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
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <strings.h>
#include <wait.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/stat.h>

#include <ti_dm.h>
#include <ti_zfm.h>
#include <ti_api.h>
#include <ls_api.h>

/* global variables */

/* local constants */

#undef	ZFM_SWAP_VOL_SUPPORTED
#define	ZFM_SWAP_VOL_NAME	"$swap"

#define	ZFM_GRUB_MENU_DIR	"boot/grub"

/* private variables */

/* if set to B_TRUE, dry run mode is invoked, no changes done to the target */
static boolean_t	zfm_dryrun_mode_fl = B_FALSE;

/* ------------------------ private functions --------------------------- */

/*
 * zfm_debug_print()
 */
static void
zfm_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("TIZFM", dbg_lvl, buf);
	va_end(ap);
}


/*
 * Function:	zfm_system()
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
zfm_system(char *cmd)
{
	FILE	*p;
	int	ret;
	char	errbuf[IDM_MAXCMDLEN];

	/*
	 * catch stderr for debugging purposes
	 */

	if (strlcat(cmd, " 2>&1 1>/dev/null", IDM_MAXCMDLEN) >= IDM_MAXCMDLEN)
		zfm_debug_print(LS_DBGLVL_WARN,
		    "zfm_system: Couldn't redirect stderr\n");

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		if ((p = popen(cmd, "r")) == NULL)
			return (-1);

		while (fgets(errbuf, sizeof (errbuf), p) != NULL)
			zfm_debug_print(LS_DBGLVL_WARN, " stderr:%s", errbuf);

		ret = pclose(p);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0))
			return (-1);
	}

	return (0);
}


/*
 * Function:	zfm_zpool_exists()
 *
 * Description:	Finds out if ZFS pool already exists
 *
 * Scope:	private
 * Parameters:	zpool_name - ZFS pool name
 *
 * Return:	B_TRUE if pool exists, otherwise B_FALSE
 *
 */

static boolean_t
zfm_zpool_exists(char *zpool_name)
{
	FILE	*p;
	char	cmd[IDM_MAXCMDLEN];
	int	ret;

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool list %s >/dev/null 2>&1", zpool_name);

	if ((p = popen(cmd, "w")) == NULL)
		return (B_FALSE);

	ret = pclose(p);

	if ((ret != -1) && (WEXITSTATUS(ret) == 0))
		return (B_TRUE);
	else
		return (B_FALSE);
}

/*
 * Function:	zfm_dataset_exists()
 *
 * Description:	Finds out if ZFS dataset already exists
 *
 * Scope:	private
 * Parameters:	zpool_name - ZFS pool name
 *		dataset_name - ZFS dataset name
 *
 * Return:	B_TRUE if dataset exists, otherwise B_FALSE
 *
 */

static boolean_t
zfm_dataset_exists(char *zpool_name, char *dataset_name)
{
	FILE	*p;
	char	cmd[IDM_MAXCMDLEN];
	int	ret;

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zfs list %s/%s >/dev/null 2>&1", zpool_name,
	    dataset_name);

	if ((p = popen(cmd, "w")) == NULL)
		return (B_FALSE);

	ret = pclose(p);

	if ((ret != -1) && (WEXITSTATUS(ret) == 0))
		return (B_TRUE);
	else
		return (B_FALSE);
}


/* ----------------------- public functions --------------------------- */

/*
 * Function:	zfm_create_pool
 * Description:	Creates ZFS root/non-root pool according to set of attributes
 *		provided as nv list.
 *		Currently, only support for root pool is implemented
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	ZFM_E_SUCCESS - pool created successfully
 *		ZFM_E_ZFS_POOL_ATTR_INVALID - invalid set of attributes
 *		ZFM_E_ZFS_POOL_CREATE_FAILED - creating ZFS pool failed
 */

