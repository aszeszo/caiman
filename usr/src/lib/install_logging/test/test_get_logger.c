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
 * Test: get the install logger
 */

boolean_t
test_get_logger(void)
{
	boolean_t	retval = B_FALSE;
	logger_t	*pLogger = NULL;
	char		*loggername = "mylogger";

	printf("Test: test_get_logger\n");
	retval = _init_py();
	if (!retval) {
		printf("Can't load python module\n");
		printf("Test:test_get_logger: Fail\n");
	} else {
		/* Get a Logger */
		pLogger = get_logger(loggername);
		if (pLogger == NULL) {
				printf("test_get_logger: Fail\n");
		} else {
			printf("test_get_logger: Pass\n");
			retval = B_TRUE;
			Py_XDECREF(pLogger);
		}

	}

	return (retval);
}
