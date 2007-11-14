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
 * Copyright 1993 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef lint
#pragma ident	"@(#)nhash.c	1.3	06/02/27 SMI"
#endif				/* lint */

#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <locale.h>
#include "nhash.h"

#ifndef _KERNEL
#define	bcopy(a, b, c)	(void) memmove(b, a, c)
#define	bcmp		memcmp
#define	bzero(a, c)	memset(a, '\0', c)
#else	/* _KERNEL */
#define	malloc		bkmem_alloc
#endif	/* _KERNEL */

#define	VERIFY_HASH_REALLOC

static int
BCMP(void *str1, void *str2, int len)
{
	return (bcmp((char *)str1, (char *)str2, len));
}

static int
HASH(void *datap, int datalen, int hsz)
{
	register char *cp;
	register int	hv = 0;

	for (cp = (char *)datap; cp != ((char *)datap + datalen); hv += *cp++)
		;
	return (hv % hsz);
}

int
init_cache(Cache **cp, int hsz, int bsz,
	    int (*hfunc)(void *, int, int), int (*cfunc)(void *, void *, int))
{
	int i;

	if ((*cp = (Cache *) malloc(sizeof (**cp))) == NULL) {
		(void) fprintf(stderr, gettext("malloc(Cache **cp)"));
		return (-1);
	}
	if (((*cp)->bp =
	    (Bucket *) malloc(sizeof (*(*cp)->bp) * hsz)) == NULL) {
		(void) fprintf(stderr, gettext("malloc(Bucket cp->bp)"));
		return (-1);
	}
	(*cp)->hsz = hsz;
	(*cp)->bsz = bsz;
	for (i = 0; i < (*cp)->hsz; i++) {
		(*cp)->bp[i].nent = 0;
		(*cp)->bp[i].nalloc = 0;
		(*cp)->bp[i].itempp = NULL;
	}
	if (hfunc != (int (*)()) NULL)
		(*cp)->hfunc = hfunc;
	else
		(*cp)->hfunc = HASH;

	if (cfunc != (int (*)()) NULL)
		(*cp)->cfunc = cfunc;
	else
		(*cp)->cfunc = BCMP;
	return (0);
}

int
add_cache(Cache *cp, Item *itemp)
{
	Bucket *bp;
	Item **titempp;

	if (cp == NULL) {
		(void) fprintf(stderr,
		    gettext("add_cache(): init_cache() not called.\n"));
		return (-1);
	}

	bp = &cp->bp[(*cp->hfunc)(itemp->key, itemp->keyl, cp->hsz)];
	if (bp->nent >= bp->nalloc) {
		if (bp->nalloc == 0) {
			bp->itempp =
			    (Item **) malloc(sizeof (*bp->itempp) * cp->bsz);
		} else {
#ifdef	VERIFY_HASH_REALLOC
			(void) fprintf(stderr,
			    gettext("realloc(%d) bucket=%d\n"),
			    bp->nalloc + cp->bsz,
			    (*cp->hfunc)(itemp->key, itemp->keyl, cp->hsz));
#endif	/* VERIFY_HASH_REALLOC */
			if ((titempp =
			    (Item **) malloc(sizeof (*bp->itempp) *
			    (bp->nalloc + cp->bsz))) != NULL) {
				bcopy((char *)bp->itempp, (char *)titempp,
				    (sizeof (*bp->itempp) * bp->nalloc));
#ifdef _KERNEL
				bkmem_free(bp->itempp,
					(sizeof (*bp->itempp) * bp->nalloc));
#else	/* !_KERNEL */
				free(bp->itempp);
#endif	/* _KERNEL */
				bp->itempp = titempp;
			} else
				bp->itempp = NULL;
		}
		if (bp->itempp == NULL) {
			(void) fprintf(stderr,
			    gettext("add_cache(): out of memory\n"));
			return (-1);
		}
		bp->nalloc += cp->bsz;
	}
	bp->itempp[bp->nent] = itemp;
	bp->nent++;
	return (0);
}

Item *
lookup_cache(Cache *cp, void *datap, int datalen)
{
	int i;
	Bucket *bp;

	if (cp == NULL) {
	    (void) fprintf(stderr,
		gettext("lookup_cache(): init_cache() not called.\n"));
	    return (Null_Item);
	}

	bp = &cp->bp[(*cp->hfunc)(datap, datalen, cp->hsz)];
	for (i = 0; i < bp->nent; i++)
		if (!(*cp->cfunc)((void *)bp->itempp[i]->key, datap, datalen))
			return (bp->itempp[i]);
	return (Null_Item);
}