zfm_errno_t
zfm_create_pool(nvlist_t *attrs)
{
	char		cmd[IDM_MAXCMDLEN];

	char		*zfs_pool_name;
	char		*zfs_device;
	boolean_t	zfs_root_pool_fl = B_TRUE;
	boolean_t	zfs_preserve_pool_fl;

	/*
	 * validate set of attributes provided
	 * If root pool device is not provided, it is valid condition right now
	 * and means that no root pool will be created.
	 */

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_RPOOL_DEVICE, &zfs_device)
	    != 0) {
		zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_RPOOL_DEVICE "
		    "attribute not provided, no pool will be created\n");

		return (ZFM_E_SUCCESS);
	}

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_RPOOL_NAME, &zfs_pool_name)
	    != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_RPOOL_NAME "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_POOL_ATTR_INVALID);
	}

	/*
	 * if pool already exists, preserve it, if TI_ATTR_ZFS_RPOOL_PRESERVE
	 * is set to B_TRUE. Otherwise destroy it.
	 */

	if (nvlist_lookup_boolean_value(attrs, TI_ATTR_ZFS_RPOOL_PRESERVE,
	    &zfs_preserve_pool_fl) != 0) {
		zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_RPOOL_PRESERVE "
		    "attribute not provided, pool won't be preserved\n");

		zfs_preserve_pool_fl = B_FALSE;
	}

	if (zfm_zpool_exists(zfs_pool_name)) {
		if (zfs_preserve_pool_fl) {
			zfm_debug_print(LS_DBGLVL_INFO,
			    "pool <%s> already exists, will be preserved\n",
			    zfs_pool_name);

			return (ZFM_E_SUCCESS);
		} else {
			zfm_debug_print(LS_DBGLVL_WARN,
			    "root pool <%s> already exists, will be "
			    "destroyed\n", zfs_pool_name);

			(void) snprintf(cmd, sizeof (cmd),
			    "/usr/sbin/zpool destroy -f %s", zfs_pool_name);

			if (zfm_system(cmd) == -1) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't destroy ZFS pool\n");

				return (ZFM_E_ZFS_POOL_CREATE_FAILED);
			}
		}
	}

	/*
	 * display ZFS pool parameters for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO,
	    "zfs: ZFS pool <%s> will be created on slice <%s>\n",
	    zfs_pool_name, zfs_device);

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool create -f %s %s",
	    zfs_pool_name, zfs_device);

	if (zfm_system(cmd) == -1) {
		zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
		    "Couldn't create ZFS pool\n");

		return (ZFM_E_ZFS_POOL_CREATE_FAILED);
	}

	/*
	 * For root pool, do more things right now:
	 * [1] create "boot/grub" directory in root dataset
	 * for holding menu.lst file.
	 */

	if (zfs_root_pool_fl) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/bin/mkdir -p /%s/%s",
		    zfs_pool_name, ZFM_GRUB_MENU_DIR);

		if (zfm_system(cmd) == -1) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create <%s> directory in root "
			    "dataset <%s>\n", ZFM_GRUB_MENU_DIR,
			    zfs_pool_name);

			return (ZFM_E_ZFS_POOL_CREATE_FAILED);
		}
	}

	return (ZFM_E_SUCCESS);
}


/*
 * Function:	zfm_create_fs
 * Description:	Creates ZFS filesystems according to set of attributes
 *		provided as nv list.
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	ZFM_E_SUCCESS - filesystems created successfully
 *		ZFM_E_ZFS_FS_ATTR_INVALID - invalid set of attributes
 *		ZFM_E_ZFS_FS_CREATE_FAILED - can't create filesystem
 *		ZFM_E_ZFS_FS_SET_ATTR_FAILED - can't set filesystem attributes
 *
 */

