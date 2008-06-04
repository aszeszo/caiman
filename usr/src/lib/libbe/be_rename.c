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
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#include "libbe.h"
#include "libbe_priv.h"

/* ******************************************************************** */
/*			Public Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_rename
 * Description:	Renames the BE from the original name to the new name
 *		passed in through be_attrs. Also the entries in vfstab and
 *		menu.lst are updated with the new name.
 * Parameters:
 *		be_attrs - pointer to nvlist_t of attributes being passed in.
 *			   The following attribute values are used by
 *			   this function:
 *
 *			   BE_ATTR_ORIG_BE_NAME		*required
 *			   BE_ATTR_NEW_BE_NAME		*required
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Public
 */

int
be_rename(nvlist_t *be_attrs)
{
	be_transaction_data_t	bt = { 0 };
	be_fs_list_data_t	fld = { 0 };
	zfs_handle_t	*zhp = NULL;
	char		root_ds[MAXPATHLEN];
	char		*mp = NULL;
	int		err = 0, ret = 0;

	/* Initialize libzfs handle */
	if (!be_zfs_init())
		return (BE_ERR_INIT);

	/* Get original BE name to rename from */
	if (nvlist_lookup_string(be_attrs, BE_ATTR_ORIG_BE_NAME, &bt.obe_name)
	    != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "lookup BE_ATTR_ORIG_BE_NAME attribute\n"));
		be_zfs_fini();
		return (BE_ERR_INVAL);
	}

	/* Get new BE name to rename to */
	if (nvlist_lookup_string(be_attrs, BE_ATTR_NEW_BE_NAME, &bt.nbe_name)
	    != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "lookup BE_ATTR_NEW_BE_NAME attribute\n"));
		be_zfs_fini();
		return (BE_ERR_INVAL);
	}

	/* Validate original BE name */
	if (!be_valid_be_name(bt.obe_name)) {
		be_print_err(gettext("be_rename: "
		    "invalid BE name %s\n"), bt.obe_name);
		be_zfs_fini();
		return (BE_ERR_INVAL);
	}

	/* Validate new BE name */
	if (!be_valid_be_name(bt.nbe_name)) {
		be_print_err(gettext("be_rename: invalid BE name %s\n"),
		    bt.nbe_name);
		be_zfs_fini();
		return (BE_ERR_INVAL);
	}

	/* Find which zpool the BE is in */
	if (zpool_iter(g_zfs, be_find_zpool_callback, &bt) == 0) {
		be_print_err(gettext("be_rename: failed to "
		    "find zpool for BE (%s)\n"), bt.obe_name);
		be_zfs_fini();
		return (BE_ERR_BE_NOENT);
	} else if (ret < 0) {
		be_print_err(gettext("be_rename: zpool_iter failed: %s\n"),
		    libzfs_error_description(g_zfs));
		ret = zfs_err_to_be_err(g_zfs);
		be_zfs_fini();
		return (ret);
	}

	/* New BE will reside in the same zpool as orig BE */
	bt.nbe_zpool = bt.obe_zpool;

	be_make_root_ds(bt.obe_zpool, bt.obe_name, root_ds, sizeof (root_ds));
	bt.obe_root_ds = strdup(root_ds);
	be_make_root_ds(bt.nbe_zpool, bt.nbe_name, root_ds, sizeof (root_ds));
	bt.nbe_root_ds = strdup(root_ds);

	/*
	 * Generate a list of file systems from the BE that are legacy
	 * mounted before renaming.  We use this list to determine which
	 * entries in the vfstab we need to update after we've renamed the BE.
	 */
	if ((err = be_get_legacy_fs(bt.obe_name, bt.obe_zpool, &fld)) != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "get legacy mounted file system list for %s\n"),
		    bt.obe_name);
		goto done;
	}

	/* Get handle to BE's root dataset */
	if ((zhp = zfs_open(g_zfs, bt.obe_root_ds, ZFS_TYPE_FILESYSTEM))
	    == NULL) {
		be_print_err(gettext("be_rename: failed to "
		    "open BE root dataset (%s): %s\n"),
		    bt.obe_root_ds, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	/* Rename of BE's root dataset. */
	if (zfs_rename(zhp, bt.nbe_root_ds, B_FALSE) != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "rename dataset (%s): %s\n"), bt.obe_root_ds,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	/* Refresh handle to BE's root dataset after the rename */
	ZFS_CLOSE(zhp);
	if ((zhp = zfs_open(g_zfs, bt.nbe_root_ds, ZFS_TYPE_FILESYSTEM))
	    == NULL) {
		be_print_err(gettext("be_rename: failed to "
		    "open BE root dataset (%s): %s\n"),
		    bt.obe_root_ds, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	/* If BE is already mounted, get its mountpoint */
	if (zfs_is_mounted(zhp, &mp) && mp == NULL) {
		be_print_err(gettext("be_rename: failed to "
		    "get altroot of mounted BE %s: %s\n"),
		    bt.nbe_name, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		goto done;
	}

	/* Update BE's vfstab */
	if ((err = be_update_vfstab(bt.nbe_name, bt.nbe_zpool, &fld, mp))
	    != 0) {
		be_print_err(gettext("be_rename: "
		    "failed to update new BE's vfstab (%s)\n"), bt.nbe_name);
		goto done;
	}

	/* Update this BE's GRUB menu entry */
	if ((err = be_update_grub(bt.obe_name, bt.nbe_name, bt.obe_zpool,
	    NULL)) != 0) {
		be_print_err(gettext("be_rename: "
		    "failed to update grub menu entry from %s to %s\n"),
		    bt.obe_name, bt.nbe_name);
	}

done:
	free_fs_list(&fld);

	ZFS_CLOSE(zhp);

	be_zfs_fini();

	free(bt.obe_root_ds);
	free(bt.nbe_root_ds);
	return (err);
}
