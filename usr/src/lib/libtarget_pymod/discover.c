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

#include "geometry.h"
#include "disk.h"
#include "partition.h"
#include "slice.h"
#include "tgt.h"
#include "td_api.h"

static TgtGeometry	*TgtGeometry_Create(nvlist_t *);
static TgtDisk		*TgtDisk_Create(nvlist_t *, TgtGeometry *);
static TgtPartition	*TgtPartition_Create(nvlist_t *, TgtGeometry *);
static TgtSlice		*TgtSlice_Create(nvlist_t *, TgtGeometry *);

static PyObject		*TgtDisk_enumerate(int);
#ifndef	sparc
static PyObject		*TgtPartition_enumerate(TgtDisk *);
#endif
static PyObject		*TgtSlice_enumerate(TgtDisk *);

/* Macro to simplify creating a new target object */
#define	Tgt_NEW(tp)	(tp *)tp##Type.tp_new(&tp##Type, NULL, NULL)


/*
 * Function:    discover_target_data
 * Description: discover all disks, partitions, and slices.
 * Parameters:  None
 * Returns:     list of Disk objects
 * Scope:       Private
 */
PyObject *
discover_target_data(void)
{
	PyObject *result = NULL; /* tuple of TgtDisk */
	PyObject *list = NULL;
	PyObject *tmp = NULL;

	int idx, ndisk, num, rc;

	/*
	 * Allow this function to run in a Python thread without blocking
	 * the Python interpreter
	 */
	Py_BEGIN_ALLOW_THREADS
	rc = td_discover(TD_OT_DISK, &ndisk);
	Py_END_ALLOW_THREADS

	/* get number of disks */
	switch (rc) {
	case TD_E_SUCCESS:
		break;
	case TD_E_NO_DEVICE:
		/* There are no disks, return empty tuple */
		result = PyTuple_New(0); /* will set PyErr_NoMemory() on fail */
		return (result);
	default:
		raise_td_errcode();
		return (NULL);
	}


	list = TgtDisk_enumerate(ndisk);
	if (list == NULL && PyErr_Occurred() != NULL)
		return (NULL);


	/*
	 * From this point on we must Py_DECREF(result) and set result
	 * back to NULL on error.
	 */
	result = PyList_AsTuple(list);
	Py_DECREF(list);

	/* use a precise count for getting partitions/slices */
	ndisk = PyTuple_GET_SIZE(result);

	/* get partitions */
#ifndef sparc /* Makefile sets this, do not look for partitions on SPARC */
	for (idx = 0; idx < ndisk; idx++) {
		PyObject *list = NULL;
		TgtDisk *disk = (TgtDisk *)PyTuple_GET_ITEM(result, idx);
		assert(TgtDisk_CheckExact(disk));

		list = TgtPartition_enumerate(disk);
		if (list == NULL) {
			Py_DECREF(result);
			return (NULL);
		}

		/* partition order is about sorting and makes no sense in C */

		/* create tuple and assign to disk->children */
		tmp = disk->children;
		disk->children = PyList_AsTuple(list);
		Py_XDECREF(tmp);
		Py_DECREF(list);
	}
#endif	/* sparc not defined */

	/*
	 * Look up slices. If children is 0 go for it.
	 * If children is not 0 (there are partitions), we look up slices and
	 * assume they belong to the active partition. If there is just 1
	 * Solaris/Solaris2 partition the slices clearly belong to that
	 * Partition. Only 1 solaris allowed per disk, but if more are found
	 * we can't assign slices to any of them.
	 */
	for (idx = 0; idx < ndisk; idx++) {
		int nchild = 0;
		PyObject **tuplep = NULL;
		nvlist_t **iterl = NULL;
		nvlist_t **attrl = NULL;
		TgtGeometry *geo = NULL;
		TgtDisk *disk = (TgtDisk *)PyTuple_GET_ITEM(result, idx);
		assert(TgtDisk_CheckExact(disk));
		geo = (TgtGeometry *)disk->geometry;

		/* Figure out where slices go / if to look for them */
		nchild = PyTuple_GET_SIZE(disk->children);
		if (nchild == 0) {
			/* no partitions look for slices */
			tuplep = &(disk->children);
		} else {
			/*
			 * Have partitions, if number of Solaris/Solaris2 > 1
			 * and none are active we don't look for slices.
			 * If number of Solaris/Solaris2 equals 1 or one of
			 * the Solaris/Solaris2 is the active partition then
			 * search for slices.
			 */
			int pidx;
			int nsolaris = 0;
			TgtPartition *solpart = NULL;

			for (pidx = 0; pidx < nchild; pidx++) {
				TgtPartition *part;
				part = (TgtPartition *)PyTuple_GET_ITEM(
				    disk->children, pidx);
				switch (part->type) {
				case 0x82: /* fallthrough */
				case 0xBF:
					solpart = part;
					nsolaris++;
					/* solaris partition, check active */
					if (part->active == 1) {
						break;
					}
				default:
					continue;
				}
			}
			/* Setting tuplep will trigger a search */
			if (solpart && solpart->active == 1 || nsolaris == 1) {
				tuplep = &(solpart->children);
			}
		}

		if (tuplep == NULL) {
			/*
			 * Don't look for slices on this disk
			 * This happens when the partition that would be
			 * associated with the slices can't be determined.
			 */
			assert(nchild > 0);
			continue;
		}

		/* it should be a valid tuple we are pointing to with size 0 */
		assert(*tuplep != NULL);
		assert(PyTuple_Check(*tuplep));
		assert(PyTuple_GET_SIZE(*tuplep) == 0);


		list = TgtSlice_enumerate(disk);
		if (list == NULL) {
			Py_DECREF(result);
			return (NULL);
		}

		tmp = *tuplep;
		*tuplep = PyList_AsTuple(list);
		Py_XDECREF(tmp);
		Py_DECREF(list);
	}

	return (result);
}
PyDoc_STRVAR(discover_target_data_doc,
"discover_target_data() -> tuple of tgt.Disk objects");

