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
 * Module:	driver.c
 * Group:	none
 * Description:
 */

#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/fstyp.h>
#include <sys/fsid.h>
#include <sys/mntent.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/fs/ufs_fs.h>
#include "spmisvc_lib.h"
#include "spmisvc_api.h"
#include "spmistore_api.h"
#include "spmisoft_lib.h"
#include "spmisoft_api.h"
#include "spmicommon_api.h"

main(int argc, char **argv, char **env)
{
	Disk_t *	list = NULL;
	Disk_t *	dp;
	OSList		oslist;
	int		n;
	char *		file = NULL;
	char *		rootmount = "/a";
	int		u = 0;

	while ((n = getopt(argc, argv, "x:ud:L")) != -1) {
		switch (n) {
		case 'd':
			(void) SetSimulation(SIM_SYSDISK, 1);
			file = strdup(optarg);
			(void) printf("Using %s as an input file\n", file);
			break;
		case 'x':
			(void) set_trace_level(atoi(optarg));
			break;
		case 'L':
			rootmount = "/";
		case 'u':
			u++;
			break;
		default:
			(void) fprintf(stderr,
		"Usage: %s [-x <level>] [-u] [-L] [-d <disk file>]\n",
				argv[0]);
			exit(1);
		}
	}

	(void) set_rootdir(rootmount);
	/* initialize the disk list only for non-direct runs */
	if (!streq(rootmount, "/")) {
		n = DiskobjInitList(file);
		(void) printf("Disks found - %d\n", n);
	}

	if (u > 0) {
		oslist = SliceFindUpgradeable();
		n = OSListCount(oslist);
		if (n) {
			dump_upgradeable(oslist);
		} else
			(void) printf("No upgradeable slices.\n");
		OSListFree(&oslist);
	}
	exit(0);
}
