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

#pragma ident	"@(#)upgrade_targets.c	1.2	07/08/22 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/types.h>

#include "spmizones_api.h"
#include "spmiapp_api.h"
#include "orchestrator_private.h"

/*
 * Global variables
 */
boolean_t instances_discovery_done = B_FALSE;

/*
 * local functions
 */
void	print_space_results(FSspace **sp, char *outfile);
/*
 * om_get_upgrade_targets
 * This function will return the upgrade targets (Solaris Instances)
 * found on the system. All the solaris instances whether upgradable
 * or not will be returned to the caller.
 * Input:	None
 * Output:	int *found - Total number of Solaris Instances found
 *		in the system will be returned in num_instances.
 * Return:	The Solaris Instances will be returned in a pointer to
 *		upgrade_info_t. The space will be allocated here and the
 *              Solaris instances will be linked and returned to the caller.
 *		NULL, if the Solaris Instance data can't be returned and the
 *		om_get_errno() can be used to find the error condition.
 */
/*ARGSUSED*/
upgrade_info_t *
om_get_upgrade_targets(om_handle_t handle, uint16_t *found)
{
	char *diskname = ALLDISKS;

	return (om_get_upgrade_targets_by_disk(handle, diskname, found));
}

/*
 * om_get_upgrade_targets_by_disk
 * This function will return the upgrade targets (Solaris Instances)
 * found on a single disk passed as a parameter.
 * All the solaris instances whether upgradable or not will be
 * returned to the caller.
 * Input:	char *diskname - The name of the disk
 * Output:	int *found - Total number of Solaris Instances found
 *		in the system will be returned in num_instances.
 * Return:	The Solaris Instances will be returned in a pointer to
 *		upgrade_info_t. The space will be allocated here and the
 *              Solaris instances will be linked and returned to the caller.
 *		NULL, if the Solaris Instance data can't be returned and the
 *		om_get_errno() can be used to find the error condition.
 */
/*ARGSUSED*/
upgrade_info_t *
om_get_upgrade_targets_by_disk(om_handle_t handle,
    char *diskname, uint16_t *found)
{
	om_callback_t	cb = NULL;
	upgrade_info_t	*ui, *si;
	upgrade_info_t	*tmpui;
	upgrade_info_t	*uinfo;
	uint16_t	total = 0;

	/*
	 * If the target discovery is not yet completed, set the
	 * error number and return NULL
	 */
	if (!disk_discovery_done) {
		om_set_error(OM_DISCOVERY_NEEDED);
		return (NULL);
	}

	if (solaris_instances == NULL) {
		/*
		 * Start the instance (upgrade targets) discovery
		 * if it is the first time
		 */
		if (!instances_discovery_done) {
			solaris_instances = get_td_solaris_instances(cb);
			instances_discovery_done = B_TRUE;
		}

		/*
		 * if we don't get any instances, log the information
		 */
		if (solaris_instances == NULL) {
			om_set_error(OM_NO_UPGRADE_TARGETS_FOUND);
			return (NULL);
		}
	}

	tmpui = NULL;
	uinfo = NULL;
	om_set_error(0);
	for (ui = solaris_instances; ui != NULL; ui = ui->next) {
		if (ui->instance_type != OM_INSTANCE_UFS) {
			continue;
		}
		/*
		 * If the diskname of the instance doesn't match
		 * the passed diskname, ignore the upgrade_target
		 * and move on to next one.
		 * If diskname is ALLDISKS, get all the instances
		 */
		if (!streq(diskname, ALLDISKS) &&
		    !streq(ui->instance.uinfo.disk_name, diskname)) {
			continue;
		}
		si = copy_one_upgrade_target(ui);
		/*
		 * If it is NULL, we have to return failure
		 * free the upgrade targets already copied and bail out.
		 * The error code is already set in copy_one_upgrade_target.
		 */
		if (si == NULL) {
			local_free_upgrade_info(uinfo);
			return (NULL);
		}
		if (tmpui == NULL) {
			tmpui = si;
			uinfo = si;
		} else {
			tmpui->next = si;
			tmpui = tmpui->next;
		}
		total++;
	}
	if (uinfo == NULL) {
		om_set_error(OM_NO_UPGRADE_TARGETS_FOUND);
	}
	*found = total;
	return (uinfo);
}

