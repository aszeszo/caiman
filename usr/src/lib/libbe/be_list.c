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
#include <strings.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include "libbe.h"
#include "libbe_priv.h"

/*
 * Callback data used for zfs_iter calls.
 */
typedef struct list_callback_data {
	char *zpool_name;
	char *be_name;
	be_node_list_t *be_nodes_head;
	be_node_list_t *be_nodes;
	char current_be[MAXPATHLEN];
} list_callback_data_t;

/*
 * Private callback function prototypes
 */
static int be_get_list_all_callback(zpool_handle_t *zhp, void *data);
static int be_get_list_callback(zpool_handle_t *, void *);
static int be_add_children_callback(zfs_handle_t *zhp, void *data);
static void be_sort_list(be_node_list_t **);
static int be_qsort_compare_BEs(const void *, const void *);
static int be_qsort_compare_snapshots(const void *x, const void *y);
static int be_qsort_compare_datasets(const void *x, const void *y);

/*
 * Private data.
 */
static char be_container_ds[MAXPATHLEN];
const char *rpool;

/* ******************************************************************** */
/*			Public Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_list
 * Description:	Calls _be_list which finds all the BEs on the system and
 *		returns the datasets and snapshots belonging to each BE.
 *		Also data, such as dataset and snapshot properties,
 *		for each BE and their snapshots and datasets is
 *		returned. The data returned is as described in the
 *		be_dataset_list_t, be_snapshot_list_t and be_node_list_t
 *		structures.
 * Parameters:
 *		be_name - The name of the BE to look up.
 *			  If NULL a list of all BEs will be returned.
 *		be_nodes - A reference pointer to the list of BEs. The list
 *			   structure will be allocated by _be_list and must
 *			   be freed by a call to be_free_list. If there are no
 *			   BEs found on the system this reference will be
 *			   set to NULL.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Public
 */
int
be_list(char *be_name, be_node_list_t **be_nodes)
{
	int	ret = 0;

	/* Initialize libzfs handle */
	if (!be_zfs_init())
		return (BE_ERR_INIT);

	/* Validate be_name if its not NULL */
	if (be_name != NULL) {
		if (!be_valid_be_name(be_name)) {
			be_print_err(gettext("be_list: "
			    "invalid BE name %s\n"), be_name);
			return (BE_ERR_INVAL);
		}
	}

	ret = _be_list(be_name, be_nodes);

	be_zfs_fini();

	be_sort_list(be_nodes);

	return (ret);
}

/* ******************************************************************** */
/*			Semi-Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	_be_list
 * Description:	This does the actual work described in be_list.
 * Parameters:
 *		be_name - The name of the BE to look up.
 *			  If NULL a list of all BEs will be returned.
 *		be_nodes - A reference pointer to the list of BEs. The list
 *			   structure will be allocated here and must
 *			   be freed by a call to be_free_list. If there are no
 *			   BEs found on the system this reference will be
 *			   set to NULL.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Semi-private (library wide use only)
 */
int
_be_list(char *be_name, be_node_list_t **be_nodes)
{
	list_callback_data_t cb = { 0 };
	be_transaction_data_t bt = { 0 };
	int err = 0;

	if (be_nodes == NULL)
		return (BE_ERR_INVAL);

	if (be_find_current_be(&bt) != BE_SUCCESS) {
		/*
		 * We were unable to find a currently booted BE which
		 * probably means that we're not booted in a BE envoronment.
		 * None of the BE's will be marked as the active BE.
		 */
		(void) strcpy(cb.current_be, "-");
	} else {
		(void) strncpy(cb.current_be, bt.obe_name,
		    sizeof (cb.current_be));
	}

	/*
	 * If be_name is NULL we'll look for all BE's on the system.
	 * If not then we will only return data for the specified BE.
	 */
	if (be_name == NULL) {
		err = zpool_iter(g_zfs, be_get_list_all_callback, &cb);
		if (err != 0) {
			if (cb.be_nodes_head != NULL) {
				be_free_list(cb.be_nodes_head);
				cb.be_nodes_head = NULL;
				cb.be_nodes = NULL;
			}
			err = BE_ERR_BE_NOENT;
		} else if (cb.be_nodes_head == NULL) {
			be_print_err(gettext("be_list: "
			    "No BE's found\n"));
			err = BE_ERR_BE_NOENT;
		}
	} else {
		cb.be_name = be_name;
		err = zpool_iter(g_zfs, be_get_list_callback, &cb);
		if (err != 0) {
			if (cb.be_nodes_head != NULL) {
				be_free_list(cb.be_nodes_head);
				cb.be_nodes_head = NULL;
				cb.be_nodes = NULL;
			}
			err = BE_ERR_BE_NOENT;
		} else if (cb.be_nodes_head == NULL) {
			be_print_err(gettext("be_list: "
			    "BE (%s) does not exist\n"),
			    be_name);
			err = BE_ERR_BE_NOENT;
		}
	}

	*be_nodes = cb.be_nodes_head;

	return (err);
}

