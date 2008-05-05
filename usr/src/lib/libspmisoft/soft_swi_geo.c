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
get_all_geos(void)
{
	Module	*m;

	enter_swlib("get_all_geos");
	m = swi_get_all_geos();
	exit_swlib();
	return (m);
}

int
select_geo(Module *mod, char *geo)
{
	int i;

	enter_swlib("select_geo");
	i = swi_select_geo(mod, geo);
	exit_swlib();
	return (i);
}

int
deselect_geo(Module *mod, char *geo)
{
	int i;

	enter_swlib("deselect_geo");
	i = swi_deselect_geo(mod, geo);
	exit_swlib();
	return (i);
}

int
valid_geo(Module *mod, char *geo)
{
	int i;

	enter_swlib("valid_geo");
	i = swi_valid_geo(mod, geo);
	exit_swlib();
	return (i);
}

void
generate_locgeo_lists(char ***locs, char ***geos)
{
	enter_swlib("generate_locgeo_lists");
	swi_generate_locgeo_lists(locs, geos);
	exit_swlib();
}

char *
geo_name_from_code(char *geo)
{
	char *c;

	enter_swlib("geo_name_from_code");
	c = swi_geo_name_from_code(geo);
	exit_swlib();
	return (c);
}
