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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''
Objects and functions supporting accessing and modifying AI service instances

Service Version History:

0:
    Unversioned services (all services prior to derived manifests)

1: Incompatible with prior versions (automatic upgrade)
    Services supporting derived manifests (default manifest now
    included in the manifest database, and behaves like a normal manifest)

2: Incompatible with prior versions (manual upgrade required)
    "Install Server Image Management" (ISIM) services. Configuration moved
    from SMF to /var/ai. Support for aliases.
'''
import errno
import fileinput
import logging
import os
import socket
import sys

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.dhcp as dhcp
import osol_install.auto_install.grub as grub
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config
import osol_install.libaimdns as libaimdns

from osol_install.auto_install.data_files import DataFiles, insert_SQL, \
    place_manifest, validate_file
from osol_install.auto_install.grub import AIGrubCfg as grubcfg
from osol_install.auto_install.image import InstalladmImage, ImageError
from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen, CalledProcessError, force_delete

MOUNT = '/usr/sbin/mount'
UNMOUNT = '/usr/sbin/umount'
SYSTEMCONF = 'system.conf'
WANBOOTCONF = 'wanboot.conf'
NETBOOT = '/etc/netboot'
MENULST = grub.MENULST

STARTING_PORT = 46501
ENDING_PORT = socket.SOL_SOCKET  # Last socket is 65535
AI_SERVICE_DIR_PATH = com.AI_SERVICE_DIR_PATH

IMG_AI_DEFAULT_MANIFEST = "auto_install/manifest/default.xml"
OLD_IMG_AI_DEFAULT_MANIFEST = "auto_install/default.xml"
SYS_AI_DEFAULT_MANIFEST = "/usr/share/auto_install/manifest/default.xml"

DEFAULT_SPARC = 'default-sparc'
DEFAULT_I386 = 'default-i386'
DEFAULT_ARCH = [DEFAULT_SPARC, DEFAULT_I386]


class AIServiceError(StandardError):
    '''Base class for errors unique to AIService'''
    pass


class UnsupportedOperationError(AIServiceError, TypeError):
    '''Raised when the service does not support the called function'''
    pass


class UnsupportedAliasError(AIServiceError):
    '''Raised when alias creation cannot be done'''
    pass


class InvalidServiceError(AIServiceError):
    '''Raised when the service cannot be enabled due to some invalid state'''
    pass


class VersionError(AIServiceError):
    '''Raised if the service's version is not supported by
    this version of installadm

    '''
    def __init__(self, service_name=None, version=None, alt_msg=None):
        self.service_name = service_name
        self.version = version
        self.alt_msg = alt_msg

    def __str__(self):
        if self.alt_msg:
            return self.alt_msg
        else:
            return self.short_str()

    def short_str(self):
        '''Returns a one-line string message for this error'''
        return (cw(_("Service '%(name)s' is incompatible: "
                     "[version: %(version)s]") %
                     {'version': self.version, 'name': self.service_name}))


class OlderVersionError(VersionError):
    def __str__(self):
        if self.alt_msg:
            return self.alt_msg

        return (cw(_("\nService '%(name)s' cannot be modified because it was "
                     "created with an older version of installadm (service "
                     "version: %(version)s).\n") %
                     {'version': self.version, 'name': self.service_name}))


class NewerVersionError(VersionError):
    def __str__(self):
        if self.alt_msg:
            return self.alt_msg

        return cw(_("\nService '%(name)s' cannot be modified because it was "
                    "created with a newer version of installadm (service "
                    "version: %(version)s).\n") %
                    {'version': self.version, 'name': self.service_name})


class MountError(AIServiceError):
    '''Service could not be properly mounted'''
    def __init__(self, source, target, reason):
        self.source = source
        self.target = target
        self.reason = reason

    def __str__(self):
        return cw(_("\nUnable to mount '%(source)s' at '%(target)s':"
                    "%(reason)s\n" % {'source': self.source, \
                    'target': self.target, 'reason': self.reason}))


class UnmountError(MountError):
    '''Service could not be properly unmounted'''
    def __init__(self, target, reason):
        self.target = target
        self.reason = reason

    def __str__(self):
        return cw(_("\nUnable to unmount '%(target)s': %(reason)s\n") %
                    {'target': self.target, 'reason': self.reason})


class MultipleUnmountError(UnmountError):
    '''More than one unmount failed when unmounting a service'''
    def __init__(self, still_mounted, failures):
        self.still_mounted = still_mounted
        self.failures = failures

    def __str__(self):
        result = list()
        if self.still_mounted:
            result.append(_("Failed to unmount:"))
            result.extend(self.still_mounted)
        if self.failures:
            result.extend(self.failures)
        return "\n".join([str(r) for r in result])


def mount_enabled_services(remount=False):
    '''Mounts all services configured to be enabled. If remount is True,
    and a service is already mounted, it is first unmounted (otherwise, the
    mount is left as-is. Returns a count of how many services failed to
    mount properly, and prints to stderr as the errors are encountered.

    '''
    failures = 0
    for svc_name in config.get_all_service_names():
        if not config.is_enabled(svc_name):
            continue
        try:
            svc = AIService(svc_name)
        except VersionError as err:
            # If this installadm server doesn't understand this
            # service, do not mount it.
            print >> sys.stderr, _("\nNot mounting %s") % svc_name
            print >> sys.stderr, err
            continue
        if remount and svc.mounted():
            try:
                svc.unmount(force=True)
            except MountError as err:
                print >> sys.stderr, err
                failures += 1
                continue
        try:
            svc.mount()
        except (MountError, ImageError) as err:
            print >> sys.stderr, err
            failures += 1
            continue
    return failures


def unmount_all():
    '''Unmounts all services'''
    failures = 0
    for svc_name in config.get_all_service_names():
        try:
            svc = AIService(svc_name)
        except VersionError as err:
            # If this installadm server doesn't understand this
            # service, it wasn't mounted in the first place
            continue
        if svc.mounted():
            try:
                svc.unmount(force=True)
            except MountError as err:
                print >> sys.stderr, err
                failures += 1
    return failures


class AIService(object):
    '''Class to represent an AI service'''

    MOUNT_ON = com.BOOT_DIR
    X86_BOOTFILE = "boot/grub/pxegrub"
    EARLIEST_VERSION = 2
    LATEST_VERSION = 2

    @classmethod
    def create(cls, name, source_image, ip_start=None, ip_count=None,
               bootserver=None, alias=None, bootargs=''):
        '''Creates a service, setting up configuration, initial manifests,
        and DHCP (if desired)

        Args:
            name: Desired service name (not checked for validity)
            source_image: An InstalladmImage object representing an already
                unpacked image area

        Optional Args:
            ip_start, ip_count: Starting IP address and number of IP addresses
                to allocate in DHCP. If not specified, no DHCP setup will be
                done
            bootserver: If DHCP configuration is provided, optionally explicit
                address for the bootfile server
            alias: An AIService object to which this service will be aliased
            bootargs (x86 only): Additional bootargs to add to boot cfgfile

        '''
        service = cls(name, _check_version=False)
        service._image = source_image
        service._alias = alias
        service._bootargs = bootargs

        if alias is not None and service.image.version < 3:
            raise UnsupportedAliasError(cw(_("\nCannot create alias: Aliased "
                                             "service '%s' does not support "
                                             "aliasing. Please use a service "
                                             "with a newer image.\n") % alias))

        compatibility_port = (service.image.version < 1)
        logging.debug("compatibility port=%s", compatibility_port)
        server_hostname = socket.gethostname()

        # Determine port information
        if compatibility_port:
            port = get_a_free_tcp_port(server_hostname)
            if not port:
                raise AIServiceError(_("Cannot find a free port to start the "
                                       "web server."))
        else:
            port = libaimdns.getinteger_property(com.SRVINST, com.PORTPROP)

        props = service._init_service_config(server_hostname, port)

        # Create AI_SERVICE_DIR_PATH/<svcdir> structure
        cmd = [com.SETUP_SERVICE_SCRIPT, com.SERVICE_CREATE, name,
               props[config.PROP_TXT_RECORD], service._image.path]
        try:
            # Note: Can't rely on Popen.check_call's logger argument, as
            # the setup-service-script relies on sending information to
            # stdout/stderr
            logging.debug("Executing: %s", cmd)
            Popen.check_call(cmd)
        except CalledProcessError:
            print >> sys.stderr, _("Failed to setup service directory for "
                                   "service, %s\n" % name)

        service._create_default_manifest()

        # Supported client images will interpolate the bootserver's IP
        # address (as retrieved from the DHCP server) in place of the
        # '$serverIP' string. We choose to utilize this functionality when
        # possible so that any client can utilize this service, from any
        # network.
        if service.image.version < 1:
            # Solaris 11 Express does not support the $serverIP function.
            # We must use the configured AI network's local IP address.
            valid_nets = list(com.get_valid_networks())
            if valid_nets:
                server_ip = valid_nets[0]

                # If more than one IP is configured, inform the user of our
                # choice that we're picking the first one available.
                if len(valid_nets) > 1:
                    print >> sys.stderr, _("More than one IP address is "
                                           "configured for use with "
                                           "install services, using %s for "
                                           "this service.") % server_ip
            else:
                raise AIServiceError(_("Cannot determine bootserver IP."))
        else:
            server_ip = "$serverIP"

        logging.debug("server_ip=%s", server_ip)

        # Save location of service in format <server_ip_address>:<port>
        # It will be used later for setting service discovery fallback
        # mechanism.
        srv_address = '%s:%u' % (server_ip, port)
        logging.debug("srv_address=%s", srv_address)

        # Setup wanboot for SPARC or Grub for x86
        if service.image.arch == 'sparc':
            service._init_wanboot(srv_address)
        else:
            service._init_grub(srv_address)

        # Configure DHCP for this service
        service._configure_dhcp(ip_start, ip_count, bootserver)

        return service

    def __init__(self, name, image=None, image_class=InstalladmImage,
                 _check_version=True):
        '''Create a reference to an AIService, which can be used to control
        and manage installadm services.

        Required arguments:
            name: The name of the service. It should already exist.
                     (Use classmethod AIService.create() to make a new service)
        Optional arguments:
            image: A reference to an InstalladmImage object, used to
                      control the underlying image area. If not given,
                      one will be instantiated as needed.
            image_class: If 'image' is omitted, when an image reference is
                            needed, it will be instantiated as an instance
                            of the given class. Defaults to InstalladmImage.

        '''
        self._name = name
        self._image = image
        self._alias = None
        self._bootargs = None
        self._image_class = image_class
        self._boot_tuples = None
        self._netcfgfile = None

        # _check_version should ONLY be used by AIService.create during service
        # creation. Bypassing the version check when the service has already
        # been created may lead to indeterminate results.
        if not _check_version:
            return
        version = self.version()
        if version is None:
            raise VersionError(name, version,
                               alt_msg=_("Unable to determine service "
                                         "version for '%s'" % name))
        elif version < self.EARLIEST_VERSION:
            raise OlderVersionError(name, version)
        elif version > self.LATEST_VERSION:
            raise NewerVersionError(name, version)

    def enable(self):
        '''Enable this service. May fail, if this service is marked in need
        of re-verification, and re-verification fails.

        '''
        if config.get_service_props(self.name).get(config.PROP_REVERIFY,
                                                   False):
            self.check_valid()
        self.mount()
        config.enable_install_service(self.name)

    def disable(self, arch_safe=False, force=False):
        '''Disable this service'''
        props = {config.PROP_STATUS: config.STATUS_OFF}
        config.set_service_props(self.name, props)

        self._unregister()
        self.unmount(arch_safe=arch_safe, force=force)

        # If no longer needed, put install instance into
        # maintenance
        config.check_for_enabled_services()

    def _unregister(self):
        cmd = [com.SETUP_SERVICE_SCRIPT, com.SERVICE_DISABLE, self.name]
        Popen.check_call(cmd, check_result=Popen.ANY)

    def delete(self):
        '''Deletes this service, removing the image area, mountpoints,
        and lingering configuration.

        '''
        self.disable(arch_safe=True, force=True)

        self.remove_profiles()
        for path in self.get_files_to_remove():
            force_delete(path)

    def version(self):
        '''Look up and return the version of this service. See module
        docstring for info on what each service version supports

        '''
        props = config.get_service_props(self.name)
        try:
            return int(props[config.PROP_VERSION])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def config_dir(self):
        '''Returns the path to the configuration directory for this service'''
        return os.path.join(AI_SERVICE_DIR_PATH, self.name)

    @property
    def database_path(self):
        '''Returns the path to the database file for this service'''
        return os.path.join(self.config_dir, "AI.db")

    def database(self):
        '''Opens an AI_database.DB() object pointing to this service's
        database

        '''
        return AIdb.DB(self.database_path)

    def rename(self, new_name):
        '''Change this service's name to new_name '''
        self._update_name_in_service_props(new_name)
        new_svcdir = os.path.join(AI_SERVICE_DIR_PATH, new_name)
        if self.arch == 'sparc':
            # Update the system.conf file with the new service name
            sysconf_path = os.path.join(self.config_dir, SYSTEMCONF)
            new_str = 'install_service=' + new_name + '\n'
            for line in fileinput.input(sysconf_path, inplace=1):
                if line.startswith('install_service='):
                    sys.stdout.write(new_str)
                else:
                    sys.stdout.write(line)
            self._setup_install_conf()

            # If this is current default sparc service and it is
            # eventually allowed to be renamed, redo symlinks in
            # /etc/netboot:
            #   wanboot.conf -> /etc/netboot/<defaultsvc>/wanboot.conf
            #   system.conf  -> /etc/netboot/<defaultsvc>/system.conf
            # by calling: self.do_default_sparc_symlinks(new_name)
        else:
            # Update the grub config files with the new service name
            # Note that the new svcname is assumed to be the mountpoint
            # in /etc/netboot
            svcgrub = grubcfg(self.name, path=self.image.path,
                              config_dir=self.config_dir)
            netconfig_files, config_files, self._boot_tuples = \
                svcgrub.update_svcname(self.name, new_name)

            # update boot_cfgfile in .config file
            self._netcfgfile = netconfig_files[0]
            props = {config.PROP_BOOT_CFGFILE: self._netcfgfile}
            config.set_service_props(self.name, props)

        self._migrate_service_dir(new_svcdir)
        self._setup_manifest_dir(new_name=new_name)

    def is_default_arch_service(self):
        ''' Determine if this is the default-<arch> service'''

        return (self.name in DEFAULT_ARCH)

    def do_default_sparc_symlinks(self, svcname):
        ''' Do symlinks for default sparc service
        Input:
            svcname - svcname in symlink

        '''
        for linkname in WANBOOTCONF, SYSTEMCONF:
            self._do_default_sparc_symlink(linkname, svcname)

    def _do_default_sparc_symlink(self, linkname, svcname):
        ''' Do symlinks for default sparc service
        Input:
            linkname = either WANBOOTCONF or SYSTEMCONF
            svcname - name of service

        '''
        symlink = os.path.join(self.MOUNT_ON, linkname)
        try:
            os.remove(symlink)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
        new_target = os.path.join(self.MOUNT_ON, svcname, linkname)
        os.symlink(new_target, symlink)

    def delete_default_sparc_symlinks(self):
        '''Delete symlinks for default sparc service'''
        for linkname in WANBOOTCONF, SYSTEMCONF:
            symlink = os.path.join(self.MOUNT_ON, linkname)
            try:
                os.remove(symlink)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise

    def _migrate_service_dir(self, newsvcdir):
        '''Copy or move the AI_SERVICE_DIR_PATH/<svc> directory
           Additionally update any compatibility symlinks pointing to it
               (or create new ones)

           Input:
                  newsvcdir - full path to new service dir

        '''
        # update any symlinks pointing to svcdir
        dirlist = os.listdir(AI_SERVICE_DIR_PATH)
        for subdir in dirlist:
            fullpath = os.path.join(AI_SERVICE_DIR_PATH, subdir)
            # if not a symlink, skip
            if not os.path.islink(fullpath):
                continue
            # get target of symlink and see if it's the service
            # being renamed
            linkto = os.readlink(fullpath)
            target = os.path.join(os.path.dirname(fullpath), linkto)
            if target == self.config_dir:
                logging.debug("removing %s", fullpath)
                try:
                    os.remove(fullpath)
                except OSError as err:
                    if err.errno != errno.ENOENT:
                        raise
                logging.debug("symlink from %s to %s", fullpath, newsvcdir)
                os.symlink(newsvcdir, fullpath)

        logging.debug("rename from %s to %s", self.config_dir, newsvcdir)
        os.rename(self.config_dir, newsvcdir)

    def _update_name_in_service_props(self, newsvcname):
        '''Set service_name property to newsvcname'''

        props = config.get_service_props(self.name)
        props[config.PROP_SERVICE_NAME] = newsvcname
        config.set_service_props(self.name, props)

    def _update_path_in_service_props(self, new_path):
        '''Set image_path property to new_path '''

        props = config.get_service_props(self.name)
        props[config.PROP_IMAGE_PATH] = new_path
        config.set_service_props(self.name, props)

    @property
    def name(self):
        '''Service name'''
        return self._name

    @staticmethod
    def _prepare_target(mountpoint):
        logging.debug("_prepare_target: mountpoint is %s", mountpoint)
        try:
            os.makedirs(mountpoint)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

    @property
    def mountpoint(self):
        '''Returns the path to where this service's image should be mounted'''
        return os.path.join(self.MOUNT_ON, self.name)

    @property
    def bootmountpt(self):
        '''Returns the path to where this service's boot specific config
        file should be mounted

        '''
        if self.arch == 'i386':
            mtpt = self.boot_cfgfile
            if not mtpt:
                # Fall back to menu.lst
                mtpt = os.path.join(self.mountpoint, MENULST)
            return mtpt
        else:
            return os.path.join(self.mountpoint, SYSTEMCONF)

    def all_bootmountpts(self):
        mountpts = [os.path.join(self.mountpoint, MENULST),
                    os.path.join(self.mountpoint, SYSTEMCONF)]
        mountpts.append(self.bootmountpt)
        return mountpts

    @property
    def bootsource(self):
        '''Returns the path to the file that should be mounted at
        self.bootmountpt (e.g., /var/ai/service/<svcname>/<grub_cfg_file>)
        '''
        if self.arch == 'i386':
            mtpt = self.bootmountpt
            cfgfile = os.path.basename(mtpt)
            return os.path.join(self.config_dir, cfgfile)
        else:
            return os.path.join(self.config_dir, SYSTEMCONF)

    @property
    def boot_tuples(self):
        '''Boot tuples created by bootmgmt'''
        return self._boot_tuples

    @property
    def boot_cfgfile(self):
        '''Look up and return the name of where to mount config file
           created by bootmgmt (e.g., /etc/netboot/mysvc/<grub_cfg_file>)

        '''
        props = config.get_service_props(self.name)
        try:
            return props[config.PROP_BOOT_CFGFILE]
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def dhcp_bootfile_sparc(self):
        '''Returns a string that represents what should be added to DHCP
        as this sparc service's bootfile

        '''
        if self.arch != 'sparc':
            return None

        http_port = libaimdns.getinteger_property(com.SRVINST, com.PORTPROP)
        # Always use $serverIP keyword as setup-dhcp will substitute in
        # the correct IP addresses.
        dhcpbfile = 'http://%s:%u/%s' % ("$serverIP", http_port,
                                         com.WANBOOTCGI)
        return dhcpbfile

    def _lofs_mount(self, from_path, to_mountpoint):
        '''Internal lofs mount function. If the mountpoint
        is already in use by this service, returns without doing anything.
        Otherwise, will mount from_path on to_mountpoint, raising MountError
        for any failure.

        '''
        mount_points = com.MNTTab()['mount_point']
        specials = com.MNTTab()['special']
        if to_mountpoint in mount_points:
            mntpt_idx = mount_points.index(to_mountpoint)
            if specials[mntpt_idx] == from_path:
                # Already mounted as desired; nothing to do
                return
        self._prepare_target(to_mountpoint)
        cmd = [MOUNT, '-F', 'lofs', from_path, to_mountpoint]
        try:
            Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                             logger='', stderr_loglevel=logging.DEBUG,
                             check_result=Popen.SUCCESS)
        except CalledProcessError as err:
            raise MountError(from_path, to_mountpoint, err.popen.stderr)

    def mount(self):
        '''Perform service lofs mounts

        For all services,
          /etc/netboot/<svcname> is an lofs mount of <targetdir> (or
               self.image.path for an alias)
        In addition:
          For sparc:
            /etc/netboot/<svcname>/system.conf is an lofs mount of
                AI_SERVICE_DIR_PATH/<svcname>/system.conf
          For x86:
            /etc/netboot/<svcname>/<cfgfile> is an lofs mount of
                AI_SERVICE_DIR_PATH/<svcname>/<grub_cfg_file>

        '''
        # Verify the image and ensure the mountpoints exist
        try:
            self.image.verify()
        except ImageError as error:
            # verify doesn't know anything about services so prepend the
            # service name to the exception to give the user sufficient
            # context to fix the problem and re-raise the exception
            raise ImageError(cw(_('Service Name: %s\n') %
                             self.name + str(error)))

        # Mount service's image to /etc/netboot/<svcname>
        self._lofs_mount(self.image.path, self.mountpoint)
        # Do second lofi mount of grub config file for x86 or
        # system.conf (for sparc)
        bootsource = self.bootsource
        bootmount = self.bootmountpt
        logging.debug('lofs mount of %s, %s', bootsource, bootmount)
        self._lofs_mount(bootsource, bootmount)

    def unmount(self, force=False, arch_safe=False):
        '''Unmount the service, reversing the effects of AIService.mount()

        Will raise MultipleUnmountFailure if the service does not cleanly
        unmount. If errors occur during unmounting, but the unmounts
        are otherwise successful, then failures are ignored (logged)

        If arch_safe is True, this command will umount all potential
        mountpoints, without checking the underlying image arch
        (useful for deleting a service when the underlying image
        is corrupted or missing)

        DO NOT UNMOUNT AN ENABLED SERVICE OR YOU WILL HAVE WEIRD ERRORS

        SMF will see a service as enabled and remount it at arbitrary
        points in time

        '''
        umount_cmd = [UNMOUNT]
        if force:
            umount_cmd.append("-f")

        if arch_safe:
            mountpoints = self.all_bootmountpts()
        else:
            mountpoints = [self.bootmountpt]

        # The image mountpoint must be unmounted last, as the boot mounts
        # are mounted inside of it.
        mountpoints.append(self.mountpoint)

        failures = list()
        for mountpoint in mountpoints:
            cmd = list(umount_cmd)
            cmd.append(mountpoint)
            try:
                Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                                 logger='', stderr_loglevel=logging.DEBUG,
                                 check_result=Popen.SUCCESS)
            except CalledProcessError as err:
                failures.append(UnmountError(mountpoint, err.popen.stderr))

        still_mounted = self._currently_mounted()
        if still_mounted:
            raise MultipleUnmountError(still_mounted, failures)

    def mounted(self):
        '''Returns True if ALL mounts for this service are active.'''
        mount_points = com.MNTTab()['mount_point']
        return (self.mountpoint in mount_points and
                self.bootmountpt in mount_points)

    def _currently_mounted(self):
        '''Returns True if ANY mounts for this service are active.

        If AIService.mounted returns False while AIService.partially_mounted
        returns True, the service failed to properly mount or unmount

        '''
        current_mounts = list()
        mount_points = com.MNTTab()['mount_point']
        if self.mountpoint in mount_points:
            current_mounts.append(self.mountpoint)
        for boot_mount in self.all_bootmountpts():
            if boot_mount in mount_points:
                current_mounts.append(boot_mount)
        return current_mounts

    def is_alias(self):
        '''Determine if this service is an alias'''
        return (self.basesvc is not None)

    def is_aliasof(self, servicename):
        '''
        Determine if this service is an alias of servicename
        '''
        basesvcs = config.get_aliased_services(servicename)
        if self.name in basesvcs:
            return True
        return False

    def update_wanboot_imagepath(self, oldpath, newpath):
        ''' Update the imagepath in service's wanboot.conf

         Input:
            oldpath - imagepath to replace
            newpath - new imagepath

        '''
        logging.debug('update_wanboot_imagepath, %s to %s', oldpath, newpath)
        wanbootpath = os.path.join(self.image.path, WANBOOTCONF)
        for line in fileinput.input(wanbootpath, inplace=1):
            newline = line
            parts = newline.partition(oldpath)
            if parts[1]:
                newline = parts[0] + newpath + parts[2]
            sys.stdout.write(newline)

    def update_basesvc(self, newbasesvc_name):
        '''
        For an alias, do all activities needed if the basesvc
        has been updated:
            All:
            o update aliasof property in .config to newbasesvc_name
            o disable alias
            o x86 only:  Recreate grub config for alias and dependent aliases
            o revalidate manifests and profiles
            o enable alias
        Dependent clients are handled in set_service.

        Input:   newbasesvc_name - name of new base service

        '''
        if not self.is_alias():
            raise UnsupportedOperationError("This service is not an alias")
        newbasesvc = AIService(newbasesvc_name)
        if newbasesvc.image.version < 3:
            raise UnsupportedAliasError(cw(_("\nCannot update alias: Aliased "
                                             "service '%s' does not support "
                                             "aliasing. Please use a service "
                                             "with a newer image.\n") %
                                             newbasesvc_name))

        # The service configuration needs to be updated before the
        # service can successfully be disabled.
        logging.debug("updating alias service props for %s", self.name)
        props = {config.PROP_ALIAS_OF: newbasesvc_name}
        config.set_service_props(self.name, props)

        # disable the alias
        was_mounted = False
        if self.mounted():
            was_mounted = True
            self.disable(force=True)

        if self.arch == 'i386':
            all_aliases = config.get_aliased_services(self.name, recurse=True)

            # Update the grub config with the new base service info.
            newbasegrub = grubcfg(newbasesvc.name, path=newbasesvc.image.path,
                                  config_dir=newbasesvc.config_dir)
            aliasgrub = grubcfg(self.name, path=newbasesvc.image.path,
                                config_dir=self.config_dir)
            netconfig_files, config_files, self._boot_tuples = \
                aliasgrub.update_basesvc(newbasegrub, newbasesvc.bootargs,
                                         self.bootargs)

            # update boot_cfgfile in .config file
            self._netcfgfile = netconfig_files[0]
            props = {config.PROP_BOOT_CFGFILE: self._netcfgfile}
            config.set_service_props(self.name, props)

            # Recreate grub config files of all aliases of this alias
            # (and descendants). Use the sub alias' bootargs instead
            # of the ones specified in the base service.
            for alias in all_aliases:
                aliassvc = AIService(alias)
                sub_alias_was_mounted = False
                if aliassvc.mounted():
                    sub_alias_was_mounted = True
                    aliassvc.disable(force=True)

                aliasgrub = grubcfg(alias, path=aliassvc.image.path,
                                    config_dir=aliassvc.config_dir)
                aliasgrub.update_basesvc(newbasegrub, newbasesvc.bootargs,
                                         aliassvc.bootargs)
                if sub_alias_was_mounted:
                    aliassvc.enable()

        # Turning point: Function calls prior to this line will reference
        # the 'old' base service's image. Function calls after this line
        # will reference the *new* base service's image. Keep that in mind
        # when adding to this function.
        self._image = None

        try:
            self.check_valid()
        except InvalidServiceError:
            print >> sys.stderr, cw(_("\nOne or more of this alias' manifests "
                                      "or profiles is no longer valid. This "
                                      "service will be disabled until they "
                                      "have been removed or fixed.\n"))

        # Enable the alias to pick up the new image
        if was_mounted:
            self.enable()

        # Configure DHCP for this service
        self._configure_dhcp(None, None, None)

    @property
    def manifest_dir(self):
        '''Full path to the directory where this service's
        manifests are stored

        '''
        return os.path.join(self.config_dir, "AI_data")

    def validate_manifests(self):
        '''Re-verifies all relevant AI XML manifests associated with this
        service. For any that are no longer valid according to the image's
        DTD, an error is printed. A count of the number of invalid manifests
        is returned.

        '''
        db_conn = self.database()
        manifests = AIdb.getNames(db_conn.getQueue(), AIdb.MANIFESTS_TABLE)

        failures = 0
        for manifest in manifests:
            manifest_path = os.path.join(self.manifest_dir, manifest)
            try:
                DataFiles.from_service(self, manifest_file=manifest_path)
            except ValueError as val_err:
                error = cw(_("\nManifest '%s' is not valid for this image. "
                             "Please fix and update this manifest.\n") %
                             manifest)
                print >> sys.stderr, val_err
                print >> sys.stderr, error
                failures += 1
        return failures

    def remove_profiles(self):
        ''' delete profile files from internal database
        Arg: service - object of service to delete profile files for
        Effects: all internal profile files for service are deleted
        Exceptions: OSError logged only, considered non-critical
        Note: database untouched - assumes that database file will be deleted
        '''
        logging.debug("removing profiles...")
        dbn = self.database()
        queue = dbn.getQueue()
        if not AIdb.tableExists(queue, AIdb.PROFILES_TABLE):
            return
        query = AIdb.DBrequest("SELECT file FROM " + AIdb.PROFILES_TABLE)
        queue.put(query)
        query.waitAns()
        for row in iter(query.getResponse()):
            filename = row['file']
            try:
                if os.path.exists(filename):
                    os.unlink(filename)
            except OSError, emsg:
                logging.warn(_("Could not delete profile %(filename)s: "
                               "%(error)s") % {'filename': filename, \
                               'error': emsg})

    def validate_profiles(self):
        '''Re-verifies all relevant SC XML profiles associated with this
        service. For any that are no longer valid according to the image's
        DTD, an error is printed. A count of the number of invalid profiles
        is returned.

        '''
        failures = 0

        if self.image.version < 2:
            # Older client images do not support profiles
            return failures
        db_conn = self.database()
        queue = db_conn.getQueue()
        profile_request = AIdb.DBrequest("select name, file from " +
                                         AIdb.PROFILES_TABLE)
        queue.put(profile_request)
        profile_request.waitAns()
        profiles = profile_request.getResponse() or list()

        for profile_name, profile_path in profiles:
            valid = validate_file(profile_name, profile_path,
                                  self.image.path, verbose=False)
            if not valid:
                error = cw(_("\nProfile '%s' is not valid for this image. "
                             "Please fix and update this profile.\n") %
                             profile_name)
                print >> sys.stderr, error
                failures += 1
        return failures

    def check_valid(self):
        '''Validates whether or not this service can be enabled. If
        this service can be enabled, then the PROP_REVERIFY flag is set
        to False. If it CANNOT be enabled, the PROP_REVERIFY flag is set to
        True, the service is disabled, and InvalidServiceError is raised.

        Currently, this function only validates manifests/profiles against
        this service's image (valuable for aliases).

        '''
        invalid_manifest_count = self.validate_manifests()
        invalid_profile_count = self.validate_profiles()
        if invalid_manifest_count or invalid_profile_count:
            # Set invalid flag, and disable service. Service cannot be
            # re-enabled until it comes back as valid.
            config.set_service_props(self.name, {config.PROP_REVERIFY: True})
            self.disable()
            raise InvalidServiceError()
        else:
            # Invalid flag is cleared, but user must manually enable service
            config.set_service_props(self.name, {config.PROP_REVERIFY: False})

    @property
    def basesvc(self):
        '''get reference to basesvc of an alias or None if not an alias'''
        basesvc = None
        props = config.get_service_props(self.name)
        if config.PROP_ALIAS_OF in props:
            basesvc = props[config.PROP_ALIAS_OF]
        return basesvc

    @property
    def bootargs(self):
        '''get bootargs of a service'''
        bootargs = ''
        props = config.get_service_props(self.name)
        if config.PROP_BOOT_ARGS in props:
            bootargs = props[config.PROP_BOOT_ARGS]
        return bootargs

    @property
    def arch(self):
        '''Defer to underlying image object'''
        if self.image:
            return self.image.arch
        else:
            return None

    @property
    def image(self):
        '''Returns a reference to an InstalladmImage object (or subclass)
        pointed at this service's image path (following aliases as needed).

        The actual class of the returned object can be modified by
        passing in the desired class as the "image_class" keyword arg
        to the AIService constructor.
        '''
        if self._image is None:
            # If service is configured, get image path from config and
            # generate an InstalladmImage object. Otherwise, return None
            if config.is_service(self.name):
                props = config.get_service_props(self.name)
                if config.PROP_ALIAS_OF not in props:
                    path = props[config.PROP_IMAGE_PATH]
                else:
                    # if setting up an alias, use the image path of the
                    # service being aliased
                    alias = props[config.PROP_ALIAS_OF]
                    alias_svc = AIService(alias)
                    path = alias_svc.image.path
                self._image = self._image_class(path)
        return self._image

    def _configure_dhcp(self, ip_start, ip_count, bootserver):
        '''Add DHCP configuration elements for this service.'''

        logging.debug('Calling setup_dhcp_server %s %s %s',
                       ip_start, ip_count, bootserver)

        setup_dhcp_server(self, ip_start, ip_count, bootserver)

    def _init_grub(self, srv_address):
        '''Initialize grub for this service'''
        svcgrub = grubcfg(self.name, path=self.image.path,
                          image_info=self.image.read_image_info(),
                          srv_address=srv_address, config_dir=self.config_dir,
                          bootargs=self._bootargs)

        netconfig_files, config_files, self._boot_tuples = svcgrub.setup_grub()
        self._netcfgfile = netconfig_files[0]
        props = {config.PROP_BOOT_CFGFILE: self._netcfgfile}
        config.set_service_props(self.name, props)

    def _init_wanboot(self, srv_address):
        '''Create system.conf file in AI_SERVICE_DIR_PATH/<svcname>'''
        cmd = [com.SETUP_SPARC_SCRIPT, com.SPARC_SERVER, self.image.path,
               self.name, srv_address, self.config_dir]
        # Note: Can't rely on Popen.check_call's logger argument, as
        # the setup-service-script relies on sending information to
        # stdout/stderr
        logging.debug('Calling %s', cmd)
        # SETUP_SPARC_SCRIPT does math processing that needs to run in "C"
        # locale to avoid problems with alternative # radix point
        # representations (e.g. ',' instead of '.' in cs_CZ.*-locales).
        # Because ksh script uses built-in math we need to set locale here and
        # we can't set it in script itself
        modified_env = os.environ.copy()
        lc_all = modified_env.get('LC_ALL', '')
        if lc_all != '':
            modified_env['LC_MONETARY'] = lc_all
            modified_env['LC_MESSAGES'] = lc_all
            modified_env['LC_COLLATE'] = lc_all
            modified_env['LC_TIME'] = lc_all
            modified_env['LC_CTYPE'] = lc_all
            del modified_env['LC_ALL']
        modified_env['LC_NUMERIC'] = 'C'
        Popen.check_call(cmd, env=modified_env)
        self._setup_install_conf()

    def _setup_install_conf(self):
        '''Creates the install.conf file, as needed for compatibility
        with older sparc clients

        '''
        if self.image.version < 3:
            # AI clients starting with this version use
            # system.conf as their source for the "install_service"
            # parameter during boot. The content of system.conf
            # is identical to the install.conf file used by prior
            # image versions; for compatibility with those older
            # clients, we create a symlink.
            #
            # Note that the symlink is created in the image path itself;
            # this implies that legacy sparc services CANNOT be
            # properly aliased - a client booting the alias would get
            # the service name for the base service.
            install_conf = os.path.join(self.image.path, "install.conf")
            system_conf = self.bootsource
            try:
                os.remove(install_conf)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
            os.symlink(system_conf, install_conf)

    def _init_service_config(self, hostname, port):
        '''Initialize this service's .config file. This should only be
        called during service creation, from AIService.create()

        '''
        txt_record = '%s=%s:%u' % (com.AIWEBSERVER, hostname, port)
        logging.debug("txt_record=%s", txt_record)

        service_data = {config.PROP_SERVICE_NAME: self.name,
                        config.PROP_TXT_RECORD: txt_record,
                        config.PROP_GLOBAL_MENU: True,
                        config.PROP_REVERIFY: False,
                        config.PROP_STATUS: config.STATUS_ON}

        if self._alias:
            service_data[config.PROP_ALIAS_OF] = self._alias
        else:
            service_data[config.PROP_IMAGE_PATH] = self.image.path

        if self.arch == 'i386' and self._bootargs:
            service_data[config.PROP_BOOT_ARGS] = self._bootargs
        if self.arch == 'sparc':
            service_data[config.PROP_GLOBAL_MENU] = False

        logging.debug("service_data=%s", service_data)

        config.create_service_props(self.name, service_data)

        return service_data

    def get_files_to_remove(self):
        '''Returns a list of file paths to clean up on service deletion.
        For version 1 services, this includes:
            * The mountpoint in /etc/netboot
            * The configuration directory in AI_SERVICE_DIR_PATH
            * The symlink from AI_SERVICE_DIR_PATH/<port> to the config dir,
              if applicable
            * The symlink from the webserver's docroot to the manifest dir

        '''
        files = [self.mountpoint,
                 self.config_dir,
                 os.path.join(AI_SERVICE_DIR_PATH,
                              config.get_service_port(self.name)),
                 os.path.join(com.WEBSERVER_DOCROOT, self.name)]

        if not self.is_alias():
            files.append(self.image.path)

            # must strip the leading path separator from image_path as
            # os.join won't concatenate two absolute paths
            webserver_path = os.path.join(com.WEBSERVER_DOCROOT,
                                          self.image.path.lstrip(os.sep))
            files.append(webserver_path)

            # find the longest empty path leading up to webserver image path
            if os.path.lexists(webserver_path):
                # get the parent dir of the webserver path
                directory = os.path.dirname(webserver_path)

                # iterate up the directory structure (toward / from the
                # image server's image path) adding empty directories
                while len(os.listdir(directory)) == 1:
                    # Go no further than webserver_base
                    if directory == com.WEBSERVER_DOCROOT:
                        break
                    files.append(directory)
                    directory = os.path.dirname(directory)
        else:
            if self.is_default_arch_service() and self.arch == 'sparc':
                self.delete_default_sparc_symlinks()

        return files

    def _setup_manifest_dir(self, new_name=None):
        '''Create a symlink in the AI webserver's docroot pointing to
        the directory containing this service's manifests

        '''
        if new_name is not None:
            try:
                os.remove(os.path.join(com.WEBSERVER_DOCROOT, self.name))
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
            data_dir = os.path.join(AI_SERVICE_DIR_PATH, new_name, "AI_data")
            linkname = os.path.join(com.WEBSERVER_DOCROOT, new_name)
        else:
            data_dir = self.manifest_dir
            linkname = os.path.join(com.WEBSERVER_DOCROOT, self.name)
        if os.path.islink(linkname) or os.path.exists(linkname):
            os.remove(linkname)
        os.symlink(data_dir, linkname)

    def _create_default_manifest(self):
        '''Create an initial, default manifest for the service (preferring
        the manifest contained in the image, but falling back to the one
        on the host system as necessary.

        The manifest directory is setup first, as well.
        (See _setup_manifest_dir)

        '''
        self._setup_manifest_dir()

        default_xml = os.path.join(self.image.path,
                                   IMG_AI_DEFAULT_MANIFEST)
        if not os.path.exists(default_xml):
            # Support older service images by checking for the
            # default manifest at the previous location.
            default_xml = os.path.join(self.image.path,
                                       OLD_IMG_AI_DEFAULT_MANIFEST)
            if not os.path.exists(default_xml):
                print (_("Warning: Using default manifest %s") %
                       SYS_AI_DEFAULT_MANIFEST)
                default_xml = SYS_AI_DEFAULT_MANIFEST

        manifest_name = "orig_default"
        data = DataFiles.from_service(self,
                                      manifest_file=default_xml,
                                      manifest_name=manifest_name,
                                      set_as_default=True)
        insert_SQL(data)
        manifest_path = os.path.join(self.manifest_dir, manifest_name)
        place_manifest(data, manifest_path)
        self.set_default_manifest(manifest_name)

    def set_default_manifest(self, manifest_name, skip_manifest_check=False):
        '''Make manifest "manifest_name" the default for this service'''
        if not skip_manifest_check:
            manifest_path = "/".join([self.manifest_dir, manifest_name])
            if not os.path.isfile(manifest_path):
                raise ValueError(_("\nManifest '%s' does not exist.\n") %
                                 manifest_path)

        config.set_service_props(self.name,
                                 {config.PROP_DEFAULT_MANIFEST: manifest_name})

    def get_default_manifest(self):
        '''Return the name of the default for this service'''
        props = config.get_service_props(self.name)
        return props[config.PROP_DEFAULT_MANIFEST]

    def relocate_imagedir(self, new_path):
        '''Change the location of a service's image:
             o disable the service and all dependent aliases
             o update wanboot.conf for the service (sparc)
             o update grub config files of service and its clients
               and aliases (x86)
             o update service .config file
             o move the image and update webserver symlink
             o enable service and dependent aliases
        '''
        was_mounted = False
        if self.mounted():
            was_mounted = True
            self.disable(force=True)

        # get list of all aliases
        all_aliases = config.get_aliased_services(self.name, recurse=True)

        # Determine which aliases are enabled and disable them,
        # saving list of enabled aliases for later.
        enabled_aliases = list()
        for alias in all_aliases:
            aliassvc = AIService(alias)
            if aliassvc.mounted():
                enabled_aliases.append(alias)
                aliassvc.disable(force=True)

        # For x86, update grub config files of service, clients, and
        # aliases with the new imagepath.
        # For sparc, update wanboot.conf with the new imagepath.
        # There is nothing to do for sparc aliases or clients because they
        # reference the service's wanboot.conf file.
        if self.arch == 'i386':
            svcgrub = grubcfg(self.name, path=self.image.path,
                              config_dir=self.config_dir)

            svcgrub.update_imagepath(self.image.path, new_path)

            all_clients = config.get_clients(self.name).keys()
            for alias in all_aliases:
                all_clients.extend(config.get_clients(alias).keys())

            for clientid in all_clients:
                clientgrub = grubcfg(self.name, path=self.image.path,
                                     config_dir=self.config_dir)
                clientgrub.update_imagepath(self.image.path, new_path,
                                            mac_address=clientid[2:])
            for alias in all_aliases:
                aliassvc = AIService(alias)
                aliasgrub = grubcfg(alias, path=aliassvc.image.path,
                                    config_dir=aliassvc.config_dir)
                aliasgrub.update_imagepath(aliassvc.image.path, new_path)
        elif self.arch == 'sparc':
            self.update_wanboot_imagepath(self.image.path, new_path)

        # update image_path in .config file
        self._update_path_in_service_props(new_path)

        # relocate image and update webserver symlinks
        self.image.move(new_path)

        # enable service and aliases
        if was_mounted:
            self.enable()
        for alias in enabled_aliases:
            AIService(alias).enable()


