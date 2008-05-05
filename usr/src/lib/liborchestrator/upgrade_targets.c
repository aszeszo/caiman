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


#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/types.h>

#include "orchestrator_private.h"

/*
 * Global variables
 */
boolean_t instances_discovery_done = B_FALSE;

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
	return (B_FALSE);
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
