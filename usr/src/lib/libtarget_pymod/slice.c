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

#include "disk.h"
#include "partition.h"
#include "slice.h"
#include "tgt.h"
#include "td_api.h"

slice_const SliceConst;

PyTypeObject TgtSliceType; /* forward declaration */

#define	_STRINGIZE(X)	#X
#define	STRINGIZE(X)	_STRINGIZE(X)

#define	MAXNUM		15
#define	STR_MAXNUM	STRINGIZE(MAXNUM)

/*
 * Function:	init_slice
 * Description:	fill in the class data for tgt.Slice.
 *              This is stored in SliceConst and then we make it available
 *              as data to the class.
 * Parameters:
 *     unknown: the shared string "unknown".
 * Returns:	None
 * Scope:	Private
 *
 * NOTE: You must not call this until after you have called
 *       PyType_Ready(&TgtSliceType), as this adds to the Type's dictionary.
 *
 *       You should not need to modify this except for a "constant" that is not
 *       part of SLICE_TAG_CONSTANTS, like "unknown".
 */
void
init_slice(PyObject *unknown)
{
	/* These constants are never cleaned */
#define	CONSTANT(v, cname, pyname, value) \
	SliceConst.cname = PyString_FromString(value);
	SLICE_TAG_CONSTANTS
	SLICE_USED_BY_CONSTANTS
#undef	CONSTANT
	SliceConst.unknown = unknown; /* add the shared constant. */

	/*
	 * Keep in mind dictionaries don't steal a reference to key or value.
	 * Which is perfect, we have a pointer to them in SliceConst but now
	 * when the type object is cleaned up their ref count will go to 0
	 * and they will disappear.
	 */
#define	CONSTANT(v, cname, pyname, value) \
	PyDict_SetItemString(TgtSliceType.tp_dict, pyname, SliceConst.cname);
	SLICE_TAG_CONSTANTS
	SLICE_USED_BY_CONSTANTS
#undef	CONSTANT
	PyDict_SetItemString(TgtSliceType.tp_dict, "UNKNOWN", unknown);
}


/*
 * Function:	TgtSlice_Init
 * Description:	Initialize a tgt.Slice object.
 * Parameters:
 *     self:	tgt.Slice object to fill in
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
TgtSlice_Init(TgtSlice *self, PyObject *args, PyObject *kwds)
{
	int rc;
	char *tag = NULL;
	char *type = NULL;
	char *user = NULL;
	PyObject *geometry = NULL;
	PyObject *blocks = NULL;
	PyObject *offset = NULL;
	PyObject *unmountable = NULL;
	PyObject *readonly = NULL;
	PyObject *modified = NULL;
	PyObject *tmp = NULL;

	static char *kwlist[] = {
		"geometry", "number", "tag", "type", "offset", "blocks",
		"user", "unmountable", "readonly", "modified", NULL
	};

	rc = PyArg_ParseTupleAndKeywords(args, kwds, "O!BssOO|zO!O!O!", kwlist,
	    &TgtGeometryType, &geometry, &self->number, &tag, &type, &offset,
	    &blocks, &user, &PyBool_Type, &unmountable, &PyBool_Type,
	    &readonly, &PyBool_Type, &modified);

	if (!rc)
		return (-1); /* Raises TypeError */

	tmp = self->geometry;
	Py_INCREF(geometry);
	self->geometry = (PyObject *)geometry;
	Py_XDECREF(tmp);

	/*  between 0 and 15 inclusive */
	if (self->number < 0 || self->number > MAXNUM) {
		PyErr_SetString(PyExc_ValueError,
		    "tgt.Slice() \"id\" must be between 0 and " STR_MAXNUM
		    " inclusive");
		return (-1);
	}

	/* for tag we need to convert string to the right value */
	while (1) {
#define		CONSTANT(v, cname, pyname, value) \
		if (strcmp(tag, value) == 0) { \
			self->tag = (uint8_t)v; \
			break; \
		}
		SLICE_TAG_CONSTANTS
#undef		CONSTANT
		PyErr_SetString(PyExc_ValueError,
		    "tgt.Slice() \"tag\" must be one of the appropriate "
		    "class constants");
		return (-1);
	}

	/* for user we need to look up the right constant */
	while (type != NULL) { /* infinite loop if we were given a type */
#define		CONSTANT(v, cname, pyname, value) \
		if (strcmp(type, value) == 0) { \
			self->type = (uint8_t)v; \
			break; \
		}
		SLICE_USED_BY_CONSTANTS
#undef		CONSTANT
		PyErr_Format(PyExc_ValueError,
		    "tgt.Slice() \"type\" must be one of the appropriate "
		    "class constants, got \"%s\"", type);
		return (-1);
	}

	if (user == NULL) {
		self->user = NULL;
	} else {
		self->user = strdup(user);
	}

	/* Python 2.4 has no scan code for a potentially 64-bit value */
	if (PyLong_Check(blocks)) {
		self->blocks = PyLong_AsUnsignedLongLong(blocks);
	} else {
		if (PyInt_Check(blocks)) {
			self->blocks = (uint64_t)PyInt_AsLong(blocks);
		} else {
			PyErr_SetString(PyExc_TypeError, "tgt.Slice() "
			    "\"blocks\" an integer is required");
			return (-1);
		}
	}
	if (PyLong_Check(offset)) {
		self->offset = PyLong_AsUnsignedLongLong(offset);
	} else {
		if (PyInt_Check(offset)) {
			self->offset = (uint64_t)PyInt_AsLong(offset);
		} else {
			PyErr_SetString(PyExc_TypeError, "tgt.Slice() "
			    "\"offset\" an integer is required");
			return (-1);
		}
	}

