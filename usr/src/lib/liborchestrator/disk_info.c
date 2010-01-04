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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "orchestrator_private.h"

/*
 * Local functions
 */
static boolean_t copy_disk_info_data(disk_info_t *dest, disk_info_t *src);

/*
 * om_get_disk_info
 * This function will return the disk information of the discovered disks.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * Output:	int * total - Total number of disks returned.
 * Return:	The disk information will be returned as a pointer to
 *		disk_info_t. The space will be allocated by this function.
 *		NULL, if the disk data can't be returned.
 */
/*ARGSUSED*/
disk_info_t *
om_get_disk_info(om_handle_t handle, int *total)
{
	int		i;
	disk_target_t	*dt;
	disk_info_t	*di;
	disk_info_t	*disks;
	disk_info_t	*tmpdi;

	om_errno = 0;

	/*
	 * If the target discovery is not yet completed, set the
	 * error number and return NULL
	 */
	if (!disk_discovery_done) {
		om_set_error(OM_DISCOVERY_NEEDED);
		return (NULL);
	}

	if (system_disks  == NULL) {
		om_set_error(OM_NO_DISKS_FOUND);
		return (NULL);
	}

	tmpdi = NULL;
	disks = NULL;
	dt = system_disks;
	/*
	 * Copy the disk information from the orchestrator cache
	 */
	for (i = 0; (i < disks_total) && (dt != NULL); i++) {
		di = (disk_info_t *)calloc(1, sizeof (disk_info_t));
		if (di == NULL) {
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}

		/*
		 * Copy only the diskinfo portion from the Disk Target
		 * The Partition Information is provided once a disk is
		 * selected.
		 */
		if (!copy_disk_info_data(di, &dt->dinfo)) {
			om_set_error(OM_NO_SPACE);
			free(di);
			om_free_disk_info(handle, disks);
			return (NULL);
		}

		dt = dt->next;
		/*
		 * Link the node to the end of the diskinfo list
		 */
		if (tmpdi == NULL) {
			tmpdi = di;
			disks = tmpdi;
		} else {
			tmpdi->next = di;
			tmpdi = tmpdi->next;
		}
	}

	if (i != disks_total) {
		/* Log the information that we can't find all disks */
		disks_found = i;
	}

	*total = disks_total;
	return (disks);
}

/*
 * om_free_disk_info
 * This function will free up the disk information data allocated during
 * om_get_disk_info().
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		disk_info_t *dinfo - The pointer to disk_info_t. Usually
 *		returned by om_get_disk_info().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_disk_info(om_handle_t handle, disk_info_t *dinfo)
{
	boolean_t	follow_link = B_TRUE;

	om_errno = 0;
	if (dinfo == NULL) {
		return;
	}

	/*
	 * Traverse through link and delete all disk info
	 * if follow_link is set to true.
	 */
	local_free_disk_info(dinfo, follow_link);
}

/*
 * om_duplicate_disk_info
 * This function will allocate space and copy the disk_info_t structure
 * passed as a parameter.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		disk_info_t * - Pointer to disk_info_t. Usually the return
 *		value from get_disk_info().
 * Return:	disk_info_t * - Pointer to disk_info_t. Space will be
 *		allocated and the data is copied and returned.
 *		NULL, if space cannot be allocated.
 */
/*ARGSUSED*/
disk_info_t *
om_duplicate_disk_info(om_handle_t handle, disk_info_t *dinfo)
{
	disk_info_t	*di;
	disk_info_t	*dip;
	disk_info_t	*disks;
	disk_info_t	*tmpdi;

	om_errno = 0;

	if (dinfo == NULL) {
		om_set_error(OM_BAD_INPUT);
		return (NULL);
	}

	disks = NULL;
	tmpdi = NULL;
	/*
	 * Allocate space and copy
	 */
	for (dip = dinfo; dip != NULL; dip = dip->next) {
		di = (disk_info_t *)calloc(1, sizeof (disk_info_t));
		if (di == NULL) {
			om_set_error(OM_NO_SPACE);
			om_free_disk_info(handle, disks);
			return (NULL);
		}

		if (!copy_disk_info_data(di, dip)) {
			om_set_error(OM_NO_SPACE);
			free(di);
			om_free_disk_info(handle, disks);
			return (NULL);
		}

		/*
		 * Add the new element to the end of the linked list.
		 * Create the linked list if there are no elements.
		 */
		if (tmpdi == NULL) {
			tmpdi = di;
			disks = tmpdi;
		} else {
			tmpdi->next = di;
			tmpdi = tmpdi->next;
		}
	}
	return (disks);
}

