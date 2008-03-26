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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)ls_main.c	1.2	07/08/09 SMI"

#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <Python.h>

#include <sys/param.h>

#include <ls_api.h>

/* configuration environment variables */

/* log filename */
#define	LS_ENV_LOG_FILENAME	"LS_LOG_FILE"

/* debug filename */
#define	LS_ENV_DBG_FILENAME	"LS_DBG_FILE"

/* log destination */
#define	LS_ENV_LOG_DEST		"LS_LOG_DEST"

/* dbg destination */
#define	LS_ENV_DBG_DEST		"LS_DBG_DEST"

/* debugging level */
#define	LS_ENV_DBG_LVL		"LS_DBG_LVL"

/* default log file */
#define	LS_LOGFILE_DEFAULT	"/tmp/install_log"

/* default debug file */
#define	LS_DBGFILE_DEFAULT	"/tmp/install_log.debug"

/* default destination  */
#define	LS_DEST_DEFAULT		LS_DEST_FILE

/* default debugging level */
#define	LS_DBGLVL_DEFAULT	LS_DBGLVL_ERR

/*
 * flag indicating, if default debugging/logging function
 * should post log message
 */
#define	LS_POST_LOG_FLAG	-1

/* validate destination */
#define	ls_destination_valid(d)	\
	((d >= LS_DEST_NONE) && (d <= LS_DEST_BOTH))

/* validate debug level */
#define	ls_dbglvl_valid(l)	\
	((l >= LS_DBGLVL_NONE) && (l < LS_DBGLVL_LAST))

/* private function prototypes */

/* default method for posting logging messages */
static void ls_log_method_default(const char *id, char *msg);

/* default method for posting debugging messages */
static void ls_dbg_method_default(const char *id, ls_dbglvl_t level,
    char *msg);

/* Python method for ls_write_log_message */
static PyObject *py_write_log_message(PyObject *, PyObject *);

/* Python method for ls_write_dbg_message */
static PyObject *py_write_dbg_message(PyObject *, PyObject *);

/* private variables */

/* method for posting logging message */
static ls_log_method_t ls_log_method = ls_log_method_default;

/* method for posting debugging message */
static ls_dbg_method_t ls_dbg_method = ls_dbg_method_default;

/* log console destination */
static FILE	*ls_log_console = stderr;

/* dbg console destination */
static FILE	*ls_dbg_console = stderr;

/* log file name */
static char	*ls_log_filename = LS_LOGFILE_DEFAULT;

/* debug file name */
static char	*ls_dbg_filename = LS_DBGFILE_DEFAULT;

/* log file */
static FILE	*ls_log_file = NULL;

/* debug file */
static FILE	*ls_dbg_file = NULL;

/* log destination */
static ls_dest_t	ls_log_dest = LS_DEST_DEFAULT;

/* debug destination */
static ls_dest_t	ls_dbg_dest = LS_DEST_DEFAULT;

/* debugging level */
static ls_dbglvl_t	ls_dbglvl = LS_DBGLVL_DEFAULT;

/* ------------------------ local functions --------------------------- */

/*
 * Function:	ls_getenv_string
 * Description:	Obtains string from environment variable
 *
 * Parameters:	envname - environment variable name
 *
 *
 * Return:	NULL - variable is not defined or empty
 *		pointer - pointer to string defined by variable
 */
static char *
ls_getenv_string(char *envname)
{
	char *env_value = getenv(envname);

	if ((env_value != NULL) && (env_value[0] == '\0')) {
		env_value = NULL;
	}

	return (env_value);
}


/*
 * Function:	ls_getenv_num
 * Description:	Obtains non negative number from environment variable
 *
 * Parameters:	envname - environment variable name
 *
 * Return:	LS_E_INVAL	- variable is not defined or empty
 *		>=0		- env. variable value
 */
static int
ls_getenv_num(char *envname)
{
	char *env_value;
	char *ret;
	int num;

	if ((env_value = ls_getenv_string(envname)) == NULL) {
		return (LS_E_INVAL);
	}

	errno = 0;
	num = strtol(env_value, &ret, 10);

	if ((errno != 0) || (ret[0] != '\0'))
		return (LS_E_INVAL);
	else
		return (num);
}


/*
 * Function:	ls_dbg_method_default
 * Description:
 *
 * Parameters:	id - module identification
 *		level - debug message level
 *		msg - debugging message
 *
 *
 * Return:
 */
