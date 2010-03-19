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

#include "tgt.h"
#include "td_api.h"
#include "ti_api.h"

/* Our Exception */
PyObject *TgtError = NULL;
PyObject *TgtUtilsModule = NULL;

/*
 * Just the docstring is in this file as the PyDoc_STRVAR macro
 * declares a static character pointer.
 */
PyDoc_STRVAR(discover_target_data_doc,
"discover_target_data() -> tuple of tgt.Disk objects");
PyDoc_STRVAR(create_disk_target_doc,
"create_disk_target() -> int to indicate success or failure");
PyDoc_STRVAR(create_zfs_root_pool_doc,
"create_zfs_root_pool() -> int to indicate success or failure");
PyDoc_STRVAR(create_zfs_volume_doc,
"create_zfs_volume() -> int to indicate success or failure");
PyDoc_STRVAR(create_be_target_doc,
"create_be_target() -> int to indicate success or failure");
PyDoc_STRVAR(release_zfs_root_pool_doc,
"release_zfs_root_pool() -> int to indicate success or failure");

static PyMethodDef TgtMethods[] = {
	{
		.ml_name = "discover_target_data",
		.ml_meth = (PyCFunction)discover_target_data,
		.ml_flags = METH_NOARGS,
		.ml_doc = discover_target_data_doc
	},
	{
		.ml_name = "create_disk_target",
		.ml_meth = (PyCFunction)create_disk_target,
		.ml_flags = METH_VARARGS,
		.ml_doc = create_disk_target_doc
	},
	{
		.ml_name = "create_zfs_root_pool",
		.ml_meth = (PyCFunction)create_zfs_root_pool,
		.ml_flags = METH_VARARGS,
		.ml_doc = create_zfs_root_pool_doc
	},
	{
		.ml_name = "release_zfs_root_pool",
		.ml_meth = (PyCFunction)release_zfs_root_pool,
		.ml_flags = METH_VARARGS,
		.ml_doc = release_zfs_root_pool_doc
	},
	{
		.ml_name = "create_zfs_volume",
		.ml_meth = (PyCFunction)create_zfs_volume,
		.ml_flags = METH_VARARGS,
		.ml_doc = create_zfs_volume_doc
	},
	{
		.ml_name = "create_be_target",
		.ml_meth = (PyCFunction)create_be_target,
		.ml_flags = METH_VARARGS,
		.ml_doc = create_be_target_doc
	}, { NULL }  /* Sentinel */
};


/*
 * Function:	raise_td_errcode
 * Description:	based on td_errno_t raise appropriate Python error.
 * Parameters:	code
 * Returns:	None
 * Scope:	Public
 */
void
raise_td_errcode(void)
{
	switch (td_get_errno()) {
	case TD_E_SUCCESS:
	case TD_E_END:		/* end of enumerated list */
		break;
	case TD_E_MEMORY:	/* memory allocation failure */
		PyErr_NoMemory();
		break;
	case TD_E_NO_DEVICE:	/* no device for specified name */
		PyErr_SetString(TgtError, "No device for specified name");
		break;
	case TD_E_NO_OBJECT:	/* specified object does not exist */
		PyErr_SetString(TgtError, "Specified object does not exist");
		break;
	case TD_E_INVALID_ARG:	/* invalid argument passed */
		/* We should ensure this doesn't happen */
		PyErr_SetString(PyExc_TypeError, "Invalid argument passed");
		break;
	case TD_E_THREAD_CREATE: /* no resources for thread */
		PyErr_NoMemory();
		break;
	case TD_E_SEMAPHORE:	/* error on semaphore */
	case TD_E_MNTTAB:	/* error on open of mnttab */
		PyErr_SetString(TgtError, "No device for specified name");
		break;
	default:
		/* header changed and we missed it if this happens */
		PyErr_SetString(TgtError, "unknown td_errno_t code");
		break;
	}
}
/*
 * Function:	raise_ti_errcode
 * Description:	based on ti_errno_t raise appropriate Python error.
 * Parameters:	code
 * Returns:	None
 * Scope:	Public
 */
