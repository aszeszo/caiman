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


#ifndef	_TRANSFERMOD_H
#define	_TRANSFERMOD_H

#pragma ident	"@(#)transfermod.h	1.3	07/11/12 SMI"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Dummy definition for TM - To be removed
 */
#define	TM_ATTR_TARGET_DIRECTORY	"mountpoint"
#define	TM_SUCCESS	0

int TM_perform_transfer(nvlist_t *targs, void(*progress)(int));
void TM_abort_transfer();
void TM_enable_debug();

#ifdef __cplusplus
}
#endif

#endif	/* _TRANSFERMOD_H */

