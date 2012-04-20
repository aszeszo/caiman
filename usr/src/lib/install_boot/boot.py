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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
""" boot.py -- Installs and configures boot loader and boot menu
    onto physical systems and installation images.
"""

import abc
import array
import fcntl
import linecache
import os
import platform
import struct
import tempfile

from grp import getgrnam
from pwd import getpwnam
from shutil import move, rmtree

from bootmgmt import bootconfig, BootmgmtUnsupportedPlatformError, \
    BootmgmtPropertyWriteError, BootmgmtUnsupportedPropertyError
from bootmgmt.bootconfig import BootConfig, DiskBootConfig, ODDBootConfig, \
    SolarisDiskBootInstance, SolarisODDBootInstance, ChainDiskBootInstance
from bootmgmt.bootinfo import SystemFirmware
from bootmgmt.bootloader import BootLoader
from solaris_install import DC_LABEL, DC_PERS_LABEL, \
    CalledProcessError, Popen, run
from solaris_install.boot.boot_spec import BootMods, BootEntry
from solaris_install.data_object import ObjectNotFoundError
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.logger import INSTALL_LOGGER_NAME as ILN
from solaris_install.target import Target
from solaris_install.target.logical import be_list, BE, Zpool
from solaris_install.target.physical import Disk, FDISK, Iscsi, GPTPartition, \
    Partition, Slice
from solaris_install.target.vdevs import _get_vdev_mapping
from solaris_install.transfer.media_transfer import get_image_grub_title

BOOT_ENV = "boot-env"
# Boot GPT partition or slice devices eg. c0t0d0s0
DEVS = "devs"

# Stuff used to set up a USB media image with grub2
GRUB_SETUP = "/usr/lib/grub2/bios/sbin/grub-setup"
LOFIADM = "/usr/sbin/lofiadm"
MBR_IMG_RPATH = "boot/mbr.img"

# For USB we assume a 512b block size. Seems most reasonable for a USB stick
BLOCKSIZE = 512
KB = 1024
MB = (KB * KB)


