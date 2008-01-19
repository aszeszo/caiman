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
#pragma ident	"@(#)slim_util.c	1.12	07/10/23 SMI"


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
 * local functions
 */
int	slim_set_fdisk_attrs(nvlist_t **target_atrs, char *diskname);
int	slim_set_slice_attrs(nvlist_t **target_attrs, char *diskname);

/*
 * slim_set_fdisk_attrs
 * This function sets the appropriate fdisk attributes for target instantiation.
 * Input:	nvlist_t *target_attrs - list to add attributes to
 * Output:	None
 * Return:	errno - see orchestrator_api.h
 */
int
slim_set_fdisk_attrs(nvlist_t **list, char *diskname)
{
	disk_target_t	*dt;
	disk_parts_t	*cdp;
	int		i = 0;
	uint32_t	size1, size2;
	uint8_t		type1, type2;

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

	if (nvlist_add_boolean_value(*list, TI_ATTR_FDISK_WDISK_FL,
	    whole_disk) != 0) {
		om_log_print("Couldn't add WDISK_FL attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}
	om_log_print("whole_disk = %d\n", whole_disk);

	if (nvlist_add_string(*list, TI_ATTR_FDISK_DISK_NAME,
	    diskname) != 0) {
		om_log_print("Couldn't add FDISK_DISK_NAME attr\n");
		om_set_error(OM_NO_SPACE);
		return (-1);
	}
	om_log_print("diskname set = %s\n", diskname);
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
slim_set_slice_attrs(nvlist_t **list, char *diskname)
{
	disk_target_t	*dt;
	int		i;
	uint32_t	size = 0;
	uint32_t	swap_size = 0;

	for (dt = system_disks; dt != NULL; dt = dt->next) {
		if (streq(dt->dinfo.disk_name, diskname)) {
			break;
		}
	}
	if (dt == NULL) {
		om_log_print("Bad disk name\n");
		om_set_error(OM_BAD_DISK_NAME);
		return (-1);
	}
	for (i = 0; i < FD_NUMPART; i++) {
		if (dt->dparts && dt->dparts->pinfo[i].partition_type ==
		    SUNIXOS2) {
			size = dt->dparts->pinfo[i].partition_size;
			break;
		}
	}
	/*
	 * If no exiting solaris partition, use the whole disk for size.
	 */
	if (size == 0) {
		size = dt->dinfo.disk_size;
	}

	if (size == 0) {
		om_log_print("No size found on disk chosen\n");
		goto error;
	}
	if (size > TWENTY_GB_TO_MB) {
		swap_size = TWO_GB_TO_MB;
	} else if (size > TEN_GB_TO_MB) {
		swap_size = ONE_GB_TO_MB;
	} else if (size >= FOUR_GB_TO_MB) {
		swap_size = HALF_GB_TO_MB;
	} else {
		om_log_print("Device is too small for installation. Must "
		    "have 4GB of free space to install\n");
		goto error;
	}
	/*
	 * Set the default to use the  whole partition as the slice.
	 */
	if (nvlist_add_boolean_value(*list, TI_ATTR_SLICE_DEFAULT_LAYOUT,
	    B_TRUE) != 0) {
		om_log_print("Couldn't set whole partition attribute\n");
		goto error;
	}
	/*
	 * ZFS dataset attributes.
	 */
	if (nvlist_add_uint16(*list, TI_ATTR_ZFS_FS_NUM, ZFS_FS_NUM) != 0) {
		om_log_print("Couldn't set zfs fs num attr\n");
		goto error;
	}
	if (nvlist_add_uint16(*list, TI_ATTR_ZFS_SHARED_FS_NUM,
	    ZFS_SHARED_FS_NUM) != 0) {
                om_log_print("Couldn't set zfs shared fs num attr\n");
                goto error;
        }
	if (nvlist_add_string_array(*list, TI_ATTR_ZFS_FS_NAMES,
	    zfs_fs_names, ZFS_FS_NUM) != 0) {
		om_log_print("Couldn't set zfs fs name attr\n");
		goto error;
	}
	if (nvlist_add_string_array(*list, TI_ATTR_ZFS_SHARED_FS_NAMES,
            zfs_shared_fs_names, ZFS_SHARED_FS_NUM) != 0) {
                om_log_print("Couldn't set zfs shared fs name attr\n");
                goto error;
        }

	om_set_error(OM_SUCCESS);
	return (OM_SUCCESS);
error:
	om_set_error(OM_TARGET_INSTANTIATION_FAILED);
	return (-1);
}
