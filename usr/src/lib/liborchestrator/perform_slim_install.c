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

#pragma ident	"@(#)perform_slim_install.c	1.27	07/10/30 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <pthread.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <sys/wait.h>
#include <crypt.h>
#include <unistd.h>
#include <time.h>
#include <libgen.h>
#include <netdb.h>
#include <locale.h>

#include "spmisoft_lib.h"
#include "td_lib.h"
#include "cl_database_parms.h"
#include "admldb.h"

#include "orchestrator_private.h"
#include "transfermod.h"

#include <ls_api.h>

#define	UN(string) ((string) ? (string) : "")

#define	ROOT_NAME	"root"
#define	ROOT_UID	"0"
#define	ROOT_GID	"1"
#define	ROOT_PATH	"/"

#define	USER_UID	"101"
#define	USER_GID	"10"	/* staff */
#define	USER_PATH	"/export/home/"

#define	STATE_FILE	"/etc/.sysIDtool.state"

#define	MAXDEVSIZE	100

struct icba {
	om_install_type_t	install_type;
	pid_t			pid;
	om_callback_t		cb;
};

struct transfer_callback {
	char		*target;
	om_callback_t	cb;
};

struct ti_callback {
	nvlist_t *target_attrs;
	ti_cbf_t cb;
};

/*
 * Global Variables
 */
static	pid_t		pfinstall_pid;
static	boolean_t	install_test = B_FALSE;
static	char		*state_file_path = NULL;
om_install_type_t	install_type;
static	char		*save_login_name = NULL;
static	char		*def_locale;
om_callback_t		om_cb;
boolean_t		ti_done = B_FALSE;
char			zfs_device[MAXDEVSIZE];
char			swap_device[MAXDEVSIZE];

extern	char		**environ;

struct _shortloclist {
	const char	*shortloc;
	boolean_t	added;
} shortloclist[] = {
	/*
	 * sorting in reverse alphabetical order since
	 * entry for substring (e.g. "zh") needs to come
	 * before longer name (e.g. "zh_TW" or "zh_HK")
	 */
	{ "zh_TW", B_FALSE },
	{ "zh_HK", B_FALSE },
	{ "zh",    B_FALSE },
	{ "sv",    B_FALSE },
	{ "pt_BR", B_FALSE },
	{ "ko",    B_FALSE },
	{ "ja",    B_FALSE },
	{ "it",    B_FALSE },
	{ "fr",    B_FALSE },
	{ "es",    B_FALSE },
	{ "de",    B_FALSE },
	{ NULL,    B_FALSE },
};

/*
 * local functions
 */


static void	add_shortloc(const char *locale, FILE *fp);
static char 	*find_state_file();
static void	init_shortloclist(void);
static void	read_and_save_locale(char *path);
static void	remove_component(char *path);
static int	replace_db(char *name, char *value);
static int	set_entry(char *table, char *key, char *value, char *rootdir);
static int 	set_net_hostname(char *hostname);
static void 	set_system_state(void);
static int	trav_link(char **path);
static void 	write_sysid_state(sys_config *sysconfigp);
static void	notify_error_status(int status);
static void	notify_install_complete();
static void	enable_nwam();
static void	create_user_directory();
static void	transfer_log_files(char *target);
static void	umount_tmp(char *path);
static void	run_install_finish_script(char *target);
static void 	setup_users_default_environ(char *target);
static void	setup_etc_vfstab_for_zfs_root(char *target);
static void	reset_zfs_mount_property(char *target);
static void	run_installgrub(char *target, char *device);
static void	transfer_config_files(char *target);

void 		*do_transfer(void *arg);
void		*do_ti(void *args);
ti_errno_t	ti_cb(nvlist_t *progress);

/*
 * om_perform_install
 * This function will setup configuration, create jumpstart profile based on
 * the data from GUI and call install/upgrade function(s).
 * Input:	nvlist_t *uchoices - The user choices will be provided as
 *		name-value pairs
 *		void *cb - callback function to inform the GUI about
 *		the progress.
 * Output:	None
 * Return:	OM_SUCCESS, if the install program started succcessfully
 *		OM_FAILURE, if the there is a failure
 * Notes:	The user selected configuration is passed from the GUI
 *		in the form of name-value pair list
 *		The current values passed are:
 *		install_type - uint8_t (initial_install/upgrade)
 *		disk name - String (only for initial_install- example c0d0)
 *		upgrade target - String (only for upgrade - example c0d0s0)
 *		list of locales to be installed - String
 *		default locale - String
 *		user name - String - The name of the user account to be created
 *		user password - String - user password
 *		root password - String - root password
 */

