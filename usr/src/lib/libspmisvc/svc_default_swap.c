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
 * Module:	svc_default_swap.c
 * Group:	libspmisvc
 * Description:
 *		The functions used to find and set the default swap slice.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#include "spmisvc_api.h"
#include "spmisvc_lib.h"
#include "spmicommon_api.h"

/* module gobals */
static char *_default_swap_disk = NULL;
static int _default_swap_slice = -1;
static int _default_swap_size = 0;
static boolean_t swapinfo_file_read = B_FALSE;

/* private functions */
static void _ReadSwapinfoFile(void);


void
_ReadSwapinfoFile(void)
{
	char buf[BUFSIZ + 1];
	char *tok = NULL;
	FILE *fp = (FILE *)NULL;

	if (swapinfo_file_read == B_FALSE) {
		swapinfo_file_read = B_TRUE;

		if ((fp = fopen(SWAPINFO_FILE, "r")) == (FILE *)NULL) {
			write_debug(SVC_DEBUG_L1(1), "No /.swapinfo file\n");
			return;
		}

		if (fgets(buf, BUFSIZ, fp)) {

			buf[strlen(buf) - 1] = '\0';

			if ((tok = strtok(buf, " ")) != NULL)
				_default_swap_disk = xstrdup(tok);

			if ((tok = strtok(NULL, " ")) != NULL)
				_default_swap_slice = atoi(tok+1);

			if ((tok = strtok(NULL, " ")) != NULL)
				_default_swap_size = atoi(tok);

			write_debug(SVC_DEBUG_L1(1),
				"Found /.swapinfo file: %s s%d %d",
				_default_swap_disk ? _default_swap_disk :
					"NULL",
				_default_swap_slice, _default_swap_size);
		} else {
			write_debug(SVC_DEBUG_L1(1),
				"/.swapinfo file was empty\n");
		}

		(void) fclose(fp);
	}
}

char *
DefaultSwapGetDisk(void)
{
	if (!swapinfo_file_read) {
		_ReadSwapinfoFile();
	}

	return (_default_swap_disk);
}

int
DefaultSwapGetSlice(void)
{
	if (!swapinfo_file_read) {
		_ReadSwapinfoFile();
	}
	return (_default_swap_slice);
}

int
DefaultSwapGetSize(void)
{
	if (!swapinfo_file_read) {
		_ReadSwapinfoFile();
	}
	return (_default_swap_size);
}

int
DefaultSwapGetDiskobj(Disk_t **diskp)
{
	Disk_t *dp = NULL;
	char *disk = NULL;
	char *slice = NULL;
	int size = 0;

	disk = DefaultSwapGetDisk();

	if (disk) {
		WALK_DISK_LIST(dp) {
			if (streq(disk_name(dp), disk))
				break;
		}
	}

	write_debug(SCR, get_trace_level() > 3, NULL, DEBUG_LOC,
		LEVEL1, "DefaultSwapGetDiskobj: returns = %s",
		dp ? "D_OK" : "D_FAILED");
	if (dp == NULL) {
		*diskp = NULL;
		return (D_FAILED);
	} else {
		*diskp = dp;
		return (D_OK);
	}
}

char *
GetSwapFile(void)
{
	if (access(SWAP2_SWAP_FILE, F_OK) == 0) {
		return (SWAP2_SWAP_FILE);
	}

	return (NULL);
}
