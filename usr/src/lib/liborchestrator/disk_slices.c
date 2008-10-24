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

#define	EXEMPT_SLICE(s) ((s) == 2 || (s) == 8 || (s) == 9)
#define	SLICE_END(i) \
	(sorted_slices[(i)].slice_offset + sorted_slices[(i)].slice_size)

static struct free_region {
	uint64_t free_offset;
	uint64_t free_size;
};

/* track slice edits */
static struct {
	boolean_t preserve;
	boolean_t delete;
	boolean_t create;
	boolean_t install;
	uint64_t create_size;
} slice_edit_list[NDKMAP];

/* dry run for use in test driver */
boolean_t orch_part_slice_dryrun = B_FALSE;

static boolean_t whole_partition = B_TRUE; /* use whole partition for slice 0 */

/* free space management */
static slice_info_t sorted_slices[NDKMAP];
static int n_sorted_slices = 0;
static struct free_region free_space_table[NDKMAP];
static int n_fragments = 0;

static int om_prepare_vtoc_target(nvlist_t *, char *, boolean_t);
static boolean_t are_slices_preserved(void);
static boolean_t is_install_slice_specified(void);
static boolean_t remove_slice_from_table(uint8_t);
static slice_info_t *map_slice_id_to_slice_info(uint8_t);
static struct free_region *find_unused_region_of_size(uint64_t);
static boolean_t build_free_space_table(void);
static struct free_region *find_free_region_best_fit(uint64_t);
static struct free_region *find_largest_free_region(void);
static void insertion_sort_slice_info(slice_info_t *);
static void sort_used_regions(void);
static void log_slice_map(void);
static void log_free_space_table(void);
static void log_used_regions(void);
static uint64_t find_solaris_partition_size(void);
static boolean_t append_free_space_table(uint64_t, uint64_t);
/*
 * om_get_slice_info
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
om_get_slice_info(om_handle_t handle, char *diskname)
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
	return (om_duplicate_slice_info(0, ds));
}

/*
 * om_free_disk_slice_info
 * This function will free up the disk information data allocated during
 * om_get_slice_info().
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		disk_slices_t *dsinfo - The pointer to disk_slices_t. Usually
 *		returned by om_get_slice_info().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_disk_slice_info(om_handle_t handle, disk_slices_t *dsinfo)
{
	om_errno = 0;
	if (dsinfo == NULL) {
		return;
	}

	local_free_slice_info(dsinfo);
}

/*
 * om_duplicate_slice_info
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
om_duplicate_slice_info(om_handle_t handle, disk_slices_t *dslices)
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

/*
 * om_set_slice_info
 * This function will save the slice information passed by the
 * caller and use it for creating slices during install.
 * This function should be used in conjunction with om_perform_install
 * If om_perform_install is not called, no changes in the disk will be made.
 *
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 * 		disk_slices_t *ds - The modified slices
 * Output:	None
 * Return:	OM_SUCCESS - If the slice information is saved
 *		OM_FAILURE - If the data cannot be saved.
 * Note:	If the partition information can't be saved, the om_errno
 *		will be set to the actual error condition. The error
 *		information can be obtained by calling om_get_errno().
 */
