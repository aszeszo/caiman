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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */
#include <Python.h>
#include <libnvpair.h>
#include <ti_api.h>
#include <sys/types.h>

static PyObject	*py_ti_create_target(PyObject *self, PyObject *args);
static PyObject	*py_ti_release_target(PyObject *self, PyObject *args);
static int ti_setup_nvlist(nvlist_t *attrs, PyObject *ti_properties);

/*
 * Create the method table that translates the method called
 * by the python program (ex. ti_create_target) to the associated
 * c function (ex. py_ti_create_target)
 */
static	PyMethodDef libtiMethods[] = {
	{"ti_create_target", py_ti_create_target, METH_VARARGS,
	"Create a target"},
	{"ti_release_target", py_ti_release_target, METH_VARARGS,
	"Release a target"},
	{NULL, NULL, 0, NULL} };

struct attr_node {
	char		*attribute;
	data_type_t	type;
};

/*
 * The attr_table is used in the bsearch, thus it must
 * be kept sorted for proper functionality.
 */
static struct attr_node attr_table[] = {
	{TI_ATTR_BE_FS_NAMES, DATA_TYPE_STRING_ARRAY},
	{TI_ATTR_BE_FS_NUM, DATA_TYPE_UINT16},
	{TI_ATTR_BE_MOUNTPOINT, DATA_TYPE_STRING},
	{TI_ATTR_BE_NAME, DATA_TYPE_STRING},
	{TI_ATTR_BE_RPOOL_NAME, DATA_TYPE_STRING},
	{TI_ATTR_BE_SHARED_FS_NAMES, DATA_TYPE_STRING_ARRAY},
	{TI_ATTR_BE_SHARED_FS_NUM, DATA_TYPE_UINT16},
	{TI_ATTR_DC_RAMDISK_BOOTARCH_NAME, DATA_TYPE_STRING},
	{TI_ATTR_DC_RAMDISK_BYTES_PER_INODE, DATA_TYPE_UINT32},
	{TI_ATTR_DC_RAMDISK_DEST, DATA_TYPE_STRING},
	{TI_ATTR_DC_RAMDISK_FS_TYPE, DATA_TYPE_UINT16},
	{TI_ATTR_DC_RAMDISK_SIZE, DATA_TYPE_UINT32},
	{TI_ATTR_DC_UFS_DEST, DATA_TYPE_STRING},
	{TI_ATTR_FDISK_DISK_NAME, DATA_TYPE_STRING},
	{TI_ATTR_FDISK_PART_ACTIVE, DATA_TYPE_UINT8_ARRAY},
	{TI_ATTR_FDISK_PART_BCYLS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_BHEADS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_BSECTS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_ECYLS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_EHEADS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_ESECTS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_IDS, DATA_TYPE_UINT8_ARRAY},
	{TI_ATTR_FDISK_PART_NUM, DATA_TYPE_UINT16},
	{TI_ATTR_FDISK_PART_NUMSECTS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_PART_PRESERVE, DATA_TYPE_BOOLEAN_ARRAY},
	{TI_ATTR_FDISK_PART_RSECTS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_FDISK_WDISK_FL, DATA_TYPE_BOOLEAN},
	{TI_ATTR_SLICE_DEFAULT_LAYOUT, DATA_TYPE_BOOLEAN},
	{TI_ATTR_SLICE_DISK_NAME, DATA_TYPE_STRING},
	{TI_ATTR_SLICE_FLAGS, DATA_TYPE_UINT16_ARRAY},
	{TI_ATTR_SLICE_NUM, DATA_TYPE_UINT16},
	{TI_ATTR_SLICE_PARTS, DATA_TYPE_UINT16_ARRAY},
	{TI_ATTR_SLICE_SIZES, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_SLICE_TAGS, DATA_TYPE_UINT16_ARRAY},
	{TI_ATTR_SLICE_1STSECS, DATA_TYPE_UINT64_ARRAY},
	{TI_ATTR_TARGET_TYPE, DATA_TYPE_UINT32},
	{TI_ATTR_ZFS_FS_NAMES, DATA_TYPE_STRING_ARRAY},
	{TI_ATTR_ZFS_FS_NUM, DATA_TYPE_UINT16},
	{TI_ATTR_ZFS_FS_POOL_NAME, DATA_TYPE_STRING},
	{TI_ATTR_ZFS_PROP_NAMES, DATA_TYPE_STRING_ARRAY},
	{TI_ATTR_ZFS_PROP_VALUES, DATA_TYPE_STRING_ARRAY},
	{TI_ATTR_ZFS_PROPERTIES, DATA_TYPE_NVLIST_ARRAY},
	{TI_ATTR_ZFS_RPOOL_DEVICE, DATA_TYPE_STRING},
	{TI_ATTR_ZFS_RPOOL_NAME, DATA_TYPE_STRING},
	{TI_ATTR_ZFS_RPOOL_PRESERVE, DATA_TYPE_BOOLEAN},
	{TI_ATTR_ZFS_VOL_NUM, DATA_TYPE_UINT16}
};

