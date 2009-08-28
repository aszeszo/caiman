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
/*
 * td_mg.c is the main module for the Target Discovery phase of the Caiman
 * project.  It contains the main support code for the Manager (MG) module
 * of Target Discovery
 */
#include <stdio.h>
#include <stdarg.h>
#include <strings.h>
#include <sys/param.h>
#include <sys/systeminfo.h>
#include <sys/types.h>
#include <unistd.h>
#include <libfstyp.h>
#include <libnvpair.h>
#include <sys/vtoc.h> /* read disk's VTOC for root FS */
#include <sys/mnttab.h>
#include <sys/vfstab.h>
#include <sys/mntent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#include <signal.h>
#include <time.h>
#include <ustat.h>
#include <sys/wait.h>
#include <libintl.h>

#include <instzones_api.h>

#include <td_lib.h> /* TD internal definitions */
#include <td_api.h> /* TD user definitions */
#include <td_dd.h> /* TD disk module definitions */
#include <td_version.h> /* version info */

#include <ls_api.h>	/* logging service */
#include <assert.h>

/* mount var on separate slice return codes */
#define	MNTRC_MOUNT_SUCCEEDS 1
#define	MNTRC_NO_MOUNT 0
#define	MNTRC_OPENING_VFSTAB (-1)
#define	MNTRC_MOUNT_FAIL (-2)
#define	MNTRC_MUST_MANUAL_FSCK (-3)
#define	MNTRC_FSCK_FAILURE (-4)

#define	ATTR_LIST_TERMINATOR ((nvlist_t *)-1)

/* template temporary directory names for mkdtemp() */
#define	TEMPLATEROOT	"/tmp/td_rootXXXXXX"
#define	TEMPLATEVAR	TEMPLATEROOT "/var"

/* object instances */
struct td_obj {
	ddm_handle_t handle;		/* disk module handle */
	nvlist_t *attrib;		/* attribute list for disk */
	boolean_t discovery_done;	/* discovery performed for object */
};

/* class for TD objects */
struct td_class {
	td_object_type_t objtype;	/* self-type identifier */
	int objcnt;			/* count of objects */
	struct td_obj *objarr;		/* object array */
	struct td_obj *objcur;		/* current object */
	ddm_handle_t *pddm;		/* disk module handle */
	boolean_t issorted;		/* object list has been sorted */
	int (*compare_routine)(const void *, const void *); /* sorting */
};

/* sort comparison routines for objects */
static int compare_disk_objs(const void *p1, const void *p2);
static int compare_partition_objs(const void *p1, const void *p2);
static int compare_slice_objs(const void *p1, const void *p2);
static int compare_os_objs(const void *p1, const void *p2);

/* object type declarations */
static struct td_class objlist[] = {
	{TD_OT_DISK, 0, NULL, NULL, NULL, B_FALSE, compare_disk_objs},
	{TD_OT_PARTITION, 0, NULL, NULL, NULL, B_FALSE, compare_partition_objs},
	{TD_OT_SLICE, 0, NULL, NULL, NULL, B_FALSE, compare_slice_objs},
	{TD_OT_OS, 0, NULL, NULL, NULL, B_FALSE, compare_os_objs}
};
#define	is_valid_td_object_type(ot) \
	((ot) >= 0 && (ot) < sizeof (objlist) / sizeof (objlist[0]))

static int td_errno = 0;
static char CLUSTER_tmp_path[MAXPATHLEN] = "";
static char clustertoc_tmp_path[MAXPATHLEN] = "";
static char rootdir[BUFSIZ] = "";
static char mntrc_text[32];

/* disk module handle lists shorthand */
#define	PDDMDISKS (objlist[TD_OT_DISK].pddm)
#define	PDDMPARTS (objlist[TD_OT_PARTITION].pddm)
#define	PDDMSLICES (objlist[TD_OT_SLICE].pddm)

/* arrays of TD objects shorthand */
#define	PDISKARR (objlist[TD_OT_DISK].objarr)
#define	PPARTARR (objlist[TD_OT_PARTITION].objarr)
#define	PSLICEARR (objlist[TD_OT_SLICE].objarr)

/* count of objects per type shorthand */
#define	NDISKS (objlist[TD_OT_DISK].objcnt)
#define	NPARTS (objlist[TD_OT_PARTITION].objcnt)
#define	NSLICES (objlist[TD_OT_SLICE].objcnt)
#define	NOS (objlist[TD_OT_OS].objcnt)

/* user current object pointers shorthand */
#define	CURDISK (objlist[TD_OT_DISK].objcur)
#define	CURPART (objlist[TD_OT_PARTITION].objcur)
#define	CURSLICE (objlist[TD_OT_SLICE].objcur)
#define	CUROS (objlist[TD_OT_OS].objcur)

static td_errno_t set_td_errno(int);
static void clear_td_errno();
static td_errno_t os_discover(void);
static struct td_obj *search_disks(const char *);
static char *td_get_default_inst(void);
static boolean_t string_array_add(const char *, char ***);
static boolean_t is_path_on_svm(FILE *, const char *);
static char *clustertoc_read_path(int, const char *);
static char *CLUSTER_read_path(int, const char *);
static char *td_get_value(const char *, char);
static boolean_t bootenv_exists(const char *);
static struct td_obj *disk_random_slice(nvlist_t *);
static void disks_discover_all_attrs(void);
static void sort_objs(td_object_type_t);
static int td_fsck_mount(char *, char *, boolean_t, char *, char *, char *,
    nvlist_t **);
static nvlist_t *dup_attr_set_errno(struct td_obj *);
static void free_td_obj_list(td_object_type_t);
static nvlist_t **td_discover_object_by_disk(td_object_type_t,
    const char *, int *);
static boolean_t is_wrong_metacluster(char *);
static struct td_obj *search_disks_for_slices(char *);
static void td_debug_cat_file(ls_dbglvl_t, char *);
static int td_is_isa(char *);
static char *mntrc_strerror(int);
static char *jump_dev_prefix(const char *slicenm);

/*
 * external Target Discovery interfaces
 */

/*
 * Posts debugging message for Management module
 */
void
td_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[256]; /* one output line */

	va_start(ap, fmt);
	(void) vsnprintf(buf, sizeof (buf), fmt, ap);
	(void) ls_write_dbg_message("TDMG", dbg_lvl, buf);
	va_end(ap);
}

/*
 * discover objects of specific type
 * interface to TD user
 * parameters:
 *	otype	indicate object type to discover
 *	number_found	if non-NULL, set to number of objects discovered
 * returns TD_ERRNO
 * calls lower-level modules that support the specified object type
 *
 * After discovery, the user enumerates through the discovered objects,
 * requesting attribute information.
 */
td_errno_t
td_discover(td_object_type_t otype, int *number_found)
{
	ddm_handle_t *pddm; /* temporaries */
	struct td_obj *ptdobj;
	int iobj;
	td_errno_t ret = TD_E_SUCCESS; /* return value */

	clear_td_errno();
	if (number_found != NULL)
		*number_found = 0;

	switch (otype) {
	case TD_OT_DISK: /* get disks */
		if (PDDMDISKS == NULL) {
			PDDMDISKS = ddm_get_disks();
			if (PDDMDISKS == NULL) {
				return (set_td_errno(TD_E_NO_DEVICE));
			}
		}
		for (NDISKS = 0, pddm = PDDMDISKS; *pddm != NULL;
		    pddm++, NDISKS++)
			;
		if (number_found != NULL)
			*number_found = NDISKS;

		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "got disks nfound=%d\n", NDISKS);

		/* allocate space for all disks plus terminator element */
		PDISKARR =
		    realloc(PDISKARR, (NDISKS + 1) * sizeof (struct td_obj));
		if (PDISKARR == NULL)
			return (set_td_errno(TD_E_MEMORY));

		pddm = PDDMDISKS;
		ptdobj = PDISKARR;
		for (iobj = 0; iobj < NDISKS; iobj++, pddm++, ptdobj++) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "disks %d nfound=%d\n", iobj, NDISKS);

			ptdobj->handle = *pddm;
			ptdobj->attrib = NULL;
			ptdobj->discovery_done = B_FALSE;
		}
		/* mark end of array */
		ptdobj->handle = NULL;
		ptdobj->attrib = NULL;
		CURDISK = NULL;
		break;
	case TD_OT_PARTITION:
		if (PDDMPARTS == NULL) {
			PDDMPARTS = ddm_get_partitions(DDM_DISCOVER_ALL);
			if (PDDMPARTS == NULL) {
				return (set_td_errno(TD_E_END));
			}
		}
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO, "got partitions\n");

		for (NPARTS = 0, pddm = PDDMPARTS; *pddm != NULL;
		    pddm++, NPARTS++)
			;
		if (number_found != NULL)
			*number_found = NPARTS;
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "got disks nfound=%d\n", NPARTS);

		/* allocate space for all disks plus terminator element */
		PPARTARR =
		    realloc(PPARTARR, (NPARTS + 1) * sizeof (struct td_obj));
		if (PPARTARR == NULL)
			return (set_td_errno(TD_E_MEMORY));

		pddm = PDDMPARTS;
		ptdobj = PPARTARR;
		for (iobj = 0; iobj < NPARTS; iobj++, pddm++, ptdobj++) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "partitions %d nfound=%d\n", iobj, NPARTS);

			ptdobj->handle = *pddm;
			ptdobj->attrib = NULL;
			ptdobj->discovery_done = B_FALSE;
		}
		/* mark end of array */
		ptdobj->handle = NULL;
		ptdobj->attrib = NULL;
		CURPART = NULL;
		break;
	case TD_OT_SLICE:
		if (PDDMSLICES == NULL) {
			PDDMSLICES = ddm_get_slices(DDM_DISCOVER_ALL);
			if (PDDMSLICES == NULL)
				return (set_td_errno(TD_E_END));
		}
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO, "got slices\n");

		for (NSLICES = 0, pddm = PDDMSLICES; *pddm != NULL;
		    pddm++, NSLICES++)
			;
		if (number_found != NULL)
			*number_found = NSLICES;
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "got disks nfound=%d\n", NSLICES);

		/* allocate space for all disks plus terminator element */
		PSLICEARR =
		    realloc(PSLICEARR, (NSLICES + 1) * sizeof (struct td_obj));
		if (PSLICEARR == NULL)
			return (set_td_errno(TD_E_MEMORY));

		pddm = PDDMSLICES;
		ptdobj = PSLICEARR;
		for (iobj = 0; iobj < NSLICES; iobj++, pddm++, ptdobj++) {
			ptdobj->handle = *pddm;
			ptdobj->attrib = NULL;
			ptdobj->discovery_done = B_FALSE;
		}
		/* mark end of array */
		ptdobj->handle = NULL;
		ptdobj->attrib = NULL;
		CURSLICE = NULL;
		break;
	case TD_OT_OS: /* get OS instances */
		if (PDDMSLICES == NULL) {
			PDDMSLICES = ddm_get_slices(NULL); /* get all slices */
			if (PDDMSLICES == NULL)
				return (set_td_errno(TD_E_END));
		}
		NSLICES = 0;
		pddm = PDDMSLICES;
		while (*pddm != NULL) { /* count slices */
			pddm++;
			NSLICES++;
		}
		NOS = 0; /* reset master count */
		ret = os_discover();
		if (number_found != NULL)
			*number_found = NOS;
		CUROS = NULL; /* reset current to first */
		break;
	default:
		ret = TD_E_NO_OBJECT;
		break;
	}
	return (set_td_errno(ret));
}

