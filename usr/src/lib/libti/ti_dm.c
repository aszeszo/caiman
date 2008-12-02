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
#include <stdlib.h>
#include <strings.h>
#include <unistd.h>
#include <sys/dkio.h>
#include <sys/mnttab.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <sys/types.h>
#include <sys/vtoc.h>

#include <ti_dm.h>
#include <ti_api.h>
#include <ls_api.h>

/* global variables */

/* local constants */

#define	IDM_MNTTAB_PATH		"/etc/mnttab"

/*
 * parameters for setting swap slice
 *
 * disk                 swap
 * =========================
 *  8 GB - 10 GB        0.5G
 *
 * 10 GB - 20 GB        1G
 *
 * >20 GB            2G
 */

static uint32_t idm_swap_size_table[][2] = {
	{ 10*1024,	512 },
	{ 20*1024,	1024 },
	{ 0,		2048 }
};


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

/*
 * Convert extvtoc structure to vtoc.
 * This is really temporary and must be removed
 * as soon as write_extvtoc bug(CR 6769481) is fixed.
 *
 */

static void
convert_extvtoc_to_vtoc(struct extvtoc *extvp, struct vtoc *vp)
{
	int i;

	for (i = 0; i < 3; i++)
		vp->v_bootinfo[i] = (unsigned long)extvp->v_bootinfo[i];

	vp->v_sanity = (unsigned long)extvp->v_sanity;
	vp->v_version = (unsigned long)extvp->v_version;
	bcopy(extvp->v_volume, vp->v_volume, LEN_DKL_VVOL);
	vp->v_sectorsz = extvp->v_sectorsz;
	vp->v_nparts = extvp->v_nparts;
	for (i = 0; i < 10; i++)
		vp->v_reserved[i] = (unsigned long)extvp->v_reserved[i];
	for (i = 0; i < V_NUMPAR; i++) {
		vp->v_part[i].p_tag = extvp->v_part[i].p_tag;
		vp->v_part[i].p_flag = extvp->v_part[i].p_flag;
		vp->v_part[i].p_start = (daddr_t)extvp->v_part[i].p_start;
		vp->v_part[i].p_size = (long)extvp->v_part[i].p_size;
		vp->timestamp[i] = (time_t)extvp->timestamp[i];
	}
	bcopy(extvp->v_asciilabel, vp->v_asciilabel, LEN_DKL_ASCII);
}
/*
 * XXX Temporary function and should be removed when CR 6769487 is fixed.
 * Use DKIOCGMEDIAINFO to get the capacity of the drive to get the true
 * capacity.
 * Return:
 * 	-1: failure
 *	0: less than 1TB
 *	1: more than 1TB
 */
static int
idm_is_mtb_disk(int fd)
{
	struct dk_minfo	dkinfo;
	int	ret = -1;

	if (ioctl(fd, DKIOCGMEDIAINFO, &dkinfo) < 0) {
		idm_debug_print(LS_DBGLVL_ERR, "DKIOCGMEDIAINFO failed\n");

		return (-1);
	}

	if (dkinfo.dki_media_type == DK_FIXED_DISK) {
		ret = (dkinfo.dki_capacity < ONE_TB_IN_BLKS) ? 0 : 1;
	}

	return (ret);

}
/*
 * Function:	idm_calc_swap_size()
 *
 * Description:	Calculate swap slice size in cylinders according to
 *		following algorithm (taken from orchestrator)
 *		 disk                 swap
 *		===========================
 *		<= 10 GB		0.5G
 *
 *		10 GB - 20 GB		1G
 *
 *		>20 GB			2G
 *
 * Scope:	private
 * Parameters:	cyls_available - # of total cylinders available
 *		nsecs - # of sectors per cylinder
 *
 * Return:	0 - there is no space for swap slice available
 *		>0 - # of cylinders reserved for swap slice
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
idm_system(char *cmd)
{
	FILE	*p;
	int	ret;
	char	errbuf[IDM_MAXCMDLEN];

	/*
	 * catch stderr for debugging purposes
	 */

	if (strlcat(cmd, " 2>&1 1>/dev/null", IDM_MAXCMDLEN) >= IDM_MAXCMDLEN)
		idm_debug_print(LS_DBGLVL_WARN,
		    "idm_system: Couldn't redirect stderr\n");

	idm_debug_print(LS_DBGLVL_INFO, "dm cmd: "
	    "%s\n", cmd);

	if (!idm_dryrun_mode_fl) {
		if ((p = popen(cmd, "r")) == NULL)
			return (-1);

		while (fgets(errbuf, sizeof (errbuf), p) != NULL)
			idm_debug_print(LS_DBGLVL_WARN, " stderr:%s", errbuf);

		ret = pclose(p);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0))
			return (-1);
	}

	return (0);
}


/*
 * Function:	idm_display_vtoc
 * Description:	Displays an extended VTOC structure for debugging purposes
 *
 * Scope:	private
 * Parameters:	dbglvl - debugging level
 *		pvtoc - pointer to extvtoc structure
 *
 */

static void
idm_display_vtoc(ls_dbglvl_t dbglvl, struct extvtoc *pvtoc)
{
	int	i;

	idm_debug_print(dbglvl, "---------------------------------\n");
	idm_debug_print(dbglvl, " # TAG FLAG    1st_sec       size\n");
	idm_debug_print(dbglvl, "---------------------------------\n");

	for (i = 0; i < pvtoc->v_nparts; i++) {
		if (pvtoc->v_part[i].p_size == 0)
			continue;

		idm_debug_print(dbglvl,
		    "%2d  %02X   %02X %10lld %10lld\n", i,
		    pvtoc->v_part[i].p_tag, pvtoc->v_part[i].p_flag,
		    pvtoc->v_part[i].p_start, pvtoc->v_part[i].p_size);
	}

	idm_debug_print(dbglvl, "---------------------------------\n");
}