#define	SET_BOOL(nm) self->nm = (nm == Py_True) ? 1 : 0
	SET_BOOL(unmountable);
	SET_BOOL(readonly);
	SET_BOOL(modified);
#undef	SET_BOOL

	return (rc);
}


/*
 * Function:	TgtSlice_New
 * Description:	allocate and assign sensible initial values to a tgt.Slice.
 * Parameters:
 *     type:	type object, do *NOT* assume it is TgtSliceType!
 *     args:	ignored, exists to match function prototype.
 *     kwds:	ignored, exists to match function prototype.
 * Returns:	None
 * Scope:	Private
 */
static PyObject *
TgtSlice_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtSlice *self = NULL;

	self = (TgtSlice *)type->tp_alloc(type, 0);
	if (self == NULL)
		return (NULL); /* sets memory error */

	self->geometry = TgtGeometryDefault;
	Py_INCREF(TgtGeometryDefault);
	self->user = self->last_mount = NULL;
	self->blocks = self->offset = 0;
	self->number = 0;
	self->tag = self->type = (uint8_t)-1;
	self->unmountable = self->readonly = self->modified = 0;

	return ((PyObject *)self);
}


/*
 * Function:	TgtSlice_Deallocate
 * Description:	Free up a TgtSlice
 * Parameters:
 * 	self:	TgtSlice to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 *
 * NOTE: Unless you have not followed the MEMBER macros at the top there
 *       is no reason to alter this function.
 */
static void
TgtSlice_Deallocate(TgtSlice *self)
{
	Py_XDECREF(self->geometry);
	if (self->user != NULL) {
		free(self->user);
		self->user = NULL;
	}
	if (self->last_mount != NULL) {
		free(self->last_mount);
		self->last_mount = NULL;
	}
	self->ob_type->tp_free((PyObject*)self);
}

