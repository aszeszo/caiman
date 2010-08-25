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
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 */

#include "Python.h"	/* Must be the first header file. */
#include <alloca.h>
#include <libintl.h>
#include <strings.h>
#include <auto_install.h>

/* Python DDU function module related definitions. */
#define	DDU_FUNCTION_MODULE	"DDU.ddu_function"
#define	DDU_PACKAGE_LOOKUP	"ddu_package_lookup"
#define	DDU_INSTALL_PACKAGE	"ddu_install_package"
#define	DDU_DEVSCAN		"ddu_devscan"
#define	DDU_BUILD_REPO_LIST	"ddu_build_repo_list"

/* Python DDU package module related definitions. */
#define	DDU_PACKAGE_MODULE	"DDU.ddu_package"
#define	DDU_PACKAGE_OBJECT	"ddu_package_object"

/* Pkg commands. */
#define	PKG_PUBLISHER		"/usr/bin/pkg publisher"

/* DDU error log */
#define	DDU_ERRLOG		"/tmp/ddu_err.log"

/*  DDU error module related. */
#define	DDU_ERROR_MODULE		"DDU.ddu_errors"
#define	DDU_PACKAGE_NOT_FOUND_EXC	"PackageNoFound"

/* ICT module related definitions. */
#define	ICT_MODULE		"osol_install.ict"
#define	ICT_CLASS		"ICT"
#define	ICT_UPDATE_ARCHIVE	"update_boot_archive"

/* AI Manifest (AIM) related path definitions. */
#define	AIM_PREFACE		"auto_install/ai_instance/add_drivers/"
#define	PKGSPEC_NODEPATH	"software"
#define	ORIGIN_NODEPATH		"software/source/publisher/origin/name"
#define	TYPE_NODEPATH		"software[source/publisher/origin/" \
				    "name=\"%s\"]/software_data/type"
#define	NAME_NODEPATH		"software[source/publisher/origin/" \
				    "name=\"%s\":software_data/" \
				    "type=\"%s\"]/software_data/name"
#define	ACTION_NONAME_NODEPATH \
				"software[source/publisher/origin/" \
				    "name=\"%s\":software_data/" \
				    "type=\"%s\"]/software_data/action"
#define	ACTION_YESNAME_NODEPATH \
				"software[source/publisher/origin/" \
				    "name=\"%s\":software_data/type=\"%s\":" \
				    "software_data/name=\"%s\"]/" \
				    "software_data/action"

#define	SEARCH_NODEPATH		"search_all"
#define	SEARCH_ORIGIN_NODEPATH	"search_all/source/publisher/origin/name"
#define	SEARCH_PUBNAME_NODEPATH	"search_all/source/publisher/name"
#define	SEARCH_ADDALL_NODEPATH	"search_all/addall"

#define	MAX_NODEPATH_SIZE	256

typedef struct {
	PyThreadState *myThreadState;
	PyThreadState *mainThreadState;
	PyObject *pFunctionModule;
	PyObject *pPackageModule;
	PyObject *pErrorModule;
	PyObject *pICTModule;
} py_state_t;

typedef struct {
	char path_str[MAX_NODEPATH_SIZE];
	char *post_prefix_start;
	int post_prefix_len;
} path_t;

static py_state_t *auto_ddu_lib_init();
static void auto_ddu_lib_fini(py_state_t *py_state_p);
static void ai_dump_python_exception();
static PyObject *ai_call_ddu_devscan(py_state_t *py_state_p,
    boolean_t get_only_missing_drivers, char *dev_type);
static int ai_call_ddu_package_lookup(py_state_t *py_state_p,
    PyObject *pDevObj, PyObject *pRepoList, PyObject **pPackageObj_p);
static int ai_call_ddu_install_package(py_state_t *py_state_p,
    PyObject *ddu_package_obj, char *install_root, boolean_t third_party_ok);
static PyObject *ai_new_ddu_package_object(py_state_t *py_state_p,
    char *type, char *name, char *origin);
static int ai_get_ddu_package_object_values(PyObject *pDDUPackageObject,
    char **type, char **location, char **name, char **descr, char **inf_link,
    boolean_t *third_party);
static int ai_get_ddu_dev_data_values(PyObject *pDDUDevData,
    char **dev_type_p, char **descr_p, char **vendor_ID_p, char **device_ID_p,
    char **class_p);
static int ai_du_process_manual_pkg(py_state_t *py_state_p,
    PyObject *pPackageList, char *origin, char *type, char *name,
    char *noinstall);
static int ai_du_process_manual_pkg_names(py_state_t *py_state_p,
    path_t *path_p, PyObject *pPackageList, char *origin, char *type,
    char *name);
static int ai_du_process_manual_pkg_types(py_state_t *py_state_p,
    PyObject *pPackageList, path_t *path_p, char *origin, char *type);
static int ai_du_get_manual_pkg_list(py_state_t *py_state_p, path_t *path_p,
    PyObject **pPackageList_p);
static int ai_du_get_searched_pkg_list(py_state_t *py_state_p, path_t *path_p,
    char *install_root, PyObject **pPackageList_p);
static int ai_du_install_packages(py_state_t *py_state_p,
    PyObject *pPkgTupleList, char *install_root, boolean_t honor_noinstall,
    int *num_installed_pkgs_p);
static char **ai_uniq_manifest_values(char **in, int *len_p);
static int ai_du_call_update_archive_ict(py_state_t *py_state_p,
    char *install_root);

/*
 * Stores the list of packages set up by ai_du_get_and_install() for use by
 * ai_du_install().
 */
static PyObject *py_pkg_list;

static char *empty_string = "";

/* Private functions. */

/*
 * auto_ddu_lib_init:
 * Initialize they python interpreter state so that python functions can be
 * called from this module.  Initialize a few common things always used.
 *
 * Arguments: None
 *
 * Returns:
 *   Success: A pointer to an initialized py_state_t object
 *   Failure: NULL
 *
 * Note: Call auto_ddu_lib_fini(), passing it the item returned from this
 * function, to undo the effects of this function.
 */
static py_state_t *
auto_ddu_lib_init()
{
	py_state_t *py_state_p = malloc(sizeof (py_state_t));

	static PyObject *pFunctionModule = NULL;
	static PyObject *pPackageModule = NULL;
	static PyObject *pErrorModule = NULL;
	static PyObject *pICTModule = NULL;

	if (py_state_p == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR, "auto_ddu_lib_init: "
		    "No memory.\n");
		return (NULL);
	}

	/* If one of the above is NULL, all will be NULL. */
	if (pFunctionModule == NULL) {
		PyObject *pName;

		/* Get names of modules for use by python/C interfaces. */
		if ((pName = PyString_FromString(DDU_FUNCTION_MODULE)) !=
		    NULL) {
			pFunctionModule = PyImport_Import(pName);
			Py_DECREF(pName);
		}
		if ((pName = PyString_FromString(DDU_PACKAGE_MODULE)) != NULL) {
			pPackageModule = PyImport_Import(pName);
			Py_DECREF(pName);
		}
		if ((pName = PyString_FromString(DDU_ERROR_MODULE)) != NULL) {
			pErrorModule = PyImport_Import(pName);
			Py_DECREF(pName);
		}
		if ((pName = PyString_FromString(ICT_MODULE)) != NULL) {
			pICTModule = PyImport_Import(pName);
			Py_DECREF(pName);
		}

		/* Cleanup and return NULL on error. */
		if ((pFunctionModule == NULL) || (pPackageModule == NULL) ||
		    (pErrorModule == NULL) || (pICTModule == NULL)) {
			auto_debug_print(AUTO_DBGLVL_ERR, "auto_ddu_lib_init: "
			    "error accessing DDU library or ICT modules.\n");
			PyErr_Print();
			Py_XDECREF(pFunctionModule);
			Py_XDECREF(pPackageModule);
			Py_XDECREF(pErrorModule);
			Py_XDECREF(pICTModule);
			pFunctionModule = pPackageModule = NULL;
			pErrorModule = pICTModule = NULL;
			free(py_state_p);
			return (NULL);
		}
	}

	/* Set up python interpreter state. */
	PyEval_InitThreads();
	py_state_p->mainThreadState = PyThreadState_Get();
	py_state_p->myThreadState =
	    PyThreadState_New(py_state_p->mainThreadState->interp);
	(void) PyThreadState_Swap(py_state_p->myThreadState);

	py_state_p->pFunctionModule = pFunctionModule;
	py_state_p->pPackageModule = pPackageModule;
	py_state_p->pErrorModule = pErrorModule;
	py_state_p->pICTModule = pICTModule;

	return (py_state_p);
}

/*
 * auto_ddu_lib_fini:
 * Undo initialization of python interpreter state set up by
 * auto_ddu_lib_init().
 *
 * Arguments: A pointer to an initialized py_state_t object
 *
 * Returns: N/A
 */
static void
auto_ddu_lib_fini(py_state_t *py_state_p)
{
	if (py_state_p == NULL) {
		return;
	}
	(void) PyThreadState_Swap(py_state_p->mainThreadState);
	PyThreadState_Clear(py_state_p->myThreadState);
	PyThreadState_Delete(py_state_p->myThreadState);
	free(py_state_p);
}

