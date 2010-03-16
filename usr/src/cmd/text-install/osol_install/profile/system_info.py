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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

'''
Represent Systemwide attributes such as timezone and locale 
'''

import locale
import logging


class SystemInfo(object):
    '''
    Represents miscellaneous system information
    '''
    
    DEFAULT_HOSTNAME = "opensolaris"
    UTC = "UTC"
    
    DEFAULT_LOCALE = "C"
    DEFAULT_ACTUAL_LOCALE = "C/POSIX"

    def __init__(self, hostname=None, tz_region=None,
                 tz_country=None, tz_timezone=None, time_offset=0,
                 keyboard=None, locale=None, actual_lang=None):
        if hostname is None:
            hostname = SystemInfo.DEFAULT_HOSTNAME
        self.hostname = hostname
        self.tz_region = tz_region
        self.tz_country = tz_country
        self.tz_timezone = tz_timezone
        self.time_offset = time_offset
        self.keyboard = keyboard
        self.locale = locale
        self.actual_lang = actual_lang 
    
    def __str__(self):
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
                logging.warn(err)
                self.actual_lang = self.locale

