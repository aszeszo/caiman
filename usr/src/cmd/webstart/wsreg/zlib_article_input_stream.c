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

#pragma ident	"@(#)zlib_article_input_stream.c	1.6	06/02/27 SMI"

/*
 * In order to compile this object, you must have zlib
 * header files.  This object was made to compile against
 * zlib version 1.1.3. Also, you must have the
 * $(ZLIB_HOME)/contrib/minizip/unzip.h header file.
 *
 * In order to link with this object file, you must have
 * the zlib library to link against as well as the
 * $(ZLIB_HOME)/contrib/minizip/unzip.o object file.
 */
#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <limits.h>
#include <zlib.h>
#include <unzip.h>
#include "zlib_article_input_stream.h"
#include "string_util.h"
#include "wsreg.h"

/*
 * This structure contains data private to a zlib article
 * input stream object.
 */
struct _Zlib_article_input_stream_private
{
	char		*filename;
	unzFile		unzip_file;
	unz_global_info	global_info;
	char		*current_file_name;
	int		current_file_count;
	unz_file_info	current_file_info;
} _Zlib_article_input_stream_private;

/*
 * Frees the specified article input stream.
 */
static void
zlibais_free(Zlib_article_input_stream *ain)
{
	if (ain->pdata->filename != NULL)
		free(ain->pdata->filename);
	if (ain->pdata->unzip_file != NULL)
		free(ain->pdata->unzip_file);
	if (ain->pdata->current_file_name != NULL)
		free(ain->pdata->current_file_name);
	free(ain->pdata);
	free(ain);
}

/*
 * Closes the specified article input stream.  The
 * article input stream object is freed as a result of
 * this call.
 */
static void
zlibais_close(Zlib_article_input_stream *ain)
{
	unzCloseCurrentFile(ain->pdata->unzip_file);
	zlibais_free(ain);
}

/*
 * Returns true if the specified article input stream
 * has more articles to read.
 */
static Boolean
zlibais_has_more_articles(Zlib_article_input_stream *ain)
{
	return (ain->pdata->current_file_count <
	    ain->pdata->global_info.number_entry);
}

/*
 * Returns the next article from the specified article
 * input stream object.  It is the caller's responsibility
 * to free the resulting article.
 */
static Article *
zlibais_get_next_article(Zlib_article_input_stream *ain)
{
	Article *_article = _wsreg_article_create();
	Article *article = NULL;

	if (ain->has_more_articles(ain)) {
		char article_name[PATH_MAX];
		int result = unzGetCurrentFileInfo(ain->pdata->unzip_file,
		    &ain->pdata->current_file_info,
		    article_name,
		    sizeof (article_name),
		    NULL, 0, NULL, 0);
		if (result != UNZ_OK) {
			_article->free(_article);
			return (NULL);
		}
		/*
		 * Now, we have to read the file contents from the zip stream.
		 * NOTE:The uncompressed size is
		 * ain->current_file_info.uncompressed_size
		 */
		{
			int buffer_size =
			    ain->pdata->current_file_info.uncompressed_size;
			char *buffer = (char *)
			    wsreg_malloc(sizeof (char) * (buffer_size + 1));
			memset(buffer, 0, sizeof (char) * (buffer_size + 1));

			result = unzOpenCurrentFile(ain->pdata->unzip_file);
			if (result != UNZ_OK) {
				printf("error %d with zipfile\n", result);
			}
			result = unzReadCurrentFile(ain->pdata->unzip_file,
			    buffer,
			    buffer_size);
			if (result < 0) {
				printf("error with zipfile in read\n");
			}

			article = _article->from_string(article_name, buffer);

			free(buffer);
			result = unzCloseCurrentFile(ain->pdata->unzip_file);
			if (result != UNZ_OK) {
				printf("error %d during CloseCurrentFile\n",
				    result);
			}
		}
		/*
		 * Finally, prepare to read the next file from the zip stream.
		 */
		ain->pdata->current_file_count++;
		if (ain->pdata->current_file_count <
		    ain->pdata->global_info.number_entry) {
			result = unzGoToNextFile(ain->pdata->unzip_file);
		}
	}
	_article->free(_article);
	return (article);
}

/*
 * Creates a new article input stream that reads articles from
 * a zip file using the zlib library.
 */
static Zlib_article_input_stream *
zlibais_create()
{
	Zlib_article_input_stream *ain =
	    (Zlib_article_input_stream*)
	    wsreg_malloc(sizeof (Zlib_article_input_stream));
	struct _Zlib_article_input_stream_private *p = NULL;

	/*
	 * Load the method set.
	 */
	ain->open = _wsreg_zlibais_open;
	ain->close = zlibais_close;
	ain->has_more_articles = zlibais_has_more_articles;
	ain->get_next_article = zlibais_get_next_article;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Zlib_article_input_stream_private *)
	    wsreg_malloc(sizeof (struct _Zlib_article_input_stream_private));
	memset(p, 0,
	    sizeof (struct _Zlib_article_input_stream_private));
	ain->pdata = p;
	return (ain);
}

Zlib_article_input_stream *
_wsreg_zlibais_open(const char *filename)
{
	Zlib_article_input_stream *ais = NULL;
	int result;
	String_util *sutil = _wsreg_strutil_initialize();

	if (filename != NULL) {
		ais =
		    zlibais_create();
		ais->pdata->filename = sutil->clone(filename);
		ais->pdata->unzip_file = unzOpen(ais->pdata->filename);
		if (ais->pdata->unzip_file == NULL) {
			zlibais_free(ais);
			return (NULL);
		}

		result = unzGetGlobalInfo(ais->pdata->unzip_file,
		    &ais->pdata->global_info);
		if (result != UNZ_OK) {
			unzCloseCurrentFile(ais->pdata->unzip_file);
			zlibais_free(ais);
			return (NULL);
		}
	}
	return (ais);
}
