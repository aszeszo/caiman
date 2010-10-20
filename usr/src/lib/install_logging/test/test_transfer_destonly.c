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
test_transfer_destonly(void)
{
	boolean_t	retval = B_FALSE;
	const char	*dest_dir = "/var/tmp/install/dest";
	logger_t	*pLogger = NULL;
	nvlist_t	*transfer_args = NULL;


	char            dest_pid_str[256];
	PyObject	*pDest = NULL;
	PyObject	*pArg = NULL;
	PyObject	*pList = NULL;
	const char      *default_log = "default_log";
	int             pid;

	printf("Test: test_transfer_destonly\n");
	pLogger = (logger_t *)test_setup();
	if (pLogger == NULL) {
		printf("Failed to get a Logger\n");
		return (retval);
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
		nvlist_free(transfer_args);
		printf("problem with destination\n");
		goto cleanup;
	}

	retval = transfer_log(pLogger, transfer_args);
	if (!retval) {
		printf("test_transfer_destonly: FAIL\n");
	} else {
		printf("test_transfer_destonly: Pass\n");
	}
	nvlist_free(transfer_args);


	if ((pid = getpid()) < 0) {
                printf("Unable to get pid\n");
                goto cleanup;
        }
	
	(void)snprintf(dest_pid_str, sizeof (dest_pid_str), "%s/%s.%d",
            dest_dir, default_log, pid);

	 pDest = PyString_FromString(dest_pid_str);
        if (pDest == NULL) {
               fprintf(stderr, "Failed to convert the log destination to a Python string");
                goto cleanup;
        }

	pList = PyString_FromString("_log_list");
        pArg = PyObject_GetAttr((PyObject *)pLogger, pList);
	PyObject_CallMethod(pArg, "remove", "O", pDest);

cleanup:
	Py_XDECREF(pDest);
	Py_XDECREF(pArg);
	Py_XDECREF(pList);
	Py_XDECREF(pLogger);
	return (retval);
}
