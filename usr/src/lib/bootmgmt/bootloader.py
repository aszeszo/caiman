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
Boot loader abstraction for pybootmgmt
"""

from bootmgmt.backend.loader import BackendBootLoaderFactory
from bootmgmt.bootinfo import SystemFirmware
from bootmgmt.bootutil import LoggerMixin
from bootmgmt import (BootmgmtError, BootmgmtNotSupportedError,
                      BootmgmtUnsupportedPropertyError,
                      BootmgmtUnsupportedOperationError)


class BootLoader(LoggerMixin):

    PROP_MINMEM64 = 'minmem64'
    PROP_TIMEOUT = 'timeout'

    PROP_CONSOLE = 'console'
    PROP_CONSOLE_TEXT = 'text'
    PROP_CONSOLE_GFX = 'graphics'
    PROP_CONSOLE_SERIAL = 'serial'

    PROP_SERIAL_PARAMS = 'serial_params'

    PROP_QUIET = 'quiet'

    PROP_BOOT_TARGS = 'boot-targets'

    PROP_SPLASH = "splashimage"
    PROP_FORECOLOR = "foreground"
    PROP_BACKCOLOR = "background"

    # When console=serial, this property should be set:
    PROP_SERIAL_PARAMS = 'serial_params'
    # Indices for the serial_params tuple:
    PROP_SP_PORT = 0
    PROP_SP_SPEED = 1
    PROP_SP_DATAB = 2
    PROP_SP_PARITY = 3
    PROP_SP_STOPB = 4
    PROP_SP_FLOWC = 5

    @staticmethod
    def get(**kwargs):
        return BackendBootLoaderFactory.get(**kwargs)

    @classmethod
    def probe(cls, **kwargs):
        return (None, None)

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        if not type(value) is bool:
            raise ValueError('dirty must be a bool')
        if value != self._dirty:
            self._debug('dirty => ' + str(value))
            self._dirty = value

    def __init__(self, **kwargs):
        self._dirty = False
        self.old_loader = None
        self.devices = kwargs.get('devices', None)
        self.firmware = SystemFirmware.get(kwargs.get('fwtype', None))
        self.version = kwargs.get('version', None)
        self._boot_config = kwargs.get('bootconfig', None)
        self.data_source_boot_instance = None
        self._bl_props = {}

        # If there is a root dir defined in the bootconfig passed in,
        # and no rootpath, set rootpath to the bootconfig's root.
        bc_sysroot = '/'
        if (not self._boot_config is None and
            not self._boot_config.get_root() is None):
            bc_sysroot = self._boot_config.get_root()

        self.rootpath = kwargs.get('rootpath', bc_sysroot)
        
    def _get_boot_loader_data_root(self):
        """Returns the root to use as the path to boot loader data files"""
        if (not self.data_source_boot_instance is None and
            not self.data_source_boot_instance.rootpath is None):
            return self.data_source_boot_instance.rootpath
        return self.rootpath # Initted in __init__; incl. the fallback to '/'

    def _write_config(self, basepath):
        pass

    def load_config(self):
        pass

    def new_config(self):
        # Clear out the boot loader properties dictionary, except for the
        # boot targets supported by the boot loader
        boot_targs = self._bl_props[BootLoader.PROP_BOOT_TARGS]
        self._bl_props = {BootLoader.PROP_BOOT_TARGS: boot_targs}

    def migrate_config(self):
        pass

    # Property-specific handlers
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
                    parity = {'N': 'no',
                              'E': 'even',
                              'O': 'odd'}[params[BootLoader.PROP_SP_PARITY]]
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

    # Property-related methods
    def _prop_validate(self, key, value=None, validate_value=False):
        """Validate the property key and optionally value"""

        props = getattr(self, 'SUPPORTED_PROPS', [])
        if not key in props:
            raise BootmgmtUnsupportedPropertyError(key + ' is not a supported '
                                                   'property')

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

        self._prop_validate(key, validate_value=False)
        return self._bl_props.get(key, None)

    def delprop(self, key):
        "Delete a Boot Loader property"

        self._prop_validate(key, validate_value=False)

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

    def install(self, location):
        """Install the boot loader onto a disk or set of disks.  location
        is either a single string or a list of strings (each of which
        is a character-special device path, which the boot loader
        will use to determine where to install itself) or a path to a
        directory that will hold the boot loader files and
        configuration files (see below).
        If the version property is set in this BootLoader instance and
        this boot loader supports recording the version number at boot 
        loader installation time, each location specified will be queried
        for boot loader version information.  
        The boot loader will be installed to each installation location
        with a version older than the version specified.

        Note that for some boot configurations (i.e. net and ODD),
        the boot loader isn't installed per-se;  the loader and its
        support files are copied to a well-known location, and that
        location is used as an input to other programs or configuration
        stores (i.e. mkisofs is given the path to a boot image; the
        DHCP server is configured with the name of the NBP (i.e. pxegrub)
        and configuration file(s) for PXE-compliant boot environments,
        etc.).  For these cases, install() will return a set of tuples,
        each of the following form:
           (<type>, <srcpath>, <dstpath>, <owner>, <group>, <mode>)
        <type> depends on the platform and boot configuration that this
        BootLoader is associated with (defined in child classes).
        <srcpath> is the path from which the file should be copied.
        <dstpath> is the path to which the file should be copied (tokens
        are embedded in the path to instruct the consumer of the final
        location (see the commit_boot_config() documentation in children
        of BootConfig for a list of tokens and their expansions)).
        <owner>, <group>, and <mode> are the uid, gid, and permissions
        mode bits (respectively) that should be set on the destination
        file.  
        """
        pass


#
# BootLoader Exceptions
#

class BootLoaderInstallError(BootmgmtError):
    pass


class BootPartitionAccessError(BootLoaderInstallError):
    pass


class BootDeviceNotFoundError(BootLoaderInstallError):
    pass


class BootLoaderFeatureUnsupportedError(BootmgmtNotSupportedError):
    pass


class BootLoaderUnsupportedPartTypeError(BootLoaderFeatureUnsupportedError):
    pass
