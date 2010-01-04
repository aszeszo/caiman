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

#include <assert.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libnvpair.h>
#include <libintl.h>
#include <locale.h>
#include <sys/param.h>
#include <sys/types.h>
#include <td_api.h>

#include <auto_install.h>
#include <orchestrator_api.h>

#define	MB_TO_SECTORS	((uint64_t)2048)
#define	NULLCHK(ptr, alternate_text) ((ptr) == NULL ? (alternate_text) : (ptr))
#define	TAG_IS_TRUE(tag) (strncasecmp(tag, "true", sizeof (tag)) == 0)
#define	DISK_CRIT_SPECIFIED(crit) ((crit)[0] != '\0')
#define	STRING_CRIT_MATCHES(crit, disk_par) (strcmp(crit, disk_par) == 0)

static	boolean_t	discovery_done = B_FALSE;

static boolean_t disk_type_match(const char *, om_disk_type_t);
static disk_info_t *disk_criteria_match(disk_info_t *, auto_disk_info *);
static disk_info_t *get_disk_info(om_handle_t handle);
static disk_info_t *select_default_disk(disk_info_t *);
static boolean_t disk_criteria_specified(auto_disk_info *);
static uint64_t find_solaris_disk_size(disk_info_t *);
static void dump_disk_criteria(auto_disk_info *adi);
static boolean_t validate_IP(char *);

static om_handle_t	handle;
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
 * Initiate the target discovery and wait until it is finished.
 *
 * Output:
 *	initializes module private variable 'handle' which is used to refer
 *	to the data collected by target discovery service
 *
 * Returns:
 *	 AUTO_TD_SUCCESS on success
 *	 AUTO_TD_FAILURE on failure
 */