int
om_perform_install(nvlist_t *uchoices, om_callback_t cb)
{
	char		*name;
	char		*lname = NULL, *passwd = NULL, *hostname = NULL,
	    *uname = NULL, *upasswd = NULL;
	char		*tmp_file;
	int		status = OM_SUCCESS;
	nvlist_t	*target_attrs = NULL;
	om_callback_info_t cb_data;
	ti_errno_t	error = 0;
	uintptr_t	app_data = 0;
	uint8_t		type;
	char		*ti_test = getenv("TI_SLIM_TEST");
	pthread_t	ti_thread;
	int		ret = 0;


	if (uchoices == NULL) {
		om_set_error(OM_BAD_INPUT);
	}
	if (!ti_test) {

	/*
	 * Get the install_type
	 */
	if (nvlist_lookup_uint8(uchoices,
	    OM_ATTR_INSTALL_TYPE, &type) != 0) {
		om_set_error(OM_NO_INSTALL_TYPE);
		return (OM_FAILURE);
	}

	/*
	 * Supports only initial_install and upgrade
	 */
	if (type != OM_INITIAL_INSTALL) {
		om_set_error(OM_BAD_INSTALL_TYPE);
		return (OM_FAILURE);
	}
	install_type = type;

	/*
	 * Special value for testing
	 */
	if (nvlist_lookup_boolean_value(uchoices,
	    OM_ATTR_INSTALL_TEST, (boolean_t *)&install_test) != 0) {
		install_test = B_FALSE;
	}
	}

	/*
	 * Now process initial install
	 * Get the disk name - Install target
	 */
	fprintf(stderr, "getting disk name\n");
	if (nvlist_lookup_string(uchoices, OM_ATTR_DISK_NAME, &name) != 0) {
		om_debug_print(OM_DBGLVL_ERR, "No install target\n");
		om_set_error(OM_NO_INSTALL_TARGET);
		return (OM_FAILURE);
	}
	fprintf(stderr, "diskname = %s\n", name);

	if (!is_diskname_valid(name)) {
		om_set_error(OM_BAD_INSTALL_TARGET);
		return (OM_FAILURE);
	}


	/*
	 * For initial install, set up the following things.
	 * 1. Timezone
	 * 2. default locale
	 * 3. Root Password
	 * 4. User Name
	 * 5. User password
	 * 6. Host/nodename
	 */

	if (!ti_test) {
	/*
	 * Get the default locale. Save it off for later. We don't
	 * set the system default locale until after the installation
	 * has completed. XXX will Slim have this set from GUI?
	 */
	if (nvlist_lookup_string(uchoices,
	    OM_ATTR_DEFAULT_LOCALE, &def_locale) != 0) {
		/*
		 * Default locale is not passed, so don't set it
		 * Log the information and continue
		 */
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_DEFAULT_LOCALE not set,"
		    "default locale is null\n");
		om_log_print("Default locale is NULL\n");
		def_locale = NULL;
	} else {
		om_debug_print(OM_DBGLVL_INFO, "Default locale specified: %s\n",
		    def_locale);
	}
	/*
	 * Get the root password
	 */
	if (nvlist_lookup_string(uchoices,
	    OM_ATTR_ROOT_PASSWORD, &passwd) != 0) {
		/*
		 * Root password is not passed, so don't set it
		 * Log the information and set the default password
		 */
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_ROOT_PASSWORD not set,"
		    "set the default root password\n");
		om_log_print("Root password not specified, set to default\n");
		(void) set_root_password(OM_DEFAULT_ROOT_PASSWORD);
	} else {
		om_debug_print(OM_DBGLVL_INFO, "Got root passwd\n");
		(void) set_root_password(passwd);
	}

	/*
	 * Get the user name,if set, which is different than the login
	 * name.
	 */

	if (nvlist_lookup_string(uchoices,
	    OM_ATTR_USER_NAME, &uname) != 0) {
		/*
		 * User name is not passed, so don't set it
		 * Log the information and continue
		 */
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_USER_NAME not set,"
		    "User name not available\n");
		om_log_print("User name not specified\n");
	}
	if (uname)
		om_debug_print(OM_DBGLVL_INFO, "User name set to"
		    "%s\n", uname);

	if (nvlist_lookup_string(uchoices, OM_ATTR_LOGIN_NAME, &lname) != 0) {
		/*
		 * No login name, don't worry about getting passwd info.
		 * Log this data and move on.
		 */
		om_debug_print(OM_DBGLVL_WARN,
		    "OM_ATTR_LOGIN_NAME not set,"
		    "User login name not available\n");
		om_log_print("User login name not specified\n");
	} else {
		/*
		 * we got the user name.
		 * Get the password
		 */
		om_debug_print(OM_DBGLVL_INFO, "User login name set to"
		    "%s\n", lname);

		if (nvlist_lookup_string(uchoices,
		    OM_ATTR_USER_PASSWORD, &upasswd) != 0) {
			/* Password not specified, use default value */
			upasswd = OM_DEFAULT_USER_PASSWORD;
		} else {

			/*
			 * Got user name and password
			 */
			om_debug_print(OM_DBGLVL_INFO, "Got user password\n");
		}
		status  = set_user_name_password(uname, lname, upasswd);
		if (status != 0) {
			om_debug_print(OM_DBGLVL_INFO,
			    "Couldn't set user password data\n");
		}
		/*
		 * Save the login name, it is needed to create user's
		 * home directory
		 */
		save_login_name = strdup(lname);
	}

	if (nvlist_lookup_string(uchoices, OM_ATTR_HOST_NAME,
	    &hostname) != 0) {
		/*
		 * User has cleared default host name for some reason.
		 * NWAM will use dhcp so a dhcp address will become
		 * the host/nodename.
		 */
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_HOST_NAME "
		    "not set,"
		    "User probably cleared default host name\n");

	} else {
		om_debug_print(OM_DBGLVL_INFO, "Hostname set to %s\n",
		    hostname);
		(void) set_hostname_nodename(hostname);
	}

	/*
	 * The .sysIDtool.state file needs to be written before the
	 * install completes. The transfer list is processed
	 * before we return from pfinstall, so update the state
	 * here for install.
	 */
	set_system_state();
	/*
	 * Setup install targets. Set the global orchestrator callback
	 * value for use later. Ick.. this is ugly, but for now, until
	 * TI is finalized we need a way to translate the TI->OM
	 * callbacks.
	 *
	 */
	}
	fprintf(stderr, "Past ti_test\n");
	if (cb) {
		om_cb = cb;
	}
	if (nvlist_alloc(&target_attrs, TI_TARGET_NVLIST_TYPE,
	    0) != 0) {
		om_log_print("Could not create target list.\n");
		return (OM_NO_SPACE);
	}


	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    ROOTPOOL_NAME) != 0) {
		om_log_print("ZFS root pool name could not be added. \n");
		return (OM_NO_SPACE);
	}
	/*
	 * Do fdisk configuration attributes and vtoc slice
	 * configuration attributes.
	 */
	if (slim_set_fdisk_attrs(&target_attrs, name) != 0) {
		om_log_print("Couldn't set fdisk attributes.\n");
		/*
		 * Will be set in function above.
		 */
		nvlist_free(target_attrs);
		return (om_get_error());
	}
	om_log_print("Set fdisk attrs\n");
	if (slim_set_slice_attrs(&target_attrs, name) != 0) {
		om_log_print("Couldn't set slice attributes. \n");
		nvlist_free(target_attrs);
		return (om_get_error());
	}

	snprintf(swap_device, sizeof (swap_device), "/dev/dsk/%ss1", name);
	snprintf(zfs_device, sizeof (zfs_device), "%ss0", name);

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_DEVICE,
	    zfs_device) != 0) {
		om_log_print("Could not set zfs rpool device name\n");
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	om_log_print("Set zfs root pool device\n");
	/*
	 * Start a thread to call TI module.
	 */

	ret = pthread_create(&ti_thread, NULL, do_ti, target_attrs);
	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		return (OM_FAILURE);
	}

	/*
	 * Start the install.
	 */
	if (call_transfer_module(INSTALLED_ROOT_DIR, cb) != OM_SUCCESS) {
		om_log_print("Initial install failed\n");
		status = OM_FAILURE;
		om_set_error(OM_INITIAL_INSTALL_FAILED);
		goto install_return;
	}
	om_debug_print(OM_DBGLVL_INFO, "om_perform_install() returned"
	    " success. The install is started\n");
install_return:
	return (status);
}

/*
 * om_perform_tools_install
 * This function will call the install program that install tools
 * call call_tools_install to setup callback for tools install progress
 * Input:	void *cb - callback function to inform the GUI about
 *		the progress.
 * Output:	None
 * Return:	OM_SUCCESS, if the install program started succcessfully
 *		OM_FAILURE, if the there is a failure
 */

int
om_perform_tools_install(om_callback_t cb)
{
	/*
	 * Call the function to setup separate thread for installer
	 * callbacks.
	 */
	if (call_tools_install(cb) != OM_SUCCESS) {
		om_set_error(OM_INITIAL_INSTALL_FAILED);
		return (OM_FAILURE);
	}
	return (OM_SUCCESS);
}
/*
 * call_transfer_module
 * This function creates the a thread to call the transfer module and
 * another thread to handle callbacks.
 * Input:	target_dir - The mounted directory for alternate root
 *		om_call_back_t *cb - The callback function
 * Output:	None
 * Return:	OM_SUCCESS, if the all threads are started successfully
 *		OM_FAILURE, if the there is a failure
 */
