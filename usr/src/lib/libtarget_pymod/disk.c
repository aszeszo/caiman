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

#include "geometry.h"
#include "disk.h"
#include "tgt.h"
#include "boolobject.h"
#include "td_api.h"


disk_const DiskConst;

PyTypeObject TgtDiskType; /* forward declaration */

/*
 * Function:	init_disk
 * Description:	fill in the class data for tgt.Disk.
 *              This is stored in DiskConst and then we make it available
 *              as data to the class.
 * Parameters:
 *     unknown: the shared string "unknown".
 * Returns:	None
 * Scope:	Private
 *
 * NOTE: You must not call this until after you have called
 *       PyType_Ready(&TgtDiskType), as this adds to the Type's dictionary.
 */
void
init_disk(PyObject *unknown)
{
#define	CONSTANT(v, cname, pyname, value) \
	DiskConst.cname = PyString_FromString(value);
	CONTROLLER_CONSTANTS
#undef	CONSTANT
	DiskConst.unknown = unknown; /* add the shared constant. */

	/*
	 * Keep in mind dictionaries don't steal a reference to key or value.
	 * Which is perfect, we have a pointer to them in SliceConst but now
	 * when the type object is cleaned up their ref count will go to 0
	 * and they will disappear.
	 */
#define	CONSTANT(v, cname, pyname, value) \
	PyDict_SetItemString(TgtDiskType.tp_dict, pyname, DiskConst.cname);
	CONTROLLER_CONSTANTS
#undef	CONSTANT
	PyDict_SetItemString(TgtDiskType.tp_dict, "UNKNOWN", unknown);
}

/*
 * Function:    TgtDisk_Init
 * Description: Initialize a tgt.Disk object.
 * Parameters:
 *     self:    tgt.Disk object to fill in
 *     args:    the arguments given to Python to try to init object
 *     kwds:    similar to args.
 * Returns:     None
 * Scope:       Private
 *
 * NOTE: when tgt.discover_target_data() is called this is not used.
 *       This is for creating a layout without using libtd.so.
 *       Useful for testing and possibly for target instantiation?
 */
