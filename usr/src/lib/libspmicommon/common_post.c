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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */



/*
 * Module:	common_post.c
 * Group:	libspmicommon
 * Description:	This module contains common utilities used to
 *		post or log messages and notices to application
 *		users
 */

#include <libgen.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <dlfcn.h>
#include <link.h>
#include <sys/param.h>
#include <sys/stat.h>
#include "spmicommon_lib.h"
#include "common_strings.h"
#include "bootlog.h"

/* private prototypes */

static char	 *_dflt_error_format(u_int, char *);
static void	_dflt_error_func(u_int, char *);
static void	_dflt_log_func(u_int, char *);
static char	*_dflt_status_format(u_int, char *);
static void	_dflt_status_func(u_int, char *);
static char	*_dflt_warning_format(u_int, char *);
static void	_dflt_warning_func(u_int, char *);
static void	_write_message(u_char, u_int, u_int, char *);
static boolean_t	bootlog_available(void);

/* local variables */

static void	(*_status_func)(u_int, char *) = _dflt_status_func;
static void	(*_progress_func)(u_int, char *) = _dflt_status_func;
static void	(*_error_func)(u_int, char *) = _dflt_error_func;
static void	(*_warning_func)(u_int, char *) = _dflt_warning_func;
static void	(*_log_func)(u_int, char *) = _dflt_log_func;

/* local globals */

static FILE	*_StatusFp = stdout;
static FILE	*_ErrorFp = stderr;
static FILE	*_WarningFp = stderr;
static FILE	*_log_file = NULL;

/* ---------------------- public functions ----------------------- */

/*
 * Function:	_setup_install_log
 * Description:	Copy the install_log file from /tmp to the target
 *		filesystem and add a timestamp to the name.
 *		Set up a symlink to this new file from either
 *		install_log or upgrade_log in hte same directory.
 *		If the log is open for writing, close & reopen
 *		at the new location.
 *		This function was moved here from libspmisvc so
 *		it could use some knowledge about the log file.
 *
 *		Until after 2.6, set up a symbolic link from
 *		var/sadm/install_data for backwards compatibility
 *		as stated in PSARC/1994/331.
 * Scope:	publice
 * Parameters:	none
 * Return:	Pointer to new logfile on success
 *		NULL on failure
 */
