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
 * Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
 */

/*
 * ZFS Pools discovery for Target Discovery module
 */
#include <unistd.h>
#include <libnvpair.h>
#include <strings.h>
#include <td_lib.h>
#include <td_api.h>
#include <ls_api.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <libdiskmgt.h>

#include <td_dd.h>
#include <td_zpool.h>

/* Library wide variables */
static libzfs_handle_t *g_zfs;
static td_zpool_info_t *g_zpools_list = NULL;

static void td_zpool_info_list_release(td_zpool_info_t *list);
static ddm_handle_t *td_zpool_discover(int *nzpools);
static td_zpool_target_t *td_zpool_target_allocate(zpool_handle_t *zhp,
	nvlist_t *child, int *logcnt, int *errn, boolean_t do_logs,
	boolean_t is_spare);
static int td_zpool_iter_callback(zpool_handle_t *zhp, void *data);
static void td_zpool_info_list_add(td_zpool_info_t **list,
	td_zpool_info_t *new);
static void td_zpool_target_free(td_zpool_target_t *zt);
static void td_zpool_info_free(td_zpool_info_t *zi);
static void td_zpool_allocate_target_nvlist(td_zpool_target_t **zts,
	uint32_t num_nvtargets,
	nvlist_t *nvtarget,
	const char *attr_name,
	const char *attr_num,
	int *errn);
static nvlist_t *td_zpool_get_attributes(td_zpool_info_t *zi, int *errn);
static void td_zpool_target_print(td_zpool_target_t *zt,
	int depth, boolean_t is_spare);
static void td_zpool_info_print(td_zpool_info_t *zi, int num);
static void td_zpool_info_print_ptrs(td_zpool_info_t **ptrs);
static void td_zpool_info_print_list(td_zpool_info_t *start);
static ddm_handle_t *td_zpool_info_ptrs_to_ddm_handle(td_zpool_info_t **ptrs);
static td_zpool_info_t **td_zpool_info_get_ptrs(
	td_zpool_info_t *zpools_list, int *nzpools);
static void free_nvlist_array(nvlist_t **nv, int count);
static nvlist_t *allocate_target_nvlist(td_zpool_target_t *zt, int *errn);
static int td_zpool_import_find(libzfs_handle_t *zh,
	td_zpool_info_t **zi_list);
static int td_zpool_import_add(nvlist_t *pool,
	td_zpool_info_t **zi_list);

/*
 * *******************************************************************
 * Public Functions
 * *******************************************************************
 */

/*
 * Function:	ddm_free_zpool_list()
 *
 * Description:	Release zpool list for td_mg.c
 *
 * Parameters:
 *		ddm_handle_t *dh : Handler list to free
 *
 * Returns:
 *		Nothing
 *
 * Scope:
 * 		Public
 */
void
ddm_free_zpool_list(ddm_handle_t *dh)
{
	free(dh);
	td_zpool_info_list_release(g_zpools_list);
	g_zpools_list = NULL;
}

/*
 * Function:	ddm_get_zpools()
 *
 * Description:	Get zpool list for td_mg.c
 *
 * Parameters:
 *		int *nzpools	: Container for number of zpools
 *
 * Returns:
 *		ddm_handle_t *	: Array of zpools handles discovered
 *		int *nzpools	: Sets to number of zpools found
 *
 * Scope:
 *		Public
 */
ddm_handle_t *
ddm_get_zpools(int *nzpools)
{
	ddm_handle_t	*dh;

	/* Initialize number of zpools found to 0 */
	if (nzpools != NULL)
		*nzpools = 0;

	DDM_DEBUG(DDM_DBGLVL_NOTICE, "%s", "-> ddm_get_zpools()\n");

	dh = (ddm_handle_t *)td_zpool_discover(nzpools);

	if (dh == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "Can't get zpool info\n");
	}

	return (dh);
}

/*
 * Function:	ddm_get_zpool_attributes()
 *
 * Description:	Get attributes of Zpools.
 *
 * Parameters:
 *		ddm_handle_t zpool : zpool handle to get attributes for
 *
 * Returns:
 *		nvlist_t pointer containing attributes
 *
 * Scope:
 *		Public
 */
nvlist_t *
ddm_get_zpool_attributes(ddm_handle_t zpool)
{
	td_zpool_info_t *zi;
	nvlist_t *attrs;
	int errn = 0;

	zi = (td_zpool_info_t *)(uintptr_t)zpool;

	attrs = td_zpool_get_attributes(zi, &errn);
	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_zpool_attributes():"
		    " Can't get attr. for Zpool, err=%d\n", errn);
		return (NULL);
	}

	return (attrs);
}

/*
 * ********************************************************************
 * Private Functions
 * ********************************************************************
 */

/*
 * Function:	td_zpool_info_list_release()
 *
 * Description:	Release all internally allocated memory for
 *      	already discovered zpools
 *
 * Parameters:
 *		td_zpool_info_t *list : Internal linked list to be freed
 *
 * Returns:
 *		void
 *
 * Scope:
 *		Private
 */
static void
td_zpool_info_list_release(td_zpool_info_t *list)
{
	td_zpool_info_t *cur;
	td_zpool_info_t *tofree;

	if (list == NULL) {
		return;
	}

	for (cur = list; cur != NULL; ) {
		tofree = cur;
		cur = cur->next;
		td_zpool_info_free(tofree);
	}
}

/*
 * Function:	td_zpool_discover()
 *
 * Description: Discover zpools in the system by using libzfs's
 * 		zpool_iter() function. The attributes of the zpools are
 * 		stored in the linked list of td_zpool_info_t.
 *
 * Parameters:
 *		int *nzpools	: Return number of zpools found
 *
 * Returns:
 *		ddm_handle_t *	: Array of ddm_handle_t for all pools
 *		int *nzpools	: Number of zpools discovered
 *
 * Scope:
 *		Private
 */
