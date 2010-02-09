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
#include <errno.h>
#include <sys/param.h>
#include <sys/types.h>
#include <libnvpair.h>
#include "td_api.h"
#include "libdiskmgt.h"

#include "orchestrator_private.h"

static int offset_compare(const void *p1, const void *p2);
static	char	*get_solaris_release_string(nvlist_t *list, int slice);
static	char	*get_not_upgradeable_zone_list(nvlist_t *list);
static	char	*get_svm_components(nvlist_t *attr_list);

/*
 * start_td_disk_discovery
 * This function will call the target discovery module and populate
 * Orchestrator cache.
 * Output:	The number of devices discovered will be returned.
 * Return:	OM_SUCCESS, if the target discovery can be started successfully
 *		td_error, if the target discovery can't be started.
 */

int
start_td_disk_discover(int *ndisks)
{
	td_errno_t	ret;
	int		num;

	ret = td_discover(TD_OT_DISK, &num);
	if (ret) {
		/*
		 * If there are no disks on the system, return success
		 * so that orchestrator can set the correct error number
		 * for no disks
		 */
		if (ret == TD_E_NO_DEVICE) {
			om_debug_print(OM_DBGLVL_ERR,
			    "No disks on the system\n");
		} else {
			om_debug_print(OM_DBGLVL_ERR, "Can't discover disks\n");
			return (ret);
		}
	}

	*ndisks = num;
	return (OM_SUCCESS);
}

/*
 * get_td_disk_info_discover
 * This function will get the disk information from TD module and populate
 * Orchestrator cache.
 * Input:	Number of devices discovered
 *		Callback function to report progress to the caller
 * Output:	Number of disks that can be read
 * Return:	Linked list of disk_target_t with disk information filled out.
 */
disk_target_t *
get_td_disk_info_discover(int *ndisks, om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;
	int			i;
	int			num, bad;
	disk_target_t		*disks, *dt, *tmpdt;

	num = *ndisks;
	bad = 0;
	tmpdt = NULL;
	disks = NULL;

	/*
	 * if passed number of disks is not positive, there is no point
	 * in continuing the disk discovery
	 */
	if (num <= 0) {
		om_set_error(OM_NO_DISKS_FOUND);
		return (NULL);
	}

	/*
	 * Initialize the fixed values for disk info discover callback
	 */
	if (cb != NULL) {
		cb_data.callback_type = OM_TARGET_TARGET_DISCOVERY;
		cb_data.num_milestones = 4;
		cb_data.curr_milestone = OM_DISK_DISCOVERY;
	}

	for (i = 1; i <= num; i++) {
		/*
		 * Get the disk information
		 */
		dt = enumerate_next_disk();
		/*
		 * We are not getting disk_info for a disk
		 * So don't count this disk.
		 */
		if (dt == NULL) {
			bad++;
			continue;
		}
		/*
		 * Link the node to the end of the disk_target list
		 */
		if (tmpdt == NULL) {
			tmpdt = dt;
			disks = dt;
		} else {
			tmpdt->next = dt;
			tmpdt = tmpdt->next;
		}
		/*
		 * Issue a callback, if the callback function is given
		 */
		if (cb != NULL) {
			cb_data.percentage_done = (i*100)/num;
			cb(&cb_data, app_data);
		}
	}
	*ndisks = num - bad;
	if (tmpdt != NULL) {
		tmpdt->next = NULL;
	}

	/*
	 * If percentage_done is not 100%, send a callback to indicate
	 * that it is completed.
	 */
	if (cb != NULL && cb_data.percentage_done != 100) {
		cb_data.percentage_done = 100;
		cb(&cb_data, app_data);
	}
	return (disks);
}

/*
 * get_td_disk_parts_discover
 * This function discovers the partition information for each disk and populate
 * Orchestrator cache.
 * Input:	disk_target_t *, the list of disks discovered
 *		Callback function to report progress to the caller
 * Output:	The disk partitions of each of the disk in the system
 *		is discovered and saved in orchestartor cache
 * Return:	None
 */
void
get_td_disk_parts_discover(disk_target_t *disks, om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;
	disk_target_t		*dt;
	int			i;

	if (disks == NULL) {
		return;
	}

	/*
	 * Initialize the fixed values for disk parition discover callback
	 */
	if (cb != NULL) {
		cb_data.callback_type = OM_TARGET_TARGET_DISCOVERY;
		cb_data.num_milestones = 4;
		cb_data.curr_milestone = OM_PARTITION_DISCOVERY;
	}

	for (dt = disks, i = 1; dt != NULL; dt = dt->next, i++) {
		/*
		 * Now get the partitions for this disk
		 */
		dt->dparts = enumerate_partitions(dt->dinfo.disk_name);
		/*
		 * Issue a callback, if the callback function is given
		 */
		if (cb != NULL) {
			cb_data.percentage_done = (i*100)/disks_total;
			cb(&cb_data, app_data);
		}
	}
	/*
	 * If percentage_done is not 100%, send a callback to indicate
	 * that it is completed.
	 */
	if (cb != NULL && cb_data.percentage_done != 100) {
		cb_data.percentage_done = 100;
		cb(&cb_data, app_data);
	}
}

/*
 * get_td_disk_slices_discover
 * This function discovers the VTOC slices information for each disk
 * and populate Orchestrator cache.
 * Input:	disk_target_t *, the list of disks discovered
 * Output:	The disk slices of each of the disk in the system
 *		is discovered and saved in orchestartor cache
 * Return:	None
 */