/*ARGSUSED*/
int
om_set_slice_info(om_handle_t handle, disk_slices_t *ds)
{
	disk_target_t	*dt;
	disk_parts_t	*dp;
	/*
	 * Validate the input
	 */
	if (ds == NULL || ds->disk_name == NULL) {
		om_set_error(OM_BAD_INPUT);
		return (OM_FAILURE);
	}

	/*
	 * Find the disk from the cache using the diskname
	 */
	dt = find_disk_by_name(ds->disk_name);

	if (dt == NULL) {
		om_debug_print(OM_DBGLVL_ERR,
		    "could not find disk by name.\n");
		if (ds->disk_name != NULL)
			om_debug_print(OM_DBGLVL_ERR,
			    "disk name %s.\n", ds->disk_name);
		return (OM_FAILURE);
	}

	if (dt->dslices == NULL) {
		/*
		 * Log the information that the slices are not defined
		 * before the install started and GUI has defined the slices
		 * and saving it with orchestrator to be used during install
		 */
		om_log_print("No slices defined prior to install\n");
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
	 * It looks like the slice information is okay
	 * so take a copy and save it to use during install
	 */
	if (committed_disk_target == NULL) {
		disk_info_t	di;

		committed_disk_target =
		    (disk_target_t *)calloc(1, sizeof (disk_target_t));
		if (committed_disk_target == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}
		di = dt->dinfo;
		if (di.disk_name != NULL) {
			committed_disk_target->dinfo.disk_name =
			    strdup(di.disk_name);
		}
		committed_disk_target->dinfo.disk_size = di.disk_size;
		committed_disk_target->dinfo.disk_size_sec = di.disk_size_sec;
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
	}

	if (committed_disk_target->dinfo.disk_name == NULL ||
	    committed_disk_target->dinfo.vendor == NULL ||
	    committed_disk_target->dinfo.serial_number == NULL) {
		goto sdpi_return;
	}
	/*
	 * Copy the slice data from the input
	 */
	committed_disk_target->dslices =
	    om_duplicate_slice_info(handle, ds);
	if (committed_disk_target->dslices == NULL) {
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

/*
 * Slice editing suite
 *
 * These functions start with a description of existing slices
 * To find slices for a disk:
 *	-perform Target Discovery, finding disks and slices for the disk
 *	-get slices table for disk with om_get_slices_info()
 *	-if slices exist (not NULL), set target disk information with
 *		om_set_slice_info()
 *	-if no slices exist (NULL) , create empty slice table with
 *		om_init_slice_info()
 * The slice descriptions can then be edited with:
 *	om_create_slice(), om_delete_slice()
 * and preserved with:
 *	om_preserve_slice()
 * When new slice configuration is complete, it is written to disk with
 *	om_write_vtoc()
 *
 * om_preserve_slice() - protect slice given unique slice ID
 * slice_id - slice identifier
 * returns B_TRUE if parameter valid, B_FALSE otherwise
 */
boolean_t
om_preserve_slice(uint8_t slice_id)
{
	if (slice_id >= NDKMAP) {
		om_set_error(OM_BAD_INPUT);
		return (B_FALSE);
	}
	slice_edit_list[slice_id].preserve = B_TRUE;
	return (B_TRUE);
}

/*
 * are_slices_preserved() - returns true if any slices have been explicitly
 *	preserved
 */
static boolean_t
are_slices_preserved()
{
	int slice_id;

	for (slice_id = 0; slice_id < NDKMAP; slice_id++)
		if (slice_edit_list[slice_id].preserve)
			return (B_TRUE);
	return (B_FALSE);
}

/*
 * is_install_slice_specified() - returns true if slice to install to
 *	has been explicitly specified
 */
static boolean_t
is_install_slice_specified()
{
	int slice_id;

	for (slice_id = 0; slice_id < NDKMAP; slice_id++)
		if (slice_edit_list[slice_id].install)
			return (B_TRUE);
	return (B_FALSE);
}
/*
 * om_create_slice() - protect slice given unique slice ID
 * slice_id - slice identifier
 * slice_size - size in sectors
 * is_root - B_TRUE if slice to receive V_ROOT partition tag
 * returns B_TRUE if parameter valid, B_FALSE otherwise
 */
boolean_t
om_create_slice(uint8_t slice_id, uint64_t slice_size, boolean_t is_root)
{
	disk_slices_t *dslices;
	slice_info_t *psinfo;
	int isl;
	struct free_region *pfree_region;

	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dslices != NULL);

	om_debug_print(OM_DBGLVL_INFO, "to create slice %d \n", slice_id);

	if (slice_id >= NDKMAP) {
		om_set_error(OM_BAD_INPUT);
		return (B_FALSE);
	}
	dslices = committed_disk_target->dslices;
	if (EXEMPT_SLICE(slice_id) || slice_edit_list[slice_id].preserve) {
		om_set_error(OM_PROTECTED);
		return (B_FALSE);
	}
	psinfo = committed_disk_target->dslices->sinfo;
	log_slice_map();
	for (isl = 0; isl < NDKMAP; isl++, psinfo++) {
		if (slice_id == psinfo->slice_id &&
		    psinfo->slice_size != 0) { /* slice already exists */
			om_debug_print(OM_DBGLVL_ERR,
			    "creating slice which already exists\n");
			om_set_error(OM_ALREADY_EXISTS);
			return (B_FALSE);
		}
	}
	psinfo = committed_disk_target->dslices->sinfo;
	for (isl = 0; isl < NDKMAP; isl++, psinfo++)
		if (psinfo->slice_size == 0)
			break;
	if (isl >= NDKMAP) {
		om_set_error(OM_ALREADY_EXISTS);
		return (B_FALSE);
	}
	pfree_region = find_unused_region_of_size(slice_size);
	if (pfree_region == NULL) {
		om_debug_print(OM_DBGLVL_ERR,
		    "failure to find unused region of size %lld\n", slice_size);
		om_set_error(OM_ALREADY_EXISTS);
		return (B_FALSE);
	}
	if (slice_size == 0)
		slice_size = pfree_region->free_size;
	om_debug_print(OM_DBGLVL_INFO, "new slice %d offset=%lld size=%lld\n",
	    slice_id, pfree_region->free_offset, slice_size);
	psinfo->slice_id = slice_id;
	psinfo->tag = (is_root ? V_ROOT:V_UNASSIGNED); /* partition tag */
	psinfo->flags = 0;
	psinfo->slice_offset = pfree_region->free_offset;
	psinfo->slice_size = slice_size;
	slice_edit_list[slice_id].create = B_TRUE;
	slice_edit_list[slice_id].create_size = slice_size;
	if (slice_id == 0 || is_root)
		slice_edit_list[slice_id].install = B_TRUE;
	whole_partition = B_FALSE;
	om_debug_print(OM_DBGLVL_INFO,
	    "to create slice offset:%lld size:%lld \n",
	    psinfo->slice_offset, psinfo->slice_size);
	return (B_TRUE);
}

/*
 * delete_slice() - delete slice by unique slice ID
 * slice_id - slice identifier
 * returns B_TRUE if parameters valid and slice not preserved, B_FALSE otherwise
 */
boolean_t
om_delete_slice(uint8_t slice_id)
{
	disk_slices_t *dslices;
	int isl;

	assert(slice_id < NDKMAP);
	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dslices != NULL);

	if (EXEMPT_SLICE(slice_id) || slice_edit_list[slice_id].preserve) {
		om_set_error(OM_PROTECTED);
		return (B_FALSE);
	}
	if (remove_slice_from_table(slice_id))
		return (B_TRUE);
	om_debug_print(OM_DBGLVL_ERR, "delete slice fails - %d not found\n",
	    slice_id);
	om_set_error(OM_BAD_INPUT);
	return (B_FALSE);
}

/*
 * on_write_vtoc() - when partition editing is finished,
 * write out disk partition
 * returns B_TRUE for success, B_FALSE otherwise
 */
boolean_t
om_write_vtoc()
{
	nvlist_t *target_attrs;
	char *disk_name;

	/*
	 * if slices preseved and no slices are defined, assume that space
	 * before the preserved slice is to be allocated to slice 0
	 */
	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dslices != NULL);

	/* log free space table according to debugging level */
	build_free_space_table();
	log_free_space_table();

	/* if preserved slices, remove all other slices */
	/* must also preserve newly-created slices */
	if (are_slices_preserved()) {
		uint8_t slice_id;
		slice_info_t *psinfo;

		om_debug_print(OM_DBGLVL_INFO, "Preserving slices...\n");
		/* remove all non-preserved slices from table */
		psinfo = committed_disk_target->dslices->sinfo;
		for (slice_id = 0; slice_id < NDKMAP; slice_id++) {
			if (EXEMPT_SLICE(slice_id))
				continue;
			psinfo = map_slice_id_to_slice_info(slice_id);
			if (psinfo == NULL)
				continue;
			if (psinfo->slice_size == 0)
				continue;
			/* if not preserved and not newly created, remove */
			if (slice_edit_list[slice_id].preserve) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Preserving slice %d\n", slice_id);
				continue;
			}
			if (slice_edit_list[slice_id].create) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Preserving new slice %d\n", slice_id);
				continue;
			}
			remove_slice_from_table(slice_id);
		}
		whole_partition = B_FALSE;
	}
	/* if no slice to install to was explicitly specified */
	if (!is_install_slice_specified() && !whole_partition) {
		/* create slice 0 in largest free region */
		om_debug_print(OM_DBGLVL_INFO,
		    "Creating slice 0 in largest free region in partition\n");
		if (!om_create_slice(0, 0, B_TRUE)) {
			om_debug_print(OM_DBGLVL_ERR,
			    "Slice 0 could not be created. It is required that "
			    "OpenSolaris be installed in slice 0\n");
			return (B_FALSE);
		}
	}
	/* TODO check remaining size - is it big enough to install Solaris? */

	/* log final tables of slices and free space for debugging */
	log_slice_map();
	if (!build_free_space_table()) {
		om_debug_print(OM_DBGLVL_ERR, "Aborting VTOC editing "
		    "due to overlapping slices\n");
		om_set_error(OM_SLICES_OVERLAP);
		return (B_FALSE);
	}
	log_free_space_table();

	if (orch_part_slice_dryrun) {
		printf("Exiting dryrun\n");
		exit(0);
	}

	/* Create nvlist containing attributes describing the target */

	if (nvlist_alloc(&target_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Couldn't create nvlist describing the target\n");
		om_set_error(OM_NO_SPACE);
		return (B_FALSE);
	}
	if (om_prepare_vtoc_target(target_attrs,
	    committed_disk_target->dinfo.disk_name, whole_partition) != 0) {
		om_debug_print(OM_DBGLVL_ERR,
		    "preparing of VTOC target failed\n");

		nvlist_free(target_attrs);
		return (B_FALSE);
	} else
		om_debug_print(OM_DBGLVL_INFO,
		    "VTOC target prepared successfully\n");
	/* write vtoc */
	if (ti_create_target(target_attrs, NULL) !=
	    TI_E_SUCCESS) {
		om_debug_print(OM_DBGLVL_ERR,
		    "ERR: creating of VTOC target failed\n");

		nvlist_free(target_attrs);
		return (B_FALSE);
	} else
		om_debug_print(OM_DBGLVL_ERR,
		    "VTOC target created successfully\n");
	nvlist_free(target_attrs);
	return (B_TRUE);
}

