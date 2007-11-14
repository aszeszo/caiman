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

#ifndef _XML_TAG_H
#define	_XML_TAG_H

#pragma ident	"@(#)xml_tag.h	1.5	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"
#include "string_map.h"

#define	Xml_tag struct _Xml_tag

	struct _Xml_tag_private;
	struct _Xml_tag
	{
		void (*free)(Xml_tag *xt);
		char *(*get_tag_string)(const Xml_tag *xt);
		void (*set_value_string)(Xml_tag *xt, const char *value);
		char *(*get_value_string)(const Xml_tag *xt);
		void (*set_tag)(Xml_tag *xt, String_map *xm, const char *tag);
		int (*get_tag)(const Xml_tag *xt);
		void (*set_end_tag)(Xml_tag *xt, Boolean end);
		Boolean (*is_end_tag)(const Xml_tag *xt);

		struct _Xml_tag_private *pdata;
	};

/*
 * Creates an xml tag
 */
	Xml_tag *_wsreg_xtag_create();


#ifdef	__cplusplus
}
#endif

#endif /* _XML_TAG_H */
