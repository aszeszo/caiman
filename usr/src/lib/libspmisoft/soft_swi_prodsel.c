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
#pragma ident	"@(#)soft_swi_prodsel.c	1.3	07/11/09 SMI"
#endif

#include "spmisoft_api.h"
#include "sw_swi.h"

Module *
add_cd_module(Module *mod, char *cdname, char *locname, char *subdir)
{
	Module	*m;

	enter_swlib("add_cd_module");
	m = swi_add_cd_module(mod, cdname, locname, subdir);
	exit_swlib();
	return (m);
}

Module *
add_os_module(Module *mod, char *osfilename, char *ospath)
{
	Module	*m;

	enter_swlib("add_os_module");
	m = swi_add_os_module(mod, osfilename, ospath);
	exit_swlib();
	return (m);
}

Module *
add_comp_module(Module *mod, char *pdname, char *locname, int defins)
{
	Module	*m;

	enter_swlib("add_comp_module");
	m = swi_add_comp_module(mod, pdname, locname, defins);
	exit_swlib();
	return (m);
}

Module *
get_all_cds(void)
{
	Module	*m;

	enter_swlib("get_all_cds");
	m = (Module *)swi_get_all_cds();
	exit_swlib();
	return (m);
}

int
select_cd(Module *mod, char *cd)
{
	int i;

	enter_swlib("select_cd");
	i = swi_select_cd(mod, cd);
	exit_swlib();
	return (i);
}

int
deselect_cd(Module *mod, char *cd)
{
	int i;

	enter_swlib("deselect_cd");
	i = swi_deselect_cd(mod, cd);
	exit_swlib();
	return (i);
}

int
select_component(Module *mod, char *pdsuffix)
{
	int i;

	enter_swlib("select_component");
	i = swi_select_component(mod, pdsuffix);
	exit_swlib();
	return (i);
}

int
deselect_component(Module *mod, char *pdsuffix)
{
	int i;

	enter_swlib("deselect_component");
	i = swi_deselect_component(mod, pdsuffix);
	exit_swlib();
	return (i);
}

long
get_cd_fs_size(CD_Info *cdinfo, FileSys fs)
{
	long i;

	enter_swlib("get_cd_fs_size");
	i = swi_get_cd_fs_size(cdinfo, fs);
	exit_swlib();
	return (i);
}

long
get_cd_size(CD_Info *cdinfo)
{
	long i;

	enter_swlib("get_cd_size");
	i = swi_get_cd_size(cdinfo);
	exit_swlib();
	return (i);
}

long
get_component_fs_size(Product_Toc *pdinfo, FileSys fs)
{
	long i;

	enter_swlib("get_component_fs_size");
	i = swi_get_component_fs_size(pdinfo, fs);
	exit_swlib();
	return (i);
}

long
get_component_size(Product_Toc *pdinfo)
{
	long i;

	enter_swlib("get_component_size");
	i = swi_get_component_size(pdinfo);
	exit_swlib();
	return (i);
}
