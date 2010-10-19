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

#include <Python.h>
#include <errno.h>
#include <string.h>
#include <sys/errno.h>
#include <libintl.h>
#include "liberrsvc.h"
#include "liberrsvc_priv.h"
#include "liberrsvc_defs.h"

#define	STD_ERR 2

/* The name of the Python module containing the functions we will call */
#define	ERRSVC_PY_MOD "osol_install.errsvc"

/* The names of the Python functions we will call */
#define	ERROR_INFO_CLASS "ErrorInfo"
#define	CLEAR_ERROR_LIST_FUNC "clear_error_list"
#define	SET_ERROR_DATA "set_error_data"
#define	DUMP_ALL_ERRORS_FUNC "__dump_all_errors__"
#define	GET_ERRORS_BY_MOD_ID "get_errors_by_mod_id"
#define	GET_ALL_ERRORS "get_all_errors"
#define	GET_ERRORS_BY_TYPE "get_errors_by_type"
#define	GET_ERR_TYPE "get_error_type"
#define	GET_MOD_ID "get_mod_id"
#define	GET_ERR_DATA_BY_TYPE "get_error_data_by_type"

/* Identifier for this library */
#define	ERRSVC_ID "LIBERRSVC"

/* Standard error messages */
#define	ERR_PY_FUNC gettext("ERROR - Unable to call Python function")
#define	ERR_PY_CALL gettext("ERROR - Python function call returned failure")
#define	ERR_INVAL_PARAM gettext("ERROR - Invalid Parameter passed to function")
#define	ERR_UNKNOWN gettext("UNKNOWN ERROR")

static PyThreadState *mainThreadState = NULL;
static char *empty_argv[1] = { "" };

int es_errno = 0;

/* ******************************************** */
/*		Private Functions		*/
/* ******************************************** */

/*
 * Convenience function for handling logging.
 * Initially will print to standard err. When
 * logging is enabled, the logging will print
 * to the log.
 */
void
_log_error(char *error_template, ...)
{
	va_list(ap);

	va_start(ap, error_template);
	vfprintf(stderr, error_template, ap);
	va_end(ap);

}

/*
 * Function:    _es_lib_assert
 *
 * Description: Check to see if a C error has occurred. If it has
 *		print an error message and abort.
 *
 * Parameters: None
 *
 * Return: None
 *
 * Scope: Private
 */
void
_es_lib_assert(void)
{
	const char *str_err = NULL;
	int err = 0;

	str_err = es_get_failure_reason_str();
	err = es_get_failure_reason_int();
	fprintf(stderr, "\tERROR: Library error:\n\t%d\n\t%s\n\tAborting.\n",
	    err ? err : -1,
	    str_err ? str_err : ERR_UNKNOWN);
#ifdef NDEBUG
	abort();
#endif
}

/*
 * Function:  _es_py_assert
 *
 * Description: Check if the specified Python exception has occurred.
 * 		If it has, print an error message and abort.
 *
 * Note: If compiled with -DNDEBUG, a NOOP variant of this function
 *       is invoked, which does nothing.
 *
 * Parameters: exc - Python object containing the python error.
 *
 * Return: None
 *
 * Scope: Private
 */

#ifdef NDEBUG
#define	_es_py_assert(x)	((void)0)	/* NOOP */
#else
void
_es_py_assert(PyObject *exc)
{
	PyObject *pType;
	PyObject *pValue;
	PyObject *pTraceback;
	PyObject *pString = NULL;
	char *type_str = NULL;
	char *val_str = NULL;

	if (! PyErr_Occurred()) {
		return;
	}

	if (! PyErr_ExceptionMatches(exc)) {
		return;
	}

	/* Fetching the error details also clears the error indicator */
	PyErr_Fetch(&pType, &pValue, &pTraceback);

	if ((pType != NULL) &&
	    ((pString = PyObject_Str(pType)) != NULL) &&
	    (PyString_Check(pString))) {
		type_str = PyString_AsString(pString);
	}

	if ((pValue != NULL) &&
	    ((pString = PyObject_Str(pValue)) != NULL) &&
	    (PyString_Check(pString))) {
		val_str = PyString_AsString(pString);
	}

	_log_error(gettext("ERROR: Python Exception "
	    "Raised:\n\t%s\n\t%s\nAborting.\n"),
	    type_str ? type_str : "UNKNOWN ERROR TYPE",
	    val_str ? val_str : "UNKNOWN ERROR VALUE\n");

	Py_XDECREF(pString);
	Py_XDECREF(pTraceback);
	Py_XDECREF(pValue);
	Py_XDECREF(pType);

	/*
	 * TODO: When logging becomes available this should be logged to the
	 * error log along with the traceback.
	 */
	fprintf(stderr, "\nPrinting out stack trace:\n");
	printstack(STD_ERR);

	abort();
}
#endif

/*
 * Function:  _initialize
 *
 * Description: Convenience function for initializing Python-C API
 *
 * Parameters: None
 *
 * Returns:
 *	B_TRUE on Success
 *	B_FALSE on Failure
 *
 * Scope: Private
 */
