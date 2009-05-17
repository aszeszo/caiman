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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libnvpair.h>
#include <locale.h>
#include <sys/param.h>
#include <sys/types.h>

#include "auto_install.h"

#define	MB_TO_SECTORS	((uint64_t)2048)
#define	NULLCHK(ptr, alternate_text) ((ptr) == NULL ? (alternate_text) : (ptr))

static	boolean_t	discovery_done = B_FALSE;

static boolean_t disk_type_match(const char *, om_disk_type_t);
static disk_info_t *disk_criteria_match(disk_info_t *,
    auto_disk_info *);
static disk_info_t *select_default_disk(disk_info_t *);
static boolean_t disk_criteria_specified(auto_disk_info *);
static uint64_t find_solaris_disk_size(disk_info_t *);

om_handle_t	handle;
void	update_progress(om_callback_info_t *cb_data, uintptr_t app_data);

/*
 * Handle target discovery callbacks from orchestrator
 */
void
update_progress(om_callback_info_t *cb_data, uintptr_t app_data)
{
	if (cb_data->curr_milestone == OM_UPGRADE_TARGET_DISCOVERY &&
	    cb_data->percentage_done == 100) {
		discovery_done = B_TRUE;
	}
}

/*
 * Get the information about all the disks on the system
 */
disk_info_t *
get_disk_info(om_handle_t handle)
{
	disk_info_t	*disks;
	int		total;

	disks = om_get_disk_info(handle, &total);

	if (disks == NULL || total == 0) {
		(void) auto_debug_print(AUTO_DBGLVL_INFO,
		    "No Disks found...\n");
		return (NULL);
	}

	(void) auto_debug_print(AUTO_DBGLVL_INFO, "Number of disks = %d\n",
	    total);
	return (disks);
}
#ifndef	__sparc
/*
 * Get the partition information given the disk name
 */
disk_parts_t *
get_disk_partition_info(om_handle_t handle, char *disk_name)
{
	disk_parts_t	*dp;

	if (disk_name == NULL) {
		(void) auto_debug_print(AUTO_DBGLVL_INFO,
		    "disk_name is NULL\n");
		return (NULL);
	}

	dp = om_get_disk_partition_info(handle, disk_name);
	if (dp == NULL) {
		(void) auto_debug_print(AUTO_DBGLVL_INFO,
		    "Could not find partitions for %s - Error = %d\n",
		    disk_name, om_get_error());
		return (NULL);
	}

	return (dp);
}
#endif
/*
 * Validate the diskname
 * Do the target discovery and verify whether the passed diskname
 * is available in the system and get the characteristics.
 *
 * Returns:
 *	 AUTO_TD_SUCCESS on success
 *	 AUTO_TD_FAILURE on failure
 */
