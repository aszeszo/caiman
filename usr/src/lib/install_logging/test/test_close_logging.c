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
 * Test: Test close_logging.
 */

boolean_t
test_close_logging(void)
{
	boolean_t	retval = B_FALSE;
	boolean_t	handler_ret = B_FALSE;
	logger_t	*pLogger = NULL;
	const char	*filename = "/var/tmp/install/closetestfile";
	const char	*default_log = "/var/tmp/install/default_log";
	const char	*source_log = "/var/tmp/install/source_log";
	const char	*handler_log = "/var/tmp/install/addhandlertest";
	log_file_list_t *test_list = NULL;
	nvlist_t	*handler_args = NULL;
	int		pid;
	char		log_pid_str[256];
	int		count = 0;

	printf("Test: test_close_logging\n");

	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		return (retval);
	}

	if ((pid = getpid()) < 0) {
		printf("Unable to get pid\n");
		goto cleanup;
	}

	(void) snprintf(log_pid_str, sizeof (log_pid_str), "%s.%d",
	    default_log, pid);

	if (nvlist_alloc(&handler_args, NVATTRS, 0) != 0) {
		printf("Can't allocate space for handler args\n");
		goto cleanup;
	}

	if (handler_args == NULL) {
		printf("nvlist_alloc failed.\n");
		goto cleanup;
	}

	/* Create a list of arguments for a FileHandler */
	if ((nvlist_add_string(handler_args, HANDLER, FILE_HANDLER) != 0) ||
	    (nvlist_add_string(handler_args, FILENAME, filename) != 0) ||
	    (nvlist_add_string(handler_args, LEVEL, "INFO") != 0)) {
		nvlist_free(handler_args);
		printf("Can't create handler args\n");
		goto cleanup;
	}

	handler_ret = add_handler(pLogger, handler_args, LOGGING_FILE_HDLR);
	nvlist_free(handler_args);
	if (!handler_ret) {
		printf("Failed to add handler\n");
		goto cleanup;
	}

	test_list = close_logging(pLogger);
	if (test_list == NULL) {
		printf("close_logging did not return a list: FAIL\n");
		if (test_list)
			free(test_list);
		goto cleanup;
	}

	while (count < 4) {
		if ((strcmp(test_list->logfile, log_pid_str) == 0) ||
		    (strcmp(test_list->logfile, filename) == 0) ||
		    (strcmp(test_list->logfile, handler_log) == 0) ||
		    (strcmp(test_list->logfile, source_log) == 0)) {
			retval = B_TRUE;
			count++;
			test_list = test_list->logfile_next;
		} else {
			printf("close_logging failed\n");
			retval = B_FALSE;
			goto cleanup;
		}
	}

cleanup:
	if (test_list)
		free(test_list);
	Py_XDECREF(pLogger);
	return (retval);
}
