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
Legacy GRUB BootLoader Implementation for pybootmgmt
"""

import tempfile
import shutil
import os
import gettext
import stat
import re

from bootmgmt.backend.loader.menulst import (MenuDotLst, MenuLstError,
                                             MenuLstMenuEntry, MenuLstCommand,
                                             MenuLstBootLoaderMixIn)
from bootmgmt.bootloader import BootLoader, BootLoaderInstallError
from bootmgmt.bootconfig import (BootConfig, DiskBootConfig, BootInstance,
                                 SolarisDiskBootInstance)
from bootmgmt.bootconfig import ChainDiskBootInstance
from bootmgmt.bootutil import get_current_arch_string
from bootmgmt.pysol import (libzfs_init, libzfs_fini, zpool_open, zpool_close,
                            zpool_get_physpath, zpool_set_prop, zpool_get_prop,
                            ZPOOL_PROP_BOOTFS, libzfs_error_description)
from bootmgmt import (BootmgmtArgumentError,
                      BootmgmtUnsupportedOperationError,
                      BootmgmtInterfaceCodingError,
                      BootmgmtIncompleteBootConfigError,
                      BootmgmtConfigReadError,
                      BootmgmtConfigWriteError,
                      BootmgmtMalformedPropertyValueError,
                      BootmgmtUnsupportedPlatformError,
                      BootmgmtNotSupportedError,
                      BootmgmtUnsupportedPropertyError)
from solaris_install import Popen, CalledProcessError

_ = gettext.translation('SUNW_OST_OSCMD', '/usr/lib/locale',
    fallback=True).gettext


class LegacyGRUBBootLoader(BootLoader, MenuLstBootLoaderMixIn):
    """Implementation of a Legacy GRUB (GRUB 0.97) BootLoader.  Handles parsing
    the menu.lst file (reading and writing), though reading it and creating
    BootInstance objects is rather fragile"""

    WEIGHT = 1  # Legacy GRUB's probe weight

    MENU_LST_PATH = '/boot/grub/menu.lst'

    DEFAULT_GRUB_SPLASH = '/boot/grub/splash.xpm.gz'
    DEFAULT_TIMEOUT = 30         # 30 seconds is the default timeout
    DEFAULT_FORECOLOR = '343434'
    DEFAULT_BACKCOLOR = 'F7FBFF'

    # This dict is applied to the menu.lst template (below)
    DEFAULT_PROPDICT = {
             'default': 'default 0',
             'timeout': 'timeout ' + str(DEFAULT_TIMEOUT),
              'serial': '#   serial --unit=0 --speed=9600',
            'terminal': '#   terminal serial',
         'splashimage': '#   splashimage ' + DEFAULT_GRUB_SPLASH,
          'foreground': '#   foreground ' + DEFAULT_FORECOLOR,
          'background': '#   background ' + DEFAULT_BACKCOLOR,
            'minmem64': '#',
          'hiddenmenu': '#'}

    INSTALLGRUB_NOUPDT = 4       # from src/cmd/boot/common/boot_utils.h
    INSTALLGRUB_NOEINFO = 6      # (ditto)

    # Supported properties for setprop()
    SUPPORTED_PROPS = [
      BootLoader.PROP_CONSOLE,
      BootLoader.PROP_SERIAL_PARAMS,
      BootLoader.PROP_MINMEM64,
      BootLoader.PROP_TIMEOUT,
      BootLoader.PROP_QUIET,
      BootLoader.PROP_SPLASH,
      BootLoader.PROP_FORECOLOR,
      BootLoader.PROP_BACKCOLOR
    ]

    # Template for NEW menu.lst files:
    MENU_LST_PREAMBLE = (
r"""# default menu entry to boot
%(default)s
#
# menu timeout in second before default OS is booted
# set to -1 to wait for user input
%(timeout)s
#
# To enable grub serial console to ttya uncomment the following lines
# and comment out the splashimage line below
# WARNING: do not enable grub serial console when BIOS console serial
#       redirection is active.
%(serial)s
%(terminal)s
#
# Uncomment the following line to enable GRUB splashimage on console
%(splashimage)s
%(foreground)s
%(background)s
#
# To chainload another OS
#
# title Another OS
#       root (hd<disk no>,<partition no>)
#       chainloader +1
#
# To chainload a Solaris release not based on GRUB:
#
# title Solaris 9
#       root (hd<disk no>,<partition no>)
#       chainloader +1
#       makeactive
#
# To load a Solaris instance based on GRUB:
#
# title Solaris <version>
#       bootfs <poolname>/ROOT/<BE_name>
#       kernel /platform/i86pc/kernel/amd64/unix
#       module /platform/i86pc/amd64/boot_archive

