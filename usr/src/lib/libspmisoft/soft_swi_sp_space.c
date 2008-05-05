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


#include "spmisoft_api.h"
#include "sw_swi.h"

FSspace **
calc_cluster_space(Module *mod, ModStatus status)
{
	FSspace **fsp;

	enter_swlib("calc_cluster_space");
	fsp = swi_calc_cluster_space(mod, status);
	exit_swlib();
	return (fsp);
}

FSspace **
calc_package_space(Module *mod, ModStatus status)
{
	FSspace **fsp;

	enter_swlib("calc_package_space");
	fsp = swi_calc_package_space(mod, status);
	exit_swlib();
	return (fsp);
}

ulong
calc_tot_space(Product * prod)
{
	ulong l;

	enter_swlib("calc_tot_space");
	l = swi_calc_tot_space(prod);
	exit_swlib();
	return (l);
}

long
tot_pkg_space(Modinfo *m)
{
	long l;

	enter_swlib("tot_pkg_space");
	l = swi_tot_pkg_space(m);
	exit_swlib();
	return (l);
}

void
free_fsspace(FSspace *fsp)
{
	enter_swlib("free_fsspace");
	swi_free_fsspace(fsp);
	exit_swlib();
	return;
}

int
calc_sw_fs_usage(FSspace **fsp, int (*callback)(void *, void *), void *arg)
{
	int i;

	enter_swlib("calc_sw_fs_usage");
	i = swi_calc_sw_fs_usage(fsp, callback, arg);
	exit_swlib();
	return (i);
}