/*
 * Function:	idm_check_vtoc
 * Description:	sanity checking an extended VTOC structure
 *
 * Scope:	private
 * Parameters:	pvtoc - pointer to extvtoc structure
 *
 * Return:	IDM_E_SUCCES - VTOC sanity checking passed
 *		IDM_E_VTOC_INVALID - VTOC structure is invalid
 *
 */

static idm_errno_t
idm_check_vtoc(struct extvtoc *pvtoc)
{
	assert(pvtoc != NULL);

	return (IDM_E_SUCCESS);
}


/*
 * Function:	idm_adjust_vtoc
 * Description:	Adjust an extended VTOC structure. Following is done:
 *		[1] slice geometry is adjusted, so that every slice
 *		    starts and ends on cylinder boundary
 *		[2] avoid slices overlapping
 *
 * Scope:	private
 * Parameters:	pvtoc - pointer to extvtoc structure
 *		nsecs - number of sectors per cylinder
 *
 * Return:	IDM_E_SUCCESS - adjusting succeeded, no changes done
 *		IDM_E_VTOC_MODIFIED - adjusting succeeded, VTOC modified
 *		IDM_E_VTOC_ADJUST_FAILED - VTOC structure can't be modified
 *
 */

static idm_errno_t
idm_adjust_vtoc(struct extvtoc *pvtoc, uint16_t nsecs)
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
			diskaddr_t old = pvtoc->v_part[i].p_start;

			/* round down/up to nearest cylinder */

			pvtoc->v_part[i].p_start =
			    ((old + (nsecs / 2)) / nsecs) * nsecs;

			idm_debug_print(LS_DBGLVL_INFO, "Start of slice %d "
			    "adjusted: %lld->%lld\n", i, old,
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


/*
 * Function:	idm_fill_preserved_partitions
 * Description:	Read partition geometry information for partitions which should
 *		remain unchanged
 *
 * Scope:	private
 * Parameters:	disk_name	- disk device name in c#t#d# format
 *		pt		- pointer to structure containing information
 *				  about partition table to be created
 *		part_preserve	- array of flags indicating which partition
 *				  should be preserved
 *		npart		- number of partitions to be processed
 *
 * Return:	IDM_E_SUCCESS - partition info successfully read
 *		IDM_E_FDISK_CLI_FAILED - fdisk(1M) command failed
 *
 */

static idm_errno_t
idm_fill_preserved_partitions(char *disk_name, idm_part_table_t *pt,
    boolean_t *part_preserve, uint_t npart)
{
	FILE			*pt_file;
	char			cmd[IDM_MAXCMDLEN];
	char			fdisk_line[1000];
	idm_fdisk_partition_t	*pt_orig, *pt_tmp;
	uint_t			npart_orig;

	uint_t			id, active;
	uint64_t		bh, bs, bc, eh, es, ec, offset, size;

	uint_t			i;
	int			ret;

	/* Read original partition table to temporary file */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/fdisk -n -R -v -W " IDM_ORIG_PARTITION_TABLE_FILE
	    " /dev/rdsk/%sp0", disk_name);

	ret = idm_system(cmd);

	if (ret == -1) {
		idm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't read partition table for disk %s\n", disk_name);

		return (IDM_E_FDISK_CLI_FAILED);
	}

	pt_file = fopen(IDM_ORIG_PARTITION_TABLE_FILE, "r");

	if (pt_file == NULL) {
		idm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't open partition table file %s\n",
		    IDM_ORIG_PARTITION_TABLE_FILE);

		return (IDM_E_FDISK_CLI_FAILED);
	}

	/* Read original partition table to memory */

	pt_orig = NULL;
	npart_orig = 0;
	while (fgets(fdisk_line, sizeof (fdisk_line), pt_file) != NULL) {
		/*
		 * lines starting with '*' are comments - ignore them
		 * as well as empty lines
		 */

		if ((fdisk_line[0] == '*') || (fdisk_line[0] == '\n'))
			continue;

		/*
		 * read line describing partition/logical volume.
		 * Line is in following format (decimal numbers):
		 *
		 * id act bhead bsect bcyl ehead esect ecyl rsect numsect
		 *
		 * id - partition
		 * act - active flag - 0|128
		 * bhead, bsect, bcyl - start of partition in CHS format
		 * ehead, esect, ecyl - end of partition in CHS format
		 * rsect - partition offset in sectors from beginning
		 *	   of the disk
		 * numsect - size of partition in sectors
		 */

		id = active = bh = bs = bc = eh = es = ec = offset = size = 0;

		ret = sscanf(fdisk_line, "%u%u%llu%llu%llu%llu%llu%llu%llu%llu",
		    &id, &active, &bh, &bs, &bc, &eh, &es, &ec, &offset, &size);

		if (ret != 10) {
			idm_debug_print(LS_DBGLVL_ERR,
			    "following fdisk line has unsupported format:\n"
			    "%s\n", fdisk_line);

			(void) fclose(pt_file);
			free(pt_orig);

			return (IDM_E_FDISK_CLI_FAILED);
		}

		/* allocate memory for new entry and store the values */
		pt_tmp = pt_orig;
		pt_orig = realloc(pt_orig, (npart_orig + 1) *
		    sizeof (idm_fdisk_partition_t));

		if (pt_orig == NULL) {
			idm_debug_print(LS_DBGLVL_ERR, "OOM :-(\n");

			free(pt_tmp);
			(void) fclose(pt_file);
			return (IDM_E_FDISK_CLI_FAILED);
		}

		pt_orig[npart_orig].id = id;
		pt_orig[npart_orig].active = active;
		pt_orig[npart_orig].bhead = bh;
		pt_orig[npart_orig].bsect = bs;
		pt_orig[npart_orig].bcyl = bc;
		pt_orig[npart_orig].ehead = eh;
		pt_orig[npart_orig].esect = es;
		pt_orig[npart_orig].ecyl = ec;
		pt_orig[npart_orig].offset = offset;
		pt_orig[npart_orig].size = size;

		npart_orig++;
	}

	(void) fclose(pt_file);

	idm_debug_print(LS_DBGLVL_INFO,
	    "Original partition table contains %u entries\n", npart_orig);

	/*
	 * print original fdisk partition table for debugging purposes
	 */

	idm_debug_print(LS_DBGLVL_INFO,
	    "Original partition table configuration\n");

	idm_debug_print(LS_DBGLVL_INFO,
	    "*   ID    bh    bs    bc    eh    es    ec     "
	    "offset       size\n");

	idm_debug_print(LS_DBGLVL_INFO,
	    "-----------------------------------------------"
	    "-----------------\n");

	for (i = 0; i < npart_orig; i++) {
		idm_debug_print(LS_DBGLVL_INFO,
		    "%2d%s %02X %5llu %5llu %5llu %5llu %5llu %5llu %10llu "
		    "%10llu\n",
		    i + 1, pt_orig[i].active != 0 ? "+" : " ",
		    pt_orig[i].id, pt_orig[i].bhead, pt_orig[i].bsect,
		    pt_orig[i].bcyl, pt_orig[i].ehead, pt_orig[i].esect,
		    pt_orig[i].ecyl, pt_orig[i].offset, pt_orig[i].size);
	}

	idm_debug_print(LS_DBGLVL_INFO,
	    "-----------------------------------------------"
	    "-----------------\n");


	/*
	 * Go through new partition table and if there is entry to be
	 * preserved, try to find appropriate record in original
	 * partition table. Use 1st sector and sector size as keys.
	 */

	for (i = 0; i < npart; i++) {
		uint_t	j;

		/*
		 * If this partition shouldn't be preserved, continue
		 */

		if (!part_preserve[i]) {
			idm_debug_print(LS_DBGLVL_INFO,
			    "Partition %d won't be preserved\n", i + 1);

			continue;
		}

		/*
		 * Try to find matching entry in exiting partition table.
		 * Use 1st sector and sector size as matching keys.
		 */

		for (j = 0; j < npart_orig; j++) {
			if ((pt->offset[i] == pt_orig[j].offset) &&
			    (pt->size[i] == pt_orig[j].size))
				break;
		}

		/*
		 * If matching entry not found, don't proceed, since
		 * something went wrong and we might corrupt existing
		 * partition table
		 */

		if (j == npart_orig) {
			idm_debug_print(LS_DBGLVL_ERR,
			    "Partition %d can't be preserved, matching entry "
			    "not found in orig. part. table\n", i + 1);

			free(pt_orig);
			return (IDM_E_FDISK_CLI_FAILED);
		}

		idm_debug_print(LS_DBGLVL_INFO,
		    "Partition %d will be preserved, matching entry "
		    "found in orig. part. table\n", i + 1);

		/* replace new values with original ones */

		pt->id[i] = pt_orig[j].id;
		pt->active[i] = pt_orig[j].active;
		pt->bhead[i] = pt_orig[j].bhead;
		pt->bsect[i] = pt_orig[j].bsect;
		pt->bcyl[i] = pt_orig[j].bcyl;
		pt->ehead[i] = pt_orig[j].ehead;
		pt->esect[i] = pt_orig[j].esect;
		pt->ecyl[i] = pt_orig[j].ecyl;
		pt->offset[i] = pt_orig[j].offset;
		pt->size[i] = pt_orig[j].size;
	}

	free(pt_orig);
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
			    "/usr/sbin/umount -f %s",
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
 * Function:	idm_release_swap
 * Description:	Delete all swap pools on disk
 *		Following steps are done:
 *		[1] /etc/mnttab is being parsed with getmntent(3C)
 *		[2] If <special> field begins with "/dev/dsk/<disk_name>",
 *		    attempt is made to unmount mounted filesystem by means
 *		    of "umount -f <special>" command.
 *
 * Scope:	public
 * Parameters:	disk_name - disk which should be released
 *
 * Return:	IDM_E_SUCCESS - swap devices released
 *		IDM_E_RELEASE_SWAP_FAILED - releasing of swap devices failed
 */

