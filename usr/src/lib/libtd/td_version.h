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

#ifndef _TD_VERSION_H
#define	_TD_VERSION_H

#pragma ident	"@(#)td_version.h	1.1	07/08/03 SMI"

/*
 * Module:	td_version.h
 * Group:	libtd
 * Description:	This header contains version comparison definitions
 *    used in td_version.c main module
 */

#ifdef __cplusplus
extern "C" {
#endif

#define	ERR_STR_TOO_LONG	-101

#define	V_NOT_UPGRADEABLE	-2
#define	V_LESS_THAN		-1
#define	V_EQUAL_TO		0
#define	V_GREATER_THAN		1

int	td_prod_vcmp(const char *, const char *);

#ifdef __cplusplus
}
#endif

#endif /* _TD_VERSION_H */