/*
 * ai_dump_python_exception:
 * Dump the class and message of a python exception.  Traceback not dumped.
 *
 * Caveat: An exception must be ready to be dumped, as indicated by
 * PyErr_Occurred() * returning Non-NULL.
 *
 * Arguments: None
 *
 * Returns: N/A
 */
static void
ai_dump_python_exception()
{
	PyObject *pType, *pValue, *pTraceback;
	PyObject *pTypeString, *pValueString;

	if (PyErr_Occurred() == NULL) {
		return;
	}

	PyErr_Fetch(&pType, &pValue, &pTraceback);
	pTypeString = PyObject_Str(pType);
	pValueString = PyObject_Str(pValue);
	auto_debug_print(AUTO_DBGLVL_ERR,
	    "%s\n", PyString_AsString(pTypeString));
	auto_debug_print(AUTO_DBGLVL_ERR,
	    "%s\n", PyString_AsString(pValueString));
	Py_DECREF(pType);
	Py_DECREF(pValue);
	Py_DECREF(pTraceback);
	Py_DECREF(pTypeString);
	Py_DECREF(pValueString);
	PyErr_Clear();
}

/*
 * ai_call_ddu_build_repo_list:
 * Call the DDU library ddu_build_repo_list function.  This sets up the
 * list of repositories specified (as name/URL tuples) in the second argument,
 * and returns a python list of ddu_repo_objects for use by ddu_package_lookup.
 *
 * Arguments:
 *   py_state: Initialized py_state_t object.
 *   pRepoTypleList: List of (pubname, URL) tuples, each tuple representing
 *	a repository.
 *
 * Returns:
 *   Success: A python object representing a list of ddu_repo_objects.
 *   Failure: NULL
 */
static PyObject *
ai_call_ddu_build_repo_list(py_state_t *py_state_p, PyObject *pRepoTupleList)
{
	PyObject *pRet = NULL;

	/* Find the function */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pFunctionModule,
	    DDU_BUILD_REPO_LIST);

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Function not callable: %s\n", DDU_BUILD_REPO_LIST);
	} else {
		PyObject *pArgs = PyTuple_New(1);

		/*
		 * INCREF here since PyTuple_SetItem steals the reference, and
		 * can decrement the refcount when pArgs is DECREFed.
		 */
		Py_INCREF(pRepoTupleList);

		/* Set up args to python function and call it. */
		(void) PyTuple_SetItem(pArgs, 0, pRepoTupleList);
		pRet = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);

		if ((PyErr_Occurred() != NULL) || (pRet == NULL) ||
		    (pRet == Py_None)) {
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "%s returned an error.\n", DDU_BUILD_REPO_LIST);
			ai_dump_python_exception();
			Py_XDECREF(pRet);
			pRet = NULL;
		}
	}

	Py_XDECREF(pFunc);
	return (pRet);
}

/*
 * ai_call_ddu_devscan:
 * Call the DDU library ddu_devscan function.  This function performs a device
 * scan on the system, to find out which devices are missing drivers.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   get_only_missing_drivers: Boolean: when true, return only the list of
 *	devices which are missing drivers.  When false, return all devices.
 *   dev_type: Type of devices to scan for.  See the DDU library ddu_devscan()
 *	function for the list of device types.  "all" is an acceptable device
 *	type.
 *
 * Returns:
 *   Success:
 *	A python object representing a list of unique ddu_dev_data objects is
 *	returned.
 *	- NOTE: if no devices are missing drivers and get_only_missing_drivers
 *	  is true, then an empty list is returned.
 *	- A ddu_dev_data object represents a found device.
 *   Failure:
 *	NULL
 */
static PyObject *
ai_call_ddu_devscan(py_state_t *py_state_p,
    boolean_t get_only_missing_drivers, char *dev_type)
{
	PyObject *pRet = NULL;
	PyObject *pList = NULL;
	Py_ssize_t orig_listlen;
	char **vids, **dids, **classes;
	Py_ssize_t new_listused = 0;
	Py_ssize_t i, j;

	/* Find the function */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pFunctionModule,
	    DDU_DEVSCAN);

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Function not callable: %s\n", DDU_DEVSCAN);
		Py_XDECREF(pFunc);
		return (NULL);
	} else {
		/* Set up args to python function and call it. */
		PyObject *pArgs = PyTuple_New(2);
		(void) PyTuple_SetItem(pArgs, 0,
		    PyBool_FromLong((long)get_only_missing_drivers));
		(void) PyTuple_SetItem(pArgs, 1, PyString_FromString(dev_type));
		pList = PyObject_CallObject(pFunc, pArgs);

		Py_DECREF(pArgs);
		if ((PyErr_Occurred() != NULL) || (pList == NULL) ||
		    (pList == Py_None)) {
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "%s returned an error.\n", DDU_DEVSCAN);
			ai_dump_python_exception();
			Py_XDECREF(pList);
			Py_XDECREF(pFunc);
			return (NULL);
		}
	}

	Py_XDECREF(pFunc);

	orig_listlen = PyList_Size(pList);
	if (orig_listlen < 2) {
		return (pList);
	}

	/* Check for duplicates. */
	vids = (char **)malloc(sizeof (char *) * orig_listlen);
	dids = (char **)malloc(sizeof (char *) * orig_listlen);
	classes = (char **)malloc(sizeof (char *) * orig_listlen);
	if ((vids == NULL) || (dids == NULL) || (classes == NULL)) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_call_ddu_devscan: No memory.\n");
		return (NULL);
	}

	/* Build a list of unique values to be returned. */
	pRet = PyList_New(0);

	/* Loop through the list. */
	for (i = 0; i < orig_listlen; i++) {
		PyObject *pDDUDevData = PyList_GetItem(pList, i);
		char *vendor_ID, *device_ID, *class;
		boolean_t dup;

		if (ai_get_ddu_dev_data_values(pDDUDevData, NULL, NULL,
		    &vendor_ID, &device_ID, &class) != AUTO_INSTALL_SUCCESS) {
			/* If can't compare, just allow it. */
			continue;
		}

		/* Check for matching vendor, device, class. */
		for (j = 0, dup = B_FALSE; j < new_listused; j++) {
			if ((strcmp(class, classes[j]) == 0) &&
			    (strcmp(device_ID, dids[j]) == 0) &&
			    (strcmp(vendor_ID, vids[j]) == 0)) {
				dup = B_TRUE;
				break;
			}
		}

		if (!dup) {
			(void) PyList_Append(pRet, pDDUDevData);
			vids[new_listused] = vendor_ID;
			dids[new_listused] = device_ID;
			classes[new_listused++] = class;
		}
	}

	free(vids);
	free(dids);
	free(classes);

	Py_XDECREF(pList);
	return (pRet);
}

/*
 * ai_call_ddu_package_lookup:
 * Call the DDU library ddu_package_lookup function.  Given a list of
 * repositories, this function attempts to find a pkg(5) package in one of the
 * repositories.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   pDevObj: A python ddu_dev_data object representing a device.
 *   pRepoList: A python list of ddu_repo_object objects.  This represents the
 *	list of repositories to search through for a driver package.
 *   pPackageObj_p: Pointer to the returned ddu_package_object.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: pPackageObj_p points to an object representing a
 *	package to install for the given device.
 *   AUTO_INSTALL_PKG_NOT_FOUND: No package was found to install for the given
 *	device.  pPackageObj_p set to NULL.
 *   AUTO_INSTALL_FAILURE: Corresponds to an error other than not finding the
 *	package to install for the given device.  pPackageObj_p set to NULL.
 */