int
auto_target_discovery(void)
{
	/*
	 * Initiate target discovery process.
	 * Return with failure if the process can't be started
	 */
	auto_log_print(gettext("Initiating Target Discovery...\n"));
	handle = om_initiate_target_discovery(update_progress);

	if (handle < 0) {
		(void) auto_log_print(gettext("Could not start target "
		    "discovery\n"));
		return (AUTO_TD_FAILURE);
	}

	/*
	 * Wait for target discovery to complete
	 */
	while (!discovery_done) {
		sleep(2);
	}

	/*
	 * Return with failure if there are no potential targets
	 * for the installation.
	 */

	if (get_disk_info(handle) == NULL) {
		auto_log_print(gettext("No disks found on the target"
		    " system\n"));

		return (AUTO_TD_FAILURE);
	}

	auto_log_print(gettext("Target Discovery finished successfully\n"));
	return (AUTO_TD_SUCCESS);
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
 * Try to find a target disk which matches specified criteria.
 *
 * Hierarchical set of rules is applied.
 * We stop processing them as soon as target disk is identified.
 * If particular rule is applied and matching disk is not found,
 * abort processing immediately and return with failure.
 *
 * [1] If boot disk is required, use that.
 * [2] Try to find a disk that matches criteria specified.
 * [3] If no criteria were specified in manifest, apply algorithm for
 *     selecting the default disk.
 *
 * Input:
 *	target disk criteria obtained from manifest. If not provided
 *	(set to NULL), it is assumed that c#t#d# disk name was directly
 *	specified instead of AI manifest
 *
 * Output:
 *	c#t#d# name of identified target disk
 *	    - memory allocation is done in this function. Caller is responsible
 *	      for freeing it
 *
 * Returns:
 *	 AUTO_TD_SUCCESS on success
 *	 AUTO_TD_FAILURE on failure
 */
int
auto_select_install_target(char **diskname, auto_disk_info *adi)
{
	disk_info_t	*disks, *di = NULL;
	disk_slices_t	*ds = NULL;
#ifndef	__sparc
	disk_parts_t	*part = NULL;
#endif
	boolean_t	look_for_existing_slices = B_TRUE;
	boolean_t	target_disk_identified = B_FALSE;

	/*
	 * check if there are potential installation targets.
	 * There is no point to continue if there are no disks available.
	 */
	if ((disks = get_disk_info(handle)) == NULL) {
		auto_log_print(gettext("No disks are available for the "
		    "installation\n"));

		return (AUTO_TD_FAILURE);
	}

	/*
	 * If there is no AI manifest, disk name was specified directly.
	 * In this case make sure that specified disk exists.
	 */
	if (adi == NULL) {
		if ((*diskname != NULL) &&
		    om_find_disk_by_ctd_name(disks, *diskname) != NULL)
			return (AUTO_TD_SUCCESS);
		else
			return (AUTO_TD_FAILURE);
	}

	/* check if boot disk required as target for the installation */

	if (strcasecmp(adi->diskname, AIM_TARGET_DEVICE_BOOT_DISK) == 0) {
		if (((di = om_get_boot_disk(disks)) == NULL) ||
		    (di->disk_name == NULL)) {
			auto_log_print(gettext("Boot disk specified as "
			    "installation target, but the boot disk was not "
			    "found\n"));

			return (AUTO_TD_FAILURE);
		}

		target_disk_identified = B_TRUE;

		auto_log_print(gettext("Boot disk specified as installation"
		    " target\n"));
	}

	/*
	 * If target disk has not been determined yet, try to find one
	 * matching the criteria specified in AI manifest
	 *
	 * In case that no criteria were specified, apply algorithm for
	 * selecting the default target disk.
	 *
	 */

	if (!target_disk_identified) {
		if (disk_criteria_specified(adi)) {
			di = disk_criteria_match(disks, adi);

			if (di == NULL) {
				auto_log_print(gettext("Could not find a disk "
				    "based on manifest criteria\n"));
				return (AUTO_TD_FAILURE);
			}

			target_disk_identified = B_TRUE;
		} else {
			/*
			 * if a disk criteria wasn't specified
			 * try selecting a default disk
			 */
			di = select_default_disk(disks);
			if (di == NULL) {
				auto_log_print(gettext("Could not find a disk "
				    "using default search. Specify a disk name "
				    "or other search criteria in the "
				    "manifest.\n"));
				return (AUTO_TD_FAILURE);
			}

			target_disk_identified = B_TRUE;
		}
	}

	/*
	 * If we get to this point, target disk was successfully identified
	 * and 'di' variable points to its disk_info_t structure.
	 * Abort if those conditions are not met.
	 */

	assert(target_disk_identified);
	assert(di != NULL);

	/* Save the c#t#d# disk name for the consumer */

	*diskname = strdup(di->disk_name);

#ifndef	__sparc
	/*
	 * Obtain partition information for target disk
	 */
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

/*
 * Get the information about all the disks on the system
 */
static disk_info_t *
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

static disk_info_t *
disk_criteria_match(disk_info_t *disks, auto_disk_info *adi)
{
	disk_info_t *di;
	uint64_t find_disk_size_sec = adi->disksize;

	/* Dump the list of disk criteria to be applied */
	auto_log_print(gettext("Searching for a disk target matching the "
	    "following criteria\n"));
	dump_disk_criteria(adi);

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
		if (DISK_CRIT_SPECIFIED(adi->disktype) &&
		    !disk_type_match(adi->disktype, di->disk_type)) {
			auto_log_print(
			    "Disk %s type %s not requested type %s\n",
			    di->disk_name,
			    adi->disktype == NULL ? "(unknown)" : adi->disktype,
			    adi->disktype);
			continue; /* no type match */
		}
		if (DISK_CRIT_SPECIFIED(adi->diskvendor) &&
		    (di->vendor == NULL ||
		    strcasecmp(adi->diskvendor, di->vendor) != 0)) {
			auto_log_print("Disk %s "
			    "vendor (%s) not requested vendor %s\n",
			    di->disk_name,
			    NULLCHK(di->vendor, "name not available"),
			    adi->diskvendor);
			continue; /* vendor mismatch */
		}

		/* try to find match for c#t#d# name */
		if (DISK_CRIT_SPECIFIED(adi->diskname) &&
		    !STRING_CRIT_MATCHES(adi->diskname, di->disk_name)) {
			auto_log_print(gettext("Disk %s doesn't match desired "
			    "name %s\n"), di->disk_name, adi->diskname);

			continue; /* c#t#d# name doesn't match */
		}

		/* try to find match for volume name */
		if (DISK_CRIT_SPECIFIED(adi->diskvolname) &&
		    (di->disk_volname == NULL ||
		    !STRING_CRIT_MATCHES(adi->diskvolname, di->disk_volname))) {
			if (di->disk_volname == NULL)
				auto_log_print(gettext("Volume name not set for"
				    " disk %s\n"), di->disk_name);
			else
				auto_log_print(gettext("Disk %s has volume name"
				    " \"%s\" - doesn't match desired volume"
				    " name\n"),
				    di->disk_name, di->disk_volname);

			continue; /* volume name doesn't match */
		}

		/* try to find match for device ID */
		if (DISK_CRIT_SPECIFIED(adi->diskdevid) &&
		    (di->disk_devid == NULL ||
		    !STRING_CRIT_MATCHES(adi->diskdevid, di->disk_devid))) {
			if (di->disk_devid == NULL)
				auto_log_print(gettext("Device ID not available"
				    " for disk %s\n"), di->disk_name);
			else
				auto_log_print(gettext("Disk %s has device ID"
				    " \"%s\" - doesn't match desired device"
				    " ID\n"),
				    di->disk_name, di->disk_devid);

			continue; /* device ID doesn't match */
		}

		/* try to find match for device path */
		if (DISK_CRIT_SPECIFIED(adi->diskdevicepath) &&
		    (di->disk_device_path == NULL ||
		    !STRING_CRIT_MATCHES(adi->diskdevicepath,
		    di->disk_device_path))) {
			if (di->disk_device_path == NULL)
				auto_log_print(gettext("Device path not "
				    "available for disk %s\n"), di->disk_name);
			else
				auto_log_print(gettext("Disk %s has device path"
				    " \"%s\" - doesn't match desired device"
				    " path\n"),
				    di->disk_name, di->disk_device_path);

			continue; /* device path doesn't match */
		}

#ifndef	__sparc
		/* require a disk with a Solaris partition if specified */
		if (TAG_IS_TRUE(adi->diskusepart)) {
			int ipr;
			disk_parts_t	*part;

			auto_log_print(gettext("Manifest indicates that Solaris"
			    " fdisk partition must \n"
			    " be on the target disk prior to installation.\n"));

			part = get_disk_partition_info(handle, di->disk_name);
			if (part == NULL) {
				auto_log_print(
				    "Disk %s has no partition information\n",
				    di->disk_name);
				continue;
			}
			for (ipr = 0; ipr < OM_NUMPART; ipr++)
				if (part->pinfo[ipr].partition_type == SUNIXOS2)
					break;
			free(part);
			if (ipr >= OM_NUMPART) { /* no Solaris partition */
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
	if (adi->diskname[0] != '\0')
		return (B_TRUE);
	if (adi->diskvolname[0] != '\0')
		return (B_TRUE);
	if (adi->diskdevicepath[0] != '\0')
		return (B_TRUE);
	if (adi->diskdevid[0] != '\0')
		return (B_TRUE);
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

/*
 * mount iSCSI target according to iSCSI target parameters obtained from:
 * - AI manifest, or if not found, from
 * - DHCP Rootpath parameter from network interface
 * adi - contains manifest info
 * devnam - output NULL-terminated device name for the iSCSI boot target
 *	if an iSCSI boot target is identified without fatal error
 * devnamlen - max length of devnam
 *
 * Returns -1 if fatal error encountered, 0 otherwise
 * Returns iSCSI boot disk name at devnam if found (max length devnamlen)
 *	without encountering fatal error.
 *
 * Attempts to mount using libima with iSCSI initiator
 * If iSCSI parameters are provided, target must be mounted,
 *	otherwise considered fatal
 * If no ISCSI parameters are found, return 0 with no change at devnam
 */
int
mount_iscsi_target_if_requested(auto_disk_info *adi, char *devnam,
    int devnamlen)
{
	td_errno_t ret;
	nvlist_t *attrs;
	char *pdevnam;
	char *diskiscsi_name;
	char *diskiscsi_ip;
	uint32_t diskiscsi_port = 0;
	char *diskiscsi_lun = "";

	/*
	 * If the source of iSCSI boot parameters is set to DHCP,
	 * check DHCP Rootpath and fetch iSCSI boot parameters if provided
	 */
	if (adi->diskiscsi.parm_src == AI_ISCSI_PARM_SRC_DHCP) {
		FILE	*pipe_fp;
		char	rootpath[MAXPATHLEN] = "";
		char	cmd[] = "/sbin/dhcpinfo Rootpath";
		char	*p;
		int	ret;
		char	*diskiscsi_porta;

		auto_log_print("Manifest indicates that the source of iSCSI "
		    "boot parameters is DHCP parameter Rootpath\n");
		/*
		 * check DHCP Rootpath for iSCSI target parameters
		 */
		errno = 0;
		if ((pipe_fp = popen(cmd, "r")) == NULL) {
			auto_log_print("Could not check DHCP info for iSCSI "
			    "boot client, since piping command %s failed.\n",
			    cmd);
			return (0);
		}
		if (fgets(rootpath, sizeof (rootpath), pipe_fp) != NULL) {
			/* remove the trailing new-line */
			rootpath[strlen(rootpath) - 1] = '\0';
		}
		if ((ret = pclose(pipe_fp)) != 0)
			auto_log_print("Error in command to check DHCP "
			    "for iSCSI boot client. Command:%s\n", cmd);
		/*
		 * if problem, diagnose dhcpinfo exit status
		 *	log and return - not critical
		 */
		switch (ret) {
		case 0:	/* success */
			break;
		case 2:
			auto_log_print("DHCP error (no client daemon, "
			    "interface failed to configure, "
			    "or no satisfactory DHCP responses received)\n");
			return (0);
		case 3:
			auto_log_print("Bad arguments\n");
			return (0);
		case 4:
			auto_log_print("Timeout\n");
			return (0);
		case 6:
			auto_log_print("System error\n");
			return (0);
		case -1:
		default:
			auto_log_print("Unknown error %d errno %d\n",
			    ret, errno);
			return (0);
		}
		auto_log_print("DHCP Rootpath=%s\n", rootpath);
		/*
		 * RFC 4173 defines format of iSCSI boot target in Rootpath
		 *	Rootpath=iscsi:<IP>:<protocol>:<port>:<LUN>:<target>
		 */
		if (rootpath[0] == '\0' ||
		    strncmp(rootpath, "iscsi:", strlen("iscsi:")) != 0) {
			goto iscsi_rootpath_usage;
		}
		/*
		 * parse iSCSI Rootpath - parse errors will fail install
		 */
		if ((p = strchr(rootpath, ':')) == NULL)
			goto iscsi_rootpath_usage;
		*p++ = '\0';
		diskiscsi_ip = p;	/* IP */
		if ((p = strchr(p, ':')) == NULL)
			goto iscsi_rootpath_usage;
		*p++ = '\0'; /* protocol ignored - assumed TCP */
		if ((p = strchr(p, ':')) == NULL)
			goto iscsi_rootpath_usage;
		*p++ = '\0';
		diskiscsi_porta = p;	/* port */
		if ((p = strchr(p, ':')) == NULL)
			goto iscsi_rootpath_usage;
		*p++ = '\0';
		diskiscsi_lun = p;	/* LUN */
		if ((p = strchr(p, ':')) == NULL)
			goto iscsi_rootpath_usage;
		*p++ = '\0';
		diskiscsi_name = p;	/* target name */
		if (*diskiscsi_name == '\0' || *diskiscsi_ip == '\0') {
			auto_log_print("DHCP Rootpath must specify both iSCSI "
			    "IP and target name.\n");
			goto iscsi_rootpath_usage;
		}
		if (*diskiscsi_porta != '\0')
			diskiscsi_port = atol(diskiscsi_porta);
		auto_log_print("iSCSI boot target parameters will be taken "
		    "from DHCP Rootpath.\n");
	} else {
		/*
		 * use manifest information for iSCSI target parameters
		 */

		/*
		 * if neither iSCSI name nor IP were found in manifest
		 * then no iSCSI
		 */
		if (adi->diskiscsi.name[0] == '\0' ||
		    adi->diskiscsi.ip[0] == '\0') {
			return (0);
		}

		/*
		 * iSCSI target name and IP address are both mandatory if
		 * manifest is used to specify iSCSI target parameters
		 * Providing one * and not * the other will be considered a
		 * serious error.
		 */
		if (adi->diskiscsi.name[0] == '\0' ^
		    adi->diskiscsi.ip[0] == '\0') {
			auto_log_print("iSCSI target %s not specified\n",
			    adi->diskiscsi.name[0] == '\0' ?
			    "name" : "IP address");
			auto_log_print("Manifest must specify both iSCSI IP "
			    "and target name if either one is specified.\n");
			return (-1);
		}
		diskiscsi_name = adi->diskiscsi.name;
		diskiscsi_ip = adi->diskiscsi.ip;
		diskiscsi_port = adi->diskiscsi.port;
		diskiscsi_lun = adi->diskiscsi.lun;
		auto_log_print("iSCSI boot target parameters will be taken "
		    "from AI manifest.\n");
	}
	if (!validate_IP(diskiscsi_ip)) {
		auto_log_print("iSCSI target IP address format is bad.\n");
		auto_debug_print(AUTO_DBGLVL_INFO, "\tIP address=%s\n",
		    diskiscsi_ip);
		auto_log_print("\tIPv4 address must be numeric in the form: "
		    "NNN.NNN.NNN.NNN where NNN is a decimal number.\n");
		return (-1);
	}
	if (diskiscsi_port > 0xFFFF) {
		auto_log_print("iSCSI port (%d) is too large. "
		    "Maximum value is 65535.\n", diskiscsi_port);
		return (-1);
	}
	auto_debug_print(AUTO_DBGLVL_INFO, "iSCSI target parameters:\n");
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tTarget name=%s\n", diskiscsi_name);
	auto_debug_print(AUTO_DBGLVL_INFO, "\tIP address=%s\n", diskiscsi_ip);
	auto_debug_print(AUTO_DBGLVL_INFO, "\tport=%lu\n", diskiscsi_port);
	auto_debug_print(AUTO_DBGLVL_INFO, "\tLUN=%s\n", diskiscsi_lun);

	/*
	 * allocate TD attributes
	 */
	if (nvlist_alloc(&attrs, NV_UNIQUE_NAME, 0) != 0) {
		auto_log_print("Could not create target nvlist.\n");
		return (-1);
	}
	if (nvlist_add_uint32(attrs, TD_ATTR_TARGET_TYPE,
	    TD_TARGET_TYPE_ISCSI_STATIC_CONFIG) != 0) {
		auto_log_print("iSCSI target type could not be added. \n");
		goto error_exit;
	}
	if (nvlist_add_string(attrs, TD_ISCSI_ATTR_NAME, diskiscsi_name) != 0) {
		auto_log_print("iSCSI target name could not be added. \n");
		goto error_exit;
	}
	if (nvlist_add_string(attrs, TD_ISCSI_ATTR_IP, diskiscsi_ip) != 0) {
		auto_log_print("iSCSI target IP could not be added. \n");
		goto error_exit;
	}
	if (nvlist_add_uint32(attrs, TD_ISCSI_ATTR_PORT, diskiscsi_port) != 0) {
		auto_log_print("iSCSI target port could not be added. \n");
		goto error_exit;
	}
	if (nvlist_add_string(attrs, TD_ISCSI_ATTR_LUN, diskiscsi_lun) != 0) {
		auto_log_print("iSCSI target LUN could not be added. \n");
		goto error_exit;
	}

	ret = td_target_search(attrs);
	if (ret != TD_E_SUCCESS) {
		auto_debug_print(AUTO_DBGLVL_ERR, "iSCSI static "
		    "configuration failed\n");
		goto error_exit;
	}
	if (nvlist_lookup_string(attrs, TD_ISCSI_ATTR_DEVICE_NAME,
	    &pdevnam)) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "iSCSI target device not found.\n");
		goto error_exit;
	} else {
		/*
		 * convert "/dev/rdsk/cNtNtNs2" to "cNtNdN" in place
		 */
		char *ps;
		char mydevname[MAXNAMELEN];
		char rdsk[] = "/dev/rdsk/";

		if (strncmp(pdevnam, rdsk, strlen(rdsk) != 0)) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Failed to parse device name for iSCSI:%s\n",
			    pdevnam);
			goto error_exit;
		}
		(void) strlcpy(mydevname, &pdevnam[strlen(rdsk)],
		    sizeof (mydevname));
		/*
		 * locate 's' in 'ctds' format
		 */
		if ((ps = strrchr(mydevname, 's')) == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "discovered iSCSI device name %s is not a valid "
			    "slice name and will be considered invalid.\n",
			    mydevname);
			goto error_exit;
		}
		*ps = '\0';	/* trim slice number designation */
		if (strlcpy(devnam, mydevname, devnamlen) >= devnamlen) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "iSCSI device name buffer overflow=%s\n",
			    mydevname);
			goto error_exit;
		}
	}
	auto_log_print("iSCSI boot target mounted: device %s\n", devnam);
	auto_log_print("iSCSI boot target name %s IP %s\n", diskiscsi_name,
	    diskiscsi_ip);
	nvlist_free(attrs);
	return (0);
