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

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <pthread.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <sys/wait.h>
#include <crypt.h>
#include <unistd.h>
#include <time.h>
#include <libgen.h>
#include <netdb.h>
#include <locale.h>

#include "orchestrator_private.h"

/*
 * slim_set_fdisk_attrs
 * This function sets the appropriate fdisk attributes for target instantiation.
 * Input:	nvlist_t *target_attrs - list to add attributes to
 * Output:	None
 * Return:	errno - see orchestrator_api.h
 */
int
slim_set_fdisk_attrs(nvlist_t *list, char *diskname)
{
	disk_target_t	*dt;
	disk_parts_t	*cdp;
	int		i;
	boolean_t	preserve_all;

	uint8_t		part_ids[OM_NUMPART], part_active_flags[OM_NUMPART];
	uint64_t	part_offsets[OM_NUMPART], part_sizes[OM_NUMPART];
	boolean_t	preserve_array[OM_NUMPART];

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

			part_ids[pos] = part_active_flags[pos] =
			    part_offsets[pos] = part_sizes[pos] = 0;
		} else {
			part_ids[pos] = type_new;
			part_active_flags[pos] = 0;
			part_offsets[pos] = cdp->pinfo[i].partition_offset_sec;
			part_sizes[pos] = cdp->pinfo[i].partition_size_sec;
		}
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


/*
 * slim_set_slice_attrs
 * This function sets the appropriate slice and attributes for target
 * instaniation.
 * Input:	nvlist_t *target_attrs - list to add attributes to
 * Output:	None
 * Return:	errno - see orchestartor_api.h
 *
 * Notes: 	The Default layout will be based on size of the disk/partition
 * Disk size		swap		root pool
 * =========================================================================
 *  4 GB - 10 GB	0.5G		Rest
 * 10 GB - 20 GB	1G		Rest
 * 20 GB - 30 Gb	2G		Rest
 * > 30 GB		2G		Rest
 */
int
slim_set_slice_attrs(nvlist_t *list, char *diskname)
{
	/*
	 * set target type
	 */

	if (nvlist_add_uint32(list, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_VTOC) != 0) {
		(void) om_log_print("Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");
		goto error;
	}

	/*
	 * set disk name
	 */
	if (nvlist_add_string(list, TI_ATTR_SLICE_DISK_NAME,
	    diskname) != 0) {
		om_log_print("Couldn't add TI_ATTR_SLICE_DISK_NAME to"
		    "nvlist\n");
		goto error;
	}

	/*
	 * Set the default to use the  whole partition as the slice.
	 */
	if (nvlist_add_boolean_value(list, TI_ATTR_SLICE_DEFAULT_LAYOUT,
	    B_TRUE) != 0) {
		om_log_print("Couldn't set whole partition attribute\n");
		goto error;
	}

	om_set_error(OM_SUCCESS);
	return (OM_SUCCESS);
error:
	om_set_error(OM_TARGET_INSTANTIATION_FAILED);
	return (-1);
}