static int
ai_call_ddu_package_lookup(py_state_t *py_state_p,
    PyObject *pDevObj, PyObject *pRepoList, PyObject **pPackageObj_p)
{
	int err = AUTO_INSTALL_SUCCESS;

	/* Find the function */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pFunctionModule,
	    DDU_PACKAGE_LOOKUP);

	*pPackageObj_p = NULL;

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Function not callable: %s\n", DDU_PACKAGE_LOOKUP);
	} else {
		/* Set up args to python function. */
		PyObject *pArgs = PyTuple_New(2);
		Py_INCREF(pDevObj);	/* PyTuple_SetItem steals reference. */
		Py_INCREF(pRepoList);	/* PyTuple_SetItem steals reference. */
		(void) PyTuple_SetItem(pArgs, 0, pDevObj);
		(void) PyTuple_SetItem(pArgs, 1, pRepoList);

		/* Call ddu_package_lookup() */
		*pPackageObj_p = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);
		if ((PyErr_Occurred() != NULL) || (*pPackageObj_p == NULL) ||
		    (*pPackageObj_p == Py_None)) {
			err = AUTO_INSTALL_FAILURE;
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "%s returned an error.\n", DDU_PACKAGE_LOOKUP);
			if (PyErr_Occurred() != NULL) {
				PyObject *pType, *pValue, *pTraceback;
				PyObject *pPkgNotFndExcObj =
				    PyObject_GetAttrString(
				    py_state_p->pErrorModule,
				    DDU_PACKAGE_NOT_FOUND_EXC);
				PyErr_Fetch(&pType, &pValue, &pTraceback);

				if (PyObject_IsSubclass(pType,
				    pPkgNotFndExcObj) == 1) {	/* 1 = match */
					err = AUTO_INSTALL_PKG_NOT_FND;
				}
				Py_DECREF(pType);
				Py_DECREF(pValue);
				Py_DECREF(pTraceback);
				Py_DECREF(pPkgNotFndExcObj);
				PyErr_Clear();
			}
			Py_XDECREF(*pPackageObj_p);
			*pPackageObj_p = NULL;

		} else {
			/*
			 * DDU can return a pPackageObj_p that has type unknown,
			 * no location and no inf_link.  Treat these as
			 * "package not found" as well.
			 */
			char *ttype = empty_string;
			char *tlocn = empty_string;
			char *tinf_link = empty_string;
			(void) ai_get_ddu_package_object_values(*pPackageObj_p,
			    &ttype, &tlocn, NULL, NULL, &tinf_link, NULL);
			if ((tlocn[0] == '\0') && (tinf_link[0] == '\0') &&
			    (strcmp(ttype, "UNK") == 0)) {
				err = AUTO_INSTALL_PKG_NOT_FND;
				Py_XDECREF(*pPackageObj_p);
				*pPackageObj_p = NULL;
			}
		}
	}

	Py_XDECREF(pFunc);
	return (err);
}

/*
 * ai_call_ddu_install_package:
 * Call the DDU library ddu_install_package function.  Install the package
 * represented by pDDUPackageObj under the tree or file system given by
 * install_root.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   pDDUPackageObj: A python ddu_package_object representing the package to
 *	install.
 *   install_root: The root of the directory tree or file system in which to
 *	install the package.
 *   third_party_ok: Boolean: When true, it is OK to download and install
 *	packages found at third-party websites (as opposed to pkg(5)
 *	repositories).
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: Package was successfully installed.
 *   AUTO_INSTALL_FAILURE: Package was not successfully installed.
 *
 * NOTE: check installer logfile for details of the failure.
 */
static int
ai_call_ddu_install_package(py_state_t *py_state_p,
    PyObject *pDDUPackageObj, char *install_root, boolean_t third_party_ok)
{
	int rval = AUTO_INSTALL_SUCCESS;

	/* Find the function */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pFunctionModule,
	    DDU_INSTALL_PACKAGE);

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Function not callable: %s\n", DDU_INSTALL_PACKAGE);
		rval = AUTO_INSTALL_FAILURE;

	} else {

		/* Set up args to python function. */
		PyObject *pArgs = PyTuple_New(3);
		Py_INCREF(pDDUPackageObj);	/* PyTuple_SetItem steals ref */
		(void) PyTuple_SetItem(pArgs, 0, pDDUPackageObj);
		(void) PyTuple_SetItem(pArgs, 1,
		    PyString_FromString(install_root));
		(void) PyTuple_SetItem(pArgs, 2,
		    PyBool_FromLong((long)third_party_ok));

		/* Call ddu_install_packages() */
		(void) PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);

		if (PyErr_Occurred() != NULL) {
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "%s returned an error\n", DDU_INSTALL_PACKAGE);
			ai_dump_python_exception();
			rval = AUTO_INSTALL_FAILURE;
		}
	}

	Py_XDECREF(pFunc);
	return (rval);
}

/*
 * ai_new_ddu_package_object:
 * Create a new ddu_package_object of given type, name and location.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   type: type of package.
 *   name: name of package. (Not used by all types of packages.)
 *   origin: directory of where package is located.
 *
 * Returns:
 *   Success: A new python ddu_package_object object of the given
 *	type/name/location.
 *   Failure: NULL
 */
static PyObject *
ai_new_ddu_package_object(py_state_t *py_state_p,
    char *type, char *name, char *origin)
/*
 * Construct and return a new python ddu_package_object based on arguments.
 * Assumes auto_ddu_lib_init() has been called.
 *
 * Success: Returns the new object.
 * Failure: NULL
 */
{
	PyObject *pRet = NULL;

	/* Find the function */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pPackageModule,
	    DDU_PACKAGE_OBJECT);

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ddu_package_object constructor not callable\n");
	} else {
		/* Set up args to python function. */
		PyObject *pArgs = PyTuple_New(3);
		(void) PyTuple_SetItem(pArgs, 0, PyString_FromString(type));
		(void) PyTuple_SetItem(pArgs, 1, PyString_FromString(name));
		(void) PyTuple_SetItem(pArgs, 2, PyString_FromString(origin));

		/* Call ddu_package_object constructor. */
		pRet = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);
		if ((PyErr_Occurred() != NULL) || (pRet == NULL) ||
		    (pRet == Py_None)) {
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ddu_package_object constructor failed\n");
			ai_dump_python_exception();
			Py_XDECREF(pRet);
			pRet = NULL;
		}
	}

	Py_XDECREF(pFunc);
	return (pRet);
}

/*
 * ai_get_ddu_package_object_values:
 * Return selected values from a given ddu_package_object.
 *
 * Values returned live on the python interpreter's heap, and should not be
 * modified or freed.  They live only as long as the python obj they come from.
 *
 * Note: implementation is tied to the fields of the python object.
 *
 * Arguments:
 *   pDDUPackageObject: Object to extract values from.  Assumed to be a
 *	ddu_package_object;  not verified.
 *   type: char string pointer returned filled in with "pkg_type" field.
 *	Not processed if NULL.
 *   location: char string pointer returned filled in with "pkg_location" field.
 *	Not processed if NULL.
 *   name: char string pointer returned filled in with "pkg_name" field.
 *	Not processed if NULL.
 *   descr: char string pointer returned filled in with "device_descriptor"
 *	field.  Not processed if NULL.
 *   inf_link: char string pointer returned filled in with "inf_link" field.
 *	Not processed if NULL.
 *   third_party: boolean pointer returned filled in with
 *	"third_party_from_search" field.  Not processed if NULL.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: when all requested fields are found and extracted.
 *   AUTO_INSTALL_FAILURE: when one or more fields could not be found or
 *	extracted.
 */
static int
ai_get_ddu_package_object_values(PyObject *pDDUPackageObject,
    char **type, char **location, char **name, char **descr, char **inf_link,
    boolean_t *third_party)
{
	PyObject *pValue;

	if (type != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject, "pkg_type");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object pkg_type field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*type = PyString_AsString(pValue);
	}

	if (location != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject,
		    "pkg_location");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object pkg_location field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*location = PyString_AsString(pValue);
	}

	if (name != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject, "pkg_name");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object pkg_name field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*name = PyString_AsString(pValue);
	}

	if (descr != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject,
		    "device_descriptor");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object device_descriptor field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*descr = PyString_AsString(pValue);
	}

	if (inf_link != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject, "inf_link");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object inf_link field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*inf_link = PyString_AsString(pValue);
	}

	if (third_party != NULL) {
		pValue = PyObject_GetAttrString(pDDUPackageObject,
		    "third_party_from_search");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_package_object_values: "
			    "no ddu_package_object "
			    "third_party_from_search field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*third_party = (PyObject_IsTrue(pValue));
	}

	return (AUTO_INSTALL_SUCCESS);
}

/*
 * ai_get_ddu_dev_data_values:
 * Return selected values from a given ddu_dev_data object.
 *
 * Values returned live on the python interpreter's heap, and should not be
 * modified or freed.  They live only as long as the python obj they come from.
 *
 * Note: implementation is tied to the fields of the python object.
 *
 * Arguments:
 *   pDDUDevData: Object to extract values from.  Assumed to be a
 *	ddu_dev_data object;  not verified.
 *   dev_type_p: char string pointer returned filled in with "device_type"
 *	field.  Not processed if NULL.
 *   descr_p: char string pointer returned filled in with "description" field.
 *	Not processed if NULL.
 *   vendor_ID_p: char string pointer returned filled in with "vendor ID" field.
 *	Not processed if NULL.
 *   device_ID_p: char string pointer returned filled in with "device ID" field.
 *	Not processed if NULL.
 *   class_p: char string pointer returned filled in with PCI "class" field.
 *	Not processed if NULL.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: when all requested fields are found and extracted.
 *   AUTO_INSTALL_FAILURE: when one or more fields could not be found or
 *	extracted.
 */