boolean_t
_initialize()
{
	if (!Py_IsInitialized()) {
		Py_Initialize();

		/*
		 * sys.argv needs to be initialized, just in case other
		 * modules access it.  It is not initialized automatically by
		 * Py_Initialize().
		 */
		PySys_SetArgv(1, empty_argv); /* Init sys.argv[]. */
	}

	if (PyErr_Occurred()) {
		return (B_FALSE);
	}

	return (B_TRUE);
}

/*
 * Function:  _load_module
 *
 * Description: Convenience function for loading Python module
 *
 * Parameters: mode_name - The name of the Python module being loaded.
 *
 * Returns:
 *	NULL on failure
 *	Pointer to PyObject on success
 *
 * Scope: Private
 */
static PyObject	*
_load_module(char *mod_name)
{
	PyObject	*pModule = NULL;
	PyObject	*pName;

	es_errno = 0;

	/* Make the name object and import the Python module */
	if ((pName = PyString_FromString(mod_name)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	}

	if (pModule == NULL) {
		_log_error(gettext("\t[%s] ERROR - Import of [%s] failed\n"),
		    ERRSVC_ID, mod_name);
		es_errno = EINVAL;
	}

	return (pModule);
}

/*
 * Function:  _start_threads
 *
 * Description: Convenience function for initializing threads for Python-C API
 *
 * Parameters: None
 *
 * Returns:
 *	Pointer to PyThreadState
 *	Null on failure
 *
 * Scope: Private
 */
static PyThreadState *
_start_threads()
{
	PyThreadState	*myThreadState;

	PyEval_InitThreads();
	mainThreadState = PyThreadState_Get();
	myThreadState = PyThreadState_New(mainThreadState->interp);
	PyThreadState_Swap(myThreadState);

	return (myThreadState);
}

/*
 * Function: _stop_threads
 *
 * Description: Convenience function for clearing threads for Python-C API
 *
 * Parameters: None
 *
 * Returns:
 *	void
 *
 * Scope: Private
 */
void
_stop_threads(PyThreadState *myThreadState)
{
	PyThreadState_Swap(mainThreadState);
	PyThreadState_Clear(myThreadState);
	PyThreadState_Delete(myThreadState);
}

/*
 * Function: _convert_pylist_to_err_info_list
 *
 * Description: Convenience function for converting a python list to
 *		an err_info_list_t linked list.
 *
 * Parameters: None
 *
 * Returns:
 *	A pointer to the new list on Success.
 *	NULL on failure
 *
 * Scope: Private
 */
err_info_list_t *
_convert_pylist_to_err_info_list(PyObject *pRet)
{
	err_info_list_t *new_list = NULL;
	err_info_list_t *new_list_tail = NULL;
	PyObject *item;
	int i;
	int len = 0;

	errno = 0;

	/* Check that there is something to convert first */
	if (pRet == NULL || !PySequence_Check(pRet)) {
		return (NULL);
	}

	len = (int)PySequence_Length(pRet);

	for (i = 0; i < len; i++) {
		err_info_list_t *new_item;

		item = PySequence_GetItem(pRet, i);

		new_item = (err_info_list_t *)malloc(sizeof (err_info_list_t));
		es_errno = errno;
		if (new_item == NULL) {
			_log_error(gettext("\t[%s] ERROR - Unable to "
			    "allocate memory for new list.\n"),
			    ERRSVC_ID);
			_es_lib_assert();
			break;
		}

		/* Update new list item */
		new_item->ei_err_info = (err_info_t *)item;
		new_item->ei_next = NULL;

		/* Insert to the list */
		if (new_list == NULL) {
			/* First element in the new list */
			new_list = new_item;
		} else if (new_list_tail != NULL) {
			new_list_tail->ei_next = new_item;
		} else {
			/* Shouldn't happen */
			_log_error(gettext("\t[%s] ERROR - Unable to insert "
			    "item into new linked list.\n"), ERRSVC_ID);
			break;
		}

		/* Update tail pointer to be new item */
		new_list_tail = new_item;
	}

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	return (new_list);
}

/* ******************************************** */
/*		Public Functions		*/
/* ******************************************** */

/*
 * Function: es_get_failure_reason_int
 *
 * Description: Accessor function for retrieveing the global error set
 *		internal to the liberrsvc library.
 *
 * Parameters: None
 *
 * Returns:
 *	The value of the global error that ets set if there is an error
 *	internal to the library
 *
 * Note: These errors will always be an errno.
 *
 * Scope: Public
 */
int
es_get_failure_reason_int(void)
{
	return (es_errno);
}

/*
 * Function: es_get_failure_reason_str
 *
 * Description: Accessor function that returns an error message
 *		string that maps to the error number.
 *
 * Parameters: None
 *
 * Returns: an error message string that maps to an
 *	    error number.
 *
 * Scope: Public
 */
const char *
es_get_failure_reason_str(void)
{
	return ((const char *)strerror(es_errno));
}

/*
 * Function: es_create_err_info
 *
 * Description: The C interface to create a Python ErrorInfo object.
 *
 * Parameters:	mod_id  - the string identifier for the module which
 *			  is setting the info for this error
 *		err_type - The error type
 *
 * Returns:
 *	ErrInfo Object on Success (cast to err_info_t)
 *	NULL on failure
 *
 * Scope: Public
 */
err_info_t *
es_create_err_info(char *mod_id, int err_type)
{
	PyThreadState	*myThreadState;
	PyObject	*pParamModId = NULL;
	PyObject	*pParamErrType = NULL;
	PyObject	*pModule = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pRet = NULL;

	errno = 0;
	es_errno = 0;

	if (_initialize() != B_TRUE) {
		return (NULL);
	}

	myThreadState = _start_threads();

	/*
	 * Prepare the params.
	 * We have 2 parameters to pass into Python, a
	 * string and an int.
	 */
	if (mod_id == NULL || strcmp(mod_id, "") == 0) {
		_log_error(gettext("\t[%s] %s [%s] (Invalid mod_id "
		    "parameter)\n"), ERRSVC_ID, ERR_PY_FUNC, ERROR_INFO_CLASS);
		es_errno = EINVAL;
		goto cleanup;
	}

	pParamModId = PyString_FromString(mod_id);
	if (pParamModId == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (Cannot create PyString)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, ERROR_INFO_CLASS);
		es_errno = EINVAL;
		goto cleanup;
	}

	pParamErrType = PyInt_FromLong((long)err_type);

	pModule = _load_module(ERRSVC_PY_MOD);
	if (pModule == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (Cannot load Python "
		    "module)\n"), ERRSVC_ID, ERR_PY_FUNC, ERROR_INFO_CLASS);
		goto cleanup;
	}

	pFunc = PyObject_GetAttrString(pModule, ERROR_INFO_CLASS);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("\t[%s] %s [%s] (Cannot call Python "
		    "function)\n"), ERRSVC_ID, ERR_PY_FUNC, ERROR_INFO_CLASS);

		es_errno = EINVAL;
		goto cleanup;
	}

	/* Call Python class instantiation function ErrorInfo() */
	pRet = PyObject_CallFunctionObjArgs(pFunc, pParamModId,
	    pParamErrType, NULL);
	if (pRet == NULL) {
		/*
		 * ErrorInfo() can raise a ValueError exception,
		 * so check if that happened.
		 */
		es_errno = EINVAL;
		_es_py_assert(PyExc_ValueError);
	}


	/* Cleanup code, shared by both the success and failure path */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);
	Py_XDECREF(pParamModId);
	Py_XDECREF(pParamErrType);

	_stop_threads(myThreadState);

	return ((err_info_t *)pRet);
}

