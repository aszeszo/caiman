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

StringList *
readStringListFromFile(char *path)
{
	StringList *s;
	enter_swlib("readStringListFromFile");
	s = (StringList *)swi_readStringListFromFile(path);
	exit_swlib();
	return (s);
}

int
writeStringListToFile(char *path, StringList *strlist)
{
	int i;
	enter_swlib("readStringListFromFile");
	i = swi_writeStringListToFile(path, strlist);
	exit_swlib();
	return (i);
}

char *
get_device()
{
	char *c;

	enter_swlib("get_device");
	c = swi_get_device();
	exit_swlib();
	return (c);
}

char *
get_rawdevice()
{
	char *c;

	enter_swlib("get_rawdevice");
	c = swi_get_rawdevice();
	exit_swlib();
	return (c);
}

void
set_devices(char *ctds)
{
	enter_swlib("set_devices");
	swi_set_devices(ctds);
	exit_swlib();
}

void
set_useAltImage(int minusC)
{
	enter_swlib("set_useAltImage");
	swi_set_useAltImage(minusC);
	exit_swlib();
}

int
get_useAltImage()
{
	int i;
	enter_swlib("get_useAltImage");
	i = swi_get_useAltImage();
	exit_swlib();
	return (i);
}

void
run_parse_dynamic_clustertoc()
{
	enter_swlib("run_parse_dynamic_clustertoc");
	swi_run_parse_dynamic_clustertoc();
	exit_swlib();
}

void
sw_lib_init(int ptype)
{
	enter_swlib("sw_lib_init");
	swi_sw_lib_init(ptype);
	exit_swlib();
}

int
set_instdir_svc_svr(Module * prod)
{
	int i;

	enter_swlib("set_instdir_svc_svr");
	i = swi_set_instdir_svc_svr(prod);
	exit_swlib();
	return (i);
}

void
clear_instdir_svc_svr(Module * prod)
{
	enter_swlib("clear_instdir_svc_svr");
	swi_clear_instdir_svc_svr(prod);
	exit_swlib();
}

char *
gen_pboot_path(char *rootdir)
{
	char *c;

	enter_swlib("gen_pboot_path");
	c = swi_gen_pboot_path(rootdir);
	exit_swlib();
	return (c);
}

char *
gen_bootblk_path(char *rootdir)
{
	char *c;

	enter_swlib("gen_bootblk_path");
	c = swi_gen_bootblk_path(rootdir);
	exit_swlib();
	return (c);
}

char *
gen_openfirmware_path(char *rootdir)
{
	char *c;

	enter_swlib("gen_openfirmware_path");
	c = swi_gen_openfirmware_path(rootdir);
	exit_swlib();
	return (c);
}

int
map_fs_idx_from_mntpnt(char *mntpnt)
{
	int i;

	enter_swlib("map_fs_idx_from_mntpnt");
	i = swi_map_fs_idx_from_mntpnt(mntpnt);
	exit_swlib();
	return (i);
}

int
map_zone_fs_idx_from_mntpnt(char *mntpnt, char *p_rootdir)
{
	int i;

	enter_swlib("map_fs_idx_from_mntpnt");
	i = swi_map_zone_fs_idx_from_mntpnt(mntpnt, p_rootdir);
	exit_swlib();
	return (i);
}
