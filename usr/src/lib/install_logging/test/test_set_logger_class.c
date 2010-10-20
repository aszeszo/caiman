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
 * Test: set the install logger to the class specified
 */
boolean_t
test_set_logger_class(void)
{
	boolean_t	retval = B_FALSE;
	char		*logger_class = "InstallLogger";
	PyObject	*check_logger = NULL;
	PyObject	*check_moduleOne = NULL;
	PyObject	*check_moduleTwo = NULL;

	printf("Test: test_set_install_logger_class\n");

	retval = set_logger_class(logger_class);
	if (!retval) {
		printf("No logger class set\n");
		printf("test_set_install_logger_class: Fail\n");
	} else {
		printf("test_set_install_logger_class: Pass\n");
	}

	return (retval);
}