void
get_td_disk_slices_discover(disk_target_t *disks, om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;
	disk_target_t		*dt;
	int			i;

	if (disks == NULL) {
		return;
	}

	/*
	 * Initialize the fixed values for disk parition discover callback
	 */
	if (cb != NULL) {
		cb_data.callback_type = OM_TARGET_TARGET_DISCOVERY;
		cb_data.num_milestones = 4;
		cb_data.curr_milestone = OM_SLICE_DISCOVERY;
	}

	for (dt = disks, i = 1; dt != NULL; dt = dt->next, i++) {
		/*
		 * Now get the partitions for this disk
		 */
		dt->dslices = enumerate_slices(dt->dinfo.disk_name);
		/*
		 * Issue a callback, if the callback function is given
		 */
		if (cb != NULL) {
			cb_data.percentage_done = (i*100)/disks_total;
			cb(&cb_data, app_data);
		}
	}
	/*
	 * If percentage_done is not 100%, send a callback to indicate
	 * that it is completed.
	 */
	if (cb != NULL && cb_data.percentage_done != 100) {
		cb_data.percentage_done = 100;
		cb(&cb_data, app_data);
	}
}

/*
 * get_td_solaris_instances
 * This function will get the solaris instances found on the system
 * from TD module and populate Orchestrator cache.
 * Input:	None
 * Output:	None
 * Return:	Linked list of upgrade_info_t pointers with solaris instances
 *		information.
 */
upgrade_info_t *
get_td_solaris_instances(om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;
	int			ret, num;
	int			i;
	upgrade_info_t		*ut, *tmput;
	upgrade_info_t		*instances;

	/*
	 * Initialize the fixed values for disk info discover callback
	 */
	if (cb != NULL) {
		cb_data.callback_type = OM_TARGET_TARGET_DISCOVERY;
		cb_data.num_milestones = 4;
		cb_data.curr_milestone = OM_UPGRADE_TARGET_DISCOVERY;
	}

	tmput = NULL;
	instances = NULL;
	ret = td_discover(TD_OT_OS, &num);
	if (ret < 0 || num <= 0) {
		/*
		 * send a callback to indicate that it is over
		 */
		if (cb != NULL) {
			cb_data.percentage_done = 100;
			cb(&cb_data, app_data);
		}
		return (NULL);
	}

	for (i = 0; i < num; i++) {
		/*
		 * Get the disk information
		 */
		ut = enumerate_next_instance();
		/*
		 * We are not getting instance information for an instance
		 */
		if (ut == NULL) {
			continue;
		}
		/*
		 * Link the node to the end of the disk_target list
		 */
		if (tmput == NULL) {
			tmput = ut;
			instances = ut;
		} else {
			tmput->next = ut;
			tmput = tmput->next;
		}
		/*
		 * Issue a callback, if the callback function is given
		 */
		if (cb != NULL) {
			cb_data.percentage_done = (i*100)/num;
			cb(&cb_data, app_data);
		}
	}
	if (tmput != NULL) {
		tmput->next = NULL;
	}
	/*
	 * If percentage_done is not 100%, send a callback to indicate
	 * that it is completed.
	 */
	if (cb != NULL && cb_data.percentage_done != 100) {
		cb_data.percentage_done = 100;
		cb(&cb_data, app_data);
	}
	return (instances);
}

/*
 * send_discovery_complete_callback
 * This function sends a callback to indicate that the target discovery
 * is completed. This is needed if there are no disks discovered.
 * Input:	None
 * Output:	None
 * Return:	None
 */
void
send_discovery_complete_callback(om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;

	/*
	 * Send a callbacks to indicate all discovery is done
	 * OM_UPGRADE_TARGET_DISCOVERY is the last milestone.
	 */
	if (cb != NULL) {
		cb_data.callback_type = OM_TARGET_TARGET_DISCOVERY;
		cb_data.num_milestones = 4;
		cb_data.curr_milestone = OM_UPGRADE_TARGET_DISCOVERY;
		cb_data.percentage_done = 100;
		cb(&cb_data, app_data);
	}
}

/*
 * enumerate_next_disk
 * This function will get the disk information from TD module.
 * Input:	None
 * Output:	None
 * Return:	Pointer to disk_target_t with disk information for the next
 *		available disk from the Target Discovery.
 */
