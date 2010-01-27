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

boolean_t
get_err_data_int_by_type(void)
{
	err_info_t	*rv1 = NULL;
	err_info_t	*rv2 = NULL;
	err_info_list_t *list = NULL;
	boolean_t	ret;
	int		err_int;
	int		errors = 0;

	printf("\n\nTesting get_err_data_int_by_type\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	if (rv1 == NULL) {
		printf("test FAILED at 1\n");
		errors++;
	}

	if (!errors) {
		printf("\tAdding integer data '17'\n");

		if (es_set_err_data_int(rv1, ES_DATA_ERR_NUM, 17) != B_TRUE) {
			printf("test FAILED at 2\n");
			errors++;
		} else {
			printf("test PASSED\n");
		}
	}

	if (!errors) {
		printf("Testing es_get_err_data_int_by_type success case\n");
		ret = es_get_err_data_int_by_type(rv1, ES_DATA_ERR_NUM,
		    &err_int);
		if (ret == B_TRUE && err_int == 17) {
			printf("value of err_int is %d\n", err_int);
			printf("test SUCCEEDED\n");
		} else {
			printf("test failed at 3\n");
			errors++;
		}
	}

	if (!errors) {
		printf("Testing es_get_err_data_int_by_type failure case\n");
		ret = es_get_err_data_int_by_type(rv1, 50, &err_int);
		if (ret == B_FALSE) {
			printf("Test failed to find invalid type\n");
			printf("test SUCCEEDED\n");
		} else {
			printf("Test should fail to find invalid type\n");
			printf("test failed at 3\n");
			errors++;
		}
	}

	es_free_errors();

	if (errors) {
		return (B_FALSE);
	}

	printf("test PASSED\n");
	return (B_TRUE);
}
