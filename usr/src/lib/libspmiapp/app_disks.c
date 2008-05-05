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
 * Module:	app_disks.c
 * Group:	libspmiapp
 * Description:
 *	Generic disk handling convenience functions needed by the apps.
 */
#include <stdlib.h>
#include <string.h>
#include <libgen.h>
#include <sys/types.h>

#include "spmiapp_lib.h"
#include "spmisvc_lib.h"
#include "app_utils.h"

/*
 * Function: DiskRestoreAll
 * Description:
 *	Restore all the disks in disk list to the current state
 *	from the requested state.
 *
 * Scope:	PUBLIC
 * Parameters:
 *	state:	CFG_COMMIT or CFG_EXIST
 * Return: none
 * Globals: operates on the global disk list.
 * Notes:
 */
void
DiskRestoreAll(Label_t state)
{
	Disk_t *dp;

	WALK_DISK_LIST(dp) {
		restore_disk(dp, state);
	}
}

/*
 * Function: DiskCommitAll
 * Description:
 *	Commit all the disks in disk list (i.e. copy the current
 *	configuration to the committed state of the disks.
 *
 * Scope:	PUBLIC
 * Parameters:  none
 * Return: none
 * Globals: operates on the global disk list.
 * Notes:
 */
void
DiskCommitAll(void)
{
	Disk_t *dp;

	WALK_DISK_LIST(dp) {
		commit_disk_config(dp);
	}
}

/*
 * Function: DiskSelectAll
 * Description:
 *	Select or deselect all the disks in the disk list.
 *
 * Scope:	PUBLIC
 * Parameters:
 *	select:
 *		0: deselect all disks
 *		!0: select all disks
 * Return: none
 * Globals: operates on the global disk list.
 * Notes:   On Intel systems you may want to call
 *          DiskDeselectNonSolaris after calling this
 *          function, to prevent unwanted selection
 *          of disks without Solaris partitions.
 */
void
DiskSelectAll(int select)
{
	Disk_t *dp;

	WALK_DISK_LIST(dp) {
		if (select)
			select_disk(dp, NULL);
		else
			deselect_disk(dp, NULL);
	}
}

/*
 * Function: DiskDeselectNonSolaris
 * Description:
 *	Deselect all the disks in the disk list
 *      which don't have Solaris partitions on them.
 *
 * Scope:	PUBLIC
 * Parameters:  none
 * Return:      none
 * Globals:     operates on the global disk list.
 * Notes:       Used on Intel systems where one or more
 *              disks may not have Solaris partitions.
 *              Prevents erroneous attempts to use
 *              DOS-formatted disks for installation
 *              or upgrade.
 */
void
DiskDeselectNonSolaris(Label_t state)
{
	Disk_t *dp;

	write_debug(APP_DEBUG_L1, "Entering DiskDeselectNonSolaris");

	if (state != CFG_CURRENT && state != CFG_COMMIT && state != CFG_EXIST) {
		write_debug(APP_DEBUG_L1,
			    "DiskDeselectNonSolaris: bad argument");
		return;
	}

	if (IsIsa("i386")) {
		write_debug(APP_DEBUG_L1, "Walking disk list");
		WALK_DISK_LIST(dp) {
			if (get_solaris_part(dp, state) == 0) {
				write_debug(APP_DEBUG_L1,
				    "Deselecting %s: no Solaris partition",
				    disk_name(dp));
				deselect_disk(dp, NULL);
			}
		}
	}
	write_debug(APP_DEBUG_L1, "Leaving DiskDeselectNonSolaris");

}

/*
 * Function: DiskNullAll
 * Description:
 *	Configure all selected disks to be empty.
 *
 * Scope:	PUBLIC
 * Parameters: none
 * Return: none
 * Globals: operates on the global disk list.
 * Notes:
 */
void
DiskNullAll(void)
{
	Disk_t *dp;

	WALK_DISK_LIST(dp) {
		SdiskobjConfig(LAYOUT_RESET, dp, NULL);
	}
}

void
DiskPrintAll(void)
{
	Disk_t *dp;

	WALK_DISK_LIST(dp) {
		print_disk(dp, NULL);
	}
}

/*
 * Function:	DiskGetContentDefault
 * Description:	Sum up the total space that would be required to
 *		hold the default layout configuration
 * Scope:	public
 * Parameters:	none
 * Return:	# >= 0	total number of sectors
 */
int
DiskGetContentDefault(void)
{
	ResobjHandle	res;
	int		total = 0;
	int		subtotal;

	/* sum up all independent file system resources */
	WALK_DIRECTORY_LIST(res) {
		if (ResobjIsIndependent(res))
			total += ResobjGetContent(res, ADOPT_ALL,
					RESSIZE_DEFAULT);
	}

	subtotal = total;
	/* find the minimum swap total for this system */
	total += ResobjGetSwap(RESSIZE_DEFAULT);

	if (get_trace_level())
		write_message(LOG, STATMSG, LEVEL1,
		    "===(Default) Grand Total: %d, +swap: %d",
		    sectors_to_mb(subtotal), sectors_to_mb(total));
	return (sectors_to_mb(total));
}

/*
 * Function:	DiskGetContentMinimum
 * Description:
 *	Sum up the total space that would be required to hold the minimum
 *	layout configuration.
 * Scope:	public
 * Parameters:	none
 * Return:	# >= 0	total number of sectors
 */
int
DiskGetContentMinimum(void)
{
	ResobjHandle	res;
	int		total = 0;
	int		subtotal;

	/* sum up all independent file system resources */
	WALK_DIRECTORY_LIST(res) {
		if (ResobjIsIndependent(res))
			total += ResobjGetContent(res, ADOPT_ALL,
					RESSIZE_MINIMUM);
	}

	subtotal = total;
	/* find the minimum swap total for this system */
	total += ResobjGetSwap(RESSIZE_MINIMUM);
	if (get_trace_level())
		write_message(LOG, STATMSG, LEVEL1,
		    "===(Minimum) Grand Total: %d, +swap: %d",
		    sectors_to_mb(subtotal), sectors_to_mb(total));
	return (sectors_to_mb(total));
}
