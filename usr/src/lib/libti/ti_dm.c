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
#include <wait.h>
#include <stdarg.h>
#include <stdio.h>
#include <strings.h>
#include <unistd.h>
#include <sys/dkio.h>
#include <sys/mnttab.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/vtoc.h>

#include <ti_dm.h>
#include <ti_api.h>
#include <ls_api.h>

/*
 * if defined, create s1 slice for swap device
 * when default VTOC is being created
 */
#define	IDM_CREATE_S1_FOR_SWAP

/* global variables */

/* local constants */

#define	IDM_MNTTAB_PATH		"/etc/mnttab"


#ifdef	IDM_CREATE_S1_FOR_SWAP
/*
 * parameters for setting swap slice
 *
 * disk                 swap
 * =========================
 *  8 GB - 10 GB	0.5G
 *
 * 10 GB - 20 GB	1G
 *
 * >20 GB		2G
 */

static uint32_t idm_swap_size_table[][2] = {
	{ 10*1024,	512 },
	{ 20*1024,	1024 },
	{ 0,		2048 }
};
#endif /* IDM_CREATE_S1_FOR_SWAP */

/* private variables */

/* if set to B_TRUE, dry run mode is invoked, no changes done to the target */
static boolean_t	idm_dryrun_mode_fl = B_FALSE;


/* ------------------------ private functions --------------------------- */


/*
 * idm_debug_print()
 */
static void
idm_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("TIDM", dbg_lvl, buf);
	va_end(ap);
}


#ifdef IDM_CREATE_S1_FOR_SWAP

/*
 * Function:	idm_calc_swap_size()
 *
 * Description:	Calculate swap slice size in cylinders according to
 *		following algorithm (taken from orchestrator)
 *		  disk                 swap
 *		===========================
 *		 <= 10 GB		0.5G
 *
 *		 10 GB - 20 GB		1G
 *
 *		 >20 GB			2G
 *
 * Scope:	private
 * Parameters:	cyls_available - # of total cylinders available
 *		nsecs - # of sectors per cylinder
 *
 * Return:	0 - there is no space for swap slice available
 *		>0 - # of cylinders reserved for swap slice
 *
 */
static uint32_t
idm_calc_swap_size(uint32_t *cyls_available, uint32_t nsecs)
{
	int		i;
	uint32_t	mbs_available =
	    idm_cyls_to_mbs(*cyls_available, nsecs);
	uint32_t	cyls_swap = 0;

	/* find appropriate range or use maximum allowed */

	for (i = 0; idm_swap_size_table[i][0] != 0 &&
	    idm_swap_size_table[i][0] <= mbs_available; i++)
		;

	cyls_swap = idm_mbs_to_cyls(idm_swap_size_table[i][1], nsecs);

	/*
	 * if we allocated more than available for some reason,
	 * something went really wrong
	 */

	assert(cyls_swap < *cyls_available);

	*cyls_available -= cyls_swap;

	idm_debug_print(LS_DBGLVL_INFO, "Total space is %ld MiB, %ld MiB "
	    "(%ld cyls) will be dedicated to swap slice\n",
	    mbs_available, idm_swap_size_table[i][1], cyls_swap);

	return (cyls_swap);
}

#endif /* IDM_CREATE_S1_FOR_SWAP */


/*
 * Function:	idm_system()
 *
 * Description:	Execute shell commands in a thread-safe manner
 *
 * Scope:	private
 * Parameters:	cmd - the command to execute
 *
 * Return:	if popen() fails, -1, otherwise return code from command
 *
 */

static int
idm_system(const char *cmd)
{
	FILE	*p;
	int	ret;

	idm_debug_print(LS_DBGLVL_INFO, "dm cmd: "
	    "%s\n", cmd);

	if (!idm_dryrun_mode_fl) {
		if ((p = popen(cmd, "w")) == NULL)
			return (-1);

		ret = pclose(p);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0))
			return (-1);
	}

	return (0);
}