/* ******************************************************************** */
/*			Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_get_list_all_callback
 * Description:	Callback function used by zpool_iter to look through all
 *		the pools on the system looking for BEs. This function is
 *		used when no BE is specified and we want to return a list
 *		of all BEs on the system.
 * Parameters:
 *		zlp - handle to the first zpool. (provided by the
 *		      zpool_iter call)
 *		data - pointer to the callback data and where we'll pass
 *		       the list of BE back.
 * Returns:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_get_list_all_callback(zpool_handle_t *zlp, void *data)
{
	list_callback_data_t *cb = (list_callback_data_t *)data;
	zfs_handle_t *zhp = NULL;
	int err = 0;

	rpool = zpool_get_name(zlp);

	/*
	 * Generate string for the BE container dataset
	 */
	be_make_container_ds(rpool, be_container_ds,
	    sizeof (be_container_ds));

	/*
	 * Check if main BE container dataset exists
	 */
	if (!zfs_dataset_exists(g_zfs, be_container_ds,
	    ZFS_TYPE_FILESYSTEM)) {
		/*
		 * No BE container dataset exists in this pool,
		 * no valid BE's in this pool, try the next pool.
		 */
		zpool_close(zlp);
		return (0);
	}

	if ((zhp = zfs_open(g_zfs, be_container_ds, ZFS_TYPE_FILESYSTEM)) ==
	    NULL) {
		be_print_err(gettext("be_get_list_all_callback: failed to "
		    "open BE container dataset %s: %s\n"),
		    be_container_ds, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		zpool_close(zlp);
		return (err);
	}

	if (cb->be_nodes_head == NULL) {
		cb->be_nodes_head = cb->be_nodes =
		    calloc(1, sizeof (be_node_list_t));
		if (cb->be_nodes == NULL) {
			ZFS_CLOSE(zhp);
			zpool_close(zlp);
			be_print_err(gettext("be_get_list_all_callback: memory "
			    "allocation failed\n"));
			return (BE_ERR_NOMEM);
		}
	}

	/*
	 * iterate through the next level of datasets to find the BE's
	 * within the pool
	 */
	err = zfs_iter_filesystems(zhp, be_add_children_callback, cb);
	ZFS_CLOSE(zhp);
	zpool_close(zlp);

	return (err);
}

/*
 * Function:	be_get_list_callback
 * Description:	Callback function used by zfs_iter to look through all
 *		the datasets and snapshots for the named BE. This function
 *		is used when a BE name has been specified.
 * Parameters:
 *		zlp - handle to the first zfs dataset. (provided by the
 *		      zfs_iter_* call)
 *		data - pointer to the callback data and where we'll pass
 *		       the BE information back.
 * Returns:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_get_list_callback(zpool_handle_t *zlp, void *data)
{
	list_callback_data_t *cb = (list_callback_data_t *)data;
	char be_ds[MAXPATHLEN];
	char prop_buf[MAXPATHLEN];
	nvlist_t *userprops;
	nvlist_t *propval;
	char *prop_str;
	char *grub_default_bootfs;
	zfs_handle_t *zhp = NULL;
	zpool_handle_t *zphp = NULL;
	int err = 0;

	rpool =  zpool_get_name(zlp);

	/*
	 * Generate string for the BE container dataset
	 */
	be_make_container_ds(rpool, be_container_ds,
	    sizeof (be_container_ds));
	be_make_root_ds(rpool, cb->be_name, be_ds, sizeof (be_ds));

	/*
	 * Check if main BE dataset exists
	 */
	if (!zfs_dataset_exists(g_zfs, be_ds,
	    ZFS_TYPE_FILESYSTEM)) {
		/*
		 * No BE root dataset exists in this pool,
		 * no valid BE's in this pool. Try the
		 * next zpool.
		 */
		zpool_close(zlp);
		return (BE_SUCCESS);
	}

	if ((zhp = zfs_open(g_zfs, be_ds, ZFS_TYPE_FILESYSTEM)) == NULL) {
		be_print_err(gettext("be_get_list_callback: failed to open "
		    "BE root dataset %s: %s\n"), be_ds,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		zpool_close(zlp);
		return (err);
	}

	cb->be_nodes_head = cb->be_nodes = calloc(1, sizeof (be_node_list_t));
	if (cb->be_nodes == NULL) {
		ZFS_CLOSE(zhp);
		zpool_close(zlp);
		be_print_err(gettext("be_get_list_callback: memory allocation "
		    "failed\n"));
		return (BE_ERR_NOMEM);
	}

	cb->be_nodes->be_root_ds = strdup(be_ds);

	cb->be_nodes->be_node_name = strdup(cb->be_name);
	if (strncmp(cb->be_name, cb->current_be, MAXPATHLEN) == 0)
		cb->be_nodes->be_active = B_TRUE;
	else
		cb->be_nodes->be_active = B_FALSE;

	cb->be_nodes->be_rpool = strdup(rpool);

	zphp = zpool_open(g_zfs, rpool);
	cb->be_nodes->be_space_used = zfs_prop_get_int(zhp, ZFS_PROP_USED);
	zpool_get_prop(zphp, ZPOOL_PROP_BOOTFS, prop_buf, ZFS_MAXPROPLEN,
	    NULL);
	grub_default_bootfs = be_default_grub_bootfs(rpool);
	if (grub_default_bootfs != NULL)
		if (strcmp(grub_default_bootfs, be_ds) == 0)
			cb->be_nodes->be_active_on_boot = B_TRUE;
		else
			cb->be_nodes->be_active_on_boot = B_FALSE;
	else if (prop_buf != NULL && strcmp(prop_buf, be_ds) == 0)
		cb->be_nodes->be_active_on_boot = B_TRUE;
	else
		cb->be_nodes->be_active_on_boot = B_FALSE;
	free(grub_default_bootfs);
	/*
	 * If the dataset is mounted use the mount point
	 * returned from the zfs_is_mounted call. If the
	 * dataset is not mounted then pull the mount
	 * point information out of the zfs properties.
	 */
	cb->be_nodes->be_mounted = zfs_is_mounted(zhp,
	    &(cb->be_nodes->be_mntpt));
	if (!cb->be_nodes->be_mounted) {
		err = zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, prop_buf,
		    ZFS_MAXPROPLEN, NULL, NULL, 0, B_FALSE);
		if (err)
			cb->be_nodes->be_mntpt = NULL;
		else
			cb->be_nodes->be_mntpt = strdup(prop_buf);
	}
	cb->be_nodes->be_node_creation = (time_t)zfs_prop_get_int(zhp,
	    ZFS_PROP_CREATION);

	/*
	 * We need to get the "com.sun.libbe:policy" user property
	 */
	if ((userprops = zfs_get_user_props(zhp)) == NULL) {
		cb->be_nodes->be_policy_type = strdup("static");
	} else {
		if (nvlist_lookup_nvlist(userprops, BE_POLICY_PROPERTY,
		    &propval) != 0 || propval == NULL) {
			cb->be_nodes->be_policy_type = strdup("static");
		} else {
			verify(nvlist_lookup_string(propval, ZPROP_VALUE,
			    &prop_str) == 0);
			if (prop_str == NULL || strcmp(prop_str, "-") == 0 ||
			    strcmp(prop_str, "") == 0)
				cb->be_nodes->be_policy_type = strdup("static");
			else
				cb->be_nodes->be_policy_type = strdup(prop_str);
		}
	}

	zpool_close(zphp);

	/*
	 * Increment the dataset counter to include the root dataset
	 * of the BE.
	 */
	cb->be_nodes->be_node_num_datasets++;

	/*
	 * iterate through the next level of datasets to find the BE's
	 * within the pool
	 */
	err = zfs_iter_children(zhp, be_add_children_callback, cb);
	ZFS_CLOSE(zhp);
	zpool_close(zlp);
	return (err);
}

