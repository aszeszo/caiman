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

""" pre_pkg_img_mod.py - Customizations to the package image area before
boot archive construction begins.
"""
import os
import os.path
import re
import shutil
import subprocess
from distutils.text_file import TextFile

from osol_install.install_utils import dir_size, encrypt_password
from pkg.cfgfiles import PasswordFile
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.distro_const import DC_LABEL, DC_PERS_LABEL
from solaris_install.distro_const.configuration import Configuration

# load a table of common unix cli calls
import solaris_install.distro_const.cli as cli
cli = cli.CLI()


class PrePkgImgMod(Checkpoint):
    """ Configure the pkg_image path before creating the boot_archive.
    """

    DEFAULT_ARG = {"root_password": "solaris", "is_plaintext": "true"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(PrePkgImgMod, self).__init__(name)
        self.root_password = arg.get("root_password",
                                     self.DEFAULT_ARG.get("root_password"))
        self.is_plaintext = arg.get("is_plaintext",
                                    self.DEFAULT_ARG.get("is_plaintext"))
        self.hostname = arg.get("hostname")

        # instance attributes
        self.doc = None
        self.dc_dict = {}
        self.dc_pers_dict = {}
        self.svc_profiles = []
        self.pkg_img_path = None
        self.img_info_path = None
        self.ba_build = None
        self.tmp_dir = None
        self.save_path = None

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 180

    def parse_doc(self):
        """ class method for parsing data object cache (DOC) objects for use by
        the checkpoint.
        """
        self.doc = InstallEngine.get_instance().data_object_cache

        try:
            self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
                class_type=DataObjectDict)[0].data_dict
            self.ba_build = self.dc_dict["ba_build"]
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.img_info_path = os.path.join(self.pkg_img_path, ".image_info")
            self.tmp_dir = self.dc_dict.get("tmp_dir")
            svc_profile_list = self.doc.volatile.get_descendants(self.name,
                class_type=Configuration)
            dc_pers_dict = self.doc.persistent.get_children(name=DC_PERS_LABEL,
                class_type=DataObjectDict)
            if dc_pers_dict:
                self.dc_pers_dict = dc_pers_dict[0].data_dict

        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " +
                               str(msg))

        for profile in svc_profile_list:
            self.svc_profiles.append(profile.source)

    def set_password(self):
        """ class method to set the root password
        """
        self.logger.debug("root password is: " + self.root_password)
        self.logger.debug("is root password plaintext: " +
                          str(self.is_plaintext))

        if self.is_plaintext.capitalize() == "True":
            encrypted_pw = encrypt_password(self.root_password,
                                            alt_root=self.pkg_img_path)
        else:
            encrypted_pw = self.root_password

        self.logger.debug("encrypted root password is: " + encrypted_pw)

        pfile = PasswordFile(self.pkg_img_path)
        root_entry = pfile.getuser("root")
        root_entry["password"] = encrypted_pw
        pfile.setvalue(root_entry)
        pfile.writefile()

    def modify_etc_system(self):
        """ class method to modify etc/system
        """
        # path to the save directory
        save_path = os.path.join(self.pkg_img_path, "save")

        if not os.path.exists(save_path):
            os.mkdir(save_path)

        # create /save/etc directory, if needed
        if not os.path.exists(os.path.join(save_path, "etc")):
            os.mkdir(os.path.join(save_path, "etc"))

        # save a copy of /etc/system
        etc_system = os.path.join(self.pkg_img_path, "etc/system")
        if os.path.exists(etc_system):
            shutil.copy2(etc_system, os.path.join(save_path, "etc/system"))

        # Modify /etc/system to make ZFS consume less memory
        with open(etc_system, "a+") as fh:
            fh.write("set zfs:zfs_arc_max=0x4002000\n")
            fh.write("set zfs:zfs_vdev_cache_size=0\n")

    def configure_smf(self):
        """ class method for the configuration of SMF manifests
        """
        self.logger.info("Preloading SMF repository")

        cmd = [cli.MANIFEST_IMPORT, "-f",
               os.path.join(self.pkg_img_path, "etc/svc/repository.db"),
               "-d", os.path.join(self.pkg_img_path, "var/svc/manifest")]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        subprocess.check_call(cmd)

        cmd = [cli.MANIFEST_IMPORT, "-f",
               os.path.join(self.pkg_img_path, "etc/svc/repository.db"),
               "-d", os.path.join(self.pkg_img_path, "lib/svc/manifest")]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        subprocess.check_call(cmd)

        # update environment variables
        os.environ.update({"SVCCFG_REPOSITORY":
            os.path.join(self.pkg_img_path, "etc/svc/repository.db")})

        # set the SVCCFG_DTD root
        os.environ.update({"SVCCFG_DTD":
            "/usr/share/lib/xml/dtd/service_bundle.dtd.1"})

        # apply SMF profiles

        # use the svccfg in the package image path
        SVCCFG = os.path.join(self.pkg_img_path, "usr/sbin/svccfg")

        if not os.path.exists(SVCCFG):
            raise RuntimeError(SVCCFG + " does not exist")

        for svc_profile_path in self.svc_profiles:
            self.logger.info("Applying SMF profile: %s" % svc_profile_path)

            cmd = [SVCCFG, "apply", svc_profile_path]
            self.logger.debug("executing:  %s" % " ".join(cmd))
            subprocess.check_call(cmd)

        # set the hostname of the distribution
        if self.hostname is not None:
            cmd = [SVCCFG, "-s", "system/identity:node", "setprop",
                   "config/nodename", "=", "astring:", '"%s"' % self.hostname]
            self.logger.debug("executing:  %s" % " ".join(cmd))
            subprocess.check_call(cmd)
        else:
            # retrieve the default hostname
            cmd = [SVCCFG, "-s", "system/identity:node", "listprop",
                   "config/nodename"]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            outs, _none = p.communicate()
            self.hostname = outs.strip().split()[2]

        # update /etc/inet/hosts with the hostname
        hostsfile = os.path.join(self.pkg_img_path, "etc/inet/hosts")
        l = []
        with open(hostsfile, "r") as fh:
            for line in fh.readlines():
                if line.startswith("127"):
                    line = "%s\t%s\n" % (line.rstrip(), self.hostname)
                l.append(line)

        # re-write the file
        with open(hostsfile, "w") as fh:
            fh.writelines(l)

        # unset SVCCFG_REPOSITORY and SVCCFG_DTD
        del os.environ["SVCCFG_REPOSITORY"]
        del os.environ["SVCCFG_DTD"]

    def calculate_size(self):
        """ class method to populate the .image_info file with the size of the
        image.
        """
        self.logger.debug("calculating size of the pkg_image area")
        image_size = int(round((dir_size(self.pkg_img_path) / 1024)))

        with open(self.img_info_path, "a+") as fh:
            fh.write("IMAGE_SIZE=%d\n" % image_size)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                            "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # preload smf manifests
        self.configure_smf()

        # write out the .image_info file
        self.calculate_size()