/*
 * enumerate discovered objects of specific type
 * interface to TD user
 * parameters:
 *	otype	indicate object type to enumerate
 * returns TD_ERRNO
 *	TD_E_END indicated the end of the list has been reached
 *
 * After discovery, the user enumerates through the discovered objects,
 * requesting attribute information. This design eliminates the need for
 * the user to have handles or other opaque data to maintain
 *
 * must be called to set the first object
 */
td_errno_t
td_get_next(td_object_type_t otype)
{
	clear_td_errno();

	if (!is_valid_td_object_type(otype))
		return (set_td_errno(TD_E_NO_OBJECT));

	if (objlist[otype].objcur == NULL)
		objlist[otype].objcur = objlist[otype].objarr;
	else
		objlist[otype].objcur++;
	/* expect NULL terminator to object list */
	if (objlist[otype].objcur == NULL ||
	    objlist[otype].objcur->handle == NULL) {
		objlist[otype].objcur = NULL;
		return (set_td_errno(TD_E_END));
	}
	return (TD_E_SUCCESS);
}

/*
 * reset enumeration of objects for specific type
 * interface to TD user
 * parameters:
 *	otype	indicate object type to enumerate
 * returns TD_ERRNO
 *	TD_E_END indicated the end of the list has been reached
 *
 * After discovery, the user enumerates through the discovered objects,
 * requesting attribute information. This routine is used if the user
 * wishes to reset the enumeration and start it again
 *
 * after it is called, there is no current object - td_get_next must be called
 *	to fetch the first object
 */
td_errno_t
td_reset(td_object_type_t otype)
{
	clear_td_errno();

	if (!is_valid_td_object_type(otype))
		return (set_td_errno(TD_E_NO_OBJECT));

	objlist[otype].objcur = NULL;
	return (TD_E_SUCCESS);
}

/*
 * fetch attributes for currently enumerated object of specified type
 * interface to TD user
 * parameters:
 *	otype	indicate object type for which to fetch objects
 * returns an name-value pair list of attributes for the currently enumerated
 *	object.  If there are no attributes, NULL is returned.
 *	TD_ERRNO is also set
 *
 * After discovery, the user enumerates through the discovered objects,
 * requesting attribute information. This interface discovers the attribute
 * information for the currently enumerated object and returns it
 *
 * Attributes are discovered only once during the first call.  Once
 * discovered, they are cached until discovery is repeated or discovered
 * data is released
 */
nvlist_t *
td_attributes_get(td_object_type_t otype)
{
	clear_td_errno();
	switch (otype) {
	case TD_OT_DISK:
		if (CURDISK == NULL || CURDISK->handle == 0) {
			(void) set_td_errno(TD_E_END);
			return (NULL);
		}
		/* if cached, return cached value */
		if (CURDISK->discovery_done)
			return (dup_attr_set_errno(CURDISK));
		/* get disk attributes */
		CURDISK->attrib = ddm_get_disk_attributes(CURDISK->handle);
		CURDISK->discovery_done = B_TRUE;
		if (CURDISK->attrib == NULL) {
			/* no attributes returned from disk module */
			return (NULL);
		}
		return (dup_attr_set_errno(CURDISK));
	case TD_OT_PARTITION:
		if (CURPART == NULL || CURPART->handle == NULL) {
			(void) set_td_errno(TD_E_END);
			return (NULL);
		}
		if (CURPART->discovery_done)
			return (dup_attr_set_errno(CURPART));
		/* discover attributes */
		CURPART->attrib = ddm_get_partition_attributes(CURPART->handle);
		CURPART->discovery_done = B_TRUE;
		if (CURPART->attrib == NULL) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "Partition attribute not found\n");

			return (NULL);
		}
		return (dup_attr_set_errno(CURPART));
	case TD_OT_SLICE:
		if (CURSLICE == NULL || CURSLICE->handle == NULL) {
			(void) set_td_errno(TD_E_END);
			return (NULL);
		}
		if (CURSLICE->discovery_done)
			return (dup_attr_set_errno(CURSLICE));
		/* discover attributes */
		CURSLICE->attrib = ddm_get_slice_attributes(CURSLICE->handle);
		CURSLICE->discovery_done = B_TRUE;
		if (CURSLICE->attrib == NULL) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "slice attribute not found\n");
			return (NULL);
		}
		/* xref slice with disks to discard slices on read-only media */
		if (disk_random_slice(CURSLICE->attrib) == NULL) {
			/* if can't xref, clear attributes */
			ddm_free_attr_list(CURSLICE->attrib);
			CURSLICE->attrib = NULL;
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    ">>>slice discovery>>>"
				    "slice has no disk entry\n");
			return (NULL);
		}
		return (dup_attr_set_errno(CURSLICE));
	case TD_OT_OS:
		/*
		 * Solaris instances are handled differently in that attributes
		 * are set at discovery time
		 */
		if (CUROS == NULL || CUROS->handle == NULL) {
			(void) set_td_errno(TD_E_END);
			return (NULL);
		}
		if (CUROS->attrib == NULL) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "OS attribute not found\n");
			return (NULL);
		}
		return (dup_attr_set_errno(CUROS));
	default:
		break;
	}
	(void) set_td_errno(TD_E_NO_OBJECT);
	return (NULL);
}

/*
 * perform discovery of all objects of the specified type and return all
 *	attributes
 * interface to TD user
 * parameters:
 *	otype	indicate object type for which to fetch objects
 *	pcount	if non-NULL, loaded with number of elements in returned
 *		attribute array.
 *		Necessary for enumerating returned array of attributes
 *	tderr	if non-NULL, loaded with TD_ERRNO
 * returns an array of name-value pair lists of attributes for all objects
 *	of the specified type.  If an error is encountered during enumeration
 *	of the objects, a list of the objects that have been acquired to that
 *	point will be returned, and tderr will reflect an error conditionl
 *
 * This is a convenience routine - it consolidates the process of
 * discovery, enumeration, and fetching of the attribute information into a
 * single interface.
 * Objects with no attribute lists will have NULL attribute list pointers.
 * Use pcount to determine the list length.
 */
nvlist_t **
td_discover_get_attribute_list(const char *attribute_name,
    const char *attribute_value, td_object_type_t otype, int *pcount,
    td_errno_t *tderr)
{
	td_errno_t tderrno = TD_E_SUCCESS;
	int nobjs = 0, i;
	nvlist_t **attr, **attrlist = NULL;
	nvlist_t *attr_tmp;
	int match_attr = 0;
	char *attrval;

	clear_td_errno();
	tderrno = td_discover(otype, &nobjs);
	if (tderrno != TD_E_SUCCESS || nobjs == 0)
		goto discallend;

	attrlist = malloc((nobjs + 1) * sizeof (*attrlist));
	if (attrlist == NULL) {
		(void) set_td_errno(TD_E_MEMORY);
		return (NULL);
	}
	attr = attrlist;
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO, " %d found\n", nobjs);

	if (attribute_name != NULL) {
		assert(attribute_value != NULL);
		match_attr = 1;
	}

	for (i = 0; i < nobjs && tderrno == TD_E_SUCCESS; i++, attr++) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO, "     %d)\n", i);
		tderrno = td_get_next(otype);
		if (tderrno != TD_E_SUCCESS) {
			td_debug_print(LS_DBGLVL_ERR,
			    "td_discover_get_attribute_list receives "
			    "an error while enumerating. "
			    "Object type=%d TD_ERRNO=%d", otype, tderrno);
			break;
		}

		attr_tmp = td_attributes_get(otype);
		if (match_attr == 1) {
			if ((nvlist_lookup_string(attr_tmp, attribute_name,
			    &attrval) == 0) &&
			    (strcmp(attribute_value, attrval) == 0))
				*attr = attr_tmp;
		} else {
			*attr = attr_tmp;
		}

		tderrno = td_get_errno();
	}
	*attr = ATTR_LIST_TERMINATOR;
discallend:
	if (pcount != NULL)
		*pcount = nobjs;
	if (tderr != NULL)
		*tderr = tderrno;
	return (attrlist);
}

nvlist_t **
td_discover_disk_by_vendor(const char *vendor, int *pcount)
{
	return (td_discover_get_attribute_list(TD_DISK_ATTR_VENDOR, vendor,
	    TD_OT_DISK, pcount, NULL));
}

nvlist_t **
td_discover_disk_by_ctype(const char *ctype, int *pcount)
{
	return (td_discover_get_attribute_list(TD_DISK_ATTR_CTYPE, ctype,
	    TD_OT_DISK, pcount, NULL));
}

