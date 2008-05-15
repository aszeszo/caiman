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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _TI_BEM_H
#define	_TI_BEM_H

/*
 * Module:	ti_bem.h
 * Group:
 * Description:	This module contains the Target Instantiation BE module
 *		data structures, constants, and function prototypes.
 */

#include "ti_api.h"
#include "ls_api.h"

#ifdef __cplusplus
extern "C" {
#endif

#define	IBEM_DEBUG	ibem_debug_print

/* type definitions */


/* return codes */

typedef enum ibem_errno_t {
	IBEM_E_SUCCESS,
	IBEM_E_ATTR_INVALID, 		/* invalid set of attributes passed */
	IBEM_E_RPOOL_NOT_EXIST,		/* root pool does not exist */
	IBEM_E_BE_CREATE_FAILED,	/* be_init() failed */
	IBEM_E_BE_MOUNT_FAILED		/* be_mount() failed */
} ibem_errno_t;

/* constants */

#define	IBEM_MAXCMDLEN		1024

/* macros */

/* global variables */

/* function prototypes */
ibem_errno_t ibem_create_be(nvlist_t *attrs);

/* Makes TI BE module work in dry run mode */

void ibem_dryrun_mode(void);

#ifdef __cplusplus
}
#endif

#endif /* _TI_BEM_H */
