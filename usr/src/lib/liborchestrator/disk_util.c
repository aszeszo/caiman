/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
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

#pragma ident	"@(#)disk_util.c	1.1	07/08/03 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <sys/param.h>
#include <sys/types.h>

#include "orchestrator_private.h"

/*
 * local_free_disk_info
 * This function will free up the disk information data
 * Input: 	disk_info_t *dinfo - The pointer to disk_info_t.
 *		boolean_t follow_link - The disk_info_t structure has a
 *		pointer to the next disk_info. If this flag is true,
 *		then traverse the link and delete all the entries. If it is
 *		false, just delete this entry.
 * Output:	None.
 * Return:	None.
 */
void
local_free_disk_info(disk_info_t *dinfo, boolean_t follow_link)
{
	disk_info_t	*di;
	disk_info_t	*nextdi;

	if (dinfo == NULL) {
		return;
	}

	/*
	 * traverse through disk_info_t structure to free all elements
	 */
	for (di = dinfo; di != NULL; di = nextdi) {
		free(di->disk_name);
		free(di->vendor);
		free(di->serial_number);
		nextdi = di->next;

		/*
		 * If we deal with linked list, members are dynamically
		 * allocated, so free also memory allocated for particular
		 * member. Otherwise, disk_info_t was not allocated
		 * dynamically. If this is the case, we are done.
		 */
		if (follow_link)
			free(di);
		else
			break;
	}
}

/*
 * local_free_part_info
 * This function will free up the disk partition information data of a disk
 * Input: 	disk_parts_t *dpinfo - The pointer to disk_parts_t.
 * Output:	None.
 * Return:	None.
 */
void
local_free_part_info(disk_parts_t *dpinfo)
{
	if (dpinfo == NULL) {
		return;
	}

	if (dpinfo->disk_name) {
		free(dpinfo->disk_name);
	}
	free(dpinfo);
}

/*
 * local_free_slice_info
 * This function will free up the disk slices data of a disk.
 * Input: 	disk_slices_t *dsinfo - The pointer to disk_slices_t.
 * Output:	None.
 * Return:	None.
 */
void
local_free_slice_info(disk_slices_t *dsinfo)
{
	if (dsinfo == NULL) {
		return;
	}

	if (dsinfo->disk_name) {
		free(dsinfo->disk_name);
	}
	free(dsinfo);
}

/*
 * local_free_upgrade_info
 * This function will free up the upgrade targets data
 * Input: 	upgrade_info_t *uinfo - The pointer to upgrade_info_t.
 * Output:	None.
 * Return:	None.
 */
void
local_free_upgrade_info(upgrade_info_t *uinfo)
{
	upgrade_info_t	*ui;
	upgrade_info_t	*nextui;

	if (uinfo == NULL) {
		return;
	}

	/*
	 * traverse through upgrade_info_t structure to free all elements
	 */
	for (ui = uinfo; ui != NULL; ui = nextui) {
		if (ui->instance_type == OM_INSTANCE_UFS) {
			if (ui->instance.uinfo.disk_name) {
				free(ui->instance.uinfo.disk_name);
			}
			if (ui->instance.uinfo.svm_info) {
				free(ui->instance.uinfo.svm_info);
			}
		}
		if (ui->solaris_release) {
			free(ui->solaris_release);
		}
		if (ui->incorrect_zone_list) {
			free(ui->incorrect_zone_list);
		}
		nextui = ui->next;
		free(ui);
	}
}

/*
 * Function:	just_the_disk_name
 * Description: Convert a conventional disk name into the internal canonical
 *		form. Remove the trailing index reference. The return status
 *		reflects whether or not the 'src' name is valid.
 *
 *				src			 dst
 *			---------------------------------------
 *			[/dev/rdsk/]c0t0d0s0	->	c0t0d0
 *			[/dev/rdsk/]c0t0d0p0	->	c0t0d0
 *			[/dev/rdsk/]c0d0s0	->	c0d0
 *			[/dev/rdsk/]c0d0p0	->	c0d0
 *
 * Scope:	public
 * Parameters:	dst	- used to retrieve cannonical form of drive name
 *			  ("" if not valid)
 *		src	- name of drive to be processed (see table above)
 * Return:	 0	- valid disk name
 *		-1	- invalid disk name
 */