nvlist_t **
td_discover_disk_by_size(const char *size, int *pcount)
{
	return (td_discover_get_attribute_list(TD_DISK_ATTR_SIZE, size,
	    TD_OT_DISK, pcount, NULL));
}

nvlist_t **
td_discover_disk_by_btype(const char *btype, int *pcount)
{
	return (td_discover_get_attribute_list(TD_DISK_ATTR_BTYPE, btype,
	    TD_OT_DISK, pcount, NULL));
}

/*
 * perform discovery of all partitions on the specified disk and return all`
 * attributes for all partitions on that disk
 * interface to TD user
 * parameters:
 *	disk	name of disk in format cXtXdX or cXdX
 *	pcount	if non-NULL, loaded with number of elements in returned
 *		attribute array.
 *		Necessary for enumerating returned array of attributes
 * returns an array of name-value pair lists of attributes for all objects
 *	of the specified type.
 *
 * Objects with no attribute lists will have NULL attribute list pointers.
 * Use pcount to determine the list length.
 *
 * To search disk list, uses binary search bsearch(3C) with qsort(3C)
 */
nvlist_t **
td_discover_partition_by_disk(const char *disk, int *pcount)
{
	return (td_discover_object_by_disk(TD_OT_PARTITION, disk, pcount));
}

nvlist_t **
td_discover_slice_by_disk(const char *disk, int *pcount)
{
	return (td_discover_object_by_disk(TD_OT_SLICE, disk, pcount));
}

/*
 * return most recent errno for TD
 * interface to TD user
 */
td_errno_t
td_get_errno(void)
{
	return (td_errno);
}

/*
 * release all resources used by Target Discovery Manager
 * interface to TD user
 *   released resources:
 *     - memory allocated for caching of discovery data
 */
td_errno_t
td_discovery_release(void)
{
	clear_td_errno();
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO, "td_discovery_release\n");
	/* free attributes for all object types */
	free_td_obj_list(TD_OT_DISK);
	free_td_obj_list(TD_OT_PARTITION);
	free_td_obj_list(TD_OT_SLICE);
	free_td_obj_list(TD_OT_OS);
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO, "td_discovery_release ends \n");
	return (TD_E_SUCCESS);
}

/*
 * release memory allocated for attributes of a single object
 * interface for TD user
 */
void
td_list_free(nvlist_t *pnv)
{
	if (pnv != NULL)
		nvlist_free(pnv);
}
/*
 * release memory allocated for attributes of a list of objects
 * interface for TD user
 */
void
td_attribute_list_free(nvlist_t **attrlist)
{
	nvlist_t **olist;

	if (attrlist == NULL)
		return;
	for (olist = attrlist; *attrlist != ATTR_LIST_TERMINATOR; attrlist++)
		td_list_free(*attrlist);
	free(olist);
}

/*
 * end of Target Discovery user interfaces
 */

/*
 * global functions used only in TD
 */

/*
 * td_get_rootdir()
 *	Returns the rootdir previously set by a call to td_set_rootdir(). If
 *	td_set_rootdir() hasn't been called this returns a pointer to an empty
 *	string.
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to current rootdir string
 * Status:
 *	public
 */
char *
td_get_rootdir(void)
{
	return (rootdir);
}

/*
 * td_set_rootdir()
 *	Sets the global 'rootdir' variable. Used to install packages
 *	to 'newrootdir'.
 * Parameters:
 *	newrootdir	- non-NULL pathname used to set rootdir
 * Return:
 *	none
 * Status:
 *	public
 */
void
td_set_rootdir(char *newrootdir)
{
	(void) strcpy(rootdir, newrootdir);
	z_canoninplace(rootdir);

	if (streq(rootdir, "/"))
		rootdir[0] = '\0';
}

/*
 * is_new_var_sadm() taken from soft_install.c
 *	this function will return true if the new var/sadm directory
 * 	structure is present or false of it is not present. For simplicity
 * 	and to have a strict rule, the new structure is defined by the
 *	location of the INST_RELEASE file.
 *
 * parameters:
 *	rootdir - This is the root directory passed in by caller.
 * Return:
 *	1	the new structure is present
 *	0	the new structure is not present (old structure assumed)
 *	-1	INST_RELEASE is not present
 * Status:
 *	software library internal
 */
int
td_is_new_var_sadm(const char *rootdir)
{
	char		tmpFile[MAXPATHLEN];	/* A scratch variable */
	FILE		*fp = NULL;
	char		buf[BUFSIZ + 1];
	char		*os = NULL;
	char		*version = NULL;
	char		os_version[MAXPATHLEN];

	/* Now setup a few global variables for some important files. Each */
	/* file name needs to be tested individually for the case of an */
	/* interrupted upgrade or partical upgrade. What is done is the */
	/* file in the new directory tree is checked first, if it is not */
	/* present the old directroy tree is used. */


	(void) snprintf(tmpFile, sizeof (tmpFile),
	    "%s/var/sadm/system/admin/INST_RELEASE", td_get_rootdir());

	if ((fp = fopen(tmpFile, "r")) == NULL) {
		/*
		 * Since the open failed we must now check the old path.
		 */
		(void) snprintf(tmpFile, sizeof (tmpFile),
		    "%s/var/sadm/softinfo/INST_RELEASE",
		    rootdir);
		/*
		 * If open fails and this is a non-global zone, try
		 * opening the file_descriptor for the INST_RELEASE file from
		 * global zone before quitting.
		 */
		if ((fp = fopen(tmpFile, "r")) == NULL) {
			/* The INST_RELEASE file does not appear to exist. */
			return (-1);
		}
	}

	/*
	 * Now that the file is opened we can read out the VERSION and OS
	 * to determin where the the var/sadm information is.
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n')
			continue;
		else if (strncmp(buf, "OS=", 3) == 0)
			os = strdup(td_get_value(buf, '='));
		else if (strncmp(buf, "VERSION=", 8) == 0)
			version = strdup(td_get_value(buf, '='));
	}
	(void) fclose(fp);

	if (os == NULL || version == NULL) {
		(os == NULL) ? free(version) : free(os);
		/*
		 * This is an error.  The INST_RELEASE file seems to be
		 * corrupt.
		 */
		return (-1);
	}

	(void) snprintf(os_version, sizeof (os_version), "%s_%s", os, version);
	free(os);
	free(version);

	/*
	 * We now have a version string to compare with, if the version is
	 * < Solaris_2.5 then this is pre-KBI and pre new var/sadm
	 */
	if (td_prod_vcmp(os_version, "Solaris_2.5") >= 0)
		return (1);	/* A version, 2.5 or higher */
	else
		return (0);	/* Less than 2.5 */
}

/*
 * static functions
 */
td_errno_t
add_td_discovered_obj(td_object_type_t objtype, nvlist_t *onvl)
{
	struct td_obj *pobja = objlist[objtype].objarr;

	pobja =
	    realloc(pobja, sizeof (*pobja) * (objlist[objtype].objcnt + 2));

	if (pobja == NULL) {
		td_debug_print(LS_DBGLVL_ERR,
		    "nvlist td_obj allocation failure\n");
		return (TD_E_MEMORY);
	}
	objlist[objtype].objarr = pobja;
	pobja += objlist[objtype].objcnt;
	pobja->attrib = onvl;
	pobja->handle = (ddm_handle_t)onvl;
	pobja->discovery_done = B_TRUE;
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO, "added to td_obj list!!!\n");
	objlist[objtype].objcnt++;
	pobja++;
	pobja->attrib = NULL;
	pobja->handle = 0L;
	pobja->discovery_done = B_FALSE;
	return (TD_E_SUCCESS);
}

/*
 * usr_packages_exist
 * Check the system to see if critical "/usr" packages have
 *		been installed in the system mounted relative to TD rootdir.
 *		"/usr" files must exist on all systems for upgradeability (i.e.
 *		dataless systems will not have these files). The existence
 *		of "/usr" files is achieved by looking for the existence of the
 *		SUNWcsu package.
 * zonename	zone name to check
 *			If NULL, check against the global zone,
 *			no need to zone exec.
 *			If non-NULL, check against the zone zonename,
 *			use zone exec.
 * Return:	B_TRUE	- /usr packages are present
 *		B_FALSE	- /usr packages do not exist
 */
static boolean_t
usr_packages_exist(char *zonename)
{
	char	path[MAXPATHLEN];

	(void) snprintf(path, sizeof (path), "%s/var/sadm/pkg/SUNWcsu",
	    td_get_rootdir());

	if (zonename == NULL) {
		if (access(path, F_OK) == 0)
			return (B_TRUE);
	} else {
		/* Generate args list for zone exec call. */
		char *arg[] = {"/usr/bin/ls", NULL, NULL};

		arg[1] = path;

		if (z_zone_exec(zonename, arg[0], arg,
		    "/dev/null", "/dev/null", NULL) == 0)
			return (B_TRUE);
	}
	return (B_FALSE);
}

/*
 * non_upgradeable_zone_list
 * Takes a mounted slice which represents a UFS "/" file system,
 * 	check for any viable Solaris zones which are not upgradeable
 *
 * fp	pointer to vfstab for global zone
 * znvl	if non-NULL, set with address of array of char pointers - each element
 *	is string of non-global zone that is not upgradeable
 * returns:	NULL	- any and all non-global zones that should be upgraded
 * 			are upgradeable (or no non-local zones at all)
 *		char ** - at least one zone should be
 *			upgradeable but is not upgradeable
 *			List of zones-if not NULL, should be returned to heap
 *
 * Upgradeability criteria. Candidate zones must be:
 * 	o non-global zones
 * 	o installed
 * Disqualification criteria.
 * 	o SUNWcsu package directory missing
 */
