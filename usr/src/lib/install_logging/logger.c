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
#include <Python.h>
#include "logger.h"

/* Parameters for error reporting */
char *LOG_MOD_ID = "LOG";

/* The name of the Python module containing the functions we will call */
#define LOGSVC_PY_MOD "solaris_install.logger"
#define	LOGGING_PY_MOD "logging"
#define	LOGGING_PY_HANDLER_MOD "logging.handlers"

/* The names of the Python functions that are called */
#define	LOGGING_BASIC_CONFIG_FUNC "basicConfig"
#define	LOGGING_GET_LOGGER_FUNC "getLogger"
#define	LOGGING_TRANSFER_LOG "transfer_log"
#define	LOGGING_SET_LOGGER_CLASS "setLoggerClass"
#define	LOGGING_ADD_HANDLER "addHandler"
#define	SET_LOG_LEVEL "setLevel"
#define	GET_LEVEL_NAME "getLevelName"
#define	REPORT_PROGRESS "report_progress"
#define	CLOSE "close"

/* The Logging sub-class for logging */
#define	LOGGER_CLASS "InstallLogger"

/*
 * Function:  _initialize_py
 *
 * Description: Convenience function for initializing Python-C API
 *
 * Parameters: None
 *
 * Returns:
 *      B_TRUE on Success
 *      B_FALSE on Failure
 *
 * Scope: Private
 */
boolean_t
_initialize_py()
{
	if (!Py_IsInitialized()) {
		Py_Initialize();
	}

	if (PyErr_Occurred()) {
		return (B_FALSE);
	}

	return (B_TRUE);
}

/*
 * Function:  _load_module
 *
 * Description: Convenience function for loading Python modules
 *
 * Parameters: mode_name - The name of the Python module being loaded.
 *
 * Returns:
 *      NULL on failure
 *      Pointer to PyObject on success
 *
 * Scope: Private
 */
static PyObject *
_load_module(char *mod_name)
{
	PyObject	*pModule = NULL;
	PyObject	*pName;

	/* Make the name object and import the Python module */

	if ((pName = PyString_FromString(mod_name)) != NULL) {
		pModule = PyImport_Import(pName);
		Py_DECREF(pName);
	}

	return (pModule);
}

/*
 * Function:  _report_error
 *
 * Description: This Function is used to record generated errors.
 *
 * Parameters:	err_type    - the logging error type that was
 *			      generated.
 *		func_name   - the name of the function that
 *			      generated the error.
 *		message	    - the error message.
 *
 * Returns:
 *	   No return value
 *
 * Scope: Private
 */
void
_report_error(int err_type, char *func_name, char *message, ...)
{
	va_list		ap;
	char		*buf = NULL;
	err_info_t	*log_err_info = NULL;

	/* Collect the message to be logged */
	va_start(ap, message);
	(void) vasprintf(&buf, message, ap);
	va_end(ap);

	if ((buf == NULL) ||
	    ((func_name == NULL || strcmp(func_name, "")) == 0) ||
	    (0 > err_type > 3)) {
		err_type = LOGGING_ERR_REPORTING_ERROR;

		log_err_info = es_create_err_info(LOG_MOD_ID, ES_ERR);
		es_set_err_data_int(log_err_info, ES_DATA_ERR_NUM,
		    err_type);
		es_set_err_data_str(log_err_info, ES_DATA_FAILED_AT,
		    "Logging failed to properly report error");
	} else {

		log_err_info = es_create_err_info(LOG_MOD_ID, ES_ERR);
		es_set_err_data_int(log_err_info, ES_DATA_ERR_NUM,
		    err_type);
		es_set_err_data_str(log_err_info, ES_DATA_FAILED_AT,
		    func_name);
		es_set_err_data_str(log_err_info, ES_DATA_OP_STR, buf);
		free(buf);
	}
}

/*
 * Function: _convert_list
 *
 * Description: Convenience function for converting a python list to
 *              a linked list.
 *
 * Parameters: A PyObject containing a list of values
 *
 * Returns:	On Success -  A pointer to the new list
 *		On Failure -  NULL
 *
 * Scope: Private
 */
