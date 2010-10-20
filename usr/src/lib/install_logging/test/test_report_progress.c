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
 *
 * Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
 */

#include "../logger.h"

/*
 * Test: Add a handler to a progress handler.
 */

boolean_t
test_report_progress(void)
{
	boolean_t	retval = B_FALSE;
	boolean_t	handler_ret = B_FALSE;
	char		*loggername = "mylogger";
	const char	*host = "localhost";
	int		port = 2333;
	logger_t	*pLogger = NULL;
	nvlist_t	*handler_args = NULL;


	printf("Test: test_report_progress\n");
	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		return (retval);
	}

	if (nvlist_alloc(&handler_args, NVATTRS, 0) != 0) {
		printf("Cannot allocate space for handler args\n");
		goto cleanup;
	}

	if (handler_args == NULL) {
		printf("nvlist_alloc failed.\n");
		goto cleanup;
	}

	/* Create a list of arguments for a ProgressHandler */
	if ((nvlist_add_string(handler_args, HANDLER, PROGRESS_HANDLER) != 0) ||
	    (nvlist_add_string(handler_args, HOST, host) != 0) ||
	    (nvlist_add_int32(handler_args, PORT, port) != 0)) {
		nvlist_free(handler_args);
		printf("Cannot create handler args\n");
		goto cleanup;
	}

	handler_ret = add_handler(pLogger, handler_args, LOGGING_PROGRESS_HDLR);
	nvlist_free(handler_args);
	if (!handler_ret) {
		printf("Adding progress handler failed cannot continue\n");
		goto cleanup;
	} else {

		retval = report_progress(pLogger, 0, "Test: 0 done");
		if (!retval) {
			printf("test_report_progress: Fail 0\n");
			goto cleanup;
		}

		retval = report_progress(pLogger, 20, "Test 20 done");
		if (!retval) {
			printf("test_report_progress: Fail 20\n");
			goto cleanup;
		}

		retval = report_progress(pLogger, 40, "Test: 40 done");
		if (!retval) {
			printf("test_report_progress: Fail 40\n");
			goto cleanup;
		}

		retval = report_progress(pLogger, 60, "Test: 60 done");
		if (!retval) {
			printf("test_report_progress: Fail 60\n");
			goto cleanup;
		}

		retval = report_progress(pLogger, 80, "Test:80 done");
		if (!retval) {
			printf("test_report_progress: Fail 80\n");
			goto cleanup;
		}

		retval = report_progress(pLogger, 100, "Test:100 done");
		if (!retval) {
			printf("test_log_message: Fail 100\n");
			goto cleanup;
		}
	}
	printf("test_report_progress: Pass\n");

cleanup:
	Py_XDECREF(pLogger);
	return (retval);
}
