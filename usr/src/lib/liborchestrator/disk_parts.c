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

#pragma ident	"@(#)disk_parts.c	1.7	07/10/11 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "orchestrator_private.h"

extern boolean_t	whole_disk = B_FALSE; /* assume existing partition */

/*
 * om_get_disk_partition_info
 * This function will return the partition information of the specified disk.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		char *diskname - The name of the disk
 * Output:	None
 * Return:	disk_parts_t * - The fdisk partition information for
 *		the disk with diskname will be 	returned. The space will be
 *		allocated here linked and returned to the caller.
 *		NULL - if the partition data can't be returned.
 */
/*ARGSUSED*/
disk_parts_t *
om_get_disk_partition_info(om_handle_t handle, char *diskname)
{
	disk_parts_t	*dp;

	/*
	 * Validate diskname
	 */
	if (diskname == NULL || diskname[0] == '\0') {
		om_set_error(OM_BAD_DISK_NAME);
		return (NULL);
	}

	/*
	 * If the discovery is not yet completed or not started,
	 * return error
	 */
	if (!disk_discovery_done) {
		om_set_error(OM_DISCOVERY_NEEDED);
		return (NULL);
	}

	if (system_disks == NULL) {
		om_set_error(OM_NO_DISKS_FOUND);
		return (NULL);
	}

	/*
	 * Find the disk from the cache using the diskname
	 */
	dp = find_partitions_by_disk(diskname);
	if (dp == NULL) {
		return (NULL);
	}

	/*
	 * copy the data
	 */
	return (om_duplicate_disk_partition_info(handle, dp));
}

/*
 * om_free_disk_partition_info
 * This function will free up the disk information data allocated during
 * om_get_disk_partition_info().
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		disk_parts_t *dinfo - The pointer to disk_parts_t. Usually
 *		returned by om_get_disk_partition_info().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_disk_partition_info(om_handle_t handle, disk_parts_t *dpinfo)
{
	if (dpinfo == NULL) {
		return;
	}

	local_free_part_info(dpinfo);
}

/*
 * om_validate_and_resize_disk_partitions
 * This function will check whether the the partition information of the
 * specified disk is valid. If the reuqested space can't be allocated, then
 * suggested partition allocation will be returned.
 * Input:	disk_parts_t *dpart
 * Output:	None
 * Return:	disk_parts_t *, with the corrected values. If the sizes
 *		are valide, the return disk_parts_t structure will have same
 *		data as the the	disk_parts_t structure passed as the input.
 *		NULL, if the partition data is invalid.
 * Note:	If the partition is not valid, the om_errno will be set to
 *		the actual error condition. The error information can be
 *		obtained by calling om_get_errno().
 *
 *		This function checks:
 *		- Whether the total partition space is < disk space
 *		- There is enough space to create a new parition
 *		- if there are holes between partitions, can the new
 *		partition fitted with in any of the holes.
 */