static int
ai_get_ddu_dev_data_values(PyObject *pDDUDevData, char **dev_type_p,
    char **descr_p, char **vendor_ID_p, char **device_ID_p, char **class_p)
{
	PyObject *pValue;

	if (dev_type_p != NULL) {
		pValue = PyObject_GetAttrString(pDDUDevData, "device_type");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_dev_data_values: "
			    "no ddu_dev_data device_type field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*dev_type_p = PyString_AsString(pValue);
	}

	if (descr_p != NULL) {
		pValue = PyObject_GetAttrString(pDDUDevData, "description");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_dev_data_values: "
			    "no ddu_dev_data description field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*descr_p = PyString_AsString(pValue);
	}

	if (vendor_ID_p != NULL) {
		pValue = PyObject_GetAttrString(pDDUDevData, "vendor_id");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_dev_data_values: "
			    "no ddu_dev_data vendor_id field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*vendor_ID_p = PyString_AsString(pValue);
	}

	if (device_ID_p != NULL) {
		pValue = PyObject_GetAttrString(pDDUDevData, "device_id");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_dev_data_values: "
			    "no ddu_dev_data device_id field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*device_ID_p = PyString_AsString(pValue);
	}

	if (class_p != NULL) {
		pValue = PyObject_GetAttrString(pDDUDevData, "class_code");
		if (pValue == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_get_ddu_dev_data_values: "
			    "no ddu_dev_data class_code field.\n");
			return (AUTO_INSTALL_FAILURE);
		}
		*class_p = PyString_AsString(pValue);
	}

	return (AUTO_INSTALL_SUCCESS);
}

/*
 * ai_du_process_manual_pkg:
 * Create a ddu_package_object from parameters, and add it to the pPackageList.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   pPackageList: List of packages to append the new ddu_package_object to.
 *   origin: directory of where package or package directive is located.
 *   type: type of package.
 *   name: name of package.
 *   noinstall: boolean whether package is to be installed only to booted
 *	environment, not to target.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: A new package object was successfully appended to
 *	pPackageList.
 *   AUTO_INSTALL_FAILURE: An error occurred when trying to create a new
 *	package object or append it to the pPackageList.
 *
 *   Note: The list object referenced by pPackageList will be modified.
 */
static int
ai_du_process_manual_pkg(py_state_t *py_state_p, PyObject *pPackageList,
    char *origin, char *type, char *name, char *noinstall)
{
	PyObject *pDDUPackageObject;
	PyObject *pTuple;

	auto_log_print(gettext(
	    "Add Drivers: Found manifest entry for package:\n"));
	if (name != empty_string) {
		auto_log_print(gettext("  type:%s, origin:%s, name:%s\n"),
		    type, origin, name);
	} else {
		auto_log_print(gettext("  type:%s, origin:%s\n"),
		    type, origin);
	}
	if (strcmp(noinstall, "true") == 0) {
		auto_log_print(gettext("    Package to be "
		    "installed only in current booted environment.\n"));
	} else {
		auto_log_print(gettext("    Package to be "
		    "installed in current booted environment and target.\n"));
	}

	/* Initialize a new ddu_package_object object */
	pDDUPackageObject = ai_new_ddu_package_object(py_state_p,
	    type, name, origin);

	if (pDDUPackageObject == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_process_manual_pkg: <add_drivers> error:\n"
		    "Error creating new package object for "
		    "origin %s %s\n", origin, name);
		return (AUTO_INSTALL_FAILURE);
	}

	pTuple = PyTuple_New(3);
	(void) PyTuple_SetItem(pTuple, 0, pDDUPackageObject);
	(void) PyTuple_SetItem(pTuple, 1, Py_True);	/* third party OK */
	(void) PyTuple_SetItem(pTuple, 2,
	    (strcmp(noinstall, "true") == 0) ? Py_True : Py_False);

	/*
	 * NOTE: Don't decref pTuple here as PyList_Append doesn't
	 * steal a reference to it.
	 */
	(void) PyList_Append(pPackageList, pTuple);
	return (AUTO_INSTALL_SUCCESS);
}

/*
 * ai_du_process_manual_pkg_names:
 * Do any processing of packages for which unique origin (location), type and
 *	name are known.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   path_p: Used to build nodepath strings for manifest checking.
 *   pPackageList: List of packages to append the new ddu_package_object to.
 *   origin: directory of where package is located.
 *   type: type of package.
 *   name: name of package.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: Package processed successfully and appended to
 *	pPackageList.
 *   AUTO_INSTALL_FAILURE: An error occurred.  No package appended to
 *	pPackageList.
 *
 *   Note 1: the object pointed to by pPackageList will be modified.
 */
static int
ai_du_process_manual_pkg_names(py_state_t *py_state_p, path_t *path_p,
    PyObject *pPackageList, char *origin, char *type, char *name)
{
	char **actions;
	int actions_len;
	char *nodespec;
	int rval;

	/* Get the action attribute. */

	/* Search is different depending on whether a name is specified. */
	if (name == empty_string) {
		nodespec = ACTION_NONAME_NODEPATH;
	} else {
		nodespec = ACTION_YESNAME_NODEPATH;
	}

	if (snprintf(path_p->post_prefix_start, path_p->post_prefix_len,
	    nodespec, origin, type, name) >= path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_process_manual_pkg_names: "
		    "<add_drivers> manifest error:\n"
		    "action path buffer overflow for origin \"%s\", "
		    "type \"%s\", name \"%s\"\n", origin, type, name);
		return (AUTO_INSTALL_FAILURE);
	}

	actions = ai_get_manifest_values(path_p->path_str, &actions_len);

	/*
	 * Note: action must be present and must be
	 * either "install" or "noinstall".
	 */
	if (actions_len <= 0) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "no action value for origin \"%s\", "
		    "type \"%s\", name \"%s\"\n"), origin, type, name);
		rval = AUTO_INSTALL_FAILURE;

	} else if (actions_len > 1) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "multiple action values for origin \"%s\", "
		    "type \"%s\", name \"%s\"\n"), origin, type, name);
		rval = AUTO_INSTALL_FAILURE;

	} else if (strcmp(actions[0], "install") == 0) {
		/*
		 * If action="install" then call ai_du_process_manual_pkg with
		 * noinstall param set to empty_string, which means pkg will be
		 * installed in both boot env and target.
		 */

		/* Obj pointed to by pPackageList will be modified. */
		rval = ai_du_process_manual_pkg(py_state_p, pPackageList,
		    origin, type, name, empty_string);
	} else if (strcmp(actions[0], "noinstall") == 0) {
		/*
		 * If action="noinstall" then call ai_du_process_manual_pkg with
		 * noinstall param set to "true", which means pkg will only be
		 * installed in both boot env and not in target.
		 */
		/* Obj pointed to by pPackageList will be modified. */
		rval = ai_du_process_manual_pkg(py_state_p, pPackageList,
		    origin, type, name, "true");
	} else {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "action must be install or noinstall for origin \"%s\", "
		    "type \"%s\", name \"%s\"\n"), origin, type, name);
		rval = AUTO_INSTALL_FAILURE;
	}
	ai_free_manifest_values(actions);
	return (rval);
}

/*
 * ai_du_process_manual_pkg_types:
 * Do any processing of packages for which unique location and type are known.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   pPackageList: List of packages to append the new ddu_package_object to.
 *   origin: directory of where package is located.
 *   type: type of package.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: Package processed successfully and appended to
 *	pPackageList.
 *   AUTO_INSTALL_FAILURE: An error occurred.  No package appended to
 *	pPackageList.
 *
 *   Note 1: the pPackageList will be modified.
 *   Note 2: Appropriate error messages are logged/displayed.
 */
static int
ai_du_process_manual_pkg_types(py_state_t *py_state_p, PyObject *pPackageList,
    path_t *path_p, char *origin, char *type)
{
	char **names;
	char **uniq_names;
	int namelen;
	int k;
	int rval = AUTO_INSTALL_SUCCESS;

	if ((strcmp(type, "P5I") != 0) &&
	    (strcmp(type, "SVR4") != 0) &&
	    (strcmp(type, "DU") != 0)) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "invalid type %s given for origin %s\n"), type, origin);
		return (AUTO_INSTALL_FAILURE);
	}

	/* Get all names assocated with type and origin. */

	if (snprintf(path_p->post_prefix_start, path_p->post_prefix_len,
	    NAME_NODEPATH, origin, type) >= path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_process_manual_pkg_types: "
		    "<add_drivers> manifest error:\n"
		    "name path buffer overflow for origin "
		    "%s, type %s\n", origin, type);
		return (AUTO_INSTALL_FAILURE);
	}

	names = ai_get_manifest_values(path_p->path_str, &namelen);
	uniq_names = ai_uniq_manifest_values(names, &namelen);
	ai_free_manifest_values(names);
	names = uniq_names;

	/* P5I and DU type entries don't have a "name" entry. */
	if (strcmp(type, "SVR4") != 0) {
		if (namelen > 0) {
			auto_log_print(gettext(
			    "Add Drivers: <add_drivers> "
			    "manifest error:\n"
			    "name given to P5I or DU package specification at "
			    "origin %s\n"), origin);
			rval = AUTO_INSTALL_FAILURE;
		} else {
			/* Obj pointed to by pPackageList will be modified. */
			rval = ai_du_process_manual_pkg_names(py_state_p,
			    path_p, pPackageList, origin, type, empty_string);
		}

	/* There must be at least one "name" entry per pkgspec for SVR4 type. */
	} else if (namelen <= 0) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "  no name given for SVR4 package specification\n"
		    "  at origin %s, type %s\n"), origin, type);
		rval = AUTO_INSTALL_FAILURE;

	} else {
		/* Process each origin/type/name entry. */
		for (k = 0; k < namelen; k++) {

			/* Obj pointed to by pPackageList will be modified. */
			int status = ai_du_process_manual_pkg_names(py_state_p,
			    path_p, pPackageList, origin, type, names[k]);
			if (status == AUTO_INSTALL_FAILURE) {
				rval = AUTO_INSTALL_FAILURE;
			}
		}
	}
	ai_free_manifest_values(names);
	return (rval);
}

