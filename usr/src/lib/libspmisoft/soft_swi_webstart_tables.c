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

int
readProductTables()
{
	int i;

	enter_swlib("readProductTables");
	i = (int)swi_readProductTables();
	exit_swlib();
	return (i);
}

void
readCDInfo(CD_Info *cdinfo)
{
	enter_swlib("readCDInfo");
	(void) swi_readCDInfo(cdinfo);
	exit_swlib();
}

void
readProductToc(CD_Info *cdinfo)
{
	enter_swlib("readProductToc");
	(void) swi_readProductToc(cdinfo);
	exit_swlib();
}

char *
get_loc_cdname(char *subdir)
{
	char *c;
	enter_swlib("get_loc_cdname");
	c = (char *)swi_get_loc_cdname(subdir);
	exit_swlib();
	return (c);
}

char *
get_loc_cdhelp(char *subdir)
{
	char *c;
	enter_swlib("get_loc_cdhelp");
	c = (char *)swi_get_loc_cdhelp(subdir);
	exit_swlib();
	return (c);
}

char *
get_loc_prodhelp(char *pdsuffix)
{
	char *c;
	enter_swlib("get_loc_prodhelp");
	c = (char *)swi_get_loc_prodhelp(pdsuffix);
	exit_swlib();
	return (c);
}

char *
get_loc_license_path()
{
	char *c;
	enter_swlib("get_loc_license_path");
	c = (char *)swi_get_loc_license_path();
	exit_swlib();
	return (c);
}

void
parsePDfile(CD_Info *cdinfo)
{
	enter_swlib("parsePDfile");
	(void) swi_parsePDfile(cdinfo);
	exit_swlib();
}

void
setMkit(Media_Kit_Info *newmkit)
{
	enter_swlib("setMkit");
	(void) swi_setMkit(newmkit);
	exit_swlib();
}

Media_Kit_Info *
getMkit()
{
	Media_Kit_Info *m;

	enter_swlib("getMkit");
	m = (Media_Kit_Info *)swi_getMkit();
	exit_swlib();
	return (m);
}