/*
 * Function:	be_add_children_callback
 * Description:	Callback function used by zfs_iter to look through all
 *		the datasets and snapshots for each BE and add them to
 *		the lists of information to be passed back.
 * Parameters:
 *		zhp - handle to the first zfs dataset. (provided by the
 *		      zfs_iter_* call)
 *		data - pointer to the callback data and where we'll pass
 *		       the BE information back.
 * Returns:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_add_children_callback(zfs_handle_t *zhp, void *data)
{
	list_callback_data_t	*cb = (list_callback_data_t *)data;
	char			prop_buf[ZFS_MAXPROPLEN];
	char			*str, *ds_path;
	nvlist_t		*propval;
	nvlist_t		*userprops;
	char			*prop_str;
	char			*last;
	char			*grub_default_bootfs;
	int			err = 0;

	ds_path = str = strdup(zfs_get_name(zhp));

	if (strncmp(str + strlen(be_container_ds), "@", 1) == 0) {
		/*
		 * This is a snapshot created by the installer and not a BE.
		 */
		ZFS_CLOSE(zhp);
		return (BE_SUCCESS);
	}
	/*
	 * get past the end of the container dataset plus the trailing "/"
	 */
	str = str + (strlen(be_container_ds) + 1);
	if (strchr(str, '/') == NULL && strchr(str, '@') == NULL) {
		if (cb->be_nodes->be_node_name == NULL) {
			zpool_handle_t *zphp = zpool_open(g_zfs, rpool);
			zfs_handle_t *zfshp = zfs_open(g_zfs, ds_path,
			    ZFS_TYPE_DATASET);
			cb->be_nodes->be_node_name = strdup(str);
			if (strncmp(str, cb->current_be, MAXPATHLEN) == 0)
				cb->be_nodes->be_active = B_TRUE;
			else
				cb->be_nodes->be_active = B_FALSE;
			cb->be_nodes->be_root_ds = strdup(ds_path);
			cb->be_nodes->be_rpool = strdup(rpool);
			cb->be_nodes->be_space_used = zfs_prop_get_int(zfshp,
			    ZFS_PROP_USED);
			zpool_get_prop(zphp, ZPOOL_PROP_BOOTFS, prop_buf,
			    ZFS_MAXPROPLEN, NULL);
			grub_default_bootfs = be_default_grub_bootfs(rpool);
			if (grub_default_bootfs != NULL) {
				if (strcmp(grub_default_bootfs, ds_path) == 0)
					cb->be_nodes->be_active_on_boot =
					    B_TRUE;
				else
					cb->be_nodes->be_active_on_boot =
					    B_FALSE;
			} else if (prop_buf != NULL &&
			    strcmp(prop_buf, ds_path) == 0)
				cb->be_nodes->be_active_on_boot = B_TRUE;
			else
				cb->be_nodes->be_active_on_boot =
				    B_FALSE;
			free(grub_default_bootfs);
			/*
			 * If the dataset is mounted use the mount point
			 * returned from the zfs_is_mounted call. If the
			 * dataset is not mounted then pull the mount
			 * point information out of the zfs properties.
			 */
			cb->be_nodes->be_mounted = zfs_is_mounted(zfshp,
			    &(cb->be_nodes->be_mntpt));
			if (!cb->be_nodes->be_mounted) {
				err = zfs_prop_get(zfshp, ZFS_PROP_MOUNTPOINT,
				    prop_buf, ZFS_MAXPROPLEN, NULL, NULL, 0,
				    B_FALSE);
				if (err)
					cb->be_nodes->be_mntpt = NULL;
				else
					cb->be_nodes->be_mntpt =
					    strdup(prop_buf);
			}
			cb->be_nodes->be_node_creation =
			    (time_t)zfs_prop_get_int(zfshp,
			    ZFS_PROP_CREATION);
			/*
			 * We need to get the "com.sun.libbe:policy" user
			 * property
			 */
			if ((userprops = zfs_get_user_props(zfshp)) == NULL) {
				cb->be_nodes->be_policy_type =
				    strdup("static");
			} else {
				if (nvlist_lookup_nvlist(userprops,
				    BE_POLICY_PROPERTY, &propval) != 0 ||
				    propval == NULL) {
					cb->be_nodes->be_policy_type =
					    strdup("static");
				} else {
					verify(nvlist_lookup_string(propval,
					    ZPROP_VALUE, &prop_str) == 0);
					if (prop_str == NULL ||
					    strcmp(prop_str, "-") == 0 ||
					    strcmp(prop_str, "") == 0)
						cb->be_nodes->be_policy_type =
						    strdup("static");
					else
						cb->be_nodes->be_policy_type =
						    strdup(prop_str);
				}
			}
			cb->be_nodes->be_node_num_datasets++;
			ZFS_CLOSE(zfshp);
			zpool_close(zphp);
		} else {
			zpool_handle_t *zphp = zpool_open(g_zfs, rpool);
			zfs_handle_t *zfshp = zfs_open(g_zfs, ds_path,
			    ZFS_TYPE_DATASET);
			cb->be_nodes->be_next_node = calloc(1,
			    sizeof (be_node_list_t));
			if (cb->be_nodes->be_next_node == NULL) {
				ZFS_CLOSE(zhp);
				ZFS_CLOSE(zfshp);
				zpool_close(zphp);
				be_print_err(gettext(
				    "be_add_children_callback: memory "
				    "allocation failed\n"));
				return (BE_ERR_NOMEM);
			}
			cb->be_nodes = cb->be_nodes->be_next_node;
			cb->be_nodes->be_next_node = NULL;
			cb->be_nodes->be_node_name = strdup(str);
			if (strncmp(str, cb->current_be, MAXPATHLEN) == 0)
				cb->be_nodes->be_active = B_TRUE;
			else
				cb->be_nodes->be_active = B_FALSE;
			cb->be_nodes->be_root_ds = strdup(ds_path);
			cb->be_nodes->be_rpool = strdup(rpool);
			cb->be_nodes->be_space_used = zfs_prop_get_int(zfshp,
			    ZFS_PROP_USED);
			zpool_get_prop(zphp, ZPOOL_PROP_BOOTFS, prop_buf,
			    ZFS_MAXPROPLEN, NULL);
			grub_default_bootfs = be_default_grub_bootfs(rpool);
			if (grub_default_bootfs != NULL) {
				if (strcmp(grub_default_bootfs, ds_path) == 0)
					cb->be_nodes->be_active_on_boot
					    = B_TRUE;
				else
					cb->be_nodes->be_active_on_boot
					    = B_FALSE;
			} else if (prop_buf != NULL &&
			    strcmp(prop_buf, ds_path) == 0)
				cb->be_nodes->be_active_on_boot =
				    B_TRUE;
			else
				cb->be_nodes->be_active_on_boot =
				    B_FALSE;
			free(grub_default_bootfs);
			/*
			 * If the dataset is mounted use the mount point
			 * returned from the zfs_is_mounted call. If the
			 * dataset is not mounted then pull the mount
			 * point information out of the zfs properties.
			 */
			cb->be_nodes->be_mounted = zfs_is_mounted(zfshp,
			    &(cb->be_nodes->be_mntpt));
			if (!cb->be_nodes->be_mounted) {
				err = zfs_prop_get(zfshp, ZFS_PROP_MOUNTPOINT,
				    prop_buf, ZFS_MAXPROPLEN, NULL, NULL, 0,
				    B_FALSE);
				if (err)
					cb->be_nodes->be_mntpt = NULL;
				else
					cb->be_nodes->be_mntpt =
					    strdup(prop_buf);
			}
			cb->be_nodes->be_node_creation =
			    (time_t)zfs_prop_get_int(zfshp,
			    ZFS_PROP_CREATION);
			/*
			 * We need to get the "com.sun.libbe:policy" user
			 * property
			 */
			if ((userprops = zfs_get_user_props(zfshp)) == NULL) {
				cb->be_nodes->be_policy_type =
				    strdup("static");
			} else {
				if (nvlist_lookup_nvlist(userprops,
				    BE_POLICY_PROPERTY, &propval) != 0 ||
				    propval == NULL) {
					cb->be_nodes->be_policy_type =
					    strdup("static");
				} else {
					verify(nvlist_lookup_string(propval,
					    ZPROP_VALUE, &prop_str) == 0);
					if (prop_str == NULL || strcmp(prop_str,
					    "-") == 0 || strcmp(prop_str,
					    "") == 0)
						cb->be_nodes->be_policy_type =
						    strdup("static");
					else
						cb->be_nodes->be_policy_type =
						    strdup(prop_str);
				}
			}
			cb->be_nodes->be_node_num_datasets++;
			ZFS_CLOSE(zfshp);
			zpool_close(zphp);
		}
	} else if (strchr(str, '/') != NULL && strchr(str, '@') == NULL) {
		if (cb->be_nodes->be_node_datasets == NULL) {
			zfs_handle_t *zfshp = zfs_open(g_zfs, ds_path,
			    ZFS_TYPE_DATASET);
			cb->be_nodes->be_node_datasets = calloc(1,
			    sizeof (be_dataset_list_t));
			if (cb->be_nodes->be_node_datasets == NULL) {
				ZFS_CLOSE(zhp);
				ZFS_CLOSE(zfshp);
				be_print_err(gettext(
				    "be_add_children_callback: memory "
				    "allocation failed\n"));
				return (BE_ERR_NOMEM);
			}
			cb->be_nodes->be_node_datasets->be_dataset_name =
			    strdup(str);
			cb->be_nodes->be_node_datasets->be_ds_space_used =
			    zfs_prop_get_int(zfshp, ZFS_PROP_USED);
			/*
			 * If the dataset is mounted use the mount point
			 * returned from the zfs_is_mounted call. If the
			 * dataset is not mounted then pull the mount
			 * point information out of the zfs properties.
			 */
			cb->be_nodes->be_node_datasets->be_ds_mounted =
			    zfs_is_mounted(zfshp,
			    &(cb->be_nodes->be_node_datasets->be_ds_mntpt));
			if (!cb->be_nodes->be_node_datasets->be_ds_mounted) {
				err = zfs_prop_get(zfshp, ZFS_PROP_MOUNTPOINT,
				    prop_buf, ZFS_MAXPROPLEN, NULL, NULL, 0,
				    B_FALSE);
				if (err)
				cb->be_nodes->be_node_datasets->be_ds_mntpt =
				    NULL;
				else
				cb->be_nodes->be_node_datasets->be_ds_mntpt =
				    strdup(prop_buf);
			}
			cb->be_nodes->be_node_datasets->be_ds_creation =
			    (time_t)zfs_prop_get_int(zfshp, ZFS_PROP_CREATION);
			/*
			 * We need to get the "com.sun.libbe:policy" user
			 * property
			 */
			if ((userprops = zfs_get_user_props(zfshp)) == NULL) {
				cb->be_nodes->be_node_datasets->be_ds_plcy_type
				    = strdup(cb->be_nodes->be_policy_type);
			} else {
				if (nvlist_lookup_nvlist(userprops,
				    BE_POLICY_PROPERTY, &propval) != 0 ||
				    propval == NULL) {
				cb->be_nodes->be_node_datasets->be_ds_plcy_type
				    = strdup(cb->be_nodes->be_policy_type);
				} else {
					verify(nvlist_lookup_string(propval,
					    ZPROP_VALUE, &prop_str) == 0);
					if (prop_str == NULL ||
					    strcmp(prop_str, "-") == 0 ||
					    strcmp(prop_str, "") == 0)
				cb->be_nodes->be_node_datasets->be_ds_plcy_type
				    = strdup(cb->be_nodes->be_policy_type);
					else
				cb->be_nodes->be_node_datasets->be_ds_plcy_type
				    = strdup(prop_str);
				}
			}
			cb->be_nodes->be_node_datasets->be_next_dataset =
			    NULL;
			cb->be_nodes->be_node_num_datasets++;
			ZFS_CLOSE(zfshp);
		} else if (strcmp(
		    cb->be_nodes->be_node_datasets->be_dataset_name,
		    str) != 0) {
			be_dataset_list_t *datasets =
			    cb->be_nodes->be_node_datasets;
			while (datasets != NULL) {
				if (strcmp(datasets->be_dataset_name, str) ==
				    0) {
					/*
					 * We already have this dataset, move
					 * on to the next one.
					 */
					datasets = datasets->be_next_dataset;
					continue;
				} else if (datasets->be_next_dataset == NULL) {
					/*
					 * We're at the end of the list add
					 * the new dataset.
					 */
					zfs_handle_t *zfshp = zfs_open(g_zfs,
					    ds_path, ZFS_TYPE_DATASET);
					datasets->be_next_dataset = calloc(1,
					    sizeof (be_dataset_list_t));
					if (datasets->be_next_dataset ==
					    NULL) {
						ZFS_CLOSE(zhp);
						ZFS_CLOSE(zfshp);
						be_print_err(gettext(
						    "be_add_children_callback: "
						    "memory allocation "
						    "failed\n"));
						return (BE_ERR_NOMEM);
					}
					datasets = datasets->be_next_dataset;
					datasets->be_dataset_name = strdup(str);
					datasets->be_ds_space_used =
					    zfs_prop_get_int(zfshp,
					    ZFS_PROP_USED);
					/*
					 * If the dataset is mounted use
					 * the mount point returned from the
					 * zfs_is_mounted call. If the
					 * dataset is not mounted then pull
					 * the mount point information out
					 * of the zfs properties.
					 */
					datasets->be_ds_mounted =
					    zfs_is_mounted(zfshp,
					    &(datasets->be_ds_mntpt));
					if (!datasets->be_ds_mounted) {
						err = zfs_prop_get(zfshp,
						    ZFS_PROP_MOUNTPOINT,
						    prop_buf, ZFS_MAXPROPLEN,
						    NULL, NULL, 0, B_FALSE);
						if (err)
							datasets->be_ds_mntpt =
							    NULL;
						else
							datasets->be_ds_mntpt =
							    strdup(prop_buf);
					}
					datasets->be_ds_creation =
					    (time_t)zfs_prop_get_int(zfshp,
					    ZFS_PROP_CREATION);
					/*
					 * We need to get the
					 * "com.sun.libbe:policy" user
					 * property
					 */
					if ((userprops = zfs_get_user_props(
					    zfshp)) == NULL) {
				datasets->be_ds_plcy_type =
				    strdup(cb->be_nodes->be_policy_type);
					} else {
						if (nvlist_lookup_nvlist(
						    userprops,
						    BE_POLICY_PROPERTY,
						    &propval) != 0 ||
						    propval == NULL) {
					datasets->be_ds_plcy_type =
					    strdup(
					    cb->be_nodes->be_policy_type);
						} else {
					verify(nvlist_lookup_string(propval,
					    ZPROP_VALUE, &prop_str) == 0);
							if (prop_str == NULL ||
							    strcmp(prop_str,
							    "-") == 0 ||
							    strcmp(prop_str,
							    "") == 0)
					datasets->be_ds_plcy_type =
					    strdup(
					    cb->be_nodes->be_policy_type);
							else
					datasets->be_ds_plcy_type =
					    strdup(prop_str);
						}
					}
					cb->be_nodes->be_node_num_datasets++;
					datasets->be_next_dataset = NULL;
					ZFS_CLOSE(zfshp);
				}
				datasets = datasets->be_next_dataset;
			}
		}
	} else {
		if (cb->be_nodes->be_node_snapshots == NULL) {
			int space_used;
			zfs_handle_t *zfshp = zfs_open(g_zfs, ds_path,
			    ZFS_TYPE_SNAPSHOT);
			cb->be_nodes->be_node_snapshots =
			    calloc(1, sizeof (be_snapshot_list_t));
			if (cb->be_nodes->be_node_snapshots == NULL) {
				ZFS_CLOSE(zhp);
				ZFS_CLOSE(zfshp);
				be_print_err(gettext(
				    "be_add_children_callback: memory "
				    "allocation failed\n"));
				return (BE_ERR_NOMEM);
			}
			cb->be_nodes->be_node_snapshots->be_snapshot_name =
			    strdup(str);
			cb->be_nodes->be_node_snapshots->be_snapshot_creation
			    = (time_t)zfs_prop_get_int(zfshp,
			    ZFS_PROP_CREATION);
			strtok_r(str, "@", &last);
			if (!be_valid_auto_snap_name(last)) {
			cb->be_nodes->be_node_snapshots->be_snapshot_type =
			    strdup("static");
			} else {
			cb->be_nodes->be_node_snapshots->be_snapshot_type =
			    strdup(strtok_r(NULL, ":", &last));
			}
			space_used = zfs_prop_get_int(zfshp, ZFS_PROP_USED);
			if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
				ZFS_CLOSE(zhp);
				ZFS_CLOSE(zfshp);
				be_print_err(gettext(
				    "be_add_children_callback: get space "
				    "used failed (%d)\n"), err);
				return (err);
			}
			cb->be_nodes->be_node_snapshots->be_snapshot_space_used
			    = space_used;
			cb->be_nodes->be_node_snapshots->be_next_snapshot =
			    NULL;
			cb->be_nodes->be_node_num_snapshots++;
			ZFS_CLOSE(zfshp);
		} else if (
		    strcmp(cb->be_nodes->be_node_snapshots->be_snapshot_name,
		    str) != 0) {
			be_snapshot_list_t *snapshots =
			    cb->be_nodes->be_node_snapshots;
			while (snapshots != NULL) {
				if (strcmp(snapshots->be_snapshot_name,
				    str) == 0) {
					/*
					 * We already have this snapshot
					 * move on
					 */
					snapshots = snapshots->be_next_snapshot;
					continue;
				} else if (snapshots->be_next_snapshot ==
				    NULL) {
					char *last;
					int space_used;
					/*
					 * We're at the end of the list add the
					 * new snapshot.
					 */
					zfs_handle_t *zfshp =
					    zfs_open(g_zfs, ds_path,
					    ZFS_TYPE_SNAPSHOT);
					snapshots->be_next_snapshot = calloc(1,
					    sizeof (be_snapshot_list_t));
					if (snapshots->be_next_snapshot ==
					    NULL) {
						ZFS_CLOSE(zhp);
						ZFS_CLOSE(zfshp);
						be_print_err(gettext(
						    "be_add_children_callback: "
						    "memory allocation "
						    "failed\n"));
						return (BE_ERR_NOMEM);
					}
					snapshots = snapshots->be_next_snapshot;
					snapshots->be_snapshot_name =
					    strdup(str);
					snapshots->be_snapshot_creation =
					    (time_t)zfs_prop_get_int(zfshp,
					    ZFS_PROP_CREATION);
					strtok_r(str, "@", &last);
					if (!be_valid_auto_snap_name(last)) {
						snapshots->be_snapshot_type =
						    strdup("static");
					} else {
						snapshots->be_snapshot_type =
						    strdup(strtok_r(NULL, ":",
						    &last));
					}
					space_used = zfs_prop_get_int(zfshp,
					    ZFS_PROP_USED);
					if ((err = zfs_err_to_be_err(g_zfs)) !=
					    BE_SUCCESS) {
						ZFS_CLOSE(zhp);
						ZFS_CLOSE(zfshp);
						be_print_err(gettext(
						    "be_add_children_callback: "
						    "get space used failed "
						    "(%d)\n"), err);
						return (err);
					}
					snapshots->be_snapshot_space_used =
					    space_used;
					cb->be_nodes->be_node_num_snapshots++;
					snapshots->be_next_snapshot = NULL;
					ZFS_CLOSE(zfshp);
				}
				snapshots = snapshots->be_next_snapshot;
			}
		}
	}
	err = zfs_iter_children(zhp, be_add_children_callback, cb);
	if (err != 0) {
		be_print_err(gettext("be_add_children_callback: "
		    "encountered error: %s\n"),
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
	}
	ZFS_CLOSE(zhp);
	return (err);
}