int
call_transfer_module(char *target_dir, om_callback_t cb)
{
	struct icba			*cb_args;
	struct transfer_callback	*tcb_args;
	om_callback_t			tcb;
	int				ret;
	int				i;
	pthread_t			callback_thread;
	pthread_t			transfer_thread;

	if (target_dir == NULL) {
		om_set_error(OM_NO_INSTALL_TARGET);
		return (OM_FAILURE);
	}

	if (fopen(PROGRESS_FILE, "w") == NULL) {
		om_set_error(OM_NO_PROGRESS_FILE);
		return (OM_FAILURE);
	}

	tcb_args = (struct transfer_callback *)
	    calloc(1, sizeof (struct transfer_callback));
	if (tcb_args == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	tcb_args->target = strdup(target_dir);
	if (tcb_args->target == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	tcb_args->cb = tcb;
	/*
	 * Create a thread for running pfinstall
	 */
	ret = pthread_create(&transfer_thread, NULL,
	    do_transfer, (void *)tcb_args);

	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		return (OM_FAILURE);
	}

	/*
	 * If there is no callback, don't create callback thread
	 */
	if (cb != NULL) {
		cb_args = (struct icba *)calloc(1, sizeof (struct icba));
		if (cb_args == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}
		cb_args->install_type = install_type;
		cb_args->pid = pfinstall_pid;
		cb_args->cb = cb;
		/*
		 * Create a thread for handling callback
		 */
		ret = pthread_create(&callback_thread, NULL,
		    handle_install_callback, (void *)cb_args);

		if (ret != 0) {
			om_set_error(OM_ERROR_THREAD_CREATE);
			return (OM_FAILURE);
		}
	}
	return (OM_SUCCESS);
}

void *
do_ti(void *args)
{
	struct ti_callback	*ti_args;
	int			status = 0;
	nvlist_t		*attrs = (nvlist_t *)args;
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;

	ti_args = (struct ti_callback *)
	    calloc(1, sizeof (struct ti_callback));

	if (ti_args == NULL) {
		om_log_print("Couldn't create ti_callback args\n");
		om_set_error(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	nvlist_dup(attrs, &ti_args->target_attrs, 0);
	ti_args->cb = ti_cb;

	if (ti_args->target_attrs == NULL || ti_args->cb == 0) {
		om_log_print("ti_args == NULL\n");
		status = -1;
		pthread_exit((void *)&status);
	}

	status = ti_create_target(ti_args->target_attrs, ti_args->cb);
	if (status != TI_E_SUCCESS) {
		om_log_print("TI process completed unsuccessfully \n");
		ti_done = B_TRUE;
		cb_data.num_milestones = 3;
		cb_data.callback_type = OM_INSTALL_TYPE;
		cb_data.curr_milestone = OM_INVALID_MILESTONE;
		cb_data.percentage_done = OM_TARGET_INSTANTIATION_FAILED;
		om_cb(&cb_data, app_data);
	} else {
		om_log_print("TI process completed successfully \n");
		ti_done = B_TRUE;
		cb_data.num_milestones = 3;
		cb_data.callback_type = OM_INSTALL_TYPE;
		cb_data.curr_milestone = OM_TARGET_INSTANTIATION;
		cb_data.percentage_done = 100;
		om_cb(&cb_data, app_data);
	}
	om_log_print("ti_create_target exited with status = %d\n", status);
	pthread_exit((void *)&status);
}

/*
 * do_transfer
 * This function calls the api to do the actual transfer of install contents
 * from cd/dvd to hard disk
 * Input:	void *arg - Pointer to the parameters needed to call
 *		transfer mdoule. Currently the full path of the alternate root
 *		and callback parameter
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
void *
do_transfer(void *args)
{
	struct transfer_callback	*tcb_args;
	nvlist_t			*transfer_attr;
	int				status;

	/*
	 * If TI isn't complete, sleep and check again. Can't do transfer
	 * until TI is completed.
	 */
	while (ti_done != B_TRUE) {
		om_log_print("TI process not completed, Transfer waiting...\n");
		sleep(5);
	}
	/*
	 * Sleep some more while TI reports progress.
	 */
	om_log_print("TI procesing completed. Beginning transfer service \n");
	sleep(3);

	tcb_args = (struct transfer_callback *)args;

	if (tcb_args->target == NULL) {
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_alloc(&transfer_attr, NV_UNIQUE_NAME, 0) != 0) {
		om_set_error(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}
	if (nvlist_add_string(transfer_attr, TM_ATTR_TARGET_DIRECTORY,
	    tcb_args->target) != 0) {
		nvlist_free(transfer_attr);
		status = -1;
		pthread_exit((void *)&status);
	}

	/*
	 * status = TM_perform_transfer(transfer_attr, tcb_args->cb);
	 */
	status = TM_perform_transfer(transfer_attr, NULL);
	if (status == TM_SUCCESS) {
		/*
		 * We only want to enable nwam  and create user's
		 * login directory for initial install.
		 */
		if (install_type == OM_INITIAL_INSTALL) {
			if (def_locale != NULL)
				(void) om_set_default_locale_by_name(
				    def_locale);

			enable_nwam();
			/*
			 * Create user directory if needed
			 */
			create_user_directory();
		}
		setup_etc_vfstab_for_zfs_root(tcb_args->target);
		setup_users_default_environ(tcb_args->target);
		run_install_finish_script(tcb_args->target);
		reset_zfs_mount_property(tcb_args->target);
		run_installgrub(tcb_args->target, zfs_device);
		transfer_config_files(tcb_args->target);
		/*
		 * Transfer the gui-install.log and the jumpstart
		 * profile to /var/sadm/system/install
		 */
		transfer_log_files(tcb_args->target);

		/*
		 * Take a snapshot of the installation.
		 */
		td_safe_system("/usr/sbin/zfs snapshot -r " ROOTPOOL_SNAPSHOT);

		/*
		 * Notify the caller that install is completed
		 */
		notify_install_complete();
	} else {
		notify_error_status(status);
	}

	nvlist_free(transfer_attr);
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}

/*
 * handle_install_callback
 * This function handle the callbacks while pfinstall is running.
 * The pfinstall writes out the progress information to a file called
 * /tmp/install_update_progress.out, which is passed as an argument to
 * pfinstall. This function parses the data and creates the callback
 * structure and calls the application provided callback function.
 * Input:	void *args - The arguments to initialize the callback.
 *		currently the structure containing install_type, process
 *		id of pfinstall and the callback function are passed.
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
void *
handle_install_callback(void *args)
{
	om_callback_info_t	cb_data;
	struct icba		*cp;
	int			i;
	FILE			*progress_fp = NULL;
	int16_t			status = 0;
	boolean_t		sleep_for_callback = B_TRUE;
	char			buf[1024];
	uintptr_t		app_data = 0;
	int16_t			percent;
	int16_t			prev_percent = 101;
	om_milestone_type_t	milestone;

	cp = (struct icba *)args;

	if (cp->cb == NULL) {
		goto thread_end;
	}

	/*
	 * If the progress file is not available, return an error.
	 */
	if (access(PROGRESS_FILE, R_OK|F_OK) != 0) {
		status = OM_NO_PROGRESS_FILE;
		goto thread_end;
	}

	/*
	 * Open the progress file.
	 */
	progress_fp = fopen(PROGRESS_FILE, "r");
	if (progress_fp == NULL) {
		status = OM_NO_PROGRESS_FILE;
		goto thread_end;
	}

	/*
	 * Callback data was initialized in ti_cb().
	 */
	cb_data.num_milestones = 3;
	cb_data.callback_type = OM_INSTALL_TYPE;
	/*
	 * Loop forever - wait for either the process being monitored to
	 * terminate or for data to be written to the progress file:
	 * - If the process terminates, return from this function.
	 * - If there is data available from the progress file, call
	 *   callback to inform the progress.
	 * Sleep between passes so as not to consume too much cpu.
	 */

	while (sleep_for_callback) {
		/* Sleep 2 seconds between attempts to read progress file */
		(void) sleep(2);

		/* As long as bytes are available, process them */
		while (fgets(buf, sizeof (buf), progress_fp) != NULL) {
			/*
			 * Generate callback
			 */
			milestone = get_the_milestone(buf);
			/*
			 * If install is completed or failed, then we have
			 * to let the caller to know.
			 */
			if (milestone == OM_INSTALLER_FAILED) {
				sleep_for_callback = B_FALSE;
				status = OM_PFINSTALL_FAILURE;
				break;
			} else if (milestone == OM_POSTINSTAL_TASKS) {
				sleep_for_callback = B_FALSE;
				status = OM_SUCCESS;
				break;
			} else if (milestone == OM_INVALID_MILESTONE) {
				continue;
			}
			cb_data.curr_milestone = milestone;
			percent = get_the_percentage(buf);
			/*
			 * Send callback only if the percentage changes
			 */
			if (percent == prev_percent) {
				continue;
			}
			cb_data.percentage_done = percent;
			prev_percent = percent;
			/*
			 * call the callback
			 */
			cp->cb(&cb_data, app_data);
		}
	}

	/*
	 * Either the process being monitored died OR all bytes have been
	 * processed. Close the progress file and return
	 */
thread_end:
	if (progress_fp != NULL) {
		(void) fclose(progress_fp);
	}
	/*
	 * Send a callback indicating that the callbacks are done
	 */
	if (cp->cb) {
		if (status == OM_SUCCESS) {
			/*
			 * Send a callback indicating that the current
			 * milestone is done.
			 */
			cb_data.percentage_done = 100;
			cp->cb(&cb_data, app_data);

			/*
			 * Since pfinstall doesn't account for postinstall
			 * tasks, send a callback to the caller that
			 * post install task is completed.
			 */
			if (!install_test) {
				cb_data.curr_milestone = OM_POSTINSTAL_TASKS;
				cb_data.percentage_done = 100;
				cp->cb(&cb_data, app_data);
			}
		} else {
			/*
			 * Send a callback indication error. The error code
			 * is sent in the place of percentage value
			 */
			cb_data.curr_milestone = OM_INSTALLER_FAILED;
			cb_data.percentage_done = status;
			cp->cb(&cb_data, app_data);
		}
	}
	/*
	 * The args allocated when this thread was created. The creator of this
	 * thread won't be freeing the space allocated for args.
	 */
	free(cp);

	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}

ti_errno_t
ti_cb(nvlist_t *progress)
{

	static om_callback_info_t cb_data;
	uint16_t	ms_curr;
	uint16_t	ms_num;
	uint16_t	ms_perc_done;
	uint16_t	ms_perc;
	uintptr_t	app_data;
	static		boolean_t  first_time = B_TRUE;

	if (progress == NULL) {
		om_log_print("No TI attr data found \n");
		return;
	}

	/*
	 * Initialize callback stuff.
	 */
	fprintf(stderr, "in ti_cb\n");

	if (first_time) {
		cb_data.num_milestones = 3;
		cb_data.callback_type = OM_INSTALL_TYPE;
		cb_data.curr_milestone = OM_TARGET_INSTANTIATION;
		cb_data.percentage_done = 0;
		first_time = B_FALSE;
		om_cb(&cb_data, app_data);
	}

	/*
	 * For TI there are 5 milestones. Split these in to equal
	 * parts for now, then report percentage to caller.
	 */


	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_NUM, &ms_num);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_CURR, &ms_curr);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_PERC_DONE,
	    &ms_perc_done);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_PERC, &ms_perc);

	switch (ms_curr) {
		case TI_MILESTONE_FDISK:
			om_log_print("Creating fdisk partition\n");
			om_log_print("For FDISK creationg ms_perc_done = %d\n",
			    ms_perc_done);
			cb_data.percentage_done = ms_perc_done * .20;
			om_cb(&cb_data, app_data);
			break;
		case TI_MILESTONE_VTOC:
			om_log_print("Creating slices\n");
			om_log_print("For creating VTOC msperc_done = %d\n",
			    ms_perc_done);
			cb_data.percentage_done = ms_perc_done * .40;
			om_cb(&cb_data, app_data);
			break;
		case TI_MILESTONE_ZFS_RPOOL:
			om_log_print("creating zpool\n");
			om_log_print("For creating zpool ms_perc_done = %d\n",
			    ms_perc_done);
			om_log_print("total percent to do = %d\n",
			    ms_perc);
			cb_data.percentage_done = ms_perc_done * .60;
			om_cb(&cb_data, app_data);
			break;
		case TI_MILESTONE_ZFS_FS:
			om_log_print("Creating zfs datasets\n");
			om_log_print("For creating zfs fs ms_perc_done = %d\n",
			    ms_perc_done);
			cb_data.percentage_done = ms_perc_done * .80;
			om_cb(&cb_data, app_data);

			/*
			 * Check for this here since I know the order
			 * of TI processing. This needs to be fixed for
			 * the future XXXX.
			 */
			break;
		default:
			om_log_print("No valid milestone\n");
			cb_data.percentage_done = 0;
			om_cb(&cb_data, app_data);
		}