log_file_list_t *
_convert_list(PyObject *pRet)
{
	log_file_list_t		*new_list = NULL;
	log_file_list_t		*new_list_tail = NULL;
	PyObject		*py_item;
	char			*cstring_item;
	int			i;
	int			len = 0;
	char			*function = "_convert_list";


	/* Check to see if there is a list to convert */
	if (pRet == NULL || !PySequence_Check(pRet)) {
		return (NULL);
	}

	len = (int)PySequence_Length(pRet);

	for (i = 0; i < len; i++) {
		log_file_list_t *new_item;

		py_item = PySequence_GetItem(pRet, i);
		cstring_item = PyString_AsString(py_item);

		new_item = (log_file_list_t *)malloc(sizeof (log_file_list_t));
		if (new_item == NULL) {
			_report_error(LOGGING_ERR_DATA_INVALID, function, \
			    "Unable to allocate memory for new list.");
			break;
		}

		/* Update new list item */
		new_item->logfile = cstring_item;
		new_item->logfile_next = NULL;

		/* Insert to the list */
		if (new_list == NULL) {
			/* First element in the new list */
			new_list = new_item;
		} else if (new_list_tail != NULL) {
			new_list_tail->logfile_next = new_item;
		} else {
			_report_error(LOGGING_ERR_DATA_INVALID, function, \
			    "Unable to insert item into new linked list.");
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


/*
 * Function:    create_filehandler
 *
 * Description: Creates a FileHandler
 *
 *
 * Parameters:     nvlist of filehandler attributes
 *
 *
 * Returns:
 *      A dictionary PyObject  cast as logger_handler_t- On Success
 *      NULL - On Failure
 *
 * Scope: Private
 */
static logger_handler_t *
create_filehandler(nvlist_t *hdlrlst) {

	PyObject	*pFileDict = NULL;
	PyObject	*pFilename = NULL;
	PyObject	*pMode = NULL;
	PyObject	*pLevel = NULL;
	char		*hdlr;
	char		*filename;
	char		*mode;
	char		*level;
	char		*function = "create_filehandler";

	/*
	 * A FileHandler request requires filename data. There are
	 * also optional data that a user can request: mode and level.
	 * Perform checks to see what arguments the user has passed in.
	 */

	if ((nvlist_lookup_string(hdlrlst, FILENAME, &filename)) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Unable to get filename\n");
		goto cleanup;
	}

	pFilename = PyString_FromString(filename);
	if (pFilename == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert the file name to a Python string");
		goto cleanup;
	}

	pFileDict = PyDict_New();
	if (pFileDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}

	if (PyDict_SetItemString(pFileDict, FILENAME, pFilename) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the file \
		    name into the dictionary");
		goto cleanup;
	}


	/*
	 * The mode parameter is an optional attribute when creating a
	 * FileHandler. Check for it, but don't fail if one does not
	 * exist.
	 */
	if ((nvlist_lookup_string(hdlrlst, MODE, &mode)) == 0) {
		pMode = PyString_FromString(mode);
		if (pMode == NULL) {
			_report_error(LOGGING_ERR_DATA_INVALID, function,
			    "Failed to convert the mode to a Python string");
			goto cleanup;
		}

		if (PyDict_SetItemString(pFileDict, MODE, pMode) != 0) {
			_report_error(LOGGING_ERR_PY_FUNC, function,
			    "Failed to insert the required Python args for the \
			    mode into the dictionary");
			goto cleanup;
		}
	}

cleanup:
	if (PyErr_Occurred()) {
		pFileDict = NULL;
		PyErr_Clear();
	}

	Py_XDECREF(pFilename);
	Py_XDECREF(pMode);
	Py_XDECREF(pLevel);
	return ((logger_handler_t *)pFileDict);
}


/*
 * Function:    create_progresshandler
 *
 * Description: Creates a ProgressHandler
 *
 *
 * Parameters:  nvlist of filehandler attributes
 *
 *
 *
 * Returns:
 *      A dictionary PyObject cast as logger_handler_t - On Success
 *      NULL - On Failure
 *
 * Scope: Private
 */
static logger_handler_t *
create_progresshandler(nvlist_t *hdlrlst) {

	PyObject	*pPort = NULL;
	PyObject	*pHost = NULL;
	PyObject	*pProgDict = NULL;
	char		*hdlr;
	int		port;
	char		*host;
	char		*function = "create_progresshandler";

	pProgDict = PyDict_New();
	if (pProgDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}

	if ((nvlist_lookup_int32(hdlrlst, PORT, &port)) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function,
		    "Unable to get the port number");
		goto cleanup;
	}

	pPort = PyInt_FromLong(port);
	if (pPort == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert the progress integer to a \
		     Python integer");
		goto cleanup;
	}

	if (PyDict_SetItemString(pProgDict, PORT, pPort) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the \
		    port no. into the dictionary");
		goto cleanup;
	}

	if (nvlist_lookup_string(hdlrlst, HOST, &host) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function,
		    "Unable to get the host name");
		goto cleanup;
	}

	pHost = PyString_FromString(host);
	if (pHost == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert C string to Python string");
		goto cleanup;
	}

	if (PyDict_SetItemString(pProgDict, HOST, pHost) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the \
		    host into the dictionary");
		goto cleanup;
	}

cleanup:
	if (PyErr_Occurred()) {
		pProgDict = NULL;
		PyErr_Clear();
	}
	Py_XDECREF(pPort);
	Py_XDECREF(pHost);
	return ((logger_handler_t *)pProgDict);
}


/*
 * Function:    create_httphandler
 *
 * Description: Creates a HTTPHandler
 *
 *
 * Parameters:  nvlist of filehandler attributes
 *
 *
 *
 * Returns:
 *      A dictionary PyObject cast as a logger_handler_t - On Success
 *      NULL - On Failure
 *
 * Scope: Private
 */
static logger_handler_t *
create_httphandler(nvlist_t *hdlrlst) {

	PyObject	*pUrl = NULL;
	PyObject	*pHost = NULL;
	PyObject	*pMethod = NULL;
	PyObject	*pHttpDict = NULL;
	char		*hdlr;
	char		*host;
	char		*method;
	char		*url;
	char		*function = "create_httphandler";

	pHttpDict = PyDict_New();
	if (pHttpDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}

	/*
	 * An HTTPHandler request requires a host, a url, and methods.
	 * Methods can be GET, POST or may include both.
	 */

	if ((nvlist_lookup_string(hdlrlst, URL, &url)) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function,
		    "Unable to get the url");
		goto cleanup;
	}

	pUrl = PyString_FromString(url);
	if (pUrl == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert C string to Python string");
		goto cleanup;
	}

	if (PyDict_SetItemString(pHttpDict, URL, pUrl) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the url \
		    into the dictionary");
		goto cleanup;
	}

	if ((nvlist_lookup_string(hdlrlst, HOST, &host)) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function,
		    "Unable to get the host");
		goto cleanup;
	}

	pHost = PyString_FromString(host);
	if (pHost == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert C string to Python string");
		goto cleanup;
	}

	if (PyDict_SetItemString(pHttpDict, HOST, pHost) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the host \
		    into the dictionary");
		goto cleanup;
	}

	if (nvlist_lookup_string(hdlrlst, METHOD, &method) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function,
		    "Unable to get the method");
		goto cleanup;
	}

	pMethod = PyString_FromString(method);
	if (pMethod == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert C string for the method to \
		    Python string");
		goto cleanup;
	}

	if (PyDict_SetItemString(pHttpDict, METHOD, pMethod) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the method \
		    into the dictionary");
	}