static boolean_t
non_upgradeable_zone_list(FILE *fp, char ***znvl)
{
	zoneList_t	zoneList;
	int		zoneIndex;
	char		*zonename;
	char		*zonepath;
	char		*zname;
	boolean_t	are_bad_zones = B_FALSE;

	if (z_zones_are_implemented() == B_FALSE) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "zones not implemented root=%s\n",
			    td_get_rootdir());
		return (B_FALSE); /* no non-upgradeable zones */
	}
	z_set_zone_root(td_get_rootdir());

	if ((zoneList = z_get_nonglobal_zone_list()) == NULL) {
		td_debug_print(LS_DBGLVL_INFO,
		    MSG0_COULD_NOT_GET_NONGLOBAL_ZONE_LIST);
		return (B_FALSE);	/* no alternate zones */
	}

	/* scan all non-global zones */
	for (zoneIndex = 0;
	    (zonename = z_zlist_get_zonename(zoneList, zoneIndex)) != NULL;
	    zoneIndex++) {

		/* non-global zone - installed? */

		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "zone name = %s\n", zonename);
		if (z_zlist_get_current_state(zoneList, zoneIndex) <
		    ZONE_STATE_INSTALLED) {
			td_debug_print(LS_DBGLVL_INFO,
			    MSG0_ZONE_NOT_INSTALLED, zonename);
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "zone not installed = %s\n", zonename);
			continue;
		}

		/*
		 * zone must be upgradeable - identify anything wrong
		 * that would break an upgrade
		 */

		/*
		 * If root mounted on an alternate root,
		 * get the scratchname.
		 */
		if (!streq(td_get_rootdir(), "/")) {
			zname = z_zlist_get_scratch(zoneList, zoneIndex);
			if (zname == NULL) {
				if (TLI)
					td_debug_print(LS_DBGLVL_INFO,
					    "scratch zone = %s\n", zonename);
				td_debug_print(LS_DBGLVL_INFO,
				    MSG1_COULD_NOT_GET_SCRATCHNAME, zonename);
				continue;
			}
		} else {
			zname = zonename;
		}

		/*
		 * zone cannot be on svm
		 */
		zonepath = z_zlist_get_zonepath(zoneList, zoneIndex);
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "zone path = %s\n", zonepath);
		if (zonepath != NULL && is_path_on_svm(fp, zonepath)) {
			td_debug_print(LS_DBGLVL_ERR,
			    "zone path = %s\n", zonepath);

			if (string_array_add(zname, znvl))
				are_bad_zones = B_TRUE;

			td_debug_print(LS_DBGLVL_INFO,
			    MSG0_MISSING_ZONE_PKG_DIR, zonename);
			continue;
		}

		if (usr_packages_exist(zname)) {
			/* add zonename to list of nonupgradeable zones */
			if (string_array_add(zname, znvl))
				are_bad_zones = B_TRUE;

			td_debug_print(LS_DBGLVL_INFO,
			    MSG0_MISSING_ZONE_PKG_DIR, zonename);
			continue; /* finish zone scan for messages */
		}

		/* non-global zone is upgradeable */

		td_debug_print(LS_DBGLVL_INFO, MSG0_ZONE_UPGRADEABLE, zonename);
	}

	(void) z_free_zone_list(zoneList);

	return (are_bad_zones);
}

/* adds another string to a NULL-terminated array of strings */
static boolean_t
string_array_add(const char *name, char ***stringarray)
{
	char **newstr;
	int curlen;

	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "adding string <%s> to array\n", name);
	if (*stringarray == NULL) {
		newstr = malloc(2 * sizeof (*newstr));
		curlen = 0;
	} else {
		for (curlen = 0; stringarray[curlen] != NULL; curlen++)
			;
		newstr = realloc(*stringarray,
		    (curlen + 2) * sizeof (char *));
	}
	if (newstr == NULL)
		return (B_FALSE);
	newstr[curlen] = strdup(name);
	curlen++;
	newstr[curlen] = NULL;
	*stringarray = newstr;
	return (B_TRUE);
}

/*
 * zones_not_upgradeable_on_slice
 * Mount the given slice and call non_upgradeable_zone_list
 *	to get the list of Solaris zones on that slice
 * 	which are not upgradeable
 *
 * device	- disk slice that contains root file system
 *			For example c0t0d0s0.
 * fp		- pointer to vfstab for global root directory
 * badZoneList	- pointer to pointer to StringList which will
 *			be filled in with list of bad zones if they
 *			exist.
 * Return:	B_TRUE		- Non-global zones exist in this slice.
 *		B_FALSE		- Non-global zones do not exist in this slice.
 */
static boolean_t
zones_not_upgradeable_on_slice(char *device, FILE *fp, char ***znvl)
{
	boolean_t	are_bad_zones = B_FALSE;

	*znvl = NULL;
	if (device == NULL)
		return (B_FALSE);
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "checking zones upg on slice: %s\n", device);
	/* Unmount old disk slices, if any */
	td_umount_and_delete_swap();
	/* Mount the global zone root slice to access non-global zones */
	if (td_mount_and_add_swap(device) == 0 && z_non_global_zones_exist()) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "ng zones exist on slice: device=%s\n", device);
		are_bad_zones = non_upgradeable_zone_list(fp, znvl);
	}
	/* Unmount the disk slices */
	td_umount_and_delete_swap();
	return (are_bad_zones);
}

/*
 * duplicate attribute list
 * set errno on failure
 */
static nvlist_t *
dup_attr_set_errno(struct td_obj *curobj)
{
	nvlist_t *rattrib; /* attribute list for disk */
	int ret;

	if ((ret = nvlist_dup(curobj->attrib, &rattrib, NV_UNIQUE_NAME)) == 0)
		return (rattrib);
	td_debug_print(LS_DBGLVL_ERR, "nvlist_dup failure: errno=%d\n", ret);
	(void) set_td_errno((ret == EINVAL) ? TD_E_INVALID_ARG : TD_E_MEMORY);
	return (NULL);
}

/*
 * set errno for TD
 * NOTE: not thread-safe
 * return value for convenience
 */
static td_errno_t
set_td_errno(int val)
{
	return (td_errno = val);
}

/*
 * clear errno for TD
 * NOTE: not thread-safe
 */
static void
clear_td_errno(void)
{
	td_errno = TD_E_SUCCESS;
}

static boolean_t
is_path_on_svm(FILE *fp, const char *path)
{
	boolean_t is_on_svm = B_FALSE;
	struct vfstab vfstab;
	const char svm_prefix[] = "/dev/md/";

	if (fp == NULL) {
		td_debug_print(LS_DBGLVL_INFO,
		    "vfstab file pointer is null in is_path_on_svm\n");
		return (B_FALSE);
	}
	resetmnttab(fp);
	while (getvfsent(fp, &vfstab) == 0) {
		if (vfstab.vfs_mountp == NULL)
			continue;
		/* find match on mount point */
		if (strncmp(path, vfstab.vfs_mountp,
		    strlen(vfstab.vfs_mountp)) != 0)
			continue;
		/* check for svm type of device name */
		if (strncmp(vfstab.vfs_special,
		    svm_prefix, sizeof (svm_prefix) - 1) == 0) {
			is_on_svm = B_TRUE;
			break;
		}
	}
	resetmnttab(fp);
	return (is_on_svm);
}

/*
 * td_is_fstyp
 * Determines whether a device contains a file
 * system of the requested type
 *
 * Input:
 *	slicenm - disk slice that is to be checked.
 *		  slicenm is in ctds format.
 *
 *	fs      - filesystem type to check
 *
 * Return:	B_TRUE		Device contains requested fs type
 *		B_FALSE		Check for fs type fails
 */

boolean_t
td_is_fstyp(const char *slicenm, char *fs)
{
	int		fd;
	boolean_t	is_fstyp = B_FALSE;
	int		status;
	char		devpath[MAXPATHLEN];
	fstyp_handle_t	fstyp_handle;
	const char	*fstype;

	(void) snprintf(devpath, sizeof (devpath), "/dev/rdsk/%s", slicenm);
	fd = open(devpath, O_RDONLY | O_NDELAY);
	if (fd < 0) {
		td_debug_print(LS_DBGLVL_INFO,
		    "td_is_fstyp():Could not open %s\n", slicenm);
		td_debug_print(LS_DBGLVL_INFO,
		    "td_is_fstyp(): %s\n", strerror(errno));
		return (is_fstyp);
	}

	if ((status = fstyp_init(fd, 0, NULL, &fstyp_handle)) != 0) {
		td_debug_print(LS_DBGLVL_INFO,
		    "td_is_fstyp(): %s\n", fstyp_strerror(fstyp_handle,
		    status));
		(void) close(fd);
		return (is_fstyp);
	}

	if ((status = fstyp_ident(fstyp_handle, fs, &fstype)) == 0) {
		td_debug_print(LS_DBGLVL_INFO,
		    "td_is_fstyp():fstype is %s\n", fstype);
		is_fstyp = B_TRUE;
	} else {
		td_debug_print(LS_DBGLVL_INFO,
		    "td_is_fstyp(): Checking fstype, %s\n",
		    fstyp_strerror(fstyp_handle, status));

	}


	fstyp_fini(fstyp_handle);
	(void) close(fd);
	return (is_fstyp);
}

/*
 * return an nvlist of information interesting to someone wanting Solaris
 * instances
 * - slice name
 */
