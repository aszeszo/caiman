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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _TD_API_H
#define	_TD_API_H

#pragma ident	"@(#)ti_api.h	1.3	07/10/23 SMI"

/*
 * This header file is for users of the Target Instantiation library
 */

#include <libnvpair.h>
#include <sys/types.h>

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
	TI_E_VTOC_FAILED,		/* VTOC part of TI failed */
	TI_E_INVALID_ZFS_ATTR,		/* ZFS set of attributes invalid */
	TI_E_ZFS_FAILED,		/* ZFS part of TI failed */
	TI_E_REP_FAILED			/* progress report failed */
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

/* type of nvlist describing the target */
#define	TI_TARGET_NVLIST_TYPE		NV_UNIQUE_NAME

/* common target nv attributes */

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

/* name of disk */
#define	TI_ATTR_FDISK_DISK_NAME		"ti_fdisk_disk_name"

/* nv attribute names for VTOC structure */

/* boolean - create default VTOC - s1 for swap, s0 occupies remaining space */
#define	TI_ATTR_SLICE_DEFAULT_LAYOUT	"ti_slice_default_layout"

/* uint16 - # of slices to be created */
#define	TI_ATTR_SLICE_NUM		"ti_slice_num"

/* uint16 array of VTOC slice numbers */
#define	TI_ATTR_SLICE_PARTS		"ti_slice_parts"

/* uint16 array of VTOC slice tags */
#define	TI_ATTR_SLICE_TAGS		"ti_slice_tags"

/* uint16 array of VTOC slice flags */
#define	TI_ATTR_SLICE_FLAGS		"ti_slice_flags"

/* uint32 array of 1st slice sectors */
#define	TI_ATTR_SLICE_1STSECS		"ti_slice_1stsecs"

/* uint32 array of slice sizes in sectors */
#define	TI_ATTR_SLICE_SIZES		"ti_slice_sizes"

/* nv attribute names for ZFS */

/* string - name of root pool to be created */
#define	TI_ATTR_ZFS_RPOOL_NAME		"ti_zfs_rpool_name"

/* string - name of BE to be created */
#define TI_ATTR_ZFS_BE_NAME		"ti_zfs_be_name"

/* string - root pool device */
#define	TI_ATTR_ZFS_RPOOL_DEVICE	"ti_zfs_rpool_device"

/* uint16 - # of ZFS file systems */
#define	TI_ATTR_ZFS_FS_NUM		"ti_zfs_fs_num"

/* uint16 - # of ZFS file systems */
#define TI_ATTR_ZFS_SHARED_FS_NUM	"ti_zfs_shared_fs_num"

/* string - ZFS pool name */
#define	TI_ATTR_ZFS_FS_POOL_NAME	"ti_zfs_fs_pool_name"

/* string array - ZFS file system names */
#define	TI_ATTR_ZFS_FS_NAMES		"ti_zfs_fs_names"

/* string array - ZFS file system names */
#define TI_ATTR_ZFS_SHARED_FS_NAMES	"ti_zfs_shared_fs_names"

/* uint16 - # of ZFS volumes */
#define	TI_ATTR_ZFS_VOL_NUM		"ti_zfs_vol_num"

/* string array - ZFS volume names */
#define	TI_ATTR_ZFS_VOL_NAMES		"ti_zfs_vol_names"

/* uint32 array - ZFS volume sizes in MB */
#define	TI_ATTR_ZFS_VOL_MB_SIZES	"ti_zfs_vol_mb_sizes"

/* function prototypes */

/* creates target described by set of nvlist attributes */
ti_errno_t ti_create_target(nvlist_t *, ti_cbf_t);

/* Makes TI work in dry run mode */
void ti_dryrun_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* _TD_API_H */
