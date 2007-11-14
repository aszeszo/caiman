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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */



/*
 * Module:	spmicommon_lib.h
 * Group:	libspmicommon
 * Description:	This module contains the libspmicommon internal data structures,
 *		constants, and function prototypes.
 */

#ifndef	_SPMICOMMON_LIB_H
#define	_SPMICOMMON_LIB_H

#pragma ident	"@(#)spmicommon_lib.h	1.5	07/11/12 SMI"


#include "spmicommon_api.h"
#include <ctype.h>

/* constants */

#define	TMPLOGFILE	"/tmp/install_log"

/* macros */

#define	must_be(s, c)  	if (*s++ != c) return (0)
#define	skip_digits(s)	if (!isdigit(*(s))) return (0); \
			while (isdigit(*(s))) (s)++;

/* function prototypes */

#ifdef __cplusplus
extern "C" {
#endif

/*
 *  The following functions can be used by other spmi libs, but not
 *  by applications.
 */

/* common_scriptwrite.c */
void		scriptwrite(FILE *, uint, char **, ...);

/* common_util.c */
int		SystemGetMemsize(void);

#ifdef __cplusplus
}
#endif

#endif	/* _SPMICOMMON_LIB_H */
