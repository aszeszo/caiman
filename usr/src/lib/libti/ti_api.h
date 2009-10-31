/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */
/*
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _TD_API_H
#define	_TD_API_H

/*
 * This header file is for users of the Target Instantiation library
 */

#include <libnvpair.h>
#include <sys/types.h>
#include <libbe.h>

#ifdef __cplusplus
extern "C" {
#endif

/* type definitions */

typedef uint64_t ti_handle_t;

typedef enum {
	TI_E_SUCCESS = 0,		/* command succeeded */
	TI_E_INVALID_FDISK_ATTR,	/* fdisk set of attributes invalid */
	TI_E_FDISK_FAILED,		/* fdisk part of TI failed */
	TI_E_UNMOUNT_FAILED,		/* freeing target media failed */
	TI_E_INVALID_VTOC_ATTR,		/* VTOC set of attributes invalid */
	TI_E_DISK_LABEL_FAILED,		/* disk label failed */
	TI_E_VTOC_FAILED,		/* VTOC part of TI failed */
	TI_E_INVALID_ZFS_ATTR,		/* ZFS set of attributes invalid */
	TI_E_ZFS_FAILED,		/* ZFS part of TI failed */
	TI_E_INVALID_BE_ATTR,		/* BE set of attributes invalid */
	TI_E_BE_FAILED,			/* BE part of TI failed */
	TI_E_REP_FAILED,		/* progress report failed */
	TI_E_TARGET_UNKNOWN,		/* unknown target type */
	TI_E_TARGET_NOT_SUPPORTED,	/* unsupported target type */
	TI_E_INVALID_RAMDISK_ATTR,	/* */
	TI_E_RAMDISK_MKFILE_FAILED,	/* */
	TI_E_RAMDISK_LOFIADM_FAILED,	/* */
	TI_E_NEWFS_FAILED,		/* */
	TI_E_MKDIR_FAILED,		/* */
	TI_E_MOUNT_FAILED,		/* */
	TI_E_RMDIR_FAILED,		/* */
	TI_E_PY_INVALID_ARG		/* invalid arg in Python interface */
} ti_errno_t;

/* type of callback function reporting progress */
typedef ti_errno_t (*ti_cbf_t)(nvlist_t *);

/* milestones for progress report */

typedef enum {
	TI_MILESTONE_FDISK = 1,		/* fdisk structures created */
	TI_MILESTONE_VTOC,		/* VTOC structures created */
	TI_MILESTONE_ZFS_RPOOL,		/* ZFS root pool created */
	TI_MILESTONE_ZFS_FS,		/* ZFS file systems created */
	TI_MILESTONE_LAST		/* everything is done */
} ti_milestone_t;

/*
 * ZFS user property indicating that pool was successfully
 * installed. It is used for determining, if existing ZFS
 * pool was fully or partially populated by the installer
 */
#define	TI_RPOOL_PROPERTY_STATE		"org.opensolaris.caiman:install"
#define	TI_RPOOL_BUSY			"busy"
#define	TI_RPOOL_READY			"ready"

/*
 * ZFS volume names for swap and dump
 */
#define	TI_ZFS_VOL_NAME_SWAP	"swap"
#define	TI_ZFS_VOL_NAME_DUMP	"dump"

/* string - ramdisk fs type */
#define	TI_DC_RAMDISK_FS_TYPE_UFS	((uint16_t)1)

/* type of nvlist describing the target */
#define	TI_TARGET_NVLIST_TYPE		NV_UNIQUE_NAME

/* common target nv attributes */
/* target type */
#define	TI_ATTR_TARGET_TYPE		"ti_target_type"

/* array indices for target methods */
#define	TI_TARGET_TYPE_FDISK		0
#define	TI_TARGET_TYPE_DISK_LABEL	1
#define	TI_TARGET_TYPE_VTOC		2
#define	TI_TARGET_TYPE_ZFS_RPOOL	3
#define	TI_TARGET_TYPE_ZFS_FS		4
#define	TI_TARGET_TYPE_ZFS_VOLUME	5
#define	TI_TARGET_TYPE_BE		6
#define	TI_TARGET_TYPE_DC_UFS		7
#define	TI_TARGET_TYPE_DC_RAMDISK	8

/* progress report */

/* total num of milestones */
#define	TI_PROGRESS_MS_NUM		"ti_progress_ms_num"

/* current milestone in progress */
#define	TI_PROGRESS_MS_CURR		"ti_progress_ms_curr"

/* percentage current milestone takes from total */
#define	TI_PROGRESS_MS_PERC		"ti_progress_ms_perc"

/* percentage done of current milestone */
#define	TI_PROGRESS_MS_PERC_DONE	"ti_progress_ms_perc_done"

/* total estimated time in [ms] */
#define	TI_PROGRESS_TOTAL_TIME		"ti_progress_total_time"

/* nv attribute names for fdisk partition structure */

/* use whole disk for Solaris2 parition */
#define	TI_ATTR_FDISK_WDISK_FL		"ti_fdisk_wdisk_fl"

/* string - name of disk */
#define	TI_ATTR_FDISK_DISK_NAME		"ti_fdisk_disk_name"

/* uint16 - total number of partitions - including logical volumes */
#define	TI_ATTR_FDISK_PART_NUM		"ti_fdisk_part_num"

/* uint8 array - partition IDs */
#define	TI_ATTR_FDISK_PART_IDS		"ti_fdisk_part_ids"

/* uint8 array - partition ACTIVE flag */
#define	TI_ATTR_FDISK_PART_ACTIVE	"ti_fdisk_part_active"

/* uint64 array - start of partition - head - optional */
#define	TI_ATTR_FDISK_PART_BHEADS	"ti_fdisk_part_bheads"

/* uint64 array - start of partition - sector - optional */
#define	TI_ATTR_FDISK_PART_BSECTS	"ti_fdisk_part_bsects"

/* uint64 array - start of partition - cylinder - optional */
#define	TI_ATTR_FDISK_PART_BCYLS	"ti_fdisk_part_bcyls"

/* uint64 array - end of partition - head - optional */
#define	TI_ATTR_FDISK_PART_EHEADS	"ti_fdisk_part_eheads"

/* uint64 array - end of partition - sector - optional */
#define	TI_ATTR_FDISK_PART_ESECTS	"ti_fdisk_part_esects"

/* uint64 array - end of partition - cylinder - optional */
#define	TI_ATTR_FDISK_PART_ECYLS	"ti_fdisk_part_ecyls"

/* uint64 array - start of partition - offset from beginning of the disk */
#define	TI_ATTR_FDISK_PART_RSECTS	"ti_fdisk_part_rsects"

/* uint64 array - size of partition - number of sectors */
#define	TI_ATTR_FDISK_PART_NUMSECTS	"ti_fdisk_part_numsects"

/* boolean_t array - preserve partition geometry - optional */
#define	TI_ATTR_FDISK_PART_PRESERVE	"ti_fdisk_part_preserve"

/* nv attribute names for VTOC structure */

/* boolean - create default VTOC - s0 for main zpool */
#define	TI_ATTR_SLICE_DEFAULT_LAYOUT	"ti_slice_default_layout"

/* boolean - create swap slice - s1 for swap */
#define	TI_ATTR_CREATE_SWAP_SLICE	"ti_slice_swap"

/* string - disk name */
#define	TI_ATTR_SLICE_DISK_NAME		"ti_slice_disk_name"

/* uint16 - # of slices to be created */
#define	TI_ATTR_SLICE_NUM		"ti_slice_num"

/* uint16 array of VTOC slice numbers */
#define	TI_ATTR_SLICE_PARTS		"ti_slice_parts"

/* uint16 array of VTOC slice tags */
#define	TI_ATTR_SLICE_TAGS		"ti_slice_tags"

/* uint16 array of VTOC slice flags */
#define	TI_ATTR_SLICE_FLAGS		"ti_slice_flags"

/* uint64 array of 1st slice sectors */
#define	TI_ATTR_SLICE_1STSECS		"ti_slice_1stsecs"

/* uint64 array of slice sizes in sectors */
#define	TI_ATTR_SLICE_SIZES		"ti_slice_sizes"

/* nv attribute names for ZFS */

/* string - name of root pool to be created */
#define	TI_ATTR_ZFS_RPOOL_NAME		"ti_zfs_rpool_name"

/* string - root pool device */
#define	TI_ATTR_ZFS_RPOOL_DEVICE	"ti_zfs_rpool_device"

/* boolean_t - preserve root pool, if it already exists  */
#define	TI_ATTR_ZFS_RPOOL_PRESERVE	"ti_zfs_rpool_preserve"

/* uint16 - # of ZFS file systems */
#define	TI_ATTR_ZFS_FS_NUM		"ti_zfs_fs_num"

/* string - ZFS file system pool name */
#define	TI_ATTR_ZFS_FS_POOL_NAME	"ti_zfs_fs_pool_name"

/* string array - ZFS file system names */
#define	TI_ATTR_ZFS_FS_NAMES		"ti_zfs_fs_names"

/* string - ZFS volume pool name */
#define	TI_ATTR_ZFS_VOL_POOL_NAME	"ti_zfs_vol_pool_name"

/* uint16 - # of ZFS volumes */
#define	TI_ATTR_ZFS_VOL_NUM		"ti_zfs_vol_num"

/* string array - ZFS volume names */
#define	TI_ATTR_ZFS_VOL_NAMES		"ti_zfs_vol_names"

/* uint32 array - ZFS volume sizes in MB */
#define	TI_ATTR_ZFS_VOL_MB_SIZES	"ti_zfs_vol_mb_sizes"

/* uint16 array - ZFS volume types */
#define	TI_ATTR_ZFS_VOL_TYPES		"ti_zfs_vol_types"

/* ZFS volume types */
/* generic ZFS volume */
#define	TI_ZFS_VOL_TYPE_GENERIC		0
/* ZFS volume is dedicated to swap */
#define	TI_ZFS_VOL_TYPE_SWAP		1
/* ZFS volume is dedicated to dump */
#define	TI_ZFS_VOL_TYPE_DUMP		2

/* nvlist - ZFS properties */
#define	TI_ATTR_ZFS_PROPERTIES		"ti_zfs_properties"

/* string array - ZFS property names */
#define	TI_ATTR_ZFS_PROP_NAMES		"ti_zfs_prop_names"

/* string array - ZFS property values */
#define	TI_ATTR_ZFS_PROP_VALUES		"ti_zfs_prop_values"

/* nv attribute names for BE */

/* string - name of ZFS root pool */
#define	TI_ATTR_BE_RPOOL_NAME		"ti_be_rpool_name"

/* string - BE name */
#define	TI_ATTR_BE_NAME			"ti_be_name"

/* uint16 - # of non-shared file systems */
#define	TI_ATTR_BE_FS_NUM		"ti_be_fs_num"

/* string array - BE non-shared file system names */
#define	TI_ATTR_BE_FS_NAMES		"ti_be_fs_names"

/* uint16 - # of shared file systems */
#define	TI_ATTR_BE_SHARED_FS_NUM    	"ti_be_shared_fs_num"

/* string array - BE non-shared file system names */
#define	TI_ATTR_BE_SHARED_FS_NAMES  	"ti_be_shared_fs_names"

/* string - BE mountpoint */
#define	TI_ATTR_BE_MOUNTPOINT		"ti_be_mountpoint"

/* string - ramdisk fs type */
#define	TI_ATTR_DC_RAMDISK_FS_TYPE	"ti_dc_ramdisk_fs_type"

/* uint16_t - ramdisk size in K bytes */
#define	TI_ATTR_DC_RAMDISK_SIZE		"ti_dc_ramdisk_size"

/* string - ramdisk mountpoint */
#define	TI_ATTR_DC_RAMDISK_BOOTARCH_NAME	"ti_dc_ramdisk_bootarch_name"

/* string - ramdisk fs type */
#define	TI_ATTR_DC_RAMDISK_DEST		"ti_dc_ramdisk_dest"

/* string - directory type */
#define	TI_ATTR_DC_UFS_DEST		"ti_dc_ufs_dest"

/* string - label disk name */
#define	TI_ATTR_LABEL_DISK_NAME		"ti_label_disk_name"

/* function prototypes */

/* creates target described by set of nvlist attributes */
ti_errno_t ti_create_target(nvlist_t *, ti_cbf_t);

/* releases/destroys target described by set of nvlist attributes */
ti_errno_t ti_release_target(nvlist_t *);

/* checks if target described by set of nvlist attributes exists */
boolean_t ti_target_exists(nvlist_t *);

/* Makes TI work in dry run mode */
void ti_dryrun_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* _TD_API_H */