static void
ls_dbg_method_default(const char *id, ls_dbglvl_t level, char *msg)
{
	FILE 		*post_console;
	FILE 		**post_file;
	ls_dest_t	post_dest;
	char 		*post_filename;
	char		buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
	static int	fl_init_console_done = 0;

	/*
	 * set variables according to required action (debug or log)
	 * and format debug or log message appropriately
	 */

	if (level == LS_POST_LOG_FLAG) {
		post_console = ls_log_console;
		post_file = &ls_log_file;
		post_dest = ls_log_dest;
		post_filename = ls_log_filename;

		(void) snprintf(buf, sizeof (buf), "<%s> %s", id, msg);
	} else {
		char		*lvl_str;

		post_console = ls_dbg_console;
		post_file = &ls_dbg_file;
		post_dest = ls_dbg_dest;
		post_filename = ls_dbg_filename;

		switch (level) {
			case LS_DBGLVL_EMERG:
				lvl_str = "!";
				break;

			case LS_DBGLVL_ERR:
				lvl_str = "E";
				break;

			case LS_DBGLVL_WARN:
				lvl_str = "W";
				break;

			case LS_DBGLVL_INFO:
				lvl_str = "I";
				break;

			case LS_DBGLVL_TRACE:
				lvl_str = "T";
				break;

			default:
				lvl_str = "?";
				break;
		}

		(void) snprintf(buf, sizeof (buf), "<%s_%s> %s", id, lvl_str,
		    msg);
	}

	/* post to console */

	if ((post_dest & LS_DEST_CONSOLE) != 0) {

		/*
		 * Unbuffered I/O - set only once
		 */
		if (!fl_init_console_done) {
			fl_init_console_done = 1;

			(void) setbuf(ls_log_console, NULL);
			(void) setbuf(ls_dbg_console, NULL);
		}

		(void) fputs(buf, post_console);
	}

	/* post to file */

	if ((post_dest & LS_DEST_FILE) != 0) {
		if (*post_file == NULL) {
			if ((*post_file = fopen(post_filename, "a")) != NULL)
				/*
				 * Unbuffered I/O
				 */
				(void) setbuf(*post_file, NULL);
		}

		if (*post_file != NULL)
			(void) fputs(buf, *post_file);
	}
}


/*
 * Function:	ls_log_method_default
 * Description:
 *
 * Parameters:	id - module identification
 *		msg - logging message
 *
 *
 * Return:
 */
static void
ls_log_method_default(const char *id, char *msg)
{
	ls_dbg_method_default(id, LS_POST_LOG_FLAG, msg);
}

/* ----------------------- public functions --------------------------- */

/*
 * Function:	ls_init_log
 * Description:	Initializes logging service. Sets parameters according
 *		to environment variables. If appropriate evn. variable
 *		is not available, sets it to the default value.
 *
 * Parameters:	-
 *
 *
 * Return:	-
 *
 */
void
ls_init_log(void)
{
	/* set destination - default is console & file */

	ls_log_dest = (ls_dest_t)ls_getenv_num(LS_ENV_LOG_DEST);

	if (!ls_destination_valid(ls_log_dest)) {
		ls_log_dest = LS_DEST_DEFAULT;
	}

	/* set log file */

	ls_log_filename = ls_getenv_string(LS_ENV_LOG_FILENAME);

	/* if NULL, set to default */

	if (ls_log_filename == NULL)
		ls_log_filename = LS_LOGFILE_DEFAULT;
}


/*
 * Function:	ls_init_dbg
 * Description:	Initializes debugging service. Sets parameters according
 *		to the environment variables. If appropriate evn. variable
 *		is not available, sets it to the default value.
 *
 * Parameters:	-
 *
 *
 * Return:	-
 */
void
ls_init_dbg(void)
{
	/* set destination - default is console & file */

	ls_dbg_dest = (ls_dest_t)ls_getenv_num(LS_ENV_DBG_DEST);

	if (!ls_destination_valid(ls_dbg_dest)) {
		ls_dbg_dest = LS_DEST_DEFAULT;
	}

	/* set debug level */

	ls_dbglvl = (ls_dbglvl_t)ls_getenv_num(LS_ENV_DBG_LVL);

	if (!ls_dbglvl_valid(ls_dbglvl)) {
		ls_dbglvl = LS_DBGLVL_DEFAULT;
	}

	/* set debug file */

	ls_dbg_filename = ls_getenv_string(LS_ENV_DBG_FILENAME);

	/* if NULL, set to default */

	if (ls_dbg_filename == NULL)
		ls_dbg_filename = LS_DBGFILE_DEFAULT;
}


/*
 * Function:	ls_set_dbg_level
 * Description:	Set debugging level
 *
 * Parameters:	level - debug level
 *
 *
 * Return:	LS_E_SUCCESS	- level set successfully
 *		LS_E_INVAL	- invalid level requested
 */
ls_errno_t
ls_set_dbg_level(ls_dbglvl_t level)
{
	/* check input parameters */

	if (!ls_dbglvl_valid(level)) {
		return (LS_E_INVAL);
	}

	ls_dbglvl = level;

	return (LS_E_SUCCESS);
}

/*
 * Function:	ls_get_dbg_level
 * Description:	Get current debugging level
 *
 * Parameters:	-
 *
 * Return:	current debugging level
 */
ls_dbglvl_t
ls_get_dbg_level(void)
{
	return (ls_dbglvl);
}


/*
 * Function:	ls_register_log_method
 * Description:	register alternate method performing actual posting of
 *		log message
 *
 * Parameters:	func	- pointer to alternate method
 *
 * Return:	-
 *
 */