/*
 * Function:	TgtDisk_enumerate
 * Description:	enumerate target disks available.
 * Parameters:
 * 	ndisk	number of disks (although some may not be valid).
 * Returns:	PyObject pointer that is a list of disks. Or NULL
 *		in case of error (exception set for Python).
 * Scope:	Private
 *
 * N.B.: libtd.so does not distinguish between disk and geometry,
 *       we do. So this reads up both at the same time.
 */
static PyObject*
TgtDisk_enumerate(int ndisk)
{
	PyObject *result = NULL; /* our list */
	int idx, rc;

	if ((result = PyList_New(0)) == NULL)
		return (PyErr_NoMemory());

	for (idx = 0; idx < ndisk; idx++) {
		TgtGeometry *geo = NULL;
		TgtDisk *disk = NULL;
		nvlist_t *attr = NULL;

		rc = td_get_next(TD_OT_DISK); /* doesn't go to disk */
		if (rc != TD_E_SUCCESS) {
			continue; /* bad disk */
		}

		Py_BEGIN_ALLOW_THREADS
		attr = td_attributes_get(TD_OT_DISK);
		Py_END_ALLOW_THREADS
		if (attr == NULL) {
			continue; /* bad disk */
		}

		geo = TgtGeometry_Create(attr);
		/*
		 * disk could have had unacceptable geometry, in which case
		 * NULL is returned and no error is set.
		 */
		if (geo != NULL) {
			disk = TgtDisk_Create(attr, geo);
		}
		nvlist_free(attr); /* done in any case */

		if (geo == NULL) {
			if (PyErr_Occurred() == NULL)
				continue;
			goto TgtDisk_enumerate_CLEANUP;
		}
		Py_DECREF(geo); /* disk holds ref but we are done with it */

		if (PyList_Append(result, (PyObject *)disk)) {
			PyErr_NoMemory();
			goto TgtDisk_enumerate_CLEANUP;
		}
	}

	return (result);

TgtDisk_enumerate_CLEANUP:
	Py_XDECREF(result);
	return (NULL);
}

#ifndef	sparc /* only build this if not sparc */
/*
 * Function:	TgtPartition_enumerate
 * Description:	enumerate target partitions for a single disk.
 * Parameters:
 * 	ndisk	number of disks (although some may not be valid).
 * Returns:	PyObject pointer that is a list of Partitions. Or
 * 		NULL in case of error (exception set for Python).
 * Scope:	Private
 */