error_exit:
	nvlist_free(attrs);
	return (-1);
iscsi_rootpath_usage:
	auto_log_print("iSCSI target parameter parsing error.\n");
	auto_log_print("Check DHCP server Rootpath syntax against RFC 4173.\n");
	auto_log_print("Rootpath=iscsi:<IP>:<protocol>:<port>:<LUN>:<target>"
	    "\n");
	return (-1);
}

/*
 * validate NULL-terminated string as IPv4 address
 * Return B_TRUE if valid, B_FALSE otherwise
 */
static boolean_t
validate_IP(char *p)
{
	unsigned short val;
	char c;

	errno = 0;
	if (sscanf(p, "%3hd.%3hd.%3hd.%3hd%c", /* IPv4 */
	    &val, &val, &val, &val, &c) == 4 && errno == 0)
		return (B_TRUE);
	return (B_FALSE);
}

/*
 * Print target disk criteria specified in the manifest.
 *
 * Returns:
 * 	none
 */
static void
dump_disk_criteria(auto_disk_info *adi)
{
	if (adi->diskname[0] != '\0')
		auto_log_print(gettext(" Disk name: %s\n"), adi->diskname);
	if (adi->diskvolname[0] != '\0')
		auto_log_print(gettext(" Volume name: %s\n"), adi->diskvolname);
	if (adi->diskdevid[0] != '\0')
		auto_log_print(gettext(" Device ID: %s\n"), adi->diskdevid);
	if (adi->diskdevicepath[0] != '\0')
		auto_log_print(gettext(" Device path: %s\n"),
		    adi->diskdevicepath);
	if (adi->disktype[0] != '\0')
		auto_log_print(gettext(" Type: %s\n"), adi->disktype);
	if (adi->diskvendor[0] != '\0')
		auto_log_print(gettext(" Vendor: %s\n"), adi->diskvendor);
	if (adi->disksize != 0)
		auto_log_print(gettext(" Size [MiB]: %llu\n"),
		    adi->disksize / MB_TO_SECTORS);
#ifndef	__sparc
	if (adi->diskusepart[0] != '\0')
		auto_log_print(gettext(" Use existing Solaris partition:"
		    " %s\n"), adi->diskusepart);
#endif
	if (adi->diskoverwrite_rpool[0] != '\0')
		auto_log_print(gettext(" Use existing ZFS root pool 'rpool':"
		    " %s\n"), adi->diskoverwrite_rpool);

}
