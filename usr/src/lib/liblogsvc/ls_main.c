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
#include <sys/param.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <libgen.h>
#include <libnvpair.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <strings.h>
#include <time.h>
#include <wait.h>

#include <ls_api.h>

/* configuration environment variables */

/* log filename */
#define	LS_ENV_LOG_FILENAME	"LS_FILE"

/* log destination */
#define	LS_ENV_LOG_DEST		"LS_DEST"

/* debugging level */
#define	LS_ENV_DBG_LVL		"LS_DBG_LVL"

/* timestamp */
#define	LS_ENV_TIMESTAMP	"LS_TIMESTAMP"

/* default log file name */
#define	LS_LOGFILE_DEFAULT_NAME	"install_log"

/* source log file path */
#define	LS_LOGFILE_SRC_PATH	"/tmp/"

/* destination log file path */
#define	LS_LOGFILE_DST_PATH	"/var/sadm/system/logs/"

/* default log file */
#define	LS_LOGFILE_DEFAULT	LS_LOGFILE_SRC_PATH LS_LOGFILE_DEFAULT_NAME

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

/* debug console destination */
static FILE	*ls_dbg_console = stderr;

/* log file name */
static char	*ls_log_filename = LS_LOGFILE_DEFAULT;

/* log file */
static FILE	*ls_log_file = NULL;

/* log destination */
static ls_dest_t	ls_log_dest = LS_DEST_DEFAULT;

/* debugging level */
static ls_dbglvl_t	ls_dbglvl = LS_DBGLVL_DEFAULT;

/* add timestamp to messages */
static boolean_t	ls_timestamp = B_TRUE;

/* ------------------------ local functions --------------------------- */

/*
 * idm_debug_print()
 */
static void
ls_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("LS", dbg_lvl, buf);
	va_end(ap);
}


/*
 * Function:	ls_system()
 *
 * Description:	Execute shell commands in a thread-safe manner
 *
 * Scope:	private
 * Parameters:	cmd - the command to execute
 *
 * Return:	-1 if fails, otherwise 0
 *
 */

