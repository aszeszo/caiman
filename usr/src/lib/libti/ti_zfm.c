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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)ti_zfm.c	1.6	07/10/23 SMI"

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

#define	ZFM_ROOT_MOUNTPOINT	"/a"

#define	ZFM_GRUB_MENU_DIR	"boot/grub"

#define	ZFM_BE_CONTAINER_NAME	"ROOT"

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
zfm_system(const char *cmd)
{
	FILE *p;

	if ((p = popen(cmd, "w")) == NULL)
		return (-1);

	return (pclose(p));
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
	int		ret;

	char		*zfs_pool_name;
	char		*zfs_device;
	boolean_t	zfs_root_pool_fl = B_TRUE;

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
	 * display ZFS pool parameters for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO,
	    "zfs: ZFS pool <%s> will be created on slice <%s>\n", zfs_pool_name,
	    zfs_device);

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool create -f %s %s >/dev/null",
	    zfs_pool_name, zfs_device);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	/* if invoked in dry run mode, no changes done to the target */

	if (zfm_dryrun_mode_fl) {
		(void) sleep(5);
	} else {

		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create ZFS pool\n");

			return (ZFM_E_ZFS_POOL_CREATE_FAILED);
		}
	}

	/*
	 * For root pool, do more things right now:
	 * [1] create "boot/grub" directory in root dataset
	 * for holding menu.lst file.
	 */

	if (zfs_root_pool_fl) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/bin/mkdir -p /%s/%s >/dev/null",
		    zfs_pool_name, ZFM_GRUB_MENU_DIR);

		zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

		if (!zfm_dryrun_mode_fl) {
			ret = zfm_system(cmd);

			if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't create <%s> directory in root "
				    "dataset <%s>\n", ZFM_GRUB_MENU_DIR,
				    zfs_pool_name);

				return (ZFM_E_ZFS_POOL_CREATE_FAILED);
			}
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
	int		ret;

	char		**fs_names;
	char		**shared_fs_names;
	char		*zfs_pool_name;
	char		*zfs_be_name;
	uint_t		nelem;
	int		i;
	uint16_t	fs_num;
	uint16_t	shared_fs_num;

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

        if (nvlist_lookup_uint16(attrs, TI_ATTR_ZFS_SHARED_FS_NUM, &shared_fs_num)
	    != 0) {
                zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_SHARED_FS_NUM "
                    "attribute not provided, no datasets will be created\n");

                return (ZFM_E_SUCCESS);
        }

	if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_RPOOL_NAME, &zfs_pool_name)
	    != 0) {
		zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_RPOOL_NAME "
		    "attribute not provided, but required\n");

		return (ZFM_E_ZFS_FS_ATTR_INVALID);
	}

        if (nvlist_lookup_string(attrs, TI_ATTR_ZFS_BE_NAME, &zfs_be_name)
	    != 0) {
                zfm_debug_print(LS_DBGLVL_INFO, "TI_ATTR_ZFS_BE_NAME "
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

        if (nvlist_lookup_string_array(attrs, TI_ATTR_ZFS_SHARED_FS_NAMES,
	    &shared_fs_names, &nelem) != 0) {
                zfm_debug_print(LS_DBGLVL_ERR, "TI_ATTR_ZFS_SHARED_FS_NAMES "
                    "attribute not provided, but required\n");

                return (ZFM_E_ZFS_FS_ATTR_INVALID);
        }

	if (nelem != shared_fs_num) {
                zfm_debug_print(LS_DBGLVL_ERR, "Size of ZFS shared fs name array"
                    "doesn't match num of shared fs to be created\n");

                return (ZFM_E_ZFS_FS_ATTR_INVALID);
        }


	/*
	 * display fs to be created for debugging purposes
	 */

	zfm_debug_print(LS_DBGLVL_INFO, "ZFS fs to be created: \n");

	for (i = 0; i < fs_num; i++) {
		zfm_debug_print(LS_DBGLVL_INFO, " [%d] %s\n",
		    i + 1, fs_names[i]);
	}
	for (i = 0; i < shared_fs_num; i++) {
                zfm_debug_print(LS_DBGLVL_INFO, " [%d] %s\n",
                    i + 1, shared_fs_names[i]);
        }

	/* if invoked in dry run mode, no changes done to the target */


	/*
	 * create BE container dataset
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zfs create -o mountpoint=none %s/%s >/dev/null",
	    zfs_pool_name, ZFM_BE_CONTAINER_NAME);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create ZFS filesystem\n");

			return (ZFM_E_ZFS_FS_CREATE_FAILED);
		}
	}

	/*
	 * create root dataset for BE.
	 */

	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/zfs create -o "
	    "mountpoint=legacy %s/%s/%s >/dev/null", zfs_pool_name,
	    ZFM_BE_CONTAINER_NAME, zfs_be_name);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create ZFS filesystem\n");

			return (ZFM_E_ZFS_FS_CREATE_FAILED);
		}
	}

	/*
	 * Create /a mountpoint.
	 */

	(void) snprintf(cmd, sizeof (cmd), "/usr/bin/mkdir -p %s >/dev/null",
	    ZFM_ROOT_MOUNTPOINT);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't create %s directory\n");

			return (ZFM_E_ZFS_FS_CREATE_FAILED);
		}
	}

	zfm_debug_print(LS_DBGLVL_INFO, "zfs: "
	    "%s directory created\n", ZFM_ROOT_MOUNTPOINT);

	/*
	 * mount root fs explicitly, since its
	 * mountpoint property has been set to legacy
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/mount -F zfs %s/%s/%s %s >/dev/null",
	    zfs_pool_name, ZFM_BE_CONTAINER_NAME, zfs_be_name,
	    ZFM_ROOT_MOUNTPOINT);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't mount ZFS root "
			    "filesystem\n");

			return (ZFM_E_ZFS_FS_CREATE_FAILED);
		}
	}

	/*
	 * Set bootfs property for root pool. It can't be
	 * set before root filesystem is created.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool set bootfs=%s/%s/%s %s >/dev/null",
	    zfs_pool_name, ZFM_BE_CONTAINER_NAME, zfs_be_name,
	    zfs_pool_name);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (!zfm_dryrun_mode_fl) {
		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
			    "Couldn't set bootfs property to "
			    "<%s/%s/%s> for root pool <%s>\n",
			    zfs_pool_name, ZFM_BE_CONTAINER_NAME,
			    zfs_be_name, zfs_pool_name);

			return (ZFM_E_ZFS_POOL_CREATE_FAILED);
		}
	}

	/* create file systems under root */
        for (i = 0; i < fs_num; i++) {
		(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/zfs create "
		    "-o mountpoint=%s/%s %s/%s/%s/%s >/dev/null",
		    ZFM_ROOT_MOUNTPOINT, fs_names[i], zfs_pool_name,
		    ZFM_BE_CONTAINER_NAME, zfs_be_name, fs_names[i]);

		zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

		if (!zfm_dryrun_mode_fl) {
			ret = zfm_system(cmd);

			if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't create ZFS filesystem\n");

				return (ZFM_E_ZFS_FS_CREATE_FAILED);
			}
		}
	}

	/* create shared file systems */
        for (i = 0; i < shared_fs_num; i++) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs create -o mountpoint=%s/%s "
		    "%s/%s >/dev/null", ZFM_ROOT_MOUNTPOINT,
		    shared_fs_names[i], zfs_pool_name, shared_fs_names[i]);

		zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

		if (!zfm_dryrun_mode_fl) {
			ret = zfm_system(cmd);

			if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't create ZFS filesystem\n");

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
	int		ret;

	char		*zfs_pool_name;
	char		**vol_names;
	char		*swap_vol_name;
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
			    "/usr/sbin/zfs create -S %dmb %s >/dev/null",
			    vol_sizes[i], zfs_pool_name);
		} else
