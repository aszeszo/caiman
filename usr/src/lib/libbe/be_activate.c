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
#include <libintl.h>
#include <libnvpair.h>
#include <libzfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/mnttab.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include "libbe.h"
#include "libbe_priv.h"

char	*mnttab = MNTTAB;

/*
 * Private function prototypes
 */
static int set_bootfs(char *boot_rpool, char *be_root_ds);
static int set_canmount(be_node_list_t *, char *);
static int be_do_installgrub(be_transaction_data_t *);
static int be_get_grub_vers(be_transaction_data_t *, char **, char **);
static int get_ver_from_capfile(char *, char **);

/* ******************************************************************** */
/*			Public Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_activate
 * Description:	Calls _be_activate which activates the BE named in the
 *		attributes passed in through be_attrs. The process of
 *		activation sets the bootfs property of the root pool, resets
 *		the canmount property to noauto, and sets the default in the
 *		grub menu to the entry corresponding to the entry for the named
 *		BE.
 * Parameters:
 *		be_attrs - pointer to nvlist_t of attributes being passed in.
 *			The follow attribute values are used by this function:
 *
 *			BE_ATTR_ORIG_BE_NAME		*required
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Public
 */
int
be_activate(nvlist_t *be_attrs)
{
	int	ret = 0;
	char	*be_name = NULL;

	/* Initialize libzfs handle */
	if (!be_zfs_init())
		return (BE_ERR_INIT);

	/* Get the BE name to activate */
	if (nvlist_lookup_string(be_attrs, BE_ATTR_ORIG_BE_NAME, &be_name)
	    != 0) {
		be_print_err(gettext("be_activate: failed to "
		    "lookup BE_ATTR_ORIG_BE_NAME attribute\n"));
		be_zfs_fini();
		return (BE_ERR_INVAL);
	}

	/* Validate BE name */
	if (!be_valid_be_name(be_name)) {
		be_print_err(gettext("be_activate: invalid BE name %s\n"),
		    be_name);
		return (BE_ERR_INVAL);
	}

	ret = _be_activate(be_name);

	be_zfs_fini();

	return (ret);
}

/* ******************************************************************** */
/*			Semi Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	_be_activate
 * Description:	This does the actual work described in be_activate.
 * Parameters:
 *		be_name - pointer to the name of BE to activate.
 *
 * Return:
 *		0 - Success
 *		be_errnot_t - Failure
 * Scope:
 *		Public
 */
