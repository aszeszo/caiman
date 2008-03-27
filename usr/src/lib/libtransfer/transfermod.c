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
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libnvpair.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <limits.h>
#include <unistd.h>
#include <errno.h>
#include <pthread.h>
#include <sys/kbio.h>
#include <ls_api.h>
#include "transfermod.h"

#define	TRANSFER_PY_SCRIPT "transfer_mod"
#define	TRANSFER_PY_FUNC "perform_transfer"
#define	TRANSFER_ID "TRANSFERMOD"

static pthread_mutex_t tran_mutex = PTHREAD_MUTEX_INITIALIZER;
static char *tmpenv = "TMPDIR=/tmp";
static PyThreadState * mainThreadState = NULL;
static tm_callback_t progress;
static PyObject *tmod_logprogress(PyObject *self, PyObject *args);
static PyObject * tmod_abort_signaled(PyObject *self, PyObject *args);
static int do_abort = 0;
static int dbgflag = 0;

struct _TM_defines {
	char *name;
	int value;
} TM_defines[] = {
	{"TM_PERFORM_CPIO", TM_PERFORM_CPIO},
	{"TM_PERFORM_IPS", TM_PERFORM_IPS},
	{"TM_CPIO_ENTIRE", TM_CPIO_ENTIRE},
	{"TM_CPIO_LIST", TM_CPIO_LIST},
	{"TM_IPS_INIT", TM_IPS_INIT},
	{"TM_IPS_VERIFY", TM_IPS_VERIFY},
	{"TM_IPS_RETRIEVE", TM_IPS_RETRIEVE},
	{"TM_E_SUCCESS", TM_E_SUCCESS},
	{"TM_E_INVALID_TRANSFER_TYPE_ATTR", TM_E_INVALID_TRANSFER_TYPE_ATTR},
	{"TM_E_INVALID_CPIO_ACT_ATTR", TM_E_INVALID_CPIO_ACT_ATTR},
	{"TM_E_CPIO_ENTIRE_FAILED", TM_E_CPIO_ENTIRE_FAILED},
	{"TM_E_INVALID_CPIO_FILELIST_ATTR", TM_E_INVALID_CPIO_FILELIST_ATTR},
	{"TM_E_CPIO_LIST_FAILED", TM_E_CPIO_LIST_FAILED},
	{"TM_E_INVALID_IPS_ACT_ATTR", TM_E_CPIO_LIST_FAILED},
	{"TM_E_INVALID_IPS_SERVER_ATTR", TM_E_INVALID_IPS_SERVER_ATTR},
	{"TM_E_INVALID_IPS_MNTPT_ATTR", TM_E_INVALID_IPS_MNTPT_ATTR},
	{"TM_E_IPS_INIT_FAILED", TM_E_IPS_INIT_FAILED},
	{"TM_E_IPS_VERIFY_FAILED", TM_E_IPS_VERIFY_FAILED},
	{"TM_E_IPS_RETRIEVE_FAILED", TM_E_IPS_RETRIEVE_FAILED},
	{"TM_E_ABORT_FAILED", TM_E_ABORT_FAILED},
	{"TM_E_REP_FAILED", TM_E_REP_FAILED},
	{"TM_E_PYTHON_ERROR", TM_E_PYTHON_ERROR},
	{NULL, 0}
};


/*
 * Declare functions exported as Python methods via the tmod module.
 */
static PyMethodDef tmodMethods[] = {
	{"logprogress", tmod_logprogress, METH_VARARGS,
	    "Record the percentage completion of the transfer process"},
	{"abort_signaled", tmod_abort_signaled, METH_VARARGS,
	    "Return an integer indicating whether abort operation has been"
	    "signaled"},
	{NULL, NULL, 0, NULL}	/* Sentinel */
};

/*
 * Log an error message to a logfile or stderr.
 */
static void
Perror(const char *str)
{
	char *err;

	perror("<TRANSFERMOD> ");
	err = strerror(errno);
	ls_write_log_message(TRANSFER_ID, "%s: %s\n", str, err);
}


/*
 * Log the percentage completion to a logfile in an XML format that
 * the Orchestrator can understand. This is used if a callback func
 * has not been provided.
 */
