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

#ifndef _DS_ARTICLE_INPUT_STREAM_H
#define	_DS_ARTICLE_INPUT_STREAM_H

#pragma ident	"@(#)ds_article_input_stream.h	1.3	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "article.h"
#include "boolean.h"
#include "file_reader.h"

#define	Ds_article_input_stream struct _Ds_article_input_stream
struct _Ds_article_input_stream_private;

struct _Ds_article_input_stream
{
	/*
	 * Opens the article input stream.
	 */
	Ds_article_input_stream* (*open)(File_reader *freader);

	/*
	 * Closes the specified article input stream.
	 */
	void (*close)(Ds_article_input_stream *ain);

	/*
	 * Returns true if more articles are available in the
	 * specified article input stream.
	 */
	Boolean (*has_more_articles)(Ds_article_input_stream *ain);

	/*
	 * Returns the next article from the specified
	 * article input stream.  The returned article
	 * must be freed by the caller.
	 */
	Article *(*get_next_article)(Ds_article_input_stream *ain);

	struct _Ds_article_input_stream_private *pdata;
};

Ds_article_input_stream *_wsreg_dsais_open(File_reader *freader);


#ifdef	__cplusplus
}
#endif

#endif /* _DS_ARTICLE_INPUT_STREAM_H */
