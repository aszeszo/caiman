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
get_err_data_str_by_type(void)
{
	boolean_t		retval = B_FALSE;
	err_info_t		*rv1 = NULL;
	err_info_t		*rv2 = NULL;
	err_info_list_t		*list = NULL;
	boolean_t		ret;
	char			*err_str = NULL;
	char			*str = "Hello";
	int			errors = 0;

	printf("\n\nTesting es_get_err_data_str_by_type\n");

	rv1 = es_create_err_info("TD", ES_ERR);
	if (rv1 == NULL) {
		printf("test FAILED\n");
		errors++;
	}

	if (!errors) {
		if (rv1 != NULL) {
			printf("\tAdding data string 'Hello'\n");

			if (es_set_err_data_str(rv1, ES_DATA_OP_STR,
			    "Hello") != B_TRUE) {
				printf("test FAILED\n");
				errors++;
			} else {
				printf("\tAdding vararg data string:\n");
				printf("\t\t\"Line [%%d] Error [%%s]\", 100, "
				    "\"Bad partition\"\n");

				if (es_set_err_data_str(rv1, ES_DATA_FIXIT_STR,
				    "Line [%d] Error [%s]", 100,
				    "Bad partition") != B_TRUE) {
					printf("test FAILED\n");
					errors++;
				} else {
					printf("test PASSED\n");
				}
			}
		}
	}

	if (!errors) {
		ret = es_get_err_data_str_by_type(rv1, ES_DATA_OP_STR,
		    &err_str);
		if (ret == B_TRUE && strcmp(err_str, str) == 0) {
			printf("value of err_str is %s\n", err_str);
			printf("test SUCCEEDED\n");
			free(err_str);
		} else {
			printf("failed - value of err_str is %s\n", err_str);
			printf("test failed\n");
			errors++;
			free(err_str);
		}

	}

	es_free_errors();

	if (errors)
		return (B_FALSE);

	return (B_TRUE);
}
