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
 * Test: Add a handler to a logger.
 */

boolean_t
test_addhandler_fail(void)
{
	boolean_t	retval = B_FALSE;
	const char      *filename = "/var/tmp/install/addhandlerfailtest";
        char            *level = "INFO";
	logger_t	*pLogger = NULL;
	nvlist_t        *handler_args = NULL;
	

	printf("Test: test_addhandler\n");
	pLogger = (logger_t *)test_setup();
        if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		printf("Cannot proceed with test\n");
		retval = B_FALSE;
		return (retval);
        }

	if (nvlist_alloc(&handler_args, NVATTRS, 0) != 0) {
		printf("Can't allocate space for handler args\n");
		printf("Cannot proceed with test.\n");
                return (retval);
        }

	if (handler_args == NULL) {
		printf("nvlist_alloc failed.\n");
		printf("Cannot proceed with test.\n");
		return (B_FALSE);
	}

        retval = add_handler(pLogger, handler_args, LOGGING_FILE_HDLR);
        nvlist_free(handler_args);
        if (retval) {
		 printf("test_addhandler_fail: Fail\n");
	} else {
		printf("test_addhandler_fail: Pass\n");
		retval = B_TRUE;
	}
	return (retval);
}
