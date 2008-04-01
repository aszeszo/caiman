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
#include <libnvpair.h>
#include <stdarg.h>
#include <unistd.h>
#include <sys/param.h>
#include <sys/types.h>

#include <ti_dm.h>
#include <ti_zfm.h>
#include <ti_api.h>
#include <ls_api.h>

/* global variables */

/* local constants */

/*
 * Percentage particular milestones take from total time.
 * Obviously, sum of values must always be 100.
 */
static int	ti_milestone_percentage[TI_MILESTONE_LAST] = {
	3,	/* TI_MILESTONE_FDISK */
	6,	/* TI_MILESTONE_VTOC */
	40,	/* TI_MILESTONE_ZFS_RPOOL */
	100	/* TI_MILESTONE_ZFS_FS */
};

/* private variables */

/* ------------------------ local functions --------------------------- */

/*
 * imm_debug_print()
 */
static void
imm_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("TIMM", dbg_lvl, buf);
	va_end(ap);
}


/*
 * Function:	ti_report_progress
 * Description:	Report progress by calling callback function. Progress
 *		is described as nv list of attributes and contains following
 *		information:
 *
 *		[1] Total number of milestones.
 *		[2] Current milestone in progress.
 *		[3] Percentage current milestone takes from total time.
 *		[4] Percentage done of current milestone.
 *
 *		New nvlist for storing attributes is always created. It is freed
 *		after return from callback.
 *
 * Scope:	private
 * Parameters:	ms_curr - current milestone
 *		ms_num - total number of milestones
 *		percentage - percetage done of current milestone
 *		cbf - pointer to callback function reporting progress
 *
 * Return:	TI_E_SUCCESS - progress report finished successfully
 *		TI_E_REP_FAILED - progress report failed
 */

static ti_errno_t
ti_report_progress(ti_milestone_t ms_curr, uint16_t ms_num,
    uint16_t percentage, ti_cbf_t cbf)
{
	nvlist_t *progress = NULL;

	/*
	 * If pointer to callback function is not set, there is nothing to do.
	 * Check is done here, so that it is not necessary to do it in caller
	 * every time progress is to be reported.
	 */

	if (cbf == NULL) {
		imm_debug_print(LS_DBGLVL_INFO,
		    "ti_report_progress: "
		    "No callback function, exit with success\n");

		return (TI_E_SUCCESS);
	}

	/*
	 * sanity check for current milestone. Done because later
	 * current milestone is used as index to array. We want
	 * to avoid bad access as soon as possible.
	 */

	if ((ms_curr < TI_MILESTONE_FDISK) || (ms_curr >= TI_MILESTONE_LAST)) {
		imm_debug_print(LS_DBGLVL_WARN,
		    "ti_report_progress: Invalid milestone %d passed\n",
		    ms_curr);

		return (TI_E_REP_FAILED);
	}

	if ((nvlist_alloc(&progress, NV_UNIQUE_NAME, 0) != 0) ||
	    (progress == NULL)) {
		imm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't create progress report nvlist\n");

		return (TI_E_REP_FAILED);
	}

	/* total # of milestones */

	if (nvlist_add_uint16(progress, TI_PROGRESS_MS_NUM,
	    ms_num) != 0) {
		imm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add TI_PROGRESS_MS_NUM to nvlist\n");

		return (TI_E_REP_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO,
		    "ti_report_progress(): "
		    "TI_PROGRESS_MS_NUM=%d added to nvlist\n",
		    TI_MILESTONE_LAST);
	}

	/* current milestone in progress */

	if (nvlist_add_uint16(progress, TI_PROGRESS_MS_CURR, ms_curr)
	    != 0) {
		imm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add TI_PROGRESS_MS_CURR to nvlist\n");

		return (TI_E_REP_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO,
		    "ti_report_progress(): "
		    "TI_PROGRESS_MS_CURR=%d added to nvlist\n",
		    ms_curr);
	}

	/* percentage current milestone takes from total time */

	if (nvlist_add_uint16(progress, TI_PROGRESS_MS_PERC,
	    ti_milestone_percentage[ms_curr - 1]) != 0) {
		imm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add TI_PROGRESS_MS_PERC to nvlist\n");

		return (TI_E_REP_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO,
		    "ti_report_progress(): "
		    "TI_PROGRESS_MS_PERC=%d added to nvlist\n",
		    ti_milestone_percentage[ms_curr - 1]);
	}

	/* percentage current milestone finished */

	if (nvlist_add_uint16(progress, TI_PROGRESS_MS_PERC_DONE,
	    percentage) != 0) {
		imm_debug_print(LS_DBGLVL_ERR,
		    "Couldn't add TI_PROGRESS_MS_PERC_DONE to nvlist\n");

		return (TI_E_REP_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO,
		    "ti_report_progress(): "
		    "TI_PROGRESS_MS_PERC_DONE=%d added to nvlist\n",
		    percentage);
	}

	/* nvlist is prepared for now, so invoke callback function */

	cbf(progress);

	/* release nvlist */

	nvlist_free(progress);

	return (TI_E_SUCCESS);
}


