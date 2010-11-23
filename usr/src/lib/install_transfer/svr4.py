#!/usr/bin/python
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
'''Transfer SVR4 checkpoint. Sub-class of the checkpoint class'''


import abc
import linecache
import os
import subprocess

from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.engine import InstallEngine
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import SVR4Spec
from solaris_install.transfer.info import ACTION, CONTENTS, SVR4_ARGS
from solaris_install.transfer.prog import ProgressMon

class AbstractSVR4(AbstractCheckpoint):
    '''Subclass for transfer SVR4 checkpoint'''
    __metaclass__ = abc.ABCMeta

    # constants used by svr4 transfer actions
    PKGADD = "/usr/sbin/pkgadd"
    DEFAULT_PKGADD_ARGS = "-n -d %s -R %s"
    PKGRM = "/usr/sbin/pkgrm"
    DEFAULT_PKGRM_ARGS = "-n -R %s"
    FILE = "/usr/bin/file"
    DEFAULT_PROG_EST = 10
    DEFAULT_SIZE = 512

    def __init__(self, name):
        super(AbstractSVR4, self).__init__(name)

        # Attributes per transfer action
        self.src = None
        self.datastream = False
        self.dst = None
        self.doc = None

        # Used to set for dry run
        self.dry_run = False

        # Use for progress reporting
        self.total_size = 0
        self.give_progress = False
        self.svr4_process = None
        self._cancel_event = False
        self.give_progress = False

        # Handle for the progress monitor
        self.pmon = None
        self._transfer_list = []

    def _calc_size(self):
        '''Calculate the size of the transfer. Return size is in bytes'''
        total_pkg_install_size = 0
        for trans_val in self._transfer_list:
            if trans_val.get(ACTION) == "install":
                for svr4_pkg in trans_val.get(CONTENTS):
                    # get the size of the package from the information
                    # in the source package information
                    if self.datastream:
                        svr4_pkg_info = linecache.getline(
                                        os.path.join(self.src,
                                                     svr4_pkg), 2).split()
                    else:
                        svr4_pkg_info = linecache.getline( \
                                        os.path.join(self.src, svr4_pkg,
                                                     '/pkgmap'), 1).split()
                    total_pkg_install_size += (int(svr4_pkg_info[1]) * \
                                               int(svr4_pkg_info[2]))
        return total_pkg_install_size

    def get_size(self):
        '''Compute the size of the transfer specified'''
        try:
            self._parse_input()
        except Exception:
            # Check to see if parse input failed because
            # the source doesn't exist. If we don't have
            # a src yet, then we can't compute the size
            # so just return the standard default. If the
            # src is none, it will be caught by parse_input.
            if self.src and not os.path.exists(self.src):
                return self.DEFAULT_SIZE

        self._validate_input()
        return self._calc_size()

    def get_progress_estimate(self):
        '''Returns an estimate of the time this checkpoint will take'''
        if self.total_size == 0:
            self.total_size = self.get_size()

        progress_estimate = \
            (self.total_size / self.DEFAULT_SIZE) * self.DEFAULT_PROG_EST
        self.give_progress = True
        return progress_estimate

    def execute(self, dry_run=False):
        '''Execute method for the SVR4 checkpoint module. Will read the
           input parameters and perform the specified transfer.
        '''
        self.logger.debug("Starting SVR4 transfer")
        if self.give_progress:
            self.logger.report_progress("Beginning SVR4 transfer", 0)
        else:
            self.logger.debug("Beginning SVR4 transfer")
        self.dry_run = dry_run

        try:
            # Read the parameters from the DOC and put into the
            # local attributes.
            self._parse_input()
            # Validate the attributes
            self._validate_input()

            # Check to see if a cancel event has been requested.
            self.check_cancel_event()
            # Finally, actually perform the SVR4 transfer.
            self._transfer()
        finally:
            self._cleanup()

    @abc.abstractmethod
    def _parse_input(self):
        '''This method is required to be implemented by all subclasses'''
        raise NotImplementedError

    def cancel(self):
        '''Cancel the transfer in progress'''
        self._cancel_event = True
        if self.svr4_process:
            self.svr4_process.kill()

    def check_cancel_event(self):
        '''Check the _cancel_event attribute to see if a cancel event  has been
           requested. If it has, cleanup what has been done already
        '''
        if self._cancel_event:
            self._cleanup()

    def _cleanup(self):
        '''Method to perform any necessary cleanup needed.'''
        self.logger.debug("Cleaning up")
        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None

        if self.dry_run:
            return

    def _transfer(self):
        '''Method to transfer from the source to the destination'''
        if self.give_progress:
            if self.total_size == self.DEFAULT_SIZE:
                # We weren't able to compute the size due to the
                # lack of the source when get_progress_estimate was
                # called. In order to do accurate progress estimate,
                # get that size now.
                self.total_size = self.get_size()

            # Start up the ProgressMon to report progress
            # while the actual transfer is taking place.
            self.pmon = ProgressMon(logger=self.logger)
            self.pmon.startmonitor(self.dst, self.total_size, 0, 100)

        # Perform the transfer specific operations.

        for trans_val in self._transfer_list:

            # Get the arguments for the transfer process
            arglist = trans_val.get(SVR4_ARGS).split(' ')

            # Parse the components to determine the transfer action
            if trans_val.get(ACTION) == 'install':
                self.check_cancel_event()
                self.logger.info("Installing SVR4 packages")

                # Check to see if datastream packages are selected
                if self.datastream:
                    cmd = [self.PKGADD] + arglist
                else:
                    cmd = [self.PKGADD] + arglist + trans_val.get(CONTENTS)

            elif trans_val.get(ACTION) == 'uninstall':
                self.check_cancel_event()
                self.logger.info("Uninstalling SVR4 packages")
                cmd = [self.PKGRM] + arglist + trans_val.get(CONTENTS)

            else:
                self.logger.info("Transfer action, %s, is not valid"
                                 % (trans_val.get(ACTION)))
                self.check_cancel_event()
                continue

            self.logger.info("Executing the following transfer command: %s "
                             % cmd)
            if not self.dry_run:
                self.check_cancel_event()
                pkg_proc = subprocess.Popen(cmd, shell=False,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT)
                while 1:
                    self.check_cancel_event()
                    pkgoutput = pkg_proc.stdout.readline()
                    if not pkgoutput:
                        if pkg_proc.poll() != 0:
                            self.svr4_process = None
                            raise Exception("SVR4 Transfer Error while "
                                            "adding packages")
                        break
                    pkgoutput = pkgoutput[:-1]
                    if not pkgoutput.strip():
                        continue
                    self.logger.debug("%s", pkgoutput)
                self.svr4_process = None

        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None

    def _validate_input(self):
        '''Check the required input parameters and verify that
           they are set appropriately.
        '''
        self.logger.debug("Validating SVR4 input")

        # destination is a required parameter
        if self.dst is None:
            raise ValueError("SVR4 destination must be specified")

        # Check for required attributes
        # Args are required when the transfer action is install
        # Packages are required for both install and uninstall actions
        if not self._transfer_list:
            raise ValueError("Transfer list must be specified")

        for trans_val in self._transfer_list:
            if trans_val.get(ACTION) != "install" and \
               trans_val.get(ACTION) != "uninstall":
                raise ValueError("Transfer action \"%s\" is not a"
                                 "valid SVR4 action" % trans_val.get(ACTION))

            if trans_val.get(ACTION) == "install" and \
               not trans_val.get(SVR4_ARGS):
                raise ValueError("SVR4 args must be specified")

            if not trans_val.get(CONTENTS):
                raise ValueError("SVR4 packages must be specified")

        # source is a required parameter
        if not self.src:
            raise ValueError("SVR4 source must be specified")

        if self.src:
            if not os.access(self.src, os.R_OK):
                raise ValueError("The source either "
                                 "does not exist or is unable to be read, %s",
                                 self.src)