/*
 * om_convert_linked_disk_info_to_array
 * This function converts the linked list of disks represented in disk_info_t to
 * an array of pointers so that each pointer will be pointed to the disk_info_t
 * of each disk.
 * Input:	disk_info_t * - The disk infomation structure represented by
 *		linked list of disk_info_t. It is the usually the value
 *		returned by om_get_disk_info().
 * 		int total - Total number of disks returned.
 * Return:	A array of pointers to disk_info_t
 */
/*ARGSUSED*/
disk_info_t **
om_convert_linked_disk_info_to_array(om_handle_t handle,
	disk_info_t *dinfo, int total)
{
	int		i = 0;
	disk_info_t	*di;
	disk_info_t	**di_array;

	om_errno = 0;

	if (dinfo  == NULL) {
		om_set_error(OM_BAD_INPUT);
		return (NULL);
	}

	/*
	 * Allocate an array of pointers so that each disk_info_t
	 * can be assigned to each element of the array
	 */
	di_array = (disk_info_t **)calloc(total, sizeof (disk_info_t *));
	if (di_array == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}

	/*
	 * Assign each disk_info_t to an element of array of pointers
	 */
	for (i = 0, di = dinfo; di != NULL; di = di->next, i++) {
		di_array[i] = di;
	}

	return (di_array);
}

/*
 * om_free_disk_info_array
 * This function will free up the disk array allocated by
 * om_convert_linked_disk_info_to_array()
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		disk_info_t **dinfo - The pointer to array of disk_info_t.
 *		Usually returned by om_convert_linked_disk_info_to_array().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_disk_info_array(om_handle_t handle, disk_info_t **di_array)
{
	if (di_array == NULL || *di_array == NULL) {
		return;
	}

	free(di_array);
}

/*
 * copy_disk_info_data
 * This function copies all the disk info data from source to destination
 */
/*ARGSUSED*/
static boolean_t
copy_disk_info_data(disk_info_t *dest, disk_info_t *src)
{
	if (src->disk_name) {
		dest->disk_name = strdup(src->disk_name);
	}

	if (src->disk_volname) {
		dest->disk_volname = strdup(src->disk_volname);
	}
	if (src->disk_devid) {
		dest->disk_devid = strdup(src->disk_devid);
	}
	if (src->disk_device_path) {
		dest->disk_device_path = strdup(src->disk_device_path);
	}

	dest->disk_size = src->disk_size;
	dest->disk_size_total =  src->disk_size_total;
	dest->disk_type = src->disk_type;
	if (src->vendor) {
		dest->vendor = strdup(src->vendor);
	}
	dest->boot_disk = src->boot_disk;
	dest->label = src->label;
	dest->removable = src->removable;
	if (src->serial_number) {
		dest->serial_number = strdup(src->serial_number);
	}

	/*
	 * Check whether any of the strdup call failed
	 */
	if (dest->disk_name == NULL || dest->vendor == NULL ||
	    dest->serial_number == NULL || dest->disk_devid == NULL ||
	    dest->disk_device_path == NULL) {
		free(dest->disk_name);
		free(dest->disk_volname);
		free(dest->disk_devid);
		free(dest->disk_device_path);
		free(dest->vendor);
		free(dest->serial_number);
		return (B_FALSE);
	}
	dest->next = NULL;
	return (B_TRUE);
}

/*
 * om_get_boot_disk
 *
 * Searches linked list of discovered disks for boot disk. It assumes that
 * target discovery was done.
 *
 * Input:	disk_list - linked list of discvovered disks
 *
 * Return:	NULL if boot disk was not found, otherwise pointer to
 *		boot disk disk_info_t structure
 */
disk_info_t *
om_get_boot_disk(disk_info_t *disk_list)
{
	disk_info_t	*di;

	/* Walk through the list of disks and search for boot disk */

	for (di = disk_list; di != NULL; di = di->next) {
		if (di->boot_disk)
			break;
	}

	return (di);
}

/*
 * om_find_disk_by_ctd_name
 *
 * Searches linked list of discovered disks for disk with given c#t#d# name.
 * It assumes that target discovery was done.
 *
 * Input:	disk_list - linked list of discvovered disks
 *
 * Return:	NULL if disk was not found, otherwise pointer to
 *		disk disk_info_t structure
 */
disk_info_t *
om_find_disk_by_ctd_name(disk_info_t *disk_list, char *ctd_name)
{
	disk_info_t	*di;

	/* Walk through the list of disks and search for required disk */

	for (di = disk_list; di != NULL; di = di->next) {
		if (strcmp(di->disk_name, ctd_name) == 0)
			break;
	}

	return (di);
}