int
_be_activate(char *be_name)
{
	be_transaction_data_t cb = { 0 };
	char		root_ds[MAXPATHLEN];
	char		*cur_vers = NULL, *new_vers = NULL;
	be_node_list_t	*be_nodes;
	int		ret, entry, err = 0;

	/*
	 * TODO: The BE needs to be validated to make sure that it is actually
	 * a bootable BE.
	 */

	if (be_name == NULL)
		return (BE_ERR_INVAL);

	/* Set obe_name to be_name in the cb structure */
	cb.obe_name = be_name;

	/* find which zpool the be is in */
	if ((ret = zpool_iter(g_zfs, be_find_zpool_callback, &cb)) == 0) {
		be_print_err(gettext("be_activate: failed to "
		    "find zpool for BE (%s)\n"), cb.obe_name);
		be_zfs_fini();
		return (BE_ERR_BE_NOENT);
	} else if (ret < 0) {
		be_print_err(gettext("be_activate: "
		    "zpool_iter failed: %s\n"),
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		be_zfs_fini();
		return (err);
	}

	be_make_root_ds(cb.obe_zpool, cb.obe_name, root_ds, sizeof (root_ds));
	cb.obe_root_ds = strdup(root_ds);

	if ((err = be_get_grub_vers(&cb, &cur_vers, &new_vers)) != 0) {
		be_print_err(gettext("be_activate: failed to get grub "
		    "versions from capability files.\n"));
		return (err);
	}
	if (cur_vers != NULL) {
		/*
		 * We need to check to see if the version number from the
		 * BE being activated is greater than the current one.
		 */
		if (new_vers != NULL &&
		    atof(cur_vers) < atof(new_vers)) {
			err = be_do_installgrub(&cb);
			if (err) {
				be_zfs_fini();
				free(new_vers);
				free(cur_vers);
				return (err);
			}
			free(new_vers);
		}
		free(cur_vers);
	} else if (new_vers != NULL) {
		err = be_do_installgrub(&cb);
		if (err) {
			be_zfs_fini();
			free(new_vers);
			return (err);
		}
		free(new_vers);
	}

	err = _be_list(cb.obe_name, &be_nodes);
	if (err) {
		be_zfs_fini();
		return (err);
	}

	err = set_canmount(be_nodes, "noauto");
	if (err) {
		be_print_err(gettext("be_activate: failed to set "
		    "canmount dataset property\n"));
		goto done;
	}

	if (!be_has_grub_entry(root_ds, cb.obe_zpool, &entry)) {
		if ((err = be_append_grub(cb.obe_name, cb.obe_zpool, NULL,
		    NULL)) != 0) {
			be_print_err(gettext("be_activate: Failed to add "
			    "BE (%s) to the GRUB menu\n"), cb.obe_name);
			goto done;
		}
	}

	err = set_bootfs(be_nodes->be_rpool, root_ds);
	if (err) {
		be_print_err(gettext("be_activate: failed to set "
		    "bootfs pool property for %s\n"), root_ds);
		goto done;
	}

	err = be_change_grub_default(cb.obe_name, be_nodes->be_rpool);
	if (err) {
		be_print_err(gettext("be_activate: failed to change "
		    "the default entry in menu.lst\n"));
	}

done:
	be_free_list(be_nodes);
	return (err);
}

/*
 * Function:	be_activate_current_be
 * Description:	Set the currently "active" BE to be "active on boot"
 * Paramters:
 *		none
 * Returns:
 *		0 - Success
 *		be_errnot_t - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
be_activate_current_be(void)
{
	int err = 0;
	be_transaction_data_t bt = { 0 };

	if ((err = be_find_current_be(&bt)) != BE_SUCCESS) {
		return (err);
	}

	if ((err = _be_activate(bt.obe_name)) != BE_SUCCESS) {
		be_print_err(gettext("be_activate_current_be: failed to "
		    "activate %s\n"), bt.obe_name);
		return (err);
	}

	return (BE_SUCCESS);
}

/*
 * Function:	be_is_active_on_boot
 * Description:	Checks if the BE name passed in has the "active on boot"
 *		property set to B_TRUE.
 * Paramters:
 *		be_name - the name of the BE to check
 * Returns:
 *		B_TRUE - if active on boot.
 *		B_FALSE - if not active on boot.
 * Scope:
 *		Semi-private (library wide use only)
 */
boolean_t
be_is_active_on_boot(char *be_name)
{
	be_node_list_t *be_node = NULL;

	if (be_name == NULL) {
		be_print_err(gettext("be_is_active_on_boot: "
		    "be_name must not be NULL\n"));
		return (B_FALSE);
	}

	if (_be_list(be_name, &be_node) != 0) {
		return (B_FALSE);
	}

	if (be_node == NULL) {
		return (B_FALSE);
	}

	if (be_node->be_active_on_boot) {
		be_free_list(be_node);
		return (B_TRUE);
	} else {
		be_free_list(be_node);
		return (B_FALSE);
	}
}

/* ******************************************************************** */
/*			Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	set_bootfs
 * Description:	Sets the bootfs property on the boot pool to be the
 *		root dataset of the activated BE.
 * Parameters:
 *		boot_pool - The pool we're setting bootfs in.
 *		be_root_ds - The main dataset for the BE.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
set_bootfs(char *boot_rpool, char *be_root_ds)
{
	zpool_handle_t *zhp;
	int err = 0;

	if ((zhp = zpool_open(g_zfs, boot_rpool)) == NULL) {
		be_print_err(gettext("set_bootfs: failed to open pool "
		    "(%s): %s\n"), boot_rpool, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		return (err);
	}

	err = zpool_set_prop(zhp, "bootfs", be_root_ds);
	if (err) {
		be_print_err(gettext("set_bootfs: failed to set "
		    "bootfs property for pool %s: %s\n"), boot_rpool,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		zpool_close(zhp);
		return (err);
	}

	zpool_close(zhp);
	return (BE_SUCCESS);
}

/*
 * Function:	set_canmount
 * Description:	Sets the canmount property on the datasets of the
 *		activated BE.
 * Parameters:
 *		be_nodes - The be_node_t returned from be_list
 *		value - The value of canmount we setting, on|off|noauto.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
set_canmount(be_node_list_t *be_nodes, char *value)
{
	char		ds_path[MAXPATHLEN];
	char		prop_buf[BUFSIZ];
	zfs_handle_t	*zhp = NULL;
	be_node_list_t	*list = be_nodes;
	int		err = 0;

	while (list != NULL) {
		be_dataset_list_t *datasets = list->be_node_datasets;

		be_make_root_ds(list->be_rpool, list->be_node_name, ds_path,
		    sizeof (ds_path));

		if ((zhp = zfs_open(g_zfs, ds_path, ZFS_TYPE_DATASET)) ==
		    NULL) {
			be_print_err(gettext("set_canmount: failed to open "
			    "dataset (%s): %s\n"), ds_path,
			    libzfs_error_description(g_zfs));
			err = zfs_err_to_be_err(g_zfs);
			return (err);
		}
		while (zfs_promote(zhp) == 0) {
			ZFS_CLOSE(zhp);
			if ((zhp = zfs_open(g_zfs, ds_path,
			    ZFS_TYPE_DATASET)) == NULL) {
				be_print_err(gettext("set_canmount: failed to "
				    "open dataset (%s): %s\n"), ds_path,
				    libzfs_error_description(g_zfs));
				err = zfs_err_to_be_err(g_zfs);
				return (err);
			}
		}
		if (zfs_prop_get(zhp, ZFS_PROP_ORIGIN, prop_buf,
		    sizeof (prop_buf), NULL, NULL, 0, B_FALSE) != 0) {
			strlcpy(prop_buf, "-", sizeof (prop_buf));
		}
		if (strcmp(prop_buf, "-") != 0) {
			ZFS_CLOSE(zhp);
			be_print_err(gettext("set_canmount: failed to "
			    "promote dataset (%s)\n"), ds_path);
			return (BE_ERR_PROMOTE);
		}
		if (zfs_prop_get_int(zhp, ZFS_PROP_MOUNTED)) {
			/*
			 * it's already mounted so we can't change the
			 * canmount property anyway.
			 */
			err = 0;
		} else {
			err = zfs_prop_set(zhp,
			    zfs_prop_to_name(ZFS_PROP_CANMOUNT), value);
			if (err) {
				ZFS_CLOSE(zhp);
				be_print_err(gettext("set_canmount: failed to "
				    "set dataset property (%s): %s\n"),
				    ds_path, libzfs_error_description(g_zfs));
				err = zfs_err_to_be_err(g_zfs);
				return (err);
			}
		}
		ZFS_CLOSE(zhp);

		while (datasets != NULL) {
			be_make_root_ds(list->be_rpool,
			    datasets->be_dataset_name, ds_path,
			    sizeof (ds_path));

			if ((zhp = zfs_open(g_zfs, ds_path, ZFS_TYPE_DATASET))
			    == NULL) {
				be_print_err(gettext("set_canmount: failed to "
				    "open dataset %s: %s\n"), ds_path,
				    libzfs_error_description(g_zfs));
				err = zfs_err_to_be_err(g_zfs);
				return (err);
			}
			while (zfs_promote(zhp) == 0) {
				ZFS_CLOSE(zhp);
				if ((zhp = zfs_open(g_zfs, ds_path,
				    ZFS_TYPE_DATASET)) == NULL) {
					be_print_err(gettext("set_canmount: "
					    "Failed to open dataset "
					    "(%s): %s\n"), ds_path,
					    libzfs_error_description(g_zfs));
					err = zfs_err_to_be_err(g_zfs);
					return (err);
				}
			}
			if (zfs_prop_get(zhp, ZFS_PROP_ORIGIN, prop_buf,
			    sizeof (prop_buf), NULL, NULL, 0, B_FALSE) != 0) {
				strlcpy(prop_buf, "-", sizeof (prop_buf));
			}
			if (strcmp(prop_buf, "-") != 0) {
				ZFS_CLOSE(zhp);
				be_print_err(gettext("set_canmount: "
				    "Failed to promote the dataset (%s)\n"),
				    ds_path);
				return (BE_ERR_PROMOTE);
			}
			if (zfs_prop_get_int(zhp, ZFS_PROP_MOUNTED)) {
				/*
				 * it's already mounted so we can't change the
				 * canmount property anyway.
				 */
				err = 0;
				ZFS_CLOSE(zhp);
				break;
			}
			err = zfs_prop_set(zhp,
			    zfs_prop_to_name(ZFS_PROP_CANMOUNT), value);
			if (err) {
				ZFS_CLOSE(zhp);
				be_print_err(gettext("set_canmount: "
				    "Failed to set property value %s "
				    "for dataset %s: %s\n"), value, ds_path,
				    libzfs_error_description(g_zfs));
				err = zfs_err_to_be_err(g_zfs);
				return (err);
			}
			ZFS_CLOSE(zhp);
			datasets = datasets->be_next_dataset;
		}
		list = list->be_next_node;
	}
	return (err);
}