/*
 * Function:	idm_display_vtoc
 * Description:	Displays VTOC structure for debugging purposes
 *
 * Scope:	private
 * Parameters:	dbglvl - debugging level
 *		pvtoc - pointer to VTOC structure
 *
 */

static void
idm_display_vtoc(ls_dbglvl_t dbglvl, struct vtoc *pvtoc)
{
	int	i;

	idm_debug_print(dbglvl, "---------------------------------\n");
	idm_debug_print(dbglvl, " # TAG FLAG    1st_sec       size\n");
	idm_debug_print(dbglvl, "---------------------------------\n");

	for (i = 0; i < pvtoc->v_nparts; i++) {
		if (pvtoc->v_part[i].p_size == 0)
			continue;

		idm_debug_print(dbglvl,
		    "%2d  %02X   %02X %10ld %10ld\n", i,
		    pvtoc->v_part[i].p_tag, pvtoc->v_part[i].p_flag,
		    pvtoc->v_part[i].p_start, pvtoc->v_part[i].p_size);
	}

	idm_debug_print(dbglvl, "---------------------------------\n");
}


/*
 * Function:	idm_check_vtoc
 * Description:	sanity checking VTOC structure
 *
 * Scope:	private
 * Parameters:	pvtoc - pointer to VTOC structure
 *
 * Return:	IDM_E_SUCCES - VTOC sanity checking passed
 *		IDM_E_VTOC_INVALID - VTOC structure is invalid
 *
 */

static idm_errno_t
idm_check_vtoc(struct vtoc *pvtoc)
{
	assert(pvtoc != NULL);

	return (IDM_E_SUCCESS);
}


/*
 * Function:	idm_adjust_vtoc
 * Description:	Adjust VTOC structure. Following is done:
 *		[1] slice geometry is adjusted, so that every slice
 *		    starts and ends on cylinder boundary
 *		[2] avoid slices overlapping
 *
 * Scope:	private
 * Parameters:	pvtoc - pointer to VTOC structure
 *		nsecs - number of sectors per cylinder
 *
 * Return:	IDM_E_SUCCESS - adjusting succeeded, no changes done
 *		IDM_E_VTOC_MODIFIED - adjusting succeeded, VTOC modified
 *		IDM_E_VTOC_ADJUST_FAILED - VTOC structure can't be modified
 *
 */

static idm_errno_t
idm_adjust_vtoc(struct vtoc *pvtoc, uint16_t nsecs)
{
#ifndef sparc
	uint32_t	sector_min;	/* the 1st available sector */
#endif
	int		i;

	idm_debug_print(LS_DBGLVL_INFO, "Adjusting VTOC structure...\n");

	for (i = 0; i < pvtoc->v_nparts; i++) {

		/* Skip unused slices */

		if (pvtoc->v_part[i].p_size == 0)
			continue;

		/* don't check BOOT & BACKUP slices */

		if ((i == IDM_BOOT_SLICE) || (i == IDM_ALL_SLICE)) {
			idm_debug_print(LS_DBGLVL_INFO, "Slice %d "
			    "is not subject of checking process\n", i);

			continue;
		}

		/*
		 * adjust the 1st sector in case that
		 * [1] it doesn't start on cylinder boundary, OR
		 * [2] it occupies BOOT slice - doesn't apply to sparc
		 */

		if ((pvtoc->v_part[i].p_start % nsecs) != 0) {
			uint32_t old = pvtoc->v_part[i].p_start;

			/* round down/up to nearest cylinder */

			pvtoc->v_part[i].p_start =
			    ((old + (nsecs / 2)) / nsecs) * nsecs;

			idm_debug_print(LS_DBGLVL_INFO, "Start of slice %d "
			    "adjusted: %ld->%ld\n", i, old,
			    pvtoc->v_part[i].p_start);
		}

#ifndef sparc
		/*
		 * the 1st available sector is the one right after boot slice,
		 * which occupies the 1st cylinder.
		 */

		sector_min = pvtoc->v_part[IDM_BOOT_SLICE].p_size;

		if (pvtoc->v_part[i].p_start < sector_min) {
			uint32_t old_start = pvtoc->v_part[i].p_start;
			uint32_t old_size = pvtoc->v_part[i].p_size;

			/* adjust the 1st sector right after BOOT slice */

			pvtoc->v_part[i].p_start = sector_min;

			idm_debug_print(LS_DBGLVL_INFO, "Start of slice %d "
			    "adjusted: %ld->%ld\n", i, old_start,
			    pvtoc->v_part[i].p_start);

			/* adjust also size appropriately */

			old_start = sector_min - old_start;

			if (pvtoc->v_part[i].p_size < old_start) {
				idm_debug_print(LS_DBGLVL_INFO,
				    "Size&start of slice %d adjusted to 0\n");

				pvtoc->v_part[i].p_start = 0;
				pvtoc->v_part[i].p_size = 0;
			} else {
				pvtoc->v_part[i].p_size -= old_start;

				idm_debug_print(LS_DBGLVL_INFO, "Size of slice "
				    "%d adjusted: %d->%d\n", i, old_size,
				    pvtoc->v_part[i].p_size);
			}

		}
#endif

		/* adjust size */

		if ((pvtoc->v_part[i].p_size % nsecs) != 0) {
			uint32_t old = pvtoc->v_part[i].p_size;

			/* round down to nearest cylinder */

			pvtoc->v_part[i].p_size = (old / nsecs) * nsecs;

			idm_debug_print(LS_DBGLVL_INFO, "Size of slice %d "
			    "adjusted: %d->%d\n", i, old,
			    pvtoc->v_part[i].p_size);
		}
	}

	return (IDM_E_SUCCESS);
}


