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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "orchestrator_private.h"

boolean_t	whole_disk = B_FALSE; /* assume existing partition */

static void log_partition_map();


/* ----------------- definition of private functions ----------------- */

/*
 * is_resized_partition
 * This function checks if partition size changed
 *
 * Input:	pold, pnew - pointer to the old and new partition entries
 *
 * Return:	B_TRUE - partition was resized
 *		B_FALSE - partition size not chnged
 */

static boolean_t
is_resized_partition(partition_info_t *pold, partition_info_t *pnew)
{
	return (pold->partition_size != pnew->partition_size);
}


/*
 * is_changed_partition
 * This function checks if partition changed. It means that
 * [1] size changed OR
 * [2] type changed for used partition (size is not 0)
 *
 * Input:	pold, pnew - pointer to the old and new partition entries
 *
 * Return:	B_TRUE - partition was resized
 *		B_FALSE - partition size not chnged
 */

static boolean_t
is_changed_partition(partition_info_t *pold, partition_info_t *pnew)
{
	return (is_resized_partition(pold, pnew) ||
	    (pold->partition_type != pnew->partition_type &&
	    pnew->partition_size != 0));
}


/*
 * is_deleted_partition
 * This function checks if partition was deleted
 *
 * Input:	pold, pnew - pointer to the old and new partition entries
 *
 * Return:	B_TRUE - partition was deleted
 *		B_FALSE - partition was not deleted
 */

static boolean_t
is_deleted_partition(partition_info_t *pold, partition_info_t *pnew)
{
	return (pold->partition_size != 0 && pnew->partition_size == 0);
}


/*
 * is_created_partition
 * This function checks if partition was created
 *
 * Input:	pold, pnew - pointer to the old and new partition entries
 *
 * Return:	B_TRUE - partition was created
 *		B_FALSE - partition already existed
 */

static boolean_t
is_created_partition(partition_info_t *pold, partition_info_t *pnew)
{
	return (pold->partition_size == 0 && pnew->partition_size != 0);
}


/*
 * is_used_partition
 * This function checks if partition_info_t structure
 * describes used partition entry.
 *
 * Entry is considered to be used if
 * [1] partition size is greater than 0
 * [2] type is not set to unused - id 0 or 100
 *
 * Input:	pentry - pointer to the partition entry
 *
 * Return:	B_TRUE - partition entry is in use
 *		B_FALSE - partition entry is empty
 */

static boolean_t
is_used_partition(partition_info_t *pentry)
{
	return (pentry->partition_type != 0 &&
	    pentry->partition_type != UNUSED);
}

/*
 * set_partition_unused
 * This function sets partition entry as unused
 *
 * Input:	pentry - pointer to the partition entry
 */

static void
set_partition_unused(partition_info_t *pentry)
{
	bzero(pentry, sizeof (*pentry));
	pentry->partition_type = UNUSED;
	pentry->partition_size = 0;
	pentry->partition_size_sec = 0;
}

/*
 * get_first_used_partition
 * This function will search array of partition_info_t structures
 * and will find the first used entry
 *
 * see is_used_partition() for how emtpy partition is defined
 *
 * Input:	pentry - pointer to the array of partition entries
 *
 * Output:	None
 *
 * Return:	>=0	- index of first used partition entry
 *		-1	- array contains only empty entries
 */

static int
get_first_used_partition(partition_info_t *pentry)
{
	int i;

	for (i = 0; i < OM_NUMPART; i++) {
		if (is_used_partition(&pentry[i]))
			return (i);
	}

	return (-1);
}

/*
 * get_last_used_partition
 * This function will search array of partition_info_t structures
 * and will find the last used entry
 *
 * see is_used_partition() for how empty partition is defined
 *
 * Input:	pentry - pointer to the array of partition entries
 *
 * Output:	None
 *
 * Return:	>=0	- index of first used partition entry
 *		-1	- array contains only empty entries
 */

static int
get_last_used_partition(partition_info_t *pentry)
{
	int i;

	for (i = OM_NUMPART - 1; i >= 0; i--) {
		if (is_used_partition(&pentry[i]))
			return (i);
	}

	return (-1);
}

/*
 * get_next_used_partition
 * This function will search array of partition_info_t structures
 * and will find the next used entry
 *
 * Input:	pentry - pointer to the array of partition entries
 *		current - current index
 *
 * Output:	None
 *
 * Return:	>=0	- index of next used partition entry
 *		-1	- no more used entries
 */

static int
get_next_used_partition(partition_info_t *pentry, int current)
{
	int i;

	for (i = current + 1; i < OM_NUMPART; i++) {
		if (is_used_partition(&pentry[i]))
			return (i);
	}

	return (-1);
}


