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

#pragma ident	"@(#)list.c	1.10	06/02/27 SMI"

#include <stdlib.h>
#include <string.h>
#include "list.h"
#include "wsreg.h"

#define	List_element struct _List_element
#define	Private_element struct _List_element_private

/*
 * The _List_element class is private to the List class.  It
 * serves as a container in which data can be stored and linked
 * together with other such containers into a list.
 */
struct _List_element_private;
struct _List_element
{
	List_element *(*create)(void *data);
	void *(*free)(List_element *element);
	Private_element *pdata;
} _List_element;

/*
 * This structure contains data that is private to a list element object.
 */
struct _List_element_private
{
	void *data;
	List_element *previous;
	List_element *next;
} _List_element_private;

/*
 * This structure contains data that is private to a list object.
 */
struct _List_private
{
	unsigned int size;
	List_element *head;
	List_element *tail;
	List_element *current;
} _List_private;

/*
 * This function frees the memory associated with the specified element.
 * It is up to the caller to free the associated data.
 */
static void *
lel_free(List_element *element)
{
	void *data = NULL;
	if (element != NULL) {
		if (element->pdata != NULL) {
			data = element->pdata->data;
			element->pdata->next = NULL;
			element->pdata->previous = NULL;
			free(element->pdata);
		}
		free(element);
	}
	return (data);
}

/*
 * Creates a new list element object that is initialized to store
 * the specified data.  The data is not cloned, so the caller must
 * be sure not to free the data after this function is called.
 */
static List_element *
lel_create(void *data)
{
	List_element *le = (List_element*)wsreg_malloc(sizeof (List_element));
	Private_element *p = NULL;

	/*
	 * Load the method set.
	 */
	le->create = lel_create;
	le->free =   lel_free;

	p = (Private_element*)wsreg_malloc(sizeof (Private_element));
	memset(p, 0, sizeof (Private_element));

	p->data = data;
	le->pdata = p;
	return (le);
}

/*
 * Removes the list element identified by the specified position from
 * the specified list.  The data associated with that element is
 * returned.  It is the responsibility of the caller to free the
 * data.
 */
static void *
lst_remove_element_at(List *list, int pos)
{
	void *result = NULL;
	List_element * element;
	int index = 0;
	element = list->pdata->head;

	for (index = 0;
		index < pos && element != NULL;
		index++) {
		element = element->pdata->next;
	}

	if (element != NULL) {
		/*
		 * The element is in the list.
		 */
		if (element->pdata->previous != NULL) {
			element->pdata->previous->pdata->next =
			    element->pdata->next;
		}
		if (element->pdata->next != NULL) {
			element->pdata->next->pdata->previous =
			    element->pdata->previous;
		}
		list->pdata->size--;

		if (element == list->pdata->head) {
			list->pdata->head = element->pdata->next;
		}
		if (element == list->pdata->tail) {
			list->pdata->tail = element->pdata->previous;
		}
		result = element->pdata->data;
		element->free(element);
	}
	return (result);
}

/*
 * Removes the specified data from the specified list.  The
 * equal function is called to determine if the specified data
 * is equal to data stored in any element in the list.
 *
 * If the equal function is not specified (i.e. NULL), a
 * simple pointer comparison is performed to determine equality.
 *
 * The data associated with the element being removed from the
 * list is returned to the caller.  It is the caller's responsibility
 * to free the resulting data.
 */
static void *
lst_remove(List *list, const void *data, Equal equal_function)
{
	void *result = NULL;
	List_element * element;
	int index = 0;
	Boolean done = FALSE;
	element = list->pdata->head;

	for (index = 0;
		!done && element != NULL;
		index++) {
		if ((equal_function != NULL &&
		    (*equal_function)(data, element->pdata->data)) ||
		    data == element->pdata->data) {
				/*
				 * Found the element.
				 */
			done = TRUE;
			break;
		}
		element = element->pdata->next;
	}

	if (element != NULL) {
		/*
		 * The element is in the list.
		 */
		if (element->pdata->previous != NULL) {
			element->pdata->previous->pdata->next =
			    element->pdata->next;
		}
		if (element->pdata->next != NULL) {
			element->pdata->next->pdata->previous =
			    element->pdata->previous;
		}
		list->pdata->size--;

		if (element == list->pdata->head) {
			list->pdata->head = element->pdata->next;
		}
		if (element == list->pdata->tail) {
			list->pdata->tail = element->pdata->previous;
		}
		result = element->pdata->data;
		element->free(element);
	}
	return (result);
}