char *
_setup_install_log(void)
{
	int	reopen = 0;
	char	*dated_path, *new_logpath;
	char	*old_logpath = "/var/sadm/install_data/upgrade_log";
	FILE	*tmpf;
	static char	new_path[MAXPATHLEN] = "";

	if (get_install_type() == CMNUpgrade) {
		(void) sprintf(new_path, "%s%s/upgrade_log",
		    get_rootdir(), "/var/sadm/system/logs");
		new_logpath = new_path + strlen(get_rootdir());
		/*
		 * If there is a symbolic link in the old location,
		 * remove it.  If there is a file, not a sym link,
		 * move it to the new location in the dated form.
		 * Remove ths after 2.6
		 */

		(void) rm_link_mv_file(old_logpath, new_logpath);

		/*
		 * Remove an existing symlink, or rename the log file
		 * to a dated form.
		 */

		(void) rm_link_mv_file(new_logpath, new_logpath);

		/*
		 * Create a new dated log file & symlink
		 */

		if ((tmpf = fopen(new_path, "w")) == NULL) {
			return (NULL);
		}
		(void) fclose(tmpf);
		if ((dated_path =
		    (char *)rm_link_mv_file(new_logpath, new_logpath))
		    == NULL) {
			return (NULL);
		}
		(void) chmod(dated_path, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
		(void) symlink(basename(dated_path), new_path);
		/*
		 * Remove this after 2.6
		 */
		{ char tmppath[MAXPATHLEN];
		(void) sprintf(tmppath, "%s/%s", get_rootdir(), old_logpath);
		(void) symlink("../system/logs/upgrade_log", tmppath);
		}
	} else {
		/*
		 * Initial install
		 */
		(void) sprintf(new_path, "%s%s/install_log",
		    get_rootdir(), "/var/sadm/system/logs");
		new_logpath = new_path + strlen(get_rootdir());
		/*
		 * Remove this after 2.6
		 */
		{ char tmppath[MAXPATHLEN];
		(void) sprintf(tmppath, "%s/var/sadm/install_data/install_log",
		    get_rootdir());
		(void) symlink("../system/logs/install_log", tmppath);
		}
	}
	/*
	 * If we've started writing a log file, copy it to the
	 * permanent location.
	 */
	if (access(TMPLOGFILE, F_OK) == 0) {
		if (_log_file != NULL) {
			reopen = 1;
			(void) fclose(_log_file);
			_log_file = NULL;
		}
		if (_copy_file(new_path, TMPLOGFILE) == ERROR) {
			return (NULL);
		}
		if (reopen != 0) {
			if ((_log_file = fopen(new_path, "a")) == NULL) {
				/*
				 * Punt
				 */
				return (NULL);
			}
		}
	}
	return (new_path);
}

/*
 * Function:	write_status_register_log
 * Description:	Register a file name into which the logging data should
 *		go when the SCR option is use. If NULL, output goes to
 *		stdout.
 * Scope:	public
 * Parameters:	file	[RO, *RO] (char *)
 *			File name into which logging will be appended.
 * Return:
 *	SUCCESS: file was successfully openned for write
 *	FAILURE: file was NOT successfully openned for write
 */
int
write_status_register_log(char *file)
{
	FILE	*fp;

	/* close the current output file if it was not stdout */
	if (_StatusFp != stdout) {
		(void) fclose(_StatusFp);
		_StatusFp = stdout;
	}

	if (file != NULL && (fp = fopen(file, "a")) != NULL) {
		_StatusFp = fp;
		return (SUCCESS);
	}

	return (FAILURE);
}

/*
 * Function:	write_error_register_log
 * Description:	Register a file name into which the logging data should
 *		go when the ERRMSG option is used. If NULL, output goes to
 *		stderr.
 * Scope:	public
 * Parameters:	file	[RO, *RO] (char *)
 *			File name into which logging will be appended.
 * Return:
 *	SUCCESS: file was successfully openned for write
 *	FAILURE: file was NOT successfully openned for write
 */
int
write_error_register_log(char *file)
{
	FILE	*fp;

	/* close the current output file if it was not stderr */
	if (_ErrorFp != stderr) {
		(void) fclose(_ErrorFp);
		_ErrorFp = stderr;
	}

	if (file != NULL && (fp = fopen(file, "a")) != NULL) {
		_ErrorFp = fp;
		return (SUCCESS);
	}

	return (FAILURE);
}

/*
 * Function:	write_warning_register_log
 * Description:	Register a file name into which the logging data should
 *		go when the WARNMSG option is used. If NULL, output goes to
 *		stderr.
 * Scope:	public
 * Parameters:	file	[RO, *RO] (char *)
 *			File name into which logging will be appended.
 * Return:
 *	SUCCESS: file was successfully openned for write
 *	FAILURE: file was NOT successfully openned for write
 */
int
write_warning_register_log(char *file)
{
	FILE	*fp;

	/* close the current output file if it was not stderr */
	if (_WarningFp != stderr) {
		(void) fclose(_WarningFp);
		_WarningFp = stderr;
	}

	if (file != NULL && (fp = fopen(file, "a")) != NULL) {
		_WarningFp = fp;
		return (SUCCESS);
	}

	return (FAILURE);
}

/*
 * Function:	register_func
 * Description:	Register a STATUS, ERRMSG, or WARNMSG notification
 *		handler routine. This routine allows applications to
 *		supply their own routines which are called when posting
 *		status, error, and warning messages to the display. There
 *		are three separate handlers which can be supplied, one for
 *		each message type.
 * Scope:	public
 * Parameters:	type	- [RO]
 *			  [ERRMSG  - non-reconcilable problem
 *			   STATMSG - status
 *			   PROGMSG - progress
 *			   WARNMSG - advisory warning]
 *			  notification type
 *		func	- [RO]
 *			  pointer to a function which is to be used for
 *			  posting display messages of type 'type'
 * Return:	pointer to the previously registered handler function
 */
void (*
register_func(u_int type, void (*func)(u_int, char *)))()
{
	void 	(*oldfunc)(u_int, char *) = NULL;

	switch (type) {
	    case ERRMSG:
		oldfunc = _error_func;
		_error_func = func;
		break;
	    case WARNMSG:
		oldfunc = _warning_func;
		_warning_func = func;
		break;
	    case STATMSG:
		oldfunc = _status_func;
		_status_func = func;
		break;
	    case PROGMSG:
		oldfunc = _progress_func;
		_progress_func = func;
		break;
	}

	return (oldfunc);
}

/*
 * Function:	write_message
 * Description:	Write text data to the log file and/or the display.
 *		The text should already be internationalized by the calling
 *		routine. If the application has registered a display routine,
 *		that routine should be used to present the text, otherwise
 *		the display will be assumed to be stdout.
 *
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	public
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  Specify where to record the message.
 *		type	- [RO]
 *			  [STATMSG  - status message
 *			   ERRMSG   - non-reconcilable problem
 *			   PROGMSG - progress
 *			   WARNMSG  - advisory warning]
 *			   Notification type.
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - msg continuation from preceding message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  print format string
 *		...	- [RO]
 *			  optional print arguments
 * Return:		none
 */
void
/*VARARGS4*/
write_message(u_char dest, u_int type, u_int format, char *string, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, string);
	(void) vsprintf(buf, string, ap);
	_write_message(dest, type, format, buf);
	va_end(ap);
}

