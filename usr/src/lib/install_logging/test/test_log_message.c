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
 * Test: Log a message to the logger.
 */

boolean_t
test_log_message(void)
{
	boolean_t	retval = B_FALSE;
	logger_t	*pLogger = NULL;
	char		*level = "DEBUG";

	printf("Test: test_log_message\n");

	pLogger = (logger_t *)test_setup();
printf("after getting pLogger\n");
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		printf("Cannot proceed with test\n");
		return (retval);
	}

	retval = set_log_level(pLogger, level);
printf("after setting level\n");
	if (!retval) {
		printf("set_log_level: Fail\n");
		goto cleanup;
	}

	retval = log_message(pLogger, DEBUG, "Debug message from test");
	if (!retval) {
		printf("test_log_message: Fail\n");
		goto cleanup;
	}

	retval = log_message(pLogger, INFO, "Info  message from test");
	if (!retval) {
		printf("test_log_message: Fail\n");
		goto cleanup;
	}

	retval = log_message(pLogger, WARNING, "Warning  message from test");
	if (!retval) {
		printf("test_log_message: Fail\n");
		goto cleanup;
	}

	retval = log_message(pLogger, ERROR, "Error message from test");
	if (!retval) {
		printf("test_log_message: Fail\n");
		goto cleanup;
	}

	retval = log_message(pLogger, CRITICAL, "Critical message from test");
	if (!retval) {
		printf("test_log_message: Fail\n");
		goto cleanup;
	}

	retval = B_TRUE;
	printf("test_log_message: Pass\n");

cleanup:
	Py_XDECREF(pLogger);
	return (retval);
}
