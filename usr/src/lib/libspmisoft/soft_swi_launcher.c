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


#ifndef lint
#endif

#include "spmisoft_api.h"
#include "sw_swi.h"

void
parsePackagesToBeAdded()
{
	enter_swlib("parsePackagesToBeAdded");
	(void) swi_parsePackagesToBeAdded();
	exit_swlib();
}

void
setup_launcher(int autoreboot)
{
	enter_swlib("setup_launcher");
	(void) swi_setup_launcher(autoreboot);
	exit_swlib();
}

void
create_dispatch_table()
{
	enter_swlib("create_dispatch_table");
	(void) swi_create_dispatch_table();
	exit_swlib();
}
