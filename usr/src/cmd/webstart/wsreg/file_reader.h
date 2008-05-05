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

#ifndef _FILE_READER_H
#define	_FILE_READER_H


#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"

#define	File_reader struct _File_reader

struct _File_reader_private;
struct _File_reader
{
	void (*free)(File_reader *fr);
	char *(*read_line)(File_reader *fr);
	Boolean (*has_more_lines)(File_reader *fr);
	void (*set_log_file)(File_reader *fr, FILE *logfile);
	void (*set_echo_function)(File_reader *fr,
	    void (*echo_function)(const char *line));
	struct _File_reader_private *pdata;
};

File_reader *
_wsreg_freader_create(FILE *file, char **end_tokens);


#ifdef	__cplusplus
}
#endif

#endif /* _FILE_READER_H */