/*
 * ai_du_get_manual_pkg_list:
 * Read the AI ai.xml Manifest file and process the <software> tags under the
 * <add_drivers> section.  <software> represents a manual specification of a
 * package to install.  Do error checking of the manifest as necessary, as this
 * function reads the manifest before it is validated against a schema.
 *
 * Validates syntax and processes the following from the manifest:
 *	<add_drivers>
 *		<software>
 *			<source>
 *				<publisher>
 *					<origin name="location"/>
 *				</publisher>
 *			</source>
 *			<software_data type="type" action="noinstall">
 *				<name>"name"</name>
 *			</software_data>
 *		</software>
 *	</add_drivers>
 *
 *	type can be "SVR4", "P5I" or "DU".
 *	name not allowed if type is "P5I" or "DU"
 *
 * Always return a list.  An empty list can be returned if the manifest shows
 * there are no packages to install for Driver Update, or on some errors.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   path_p: Used to build nodepath strings for manifest checking.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: A complete python list of (ddu_package_object,
 *	third_party_ok, noinstall) tuples suitable for input to
 *	ai_du_install_packages() has been created.
 *   AUTO_INSTALL_FAILURE: A python list of tuples suitable for input to
 *	ai_du_install_packages() has been created, but is missing one or more
 *	requested packages due to errors.  These errors could be manifest
 *	parsing errors or errors in setting up the packages.
 *
 * NOTE: check installer logfile for details of the failure.
 */
static int
ai_du_get_manual_pkg_list(py_state_t *py_state_p, path_t *path_p,
    PyObject **pPackageList_p)
{
	char **uniq_origins = NULL;
	char **types = NULL;
	int origin_len, typelen;
	char **origins;
	char **uniq_types;
	int num_pkgspecs;
	int i, j;
	int rval = AUTO_INSTALL_SUCCESS;

	/*
	 * Initialize a zero-length list.
	 * This will be returned empty if nothing to install has been found
	 * or if an error is found early on.
	 */
	*pPackageList_p = PyList_New(0);

	/* Read manifest for specific package requests. */

	/* Get the number of <software> package spec entries. */
	if (strlcpy(path_p->post_prefix_start, PKGSPEC_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR, "ai_du_get_manual_pkg_list: "
		    "<software> path buffer overflow\n");
		return (AUTO_INSTALL_FAILURE);
	}

	/* Use "origins" like a dummy here.  Interest only in num_pkgspecs. */
	origins = ai_get_manifest_values(path_p->path_str, &num_pkgspecs);
	ai_free_manifest_values(origins);

	/* No package specs.  Return an empty list. */
	if (num_pkgspecs <= 0) {
		return (AUTO_INSTALL_SUCCESS);
	}

	/* Retrieve a list of all specific package request origins. */
	if (strlcpy(path_p->post_prefix_start, ORIGIN_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_manual_pkg_list: origin path buffer overflow\n");
		return (AUTO_INSTALL_FAILURE);
	}

	/* Get real origins list here for use below. */
	origins = ai_get_manifest_values(path_p->path_str, &origin_len);

	/*
	 * Not a perfect test to validate package specs vs origins in
	 * manifest, but it will do...
	 */
	if (origin_len != num_pkgspecs) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_manual_pkg_list: <add_drivers> manifest error:\n"
		    "There is not a 1-1 <origin> - <software> mapping.\n");
		ai_free_manifest_values(origins);
		return (AUTO_INSTALL_FAILURE);
	}

	uniq_origins = ai_uniq_manifest_values(origins, &origin_len);
	ai_free_manifest_values(origins);
	origins = uniq_origins;

	/*
	 * For each origin (location), get types.  Note it is possible for
	 * there to be more than one type at an origin.  There can also be more
	 * than one item of a given type at an origin.
	 */
	for (i = 0; i < origin_len; i++) {

		/* Process "type" entries. */

		if (snprintf(path_p->post_prefix_start, path_p->post_prefix_len,
		    TYPE_NODEPATH, origins[i]) >= path_p->post_prefix_len) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_manual_pkg_list: "
			    "<add_drivers> manifest error:\n"
			    "type path buffer overflow for origin %s\n",
			    origins[i]);
			rval = AUTO_INSTALL_FAILURE;
			continue;
		}

		types = ai_get_manifest_values(path_p->path_str, &typelen);
		if (typelen <= 0) {
			auto_log_print(gettext("Add Drivers: "
			    "<add_drivers> manifest error:\n"
			    "no type given for origin %s\n"), origins[i]);
			rval = AUTO_INSTALL_FAILURE;
			continue;
		}

		uniq_types = ai_uniq_manifest_values(types, &typelen);
		ai_free_manifest_values(types);
		types = uniq_types;

		/* Loop for all types found at this origin... */
		for (j = 0; j < typelen; j++) {

			/* Obj *pPackageList_p points to will be modified.  */
			int status = ai_du_process_manual_pkg_types(py_state_p,
			    *pPackageList_p, path_p, origins[i], types[j]);
			if (status == AUTO_INSTALL_FAILURE) {
				rval = AUTO_INSTALL_FAILURE;
			}
		}
	}

	ai_free_manifest_values(origins);
	ai_free_manifest_values(types);
	return (rval);
}

/*
 * ai_du_get_searched_pkg_list:
 * Read the AI ai.xml Manifest file and process the <search_all> tag under the
 * <add_drivers> section.  Do the needful to scan for missing devices and to
 * perform package searches and installs for missing drivers.  Do error
 * checking of the manifest as necessary, as this function reads the manifest
 * before it is validated against a schema.
 *
 * Always return a list.  An empty list can be returned if a search determines
 * there are no packages to install for Driver Update (i.e. the system is
 * missing no drivers), or on some errors.
 *
 * Validates syntax and processes the following from the manifest:
 *	<add_drivers>
 *		<search_all addall="false">
 *			<source>
 *				<publisher name="publisher">
 *					<origin name="location"/>
 *				</publisher>
 *			</source>
 *		</search_all>
 *	</add_drivers>
 *
 *	publisher and origin are both optional, but if one is specified then
 *		the other must also be specified.
 *
 *	addall is optional.  When true, it allows search_all to install third
 *	party drivers (found via the database in the given pkg(5) repository,
 *	but installed from somewhere else).  Defaults to "false" if not
 *	specified.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   path_p: Used to build nodepath strings for manifest checking.
 *   install_root: Root used for determining pkg publisher.
 *   pPackageList_p: A python list of (ddu_package_object, third_party_ok,
 *	noinstall) tuples suitable for input to ai_du_install_packages().
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: No errors were encountered in retrieving package
 *	information.  It is also possible that the system is missing no drivers,
 *	and an empty list is returned.
 *   AUTO_INSTALL_PKG_NOT_FND: Packages for one or more missing drivers are not
 *	available.
 *   AUTO_INSTALL_FAILURE: One or more errors (other than packages which were
 *	not available) were encountered in retrieving package information.
 *
 * NOTE: check installer logfile for details of the failure.
 */