/*ARGSUSED*/
disk_parts_t *
om_validate_and_resize_disk_partitions(om_handle_t handle, disk_parts_t *dpart)
{
	disk_target_t	*dt;
	disk_parts_t	*dp, *new_dp;
	int		i, j;
	int		used = 0;
	int		max_space = 0;
	boolean_t	changed = B_FALSE;

	/*
	 * validate the input
	 */
	if (dpart == NULL) {
		om_set_error(OM_INVALID_DISK_PARTITION);
		return (NULL);
	}

	/*
	 * Is the target discovery completed?
	 */
	if (!disk_discovery_done) {
		om_set_error(OM_DISCOVERY_NEEDED);
		return (NULL);
	}

	if (system_disks  == NULL) {
		om_set_error(OM_NO_DISKS_FOUND);
		return (NULL);
	}

	if (dpart->disk_name == NULL) {
		om_set_error(OM_INVALID_DISK_PARTITION);
		return (NULL);
	}

	/*
	 * Find the disk from the cache using the diskname
	 */
	dt = find_disk_by_name(dpart->disk_name);
	if (dt == NULL) {
		om_set_error(OM_INVALID_DISK_PARTITION);
		return (NULL);
	}

	/*
	 * Create the disk_parts_t structure to be returned
	 */
	new_dp = om_duplicate_disk_partition_info(handle, dpart);
	if (new_dp == NULL) {
		return (NULL);
	}

	/*
	 * Calculate the total size used for partitions and compare
	 * it with disk size to see that it can be accommodated
	 */
	for (i = 0; i < FD_NUMPART; i++) {
		used += new_dp->pinfo[i].partition_size;
	}

	if (used > dt->dinfo.disk_size) {
		om_set_error(OM_CONFIG_EXCEED_DISK_SIZE);
	}

	/*
	 * If there are no disk partitions defined, The caller has defined
	 * the partitions. We already checked the size, so return success
	 * For slim, if there were no disk partitions defined, then the user
	 * is using the whole disk. These are the only options available. This
	 * will have to be reworked for futures stuff. XXX Fix XXX.
	 */
	if (dt->dparts == NULL) {
		whole_disk = B_TRUE;
		return (new_dp);
	}

	dp = dt->dparts;
	/*
	 * Compare the size and partition type of each partition
	 * to decide whether anything is changed. For slim this means
	 * not changing subsequent partitions to type 100(unknown). This
	 * is only true for slim at this point. XXX needs to be fixed later.
	 */
	for (i = 0; i < FD_NUMPART; i++) {
		if ((dp->pinfo[i].partition_size !=
		    new_dp->pinfo[i].partition_size) ||
		    (dp->pinfo[i].partition_type !=
		    new_dp->pinfo[i].partition_type)) {
			if (new_dp->pinfo[i].partition_type == 100) {
				continue;
			}
			om_log_print("disk partition info changed\n");
			changed = B_TRUE;
		}
	}
	/*
	 * For slim, we assume 2 options 1) The user uses the whole
	 * disk, 2) the user keeps the existing Solaris partition
	 * and uses it. So, if partition table not changed, 
	 * whole_disk = B_FALSE.
	 */
	if (!changed) {
		/*
		 * No change in the partition table. whole_disk stays
		 * B_FALSE.
		 */
		return (new_dp);
	}
	/*
	 * For Slim Oct only. XXX rethink this in general.
	 */
	whole_disk = B_TRUE;
	/*
	 * Check whether this operation is allowed.
	 * For example if there are more than one partition with the same id
	 * deleting one will delete all the partitions with the same id
	 * All these changes will go away once underlying installer can delete
	 * partitions by number and not by type.
	 */
	for (i = 0; i < FD_NUMPART; i++) {
		/*
		 * Ignore if the existing partition in the disk is
		 * UNUSED or undefined (0)
		 */
		if ((dp->pinfo[i].partition_type == PART_UNDEFINED) ||
		    (dp->pinfo[i].partition_type == UNUSED)) {
			continue;
		}
		for (j = i+1; j < FD_NUMPART; j++) {
			/*
			 * If there are more than one partition have
			 * same partition id in the existing
			 * fdisk table, check whether the user is changing
			 * it using dwarf installer
			 */
			if (dp->pinfo[i].partition_type ==
			    dp->pinfo[j].partition_type) {
				/*
				 * if the user changes partition type and
				 * not sizes, then pfinstall will delete all
				 * the partitions of the type. So we should not
				 * allow it
				 */
				if ((dp->pinfo[i].partition_type !=
				    new_dp->pinfo[i].partition_type) &&
				    (dp->pinfo[i].partition_size ==
				    new_dp->pinfo[i].partition_size)) {
					om_set_error(OM_UNSUPPORTED_CONFIG);
					free(new_dp);
					return (NULL);
				}
				if ((dp->pinfo[j].partition_type !=
				    new_dp->pinfo[j].partition_type) &&
				    (dp->pinfo[j].partition_size ==
				    new_dp->pinfo[j].partition_size)) {
					om_set_error(OM_UNSUPPORTED_CONFIG);
					free(new_dp);
					return (NULL);
				}
				/*
				 * If one of the partitions of the same
				 * partition type is deleted while another
				 * one doesn't change its size or type, then
				 * the user wants to preserve the other one
				 * we cannot handle it with current installer
				 */
				if ((dp->pinfo[i].partition_type ==
				    new_dp->pinfo[i].partition_type) &&
				    (dp->pinfo[i].partition_size ==
				    new_dp->pinfo[i].partition_size) &&
				    (dp->pinfo[j].partition_size !=
				    new_dp->pinfo[j].partition_size)) {
					om_set_error(OM_UNSUPPORTED_CONFIG);
					free(new_dp);
					return (NULL);
				}
				/*
				 * We have already handled type change with out
				 * size change. So now handle size change or
				 * size and type change.
				 * if the size of the partition i is changed,
				 * the gui deletes all partitions below it.
				 * We should allow that change. So start
				 * comparing only index j.
				 */
				if ((dp->pinfo[j].partition_size !=
				    new_dp->pinfo[j].partition_size) &&
				    (new_dp->pinfo[j].partition_size != 0)) {
					om_set_error(OM_UNSUPPORTED_CONFIG);
					free(new_dp);
					return (NULL);
				}
			}
		}
	}

	/*
	 * The caller changed the partition sizes but offset to each partition
	 * may not be updated by the caller. So update the offset to each
	 * partition if needed.
	 */
	for (i = 1; i < FD_NUMPART; i++) {
		uint32_t	size1, size2;
		uint32_t	offset1, offset2;

		j = i-1;
		size1 = dp->pinfo[j].partition_size;
		size2 = new_dp->pinfo[j].partition_size;
		/*
		 * Only change the offset, if the changed size is
		 * greater than the original size
		 */
		if (size1 < size2) {
			offset1 = dp->pinfo[i].partition_offset;
			offset2 = new_dp->pinfo[i].partition_offset;
			if (offset1 == offset2) {
				/*
				 * See whether the increase in size will still
				 * fit with the old offset value
				 */
				if (size2 + new_dp->pinfo[j].partition_offset >
				    offset2) {
					new_dp->pinfo[i].partition_offset =
					    new_dp->pinfo[j].partition_offset
					    + size2;
				}
			}
		}
	}

	/*
	 * Check whether each partition fits in the available space
	 */
	for (i = 1; i < FD_NUMPART; i++) {
		j = i-1;
		/*
		 * If the size is not changed, ignore the partition
		 */
		if (dp->pinfo[j].partition_size ==
		    new_dp->pinfo[j].partition_size) {
			continue;
		}
		/*
		 * If the part_size is 0, then the part is not used
		 * Get the max size for each partition.
		 * If the next partition size is 0, then the rest of the disk
		 * is available for this partition. Otherwise only the space
		 * between the current partition offset and next partition
		 * offset is available
		 */
		if (new_dp->pinfo[j].partition_size != 0) {
			/*
			 * If the offset of the next partition is 0, then
			 * it was not used before but the user modified the
			 * parts so that it needs to be validated.
			 */
			if (new_dp->pinfo[i].partition_offset != 0) {
				max_space = new_dp->pinfo[i].partition_offset
				    - new_dp->pinfo[j].partition_offset
				    - OVERHEAD_IN_MB;
			} else {
				max_space = dt->dinfo.disk_size - used
				    + new_dp->pinfo[j].partition_size
				    - OVERHEAD_IN_MB;
			}

			om_debug_print(OM_DBGLVL_INFO, "Max Space = %u\n",
			    max_space);

			if (new_dp->pinfo[j].partition_size  > max_space) {
				new_dp->pinfo[j].partition_size = max_space;
				om_set_error(OM_CONFIG_EXCEED_DISK_SIZE);
			}
		}
	}
	return (new_dp);
}