/* ----------------------- public functions --------------------------- */

/*
 * Function:	idm_unmount_all
 * Description:	Unmounts all filesystem mounted on all disk partitions/slices.
 *		Following steps are done:
 *		[1] /etc/mnttab is being parsed with getmntent(3C)
 *		[2] If <special> field begins with "/dev/dsk/<disk_name>",
 *		    attempt is made to unmount mounted filesystem by means
 *		    of "umount -f <special>" command.
 *
 * Scope:	public
 * Parameters:	disk_name - disk which should be released
 *
 * Return:	IDM_E_SUCCESS - All filesystem unmounted successfully
 *		IDM_E_UNMOUNT_FAILED - Unmount operation failed
 */

idm_errno_t
idm_unmount_all(char *disk_name)
{
	struct mnttab	mnt_tab;
	FILE		*pf;
	int		ret;
	char		device[MAXPATHLEN];
	char		cmd[IDM_MAXCMDLEN];
	/*
	 * open mnttab for reading
	 */

	pf = fopen(IDM_MNTTAB_PATH, "r");

	if (pf == NULL) {
		idm_debug_print(LS_DBGLVL_ERR, "Couldn't open "
		    "<%s> for reading\n", IDM_MNTTAB_PATH);

		return (IDM_E_UNMOUNT_FAILED);
	} else
		idm_debug_print(LS_DBGLVL_INFO, "<%s> opened for "
		    "reading\n", IDM_MNTTAB_PATH);

	(void) snprintf(device, sizeof (device), "/dev/dsk/%s", disk_name);

	while ((ret = getmntent(pf, &mnt_tab)) == 0) {

		idm_debug_print(LS_DBGLVL_INFO, " mnttab: D=%s, M=%s, F=%s, "
		    "O=%s\n", mnt_tab.mnt_special, mnt_tab.mnt_mountp,
		    mnt_tab.mnt_fstype, mnt_tab.mnt_mntopts);

		/*
		 * look at the <special> field. If it begins with
		 * "/dev/dsk/<disk_name>" string, try to unmount it.
		 */

		if (strncmp(mnt_tab.mnt_special, device, strlen(device))
		    == 0) {
			idm_debug_print(LS_DBGLVL_INFO, "%s is mounted "
			    "on %s - will be unmounted now\n",
			    mnt_tab.mnt_mountp, mnt_tab.mnt_special);

			(void) snprintf(cmd, sizeof (cmd),
			    "/usr/sbin/umount -f %s >/dev/null",
			    mnt_tab.mnt_special);

			ret = idm_system(cmd);

			if (ret == -1) {
				idm_debug_print(LS_DBGLVL_ERR, "dm: "
				    "Couldn't unmount %s\n",
				    mnt_tab.mnt_mountp);

				return (IDM_E_UNMOUNT_FAILED);
			}
		}
	}

	if (fclose(pf) != 0)
		idm_debug_print(LS_DBGLVL_WARN, "Closing "
		    "<%s> failed\n", IDM_MNTTAB_PATH);

	/* -1 return code (EOF) means "all items were processed" - this is OK */

	if (ret == -1)
		return (IDM_E_SUCCESS);

	idm_debug_print(LS_DBGLVL_ERR, "getmntent(3C) failed with "
	    "error code %d\n", ret);

	return (IDM_E_UNMOUNT_FAILED);
}