static td_errno_t
os_discover(void)
{
	ddm_handle_t *cslice;
	FILE *mnttabfp; /* running system mnttab file pointer */
	char *tmprootmntpnt = NULL;
	char tmpvarmntpnt[] = TEMPLATEVAR;
	char templateroot[] = TEMPLATEROOT; /* for mkdtemp() */
	td_errno_t tderr = TD_E_SUCCESS; /* return status */
	char *orootdir = strdup(td_get_rootdir());
	char build_id[80];
	FILE *localvfstabfp;

	/* set current swap file and device as exempt from later removal */
	if ((localvfstabfp = fopen(VFSTAB, "r")) != NULL) {
		struct vfstab localvfstab, localvref;

		/* look for swap in vfstab */
		bzero(&localvref, sizeof (struct vfstab));
		localvref.vfs_fstype = "swap";
		if ((getvfsany(localvfstabfp, &localvfstab, &localvref) == 0) &&
		    localvfstab.vfs_special != NULL &&
		    *localvfstab.vfs_special != '\0' &&
		    *localvfstab.vfs_special != '-') {
			printf("found swap device %s\n",
			    localvfstab.vfs_special);
			td_SetExemptSwapfile(localvfstab.vfs_special);
		}
		(void) fclose(localvfstabfp);
	}

	/* check for Solaris disk */

	/* for each slice, evaluate it for OS instance */
	if (PDDMSLICES == NULL) { /* get all slices */
		PDDMSLICES = ddm_get_slices(DDM_DISCOVER_ALL);
		if (PDDMSLICES == NULL)
			return (TD_E_END);
	}
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO, "Opening /etc/mnttab...\n");
	mnttabfp = fopen(MNTTAB, "r");
	if (mnttabfp == NULL) {
		td_debug_print(LS_DBGLVL_ERR,
		    "could not open mnttab %s fails errno=%d\n",
		    MNTTAB, errno);
		return (TD_E_MNTTAB);
	}
	/* seeking partition tag is root */
	for (cslice = PDDMSLICES; *cslice != NULL; cslice++) {
		struct mnttab mpref, mnttab;
		struct vfstab vref, vfstab;
		uint32_t partition_tag;
		char *slicenm; /* name of slice */
		char slicemp[MAXPATHLEN];
		char *varslice = NULL; /* assume no separate var */
		char vfstabname[MAXPATHLEN];
		boolean_t varmounted = B_FALSE;
		FILE *vfstabfp = NULL;
		boolean_t rootmounted;
		nvlist_t *nvl, *onvl, *svmnvl = NULL;
		char release[32] = "";
		char minor[32] = "";
		char **znvl;
		struct td_upgrade_fail_reasons fr;
		int new_var_sadm;
		int ret;
		char *pclustertoc, *pcluster;

		nvl = ddm_get_slice_attributes(*cslice);
		if (nvl == NULL)
			continue;

		/* check VTOC information: partition tag says root fs */
		if (nvlist_lookup_uint32(nvl, TD_SLICE_ATTR_TAG,
		    &partition_tag) != 0 ||
		    (partition_tag != 0 && partition_tag != V_ROOT))
			continue;

		/* now root slice candidate based on attributes */

		if (nvlist_lookup_string(nvl, TD_SLICE_ATTR_NAME, &slicenm) !=
		    0) {
			td_debug_print(LS_DBGLVL_ERR, "slice name not found\n");
			continue;
		}

		/* xref slice with disks - eliminates RO media slices */
		if (disk_random_slice(nvl) == NULL) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "slice %s has no disk entry\n", slicenm);
			continue;
		}

		bzero(&fr, sizeof (fr)); /* clear upgrade fail reason codes */

		/* is root slice mounted */
		if (tmprootmntpnt == NULL) /* mount point for root */
			tmprootmntpnt = mkdtemp(templateroot);
		bzero(&mpref, sizeof (struct mnttab));
		td_set_rootdir(tmprootmntpnt);
		rootmounted = B_FALSE; /* assume not */

		/* get mount point from mnttab given slice name */
		(void) snprintf(slicemp, sizeof (slicemp),
		    "/dev/dsk/%s", slicenm);
		mpref.mnt_special = slicemp;
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "mounting %s %s \n", slicemp, tmprootmntpnt);
		/* if slice already mounted */
		resetmnttab(mnttabfp);
		if (getmntany(mnttabfp, &mnttab, &mpref) == 0) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "slice %s busy, assumed mounted\n",
				    slicenm);
			rootmounted = B_TRUE;
			/* assume already mounted - find mount point */
			if (strcmp(mnttab.mnt_fstype, MNTTYPE_UFS) != 0) {
				if (TLI)
					td_debug_print(LS_DBGLVL_INFO,
					    "  skipping %s fstype=%s\n",
					    slicemp, mnttab.mnt_fstype);
				continue;
			}
			td_set_rootdir(mnttab.mnt_mountp);
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "getmntany rootdir=%s\n",
				    td_get_rootdir());
			/* look for separate var in mnttab for the slice */
			bzero(&mpref, sizeof (struct mnttab));
			mpref.mnt_mountp = "/var";
			resetmnttab(mnttabfp);
			if (getmntany(mnttabfp, &mnttab, &mpref) == 0) {
				if (TLI)
					td_debug_print(LS_DBGLVL_INFO,
					    "separate var already mounted\n");
				varmounted = B_TRUE;
			} else { /* var not mounted - find mntpnt in vfstab */
				(void) strncpy(tmpvarmntpnt, tmprootmntpnt,
				    sizeof (TEMPLATEVAR));
				(void) strlcat(tmpvarmntpnt, "/var",
				    sizeof (TEMPLATEVAR));
			}
			(void) strcpy(vfstabname, td_get_rootdir());
			(void) strcat(vfstabname, VFSTAB);
		} else {
			/*
			 * Check to see what type of filesystem the
			 * device contains. The fsck and mount code only
			 * applies to ufs filesystems
			 */

			if (!td_is_fstyp(slicenm, "ufs"))
				continue;

			/* perform fsck and mount */
			ret = td_fsck_mount(tmprootmntpnt, slicenm, B_TRUE,
			    NULL, "-r", "ufs", &svmnvl);
			if (ret != MNTRC_MOUNT_SUCCEEDS) {
				continue;
			}

			/* read vfstab from mounted slice */
			(void) strncpy(tmpvarmntpnt, tmprootmntpnt,
			    sizeof (TEMPLATEVAR));
			(void) strlcat(tmpvarmntpnt, "/var",
			    sizeof (TEMPLATEVAR));
			/* use vfstab from mounted root slice */
			(void) snprintf(vfstabname, sizeof (vfstabname),
			    "%s%s", tmprootmntpnt, VFSTAB);
		}
		if (TLI)
			td_debug_cat_file(LS_DBGLVL_INFO, vfstabname);

		/* open vfstab on root */
		vfstabfp = fopen(vfstabname, "r");
		if (vfstabfp == NULL) {
			int ret = errno;

			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "fopen of vfstab %s fails:<%s> - "
				    "slice skipped\n",
				    vfstabname, strerror(ret));
			if (partition_tag != V_ROOT)
				goto umount;
		}
		if (!varmounted && vfstabfp != NULL) {
			char *varfsck = NULL;

			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "analyzing vfstab %s...\n", vfstabname);
			/* look for var in vfstab */
			bzero(&vref, sizeof (struct vfstab));
			vref.vfs_mountp = "/var";
			if ((ret = getvfsany(vfstabfp, &vfstab, &vref)) == 0) {
				varslice = vfstab.vfs_special;
				varfsck = vfstab.vfs_fsckdev;
			}
			/* if var on separate volume, attempt to mnt, dismnt */
			if (varslice != NULL) {
				/* cNtNdN version of slice name */
				char *varctd = NULL;
				char *varfsckctd = NULL;
				char emnt[MAXPATHLEN] = "";
				char efsckd[MAXPATHLEN] = "";

				if (TLI)
					td_debug_print(LS_DBGLVL_INFO,
					    "mounting %s on %s...\n",
					    varslice, tmpvarmntpnt);
				if (vfstab.vfs_fsckdev == NULL ||
				    vfstab.vfs_fsckpass == NULL ||
				    *vfstab.vfs_fsckpass == '-') {
					varfsck = NULL;
				} else {
					if (td_map_to_effective_dev(
					    varfsck, efsckd, sizeof (efsckd))
					    != 0) {
						td_debug_print(LS_DBGLVL_WARN,
						    "Can't access device %s\n",
						    varslice);
						varfsck = NULL;
						fr.var_not_mountable = 1;
					} else {
						if (strncmp(varfsck, efsckd,
						    sizeof (efsckd)) != 0)
							td_debug_print(
							    LS_DBGLVL_INFO,
							    "%s mapped to %s\n",
							    varfsck, efsckd);
						else
							td_debug_print(
							    LS_DBGLVL_INFO,
							    "not re-mapped\n");
						varfsckctd = jump_dev_prefix(
						    efsckd);
					}
				}
				if (td_map_to_effective_dev(
				    varslice, emnt, sizeof (emnt))
				    != 0) {
					td_debug_print(LS_DBGLVL_WARN,
					    "Can't access device %s\n",
					    varslice);
					varslice = NULL;
					if (partition_tag != V_ROOT)
						goto umount;
					fr.var_not_mountable = 1;
				} else {
					varctd = jump_dev_prefix(emnt);
				}
				if (varslice != NULL) {
					int mr;

					td_debug_print(LS_DBGLVL_INFO,
					    "doing var mount slice=%s\n",
					    varslice);
					mr = td_fsck_mount(tmpvarmntpnt,
					    varctd, varfsckctd != NULL,
					    varfsckctd, "-r", "ufs", NULL);
					if (mr != MNTRC_MOUNT_SUCCEEDS) {
						ret = errno;
						td_debug_print(
						    LS_DBGLVL_ERR,
						    "var mount failed "
						    "<%s> errno=%d\n",
						    mntrc_strerror(mr),
						    ret);
						td_debug_print(
						    LS_DBGLVL_ERR,
						    "varctd=%s\n",
						    varctd);
						td_debug_print(
						    LS_DBGLVL_ERR,
						    "tmpvarmntpnt=%s\n",
						    tmpvarmntpnt);
						varslice = NULL;
						if (partition_tag !=
						    V_ROOT)
							goto umount;
						fr.var_not_mountable = 1;
					}
				}
			}
		}
		/* is INST_RELEASE present? Old or new location? */
		new_var_sadm = td_is_new_var_sadm(td_get_rootdir());
		if (new_var_sadm == -1) {
			if (partition_tag != V_ROOT) /* not explicitly root */
				goto umount; /* do not count as Solaris BE */
			fr.no_inst_release	= 1;
		}
		/* get release information */
		if (!td_get_release(td_get_rootdir(), release,
		    sizeof (release), minor, sizeof (minor))) {
			if (partition_tag != V_ROOT) /* not explicitly root */
				goto umount; /* do not count as Solaris BE */
			fr.no_inst_release	= 1;
		}
		/* Does it have .clustertoc and CLUSTER files? */
		pclustertoc = clustertoc_read_path(new_var_sadm,
		    td_get_rootdir());
		if (pclustertoc == NULL || access(pclustertoc, F_OK) != 0) {
			if (partition_tag != V_ROOT) /* not explicitly root */
				goto umount; /* do not count as Solaris BE */
			fr.no_clustertoc = 1;
		}
		pcluster = CLUSTER_read_path(new_var_sadm, td_get_rootdir());
		if (pcluster == NULL || *pcluster == '\0' ||
		    access(pcluster, F_OK) != 0) {
			if (partition_tag != V_ROOT) /* not explicitly root */
				goto umount; /* do not count as Solaris BE */
			fr.no_cluster = 1;
		} else if (is_wrong_metacluster(pcluster)) {
			/* is installed metacluster upgradeable? */
			fr.wrong_metacluster = 1;
		}
		/*
		 * Check for /boot/solaris/bootenv.rc if warranted (Intel >=2.7)
		 */
		if (td_is_isa("i386") && release[0] != '\0') {
			int cmp;

			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    " -checking for x86 boot env\n");
			cmp = td_prod_vcmp(release, "Solaris_2.7");
			if (cmp == V_GREATER_THAN || cmp == V_EQUAL_TO)
				if (!bootenv_exists(td_get_rootdir())) {
					if (TLI)
						td_debug_print(LS_DBGLVL_INFO,
						    " no boot env\n");
					if (partition_tag != V_ROOT)
						goto umount;
					fr.no_bootenvrc = 1;
				}
		}
		/* check for DEVX-only upgrade */
		if (release[0] != '\0' &&
		    td_prod_vcmp(release, "Solaris_11") == V_LESS_THAN) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    " -OS version (%s)< 11\n", release);
			if (partition_tag != V_ROOT)
				goto umount;
			fr.os_version_too_old = 1;
		}
		/* check for usr packages on global zone */
		if (!usr_packages_exist(NULL)) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "no usr packages found\n");
			if (partition_tag != V_ROOT)
				goto umount;
			fr.no_usr_packages = 1;
		}
