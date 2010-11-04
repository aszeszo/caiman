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
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 */

#ifndef _TD_ZPOOL_H
#define	_TD_ZPOOL_H

/*
 * Module:	td_zpool.h
 * Group:
 * Description:	This module contains the Target Discovery ZFS Pool
 *		module data structures, constants, and function
 *              prototypes.
 */

#include <ctype.h>
#include <libzfs.h>
#include <math.h>
#include <sys/types.h>
#include <sys/nvpair.h>

#include "td_api.h"
#include "td_dd.h"
#include "ls_api.h"

#ifdef __cplusplus
extern "C" {
#endif


/* type definition / macros */
#define	MB_IN_GB	1024
#define	BYTES_TO_MB(size)	((size) / (MB_IN_GB * MB_IN_GB))
#define	ONE_DECIMAL(val)	((round((val) * 10)) / 10.0)
#define	MB_TO_GB(size_mb)	ONE_DECIMAL((size_mb) / MB_IN_GB)

/* zpool targets */
typedef struct td_zpool_target {
	char *name;
	char *health;
	uint64_t read_errors;
	uint64_t write_errors;
	uint64_t checksum_errors;
	uint32_t num_targets;
	struct td_zpool_target **targets;
} td_zpool_target_t;

/*
 * Structure for zpool attributes.
 * Used for zpool_iter callback data.
 */
typedef struct td_zpool_attributes {
	char *name;
	char *health;
	zpool_status_t status;
	uint64_t guid;
	uint64_t size; 	/* Size in Bytes */
	uint64_t capacity;
	uint32_t version;
	boolean_t import;
	char *bootfs;
	uint32_t num_targets;
	td_zpool_target_t **targets;
	uint32_t num_logs;
	td_zpool_target_t **logs;
	uint32_t num_spares;
	td_zpool_target_t **spares;
	uint32_t num_l2cache;
	td_zpool_target_t **l2cache;
} td_zpool_attributes_t;

/* Linked list of zpool attributes */
typedef struct td_zpool_info {
	td_zpool_attributes_t attributes;
	struct td_zpool_info *next;
} td_zpool_info_t;

/* function prototypes */
extern ddm_handle_t	*ddm_get_zpools(int *nzpools);
extern void ddm_free_zpool_list(ddm_handle_t *dh);
extern nvlist_t *ddm_get_zpool_attributes(ddm_handle_t zpool);

#ifdef __cplusplus
}
#endif

#endif /* _TD_ZPOOL_H */