/*
 * Function:	idm_fdisk_whole_disk
 * Description:	Uses whole disk as target. Creates one Solaris2 partition
 *		occupying all available disk space.
 *
 * Scope:	public
 * Parameters:	disk_name - disk which should be formatted with one Solaris2
 *		parition
 *
 * Return:	IDM_E_SUCCESS - Solaris2 partition created successfully
 *		IDM_E_FDISK_WDISK_FAILED - "fdisk -n -B" command failed
 */

idm_errno_t
idm_fdisk_whole_disk(char *disk_name)
{
	char	cmd[IDM_MAXCMDLEN];
	int	ret;

	/* if invoked in dry run mode, no changes done to the target */

	if (idm_dryrun_mode_fl) {
		(void) sleep(1);

		return (IDM_E_SUCCESS);
	}

	/*
	 * Provide fdisk(1M) with "-n" option in order to make it work
	 * in non-interactive mode. Otherwise it might hang the installer
	 * when waiting for user input.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/fdisk -n -B /dev/rdsk/%sp0 >/dev/null",
	    disk_name);

	idm_debug_print(LS_DBGLVL_INFO, "fdisk: "
	    "Creating Solaris2 partition on whole disk %s:\n", disk_name);

	ret = idm_system(cmd);

	if (ret == -1) {
		idm_debug_print(LS_DBGLVL_ERR, "fdisk: "
		    "fdisk -n -B failed. Couldn't create Solaris2 "
		    "partition on whole disk %s", disk_name);

		return (IDM_E_FDISK_WDISK_FAILED);
	}

	return (IDM_E_SUCCESS);
}


/*
 * Function:	idm_create_vtoc
 * Description:	Creates VTOC structure on existing Solaris2 partition
 *		according to set of attributes provided as nv list.
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	IDM_E_SUCCESS - VTOC created successfully
 *		IDM_E_VTOC_ATTR_INVALID - invalid set of attributes passed
 *		IDM_E_VTOC_FAILED - VTOC creation failed
 */

idm_errno_t
idm_create_vtoc(nvlist_t *attrs)
{
	char		cmd[IDM_MAXCMDLEN];
	int		ret;
	struct vtoc	vtoc;
	struct dk_geom	geom;
	char		device[MAXPATHLEN];
	char		*disk_name;
	int		fd;
	int		i;
	uint16_t	slice_num;
	uint16_t	*slice_parts, *slice_tags;
	uint16_t	*slice_flags;
	uint64_t	*slice_1stsecs, *slice_sizes;
	uint_t		nelem;
	uint32_t	nsecs;
	boolean_t	fl_slice_def_layout = B_FALSE;

	/* sanity check */

	assert(attrs != NULL);

	/*
	 * Obtain disk name. If not available, return with error
	 */

	if (nvlist_lookup_string(attrs, TI_ATTR_FDISK_DISK_NAME, &disk_name)
	    != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
		    "TI_ATTR_FDISK_DISK_NAME is required but not defined\n");

		return (IDM_E_VTOC_FAILED);
	}

	/*
	 * look, if default layout is to be used. If this is the case, dedicate
	 * slice 1 to swap (if required) and remaining space on disk/Solaris2
	 * partition to slice 0
	 */

	if ((nvlist_lookup_boolean_value(attrs, TI_ATTR_SLICE_DEFAULT_LAYOUT,
	    &fl_slice_def_layout) == 0) && fl_slice_def_layout) {

#ifdef	IDM_CREATE_S1_FOR_SWAP
		idm_debug_print(LS_DBGLVL_INFO, "vtoc: Default layout required,"
		    " s1 will be dedicated to swap, s0 will occupy remaining"
		    " space\n");

		slice_num = 2;
#else
		idm_debug_print(LS_DBGLVL_INFO, "vtoc: Default layout required,"
		    "slice 0 will occupy all disk/fdisk partition\n");

		slice_num = 1;
#endif
	}

	/*
	 * check for remaining attributes, only if default layout is not
	 * required. Also, consider 1st inforamtion to be optional.
	 */

	if (!fl_slice_def_layout) {
		/*
		 * Obtain number of VTOC slices to be created. If not available,
		 * return with error
		 */

		if (nvlist_lookup_uint16(attrs, TI_ATTR_SLICE_NUM, &slice_num)
		    != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "TI_ATTR_SLICE_NUM is required but not defined\n");

			return (IDM_E_VTOC_FAILED);
		}

		/*
		 * Obtain attributes describing VTOC geometry. If not available,
		 * return with error. Check if arrays contain right number of
		 * elements.
		 */

		/* slice numbers */

		if (nvlist_lookup_uint16_array(attrs, TI_ATTR_SLICE_PARTS,
		    &slice_parts, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			"TI_ATTR_SLICE_PARTS is required but not defined\n");

			return (IDM_E_VTOC_FAILED);
		} else if (nelem != slice_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "size of TI_ATTR_SLICE_PARTS array is invalid\n");

			return (IDM_E_VTOC_FAILED);
		}

		/* slice tags */

		if (nvlist_lookup_uint16_array(attrs, TI_ATTR_SLICE_TAGS,
		    &slice_tags, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "TI_ATTR_SLICE_TAGS is required but not defined\n");

			return (IDM_E_VTOC_FAILED);
		} else if (nelem != slice_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "size of TI_ATTR_SLICE_TAGS array is invalid\n");

			return (IDM_E_VTOC_FAILED);
		}

		/* slice flags */

		if (nvlist_lookup_uint16_array(attrs, TI_ATTR_SLICE_FLAGS,
		    &slice_flags, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "TI_ATTR_SLICE_FLAGS is required but not "
			    "defined\n");

			return (IDM_E_VTOC_FAILED);
		} else if (nelem != slice_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "size of TI_ATTR_SLICE_FLAGS array is invalid\n");

			return (IDM_E_VTOC_FAILED);
		}

		/* firts slice sectors */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_SLICE_1STSECS,
		    &slice_1stsecs, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "TI_ATTR_SLICE_1STSECS is required but not "
			    "defined\n");

			return (IDM_E_VTOC_FAILED);
		} else if (nelem != slice_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "size of TI_ATTR_SLICE_1STSECS array is invalid\n");

			return (IDM_E_VTOC_FAILED);
		}

		/* slice sizes */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_SLICE_SIZES,
		    &slice_sizes, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "TI_ATTR_SLICE_SIZES is required but not "
			    "defined\n");

			return (IDM_E_VTOC_FAILED);
		} else if (nelem != slice_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
			    "size of TI_ATTR_SLICE_SIZES array is invalid\n");

			return (IDM_E_VTOC_FAILED);
		}
	}

	idm_debug_print(LS_DBGLVL_INFO, "Creating %d slices on disk %s...\n",
	    slice_num, disk_name);

	(void) snprintf(device, MAXPATHLEN, "/dev/rdsk/%ss2", disk_name);

	/* open device */

	if ((fd = open(device, O_RDWR | O_NDELAY)) < 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
		    "couldn't open %s device\n", device);

		return (IDM_E_VTOC_FAILED);
	}

	/*
	 * Display disk geometry information
	 */

	if (ioctl(fd, DKIOCGGEOM, &geom) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Couldn't obtain "
		    "information about geometry of %s device\n", device);

		return (IDM_E_VTOC_FAILED);
	} else {
		/* calculate number of sectors per cylinder */

		nsecs = (uint32_t)geom.dkg_nhead * geom.dkg_nsect;

		idm_debug_print(LS_DBGLVL_INFO, "Disk geometry:\n"
		    " H=%d, Sec/Track=%ld, Sec/Cyl=%d\n"
		    " Ct=%d, Ca=%d, Co=%d, Cp=%d\n",
		    (int)geom.dkg_nhead, (int)geom.dkg_nsect,
		    nsecs,
		    (int)geom.dkg_ncyl, (int)geom.dkg_acyl,
		    (int)geom.dkg_bcyl, (int)geom.dkg_pcyl);
	}