/*
 * Function:	be_free_list
 * Description:	Frees up all the data allocated for the list of BEs,
 *		datasets and snapshots returned by be_list.
 * Parameters:
 *		be_node - be_nodes_t structure returned from call to be_list.
 * Returns:
 *		none
 * Scope:
 *		Private
 */
void
be_free_list(be_node_list_t *be_nodes)
{
	be_node_list_t *temp_node;
	be_node_list_t *list = be_nodes;

	while (list != NULL) {
		be_dataset_list_t *datasets = list->be_node_datasets;
		be_snapshot_list_t *snapshots = list->be_node_snapshots;

		while (datasets != NULL) {
			be_dataset_list_t *temp_ds = datasets;
			datasets = datasets->be_next_dataset;
			if (temp_ds->be_dataset_name != NULL)
				free(temp_ds->be_dataset_name);
			if (temp_ds->be_ds_mntpt != NULL)
				free(temp_ds->be_ds_mntpt);
			if (temp_ds->be_ds_plcy_type)
				free(temp_ds->be_ds_plcy_type);
			free(temp_ds);
		}

		while (snapshots != NULL) {
			be_snapshot_list_t *temp_ss = snapshots;
			snapshots = snapshots->be_next_snapshot;
			if (temp_ss->be_snapshot_name != NULL)
				free(temp_ss->be_snapshot_name);
			if (temp_ss->be_snapshot_type)
				free(temp_ss->be_snapshot_type);
			free(temp_ss);
		}

		temp_node = list;
		list = list->be_next_node;
		if (temp_node->be_node_name != NULL)
			free(temp_node->be_node_name);
		if (temp_node->be_root_ds != NULL)
			free(temp_node->be_root_ds);
		if (temp_node->be_rpool != NULL)
			free(temp_node->be_rpool);
		if (temp_node->be_mntpt != NULL)
			free(temp_node->be_mntpt);
		if (temp_node->be_policy_type != NULL)
			free(temp_node->be_policy_type);
		free(temp_node);
	}
}