static PyObject*
TgtPartition_enumerate(TgtDisk *disk)
{
	PyObject *result = NULL; /* list of partitions */
	TgtGeometry *geo = NULL;
	nvlist_t **iterl = NULL;
	nvlist_t **attrl = NULL;
	int idx, num;

	assert(disk != NULL);
	geo = (TgtGeometry *)disk->geometry;


	if ((result = PyList_New(0)) == NULL)
		return (PyErr_NoMemory());

	/* this returns an nvlist_t which contains nvlist_t */
	Py_BEGIN_ALLOW_THREADS
	attrl = td_discover_partition_by_disk(disk->name, &num);
	Py_END_ALLOW_THREADS

	for (idx = 0, iterl = attrl; idx < num; idx++, iterl++) {
		TgtPartition *part = TgtPartition_Create(*iterl, geo);
		if (part == NULL) {
			if (PyErr_Occurred() == NULL)
				continue;
			goto TgtPartition_enumerate_CLEANUP;
		}
		if (PyList_Append(result, (PyObject *)part)) {
			Py_DECREF(part);
			PyErr_NoMemory();
			goto TgtPartition_enumerate_CLEANUP;
		}
	}
	td_attribute_list_free(attrl);
	return (result);

TgtPartition_enumerate_CLEANUP:
	/* You need to have set error before jumping here */
	td_attribute_list_free(attrl);
	Py_XDECREF(result);

	return (NULL);
}
#endif	/* sparc : only build this if not sparc */

/*
 * Function:	TgtSlice_enumerate
 * Description:	enumerate target slices for a single disk.
 * Parameters:
 * 	disk	target disk to enumerate.
 * Returns:	PyObject pointer that is a list of Slices. Or
 * 		NULL in case of error (exception set for Python).
 * Scope:	Private
 */
static PyObject*
TgtSlice_enumerate(TgtDisk *disk)
{
	PyObject *result = NULL; /* list of slices */
	TgtGeometry *geo = NULL;
	nvlist_t **iterl = NULL;
	nvlist_t **attrl = NULL;
	int idx, num;

	assert(disk != NULL);
	geo = (TgtGeometry *)disk->geometry;

	if ((result = PyList_New(0)) == NULL)
		return (PyErr_NoMemory());

	Py_BEGIN_ALLOW_THREADS
	attrl = td_discover_slice_by_disk(disk->name, &num);
	Py_END_ALLOW_THREADS
	if (num <= 0 || num > NDKMAP) {
		td_attribute_list_free(attrl);
		return (result); /* empty list */
	}

	for (idx = 0, iterl = attrl; idx < num; idx++, iterl++) {
		TgtSlice *slice = TgtSlice_Create(*iterl, geo);
		if (slice == NULL) {
			if (PyErr_Occurred() == NULL)
				continue;
			goto TgtSlice_enumerate_CLEANUP;
		}
		if (PyList_Append(result, (PyObject *)slice)) {
			Py_DECREF(slice);
			PyErr_NoMemory();
			goto TgtSlice_enumerate_CLEANUP;
		}
	}
	td_attribute_list_free(attrl);

	return (result);

TgtSlice_enumerate_CLEANUP:
	/* You need to have set error before jumping here */
	td_attribute_list_free(attrl);
	Py_XDECREF(result);

	return (NULL);
}

/*
 * Function:	TgtGeometry_Create
 * Description:	fill in a tgt.Geometry object correctly.
 * Parameters:	None
 * Returns:	TgtGeometry that is the tgt.Geometry object.
 * Scope:	Private
 *
 * N.B.: If we get a disk with unacceptable values we return NULL.
 *       So you must check for an error condition using PyErr_Occurred()
 *       to see if that is NULL.
 */