/*
 * Function: es_free_err_info_list
 *
 * Description: Frees a linked list of err_info_list_t, such as that returned
 *		by the es_get_*() set of functions.
 *
 * Parameters:	list - The list of err_info_t's.
 *
 * Returns:
 *	None
 *
 * Scope: Public
 */
void
es_free_err_info_list(err_info_list_t *list)
{
	err_info_list_t *next;
	PyObject *err;

	while (list != NULL) {
		next = list->ei_next;
		err = (PyObject *)(list->ei_err_info);
		Py_XDECREF(err);
		free(list);
		list = next;
	}
}

/*
 * Function: es_free_errors
 *
 * Description: The C interface to Python function clear_error_list. This
 *		function free's all the errors created and set and all
 *		assosiated memory
 *
 * Parameters:
 *	None
 *
 * Returns:
 *	None
 *
 * Scope: Public
 */
void
es_free_errors(void)
{
	PyThreadState *myThreadState;
	PyObject *pModule = NULL;
	PyObject *pFunc = NULL;
	PyObject *pRet = NULL;
	PyObject *err;
	err_info_list_t *list;
	err_info_list_t *next;

	/*
	 * Before calling Python, decrement the references on each error.
	 * (Each error will have 1 outstanding reference from its initial
	 * creation.)
	 * In order to do that, we must call es_get_all_errors, which in
	 * turn will increment the references and allocate some memory.
	 * So, we also call es_free_err_into_list to tidy up.
	 */
	next = list = es_get_all_errors();
	while (next != NULL) {
		err = (PyObject *)(next->ei_err_info);
		Py_XDECREF(err);
		next = next->ei_next;
	}
	es_free_err_info_list(list);


	if (_initialize() != B_TRUE) {
		return;
	}

	myThreadState = _start_threads();

	pModule = _load_module(ERRSVC_PY_MOD);

	if (pModule != NULL) {
		pFunc = PyObject_GetAttrString(pModule, CLEAR_ERROR_LIST_FUNC);
	}

	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("\t[%s] %s [%s] (function)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, CLEAR_ERROR_LIST_FUNC);
	} else {
		/* Call Python function clear_error_list */
		pRet = PyObject_CallFunctionObjArgs(pFunc, NULL);

		if (pRet == NULL) {
			_log_error(gettext("\t[%s] %s [%s] (Call)\n"),
			    ERRSVC_ID, ERR_PY_FUNC, CLEAR_ERROR_LIST_FUNC);
		}
	}

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);

	_stop_threads(myThreadState);
}

