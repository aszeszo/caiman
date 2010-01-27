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
 * Test #7
 */
boolean_t
test7(void)
{
	int		errors = 0;
	err_info_t	*rv1 = NULL;

	/*
	 * Test 7: es_set_err_data_int
	 *
	 * NB:
	 * This test should be extended when es_get_err_data_int_by_type()
	 * is written.
	 */
	printf("\nTest 7: es_set_err_data_int\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	if (rv1 == NULL) {
		printf("test FAILED - could not create err_info\n");
		errors++;
	}

	if (! errors) {
		if (es_set_err_data_int(rv1, ES_DATA_ERR_NUM, 17) != B_TRUE) {
			printf("test FAILED - could not set ES_DATA_ERR_NUM "
			    "to an integer\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_int(rv1, ES_DATA_OP_STR, 44) != B_FALSE) {
			printf("test FAILED - should not allow "
			    "ES_DATA_OP_STR to be an integer\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_int(rv1, ES_DATA_FAILED_AT,
		    101) != B_FALSE) {
			printf("test FAILED - should not allow "
			    "ES_DATA_FAILED_AT to be an integer\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_int(rv1, ES_DATA_FAILED_STR, -3) !=
		    B_FALSE) {
			printf("test FAILED - should not allow "
			    "ES_DATA_FAILED_STR to be an integer\n");
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
