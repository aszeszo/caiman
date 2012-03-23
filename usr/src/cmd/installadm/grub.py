#!/usr/bin/python2.6
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
'''
Classes and functions supporting creating and modifying bootmgmt
configuration files
'''
import logging
import os
from grp import getgrnam
from pwd import getpwnam

import osol_install.auto_install.installadm_common as com

from bootmgmt import BootmgmtUnsupportedPropertyError
from bootmgmt.bootconfig import BootConfig, NetBootConfig, \
    SolarisNetBootInstance
from bootmgmt.bootloader import BootLoader
from osol_install.auto_install.installadm_common import XDEBUG

MENULST = 'menu.lst'

# NBP_TYPE values come from RFC 4578
NBP_TYPE = {'0000': 'bios', '0007': 'uefi'}


class GrubError(StandardError):
    '''Base class for errors unique to grub module'''
    pass


def update_boot_instance_svcname(boot_instance, oldname, newname):
    '''Update the svcname/mountdir in a boot_instance

     Input:
        boot_instance - boot_instance to update
        oldname - current svcname
        newname - replacement svcname
     Returns: updated boot_instance

    '''
    logging.log(XDEBUG, 'in update_boot_instance_svcname %s %s',
                oldname, newname)
    kernel = boot_instance.kernel
    boot_instance.kernel = update_kernel_ba_svcname(kernel, oldname, newname)

    boot_archive = boot_instance.boot_archive
    boot_instance.boot_archive = update_kernel_ba_svcname(boot_archive,
        oldname, newname)

    kargs = boot_instance.kargs
    boot_instance.kargs = update_kargs_install_service(kargs, oldname, newname)
    return boot_instance


def update_kargs_install_service(current_kargs, oldsvcname, newsvcname):
    '''Update install_service in kargs string

     Input:
        current_kargs - current value of kargs string to update
        oldsvcname - current svcname
        newsvcname - replacement svcname
     Returns: updated kargs string

    '''
    logging.log(XDEBUG, 'in update_kargs_install_service current_kargs=%s '
                'oldsvcname=%s newsvcname=%s', current_kargs,
                oldsvcname, newsvcname)

    new_kargs = current_kargs
    install_svc = 'install_service='
    parts = current_kargs.partition(install_svc)
    if parts[1]:
        ending = parts[2].partition(',')[2]
        new_kargs = parts[0] + install_svc + newsvcname + ',' + ending
    return(new_kargs)


def update_kernel_ba_svcname(current_string, oldsvcname, newsvcname):
    '''Update the svcname/mountdir in kernel or boot_archive string

     Input:
        current_string - current value of string to update
        oldsvcname - current svcname
        newsvcname - replacement svcname
     Returns: updated string

    '''
    logging.log(XDEBUG, 'in update_kernel_ba_svcname %s %s %s',
                current_string, oldsvcname, newsvcname)
    new_string = current_string
    parts = current_string.partition(oldsvcname)
    if parts[1]:
        new_string = parts[0] + newsvcname + parts[2]
    return new_string


def update_kargs_bootargs(current_kargs, oldbootargs, newbootargs):
    '''Update bootargs in kargs string

     Input:
        current_kargs - current value of kargs string to update
        oldbootargs - bootargs to replace
        newbootargs - replacement bootargs
     Returns: updated kargs string

    '''
    logging.log(XDEBUG, 'in update_kargs_bootargs current_kargs=%s '
                'oldbootargs=%s newbootargs=%s', current_kargs,
                oldbootargs, newbootargs)

    newbootargs = newbootargs.strip()
    parts = current_kargs.partition('-B')
    if not parts[1]:
        return current_kargs
    ending = parts[2].lstrip()
    # Need to check for oldbootargs because '' is
    # a valid value
    if oldbootargs and oldbootargs in ending:
        ending = ending.replace(oldbootargs, newbootargs)
    else:
        ending = newbootargs + ending
    return(parts[0] + '-B ' + ending)


