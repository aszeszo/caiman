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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef	_ZPOOL_H
#define	_ZPOOL_H
#include "Python.h"
#include "structmember.h"

/* We just need some constants, but it fails unless _FILE_OFFSET_BITS=32 */
#undef	_FILE_OFFSET_BITS
#define	_FILE_OFFSET_BITS	32

typedef struct {
	PyObject_HEAD
	char	*name;			/* zfs dataset name */
	char	*mountpoint;		/* zfs dataset mountpoint */
	char	*be_name;		/* be name */
	uint8_t	zfs_swap;		/* create a swap device */
	uint32_t swap_size;		/* size of swap */
	uint8_t zfs_dump;		/* create a dump device */
	uint32_t dump_size;		/* size of dump */

} TgtZFSDataset;

typedef struct {
	PyObject_HEAD
	char *name;			/* zpool name (required) */
	char *device;			/* device (required) */
	PyObject *datasets;		/* zfs datasets */
} TgtZpool;

#endif	/* _ZPOOL_H */