cleanup:
	if (PyErr_Occurred()) {
		pHttpDict = NULL;
		PyErr_Clear();
	}

	Py_XDECREF(pUrl);
	Py_XDECREF(pHost);
	Py_XDECREF(pMethod);
	return ((logger_handler_t *)pHttpDict);
}


/*
 * Function:    create_streamhandler
 *
 * Description: Creates a StreamHandler
 *
 *
 * Parameters:  nvlist of streamhandler attributes
 *
 *
 *
 * Returns:
 *      A dictionary PyObject cast as logger_handler_t - On Success
 *      NULL - On Failure
 *
 * Scope: Private
 */
static logger_handler_t *
create_streamhandler(nvlist_t *hdlrlst) {

	PyObject	*pStrm = NULL;
	PyObject	*pStrmDict = NULL;
	char		*hdlr;
	char		*strm;
	char		*function = "create_streamhandler";

	pStrmDict = PyDict_New();
	if (pStrmDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}

	/*
	 * Check for a stream value, but it's optional. Don't fail if
	 * none is found.
	 */
	if ((nvlist_lookup_string(hdlrlst, STRM, &strm)) == 0) {
		pStrm = PySys_GetObject(strm);
		if (pStrm == NULL) {
			_report_error(LOGGING_ERR_PY_FUNC, function,
			    "Failed to convert C string for the stream to \
			    Python string");
			goto cleanup;
		}

		if (PyDict_SetItemString(pStrmDict, STRM, pStrm) != 0) {
			_report_error(LOGGING_ERR_PY_FUNC, function,
			    "Failed to insert the required Python args for the \
			    stream into the dictionary");
		}
	}

cleanup:
	if (PyErr_Occurred()) {
		pStrmDict = NULL;
		PyErr_Clear();
	}

	Py_XDECREF(pStrm);
	return ((logger_handler_t *)pStrmDict);

}







/*
 * Public Functions
 */

/*
 * Function: set_logger_class
 *
 * Description:	Set the logger class to the requested class.
 *
 *
 * Parameters:	logger_class - A sub-class of the Python Logger
 *
 * Returns:
 *		B_TRUE on success
 *		B_FALSE on failure
 *
 * Scope: Public
 */