def update_kargs_imagepath(current_kargs, oldpath, newpath):
    '''Update imagepath in kargs string

     Input:
        current_kargs - current value of kargs string to update
        oldpath - imagepath to replace
        newpath - new imagepath
     Returns: updated kargs string

    '''
    logging.log(XDEBUG, 'in update_kargs_imagepath current_kargs=%s '
                'oldpath=%s newpath=%s', current_kargs, oldpath, newpath)

    install_media = 'install_media='
    parts = current_kargs.partition(install_media)

    # Example line (spaces added for readability):
    #   -B install_media=http://$serverIP:5555//export/auto_install/myimg,
    #      install_service=mysvc,install_svc_address=$serverIP:5555

    if not parts[1]:
        return current_kargs

    # The line contains 'install_media='.
    # parts[2] is:
    #   http://$serverIP:5555//export/auto_install/myimg,
    #      install_service=mysvc,install_svc_address=$serverIP:5555
    ending_parts = parts[2].partition(',')
    media_str = ending_parts[0]
    #   http://$serverIP:5555//export/auto_install/myimg

    rest_of_string = ending_parts[1] + ending_parts[2]
    #   ,install_service=mysvc,install_svc_address=$serverIP:5555

    new_media_str = media_str.replace(oldpath, newpath, 1)
    #   http://$serverIP:5555//foo/newpath

    new_kargs = parts[0] + install_media + new_media_str + rest_of_string
    #   kernel$ /mysvc/platform/i86pc/kernel/$ISADIR/unix -B
    #      install_media=http://$serverIP:5555//foo/newpath,
    #      install_service=mysvc,install_svc_address=$serverIP:5555

    return new_kargs


def set_perms(filename, uid, gid, mode):
    '''Update permissions of a file'''
    logging.debug("Setting ownership of %s to: %s:%s", filename, uid, gid)
    os.chown(filename, getpwnam(uid).pw_uid, getgrnam(gid).gr_gid)
    if mode:
        logging.debug("Setting permissions of %s to: %d", filename, mode)
        os.chmod(filename, mode)