/*
 * Function:	be_get_grub_vers
 * Description:	Gets the grub version number from /boot/grub/capability. If
 *              capability file doesn't exist NULL is returned.
 * Parameters:
 *              bt - The transaction data for the BE we're getting the grub
 *                   version for.
 *              cur_vers - used to return the current version of grub from
 *                         the root pool.
 *              new_vers - used to return the grub version of the BE we're
 *                         activating.
 * Return:
 *              0 - Success
 *              be_errno_t - Failed to find version
 * Scope:
 *		Private
 */
static int
be_get_grub_vers(be_transaction_data_t *bt, char **cur_vers, char **new_vers)
{
	zfs_handle_t	*zhp;
	int err = 0;
	char cap_file[MAXPATHLEN];
	char *temp_mntpnt;
	char *zpool_mntpt;
	boolean_t be_mounted = B_FALSE;


	if (bt == NULL || bt->obe_name == NULL || bt->obe_zpool == NULL ||
	    bt->obe_root_ds == NULL) {
		be_print_err(gettext("get_grub_vers: Invalid BE\n"));
		return (BE_ERR_INVAL);
	}

	if ((zhp = zfs_open(g_zfs, bt->obe_zpool, ZFS_TYPE_FILESYSTEM)) ==
	    NULL) {
		be_print_err(gettext("get_grub_vers: zfs_open failed: %s\n"),
		    libzfs_error_description(g_zfs));
		return (zfs_err_to_be_err(g_zfs));
	}
	if (!zfs_is_mounted(zhp, &zpool_mntpt)) {
		be_print_err(gettext("get_grub_vers: root pool is not "
		    "mounted, can not access root grub directory\n"),
		    bt->obe_zpool);
		ZFS_CLOSE(zhp);
		return (BE_ERR_NOTMOUNTED);
	} else {
		/*
		 * get the version of the most recent grub update.
		 */
		(void) snprintf(cap_file, sizeof (cap_file), "/%s%s",
		    zpool_mntpt, BE_CAP_FILE);
		free(zpool_mntpt);
		ZFS_CLOSE(zhp);
		err = get_ver_from_capfile(cap_file, cur_vers);
		if (err != 0)
			return (err);
	}

	if ((zhp = zfs_open(g_zfs, bt->obe_root_ds, ZFS_TYPE_FILESYSTEM)) ==
	    NULL) {
		be_print_err(gettext("get_grub_vers: failed to "
		    "open BE root dataset (%s): %s\n"), bt->obe_root_ds,
		    libzfs_error_description(g_zfs));
		free(cur_vers);
		return (zfs_err_to_be_err(g_zfs));
	}
	if (!zfs_is_mounted(zhp, &temp_mntpnt)) {
		err = _be_mount(bt->obe_name, &temp_mntpnt, 0);
		if (err) {
			be_print_err(gettext("get_grub_vers: failed to "
			    "mount BE (%s)\n"), bt->obe_name);
			free(*cur_vers);
			*cur_vers = NULL;
			ZFS_CLOSE(zhp);
			return (NULL);
		}
		be_mounted = B_TRUE;
	}
	ZFS_CLOSE(zhp);

	/*
	 * Now get the grub version for the BE being activated.
	 */
	(void) snprintf(cap_file, sizeof (cap_file), "%s%s", temp_mntpnt,
	    BE_CAP_FILE);
	err = get_ver_from_capfile(cap_file, new_vers);
	if (err != 0) {
		free(*cur_vers);
		*cur_vers = NULL;
	}
	if (be_mounted)
		(void) _be_unmount(bt->obe_name, 0);
	free(temp_mntpnt);
	return (err);
}