zfm_errno_t
zfm_create_fs(nvlist_t *attrs)
{
	char		cmd[IDM_MAXCMDLEN];

	char		**fs_names;
	char		*zfs_pool_name;
	nvlist_t	**props;
	uint_t		nelem;
	int		i;
	uint16_t	fs_num;

	/*
	 * validate set of attributes provided
	 * If number of datasets to be created is not provided, it is valid
	 * condition right now and means that no datasets will be created.
	 */

	if (nvlist_lookup_uint16(attrs, TI_ATTR_ZFS_FS_NUM, &fs_num) != 0) {
		zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_FS_NUM "
		    "attribute not provided, no datasets will be created\n");

		return (ZFM_E_SUCCESS);
	}

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_FS_POOL_NAME,
	    &zfs_pool_name) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_FS_POOL_NAME "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_FS_ATTR_INVALID);
	}

	if (nvlist_lookup_string_array(attrs, TI_ATTR_ZFS_FS_NAMES, &fs_names,
	    &nelem) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_FS_NAMES "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_FS_ATTR_INVALID);
	}

	if (nelem != fs_num) {
		zfm_debug_print(LS_DBGLVL_ERR, "Size of ZFS fs name array"
		    "doesn't match num of fs to be created\n");

		return (ZFM_E_ZFS_FS_ATTR_INVALID);
	}

	/*
	 * read ZFS properties if they are provided
	 */

	if (nvlist_lookup_nvlist_array(attrs, TI_ATTR_ZFS_FS_PROPERTIES,
	    &props, &nelem) != 0) {
		props = NULL;
		zfm_debug_print(LS_DBGLVL_INFO,
		    "Properties not provided\n");
	}

	/*
	 * display fs to be created for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO, "ZFS fs to be created: \n");

	for (i = 0; i < fs_num; i++) {
		zfm_debug_print(LS_DBGLVL_INFO, " [%d] %s\n",
		    i + 1, fs_names[i]);
	}

	/* if invoked in dry run mode, no changes done to the target */

	/*
	 * create file systems and set properties
	 */

	for (i = 0; i < fs_num; i++) {
		char		**prop_names, **prop_values;
		uint_t		prop_numn, prop_numv;
		int		j;

		/*
		 * if dataset already exists, don't create it
		 */

		if (zfm_dataset_exists(zfs_pool_name, fs_names[i])) {
			zfm_debug_print(LS_DBGLVL_INFO,
			    "dataset <%s/%s> already exists, won't be created "
			    "again\n", zfs_pool_name, fs_names[i]);

			continue;
		}

		(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/zfs "
		    "create -p %s/%s", zfs_pool_name, fs_names[i]);

		if (zfm_system(cmd) == -1) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create ZFS filesystem\n");

			return (ZFM_E_ZFS_FS_CREATE_FAILED);
		}

		/*
		 * Set ZFS properties if provided
		 */

		if (props == NULL || props[i] == NULL ||
		    (nvlist_lookup_string_array(props[i],
		    TI_ATTR_ZFS_FS_PROP_NAMES, &prop_names, &prop_numn) != 0) ||
		    (nvlist_lookup_string_array(props[i],
		    TI_ATTR_ZFS_FS_PROP_VALUES, &prop_values, &prop_numv)
		    != 0)) {
			zfm_debug_print(LS_DBGLVL_INFO,
			    "Properties not provided for %s dataset\n",
			    fs_names[i]);

			continue;
		}

		for (j = 0; j < prop_numn; j++) {
			(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/zfs set "
			    "%s=%s %s/%s", prop_names[j],
			    prop_values[j], zfs_pool_name, fs_names[i]);

			zfm_debug_print(LS_DBGLVL_INFO,
			    "Property %s=%s is set for %s/%s\n", prop_names[j],
			    prop_values[j], zfs_pool_name, fs_names[i]);

			if (zfm_system(cmd) == -1) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't set ZFS property\n");

				return (ZFM_E_ZFS_FS_CREATE_FAILED);
			}
		}
	}

	if (zfm_dryrun_mode_fl) {
		(void) sleep(1);
	}

	return (ZFM_E_SUCCESS);
}


/*
 * Function:	zfm_fs_exists
 * Description:	Checks if ZFS filesystem exists
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	B_TRUE - ZFS dataset exists
 *		B_FALSE - ZFS dataset doesn't exist
 *
 */

boolean_t
zfm_fs_exists(nvlist_t *attrs)
{
	char		**fs_names;
	char		*zfs_pool_name;
	uint_t		nelem;
	uint16_t	fs_num;

	/*
	 * validate set of attributes provided
	 * Only one dataset can be checked at one time
	 */

	if (nvlist_lookup_uint16(attrs, TI_ATTR_ZFS_FS_NUM, &fs_num) != 0) {
		zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_FS_NUM "
		    "attribute not provided, no check will be done\n");

		return (B_FALSE);
	}

	if (fs_num != 1) {
		zfm_debug_print(LS_DBGLVL_WARN, "Only one dataset "
		    "can be checked at one time\n");

		return (B_FALSE);
	}

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_FS_POOL_NAME,
	    &zfs_pool_name) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_FS_POOL_NAME "
		    "attribute not provided, but required\n");

		return (B_FALSE);
	}

	if (nvlist_lookup_string_array(attrs, TI_ATTR_ZFS_FS_NAMES, &fs_names,
	    &nelem) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_FS_NAMES "
		    "attribute not provided, but required\n");

		return (B_FALSE);
	}

	if (nelem != fs_num) {
		zfm_debug_print(LS_DBGLVL_ERR, "Size of ZFS fs name array"
		    "doesn't match num of fs to be created\n");

		return (B_FALSE);
	}

	/*
	 * ignore ZFS properties for now
	 */

	/*
	 * display fs to be checked for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO, "ZFS fs to be checked: %s/%s\n",
	    zfs_pool_name, fs_names[0]);

	return (zfm_dataset_exists(zfs_pool_name, fs_names[0]));
}


/*
 * Function:	zfm_create_volumes
 * Description:	Creates ZFS volumes according to set of attributes
 *		provided as nv list.
 *		Currently, it also handles creating swap space on
 *		ZFS volume. It is only temporary solution, it needs
 *		to be moved to the separate module. It is assumed
 *		that the first volume is to be dedicated to the swap
 *
 * Scope:	public
 * Parameters:	attrs - set of attribtues describing the target
 *
 * Return:	ZFM_E_SUCCESS - filesystems created successfully
 *		ZFM_E_ZFS_VOL_ATTR_INVALID - invalid set of attributes
 *		ZFM_E_ZFS_VOL_CREATE_FAILED - can't create volume
 *		ZFM_E_ZFS_VOL_SET_ATTR_FAILED - can't set volume attributes
 *
 */