/*
 * Function:	write_notice
 * Description:	Write text data to the log file and the display. The
 *		text should already be internationalized by the calling
 *		routine. If the application has registered a display routine,
 *		that routine should be used to present the text, otherwise
 *		the display will be assumed to be stderr.
 *
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a msg needs to be longer than this, the FMTPARTIAL
 *			format flag should be used on consecutive message calls.
 * Scope:	public
 * Parameters:	type	- [RO]
 *			  [ERRMSG  - non-reconcilable problem
 *			   PROGMSG - progress
 *			   WARNMSG - advisory warning]
 *			  Notification type.
 *		string	- [RO]
 *			  print format string
 *		...	- [RO]
 *			  optional printf arguments
 * Return:	none
 */
void
/*VARARGS2*/
write_notice(u_int type, char *string, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, string);
	(void) vsprintf(buf, string, ap);
	_write_message(LOG|SCR, type, LEVEL0, buf);
	va_end(ap);
}

/*
 * Function:	write_status
 * Description:	Write a status message.
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	public
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  specify where to record the message
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - msg continuation from preceding message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  print format string
 *		...	- [RO]
 *			  optional printf arguments
 * Return:	none
 */
void
/*VARARGS3*/
write_status(u_char dest, u_int format, char *string, ...)
{
	va_list		ap;
	char		buf[MAXPATHLEN + 1] = "";

	va_start(ap, string);
	(void) vsprintf(buf, string, ap);
	_write_message(dest, STATMSG, format, buf);
	va_end(ap);
}

/*
 * Function:	write_progress
 * Description:	Write a progress message.
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	public
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  specify where to record the message
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - msg continuation from preceding message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  print format string
 *		...	- [RO]
 *			  optional printf arguments
 * Return:	none
 */
void
/*VARARGS3*/
write_progress(u_char dest, u_int format, char *string, ...)
{
	va_list		ap;
	char		buf[MAXPATHLEN + 1] = "";

	va_start(ap, string);
	(void) vsprintf(buf, string, ap);
	_write_message(dest, PROGMSG, format, buf);
	va_end(ap);
}

/*
 * Function:	write_message_nofmt
 * Description:	Write text data to the log file and/or the display.
 *		The text should already be internationalized by the calling
 *		routine. If the application has registered a display routine,
 *		that routine should be used to present the text, otherwise
 *		the display will be assumed to be stdout.
 *
 *		The difference between this and write_message is that
 *		we DO NOT pass the string through vsprintf.
 *		Callers who want to pass strings directly through to be printed
 *		(e.g. from a child pkgadd) that may have "%" modifiers
 *		in them should use this routine.  If they use
 *		write_message directly and it has a "%" modifier in it
 *		then the app is bound to core dump because it will have
 *		no data to also feed to the vsprintf.
 *		(See bug 1267474 for an example of this happening).
 *
 *		NOTE:	Since we are not vsprintf'ing into an internal
 *			buffer for these, the string passed in may be of
 *			any length.
 * Scope:	public
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  Specify where to record the message.
 *		type	- [RO]
 *			  [STATMSG  - status message
 *			   ERRMSG   - non-reconcilable problem
 *			   PROGMSG - progress
 *			   WARNMSG  - advisory warning]
 *			   Notification type.
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - message continuation from preceding
 *				message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *				format of the message (used by the formatting
 *				routine).
 *		string	- [RO]
 *			  string to print
 * Return:		none
 */
