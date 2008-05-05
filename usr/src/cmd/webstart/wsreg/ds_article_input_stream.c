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


#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "ds_article_input_stream.h"

/*
 * This structure is used to bind object-private data to
 * a Ds_article_input_stream object.
 */
struct _Ds_article_input_stream_private
{
	File_reader	*freader;
} _Ds_article_input_stream_private;

/*
 * Frees the specified article input stream.
 */
static void
dsais_free(Ds_article_input_stream *ain)
{
	free(ain->pdata);
	free(ain);
}

/*
 * Closes the specified article input stream.
 * The article input stream is freed as a result
 * of this call.
 */
static void
dsais_close(Ds_article_input_stream *ain)
{
	dsais_free(ain);
}

/*
 * Returns true if the specified input stream contains more
 * articles; false otherwise.
 */
static Boolean
dsais_has_more_articles(Ds_article_input_stream *ain)
{
	return (ain->pdata->freader->has_more_lines(
		ain->pdata->freader));
}

/*
 * Returns the next article from the specified article
 * input stream.  If no more articles are associated with
 * the specified input stream, NULL is returned.
 */
static Article *
dsais_get_next_article(Ds_article_input_stream *ain)
{
	Article *_article = _wsreg_article_create();
	Article *article = NULL;

	if (ain->has_more_articles(ain)) {
		article = _article->read_data_sheet(ain->pdata->freader);
	}
	_article->free(_article);
	return (article);
}

/*
 * Creates a data stream article input stream.
 */
static Ds_article_input_stream *
dsais_create()
{
	Ds_article_input_stream *ain =
	    (Ds_article_input_stream*)
	    wsreg_malloc(sizeof (Ds_article_input_stream));
	struct _Ds_article_input_stream_private *p = NULL;

	/*
	 * Load the method set.
	 */
	ain->open = _wsreg_dsais_open;
	ain->close = dsais_close;
	ain->has_more_articles = dsais_has_more_articles;
	ain->get_next_article = dsais_get_next_article;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Ds_article_input_stream_private *)
	    wsreg_malloc(sizeof (struct _Ds_article_input_stream_private));
	memset(p, 0, sizeof (struct _Ds_article_input_stream_private));
	ain->pdata = p;
	return (ain);
}

/*
 * Opens a new data sheet article input stream that reads
 * from the specified File_reader object.  The resulting
 * article input stream must be closed after use.
 */
Ds_article_input_stream *
_wsreg_dsais_open(File_reader *freader)
{
	Ds_article_input_stream *ais = NULL;

	if (freader != NULL) {
		ais = dsais_create();
		ais->pdata->freader = freader;
	}
	return (ais);
}