/*
 * get_previous_used_partition
 * This function will search array of partition_info_t structures
 * and will find the previous used entry
 *
 * Input:	pentry - pointer to the array of partition entries
 *		current - current index
 *
 * Output:	None
 *
 * Return:	>=0	- index of next used partition entry
 *		-1	- no more used entries
 */

static int
get_previous_used_partition(partition_info_t *pentry, int current)
{
	int i;

	for (i = current - 1; i >= 0; i--) {
		if (is_used_partition(&pentry[i]))
			return (i);
	}

	return (-1);
}


/*
 * is_first_used_partition
 * This function checks if index points
 * to the first used partition entry.
 *
 * Input:	pentry	- pointer to the array of partition entries
 *		index	- index of partition to be checked
 *
 * Return:	B_TRUE - partition entry is in use
 *		B_FALSE - partition entry is empty
 */

static boolean_t
is_first_used_partition(partition_info_t *pentry, int index)
{
	return (get_first_used_partition(pentry) == index);
}

/*
 * is_last_used_partition
 * This function checks if index points to
 * the last used partition entry.
 *
 * Input:	pentry	- pointer to the array of partition entries
 *		index	- index of partition to be checked
 *
 * Return:	B_TRUE - partition entry is in use
 *		B_FALSE - partition entry is empty
 */

static boolean_t
is_last_used_partition(partition_info_t *pentry, int index)
{
	return (get_last_used_partition(pentry) == index ?
	    B_TRUE : B_FALSE);
}

static void
log_partition_map()
{
	int ipar;
	partition_info_t *pinfo;

	pinfo = committed_disk_target->dparts->pinfo;
	om_debug_print(OM_DBGLVL_INFO,
	    "id\ttype\tsector offset\tsize in sectors\n");
	for (ipar = 0; ipar < OM_NUMPART; ipar++) {
		om_debug_print(OM_DBGLVL_INFO, "%d\t%02X\t%lld\t%lld\n",
		    pinfo[ipar].partition_id,
		    pinfo[ipar].partition_type,
		    pinfo[ipar].partition_offset_sec,
		    pinfo[ipar].partition_size_sec);
	}
}