done:
	if (ms_perc == 100) {
		om_log_print("TI process completed \n");
		ti_done = B_TRUE;
		cb_data.percentage_done = 100;
		om_cb(&cb_data, app_data);
		return (OM_SUCCESS);
	}
}

/*
 * Parsing function to get the percentage value from the string.
 * The string will be like "percent=11"
 * The output is an integer from 0 - 100
 */
int16_t
get_the_percentage(char *str)
{
	char	*ptr, *ptr1;
	int16_t	percent;

	/*
	 * Look for percent="N"
	 */
	ptr = strstr(str, "percent=");
	if (ptr == NULL) {
		return (-1);
	}
	/*
	 * Find where the number is starting
	 */
	while (isdigit(*ptr) == 0) {
		ptr++;
	}
	ptr1 = strchr(ptr, '"');
	if (ptr1 == NULL) {
		return (-1);
	}
	*ptr1 = '\0';

	errno = 0;
	percent = (int16_t)strtol(ptr, (char **)NULL, 10);
	if (errno != 0) {
		/*
		 * Log the information
		 */
		return (-1);
	}
	return (percent);
}

/*
 * Parsing function to get the current milestone
 * and converts it to integer.
 * The string looks like "<progressStatus"
 */
int
get_the_milestone(char *str)
{
	if (strncasecmp(str, PROGRESS_STATUS,
	    strlen(PROGRESS_STATUS)) == 0) {
		return (OM_SOFTWARE_UPDATE);
	}
	if (strncasecmp(str, TARGET_INSTANTIATION_STATUS,
	    strlen(TARGET_INSTANTIATION_STATUS)) == 0) {
		return (OM_TARGET_INSTANTIATION);
	}
	if (strncasecmp(str, POST_INSTALL_STATUS,
	    strlen(POST_INSTALL_STATUS)) == 0) {
		return (OM_POSTINSTAL_TASKS);
	}
	if (strncasecmp(str, UPGRADE_SPACE_CHECK,
	    strlen(UPGRADE_SPACE_CHECK)) == 0) {
		return (OM_UPGRADE_CHECK);
	}
	if (strncasecmp(str, INSTALLER_FAILED,
	    strlen(INSTALLER_FAILED)) == 0) {
		return (OM_INSTALLER_FAILED);
	}
	return (OM_INVALID_MILESTONE);
}

/*
 * call_tools_install
 * This function creates the a thread to execute the pfinstall command and
 * another thread to handle callbacks.
 * Input: 	om_call_back_t *cb - The callback function
 * Output:	None
 * Return:	OM_SUCCESS, if the all threads are started successfully
 *		OM_FAILURE, if the there is a failure
 */