/*
 * om_duplicate_disk_partition_info
 * This function will allocate space and copy the disk_parts_t structure
 * passed as a parameter.
 * Input:	om_handle_t handle - The handle returned by
 *              om_initiate_target_discovery()
 *		disk_parts_t * - Pointer to disk_parts_t. Usually the return
 *		value from get_disk_partition_info().
 * Return:	disk_parts_t * - Pointer to disk_parts_t. Space will be
 *		allocated and the data is copied and returned.
 *		NULL, if space cannot be allocated.
 */
/*ARGSUSED*/
disk_parts_t *
om_duplicate_disk_partition_info(om_handle_t handle, disk_parts_t *dparts)
{
	disk_parts_t	*dp;

	if (dparts == NULL) {
		om_set_error(OM_BAD_INPUT);
		return (NULL);
	}

	/*
	 * Allocate space for partitions and copy data
	 */
	dp = (disk_parts_t *)calloc(1, sizeof (disk_parts_t));

	if (dp == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}

	(void) memcpy(dp, dparts, sizeof (disk_parts_t));
	dp->disk_name = strdup(dparts->disk_name);

	return (dp);
}

/*
 * om_set_disk_partition_info
 * This function will save the disk partition information passed by the
 * caller and use it for creating disk partitions during install.
 * This function should be used in conjunction with om_perform_install
 * If om_perform_install is not called, no changes in the disk will be made.
 *
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		disk_parts_t *dp - The modified disk partitions
 * Output:	None
 * Return:	OM_SUCCESS - If the disk partition infromation is saved
 *		OM_FAILURE - If the data cannot be saved.
 * Note:	If the partition information can't be saved, the om_errno
 *		will be set to the actual error condition. The error
 *		information can be obtained by calling om_get_errno().
 */
