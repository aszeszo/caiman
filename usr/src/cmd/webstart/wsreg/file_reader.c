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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)file_reader.c	1.7	06/02/27 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <strings.h>
#include "file_reader.h"
#include "wsreg.h"
#include "string_util.h"

/*
 * Private class data associated with the File_reader.
 */
struct _File_reader_private
{
	FILE *file;
	char **end_tokens;
	Boolean finished;
	FILE *logfile;
	void (*echo_function)(const char *line);
} _File_reader_private;

/*
 * Frees the specified File_reader object.
 */
static void
fr_free(File_reader *fr)
{
	if (fr->pdata->end_tokens != NULL) {
		int index = 0;
		while (fr->pdata->end_tokens[index] != NULL) {
			free(fr->pdata->end_tokens[index++]);
		}
		free(fr->pdata->end_tokens);
	}
	free(fr->pdata);
	free(fr);
}

/*
 * Private method that determines if the specified
 * line begins with an end token that is optionally
 * provided in the File_reader constructor.
 */
static Boolean
is_end_token(File_reader *fr, char *line)
{
	Boolean result = FALSE;
	if (line != NULL && fr->pdata->end_tokens != NULL) {
		int index = 0;
		while (fr->pdata->end_tokens[index] != NULL) {
			if (strncmp(line, fr->pdata->end_tokens[index],
			    strlen(fr->pdata->end_tokens[index])) == 0) {
				/*
				 * Found and end token.
				 */
				result = TRUE;
				return (result);
			}
			index++;
		}
	}
	return (result);
}

/*
 * Logs all input from the specified file reader object
 * to the associated log file.  This is the varargs version
 * of the log function.  The log_message function should
 * be used by clients.
 */
static void
vlog_message(File_reader *fr, const char *format, va_list ap)
{
	if (fr->pdata->logfile != NULL) {
		(void) vfprintf(fr->pdata->logfile, format, ap);
		fflush(fr->pdata->logfile);
	}
}

/*
 * Private method. Logs the specified message to the
 * log file associated with the specified file reader
 * object.
 */
/*ARGSUSED*/
static void
log_message(File_reader *fr, const char *format, int count, ...)
{
	va_list ap;
	va_start(ap, count);
	vlog_message(fr, format, ap);
}



/*
 * Reads will occur in increments  of BUFFER_SIZE.
 */
#define	BUFFER_SIZE 20

/*
 * Reads an entire line, even if it is longer than
 * BUFFER_SIZE.  This method is guaranteed to return
 * the entire line by allocating memory to store
 * the line.  It is the responsibility of the caller
 * to free the resulting line.
 *
 * If the end of file is encountered, all data
 * preceding the eof is returned.  If no data precedes
 * eof, NULL is returned and a subsequent call to
 * has_more_lines() will return false.
 *
 * If the line matches an end token (if provided in the
 * constructor), NULL is returned and a subsequent
 * call to has_more_lines will return false.
 */
static char *
fr_read_line(File_reader *fr)
{
	static char line_buffer[BUFFER_SIZE];
	char *next_line = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Only read the next line if the file reader has
	 * not found an end token.
	 */
	if (fr->has_more_lines(fr)) {
		/*
		 * Read the entire next line - even if it is longer
		 * than BUFFER_SIZE.
		 */
		char *result = fgets(line_buffer, BUFFER_SIZE, fr->pdata->file);
		if (result == NULL) {
			fr->pdata->finished = TRUE;
			return (NULL);
		}
		next_line = sutil->clone(result);
		while (!fr->pdata->finished &&
		    result[strlen(result) - 1] != '\n') {
			result = fgets(line_buffer, BUFFER_SIZE,
			    fr->pdata->file);
			if (result == NULL) {
				fr->pdata->finished = TRUE;
			} else {
				next_line = (char *)realloc(next_line,
				    sizeof (char) * (strlen(next_line) +
					strlen(result) + 1));
				strcat(next_line, result);
			}
		}

		/*
		 * Strip off the '\n'.
		 */
		if (next_line != NULL &&
		    next_line[strlen(next_line) - 1] == '\n') {
			next_line[strlen(next_line) - 1] = '\0';
		}

		/*
		 * Log the line.  We do that here so we can log the
		 * end token also.
		 */
		log_message(fr, "%s\n", 1, next_line);
		if (fr->pdata->echo_function != NULL) {
			(*fr->pdata->echo_function)(next_line);
		}

		/*
		 * Check to see if we encountered an end token at the beginning
		 * of the new line.
		 */
		if (is_end_token(fr, next_line)) {
			fr->pdata->finished = TRUE;
			free(next_line);
			return (NULL);
		}
	}

	return (next_line);
}

/*
 * Returns false if the specified File_reader object
 * has encountered an eof or an end token; true
 * otherwise.
 */
static Boolean
fr_has_more_lines(File_reader *fr)
{
	return (!(fr->pdata->finished));
}

/*
 * Sets the FILE used to write to the log file into
 * the specified file reader object.
 */
static void
fr_set_log_file(File_reader *fr, FILE *logfile)
{
	fr->pdata->logfile = logfile;
}

/*
 * Sets the echo function.  The echo function is used as
 * a diagnostic.  Every line read by the specified file
 * reader object will be sent to the echo function.
 *
 * If NULL is specified as the echo function, file reader
 * echo will be disabled.
 */
static void
fr_set_echo_function(File_reader *fr, void (*echo_function)(const char *line))
{
	fr->pdata->echo_function = echo_function;
}

/*
 * File_reader constructor.  The new File_reader
 * will read from the specified file and terminate
 * upon reading any of the specified end tokens.
 */
File_reader *
_wsreg_freader_create(FILE *file, char **end_tokens)
{
	File_reader *fr = (File_reader*)wsreg_malloc(sizeof (File_reader));
	struct _File_reader_private *p = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Load the method set.
	 */
	fr->free = fr_free;
	fr->read_line = fr_read_line;
	fr->has_more_lines = fr_has_more_lines;
	fr->set_log_file = fr_set_log_file;
	fr->set_echo_function = fr_set_echo_function;

	/*
	 * Initialize the private data.
	 */
	p = (struct _File_reader_private *)wsreg_malloc(
		sizeof (struct _File_reader_private));
	memset(p, 0, sizeof (struct _File_reader_private));
	p->file = file;
	if (end_tokens != NULL) {
		int count = 0;
		int index = 0;

		/*
		 * Copy the end tokens.
		 */
		while (end_tokens[index] != NULL) {
			index++;
		}

		count = index;
		p->end_tokens = (char **)
		    wsreg_malloc(sizeof (char *) * (count + 1));
		index = 0;
		while (end_tokens[index] != NULL) {
			p->end_tokens[index] =
			    sutil->clone(end_tokens[index]);
			index++;
		}
		p->end_tokens[count] = NULL;
	}

	fr->pdata = p;
	return (fr);
}
