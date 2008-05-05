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

#ifndef _STRING_MAP_H
#define	_STRING_MAP_H


#ifdef __cplusplus
extern "C" {
#endif

#define	String_map struct _String_map

	struct _String_map_private;
	struct _String_map
	{
		void (*free)(String_map *xm);
		int  (*get_id)(String_map *xm, const char *string);
		char *(*get_string)(String_map *xm, int id);

		struct _String_map_private *pdata;
	};

/*
 * Creates an xml tag map
 */
	String_map *_wsreg_stringmap_create(char **string_set);


#ifdef	__cplusplus
}
#endif

#endif /* _STRING_MAP_H */
