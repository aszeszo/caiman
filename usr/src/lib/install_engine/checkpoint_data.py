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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''
Class for keeping track of bookkeeping information for checkpoints
'''

import decimal
import imp
import logging
import os
import sys
import warnings

from itertools import izip

from osol_install.install_utils import get_argspec
from solaris_install.data_object import DataObject
from solaris_install.logger import INSTALL_LOGGER_NAME

def validate_function_args(func, args, kwargs):
    ''' Make sure all required and keyword parameters are passed in
        to the constructor of the checkpoint class.
        Python 2.7's  inspect module has a getcallargs() function that
        does what this function does.  So, when we migrate to
        Python 2.7 or higher, this function can be replaced with the one from
        Python 2.7. '''

    # make a copy of kwargs so this function can manipulate the copy
    # instead of the acutal dictionary
    kwargs_copy = kwargs.copy()

    spec = get_argspec(func)

    num_spec_args = len(spec.args)
    arg_value = {}

    # fill with expected arguments
    arg_value.update(izip(spec.args, args))

    # in case there are expected arguments that a user has
    # specified by name, fill them in here.
    for arg_ in spec.args:
        if arg_ in kwargs_copy:
            if arg_ in arg_value:
                raise TypeError(arg_ + "is specified twice in the arguments")
            else:
                arg_value[arg_] = kwargs_copy.pop(arg_)

    default_val = {}
    if spec.defaults is not None:
        # match the defaults with the keywords
        default_val = {}
        i = 1
        for default in reversed(spec.defaults):
            key = spec.args[num_spec_args - i]
            i += 1
            default_val[key] = default

    # fill in any missing values with the defaults
    for key_ in default_val.keys():
        if key_ not in arg_value:
            arg_value[key_] = default_val[key_]

    # Go through all the required arguments, they should all have values now
    for arg_ in spec.args:
        if arg_ not in arg_value:
            raise TypeError("Argument %s is required, but not specified. \
                            spec = %s, args = %s, kwargs = %s" % \
                            (arg_, spec, args, kwargs))

    # Make sure variable keyword arguments are not specified if not expected

    var_kw_len = len(kwargs_copy)

    if (spec.keywords is None) and (var_kw_len != 0):
        # We don't expect any variable keywords, but some is supplied
        raise TypeError("Variable keyword argument not expected, but "
                        "%d unexpected keyword argument supplied. Unexpected "
                        "keywords are: %s" % (var_kw_len, str(kwargs_copy)))


class CheckpointRegistrationData(DataObject):
    ''' All values stored here are provided during checkpoint registration '''
    def __init__(self, name, mod_name, module_path, checkpoint_class_name,
                 loglevel, args, kwargs):

        self.cp_name = name
        self.mod_name = mod_name
        self.module_path = module_path
        self.checkpoint_class_name = checkpoint_class_name
        self.loglevel = loglevel

        if args is None:
            self.args = ()
        else:
            self.args = args

        if kwargs is None:
            self.kwargs = {}
        else:
            self.kwargs = kwargs

        DataObject.__init__(self, name)

    def __eq__(self, other):
        return (self.cp_name == other.cp_name and \
               self.mod_name == other.mod_name and \
               self.module_path == other.module_path and \
               self.checkpoint_class_name == other.checkpoint_class_name and \
               self.args == other.args and \
               self.kwargs == other.kwargs)

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_xml(self):
        ''' Data to be used by engine only, will not be written to XML '''
        return None

    @classmethod
    def from_xml(cls, xml_node):
        ''' Data to be used by engine only, will not be retrieved XML '''
        return None

    @classmethod
    def can_handle(cls, xml_node):
        ''' Data to be used by engine only, will not be retrieved XML '''
        return False


class CheckpointData(object):

    ''' This is used for storing checkpoint related value that's generated, and
        used by engine.  The values here are not stored in the DOC '''

    def __init__(self, name, mod_name, module_path, checkpoint_class_name,
                 loglevel, args, kwargs):

        self.cp_info = CheckpointRegistrationData(name, mod_name, module_path,
                                                  checkpoint_class_name,
                                                  loglevel, args, kwargs)

        self.logger = logging.getLogger(INSTALL_LOGGER_NAME + "." + name)
        self.mod = None
        self.checkpoint_class = None
        self.completed = False
        self.zfs_snap = None
        self.data_cache_path = None
        self.prog_est = decimal.Decimal('0')
        self.prog_est_ratio = decimal.Decimal('0')
        self.prog_reported = decimal.Decimal('0')

    def validate_checkpoint_info(self):
        ''' Validate the information provided for the checkpoint '''

        # Check whether the module is under sys.path.  If not, throw a warning
        if self.cp_info.module_path is not None:
            in_sys_path = False
            for path_ in sys.path:
                if self.cp_info.module_path.startswith(path_):
                    in_sys_path = True
                    break

            if not in_sys_path:
                self.logger.warn(self.cp_info.module_path + \
                                 " is not in sys.path")
                warnings.warn(self.cp_info.module_path + \
                              " is not in sys.path.", RuntimeWarning)

        self._load_module()

        # Make sure all required arguments for the constructor of the
        # checkpoint are provided during registration.   The "self"
        # and "checkpoint_name" arguments are expected by checkpoint
        # constructors but they are not provided registration,
        # add them explicitly.

        args_chk = ["self", "checkpoint_name"]
        args_chk.extend(self.cp_info.args)

        validate_function_args(self.checkpoint_class, args_chk,
                               self.cp_info.kwargs)

    @property
    def name(self):
        ''' Make it easier to get the name value '''
        return self.cp_info.cp_name

    def _load_module(self):
        ''' Load the checkpoint into memory.  This will not instantiate it '''
        self.mod = None

        if self.cp_info.mod_name in sys.modules:
            # if the module has already been loaded, just use it.
            self.mod = sys.modules[self.cp_info.mod_name]

            # if a module_path is specified, make sure it matches with the
            # one already loaded.
            if (self.cp_info.module_path is not None):
                full_p = os.path.join(self.cp_info.module_path,
                                      self.cp_info.mod_name)
                if not self.mod.__file__.startswith(full_p):
                    # Another module with the same name from a different path
                    # is already loaded.  Give a warning so the caller
                    # is aware.
                    self.logger.warn(self.cp_info.mod_name +
                                     " is previous loaded from " +
                                     self.mod.__file__ +
                                     ".  It will be overwritten by the " +
                                     "copy from " + full_p)
                    warnings.warn(self.cp_info.mod_name +
                                  " is previous loaded from " +
                                  self.mod.__file__ +
                                  ".  It will be overwritten by the " +
                                  "copy from " + full_p, RuntimeWarning)
                    self.mod = None

        if self.mod is None:
            # find and load the module
            if self.cp_info.module_path is None:
                self.logger.debug("Loading checkpoint %s by module name (%s)",
                                  self.name, self.cp_info.mod_name)
                file_, pathname, desc = imp.find_module(self.cp_info.mod_name)
            else:
                self.logger.debug("Loading checkpoint %s by module name (%s)"
                                  " and path (%s)", self.name,
                                  self.cp_info.mod_name,
                                  self.cp_info.module_path)
                file_, pathname, desc = imp.find_module(self.cp_info.mod_name,
                                                    [self.cp_info.module_path])
                self.logger.debug("Loading module:\n\tfile = %s\n\t"
                                  "pathname = %s\n\tdescription = %s",
                                  file_, pathname, desc)
            self.mod = imp.load_module(self.cp_info.mod_name, file_,
                                       pathname, desc)

        # find the checkpoint class within the module
        self.checkpoint_class = getattr(self.mod,
                                        self.cp_info.checkpoint_class_name)

    def load_checkpoint(self):
        ''' Instantiate the checkpoint '''
        checkpoint = self.checkpoint_class(self.cp_info.name,
                                           *self.cp_info.args,
                                           **self.cp_info.kwargs)
        return checkpoint

    def __str__(self):
        return self.cp_info.cp_name