def get_a_free_tcp_port(hostname):
    ''' get next free tcp port

        Looks for next free tcp port number, starting from 46501

        Input:   hostname
        Returns: next free tcp port number if one found or
                 None if no free port found

    '''
    # determine ports in use by other install services
    existing_ports = set()
    allprops = config.get_all_service_names()
    for svcname in allprops:
        port = config.get_service_port(svcname)
        existing_ports.add(int(port))

    logging.debug("get_a_free_tcp_port, existing_ports=%s", existing_ports)

    mysock = None
    for port in xrange(STARTING_PORT, ENDING_PORT):
        try:
            # skip ports of existing install services
            if port in existing_ports:
                continue
            mysock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            mysock.bind((hostname, port))
        except socket.error:
            continue
        else:
            logging.debug("found free tcp port: %s" % port)
            mysock.close()
            break
    else:
        logging.debug("no available tcp port found")
        return None

    return port


_DHCP_MSG = """No local DHCP configuration found. This service is the default
alias for all %s clients. If not already in place, the following should
be added to the DHCP configuration:"""


def setup_dhcp_server(service, ip_start, ip_count, bootserver):
    '''Set-up DHCP server for given AI service and IP address range'''

    _incomplete_msg = cw(_("\nThe install service has been created but the "
                           "DHCP configuration has not been completed. Please "
                           "see dhcpd(8) for further information.\n"))

    arch = service.arch
    logging.debug("setup_dhcp_server: ip_start=%s, ip_count=%s, arch=%s",
                  ip_start, ip_count, arch)

    server = dhcp.DHCPServer()
    svc_cmd = False
    if ip_count:
        # The end-user has requested that DHCP be configured on this server
        # by passing the IP start and IP count arguments. We will add to the
        # configuration and then take the proper action for the SMF service.
        if server.is_online():
            # DHCP server is configured and running. We will add to the
            # configuration and then restart the SMF service.
            svc_cmd = 'restart'
        else:
            if not server.is_configured():
                # We need to configure and enable a new DHCP server. Lay the
                # base configuration down and then enable the SMF service.
                # Note we will not enable an existing DHCP configuration if the
                # SMF service is offline.
                print cw(_("\nStarting DHCP server..."))
                server.init_config()
                svc_cmd = 'enable'

        try:
            print cw(_("Adding IP range to local DHCP configuration"))
            server.add_address_range(ip_start, ip_count, bootserver)
        except dhcp.DHCPServerError as err:
            print >> sys.stderr, cw(_("\nUnable to add IP range: %s\n" % err))
            print >> sys.stderr, _incomplete_msg
            return

    # Regardless of whether the IP arguments are passed or not, now check the
    # current DHCP configuration for default service configuration. If we're
    # creating a new default alias for this architecture, set this service's
    # bootfile as the default in the DHCP local server.
    if arch == 'sparc':
        bootfile = service.dhcp_bootfile_sparc
        bfile = dhcp.fixup_sparc_bootfile(bootfile)
        client_type = 'SPARC'
    else:
        # create new tuple list containing only the arch val and relpath
        # i.e., go from entries of (dhcparch, archtype, relpath to nbp) to
        # (dhcparch, relpath to nbp)
        bootfile = service.boot_tuples
        bootfile_tuples = zip(*service.boot_tuples)
        bootfile_tuples = zip(bootfile_tuples[0], bootfile_tuples[2])
        bfile = ''
        for archval, archtype, relpath in service.boot_tuples:
            line = ('    ' + archtype + ' clients (arch ' + archval + '):  ' +
                     relpath + '\n')
            bfile = bfile + line
        client_type = 'PXE'

    logging.debug("setup_dhcp_server: bootfile=%s, bfile=\n%s",
                  bootfile, bfile)

    if server.is_configured():
        if service.is_default_arch_service():
            try:
                if arch == 'i386':
                    # add the arch option if needed
                    server.add_option_arch()
                if server.arch_class_is_set(arch):
                    # There is a class for this architecture already in place
                    cur_bootfile = server.get_bootfile_for_arch(arch)
                    logging.debug('cur_bootfile is %s', cur_bootfile)
                    if cur_bootfile is None:
                        # No bootfile set for this arch
                        print cw(_("Setting the default %(type)s bootfile in "
                                   "the local DHCP configuration to "
                                   "'%(bfile)s'\n") % {'type': client_type, \
                                   'bfile': bfile})
                        server.add_bootfile_to_arch(arch, bootfile)
                    elif ((arch == 'sparc' and cur_bootfile != bfile) or
                          (arch == 'i386' and sorted(bootfile_tuples) !=
                           sorted(cur_bootfile))):
                        # Update the existing bootfile to our default
                        print cw(_("Updating the default %(type)s bootfile in "
                                   "the local DHCP configuration from "
                                   "'%(bootfile)s' to '%(bfile)s'\n ") %
                                   {'type': client_type, \
                                    'bootfile': cur_bootfile, 'bfile': bfile})
                        server.update_bootfile_for_arch(arch, bootfile)
                else:
                    # Set up a whole new architecture class
                    print cw(_("Setting the default %(type)s bootfile in the "
                               "local DHCP configuration to '%(bfile)s'\n") %
                               {'type': client_type, 'bfile': bfile})
                    server.add_arch_class(arch, bootfile)

            except dhcp.DHCPServerError as err:
                print >> sys.stderr, cw(_("Unable to update the local DHCP "
                                          "configuration: %s\n" % err))
                print >> sys.stderr, _incomplete_msg
                return

            # Make sure we kick the DHCP server, if needed
            if server.is_online and not svc_cmd:
                svc_cmd = 'restart'

        # Configuration is complete, update the SMF service accordingly
        if svc_cmd:
            try:
                server.control(svc_cmd)
            except dhcp.DHCPServerError as err:
                print >> sys.stderr, cw(_("\nUnable to update the DHCP SMF "
                                          "service after reconfiguration: "
                                          "%s\n" % err))
                print >> sys.stderr, cw(_("\nThe install service has been "
                                          "created and the DHCP configuration "
                                          "has been updated, however the DHCP "
                                          "SMF service requires attention. "
                                          "Please see dhcpd(8) for further "
                                          "information.\n"))
    elif service.is_default_arch_service():
        # DHCP configuration is not local and this is the default service for
        # this this architecture. Provide DHCP boot configuration information.
        valid_nets = list(com.get_valid_networks())
        if valid_nets:
            server_ip = valid_nets[0]

        print _(_DHCP_MSG % client_type)

        if arch == 'i386':
            # Boot server IP is not needed for SPARC clients
            print _("\t%-20(msg)s : %(ip)s" % {'msg': "Boot server IP", \
                    'ip': server_ip})
            print _("\t%-20(msg)s : %(bootfile)s\n" % {'msg': "Boot file", \
                    'bootfile': bfile})
        else:
            print _("%s: %s\n" % ("Boot file", bfile))

        if len(valid_nets) > 1 and arch == 'i386':
            print cw(_("\nNote: determined more than one IP address "
                       "configured for use with AI. Please ensure the above "
                       "'Boot server IP' is correct.\n"))


if __name__ == '__main__':
    if sys.argv[1] == "mount-all":
        sys.exit(mount_enabled_services())
    elif sys.argv[1] == "remount":
        sys.exit(mount_enabled_services(remount=True))
    elif sys.argv[1] == "unmount-all":
        sys.exit(unmount_all())
    else:
        sys.exit("Invalid arguments")