/*
 * Function: es_set_err_data_int
 *
 * Description: The C interface to Python class method
 *		ErrorInfo.set_error_data() for setting integer data.
 *
 * Parameters:
 *	err - an instance of Python class ErrorInfo, eg as returned
 *	      from es_create_err_info().
 * 	type - The error data element type
 *	val - The value to be stored for this element type.
 *
 * Returns:
 *	B_TRUE on Success
 *	B_FALSE on Failure
 *
 * Scope: Public
 */
boolean_t
es_set_err_data_int(err_info_t *err, int type, int val)
{
	PyThreadState *myThreadState;
	PyObject *pMethod = NULL;
	PyObject *pRet = NULL;
	PyObject *pParamType = NULL;
	PyObject *pParamVal = NULL;
	boolean_t retval = B_FALSE;

	es_errno = 0;

	if (_initialize() != B_TRUE) {
		return (retval);
	}

	myThreadState = _start_threads();

	/*
	 * Prepare the params.
	 * We have 2 parameters to pass into Python,
	 * two ints (pParamType and pParamVal).
	 */
	pParamType = PyInt_FromLong((long)type);
	pParamVal = PyInt_FromLong((long)val);

	/*
	 * Check that the passed-in 'err' is a Python instance
	 * and that it has an attribute for the method we want
	 * to call
	 */
	if (err == NULL ||
	    ! PyObject_HasAttrString((PyObject *)err, SET_ERROR_DATA)) {
		_log_error(gettext("\t[%s] %s [%s] (invalid error object)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, SET_ERROR_DATA);
		es_errno = EINVAL;
		goto cleanup;
	}

	pMethod = PyString_FromString(SET_ERROR_DATA);
	if (pMethod == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (cannot create PyString)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, SET_ERROR_DATA);
		goto cleanup;
	}

	/* Call Python class method ErrorInfo.set_error_data */
	pRet = PyObject_CallMethodObjArgs((PyObject *)err, pMethod,
	    pParamType, pParamVal, NULL);
	if (pRet == NULL) {
		/*
		 * set_error_data() can raise ValueError or RuntimeError
		 * exceptions.  Assert that ValueError did not occur,
		 * but just return B_FALSE for RuntimeError.
		 */
		es_errno = EINVAL;
		_es_py_assert(PyExc_ValueError);
		goto cleanup;
	}

	retval = B_TRUE;

	/* Cleanup code, shared by both the success and failure path */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pParamVal);
	Py_XDECREF(pParamType);
	Py_XDECREF(pMethod);

	_stop_threads(myThreadState);

	return (retval);
}

/*
 * Function: es_set_err_data_str
 *
 * Description: The C interface to Python class method
 *		ErrorInfo.set_error_data() for setting integer data.
 *
 * Parameters:
 *	err - an instance of Python class ErrorInfo, eg as returned
 *	      from es_create_err_info().
 * 	type - The error data element type
 *	str - The string to be stored for this element type.
 *	      This can be an interpreted string similar to that used
 *	      for printf.
 *
 * Returns:
 *	B_TRUE on Success
 *	B_FALSE on Failure
 *
 * Scope: Public
 */