boolean_t
set_logger_class(const char *logger_class)
{
	boolean_t 	retval = B_FALSE;
	PyObject	*pModuleLogging = NULL;
	PyObject	*pModuleLogsvc = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pTupArgs = NULL;
	PyObject	*pRet = NULL;
	PyObject	*pDict = NULL;
	PyObject	*pLoggerClass = NULL;
	char		*function = "set_logger_class";
	int		refcount = 0;


	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize Python interpreter");
		PyErr_Print();
		return (retval);
	}


	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */

	pModuleLogging = _load_module(LOGGING_PY_MOD);
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogging == NULL || pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}


	/*
	 * To set the logger class, first obtain the set_logger_class
	 * function.
	 */
	pFunc = PyObject_GetAttrString(pModuleLogging,
	    LOGGING_SET_LOGGER_CLASS);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to retrieve the python reference for %s", \
		    LOGGING_SET_LOGGER_CLASS);
		goto cleanup;
	}


	/* Get the module dictionary. */
	pDict = PyModule_GetDict(pModuleLogsvc);
	if (pDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the required Python module");
		goto cleanup;
	}


	/* Get the logger Class */
	pLoggerClass = PyDict_GetItemString(pDict, logger_class);
	if (pLoggerClass == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to find the requested logger class");
		goto cleanup;
	}


	/* Set the Logger class */
	pRet = PyObject_CallFunctionObjArgs(pFunc, pLoggerClass, NULL);
	if (pRet != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to retrieve a dictionary entry for %s", \
		    logger_class);
		goto cleanup;
	}


	/* Successfully set the logger class */
	retval = B_TRUE;

cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}
	Py_XDECREF(pModuleLogging);
	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pFunc);
	Py_XDECREF(pRet);
	return (retval);
}


/*
 * Function: transfer_log
 *
 * Description: Transfers the default log to the requested destination.
 *              If source is an empty string, the default log file
 *              created by the logger at instantiation is transferred
 *              to the destination.
 *
 *
 * Parameters:  logger - A logger instance
 *              trnsfrlist - A list containing the following:
 *                              A destination directory
 *                              A source file
 *
 *
 *
 * Returns:     B_TRUE on success
 *              B_FALSE on failure
 *
 * Scope: Public
 */
boolean_t
transfer_log(logger_t *logger, nvlist_t *trnsfrlist)
{
	boolean_t	retval = B_FALSE;
	PyObject	*pModuleLogsvc = NULL;
	PyObject	*pTransDict = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pSrc = NULL;
	PyObject	*pDest = NULL;
	PyObject	*pTupArgs = NULL;
	PyObject	*pRet = NULL;
	char		*destination;
	char		*source;
	char		*function = "transfer_log";

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (retval);
	}

	/* Verify that the logger variable is valid */
	if (logger == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return (retval);
	}

	pTransDict = PyDict_New();
	if (pTransDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}

	if ((nvlist_lookup_string(trnsfrlist, DEST, &destination)) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Unable to get destination for log transfer\n");
		goto cleanup;
	}

	pDest = PyString_FromString(destination);
	if (pDest == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to convert the log destination to a Python string");
		goto cleanup;
	}

	if (PyDict_SetItemString(pTransDict, DEST, pDest) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function,
		    "Failed to insert the required Python args for the \
		    destination name into the dictionary");
		goto cleanup;
	}


	/*
	 * The source parameter is an optional attribute when transferring.
	 * Check for it, but don't fail if one does not exist.
	 */
	if ((nvlist_lookup_string(trnsfrlist, SOURCE, &source)) == 0) {
		pSrc = PyString_FromString(source);
		if (pSrc == NULL) {
			_report_error(LOGGING_ERR_PY_FUNC, function,
			    "Failed to convert the log source to a Python \
			    string");
			goto cleanup;
		}

		if (PyDict_SetItemString(pTransDict, SOURCE, pSrc) != 0) {
			_report_error(LOGGING_ERR_PY_FUNC, function,
			    "Failed to insert the required Python args for the \
			    source name into the dictionary");
			goto cleanup;
		}

	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* To transfer, first obtain the transfer function. */
	pFunc = PyObject_GetAttrString((PyObject *)logger, LOGGING_TRANSFER_LOG);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," \
		    LOGGING_TRANSFER_LOG);
		goto cleanup;
	}

	pTupArgs = PyTuple_New(0);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple for log transfer.");
		goto cleanup;
	}

	/* Call the Python Function and check the return value */
	pRet = PyObject_Call(pFunc, pTupArgs, pTransDict);
	if (pRet != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The function call to Python failed");
		goto cleanup;
	}

	/* Transfer succeeded. Set the return value to true. */
	retval = B_TRUE;

cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}
	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pFunc);
	Py_XDECREF(pSrc);
	Py_XDECREF(pDest);
	Py_XDECREF(pTupArgs);
	Py_XDECREF(pRet);
	return (retval);
}

