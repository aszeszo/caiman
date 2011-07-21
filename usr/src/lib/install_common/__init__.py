#!/usr/bin/python
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''Module body for solaris_install package

Classes, functions and variables that are globally useful to install
technologies should go here.

'''

import errno
import functools
import gettext
import logging
import os
import shutil
import sys
import subprocess

from collections import namedtuple
from select import select

from data_object import DataObject

from solaris_install.logger import INSTALL_LOGGER_NAME


_ = gettext.translation('AI', '/usr/share/locale', fallback=True).gettext

# Useful common directories and path pieces

# System Temporary Directory - for secure processes
SYSTEM_TEMP_DIR = '/system/volatile'

# Post-Install Logs Location
POST_INSTALL_LOGS_DIR = '/var/sadm/system/logs'

# DOC label for entries pertaining to the distribution constructor
# All 'volatile' entries are stored in DC_LABEL and all 'persistent'
# entries are stored in DC_PERS_LABEL
DC_LABEL = "DC specific"
DC_PERS_LABEL = "DC specific persistent"


class CalledProcessError(subprocess.CalledProcessError):
    '''Expansion of subprocess.CalledProcessError that may optionally
    store a reference to the Popen object that caused the error.

    '''
    def __init__(self, returncode, cmd, popen=None):
        super(CalledProcessError, self).__init__(returncode, cmd)
        self.popen = popen

    def __str__(self):
        return ("Command '%s' returned unexpected exit status %s" %
                (self.cmd, self.returncode))


class StderrCalledProcessError(CalledProcessError):
    '''A subprocess generated output to stderr'''
    def __str__(self):
        return "Command '%s' generated error output" % self.cmd


class _LogBuffer(object):
    '''Class that reads from a filehandle (given by fileno), buffers
    the output and dumps to a logger on newlines

    '''
    def __init__(self, fileno, logger, loglevel, bufsize):
        '''fileno - File number of the file handle to read from
        logger - The logger to log to
        loglevel - The level at which to log
        bufsize - How much to try and read at any given time

        '''
        self.fileno = fileno
        self.logger = logger
        self.loglevel = loglevel
        self.bufsize = bufsize

        self._buffer = []
        self._all = []

    def read_filehandle(self, flush=False):
        '''Read pending output from the filehandle, and store it in
        the internal buffer. If the output contains a newline, or
        flush=True, then flush the internal buffer to the logger

        '''
        output = os.read(self.fileno, self.bufsize)
        if "\n" in output or flush:
            # "Flush" the _LogBuffer's buffer to the logger,
            # and add the output to the list of all output
            # captured so far. Trailing newline is stripped,
            # as it is expected that the logger will *add* one
            if flush:
                end_buf, newline, begin_buf = output, '', ''
            else:
                end_buf, newline, begin_buf = output.rpartition("\n")
            self._buffer.append(end_buf)
            flush_out = "".join(self._buffer)

            log_out = flush_out.strip()
            if log_out:
                # Avoid sending blank lines to the logger
                self.logger.log(self.loglevel, log_out)

            # Keep a record of all output retrieved so far in the
            # self._all variable, so that the full output
            # may be retrieved later. (Note that blank lines here are
            # preserved, in contrast with what is logged)
            self._all.extend((flush_out, newline))
            self._buffer = [begin_buf]
        else:
            self._buffer.append(output)

    def all_output(self):
        '''Return all the output retrieved'''
        self.read_filehandle(flush=True)
        return "".join(self._all)


class Popen(subprocess.Popen):
    '''Enhanced version of subprocess.Popen with functionality commonly
    used by install technologies. Functionality that requires blocking until
    the subprocess completes is contained within the check_call classmethod,
    which is similar to subprocess.check_call.

    === Usage examples ===
    The below examples all assume the command to be run is stored
    in a list named 'cmd', e.g., cmd = ['/usr/bin/ls', '-l', '/tmp']

    * Run a command, raising an exception for non-zero return
    >>> Popen.check_call(cmd)

    * Run a command, saving all stdout and stderr output
    >>> ls = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
    >>> print ls.stdout
    srwxrwxrwx 1 root     root     0 2011-02-14 09:14 dbus-zObU7eocIA

    * Run a command, logging stderr and ignoring stdout
    >>> mylogger = logging.getLogger('MyLogger')
    >>> ls = Popen.check_call(cmd, stdout=Popen.DEVNULL, stderr=Popen.STORE,
                              logger=mylogger)

    * Run a command, logging stderr at the logging.INFO level
    >>> ls = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                              logger="MyLogger", stderr_loglevel=logging.INFO)

    * Run a command, triggering an exception if the returncode is
      anything EXCEPT '4' or '-1'
    >>> Popen.check_call(cmd, check_result=(-1, 4))

    * Run a command, and trigger an exception if it printed anything
      to stderr
    >>> Popen.check_call(cmd, stderr=Popen.PIPE,
                         check_result=(Popen.STDERR_EMPTY,))

    * Run a command, storing stdout, and ignoring the returncode
    >>> ls = Popen.check_call(cmd, stdout=Popen.STORE, check_result=Popen.ANY)

    '''

    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    STORE = object()
    DEVNULL = object()

    ANY = object()
    STDERR_EMPTY = object()
    SUCCESS = (0,)

    LOG_BUFSIZE = 8192

    def __init__(self, args, bufsize=0, executable=None,
                   stdin=None, stdout=None, stderr=None,
                   preexec_fn=None, close_fds=False, shell=False,
                   cwd=None, env=None, universal_newlines=False,
                   startupinfo=None, creationflags=0):
        if stdout is Popen.DEVNULL:
            stdout = open(os.devnull, "w+")

        if stderr is Popen.DEVNULL:
            stderr = open(os.devnull, "w+")

        if stdin is Popen.DEVNULL:
            stdin = open(os.devnull, "r+")

        super(Popen, self).__init__(args, bufsize=bufsize,
                                    executable=executable, stdin=stdin,
                                    stdout=stdout, stderr=stderr,
                                    preexec_fn=preexec_fn, close_fds=close_fds,
                                    shell=shell, cwd=cwd, env=env,
                                    universal_newlines=universal_newlines,
                                    startupinfo=startupinfo,
                                    creationflags=creationflags)

    @classmethod
    def check_call(cls, args, bufsize=0, executable=None,
                   stdin=None, stdout=None, stderr=None,
                   preexec_fn=None, close_fds=False, shell=False,
                   cwd=None, env=None, universal_newlines=False,
                   startupinfo=None, creationflags=0, check_result=None,
                   logger=None, stdout_loglevel=logging.DEBUG,
                   stderr_loglevel=logging.ERROR):
        '''solaris_install.Popen.check_call is interface compatible with
        subprocess.check_call, accepting all the same positional/keyword
        arguments.

        solaris_install.Popen.check_call will store the output from stdout and
        stderr if they are set to Popen.STORE. Note that
        Popen.stdout and Popen.stderr are replaced with a string -
        references to filehandles won't be preserved in the manner that a
        standard use of the Popen class allows.

        logger: If given, the stdout and stderr output from the subprocess
        will be logged to this logger. (This parameter also accepts a string,
        which will be passed to logging.getLogger() to retrieve an appropriate
        logger). One or both of stdout/stderr must be set to Popen.PIPE or
        Popen.STORE for this functionality to work (a ValueError is raised
        if that is not the case). See also stdout_loglevel and stderr_loglevel

        stdout_loglevel and stderr_loglevel: If the stdout/stderr output
        from the subprocess are logged as a result of logger being set,
        the output will be logged at the specified log level. Defaults are:
            stdout_loglevel: logging.DEBUG
            stderr_loglevel: logging.ERROR

        check_result: If specified, should be an iterable of all "acceptable"
        values for the return code of the process. If the subprocess' return
        code is not one of the given values, then a CalledProcessError
        will be raised upon command completion. In addition to integer values,
        the special value solaris_install.Popen.STDERR_EMPTY may be
        included; if it is, then the subprocess will be considered to have
        exited unsuccessfully (and a CalledProcessError raised) if there
        was any output to stderr. Note that stderr must be set to
        Popen.STORE for this to be successful. By default, any non-zero
        returncodes are considered errors.

        Setting check_result=Popen.ANY causes this function to mimic
        subprocess.call (that is, the returncode will be ignored and the
        caller is expected to ensure that appropriate behavior occurred)

        '''
        if check_result is None:
            check_result = Popen.SUCCESS

        # While Popen.STORE is essentially identical to Popen.PIPE currently,
        # the separate Popen.STORE parameter is preserved in case the
        # functionality diverges in the future. Consumers should use
        # Popen.STORE to ensure forwards-compatibility.
        if stdout is Popen.STORE:
            stdout = Popen.PIPE

        if stderr is Popen.STORE:
            stderr = Popen.PIPE

        if logger is not None:
            if stderr is not Popen.PIPE and stdout is not Popen.PIPE:
                raise ValueError("'logger' argument requires one or both "
                                 "of stdout/stderr to be set to PIPE or "
                                 "STORE")
            if isinstance(logger, basestring):
                logger = logging.getLogger(logger)
            if logger.isEnabledFor(stdout_loglevel):
                logger.log(stdout_loglevel, "Executing: %s", args)

        popen = cls(args, bufsize=bufsize,
                    executable=executable, stdin=stdin,
                    stdout=stdout, stderr=stderr,
                    preexec_fn=preexec_fn, close_fds=close_fds,
                    shell=shell, cwd=cwd, env=env,
                    universal_newlines=universal_newlines,
                    startupinfo=startupinfo,
                    creationflags=creationflags)

        if logger is None:
            # Simple case - capture all output, and replace the
            # Popen.stdout/stderr filehandles with the actual output
            output = popen.communicate()
            popen.stdout, popen.stderr = output
        else:
            if bufsize > 1:
                log_bufsize = bufsize
            else:
                log_bufsize = Popen.LOG_BUFSIZE
            popen.stdout, popen.stderr = popen._log(logger, log_bufsize,
                                                    stdout_loglevel,
                                                    stderr_loglevel)
        if check_result is Popen.ANY:
            return popen
        if popen.returncode not in check_result:
            raise CalledProcessError(popen.returncode, args, popen)
        if popen.stderr and popen.STDERR_EMPTY in check_result:
            raise StderrCalledProcessError(popen.returncode, args, popen)

        return popen

    def _log(self, logger, bufsize, stdout_loglevel, stderr_loglevel):
        '''Poll the stdout/stderr pipes for output, occasionally
        dumping that output to the log.

        While the subprocess is running, the filehandles are checked (using
        select) for any pending output. The output is stored in memory,
        until a newline is found, at which point it's passed to the
        logger. (see _LogBuffer class, above)

        Additionally, all output is stored. This function returns a tuple
        of (stdout, stderr), like Popen.communicate()

        '''
        select_from = []
        if self.stdout:
            stdout_logbuffer = _LogBuffer(self.stdout.fileno(), logger,
                                          stdout_loglevel, bufsize)
            select_from.append(self.stdout.fileno())
        else:
            stdout_logbuffer = None
        if self.stderr:
            stderr_logbuffer = _LogBuffer(self.stderr.fileno(), logger,
                                          stderr_loglevel, bufsize)
            select_from.append(self.stderr.fileno())
        else:
            stderr_logbuffer = None

        while self.poll() is None:
            ready = select(select_from, [], [], 0.25)[0]
            if stdout_logbuffer and stdout_logbuffer.fileno in ready:
                stdout_logbuffer.read_filehandle()
            if stderr_logbuffer and stderr_logbuffer.fileno in ready:
                stderr_logbuffer.read_filehandle()

        if stdout_logbuffer:
            stdout = stdout_logbuffer.all_output()
        else:
            stdout = None
        if stderr_logbuffer:
            stderr = stderr_logbuffer.all_output()
        else:
            stderr = None
        return stdout, stderr


# create a functools.partial object to represent common invocations of Popen.
#
# usage:
# from solaris_install import run, run_slient
# cmd = [my command]
# p = run(cmd)   # p.stdout and p.stderr are available as normal
# runsilent(cmd)  # p.stdout and p.stderr are set to /dev/null

run = functools.partial(Popen.check_call, stdout=Popen.STORE,
                        stderr=Popen.STORE, stderr_loglevel=logging.DEBUG,
                        logger=INSTALL_LOGGER_NAME)
run_silent = functools.partial(Popen.check_call, stdout=Popen.DEVNULL,
                               stderr=Popen.DEVNULL)


class ApplicationData(DataObject):
    """Application Data class

    Provides a location for CUD applications to store application specific data
    that checkpoints, etc. may require access to.

    Currently stores:
    - Application Name
    - Work Directory, defaulting to /system/volatile
    """

    def __init__(self, application_name, work_dir="/system/volatile/"):
        super(ApplicationData, self).__init__(application_name)

        self._application_name = application_name
        self._work_dir = work_dir
        self.data_dict = dict()

    @property
    def application_name(self):
        """Read-only Application Name - set at initialisation"""
        return self._application_name

    @property
    def work_dir(self):
        """Read-only Work Directory - set at initialisation"""
        return self._work_dir

    # Implement no-op XML methods
    def to_xml(self):
        return None

    @classmethod
    def can_handle(cls, element):
        return False

    @classmethod
    def from_xml(cls, element):
        return None


# Utility methods to generate paths given files
def system_temp_path(file=None):
    ''' Return System Temporary Directory, with file string appended'''
    if file is not None:
        return os.path.sep.join([SYSTEM_TEMP_DIR, file])
    else:
        return SYSTEM_TEMP_DIR


def post_install_logs_path(file=None):
    ''' Return Post-Install Logs Directory, with file string appended'''
    if file is not None:
        return os.path.sep.join([POST_INSTALL_LOGS_DIR, file])
    else:
        return POST_INSTALL_LOGS_DIR


def force_delete(path):
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
    except (IOError, OSError) as err:
        if getattr(err, "errno", None) != errno.ENOENT:
            raise