/*ARGSUSED*/
int
om_set_disk_partition_info(om_handle_t handle, disk_parts_t *dp)
{
	disk_target_t	*dt;
	disk_info_t	di;

	/*
	 * Validate the input
	 */
	if (dp == NULL || dp->disk_name == NULL) {
		om_set_error(OM_BAD_INPUT);
		return (OM_FAILURE);
	}

	/*
	 * Find the disk from the cache using the diskname
	 */
	dt = find_disk_by_name(dp->disk_name);

	if (dt == NULL) {
		return (OM_FAILURE);
	}

	if (dt->dparts == NULL) {
		/*
		 * Log the information that the disk partitions are not defined
		 * before the install started and GUI has defined the partitions
		 * and saving it with orchestrator to be used during install
		 */
		om_log_print("No disk partitions defined prior to install\n");
	}

	/*
	 * If the disk data (partitions and slices) are already committed
	 * before, free the data before saving the new disk data.
	 */
	if (committed_disk_target != NULL) {
		local_free_disk_info(&committed_disk_target->dinfo, B_FALSE);
		local_free_part_info(committed_disk_target->dparts);
		local_free_slice_info(committed_disk_target->dslices);
		free(committed_disk_target);
		committed_disk_target = NULL;
	}

	/*
	 * It looks like the partition information is okay
	 * so take a copy and save it to use during install
	 */
	committed_disk_target =
	    (disk_target_t *)calloc(1, sizeof (disk_target_t));
	if (committed_disk_target == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	di = dt->dinfo;
	if (di.disk_name != NULL) {
		committed_disk_target->dinfo.disk_name = strdup(di.disk_name);
	}
	committed_disk_target->dinfo.disk_size = di.disk_size;
	committed_disk_target->dinfo.disk_type = di.disk_type;
	if (di.vendor != NULL) {
		committed_disk_target->dinfo.vendor = strdup(di.vendor);
	}
	committed_disk_target->dinfo.boot_disk = di.boot_disk;
	committed_disk_target->dinfo.label = di.label;
	committed_disk_target->dinfo.removable = di.removable;
	if (di.serial_number != NULL) {
		committed_disk_target->dinfo.serial_number =
		    strdup(di.serial_number);
	}

	if (committed_disk_target->dinfo.disk_name == NULL ||
	    committed_disk_target->dinfo.vendor == NULL ||
	    committed_disk_target->dinfo.serial_number == NULL) {
		goto sdpi_return;
	}
	/*
	 * We are not dealing with slices in Dwarf
	 */
	committed_disk_target->dslices = NULL;

	/*
	 * Copy the partition data from the input
	 */
	committed_disk_target->dparts =
	    om_duplicate_disk_partition_info(handle, dp);
	if (committed_disk_target->dparts == NULL) {
		goto sdpi_return;
	}
	return (OM_SUCCESS);
sdpi_return:
	local_free_disk_info(&committed_disk_target->dinfo, B_FALSE);
	local_free_part_info(committed_disk_target->dparts);
	local_free_slice_info(committed_disk_target->dslices);
	free(committed_disk_target);
	committed_disk_target = NULL;
	return (OM_FAILURE);
}