/* ----------------- definition of public functions ----------------- */

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
	boolean_t	changed = B_FALSE;
	disk_target_t	*dt;
	disk_parts_t	*dp, *new_dp;
	int		i;

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
		om_set_error(OM_BAD_DISK_NAME);
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
	 * check if "whole disk" path was selected. It is true if
	 * both following conditions are met:
	 * [1] Only first partition is defined. Rest are left unused
	 *	(size ==0 &&, type == 100)
	 * [2] First partition is Solaris2 and occupies all available space
	 */

	whole_disk = B_TRUE;

	if ((new_dp->pinfo[0].partition_size != dt->dinfo.disk_size) ||
	    (new_dp->pinfo[0].partition_type != SUNIXOS2)) {
		om_debug_print(OM_DBGLVL_INFO, "entire disk not used\n");
		whole_disk = B_FALSE;
	}

	for (i = 1; i < OM_NUMPART && whole_disk == B_TRUE; i++) {
		if ((new_dp->pinfo[i].partition_size != 0) ||
		    is_used_partition(&new_dp->pinfo[i])) {
			om_debug_print(OM_DBGLVL_INFO,
			    "Entire disk not used\n");
			whole_disk = B_FALSE;
		}
	}

	if (whole_disk) {
		return (new_dp);
	}

	/*
	 * if target disk is empty (there are no partitions defined),
	 * create dummy partition configuration. This allows using
	 * unified code for dealing with partition changes.
	 */

	if (dt->dparts == NULL) {
		om_log_print("disk currently doesn't contain any partition\n");

		dp = om_duplicate_disk_partition_info(handle, dpart);

		if (dp == NULL) {
			om_log_print("Couldn't duplicate partition info\n");
			return (NULL);
		}

		(void) memset(dp->pinfo, 0, sizeof (partition_info_t) *
		    OM_NUMPART);
	} else
		dp = dt->dparts;

	/*
	 * Compare the size and partition type (for used partition)
	 * of each partition to decide whether any of them was changed.
	 */

	for (i = 0; i < OM_NUMPART; i++) {
		if (is_changed_partition(&dp->pinfo[i], &new_dp->pinfo[i])) {
			om_log_print("disk partition info changed\n");
			changed = B_TRUE;
			break;
		}
	}

	if (!changed) {
		/*
		 * No change in the partition table.
		 */
		om_log_print("disk partition info not changed\n");

		/* release partition info if allocated if this function */
		if (dt->dparts == NULL)
			local_free_part_info(dp);

		return (new_dp);
	}

	/*
	 * Finally calculate sector geometry information for changed
	 * partitions
	 */

	om_debug_print(OM_DBGLVL_INFO,
	    "Partition LBA information before recalculation\n");

	for (i = 0; i < OM_NUMPART; i++) {
		om_debug_print(OM_DBGLVL_INFO,
		    "[%d] pos=%d, id=%02X, beg=%lld, size=%lld(%ld MiB)\n", i,
		    new_dp->pinfo[i].partition_id,
		    new_dp->pinfo[i].partition_type,
		    new_dp->pinfo[i].partition_offset_sec,
		    new_dp->pinfo[i].partition_size_sec,
		    new_dp->pinfo[i].partition_size);
	}

	for (i = 0; i < OM_NUMPART; i++) {
		partition_info_t	*p_orig = &dp->pinfo[i];
		partition_info_t	*p_new = &new_dp->pinfo[i];

		/*
		 * If the partition was not resized, skip it, since
		 * other modifications (change of type) don't require
		 * offset & size recalculation
		 */

		if (!is_resized_partition(p_orig, p_new))
			continue;

		/*
		 * If partition is deleted (marked as "UNUSED"),
		 * clear offset and size
		 */

		if (is_deleted_partition(p_orig, p_new)) {
			om_debug_print(OM_DBGLVL_INFO,
			    "Partition pos=%d, type=%02X is deleted\n",
			    p_orig->partition_id,
			    p_orig->partition_type);

			p_new->partition_offset_sec =
			    p_new->partition_size_sec = 0;

			/*
			 * don't clear partition_id - it is "read only"
			 * from orchestrator point of view - modified by GUI
			 */
			continue;
		}

		if (is_created_partition(p_orig, p_new)) {
			om_debug_print(OM_DBGLVL_INFO,
			    "Partition pos=%d, type=%02X is created\n",
			    p_new->partition_id, p_new->partition_type);
		}

		/*
		 * Calculate sector offset information
		 *
		 * Gaps are not allowed for now - partition starts
		 * right after previous used partition
		 *
		 * If this is the first partition, it starts at the
		 * first cylinder - adjust size accordingly
		 */

		if (is_first_used_partition(new_dp->pinfo, i)) {
			p_new->partition_offset_sec = dt->dinfo.disk_cyl_size;
			p_new->partition_size -=
			    dt->dinfo.disk_cyl_size/BLOCKS_TO_MB;

			om_debug_print(OM_DBGLVL_INFO,
			    "%d (%02X) is the first partition - "
			    "will start at the 1st cylinder (sector %lld)\n",
			    i, p_new->partition_type,
			    p_new->partition_offset_sec);
		} else {
			partition_info_t	*p_prev;
			int			previous;

			previous = get_previous_used_partition(new_dp->pinfo,
			    i);

			/*
			 * previous should be always found, since check for
			 * "first used" was done in if() statement above
			 */

			assert(previous != -1);
			p_prev = &new_dp->pinfo[previous];

			p_new->partition_offset_sec =
			    p_prev->partition_offset_sec +
			    p_prev->partition_size_sec;

		}

		/*
		 * user changed partition size in GUI or size
		 * was adjusted above.
		 * Calculate new sector size information from megabytes
		 */

		om_set_part_sec_size_from_mb(p_new);

		/*
		 * If the partition overlaps with subsequent one
		 * which is in use and that partition was not changed,
		 * adjust size accordingly.
		 *
		 * If subsequent used partition was resized as well, its
		 * offset and size will be adjusted in next step, so
		 * don't modify size of current partition.
		 *
		 * If this is the last used partition, adjust its size
		 * so that it fits into available disk space
		 */

		if (!is_last_used_partition(new_dp->pinfo, i)) {
			partition_info_t	*p_next_orig, *p_next_new;
			int			next;

			next = get_next_used_partition(new_dp->pinfo, i);

			/*
			 * next should be always found, since check for
			 * "last used" was done in if() statement above
			 */

			assert(next != -1);
			p_next_orig = &dp->pinfo[next];
			p_next_new = &new_dp->pinfo[next];

			/*
			 * next partition was resized, adjust rather that one,
			 * leave current one as is
			 */

			if (is_resized_partition(p_next_orig, p_next_new))
				continue;

			if ((p_new->partition_offset_sec +
			    p_new->partition_size_sec) >
			    p_next_new->partition_offset_sec) {
				p_new->partition_size_sec =
				    p_next_new->partition_offset_sec -
				    p_new->partition_offset_sec;

				/*
				 * partition sector size was adjusted.
				 * Recalculate size in MiB as well
				 */

				om_set_part_mb_size_from_sec(p_new);

				om_debug_print(OM_DBGLVL_INFO,
				    "Partition %d (ID=%02X) overlaps with "
				    "subsequent partition, "
				    "size will be adjusted to %d MB", i,
				    p_new->partition_type,
				    p_new->partition_size);
			}
		} else if ((p_new->partition_offset_sec +
		    p_new->partition_size_sec) > dt->dinfo.disk_size_sec) {
			p_new->partition_size_sec =
			    dt->dinfo.disk_size_sec -
			    p_new->partition_offset_sec;

			/*
			 * sector size of last used partition was adjusted.
			 * Recalculate size in MiB as well
			 */

			om_set_part_mb_size_from_sec(p_new);

			om_debug_print(OM_DBGLVL_INFO,
			    "Partition %d (ID=%02X) exceeds disk size, "
			    "size will be adjusted to %d MB\n", i,
			    p_new->partition_type,
			    p_new->partition_size);
		}
	}

	om_debug_print(OM_DBGLVL_INFO,
	    "Adjusted partition LBA information\n");

	for (i = 0; i < OM_NUMPART; i++) {
		om_debug_print(OM_DBGLVL_INFO,
		    "[%d] pos=%d, id=%02X, beg=%lld, size=%lld(%ld MiB)\n", i,
		    new_dp->pinfo[i].partition_id,
		    new_dp->pinfo[i].partition_type,
		    new_dp->pinfo[i].partition_offset_sec,
		    new_dp->pinfo[i].partition_size_sec,
		    new_dp->pinfo[i].partition_size);
	}

	/* release partition info if allocated if this function */

	if (dt->dparts == NULL)
		local_free_part_info(dp);

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
	if (committed_disk_target != NULL &&
	    strcmp(committed_disk_target->dinfo.disk_name, dt->dinfo.disk_name)
	    != 0) {
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
	if (committed_disk_target == NULL) {
		committed_disk_target =
		    (disk_target_t *)calloc(1, sizeof (disk_target_t));
		if (committed_disk_target == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}
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
	 * Copy the partition data from the input
	 */
	committed_disk_target->dparts =
	    om_duplicate_disk_partition_info(handle, dp);
	if (committed_disk_target->dparts == NULL) {
		goto sdpi_return;
	}
	/* finishing set partition info */
	log_partition_map();
	return (OM_SUCCESS);
sdpi_return:
	local_free_disk_info(&committed_disk_target->dinfo, B_FALSE);
	local_free_part_info(committed_disk_target->dparts);
	local_free_slice_info(committed_disk_target->dslices);
	free(committed_disk_target);
	committed_disk_target = NULL;
	return (OM_FAILURE);
}

/*
 * Partition editing suite
 *
 * These functions start with a description of existing partitions
 * To find partitions for a disk:
 *	-perform Target Discovery, finding disks and partitions for the disk
 *	-get partition table for disk with om_get_disk_partition_info()
 *	-if partitions exist (not NULL), set target disk information with
 *		om_set_disk_partition_info()
 *	-if no partitions exist (NULL) , create empty partition table with
 *		om_init_disk_partition_info()
 * The partition descriptions can then be edited with:
 *	om_create_partition(), om_delete_partition()
 * When new partition configuration is complete, finalize it for TI with:
 *	om_finalize_fdisk_info_for_TI()
 * Set attribute list for TI with:
 *	om_set_fdisk_target_attrs()
 *
 * om_create_partition() - create a new partition
 * partition_size_sec - size of partition in sectors
 * partition_offset_sec - offset of begininng sector
 * use_entire_disk - if true, ignore size, offset and commit entire disk
 * only Solaris partitions are created
 * returns B_TRUE if success, B_FALSE otherwise
 */
boolean_t
om_create_partition(uint64_t partition_offset_sec, uint64_t partition_size_sec,
    boolean_t use_entire_disk)
{
	disk_parts_t *dparts;
	partition_info_t *pinfo;
	int ipart;

	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dparts != NULL);

	dparts = committed_disk_target->dparts;
	pinfo = committed_disk_target->dparts->pinfo;
	for (ipart = 0; ipart < FD_NUMPART; ipart++, pinfo++) {
		if (partition_offset_sec == pinfo->partition_offset_sec &&
		    pinfo->partition_size_sec != 0) { /* part already exists */
			om_debug_print(OM_DBGLVL_ERR, "Attempting to "
			    "create partition that already exists\n");
			om_set_error(OM_ALREADY_EXISTS);
			return (B_FALSE);
		}
	}
	/* find free entry */
	pinfo = committed_disk_target->dparts->pinfo; /* reset */
	for (ipart = 0; ipart < FD_NUMPART; ipart++, pinfo++)
		if (!is_used_partition(pinfo))
			break;
	if (ipart >= FD_NUMPART) {
		om_set_error(OM_BAD_INPUT);
		return (B_FALSE);
	}

	if (use_entire_disk) {
		partition_offset_sec = 0;
		partition_size_sec =
		    committed_disk_target->dinfo.disk_size * BLOCKS_TO_MB;
	}
	/* if size set to 0 in manifest, take entire disk */
	if (partition_size_sec == 0)
		partition_size_sec =
		    ((uint64_t)committed_disk_target->dinfo.disk_size *
		    (uint64_t)BLOCKS_TO_MB);

	om_debug_print(OM_DBGLVL_INFO, "adding partition in slot %d\n", ipart);
	pinfo->partition_id = ipart + 1;
	pinfo->partition_offset_sec = partition_offset_sec;
	pinfo->partition_offset = pinfo->partition_offset_sec / BLOCKS_TO_MB;
	pinfo->partition_size_sec = partition_size_sec;
	pinfo->partition_size = pinfo->partition_size_sec / BLOCKS_TO_MB;
	pinfo->content_type = OM_CTYPE_SOLARIS;
	pinfo->partition_type = SUNIXOS2;	/* Solaris */
	om_debug_print(OM_DBGLVL_INFO,
	    "will create Solaris partition of size=%lld offset=%lld\n",
	    pinfo->partition_size_sec, pinfo->partition_offset_sec);

	om_debug_print(OM_DBGLVL_INFO, "new partition info:\n");
	log_partition_map();
	return (B_TRUE);
}