/*
 * Function: close_logging
 *
 * Description: Terminates the logging service.
 *
 *
 * Parameters:  logger - A logger instance
 *
 *
 * Returns:	On Success - A list of log files
 *              On Failure - Returns NULL
 *
 * Scope: Public
 */
log_file_list_t *
close_logging(logger_t *logger)
{
	PyObject	*pModuleLogsvc = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pTupArgs = NULL;
	PyObject	*pRet = NULL;
	char		*function = "close_logging";
	log_file_list_t	*return_list = NULL;

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (NULL);
	}

	/* Verify that the logger variable is valid */
	if (logger == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return (NULL);
	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* To close logging, first obtain the close function. */
	pFunc = PyObject_GetAttrString((PyObject *)logger, CLOSE);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," CLOSE);
		goto cleanup;
	}

	/*
	 * Build the argument list  for the function call and store it
	 * in a tuple. In this case, an empty tuple is created because
	 * there are no parameters.
	 */
	pTupArgs = PyTuple_New(0);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}

	/* Call the close function */
	pRet = PyObject_Call(pFunc, pTupArgs, NULL);
	if (pRet == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The function call to Python failed");
		goto cleanup;
	}

	/* close succeeded. Set the return value to true. */
	return_list = _convert_list(pRet);

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}

	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pFunc);
	Py_XDECREF(pTupArgs);
	Py_XDECREF(pRet);
	return (return_list);

}

/*
 * Function: set_log_level
 *
 * Description:	Adds a logging level to handlers and loggers.
 *
 *
 * Parameters:  name - the name of the handler/logger
 *              level - the level to associate with the handler/logger.
 *		        This is a string value using one of the
 *			following: DEBUG, INFO, ERROR, WARNING,
 *			CRITICAL
 *
 *
 * Returns:
 *      B_TRUE - On Success
 *      B_FALSE - On Failure
 *
 * Scope: Public
 */
boolean_t
set_log_level(logger_t *name, char *level)
{
	boolean_t	retval = B_FALSE;
	PyObject	*pModuleLogging = NULL;
	PyObject	*pModuleLogsvc = NULL;
	PyObject	*pLevel = NULL;
	PyObject	*pRet = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pArg = NULL;
	PyObject	*pTupArgs = NULL;
	int		level_value = 0;
	char		*function = "set_log_level";

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (retval);
	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogging = _load_module(LOGGING_PY_MOD);
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogging == NULL || pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* To get the level, first obtain the get_level function. */
	pFunc = PyObject_GetAttrString(pModuleLogging, GET_LEVEL_NAME);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," GET_LEVEL_NAME);
		goto cleanup;
	}

	/* Build the argument list for the function call */
	if ((pArg = PyString_FromString(level)) == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to convert C string to Python string");
		goto cleanup;
	}

	pTupArgs = PyTuple_New(1);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}

	if (PyTuple_SetItem(pTupArgs, 0, pArg) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to set the required Python tuple args");
		goto cleanup;
	}

	/* Call the get_level_name function with the argument list */
	pLevel = PyObject_Call(pFunc, pTupArgs, NULL);
	if (pLevel == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to get the level name");
		goto cleanup;
	}

	Py_XDECREF(pTupArgs);
	Py_XDECREF(pFunc);

	/* To set the level, first obtain the set_log_level function. */
	pFunc = PyObject_GetAttrString((PyObject *)name, SET_LOG_LEVEL);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," SET_LOG_LEVEL);
		goto cleanup;
	}

	/* Build our argument list */
	pTupArgs = PyTuple_New(1);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}

	PyTuple_SetItem(pTupArgs, 0, pLevel);
	if ((PyTuple_SetItem(pTupArgs, 0, pLevel)) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to set the required Python tuple args");
		goto cleanup;
	}

	pRet = PyObject_Call(pFunc, pTupArgs, NULL);
	if (pRet != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The function call to Python failed to set the log level");
		goto cleanup;
	}

	/* set_log_level succeeded. Set the return value to true. */
	retval = B_TRUE;

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}

	Py_XDECREF(pTupArgs);
	Py_XDECREF(pFunc);
	Py_XDECREF(pRet);
	Py_XDECREF(pLevel);
	return (retval);
}

/*
 * Function: add_handler
 *
 * Description:	Adds a handler to a logger
 *
 *
 * Parameters:	logger  -  A logger instance
 *		hdlrlist - A handler parameters stored in an nvlist
 *		hdlrtyp -  An enum value that identifies the handler
 *
 *
 * Returns:	B_TRUE -  On Success
 *		B_FALSE - On Failure
 *
 * Scope: Public
 */

