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
 * Copyright 1999 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _LIST_H
#define	_LIST_H


#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"

#define	List struct _List

	typedef void (*Free)(void *value);
	typedef int (*Equal)(const void *value1, const void *value2);
	typedef void *(*Clone)(void *value);
	typedef void (*Print)(int pos, void *data);

	struct _List_private;
	struct _List
	{
		List *(*create)();
		void (*free)(List *list, Free free_function);
		void (*add_element)(List *list, void *data);
		Boolean (*insert_element_at)(List *list, void *data, int pos);
		void *(*remove_element_at)(List *list, int pos);
		void *(*remove)(List *list, const void *data,
		    Equal equal_function);
		int (*size)(List *list);
		void (*reset_iterator)(List *list);
		Boolean  (*has_more_elements)(List *list);
		void *(*next_element)(List *list);
		void *(*element_at)(List *list, int pos);
		int  (*index_of)(List *list, void *data, Equal equal_function);
		Boolean  (*contains)(List *list, void *data,
		    Equal equal_function);
		List *(*intersection)(List *list1, List *list2,
		    Equal equal_function);
		List *(*difference)(List *list1, List *list2,
		    Equal equal_function);
		List *(*clone)(List *list, Clone clone_function);
		void (*print)(List *list, Print print_function);

		struct _List_private *pdata;
	};

	List *_wsreg_list_create();


#ifdef	__cplusplus
}
#endif

#endif /* _LIST_H */
