#!/usr/bin/python2.6
#
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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

"""
aimanifest.py: aimanifest commandline wrapper around Manifest Input Module
"""

import errno
import gettext
import logging
import os
import sys

from optparse import OptionParser
from traceback import print_exc

import solaris_install.manifest_input as milib

from solaris_install.logger import InstallLogger
from solaris_install.manifest_input.mim import ManifestInput

_ = gettext.translation('solaris_install_aimanifest', '/usr/share/locale',
                        fallback=True).gettext

AIM_LOGGER = None

VALIDATE = True
NO_VALIDATE = False


class AimOptionParser(OptionParser):
    '''
    OptionParser which provides error_w_errno() to return a more correct errno
    '''

    def error_w_errno(self, errnum, message):
        '''
        Log and display a message, and exit with errnum status
        '''
        AIM_LOGGER.error(message)
        print >> sys.stderr, _("Usage:\n") + self.usage + "\n"
        print >> sys.stderr, os.path.basename(sys.argv[0]) + \
                                             ": error: " + message
        sys.exit(errnum)


def usage(argv):
    '''
    Assemble command usage string.
    '''

    name = os.path.basename(argv[0])
    usage_str = _(
        "    %s subcommand cmd_options\n" +
        "    subcommands:\n" +
        "    " + name + " set [-r] <path> <value>  " +
                  "Change value or add/change attributes\n" +
        "    " + name + " add [-r] <path> <value>  Add new element\n" +
        "    " + name + " get [-r] <path>          " +
                  "Retrieve element value or attributes\n" +
        "    " + name + " load [-i] <filename>     " +
                  "Load / incrementally overlay XML file\n" +
        "    " + name + " validate                 Validate XML data\n" +
        "\n    The -r option to set/add/get displays the path of " +
                  "the returned element\n" +
        "    in terms of node IDs.  This path may be used in " +
                  "subsequent calls to\n" +
        "    %s to specify the affected element more directly.\n" +
        "\n    The following environment variables are read:\n" +
        "      AIM_MANIFEST: Pathname of the evolving manifest.            " +
                  "(Must be set)\n" +
        "      AIM_DTD: Overrides the DTD given in the evolving manifest.  " +
                  "(Optional)\n" +
        "      AIM_LOGFILE: Logfile for additional information.            " +
                  "(Optional)\n") % (
        name, name)
    return usage_str


def _handle_error(error):
    '''
    Display the error message, log the whole traceback and set errno

    Args:
      error: exception containing message and, if IOError, an errno.
              Assume messages are localized.

    Returns:
      errno: EINVAL unless overridden by an IOError exception's errno.
    '''
    if isinstance(error, milib.MimMultMsgError):
        for msg in error.errors:
            # These messages come already localized.
            print >> sys.stderr, msg
            AIM_LOGGER.error(msg)
    else:
        print >> sys.stderr, str(error)
        AIM_LOGGER.exception(str(error))
    rval = getattr(error, "errno", errno.EINVAL)

    # Handle the cases where the errno field exists in the exception
    # but is None or 0
    if not rval:
        rval = errno.EIO if isinstance(error, IOError) else errno.EINVAL
    return rval


def _log_final_status(mim, path=None):
    '''
    Log status.  Usually called after running a subcommand.  Checks to see if
    the manifest validates, when this information would be logged.  Does
    nothing if logging is disabled.

    Args:
      mim: Reference to the Manifest Input Module, needed for validation.

      path: Nodepath, used for printing only.
    '''
    if AIM_LOGGER.isEnabledFor(logging.INFO):
        try:
            mim.validate()
            validated = _("Pass")
        except (milib.MimError, IOError):
            validated = _("Fail")
        out = _("cmd:success, validation:") + validated
        if path:
            out += _(", node:") + path
        AIM_LOGGER.info(out)


def _setup_logging():
    '''
    Set up logging.

    If AIM_LOGFILE is set in the environment, enable logging to the file
    specified by AIM_LOGFILE.  Enable logging at the level specified by
    the environment variable AIM_LOGLEVEL if set, else set to the INFO level
    by default.  (These two variables (and logging here in general) is to
    support the Derived Manifest Module (DMM).
    '''
    # pylint: disable-msg=W0603
    global AIM_LOGGER

    logging.setLoggerClass(InstallLogger)
    AIM_LOGGER = logging.getLogger("aimanifest")
    logfile_name = os.environ.get("AIM_LOGFILE")
    if logfile_name is not None:
        try:
            logging.basicConfig(format="%(asctime)s: %(name)s: "
                                "%(levelname)s: %(message)s",
                                datefmt="%H:%M:%S",
                                filename=logfile_name,
                                filemode="a")
        except IOError as (errno, strerror):
            raise SystemExit(_("AIM_LOGFILE I/O Error(%(errno)s) :"
                               "%(strerror)s : %(fname)s"
                               % ({"errno": errno, "strerror": strerror, \
                               "fname": logfile_name})))

        logging_level = os.environ.get("AIM_LOGLEVEL")
        if logging_level and logging_level.isdigit():
            AIM_LOGGER.setLevel(int(logging_level))
        else:
            AIM_LOGGER.setLevel(logging.INFO)
    else:
        AIM_LOGGER.setLevel(logging.NOTSET)