/*
 * om_prepare_vtoc_target() - create attribute list for new vtoc
 */
static int
om_prepare_vtoc_target(nvlist_t *target_attrs, char *disk_name,
    boolean_t default_layout)
{
	assert(target_attrs != NULL);

	/* set target type attribute */

	if (nvlist_add_uint32(target_attrs,
	    TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_VTOC) != 0) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Couldn't add TI_ATTR_TARGET_TYPE to nvlist\n");

		nvlist_free(target_attrs);
		exit(1);
	}

	/* add attributes requiring creating VTOC */

	/* disk name */

	if (nvlist_add_string(target_attrs, TI_ATTR_SLICE_DISK_NAME,
	    disk_name) != 0) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Couldn't add TI_ATTR_SLICE_DISK_NAME to nvlist\n");
		return (-1);
	}

	/*
	 * create default or customized layout ?
	 * If customized layout is to be created, file containing layout
	 * configuration needs to be provided
	 */

	if (default_layout) {
		om_debug_print(OM_DBGLVL_INFO, "Default slice layout used\n");
		if (nvlist_add_boolean_value(target_attrs,
		    TI_ATTR_SLICE_DEFAULT_LAYOUT, B_TRUE) != 0) {
			om_debug_print(OM_DBGLVL_ERR, "Couldn't add "
			    "TI_ATTR_SLICE_DEFAULT_LAYOUT to nvlist\n");
			return (-1);
		}
	} else {
		int isl;
		slice_info_t *psinfo;
		uint16_t part_num;
		uint16_t *pnum, *ptag, *pflag;
		uint64_t *pstart, *psize;

		assert(committed_disk_target != NULL);
		assert(committed_disk_target->dslices != NULL);

		psinfo = committed_disk_target->dslices->sinfo;
		part_num = 0;
		pnum = ptag = pflag = NULL;
		pstart = psize = NULL;

		for (isl = 0; isl < NDKMAP; isl++, psinfo++) {
			if (psinfo->slice_size == 0)
				continue;
			/*
			 * read line describing VTOC slice.
			 * Line is in following format (decimal numbers):
			 *
			 * num tag flag 1st_sector size_in_sectors
			 *
			 * num - slice number - 0-7 for Sparc, 0-15 for x86
			 * tag - slice tag
			 *	 0 - V_UNASSIGNED
			 *	 1 - V_BOOT
			 *	 2 - V_ROOT
			 *	 3 - V_SWAP
			 *	 4 - V_USR
			 *	 5 - V_BACKUP
			 *	 6 - V_STAND
			 *	 7 - V_VAR
			 *	 8 - V_HOME
			 * flag - slice flag
			 *	 01 - V_UNMNT
			 *	 10 - V_RONLY
			 * 1st_sector - 1st sector of slice
			 * size_in_sectors - slice size in sectors
			 */
			part_num++;
			/* reallocate memory for another line */
			pnum = realloc(pnum, part_num * sizeof (uint16_t));
			ptag = realloc(ptag, part_num * sizeof (uint16_t));
			pflag = realloc(pflag, part_num * sizeof (uint16_t));
			pstart = realloc(pstart, part_num * sizeof (uint64_t));
			psize = realloc(psize, part_num * sizeof (uint64_t));

			if (pnum == NULL || ptag == NULL ||
			    pflag == NULL || pstart == NULL || psize == NULL) {
				om_debug_print(OM_DBGLVL_ERR,
				    "Memory allocation failed\n");
				return (-1);
			}
			/* fill in data */
			pnum[part_num - 1] = psinfo->slice_id;
			ptag[part_num - 1] = psinfo->tag;
			pflag[part_num - 1] = psinfo->flags;
			pstart[part_num - 1] = psinfo->slice_offset;
			psize[part_num - 1] = psinfo->slice_size;
		}
		om_debug_print(OM_DBGLVL_INFO, "Passed to TI\n");
		om_debug_print(OM_DBGLVL_INFO, "\tid\toffset\tsize\n");
		for (isl = 0; isl < part_num; isl++) {
			om_debug_print(OM_DBGLVL_INFO, "\t%d\t%lld\t%lld\n",
			    pnum[isl], pstart[isl], psize[isl]);
		}
		/* add number of slices to be created */
		if (nvlist_add_uint16(target_attrs, TI_ATTR_SLICE_NUM,
		    part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR,
			    "Couldn't add TI_ATTR_SLICE_NUM to nvlist\n");
			return (-1);
		}
		/* add slice geometry configuration */
		/* slice numbers */
		if (nvlist_add_uint16_array(target_attrs, TI_ATTR_SLICE_PARTS,
		    pnum, part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR,
			    "Couldn't add TI_ATTR_SLICE_PARTS to nvlist\n");
			return (-1);
		}
		/* slice tags */
		if (nvlist_add_uint16_array(target_attrs,
		    TI_ATTR_SLICE_TAGS, ptag, part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR, "Couldn't add "
			    "TI_ATTR_SLICE_TAGS to nvlist\n");
			return (-1);
		}
		/* slice flags */
		if (nvlist_add_uint16_array(target_attrs,
		    TI_ATTR_SLICE_FLAGS, pflag, part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR, "Couldn't add "
			    "TI_ATTR_SLICE_FLAGS to nvlist\n");

			return (-1);
		}
		/* slice start */
		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_SLICE_1STSECS, pstart, part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR, "Couldn't add "
			    "TI_ATTR_SLICE_1STSECS to nvlist\n");

			return (-1);
		}
		/* slice size */
		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_SLICE_SIZES, psize, part_num) != 0) {
			om_debug_print(OM_DBGLVL_ERR, "Couldn't add "
			    "TI_ATTR_SLICE_SIZES to nvlist\n");
			return (-1);
		}
	}

	return (0);
}
/*
 * set slice info initially for no slices
 * allocate on heap
 * given disk name, set all slices empty
 * return pointer to disk partition info
 * return NULL if memory allocation failure
 */