boolean_t
add_handler(logger_t *logger, nvlist_t *hdlrlist,
    logging_handler_type_t hdlrtyp)
{
	boolean_t		retval = B_FALSE;
	PyObject		*pModuleLogging = NULL;
	PyObject		*pModuleLogsvc = NULL;
	PyObject		*pClassModule = NULL;
	PyObject		*pClass = NULL;
	PyObject		*pTupArgs = NULL;
	logger_handler_t	*pDict = NULL;
	PyObject		*pInstance = NULL;
	PyObject		*pFunc = NULL;
	PyObject    		*pRet = NULL;
	char			*hdlr;
	int			ret;
	char			*level;
	char			*function = "add_handler";


	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (retval);
	}

	/* Verify that the logger variable is valid */
	if (logger == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return (retval);
	}


	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogging = _load_module(LOGGING_PY_MOD);
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogging == NULL || pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* Obtain the value for the requested handler */
	if (nvlist_lookup_string(hdlrlist, HANDLER, &hdlr) != 0) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Requested handler does not appear to exist.");
		goto cleanup;
	}

	/*
	 * Determine the type of handler requested and store the
	 * parameters for the handler in a dictionary.
	 */
	switch (hdlrtyp) {
		case LOGGING_FILE_HDLR:
			pClassModule = pModuleLogsvc;
			Py_INCREF(pClassModule);
			pDict = create_filehandler(hdlrlist);
			break;
		case LOGGING_PROGRESS_HDLR:
			pClassModule = pModuleLogsvc;
			Py_INCREF(pClassModule);
			pDict = create_progresshandler(hdlrlist);
			break;
		case LOGGING_STREAM_HDLR:
			pClassModule = pModuleLogging;
			Py_INCREF(pClassModule);
			pDict = create_streamhandler(hdlrlist);
			break;
		case LOGGING_HTTP_HDLR:
			pClassModule = _load_module(LOGGING_PY_HANDLER_MOD);
			if (pClassModule == NULL) {
				_report_error(LOGGING_ERR_PY_FUNC, function,
				    "Failed to load required Python \
				    logging modules");
				goto cleanup;
			}
			pDict = create_httphandler(hdlrlist);
			break;
		default:
			_report_error(LOGGING_ERR_DATA_INVALID, function, \
			    "Requested handler is not supported.");
			goto cleanup;
	}

	/* Make sure that the dictionary was populated */
	if (pDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to create dictionary for handler instance");
		goto cleanup;
	}

	/*
	 * A class instance of the requested handler must be created, and
	 * then this instance is added to the logger. pClass holds the
	 * Python module that contains the handler class.
	 */
	pClass = PyObject_GetAttrString(pClassModule, hdlr);
	if (pClass == NULL || !PyCallable_Check(pClass)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python handler class");
		goto cleanup;
	}

	/*
	 * Instantiate an empty tuple needed for the Python method to create an
	 * instance of the handler class
	 */
	pTupArgs = PyTuple_New(0);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}

	/* This call creates the instance of the handler class */
	pInstance = PyObject_Call(pClass, pTupArgs, (PyObject *)pDict);
	if (pInstance == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The function call to Python failed to create a handler \
		    class instance");
		goto cleanup;
	}

	/*
	 * If the handler has a log level associated with it, it is added to the
	 * handler class instance before adding the handler to the logger.
	 */
	if ((nvlist_lookup_string(hdlrlist, LEVEL, &level)) == 0) {
		if (ret = set_log_level((logger_t *)pInstance, level) != B_TRUE) {
			_report_error(LOGGING_ERR_PY_FUNC, function, \
			    "Failed to set the required Python tuple args");
			goto cleanup;
		}

	}

	/*
	 * To add the handler instance to the logger,
	 * first obtain the add_handler function.
	 */
	pFunc = PyObject_GetAttrString((PyObject *)logger, LOGGING_ADD_HANDLER);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," \
		    LOGGING_ADD_HANDLER);
		goto cleanup;
	}

	if (_PyTuple_Resize(&pTupArgs, 1) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to resize Python tuple.");
		goto cleanup;
	}

	if (retval = PyTuple_SetItem(pTupArgs, 0, pInstance) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to set the required Python tuple args");
		goto cleanup;
	}

	/* Call the add_handler function with the Handler class instance */
	pRet = PyObject_CallObject(pFunc, pTupArgs);
	if (pRet != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The function call to Python failed to create a handler");
		goto cleanup;
	}

	/* add_handler succeeded. Set the return value to true. */
	retval = B_TRUE;

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}

	Py_XDECREF(pModuleLogging);
	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pClassModule);
	Py_XDECREF(pClass);
	Py_XDECREF(pInstance);
	Py_XDECREF(pTupArgs);
	Py_XDECREF(pDict);
	Py_XDECREF(pFunc);
	Py_XDECREF(pRet);
	return (retval);
}


