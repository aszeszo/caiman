/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <Python.h>
#include <sys/varargs.h>
#include <stdio.h>
#include <libnvpair.h>
#include "libbe.h"

#define	BE_ATTR_ACTIVE  "active"
#define	BE_ATTR_ACTIVE_ON_BOOT  "active_boot"
#define	BE_ATTR_SPACE   "space_used"
#define	BE_ATTR_DATASET "dataset"
#define	BE_ATTR_STATUS  "status"
#define	BE_ATTR_DATE    "date"
#define	BE_ATTR_MOUNTED "mounted"

/*
 * public libbe functions
 */

PyObject *beCreateSnapshot(PyObject *, PyObject *);
PyObject *beCopy(PyObject *, PyObject *);
PyObject *beList(PyObject *, PyObject *);
PyObject *beActivate(PyObject *, PyObject *);
PyObject *beDestroy(PyObject *, PyObject *);
PyObject *beDestroySnapshot(PyObject *, PyObject *);
PyObject *beRename(PyObject *, PyObject *);
PyObject *beMount(PyObject *, PyObject *);
PyObject *beUnmount(PyObject *, PyObject *);
void initlibbe();

static boolean_t convertBEInfoToDictionary(be_node_list_t *be,
    PyObject **listDict);
static boolean_t convertDatasetInfoToDictionary(be_dataset_list_t *ds,
    PyObject **listDict);
static boolean_t convertSnapshotInfoToDictionary(be_snapshot_list_t *ss,
    PyObject **listDict);
static boolean_t convertPyArgsToNvlist(nvlist_t **nvList, int numArgs, ...);


/* ~~~~~~~~~~~~~~~ */
/* Public Funtions */
/* ~~~~~~~~~~~~~~~ */

/*
 * Function:    beCreateSnapshot
 * Description: Convert Python args to nvlist pairs and
 *              call libbe:be_create_snapshot to create a
 *              snapshot of all the datasets within a BE
 * Parameters:
 *   args -          pointer to a python object containing:
 *        beName -   The name of the BE to create a snapshot of
 *        snapName - The name of the snapshot to create (optional)
 *
 *        The following public attribute values. defined by libbe.h,
 *        are used by this function:
 *
 * Returns a pointer to a python object and an optional snapshot name:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beCreateSnapshot(PyObject *self, PyObject *args)
{
	char	*beName = NULL;
	char	*snapName = NULL;
	nvlist_t	*beAttrs = NULL;

	if (!PyArg_ParseTuple(args, "z|z", &beName, &snapName)) {
		return (Py_BuildValue("[is]", 1, NULL));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 4,
	    BE_ATTR_ORIG_BE_NAME, beName,
	    BE_ATTR_SNAP_NAME, snapName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("[is]", 1, NULL));
	}

	if (beAttrs != NULL) {
		if (be_create_snapshot(beAttrs) != 0) {
			nvlist_free(beAttrs);
			return (Py_BuildValue("[is]", 1, NULL));
		}
		if (snapName == NULL) {
			if (nvlist_lookup_pairs(beAttrs,
			    NV_FLAG_NOENTOK, BE_ATTR_SNAP_NAME,
			    DATA_TYPE_STRING, &snapName, NULL) != 0) {
				nvlist_free(beAttrs);
				return (Py_BuildValue("[is]", 1, NULL));
			}
			nvlist_free(beAttrs);
			return (Py_BuildValue("[is]", 0, snapName));
		}
	}
	nvlist_free(beAttrs);

	return (Py_BuildValue("[is]", 0, NULL));
}

/*
 * Function:    beCopy
 * Description: Convert Python args to nvlist pairs and call libbe:be_copy
 *              to create a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     trgtBeName - The name of the BE to create
 *     srcBeName - The name of the BE used to create trgtBeName (optional)
 *     rpool - The pool to create the new BE in (optional)
 *     srcSnapName - The snapshot name (optional)
 *     beNameProperties - The properties to use when creating
 *                        the BE (optional)
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beCopy(PyObject *self, PyObject *args)
{
	char	*trgtBeName = NULL;
	char	*srcBeName = NULL;
	char	*srcSnapName = NULL;
	char	*rpool = NULL;
	int		pos = 0;
	nvlist_t	*beAttrs = NULL;
	nvlist_t	*beProps = NULL;
	PyObject	*beNameProperties = NULL;
	PyObject	*pkey = NULL;
	PyObject	*pvalue = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "z|zzzO", &trgtBeName, &srcBeName,
	    &srcSnapName, &rpool, &beNameProperties)) {
		return (Py_BuildValue("i", 1));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 8,
	    BE_ATTR_NEW_BE_NAME, trgtBeName,
	    BE_ATTR_ORIG_BE_NAME, srcBeName,
	    BE_ATTR_SNAP_NAME, srcSnapName,
	    BE_ATTR_NEW_BE_POOL, rpool)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beNameProperties != NULL) {
		if (nvlist_alloc(&beProps, NV_UNIQUE_NAME, 0) != 0) {
			printf("nvlist_alloc failed.\n");
			goto cleanupFailure;
		}
		while (PyDict_Next(beNameProperties, &pos, &pkey, &pvalue)) {
			if (!convertPyArgsToNvlist(&beProps, 2,
			    PyString_AsString(pkey),
			    PyString_AsString(pvalue))) {
				goto cleanupFailure;
			}
		}
	}

	if (beProps != NULL && beAttrs != NULL &&
	    nvlist_add_nvlist(beAttrs, BE_ATTR_ZFS_PROPERTIES,
		    beProps) != 0) {
		goto cleanupFailure;
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_copy(beAttrs));
		nvlist_free(beAttrs);
		if (beProps != NULL) nvlist_free(beProps);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));

cleanupFailure:
	nvlist_free(beProps);
	nvlist_free(beAttrs);
	return (Py_BuildValue("i", 1));

}

/*
 * Function:    beList
 * Description: Convert Python args to nvlist pairs and call libbe:be_list
 *              to gather information about Boot Environments
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the BE to list (optional)
 *
 * Returns a pointer to a python object:
 *      A list of Dictionaries containing all the Boot Environment information
 *      NULL - Failure
 * Scope:
 *      Public
 */

