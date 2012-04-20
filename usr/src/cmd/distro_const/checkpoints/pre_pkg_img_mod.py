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

""" pre_pkg_img_mod.py - Customizations to the package image area before
boot archive construction begins.
"""
import logging
import os
import platform
import re
import shutil
import tempfile

from distutils.text_file import TextFile

from osol_install.install_utils import dir_size, encrypt_password
from pkg.cfgfiles import PasswordFile
from solaris_install import CalledProcessError, DC_LABEL, DC_PERS_LABEL, \
    path_matches_dtd, run
from solaris_install.configuration.configuration import Configuration
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.data_object.data_dict import DataObjectDict

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
        self.image_type = ""

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
            # path to the save directory
            self.save_path = os.path.join(self.pkg_img_path, "save")
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

    def modify_dhcpagent(self):
        """ method to modify /etc/default/dhcpagent to include the Rootpath
        bootp-dhcp-parameter for finding iSCSI information from the DHCP server

        This method can be removed if/when CR 7129888 is addressed
        """

        # verify /etc/default/dhcpagent exists
        dhcpagent = os.path.join(self.pkg_img_path, "etc/default/dhcpagent")
        if not os.path.exists(dhcpagent):
            self.logger.debug("skipping save of /etc/default/dhcpagent")
            return

        # path to the save directory
        save_path = os.path.join(self.pkg_img_path, "save")

        if not os.path.exists(save_path):
            os.mkdir(save_path)

        # create /save/etc/default directory, if needed
        if not os.path.exists(os.path.join(save_path, "etc/default")):
            os.makedirs(os.path.join(save_path, "etc/default"))

        # save a copy of /etc/default/dhcpagent
        shutil.copy2(dhcpagent,
                     os.path.join(save_path, "etc/default/dhcpagent"))

        # open the file and read it into memory
        with open(dhcpagent, "r") as fh:
            contents = fh.read()

        new_file = list()
        for line in contents.splitlines():
            if line.startswith("PARAM_REQUEST_LIST") and "17" not in line:
                # append the parameter to enable rootpath
                new_file.append(line + ",17")
            else:
                new_file.append(line)

        # rewrite the file
        with open(dhcpagent, "w+") as fh:
            fh.write("\n".join(new_file))
            fh.write("\n")

    def save_etc_inet_hosts(self):
        """ class method to save pristine hosts(4) file. hosts(4) file
        is modified by identity:node smf service and we don't want those
        changes to be propagated to the target system.
        """
        # create save/etc/inet directory, if needed
        if not os.path.exists(os.path.join(self.save_path, "etc/inet")):
            os.makedirs(os.path.join(self.save_path, "etc/inet"))

        # save a copy of /etc/inet/hosts
        etc_inet_hosts = os.path.join(self.pkg_img_path, "etc/inet/hosts")
        if os.path.exists(etc_inet_hosts):
            shutil.copy2(etc_inet_hosts, os.path.join(self.save_path,
                                                      "etc/inet/hosts"))

    def save_menu_lst(self):
        """ class method to save the original /boot/grub/menu.lst file if it
            exists. It will not exist on GRUB2 based images so it is silently
            ignored if not present.
        """

        save_list = ["boot/grub/menu.lst"]
        if os.path.exists(os.path.join(self.pkg_img_path, save_list[0])):
            self.save_files_directories(save_list)

    def save_files_directories(self, save_list=None):
        """ class method for saving key files and directories for restoration
        after installation. Missing target directories are created.
        """

        # If there is nothing to save, just return
        if save_list is None or len(save_list) == 0:
            return

        for df in save_list:
            # If object does not exist, skip it.
            full_path = os.path.join(self.pkg_img_path, df)
            dest_path = os.path.join(self.save_path, df)
            if not os.path.exists(full_path):
                self.logger.error("WARNING:  unable to find " + full_path +
                                  " to save for later restoration!")
                continue

            # If object is directory, just create it in save area.
            if os.path.isdir(full_path) and not os.path.exists(dest_path):
                os.makedirs(dest_path)
                continue

            # If object is file, move it to save area. Create missing
            # directories as part of that process.
            if os.path.isfile(full_path) and not os.path.exists(dest_path):
                dir_path = os.path.dirname(dest_path)
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)

                # move the file and preserve file metadata
                shutil.move(full_path, dir_path)

    def configure_smf(self):
        """ class method for the configuration of SMF manifests
        """

        #
        # For purposes of System Configuration, network/physical
        # and network/install services have to depend on manifest-import
        # and milestone/config. That creates dependency cycle on install
        # media, since network/physical (depending on network/install)
        # takes care of bringing up PXE/wanboot NIC which is needed for
        # purposes of mounting root filesystem (in case of network boot).
        # And milestone/config and manifest-import depend on smf services
        # responsible for assembling root filesystem.
        #
        # As a workaround, deliver media specific smf manifests
        # for milestone/config, network/physical and network/install -
        # import milestone/config and manifest-import without specifying
        # network/physical and network/install as their dependents.
        # We can do that, since media come pre-configured.
        #
        # Save the original manifests - they replace media specific ones
        # on the target system in case of CPIO transfer method.
        #
        save_list = ["lib/svc/manifest/milestone/config.xml",
                     "lib/svc/manifest/network/network-install.xml",
                     "lib/svc/manifest/network/network-physical.xml"]

        self.save_files_directories(save_list)

        self.logger.info("Preloading SMF repository")

        # create a unique file in /tmp for the construction of the SMF
        # repository
        _none, repo_name = tempfile.mkstemp(dir="/tmp", prefix="install_repo_")

        # Set environment variables needed by svccfg.
        smf_env_vars = dict()
        smf_env_vars["SVCCFG_REPOSITORY"] = repo_name
        smf_env_vars["SVCCFG_CONFIGD_PATH"] = os.path.join(
            self.pkg_img_path, "lib/svc/bin/svc.configd")
        smf_env_vars["SVCCFG_DTD"] = os.path.join(
            self.pkg_img_path, "usr/share/lib/xml/dtd/service_bundle.dtd.1")
        smf_env_vars["SVCCFG_MANIFEST_PREFIX"] = self.pkg_img_path
        smf_env_vars["SVCCFG_CHECKHASH"] = "1"

        # add all of the manifests in /var and /lib
        for manifest_dir in ["lib", "var"]:
            import_dir = os.path.join(self.pkg_img_path,
                                      "%s/svc/manifest" % manifest_dir)
            cmd = [cli.SVCCFG, "import", import_dir]
            try:
                p = run(cmd, env=smf_env_vars)
            except CalledProcessError:
                raise RuntimeError("Error importing manifests from %s" % \
                                   import_dir)

        # Apply each profile from the manifest
        for svc_profile_path in self.svc_profiles:
            self.logger.info("Applying SMF profile: %s" % svc_profile_path)
            cmd = [cli.SVCCFG, "apply", svc_profile_path]
            run(cmd, env=smf_env_vars)

        # set the hostname of the distribution
        if self.hostname is not None:
            cmd = [cli.SVCCFG, "-s", "system/identity:node", "setprop",
                   "config/nodename", "=", "astring:", '"%s"' % self.hostname]
            run(cmd, env=smf_env_vars)
        else:
            # retrieve the default hostname
            cmd = [cli.SVCCFG, "-s", "system/identity:node", "listprop",
                   "config/nodename"]
            p = run(cmd, env=smf_env_vars)
            self.hostname = p.stdout.strip().split()[2]

        # move the repo from /tmp to the proper place
        self.logger.debug("moving repo from /tmp into pkg_image directory")
        shutil.move(repo_name, os.path.join(self.pkg_img_path,
            "etc/svc/repository.db"))

    def calculate_size(self):
        """ class method to populate the .image_info file with the size of the
        image.
        """
        self.logger.debug("calculating size of the pkg_image area")
        image_size = int(round((dir_size(self.pkg_img_path) / 1024)))

        with open(self.img_info_path, "a+") as fh:
            fh.write("IMAGE_SIZE=%d\n" % image_size)

    def add_image_type(self):
        """ class method to populate the .image_info file with the 
        image type.
        """
        with open(self.img_info_path, "a+") as fh:
            fh.write("IMAGE_TYPE=%s\n" % self.image_type)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class
        dry_run is not used in DC
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                            "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # save /boot/grub/menu.lst
        self.save_menu_lst()

        # preload smf manifests
        self.configure_smf()

        # write out the .image_info file
        self.calculate_size()

        # write out the image type into the .image_info file
        self.add_image_type()