/*
 * Initialize libti module.
 */
PyMODINIT_FUNC
initlibti(void)
{
	(void) Py_InitModule("libti", libtiMethods);
}

/*
 * add_uint8_array
 * Add a uint8_array into the nvlist
 * Arguments: attrs - nvlist_t to put the uint8 array into
 *	      attribute - the name of the nvlist
 *            pvalue - list of uint8_ts
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_uint8_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	uint8_t		*val_array;
	Py_ssize_t	len, index;

	/*
	 * Find out how big the list of uint8_ts is.
	 */
	len = PyList_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}

	/*
	 * malloc the array accoringly
	 */
	val_array = malloc(len * sizeof (uint8_t));
	if (val_array == NULL) {
		return (B_FALSE);
	}

	/*
	 * Get each uint8_t in the list, convert from PyObject
	 * to uint8_t and put into the array.
	 */
	for (index = 0; index < len; index++) {
		val_array[index] = (uint8_t)PyInt_AsLong(
		    PyList_GetItem(pvalue, index));
	}

	/*
	 * and place the array into the nvlist
	 */
	if (nvlist_add_uint8_array(attrs, attribute, val_array, len) != 0) {
		free(val_array);
		return (B_FALSE);
	}
	free(val_array);
	return (B_TRUE);
}

/*
 * add_uint16_array
 * Add a uint16_array into the nvlist
 * Arguments: attrs - nvlist_t to put the uint16 array into
 *	      attribute - the name of the nvlist
 *            pvalue - list of uint16_ts
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_uint16_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	uint16_t	*val_array;
	Py_ssize_t	len, index;

	/*
	 * Find out how big the list of uint16_ts is.
	 */
	len = PyList_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}


	/*
	 * malloc the array accoringly
	 */
	val_array = malloc(len * sizeof (uint16_t));
	if (val_array == NULL) {
		return (B_FALSE);
	}


	/*
	 * Get each uint16_t in the list, convert from PyObject
	 * to uint16_t and put into the array.
	 */
	for (index = 0; index < len; index++) {
		val_array[index] = (uint16_t)PyInt_AsLong(
		    PyList_GetItem(pvalue, index));
	}

	/*
	 * and place the array into the nvlist
	 */
	if (nvlist_add_uint16_array(attrs, attribute, val_array, len) != 0) {
		free(val_array);
		return (B_FALSE);
	}
	free(val_array);
	return (B_TRUE);
}

/*
 * add_uint64_array
 * Add a uint64_array into the nvlist
 * Arguments: attrs - nvlist_t to put the uint64 array into
 *	      attribute - the name of the nvlist
 *            pvalue - list of uint64_ts
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_uint64_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	uint64_t	*val_array;
	Py_ssize_t	len, index;

	/*
	 * Find out how big the list of uint64_TS IS.
	 */
	len = PyList_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}

	/*
	 * malloc the array accoringly
	 */
	val_array = malloc(len * sizeof (uint64_t));
	if (val_array == NULL) {
		return (B_FALSE);
	}


	/*
	 * Get each uint64_t in the list, convert from PyObject
	 * to uint64_t and put into the array.
	 */
	for (index = 0; index < len; index++) {
		val_array[index] = (uint64_t)PyLong_AsUnsignedLong(
		    PyList_GetItem(pvalue, index));
	}

	/*
	 * and place the array into the nvlist
	 */
	if (nvlist_add_uint64_array(attrs, attribute,
	    val_array, len) != 0) {
		free(val_array);
		return (B_FALSE);
	}
	free(val_array);
	return (B_TRUE);
}

