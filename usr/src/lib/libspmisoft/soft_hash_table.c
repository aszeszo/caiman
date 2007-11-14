/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)soft_hash_table.c	1.1	07/11/08 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <soft_hash_table.h>

/* Allocates and returns a Node data structure. */
Node *
getnode()
{
	Node *mynode = (Node *) malloc(sizeof (Node));
	if (mynode == NULL) {
		return (NULL);
	}

	mynode->next = NULL;
	mynode->prev = NULL;
	mynode->next_in_hashchain = NULL;
	mynode->prev_in_hashchain = NULL;
	mynode->key = NULL;
	mynode->data = NULL;
	mynode->delproc = NULL;

	return (mynode);
}


/*
 * Allocates and returns a List data structure. Also allocates an empty node for
 * the head of the linked list of nodes and an empty node for the head of the
 * chain in each hash table bucket.
 */
List *
getlist()
{
	int i;
	List *mylist = (List *) malloc(sizeof (List));
	if (mylist == NULL) {
		return (NULL);
	}

	/* Empty node used for head of chain in each hashtable bucket */
	for (i = 0; i < HASHTABLESIZE; i++) {
		mylist->hashtable[i] = getnode();
	}

	/* Empty node used for head of linked list */
	mylist->list = getnode();

	/* Set up the circular list */
	mylist->list->next = mylist->list;
	mylist->list->prev = mylist->list;

	return (mylist);
}


/*
 * The hashing function for locating the correct hash bucket in the hashtable
 * for the List data structure.
 */
static int
hashfunc(char *mykey)
{
	int i, index = 0;

	if (mykey == NULL) {
		return (-1);
	}

	/*
	 * Using the ascii values of the charactures in the package name to
	 * generate the hash key.
	 */
	for (i = 0; (i < strlen(mykey)) && (mykey[i] != 0); i++) {
		index += (int)mykey[i];
	}
	return (index % HASHTABLESIZE);
}

/*
 * Adds a node to the List *mylist.
 * Prepended to the linked list as well as inserted as
 * the head of the chain in the correct hash bucket.
 */
int
addnode(List *mylist, Node *node)
{
	int h_index;
	Node *swap_node = NULL;
	Node *bucket = NULL;

	/* Check to see if entry already exists */
	if ((mylist == NULL) || (node == NULL) ||
	    (findnode(mylist, node->key) != NULL)) {
		return (-1);
	}

	h_index = hashfunc(node->key);
	if (h_index == -1) {
		return (-1);
	}

	bucket = mylist->hashtable[h_index];

	/* Add Node after head of chain in hashtable bucket. */
	swap_node = bucket->next_in_hashchain;
	node->prev_in_hashchain = bucket;
	bucket->next_in_hashchain = node;
	if (swap_node == NULL) {
		/* Adding Node to an empty chain */
		node->next_in_hashchain = NULL;
	} else {
		node->next_in_hashchain = swap_node;
		swap_node->prev_in_hashchain = node;
	}

	/* Add node to the end of the circular linked list. */
	if ((mylist->list != NULL) && (mylist->list->prev != NULL) &&
	    (mylist->list->next != NULL)) {
		node->prev = mylist->list->prev;
		node->next = mylist->list;
		node->prev->next = node;
		node->next->prev = node;
	} else {
		/* there is a problem with the linked list */
		return (-1);
	}

	return (0);
}



/*
 * Deletes node from linked list and from chain in the matching hash bucket.
 * If node is at the beginning of the linked list or at the head of the chain
 * in a hash bucket, the behavior of this function is undefined.  We need to
 * pass in the List in order to correctly delete this node.
 * This function will not be called for the empty nodes at the head of the
 * hash buckets and linked list, so we can assume that every node has a
 * previous node in the chain or linked list.
 */
void
delnode(Node *mynode)
{

	if (mynode == NULL) {
		return;
	}


	/* Delete from circular linked list */
	/* Both of the following if statements should always be true */
	if (mynode->prev != NULL) {
		mynode->prev->next = mynode->next;
	}
	if (mynode->next != NULL) {
		mynode->next->prev = mynode->prev;
	}


	/* Remove from chain in hashtable bucket */
	/* Both of the following if statements should always be true */
	if (mynode->prev_in_hashchain != NULL) {
		mynode->prev_in_hashchain->next_in_hashchain =
		    mynode->next_in_hashchain;
	}
	if (mynode->next_in_hashchain != NULL) {
		mynode->next_in_hashchain->prev_in_hashchain =
		    mynode->prev_in_hashchain;
	}


	if (mynode->delproc != NULL) {
		mynode->delproc(mynode);
	}
	free(mynode);
}

