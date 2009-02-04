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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
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
#include <errno.h>

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
 * Private function prototypes
 */
static int be_add_children_callback(zfs_handle_t *zhp, void *data);
static int be_get_list_callback(zpool_handle_t *, void *);
static int be_get_node_data(zfs_handle_t *, be_node_list_t *, char *,
    const char *, char *, char *);
static int be_get_ds_data(zfs_handle_t *, char *, be_dataset_list_t *,
    be_node_list_t *);
static int be_get_ss_data(zfs_handle_t *, char *, be_snapshot_list_t *,
    be_node_list_t *);
static void be_sort_list(be_node_list_t **);
static int be_qsort_compare_BEs(const void *, const void *);
static int be_qsort_compare_snapshots(const void *x, const void *y);
static int be_qsort_compare_datasets(const void *x, const void *y);
static void *be_list_alloc(int *, size_t);

/*
 * Private data.
 */
static char be_container_ds[MAXPATHLEN];

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
	if (be_name != NULL)
		cb.be_name = strdup(be_name);

	err = zpool_iter(g_zfs, be_get_list_callback, &cb);
	if (err != 0) {
		if (cb.be_nodes_head != NULL) {
			be_free_list(cb.be_nodes_head);
			cb.be_nodes_head = NULL;
			cb.be_nodes = NULL;
		}
		err = BE_ERR_BE_NOENT;
	}

	if (cb.be_nodes_head == NULL) {
		if (be_name != NULL)
			be_print_err(gettext("be_list: BE (%s) does not "
			    "exist\n"), be_name);
		else
			be_print_err(gettext("be_list: No BE's found\n"));
		err = BE_ERR_BE_NOENT;
	}

	*be_nodes = cb.be_nodes_head;

	free(cb.be_name);

	be_sort_list(be_nodes);

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
 *		Semi-private (library wide use only)
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
			free(temp_ds->be_dataset_name);
			free(temp_ds->be_ds_mntpt);
			free(temp_ds->be_ds_plcy_type);
			free(temp_ds);
		}

		while (snapshots != NULL) {
			be_snapshot_list_t *temp_ss = snapshots;
			snapshots = snapshots->be_next_snapshot;
			free(temp_ss->be_snapshot_name);
			free(temp_ss->be_snapshot_type);
			free(temp_ss);
		}

		temp_node = list;
		list = list->be_next_node;
		free(temp_node->be_node_name);
		free(temp_node->be_root_ds);
		free(temp_node->be_rpool);
		free(temp_node->be_mntpt);
		free(temp_node->be_policy_type);
		free(temp_node->be_uuid_str);
		free(temp_node);
	}
}

/* ******************************************************************** */
/*			Private Functions				*/
/* ******************************************************************** */