static int
TgtDisk_Init(TgtDisk *self, PyObject *args, PyObject *kwds)
{
	int rc;
	char *name = NULL;
	char *vendor = NULL;
	char *serialno = NULL;
	char *controller = NULL;
	PyObject *tmp = NULL;
	PyObject *geometry = NULL;
	PyObject *blocks = NULL; /* Python2.4 missing uint64_t fmt spec */
	PyObject *vtoc = NULL;
	PyObject *gpt = NULL;
	PyObject *fdisk = NULL;
	PyObject *boot = NULL;
	PyObject *removable = NULL;
	PyObject *constantref = NULL;
	PyObject *use_whole = NULL;

	/* Remember to keep TgtDiskTypeDoc current with this list */
	static char *kwlist[] = {
		"geometry", "name", "blocks", "controller", "vtoc", "gpt",
		"fdisk", "boot", "removable", "vendor", "serialno", "use_whole",
		NULL
	};

	/* set default vaules for unrequired args */
	boot = removable = Py_False;
	self->vtoc = self->gpt = self->fdisk = 0; /* not set during init */

	rc = PyArg_ParseTupleAndKeywords(args, kwds, "O!sO|sO!O!O!O!O!zzO!",
	    kwlist, &TgtGeometryType, &geometry, &name, &blocks,
	    &controller, &PyBool_Type, &vtoc, &PyBool_Type, &gpt,
	    &PyBool_Type, &fdisk, &PyBool_Type, &boot, &PyBool_Type,
	    &removable, &vendor, &serialno, &PyBool_Type, &use_whole);

	if (!rc)
		return (-1);

	/*
	 * Have to take care that if we return -1 we have correct ref counts.
	 * On failure, self will be decrefed and  TgtDisk_Deallocate() will
	 * (probably, unless ref counts off) be called.
	 */
	tmp = self->geometry;
	Py_INCREF(geometry);
	self->geometry = geometry;
	Py_XDECREF(tmp);

	/* Python 2.4 has no scan code for a potentially 64-bit value */
	if (PyLong_Check(blocks)) {
		self->blocks = PyLong_AsUnsignedLongLong(blocks);
	} else {
		if (PyInt_Check(blocks)) {
			self->blocks = (uint64_t)PyInt_AsLong(blocks);
		} else {
			PyErr_SetString(PyExc_TypeError,
				"tgt.Disk() \"blocks\" an integer is required");
			return (-1);
		}
	}

	/*
	 * The controller must be a string we recognize, but not necessarily
	 * the tgt.Disk class constant.
	 */
	constantref = DiskConst.unknown; /* default if given NULL/None */
	while (1) {
		if (controller == NULL)
			break;

#define		CONSTANT(v, cname, pyname, value) \
		if (strcmp(controller, value) == 0) { \
			constantref = DiskConst.cname; \
			break; \
		}
		CONTROLLER_CONSTANTS
#undef		CONSTANT
		if (strcmp(controller,
		    PyString_AsString(DiskConst.unknown)) == 0) {
			constantref = DiskConst.unknown;
			break;
		}

		/* any unknown value is not acceptable */
		PyErr_SetString(PyExc_ValueError,
		    "tgt.Disk() \"controller\" not a CONTROLLER_CONSTANT");
		return (-1);
	}
	tmp = self->controller;
	Py_INCREF(constantref);
	self->controller = constantref;
	Py_XDECREF(tmp);


	self->name = strdup(name); /* can't be NULL */
	if (self->name == NULL) {
		PyErr_NoMemory();
		return (-1);
	}
	self->vendor = self->serialno = NULL;
	if (vendor) {
		self->vendor = strdup(vendor);
		if (self->vendor == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}
	if (serialno) {
		self->serialno = strdup(serialno);
		if (self->serialno == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

#define	SET_BOOL(nm) self->nm = (nm == Py_True) ? 1 : 0
	SET_BOOL(vtoc);
	SET_BOOL(gpt);
	SET_BOOL(fdisk);
	SET_BOOL(boot);
	SET_BOOL(removable);
	SET_BOOL(use_whole);
#undef	SET_BOOL

	return (0);
}

/*
 * Function:    TgtDisk_New
 * Description: allocate and assign sensible initial values to a tgt.Disk.
 * Parameters:
 *     type:    type object, do *NOT* assume it is TgtDiskType!
 *     args:    ignored, exists to match function prototype.
 *     kwds:    ignored, exists to match function prototype.
 * Returns:     None
 * Scope:       Private
 */
static PyObject *
TgtDisk_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtDisk *self = NULL;

	self = (TgtDisk *)type->tp_alloc(type, 0);
	if (self == NULL)
		return (NULL); /* sets memory error */

	/* The only thing that can fail is PyTyple_New so do that first */
	if ((self->children = PyTuple_New(0)) == NULL) {
		return (NULL);
	}

	/* Set everything else to "sensible defaults" */
	self->geometry = TgtGeometryDefault;
	Py_INCREF(TgtGeometryDefault);
	self->controller = DiskConst.unknown;
	Py_INCREF(self->controller);

	self->name = self->vendor = self->serialno = NULL;
	self->blocks = 0;
	self->vtoc = self->gpt = self->fdisk = 0;
	self->boot = self->removable = self->use_whole = 0;

	return ((PyObject *)self);
}


/*
 * Function:	TgtDisk_Deallocate
 * Description:	Free up a TgtDisk
 * Parameters:
 * 	self:	TgtDisk to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 */
static void
TgtDisk_Deallocate(TgtDisk *self)
{
	Py_XDECREF(self->geometry);
	Py_XDECREF(self->children);
	Py_XDECREF(self->controller);
#define	FREE_STR(cname)			\
	if (self->cname != NULL) {	\
		free(self->cname);	\
		self->cname = NULL;	\
	}

	FREE_STR(name)
	FREE_STR(vendor)
	FREE_STR(serialno)
#undef	FREE_STR

	self->ob_type->tp_free((PyObject*)self);
}

static int
TgtDisk_copy_common(TgtDisk *orig, TgtDisk *copy)
{
	PyObject *tmp = NULL;

	/* Geometry is always shared */
	tmp = copy->geometry;
	Py_INCREF(orig->geometry);
	copy->geometry = orig->geometry;
	Py_XDECREF(tmp);

	tmp = copy->controller;
	Py_INCREF(orig->controller);
	copy->controller = orig->controller;
	Py_XDECREF(tmp);


#define	STRCOPY(member) \
	if (orig->member != NULL) { \
		copy->member = strdup(orig->member); \
		if (copy->member == NULL) { \
			PyErr_NoMemory(); \
			return (-1); \
		} \
	}

	STRCOPY(name);
	STRCOPY(vendor);
	STRCOPY(serialno);
#undef	STRCOPY

#define	SET_MEMBER(member) copy->member = orig->member
	SET_MEMBER(blocks);
	SET_MEMBER(vtoc);
	SET_MEMBER(gpt);
	SET_MEMBER(fdisk);
	SET_MEMBER(boot);
	SET_MEMBER(removable);
	SET_MEMBER(use_whole);
#undef	SET_MEMBER

	return (0);
}
static PyObject*
TgtDisk_copy(TgtDisk* self, PyObject* args)
{
	TgtDisk *copy = NULL;
	PyObject *tmp = NULL;

	if (!PyArg_ParseTuple(args, ":__copy__"))
		return (NULL);

	copy = (TgtDisk *)TgtDiskType.tp_new(&TgtDiskType, NULL, NULL);

	if (copy == NULL)
		return (PyErr_NoMemory());

	if (TgtDisk_copy_common(self, copy) != 0) {
		Py_DECREF(copy);
		return (NULL);
	}

	/* for copy we just need references */
	tmp = copy->children;
	Py_INCREF(self->children);
	copy->children = self->children;
	Py_XDECREF(tmp);

	return ((PyObject *)copy);
}
static PyObject*
TgtDisk_deepcopy(TgtDisk* self, PyObject* args)
{
	int rc, idx;
	TgtDisk *copy = NULL;
	PyObject *memo = NULL;
	PyObject *tmp = NULL;
	PyObject *children = NULL;

	if (!PyArg_ParseTuple(args, "O!:__deepcopy__", &PyDict_Type, &memo))
		return (NULL);


	/* check and make sure we haven't copied this already. */
	rc = PyDict_Contains(memo, (PyObject *)self);
	switch (rc) {
	case -1: /* error */
		return (NULL); /* err should be set */
	case 1:
		tmp = PyDict_GetItem(memo, (PyObject *)self);
		Py_INCREF(tmp);
		return (tmp); /* don't copy again */
	}
	assert(rc == 0);


	copy = (TgtDisk *)TgtDiskType.tp_new(&TgtDiskType, NULL, NULL);
	if (copy == NULL)
		return (PyErr_NoMemory());

	if (TgtDisk_copy_common(self, copy) != 0) {
		Py_DECREF(copy);
		return (NULL);
	}

	/* need a new children tuple with new children elements of tuple */
	rc = PyTuple_Size(self->children);

	children = PyTuple_New(rc);
	for (idx = 0; idx < rc; idx++) {
		PyObject *oldc, *newc;
		oldc = PyTuple_GetItem(self->children, idx);

		assert((TgtPartition_Check(oldc) || TgtSlice_Check(oldc)));
		/*
		 * can't assume its tgt.Partition or tgt.Slice, could be a
		 * subclass.
		 */
		newc = PyObject_CallMethod(oldc, "__deepcopy__", "O", memo);
		if (newc == NULL || PyTuple_SetItem(children, idx, newc) != 0) {
			Py_XDECREF(newc);
			Py_DECREF(children);
			Py_DECREF(copy);
			return (NULL);
		}
	}

	tmp = copy->children;
	copy->children = children;
	Py_XDECREF(tmp);

	/* add this to memo dict so we won't do it again */
	rc = PyDict_SetItem(memo, (PyObject *)self, (PyObject *)copy);
	if (rc == -1) {
		Py_DECREF(copy);
		return (NULL);
	}

	return ((PyObject *)copy);
}

static PyMethodDef TgtDiskMethods[] = {
	{
		.ml_name = "__copy__",
		.ml_meth = (PyCFunction)TgtDisk_copy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, {
		.ml_name = "__deepcopy__",
		.ml_meth = (PyCFunction)TgtDisk_deepcopy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, { NULL } /* Sentinel */
};


static PyMemberDef TgtDiskMembers[] = {
	{
		.name = "name",
		.type = T_STRING,
		.offset = offsetof(TgtDisk, name),
		.flags = READONLY, /* only set at __init__() */
		.doc = "disk name"
	}, {
		.name = "controller",
		.type = T_OBJECT,
		.offset = offsetof(TgtDisk, controller),
		.flags = READONLY, /* only set at __init__() */
		.doc = "disk controller type (a CONTROLLER constant)"
	}, { NULL } /* Sentinel */
};

/* structure members that can't be made part of PyMemberDef */

static PyObject *
TgtDisk_get_geometry(TgtDisk *self, void *closure)
{
	PyObject *result = self->geometry;
	assert(result != NULL);
	Py_INCREF(result);
	return (result);
}
static int
TgtDisk_set_geometry(TgtDisk *self, PyObject *value, void *closure)
{
	PyObject *tmp = NULL;
	if (value == NULL || (TgtGeometry_Check(value) == 0)) {
		PyErr_SetString(PyExc_TypeError,
		    "\"geometry\" must be a tgt.Geometry object");
		return (-1);
	}
	tmp = self->geometry;
	self->geometry = value;
	Py_INCREF(self->geometry);
	assert(tmp != NULL);
	Py_DECREF(tmp);
	return (0);
}
PyDoc_STRVAR(TgtDisk_doc_geometry, "tgt.Geometry object describing tgt.Disk");

static PyObject *
TgtDisk_get_children(TgtDisk *self, void *closure)
{
	PyObject *result = self->children;
	assert(result != NULL);
	Py_INCREF(result);
	return (result);
}
static int
TgtDisk_set_children(TgtDisk *self, PyObject *value, void *closure)
{
	PyObject *tmp = NULL;
	if (value == NULL || (PyTuple_Check(value) == 0)) {
		PyErr_SetString(PyExc_TypeError,
		    "\"children\" must be a tuple");
		return (-1);
	}
	/* TODO: verify children are all either tgt.Slice or tgt.Partition */
	tmp = self->children;
	self->children = value;
	Py_INCREF(self->children);
	assert(tmp != NULL);
	Py_DECREF(tmp);
	return (0);
}
PyDoc_STRVAR(TgtDisk_doc_children,
	"tuple of tgt.Parttion or tgt.Slice objects");

static PyObject *
TgtDisk_get_vendor(TgtDisk *self, void *closure)
{
	if (self->vendor == NULL) {
		Py_INCREF(DiskConst.unknown);
		return (DiskConst.unknown);
	}
	return (PyString_FromString(self->vendor));
}
PyDoc_STRVAR(TgtDisk_doc_vendor, "disk manufacturer or tgt.Disk.unknown");

static PyObject *
TgtDisk_get_serialno(TgtDisk *self, void *closure)
{
	if (self->serialno == NULL) {
		Py_INCREF(DiskConst.unknown);
		return (DiskConst.unknown);
	}
	return (PyString_FromString(self->serialno));
}
PyDoc_STRVAR(TgtDisk_doc_serialno,
"manufacturer assigned serialno or tgt.Disk.unknown");

static PyObject *
TgtDisk_get_blocks(TgtDisk *self, void *closure)
{
	return (PyLong_FromLongLong(self->blocks));
}
PyDoc_STRVAR(TgtDisk_doc_blocks, "number of blocks (size in blocks)");

#define	BOOL_GETSET(member, doc) \
static PyObject * \
TgtDisk_get_##member(TgtDisk *self, void *closure) \
{ \
	PyObject *result = (self->member == 1) ? Py_True : Py_False; \
	Py_INCREF(result); \
	return (result); \
} \
static int \
TgtDisk_set_##member(TgtDisk *self, PyObject *value, void *closure) \
{ \
	if (value == NULL || (PyBool_Check(value) == 0)) { \
		PyErr_SetString(PyExc_TypeError, "\"" #member "\"" \
		    "must be a bool"); \
		return (-1); \
	} \
	self->member = (value == Py_True) ? 1 : 0; \
	return (0); \
} \
PyDoc_STRVAR(TgtDisk_doc_##member, doc)

BOOL_GETSET(vtoc, "True if tgt.Disk has VTOC");
BOOL_GETSET(gpt, "True if tgt.Disk has a GUID Partition Table");
BOOL_GETSET(fdisk, "True if tgt.Disk has fdisk Partitions");
BOOL_GETSET(boot, "True if tgt.Disk is a boot disk");
BOOL_GETSET(removable, "True if tgt.Disk is removable");
BOOL_GETSET(use_whole, "True if whole disk is to be used for install");

#undef	BOOL_GETSET

static PyObject * \
TgtDisk__str__(TgtDisk *self) {
	return (_call_print_method((PyObject*)self, "print_disk"));
}

static PyGetSetDef TgtDiskGetSets[] = {
	{
		.name = "geometry",
		.get = (getter)TgtDisk_get_geometry,
		.set = (setter)TgtDisk_set_geometry,
		.doc = TgtDisk_doc_geometry,
		.closure = NULL
	}, {
		.name = "children",
		.get = (getter)TgtDisk_get_children,
		.set = (setter)TgtDisk_set_children,
		.doc = TgtDisk_doc_children,
		.closure = NULL
	}, {
		.name = "vendor",
		.get = (getter)TgtDisk_get_vendor,
		.set = (setter)NULL, /* only set at __init__() */
		.doc = TgtDisk_doc_vendor,
		.closure = NULL
	}, {
		.name = "serialno",
		.get = (getter)TgtDisk_get_serialno,
		.set = (setter)NULL, /* only set at __init__() */
		.doc = TgtDisk_doc_serialno,
		.closure = NULL
	}, {
		.name = "blocks",
		.get = (getter)TgtDisk_get_blocks,
		.set = (setter)NULL, /* only set at __init__() */
		.doc = TgtDisk_doc_blocks,
		.closure = NULL
	}, {
		.name = "vtoc",
		.get = (getter)TgtDisk_get_vtoc,
		.set = (setter)TgtDisk_set_vtoc,
		.doc = TgtDisk_doc_vtoc,
		.closure = NULL
	}, {
		.name = "gpt",
		.get = (getter)TgtDisk_get_gpt,
		.set = (setter)TgtDisk_set_gpt,
		.doc = TgtDisk_doc_gpt,
		.closure = NULL
	}, {
		.name = "fdisk",
		.get = (getter)TgtDisk_get_fdisk,
		.set = (setter)TgtDisk_set_fdisk,
		.doc = TgtDisk_doc_fdisk,
		.closure = NULL
	}, {
		.name = "boot",
		.get = (getter)TgtDisk_get_boot,
		.set = (setter)TgtDisk_set_boot,
		.doc = TgtDisk_doc_boot,
		.closure = NULL
	}, {
		.name = "removable",
		.get = (getter)TgtDisk_get_removable,
		.set = (setter)TgtDisk_set_removable,
		.doc = TgtDisk_doc_removable,
		.closure = NULL
	}, {
		.name = "use_whole",
		.get = (getter)TgtDisk_get_use_whole,
		.set = (setter)TgtDisk_set_use_whole,
		.doc = TgtDisk_doc_use_whole,
		.closure = NULL
	}, { NULL } /* Sentinel */
};


#define	CONSTANT(v, cname, pyname, value) "\t\ttgt.Disk." pyname "\n"
PyDoc_STRVAR(TgtDiskTypeDoc,
"tgt.Disk(geometry, name, blocks, controller=tgt.Disk.ATA,\n\
          vtoc=False, gpt=Fasle, fdisk=False, boot=False,\n\
          removable=False, vendor=None, serialno=None,\n\
          use_whole=False) -> tgt.Disk object\n\
\n\
A Disk object represents a physical drive in the system.\n\
\n\
String constants defined for this class:\n\
\tCONTROLLER constants:\n"
CONTROLLER_CONSTANTS
"\t\ttgt.Disk.UNKNOWN");
#undef	CONSTANT


PyTypeObject TgtDiskType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.Disk",
	.tp_basicsize = sizeof (TgtDisk),
	.tp_dealloc = (destructor)TgtDisk_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtDiskTypeDoc,
	.tp_methods = TgtDiskMethods,
	.tp_members = TgtDiskMembers,
	.tp_getset = TgtDiskGetSets,
	.tp_init = (initproc)TgtDisk_Init,
	.tp_new = TgtDisk_New,
	.tp_str = (reprfunc)TgtDisk__str__
};
