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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""dc_utils.py - Distribution Constructor utility functions."""

import os
import logging
import datetime

from osol_install.distro_const.dc_defs import DC_LOGGER_NAME

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_value(manifest_obj, path, is_key=False):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Read the value of the path specified.
    This returns only the first value of the list.

    Args:
       manifest_obj: Manifest object (could be ManifestServ or
            ManifestRead object)
       path: path to read
       is_key: Set to True if the path is to be interpreted as a key

    Returns:
       the first value found (as a string) if there is at least
            one value to retrieve.
       None: if no value found

    Raises:
       None

    """

    node_list = manifest_obj.get_values(path, is_key)
    if node_list and node_list[0]:
        return str(node_list[0])
    return None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_list(manifest_obj, path, is_key=False):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Create a list of the values of the path specified.

    Args:
       manifest_obj: Manifest object (could be ManifestServ or
            ManifestRead object)
       path: path to read from
       is_key: Set to True if the path is to be interpreted as a key

    Returns:
       A list of values.
       An empty list is returned if no values are found.

    Raises:
       None

    """

    node_list = manifest_obj.get_values(path, is_key)
    return_node_list = []

    for node in node_list:
        if node:
            return_node_list.append(str(node))
    return return_node_list

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_manifest_boolean(manifest_obj, path, is_key=False):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Get the value of the path specified as a boolean value.
    This is a wrapper for get_manifest_value(), but it is more
    convenient to check the string and return the boolean value here
    than have code to check for it every place in the main program.

    Args:
       manifest_obj: Manifest object (could be ManifestServ or
            ManifestRead object)
       path: path to read
       is_key: Set to True if the path is to be interpreted as a key

    Returns:
       None: if value from get_manifest_value() returns none.
       true: if the string from get_manifest_value() is "true", regardless
       case, this will return true.
       false: it the string from get_manifest_value() is not "true"

    Raises:
       None

    """

    str_val = get_manifest_value(manifest_obj, path, is_key)
    if str_val is None:
        return None
    return ((str_val.lower()) == "true")


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def cleanup_dir(mntpt):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Remove all files and directories underneath the mount point.
    Any errors are ignored since they aren't fatal.

    Input:
       mntpt: mount point to remove files and directories from

    Returns:
       None

    Raises:
       None

    """

    for root, dirs, files in os.walk(mntpt, topdown=False):
        for name in files:
            try:
                os.unlink(os.path.join(root, name))
            except OSError:
                pass

        for direct in dirs:
            try:
                os.rmdir(os.path.join(root, direct))
            except OSError:
                pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def setup_dc_logfile_names(logging_dir):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Computes the name of the simple and detail log based on time

    Input:
       logging_dir: name of the log file directory

    Returns:
       Name of the simple log and detail log

    Raises:
       None

    """

    timeformat_str = "%Y-%m-%d-%H-%M-%S"
    now = datetime.datetime.now()
    str_timestamp = now.strftime(timeformat_str)

    simple_log_name = logging_dir + "/simple-log-" + str_timestamp
    detail_log_name = logging_dir + "/detail-log-" + str_timestamp

    return (simple_log_name, detail_log_name)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def setup_dc_logging():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Setup logging for the Distribution Constructor application
    Log information.  Logging information will only go to the console
    for now.  The console will be set to have a debugging level of INFO

    Input:
       None

    Returns:
       The logger object

    Raises:
       None

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    #
    # Need to set the most top level one to the lowest log level
    # so all handlers added can also log at various levels
    #
    dc_log.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    dc_log.addHandler(console)

    return (dc_log)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def add_file_logging(simple_log_name, detail_log_name):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Add 2 file loggers where logged information will go to
    the 2 specified files.
    - The simple log will go into the file specified in simple_log_name.
    The simple log will have debug level of INFO
    - The detail log will go into the file specified in detail_log_name.
    The detail log will have debug level of DEBUG

    Input:
       simple_log_name: name of the log file for the simple log
       detail_log_name: name of the log file for the detail log

    Returns:
       None

    Raises:
       None

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)

    simple_log = logging.FileHandler(simple_log_name, "a+")
    simple_log.setLevel(logging.INFO)
    dc_log.addHandler(simple_log)

    detail_log = logging.FileHandler(detail_log_name, "a+")
    detail_log.setLevel(logging.DEBUG)
    dc_log.addHandler(detail_log)