int
auto_validate_target(char **diskname, install_params *iparam,
    auto_disk_info *adi)
{
	disk_info_t	*disks, *di = NULL;
	disk_slices_t	*ds = NULL;
#ifndef	__sparc
	disk_parts_t	*part = NULL;
#endif
	boolean_t	look_for_existing_slices = B_TRUE;

	/*
	 * Initiate Target Discovery
	 */
	handle = om_initiate_target_discovery(update_progress);
	if (handle < 0) {
		(void) auto_log_print(gettext("Cannot start target "
		    "discovery...\n"));
		return (AUTO_TD_FAILURE);
	}

	/*
	 * Wait for target discovery to complete
	 */
	while (discovery_done == B_FALSE) {
		sleep(10);
	}

	disks = get_disk_info(handle);

	if (disks == NULL) {
		auto_log_print(gettext("No Disks found on the target "
		    "system\n"));
		return (AUTO_TD_FAILURE);
	}

	/*
	 * Validate the disk name and size
	 *
	 * If the diskname is NULL or unspecified, we
	 * use the manifest information to find the first
	 * matching disk
	 */
	if (*diskname == NULL || *diskname[0] == '\0') {
		if (disk_criteria_specified(adi)) {
			di = disk_criteria_match(disks, adi);

			if (di == NULL) {
				auto_log_print(gettext("Could not find a disk "
				    "based on manifest criteria\n"));
				return (AUTO_TD_FAILURE);
			}
			*diskname = strdup(di->disk_name);
		} else {
			/*
			 * if a disk criteria wasn't specified
			 * try selecting a default disk
			 */
			di = select_default_disk(disks);
			if (di == NULL) {
				auto_log_print(gettext("Cannot find a disk "
				    "using default search. Specify a disk name "
				    "or other search criteria in the "
				    "manifest.\n"));
				return (AUTO_TD_FAILURE);
			}
			*diskname = strdup(di->disk_name);
		}
	} else {
		for (di = disks; di != NULL; di = di->next) {
			if (strcmp(di->disk_name, *diskname) == 0) {
				auto_log_print(
				    "Disk = %s found on the system\n",
				    di->disk_name);
				break;
			}
		}
		if (di == NULL) {
			auto_log_print(gettext("Cannot find the specified disk "
			    "%s on the target system.\n"), *diskname);
			return (AUTO_TD_FAILURE);
		}
	}

	if (di == NULL) {
		auto_log_print(gettext("Cannot find the disk %s on the "
		    "target system.\n"), *diskname);
		return (AUTO_TD_FAILURE);
	}
#ifndef	__sparc
	part = get_disk_partition_info(handle, di->disk_name);

	/*
	 * Check whether there is a Solaris partition already there
	 * Otherwise we will use the whole disk
	 */
	if (part == NULL) {
		/*
		 * If there is no Solaris fdisk partition,
		 * don't bother looking for slices.
		 */
		look_for_existing_slices = B_FALSE;

		auto_log_print(gettext("Cannot find the partitions for disk %s "
		    "on the target system\n"), di->disk_name);
		part = om_init_disk_partition_info(di);
		if (part == NULL) {
			auto_log_print(gettext("Cannot init partition info\n"));
			return (AUTO_TD_FAILURE);
		}
	}

	if (om_set_disk_partition_info(handle, part) != OM_SUCCESS) {
		auto_log_print(gettext("Unable to set the disk partition "
		    "info\n"));
		return (AUTO_TD_FAILURE);
	}
#endif

	/*
	 * For x86, if we didn't find a Solaris fdisk partition,
	 * we shouldn't bother looking for vtoc slices on the disk.
	 * This flag is set above for this case.
	 */
	if (look_for_existing_slices) {
		ds = om_get_slice_info(handle, di->disk_name);
	}

	if (ds == NULL) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "no disk slice info found.\n");
		ds = om_init_slice_info(di->disk_name);
		if (ds == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "couldn't initialize disk slice info\n");
			return (AUTO_TD_FAILURE);
		}
	}
	if (om_set_slice_info(handle, ds) != OM_SUCCESS) {
		auto_log_print(gettext("Unable to set the disk slice "
		    "info\n"));
		return (AUTO_TD_FAILURE);
	}
	return (AUTO_TD_SUCCESS);
}

static boolean_t
disk_type_match(const char *disk, om_disk_type_t type)
{
	switch (type) {
		case (OM_DTYPE_ATA):
			return (strcasecmp(disk, "ATA") == 0);
		case (OM_DTYPE_SCSI):
			return (strcasecmp(disk, "SCSI") == 0);
		case (OM_DTYPE_FIBRE):
			return (strcasecmp(disk, "FIBER") == 0 ||
			    strcasecmp(disk, "FIBRE") == 0);
		case (OM_DTYPE_USB):
			return (strcasecmp(disk, "USB") == 0);
		case (OM_DTYPE_SATA):
			return (strcasecmp(disk, "SATA") == 0);
		case (OM_DTYPE_FIREWIRE):
			return (strcasecmp(disk, "FIREWIRE") == 0);
		default:
			break;
	}
	return (B_FALSE);
}

