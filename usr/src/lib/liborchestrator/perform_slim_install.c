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
#include <wait.h>

#include "td_lib.h"
#include "cl_database_parms.h"
#include "admldb.h"

#include "orchestrator_private.h"
#include <transfermod.h>

#include <ls_api.h>


/*
 * Start of code to address temporary set hostid fix.
 *
 * The below section of code will be used temporarily set the hostid.
 *
 * A more permanent fix to provide hostid is being worked. Once that fix
 * is available this code should be removed.
 */
#include <elf.h>
#include <libelf.h>
#include <utime.h>
#include <sys/systeminfo.h>
#include <sys/time.h>

static void	setup_hostid(char *target);

typedef enum machine_type {
	MT_UNDEFINED = -1,
	MT_STANDALONE = 0,
	MT_SERVER = 1,
	MT_DATALESS = 2,
	MT_DISKLESS = 3,
	MT_SERVICE = 4,
	MT_CCLIENT = 5
} MachineType;

/* common path names */
#define	IDKEY		"/kernel/misc/sysinit"
#define	IDKEY64		"/kernel/misc/amd64/sysinit"

/*
 * Return status constants
 */
#define	NOERR		0
#define	ERROR		1

/*
 * End of code to address temporary set hostid fix.
 */

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
};

/*
 * Global Variables
 */
static	boolean_t	install_test = B_FALSE;
static	char		*state_file_path = NULL;
om_install_type_t	install_type;
static	char		*save_login_name = NULL;
static	char		*def_locale;
static	pthread_t	ti_thread;
static	int		ti_ret;
static	MachineType	machinetype = MT_STANDALONE;

om_callback_t		om_cb;
char			zfs_device[MAXDEVSIZE];
char			swap_device[MAXDEVSIZE];
char			*zfs_fs_names[ZFS_FS_NUM] = {"/", "/opt"};
char			*zfs_shared_fs_names[ZFS_SHARED_FS_NUM] =
	{"/export", "/export/home"};

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

image_info_t	image_info = {B_FALSE, 4096, 1.0, "off"};
int		tm_percentage_done = 0;

/*
 * local functions
 */


static void	add_shortloc(const char *locale, FILE *fp);
static char 	*find_state_file();
static void	init_shortloclist(void);
static void	read_and_save_locale(char *path);
static void	remove_component(char *path);
static int	replace_db(char *name, char *value);
static int 	set_net_hostname(char *hostname);
static void 	set_system_state(void);
static int	trav_link(char **path);
static void 	write_sysid_state(sys_config *sysconfigp);
static void	notify_error_status(int status);
static void	notify_install_complete();
static void	create_user_directory();
static int	call_transfer_module(char *target_dir, om_callback_t cb);
static void	run_install_finish_script(char *target);
static void 	setup_users_default_environ(char *target);
static void	setup_etc_vfstab_for_zfs_root(char *target);
static void	reset_zfs_mount_property(char *target);
static void	activate_be(char *be_name);
static void	run_installgrub(char *target, char *device);
static void	transfer_config_files(char *target);
static void	handle_TM_callback(const int percent, const char *message);
static int	prepare_zfs_root_pool_attrs(nvlist_t **attrs, char *disk_name);
static int	prepare_be_attrs(nvlist_t **attrs);
static int	obtain_image_info(image_info_t *info);
static char	*get_rootpool_id(char *rpool_name);
static void	set_machinetype(MachineType);
static MachineType get_machinetype(void);