int
call_tools_install(om_callback_t cb)
{
	pthread_t	callback_thread;
	struct icba	*cb_args;
	int		ret;
	int		i;

	/*
	 * If there is no callback, don't create callback thread
	 */
	if (cb != NULL) {
		cb_args = calloc(1, sizeof (struct icba));
		if (cb_args == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}

		cb_args->pid = 1;
		cb_args->cb = cb;
		/*
		 * Create a thread for handling callback
		 */
		ret = pthread_create(&callback_thread, NULL,
		    handle_tools_install_callback, (void *)cb_args);
		if (ret != 0) {
			om_set_error(OM_ERROR_THREAD_CREATE);
			return (OM_FAILURE);
		}
	}
	return (OM_SUCCESS);
}

/*
 * handle_tools_install_callback
 * This function handle the callbacks while tools install is running.
 * Input:	void *args - The arguments to initialize the callback.
 *		currently the structure containing install_type, process
 *		id and the callback function are passed.
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
void *
handle_tools_install_callback(void *args)
{
	om_callback_info_t	cb_data;
	struct icba		*cp;
	int16_t			status = 0;
	boolean_t		sleep_for_callback = B_TRUE;
	uintptr_t		app_data = 0;

	cp = (struct icba *)args;

	/*
	 * Initialize the callback param
	 */
	cb_data.callback_type = OM_TOOLS_INSTALL_TYPE;
	cb_data.num_milestones = 3;
	(void) sleep(10);

	/*
	 * Send a callback indicating that the callbacks are done
	 */
	cb_data.curr_milestone = OM_TOOLS_JAVAAPPSVR;
	cb_data.percentage_done = 100;
	cp->cb(&cb_data, app_data);

	/*
	 * The args allocated when this thread was created. The creator of this
	 * thread won't be freeing the space allocated for args.
	 */
	free(cp);

	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}

int
set_root_password(char *e_passwd)
{
	return (set_password_common(NULL, ROOT_NAME, e_passwd));
}

int
set_user_name_password(char *user, char *login, char *e_passwd)
{
	return (set_password_common(user, login, e_passwd));
}

int
set_password_common(char *user, char *login, char *e_passwd)
{

	char		*name, *pw, *uid, *gid, *gcos, *path, *shell;
	char		*last, *min, *max, *warn, *inactive, *expire, *flag;
	int		ret_stat, len;
	char		*userpath = NULL;
	Table		*tbl;
	Db_error	*db_err;
	char		*tmp_login;

	/*
	 * A user can set a login name with no password.
	 */

	if (login == NULL) {
		om_set_error(OM_INVALID_USER);
		return (OM_FAILURE);
	}

	tmp_login = strdup(login);
	if (tmp_login == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	tbl = table_of_type(DB_PASSWD_TBL);
	ret_stat = lcl_list_table(DB_NS_UFS, NULL, NULL,
	    DB_DISABLE_LOCKING | DB_LIST_SHADOW | DB_LIST_SINGLE,
	    &db_err, tbl, login, &name, &pw, &uid,
	    &gid, &gcos, &path, &shell, &last, &min,
	    &max, &warn, &inactive, &expire, &flag);

	if (ret_stat == -1) {
		om_log_print(db_err->msg);
	}

	if (ret_stat != 0 || gid == NULL) {
		if (strcmp(login, ROOT_NAME) == 0)
			gid = ROOT_GID;
		else {
			gid = USER_GID;
			uid = USER_UID;
			shell = "/bin/bash";
		}
	}

	if (ret_stat != 0 || path == NULL) {
		if (strcmp(login, ROOT_NAME) == 0)
			path = ROOT_PATH;
		else {
			len = strlen(USER_PATH) + strlen(login) + 1;
			userpath = (char *)malloc(len);
			if (userpath == NULL) {
				om_debug_print(OM_DBGLVL_ERR,
				    "Could not allocate space for "
				    "user path.\n");
				om_set_error(OM_NO_SPACE);
				free(tmp_login);
				return (OM_FAILURE);
			}
			(void) memset(userpath, 0, len);
			(void) snprintf(userpath, len, "%s%s", USER_PATH,
			    login);
			path = userpath;
		}
	}
	if (user != NULL && user[0] != '\0') {
		gcos = user;
	}
	/*
	 * We are guaranteed a root entry in the /etc/passwd file for
	 * initial install. So, the data will be returned for some of
	 * the fields we use, such as name, or gid, or shell.
	 */
	if (strcmp(login, ROOT_NAME) == 0) {
		ret_stat = lcl_set_table_entry(DB_NS_UFS, NULL, NULL,
		    DB_ADD_MODIFY,  &db_err, tbl, ROOT_NAME,
		    &name, &e_passwd, &uid, &gid, &user, &path,
		    &shell, &last, &min, &max, &warn, &inactive,
		    &expire, &flag);
	} else {
		ret_stat = lcl_set_table_entry(DB_NS_UFS, NULL, NULL,
		    DB_ADD_MODIFY, &db_err, tbl,
		    &login, &login, &e_passwd, &uid, &gid, &gcos, &path,
		    &shell, &last, &min, &max, &warn, &inactive,
		    &expire, &flag);
	}

	if (ret_stat == -1) {
		om_log_print("Could not set user password table\n");
		om_set_error(OM_SET_USER_FAIL);
		return (OM_FAILURE);
	}
	om_log_print("Set user %s in password and shadow file\n", login);
	free_table(tbl);
	return (OM_SUCCESS);
}

int
set_hostname_nodename(char *hostname)
{

	if (hostname == NULL) {
		om_set_error(OM_INVALID_NODENAME);
		return (OM_FAILURE);
	}
	/*
	 * Both the hostname and nodename will be the same.
	 */
	if (replace_db(NODENAME, hostname) != 0) {
		om_set_error(OM_SET_NODENAME_FAILURE);
		return (OM_FAILURE);
	}

	if (chmod(NODENAME, S_IRUSR | S_IRGRP | S_IROTH) != 0) {
		om_set_error(OM_SET_NODENAME_FAILURE);
		return (OM_FAILURE);
	}

	/*
	 * hostname needs to be aliased to loghost in /etc/hosts file.
	 */
	(void) set_net_hostname(hostname);
	return (OM_SUCCESS);
}

/*ARGSUSED*/
uint64_t
om_get_min_size(char *media, char *distro)
{
	/*
	 * Size in MB that is the minimum device size we will allow
	 * for installing Slim.
	 */
	return (4096);
}

char *
om_encrypt_passwd(char *passwd, char *username)
{
	char	*e_pw = NULL;
	char	*saltc;
	struct 	passwd	*u_pw = NULL;

	u_pw = getpwnam(username);
	if (u_pw == NULL) {
		u_pw = malloc(sizeof (struct passwd));
		if (u_pw == NULL) {
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}
		u_pw->pw_name = strdup(username);
		if (u_pw->pw_name == NULL) {
			free((void *)u_pw);
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}
	}
	saltc = crypt_gensalt(NULL, u_pw);
	if (saltc == NULL) {
		free((void *)u_pw->pw_name);
		free((void *)u_pw);
		om_set_error(errno);
		return (NULL);
	}

	e_pw = crypt((const char *)passwd, saltc);
	return (e_pw);
}

static int
set_net_hostname(char *hostname)
{
	char	aliases[MAXHOSTNAMELEN + MAXHOSTNAMELEN + 5];
	char	*aliasp;
	int	status = 0;
	char	entry[256];

	(void) strcpy(aliases, LOG_HOST);
	(void) strcat(aliases, " ");
	(void) strcat(aliases, hostname);
	aliasp = aliases;

	(void) snprintf(entry, sizeof (entry), "%s\t%s\t%s\n", LOOPBACK_IP,
	    hostname, UN(aliasp));
	status = set_entry(HOSTS_TABLE, hostname, entry, "/");
	if (status != 0) {
		om_log_print("Could not write hosts file\n");
		om_set_error(OM_CANT_WRITE_FILE);
		return (OM_FAILURE);
	}
	return (OM_SUCCESS);
}

/*ARGSUSED*/
static int
set_entry(char *table, char *key, char *val, char *rootdir)
{
	FILE 	*rfp, *wfp;
	char 	tmpname[128], table_name[128], buff[1024], dup[1034];
	char	command[1024];
	char 	*p;
	int 	fld, keypos, done = 0;
	int	status = 0;

	(void) snprintf(tmpname, sizeof (tmpname), "/tmp/orch%d",
	    getpid());
	if ((wfp = fopen(tmpname, "w")) == NULL)  {
		om_log_print("Can't open file %s\n", tmpname);
		om_set_error(OM_CANT_OPEN_FILE);
		return (OM_FAILURE);
	}
	(void) snprintf(table_name, sizeof (table_name),
	    "%s", table);

	if ((rfp = fopen(table_name, "r")) != NULL) {
		keypos = 1;

		while (fgets(buff, 1024, rfp) == buff) {
			(void) strcpy(dup, buff);
			p = strtok(buff, " \t\n");

			for (fld = 0; fld < keypos; fld++) {
				p = strtok(NULL, " \t\n");
			}
			if (p && strcmp(p, key) == 0) {
				if (fputs(val, wfp) == EOF)
					break;
				done = 1;
			}
		}
		(void) fclose(rfp);
	}
	if (!done) {
		om_debug_print(OM_DBGLVL_INFO,
		    "Didn't write data to table = %s\n", table_name);
		(void) fputs(val, wfp);
	}
	(void) fclose(wfp);

	/*
	 * For slim we cannot rename. Differnt devices.
	 */

	om_log_print("copying table %s to %s\n", tmpname, table_name);

	snprintf(command, 1024, "/bin/cp %s %s", tmpname, table_name);
	if (system(command) != 0) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Cannot cp table %s\n", tmpname);
		om_debug_print(OM_DBGLVL_ERR,
		    "copy error = %s\n", strerror(errno));
		return (OM_FAILURE);
	}
	return (OM_SUCCESS);
}
static void
set_system_state(void)
{
	sys_config	sysconfig;

	sysconfig.configured = 1;
	sysconfig.bootparamed = 1;
	sysconfig.networked = 1;
	sysconfig.extnetwork = 1;
	sysconfig.autobound = 1;
	sysconfig.subnetted = 1;
	sysconfig.passwdset = 1;
	sysconfig.localeset = 1;
	sysconfig.security = 1;
	sysconfig.nfs4domain = 1;
	(void) sprintf(sysconfig.termtype, "sun");

	write_sysid_state(&sysconfig);

}

