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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#

""" boot_archive_configure - configure a populated boot archive area into a
usable boot archive.
"""
import os
import shutil
import datetime

from osol_install.install_utils import dir_size
from solaris_install import DC_LABEL, run
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.transfer.info import Software, Source, Destination, \
    CPIOSpec, Dir
from solaris_install.transfer.media_transfer import TRANSFER_ROOT, \
    INSTALL_TARGET_VAR
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()


class BootArchiveConfigure(Checkpoint):
    """ class to configure the boot archive
    """

    DEFAULT_ARG = {"image_type": None}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(BootArchiveConfigure, self).__init__(name)
        self.image_type = arg.get("image_type",
                                  self.DEFAULT_ARG.get("image_type"))

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.pkg_img_path = None
        self.ba_build = None

        # set the file_defaults to the path of this checkpoint/defaultfiles
        self.file_defaults = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "defaultfiles")

    def get_progress_estimate(self):
        """Returns an estimate of the time this checkpoint will take
        """
        return 20

    def configure_system(self):
        """ class method for the execution of various, isolated shell commands
        needed to configure the boot archive.
        """
        self.logger.info("preparing boot archive")

        # configure devices
        cmd = [cli.DEVFSADM, "-r", self.ba_build]
        run(cmd)

        # etc/dev/.devfsadm_dev.lock gets created every time devfsadm is run.
        # remove it since there's no point in carrying it forward through to
        # the image
        lockfile = os.path.join(self.ba_build, "etc/dev/.devfsadm_dev.lock")
        if os.path.exists(lockfile):
            self.logger.debug("Removing devfsadm lock file")
            os.remove(lockfile)

        # Set a marker so that every boot is a reconfiguration boot
        self.logger.debug("Creating /reconfigure")
        with open(os.path.join(self.ba_build, "reconfigure"), "w"):
            pass

        # Set up /etc/rtc_config
        self.logger.debug("Setting up /etc/rtc_config")
        cmd = [cli.CP, os.path.join(self.file_defaults, "rtc_config.default"),
               os.path.join(self.ba_build, "etc/rtc_config")]
        run(cmd)

        # go to the ba_build directory
        os.chdir(self.ba_build)

        # create volume set id file, use system name + date for uniqueness
        with open(".volsetid", "w") as v:
            volsetid = os.uname()[1] + '-' + \
                       datetime.datetime.now().isoformat()
            self.logger.debug("Setting .volsetid to %s" % volsetid)
            v.write(volsetid)

        # chmod it to 444 and set the ownership to root:root (0:0)
        os.chmod(".volsetid", 0444)
        os.chown(".volsetid", 0, 0)

        # create the file marking the image type (e.g. .autoinstall or
        # .livecd)
        self.logger.debug("Creating image_type file")
        with open(self.image_type, "w"):
            pass

        # touch an empty etc/dumpadm.conf file so the dumpadm service will
        # start correctly; it's a required dependency of fmd
        self.logger.debug("Creating empty /etc/dumpadm.conf")
        with open(os.path.join(self.ba_build, "etc/dumpadm.conf"), "w"):
            pass

        # create opt symlink to mnt/misc/opt if needed
        if not os.path.islink("opt"):
            self.logger.debug("Creating symlink of opt -> mnt/misc/opt")
            os.symlink("mnt/misc/opt", "opt")

        tr_uninstall = CPIOSpec()
        tr_uninstall.action = CPIOSpec.UNINSTALL
        tr_uninstall.contents = ["opt"]

        root_tr_software_node = self.doc.persistent.get_descendants(
            name=TRANSFER_ROOT, class_type=Software, not_found_is_err=True)[0]
        root_tr_software_node.insert_children(tr_uninstall)

        # copy the SMF repository from pkg_image_path to ba_build
        pkg_img_path_repo = os.path.join(self.pkg_img_path,
                                         "etc/svc/repository.db")
        ba_build_repo = os.path.join(self.ba_build,
                                     "etc/svc/repository.db")
        shutil.copy2(pkg_img_path_repo, ba_build_repo)

    def configure_symlinks(self):
        """ class method for the configuration of symlinks needed in the boot
        archive.
        """
        self.logger.debug("Creating additional symlinks in ramdisk")

        self.logger.debug("creating set of files in pkg_img_path:  %s" % \
                          self.pkg_img_path)

        # change to the pkg_img_path directory
        os.chdir(self.pkg_img_path)

        # walk /etc and /var in pkg_img_path and create a list of
        # directories
        pkg_img_dirs = []
        for rootdir in ["etc", "var"]:
            for root, dirs, files in os.walk(rootdir):
                for d in dirs:
                    pkg_img_dirs.append(os.path.join(root, d))

        # change to the boot_archive directory
        os.chdir(self.ba_build)

        # walk the pkg_img_dirs list and create each directory that doesn't
        # already exist.  Also, copy the directory permissions and metadata
        # to the new directory
        for d in pkg_img_dirs:
            ba_path = os.path.join(self.ba_build, d)
            pkg_path = os.path.join(self.pkg_img_path, d)

            # split the directory on / to verify parent directories exist
            dir_list = d.split("/")

            # keep a 'path' string for verification
            path = ""
            for subdir in dir_list:
                # extend path
                path = os.path.join(path, subdir)
                full_path = os.path.join(self.ba_build, path)

                # check to see if it exists and is not already a symlink
                if not os.path.exists(full_path) and \
                    not os.path.islink(full_path):

                    # create the directory
                    os.mkdir(os.path.join(self.ba_build, path))

                    # copy the metadata from pkg_image to boot_archive
                    shutil.copystat(os.path.join(self.pkg_img_path, path),
                                    os.path.join(self.ba_build, path))

                    # copy the uid/gid as well
                    pkg_statinfo = os.stat(os.path.join(self.pkg_img_path,
                                                        path))

                    os.chown(os.path.join(self.ba_build, path),
                             pkg_statinfo.st_uid, pkg_statinfo.st_gid)

        # now that the directory structure is created, create symlinks for
        # all the missing files in the boot_archive

        # change to the pkg_img_path directory
        os.chdir(self.pkg_img_path)

        # keep track of all the symlinks created
        misc_symlinks = []
        for rootdir in ["etc", "var"]:
            for root, dirs, files in os.walk(rootdir):
                for f in files:
                    pkg_path = os.path.join(self.pkg_img_path, root, f)

                    # skip symlinks
                    if os.path.islink(pkg_path):
                        continue

                    ba_path = os.path.join(self.ba_build, root, f)
                    if not os.path.exists(ba_path):
                        # the file is missing from the boot_archive so
                        # create a symlink to /mnt/misc/file/path
                        misc_path = os.path.join("/mnt/misc", root, f)

                        # save the cwd
                        cwd = os.getcwd()

                        # changedir to the dirname of the file
                        os.chdir(os.path.dirname(ba_path))

                        # create the symlink
                        os.symlink(misc_path, f)

                        os.chdir(cwd)

                        misc_symlinks.append(os.path.join(root, f))

        tr_uninstall = CPIOSpec()
        tr_uninstall.action = CPIOSpec.UNINSTALL
        tr_uninstall.contents = misc_symlinks

        # Add that into the software transfer list.  The list of files to
        # uninstall MUST go before the contents to be installed from /mnt/misc
        root_tr_software_node = self.doc.persistent.get_descendants(
            name=TRANSFER_ROOT, class_type=Software, not_found_is_err=True)[0]

        root_tr_software_node.insert_children(tr_uninstall)

        self.logger.debug(str(self.doc.persistent))

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
        except KeyError:
            raise RuntimeError("Error retrieving a value from the DOC")

    def add_root_transfer_to_doc(self):
        """ Adds the list of files of directories to be transferred
            to the DOC
        """
        if self.doc is None:
            self.doc = InstallEngine.get_instance().data_object_cache

        src_path = Dir("/")
        src = Source()
        src.insert_children(src_path)

        dst_path = Dir(INSTALL_TARGET_VAR)
        dst = Destination()
        dst.insert_children(dst_path)

        dot_node = CPIOSpec()
        dot_node.action = CPIOSpec.INSTALL
        dot_node.size = str(dir_size(os.path.join(self.ba_build, "")))
        dot_node.contents = ["."]

        usr_node = CPIOSpec()
        usr_node.action = CPIOSpec.INSTALL
        usr_node.size = str(dir_size(os.path.join(self.pkg_img_path, "usr")))
        usr_node.contents = ["usr"]

        dev_node = CPIOSpec()
        dev_node.action = CPIOSpec.INSTALL
        dev_node.size = str(dir_size(os.path.join(self.pkg_img_path, "dev")))
        dev_node.contents = ["dev"]

        software_node = Software(TRANSFER_ROOT, type="CPIO")
        software_node.insert_children([src, dst, dot_node, usr_node, dev_node])

        self.doc.persistent.insert_children(software_node)

        self.logger.debug(str(self.doc.persistent))

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Boot Archive Configuration" + \
            " Checkpoint ===")

        self.parse_doc()

        self.add_root_transfer_to_doc()

        # configure various boot archive files
        self.configure_system()

        # configure various symlinks
        self.configure_symlinks()


