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

#pragma ident	"@(#)file_token.c	1.7	06/02/27 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "file_token.h"
#include "wsreg.h"
#include "string_util.h"

/*
 * This structure is used to associate object-private
 * data to a File_token object.
 */
struct _File_token_private
{
	char *filename;
	off_t size;
	time_t modification_time;
} _File_token_private;

/*
 * Frees the specified file token object.
 */
static void
ft_free(File_token *ft)
{
	if (ft->pdata->filename != NULL)
		free(ft->pdata->filename);
	free(ft->pdata);
	free(ft);
}

/*
 * Returns true if the two specified file tokens are
 * equal; false otherwise.
 */
static Boolean
ft_equals(File_token *ft1, File_token *ft2)
{
	if (ft1 == ft2)
		return (TRUE);
	if (ft1 != NULL && ft2 != NULL) {
		if (strcmp(ft1->pdata->filename, ft2->pdata->filename) != 0)
			return (FALSE);
		if (ft1->pdata->size != ft2->pdata->size)
			return (FALSE);
		if (ft1->pdata->modification_time !=
		    ft2->pdata->modification_time)
			return (FALSE);
		return (TRUE);
	}
	return (FALSE);
}

/*
 * Returns true if ft1 is newer than ft2; false otherwise.
 */
static Boolean
ft_is_newer(File_token *ft1, File_token *ft2)
{
	return (ft1->pdata->modification_time >
	    ft2->pdata->modification_time);
}

/*
 * Returns a clone of the specified file token.
 * It is the responsibility of the caller to free
 * the resulting file token.
 */
static File_token *
ft_clone(File_token *ft)
{
	File_token *result = NULL;

	result = _wsreg_ftoken_create(ft->pdata->filename);
	result->pdata->size = ft->pdata->size;
	result->pdata->modification_time = ft->pdata->modification_time;
	return (result);
}

/*
 * Diagnostic function that prints the specified file token.
 */
static void
ft_print(File_token *ft)
{
	(void) printf("File_token: ");
	if (ft != NULL) {
		if (ft->pdata != NULL) {
			(void) printf("name=%s ", ft->pdata->filename);
			(void) printf("size=%d ", (int)ft->pdata->size);
			(void) printf("modified_time=%ld ",
			    ft->pdata->modification_time);
		}
	} else {
		(void) printf("NULL");
	}
	(void) printf("\n");
}

/*
 * Creates a file token that represents the current state
 * of the specified file.  The file token is used to determine
 * if the associated file has been modified.
 */
File_token *
_wsreg_ftoken_create(const char *filename)
{
	File_token *ft = (File_token*)wsreg_malloc(sizeof (File_token));
	struct _File_token_private *p = NULL;
	struct stat statbuf;
	int result = 0;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Load the method set.
	 */
	ft->free = ft_free;
	ft->equals = ft_equals;
	ft->is_newer = ft_is_newer;
	ft->clone = ft_clone;
	ft->print = ft_print;

	/*
	 * Initialize the private data.
	 */
	p = (struct _File_token_private *)wsreg_malloc(
		sizeof (struct _File_token_private));
	memset(p, 0, sizeof (struct _File_token_private));
	ft->pdata = p;

	ft->pdata->filename = sutil->clone(filename);
	result = stat(filename, &statbuf);
	if (result != -1) {
		ft->pdata->size = statbuf.st_size;
		ft->pdata->modification_time = statbuf.st_mtime;
	}
	return (ft);
}