add_instance:
		/* ***** instance found-add to array of nvlists ***** */
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "Solaris instance found!!!\n");
		if (nvlist_alloc(&onvl, NV_UNIQUE_NAME, 0) != 0) {
			td_debug_print(LS_DBGLVL_ERR,
			    "nvlist allocation failure\n");
			tderr = TD_E_MEMORY;
			goto umount;
		}	/* allocate list */
		/* factor in any svm information */
		if (svmnvl != NULL) {
			if (nvlist_merge(onvl, svmnvl, NV_UNIQUE_NAME) != 0)
				td_debug_print(LS_DBGLVL_ERR,
				    "nvlist merge failure\n");
			fr.svm_root_mirror = 1;
		}
		if (zones_not_upgradeable_on_slice(slicenm, vfstabfp, &znvl)) {

			int nelem = 0;
			char **p;

			for (p = znvl; *p != NULL; p++)
				nelem++;
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    " %d non-upgradeable zones found\n", nelem);
			if (nelem > 0) {
				if (nvlist_add_string_array(onvl,
				    TD_OS_ATTR_ZONES_NOT_UPGRADEABLE,
				    znvl, nelem) != 0)
					td_debug_print(LS_DBGLVL_ERR,
					    "add string array failed\n");
				fr.zones_not_upgradeable = 1;
			}
		}
		/* add Solaris version string to attribute list */
		if (release[0] == '\0') {
			fr.no_version = 1;
		} else {
			if (nvlist_add_string(onvl, TD_OS_ATTR_VERSION, release)
			    != 0) {
				td_debug_print(LS_DBGLVL_ERR,
				    "nvlist add_string failure\n");
				nvlist_free(nvl);
				tderr = TD_E_MEMORY;
				goto umount;
			}
			if (minor[0] != '\0' && nvlist_add_string(onvl,
			    TD_OS_ATTR_VERSION_MINOR, minor) != 0) {
				td_debug_print(LS_DBGLVL_ERR,
				    "nvlist add_string failure\n");
				nvlist_free(nvl);
				tderr = TD_E_MEMORY;
				goto umount;
			}
		}
		/* add slice name to attribute list */
		if (nvlist_add_string(onvl, TD_OS_ATTR_SLICE_NAME, slicenm)
		    != 0) {
			td_debug_print(LS_DBGLVL_ERR,
			    "nvlist add_string failure\n");
			nvlist_free(nvl);
			tderr = TD_E_MEMORY;
			goto umount;
		}
		/* fetch build id */
		if (td_get_build_id(td_get_rootdir(), build_id,
		    sizeof (build_id)) != NULL) {
			if (nvlist_add_string(onvl, TD_OS_ATTR_BUILD_ID,
			    build_id) != 0) {
				td_debug_print(LS_DBGLVL_ERR,
				    "nvlist add_string failure\n");
				nvlist_free(nvl);
				tderr = TD_E_MEMORY;
				goto umount;
			}
		}
		/* if upgrade will fail, give reasons */
		if (TD_UPGRADE_FAIL(fr) &&
		    nvlist_add_uint32(onvl, TD_OS_ATTR_NOT_UPGRADEABLE,
		    *(uint32_t *)&fr) != 0) {
			nvlist_free(nvl);
			tderr = TD_E_MEMORY;
			goto umount;
		}
		/* allocate or extend list */
		tderr = add_td_discovered_obj(TD_OT_OS, onvl);
		if (tderr != TD_E_SUCCESS) {
			nvlist_free(nvl);
			goto umount;
		}
umount:		/* if we goto to this label, no Solaris instance */

		/* release temp resources for slice */
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "release temp resources for slice\n");
		if (vfstabfp != NULL) /* alternate slice mnttab */
			(void) fclose(vfstabfp);
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "umount current root %s\n", rootmounted ?
			    "YES": "NO");
		/* unmount var if on separate slice */
		if (varslice != NULL)
			(void) umount2(tmpvarmntpnt, 0);
		/* unmount current root, var at temporary mount points */
		if (!rootmounted && umount2(tmprootmntpnt, 0) != 0) {
			/* unmount failed - use new temp mount point */
			(void) strncpy(templateroot, TEMPLATEROOT,
			    sizeof (templateroot));
			tmprootmntpnt = NULL;
		}
		if (tderr != TD_E_SUCCESS)
			break;
	} /* next slice */
	td_be_list(); /* discover all Snap Boot Environments */
	if (tderr == TD_E_SUCCESS)
		sort_objs(TD_OT_OS);
	if (tmprootmntpnt != NULL)
		(void) rmdir(tmprootmntpnt);
	(void) fclose(mnttabfp);
	td_set_rootdir(orootdir);
	free(orootdir);
	return (tderr); /* return error/success code */
}

/*
 * fsck -m checks to see if file system
 * needs checking.
 *
 * if return code = 0, disk is OK, can be mounted.
 * if return code = 32, disk is dirty, must be fsck'd
 * if return code = 33, disk is already mounted
 *
 * If the file system to be mounted is the true root,
 * don't bother to do the fsck -m (since the results are
 * unpredictable).  We know it must be mounted, so set
 * the cmdstatus to 33.  This will drop us into the code
 * that verifies that the EXPECTED file system is mounted
 * as root.
 *
 * If no fsckdev was specified, assume that fscking doesn't
 * need to be done for this filesystem.
 */
static int
td_fsck_mount(char *basemount, char *slicenm, boolean_t dofsck, char *fsckdev,
    char *mntopts, char *fstype, nvlist_t **attr)
{
	char			options[MAXPATHLEN];
	char			cmd[MAXPATHLEN];
	char			localmntdev[MAXPATHLEN];
	char			*mntdev;
	char			locfsckdev[MAXPATHLEN];
	int			status;
	int			cmdstatus;

	(void) snprintf(localmntdev, sizeof (localmntdev),
	    "/dev/dsk/%s", slicenm);
	if (fsckdev == NULL) {
		(void) snprintf(locfsckdev, sizeof (locfsckdev),
		    "/dev/rdsk/%s", slicenm);
		fsckdev = locfsckdev;
	} else {
		(void) snprintf(locfsckdev, sizeof (locfsckdev),
		    "/dev/rdsk/%s", fsckdev);
		fsckdev = locfsckdev;
	}

	if (strcmp(mntopts, "-") == 0)
		options[0] = '\0';
	else {
		(void) strcpy(options, "-o ");
		(void) strcat(options, mntopts);
	}

	mntdev = strdup(localmntdev);

	/*
	 * fsck -m checks to see if file system
	 * needs checking.
	 *
	 * if return code = 0, disk is OK, can be mounted.
	 * if return code = 32, disk is dirty, must be fsck'd
	 * if return code = 33, disk is already mounted
	 *
	 * If the file system to be mounted is the true root,
	 * don't bother to do the fsck -m (since the results are
	 * unpredictable).  We know it must be mounted, so set
	 * the cmdstatus to 33.  This will drop us into the code
	 * that verifies that the EXPECTED file system is mounted
	 * as root.
	 *
	 * do fsck according to boolean
	 */
	if (strcmp(basemount, "/") == 0) {
		cmdstatus = 33;
	} else if (!dofsck) {
		cmdstatus = 0;
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/fsck -m -F %s %s",
		    fstype, fsckdev);
		td_debug_print(LS_DBGLVL_INFO, "fsck cmd <%s>\n", cmd);
		status = td_safe_system(cmd, B_TRUE);
		cmdstatus = WEXITSTATUS(status);
	}
	if (cmdstatus == 0) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/sbin/mount -F %s %s %s %s",
		    fstype, mntopts, mntdev, basemount);
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO, "mount cmd=%s\n", cmd);
		if ((status = td_safe_system(cmd, B_TRUE)) != 0) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Failure mounting %s, error = %d <%s>\n",
				    basemount, WEXITSTATUS(status), cmd);
			return (MNTRC_MOUNT_FAIL);
		}
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "fsck on %s %s succeeds\n", mntdev, basemount);
		/* set the mntdev to the mirror if there is one */
		if (td_set_mntdev_if_svm(basemount, mntopts, NULL, NULL, attr)
		    != SUCCESS)
			return (MNTRC_MOUNT_FAIL);
	} else {
		if (TLW)
			td_debug_print(LS_DBGLVL_WARN,
			    "Unrecognized failure %d from 'fsck -m -F %s %s'\n",
			    cmdstatus, fstype, fsckdev);

		return (MNTRC_FSCK_FAILURE);
	}
	return (MNTRC_MOUNT_SUCCEEDS);
}