static void
log_progress(const int percent, const char *message) {
	static FILE *plog = NULL;

	if (plog == NULL) {
		plog = fopen("/tmp/install_update_progress.out", "a+");
	}

	if (plog != NULL) {
		(void) fprintf(plog, "<progressStatus source=\"TransferMod\" "
		    "type=\"solaris-install\" percent=\"%d\" />\n", percent);
		(void) fflush(plog);
		if (percent == 100) {
			(void) fclose(plog);
		}
	}
}

/*
 * Callback invoked from Python script for progress reporting.
 */
static PyObject *
tmod_logprogress(PyObject *self, PyObject *args)
{
	int percent;
	char *message;

	if (!PyArg_ParseTuple(args, "is", &percent, &message))
		return (NULL);

	(*progress)(percent, message);

	return (Py_BuildValue("i", 0));
}

static PyObject *
tmod_abort_signaled(PyObject *self, PyObject *args)
{
	return (Py_BuildValue("i", do_abort));
}

void
add_TM_defines(PyObject *pDict)
{
	int i;

	/*
	 * Insert KIOCLAYOUT into module's namespace so that
	 * it can probe the keyboard layout.
	 */
	PyDict_SetItem(pDict, PyString_FromString("KIOCLAYOUT"),
	    Py_BuildValue("i", KIOCLAYOUT));

	/*
	 * Insert additional TM specific defines into namespace
	 */
	PyDict_SetItem(pDict, PyString_FromString("TRANSFER_ID"),
	    PyString_FromString(TRANSFER_ID));

	PyDict_SetItem(pDict, PyString_FromString(TM_ATTR_MECHANISM),
	    PyString_FromString(TM_ATTR_MECHANISM));
	PyDict_SetItem(pDict, PyString_FromString(TM_ATTR_IMAGE_INFO),
	    PyString_FromString(TM_ATTR_IMAGE_INFO));
	PyDict_SetItem(pDict, PyString_FromString(TM_CPIO_ACTION),
	    PyString_FromString(TM_CPIO_ACTION));
	PyDict_SetItem(pDict, PyString_FromString(TM_IPS_ACTION),
	    PyString_FromString(TM_IPS_ACTION));
	PyDict_SetItem(pDict,
	    PyString_FromString(TM_ATTR_TARGET_DIRECTORY),
	    PyString_FromString(TM_ATTR_TARGET_DIRECTORY));
	PyDict_SetItem(pDict, PyString_FromString(TM_CPIO_SRC_MNTPT),
	    PyString_FromString(TM_CPIO_SRC_MNTPT));
	PyDict_SetItem(pDict, PyString_FromString(TM_CPIO_DST_MNTPT),
	    PyString_FromString(TM_CPIO_DST_MNTPT));
	PyDict_SetItem(pDict, PyString_FromString(TM_CPIO_LIST_FILE),
	    PyString_FromString(TM_CPIO_LIST_FILE));

	for (i = 0; TM_defines[i].name != NULL; i++) {
		PyDict_SetItem(pDict, PyString_FromString(TM_defines[i].name),
		    Py_BuildValue("i", TM_defines[i].value));
	}
}