boolean_t
es_set_err_data_str(err_info_t *err, int type, char *str, ...)
{
	PyThreadState *myThreadState;
	PyObject *pMethod = NULL;
	PyObject *pRet = NULL;
	PyObject *pParamType = NULL;
	PyObject *pParamVal = NULL;
	boolean_t retval = B_FALSE;
	va_list ap;
	char *buf = NULL;
	int error = 0;

	es_errno = 0;
	errno = 0;

	if (_initialize() != B_TRUE) {
		return (retval);
	}

	myThreadState = _start_threads();

	/*
	 * Prepare the params.
	 * We have 2 parameters to pass into Python,
	 * an int (pParamType) and a string (pParamVal).
	 * The string can include formatting characters which are
	 * expanded from the optional varargs.
	 */
	pParamType = PyInt_FromLong((long)type);

	if (str == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (NULL string)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, SET_ERROR_DATA);
		es_errno = EINVAL;
		goto cleanup;
	}

	va_start(ap, str);
	(void) vasprintf(&buf, str, ap);
	error = errno;
	va_end(ap);

	if (buf == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (varargs)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, SET_ERROR_DATA);

		_es_lib_assert();
		goto cleanup;
	}

	pParamVal = PyString_FromString(buf);
	if (pParamVal == NULL) {
		_log_error(gettext("\t[%s] %s [%s] (Cannot create PyString)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, SET_ERROR_DATA);
		es_errno = EINVAL;
		goto cleanup;
	}

	/*
	 * Check that the passed-in 'err' is a Python instance
	 * and that it has an attribute for the method we want
	 * to call
	 */
	if (err == NULL ||
	    ! PyObject_HasAttrString((PyObject *)err, SET_ERROR_DATA)) {
		_log_error(gettext("\t[%s] %s [%s] (invalid error object)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, SET_ERROR_DATA);
		es_errno = EINVAL;
		goto cleanup;
	}

	pMethod = PyString_FromString(SET_ERROR_DATA);
	if (pMethod == NULL) {
		_log_error(gettext("\t[%s] %s[%s] (String)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, SET_ERROR_DATA);
		es_errno = EINVAL;
		goto cleanup;
	}

	/* Call Python class method ErrorInfo.set_error_data */
	pRet = PyObject_CallMethodObjArgs((PyObject *)err, pMethod,
	    pParamType, pParamVal, NULL);
	if (pRet == NULL) {
		/*
		 * set_error_data() can raise ValueError or RuntimeError
		 * exceptions.  Assert that ValueError did not occur,
		 * but just return B_FALSE for RuntimeError.
		 */
		es_errno = EINVAL;
		_es_py_assert(PyExc_ValueError);
		goto cleanup;
	}

	retval = B_TRUE;

	/* Cleanup code, shared by both the success and failure path */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pParamVal);
	Py_XDECREF(pParamType);
	Py_XDECREF(pMethod);
	if (buf != NULL) {
		free(buf);
	}

	_stop_threads(myThreadState);

	return (retval);
}

/*
 * Function: es_get_errors_by_modid
 *
 * Description:
 *	The C interface to Python module method get_errors_by_modid()
 *	for getting a list of errors based on module id.
 *
 * Parameters:
 *	mod_id - string that represents the module id provided when
 *		 creating errors using es_create_err_info()
 * Returns:
 *	err_info_list_t linked list on Success
 *	NULL on Failure
 *
 * Note:
 *	The consumer is resposible to free the linked list of err_info_list_t
 *	returned using es_free_err_info_list().
 *
 * Scope: Public
 */
err_info_list_t *
es_get_errors_by_modid(char *mod_id)
{
	PyThreadState *myThreadState;
	PyObject *pParamModId = NULL;
	PyObject *pModule = NULL;
	PyObject *pFunc = NULL;
	PyObject *pRet = NULL;
	err_info_list_t *return_list = NULL;

	if (_initialize() != B_TRUE) {
		return (NULL);
	}

	myThreadState = _start_threads();

	/*
	 * Prepare the params.
	 * We have 1 parameters to pass into Python, a
	 * string.
	 */
	pParamModId = PyString_FromString(mod_id);
	if (pParamModId == NULL) {
		_log_error(gettext("[%s] %s [%s] (String)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, GET_ERRORS_BY_MOD_ID);
	}

	if (pParamModId != NULL) {
		pModule = _load_module(ERRSVC_PY_MOD);
	}

	if (pModule != NULL) {
		pFunc = PyObject_GetAttrString(pModule, GET_ERRORS_BY_MOD_ID);
	}

	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("[%s] %s [%s] (function)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, GET_ERRORS_BY_MOD_ID);
		es_errno = EINVAL;
	} else {
		/* Call Python function get_errors_by_modid */
		pRet = PyObject_CallFunctionObjArgs(pFunc, pParamModId, NULL);
		if (pRet == NULL) {
			_log_error(gettext("[%s] %s [%s] (Call)\n"),
			    ERRSVC_ID, ERR_PY_CALL, GET_ERRORS_BY_MOD_ID);
			_es_py_assert(PyExc_ValueError);
		}
	}

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	/* Convert returned Python List to a linked list of err_info_list_t */
	return_list = _convert_pylist_to_err_info_list(pRet);

	Py_XDECREF(pRet);
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);
	Py_XDECREF(pParamModId);

	_stop_threads(myThreadState);

	return (return_list);
}

/*
 * Function: es_get_all_errors
 *
 * Description:
 *	The C interface to Python module method get_all_errors()
 *	for getting a list of all errors known to the error service.
 *
 * Parameters:
 *	None
 *
 * Returns:
 *	err_info_list_t linked list on Success
 *	NULL on Failure
 *
 * Note:
 *	The consumer is resposible to free the linked list of err_info_list_t
 *	returned using es_free_err_info_list().
 *
 * Scope: Public
 */
err_info_list_t *
es_get_all_errors()
{
	PyThreadState *myThreadState;
	PyObject *pModule = NULL;
	PyObject *pFunc = NULL;
	PyObject *pRet = NULL;
	err_info_list_t *return_list = NULL;

	if (_initialize() != B_TRUE) {
		return (NULL);
	}

	myThreadState = _start_threads();

	pModule = _load_module(ERRSVC_PY_MOD);

	if (pModule != NULL) {
		pFunc = PyObject_GetAttrString(pModule, GET_ALL_ERRORS);
	}

	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("[%s] %s [%s] (function)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, GET_ALL_ERRORS);
	} else {
		/* Call Python function get_all_errors */
		pRet = PyObject_CallFunctionObjArgs(pFunc, NULL);

		if (pRet == NULL) {
			_log_error(gettext("[%s] %s [%s] (Call)\n"),
			    ERRSVC_ID, ERR_PY_FUNC, GET_ALL_ERRORS);
			es_errno = EINVAL;
			_es_py_assert(PyExc_ValueError);
		}
	}

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	/* Convert returned Python List to a linked list of err_info_list_t */
	return_list = _convert_pylist_to_err_info_list(pRet);

	Py_XDECREF(pRet);
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);

	_stop_threads(myThreadState);

	return (return_list);
}

/*
 * TODO: Move this function to the private function block
 * The C interface to Python function __dump_all_errors__.
 * (mainly for testing purposes)
 */
boolean_t
es__dump_all_errors__(void)
{
	PyThreadState *myThreadState;
	PyObject *pModule = NULL;
	PyObject *pFunc = NULL;
	PyObject *pRet = NULL;
	boolean_t retval = B_FALSE;

	if (_initialize() != B_TRUE) {
		return (retval);
	}

	myThreadState = _start_threads();

	pModule = _load_module(ERRSVC_PY_MOD);

	if (pModule != NULL) {
		pFunc = PyObject_GetAttrString(pModule, DUMP_ALL_ERRORS_FUNC);
	}

	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("[%s] %s [%s] (function)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, DUMP_ALL_ERRORS_FUNC);
		es_errno = EINVAL;
	} else {
		/* Call Python function __dump_all_errors__ */
		pRet = PyObject_CallFunctionObjArgs(pFunc, NULL);

		if (pRet == NULL) {
			_log_error(gettext("[%s] %s [%s] (Call)\n"),
			    ERRSVC_ID, ERR_PY_CALL, DUMP_ALL_ERRORS_FUNC);
			_es_py_assert(PyExc_ValueError);
		} else {
			retval = B_TRUE;
		}
	}

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);

	_stop_threads(myThreadState);

	return (retval);
}

/*
 * Function:    es_get_errors_by_type
 *
 * Description: The C interface to Python module function
 *              get_errors_by_type. Returns a list of errors that
 *              have the given error_type. The list of errors should
 *              be freed using es_free_err_info_list when finished.
 *
 * Parameters:  err_type - An integer value that represents an error type
 *              list_is_empty - Flag indicating that there were no errors
 *				to put in the list.
 *
 * Return:
 *              On success, an err_info_list_t list of errors that are
 *              associated with the given error type.
 *
 *              On failure, returns NULL and sets the list_is_empty flag
 *		to true.
 *		The list_is_empty flag is used in order to distinguish
 *		between whether we returned NULL because no list
 *		existed or because there was a problem.
 * Scope: Public
 */
err_info_list_t *
es_get_errors_by_type(int err_type, boolean_t *list_is_empty)
{
	PyObject 	*pModule = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pRet = NULL;
	PyThreadState	*myThreadState;
	PyObject	*pParamErrType = NULL;
	err_info_list_t	*return_list = NULL;

	*list_is_empty = B_FALSE;

	if (_initialize() != B_TRUE) {
		return (return_list);
	}

	myThreadState = _start_threads();

	pParamErrType = PyInt_FromLong((long)err_type);
	pModule = _load_module(ERRSVC_PY_MOD);

	if (pModule == NULL) {
		goto cleanup;
	}

	/* Retrieve the attribute from the module */
	pFunc = PyObject_GetAttrString(pModule, GET_ERRORS_BY_TYPE);

	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_log_error(gettext("[%s] %s [%s] (function)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, GET_ERRORS_BY_MOD_ID);
		es_errno = EINVAL;
		goto cleanup;
	}

	/* Make the function call with the error type provided */
	pRet = PyObject_CallFunctionObjArgs(pFunc, pParamErrType, NULL);

	if (pRet != NULL) {
		/*
		 * Convert returned Python List to a linked list of
		 * err_info_list_t
		 */
		return_list = _convert_pylist_to_err_info_list(pRet);
	} else if (PyErr_Occurred()) {
		_log_error(gettext("[%s] %s [%s] (Call)\n"),
		    ERRSVC_ID, ERR_PY_CALL, GET_ERRORS_BY_TYPE);
		es_errno = EINVAL;
	} else {
		/*
		 * Fall through and cleanup
		 */
		*list_is_empty = B_TRUE;
	}

	/* Cleanup code, shared by both the success and failure path */
cleanup:

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pFunc);
	Py_XDECREF(pModule);
	Py_XDECREF(pParamErrType);

	_stop_threads(myThreadState);

	return (return_list);
}

/*
 * Function:	es_get_err_type(err_info_t err)
 *
 * Description:	The C interface to Python class method ErrorInfo.get_error_type.
 * 		Queries the error information and returns the error type.
 *
 * Parameters:  err_info_t - A structure containing information for
 *			     an error.
 *
 * Return:	On success, returns an integer value that
 *		represents an error type as defined in enum
 *		err_type in liberrsvc_defs.h.
 *
 *		On failure, returns -1
 * Scope:
 *	Public
 */
int
es_get_err_type(err_info_t *err)
{
	PyObject	*pMethod = NULL;
	PyObject	*pRet = NULL;
	PyThreadState	*myThreadState;
	int		retvalue = -1;
	long		py_retval;

	es_errno = 0;

	if (err == NULL)
		return (retvalue);

	if (_initialize() != B_TRUE)
		return (retvalue);

	myThreadState = _start_threads();

	if (! PyObject_HasAttrString((PyObject *)err, GET_ERR_TYPE)) {
		_log_error(gettext("[%s] %s [%s] (attribute)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, GET_ERR_TYPE);
		es_errno = EINVAL;
		goto cleanup;
	}

	/* Load the python module containing the module functions */
	pMethod = PyString_FromString(GET_ERR_TYPE);
	if (pMethod == NULL) {
		_log_error(gettext("[%s] %s [%s] (String)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, GET_ERR_TYPE);
		goto cleanup;
	}

	/* Make the Call to the Python method */
	pRet = PyObject_CallMethodObjArgs((PyObject *)err, pMethod, NULL);

	if (pRet == NULL || !PyInt_Check(pRet)) {
		_log_error(gettext("[%s] %s [%s] (Call)\n"),
		    ERRSVC_ID, ERR_PY_CALL, GET_ERR_TYPE);
		goto cleanup;
	}

	/* Convert the Python integer object back into a C int */
	py_retval = PyInt_AsLong(pRet);
	if (py_retval != -1 && !PyErr_Occurred())
		retvalue = (int)py_retval;

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pMethod);

	_stop_threads(myThreadState);

	return (retvalue);
}

/*
 * Function:    es_get_err_mod_id
 *
 * Description:	The C interface to Python class method ErrorInfo.get_mod_id.
 *		Queries the error information and returns the
 *		returns the mod id string.
 *
 * Parameters:  err - A structure containing information for
 *		      an error.
 *
 * Return:
 *		On success, returns a module id string.
 *
 *		On failure, returns NULL
 * Scope:
 *	Public
 */
char *
es_get_err_mod_id(err_info_t *err)
{
	PyObject	*pMethod = NULL;
	PyObject	*pRet = NULL;
	PyThreadState	*myThreadState;
	char		*retval = NULL;

	es_errno = 0;
	errno = 0;

	if (err == NULL)
		return (retval);

	if (_initialize() != B_TRUE)
		return (NULL);

	myThreadState = _start_threads();

	if (!PyObject_HasAttrString((PyObject *)err, GET_MOD_ID)) {
		_log_error(gettext("[%s] %s [%s] (attribute)\n"),
		    ERRSVC_ID, ERR_INVAL_PARAM, GET_MOD_ID);
		es_errno = EINVAL;
		goto cleanup;
	}
	pMethod = PyString_FromString(GET_MOD_ID);
	if (pMethod == NULL) {
		_log_error(gettext("[%s] %s [%s] (String)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, GET_MOD_ID);
		goto cleanup;
	}

	/* Make the call to the Python method */
	pRet = PyObject_CallMethodObjArgs((PyObject *)err, pMethod, NULL);

	/* Check to see if the Python call failed to return a string */
	if (PyString_Check(pRet)) {
		int err_num = 0;
		retval = strdup(PyString_AsString(pRet));
		err_num = errno;
		if (retval == NULL) {
			es_errno = err_num;
			_es_lib_assert();
		}
	} else {
		_es_py_assert(PyExc_ValueError);
	}


	/* Cleanup that is shared by both the success and failure path */
cleanup:

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pRet);
	Py_XDECREF(pMethod);

	_stop_threads(myThreadState);

	return (retval);
}

/*
 * Function:    es_get_err_data_int_by_type
 *
 * Description: The C interface to the Python class method
 *              ErrorInfo.get_error_data_by_type. Queries the error
 *              information and returns the error integer based on the
 *              element type.
 *
 * Parameters:  err             - A structure containing information for
 *				  an error.
 *              elem_type       - An integer data element type.
 *              err_int         - The address of a location for an error
 *				  integer to be stored. The check that a NULL
 *				  pointer hasn't been passed in should
 *                                be done by the consumer using this interface.
 * Return:
 *                              On success, populates err_int with an error
 *				integer number and returns B_TRUE.
 *
 *                              On failure, returns B_FALSE.
 * Scope:
 *	Public
 */
boolean_t
es_get_err_data_int_by_type(err_info_t *err, int elem_type, int *err_int)
{
	PyThreadState	*myThreadState;
	PyObject	*pMethod = NULL;
	PyObject	*pElemType = NULL;
	PyObject	*pErrInt = NULL;
	int		pRetVal;
	boolean_t	retval = B_FALSE;

	es_errno = 0;

	if (err == NULL) {
		es_errno = EINVAL;
		return (retval);
	}

	if (_initialize() != B_TRUE)
		return (retval);

	myThreadState = _start_threads();

	pElemType = PyInt_FromLong((long)elem_type);

	if (!PyObject_HasAttrString((PyObject *)err, GET_ERR_DATA_BY_TYPE)) {
		_log_error(gettext("[%s] %s [%s] (attribute)\n"), ERRSVC_ID,
		    ERR_INVAL_PARAM, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		goto cleanup;
	}
	pMethod = PyString_FromString(GET_ERR_DATA_BY_TYPE);
	if (pMethod == NULL) {
			_log_error(gettext("[%s] %s [%s] (String)\n"),
			    ERRSVC_ID, ERR_PY_FUNC, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		goto cleanup;
	}

	/* Make the Call to the Python method */
	pErrInt = PyObject_CallMethodObjArgs((PyObject *)err, pMethod,
	    pElemType, NULL);

	/* Check to see if the Python call failed to return an integer */
	if (pErrInt == NULL) {
		_log_error(gettext("[%s] %s [%s] (Call)\n"),
		    ERRSVC_ID, ERR_PY_CALL, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		_es_py_assert(PyExc_ValueError);
		goto cleanup;
	}
	if (PyInt_Check(pErrInt)) {

		/* Convert the Python integer object back into a C int */
		pRetVal = PyInt_AsLong(pErrInt);
		if (!PyErr_Occurred()) {
			*err_int = (int)pRetVal;
			retval = B_TRUE;
		}
	}

	/* Cleanup that is shared by both the success and failure paths */
cleanup:

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pElemType);
	Py_XDECREF(pErrInt);
	Py_XDECREF(pMethod);

	_stop_threads(myThreadState);

	return (retval);
}

/*
 * Function:    es_get_err_data_str_by_type
 *
 * Description:	The C interface to Python class method
 *		ErrorInfo.get_error_data_by_type.
 *		Queries the error information and returns the error
 *		data number based on the element type.
 *
 * Parameters:	err             -A structure containing information for
 *                               an error.
 *		elem_type       -A data element type
 *		err_str         -The pointer to an address for an error string.
 *
 * Return:	On success, err_str contains a pointer to an an error string.
 *		The consumer must free the memory with free() when finished.
 *		Returns B_TRUE.
 *
 *		On failure, returns B_FALSE.
 *
 * Scope:
 *	Public
 */
boolean_t
es_get_err_data_str_by_type(err_info_t *err, int elem_type, char **err_str)
{
	PyThreadState	*myThreadState;
	PyObject	*pMethod = NULL;
	PyObject	*pElemType = NULL;
	PyObject	*pErrStr = NULL;
	boolean_t	retval = B_FALSE;
	int		err_num = 0;

	errno = 0;
	es_errno = 0;


	if (err == NULL) {
		es_errno = EINVAL;
		return (retval);
	}

	if (_initialize() != B_TRUE)
		return (retval);

	myThreadState = _start_threads();

	pElemType = PyInt_FromLong((long)elem_type);

	if (! PyObject_HasAttrString((PyObject *)err, GET_ERR_DATA_BY_TYPE)) {
		_log_error(gettext("[%s] %s [%s] (attribute)\n"), ERRSVC_ID,
		    ERR_INVAL_PARAM, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		goto cleanup;
	}
	pMethod = PyString_FromString(GET_ERR_DATA_BY_TYPE);
	if (pMethod == NULL) {
		_log_error(gettext("[%s] %s [%s] (String)\n"),
		    ERRSVC_ID, ERR_PY_FUNC, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		goto cleanup;
	}

	/* Make the call to the Python method */
	pErrStr = PyObject_CallMethodObjArgs((PyObject *)err, pMethod,
	    pElemType, NULL);

	/* Check to see if the Python call failed to return a string */
	if (pErrStr == NULL) {
		_log_error(gettext("[%s] %s [%s] (Call)\n"), ERRSVC_ID,
		    ERR_PY_CALL, GET_ERR_DATA_BY_TYPE);
		es_errno = EINVAL;
		_es_py_assert(PyExc_ValueError);
		goto cleanup;
	}

	if (PyString_Check(pErrStr)) {
		/*
		 * if pErrStr is not NULL but it also not a String
		 * (eg it's None) then do nothing and return B_FALSE
		 */
		*err_str = strdup(PyString_AsString(pErrStr));
		err_num = errno;
		if (err_str != NULL)
			retval = B_TRUE;
		else
			es_errno = err_num;
	}

	/* Cleanup that is shared by both the success and failure path */
cleanup:

	if (PyErr_Occurred()) {
		PyErr_Print();
	}

	Py_XDECREF(pElemType);
	Py_XDECREF(pErrStr);
	Py_XDECREF(pMethod);

	_stop_threads(myThreadState);

	return (retval);
}
