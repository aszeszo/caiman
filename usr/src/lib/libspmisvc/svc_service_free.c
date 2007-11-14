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

#pragma ident	"@(#)svc_service_free.c	1.3	07/10/09 SMI"


#include "spmicommon_lib.h"
#include "spmisoft_lib.h"
#include "spmisvc_lib.h"
#include <stdlib.h>

/* Public Prototype Specifications */

void	free_service_list(SW_service_list *);
void	free_error_info(SW_error_info *);
void	free_createroot_info(SW_createroot_info *);

/* Private Prototype Specifications */

static void	free_service(SW_service *);

void
free_service_list(SW_service_list *svc_list)
{
	SW_service	*cursvc, *nextone;

	cursvc = svc_list->sw_svl_services;
	while (cursvc) {
		nextone = cursvc->next;
		free_service(cursvc);
		free(cursvc);
		cursvc = nextone;
	}
	svc_list->sw_svl_services = NULL;
	free(svc_list);
}

void
free_platform_list(StringList *platlist)
{
	StringListFree(platlist);
}

void
free_error_info(SW_error_info *err_info)
{
	switch (err_info->sw_error_code) {
	  case SW_INSUFFICIENT_SPACE:
		free_final_space_report(err_info->sw_space_results);
		break;

	}
	free(err_info);
}

void
free_createroot_info(SW_createroot_info *cri)
{
	SW_pkgadd_def	*nextpkg, *pkg;
	SW_remmnt	*nextrmnt, *rmnt;

	pkg = cri->sw_root_packages;
	cri->sw_root_packages = NULL;
	while (pkg) {
		nextpkg = pkg->next;
		if (pkg->sw_pkg_dir) {
			free(pkg->sw_pkg_dir);
			pkg->sw_pkg_dir = NULL;
		}
		if (pkg->sw_pkg_name) {
			free(pkg->sw_pkg_name);
			pkg->sw_pkg_name = NULL;
		}
		free(pkg);
		pkg = nextpkg;
	}
	rmnt = cri->sw_root_remmnt;
	cri->sw_root_remmnt = NULL;
	while (rmnt) {
		nextrmnt = rmnt->next;
		if (rmnt->sw_remmnt_mntpnt) {
			free(rmnt->sw_remmnt_mntpnt);
			rmnt->sw_remmnt_mntpnt = NULL;
		}
		if (rmnt->sw_remmnt_mntdir) {
			free(rmnt->sw_remmnt_mntdir);
			rmnt->sw_remmnt_mntdir = NULL;
		}
		free(rmnt);
		rmnt = nextrmnt;
	}
	free(cri);
}

static void
free_service(SW_service *svc)
{
	free(svc->sw_svc_os);
	svc->sw_svc_os = NULL;
	free(svc->sw_svc_version);
	svc->sw_svc_version = NULL;
	free(svc->sw_svc_isa);
	svc->sw_svc_isa = NULL;
	free(svc->sw_svc_plat);
	svc->sw_svc_plat = NULL;
}