/*
 * om_delete_partition() - delete an existing partition
 * partition_size_sec - size of partition in sectors
 * partition_offset_sec - offset of begininng sector
 * returns B_TRUE if success, B_FALSE otherwise
 */
boolean_t
om_delete_partition(uint64_t partition_offset_sec, uint64_t partition_size_sec)
{
	disk_parts_t *dparts;
	int ipart;

	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dparts != NULL);
	dparts = committed_disk_target->dparts;
	om_debug_print(OM_DBGLVL_INFO,
	    "deleting partition: offset=%lld size=%lld\n",
	    partition_offset_sec, partition_size_sec);
	for (ipart = 0; ipart < FD_NUMPART; ipart++) {
		om_debug_print(OM_DBGLVL_INFO,
		    "ipart=%d offset=%lld size=%lld\n",
		    ipart, dparts->pinfo[ipart].partition_offset_sec,
		    dparts->pinfo[ipart].partition_size_sec);
		if (partition_offset_sec ==
		    dparts->pinfo[ipart].partition_offset_sec &&
		    partition_size_sec ==
		    dparts->pinfo[ipart].partition_size_sec) {

			int ip;

			om_debug_print(OM_DBGLVL_INFO, "match - deleting\n");
			for (ip = 0; ip < FD_NUMPART; ip++)
				om_debug_print(OM_DBGLVL_INFO,
				    "pre-delete dump[%d]: part_id=%d size=%d\n",
				    ip, dparts->pinfo[ip].partition_id,
				    dparts->pinfo[ip].partition_size);
			memcpy(&dparts->pinfo[ipart], /* shift rest up by one */
			    &dparts->pinfo[ipart + 1],
			    (FD_NUMPART - ipart - 1) *
			    sizeof (partition_info_t));
			/* clear last entry */
			set_partition_unused(&dparts->pinfo[FD_NUMPART - 1]);
			/* renumber partition IDs */
			for (ip = 0; ip < FD_NUMPART; ip++)
				if (is_used_partition(&dparts->pinfo[ip]))
					dparts->pinfo[ip].partition_id =
					    ip+1;

			for (ip = 0; ip < FD_NUMPART; ip++)
				om_debug_print(OM_DBGLVL_INFO,
				    "post-delete dump: part_id=%d size=%d\n",
				    dparts->pinfo[ip].partition_id,
				    dparts->pinfo[ip].partition_size);
			return (B_TRUE);
		}
	}
	om_debug_print(OM_DBGLVL_ERR,
	    "Failed to locate specified partition to delete at starting sector "
	    "%lld with size in sectors=%lld\n",
	    partition_offset_sec, partition_size_sec);
	om_set_error(OM_BAD_INPUT);
	return (B_FALSE);
}