class TransferSVR4(AbstractSVR4):
    '''Transfer subclass uses checkpoint interface. Takes data from the DOC'''
    def __init__(self, name):
        super(TransferSVR4, self).__init__(name)

        # Holds the list of transfer dictionaries
        self._transfer_list = []

        # Get the reference to the data object cache
        self.doc = InstallEngine.get_instance().data_object_cache

        # Get the checkpoint info from the DOC
        self.soft_list = self.doc.get_descendants(name=self.name,
                                             class_type=Software)

        # Check that the soft_list only has one entry
        if len(self.soft_list) != 1:
            raise ValueError("Only one value for Software node must be "
                             "specified with name " + self.name)

    def _parse_input(self):
        '''Method to read the parameters from the data object cache and
           place them into the local lists.
        '''
        self.logger.info("Parsing the data object cache")

        # Get a reference to the data object cache
        self.doc = InstallEngine.get_instance().data_object_cache

        soft_node = self.soft_list[0]

        # Get the destination info
        dst_list = soft_node.get_children(Destination.DESTINATION_LABEL,
                                          Destination)
        self.dst = (dst_list[0].get_children(Dir.DIR_LABEL, Dir)[0].dir_path)
        self.dst = self.doc.str_replace_paths_refs(self.dst)

        if len(dst_list) > 1:
            raise ValueError("Invalid to specify more than one "
                             "destination")

        # Get the source info
        src_list = soft_node.get_children(Source.SOURCE_LABEL, Source)

        if len(src_list) > 1:
            raise ValueError("Invalid to specify more than one source")

        pub = src_list[0].get_children(Publisher.PUBLISHER_LABEL, Publisher)
        origin = pub[0].get_children(Origin.ORIGIN_LABEL, Origin)[0].origin
        self.src = self.doc.str_replace_paths_refs(origin)

        if not os.path.exists(self.src):
            raise ValueError("Source doesn't exist")

        if not os.access(self.src, os.R_OK):
            raise ValueError("The source specified, " + self.src
                                      + ", is unable to be read.")

        # Get the list of transfers from this specific node in the DOC
        # and parse the information into a list of transfers that will
        # be performed
        transfer_list = soft_node.get_children(class_type=SVR4Spec)
        for trans in transfer_list:
            trans_attr = dict()

            trans_attr[ACTION] = trans.action
            trans_attr[CONTENTS] = trans.contents
            # Get the Args from the DOC if they exist.
            try:
                args = trans.get_children(Args.ARGS_LABEL, Args)
            except  ObjectNotFoundError:
                args = None

            # if no argument was specified, determine if the action
            # is pkg install or pkg uninstall and apply the appropriate
            # default args.
            self.logger.info("Determining package types "
                             "and source for transfer")
            if not args:
                if trans_attr.get(ACTION) == "install":
                    # Check to see if the packages are datastream packages
                    # All packages must be of the same type.
                    pkg_datastream_check = len(trans_attr[CONTENTS])
                    for pkg in trans_attr.get(CONTENTS):
                        cmd = [self.FILE] + [self.src + "/" + pkg]
                        if not self.dry_run:
                            pkg_proc = subprocess.Popen(cmd, shell=False,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.STDOUT)
                            self.svr4_process = pkg_proc
                            while 1:
                                self.check_cancel_event()
                                pkgoutput = pkg_proc.stdout.readline()
                                if not pkgoutput: 
                                    if pkg_proc.poll() != 0:
                                        self.svr4_process = None
                                        raise Exception("SVR4 error reading "
                                                        "packages")
                                    break
                                if "package datastream" in pkgoutput:
                                    self.datastream = True
                                    pkg_datastream_check -= 1
                            self.svr4_process = None

                    # If the datastream flag is set and pkg_datastream_check
                    # has been decremented to 0, then construct args to use
                    # datastream packages
                    if self.datastream and pkg_datastream_check == 0:
                        datastrm_src = ' '.join(["%s/%s" % (self.src, v) for v
                                        in trans_attr.get(CONTENTS)])
                        trans_attr[SVR4_ARGS] = self.DEFAULT_PKGADD_ARGS % \
                                                  (datastrm_src, self.dst)
                    elif self.datastream and pkg_datastream_check != 0:
                        raise Exception("Packages are an invalid combination "
                                        "of datastream and directory "
                                        "packages")
                    else:
                        # Use the default pkgadd args for directory-based pkgs
                        trans_attr[SVR4_ARGS] = self.DEFAULT_PKGADD_ARGS % \
                                                  (self.src, self.dst)
                else:
                    # Use the default pkgrm args
                    trans_attr[SVR4_ARGS] = self.DEFAULT_PKGRM_ARGS % \
                                              (self.dst)
            else:
                # if an argument was specified, validate that the user
                # only specified one and that it was svr4_args. Anything
                # else is invalid.
                if len(args) > 1:
                    self._cleanup()
                    raise Exception("Invalid: multiple svr4 args specified ")
                else:
                    try:
                        trans_attr[SVR4_ARGS] = args[0].arg_dict[SVR4_ARGS]
                    except KeyError:
                        self._cleanup()
                        raise Exception("Error defining svr4_args")

            # Append the transfer info to the list of transfers to be performed
            self._transfer_list.append(trans_attr)


