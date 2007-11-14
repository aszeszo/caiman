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

#ifndef _TEST_H
#define	_TEST_H

#pragma ident	"@(#)test.h	1.2	07/10/04 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#define	DISK_INFO		0x01
#define	PART_INFO		0x02
#define	SLICE_INFO		0x04
#define	UPGRADE_TARGET_INFO	0x08
#define	DO_INSTALL		0x10
#define	DO_UPGRADE		0x20
#define	DO_SLIM_INSTALL		0x40
#define	ALL_OPTIONS		0x1f

int	om_test_target_discovery(int arg);
#ifdef __cplusplus
}
#endif

#endif	/* _TEST_H */
