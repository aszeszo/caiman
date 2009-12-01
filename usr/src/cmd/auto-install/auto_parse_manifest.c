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
#include "auto_install.h"

#define	AI_PARSE_MANIFEST_SCRIPT "osol_install.auto_install.ai_parse_manifest"
#define	AI_CREATE_MANIFESTSERV "ai_create_manifestserv"
#define	AI_LOOKUP_MANIFEST_VALUES "ai_lookup_manifest_values"

static PyThreadState * mainThreadState = NULL;

/*
 * The C interface to ai_create_manifestserv (python module)
 * This function takes a manifest file and hands it off to
 * the ManifestServ. It returns the socket thus created which
 * can then be used to lookup various paths.
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
	PyObject	*pFunc, *pModule = NULL, *pName;
	PyObject	*pArgs, *pValues;
	PyThreadState	*myThreadState;
	PyObject	*rv = NULL;

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
	if (pModule == NULL) {
		PyErr_Print();
		auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
		    AI_CREATE_MANIFESTSERV);
		Py_Finalize();
		return (NULL);
	}

	/* Load the ai_parse_manifest module */
	pFunc = PyObject_GetAttrString(pModule, AI_CREATE_MANIFESTSERV);
	/* pFunc is a new reference */
	if (pFunc && PyCallable_Check(pFunc)) {
		PyObject *pRet;

		pArgs = PyTuple_New(1);
		PyTuple_SetItem(pArgs, 0, PyString_FromString(filename));

		/* Call the ai_parse_manifest */
		pRet = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);
		if (pRet != NULL) {
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
			Py_DECREF(pFunc);
			Py_DECREF(pModule);
			PyErr_Print();
			auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
			    AI_CREATE_MANIFESTSERV);
			rv = NULL;
		}
	} else {
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
 * Lookup an path from the socket that was
 * created by calling ai_create_manifestserv
 *
 * The caller is responsible for freeing up
 * memory associated with the return value
 */
char **
ai_lookup_manifest_values(PyObject *server_obj, char *path, int *len)
{
	PyObject 	*pFunc, *pName, *pModule = NULL;
	PyObject 	*pArgs;
	PyThreadState	*myThreadState;
	PyObject 	*item;
	char		**rv;

	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	pName = PyString_FromString(AI_PARSE_MANIFEST_SCRIPT);
	if (pName == NULL) {
		PyErr_Print();
		auto_debug_print(AUTO_DBGLVL_INFO, "Call failed: %s\n",
		    AI_LOOKUP_MANIFEST_VALUES);
		Py_Finalize();
		return (NULL);
	}

	pModule = PyImport_Import(pName);
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
		PyTuple_SetItem(pArgs, 0, server_obj);
		PyTuple_SetItem(pArgs, 1, PyString_FromString(path));

		pRet = PyObject_CallObject(pFunc, pArgs);
		/*
		 * We intentionally don't do a DECREF on
		 * pArgs because it somehow decrements a
		 * reference count on the server_obj which
		 * results in it being garbage collected
		 */
		if (pRet != NULL) {
			Py_ssize_t list_ln = PyList_Size(pRet);
			Py_ssize_t i;

			/* pass number of list elements to the caller */
			*len = (int)list_ln;

			/*
			 * XXX this memory needs to be freed --
			 * where might that be?
			 */
			if (list_ln > 0) {
				rv = malloc(list_ln * sizeof (char *));
				for (i = 0; i < list_ln; i++) {
					item = PyList_GetItem(pRet, i);
					rv[i] = PyString_AsString(item);
					/*
					 * We intentionally don't do a DECREF
					 * on item here because it somehow
					 * results in the value in rv[i] being
					 * garbage collected. So, if rv[i] is
					 * passed as an argument to the transfer
					 * module it keels over as it tries to
					 * dereference rv[i]
					 *
					 * XXX needs investigation longer term
					 * Py_DECREF(item);
					 */
				}
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
 * This function must be called to delete all
 * state created by ai_create_manifestserv
 */
void
ai_destroy_manifestserv(PyObject *server_obj)
{
	if (Py_IsInitialized())
		Py_Finalize();
}