/*
 * Function:	imm_skip_disk_module
 * Description:	Inspects attribute list and makes decision, if there
 *		is any action targeted to Disk Module.
 *
 * Scope:	private
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	B_TRUE - Skip disk module
 *		B_FALSE - Disk module is supposed to be called
 */

boolean_t
imm_skip_disk_module(nvlist_t *attrs)
{
	char	*disk_name;

	/*
	 * If disk name is provided, it means for now that
	 * there is some action item for Disk module
	 */

	if (nvlist_lookup_string(attrs, TI_ATTR_FDISK_DISK_NAME, &disk_name)
	    == 0) {
		imm_debug_print(LS_DBGLVL_INFO,
		    "Disk module will be invoked\n");

		return (B_FALSE);
	} else {
		imm_debug_print(LS_DBGLVL_INFO,
		    "Disk module will be skipped\n");

		return (B_TRUE);
	}
}


/* ------------------------ public functions -------------------------- */

/*
 * Function:	ti_create_target
 * Description:	Creates target for installation according to set of attributes
 *		provided as nv list. If pointer to callback function is provided
 *		progress is reported via calling this callback function.
 *
 *		Currently, following steps are carried out:
 *
 *		[1] First, it is decided, if there are any Disk Module tasks.
 *		    If only ZFS module is to be utilized, Disk module is not
 *		    called at all.
 *		[2] If TI_ATTR_WDISK_FL is set, Solaris2 partition is created
 *		    on selected disk. Whole disk is used.
 *		[3] VTOC slice configuration is created within Solaris2
 *		    partition.  Two slices are created. One for ZFS root pool,
 *		    one for swap.
 *		[4] ZFS root pool is created on one of the slices.
 *		[5] ZFS filesystems are created within root pool according to
 *		    information provided.
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *		cbf - pointer to callback function reporting progress
 *
 * Return:	TI_E_SUCCESS - target created successfully
 *		TI_E_INVALID_FDISK_ATTR - fdisk attribute set invalid
 *		TI_E_FDISK_FAILED - fdisk failed
 *		TI_E_VTOC_FAILED - VTOC failed
 *		TI_E_ZFS_FAILED - creating ZFS structures failed
 */

