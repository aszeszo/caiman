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

#ifndef _HASHTABLE_H
#define	_HASHTABLE_H


#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#include <stdlib.h>
#include "list.h"
#include "boolean.h"

#define	Hashtable struct _Hashtable

struct _Hashtable_private;

/*
 * The free function is used to free values in the
 * Hashtable.
 */
typedef void (*Free_function)(void*);

struct _Hashtable
{
	/*
	 * Creates an empty hashtable.
	 */
	Hashtable *(*create)();

	/*
	 * Frees the specified hashtable.  All keys are freed,
	 * and all values will be freed using the specified
	 * free function.  If the free function is not specified
	 * the values will not be freed.
	 */
	void (*free)(Hashtable *hashtable, Free_function);

	/*
	 * Returns the number of entries in the specified
	 * hashtable.
	 */
	int (*size)(Hashtable *hashtable);

	/*
	 * Returns true if the specified hashtable is empty;
	 * false otherwise.
	 */
	Boolean (*is_empty)(Hashtable *hashtable);

	/*
	 * Returns the list of keys in the specified
	 * hashtable.  The memory references in the
	 * resulting list are the same as the ones in the
	 * hashtable.  The list must be freed before the
	 * hashtable, and its keys should not be freed.
	 */
	List *(*keys)(Hashtable *hashtable);

	/*
	 * Returns the list of values in the specified
	 * hashtable.  The memory references in the
	 * resulting list are the same as the ones in the
	 * hashtable.  The list must be freed before the
	 * hashtable, and its values should not be freed.
	 */
	List* (*elements)(Hashtable *hashtable);

	/*
	 * Returns true if the specified hashtable contains the
	 * specified key; false otherwise.
	 */
	Boolean (*contains_key)(Hashtable *hashtable, const char *key);

	/*
	 * Returns the value associated with the specified key in
	 * the specified hashtable.  The resulting memory reference
	 * is the same as the one in the hashtable, so it
	 * should not be freed.
	 */
	void *(*get)(Hashtable *hashtable, const char *key);

	/*
	 * Puts the specified key/value pair into the specified
	 * hashtable.  The value pointer is simply placed in the
	 * hashtable, so be sure not to free it after this call.
	 */
	void *(*put)(Hashtable *hashtable, const char *key, void *value);

	/*
	 * Removes the value associated with the specified key in the
	 * specified hashtable.  The resulting value (if any) is
	 * returned, and should be freed by the caller.
	 */
	void *(*remove)(Hashtable *hashtable, const char *key);

	/*
	 * Clears the specified hashtable.  This is similar to free
	 * in that all of the key/value pairs in the hashtable are
	 * freed, except that the hashtable itself is not freed.
	 */
	void (*clear)(Hashtable *hashtable, Free_function);

	struct _Hashtable_private *pdata;
};

Hashtable *_wsreg_hashtable_create();


#ifdef	__cplusplus
}
#endif

#endif /* _HASHTABLE_H */
