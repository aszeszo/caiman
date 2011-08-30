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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Defines SystemInfo class which serves as a container for following
system information:
 - hostname
 - time zone
 - language and locale
 - keyboard layout
 - terminal type
'''

import array
import fcntl
import locale
import logging
import platform
from subprocess import Popen, PIPE

import solaris_install.data_object as data_object
from solaris_install.getconsole import get_console, SERIAL_CONSOLE,\
    PHYSICAL_CONSOLE
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile import SMFConfig, SMFInstance, \
                                              SMFPropertyGroup, SYSTEM_LABEL


_LOGGER = None


def LOGGER():
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger(INSTALL_LOGGER_NAME + ".sysconfig")
    return _LOGGER


class SystemInfo(data_object.DataObject):
    '''
    Represents miscellaneous system information
    '''
    
    DEFAULT_HOSTNAME = "solaris"
    UTC = "UTC"
    
    DEFAULT_LOCALE = "C"
    DEFAULT_ACTUAL_LOCALE = "C/POSIX"

    # The maximum length of the hostname should ideally come from
    # a call to os.sysconf('SC_HOST_NAME_MAX') (see similar calls
    # in user_info.py) but this currently results in a ValueError.
    MAX_HOSTNAME_LEN = 256
    
    LABEL = SYSTEM_LABEL

    def __init__(self, hostname=None, tz_region=None,
                 tz_country=None, tz_timezone=None, time_offset=0,
                 keyboard=None, locale=None, actual_lang=None,
                 terminal_type=None):
        data_object.DataObject.__init__(self, self.LABEL)
        
        if hostname is None:
            hostname = SystemInfo.DEFAULT_HOSTNAME
        self.hostname = hostname
        self.tz_region = tz_region
        self.tz_country = tz_country
        self.tz_timezone = tz_timezone
        self.time_offset = time_offset
        self.locale = locale
        self.actual_lang = actual_lang
        self.terminal_type = terminal_type
        #
        # /usr/share/lib/keytables/type_6/kbd_layouts file contains mapping
        # of available keyboard layout numbers to strings in form of
        # <layout_string>=<layout_number>, for instance 'Czech=5'
        #
        self.kbd_layout_file = '/usr/share/lib/keytables/type_6/kbd_layouts'
        self.kbd_device = '/dev/kbd'

        #
        # If keyboard layout was not specified, set it to the current one.
        # If current one can't be determined, go with 'US-English'
        # as a default value.
        #
        if keyboard is None:
            keyboard = self.determine_keyboard_layout(self.kbd_device,
                                                      self.kbd_layout_file)
        if keyboard is None:
            LOGGER().warn("Failed to obtain current keyboard layout, using "
                         "US-English as a default")
            keyboard = 'US-English'
        self.keyboard = keyboard

        # If terminal type was not specified, determine default one.
        if self.terminal_type is None:
            self.terminal_type = self.determine_terminal_type()

    def __repr__(self):
        result = ["System Info:"]
        result.append("\nHostname: ")
        result.append(str(self.hostname))
        result.append("\nTZ: ")
        result.append(str(self.tz_region))
        result.append(" - ")
        result.append(str(self.tz_country))
        result.append(" - ")
        result.append(str(self.tz_timezone))
        result.append("\nTime Offset: ")
        result.append(str(self.time_offset))
        result.append("\nKeyboard: ")
        result.append(str(self.keyboard))
        result.append("\nLocale: ")
        result.append(str(self.locale))
        return "".join(result)
    
    @staticmethod
    def get_actual_lang(locale):
        '''Determine the human readable language from the locale

        '''

        try:
            fp = open("/usr/share/gui-install/langs_localized")
        except:
            raise ValueError(
                "Unable to open /usr/share/gui-install/langs_localized")
        
        for line in fp:
            key, splitter, val = line.partition(":")
            if key == locale:
                return (val.rstrip())

        raise ValueError("Unsupported language for locale " + locale)

    @staticmethod
    def determine_keyboard_layout(kbd_device, kbd_layout_file):
        '''Read in the keyboard layout set during boot.'''
        '''Get keyboard layout using ioctl KIOCLAYOUT on /dev/kbd
        Return current keyboard layout in form of string or None if it can't
        be determined.
        '''
        #ioctl codes taken from /usr/include/sys/kbio.h
        kioc = ord('k') << 8
        kioclayout = kioc | 20
        LOGGER().info("Opening keyboard device: %s", kbd_device)
        try:
            kbd = open(kbd_device, "r+")
        except IOError:
            LOGGER().warn("Failed to open keyboard device %s", kbd_device)
            return None

        k = array.array('i', [0])
        
        try:
            status = fcntl.ioctl(kbd, kioclayout, k, 1)
        except IOError as err:
            status = err.errno
            LOGGER().warn("fcntl.ioctl() KIOCLAYOUT_FAILED: status=%s",
                         status=err.errno)
            kbd.close()
            return None
        
        layout_number = k.tolist()[0]
        kbd.close()

        '''now convert a keyboard layout to the layout string.

        We should not be doing this here, but unfortunately there
        is no interface in the keyboard API to perform
        this mapping for us - RFE 7009857.'''
        kbd_layout_name = None
        try:
            with open(kbd_layout_file, "r") as fh:
                # read file until keyboard layout number matches
                for line in fh:
                    # ignore comments
                    if line.startswith('#'):
                        continue
                    if '=' not in line:
                        continue
                    (kbd_lname, num) = line.split('=')
                    if int(num) == layout_number:
                        kbd_layout_name = kbd_lname
                        break
        except IOError:
            LOGGER().warn("Failed to open keyboard layout file %s",
                kbd_layout_file)

        LOGGER().info("Detected following current keyboard layout: %s",
                     kbd_layout_name)

        return kbd_layout_name

    @staticmethod
    def determine_terminal_type():
        '''Determine default value for terminal type from type
        of running environment.
        Use following algorithm:
         - If connected to SPARC via keyboard/monitor, use "sun"
         - If connected to X86 via keyboard/monitor, use "sun-color"
         - If connected to X86 and unable to determine whether we are using
           physical or serial console, use "sun-color"
         - If running on serial console, use "vt100"
         - Otherwise, use "vt100"'''

        term_type = "vt100"

        console_type = get_console()

        LOGGER().info("console type: %s", console_type)

        if platform.processor() == "i386":
            if console_type != SERIAL_CONSOLE:
                # not on physical console or unable to determine console type
                term_type = "sun-color"
        else:
            # SPARC
            if console_type == PHYSICAL_CONSOLE:
                term_type = "sun"

        return term_type

    def determine_locale(self):
        '''Read in the language set during boot.'''
        # getdefaultlocale() returns a tuple such as ('en_US', 'UTF8')
        # The second portion of that tuple is not formatted correctly for
        # processing, so use getpreferredencoding() to get the encoding.
        language = locale.getdefaultlocale()[0]
        encoding = locale.getpreferredencoding()
        
        if language is None:
            self.locale = SystemInfo.DEFAULT_LOCALE
            self.actual_lang = SystemInfo.DEFAULT_ACTUAL_LOCALE
        else:
            if encoding:
                self.locale = ".".join([language, encoding])
            else:
                self.locale = language
            try:
                self.actual_lang = self.get_actual_lang(self.locale)
            except ValueError, err:
                LOGGER().warn(err)
                self.actual_lang = self.locale
    
    def to_xml(self):
        data_objects = []

        #
        # fmri:
        #  svc:/system/timezone:default
        #
        # configures:
        #  timezone - timezone/localtime smf property
        #
        if self.tz_timezone is not None:
            smf_svc_timezone = SMFConfig('system/timezone')
            data_objects.append(smf_svc_timezone)
        
            smf_svc_timezone_default = SMFInstance('default')
            smf_svc_timezone.insert_children(smf_svc_timezone_default)
            smf_pg_timezone = SMFPropertyGroup('timezone')
            smf_svc_timezone_default.insert_children(smf_pg_timezone)

            smf_pg_timezone.add_props(localtime=self.tz_timezone)

        #
        # fmri:
        #  svc:/system/environment:init
        #
        # configures:
        #  locale - environment/LANG smf property
        #
        if self.locale is not None:
            smf_svc_env = SMFConfig('system/environment')
            data_objects.append(smf_svc_env)
        
            smf_svc_env_init = SMFInstance('init')
            smf_svc_env.insert_children(smf_svc_env_init)
            smf_pg_env = SMFPropertyGroup('environment')
            smf_svc_env_init.insert_children(smf_pg_env)

            smf_pg_env.add_props(LANG=self.locale)

        #
        # fmri:
        #  svc:/system/identity:node
        #
        # configures:
        #  system hostname - config/nodename smf property
        #

        smf_svc_system_identity = SMFConfig('system/identity')
        data_objects.append(smf_svc_system_identity)
        smf_instance_system_identity = SMFInstance('node')
        smf_svc_system_identity.insert_children([smf_instance_system_identity])

        smf_pg_config = SMFPropertyGroup('config')
        smf_instance_system_identity.insert_children([smf_pg_config])

        smf_pg_config.add_props(nodename=self.hostname)

        #
        # fmri:
        #  svc:/system/keymap/config:default
        #
        # configures:
        #  keyboard layout - keymap/layout smf property
        #

        smf_svc_keymap = SMFConfig('system/keymap')
        data_objects.append(smf_svc_keymap)
        smf_instance_keymap = SMFInstance('default')
        smf_svc_keymap.insert_children([smf_instance_keymap])
        
        smf_pg_keymap = SMFPropertyGroup('keymap', pg_type='system')
        smf_instance_keymap.insert_children([smf_pg_keymap])
        
        smf_pg_keymap.add_props(layout=self.keyboard)
        
        #
        # fmri:
        #  svc:/system/console-login:default
        #
        # configures:
        #  terminal type - ttymon/terminal_type smf property
        #
        
        smf_svc_console = SMFConfig('system/console-login')
        data_objects.append(smf_svc_console)
        smf_instance_console = SMFInstance('default')
        smf_svc_console.insert_children([smf_instance_console])
        
        smf_pg_ttymon = SMFPropertyGroup('ttymon')
        smf_instance_console.insert_children([smf_pg_ttymon])
        
        smf_pg_ttymon.add_props(terminal_type=self.terminal_type)
        
        return [do.get_xml_tree() for do in data_objects]

    @classmethod
    def from_xml(cls, xml_node):
        return None
    
    @classmethod
    def can_handle(cls, xml_node):
        return False