void
write_message_nofmt(u_char dest, u_int type, u_int format, char *string)
{
	_write_message(dest, type, format, string);
}

/*
 * Function:	write_notice_nofmt
 * Description:	Write text data to the log file and the display. The
 *		text should already be internationalized by the calling
 *		routine. If the application has registered a display routine,
 *		that routine should be used to present the text, otherwise
 *		the display will be assumed to be stderr.
 *
 *		The difference between this and write_notice is that
 *		we DO NOT pass the string through vsprintf.
 *		Callers who want to pass strings directly through to be printed
 *		(e.g. from a child pkgadd) that may have "%" modifiers
 *		in them should use this routine.  If they use
 *		write_notice directly and it has a "%" modifier in it
 *		then the app is bound to core dump because it will have
 *		no data to also feed to the vsprintf.
 *		(See bug 1267474 for an example of this happening).
 *
 *		NOTE:	Since we are not vsprintf'ing into an internal
 *			buffer for these, the string passed in may be of
 *			any length.
 * Scope:	public
 * Parameters:	type	- [RO]
 *			  [ERRMSG  - non-reconcilable problem
 *			   PROGMSG - progress
 *			   WARNMSG - advisory warning]
 *			  Notification type.
 *		string	- [RO]
 *			  string to print
 * Return:	none
 */
void
write_notice_nofmt(u_int type, char *string)
{
	_write_message(LOG|SCR, type, LEVEL0, string);
}

/*
 * Function:	write_status_nofmt
 * Description:	Write a status message.
 *
 *		The difference between this and write_status is that
 *		we DO NOT pass the string through vsprintf.
 *		Callers who want to pass strings directly through to be printed
 *		(e.g. from a child pkgadd) that may have "%" modifiers
 *		in them should use this routine.  If they use
 *		write_status directly and it has a "%" modifier in it
 *		then the app is bound to core dump because it will have
 *		no data to also feed to the vsprintf.
 *		(See bug 1267474 for an example of this happening).
 *
 *		NOTE:	Since we are not vsprintf'ing into an internal
 *			buffer for these, the string passed in may be of
 *			any length.
 * Scope:	public
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  specify where to record the message
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - message continuation from preceding
 *				message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *				format of the message (used by the formatting
 *				routine).
 * Return:	none
 */
void
write_status_nofmt(u_char dest, u_int format, char *string)
{
	_write_message(dest, STATMSG, format, string);
}

/*
 * Function: write_debug
 * Description:
 *	Print a standardly formatted debug output line.
 *	There is a standard 'header' line format that can be generated
 *	that will look something like:
 *		Debug LIBSPMITTY -- "util.c", line 80
 *		Debug LIBSPMITTY -- "util.c", line 95
 *	And you can print just data lines like:
 *		x = 32
 * Scope:	PUBLIC
 * Parameters:
 *	dest	- [RO]
 *		 [LOG	  - write only to the log file
 *		 SCR	  - write only to the display
 *		 LOGSCR - write to both the file and display]
 *	debug_flag - Is debug actually turned on?  If not - nothing is
 *		printed.
 *	who_called - A caller can use this to identify where this
 *		debug output is coming from (e.g. each library and app
 *		can have its own tag to easily distinguish where output
 *		is coming from).
 *		If who_called is NULL, then the header line of
 *		output is not printed, and only the data line from the
 *		format/var args is printed.
 *	file_name - name of file the debug output request was called from.
 *		Use macro __FILE__.
 *	line_number - line number the debug output request was called from.
 *		Use macro __LINE__.
 *	 format	- [RO]
 *		 [LEVEL0   - base level message
 *		 LEVEL1   - first level message
 *		 LEVEL2   - second level message
 *		 LEVEL3   - third level message
 *		 CONTINUE - message continuation from preceding message
 *		 LISTITEM - item type message
 *		 FMTPARTIAL  - part of a message (more to come)]
 *		 format of the message (used by the formatting routine)
 *	fmtstr - format string to print any message you want.
 *		Used to pass to vfprintf.
 *	...	- var args to be used with format above to pass to vfprintf.
 * Return:	none
 * Globals:	none
 * Notes:
 *	The defines, DEBUG_LOC and DEBUG_LOC_NOHD may be useful
 *	to use as parameters when calling this routine.
 */