static int
ls_system(char *cmd)
{
	FILE	*p;
	int	ret;
	char	errbuf[MAXPATHLEN];

	/*
	 * catch stderr for debugging purposes
	 */

	if (strlcat(cmd, " 2>&1 1>/dev/null", MAXPATHLEN) >= MAXPATHLEN)
		ls_debug_print(LS_DBGLVL_WARN,
		    "strlcat failed: %s\n", strerror(errno));

	ls_debug_print(LS_DBGLVL_INFO, "ls cmd: "
	    "%s\n", cmd);

	if ((p = popen(cmd, "r")) == NULL)
		return (-1);

	while (fgets(errbuf, sizeof (errbuf), p) != NULL)
		ls_debug_print(LS_DBGLVL_WARN, " stderr:%s", errbuf);

	ret = pclose(p);

	if (ret == -1)
		return (-1);

	if (WEXITSTATUS(ret) != 0) {
		ls_debug_print(LS_DBGLVL_WARN,
		    " command failed: err=%d\n", ret);
		return (-1);
	}

	return (0);
}


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
	char		buf[LS_MESSAGE_MAXLEN + LS_ID_MAXLEN + 1];
	static int	fl_init_console_done = 0;
	time_t		tstamp;
	char		asc_tstamp[30];
	struct tm	*tm_tstamp;
	char		*s = NULL;
	char		*e = NULL;

	if (msg == NULL)
		return;

	/*
	 * set variables according to required action (debug or log)
	 * and format debug or log message appropriately
	 */

	/*
	 * prepare time stamp in UTC format
	 */

	if (ls_timestamp) {
		if ((tstamp = time(NULL)) != (time_t)-1 &&
		    (tm_tstamp = gmtime(&tstamp)) != NULL &&
		    asctime_r(tm_tstamp, asc_tstamp, sizeof (asc_tstamp)) !=
		    NULL) {
			/*
			 * drop weekday and year information
			 */

			if ((s = strchr(asc_tstamp, ' ')) != NULL) {
				s++;
				e = strrchr(asc_tstamp, ' ');

				*e = '\0';
			} else
				s = "--:--:--";
		} else
			s = "--:--:--";
	}

	if (level == LS_POST_LOG_FLAG) {
		post_console = ls_log_console;

		if (ls_timestamp)
			(void) snprintf(buf, sizeof (buf), "<%s %s> %s",
			    id, s, msg);
		else
			(void) snprintf(buf, sizeof (buf), "<%s> %s", id, msg);
	} else {
		char		*lvl_str;

		post_console = ls_dbg_console;

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

			default:
				lvl_str = "?";
				break;
		}

		if (ls_timestamp) {
			(void) snprintf(buf, sizeof (buf), "<%s_%s %s> %s", id,
			    lvl_str, s, msg);
		} else
			(void) snprintf(buf, sizeof (buf), "<%s_%s> %s", id,
			    lvl_str, msg);
	}

	/* post to console */

	if ((ls_log_dest & LS_DEST_CONSOLE) != 0) {

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

	if ((ls_log_dest & LS_DEST_FILE) != 0) {
		if (ls_log_file == NULL) {
			if ((ls_log_file = fopen(ls_log_filename, "a")) != NULL)
				/*
				 * Unbuffered I/O
				 */
				(void) setbuf(ls_log_file, NULL);
		}

		if (ls_log_file != NULL)
			(void) fputs(buf, ls_log_file);
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
 * Function:	ls_init
 * Description:	Initializes logging service. Sets parameters according
 *		to nvlist parameters or environment variables.
 *		Evn. variable takes precedence over nvlist attribute.
 *		If parameter is not defined, sets it to the default value.
 *
 * Parameters:	- params - nvlist set of attribute
 *
 *
 * Return:	- LS_E_SUCCESS - service initialized successfully
 *		- LS_E_NOMEM - memory allocation failed
 *
 */
ls_errno_t
ls_init(nvlist_t *params)
{
	char		*str;
	int16_t		dest, lvl;
	boolean_t	stamp;

	/*
	 * Process nvlist attributes first.
	 * Then proceed with environment variables - which
	 * take precedence over nvlist
	 * Any parameter not set will retain its default value
	 */

	if (params != NULL) {
		/* log file */

		if (nvlist_lookup_string(params, LS_ATTR_LOG_FILE, &str) == 0) {
			ls_log_filename = strdup(str);

			if (ls_log_filename == NULL)
				return (LS_E_NOMEM);
		}

		/* destination */

		if ((nvlist_lookup_int16(params, LS_ATTR_DEST, &dest) == 0) &&
		    ls_destination_valid(dest))
			ls_log_dest = dest;

		/* timestamp */

		if (nvlist_lookup_boolean_value(params, LS_ATTR_TIMESTAMP,
		    &stamp) == 0)
			ls_timestamp = stamp;

		/* debug level */

		if ((nvlist_lookup_int16(params, LS_ATTR_DBG_LVL, &lvl) == 0) &&
		    ls_dbglvl_valid(lvl))
			ls_dbglvl = lvl;
	}

	/* environment variables */

	/* set log file */

	ls_log_filename = ls_getenv_string(LS_ENV_LOG_FILENAME);

	/* if NULL, set to default */

	if (ls_log_filename == NULL)
		ls_log_filename = LS_LOGFILE_DEFAULT;

	/* set destination - default is console & file */

	ls_log_dest = (ls_dest_t)ls_getenv_num(LS_ENV_LOG_DEST);

	if (!ls_destination_valid(ls_log_dest)) {
		ls_log_dest = LS_DEST_DEFAULT;
	}

	/* time stamp */

	if ((stamp = ls_getenv_num(LS_ENV_TIMESTAMP)) != LS_E_INVAL)
		ls_timestamp = stamp == 0 ? B_FALSE : B_TRUE;

	/* set debug level */

	ls_dbglvl = (ls_dbglvl_t)ls_getenv_num(LS_ENV_DBG_LVL);

	if (!ls_dbglvl_valid(ls_dbglvl)) {
		ls_dbglvl = LS_DBGLVL_DEFAULT;
	}

	/* initialize Python logging module logsvc */
	if (!ls_init_python_module())
		ls_write_log_message("LIBLOGSVC","ERROR: Python logging module "
		    "logsvc failed to initialize\n");

	return (LS_E_SUCCESS);
}


/*
 * Function:	ls_transfer
 * Description:	Transfers log file to the
 *		destination (installed Solaris instance)
 *
 * Parameters:	- src_mountpoint - source of log file
 * 		- dst_mountpoint - destination (alternate root)
 *
 *
 * Return:	- LS_E_SUCCESS - service initialized successfully
 *		- LS_E_LOG_TRANSFER_FAILED - couldn't transfer log file
 *
 */
ls_errno_t
ls_transfer(char *src_mountpoint, char *dst_mountpoint)
{
	char	cmd[MAXPATHLEN];
	DIR	*dirp;
	int	ret;
	char	*fname;

	if ((src_mountpoint == NULL) || (dst_mountpoint == NULL))
		return (LS_E_LOG_TRANSFER_FAILED);

	/*
	 * Check whether the target directory exists. If not create it
	 */

	(void) snprintf(cmd, sizeof (cmd), "%s" LS_LOGFILE_DST_PATH,
	    dst_mountpoint);

	dirp = opendir(cmd);
	if (dirp == NULL) {
		/*
		 * Create and set the directory permission to 755
		 */
		ret = mkdirp(cmd,
		    S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH);

		if (ret != 0) {
			ls_debug_print(LS_DBGLVL_ERR,
			    "Couldn't create target directory %s\n", cmd);

			return (LS_E_LOG_TRANSFER_FAILED);
		}
	} else
		(void) closedir(dirp);

	/*
	 * extract log file name from path
	 */

	if ((fname = strrchr(ls_log_filename, '/')) == NULL) {
		ls_debug_print(LS_DBGLVL_ERR,
		    "Couldn't determine log file name\n");

		return (LS_E_LOG_TRANSFER_FAILED);
	}

	fname++;

	ls_debug_print(LS_DBGLVL_INFO,
	    "Extracted log file name: %s\n", fname);

	/*
	 * copy install log file to the destination
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp %s%s %s%s%s", src_mountpoint, ls_log_filename,
	    dst_mountpoint, LS_LOGFILE_DST_PATH, fname);

	if (ls_system(cmd) != 0) {
		ls_debug_print(LS_DBGLVL_ERR,
		    "Transfer of log file failed\n");

		return (LS_E_LOG_TRANSFER_FAILED);
	}

	return (LS_E_SUCCESS);
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
		return (NULL);

	(void) strlcpy(buf, msg, sizeof (buf));
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
		return (NULL);

	/* only post message, if current debugging level allows it */

	if (level <= ls_get_dbg_level()) {
		(void) strlcpy(buf, msg, sizeof (buf));
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
		return (B_FALSE);
	/* initialize constants in module */
	/* debugging levels */
	PyModule_AddIntConstant(mod, "LS_DBGLVL_NONE", LS_DBGLVL_NONE);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_EMERG", LS_DBGLVL_EMERG);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_ERR", LS_DBGLVL_ERR);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_WARN", LS_DBGLVL_WARN);
	PyModule_AddIntConstant(mod, "LS_DBGLVL_INFO", LS_DBGLVL_INFO);
	/* destinations */
	PyModule_AddIntConstant(mod, "LS_DEST_NONE", LS_DEST_NONE);
	PyModule_AddIntConstant(mod, "LS_DEST_CONSOLE", LS_DEST_CONSOLE);
	PyModule_AddIntConstant(mod, "LS_DEST_FILE", LS_DEST_FILE);
	return (B_TRUE);
}
