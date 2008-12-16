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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <Python.h>
#include <libnvpair.h>
#include <ls_api.h>
#include <errno.h>
#include "transfermod.h"

#define	TRANSFER_PY_SCRIPT "transfer_mod"
#define	PERFORM_TRANSFER_FUNC "tm_perform_transfer"
#define	TRANSFER_ABORT_FUNC "tm_abort_transfer"
#define	TRANSFER_ID "TRANSFERMOD"
/*
 * Python is not able to find the transfer_mod.py module since it
 * is not in the "standard" python path.  Instead of making
 * every caller of this library set PYTHONPATH to point to the
 * subdirectory containing all the install related python modules,
 * the PYTHONPATH env variable will be set in this library before
 * python is initialized.
 */
#define	PY_PATH "PYTHONPATH=/usr/lib/python2.4/vendor-packages/osol_install"

static PyObject *tmod_logprogress(PyObject *self, PyObject *args);
static PyObject *tmod_set_callback(PyObject *self, PyObject *args);

static PyThreadState * mainThreadState = NULL;
static tm_callback_t progress;
static PyObject *py_callback = NULL;
static int dbgflag = 0;


void initlibtransfer();

/* Private python initialization structure */

static struct PyMethodDef libtransferMethods[] = {
	{"logprogress", tmod_logprogress, METH_VARARGS,
	    "Record the percentage completion of the transfer process"},
	{"set_py_callback", tmod_set_callback, METH_VARARGS,
	    "Save the Python callback"},
	{NULL, NULL, 0, NULL}
};

/* initialize module */
void
initlibtransfer()
{
	/* PyMODINIT_FUNC; */
	(void) Py_InitModule("libtransfer", libtransferMethods);
}

/*
 * Callback invoked from Python script for progress reporting.
 */
/* ARGSUSED */
static PyObject *
tmod_logprogress(PyObject *self, PyObject *args)
{
	int percent;
	char *message;

	/*
	 * If there is a python callback, then call it.
	 */
	if (py_callback != NULL) {
		PyEval_CallObject(py_callback, args);
		return (Py_BuildValue("i", 0));
	}

	/*
	 * No python callback, so call the C one.
	 */
	if (!PyArg_ParseTuple(args, "is", &percent, &message))
		return (Py_BuildValue("i", 0));

	if (progress != NULL) {
		(*progress)(percent, message);
	}

	return (Py_BuildValue("i", 0));
}

/*
 * Function to call to setup a Python function as the callback
 */
/* ARGSUSED */
static PyObject *
tmod_set_callback(PyObject *self, PyObject *args)
{
	PyObject	*callbck_temp;
	int		rval = 1;

	if (PyArg_ParseTuple(args, "O", &callbck_temp)) {
		if (PyCallable_Check(callbck_temp)) {
			py_callback = callbck_temp;  /* Remember new callback */
			rval = 0; /* success */
		}
	}
	return (Py_BuildValue("i", rval));
}

tm_errno_t
TM_perform_transfer_cpio(nvlist_t *nvl, tm_callback_t prog)
{
	return (TM_perform_transfer(nvl, prog));
}

/*
 * XXX there's a built in assumption about the
 * ordering -- fix
 */
tm_errno_t
TM_perform_transfer_ips(nvlist_t **nvl, tm_callback_t prog)
{
	int	status;

	/* first initialize ips */
	status = TM_perform_transfer(nvl[0], prog);
	if (status != TM_SUCCESS) {
		ls_write_log_message(TRANSFER_ID,
		    "IPS initialization failed\n");
		return (status);
	}
	ls_write_log_message(TRANSFER_ID, "IPS initilization finished\n");

	/* do the actual transfer */
	status = TM_perform_transfer(nvl[1], prog);
	if (status != TM_SUCCESS)
		ls_write_log_message(TRANSFER_ID,
		    "IPS transfer failed\n");

	ls_write_log_message(TRANSFER_ID, "IPS transfer finished\n");
	return (status);

}

/*
 * The C interface to tm_perform_transfer (python module)
 * This function will parse the nvlist and put the values
 * into a Tuple for use by the python method tm_perform_transfer.
 * If the user passes a callback in prog, the callback will be
 * registered.
 */