class AIGrubCfg(object):
    '''AIGrubCfg interacts with the bootmgmt classes to create and
    modify the AI boot related service configuration files.
    '''

    def __init__(self, name, path=None, image_info=None, srv_address=None,
                 config_dir=None, bootargs=None):
        '''Constructor for class
        Input:
            name - service name
            path - image path for service
            image_info - dict of image info
            srv_address - srv_address from AIService
            config_dir - service config dir (/var/ai/service/<svcname>)
            bootargs - string of user specified bootargs or '' if none

        '''
        # Used for string token substitution of pybootgmmt return data
        self.boot_tokens = dict()
        self.netbc = None
        self.svcname = name
        self.img_path = path
        self.image_info = image_info
        self.srv_address = srv_address
        self.svc_config_dir = config_dir
        self.bootargs = bootargs
        self.tftp_subdir = '/' + name
        self.mac_address = None

    def setup_grub(self):
        '''Setup grub files'''
        self.init_netboot_config()
        self.build_default_entries()
        netconfig_files, config_files, boot_tuples = self.handle_boot_config()

        logging.debug('setup_grub returning:\n  netconfig_files: %s\n  '
                      'config_files: %s\n  boot_tuples: %s',
                      netconfig_files, config_files, boot_tuples)
        return (netconfig_files, config_files, boot_tuples)

    def init_netboot_config(self):
        '''Instantiates the bootmgmt.bootConfig.NetBootConfig subclass
           object for this class
        '''
        logging.debug('in init_boot_config')
        self.netbc = NetBootConfig([BootConfig.BCF_CREATE],
            platform=('x86', None),
            osimage_root=self.img_path,
            data_root=self.svc_config_dir,
            tftproot_subdir=self.tftp_subdir)

        # Set props to disable graphical boot splash, apply boot timeout
        # property to boot loader, and set min_mem64.
        propdict = {BootLoader.PROP_CONSOLE: BootLoader.PROP_CONSOLE_TEXT}
        if "grub_min_mem64" in self.image_info:
            minmem64 = self.image_info["grub_min_mem64"]
            propdict[BootLoader.PROP_MINMEM64] = minmem64
        for key in propdict:
            try:
                self.netbc.boot_loader.setprop(key, propdict[key])
            except BootmgmtUnsupportedPropertyError:
                logging.debug("Boot loader type '%s' does not support the "
                              "'%s' property. Ignoring.",
                              self.netbc.boot_loader.name, key)

    def build_default_entries(self):
        '''Construct the default boot entries and insert them into the
           NetBootConfig object's boot_instances list
        '''
        logging.debug('in build_default_entries')

        # Create net boot instance for Text Installer
        ti_title = self.image_info.get("no_install_grub_title",
                                       "Text Installer and command line")
        ti_nbi = SolarisNetBootInstance(None, platform='x86', title=ti_title)

        # Modify kernel and boot_archive lines if 32 bit
        unix_32bit = 'platform/i86pc/kernel/unix'
        if os.path.exists(os.path.join(self.img_path, unix_32bit)):
            ti_nbi.kernel = '/platform/i86pc/kernel/%(karch)s/unix'
            ti_nbi.boot_archive = '/platform/i86pc/%(karch)s/boot_archive'

        # prepend kernel and boot_archive lines with /<svcname>
        ti_nbi.kernel = '/' + self.svcname + ti_nbi.kernel
        ti_nbi.boot_archive = '/' + self.svcname + ti_nbi.boot_archive
        ti_nbi.kargs = ("-B %sinstall_media=http://%s/%s,install_service=%s,"
                        "install_svc_address=%s" %
                        (self.bootargs, self.srv_address, self.img_path,
                        self.svcname, self.srv_address))
        self.netbc.add_boot_instance(ti_nbi)

        # Create net boot instance for AI
        ai_title = self.image_info.get("grub_title",
            "Solaris " + self.svcname) + ' Automated Install'
        ai_nbi = SolarisNetBootInstance(None, platform='x86', title=ai_title)
        ai_nbi.kernel = ti_nbi.kernel
        ai_nbi.boot_archive = ti_nbi.boot_archive
        ai_nbi.kargs = ("-B %sinstall=true,install_media=http://%s/%s,"
                        "install_service=%s,install_svc_address=%s" %
                        (self.bootargs, self.srv_address, self.img_path,
                        self.svcname, self.srv_address))
        self.netbc.add_boot_instance(ai_nbi)

    def handle_boot_config(self):
        '''Call commit_boot_config and process the resulting tuple list'''
        logging.debug('in handle_boot_config')
        tuple_list = self.netbc.commit_boot_config()
        netconfig_files, config_files, boot_tuples = \
            self._handle_boot_tuple_list(tuple_list)

        # Remove the install image's cfgfile so we do not boot it.
        for file in netconfig_files + config_files:
            cfgfile = os.path.basename(file)
            media_grub = os.path.join(self.img_path, "boot/grub", cfgfile)
            if os.path.exists(media_grub):
                logging.debug('removing %s', media_grub)
                os.remove(media_grub)
        return (netconfig_files, config_files, boot_tuples)

    def _handle_boot_tuple_list(self, boot_config_list):
        '''Process returned tuple list from commit_boot_config()
           and handle entries appropriately.
           Returns tuple containing:
               netconfig_files: List of boot loader configuration files
                            e.g. /etc/netboot/<svcname>/[menu.lst|grub.cfg]
               config_files: List of other bootmgmt configuration files
               boot_tuples: list of tuples consisting of:
               (<type>, <archval>, <relative path of bootfile in tftproot>)
                e.g., ('00:00', 'bios', '<svcname>/boot/grub/pxegrub2')
        '''
        logging.debug('in _handle_boot_tuple_list tuples are %s',
                      boot_config_list)
        # Add dictionary mappings for tokens that commit_boot_config() might
        # return.
        self.boot_tokens[NetBootConfig.TOKEN_TFTP_ROOT] = com.BOOT_DIR
        boot_tuples = list()
        netconfig_files = list()
        config_files = list()
        for boot_config in boot_config_list:
            # boot-config elements can be either tuples or lists of tuples.
            # Cast tuples into a list for consistent iteration loop below.
            if not isinstance(boot_config, list):
                boot_config = [boot_config]
            for config_set in boot_config:
                ftype = config_set[0]
                if ftype == BootConfig.OUTPUT_TYPE_NETCONFIG:
                    dest_file = self._handle_file_type(config_set)
                    netconfig_files.append(dest_file)
                elif ftype == BootConfig.OUTPUT_TYPE_FILE:
                    dest_file = self._handle_file_type(config_set)
                    config_files.append(dest_file)
                elif ftype in [BootConfig.OUTPUT_TYPE_BIOS_NBP,
                               BootConfig.OUTPUT_TYPE_UEFI64_NBP]:
                    boot_entry = self._handle_nbp_type(config_set)
                    boot_tuples.append(boot_entry)
                else:
                    raise GrubError("Unexpected boot loader file "
                                    "type: %s" % ftype)

        logging.debug('_handle_boot_tuple_list returning netconfig_files: %s',
                      netconfig_files)
        logging.debug('_handle_boot_tuple_list returning config_files: %s',
                      config_files)
        logging.debug('_handle_boot_tuple_list returning boot_tuples: %s',
                      boot_tuples)
        return (netconfig_files, config_files, boot_tuples)

    def _handle_file_type(self, config):
        '''Method that handles tuple entry of type BootConfig.OUTPUT_TYPE_FILE
           Returns 'dest' from tuple, after updating '%(tftproot)s' token
           with appropriate value.

        '''
        ftype, src, objref, dest, uid, gid, mode = config

        if src is None:
            raise GrubError("Error: No source path defined for boot file.")
        if dest is None:
            raise GrubError("Error: No destination path defined for boot "
                            "file.")
        # handle ownership/permissions
        if uid is None:
            uid = -1
        if gid is None:
            gid = -1
        set_perms(src, uid, gid, mode)

        # for a client, use the src as the dest, because the file is
        # created directly in tftproot
        if self.mac_address is not None:
            real_dest = src
        else:
            real_dest = dest % self.boot_tokens
        return (real_dest)

    def _handle_nbp_type(self, config):
        '''Method that handles tuple entry of type
           BootConfig.OUTPUT_TYPE_BIOS_NBP or OUTPUT_TYPE_UEFI64_NBP
           Returns tuple:
               (dhcparch, archtype, relpath to nbp)
               ('00:00', 'bios', mysvc/boot/grub/pxegrub2')
        '''
        ftype, src, objref, dest, uid, gid, mode = config

        if src is None:
            raise GrubError("Error: No source path defined for nbp file.")

        # ftype will be 'nbp-platform-0xnnnn', such as 'nbp-platform-0x0007'
        # strip off the '0x'
        archval = ftype.rpartition('-0x')[2]
        archtype = archval
        if archval in NBP_TYPE:
            archtype = (NBP_TYPE[archval])
        dhcparch = archval[0:2] + ':' + archval[2:4]

        # create the relative path to the nbp (from /etc/netboot)
        relpath = self.svcname + src.partition(self.img_path)[2]
        return (dhcparch, archtype, relpath)

    def _read_current_config(self, mac_address=None):
        '''Read in current config and set self.netbc'''
        logging.debug('_read_current_config: mac_address is %s', mac_address)

        if mac_address is None:
            # Read in service's config
            self.netbc = NetBootConfig([],
                platform=('x86', None),
                osimage_root=self.img_path,
                data_root=self.svc_config_dir,
                tftproot_subdir=self.tftp_subdir)
        else:
            # Read in clients's config
            self.netbc = NetBootConfig([],
                platform=('x86', None),
                osimage_root=self.img_path,
                data_root=com.BOOT_DIR,
                client_id=mac_address,
                tftproot_subdir=self.tftp_subdir)
            self.mac_address = mac_address

    def update_imagepath(self, oldpath, newpath, mac_address=None):
        '''Update the imagepath in the boot configfiles

        Arguments:
            oldpath - imagepath to replace
            newpath - new imagepath
            mac_address - client MAC address
        '''
        logging.debug('update_imagepath: oldpath=%s newpath=%s '
                      'mac_address=%s', oldpath, newpath, mac_address)

        self._read_current_config(mac_address=mac_address)

        # Update imagepath in service's boot_instance kargs
        for boot_instance in self.netbc.boot_instances:
            kargs = boot_instance.kargs
            boot_instance.kargs = update_kargs_imagepath(kargs, oldpath,
                                                         newpath)
        tuple_list = self.netbc.commit_boot_config()
        netconfig_files, config_files, boot_tuples = \
            self._handle_boot_tuple_list(tuple_list)
        return (netconfig_files, config_files, boot_tuples)

    def update_svcname(self, oldname, newname, mac_address=None):
        '''Update the service name in the boot configfiles

        Arguments:
            oldpath - imagepath to replace
            newpath - new imagepath
            mac_address - client MAC address
        '''
        logging.debug('in update_svcname oldname=%s newname=%s',
                      oldname, newname)
        self._read_current_config(mac_address=mac_address)

        # Update net_tftproot_subdir in NetBootConfig instance
        self.netbc.net_tftproot_subdir = '/' + newname

        # Update svcname in service's boot_instance kargs
        for boot_instance in self.netbc.boot_instances:
            boot_instance = update_boot_instance_svcname(boot_instance,
                oldname, newname)

        tuple_list = self.netbc.commit_boot_config()
        netconfig_files, config_files, boot_tuples = \
            self._handle_boot_tuple_list(tuple_list)
        return (netconfig_files, config_files, boot_tuples)

    def get_mountpt(self, mac_address=None):
        '''Get the mountpt'''
        logging.debug('in get_mountpt')
        self._read_current_config(mac_address=mac_address)
        kernel = self.netbc.boot_instances[0].kernel.lstrip('/')
        parts = kernel.partition('/')
        mountpt = ''
        if parts[1]:
            mountpt = parts[0]
        logging.debug('get_mountpt returning %s', mountpt)
        return mountpt

    def setup_client(self, mac_address, bootargs='', service_bootargs=''):
        '''Setup a client's config files, using service's config info
           but allowing for client specific bootargs

        Arguments:
            mac_address - client MAC address
                          (either ABABABABABAB or AB:AB:AB:AB:AB:AB)
            bootargs = bootargs of client
            service_bootargs = bootargs of service
        Returns:
            Returns tuple (netconfig_files, config_files, boot_tuples):
               netconfig_files: List of boot loader configuration files
                            e.g. /etc/netboot/<svcname>/[menu.lst|grub.cfg]
               config_files: List of other bootmgmt configuration files
               boot_tuples: list of tuples consisting of:
                (<type>, <archval>, <relative path of bootfile>)
                [('00:00', 'bios', 'myservice/boot/grub/pxegrub2'),
                 ('00:07', 'uefi', 'seth0126rename/boot/grub/grub2netx64.efi')]

        '''
        logging.debug('setup_client: mac_address=%s, bootargs=%s, '
                      'service_bootargs=%s', mac_address, bootargs,
                      service_bootargs)
        self.mac_address = mac_address

        # Read in service's config
        svc_netbc = NetBootConfig([],
            platform=('x86', None),
            osimage_root=self.img_path,
            data_root=self.svc_config_dir,
            tftproot_subdir=self.tftp_subdir)

        # create client boot config
        client_netbc = NetBootConfig([BootConfig.BCF_CREATE],
            platform=('x86', None),
            osimage_root=self.img_path,
            data_root=com.BOOT_DIR,
            client_id=mac_address,
            tftproot_subdir=self.tftp_subdir)

        # Copy service boot instances and add to client (update bootargs
        # first, if they were specified by user)
        svc_boot_instances = svc_netbc.boot_instances
        for boot_instance in svc_boot_instances:
            client_bi = boot_instance.copy()
            if bootargs:
                client_bi.kargs = update_kargs_bootargs(client_bi.kargs,
                    service_bootargs, bootargs)
            client_netbc.add_boot_instance(client_bi)

        # Set client boot loader props the same as in the service
        # E.g., BootLoader.<PROP_CONSOLE/PROP_TIMEOUT/PROP_MINMEM64>
        svc_bl = svc_netbc.boot_loader
        for prop in svc_bl.SUPPORTED_PROPS:
            client_netbc.boot_loader.setprop(prop, svc_bl.getprop(prop))

        # Commit the configuration. This will result in the creation of
        # the <cfgfile>.<clientid> file (e.g., menu.lst.01223344223344
        # or grub.cfg.01223344223344) in tftproot.
        tuple_list = client_netbc.commit_boot_config()
        netconfig_files, config_files, boot_tuples = \
            self._handle_boot_tuple_list(tuple_list)
        return (netconfig_files, config_files, boot_tuples)

    def update_basesvc(self, newbasesvc_netbc, newbasesvc_bootargs='',
                       alias_bootargs=''):
        '''Update an alias's config files for a new basesvc

        Arguments:
            newbasesvc_netbc - AIGrubCfg object of new basesvc
            bootargs = bootargs of client
            service_bootargs = bootargs of service
        Returns tuple (netconfig_files, config_files, boot_tuples):
               netconfig_files: List of boot loader configuration files
                            e.g. /etc/netboot/<svcname>/[menu.lst|grub.cfg]
               config_files: List of other bootmgmt configuration files
               boot_tuples: list of tuples consisting of:
                (<type>, <archval>, <relative path of bootfile>)

        '''
        logging.debug('update_basesvc: newbasesvc_bootargs=%s, '
                      'alias_bootargs=%s' %
                      (newbasesvc_bootargs, alias_bootargs))

        # Read in new baseservice's config
        newbase_netbc = NetBootConfig([],
            platform=('x86', None),
            osimage_root=newbasesvc_netbc.img_path,
            data_root=newbasesvc_netbc.svc_config_dir,
            tftproot_subdir=newbasesvc_netbc.tftp_subdir)

        # Create new alias config
        alias_netbc = NetBootConfig([BootConfig.BCF_CREATE],
            platform=('x86', None),
            osimage_root=newbasesvc_netbc.img_path,
            data_root=self.svc_config_dir,
            tftproot_subdir=self.tftp_subdir)

        # Copy new baseservice boot instances and use for alias, but
        # use name and bootargs of alias
        newbase_boot_instances = newbase_netbc.boot_instances
        for boot_inst in newbase_boot_instances:
            alias_bi = boot_inst.copy()
            alias_bi = update_boot_instance_svcname(alias_bi,
                newbasesvc_netbc.svcname, self.svcname)
            alias_bi.kargs = update_kargs_bootargs(alias_bi.kargs,
                newbasesvc_bootargs, alias_bootargs)
            alias_netbc.add_boot_instance(alias_bi)

        # Set alias boot loader props the same as in the base service
        # E.g., BootLoader.<PROP_CONSOLE/PROP_TIMEOUT/PROP_MINMEM64>
        newbase_bl = newbase_netbc.boot_loader
        for prop in newbase_bl.SUPPORTED_PROPS:
            alias_netbc.boot_loader.setprop(prop, newbase_bl.getprop(prop))

        # Commit the configuration.
        tuple_list = alias_netbc.commit_boot_config()
        netconfig_files, config_files, boot_tuples = \
            self._handle_boot_tuple_list(tuple_list)
        return (netconfig_files, config_files, boot_tuples)