void
ls_register_log_method(ls_log_method_t func)
{
	assert(func != NULL);

	ls_log_method = func;
}


/*
 * Function:	ls_register_dbg_method
 * Description:	register alternate method performing actual posting of
 *		debug message
 *
 * Parameters:	func	- pointer to alternate method
 *
 * Return:	-
 *
 */
void
ls_register_dbg_method(ls_dbg_method_t func)
{
	assert(func != NULL);

	ls_dbg_method = func;
}


/*
 * Function:	ls_write_log_message
 * Description:	Write log message to the file and/or the display.
 *		The text should already be internationalized by the calling
 *		routine.
 *
 * Parameters:	id - module identification
 *		fmt - logging message format
 *
 * Return:
 */
/* PRINTFLIKE2 */
void
ls_write_log_message(const char *id, const char *fmt, ...)
{
	va_list	ap;
	char	buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];

	va_start(ap, fmt);
	(void) vsnprintf(buf, sizeof (buf), fmt, ap);
	ls_log_method(id, buf);
	va_end(ap);
}


/*
 * Function:	ls_write_dbg_message
 * Description:	Write debug message to the file and/or the display.
 *		The text should already be internationalized by the calling
 *		routine.
 *
 * Parameters:	id - module identification
 *		level - debug level
 *		fmt - debugging message format
 *
 * Return:
 */
/* PRINTFLIKE3 */
void
ls_write_dbg_message(const char *id, ls_dbglvl_t level, const char *fmt, ...)
{
	va_list	ap;
	char	buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];

	/* only post message, if current debugging level allows it */

	if (level <= ls_get_dbg_level()) {
		va_start(ap, fmt);
		(void) vsnprintf(buf, sizeof (buf), fmt, ap);
		ls_dbg_method(id, level, buf);
		va_end(ap);
	}
}

/*
 * py_write_log_message - Python-callable wrapper for ls_write_log_message
 * parameters:
 *	id - log module identification
 *	buf - character string - must already be formatted
 * returns NULL if argument parsing error, 1 otherwise
 * must be loaded with call to ls_init_python_module()
 * declared static - callable only by Python through table
 */
static PyObject *
py_write_log_message(PyObject *self, PyObject *args)
{
	char	buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
	char	*id, *msg;

	if (!PyArg_ParseTuple(args, "ss", &id, &msg))
		return NULL;

	(void) strlcpy(buf, msg, sizeof(buf));
	ls_log_method(id, buf);
	return (Py_BuildValue("i", 1));
}

/*
 * py_write_dbg_message - Python-callable wrapper for ls_write_dbg_message
 * parameters:
 *	id - log module identification
 *	level - debugging level
 *	buf - character string - must already be formatted
 * returns NULL if argument parsing error, 1 otherwise
 * must be loaded with call to ls_init_python_module()
 * declared static - callable only by Python through table
 */
static PyObject *
py_write_dbg_message(PyObject *self, PyObject *args)
{
	char	buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
	char	*id, *msg;
	int	level;

	if (!PyArg_ParseTuple(args, "sis", &id, &level, &msg))
		return NULL;

	/* only post message, if current debugging level allows it */

	if (level <= ls_get_dbg_level()) {
		(void) strlcpy(buf, msg, sizeof(buf));
		ls_dbg_method(id, level, buf);
	}
	return (Py_BuildValue("i", 1));
}

/*
 * initialize Python module for liblogsvc, named logsvc
 * returns B_TRUE for success, B_FALSE for failure
 * Python is initialized if it isn't already
 */
boolean_t
ls_init_python_module()
{
	static PyMethodDef logsvcMethods[] = {
		{"write_log", py_write_log_message, METH_VARARGS,
		 "Write to logfile"},
		{"write_dbg", py_write_dbg_message, METH_VARARGS,
		 "Write to debug logfile"},
		{NULL, NULL, 0, NULL}	/* Sentinel */
	};
	PyObject *mod;

	if (!Py_IsInitialized()) /* initialize Python */
		Py_Initialize();
	/* initialize module and its methods */
	mod = Py_InitModule("logsvc", logsvcMethods);
	if (mod == NULL)
		return(B_FALSE);
	/* initialize constants in module */
	/* debugging levels */
	PyModule_AddIntConstant(mod, "LS_DBGLVL_NONE", LS_DBGLVL_NONE);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_EMERG", LS_DBGLVL_EMERG);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_ERR", LS_DBGLVL_ERR);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_WARN", LS_DBGLVL_WARN);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_INFO", LS_DBGLVL_INFO);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_TRACE", LS_DBGLVL_TRACE);
	/* destinations */
	PyModule_AddIntConstant(mod, "LS_DEST_NONE", LS_DEST_NONE);
	PyModule_AddIntConstant(mod, "LS_DEST_CONSOLE", LS_DEST_CONSOLE);
	PyModule_AddIntConstant(mod, "LS_DEST_FILE", LS_DEST_FILE);
	return(B_TRUE);
}