tm_errno_t
TM_perform_transfer(nvlist_t *nvl, tm_callback_t prog)
{
	PyObject	*pFunc, *pModule = NULL, *pName;
	PyObject	*pArgs, *pValues;
	nvpair_t	*curr;
	tm_errno_t	rv = TM_E_SUCCESS;
	int		i, numpairs = 0;
	PyThreadState	*myThreadState;

	if (dbgflag)
		nvlist_add_string(nvl, "dbgflag", "true");
	else
		nvlist_add_string(nvl, "dbgflag", "false");

	curr = nvlist_next_nvpair(nvl, NULL);
	while (curr != NULL) {
		nvpair_t *next = nvlist_next_nvpair(nvl, curr);
		numpairs++;
		curr = next;
	}

	if (!Py_IsInitialized()) {
		if (putenv(PY_PATH) != 0) {
			ls_write_log_message(TRANSFER_ID,
			    "Failed to set PYTHONPATH.  Error: %s\n",
			    strerror(errno));
			return (TM_E_PYTHON_ERROR);
		}
		Py_Initialize();
	}

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);
	progress = prog;

	pModule = NULL;
	if ((pName = PyString_FromString(TRANSFER_PY_SCRIPT)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	}
	if (pModule == NULL) {
		PyErr_Print();
		ls_write_log_message(TRANSFER_ID,
		    "Call failed: %s\n", PERFORM_TRANSFER_FUNC);
		Py_Finalize();
		return (TM_E_PYTHON_ERROR);
	}

	/* Load the Transfer Module */
	pFunc = PyObject_GetAttrString(pModule, PERFORM_TRANSFER_FUNC);
	/* pFunc is a new reference */
	if (pFunc && PyCallable_Check(pFunc)) {
		char *val;
		PyObject *pTuple;
		PyObject *pRet;

		pArgs = PyTuple_New(1);
		pValues = PyTuple_New(numpairs);
		curr = nvlist_next_nvpair(nvl, NULL);

		/*
		 * Add all the nvlist parameters to the Python
		 * function's argument list.
		 */
		for (i = 0; i < numpairs; ++i) {
			char *name;

			nvpair_t *next = nvlist_next_nvpair(nvl, curr);
			name = nvpair_name(curr);
			pTuple = PyTuple_New(2);
			PyTuple_SetItem(pTuple, 0,
			    PyString_FromString(name));

			if (strcmp(name, TM_ATTR_MECHANISM) == 0 ||
			    strcmp(name, TM_CPIO_ACTION) == 0 ||
			    strcmp(name, TM_IPS_ACTION) == 0) {
				uint32_t val;

				nvpair_value_uint32(curr, &val);
				PyTuple_SetItem(pTuple, 1,
				    PyInt_FromLong(val));
			} else if (strcmp(name, TM_IPS_IMAGE_CREATE_FORCE) ==
			    0) {
				boolean_t val;
				char *boolean_str;

				nvpair_value_boolean_value(curr, &val);
				boolean_str = val ? "true" : "false";
				PyTuple_SetItem(pTuple, 1,
				    PyString_FromString(boolean_str));
			} else {
				nvpair_value_string(curr, &val);
				PyTuple_SetItem(pTuple, 1,
				    PyString_FromString(val));
			}

			if (!pTuple) {
				Py_DECREF(pArgs);
				Py_DECREF(pModule);
				ls_write_log_message(TRANSFER_ID,
				    "Cannot convert argument\n");
				return (1);
			}
			/* pTuple reference stolen here: */
			PyTuple_SetItem(pValues, i, pTuple);
			curr = next;
		}
		PyTuple_SetItem(pArgs, 0, pValues);

		/* Call our transfer script */
		pRet = PyObject_CallObject(pFunc, pArgs);
		Py_DECREF(pArgs);
		if (pRet != NULL) {
			rv = PyInt_AsLong(pRet);
			Py_DECREF(pRet);
		} else {
			Py_DECREF(pFunc);
			Py_DECREF(pModule);
			PyErr_Print();
			ls_write_log_message(TRANSFER_ID,
			    "Call failed: %s\n", PERFORM_TRANSFER_FUNC);
			rv = TM_E_PYTHON_ERROR;
		}
	} else {
		if (PyErr_Occurred())
			PyErr_Print();
		rv = TM_E_PYTHON_ERROR;
	}
	Py_XDECREF(pFunc);
	Py_DECREF(pModule);
	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
	Py_Finalize();
	return (rv);
}

/*
 * Indicate cancellation of a transfer process if any.
 */
