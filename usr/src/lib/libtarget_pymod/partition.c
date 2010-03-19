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
#include "partition.h"
#include "tgt.h"
#include "td_api.h"

/*
 * NOTE: libdiskmgmt has labelled partition data incorrectly. We correct it here
 *       in the Python names. TgtPartition data structure still use the
 *       libdiskmgmt naming scheme. Here is the conversion:
 *
 * libdiskmgmt   | Python | example
 * --------------+--------+----------------
 * id            | number | 1
 * type          | id     | 0xBF (Solaris2)
 * typetypething | type   | ???  (Primary)
 */


part_const PartConst;

PyTypeObject TgtPartitionType; /* forward declaration */

#define	MAXID (FD_NUMPART + MAX_EXT_PARTS)

/*
 * Function:	init_partition
 * Description:	fill in the class data for tgt.Partition.
 *              This is stored in PartConst and then we make it available
 *              as data to the class.
 * Parameters:
 *     unknown: the shared string "unknown".
 * Returns:	None
 * Scope:	Private
 *
 * NOTE: You must not call this until after you have called
 *       PyType_Ready(&TgtPartitionType), as this adds to the Type's dictionary.
 *
 *       Well not yet, but it could later.
 */
void
init_partition(PyObject *unknown)
{
	int rc;
	PyObject *v = NULL;
	PyObject *k = NULL;
	PartConst.unknown = unknown; /* add the shared constant. */
	PyObject *dict = PyDict_New();

	/* Add all our unique keys */
#define	CONSTANT(key, val) \
	v = PyString_FromString(val); \
	assert(v != NULL); \
	k = PyInt_FromLong(key); \
	assert(k != NULL); \
	rc = PyDict_SetItem(dict, k, v); \
	assert(rc == 0); \
	Py_DECREF(k); \
	Py_DECREF(v);
	UNIQUE_PARTITION_TYPE
#undef	CONSTANT

	/* add non-unique keys */
#define	CONSTANT(key, val) \
	k = PyInt_FromLong(key); \
	assert(k != NULL); \
	rc = PyDict_SetItem(dict, k, v); \
	assert(rc == 0); \
	Py_DECREF(k);

	v = PyString_FromString(TP_EUMEL_ELAN);
	assert(v != NULL);
	EUMEL_ELAN_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_NOVEL);
	assert(v != NULL);
	NOVEL_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_FAULT_TOLERANT_FAT32);
	assert(v != NULL);
	FAULT_TOLERANT_FAT32_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_FREE_FDISK_HDN_DOS_EXT);
	assert(v != NULL);
	FREE_FDISK_HDN_DOS_EXT_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_HP_SPEEDSTOR);
	assert(v != NULL);
	HP_SPEEDSTOR_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_DRDOS8);
	assert(v != NULL);
	DRDOS8_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_SPEEDSTOR);
	assert(v != NULL);
	SPEEDSTOR_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_RESERVED);
	assert(v != NULL);
	RESERVED_PARTITION_TYPE
	Py_DECREF(v);

	v = PyString_FromString(TP_UNUSED);
	assert(v != NULL);
	UNUSED_PARTITION_TYPE
	Py_DECREF(v);

	/* For "unknown" we can use our common PyObject */
	v = unknown;
	UNKNOWN_PARTITION_TYPE
	v = NULL;
	k = NULL;
#undef	CONSTANT

	PartConst.type = PyDictProxy_New(dict);
	PyDict_SetItemString(TgtPartitionType.tp_dict, "UNKNOWN", unknown);
	PyDict_SetItemString(TgtPartitionType.tp_dict, "ID", PartConst.type);
}

/*
 * Function:	TgtPartition_Init
 * Description:	Initialize a tgt.Partition object.
 * Parameters:
 *     self:	tgt.Partition object to fill in
 *     args:	the arguments given to Python to try to init object
 *     kwds:	similar to args.
 * Returns:	None
 * Scope:	Private
 *
 * NOTE: when tgt.discover_target_data() is called this is not used.
 *       This is for creating a layout without using libtd.so.
 *       Useful for testing and possibly for target instantiation?
 */