static ddm_handle_t *
td_zpool_discover(int *nzpools)
{
	ddm_handle_t *df = NULL;
	td_zpool_info_t **zpools_ptrs = NULL;

	/* Initialize libzfs handle */
	if ((g_zfs = libzfs_init()) == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_discover():"
		    " failed to initialize ZFS library\n");
		return (NULL);
	}

	if (g_zpools_list != NULL) {
		td_zpool_info_list_release(g_zpools_list);
		g_zpools_list = NULL;
	}

	if ((zpool_iter(g_zfs, td_zpool_iter_callback, &g_zpools_list)) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_discover()"
		    " failed to iterate zpools\n");
		libzfs_fini(g_zfs);
		return (NULL);
	}

	if ((td_zpool_import_find(g_zfs, &g_zpools_list)) == 0) {
		zpools_ptrs = td_zpool_info_get_ptrs(g_zpools_list, nzpools);
		td_zpool_info_print_list(g_zpools_list);
		td_zpool_info_print_ptrs(zpools_ptrs);
		df = td_zpool_info_ptrs_to_ddm_handle(zpools_ptrs);
		free(zpools_ptrs);
	} else {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_discover()"
		    " failed to iterate import candidates\n");
		libzfs_fini(g_zfs);
		return (NULL);
	}

	libzfs_fini(g_zfs);

	return (df);
}

/*
 * Function: td_zpool_target_allocate
 *
 * Description: Allocate a td_zpool_target_t for target if
 *		this target has children recursively call this function
 *		to allocate further targets.
 *
 * Parameters:
 *		zpool_handle_t *zhp	: zpool handle
 *		nvlist_t *child		: nvlist for this target
 *		int *logcnt   		: Return log count
 *		int  *errn  		: Return error number
 *		boolean_t  do_logs	: Process logs or not
 *		boolean_t  is_spare	: Is this a spare
 *
 * Returns:
 *		td_zpool_target_t *	: Allocated td_zpool_target_t
 *
 * Scope:
 * 		Private
 */
static td_zpool_target_t *
td_zpool_target_allocate(zpool_handle_t *zhp,
	nvlist_t *child,
	int *logcnt,
	int *errn,
	boolean_t do_logs,
	boolean_t is_spare)
{
	nvlist_t **nvchild;
	td_zpool_target_t *top_target = NULL;
	char *vname;
	uint_t vsc;
	vdev_stat_t *vs;
	uint64_t islog = B_FALSE;
	uint64_t ishole = B_FALSE;
	int cnt1 = 0;

	*errn = 0;

	/*
	 * Determine if this target device is a ZFS Log or a ZFS Hole.
	 * If a ZFS Log device and we do not want to process logs then
	 * return NULL.
	 * ZFS Holes occur when you remove a slog after having add more
	 * stripes, we always want to ignore these.
	 */
	(void) nvlist_lookup_uint64(child, ZPOOL_CONFIG_IS_LOG, &islog);
	(void) nvlist_lookup_uint64(child, ZPOOL_CONFIG_IS_HOLE, &ishole);

	if (ishole) {
		return (NULL);
	}

	if (islog) {
		*logcnt = *logcnt + 1;
		if (!do_logs) {
			return (NULL);
		}
	} else {
		if (do_logs) {
			return (NULL);
		}
	}

	top_target = calloc(1, sizeof (td_zpool_target_t));
	if (top_target == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_target_allocate():"
		    " failed to allocate memory for top target,"
		    " err=%d\n", ENOMEM);
		*errn = ENOMEM;
		return (NULL);
	}

	vname = zpool_vdev_name(g_zfs, zhp, child, B_TRUE);
	if (vname == NULL) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_target_allocate():"
		    " failed to get device name\n");
		td_debug_print(LS_DBGLVL_WARN,
		    "%d : %s\n", libzfs_errno(g_zfs),
		    libzfs_error_description(g_zfs));
		td_zpool_target_free(top_target);
		*errn = -1;
		return (NULL);
	}
	top_target->name = strdup(vname);

	if (nvlist_lookup_uint64_array(child,
	    ZPOOL_CONFIG_VDEV_STATS,
	    (uint64_t **)&vs, &vsc) != 0) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_target_allocate():"
		    " failed to get device stats\n");
		top_target->health = strdup("UNKNOWN");
		top_target->read_errors = 0;
		top_target->write_errors = 0;
		top_target->checksum_errors = 0;
	} else {
		if (is_spare) {
			if (vs->vs_aux == VDEV_AUX_SPARED) {
				top_target->health = strdup("INUSE");
			} else if (vs->vs_state == VDEV_STATE_HEALTHY) {
				top_target->health = strdup("AVAIL");
			} else {
				top_target->health = zpool_state_to_name(
				    vs->vs_state, vs->vs_aux);
			}
			top_target->read_errors = 0;
			top_target->write_errors = 0;
			top_target->checksum_errors = 0;
		} else {
			top_target->health =
			    zpool_state_to_name(vs->vs_state, vs->vs_aux);
			top_target->read_errors = vs->vs_read_errors;
			top_target->write_errors = vs->vs_write_errors;
			top_target->checksum_errors = vs->vs_checksum_errors;
		}
	}

	top_target->num_targets = 0;
	(void) nvlist_lookup_nvlist_array(child,
	    ZPOOL_CONFIG_CHILDREN,
	    &nvchild, &top_target->num_targets);

	if (top_target->num_targets > 0) {
		top_target->targets =
		    calloc(top_target->num_targets,
		    sizeof (td_zpool_target_t *));
		if (top_target->targets == NULL) {
			td_debug_print(LS_DBGLVL_ERR,
			    "td_zpool_target_allocate():"
			    " failed to allocate memory for targets,"
			    " err=%d\n", ENOMEM);
			*errn = ENOMEM;
			top_target->num_targets = 0;
			td_zpool_target_free(top_target);
			return (NULL);
		}

		for (cnt1 = 0; cnt1 < top_target->num_targets; cnt1++) {
			top_target->targets[cnt1] =
			    td_zpool_target_allocate(zhp, nvchild[cnt1],
			    logcnt, errn, B_FALSE, is_spare);

			if (*errn != 0) {
				td_debug_print(LS_DBGLVL_ERR,
				    "td_zpool_target_allocate():"
				    " failed to allocate memory for targets,"
				    " err=%d\n", *errn);
				/* Free any previously allocated targets */
				td_zpool_target_free(top_target);
				return (NULL);
			}
		}
	} else {
		top_target->targets = NULL;
	}

	return (top_target);
}


/*
 * Function: td_zpool_import_add
 *
 * Description: Found importable zpool, generate zpool_info_t structure
 *		and add to linked list of discovered zpools.
 *
 * Parameters:
 *		nvlist_t *pool          	: nvlist of importable pool
 *		td_zpool_info_t *zi_list	: td_zpool_info_t linked list
 *
 * Returns:
 *		0	: Success
 *		1	: Failure
 *
 * Scope:
 * 		Private
 */
