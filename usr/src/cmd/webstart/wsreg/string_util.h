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

#ifndef _STRING_UTIL_H
#define	_STRING_UTIL_H

#pragma ident	"@(#)string_util.h	1.8	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"

#define	String_util struct _String_util

	struct _String_util
	{
		char *(*clone)(const char *str);
		char *(*to_lower)(const char *str);
		char *(*to_upper)(const char *str);
		Boolean (*equals_ignore_case)(const char *str1,
		    const char *str2);
		Boolean (*starts_with)(const char *str1, const char *str2);
		int (*last_index_of)(const char *str, const int c);
		Boolean (*contains_substring)(const char *str,
		    const char *substr);
		char *(*append)(char *str1, const char *str2);
		char *(*prepend)(char *str1, const char *str2);
		void (*trim_whitespace)(char *str1);
		char (*get_escaped_character)(const char c);
	};

	String_util *_wsreg_strutil_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _STRING_UTIL_H */