/*
 * om_finalize_fdisk_info_for_TI() - write out partition table containing edits
 * performs adjustments to layout:
 *	-eliminate use of first cylinder for x86
 *	-eliminate overlapping
 * returns B_TRUE if success, B_FALSE otherwise
 * side effect: may modify target disk partition info
 */
boolean_t
om_finalize_fdisk_info_for_TI()
{
	disk_parts_t *dparts = committed_disk_target->dparts;
	disk_parts_t *newdparts;

	assert(committed_disk_target->dinfo.disk_name != NULL);

	newdparts = om_validate_and_resize_disk_partitions(0, dparts);
	if (newdparts == NULL) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Partition information is invalid\n");
		return (B_FALSE);
	}
	committed_disk_target->dparts = newdparts;
	om_debug_print(OM_DBGLVL_INFO,
	    "om_finalize_fdisk_info_for_TI:%s partition 0 %ld MB disk %ld MB\n",
	    whole_disk ? "entire disk":"",
	    dparts->pinfo[0].partition_size,
	    committed_disk_target->dinfo.disk_size);
	log_partition_map();
	return (B_TRUE);
}

/*
 * set disk partition info initially for no partitions
 * allocate on heap
 * given disk name, set all partitions empty
 * return pointer to disk partition info
 * return NULL if memory allocation failure
 */