class AIBootArchiveConfigure(BootArchiveConfigure, Checkpoint):
    """ AIBootArchiveConfigure - class to configure the boot archive directory
    specific to AI distributions.
    """

    DEFAULT_ARG = {"image_type": ".autoinstall"}

    def __init__(self, name, arg=DEFAULT_ARG):
        """ constructor for class.
        image_type - string containing the image_type (.autoinstall, .livecd)
        """
        super(AIBootArchiveConfigure, self).__init__(name, arg)
        self.image_type = arg.get("image_type",
                                  self.DEFAULT_ARG.get("image_type"))

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Boot Archive Configuration" + \
            " Checkpoint ===")

        self.parse_doc()

        self.add_root_transfer_to_doc()

        # configure various boot archive files
        self.configure_system()

        # configure various symlinks
        self.configure_symlinks()


class LiveCDBootArchiveConfigure(BootArchiveConfigure, Checkpoint):
    """ LiveCDBootArchiveConfigure - class to configure the boot archive
    directory specific to LiveCD distributions.
    """

    DEFAULT_ARG = {"image_type": ".livecd"}

    def __init__(self, name, arg=DEFAULT_ARG):
        """ constructor for class.
        image_type - string containing the image_type (.autoinstall, .livecd)
        """
        super(LiveCDBootArchiveConfigure, self).__init__(name, arg)
        self.image_type = arg.get("image_type",
                                  self.DEFAULT_ARG.get("image_type"))

    def configure_gdm(self):
        """ class method to configure gdm to automatically log the jack user on
        after GNOME starts.
        """
        self.logger.debug("Configuring gdm for LiveCD boot")
        # Enable auto-login in gdm, and save original to replace after
        # installation
        self.logger.debug("updating gdm's custom.conf file")

        # save the original /etc/gdm/custom.conf in the boot_archive to
        # the /save directory
        if not os.path.exists(os.path.join(self.pkg_img_path, "save/etc/gdm")):
            os.makedirs(os.path.join(self.pkg_img_path, "save/etc/gdm"))

        shutil.copy2(os.path.join(self.ba_build, "etc/gdm/custom.conf"),
                     os.path.join(self.pkg_img_path,
                                  "save/etc/gdm/custom.conf"))

        # delete the original custom.conf
        os.remove(os.path.join(self.ba_build, "etc/gdm/custom.conf"))

        # change to etc/gdm
        os.chdir(os.path.join(self.pkg_img_path, "etc/gdm"))

        with open("./custom.conf", "r") as fh:
            custom_conf = fh.readlines()

        # walk the lines and when the [daemon] line comes up, append the
        # entries to auto-login the 'jack' user
        with open("./custom.conf", "w") as fh:
            for line in custom_conf:
                if not line.startswith("[daemon]"):
                    fh.write(line)
                else:
                    # write this line out
                    fh.write(line)

                    # write the rest of the entries
                    fh.write("AutomaticLoginEnable=true\n")
                    fh.write("AutomaticLogin=jack\n")
                    fh.write("GdmXserverTimeout=30\n")

    def configure_sudoers(self):
        """ class method to configure /etc/sudoers
        """
        # Give jack administrator profile and convert root to a role
        self.logger.debug("updating sudoers for root and jack")

        # give jack full sudo rights, saving sudoers for restoraton during
        # install
        if not os.path.exists(os.path.join(self.pkg_img_path, "save/etc")):
            os.makedirs(os.path.join(self.pkg_img_path, "save/etc"))

        shutil.copy2(os.path.join(self.ba_build, "etc/sudoers"),
                     os.path.join(self.pkg_img_path, "save/etc/sudoers"))

        with open(os.path.join(self.ba_build, "etc", "sudoers"), "a") as fh:
            fh.write("jack ALL=(ALL) ALL\n")

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Boot Archive Configuration" + \
            " Checkpoint ===")

        self.parse_doc()

        self.add_root_transfer_to_doc()

        # configure various boot archive files
        self.configure_system()

        # configure gdm for automatic login
        self.configure_gdm()

        # configure /etc/sudoers
        self.configure_sudoers()

        # configure various symlinks
        self.configure_symlinks()


class TextBootArchiveConfigure(BootArchiveConfigure, Checkpoint):
    """ TextBootArchiveConfigure - class to configure the boot archive
    directory specific to the text install media
    """

    DEFAULT_ARG = {"image_type": ".textinstall"}

    def __init__(self, name, arg=DEFAULT_ARG):
        """ constructor for class.
        image_type - string containing the image_type (.autoinstall, .livecd)
        """
        super(TextBootArchiveConfigure, self).__init__(name, arg)
        self.image_type = arg.get("image_type",
                                  self.DEFAULT_ARG.get("image_type"))
