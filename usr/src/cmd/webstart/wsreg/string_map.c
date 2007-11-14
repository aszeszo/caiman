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

#pragma ident	"@(#)string_map.c	1.6	06/02/27 SMI"

#include <stdlib.h>
#include <strings.h>
#include "string_map.h"
#include "string_util.h"
#include "wsreg.h"

/*
 * The private data associated with a string map object.
 */
struct _String_map_private
{
	char **string_set;
	int map_size;
} _String_map_private;

/*
 * Frees the specified string map.
 */
static void
sm_free(String_map *sm)
{
	if (sm->pdata->string_set != NULL) {
		int i = 0;
		while (sm->pdata->string_set[i] != NULL) {
			free(sm->pdata->string_set[i]);
			i++;
		}
		free(sm->pdata->string_set);
	}
	free(sm->pdata);
	free(sm);
}

/*
 * Returns the index in the specified string map of the
 * specified string.  If the string is not in the specified
 * string map, -1 is returned.
 */
static int
sm_get_id(String_map *sm, const char *string)
{
	char **string_set = sm->pdata->string_set;
	int id = 0;

	for (id = 0; string_set[id] != NULL; id++) {
			if (strcmp(string, string_set[id]) == 0)
				return (id);
		}
	return (-1);
}

/*
 * Returns the string associated with the specified id in
 * the specified string map.  If the specified id is not
 * found in the string map, NULL is returned.
 *
 * The caller should not free the resulting string.
 */
static char *
sm_get_string(String_map *sm, int id)
{
	char **string_set = sm->pdata->string_set;

	if (sm->pdata->map_size >= id)
		return (string_set[id]);
	return (NULL);
}

/*
 * Creates a new string map from the specified set
 * of strings.  The set of strings must be a NULL-terminated
 * array of strings.
 */
String_map *
_wsreg_stringmap_create(char **string_set)
{
	String_map *sm = (String_map*)wsreg_malloc(sizeof (String_map));
	String_util *sutil = _wsreg_strutil_initialize();
	struct _String_map_private *p = NULL;
	int map_size = 0;
	int index = 0;

	/*
	 * Load the method set.
	 */
	sm->free = sm_free;
	sm->get_id = sm_get_id;
	sm->get_string = sm_get_string;

	/*
	 * Initialize the private data.
	 */
	p = (struct _String_map_private *)
	    wsreg_malloc(sizeof (struct _String_map_private));

	/*
	 * Figure out how many strings there are.
	 */
	while (string_set[map_size] != NULL)
		map_size++;

	p->string_set = (char **)
	    wsreg_malloc(sizeof (char *) * (map_size + 1));
	for (index = 0; index < map_size; index++) {
		p->string_set[index] = sutil->clone(string_set[index]);
	}
	p->string_set[map_size] = NULL;
	p->map_size = map_size;

	sm->pdata = p;
	return (sm);
}
