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

#pragma ident	"@(#)soft_swi_media.c	1.4	07/11/12 SMI"

#include "spmisoft_api.h"
#include "sw_swi.h"

Module *
add_media(char * dir)
{
	Module *m;

	enter_swlib("add_media");
	m = swi_add_media(dir);
	exit_swlib();
	return (m);
}

Module *
add_specific_media(char * dir, char * dev)
{
	Module *m;

	enter_swlib("add_specific_media");
	m = swi_add_specific_media(dir, dev);
	exit_swlib();
	return (m);
}

int
load_media(Module * mod, int use_packagetoc)
{
	int i;

	enter_swlib("load_media");
	i = swi_load_media(mod, use_packagetoc);
	exit_swlib();
	return (i);
}

int
unload_media(Module * mod)
{
	int i;

	enter_swlib("unload_media");
	i = swi_unload_media(mod);
	exit_swlib();
	return (i);
}

int
eject_media( char* device, MediaType mt )
{
        int i;
	
	enter_swlib( "eject_media" );
	i = swi_eject_media( device, mt );
	exit_swlib();
	return (i);
}

void
set_eject_on_exit(int value)
{
	enter_swlib("set_eject_on_exit");
	swi_set_eject_on_exit(value);
	exit_swlib();
	return;
}

Module *
get_media_head(void)
{
	Module *m;

	enter_swlib("get_media_head");
	m = swi_get_media_head();
	exit_swlib();
	return (m);
}

Module *
find_media(char * dir, char * dev)
{
	Module *m;

	enter_swlib("find_media");
	m = swi_find_media(dir, dev);
	exit_swlib();
	return (m);
}
