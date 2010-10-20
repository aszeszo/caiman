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
 *
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 *
 */

/*
 * To run this test program against a local build, you should first, either:
 * A - run a nightly build, OR
 * B - do the following:
 *     - 'make install' in parent dirrectory (usr/src/lib/install_logging)
 *     - 'make install' in usr/src/lib/install_logging_pymod
 *     - 'make install' in usr/src/lib/install_common
 *       (this is needed to create the file:
 * proto/root_i386/usr/lib/python2.6/vendor-packages/solaris_install/__init__.py)
 *     - 'make install' in usr/src/lib/install_engine
 *        (this creates the engine in osol_install)
 *
 *
 * and then:
 * - export \
 * PYTHONPATH=../../../../../proto/root_i386/usr/lib/python2.6/vendor-packages
 *   (adjust "i386" for SPARC)
 * - Run ./tlogger at the command line
 */


#include "../logger.h"

#define	ENGINE_PY_MOD "solaris_install.engine"
#define	LOGGING_PY_MOD "logging"
#define	INSTALL_LOGGING_PY_MOD "solaris_install.logger"

extern logger_t *test_setup();
extern boolean_t test_set_logger_class();
extern boolean_t test_add_progress_handler();
extern boolean_t test_addhandler();
extern boolean_t test_close_logging();
extern boolean_t test_get_logger();
extern boolean_t test_log_message();
extern boolean_t test_report_progress();
extern boolean_t test_report_progress_fail();
extern boolean_t test_set_log_level();
extern boolean_t test_transfer_destonly();
extern boolean_t test_transfer_srclog();
extern boolean_t test_addstrmhandler();


/* Initializes the Python Interpreter */
boolean_t
_init_py()
{
	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	if (PyErr_Occurred()) {
		return (B_FALSE);
	}

	return (B_TRUE);
}

/* Loads Python Modules */
static PyObject *
_load_module(char *mod_name)
{
	PyObject	*pModule = NULL;
	PyObject	*pName;

	/* Make the name object and import the Python module */
	if ((pName = PyString_FromString(mod_name)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	} else {
		PyErr_Print();
	}

	return (pModule);
}


/*
 * Function:  _init_eng
 *
 * Description: This Function is used to initialize an engine
 *              interface for test purposes.
 *
 * Parameters: None
 *
 * Returns:
 *      NULL on failure
 *      Pointer to PyObject on success
 *
 * Scope: Test Module
 */
PyObject *
_init_eng()
{
	PyObject	*pModule = NULL;
	PyObject	*pClass = NULL;
	PyObject	*pTupArgs = NULL;
	PyObject	*pInstance = NULL;
	char		*eng = "InstallEngine";

	if (_init_py() != B_TRUE) {
		return (pInstance);
	}

	/* Load the Python module */
	pModule = _load_module(ENGINE_PY_MOD);
	if (pModule == NULL) {
		fprintf(stderr, "_init_engine:no module loaded\n");
		goto cleanup;
	}

	/* Instantiate the engine */
	pClass = PyObject_GetAttrString(pModule, eng);
	if (pClass == NULL) {
		fprintf(stderr, "_init_eng:no class found\n");
		goto cleanup;
	}

	/* Create an instance of the class */
	if (!PyCallable_Check(pClass)) {
		fprintf(stderr, "_init_eng:class not callable\n");
		goto cleanup;
	}

	/* Call the class instance with arguments */
	pTupArgs = PyTuple_New(0);
	pInstance = PyObject_Call(pClass, pTupArgs, NULL);
	if (pInstance == NULL) {
		fprintf(stderr, "_init_eng:instance failed\n");
		goto cleanup;
	}

cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pClass);
	Py_XDECREF(pTupArgs);

	return (pInstance);

}


int
main(int argc, char **argv) {
	int 		passes = 0;
	int 		fails = 0;
	PyObject 	*pTestEngine = NULL;

	printf("Testing Install Logging (C side)\n\n");

	/* Initialize a test engine */
	pTestEngine = _init_eng();
	if (pTestEngine == NULL) {
		fprintf(stderr, "No engine. Can't continue\n");
		return;
	}

	if (test_set_logger_class()) {
		passes++;
	} else {
		fails++;
	}

	if (test_get_logger()) {
		passes++;
	} else {
		fails++;
	}

	if (test_set_log_level()) {
		passes++;
	} else {
		fails++;
	}

	if (test_addhandler()) {
		passes++;
	} else {
		fails++;
	}

	if (test_addstrmhandler()) {
		passes++;
	} else {
		fails++;
	}

	if (test_add_progress_handler()) {
		passes ++;
	} else {
		fails++;
	}

	if (test_log_message()) {
		passes++;
	} else {
		fails++;
	}

	if (test_report_progress()) {
		passes++;
	} else {
		fails++;
	}

	if (test_report_progress_fail()) {
		passes++;
	} else {
		fails++;
	}

	if (test_transfer_srclog()) {
		passes++;
	} else {
		fails++;
	}

	if (test_transfer_destonly()) {
		passes++;
	} else {
		fails++;
	}

        if (test_close_logging()) {
		passes++;
	} else {
		fails++;
	}


	printf("\n\nSummary of tests\n");
	printf("================\n");
	printf("Total number of tests run:\t%d\n", (passes + fails));
	printf("Number of tests that PASSED:\t%d\n", passes);
	printf("Number of tests that FAILED:\t%d\n", fails);
	printf("\nFinished.\n");

	return (0);
}
