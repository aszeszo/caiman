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

#ifndef _ARTICLE_H
#define	_ARTICLE_H

#pragma ident	"@(#)article.h	1.5	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#include "boolean.h"
#include "revision.h"
#include "list.h"
#include "file_reader.h"
#include "wsreg.h"

#define	Article struct _Article

struct _Article_private;
struct _Article
{
	Article *(*create)();
	void (*free)(Article *a);

	Article *(*from_string)(char *name, char *buffer);

	Article *(*read_data_sheet)(File_reader *freader);
	Article *(*from_component)(Wsreg_component *component);
	int (*set_mnemonic)(Article *a, const char *mnemonic);
	char *(*get_mnemonic)(Article *a);
	int (*set_id)(Article *a, const char *id);
	char *(*get_id)(Article *a);
	void (*generate_id)(Article *a);
	char **(*get_child_mnemonics)(Article *a);
	char **(*get_child_ids)(Article *a);
	char *(*set_property)(Article *a,
	    const char *property_name,
	    const char *property_value);
	char *(*get_property)(Article *a,
	    const char *property_name);
	char *(*remove_property)(Article *a,
	    const char *property_name);
	char **(*get_property_names)(Article *a);
	int (*add_revision)(Article *a,
	    Revision *r);
	Revision **(*get_revisions)(Article *a);
	char *(*get_version)(Article *a);
	void (*print)(Article *a, FILE *file);

	struct _Article_private *pdata;
};

Article *_wsreg_article_create();

#ifdef	__cplusplus
}
#endif

#endif /* _ARTICLE_H */