disk_target_t *
enumerate_next_disk()
{
	nvlist_t	*attr_list;
	td_errno_t	ret;
	char		*str;
	uint32_t	bsize;
	uint32_t	value;
	uint32_t	nsect;
	uint32_t	nheads;
	uint64_t	nblocks;
	disk_target_t	*dt;

	/*
	 * Call the function to get the next disk from Target discovery
	 * module
	 */
	ret = td_get_next(TD_OT_DISK);

	if (ret != 0) {
		return (NULL);
	}

	/*
	 * Get the list of attributes available for this disk
	 */
	attr_list = td_attributes_get(TD_OT_DISK);

	if (attr_list == NULL) {
		return (NULL);
	}

	/*
	 * if the device type is not FIXED, ignore the entry
	 * we don't want to count cdrom, floopy etc.
	 */
	if (nvlist_lookup_uint32(attr_list, TD_DISK_ATTR_MTYPE,
	    &value) == OM_SUCCESS) {
		if (value != TD_MT_FIXED) {
			nvlist_free(attr_list);
			return (NULL);
		}
	} else {
		nvlist_free(attr_list);
		return (NULL);
	}

	/*
	 * We got a disk. Now allocate space for disk_target_t
	 */
	dt = (disk_target_t *)calloc(1, sizeof (disk_target_t));
	if (dt == NULL) {
		nvlist_free(attr_list);
		return (NULL);
	}

	dt->dparts = NULL;
	dt->dslices = NULL;

	/*
	 * Get the disk name
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_NAME, &str) == OM_SUCCESS) {
		dt->dinfo.disk_name = strdup(str);
	} else {
		dt->dinfo.disk_name = strdup("");
	}
	if (dt->dinfo.disk_name == NULL) {
		om_set_error(OM_NO_SPACE);
		goto end_return;
	}

	/*
	 * Get volume name. It is optional. If not available, disk_volname
	 * will remain NULL. calloc(3C) above took care of the intialization.
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_VOLNAME, &str) == OM_SUCCESS) {
		dt->dinfo.disk_volname = strdup(str);

		if (dt->dinfo.disk_volname == NULL) {
			om_set_error(OM_NO_SPACE);
			goto end_return;
		}
	}

	/*
	 * Get device ID
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_DEVID, &str) == OM_SUCCESS) {
		dt->dinfo.disk_devid = strdup(str);

		if (dt->dinfo.disk_devid == NULL) {
			om_set_error(OM_NO_SPACE);
			goto end_return;
		}
	}

	/*
	 * Get device path
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_DEVICEPATH, &str) == OM_SUCCESS) {
		dt->dinfo.disk_device_path = strdup(str);

		if (dt->dinfo.disk_device_path == NULL) {
			om_set_error(OM_NO_SPACE);
			goto end_return;
		}
	}

	/*
	 * Get the disk type (controller type)
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_CTYPE, &str) == OM_SUCCESS) {
		dt->dinfo.disk_type = ctype_to_disktype_enum(str);
	} else {
		dt->dinfo.disk_type = OM_DTYPE_UNKNOWN;
	}

	/*
	 * Is the disk removable (like USB)
	 */
	if (nvlist_lookup_boolean(attr_list,
	    TD_DISK_ATTR_REMOVABLE) == OM_SUCCESS) {
		dt->dinfo.removable = B_TRUE;
	} else {
		dt->dinfo.removable = B_FALSE;
	}

	/*
	 * Get the disk label
	 */
	if (nvlist_lookup_uint32(attr_list, TD_DISK_ATTR_LABEL,
	    &value) == OM_SUCCESS) {
		if (value & TD_DISK_LABEL_VTOC) {
			dt->dinfo.label = OM_LABEL_VTOC;
		} else if (value & TD_DISK_LABEL_GPT) {
			dt->dinfo.label = OM_LABEL_GPT;
		} else if (value & TD_DISK_LABEL_FDISK) {
			dt->dinfo.label = OM_LABEL_FDISK;
		} else {
			dt->dinfo.label = OM_LABEL_UNKNOWN;
		}
	} else {
		dt->dinfo.label = OM_LABEL_UNKNOWN;
	}

	/*
	 * Calculate the total size of the disk
	 */
	if (nvlist_lookup_uint32(attr_list,
	    TD_DISK_ATTR_BLOCKSIZE, &bsize) != OM_SUCCESS) {
		bsize = 0;
	}

	if (nvlist_lookup_uint64(attr_list,
	    TD_DISK_ATTR_SIZE, &nblocks) != OM_SUCCESS) {
		nblocks = 0;
	}

	if (bsize == 0 || nblocks == 0) {
		om_log_print("Ignoring %s because of bad Geometry\n",
		    dt->dinfo.disk_name);
		goto end_return;
	}

	dt->dinfo.disk_size_sec = (bsize * nblocks)/512;
	dt->dinfo.disk_size_total = dt->dinfo.disk_size =
	    (bsize * nblocks)/ONEMB;

	/*
	 * If disk is too big, adjust usable disk size
	 */
	if (dt->dinfo.disk_size > om_get_max_usable_disk_size()) {
		dt->dinfo.disk_size = om_get_max_usable_disk_size();

		/*
		 * display in MB for debugging purposes, but post log
		 * message using more convenient GB
		 */

		om_debug_print(OM_DBGLVL_WARN,
		    "Disk %s is too big (%luMiB),"
		    " usable size will be adjusted to %luMiB\n",
		    dt->dinfo.disk_name, dt->dinfo.disk_size_total,
		    dt->dinfo.disk_size);

		om_log_print(
		    "Disk %s is too big (%luGiB),"
		    " usable size will be adjusted to %luGiB\n",
		    dt->dinfo.disk_name,
		    dt->dinfo.disk_size_total / ONE_GB_TO_MB,
		    dt->dinfo.disk_size / ONE_GB_TO_MB);
	}

	/*
	 * Calculate the size of 1 cylinder in blocks/sectors
	 * One sector = 512 bytes
	 * 1 cylinder = (number of sectors per track) * (number of heads)
	 */
	if (nvlist_lookup_uint32(attr_list,
	    TD_DISK_ATTR_NHEADS, &nheads) != OM_SUCCESS) {
		dt->dinfo.disk_cyl_size = 0;
		om_log_print("Ignoring %s because of bad Geometry\n",
		    dt->dinfo.disk_name);

		goto end_return;
	}

	if (nvlist_lookup_uint32(attr_list,
	    TD_DISK_ATTR_NSECTORS, &nsect) != OM_SUCCESS) {
		dt->dinfo.disk_cyl_size = 0;
		om_log_print("Ignoring %s because of bad Geometry\n",
		    dt->dinfo.disk_name);

		goto end_return;
	}

	dt->dinfo.disk_cyl_size = nsect * nheads;

	/*
	 * Set whether the disk is the default boot disk
	 */
	if (nvlist_lookup_boolean(attr_list,
	    TD_DISK_ATTR_CURRBOOT) == OM_SUCCESS) {
		dt->dinfo.boot_disk = B_TRUE;
	} else {
		dt->dinfo.boot_disk = B_FALSE;
	}

	/*
	 * Get the manufacturer
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_DISK_ATTR_VENDOR, &str) == OM_SUCCESS) {
		dt->dinfo.vendor = strdup(str);
	} else {
		dt->dinfo.vendor = strdup(OM_UNKNOWN_STRING);
	}
	if (dt->dinfo.vendor == NULL) {
		om_set_error(OM_NO_SPACE);
		goto end_return;
	}

	/*
	 * Currently Target discovery can't get the disk serial number
	 */
	dt->dinfo.serial_number = strdup(OM_UNKNOWN_STRING);
	if (dt->dinfo.serial_number == NULL) {
		om_set_error(OM_NO_SPACE);
		goto end_return;
	}
	/*
	 * we are done. Free the nvpair list and return the disk
	 */
	nvlist_free(attr_list);
	return (dt);
end_return:
	nvlist_free(attr_list);
	free(dt->dinfo.serial_number);
	free(dt->dinfo.vendor);
	free(dt->dinfo.disk_name);
	free(dt);
	return (NULL);
}