static int
ai_du_get_searched_pkg_list(py_state_t *py_state_p, path_t *path_p,
    char *install_root, PyObject **pPackageList_p)
{
	PyObject *pDeviceList = NULL;
	PyObject *pTuple;
	PyObject *pRepoTupleList;
	int len, sublen;
	PyObject *pSearchRepoList = NULL;
	char *search_origin, *search_pub;
	PyObject *py_search_addall = NULL;
	char **searches = NULL;
	char **search_origins = NULL;
	char **search_pubs = NULL;
	char **search_addalls = NULL;
	Py_ssize_t i, listlen;
	int rval = AUTO_INSTALL_FAILURE;

	*pPackageList_p = PyList_New(0); /* Initialize a zero-length list. */

	/* Read manifest for search requests. */

	if (strlcpy(path_p->post_prefix_start, SEARCH_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: "
		    "search pathname buffer overflow.\n");
		return (AUTO_INSTALL_FAILURE);
	}

	searches = ai_get_manifest_values(path_p->path_str, &len);
	ai_free_manifest_values(searches);
	if (len > 1) {
		auto_log_print(gettext("Add Drivers: "
		    "Only one <search_all> entry allowed in manifest\n"));
		return (AUTO_INSTALL_FAILURE);
	}

	if (len <= 0) {
		return (AUTO_INSTALL_SUCCESS);
	}

	auto_log_print(gettext("Add Drivers: Doing a device "
	    "scan for devices which are missing drivers...\n"));

	/*
	 * Call ddu_devscan() to do search if requested.
	 * The boolean value is to scan only for missing drivers.
	 */
	pDeviceList = ai_call_ddu_devscan(py_state_p, B_TRUE, "all");
	if (pDeviceList == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: "
		    "Error scanning for missing drivers.\n");
		return (AUTO_INSTALL_FAILURE);

	/* An empty list is perfectly acceptable here.  No missing drivers. */
	} else if (PyList_Size(pDeviceList) == 0) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: No missing drivers found.\n");
		return (AUTO_INSTALL_SUCCESS);
	}

	/* Get repo location, if specified. */

	if (strlcpy(path_p->post_prefix_start, SEARCH_ORIGIN_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: search repo origin path "
		    "buffer overflow.\n");
		return (AUTO_INSTALL_FAILURE);
	}

	auto_log_print(gettext("Add Drivers: Querying manifest "
	    "for explicit repo for getting missing driver packages...\n"));

	search_origins = ai_get_manifest_values(path_p->path_str, &sublen);
	if (sublen == 1) {
		search_origin = search_origins[0];
	} else if (sublen <= 0) {
		search_origin = empty_string;
	} else {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "Only one origin allowed per <search_all> entry.\n"));
		goto done;
	}

	/* Get repo publisher, if specified. */

	if (strlcpy(path_p->post_prefix_start, SEARCH_PUBNAME_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: search repo publisher path "
		    "buffer overflow.\n");
		goto done;
	}

	search_pubs = ai_get_manifest_values(path_p->path_str, &sublen);
	if (sublen == 1) {
		search_pub = search_pubs[0];
	} else if (sublen <= 0) {
		search_pub = empty_string;
	} else {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "Only one publisher allowed for a <search_all> entry\n"));
		goto done;
	}

	/* Can't have one without the other. */
	if ((search_pub == empty_string) ^
	    (search_origin == empty_string)) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "search repo origin and "
		    "publisher must be specified together.\n"));
		goto done;
	}

	/*
	 * if publisher and origin provided, create tuple from them and
	 * build a repo list from it.
	 */
	if (search_pub != empty_string) {

		auto_log_print(gettext("Add Drivers: "
		    "Found repo in manifest: publisher:%s, origin:%s\n"),
		    search_pub, search_origin);

		pTuple = PyTuple_New(2);
		(void) PyTuple_SetItem(pTuple, 0,
		    PyString_FromString(search_pub));
		(void) PyTuple_SetItem(pTuple, 1,
		    PyString_FromString(search_origin));
		pRepoTupleList = PyList_New(0);
		(void) PyList_Append(pRepoTupleList, pTuple);
		pSearchRepoList = ai_call_ddu_build_repo_list(py_state_p,
		    pRepoTupleList);
		Py_DECREF(pTuple);
		Py_DECREF(pRepoTupleList);

		if (pSearchRepoList == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_searched_pkg_list:"
			    "Error building search repo list.\n");
			goto done;
		}

		auto_log_print(gettext("Add Drivers: "
		    "Searching for packages in %s repository at %s\n"),
		    search_pub, search_origin);

	} else {
		FILE *pub_info;
		char pub_buf[MAXPATHLEN];
		char cmd_buf[MAXPATHLEN];

		/* No publisher/URL provided.  Return an empty repo list. */

		auto_log_print(gettext("Add Drivers: "
		    "No explicit <search_all> repo specified in manifest\n"));
		auto_log_print(gettext("... Searching for packages in "
		    "repositories already configured on the system\n"));

		(void) snprintf(cmd_buf, MAXPATHLEN,
		    "/usr/bin/pkg -R %s publisher", install_root);
		if ((pub_info = popen(cmd_buf, "r")) != NULL) {
			while (fgets(pub_buf, MAXPATHLEN, pub_info) != NULL) {
				auto_log_print("%s\n", pub_buf);
			}
			(void) pclose(pub_info);
		}

		pSearchRepoList = PyList_New(0);
	}

	/* Find out if <addall> was specified. */

	if (strlcpy(path_p->post_prefix_start, SEARCH_ADDALL_NODEPATH,
	    path_p->post_prefix_len) > path_p->post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_searched_pkg_list: search addall path "
		    "buffer overflow.\n");
		goto done;
	}

	/* No more than a single true/false value is allowed. */
	search_addalls = ai_get_manifest_values(path_p->path_str, &sublen);
	if ((sublen > 1) ||
	    ((sublen == 1) &&
	    ((strcmp(search_addalls[0], "true") != 0) &&
	    (strcmp(search_addalls[0], "false") != 0)))) {
		auto_log_print(gettext("Add Drivers: "
		    "<add_drivers> manifest error:\n"
		    "invalid addall value for <search_all> entry\n"));
		goto done;

	/* Default to false if not provided. */
	} else if ((sublen <= 0) || (strcmp(search_addalls[0], "false") == 0)) {
		Py_INCREF(Py_False);
		py_search_addall = Py_False;

	} else {
		auto_log_print(gettext("Add Drivers: Manifest "
		    "allows adding of third-party drivers\n"));
		Py_INCREF(Py_True);
		py_search_addall = Py_True;
	}

	/*
	 * Append packages found for missing devices, to the list of packages
	 * to install.
	 */
	rval = AUTO_INSTALL_SUCCESS;
	listlen = PyList_Size(pDeviceList);
	for (i = 0; i < listlen; i++) {

		PyObject *pDDUPackageObject;
		PyObject *pDDUDevData;
		char *dev_type;
		char *descr;
		int lookup_err;
		boolean_t third_party = B_FALSE;

		pDDUDevData = PyList_GetItem(pDeviceList, i);

		/* Find the package containing the driver for this device. */
		lookup_err = ai_call_ddu_package_lookup(py_state_p,
		    pDDUDevData, pSearchRepoList, &pDDUPackageObject);

		/* Get info for display / logging purposes, and log it. */
		if (ai_get_ddu_dev_data_values(pDDUDevData, &dev_type, &descr,
		    NULL, NULL, NULL) != AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_searched_pkg_list: Error retrieving "
			    "device information for display\n");
			dev_type = descr = empty_string;
		}

		/* Package not found is not considered an error. */
		if (lookup_err == AUTO_INSTALL_PKG_NOT_FND) {
			auto_log_print(gettext("Add Drivers: "
			    "Warning: Search found no package for "
			    "\"%s\" type device \"%s\".\n"), dev_type, descr);
			/*
			 * Set marginal success status.
			 * Don't override failure status.
			 */
			if (rval == AUTO_INSTALL_SUCCESS) {
				rval = AUTO_INSTALL_PKG_NOT_FND;
			}
			continue;
		} else if (lookup_err != AUTO_INSTALL_SUCCESS) {
			auto_log_print(gettext("Add Drivers: "
			    "Error retrieving package for "
			    "\"%s\" type device \"%s\".\n"), dev_type, descr);
			rval = AUTO_INSTALL_FAILURE;
			continue;
		} else {
			auto_log_print(gettext("Add Drivers: "
			    "DDU returned package info for "
			    "\"%s\" type device \"%s\".\n"), dev_type, descr);
		}

		(void) ai_get_ddu_package_object_values(pDDUPackageObject,
		    NULL, NULL, NULL, NULL, NULL, &third_party);
		if (third_party) {
			auto_log_print(gettext("  This is a third-party "
			    "package.\n"));
		}

		/* Append the package info to the returned list. */

		/*
		 * NOTE: Don't decref pTuple here as PyList_Append doesn't
		 * steal a reference to it.
		 */
		pTuple = PyTuple_New(3);
		(void) PyTuple_SetItem(pTuple, 0, pDDUPackageObject);
		Py_INCREF(py_search_addall);	/* 3rd party OK */
		(void) PyTuple_SetItem(pTuple, 1, py_search_addall);
		Py_INCREF(Py_False);		/* always install */
		(void) PyTuple_SetItem(pTuple, 2, Py_False);
		(void) PyList_Append(*pPackageList_p, pTuple);
	}
done:
	/* Cleanup time, whether an error occured or not. */
	ai_free_manifest_values(search_origins);
	ai_free_manifest_values(search_pubs);
	Py_XDECREF(py_search_addall);
	Py_XDECREF(pSearchRepoList);
	Py_XDECREF(pDeviceList);
	return (rval);
}

/*
 * ai_du_install_packages:
 * Install packages provided by the pPkgTupleList.  Install in the filesystem /
 * tree under install_root, skipping packages with noinstall flag set if
 * honor_noinstall is set.
 *
 * NOTE: it is assumed that the DDU library returns successful status when
 * attempting to install a package which is already installed.
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   pPkgTupleList: Python list of (ddu_package_object, third_party_ok,
 *	noinstall) tuples which define packages to add and their parameters for
 *	adding them.  Guaranteed not to be NULL.  When third_party_ok is true,
 *	add the corresponding package even if it is to be downloaded from a
 *	third party website.  When noinstall is true in the tuple and the
 *	honor_noinstall argument is also true, skip adding the corresponding
 *	package.  (This may be used to skip installation onto the target disk,
 *	after having installed into the booted install environment.)
 *   install_root: Top of the filesystem or tree where the packages are to be
 *	installed.
 *   honor_noinstall: When true and the noinstall flag is set in a package
 *	tuple, skip installing that package.
 *   num_installed_pkgs_p: Returns the value passed in, plus the number of
 *	packages actually installed.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: All packages were able to be installed.
 *   AUTO_INSTALL_FAILURE: At least one package was not able to be installed.
 *
 * NOTE: check installer logfile for details of the failure.
 */