static int
replace_db(char *name, char *value)
{

	FILE 	*ifp, *ofp;	/* Input & output files */
	int	tmp;
	char	*tmpdir;	/* Temp file name and location */
	char 	*tdb;

	/*
	 * Generate temporary file name to use.  We make sure it's in the same
	 * directory as the db we're processing so that we can use rename to
	 * do the replace later.  Otherwise we run the risk of being on the
	 * wrong filesystem and having rename() fail for that reason.
	 */
	if (name == NULL || value == NULL) {
		om_debug_print(OM_DBGLVL_INFO,
		    "Invalid values for replacing db\n");
		return (OM_FAILURE);
	}
	tdb = strdup(name);
	if (tdb == NULL) {
		om_set_error(OM_NO_SPACE);
		om_log_print("Could not allocate space for %s\n", name);
		return (OM_FAILURE);
	}
	if (trav_link(&tdb) == -1) {
		om_set_error(OM_NO_SUCH_DB_FILE);
		om_log_print("Couldn't fine db file %s\n", name);
		return (OM_FAILURE);
	}

	tmpdir = (char *)malloc(strlen(tdb) + 7);
	if (tmpdir == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	(void) memset(tmpdir, 0, strlen(tdb) + 7);

	(void) snprintf(tmpdir, strlen(tdb), "%s", tdb);
	(void) strcat(tmpdir, "XXXXXX");
	if ((tmp = mkstemp(tmpdir)) == -1) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Can't create temp file for replacing db\n");
		om_set_error(OM_CANT_CREATE_TMP_FILE);
		free(tmpdir);
		return (OM_FAILURE);
	}

	ofp = fdopen(tmp, "w");
	if (ofp == NULL) {
		om_set_error(OM_CANT_CREATE_TMP_FILE);
		return (OM_FAILURE);
	}

	if (fprintf(ofp, "%s\n", value) == EOF) {
		om_set_error(OM_CANT_WRITE_TMP_FILE);
		(void) fclose(ofp);
		return (OM_FAILURE);
	}

	/* Quick check to make sure we have read & write rights to the file */
	if ((ifp = fopen(tdb, "w")) != NULL)
		(void) fclose(ifp);
	else if (errno != ENOENT) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Cannot open file to rename to\n");
		return (OM_FAILURE);
	}
	(void) fclose(ofp);

	if (rename(tmpdir, tdb) != 0) {
		free(tmpdir);
		om_set_error(OM_SETNODE_FAILURE);
		om_debug_print(OM_DBGLVL_ERR,
		    "Could not rename file %s to %s\n", tmp, name);
		return (OM_FAILURE);
	}
	return (OM_SUCCESS);
}

static char *
find_state_file()
{
	char *path;

	if (state_file_path == NULL) {
		path = STATE_FILE;
		if (trav_link(&path) == 0) {
			state_file_path = strdup(path);
			if (state_file_path == NULL) {
				om_set_error(OM_NO_SPACE);
				return (NULL);
			}
			om_debug_print(OM_DBGLVL_INFO,
			    "State file changing = %s\n", state_file_path);
		} else {
			state_file_path = STATE_FILE;
			om_debug_print(OM_DBGLVL_INFO,
			    "State file changing = %s\n", state_file_path);
		}
	}

	om_debug_print(OM_DBGLVL_INFO,
	    "sydIDtool.state file is %s\n", state_file_path);
	return (state_file_path);
}

static int
trav_link(char **path)
{
	static char	newpath[MAXPATHLEN];
	char 		lastpath[MAXPATHLEN];
	int 		len;
	char 		*tp;

	(void) strcpy(lastpath, *path);
	while ((len = readlink(*path, newpath, sizeof (newpath))) != -1) {
		newpath[len] = '\0';
		if (newpath[0] != '/') {
			tp = strdup(newpath);
			if (tp == NULL) {
				om_set_error(OM_NO_SPACE);
				om_debug_print(OM_DBGLVL_ERR,
				    "Could not allocate space for "
				    "%s\n", newpath);
				return (OM_FAILURE);
			}
			remove_component(lastpath);
			(void) snprintf(newpath, sizeof (newpath), "%s/%s",
			    lastpath, tp);
			free(tp);
		}
		(void) strcpy(lastpath, newpath);
		*path = newpath;
	}
	/* XXX why is this so? XXX */
	if (errno == ENOENT || errno == EINVAL)
		return (OM_SUCCESS);
	return (OM_FAILURE);
}