/*
 * Function: log_message
 *
 * Description:	Passes a message to the logger to be logger.
 *
 *
 * Parameters:	logger - A logger instance
 *		level - The log level of the message
 *		message - The message to be logged
 *
 *
 * Returns:
 *		B_True - on Success
 *		B_FALSE - on Failure
 *
 * Scope: Public
 */
boolean_t
log_message(logger_t *logger, const char *level, const char *message, ...)
{
	PyThreadState   *myThreadState;
	va_list 	ap;
	char 		*buf = NULL;
	boolean_t   	retval = B_FALSE;
	PyObject    	*pModuleLogging = NULL;
	PyObject	*pModuleLogsvc = NULL;
	PyObject    	*pFunc = NULL;
	PyObject    	*pTupArgs = NULL;
	PyObject    	*pMessage = NULL;
	PyObject    	*pRet = NULL;
	int		ret;
	char		*function = "log_message";

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (retval);
	}


	/* Verify that the logger variable is valid */
	if (logger == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return (retval);
	}

	/* Verify that the level variable is valid */
	if (level == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to find a log level");
		return (retval);
	}

	/* Verify that the logging level is valid */
	if ((strcmp(level, NOTSET) != 0) &&
	    (strcmp(level, DEBUG) != 0) &&
	    (strcmp(level, INFO) != 0) &&
	    (strcmp(level, WARNING) != 0) &&
	    (strcmp(level, ERROR) != 0) &&
	    (strcmp(level, FATAL) != 0) &&
	    (strcmp(level, CRITICAL) != 0)) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Requested log level is not valid\n");
		goto cleanup;
	}

	/* Collect the message to be logged */
	va_start(ap, message);
	(void) vasprintf(&buf, message, ap);
	va_end(ap);


	if (buf == NULL) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed find a log message");
		goto cleanup;
	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogging = _load_module(LOGGING_PY_MOD);
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogging == NULL || pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/*
	 * To log the message, first obtain the function for logging
	 * messages at the requested level.
	 */
	pFunc = PyObject_GetAttrString((PyObject *)logger, level);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python log level function");
		goto cleanup;
	}

	/*
	 * Build the argument list  for the function call and store it
	 * in a tuple. The following three blocks of code accomplish this
	 * task.
	 */
	pTupArgs = PyTuple_New(1);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}
	pMessage = PyString_FromString(buf);
	if (pMessage == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to convert the log message string to a Python \
		     string");
		free(buf);
		goto cleanup;
	}
	free(buf);

	if (ret = PyTuple_SetItem(pTupArgs, 0, pMessage) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to set the required Python tuple args");
		goto cleanup;
	}

	/* Call the function and log the message */
	pRet = PyObject_CallObject(pFunc, pTupArgs);
	if (pRet != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "The message failed to log properly");
		goto cleanup;
	}

	/* log message succeeded. Set the return value to true. */
	retval = B_TRUE;

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}
	Py_XDECREF(pModuleLogging);
	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pFunc);
	Py_XDECREF(pTupArgs);
	Py_XDECREF(pRet);
	return (retval);
}

/*
 * Function: get_logger
 *
 * Description: Gets the requested logging handle, or if one
 *              isn't requested, it returns the default logger.
 *
 *
 * Parameters:	logger_name - A string that represents logger.
 *
 * Returns:
 *      A Python logger object on success cast to a logger_t object
 * 	NULL on failure
 *
 * Scope: Public
 */
logger_t *
get_logger(const char *logger_name)
{
	PyObject    	*pModuleLogging = NULL;
	PyObject    	*pFunc = NULL;
	PyObject    	*pTupArgs = NULL;
	PyObject    	*pArg = NULL;
	PyObject    	*pLogger = NULL;
	int		ret;
	char		*function = "get_logger";

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Print();
		return ((logger_t *)pLogger);
	}

	/* Verify that the logger variable is valid */
	if (logger_name == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return ((logger_t *)pLogger);
	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogging = _load_module(LOGGING_PY_MOD);
	if (pModuleLogging == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* To obtain a logger, first obtain the get_logger function */
	pFunc = PyObject_GetAttrString(pModuleLogging, LOGGING_GET_LOGGER_FUNC);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python %s," LOGGING_GET_LOGGER_FUNC);
		goto cleanup;
	}

	/*
	 * Build the argument list  for the function call and store it
	 * in a tuple. The following three blocks of code accomplish this
	 * task.
	 */
	if ((pArg = PyString_FromString(logger_name)) == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to convert the logger name string to a Python \
		     string");
		goto cleanup;
	}

	pTupArgs = PyTuple_New(1);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}

	if (ret = PyTuple_SetItem(pTupArgs, 0, pArg) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to set the required Python tuple args");
		goto cleanup;
	}

	/* Call the function and get a logger */
	pLogger = PyObject_Call(pFunc, pTupArgs, NULL);
	if (pLogger == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to get a logger");
	}

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Print();
	}
	Py_XDECREF(pModuleLogging);
	Py_XDECREF(pFunc);
	Py_XDECREF(pTupArgs);
	return ((logger_t *)pLogger);

}

