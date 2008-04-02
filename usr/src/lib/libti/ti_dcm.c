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
#include <libgen.h>
#include <stdarg.h>
#include <unistd.h>
#include <wait.h>
#include <errno.h>
#include <sys/param.h>
#include <sys/types.h>

#include <ti_dm.h>
#include <ti_zfm.h>
#include <ti_api.h>
#include <ls_api.h>

/* global variables */

/* local prototypes */
static int ramdisk_system(const char *, char *, size_t);

/* local constants */
#define	TIDC "TIDC"	/* module name for debug/log messages */

/* private variables */
static boolean_t dcm_dryrun_mode_fl = B_FALSE;

/* ------------------------ local functions --------------------------- */

/*
 * Function:	ramdisk_system()
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
ramdisk_system(const char *cmd, char *obuf, const size_t obufsize)
{
	FILE	*p;
	int	ret;

	ls_write_dbg_message(TIDC, LS_DBGLVL_INFO, "ramdisk cmd: %s\n", cmd);
	if (!dcm_dryrun_mode_fl) {
		if ((p = popen(cmd, "r")) == NULL)
			return (-1);
		if (fgets(obuf, obufsize, p) == NULL) {
			(void) pclose(p);
			return (-1);
		}
		obuf[strlen(obuf) - 1] = '\0';
		ls_write_dbg_message(TIDC, LS_DBGLVL_INFO,
		    "ramdisk cmd stdout: %s\n", obuf);
		if ((ret = pclose(p)) == -1 || WEXITSTATUS(ret) != 0)
			return (-1);
	}
	return (0);
}

/*
 * Function:	dcm_system()
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
dcm_system(char *cmd)
{
	FILE	*p;
	int	ret;
	char	errbuf[IDM_MAXCMDLEN];

	/* catch stderr for debugging purposes */
	if (strlcat(cmd, " 2>&1 1>/dev/null", IDM_MAXCMDLEN) >= IDM_MAXCMDLEN)
		ls_write_dbg_message(TIDC, LS_DBGLVL_WARN,
		    "dcm_system: Couldn't redirect stderr\n");
	ls_write_dbg_message(TIDC, LS_DBGLVL_INFO, "ramdisk cmd: %s\n", cmd);
	if (!dcm_dryrun_mode_fl) {
		if ((p = popen(cmd, "r")) == NULL)
			return (-1);
		while (fgets(errbuf, sizeof (errbuf), p) != NULL)
			ls_write_dbg_message(TIDC, LS_DBGLVL_WARN,
			    " dcm_system output:%s\n", errbuf);
		if (((ret = pclose(p)) == -1) || (WEXITSTATUS(ret) != 0))
			return (-1);
	}
	return (0);
}


/* ------------------------ public functions -------------------------- */

/*
 * Function:	ti_create_ramdisk
 * Attributes (all required):
 *	TI_TARGET_TYPE_DC_RAMDISK - indicates type of target to be created
 *	TI_ATTR_DC_RAMDISK_SIZE - ramdisk size in K
 *	TI_ATTR_DC_RAMDISK_BOOTARCH_NAME - name of boot archive
 *	TI_ATTR_DC_RAMDISK_DEST - ramdisk path
 */
ti_errno_t
ti_create_ramdisk(nvlist_t *attrs, ti_cbf_t cbf)
{
	uint32_t	ramdisk_size;	/* attr: desired size of ramdisk */
	char		*bootarch_name;	/* attr: name of boot archive */
	char		*ramdisk_path;	/* attr: path of boot archive */
	uint16_t	ramdisk_fstype;	/* attr: path of boot archive */
	char		cmd[IDM_MAXCMDLEN];	/* to hold shell command */
	char		pseudod[512];	/* newfs returns pseudodevice */
	int		ret = 0;	/* function return code */
	boolean_t	rollback_mkfile = B_FALSE;
	boolean_t	rollback_lofiadm = B_FALSE;
	boolean_t	rollback_mkdir = B_FALSE;

	if (nvlist_lookup_uint32(attrs, TI_ATTR_DC_RAMDISK_SIZE,
	    &ramdisk_size) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "RAM disk size not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	if (nvlist_lookup_string(attrs, TI_ATTR_DC_RAMDISK_BOOTARCH_NAME,
	    &bootarch_name) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Boot archive name not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	if (nvlist_lookup_string(attrs, TI_ATTR_DC_RAMDISK_DEST,
	    &ramdisk_path) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "RAM disk name not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	if (nvlist_lookup_uint16(attrs, TI_ATTR_DC_RAMDISK_FS_TYPE,
	    &ramdisk_fstype) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "RAM disk file system type not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	/* currently only fs type for ramdisk is UFS */
	if (ramdisk_fstype != TI_DC_RAMDISK_FS_TYPE_UFS) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "RAM disk file system type invalid\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	/* allocate ramdisk file space */
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/mkfile %dk %s",
	    ramdisk_size, bootarch_name);
	if (dcm_system(cmd) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't create ramdisk file cmd=<%s>\n", cmd);
		return (TI_E_RAMDISK_MKFILE_FAILED);
	}
	rollback_mkfile = B_TRUE;	/* rollback if subsequent cmd fails */
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/lofiadm -a %s",
	    bootarch_name);
	if (ramdisk_system(cmd, pseudod, sizeof (pseudod)) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't add file as block device. cmd=<%s>\n", cmd);
		return (TI_E_RAMDISK_LOFIADM_FAILED);
	}
	rollback_lofiadm = B_TRUE;	/* rollback if subsequent cmd fails */
	/* make file system on ramdisk */
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/newfs %s 0</dev/null",
	    pseudod);
	if (dcm_system(cmd) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't create newfs cmd=<%s>\n", cmd);
		ret = TI_E_NEWFS_FAILED;
		goto rollback;
	}
	/* make mountpoint for ramdisk */
	if (!dcm_dryrun_mode_fl && mkdirp(ramdisk_path, 0755) == -1 &&
	    errno != EEXIST) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't create directory <%s>\n", ramdisk_path);
		ret = TI_E_MKDIR_FAILED;
		goto rollback;
	}
	rollback_mkdir = B_TRUE;	/* rollback if subsequent cmd fails */
	/* mount ramdisk */
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/mount -o nologging %s %s",
	    pseudod, ramdisk_path);
	if (dcm_system(cmd) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't mount ramdisk cmd=<%s>\n", cmd);
		ret = TI_E_MOUNT_FAILED;
		goto rollback;
	}
	if (ret == 0)
		return (0);
