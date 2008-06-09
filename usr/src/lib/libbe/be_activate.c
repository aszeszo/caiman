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

/* ******************************************************************** */
/*			Public Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_activate
 * Description:	Calls _be_activate which activates the BE named in the
 *		attributes passed in through be_attrs. The process of
 *		activation sets the bootfs property of the root pool, resets
 *		the canmount property to on, and sets the default in the grub
 *		menu to the entry corresponding to the entry for the named BE.
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
	zfs_handle_t	*zhp;
	char		root_ds[MAXPATHLEN];
	char		mountpoint[MAXPATHLEN];
	be_node_list_t *be_nodes;
	int		err = 0;
	int		ret, entry;

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

	zhp = zfs_open(g_zfs, cb.obe_root_ds, ZFS_TYPE_DATASET);
	if (zhp == NULL) {
		/*
		 * The zfs_open failed return an error
		 */
		be_print_err(gettext("be_activate: failed "
		    "to open BE root dataset (%s): %s\n"), cb.obe_root_ds,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		be_zfs_fini();
		return (err);
	} else {
		/*
		 * once the legacy mounts are no longer needed for booting
		 * zfs root this should be removed.
		 */
		zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, mountpoint,
		    sizeof (mountpoint), NULL, NULL, 0, B_FALSE);
		if (strcmp(mountpoint, ZFS_MOUNTPOINT_LEGACY) != 0)
			zfs_prop_set(zhp, zfs_prop_to_name(ZFS_PROP_MOUNTPOINT),
			    ZFS_MOUNTPOINT_LEGACY);
	}

	ZFS_CLOSE(zhp);

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