static int
td_zpool_import_add(nvlist_t *pool, td_zpool_info_t **zi_list)
{
	td_zpool_info_t *list = *zi_list;
	int cnt1 = 0, logcnt = 0;
	uint32_t targetcnt = 0;
	nvlist_t **l2cache, **spares;
	uint_t nl2cache, nspares;
	char *msgid;
	nvlist_t *nvroot, **child;
	uint32_t num_children = 0;
	uint_t vsc;
	vdev_stat_t *vs;
	td_zpool_info_t *zi = NULL;
	char *name;
	uint64_t guid;

	/* name */
	if (nvlist_lookup_string(pool, ZPOOL_CONFIG_POOL_NAME, &name) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to get pool name.\n");
		return (1);
	}

	/* GUID */
	if (nvlist_lookup_uint64(pool, ZPOOL_CONFIG_POOL_GUID, &guid) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to get pool GUID.\n");
		return (1);
	}

	/* VDEV Tree */
	if (nvlist_lookup_nvlist(pool,
	    ZPOOL_CONFIG_VDEV_TREE, &nvroot) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to get vdev tree\n");
		return (1);
	}

	/* VDEV STATS */
	if (nvlist_lookup_uint64_array(nvroot, ZPOOL_CONFIG_VDEV_STATS,
	    (uint64_t **)&vs, &vsc) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to get vdev stats\n");
		return (1);
	}

	/* Construct td_zpool_info_t of attributes for this zpool */
	zi = calloc(1, sizeof (td_zpool_info_t));
	if (zi == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to allocate memory for zpool,"
		    " err=%d\n", ENOMEM);
		return (1);
	}

	zi->attributes.name = strdup(name);
	zi->attributes.health =
	    zpool_state_to_name(vs->vs_state, vs->vs_aux);
	zi->attributes.status = zpool_import_status(pool, &msgid);
	zi->attributes.guid = guid;
	zi->attributes.size = 0;
	zi->attributes.capacity = 0;
	zi->attributes.version = 0;
	zi->attributes.bootfs = NULL;

	/* Import or not */
	/* As this zpool was reported via import search it is an import */
	zi->attributes.import = B_TRUE;


	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_CHILDREN,
	    &child, &num_children) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to traverse vdev tree\n");
		td_zpool_info_free(zi);
		return (1);
	}

	zi->attributes.targets =
	    calloc(num_children,
	    sizeof (td_zpool_target_t *));

	if (zi->attributes.targets == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
		    " failed to allocate memory for toplevel targets,"
		    " err=%d\n", ENOMEM);
		td_zpool_info_free(zi);
		return (1);
	}

	/* Process all normal non log/hole targets */
	logcnt = 0;
	targetcnt = 0;
	for (cnt1 = 0; cnt1 < num_children; cnt1++) {
		int errn = 0;
		td_zpool_target_t *zt =
		    td_zpool_target_allocate(NULL, child[cnt1],
		    &logcnt, &errn, B_FALSE, B_FALSE);

		if (errn != 0) {
			/* Error already written via td_debug_print() */
			/* So just return error from iter function */
			td_zpool_info_free(zi);
			return (1);
		}

		if (zt != NULL) {
			zi->attributes.targets[targetcnt++] = zt;
		}
	}
	zi->attributes.num_targets = targetcnt;

	/* Process all logs and add them as targets */
	if (logcnt > 0) {
		zi->attributes.num_logs = logcnt;
		zi->attributes.logs =
		    calloc(zi->attributes.num_logs,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.logs == NULL) {
			td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
			    " failed to allocate memory for zpool logs,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < num_children; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(NULL, child[cnt1],
			    &dummycnt, &errn, B_TRUE, B_FALSE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.logs[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_logs = 0;
		zi->attributes.logs = NULL;
	}


	/* Process All Cache and add them as targets */
	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_L2CACHE,
	    &l2cache, &nl2cache) == 0) {
		zi->attributes.num_l2cache = nl2cache;
		zi->attributes.l2cache =
		    calloc(zi->attributes.num_l2cache,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.l2cache == NULL) {
			td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
			    " failed to allocate memory for zpool cache,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < zi->attributes.num_l2cache; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(NULL, l2cache[cnt1],
			    &dummycnt, &errn, B_FALSE, B_FALSE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.l2cache[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_l2cache = 0;
		zi->attributes.l2cache = NULL;
	}

	/* Process All spares and add them as targets */
	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_SPARES,
	    &spares, &nspares) == 0) {
		zi->attributes.num_spares = nspares;
		zi->attributes.spares =
		    calloc(zi->attributes.num_spares,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.spares == NULL) {
			td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_add():"
			    " failed to allocate memory for zpool spares,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < zi->attributes.num_spares; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(NULL, spares[cnt1],
			    &dummycnt, &errn, B_FALSE, B_TRUE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.spares[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_spares = 0;
		zi->attributes.spares = NULL;
	}

	td_zpool_info_list_add(&list, zi);
	if (*zi_list == NULL) {
		*zi_list = list;
	}
	return (0);
}

/*
 * Function: td_zpool_import_find
 *
 * Description: Find all importable zpools currently not imported.
 *		Equivalent to calling CLI "zpool import" with no arguments.
 *
 * Parameters:
 *		libzfs_handle_t *zh	: libzfs handle
 *
 * Returns:
 *		0	: Success
 *		1	: Fail
 *
 * Scope:
 * 		Private
 */
static int
td_zpool_import_find(libzfs_handle_t *zh, td_zpool_info_t **zi_list)
{
	char **searchdirs = NULL;
	importargs_t idata = { 0 };
	nvlist_t *nv_pools = NULL;
	nvpair_t *elem;
	nvlist_t *config;
	uint64_t pool_state = -1ULL;

	searchdirs = calloc(1, sizeof (char *));

	if (searchdirs == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_import_find():"
		    " failed to allocate memory for import search path,"
		    " err=%d\n", ENOMEM);
		return (1);
	}

	searchdirs[0] = "/dev/dsk";

	idata.path = searchdirs;
	idata.paths = 1;
	idata.poolname = NULL;
	idata.guid = 0;
	idata.cachefile = NULL;

	nv_pools = zpool_search_import(zh, &idata);

	if (nv_pools != NULL) {
		elem = NULL;
		while ((elem = nvlist_next_nvpair(nv_pools, elem)) != NULL) {
			if (nvpair_value_nvlist(elem, &config) != 0) {
				td_debug_print(LS_DBGLVL_WARN,
				    "td_zpool_import_find():"
				    " nvpair_value_nvlist failed.\n");
				printf("nvpair_valu_nvlist failed\n");
				continue;
			}
			if (nvlist_lookup_uint64(config,
			    ZPOOL_CONFIG_POOL_STATE, &pool_state) != 0) {
				td_debug_print(LS_DBGLVL_WARN,
				    "td_zpool_import_find():"
				    " failed to get pool state.\n");
				printf("pool state failed\n");
				continue;
			}

			if (pool_state == POOL_STATE_DESTROYED) {
				printf("pool is destroyed\n");
				td_debug_print(LS_DBGLVL_INFO,
				    "td_zpool_import_find():"
				    " Skipping destroyed pool.\n");
				continue;
			}

			if (td_zpool_import_add(config, zi_list) != 0) {
				free(searchdirs);
				return (1);
			}
		}
	}

	free(searchdirs);
	return (0);
}