class BootMenu(Checkpoint):
    """ Abstract class for BootMenu checkpoint
    """
    __metaclass__ = abc.ABCMeta
    DEFAULT_TIMEOUT = 30

    def __init__(self, name):
        """ Constructor for class
        """
        super(BootMenu, self).__init__(name)
        self.arch = platform.processor()
        self.boot_entry_list = list()
        self.boot_timeout = BootMenu.DEFAULT_TIMEOUT
        self.boot_mods = None
        self.boot_title = None
        # Used for string token substitution of pybootgmmt return data
        self.boot_tokens = dict()
        self.config = None
        self.doc = InstallEngine.get_instance().data_object_cache
        self.img_info_path = None
        self.rel_file_title = None

    def get_progress_estimate(self):
        """ Returns an estimate of the time this checkpoint will
            take to complete.
        """
        return 5

    @abc.abstractmethod
    def build_default_entries(self):
        """ This method is required to be implemented by all subclasses.
            Standard, pre-defined boot menu entries get created by
            subclass implementors of this method.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def build_custom_entries(self):
        """ This method is required to be implemented by all subclasses.
            Custom entries specified in the boot_mods section of the
            XML manifest get created by subclass implementors of this method.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def _get_rel_file_path(self):
        """ This method is required to be implemented by all subclasses.
            Returns file system path to the release file.
        """
        raise NotImplementedError

    def parse_doc(self, dry_run=False):
        """ Parse data object cache for values required by the checkpoint
            execution.
        """
        # Break doc parsing down into 2 specific parts as the target
        # configuration in the doc differs between DC (for ISO images)
        # and and live system installation.
        self._parse_doc_target(dry_run)
        self._parse_doc_boot_mods()

    def _parse_doc_boot_mods(self):
        """ Parses data object cache (DOC) BootMods tree for configuration of
            the checkpoint.
        """
        try:
            # Check and retrieve the optional manifest
            # specific boot configurations.
            boot_mods = self.doc.get_descendants(class_type=BootMods)
            if len(boot_mods) < 1:
                return
            self.boot_mods = boot_mods[0]
        except ObjectNotFoundError as err:
            raise RuntimeError("Error retrieving BootMods from the DOC: " + \
                str(err))

        if self.boot_mods.title and len(self.boot_mods.title) > 0:
            self.logger.info("Setting boot title prefix from manifest value: \
                             '%s'" % self.boot_mods.title)
            self.boot_title = self.boot_mods.title

        if self.boot_mods.timeout is not None:
            self.logger.info("Setting boot timeout from manifest value: %d" \
                             % self.boot_mods.timeout)
            self.boot_timeout = self.boot_mods.timeout

        try:
            self.boot_entry_list = self.boot_mods.get_children(
                class_type=BootEntry)
        except ObjectNotFoundError:
            # the manifest does not contain any custom boot entries
            self.logger.debug("No custom boot entries found in the DOC")

    @abc.abstractmethod
    def _parse_doc_target(self, dry_run=False):
        """ This method is required to be implemented by all subclasses.
            Additional class specific parsing to determine the boot
            configuration's target paths or devices get performed by
            subclass implementors this method.

            Input:
                None
            Output:
                None
        """
        raise NotImplementedError

    @abc.abstractmethod
    def init_boot_config(self, autogen=True):
        """ This method is required to be implemented by all subclasses.

            Input:
                None
            Output:
                None
        """
        raise NotImplementedError

    @abc.abstractmethod
    def install_boot_loader(self, dry_run=False):
        """ This method is required to be implemented by all subclasses.

            Input:
                dry_run
                - If True, the set of files that constitute the boot
                  configuration is written to a temporary directory (and not to
                  the official location(s)) When files are written to a
                  temporary directory, the list and format of the files written
                  is returned (see Output)
            Output:
                None
        """
        raise NotImplementedError

    def _handle_boot_config_list(self, boot_config_list, dry_run):
        """ Method that checks returned tuple list from commit_boot_config()
            and copies over content as appropriate to their targets.
        """
        for boot_config in boot_config_list:
            # boot-config elements can be either tuples or lists of tuples.
            # Cast tuples into a list for consistent iteration loop below.
            if not isinstance(boot_config, list):
                boot_config = [boot_config]
            for config_set in boot_config:
                ftype = config_set[0]
                if ftype == BootConfig.OUTPUT_TYPE_FILE:
                    self._handle_file_type(config_set)
                elif ftype in [BootConfig.OUTPUT_TYPE_BIOS_ELTORITO,
                               BootConfig.OUTPUT_TYPE_UEFI_ELTORITO]:
                # XXX add handlers for the following when supported:
                #              BootConfig.OUTPUT_TYPE_HSFS_BOOTBLK
                    self._handle_iso_boot_image_type(config_set, dry_run)
                else:
                    raise RuntimeError("Unrecognized boot loader " \
                                       "file type: %s" % ftype)

    def _handle_file_type(self, config):
        """ Method that copies generic file types to their appropriate targets.
        """
        ftype, src, objref, dest, uid, gid, mode = config
        # Copy from 'src' to 'dest' and set uid:gid + mode
        if src is None:
            raise RuntimeError("No source path defined for boot" \
                               "file")
        if dest is None:
            raise RuntimeError("No destination path defined for boot" \
                               "file")
        # XXX The 'dest' field, I believe, should be prepended with the
        # string token '%(systemroot)s' but it currently appears not to
        # be the case sometimes, and instead specifies an absolute path
        # such as '/boot/grub/menu.lst'
        # Check for a leading slash and prepend if necessary
        if os.path.isabs(dest):
            dest = '%(' + BootConfig.TOKEN_SYSTEMROOT + ')s' + dest

        real_dest = dest % (self.boot_tokens)
        par_dir = os.path.abspath(os.path.join(real_dest, os.path.pardir))

        try:
            if not os.path.exists(par_dir):
                self.logger.debug("Creating boot configuration folder: %s" \
                                  % par_dir)
                os.makedirs(par_dir)
            self.logger.debug("Moving boot configuration file: \n" \
                              "%s -> %s" % (src, real_dest))
            move(src, real_dest)
            if uid is None:
                uid = -1
            if gid is None:
                gid = -1
            self.logger.debug("Setting ownership of %s to: %s:%s" \
                              % (real_dest, uid, gid))
            os.chown(real_dest,
                     getpwnam(uid).pw_uid,
                     getgrnam(gid).gr_gid)
            if mode:
                self.logger.debug("Setting permissions of %s to: %d" \
                                  % (real_dest, mode))
                os.chmod(real_dest, mode)
        except OSError as err:
            raise RuntimeError("Error copying boot configuration files to " \
                                 "target: %s" % str(err))

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class
        """
        self.parse_doc(dry_run)
        self.init_boot_config()
        self.build_default_entries()
        self.build_custom_entries()
        self.install_boot_loader(dry_run)


class SystemBootMenu(BootMenu):
    """ Class for SystemBootMenu checkpoint. Suitable for automatic boot loader
        and boot menu configuration for install applications that install onto
        a physical system device such as gui-install, text install and AI
    """

    def __init__(self, name):
        """ Constructor for class
        """
        super(SystemBootMenu, self).__init__(name)

        # Dictionary for quick lookup of paramaters needed to configure and
        # install the boot loader.
        self.boot_target = dict()
        self.boot_target[BOOT_ENV] = None
        self.boot_target[DEVS] = list()
        self.img_info_title = None

        # Filesystem name of the target boot environment eg.
        # rpool/ROOT/solaris-11-XYZ
        self.target_bootfs = None
        # Convenience reference to the SolarisDiskBootInstance for boot target
        self.target_boot_instance = None
        # Mountpoint of pool toplevel dataset
        self.pool_tld_mount = None

        # iSCSI attributes
        self.iscsi_doc_obj = None
        self.iscsi_boot = False

    def init_boot_config(self, autogen=True):
        """ Instantiates the appropriate bootmgmt.bootConfig subclass object
            for this class
        """
        bc_flags = [bootconfig.BootConfig.BCF_CREATE]
        if autogen:
            bc_flags.append(bootconfig.BootConfig.BCF_AUTOGEN)
        bc_flags = tuple(bc_flags)
        target_be = self.boot_target[BOOT_ENV]
        # If the BE is unmounted for some reason we need to go and mount it.
        if target_be.mountpoint == None:
            tmp_be_mp = tempfile.mkdtemp(dir="/system/volatile",
                                         prefix="be_mount_%s_" \
                                         % (target_be.name))
            self.logger.debug("Mounting BE %s at: %s" % \
                               (target_be.name, tmp_be_mp))
            target_be.mount(tmp_be_mp, dry_run=False)

        # Note that 'platform' tuple is not supplied here since we want to
        # go with the running system arch/firmware, which bootmgmt defaults to.
        self.config = DiskBootConfig(bc_flags,
            rpname=target_be.parent.name,
            tldpath=self.pool_tld_mount,
            zfspath=target_be.mountpoint,
            set_bootfs_on_commit=True)

        # Apply boot timeout property to boot loader.
        try:
            self.config.boot_loader.setprop(BootLoader.PROP_TIMEOUT,
                                            self.boot_timeout)
        except BootmgmtUnsupportedPropertyError:
            self.logger.warning("Boot loader type %s does not support the \
                                'timeout' property. Ignoring." \
                                % self.config.boot_loader.name)

    def _get_x86_console(self):
        """
            Determine X86 console device. Adapted from libict_pymod
            Returns console device found in bootenv.rc, from devprop command,
            or default 'text'.
        """
        osconsole = None
        bootvars = self.target_boot_instance.boot_vars
        osconsole = bootvars.getprop('output-device')
        if osconsole is not None:
            return osconsole

        # get console setting from devprop via. 'console'
        osconsole = self._get_dev_property(propname='console')

        if osconsole is None:
            # get console setting from devprop via. 'output-device'
            osconsole = self._get_dev_property(
                propname='output-device')
            if osconsole == 'screen':
                osconsole = 'text'
        # Set default console value to text
        if osconsole is None or osconsole == '':
            osconsole = 'text'
        return osconsole

    def _get_dev_property(self, propname):
        """
            Internal helper method.
            Retrieves the value of propname reported by devprop(1M)

            Returns: A string value associated with propname or None
        """
        propname_val = None
        cmd = ["/usr/sbin/devprop", "-s", propname]
        p = Popen.check_call(cmd,
            stdout=Popen.STORE,
            stderr=Popen.STORE,
            logger=ILN)
        if p.returncode != 0:
            raise RuntimeError('Error getting device property: %s' \
                               'Exit status=%s' % (cmd, p.stderr))

        result = p.stdout.strip()
        if len(result) > 0:
            propname_val = result
            self.logger.debug("Found device property value for " \
                              "%s: '%s'" % (propname, propname_val))
        else:
            self.logger.debug("No device property value found for %s" \
                             % propname)
        return propname_val

    def _set_firmware_boot_device(self, dry_run):
        """ Set the boot device in the system firmware on SPARC and UEFI64
            This performs no action on BIOS systems, which lack this feature.
        """
        firmware = self.config.boot_loader.firmware

        # Skip on BIOS since it lacks this capability
        if firmware.fw_name == 'bios':
            return

        # XXX Seth
        # Eventually we will use the common firmware.setprop() method to set
        # the boot device on both SPARC and UEFI. For now SPARC still uses our
        # own implementation until implemented in pybootmgmt.

        # SPARC firmware is AKA Open Boot Prom (OBP)
        if firmware.fw_name == 'obp':
            self._set_sparc_prom_boot_device(dry_run)

        elif firmware.fw_name == 'uefi64':
            # Construct boot device path names
            boot_devs = [os.path.join('/dev/dsk', dev) \
                for dev in self.boot_target[DEVS]]

            if dry_run:
                return

            try:
                firmware.setprop(SystemFirmware.PROP_BOOT_DEVICE, boot_devs)
            except BootmgmtPropertyWriteError as bpw:
                # Don't treat this as fatal, the user can manually select the
                # boot device on reboot.
                self.logger.warning("Failed to set UEFI firmware boot " \
                                    "device:\n%s" % str(bpw))

    def _set_sparc_prom_boot_device(self, dry_run):
        """ Set the SPARC boot-device parameter using eeprom.
            If the root pool is mirrored, sets the boot-device parameter as a
            sequence of the devices forming the root pool.
        """
        self.logger.info("Setting openprom boot-device")

        if self.iscsi_boot:
            if not dry_run:
                try:
                    # swap the default boot strings to be 'net disk'
                    cmd = '/usr/sbin/eeprom boot-device="net disk"'
                    run(cmd, shell=True)

                    # add the iscsi OBP options to the network-boot-args
                    cmd = '/usr/sbin/eeprom network-boot-arguments=%s' % \
                          self.iscsi_doc_obj.sparc_obp_boot_string
                    run(cmd, shell=True)

                except CalledProcessError as cpe:
                    # Treat this as non-fatal. It can be manually fixed later
                    # on reboot.
                    self.logger.warning("Failed to set openprom boot-device:")
                    self.logger.warning(str(cpe))
            return

        prom_device = "/dev/openprom"
        # ioctl codes and OPROMMAXPARAM taken from
        # /usr/include/sys/openpromio.h
        oioc = ord('O') << 8

        # Convert devfs path to prom path
        opromdev2promname = oioc | 15
        oprommaxparam = 32768

        boot_devs = [os.path.join('/dev/dsk', dev) \
            for dev in self.boot_target[DEVS]]

        cur_prom_boot_devs = list()
        new_prom_boot_devs = list()
        prom_arg_str = None

        # Get the current boot device(s) using eeprom
        try:
            cmd = ["/usr/sbin/eeprom", "boot-device"]
            p = run(cmd)
            result = p.stdout.replace('boot-device=', '', 1)
            cur_prom_boot_devs = result.split()
        except CalledProcessError as cpe:
            # Treat this as non-fatal. We can still attempt to set the
            # boot-device property.
            self.logger.warning("Error querying openprom boot-device:")
            self.logger.warning(str(cpe))

        self.logger.debug("Opening prom device: %s" % prom_device)
        try:
            with open(prom_device, "r") as prom:
                # Set boot-device as a sequence for mirrored root pools since
                # the OBP will try to boot each successive device specifier
                # in the list until something opens successfully.
                for i, boot_dev in enumerate(boot_devs):
                    self.logger.debug("Boot device %d: %s" % (i, boot_dev))

                    # Set up a mutable array for ioctl to read from and write
                    # to. Standard Python objects are not usable here.
                    # fcntl.ioctl requires a mutable buffer pre-packed with the
                    # correct values (as determined by the device-driver).
                    # In this case,openprom(7D) describes the following C
                    # stucture as defined in <sys.openpromio.h>
                    # struct openpromio {
                    #     uint_t  oprom_size; /* real size of following data */
                    #     union {
                    #         char  b[1];  /* NB: Adjacent, Null terminated */
                    #         int   i;
                    #     } opio_u;
                    # };
                    dev = (boot_dev + "\0").ljust(oprommaxparam)
                    buf = array.array('c', struct.pack('I%ds' % oprommaxparam,
                                      oprommaxparam, dev))

                    # use ioctl to query the prom device.
                    fcntl.ioctl(prom, opromdev2promname, buf, True)

                    # Unpack the mutable array, buf, which
                    # ioctl just wrote into.
                    new_oprom_size, new_dev = struct.unpack(
                        'I%ds' % oprommaxparam,
                        buf)

                    # Device names are a list of null-terminated tokens, with
                    # a double null on the final token.
                    # We use only the first token.
                    prom_name = new_dev.split('\0')[0]
                    new_prom_boot_devs.append(prom_name)
                    self.logger.debug("%s prom device name: %s" \
                                      % (boot_dev, prom_name))
        except StandardError as std:
            # Treat this as non-fatal. It can be manually fixed later
            # on reboot.
            self.logger.warning("Failed to set openprom boot-device " \
                                "parameter:\n%s" % str(std))
            return

        # Append old boot-device list onto new list, filtering out any
        # duplicate device names already in the new list.
        new_prom_boot_devs.extend([d for d in cur_prom_boot_devs if \
                                   d not in new_prom_boot_devs])
        prom_arg_str = " ".join(new_prom_boot_devs)
        cmd = ["/usr/sbin/eeprom", "boot-device=%s" % prom_arg_str]
        if not dry_run:
            try:
                run(cmd)
            except CalledProcessError as cpe:
                # Treat this as non-fatal. It can be manually fixed later
                # on reboot.
                self.logger.warning("Failed to set openprom boot-device:")
                self.logger.warning(str(cpe))

    def _is_target_instance(self, instance):
        """ Returns True if instance is the boot instance we just installed.
            Otherwise returns False
            Inputs:
            - instance: A BootInstance object
        """
        # If not a SolarisDiskBootInstance it's not what we just installed
        if not isinstance(instance, bootconfig.SolarisDiskBootInstance):
            return False
        # If the fstype of the instance is not zfs
        if instance.fstype is not "zfs":
            return False
        # Check the bootfs property to see if it's a match
        if instance.bootfs == self.target_bootfs:
            return True

        return False

    def _ref_target_instance(self, instance):
        """ Trivial internal convenience method that stores a
            reference to the target SolarisDiskBootInstance.
        """
        self.target_boot_instance = instance

    def _set_as_default_instance(self, instance):
        """ Sets instance as the default boot instance in a boot configuration
            Inputs:
            - instance: A BootInstance object
        """
        self.logger.debug("Marking '%s' as the default boot instance" \
                         % instance.title)
        instance.default = True

    def _set_instance_bootenv(self, instance, mountpoint):
        """
            Sets console property for the boot instance in
            bootenv.rc and kernel boot args.
            'console' property is determined from bootenv.rc and
            devprop(1M) values for 'output-device' and 'console'
        """
        # First, bootmgmt needs to read from the bootenv.rc of the BE
        instance.init_from_rootpath(mountpoint)

        curosconsole = instance.boot_vars.getprop('output-device')
        osconsole = self._get_x86_console()

        # Put it in bootenv.rc
        if osconsole is not None and curosconsole != osconsole:
            self.logger.info('Setting console boot device property to %s' \
                             % osconsole)
            instance.boot_vars.setprop(BootLoader.PROP_CONSOLE, osconsole)

        # Detect the gui-install client by checking for it's profile object
        # in the DOC
        gui_prof = self.doc.persistent.get_first_child(name="GUI Install")

        # If the client is gui-install and the console device is a graphical
        # framebuffer, enable the BootLoader splash and happy face boot.
        # Note 'text' below indicates a framebuffer based console, not to
        # be confused with the meaning of BootLoader.PROP_CONSOLE_TEXT
        if osconsole in ['text', 'graphics'] and gui_prof is not None:
            self.logger.info("Enabling happy face boot on boot instance: %s" \
                             % instance.title)
            self.config.boot_loader.setprop(
                BootLoader.PROP_CONSOLE,
                BootLoader.PROP_CONSOLE_GFX)
            instance.kargs = "-B $ZFS-BOOTFS,console=graphics"
        else:
            self.logger.info("Disabling boot loader graphical splash")
            self.config.boot_loader.setprop(
                BootLoader.PROP_CONSOLE,
                BootLoader.PROP_CONSOLE_TEXT)

    def _set_instance_title(self, instance):
        """ Sets the title of instance to match self.boot_title
            Inputs:
            - instance: A BootInstance object
        """
        self.logger.debug("Setting title of boot instance '%s' to '%s'" \
                         % (instance.title, self.boot_title))
        instance.title = self.boot_title

    def _get_rel_file_path(self):
        """
            Returns file system path to the release file.
        """
        return os.path.join(self.boot_target[BOOT_ENV].mountpoint,
                             "etc/release")

    def _parse_doc_target(self, dry_run=False):
        """ Parses the target objects in the DOC to determine the
            installation target device for boot loader installation
        """
        try:
            target = self.doc.get_descendants(Target.DESIRED, Target,
                max_count=1, max_depth=2, not_found_is_err=True)[0]
        except ObjectNotFoundError:
            raise RuntimeError("No desired target element specified")

        # Find the root pool(s).
        root_pools = list()
        for pool in target.get_descendants(class_type=Zpool):
            if pool.is_root:
                root_pools.append(pool)
        if len(root_pools) < 1:
            raise RuntimeError("No desired target Zpool specified")
        root_pool = root_pools[0]
        boot_env = root_pool.get_first_child(class_type=BE)
        if boot_env is None:
            raise RuntimeError("No BE specified in Target.Desired tree")
        self.boot_target[BOOT_ENV] = boot_env

        # If dry_run is True, the target BE might not exist so only bail out
        # if not a dry run.
        result = be_list(boot_env.name)
        if len(result) != 1:
            if dry_run == False:
                raise RuntimeError("Target BE \'%s\' does not exist" \
                                      % (boot_env.name))
        else:
            self.target_bootfs = result[0][2]

        # Get root pool's top level filesystem mountpoint
        pool = boot_env.parent
        if pool.mountpoint:
            self.pool_tld_mount = pool.mountpoint
        # If mountpoint not defined by the zpool, look at its datasets
        # for one with the same name as the zpool.
        if self.pool_tld_mount is None:
            for filesystem in pool.filesystems:
                if filesystem.name == pool.name:
                    self.pool_tld_mount = filesystem.get("mountpoint")
                    break
        # If no top level dataset definition exists then assume default zfs
        # behaviour for pool top level dataset mount point as '/<pool.name>'
        if self.pool_tld_mount is None:
            self.pool_tld_mount = os.path.join('/', pool.name)

        if not os.path.exists(self.pool_tld_mount):
            raise RuntimeError("Expected mountpoint \'%s\' of top level" \
                               "fileystem \'%s\' does not exist!" \
                               % (pool.name, self.pool_tld_mount))

        # Look for an Iscsi DOC object
        iscsi_check = self.doc.get_descendants(class_type=Iscsi)
        if iscsi_check:
            self.iscsi_doc_obj = iscsi_check[0]

        # Figure out the boot device names in ctd notation
        for disk in target.get_children(class_type=Disk):
            if disk.whole_disk and disk.label == "GPT":
                # extract the vdevs from the root pool and extend the
                # boot_target list
                vdevs = _get_vdev_mapping(root_pool.name)
                for entry in vdevs.values():
                    for vdev in entry:
                        if vdev.startswith('/dev/dsk/'):
                            vdev = vdev.lstrip('/dev/dsk/')
                        self.boot_target[DEVS].append(vdev)

                if self.iscsi_doc_obj and \
                   disk.ctd in self.iscsi_doc_obj.ctd_list:
                    # For the whole disk case, slice 0 will contain 99% of the
                    # disk so use that.  Since this is an OBP setting, it must
                    # be done by letter.  s0 = 'a'
                    self.iscsi_boot = True
                    self.iscsi_doc_obj.sparc_slice = "a"

                    # verify the LUN and target name are set
                    if self.iscsi_doc_obj.target_lun is None:
                        self.iscsi_doc_obj.target_lun = \
                            self.iscsi_doc_obj.iscsi_dict[disk.ctd].lun_num

                    if self.iscsi_doc_obj.target_name is None:
                        self.iscsi_doc_obj.target_name = \
                            self.iscsi_doc_obj.iscsi_dict[disk.ctd].target_name
                break

            # Look for either GPT partitions or slices that are in the boot/
            # root pool and store their ctd device names.
            # node(s) refers to one or the other type within the context
            # of each disk.
            nodes = disk.get_children(class_type=GPTPartition)
            if not nodes:
                nodes = disk.get_descendants(class_type=Slice, max_depth=2)
            boot_nodes = [node for node in nodes if \
                          node.in_zpool == root_pool.name]
            bdevs = ['%ss%s' % (disk.ctd, node.name) for node in boot_nodes]
            self.boot_target[DEVS].extend(bdevs)

            if self.iscsi_doc_obj and disk.ctd in self.iscsi_doc_obj.ctd_list:
                self.iscsi_boot = True

                # set the sparc slice.  Since this is an OBP setting, it must
                # be done by letter.  s0 = 'a', s1 = 'b', etc.
                self.iscsi_doc_obj.sparc_slice = \
                    chr(97 + int(boot_nodes[0].name))

                # verify the LUN and target name are set
                if self.iscsi_doc_obj.target_lun is None:
                    self.iscsi_doc_obj.target_lun = \
                        self.iscsi_doc_obj.iscsi_dict[disk.ctd].lun_num

                if self.iscsi_doc_obj.target_name is None:
                    self.iscsi_doc_obj.target_name = \
                        self.iscsi_doc_obj.iscsi_dict[disk.ctd].target_name

        if not self.boot_target[DEVS]:
            raise RuntimeError("Could not find any boot devices to " \
                               "install the boot loader onto.")

        title_line = linecache.getline(self._get_rel_file_path(), 1)
        self.rel_file_title = title_line.strip()
        # Set an initial boot_title value. It can be overwritten later by the
        # .image_info file GRUB_TITLE value or the BootMods tree of the DOC.
        self.boot_title = self.rel_file_title

        # On X86 systems, set boot title according to "GRUB_TITLE" keyword
        # of the .image_info file, if defined.
        if self.arch == 'sparc':
            return
        try:
            self.img_info_title = get_image_grub_title(
                self.logger,
                image_info_file=self.img_info_path)
        # get_image_grub_title() will raise CalledProcessError if not
        # booted from installation media so suppress it if dry_run == True
        except CalledProcessError as cpe:
            if dry_run == False:
                raise cpe

        if self.img_info_title is not None:
            self.logger.debug("Setting boot title to image info value: %s" \
                % self.img_info_title)
            self.boot_title = self.img_info_title

    def build_default_entries(self):
        """ Method for constructing the default entries list.
            When installing onto physical target systems, the list of entries
            is autogenerated based on discovery routines within bootmgmt.
            The discovered entries should already be present from the
            invocation of init_boot_config() so the only remaining tasks here
            are to set the new boot environment as the default boot instance
            and the console properties on X86.
        """
        # Find the boot environment (BE) we just installed and
        # make it the default boot instance
        self.config.modify_boot_instance(self._is_target_instance,
                                         self._ref_target_instance)
        self._set_as_default_instance(self.target_boot_instance)
        # Set its boot title
        self._set_instance_title(self.target_boot_instance)
        # Set up bootenv.rc console properties and
        # happy face boot on the target instance
        if self.arch == 'i386':
            self._set_instance_bootenv(
                instance=self.target_boot_instance,
                mountpoint=self.boot_target[BOOT_ENV].mountpoint)

    def build_custom_entries(self):
        """ Currently only consumed by AI installer app. GUI & Text do not
            consume a manifest XML file.
        """
        for entry in self.boot_entry_list:
            instance = \
                SolarisDiskBootInstance(self.boot_target[BOOT_ENV].mountpoint,
                                        fstype='zfs',
                                        bootfs=self.target_bootfs)
            instance.title = self.boot_title + \
                             " " + entry.title_suffix
            if entry.default_entry:
                instance.default = True
            else:
                instance.default = False
            instance.kargs = entry.kernel_args

            if entry.insert_at == "start":
                where = 0
            else:
                where = -1
            self.logger.info("Adding custom boot entry: \'%s\'" \
                             % instance.title)
            self.config.add_boot_instance(instance, where)

    def install_boot_loader(self, dry_run=False):
        """ Install the boot loader and associated boot
            configuration files
        """
        if not self.boot_target[DEVS]:
            raise RuntimeError("No boot devices identified!")

        boot_rdevs = [os.path.join('/dev/rdsk', dev) \
            for dev in self.boot_target[DEVS]]

        if dry_run == True:
            # Write boot config to a temporary directory instead of to
            # a physical target
            temp_dir = \
                tempfile.mkdtemp(dir="/tmp", prefix="boot_config_")
            # Add dictionary mappings for tokens that commit_boot_config()
            # might return.
            self.boot_tokens[DiskBootConfig.TOKEN_ZFS_RPOOL_TOP_DATASET] = \
                self.pool_tld_mount
            self.boot_tokens[BootConfig.TOKEN_SYSTEMROOT] = \
                self.boot_target[BOOT_ENV].mountpoint
            self.logger.info("Installing boot loader configuration files to: \
                             %s" % (temp_dir))
            boot_config_list = \
                self.config.commit_boot_config(temp_dir, None)
            self._handle_boot_config_list(boot_config_list, dry_run)
        else:
            # Check to make sure that an installation attempt is not
            # executed on a live system
            if self.boot_target[BOOT_ENV].mountpoint == '/':
                raise RuntimeError("Boot checkpoint can not be executed on " \
                                     "a live system except with dry run mode")
            # XXX Seth: Pybootmgmt ought to be creating this directory tree
            # when doing a physical boot loader installation onto the disk.
            # While it's being fixed, create the directories ourselves to
            # make legacy Grub installation work.
            if not dry_run and self.config.boot_loader.name == "Legacy GRUB":
                grub_dir = os.path.join(self.pool_tld_mount, "boot", "grub")
                if not os.path.exists(grub_dir):
                    self.logger.info("Creating Legacy GRUB config directory:" \
                                     "\n\t%s" % (grub_dir))
                    os.makedirs(grub_dir, 0755)

            # Danger Will Robinson!!
            self.logger.info("Installing boot loader to devices: %s" \
                             % str(boot_rdevs))
            # NOTE: Use the force (haha) option to force installation of the
            # boot loader onto a disk that may have a versioned boot loader
            # already installed.
            self.config.commit_boot_config(boot_devices=boot_rdevs,
                                           force=True)

            self.logger.info("Setting boot devices in firmware")
            self._set_firmware_boot_device(dry_run)

        if dry_run:
            rmtree(temp_dir)


class ISOImageBootMenu(BootMenu):
    """ Abstract base class for ISOImageBootMenu checkpoint
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, name):
        """ Constructor for class
        """
        super(ISOImageBootMenu, self).__init__(name)
        self.ba_build = None
        self.dc_dict = dict()
        self.dc_pers_dict = dict()
        self.pkg_img_path = None
        self.tmp_dir = None

    def init_boot_config(self, autogen=True):
        """ Instantiates the appropriate bootmgmt.bootConfig subclass object
            for this class
        """
        bc_flags = (bootconfig.BootConfig.BCF_CREATE,
                    bootconfig.BootConfig.BCF_ONESHOT)
        self.config = ODDBootConfig(bc_flags,
                                    oddimage_root=self.pkg_img_path)

        # Inspect boot loader to determine if it can support creation of a
        # hybrid BIOS/UEFI bootable ISO image.
        try:
            self.config.boot_loader.setprop(BootLoader.PROP_BOOT_TARGS,
                                            ['bios', 'uefi64'])
        except BootmgmtUnsupportedPlatformError:
            self.logger.warning("Boot loader '%s' does not support both " \
                "BIOS and UEFI64 platforms." % (self.config.boot_loader.name))

        fw_targs = self.config.boot_loader.getprop(BootLoader.PROP_BOOT_TARGS)
        if isinstance(fw_targs, str):
            fw_targs = [fw_targs]
        self.logger.info("Creating ISO boot configuration for firmware " \
                         "targets: " + ', '.join(fw_targs))

        # Apply boot timeout property to boot loader.
        try:
            self.config.boot_loader.setprop(BootLoader.PROP_TIMEOUT,
                                            self.boot_timeout)
        except BootmgmtUnsupportedPropertyError:
            self.logger.warning("Boot loader type %s does not support the \
                'timeout' property. Ignoring." \
                % self.config.boot_loader.name)

        # Apply ident file property if required by boot loader:
        # GRUB2 requires this file, Legacy GRUB doesn't. No big deal
        if BootLoader.PROP_IDENT_FILE in \
            self.config.boot_loader.SUPPORTED_PROPS:
            # read .volsetid and derive a unique ident file name from it
            vpath = os.path.join(self.ba_build, ".volsetid")
            with open(vpath, "r") as vpath_fh:
                volsetid = vpath_fh.read().strip()

            identfile = "." + volsetid
            identpath = os.path.join(self.pkg_img_path, identfile)
            self.logger.info("Boot loader unique ident file name: %s" \
                             % identfile)
            with open(identpath, "a+") as identf:
                identf.write("# This file identifies the image root for GRUB2")

            self.config.boot_loader.setprop(BootLoader.PROP_IDENT_FILE,
                                            "/" + identfile)

    def _get_rel_file_path(self):
        """
            Returns file system path to the release file.
        """
        return os.path.join(self.pkg_img_path, "etc/release")

    def _add_chainloader_entry(self):
        """ Adds a chainloader entry to the boot configuration.
        """
        instance = ChainDiskBootInstance(chaininfo=tuple([0]))
        instance.title = "Boot from Hard Disk"
        self.config.add_boot_instance(instance)

    def build_custom_entries(self):
        """ Add custom defined boot entries from the manifest XML
        """
        for entry in self.boot_entry_list:
            instance = SolarisODDBootInstance(self.pkg_img_path)
            instance.title = self.boot_title + " " + entry.title_suffix
            # The last boot entry in the list tagged as the default boot entry
            # overrides the previous default if more than one is tagged as
            # the default.
            if entry.default_entry:
                instance.default = True
            else:
                instance.default = False
            instance.kargs = entry.kernel_args
            if entry.insert_at == "start":
                where = 0
            else:
                where = -1
            self.config.add_boot_instance(instance, where)

    def _parse_doc_target(self, dry_run=False):
        """ Class method for parsing data object cache (DOC) objects for use by
            the checkpoint.
        """
        try:
            self.dc_pers_dict = self.doc.persistent.get_children(
                name=DC_PERS_LABEL,
                class_type=DataObjectDict,
                not_found_is_err=True)[0].data_dict
        except ObjectNotFoundError:
            pass

        self.dc_dict = self.doc.volatile.get_children(name=DC_LABEL,
            class_type=DataObjectDict,
            not_found_is_err=True)[0].data_dict

        try:
            self.ba_build = self.dc_dict["ba_build"]
            self.pkg_img_path = self.dc_dict["pkg_img_path"]
            self.tmp_dir = self.dc_dict["tmp_dir"]
        except KeyError, msg:
            raise RuntimeError("Error retrieving a value from the DOC: " + \
                str(msg))
        self.img_info_path = os.path.join(self.pkg_img_path, ".image_info")

        title_line = linecache.getline(self._get_rel_file_path(), 1)
        self.rel_file_title = title_line.strip()
        # Set an initial boot_title value. It can be overwritten later when
        # parsing the BootMods tree of the DOC
        self.boot_title = self.rel_file_title

    def _prepare_usb_boot(self, dry_run=False):
        """ Creates an embeddable boot image for GRUB2 based USB boot media
        """
        # Return if this is not GRUB2
        if self.config.boot_loader.name != "GRUB2":
            return

        self.logger.info("Preparing MBR embedded GRUB2 boot image for USB")

        # Create a nice big 10MB lofi file.
        imagesize = (10 * MB)
        imagename = os.path.join(self.tmp_dir, "mbr_embedded_grub2")

        with open(imagename, 'w') as imagefile:
            imagefile.seek(imagesize - 1)
            imagefile.write('\0')

        if not dry_run:
            # Create the lofi device
            lofi_dev = None
            lofi_rdev = None
            cmd = [LOFIADM, "-a", imagename]
            try:
                p = run(cmd)
                lofi_dev = p.stdout.strip()
                lofi_rdev = lofi_dev.replace("lofi", "rlofi")

                uefi_image_size = os.stat(self._uefi_image_name).st_size
                self.logger.debug("EFI system partition image: %s",
                                  self._uefi_image_name)

                # write the uefi.img to the lofi character dev at 1MB offset
                # in 1KB increments, instead of allocating one giant buffer.
                self.logger.debug("Writing EFI system partition image to: %s",
                                  lofi_rdev)
                with open(self._uefi_image_name, 'r') as src:
                    with open(lofi_rdev, 'w') as dst:
                        dst.seek(MB)
                        for i in range(uefi_image_size / KB):
                            dst.write(src.read(KB))
                        tail = uefi_image_size % KB
                        if tail > 0:
                            dst.write(src.read(tail))

                # Write out an fdisk table. We don't use the standard install
                # target modules because we want precise control over the
                # geometry, plus it's not well suited to lofi devices.
                # Layout:
                # - type ESP, active, at 1M offset,
                # - partition size = uefi_image size
                # The ESP is marked active, because despite the fact that we
                # write GRUB to the MBR, some BIOSes are brain dead and won't
                # boot USB media without an active DOS partition.
                esptype = Partition.name_to_num("EFI System")
                startblock = MB / BLOCKSIZE
                uefi_image_nblocks = uefi_image_size / BLOCKSIZE
                fdiskentry = "%d:128:0:0:0:0:0:0:%d:%d" \
                             % (esptype, startblock, uefi_image_nblocks)
                self.logger.debug("Creating fdisk table on %s:\n\t%s",
                                  lofi_rdev, fdiskentry)
                cmd = [FDISK, "-A", fdiskentry, lofi_rdev]
                run(cmd)

                # Install the BIOS grub2 core image in the MBR of the lofi dev
                self.logger.debug("Installing GRUB2 on %s", lofi_rdev)
                bios_grub_dir = os.path.join(self.pkg_img_path,
                                             "boot/grub/i386-pc")
                cmd = [GRUB_SETUP, "-d", bios_grub_dir,
                       "--root-device=(hostdisk/" + lofi_rdev + ")",
                       "-M", lofi_rdev]
                run(cmd)

                # Write the first 1MB of the lofi image out to file and store
                # it in the pkg_img area for inclusion in the ISO
                usb_image_name = os.path.join(self.pkg_img_path,
                                              MBR_IMG_RPATH)
                self.logger.debug("Writing GRUB2 MBR image to: %s",
                                  usb_image_name)
                with open(lofi_rdev, 'r') as src:
                    with open(usb_image_name, 'w') as dst:
                        for i in range(KB):
                            dst.write(src.read(KB))
            finally:
                # remove the lofi device
                if lofi_dev is not None:
                    cmd = [LOFIADM, "-d", lofi_dev]
                    run(cmd)

            # Remove the backing file for the lofi image
            os.unlink(imagename)
            self.logger.info("MBR embedded GRUB2 boot image complete")

    def execute(self, dry_run=False):
        """ Primary execution method used by the Checkpoint parent class
        """
        self.logger.info("=== Executing Boot Loader Setup Checkpoint ===")
        super(ISOImageBootMenu, self).execute(dry_run)
        self.update_img_info_path()
        self._prepare_usb_boot(dry_run)

    def install_boot_loader(self, dry_run=False):
        """ Install the boot loader and associated boot configuration files.
        """
        if dry_run == True:
            temp_dir = \
                tempfile.mkdtemp(dir="/tmp", prefix="iso_boot_config_")
        else:
            temp_dir = self.pkg_img_path

        # Add dictionary mappings for tokens that commit_boot_config() might
        # return.
        self.boot_tokens[BootConfig.TOKEN_SYSTEMROOT] = self.pkg_img_path
        self.boot_tokens[ODDBootConfig.TOKEN_ODD_ROOT] = self.pkg_img_path

        self.logger.debug("Writing boot configuration to %s" % (temp_dir))
        boot_config_list = self.config.commit_boot_config(temp_dir, None)
        self._handle_boot_config_list(boot_config_list, dry_run)
        if dry_run:
            rmtree(temp_dir)

    def update_img_info_path(self):
        """ Method to write out the .img_info_path file.
        """
        self.logger.info("Updating %s" % self.img_info_path)

        # Write out the GRUB_TITLE line
        with open(self.img_info_path, "a+") as iip:
            try:
                iip.write("GRUB_TITLE=" + self.boot_title)
            except IOError, msg:
                raise RuntimeError(msg)

    def _handle_iso_boot_image_type(self, config, dry_run):
        """ Method that copies ISO El Torito and HSFS bootblockimage file types
            to their appropriate targets.
        """

        # XXX: Add in key/val pair to handle the SPARC HSFS BOOTBLK
        # type here when pybootmgmt supports this firmware type.
        # For now just it just does BIOS & UEFI ELTORITO.
        eltorito_dict = {
            BootConfig.OUTPUT_TYPE_BIOS_ELTORITO: \
                ("bios-eltorito-img", "BIOS"),
            BootConfig.OUTPUT_TYPE_UEFI_ELTORITO: \
                ("uefi-eltorito-img", "UEFI")
        }

        # Store the ISO boot image path in DC's dictionary for later use
        # when constructing the ISO image
        img_type = config[0]
        src = config[1]
        if config[3] is None:
            dst = src
        else:
            dst = config[3] % self.boot_tokens

        img_val = eltorito_dict.get(img_type)
        if img_val is None:
            raise RuntimeError("Unrecognised ISO boot loader image type: %s" \
                               % img_type)
        else:
            img_id, firmware_id = img_val

        if not os.path.exists(src):
            raise RuntimeError("Expected  boot image type \'%s\' does not " \
                               "exist at path: %s" % (img_type, src))

        # Keep a reference to the full path name of the UEFI image. We need it
        # later to set up USB boot.
        if img_type == BootConfig.OUTPUT_TYPE_UEFI_ELTORITO:
            self._uefi_image_name = dst
        if dry_run is True:
            self.logger.debug("Deleting El Torito image: %s" % src)
            os.unlink(src)
            return

        if not os.path.abspath(src).startswith(self.pkg_img_path):
            raise RuntimeError("El Torito boot image \'%s\' mislocated "
                               "outside of image root: %s" \
                               % (src, self.pkg_img_path))
        if src != dst:
            os.rename(src, dst)
        if self.dc_pers_dict:
            self.doc.persistent.delete_children(name=DC_PERS_LABEL)

        # Strip out the pkg_img_path prefix from dst. Otherwise
        # mkisofs will choke because it requires a relative rather
        # than an absolute path for the eltorito image argument
        self.dc_pers_dict[img_id] = \
            dst.split(self.pkg_img_path + os.sep)[1]
        self.doc.persistent.insert_children(
            DataObjectDict(DC_PERS_LABEL,
            self.dc_pers_dict, generate_xml=True))

        self.logger.info("%s El Torito boot image name: %s" \
                         % (firmware_id, self.dc_pers_dict[img_id]))


