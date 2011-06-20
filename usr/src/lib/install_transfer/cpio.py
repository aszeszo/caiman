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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
Transfer CPIO checkpoint. Sub-class of the checkpoint class.
"""

import abc
import operator
import os
import shutil
import subprocess
import tempfile

from osol_install.install_utils import file_size
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.engine import InstallEngine
from solaris_install.target.size import Size
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import CPIOSpec as CPIO
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import ACTION, CONTENTS, CPIO_ARGS
from solaris_install.transfer.prog import ProgressMon
from solaris_install.transfer.media_transfer import TRANSFER_ROOT, \
    TRANSFER_MISC, TRANSFER_MEDIA, get_image_size


class AbstractCPIO(Checkpoint):
    '''Subclass for transfer CPIO checkpoint'''
    __metaclass__ = abc.ABCMeta

    # Constant values
    CPIO = "/usr/bin/cpio"
    DEF_CPIO_ARGS = "-pdum"
    DEFAULT_PROG_EST = 10
    DEFAULT_SIZE = 1000   # Default size of a transfer in kbytes

    def __init__(self, name):
        super(AbstractCPIO, self).__init__(name)

        # A list of transfer operations
        self._transfer_list = []

        # Handle to the DOC
        self._doc = None

        # Required attributes for source and destination
        self.dst = None
        self.src = None

        # Parameters used for progress reporting
        self.distro_size = 0          # value stored in kilobytes
        self.give_progress = False

        # Set a default value for dry_run
        # Determines whether install is executed
        self.dry_run = False

        # Flag to cancel execution of any action
        self._cancel_event = False

        # Process handle for the actual cpio
        self.cpio_process = None

        # Progress monitor handle
        self.pmon = None

        # Default value used by get_size to determine
        # if image_info is used
        self._use_image_info = False

        self._image_size = 0

    def get_media_transfer_size(self):
        ''' Hack to skip computing size of media transfer checkpoints
            to we can speed up the start of the install
        '''

        self.logger.debug("Special size calculation for: " + self.name)
        if self._image_size == 0:
            image_info_size = get_image_size(self.logger)
            size_in_mb = Size(str(image_info_size) + Size.mb_units)
            self._image_size = size_in_mb.get(Size.kb_units)
            self.logger.debug("image_info size: %d kb", self._image_size)

        if self.name == TRANSFER_ROOT:
            weight = 0.75
        elif self.name == TRANSFER_MISC:
            weight = 0.05
        elif self.name == TRANSFER_MEDIA:
            weight = 0.20
        else:
            raise RuntimeError("Not applicable for other checkpoints")

        return int(self._image_size * weight)

    def get_size(self):
        '''Compute the size of the transfer specified'''

        # Check to see if parse input failed because
        # the source doesn't exist. If we don't have
        # a src yet, then we can't compute the size
        # so just return the standard default. If src
        # is none, the failure occurs in _parse_input.
        #
        # Size returned is in kilobytes
        #
        try:
            self._parse_input()
        except ValueError, msg:
            if self.src and not os.path.exists(self.src):
                return self.DEFAULT_SIZE
            raise

        self._validate_input()
        size = 0

        # There may be a .image_info file at the src. If it's there,
        # use this to determine the size of the transfer. If it's
        # not there then compute the size.
        image_info = os.path.join(self.src, ".image_info")
        if self._use_image_info and os.path.exists(image_info):
            with open(image_info, 'r') as filehandle:
                for line in filehandle.readlines():
                    (opt, sep, val) = line.rstrip().partition("=")
                    if opt == "IMAGE_SIZE":
                        # Remove the '\n' character read from
                        # the file, and convert to integer
                        return(int(val.rstrip()))

        # Compute the image size from the data in the transfer install
        # list, if it contains valid data
        for transfer in self._transfer_list:
            if transfer.get(ACTION) == "install":
                file_list = transfer.get(CONTENTS)
                self.logger.debug("Unable to read .image_info file")
                self.logger.debug("Computing distribution size.")

                with open(file_list, 'r') as filehandle:
                    # Determine the file size for each file listed and sum
                    # the sizes.
                    try:
                        size = size + sum(map(file_size,
                                         [os.path.join(self.src,
                                                       f.rstrip())
                                         for f in filehandle.readlines()]))
                    except OSError:
                        # If the file doesn't exist that's OK.
                        pass

        # The file_size() function used for calculating size of each
        # file returns the value in bytes.  Convert to kilobytes.
        size = size / 1024
        return size

    def get_progress_estimate(self):
        '''Returns an estimate of the time this checkpoint will take
           given the DOC input
        '''

        if self.distro_size == 0:
            if self.name == TRANSFER_ROOT or \
                self.name == TRANSFER_MISC or \
                self.name == TRANSFER_MEDIA:
                self.distro_size = self.get_media_transfer_size()
            else:
                self.distro_size = self.get_size()

        self.logger.debug("Distro size: %d KB", self.distro_size)
        progress_estimate = \
            int((float(self.distro_size) / self.DEFAULT_SIZE) * \
                self.DEFAULT_PROG_EST)

        self.give_progress = True
        return progress_estimate

    def cancel(self):
        '''Cancel the transfer in progress'''
        self._cancel_event = True
        if self.cpio_process:
            self.cpio_process.kill()

    def execute(self, dry_run=False):
        '''Execute method for the CPIO checkpoint module. Will read the
           input parameters and perform the specified transfer.
        '''
        self.logger.info("=== Executing %s Checkpoint ===" % self.name)
        if self.give_progress:
            self.logger.report_progress("Beginning CPIO transfer", 0)

        self.dry_run = dry_run

        try:
            # Read the parameters put into the local attributes
            self._parse_input()
            self._validate_input()

            # Check to see if a cancel_event has been requested.
            self.check_cancel_event()

            # Finally, actually perform the CPIO transfer.
            self._transfer()
        finally:
            self._cleanup()

    def check_cancel_event(self):
        '''Check the  _cancel_event attribute to see if a cancel_event has been
           requested. If it has, cleanup what has been done already
        '''
        if self._cancel_event:
            self._cleanup()

    @abc.abstractmethod
    def _parse_input(self):
        '''This method is required to be implemented by all subclasses'''
        raise NotImplementedError

    def _cleanup_tmp_files(self):
        '''Remove the tmp files we created from the system'''
        try:
            for transfer in self._transfer_list:
                if transfer.get(ACTION) == "install" \
                   and os.path.exists(transfer.get(CONTENTS)):
                    os.unlink(transfer.get(CONTENTS))
        except OSError:
            pass

    def _cleanup(self):
        '''Method to perform any necessary cleanup needed'''
        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None

        self._cleanup_tmp_files()

    def _validate_input(self):
        '''Method to validate the local attributes'''
        self.logger.debug("Validating CPIO input")

        if self.dst is None:
            self._cleanup_tmp_files()
            raise ValueError("CPIO destination must be specified")

    def validate_contents(self, contents):
        '''Check that the contents passed in are a valid list
           of files or a file containing a list of files. If it is
           a file make sure it is readable.
        '''
        self.logger.debug("Validating CPIO contents")
        if contents:
            if isinstance(contents, list):
                return contents
            else:
                # If the default file list is specified and it's
                # not there, this isn't an error, just set file_list
                # to None.
                cpio_install_types = [CPIO.DEF_INSTALL_LIST,
                                      CPIO.DEF_UNINSTALL_LIST,
                                      CPIO.DEF_MEDIA_TRANSFORM]
                if contents in cpio_install_types and \
                        not os.access(os.path.join(self.src, contents),\
                                     os.R_OK):
                    self.logger.debug("CPIO Transfer: no default file "
                                      "list found")
                    return None
                else:
                    # Check if the file path is relative or absolute.
                    if not os.path.isabs(contents):
                        contents = os.path.join(self.src, contents)
                    # Verify that the file is readable.
                    if not os.access(contents, os.R_OK):
                        raise ValueError("CPIO Transfer file list specified "
                                         "either doesn't exist or is not "
                                         "readable, %s" % contents)
                    return contents
        else:
            self.logger.debug("CPIO Transfer: No contents list found")
            return None

    def sort_by_inode(self, infile, outfile):
        '''Sort the entries in the file by inode. Place
           the sorted results in the file
        '''
        # Sort the entries by inode
        tmp_flist = []
        with open(infile, 'r') as filehandle:
            for fname in filehandle.readlines():
                fname = fname.rstrip()
                try:
                    st1 = os.lstat(os.path.join(self.src, fname))
                    tmp_flist.append((st1.st_ino, fname))
                except OSError, msg:
                    self.logger.debug("CPIO transfer error processing %s",
                                      fname)
                    self.logger.debug(msg)

        tmp_flist.sort(key=operator.itemgetter(0))
        with open(outfile, 'a') as filehandle:
            for entry in map(operator.itemgetter(1), tmp_flist):
                filehandle.write(entry + "\n")

    def build_file_list(self, src, flist):
        '''Method to build a list of files to be transferred from the specified
           source. All files in the directory tree rooted at src are included.
           Input: src: src of the tree to walk
           output_file : file to place the sorted file list into.
        '''
        self.logger.debug("CPIO Transfer: building the file list")

        # Walk the source to get the list of files to be transferred.
        st2 = os.stat(src)

        if "./" not in flist:
            flist.append("./")

        self.logger.debug("building file list %s", src)

        st1 = os.lstat(src)

        # Compute the relative source and append to the file list
        flist.append(src.partition(self.src)[2].lstrip("/"))

        # Walk the source in order to put all dirs and files in the list to be
        # transfered.
        for root, dirs, files in os.walk(src):
            self.check_cancel_event()

            rmlist = []
            # Process the dirs
            for dir_name in dirs:
                # Full path name of the directory
                dir_full_path = os.path.join(root, dir_name)

                # Directory relative to the src passed in.
                dir_rel_to_src = os.path.join(
                    root.partition(self.src)[2].lstrip("/"), dir_name)
                # Write the inode for the dir and the path relative to the src
                # to the list to be cpio'd.
                st1 = os.lstat(dir_full_path)

                # Store the inode number and the directory relative to the
                # source to the list to be cpio'd. Store as a tuple.
                flist.append(dir_rel_to_src)

                # Identify the directories that we do not want to traverse.
                # These are those that can't be read for some reason or those
                # holding other mounted filesystems. Place these dirs in
                # rmlist.
                try:
                    st1 = os.stat(dir_full_path)
                except OSError:
                    rmlist.append(dir_name)
                    continue

                # Emulate nftw(..., FTW_MOUNT) for directories
                if st1.st_dev != st2.st_dev:
                    rmlist.append(dir_name)

            # Remove the dirs specified above.
            for dir_remove in rmlist:
                dirs.remove(dir_remove)

            # Process the files.
            for name in files:
                self.check_cancel_event()
                # Full path name for file.
                file_full_path = os.path.join(root, name)

                # File name relative to the source.
                file_rel_to_src = os.path.join(
                    root.partition(self.src)[2].lstrip("/"), name)
                st1 = os.lstat(file_full_path)

                # Store the inode number and the filename relative to the
                # source to the list to be cpio'd. Store as a tuple.
                flist.append(file_rel_to_src)

    def transfer_filelist(self, file_list, cpio_args):
        '''Method to transfer the files listed in file_list to the
           indicated destination. The transfer uses the cpio utility
           with the arguments specified in cpio_args.
        '''

        self.logger.debug("Transferring files in %s", file_list)

        os.chdir(self.src)
        if cpio_args != "-pdum":
            cpio_args = cpio_args.split(' ')
            cmd = [self.CPIO] + cpio_args + [self.dst]
        else:
            cmd = [self.CPIO, cpio_args, self.dst]

        self.logger.debug("The command executing is %s", cmd)
        if not self.dry_run:
            err_file = os.tmpfile()
            #strip the args sep on space
            # do plus like in svr4
            cpio_proc = subprocess.Popen(cmd, shell=False,
                                         stdin=open(file_list, 'r'),
                                         stderr=err_file, close_fds=True)
            self.cpio_process = cpio_proc
            cpio_proc.wait()
            self.cpio_process = None

    def run_exec_file(self, file_name):
        '''Run the executable file specified'''
        self.logger.debug("Running %s", file_name)
        subprocess.check_call([file_name, self.src, self.dst])

    def parse_transfer_node(self, trans):
        '''Parse the information in the transfer node to determine
           the action to perform and the source of the data
        '''
        if trans.action == "install":
            fl_data = self.validate_contents(trans.contents)
            if isinstance(fl_data, list):
                # Go through the list and find directory entries
                bflist = list(fl_data)
                for item in fl_data:
                    if os.path.isdir(os.path.join(self.src, item.rstrip())):
                        # Remove the dir entries and create a file
                        # list that contains files within those dirs.

                        bflist.pop(bflist.index(item))
                        self.build_file_list(os.path.join(self.src,
                            item.rstrip()), bflist)
                tmp_file = tempfile.mktemp()
                with open(tmp_file, 'w') as filehandle:
                    for file_name in bflist:
                        filehandle.write(file_name + "\n")
                fl_data = tmp_file
            sorted_file = tempfile.mktemp()
            try:
                self.sort_by_inode(fl_data, sorted_file)
                os.unlink(fl_data)
            except OSError:
                os.unlink(sorted_file)
                sorted_file = fl_data
            self.logger.debug("File List: %s", sorted_file)
            return sorted_file
        elif trans.action == "uninstall":
            uninstall_data = self.validate_contents(trans.contents)
            self.logger.debug("Uninstalling data")
            if isinstance(uninstall_data, str) and \
               os.path.isfile(uninstall_data):
                uninstall_list = []
                with open(uninstall_data, 'r') as fh:
                    uninstall_list = [line.rstrip() for line in fh.readlines()]
                return uninstall_list
            else:
                return uninstall_data
        elif trans.action == "transform":
            self.logger.debug("Using media transform")
            return self.validate_contents(trans.contents)
        else:
            # if no action is specified, then default to using
            # the existing tranfer file.

            cpio_def_list = [CPIO.DEF_INSTALL_LIST,
                             CPIO.DEF_UNINSTALL_LIST,
                             CPIO.DEF_MEDIA_TRANSFORM]

            for def_transfer in cpio_def_list:
                contents = self.validate_contents(def_transfer)
                if contents:
                    return contents
            raise Exception("CPIO Transfer unable to determine desired action")

    def _transfer(self):
        '''Method to transfer from the source to the destination'''
        # Check for the existence of the destination directory for the
        # transfer and create it if it doesn't exist.
        if not os.path.exists(self.dst):
            if not self.dry_run:
                os.makedirs(self.dst)

        if self.give_progress:
            if self.distro_size == self.DEFAULT_SIZE:
                # We weren't able to compute the size due to the
                # lack of the source when get_progress_estimate was
                # called. In order to do accurate progress estimate,
                # get that size now.
                self.distro_size = self.get_size()

            # Start up the ProgressMon to report progress while the actual
            # transfer is taking place.
            self.pmon = ProgressMon(logger=self.logger)
            self.pmon.startmonitor(self.dst, self.distro_size)

        for trans in self._transfer_list:
            # before starting any transforms, installs or uninstalls, first
            # verify this transaction has contents to operate on
            if trans.get(CONTENTS) is None:
                raise RuntimeError("%s action has no contents" % \
                                   trans.get(ACTION))
            if trans.get(ACTION) == "transform":
                if not self.dry_run:
                    self.run_exec_file(trans.get(CONTENTS))
                continue
            if trans.get(ACTION) == "install":
                self.logger.info("Transferring files to %s", self.dst)
                self.transfer_filelist(trans.get(CONTENTS),
                                       trans.get(CPIO_ARGS))

            elif trans.get(ACTION) == "uninstall":
                self.logger.debug("Removing specified files "
                                  "and directories")
                if not self.dry_run:
                    for item in trans.get(CONTENTS):
                        entry = os.path.join(self.dst, item.rstrip())
                        try:
                            if os.path.isdir(entry):
                                shutil.rmtree(entry)
                            else:
                                os.unlink(entry)
                        except OSError:
                            # If the item isn't there that's what we
                            # wanted anyway so just continue.
                            pass

        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None


class TransferCPIO(AbstractCPIO):
    '''CPIO transfer class which takes input from the DOC'''
    VALUE_SEPARATOR = ","

    def __init__(self, name):
        super(TransferCPIO, self).__init__(name)

        # Holds a list of transfer actions
        self._transfer_list = []

        # Hold the handle to the DOC
        self._doc = InstallEngine.get_instance().data_object_cache

        # Get the checkpoint info from the DOC
        self.soft_list = self._doc.get_descendants(name=self.name,
                                              class_type=Software)

        # Check that the soft_list only has one entry
        if len(self.soft_list) != 1:
            raise ValueError("Only one value for Software node can be "
                             "specified with name %s", self.name)

    def _parse_input(self):
        '''Method to read the parameters from the data object cache and
           place them into the local lists.
        '''
        self.logger.debug("Parsing the Data Object Cache")

        soft_node = self.soft_list[0]

        # Get the destination info
        dst_list = soft_node.get_children(Destination.DESTINATION_LABEL,
                                          Destination)
        self.dst = self._doc.str_replace_paths_refs(
            dst_list[0].get_children(Dir.DIR_LABEL, Dir)[0].dir_path)

        # Get the source info
        src_list = soft_node.get_children(Source.SOURCE_LABEL, Source)

        self.src = self._doc.str_replace_paths_refs(
            src_list[0].get_children(Dir.DIR_LABEL, Dir)[0].dir_path)

        if not os.path.exists(self.src):
            raise ValueError("The source doesn't exist: %s", self.src)

        if not os.access(self.src, os.R_OK):
            raise ValueError("CPIO Transfer unable to read the specified "
                             "source: %s", self.src)

        # Get the list of transfers from this specific node in the DOC
        transfer_list = soft_node.get_children(class_type=CPIO)

        for trans in transfer_list:
            trans_attr = dict()
            args = trans.get_children(name=Args.ARGS_LABEL, class_type=Args)

            # An argument was specified, validate that the user
            # only specified one and that it was cpio_args. Anything
            # else is illegal.
            if args:
                if len(args) > 1:
                    self._cleanup_tmp_files()
                    raise ValueError("Invalid to specify cpio "
                                     "arguments multiple times.")
                else:
                    try:
                        trans_attr[CPIO_ARGS] = args[0].arg_dict["cpio_args"]
                    except NameError:
                        self._cleanup_tmp_files()
            # if no args are specified use the default list.
            else:
                # Use the default cpio args.
                trans_attr[CPIO_ARGS] = self.DEF_CPIO_ARGS

            trans_attr[CONTENTS] = self.parse_transfer_node(trans)
            trans_attr[ACTION] = trans.action
            self._transfer_list.append(trans_attr)


class TransferCPIOAttr(AbstractCPIO):
    '''CPIO transfer class which gets it input directly from the attributes.
       Provides the checkpoint functionality.
    '''
    def __init__(self, name):
        super(TransferCPIOAttr, self).__init__(name)

        # Attributes that can be populated
        self.cpio_args = self.DEF_CPIO_ARGS
        self.action = None
        self.type = None
        self.contents = None
        self._transfer_list = []

    def _parse_input(self):
        '''Parse the input parameters and put them into local attributes'''
        self.logger.debug("CPIO Transfer: parsing the input")

        if self.src is None:
            raise ValueError("Source must be specified")

        if not os.path.exists(self.src):
            raise ValueError("Source doesn't exist")

        self._transfer_list = []
        trans_attr = dict()
        trans_attr[CPIO_ARGS] = self.cpio_args
        trans_attr[CONTENTS] = self.parse_transfer_node(self)
        trans_attr[ACTION] = self.action
        self._transfer_list.append(trans_attr)