/*
 * clustertoc_read_path()
 *	this function will return the correct path for the .clustertoc
 *	file.
 *
 * Called By: load_installed_product
 *
 * parameters:
 *	new_var_sadm
 *		1 - new var/sadm
 *		0 - old var/sadm
 *		-1 - unknown since INST_RELEASE was not found
 *	rootdir - This is the root directory passed in by caller.
 * Return:
 *	the path to the file or NULL if not found.
 * Status:
 *	software library internal
 */
static char *
clustertoc_read_path(int new_var_sadm, const char *rootdir)
{
	/*
	 * Check to see if the temp variable used to hold the path is
	 * free. If not free it, then allocate a new one.
	 */
	if (new_var_sadm != 0) /* if new var/sadm or INST_RELEASE not found */
		(void) snprintf(clustertoc_tmp_path, MAXPATHLEN,
		    "%s/var/sadm/system/admin/.clustertoc",
		    rootdir);
	else
		(void) snprintf(clustertoc_tmp_path, MAXPATHLEN,
		    "%s/var/sadm/install_data/.clustertoc",
		    rootdir);

	return (clustertoc_tmp_path);
}

/*
 * CLUSTER_read_path()
 *	this function will return the correct path for the CLUSTER
 *	file.
 *
 * parameters:
 *	new_var_sadm
 *		1 - new var/sadm
 *		0 - old var/sadm
 *		-1 - unknown since INST_RELEASE was not found
 *	rootdir - This is the root directory passed in by caller.
 * Return:
 *	the path to the file or NULL if not found.
 * Status:
 *	software library internal
 */
static char *
CLUSTER_read_path(int new_var_sadm, const char *rootdir)
{
	/*
	 * Check to see if the temp variable used to hold the path is
	 * free. If no free it, then allocate a new one.
	 */
	if (new_var_sadm != 0) /* if new var/sadm or INST_RELEASE not found */
		(void) snprintf(CLUSTER_tmp_path, MAXPATHLEN,
		    "%s/var/sadm/system/admin/CLUSTER",
		    rootdir);
	else
		(void) snprintf(CLUSTER_tmp_path, MAXPATHLEN,
		    "%s/var/sadm/install_data/CLUSTER",
		    rootdir);

	return (CLUSTER_tmp_path);
}

/*
 * is_wrong_metacluster()
 *	this function checks for a metacluster that is deemed upgradeable
 *
 * parameters:
 *	pcluster - current name of cluster file determined previously
 * Return:
 *	true if metacluster not upgradeable
 * Status:
 *	software library internal
 */
static boolean_t
is_wrong_metacluster(char *pcluster)
{
	FILE	*fp;
	char	line[BUFSIZ];

	/* if no cluster file, don't report wrong cluster */
	if (pcluster == NULL || *pcluster == '\0' ||
	    (fp = fopen(pcluster, "r")) == NULL)
		return (B_FALSE);

	/* First line must be CLUSTER=SUNWCXall */
	if (fgets(line, sizeof (line), fp) == NULL) {
		(void) fclose(fp);
		return (B_TRUE); /* not desired metacluster */
	}
	(void) fclose(fp);

	return (strncmp(line, "CLUSTER=SUNWCXall", 17) != 0);
}

/*
 * td_get_value()
 *	Parse out value from string passed in. str should be of the form:
 *	"TOKENxVALUE\n" where x=delim.  The trailing \n is optional, and
 *	will be removed.
 *	Also, leading and trailing white space will be removed from VALUE.
 * parameters:
 *	str	- string pointer to text line to be parsed
 *	delim	- a character delimeter
 * Return:
 * Status:
 *	private
 */
static char *
td_get_value(const char *str, char delim)
{
	char	   *cp, *cp1;

	if ((cp = strchr(str, delim)) == NULL)
		return (NULL);

	cp += 1;		/* value\n	*/
	cp1 = strchr(cp, '\n');
	if (cp1 && *cp1)
		*cp1 = '\0';	/* value	*/

	/* chop leading white space */
	for (; cp && *cp && ((*cp == ' ') || (*cp == '\t')); ++cp)
		;

	if (*cp == '\0')
		return ("");

	/* chop trailing white space */
	for (cp1 = cp + strlen(cp) - 1;
	    cp1 >= cp && ((*cp1 == ' ') || (*cp1 == '\t')); --cp1)
		*cp1 = '\0';

	if (cp && *cp)
		return (cp);

	return ("");
}

/*
 * td_get_default_inst()
 *	Returns the default instruction set architecture of the
 *	machine it is executed on. (eg. sparc, i386, ...)
 *	NOTE:	SYS_INST environment variable may override default
 *		return value
 * parameters:
 *	none
 * Return:
 *	NULL	- the architecture returned by sysinfo() was too long for
 *		  local variables
 *	char *	- pointer to a string containing the default implementation
 * Status:
 *	public
 */
static char *
td_get_default_inst(void)
{
	int	i;
	char	*envp;
#define	ARCH_LENGTH MAXNAMELEN
	static char	default_inst[ARCH_LENGTH] = "";

	if (default_inst[0] == '\0') {
		if ((envp = getenv("SYS_INST")) != NULL) {
			if ((int)strlen(envp) >= ARCH_LENGTH)
				return (NULL);
			else
				(void) strcpy(default_inst, envp);
		} else  {
			i = sysinfo(SI_ARCHITECTURE, default_inst, ARCH_LENGTH);
			if (i < 0 || i > ARCH_LENGTH)
				return (NULL);
		}
	}
	return (default_inst);
}

/*
 * Function:	td_is_isa
 * Description:	Boolean function indicating whether the instruction set
 *		architecture of the executing system matches the name provided.
 *		The string must match a system defined architecture (e.g.
 *		"i386", "ppc, "sparc") and is case sensitive.
 * Scope:	public
 * Parameters:	name	- [RO, *RO]
 *		string representing the name of instruction set architecture
 *		being tested
 * Return:	0 - the system instruction set architecture is different from
 *			the one specified
 * 		1 - the system instruction set architecture is the same as the
 *			one specified
 */
static int
td_is_isa(char *name)
{
	return (streq(td_get_default_inst(), name) ? 1 : 0);
}

/*
 * Function:	bootenv_exists
 * Description:	Determine whether or not /boot/solaris/bootenv.rc exists.  This
 *		check is performed on Intel images installed with Solaris 7 or
 *		later.
 * Scope:	private
 * Parameters:	release	- [RO, *RO] (char *)
 *			  the release on the installed image
 * Return:	1	- check successful or not necessary
 *		0	- check failed
 */
static boolean_t
bootenv_exists(const char *rootdir)
{
	char path[MAXPATHLEN];

	(void) snprintf(path, sizeof (path), "%s/boot/solaris/bootenv.rc",
	    rootdir);
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "looking for bootenv in %s access returns %d\n",
		    path, access(path, F_OK));
	return (access(path, F_OK) == 0);
}

/*
 * free all resources for a td object
 */
static void
free_td_obj_list(td_object_type_t ot)
{
	struct td_class *pobl = &objlist[ot];
	struct td_obj *pobj;

	if (pobl->objarr != NULL) {
		/* release attribute data */
		for (pobj = pobl->objarr; pobj->handle != 0; pobj++)
			if (pobj->attrib != NULL)
				nvlist_free(pobj->attrib);
		/* release object instance list */
		free(pobl->objarr);
		pobl->objarr = NULL;
	}
	/* unset static information for object */
	pobl->objcur = NULL;
	pobl->objcnt = 0;
	pobl->issorted = B_FALSE;
	/* free handle lists from lower-level modules */
	if (pobl->pddm != NULL) {
		(void) ddm_free_handle_list(pobl->pddm);
		pobl->pddm = NULL;
	}
}

static nvlist_t **
td_discover_object_by_disk(td_object_type_t ot, const char *disk, int *pcount)
{
	struct td_obj *pobj, *pdisk;
	nvlist_t **ppd = NULL; /* partition list to return */
	char *pobjname;
	int i, nmatch = 0;
	char	device_match[MAXPATHLEN];

	clear_td_errno();
	if (pcount != NULL)
		*pcount = 0;

	/* supported only for partitions and slices */
	if (ot != TD_OT_PARTITION && ot != TD_OT_SLICE) {
		(void) set_td_errno(TD_E_NO_OBJECT);
		return (NULL);
	}
	/* discover disks if not done */
	if (objlist[TD_OT_DISK].objarr == NULL) {
		(void) td_discover(TD_OT_DISK, NULL);
		if (TD_ERRNO != TD_E_SUCCESS)
			return (NULL);
	}
	pdisk = search_disks(disk);
	if (pdisk == NULL) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "search_disks found no matching disk\n");
		(void) set_td_errno(TD_E_NO_DEVICE);
		return (NULL);
	}
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    ">>>  discover partition by diskname=%s\n", disk);
	/* discover object type if not done */
	if (objlist[ot].objarr == NULL) {
		(void) td_discover(ot, NULL);
		if (TD_ERRNO != TD_E_SUCCESS)
			return (NULL);
	}
	pobj = objlist[ot].objarr;
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    ">>>   object count=%d\n", objlist[ot].objcnt);

	(void) snprintf(device_match, sizeof (device_match), "%s%s",
	    disk, ot == TD_OT_PARTITION ? "p" : "s");

	for (i = 0; i < objlist[ot].objcnt; i++, pobj++) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    ">>>   obj %d handle=0x%llx\n", i, pobj->handle);
		if (!pobj->discovery_done) {
			pobj->attrib = (ot == TD_OT_PARTITION ?
			    ddm_get_partition_attributes(pobj->handle):
			    ddm_get_slice_attributes(pobj->handle));
			pobj->discovery_done = B_TRUE;
		}
		/*
		 * if no attributes, we cannot match on name
		 * this may pose a problem, since there could be a partition
		 * without attributes that is on the disk
		 */
		if (pobj->attrib == NULL)
			continue;
		/* match on partition/slice name? */
		if (nvlist_lookup_string(pobj->attrib,
		    (ot == TD_OT_PARTITION ?
		    TD_PART_ATTR_NAME : TD_SLICE_ATTR_NAME),
		    &pobjname) != 0)
			continue;
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    " obj=%s search disk=%s\n", pobjname, disk);
		/*
		 * Look for an exact match between the slice/partition
		 * (pobjname) we're processing and the passed in disk
		 * name + disk part (eg: c0t0d0s or c0d0p)
		 */
		if (strstr(pobjname, device_match) == NULL)
			continue;
		/* match on disk name */
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    ">>>   partition/slice %d %s NDISKS=%d\n",
			    i, pobjname, NDISKS);
		/* allocate or extend list of pointers */
		ppd = ((ppd == NULL) ?
		    malloc(2 * sizeof (*ppd)) :
		    realloc(ppd, (nmatch + 2) * sizeof (*ppd)));
		if (ppd == NULL) {
			(void) set_td_errno(TD_E_MEMORY);
			return (NULL);
		}
		/* copy partition attributes */
		if (nvlist_dup(pobj->attrib, &ppd[nmatch], NV_UNIQUE_NAME)
		    != 0) {
			(void) set_td_errno(TD_E_MEMORY);
			return (NULL);
		}
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    ">>>   partition/slice match %d %s %s \n",
			    nmatch, disk, pobjname);
		nmatch++;
		ppd[nmatch] = ATTR_LIST_TERMINATOR;
	}
	if (pcount != NULL)
		*pcount = nmatch;
	return (ppd);
}