PyObject *
beList(PyObject *self, PyObject *args)
{
	char	*beName = NULL;
	be_node_list_t *list, *be;
	PyObject *dict = NULL;
	PyObject *listOfDicts = NULL;

	if (!PyArg_ParseTuple(args, "|z", &beName)) {
		return (NULL);
	}

	if (be_list(beName, &list) != 0) {
		be_free_list(list);
		return (Py_BuildValue("", NULL));
	}

	if ((listOfDicts = PyList_New(0)) == NULL) {
		return (Py_BuildValue("", NULL));
	}

	for (be = list; be != NULL; be = be->be_next_node) {
		be_dataset_list_t *ds = be->be_node_datasets;
		be_snapshot_list_t *ss = be->be_node_snapshots;

		if ((dict = PyDict_New()) == NULL) {
			goto cleanupFailure;
		}

		if (!convertBEInfoToDictionary(be, &dict)) {
			Py_DECREF(dict);
			goto cleanupFailure;
		}

		if (PyList_Append(listOfDicts, dict) != 0) {
			Py_DECREF(dict);
			goto cleanupFailure;
		}

		Py_DECREF(dict);

		while (ds != NULL) {
			if ((dict = PyDict_New()) == NULL) {
				goto cleanupFailure;
			}

			if (!convertDatasetInfoToDictionary(ds, &dict)) {
				Py_DECREF(dict);
				goto cleanupFailure;
			}

			if (PyList_Append(listOfDicts, dict) != 0) {
				Py_DECREF(dict);
				goto cleanupFailure;
			}

			ds = ds->be_next_dataset;

			Py_DECREF(dict);
		}


		while (ss != NULL) {
			if ((dict = PyDict_New()) == NULL) {
				Py_DECREF(dict);
				goto cleanupFailure;
			}

			if (!convertSnapshotInfoToDictionary(ss, &dict)) {
				Py_DECREF(dict);
				goto cleanupFailure;
			}

			if (PyList_Append(listOfDicts, dict) != 0) {
				Py_DECREF(dict);
				goto cleanupFailure;
			}

			ss = ss->be_next_snapshot;

			Py_DECREF(dict);
		}
	}

	be_free_list(list);

	return (Py_BuildValue("O", listOfDicts));

cleanupFailure:
	be_free_list(list);
	return (Py_BuildValue("", NULL));

}