int
just_the_disk_name(char *dst, char *src)
{
	char		name[MAXPATHLEN];
	char		*cp;

	*dst = '\0';

	(void) strcpy(name, src);
	/*
	 * The slice could be like s2 or s10
	 */
	cp = name + strlen(name) - 3;
	if (*cp) {
		if (*cp == 'p' || *cp == 's') {
			*cp = '\0';
		} else {
			cp++;
			if (*cp == 'p' || *cp == 's') {
				*cp = '\0';
			}
		}
	}

	/* It could be full pathname like /dev/dsk/disk_name */
	if ((cp = strrchr(name, '/')) != NULL) {
		cp++;
		(void) strcpy(dst, cp);
	} else {
		/* Just the disk name is provided, so return the name */
		(void) strcpy(dst, name);
	}
	return (0);
}

/*
 * Function:	is_diskname_valid
 * Description:	Check if a string syntactically represents a cannonical
 *		disk name (e.g. c0t0d0).
 * Input:	char * diskname, the string to be validated
 * Return:	B_TRUE       - disk name valid
 *		B_FALSE      - disk name not valid
 */
boolean_t
is_diskname_valid(char *diskname)
{
	int 	i;

	/* validate parameters */
	if ((diskname == NULL) || (strlen(diskname) <= 2)) {
		return (B_FALSE);
	}

	diskname = diskname + strlen(diskname) - 3;
	/*
	 * If it is a slice/part return failure
	 * We have check for 1 digit slice and 2 digit slice numbers
	 */
	for (i = 0; i < 2; i++) {
		if ((*diskname == 's' || *diskname == 'p') &&
		    (isdigit(*(diskname+1)))) {
			return (B_FALSE);
		}
		diskname++;
	}

	return (B_TRUE);
}

/*
 * Function:	is_slicename_valid
 * Description:	Check to see a string syntactically represents a
 *		cannonical slice device name (e.g. c0t0d0s3).
 *		slice names cannot be path names (i.e. cannot contain
 *		any /'s.).
 *		They should be in the form 'sX', where X is a digit
 *		between 0 and 7.
 * Input:	char *slicename, string to be validated
 * Return:	B_TRUE       - valid slice name syntax
 *		B_FALSE      - invalid slice name syntax
 */
boolean_t
is_slicename_valid(char *slicename)
{
	int 	i;
	char	*ptr;
	int	c;

	/* validate parameters */
	if ((slicename == NULL) || (strlen(slicename) <= 2)) {
		return (B_FALSE);
	}

	if (strchr(slicename, '/') != NULL) {
		return (B_FALSE);
	}

	/*
	 * Should end with sN
	 */
	ptr = slicename + strlen(slicename) - 3;
	for (i = 0; i < 2; i++) {
		c = *(ptr+1);
		if ((*ptr == 's') && isdigit(c)) {
			return (B_TRUE);
		}
		ptr++;
	}
	return (B_FALSE);
}

/*
 * Given a disk name, this function returns the disk target structure
 * If it is not found NULL will be returned.
 */
disk_target_t *
find_disk_by_name(char *diskname)
{
	disk_target_t	*dt;

	for (dt = system_disks; dt != NULL; dt = dt->next) {
		if (streq(dt->dinfo.disk_name, diskname)) {
			break;
		}
	}

	if (dt == NULL) {
		om_set_error(OM_BAD_DISK_NAME);
		return (NULL);
	}
	return (dt);
}

/*
 * If diskname is provided, this function return the pointer to the partition
 * data from the disk target structure cache
 */
disk_parts_t *
find_partitions_by_disk(char *diskname)
{
	disk_target_t	*dt;

	dt = find_disk_by_name(diskname);
	if (dt != NULL) {
		if (dt->dparts == NULL) {
			om_set_error(OM_NO_PARTITION_FOUND);
			return (NULL);
		}
		return (dt->dparts);
	}
	return (NULL);
}

/*
 * If diskname is provided, this function return the pointer to the slices
 * data from the disk target structure cache
 */
disk_slices_t *
find_slices_by_disk(char *diskname)
{
	disk_target_t	*dt;

	dt = find_disk_by_name(diskname);
	if (dt != NULL) {
		if (dt->dslices == NULL) {
			om_set_error(OM_FORMAT_UNKNOWN);
			return (NULL);
		}
		return (dt->dslices);
	}
	return (NULL);
}