#if 0
	/*
	 * Clear in memory VTOC configuration. Final VTOC structure
	 * will be described by attributes. Slices 2&8 are created
	 * automaticaly.
	 */

	(void) memset(&vtoc, 0, sizeof (struct vtoc));
	vtoc.v_sectorsz = 512;

	/*
	 * max number of slices is 16 for x86, 8 for sparc.
	 * For now, only x86 is supported. Needs to be modified
	 * when sparc platform is supported.
	 */
	vtoc.v_nparts = NDKAP;
	vtoc.v_sanity = VTOC_SANE;
	vtoc.v_version = V_VERSION;

#else
	/*
	 * Read original VTOC from target. When tried previously with VTOC
	 * created from scratch, format complained about missing disk info.
	 * All slices are deleted, but rest of the information is preserved.
	 */

	if (read_vtoc(fd, &vtoc) < 0) {
		idm_debug_print(LS_DBGLVL_ERR, "vtoc: Couldn't read "
		    "existing VTOC from %s device\n", device);

		(void) close(fd);

		return (IDM_E_VTOC_FAILED);
	}

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "  Original VTOC configuration    \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &vtoc);

	/*
	 * Clear slice information. Everything else is preserved.
	 */

	for (i = 0; i < vtoc.v_nparts; i++) {
		vtoc.v_part[i].p_start = 0;
		vtoc.v_part[i].p_size = 0;
		vtoc.v_part[i].p_tag = 0;
		vtoc.v_part[i].p_flag = 0;
	}