static void
log_partition_map(partition_info_t *pinfo)
{
	int ipar;

om_debug_print(OM_DBGLVL_INFO, "log_partition_map - after sorting\n");
	om_debug_print(OM_DBGLVL_INFO,
	    "id\ttype\torder\tsector offset\tsize in sectors\n");
	for (ipar = 0; ipar < OM_NUMPART; ipar++) {
		om_debug_print(OM_DBGLVL_INFO, "%d\t%02X\t%2d\t%lld\t%lld\n",
		    pinfo[ipar].partition_id,
		    pinfo[ipar].partition_type,
		    pinfo[ipar].partition_order,
		    pinfo[ipar].partition_offset_sec,
		    pinfo[ipar].partition_size_sec);
	}
}

/*
 * enumerate_partitions
 * This function will get all the partitions of a disk from TD module
 * Input:	char *diskname, the name of the disk, whose partitions are
 *		required.
 * Output:	None
 * Return:	disk_parts_t *, pointer to disk partition information
 *		of the requested disk.
 */
disk_parts_t *
enumerate_partitions(char *disk_name)
{
	nvlist_t	**attr_list, **save_attr_list;
	int		i;
	int		num, bad;
	uint8_t		part, part_id;
	char		*str;
	char		*ptr;
	uint32_t	value;
	disk_parts_t	*dp;

	/*
	 * Partitions are defined only for X86
	 */
	if (!is_system_x86()) {
		return (NULL);
	}

	if (disk_name == NULL) {
		return (NULL);
	}

	/*
	 * Get all the partitions of this disk
	 */
	attr_list = td_discover_partition_by_disk(disk_name, &num);
	if (num <= 0) {
		if (attr_list != NULL) {
			td_attribute_list_free(attr_list);
		}
		return (NULL);
	}

	/*
	 * save the attr list so that it can be freed later.
	 */
	save_attr_list = attr_list;
	/*
	 * We found some partitions, allocate space
	 */
	dp = (disk_parts_t *)calloc(1, sizeof (disk_parts_t));
	if (dp == NULL) {
		om_set_error(OM_NO_SPACE);
		goto enp_return;
	}

	/*
	 * Set the disk name
	 */
	dp->disk_name = strdup(disk_name);
	if (dp->disk_name == NULL) {
		om_set_error(OM_NO_SPACE);
		goto enp_return;
	}

	bad = 0;
	for (i = 0; i < num; i++, attr_list++) {
		/*
		 * If can't get the partition name, ignore that partition.
		 */
		if (nvlist_lookup_string(*attr_list,
		    TD_PART_ATTR_NAME, &str) != OM_SUCCESS) {
			bad++;
			continue;
		}

		/*
		 * If the partition name is not ending with pX
		 * ignore this partition
		 */
		ptr = str + strlen(str) - 2;
		if (*ptr == 'p') {
			ptr++;
		} else {
			bad++;
			om_debug_print(OM_DBGLVL_WARN, BAD_DISK_SLICE, str);
			om_log_print(BAD_DISK_SLICE, str);
			continue;
		}
		/*
		 * The partition will is of the form cXtXdXpX
		 */
		errno = 0;
		part_id = (int)strtol(ptr, (char **)NULL, 10);
		if (errno != 0 || part_id < 1 || part_id > OM_NUMPART) {
			/*
			 * Log the information
			 */
			bad++;
			om_debug_print(OM_DBGLVL_WARN, BAD_DISK_SLICE, str);
			om_log_print(BAD_DISK_SLICE, str);
			continue;
		}

		/*
		 * pinfo is an array with each element representing a partition
		 * in the range of 1-OM_NUMPART, which includes all possible
		 * primary or logical partitions. pinfo is indexed by fdisk
		 * partition number (ctdpN), but zero-based,
		 * so device /dev/rdsk/ctdpN goes in pinfo[N-1],
		 *	and pinfo[N-1].partition_id = N
		 *
		 * NOTE: terribly confusing struct element misnomers with
		 *	respect to the fdisk man page:
		 * - the N in ctdpN corresponds to struct element partition_id
		 * - the fdisk ID corresponds to struct element partition_type
		 * - struct element partition_id != fdisk ID!!!
		 */

		part = part_id - 1;
		dp->pinfo[part].partition_id = part_id;
		/*
		 * Get the bootable flag
		 */
		if (nvlist_lookup_uint32(*attr_list,
		    TD_PART_ATTR_BOOTID, &value) == OM_SUCCESS) {
			dp->pinfo[part].active =
			    value & ACTIVE ? B_TRUE : B_FALSE;
		} else {
			dp->pinfo[part].active = B_FALSE;
		}

		/*
		 * Get the partition type
		 */
		if (nvlist_lookup_uint32(*attr_list,
		    TD_PART_ATTR_TYPE, &value) == OM_SUCCESS) {
			dp->pinfo[part].partition_type = (uint8_t)value;
		} else {
			dp->pinfo[part].partition_type = 0;
		}

		/*
		 * Get the content type
		 */
		if (nvlist_lookup_uint32(*attr_list,
		    TD_PART_ATTR_CONTENT, &value) == OM_SUCCESS) {
			if (value == TD_PART_CONTENT_LSWAP) {
				dp->pinfo[part].content_type =
				    OM_CTYPE_LINUXSWAP;
			} else {
				dp->pinfo[part].content_type =
				    OM_CTYPE_UNKNOWN;
			}
		} else {
			dp->pinfo[part].content_type = OM_CTYPE_UNKNOWN;
		}

		/*
		 * Get the starting block
		 */
		if (nvlist_lookup_uint32(*attr_list,
		    TD_PART_ATTR_START, &value) == OM_SUCCESS) {
			dp->pinfo[part].partition_offset =
			    value/BLOCKS_TO_MB;

			dp->pinfo[part].partition_offset_sec = value;
		} else {
			dp->pinfo[part].partition_offset =
			    dp->pinfo[part].partition_offset_sec = 0;
		}

		/*
		 * The size value is number of blocks.
		 * Each block is 512 bytes.
		 * Get the size of the partition in MB
		 */
		if (nvlist_lookup_uint32(*attr_list,
		    TD_PART_ATTR_SIZE, &value) == OM_SUCCESS) {
			dp->pinfo[part].partition_size
			    = value/BLOCKS_TO_MB;

			dp->pinfo[part].partition_size_sec = value;
		} else {
			dp->pinfo[part].partition_size =
			    dp->pinfo[part].partition_size_sec = 0;
		}
	}
	/*
	 * We are finished with attr_list. Free the resources
	 */
	td_attribute_list_free(save_attr_list);

	/*
	 * Sort the disk partitions based on offset value.
	 * This will be useful for functions that validate the partitions
	 */
	num -= bad;
	sort_partitions_by_offset(dp, num);
	log_partition_map(dp->pinfo);
	return (dp);
enp_return:
	td_attribute_list_free(save_attr_list);
	local_free_part_info(dp);
	return (NULL);
}

