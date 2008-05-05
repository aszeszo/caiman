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



/*
 * Module:	app_sw.c
 * Group:	libspmiapp
 * Description:
 *	SW lib - app level code
 */
#include <stdlib.h>
#include <string.h>

#include "spmiapp_api.h"

/*
 * Function: initNativeArch
 * Description:
 *	Initialize the software library to the current native machine
 *	architecture.
 * Scope:	public
 * Parameters: none
 * Return:	[void]
 * Globals:	none
 * Notes:
 */
void
initNativeArch(void)
{
	char *nativeArch = NULL;

	Module *prod = get_current_product();

	nativeArch = get_default_arch();
	select_arch(prod, nativeArch);
	mark_arch(prod);
}