/*
 * Returns the index in the specified list at which the specified
 * data is stored.  If the specified data is not stored in the
 * list, -1 is returned.
 *
 * The specified equal function is used to determine if the specified
 * data matches any data element stored in the specified list.  If
 * the equal function is not specified, a simple pointer comparison
 * is used to determine equality.
 */
static int
lst_index_of(List *list, void *data, Equal equal_function)
{
	int result = 0;
	void *d = NULL;

	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		d = list->next_element(list);
		if ((*equal_function)(d, data))
			return (result);
		result++;
	}
	return (-1);
}

/*
 * Returns the size of the specified list.
 */
static int
lst_size(List *list)
{
	return (list->pdata->size);
}

/*
 * Frees the specified list.
 *
 * The specified free function is used to free the list's contents.  If
 * the free function is not specified, the contents will not be
 * freed with the list.  In that case, it is the caller's responsibility
 * to free the contents of the list.
 */
static void
lst_free(List *list, Free free_function)
{
	void *data = NULL;

	if (list == NULL) {
		return;
	}

	if (list->pdata != NULL) {
		while (list->pdata->head != NULL) {
			data = lst_remove_element_at(list, 0);

			if (free_function != NULL) {
				(*free_function)(data);
			}
		}
		free(list->pdata);
	}
	free(list);
}

/*
 * Adds the specified data to the specified list.  The
 * data is not cloned, so the caller must not free the
 * specified data after this function is called.
 */
static void
lst_add_element(List *list, void *data)
{
	List_element *element = lel_create(data);
	if (list->pdata->head == NULL) {
		/*
		 * This is the first element in the list.
		 */
		element->pdata->previous = NULL;
		element->pdata->next = NULL;
		list->pdata->head = element;
		list->pdata->tail = element;
	} else {
		/*
		 * Append the element to the end of the list.
		 */
		element->pdata->previous = list->pdata->tail;
		element->pdata->next = NULL;
		list->pdata->tail->pdata->next = element;
		list->pdata->tail = element;
	}
	list->pdata->size++;
}

/*
 * Inserts the specified data into the specified list at the
 * specified position.  If the size of the list is such that
 * the insertion at the specified position is impossible,
 * false is returned.
 */
static Boolean
lst_insert_element_at(List *list, void *data, int pos)
{
	Boolean result = FALSE;
	int index = 0;

	List_element *element = lel_create(data);
	List_element *current_element = list->pdata->head;

	if (list == NULL) {
		return (result);
	}

	for (index = 0;
		index < pos && current_element != NULL;
		index++) {
		current_element = current_element->pdata->next;
	}

	if (current_element != NULL) {
		/*
		 * Found the position element.  Insert the new element here.
		 */
		element->pdata->previous = current_element->pdata->previous;
		current_element->pdata->previous = element;
		element->pdata->next = current_element;
		if (element->pdata->previous != NULL) {
			element->pdata->previous->pdata->next = element;
		}

		if (current_element == list->pdata->head) {
			list->pdata->head = element;
		}
		list->pdata->size++;
		result = TRUE;
	}
	return (result);
}

/*
 * Prepares the specified list for sequential iteration through
 * the list of data.
 */
static void
lst_reset_iterator(List *list)
{
	list->pdata->current = list->pdata->head;
}

/*
 * Returns true if the iterator position is such that more
 * elements can be read from the specified list; false
 * otherwise.
 *
 * The list must first be prepared for iteration with the
 * reset_iterator method.
 */
static Boolean
lst_has_more_elements(List *list)
{
	return (list->pdata->current != NULL);
}

/*
 * Returns the next piece of data being stored in the specified
 * list.  The data is not cloned, so the caller should not free
 * the resulting data.
 *
 * The list must first be prepared for iteration with the
 * reset_iterator method.
 */
static void *
lst_next_element(List *list)
{
	void *result = NULL;
	List_element *next = list->pdata->current;
	if (next != NULL) {
		list->pdata->current = list->pdata->current->pdata->next;
		result = next->pdata->data;
	}
	return (result);
}

/*
 * Returns the data stored in the specified list at the specified
 * position.  The resulting data is not a clone, so the caller must
 * not free it.
 */
static void*
lst_element_at(List *list, int pos)
{
	void *result = NULL;
	List_element *element;
	int index = 0;

	if (list == NULL) {
		return (NULL);
	}

	element = list->pdata->head;
	for (index = 0;
		index < pos && element != NULL;
		index++) {
		element = element->pdata->next;
	}
	if (element != NULL) {
		result = element->pdata->data;
	}

	return (result);
}

