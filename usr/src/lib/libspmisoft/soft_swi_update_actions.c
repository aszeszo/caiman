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


#pragma ident	"@(#)soft_swi_update_actions.c	1.4	07/11/09 SMI"

#include "spmisoft_api.h"
#include "sw_swi.h"

int
load_clients(void)
{
	int i;

	enter_swlib("load_clients");
	i = swi_load_clients();
	exit_swlib();
	return (i);
}

int
load_zones(void)
{
	int i;

	enter_swlib("load_zones");
	i = swi_load_zones();
	exit_swlib();
	return (i);
}

void
update_action(Module * toggled_mod)
{
	enter_swlib("update_action");
	swi_update_action(toggled_mod);
	exit_swlib();
}

int
upg_select_locale(Module *prodmod, char *locale)
{
	int i;

	enter_swlib("upg_select_locale");
	i = swi_upg_select_locale(prodmod, locale);
	exit_swlib();
	return (i);
}

int
upg_deselect_locale(Module *prodmod, char *locale)
{
	int i;

	enter_swlib("upg_deselect_locale");
	i = swi_upg_deselect_locale(prodmod, locale);
	exit_swlib();
	return (i);
}

int
upg_select_geo(Module *prodmod, char *locale)
{
	int i;

	enter_swlib("upg_select_geo");
	i = swi_upg_select_geo(prodmod, locale);
	exit_swlib();
	return (i);
}

int
upg_deselect_geo(Module *prodmod, char *locale)
{
	int i;

	enter_swlib("upg_deselect_geo");
	i = swi_upg_deselect_geo(prodmod, locale);
	exit_swlib();
	return (i);
}