zfm_errno_t
zfm_create_volumes(nvlist_t *attrs)
{
	char		cmd[IDM_MAXCMDLEN];

	char		*zfs_pool_name;
	char		**vol_names;
	uint32_t	*vol_sizes;
	uint_t		nelem;
	int		i;
	uint16_t	vol_num;

	/*
	 * validate set of attributes provided
	 * If number of volumes to be created is not provided, it is valid
	 * condition right now and means that no volumes will be created.
	 */

	if (nvlist_lookup_uint16(attrs, TI_ATTR_ZFS_VOL_NUM, &vol_num) != 0) {
		zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_VOL_NUM "
		    "attribute not provided, no volumes will be created\n");

		return (ZFM_E_SUCCESS);
	}

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_RPOOL_NAME, &zfs_pool_name)
	    != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_RPOOL_NAME "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_VOL_ATTR_INVALID);
	}

	if (nvlist_lookup_string_array(attrs, TI_ATTR_ZFS_VOL_NAMES, &vol_names,
	    &nelem) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_VOL_NAMES "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_VOL_ATTR_INVALID);
	}

	if (nelem != vol_num) {
		zfm_debug_print(LS_DBGLVL_ERR, "Size of ZFS volume name array"
		    "doesn't match num of volumes to be created\n");

		return (ZFM_E_ZFS_VOL_ATTR_INVALID);
	}

	if (nvlist_lookup_uint32_array(attrs, TI_ATTR_ZFS_VOL_MB_SIZES,
	    &vol_sizes, &nelem) != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_VOL_MB_SIZES "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_VOL_ATTR_INVALID);
	}

	if (nelem != vol_num) {
		zfm_debug_print(LS_DBGLVL_ERR, "Size of ZFS volume size array"
		    "doesn't match num of volumes to be created\n");

		return (ZFM_E_ZFS_VOL_ATTR_INVALID);
	}

	/*
	 * display volumes to be created for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO, "ZFS volumes to be created: \n");

	for (i = 0; i < vol_num; i++) {
		zfm_debug_print(LS_DBGLVL_INFO, " [%d] %s, size=%d MB\n",
		    i + 1, vol_names[i], vol_sizes[i]);
	}

	for (i = 0; i < vol_num; i++) {

		/*
		 * create ZFS volumes.
		 */

		/*
		 * If this is the first one, treat it temporarily to be used
		 * as swap device. ZFS uses dedicated "$swap" name for such
		 * type of volume.
		 * It is assumed that in next release there would be
		 * attributes further describing the ZFS volume to be
		 * created.
		 */

#ifdef ZFM_SWAP_VOL_SUPPORTED
		if (i == 0) {
			(void) snprintf(cmd, sizeof (cmd),
			    "/usr/sbin/zfs create -S %dmb %s",
			    vol_sizes[i], zfs_pool_name);
		} else
#endif
		{
			(void) snprintf(cmd, sizeof (cmd),
			    "/usr/sbin/zfs create -V %dmb %s/%s",
			    vol_sizes[i], zfs_pool_name, vol_names[i]);
		}

		if (zfm_system(cmd) == -1) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create ZFS volume\n");

			return (ZFM_E_ZFS_VOL_CREATE_FAILED);
		}
	}

	/*
	 * For now, dedicate the first ZFS volume for swap device.
	 * Add the volume to the swap area. We need name of ZFS root
	 * pool and name of ZFS volume (name defaults to "$swap").
	 * Dealing with swap device here is only temporary solution.
	 * This kind of tasks is to be handled in separate module.
	 */

	/*
	 * don't create swap on ZFS volume - this feature
	 * is not available for now, but it will be delivered
	 * soon.
	 */

	return (ZFM_E_SUCCESS);
}


/*
 * Function:	zfm_dryrun_mode
 * Description:	Makes TI ZFS module work in dry run mode.
 *		No changes done to the target.
 *
 * Scope:	public
 * Parameters:
 *
 * Return:
 */

void
zfm_dryrun_mode(void)
{
	zfm_dryrun_mode_fl = B_TRUE;
}