void
write_debug(u_char dest, int debug_flag, char *who_called, char *file_name,
			int line_number, u_int format, char *fmtstr, ...)
{
	va_list ap;
	char		buf[MAXPATHLEN + 1] = "";
	int old_trace_level;

	if (!debug_flag)
		return;

	old_trace_level = get_trace_level();
	(void) set_trace_level(1);

	/*
	 * if they specified a 'who_called', then
	 * print first debug info line with who_called, function name,
	 * file name, line number, etc...
	 *
	 * if no 'who_called', then
	 * don't print first line with debug info.
	 * i.e. so we can end up with debug output like:
	 * Debug LIBSPMITTY -- "util.c", line 80: main()
	 * 	x = 32
	 * 	y = 32
	 */
	if (who_called) {
		(void) write_status(dest, LEVEL0,
			"Debug %s -- \"%s\", line %d",
			who_called,
			file_name ? file_name : "",
			line_number);
	}

	if (fmtstr) {
		va_start(ap, fmtstr);
		(void) vsprintf(buf, fmtstr, ap);
		_write_message(dest, STATMSG, format, buf);
		va_end(ap);
	}
	(void) set_trace_level(old_trace_level);
}

/*
 * Function: write_debug_test
 * Description:
 * 	A test routine for the write_debug routine.
 * Scope:       PUBLIC
 * Parameters:  none
 * Return:	none
 * Globals:	none
 * Notes:
 *	Output will look something like:
 *
 * Debug MYNAME -- "common_post.c", line 618
 *
 * Debug MYNAME -- "common_post.c", line 620
 *
 * Debug MYNAME -- "common_post.c", line 622
 *         Entering 33
 *         Leaving 45
 *
 * Debug MYNAME -- "common_post.c", line 626
 *         Leaving 45
 *         x = 32
 *         y = 102
 *
 * Debug MYNAME -- "common_post.c", line 634
 *         - item 0
 *                   item 0
 *                   item 1
 *                   item 2
 *         - item 1
 *                   item 0
 *                   item 1
 *                   item 2
 *         - item 2
 *                   item 0
 *                   item 1
 *                   item 2
 *         - item 3
 *                   item 0
 *                   item 1
 *                   item 2
 *         - item 4
 *                   item 0
 *                   item 1
 *                   item 2
 *
 * Debug MYNAME -- "common_post.c", line 645
 *
 */
void
write_debug_test(void)
{
	int i;
	int j;
	u_char dest;

	dest = LOGSCR;

	/* locations with no text */
	write_debug(dest, 1, "MYNAME", DEBUG_LOC,
		LEVEL1, NULL);
	write_debug(dest, 1, "MYNAME", DEBUG_LOC,
		LEVEL1, NULL);

	/* locations with some text */
	write_debug(dest, 1, "MYNAME", DEBUG_LOC,
		LEVEL1, "%s %d", "Entering", 33);

	/* no location with some text */
	write_debug(dest, 1, DEBUG_LOC_NOHD,
		LEVEL1, "%s %d", "Leaving", 45);

	/* location with text */
	write_debug(dest, 1, "MYNAME", DEBUG_LOC,
		LEVEL1, "%s %d", "Leaving", 45);

	/* no location with text */
	write_debug(dest, 1, NULL, DEBUG_LOC,
		LEVEL1, "x = %d", 32);
	write_debug(dest, 1, NULL, DEBUG_LOC,
		LEVEL1, "y = %d", 102);

	/* test list items */
	write_debug(dest, 1, "MYNAME", DEBUG_LOC,
		LEVEL1, NULL);
	for (i = 0; i < 5; i++) {
		write_debug(dest, 1, DEBUG_LOC_NOHD,
			LEVEL1|LISTITEM, "item %d", i);
		for (j = 0; j < 3; j++) {
			write_debug(dest, 1, DEBUG_LOC_NOHD,
				LEVEL2|LISTITEM|CONTINUE, "item %d", j);
		}
	}
}

/* ---------------------- private functions ---------------------- */

/*
 * Function:	_dflt_error_func
 * Description:	The default error logging function which converts a
 *		notice message into the default format and prints it
 *		out to stderr.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  format of the message (used by the formatting
 *			  routine)
 *		string	- [RO]
 *			  buffer containing notice message to be logged
 * Return:	none
 */
