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

#pragma ident	"@(#)soft_swi_v_version.c	1.2	07/11/12 SMI"

#include "spmisoft_api.h"
#include "sw_swi.h"

int
prod_vcmp(char * v1, char * v2)
{
	int i;

	enter_swlib("prod_vcmp");
	i = swi_prod_vcmp(v1, v2);
	exit_swlib();
	return (i);
}

int
pkg_vcmp(char * v1, char * v2)
{
	int i;

	enter_swlib("pkg_vcmp");
	i = swi_pkg_vcmp(v1, v2);
	exit_swlib();
	return (i);
}

int
is_patch(Modinfo * mi)
{
	int i;

	enter_swlib("is_patch");
	i = swi_is_patch(mi);
	exit_swlib();
	return (i);
}

int
is_patch_of(Modinfo *mi1, Modinfo *mi2)
{
	int i;

	enter_swlib("is_patch_of");
	i = swi_is_patch_of(mi1, mi2);
	exit_swlib();
	return (i);
}