/*
 * om_is_upgrade_target_valid
 * This function will check whether the user selected Solaris Instance
 * can be upgraded.
 * Input:	UpgradeInfo *uinfo
 * Output:	int *messageId - If the Solaris Instance can't be upgraded,
 *		the id of the error message will be returned
 * Return:	B_TRUE, if the Solaris Instance can be upgradable
 *		B_FALSE, if the Solaris Instance can't be upgradable
 */
/*ARGSUSED*/
boolean_t
om_is_upgrade_target_valid(om_handle_t handle,
    upgrade_info_t *uinfo, om_callback_t ut_cb)
{
	pthread_t	validate_upgrade_thread;
	callback_args_t *cb_args;
	int		ret;
	char		root_slice[MAXNAMELEN];

	if (uinfo == NULL) {
		om_set_error(OM_NO_UPGRADE_TARGET);
		return (B_FALSE);
	}

	/*
	 * We support only solaris instance which is on UFS.
	 * The other types of targets like zfs will be added when they
	 * become available
	 */
	if (uinfo->instance_type != OM_INSTANCE_UFS) {
		om_set_error(OM_NOT_UFS_UPGRADE_TARGET);
		return (B_FALSE);
	}

	if (uinfo->instance.uinfo.disk_name == NULL) {
		om_set_error(OM_NO_UPGRADE_TARGET);
		return (B_FALSE);
	}

	if (!uinfo->upgradable)	{
		om_set_error(OM_UPGRADE_NOT_ALLOWED);
		return (B_FALSE);
	}

	(void) snprintf(root_slice, sizeof (root_slice), "%ss%d",
	    uinfo->instance.uinfo.disk_name, uinfo->instance.uinfo.slice);
	/*
	 * Create a thread for running discovery and report progress
	 * using the callback function.
	 * if callback function is not provided, do not create the thread
	 */
	cb_args = (callback_args_t *)calloc(1, sizeof (callback_args_t));
	if (cb_args == NULL) {
		om_set_error(OM_NO_SPACE);
		return (B_FALSE);
	}
	cb_args->cb = ut_cb;
	cb_args->cb_type.valid.target = strdup(root_slice);
	if (cb_args->cb_type.valid.target == NULL) {
		om_set_error(OM_NO_SPACE);
		free(cb_args);
		return (B_FALSE);
	}
	ret = pthread_create(&validate_upgrade_thread, NULL,
	    handle_upgrade_validation, (void *)cb_args);

	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		free(cb_args->cb_type.valid.target);
		free(cb_args);
		return (B_FALSE);
	}
	return (B_TRUE);
}

/*
 * om_free_upgrade_targets
 * This function will free up the upgrade target information data
 * allocated during om_get_upgrade_targets().
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		upgrade_info_t *uinfo - The pointer to upgrade_info_t. Usually
 *		returned by om_get_upgrade_targets().
 * Output:	None.
 * Return:	None.
 */
/*ARGSUSED*/
void
om_free_upgrade_targets(om_handle_t handle, upgrade_info_t *uinfo)
{
	om_set_error(0);
	if (uinfo == NULL) {
		return;
	}

	local_free_upgrade_info(uinfo);
}

/*
 * om_duplicate_upgrade_targets
 * This function allocates space and copy the upgrade_info_t structure
 * passed as a parameter.
 * Input:	om_handle_t handle - The handle returned by
 *		om_initiate_target_discovery()
 *		upgrade_info_t * - Pointer to upgrade_info_t. Usually the return
 *		value from get_upgrade_targets().
 * Return:	upgrade_info_t * - Pointer to upgrade_info_t. Space will be
 *		allocated and the data is copied and returned.
 *		NULL, if space cannot be allocated.
 */
/*ARGSUSED*/
upgrade_info_t *
om_duplicate_upgrade_targets(om_handle_t handle, upgrade_info_t *uiptr)
{
	upgrade_info_t	*ui, *si;
	upgrade_info_t	*tmpui;
	upgrade_info_t	*uinfo;
	/*
	 * Get the Solaris Instances from TD module
	 */
	tmpui = NULL;
	uinfo = NULL;
	om_set_error(0);
	for (ui = uiptr; ui != NULL; ui = ui->next) {
		si = copy_one_upgrade_target(ui);
		if (si == NULL) {
			continue;
		}
		if (tmpui == NULL) {
			tmpui = si;
			uinfo = si;
		} else {
			tmpui->next = si;
			tmpui = tmpui->next;
		}
	}
	if (uinfo == NULL) {
		om_set_error(OM_NO_UPGRADE_TARGETS_FOUND);
	}
	return (uinfo);
}

