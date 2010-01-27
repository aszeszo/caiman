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
 * Test get_errors_by_type
 */
boolean_t
test_get_errors_by_type(void) {
	err_info_t *rv1 = NULL;
	err_info_t *rv2 = NULL;
	err_info_t *rv3 = NULL;
	err_info_t *rv4 = NULL;
	err_info_t *rv5 = NULL;
	int errors = 0;
	err_info_list_t *list = NULL;
	boolean_t  errp;


	printf("\n\nTesting get_errors_by_type(C side)\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	rv2 = es_create_err_info("TI", ES_CLEANUP_ERR);
	rv3 = es_create_err_info("TD", ES_CLEANUP_ERR);
	rv4 = es_create_err_info("DC", ES_REPAIRED_ERR);
	rv5 = es_create_err_info("AI", ES_ERR);
	if (rv1 == NULL || rv2 == NULL || rv3 == NULL ||
	    rv4 == NULL || rv5 == NULL) {
		errors++;
	}

	if (!errors) {
		list = es_get_errors_by_type(ES_ERR, &errp);
		if (list == NULL || errp == 1) {
			errors++;
		} else {
			int count = 0;
			err_info_list_t *item = list;
			while (item != NULL) {
				count++;
				item = item->ei_next;
			}
			if (count != 2) {
				errors++;
			}
		}
	}

	if (!errors) {
		errp = 0;

		list = es_get_errors_by_type(ES_REPAIRED_ERR, &errp);
		if (list == NULL || errp == 1) {
			errors++;
		} else {
			int count = 0;
			err_info_list_t *item = list;
			while (item != NULL) {
				count++;
				item = item->ei_next;
			}
			if (count != 1) {
				errors++;
			}
		}
	}

	if (!errors) {
		errp = 0;

		list = es_get_errors_by_type(65, &errp);
		if (list != NULL && errp != 0) {
			errors++;
		}
	}

	es_free_errors();

	if (errors) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	printf("test PASSED\n");
	return (B_TRUE);
}