static TgtGeometry *
TgtGeometry_Create(nvlist_t *disk_list)
{
	TgtGeometry *geometry = NULL;
	char *str = NULL;
	uint32_t bsz, val, nsect, nhead, cylsz;
	uint64_t nblock;

	assert(disk_list != NULL);

	/*
	 * TgtGeometry_Create(), is caled first so it needs to do the sanity
	 * checking of the disk. If we are skipping this one there is no
	 * point in creating a geometry.
	 *
	 * Most data it looks up is ignored but will be used in
	 * TgtDisk_Create() should this pass.
	 */
	if (nvlist_lookup_uint32(disk_list, TD_DISK_ATTR_MTYPE, &val) == 0) {
		if (val != TD_MT_FIXED)
			goto TgtGeometry_Create_SKIP_DISK;
	} else {
		goto TgtGeometry_Create_SKIP_DISK;
	}

	bsz = nblock = 0;
	(void) nvlist_lookup_uint32(disk_list, TD_DISK_ATTR_BLOCKSIZE, &bsz);
	(void) nvlist_lookup_uint64(disk_list, TD_DISK_ATTR_SIZE, &nblock);
	if (bsz == 0 || nblock == 0) {
		/* bad geometry -- may consider a debug print here? */
		goto TgtGeometry_Create_SKIP_DISK;
	}

	/* this is odd as we don't even use this stuff */
	if ((nvlist_lookup_uint32(disk_list, TD_DISK_ATTR_NHEADS, &nsect)
	    != 0) || (nvlist_lookup_uint32(disk_list, TD_DISK_ATTR_NSECTORS,
	    &nhead) != 0)) {
		/* fake the cylsz to be identical to block size */
		cylsz = bsz;
	} else {
		cylsz = nsect * nhead;
	}

	if (nvlist_lookup_string(disk_list, TD_DISK_ATTR_NAME, &str) != 0) {
		/* have to be able to reference the disk */
		goto TgtGeometry_Create_SKIP_DISK;
	}

	geometry = Tgt_NEW(TgtGeometry);
	if (geometry == NULL) {
		return ((TgtGeometry *)PyErr_NoMemory());
	}

	geometry->blocksz = bsz;
	geometry->cylsz = cylsz;

	return (geometry);

TgtGeometry_Create_SKIP_DISK:
	/* This label assumes you have not created any objects */
	PyErr_Clear(); /* make sure no error set */
	return (NULL);
}

/*
 * Function:	TgtDisk_Create
 * Description:	fill in a tgt.Disk object correctly.
 * Parameters:	None
 * Returns:	TgtDisk that is the tgt.Disk object.
 * Scope:	Private
 *
 * N.B.: If we get a disk with unacceptable values (like bad geometry) we return
 *       NULL. So you must check for an error condition using PyErr_Occurred()
 *       to see if that is NULL.
 */
static TgtDisk *
TgtDisk_Create(nvlist_t *disk_list, TgtGeometry *geo)
{
	TgtDisk *disk = NULL;
	PyObject *constantref = NULL;
	PyObject *tmp = NULL;
	char *str = NULL;
	uint32_t val;
	uint64_t nblock;

	assert(disk_list != NULL);

	/*
	 * TgtGeometry_Create() already verified the disk.
	 */
	disk = Tgt_NEW(TgtDisk);
	if (disk == NULL) {
		PyErr_NoMemory();
		goto TgtDisk_Create_CLEANUP;
	}

	/*
	 * can cheat a bit here b/c we know nobody has seen this Object yet
	 * and b/c we know if goemetry is set to TgtGeometryDefault.
	 */
	assert(disk->geometry == TgtGeometryDefault);
	Py_DECREF(disk->geometry);
	Py_INCREF(geo);
	disk->geometry = (PyObject *)geo;

	(void) nvlist_lookup_uint64(disk_list, TD_DISK_ATTR_SIZE, &nblock);
	assert(nblock != 0);
	disk->blocks = nblock;
	(void) nvlist_lookup_string(disk_list, TD_DISK_ATTR_NAME, &str);
	assert(str != NULL);
	disk->name = strdup(str); /* this still has name */
	if (disk->name == NULL) {
		PyErr_NoMemory();
		goto TgtDisk_Create_CLEANUP;
	}

	/* controller already set to default */
	constantref = DiskConst.unknown; /* default */
	if ((nvlist_lookup_string(disk_list, TD_DISK_ATTR_CTYPE, &str) == 0) &&
	    (str != NULL)) {
		while (1) {
#define			CONSTANT(v, cname, pyname, value) \
			if (strcmp(str, value) == 0) { \
				constantref = DiskConst.cname; \
				break; \
			}
			CONTROLLER_CONSTANTS
#undef			CONSTANT
			break; /* leave it as "unknown" */
		}
	}
	tmp = disk->controller;
	Py_INCREF(constantref);
	disk->controller = constantref;
	Py_XDECREF(tmp);

	disk->vtoc = disk->gpt = disk->fdisk = 0;
	if (nvlist_lookup_uint32(disk_list, TD_DISK_ATTR_LABEL, &val) == 0) {
		/*
		 * we just trust that it is something we understand.
		 * That way instantiation can use it. But if it isn't in
		 * LABEL_CONSTANTS it will print as "unknown".
		 */
		disk->vtoc = (val & TD_DISK_LABEL_VTOC) ? 1 : 0;
		disk->gpt = (val & TD_DISK_LABEL_GPT) ? 1 : 0;
		disk->fdisk = (val & TD_DISK_LABEL_FDISK) ? 1 : 0;
	}

	disk->removable = disk->boot = 0;
	if (nvlist_lookup_boolean(disk_list, TD_DISK_ATTR_REMOVABLE) == 0) {
		disk->removable = 1;
	}
	if (nvlist_lookup_boolean(disk_list, TD_DISK_ATTR_CURRBOOT) == 0) {
		disk->boot = 1;
	}

	disk->serialno = NULL; /* not implemented in libtd.so */
	disk->vendor = NULL;
	if ((nvlist_lookup_string(disk_list, TD_DISK_ATTR_VENDOR, &str) == 0) &&
		(str != NULL)) {
		/* if it is the string "unknown" then leave NULL */
		if (strcmp(str, "unknown") != 0) {
			disk->vendor = strdup(str); /* its OK if it failed */
		}
	}

	/* Verify children is null tuple */
	assert(disk->children != NULL);
	assert(PyTuple_Check(disk->children));
	assert(PyTuple_GET_SIZE(disk->children) == 0);

	return (disk);

TgtDisk_Create_CLEANUP:
	Py_XDECREF(disk);
	return (NULL);

TgtDisk_Create_SKIP_DISK:
	/* This label assumes you have not created any objects */
	PyErr_Clear(); /* make sure no error set */
	return (NULL);
}


