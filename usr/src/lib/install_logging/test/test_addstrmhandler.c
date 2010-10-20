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
test_addstrmhandler()
{
	boolean_t	retval = B_FALSE;
	const char	*stream = "sys.stdout";
	char		*level = "INFO";
	nvlist_t	*handler_args = NULL;
	logger_t	*pLogger = NULL;

	printf("Test: test_addstrmhandler\n");
	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		return (retval);
	}

	if (nvlist_alloc(&handler_args, NVATTRS, 0) != 0) {
		printf("Can't allocate space for handler args\n");
		goto cleanup;
	}

	if (handler_args == NULL) {
		printf("nvlist_alloc failed.\n");
		goto cleanup;
	}

	/* Create a list of arguments for a FileHandler */
	if ((nvlist_add_string(handler_args, HANDLER, STREAM_HANDLER) != 0) ||
	    (nvlist_add_string(handler_args, STRM, stream) != 0) ||
	    (nvlist_add_string(handler_args, LEVEL, "INFO") != 0)) {
		nvlist_free(handler_args);
		printf("Can't create handler args\n");
		goto cleanup;
	}

	retval = add_handler(pLogger, handler_args, LOGGING_STREAM_HDLR);
	nvlist_free(handler_args);
	if (!retval) {
		printf("test_addstrmhandler: Fail\n");
	} else {
		printf("test_addstrmhandler: Pass\n");
	}

cleanup:
	Py_XDECREF(pLogger);
	return (retval);
}
