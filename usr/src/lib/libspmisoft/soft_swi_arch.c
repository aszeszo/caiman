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

Arch	*
get_all_arches(Module *mod)
{
	Arch	*ap;

	enter_swlib("get_all_arches");
	ap = swi_get_all_arches(mod);
	exit_swlib();
	return (ap);
}

int
package_selected(Node * np, char * foo)
{
	int	a;

	enter_swlib("package_selected");
	a = swi_package_selected(np, foo);
	exit_swlib();
	return (a);
}

char  *
get_default_arch(void)
{
	char	*cp;

	enter_swlib("get_default_arch");
	cp = swi_get_default_arch();
	exit_swlib();
	return (cp);
}

char *
get_default_impl(void)
{
	char	*cp;

	enter_swlib("get_default_impl");
	cp = swi_get_default_impl();
	exit_swlib();
	return (cp);
}

int
select_arch(Module * prod, char * arch)
{
	int	i;

	enter_swlib("select_arch");
	i = swi_select_arch(prod, arch);
	exit_swlib();
	return (i);
}

int
valid_arch(Module *prod, char *arch)
{
	int	i;

	enter_swlib("valid_arch");
	i = swi_valid_arch(prod, arch);
	exit_swlib();
	return (i);
}

int
deselect_arch(Module * prod, char * arch)
{
	int	i;

	enter_swlib("deselect_arch");
	i = swi_deselect_arch(prod, arch);
	exit_swlib();
	return (i);
}

void
mark_arch(Module * prod)
{
	enter_swlib("mark_arch");
	swi_mark_arch(prod);
	exit_swlib();
	return;
}