void
raise_ti_errcode(int ti_errno)
{
	switch (ti_errno) {
	case TI_E_SUCCESS:
	case TI_E_INVALID_FDISK_ATTR:	/* fdisk set of attributes invalid */
		PyErr_SetString(TgtError, "fdisk set of attributes invalid");
		break;
	case TI_E_FDISK_FAILED:		/* fdisk part of TI failed */
		PyErr_SetString(TgtError, "fdisk part of TI failed");
		break;
	case TI_E_UNMOUNT_FAILED:	/* freeing target media failed */
		PyErr_SetString(TgtError, "freeing target media failed");
		break;
	case TI_E_INVALID_VTOC_ATTR:	/* VTOC set of attributes invalid */
		PyErr_SetString(TgtError, "VTOC set of attributes invalid");
		break;
	case TI_E_DISK_LABEL_FAILED:	/* disk label failed */
		PyErr_SetString(PyExc_TypeError, "disk label failed");
		break;
	case TI_E_VTOC_FAILED: 		/* VTOC part of TI failed */
		PyErr_SetString(PyExc_TypeError, "VTOC part of TI failed");
		break;
	case TI_E_INVALID_ZFS_ATTR:	/* ZFS set of attributes invalid */
		PyErr_SetString(PyExc_TypeError,
		    "ZFS set of attributes invalid");
		break;
	case TI_E_ZFS_FAILED:		/* ZFS part of TI failed */
		PyErr_SetString(PyExc_TypeError, "ZFS part of TI failed");
		break;
	case TI_E_INVALID_BE_ATTR:	/* BE set of attributes invalid */
		PyErr_SetString(PyExc_TypeError,
		    "BE set of attributes invalid");
		break;
	case TI_E_BE_FAILED:		/* BE part of TI failed */
		PyErr_SetString(PyExc_TypeError, "BE part of TI failed");
		break;
	case TI_E_REP_FAILED:		/* progress report failed */
		PyErr_SetString(PyExc_TypeError, "progress report failed");
		break;
	case TI_E_TARGET_UNKNOWN:	/* unknown target type */
		PyErr_SetString(PyExc_TypeError, "unknown target type");
		break;
	case TI_E_TARGET_NOT_SUPPORTED:	/* unsupported target type */
		PyErr_SetString(PyExc_TypeError, "unsupported target type");
		break;
	case TI_E_INVALID_RAMDISK_ATTR:
		PyErr_SetString(PyExc_TypeError, "Invalid ramdisk attribute");
		break;
	case TI_E_RAMDISK_MKFILE_FAILED:
		PyErr_SetString(PyExc_TypeError, "ramdisk mkfile failed");
		break;
	case TI_E_RAMDISK_LOFIADM_FAILED:
		PyErr_SetString(PyExc_TypeError, "ramdisk lofiadm failed");
		break;
	case TI_E_NEWFS_FAILED:
		PyErr_SetString(PyExc_TypeError, "newfs failed");
		break;
	case TI_E_MKDIR_FAILED:
		PyErr_SetString(PyExc_TypeError, "mkdir failed");
		break;
	case TI_E_MOUNT_FAILED:
		PyErr_SetString(PyExc_TypeError, "mount failed");
		break;
	case TI_E_RMDIR_FAILED:
		PyErr_SetString(PyExc_TypeError, "rmdir failed");
		break;
	case TI_E_PY_INVALID_ARG:	/* invalid arg in Python interface */
		PyErr_SetString(PyExc_TypeError,
		    "invalid arg in Python interface");
		break;
	case TI_E_PY_NO_SPACE:		/* no space error in Python interface */
		PyErr_SetString(PyExc_TypeError,
		    "no space error in Python interface");
		break;
	default:
		/* header changed and we missed it if this happens */
		PyErr_SetString(TgtError, "unknown ti_errno_t code");
		break;
	}
}


PyDoc_STRVAR(TgtDoc,
"This module provides tgt.Disk, tgt.Partition, and tgt.Slice types.");

#ifndef	PyMODINIT_FUNC
#define	PyMODINIT_FUNC void
#endif	/* PyMODINIT_FUNC */
PyMODINIT_FUNC
inittgt(void)
{
	PyObject *module = NULL;
	PyObject *unknown = NULL;

	/* The type objects provided */
	if (PyType_Ready(&TgtGeometryType) < 0)
		return;
	if (PyType_Ready(&TgtDiskType) < 0)
		return;
	if (PyType_Ready(&TgtPartitionType) < 0)
		return;
	if (PyType_Ready(&TgtSliceType) < 0)
		return;
	if (PyType_Ready(&TgtZpoolType) < 0)
		return;
	if (PyType_Ready(&TgtZFSDatasetType) < 0)
		return;

	module = Py_InitModule3("tgt", TgtMethods, TgtDoc);
	if (module == NULL)
		return;


	Py_INCREF(&TgtGeometryType);
	PyModule_AddObject(module, "Geometry", (PyObject *)&TgtGeometryType);
	Py_INCREF(&TgtDiskType);
	PyModule_AddObject(module, "Disk", (PyObject *)&TgtDiskType);
	Py_INCREF(&TgtPartitionType);
	PyModule_AddObject(module, "Partition", (PyObject *)&TgtPartitionType);
	Py_INCREF(&TgtSliceType);
	PyModule_AddObject(module, "Slice", (PyObject *)&TgtSliceType);
	Py_INCREF(&TgtZpoolType);
	PyModule_AddObject(module, "Zpool", (PyObject *)&TgtZpoolType);
	Py_INCREF(&TgtZFSDatasetType);
	PyModule_AddObject(module, "ZFSDataset",
	    (PyObject *)&TgtZFSDatasetType);

	TgtError = PyErr_NewException("tgt.TgtError", NULL, NULL);
	PyModule_AddObject(module, "TgtError", TgtError);

	/* Initialize each type object. */
	unknown = PyString_FromString("unknown");
	init_disk(unknown);
	init_partition(unknown);
	init_slice(unknown);
}

PyObject *retrieve_tgt_utils_module() {
	if (TgtUtilsModule == NULL) {
		TgtUtilsModule = PyImport_ImportModule(TGT_UTILS);
	}
	return (TgtUtilsModule);
}


PyObject *_call_print_method(PyObject *self, const char *method_name) {
	PyObject *tgt_utils = NULL;
	PyObject *print_method = NULL;
	PyObject *args = NULL;
	PyObject *obj_as_string = NULL;

	tgt_utils = retrieve_tgt_utils_module();

	if (tgt_utils == NULL) {
		PyErr_Format(PyExc_ImportError, "Could not import %s",
		    TGT_UTILS);
		return (NULL);
	}

	if (PyObject_HasAttrString(tgt_utils, method_name) != 1) {
		PyErr_Format(PyExc_NameError,
		    "'%s' not in %s", method_name, TGT_UTILS);
		return (NULL);
	}

	print_method = PyObject_GetAttrString(tgt_utils, method_name);
	if (PyCallable_Check(print_method) != 1) {
		PyErr_Format(PyExc_TypeError, "'%s' not a callable object",
		    method_name);
		goto done;
	}

	args = PyTuple_Pack(1, self);

	if (args == NULL) {
		PyErr_NoMemory();
		goto done;
	}

	obj_as_string = PyObject_Call(print_method, args, NULL);

done:
	Py_XDECREF(args);
	Py_XDECREF(print_method);

	return (obj_as_string);
}