class AIPrePkgImgMod(PrePkgImgMod, Checkpoint):
    """ class to prepare the package image area for AI distributions
    """

    DEFAULT_ARG = {"root_password": "solaris", "is_plaintext": "true"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(AIPrePkgImgMod, self).__init__(name)
        self.root_password = arg.get("root_password",
                                     self.DEFAULT_ARG.get("root_password"))
        self.is_plaintext = arg.get("is_plaintext",
                                    self.DEFAULT_ARG.get("is_plaintext"))
        self.hostname = arg.get("hostname")

    def get_pkg_version(self, pkg):
        """ class method to store the version of a package into a path

        pkg - which package to query
        path - where to write the output to
        """
        self.logger.debug("extracting package version of %s" % pkg)
        version_re = re.compile(r"FMRI:.*?%s@.*?\,(.*?):" % pkg)

        cmd = [cli.PKG, "-R", self.pkg_img_path, "info", pkg]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        pkg_output = p.communicate()[0]

        version = version_re.search(pkg_output).group(1)

        # ai_pkg_version needs to live in the persistent
        # section of the DOC to ensure pause/resume works
        # correctly.
        #
        # update the DC_PERS_LABEL DOC object with a new
        # dictionary that contains ai_pkg_version as an
        # additional entry.
        if len(self.dc_pers_dict) != 0:
            self.doc.persistent.delete_children(name=DC_PERS_LABEL)

        self.dc_pers_dict[pkg] = version
        self.doc.persistent.insert_children(DataObjectDict(DC_PERS_LABEL,
            self.dc_pers_dict, generate_xml=True))

    def add_versions(self, version_filename):
        """ class method to populate the .image_info file with the versions
        of the image.
        """
        self.logger.debug("adding the versions of the iso image")
        img_version_path = os.path.join(self.pkg_img_path, version_filename)

        # append the .image_info file with the version file information
        with open(self.img_info_path, "a") as img_fh:
            version_fh = TextFile(filename=img_version_path, lstrip_ws=True)
            version_line = version_fh.readline()
            while version_line:
                img_fh.write(version_line + '\n')
                version_line = version_fh.readline()

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                         "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # preload smf manifests
        self.configure_smf()

        # set up the pkg_img_path with auto-install information
        self.logger.debug("creating auto_install directory")
        os.chdir(os.path.join(self.pkg_img_path, "usr/share"))
        shutil.copytree("auto_install", os.path.join(self.pkg_img_path,
            "auto_install"), symlinks=True)

        self.get_pkg_version("auto-install")
        self.modify_etc_system()

        # write out the .image_info file
        self.calculate_size()
        self.add_versions("usr/share/auto_install/version")


class LiveCDPrePkgImgMod(PrePkgImgMod, Checkpoint):
    """ class to prepare the package image area for LiveCD distributions
    """

    DEFAULT_ARG = {"root_password": "solaris", "is_plaintext": "true"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(LiveCDPrePkgImgMod, self).__init__(name)
        self.root_password = arg.get("root_password",
                                     self.DEFAULT_ARG.get("root_password"))
        self.is_plaintext = arg.get("is_plaintext",
                                    self.DEFAULT_ARG.get("is_plaintext"))
        self.hostname = arg.get("hostname")

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 180

    def save_files(self):
        """ class method for saving key files and directories for restoration
        after installation
        """
        self.logger.debug("Creating the save directory with files and " +
                          "directories for restoration after installation")

        os.chdir(self.pkg_img_path)

        # path to the save directory
        self.save_path = os.path.join(self.pkg_img_path, "save")

        # create needed directory paths
        save_dirs = ["usr/share/dbus-1/services", "etc/gconf/schemas",
                     "usr/share/gnome/autostart", "etc/xdg/autostart"]
        for d in save_dirs:
            if not os.path.exists(os.path.join(self.save_path, d)):
                os.makedirs(os.path.join(self.save_path, d))

        # remove gnome-power-manager, vp-sysmon, and updatemanagernotifier
        # from the liveCD and restore after installation
        save_files = ["etc/xdg/autostart/updatemanagernotifier.desktop",
                      "usr/share/dbus-1/services/gnome-power-manager." + \
                      "service",
                      "usr/share/dbus-1/services/gnome-power-manager." + \
                      "desktop",
                      "usr/share/gnome/autostart/vp-sysmon.desktop",
                      "etc/system"]

        for f in save_files:
            # move the files and preserve the file metadata
            if os.path.exists(os.path.join(self.pkg_img_path, f)):
                shutil.move(os.path.join(self.pkg_img_path, f),
                            os.path.join(self.save_path, os.path.dirname(f)))

        # fix /etc/gconf/schemas/panel-default-setup.entries to use the theme
        # background rather than image on live CD and restore it after
        # installation
        panel_file = "etc/gconf/schemas/panel-default-setup.entries"

        # copy the file to the save directory first
        shutil.copy2(os.path.join(self.pkg_img_path, panel_file),
                     os.path.join(self.save_path, panel_file))

        with open(os.path.join(self.pkg_img_path, panel_file), "r") as fh:
            panel_file_data = fh.read()

        panel_file_data = panel_file_data.replace("<string>image</string>",
                                                  "<string>gtk</string>")
        # re-open the file and write the data out
        with open(os.path.join(self.pkg_img_path, panel_file), "w+") as fh:
            fh.write(panel_file_data)

    def generate_gnome_caches(self):
        """ class method to generate the needed gnome caches
        """
        # GNOME service start methods are executed in order to
        # pre-generate the gnome caches. Since these services are
        # not alternate root aware, the start methods need to be
        # executed in a chroot'd environment (chroot'd to the pkg_image
        # area).
        #
        # Also, the service start methods redirect their output to /dev/null.
        # Create a temporary file named 'dev/null' inside the pkg_image
        # area where these services can dump messages to. Once the caches
        # have been generated, the temporary 'dev/null' file needs to be
        # removed.
        self.logger.debug("creating temporary /dev/null in pkg_image")
        cmd = [cli.TOUCH, os.path.join(self.pkg_img_path, "dev/null")]
        subprocess.check_call(cmd)

        # use the repository in the proto area
        os.environ.update({"SVCCFG_REPOSITORY":
            os.path.join(self.pkg_img_path, "etc/svc/repository.db")})

        # generate a list of services to refresh
        cmd = [cli.SVCCFG, "list", "*desktop-cache*"]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        stdout, _none = p.communicate()
        service_list = stdout.splitlines()

        # if no services were found, log a message
        if not service_list:
            self.logger.debug("no services named *desktop-cache* were found")

        # since there is only a handful of methods to execute, there is
        # negligible overhead to spawning a process to execute the method.
        for service in service_list:
            # remove ":default" from the service name
            service = service.replace(":default", "")

            # get the name of the refresh/exec script
            cmd = [cli.SVCCFG, "-s", service, "listprop", "refresh/exec"]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            stdout, _none = p.communicate()

            # verify there's no error
            if p.returncode != 0:
                self.logger.critical("service: " + service + "does " +
                                     "not have a start method")
                continue

            # the output looks like:
            # refresh/exec  astring  "/lib/svc/method/method-name %m"\n

            # the method is the 3rd argument
            method = stdout.split()[2]

            # strip the double-quotes from the method
            method = method.strip('"')

            # fork a process for chroot
            pid = os.fork()
            cmd = [cli.BASH, method, "refresh"]
            if pid == 0:
                os.chroot(self.pkg_img_path)
                self.logger.debug("executing:  %s" % " ".join(cmd))
                subprocess.check_call(cmd, stdout=open("/dev/null", "w"),
                                      stderr=subprocess.STDOUT)
                os._exit(0)
            else:
                # wait for the child to exit
                _none, status = os.wait()
                if status != 0:
                    raise RuntimeError("%s failed" % " ".join(cmd))

        # unset SVCCFG_REPOSITORY
        del os.environ["SVCCFG_REPOSITORY"]

        # We disabled gnome-netstatus-applet for the liveCD but we want it
        # to be active when the default user logs in after installation.
        # By giving the saved copy of panel-default-setup.entries a later
        # timestamp than the global gconf cache we'll end up enabling the
        # applet on first reboot when the desktop-cache/gconf-cache service
        # starts.
        cmd = [cli.TOUCH, os.path.join(self.pkg_img_path,
               "etc/gconf/schemas/panel-default-setup.entries")]
        self.logger.debug("executing:  %s" % " ".join(cmd))
        subprocess.check_call(cmd)

        # remove the temporary dev/null
        self.logger.debug("removing temporary /dev/null from pkg_image")
        os.unlink(os.path.join(self.pkg_img_path, "dev/null"))

        self.logger.info("Creating font cache")
        pid = os.fork()
        cmd = [cli.FC_CACHE, "--force"]
        if pid == 0:
            os.chroot(self.pkg_img_path)
            self.logger.debug("executing:  %s" % " ".join(cmd))
            subprocess.check_call(cmd)
            os._exit(0)
        else:
            _none, status = os.wait()
            if status != 0:
                    raise RuntimeError("%s failed" % " ".join(cmd))

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                         "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # preload smf manifests
        self.configure_smf()

        # save key files and directories
        self.save_files()

        # modify /etc/system
        self.modify_etc_system()

        # create the gnome caches
        self.generate_gnome_caches()

        # write out the .image_info file
        self.calculate_size()


class TextPrePkgImgMod(PrePkgImgMod, Checkpoint):
    """ class to prepare the package image area for text install distributions
    """

    DEFAULT_ARG = {"root_password": "solaris", "is_plaintext": "true"}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(TextPrePkgImgMod, self).__init__(name)
        self.root_password = arg.get("root_password",
                                     self.DEFAULT_ARG.get("root_password"))
        self.is_plaintext = arg.get("is_plaintext",
                                    self.DEFAULT_ARG.get("is_plaintext"))
        self.hostname = arg.get("hostname")

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                         "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # preload smf manifests
        self.configure_smf()

        # modify /etc/system
        self.modify_etc_system()

        # write out the .image_info file
        self.calculate_size()