/*
 * Function: report_progress
 *
 * Description:	Reports progress to the progress reporting tools
 *
 *
 * Parameters:	logger - A logger instance
 *		progress - A progress value that represents the
 *			   percentage of completion
 *		message  - An optional information message
 *
 * Returns:
 *		B_TRUE on Success
 *		B_FALSE on Failure
 *
 * Scope: Public
 */
boolean_t
report_progress(logger_t *logger, long progress, const char *message, ...)
{
	va_list 	ap;
	char 		*buf = NULL;
	boolean_t	retval = B_FALSE;
	PyObject	*pModuleLogging = NULL;
	PyObject	*pModuleLogsvc = NULL;
	PyObject	*pFunc = NULL;
	PyObject	*pTupArgs = NULL;
	PyObject	*pMessage = NULL;
	PyObject	*pProgress = NULL;
	PyObject	*pDict = NULL;
	PyObject	*pValue = NULL;
	char		*function = "report_progress";

	/* Initialize the Python interpreter if necessary */
	if (_initialize_py() != B_TRUE) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to initialize the Python module.");
		PyErr_Clear();
		return (retval);
	}

	/* Verify that the logger variable is valid */
	if (logger == NULL) {
		_report_error(LOGGING_ERR_DATA_INVALID, function, \
		    "Failed to locate logger instance");
		return (retval);
	}

	/* Collect the progress information */
	va_start(ap, message);
	(void) vasprintf(&buf, message, ap);
	va_end(ap);

	if (buf == NULL) {
		_report_error(LOGGING_ERR_PY_INIT, function, \
		    "Failed to find a progress report");
		goto cleanup;
	}

	/*
	 * Load the Python modules that are needed in order to
	 * interface with the logging functionality
	 */
	pModuleLogging = _load_module(LOGGING_PY_MOD);
	pModuleLogsvc = _load_module(LOGSVC_PY_MOD);
	if (pModuleLogging == NULL || pModuleLogsvc == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load required Python logging modules");
		goto cleanup;
	}

	/* To report progress, first obtain the report_progress function */
	pFunc = PyObject_GetAttrString((PyObject *)logger, REPORT_PROGRESS);
	if (pFunc == NULL || ! PyCallable_Check(pFunc)) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to load the Python function %s," REPORT_PROGRESS);
		goto cleanup;
	}

	/*
	 * Build the argument list  for the function call and store it
	 * in a dictionary. The following blocks of code accomplish this
	 * task. The tuple is necessary for the function call, although
	 * it is empty.
	 */
	pTupArgs = PyTuple_New(0);
	if (pTupArgs == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python tuple.");
		goto cleanup;
	}


	pProgress = PyInt_FromLong(progress);
	if (pProgress == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to convert the progress integer to a Python \
		     integer");
		goto cleanup;
	}

	pDict = PyDict_New();
	if (pDict == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to instantiate a Python dictionary.");
		goto cleanup;
	}


	if (PyDict_SetItemString(pDict, PROGRESS, pProgress) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to insert the required Python args for progress \
		    into the dictionary");
		goto cleanup;
	}

	pMessage = PyString_FromString(buf);
	if (pMessage == NULL) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to convert the logger name string to a Python \
		    string");
		free(buf);
		goto cleanup;
	}
	free(buf);

	if (PyDict_SetItemString(pDict, MESSAGE, pMessage) != 0) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to insert the required Python args for the message \
		    into the dictionary");
		goto cleanup;
	}

	/* Call the function and report progress */
	pValue = PyObject_Call(pFunc, pTupArgs, pDict);
	if (pValue != Py_None) {
		_report_error(LOGGING_ERR_PY_FUNC, function, \
		    "Failed to report the progress");
		goto cleanup;
	}

	/* Report progress succeeded. Set the return value to true. */
	retval = B_TRUE;

	/* Cleanup that is shared by both the success and failure paths */
cleanup:
	if (PyErr_Occurred()) {
		PyErr_Clear();
	}
	Py_XDECREF(pModuleLogging);
	Py_XDECREF(pModuleLogsvc);
	Py_XDECREF(pFunc);
	Py_XDECREF(pTupArgs);
	Py_XDECREF(pDict);
	Py_XDECREF(pProgress);
	Py_XDECREF(pValue);
	return (retval);
}