static disk_info_t *
disk_criteria_match(disk_info_t *disks, auto_disk_info *adi)
{
	disk_info_t *di;
	uint64_t find_disk_size_sec = adi->disksize;

	for (di = disks; di != NULL; di = di->next) {
		if (find_disk_size_sec > 0) {
			uint64_t disk_size_sec = di->disk_size * MB_TO_SECTORS;

			/*
			 * for some reason, the disk_size_sec disk info
			 * element is coming up zero, but disk_size element OK.
			 * TODO: investigate - until then, use disk_size
			 */
			if (disk_size_sec < find_disk_size_sec) {
				auto_log_print("Disk %s "
				    "size %lld sectors smaller than requested "
				    "%lld sectors\n",
				    di->disk_name, disk_size_sec,
				    find_disk_size_sec);
				continue; /* disk too small */
			}
		}
		if (adi->disktype[0] != '\0' &&
		    !disk_type_match(adi->disktype, di->disk_type)) {
			auto_log_print(
			    "Disk %s type %s not requested type %s\n",
			    di->disk_name,
			    adi->disktype == NULL ? "(unknown)" : adi->disktype,
			    adi->disktype);
			continue; /* no type match */
		}
		if (adi->diskvendor[0] != '\0' &&
		    (di->vendor == NULL ||
		    strcasecmp(adi->diskvendor, di->vendor) != 0)) {
			auto_log_print("Disk %s "
			    "vendor (%s) not requested vendor %s\n",
			    di->disk_name,
			    NULLCHK(di->vendor, "name not available"),
			    adi->diskvendor);
			continue; /* vendor mismatch */
		}
#ifndef	__sparc
		/* require a disk with a Solaris partition if specified */
		if (strcasecmp(adi->diskusepart, "true") == 0) {
			int ipr;
			disk_parts_t	*part;

			part = get_disk_partition_info(handle, di->disk_name);
			if (part == NULL) {
				auto_log_print(
				    "Disk %s has no partition information\n",
				    di->disk_name);
				continue;
			}
			for (ipr = 0; ipr < FD_NUMPART; ipr++)
				if (part->pinfo[ipr].partition_type == SUNIXOS2)
					break;
			free(part);
			if (ipr >= FD_NUMPART) { /* no Solaris partition */
				auto_log_print(
				    "Disk %s has no Solaris2 partitions\n",
				    di->disk_name);
				continue;
			}
		}
#endif
		break;
	}
	if (di == NULL) {
		char *errmsg = gettext(
		    "No disk that matches all manifest criteria was found\n");

		printf(errmsg);
		auto_log_print(errmsg);
	} else
		auto_log_print(gettext(
		    "Disk %s selected based on manifest criteria\n"),
		    di->disk_name);
	return (di);
}

/*
 * This function selects a default disk to do
 * installation on.
 *
 * The first disk that has a Solaris2 partition
 * defined and has a big enough slice0 is selected.
 *
 * Returns:
 * 	disk_info_t for the matching disk
 * 	NULL if no matching disk is found
 */
static disk_info_t *
select_default_disk(disk_info_t *disks)
{
	disk_info_t *di;
	uint64_t min_disk_size_MB;
	uint64_t min_disk_size_secs;

	/* get the minimum recommended disk size in sectors */
	min_disk_size_MB = om_get_recommended_size(NULL, NULL);
	auto_log_print(
	    "Checking any disks for minimum recommended size of %lld MB\n",
	    min_disk_size_MB);
	min_disk_size_secs = min_disk_size_MB * MB_TO_SECTORS;
	for (di = disks; di != NULL; di = di->next) {
		uint64_t disk_size_secs = find_solaris_disk_size(di);

		auto_log_print("Disk %s size listed as %lld MB\n",
		    di->disk_name, disk_size_secs / MB_TO_SECTORS);
		if (disk_size_secs >= min_disk_size_secs) {
			auto_log_print("Default disk selected is %s\n",
			    di->disk_name);
			return (di);
		}
		/* disk is not big enough, so move on to the next disk */
	}
	auto_debug_print(AUTO_DBGLVL_INFO, "No default disk was selected\n");
	return (NULL);
}

/*
 * get disk (SPARC) or partition (x86) size in sectors from target information
 */
static uint64_t
find_solaris_disk_size(disk_info_t *di)
{
	return (di->disk_size_sec > 0 ? di->disk_size_sec:
	    ((uint64_t)di->disk_size * MB_TO_SECTORS));
}

/*
 * Check to see if the disk criteria was specified
 * at all in the manifest.
 *
 * Returns:
 * 	B_TRUE if any of the disk selection criteria were specified
 *	B_FALSE otherwise
 */
static boolean_t
disk_criteria_specified(auto_disk_info *adi)
{
	if (adi->disktype[0] != '\0')
		return (B_TRUE);
	if (adi->diskvendor[0] != '\0')
		return (B_TRUE);
	if (adi->disksize != 0)
		return (B_TRUE);
#ifndef	__sparc
	if (adi->diskusepart[0] != '\0')
		return (B_TRUE);
#endif
	if (adi->diskoverwrite_rpool[0] != '\0')
		return (B_TRUE);
	return (B_FALSE);
}