/*
 * add_boolean_array
 * Add a boolean_array into the nvlist
 * Arguments: attrs - nvlist_t to put the boolean array into
 *	      attribute - the name of the nvlist
 *	      pvalue - list of booleans
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_boolean_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	boolean_t	*val_array;
	Py_ssize_t	len, index;

	/*
	 * Find out how big the list of booleans is.
	 */
	len = PyList_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}


	/*
	 * malloc the array accoringly
	 */
	val_array = malloc(len * sizeof (boolean_t));
	if (val_array == NULL) {
		return (B_FALSE);
	}


	/*
	 * Get each boolean in the list, convert from PyObject
	 * to boolean and put into the array.
	 */
	for (index = 0; index < len; index++) {
		if (PyList_GetItem(pvalue, index) == Py_True)
			val_array[index] = B_TRUE;
		else
			val_array[index] = B_FALSE;
	}

	/*
	 * and place the array into the nvlist
	 */
	if (nvlist_add_boolean_array(attrs, attribute,
	    val_array, len) != 0) {
		free(val_array);
		return (B_FALSE);
	}
	free(val_array);
	return (B_TRUE);
}

/*
 * add_string_array
 * Add a string_array into the nvlist
 * Arguments: attrs - nvlist_t to put the string array into
 *	      attribute - the name of the nvlist
 *            pvalue - list of strings
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_string_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	char	**val_array;
	char	*value;
	Py_ssize_t	len, index;


	/*
	 * Find out how big the list of strings is.
	 */
	len = PyList_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}

	/*
	 * malloc the array accoringly
	 */
	val_array = malloc(len * sizeof (char *));
	if (val_array == NULL) {
		return (B_FALSE);
	}


	/*
	 * Get each string in the list, convert from PyObject
	 * to string and put into the array.
	 */
	for (index = 0; index < len; index++) {
		value = PyString_AsString(
		    PyList_GetItem(pvalue, index));
		val_array[index] = value;
	}

	/*
	 * and place the array into the nvlist
	 */
	if (nvlist_add_string_array(attrs, attribute,
	    val_array, len) != 0) {
		free(val_array);
		return (B_FALSE);
	}
	free(val_array);
	return (B_TRUE);
}

/*
 * add_nvlist_array
 * Add a nvlist_array into the nvlist
 * Arguments: attrs - nvlist_t to put the nvlist array into
 *	      attribute - the name of the nvlist
 *            pvalue - list of nvlist_ts
 * Returns: B_TRUE on success
 *          B_FALSE on failure
 */
static boolean_t
add_nvlist_array(nvlist_t *attrs, char *attribute, PyObject *pvalue)
{
	nvlist_t	*fs_attrs;
	nvlist_t	**val_array;
	PyObject	*list_obj;
	Py_ssize_t	len, index, i;
	int		ret = B_TRUE;

	/*
	 * Find out how big the list of nvlists is.
	 */
	len = PyTuple_Size(pvalue);
	if (len <= 0) {
		return (B_FALSE);
	}


	/*
	 * malloc the array accordingly
	 */
	val_array = malloc(len * sizeof (nvlist_t *));
	if (val_array == NULL) {
		return (B_FALSE);
	}

	/*
	 * Get each nvlist in the list, convert from PyObject
	 * to nvlist and put into the array.
	 */
	for (index = 0; index < len; index++) {
		/*
		 * Get the list
		 */
		list_obj = PyTuple_GetItem(pvalue, index);
		if (list_obj == NULL) {
			ret = B_FALSE;
			goto done;
		}

		if (nvlist_alloc(&fs_attrs, NV_UNIQUE_NAME, 0)) {
			ret = B_FALSE;
			goto done;
		}

		if ((ti_setup_nvlist(fs_attrs, list_obj)) != TI_E_SUCCESS) {
			nvlist_free(fs_attrs);
			ret = B_FALSE;
			goto done;
		}

		/*
		 * And add the nvlist to the array of nvlists
		 */
		val_array[index] = fs_attrs;
	}

	/*
	 * Add the array of nvlists to the nvlist
	 */
	if (nvlist_add_nvlist_array(attrs, attribute, val_array, len)) {
		ret = B_FALSE;
		goto done;
	}

done:
	for (i = 0; i < index; i++) {
		nvlist_free(val_array[i]);
	}
	free(val_array);
	return (ret);
}


/*
 * attr_compare
 * function used by the bsearch to compare the string
 * field in the nodes.
 */