static int
TgtSlice_copy_common(TgtSlice *orig, TgtSlice *copy)
{
	PyObject *tmp = NULL;

	/* Geometry is always shared */
	tmp = copy->geometry;
	Py_INCREF(orig->geometry);
	copy->geometry = orig->geometry;
	Py_XDECREF(tmp);

#define	STRCOPY(member) \
	if (orig->member != NULL) { \
		copy->member = strdup(orig->member); \
		if (copy->member == NULL) { \
			PyErr_NoMemory(); \
			return (-1); \
		} \
	}

	STRCOPY(user);
	STRCOPY(last_mount);
#undef	STRCOPY


#define	SET_MEMBER(member) copy->member = orig->member
	SET_MEMBER(offset);
	SET_MEMBER(blocks);
	SET_MEMBER(number);
	SET_MEMBER(tag);
	SET_MEMBER(type);
	SET_MEMBER(unmountable);
	SET_MEMBER(readonly);
	SET_MEMBER(modified);
#undef	SET_MEMBER

	return (0);
}

static PyObject*
TgtSlice_copy(TgtSlice* self, PyObject* args)
{
	TgtSlice *copy = NULL;

	if (!PyArg_ParseTuple(args, ":__copy__"))
		return (NULL);

	copy = (TgtSlice *)TgtSliceType.tp_new(&TgtSliceType, NULL, NULL);
	if (copy == NULL)
		return (PyErr_NoMemory());

	if (TgtSlice_copy_common(self, copy) != 0) {
		Py_DECREF(copy);
		return (NULL);
	}

	return ((PyObject *)copy);
}
static PyObject*
TgtSlice_deepcopy(TgtSlice* self, PyObject* args)
{
	int rc;
	PyObject *memo = NULL;
	PyObject *tmp = NULL;
	TgtSlice *copy = NULL;

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

	copy = (TgtSlice *)TgtSliceType.tp_new(&TgtSliceType, NULL, NULL);
	if (copy == NULL)
		return (PyErr_NoMemory());


	if (TgtSlice_copy_common(self, copy) != 0) {
		Py_DECREF(copy);
		return (NULL);
	}

	/* add this to memo dict so we won't do it again */
	rc = PyDict_SetItem(memo, (PyObject *)self, (PyObject *)copy);
	if (rc == -1) {
		Py_DECREF(copy);
		return (NULL);
	}

	return ((PyObject *)copy);
}