static int
ai_du_install_packages(py_state_t *py_state_p, PyObject *pPkgTupleList,
    char *install_root, boolean_t honor_noinstall, int *num_installed_pkgs_p)
{
	Py_ssize_t len;
	Py_ssize_t i;
	int rval = AUTO_INSTALL_SUCCESS;

	auto_log_print(gettext("Add Drivers: "
	    "Installing packages to %s\n"), install_root);

	len = PyList_Size(pPkgTupleList);
	for (i = 0; i < len; i++) {

		/* Break out the tuple. */

		PyObject *pTuple = PyList_GetItem(pPkgTupleList, i);
		PyObject *pDDUPackageObject = PyTuple_GetItem(pTuple, 0);
		PyObject *pThirdPartyOK = PyTuple_GetItem(pTuple, 1);
		PyObject *pNoInstall = PyTuple_GetItem(pTuple, 2);
		char *type, *location, *name, *descr, *inf_link;
		boolean_t third_party;

		if (ai_get_ddu_package_object_values(pDDUPackageObject,
		    &type, &location, &name, &descr, &inf_link, &third_party) !=
		    AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_install_packages: Error extracting package "
			    "information for ddu_package_object.\n");
			type = location = name = descr = inf_link =
			    empty_string;
			third_party = B_FALSE;
		} else {
			if (strcmp(name, empty_string) == 0) {
				auto_log_print(gettext(
				    "  %s package at origin:%s\n"),
				    type, location);
			} else {
				auto_log_print(gettext(
				    "  %s package at origin:%s, name:%s\n"),
				    type, location, name);
			}
		}

		if (PyObject_IsTrue(pNoInstall) && honor_noinstall) {
			auto_log_print(gettext("Add Drivers: "
			    "    honoring noinstall: skipping package.\n"));
			continue;
		}

		/* Display any third-party package errors to console. */
		if ((! PyObject_IsTrue(pThirdPartyOK)) && third_party) {
			char *msg1_3p = gettext("  Manifest is not allowing "
			    "third party packages found through search for "
			    "installation to %s\n");
			char *msg2_3p = gettext("  Info on the package to "
			    "install to make device \"%s\"\n"
			    "    operational is available:\n"
			    "    %s\n");
			(void) fprintf(stderr, msg1_3p, install_root);
			auto_log_print(msg1_3p, install_root);
			(void) fprintf(stderr, msg2_3p, descr, inf_link);
			auto_log_print(msg2_3p, descr, inf_link);
			rval = AUTO_INSTALL_FAILURE;
			continue;
		}

		/* Handle uninstallable package objects. */
		if (strcmp(location, empty_string) == 0) {
			if (strcmp(inf_link, empty_string) == 0) {
				auto_log_print(gettext(
				    "Add Drivers: Package not "
				    "found for device: \"%s\"\n"), descr);
			} else {
				auto_log_print(gettext(
				    "Add Drivers: Package for device: \"%s\" "
				    "must be installed manually.\n"
				    "For more information go to:\n %s\n"),
				    descr, inf_link);
			}
			rval = AUTO_INSTALL_FAILURE;
			continue;
		}

		/* All is well.  Install the package. */
		if (ai_call_ddu_install_package(py_state_p, pDDUPackageObject,
		    install_root, PyObject_IsTrue(pThirdPartyOK)) ==
		    AUTO_INSTALL_FAILURE) {
			auto_log_print(gettext("Add Drivers: "
			    "Error installing package to %s\n"), install_root);
			rval = AUTO_INSTALL_FAILURE;
		} else {
			(*num_installed_pkgs_p)++;
		}
	}
	return (rval);
}

/*
 * ai_uniq_manifest_values:
 * Remove duplicate values in lists returned by ai_lookup_manifest_values().
 *
 * Arguments:
 *   in: the input list of values.
 *   len_p: The length of the input list, on input.  Returns the length of the
 *	list returned.
 *
 * Returns:
 *   Success: The resulting list of unique values.
 *   Failure: NULL
 */
static char **
ai_uniq_manifest_values(char **in, int *len_p)
{
	int in_len = *len_p;
	int dup_count = 0;
	char **out;
	char *comp;
	boolean_t *is_dup = (boolean_t *)alloca(in_len * sizeof (boolean_t));
	int i, j;

	if ((in_len == 0) || (in == NULL)) {
		return (NULL);
	}

	bzero(is_dup, (in_len * sizeof (boolean_t)));

	for (i = 0; i < in_len - 1; i++) {
		comp = in[i];
		for (j = i + 1; j < in_len; j++) {
			if ((!is_dup[j]) && (strcmp(comp, in[j]) == 0)) {
				is_dup[j] = B_TRUE;
				dup_count++;
			}
		}
	}

	out = (char **)malloc((in_len - dup_count + 1) * sizeof (char *));
	if (out == NULL) {
		return (NULL);
	}
	for (i = 0, j = 0; i < in_len; i++) {
		if (!is_dup[i]) {
			out[j++] = strdup(in[i]);
		}
	}
	out[j] = NULL;

	*len_p = j;
	return (out);
}

/*
 * ai_du_call_update_archive_ict:
 * Call the bootadm update_archive ICT
 *
 * Arguments:
 *   py_state_p: Initialized py_state_t object.
 *   install_root: root of the tree where to call the ICT.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: ICT was successfully executed.
 *   AUTO_INSTALL_FAILURE: ICT was not successfully executed.
 */
static int
ai_du_call_update_archive_ict(py_state_t *py_state_p, char *install_root)
{
	int rval = AUTO_INSTALL_FAILURE;
	PyObject *pICT_instance = NULL;
	PyObject *pICT_rval = NULL;

	/* Find the constructor. */
	PyObject *pFunc = PyObject_GetAttrString(py_state_p->pICTModule,
	    ICT_CLASS);

	if ((pFunc == NULL) || (!PyCallable_Check(pFunc))) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ICT constructor not callable\n");
	} else {
		/* Set up args to python function. */
		PyObject *pArgs = PyTuple_New(1);
		(void) PyTuple_SetItem(pArgs, 0,
		    PyString_FromString(install_root));

		/* Call constructor. */
		pICT_instance = PyObject_CallObject(pFunc, pArgs);
		Py_XDECREF(pFunc);
		Py_DECREF(pArgs);
		if ((PyErr_Occurred() != NULL) || (pICT_instance == NULL) ||
		    (pICT_instance == Py_None)) {
			auto_debug_dump_file(AUTO_DBGLVL_ERR, DDU_ERRLOG);
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ICT constructor failed\n");
			ai_dump_python_exception();
			Py_CLEAR(pICT_instance);
		}
	}

	if (pICT_instance != NULL) {
		pICT_rval = PyObject_CallMethod(
		    pICT_instance, ICT_UPDATE_ARCHIVE, NULL);
		if (pICT_rval == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Error running update_boot_archive ICT.\n");
		} else if (PyInt_AsLong(pICT_rval) != 0) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "update_boot_archive ICT returned an error.\n");
		} else {
			rval = AUTO_INSTALL_SUCCESS;
		}
		Py_XDECREF(pICT_rval);
		Py_DECREF(pICT_instance);
	}

	return (rval);
}

/* Exported functions. */

/*
 * ai_du_get_and_install:
 * Query the manifest for the entire <add_drivers> section, and add packages
 * accordingly.  Add packages to install_root.  If a package has its noinstall
 * flag set and the honor_noinstall argument is set, skip adding that package.
 * Save the list of packages to install to the module global py_pkg_list, so
 * that the same list of packages can be installed to a different target with
 * ai_du_install().
 *
 * Install all explicitly-stated packages first.  Then do <search_all> last.
 * This is to handle any explicit requests for matching a special driver to a
 * device, before <search_all> finds the first available one.
 *
 * If search determines that a driver is missing and cannot find a package for
 * it, this is not reported as an error.  A ddu_package_object is not created in
 * this case, so no installation or package fetch is done for this driver.  Any
 * other kind of problem which occurs around searched packages, during the
 * search itself or during an installation of a package found during search, is
 * reported as an error.
 *
 * Any issue found around explicitly specified packages (<software>s), whether
 * it be that the package is not found or there was an issue during
 * installation, is reported as an error.  ddu_package_objects are always
 * created for these packages.
 *
 * Assumes ai_create_manifest_image() has set up the manifest data.
 * Does not assume any data has been verified though.
 *
 * Arguments:
 *   install_root: Top of the filesystem or tree where the packages are to be
 *	installed.
 *   honor_noinstall: When true and the noinstall flag is set in a package
 *	tuple, skip installing that package.
 *   update_boot_archive: When true, run the ICT to update the boot archive.
 *   num_pkgs_installed_p: Returns the number of packages installed.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: No errors found.
 *   AUTO_INSTALL_PKG_NOT_FND: At least one needed package found during search
 *	could not be found.  No other errors encountered.
 *   AUTO_INSTALL_FAILURE: An error was encountered and was different than
 *	not being able to find a package for a missing driver.
 *
 *   Boot archive update status is not reflected in this return status.
 *   NOTE: this routine will continue on most errors, in order to install as
 *	many packages as possible.
 *
 * NOTE: return status and num_pkgs_installed together tell the caller the full
 * story.  It is possible, for example, that no packages were installed because
 * one package flagged during search could not be found.
 *
 * NOTE: check installer logfile for details of the failure.
 *
 * Side effects:
 *   module global py_pkg_list is set to point to list of packages to install.
 */
