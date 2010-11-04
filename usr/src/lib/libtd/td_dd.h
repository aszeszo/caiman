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
 * Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#ifndef _TD_DD_H
#define	_TD_DD_H

/*
 * Module:	td_dd.h
 * Group:
 * Description:	This module contains the Target Discovery disk module
 *		data structures, constants, and function prototypes.
 */

#include <ctype.h>
#include <sys/types.h>
#include <sys/nvpair.h>

#include "td_api.h"
#include "ls_api.h"

#ifdef __cplusplus
extern "C" {
#endif

#define	DDM_DEBUG	ddm_debug_print

/* type definitions */
/* typedef dm_descriptor_t	ddm_handle_t; */
typedef uint64_t		ddm_handle_t;

#define	DDM_DBGLVL_ERROR	LS_DBGLVL_ERR
#define	DDM_DBGLVL_WARNING	LS_DBGLVL_WARN
#define	DDM_DBGLVL_NOTICE	LS_DBGLVL_INFO
#define	DDM_DBGLVL_INFO		LS_DBGLVL_INFO

/* return codes */

typedef enum ddm_err_t {
	DDM_SUCCESS,
	DDM_FAILURE
} ddm_err_t;

/* constants */

/* discoverall targets for given type */
#define	DDM_DISCOVER_ALL	(ddm_handle_t)0

/* attributes for newly created nv list */
#define	DDM_NVATTRS (NV_UNIQUE_NAME | NV_UNIQUE_NAME_TYPE)

/* macros */

#define	ddm_must_be(s, c)  if (*s++ != c) return (0)
#define	ddm_skip_digits(s)	if (!isdigit(*(s))) return (0); \
			while (isdigit(*(s))) (s)++;

#define	ddm_is_pathname(x)	((x) != NULL && *(x) == '/')


/* function prototypes */
extern ddm_handle_t	*ddm_get_disks(int *ndisks);
extern nvlist_t		*ddm_get_disk_attributes(ddm_handle_t d);
extern ddm_handle_t	*ddm_get_partitions(ddm_handle_t d, int *nparts);
extern nvlist_t		*ddm_get_partition_attributes(ddm_handle_t p);
extern ddm_handle_t	*ddm_get_slices(ddm_handle_t h, int *nslices);
extern nvlist_t		*ddm_get_slice_attributes(ddm_handle_t s);
extern void		ddm_free_handle_list(ddm_handle_t *h);
extern void		ddm_free_attr_list(nvlist_t *attrs);
extern int		ddm_get_slice_inuse_stats(char *, nvlist_t *);

extern ddm_err_t
    ddm_slice_inuse_by_svm(char *slice, nvlist_t *attr, int *errp);
extern int
    ddm_start_svm_and_get_root_comps(char *slice, char *mntpnt, nvlist_t *attr);
extern int
    ddm_get_svm_comps_from_md_name(char *md_name, char *mntpnt, nvlist_t *attr);
extern int ddm_stop_svm(void);

extern int ddm_is_slice_name(char *str);

/* PRINTFLIKE2 */
extern void ddm_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...);

#ifdef __cplusplus
}
#endif

#endif /* _TD_DD_H */
