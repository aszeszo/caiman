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

""" pkg_img_mod

 Customizations to the package image area after the boot archive
 has been created

"""
import os
import platform
import shutil
import subprocess

from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const import DC_LABEL
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()

_NULL = open("/dev/null", "r+")


class PkgImgMod(Checkpoint):
    """ PkgImgMod - class to modify the pkg_image directory after the boot
    archive is built.
    """

    DEFAULT_ARG = {"compression_type": "gzip"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(PkgImgMod, self).__init__(name)
        self.compression_type = arg.get("compression_type",
                                        self.DEFAULT_ARG.get(
                                            "compression_type"))
        self.dist_iso_sort = arg.get("dist_iso_sort")

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.pkg_img_path = None
        self.ba_build = None
        self.tmp_dir = None

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take"""
        return 415

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache
        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict)[0].data_dict

        try:
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.tmp_dir = self.dc_dict["tmp_dir"]
            self.ba_build = self.dc_dict["ba_build"]
        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " +
                                str(msg))

    def strip_root(self):
        """ class method to clean up the root of the package image path
        """
        if not os.path.isdir(self.pkg_img_path):
            raise RuntimeError("Package Image path " + self.pkg_img_path +
                            " is not valid")

        # Copy the volsetid to the root of the image
        shutil.copy(os.path.join(self.ba_build, ".volsetid"),
                    self.pkg_img_path)

        # Remove the password lock file left around from user actions
        # during package installation; if left in place it becomes a
        # symlink into /mnt/misc which causes installer's attempt to
        # create a user account to fail
        if os.path.exists(os.path.join(self.pkg_img_path,
                                       "etc/.pwd.lock")):
            os.remove(self.pkg_img_path + "/etc/.pwd.lock")

        os.chdir(self.pkg_img_path)

        # sbin, kernel and lib are contained within the boot_archive
        # Thus, not needed in the pkg_image area
        self.logger.info("Removing sbin, kernel and lib from " +
                         "pkg_image area")
        shutil.rmtree("sbin", ignore_errors=True)
        shutil.rmtree("kernel", ignore_errors=True)
        shutil.rmtree("lib", ignore_errors=True)

    def strip_x86_platform(self):
        """ class method to clean up the package image path for x86 systems
        """
        # save the current working directory
        cwd = os.getcwd()

        os.chdir(os.path.join(self.pkg_img_path, "platform"))
        # walk the directory tree and remove anything other than the kernel
        # and boot_archive files
        for (root, _none, files) in os.walk("."):
            for f in files:
                if f == "unix" or f == "boot_archive":
                    continue
                else:
                    self.logger.debug("removing " + os.path.join(root, f))
                    os.unlink(os.path.join(root, f))

        # copy the platform directory to /boot since grub does not understand
        # symlinks
        os.chdir(self.pkg_img_path)
        shutil.copytree(os.path.join(self.pkg_img_path, "platform"),
                        os.path.join(self.pkg_img_path, "boot/platform"),
                        symlinks=True)

        os.chdir(cwd)

    def strip_sparc_platform(self):
        """ class method to clean up the package image path for sparc systems
        """
        os.chdir(os.path.join(self.pkg_img_path, "platform"))
        # walk the directory tree and remove anything other than wanboot
        # and boot_archive files
        for (root, _none, files) in os.walk("."):
            for f in files:
                if f == "wanboot" or f == "boot_archive":
                    continue
                else:
                    self.logger.debug("removing " + os.path.join(root, f))
                    os.unlink(os.path.join(root, f))

        # symlink the platform directory in boot:
        # boot/platform -> ../platform
        os.chdir(self.pkg_img_path)
        os.symlink(os.path.join("..", "platform"),
                   os.path.join(self.pkg_img_path, "boot/platform"))

    def create_usr_archive(self):
        """ class method to create the /usr file system archive
        """
        os.chdir(self.pkg_img_path)

        # Generate the /usr file system archive.
        self.logger.info("Generating /usr file system archive")

        cmd = [cli.MKISOFS, "-o", "solaris.zlib", "-quiet", "-N",
               "-l", "-R", "-U", "-allow-multidot", "-no-iso-translate",
               "-cache-inodes", "-d", "-D", "-V", "\"compress\"", "usr"]

        # Use the iso_sort file if one is specified
        if self.dist_iso_sort is not None and \
           os.path.exists(self.dist_iso_sort):
            # insert the flags directly after the name of the output file
            cmd.insert(3, "-sort")
            cmd.insert(4, self.dist_iso_sort)

        self.logger.debug("executing:  %s" % " ".join(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=_NULL)

        # log the output
        outs, _none = p.communicate()
        for line in outs.splitlines():
            self.logger.debug(line)

        self.logger.info("Compressing /usr file system archive using: " +
                            self.compression_type)

        cmd = [cli.LOFIADM, "-C", self.compression_type,
               os.path.join(self.pkg_img_path, "solaris.zlib")]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        _none, stderr = p.communicate()
        if p.returncode != 0:
            raise RuntimeError("Compression of /usr file system failed:" +
                                os.strerror(p.returncode))

    def create_misc_archive(self):
        """ class method to create the /mnt/misc file system archive
        """
        os.chdir(self.pkg_img_path)

        self.logger.info("Generating /mnt/misc file system archive")

        os.mkdir("miscdirs")
        shutil.move("opt", "miscdirs")
        shutil.move("etc", "miscdirs")
        shutil.move("var", "miscdirs")

        cmd = [cli.MKISOFS, "-o", "solarismisc.zlib", "-N", "-l", "-R",
               "-U", "-allow-multidot", "-no-iso-translate", "-quiet",
               "-cache-inodes", "-d", "-D", "-V", "\"compress\"",
               "miscdirs"]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=_NULL)

        # log the output
        outs, _none = p.communicate()
        for line in outs.splitlines():
            self.logger.debug(line)

        self.logger.info("Compressing /mnt/misc file system archive " +
                            "using: " + self.compression_type)

        cmd = [cli.LOFIADM, "-C", self.compression_type,
               os.path.join(self.pkg_img_path, "solarismisc.zlib")]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        _none, stderr = p.communicate()
        if p.returncode != 0:
            if "invalid algorithm name" in stderr:
                raise RuntimeError("Invalid compression algorithm " +
                    "specified for /mnt/misc archive: " +
                    self.compression_type)
            else:
                raise RuntimeError("Compression of /mnt/misc file system " +
                                   "failed")

        # the removal of /usr must be deferred to until
        # solarismisc.zlib has been created because the
        # contents of solarismisc.zlib actually come from /usr
        shutil.rmtree(os.path.join(self.pkg_img_path, "miscdirs"),
                      ignore_errors=True)
        shutil.rmtree(os.path.join(self.pkg_img_path, "usr"),
                      ignore_errors=True)

    def create_livecd_content_file(self):
        """ class method to create the .livecd-cdrom-content file
        """
        # save the current working directory
        cwd = os.getcwd()

        # change to the pkg_img_path
        os.chdir(self.pkg_img_path)

        content_list = []
        for root, dirs, files in os.walk("."):
            for f in files:
                if not f.endswith(".zlib") and not f.endswith(".image_info") \
                    and not f.endswith("boot_archive") and not \
                    f.endswith(".livecd-cdrom-content"):
                    content_list.append(os.path.join(root, f))
            for d in dirs:
                content_list.append(os.path.join(root, d))

        with open(".livecd-cdrom-content", "w") as fh:
            for entry in content_list:
                fh.write(entry + "\n")

        os.chdir(cwd)
    
    def create_save_list(self):
        '''Store a list of files under the 'save' directory. Net-booted
        text installer uses this list to determine what files it needs from
        the boot server
        
        '''
        save_files = []
        save_dir = os.path.join(self.pkg_img_path, "save")
        for root, d, files in os.walk(save_dir):
            for f in files:
                relpath = os.path.relpath(os.path.join(root, f),
                                          start=self.pkg_img_path)
                save_files.append(relpath)
        
        save_list = os.path.join(self.pkg_img_path, "save_list")
        with open(save_list, "w") as save_fh:
            for entry in save_files:
                save_fh.write(entry + "\n")

    def execute(self, dry_run=False):
        """Customize the pkg_image area. Assumes that a populated pkg_image
           area exists and that the boot_archive has been built
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Pkg Image Modification Checkpoint ===")

        self.parse_doc()

        # clean up the root of the package image path
        self.strip_root()

        # create the /usr archive
        self.create_usr_archive()

        # create the /mnt/misc archive
        self.create_misc_archive()
        
        self.create_save_list()


class LiveCDPkgImgMod(PkgImgMod, Checkpoint):
    """ LiveCDPkgImgMod - class to modify the pkg_image directory after the boot
    archive is built for Live CD distributions
    """

    DEFAULT_ARG = {"compression_type": "gzip"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(LiveCDPkgImgMod, self).__init__(name, arg)

    def cleanup_icons(self):
        """ class method to remove all icon-theme.cache files
        """
        self.logger.debug("Cleaning out icon theme cache")

        os.chdir(os.path.join(self.pkg_img_path, "usr"))
        for root, _none, files in os.walk("."):
            if "icon-theme.cache" in files:
                os.unlink(os.path.join(root, "icon-theme.cache"))

    def strip_platform(self):
        """ class method to remove every file from platform/ except for the
        kernel and boot_archive.
        """
        self.logger.debug("platform only needs to contain the kernel " +
                          "and boot_archive")

        os.chdir(os.path.join(self.pkg_img_path, "platform"))
        for root, _none, files in os.walk("."):
            for f in files:
                if f == "unix" or f == "boot_archive":
                    continue
                os.unlink(os.path.join(root, f))

    def execute(self, dry_run=False):
        """Customize the pkg_image area. Assumes that a populated pkg_image
           area exists and that the boot_archive has been built
        """
        self.logger.info("=== Executing Pkg Image Modification Checkpoint ===")

        self.parse_doc()

        # remove icon caches
        self.cleanup_icons()

        # clean up the root of the package image path
        self.strip_root()

        # create the /usr archive
        self.create_usr_archive()

        # create the /mnt/misc archive
        self.create_misc_archive()

        # strip the /platform directory
        self.strip_platform()

        # create the .livecd-cdrom-content file
        self.create_livecd_content_file()


class TextPkgImgMod(PkgImgMod, Checkpoint):
    """ TextPkgImgMod - class to modify the pkg_image directory after the boot
    archive is built for Text media
    """

    DEFAULT_ARG = {"compression_type": "gzip"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(TextPkgImgMod, self).__init__(name, arg)

    def execute(self, dry_run=False):
        """ Customize the pkg_image area. Assumes that a populated pkg_image
        area exists and that the boot_archive has been built
        """
        self.logger.info("=== Executing Pkg Image Modification Checkpoint ===")

        self.parse_doc()

        # clean up the root of the package image path
        self.strip_root()

        # create the /usr archive
        self.create_usr_archive()

        # create the /mnt/misc archive
        self.create_misc_archive()

        # get the platform of the system
        arch = platform.processor()

        # save the current working directory
        cwd = os.getcwd()
        try:
            # clean up the package image path based on the platform
            if arch == "i386":
                self.strip_x86_platform()
            else:
                self.strip_sparc_platform()
    
            # create the .livecd-cdrom-content file
            self.create_livecd_content_file()
        finally:
            # return to the initial directory
            os.chdir(cwd)
        
        self.create_save_list()

# Currently, no difference between AIPkgImgMod and TextPkgImgMod.
# Defined as an empty subclass here so that manifests can
# reference AIPkgImgMod now, and if the classes diverge,
# old manifests won't need updating
class AIPkgImgMod(TextPkgImgMod):
    """ AIPkgImgMod - class to modify the pkg_image directory after the boot
    archive is built for AI distributions
    """
    pass
