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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <stdio.h>
#include <string.h>

#include "../liberrsvc.h"

/*
 * Test 1: es_create_err_info
 */
boolean_t
test1(void)
{
	boolean_t	retval = B_FALSE;
	err_info_t	*rv1 = NULL;
	err_info_t	*rv2 = NULL;

	printf("Test 1: es_create_err_info\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	if (rv1 == NULL) {
		printf("test FAILED\n");
	} else {
		/* printf("\tes_create_err_info returned [%p]\n", rv1); */

		rv2 = es_create_err_info("TI", ES_CLEANUP_ERR);
		if (rv2 == NULL) {
			printf("test FAILED\n");
		} else {
			printf("test PASSED\n");
			retval = B_TRUE;
		}
	}

	es_free_errors();

	return (retval);
}