/*
 * enumerate_slices
 * This function will get all the slices of a disk from TD module
 * Input:	char *diskname, the name of the disk, whose slices are
 *		required.
 * Output:	None
 * Return:	disk_slices_t *, pointer to disk slices information
 *		of the requested disk.
 * Note:	It is possible to have more than one solaris partitions in the
 *		case of X86 and hence more than one set of slices. Because of
 *		Name space issues these slices will have the same name. So we
 *		can return only one set of slices for each disk.
 *		If one of the solaris is an active partition, the slices
 *		corresponding to the partition is returned. If none of the
 *		partitions are active, the result is undefined.
 *		Having more than one solaris partition is considered to be
 *		illegal configuration.
 */
disk_slices_t *
enumerate_slices(char *disk_name)
{
	disk_slices_t	*ds;
	nvlist_t	**attr_list, **save_attr_list;
	int		i;
	int		num, bad;
	char		*str;
	uint32_t	value;
	uint64_t	big;

	/*
	 * start the VTOC slices discovery.
	 */

	if (disk_name == NULL) {
		return (NULL);
	}

	ds = NULL;
	/*
	 * Get all the partitions of this disk
	 */
	attr_list = td_discover_slice_by_disk(disk_name, &num);
	/*
	 * Save the attr_list since it will be advanced through the loop
	 */
	save_attr_list = attr_list;
	if (num > 0) {
		/*
		 * Found some slices. Allocate space
		 */
		ds = (disk_slices_t *)calloc(1, sizeof (disk_slices_t));
		if (ds == NULL) {
			om_set_error(OM_NO_SPACE);
			goto ens_return;
		}
		ds->disk_name = strdup(disk_name);
		if (ds->disk_name == NULL) {
			om_set_error(OM_NO_SPACE);
			goto ens_return;
		}
		/*
		 * How to get the partition_id?
		 */
		ds->partition_id = OM_PARTITION_UNKNOWN;

		bad = 0;

		/*
		 * Enumerate through the list of slices associated with given
		 * disk and save slice information in allocated disk_slices_t
		 * data structure. There is only space for NDKMAP slices, so
		 * make sure we don't overflow.
		 *
		 * Actually, if more than NDKMAP slices were reported as
		 * associated with given disk, something went wrong during
		 * target discovery - we shouldn't continue at this point
		 */
		if (num > NDKMAP) {
			om_debug_print(OM_DBGLVL_ERR,
			    "%d slices were reported as associated with disk %s"
			    " which is more than we could store (NDKMAP=%d)\n",
			    num, disk_name, NDKMAP);

			om_set_error(OM_TD_DISCOVERY_FAILED);
			goto ens_return;
		}

		for (i = 0; i < num; i++, attr_list++) {
			/*
			 * Get the slice name
			 */
			if (nvlist_lookup_string(*attr_list,
			    TD_SLICE_ATTR_NAME, &str) != OM_SUCCESS) {
				bad++;
				continue;
			}

			/*
			 * Get the slice number
			 */
			if (nvlist_lookup_uint32(*attr_list,
			    TD_SLICE_ATTR_INDEX, &value) == OM_SUCCESS) {
				ds->sinfo[i].slice_id = (uint8_t)value;
			} else {
				ds->sinfo[i].slice_id = OM_SLICE_UNKNOWN;
			}

			/*
			 * Get the starting block
			 */
			if (nvlist_lookup_uint64(*attr_list,
			    TD_SLICE_ATTR_START, &big) == OM_SUCCESS) {
				ds->sinfo[i].slice_offset = big;
			} else {
				ds->sinfo[i].slice_offset = 0;
			}

			/*
			 * Get the size of the slice in MB
			 */
			if (nvlist_lookup_uint64(*attr_list,
			    TD_SLICE_ATTR_SIZE, &big) == OM_SUCCESS) {
				ds->sinfo[i].slice_size = big;
			} else {
				ds->sinfo[i].slice_size = 0;
			}

			/*
			 * Get the slice flag
			 */
			if (nvlist_lookup_uint32(*attr_list,
			    TD_SLICE_ATTR_FLAG, &value) == OM_SUCCESS) {
				ds->sinfo[i].flags = (uint8_t)value;
			} else {
				ds->sinfo[i].flags = 0;
			}

			/*
			 * Get the slice tag
			 */
			if (nvlist_lookup_uint32(*attr_list,
			    TD_SLICE_ATTR_TAG, &value) == OM_SUCCESS) {
				ds->sinfo[i].tag = value;
			} else {
				ds->sinfo[i].tag = 0;
			}
		}
		/*
		 * We are finished with attr_list. Free the resources
		 */
		td_attribute_list_free(save_attr_list);
	}
	return (ds);
ens_return:
	free(ds->disk_name);
	free(ds);
	td_attribute_list_free(save_attr_list);
	return (NULL);
}