/*
 * Function:	be_get_list_callback
 * Description:	Callback function used by zfs_iter to look through all
 *		the pools on the system looking for BEs. If a BE name was
 *		specified only that BE's information will be collected and
 *		returned.
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
	char *open_ds = NULL;
	char *rpool = NULL;
	zfs_handle_t *zhp = NULL;
	int err = 0;

	cb->zpool_name = rpool =  (char *)zpool_get_name(zlp);

	/*
	 * Generate string for the BE container dataset
	 */
	be_make_container_ds(rpool, be_container_ds,
	    sizeof (be_container_ds));

	/*
	 * If a BE name was specified we use it's root dataset in place of
	 * the container dataset. This is because we only want to collect
	 * the information for the specified BE.
	 */
	if (cb->be_name != NULL) {
		/*
		 * Generate string for the BE root dataset
		 */
		be_make_root_ds(rpool, cb->be_name, be_ds, sizeof (be_ds));
		open_ds = be_ds;
	} else {
		open_ds = be_container_ds;
	}

	/*
	 * Check if the dataset exists
	 */
	if (!zfs_dataset_exists(g_zfs, open_ds,
	    ZFS_TYPE_FILESYSTEM)) {
		/*
		 * The specified dataset does not exist in this pool or
		 * there are no valid BE's in this pool. Try the next zpool.
		 */
		zpool_close(zlp);
		return (BE_SUCCESS);
	}

	if ((zhp = zfs_open(g_zfs, open_ds, ZFS_TYPE_FILESYSTEM)) == NULL) {
		be_print_err(gettext("be_get_list_callback: failed to open "
		    "the BE dataset %s: %s\n"), open_ds,
		    libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		zpool_close(zlp);
		return (err);
	}

	if (cb->be_nodes_head == NULL) {
		if ((cb->be_nodes_head = be_list_alloc(&err,
		    sizeof (be_node_list_t))) == NULL) {
			ZFS_CLOSE(zhp);
			zpool_close(zlp);
			return (err);
		}
		cb->be_nodes = cb->be_nodes_head;
	}

	/*
	 * If a BE name was specified we iterate through the datasets
	 * and snapshots for this BE only. Otherwise we will iterate
	 * through the next level of datasets to find all the BE's
	 * within the pool
	 */
	if (cb->be_name != NULL) {
		if ((err = be_get_node_data(zhp, cb->be_nodes, cb->be_name,
		    rpool, cb->current_be, be_ds)) != 0) {
			ZFS_CLOSE(zhp);
			zpool_close(zlp);
			return (err);
		}
		err = zfs_iter_snapshots(zhp, be_add_children_callback, cb);
	}


	if (err == 0)
		err = zfs_iter_filesystems(zhp, be_add_children_callback, cb);
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
	char			*str = NULL, *ds_path = NULL;
	int			err = 0;

	ds_path = str = strdup(zfs_get_name(zhp));

	/*
	 * get past the end of the container dataset plus the trailing "/"
	 */
	str = str + (strlen(be_container_ds) + 1);
	if (zfs_get_type(zhp) == ZFS_TYPE_SNAPSHOT) {
		be_snapshot_list_t *snapshots = NULL;
		if (cb->be_nodes->be_node_snapshots == NULL) {
			if ((cb->be_nodes->be_node_snapshots =
			    be_list_alloc(&err, sizeof (be_snapshot_list_t)))
			    == NULL || err != 0) {
				ZFS_CLOSE(zhp);
				return (err);
			}
			cb->be_nodes->be_node_snapshots->be_next_snapshot =
			    NULL;
			snapshots = cb->be_nodes->be_node_snapshots;
		} else {
			for (snapshots = cb->be_nodes->be_node_snapshots;
			    snapshots != NULL;
			    snapshots = snapshots->be_next_snapshot) {
				if (snapshots->be_next_snapshot != NULL)
					continue;
				/*
				 * We're at the end of the list add the
				 * new snapshot.
				 */
				if ((snapshots->be_next_snapshot =
				    be_list_alloc(&err,
				    sizeof (be_snapshot_list_t))) == NULL ||
				    err != 0) {
					ZFS_CLOSE(zhp);
					return (err);
				}
				snapshots = snapshots->be_next_snapshot;
				snapshots->be_next_snapshot = NULL;
				break;
			}
		}
		if ((err = be_get_ss_data(zhp, str, snapshots,
		    cb->be_nodes)) != 0) {
			ZFS_CLOSE(zhp);
			return (err);
		}
	} else if (strchr(str, '/') == NULL) {
		if (cb->be_nodes->be_node_name != NULL) {
			if ((cb->be_nodes->be_next_node =
			    be_list_alloc(&err, sizeof (be_node_list_t))) ==
			    NULL || err != 0) {
				ZFS_CLOSE(zhp);
				return (err);
			}
			cb->be_nodes = cb->be_nodes->be_next_node;
			cb->be_nodes->be_next_node = NULL;
		}
		if ((err = be_get_node_data(zhp, cb->be_nodes, str,
		    cb->zpool_name, cb->current_be, ds_path)) != 0) {
			ZFS_CLOSE(zhp);
			return (err);
		}
	} else if (strchr(str, '/') != NULL) {
		be_dataset_list_t *datasets = NULL;
		if (cb->be_nodes->be_node_datasets == NULL) {
			if ((cb->be_nodes->be_node_datasets =
			    be_list_alloc(&err, sizeof (be_dataset_list_t)))
			    == NULL || err != 0) {
				ZFS_CLOSE(zhp);
				return (err);
			}
			cb->be_nodes->be_node_datasets->be_next_dataset = NULL;
			datasets = cb->be_nodes->be_node_datasets;
		} else {
			for (datasets = cb->be_nodes->be_node_datasets;
			    datasets != NULL;
			    datasets = datasets->be_next_dataset) {
				if (datasets->be_next_dataset != NULL)
					continue;
				/*
				 * We're at the end of the list add
				 * the new dataset.
				 */
				if ((datasets->be_next_dataset =
				    be_list_alloc(&err,
				    sizeof (be_dataset_list_t)))
				    == NULL || err != 0) {
					ZFS_CLOSE(zhp);
					return (err);
				}
				datasets = datasets->be_next_dataset;
				datasets->be_next_dataset = NULL;
				break;
			}
		}

		if ((err = be_get_ds_data(zhp, str,
		    datasets, cb->be_nodes)) != 0) {
			ZFS_CLOSE(zhp);
			return (err);
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

/*
 * Function:	be_get_node_data
 * Description:	Helper function used to collect all the information to fill
 *		in the be_node_list structure to be returned by be_list.
 * Parameters:
 *		zhp - Handle to the root dataset for the BE whose information
 *		      we're collecting.
 *		be_node - a pointer to the node structure we're filling in.
 *		be_name - The BE name of the node whose information we're
 *		          collecting.
 *		current_be - the name of the currently active BE.
 *		be_ds - The dataset name for the BE.
 *
 * Returns:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_get_node_data(
	zfs_handle_t *zhp,
	be_node_list_t *be_node,
	char *be_name,
	const char *rpool,
	char *current_be,
	char *be_ds)
{
	char prop_buf[MAXPATHLEN];
	nvlist_t *userprops = NULL;
	nvlist_t *propval = NULL;
	char *prop_str = NULL;
	char *grub_default_bootfs = NULL;
	zpool_handle_t *zphp = NULL;
	int err = 0;

	if (be_node == NULL || be_name == NULL || current_be == NULL ||
	    be_ds == NULL) {
		be_print_err(gettext("be_get_node_data: invalid arguments, "
		    "can not be NULL\n"));
		return (BE_ERR_INVAL);
	}

	errno = 0;

	be_node->be_root_ds = strdup(be_ds);
	if ((err = errno) != 0 || be_node->be_root_ds == NULL) {
		be_print_err(gettext("be_get_node_data: failed to "
		    "copy root dataset name\n"));
		return (errno_to_be_err(err));
	}

	be_node->be_node_name = strdup(be_name);
	if ((err = errno) != 0 || be_node->be_node_name == NULL) {
		be_print_err(gettext("be_get_node_data: failed to "
		    "copy BE name\n"));
		return (errno_to_be_err(err));
	}
	if (strncmp(be_name, current_be, MAXPATHLEN) == 0)
		be_node->be_active = B_TRUE;
	else
		be_node->be_active = B_FALSE;

	be_node->be_rpool = strdup(rpool);
	if ((err = errno) != 0 || be_node->be_rpool == NULL) {
		be_print_err(gettext("be_get_node_data: failed to "
		    "copy root pool name\n"));
		return (errno_to_be_err(err));
	}

	be_node->be_space_used = zfs_prop_get_int(zhp, ZFS_PROP_USED);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_node_data: get space used failed (%d)\n"), err);
		return (err);
	}

	if ((zphp = zpool_open(g_zfs, rpool)) == NULL) {
		be_print_err(gettext("be_get_node_data: failed to open pool "
		    "(%s): %s\n"), rpool, libzfs_error_description(g_zfs));
		err = zfs_err_to_be_err(g_zfs);
		return (err);
	}

	zpool_get_prop(zphp, ZPOOL_PROP_BOOTFS, prop_buf, ZFS_MAXPROPLEN,
	    NULL);
	if (be_has_grub() &&
	    (be_default_grub_bootfs(rpool, &grub_default_bootfs) == 0) &&
	    grub_default_bootfs != NULL)
		if (strcmp(grub_default_bootfs, be_ds) == 0)
			be_node->be_active_on_boot = B_TRUE;
		else
			be_node->be_active_on_boot = B_FALSE;
	else if (prop_buf != NULL && strcmp(prop_buf, be_ds) == 0)
		be_node->be_active_on_boot = B_TRUE;
	else
		be_node->be_active_on_boot = B_FALSE;
	free(grub_default_bootfs);
	zpool_close(zphp);

	/*
	 * If the dataset is mounted use the mount point
	 * returned from the zfs_is_mounted call. If the
	 * dataset is not mounted then pull the mount
	 * point information out of the zfs properties.
	 */
	be_node->be_mounted = zfs_is_mounted(zhp,
	    &(be_node->be_mntpt));
	if (!be_node->be_mounted) {
		err = zfs_prop_get(zhp, ZFS_PROP_MOUNTPOINT, prop_buf,
		    ZFS_MAXPROPLEN, NULL, NULL, 0, B_FALSE);
		if (err)
			be_node->be_mntpt = NULL;
		else
			be_node->be_mntpt = strdup(prop_buf);
	}

	be_node->be_node_creation = (time_t)zfs_prop_get_int(zhp,
	    ZFS_PROP_CREATION);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_node_data: get creation time failed (%d)\n"), err);
		return (err);
	}

	/* Get all user properties used for libbe */
	if ((userprops = zfs_get_user_props(zhp)) == NULL) {
		be_node->be_policy_type = strdup(be_default_policy());
	} else {
		if (nvlist_lookup_nvlist(userprops, BE_POLICY_PROPERTY,
		    &propval) != 0 || propval == NULL) {
			be_node->be_policy_type =
			    strdup(be_default_policy());
		} else {
			verify(nvlist_lookup_string(propval, ZPROP_VALUE,
			    &prop_str) == 0);
			if (prop_str == NULL || strcmp(prop_str, "-") == 0 ||
			    strcmp(prop_str, "") == 0)
				be_node->be_policy_type =
				    strdup(be_default_policy());
			else
				be_node->be_policy_type = strdup(prop_str);
		}

		if (nvlist_lookup_nvlist(userprops, BE_UUID_PROPERTY, &propval)
		    == 0 && nvlist_lookup_string(propval, ZPROP_VALUE,
		    &prop_str) == 0) {
			be_node->be_uuid_str = strdup(prop_str);
		}
	}

	/*
	 * Increment the dataset counter to include the root dataset
	 * of the BE.
	 */
	be_node->be_node_num_datasets++;

	return (err);
}

/*
 * Function:	be_get_ds_data
 * Description:	Helper function used by be_add_children_callback to collect
 *		the dataset related information that will be returned by
 *		be_list.
 * Parameters:
 *		zhp - Handle to the zfs dataset whose information we're
 *		      collecting.
 *		name - The name of the dataset we're processing.
 *		dataset - A pointer to the be_dataset_list structure
 *			  we're filling in.
 *		node - The node structure that this dataset belongs to.
 * Return:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_get_ds_data(
	zfs_handle_t *zfshp,
	char *name,
	be_dataset_list_t *dataset,
	be_node_list_t *node)
{
	char			prop_buf[ZFS_MAXPROPLEN];
	nvlist_t		*propval = NULL;
	nvlist_t		*userprops = NULL;
	char			*prop_str = NULL;
	int			err = 0;

	if (zfshp == NULL || name == NULL || dataset == NULL || node == NULL) {
		be_print_err(gettext("be_get_ds_data: invalid arguments, "
		    "can not be NULL\n"));
		return (BE_ERR_INVAL);
	}

	errno = 0;

	dataset->be_dataset_name = strdup(name);
	if ((err = errno) != 0) {
		be_print_err(gettext("be_get_ds_data: failed to copy "
		    "dataset name\n"));
		return (errno_to_be_err(err));
	}

	dataset->be_ds_space_used = zfs_prop_get_int(zfshp, ZFS_PROP_USED);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_ds_data: get space used failed (%d)\n"), err);
		return (err);
	}

	/*
	 * If the dataset is mounted use the mount point
	 * returned from the zfs_is_mounted call. If the
	 * dataset is not mounted then pull the mount
	 * point information out of the zfs properties.
	 */
	if (!(dataset->be_ds_mounted = zfs_is_mounted(zfshp,
	    &(dataset->be_ds_mntpt)))) {
		err = zfs_prop_get(zfshp, ZFS_PROP_MOUNTPOINT,
		    prop_buf, ZFS_MAXPROPLEN, NULL, NULL, 0,
		    B_FALSE);
		if (err != 0)
			dataset->be_ds_mntpt = NULL;
		else
			dataset->be_ds_mntpt = strdup(prop_buf);
	}
	dataset->be_ds_creation =
	    (time_t)zfs_prop_get_int(zfshp, ZFS_PROP_CREATION);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_ds_data: get creation time failed (%d)\n"), err);
		return (err);
	}

	/*
	 * Get the user property used for the libbe
	 * cleaup policy
	 */
	if ((userprops = zfs_get_user_props(zfshp)) == NULL) {
		dataset->be_ds_plcy_type =
		    strdup(node->be_policy_type);
	} else {
		if (nvlist_lookup_nvlist(userprops,
		    BE_POLICY_PROPERTY, &propval) != 0 ||
		    propval == NULL) {
			dataset->be_ds_plcy_type =
			    strdup(node->be_policy_type);
		} else {
			verify(nvlist_lookup_string(propval,
			    ZPROP_VALUE, &prop_str) == 0);
			if (prop_str == NULL ||
			    strcmp(prop_str, "-") == 0 ||
			    strcmp(prop_str, "") == 0)
				dataset->be_ds_plcy_type
				    = strdup(node->be_policy_type);
			else
				dataset->be_ds_plcy_type = strdup(prop_str);
		}
	}

	node->be_node_num_datasets++;
	return (err);
}

