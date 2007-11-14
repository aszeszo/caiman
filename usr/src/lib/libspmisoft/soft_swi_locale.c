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

#pragma ident	"@(#)soft_swi_locale.c	1.6	07/11/12 SMI"

#include "spmisoft_api.h"
#include "sw_swi.h"

Module *
get_all_locales(void)
{
	Module	*m;

	enter_swlib("get_all_locales");
	m = swi_get_all_locales();
	exit_swlib();
	return (m);
}

int
select_locale(Module *mod, char *locale, int decomp)
{
	int	i;

	enter_swlib("select_locale");
	i = swi_select_locale(mod, locale, decomp);
	exit_swlib();
	return (i);
}

int
deselect_locale(Module *mod, char *locale)
{
	int	i;

	enter_swlib("deselect_locale");
	i = swi_deselect_locale(mod, locale);
	exit_swlib();
	return (i);
}

int
valid_locale(Module *mod, char *locale)
{
	int i;

	enter_swlib("valid_locale");
	i = swi_valid_locale(mod, locale);
	exit_swlib();
	return (i);
}

int
locale_list_selected(StringList **list)
{
	int i;

	enter_swlib("locale_list_selected");
	i = swi_locale_list_selected(list);
	exit_swlib();
	return (i);
}

char *
get_init_default_system_locale()
{
	char *locale;

	enter_swlib("get_init_default_system_locale");
	locale = swi_get_init_default_system_locale();
	exit_swlib();
	return (locale);
}

char *
get_default_system_locale()
{
	char *locale;

	enter_swlib("get_default_system_locale");
	locale = swi_get_default_system_locale();
	exit_swlib();
	return (locale);
}

int
set_default_system_locale(char *locale)
{
	int i;

	enter_swlib("set_default_system_locale");
	i = swi_set_default_system_locale(locale);
	exit_swlib();
	return (i);
}

char *
get_system_locale()
{
	char *locale;

	enter_swlib("get_system_locale");
	locale = swi_get_system_locale();
	exit_swlib();
	return (locale);
}

char *
get_locale_geo(char *locale)
{
	char *geo;

	enter_swlib("get_locale_geo");
	geo = swi_get_locale_geo(locale);
	exit_swlib();
	return (geo);
}

int
save_locale(char *locale, char *target)
{
	int i;

	enter_swlib("save_locale");
	i = swi_save_locale(locale, target);
	exit_swlib();
	return (i);
}

int
get_sys_locale_list(char *lang, char ***localep)
{
	int i;

	enter_swlib("get_sys_locale_list");
	i = swi_get_sys_locale_list(lang, localep);
	exit_swlib();
	return (i);
}

void
build_locale_list()
{
	enter_swlib("build_locale_list");
	swi_build_locale_list();
	exit_swlib();
}

char *
get_composite_locale(char *locale)
{
	char *composite_locale;
	enter_swlib("get_composite_locale");
	composite_locale = swi_get_composite_locale(locale);
	exit_swlib();

	return (composite_locale);
}