#endif
		{
			(void) snprintf(cmd, sizeof (cmd),
			    "/usr/sbin/zfs create -V %dmb %s/%s >/dev/null",
			    vol_sizes[i], zfs_pool_name, vol_names[i]);
		}

		zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

		if (!zfm_dryrun_mode_fl) {
			ret = zfm_system(cmd);

			if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
				zfm_debug_print(LS_DBGLVL_ERR, "zfs: "
				    "Couldn't create ZFS volume\n");

				return (ZFM_E_ZFS_VOL_CREATE_FAILED);
			}
		}
	}

	/*
	 * For now, dedicate the first ZFS volume for swap device.
	 * Add the volume to the swap area. We need name of ZFS root
	 * pool and name of ZFS volume (name defaults to "$swap").
	 * Dealing with swap device here is only temporary solution.
	 * This kind of tasks is to be handled in separate module.
	 */

#if 0

#ifdef ZFM_SWAP_VOL_SUPPORTED
	swap_vol_name = ZFM_SWAP_VOL_NAME;
#else
	swap_vol_name = vol_names[0];
#endif

	/*
	 * don't create swap on ZFS volume - this feature
	 * is not available for now, but it will be delivered
	 * soon.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/swap -a /dev/zvol/dsk/%s/%s >/dev/null",
	    zfs_pool_name, swap_vol_name);

	zfm_debug_print(LS_DBGLVL_INFO, "zfs cmd: %s\n", cmd);

	if (zfm_dryrun_mode_fl) {
		(void) sleep(1);
	} else {

		ret = zfm_system(cmd);

		if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {
			zfm_debug_print(LS_DBGLVL_WARN, "zfm: "
			    "Couldn't add zvol <%s> to swap space\n",
			    swap_vol_name);
		}
	}
#endif

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