/*
 * Returns true if the specified list contains the specified data;
 * false otherwise.
 *
 * The specified equal function is used to determine if the specified
 * data matches any data being stored in the specified list.  If
 * the equal function is not specified, a simple pointer comparison
 * is used to determine equality.
 */
static Boolean
lst_contains(List *list, void *data, Equal equal)
{
	void *d = NULL;
	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		d = list->next_element(list);
		if ((*equal)(d, data)) {
			return (TRUE);
		}
	}
	return (FALSE);
}


/*
 * Calculates the intersection of the two specified lists.  The
 * resulting intersection is returned in the form of a list.
 *
 * The specified equal function is used to determine if data
 * stored in one list matches any data being stored in the other
 * list.  If the equal function is not specified, a simple pointer
 * comparison is used to determine equality.
 */
static List *
lst_intersection(List *list1, List *list2, Equal equal)
{
	/*
	 * This function always returns a valid list.
	 */
	List *result = list1->create();
	void *data = NULL;
	list1->reset_iterator(list1);
	while (list1->has_more_elements(list1)) {
		data = list1->next_element(list1);
		if (list2->contains(list2, data, equal)) {
			/*
			 * The element should be added to the resulting list.
			 */
			result->add_element(result, data);
		}
	}
	return (result);
}

/*
 * Calculates the difference between the two lists.  This calculation
 * is essentially (list1 - list2).  That is, the difference is all of
 * the data contained in list 1 that does not also appear in list
 * 2.
 *
 * The specified equal function is used to determine if data
 * stored in one list matches any data being stored in the other
 * list.  If the equal function is not specified, a simple pointer
 * comparison is used to determine equality.
 */
static List *
lst_difference(List *list1, List *list2, Equal equal_function)
{
	/*
	 * This function always returns a valid list.
	 */
	List *result = list1->create();
	void *data = NULL;

	list1->reset_iterator(list1);
	while (list1->has_more_elements(list1)) {
		data = list1->next_element(list1);
		if (!list2->contains(list2, data,
		    equal_function)) {
			/*
			 * The element should be added to the resulting list.
			 */
			result->add_element(result, data);
		}
	}
	return (result);
}

/*
 * Clones the specified list.  The specified clone function is used
 * to clone the data in the specified list.  If no clone function is
 * specified, the data pointers in the original list are copied to
 * the resulting list.
 */
static List *
lst_clone(List *list, Clone clone_function)
{
	List *cloned_list = list->create();
	void *data = NULL;

	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		data = list->next_element(list);
		if (clone_function != NULL) {
			/*
			 * Use the clone function to duplicate the element.
			 */
			cloned_list->add_element(cloned_list,
			    (*clone_function)(data));
		} else {
			/*
			 * Simply copy the data pointer to the new list.
			 */
			cloned_list->add_element(cloned_list, data);
		}
	}
	return (cloned_list);
}

/*
 * Prints the contents of the specified list.  This is a diagnostic
 * method.
 *
 * The specified print function is called on to print the data in
 * the list.  The print function must be specified.
 */
static void
lst_print(List *list, Print print_function)
{
	int pos = 0;
	void *data = NULL;
	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		data = list->next_element(list);
		(*print_function)(pos, data);
		pos++;
	}
}

/*
 * Creates a new, empty list object.
 */
List*
_wsreg_list_create()
{
	List *l = (List *)wsreg_malloc(sizeof (List));
	struct _List_private *p = NULL;

	/*
	 * Load the method set.
	 */
	l->create = _wsreg_list_create;
	l->free = lst_free;
	l->add_element = lst_add_element;
	l->insert_element_at = lst_insert_element_at;
	l->remove_element_at = lst_remove_element_at;
	l->remove = lst_remove;
	l->size = lst_size;
	l->reset_iterator = lst_reset_iterator;
	l->has_more_elements = lst_has_more_elements;
	l->next_element = lst_next_element;
	l->element_at = lst_element_at;
	l->index_of = lst_index_of;
	l->contains = lst_contains;
	l->intersection = lst_intersection;
	l->difference = lst_difference;
	l->clone = lst_clone;
	l->print = lst_print;

	/*
	 * Initialize the private data.
	 */
	p = (struct _List_private *)
	    wsreg_malloc(sizeof (struct _List_private));
	memset(p, 0, sizeof (struct _List_private));
	l->pdata = p;
	return (l);
}
