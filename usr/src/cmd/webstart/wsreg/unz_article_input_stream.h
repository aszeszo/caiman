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

#ifndef _UNZ_ARTICLE_INPUT_STREAM_H
#define	_UNZ_ARTICLE_INPUT_STREAM_H


#ifdef __cplusplus
extern "C" {
#endif

#include "article.h"
#include "boolean.h"

#define	Unz_article_input_stream struct _Unz_article_input_stream
	struct _Unz_article_input_stream_private;

	struct _Unz_article_input_stream
	{
		/*
		 * Opens the article input stream.
		 */
		Unz_article_input_stream *(*open)(const char *filename,
		    int *result);

		/*
		 * Closes the specified article input stream.
		 */
		void (*close)(Unz_article_input_stream *ain);

		/*
		 * Returns true if more articles are available in the
		 * specified article input stream.
		 */
		Boolean (*has_more_articles)(Unz_article_input_stream *ain);

		/*
		 * Returns the next article from the specified
		 * article input stream.  The returned article
		 * must be freed by the caller.
		 */
		Article *(*get_next_article)(Unz_article_input_stream *ain);

		/*
		 * Returns the number of articles to be converted.
		 */
		int (*get_article_count)(Unz_article_input_stream *ain);

		struct _Unz_article_input_stream_private *pdata;
	};

	Unz_article_input_stream *_wsreg_uzais_open(const char *filename,
	    int *result);


#ifdef	__cplusplus
}
#endif

#endif /* _UNZ_ARTICLE_INPUT_STREAM_H */