#endif

	/* create slice 2 (ALL) - contains all available space */

	vtoc.v_part[IDM_ALL_SLICE].p_tag = V_BACKUP;
	vtoc.v_part[IDM_ALL_SLICE].p_flag = V_UNMNT;
	vtoc.v_part[IDM_ALL_SLICE].p_start = 0;
	vtoc.v_part[IDM_ALL_SLICE].p_size =
	    idm_cyls_to_secs(geom.dkg_ncyl, nsecs);

	/* create slice 8 (BOOT) - allocates 1st cylinder - only x86 */
#ifndef sparc
	vtoc.v_part[IDM_BOOT_SLICE].p_tag = V_BOOT;
	vtoc.v_part[IDM_BOOT_SLICE].p_flag = V_UNMNT;
	vtoc.v_part[IDM_BOOT_SLICE].p_start = 0;
	vtoc.v_part[IDM_BOOT_SLICE].p_size =
	    idm_cyls_to_secs(IDM_BOOT_SLICE_RES_CYL, nsecs);
#endif

	/*
	 * Modify original VTOC structure according to set of attributes.
	 */

	if (fl_slice_def_layout) {
		uint32_t	cyls_available = geom.dkg_ncyl
		    - IDM_BOOT_SLICE_RES_CYL;

#ifdef IDM_CREATE_S1_FOR_SWAP
		uint32_t	cyls_swap = 0;

		/*
		 * if required, create slice 1 for holding swap. Assign
		 * remaining space to slice 0.
		 */
		cyls_swap = idm_calc_swap_size(&cyls_available, nsecs);

		if (cyls_swap != 0) {
			vtoc.v_part[1].p_start = idm_cyls_to_secs(
			    IDM_BOOT_SLICE_RES_CYL, nsecs);

			idm_debug_print(LS_DBGLVL_INFO,
			    "%ld cyls were dedicated to swap slice\n",
			    cyls_swap);

			vtoc.v_part[1].p_size = idm_cyls_to_secs(cyls_swap,
			    nsecs);

			vtoc.v_part[1].p_tag = V_SWAP;
			vtoc.v_part[1].p_flag = V_UNMNT;
		} else {
			idm_debug_print(LS_DBGLVL_WARN,
			    "Space for swap slice s1 not available\n");
		}
#endif
		/*
		 * slice 0 goes after slice 1, so that it could grow up
		 * if there is additional free space available
		 */

		vtoc.v_part[0].p_start = vtoc.v_part[1].p_start
		    + vtoc.v_part[1].p_size;

		vtoc.v_part[0].p_size =
		    idm_cyls_to_secs(cyls_available, nsecs);

		vtoc.v_part[0].p_tag = V_ROOT;
		vtoc.v_part[0].p_flag = 0x00;

	} else {
		for (i = 0; i < slice_num; i++) {
			uint16_t	part_num;

			part_num = slice_parts[i];
			vtoc.v_part[part_num].p_start = slice_1stsecs[i];
			vtoc.v_part[part_num].p_size = slice_sizes[i];
			vtoc.v_part[part_num].p_tag = slice_tags[i];
			vtoc.v_part[part_num].p_flag = slice_flags[i];
		}
	}

	/* display modified VTOC structure */

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "      New VTOC configuration     \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &vtoc);

	/*
	 * Adjust VTOC geometry part, so that slices start and end on
	 * cylinder boundary. Probably not necessary for x86 (done in
	 * kernel) but required for sparc.
	 */

