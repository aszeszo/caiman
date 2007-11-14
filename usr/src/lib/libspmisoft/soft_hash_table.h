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

#pragma ident	"@(#)soft_hash_table.h	1.1	07/11/08 SMI"

#ifndef	_SPMISOFT_HASH_TABLE_H
#define	_SPMISOFT_HASH_TABLE_H

#ifdef __cplusplus
extern "C" {
#endif



#define	HASHTABLESIZE 499

typedef struct node
{
	struct node *next;
	struct node *prev;
	struct node *next_in_hashchain;
	struct node *prev_in_hashchain;
	char *key; 				/* used for package name */
	void *data;				/* used for Modinfo */
	void (*delproc)();
} Node;


/*
 * List contains a chained hash table and a linked list of all elements in the
 * hash table.
 */
typedef struct
{
	struct node *list;
	struct node *hashtable[HASHTABLESIZE];
}List;

extern List *getlist();
extern Node *getnode();
extern int addnode(List *, Node *);
extern Node *findnode(List *,  char *);
extern void delnode(Node *);
extern void dellist(List **);
extern void sortlist(List *, int func(Node *, Node *));
extern int walklist(List *, int func(Node *, caddr_t), char *);

#ifdef __cplusplus
}
#endif

#endif /* _SPMISOFT_HASH_TABLE_H */
