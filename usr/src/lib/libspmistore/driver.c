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
 * Group:	libspmistore
 * Description:	Test module to drive unit tests
 */

#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <libgen.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/dkio.h>
#include <sys/vtoc.h>
#include <sys/fs/ufs_fs.h>
#include "spmistore_lib.h"
#include "spmicommon_api.h"

/* --------------------- Test Interface ------------------------ */

main(int argc, char **argv, char **env)
{
	Disk_t *	dp;
	int		n;
	char *		file = NULL;
	int		printboot = 0;

	while ((n = getopt(argc, argv, "bx:d:h")) != -1) {
		switch (n) {
		case 'b':
			printboot++;
			break;
		case 'd':
			(void) SetSimulation(SIM_SYSDISK, 1);
			file = xstrdup(optarg);
			(void) printf("Using %s as an input file\n", file);
			break;
		case 'x':
			(void) set_trace_level(atoi(optarg));
			break;
		case 'h':
			(void) printf(
			    "Usage: %s [-x <debug level>] [-d <disk file>]\n",
			    basename(argv[0]));
			exit(1);
		}
	}

	(void) set_rootdir("/a");
	n = DiskobjInitList(file);
	if (n < 0) {
		(void) printf("Error %d returned from disk load\n", n);
		exit (1);
	}

	(void) printf("%d disks found\n\n", n);
	(void) printf("-----------------------------------\n");

	WALK_DISK_LIST(dp) {
		print_disk(dp, NULL);
		(void) printf("-----------------------------------\n");
	}

	if (printboot)
		BootobjPrint();

	exit (0);
}
