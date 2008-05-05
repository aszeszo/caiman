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

/*
 * om_get_disk_slices_info
 * This function will return the disk slices (VTOC) information of the
 * specified disk.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		char *diskname - The name of the disk
 * Output:	None
 * Return:	disk_slices_t * - The VTOC disk slices information for
 *		the disk with diskname will be 	returned. The space will be
 *		allocated here linked and returned to the caller.
 *		NULL - if the partition data can't be returned.
 */
/*ARGSUSED*/
disk_slices_t *
om_get_disk_slices_info(om_handle_t handle, char *diskname)
{
	disk_slices_t	*ds;

	om_errno = 0;
	if (diskname == NULL || diskname[0] == '\0') {
		om_errno = OM_BAD_DISK_NAME;
		return (NULL);
	}

	/*
	 * If the target discovery is not yet completed, set the
	 * error number and return NULL
	 */
	if (!disk_discovery_done) {
		om_errno = OM_DISCOVERY_NEEDED;
		return (NULL);
	}

	if (system_disks  == NULL) {
		om_errno = OM_NO_DISKS_FOUND;
		return (NULL);
	}

	/*
	 * Find the disk from the cache using the passed diskname
	 */
	ds = find_slices_by_disk(diskname);
	return (om_duplicate_disk_slices_info(0, ds));
}

/*
 * om_free_disk_slices_info
 * This function will free up the disk information data allocated during
 * om_get_disk_slices_info().
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		disk_slices_t *dsinfo - The pointer to disk_slices_t. Usually
 *		returned by om_get_disk_slices_info().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_disk_slices_info(om_handle_t handle, disk_slices_t *dsinfo)
{
	om_errno = 0;
	if (dsinfo == NULL) {
		return;
	}

	local_free_slice_info(dsinfo);
}

/*
 * om_duplicate_disk_slices_info
 * This function allocates space and copy the disk_slices_t structure
 * passed as a parameter.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		disk_slices_t * - Pointer to disk_slices_t. Usually the return
 *		value from get_disk_slices_info().
 * Return:	disk_slices_t * - Pointer to disk_slices_t. Space will be
 *		allocated and the data is copied and returned.
 *		NULL, if space cannot be allocated.
 */
/*ARGSUSED*/
disk_slices_t *
om_duplicate_disk_slices_info(om_handle_t handle, disk_slices_t *dslices)
{
	disk_slices_t	*ds;

	om_errno = 0;

	if (dslices == NULL) {
		om_errno = OM_BAD_INPUT;
		return (NULL);
	}

	/*
	 * Allocate and copy the slices_info
	 */
	ds = (disk_slices_t *)calloc(1, sizeof (disk_slices_t));

	if (ds == NULL) {
		om_errno = OM_NO_SPACE;
		return (NULL);
	}

	(void) memcpy(ds, dslices, sizeof (disk_slices_t));

	ds->partition_id = dslices->partition_id;
	ds->disk_name = strdup(dslices->disk_name);

	return (ds);
}