/*
 * enumerate_next_instance
 * This function will get the next upgrade target information from TD module.
 * Input:	None
 * Output:	None
 * Return:	Pointer to upgrade_info_t with Solaris instance information
 *		for the next available solaris instances from the Target
 *		Discovery module.
 */
upgrade_info_t *
enumerate_next_instance()
{
	nvlist_t	*attr_list;
	td_errno_t	ret;
	char		*str;
	char		*ptr = NULL;
	uint32_t	value;
	upgrade_info_t *ut;

	/*
	 * Call the function to get the next disk from Target discovery
	 * module
	 */
	ret = td_get_next(TD_OT_OS);

	if (ret) {
		return (NULL);
	}

	/*
	 * Get the list of attributes available for this disk
	 */
	attr_list = td_attributes_get(TD_OT_OS);

	if (attr_list == NULL) {
		return (NULL);
	}

	/*
	 * We got a disk. Now allocate space for disk_target_t
	 */
	ut = (upgrade_info_t *)calloc(1, sizeof (upgrade_info_t));
	if (ut == NULL) {
		nvlist_free(attr_list);
		return (NULL);
	}

	/*
	 * Assume the instance type is UFS for Dwarf
	 */
	ut->instance_type = OM_INSTANCE_UFS;
	ut->zones_installed = B_FALSE;
	ut->upgradable = B_TRUE;

	if (ut->instance_type == OM_INSTANCE_UFS) {
		ut->instance.uinfo.svm_configured = B_FALSE;
	}
	/*
	 * Get the slice name like c0d0s0.
	 * extract the disk and slice.
	 * If the diskname is not valid, return NULL
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_OS_ATTR_SLICE_NAME, &str) == OM_SUCCESS) {
		ut->instance.uinfo.disk_name = strdup(str);
		if (ut->instance.uinfo.disk_name == NULL) {
			goto eni_return;
		}
		if (just_the_disk_name(ut->instance.uinfo.disk_name, str) < 0) {
			goto eni_return;
		}
		/*
		 * slice could be single digit or two digits
		 */
		ptr = str + strlen(str) - 3;
		if (*ptr == 's') {
			ptr++;
		} else if (*(ptr+1) == 's') {
			ptr += 2;
		} else {
			goto eni_return;
		}
		errno = 0;
		ut->instance.uinfo.slice = strtol(ptr, (char **)NULL, 10);
		if (errno != 0) {
			goto eni_return;
		}
	} else {
		/*
		 * No upgrade target. We can't proceed
		 */
		om_set_error(OM_NO_UPGRADE_TARGET_NAME);
		goto eni_return;
	}

	/*
	 * Get the Release information
	 */
	ut->solaris_release = get_solaris_release_string(attr_list,
	    ut->instance.uinfo.slice);
	if (ut->solaris_release == NULL) {
		goto eni_return;
	}
	/*
	 * Non upgradeable zones if it is available
	 */
	ut->incorrect_zone_list = get_not_upgradeable_zone_list(attr_list);
	if (ut->incorrect_zone_list == NULL &&
	    om_get_error() == OM_NO_SPACE) {
		goto eni_return;
	}

	/*
	 * Get the upgradable attribute
	 */
	if (nvlist_lookup_uint32(attr_list, TD_OS_ATTR_NOT_UPGRADEABLE,
	    &value) == OM_SUCCESS) {
		if (value == 0) {
			ut->upgradable = B_TRUE;
		} else {
			ut->upgradable =  B_FALSE;
			ut->upgrade_message_id =
			    convert_td_value_to_om_upgrade_message(&value);
		}
	} else {
		/*
		 * not upgradable is not set by target discovery. So set the
		 * upgradable to true;
		 */
		ut->upgradable = B_TRUE;
	}

	/*
	 * Get the SVM related values from TD
	 */
	if (nvlist_lookup_string(attr_list,
	    TD_OS_ATTR_MD_COMPS, &str) == OM_SUCCESS) {
		ut->instance.uinfo.svm_configured = B_TRUE;
		ut->instance.uinfo.svm_info = get_svm_components(attr_list);
		if (ut->instance.uinfo.svm_info == NULL &&
		    om_get_error() == OM_NO_SPACE) {
			goto eni_return;
		}
	}
	/*
	 * we are done. Free the nvpair list and return the disk
	 */
	nvlist_free(attr_list);
	return (ut);