/*
 * Function: td_zpool_iter_callback
 *
 * Description: Callback triggered by zpool_iter(), called for
 *		each zpool discovered, pool is queried for various
 *		properties and vdev structure, and results are stored
 *		in internal linked list of td_zpool_info_t's.
 *
 * Parameters:
 *		zpool_handle_t *zlp	: Current zpool handler
 *		void *data      	: List of discovered zpools
 *
 * Returns:
 *		0 : Success
 *		1 : Fail
 *
 * Scope:
 * 		Private
 */
static int
td_zpool_iter_callback(zpool_handle_t *zhp, void *data)
{
	td_zpool_info_t **_list = data;
	td_zpool_info_t *list = *_list;
	char prop_buf[ZFS_MAXPROPLEN];
	td_zpool_info_t *zi = NULL;
	char *status;
	nvlist_t *config, *nvroot, **child;
	int cnt1 = 0, logcnt = 0, targetcnt = 0;
	uint_t vsc;
	vdev_stat_t *vs;
	nvlist_t **l2cache, **spares;
	uint_t nl2cache, nspares;
	uint32_t num_children = 0;

	/* Construct td_zpool_info_t of attributes for this zpool */
	zi = calloc(1, sizeof (td_zpool_info_t));
	if (zi == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_iter_callback():"
		    " failed to allocate memory for zpool,"
		    " err=%d\n", ENOMEM);
		return (1);
	}

	/* name */
	zi->attributes.name = strdup(zpool_get_name(zhp));
	if (zi->attributes.name == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_iter_callback():"
		    " failed to get pool name\n");
		td_zpool_info_free(zi);
		return (0);
	}

	/* Pool status */
	zi->attributes.status = zpool_get_status(zhp, &status);

	/* GUID */
	zi->attributes.guid = zpool_get_prop_int(zhp, ZPOOL_PROP_GUID, NULL);

	/* Health */
	zpool_get_prop(zhp, ZPOOL_PROP_HEALTH, prop_buf, ZFS_MAXPROPLEN, NULL);
	if (prop_buf == NULL) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to get health property for pool: %s\n",
		    zi->attributes.name);
		zi->attributes.health = strdup("UNKNOWN");
	} else {
		zi->attributes.health = strdup(prop_buf);
	}

	/* Pool size */
	zi->attributes.size =
	    zpool_get_prop_int(zhp, ZPOOL_PROP_SIZE, NULL);

	/* Pool capacity */
	zi->attributes.capacity =
	    zpool_get_prop_int(zhp, ZPOOL_PROP_CAPACITY, NULL);

	/* Pool version */
	zi->attributes.version =
	    zpool_get_prop_int(zhp, ZPOOL_PROP_VERSION, NULL);

	/* Import or not */
	/* As this zpool was reported via zpool_iter, not an import */
	zi->attributes.import = B_FALSE;

	/* Get vdev configuration for this pool */
	if ((config = zpool_get_config(zhp, NULL)) == NULL) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to get pool configuration for pool : %s\n",
		    zi->attributes.name);
		td_debug_print(LS_DBGLVL_WARN,
		    "%d : %s\n", libzfs_errno(g_zfs),
		    libzfs_error_description(g_zfs));
		goto add_pool;
	}

	/* Boot Filesystem */
	zpool_get_prop(zhp, ZPOOL_PROP_BOOTFS, prop_buf, ZFS_MAXPROPLEN, NULL);
	if (prop_buf == NULL) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to get boot filesystem property for pool: %s\n",
		    zi->attributes.name);
		zi->attributes.bootfs = NULL;
	} else {
		zi->attributes.bootfs = strdup(prop_buf);
	}

	if (nvlist_lookup_nvlist(config,
	    ZPOOL_CONFIG_VDEV_TREE, &nvroot) != 0) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to get vdev tree\n");
		goto add_pool;
	}

	if (nvlist_lookup_uint64_array(nvroot, ZPOOL_CONFIG_VDEV_STATS,
	    (uint64_t **)&vs, &vsc) != 0) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to get vdev stats\n");
		goto add_pool;
	}

	/* State reported via VDEV_STATS is more accurate, replace */
	free(zi->attributes.health);
	zi->attributes.health =
	    zpool_state_to_name(vs->vs_state, vs->vs_aux);

	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_CHILDREN,
	    &child, &num_children) != 0) {
		td_debug_print(LS_DBGLVL_WARN, "td_zpool_iter_callback():"
		    " failed to traverse vdev tree\n");
		goto add_pool;
	}

	zi->attributes.targets =
	    calloc(num_children,
	    sizeof (td_zpool_target_t *));

	if (zi->attributes.targets == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_iter_callback():"
		    " failed to allocate memory for toplevel targets,"
		    " err=%d\n", ENOMEM);
		td_zpool_info_free(zi);
		return (1);
	}

	/* Process all normal non log/hole targets */
	logcnt = 0;
	targetcnt = 0;
	for (cnt1 = 0; cnt1 < num_children; cnt1++) {
		int errn = 0;
		td_zpool_target_t *zt =
		    td_zpool_target_allocate(zhp, child[cnt1],
		    &logcnt, &errn, B_FALSE, B_FALSE);

		if (errn != 0) {
			/* Error already written via td_debug_print() */
			/* So just return error from iter function */
			td_zpool_info_free(zi);
			return (1);
		}

		if (zt != NULL) {
			zi->attributes.targets[targetcnt++] = zt;
		}
	}
	zi->attributes.num_targets = (uint32_t)targetcnt;

	/* Process all logs and add them as targets */
	if (logcnt > 0) {
		zi->attributes.num_logs = logcnt;
		zi->attributes.logs =
		    calloc(zi->attributes.num_logs,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.logs == NULL) {
			td_debug_print(LS_DBGLVL_ERR,
			    "td_zpool_iter_callback():"
			    " failed to allocate memory for zpool logs,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < num_children; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(zhp, child[cnt1],
			    &dummycnt, &errn, B_TRUE, B_FALSE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.logs[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_logs = 0;
		zi->attributes.logs = NULL;
	}


	/* Process All Cache and add them as targets */
	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_L2CACHE,
	    &l2cache, &nl2cache) == 0) {
		zi->attributes.num_l2cache = nl2cache;
		zi->attributes.l2cache =
		    calloc(zi->attributes.num_l2cache,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.l2cache == NULL) {
			td_debug_print(LS_DBGLVL_ERR,
			    "td_zpool_iter_callback():"
			    " failed to allocate memory for zpool cache,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < zi->attributes.num_l2cache; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(zhp, l2cache[cnt1],
			    &dummycnt, &errn, B_FALSE, B_FALSE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.l2cache[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_l2cache = 0;
		zi->attributes.l2cache = NULL;
	}

	/* Process All spares and add them as targets */
	if (nvlist_lookup_nvlist_array(nvroot, ZPOOL_CONFIG_SPARES,
	    &spares, &nspares) == 0) {
		zi->attributes.num_spares = nspares;
		zi->attributes.spares =
		    calloc(zi->attributes.num_spares,
		    sizeof (td_zpool_target_t *));
		if (zi->attributes.spares == NULL) {
			td_debug_print(LS_DBGLVL_ERR,
			    "td_zpool_iter_callback():"
			    " failed to allocate memory for zpool spares,"
			    " err=%d\n", ENOMEM);
			td_zpool_info_free(zi);
			return (1);
		}

		targetcnt = 0;
		for (cnt1 = 0; cnt1 < zi->attributes.num_spares; cnt1++) {
			int errn = 0;
			int dummycnt;
			td_zpool_target_t *zt =
			    td_zpool_target_allocate(zhp, spares[cnt1],
			    &dummycnt, &errn, B_FALSE, B_TRUE);

			if (errn != 0) {
				/* Error already written via td_debug_print() */
				/* So just return error from iter function */
				td_zpool_info_free(zi);
				return (1);
			}

			if (zt != NULL) {
				zi->attributes.spares[targetcnt++] = zt;
			}
		}
	} else {
		zi->attributes.num_spares = 0;
		zi->attributes.spares = NULL;
	}

add_pool:
	td_zpool_info_list_add(&list, zi);
	if (*_list == NULL) {
		*_list = list;
	}
	zpool_close(zhp);
	return (0);
}

/*
 * Function: td_zpool_info_list_add
 *
 * Description: Adds a new td_zpool_info to global linked list of discovered
 *		zpools.
 *
 * Parameters:
 *		td_zpool_info_t **list	: List to add new item to
 *		td_zpool_info_t *new	: New zpool to add to linked list
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_info_list_add(td_zpool_info_t **list, td_zpool_info_t *new)
{
	td_zpool_info_t *cur;

	if (new == NULL)
		return;

	if (*list == NULL) {
		/* First item on list */
		*list = new;
	} else {
		/* Traverse to end of list and add item */
		for (cur = *list; cur->next != NULL; cur = cur->next)
			;

		/* Add new td_zpool_info to end of list */
		cur->next = new;
	}
}


/*
 * Function: td_zpool_target_free
 *
 * Description: Frees memory allocated for td_zpool_target_t
 *
 * Parameters:
 *		td_zpool_target_t *zt : td_zpool_target_t to be freed
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_target_free(td_zpool_target_t *zt)
{
	int i = 0;

	if (zt == NULL) {
		return;
	}

	for (i = 0; i < zt->num_targets; i++) {
		td_zpool_target_free(zt->targets[i]);
	}
	free(zt->targets);
	free(zt->name);
	free(zt->health);
	free(zt);
}

/*
 * Function: td_zpool_info_free
 *
 * Description: Frees memory allocated for td_zpool_info
 *
 * Parameters:
 *		td_zpool_info_t *zi : td_zpool_info_t to be freed
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_info_free(td_zpool_info_t *zi)
{
	int i = 0;

	if (zi == NULL) {
		return;
	}

	/* Free all targets */
	for (i = 0; i < zi->attributes.num_targets; i++) {
		td_zpool_target_free(zi->attributes.targets[i]);
	}
	free(zi->attributes.targets);

	/* Free all logs */
	for (i = 0; i < zi->attributes.num_logs; i++) {
		td_zpool_target_free(zi->attributes.logs[i]);
	}
	free(zi->attributes.logs);

	/* Free all l2cache */
	for (i = 0; i < zi->attributes.num_l2cache; i++) {
		td_zpool_target_free(zi->attributes.l2cache[i]);
	}
	free(zi->attributes.l2cache);

	/* Free all spares */
	for (i = 0; i < zi->attributes.num_spares; i++) {
		td_zpool_target_free(zi->attributes.spares[i]);
	}
	free(zi->attributes.spares);

	free(zi->attributes.name);
	free(zi->attributes.health);
	free(zi->attributes.bootfs);
	free(zi);
}
/*
 * Function: free_nvlist_array
 *
 * Description: Frees all elements of an nvlist array and the
 *		main array pointer itself.
 *
 * Parameters:
 *		nvlist **nv : nvlist_t array to free
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
free_nvlist_array(nvlist_t **nv, int count)
{
	int i = 0;

	if (nv == NULL) {
		return;
	}

	for (i = 0; i < count; i++) {
		nvlist_free(nv[i]);
	}
	free(nv);
}

/*
 * Function: td_zpool_allocate_target_nvlist
 *
 * Description: Allocates nvlist for this target.
 *		potentially called recursively to allocate targets
 *		of this target.
 *
 * Parameters:
 *		td_zpool_target_t **zts	: targets array
 *      	uint32_t num_nvtargets	: Number of targets
 *		nvlist_t *nvtarget  	: top level nvlist
 *      	const char *attr_name	: NV attribute name
 *      	const char *attr_num	: NV attribute number
 *		int *errn           	: Error number to return
 *
 * Returns:
 *		errn      		: sets to error value;
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_allocate_target_nvlist(td_zpool_target_t **zts,
	uint32_t num_nvtargets,
	nvlist_t *nvtarget,
	const char *attr_name,
	const char *attr_num,
	int *errn)
{
	int cnt1 = 0;
	uint32_t num_targets = 0;
	nvlist_t **targets;
	nvlist_t *tmptarget = NULL;

	if (num_nvtargets == 0) {
		return;
	}

	/* Generate nvlist array of each target grouping */
	targets = calloc(num_nvtargets, sizeof (nvlist_t *));
	if (targets == NULL) {
		td_debug_print(LS_DBGLVL_ERR,
		    "td_zpool_allocate_target_nvlist():"
		    " Failed to allocate target nvlist.\n");
		*errn = ENOMEM;
		return;
	}

	num_targets = 0;
	for (cnt1 = 0; cnt1 < num_nvtargets; cnt1++) {
		tmptarget = allocate_target_nvlist(zts[cnt1], errn);

		if (*errn != 0) {
			free_nvlist_array(targets, cnt1);
			return;
		}
		targets[num_targets++] = tmptarget;
	}

	/* Add TD_ZPOOL_ATTR_NUM_TARGETS attribute */
	if (nvlist_add_uint32(nvtarget,
	    attr_num, num_targets) != 0) {
		td_debug_print(LS_DBGLVL_ERR,
		    "td_zpool_allocate_target_nvlist():"
		    " Failed to add number of targets to target nvlist.\n");
		free_nvlist_array(targets, cnt1);
		*errn = ENOMEM;
		return;
	}

	/* Add TD_ZPOOL_ATTR_TARGETS attribute */
	if (nvlist_add_nvlist_array(nvtarget,
	    attr_name, targets,
	    num_targets) != 0) {
		td_debug_print(LS_DBGLVL_ERR,
		    "td_zpool_allocate_target_nvlist():"
		    " Failed to add targets to target nvlist.\n");
		free_nvlist_array(targets, cnt1);
		*errn = ENOMEM;
		return;
	}

	/* Free up targets nvlists */
	free_nvlist_array(targets, num_targets);
}

