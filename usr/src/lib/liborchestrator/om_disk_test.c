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


#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "orchestrator_private.h"
#include "test.h"

int
main(int argc, char **argv)
{
	int	opt;
	int	options = 0;

	while ((opt = getopt(argc, argv, "dpsuISU")) != -1) {
		switch (opt) {
		/*
		 * Diskinfo only
		 */
		case 'd':
			options |= DISK_INFO;
			break;
		case 'p':
			options = options | PART_INFO;
			break;
		case 's':
			options |= SLICE_INFO;
			break;
		case 'u':
			options |= UPGRADE_TARGET_INFO;
			break;
		case 'I':
			options |= DO_INSTALL;
			break;
		case 'U':
			options |= DO_UPGRADE;
			break;
		case 'S':
			options |= DO_SLIM_INSTALL;
			break;
		default:
			(void) fprintf(stderr, "Usage: %s -dpsuIU\n");
			(void) fprintf(stderr, "Use -d to get disk_info\n");
			(void) fprintf(stderr,
			    "Use -p to get disk_partitions\n");
			(void) fprintf(stderr, "Use -s to get disk_slices\n");
			(void) fprintf(stderr,
			    "Use -u to get upgrade targets\n");
			(void) fprintf(stderr,
			    "Use -I to perform initial install\n");
			(void) fprintf(stderr, "Use -U to perform upgrade\n");
			(void) fprintf(stderr,
			    "Specifying no options is same as");
			(void) fprintf(stderr, "-dpsuI");
			exit(1);
		}
	}

	if (options == 0) {
		options |= ALL_OPTIONS;
	}
	(void) om_test_target_discovery(options);
	exit(0);
}