/*
 * Function:	get_ver_from_capfile
 * Description: Parses the capability file passed in looking for the VERSION
 *              line. If found the version is returned in vers, if not then
 *              NULL is returned in vers.
 *
 * Parameters:
 *              file - the path to the capability file we want to parse.
 *              vers - the version string that will be passed back.
 * Return:
 *              0 - Success
 *              be_errno_t - Failed to find version
 * Scope:
 *		Private
 */
static int
get_ver_from_capfile(char *file, char **vers)
{
	FILE *fp = NULL;
	char line[BUFSIZ];
	char *last;
	uint_t err = 0;

	errno = 0;
	fp = fopen(file, "r");
	err = errno;

	if (err == 0 && fp != NULL) {
		while (fgets(line, BUFSIZ, fp)) {
			char *tok = strtok_r(line, "=", &last);

			if (tok == NULL || tok[0] == '#') {
				continue;
			} else if (strcmp(tok, "VERSION") == 0) {
				fclose(fp);
				*vers = strdup(last);
				return (BE_SUCCESS);
			}
		}
		fclose(fp);
		fp = NULL;
	} else if (err == ENOENT) {
		/*
		 * If capability file doesn't exist, set the version to NULL,
		 * but return success.
		 * This is correct because it is valid in older releases for
		 * the capability file to be missing.
		 */
		*vers = NULL;
		return (BE_SUCCESS);
	} else {
		be_print_err(gettext("get_ver_from_capfile: failed to open "
		    "file %s with err %s\n"), file, strerror(err));
		err = errno_to_be_err(err);
		if (fp != NULL)
			fclose(fp);
	}
	*vers = NULL;
	return (err);
}

