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

boolean_t set_err_data(err_info_t *, int, char *, char *, char *, char *);

boolean_t
test_with_args(
	char *modid,
	int err_type,
	int err_num,
	char *opt_str,
	char *fixit_str,
	char *failed_at_str,
	char *failed_str)
{
	boolean_t ret = B_TRUE;
	err_info_t *rv1 = NULL;
	err_info_t *rv2 = NULL;
	err_info_list_t *list = NULL;
	int err_int;

	printf("\n\nTesting interfaces with passed in arguments\n");

	rv1 = es_create_err_info(modid, err_type);
	if (rv1 == NULL) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	ret = set_err_data(rv1, err_num, opt_str, fixit_str,
	    failed_at_str, failed_str);
	if (ret != B_TRUE) {
		printf("set_err_data failed\n");
		goto cleanup;
	}

	ret = es_get_err_data_int_by_type(rv1, ES_DATA_ERR_NUM,
	    &err_int);
	if (ret == B_TRUE && err_int == err_num) {
		printf("value of err_int is %d\n", err_int);
		printf("test SUCCEEDED\n");
	} else {
		printf("value of err_int is %d\n", err_int);
		printf("test failed\n");
		goto cleanup;
	}

	list = es_get_all_errors();
	if (list == NULL) {
		ret = B_FALSE;
		printf("Test FAILED\n");
	} else {
		while (list != NULL) {
			int ret_num = 0;
			char *temp_str = NULL;
			char tmp_str[1024];
			if (es_get_err_type(list->ei_err_info) !=
			    err_type) {
				printf("es_get_err_type, Test Failed\n");
				ret = B_FALSE;
				break;
			}
			if (strcmp(es_get_err_mod_id(list->ei_err_info),
			    modid) != 0) {
				printf("es_get_err_mod_id, "
				    "Test Failed\n");
				ret = B_FALSE;
				break;
			}
			ret = es_get_err_data_int_by_type(
			    list->ei_err_info, ES_DATA_ERR_NUM,
			    &ret_num);
			if (ret != B_TRUE || ret_num != err_num) {
				printf("ES_DATA_ERR_NUM,Test FAILED\n");
				break;
			}

			ret = es_get_err_data_str_by_type(
			    list->ei_err_info, ES_DATA_OP_STR,
			    &temp_str);
			if (ret != B_TRUE || strcmp(temp_str, opt_str) != 0) {
				printf("ES_DATA_OP_STR,Test FAILED\n");
				free(temp_str);
				break;
			}
			free(temp_str);

			ret = es_get_err_data_str_by_type(
			    list->ei_err_info, ES_DATA_FIXIT_STR,
			    &temp_str);
			if (ret != B_TRUE ||
			    strcmp(temp_str, fixit_str) != 0) {
				printf("ES_DATA_FIXIT_STR,Test FAILED\n");
				free(temp_str);
				break;
			}
			free(temp_str);

			ret = es_get_err_data_str_by_type(
			    list->ei_err_info, ES_DATA_FAILED_AT,
			    &temp_str);
			sprintf(tmp_str, "The failed at string is %s",
			    failed_at_str);
			if (ret != B_TRUE ||
			    strcmp(temp_str, tmp_str) != 0) {
				printf("ES_DATA_FAILED_AT,Test FAILED\n");
				free(temp_str);
				break;
			}
			free(temp_str);

			ret = es_get_err_data_str_by_type(
			    list->ei_err_info, ES_DATA_FAILED_STR,
			    &temp_str);
			if (ret != B_TRUE ||
			    strcmp(temp_str, failed_str) != 0) {
				printf("ES_DATA_FAILED_STR, Test FAILED\n");
				free(temp_str);
				break;
			}
			free(temp_str);
			list = list->ei_next;
		}

		if (ret == B_TRUE) {
			printf("Test PASSED\n");
		}
	}

cleanup:
	es_free_errors();

	return (ret);
}

boolean_t
set_err_data(
	err_info_t *rv1,
	int err_num,
	char *opt_str,
	char *fixit_str,
	char *failed_at_str,
	char *failed_str)
{
	if (rv1 == NULL) {
		printf("test FAILED\n");
		return (B_FALSE);
	}
	if (es_set_err_data_int(rv1, ES_DATA_ERR_NUM, err_num) != B_TRUE) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	if (es_set_err_data_str(rv1, ES_DATA_OP_STR, opt_str) != B_TRUE) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	if (es_set_err_data_str(rv1, ES_DATA_FIXIT_STR, fixit_str) != B_TRUE) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	if (es_set_err_data_str(rv1, ES_DATA_FAILED_AT,
	    "The failed at string is %s", failed_at_str) != B_TRUE) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	if (es_set_err_data_str(rv1, ES_DATA_FAILED_STR,
	    failed_str) != B_TRUE) {
		printf("test FAILED\n");
		return (B_FALSE);
	}

	return (B_TRUE);
}