class AIPrePkgImgMod(PrePkgImgMod, Checkpoint):
    """ class to prepare the package image area for AI distributions
    """

    DEFAULT_ARG = {"root_password": "solaris", "is_plaintext": "true",
                   "service_name": None}
    SERVICE_NAME = "solarisdev-%{arch}-%{build}"

    def __init__(self, name, arg=DEFAULT_ARG):
        super(AIPrePkgImgMod, self).__init__(name)
        self.root_password = arg.get("root_password",
                                     self.DEFAULT_ARG.get("root_password"))
        self.is_plaintext = arg.get("is_plaintext",
                                    self.DEFAULT_ARG.get("is_plaintext"))
        self.hostname = arg.get("hostname")
        self._service_name = arg.get("service_name",
                                     self.DEFAULT_ARG.get("service_name"))
        self.image_type = "AI"

    def get_pkg_version(self, pkg):
        """ class method to store the version of a package into a path

        pkg - which package to query
        path - where to write the output to
        """
        self.logger.debug("extracting package version of %s" % pkg)
        version_re = re.compile(r"FMRI:.*?%s@.*?\,(.*?):" % pkg)

        cmd = [cli.PKG, "-R", self.pkg_img_path, "info", pkg]
        p = run(cmd)
        version = version_re.search(p.stdout).group(1)

        # auto-install pkg version needs to live in the persistent
        # section of the DOC to ensure pause/resume works correctly.
        # Save it here for later update in DOC by the execute method.
        self.dc_pers_dict[pkg] = version

    def get_license(self):
        """ class method to get license and save to a file

        The OTN license from the osnet-incorporation pkg is obtained and
        saved to a file for later use by the ai_publish_pkg checkpoint.

        """
        self.logger.debug("obtaining OTN license for AI image package")
        cmd = [cli.PKG, "-R", self.pkg_img_path, "info", "--license",
               "osnet-incorporation"]
        pkg_info = run(cmd)

        # if the tmp_dir doesn't exist create it
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

        lic_path = os.path.join(self.tmp_dir, "lic_OTN")
        with open(lic_path, 'w') as otn_license:
            otn_license.write(pkg_info.stdout)

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

    def add_default_svcname(self, pkg):
        """ class method to populate the .image_info file with the default
        service name. The default service name is used by installadm
        create-service if no service name is explicitly specified.
        """
        self.logger.debug("adding the default service name")

        if self._service_name is None:
            self._service_name = self.SERVICE_NAME
        name = self._service_name.replace("%{", "%(").replace("}", ")s")
        # get build number from version (from '5.11-0.171' or '5.11-0.175.0.1'
        # get '171' or '175.0.1')
        build = self.dc_pers_dict[pkg].partition("-")[2].partition('.')[2]

        # Replace the '.'s in the build name with '_'s.  The service name
        # that is generated from 'build' is used as the default service
        # name in 'installadm create-service'.  The inclusion of '.'s
        # in the service name cause problems for the DNS server so they
        # need to be either removed or replaced.
        build = build.replace('.', '_')

        name = name % {"build": build, "arch": platform.processor()}

        # the service name needs to be in the persistent section of
        # the DOC for ai-publish-package to reference later. Save
        # it locally and the execute method will update the DOC.
        self.dc_pers_dict["service-name"] = name

        # append the .image_info file with the service name
        with open(self.img_info_path, "a") as fh:
            fh.write("SERVICE_NAME=%s\n" % name)

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class.
        """
        self.logger.info("=== Executing Pre-Package Image Modification " +
                         "Checkpoint ===")

        self.parse_doc()

        # set root's password
        self.set_password()

        # save /boot/grub/menu.lst
        self.save_menu_lst()

        # preload smf manifests
        self.configure_smf()

        # set up the pkg_img_path with auto-install information
        self.logger.debug("creating auto_install directory")

        # change source path to 'usr/share' of the package image
        os.chdir(os.path.join(self.pkg_img_path, "usr/share"))

        # set destination path
        pkg_ai_path = os.path.join(self.pkg_img_path, "auto_install")

        # Copy files from /usr/share/auto_install
        shutil.copytree("auto_install", pkg_ai_path, symlinks=True)

        # Copy files from /usr/share/install too
        old_wd = os.getcwd()
        os.chdir(os.path.join(self.pkg_img_path, "usr/share/install"))
        ai_dtd_found = False
        for dtd_file in [f for f in os.listdir(".") if path_matches_dtd(f)]:
            shutil.copy(dtd_file, pkg_ai_path)
            if not ai_dtd_found and dtd_file.startswith("ai.dtd"):
                ai_dtd_found = True
                os.symlink(dtd_file, os.path.join(pkg_ai_path, "ai.dtd"))
        os.chdir(old_wd)  # Restore Working Directory

        # move in service_bundle(4) for AI server profile validation
        shutil.copy("lib/xml/dtd/service_bundle.dtd.1", pkg_ai_path)

        # clear way for get_pkg_version and add_default_svcname
        # to update the dc_pers_dict
        if self.dc_pers_dict:
            self.doc.persistent.delete_children(name=DC_PERS_LABEL)

        self.get_pkg_version("auto-install")
        self.get_license()
        self.modify_etc_system()

        # modify /etc/default/dhcpagent
        self.modify_dhcpagent()

        # write out the .image_info file
        self.calculate_size()

        # write out the image type into the .image_info file
        self.add_image_type()

        self.add_versions("usr/share/auto_install/version")
        self.add_default_svcname("auto-install")

        # update the DC_PERS_LABEL DOC object with a new
        # dictionary that contains auto-install and service_name
        # as additional entries.
        self.logger.debug("updating persistent doc %s" % self.dc_pers_dict)
        self.doc.persistent.insert_children(DataObjectDict(DC_PERS_LABEL,
            self.dc_pers_dict, generate_xml=True))


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
        self.image_type = "LiveCD"

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will take
            in seconds
        """
        return 180

    def save_files(self):
        """ class method for saving key files and directories for restoration
        after installation. Files are moved to the 'save' area.
        """
        self.logger.debug("Creating the save directory with files and " +
                          "directories for restoration after installation")

        # remove gnome-power-manager, vp-sysmon, and updatemanagernotifier
        # from the liveCD and restore after installation
        save_list = [
            "etc/gconf/schemas",
            "etc/xdg/autostart/updatemanagernotifier.desktop",
            "usr/share/dbus-1/services/gnome-power-manager.service",
            "usr/share/gnome/autostart/gnome-power-manager.desktop",
            "usr/share/gnome/autostart/vp-sysmon.desktop"
        ]

        self.save_files_directories(save_list)

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

        #
        # Needed, otherwise it was observed that some binaries run within
        # 'chroot' environment fail to determine 'current working directory'.
        #
        os.chdir(self.pkg_img_path)

        self.logger.debug("creating temporary /dev/null in pkg_image")
        cmd = [cli.TOUCH, os.path.join(self.pkg_img_path, "dev/null")]
        run(cmd)

        # Set environment variables needed by svccfg.
        smf_env_vars = dict()
        smf_env_vars["SVCCFG_CONFIGD_PATH"] = os.path.join(
            self.pkg_img_path, "lib/svc/bin/svc.configd")
        smf_env_vars["SVCCFG_DTD"] = os.path.join(
            self.pkg_img_path, "usr/share/lib/xml/dtd/service_bundle.dtd.1")
        smf_env_vars["SVCCFG_MANIFEST_PREFIX"] = self.pkg_img_path
        smf_env_vars["SVCCFG_CHECKHASH"] = "1"
        smf_env_vars["SVCCFG_REPOSITORY"] = os.path.join(
            self.pkg_img_path, "etc/svc/repository.db")

        # generate a list of services to refresh
        cmd = [cli.SVCCFG, "list", "*desktop-cache*"]
        p = run(cmd, stderr_loglevel=logging.ERROR, env=smf_env_vars)
        service_list = p.stdout.splitlines()

        # if no services were found, log a message
        if not service_list:
            self.logger.error("WARNING:  no services named *desktop-cache* "
                              "were found")

        # since there is only a handful of methods to execute, there is
        # negligible overhead to spawning a process to execute the method.
        for service in service_list:
            # remove ":default" from the service name
            service = service.replace(":default", "")

            # get the name of the refresh/exec script
            cmd = [cli.SVCCFG, "-s", service, "listprop", "refresh/exec"]
            try:
                p = run(cmd, env=smf_env_vars)
            except CalledProcessError:
                self.logger.critical("service: " + service + " does " +
                                     "not have a start method")
                continue

            # the output looks like:
            # refresh/exec  astring  "/lib/svc/method/method-name %m"\n

            # the method is the 3rd argument
            method = p.stdout.split()[2]

            # strip the double-quotes from the method
            method = method.strip('"')

            # fork a process for chroot
            pid = os.fork()
            cmd = [cli.BASH, method, "refresh"]
            if pid == 0:
                os.chroot(self.pkg_img_path)
                self.logger.debug("executing:  %s" % " ".join(cmd))
                run(cmd)
                os._exit(0)
            else:
                # wait for the child to exit
                _none, status = os.wait()
                if status != 0:
                    raise RuntimeError("%s failed" % " ".join(cmd))

        # We disabled gnome-netstatus-applet for the liveCD but we want it
        # to be active when the default user logs in after installation.
        # By giving the saved copy of panel-default-setup.entries a later
        # timestamp than the global gconf cache we'll end up enabling the
        # applet on first reboot when the desktop-cache/gconf-cache service
        # starts.
        cmd = [cli.TOUCH, os.path.join(self.pkg_img_path,
               "etc/gconf/schemas/panel-default-setup.entries")]
        run(cmd)

        # remove the temporary dev/null
        self.logger.debug("removing temporary /dev/null from pkg_image")
        os.unlink(os.path.join(self.pkg_img_path, "dev/null"))

        self.logger.info("Creating font cache")
        pid = os.fork()
        cmd = [cli.FC_CACHE, "--force"]
        if pid == 0:
            os.chroot(self.pkg_img_path)
            run(cmd)
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

        # save /boot/grub/menu.lst
        self.save_menu_lst()

        # preload smf manifests
        self.configure_smf()

        # save key files and directories
        self.save_files()

        # modify /etc/system
        self.modify_etc_system()

        # modify /etc/default/dhcpagent
        self.modify_dhcpagent()

        # save pristine /etc/inet/hosts file
        self.save_etc_inet_hosts()

        # create the gnome caches
        self.generate_gnome_caches()

        # write out the .image_info file
        self.calculate_size()

        # write out the image type into the .image_info file
        self.add_image_type()


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
        self.image_type = "Text"

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

        # modify /etc/default/dhcpagent
        self.modify_dhcpagent()

        # save pristine /etc/inet/hosts file
        self.save_etc_inet_hosts()

        # write out the .image_info file
        self.calculate_size()

        # write out the image type into the .image_info file
        self.add_image_type()