static void
remove_component(char *path)
{
	char	*p;

	p = strrchr(path, '/');	/* find last '/' */
	if (p == NULL) {
		*path = '\0';
	} else {
		*p = '\0';
	}
}

static void
write_sysid_state(sys_config *sysconfigp)
{
	mode_t	cmask;	/* Current umask */
	FILE	*fp;
	char	*file = NULL;

	cmask = umask((mode_t)022);
	file = find_state_file();
	if (file == NULL) {
		om_set_error(OM_CANT_OPEN_FILE);
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not find sysidtool.state file\n");
		return;
	}

	fp = fopen(file, "w");
	(void) umask(cmask);

	if (fp == NULL) {
		om_debug_print(OM_DBGLVL_WARN,
		    "sysIDtool %s couldn't open: "
		    "errno = %d\n", find_state_file(), errno);
		return;
	}
	/*
	 * Write each state component.
	 */
	(void) fprintf(fp, "%d\t%s\n", sysconfigp->configured,
	    "# System previously configured?");
	om_debug_print(OM_DBGLVL_INFO, "write ( configured): %d\n",
	    sysconfigp->configured);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->bootparamed,
	    "# Bootparams succeeded?");
	om_debug_print(OM_DBGLVL_INFO, "write (bootparamed): %d\n",
	    sysconfigp->bootparamed);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->networked,
	    "# System is on a network?");
	om_debug_print(OM_DBGLVL_INFO, "write (  networked): %d\n",
	    sysconfigp->networked);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->extnetwork,
	    "# Extended network information gathered?");
	om_debug_print(OM_DBGLVL_INFO, "write (ext network): %d\n",
	    sysconfigp->extnetwork);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->autobound,
	    "# Autobinder succeeded?");
	om_debug_print(OM_DBGLVL_INFO, "write (  autobound): %d\n",
	    sysconfigp->autobound);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->subnetted,
	    "# Network has subnets?");
	om_debug_print(OM_DBGLVL_INFO, "write (  subnetted): %d\n",
	    sysconfigp->subnetted);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->passwdset,
	    "# root password prompted for?");
	om_debug_print(OM_DBGLVL_INFO, "write (     passwd): %d\n",
	    sysconfigp->passwdset);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->localeset,
	    "# locale and term prompted for?");
	om_debug_print(OM_DBGLVL_INFO, "write (     locale): %d\n",
	    sysconfigp->localeset);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->security,
	    "# security policy in place");
	om_debug_print(OM_DBGLVL_INFO, "write (   security): %d\n",
	    sysconfigp->security);

	(void) fprintf(fp, "%d\t%s\n", sysconfigp->nfs4domain,
	    "# NFSv4 domain configured");
	om_debug_print(OM_DBGLVL_INFO, "write ( nfs4domain): %d\n",
	    sysconfigp->nfs4domain);
	/*
	 * N.B.: termtype MUST be the last entry in sysIDtool.state,
	 * as suninstall.sh tails this file to get the TERM env variable.
	 */
	(void) fprintf(fp, "%s\n", sysconfigp->termtype);
	om_debug_print(OM_DBGLVL_INFO, "write (       term): %s\n",
	    sysconfigp->termtype);

	(void) fclose(fp);
}

static void
add_shortloc(const char *locale, FILE *fp)
{
	struct _shortloclist    *p = NULL;

	for (p = shortloclist; p->shortloc != NULL; p++) {
		if (strncmp(p->shortloc, locale, strlen(p->shortloc)) == 0) {
			if (p->added == B_FALSE) {
				(void) fprintf(fp, "locale %s\n", p->shortloc);
				p->added = B_TRUE;
			}
			break;
		}
	}
}

static void
init_shortloclist(void)
{
	struct _shortloclist    *p = NULL;
	for (p = shortloclist; p->shortloc != NULL; p++) {
		p->added = B_FALSE;
	}
}

/*
 * Write to the pfinstall progress file that there is an error.
 * A callback will be sent to the caller with the error number
 */
static	void
notify_error_status(int	status)
{
	FILE	*fp;

	fp = fopen(PROGRESS_FILE, "a");
	if (fp != NULL) {
		(void) fprintf(fp,
		    "%s" \
		    " source=\"orchestrator\"" \
		    " type=\"install-failure\"" \
		    " percent=\"%d\" />\n",
		    INSTALLER_FAILED, (int)status);
		/* WRITE it out */
		(void) fclose(fp);
	}
}

/*
 * Write to the install progress file that install is completed
 */
static	void
notify_install_complete()
{
	FILE	*fp;

	fp = fopen(PROGRESS_FILE, "a");
	if (fp != NULL) {
		(void) fprintf(fp,
		    "%s" \
		    " source=\"orchestrator\"" \
		    " type=\"solaris-install\"" \
		    " percent=\"100\" />\n",
		    POST_INSTALL_STATUS);
		/* WRITE it out */
		(void) fclose(fp);
	}
}

/*
 * Execute nwam_script to enable NetWork Auto Magic.
 */
static void
enable_nwam()
{
	char	cmd[MAXPATHLEN];

	(void) snprintf(cmd, sizeof (cmd), "%s", "/sbin/enable_nwam");
	if (system(cmd) == 0) {
		om_debug_print(OM_DBGLVL_INFO, "Nwam is enabled\n");
		om_log_print("Enabled Nwam for first" " reboot\n");
	} else {
		om_debug_print(OM_DBGLVL_ERR, "Nwam is not enabled\n");
		om_log_print("Could not enable nwam\n");
	}
}

/*
 * Create user directory if user is added successfully
 * uid, gid are predefined. The user directory will be created in
 * /export/home. The user directory will be /export/home/<login_name>
 */
static void
create_user_directory()
{
	if (save_login_name != NULL) {
		char	homedir[MAXPATHLEN];
		int	ret;

		(void) snprintf(homedir, sizeof (homedir),
		    "%s/%s/%s", INSTALLED_ROOT_DIR, EXPORT_FS, save_login_name);
		ret = mkdir(homedir, S_IRWXU | S_IRWXG | S_IRWXO);
		if (ret) {
			om_debug_print(OM_DBGLVL_WARN,
			    HOMEDIR_CREATE_FAILED, homedir, ret);
			om_log_print(HOMEDIR_CREATE_FAILED, homedir, ret);
		} else {
			/*
			 * Home directory is successfully created.
			 * Change the ownership to the newly created user
			 */
			uid_t uid;
			gid_t gid;

			uid = (uid_t)strtol(USER_UID, (char **)NULL, 10);
			gid = (gid_t)strtol(USER_GID, (char **)NULL, 10);
			if (uid != 0 && gid != 0) {
				(void) chown(homedir, uid, gid);
			} else {
				om_debug_print(OM_DBGLVL_WARN,
				    "cannot change ownership of %s to %d:%d",
				    homedir, uid, gid);
			}
		}
	}
}

/*
 * Copy the gui-install.log, transfer_log and install_log created for install
 * to /var/sadm/system/install
 */
