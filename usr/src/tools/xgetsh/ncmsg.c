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
#pragma ident	"@(#)ncmsg.c	1.2	06/02/27 SMI"
#endif				/* lint */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <locale.h>
#include "nhash.h"
#include "xgetsh.h"

#define	HASHSIZE	151
#define	BSZ		4

static Cache *msgs_cache = (Cache *) NULL;

int
cmsg(const char *msgid)
{
	Item *itemp;
	int len;

	if (msgs_cache == (Cache *) NULL)
		if (init_cache(&msgs_cache, HASHSIZE, BSZ,
		    (int (*)())NULL, (int (*)())NULL) == -1) {
			(void) fprintf(stderr,
			    gettext("cmsg(): init_cache() failed.\n"));
			exit(1);
		}

	len = strlen(msgid) + 1;

	if ((itemp = lookup_cache(msgs_cache, (void *) msgid, len)) ==
	    Null_Item) {
		if ((itemp = (Item *) malloc(sizeof (*itemp))) == Null_Item) {
			(void) fprintf(stderr,
			    gettext("cmsg(): itemp=malloc(%d)\n"),
			    sizeof (*itemp));
			exit(1);
		}

		if ((itemp->key = (char *) malloc(len)) == NULL) {
			(void) fprintf(stderr,
			    gettext("cmsg(): itemp->key=malloc(%d)\n"),
			    len);
			exit(1);
		}
		(void) memmove(itemp->key, msgid, len);
		itemp->keyl = len;

		itemp->data = NULL;
		itemp->datal = 0;

		if (add_cache(msgs_cache, itemp) == -1)
			(void) fprintf(stderr,
			    gettext("cmsg(): add_cache() failed.\n"));

		return (0);
	} else {
		return (1);
	}
}
