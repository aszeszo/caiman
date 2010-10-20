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
test_transfer_srclog(void)
{
	boolean_t	retval = B_FALSE;
	boolean_t	handler_ret = B_FALSE;
	const char	*dest_dir = "/var/tmp/install/dest";
	const char	*src_file = "/var/tmp/install/source_log";
	logger_t	*pLogger = NULL;
	nvlist_t	*handler_args;
	nvlist_t	*transfer_args = NULL;

	char            dest_pid_str[256];
        PyObject        *pDest = NULL;
        PyObject        *pArg = NULL;
        PyObject        *pList = NULL;
        const char      *src_log = "source_log";


	printf("Test: test_transfer_srclog\n");
	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		return(retval);	
	}

	/* Add a filehandler */
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
	    (nvlist_add_string(handler_args, FILENAME, src_file) != 0) ||
	    (nvlist_add_string(handler_args, LEVEL, "INFO") != 0)) {
		nvlist_free(handler_args);
		printf("Can't create handler args\n");
		goto cleanup;
	}

	handler_ret = add_handler(pLogger, handler_args, LOGGING_FILE_HDLR);
	nvlist_free(handler_args);
	if (!handler_ret) {
		printf("Can't add handler\n");
		goto cleanup;
	}

	if (nvlist_alloc(&transfer_args, NVATTRS, 0) != 0) {
		printf("Can't allocate space for transfer args\n");
		goto cleanup;
	}

	if (transfer_args == NULL) {
		printf("nvlist_alloc failed.\n");
		goto cleanup;
	}

	/* Create a list of arguments used in transferring logs */
	if (nvlist_add_string(transfer_args, DEST, dest_dir) != 0) {
		printf("problem with destination\n");
		nvlist_free(transfer_args);
		goto cleanup;
	}

	if (nvlist_add_string(transfer_args, SOURCE, src_file) != 0) {
		printf("problem with src\n");
		nvlist_free(transfer_args);
		goto cleanup;
	}

	retval = transfer_log(pLogger, transfer_args);
	nvlist_free(transfer_args);
	if (!retval) {
		printf("test_transfer_log: FAIL\n");
		goto cleanup;
	} else {
		printf("test_transfer_srclog: Pass\n");
	}


        (void)snprintf(dest_pid_str, sizeof (dest_pid_str), "%s/%s",
            dest_dir, src_log);

         pDest = PyString_FromString(dest_pid_str);
        if (pDest == NULL) {
               fprintf(stderr, "Failed to convert the log destination to a Python string");
                goto cleanup;
        }

        pList = PyString_FromString("_log_list");
        pArg = PyObject_GetAttr((PyObject *)pLogger, pList);
        PyObject_CallMethod(pArg, "remove", "O", pDest);


cleanup:
	Py_XDECREF(pLogger);
	return (retval);
}