/*
 * Walks linked list and deletes each Node after the head of the list.
 * Then deletes the head and frees the hashtable array and the List data
 * structure.
 */
void
dellist(List **llist)
{
	int i;
	Node *dnode = NULL; /* Node to be deleted */
	Node *mynode = NULL;
	List *mylist = *llist;

	if (mylist == NULL) {
		return;
	}

	if (mylist->list != NULL) {
		/* Skipping empty node */
		mynode = mylist->list->next;

		/* Delete rest of nodes on the linked list */
		/* mynode should never be NULL */
		while ((mynode != NULL) && (mynode != mylist->list)) {
			dnode = mynode;
			mynode = mynode->next;
			delnode(dnode);
		}
	}

	/*
	 * Delete empty nodes used for head of chain in each
	 * hashtable bucket
	 */
	for (i = 0; i < HASHTABLESIZE; i++) {
		free(mylist->hashtable[i]);
	}

	/* Delete empty node at head of linked list */
	free(mylist->list);

	free(mylist);
	*llist = NULL;
}

/*
 * Finds the node by locating the correct hash bucket and then using the
 * key to find the correct entry on the chain.
 */
Node *
findnode(List *mylist,  char *key)
{
	Node *node = NULL;
	int h_index =  0;

	if ((mylist == NULL) || (key == NULL)) {
		return (NULL);
	}

	h_index = hashfunc(key);
	if (h_index == -1) {
		return (NULL);
	}

	/* Skipping empty node at head of chain in hashtable bucket. */
	node = mylist->hashtable[h_index]->next_in_hashchain;

	if (node == NULL) {
		return (NULL);
	}

	/* walk the chain in the hash bucket to find the matching Node */
	do {
		if (strcmp(node->key, key)  == 0) {
			return (node);
		} else {
			node = node->next_in_hashchain;
		}
	} while (node != NULL);

	/* Couldn't find a match */
	return (NULL);
}

/* Orders the linked list according to the return of func() */
void
sortlist(List *mylist, int func(Node *node_a, Node *node_b))
{
	Node *head = NULL;
	Node *mynode = NULL;
	Node *pnt1 = NULL;
	Node *pnt2 = NULL;
	int swapped = 1;

	/* Exit if not initialized or empty list */
	if ((mylist == NULL) || (mylist->list == NULL) ||
	    (mylist->list->prev == mylist->list)) {
		return;
	}

	/* Skipping the empty node on the head of the list */
	head = mylist->list->next;

	/* break the circular list */
	mylist->list->prev->next = NULL;
	mylist->list->prev = NULL;

	/*
	 * This is a simple Bubble Sort.  Each time an ellement is swapped we
	 * return to the head of the list to check for next ellement to be
	 * swapped.
	 */
	while (1) {
		if (swapped) {
			pnt1 = head;
			pnt2 = head->next;
			swapped = 0;
		} else if ((pnt1->next != NULL) && (pnt2->next != NULL)) {
			pnt1 = pnt1->next;
			pnt2 = pnt2->next;
		} else {
			break;
		}
		if (func(pnt1, pnt2) > 0) {
			pnt1->next = pnt2->next;
			pnt2->prev = pnt1->prev;
			pnt1->prev = pnt2;
			pnt2->next = pnt1;
			pnt2->prev->next = pnt2;
			if (pnt1->next != NULL) {
				pnt1->next->prev = pnt1;
			}
			if (pnt1 == head) {
				head = pnt2;
			}
			swapped = 1;
		}
	}

	/* Reset the circular list */

	/* Skip empty head of linked list */
	mynode = mylist->list->next;
	/* Walk to end of list */
	while (mynode != NULL) {
		if (mynode->next != NULL) {
			mynode = mynode->next;
		} else {
			break;
		}
	}
	mylist->list->prev = mynode;
	mynode->next = mylist->list;
}



/* Walks the linked list and calls func() for each node */
int
walklist(List *mylist, int func(Node *node, caddr_t data), char *name)
{
	Node *mynode = NULL;
	int numb_nodes = 0; /* need to track if we walked through any nodes */

	if ((mylist == NULL) || (mylist->list == NULL)) {
		return (-1);
	}

	/* Skip empty head of linked list */
	mynode = mylist->list->next;

	/* Walk the linked list */
	while ((mynode != NULL) && (mynode != mylist->list)) {
		if (func(mynode, name)) {
			++numb_nodes;
		}
		mynode = mynode->next;
	}
	return (numb_nodes);
}