disk_slices_t *
om_init_slice_info(const char *disk_name)
{
	disk_slices_t *ds;
	int i;

	assert(disk_name != NULL);
	ds = calloc(1, sizeof (disk_slices_t));
	if (ds == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	ds->disk_name = strdup(disk_name);
	if (ds->disk_name == NULL) {
		free(ds);
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	return (ds);
}

/*
 * remove slice from usage table by ID
 * return TRUE for success, FALSE otherwise
 */
static boolean_t
remove_slice_from_table(uint8_t slice_id)
{
	slice_info_t *sinfo;
	int isl;

	sinfo = &committed_disk_target->dslices->sinfo[0];
	for (isl = 0; isl < NDKMAP; isl++) {
		if (slice_id == sinfo[isl].slice_id) {
			memmove(&sinfo[isl],
			    &sinfo[isl + 1],
			    (NDKMAP - isl - 1) * sizeof (slice_info_t));
			bzero(&sinfo[NDKMAP - 1],
			    sizeof (disk_slices_t)); /* clear last entry */
			slice_edit_list[slice_id].delete = B_TRUE;
			om_debug_print(OM_DBGLVL_INFO, "slice %d deleted from "
			    "table\n", slice_id);
			return (B_TRUE);
		}
	}
	om_debug_print(OM_DBGLVL_ERR, "failed to delete slice %d from table\n",
	    slice_id);
	return (B_FALSE);
}

/*
 * given slice ID, return its info struct for the target disk
 * return NULL if not found
 */
static slice_info_t *
map_slice_id_to_slice_info(uint8_t slice_id)
{
	slice_info_t *psinfo = &committed_disk_target->dslices->sinfo[0];
	int isl;

	for (isl = 0; isl < NDKMAP; isl++, psinfo++)
		if (slice_id == psinfo->slice_id && psinfo->slice_size > 0)
			return (psinfo);
	return (NULL);
}
/*
 * find best fit among blocks of unused space that has at least slice_size
 *	sectors unallocated
 * if slice_size is 0, return largest free region
 */
static struct free_region *
find_unused_region_of_size(uint64_t slice_size)
{
	slice_info_t *psinfo;
	uint64_t new_slice_offset;
	uint64_t partition_size_sec = find_solaris_partition_size();
	int isl;
	struct free_region *pfree_region;

	assert(committed_disk_target != NULL);
	assert(partition_size_sec != NULL);

	build_free_space_table();
	log_free_space_table();
	if (slice_size == 0) {
		if ((pfree_region = find_largest_free_region()) == NULL)
			return (NULL);
	} else {
		if ((pfree_region = find_free_region_best_fit(slice_size))
		    == NULL)
			return (NULL);
	}
	return (pfree_region);
}

/*
 * do a sorted insertion of used space in partition
 */
static void
insertion_sort_slice_info(slice_info_t *psinfo)
{
	int isl;

	for (isl = 0; isl < n_sorted_slices; isl++)
		if (sorted_slices[isl].slice_offset > psinfo->slice_offset)
			break;
	/* safe push downward */
	memmove(&sorted_slices[isl + 1], &sorted_slices[isl],
	    (n_sorted_slices - isl) * sizeof (slice_info_t));
	/* move in new slice info entry */
	memcpy(&sorted_slices[isl], psinfo, sizeof (slice_info_t));
	n_sorted_slices++;
}

/*
 * make table of used partition space taken from disk target
 */
static void
sort_used_regions()
{
	slice_info_t *psinfo;
	int isl;

	n_sorted_slices = 0;
	for (psinfo = &committed_disk_target->dslices->sinfo[0],
	    isl = 0; isl < NDKMAP; isl++, psinfo++) {
		if (EXEMPT_SLICE(psinfo->slice_id) || psinfo->slice_size == 0)
			continue;
		insertion_sort_slice_info(psinfo);
	}
	log_used_regions();
}

/*
 * populate a table with entries for each region of free space in the
 * target disk partition table
 * returns B_FALSE if any overlapping in the slices was detected,
 * B_TRUE if no problems were detected
 * side effects:
 *	sets n_fragments: number of free space fragments
 *	calls append_free_space_table() to add free regions
 */
static boolean_t
build_free_space_table()
{
	int isl;
	uint64_t free_size;
	uint64_t partition_size_sec = find_solaris_partition_size();

	sort_used_regions(); /* sort slice table by starting offset */
	n_fragments = 0; /* reset number of free regions */

	/* if no slices used, set entire partition as being free */
	if (n_sorted_slices == 0) {
		append_free_space_table(0, partition_size_sec);
		return (B_TRUE);
	}
	/* check for space before first slice */
	if (sorted_slices[0].slice_offset != 0)
		append_free_space_table(0, sorted_slices[0].slice_offset);
	for (isl = 0; isl < n_sorted_slices - 1; isl++) {
		/* does end of current slice overlap start of next slice? */
		if (SLICE_END(isl) > sorted_slices[isl + 1].slice_offset) {
			om_debug_print(OM_DBGLVL_ERR, "User is requesting "
			    "overlapping slices, which is illegal.\n");
			return (B_FALSE);
		}
		/* compute space between slices */
		free_size =
		    sorted_slices[isl + 1].slice_offset - SLICE_END(isl);
		if (free_size > 0)
			append_free_space_table(SLICE_END(isl), free_size);
	}
	/* check for any free space between last slice and end of partition */
	free_size = partition_size_sec - SLICE_END(n_sorted_slices - 1);
	if (free_size > 0)
		append_free_space_table(
		    SLICE_END(n_sorted_slices - 1), free_size);
	return (B_TRUE);
}

/*
 * append offset and length of a block of free space
 */
static boolean_t
append_free_space_table(uint64_t free_offset, uint64_t free_size)
{
	if (n_fragments >= NDKMAP)
		return (B_FALSE);
	free_space_table[n_fragments].free_offset = free_offset;
	free_space_table[n_fragments].free_size = free_size;
	n_fragments++;
	return (B_TRUE);
}
/*
 * find largest contiguous space not in other slices in free space table
 * must have previous call to build_free_space_table()
 * return size + offset of region or NULL if none found
 */
static struct free_region *
find_largest_free_region()
{
	struct free_region *pregion;
	struct free_region *largest_region = NULL;
	int ireg;

	for (pregion = free_space_table, ireg = 0;
	    ireg < n_fragments; ireg++, pregion++) {
		if (largest_region == NULL ||
		    pregion->free_size > largest_region->free_size)
			largest_region = pregion;
	}
	return (largest_region);
}

/*
 * find contiguous space that fits requested size most closely
 * must have previous call to build_free_space_table()
 * return size + offset of region or NULL if none found
 */
static struct free_region *
find_free_region_best_fit(uint64_t slice_size)
{
	struct free_region *pregion;
	struct free_region *best_fit = NULL;
	int ireg;

	for (pregion = free_space_table, ireg = 0;
	    ireg < n_fragments; ireg++, pregion++) {
		if (best_fit == NULL) { /* find first fit */
			if (pregion->free_size >= slice_size)
				best_fit = pregion;
			continue;
		}
		/* check if better fit */
		if (pregion->free_size > slice_size &&
		    pregion->free_size < best_fit->free_size)
			best_fit = pregion;
	}
	return (best_fit);
}

/*
 * get partition size in sectors from target partition information
 */
static uint64_t
find_solaris_partition_size()
{
	int isl;
	slice_info_t *psinfo;
	int ipart;
	disk_parts_t *dparts;

	/* check slice 2 for length */
	psinfo = committed_disk_target->dslices->sinfo;
	for (isl = 0; isl < NDKMAP; isl++, psinfo++)
		if (psinfo->slice_id == 2 && psinfo->slice_size != 0)
			return (psinfo->slice_size);

	assert(committed_disk_target->dparts != NULL);
	assert(committed_disk_target->dparts->pinfo != NULL);

	/* as fallback, take size from discovered info */
	dparts = committed_disk_target->dparts;
	for (ipart = 0; ipart < FD_NUMPART; ipart++)
		if (dparts->pinfo[ipart].partition_type == SUNIXOS2)
			return (dparts->pinfo[ipart].partition_size_sec);
	/* if no partition table defined as yet, use disk info */
	return (committed_disk_target->dinfo.disk_size_sec > 0 ?
	    committed_disk_target->dinfo.disk_size_sec:
	    ((uint64_t)committed_disk_target->dinfo.disk_size *
	    (uint64_t)BLOCKS_TO_MB));
}

/*
 * dump modified slice table
 */
static void
log_slice_map()
{
	int isl;
	slice_info_t *sinfo;

	sinfo = &committed_disk_target->dslices->sinfo[0];
	om_debug_print(OM_DBGLVL_INFO, "Modified slice table\n");
	om_debug_print(OM_DBGLVL_INFO, "\tid\toffset\tsize\toff+size\ttag\n");
	for (isl = 0; isl < NDKMAP; isl++) {
		if (sinfo[isl].slice_size == 0)
			continue;
		if (EXEMPT_SLICE(sinfo[isl].slice_id))
			continue;
		om_debug_print(OM_DBGLVL_INFO, "\t%d\t%lld\t%lld\t%lld\t%d\n",
		    sinfo[isl].slice_id,
		    sinfo[isl].slice_offset,
		    sinfo[isl].slice_size,
		    sinfo[isl].slice_offset + sinfo[isl].slice_size,
		    sinfo[isl].tag);
	}
}

/*
 * dump from sorted non-exempt slice table
 */
static void
log_used_regions()
{
	int isl;

	om_debug_print(OM_DBGLVL_INFO, "Sorted slices table:\n");
	if (n_sorted_slices == 0) {
		om_debug_print(OM_DBGLVL_INFO, "\tno slices in sorted table\n");
		return;
	}
	om_debug_print(OM_DBGLVL_INFO, "\tslice\toffset\tsize\toffset+size\n");
	for (isl = 0; isl < n_sorted_slices; isl++) {
		om_debug_print(OM_DBGLVL_INFO, "\t%d\t%lld\t%lld\t%lld\n",
		    sorted_slices[isl].slice_id,
		    sorted_slices[isl].slice_offset,
		    sorted_slices[isl].slice_size,
		    sorted_slices[isl].slice_offset +
		    sorted_slices[isl].slice_size);
	}
}

/*
 * dump free space entries from table
 */
static void
log_free_space_table()
{
	int i;

	om_debug_print(OM_DBGLVL_INFO, "Free space fragments - count %d\n",
	    n_fragments);
	if (n_fragments == 0) {
		om_debug_print(OM_DBGLVL_INFO, "\tno free space\n");
		return;
	}
	om_debug_print(OM_DBGLVL_INFO, "\toffset\tsize\tnoffset+size\n");
	for (i = 0; i < n_fragments; i++)
		om_debug_print(OM_DBGLVL_INFO, "\t%lld\t%lld\t%lld\n",
		    free_space_table[i].free_offset,
		    free_space_table[i].free_size,
		    free_space_table[i].free_offset +
		    free_space_table[i].free_size);
}

/*
 * end of slice editing suite
 */