static int
attr_compare(const void *attr1, const void *attr2)
{
	return (strcmp(((const struct attr_node *)attr1)->attribute,
	    ((const struct attr_node *)attr2)->attribute));
}

/*
 * ti_setup_nvlist
 * This will place the python args into the C nvlist
 */
int
ti_setup_nvlist(nvlist_t *attrs, PyObject *ti_properties)
{
	PyObject	*pkey = NULL;
	PyObject	*pvalue = NULL;
	int		pos = 0;
	boolean_t	value;
	struct attr_node	*node_ptr, node;

	/*
	 * Loop through the list pulling out key (name) value pairs
	 * for each entry in the list.
	 */
	while (PyDict_Next(ti_properties, &pos, &pkey, &pvalue)) {
		node.attribute = PyString_AsString(pkey);

		node_ptr = bsearch(&node, attr_table,
		    sizeof (attr_table) / sizeof (struct attr_node),
		    sizeof (struct attr_node), attr_compare);

		if (node_ptr == NULL)
			return (TI_E_PY_INVALID_ARG);

		switch (node_ptr->type) {
			case DATA_TYPE_UINT32:
				/*
				 * Place the uint32 properties into the nvlist
				 */
				if (nvlist_add_uint32(attrs,
				    node.attribute, (uint32_t)PyInt_AsLong(
				    pvalue)) != 0) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_STRING:
				/*
				 * Place the string properties into the nvlist
				 */
				if (nvlist_add_string(attrs, node.attribute,
				    PyString_AsString(pvalue)) != 0) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_UINT16:
				/*
				 * Place the uint 16 properties into the nvlist
				 */
				if (nvlist_add_uint16(attrs, node.attribute,
				    (uint16_t)PyInt_AsLong(pvalue)) != 0) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_BOOLEAN:
				/*
				 * Place the boolean properties into the nvlist
				 */
				if (pvalue == Py_True)
					value = B_TRUE;
				else
					value = B_FALSE;
				if (nvlist_add_boolean_value(attrs,
				    node.attribute, value) != 0) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_UINT8_ARRAY:
				if (!add_uint8_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_UINT16_ARRAY:
				if (!add_uint16_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_UINT64_ARRAY:
				if (!add_uint64_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_BOOLEAN_ARRAY:
				if (!add_boolean_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_STRING_ARRAY:
				if (!add_string_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			case DATA_TYPE_NVLIST_ARRAY:
				if (!add_nvlist_array(attrs, node.attribute,
				    pvalue)) {
					return (TI_E_PY_INVALID_ARG);
				}
				break;
			default:
				return (TI_E_PY_INVALID_ARG);
				break;
		}
	}
	return (TI_E_SUCCESS);
}

/*
 * py_ti_create_target
 * Main function. This is the wrapper for a python function to call the
 * C function, ti_create_target.
 */
/* ARGSUSED */
static PyObject *
py_ti_create_target(PyObject *self, PyObject *args)
{
	int		ret;
	nvlist_t	*attrs;
	PyObject	*ti_properties;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "O", &ti_properties)) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if (ti_properties == NULL) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if (nvlist_alloc(&attrs, NV_UNIQUE_NAME, 0) != 0) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if ((ret = ti_setup_nvlist(attrs, ti_properties)) != TI_E_SUCCESS) {
		nvlist_free(attrs);
		return (Py_BuildValue("i", ret));
	}


	ret = ti_create_target(attrs, NULL);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		return (Py_BuildValue("i", ret));
	}

	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}

/*
 * py_ti_release_target
 * Main function. This is the wrapper for a python function to call the
 * C function, ti_release_target.
 */
/* ARGSUSED */
static PyObject *
py_ti_release_target(PyObject *self, PyObject *args)
{
	int		ret;
	nvlist_t	*attrs;
	PyObject	*ti_properties;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "O", &ti_properties)) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if (ti_properties == NULL) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if (nvlist_alloc(&attrs, NV_UNIQUE_NAME, 0) != 0) {
		return (Py_BuildValue("i", TI_E_PY_INVALID_ARG));
	}

	if ((ret = ti_setup_nvlist(attrs, ti_properties)) != TI_E_SUCCESS) {
		nvlist_free(attrs);
		return (Py_BuildValue("i", ret));
	}

	ret = ti_release_target(attrs);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		return (Py_BuildValue("i", ret));
	}

	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}