/*
 * Function:    beActivate
 * Description: Convert Python args to nvlist pairs and call libbe:be_activate
 *              to activate a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the BE to activate
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beActivate(PyObject *self, PyObject *args)
{
	char		*beName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "z", &beName)) {
		return (Py_BuildValue("i", 1));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 2, BE_ATTR_ORIG_BE_NAME, beName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_activate(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beDestroy
 * Description: Convert Python args to nvlist pairs and call libbe:be_destroy
 *              to destroy a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the BE to destroy
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beDestroy(PyObject *self, PyObject *args)
{
	char		*beName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "z", &beName)) {
		return (NULL);
	}

	if (!convertPyArgsToNvlist(&beAttrs, 2, BE_ATTR_ORIG_BE_NAME, beName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_destroy(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beDestroySnapshot
 * Description: Convert Python args to nvlist pairs and call libbe:be_destroy
 *              to destroy a snapshot of a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the BE to destroy
 *     snapName - The name of the snapshot to destroy
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beDestroySnapshot(PyObject *self, PyObject *args)
{
	char		*beName = NULL;
	char		*snapName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "zz", &beName, &snapName)) {
		return (NULL);
	}

	if (!convertPyArgsToNvlist(&beAttrs, 4,
	    BE_ATTR_ORIG_BE_NAME, beName,
	    BE_ATTR_SNAP_NAME, snapName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_destroy_snapshot(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beRename
 * Description: Convert Python args to nvlist pairs and call libbe:be_rename
 *              to rename a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     oldBeName - The name of the old Boot Environment
 *     newBeName - The name of the new Boot Environment
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beRename(PyObject *self, PyObject *args)
{
	char		*oldBeName = NULL;
	char		*newBeName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "zz", &oldBeName, &newBeName)) {
		return (Py_BuildValue("i", 1));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 4,
	    BE_ATTR_ORIG_BE_NAME, oldBeName,
	    BE_ATTR_NEW_BE_NAME, newBeName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_rename(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beMount
 * Description: Convert Python args to nvlist pairs and call libbe:be_mount
 *              to mount a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the Boot Environment to mount
 *     mountpoint - The path of the mountpoint to mount the
 *                  Boot Environment on (optional)
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beMount(PyObject *self, PyObject *args)
{
	char *beName = NULL;
	char *mountpoint = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "zz", &beName, &mountpoint)) {
		return (Py_BuildValue("i", 1));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 4,
	    BE_ATTR_ORIG_BE_NAME, beName,
	    BE_ATTR_MOUNTPOINT, mountpoint)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_mount(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beUnmount
 * Description: Convert Python args to nvlist pairs and call libbe:be_unmount
 *              to unmount a Boot Environment
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the Boot Environment to unmount
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beUnmount(PyObject *self, PyObject *args)
{
	char 		*beName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "z", &beName)) {
		return (Py_BuildValue("i", 1));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 2,
	    BE_ATTR_ORIG_BE_NAME, beName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_unmount(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/*
 * Function:    beRollback
 * Description: Convert Python args to nvlist pairs and call libbe:be_rollback
 *              to rollback a Boot Environment to a previously taken
 *               snapshot.
 * Parameters:
 *   args -     pointer to a python object containing:
 *     beName - The name of the Boot Environment to unmount
 *
 * Returns a pointer to a python object:
 *      0 - Success
 *      1 - Failure
 * Scope:
 *      Public
 */

PyObject *
beRollback(PyObject *self, PyObject *args)
{

	char	*beName = NULL;
	char	*snapName = NULL;
	nvlist_t	*beAttrs = NULL;
	PyObject	*intObj = NULL;

	if (!PyArg_ParseTuple(args, "zz", &beName, &snapName)) {
		return (Py_BuildValue("i", NULL));
	}

	if (!convertPyArgsToNvlist(&beAttrs, 4,
	    BE_ATTR_ORIG_BE_NAME, beName,
	    BE_ATTR_SNAP_NAME, snapName)) {
		nvlist_free(beAttrs);
		return (Py_BuildValue("i", 1));
	}

	if (beAttrs != NULL) {
		intObj = Py_BuildValue("i", be_rollback(beAttrs));
		nvlist_free(beAttrs);
		return (intObj);
	}

	return (Py_BuildValue("i", 1));
}

/* ~~~~~~~~~~~~~~~~~ */
/* Private Functions */
/* ~~~~~~~~~~~~~~~~~ */

static boolean_t
convertBEInfoToDictionary(be_node_list_t *be, PyObject **listDict)
{
	if (be->be_node_name != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_ORIG_BE_NAME,
		    PyString_FromString(be->be_node_name)) != 0) {
			return (B_FALSE);
		}
	}

	if (be->be_rpool != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_ORIG_BE_POOL,
		    PyString_FromString(be->be_rpool)) != 0) {
			return (B_FALSE);
		}
	}

	if (be->be_mntpt != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_MOUNTPOINT,
		    PyString_FromString(be->be_mntpt)) != 0) {
			return (B_FALSE);
		}
	}

	if (PyDict_SetItemString(*listDict, BE_ATTR_MOUNTED,
	    (be->be_mounted ? Py_True : Py_False)) != 0) {
		return (B_FALSE);
	}

	if (PyDict_SetItemString(*listDict, BE_ATTR_ACTIVE,
	    (be->be_active ? Py_True : Py_False)) != 0) {
		return (B_FALSE);
	}

	if (PyDict_SetItemString(*listDict, BE_ATTR_ACTIVE_ON_BOOT,
	    (be->be_active_on_boot ? Py_True : Py_False)) != 0) {
		return (B_FALSE);
	}

	if (be->be_space_used != 0) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_SPACE,
		    PyLong_FromUnsignedLongLong(be->be_space_used)) != 0) {
			return (B_FALSE);
		}
	}

	return (B_TRUE);
}