static void
_dflt_error_func(u_int format, char *string)
{
	char *ptr;

	(void) setbuf(stderr, NULL);
	ptr = _dflt_error_format(format, string);

	(void) fwrite(ptr, strlen(ptr), 1, _ErrorFp);
}

/*
 * Function:	_dflt_error_format
 * Description:	Default error formatting routine.
 *
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  buffer containing notice message to be logged
 * Return:	char *	- pointer to buffer containing formatted data
 */
static char *
/*ARGSUSED0*/
_dflt_error_format(u_int format, char *string)
{
	static char 	buf[MAXPATHLEN + 1] = "";

	buf[0] = '\0';
	(void) sprintf(buf, "\n%s: %s\n", MSG_LEADER_ERROR, string);
	return (buf);
}

/*
 * Function:	_dflt_log_func
 * Description:	Default function which writes the message to the log file.
 *		Messages are only logged on live executions. The log
 *		file is created and open for append if this hasn't been done
 *		previously.
 * Scope:	private
 * Parameters:	format	- format of the msg (used by the formatting routine).
 *		buf	- string to be logged
 * Return:	none
 */
static void
/*ARGSUSED0*/
_dflt_log_func(u_int format, char *buf)
{
	if (!GetSimulation(SIM_EXECUTE) || get_trace_level()) {
		if (_log_file == NULL) {
			if ((_log_file = fopen(TMPLOGFILE, "a")) != NULL)
				/*
				 * Unbuffered I/O
				 */
				(void) setbuf(_log_file, NULL);
		}

		if (_log_file != NULL)
			(void) fwrite(buf, strlen(buf), 1, _log_file);
	}
}

/*
 * Function:	_dflt_status_format
 * Description:	Default status message formatting function which adds format
 *		data to the string passed in and returns a pointer to a local
 *		buffer containing the fully formatted string.
 *
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - msg continuation from preceding message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  print format string
 * Return:	char *
 */
static char *
_dflt_status_format(u_int format, char *string)
{
	static char 	buf[MAXPATHLEN + 1];

	buf[0] = '\0';

	/* assemble the format leading characters based on the format */
	/* block separation */
	if (format & LEVEL0) {
		if (((format & CONTINUE) == 0) && (string[0] != '\0'))
			(void) strcat(buf, "\n");
	} else if (format & LEVEL1)
		(void) strcat(buf, "\t");
	else if (format & LEVEL2)
		(void) strcat(buf, "\t\t");
	else if (format & LEVEL3)
		(void) strcat(buf, "\t\t\t");

	/* class demarcation */
	if (format & LISTITEM) {
		if (format & CONTINUE)
			(void) strcat(buf, "  ");
		else
			(void) strcat(buf, "- ");
	}

	(void) strcat(buf, string);
	if ((format & FMTPARTIAL) == 0)
		(void) strcat(buf, "\n");

	return (buf);
}

/*
 * Function:	_dflt_status_func
 * Description:	The default status logging function which converts a
 *		status message into the default format and prints it
 *		out to stdout.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  format parameter for format function
 *		string	- [RO]
 *			  buffer containing message to be logged
 * Return:	none
 */
static void
_dflt_status_func(u_int format, char *string)
{
	char *ptr;

	ptr = _dflt_status_format(format, string);
	(void) fwrite(ptr, strlen(ptr), 1, _StatusFp);
	(void) fflush(_StatusFp);
}

/*
 * Function:	_dflt_warning_format
 * Description:	Default warning format routine.
 *
 *		NOTE:	A single message when formatted should not exceed
 *			1000 bytes or it will cause corruptions and core dumps.
 *			If a message needs to be longer than this, the
 *			FMTPARTIAL format flag should be used on consecutive
 *			message calls.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  buffer containing notice message to be logged
 * Return:	char *	- pointer to buffer containing formatted data
 */
static char *
/*ARGSUSED0*/
_dflt_warning_format(u_int format, char *string)
{
	static char 	buf[MAXPATHLEN + 1] = "";

	buf[0] = '\0';
	(void) sprintf(buf, "%s: %s\n", MSG_LEADER_WARNING, string);
	return (buf);
}

/*
 * Function:	_dflt_warning_func
 * Description:	The default warning logging function which converts a
 *		notice message into the default format and prints it
 *		out to stderr.
 * Scope:	private
 * Parameters:	format	- [RO]
 *			  format of the msg (used by the formatting routine).
 *		string	- [RO]
 *			  buffer containing notice message to be logged
 * Return:	none
 */