void 		*do_transfer(void *arg);
void		*do_ti(void *args);

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
	int		status = OM_SUCCESS;
	nvlist_t	*target_attrs = NULL;
	uint8_t		type;
	char		*ti_test = getenv("TI_SLIM_TEST");
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
	if (nvlist_lookup_string(uchoices, OM_ATTR_DISK_NAME, &name) != 0) {
		om_debug_print(OM_DBGLVL_ERR, "No install target\n");
		om_set_error(OM_NO_INSTALL_TARGET);
		return (OM_FAILURE);
	}

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
			om_log_print("Couldn't create user account\n");
			return (OM_FAILURE);
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
	if (cb) {
		om_cb = cb;
	}
	if (nvlist_alloc(&target_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		om_log_print("Could not create target list.\n");
		return (OM_NO_SPACE);
	}

	/*
	 * Set fdisk configuration attributes
	 */
	if (slim_set_fdisk_attrs(target_attrs, name) != 0) {
		om_log_print("Couldn't set fdisk attributes.\n");
		/*
		 * Will be set in function above.
		 */
		nvlist_free(target_attrs);
		return (om_get_error());
	}
	om_log_print("Set fdisk attrs\n");

	/*
	 * set swap device name
	 */

	snprintf(swap_device, sizeof (swap_device), "/dev/dsk/%ss1", name);

	/*
	 * if there is a root pool imported with name which will be finally
	 * picked up by installer for target root pool, there is nothing
	 * we can do at this point. Log warning message and exit.
	 */

	ret = td_safe_system("/usr/sbin/zpool list " ROOTPOOL_NAME, B_TRUE);
	if ((ret == -1) || WEXITSTATUS(ret) != 0) {
		om_debug_print(OM_DBGLVL_INFO, "Root pool " ROOTPOOL_NAME
		    " doesn't exist\n");
	} else {
		om_log_print("Root pool " ROOTPOOL_NAME " exists,"
		    " we can't proceed with the installation\n");

		om_set_error(OM_ZFS_ROOT_POOL_EXISTS);
		return (OM_FAILURE);
	}

	/*
	 * Start a thread to call TI module for fdisk & vtoc targets.
	 */

	ti_ret = pthread_create(&ti_thread, NULL, do_ti, target_attrs);
	if (ti_ret != 0) {
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
 * call_transfer_module
 * This function creates the a thread to call the transfer module
 * Input:	target_dir - The mounted directory for alternate root
 *		om_call_back_t *cb - The callback function
 * Output:	None
 * Return:	OM_SUCCESS, if the all threads are started successfully
 *		OM_FAILURE, if the there is a failure
 */
static int
call_transfer_module(char *target_dir, om_callback_t cb)
{
	struct transfer_callback	*tcb_args;
	int				ret;
	pthread_t			transfer_thread;

	if (target_dir == NULL) {
		om_set_error(OM_NO_INSTALL_TARGET);
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
	/*
	 * Create a thread for running Transfer Module
	 */
	ret = pthread_create(&transfer_thread, NULL,
	    do_transfer, (void *)tcb_args);

	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		return (OM_FAILURE);
	}

	return (OM_SUCCESS);
}

void *
do_ti(void *args)
{
	struct ti_callback	*ti_args;
	static int		status = 0;
	ti_errno_t		ti_status;
	nvlist_t		*attrs = (nvlist_t *)args;
	om_callback_info_t	cb_data;
	uintptr_t		app_data = 0;
	char			*disk_name;
	nvlist_t		*ti_ex_attrs;

	ti_args = (struct ti_callback *)
	    calloc(1, sizeof (struct ti_callback));

	if (ti_args == NULL) {
		om_log_print("Couldn't create ti_callback args\n");
		om_set_error(OM_NO_SPACE);
		status = -1;
		goto ti_error;
	}

	nvlist_dup(attrs, &ti_args->target_attrs, 0);

	if (ti_args->target_attrs == NULL) {
		om_log_print("ti_args == NULL\n");
		om_set_error(OM_NO_TARGET_ATTRS);
		status = -1;
		goto ti_error;
	}

	/*
	 * create fdisk target
	 */

	/* Obtain disk name first */

	if (nvlist_lookup_string(ti_args->target_attrs, TI_ATTR_FDISK_DISK_NAME,
	    &disk_name) != 0) {
		om_debug_print(OM_DBGLVL_ERR, "Disk name not provided, can't "
		    "proceed with target instantiation\n");
		om_set_error(OM_NO_INSTALL_TARGET);
		status = -1;
		goto ti_error;
	}

	/* initialize progress report structures */

	cb_data.num_milestones = 3;
	cb_data.callback_type = OM_INSTALL_TYPE;
	cb_data.curr_milestone = OM_TARGET_INSTANTIATION;
	cb_data.percentage_done = 0;

	/*
	 * create fdisk target
	 */

	ti_status = ti_create_target(ti_args->target_attrs, NULL);

	if (ti_status != TI_E_SUCCESS) {
		om_log_print("Could not create fdisk target\n");
		om_set_error(OM_TARGET_INSTANTIATION_FAILED);
		status = -1;
		goto ti_error;
	}

	cb_data.percentage_done = 20;
	om_cb(&cb_data, app_data);

	/*
	 * create VTOC target
	 */

	if (nvlist_alloc(&ti_ex_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		om_log_print("Could not create target list.\n");
		om_set_error(OM_NO_SPACE);
		status = -1;
		goto ti_error;
	}

	if (slim_set_slice_attrs(ti_ex_attrs, disk_name) != 0) {
		om_log_print("Couldn't set slice attributes. \n");
		nvlist_free(ti_ex_attrs);
		status = -1;
		goto ti_error;
	}

	ti_status = ti_create_target(ti_ex_attrs, NULL);
	nvlist_free(ti_ex_attrs);

	if (ti_status != TI_E_SUCCESS) {
		om_log_print("Could not create VTOC target\n");
		om_set_error(OM_CANT_CREATE_VTOC_TARGET);
		status = -1;
		goto ti_error;
	}

	cb_data.percentage_done = 40;
	om_cb(&cb_data, app_data);

	/*
	 * Create ZFS root pool.
	 */

	om_log_print("Set zfs root pool device\n");

	if (prepare_zfs_root_pool_attrs(&ti_ex_attrs, disk_name) !=
	    OM_SUCCESS) {
		om_log_print("Could not prepare ZFS root pool attribute set\n");
		nvlist_free(ti_ex_attrs);
		status = -1;
		goto ti_error;
	}

	om_log_print("creating zpool\n");

	/* call TI for creating zpool */

	ti_status = ti_create_target(ti_ex_attrs, NULL);

	nvlist_free(ti_ex_attrs);

	if (ti_status != TI_E_SUCCESS) {
		om_log_print("Could not create ZFS root pool target\n");
		om_set_error(OM_CANT_CREATE_ZPOOL);
		status = -1;
		goto ti_error;
	}

	cb_data.percentage_done = 60;
	om_cb(&cb_data, app_data);

	/*
	 * Create BE
	 */

	if (prepare_be_attrs(&ti_ex_attrs) != OM_SUCCESS) {
		om_log_print("Could not prepare BE attribute set\n");
		nvlist_free(ti_ex_attrs);
		status = -1;
		goto ti_error;
	}

	ti_status = ti_create_target(ti_ex_attrs, NULL);

	nvlist_free(ti_ex_attrs);

	if (ti_status != TI_E_SUCCESS) {
		om_log_print("Could not create BE target\n");
		status = -1;
		goto ti_error;
	} else
		om_log_print("TI process completed \n");

	cb_data.percentage_done = 99;
	om_cb(&cb_data, app_data);

ti_error:

	cb_data.num_milestones = 3;
	cb_data.callback_type = OM_INSTALL_TYPE;

	if (status != 0) {
		om_log_print("TI process completed unsuccessfully \n");
		cb_data.curr_milestone = OM_INVALID_MILESTONE;
		cb_data.percentage_done = OM_TARGET_INSTANTIATION_FAILED;
	} else {
		om_log_print("TI process completed successfully \n");
		cb_data.curr_milestone = OM_TARGET_INSTANTIATION;
		cb_data.percentage_done = 100;
	}

	om_cb(&cb_data, app_data);

	om_log_print("ti_create_target exited with status = %d\n", status);
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
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
	char				cmd[MAXPATHLEN];
	char				*rpool_id;
	int				ret;
	void				*exit_val;

	(void) pthread_join(ti_thread, &exit_val);

	ti_ret += *(int *)exit_val;
	if (ti_ret != 0) {
		om_log_print("Target instantiation failed exit_val=%d\n",
		    ti_ret);
		om_set_error(OM_TARGET_INSTANTIATION_FAILED);
		notify_error_status(OM_TARGET_INSTANTIATION_FAILED);
		status = -1;
		pthread_exit((void *)&status);
	}

	/*
	 * Sleep some more while TI reports progress.
	 */
	om_log_print("TI procesing completed. Beginning transfer service \n");

	tcb_args = (struct transfer_callback *)args;

	if (tcb_args->target == NULL) {
		om_set_error(OM_NO_TARGET_ATTRS);
		notify_error_status(OM_NO_TARGET_ATTRS);
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_alloc(&transfer_attr, NV_UNIQUE_NAME, 0) != 0) {
		om_set_error(OM_NO_SPACE);
		notify_error_status(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_add_uint32(transfer_attr, TM_ATTR_MECHANISM,
	    TM_PERFORM_CPIO) != 0) {
		nvlist_free(transfer_attr);
		om_set_error(OM_NO_SPACE);
		notify_error_status(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_add_uint32(transfer_attr, TM_CPIO_ACTION,
	    TM_CPIO_ENTIRE) != 0) {
		nvlist_free(transfer_attr);
		om_set_error(OM_NO_SPACE);
		notify_error_status(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_add_string(transfer_attr, TM_CPIO_SRC_MNTPT, "/") != 0) {
		nvlist_free(transfer_attr);
		om_set_error(OM_NO_SPACE);
		notify_error_status(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	if (nvlist_add_string(transfer_attr, TM_CPIO_DST_MNTPT,
	    tcb_args->target) != 0) {
		nvlist_free(transfer_attr);
		om_set_error(OM_NO_SPACE);
		notify_error_status(OM_NO_SPACE);
		status = -1;
		pthread_exit((void *)&status);
	}

	status = TM_perform_transfer(transfer_attr, handle_TM_callback);
	if (status == TM_SUCCESS) {
		/*
		 * We only want to enable nwam  and create user's
		 * login directory for initial install.
		 */
		if (install_type == OM_INITIAL_INSTALL) {
			if (def_locale != NULL)
				(void) om_set_default_locale_by_name(
				    def_locale);

			/*
			 * Create user directory if needed
			 */
			create_user_directory();
		}
		setup_etc_vfstab_for_zfs_root(tcb_args->target);
		setup_users_default_environ(tcb_args->target);

		/*
		 * Start of code to address temporary set hostid fix.
		 *
		 * The below section of code will be used temporarily set
		 * the hostid.
		 *
		 * A more permanent fix to provide hostid is being worked.
		 * Once that fix is available this code should be removed.
		 */
		setup_hostid(tcb_args->target);
		/*
		 * End of code to address temporary set hostid fix.
		 */

		activate_be(INIT_BE_NAME);
		run_installgrub(tcb_args->target, zfs_device);
		transfer_config_files(tcb_args->target);
		reset_zfs_mount_property(tcb_args->target);

		/*
		 * mount "/" once more, since we need run
		 * install finish scipt
		 */

		(void) snprintf(cmd, sizeof (cmd),
		    "/sbin/mount -F zfs %s/ROOT/%s %s",
		    ROOTPOOL_NAME, INIT_BE_NAME, tcb_args->target);

		om_log_print("%s\n", cmd);
		td_safe_system(cmd, B_TRUE);

		run_install_finish_script(tcb_args->target);

		/*
		 * Take a snapshot of the installation.
		 */
		td_safe_system("/usr/sbin/zfs snapshot -r " ROOTPOOL_SNAPSHOT,
		    B_TRUE);

		/*
		 * Transfer log files to the destination now,
		 * when everything is finished
		 */
		ls_transfer("/", tcb_args->target);

		/*
		 * Notify the caller that install is completed
		 */

		notify_install_complete();
	} else {
		om_debug_print(OM_DBGLVL_WARN, NSI_TRANSFER_FAILED, status);
		om_log_print(NSI_TRANSFER_FAILED, status);
		notify_error_status(OM_TRANSFER_FAILED);
	}

	nvlist_free(transfer_attr);
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
}

/*
 * handle_TM_callback
 * This function handles the callbacks for TM
 * It builds the callback data the GUI expects
 * Input:	percent - percentage complete
 *		message - localized text message for GUI to display
 * Output:	None
 * Return:	None
 */
static void
handle_TM_callback(const int percent, const char *message)
{
	om_callback_info_t cb_data;

	cb_data.num_milestones = 3;
	cb_data.curr_milestone = OM_SOFTWARE_UPDATE;
	cb_data.callback_type = OM_INSTALL_TYPE;
	cb_data.percentage_done = percent;
	cb_data.message = message;
	om_cb(&cb_data, 0);
	tm_percentage_done = percent;
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

	/*
	 * A user can set a login name with no password.
	 */

	if (login == NULL) {
		om_set_error(OM_INVALID_USER);
		return (OM_FAILURE);
	}

	tbl = table_of_type(DB_PASSWD_TBL);
	ret_stat = lcl_list_table(DB_NS_UFS, NULL, NULL,
	    DB_DISABLE_LOCKING | DB_LIST_SHADOW | DB_LIST_SINGLE,
	    &db_err, tbl, login, &name, &pw, &uid,
	    &gid, &gcos, &path, &shell, &last, &min,
	    &max, &warn, &inactive, &expire, &flag);

	if (ret_stat == -1) {
		om_log_print("%s\n", db_err->msg);
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

		/*
		 * If add failed a relic entry may have been left from a
		 * failed install. Try to remove it then add again.
		 */
		if (ret_stat == -1) {
			ret_stat = lcl_remove_table_entry(DB_NS_UFS, NULL,
			    NULL, DB_MODIFY, &db_err, tbl, login);
			if (ret_stat == -1) {
				om_log_print("Could not remove table entry\n");
				om_log_print("for %s\n", login);
				om_log_print("%s\n", db_err->msg);
				om_set_error(OM_SET_USER_FAIL);
				return (OM_FAILURE);
			}

			ret_stat = lcl_set_table_entry(DB_NS_UFS, NULL, NULL,
			    DB_ADD_MODIFY, &db_err, tbl,
			    &login, &login, &e_passwd, &uid, &gid, &gcos, &path,
			    &shell, &last, &min, &max, &warn, &inactive,
			    &expire, &flag);
		}
	}

	if (ret_stat == -1) {
		om_log_print("Could not set user password table\n");
		om_log_print("%s\n", db_err->msg);
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
	 *
	 * take uncompressed size of image and add 20% reserve
	 *
	 * also don't forget to add swap space
	 */
	if (obtain_image_info(&image_info) != OM_SUCCESS)
		om_log_print("Couldn't read image info file");

	return ((uint64_t)(image_info.image_size *
	    image_info.compress_ratio * 1.2 + MIN_SWAP_SPACE));
}


/*ARGSUSED*/
uint64_t
om_get_recommended_size(char *media, char *distro)
{
	/*
	 * Size in MB that is the recommended device size we will allow
	 * for installing Slim.
	 *
	 * Account for one full upgrade and add some more space for
	 * additional software.
	 */

	return (om_get_min_size(NULL, NULL) * 2 + 2048);
}

/*
 * Return the UID which will be assigned to the new user
 * created by the installer.
 */
uid_t
om_get_user_uid(void)
{
	return ((uid_t)atoi(USER_UID));
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
	char	entry[MAXHOSTNAMELEN * 5];
	char 	*tmpnam;
	FILE 	*rfp, *wfp;
	char 	buff[1024], dup[1024];
	char 	*p;
	boolean_t	done = B_FALSE, error = B_FALSE;
	int	ret;

	(void) snprintf(entry, sizeof (entry), "%s\t%s %s.local %s %s\n",
	    LOOPBACK_IP, hostname, hostname, LOCALHOST, LOG_HOST);
	tmpnam = tempnam(HOSTS_DIR, NULL);
	if (tmpnam == NULL) {
		om_log_print("Unable to generate tmp hosts file name: %s\n",
		    strerror(errno));
		om_set_error(OM_CANT_CREATE_TMP_FILE);
		return (OM_FAILURE);
	}
	if ((wfp = fopen(tmpnam, "w")) == NULL)  {
		om_log_print("Can't open file %s\n", tmpnam);
		om_set_error(OM_CANT_OPEN_FILE);
		free(tmpnam);
		return (OM_FAILURE);
	}

	if ((rfp = fopen(HOSTS_TABLE, "r")) != NULL) {
		while (fgets(buff, sizeof (buff), rfp) == buff) {
			(void) strcpy(dup, buff);
			p = strtok(buff, " \t\n");
			if (p != NULL && strcmp(p, LOOPBACK_IP) == 0) {
				/* Matched, replace it */
				ret = fputs(entry, wfp);
				done = B_TRUE;
			} else {
				/* Didn't match, copy it */
				ret = fputs(dup, wfp);
			}
			if (ret == EOF) {
				error = B_TRUE;
				break;
			}
		}
		(void) fclose(rfp);
	}
	if (!error && !done) {
		/* Not written yet, so write it now */
		if (fputs(entry, wfp) == EOF)
			error = B_TRUE;
	}
	if (error) {
		om_debug_print(OM_DBGLVL_ERR, "Write error updating %s: %s\n",
		    HOSTS_TABLE, strerror(errno));
		(void) fclose(wfp);
		free(tmpnam);
		return (OM_FAILURE);
	} else {
		(void) fclose(wfp);
		om_log_print("Renaming table %s to %s\n", tmpnam, HOSTS_TABLE);
		if (rename(tmpnam, HOSTS_TABLE) != 0) {
			om_debug_print(OM_DBGLVL_ERR,
			    "Rename of %s failed, error was: %s\n",
			    tmpnam, strerror(errno));
			free(tmpnam);
			return (OM_FAILURE);
		}
	}
	free(tmpnam);
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
 * Inform GUI of error condition through callback
 */
static	void
notify_error_status(int status)
{
	om_callback_info_t cb_data;

	cb_data.num_milestones = 3;
	cb_data.curr_milestone = -1; /* signals error to GUI */
	cb_data.callback_type = OM_INSTALL_TYPE;
	cb_data.percentage_done = status; /* overload value on error */
	cb_data.message = NULL;
	om_cb(&cb_data, 0);
}

/*
 * Notify the GUI that the installation is complete
 */
static	void
notify_install_complete()
{
	om_callback_info_t cb_data;

	cb_data.num_milestones = 3;
	cb_data.curr_milestone = OM_POSTINSTAL_TASKS;
	cb_data.callback_type = OM_INSTALL_TYPE;
	cb_data.percentage_done = 100;
	cb_data.message = NULL;
	om_cb(&cb_data, 0);
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
	(void) fprintf(fp, "%s/ROOT/%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n",
	    ROOTPOOL_NAME, INIT_BE_NAME, "-", "/", "zfs", "-", "no", "-");

	om_log_print("Setting up swap mount in /etc/vfstab\n");

	(void) fprintf(fp, "%s\t%s\t\t%s\t\t%s\t%s\t%s\t%s\n",
	    swap_device, "-", "-", "swap", "-", "no", "-");

	(void) fclose(fp);
}

static void
setup_users_default_environ(char *target)
{
	char	cmd[MAXPATHLEN];
	char	user_path[MAXPATHLEN];
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
		uid_t uid;
		gid_t gid;

		(void) snprintf(user_path, sizeof (user_path), "%s/%s/%s/%s",
		    target, home, save_login_name, bashrc);

		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/^PATH/%s &/' %s >%s",
		    "export", profile, user_path);
		om_log_print("%s\n", cmd);
		td_safe_system(cmd, B_FALSE);

		/*
		 * Change owner to user. Change group to staff.
		 */
		uid = (uid_t)strtol(USER_UID, (char **)NULL, 10);
		gid = (gid_t)strtol(USER_GID, (char **)NULL, 10);
		if (uid != 0 && gid != 0) {
			(void) chown(user_path, uid, gid);
		}
	}
}

/*
 * Setup mountpoint property back to "/" from "/a" for
 * /, /opt, /export, /export/home
 */
static void
reset_zfs_mount_property(char *target)
{
	char 		cmd[MAXPATHLEN];
	nvlist_t	*attrs;
	int		i, ret;

	if (target == NULL) {
		return;
	}

	om_log_print("Unmounting BE\n");

	/*
	 * make sure we are not in alternate root
	 * otherwise be_unmount() fails
	 */

	chdir("/root");

	/*
	 * Since be_unmount() can't currently handle shared filesystems,
	 * it is necessary to manually set their mountpoint to the
	 * appropriate value.
	 */

	for (i = ZFS_SHARED_FS_NUM - 1; i >= 0; i--) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs unmount %s%s",
		    ROOTPOOL_NAME, zfs_shared_fs_names[i]);

		om_log_print("%s\n", cmd);
		ret = td_safe_system(cmd, B_TRUE);

		if ((ret == -1) || WEXITSTATUS(ret) != 0) {
			om_debug_print(OM_DBGLVL_WARN,
			    "Couldn't unmount %s%s, err=%d\n", ROOTPOOL_NAME,
			    zfs_shared_fs_names[i], ret);
		}

		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/zfs set mountpoint=%s %s%s",
		    zfs_shared_fs_names[i], ROOTPOOL_NAME,
		    zfs_shared_fs_names[i]);

		om_log_print("%s\n", cmd);
		ret = td_safe_system(cmd, B_TRUE);

		if ((ret == -1) || WEXITSTATUS(ret) != 0) {
			om_debug_print(OM_DBGLVL_WARN,
			    "Couldn't change mountpoint for %s%s, err=%d\n",
			    ROOTPOOL_NAME, zfs_shared_fs_names[i], ret);
		}
	}

	/*
	 * Unmount non-shared BE filesystems
	 */
	if (nvlist_alloc(&attrs, NV_UNIQUE_NAME, 0) != 0) {
		om_log_print("Could not create target list.\n");
	}

	if (nvlist_add_string(attrs, BE_ATTR_ORIG_BE_NAME, INIT_BE_NAME) != 0) {
		om_log_print("BE name could not be added. \n");

		return;
	}

	(void) be_unmount(attrs);

	nvlist_free(attrs);
}

/*
 * Setup bootfs property, so that newly created Solaris instance
 * is boooted appropriately
 */
static void
activate_be(char *be_name)
{
	char 		cmd[MAXPATHLEN];

	/*
	 * Set bootfs property for root pool. It can't be
	 * set before root filesystem is created.
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zpool set bootfs=%s/ROOT/%s %s",
	    ROOTPOOL_NAME, be_name, ROOTPOOL_NAME);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd, B_TRUE);
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
		    "%s %s initial_install",
		    tool, target);
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/root/installer/install-finish %s initial_install",
		    target);
	}

	om_log_print("%s\n", cmd);
	td_safe_system(cmd, B_TRUE);
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
	    "/usr/sbin/installgrub %s/boot/grub/stage1"
	    " %s/boot/grub/stage2 /dev/rdsk/%s",
	    target, target, device);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd, B_TRUE);
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
	td_safe_system(cmd, B_FALSE);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/sed -e '/^jack/d' %s >%s%s",
	    shadow, target, shadow);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd, B_FALSE);

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
	td_safe_system(cmd, B_FALSE);
	free(save_login_name);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/cp %s %s%s",
	    hosts, target, hosts);

	om_log_print("%s\n", cmd);
	td_safe_system(cmd, B_TRUE);
}

/*
 * prepare_zfs_root_pool_attrs
 * Creates nvlist set of attributes describing ZFS pool to be created
 * Input:	nvlist_t **attrs - attributes describing the target
 *		char *disk_name - disk name which will hold the pool
 * Output:
 * Return:	OM_SUCCESS
 *		OM_FAILURE
 * Notes:
 */
static int
prepare_zfs_root_pool_attrs(nvlist_t **attrs, char *disk_name)
{
	if (nvlist_alloc(attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		om_log_print("Could not create target nvlist.\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_uint32(*attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_RPOOL) != 0) {
		(void) om_log_print("Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string(*attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    ROOTPOOL_NAME) != 0) {
		om_log_print("ZFS root pool name could not be added. \n");

		return (OM_FAILURE);
	}

	snprintf(zfs_device, sizeof (zfs_device), "%ss0", disk_name);

	if (nvlist_add_string(*attrs, TI_ATTR_ZFS_RPOOL_DEVICE,
	    zfs_device) != 0) {
		om_log_print("Could not set zfs rpool device name\n");

		return (OM_FAILURE);
	}

	return (OM_SUCCESS);
}

/*
 * prepare_be_attrs
 * Creates nvlist set of attributes describing boot environment (BE)
 * Input:	nvlist_t **attrs - attributes describing the target
 *
 * Output:
 * Return:	OM_SUCCESS
 *		OM_FAILURE
 * Notes:
 */
static int
prepare_be_attrs(nvlist_t **attrs)
{
	if (nvlist_alloc(attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		om_log_print("Could not create target nvlist.\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_uint32(*attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_BE) != 0) {
		(void) om_log_print("Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string(*attrs, TI_ATTR_BE_RPOOL_NAME,
	    ROOTPOOL_NAME) != 0) {
		om_log_print("BE root pool name could not be added. \n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string(*attrs, TI_ATTR_BE_NAME,
	    INIT_BE_NAME) != 0) {
		om_log_print("BE name could not be added. \n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string_array(*attrs, TI_ATTR_BE_FS_NAMES,
	    zfs_fs_names, ZFS_FS_NUM) != 0) {
		om_log_print("Couldn't set zfs fs name attr\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string_array(*attrs, TI_ATTR_BE_SHARED_FS_NAMES,
	    zfs_shared_fs_names, ZFS_SHARED_FS_NUM) != 0) {
		om_log_print("Couldn't set zfs shared fs name attr\n");

		return (OM_FAILURE);
	}

	if (nvlist_add_string(*attrs, TI_ATTR_BE_MOUNTPOINT,
	    INSTALLED_ROOT_DIR) != 0) {
		om_log_print("Couldn't set be mountpoint attr\n");

		return (OM_FAILURE);
	}

	return (OM_SUCCESS);
}


/*
 * obtain_image_info
 * Parse image info file and reads following information from it:
 * [1] total size of installed bits
 * [2] compression ratio, if ZFS compression is turned on
 * [3] compression type
 * Input:	image_info_t * info - pointer to structure, which will
 *		be populated with image information
 *
 * Output:
 * Return:	OM_SUCCESS - information read successfully
 *		OM_FAILURE - image information couldn't be obtained
 * Notes:
 */

static int
obtain_image_info(image_info_t *info)
{
	FILE		*info_file;
	char		line[IMAGE_INFO_LINE_MAXLN];
	boolean_t	got_size = B_FALSE;
	boolean_t	got_cratio = B_FALSE;
	boolean_t	got_ctype = B_FALSE;

	/*
	 * fill in the structure only once
	 */

	if (info->initialized) {
		return (OM_SUCCESS);
	}

	/*
	 * open image info file, parse it
	 * and populate data structure
	 */

	info_file = fopen(IMAGE_INFO_FILE_NAME, "r");
	if (info_file == NULL) {
		om_debug_print(OM_DBGLVL_WARN,
		    "Couldn't open image info file " IMAGE_INFO_FILE_NAME "\n");

		return (OM_FAILURE);
	}

	while (fgets(line, sizeof (line), info_file) != NULL) {
		char	*par_name, *par_value;

		/*
		 * get parameter name
		 */

		/* TAB is one of separators */

		par_name = strtok(line, "= 	");

		if (par_name == NULL) {
			om_debug_print(OM_DBGLVL_WARN,
			    "Invalid parameter %s\n", line);
			continue;
		}

		/*
		 * get parameter value
		 */

		par_value = strtok(NULL, "= 	");

		if (par_value == NULL) {
			om_debug_print(OM_DBGLVL_WARN,
			    "Invalid parameter %s\n", line);
			continue;
		}

		/*
		 * look at the parameter name and compare to
		 * known/requested
		 */

		if (strcmp(par_name, IMAGE_INFO_TOTAL_SIZE) == 0) {
			uint64_t	size;

			errno = 0;
			size = strtoll(par_value, NULL, 10);

			if (errno == 0) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Got image size: %lld\n", size);

				/* convert kiB -> MiB */

				image_info.image_size = size/ONE_MB_TO_KB;
				got_size = B_TRUE;
			} else
				om_debug_print(OM_DBGLVL_WARN,
				    "Invalid format of total size parameter\n");
		}

		/*
		 * ask for compression ratio
		 */

		if (strcmp(par_name, IMAGE_INFO_COMPRESSION_RATIO) == 0) {
			float ratio;

			errno = 0;
			ratio = strtof(par_value, NULL);

			if (errno == 0) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Got compression ratio: %f\n", ratio);

				image_info.compress_ratio = ratio;
				got_cratio = B_TRUE;
			} else
				om_debug_print(OM_DBGLVL_WARN,
				    "Invalid format of compression ratio "
				    "parameter\n");
		}

		/*
		 * ask for compression type
		 */

		if (strcmp(par_name, IMAGE_INFO_COMPRESSION_TYPE) == 0) {
			char *type;

			type = strdup(par_value);

			if (type != NULL) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Got compression type: %s\n", type);

				image_info.compress_type = type;
				got_ctype = B_TRUE;
			} else
				om_debug_print(OM_DBGLVL_WARN,
				    "Invalid format of compression type "
				    "parameter\n");
		}

		if (got_size && got_cratio && got_ctype)
			break;
	}

	(void) fclose(info_file);

	/*
	 * if at least one of parameters obtained,
	 * we read image info file successfully
	 */

	if (got_size || got_cratio || got_ctype) {
		info->initialized = B_TRUE;
		return (OM_SUCCESS);
	} else
		return (OM_FAILURE);
}


/*
 * get_rootpool_id
 *
 * Obtains id for given root pool name
 * it allocates memory for id returned - should be freed by caller
 * Return:	== NULL - couldn't obtain pool id
 *		!= NULL - pointer to id string
 * Notes:
 */

static char *
get_rootpool_id(char *rpool_name)
{
	FILE	*p;
	char	cmd[MAXPATHLEN];
	char	*strbuf;
	int	ret;

	strbuf = malloc(MAXPATHLEN);

	if (strbuf == NULL) {
		om_log_print("Out of memory\n");
		return (NULL);
	}

	(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/zpool list -H -o guid %s",
	    rpool_name);

	om_log_print("%s\n", cmd);

	if ((p = popen(cmd, "r")) == NULL) {
		om_log_print("Couldn't obtain pool id\n");

		free(strbuf);
		return (NULL);
	}

	if (fgets(strbuf, MAXPATHLEN, p) == NULL) {
		om_log_print("Couldn't obtain pool id\n");

		free(strbuf);
		(void) pclose(p);
		return (NULL);
	}

	ret = WEXITSTATUS(pclose(p));

	if (ret != 0) {
		om_log_print("Command failed with error %d\n", ret);
		free(strbuf);
		return (NULL);
	}

	/* strip new line */
	if (strbuf[strlen(strbuf) - 1] == '\n')
		strbuf[strlen(strbuf) - 1] = '\0';

	return (strbuf);
}


/*
 * Start of code to address temporary set hostid fix.
 *
 * The below section of code will be used temporarily set the hostid.
 *
 * A more permanent fix to provide hostid is being worked. Once that fix
 * is available this code should be removed.
 */

/* private prototypes */

static int		setser(char *);
static int		patchser_64(char *, char *);
static int		get_serial32(char *, int32_t *, int32_t *);
static int		set_serial64(char *, int32_t, int32_t);

/* constants */

/*
 * These two definitions MUST follow the same definitions as found in
 * the ON consolidation in usr/src/uts/common/io/sysinit.c.  If that
 * file changes, so must this one.
 */
#define	HOSTID_SYMBOL	"t"
#define	V1		0x38d4419a

#define	A	16807
#define	M	2147483647
#define	Q	127773
#define	R	2836
#define	x()	if ((s = ((A*(s%Q))-(R*(s/Q)))) <= 0) s += M

/*
 * Function:	setup_hostid
 * Description:	Set the hostid on any system supporting the i386 model of
 *		hostids.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	- set successful
 *		ERROR	- set failed
 */
static void
setup_hostid(char *target)
{
	char	buf[32] = "";
	char	orig[64] = "";
	char	path32[MAXPATHLEN] = "";
	char	path64[MAXPATHLEN] = "";

	if (target == NULL) {
		return;
	}

	/* cache client hostids are set by hostmanager */
	if (get_machinetype() == MT_CCLIENT) {
		return;
	}

	(void) sprintf(orig, "/tmp/root%s", IDKEY);
	(void) sprintf(path32, "%s%s", target, IDKEY);
	(void) sprintf(path64, "%s%s", target, IDKEY64);

	om_log_print("setup_hostid() to path32 ->%s<-\n", path32);
	om_log_print("setup_hostid() to path64 ->%s<-\n", path64);

	/* only set if the original was not saved */
	if (access(path32, F_OK) == 0) {
		if (access(orig, F_OK) < 0 &&
		    (sysinfo(SI_HW_SERIAL, buf, 32) < 0 ||
		    buf[0] == '0')) {
			if (setser(path32) < 0) {
				om_log_print("setser(%s)\n", path32);
				om_log_print("   returned ERROR \n");
				return;
			}
		}

		/*
		 * Get the hostid from 32-bit sysinit module and set it
		 * to 64-bit sysinit module so that both 32-bit and
		 * 64-bit hostid are same
		 */
		if (access(path64, F_OK) == 0) {
			if (patchser_64(path32, path64) < 0) {
				om_log_print("patchser_64(%s, %s)\n",
				    path32, path64);
				om_log_print("   returned ERROR \n");
				return;
			}
		}
	}
}

/*
 * Function:	setser
 * Description: Generate a hardware serial number in the range 1 to (10**9-1)
 *		and sets appropriate constants in the sysinit module with name
 *		fn.  Uses elf(3ELF) libraries.
 * Scope:	private
 * Parameters:	fn	- module file name
 * Return:	ERROR	- couldn't generate serial number
 *		NOERROR - could
 */
static int
setser(char *fn)
{
	struct timeval tv;
	struct stat statbuf;
	struct utimbuf utimbuf;
	int fd, count, i;
	Elf *elf;
	Elf_Scn *scn;
	Elf_Scn *dscn;
	Elf32_Shdr *shdr;
	Elf32_Sym *sym;
	Elf_Data *data;
	char *dbuf = NULL;
	Elf_Data *elfdata;
	int32_t s;
	int32_t ver;
	char *symname;
	int32_t t[3];

	/* open the module file */
	if ((fd = open(fn, O_RDWR)) < 0)
		return (ERROR);

	/* get file status for times */
	if (fstat(fd, &statbuf) < 0)
		goto out;

	/* open the ELF */
	elf_version(EV_CURRENT);
	elf = elf_begin(fd, ELF_C_RDWR, (Elf *)0);
	if (elf == NULL)
		goto out;

	/* find the symbol table */
	scn = NULL;
	while ((scn = elf_nextscn(elf, scn)) != NULL) {
		shdr = elf32_getshdr(scn);
		if (shdr->sh_type == SHT_SYMTAB) {
			/* found the symbol table, so lets go search it. */
			break;
		}
	}

	if (scn == NULL) {
		/* no symbol table, so silently bail */
		goto elfout;
	}

	/* how many symbols in the symbol table */
	data = elf_getdata(scn, NULL);
	count = shdr->sh_size / shdr->sh_entsize;

	/* find the super-secret symbol we are looking for */
	for (i = 0; i < count; ++i) {
		sym = (Elf32_Sym *)((char *)data->d_buf +
		    (i * sizeof (Elf32_Sym)));
		symname = elf_strptr(elf, shdr->sh_link, sym->st_name);
		if (symname == NULL) {
			/* ignore null symbols */
			continue;
		}
		if (strcmp(symname, HOSTID_SYMBOL) == 0) {
			/*
			 * We found the right symbol.
			 * Now go find the section it's in.
			 */
			dscn = elf_getscn(elf, sym->st_shndx);

			/* Finally find the section contents (dbuf) */
			elfdata = elf_getdata(dscn, NULL);
			dbuf = (char *)elfdata->d_buf;

			/*
			 * dbuf + symbol offset points to the version
			 * identifier
			 */
			ver = *((uint32_t *)(dbuf+sym->st_value));

			/*
			 * Version must match the super-secret one we
			 * are expecting
			 */
			if (ver != (uint32_t)V1) {
				goto elfout;
			}
			break;
		}
	}

	if (dbuf == NULL) {
		/* didn't find the symbol, bail */
		goto elfout;
	}

	/* generate constants and serial number */
	(void) gettimeofday(&tv, (void *)NULL);
	s = tv.tv_sec + tv.tv_usec - (22*365*24*60*60);
	do {
		x();
		t[1] = s;
		x();
		t[2] = s;
		x();
		s %= 1000000000;
	} while (s == 0);

	/* store constants */
	*(((uint32_t *)dbuf) + 1) = t[1];
	*(((uint32_t *)dbuf) + 2) = t[2];

	/* ensure that the memory image of the ELF file is complete */
	elf_update(elf, ELF_C_NULL);
	elf_update(elf, ELF_C_WRITE);   /* update ELF file on disk */
	elf_end(elf);
	(void) close(fd);

	/* restore file access and modification times */
	utimbuf.actime = statbuf.st_atime;
	utimbuf.modtime = statbuf.st_mtime;
	if (utime(fn, &utimbuf) < 0)
		return (ERROR);

	return (NOERR);	/* return success */

elfout:	elf_end(elf);

	/* close file and return error code */
out:    (void) close(fd);
	return (ERROR);

}

/*
 * function:	patchser_64
 * Description:	Get the serial number (hostid) from the 32-bit sysinit
 *		module and patch the 64-bit sysinit module
 * Scope:	private
 * Parameters:	src	- Source module file name
 *		dst	- Destnation module file name
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
patchser_64(char *src, char *dst)
{
	int32_t l1, l2;

	if (get_serial32(src, &l1, &l2) == NOERR) {
		if (set_serial64(dst, l1, l2) == NOERR) {
			return (NOERR);
		}
	}
	return (ERROR);
}

/*
 * function:	get_serial32
 * Description:	Get the serial number from 32-bit sysinit module
 *		This has been populated either with the serial number from
 *		the OS instance on the disk or created a new one using setser
 *		function.
 * Scope:	private
 * Parameters:	fn	- module file name
 *		value1	- The first 32-byte of the serial number
 *		value2	- The second 32-byte of the serial number
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
get_serial32(char *fn, int32_t *value1, int32_t *value2)
{
	Elf32_Ehdr Ehdr;
	Elf32_Shdr Shdr;
	int fd;
	int rc;
	char name[6];
	off_t offset;
	off_t shstrtab_offset;
	off_t data_offset;
	int i;
	int32_t t[3];

	rc = ERROR;	/* assume module doesn't exist */

	/* open the module file */
	if ((fd = open(fn, O_RDONLY)) < 0) {
		return (rc);
	}

	/* read the elf header */
	offset = 0;
	if (pread(fd, &Ehdr, sizeof (Ehdr), offset) < 0) {
		goto out;
	}

	/* read the section header for the section string table */
	offset = Ehdr.e_shoff + (Ehdr.e_shstrndx * Ehdr.e_shentsize);
	if (pread(fd, &Shdr, sizeof (Shdr), offset) < 0) {
		goto out;
	}

	/* save the offset of the section string table */
	shstrtab_offset = Shdr.sh_offset;

	/* find the .data section header */
	/*CSTYLED*/
	for (i = 1; ; ) {
		offset = Ehdr.e_shoff + (i * Ehdr.e_shentsize);
		if (pread(fd, &Shdr, sizeof (Shdr), offset) < 0) {
			goto out;
		}
		offset = shstrtab_offset + Shdr.sh_name;
		if (pread(fd, name, sizeof (name), offset) < 0) {
			goto out;
		}
		if (strcmp(name, ".data") == 0)
			break;
		if (++i >= (int)Ehdr.e_shnum) {
			/* reached end of table */
			goto out;
		}
	}

	/* save the offset of the data section */
	data_offset = Shdr.sh_offset;

	/* read and check the version number and initial seed values */
	offset = data_offset;
	if (pread(fd, &t[0], sizeof (t[0]) * 3, offset) < 0) {
		goto out;
	}

	*value1 = t[1];
	*value2 = t[2];
	rc = NOERR;

out:    (void) close(fd);
	return (rc);
}

/*
 * function:	set_serial64
 * Description:	Set the serial number in the 64-bit sysinit module using
 *		the serial number got from 32-bit sysinit module
 *		This has been populated either with the serial number from
 *		the OS instance on the disk or created a new one using setser
 *		function.
 * Scope:	private
 * Parameters:	fn	- module file name
 *		value1	- The first 32-byte of the serial number
 *		value2	- The second 32-byte of the serial number
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
set_serial64(char *fn, int32_t value1, int32_t value2)
{
	struct stat statbuf;
	struct utimbuf utimbuf;
	int fd, count, i;
	Elf *elf;
	Elf_Scn *scn;
	Elf_Scn *dscn;
	Elf64_Shdr *shdr;
	Elf64_Sym *sym;
	Elf_Data *data;
	char *dbuf = NULL;
	Elf_Data *elfdata;
	uint32_t ver;
	char *symname;

	/* open the module file */
	if ((fd = open(fn, O_RDWR)) < 0)
		return (ERROR);

	/* get file status for times */
	if (fstat(fd, &statbuf) < 0)
		goto out;

	/* open the ELF */
	elf_version(EV_CURRENT);
	elf = elf_begin(fd, ELF_C_RDWR, (Elf *)0);
	if (elf == NULL)
		goto out;

	/* find the symbol table */
	scn = NULL;
	while ((scn = elf_nextscn(elf, scn)) != NULL) {
		shdr = elf64_getshdr(scn);
		if (shdr->sh_type == SHT_SYMTAB) {
			/* found the symbol table, so lets go search it. */
			break;
		}
	}

	if (scn == NULL) {
		/* no symbol table, so silently bail */
		goto elfout;
	}

	/* how many symbols in the symbol table */
	data = elf_getdata(scn, NULL);
	count = shdr->sh_size / shdr->sh_entsize;

	/* find the super-secret symbol we are looking for */
	for (i = 0; i < count; ++i) {
		sym = (Elf64_Sym *)((char *)data->d_buf +
		    (i * sizeof (Elf64_Sym)));
		symname = elf_strptr(elf, shdr->sh_link, sym->st_name);
		if (symname == NULL) {
			/* ignore null symbols */
			continue;
		}
		if (strcmp(symname, HOSTID_SYMBOL) == 0) {
			/*
			 * We found the right symbol.
			 * Now go find the section it's in.
			 */
			dscn = elf_getscn(elf, sym->st_shndx);

			/* Finally find the section contents (dbuf) */
			elfdata = elf_getdata(dscn, NULL);
			dbuf = (char *)elfdata->d_buf;

			/*
			 * dbuf + symbol offset points to the version
			 * identifier
			 */
			ver = *((uint32_t *)(dbuf+sym->st_value));

			/*
			 * Version must match the super-secret one we
			 * are expecting
			 */
			if (ver != (uint32_t)V1) {
				goto elfout;
			}
			break;
		}
	}

	if (dbuf == NULL) {
		/* didn't find the symbol, bail */
		goto elfout;
	}

	/* Set the hostid  */
	*(((uint32_t *)dbuf) + 1) = value1;
	*(((uint32_t *)dbuf) + 2) = value2;

	/* ensure that the memory image of the ELF file is complete */
	elf_update(elf, ELF_C_NULL);
	elf_update(elf, ELF_C_WRITE);   /* update ELF file on disk */
	elf_end(elf);
	(void) close(fd);

	/* restore file access and modification times */
	utimbuf.actime = statbuf.st_atime;
	utimbuf.modtime = statbuf.st_mtime;
	if (utime(fn, &utimbuf) < 0)
		return (ERROR);

	return (NOERR);	/* return success */

elfout:	elf_end(elf);

	/* close file and return error code */
out:    (void) close(fd);
	return (ERROR);
}

/*
 * get_machinetype()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	private
 */
static MachineType
get_machinetype(void)
{
	return (machinetype);
}

/*
 * set_machinetype()
 *	Set the global machine "type" specifier
 * Parameters:
 *	type	- machine type specifier (valid types: MT_SERVER,
 *		  MT_DATALESS, MT_DISKLESS, MT_CCLIENT, MT_SERVICE)
 * Return:
 *	none
 * Status:
 *	private
 */
static void
set_machinetype(MachineType type)
{
	machinetype = type;
}

/*
 * End of code to address temporary set hostid fix.
 */