void
TM_abort_transfer()
{
	PyObject *pFunc, *pModule, *pName;

	if (!Py_IsInitialized()) {
		if (putenv(PY_PATH) != 0) {
			ls_write_log_message(TRANSFER_ID,
			    "Failed to set PYTHONPATH.  Error: %s\n",
			    strerror(errno));
		}
		Py_Initialize();
	}

	pName = PyString_FromString(TRANSFER_PY_SCRIPT);
	if (pName == NULL) {
		PyErr_Print();
		ls_write_log_message(TRANSFER_ID,
		    "Call failed: %s\n", TRANSFER_ABORT_FUNC);
		Py_Finalize();
		return;
	}

	pModule = PyImport_Import(pName);
	if (!pModule) {
		PyErr_Print();
		ls_write_log_message(TRANSFER_ID,
		    "Call failed: %s\n", TRANSFER_ABORT_FUNC);
		Py_Finalize();
		return;
	}

	/* Load the Transfer Module */
	pFunc = PyObject_GetAttrString(pModule, TRANSFER_ABORT_FUNC);
	/* pFunc is a new reference */
	if (pFunc && PyCallable_Check(pFunc)) {
		/* Call our transfer script */
		PyObject_CallObject(pFunc, NULL);
	} else {
		if (PyErr_Occurred())
		PyErr_Print();
		Py_Finalize();
		return;
	}
	Py_Finalize();
}

/* Enable debugging messages */
void
TM_enable_debug()
{
	dbgflag = 1;
}

#ifdef __TM_TEST__

void
show_progress(int percent)
{
	(void) fprintf(stderr, "%d\n", percent);
}

/*
 * Main test program to test the transfer module via the C
 * interface. If using this code, you will need to customize
 * the values to suit your situation. i.e. parameters like
 * "/export/home/ips1" will need to be changed to fit your
 * testing situation.
 */
int
main(void) {
	nvlist_t *nvl;
	tm_errno_t rv;

	/*
	 * Set PYTHONPATH to /tmp so python can find our script
	 * Used only for testing.
	 */
	if (putenv("PYTHONPATH=/tmp") != 0) {
		return (1);
	}
	TM_enable_debug();

#if 0
	/* test ips init */
	printf("Testing IPS init\n");
	nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0);
	nvlist_add_string(nvl, TM_IPS_INIT_MNTPT,  "/export/home/ips1");
	nvlist_add_uint32(nvl, TM_ATTR_MECHANISM, TM_PERFORM_IPS);
	nvlist_add_uint32(nvl, TM_IPS_ACTION, TM_IPS_INIT);
	nvlist_add_string(nvl, TM_IPS_PKG_URL, "http://ipkg.sfbay:29047");
	nvlist_add_string(nvl, TM_IPS_PKG_AUTH, "http://ipkg.sfbay:29047");
	rv = TM_perform_transfer(nvl, NULL);
	if (rv != 0) {
		printf("test FAILED\n");
	} else {
		printf("test PASSED\n");
	}
	nvlist_free(nvl);

	/* test ips verify */
	printf("Testing IPS contents verify\n");
	nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0);
	nvlist_add_string(nvl, TM_IPS_INIT_MNTPT,  "/export/home/ips1");
	nvlist_add_uint32(nvl, TM_ATTR_MECHANISM, TM_PERFORM_IPS);
	nvlist_add_uint32(nvl, TM_IPS_ACTION, TM_IPS_REPO_CONTENTS_VERIFY);
	nvlist_add_string(nvl, TM_IPS_PKGS,
	    "/export/home/jeanm/transfer_mod_test/pkg_file.txt");
	rv = TM_perform_transfer(nvl, NULL);
	if (rv != 0) {
		printf("test FAILED\n");
	} else {
		printf("test PASSED\n");
	}
	nvlist_free(nvl);
#endif
	/* test cpio entire */
	printf("Testing cpio entire\n");
	nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0);
	nvlist_add_string(nvl, TM_CPIO_DST_MNTPT,  "/test");
	nvlist_add_uint32(nvl, TM_ATTR_MECHANISM, TM_PERFORM_CPIO);
	nvlist_add_uint32(nvl, TM_CPIO_ACTION, TM_CPIO_ENTIRE);
	nvlist_add_string(nvl, TM_CPIO_SRC_MNTPT, "/lib");
	rv = TM_perform_transfer(nvl, NULL);
	if (rv != 0) {
		printf("test FAILED\n");
	} else {
		printf("test PASSED\n");
	}
	nvlist_free(nvl);

	return (rv);
}

#endif