static int
TgtPartition_Init(TgtPartition *self, PyObject *args, PyObject *kwds)
{
	int rc;
	TgtGeometry *geometry = NULL;
	PyObject *active = NULL;
	PyObject *modified = NULL;
	PyObject *use_whole = NULL;
	PyObject *tmp = NULL;

	static char *kwlist[] = {
		"geometry", "number", "id", "offset", "blocks", "active",
		"modified", "use_whole", NULL
	};

	active = Py_False;
	rc = PyArg_ParseTupleAndKeywords(args, kwds, "O!IHII|O!O!O!", kwlist,
	    &TgtGeometryType, &geometry, &self->id, &self->type,
	    &self->offset, &self->blocks, &PyBool_Type, &active,
	    &PyBool_Type, &modified, &PyBool_Type, &use_whole);

	if (!rc)
		return (-1);

	tmp = self->geometry;
	Py_INCREF(geometry);
	self->geometry = (PyObject *)geometry;
	Py_XDECREF(tmp);

	/* Minimal validation */
	if (self->id > MAXID || self->id < 1) {
		PyErr_Format(PyExc_ValueError,
		    "tgt.Partition() \"id\" must be 1-%d", MAXID);
		return (-1);
	}

	if (self->type > 0xFF) {
		if (self->type != 0x182) { /* the one special case */
			PyErr_SetString(PyExc_ValueError,
			    "tgt.Partition() \"type\" must be between "
			    "0 and 255 or 386");
			return (-1);
		}
	}

#define	SET_BOOL(nm) self->nm = (nm == Py_True) ? 1 : 0
	SET_BOOL(active);
	SET_BOOL(modified);
	SET_BOOL(use_whole);
#undef	SET_BOOL

	return (rc);
}

/*
 * Function:	TgtPartition_New
 * Description:	allocate and assign sensible initial values to a tgt.Partition.
 * Parameters:
 *     type:	type object, do *NOT* assume it is TgtPartitionType!
 *     args:	ignored, exists to match function prototype.
 *     kwds:	ignored, exists to match function prototype.
 * Returns:	None
 * Scope:	Private
 */
static PyObject *
TgtPartition_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtPartition *self = NULL;

	self = (TgtPartition *)type->tp_alloc(type, 0);
	if (self == NULL)
		return (NULL); /* sets memory error */

	/* The only thing that can fail is PyTyple_New so do that first */
	if ((self->children = PyTuple_New(0)) == NULL) {
		return (NULL);
	}

	self->geometry = TgtGeometryDefault;
	Py_INCREF(TgtGeometryDefault);
	self->offset = self->blocks = 0;
	self->type = 0;
	self->id = 0;
	self->active = self->modified = self->use_whole = 0;
	self->children = PyTuple_New(0);

	return ((PyObject *)self);
}


/*
 * Function:	TgtPartition_Deallocate
 * Description:	Free up a TgtPartition
 * Parameters:
 * 	self:	TgtPartition to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 */
static void
TgtPartition_Deallocate(TgtPartition *self)
{
	Py_XDECREF(self->geometry);
	Py_XDECREF(self->children);
	self->ob_type->tp_free((PyObject*)self);
}

/* XXX Temporarily leave this in, but better implemented in Python */
static PyObject *
TgtPartition_type_as_string(TgtPartition *self)
{
	/*
	 * This is far easier to do in Python.
	 * In fact this method isn't even documented.
	 * You just have to figure out how to call the equivalent of
	 * PyDict_GetItem() on a PyDictProxy. Here it is!
	 */
	PyObject *key = NULL;
	PyObject *result = NULL;
	PyTypeObject *type = PartConst.type->ob_type;

	key = PyInt_FromLong(self->type);

	result = type->tp_as_mapping->mp_subscript(PartConst.type, key);
	assert(result != NULL);
	Py_INCREF(result);

	return (result);
}
PyDoc_STRVAR(TgtPartition_doc_type_as_string, "string representation of type");

