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

""" boot_archive_archive - archive the boot archive directory
"""
import copy
import math
import os
import platform
import stat

from solaris_install import DC_LABEL, run, run_silent
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from osol_install.install_utils import dir_size
from solaris_install.target.logical import Lofi
from solaris_install.transfer.cpio import TransferCPIOAttr
from solaris_install.transfer.info import INSTALL

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()


class BootArchiveArchive(Checkpoint):
    """ class to archive the boot archive directory
    """

    DEFAULT_ARG = {"compression_type": "gzip", "compression_level": 9,
                   "size_pad": 0, "bytes_per_inode": 0}
    DEFAULT_ARGLIST = {"uncompressed_files": []}

    MIN_PADDING_SIZE_IN_MB = 35

    def __init__(self, name, arg=DEFAULT_ARG, arglist=DEFAULT_ARGLIST):
        super(BootArchiveArchive, self).__init__(name)

        self.comp_type = arg.get("compression_type",
                                 self.DEFAULT_ARG.get("compression_type"))
        self.comp_level = int(arg.get("compression_level",
                              self.DEFAULT_ARG.get("compression_level")))
        self.size_pad = int(arg.get("size_pad",
                            self.DEFAULT_ARG.get("size_pad")))
        self.nbpi = int(arg.get("bytes_per_inode",
                        self.DEFAULT_ARG.get("bytes_per_inode")))

        self.uncompressed_files = arglist.get("uncompressed_files",
                                              self.DEFAULT_ARGLIST.get(
                                                  "uncompressed_files"))

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.pkg_img_path = None
        self.ba_build = None
        self.tmp_dir = None

        self.lofi = None

        if platform.processor() == "i386":
            self.kernel_arch = "x86"
        else:
            self.kernel_arch = "sparc"

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 20

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache
        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)[0].data_dict

        try:
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.ba_build = self.dc_dict["ba_build"]
            self.tmp_dir = self.dc_dict["tmp_dir"]
        except KeyError:
            raise RuntimeError("Error retrieving a value from the DOC")

    def calculate_nbpi(self, directory, size):
        """ class method to calculate exactly what the nbpi should be

        directory - root of the boot archive
        size - the size of the boot archive
        """
        file_count = 0

        # get the cwd to return to later
        cwd = os.getcwd()

        # change to the boot_archive directory
        os.chdir(directory)
        for _none, dirs, files in os.walk("."):
            file_count += len(files) + len(dirs)

        # Add inode overhead for multiple disk systems using 500 disks as a
        # target upper bound.
        #
        # For sparc we need 16 indoes per target device:
        # 8 slices * 2 (block and character device)
        #
        # For x86 we need 42 inodes
        # (5 partitions + 16 slices) * 2
        # To account for dual ported drives double the figure.

        if self.kernel_arch == "x86":
            ioverhead = 42 * 500 * 2
        else:
            ioverhead = 16 * 500 * 2

        nbpi = int(round(size * 1024 / (file_count + ioverhead)))
        # round the nbpi to the largest power of 2 which is less than or equal
        # to the calculated value
        if nbpi != 0:
            nbpi = int(pow(2, math.floor(math.log(nbpi, 2))))
            self.logger.debug("Calculated number of bytes per inode: %d" % \
                              nbpi)

        # return back to the cwd
        os.chdir(cwd)

        return nbpi

    def calculate_ba_size(self, directory):
        """ class method to calculate the size of the boot archive area

        directory - root of the boot archive
        """
        size = dir_size(directory) / 1024

        self.logger.debug("BA size before padding: %d", size)

        # For writable space, add in the minimum padding size plus whatever
        # was specified explicitly as additional padding size in the manifest.
        # Note: the space needed for the inodes eats away some of this space.
        size = size + (self.MIN_PADDING_SIZE_IN_MB * 1024) + \
               (self.size_pad * 1024)

        self.logger.debug("BA size after padding: %d", size)

        if self.nbpi == 0:
            self.nbpi = self.calculate_nbpi(directory, size)

        self.logger.info("ramdisk will be " + \
                         "%d MB in size " % (size / 1024) + \
                         "with an nbpi of %d" % self.nbpi)
        return size

    def create_ramdisks(self):
        """ class method to create the ramdisks and lofi mount them
        """
        # if the tmp_dir doesn't exist create it
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        # create Lofi objects and store them in a list to iterate over
        size = self.calculate_ba_size(self.ba_build)
        if self.kernel_arch == "x86":
            ramdisk = os.path.join(self.pkg_img_path,
                                   "platform/i86pc/amd64/boot_archive")
            mountpoint = os.path.join(self.tmp_dir, "x86_lofimnt")
        elif self.kernel_arch == "sparc":
            ramdisk = os.path.join(self.pkg_img_path,
                                   "platform/sun4u/boot_archive")
            mountpoint = os.path.join(self.tmp_dir, "sparc_lofimnt")

            # add specific entries to /etc/system for sparc
            etc_system = os.path.join(self.ba_build, "etc/system")
            with open(etc_system, "a+") as fh:
                fh.write("set root_is_ramdisk=1\n")
                fh.write("set ramdisk_size=%d\n" % size)
                fh.write("set kernel_cage_enable=0\n")

        self.lofi = Lofi(ramdisk, mountpoint, size)
        self.lofi.nbpi = self.nbpi

    def install_bootblock(self, lofi_device):
        """ class method to install the boot blocks for a sparc distribution
        """
        cmd = [cli.INSTALLBOOT,
               os.path.join(self.pkg_img_path,
                            "usr/platform/sun4u/lib/fs/ufs/bootblk"),
               lofi_device]
        run(cmd)

    def sparc_fiocompress(self, mountpoint):
        """ class method to fiocompress majority of the files
            in the boot archive.
            Note: this method only applies to SPARC
        """
        # construct a list of exclusion files and directories
        exclude_dirs = ["usr/kernel"]
        exclude_files = copy.deepcopy(self.uncompressed_files)
        flist = os.path.join(self.ba_build, "boot/solaris/filelist.ramdisk")
        with open(flist, "r") as fh:
            lines = [line.strip() for line in fh.readlines()]
        for line in lines:
            if os.path.isdir(os.path.join(self.ba_build, line)):
                exclude_dirs.append(line)
            elif os.path.isfile(os.path.join(self.ba_build, line)):
                exclude_files.append(line)

        # get the cwd
        cwd = os.getcwd()

        os.chdir(self.ba_build)
        for root, dirs, files in os.walk("."):
            # strip off the leading . or ./
            root = root.lstrip("./")

            # check to see if root is in the exclude_dirs list
            if root in exclude_dirs:
                self.logger.debug("skipping " + root + " due to exclude list")
                continue

            # walk each dir and if the entry is in the exclude_dir list, skip
            # it
            for d in dirs:
                if os.path.join(root, d) in exclude_dirs:
                    self.logger.debug("skipping " + os.path.join(root, d) + \
                                      " due to exclude list")
                    dirs.remove(d)

            # walk each file and if it's in the skip_list, continue
            for f in files:
                if os.path.join(root, f) in exclude_files:
                    self.logger.debug("skipping " + os.path.join(root, f) + \
                                     " due to exclude list")
                    continue

                # we have a file that needs to be fiocompressed
                ba_path = os.path.join(self.ba_build, root, f)
                mp_path = os.path.join(mountpoint, root, f)

                # ensure that the file meets the following criteria:
                # - it is a regular file
                # - size > 0
                # is is NOT a hardlink
                statinfo = os.lstat(ba_path)
                if stat.S_ISREG(statinfo.st_mode) and not \
                   statinfo.st_size == 0 and \
                   statinfo.st_nlink < 2:
                    # fiocompress the file
                    cmd = [cli.FIOCOMPRESS, "-mc", ba_path, mp_path]
                    run(cmd)

        # return to the original directory
        os.chdir(cwd)

    def create_archives(self):
        """ class method to walk the list of lofi entries and create the
        archives
        """
        self.logger.info("Populating ramdisks")

        # create the ramdisk and lofi mount it
        self.lofi.create(dry_run=False)

        # create a new TransferCPIOAttr object to copy every file from
        # boot_archive to the lofi mountpoint.
        tr_attr = TransferCPIOAttr("Archive Population")

        # set the transfer src correctly
        tr_attr.src = self.ba_build
        tr_attr.dst = self.lofi.mountpoint
        tr_attr.action = INSTALL
        tr_attr.contents = ["./"]
        tr_attr.execute()

        # remove lost+found so it's not carried along to ZFS by an
        # installer
        if os.path.exists(os.path.join(self.lofi.mountpoint,
                                       "lost+found")):
            os.rmdir(os.path.join(self.lofi.mountpoint, "lost+found"))

        if self.kernel_arch == "sparc":
            # install the boot blocks.
            self.install_bootblock(self.lofi.lofi_device.replace("lofi",
                                   "rlofi"))

            # we can't use the transfer module for all of the files due to
            # needing to use fiocompress which copies the file for us.
            self.sparc_fiocompress(self.lofi.mountpoint)

        # umount the lofi device and release the boot_archive
        self.lofi.destroy(dry_run=False)

        if self.kernel_arch == "x86":
            # use gzip to compress the boot archives on x86
            cmd = [cli.CMD7ZA, "a", "-tgzip",
                   "-mx=%d" % self.comp_level,
                   self.lofi.ramdisk + ".gz", self.lofi.ramdisk]
            run_silent(cmd)

            # move the file into the proper place in the pkg image area
            os.rename(self.lofi.ramdisk + ".gz", self.lofi.ramdisk)
        else:
            # the boot_archive for sun4u/sun4v is combined into a single
            # file: sun4u/boot_archive.
            # create a symlink from sun4v/boot_archive to
            # sun4u/boot_archive
            cwd = os.getcwd()
            os.chdir(os.path.join(self.pkg_img_path, "platform/sun4v"))
            os.symlink("../../platform/sun4u/boot_archive", "boot_archive")
            os.chdir(cwd)

        # chmod the boot_archive file to 0644
        os.chmod(self.lofi.ramdisk, 0644)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Boot Archive Archive Checkpoint ===")

        self.parse_doc()

        # create the ramdisk entries based on platform
        self.create_ramdisks()

        # create, populate, and archive the boot archives
        self.create_archives()