/*
 * Function:	TgtPartition_Create
 * Description:	fill in a tgt.Partition object correctly.
 * Parameters:	None
 * Returns:	TgtPartition that is the tgt.Partition object.
 * Scope:	Private
 *
 * N.B.: If we get a partition with unacceptable values we return
 *       NULL. So you must check for an error condition using PyErr_Occurred()
 *       to see if that is NULL.
 */
static TgtPartition *
TgtPartition_Create(nvlist_t *part_list, TgtGeometry *geo)
{
	TgtPartition *part = NULL;
	PyObject *list = NULL;
	PyObject *tmp = NULL;
	char *str = NULL;
	char *ptr = NULL;
	nvlist_t **attr_list_list = NULL;
	nvlist_t **attr_list_iter = NULL;
	int idx, num;
	uint32_t val;

	if (nvlist_lookup_string(part_list, TD_PART_ATTR_NAME, &str) != 0) {
		goto TgtPartition_Create_SKIP_PARTITON;
	}

	/* If the partition name is not ending with pX ignore this partition */
	ptr = str + strlen(str) - 2;
	if (*ptr == 'p') {
		ptr++;
	} else {
		ptr = str + strlen(str) - 3;
		if (*ptr == 'p') {
			ptr++;
		} else {
			goto TgtPartition_Create_SKIP_PARTITON;
		}
	}

	part = Tgt_NEW(TgtPartition);
	if (part == NULL) {
		return (NULL); /* sets mem error */
	}

	assert(part->geometry == TgtGeometryDefault);
	Py_DECREF(part->geometry);
	Py_INCREF(geo);
	part->geometry = (PyObject *)geo;


	/* The partition is of the form cXtXdXpX */
	errno = 0;
	part->id = (uint8_t)strtol(ptr, (char **)NULL, 10);
	if (errno != 0) {
		/* just skip */
		goto TgtPartition_Create_CLEANUP;
	}

	part->active = 0;
	if (nvlist_lookup_uint32(part_list, TD_PART_ATTR_BOOTID, &val) == 0) {
		if (val & ACTIVE)
			part->active = 1;
	}

	if (nvlist_lookup_uint32(part_list, TD_PART_ATTR_TYPE, &val) == 0) {
		part->type = (uint16_t)val; /* type/content 0-255 */
	}

	if (part->type == 0x82) {
		/*
		 * Original Solaris and Linux Swap share 0x82.
		 * Disambiguate now. On failure assume Solaris.
		 */
		if (nvlist_lookup_uint32(part_list, TD_PART_ATTR_CONTENT, &val)
		    == 0) {
			if (val != 0) {
				part->type = 0x182;
			}
		}
	}

	if (nvlist_lookup_uint32(part_list, TD_PART_ATTR_START, &val) == 0) {
		part->offset = val; /* not 64-bit? */
	}

	if (nvlist_lookup_uint32(part_list, TD_PART_ATTR_SIZE, &val) == 0) {
		part->blocks = val; /* not 64-bit? */
	}

	/* Verify children is null tuple */
	assert(part->children != NULL);
	assert(PyTuple_Check(part->children));
	assert(PyTuple_GET_SIZE(part->children) == 0);

	return (part);

TgtPartition_Create_CLEANUP:
	Py_XDECREF(part);
	return (NULL);

TgtPartition_Create_SKIP_PARTITON:
	/* This label assumes you have not created any objects */
	PyErr_Clear(); /* make sure no error set */
	return (NULL);
}