/*
 * Function:	be_sort_list
 * Description:	Sort BE node list
 * Parameters:
 *		pointer to address of list head
 * Returns:
 *		nothing
 * Side effect:
 *		node list sorted by name
 * Scope:
 *		Private
 */
static void
be_sort_list(be_node_list_t **pstart)
{
	size_t ibe, nbe;
	be_node_list_t *p;
	be_node_list_t **ptrlist = NULL;

	if (pstart == NULL)
		return;
	/* build array of linked list BE struct pointers */
	for (p = *pstart, nbe = 0; p != NULL; nbe++, p = p->be_next_node) {
		ptrlist = realloc(ptrlist,
		    sizeof (be_node_list_t *) * (nbe + 2));
		ptrlist[nbe] = p;
	}
	if (nbe == 0)
		return;
	/* in-place list quicksort using qsort(3C) */
	if (nbe > 1)	/* no sort if less than 2 BEs */
		qsort(ptrlist, nbe, sizeof (be_node_list_t *),
		    be_qsort_compare_BEs);

	ptrlist[nbe] = NULL; /* add linked list terminator */
	*pstart = ptrlist[0]; /* set new linked list header */
	/* for each BE in list */
	for (ibe = 0; ibe < nbe; ibe++) {
		size_t k, ns;	/* subordinate index, count */

		/* rewrite list pointer chain, including terminator */
		ptrlist[ibe]->be_next_node = ptrlist[ibe + 1];
		/* sort subordinate snapshots */
		if (ptrlist[ibe]->be_node_num_snapshots > 1) {
			const size_t nmax = ptrlist[ibe]->be_node_num_snapshots;
			be_snapshot_list_t ** const slist =
			    malloc(sizeof (be_snapshot_list_t *) * (nmax + 1));
			be_snapshot_list_t *p;

			if (slist == NULL)
				continue;
			/* build array of linked list snapshot struct ptrs */
			for (ns = 0, p = ptrlist[ibe]->be_node_snapshots;
			    ns < nmax && p != NULL;
			    ns++, p = p->be_next_snapshot) {
				slist[ns] = p;
			}
			if (ns < 2)
				goto end_snapshot;
			slist[ns] = NULL; /* add terminator */
			/* in-place list quicksort using qsort(3C) */
			qsort(slist, ns, sizeof (be_snapshot_list_t *),
			    be_qsort_compare_snapshots);
			/* rewrite list pointer chain, including terminator */
			ptrlist[ibe]->be_node_snapshots = slist[0];
			for (k = 0; k < ns; k++)
				slist[k]->be_next_snapshot = slist[k + 1];
end_snapshot:
			free(slist);
		}
		/* sort subordinate datasets */
		if (ptrlist[ibe]->be_node_num_datasets > 1) {
			const size_t nmax = ptrlist[ibe]->be_node_num_datasets;
			be_dataset_list_t ** const slist =
			    malloc(sizeof (be_dataset_list_t *) * (nmax + 1));
			be_dataset_list_t *p;

			if (slist == NULL)
				continue;
			/* build array of linked list dataset struct ptrs */
			for (ns = 0, p = ptrlist[ibe]->be_node_datasets;
			    ns < nmax && p != NULL;
			    ns++, p = p->be_next_dataset) {
				slist[ns] = p;
			}
			if (ns < 2) /* subordinate datasets < 2 - no sort */
				goto end_dataset;
			slist[ns] = NULL; /* add terminator */
			/* in-place list quicksort using qsort(3C) */
			qsort(slist, ns, sizeof (be_dataset_list_t *),
			    be_qsort_compare_datasets);
			/* rewrite list pointer chain, including terminator */
			ptrlist[ibe]->be_node_datasets = slist[0];
			for (k = 0; k < ns; k++)
				slist[k]->be_next_dataset = slist[k + 1];
end_dataset:
			free(slist);
		}
	}
free:
	free(ptrlist);
}

