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
 * Module:	app_lfs.c
 * Group:	libspmiapp
 * Description:
 *	Application library level local file system handling routines.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "spmicommon_api.h"
#include "spmistore_api.h"
#include "spmiapp_api.h"
#include "app_utils.h"

#include "app_strings.h"

/*
 * Function:	any_preservable_filesystems
 * Description:
 *	A function used by both installtool and ttinstall to determine
 *	if there are any preservable file systems on the system being
 *	installed.
 * Scope:	PUBLIC
 * Parameters:  None
 * Return:	[int]
 *	0 - No Preservable file systems found
 *	1 - Preservable file systems found
 */

int
any_preservable_filesystems(void)
{
	int	i;
	Disk_t	*dp;

	WALK_DISK_LIST(dp) {
		if (disk_selected(dp)) {
			/*
			 * check the sdisk geometry to make sure it is not NULL
			 */
			if (sdisk_geom_null(dp))
				continue;
			/*
			 * check the sdisk geometry, if existing
			 * differs from current
			 * then the geometry has changed and file systems
			 * cannot be preserved
			 */
			if (sdisk_geom_same(dp, CFG_EXIST) != D_OK)
					continue;
			/*
			 * if you get this far then the geometry
			 * check has passed for each
			 * disk, now check the size of each slice to see if it
			 * may contain data (size > 0)
			 *
			 * if the size of a slice is greater than zero, this
			 * slice can be preserved
			 */
			WALK_SLICES(i) {
				if ((orig_slice_size(dp, i) > 0) &&
				    !slice_locked(dp, i))
					return (1);
			}
		}
	}

	/*
	 * else no preservable file systems were found (size <= 0)
	 */
	return (0);

}