int
ai_du_get_and_install(char *install_root, boolean_t honor_noinstall,
    boolean_t update_boot_archive, int *num_installed_pkgs_p)
{
	PyObject *manual_pkg_list;
	PyObject *searched_pkg_list;
	py_state_t *py_state_p;
	path_t path;
	char **dummy_list;
	int num_entries;
	int len;
	Py_ssize_t manual_size = 0;
	Py_ssize_t searched_size = 0;
	int rval = AUTO_INSTALL_SUCCESS;

	*num_installed_pkgs_p = 0;

	/* Initialize path, post_prefix_start and post_prefix_len for later. */
	(void) strncpy(path.path_str, AIM_PREFACE, MAX_NODEPATH_SIZE);
	len = strlen(path.path_str);
	path.post_prefix_start = &path.path_str[len];
	path.post_prefix_len = MAX_NODEPATH_SIZE - len;

	/*
	 * Set up an empty py_pkg_list so ai_du_install() knows this function
	 * was called first.
	 */
	if (py_pkg_list != NULL) {
		Py_CLEAR(py_pkg_list);
	}

	py_pkg_list = PyList_New(0);

	/*
	 * See if the manifest has at least one <software> or search_all entry.
	 * If not, just return success (e.g. no-op).
	 */

	/* Get the number of <software> entries. */
	if (strlcpy(path.post_prefix_start, PKGSPEC_NODEPATH,
	    path.post_prefix_len) > path.post_prefix_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_and_install: <software> path buffer overflow\n");
		return (AUTO_INSTALL_FAILURE);
	}

	/* Get number of <software> entries in the manifest. */
	dummy_list = ai_get_manifest_values(path.path_str, &num_entries);
	ai_free_manifest_values(dummy_list);

	if (num_entries <= 0) {
		/* See if there is a search_all entry in the manifest. */
		if (strlcpy(path.post_prefix_start, SEARCH_NODEPATH,
		    path.post_prefix_len) > path.post_prefix_len) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_and_install: "
			    "search path buffer overflow\n");
			return (AUTO_INSTALL_FAILURE);
		}

		dummy_list = ai_get_manifest_values(path.path_str,
		    &num_entries);
		ai_free_manifest_values(dummy_list);
		if (num_entries <= 0) {
			return (AUTO_INSTALL_SUCCESS);
		}
	}

	/*
	 * Install all explicitly specified packages first.
	 *
	 * Do the search for missing devices afterward, as an independent step,
	 * to account for newly-operational devices as a result of
	 * explicitly-specified package installation.
	 */

	if ((py_state_p = auto_ddu_lib_init()) == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_and_install: "
		    "Error initializing auto_ddu_lib.\n");
		rval = AUTO_INSTALL_FAILURE;
		goto done;
	}

	if (ai_du_get_manual_pkg_list(py_state_p, &path,
	    &manual_pkg_list) != AUTO_INSTALL_SUCCESS) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_and_install: "
		    "Error getting <software> package specification.\n");
		rval = AUTO_INSTALL_FAILURE;
		/* Keep going.  Don't abort. */
	}

	manual_size = PyList_Size(manual_pkg_list);
	if (manual_size > 0) {
		if (ai_du_install_packages(py_state_p, manual_pkg_list,
		    install_root, honor_noinstall, num_installed_pkgs_p) !=
		    AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_and_install: Error installing at least "
			    "one <software> package specification.\n");
			rval = AUTO_INSTALL_FAILURE;
			/* Keep going.  Don't abort. */
		}
	}

	switch (ai_du_get_searched_pkg_list(py_state_p, &path, install_root,
	    &searched_pkg_list)) {
	case AUTO_INSTALL_FAILURE:
		rval = AUTO_INSTALL_FAILURE;
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_get_and_install: "
		    "Error searching for inoperable devices and "
		    "missing driver packages.\n");
		/* Keep going.  Don't abort. */
		break;
	case AUTO_INSTALL_PKG_NOT_FND:
		if (rval != AUTO_INSTALL_FAILURE) {
			rval = AUTO_INSTALL_PKG_NOT_FND;
		}
		break;
	default:
		break;
	}

	searched_size = PyList_Size(searched_pkg_list);
	if (searched_size > 0) {
		if (ai_du_install_packages(py_state_p, searched_pkg_list,
		    install_root, honor_noinstall, num_installed_pkgs_p) !=
		    AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_and_install: Error installing at least "
			    "one searched package for <search_all>.\n");
			rval = AUTO_INSTALL_FAILURE;
			/* Keep going.  Don't abort. */
		}
	}

	if (update_boot_archive && (*num_installed_pkgs_p > 0)) {
		if (ai_du_call_update_archive_ict(py_state_p, install_root) !=
		    AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_get_and_install: Warning: could not update "
			    "boot archive for %s.\n", install_root);
		}
	}

	/*
	 * Save the manual and searched package lists in py_pkg_list.
	 * The new list can be used in a later call to ai_du_install().
	 */

	if (manual_size > 0) {
		(void) PyList_SetSlice(py_pkg_list, 0, manual_size - 1,
		    manual_pkg_list);
	}
	Py_DECREF(manual_pkg_list);

	if (searched_size > 0) {
		(void) PyList_SetSlice(py_pkg_list, manual_size,
		    manual_size + searched_size - 1, searched_pkg_list);
	}
	Py_DECREF(searched_pkg_list);

done:
	auto_ddu_lib_fini(py_state_p);

	return (rval);
}

/*
 * ai_du_install:
 * Install additional packages based on driver update parameters fetched from a
 * previous ai_du_get_and_install() call.  The module global py_pkg_list
 * supplies the list (and order) of packages to install.  Add packages to
 * install_root.  If a package has its noinstall flag set and the
 * honor_noinstall argument is set, skip adding that package.
 *
 * This routine assumes the py_pkg_list was set up via a prior call to
 * ai_du_get_and_install_packages().
 *
 * The availability and origin (location) of all packages to be installed is
 * assumed the same as when the py_pkg_list was built (i.e. the most recent
 * call to ai_du_get_and_install()).
 *
 * Arguments:
 *   install_root: Top of the filesystem or tree where the packages are to be
 *	installed.
 *   honor_noinstall: When true and the noinstall flag is set in a package
 *	tuple, skip installing that package.
 *   update_boot_archive: When true, run the ICT to update the boot archive.
 *   num_installed_pkgs_p: Returns the number of packages successfully
 *	installed.
 *   NOTE: the modular global py_pkg_list specifies the packages to install.
 *
 * Returns:
 *   AUTO_INSTALL_SUCCESS: No errors found and at least one package was
 *	installed.
 *   AUTO_INSTALL_FAILURE: An error was encountered.  Some packages may have
 *	been installed.
 *
 *   Boot archive update status is not reflected in this return status.
 *   NOTE: this routine will continue on most errors, in order to install as
 *	many packages as possible.
 *
 * NOTE: return status and num_pkgs_installed together tell the caller the full
 * story.  It is possible, for example, that no packages were installed because
 * one package flagged during search could not be found.
 *
 * NOTE: check installer logfile for details of the failure.
 */
int
ai_du_install(char *install_root, boolean_t honor_noinstall,
    boolean_t update_boot_archive, int *num_installed_pkgs_p)
{
	int rval = AUTO_INSTALL_SUCCESS;

	py_state_t *py_state_p;

	*num_installed_pkgs_p = 0;

	if (py_pkg_list == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_install: ai_du_get_and_install needs to be "
		    "called first.\n");
		return (AUTO_INSTALL_FAILURE);

	} else if (PyList_Size(py_pkg_list) == 0) {
		return (AUTO_INSTALL_SUCCESS);
	}

	if ((py_state_p = auto_ddu_lib_init()) == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_install: "
		    "Error initializing auto_ddu_lib.\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if ((rval = ai_du_install_packages(py_state_p, py_pkg_list,
	    install_root, honor_noinstall, num_installed_pkgs_p)) !=
	    AUTO_INSTALL_SUCCESS) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "ai_du_install: Error installing packages.\n");
		rval = AUTO_INSTALL_FAILURE;
	}

	if (update_boot_archive && (*num_installed_pkgs_p > 0)) {
		if (ai_du_call_update_archive_ict(py_state_p,
		    install_root) != AUTO_INSTALL_SUCCESS) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "ai_du_install: Warning: could not update boot "
			    "archive for %s.\n", install_root);
		}
	}

	auto_ddu_lib_fini(py_state_p);

	return (rval);
}