/*
 * Function:	be_do_installgrub
 * Description:	This function runs installgrub using the grub loader files
 *              from the BE we're activating and installing them on the
 *              pool the BE lives in.
 *
 * Parameters:
 *              bt - The transaction data for the BE we're activating.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 *
 * Scope:
 *		Private
 */
static int
be_do_installgrub(be_transaction_data_t *bt)
{
	zpool_handle_t  *zphp;
	zfs_handle_t	*zhp;
	nvlist_t **child, *nv, *config;
	uint_t c, children = 0;
	char *tmp_mntpt = NULL;
	FILE *cap_fp = NULL;
	FILE *zpool_cap_fp = NULL;
	char line[BUFSIZ];
	char cap_file[MAXPATHLEN];
	char zpool_cap_file[MAXPATHLEN];
	char stage1[MAXPATHLEN];
	char stage2[MAXPATHLEN];
	char installgrub_cmd[MAXPATHLEN];
	char *vname;
	int err = 0;
	boolean_t be_mounted = B_FALSE;

	if ((zhp = zfs_open(g_zfs, bt->obe_root_ds, ZFS_TYPE_FILESYSTEM)) ==
	    NULL) {
		be_print_err(gettext("get_grub_vers: failed to "
		    "open BE root dataset (%s): %s\n"), bt->obe_root_ds,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		return (err);
	}
	if (!zfs_is_mounted(zhp, &tmp_mntpt)) {
		if (_be_mount(bt->obe_name, &tmp_mntpt, 0) != 0) {
			be_print_err(gettext("be_do_installgrub: failed to "
			    "mount BE (%s)\n"), bt->obe_name);
			return (BE_ERR_MOUNT);
		}
		be_mounted = B_TRUE;
	}
	ZFS_CLOSE(zhp);

	(void) snprintf(stage1, sizeof (stage1), "%s%s", tmp_mntpt, BE_STAGE_1);
	(void) snprintf(stage2, sizeof (stage2), "%s%s", tmp_mntpt, BE_STAGE_2);

	if ((zphp = zpool_open(g_zfs, bt->obe_zpool)) == NULL) {
		be_print_err(gettext("be_do_installgrub: failed to open "
		    "pool (%s): %s\n"), bt->obe_zpool,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		if (be_mounted)
			(void) _be_unmount(bt->obe_name, 0);
		free(tmp_mntpt);
		return (err);
	}

	if ((config = zpool_get_config(zphp, NULL)) == NULL) {
		be_print_err(gettext("be_do_installgrub: failed to get zpool "
		    "configuration information. %s\n"),
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	/*
	 * Get the vdev tree
	 */
	if (nvlist_lookup_nvlist(config, ZPOOL_CONFIG_VDEV_TREE, &nv) != 0) {
		be_print_err(gettext("be_do_installgrub: failed to get vdev "
		    "tree: %s\n"), libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	if (nvlist_lookup_nvlist_array(nv, ZPOOL_CONFIG_CHILDREN, &child,
	    &children) != 0) {
		be_print_err(gettext("be_do_installgrub: failed to traverse "
		    "the vdev tree: %s\n"), libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}
	for (c = 0; c < children; c++) {
		uint_t i, nchildren = 0;
		nvlist_t **nvchild;
		vname = zpool_vdev_name(g_zfs, zphp, child[c]);
		if (vname == NULL) {
			be_print_err(gettext(
			    "be_do_installgrub: "
			    "failed to get device name: %s\n"),
			    libzfs_error_description(g_zfs));
			err = zfs_err_to_be_err(g_zfs);
			goto done;
		}
		if (strcmp(vname, "mirror") == 0 || vname[0] != 'c') {

			if (nvlist_lookup_nvlist_array(child[c],
			    ZPOOL_CONFIG_CHILDREN, &nvchild, &nchildren) != 0) {
				be_print_err(gettext("be_do_installgrub: "
				    "failed to traverse the vdev tree: %s\n"),
				    libzfs_error_description(g_zfs));
				err = zfs_err_to_be_err(g_zfs);
				goto done;
			}

			for (i = 0; i < nchildren; i++) {
				vname = zpool_vdev_name(g_zfs, zphp,
				    nvchild[i]);
				if (vname == NULL) {
					be_print_err(gettext(
					    "be_do_installgrub: "
					    "failed to get device name: %s\n"),
					    libzfs_error_description(g_zfs));
					err = zfs_err_to_be_err(g_zfs);
					goto done;
				}

				(void) snprintf(installgrub_cmd,
				    sizeof (installgrub_cmd),
				    "%s %s %s /dev/rdsk/%s > /dev/null 2>&1",
				    BE_INSTALL_GRUB, stage1, stage2, vname);
				err = system(installgrub_cmd);

				if (err) {
					be_print_err(gettext(
					    "be_do_installgrub: installgrub "
					    "failed for device %s.\n"), vname);
					free(vname);
					err = errno_to_be_err(err);
					goto done;
				}
				free(vname);
			}
		} else {
			(void) snprintf(installgrub_cmd,
			    sizeof (installgrub_cmd),
			    "%s %s %s /dev/rdsk/%s > /dev/null 2>&1",
			    BE_INSTALL_GRUB, stage1, stage2, vname);
			err = system(installgrub_cmd);

			if (err) {
				be_print_err(gettext(
				    "be_do_installgrub: installgrub "
				    "failed for device %s.\n"), vname);
				free(vname);
				err = errno_to_be_err(err);
				goto done;
			}
			free(vname);
		}
	}

	/*
	 * Copy the grub capability file from the BE we're activating into
	 * the root pool.
	 */
	(void) snprintf(cap_file, sizeof (cap_file), "%s%s", tmp_mntpt,
	    BE_CAP_FILE);
	(void) snprintf(zpool_cap_file, sizeof (zpool_cap_file), "/%s%s",
	    bt->obe_zpool, BE_CAP_FILE);
	if ((cap_fp = fopen(cap_file, "r")) == NULL) {
		err = errno;
		be_print_err(gettext("be_do_installgrub: failed to open grub "
		    "capability file\n"));
		err = errno_to_be_err(err);
		goto done;
	}
	if ((zpool_cap_fp = fopen(zpool_cap_file, "w")) == NULL) {
		err = errno;
		be_print_err(gettext("be_do_installgrub: failed to open new "
		    "grub capability file\n"));
		err = errno_to_be_err(err);
		goto done;
	}

	while (fgets(line, BUFSIZ, cap_fp)) {
		fputs(line, zpool_cap_fp);
	}

	fclose(zpool_cap_fp);
	fclose(cap_fp);

done:
	if (be_mounted)
		(void) _be_unmount(bt->obe_name, 0);
	zpool_close(zphp);
	free(tmp_mntpt);
	return (err);
}
