#! /usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
Loader backend for the SPARC Boot Block (SBB)
"""

import grp
import os
import pwd
import shutil
import tempfile
from ... import BootmgmtError, BootmgmtUnsupportedPlatformError
from ... import BootmgmtConfigWriteError
from ...bootloader import BootLoader, BootLoaderInstallError
from ...bootconfig import BootConfig, DiskBootConfig, SolarisDiskBootInstance
from ...bootutil import get_current_arch_string
from .menulst import MenuDotLst, MenuLstError, MenuLstMenuEntry, MenuLstCommand
from .menulst import MenuLstBootLoaderMixIn
from ...pysol import platform_name, machine_name
from solaris_install import Popen, CalledProcessError

class OBPBootLoader(BootLoader):
    @staticmethod
    def probe_generic(**kwargs):
        """Generic probe checks for OBP boot loaders"""
        if get_current_arch_string() != 'sparc':
            raise BootmgmtUnsupportedPlatformError('SPARC-only')


class WanbootBootLoader(OBPBootLoader):
    @staticmethod
    def probe(**kwargs):
        return (None, None)


class HSFSBootLoader(OBPBootLoader):
    @staticmethod
    def probe(**kwargs):
        return (None, None)


class UFSBootLoader(OBPBootLoader):
    @staticmethod
    def probe(**kwargs):
        return (None, None)


class ZFSBootLoader(OBPBootLoader, MenuLstBootLoaderMixIn):

    MENU_LST_PATH = '/boot/menu.lst'

    BOOTLST_PATH = '/platform/%(mach)s/bootlst'
    BOOTLST_OWNER = 'root'
    BOOTLST_GROUP = 'sys'
    BOOTLST_PERMS = 0644

    WEIGHT = 1
    BOOTBLK_PATH = '/usr/platform/%(platformname)s/lib/fs/zfs/bootblk'
    INSTALLBOOT_NOUPDT = 4

    @staticmethod
    def probe(**kwargs):
        """Probe for ZFS boot block files for use with the BootConfig passed
        in"""

        try:
            OBPBootLoader.probe_generic(**kwargs)
        except BootmgmtError:
            return (None, None)

        bootconfig = kwargs.get('bootconfig', None)

        if (bootconfig is None or bootconfig.boot_class is None):
            return (None, None)

        if (bootconfig.boot_class == BootConfig.BOOT_CLASS_DISK and
            bootconfig.boot_fstype == 'zfs'):
            return ZFSBootLoader._probe_disk(**kwargs)
        else:
            raise BootmgmtUnsupportedOperationError('ZFSBootLoader only '
                                      'supports ZFS-based disk boot '
                                      'configurations')

    @classmethod
    def _probe_disk(cls, **kwargs):
        """This ZFS boot block probe function searches the ZFS top-level dataset
        for a menu.lst file.  If that's not present, we search the system root
        for the ZFS boot block file,
        usr/platform/{platform-name}/lib/fs/zfs/bootblk
        """
 
        bootconfig = kwargs.get('bootconfig', None)

        menuroot = bootconfig.zfstop
        dataroot = bootconfig.get_root()

        if menuroot is None or dataroot is None:
            raise BootmgmtNotSupportedError('menuroot or dataroot is None')

        cls._debug('_probe_disk():'
                   ' menuroot=%s, dataroot=%s' % (menuroot, dataroot))

        menulst = menuroot + ZFSBootLoader.MENU_LST_PATH
        try:
            open(menulst).close()
        except IOError as ioerr:
            cls._debug(('Error opening %s: ' % menulst) + ioerr.strerror)

        bootblk = dataroot
        bootblk += (ZFSBootLoader.BOOTBLK_PATH %
                    {'platformname' : platform_name()})
        cls._debug('Trying to find ' + bootblk)
        try:
            open(bootblk).close()
        except IOError as ioerr:
            cls._debug(str(ioerr))
            # Probe failed:
            return (None, None)

        # XXX - In addition to the loader files themselves, we need to ensure
        # XXX - that we have access to the installboot program in the currently
        # XXX - running system (otherwise, we'll have no way to install the
        # XXX - bootblk).

        return (ZFSBootLoader(**kwargs), ZFSBootLoader.WEIGHT)

    def __init__(self, **kwargs):
        """Constructor for ZFSBootLoader"""
        self.pkg_names = ['system/library/processor', 'SUNWcar']
        self.name = 'SPARC ZFS Boot Block'
        super(ZFSBootLoader, self).__init__(**kwargs)
        self._bl_props[BootLoader.PROP_BOOT_TARGS] = 'obp'

    def new_config(self):
        """The configuration for the ZFS boot block consists solely of the
        menu.lst file.  The default new configuration is an empty menu.lst file.
        """

        super(ZFSBootLoader, self).new_config()

    def load_config(self):
        """Load boot instances from the menu.lst file"""
        if self._boot_config.boot_class == BootConfig.BOOT_CLASS_DISK:
            self._load_config_disk()
            self.dirty = False  # We just loaded a clean config from disk!
        else:
            raise BootmgmtUnsupportedOperationError('Unsupported boot class: ' +
                  self._boot_config.boot_class)

    def _write_config(self, basepath):
        """There are two files that need to be written: the menu.lst file, using
        information from the BootConfig instance to which we have a reference,
        and the bootlst program (which will be copied from the data source
        boot instance's mounted filesystem.)
        """

        if self._boot_config is None:
            msg = 'Cannot _write_config(%s) - _boot_config is None' % basepath
            self._debug(msg)
            raise BootmgmtInterfaceCodingError(msg)
        elif self._boot_config.boot_class != BootConfig.BOOT_CLASS_DISK:
            msg = 'ZFS boot block boot loader does not support non-disk configs'
            raise BootmgmtUnsupportedOperationError(msg)

        return self._write_config_disk(basepath)


    def _zfs_boot_data_rootdir_disk(self):
        if self._boot_config.boot_fstype != 'zfs':
            raise BootmgmtUnsupportedOperationError('Filesystem %s not '
                  'supported by the ZFS boot block' %
                  self._boot_config.boot_fstype)

        return self._boot_config.zfstop

    def _load_config_disk(self):

        menu_lst = (self._zfs_boot_data_rootdir_disk() +
                   ZFSBootLoader.MENU_LST_PATH)

        try:
            menufile = SPARCMenuFile(menu_lst)
        except IOError as err:
            raise BootmgmtConfigReadError('Error while processing the %s '
                                          'file' % menu_lst, err)
        except MenuLstError as err:
            raise BootmgmtConfigReadError('Error while processing the %s '
                                          'file: %s' % (menu_lst, str(err)))

        boot_instances = []
        # Extract the properties and entries from the parsed file:
        for entity in menufile.entities():
            if not isinstance(entity, MenuLstMenuEntry):
                # Not supported, but don't raise an exception
                self._debug('Found something that was not a menu entry in '
                            'menu.lst: [[%s]]' % str(entity))
                continue

            # Menu entry found -- we only care about title and bootfs:
            bootfs = entity.find_command('bootfs')

            if bootfs is None:
                self._debug('Malformed menu entry found: %s' % str(entity))
                continue

            inst = SolarisDiskBootInstance(None,
                      fstype='zfs',
                      title=' '.join(entity.find_command('title').get_args()),
                      bootfs=' '.join(bootfs.get_args()))

            boot_instances += [inst]

        # Add the boot instances to the BootConfig instance:
        self._boot_config.add_boot_instance(boot_instances)

    def _write_config_disk(self, basepath):
        """Write the boot loader's configuration file and boot program to
        disk"""

        if self._boot_config.boot_fstype != 'zfs':
            raise BootmgmtUnsupportedOperationError('Filesystem type %s '
                                'not supported by the SPARC ZFS boot block'
                                % fstype)

        dataroot_dir = self._zfs_boot_data_rootdir_disk()

        generic_tuples = self._write_config_generic(basepath, dataroot_dir)

        bootlst_tuples = self._write_bootlst(basepath, dataroot_dir)

        if basepath is None:
            return None

        tuples = []
        if generic_tuples is not None:
            tuples += generic_tuples
        if bootlst_tuples is not None:
            tuples += bootlst_tuples

        for idx, item in enumerate(tuples):
            if (item[BootConfig.IDX_FILETYPE] == BootConfig.OUTPUT_TYPE_FILE
               and
               item[BootConfig.IDX_DESTNAME] in
                (ZFSBootLoader.MENU_LST_PATH, ZFSBootLoader.BOOTLST_PATH)):

                # Make a copy of the tuple so we can change it:
                item = list(item)

                item[BootConfig.IDX_DESTNAME] = (
                    '%(' + DiskBootConfig.TOKEN_ZFS_RPOOL_TOP_DATASET + ')s'
                    + item[BootConfig.IDX_DESTNAME])

                # Update tuple in the list:
                tuples[idx] = tuple(item)

        return tuples

    def _write_bootlst(self, basepath, boot_data_root_dir):
        """Copy the bootlst program from the root of the data source boot
        instance to either the basepath or the boot_data_root_dir and
        return a tuple describing it."""

        bootlst = ZFSBootLoader.BOOTLST_PATH % { 'mach' : machine_name() }

        source = os.path.join(self._get_boot_loader_data_root(), bootlst)

        if basepath is None:
            destination = boot_data_root_dir + bootlst
        else:
            try:
                tmpfile = tempfile.NamedTemporaryFile(dir=basepath,
                                                      delete=False)
                destination = tmpfile.name
                tmpfile.close()
            except IOError as err:
                raise BootmgmtConfigWriteError("Couldn't create a temporary "
                      'file for bootlst', err)
                return []
            
        try:
            shutil.copy(source, destination)
            self._debug('bootlst copied to %s' % destination)
        except IOError as err:
            try:
                os.remove(destination)
            except OSError as oserr:
                self._debug('Error while trying to remove %s: %s' %
                            (destination, oserr.strerror))
            raise BootmgmtConfigWriteError("Couldn't copy %s to %s" %
                                           (source, destination), err)

        if basepath is None:
            # Copy was successful, so now set the owner and mode properly:
            try:
                os.chmod(destination, ZFSBootLoader.BOOTLST_PERMS)
                os.chown(destination,
                         pwd.getpwnam(ZFSBootLoader.BOOTLST_OWNER).pw_uid,
                         grp.getgrnam(ZFSBootLoader.BOOTLST_GROUP).gr_gid)
            except OSError as oserr:
                raise BootmgmtConfigWriteError("Couldn't set mode/perms on "
                      + destination, oserr)

            return []
        else:
            return [(BootConfig.OUTPUT_TYPE_FILE,
                    tmpfile.name,
                    None,
                    ZFSBootLoader.BOOTLST_PATH,
                    ZFSBootLoader.BOOTLST_OWNER,
                    ZFSBootLoader.BOOTLST_GROUP,
                    ZFSBootLoader.BOOTLST_PERMS)]


    def _write_menu_lst(self, outfile):
        """Invoked by the MenuLstBootLoaderMixIn.
        The SPARC menu.lst is very, very simple.  We don't need to
        support comments or other in-place editing complexities.  Just
        blast out the title/bootfs pairs."""

        for inst in self._boot_config.boot_instances:
            if (getattr(inst, 'bootfs', None) is None or
                getattr(inst, 'title', None) is None):
                self._debug('Boot instance missing title or bootfs: %s'
                            % str(inst))
                continue

            outfile.write('title ' + inst.title + '\n'
                          'bootfs ' + inst.bootfs + '\n')

    # Property-related methods
    def _prop_validate(self, key, value=None, validate_value=False):
        if key == BootLoader.PROP_BOOT_TARGS:
            if validate_value and value != 'obp':
                raise BootmgmtUnsupportedPlatformError(value + ' is not a '
                      'supported firmware type for ' + self.__class__.__name__)
            return
        super(self.__class__, self)._prop_validate(key, value, validate_value)

    # BootLoader installation methods

    def install(self, location):
        return self._install_generic(location)

    # _write_loader performs the real guts of boot loader installation
    def _write_loader(self, devname, data_root):
        """Invoked by the MenuLstBootLoaderMixIn.
        Invoke installboot to write the bootblk to disk."""

        args = ['/sbin/installboot', '-F', 'zfs']

        # If a version is present, try to use it during installation
        if self.version is not None:
            args += ['-u', self.version]

        args += [data_root + (ZFSBootLoader.BOOTBLK_PATH %
                              {'platformname' : platform_name() }),
                 devname]

        self._debug('_write_loader: Invoking command: ' + ' '.join(args))

        try:
            Popen.check_call(args, stdout=Popen.STORE, stderr=Popen.STORE)
        except CalledProcessError as cpe:
            self._debug('_write_loader: Return code = %d' % cpe.returncode)
            if cpe.returncode != ZFSBootLoader.INSTALLBOOT_NOUPDT:
                output = ''
                if cpe.popen is not None and cpe.popen.stderr is not None:
                    output = '\nOutput was:\n' + cpe.popen.stderr
                raise BootLoaderInstallError('installboot failed for '
                      'device ' + devname + ': Return code ' +
                      str(cpe.returncode) + output)
        except OSError as ose:
                raise BootLoaderInstallError('Error while trying to '
                      'invoke installboot for '
                      'device ' + devname + ': ' + str(ose))


class SPARCMenuFile(MenuDotLst):
    def __init__(self, filename='/rpool/boot/menu.lst'):
        super(SPARCMenuFile, self).__init__(filename)

    def _analyze_syntax(self):
        """
        Start        := Commands
        Commands     := Command Commands | Command
        Command      := TitleLine BootfsLine
        TitleLine    := 'title' [ \t]+ Arguments
        BootfsLine   := 'bootfs' [ \t]+ BootFsSpec
        Arguments    := Arguments [ \t]+ Argument | Argument
        Argument     := [^ \t\n]+
        BootFsSpec   := ZpoolSpec '/ROOT/' ZfsSpec
        ZpoolSpec    := see zpool(1M)
        ZfsSpec      := see zfs(1M)
        """
        # XXX - Currently a NOP



def bootloader_classes():
    return [WanbootBootLoader, HSFSBootLoader, UFSBootLoader, ZFSBootLoader]