eni_return:
	nvlist_free(attr_list);
	free(ut->solaris_release);
	free(ut->instance.uinfo.disk_name);
	free(ut);
	return (NULL);
}

/*
 * ==================Private Functions ===============================
 */

/*
 * Local function to convert controller_type value returned by target discovery
 * module to disk_type enum
 */
om_disk_type_t
ctype_to_disktype_enum(char *ptr)
{
	if (ptr == NULL) {
		return (OM_DTYPE_UNKNOWN);
	}

	if (streq(ptr, DM_CTYPE_ATA)) {
		return (OM_DTYPE_ATA);
	}
	if (streq(ptr, DM_CTYPE_SCSI)) {
		return (OM_DTYPE_SCSI);
	}
	if (streq(ptr, DM_CTYPE_FIBRE)) {
		return (OM_DTYPE_FIBRE);
	}
	if (streq(ptr, DM_CTYPE_USB)) {
		return (OM_DTYPE_USB);
	}
	/*
	 * DM_CTYPE_SATA and DM_CTYPE_FIREWIRE not yet defined in libdiskmgt
	 * Once they are defined, we need to uncomment these lines
	 *
	 * if (streq(ptr, DM_CTYPE_SATA)) {
	 * return (OM_DTYPE_SATA);
	 * }
	 * if (streq(ptr, DM_CTYPE_FIREWIRE)) {
	 *	return (OM_DTYPE_FIREWIRE);
	 * }
	 */
	return (OM_DTYPE_UNKNOWN);
}

/*
 * Local function to convert TD module's "why an upgrade target cannot be
 * upgraded" Orchestrator defined upgrade message id.
 */
om_upgrade_message_t
convert_td_value_to_om_upgrade_message(uint32_t *value)
{
	struct	td_upgrade_fail_reasons	*reason;

	reason = (struct  td_upgrade_fail_reasons *)value;

	if (reason->root_not_mountable) {
		return (OM_UPGRADE_MOUNT_ROOT_FAILED);
	}
	if (reason->var_not_mountable) {
		return (OM_UPGRADE_MOUNT_VAR_FAILED);
	}
	if (reason->no_inst_release) {
		return (OM_UPGRADE_RELEASE_INFO_MISSING);
	}
	if (reason->no_cluster) {
		return (OM_UPGRADE_MISSING_CLUSTER_FILE);
	}
	if (reason->no_clustertoc) {
		return (OM_UPGRADE_MISSING_CLUSTERTOC_FILE);
	}
	if (reason->no_bootenvrc) {
		return (OM_UPGRADE_MISSING_BOOTENVRC_FILE);
	}
	if (reason->zones_not_upgradeable) {
		return (OM_UPGRADE_NG_ZONE_CONFIURE_PROBLEM);
	}
	if (reason->no_usr_packages) {
		return (OM_UPGRADE_INSTANCE_INCOMPLETE);
	}
	if (reason->no_version) {
		return (OM_UPGRADE_RELEASE_INFO_MISSING);
	}
	if (reason->svm_root_mirror) {
		return (OM_UPGRADE_INSTANCE_IS_MIRROR);
	}
	if (reason->wrong_metacluster) {
		return (OM_UPGRADE_WRONG_METACLUSTER);
	}
	if (reason->os_version_too_old) {
		return (OM_UPGRADE_RELEASE_NOT_SUPPORTED);
	}
	return (OM_UPGRADE_UNKNOWN_ERROR);
}

/*
 * This function takes a disk partitions (disk_partition_t *) and returns
 * a sorted disk partitions based on the way it is laid out in the disk
 * using the partition_offset value
 *
 * struct element partition_order will indicate the order, with the following
 * rules:
 * - Primary and extended partitions will be sorted first, with
 *	partition_order being assigned 1-FD_NUMPART
 * - Logical partitions follow, partition_order starting at FD_NUMPART+1
 */
void
sort_partitions_by_offset(disk_parts_t *dp_ptr, int num_part)
{
	disk_parts_t 	*dp;
	partition_info_t *pinfo[OM_NUMPART];
	int		i, j, partition_order;
	boolean_t	found_logical = B_FALSE;

	/*
	 * Copy the partition addresses to an array for qsort(3c)
	 */
	for (i = 0, j = 0; i < OM_NUMPART && j < num_part; i++)
		if (is_used_partition(&dp_ptr->pinfo[i]))
			pinfo[j++] = &dp_ptr->pinfo[i];
	/*
	 * Not ordered. Sort them
	 */
	qsort(&pinfo, j, sizeof (partition_info_t *), offset_compare);

	/*
	 * set partition order element, placing primary/extended first
	 * followed by any logical partitions at FD_NUMPART+1
	 */
	for (i = 0, partition_order = 1; i < j; i++) {
		if (IS_LOG_PAR(pinfo[i]->partition_id) && !found_logical) {
			found_logical = B_TRUE; /* once only */
			partition_order = FD_NUMPART + 1;
		}
		pinfo[i]->partition_order = partition_order++;
	}
}

/*
 * Comparison function for qsort use
 */