static PyMethodDef TgtSliceMethods[] = {
	{
		.ml_name = "__copy__",
		.ml_meth = (PyCFunction)TgtSlice_copy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, {
		.ml_name = "__deepcopy__",
		.ml_meth = (PyCFunction)TgtSlice_deepcopy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, { NULL } /* Sentinel */
};


/* All the TgtSliceGetSets */
static PyObject *
TgtSlice_get_geometry(TgtSlice *self, void *closure)
{
	PyObject *result = self->geometry;
	assert(result != NULL);
	Py_INCREF(result);
	return (result);
}
static int
TgtSlice_set_geometry(TgtSlice *self, PyObject *value, void *closure)
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
PyDoc_STRVAR(TgtSlice_doc_geometry, "tgt.Geometry object describing tgt.Disk");

static PyObject *
TgtSlice_get_user(TgtSlice *self, void *closure)
{
	if (self->user == NULL) {
		Py_INCREF(SliceConst.unknown);
		return (SliceConst.unknown);
	}
	return (PyString_FromString(self->user));
}
static int
TgtSlice_set_user(TgtSlice *self, PyObject *value, void *closure)
{
	char *str;
	uint8_t newtype;
	if (value == NULL) {
		/* NULL/None is OK that will become "unknown" */
		str = NULL;
	} else {
		if (PyString_Check(value) == 0) {
			PyErr_SetString(PyExc_TypeError,
			    "\"user\" must be a str");
			return (-1);
		}
		str = strdup(PyString_AsString(value));
		if (str == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

	if (self->user != NULL)
		free(self->user);
	self->user = str;
	return (0);
}
PyDoc_STRVAR(TgtSlice_doc_user, "slice user string or tgt.Slice.UNKNOWN");

static PyObject *
TgtSlice_get_last_mount(TgtSlice *self, void *closure)
{
	if (self->last_mount == NULL) {
		Py_INCREF(Py_None);
		return (Py_None);
	}
	return (PyString_FromString(self->last_mount));
}
static int
TgtSlice_set_last_mount(TgtSlice *self, PyObject *value, void *closure)
{
	char *str;
	uint8_t newtype;
	if (value == NULL) {
		/* NULL/None is OK that will become "None" */
		str = NULL;
	} else {
		if (PyString_Check(value) == 0) {
			PyErr_SetString(PyExc_TypeError,
			    "\"last_mount\" must be a str");
			return (-1);
		}
		str = strdup(PyString_AsString(value));
		if (str == NULL) {
			PyErr_NoMemory();
			return (-1);
		}
	}

	if (self->last_mount != NULL)
		free(self->last_mount);
	self->last_mount = str;
	return (0);
}
PyDoc_STRVAR(TgtSlice_doc_last_mount,
	"last mountpoint (for UFS slice) or None");

static PyObject *
TgtSlice_get_offset(TgtSlice *self, void *closure)
{
	return (PyLong_FromLongLong(self->offset));
}
static int
TgtSlice_set_offset(TgtSlice *self, PyObject *value, void *closure)
{
	uint64_t newoff;

	if (value == NULL)
		goto TgtSlice_set_offset_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newoff = (uint64_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newoff = (uint64_t)PyInt_AsLong(value);
		} else {
			goto TgtSlice_set_offset_TYPE_ERROR;
		}
	}
	self->offset = newoff;
	return (0);

TgtSlice_set_offset_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError, "\"offset\" must be an integer");
	return (-1);
}
PyDoc_STRVAR(TgtSlice_doc_offset, "offset (in blocks)");

static PyObject *
TgtSlice_get_blocks(TgtSlice *self, void *closure)
{
	return (PyLong_FromLongLong(self->blocks));
}
static int
TgtSlice_set_blocks(TgtSlice *self, PyObject *value, void *closure)
{
	uint64_t newblk;

	if (value == NULL)
		goto TgtSlice_set_blocks_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newblk = (uint64_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newblk = (uint64_t)PyInt_AsLong(value);
		} else {
			goto TgtSlice_set_blocks_TYPE_ERROR;
		}
	}
	self->blocks = newblk;
	return (0);

TgtSlice_set_blocks_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError, "\"blocks\" must be an integer");
	return (-1);
}
PyDoc_STRVAR(TgtSlice_doc_blocks, "size in blocks");

static PyObject *
TgtSlice_get_number(TgtSlice *self, void *closure)
{
	PyObject *result = PyInt_FromLong((long)self->number);
	return (result);
}
static int
TgtSlice_set_number(TgtSlice *self, PyObject *value, void *closure)
{
	uint8_t newid;

	if (value == NULL)
		goto TgtSlice_set_id_TYPE_ERROR;

	if (PyLong_Check(value)) {
		newid = (uint8_t)PyLong_AsUnsignedLong(value);
	} else {
		if (PyInt_Check(value)) {
			newid = (uint8_t)PyInt_AsLong(value);
		} else {
			goto TgtSlice_set_id_TYPE_ERROR;
		}
	}

	if (newid > MAXNUM) {
		PyErr_SetString(PyExc_ValueError,
		    "\"id\" must be 0-" STR_MAXNUM);
		return (-1);
	}
	self->number = newid;
	return (0);

TgtSlice_set_id_TYPE_ERROR:
	PyErr_SetString(PyExc_TypeError,
	    "\"id\" must be an integer 0-" STR_MAXNUM);
	return (-1);
}
PyDoc_STRVAR(TgtSlice_doc_number, "slice number, (0-" STR_MAXNUM ")");

