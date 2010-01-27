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
 * Test #8
 */
boolean_t
test8(void)
{
	int errors = 0;
	err_info_t *rv1 = NULL;

	/*
	 * Test 8: es_set_err_data_str
	 */
	printf("\nTest 8: es_set_err_data_str\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	if (rv1 == NULL) {
		printf("test FAILED - could not create err_info\n");
		errors++;
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_OP_STR,
		    "BigFail") != B_TRUE) {
			printf("test FAILED - could not set ES_DATA_OP_STR "
			    "to a string\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_OP_STR, "") != B_TRUE) {
			printf("test FAILED - could not set ES_DATA_OP_STR "
			    "to an empty string\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_OP_STR, NULL) != B_FALSE) {
			printf("test FAILED - should not allow setting "
			    "ES_DATA_OP_STR to NULL\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_FAILED_AT,
		    "mymod.c, line 101") != B_TRUE) {
			printf("test FAILED - could not set ES_DATA_FAILED_AT "
			    "to a string\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_FAILED_STR,
		    "bad param") != B_TRUE) {
			printf("test FAILED - could not set "
			    "ES_DATA_FAILED_STR to a string\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_ERR_NUM, "1") != B_FALSE) {
			printf("test FAILED - should not allow setting "
			    "ES_DATA_ERR_NUM to a string\n");
			errors++;
		}
	}

	if (! errors) {
		if (es_set_err_data_str(rv1, ES_DATA_ERR_NUM,
		    NULL) != B_FALSE) {
			printf("test FAILED - should not allow setting "
			    "ES_DATA_ERR_NUM to NULL\n");
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