/*
 * ==================Private Functions ===============================
 */

/*
 * This is a internal function used to allocate and copy an upgrade target
 */
upgrade_info_t *
copy_one_upgrade_target(upgrade_info_t *ui)
{
	upgrade_info_t	*si;

	if (ui == NULL) {
		return (NULL);
	}

	si = (upgrade_info_t *)calloc(1, sizeof (upgrade_info_t));
	if (si == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	/*
	 * setup the new upgrade target by copied values from the
	 * instance passed as an input parameter
	 */
	if (ui->solaris_release != NULL) {
		si->solaris_release = strdup(ui->solaris_release);
	} else {
		si->solaris_release = strdup(OM_UNKNOWN_STRING);
	}
	if (si->solaris_release == NULL) {
		om_set_error(OM_NO_SPACE);
		goto cout_return;
	}
	si->zones_installed = ui->zones_installed;
	si->upgradable = ui->upgradable;
	si->upgrade_message_id = ui->upgrade_message_id;
	if (ui->incorrect_zone_list != NULL) {
		si->incorrect_zone_list = strdup(ui->incorrect_zone_list);
		if (si->incorrect_zone_list == NULL) {
			om_set_error(OM_NO_SPACE);
			goto cout_return;
		}
	}
	/*
	 * Currently assuming that it is UFS
	 */
	si->instance_type = ui->instance_type;
	if (ui->instance_type == OM_INSTANCE_UFS) {
		if (ui->instance.uinfo.disk_name != NULL) {
			si->instance.uinfo.disk_name =
			    strdup(ui->instance.uinfo.disk_name);
		} else {
			/* should not happen */
			si->instance.uinfo.disk_name =
			    strdup(OM_UNKNOWN_STRING);
		}
		if (si->instance.uinfo.disk_name == NULL) {
			om_set_error(OM_NO_SPACE);
			goto cout_return;
		}
		si->instance.uinfo.slice = ui->instance.uinfo.slice;
		si->instance.uinfo.svm_configured =
		    ui->instance.uinfo.svm_configured;
		if (ui->instance.uinfo.svm_info != NULL) {
			si->instance.uinfo.svm_info =
			    strdup(ui->instance.uinfo.svm_info);
		} else {
			si->instance.uinfo.svm_info =
			    strdup(OM_UNKNOWN_STRING);
		}
		if (si->instance.uinfo.svm_info == NULL) {
			om_set_error(OM_NO_SPACE);
			goto cout_return;
		}
	}
	si->next = NULL;
	return (si);
cout_return:
	free(si->solaris_release);
	free(si->incorrect_zone_list);
	free(si->instance.uinfo.disk_name);
	free(si->instance.uinfo.svm_info);
	return (NULL);
}

/*
 * om_is_upgrade_target_valid
 * This function perform upgrade target validation using the
 * upgrade mechanism implemented in pfinatll
 * Input:	void *args - The arguments to initialize the callback.
 *		currently the structure containing upgrade target slice
 *		and the callback function are passed.
 * Output:	None
 * Return:	The status is returned as part of pthread_exit function
 */

void *
handle_upgrade_validation(void *args)
{
	callback_args_t		*cp;
	om_callback_t		cb;
	char			*root_slice;
	char			*media_dir = "/cdrom";
	Module			*media, *mod;
	char			*meta_cluster;
	FSspace			**space;
	int			status;
	int16_t			percent = 0;
	boolean_t		zones_loaded = B_FALSE;

	cp = (callback_args_t *)args;

	root_slice = cp->cb_type.valid.target;
	cb = cp->cb;

	init_spmi_for_upgrade_check();
	/*
	 * Mount the file system to examine the instance
	 */
	if ((status = mount_and_add_swap(root_slice, NULL)) != 0) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		om_debug_print(OM_DBGLVL_ERR, "mount_and_add_swap failed\n");
		goto huv_return;
	}
	percent += 10;
	send_upgrade_validation_callback(percent, cb);

	if ((mod = load_installed("/", FALSE)) == NULL) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		status = OM_BAD_UPGRADE_TARGET;
		om_debug_print(OM_DBGLVL_ERR, "load_installed failed\n");
		goto huv_return;
	}
	percent += 10;
	send_upgrade_validation_callback(percent, cb);

	meta_cluster = mod->sub->sub->info.mod->m_pkgid;

	if (load_zones() != 0) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		om_debug_print(OM_DBGLVL_ERR, "load_zones failed\n");
		status = OM_BAD_UPGRADE_TARGET;
		goto huv_return;
	}
	zones_loaded = B_TRUE;
	percent += 10;
	send_upgrade_validation_callback(percent, cb);

	/*
	 * Load the media
	 */
	if ((media = add_media(media_dir)) != NULL) {
		if (load_media(media, TRUE) != 0) {
			om_set_error(OM_CANNOT_LOAD_MEDIA);
			status = OM_CANNOT_LOAD_MEDIA;
			om_debug_print(OM_DBGLVL_ERR, "load_media failed\n");
			goto huv_return;
		}
	}
	percent += 10;
	send_upgrade_validation_callback(percent, cb);

	status = upgrade_all_envs();
	if (status != 0) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		om_debug_print(OM_DBGLVL_ERR, "upgrade_all_envs failed\n");
		goto huv_return;
	}

	(void) load_view((get_default_media())->sub, get_localmedia());

	status = configure_software(meta_cluster);

	percent += 10;
	send_upgrade_validation_callback(percent, cb);

	if (status != 0) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		om_debug_print(OM_DBGLVL_ERR, "configure_software failed\n");
		goto huv_return;
	}

	/*
	 * Get the current file system layout
	 */
	space = get_current_fs_layout(TRUE);
	if (space == NULL) {
		om_set_error(OM_BAD_UPGRADE_TARGET);
		status = OM_BAD_UPGRADE_TARGET;
		om_debug_print(OM_DBGLVL_ERR, "get_current_fs_layout failed\n");
		goto huv_return;
	}

	percent += 20;
	send_upgrade_validation_callback(percent, cb);

	status = verify_fs_layout(space, NULL, NULL);

	if (status == SP_ERR_NOT_ENOUGH_SPACE) {
		om_set_error(OM_NOT_ENOUGH_SPACE);
		om_debug_print(OM_DBGLVL_ERR, "verify_fs_layout failed\n");

		/*
		 * Report the space required information back to the user
		 */
		print_space_results(space, "/tmp/space.out");
		goto huv_return;
	} else if (status != 0) {
		om_set_error(OM_SPACE_CHECK_FAILURE);
		om_debug_print(OM_DBGLVL_ERR, "verify_fs_layout failed\n");
		goto huv_return;
	}
	percent += 20;
	send_upgrade_validation_callback(percent, cb);
	status = 0;