static boolean_t
convertDatasetInfoToDictionary(be_dataset_list_t *ds, PyObject **listDict)
{
	if (ds->be_dataset_name != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_DATASET,
		    PyString_FromString(ds->be_dataset_name)) != 0) {
			return (B_FALSE);
		}
	}

	if (PyDict_SetItemString(*listDict, BE_ATTR_STATUS,
	    (ds->be_ds_mounted ? Py_True : Py_False)) != 0) {
			return (B_FALSE);
	}

	if (ds->be_ds_mntpt != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_MOUNTPOINT,
		    PyString_FromString(ds->be_ds_mntpt)) != 0) {
			return (B_FALSE);
		}
	}

	if (ds->be_ds_space_used != 0) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_SPACE,
		    PyLong_FromUnsignedLongLong(ds->be_ds_space_used))
			    != 0) {
			return (B_FALSE);
		}
	}

	return (B_TRUE);
}

static boolean_t
convertSnapshotInfoToDictionary(be_snapshot_list_t *ss, PyObject **listDict)
{
	if (ss->be_snapshot_name != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_SNAP_NAME,
		    PyString_FromString(ss->be_snapshot_name)) != 0) {
			return (B_FALSE);
		}
	}

	if (ss->be_snapshot_creation != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_DATE,
		    PyLong_FromLong(ss->be_snapshot_creation)) != 0) {
			return (B_FALSE);
		}
	}

	if (ss->be_snapshot_type != NULL) {
		if (PyDict_SetItemString(*listDict, BE_ATTR_POLICY,
			PyString_FromString(ss->be_snapshot_type)) != 0) {
			return (B_FALSE);
		}
	}

	return (B_TRUE);
}

/*
 * Convert string arguments to nvlist attributes
 */

static boolean_t
convertPyArgsToNvlist(nvlist_t **nvList, int numArgs, ...)
{
	char *pt, *pt2;
	va_list ap;
	int i;

	if (*nvList == NULL) {
		if (nvlist_alloc(nvList, NV_UNIQUE_NAME, 0) != 0) {
			printf("nvlist_alloc failed.\n");
			return (B_FALSE);
		}
	}

	va_start(ap, numArgs);

	for (i = 0; i < numArgs; i += 2) {
	    if ((pt = va_arg(ap, char *)) == NULL ||
		    (pt2 = va_arg(ap, char *)) == NULL) {
			continue;
		}
		if (nvlist_add_string(*nvList, pt, pt2) != 0) {
			printf("nvlist_add_string failed for %s (%s).\n",
			    pt, pt2);
			nvlist_free(*nvList);
			return (B_FALSE);
		}
	}

	va_end(ap);

	return (B_TRUE);
}

/* Private python initialization structure */

static struct PyMethodDef libbeMethods[] = {
	{"beCopy", (PyCFunction)beCopy, METH_VARARGS, "Create/Copy a BE."},
	{"beCreateSnapshot", (PyCFunction)beCreateSnapshot, METH_VARARGS,
	    "Create a snapshot."},
	{"beDestroy", (PyCFunction)beDestroy, METH_VARARGS, "Destroy a BE."},
	{"beDestroySnapshot", (PyCFunction)beDestroySnapshot, METH_VARARGS,
	    "Destroy a snapshot."},
	{"beMount", (PyCFunction)beMount, METH_VARARGS, "Mount a BE."},
	{"beUnmount", (PyCFunction)beUnmount, METH_VARARGS, "Unmount a BE."},
	{"beList", (PyCFunction)beList, METH_VARARGS, "List BE info."},
	{"beRename", (PyCFunction)beRename, METH_VARARGS, "Rename a BE."},
	{"beActivate", (PyCFunction)beActivate, METH_VARARGS, "Activate a BE."},
	{"beRollback", (PyCFunction)beRollback, METH_VARARGS, "Activate a BE."},
	{NULL, NULL, 0, NULL}
};

void
initlibbe()
{
	/* PyMODINIT_FUNC; */
	(void) Py_InitModule("libbe", libbeMethods);
}