#if 1
	if (idm_adjust_vtoc(&vtoc, nsecs) != IDM_E_SUCCESS) {
		idm_debug_print(LS_DBGLVL_ERR, "Adjusting VTOC failed\n");

		return (IDM_E_VTOC_FAILED);
	}

	/* display adjusted VTOC structure */

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "   Adjusted VTOC configuration   \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &vtoc);

	/*
	 * Do some kind of sanity check for newly created VTOC structure
	 * before it is finaly written to disk
	 */

	if (idm_check_vtoc(&vtoc) != IDM_E_SUCCESS) {
		idm_debug_print(LS_DBGLVL_ERR, "Checking VTOC failed\n");

		return (IDM_E_VTOC_FAILED);
	}
#endif

	/* write out the VTOC (and label) */

	/* if invoked in dry run mode, no changes done to the target */

	if (idm_dryrun_mode_fl) {
		(void) sleep(1);

		(void) close(fd);
		return (IDM_E_SUCCESS);
	}

	if (write_vtoc(fd, &vtoc) < 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Couldn't write "
		    "VTOC to %s device, write_vtoc() failed\n", device);

		(void) close(fd);

		return (IDM_E_VTOC_FAILED);
	}

	(void) close(fd);

#ifdef IDM_CREATE_S1_FOR_SWAP
	/* Add swap device to the swap pool */

	idm_debug_print(LS_DBGLVL_INFO, "Adding /dev/dsk/%ss1 "
	    "to the swap pool...\n", disk_name);

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/swap -a /dev/dsk/%ss1 >/dev/null", disk_name);

	ret = idm_system(cmd);

	if (ret == -1) {
		idm_debug_print(LS_DBGLVL_WARN,
		    "Couldn't add </dev/dsk/%ss1> to swap pool\n", disk_name);
	}
#endif

	return (IDM_E_SUCCESS);
}


/*
 * Function:	idm_dryrun_mode
 * Description:	Makes TI disk module work in dry run mode.
 *		No changes done to the target.
 *
 * Scope:	public
 * Parameters:
 *
 * Return:
 */

void
idm_dryrun_mode(void)
{
	idm_dryrun_mode_fl = B_TRUE;
}