/*
 * Function:	TgtSlice_Create
 * Description:	fill in a tgt.Slice object correctly.
 * Parameters:	None
 * Returns:	TgtSlice that is the tgt.Slice object.
 * Scope:	Private
 */
TgtSlice *
TgtSlice_Create(nvlist_t *slice_list, TgtGeometry *geo)
{
	TgtSlice *slice = NULL;
	PyObject *tmpo = NULL;
	char *str = NULL;
	uint32_t v32;
	uint64_t v64;


	if (nvlist_lookup_string(slice_list, TD_SLICE_ATTR_NAME, &str) != 0) {
		/*
		 * presence needed for valid slice, but we don't need this to
		 * get valid id like partition.
		 */
		goto TgtSlice_Create_SKIP_SLICE;
	}

	slice = Tgt_NEW(TgtSlice);
	if (slice == NULL) {
		return (NULL); /* sets mem error */
	}

	assert(slice->geometry == TgtGeometryDefault);
	Py_DECREF(slice->geometry);
	Py_INCREF(geo);
	slice->geometry = (PyObject *)geo;

	if (nvlist_lookup_uint32(slice_list, TD_SLICE_ATTR_INDEX, &v32) == 0) {
		slice->number = v32;
	}

	if (nvlist_lookup_uint64(slice_list, TD_SLICE_ATTR_START, &v64) == 0) {
		slice->offset = v64;
	}

	if (nvlist_lookup_uint64(slice_list, TD_SLICE_ATTR_SIZE, &v64) == 0) {
		slice->blocks = v64;
	}

	if (nvlist_lookup_uint32(slice_list, TD_SLICE_ATTR_FLAG, &v32) == 0) {
		if ((v32 & V_UNMNT) != 0) { /* unmountable flag set */
			/* so probably slice 2, "backup" */
			slice->unmountable = 1;
		}
		if ((v32 & V_RONLY) != 0) { /* read only flag set */
			slice->readonly = 1;
		}
	}

	if (nvlist_lookup_uint32(slice_list, TD_SLICE_ATTR_TAG, &v32) == 0) {
		slice->tag = (uint8_t)v32;
	}

	if (nvlist_lookup_string(slice_list, TD_SLICE_ATTR_USEDBY, &str) == 0) {
		while (1) {
#define			CONSTANT(v, cname, pyname, value) \
			if (strcmp(str, value) == 0) { \
				slice->type = v; \
				break; \
			}
			SLICE_USED_BY_CONSTANTS
#undef			CONSTANT
			slice->type = (uint8_t)-1;
			break;
		}
	}

	slice->user = NULL;
	if (nvlist_lookup_string(slice_list, TD_SLICE_ATTR_INUSE, &str) == 0) {
		slice->user = strdup(str); /* keep a copy */
	}

	slice->last_mount = NULL;
	if (nvlist_lookup_string(slice_list, TD_SLICE_ATTR_LASTMNT,
	    &str) == 0) {
		if (strcmp(str, "") != 0) {
			slice->last_mount = strdup(str); /* keep a copy */
		}
	}

	return (slice);

TgtSlice_Create_SKIP_SLICE:
	/* This label assumes you have not created any objects */
	PyErr_Clear(); /* make sure no error set */
	return (NULL);
}
