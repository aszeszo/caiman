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

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <sys/types.h>

#include "orchestrator_private.h"
#include "td_api.h"

/*
 * Global Variables
 */

disk_target_t	*system_disks = NULL;
disk_target_t	*committed_disk_target = NULL;
upgrade_info_t	*solaris_instances = NULL;
boolean_t	disk_discovery_done = B_FALSE;
boolean_t	disk_discovery_failed = B_FALSE;
int		disks_total = 0;
int		disks_found = 0;
int16_t		om_errno;
om_handle_t	omh = 0;

/*
 * om_initiate_target_discovery
 * This function will start the target discovery and return to the user.
 * Input:	None
 * Output:	None
 * Return:	true, if the target discovery can be started successfully
 *		false, if the target discovery can't be started.
 */

om_handle_t
om_initiate_target_discovery(om_callback_t cb)
{
	pthread_t	discovery_thread;
	callback_args_t *cb_args;
	int		ret;

	/*
	 * call the TD module discover to find the disks on the system
	 */
	if (start_td_disk_discover(&disks_total) != OM_SUCCESS) {
		om_set_error(OM_TD_DISCOVERY_FAILED);
		return (OM_FAILURE);
	}

	/*
	 * Create a thread for running discovery and report progress
	 * using the callback function.
	 * if callback function is not provided, do not create the thread
	 */
	cb_args = (callback_args_t *)calloc(1, sizeof (callback_args_t));
	if (cb_args == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	cb_args->cb = cb;
	cb_args->cb_type.td.num_disks = disks_total;
	ret = pthread_create(&discovery_thread, NULL,
	    handle_disk_discovery, (void *)cb_args);

	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		free(cb_args);
		return (OM_FAILURE);
	}

	/*
	 * Return a handle. Currently it is not used
	 */
	return (omh++);
}

/*
 * om_free_target_data
 * This function will free up the Orchestrator's internal cache
 * that stores target discovery data.
 * Input:	om_handle_t handle - The handle to refer to the TD data
 * Output:	None.
 * Return:	None.
 */
void
om_free_target_data(om_handle_t handle)
{
	disk_target_t	*dt;
	boolean_t	follow_link = B_FALSE;

	/*
	 * Go through the disk_target_t and release all the
	 * disk_info_t, disk_parts_t and disk_slices_t structures
	 */
	for (dt = system_disks; dt != NULL; dt = dt->next) {
		local_free_disk_info(&dt->dinfo, follow_link);
		local_free_part_info(dt->dparts);
		local_free_slice_info(dt->dslices);
		free(dt);
	}
	system_disks = NULL;

	/*
	 * Free he space allocated for upgrade targets
	 */
	if (solaris_instances != NULL) {
		om_free_upgrade_targets(handle, solaris_instances);
		solaris_instances = NULL;
	}
}

/*
 * handle_disk_discovery
 * This function starts the individual disk discovery and create callbacks
 * after discovering each disk, partitions for each disk and slices for each
 * disk.
 * Input:	void *args - The arguments to initialize the callback.
 *		currently the structure containing total number of disks
 *		and the callback function are passed.
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
void *
handle_disk_discovery(void *args)
{
	callback_args_t		*cp;
	static int		status = 0;
	om_callback_t		cb;
	int			num_disks;

	cp = (callback_args_t *)args;

	num_disks = cp->cb_type.td.num_disks;
	cb = cp->cb;

	/*
	 * If there are no disks, then just send a callback to the caller
	 * indicating that the discovery is completed
	 */
	if (num_disks > 0) {
		if (system_disks != NULL || solaris_instances != NULL) {
			om_free_target_data(0);
		}
		system_disks = get_td_disk_info_discover(&num_disks, cb);
		/*
		 * if we don't get any disks, return failure
		 */
		if (system_disks != NULL) {
			get_td_disk_parts_discover(system_disks, cb);
			get_td_disk_slices_discover(system_disks, cb);
			solaris_instances = get_td_solaris_instances(cb);
		}
	}

	if (num_disks == 0) {
		send_discovery_complete_callback(cb);
	}

	/*
	 * Free the Target discovery resources after target discovery
	 * is done
	 */
	disk_discovery_done = B_TRUE;
	td_discovery_release();
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}
