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
import pwd
import grp
import gettext
import stat
import re

from .menulst import MenuDotLst, MenuLstError, MenuLstMenuEntry, MenuLstCommand
from ...bootloader import BootLoader, BootLoaderInstallError
from ...bootconfig import BootConfig, DiskBootConfig, SolarisDiskBootInstance
from ...bootconfig import ChainDiskBootInstance
from ... import BootmgmtArgumentError
from ... import BootmgmtUnsupportedOperationError, BootmgmtInterfaceCodingError
from ... import BootmgmtIncompleteBootConfigError, BootmgmtConfigReadError
from ... import BootmgmtConfigWriteError, BootmgmtMalformedPropertyValueError
from ... import BootmgmtUnsupportedPlatformError, BootmgmtNotSupportedError
from solaris_install import Popen, CalledProcessError

_ = gettext.translation("SUNW_OST_OSCMD", "/usr/lib/locale",
    fallback=True).gettext

class LegacyGRUBBootLoader(BootLoader):
    """Implementation of a Legacy GRUB (GRUB 0.97) BootLoader.  Handles parsing
    the menu.lst file (reading and writing), though reading it and creating
    BootInstance objects is rather fragile"""

    WEIGHT = 1  # Legacy GRUB's probe weight

    MENU_LST_PATH = '/boot/grub/menu.lst'

    DEFAULT_PROPDICT = {
         'default_command'     : 'default 0',
         'timeout_command'     : 'timeout 10',
         'serial_command'      : '#   serial --unit=0 --speed=9600',
         'terminal_command'    : '#   terminal serial',
         'splashimage_command' : '#   splashimage /boot/grub/splash.xpm.gz',
         # if foreground or background are used, they MUST start with
         # a newline (see the MENU_LST_PREAMBLE, below)
         'foreground'          : '',
         'background'          : '',
         'minmem64'            : '',
         'hidemenu'            : '' }

    INSTALLGRUB_NOUPDT = 4       # from src/cmd/boot/common/boot_utils.h
    INSTALLGRUB_NOEINFO = 6      # (ditto)

    DEFAULT_TIMEOUT = 10         # 10 seconds is the default timeout
    DEFAULT_FORECOLOR = '343434'
    DEFAULT_BACKCOLOR = 'F7FBFF'

    # Supported properties for setprop()
    SUPPORTED_PROPS = [BootLoader.PROP_CONSOLE,
                       BootLoader.PROP_SERIAL_PARAMS,
                       BootLoader.PROP_MINMEM64,
                       BootLoader.PROP_TIMEOUT,
                       BootLoader.PROP_QUIET]

    MENU_LST_PREAMBLE = (
r"""# default menu entry to boot
%(default_command)s
#
# menu timeout in second before default OS is booted
# set to -1 to wait for user input
%(timeout_command)s
#
# To enable grub serial console to ttya uncomment the following lines
# and comment out the splashimage line below
# WARNING: do not enable grub serial console when BIOS console serial
#       redirection is active.
%(serial_command)s
%(terminal_command)s
#
# Uncomment the following line to enable GRUB splashimage on console
%(splashimage_command)s%(foreground)s%(background)s
#
# To chainload another OS
#
# title Another OS
#       root (hd<disk no>,<partition no>)
#       chainloader +1
#
# To chainload a Solaris release not based on grub
#
# title Solaris 9
#       root (hd<disk no>,<partition no>)
#       chainloader +1
#       makeactive
#
# To load a Solaris instance based on grub
# If GRUB determines if the booting system is 64-bit capable,
# the kernel$ and module$ commands expand $ISADIR to "amd64"
#
# title Solaris <version>
#       findroot (pool_<poolname>,<partition no>,x)   --x = Solaris root slice
#       bootfs <poolname>/ROOT/<BE_name>
#       kernel$ /platform/i86pc/kernel/$ISADIR/unix
#       module$ /platform/i86pc/$ISADIR/boot_archive

#
# To override Solaris boot args (see kernel(1M)), console device and
# properties set via eeprom(1M) edit the "kernel" line to:
#
#   kernel /platform/i86pc/kernel/unix <boot-args> -B prop1=val1,prop2=val2,...
#
%(hidemenu)s
%(minmem64)s
""")

    @classmethod
    def probe(cls, **kwargs):
        """Probe for Legacy GRUB files for use with the BootConfig passed
        in"""

        bootconfig = kwargs.get('bootconfig', None)

        if (bootconfig is None or bootconfig.boot_class is None):
            return (None, None)

        if (bootconfig.boot_class == BootConfig.BOOT_CLASS_DISK and
           not bootconfig.boot_fstype is None):
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
        # XXX - that we have access to the installgrub program in the currently-
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

    def _serial_parameters(self):
        """Parse serial parameters and return a tuple of (serial port number,
        serial port speed, data bits, parity (one of 'no', 'odd' or 'even'),
        stop bits (0 or 1)) (all tuple members must be strings).

        The form of the serial_params property is:

               serial_params | A tuple containing (<portspec>,<speed>,<d>,
                             | <p>,<s>,<f>).
                             | <portspec> is currently defined to be a
                             | number (valid valid depend on the platform,
                             | but 0 is ttya (com1) and 1 is ttyb (com2)).
                             | Serial console parameters (<d>=data bits,
                             | <p>=parity ('N','E','O'),<s>=stop bits (0,1),
                             | <f>=flow control ('H','S',None) for hardware,
                             | software, or none).  The default is:
                             | (0,9600,8,'N',1,None).
        """

        params = self.getprop('serial_params')

        if not params is None:
            if not params[BootLoader.PROP_SP_PARITY] is None:
                try:
                    parity = {'N' : 'no',
                              'E' : 'even',
                              'O' : 'odd'}[params[BootLoader.PROP_SP_PARITY]]
                except KeyError:
                    self._debug('Bad parity value in serial_params')
                    parity = None

            ret_params = (params[BootLoader.PROP_SP_PORT],
                          params[BootLoader.PROP_SP_SPEED],
                          params[BootLoader.PROP_SP_DATAB],
                          parity,
                          params[BootLoader.PROP_SP_STOPB])

            # if port is not indicated, force use of port 0.
            if ret_params[0] is None:
                ret_params[0] = '0'

            return ret_params
            
        return ('0', '9600', None, None, None)

    def __init__(self, **kwargs):
        self.pkg_names = [ 'system/boot/grub', 'SUNWgrub' ]
        self.name = 'Legacy GRUB'
        self._menufile = None
        super(LegacyGRUBBootLoader, self).__init__(**kwargs)
        self._bl_props[BootLoader.PROP_BOOT_TARGS] = 'bios'

    def new_config(self):
        """The configuration for Legacy GRUB consists solely of the menu.lst
        file.  The default new configuration is an empty menu.lst file,
        with a graphical splashscreen and appropriate fore/back colors."""
        self._bl_props[BootLoader.PROP_CONSOLE] = BootLoader.PROP_CONSOLE_GFX

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

    def _load_config_disk(self):

        menu_lst = (self._menu_lst_dir_disk() +
                   LegacyGRUBBootLoader.MENU_LST_PATH)
        try:
            self._menufile = LegacyGRUBMenuFile(menu_lst)
        except IOError as err:
            raise BootmgmtConfigReadError('Error while processing the %s file' %
                                          menu_lst, err)
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
                if entity.find_command('bootfs'):
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

                elif entity.find_command('chainloader'):
                    for cmd in entity.commands():
                        if cmd.get_command() == 'title':
                            argdict['title'] = ' '.join(cmd.get_args())
                        elif (cmd.get_command() == 'root' or
                            cmd.get_command() == 'rootnoverify'):
                            argdict['root'] = ' '.join(cmd.get_args())
                        elif cmd.get_command() == 'chainloader':
                            argdict['chainload'] = ' '.join(cmd.get_args())

                elif entity.find_command('findroot'):
                    # XXX - Look up ZFS bootfs property for the pool
                    raise BootmgmtUnsupportedOperationError('XXX - Fix Me')

                if not argdict.get('chainload', None) is None:
                    inst = ChainDiskBootInstance(None, **argdict)
                else:
                    inst = SolarisDiskBootInstance(None, **argdict)

                boot_instances += [inst]

            elif isinstance(entity, MenuLstCommand) is True:
                # Add the command as a property
                arglist = entity.get_args()
                if not arglist is None and len(arglist) > 0:
                    argstring = ' '.join(arglist)
                else:
                    argstring = ''
                # XXX - Don't use setprop here; if the entity contains a
                # XXX - command we don't recognize, we'll get an exception
                # XXX - instead, just record that command as-is so it can
                # XXX - be replayed when the menu.lst is written
                # XXX - In any case, we need to parse the command and turn it
                # XXX - into a valid property key/value.
                if entity.get_command() == 'default':
                    default_index = argstring
                else:
                    self.setprop(entity.get_command(), argstring)

        if not default_index is None:
            try:
                default_index = int(default_index)
                self._debug('default GRUB entry is: ' + str(default_index))
            except ValueError:
                self._debug("Could not convert `default' index (%s) to "
                            "an int -- setting to 0" % default_index)
                default_index = 0
            if default_index < len(self._boot_config.boot_instances):
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

        fstype = self._boot_config.boot_fstype
        if fstype != 'zfs' and fstype != 'ufs':
            raise BootmgmtUnsupportedOperationError('Unknown filesystem: %s'
                                                     % fstype)
        if fstype == 'zfs':
            menu_lst_dir = self._boot_config.zfstop
        elif fstype == 'ufs':
            menu_lst_dir = self._boot_config.get_root()

        tuples = self._write_config_generic(basepath, menu_lst_dir)

        if tuples is None:
            self._debug('No tuples returned from _write_config_generic')
            return None

        for idx, item in enumerate(tuples):
            if (item[BootConfig.IDX_FILETYPE] is BootConfig.OUTPUT_TYPE_FILE and
               item[BootConfig.IDX_DESTNAME] ==
                                            LegacyGRUBBootLoader.MENU_LST_PATH):
                # Make a copy of the tuple so we can change it:
                item = list(item)

                if fstype == 'zfs':
                    item[BootConfig.IDX_DESTNAME] = (
                        '%(' + DiskBootConfig.TOKEN_ZFS_RPOOL_TOP_DATASET + ')s'
                        + LegacyGRUBBootLoader.MENU_LST_PATH)
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

                # Update item in the list:
                item = tuple(item)
                tuples[idx] = item

        return tuples

    def _write_config_generic(self, basepath, menu_lst_dir):

        # If basepath is not None, the menu.lst should be written to a file
        # under basepath (instead of to the actual location)
        if basepath is None:
            realmenu = menu_lst_dir + LegacyGRUBBootLoader.MENU_LST_PATH
            tempmenu = realmenu + '.new'

            try:
                # Don't open the new menu.lst over the old -- create a
                # temporary file, then, if the write is successful, move the
                # temporary file over the old one.
                outfile = open(tempmenu, 'w')
                self._write_menu_lst(outfile)
                outfile.close()
            except IOError as err:
                raise BootmgmtConfigWriteError("Couldn't write to %s" %
                                               tempmenu, err)

            try:
                shutil.move(tempmenu, realmenu)
            except IOError as err:
                try:
                    os.remove(tempmenu)
                except OSError as oserr:
                    self._debug('Error while trying to remove %s: %s' %
                                (tempmenu, oserr.strerror))
                raise BootmgmtConfigWriteError("Couldn't move %s to %s" %
                                               (tempmenu, realmenu), err)

            # Move was successful, so now set the owner and mode properly:
            try:
                os.chmod(realmenu, 0644)
                os.chown(realmenu, pwd.getpwnam('root').pw_uid,
                         grp.getgrnam('root').gr_gid)
            except OSError as oserr:
                raise BootmgmtConfigWriteError("Couldn't set mode/perms on "
                      + realmenu, oserr)

            return None

        # basepath is set to a path.  Use it to form the path to a temporary
        # file
        try:
            tmpfile = tempfile.NamedTemporaryFile(dir=basepath, delete=False)
            self._write_menu_lst(tmpfile)
            tmpfile.close()
        except IOError as err:
            raise BootmgmtConfigWriteError("Couldn't create a temporary "
                  'file for menu.lst', err)

        return [(BootConfig.OUTPUT_TYPE_FILE,
                tmpfile.name,
                None,
                LegacyGRUBBootLoader.MENU_LST_PATH,
                'root',
                'root',
                0644)]


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
        propdict = LegacyGRUBBootLoader.DEFAULT_PROPDICT.copy()

        minmem64 = self._bl_props.get(BootLoader.PROP_MINMEM64, None)
        if not minmem64 is None:
            propdict['minmem64'] = 'min_mem64 ' + str(minmem64)

        timeout = self._bl_props.get(BootLoader.PROP_TIMEOUT, None)
        if timeout is None:
            timeout = LegacyGRUBBootLoader.DEFAULT_TIMEOUT
        propdict['timeout_command'] = 'timeout ' + str(timeout)

        hidemenu = self._bl_props.get(BootLoader.PROP_QUIET, None)
        if hidemenu is True:
            propdict['hidemenu'] = 'hiddenmenu'

        consprop = self._bl_props.get(BootLoader.PROP_CONSOLE, None)
        if consprop is None or consprop == BootLoader.PROP_CONSOLE_GFX:
            propdict['splashimage_command'] = (
               'splashimage /boot/grub/splash.xpm.gz')
            propdict['foreground'] = (
               '\nforeground ' + LegacyGRUBBootLoader.DEFAULT_FORECOLOR)
            propdict['background'] = (
               '\nbackground ' + LegacyGRUBBootLoader.DEFAULT_BACKCOLOR)
        elif consprop == BootLoader.PROP_CONSOLE_SERIAL:
            params = self._serial_parameters()

            sercmd = 'serial --unit=%s' % params[BootLoader.PROP_SP_PORT]

            if not params[BootLoader.PROP_SP_SPEED] is None:
                sercmd += ' --speed=%s' % params[BootLoader.PROP_SP_SPEED]
            if not params[BootLoader.PROP_SP_DATAB] is None:
                sercmd += ' --word=%s' % params[BootLoader.PROP_SP_DATAB]
            if not params[BootLoader.PROP_SP_PARITY] is None:
                sercmd += ' --parity=%s' % params[BootLoader.PROP_SP_PARITY]
            if not params[BootLoader.PROP_SP_STOPB] is None:
                sercmd += ' --stop=%s' % params[BootLoader.PROP_SP_STOPB]

            propdict['serial_command'] = sercmd
            propdict['terminal_command'] = 'terminal serial'

        # iterate through the list of boot instances in the BootConfig
        # instance, adding an entry for each one:
        entries = ''
        for idx, inst in enumerate(self._boot_config.boot_instances):
            # XXX - Do validation of kernel against kernel under
            # self.rootpath (if specified)
            # XXX - Also: should we verify that a 64-bit kernel is being
            # used with a 64-bit boot archive and similarly for 32-bit?
            # XXX - Use the signature attribute
            if inst.default is True:
                propdict['default_command'] = 'default ' + str(idx)
            entries += 'title ' + inst.title + '\n'
            entries += self._generate_entry(inst)
            entries += '\n'

        outfile.write(LegacyGRUBBootLoader.MENU_LST_PREAMBLE % propdict)
        outfile.write(entries)

    # Menu-entry generator infrastructure

    def _generate_entry(self, instance):
        """Use the BootInstance's class name to find the entry-generator method.
        Entry generator functions are responsible for producing a string
        with the rest of the entry (the title is printed by the caller)"""

        instclsname = instance.__class__.__name__
        method_name = '_generate_entry_' + instclsname
        entry_generator = self.__class__.__dict__.get(method_name, None)
        if not entry_generator is None:
            # It's a method, so self must be passed explicitly
            return entry_generator(self, instance)
        else:
            self._debug('No entry generator (%s) for class %s' %
                        (method_name, instclsname))
            return ''

    def _generate_entry_generic(self, inst, kargs):

        ostr = ''
        kargs = '' if kargs is None else kargs

        try:
            inst.kernel = inst.kernel % {'karch' : "$ISADIR"}
        except KeyError:
            # If somehow another Python conversion specifier snuck in,
            # raise an exception
            raise BootmgmtMalformedPropertyValueError('kernel', inst.kernel)

        if not inst.kernel.find("$ISADIR") is -1:
            ostr += 'kernel$ ' + inst.kernel
        else:
            ostr += 'kernel ' + inst.kernel

        # kargs already has a leading space from the initialization, above
        ostr += (' ' if not kargs == '' else '') + kargs + '\n'

        try:
            inst.boot_archive = inst.boot_archive % {'karch' : "$ISADIR"}
        except KeyError:
            # If somehow another Python conversion specifier snuck in,
            # raise an exception
            raise BootmgmtMalformedPropertyValueError('boot_archive',
                                                      inst.boot_archive)

        if not inst.boot_archive.find("$ISADIR") is -1:
            ostr += 'module$ ' + inst.boot_archive + '\n'
        else:
            ostr += 'module ' + inst.boot_archive + '\n'

        return ostr


    def _generate_entry_SolarisDiskBootInstance(self, inst):
        "Menu-entry generator function for SolarisDiskBootInstance instances"

        ostr = ''
        kargs = ''
        if inst.fstype == 'zfs':
            if inst.bootfs is None:
                raise BootmgmtIncompleteBootConfigError('bootfs property '
                      'is missing')
            ostr += 'bootfs ' + inst.bootfs + '\n'

            if inst.kargs is None:
                kargs = '-B $ZFS-BOOTFS'
            elif inst.kargs.find('$ZFS-BOOTFS') is -1:
                # XXX - This is very simplistic and should be revisited
                kargs = '-B $ZFS-BOOTFS ' + inst.kargs
            else:
                kargs = inst.kargs
        elif not inst.kargs is None and inst.kargs.strip() != '':
            kargs = inst.kargs

        ostr += self._generate_entry_generic(inst, kargs)

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
        if not type(inst.chaininfo) is tuple or len(inst.chaininfo) == 0:
            raise BootmgmtArgumentError('chaininfo must be a non-zero-length '
                                        'tuple')
        if not type(inst.chaininfo[0]) is int:
            raise BootmgmtArgumentError('chaininfo[0] must be an int')
        if len(inst.chaininfo) > 1 and not type(inst.chaininfo[1]) is int:
            raise BootmgmtArgumentError('chaininfo[1] must be an int')

        diskstr = '(hd' + str(inst.chaininfo[0])

        if len(inst.chaininfo) > 1:
            diskstr += ',' + str(inst.chaininfo[1])

        diskstr += ')'

        ostr = 'rootnoverify ' + diskstr + '\n'
        ostr += 'chainloader '
        if int(inst.chainstart) != 0:
            ostr += str(int(inst.chainstart))
        ostr += '+' + str(int(inst.chaincount)) + '\n'
        return ostr

    def _prop_validate(self, key, value=None, validate_value=False):
        if key == BootLoader.PROP_BOOT_TARGS:
            if validate_value is True and value != 'bios':
                raise BootmgmtUnsupportedPlatformError(value + ' is not a '
                      'supported firmware type for ' + self.__class__.__name__)
            return
        super(self.__class__, self)._prop_validate(key, value, validate_value)

    # Property-related methods

    def setprop(self, key, value):
        """Set a Boot Loader property.  Raises BootmgmtUnsupportedPropertyError
        if the property is not supported"""

        self._prop_validate(key, value, True)

        # XXX - Check that the value for each property is well-formed
        if self._bl_props.get(key, None) != value:
            self._bl_props[key] = value
            self.dirty = True

    def getprop(self, key):
        "Get a Boot Loader property"

        self._prop_validate(key)

        return self._bl_props.get(key, None)

    def delprop(self, key):
        "Delete a Boot Loader property"

        self._prop_validate(key)

        # Check pseudoproperties:
        if key == BootLoader.PROP_BOOT_TARGS:
            raise BootmgmtUnsupportedOperationError("key `%s' may not be "
                                                    "deleted" % key)
        try:
            del self._bl_props[key]
            self.dirty = True
        except KeyError as err:
            raise BootmgmtUnsupportedOperationError("key `%s' does not exist"
                   % key, err)

    # BootLoader installation methods

    def install(self, location):

        if isinstance(location, basestring):
            try:
                filemode = os.stat(location).st_mode
            except OSError as err:
                raise BootLoaderInstallError('Error stat()ing %s' % location,
                                             err)

            if stat.S_ISDIR(filemode):
                # We have been given an output directory.  Produce the menu.lst
                # there.
                return self._write_config(location)

                # XXX - Handle other types of boot_class here (copying pxegrub,
                # stage2_eltorito)
            elif stat.S_ISCHR(filemode):
                self._write_loader(location)
                # Now write the menu.lst:
                self._write_config(None)
            else:
                raise BootmgmtArgumentError('Invalid location argument (%s)'
                                            % location)
        else:
            for devname in location:
                try:
                    filemode = os.stat(devname).st_mode
                except OSError as err:
                    self._debug('Error stat()ing %s' % devname)
                    raise BootLoaderInstallError('Error stat()ing %s' % devname,
                                                 err)
                if stat.S_ISCHR(filemode):
                    self._write_loader(devname)
                else:
                    raise BootmgmtArgumentError('%s is not a characters-special'
                                                ' file' % devname)

            self._write_config(None)

        return None

    # _write_loader performs the real guts of boot loader installation
    def _write_loader(self, devname):
        """Invoke installgrub to write stage1 and stage2 to disk.  If 
        devname is a p0 node,  pass -m to installgrub"""

        # Transform the devname if s0 wasn't passed in
        mbr = False
        realdev = devname

        if len(devname) > 2 and (devname[-2] == 'p' and devname[-1].isdigit()):
            mbr = (devname[-1] == '0' or int(devname[-1]) > 4)
            realdev = devname[:-2] + 's0'
        elif len(devname) > 3 and (devname[-3] == 'p' and
             devname[-2].isdigit() and devname[-1].isdigit()):
            realdev = devname[:-3] + 's0'
            mbr = True  # Extended partition specified, MBR is required

        args = ['/usr/sbin/installgrub']

        if mbr is True:
            args += ['-m']

        # If a version is present, try to use it during installation.
        if not self.version is None:
            args += ['-u', self.version]

        args += [self.rootpath + '/boot/grub/stage1',
                 self.rootpath + '/boot/grub/stage2',
                 realdev]

        self._debug('_write_loader: Invoking command: ' + ' '.join(args))

        try:
            Popen(args, stdout=Popen.PIPE, stderr=Popen.PIPE)
        except CalledProcessError as cpe:
            self._debug('_write_loader: Return code = %d' % cpe.returncode)
            if cpe.returncode != LegacyGRUBBootLoader.INSTALLGRUB_NOUPDT:
                output = ''
                if not cpe.popen is None and not cpe.popen.stderr is None:
                    output = '\nOutput was:\n' + cpe.popen.stderr
                raise BootLoaderInstallError('installgrub failed for '
                      'device ' + devname + ': Return code ' +
                      str(cpe.returncode) + output)

    def _get_loader_version(self, devname):
        """[DEPRECATED AND CURRENTLY UNUSED] Invoke installgrub -ie and
        return the first line (version string)."""

        args = ['/usr/sbin/installgrub', '-ie', devname]
        try:
            proc = Popen(args, stdout=Popen.STORE, stderr=Popen.STORE)
            version_string = proc.stdout.split('\n')[0]
            return version_string
        except CalledProcessError as cpe:
            if cpe.returncode != LegacyGRUBBootLoader.INSTALLGRUB_NOEINFO:
                output = ''
                if not cpe.popen is None and not cpe.popen.stderr is None:
                    output = '\nOutput was:\n' + cpe.popen.stderr
                self._debug('installgrub version check returned ' +
                            str(cpe.returncode) + '.  Ignoring.' + output)
            return None

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

