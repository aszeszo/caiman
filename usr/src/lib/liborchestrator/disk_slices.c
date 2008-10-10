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
#define	SECTORS_AFTER(s) (committed_disk_target->dinfo.disk_size - (s))
#define	MAX(p, q) ((p) > (q) ? (p):(q))

boolean_t whole_partition = B_TRUE; /* use whole partition for slice 0 */

static const uint64_t max_uint64 = 0xFFFFFFFFFFFFFFFF; /* maximum possible */
static slice_info_t ordered_slice_usage[NDKMAP];

static struct found_region {
	uint64_t slice_offset;
	uint64_t slice_size;
} found_region;

/* track slice edits */
static struct {
	boolean_t preserve;
	boolean_t delete;
	boolean_t create;
	uint32_t size;
} slice_edit_list[NDKMAP];

/* free space management */
static slice_info_t ordered_space_used[NDKMAP];
static int n_used_regions = 0;

static int om_prepare_vtoc_target(nvlist_t *, char *, boolean_t);
static boolean_t are_slices_preserved(void);
static boolean_t remove_slice_from_table(uint8_t);
static void dump_slice_map(void);
static slice_info_t *map_slice_id_to_slice_info(uint8_t);
static struct found_region *find_unused_region_of_size(uint64_t);

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
	struct found_region *pfound_region;

	assert(committed_disk_target != NULL);
	assert(committed_disk_target->dslices != NULL);

	om_debug_print(OM_DBGLVL_INFO, "to create slice %d \n", slice_id);

	dslices = committed_disk_target->dslices;
	if (slice_id == 2) {
		om_set_error(OM_PROTECTED);
		return (B_FALSE);
	}
	if (slice_id >= NDKMAP) {
		om_set_error(OM_BAD_INPUT);
		return (B_FALSE);
	}
	psinfo = committed_disk_target->dslices->sinfo;
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
		printf("failure to find empty slice slot\n");
		om_set_error(OM_ALREADY_EXISTS);
		return (B_FALSE);
	}
	pfound_region = find_unused_region_of_size(slice_size);
	if (pfound_region == NULL) {
		printf("failure to find unused region of size %lld\n",
		    slice_size);
		om_set_error(OM_ALREADY_EXISTS);
		return (B_FALSE);
	}

	om_debug_print(OM_DBGLVL_INFO, "slice id %d \n", slice_id);
	psinfo->slice_id = slice_id;
	psinfo->tag = (is_root ? 2:0); /* root, otherwise unassigned */
	psinfo->flags = 0;
	psinfo->slice_offset = pfound_region->slice_offset;
	psinfo->slice_size = pfound_region->slice_size;
	slice_edit_list[slice_id].create = B_TRUE;
	slice_edit_list[slice_id].size = slice_size;
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

	if (slice_id == 2 || slice_edit_list[slice_id].preserve) {
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

	/* if preserved slices, install in slice 0 before first preserved */
	if (are_slices_preserved()) {
		uint64_t s0_slice_size = max_uint64;
		uint8_t slice_id;
		slice_info_t *psinfo;

		/* for each slice in table */
		psinfo = committed_disk_target->dslices->sinfo;
		for (slice_id = 0; slice_id < NDKMAP; slice_id++) {

			if (slice_id == 2 || slice_id == 8)
				continue;
			psinfo = map_slice_id_to_slice_info(slice_id);
			if (psinfo == NULL)
				continue;
			if (slice_edit_list[slice_id].preserve) {

				printf("slice offset =%lld s0 slice siz=%lld\n",
				    psinfo->slice_offset, s0_slice_size);
				/* save offset of 1st preserved slice */
				if (psinfo->slice_offset > 0 &&
				    psinfo->slice_offset < s0_slice_size) {
					s0_slice_size = psinfo->slice_offset;
				printf("slice offset now =%lld s0 "
				    "slice size=%lld\n",
				    psinfo->slice_offset, s0_slice_size);
				}
					/* min offset will become size */
			} else /* remove non-preserved slices from table */
				if (psinfo->slice_size != 0)
					remove_slice_from_table(slice_id);
		}
		/* perform installation in slice 0 */
		if (s0_slice_size == max_uint64) { /* something went wrong */
			printf("internal error\n");
			return (B_FALSE);
		} else {
			printf("before create slice 0\n"); dump_slice_map();
			if (!om_create_slice(0, s0_slice_size, B_TRUE)) {
				return (B_FALSE);
			}
		}
		printf("after create slice 0\n"); dump_slice_map();
		om_debug_print(OM_DBGLVL_INFO,
		    "Creating root slice 0 of size %lld\n", s0_slice_size);
	}
	/* TODO check remaining size - is it big enough to install Solaris? */

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

static void
dump_slice_map()
{
	int isl;
	slice_info_t *sinfo;

	sinfo = &committed_disk_target->dslices->sinfo[0];
	printf("id\toffset\tsize\ttag\n");
	for (isl = 0; isl < NDKMAP; isl++) {
		printf("%d\t%lld\t%lld\t%d\n",
		    sinfo[isl].slice_id,
		    sinfo[isl].slice_offset,
		    sinfo[isl].slice_size,
		    sinfo[isl].tag);
	}
}

static boolean_t
remove_slice_from_table(uint8_t slice_id)
{
	slice_info_t *sinfo;
	int isl;

	sinfo = &committed_disk_target->dslices->sinfo[0];
#if 0
	printf("before remove id=%d\n", slice_id); dump_slice_map();
#endif
	for (isl = 0; isl < NDKMAP; isl++) {
		if (slice_id == sinfo[isl].slice_id) {
			memcpy(&sinfo[isl],
			    &sinfo[isl + 1],
			    (NDKMAP - isl - 1) * sizeof (slice_info_t));
			bzero(&sinfo[NDKMAP - 1],
			    sizeof (disk_slices_t)); /* clear last entry */
			slice_edit_list[slice_id].delete = B_TRUE;
#if 0
	printf("after remove id=%d\n", slice_id); dump_slice_map();
#endif
			return (B_TRUE);
		}
	}
	return (B_FALSE);
}

static boolean_t
insert_slice_into_table(int isl, slice_info_t *psinfo)
{
	slice_info_t *sinfo;

	sinfo = &committed_disk_target->dslices->sinfo[0];
#if 0
	printf("before remove id=%d\n", slice_id); dump_slice_map();
#endif
	memmove(&sinfo[isl + 1], &sinfo[isl],
	    (NDKMAP - isl - 1) * sizeof (slice_info_t));
	memcpy(&sinfo[isl], psinfo, sizeof (slice_info_t));
#if 0
	printf("after remove id=%d\n", slice_id); dump_slice_map();
#endif
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
 * find first unused space at end that has required #sectors unallocated
 * if slice_size is 0, return all unused space in region
 * TODO: optimize for best fit
 */
static struct found_region *
find_unused_region_of_size(uint64_t slice_size)
{
	slice_info_t *psinfo;
	uint64_t new_slice_offset;
	uint64_t disk_size_sec;
	int isl;

	assert(committed_disk_target != NULL);

	psinfo = &committed_disk_target->dslices->sinfo[0];
	new_slice_offset = 0;
	for (isl = 0; isl < NDKMAP; isl++, psinfo++) {
		if (EXEMPT_SLICE(psinfo->slice_id) || psinfo->slice_size == 0)
			continue;
		new_slice_offset = MAX(new_slice_offset, psinfo->slice_size +
		    psinfo->slice_offset);
	}
	disk_size_sec = committed_disk_target->dinfo.disk_size;
	disk_size_sec *= BLOCKS_TO_MB;
	om_debug_print(OM_DBGLVL_INFO, "disk size =%lld sectors\n",
	    disk_size_sec);
	om_debug_print(OM_DBGLVL_INFO, "calculated offset =%lld \n",
	    new_slice_offset);
	if (new_slice_offset >= disk_size_sec)
		return (NULL);
	found_region.slice_offset = new_slice_offset;
	found_region.slice_size = (slice_size == 0 ?
	    disk_size_sec - new_slice_offset : slice_size);
	om_debug_print(OM_DBGLVL_INFO, "new slice offset=%lld size=%lld\n",
	    found_region.slice_offset, found_region.slice_size);
	return (&found_region);
}

/*
 * do a sorted insertion of used space in partition
 */
static void
insert_sorted_slice_info(slice_info_t *psinfo)
{
	int isl;

	for (isl = 0; isl < n_used_regions; isl++)
		if (ordered_space_used[isl].slice_offset > psinfo->slice_offset)
			break;
	/* safe push downward */
	memmove(&ordered_space_used[isl + 1], &ordered_space_used[isl],
	    (n_used_regions - isl) * sizeof (slice_info_t));
	/* move in new slice info entry */
	memcpy(&ordered_space_used[isl], psinfo, sizeof (slice_info_t));
	n_used_regions++;
}

/*
 * make table of used partition space taken from disk target
 */
static void
sort_used_regions()
{
	slice_info_t *psinfo = &committed_disk_target->dslices->sinfo[0];
	int isl;

	n_used_regions = 0;
	for (isl = 0; isl < NDKMAP; isl++, psinfo++) {
		if (EXEMPT_SLICE(psinfo->slice_id) || psinfo->slice_size == 0)
			continue;
		insert_sorted_slice_info(psinfo);
	}
}

/*
 * end of slice editing suite
 */
