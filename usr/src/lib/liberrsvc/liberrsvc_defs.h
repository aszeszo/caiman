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
 */

/*
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _LIBERRSVC_DEFS_H
#define	_LIBERRSVC_DEFS_H

/*
 * Common defines
 */

/*
 * common datatypes
 */
enum {
	ES_DATA_ERR_NUM,
				/*
				 * this is an error number such
				 * as errno. This is not translated
				 * to a string
				 */
	ES_DATA_OP_STR,
				/*
				 * String describing operations such
				 * as lib operations
				 */
	ES_DATA_FIXIT_STR,	/* fixit strings or URL's */
	ES_DATA_FAILED_AT,	/* Strings describing function calls */
	ES_DATA_FAILED_STR	/* error string returned from failure */
} err_elem_type;

enum {
	ES_ERR,		/* information for the actual failure */
	ES_CLEANUP_ERR,	/* information on any needed cleanup */
	ES_REPAIRED_ERR	/* list of errors fixed internally */
} err_type;

#endif	/* _LIBERRSVC_DEFS_H */