static PyObject *
TgtSlice_get_tag(TgtSlice *self, void *closure)
{
	PyObject *result = NULL;

	switch (self->tag) {
#define	CONSTANT(v, cname, pyname, value) \
	case v: \
		result = SliceConst.cname; \
		break;
	SLICE_TAG_CONSTANTS
#undef	CONSTANT
	default:
		result = SliceConst.unknown;
	}
	Py_INCREF(result);
	return (result);
}
static int
TgtSlice_set_tag(TgtSlice *self, PyObject *value, void *closure)
{
	char *str;
	uint8_t newtag;
	if (value == NULL || (PyString_Check(value) == 0)) {
		PyErr_SetString(PyExc_TypeError, "\"tag\" must be a str");
		return (-1);
	}

	str = PyString_AsString(value);
	while (1) {
#define		CONSTANT(v, cname, pyname, value) \
		if (strcmp(str, value) == 0) { \
			newtag = (uint8_t)v; \
			break; \
		}
		SLICE_TAG_CONSTANTS
#undef		CONSTANT
		PyErr_SetString(PyExc_ValueError,
		    "\"tag\" must be one of the appropriate class constants");
		return (-1);
	}
	self->tag = newtag;

	return (0);
}
PyDoc_STRVAR(TgtSlice_doc_tag, "slice tag (a tgt.Slice TAG constant)");

static PyObject *
TgtSlice_get_type(TgtSlice *self, void *closure)
{
	PyObject *result = NULL;

	switch (self->type) {
#define	CONSTANT(v, cname, pyname, value) \
	case v: \
		result = SliceConst.cname; \
		break;
	SLICE_USED_BY_CONSTANTS
#undef	CONSTANT
	default:
		result = SliceConst.unknown;
	}
	Py_INCREF(result);
	return (result);
}
static int
TgtSlice_set_type(TgtSlice *self, PyObject *value, void *closure)
{
	char *str;
	uint8_t newtype;
	if (value == NULL || (PyString_Check(value) == 0)) {
		PyErr_SetString(PyExc_TypeError, "\"type\" must be a str");
		return (-1);
	}

	str = PyString_AsString(value);
	while (1) {
#define		CONSTANT(v, cname, pyname, value) \
		if (strcmp(str, value) == 0) { \
			newtype = (uint8_t)v; \
			break; \
		}
		SLICE_USED_BY_CONSTANTS
#undef		CONSTANT
		PyErr_SetString(PyExc_ValueError,
		    "\"type\" must be one of the appropriate class contants");
		return (-1);
	}
	self->type = newtype;

	return (0);
}
PyDoc_STRVAR(TgtSlice_doc_type, "slice type (a tgt.Slice TYPE constant)");

