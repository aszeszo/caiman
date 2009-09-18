#!/usr/bin/python2.4
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

import re

h_file = file('/usr/include/admin/ti_api.h', 'r').read()

# Search ti_api.h for the #defines and place the name value
# pairs into a dictionary.
finder = re.compile(r'^#define\s+(\S+?)\s+(\S+?)$', re.M)
ti_defines = dict(finder.findall(h_file))

TI_TARGET_TYPE_FDISK =  int(ti_defines['TI_TARGET_TYPE_FDISK'])
TI_TARGET_TYPE_VTOC =  int(ti_defines['TI_TARGET_TYPE_VTOC'])
TI_TARGET_TYPE_ZFS_RPOOL =  int(ti_defines['TI_TARGET_TYPE_ZFS_RPOOL'])
TI_TARGET_TYPE_ZFS_FS =  int(ti_defines['TI_TARGET_TYPE_ZFS_FS'])
TI_TARGET_TYPE_ZFS_VOLUME =  int(ti_defines['TI_TARGET_TYPE_ZFS_VOLUME'])
TI_TARGET_TYPE_BE =  int(ti_defines['TI_TARGET_TYPE_BE'])
TI_TARGET_TYPE_DC_UFS =  int(ti_defines['TI_TARGET_TYPE_DC_UFS'])
TI_TARGET_TYPE_DC_RAMDISK =  int(ti_defines['TI_TARGET_TYPE_DC_RAMDISK'])
TI_ATTR_TARGET_TYPE =  ti_defines['TI_ATTR_TARGET_TYPE'].strip('"')
TI_PROGRESS_MS_NUM =  ti_defines['TI_PROGRESS_MS_NUM'].strip('"')
TI_PROGRESS_MS_CURR =  ti_defines['TI_PROGRESS_MS_CURR'].strip('"')
TI_PROGRESS_MS_PERC =  ti_defines['TI_PROGRESS_MS_PERC'].strip('"')
TI_PROGRESS_MS_PERC_DONE =  ti_defines['TI_PROGRESS_MS_PERC_DONE'].strip('"')
TI_PROGRESS_TOTAL_TIME =  ti_defines['TI_PROGRESS_TOTAL_TIME'].strip('"')
TI_ATTR_FDISK_WDISK_FL =  ti_defines['TI_ATTR_FDISK_WDISK_FL'].strip('"')
TI_ATTR_FDISK_DISK_NAME =  ti_defines['TI_ATTR_FDISK_DISK_NAME'].strip('"')
TI_ATTR_FDISK_PART_NUM =  ti_defines['TI_ATTR_FDISK_PART_NUM'].strip('"')
TI_ATTR_FDISK_PART_IDS =  ti_defines['TI_ATTR_FDISK_PART_IDS'].strip('"')
TI_ATTR_FDISK_PART_ACTIVE =  ti_defines['TI_ATTR_FDISK_PART_ACTIVE'].strip('"')
TI_ATTR_FDISK_PART_BHEADS =  ti_defines['TI_ATTR_FDISK_PART_BHEADS'].strip('"')
TI_ATTR_FDISK_PART_BSECTS =  ti_defines['TI_ATTR_FDISK_PART_BSECTS'].strip('"')
TI_ATTR_FDISK_PART_BCYLS =  ti_defines['TI_ATTR_FDISK_PART_BCYLS'].strip('"')
TI_ATTR_FDISK_PART_EHEADS =  ti_defines['TI_ATTR_FDISK_PART_EHEADS'].strip('"')
TI_ATTR_FDISK_PART_ESECTS =  ti_defines['TI_ATTR_FDISK_PART_ESECTS'].strip('"')
TI_ATTR_FDISK_PART_ECYLS =  ti_defines['TI_ATTR_FDISK_PART_ECYLS'].strip('"')
TI_ATTR_FDISK_PART_RSECTS =  ti_defines['TI_ATTR_FDISK_PART_RSECTS'].strip('"')
TI_ATTR_FDISK_PART_NUMSECTS =  ti_defines['TI_ATTR_FDISK_PART_NUMSECTS'].strip('"')
TI_ATTR_FDISK_PART_PRESERVE =  ti_defines['TI_ATTR_FDISK_PART_PRESERVE'].strip('"')
TI_ATTR_SLICE_DEFAULT_LAYOUT =  ti_defines['TI_ATTR_SLICE_DEFAULT_LAYOUT'].strip('"')
TI_ATTR_SLICE_DISK_NAME =  ti_defines['TI_ATTR_SLICE_DISK_NAME'].strip('"')
TI_ATTR_SLICE_NUM =  ti_defines['TI_ATTR_SLICE_NUM'].strip('"')
TI_ATTR_SLICE_PARTS =  ti_defines['TI_ATTR_SLICE_PARTS'].strip('"')
TI_ATTR_SLICE_TAGS =  ti_defines['TI_ATTR_SLICE_TAGS'].strip('"')
TI_ATTR_SLICE_FLAGS =  ti_defines['TI_ATTR_SLICE_FLAGS'].strip('"')
TI_ATTR_SLICE_1STSECS =  ti_defines['TI_ATTR_SLICE_1STSECS'].strip('"')
TI_ATTR_SLICE_SIZES =  ti_defines['TI_ATTR_SLICE_SIZES'].strip('"')
TI_ATTR_ZFS_RPOOL_NAME =  ti_defines['TI_ATTR_ZFS_RPOOL_NAME'].strip('"')
TI_ATTR_ZFS_RPOOL_DEVICE =  ti_defines['TI_ATTR_ZFS_RPOOL_DEVICE'].strip('"')
TI_ATTR_ZFS_RPOOL_PRESERVE =  ti_defines['TI_ATTR_ZFS_RPOOL_PRESERVE'].strip('"')
TI_ATTR_ZFS_FS_NUM =  ti_defines['TI_ATTR_ZFS_FS_NUM'].strip('"')
TI_ATTR_ZFS_FS_POOL_NAME =  ti_defines['TI_ATTR_ZFS_FS_POOL_NAME'].strip('"')
TI_ATTR_ZFS_FS_NAMES =  ti_defines['TI_ATTR_ZFS_FS_NAMES'].strip('"')
TI_ATTR_ZFS_PROPERTIES =  ti_defines['TI_ATTR_ZFS_PROPERTIES'].strip('"')
TI_ATTR_ZFS_PROP_NAMES =  ti_defines['TI_ATTR_ZFS_PROP_NAMES'].strip('"')
TI_ATTR_ZFS_PROP_VALUES =  ti_defines['TI_ATTR_ZFS_PROP_VALUES'].strip('"')
TI_ATTR_ZFS_VOL_NUM =  ti_defines['TI_ATTR_ZFS_VOL_NUM'].strip('"')
TI_ATTR_ZFS_VOL_NAMES =  ti_defines['TI_ATTR_ZFS_VOL_NAMES'].strip('"')
TI_ATTR_ZFS_VOL_MB_SIZES =  ti_defines['TI_ATTR_ZFS_VOL_MB_SIZES'].strip('"')
TI_ATTR_BE_RPOOL_NAME =  ti_defines['TI_ATTR_BE_RPOOL_NAME'].strip('"')
TI_ATTR_BE_NAME =  ti_defines['TI_ATTR_BE_NAME'].strip('"')
TI_ATTR_BE_FS_NUM =  ti_defines['TI_ATTR_BE_FS_NUM'].strip('"')
TI_ATTR_BE_FS_NAMES =  ti_defines['TI_ATTR_BE_FS_NAMES'].strip('"')
TI_ATTR_BE_SHARED_FS_NUM =  ti_defines['TI_ATTR_BE_SHARED_FS_NUM'].strip('"')
TI_ATTR_BE_SHARED_FS_NAMES =  ti_defines['TI_ATTR_BE_SHARED_FS_NAMES'].strip('"')
TI_ATTR_BE_MOUNTPOINT =  ti_defines['TI_ATTR_BE_MOUNTPOINT'].strip('"')
TI_ATTR_DC_RAMDISK_FS_TYPE =  ti_defines['TI_ATTR_DC_RAMDISK_FS_TYPE'].strip('"')
TI_ATTR_DC_RAMDISK_SIZE =  ti_defines['TI_ATTR_DC_RAMDISK_SIZE'].strip('"')
TI_ATTR_DC_RAMDISK_BOOTARCH_NAME =  ti_defines['TI_ATTR_DC_RAMDISK_BOOTARCH_NAME'].strip('"')
TI_ATTR_DC_RAMDISK_DEST =  ti_defines['TI_ATTR_DC_RAMDISK_DEST'].strip('"')
TI_ATTR_DC_UFS_DEST =  ti_defines['TI_ATTR_DC_UFS_DEST'].strip('"')

tmp = ti_defines['TI_DC_RAMDISK_FS_TYPE_UFS']
TI_DC_RAMDISK_FS_TYPE_UFS = int(tmp.replace('((uint16_t)', '').replace(')', ''))
