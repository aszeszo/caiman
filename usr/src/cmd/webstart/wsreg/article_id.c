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
#include <stdio.h>
#include <ctype.h>
#include <time.h>
#include <math.h>
#include <strings.h>
#include "article_id.h"
#include "wsreg.h"

static Article_id *article_id = NULL;

/*
 * This private method generates a 9-digit random number.
 */
static unsigned long
generate_large_random_number()
{
	unsigned long id = (unsigned long)rand();

	/*
	 * On some systems, RAND_MAX is not sufficient to
	 * generate a 9 digit random number.  We will use
	 * multiplication of several random numbers to
	 * accomplish this.
	 * The amount of random numbers multiplied
	 * together to get a 9-digit random number is:
	 *
	 * log10(10^8)/log10(RAND_MAX)
	 * which reduces to
	 * 8/log10(RAND_MAX);
	 */
	int count = (int)(8/(int)log10((double)RAND_MAX));
	int index;

	for (index = 1; index < count; index++) {
		int next_number = rand();

		/*
		 * Only one chance to get 0. Do not allow subsequent
		 * calls to rand() to result in a 0 id.
		 */
		if (next_number == 0) {
			next_number += 1;
		}
		id *= next_number;
	}
	return (id);
}

/*
 * Generates an article id.  The resulting string
 * must be freed by the caller.
 */
static char *
artid_create_id(void)
{
	char *result = NULL;
	unsigned long id = generate_large_random_number();

	/*
	 * Now form the id according to the old rules.  See
	 * Article.java:chooseID().
	 */
	id = (id % 900000000) + 100000000; /* 9 digits; avoid leading zeros */
	result = (char *)wsreg_malloc(sizeof (char) * 10);
	sprintf(result, "%ld", id);
	return (result);
}

/*
 * Returns true if the specified id is legal; false otherwise.
 * A prodreg 2.0 id is legal if it is a 9-digit decimal number
 * that does not begin with zero.
 */
static Boolean
artid_is_legal_id(const char *id)
{
	int index;
	if (strlen(id) != 9) {
		return (FALSE);
	}
	if (id[0] == '0') {
		return (FALSE);
	}
	for (index = 0; index < 9; index++) {
		if (!isdigit((int)id[index])) {
			return (FALSE);
		}
	}
	return (TRUE);
}

/*
 * Returns the Article_id object.  If the Article_id has not been
 * created, this function will create it.  There is no need to
 * free the Article_id object.  Only one will ever be created.
 */
Article_id *
_wsreg_artid_initialize()
{
	Article_id *aid = article_id;
	if (aid == NULL) {
		aid = (Article_id *)wsreg_malloc(sizeof (Article_id));
		/*
		 * Initialize the method set.
		 */
		aid->create_id = artid_create_id;
		aid->is_legal_id = artid_is_legal_id;

		/*
		 * Use this opportunity to initialize
		 * the random number generator (this
		 * should only be done once).
		 */
		srand(time(NULL));

		article_id = aid;
	}
	return (aid);
}
