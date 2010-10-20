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
 * Test: set a logging level for a logger.
 */

boolean_t
test_set_log_level(void)
{
	boolean_t	retval = B_FALSE;
	char		*level = "INFO";
	logger_t	*pLogger = NULL;

	printf("Test: test_set_log_level\n");
	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		printf("Cannot proceed with test\n");
		return (retval);
	}

	retval = set_log_level(pLogger, level);
	if (!retval) {
		printf("test_set_log_level: Fail\n");
	} else {
		printf("test_set_log_level: Pass\n");
		retval = B_TRUE;
	}

	Py_XDECREF(pLogger);
	return (retval);
}
