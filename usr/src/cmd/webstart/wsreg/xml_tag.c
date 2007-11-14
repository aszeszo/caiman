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

#pragma ident	"@(#)xml_tag.c	1.10	06/02/27 SMI"

#include <stdlib.h>
#include <strings.h>
#include "xml_tag.h"
#include "wsreg.h"
#include "string_util.h"

/*
 * Private data associated with an xml tag object.
 */
struct _Xml_tag_private
{
	char *tag_string;
	char *value_string;
	int tag_id;
	Boolean end;
} _Xml_tag_private;

/*
 * Frees the specified xml tag object.
 */
static void
xt_free(Xml_tag *xt)
{
	if (xt->pdata->tag_string != NULL)
		free(xt->pdata->tag_string);
	if (xt->pdata->value_string != NULL)
		free(xt->pdata->value_string);
	free(xt->pdata);
	free(xt);
}

/*
 * Returns the tag string from the specified
 * xml tag.
 */
static char *
xt_get_tag_string(const Xml_tag *xt)
{
	return (xt->pdata->tag_string);
}

/*
 * Sets the specified value into the specified
 * xml tag.
 */
static void
xt_set_value_string(Xml_tag *xt, const char *value)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (xt->pdata->value_string != NULL) {
		free(xt->pdata->value_string);
		xt->pdata->value_string = NULL;
	}
	if (value != NULL) {
		xt->pdata->value_string = sutil->clone(value);
	}
}

/*
 * Returns the value from the specified
 * xml tag.
 */
static char *
xt_get_value_string(const Xml_tag *xt)
{
	return (xt->pdata->value_string);
}

/*
 * Sets the specified tag into the specified xml
 * tag object.
 */
static void
xt_set_tag(Xml_tag *xt, String_map *xm, const char *tag)
{
	int tag_id;
	String_util *sutil = _wsreg_strutil_initialize();

	if (xt->pdata->tag_string != NULL) {
		free(xt->pdata->tag_string);
		xt->pdata->tag_string = NULL;
	}

	tag_id = xm->get_id(xm, tag);
	if (tag_id != -1) {
		xt->pdata->tag_id = tag_id;
		xt->pdata->tag_string = sutil->clone(tag);
	}
}

/*
 * Returns the index of the tag from the specified
 * xml tag.
 */
static int
xt_get_tag(const Xml_tag *xt)
{
	return (xt->pdata->tag_id);
}

/*
 * Sets the flag that indicates the specified
 * xml tag is an end tag.
 */
static void
xt_set_end_tag(Xml_tag *xt, Boolean end)
{
	xt->pdata->end = end;
}

/*
 * Returns true if the specified xml tag
 * is an end tag.
 */
static Boolean
xt_is_end_tag(const Xml_tag *xt)
{
	return (xt->pdata->end);
}

/*
 * Creates a new xml tag object.
 */
Xml_tag *
_wsreg_xtag_create()
{
	Xml_tag *xt = (Xml_tag*)wsreg_malloc(sizeof (Xml_tag));
	struct _Xml_tag_private *p = NULL;

	/*
	 * Load the method set.
	 */
	xt->free = xt_free;
	xt->get_tag_string = xt_get_tag_string;
	xt->set_value_string = xt_set_value_string;
	xt->get_value_string = xt_get_value_string;
	xt->set_tag = xt_set_tag;
	xt->get_tag = xt_get_tag;
	xt->set_end_tag = xt_set_end_tag;
	xt->is_end_tag = xt_is_end_tag;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Xml_tag_private *)
	    wsreg_malloc(sizeof (struct _Xml_tag_private));
	memset(p, 0, sizeof (struct _Xml_tag_private));
	xt->pdata = p;
	return (xt);
}