/*
 * Function:	be_qsort_compare_BEs
 * Description:	lexical compare of BE names for qsort(3C)
 * Parameters:
 *		x,y - BEs with names to compare
 * Returns:
 *		positive if y>x, negative if x>y, 0 if equal
 * Scope:
 *		Private
 */
static int
be_qsort_compare_BEs(const void *x, const void *y)
{
	be_node_list_t *p = *(be_node_list_t **)x;
	be_node_list_t *q = *(be_node_list_t **)y;

	if (p == NULL || p->be_node_name == NULL)
		return (1);
	if (q == NULL || q->be_node_name == NULL)
		return (-1);
	return (strcmp(p->be_node_name, q->be_node_name));
}

/*
 * Function:	be_qsort_compare_snapshots
 * Description:	lexical compare of BE names for qsort(3C)
 * Parameters:
 *		x,y - BE snapshots with names to compare
 * Returns:
 *		positive if y>x, negative if x>y, 0 if equal
 * Scope:
 *		Private
 */
static int
be_qsort_compare_snapshots(const void *x, const void *y)
{
	be_snapshot_list_t *p = *(be_snapshot_list_t **)x;
	be_snapshot_list_t *q = *(be_snapshot_list_t **)y;

	if (p == NULL || p->be_snapshot_name == NULL)
		return (1);
	if (q == NULL || q->be_snapshot_name == NULL)
		return (-1);
	return (strcmp(p->be_snapshot_name, q->be_snapshot_name));
}

/*
 * Function:	be_qsort_compare_datasets
 * Description:	lexical compare of dataset names for qsort(3C)
 * Parameters:
 *		x,y - BE snapshots with names to compare
 * Returns:
 *		positive if y>x, negative if x>y, 0 if equal
 * Scope:
 *		Private
 */
static int
be_qsort_compare_datasets(const void *x, const void *y)
{
	be_dataset_list_t *p = *(be_dataset_list_t **)x;
	be_dataset_list_t *q = *(be_dataset_list_t **)y;

	if (p == NULL || p->be_dataset_name == NULL)
		return (1);
	if (q == NULL || q->be_dataset_name == NULL)
		return (-1);
	return (strcmp(p->be_dataset_name, q->be_dataset_name));
}