static int
offset_compare(const void *p1, const void *p2)
{
	partition_info_t *i = *((partition_info_t **)p1);
	partition_info_t *j = *((partition_info_t **)p2);

	/*
	 * logicals come after primaries
	 */
	if (IS_LOG_PAR(i->partition_id) && !IS_LOG_PAR(j->partition_id))
		return (1);
	if (!IS_LOG_PAR(i->partition_id) && IS_LOG_PAR(j->partition_id))
		return (-1);
	/*
	 * order by partition offset
	 */
	if (i->partition_offset_sec > j->partition_offset_sec)
		return (1);
	if (i->partition_offset_sec < j->partition_offset_sec)
		return (-1);
	return (0);
}
/*
 * Get the version string (like Solaris 11), minor number, and the build_id
 * from the TD module and create the solaris release string to be displayed
 * to the user
 * The release string could be of one of the following form:
 * 'Solaris 2.7'
 * 'Solaris Nevada snv_56'
 * 'Solaris Nevada SXDE 09/07'
 */
static char *
get_solaris_release_string(nvlist_t *list, int slice)
{
	int	size;
	char	*version = NULL;
	char	*minor = NULL;
	char	*build_id = NULL;
	char	*solaris_release;
	char	solaris_version[32];

	/*
	 * Get the Release information
	 */
	size = 1;

	if (nvlist_lookup_string(list, TD_OS_ATTR_VERSION, &version)
	    == OM_SUCCESS) {
		/*
		 * We can't say Solaris 11 since it is not yet released
		 * if it is 11, we change it to Solaris Express
		 */
		if (streq(version, "Solaris_11")) {
			(void) strcpy(solaris_version, "Solaris Express");
		} else {
			(void) strcpy(solaris_version, version);
		}
		size += strlen(solaris_version);
		if (nvlist_lookup_string(list, TD_OS_ATTR_VERSION_MINOR,
		    &minor) == OM_SUCCESS) {
			size += strlen(minor) + 1;
		}
		if (nvlist_lookup_string(list, TD_OS_ATTR_BUILD_ID,
		    &build_id) == OM_SUCCESS) {
			size += strlen(build_id) + 1;
		}

		/*
		 * Add the size for "(S<slice>) (slice - max 2 digits)
		 * like (S4)
		 */
		size += 6;
		solaris_release = (char *)malloc(size);
		if (solaris_release == NULL) {
			return (NULL);
		}
		(void) strcpy(solaris_release, solaris_version);
		if (minor != NULL) {
			(void) strcat(solaris_release, ".");
			(void) strcat(solaris_release, minor);
		}
		if (build_id != NULL) {
			(void) strcat(solaris_release, " ");
			(void) strcat(solaris_release, build_id);
		}
		(void) sprintf(solaris_release +
		    strlen(solaris_release), " (S%d)", slice);
	} else if (nvlist_lookup_string(list, TD_OS_ATTR_BUILD_ID,
	    &build_id) == OM_SUCCESS) {
		solaris_release = strdup(build_id);
	} else {
		solaris_release = strdup(OM_UNKNOWN_STRING);
		if (solaris_release == NULL) {
			return (NULL);
		}
	}
	return (solaris_release);
}

/*
 * get_not_upgradeable_zone_list
 * Get the list of non-global zones which have issues that prevent them
 * being upgraded.
 */
static char *
get_not_upgradeable_zone_list(nvlist_t *attr_list)
{
	char		**str_array;
	uint32_t 	value;
	char		*zone_list = NULL;
	int		size = 1;

	om_set_error(OM_SUCCESS);
	/*
	 * Non upgradeable zones if it is available
	 */
	if (nvlist_lookup_string_array(attr_list,
	    TD_OS_ATTR_ZONES_NOT_UPGRADEABLE,
	    &str_array, &value) == OM_SUCCESS) {
		char	**ptr;

		/*
		 * Find the total number of characters in the list of zones.
		 * we have to copy them in to a string and return to the caller
		 * Add 1 for the space between zones.
		 */
		for (ptr = str_array; *ptr != NULL; ptr++) {
			size += strlen(*ptr) + 1;
		}
		zone_list = calloc(1, size);
		if (zone_list == NULL) {
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}
		for (ptr = str_array; *ptr != NULL; ptr++) {
			(void) strcat(zone_list, *ptr);
			(void) strcat(zone_list, " ");
		}
	}
	return (zone_list);
}

/*
 * get_svm_components
 * If the root is mirror, get the slices that is part of root mirror
 */
static char *
get_svm_components(nvlist_t *attr_list)
{
	char		**str_array;
	uint32_t 	value;
	char		*svm_components = NULL;
	int		size = 1;
	boolean_t	first_time = B_TRUE;

	om_set_error(OM_SUCCESS);
	/*
	 * Get svm components
	 */
	if (nvlist_lookup_string_array(attr_list,
	    TD_SLICE_ATTR_MD_COMPS, &str_array, &value) == OM_SUCCESS) {
		char	**ptr;

		/*
		 * Find the total number of characters in the list of
		 * components. we have to copy them in to a string and return
		 * to the caller Add 1 for the space between components.
		 */
		for (ptr = str_array; *ptr != NULL; ptr++) {
			size += strlen(*ptr) + 1;
		}
		svm_components = calloc(1, size);
		if (svm_components == NULL) {
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}
		for (ptr = str_array; *ptr != NULL; ptr++) {
			if (first_time) {
				(void) strcpy(svm_components, *ptr);
				first_time = B_FALSE;
			} else {
				(void) strcat(svm_components, *ptr);
			}
			(void) strcat(svm_components, " ");
		}
	}
	return (svm_components);
}