disk_parts_t *
om_init_disk_partition_info(disk_info_t *di)
{
	char *disk_name;
	disk_parts_t *dp;
	int i;

	disk_name = di->disk_name;
	assert(disk_name != NULL);

	dp = calloc(1, sizeof (disk_parts_t));
	if (dp == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	dp->disk_name = strdup(disk_name);
	if (dp->disk_name == NULL) {
		free(dp);
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	/* mark all unused */
	for (i = 0; i < OM_NUMPART; i++)
		set_partition_unused(&dp->pinfo[i]);
	return (dp);
}

/*
 * om_create_target_partition_info_if_absent(): initialize a target disk
 *	partition struct if not yet initialized
 * This was designed for the case of no partition table on disk and no
 *	customizations were provided by the user
 * side effect: if no target disk partitions have been found or specified,
 *	initialize the target disk information to use the entire target disk
 *	for a single partition
 */
void
om_create_target_partition_info_if_absent()
{
	partition_info_t *pinfo;
	disk_info_t *di;

	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dparts != NULL);

	pinfo = committed_disk_target->dparts->pinfo;
	if (is_used_partition(pinfo)) /* if partition 1 is in use, */
		return;	/* target partition table has already initialized */
	om_debug_print(OM_DBGLVL_INFO,
	    "No partition info - Creating target disk partition table - "
	    "use entire target disk\n");
	/* mark first partition to be Solaris2 */
	di = &committed_disk_target->dinfo;
	pinfo->partition_id = 1;
	pinfo->content_type = OM_CTYPE_SOLARIS;
	pinfo->partition_type = SUNIXOS2;
	pinfo->partition_size = di->disk_size;
	pinfo->partition_size_sec = di->disk_size * BLOCKS_TO_MB;
}

/*
 * om_set_fdisk_target_attrs
 * This function sets the appropriate fdisk attributes for target instantiation.
 * Input:	nvlist_t *target_attrs - list to add attributes to
 * Output:	None
 * Return:	errno - see orchestrator_api.h
 */
int
om_set_fdisk_target_attrs(nvlist_t *list, char *diskname)
{
	disk_target_t	*dt;
	disk_parts_t	*cdp;
	int		i;
	boolean_t	preserve_all;

	uint8_t		part_ids[OM_NUMPART], part_active_flags[OM_NUMPART];
	uint64_t	part_offsets[OM_NUMPART], part_sizes[OM_NUMPART];
	boolean_t	preserve_array[OM_NUMPART];
	partition_info_t	*install_partition = NULL;

	om_set_error(OM_SUCCESS);

	/*
	 * We have all the data from the GUI committed at this point.
	 * Gather it, and set the attributes.
	 */

	for (dt = system_disks; dt != NULL; dt = dt->next) {
		if (streq(dt->dinfo.disk_name, diskname)) {
			break;
		}
	}

	if (dt == NULL) {
		om_log_print("Bad target disk name\n");
		om_set_error(OM_BAD_DISK_NAME);
		return (-1);
	}

	if (committed_disk_target == NULL) {
		om_log_print("Disk is not changed\n");
		preserve_all = B_TRUE;

		/*
		 * No existing partitions and No new partitions.
		 * we can't proceed with install
		 */
		if (dt->dparts == NULL) {
			om_log_print("Disk is empty - doesn't contain "
			    "partitions\n");

			om_set_error(OM_NO_PARTITION_FOUND);
			return (-1);
		}

		cdp = dt->dparts;
	} else {
		om_log_print("Disk was changed\n");
		preserve_all = B_FALSE;

		if (committed_disk_target->dparts == NULL) {
			om_log_print("Configuration of new partitions not "
			    "available\n");

			om_set_error(OM_NO_PARTITION_FOUND);
			return (-1);
		}

		cdp = committed_disk_target->dparts;
	}

	/*
	 * Make sure that there is a Solaris or Solaris 2 partition.
	 */

	for (i = 0; i < OM_NUMPART; i++) {
		if (cdp->pinfo[i].partition_type == SUNIXOS2 ||
		    (cdp->pinfo[i].partition_type == SUNIXOS &&
		    cdp->pinfo[i].content_type != OM_CTYPE_LINUXSWAP)) {
			om_log_print("Disk contains valid Solaris partition\n");

			/*
			 * Check whether the partition type is legacy Solaris
			 * (SUNIXOS) or new Solaris2 (SUNIXOS2). If it is
			 * SUNIXOS, convert it to SUNIXOS2.
			 */
			if (cdp->pinfo[i].partition_type == SUNIXOS) {
				om_log_print(
				    "Disk contains legacy Solaris partition. "
				    "It will be converted to Solaris2\n");

				/*
				 * If user didn't make any changes to the
				 * original partition configuration
				 * (committed_disk_target == NULL), it
				 * is necessary to create a copy of the
				 * original partition configuration and
				 * change the partition type.
				 */

				if (committed_disk_target == NULL) {
					om_debug_print(OM_DBGLVL_INFO,
					    "committed_disk_target == NULL, "
					    "copy of original partition "
					    "configuration will be created\n");

					/*
					 * First parameter (handle) is
					 * currently unused, set to '0'
					 */
					if (om_set_disk_partition_info(0,
					    cdp) != OM_SUCCESS) {
						om_debug_print(OM_DBGLVL_ERR,
						    "Couldn't duplicate "
						    "partition "
						    "configuration\n");

						return (-1);
					}

					cdp = committed_disk_target->dparts;
				}

				cdp->pinfo[i].partition_type = SUNIXOS2;
				preserve_all = B_FALSE;
			}
			install_partition = &cdp->pinfo[i];
			break;
		}
	}

	/*
	 * No Solaris partition. Do not proceed
	 */

	if (i == OM_NUMPART) {
		om_log_print("Disk doesn't contain valid Solaris partition\n");

		om_set_error(OM_NO_PARTITION_FOUND);
		return (-1);
	}

	/*
	 * Solaris partition found - take a look at the partition size
	 * and decide, if there is enough space to create swap and
	 * dump devices
	 */

	om_debug_print(OM_DBGLVL_INFO,
	    "Recommended disk size is %llu MiB\n",
	    om_get_recommended_size(NULL, NULL));

	om_debug_print(OM_DBGLVL_INFO,
	    "Install partition size = %lu MiB\n",
	    install_partition != NULL ?
	    install_partition->partition_size : 0);

	if (install_partition == NULL) {
		om_debug_print(OM_DBGLVL_WARN,
		    "Couldn't obtain size of install partition, swap&dump "
		    "won't be created\n");

		create_swap_and_dump = B_FALSE;
	} else if (install_partition->partition_size <
	    om_get_recommended_size(NULL, NULL) - OVERHEAD_MB) {

		om_debug_print(OM_DBGLVL_INFO,
		    "Install partition is too small, swap&dump won't "
		    "be created\n");

		create_swap_and_dump = B_FALSE;
	} else {
		om_debug_print(OM_DBGLVL_INFO,
		    "Size of install partition is sufficient for creating "
		    "swap&dump\n");

		create_swap_and_dump = B_TRUE;
	}

	/*
	 * set target type
	 */

	if (nvlist_add_uint32(list, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_FDISK) != 0) {
		(void) om_log_print("Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	if (nvlist_add_string(list, TI_ATTR_FDISK_DISK_NAME,
	    diskname) != 0) {
		om_log_print("Couldn't add FDISK_DISK_NAME attr\n");

		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	if (nvlist_add_boolean_value(list, TI_ATTR_FDISK_WDISK_FL,
	    whole_disk) != 0) {
		om_log_print("Couldn't add WDISK_FL attr\n");

		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	om_log_print("whole_disk = %d\n", whole_disk);
	om_log_print("diskname set = %s\n", diskname);

	/*
	 * If "whole disk", no more attributes need to be set
	 */

	if (whole_disk)
		return (0);

	/* add number of partitions to be created */

	if (nvlist_add_uint16(list, TI_ATTR_FDISK_PART_NUM,
	    OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_NAME attr\n");

		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	/*
	 * if no changes should be done to fdisk partition table
	 * set "preserve" flag for all partitions
	 */

	if (preserve_all) {
		om_log_print("No changes will be done to the partition "
		    "table\n");

		for (i = 0; i < OM_NUMPART; i++)
			preserve_array[i] = B_TRUE;

		/* preserve flags */

		if (nvlist_add_boolean_array(list, TI_ATTR_FDISK_PART_PRESERVE,
		    preserve_array, OM_NUMPART) != 0) {
			om_log_print("Couldn't add FDISK_PART_PRESERVE attr\n");
			om_set_error(OM_NO_SPACE);
			return (-1);
		}

		return (0);
	}

	/*
	 * check whether disk partitions are changed for this install
	 * The caller should have called to commit the changes
	 */

	if (committed_disk_target->dparts == NULL) {
		return (-1);
	}

	/*
	 * The disk we got for install is different
	 * from the disk information committed before.
	 * So return error.
	 */

	if (!streq(diskname, committed_disk_target->dinfo.disk_name)) {
		return (-1);
	}

	/*
	 * Now find out the changed partitions
	 */

	cdp = committed_disk_target->dparts;

	om_debug_print(OM_DBGLVL_INFO,
	    "Commited partition LBA information\n");

	for (i = 0; i < OM_NUMPART; i++) {
		om_debug_print(OM_DBGLVL_INFO,
		    "[%d] pos=%d, id=%02X, beg=%lld, size=%lld(%ld MiB)\n", i,
		    cdp->pinfo[i].partition_id,
		    cdp->pinfo[i].partition_type,
		    cdp->pinfo[i].partition_offset_sec,
		    cdp->pinfo[i].partition_size_sec,
		    cdp->pinfo[i].partition_size);
	}

	/*
	 * Partitions are sorted by offset for now.
	 *
	 * For TI purposes sort partitions according to position
	 * in fdisk partition table.
	 */

	/*
	 * Mark all entries as unused and then fill in used positions
	 *
	 * Set ID to 100 for unused entries. Otherwise fdisk(1M)
	 * refuses to create partition table.
	 *
	 * Initially assume that nothing will be preserved.
	 */

	for (i = 0; i < OM_NUMPART; i++) {
		part_ids[i] = 100;
		part_active_flags[i] =
		    part_offsets[i] = part_sizes[i] = 0;

		preserve_array[i] = B_FALSE;
	}

	for (i = 0; i < OM_NUMPART; i++) {
		uint64_t	size_new = cdp->pinfo[i].partition_size;
		uint8_t		type_new = cdp->pinfo[i].partition_type;
		int		pos = cdp->pinfo[i].partition_id - 1;

		/* Skip unused entries */

		if (pos == -1 || size_new == 0)
			continue;

		/*
		 * If size and type didn't change, preserve the partition.
		 * "move" operation (only offset changed) is not supported.
		 */

		/*
		 * If disk had empty partition table, don't compare,
		 * just create the partition
		 */

		if ((dt->dparts != NULL) &&
		    (dt->dparts->pinfo[i].partition_size == size_new) &&
		    (dt->dparts->pinfo[i].partition_type == type_new)) {
			preserve_array[pos] = B_TRUE;
		}

		part_ids[pos] = type_new;
		part_active_flags[pos] = 0;
		part_offsets[pos] = cdp->pinfo[i].partition_offset_sec;
		part_sizes[pos] = cdp->pinfo[i].partition_size_sec;
	}

	/*
	 * Add partition geometry to the list of attributes
	 */

	/* ID */

	if (nvlist_add_uint8_array(list, TI_ATTR_FDISK_PART_IDS,
	    part_ids, OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_IDS attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	/* ACTIVE */

	if (nvlist_add_uint8_array(list, TI_ATTR_FDISK_PART_ACTIVE,
	    part_active_flags, OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_ACTIVE attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	/* offset */

	if (nvlist_add_uint64_array(list, TI_ATTR_FDISK_PART_RSECTS,
	    part_offsets, OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_RSECTS attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	/* size */

	if (nvlist_add_uint64_array(list, TI_ATTR_FDISK_PART_NUMSECTS,
	    part_sizes, OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_NUMSECTS attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	/* preserve flags */

	if (nvlist_add_boolean_array(list, TI_ATTR_FDISK_PART_PRESERVE,
	    preserve_array, OM_NUMPART) != 0) {
		om_log_print("Couldn't add FDISK_PART_PRESERVE attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}

	om_set_error(OM_SUCCESS);
	return (0);
}