#define	BOOL_GETSET(member, doc) \
static PyObject * \
TgtSlice_get_##member(TgtSlice *self, void *closure) \
{ \
	PyObject *result = (self->member == 1) ? Py_True : Py_False; \
	Py_INCREF(result); \
	return (result); \
} \
static int \
TgtSlice_set_##member(TgtSlice *self, PyObject *value, void *closure) \
{ \
	if (value == NULL || (PyBool_Check(value) == 0)) { \
		PyErr_SetString(PyExc_TypeError, "\"" #member "\"" \
		    "must be a bool"); \
		return (-1); \
	} \
	self->member = (value == Py_True) ? 1 : 0; \
	return (0); \
} \
PyDoc_STRVAR(TgtSlice_doc_##member, doc)

BOOL_GETSET(unmountable, "True if tgt.Slice is unmountable");
BOOL_GETSET(readonly, "True if tgt.Slice is read only");
BOOL_GETSET(modified, "True if tgt.Slice has been modified");

#undef	BOOL_GETSET

static PyObject * \
TgtSlice__str__(TgtSlice *self) {
	return (_call_print_method((PyObject*)self, "print_slice"));
}

static PyGetSetDef TgtSliceGetSets[] = {
	{
		.name = "geometry",
		.get = (getter)TgtSlice_get_geometry,
		.set = (setter)TgtSlice_set_geometry,
		.doc = TgtSlice_doc_geometry,
		.closure = NULL
	}, {
		.name = "user",
		.get = (getter)TgtSlice_get_user,
		.set = (setter)TgtSlice_set_user,
		.doc = TgtSlice_doc_user,
		.closure = NULL
	}, {
		.name = "last_mount",
		.get = (getter)TgtSlice_get_last_mount,
		.set = (setter)TgtSlice_set_last_mount,
		.doc = TgtSlice_doc_last_mount,
		.closure = NULL
	}, {
		.name = "offset",
		.get = (getter)TgtSlice_get_offset,
		.set = (setter)TgtSlice_set_offset,
		.doc = TgtSlice_doc_offset,
		.closure = NULL
	}, {
		.name = "blocks",
		.get = (getter)TgtSlice_get_blocks,
		.set = (setter)TgtSlice_set_blocks,
		.doc = TgtSlice_doc_blocks,
		.closure = NULL
	}, {
		.name = "number",
		.get = (getter)TgtSlice_get_number,
		.set = (setter)TgtSlice_set_number,
		.doc = TgtSlice_doc_number,
		.closure = NULL
	}, {
		.name = "tag",
		.get = (getter)TgtSlice_get_tag,
		.set = (setter)TgtSlice_set_tag,
		.doc = TgtSlice_doc_tag,
		.closure = NULL
	}, {
		.name = "type",
		.get = (getter)TgtSlice_get_type,
		.set = (setter)TgtSlice_set_type,
		.doc = TgtSlice_doc_type,
		.closure = NULL
	}, {
		.name = "unmountable",
		.get = (getter)TgtSlice_get_unmountable,
		.set = (setter)TgtSlice_set_unmountable,
		.doc = TgtSlice_doc_unmountable,
		.closure = NULL
	}, {
		.name = "readonly",
		.get = (getter)TgtSlice_get_readonly,
		.set = (setter)TgtSlice_set_readonly,
		.doc = TgtSlice_doc_readonly,
		.closure = NULL
	}, {
		.name = "modified",
		.get = (getter)TgtSlice_get_modified,
		.set = (setter)TgtSlice_set_modified,
		.doc = TgtSlice_doc_modified,
		.closure = NULL
	}, { NULL } /* Sentinel */
};


/*
 * TODO keep this comment current!
 * If you added a MEMBER at the top that should be part of __init__()
 * then put it in this doc string.
 */
#define	CONSTANT(v, cname, pyname, value) "\t\ttgt.Slice." pyname "\n"

PyDoc_STRVAR(TgtSliceTypeDoc,
"tgt.Slice(geometry, number, tag, type, offset, blocks,\n\
           user=tgt.Slice.UNKNOWN, unmountable=False, readonly=False,\n\
           modified=False) -> tgt.Slice object\n\
\n\
A Slice object represents a Solaris slice within a Partition object.\n\
\n\
There are two groups of string constants defined for this class:\n\
\tTAG constants (valid for tgt.Slice.tag):\n"
SLICE_TAG_CONSTANTS
"\t\ttgt.Slice.UNKNOWN\n\
\tTYPE constants (valid for tgt.Slice.type):\n"
SLICE_USED_BY_CONSTANTS
"\t\ttgt.Slice.UNKNOWN");

PyTypeObject TgtSliceType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.Slice",
	.tp_basicsize = sizeof (TgtSlice),
	.tp_dealloc = (destructor)TgtSlice_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtSliceTypeDoc,
	.tp_methods = TgtSliceMethods,
	.tp_members = NULL, /* TgtSliceMembers, */
	.tp_getset = TgtSliceGetSets,
	.tp_init = (initproc)TgtSlice_Init,
	.tp_new = TgtSlice_New,
	.tp_str = (reprfunc)TgtSlice__str__
};
