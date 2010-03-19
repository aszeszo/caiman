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

#include "zpool.h"
#include "tgt.h"
#include "boolobject.h"


PyTypeObject TgtZpoolType; /* forward declaration */
PyTypeObject TgtZFSDatasetType; /* forward declaration */

/*
 * Function:    TgtZFSDataset_Init
 * Description: Initialize a tgt.ZFSDataset object.
 * Parameters:
 *     self:    tgt.ZFSDataset object to fill in
 *     args:    the arguments given to Python to try to init object
 *     kwds:    similar to args.
 * Returns:     None
 * Scope:       Private
 *
 */
static int
TgtZFSDataset_Init(TgtZFSDataset *self, PyObject *args, PyObject *kwds)
{
	int rc;
	char *name = NULL;
	PyObject *zfs_swap;
	PyObject *zfs_dump;
	char *mountpoint = NULL;
	int swap_size, dump_size;
	char *be_name = NULL;

	static char *kwlist[] = {
		"name", "mountpoint", "be_name", "zfs_swap", "swap_size",
		"zfs_dump", "dump_size", NULL
	};

	/*
	 * Set default values for unrequired arguments.
	 */
	name = mountpoint = be_name = NULL;
	zfs_swap = zfs_dump = Py_False;
	swap_size = 0;
	dump_size = 0;

	rc = PyArg_ParseTupleAndKeywords(args, kwds, "|sssOiOi", kwlist,
	    &name, &mountpoint, &be_name, &zfs_swap, &swap_size, &zfs_dump,
	    &dump_size);

	if (!rc) {
		PyErr_SetString(PyExc_TypeError,
		    "tgt.ZFSDataset() Error parsing the arguments");
		return (-1);
	}

	/*
	 * If name and mountpoint are specified, then zfs_swap or zfs_dump
	 * shouldn't be.
	 */
	if (name != NULL && mountpoint != NULL) {
		if (zfs_swap == Py_True || zfs_dump == Py_True) {
			PyErr_SetString(PyExc_TypeError,
			    "tgt.ZFSDataset() \"name\" and \"mountpoint\" are "
			    "mutually exclusive with zfs_swap and zfs_dump");
			return (-1);
		}
	}

	/*
	 * If zfs_swap or zfs_dump are specified, then name or mountpoint
	 * shouldn't be.
	 */
	if (zfs_swap != Py_False || zfs_dump != Py_False) {
		if (name != NULL || mountpoint != NULL) {
			PyErr_SetString(PyExc_TypeError,
			    "tgt.ZFSDataset() \"name\" and \"mountpoint\" are "
			    "mutually exclusive with zfs_swap and zfs_dump");
			return (-1);
		}
	}

	if (name != NULL) {
		self->name = strdup(name); /* can't be NULL */
		if (self->name == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

	if (mountpoint != NULL) {
		self->mountpoint = strdup(mountpoint); /* can't be NULL */
		if (self->mountpoint == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

	if (be_name != NULL) {
		self->be_name = strdup(be_name); /* can't be NULL */
		if (self->be_name == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

	self->zfs_swap = (zfs_swap == Py_True) ? 1 : 0;
	self->zfs_dump = (zfs_dump == Py_True) ? 1 : 0;
	self->swap_size = swap_size;
	self->dump_size = dump_size;

	return (0);
}

/*
 * Function:    TgtZpool_Init
 * Description: Initialize a tgt.Zpool object.
 * Parameters:
 *     self:    tgt.Zpool object to fill in
 *     args:    the arguments given to Python to try to init object
 *     kwds:    similar to args.
 * Returns:     None
 * Scope:       Private
 *
 */
static int
TgtZpool_Init(TgtZpool *self, PyObject *args, PyObject *kwds)
{
	int rc;
	char *name = NULL;
	char *device = NULL;

	static char *kwlist[] = {
		"name", "device", NULL
	};

	/*
	 * Set default values for unrequired arguments.
	 */
	self->name = self->device = NULL;

	rc = PyArg_ParseTupleAndKeywords(args, kwds, "ss", kwlist,
		&name, &device);

	if (!rc)
		return (-1);

	self->name = strdup(name); /* can't be NULL */
	if (self->name == NULL) {
		PyErr_NoMemory();
		return (-1);
	}

	self->device = strdup(device); /* can't be NULL */
	if (self->device == NULL) {
		PyErr_NoMemory();
		return (-1);
	}

	return (0);
}

/*
 * Function:    TgtZpool_New
 * Description: allocate and assign sensible initial values to a tgt.Zpool.
 * Parameters:
 *     type:    type object, do *NOT* assume it is TgtZpoolType!
 *     args:    ignored, exists to match function prototype.
 *     kwds:    ignored, exists to match function prototype.
 * Returns:     None
 * Scope:       Private
 *
 * NOTE: Unless you have not followed the MEMBER macros at the top there
 *       is no reason to alter this function.
 */
/* ARGSUSED */
static PyObject *
TgtZpool_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtZpool *self = NULL;

	self = (TgtZpool *)type->tp_alloc(type, 0);
	if (self == NULL)
		return (NULL); /* sets memory error */

	if ((self->datasets = PyTuple_New(0)) == NULL) {
		return (NULL);
	}
	self->name = self->device = NULL;

	return ((PyObject *)self);
}

/*
 * Function:    TgtZFSDataset_New
 * Description: allocate and assign sensible initial values to a tgt.ZFSDataset.
 * Parameters:
 *     type:    type object, do *NOT* assume it is TgtDiskType!
 *     args:    ignored, exists to match function prototype.
 *     kwds:    ignored, exists to match function prototype.
 * Returns:     None
 * Scope:       Private
 *
 */
/* ARGSUSED */
static PyObject *
TgtZFSDataset_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtZFSDataset *self = NULL;

	self = (TgtZFSDataset *)type->tp_alloc(type, 0);
	if (self == NULL)
		return (NULL); /* sets memory error */

	self->name = self->mountpoint = self->be_name = NULL;
	self->zfs_swap = 0;
	self->zfs_dump = 0;
	self->swap_size = 0;
	self->dump_size = 0;

	return ((PyObject *)self);
}


/*
 * Function:	TgtZpool_Deallocate
 * Description:	Free up a TgtZpool
 * Parameters:
 * 	self:	TgtZpool to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 */
static void
TgtZpool_Deallocate(TgtZpool *self)
{
#define	FREE_STR(cname) \
	if (self->cname != NULL) \
		free(self->cname)
	FREE_STR(name);
	FREE_STR(device);
#undef	FREE_STR

	self->ob_type->tp_free((PyObject*)self);
}

/*
 * Function:	TgtZFSDataset_Deallocate
 * Description:	Free up a TgtZFSDataset
 * Parameters:
 * 	self:	TgtZFSDataset to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 */
static void
TgtZFSDataset_Deallocate(TgtZFSDataset *self)
{
#define	FREE_STR(cname) \
	if (self->cname != NULL) \
		free(self->cname)
	FREE_STR(name);
	FREE_STR(mountpoint);
	FREE_STR(be_name);
#undef	FREE_STR
}

PyDoc_STRVAR(TgtZpoolTypeDoc,
"tgt.Zpool(name, device) -> tgt.Zpool object\n\
\n\
A Zpool object represents a zfs pool in the system.\n\
\n");

PyDoc_STRVAR(TgtZFSDatasetTypeDoc,
"tgt.ZFSDataset(name, mountpoint, be_name, zfs_swap, swap_size, zfs_dump, \
dump_size) -> tgt.ZFSDataset object\n\
\n\
A ZFSDataset object represents a zfs dataset in the system.\n\
\n");

static PyMemberDef TgtZpoolMembers[] = {
	{
		.name = "name",
		.type = T_STRING,
		.offset = offsetof(TgtZpool, name),
		.doc = "zpool name"
	}, {
		.name = "device",
		.type = T_STRING,
		.offset = offsetof(TgtZpool, device),
		.doc = "device for zpool"
	}, {
		.name = "datasets",
		.type = T_OBJECT,
		.offset = offsetof(TgtZpool, datasets),
		.doc = "datasets in the zpool"
	}, { NULL } /* Sentinel */
};

static PyMemberDef TgtZFSDatasetMembers[] = {
	{
		.name = "name",
		.type = T_STRING,
		.offset = offsetof(TgtZFSDataset, name),
		.doc = "zfs dataset name"
	}, {
		.name = "mountpoint",
		.type = T_STRING,
		.offset = offsetof(TgtZFSDataset, mountpoint),
		.doc = "zfs dataset mountpoint"
	}, {
		.name = "be_name",
		.type = T_STRING,
		.offset = offsetof(TgtZFSDataset, be_name),
		.doc = "boot environment name"
	}, {
		.name = "zfs_swap",
		.type = T_OBJECT,
		.offset = offsetof(TgtZFSDataset, zfs_swap),
		.doc = "Boolean to indicate whether to create a swap device"
	}, {
		.name = "swap_size",
		.type = T_OBJECT,
		.offset = offsetof(TgtZFSDataset, swap_size),
		.doc = "size of zfs dataset to be used for swap"
	}, {
		.name = "zfs_dump",
		.type = T_OBJECT,
		.offset = offsetof(TgtZFSDataset, zfs_dump),
		.doc = "Boolean to indicate whether to create a dump device"
	}, {
		.name = "dump_size",
		.type = T_OBJECT,
		.offset = offsetof(TgtZFSDataset, dump_size),
		.doc = "size of zfs dataset to be used for dump"
	}, { NULL } /* Sentinel */
};

PyTypeObject TgtZpoolType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.Zpool",
	.tp_basicsize = sizeof (TgtZpool),
	.tp_dealloc = (destructor)TgtZpool_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtZpoolTypeDoc,
	.tp_members = TgtZpoolMembers,
	.tp_init = (initproc)TgtZpool_Init,
	.tp_new = TgtZpool_New
};

PyTypeObject TgtZFSDatasetType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.ZFSDataset",
	.tp_basicsize = sizeof (TgtZFSDataset),
	.tp_dealloc = (destructor)TgtZFSDataset_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtZFSDatasetTypeDoc,
	.tp_members = TgtZFSDatasetMembers,
	.tp_init = (initproc)TgtZFSDataset_Init,
	.tp_new = TgtZFSDataset_New
};