/* insure all disk discovery complete */
static void
disks_discover_all_attrs(void)
{
	int j;

	/* discover disks if not done */
	if (PDISKARR == NULL) {
		(void) td_discover(TD_OT_DISK, NULL);
		if (TD_ERRNO != TD_E_SUCCESS)
			return;
	}
	for (j = 0; j < NDISKS; j++)
		/* discover disk attributes if not done */
		if (!PDISKARR[j].discovery_done) {
			PDISKARR[j].attrib =
			    ddm_get_disk_attributes(PDISKARR[j].handle);
			PDISKARR[j].discovery_done = B_TRUE;
		}
}

static struct td_obj *
disk_random_slice(nvlist_t *pattrib)
{
	char *pslicepar;

	/* match on slice name? */
	if (nvlist_lookup_string(pattrib,
	    TD_SLICE_ATTR_NAME, &pslicepar) != 0)
		return (NULL);
	disks_discover_all_attrs(); /* insure all disk discovery complete */
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    ">>>   slice/part %s NDISKS=%d\n", pslicepar, NDISKS);
	return (search_disks_for_slices(pslicepar));
}

static int
compare_os_objs(const void *p1, const void *p2)
{

	struct td_obj *o1 = (struct td_obj *)p1;
	struct td_obj *o2 = (struct td_obj *)p2;
	char *pd1 = NULL, *pd2 = NULL;

	if (o1->attrib != NULL)
		nvlist_lookup_string(o1->attrib, TD_OS_ATTR_SLICE_NAME, &pd1);
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_OS_ATTR_SLICE_NAME, &pd2);
	if (pd1 == NULL && pd2 == NULL)
		return (0);
	if (pd1 == NULL)
		return (-1);
	if (pd2 == NULL)
		return (1);
	return (strcmp(pd1, pd2));
}

static int
compare_disk_objs(const void *p1, const void *p2)
{

	struct td_obj *o1 = (struct td_obj *)p1;
	struct td_obj *o2 = (struct td_obj *)p2;
	char *pd1 = NULL, *pd2 = NULL;

	if (o1->attrib != NULL)
		nvlist_lookup_string(o1->attrib, TD_DISK_ATTR_NAME, &pd1);
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_DISK_ATTR_NAME, &pd2);
	if (pd1 == NULL && pd2 == NULL)
		return (0);
	if (pd1 == NULL)
		return (-1);
	if (pd2 == NULL)
		return (1);
	return (strcmp(pd1, pd2));
}

static int
compare_slice_objs(const void *p1, const void *p2)
{

	struct td_obj *o1 = (struct td_obj *)p1;
	struct td_obj *o2 = (struct td_obj *)p2;
	char *pd1 = NULL, *pd2 = NULL;

	if (o1->attrib != NULL)
		nvlist_lookup_string(o1->attrib, TD_SLICE_ATTR_NAME, &pd1);
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_SLICE_ATTR_NAME, &pd2);
	if (pd1 == NULL && pd2 == NULL)
		return (0);
	if (pd1 == NULL)
		return (-1);
	if (pd2 == NULL)
		return (1);
	return (strcmp(pd1, pd2));
}

static int
compare_partition_objs(const void *p1, const void *p2)
{

	struct td_obj *o1 = (struct td_obj *)p1;
	struct td_obj *o2 = (struct td_obj *)p2;
	char *pd1 = NULL, *pd2 = NULL;

	if (o1->attrib != NULL)
		nvlist_lookup_string(o1->attrib, TD_PART_ATTR_NAME, &pd1);
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_PART_ATTR_NAME, &pd2);
	if (pd1 == NULL && pd2 == NULL)
		return (0);
	if (pd1 == NULL)
		return (-1);
	if (pd2 == NULL)
		return (1);
	return (strcmp(pd1, pd2));
}

static int
compare_disk_objs_search(const void *p1, const void *p2)
{

	char *searchdisk = (char *)p1, *pdisk = NULL;
	struct td_obj *o2 = (struct td_obj *)p2;

	/* discover disk attributes if not done */
	if (!o2->discovery_done) {
		o2->attrib = ddm_get_disk_attributes(o2->handle);
		o2->discovery_done = B_TRUE;
	}
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_DISK_ATTR_NAME, &pdisk);
	if (pdisk == NULL)
		return (1);
	if (searchdisk == NULL)
		return (-1);
	return (strcmp(searchdisk, pdisk));
}

static int
compare_disk_slice_search(const void *p1, const void *p2)
{
	char *pslice = (char *)p1, *pdisk = NULL;
	struct td_obj *o2 = (struct td_obj *)p2;

	/* discover disk attributes if not done */
	if (!o2->discovery_done) {
		o2->attrib = ddm_get_disk_attributes(o2->handle);
		o2->discovery_done = B_TRUE;
	}
	if (o2->attrib != NULL)
		nvlist_lookup_string(o2->attrib, TD_DISK_ATTR_NAME, &pdisk);
	if (pdisk == NULL)
		return (1);
	if (strstr(pslice, pdisk) != NULL)
		return (0);
	return (strcmp(pslice, pdisk));
}

struct td_obj *
search_disks(const char *searchstr)
{
	struct td_class *pobjlist = &objlist[TD_OT_DISK];

	disks_discover_all_attrs(); /* insure all disk discovery complete */
	if (!pobjlist->issorted)
		sort_objs(TD_OT_DISK);
	return (bsearch(searchstr, pobjlist->objarr, pobjlist->objcnt,
	    sizeof (struct td_obj), compare_disk_objs_search));
}

static struct td_obj *
search_disks_for_slices(char *pslice)
{
	struct td_class *pobjlist = &objlist[TD_OT_DISK];

	disks_discover_all_attrs(); /* insure all disk discovery complete */
	if (!pobjlist->issorted)
		sort_objs(TD_OT_DISK);
	return (bsearch(pslice, pobjlist->objarr, pobjlist->objcnt,
	    sizeof (struct td_obj), compare_disk_slice_search));
}

boolean_t
td_is_slice(const char *name)
{
	return (search_disks_for_slices((char *)name) != NULL);
}

static void
sort_objs(td_object_type_t ot)
{
	struct td_class *pobjlist = &objlist[ot];

	if (pobjlist->issorted)
		return;
	qsort(pobjlist->objarr, pobjlist->objcnt,
	    sizeof (struct td_obj), pobjlist->compare_routine);
	pobjlist->issorted = B_TRUE;
}

static void
td_debug_cat_file(ls_dbglvl_t dbg_lvl, char *filename)
{
	char	buf[256]; /* contains 1 line of text */
	FILE	*f;

	assert(filename != NULL);

	if ((f = fopen(filename, "r")) == NULL) {
		td_debug_print(LS_DBGLVL_WARN,
		    "Couldn't open file %s for dump\n", filename);
		return;
	}
	td_debug_print(dbg_lvl, " listing %s:\n", filename);
	while (fgets(buf, sizeof (buf), f) != NULL)
		td_debug_print(dbg_lvl, "%s", buf);
	(void) fclose(f);
}

/* text for td_fsck_mount return codes */
static char *
mntrc_strerror(int ret)
{
	switch (ret) {
		case MNTRC_MOUNT_SUCCEEDS:
			return ("Mount succeeded");
		case MNTRC_NO_MOUNT:
			return ("Mount not performed");
		case MNTRC_OPENING_VFSTAB:
			return ("Error opening vfstab");
		case MNTRC_MOUNT_FAIL:
			return ("Mount failed");
		case MNTRC_MUST_MANUAL_FSCK:
			return ("Must manually run fsck on volume");
		case MNTRC_FSCK_FAILURE:
			return ("fsck failed on volume");
		default:
			break;
	}
	(void) snprintf(mntrc_text, sizeof (mntrc_text),
	    "Unknown error code=%d", ret);
	return (mntrc_text);
}

/*
 * given slice in the form /dev/dsk/cXXXXXX
 * return a pointer to the part after the last slash
 * else NULL
 */
static char *
jump_dev_prefix(const char *slicenm)
{
	char *ctd;

	if (slicenm == NULL)
		return (NULL);
	ctd = strrchr(slicenm, '/');
	if (ctd == NULL)
		return (NULL);
	ctd++;
	if (*ctd == '\0')
		return (NULL);
	return (ctd);
}
