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
 * Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#include <Python.h>
#include "auto_install.h"

#define	AI_PARSE_MANIFEST_SCRIPT "osol_install.auto_install.ai_parse_manifest"
#define	AI_CREATE_MANIFESTSERV "ai_create_manifestserv"
#define	AI_SETUP_MANIFESTSERV "ai_setup_manifestserv"
#define	AI_LOOKUP_MANIFEST_VALUES "ai_lookup_manifest_values"

static PyThreadState * mainThreadState = NULL;

/*
 * The C interface to ai_create_manifestserv (python module).
 * This function takes a manifest file and hands it off to
 * the ManifestServ. It returns the ManifestServ object thus
 * created which can then be used to lookup various paths.
 *
 * Note that the ManifestServ object created here has not been
 * validated before being returned.
 *
 * ai_destroy_manifestserv() must be called after all the
 * processing has been done to destroy the ManifestServ object
 *
 * This function can only be invoked from a single threaded
 * context.
 */
PyObject *
ai_create_manifestserv(char *filename)
{
	PyObject	*pFunc;
	PyObject	*pName;
	PyObject	*pArgs;
	PyThreadState	*myThreadState;
	PyObject	*pModule = NULL;
	PyObject	*rv = NULL;
	PyObject	*pRet = NULL;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	if ((pName = PyString_FromString(AI_PARSE_MANIFEST_SCRIPT)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	}
	if (pModule != NULL) {
		/* Load the ai_parse_manifest module */
		pFunc = PyObject_GetAttrString(pModule, AI_CREATE_MANIFESTSERV);
		/* pFunc is a new reference */
		if (pFunc && PyCallable_Check(pFunc)) {

			pArgs = PyTuple_New(1);
			PyTuple_SetItem(pArgs, 0,
			    PyString_FromString(filename));

			/* Call the ai_parse_manifest */
			pRet = PyObject_CallObject(pFunc, pArgs);
			Py_DECREF(pArgs);
			if ((pRet != NULL) && (!PyErr_Occurred())) {
				/*
				 * A reference is getting stolen here.
				 * We intentionally don't do a DECREF
				 * so that future calls using this object
				 * have a valid ManifestServ object to work
				 * with.
				 */
				if (pRet != Py_None)
					rv = pRet;
			} else {
				PyErr_Print();
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Call failed: %s\n",
				    AI_CREATE_MANIFESTSERV);
			}
		} else {
			auto_debug_print(AUTO_DBGLVL_ERR, "Python function "
			    "does not appear callable: %s\n",
			    AI_CREATE_MANIFESTSERV);
		}
	}
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);
	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
	return (rv);
}

/*
 * The C interface to ai_setup_manifestserv (python module).
 * Sets up and validates the data of a ManifestServ object.
 * Must be called after ai_create_manifestserv has set up a
 * ManifestServ object in memory.
 *
 * This function can only be invoked from a single threaded
 * context.
 */
int
ai_setup_manifestserv(PyObject *server_obj)
{
	PyObject	*pFunc;
	PyObject	*pName;
	PyObject	*pArgs;
	PyThreadState	*myThreadState;
	PyObject	*pRet;
	PyObject	*pModule = NULL;
	int		rval = AUTO_INSTALL_SUCCESS;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	if ((pName = PyString_FromString(AI_PARSE_MANIFEST_SCRIPT)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	}
	if (pModule != NULL) {
		/* Load the ai_parse_manifest module */
		pFunc = PyObject_GetAttrString(pModule, AI_SETUP_MANIFESTSERV);
		/* pFunc is a new reference */
		if (pFunc && PyCallable_Check(pFunc)) {
			pArgs = PyTuple_New(1);
			Py_INCREF(server_obj);
			PyTuple_SetItem(pArgs, 0, server_obj);

			/* Call the ai_parse_manifest */
			pRet = PyObject_CallObject(pFunc, pArgs);
			rval = PyInt_AS_LONG(pRet);
			Py_DECREF(pRet);
			Py_DECREF(pArgs);
		} else {
			auto_debug_print(AUTO_DBGLVL_ERR, "Python function "
			    "does not appear callable: %s\n",
			    AI_SETUP_MANIFESTSERV);
			rval = AUTO_INSTALL_FAILURE;
		}
	} else {
		PyErr_Print();
		auto_debug_print(AUTO_DBGLVL_ERR, "Call failed: %s\n",
		    AI_SETUP_MANIFESTSERV);
		rval = AUTO_INSTALL_FAILURE;
	}
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);
	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
	return (rval);
}

