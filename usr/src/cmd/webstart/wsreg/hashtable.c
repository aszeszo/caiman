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


#include <stdlib.h>
#include <strings.h>
#include "hashtable.h"
#include "wsreg.h"

/*
 * The hashtable entry is an element in a very lightweight
 * list that is used for each "bucket" in the hashtable.
 */
#define	Hashtable_entry struct _Hashtable_entry
struct _Hashtable_entry
{
	int hash;
	char *key;
	void *value;
	Hashtable_entry *next;
} _Hashtable_entry;

/*
 * This structure is used to bind object-private data to
 * a hashtable object.
 */
struct _Hashtable_private
{
	Hashtable_entry** table;
	int count;
	int threshold;
	float load_factor;
	int table_length;
} _Hashtable_private;


/*
 * Returns the hashcode of the specified string.
 */
static int
get_hashcode(const char *string)
{
	int h = 0;
	int off = 0;
	int len = 0;
	int i = 0;

	if (string != NULL)
		len = strlen(string);

	if (len < 16) {
		for (i = len; i > 0; i--) {
			h = (h * 37) + string[off++];
		}
	} else {
		int skip = len / 8;
		for (i = len; i > 0; i -= skip, off += skip) {
			h = (h * 39) + string[off];
		}
	}
	return (h);
}

/*
 * Creates a hashtable entry object.  The hashtable entry is
 * a very lightweight list element that is used to contain
 * all entries mapped to the same hashtable bucket.
 */
static Hashtable_entry*
hashtable_entry_create()
{
	Hashtable_entry *entry = (Hashtable_entry*)
	    wsreg_malloc(sizeof (Hashtable_entry));
	entry->hash = 0;
	entry->key = NULL;
	entry->value = NULL;
	entry->next = NULL;
	return (entry);
}

/*
 * Frees the specified hashtable entry structure and returns
 * a pointer to the next entry in the list.
 */
static Hashtable_entry*
hashtable_entry_free(Hashtable_entry *entry, Free_function free_data)
{
	Hashtable_entry *next_entry = NULL;

	next_entry = entry->next;
	if (entry->key != NULL)
		free(entry->key);
	if (entry->value != NULL &&
	    free_data != NULL)
		(*free_data)(entry->value);
	free(entry);
	return (next_entry);
}

/*
 * Frees the specified hashtable.  If a free_data function
 * is provided, it will be used to free the hashtable values.
 * The hashtable's keys are always freed.
 *
 * If the free_data function is not provided (passed in as NULL)
 * the values are not freed by this function.
 */
static void
htbl_free(Hashtable *hashtable, Free_function free_data)
{
	Hashtable_entry **table = hashtable->pdata->table;
	Hashtable_entry *entry;
	int i;
	int table_length = hashtable->pdata->table_length;

	for (i = 0; i < table_length; i++) {
		for (entry = table[i]; entry != NULL; ) {
			entry = hashtable_entry_free(entry,
			    free_data);
		}
	}
	free(table);
	free(hashtable->pdata);
	free(hashtable);
}

/*
 * Returns the number of entries currently stored in the
 * specified hashtable.
 */
static int
htbl_size(Hashtable *hashtable)
{
	return (hashtable->pdata->count);
}

/*
 * Returns true if the specified hashtable is empty (if
 * its size is 0); false otherwise.
 */
static Boolean
htbl_is_empty(Hashtable *hashtable)
{
	return (hashtable->pdata->count == 0);
}

/*
 * Returns a list containing all of the keys in the specified
 * hashtable.  The keys are not cloned when added to the
 * resulting list.
 */
static List*
htbl_keys(Hashtable *hashtable)
{
	List* keys = _wsreg_list_create();
	Hashtable_entry **table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int i;
	Hashtable_entry *entry;

	for (i = 0; i < table_length; i++) {
		for (entry = table[i]; entry != NULL; entry = entry->next) {
			keys->add_element(keys, entry->key);
		}
	}
	return (keys);
}

/*
 * Returns a list containing all of the values in the
 * specified hashtable.  The values are not cloned when
 * added to the resulting list.
 */
static List *
htbl_elements(Hashtable *hashtable)
{
	List* values = _wsreg_list_create();
	Hashtable_entry **table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int i;
	Hashtable_entry *entry;

	for (i = 0; i < table_length; i++) {
		for (entry = table[i]; entry != NULL; entry = entry->next) {
			values->add_element(values, entry->value);
		}
	}
	return (values);
}

/*
 * Returns true if the specified hashtable contains a value
 * corresponding to the specified key; false otherwise.
 */
static Boolean
htbl_contains_key(Hashtable *hashtable, const char *key)
{
	Hashtable_entry** table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int hash = get_hashcode(key);
	int index = (hash & 0x7FFFFFFF) % table_length;
	Hashtable_entry *e = NULL;

	for (e = table[index]; e != NULL; e = e->next) {
		if ((e->hash == hash) && strcmp(e->key, key) == 0) {
			return (TRUE);
		}
	}
	return (FALSE);
}

/*
 * Returns the value associated with the specified key in the
 * specified hashtable.  If no value is currently associated
 * with the specified key, NULL is returned.
 */
static void *
htbl_get(Hashtable *hashtable, const char *key)
{
	Hashtable_entry **table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int hash = get_hashcode(key);
	int index = (hash & 0x7FFFFFFF) % table_length;
	Hashtable_entry *e = NULL;

	for (e = table[index]; e != NULL; e = e->next) {
		if ((e->hash == hash) && strcmp(e->key, key) == 0) {
			return (e->value);
		}
	}
	return (NULL);
}