/*
 * Function:	be_get_ss_data
 * Description: Helper function used by be_add_children_callback to collect
 *		the dataset related information that will be returned by
 *		be_list.
 * Parameters:
 *		zhp - Handle to the zfs snapshot whose information we're
 *		      collecting.
 *		name - The name of the snapshot we're processing.
 *		shapshot - A pointer to the be_snapshot_list structure
 *			   we're filling in.
 *		node - The node structure that this snapshot belongs to.
 * Returns:
 *		0 - Success
 *		be_errno_t - Failure
 * Scope:
 *		Private
 */
static int
be_get_ss_data(
	zfs_handle_t *zfshp,
	char *name,
	be_snapshot_list_t *snapshot,
	be_node_list_t *node)
{
	nvlist_t	*propval = NULL;
	nvlist_t	*userprops = NULL;
	char		*prop_str = NULL;
	int		err = 0;

	if (zfshp == NULL || name == NULL || snapshot == NULL || node == NULL) {
		be_print_err(gettext("be_get_ss_data: invalid arguments, "
		    "can not be NULL\n"));
		return (BE_ERR_INVAL);
	}

	errno = 0;

	snapshot->be_snapshot_name = strdup(name);
	if ((err = errno) != 0) {
		be_print_err(gettext("be_get_ss_data: failed to copy name\n"));
		return (errno_to_be_err(err));
	}

	snapshot->be_snapshot_creation = (time_t)zfs_prop_get_int(zfshp,
	    ZFS_PROP_CREATION);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_ss_data: get creation "
		    "time failed (%d)\n"), err);
		return (err);
	}

	/*
	 * Try to get this snapshot's cleanup policy from its
	 * user properties first.  If not there, use default
	 * cleanup policy.
	 */
	if ((userprops = zfs_get_user_props(zfshp)) != NULL &&
	    nvlist_lookup_nvlist(userprops, BE_POLICY_PROPERTY,
	    &propval) == 0 && nvlist_lookup_string(propval,
	    ZPROP_VALUE, &prop_str) == 0) {
		snapshot->be_snapshot_type =
		    strdup(prop_str);
	} else {
		snapshot->be_snapshot_type =
		    strdup(be_default_policy());
	}

	snapshot->be_snapshot_space_used = zfs_prop_get_int(zfshp,
	    ZFS_PROP_USED);
	if ((err = zfs_err_to_be_err(g_zfs)) != 0) {
		be_print_err(gettext(
		    "be_get_ss_data: get space "
		    "used failed (%d)\n"), err);
		return (err);
	}
	node->be_node_num_snapshots++;
	return (err);
}

/*
 * Function:	be_list_alloc
 * Description: Helper function used to allocate memory for the various
 *		sructures that make up a BE node.
 * Parameters:
 *		err - Used to return any errors encountered.
 *			BE_SUCCESS - Success
 *			BE_ERR_NOMEM - Allocation failure
 *		size - The size of memory to allocate.
 * Returns:
 *		Success - A pointer to the allocated memory
 * 		Failure - NULL
 * Scope:
 *		Private
 */
static void*
be_list_alloc(int *err, size_t size)
{
	void *bep = NULL;

	bep = calloc(1, size);
	if (bep == NULL) {
		be_print_err(gettext("be_list_alloc: memory "
		    "allocation failed\n"));
		*err = BE_ERR_NOMEM;
	}
	*err = BE_SUCCESS;
	return (bep);
}