ti_errno_t
ti_create_target(nvlist_t *attrs, ti_cbf_t cbf)
{
	char		*disk_name;
	boolean_t	wdisk_fl;
	uint16_t	ms_num;

	/* sanity check */
	assert(attrs != NULL);

	/*
	 * Decide, if there are any action items for Disk Module.
	 * If only ZFS module is to be involved, avoid calling
	 * Disk Module interfaces and reduce number of milestones
	 * to be reported.
	 */

	if (imm_skip_disk_module(attrs)) {
		ms_num = TI_MILESTONE_LAST - 3;
	} else {
		ms_num = TI_MILESTONE_LAST - 1;

		/*
		 * If there is no disk to work with, exit with error message for
		 * now. In future, this configuration would be relevant, if all
		 * fdisk structures were already created.
		 */
		if (nvlist_lookup_string(attrs, TI_ATTR_FDISK_DISK_NAME,
		    &disk_name) != 0) {
			imm_debug_print(LS_DBGLVL_ERR, "Disk name not "
			    "provided\n");

			return (TI_E_INVALID_FDISK_ATTR);
		} else
			imm_debug_print(LS_DBGLVL_INFO, "Target disk: %s\n",
			    disk_name);

		/*
		 * Before we can start with destructive changes to the target,
		 * make sure, nothing is mounted on disk partitions/slices.
		 * Unmount any mounted filesystems.
		 * If any of unmount operations fail, don't proceed with
		 * further modifications.
		 */

		if (idm_unmount_all(disk_name) != IDM_E_SUCCESS) {
			imm_debug_print(LS_DBGLVL_ERR, "Couldn't unmount "
			    "filesystems mounted on <%s> disk\n", disk_name);

			return (TI_E_UNMOUNT_FAILED);
		} else
			imm_debug_print(LS_DBGLVL_INFO, "All filesystems "
			    "mounted on disk <%s> were successfully "
			    "unmounted\n", disk_name);


		/*
		 * If required, create Solaris2 partition on whole disk.
		 */

		if ((nvlist_lookup_boolean_value(attrs, TI_ATTR_FDISK_WDISK_FL,
		    &wdisk_fl) == 0) && (wdisk_fl == B_TRUE)) {
			if (idm_fdisk_whole_disk(disk_name) != IDM_E_SUCCESS) {
				imm_debug_print(LS_DBGLVL_ERR, "Creating "
				    "Solaris2 partition on whole disk %s "
				    "failed\n", disk_name);

				return (TI_E_FDISK_FAILED);
			} else {
				imm_debug_print(LS_DBGLVL_INFO, "Creating "
				    "Solaris2 partition on whole disk <%s> "
				    "succeeded\n", disk_name);
			}
		}

		/* Milestone has been reached. Report progress */

		if (ti_report_progress(TI_MILESTONE_FDISK, ms_num, 100, cbf)
		    != TI_E_SUCCESS)
			imm_debug_print(LS_DBGLVL_WARN,
			    "Progress report failed\n");

		/*
		 * Create VTOC structure within exiting Solaris2 partition.
		 * Since only one Solaris2 partition is allowed within
		 * one disk, providing disk name is sufficient. This
		 * also allows to behave consistently accross x86 and
		 * sparc platforms.
		 * For now, complete set of attributes is passed to disk module.
		 * It will apply only those attributes describing VTOC structure
		 * to be created.
		 */

		if (idm_create_vtoc(attrs) != IDM_E_SUCCESS) {
			imm_debug_print(LS_DBGLVL_ERR, "Creating VTOC "
			    "structure on disk %s failed\n", disk_name);

			return (TI_E_VTOC_FAILED);
		} else {
			imm_debug_print(LS_DBGLVL_INFO, "Creating VTOC "
			    "structure on disk %s succeeded\n",
			    disk_name);
		}

		/* Milestone has been reached. Report progress */

		if (ti_report_progress(TI_MILESTONE_VTOC, ms_num, 100, cbf)
		    != TI_E_SUCCESS)
			imm_debug_print(LS_DBGLVL_WARN,
			    "Progress report failed\n");
	}


	/*
	 * Create ZFS root pool.
	 * For now, complete set of attributes is passed to ZFS module.
	 * It will apply only those attributes describing root pool
	 * to be created.
	 */

	if (zfm_create_pool(attrs) != ZFM_E_SUCCESS) {
		imm_debug_print(LS_DBGLVL_ERR, "Creating ZFS root pool "
		    "failed\n");

		return (TI_E_ZFS_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO, "Creating ZFS root pool "
		    "succeeded\n");
	}

	/* Milestone has been reached. Report progress */

	if (ti_report_progress(TI_MILESTONE_ZFS_RPOOL, ms_num, 100, cbf)
	    != TI_E_SUCCESS)
		imm_debug_print(LS_DBGLVL_WARN, "Progress report failed\n");

	/*
	 * Create ZFS filesystems.
	 * For now, complete set of attributes is passed to ZFS module.
	 * It will apply only those attributes describing ZFS filesystems
	 * to be created.
	 */

	if (zfm_create_fs(attrs) != ZFM_E_SUCCESS) {
		imm_debug_print(LS_DBGLVL_ERR, "Creating ZFS filesystems "
		    "failed\n");

		return (TI_E_ZFS_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO, "Creating ZFS filesystems "
		    "succeeded\n");
	}

	/*
	 * Create ZFS volumes.
	 * For now, complete set of attributes is passed to ZFS module.
	 * It will apply only those attributes describing ZFS volumes
	 * to be created.
	 */

	if (zfm_create_volumes(attrs) != ZFM_E_SUCCESS) {
		imm_debug_print(LS_DBGLVL_ERR, "Creating ZFS volumes "
		    "failed\n");

		return (TI_E_ZFS_FAILED);
	} else {
		imm_debug_print(LS_DBGLVL_INFO, "Creating ZFS volumes "
		    "succeeded\n");
	}

	/* Milestone has been reached. Report progress */

	if (ti_report_progress(TI_MILESTONE_ZFS_FS, ms_num, 100, cbf)
	    != TI_E_SUCCESS)
		imm_debug_print(LS_DBGLVL_WARN, "Progress report failed\n");

	return (TI_E_SUCCESS);
}


/*
 * Function:	ti_dryrun_mode
 * Description:	Makes TI work in dry run mode. No changes done to the target.
 *
 * Scope:	public
 * Parameters:
 *
 * Return:
 */

void
ti_dryrun_mode(void)
{
	idm_dryrun_mode();
	zfm_dryrun_mode();
}