#
# To override Solaris boot args (see kernel(1M)), console device and
# properties set via eeprom(1M) edit the "kernel" line to:
#
#   kernel /platform/i86pc/kernel/amd64/unix <boot-args> -B prop=value,...
#
%(hiddenmenu)s
%(minmem64)s
""")

    @classmethod
    def probe(cls, **kwargs):
        """Probe for Legacy GRUB files for use with the BootConfig passed
        in"""

        if get_current_arch_string() != 'x86':
            cls._debug('Legacy GRUB boot loader not supported on this '
                       'platform')
            return (None, None)

        bootconfig = kwargs.get('bootconfig', None)

        if (bootconfig is None or bootconfig.boot_class is None):
            return (None, None)

        if (bootconfig.boot_class == BootConfig.BOOT_CLASS_DISK and
           bootconfig.boot_fstype is not None):
            return LegacyGRUBBootLoader._probe_disk(**kwargs)
        elif bootconfig.boot_class == BootConfig.BOOT_CLASS_ODD:
            return LegacyGRUBBootLoader._probe_odd(**kwargs)
        else:
            raise BootmgmtUnsupportedOperationError('XXX - Fix Me')

    @classmethod
    def _probe_odd(cls, **kwargs):
        """This Legacy GRUB probe function searches the ODD's root, looking for
        the Legacy GRUB menu.lst and stage1 and stage2 files"""

        bootconfig = kwargs.get('bootconfig', None)

        root = bootconfig.get_root()

        cls._debug('_probe_odd(): odd_image_root=%s' % root)

        try:
            cls._probe_generic(root, root,
                               ['stage2_eltorito'])
        except BootmgmtNotSupportedError:
            return (None, None)

        return (LegacyGRUBBootLoader(**kwargs), LegacyGRUBBootLoader.WEIGHT)

    @classmethod
    def _probe_disk(cls, **kwargs):
        """This Legacy GRUB probe function searches the ZFS top-level dataset
        for a menu.lst file.  If that's not present, we search the system root
        for /boot/grub/stage1 and /boot/grub/stage2 -- essential files that
        should exist if Legacy GRUB is the active boot loader.
        """
 
        bootconfig = kwargs.get('bootconfig', None)

        fstype = bootconfig.boot_fstype

        if fstype == 'ufs':
            menuroot = bootconfig.get_root()
            dataroot = menuroot
        elif fstype == 'zfs':
            menuroot = bootconfig.zfstop
            dataroot = bootconfig.get_root()
        else:
            return (None, None)

        cls._debug('_probe_disk():'
                   ' menuroot=%s, dataroot=%s' % (menuroot, dataroot))

        try:
            cls._probe_generic(menuroot, dataroot,
                               ['stage1', 'stage2'])
        except BootmgmtNotSupportedError:
            return (None, None)

        # XXX - In addition to the loader files themselves, we need to ensure
        # XXX - that we have access to the installgrub program in the currently
        # XXX - running system (otherwise, we'll have no way to install Legacy
        # XXX - GRUB).

        return (LegacyGRUBBootLoader(**kwargs), LegacyGRUBBootLoader.WEIGHT)

    @classmethod
    def _probe_generic(cls, menuroot, dataroot, datafiles):

        # Both the menu root and the data root locations must be specified
        if menuroot is None or dataroot is None:
            raise BootmgmtNotSupportedError('menuroot or dataroot is None')

        menulst = menuroot + LegacyGRUBBootLoader.MENU_LST_PATH
        try:
            open(menulst).close()
        except IOError as ioerr:
            cls._debug(('Error opening %s: ' % menulst) + ioerr.strerror)

        try:
            for datafile in datafiles:
                open(dataroot + '/boot/grub/' + datafile).close()
        except IOError as ioerr:
            cls._debug(str(ioerr))
            raise BootmgmtNotSupportedError('IOError when checking for '
                                            'datafiles')

    def __init__(self, **kwargs):
        self.pkg_names = ['system/boot/grub', 'SUNWgrub']
        self.name = 'Legacy GRUB'
        self._menufile = None
        super(LegacyGRUBBootLoader, self).__init__(**kwargs)
        self._bl_props[BootLoader.PROP_BOOT_TARGS] = 'bios'

    def new_config(self):
        """The configuration for Legacy GRUB consists solely of the menu.lst
        file.  The default new configuration is an empty menu.lst file,
        with a graphical splashscreen and appropriate fore/back colors."""

        super(LegacyGRUBBootLoader, self).new_config()
        # Set boot loader default properties after the config reset:
        self._bl_props[BootLoader.PROP_CONSOLE] = BootLoader.PROP_CONSOLE_GFX
        self._menufile = None

    def load_config(self):
        """Load boot instances and GRUB properties from the menu.lst file"""
        if self._boot_config.boot_class == BootConfig.BOOT_CLASS_DISK:
            self._load_config_disk()
            self.dirty = False  # We just loaded a clean config from disk!
        else:
            raise BootmgmtUnsupportedOperationError('XXX - Fix Me')

    def _write_config(self, basepath):
        """The only file that needs to be written is the menu.lst file, using
        information from the BootConfig instance to which we have a reference.
        Information from the boot loader's properties is also used to
        determine which commands are emitted at the global level"""

        if self._boot_config is None:
            msg = ('Cannot _write_config(%s) - _boot_config is None' %
                  str(basepath))
            self._debug(msg)
            raise BootmgmtInterfaceCodingError(msg)

        # Determine the type of boot configuration we're dealing with, then
        # determine the filesystem type that will hold the menu.lst.  Only
        # then can we tell the caller the appropriate path to copy it into.
        if self._boot_config.boot_class == BootConfig.BOOT_CLASS_DISK:
            return self._write_config_disk(basepath)
        elif self._boot_config.boot_class == BootConfig.BOOT_CLASS_ODD:
            return self._write_config_odd(basepath)
        else:
            raise BootmgmtUnsupportedOperationError('XXX - Fix Me')

    # Legacy GRUB methods for dealing with a disk-based BootConfig
    def _menu_lst_dir_disk(self):
        fstype = self._boot_config.boot_fstype
        if fstype != 'zfs' and fstype != 'ufs':
            raise BootmgmtUnsupportedOperationError('Unknown filesystem: %s'
                                                     % fstype)
        if fstype == 'zfs':
            menu_lst_dir = self._boot_config.zfstop
        elif fstype == 'ufs':
            menu_lst_dir = self._boot_config.get_root()

        return menu_lst_dir

    @staticmethod
    def _derive_bootfs(argdict):
        # Derive the bootfs for the specified pool and
        # add it to the argdict:
        lzfsh = libzfs_init()
        zph = zpool_open(lzfsh, argdict['rpool'])
        if zph is None:
            raise BootmgmtIncompleteBootConfigError(
                  'Cannot open zpool %s specified in findroot '
                  'directive!' % argdict['rpool'])
  
        pool_default_bootfs = zpool_get_prop(lzfsh, zph,
                                             ZPOOL_PROP_BOOTFS)
        zpool_close(zph)
        libzfs_fini(lzfsh)

        if pool_default_bootfs is not None:
            argdict['bootfs'] = pool_default_bootfs
        else:
            raise BootmgmtIncompleteBootConfigError(
                     'Could not determine default bootfs for zpool %s '
                     'specified in findroot directive!' % argdict['rpool'])

    def _load_config_disk(self):

        menu_lst = (self._menu_lst_dir_disk() +
                   LegacyGRUBBootLoader.MENU_LST_PATH)
        try:
            self._menufile = LegacyGRUBMenuFile(menu_lst)
        except IOError as err:
            raise BootmgmtConfigReadError('Error while processing the %s \
                                           file' % menu_lst, err)
        except MenuLstError as err:
            raise BootmgmtConfigReadError('Error while processing the %s '
                                          'file: %s' % (menu_lst, str(err)))

        default_index = None
        boot_instances = []
        # Extract the properties and entries from the parsed file:
        for entity in self._menufile.entities():
            if isinstance(entity, MenuLstMenuEntry):
                # Make sure we have everything first:
                # XXX - Recognize non-disk boot instances in the menu.lst
                argdict = {}
                if (entity.find_command('bootfs') is not None or
                    entity.find_command('findroot') is not None):
                    for cmd in entity.commands():
                        # Skip non-commands
                        if not isinstance(cmd, MenuLstCommand):
                            continue

                        if cmd.get_command() == 'title':
                            argdict['title'] = ' '.join(cmd.get_args())
                        elif ((cmd.get_command() == 'kernel$' or
                            cmd.get_command() == 'kernel') and
                            len(cmd.get_args()) > 0):
                            argdict['kernel'] = cmd.get_args()[0]
                            argdict['kargs'] = ' '.join(cmd.get_args()[1:])
                        elif (cmd.get_command() == 'module$' or
                              cmd.get_command() == 'module'):
                            argdict['boot_archive'] = ' '.join(cmd.get_args())
                        elif cmd.get_command() == 'bootfs':
                            argdict['bootfs'] = ' '.join(cmd.get_args())
                            argdict['fstype'] = 'zfs'
                        elif cmd.get_command() == 'findroot':
                            # XXX - Handle "BE_XXXX" and other hints
                            argstring = ''.join(cmd.get_args())
                            (pool, subs) = re.subn(
                                        r'.*pool_([^,)]+).*', r'\1', argstring)
                            if subs > 0:
                                argdict['signature'] = 'pool_' + pool
                                argdict['rpool'] = pool
                                argdict['fstype'] = 'zfs'
                            else:
                                # This is either an erroneous or older use;
                                # in that case, ignore it.
                                self._debug('Unknown findroot() '
                                            'directive: %s -- ignoring' %
                                            argstring)

                elif entity.find_command('chainloader') is not None:
                    for cmd in entity.commands():

                        # Skip non-commands
                        if not isinstance(cmd, MenuLstCommand):
                            continue

                        if cmd.get_command() == 'title':
                            argdict['title'] = ' '.join(cmd.get_args())
                        elif (cmd.get_command() == 'root' or
                            cmd.get_command() == 'rootnoverify'):
                            argdict['root'] = ' '.join(cmd.get_args())
                            args = cmd.get_args()[0]
                            if args.startswith('(hd'):
                                args = tuple(map(int, args[3:-1].split(',')))
                                argdict['chaininfo'] = args
                        elif cmd.get_command() == 'chainloader':
                            argdict['chainload'] = ' '.join(cmd.get_args())

                else: # OSes we don't know about
                    for cmd in entity.commands():
                        # Skip non-commands
                        if not isinstance(cmd, MenuLstCommand):
                            continue

                        if cmd.get_command() == 'title':
                            argdict['title'] = ' '.join(cmd.get_args())


                if argdict.get('chainload', None) is not None:
                    inst = ChainDiskBootInstance(None, **argdict)
                else:
                    bootfs_derived = False
                    if (argdict.get('rpool', None) is not None and
                        argdict.get('fstype', None) == 'zfs' and
                        argdict.get('bootfs', None) is None):
                        self._derive_bootfs(argdict)
                        bootfs_derived = True

                    if argdict.get('bootfs', None) is None:
                        self._debug('Creating a regular boot instance: %s' % argdict)
                        inst = BootInstance(None, **argdict)
                    else:
                        inst = SolarisDiskBootInstance(None, **argdict)
                        inst._bootfs_derived = bootfs_derived

                entity.boot_instance = inst
                inst._menulst_entity = entity

                boot_instances += [inst]

            elif isinstance(entity, MenuLstCommand) is True:
                # Add the command as a property
                arglist = entity.get_args()
                if arglist is not None and len(arglist) > 0:
                    argstring = ' '.join(arglist)
                else:
                    argstring = ''

                entity_cmd = entity.get_command()

                if entity_cmd == 'default':
                    default_index = argstring
                else:
                    try:
                        # Note that the property names in BootLoader were
                        # chosen to overlap the menu.lst keywords used to
                        # express them, so that we could just call setprop()
                        # and not special-case each of them.  When the
                        # menu.lst is reconsitituted, the BootLoader instance
                        # is interrogated as each command is encountered,
                        # enabling in-place "editing" of those lines from
                        # a loaded menu.lst file.
                        self.setprop(entity_cmd, argstring)
                    except BootmgmtUnsupportedPropertyError:
                        # Just ignore unsupported properties
                        self._debug('Unsupported property: %s' % entity_cmd)

        if default_index is not None:
            try:
                default_index = int(default_index)
                self._debug('default GRUB entry is: ' + str(default_index))
            except ValueError:
                self._debug("Could not convert `default' index (%s) to "
                            "an int -- setting to 0" % default_index)
                default_index = 0
            # XXX What to do when we have boot instances from both the menu.lst
            # file and from the zfs/be configuration?  What we do here, though,
            # is to mark the default boot instance as read from the menu.lst
            # file.
            if default_index < len(boot_instances):
                boot_instances[default_index].default = True
        elif len(boot_instances) > 0:
            # Set the default to be the first one
            boot_instances[0].default = True

        # Add the boot instances to the BootConfig instance:
        self._boot_config.add_boot_instance(boot_instances)

    def _write_config_disk(self, basepath):
        """This is a disk-based configuration.  We support ZFS or UFS root,
        so figure out which filesystem we're dealing with, and write the
        menu.lst file to that location."""

        menu_lst_dir = self._menu_lst_dir_disk()

        tuples = self._write_config_generic(basepath, menu_lst_dir)

        if tuples is None:
            self._debug('No tuples returned from _write_config_generic')
            return None

        fstype = self._boot_config.boot_fstype

        for idx, item in enumerate(tuples):
            if (item[BootConfig.IDX_FILETYPE] == BootConfig.OUTPUT_TYPE_FILE
               and
               item[BootConfig.IDX_DESTNAME] ==
                    LegacyGRUBBootLoader.MENU_LST_PATH):
                # Make a copy of the tuple so we can change it:
                item = list(item)

                if fstype == 'zfs':
                    item[BootConfig.IDX_DESTNAME] = (
                        '%(' + DiskBootConfig.TOKEN_ZFS_RPOOL_TOP_DATASET +
                        ')s' + LegacyGRUBBootLoader.MENU_LST_PATH)
                elif fstype == 'ufs':
                # The BootInstance included in the 6-tuple will be the first
                # SolarisDiskBootInstance in the list held in the associated
                # BootConfig's boot_instances list (this may need to be
                # revisited).
                    inst = None
                    for inst in self._boot_config.boot_instances:
                        if isinstance(inst, SolarisDiskBootInstance) is True:
                            break

                    item[BootConfig.IDX_DESTNAME] = (
                                    '%(' + BootConfig.TOKEN_SYSTEMROOT + ')s' +
                                    LegacyGRUBBootLoader.MENU_LST_PATH)
                    item[BootConfig.IDX_INSTANCE] = inst

                # Update tuple in the list:
                tuples[idx] = tuple(item)

        return tuples

    # _write_config_generic is taken from the MenuLstBootLoaderMixIn

    def _write_config_odd(self, basepath):

        if basepath is None:
            raise BootmgmtInterfaceCodingError('basepath must not be None for '
                                               'ODDBootConfig boot configs')

        odd_root = self._boot_config.get_root()
        tuples = self._write_config_generic(basepath, odd_root)

        # Now add the stage2_eltorito file to the tuples list:
        try:
            tmpfile = tempfile.NamedTemporaryFile(dir=basepath, delete=False)
            tmpfile.close()
            shutil.copy(odd_root + '/boot/grub/stage2_eltorito',
                        tmpfile.name)
        except IOError as err:
            raise BootmgmtConfigWriteError('Error while trying to copy '
                  'Legacy GRUB El Torito stage2', err)

        tuples += [(BootConfig.OUTPUT_TYPE_BIOS_ELTORITO,
                    tmpfile.name,
                    None,
                    None,
                    None,
                    None,
                    None)]

        return tuples

    # Generic support methods for all BootConfig classes

    def _write_menu_lst(self, outfile):
        """Invoked by the MenuLstBootLoaderMixIn.
        These are two cases that _write_menu_lst has to handle.  The
        first is when there was a menu.lst that was previously loaded.
        In that case, portions of that file may change, depending on
        modifications made to the BootLoader properties or to the
        individual BootInstance objects that comprise the BootConfig.
        The second case is a new menu.lst file.  For this case, we
        just fill the propdict with defaults, then update those
        defaults with values from BootLoader properties and then
        apply the propdict to the menu.lst template (above).
        Additional entries not previously present in the menu.lst
        file are appended.  In this way, the ordering of the file
        and user comments can be preserved.
        """
        
        propdict = LegacyGRUBBootLoader.DEFAULT_PROPDICT.copy()

        minmem64 = self._bl_props.get(BootLoader.PROP_MINMEM64, None)
        if minmem64 is not None:
            propdict['minmem64'] = 'min_mem64 ' + str(minmem64)
        elif self._menufile:
            propdict['minmem64'] = None

        timeout = self._bl_props.get(BootLoader.PROP_TIMEOUT, None)
        if timeout is not None:
            propdict['timeout'] = 'timeout ' + str(timeout)
        elif self._menufile:
            propdict['timeout'] = None

        hidemenu = self._bl_props.get(BootLoader.PROP_QUIET, None)
        if hidemenu is True:
            propdict['hiddenmenu'] = 'hiddenmenu'
        elif self._menufile:
            propdict['hiddenmenu'] = None

        consprop = self._bl_props.get(BootLoader.PROP_CONSOLE, None)
        if consprop is None or consprop == BootLoader.PROP_CONSOLE_GFX:
            # XXX - If there is no splashimage/forecolor/backcolor in
            # XXX - the existing menu.lst, don't add it here if no
            # XXX - splashimage / forecolor / backcolor was specified
            # XXX - in the BootLoader properties. If there was no
            # XXX - menu.lst previously loaded, DO add the defaults.
            if self._menufile is None:
                default_grub_splash = LegacyGRUBBootLoader.DEFAULT_GRUB_SPLASH
                default_forecolor = LegacyGRUBBootLoader.DEFAULT_FORECOLOR
                default_backcolor = LegacyGRUBBootLoader.DEFAULT_BACKCOLOR
            else:
                default_grub_splash = None
                default_forecolor = None
                default_backcolor = None

            splash = self._bl_props.get(BootLoader.PROP_SPLASH,
                                        default_grub_splash)
            forecolor = self._bl_props.get(BootLoader.PROP_FORECOLOR,
                              default_forecolor)
            backcolor = self._bl_props.get(BootLoader.PROP_BACKCOLOR,
                              default_backcolor)

            # The structure of each if statement below is intentional--
            # The else branch is for the case when we have a menufile
            # already and we want to support REMOVING properties that
            # were previously set (i.e. removing commands).

            if splash is not None:
                propdict['splashimage'] = 'splashimage ' + splash
            else:
                propdict['splashimage'] = None

            if forecolor is not None:
                propdict['foreground'] = 'foreground ' + forecolor
            else:
                propdict['foreground'] = None

            if backcolor is not None:
                propdict['background'] = 'background ' + backcolor
            else:
                propdict['background'] = None

            # Delete any reference to the serial console if it exists,
            # but only if we previously loaded a menu:
            if self._menufile:
                propdict['serial'] = None
                propdict['terminal'] = None

        elif consprop == BootLoader.PROP_CONSOLE_SERIAL:
            params = self._serial_parameters()

            sercmd = 'serial --unit=%s' % params[BootLoader.PROP_SP_PORT]

            if params[BootLoader.PROP_SP_SPEED] is not None:
                sercmd += ' --speed=%s' % params[BootLoader.PROP_SP_SPEED]
            if params[BootLoader.PROP_SP_DATAB] is not None:
                sercmd += ' --word=%s' % params[BootLoader.PROP_SP_DATAB]
            if params[BootLoader.PROP_SP_PARITY] is not None:
                sercmd += ' --parity=%s' % params[BootLoader.PROP_SP_PARITY]
            if params[BootLoader.PROP_SP_STOPB] is not None:
                sercmd += ' --stop=%s' % params[BootLoader.PROP_SP_STOPB]

            propdict['serial'] = sercmd
            propdict['terminal'] = 'terminal serial'

        # Figure out the default boot index first by iterating through 
        # all BootInstances
        for idx, inst in enumerate(self._boot_config.boot_instances):
            if inst.default is True:
                propdict['default'] = 'default ' + str(idx)

        # Now write the global section
        if self._menufile is None:
            outfile.write(LegacyGRUBBootLoader.MENU_LST_PREAMBLE % propdict)
        else:
            # Filter out values in propdict that are just comment lines
            propdict = dict([(k, v) for k, v in propdict.items()
                       if v is None or (len(v.strip()) > 0 and
                       v.strip()[0] != '#')])

            # Use the values in propdict to update any global commands in
            # the existing menu.lst entity list.
            self._update_menulst_globals(propdict)
            for entity in self._menufile.entities():
                # Write the menu.lst's global section first by going through
                # the entity list, making sure to ignore deleted boot
                # instances:
                if not isinstance(entity, MenuLstMenuEntry):
                    outfile.write(str(entity) + '\n')

        # iterate through the list of boot instances in the BootConfig
        # instance, adding an entry (or updating an existing entry) for 
        # each one:
        for idx, inst in enumerate(self._boot_config.boot_instances):
            # XXX - Do validation of kernel against kernel under
            # self.rootpath (if specified)
            # XXX - Also: should we verify that a 64-bit kernel is being
            # used with a 64-bit boot archive and similarly for 32-bit?
            # XXX - Use the signature attribute

            entry_lines = self._generate_entry(inst)
            # _generate_entry() returns a string only if inst._menulst_entity
            # is None.
            if entry_lines is not None:
                outfile.write('title ' + inst.title + '\n')
                outfile.write(entry_lines + '\n')
            else:
                # Make sure we ignore deleted boot instances
                entity = inst._menulst_entity
                if entity.boot_instance in self._boot_config.boot_instances:
                    outfile.write(str(entity) + '\n')
                if entry_lines is not None:
                    self._debug(('self._generate_entry() returned something '
                                 'unexpected (%s)') % entry_lines)

    def _update_menulst_globals(self, propdict):
        "Update top-level commands in the menu.lst file associated with self"

        global_cmd_entities = set()
        deleted_cmds = set()
        for entity in self._menufile.entities():
            # MenuLstCommand instances at the top level of the entity list
            # are global
            if not isinstance(entity, MenuLstCommand):
                continue

            entity_cmd = entity.get_command()

            global_cmd_entities.add(entity_cmd)

            if entity_cmd in propdict:
                cmd_and_args = propdict[entity_cmd]
                if cmd_and_args is None:
                    # Delete this entity!
                    self._menufile.delete_entity(entity)
                    deleted_cmds.add(entity_cmd)
                    continue

                # Update the entity in-place with the arguments from
                # propdict
                split_cmd_args = cmd_and_args.split(' ', 1)
                if len(split_cmd_args) > 1:
                    entity.set_args(split_cmd_args[1])

        if deleted_cmds:
            self._debug('Deleted globals => %s' % list(deleted_cmds))

        # Now figure out the set of globals that do not exist in the file
        # and add them
        cmdlist = [item for item in propdict if propdict[item] is not None]
        missing_globals = set(cmdlist).difference(global_cmd_entities)
        if missing_globals:
            self._debug('Adding global commands: %s' %
                        str(list(missing_globals)))
        for missing_cmd in missing_globals:
            self._menufile.add_global(propdict[missing_cmd])

    # Menu-entry generator infrastructure

    def _generate_entry(self, instance):
        """Use the BootInstance's class name to find the entry-generator 
        method. Entry generator functions are responsible for producing a
        string with the rest of the entry (the title is printed by the
        caller)"""

        instclsname = instance.__class__.__name__
        method_name = '_generate_entry_' + instclsname
        entry_generator = getattr(self.__class__, method_name, None)
        if entry_generator is not None:
            # Do the generic work of updating the title if an instance
            # is associated with an existing menu.lst entity:
            if instance._menulst_entity is not None:
                instance._menulst_entity.update_command('title',
                                                        instance.title)
            # It's a method, so self must be passed explicitly
            return entry_generator(self, instance)
        else:
            self._debug('No entry generator (%s) for class %s' %
                        (method_name, instclsname))
            if instance._menulst_entity is not None:
                return None
            else:
                return ''

    def _generate_entry_generic(self, inst, kargs):

        kargs = '' if kargs is None else kargs

        # If the BootInstance specifies a splashimage, foreground color
        # and/or background color, add those now
        splash = getattr(inst, BootLoader.PROP_SPLASH, None)
        forecolor = getattr(inst, BootLoader.PROP_FORECOLOR, None)
        backcolor = getattr(inst, BootLoader.PROP_BACKCOLOR, None)

        if inst._menulst_entity is None:
            if splash:
                splash_cmd = 'splashimage ' + splash
            else:
                splash_cmd = None

            if forecolor:
                fore_cmd = 'foreground ' + forecolor
            else:
                fore_cmd = None

            if backcolor:
                back_cmd = 'background ' + backcolor
            else:
                back_cmd = None
        else:
            splash_cmd = 'splashimage'
            if splash:
                splash_cmd += ' ' + splash

            fore_cmd = 'foreground'
            if forecolor:
                fore_cmd = ' ' + forecolor

            back_cmd = 'background'
            if backcolor:
                back_cmd = ' ' + backcolor

        # XXX Check to ensure that splashimage/foreground/background is not
        # XXX specified when this boot instance is using a non-graphics
        # XXX console.

        try:
            inst.kernel = inst.kernel % {'karch': '$ISADIR'}
        except KeyError:
            # If somehow another Python conversion specifier snuck in,
            # raise an exception
            raise BootmgmtMalformedPropertyValueError('kernel', inst.kernel)

        if '$' in inst.kernel or '$' in kargs:
            kernel_cmd = 'kernel$ ' + inst.kernel
        else:
            kernel_cmd = 'kernel ' + inst.kernel

        # kargs already has a leading space from the initialization, above
        kernel_cmd += (' ' if not kargs == '' else '') + kargs

        try:
            inst.boot_archive = inst.boot_archive % {'karch': '$ISADIR'}
        except KeyError:
            # If somehow another Python conversion specifier snuck in,
            # raise an exception
            raise BootmgmtMalformedPropertyValueError('boot_archive',
                                                      inst.boot_archive)

        if '$' in inst.boot_archive or '$' in kernel_cmd:
            module_cmd = 'module$ ' + inst.boot_archive
        else:
            module_cmd = 'module ' + inst.boot_archive

        # If this instance is associated with an existing menu.lst entity,
        # update that entity
        if inst._menulst_entity is not None:
            for nextcmd in (splash_cmd, fore_cmd, back_cmd, kernel_cmd,
                            module_cmd):
                nextcmd_args = nextcmd.split(' ', 1)
                if len(nextcmd_args) == 1:  # This command must be deleted
                    inst._menulst_entity.delete_command(nextcmd)
                elif len(nextcmd_args) == 2:
                    inst._menulst_entity.update_command(nextcmd_args[0],
                                                       nextcmd_args[1].strip(),
                                                       create=True)
            return None

        ostr = ''
        if splash_cmd is not None:
            ostr += splash_cmd + '\n'
        if fore_cmd is not None:
            ostr += fore_cmd + '\n'
        if back_cmd is not None:
            ostr += back_cmd + '\n'
        ostr += kernel_cmd + '\n'
        ostr += module_cmd

        return ostr

    def _generate_entry_SolarisDiskBootInstance(self, inst):
        "Menu-entry generator function for SolarisDiskBootInstance instances"

        ostr = ''
        kargs = ''
        bootfs_cmd = 'bootfs'

        if inst.fstype == 'zfs':
            if inst.bootfs is None:
                raise BootmgmtIncompleteBootConfigError('bootfs property '
                      'is missing')
            bootfs_cmd += ' ' + inst.bootfs
            if inst.kargs is None:
                kargs = '-B $ZFS-BOOTFS'
            elif inst.kargs.find('$ZFS-BOOTFS') is -1:
                # XXX - This is very simplistic and should be revisited
                kargs = '-B $ZFS-BOOTFS ' + inst.kargs
            else:
                kargs = inst.kargs
        elif inst.kargs is not None and inst.kargs.strip() != '':
            kargs = inst.kargs

        if inst._menulst_entity is not None:
            if getattr(inst, '_bootfs_derived', False) is False:
                bootfs_cmd_args = bootfs_cmd.split(' ', 1)
                if len(bootfs_cmd_args) == 1:  # This command must be deleted
                    inst._menulst_entity.delete_command(bootfs_cmd_args)
                else:
                    inst._menulst_entity.update_command(bootfs_cmd_args[0],
                                                    bootfs_cmd_args[1].strip(),
                                                    create=True)

            self._generate_entry_generic(inst, kargs)
            return None      

        ostr = self._generate_entry_generic(inst, kargs)
        ostr = bootfs_cmd + '\n' + ostr
        return ostr

    def _generate_entry_SolarisODDBootInstance(self, inst):
        return self._generate_entry_generic(inst, inst.kargs)

    def _generate_entry_ChainDiskBootInstance(self, inst):
        """Menu-entry generator for ChainDiskBootInstance instances.  This is a
        VERY simple use of the rootnoverify and chainloader Legacy GRUB
        commands.  Chainloading is only supported to a specific, numbered
        drive and physical sector offset/count."""

        if inst.chaininfo is None:
            raise BootmgmtIncompleteBootConfigError('chaininfo property is '
                  'missing')
        if type(inst.chaininfo) is not tuple or len(inst.chaininfo) == 0:
            raise BootmgmtArgumentError('chaininfo must be a non-zero-length '
                                        'tuple')
        if type(inst.chaininfo[0]) is not int:
            raise BootmgmtArgumentError('chaininfo[0] must be an int')
        if len(inst.chaininfo) > 1 and type(inst.chaininfo[1]) is not int:
            raise BootmgmtArgumentError('chaininfo[1] must be an int')

        diskstr = '(hd' + str(inst.chaininfo[0])

        if len(inst.chaininfo) > 1:
            diskstr += ',' + str(inst.chaininfo[1])

        diskstr += ')'

        rootnoverify_cmd = 'rootnoverify ' + diskstr + '\n'
        chainloader_cmd = 'chainloader '
        if int(inst.chainstart) != 0:
            chainloader_cmd += str(int(inst.chainstart))
        chainloader_cmd += '+' + str(int(inst.chaincount)) + '\n'

        if inst._menulst_entity is not None:
            for nextcmd in (rootnoverify_cmd, chainloader_cmd):
                cmd_args = nextcmd.split(' ', 1)
                inst._menulst_entity.update_command(cmd_args[0],
                                                    cmd_args[1].strip(),
                                                    create=True)
            return None      

        ostr = rootnoverify_cmd + chainloader_cmd
        return ostr

    # Property-related methods
    def _prop_validate(self, key, value=None, validate_value=False):
        if key == BootLoader.PROP_BOOT_TARGS:
            if validate_value is True and value != 'bios':
                raise BootmgmtUnsupportedPlatformError(value + ' is not a '
                      'supported firmware type for ' + self.__class__.__name__)
            return
        super(self.__class__, self)._prop_validate(key, value, validate_value)

    # BootLoader installation methods

    def install(self, location):
        # Iterate through the list of boot instances, adding _menulst_entity
        # attributes to those that do not have them.  This prevents us from
        # having to pepper lower-level code with getattr() calls.
        for inst in self._boot_config.boot_instances:
            inst.__dict__.setdefault('_menulst_entity', None)

        return self._install_generic(location)
        # XXX - Handle other types of boot_class here (copying pxegrub,
        # XXX - stage2_eltorito)

    # _write_loader performs the real guts of boot loader installation
    def _write_loader(self, devname, data_root):
        """Invoke installgrub to write stage1 and stage2 to disk.  Slice
        nodes (and only slice nodes) are required."""

        if not ((len(devname) > 2 and devname[-2] == 's' and
                devname[-1].isdigit())
           or
               (len(devname) > 3 and devname[-3] == 's' and
                devname[-2:].isdigit())):
            raise BootLoaderInstallError('Device node is not a slice: ' +
                                         devname)

        args = ['/sbin/installgrub']

        # installgrub will autodetect when to use the -m switch

        # If a version is present, try to use it during installation.
        if self.version is not None:
            args += ['-u', self.version]

        args += [data_root + '/boot/grub/stage1',
                 data_root + '/boot/grub/stage2',
                 devname]

        self._debug('_write_loader: Invoking command: ' + ' '.join(args))

        try:
            Popen.check_call(args, stdout=Popen.STORE, stderr=Popen.STORE)
        except CalledProcessError as cpe:
            self._debug('_write_loader: Return code = %d' % cpe.returncode)
            if cpe.returncode != LegacyGRUBBootLoader.INSTALLGRUB_NOUPDT:
                output = ''
                if cpe.popen is not None and cpe.popen.stderr is not None:
                    output = '\nOutput was:\n' + cpe.popen.stderr
                raise BootLoaderInstallError('installgrub failed for '
                      'device ' + devname + ': Return code ' +
                      str(cpe.returncode) + output)
        except OSError as ose:
                raise BootLoaderInstallError('Error while trying to '
                      'invoke installgrub for '
                      'device ' + devname + ': ' + str(ose))


#
# Legacy GRUB menu.lst
#
class LegacyGRUBMenuFile(MenuDotLst):
    def __init__(self, filename='/boot/solaris/menu.lst'):
        super(LegacyGRUBMenuFile, self).__init__(filename)

    def _analyze_syntax(self):
        """
        Command      := Keyword Arguments | VarName '=' Value
        Arguments    := Arguments [ \t]+ Argument | Argument
        Keyword      := 'blocklist' | 'boot' | 'bootfs' | 'bootp' |
                        'cat' | 'chainloader' | 'cmp' | 'color' |
                        'configfile' | 'debug' | 'default' |
                        'device' | 'dhcp' | 'displayapm' |
                        'displaymem' | 'embed' | 'fallback' |
                        'find' | 'findroot' | 'fstest' | 'geometry' |
                        'halt' | 'help' | 'hiddenmenu' | 'hide' |
                        'ifconfig' | 'impsprobe' | 'initrd' |
                        'install' | 'ioprobe' | 'kernel$' |
                        'kernel' | 'lock' | 'makeactive' | 'map' |
                        'md5crypt' | 'min_mem64' | 'module$' |
                        'module' | 'modulenounzip' | 'pager' |
                        'partnew' | 'parttype' | 'password' |
                        'pause' | 'quit' | 'rarp' | 'read' |
                        'reboot' | 'root' | 'rootnoverify' |
                        'savedefault' | 'serial' | 'setkey' |
                        'setup' | 'terminal' | 'terminfo' |
                        'testload' | 'testvbe' | 'tftpserver' |
                        'timeout' | 'title' | 'unhide' |
                        'uppermem' | 'vbeprobe'
        Argument     := [^ \t\n]+
        VarName      := [A-Za-z0-9]+
        Value        := [^\n]+
        """
        # XXX - Currently a NOP


def bootloader_classes():   
    return [LegacyGRUBBootLoader]
