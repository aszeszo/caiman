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

Module *
load_installed(char *rootdir, boolean_t service)
{
	Module	*m;

	enter_swlib("load_installed");
	m = swi_load_installed(rootdir, service);
	exit_swlib();
	return (m);
}

Modinfo *
next_patch(Modinfo * mod)
{
	Modinfo	*m;

	enter_swlib("next_patch");
	m = swi_next_patch(mod);
	exit_swlib();
	return (m);
}

Modinfo *
next_inst(Modinfo * mod)
{
	Modinfo	*m;

	enter_swlib("next_inst");
	m = swi_next_inst(mod);
	exit_swlib();
	return (m);
}
