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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import re

h_file = file('/usr/include/admin/transfermod.h', 'r').read()

# Search transfermod.h for the #defines and place the name value
# pairs into a dictionary.
finder = re.compile(r'^#define\s+(\S+?)\s+(\S+?)$', re.M)
tm_defines = dict(finder.findall(h_file))

TM_SUCCESS =  int(tm_defines['TM_SUCCESS'])
TM_ATTR_IMAGE_INFO = tm_defines['TM_ATTR_IMAGE_INFO'].strip('"')
TM_ATTR_MECHANISM =  tm_defines['TM_ATTR_MECHANISM'].strip('"')
TM_CPIO_ACTION = tm_defines['TM_CPIO_ACTION'].strip('"')
TM_IPS_ACTION = tm_defines['TM_IPS_ACTION'].strip('"')
TM_CPIO_SRC_MNTPT = tm_defines['TM_CPIO_SRC_MNTPT'].strip('"')
TM_CPIO_DST_MNTPT = tm_defines['TM_CPIO_DST_MNTPT'].strip('"')
TM_CPIO_LIST_FILE = tm_defines['TM_CPIO_LIST_FILE'].strip('"')
TM_CPIO_ENTIRE_SKIP_FILE_LIST = tm_defines['TM_CPIO_ENTIRE_SKIP_FILE_LIST'].strip('"')
TM_CPIO_ARGS= tm_defines['TM_CPIO_ARGS'].strip('"')
TM_IPS_PKG_URL = tm_defines['TM_IPS_PKG_URL'].strip('"')
TM_IPS_PKG_AUTH = tm_defines['TM_IPS_PKG_AUTH'].strip('"')
TM_IPS_INIT_MNTPT = tm_defines['TM_IPS_INIT_MNTPT'].strip('"')
TM_IPS_PKGS = tm_defines['TM_IPS_PKGS'].strip('"')
TM_PERFORM_CPIO = int(tm_defines['TM_PERFORM_CPIO'])
TM_PERFORM_IPS = int(tm_defines['TM_PERFORM_IPS'])
TM_CPIO_ENTIRE = int(tm_defines['TM_CPIO_ENTIRE'])
TM_CPIO_LIST = int(tm_defines['TM_CPIO_LIST'])
TM_IPS_INIT = int(tm_defines['TM_IPS_INIT'])
TM_IPS_REPO_CONTENTS_VERIFY = int(tm_defines['TM_IPS_REPO_CONTENTS_VERIFY'])
TM_IPS_RETRIEVE = int(tm_defines['TM_IPS_RETRIEVE'])
TM_IPS_REFRESH = int(tm_defines['TM_IPS_REFRESH'])
TM_IPS_SET_AUTH = int(tm_defines['TM_IPS_SET_AUTH'])
TM_IPS_UNSET_AUTH = int(tm_defines['TM_IPS_UNSET_AUTH'])
TM_IPS_SET_PROP = int(tm_defines['TM_IPS_SET_PROP'])
TM_IPS_PURGE_HIST = int(tm_defines['TM_IPS_PURGE_HIST'])
TM_IPS_IMAGE_TYPE = tm_defines['TM_IPS_IMAGE_TYPE'].strip('"')
TM_IPS_IMAGE_FULL = tm_defines['TM_IPS_IMAGE_FULL'].strip('"')
TM_IPS_IMAGE_PARTIAL = tm_defines['TM_IPS_IMAGE_PARTIAL'].strip('"')
TM_IPS_IMAGE_USER = tm_defines['TM_IPS_IMAGE_USER'].strip('"')
TM_IPS_IMAGE_CREATE_FORCE = tm_defines['TM_IPS_IMAGE_CREATE_FORCE'].strip('"')
TM_IPS_VERBOSE_MODE = tm_defines['TM_IPS_VERBOSE_MODE'].strip('"')
TM_IPS_ALT_AUTH = tm_defines['TM_IPS_ALT_AUTH'].strip('"')
TM_IPS_PREF_FLAG = tm_defines['TM_IPS_PREF_FLAG'].strip('"')
TM_IPS_MIRROR_FLAG = tm_defines['TM_IPS_MIRROR_FLAG'].strip('"')
TM_IPS_SET_MIRROR = tm_defines['TM_IPS_SET_MIRROR'].strip('"')
TM_IPS_UNSET_MIRROR = tm_defines['TM_IPS_UNSET_MIRROR'].strip('"')
TM_IPS_PREFERRED_AUTH = tm_defines['TM_IPS_PREFERRED_AUTH'].strip('"')
TM_IPS_UNINSTALL = int(tm_defines['TM_IPS_UNINSTALL'])
TM_IPS_GENERATE_SEARCH_INDEX = tm_defines['TM_IPS_GENERATE_SEARCH_INDEX'].strip('"')
TM_IPS_REFRESH_CATALOG = tm_defines['TM_IPS_REFRESH_CATALOG'].strip('"')
TM_IPS_PROP_NAME = tm_defines['TM_IPS_PROP_NAME'].strip('"')
TM_IPS_PROP_VALUE = tm_defines['TM_IPS_PROP_VALUE'].strip('"')

TM_IPS_ALT_URL = tm_defines['TM_IPS_ALT_URL'].strip('"')

# The following is only useful for python code, not C code.  So, it will 
# only be defined here, instead of being defined in transfermod.h
TM_PYTHON_LOG_HANDLER = "TM_PYTHON_LOG_HANDLER"

KIOCLAYOUT = (107<<8)|20

# Now search for the typedef enum blocks
typedef_enum_finder = re.compile('typedef enum {(.*?)}', re.S)

#And parse it out with the findall method
tm_enums = typedef_enum_finder.search(h_file)
tm_enums = tm_enums.group()

# remove the typdef enum {
enum_remover = re.compile(r'typedef enum {')
tm_enums = enum_remover.sub('', tm_enums)

# remove the comments
comment_remover = re.compile(r'\/\*.*?\*\/')
tm_enums = comment_remover.sub('', tm_enums)

# remove the trailing } 
paren_remover= re.compile(r'}')
tm_enums = paren_remover.sub('', tm_enums)

# And finally, remove the = 0
tm_enums = re.sub(r'=[^,]*', '', tm_enums)

# Split on ',' characters and only keep the TM_E_* lines.
# Strip off whitespaces
var_names = [line.strip()
	for line in tm_enums.split(',')
	if line.lstrip().startswith('TM_E_')]

for i, var_name in enumerate(var_names):
	exec('%s = %s' % (var_name, i))

TRANSFER_ID = "TRANSFER_MOD"