/*
 * Function: allocate_target_nvlist
 *
 * Description: Allocates nvlist for this target.
 *		potentially called recursively to allocate targets
 *		of this target.
 *
 * Parameters:
 *		td_zpool_target_t *zt	: td_zpool_target_t to allocate
 *		int *errn           	: Error number to return
 *
 * Returns:
 *		nvlist_t *      	: nvpair list of attributes
 *		errn            	: sets to error value;
 *
 * Scope:
 * 		Private
 */
static nvlist_t *
allocate_target_nvlist(td_zpool_target_t *zt, int *errn)
{
	nvlist_t *nvtarget = NULL;

	if (zt == NULL) {
		return (NULL);
	}

	/* Allocate NV_LIST for this target */
	if (nvlist_alloc(&nvtarget, NV_UNIQUE_NAME, 0) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to allocate target nvlist.\n");
		*errn = ENOMEM;
		return (NULL);
	}

	/* For each target build up nvlist */
	/* Add TD_ZPOOL_ATTR_TARGET_NAME attribute */
	if (nvlist_add_string(nvtarget,
	    TD_ZPOOL_ATTR_TARGET_NAME, zt->name) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add target name to nvlist.\n");
		nvlist_free(nvtarget);
		*errn = ENOMEM;
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_TARGET_HEALTH attribute */
	if (nvlist_add_string(nvtarget,
	    TD_ZPOOL_ATTR_TARGET_HEALTH, zt->health) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add target health to nvlist.\n");
		nvlist_free(nvtarget);
		*errn = ENOMEM;
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_TARGET_READ_ERRORS attribute */
	if (nvlist_add_uint64(nvtarget,
	    TD_ZPOOL_ATTR_TARGET_READ_ERRORS, zt->read_errors) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add target read errors to nvlist.\n");
		nvlist_free(nvtarget);
		*errn = ENOMEM;
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_TARGET_WRITE_ERRORS attribute */
	if (nvlist_add_uint64(nvtarget,
	    TD_ZPOOL_ATTR_TARGET_WRITE_ERRORS, zt->write_errors) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add target write errors to nvlist.\n");
		nvlist_free(nvtarget);
		*errn = ENOMEM;
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_TARGET_CHECKSUM_ERRORS attribute */
	if (nvlist_add_uint64(nvtarget,
	    TD_ZPOOL_ATTR_TARGET_CHECKSUM_ERRORS,
	    zt->checksum_errors) != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add target checksum errors to nvlist.\n");
		nvlist_free(nvtarget);
		*errn = ENOMEM;
		return (NULL);
	}

	td_zpool_allocate_target_nvlist(zt->targets,
	    zt->num_targets, nvtarget, TD_ZPOOL_ATTR_TARGETS,
	    TD_ZPOOL_ATTR_NUM_TARGETS, errn);
	if (*errn != 0) {
		td_debug_print(LS_DBGLVL_ERR, "allocate_target_nvlist():"
		    " Failed to add targets to nvlist.\n");
		nvlist_free(nvtarget);
		return (NULL);
	}

	return (nvtarget);
}

/*
 * Function: td_zpool_get_attributes
 *
 * Description: Gets the attributes of a specific Zpool.
 *		nvlist_t is populated with all the attributes for this
 *		td_zpool_info_t and returned.
 *
 * Parameters:
 *		td_zpool_info_t *zi	: zpool to get attributes for
 *		int *errn       	: Error number to return
 *
 * Returns:
 *		nvlist_t *      	: nvpair list of attributes for zpool
 *
 * Scope:
 * 		Private
 */
static nvlist_t *
td_zpool_get_attributes(td_zpool_info_t *zi, int *errn)
{
	nvlist_t *attrs = NULL;

	if (zi == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_get_attributes():"
		    " zpool handle not set.\n");
		*errn = ENODEV;
		return (NULL);
	}

	/* Allocate NV_LIST */
	if (nvlist_alloc(&attrs, NV_UNIQUE_NAME, 0) != 0) {
		*errn = ENOMEM;
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_NAME attribute */
	if (nvlist_add_string(attrs, TD_ZPOOL_ATTR_NAME,
	    zi->attributes.name) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_HEALTH attribute */
	if (nvlist_add_string(attrs, TD_ZPOOL_ATTR_HEALTH,
	    zi->attributes.health) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_STATUS attribute */
	if (nvlist_add_uint32(attrs, TD_ZPOOL_ATTR_STATUS,
	    zi->attributes.status) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_GUID attribute */
	if (nvlist_add_uint64(attrs, TD_ZPOOL_ATTR_GUID,
	    zi->attributes.guid) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_SIZE attribute */
	if (nvlist_add_uint64(attrs, TD_ZPOOL_ATTR_SIZE,
	    zi->attributes.size) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_CAPACITY attribute */
	if (nvlist_add_uint64(attrs, TD_ZPOOL_ATTR_CAPACITY,
	    zi->attributes.capacity) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_VERSION attribute */
	if (nvlist_add_uint32(attrs, TD_ZPOOL_ATTR_VERSION,
	    zi->attributes.version) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Add TD_ZPOOL_ATTR_BOOTFS attribute */
	if (zi->attributes.bootfs != NULL) {
		if (nvlist_add_string(attrs, TD_ZPOOL_ATTR_BOOTFS,
		    zi->attributes.bootfs) != 0) {
			*errn = ENOMEM;
			nvlist_free(attrs);
			return (NULL);
		}
	}

	/* Add TD_ZPOOL_ATTR_IMPORT attribute */
	if (nvlist_add_boolean_value(attrs, TD_ZPOOL_ATTR_IMPORT,
	    zi->attributes.import) != 0) {
		*errn = ENOMEM;
		nvlist_free(attrs);
		return (NULL);
	}

	/* Generate nvlist array of each target grouping */
	td_zpool_allocate_target_nvlist(zi->attributes.targets,
	    zi->attributes.num_targets, attrs, TD_ZPOOL_ATTR_TARGETS,
	    TD_ZPOOL_ATTR_NUM_TARGETS, errn);
	if (*errn != 0) {
		nvlist_free(attrs);
		return (NULL);
	}

	/* Process logs */
	td_zpool_allocate_target_nvlist(zi->attributes.logs,
	    zi->attributes.num_logs, attrs, TD_ZPOOL_ATTR_LOGS,
	    TD_ZPOOL_ATTR_NUM_LOGS, errn);
	if (*errn != 0) {
		nvlist_free(attrs);
		return (NULL);
	}


	/* Process l2cache */
	td_zpool_allocate_target_nvlist(zi->attributes.l2cache,
	    zi->attributes.num_l2cache, attrs, TD_ZPOOL_ATTR_L2CACHE,
	    TD_ZPOOL_ATTR_NUM_L2CACHE,
	    errn);
	if (*errn != 0) {
		nvlist_free(attrs);
		return (NULL);
	}

	/* Process spares */
	td_zpool_allocate_target_nvlist(zi->attributes.spares,
	    zi->attributes.num_spares, attrs, TD_ZPOOL_ATTR_SPARES,
	    TD_ZPOOL_ATTR_NUM_SPARES,
	    errn);
	if (*errn != 0) {
		nvlist_free(attrs);
		return (NULL);
	}

	return (attrs);
}

/*
 * Function: td_zpool_target_print
 *
 * Description: Print contents of td_zpool_target_t
 *
 * Parameters:
 *		td_zpool_target_t *zt	: zpool_target to print
 *		int depth           	: depth nesting to print
 *		boolean_t is_spare  	: Is spare device
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_target_print(td_zpool_target_t *zt,
	int depth,
	boolean_t is_spare)
{
	int i = 0;

	if (zt == NULL) {
		return;
	}

	if (is_spare) {
		td_debug_print(LS_DBGLVL_INFO,
		    "     |   %*s%-*s| "
		    "%9s|         | %4s| %5s| %3s|\n",
		    depth, "", 31 - depth,
		    zt->name, zt->health, "", "", "");
	} else {
		td_debug_print(LS_DBGLVL_INFO,
		    "     |   %*s%-*s| "
		    "%9s|         | %4llu| %5llu| %3llu|\n",
		    depth, "", 31 - depth,
		    zt->name, zt->health,
		    zt->read_errors, zt->write_errors,
		    zt->checksum_errors);
	}

	for (i = 0; i < zt->num_targets; i++) {
		td_zpool_target_print(zt->targets[i], depth+2, is_spare);
	}
}

/*
 * Function: td_zpool_info_print
 *
 * Description: Print contents of td_zpool_info_t
 *
 * Parameters:
 *		td_zpool_info_t *zi	: zpool to print
 *		int num 		: zpool count printed
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_info_print(td_zpool_info_t *zi, int num)
{
	int i = 0;
	double size_mb = 0;
	double size_gb = 0;

	size_mb = BYTES_TO_MB(zi->attributes.size);
	if (size_mb > MB_IN_GB) {
		size_gb = MB_TO_GB(size_mb);
		size_mb = 0;
	}

	td_debug_print(LS_DBGLVL_INFO, " %3d | %-33s| "
	    "%9s| %7.2lf%c| %4llu| %5d|  %2d|\n", num, zi->attributes.name,
	    zi->attributes.health,
	    size_mb > 0 ? size_mb : size_gb,
	    size_mb > 0 ? 'M' : 'G',
	    zi->attributes.capacity,
	    zi->attributes.status,
	    zi->attributes.version);

	td_debug_print(LS_DBGLVL_INFO, " %3s | %33llu| "
	    "%9s| %8s| %4s| %5s|  %2s|\n", "",
	    zi->attributes.guid, "", "", "", "", "", "");

	if (zi->attributes.bootfs != NULL) {
		td_debug_print(LS_DBGLVL_INFO, " %3s | %33s| "
		    "%9s| %8s| %4s| %5s|  %2s|\n", "",
		    zi->attributes.bootfs, "", "", "", "", "", "");
	}

	if (zi->attributes.import) {
		td_debug_print(LS_DBGLVL_INFO, " %3s | %33s| "
		    "%9s| %8s| %4s| %5s|  %2s|\n", "",
		    "Importable pool", "", "", "", "", "", "");
	}

	for (i = 0; i < zi->attributes.num_targets; i++) {
		td_zpool_target_print(zi->attributes.targets[i], 0, B_FALSE);
	}

	if (zi->attributes.num_logs > 0) {
		td_debug_print(LS_DBGLVL_INFO, " %3s | %-33s| "
		    "%9s| %8s| %4s| %5s|  %2s|\n", "", "logs",
		    "", "", "", "", "");
		for (i = 0; i < zi->attributes.num_logs; i++) {
			td_zpool_target_print(zi->attributes.logs[i],
			    0, B_FALSE);
		}
	}

	if (zi->attributes.num_l2cache > 0) {
		td_debug_print(LS_DBGLVL_INFO, " %3s | %-33s| "
		    "%9s| %8s| %4s| %5s|  %2s|\n", "", "cache",
		    "", "", "", "", "");
		for (i = 0; i < zi->attributes.num_l2cache; i++) {
			td_zpool_target_print(zi->attributes.l2cache[i],
			    0, B_FALSE);
		}
	}

	if (zi->attributes.num_spares > 0) {
		td_debug_print(LS_DBGLVL_INFO, " %3s | %-33s| "
		    "%9s| %8s| %4s| %5s|  %2s|\n", "", "spares",
		    "", "", "", "", "");
		for (i = 0; i < zi->attributes.num_spares; i++) {
			td_zpool_target_print(zi->attributes.spares[i],
			    0, B_TRUE);
		}
	}
}

/*
 * Function: td_zpool_info_print_ptrs
 *
 * Description:
 *		Print all td_zpool_info_t's in ptr array
 *
 * Parameters:
 *		td_zpool_info_t **ptrs : Array of pointers to print from
 *
 * Returns:
 *		void
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_info_print_ptrs(td_zpool_info_t **ptrs)
{
	int i = 0;
	int num = 0;

	if (ptrs == NULL || ptrs[0] == NULL) {
		td_debug_print(LS_DBGLVL_INFO,
		    "zpool ptrs array is empty.\n");
		return;
	}

	for (i = 0; ptrs[i]; i++) {
		td_zpool_info_print(ptrs[i], ++num);
	}
}

/*
 * Function: td_zpool_info_print_list
 *
 * Description: Runs through the linked list of zpool attributes printing all
 *		the stored information.
 *
 * Parameters:
 *		td_zpool_info_t start : Linked list of zpools to print
 *
 * Returns:
 *		NULL
 *
 * Scope:
 * 		Private
 */
static void
td_zpool_info_print_list(td_zpool_info_t *start)
{
	int num = 0;
	td_zpool_info_t *cur = start;

	if (cur == NULL) {
		td_debug_print(LS_DBGLVL_INFO,
		    "zpool list is empty.\n");
		return;
	}

	while (cur != NULL) {
		td_zpool_info_print(cur, ++num);
		cur = cur->next;
	}
}

/*
 * Function: td_zpool_info_ptrs_to_ddm_handle
 *
 * Description: Convert array of td_zpool_info_t ptrs to an
 *      	array of ddm_handle_t's for returning to TD
 *
 * Parameters:
 *      	td_zpool_info_t **ptrs	: Array of td_zpool_info_t pointers
 *
 * Returns:
 *      	ddm_handle_t *  	: Array of ddm_handle_t pointers
 *
 * Scope:
 *      	Private
 */
static ddm_handle_t *
td_zpool_info_ptrs_to_ddm_handle(td_zpool_info_t **ptrs)
{
#ifdef _LP64
	return ((ddm_handle_t *)ptrs);
#else
	/* convert the 32 bit ptrs to the 64 bit descriptors */
	int	cnt;
	int	i;
	ddm_handle_t *dh;

	if (ptrs == NULL) {
		td_debug_print(LS_DBGLVL_WARN,
		    "td_zpool_info_ptrs_to_ddm_handle():"
		    " zpool ptr array NULL cannot convert to ddm_handle_t\n");
		return (NULL);
	}

	for (cnt = 0; ptrs[cnt]; cnt++)
		;

	dh = (ddm_handle_t *)calloc(cnt + 1, sizeof (ddm_handle_t));
	if (dh == NULL) {
		td_debug_print(LS_DBGLVL_ERR,
		    "td_zpool_info_ptrs_to_ddm_handle():"
		    " Failed to allocate memory for ddm_handle_t array\n");
		return (NULL);
	}

	for (i = 0; ptrs[i]; i++) {
		dh[i] = (uintptr_t)ptrs[i];
	}

	return (dh);
#endif
}

/*
 * Function: td_zpool_info_get_ptrs
 *
 * Description: Take a linked list of zpools and generate an array
 *      	of pointers for each element in the list.
 *
 * Parameters:
 *      	td_zpool_info_t *	: Linked list of zpools
 *      	int *nzpools     	: Num Zpools discovered
 *
 * Returns:
 *      	td_zpool_info_t **	: Array of td_zpool_info_t pointers
 *      	int *nzpools      	: Number of zpools discovered
 *
 * Scope:
 *      	Private
 */
static td_zpool_info_t **
td_zpool_info_get_ptrs(td_zpool_info_t *zpools_list, int *nzpools)
{
	td_zpool_info_t **ptrs;
	td_zpool_info_t *cur;
	int pos = 0;
	int zpoolcnt = 0;

	for (zpoolcnt = 0, cur = zpools_list;
	    cur != NULL;
	    cur = cur->next)
		zpoolcnt++;

	/* Set return paramater for number of zpools found */
	if (nzpools != NULL)
		*nzpools = zpoolcnt;

	ptrs = (td_zpool_info_t **)
	    calloc(zpoolcnt + 1, sizeof (td_zpool_info_t *));
	if (ptrs == NULL) {
		td_debug_print(LS_DBGLVL_ERR, "td_zpool_info_get_ptrs():"
		    " Failed to allocate memory for zpool ptr array\n");
		return (NULL);
	}

	for (pos = 0, cur = zpools_list; cur != NULL; cur = cur->next) {
		ptrs[pos++] = cur;
	}

	return (ptrs);
}
