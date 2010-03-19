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
#include <Python.h>
#include <libnvpair.h>
#include <sys/types.h>
#include <sys/systeminfo.h>
#include "disk.h"
#include "partition.h"
#include "geometry.h"
#include "slice.h"
#include "zpool.h"
#include "tgt.h"
#include "ti_api.h"
#include <sys/dktp/fdisk.h>

#if defined(i386)
static int create_fdisk_target(PyObject *self, TgtDisk *disk);
#endif

static int create_vtoc_target(PyObject *self, TgtDisk *disk,
    PyObject *create_swap_slice);

#define	ZFS_FS_NUM		1
#define	TGT_NUMPART		(FD_NUMPART + MAX_EXT_PARTS)

static char *zfs_fs_names[ZFS_FS_NUM] = {"/"};

#if defined(i386)
/*
 * create_fdisk_target
 * Create the nvlist for the creation of an fdisk target via the TI module.
 * Call ti_create_target to do the creation.
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
static int
create_fdisk_target(PyObject *self, TgtDisk *disk)
{
	nvlist_t	*attrs;
	int		ret = TI_E_SUCCESS;
	int		i;
	int		num_parts, max_part_id;
	uint8_t		part_ids[TGT_NUMPART], part_active_flags[TGT_NUMPART];
	uint64_t	part_offsets[TGT_NUMPART], part_sizes[TGT_NUMPART];
	boolean_t	preserve_array[TGT_NUMPART];

	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_FDISK) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_string(attrs, TI_ATTR_FDISK_DISK_NAME,
	    disk->name) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	num_parts = PyTuple_GET_SIZE(disk->children);
	max_part_id = 0;
	for (i = 0; i < num_parts; i++) {
		TgtPartition 	*part;

		part = (TgtPartition *)PyTuple_GET_ITEM(disk->children, i);
		if (part->id > max_part_id)
			max_part_id = part->id;
	}
	if (disk->use_whole || num_parts == 0) {
		/*
		 * Do the whole disk, nothing else to do.
		 */
		if (nvlist_add_boolean_value(attrs, TI_ATTR_FDISK_WDISK_FL,
		    B_TRUE) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}
		ret = ti_create_target(attrs, NULL);
		nvlist_free(attrs);
		return (ret);
	}

	if (nvlist_add_uint16(attrs, TI_ATTR_FDISK_PART_NUM,
	    max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	for (i = 0; i < max_part_id; i++) {
		part_ids[i] = UNUSED;
		part_active_flags[i] = part_offsets[i] = part_sizes[i] = 0;
		preserve_array[i] = B_TRUE;
	}

	if (num_parts == 0) {
		/* error */
		nvlist_free(attrs);
		return (TI_E_PY_INVALID_ARG);
	}
	for (i = 0; i < num_parts; i++) {
		TgtPartition 	*part;
		uint64_t	blocks;
		int		pos;
		uint32_t	offset;

		part = (TgtPartition *)PyTuple_GET_ITEM(disk->children, i);
		/*
		 * Check to see if this is a partition or a slice. We only
		 * want partitions right now.
		 */
		if (!TgtPartition_Check(part)) {
			continue;
		}

		blocks =  part->blocks;
		pos =  part->id - 1;
		offset = part->offset;

		if (part->modified) {
			preserve_array[pos] = B_FALSE;
		}

		part_ids[pos] = part->type;
		part_active_flags[pos] = 0;
		part_offsets[pos] = offset;
		part_sizes[pos] = blocks;
	}

	if (nvlist_add_uint8_array(attrs, TI_ATTR_FDISK_PART_IDS, part_ids,
	    max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint8_array(attrs, TI_ATTR_FDISK_PART_ACTIVE,
	    part_active_flags, max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint64_array(attrs, TI_ATTR_FDISK_PART_RSECTS,
	    part_offsets, max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint64_array(attrs, TI_ATTR_FDISK_PART_NUMSECTS,
	    part_sizes, max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_boolean_array(attrs, TI_ATTR_FDISK_PART_PRESERVE,
	    preserve_array, max_part_id) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	ret = ti_create_target(attrs, NULL);
	nvlist_free(attrs);
	return (ret);
}
#endif

static uint16_t
slice_1_tag(
	uint16_t slice_num,
	uint16_t *slice_nums,
	uint64_t *slice_size,
	uint16_t *slice_tags)
{
	int i;

	for (i = 0; i < slice_num; i++) {
		if (slice_nums[i] == 1 && slice_size[i] != 0) {
			return (slice_tags[i]);
		}
	}
	return (V_UNASSIGNED);

}

/*
 * create_disk_label
 * Create the label for the disk.
 * Call ti_create_target to do the creation.
 * Returns: Success - libti return code from imm_create_disk_label_target
 *	    Failure - libti error code from imm_create_disk_label_target or
 *              TI_E_PY_NO_SPACE
 */
/* ARGSUSED */
static int
create_disk_label(PyObject *self, TgtDisk *disk)
{
	nvlist_t	*attrs;
	int		ret = TI_E_SUCCESS;

	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_DISK_LABEL) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_string(attrs, TI_ATTR_LABEL_DISK_NAME,
	    disk->name) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	ret = ti_create_target(attrs, NULL);
	nvlist_free(attrs);
	return (ret);
}

/*
 * create_vtoc_target
 * Create the nvlist for the creation of an vtoc target via the TI module.
 * Call ti_create_target to do the creation.
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
static int
create_vtoc_target(PyObject *self, TgtDisk *disk, PyObject *create_swap_slice)
{
	nvlist_t	*attrs;
	int		ret = TI_E_SUCCESS;
	int		num_slices;
	int		num_children;
	PyObject	*child;
	TgtPartition	*part;
	TgtSlice	*slice;
	uint16_t	snum;
	uint16_t	*s_num, *s_tag, *s_flag, tag;
	uint64_t	*s_start, *s_size;
	int		i, j;
	boolean_t	use_whole = B_FALSE;


	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_VTOC) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	if (nvlist_add_string(attrs, TI_ATTR_FDISK_DISK_NAME,
	    disk->name) != 0) {
		nvlist_free(attrs);
		return (TI_E_PY_NO_SPACE);
	}

	/*
	 * First create the array of slices
	 */
	num_children = PyTuple_GET_SIZE(disk->children);

	s_num = s_tag = s_flag = NULL;
	s_start = s_size = NULL;

	if (((TgtDisk *)disk)->use_whole) {
		use_whole = B_TRUE;
	} else {
		if (num_children == 0) {
			/*
			 * conflicting info from the user.
			 * throw an error.
			 */
			nvlist_free(attrs);
			return (TI_E_PY_INVALID_ARG);
		}
	}
	for (i = 0, snum = 0; i < num_children; i++) {
		child = PyTuple_GET_ITEM(
		    disk->children, i);
		if (!TgtSlice_Check(child)) {
			/*
			 * Must be a partition
			 * Now check for the slices that are on
			 * partitions.
			 */
			part = (TgtPartition *)child;
			if (part->use_whole) {
				use_whole = B_TRUE;
			}
			num_slices =
			    PyTuple_GET_SIZE(part->children);
			if (num_slices == 0) {
				/* no slices on the partition */
				continue;
			}
			for (j = 0; j < num_slices; j++) {
				slice = (TgtSlice *)PyTuple_GET_ITEM(
				    ((TgtPartition *)part)->children, j);
				if (!TgtSlice_Check(slice)) {
					continue;
				}
				snum++;
				s_num = realloc(s_num,
				    snum * sizeof (uint16_t));
				s_tag = realloc(s_tag,
				    snum * sizeof (uint16_t));
				s_flag = realloc(s_flag,
				    snum * sizeof (uint16_t));
				s_start = realloc(s_start,
				    snum * sizeof (uint64_t));
				s_size = realloc(s_size,
				    snum * sizeof (uint64_t));
				if (s_num == NULL || s_tag == NULL ||
				    s_flag == NULL || s_start == NULL ||
				    s_size == NULL) {
				    nvlist_free(attrs);
					return (TI_E_PY_NO_SPACE);
				}
				s_num[snum-1] = slice->number;
				s_tag[snum-1] = slice->tag;
				s_flag[snum-1] =
				    (slice->unmountable & V_UNMNT) |
				    ((slice->readonly << 4) & V_RONLY);
				s_start[snum-1] = slice->offset;
				s_size[snum-1] = slice->blocks;

			}
			continue;
		}
		slice = (TgtSlice *)child;
		if (slice->blocks == 0) {
			continue;
		}

		snum++;
		/* reallocate memory for another line */
		s_num = realloc(s_num, snum * sizeof (uint16_t));
		s_tag = realloc(s_tag, snum * sizeof (uint16_t));
		s_flag = realloc(s_flag, snum * sizeof (uint16_t));
		s_start = realloc(s_start, snum * sizeof (uint64_t));
		s_size = realloc(s_size, snum * sizeof (uint64_t));
		if (s_num == NULL || s_tag == NULL || s_flag == NULL ||
		    s_start == NULL || s_size == NULL) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		s_num[snum-1] = slice->number;
		s_tag[snum-1] = slice->tag;
		s_flag[snum-1] = (slice->unmountable & V_UNMNT) |
		    ((slice->readonly << 4) & V_RONLY);
		s_start[snum-1] = slice->offset;
		s_size[snum-1] = slice->blocks;
	}


	if (create_swap_slice == Py_True) {
		/*
		 * If slice 1 is in the table, check whether it is already
		 * marked as a swap slice in VTOC partition flag.
		 */
		tag = slice_1_tag(snum, s_num, s_size, s_tag);
		switch (tag) {
		case V_SWAP:
		case NULL:
			if (nvlist_add_boolean_value(attrs,
			    TI_ATTR_CREATE_SWAP_SLICE, B_TRUE) != 0) {
				nvlist_free(attrs);
				return (TI_E_PY_NO_SPACE);
			}
			break;
		default:
			/* error message */
			ret = TI_E_PY_SWAP_INVALID;
			break;
		}

	}

	if (use_whole) {
		if (nvlist_add_boolean_value(attrs,
		    TI_ATTR_SLICE_DEFAULT_LAYOUT, B_TRUE) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}
	} else {
		if (nvlist_add_uint16(attrs, TI_ATTR_SLICE_NUM, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		if (nvlist_add_uint16_array(attrs, TI_ATTR_SLICE_PARTS,
		    s_num, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		if (nvlist_add_uint16_array(attrs, TI_ATTR_SLICE_TAGS,
		    s_tag, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		if (nvlist_add_uint16_array(attrs, TI_ATTR_SLICE_FLAGS,
		    s_flag, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		if (nvlist_add_uint64_array(attrs, TI_ATTR_SLICE_1STSECS,
		    s_start, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}

		if (nvlist_add_uint64_array(attrs, TI_ATTR_SLICE_SIZES,
		    s_size, snum) != 0) {
			nvlist_free(attrs);
			return (TI_E_PY_NO_SPACE);
		}
	}

	ret = ti_create_target(attrs, NULL) | ret;
	nvlist_free(attrs);
	return (ret);
}

/*
 * create_disk_target
 * Detect if the system is sparc or x86 and create a fdisk or vtoc
 * target accordingly. If it is a GPT labeled disk on sparc, relabel
 * it as SMI.
 * Returns: non-NULL - Success
 *	    NULL - Failure
 */
/* ARGSUSED */
PyObject *
create_disk_target(PyObject *self, PyObject *args)
{
	int		ret = TI_E_SUCCESS;
	PyObject	*disk;
	PyObject	*create_swap_slice;

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "O!O", &TgtDiskType, &disk,
	    &create_swap_slice)) {
		raise_ti_errcode(ret);
		return (NULL);
	}

#if defined(i386)
	ret = create_fdisk_target(self, (TgtDisk *)disk);
	if (ret != TI_E_SUCCESS) {
		raise_ti_errcode(ret);
		return (NULL);
	}
#endif

#if defined(sparc)
	if (((TgtDisk *)disk)->gpt) {
		/*
		 * If we have a GPT disk, we want to label the disk
		 * as SMI so we can create it as a vtoc target later.
		 * This is done only for sparc because for x86, GPT is
		 * handled at the partition level.
		 */
		ret = create_disk_label(self, (TgtDisk *)disk);
		if (ret != TI_E_SUCCESS) {
			raise_ti_errcode(ret);
			return (NULL);
		}
	}
#endif

	ret = create_vtoc_target(self, (TgtDisk *)disk, create_swap_slice);
	if ((ret != TI_E_SUCCESS) && (ret != TI_E_PY_SWAP_INVALID)) {
		raise_ti_errcode(ret);
		return (NULL);
	}
	return (Py_BuildValue("i", ret));
}

/*
 * create_zfs_root_pool
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
PyObject *
create_zfs_root_pool(PyObject *self, PyObject *args)
{
	nvlist_t	*attrs;
	int		ret;
	PyObject	*zpool;

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "O!", &TgtZpoolType, &zpool)) {
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}

	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_RPOOL) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	/*
	 * Check for zpool name since we must have it.
	 */
	if (((TgtZpool *)zpool)->name == NULL) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}
	if (nvlist_add_string(attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    ((TgtZpool *)zpool)->name) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	/*
	 * Check for zpool device since we must have it.
	 */
	if (((TgtZpool *)zpool)->device == NULL) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}
	if (nvlist_add_string(attrs, TI_ATTR_ZFS_RPOOL_DEVICE,
	    ((TgtZpool *)zpool)->device) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	ret = ti_create_target(attrs, NULL);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		raise_ti_errcode(ret);
		return (NULL);
	}
	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}

/*
 * create_zfs_volume
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
PyObject *
create_zfs_volume(PyObject *self, PyObject *args)
{
	nvlist_t	*attrs;
	PyObject	*zfs_swap, *zfs_dump;
	uint32_t	swap_size, dump_size;
	char		*root_pool;
	uint16_t	vol_num = 0;
	char		*vol_names[2] = { 0 };
	uint16_t	vol_types[2] = { 0 };
	uint32_t	vol_sizes[2] = { 0 };
	int		ret;


	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "sOiOi", &root_pool, &zfs_swap, &swap_size,
	    &zfs_dump, &dump_size)) {
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}


	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_VOLUME) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string(attrs, TI_ATTR_ZFS_VOL_POOL_NAME,
	    root_pool) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (zfs_swap == Py_True) {
		vol_names[vol_num] = TI_ZFS_VOL_NAME_SWAP;
		vol_types[vol_num] = TI_ZFS_VOL_TYPE_SWAP;
		vol_sizes[vol_num] = swap_size;
		vol_num++;
	}
	if (zfs_dump == Py_True) {
		vol_names[vol_num] = TI_ZFS_VOL_NAME_DUMP;
		vol_types[vol_num] = TI_ZFS_VOL_TYPE_DUMP;
		vol_sizes[vol_num] = dump_size;
		vol_num++;
	}

	if (nvlist_add_uint16(attrs, TI_ATTR_ZFS_VOL_NUM, vol_num) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string_array(attrs, TI_ATTR_ZFS_VOL_NAMES, vol_names,
	    vol_num) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint32_array(attrs, TI_ATTR_ZFS_VOL_MB_SIZES,
	    vol_sizes, vol_num) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint16_array(attrs, TI_ATTR_ZFS_VOL_TYPES,
	    vol_types, vol_num) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	ret = ti_create_target(attrs, NULL);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		raise_ti_errcode(ret);
		return (NULL);
	}

	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}

/*
 * create_be_target
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
PyObject *
create_be_target(PyObject *self, PyObject *args)
{
	nvlist_t	*attrs;
	char		*root_pool;
	char		*installed_root_dir;
	char		*be_name;
	PyObject	*dataset_tuple;
	int		num_datasets;
	TgtZFSDataset	*dataset;
	char		**shared_fs_names;
	int		ret = TI_E_SUCCESS;
	int		i;

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "sssO", &root_pool, &be_name,
	    &installed_root_dir, &dataset_tuple)) {
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}

	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_BE) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string(attrs, TI_ATTR_BE_RPOOL_NAME,
	    root_pool) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string(attrs, TI_ATTR_BE_NAME,
	    be_name) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string_array(attrs, TI_ATTR_BE_FS_NAMES,
	    zfs_fs_names, ZFS_FS_NUM) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	num_datasets = PyTuple_GET_SIZE(dataset_tuple);
	shared_fs_names = malloc(num_datasets * (sizeof (char *)));
	for (i = 0; i < num_datasets; i++) {
		dataset = (TgtZFSDataset *)PyTuple_GET_ITEM(dataset_tuple, i);
		shared_fs_names[i] = strdup(dataset->mountpoint);
	}
	if (nvlist_add_string_array(attrs, TI_ATTR_BE_SHARED_FS_NAMES,
	    shared_fs_names, num_datasets) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_string(attrs, TI_ATTR_BE_MOUNTPOINT,
	    installed_root_dir) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	ret = ti_create_target(attrs, NULL);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		raise_ti_errcode(ret);
		return (NULL);
	}

	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}

/*
 * release_zfs_root_pool
 * Returns: 0 - Success
 *	   -1 - Failure
 */
/* ARGSUSED */
PyObject *
release_zfs_root_pool(PyObject *self, PyObject *args)
{
	nvlist_t	*attrs;
	int		ret;
	PyObject	*zpool;

	/*
	 * Parse the List input
	 */
	if (!PyArg_ParseTuple(args, "O!", &TgtZpoolType, &zpool)) {
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}

	if (nvlist_alloc(&attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	if (nvlist_add_uint32(attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_RPOOL) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	/*
	 * Check for zpool name since we must have it.
	 */
	if (((TgtZpool *)zpool)->name == NULL) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_INVALID_ARG);
		return (NULL);
	}
	if (nvlist_add_string(attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    ((TgtZpool *)zpool)->name) != 0) {
		nvlist_free(attrs);
		raise_ti_errcode(TI_E_PY_NO_SPACE);
		return (NULL);
	}

	ret = ti_release_target(attrs);
	if (ret != TI_E_SUCCESS) {
		nvlist_free(attrs);
		raise_ti_errcode(ret);
		return (NULL);
	}

	nvlist_free(attrs);
	return (Py_BuildValue("i", TI_E_SUCCESS));
}