/*
 * Lookup a nodepath.
 *
 * The caller is responsible for freeing up
 * memory associated with the return value.
 * ai_free_manifest_values() is provided for this.
 */
char **
ai_lookup_manifest_values(PyObject *server_obj, char *path, int *len)
{
	PyObject	*pFunc;
	PyObject	*pName;
	PyObject 	*pArgs;
	PyThreadState	*myThreadState;
	PyObject 	*item;
	char		**rv;
	PyObject	*pModule = NULL;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	pName = PyString_FromString(AI_PARSE_MANIFEST_SCRIPT);
	assert(pName != NULL);
	if (pName == NULL) {
		PyErr_Print();
		auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
		    AI_LOOKUP_MANIFEST_VALUES);
		Py_Finalize();
		return (NULL);
	}

	pModule = PyImport_Import(pName);
	assert(pModule != NULL);
	if (pModule == NULL) {
		Py_DECREF(pName);
		PyErr_Print();
		auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
		    AI_LOOKUP_MANIFEST_VALUES);
		Py_Finalize();
		return (NULL);
	}

	/* Load the ai_parse_manifest module */
	pFunc = PyObject_GetAttrString(pModule, AI_LOOKUP_MANIFEST_VALUES);
	/* pFunc is a new reference */
	if (pFunc && PyCallable_Check(pFunc)) {
		PyObject *pRet = NULL;


		pArgs = PyTuple_New(2);
		/*
		 * INCREF server_obj as PyTuple_SetItem steals its reference.
		 * A stolen reference here means that pArgs owns the reference,
		 * and so when pArgs gets DECREFed, so does server_obj.
		 * INCREF server_obj so it remains intact after DECREFing pArgs.
		 *
		 * Note: no INCREF is needed for the second arg, as the thing
		 * which gets DECREFed via pArgs is an interim python object
		 * created from a native C string.
		 */
		Py_INCREF(server_obj);
		PyTuple_SetItem(pArgs, 0, server_obj);
		PyTuple_SetItem(pArgs, 1, PyString_FromString(path));

		pRet = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);
		if (pRet != NULL) {
			Py_ssize_t list_ln = PyList_Size(pRet);
			Py_ssize_t i;

			/* pass number of list elements to the caller */
			*len = (int)list_ln;

			if (list_ln > 0) {
				rv = malloc((list_ln + 1) * sizeof (char *));
				for (i = 0; i < list_ln; i++) {
					item = PyList_GetItem(pRet, i);
					rv[i] = strdup(PyString_AsString(item));
				}
				rv[list_ln] = NULL;
			}
			else
				rv = NULL;
			Py_DECREF(pRet);
		} else {
			Py_DECREF(pFunc);
			Py_DECREF(pModule);
			PyErr_Print();
			auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
			    AI_LOOKUP_MANIFEST_VALUES);
			rv = NULL;
		}
	} else {
		assert(!PyErr_Occurred());
		if (PyErr_Occurred())
			PyErr_Print();
		rv = NULL;
	}
	Py_XDECREF(pFunc);
	Py_DECREF(pModule);
	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
	return (rv);
}

/*
 * Free up memory associated with lists returned from ai_get_manifest_values()
 */
void
ai_free_manifest_value_list(char **value_list)
{
	char **curr;

	if (value_list == NULL) {
		return;
	}

	for (curr = value_list; *curr != NULL; curr++) {
		free (*curr);
	}

	free(value_list);
}

/*
 * This function must be called to delete all
 * state created by ai_create_manifestserv
 */
void
ai_destroy_manifestserv(PyObject *server_obj)
{
	if (Py_IsInitialized())
		Py_Finalize();
}