static void
transfer_log_files(char *target)
{
	char	cmd[MAXPATHLEN];
	DIR	*dirp;
	int	ret;

	if (target == NULL) {
		return;
	}

	/*
	 * Check whether the target directory /a/var/sadm/install/logs
	 * exists. If not create it
	 */
	errno = 0;
	(void) snprintf(cmd, sizeof (cmd), "%s/%s",
	    target, INSTALL_LOG_DIRECTORY);
	dirp = opendir(cmd);
	if (dirp == NULL) {
		/*
		 * Create and set the directory permission to 755
		 */
		ret = mkdir(cmd,
		    S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH);
		if (ret) {
			om_log_print(NSI_LOG_DIR_FAILED, cmd);
			return;
		}
	} else {
		(void) closedir(dirp);
	}

	/*
	 * install_log and gui-install_log are at /tmp
	 */
	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp /tmp/%s %s/%s > /dev/null",
	    INSTALL_LOG, target, INSTALL_LOG_DIRECTORY);
	om_log_print("%s\n", cmd);
	td_safe_system(cmd);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp /tmp/%s %s/%s > /dev/null",
	    GUI_INSTALL_LOG, target, INSTALL_LOG_DIRECTORY);
	om_log_print("%s\n", cmd);
	td_safe_system(cmd);

	/*
	 * The transfer.log is created at /a
	 */
	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp %s/%s %s/%s > /dev/null",
	    target, TRANSFER_LOG, target, INSTALL_LOG_DIRECTORY);
	om_log_print("%s\n", cmd);
	td_safe_system(cmd);
}

static void
read_and_save_locale(char *path)
{
	char lc_collate[MAX_LOCALE];
	char lc_ctype[MAX_LOCALE];
	char lc_messages[MAX_LOCALE];
	char lc_monetary[MAX_LOCALE];
	char lc_numeric[MAX_LOCALE];
	char lc_time[MAX_LOCALE];
	char lang[MAX_LOCALE];
	FILE 	*tmpfp = NULL;
	FILE	*deffp = NULL;

	if (path[0] == '\0')
		return;

	tmpfp = fopen(path, "r");
	if (tmpfp == NULL)
		return;

	(void) read_locale_file(tmpfp, lang, lc_collate, lc_ctype,
	    lc_messages, lc_monetary, lc_numeric, lc_time);

	(void) fclose(tmpfp);

	deffp = fopen(TMP_DEFSYSLOC, "w");
	if (deffp == NULL) {
		return;
	}

	/*
	 * Don't care about error. If error, then system will behave
	 * as it does currently during SUUpgrade.
	 */
	fprintf(deffp, "%s\n", lc_ctype);
	(void) fclose(deffp);
}

static void
umount_tmp(char *path)
{
	char cmd[MAXPATHLEN];

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/umount -f %s > /dev/null 2>&1", path);

	td_safe_system(cmd);
}

/*
 * Setup legacy mount for zfs root in /etc/vfstab
 */
static void
setup_etc_vfstab_for_zfs_root(char *target)
{
	FILE	*fp;
	char	cmd[MAXPATHLEN];

	if (target == NULL) {
		return;
	}

	om_log_print("Setting up zfs legacy mount in /etc/vfstab\n");
	(void) snprintf(cmd, sizeof (cmd), "%s/etc/vfstab", target);

	fp = fopen(cmd, "a+");
	if (fp == NULL) {
		om_log_print("Cannot open %s to add zfs root\n", cmd);
		return;
	}
	(void) fprintf(fp, "%s/%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n",
		ROOTPOOL_NAME,"root", "-", "/", "zfs", "-", "no", "-");

	om_log_print("Setting up swap mount in /etc/vfstab\n");

	(void) fprintf(fp, "%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n",
		swap_device, "-", "-", "swap", "-", "no", "-");

	(void) fclose(fp);
}

static void
setup_users_default_environ(char *target)
{
	char	cmd[MAXPATHLEN];
	char	*profile = "/jack/.profile";
	char	*bashrc	= ".bashrc";
	char	*home = "export/home";

	/*
	 * copy the .profile from user jack to the users home directory
	 * and make it the users .bashrc
	 */
	if (target == NULL) {
		return;
	}

	if (save_login_name != NULL) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/^PATH/%s &/' %s >%s/%s/%s/%s",
		    "export", profile, target, home, save_login_name, bashrc);
		om_log_print("%s\n", cmd);
		td_safe_system(cmd);
	}
}

/*
 * Setup mount property back to / from /a for /var, /usr, /export,
 * /export/home and /opt
 */
static void
reset_zfs_mount_property(char *target)
{
	char *zfs_fs_names[3] = {"opt", "export/home", "export"};
	char cmd[MAXPATHLEN];
	int i;

	if (target == NULL) {
		return;
	}

	om_log_print("Changing zfs mount property from /a to /\n");
	/*
	 * Unmount the file systems
	 */
	for (i = 0; i < 3; i++) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/umount %s/%s > /dev/null",
		    target, zfs_fs_names[i]);
		om_log_print("%s\n", cmd);
		td_safe_system(cmd);
	}
	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/umount %s > /dev/null", target);
	om_log_print("%s\n", cmd);
	td_safe_system(cmd);

	for (i = 0; i < 3; i++) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs set mountpoint=/%s %s/%s > /dev/null",
		    zfs_fs_names[i], ROOTPOOL_NAME, zfs_fs_names[i]);
		om_log_print("%s\n", cmd);
		td_safe_system(cmd);
	}
}

/*
 * Execute install-finish script to setup the system to boot the installed
 * Solaris
 */
static void
run_install_finish_script(char *target)
{
	char cmd[MAXPATHLEN];
	char	*tool = "/sbin/install-finish";

	if (target == NULL) {
		return;
	}
	om_log_print("Running install-finish script\n");
	if (access(tool, F_OK) == 0) {
		(void) snprintf(cmd, sizeof (cmd),
		    "%s %s initial_install" \
		    " > /dev/null 2>&1", tool, target);
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/root/installer/install-finish %s initial_install" \
		    " > /dev/null 2>&1", target);
	}

	om_log_print("%s\n", cmd);
	td_safe_system(cmd);
}

/*
 * Execute installgrub to setup MBR
 * Solaris
 */
static void
run_installgrub(char *target, char *device)
{
	char cmd[MAXPATHLEN];

	if (target == NULL || device == NULL) {
		return;
	}
	om_log_print("Running installgrub to set MBR\n");
	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/installgrub %s/boot/grub/stage1" \
	    " %s/boot/grub/stage2 /dev/rdsk/%s" \
	    " > /dev/null 2>&1",
	    target, target, device);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd);
}

/*
 * Copy the modified (during install) configuration files to the target
 * Similar to transfer_list functionality of old installer
 */
static void
transfer_config_files(char *target)
{
	char cmd[MAXPATHLEN];
	char *passwd = "/etc/passwd";
	char *shadow = "/etc/shadow";
	char *user_attr = "/etc/user_attr";
	char *hosts = "/etc/inet/hosts";

	if (target == NULL) {
		return;
	}

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/sed -e '/^jack/d' %s >%s%s",
	    passwd, target, passwd);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/sed -e '/^jack/d' %s >%s%s",
	    shadow, target, shadow);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd);

	if (save_login_name != NULL) {
		/* Make user a primary administrator */
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/^jack/%s/' %s >%s%s",
		    save_login_name, user_attr, target, user_attr);
	} else {
		/*
		 * Clear out jack, and switch root out of being a role since
		 * no other user has been created
		 */
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e '/^jack/d' -e 's/type=role;//' %s >%s%s",
		    user_attr, target, user_attr);
	}
	om_log_print("%s\n", cmd);
	td_safe_system(cmd);
	free(save_login_name);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp %s %s%s > dev/null 2>&1",
	    hosts, target, hosts);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd);
}