huv_return:
	if (zones_loaded) {
		UmountAllZones(get_rootdir());
	}
	om_debug_print(OM_DBGLVL_ERR, "validation exited with status = %d\n",
	    status);

	if (umount_and_delete_swap() != 0) {
		/*
		 * Log the failure
		 */
		status = OM_CANNOT_UMOUNT_ROOT_SWAP;
		om_set_error(OM_CANNOT_UMOUNT_ROOT_SWAP);
		om_debug_print(OM_DBGLVL_ERR,
		    "umount_and_delete_swap failed\n");
	}
	if (status == 0) {
		percent = 100;
	} else {
		percent = -1;
	}
	send_upgrade_validation_callback(percent, cb);
	/*
	 * Free the arguments allocated for this thread by the caller
	 */
	free(cp->cb_type.valid.target);
	free(args);
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}

/*
 * send_upgrade_validation_callback
 * This function will send a callback with the percent information
 * passed as a parameter
 * Input:	percent - The percentage of validation completed
 *		cb - Callback function to be invoked
 * output:	None
 * Return:	None
 */
void
send_upgrade_validation_callback(int16_t percent, om_callback_t cb)
{
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;

	if (cb == NULL) {
		return;
	}
	cb_data.callback_type = OM_SYSTEM_VALIDATION;
	cb_data.num_milestones = 1;
	cb_data.curr_milestone = OM_UPGRADE_CHECK;
	cb_data.percentage_done = percent;
	cb(&cb_data, app_data);
}
