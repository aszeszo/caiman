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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

"""Transfer Module Definitions
   """
import re
import sys

H_FILE = file('/usr/include/admin/transfermod.h', 'r').read()

# Search transfermod.h for the #defines and place the name value
# pairs into a dictionary.
FINDER = re.compile(r'^#define\s+(\S+?)\s+(\S+?)$', re.M)
TM_DEFINES = dict(FINDER.findall(H_FILE))

TM_SUCCESS = int(TM_DEFINES['TM_SUCCESS'])
TM_ATTR_IMAGE_INFO = TM_DEFINES['TM_ATTR_IMAGE_INFO'].strip('"')
TM_ATTR_MECHANISM = TM_DEFINES['TM_ATTR_MECHANISM'].strip('"')
TM_CPIO_ACTION = TM_DEFINES['TM_CPIO_ACTION'].strip('"')
TM_IPS_ACTION = TM_DEFINES['TM_IPS_ACTION'].strip('"')
TM_CPIO_SRC_MNTPT = TM_DEFINES['TM_CPIO_SRC_MNTPT'].strip('"')
TM_CPIO_DST_MNTPT = TM_DEFINES['TM_CPIO_DST_MNTPT'].strip('"')
TM_CPIO_LIST_FILE = TM_DEFINES['TM_CPIO_LIST_FILE'].strip('"')
TM_CPIO_ENTIRE_SKIP_FILE_LIST = \
    TM_DEFINES['TM_CPIO_ENTIRE_SKIP_FILE_LIST'].strip('"')
TM_CPIO_ARGS = TM_DEFINES['TM_CPIO_ARGS'].strip('"')
TM_IPS_PKG_URL = TM_DEFINES['TM_IPS_PKG_URL'].strip('"')
TM_IPS_PKG_AUTH = TM_DEFINES['TM_IPS_PKG_AUTH'].strip('"')
TM_IPS_INIT_MNTPT = TM_DEFINES['TM_IPS_INIT_MNTPT'].strip('"')
TM_IPS_PKGS = TM_DEFINES['TM_IPS_PKGS'].strip('"')
TM_PERFORM_CPIO = int(TM_DEFINES['TM_PERFORM_CPIO'])
TM_PERFORM_IPS = int(TM_DEFINES['TM_PERFORM_IPS'])
TM_CPIO_ENTIRE = int(TM_DEFINES['TM_CPIO_ENTIRE'])
TM_CPIO_LIST = int(TM_DEFINES['TM_CPIO_LIST'])
TM_IPS_INIT_RETRY_TIMEOUT = TM_DEFINES['TM_IPS_INIT_RETRY_TIMEOUT'].strip('"')
TM_IPS_INIT = int(TM_DEFINES['TM_IPS_INIT'])
TM_IPS_REPO_CONTENTS_VERIFY = int(TM_DEFINES['TM_IPS_REPO_CONTENTS_VERIFY'])
TM_IPS_RETRIEVE = int(TM_DEFINES['TM_IPS_RETRIEVE'])
TM_IPS_REFRESH = int(TM_DEFINES['TM_IPS_REFRESH'])
TM_IPS_SET_AUTH = int(TM_DEFINES['TM_IPS_SET_AUTH'])
TM_IPS_UNSET_AUTH = int(TM_DEFINES['TM_IPS_UNSET_AUTH'])
TM_IPS_SET_PROP = int(TM_DEFINES['TM_IPS_SET_PROP'])
TM_IPS_PURGE_HIST = int(TM_DEFINES['TM_IPS_PURGE_HIST'])
TM_IPS_IMAGE_TYPE = TM_DEFINES['TM_IPS_IMAGE_TYPE'].strip('"')
TM_IPS_IMAGE_FULL = TM_DEFINES['TM_IPS_IMAGE_FULL'].strip('"')
TM_IPS_IMAGE_PARTIAL = TM_DEFINES['TM_IPS_IMAGE_PARTIAL'].strip('"')
TM_IPS_IMAGE_USER = TM_DEFINES['TM_IPS_IMAGE_USER'].strip('"')
TM_IPS_IMAGE_CREATE_FORCE = TM_DEFINES['TM_IPS_IMAGE_CREATE_FORCE'].strip('"')
TM_IPS_VERBOSE_MODE = TM_DEFINES['TM_IPS_VERBOSE_MODE'].strip('"')
TM_IPS_ALT_AUTH = TM_DEFINES['TM_IPS_ALT_AUTH'].strip('"')
TM_IPS_PREF_FLAG = TM_DEFINES['TM_IPS_PREF_FLAG'].strip('"')
TM_IPS_MIRROR_FLAG = TM_DEFINES['TM_IPS_MIRROR_FLAG'].strip('"')
TM_IPS_SET_MIRROR = TM_DEFINES['TM_IPS_SET_MIRROR'].strip('"')
TM_IPS_UNSET_MIRROR = TM_DEFINES['TM_IPS_UNSET_MIRROR'].strip('"')
TM_IPS_PREFERRED_AUTH = TM_DEFINES['TM_IPS_PREFERRED_AUTH'].strip('"')
TM_IPS_UNINSTALL = int(TM_DEFINES['TM_IPS_UNINSTALL'])
TM_IPS_GENERATE_SEARCH_INDEX = \
    TM_DEFINES['TM_IPS_GENERATE_SEARCH_INDEX'].strip('"')
TM_IPS_REFRESH_CATALOG = TM_DEFINES['TM_IPS_REFRESH_CATALOG'].strip('"')
TM_IPS_PROP_NAME = TM_DEFINES['TM_IPS_PROP_NAME'].strip('"')
TM_IPS_PROP_VALUE = TM_DEFINES['TM_IPS_PROP_VALUE'].strip('"')
TM_IPS_ALT_URL = TM_DEFINES['TM_IPS_ALT_URL'].strip('"')
TM_UNPACK_ARCHIVE = TM_DEFINES['TM_UNPACK_ARCHIVE'].strip('"')

# The following is only useful for python code, not C code.  So, it will 
# only be defined here, instead of being defined in transfermod.h
TM_PYTHON_LOG_HANDLER = "TM_PYTHON_LOG_HANDLER"

KIOCLAYOUT = (107 << 8) | 20

# Now search for the typedef enum blocks
TYPEDEF_ENUM_FINDER = re.compile('typedef enum {(.*?)}', re.S)

#And parse it out with the findall method
TM_ENUMS = TYPEDEF_ENUM_FINDER.search(H_FILE)
TM_ENUMS = TM_ENUMS.group()

# remove the typdef enum {
ENUM_REMOVER = re.compile(r'typedef enum {')
TM_ENUMS = ENUM_REMOVER.sub('', TM_ENUMS)

# remove the comments
COMMENT_REMOVER = re.compile(r'\/\*.*?\*\/')
TM_ENUMS = COMMENT_REMOVER.sub('', TM_ENUMS)

# remove the trailing } 
PAREN_REMOVER = re.compile(r'}')
TM_ENUMS = PAREN_REMOVER.sub('', TM_ENUMS)

# And finally, remove the = 0
TM_ENUMS = re.sub(r'=[^,]*', '', TM_ENUMS)

# Split on ',' characters and only keep the TM_E_* lines.
# Strip off whitespaces
VAR_NAMES = [line.strip()
             for line in TM_ENUMS.split(',')
             if line.lstrip().startswith('TM_E_')]

for idx, var in enumerate(VAR_NAMES):
    setattr(sys.modules[__name__], var, idx)

TRANSFER_ID = "TRANSFER_MOD"
