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

#ifndef	_TGT_MODULE_H
#define	_TGT_MODULE_H
#include "Python.h"
#include "structmember.h"
#include <libnvpair.h>

#define	TGT_UTILS "osol_install.tgt_utils"

extern void	raise_td_errcode(void);
extern void	raise_ti_errcode(int);
extern PyObject	*discover_target_data(void);
extern PyObject	*create_disk_target(PyObject *self, PyObject *args);
extern PyObject	*create_zfs_root_pool(PyObject *self, PyObject *args);
extern PyObject	*create_zfs_volume(PyObject *self, PyObject *args);
extern PyObject	*create_be_target(PyObject *self, PyObject *args);
extern PyObject	*release_zfs_root_pool(PyObject *self, PyObject *args);
extern PyObject *retrieve_tgt_utils_module();
extern PyObject *_call_print_method(PyObject *self, const char *method_name);

extern void	init_disk(PyObject *);
extern void	init_partition(PyObject *);
extern void	init_slice(PyObject *);
extern void	init_zpool(PyObject *);
extern void	init_zfsdataset(PyObject *);

extern int	TgtDisk_add_child(PyObject *, PyObject *);
extern int	TgtPartition_add_child(PyObject *, PyObject *);

extern PyTypeObject TgtGeometryType;
#define	TgtGeometry_Check(op) PyObject_TypeCheck(op, &TgtGeometryType)
#define	TgtGeometry_CheckExact(op) ((op)->ob_type == &TgtGeometryType)

extern PyTypeObject TgtDiskType;
#define	TgtDisk_Check(op) PyObject_TypeCheck(op, &TgtDiskType)
#define	TgtDisk_CheckExact(op) ((op)->ob_type == &TgtDiskType)

extern PyTypeObject TgtPartitionType;
#define	TgtPartition_Check(op) PyObject_TypeCheck(op, &TgtPartitionType)
#define	TgtPartition_CheckExact(op) ((op)->ob_type == &TgtPartitionType)

extern PyTypeObject TgtSliceType;
#define	TgtSlice_Check(op) PyObject_TypeCheck(op, &TgtSliceType)
#define	TgtSlice_CheckExact(op) ((op)->ob_type == &TgtSliceType)

extern PyTypeObject TgtZpoolType;
#define	TgtZpool_Check(op) PyObject_TypeCheck(op, &TgtZpoolType)

extern PyTypeObject TgtZFSDatasetType;
#define	TgtZFSDataset_Check(op) PyObject_TypeCheck(op, &TgtZFSDatasetType)

extern PyObject *TgtGeometryDefault;

#endif /* _TGT_MODULE_H */
