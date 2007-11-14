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
#pragma ident	"@(#)perform_install.c	1.8	07/08/27 SMI"


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

#include <ls_api.h>

#define	UN(string) ((string) ? (string) : "")

/*
 * macro symbols to estimate tools installation time
 */
#define	EST_DURATION ((time_t)(60*8)) /* estimated duration in seconds */
/*
 * percentages for each component of tools installation - must total 100%
 *
 * The following values are percentages of the install time for all tools.
 * They have been modified to reflect installation times shorter than originally
 * estimated.
 */
#define	PCT_TOOLS_SUNSTUDIO 23
#define	PCT_TOOLS_NETBEANS 31
#define	PCT_TOOLS_JAVAAPPSVR 46

#define	ROOT_NAME	"root"
#define	ROOT_UID	"0"
#define	ROOT_GID	"1"
#define	ROOT_PATH	"/"

#define	USER_UID	"101"
#define	USER_GID	"10"	/* staff */
#define	USER_PATH	"/export/home/"

#define	STATE_FILE	"/etc/.sysIDtool.state"

struct icba {
	om_install_type_t	install_type;
	pid_t			pid;
	om_callback_t		cb;
};

/*
 * Global Variables
 */
static	pid_t		pfinstall_pid;
static	pid_t		tools_install_pid;
static	boolean_t	install_test = B_FALSE;
static	char		*state_file_path = NULL;
om_install_type_t	install_type;
static	char		*save_login_name = NULL;
static	char		*def_locale;

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
static void	add_2_xfer(char *name, char *pkg, char *type);
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
static void	enable_nwam();
static void	create_user_directory();
static void	transfer_nsi_files(char *profile);
static void	umount_tmp(char *path);

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
	om_profile_t	pf;
	char		*tmp_file;
	int		status = OM_SUCCESS;
	uint8_t		type;


	if (uchoices == NULL) {
		om_set_error(OM_BAD_INPUT);
	}

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
	if (type != OM_INITIAL_INSTALL &&
	    type != OM_UPGRADE) {
		om_set_error(OM_BAD_INSTALL_TYPE);
		return (OM_FAILURE);
	}
	pf.operation = type;
	install_type = type;

	/*
	 * Unique file name for writing jumpstart profile
	 */
	tmp_file = tempnam("/tmp", "profile");
	if (tmp_file == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	/*
	 * Special value for testing
	 */
	if (nvlist_lookup_boolean_value(uchoices,
	    OM_ATTR_INSTALL_TEST, (boolean_t *)&install_test) != 0) {
		install_test = B_FALSE;
	}

	/*
	 * For upgrade, we may have to get the upgrade target,
	 * setup profile and call pfinstall.
	 */
	if (type == OM_UPGRADE) {

		char	mnt[MAXPATHLEN];

		if (nvlist_lookup_string(uchoices,
		    OM_ATTR_UPGRADE_TARGET, &name) != 0) {
			om_set_error(OM_NO_UPGRADE_TARGET);
			return (OM_FAILURE);
		}

		if (!is_slicename_valid(name)) {
			om_set_error(OM_BAD_UPGRADE_TARGET);
			return (OM_FAILURE);
		}

		/*
		 * This is ugly. During upgrade, in SUUpgrade call
		 * _update_etc_default_init() is called after the upgrade
		 * completes. It checks for a file /tmp/.defSysLoc for the
		 * current default system locale data. Otherwise it reads
		 * /etc/default/init for this data. For Dwarf we need to
		 * save off the current upgrade targets /etc/default/init
		 * file so we can restore it after the upgrade completes.
		 * The /etc/default/init file in the miniroot has a default
		 * locale of C. We know by this time that the upgrade
		 * target is valid and mountable.
		 */

		(void) snprintf(mnt, MAXPATHLEN, "/dev/dsk/%s", name);
		status = td_mount_filesys(mnt, NULL, MOUNTA, "ufs",
		    MNTOPTS, 0, NULL);

		/*
		 * The tradeoff here is that if this mount fails now,
		 * it isn't likely to succeed in pfinstall. However,
		 * if it does fail in pfinstall it will be logged to
		 * the upgrade_log, which is the correct behavior.
		 * Do not fail if mount fails here.
		 */
		if (status != 0) {
			om_log_print("Could not mount upgrade target\n");
		} else {
			char 	path[MAXPATHLEN];
			snprintf(path, sizeof (path), "%s%s", MOUNTA,
			    INIT_FILE);

			/*
			 * Now, read the locale data from /etc/default/init
			 * and save off.
			 */
			read_and_save_locale(path);
			umount_tmp(MOUNTA);
		}

		pf.install_type.upgrade.slice = strdup(name);
		if (pf.install_type.upgrade.slice == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}

		pf.profile_name = strdup(tmp_file);
		if (pf.profile_name == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}

		if (create_pfinstall_profile(pf) != OM_SUCCESS) {
			status = OM_FAILURE;
			om_set_error(OM_UPGRADE_PROFILE_FAILED);
			goto upgrade_return;
		}

		if (call_pfinstall(type, pf.profile_name, cb) != OM_SUCCESS) {
			status = OM_FAILURE;
			om_set_error(OM_UPGRADE_FAILED);
			goto upgrade_return;
		}
upgrade_return:
		free(pf.install_type.upgrade.slice);
		free(pf.profile_name);
		return (status);
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

	pf.install_type.install.diskname = strdup(name);
	if (pf.install_type.install.diskname == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	pf.profile_name = strdup(tmp_file);
	if (pf.profile_name == NULL) {
		om_set_error(OM_NO_SPACE);
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

	/*
	 * locale list
	 */
	if (nvlist_lookup_string(uchoices, OM_ATTR_LOCALES_LIST, &name) != 0) {
		/*
		 * locales list is empty.
		 * Log the information and continue
		 */
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_LOCALES_LIST "
		    "not set\n");

		pf.install_type.install.locales = NULL;
	} else {
		if (name != NULL) {
			pf.install_type.install.locales = strdup(name);
		} else {
			pf.install_type.install.locales = NULL;
		}
	}
	/*
	 * Get the default locale. Save it off for later. We don't
	 * set the system default locale until after the installation
	 * has completed.
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
		om_debug_print(OM_DBGLVL_WARN, "OM_ATTR_LOGIN_NAME not set,"
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

			status  = set_user_name_password(uname, lname,
			    OM_DEFAULT_USER_PASSWORD);
			if (status != 0) {
				om_debug_print(OM_DBGLVL_INFO,
				    "Couldn't set user password data\n");
			}
			/*
			 * Save the login name, it is needed to create user's
			 * home directory
			 */
			save_login_name = strdup(lname);
		} else {
			/*
			 * Got user name and password
			 */
			om_debug_print(OM_DBGLVL_INFO, "Got user password\n");
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

	if (create_pfinstall_profile(pf) != OM_SUCCESS) {
		om_log_print("Couldn't create install profile\n");
		status = OM_FAILURE;
		om_set_error(OM_INITIAL_INSTALL_PROFILE_FAILED);
		goto install_return;
	}

	/*
	 * We must add the shadow file to the transfer list, root
	 * password will be defaulted if not set. The call to SUInstall
	 * loads the data from the /etc/transfer_list to a set of
	 * data structures, so this has to be written before
	 * we call pfinstall.
	 */
	add_2_xfer(SHADOW_FILE, "SUNWcsr", OVERWRITE_STR);
	add_2_xfer(PASSWORD_FILE, "SUNWcsr", OVERWRITE_STR);

	/*
	 * The .sysIDtool.state file needs to be written before the
	 * install completes. The transfer list is processed
	 * before we return from pfinstall, so update the state
	 * here for install.
	 */
	set_system_state();

	/*
	 * Start the install.
	 */
	if (call_pfinstall(type, pf.profile_name, cb) != OM_SUCCESS) {
		om_log_print("Initial install failed\n");
		status = OM_FAILURE;
		om_set_error(OM_INITIAL_INSTALL_FAILED);
		goto install_return;
	}
	om_debug_print(OM_DBGLVL_INFO, "om_perform_install() returned"
	    " success. The install is started\n");
install_return:
	free(pf.install_type.install.diskname);
	free(pf.install_type.install.locales);
	free(pf.profile_name);
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
 * ------------------------ Local functions --------------------
 */

/*
 * create_pfinstall_profile
 * This function creates the profile using the name passed as part of the
 * om_profile_t structure.
 * Input:	om_profile_t pf - Create the profile using the information
 *		such as disk/slice name, list of locales, and install type
 * Output:	None
 * Return:	OM_SUCCESS, if the profile creation is successful
 *		OM_FAILURE, if the profile creation is failed.
 *
 * Notes:	SUNWCXall is the default meta cluster (software group)
 *		installed for initial install.
 */
int
create_pfinstall_profile(om_profile_t pf)
{
	FILE	*fp;
	char	buf[MAXNAMELEN];

	if (pf.profile_name == NULL) {
		return (OM_FAILURE);
	}

	fp = fopen(pf.profile_name, "w");
	if (fp == NULL) {
		return (OM_FAILURE);
	}

	if (pf.operation == OM_UPGRADE) {
		(void) fprintf(fp, "install_type upgrade\n");
		(void) fprintf(fp, "root_device %s\n",
		    pf.install_type.upgrade.slice);
	} else if (pf.operation == OM_INITIAL_INSTALL) {
		(void) fprintf(fp, "install_type initial_install\n");
		(void) fprintf(fp, "cluster SUNWCXall\n");
		(void) fprintf(fp, "usedisk %s\n",
		    pf.install_type.install.diskname);
		/*
		 * Set eeprom value to preserve for X86.
		 * X86 requires disk name where as sparc requires slice name.
		 */
		if (is_system_x86) {
			(void) fprintf(fp, "boot_device %s preserve\n",
			    pf.install_type.install.diskname);
		} else {
			(void) snprintf(buf, sizeof (buf), "%ss0\n",
			    pf.install_type.install.diskname);
			(void) fprintf(fp, "boot_device %s update\n", buf);
		}
		/*
		 * For X86 systems, write disk partition keyword (fdisk)
		 * create data for fdisk keyword
		 */
		if (is_system_x86) {
			if (!setup_profile_fdisk_entries(fp,
			    pf.install_type.install.diskname)) {
				(void) fclose(fp);
				return (OM_FAILURE);
			}
		}
		(void) fprintf(fp, "partitioning explicit\n");
		/*
		 * Create default based on the size
		 */
		if (!setup_profile_filesys_entries(fp,
		    pf.install_type.install.diskname)) {
			(void) fclose(fp);
			return (OM_FAILURE);
		}
		/*
		 * Setup locale entries in the jumpstart profile
		 */
		if (pf.install_type.install.locales != NULL) {
			if (!setup_profile_locale_entries(fp,
			    pf.install_type.install.locales)) {
				(void) fclose(fp);
				return (OM_FAILURE);
			}
		}
	}
	(void) fclose(fp);
	return (OM_SUCCESS);
}

/*
 * setup_profile_fdisk_entries
 * This function creates the profile entries for disk partitions using the
 * profile keyword fdisk.
 * Input:	File *fp - File pointer to the opened profile.
 *		char *diskname - Name of the disk where the partitions
 *		are created/modified.
 * Output:	None
 * Return:	B_TRUE, if the fdisk entries are created successfully
 *		B_FALSE, if creating fdisk entries failed
 */
boolean_t
setup_profile_fdisk_entries(FILE *fp, char *diskname)
{
	disk_target_t	*dt;
	disk_parts_t	*cdp;
	int		i;
	uint32_t	size1, size2;
	uint8_t		type1, type2;
	om_content_type_t	ctype;
	boolean_t	solpart_created = B_FALSE;
	boolean_t	solpart_deleted = B_FALSE;

	if (fp == NULL) {
		return (B_FALSE);
	}
	/*
	 * Check whether the disk exists in our cache.
	 * if not, return failure
	 */
	for (dt = system_disks; dt != NULL; dt = dt->next) {
		if (streq(dt->dinfo.disk_name, diskname)) {
			break;
		}
	}

	if (dt == NULL) {
		return (B_FALSE);
	}

	if (committed_disk_target == NULL) {
		/*
		 * No existing partitions and No new partitions.
		 * we can't proceed with install
		 */
		if (dt->dparts == NULL) {
			om_set_error(OM_NO_PARTITION_FOUND);
			return (B_FALSE);
		}
		/*
		 * Disk is not changed. We don't need to make any fdisk changes
		 * return success. But We have to make sure that there is a
		 * Solaris 2 partition. If there is a Linux Swap partition,
		 * convert it to Solaris 2 partition
		 */
		for (i = 0; i < FD_NUMPART; i++) {
			if (dt->dparts->pinfo[i].partition_type == SUNIXOS2) {
				return (B_TRUE);
			}
		}

		for (i = 0; i < FD_NUMPART; i++) {
			ctype = dt->dparts->pinfo[i].content_type;
			type1 = dt->dparts->pinfo[i].partition_type;

			/*
			 * Convert SUNIXOS only if it not linux swap
			 */
			if (type1 == SUNIXOS && ctype != OM_CTYPE_LINUXSWAP) {
				(void) fprintf(fp, "fdisk %s %d delete\n",
				    diskname, SUNIXOS);
				(void) fprintf(fp, "fdisk %s %s %u\n",
				    diskname, SOLARIS,
				    dt->dparts->pinfo[i].partition_size);
				return (B_TRUE);
			}
		}
		/*
		 * No Solaris partition. Do not proceed
		 */
		return (B_FALSE);
	}
	/*
	 * check whether disk partitions are changed for this install
	 * The caller should have called to commit the changes
	 */
	if (committed_disk_target->dparts == NULL) {
		return (B_FALSE);
	}
	/*
	 * The disk we got for install is different
	 * from the disk information committed before.
	 * So return error.
	 */
	if (!streq(diskname, committed_disk_target->dinfo.disk_name)) {
		return (B_FALSE);
	}

	/*
	 * Now find out the changed partitions
	 * For each changed partition create a delete and create fdisk
	 * entries.
	 */
	cdp = committed_disk_target->dparts;
	for (i = 0; i < FD_NUMPART; i++) {
		/*
		 * Skip deleting old fdisk entries if there are no fdisk
		 * partitions currently defined
		 */
		if (dt->dparts == NULL) {
			break;
		}
		size1 = dt->dparts->pinfo[i].partition_size;

		/*
		 * skip the entries not configured before
		 */
		if (size1 == 0) {
			continue;
		}
		type1 = dt->dparts->pinfo[i].partition_type;
		size2 = cdp->pinfo[i].partition_size;
		type2 = cdp->pinfo[i].partition_type;

		if ((size1 != size2) || (type1 != type2)) {
			if (type1 == SUNIXOS || type1 == SUNIXOS2) {
				/*
				 * We need only one delete per type
				 */
				if (!solpart_deleted) {
					(void) fprintf(fp,
					    "fdisk %s %s delete\n",
					    diskname, SOLARIS);
					solpart_deleted = B_TRUE;
				}
			} else {
				(void) fprintf(fp, "fdisk %s %d delete\n",
				    diskname, type1);
			}
		}
	}

	for (i = 0; i < FD_NUMPART; i++) {
		/*
		 * Get the size and type only if disk partitions are
		 * defined currently on the system.
		 */
		if (dt->dparts != NULL) {
			size1 = dt->dparts->pinfo[i].partition_size;
			type1 = dt->dparts->pinfo[i].partition_type;
		} else {
			size1 = 0;
			type1 = 0;
		}
		size2 = cdp->pinfo[i].partition_size;
		type2 = cdp->pinfo[i].partition_type;
		/*
		 * Create new partition only if the type/size is changed
		 */
		if ((size1 != size2) || (type1 != type2)) {
			/*
			 * Create new partitions only if size > 0
			 * and the type is solaris/DOS
			 */
			if (size2 > 0) {
				int maxsize;
				/*
				 * We need to include overhead. This is already
				 * while verifying the disk partition.
				 * We don't want pfinstall to fail
				 */
				maxsize = dt->dinfo.disk_size - OVERHEAD_IN_MB;
				if (size2 > maxsize) {
					size2 = maxsize;
				}
				if (type2 == SUNIXOS2) {
					(void) fprintf(fp, "fdisk %s %s %u\n",
					    diskname, SOLARIS, size2);
					solpart_created = B_TRUE;
				}
				if (type2 == DOSHUGE) {
					(void) fprintf(fp, "fdisk %s %s %u\n",
					    diskname, DOSPRIMARY, size2);
				} else {
					om_debug_print(OM_DBGLVL_INFO,
					    "Invalid partition %d in create\n",
					    type2);
				}
			}
		}
	}

	/*
	 * we need a solaris partition to continue with install
	 * If solaris part id is deleted and not recreated, we will be
	 * in trouble. So go through the partition table again and
	 * recreate solaris partition
	 */
	if (solpart_deleted && !solpart_created) {
		for (i = 0; i < FD_NUMPART; i++) {
			size2 = cdp->pinfo[i].partition_size;
			type2 = cdp->pinfo[i].partition_type;

			if (type2 == SUNIXOS2 && size2 > 0) {
				(void) fprintf(fp, "fdisk %s %s %u\n",
				    diskname, SOLARIS, size2);
			}
		}
	}
	return (B_TRUE);
}

/*
 * setup_profile_filesys_entries
 * This function creates the profile entries for disk slices using the
 * profile keyword filesys.
 * Input:	File *fp - File pointer to the opened profile.
 *		char *diskname - Name of the disk where the slices
 *		are created/modified.
 * Output:	None
 * Return:	B_TRUE, if the filesys entries are created successfully
 *		B_FALSE, if creating filesys entries failed
 *
 * Notes: 	The Default layout will be based on size of the disk/partition
 * Disk size		swap		root		root2	/export/home
 * =========================================================================
 *  8 GB - 10 GB	0.5G		Rest		N/A		0.5G
 *					(7G-9G)
 * 10 GB - 20 GB	1G		75% disk	N/A		Rest
 *					(8G - 15G)
 * 20 GB - 30 Gb	2G		30% disk	30% disk	Rest
 *					(Min 8G)	(Min 8G)
 * > 30 GB		2G		30% disk	30% disk	Rest
 *					(8G - 15G)	(8G - 15G)
 */
boolean_t
setup_profile_filesys_entries(FILE *fp, char *diskname)
{
	disk_target_t	*dt;
	int		i;
	uint32_t	size = 0;
	uint32_t	root_size = 0;
	uint32_t	swap_size = 0;
	uint32_t	second_root_size = 0;
	uint32_t	export_home_size = 0;

	if (fp == NULL) {
		return (B_FALSE);
	}
	/*
	 * Check whether the disk exists in our cache.
	 * if not, return failure
	 */
	for (dt = system_disks; dt != NULL; dt = dt->next) {
		if (streq(dt->dinfo.disk_name, diskname)) {
			break;
		}
	}

	if (dt == NULL) {
		return (B_FALSE);
	}

	if (committed_disk_target != NULL) {
		/*
		 * The disk we got for install is different
		 * from the disk information committed before.
		 * So return error.
		 */
		if (!streq(diskname, committed_disk_target->dinfo.disk_name)) {
			return (B_FALSE);
		}

		if (committed_disk_target->dparts == NULL) {
			return (B_FALSE);
		}
		dt = committed_disk_target;
	}

	/*
	 * For X86, get the partition size and for SPARC, get the disk size
	 */
	if (is_system_x86) {
		for (i = 0; i < FD_NUMPART; i++) {
			if (dt->dparts->pinfo[i].partition_type == SUNIXOS2) {
				size = dt->dparts->pinfo[i].partition_size;
				break;
			}
		}

		/*
		 * If there is no Solaris2 paritions, use the Linux Swap
		 * partition and it will be converted to Solaris2 by the
		 * installer.
		 */
		if (size == 0) {
			for (i = 0; i < FD_NUMPART; i++) {
				if (dt->dparts->pinfo[i].partition_type
				    == SUNIXOS) {
					size =
					    dt->dparts->pinfo[i].partition_size;
				}
			}
		}
	} else if (is_system_sparc) {
		size = dt->dinfo.disk_size;
	} else {
		/*
		 * It should be SPARC or X86
		 */
		return (B_FALSE);
	}

	if (size == 0) {
		return (B_FALSE);
	}

	/*
	 * Set the swap size
	 */
	if (size > TWENTY_GB_TO_MB) {
		swap_size = TWO_GB_TO_MB;
		root_size = (uint32_t)(size * 3)/10;
		if (root_size > MAX_ROOT_SIZE) {
			root_size = MAX_ROOT_SIZE;
		} else if (root_size < MIN_ROOT_SIZE) {
			root_size = MIN_ROOT_SIZE;
		}
		second_root_size = root_size;
	} else if (size > TEN_GB_TO_MB) {
		swap_size = ONE_GB_TO_MB;
		root_size = (uint32_t)(size * 3)/4;
	} else if (size >= EIGHT_GB_TO_MB) {
		swap_size = HALF_GB_TO_MB;
		export_home_size = HALF_GB_TO_MB;
	} else {
		om_set_error(OM_SIZE_IS_SMALL);
		return (B_FALSE);
	}

	/*
	 * Write out the filesys jumpstart entries
	 */
	if (root_size > 0) {
		(void) fprintf(fp, "filesys rootdisk.s0 %d %s\n",
		    root_size, ROOT_FS);
	} else {
		(void) fprintf(fp, "filesys rootdisk.s0 %s %s\n",
		    FREE_KEYWORD, ROOT_FS);
	}

	(void) fprintf(fp, "filesys rootdisk.s1 %d %s\n", swap_size, SWAP_FS);
	if (second_root_size > 0) {
		(void) fprintf(fp, "filesys rootdisk.s4 %d %s\n",
		    second_root_size, SECOND_ROOT_FS);
	}
	if (export_home_size > 0) {
		(void) fprintf(fp, "filesys rootdisk.s7 %d %s\n",
		    export_home_size, EXPORT_FS);
	} else {
		(void) fprintf(fp, "filesys rootdisk.s7 %s %s\n",
		    FREE_KEYWORD, EXPORT_FS);
	}
	return (B_TRUE);
}

/*
 * setup_profile_locale_entries
 * This function creates the profile entries for locales selected by the
 * user to be installed
 * Input:	File *fp - File pointer to the opened profile.
 *		char *locales - List of locales separated by space
 * Output:	None
 * Return:	B_TRUE, if the locale entries are created successfully
 *		B_FALSE, if creating locale entries failed
 */
boolean_t
setup_profile_locale_entries(FILE *fp, char *locales)
{
	char		*tok;
	char		*lasts;

	if (fp == NULL) {
		return (B_FALSE);
	}

	if (locales == NULL) {
		return (B_TRUE);
	}

	/*
	 * To reinitialize the list to B_FALSE(added) already.
	 */

	init_shortloclist();
	/*
	 * The list of locales are passed with a space as the delimiter
	 */
	if ((tok = strtok_r(locales, " ", &lasts)) != NULL) {
		(void) fprintf(fp, "locale %s\n", tok);
		add_shortloc(tok, fp);
		while ((tok = strtok_r(NULL, " ", &lasts)) != NULL) {
			(void) fprintf(fp, "locale %s\n", tok);
			add_shortloc(tok, fp);
		}
	}
	return (B_TRUE);
}

/*
 * call_pfinstall
 * This function creates the a thread to execute the pfinstall command and
 * another thread to handle callbacks.
 * Input:	install_type - initial_install/upgrade
 *		char *profile - Full path of the profile
 *		om_call_back_t *cb - The callback function
 * Output:	None
 * Return:	OM_SUCCESS, if the all threads are started successfully
 *		OM_FAILURE, if the there is a failure
 */
int
call_pfinstall(om_install_type_t install_type,
    char *profile, om_callback_t cb)
{
	struct icba	*cb_args;
	int		ret;
	int		i;
	char		*profile_file;
	pthread_t	callback_thread;
	pthread_t	pfinstall_thread;

	if (profile == NULL) {
		return (OM_FAILURE);
	}
	if (access(profile, R_OK) < 0) {
		return (OM_FAILURE);
	}

	profile_file = strdup(profile);

	if (profile_file == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	/*
	 * Create a thread for running pfinstall
	 */
	ret = pthread_create(&pfinstall_thread, NULL,
	    run_pfinstall, (void *)profile_file);

	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		return (OM_FAILURE);
	}

	/*
	 * The callback thread needs to be started only if
	 * pfinstall is started. Wait for maximum of two minutes
	 * for the pfinstall to start. If there is a problem,
	 * let the caller know that pfinstall cannot be started
	 */
	for (i = 0; i < 60; i++) {
		if (pfinstall_pid > 0) {
			break;
		}
		(void) sleep(2);
	}

	if (pfinstall_pid <= 0) {
		/*
		 * If the callback is defined, send a callback
		 * to indicate the failure.
		 * Also login to the logfile
		 */
		om_log_print("pfinstall couldn't be started\n");
		om_set_error(OM_PFINSTALL_FAILURE);
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

/*
 * run_pfinstall
 * This function forks and execs pfinstall in the child. The parent will be
 * waiting for the child to exit.
 * Input:	void *arg - Pointer to the pfinstall arguments.
 *		Currently the full path of the profile is passed.
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
void *
run_pfinstall(void *arg)
{
	char	*command[10];
	int	n = 0;
	int	status = 0;
	char	*profile = (char *)arg;
	pid_t	pid, w;
	int	devnull;

	if (profile == NULL) {
		status = -1;
		pthread_exit((void *)&status);
	}

	/*
	 * We don't want the output from stdout and stderr so
	 * close them, open /dev/null and dup2 these to /dev/null.
	 */
	devnull = open(PATH_DEVNULL, O_RDWR);
	if (devnull == -1) {
		status = -1;
		om_log_print("Can't open /dev/null\n");
		om_set_error(OM_CANT_OPEN_FILE);
		pthread_exit((void *)&status);
	}

	/*
	 * Create a child to execute pfinstall
	 */
	if ((pid = fork()) == 0) {
		(void) unlink(PROGRESS_FILE);
		(void) close(0);
		(void) close(1);
		(void) close(2);
		(void) dup2(devnull, 0);
		(void) dup2(devnull, 1);
		(void) dup2(devnull, 2);
		(void) close(devnull);
		/*
		 * Set up the arguments to run pfinstall
		 */
		if (install_test) {
			command[n++] = INSTALL_TEST_CMD;
			if (install_type == OM_UPGRADE) {
				command[n++] = "-u";
			}
		} else {
			command[n++] = INSTALL_CMD;
		}

		if (ls_get_dbg_level() >= LS_DBGLVL_TRACE) {
			command[n++] = "-x";
			command[n++] = "10";
		}

		command[n++] = "-r";
		command[n++] = PROGRESS_FILE;
		command[n++] = profile;
		command[n++] = (char *)0;

		(void) execve(command[0], command, environ);
		/* shouldn't be here, but ... */
		status = OM_FAILURE;
	} else if (pid == -1) {
		status = OM_FAILURE;
		pfinstall_pid = -1;
	} else {
		pfinstall_pid = pid;
		/*
		 * Wait for the child process to exit
		 */
		do {
			w = waitpid(pfinstall_pid, &status, 0);
		} while (w == -1 && errno == EINTR);

		/*
		 * Get the exit status from the child process
		 */

		if (WIFEXITED(status)) {
			status = (int)((char)(WEXITSTATUS(status)));
		} else if (WIFSIGNALED(status)) {
			status = (int)((char)(WTERMSIG(status)));
		} else if (WIFSTOPPED(status)) {
			status = (int)((char)(WSTOPSIG(status)));
		}

		/*
		 * Write to the pfinstall progress file that there is an error.
		 * A callback will be sent to the caller with the error number
		 */
		if (status != 0 && status != 1) {
			notify_error_status(status);
		} else {
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
			/*
			 * Transfer the gui-install.log and the jumpstart
			 * profile to /var/sadm/system/nsi
			 */
			transfer_nsi_files(profile);
			free(profile);
		}
	}

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
	char			proc_pid_file[MAXPATHLEN];
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
	 * If the process is active but the output file is not yet available,
	 * wait for up to 2 minutes for it to become available. If the process
	 * to monitor terminates, return success as there is no progress that
	 * can be reported. If the progress file becomes available continue.
	 */
	(void) snprintf(proc_pid_file, sizeof (proc_pid_file),
	    "/proc/%ld", cp->pid);

	for (i = 0; i < 60; i++) {
		/* If process does not exist, return success. */
		if (access(proc_pid_file, R_OK|F_OK) != 0) {
			status = OM_NO_PROCESS;
			goto thread_end;
		}
		/* If progress file exists, exit loop. */
		if (access(PROGRESS_FILE, R_OK|F_OK) == 0) {
			break;
		}
		/* Process exists but progress file doesnt: sleep and retry. */
		(void) sleep(2);
	}

	/*
	 * If the process is not available, no progress to report.
	 */
	if (access(proc_pid_file, R_OK) != 0) {
		status = OM_NO_PROCESS;
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
	 * Initialize the callback param
	 */
	cb_data.num_milestones = 3;
	if (cp->install_type == OM_UPGRADE) {
		cb_data.callback_type = OM_UPGRADE_TYPE;
	} else {
		cb_data.callback_type = OM_INSTALL_TYPE;
	}

	/*
	 * Send an initial callback with milestones info
	 */
	if (cp->install_type == OM_INITIAL_INSTALL) {
		/*
		 * We don't get callbacks for target instantiation
		 * with pfinstall. So we send a callback with info.
		 * that it is done.
		 */
		if (!install_test) {
			cb_data.curr_milestone = OM_TARGET_INSTANTIATION;
			/*
			 * We don't get feedback from pfinstall till
			 * packages are getting added. So this is a buffer
			 * to make progress bar to appear smooth
			 */
			for (i = 1; i <= 10; i++) {
				cb_data.percentage_done = i * 10;
				/*
				 * call the callback
				 */
				cp->cb(&cb_data, app_data);
				(void) sleep(6);
			}
		}
	}

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
			 * If pfinstall failed, then we have to let the
			 * caller to know that installer is down
			 */
			if (milestone == OM_INSTALLER_FAILED) {
				status = OM_PFINSTALL_FAILURE;
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

		/*
		 * If process has died, make the loop to end
		 */
		if (access(proc_pid_file, R_OK) != 0) {
			sleep_for_callback = B_FALSE;
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
			cb_data.curr_milestone = OM_INVALID_MILESTONE;
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
	 * for installing Solaris.
	 */
	return (8192);
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
	pthread_t	tools_install_thread;
	struct icba	*cb_args;
	int		ret;
	int		i;

	if (access(TOOLS_CMD, F_OK) != 0 && access(TOOLS_TEST_CMD, F_OK) != 0) {
		om_set_error(OM_MISSING_TOOLS_SCRIPT);
		return (OM_FAILURE);
	}

	ret = pthread_create(&tools_install_thread, NULL,
	    run_tools_script, NULL);
	if (ret != 0) {
		om_set_error(OM_ERROR_THREAD_CREATE);
		return (OM_FAILURE);
	}
	/*
	 * The callback thread needs to be started only if the tools script
	 * starts. Wait for maximum of two minutes it to start. If there is a
	 * problem, let the caller know that the script couldn't be started
	 */
	for (i = 0; i < 60; i++) {
		if (tools_install_pid > 0) {
			break;
		}
		(void) sleep(2);
	}
	if (tools_install_pid <= 0) {
		/*
		 * If the callback is defined, send a callback
		 * to indicate the failure.
		 * Also login to the logfile
		 */
		om_log_print("Tools script couldn't be started\n");

		om_set_error(OM_TOOLS_INSTALL_FAILURE);
		return (OM_FAILURE);
	}
	/*
	 * If there is no callback, don't create callback thread
	 */
	if (cb != NULL) {
		cb_args = calloc(1, sizeof (struct icba));
		if (cb_args == NULL) {
			om_set_error(OM_NO_SPACE);
			return (OM_FAILURE);
		}

		cb_args->pid = tools_install_pid;
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
 * run_tools_script
 * This function forks and execs pfinstall in the child. The parent will be
 * waiting for the child to exit.
 * Input:	void *arg - Pointer to the tools script arguments.
 * Output:	None
 * Return:	status is returned as part of pthread_exit function
 */
/*ARGSUSED*/
void *
run_tools_script(void *arg)
{
	char	*command[10];
	int	status = 0;
	pid_t	pid, w;
	int	n = 0;
	int	devnull;

	/*
	 * We don't want the stdin,stderr, stdout data so
	 * close them, open /dev/null and dup2 these to /dev/null.
	 */
	devnull = open(PATH_DEVNULL, O_RDWR);
	if (devnull == -1) {
		status = -1;
		om_log_print("Can't open /dev/null\n");
		om_set_error(OM_CANT_OPEN_FILE);
		pthread_exit((void *)&status);
	}
	/*
	 * Create a child to execute tools installer
	 */
	if ((pid = fork()) == 0) {
		(void) close(0);
		(void) close(1);
		(void) close(2);
		(void) dup2(devnull, 0);
		(void) dup2(devnull, 1);
		(void) dup2(devnull, 2);
		(void) close(devnull);

		if (access(TOOLS_CMD, F_OK) == 0) {
			command[n++] = TOOLS_CMD;
			command[n++] = "-R";
			command[n++] = INSTALLED_ROOT_DIR;
		} else {
			command[n++] = TOOLS_TEST_CMD;
		}
		command[n++] = (char *)0;
		(void) execve(command[0], command, environ);
		/* shouldn't be here, but ... */
		status = OM_FAILURE;
	} else if (pid == -1) {
		status = OM_FAILURE;
		tools_install_pid = -1;
	} else {
		tools_install_pid = pid;
		/*
		 * Wait for the child process to exit
		 */
		do {
			w = waitpid(tools_install_pid, &status, 0);
		} while (w == -1 && errno == EINTR);

		/*
		 * Get the exit status from the child process
		 */

		if (WIFEXITED(status)) {
			status = (int)((char)(WEXITSTATUS(status)));
		} else if (WIFSIGNALED(status)) {
			status = (int)((char)(WTERMSIG(status)));
		} else if (WIFSTOPPED(status)) {
			status = (int)((char)(WSTOPSIG(status)));
		}
	}
	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
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
	char			proc_pid_file[MAXPATHLEN];
	int16_t			status = 0;
	boolean_t		sleep_for_callback = B_TRUE;
	uintptr_t		app_data = 0;
	struct {
		time_t len; /* len of milestone period relative to start time */
		om_milestone_type_t id;
	} milestone[] = {
	    {PCT_TOOLS_SUNSTUDIO * EST_DURATION / 100, OM_TOOLS_SUNSTUDIO},
	    {PCT_TOOLS_NETBEANS * EST_DURATION / 100, OM_TOOLS_NETBEANS},
	    {PCT_TOOLS_JAVAAPPSVR * EST_DURATION / 100, OM_TOOLS_JAVAAPPSVR}
	};
	const int nmilestones = sizeof (milestone) / sizeof (milestone[0]);
	time_t	stime = time(0);
	int	imilestone = 0;
	int16_t	percent;
	int16_t	last_percent = -1;

	cp = (struct icba *)args;

	(void) snprintf(proc_pid_file, sizeof (proc_pid_file),
	    "/proc/%ld", cp->pid);

	/* If process does not exist, return success. */
	if (access(proc_pid_file, R_OK|F_OK) != 0) {
		status = OM_NO_PROCESS;
		goto thread_end;
	}
	/*
	 * Initialize the callback param
	 */
	cb_data.callback_type = OM_TOOLS_INSTALL_TYPE;
	cb_data.num_milestones = nmilestones;

	/*
	 * Send an initial callback with milestones info
	 */

	/*
	 * Loop forever - wait for either the process being monitored to
	 * terminate or for data to be written to the progress file:
	 * - If the process terminates, return from this function.
	 * - If there is data available from the progress file, call
	 *   callback to inform the progress.
	 * Sleep between passes so as not to consume too much cpu.
	 */

	while (sleep_for_callback) {
		time_t ctime;

		/* Sleep 2 seconds between callbacks */
		(void) sleep(2);

		ctime = time(0);

		percent = 100 * (ctime - stime) / milestone[imilestone].len;
		/* if on last milestone and still not done */
		if (imilestone == nmilestones - 1 && percent > 98)
			percent = 98; /* don't go to 100 percent yet */
		else if (percent > 100)
			percent = 100;
		if (percent != last_percent) {
			cb_data.curr_milestone = milestone[imilestone].id;
			cb_data.percentage_done = percent;
			/*
			 * call the callback
			 */
			cp->cb(&cb_data, app_data);
			last_percent = percent;
		}
		/* determine milestone change */
		if (percent >= 100 && imilestone < nmilestones - 1) {
			stime = ctime;
			imilestone++;
		}
		/*
		 * If process has finished or died, make the loop to end
		 */
		if (access(proc_pid_file, R_OK) != 0) {
			sleep_for_callback = B_FALSE;
		}
	}
	/*
	 * Either the process being monitored died OR all bytes have been
	 * processed. Close the progress file and return
	 */
thread_end:

	/*
	 * Send a callback indicating that the callbacks are done
	 */
	if (status != OM_SUCCESS) {
		cb_data.curr_milestone = -1;
		cb_data.percentage_done = status;
	} else {
		cb_data.curr_milestone = milestone[nmilestones-1].id;
		cb_data.percentage_done = 100;
	}
	/* call the callback */
	cp->cb(&cb_data, app_data);

	/*
	 * The args allocated when this thread was created. The creator of this
	 * thread won't be freeing the space allocated for args.
	 */
	free(cp);

	pthread_exit((void *)&status);
	/* LINTED [no return statement] */
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
	FILE *rfp, *wfp;
	char tmpname[128], table_name[128], buff[1024], dup[1034];
	char *p;
	int fld, keypos, done = 0;

	(void) snprintf(tmpname, sizeof (tmpname), "/tmp/orch%d",
	    getpid());
	if ((wfp = fopen(tmpname, "w")) == NULL)  {
		om_log_print("Can't open file %s\n", tmpname);
		om_set_error(OM_CANT_OPEN_FILE);
		return (OM_FAILURE);
	}
	(void) snprintf(table_name, sizeof (table_name),
	    "/tmp/root/etc/inet/%s", table);

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

	if (rename(tmpname, table_name)) {
		om_debug_print(OM_DBGLVL_ERR,
		    "Cannot rename table %s\n", tmpname);
		om_set_error(OM_CANT_WRITE_TMP_FILE);
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
add_2_xfer(char *name, char *pkg, char *type)
{
	struct	stat stat_buf;
	FILE 	*fp;

	if (stat(TRANS_LIST, &stat_buf) == -1)
		return;

	if ((fp = fopen(TRANS_LIST, "a")) == NULL) {
		om_debug_print(OM_DBGLVL_WARN, "unable to open xfer list\n");
		return;
	}

	if (fprintf(fp, "%s %s %s\n", name, pkg, type) <= 0)
		om_debug_print(OM_DBGLVL_WARN, "unable to write xfer list\n");

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
		free(save_login_name);
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
 * Copy the gui-install.log and jumpstart profile created for install/upgrade
 * to /var/sadm/system/nsi
 * Create the new files under /var/sadm/system/nsi with date signature so that
 * it can be mapped to the install/upgrade logs (using the date)
 */
static void
transfer_nsi_files(char *profile)
{
	char	new_logfile[MAXNAMELEN];
	char	new_profile[MAXNAMELEN];
	char	temp[MAXPATHLEN];
	char	temp1[MAXPATHLEN];
	char	*file;
	DIR	*dirp;
	int	ret;

	if (profile == NULL) {
		return;
	}
	/*
	 * Check for existence of gui-install.log and jumpstart profile
	 * If atleast one of them is present continue.
	 */
	(void) snprintf(temp, sizeof (temp), "/tmp/%s", GUI_INSTALL_LOG);
	if (access(temp, F_OK) != 0 && access(profile, F_OK != 0)) {
		return;
	}
	/*
	 * Check whether the target directory /a/var/sadm/system/nsi
	 * exists. If not create it
	 */
	errno = 0;
	(void) snprintf(temp, sizeof (temp), "%s/%s",
	    INSTALLED_ROOT_DIR, NSI_LOG_DIRECTORY);
	dirp = opendir(temp);
	if (dirp == NULL) {
		/*
		 * Create and set the directory permission to 755
		 */
		ret = mkdir(temp,
		    S_IRWXU | S_IRGRP | S_IXGRP | S_IROTH | S_IXOTH);
		if (ret) {
			om_log_print(NSI_LOG_DIR_FAILED, temp);
			return;
		}
	} else {
		(void) closedir(dirp);
	}

	/*
	 * Create a dated file name for gui-install.log
	 */
	file = create_dated_file(temp, GUI_INSTALL_LOG);
	if (file == NULL) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CREATE_FILE_FAILED, temp);
		return;
	}
	(void) strlcpy(new_logfile, file, sizeof (new_logfile));
	free(file);

	/*
	 * Create a dated file name for jumpstart profile
	 */
	file = create_dated_file(temp, PROFILE_NAME);
	if (file == NULL) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CREATE_FILE_FAILED, temp);
		return;
	}
	(void) strlcpy(new_profile, file, sizeof (new_profile));
	free(file);

	/*
	 * Copy gui-install_log and profile from /tmp
	 */
	(void) snprintf(temp, sizeof (temp), "/tmp/%s", GUI_INSTALL_LOG);
	(void) snprintf(temp1, sizeof (temp1), "%s/%s/%s",
	    INSTALLED_ROOT_DIR, NSI_LOG_DIRECTORY, new_logfile);
	if (copy_file(temp, temp1)) {
		om_debug_print(OM_DBGLVL_INFO, NSI_MOVE_FILE,
		    GUI_INSTALL_LOG, temp1);
	}

	(void) snprintf(temp1, sizeof (temp1), "%s/%s/%s",
	    INSTALLED_ROOT_DIR, NSI_LOG_DIRECTORY, new_profile);
	if (copy_file(profile, temp1)) {
		om_debug_print(OM_DBGLVL_INFO, NSI_MOVE_FILE,
		    PROFILE_NAME, temp1);
	}
	/*
	 * Create symlink so that gui-install_log will point to the latest
	 * dated gui-install_log
	 */
	(void) snprintf(temp, sizeof (temp), "%s/%s",
	    INSTALLED_ROOT_DIR, NSI_LOG_DIRECTORY);
	if (remove_and_relink(temp, new_logfile, GUI_INSTALL_LOG)) {
		om_debug_print(OM_DBGLVL_INFO, NSI_LINK_FILE,
		    GUI_INSTALL_LOG, new_logfile);
	}

	/*
	 * Create a symlink for the latest jumpstart profile
	 */
	if (remove_and_relink(temp, new_profile, PROFILE_NAME)) {
		om_debug_print(OM_DBGLVL_INFO, NSI_LINK_FILE,
		    PROFILE_NAME, new_logfile);
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

static void
umount_tmp(char *path)
{
	char cmd[MAXPATHLEN];

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/umount %s > /dev/null 2>&1", path);

	td_safe_system(cmd);
}
