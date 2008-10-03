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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

# manifest file node path definitions.
DISTRO_NAME = "name"
DISTRO_PARAMS = "distro_constr_params"
IMG_PARAMS = "img_params"
DISTRO_FLAGS = DISTRO_PARAMS + "/distro_constr_flags"
STOP_ON_ERR = DISTRO_FLAGS + "/stop_on_error"
CHECKPOINT_ENABLE = DISTRO_FLAGS + "/checkpoint_enable"
CHECKPOINT_RESUME = CHECKPOINT_ENABLE + "/resume_from"
DEFAULT_REPO = DISTRO_PARAMS + "/pkg_repo_default_authority"
DEFAULT_MAIN =  DEFAULT_REPO + "/main/"
DEFAULT_MAIN_AUTHNAME = DEFAULT_MAIN + "/authname"
DEFAULT_MAIN_URL = DEFAULT_MAIN + "/url"
DEFAULT_MIRROR = DEFAULT_REPO + "/mirror"
DEFAULT_MIRROR_AUTHNAME = DEFAULT_MIRROR + "/authname"
DEFAULT_MIRROR_URL = DEFAULT_MIRROR + "/url"
ADD_AUTH = DISTRO_PARAMS + "/pkg_repo_addl_authority"
ADD_AUTH_MAIN = ADD_AUTH + "/main"
ADD_AUTH_MAIN_AUTHNAME = ADD_AUTH_MAIN + "/authname"
ADD_AUTH_MAIN_URL = ADD_AUTH_MAIN + "/url"
ADD_AUTH_MIRROR = ADD_AUTH + "/mirror"
ADD_AUTH_MIRROR_AUTHNAME = ADD_AUTH_MIRROR + "/authname"
ADD_AUTH_MIRROR_URL = ADD_AUTH_MIRROR + "/url"
PACKAGES = IMG_PARAMS + "/packages"
PKG =  PACKAGES + "/pkg"
PKG_NAME =  PKG + "/name"
PKG_ATTRS =  PKG + "/attrs"
PKG_TAGS =  PKG + "/tags"
BOOT_ROOT_CONTENTS = IMG_PARAMS + "/bootroot_contents"
BOOT_ROOT_CONTENTS_BASE_INCLUDE = BOOT_ROOT_CONTENTS + "/base_include" 
BOOT_ROOT_CONTENTS_BASE_EXCLUDE = BOOT_ROOT_CONTENTS + "/base_exclude" 
BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_DIR = BOOT_ROOT_CONTENTS_BASE_INCLUDE + "[type=\"dir\"]"
BOOT_ROOT_CONTENTS_BASE_EXCLUDE_TO_TYPE_DIR = BOOT_ROOT_CONTENTS_BASE_EXCLUDE + "[type=\"dir\"]"
BOOT_ROOT_CONTENTS_BASE_INCLUDE_TO_TYPE_FILE = BOOT_ROOT_CONTENTS_BASE_INCLUDE + "[type=\"file\"]"
COMPRESSION_TYPE = IMG_PARAMS + "/live_img_compression/type"
COMPRESSION_LEVEL = IMG_PARAMS + "/live_img_compression/level"
BUILD_AREA = IMG_PARAMS + "/build_area"
OUTPUT_IMAGE = IMG_PARAMS + "/output_image"
USER = IMG_PARAMS + "/user"
USER_UID = USER + "/UID"
LOCALE_LIST = IMG_PARAMS + "/locale_list"
FINALIZER_SCRIPT = OUTPUT_IMAGE + "/finalizer/script"
FINALIZER_SCRIPT_NAME = FINALIZER_SCRIPT + "/name"
FINALIZER_SCRIPT_ARGS = FINALIZER_SCRIPT + "/argslist"
FINALIZER_SCRIPT_OUT_LOG = FINALIZER_SCRIPT + "/stdout_logfile"
FINALIZER_SCRIPT_ERR_LOG = FINALIZER_SCRIPT + "/stderr_logfile"
FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_MESSAGE = FINALIZER_SCRIPT + "[name=\"%s\"]/checkpoint/message"
FINALIZER_SCRIPT_NAME_TO_CHECKPOINT_NAME = FINALIZER_SCRIPT + "[name=\"%s\"]/checkpoint/name"
MIRROR_URL_TO_AUTHNAME = DEFAULT_MIRROR + "[url=\"%s\"]/authname"
ADD_AUTH_URL_TO_AUTHNAME = ADD_AUTH_MAIN + "[url=\"%s\"]/authname"
ADD_AUTH_MIRROR_URL_TO_AUTHNAME = ADD_AUTH_MIRROR + "[url=\"%s\"]/authname"
FINALIZER_SCRIPT_NAME_TO_ARGSLIST = FINALIZER_SCRIPT + "[name=\"%s\"]/argslist"
FINALIZER_SCRIPT_NAME_TO_STDOUT_LOG = FINALIZER_SCRIPT + "[name=\"%s\"]/stdout_logfile"
FINALIZER_SCRIPT_NAME_TO_STDERR_LOG = FINALIZER_SCRIPT + "[name=\"%s\"]/stderr_logfile"

FUTURE_URL = "http://pkg.opensolaris.org:80"
FUTURE_AUTH = "opensolaris.org"

# Path to the DC-manifest.rng and DC-manifest.defval.xml file.
# This is NOT the manifest user provides to building their images.
DC_MANIFEST_DATA="/usr/share/distro_const/DC-manifest"

FINALIZER_ROLLBACK_SCRIPT="/usr/share/distro_const/finalizer_rollback.py"
FINALIZER_CHECKPOINT_SCRIPT="/usr/share/distro_const/finalizer_checkpoint.py"

# Build area directory structure definitions. We will create
# subdirectories in the build area such that when completed we
# have <build_area>/build_data, <build_area>/build_data/pkg_image,
# <build_area>/build_data/tmp, <build_area>/build_data/bootroot,
# <build_area>/media, and <build_area>/logs
BUILD_DATA="/build_data"
PKG_IMAGE=BUILD_DATA + "/pkg_image"
TMP=BUILD_DATA + "/tmp"
BOOTROOT=BUILD_DATA + "/bootroot"
MEDIA="/media"
LOGS="/logs"

# boot root definitions.
BR_ROOT="/bmr"
BR_NAME="/x86.microroot"