def _shutdown_logging():
    '''
    Shut down logging.
    '''
    logging.shutdown()


def _do_aimanifest(argv):
    '''
    Main.  See usage for argv details.
    '''

    usage_str = usage(argv)

    if len(argv) <= 1:
        AIM_LOGGER.error(_("Error: Missing subcommand"))
        print >> sys.stderr, _("Usage:\n") + usage_str
        return errno.EINVAL

    parser = AimOptionParser(usage=usage_str)
    parser.add_option("-i", "--incremental", dest="is_incremental",
                      default=False, action="store_true",
                      help=_("Do not clear data before adding new data"))
    parser.add_option("-r", "--return-path", dest="show_path", default=False,
                      action="store_true",
                      help=_("Return unique path to affected node"))

    (options, args) = parser.parse_args(argv[1:])
    len_args = len(args)
    command = args[0]
    path = args[1] if (len_args > 1) else None
    value = args[2] if (len_args > 2) else None

    cmds_r_option = ["add", "set", "get"]
    cmds_w_value_arg = ["add", "set"]
    cmds_wo_value_arg = ["get", "load"]
    cmds_w_no_args = ["validate"]

    if ((command in cmds_w_value_arg and (len_args < 3)) or
        (command in cmds_wo_value_arg and (len_args < 2))):
        parser.error_w_errno(errno.EINVAL, _("missing argument"))
    if ((command in cmds_w_value_arg and (len_args > 3)) or
        (command in cmds_wo_value_arg and (len_args > 2)) or
        (command in cmds_w_no_args and (len_args > 1))):
        parser.error_w_errno(errno.EINVAL, _("extra arguments given"))
    if (command != "load") and options.is_incremental:
        parser.error_w_errno(errno.EINVAL,
                     _("-i is not applicable for command given"))
    if command not in cmds_r_option and options.show_path:
        parser.error_w_errno(errno.EINVAL,
                     _("-r is not applicable for command given"))

    # Pass AIM_MANIFEST as the output file.
    try:
        mim = ManifestInput(os.environ.get("AIM_MANIFEST"),
                            os.environ.get("AIM_DTD"))
    except (milib.MimError, IOError) as err:
        return (_handle_error(err))

    if (command == "set") or (command == "add"):
        AIM_LOGGER.info(_("command:%(mcommand)s, path:%(mpath)s, "
                "value:%(mvalue)s") %
                {"mcommand": command, "mpath": path, "mvalue": value})
        try:
            if command == "set":
                path = mim.set(path, value)
            else:
                path = mim.add(path, value)
            mim.commit(NO_VALIDATE)
        except (milib.MimError, IOError) as err:
            return (_handle_error(err))

        _log_final_status(mim, path)
        if options.show_path:
            # Localization not needed here.
            print path

    elif command == "get":
        AIM_LOGGER.info(_("command:%(mcommand)s, path:%(mpath)s") %
                {"mcommand": command, "mpath": path})
        try:
            (value, path) = mim.get(path)
        except (milib.MimError, IOError) as err:
            return (_handle_error(err))

        if value is None or not len(value):
            value = "\"\""

        AIM_LOGGER.info(_("successful: returns value:%(mvalue)s, "
                      "path:%(mpath)s") % {"mvalue": value, "mpath": path})

        # Localization not needed here.
        if not options.show_path:
            print "%s" % value
        else:
            print "%s %s" % (value, path)

    elif (command == "load"):
        # path arg holds the filename
        AIM_LOGGER.info(_("command:%(mcommand)s, "
                      "incremental:%(mincr)s, file:%(mfile)s") %
                    {"mcommand": command, "mincr": str(options.is_incremental),
                     "mfile": path})
        try:
            mim.load(path, options.is_incremental)
            mim.commit(NO_VALIDATE)
        except (milib.MimError, IOError) as err:
            return (_handle_error(err))

        _log_final_status(mim, path)

    elif (command == "validate"):
        AIM_LOGGER.info(_("Command:%s") % command)
        try:
            mim.validate()
            AIM_LOGGER.info(_("Validation successful"))
        except (milib.MimError, IOError) as err:
            return (_handle_error(err))

    else:
        AIM_LOGGER.error(_("Invalid subcommand \"%s\"") % command)
        print >> sys.stderr, _("Usage:\n") + usage_str
        return errno.EINVAL

    return 0  # No errors


def main(argv):
    '''
    Main program.
    '''
    _setup_logging()
    rval = 1
    try:
        rval = _do_aimanifest(argv)
    except StandardError as err:
        # Catch unexpected exceptions, logging and displaying a traceback.
        print >> sys.stderr, str(err)
        AIM_LOGGER.exception(str(err))
        print_exc()
    _shutdown_logging()
    return rval


if __name__ == "__main__":
    sys.exit(main(sys.argv))