tm_errno_t
TM_perform_transfer(nvlist_t *nvl, tm_callback_t prog)
{
	PyObject *pName, *pModule, *pDict, *pFunc;
	PyObject *pArgs, *pValue, *pValues;
	int i, numpairs;
	tm_errno_t rv = TM_E_SUCCESS;
	nvpair_t *curr;
	char *mntpt;
	PyThreadState *myThreadState;

	if (pthread_mutex_lock(&tran_mutex) != 0) {
		Perror("Unable to acquire Transfer lock ");
		return (1);
	}

	if (nvlist_lookup_string(nvl, "mountpoint", &mntpt) != 0 &&
	    nvlist_lookup_string(nvl, TM_CPIO_DST_MNTPT, &mntpt) != 0) {
		Perror("Destination root mountpoint not provided. Bailing. ");
		return (1);
	}

	if (dbgflag)
		nvlist_add_string(nvl, "dbgflag", "true");
	else
		nvlist_add_string(nvl, "dbgflag", "false");

	if (prog == NULL) {
		progress = log_progress;
	} else {
		progress = prog;
	}

	numpairs = 0;
	curr = nvlist_next_nvpair(nvl, NULL);
	while (curr != NULL) {
		nvpair_t *next = nvlist_next_nvpair(nvl, curr);
		numpairs++;
		curr = next;
	}

	/*
	 * Set TMPDIR to avoid cpio depleting ramdisk space
	 */
	if (putenv(tmpenv) != 0) {
		Perror(tmpenv);
		rv = 1;
		goto done;
	}

	if (!Py_IsInitialized()) {
		Py_Initialize(); }
	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	/*
	 * Add the tmod module that exposes utility functions from the
	 * main program (Orchestrator) into the python script.
	 */
	Py_InitModule("tmod", tmodMethods);

	pName = PyString_FromString(TRANSFER_PY_SCRIPT);
	/* Error checking of pName left out */

	pModule = PyImport_Import(pName);
	Py_DECREF(pName);

	if (pModule != NULL) {

		pDict = PyModule_GetDict(pModule);
		add_TM_defines(pDict);
		/* Load the Transfer Module */
		pFunc = PyObject_GetAttrString(pModule, TRANSFER_PY_FUNC);
		/* pFunc is a new reference */

		if (pFunc && PyCallable_Check(pFunc)) {
			char *val;

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
				pValue = PyTuple_New(2);
				PyTuple_SetItem(pValue, 0,
				    PyString_FromString(name));

				if (strcmp(name, TM_ATTR_MECHANISM) == 0 ||
				    strcmp(name, TM_CPIO_ACTION) == 0 ||
				    strcmp(name, TM_IPS_ACTION) == 0) {
					uint32_t val;

					val = nvpair_value_uint32(curr, &val);
					PyTuple_SetItem(pValue, 1,
					    PyInt_FromLong(val));
				} else {
					nvpair_value_string(curr, &val);
					PyTuple_SetItem(pValue, 1,
					    PyString_FromString(val));
				}

				if (!pValue) {
					Py_DECREF(pArgs);
					Py_DECREF(pModule);
					ls_write_log_message(TRANSFER_ID, \
					    "Cannot convert argument\n");
					return (1);
				}
				/* pValue reference stolen here: */
				PyTuple_SetItem(pValues, i, pValue);
				curr = next;
			}
			PyTuple_SetItem(pArgs, 0, pValues);

			/* Call our transfer script */
			pValue = PyObject_CallObject(pFunc, pArgs);
			Py_DECREF(pArgs);
			if (pValue != NULL) {
				rv = PyInt_AsLong(pValue);
				Py_DECREF(pValue);
			} else {
				Py_DECREF(pFunc);
				Py_DECREF(pModule);
				PyErr_Print();
				ls_write_log_message(TRANSFER_ID, \
				    "Call failed: %s\n", TRANSFER_PY_FUNC);
				rv = TM_E_PYTHON_ERROR;
			}
		} else {
			if (PyErr_Occurred())
				PyErr_Print();
			Perror("Python error");
			rv = TM_E_PYTHON_ERROR;
		}
		Py_XDECREF(pFunc);
		Py_DECREF(pModule);
	} else {
		PyErr_Print();
		Perror("Python error");
		rv = TM_E_PYTHON_ERROR;
	}

	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
	Py_Finalize();

done:
	return (rv);
}

/*
 * Indicate cancellation of a transfer process if any.
 */
void
TM_abort_transfer()
{
	if (pthread_mutex_trylock(&tran_mutex) == EBUSY) {
		/*
		 * The mutex is unlocked so there is no transfer
		 * process running.
		 */
		(void) pthread_mutex_unlock(&tran_mutex);
	} else {
		do_abort = 1;
	}
}

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

int
main(void) {
	nvlist_t *nvl;
	tm_errno_t rv;

	ls_init_log();
	ls_init_dbg();

	/*
	 * Set PYTHONPATH to /tmp so python can find our script
	 * Used only for testing.
	 */
	if (putenv("PYTHONPATH=/tmp") != 0) {
		Perror(tmpenv);
		return (1);
	}

	ls_init_python_module();
	nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0);
	nvlist_add_string(nvl, "mountpoint", "/a");
	nvlist_add_uint32(nvl, TM_ATTR_MECHANISM, TM_PERFORM_CPIO);
	nvlist_add_uint32(nvl, TM_CPIO_ACTION, TM_CPIO_ENTIRE);
	TM_enable_debug();
	rv = TM_perform_transfer(nvl, NULL);
	nvlist_free(nvl);

	return (rv);
}

#endif