class AIISOImageBootMenu(ISOImageBootMenu):
    """ Class for AIISOImageBootMenu checkpoint.
        Used by Distro Constructor for creation of Automated Install ISO image.
    """

    def __init__(self, name, arg=None):
        """ Constructor for class
        """
        super(AIISOImageBootMenu, self).__init__(name)
        self.installadm_entry = None
        if arg:
            self.__setup(**arg)
        else:
            self.__setup()

    def __setup(self, installadm_entry="boot image"):
        """ Setup checkpoint with any kwargs in manifest XML
        """
        self.installadm_entry = installadm_entry

    def init_boot_config(self, autogen=True):
        """ Instantiates the appropriate bootmgmt.bootConfig subclass object
            for AI
        """
        super(AIISOImageBootMenu, self).init_boot_config(autogen)
        # AI specific global bootloader configuration:
        # - Disable graphical boot splash
        self.config.boot_loader.setprop(
            BootLoader.PROP_CONSOLE,
            BootLoader.PROP_CONSOLE_TEXT)

    def build_default_entries(self):
        """ Constructs the default boot entries and inserts them into the
            bootConfig object's boot_instances list
        """
        ai_titles = [self.boot_title + " Automated Install custom",
                     self.boot_title + " Automated Install",
                     self.boot_title + " Automated Install custom ttya",
                     self.boot_title + " Automated Install custom ttyb",
                     self.boot_title + " Automated Install ttya",
                     self.boot_title + " Automated Install ttyb"]
        ai_kargs = ["-B install=true,aimanifest=prompt",
                    "-B install=true",
                    "-B install=true,aimanifest=prompt,console=ttya",
                    "-B install=true,aimanifest=prompt,console=ttyb",
                    "-B install=true,console=ttya",
                    "-B install=true,console=ttyb"]
        for i, title in enumerate(ai_titles):
            instance = SolarisODDBootInstance(self.pkg_img_path)
            instance.title = title
            # Make the first entry the default
            if i == 0:
                instance.default = True
            instance.kargs = ai_kargs[i]
            self.config.add_boot_instance(instance)

        # Create a chainloader boot from HD entry
        self._add_chainloader_entry()

    def update_img_info_path(self):
        """ Method to write out the .img_info_path file.
        """
        self.logger.info("Updating %s" % self.img_info_path)

        # write out the GRUB_TITLE line
        with open(self.img_info_path, "a+") as iip:
            try:
                iip.write("GRUB_TITLE=" + self.boot_title + "\n")
                iip.write("GRUB_MIN_MEM64=0\n")
                iip.write("GRUB_DO_SAFE_DEFAULT=true\n")
                iip.write("NO_INSTALL_GRUB_TITLE=%s\n" % self.installadm_entry)
            except IOError, msg:
                raise RuntimeError(msg)