idm_errno_t
idm_release_swap(char *disk_name)
{
	swaptbl_t	*st;
	swapres_t 	swr;
	int		i, num;
	char		*strtab;

	/* sanity check */

	assert(disk_name != NULL);

	/* get the number of swap devices */

	if ((num = swapctl(SC_GETNSWP, NULL)) == -1) {
		idm_debug_print(LS_DBGLVL_WARN, "Couldn't obtain number"
		    " of swap devices\n");

		return (IDM_E_RELEASE_SWAP_FAILED);
	}

	if (num == 0) {
		/* no swap devices configured */
		idm_debug_print(LS_DBGLVL_INFO, "No swap devices configured\n");

		return (IDM_E_SUCCESS);
	}

	/* allocate the swaptable */

	if ((st = malloc(num * sizeof (swapent_t) + sizeof (int))) == NULL) {
		idm_debug_print(LS_DBGLVL_WARN, "malloc() failed - "
		    "couldn't allocate memory for swap table\n");

		return (IDM_E_RELEASE_SWAP_FAILED);
	}

	/* allocate num string holders */

	if ((strtab = (char *)malloc(num * MAXPATHLEN)) == NULL) {
		free(st);

		idm_debug_print(LS_DBGLVL_WARN, "malloc() failed - "
		    "couldn't allocate memory for swap table\n");

		return (IDM_E_RELEASE_SWAP_FAILED);
	}

	/* initialize string pointers */

	for (i = 0; i < num; i++) {
		st->swt_ent[i].ste_path = strtab + (i * MAXPATHLEN);
	}

	/* get the swaptable list from the swap ctl */
	st->swt_n = num;

	if ((num = swapctl(SC_LIST, st)) == -1) {
		idm_debug_print(LS_DBGLVL_WARN, "Couldn't obtain list"
		    " of swap devices\n");

		free(strtab);
		free(st);
		return (IDM_E_RELEASE_SWAP_FAILED);
	}

	/*
	 * Walk through swap list and remove swap device
	 * if it is on target disk
	 */

	idm_debug_print(LS_DBGLVL_INFO, "Swap devices in use:\n");

	for (i = 0; i < num; i++) {
		if (strstr(st->swt_ent[i].ste_path, disk_name) != NULL) {
			/* delete the swapfile */

			swr.sr_name = st->swt_ent[i].ste_path;
			swr.sr_start = st->swt_ent[i].ste_start;
			swr.sr_length = st->swt_ent[i].ste_length;

			if (swapctl(SC_REMOVE, &swr) < 0) {
				idm_debug_print(LS_DBGLVL_WARN, "Couldn't "
				    "remove %s swap device\n");

					free(strtab);
					free(st);
					return (IDM_E_RELEASE_SWAP_FAILED);
			}

			idm_debug_print(LS_DBGLVL_INFO, " %s - removed\n",
			    st->swt_ent[i].ste_path);
		} else
			idm_debug_print(LS_DBGLVL_INFO, " %s - preserved\n",
			    st->swt_ent[i].ste_path);
	}

	/* free up what was created */

	free(strtab);
	free(st);

	return (IDM_E_SUCCESS);
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
	    "/usr/sbin/fdisk -n -B /dev/rdsk/%sp0",
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
 * Function:	idm_fdisk_create_part_table
 * Description:	Creates partition table on disk
 *
 * Scope:	public
 * Parameters:	disk_name - disk which should be partitioned
 *
 * Return:	IDM_E_SUCCESS - partition table created successfully
 *		IDM_E_FDISK_ATTR_INVALID - invalid set of attributes passed
 *		IDM_E_FDISK_PART_TABLE_FAILED - partition table couldn't
 *		    be created
 */

idm_errno_t
idm_fdisk_create_part_table(nvlist_t *attrs)
{
	char			cmd[IDM_MAXCMDLEN];
	int			ret;
	int			i;
	uint16_t		part_num;
	idm_part_table_t	*part_table, *new_part_table;
	uint_t			nelem;
	char			*disk_name;
	char			pt_file_template[] = "/tmp/ti_fdisk_XXXXXX";
	char			*pt_file_name;
	FILE			*pt_file;

	uint8_t		*part_ids, *part_active_flags;
	uint64_t	*part_bheads, *part_bsecs, *part_bcyls;
	uint64_t	*part_eheads, *part_esecs, *part_ecyls;
	uint64_t	*part_offsets, *part_sizes;
	boolean_t	*part_preserve;

	boolean_t	chs_geometry_provided = B_FALSE;

	/* obtain disk name which should be partitioned */

	if (nvlist_lookup_string(attrs, TI_ATTR_FDISK_DISK_NAME, &disk_name)
	    != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create fdisk partition"
		    "table, TI_ATTR_FDISK_DISK_NAME is required but not "
		    "defined\n");

		return (IDM_E_FDISK_ATTR_INVALID);
	}

	/*
	 * obtain number of partitions to be created. This number may be
	 * greater than maximal number of primary partitions if logical
	 * volumes within extended partition are to be created
	 */

	if (nvlist_lookup_uint16(attrs, TI_ATTR_FDISK_PART_NUM, &part_num)
	    != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create fdisk partition "
		    "table, TI_ATTR_FDISK_PART_NUM is required but not "
		    "defined\n");

		return (IDM_E_FDISK_ATTR_INVALID);
	}

	idm_debug_print(LS_DBGLVL_INFO, "%d fdisk partitions will be created\n",
	    part_num);

	/*
	 * If optional attribute TI_ATTR_FDISK_PART_PRESERVE is provided
	 * it means that some of the partitions should be preserved
	 * exactly as they are for now - any changes shouldn't be done
	 * In this case, we need to read existing partition table and
	 * just copy data for partitions to be preserved.
	 */

	if (nvlist_lookup_boolean_array(attrs, TI_ATTR_FDISK_PART_PRESERVE,
	    &part_preserve, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_INFO,
		"TI_ATTR_FDISK_PART_PRESERVE is not defined\n");

		part_preserve = NULL;
	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_PRESERVE array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else {
		boolean_t	preserve_all = B_TRUE;

		for (i = 0; i < part_num; i++) {
			idm_debug_print(LS_DBGLVL_INFO,
			    "Partition %d %s be preserved\n", i + 1,
			    part_preserve[i] ? "will" : "won't");

			if (!part_preserve[i])
				preserve_all = B_FALSE;
		}

		/*
		 * If all partitions should be preserved, don't write
		 * new partition table at all
		 */

		if (preserve_all) {
			idm_debug_print(LS_DBGLVL_INFO,
			    "All partition will be preserved, partition table"
			    " won't be touched\n");

			return (IDM_E_SUCCESS);
		}
	}

	/*
	 * Obtain attributes describing partition table. If requried attributes
	 * are not available, return with error. Check if arrays contain right
	 * number of elements.
	 */

	/* partition IDs */

	if (nvlist_lookup_uint8_array(attrs, TI_ATTR_FDISK_PART_IDS,
	    &part_ids, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		"TI_ATTR_FDISK_PART_IDS is required but not defined\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_IDS array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/* partition active flags */

	if (nvlist_lookup_uint8_array(attrs, TI_ATTR_FDISK_PART_ACTIVE,
	    &part_active_flags, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		"TI_ATTR_FDISK_PART_ACTIVE is required but not defined\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_ACTIVE array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/* partition offset in sectors from beginning of the disk */

	if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_RSECTS,
	    &part_offsets, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		"TI_ATTR_FDISK_PART_RSECTS is required but not defined\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_RSECTS array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/* partition size in sectors  */

	if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_NUMSECTS,
	    &part_sizes, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		"TI_ATTR_FDISK_PART_NUMSECTS is required but not defined\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_NUMSECTS array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/*
	 * following attributes are optional - don't complain if they are not
	 * specified. On the other hand, they create group - it means that
	 * if at least one of attributes is defined, remaining must be defined
	 * as well.
	 * TODO: Check, if none or all attributes are provided, otherwise
	 * complain.
	 */

	/* partition start - head */

	if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_BHEADS,
	    &part_bheads, &nelem) != 0) {
		idm_debug_print(LS_DBGLVL_INFO,
		"TI_ATTR_FDISK_PART_BHEADS is not defined\n");

	} else if (nelem != part_num) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create part. table, "
		    "size of TI_ATTR_FDISK_PART_BHEADS array is invalid\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	} else {
		chs_geometry_provided = B_TRUE;

		/* partition start - sector */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_BSECTS,
		    &part_bsecs, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, TI_ATTR_FDISK_PART_BSECTS is required "
			    "but not defined\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		} else if (nelem != part_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, size of TI_ATTR_FDISK_PART_BSECTS array "
			    "is invalid\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		/* partition start - cylinder */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_BCYLS,
		    &part_bcyls, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, TI_ATTR_FDISK_PART_BCYLS is required "
			    "but not defined\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		} else if (nelem != part_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, size of TI_ATTR_FDISK_PART_BCYLS array "
			    "is invalid\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		/* partition end - head */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_EHEADS,
		    &part_eheads, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, TI_ATTR_FDISK_PART_EHEADS is required "
			    "but not defined\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		} else if (nelem != part_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, size of TI_ATTR_FDISK_PART_EHEADS array "
			    "is invalid\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		/* partition end - sector */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_ESECTS,
		    &part_esecs, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, TI_ATTR_FDISK_PART_ESECTS is required "
			    "but not defined\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		} else if (nelem != part_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, size of TI_ATTR_FDISK_PART_ESECTS array "
			    "is invalid\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		/* partition end - cylinder */

		if (nvlist_lookup_uint64_array(attrs, TI_ATTR_FDISK_PART_ECYLS,
		    &part_ecyls, &nelem) != 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, TI_ATTR_FDISK_PART_ECYLS is required "
			    "but not defined\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		} else if (nelem != part_num) {
			idm_debug_print(LS_DBGLVL_ERR, "Can't create part. "
			    "table, size of TI_ATTR_FDISK_PART_ECYLS array "
			    "is invalid\n");

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}
	}

	/*
	 * save all pointers in partition table structure for easier
	 * manipulation
	 */

	part_table = calloc(1, sizeof (idm_part_table_t));

	if (part_table == NULL) {
		idm_debug_print(LS_DBGLVL_ERR, "OOM :-(\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	part_table->id = part_ids;
	part_table->active = part_active_flags;
	part_table->offset = part_offsets;
	part_table->size = part_sizes;

	if (chs_geometry_provided) {
		part_table->bhead = part_bheads;
		part_table->bsect = part_bsecs;
		part_table->bcyl = part_bcyls;
		part_table->ehead = part_eheads;
		part_table->esect = part_esecs;
		part_table->ecyl = part_ecyls;
	} else {
		part_table->bhead = NULL;
		part_table->bsect = NULL;
		part_table->bcyl = NULL;
		part_table->ehead = NULL;
		part_table->esect = NULL;
		part_table->ecyl = NULL;
	}


	/*
	 * If there are partitions to be preserved, read original
	 * partition table and fill in geometry info for items
	 * which should remain unchanged
	 */

	if (part_preserve == NULL) {
		new_part_table = part_table;
	} else {
		/*
		 * allocate space for newly created partition table
		 * and copy original data there
		 */

		new_part_table = calloc(1, sizeof (idm_part_table_t));

		if (new_part_table == NULL) {
			idm_debug_print(LS_DBGLVL_ERR, "OOM :-(\n");
			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		new_part_table->id = calloc(part_num, sizeof (uint8_t));
		new_part_table->active = calloc(part_num, sizeof (uint8_t));
		new_part_table->offset = calloc(part_num, sizeof (uint64_t));
		new_part_table->size = calloc(part_num, sizeof (uint64_t));

		new_part_table->bhead = calloc(part_num, sizeof (uint64_t));
		new_part_table->bsect = calloc(part_num, sizeof (uint64_t));
		new_part_table->bcyl = calloc(part_num, sizeof (uint64_t));

		new_part_table->ehead = calloc(part_num, sizeof (uint64_t));
		new_part_table->esect = calloc(part_num, sizeof (uint64_t));
		new_part_table->ecyl = calloc(part_num, sizeof (uint64_t));

		if (new_part_table->id == NULL ||
		    new_part_table->active == NULL ||
		    new_part_table->offset == NULL ||
		    new_part_table->size == NULL ||
		    new_part_table->bhead == NULL ||
		    new_part_table->bsect == NULL ||
		    new_part_table->bcyl == NULL ||
		    new_part_table->ehead == NULL ||
		    new_part_table->esect == NULL ||
		    new_part_table->ecyl == NULL) {
			idm_debug_print(LS_DBGLVL_ERR, "OOM :-(\n");
			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}

		memcpy(new_part_table->id, part_table->id,
		    part_num * sizeof (uint8_t));
		memcpy(new_part_table->active, part_table->active,
		    part_num * sizeof (uint8_t));
		memcpy(new_part_table->offset, part_table->offset,
		    part_num * sizeof (uint64_t));
		memcpy(new_part_table->size, part_table->size,
		    part_num * sizeof (uint64_t));

		if (part_table->bhead != NULL) {
			memcpy(new_part_table->bhead, part_table->bhead,
			    part_num * sizeof (uint64_t));
			memcpy(new_part_table->bsect, part_table->bsect,
			    part_num * sizeof (uint64_t));
			memcpy(new_part_table->bcyl, part_table->bcyl,
			    part_num * sizeof (uint64_t));

			memcpy(new_part_table->ehead, part_table->ehead,
			    part_num * sizeof (uint64_t));
			memcpy(new_part_table->esect, part_table->esect,
			    part_num * sizeof (uint64_t));
			memcpy(new_part_table->ecyl, part_table->ecyl,
			    part_num * sizeof (uint64_t));
		}

		if (idm_fill_preserved_partitions(disk_name, new_part_table,
		    part_preserve, part_num) != IDM_E_SUCCESS) {
			idm_debug_print(LS_DBGLVL_ERR,
			    "Couldn't preserve partitions on disk %s - "
			    "fdisk failed\n", disk_name);

			return (IDM_E_FDISK_PART_TABLE_FAILED);
		}
	}

	/*
	 * print final fdisk partition table for debugging purposes
	 */

	idm_debug_print(LS_DBGLVL_INFO, "fdisk(1M) will create following "
	    "partition configuration on disk %s\n", disk_name);

	idm_debug_print(LS_DBGLVL_INFO,
	    "*   ID    bh    bs    bc    eh    es    ec     "
	    "offset       size\n");

	idm_debug_print(LS_DBGLVL_INFO,
	    "-----------------------------------------------"
	    "-----------------\n");

	for (i = 0; i < part_num; i++) {
		idm_debug_print(LS_DBGLVL_INFO,
		    "%2d%s %02X %5llu %5llu %5llu %5llu %5llu %5llu %10llu "
		    "%10llu\n",
		    i + 1, new_part_table->active[i] != 0 ? "+" : " ",
		    new_part_table->id[i],
		    new_part_table->bhead != NULL ?
		    new_part_table->bhead[i] : 0,
		    new_part_table->bsect != NULL ?
		    new_part_table->bsect[i] : 0,
		    new_part_table->bcyl != NULL ? new_part_table->bcyl[i] : 0,
		    new_part_table->ehead != NULL ?
		    new_part_table->ehead[i] : 0,
		    new_part_table->esect != NULL ?
		    new_part_table->esect[i] : 0,
		    new_part_table->ecyl != NULL ? new_part_table->ecyl[i] : 0,
		    new_part_table->offset[i], new_part_table->size[i]);
	}

	idm_debug_print(LS_DBGLVL_INFO,
	    "-----------------------------------------------"
	    "-----------------\n");

	/* if invoked in dry run mode, no changes done to the target */

	if (idm_dryrun_mode_fl) {
		idm_debug_print(LS_DBGLVL_INFO, "Running in dry run mode,"
		    "partition table won't be written to the disk\n");

		(void) sleep(1);

		return (IDM_E_SUCCESS);
	}

	/*
	 * create temporary file describing fdisk partition table configuration
	 * which will be passed to "fdisk(1M) -F <file>" command
	 */

	pt_file_name = mktemp(pt_file_template);

	idm_debug_print(LS_DBGLVL_INFO,
	    "Creating %s temporary file for holding partition configuration\n",
	    pt_file_name);

	pt_file = fopen(pt_file_name, "w");

	if (pt_file == NULL) {
		idm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't create file for holding partition "
		    "configuration\n");

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/*
	 * populate file with the partition table information
	 */

	(void) fprintf(pt_file,
	    "* Target Instantiation fdisk partition table\n"
	    "*\n"
	    "* Id\t Act\t Bhead\t Bsect\t Bcyl\t Ehead\t Esect\t Ecyl\t Rsect\t"
	    " Numsect\n");

	for (i = 0; i < part_num; i++) {
		(void) fprintf(pt_file,
		    " %d\t %d\t %llu\t %llu\t %llu\t %llu\t %llu\t %llu\t"
		    " %llu\t %llu\n", new_part_table->id[i],
		    new_part_table->active[i] != 0 ? 128 : 0,
		    new_part_table->bhead != NULL ?
		    new_part_table->bhead[i] : 0,
		    new_part_table->bsect != NULL ?
		    new_part_table->bsect[i] : 0,
		    new_part_table->bcyl != NULL ? new_part_table->bcyl[i] : 0,
		    new_part_table->ehead != NULL ?
		    new_part_table->ehead[i] : 0,
		    new_part_table->esect != NULL ?
		    new_part_table->esect[i] : 0,
		    new_part_table->ecyl != NULL ? new_part_table->ecyl[i] : 0,
		    new_part_table->offset[i], new_part_table->size[i]);
	}

	if (fclose(pt_file) != 0) {
		idm_debug_print(LS_DBGLVL_WARN,
		    "Couldn't close %s file\n", pt_file_name);
	}

	/*
	 * Provide fdisk(1M) with "-n" option in order to make it work
	 * in non-interactive mode. Otherwise it might hang the installer
	 * when waiting for user input.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/fdisk -n -F %s /dev/rdsk/%sp0",
	    pt_file_name, disk_name);

	idm_debug_print(LS_DBGLVL_INFO, "fdisk: "
	    "Creating fdisk partition table on disk %s:\n", disk_name);

	ret = idm_system(cmd);

	if (ret == -1) {
		idm_debug_print(LS_DBGLVL_ERR, "fdisk: "
		    "fdisk -n -F failed. Couldn't create fdisk "
		    "partition table on disk %s\n", disk_name);

		return (IDM_E_FDISK_PART_TABLE_FAILED);
	}

	/* Free previously allocated space */

	if (part_preserve != NULL) {
		free(new_part_table->id);
		free(new_part_table->active);
		free(new_part_table->offset);
		free(new_part_table->size);

		free(new_part_table->bhead);
		free(new_part_table->bsect);
		free(new_part_table->bcyl);

		free(new_part_table->ehead);
		free(new_part_table->esect);
		free(new_part_table->ecyl);

		free(new_part_table);
	}

	free(part_table);

	/*
	 * keep temporary file - if something went wrong during
	 * fdisk(1M) operation, file is kept for debugging
	 * purposes
	 */

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
	struct extvtoc	extvtoc;
	struct vtoc	vtoc;
	struct dk_geom	geom;
	char		device[MAXPATHLEN];
	char		*disk_name;
	int		fd;
	int		i;
	int		mtb_ret;
	uint16_t	slice_num;
	uint16_t	*slice_parts, *slice_tags;
	uint16_t	*slice_flags;
	uint64_t	*slice_1stsecs, *slice_sizes;
	uint_t		nelem;
	uint32_t	nsecs;
	boolean_t	fl_slice_def_layout = B_FALSE;
	boolean_t	create_swap_slice = B_FALSE;

	/* sanity check */

	assert(attrs != NULL);

	/*
	 * Obtain disk name. It can be provided by TI_ATTR_FDISK_DISK_NAME
	 * or TI_ATTR_SLICE_DISK_NAME attributes - prefered is
	 * TI_ATTR_SLICE_DISK_NAME.
	 * If not available, return with error
	 */

	if ((nvlist_lookup_string(attrs, TI_ATTR_SLICE_DISK_NAME, &disk_name)
	    != 0) && nvlist_lookup_string(attrs, TI_ATTR_FDISK_DISK_NAME,
	    &disk_name) != 0) {
		idm_debug_print(LS_DBGLVL_ERR, "Can't create VTOC, "
		    "TI_ATTR_[SLICE|FDISK]_DISK_NAME is required but not "
		    "defined\n");

		return (IDM_E_VTOC_FAILED);
	}

	/*
	 * look, if default layout is to be used. If this is the case, dedicate
	 * slice 1 to swap (if required) and remaining space on disk/Solaris2
	 * partition to slice 0
	 */

	if ((nvlist_lookup_boolean_value(attrs, TI_ATTR_SLICE_DEFAULT_LAYOUT,
	    &fl_slice_def_layout) == 0) && fl_slice_def_layout) {

		if (nvlist_lookup_boolean_value(attrs,
		    TI_ATTR_CREATE_SWAP_SLICE, &create_swap_slice) == 0 &&
		    create_swap_slice) {
			idm_debug_print(LS_DBGLVL_INFO, "vtoc: Default layout "
			    "required with a swap slice, s1 will be dedicated "
			    "to swap, s0 will occupy remaining space\n");

			slice_num = 2;
		} else {
			idm_debug_print(LS_DBGLVL_INFO, "vtoc: Default layout "
			    "required, slice 0 will occupy all disk/fdisk "
			    "partition\n");

			slice_num = 1;
		}
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

	/*
	 * Read original VTOC from target.
	 * Slices are recreated according to the attributes provided,
	 * rest of the information is preserved.
	 */

	if (read_extvtoc(fd, &extvtoc) < 0) {
		idm_debug_print(LS_DBGLVL_ERR, "vtoc: Couldn't read "
		    "existing VTOC from %s device\n", device);

		(void) close(fd);

		return (IDM_E_VTOC_FAILED);
	}

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "  Original VTOC configuration    \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &extvtoc);

	/*
	 * Clear slice information. Everything else is preserved.
	 */

	for (i = 0; i < extvtoc.v_nparts; i++) {
		extvtoc.v_part[i].p_start = 0;
		extvtoc.v_part[i].p_size = 0;
		extvtoc.v_part[i].p_tag = 0;
		extvtoc.v_part[i].p_flag = 0;
	}

	/* create slice 2 (ALL) - contains all available space */

	extvtoc.v_part[IDM_ALL_SLICE].p_tag = V_BACKUP;
	extvtoc.v_part[IDM_ALL_SLICE].p_flag = V_UNMNT;
	extvtoc.v_part[IDM_ALL_SLICE].p_start = 0;
	extvtoc.v_part[IDM_ALL_SLICE].p_size =
	    idm_cyls_to_secs(geom.dkg_ncyl, nsecs);

	/* create slice 8 (BOOT) - allocates 1st cylinder - only x86 */
#ifndef sparc
	extvtoc.v_part[IDM_BOOT_SLICE].p_tag = V_BOOT;
	extvtoc.v_part[IDM_BOOT_SLICE].p_flag = V_UNMNT;
	extvtoc.v_part[IDM_BOOT_SLICE].p_start = 0;
	extvtoc.v_part[IDM_BOOT_SLICE].p_size =
	    idm_cyls_to_secs(IDM_BOOT_SLICE_RES_CYL, nsecs);
#endif

	/*
	 * Modify original VTOC structure according to set of attributes.
	 */

	if (fl_slice_def_layout) {
		uint32_t	cyls_available = geom.dkg_ncyl
		    - IDM_BOOT_SLICE_RES_CYL;

		if (create_swap_slice) {
			uint32_t	cyls_swap = 0;

			cyls_swap = idm_calc_swap_size(&cyls_available, nsecs);

			if (cyls_swap != 0) {
				extvtoc.v_part[1].p_start = idm_cyls_to_secs(
				    IDM_BOOT_SLICE_RES_CYL, nsecs);

				idm_debug_print(LS_DBGLVL_INFO,
				    "%ld cyls were dedicated to swap slice\n",
				    cyls_swap);

				extvtoc.v_part[1].p_size =
				    idm_cyls_to_secs(cyls_swap, nsecs);

				extvtoc.v_part[1].p_tag = V_SWAP;
				extvtoc.v_part[1].p_flag = V_UNMNT;
			} else {
				idm_debug_print(LS_DBGLVL_WARN,
				    "Space for swap slice s1 not available\n");
			}
		}

		/*
		 * Slice 0 goes after slice 1, so that it can grow up if
		 * there is additional free space available.
		 */
		extvtoc.v_part[0].p_start = extvtoc.v_part[1].p_start +
		    extvtoc.v_part[1].p_size;

		extvtoc.v_part[0].p_size =
		    idm_cyls_to_secs(cyls_available, nsecs);

		extvtoc.v_part[0].p_tag = V_ROOT;
		extvtoc.v_part[0].p_flag = 0x00;
	} else {
		for (i = 0; i < slice_num; i++) {
			uint16_t	part_num;

			part_num = slice_parts[i];
			extvtoc.v_part[part_num].p_start = slice_1stsecs[i];
			extvtoc.v_part[part_num].p_size = slice_sizes[i];
			extvtoc.v_part[part_num].p_tag = slice_tags[i];
			extvtoc.v_part[part_num].p_flag = slice_flags[i];
		}
	}

	/* display modified VTOC structure */

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "      New VTOC configuration     \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &extvtoc);

	/*
	 * Adjust VTOC geometry part, so that slices start and end on
	 * cylinder boundary. Probably not necessary for x86 (done in
	 * kernel) but required for sparc.
	 */

	if (idm_adjust_vtoc(&extvtoc, nsecs) != IDM_E_SUCCESS) {
		idm_debug_print(LS_DBGLVL_ERR, "Adjusting VTOC failed\n");

		return (IDM_E_VTOC_FAILED);
	}

	/* display adjusted VTOC structure */

	idm_debug_print(LS_DBGLVL_INFO, "---------------------------------\n");
	idm_debug_print(LS_DBGLVL_INFO, "   Adjusted VTOC configuration   \n");

	idm_display_vtoc(LS_DBGLVL_INFO, &extvtoc);

	/*
	 * Do some kind of sanity check for newly created VTOC structure
	 * before it is finaly written to disk
	 */

	if (idm_check_vtoc(&extvtoc) != IDM_E_SUCCESS) {
		idm_debug_print(LS_DBGLVL_ERR, "Checking VTOC failed\n");

		return (IDM_E_VTOC_FAILED);
	}

	/* write out the VTOC (and label) */

	/* if invoked in dry run mode, no changes done to the target */

	if (idm_dryrun_mode_fl) {
		(void) sleep(1);

		(void) close(fd);
		return (IDM_E_SUCCESS);
	}

	/*
	 * XXXX Hack to get around write_extvtoc bug and devids
	 * To removed once CR 6769487 is resolved.
	 * If the size of the disk is greater than 1TB then call
	 * write_extvtoc, else call write_vtoc.
	 */

	mtb_ret = idm_is_mtb_disk(fd);
	if (mtb_ret == -1) {
		(void) close(fd);

		return (IDM_E_VTOC_FAILED);
	}

	if (mtb_ret == 0) {
		idm_debug_print(LS_DBGLVL_INFO, "Using VTOC call\n");
		convert_extvtoc_to_vtoc(&extvtoc, &vtoc);
		if (write_vtoc(fd, &vtoc) < 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Couldn't write "
			    "VTOC to %s device, write_vtoc() failed\n",
			    device);
			(void) close(fd);

			return (IDM_E_VTOC_FAILED);
		}

	} else {
		idm_debug_print(LS_DBGLVL_INFO, "Using EXTVTOC call\n");
		if (write_extvtoc(fd, &extvtoc) < 0) {
			idm_debug_print(LS_DBGLVL_ERR, "Couldn't write "
			    "VTOC to %s device, write_extvtoc() failed\n",
			    device);
			(void) close(fd);

			return (IDM_E_VTOC_FAILED);
		}
	}

	(void) close(fd);

	if (create_swap_slice) {
		idm_debug_print(LS_DBGLVL_INFO, "Adding /dev/dsk/%ss1 "
		    "as a swap device...\n", disk_name);

		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/swap -a /dev/dsk/%ss1", disk_name);

		ret = idm_system(cmd);

		if (ret == -1) {
			idm_debug_print(LS_DBGLVL_WARN,
			    "Couldn't add </dev/dsk/%ss1> as a swap device\n",
			    disk_name);
		}
	}

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
