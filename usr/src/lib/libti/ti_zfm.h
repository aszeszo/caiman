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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _TI_ZFM_H
#define	_TI_ZFM_H

/*
 * Module:	ti_zfm.h
 * Group:
 * Description:	This module contains the Target Instantiation ZFS module
 *		data structures, constants, and function prototypes.
 */

#include "ti_api.h"
#include "ls_api.h"

#ifdef __cplusplus
extern "C" {
#endif

/* type definitions */

/* return codes */

typedef enum zfm_errno_t {
	ZFM_E_SUCCESS,
	ZFM_E_ZFS_POOL_ATTR_INVALID,	/* invalid ZFS pool set of attributes */
	ZFM_E_ZFS_POOL_CREATE_FAILED,	/* creating ZFS pool failed */
	ZFM_E_ZFS_POOL_RELEASE_FAILED,	/* releasing ZFS pool failed */
	ZFM_E_ZFS_FS_ATTR_INVALID,	/* invalid ZFS fs set of attributes */
	ZFM_E_ZFS_FS_CREATE_FAILED,	/* creating ZFS fs failed */
	ZFM_E_ZFS_FS_SET_ATTR_FAILED,	/* setting ZFS fs attributes failed */

	/* invalid ZFS volume set of attribtues */
	ZFM_E_ZFS_VOL_ATTR_INVALID,
	ZFM_E_ZFS_VOL_CREATE_FAILED,	/* creating ZFS volumes failed */

	/* setting ZFS volume attributes failed */
	ZFM_E_ZFS_VOL_SET_ATTR_FAILED,

	/* failed to set properties for ZFS dataset */
	ZFM_E_ZFS_SET_PROP_FAILED,
	/* failed to add ZFS volume to the swap pool */
	ZFM_E_ZFS_VOL_SET_SWAP_FAILED,
	/* failed to set ZFS volume as dump device */
	ZFM_E_ZFS_VOL_SET_DUMP_FAILED
} zfm_errno_t;

/* constants */

/* macros */

/* global variables */

/* function prototypes */

/* create ZFS pool */

zfm_errno_t zfm_create_pool(nvlist_t *attrs);

/* release ZFS pool */

zfm_errno_t zfm_release_pool(nvlist_t *attrs);

/* create ZFS filesystems */

zfm_errno_t zfm_create_fs(nvlist_t *attrs);

/* create ZFS volumes */

zfm_errno_t zfm_create_volumes(nvlist_t *attrs);

/* Makes TI ZFS module work in dry run mode */

void zfm_dryrun_mode(void);

/* checks if ZFS dataset exists */

boolean_t zfm_fs_exists(nvlist_t *attrs);

#ifdef __cplusplus
}
#endif

#endif /* _TI_ZFM_H */