class LiveCDISOImageBootMenu(ISOImageBootMenu):
    """ Class for LiveCDISOImageBootMenu checkpoint.
        Used by Distro Constructor for creation of LiveCD
        ISO image.
    """

    def __init__(self, name):
        """ Constructor for class
        """
        super(LiveCDISOImageBootMenu, self).__init__(name)

    def init_boot_config(self, autogen=True):
        """ Instantiates the appropriate bootmgmt.bootConfig subclass object
            for LiveCD
        """
        super(LiveCDISOImageBootMenu, self).init_boot_config(autogen)
        # LiveCD specific global bootloader configuration:
        # - Enable graphical boot splash
        self.config.boot_loader.setprop(
            BootLoader.PROP_CONSOLE,
            BootLoader.PROP_CONSOLE_GFX)

    def build_default_entries(self):
        """ Constructs the default boot entries and inserts them into the
            bootConfig object's boot_instances list
        """
        # create lists of boot titles and kernel args to use
        lcd_titles = [self.boot_title,
                      self.boot_title + " VESA driver",
                      self.boot_title + " text console",
                      self.boot_title + " Enable SSH"]
        lcd_kargs = [None,
                     "-B livemode=vesa",
                     "-B livemode=text",
                     "-B livessh=enable"]
        for i, title in enumerate(lcd_titles):
            instance = SolarisODDBootInstance(self.pkg_img_path)
            instance.title = title
            # Make the first entry the default
            if i == 0:
                instance.default = True
            instance.kargs = lcd_kargs[i]
            self.config.add_boot_instance(instance)

        # Create a chainloader boot from HD entry
        self._add_chainloader_entry()


