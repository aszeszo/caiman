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

from collections import namedtuple
import logging
import os
from select import select
import subprocess


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
            end_buf, newline, begin_buf = output.partition("\n")
            self._buffer.append(end_buf)
            log_out = "".join(self._buffer)
            self.logger.log(self.loglevel, log_out)
            
            # Keep a record of all output retrieved so far in the
            # self._all variable, so that the full output
            # may be retrieved later
            self._all.extend((log_out, newline))
            self._buffer = [begin_buf]
        else:
            self._buffer.append(output)
    
    def all_output(self):
        '''Return all the output retrieved'''
        self.read_filehandle(flush=True)
        return "".join(self._all)


class Popen(subprocess.Popen):
    '''Enhanced version of subprocess.Popen with functionality commonly
    used by install technologies
    
    '''
    
    PIPE = subprocess.PIPE
    STDOUT = subprocess.STDOUT
    STORE = object()
    
    STDERR_EMPTY = object()
    SUCCESS = (0, STDERR_EMPTY)
    
    LOG_BUFSIZE = 8192
    
    def __init__(self, args, bufsize=0, executable=None,
                 stdin=None, stdout=None, stderr=None,
                 preexec_fn=None, close_fds=False, shell=False,
                 cwd=None, env=None, universal_newlines=False,
                 startupinfo=None, creationflags=0, check_result=None,
                 logger=None, stdout_loglevel=logging.DEBUG,
                 stderr_loglevel=logging.ERROR):
        '''solaris_install.Popen is interface compatible with
        subprocess.Popen, accepting all the same positional/keyword arguments.
        
        solaris_install.Popen also provides additional functionality (see
        below).
        ***NOTE*** In all cases, using the additional functionality changes
        the behavior of Popen instantiation to BLOCK until the subprocess
        completes.
        
        solaris_install.Popen accepts an additional special value for
        the 'stdout' and 'stderr' keywords: solaris_install.Popen.STORE
        If stdout and/or stderr is set to Popen.STORE, the subprocess'
        stdout and/or stderr will be captured and saved in self.stdout
        and/or self.stderr.
        Note: This means that if Popen.STORE is used, the caller will
        be unable to reference the *file handles* to the subprocess'
        stdout/stderr upon completion of the process.
        
        logger: If given, the stdout and stderr output from the subprocess
        will be logged to this logger. (This parameter also accepts a string,
        which will be passed to logging.getLogger() to retrieve an appropriate
        logger). stdout/stderr must be set to Popen.STORE for this
        functionality to work. See also stdout_loglevel and stderr_loglevel
        
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
        was any output to stderr. Note that stderr must be set to Popen.STORE
        for this to be successful.
        
        If any of the prior functionality is used, and check_result is NOT
        set, it will default to (0, STDERR_EMPTY).
        
        '''
        self.__args = args
        wait = False
        
        if stdout is self.STORE:
            stdout = subprocess.PIPE
            wait = True
        if stderr is self.STORE:
            stderr = subprocess.PIPE
            wait = True
        if check_result is not None:
            wait = True
        if logger is not None:
            wait = True
            if isinstance(logger, basestring):
                logger = logging.getLogger(logger)
            if logger.isEnabledFor(stdout_loglevel):
                logger.log(stdout_loglevel, "Executing: %s", self.__args)
        if wait and check_result is None:
            check_result = self.SUCCESS
        
        super(Popen, self).__init__(args, bufsize=bufsize,
                                    executable=executable, stdin=stdin,
                                    stdout=stdout, stderr=stderr,
                                    preexec_fn=preexec_fn, close_fds=close_fds,
                                    shell=shell, cwd=cwd, env=env,
                                    universal_newlines=universal_newlines,
                                    startupinfo=startupinfo,
                                    creationflags=creationflags)
        
        if wait:
            if logger is None:
                # Simple case - capture all output, and replace the
                # self.stdout/stderr filehandles with the actual output
                output = self.communicate()
                self.stdout, self.stderr = output
            else:
                if bufsize > 1:
                    log_bufsize = bufsize
                else:
                    log_bufsize = self.LOG_BUFSIZE
                self.stdout, self.stderr = self.__log(logger, log_bufsize,
                                                      stdout_loglevel,
                                                      stderr_loglevel)
            
            if self.returncode not in check_result:
                raise CalledProcessError(self.returncode, self.__args, self)
            if self.stderr and self.STDERR_EMPTY in check_result:
                raise StderrCalledProcessError(self.returncode, self.__args,
                                               self)
    
    def __log(self, logger, bufsize, stdout_loglevel, stderr_loglevel):
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
            ready = select(select_from, [], [])[0]
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
