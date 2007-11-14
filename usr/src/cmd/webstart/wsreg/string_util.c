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

#pragma ident	"@(#)string_util.c	1.10	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <ctype.h>
#include <strings.h>

#include "wsreg.h"
#include "string_util.h"

/*
 * The String_util object only has static methods.
 * This object is created only once and that
 * single reference is passed to all clients.  There
 * is no free method so the object will not get
 * corrupted inadvertently.
 */
static String_util *string_util = NULL;

/*
 * This character map is used to map escaped characters
 * to their non-escaped equivalents.
 */
static char map[255];

/*
 * Clones the specified string.  The resulting string must
 * be freed by the caller.  This method handles NULL
 * strings.
 */
static char *
sutil_clone(const char *str)
{
	char *result = NULL;
	if (str != NULL) {
		int len = strlen(str);
		result = (char *)wsreg_malloc(sizeof (char) * (len + 1));
		strcpy(result, str);
	}
	return (result);
}

/*
 * Converts the specified string to lower case.
 * The resulting string must be freed by the
 * caller.
 */
static char *
sutil_to_lower(const char *str)
{
	char *result = NULL;
	if (str != NULL) {
		int index = 0;
		result = sutil_clone(str);
		while (result[index] != '\0') {
			result[index] = tolower(result[index]);
			index++;
		}
	}
	return (result);
}

/*
 * Converts the specified string to upper case.
 * The resulting string must be freed by the
 * caller.
 */
static char *
sutil_to_upper(const char *str)
{
	char *result = NULL;
	if (str != NULL) {
		int index = 0;
		result = sutil_clone(str);
		while (result[index] != '\0') {
				result[index] = toupper(result[index]);
				index++;
			}
	}
	return (result);
}

/*
 * Returns true if the specified strings are equal
 * ignoring case; false otherwise.  This method correctly
 * handles the case in which either or both strings are
 * NULL.
 */
static Boolean
sutil_equals_ignore_case(const char *str1, const char *str2)
{
	int result = FALSE;
	if (str1 != NULL && str2 != NULL) {
		int cmp = 0;

		if (string_util == NULL) {
			/*
			 * Initialize the string object.
			 */
			_wsreg_strutil_initialize();
		}
		cmp = strcasecmp(str1, str2);
		if (cmp == 0)
			result = TRUE;
	}
	return (result);
}

/*
 * Returns true if the the string str1 begins with the
 * substring str2.
 */
static Boolean
sutil_starts_with(const char *str1, const char *str2)
{
	Boolean result = FALSE;
	if (str1 == str2) {
		result = TRUE;
	} else {
		if (str1 != NULL && str2 != NULL &&
		    strncmp(str1, str2, strlen(str2)) == 0) {
			result = TRUE;
		}
	}
	return (result);
}

/*
 * Returns the index in the specified string at which the specified
 * character can be found, starting from the end of the string.
 * If the specified character is not in the string, -1 is returned.
 */
static int
sutil_last_index_of(const char *str, const int c)
{
	int result = -1;
	if (str != NULL) {
		Boolean done = FALSE;
		int index = strlen(str);
		while (!done && index != -1) {
			if (str[index] == c) {
				done = TRUE;
				result = index;
			}
			index--;
		}
	}
	return (result);
}

/*
 * Returns true if the specified string contains the specified
 * substring; false otherwise.
 */
static Boolean
sutil_contains_substring(const char *str, const char *substr)
{
	Boolean result = FALSE;
	if (str != NULL && substr != NULL) {
		if (strstr(str, substr) != NULL) {
			result = TRUE;
		}
	}
	return (result);
}

/*
 * Appends str2 to str1 and returns the result.  This function
 * handles the case when either of the strings is NULL.
 *
 * This function makes it easy to grow a string as other strings
 * are appended.  This is the equivelant of strcat, only the
 * original string is grown to the necessary size.
 */
static char *
sutil_append(char *str1, const char *str2)
{
	char *result = str1;
	if (str2 != NULL) {
		if (result == NULL) {
			return (sutil_clone(str2));
		} else {
			result = (char *)wsreg_malloc(sizeof (char) *
			    (strlen(str1) + strlen(str2) + 1));
			(void) sprintf(result, "%s%s", str1, str2);
			free(str1);
		}
	}
	return (result);
}

/*
 * Prepends str2 onto str1.  This function handles the case when either
 * of the strings is NULL.
 *
 * This function grows str1 to accomodate the prepended str2.
 */
static char *
sutil_prepend(char *str1, const char *str2)
{
	char *result = str1;
	if (str1 == NULL) {
		if (str2 != NULL) {
			return (sutil_clone(str2));
		}
	} else {
		result = (char *)wsreg_malloc(sizeof (char) * (strlen(str1) +
		    strlen(str2) + 1));
		(void) sprintf(result, "%s%s", str2, str1);
		free(str1);
	}
	return (result);
}

/*
 * This method trims whitespace from the end of the
 * specified string.
 */
static void
sutil_trim_whitespace(char *str1)
{
	if (str1 != NULL) {
		int index;
		for (index = strlen(str1) - 1;
			index > 0 && isspace((int)str1[index]);
			index--) {
			str1[index] = '\0';
		}
	}
}

/*
 * This function returns the escaped equivalent of the specified
 * character.
 */
static char
sutil_get_escaped_character(const char c)
{
	return (map[(int)c]);
}

/*
 * Initializes the string_util object.  All methods
 * in this object are static, so no need to create
 * multiple copies of this object.  Notice that
 * there is no free method.
 */
String_util *
_wsreg_strutil_initialize()
{
	String_util *sutil = string_util;
	if (sutil == NULL) {
		int i;
		sutil = (String_util *)wsreg_malloc(sizeof (String_util));

		/*
		 * Initialize the method set.
		 */
		sutil->clone = sutil_clone;
		sutil->to_lower = sutil_to_lower;
		sutil->to_upper = sutil_to_upper;
		sutil->equals_ignore_case = sutil_equals_ignore_case;
		sutil->starts_with = sutil_starts_with;
		sutil->last_index_of = sutil_last_index_of;
		sutil->contains_substring = sutil_contains_substring;
		sutil->append = sutil_append;
		sutil->prepend = sutil_prepend;
		sutil->trim_whitespace = sutil_trim_whitespace;
		sutil->get_escaped_character = sutil_get_escaped_character;

		/*
		 * Initialize the character map.
		 */
		for (i = 0; i < 255; i++) {
			map[i] = (char)i;
		}
		map[(int)'\a'] = '\a';
		map[(int)'\b'] = '\b';
		map[(int)'\r'] = '\r';
		map[(int)'\f'] = '\f';
		map[(int)'\t'] = '\t';
		map[(int)'\n'] = '\n';
		map[(int)'\v'] = '\v';

		string_util = sutil;
	}
	return (sutil);
}
