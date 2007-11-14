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


#ifndef _SPMIAPP_LIB_H
#define	_SPMIAPP_LIB_H

#pragma ident	"@(#)spmiapp_lib.h	1.2	07/10/09 SMI"


/*
 * Module:	spmiapp_lib.h
 * Group:	libspmiapp
 * Description:
 */


#include "spmiapp_api.h"

#ifdef __cplusplus
extern "C" {
#endif

/* app_profile.c */
int		configure_dfltmnts(Profile *);
int		configure_sdisk(Profile *);

#ifdef __cplusplus
}
#endif

#endif	/* _SPMIAPP_LIB_H */
