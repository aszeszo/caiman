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



#ifndef	_SOFT_VERSION_H
#define	_SOFT_VERSION_H


#pragma ident	"@(#)soft_version.h	1.2	07/11/12 SMI"

#include "spmisoft_lib.h"

#define	ERR_STR_TOO_LONG	-101

#define	V_NOT_UPGRADEABLE	-2
#define	V_LESS_THEN		-1
#define	V_EQUAL_TO		0
#define	V_GREATER_THEN		1

int	prod_vcmp(char *, char *);
int	pkg_vcmp(char *, char *);

int	is_patch(Modinfo *);
int	is_patch_of(Modinfo *, Modinfo *);

#endif	/* _SOFT_VERSION_H */
