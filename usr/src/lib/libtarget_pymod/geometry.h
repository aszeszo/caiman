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

#ifndef	_GEOMETRY_H
#define	_GEOMETRY_H
#include "Python.h"
#include "structmember.h"


/*
 * The common disk unit is a "block". In order to know the size of a disk,
 * partition, or slice is, you need to know how big a block is. Often it
 * will be 512, but it doesn't have to be.
 *
 * Cylinders are important for partition boundaries.
 *
 * With a tgt.Geometry object you can calculate sizes
 */


typedef struct {
	PyObject_HEAD
	uint32_t blocksz;		/* block size in bytes */
	uint32_t cylsz;			/* Disk cylinder size in blocks */
} TgtGeometry;


#endif	/* _GEOMETRY_H */
