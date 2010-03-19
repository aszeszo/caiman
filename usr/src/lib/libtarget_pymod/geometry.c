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
#include "tgt.h"
#include "boolobject.h"
#include "td_api.h"

#define	_STRINGIZE(X)	#X
#define	STRINGIZE(X)	_STRINGIZE(X)

#define	DEFBLKSZ	512
#define	STR_DEFBLKSZ	STRINGIZE(DEFBLKSZ)

#define	DEFCYLSZ	0
#define	STR_DEFCYLSZ	STRINGIZE(DEFCYLSZ)


/*
 * Function:    TgtGeometry_Init
 * Description: Initialize a tgt.Geometry object.
 * Parameters:
 *     self:    tgt.Geometry object to fill in
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
TgtGeometry_Init(TgtGeometry *self, PyObject *args, PyObject *kwds)
{
	int rc;

	/* Remember to keep TgtGeometryTypeDoc current with this list */
	static char *kwlist[] = { "cylsz", "blocksz", NULL };

	/* set default vaule for blocksz */
	self->blocksz = DEFBLKSZ;
	self->cylsz = DEFCYLSZ;

	rc = PyArg_ParseTupleAndKeywords(args, kwds, "|II", kwlist,
		&self->cylsz, &self->blocksz);

	if (!rc)
		return (-1);

	return (0);
}


/*
 * Function:    TgtGeometry_New
 * Description: allocate and assign sensible initial values to a tgt.Geometry.
 * Parameters:
 *     type:    type object, do *NOT* assume it is TgtGeometryType!
 *     args:    ignored, exists to match function prototype.
 *     kwds:    ignored, exists to match function prototype.
 * Returns:     None
 * Scope:       Private
 */
static PyObject *
TgtGeometry_New(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
	TgtGeometry *self = NULL;

	self = (TgtGeometry *)type->tp_alloc(type, 0);
	if (self != NULL) {
		self->blocksz = DEFBLKSZ;
		self->cylsz = DEFCYLSZ;
	}
	return ((PyObject *)self);
}


/*
 * Function:	TgtGeometry_Deallocate
 * Description:	Free up a TgtGeometry
 * Parameters:
 * 	self:	TgtGeometry to de-allocate
 * Returns:	Nothing
 * Scope:	Private
 */
static void
TgtGeometry_Deallocate(TgtGeometry *self)
{
	self->ob_type->tp_free((PyObject*)self);
}


static PyObject*
TgtGeometry_copy(TgtGeometry* self, PyObject* args)
{
	if (!PyArg_ParseTuple(args, ":__copy__"))
		return (NULL);

	/*
	 * tgt.Geometry is Read Only. Nothing is settable.
	 * Therefore it is safe to just return another ref to this object.
	 */

	Py_INCREF(self);
	return ((PyObject *)self);
}
static PyObject*
TgtGeometry_deepcopy(TgtGeometry* self, PyObject* args)
{
	PyObject *memo = NULL;

	if (!PyArg_ParseTuple(args, "O:__deepcopy__", &memo))
		return (NULL);

	/* Don't need to do any checks */
	Py_INCREF(self);
	return ((PyObject *)self);
}

static PyMethodDef TgtGeometryMethods[] = {
	{
		.ml_name = "__copy__",
		.ml_meth = (PyCFunction)TgtGeometry_copy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, {
		.ml_name = "__deepcopy__",
		.ml_meth = (PyCFunction)TgtGeometry_deepcopy,
		.ml_flags = METH_VARARGS,
		.ml_doc = NULL
	}, { NULL } /* Sentinel */
};


static PyMemberDef TgtGeometryMembers[] = {
	{
		.name = "blocksz",
		.type = T_UINT,
		.offset = offsetof(TgtGeometry, blocksz),
		.flags = READONLY,
		.doc = "block size in bytes"
	}, {
		.name = "cylsz",
		.type = T_UINT,
		.offset = offsetof(TgtGeometry, cylsz),
		.flags = READONLY,
		.doc = "cylinder size in blocks"
	}, { NULL } /* Sentinel */
};


PyDoc_STRVAR(TgtGeometryTypeDoc,
"tgt.Geometry(cylsz=" STR_DEFCYLSZ ", blocksz=" STR_DEFBLKSZ
") -> tgt.Geometry object.\n\
\n\
A Geometry object represents characteristics of a physical\n\
drive in the system which are used in size/offset calculations.\n\
\n\
The block and cylinder sizes are read-only and can only be set\n\
when the tgt.Geometry is initialized.\n\
\n\
The default \"cylsz\" is almost certainly not what you want and\n\
will not allow sane calculations of tgt.Partition boundaries.");


PyTypeObject TgtGeometryType = {
	PyObject_HEAD_INIT(NULL)
	.ob_size = 0,
	.tp_name = "tgt.Geometry",
	.tp_basicsize = sizeof (TgtGeometry),
	.tp_dealloc = (destructor)TgtGeometry_Deallocate,
	.tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
	.tp_doc = TgtGeometryTypeDoc,
	.tp_methods = TgtGeometryMethods,
	.tp_members = TgtGeometryMembers,
	.tp_init = (initproc)TgtGeometry_Init,
	.tp_new = TgtGeometry_New
};

/*
 * The default to initialize tgt.Disk, tgt.Partition, tgt.Slice with. While
 * block size is often 512, cylinder size varies more.
 *
 * Just like Py_None you still have to inc/dec references on TgtGeometryDefault.
 *
 * Currently this is just used in tgt.[Disk|Partition|Slice].__new__() to get a
 * default tgt.Geometry without fear of memory allocation failure and because
 * they will throw out the geometry in __init__() with a real one. So calling
 * alloc then init on TgtGeometry is slow and wasteful.
 *
 * If the members weren't read only this would require chaning all "setter"
 * functions to verify the user isn't tryin to modify _TgtGeometryDefault.
 */
static TgtGeometry _TgtGeometryDefault = {
	PyObject_HEAD_INIT(&TgtGeometryType)
	.blocksz = DEFBLKSZ,
	.cylsz = DEFCYLSZ
};

PyObject *TgtGeometryDefault = (PyObject *)&_TgtGeometryDefault;
