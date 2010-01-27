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
test_get_mod_id(void) {
	err_info_t	*rv1 = NULL;
	err_info_t	*rv2 = NULL;
	err_info_t	*rv3 = NULL;
	err_info_t	*rv4 = NULL;
	err_info_t	*rv5 = NULL;
	err_info_t	*rv6 = NULL;
	char		*retval = NULL;
	int		ret = 0;
	int		errors = 0;
	err_info_list_t *list = NULL;

	printf("Testing get_mod_id(C side)\n\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	rv2 = es_create_err_info("TI", ES_CLEANUP_ERR);
	rv3 = es_create_err_info("TD", ES_CLEANUP_ERR);
	rv4 = es_create_err_info("DC", ES_REPAIRED_ERR);
	rv5 = es_create_err_info("AI", ES_ERR);
	if (rv1 == NULL || rv2 == NULL || rv3 == NULL ||
	    rv4 == NULL || rv5 == NULL) {
		printf("test FAILED at 1\n");
		errors++;
	} else {
		if (!errors) {
			printf("\tes_create_err_info returned [%p]\n", rv2);
			printf("\tDump all errors:\n");
			(void) es__dump_all_errors__();
		}
	}

	if (!errors) {
		printf("\n\nes_get_err_mod_id success case\n");
		retval = es_get_err_mod_id(rv4);
		if (retval == NULL) {
			printf("test FAILED at 2\n");
			printf("retval is %s\n", retval);
			errors++;
		}
	}
	if (!errors) {
		if (strcmp(retval, "DC")) {
			printf("retval did not equal DC\n");
			printf("retval is %s\n", retval);
			errors++;
		} else {
			printf("retval is %s\n", retval);
			printf("test SUCCEEDED\n");
		}
	}

	if (!errors) {
		printf("es_get_err_mod_id failure case\n");
		retval = es_get_err_mod_id(rv6);
		if (retval == NULL) {
			printf("retval is %s\n", retval);
			printf("test SUCCEEDED\n");
		} else {
			printf("retval is %s\n", retval);
			printf("should have been NULL\n");
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