class TransferSVR4Attr(AbstractSVR4):
    ''''SVR4 Transfer subclass that uses non-checkpoint interface'''
    def __init__(self, name):
        super(TransferSVR4Attr, self).__init__(name)

        #Default pkg arguments
        self.svr4_pkgadd_args = self.DEFAULT_PKGADD_ARGS
        self.svr4_pkgrm_args = self.DEFAULT_PKGRM_ARGS
        self.svr4_args = None

        # Transfer attributes
        self.action = None
        self.contents = None
        self.transfer_list = []

    def _parse_input(self):
        '''Parse the input parameters and put them into local attributes'''
        self.logger.info("Reading the input")

        # src is required
        if not self.src:
            raise ValueError("Source must be specified")

        #src must exist
        if not os.path.exists(self.src):
            raise ValueError("Source doesn't exist")

        #dst is required
        if not self.dst:
            raise ValueError("Destination must be specified")

        trans_attr = dict()
        trans_attr[ACTION] = self.action
        trans_attr[CONTENTS] = self.contents
        # Get the args if they exist.
        if self.svr4_args:
            trans_attr[SVR4_ARGS] = self.svr4_args
        else:
            # if no argument was specified, determine if the action
            # is pkg install or pkg uninstall and apply to appropriate
            # default args.

            # Check for pkg install
            if trans_attr.get(ACTION) == "install":
                # Check to see if the packages are datastream packages
                # All packages must be of the same type.
                pkg_datastream_check = len(self.contents)
                for pkg in self.contents:
                    cmd = [self.FILE] + [self.src + "/" + pkg]
                    pkg_proc = subprocess.Popen(cmd, shell=False,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
                    self.svr4_process = pkg_proc
                    while 1:
                        self.check_cancel_event()
                        pkgoutput = pkg_proc.stdout.readline()
                        if not pkgoutput:
                            if pkg_proc.poll() != 0:
                                self.svr4_process = None
                                raise Exception("SVR4 error reading packages")
                            break
                        if "package datastream" in pkgoutput:
                            self.datastream = True
                            pkg_datastream_check -= 1
                    self.svr4_process = None

                # If the datastream flag is set and pkg_datastream_check
                # has been decremented to 0, then construct args to use
                # datastream packages
                if self.datastream and pkg_datastream_check == 0:
                    datastrm_src = ' '.join(["%s/%s" % (self.src, v) for v
                                            in self.contents])
                    trans_attr[SVR4_ARGS] = self.DEFAULT_PKGADD_ARGS %  \
                                              (datastrm_src, self.dst)
                elif self.datastream and pkg_datastream_check != 0:
                    raise ValueError("Packages are  an invalid mix of"
                                     "datastream and directory "
                                     "packages")
                else:
                    # Use the default pkgadd args for directory-based pkgs
                    trans_attr[SVR4_ARGS] = self.DEFAULT_PKGADD_ARGS % \
                                              (self.src, self.dst)
            else:
                # Use the default pkgrm args since pkg_install_list
                # was empty.
                trans_attr[SVR4_ARGS] = self.DEFAULT_PKGRM_ARGS % (self.dst)

        self._transfer_list.append(trans_attr)