static int
TgtPartition_copy_common(TgtPartition *orig, TgtPartition *copy)
{
	PyObject *tmp = NULL;

	/* Geometry is always shared */
	tmp = copy->geometry;
	Py_INCREF(orig->geometry);
	copy->geometry = orig->geometry;
	Py_XDECREF(tmp);

#define	SET_MEMBER(member) copy->member = orig->member
	SET_MEMBER(offset);
	SET_MEMBER(blocks);
	SET_MEMBER(type);
	SET_MEMBER(id);
	SET_MEMBER(active);
	SET_MEMBER(modified);
	SET_MEMBER(use_whole);
#undef	SET_MEMBER

	return (0);
}

static PyObject*
TgtPartition_copy(TgtPartition* self, PyObject* args)
{
	PyObject *tmp = NULL;
	TgtPartition *copy = NULL;

	if (!PyArg_ParseTuple(args, ":__copy__"))
		return (NULL);

	copy = (TgtPartition *)TgtPartitionType.tp_new(&TgtPartitionType, NULL,
	    NULL);
	if (copy == NULL)
		return (PyErr_NoMemory());

	if (TgtPartition_copy_common(self, copy) != 0) {
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
TgtPartition_deepcopy(TgtPartition* self, PyObject* args)
{
	int rc, idx;
	PyObject *tmp = NULL;
	PyObject *children = NULL;
	PyObject *memo = NULL;
	TgtPartition *copy = NULL;

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

	copy = (TgtPartition *)TgtPartitionType.tp_new(&TgtPartitionType, NULL,
	    NULL);
	if (copy == NULL)
		return (PyErr_NoMemory());

	if (TgtPartition_copy_common(self, copy) != 0) {
		Py_DECREF(copy);
		return (NULL);
	}

	/* need a new children tuple with new children elements of tuple */
	rc = PyTuple_Size(self->children);

	children = PyTuple_New(rc);
	for (idx = 0; idx < rc; idx++) {
		PyObject *oldc, *newc;
		oldc = PyTuple_GetItem(self->children, idx);
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

static PyMethodDef TgtPartitionMethods[] = {
	{
		.ml_name = "id_as_string", /* libdiskmgmt thinks of as type */
		.ml_meth = (PyCFunction)TgtPartition_type_as_string,
		.ml_flags = METH_NOARGS,
		.ml_doc = TgtPartition_doc_type_as_string
	}, {
		.ml_name = "__copy__",
		.ml_meth = (PyCFunction)TgtPartition_copy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, {
		.ml_name = "__deepcopy__",
		.ml_meth = (PyCFunction)TgtPartition_deepcopy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, { NULL } /* Sentinel */
};


static PyObject *
TgtPartition_get_geometry(TgtPartition *self, void *closure)
{
	PyObject *result = self->geometry;
	assert(result != NULL);
	Py_INCREF(result);
	return (result);
}
static int
TgtPartition_set_geometry(TgtPartition *self, PyObject *value, void *closure)
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
PyDoc_STRVAR(TgtPartition_doc_geometry,
	"tgt.Geometry object describing tgt.Disk");

static PyObject *
TgtPartition_get_children(TgtPartition *self, void *closure)
{
	PyObject *result = self->children;
	assert(result != NULL);
	Py_INCREF(result);
	return (result);
}
static int
TgtPartition_set_children(TgtPartition *self, PyObject *value, void *closure)
{
	PyObject *tmp = NULL;
	if (value == NULL || (PyTuple_Check(value) == 0)) {
		PyErr_SetString(PyExc_TypeError,
		    "children must be a tuple");
		return (-1);
	}
	/* TODO: verify children are all tgt.Slice objects */
	tmp = self->children;
	self->children = value;
	Py_INCREF(self->children);
	assert(tmp != NULL);
	Py_DECREF(tmp);
	return (0);
}
PyDoc_STRVAR(TgtPartition_doc_children, "tuple of tgt.Slice objects");

static PyObject *
TgtPartition_get_offset(TgtPartition *self, void *closure)
{
	PyObject *result = PyInt_FromSize_t((size_t)self->offset);
	if (result == NULL)
		return (PyErr_NoMemory());
	return (result);
}
static int
TgtPartition_set_offset(TgtPartition *self, PyObject *value, void *closure)
{
	uint32_t newoff;
	TgtGeometry *geo = (TgtGeometry *)self->geometry;

	assert(geo != NULL);

	if (value == NULL)
		goto TgtPartition_set_offset_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newoff = (uint32_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newoff = (uint32_t)PyInt_AsLong(value);
		} else {
			goto TgtPartition_set_offset_TYPE_ERROR;
		}
	}

	self->offset = newoff;
	return (0);

TgtPartition_set_offset_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError, "\"offset\" must be an integer");
	return (-1);
}
PyDoc_STRVAR(TgtPartition_doc_offset, "partition offset in disk blocks");

static PyObject *
TgtPartition_get_blocks(TgtPartition *self, void *closure)
{
	PyObject *result = PyInt_FromSize_t((size_t)self->blocks);
	if (result == NULL)
		return (PyErr_NoMemory());
	return (result);
}
static int
TgtPartition_set_blocks(TgtPartition *self, PyObject *value, void *closure)
{
	uint32_t newblk;
	TgtGeometry *geo = (TgtGeometry *)self->geometry;

	assert(geo != NULL);

	if (value == NULL)
		goto TgtPartition_set_blocks_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newblk = (uint32_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newblk = (uint32_t)PyInt_AsLong(value);
		} else {
			goto TgtPartition_set_blocks_TYPE_ERROR;
		}
	}

	self->blocks = newblk;
	return (0);

TgtPartition_set_blocks_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError, "\"blocks\" must be an integer");
	return (-1);
}
PyDoc_STRVAR(TgtPartition_doc_blocks, "partition size in disk blocks");

static PyObject *
TgtPartition_get_type(TgtPartition *self, void *closure)
{
	PyObject *result = PyInt_FromLong((long)self->type);
	if (result == NULL)
		return (PyErr_NoMemory());
	return (result);
}
static int
TgtPartition_set_type(TgtPartition *self, PyObject *value, void *closure)
{
	uint16_t newtype;

	if (value == NULL)
		goto TgtPartition_set_type_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newtype = (uint16_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newtype = (uint16_t)PyInt_AsLong(value);
		} else {
			goto TgtPartition_set_type_TYPE_ERROR;
		}
	}

	if (newtype > 0xFF) {
		if (newtype != 0x182) {
			PyErr_SetString(PyExc_ValueError,
			    "tgt.Partition() \"type\" must be between "
			    "0 and 255 or 386");
			return (-1);
		}
	}
	self->type = newtype;
	return (0);

TgtPartition_set_type_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError,
	    "\"type\" must be a tgt.Geometry object");
	return (-1);
}
PyDoc_STRVAR(TgtPartition_doc_type, "0-255 or 386, partition type");