rollback:	/* error state - roll back any previous steps */
	/* delete pseudodevice */
	if (rollback_lofiadm) {
		(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/lofiadm -d %s",
		    bootarch_name);
		(void) dcm_system(cmd);
	}
	/* delete directory */
	if (rollback_mkdir) {
		(void) snprintf(cmd, sizeof (cmd), "/usr/bin/rmdir %s",
		    ramdisk_path);
		(void) dcm_system(cmd);
	}
	/* delete file */
	if (rollback_mkfile) {
		(void) snprintf(cmd, sizeof (cmd), "/usr/bin/rm %s",
		    bootarch_name);
		(void) dcm_system(cmd);
	}
	return (ret);
}

ti_errno_t
ti_release_ramdisk(nvlist_t *attrs)
{
	char	cmd[IDM_MAXCMDLEN];	/* to hold shell command */
	char	*bootarch_name;
	char	*ramdisk_path;
	int	ret = TI_E_SUCCESS;

	if (nvlist_lookup_string(attrs, TI_ATTR_DC_RAMDISK_BOOTARCH_NAME,
	    &bootarch_name) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Boot archive name not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	if (nvlist_lookup_string(attrs, TI_ATTR_DC_RAMDISK_DEST,
	    &ramdisk_path) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "RAM disk name not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	/* unmount ramdisk */
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/umount %s",
	    ramdisk_path);
	if (dcm_system(cmd) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't unmount ramdisk for deletion-cmd=<%s>\n", cmd);
		ret = TI_E_UNMOUNT_FAILED;
	}
	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/lofiadm -d %s",
	    bootarch_name);
	if (dcm_system(cmd) == -1) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't lofiadm -d ramdisk cmd=<%s>\n", cmd);
		if (ret == TI_E_SUCCESS) /* other retvals take precedence */
			ret = TI_E_RAMDISK_LOFIADM_FAILED;
	}
	if (!dcm_dryrun_mode_fl && rmdir(ramdisk_path) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't remove directory %s errno=%d\n", ramdisk_path,
		    errno);
		if (ret == TI_E_SUCCESS) /* other retvals take precedence */
			ret = TI_E_RMDIR_FAILED;
	}
	return (ret);
}

ti_errno_t
ti_create_directory(nvlist_t *attrs, ti_cbf_t cbf)
{
	char *dirname;

	if (nvlist_lookup_string(attrs, TI_ATTR_DC_UFS_DEST, &dirname) != 0) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Directory name not provided\n");
		return (TI_E_INVALID_RAMDISK_ATTR);
	}
	/* make directory */
	if (mkdirp(dirname, 0755) == -1 && errno != EEXIST) {
		ls_write_dbg_message(TIDC, LS_DBGLVL_ERR,
		    "Couldn't create directory <%s>\n", dirname);
		return (TI_E_MKDIR_FAILED);
	}
	return (TI_E_SUCCESS);
}

/*
 * Function:	dcm_dryrun_mode
 * Description:	Makes TI DC module work in dry run mode.
 *		No changes done to the target.
 *
 * Scope:	public
 * Parameters:
 *
 * Return:
 */

void
dcm_dryrun_mode(void)
{
	dcm_dryrun_mode_fl = B_TRUE;
}