static void
_dflt_warning_func(u_int format, char *string)
{
	char *ptr;

	ptr = _dflt_warning_format(format, string);

	(void) fwrite(ptr, strlen(ptr), 1, _WarningFp);
	(void) fflush(_WarningFp);
}

/*
 * Function:	_write_message
 * Description:
 * Scope:	private
 * Parameters:	dest	- [RO]
 *			  [LOG	  - write only to the log file
 *			   SCR	  - write only to the display
 *			   LOGSCR - write to both the file and display]
 *			  specifies where the message should be recorded
 *		type	- [RO]
 *			  [STATMSG - status message
 *			   ERRMSG  - non-reconcilable problem
 *			   WARNMSG - advisory warning]
 *			  notification type
 *		format	- [RO]
 *			  [LEVEL0   - base level message
 *			   LEVEL1   - first level message
 *			   LEVEL2   - second level message
 *			   LEVEL3   - third level message
 *			   CONTINUE - message continuation from preceding
 *				      message
 *			   LISTITEM - item type message
 *			   FMTPARTIAL  - part of a message (more to come)]
 *			  format of the message (used by the formatting routine)
 *		buf	- [RO]
 *			  assembled message, unformatted
 * Return:	none
 */
static void
_write_message(u_char dest, u_int type, u_int format, char *buf)
{

	/*
	 * if the text is targetted for the remote log facility, write it
	 * using the currently registered file logging function
	 */
	if ((dest & LOG) && bootlog_available()) {
		switch (type) {
		    /* progress msgs use same format as status msgs */
		    case PROGMSG:
			    bootlog("ident", BOOTLOG_PROGRESS, "%s", buf);
			    break;

		    case STATMSG:
			    bootlog("ident", BOOTLOG_INFO, "%s", buf);
			    break;
			break;

		    case WARNMSG:
			    bootlog("ident", BOOTLOG_WARNING, "%s", buf);
			    break;
			break;

		    case ERRMSG:
			    bootlog("ident", BOOTLOG_EMERG, "%s", buf);
			    break;
			break;
		}
	}

	/*
	 * if the text is targetted for the log file, write it
	 * using the currently registered file logging function
	 */
	if (dest & LOG) {
		switch (type) {
			/*
			 * progress msgs use same format as status
			 * msgs when writing to the local log
			 */
		    case PROGMSG:
		    case STATMSG:
			(*_log_func)(format,
				_dflt_status_format(format, buf));
			break;

		    case WARNMSG:
			(*_log_func)(format, _dflt_warning_format(format, buf));
			break;

		    case ERRMSG:
			(*_log_func)(format, _dflt_error_format(format, buf));
			break;
		}
	}

	/*
	 * if the text is targetted for the display, write it
	 * using the currently registered display logging function
	 */
	if (dest & SCR) {
		switch (type) {
		    case ERRMSG:
			(*_error_func)(format, buf);
			break;
			/*
			 * progress msgs use same format as status
			 * msgs when writing to the screen
			 */
		    case PROGMSG:
		    case STATMSG:
			(*_status_func)(format, buf);
			break;
		    case WARNMSG:
			(*_warning_func)(format, buf);
			break;
		}
	}
}

/*
 * Function:	bootlog_available
 * Description:	Determines whether a remote bootlog facility is available
 *		to be invoked.
 * Scope:	private
 * Parameters:	none
 * Return:		B_TRUE - bootlog facility can be invoked
 *		B_FALSE - bootlog facility must not be invoked
 */
static boolean_t
bootlog_available(void)
{
	static boolean_t answered = B_FALSE;
	static boolean_t answer = B_FALSE;

	if (answered) {
		/* already been here, and we know the answer */
		return (answer);
	}

	/* first time in routine.  figure out answer */


	/*
	 * Thanks to 4864280, we have not allow calls to
	 * bootlog() if we can't find the corresponding
	 * dynamic library that provides the bootlog()
	 * implementation, otherwise a runtime linking
	 * error will occur, and the application
	 * that causes bootlog() to be called will abort.
	 */
	if (dlsym(RTLD_DEFAULT, "bootlog") == NULL) {
		/* no libwanboot, therefore no bootlog */
		answer = B_FALSE;
	} else {
		answer = B_TRUE;
	}
	answered = B_TRUE;

	return (answer);
}
