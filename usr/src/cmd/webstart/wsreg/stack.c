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

#pragma ident	"@(#)stack.c	1.5	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "stack.h"
#include "wsreg.h"

/*
 * The private data associated with a stack.  The stack is
 * based on a list object.
 */
struct _Stack_private
{
	List *list;
};

/*
 * Frees the specified stack.  Data in the stack will be
 * freed with the specified free function.  If the free
 * function is not specified, the data will not be freed.
 */
static void
stk_free(Stack *stack, Free free_function)
{
	stack->pdata->list->free(stack->pdata->list, free_function);
	free(stack->pdata);
	free(stack);
}

/*
 * Pushes the specified data onto the specified stack.  The
 * data is not cloned, so the caller should not free the
 * data after this call.
 */
static void
stk_push(Stack *stack, void *data)
{
	List *list = stack->pdata->list;

	/*
	 * The top of the stack is at index
	 * 0 in the list.  Always add and remove
	 * from the beginning of the list.
	 */
	list->insert_element_at(list, data, 0);
}

/*
 * Pops the data from the top of the stack.  The data
 * pointer is returned.  It is up to the caller to
 * free the data.
 */
static void *
stk_pop(Stack *stack)
{
	List *list = stack->pdata->list;
	/*
	 * The top of the stack is at index 0
	 * in the list.  Always add and remove
	 * from the beginning of the list.
	 */
	return (list->remove_element_at(list, 0));
}

/*
 * Returns the size of the specified stack.
 */
static int
stk_size(Stack *stack)
{
	List *list = stack->pdata->list;
	return (list->size(list));
}

/*
 * A diagnostic method that prints the contents
 * of the stack.  The specified print function
 * is called to print the data in the stack.
 */
static void
stk_print(Stack *stack, Print print_function)
{
	if (stack != NULL) {
		List *list = stack->pdata->list;
		list->print(list, print_function);
	}
}

/*
 * Creates a new stack and returns it to the caller.
 */
Stack *
_wsreg_stack_create()
{
	Stack *s = (Stack *)wsreg_malloc(sizeof (Stack));
	struct _Stack_private *p = NULL;

	/*
	 * Load the method set.
	 */
	s->create = _wsreg_stack_create;
	s->free = stk_free;
	s->push = stk_push;
	s->pop = stk_pop;
	s->size = stk_size;
	s->print = stk_print;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Stack_private *)
	    wsreg_malloc(sizeof (struct _Stack_private));
	memset(p, 0, sizeof (struct _Stack_private));
	p->list = _wsreg_list_create();
	s->pdata = p;
	return (s);
}