/*
 * Causes the specified hashtable to resize itself and to rehash its
 * current contents into the newly sized hashtable.  This function
 * is used when the number of key/value pairs stored in the hashtable
 * grows so large that the current hashtable size cannot access it
 * efficiently.
 */
static void
rehash(Hashtable *hashtable)
{
	int i;
	int old_capacity = hashtable->pdata->table_length;
	Hashtable_entry **old_table = hashtable->pdata->table;

	int new_capacity = old_capacity * 2 + 1;
	Hashtable_entry **new_table =
	    (Hashtable_entry**)wsreg_malloc(sizeof (Hashtable_entry*) *
		(new_capacity + 1));
	memset(new_table, 0, sizeof (Hashtable_entry*) * (new_capacity + 1));

	hashtable->pdata->table = new_table;
	hashtable->pdata->table_length = new_capacity;

	hashtable->pdata->threshold =
	    (int)(new_capacity * hashtable->pdata->load_factor);

	for (i = old_capacity; i-- > 0; ) {
		Hashtable_entry *old;
		for (old = old_table[i]; old != NULL; ) {
			int index;
			Hashtable_entry *e = old;
			old = old->next;

			index = (e->hash & 0x7FFFFFFF) % new_capacity;
			e->next = new_table[index];
			new_table[index] = e;
		}
	}
	free(old_table);
}

/*
 * Adds the specified key/value pair to the specified hashtable.
 * If a value is currently associated with the specified key,
 * that value is returned.
 *
 * The specified key is cloned and the clone of that key is
 * stored in the hashtable.  The specified value is not cloned.
 * its reference is stored directly in the hashtable.
 */
static void *
htbl_put(Hashtable *hashtable, const char *key, void *value)
{
	Hashtable_entry **table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int hash = get_hashcode(key);
	int index = (hash & 0x7FFFFFFF) % table_length;
	Hashtable_entry *e;

	for (e = table[index]; e != NULL; e = e->next) {
		if ((e->hash == hash) && strcmp(e->key, key) == 0) {
			void *old = e->value;
			e->value = value;
			return (old);
		}
	}

	if (hashtable->pdata->count >= hashtable->pdata->threshold) {
		rehash(hashtable);
		return (hashtable->put(hashtable, key, value));
	}

	/*
	 * Create the new entry;
	 */
	e = hashtable_entry_create();
	e->hash = hash;
	e->key = (char *)wsreg_malloc(sizeof (char) * (strlen(key) + 1));
	strcpy(e->key, key);
	e->value = value;
	e->next = table[index];
	table[index] = e;
	hashtable->pdata->count++;
	return (NULL);
}

/*
 * Removes the value associated with the specified key from
 * the specified hashtable.  The old value is returned to
 * the caller.
 */
static void *
htbl_remove(Hashtable *hashtable, const char *key)
{
	Hashtable_entry **table = hashtable->pdata->table;
	int table_length = hashtable->pdata->table_length;
	int hash = get_hashcode(key);
	int index = (hash & 0x7FFFFFFF) % table_length;
	void *value;
	Hashtable_entry *prev;
	Hashtable_entry *e;

	for (e = table[index], prev = NULL; e != NULL; prev = e, e = e->next) {
		if ((e->hash == hash) && strcmp(e->key, key) == 0) {
			if (prev != NULL) {
				prev->next = e->next;
			}
			else
				{
					table[index] = e->next;
				}
			hashtable->pdata->count--;
			value = e->value;
			free(e->key);
			free(e);
			return (value);
		}
	}
	return (NULL);
}

/*
 * Removes all key/value pairs from the specified hashtable.
 * If a free_data function is provided, that function will be
 * used to free all values currently stored in the specified
 * hashtable.  Otherwise, the values are not freed.
 */
static void
htbl_clear(Hashtable *hashtable, Free_function free_data)
{
	Hashtable_entry **table = hashtable->pdata->table;
	Hashtable_entry *entry;
	int i;
	int table_length = hashtable->pdata->table_length;

	for (i = 0; i < table_length; i++) {
		for (entry = table[i]; entry != NULL; ) {
			entry = hashtable_entry_free(entry, free_data);
		}
		table[i] = NULL;
	}
	hashtable->pdata->count = 0;
}

/*
 * Creates a new hashtable object and returns it to the caller.
 */
Hashtable*
_wsreg_hashtable_create()
{
	Hashtable *htbl = (Hashtable*)wsreg_malloc(sizeof (Hashtable));
	float load_factor = 0.75;
	int initial_capacity = 101;
	struct _Hashtable_private *p = NULL;

	/*
	 * Load the method set.
	 */
	htbl->create = _wsreg_hashtable_create;
	htbl->free = htbl_free;
	htbl->size = htbl_size;
	htbl->is_empty = htbl_is_empty;
	htbl->keys = htbl_keys;
	htbl->elements = htbl_elements;
	htbl->contains_key = htbl_contains_key;
	htbl->get = htbl_get;
	htbl->put = htbl_put;
	htbl->remove = htbl_remove;
	htbl->clear = htbl_clear;

	p = (struct _Hashtable_private *)
	    wsreg_malloc(sizeof (struct _Hashtable_private));
	memset(p, 0, sizeof (struct _Hashtable_private));
	p->load_factor = load_factor;
	p->table = (Hashtable_entry**)wsreg_malloc(sizeof (Hashtable_entry*) *
	    (initial_capacity + 1));
	memset(p->table, 0, sizeof (Hashtable_entry*) * (initial_capacity + 1));
	p->table_length = initial_capacity;
	p->threshold = (int)(initial_capacity * load_factor);
	htbl->pdata = p;
	return (htbl);
}