static PyObject *
TgtPartition_get_id(TgtPartition *self, void *closure)
{
	PyObject *result = PyInt_FromLong((long)self->id);
	if (result == NULL)
		return (PyErr_NoMemory());
	return (result);
}
static int
TgtPartition_set_id(TgtPartition *self, PyObject *value, void *closure)
{
	uint8_t newid;

	if (value == NULL)
		goto TgtPartition_set_id_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newid = (uint8_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newid = (uint8_t)PyInt_AsLong(value);
		} else {
			goto TgtPartition_set_id_TYPE_ERROR;
		}
	}

	if (newid > MAXID || newid < 1) {
		PyErr_Format(PyExc_ValueError, "\"number\" must be 1-%d",
		    MAXID);
		return (-1);
	}
	self->id = newid;
	return (0);

TgtPartition_set_id_TYPE_ERROR:
	PyErr_Format(PyExc_ValueError,
	    "\"number\" must be an integer 1-%d", MAXID);
	return (-1);
}
PyDoc_STRVAR(TgtPartition_doc_id, "fdisk id");

#define	BOOL_GETSET(member, doc) \
static PyObject * \
TgtPartition_get_##member(TgtPartition *self, void *closure) \
{ \
	PyObject *result = (self->member == 1) ? Py_True : Py_False; \
	Py_INCREF(result); \
	return (result); \
} \
static int \
TgtPartition_set_##member(TgtPartition *self, PyObject *value, void *closure) \
{ \
	if (value == NULL || (PyBool_Check(value) == 0)) { \
		PyErr_SetString(PyExc_TypeError, "\"" #member "\"" \
		    "must be a bool"); \
		return (-1); \
	} \
	self->member = (value == Py_True) ? 1 : 0; \
	return (0); \
} \
PyDoc_STRVAR(TgtPartition_doc_##member, doc)

BOOL_GETSET(active, "True if tgt.Partition is active");
BOOL_GETSET(modified, "True if tgt.Partition has been modified");
BOOL_GETSET(use_whole, "True if whole partition is to be used for install");

#undef	BOOL_GETSET

static PyObject * \
TgtPartition__str__(TgtPartition *self) {
	return (_call_print_method((PyObject*)self, "print_partition"));
}

static PyGetSetDef TgtPartitionGetSets[] = {
	{
		.name = "geometry",
		.get = (getter)TgtPartition_get_geometry,
		.set = (setter)TgtPartition_set_geometry,
		.doc = TgtPartition_doc_geometry,
		.closure = NULL
	}, {
		.name = "children",
		.get = (getter)TgtPartition_get_children,
		.set = (setter)TgtPartition_set_children,
		.doc = TgtPartition_doc_children,
		.closure = NULL
	}, {
		.name = "offset",
		.get = (getter)TgtPartition_get_offset,
		.set = (setter)TgtPartition_set_offset,
		.doc = TgtPartition_doc_offset,
		.closure = NULL
	}, {
		.name = "blocks",
		.get = (getter)TgtPartition_get_blocks,
		.set = (setter)TgtPartition_set_blocks,
		.doc = TgtPartition_doc_blocks,
		.closure = NULL
	}, {
		.name = "id", /* libdiskmgmt thinks of as type */
		.get = (getter)TgtPartition_get_type,
		.set = (setter)TgtPartition_set_type,
		.doc = TgtPartition_doc_type,
		.closure = NULL
	}, {
		.name = "number", /* libdiskmgmt thinks of as id */
		.get = (getter)TgtPartition_get_id,
		.set = (setter)TgtPartition_set_id,
		.doc = TgtPartition_doc_id,
		.closure = NULL
	}, {
		.name = "active",
		.get = (getter)TgtPartition_get_active,
		.set = (setter)TgtPartition_set_active,
		.doc = TgtPartition_doc_active,
		.closure = NULL
	}, {
		.name = "modified",
		.get = (getter)TgtPartition_get_modified,
		.set = (setter)TgtPartition_set_modified,
		.doc = TgtPartition_doc_modified,
		.closure = NULL
	}, {
		.name = "use_whole",
		.get = (getter)TgtPartition_get_use_whole,
		.set = (setter)TgtPartition_set_use_whole,
		.doc = TgtPartition_doc_use_whole,
		.closure = NULL
	}, { NULL } /* Sentinel */
};


PyDoc_STRVAR(TgtPartitionTypeDoc,
"tgt.Partition(geometry, number, id, offset, blocks, active=False,\n\
               modified=False, use_whole=False) -> tgt.Partition object");


PyTypeObject TgtPartitionType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.Partition",
	.tp_basicsize = sizeof (TgtPartition),
	.tp_dealloc = (destructor)TgtPartition_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtPartitionTypeDoc,
	.tp_methods = TgtPartitionMethods,
	.tp_members = NULL, /* TgtPartitionMembers, */
	.tp_getset = TgtPartitionGetSets,
	.tp_init = (initproc)TgtPartition_Init,
	.tp_new = TgtPartition_New,
	.tp_str = (reprfunc)TgtPartition__str__
};