class TextISOImageBootMenu(ISOImageBootMenu):
    """ Class for TextISOImageBootMenu checkpoint.
        Used by Distro Constructor for creation of Text installer ISO image.
    """

    DEFAULT_TIMEOUT = 5

    def __init__(self, name):
        """ Constructor for class
        """
        super(TextISOImageBootMenu, self).__init__(name)
        self.boot_timeout = TextISOImageBootMenu.DEFAULT_TIMEOUT

    def init_boot_config(self, autogen=True):
        """ Instantiates the appropriate bootmgmt.bootConfig subclass object
            for Text Install
        """
        super(TextISOImageBootMenu, self).init_boot_config(autogen)
        # Text Install Specific global bootloader configuration:
        # - Hide the boot menu.
        # - Disable graphical boot splash
        self.config.boot_loader.setprop(BootLoader.PROP_QUIET, True)
        self.config.boot_loader.setprop(
            BootLoader.PROP_CONSOLE,
            BootLoader.PROP_CONSOLE_TEXT)

    def build_default_entries(self):
        """ Constructs the default boot entries and inserts them into the
            bootConfig object's boot_instances list
        """
        ti_titles = [self.boot_title,
                     self.boot_title + " ttya",
                     self.boot_title + " ttyb"]
        ti_kargs = [None,
                    "-B console=ttya",
                    "-B console=ttyb"]
        for i, title in enumerate(ti_titles):
            instance = SolarisODDBootInstance(self.pkg_img_path)
            instance.title = title
            # Make the first entry the default
            if i == 0:
                instance.default = True
            instance.kargs = ti_kargs[i]
            self.config.add_boot_instance(instance)

        # Create a chainloader boot from HD entry
        self._add_chainloader_entry()
