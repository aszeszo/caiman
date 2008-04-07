/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
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
#include <errno.h>
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
/*                      Public Functions                                */
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
 *		non-zero - Failure
 * Scope:
 *		Public
 */

int
be_rename(nvlist_t *be_attrs)
{
	be_transaction_data_t bt = { 0 };
	zfs_handle_t	*zhp;
	char		root_ds[MAXPATHLEN];
	int		err = 0;
	int		ret;
	
        /* Initialize libzfs handle */
	if (!be_zfs_init())
		return (1);

	/* Get original BE name to rename from */
	if (nvlist_lookup_string(be_attrs, BE_ATTR_ORIG_BE_NAME, &bt.obe_name)
	    != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "lookup BE_ATTR_ORIG_BE_NAME attribute\n"));
		be_zfs_fini();
		return (1);
	}

	/* Get new BE name to rename to */
	if (nvlist_lookup_string(be_attrs, BE_ATTR_NEW_BE_NAME, &bt.nbe_name)
	    != 0) {
		be_print_err(gettext("be_rename: failed to "
		    "lookup BE_ATTR_NEW_BE_NAME attribute\n"));
		be_zfs_fini();
		return (1);
	}

	/* Validate original BE name */
	if (!be_valid_be_name(bt.obe_name)) {
		be_print_err(gettext("be_rename: "
		    "invalid BE name %s\n"), bt.obe_name);
		be_zfs_fini();
		return (1);
	}

	/* Validate new BE name */
	if (!be_valid_be_name(bt.nbe_name)) {
		be_print_err(gettext("be_rename: invalid BE name %s\n"),
		    bt.nbe_name);
		be_zfs_fini();
		return (1);
	}

	/* Find which zpool the BE is in */
	if ((ret = zpool_iter(g_zfs, be_find_zpool_callback, &bt)) == 0) {
		be_print_err(gettext("be_rename: failed to "
		    "find zpool for BE (%s)\n"), bt.obe_name);
		be_zfs_fini();
		return (1);
	} else if (ret < 0) {
		be_print_err(gettext("be_rename: zpool_iter failed: %s\n"),
		    libzfs_error_description(g_zfs));
		be_zfs_fini();
		return (1);
	}

	be_make_root_ds(bt.obe_zpool, bt.obe_name, root_ds, sizeof (root_ds));
	bt.obe_root_ds = strdup(root_ds);
	be_make_root_ds(bt.obe_zpool, bt.nbe_name, root_ds, sizeof (root_ds));
	bt.nbe_root_ds = strdup(root_ds);

	zhp = zfs_open(g_zfs, bt.obe_root_ds, ZFS_TYPE_DATASET);
	if (zhp == NULL) {
		/*
		 * The zfs_open failed, return an error.
		 */
		be_print_err(gettext("be_rename: failed to "
		    "open BE root dataset (%s)\n"),
		    bt.obe_root_ds);
		err = 1;
		goto done;
	} else {
		err = zfs_rename(zhp, bt.nbe_root_ds, B_FALSE);
		if (err) {
			be_print_err(gettext("be_rename: failed to "
			    "rename dataset (%s)\n"), bt.obe_root_ds);
			goto done;
		}
	}

	/*
	 * TODO: - Until we have ZFS boot, we need to modify the new BE's
	 * vfstab because we're still legacy mounting root.
	 */
	if ((err = be_update_vfstab(bt.nbe_name, bt.nbe_root_ds, NULL)) != 0)
		be_print_err(gettext("be_rename: filed to "
		    "update new BE's vfstab (%s)\n"), bt.nbe_name);
	else if ((err = be_update_grub(bt.obe_name, bt.nbe_name,
	    bt.obe_zpool, NULL)) != 0)
		be_print_err(gettext("be_rename: failed to update "
		    "grub menu\n"));

done:
	if (zhp != NULL)
		zfs_close(zhp);

	be_zfs_fini();

	free(bt.obe_root_ds);
	free(bt.nbe_root_ds);
	return(err);
}
