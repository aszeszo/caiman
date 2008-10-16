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

#include <errno.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <stdarg.h>
#include <wait.h>
#include "admldb.h"
#include "ict_api.h"
#include "ict_private.h"
#include "ti_api.h"
#include "orchestrator_api.h"

static int ict_safe_system(char *, boolean_t);

/*
 * Global
 */

/*
 * Function:	ict_get_error()
 *
 * This function returns the current error number set by the last called
 * ICT function.
 *
 * Input:
 *    None
 *
 * Output:
 *    None
 *
 * Return:
 *    ict_status_t - One of the predefined install completion
 *    errors will be returned. If there is no error, ICT_SUCCESS
 *    will be returned. Each ICT function should set the ict_errno
 *    to 0 if there are no errors.
 *
 */
ict_status_t
ict_get_error()
{
	return (ict_errno);
} /* END ict_get_error() */

/*
 * Function:	set_error()
 *
 * This function sets the error number passed as the argument.
 *
 * Input:	ict_status_t - The error code that will be set.
 *
 * Output:
 *    None
 *
 * Return:
 *    ict_status_t - Echos the error number that was set.
 *
 */
static ict_status_t
set_error(ict_status_t local_errno)
{
	ict_errno = local_errno;
	return (ict_errno);
} /* END set_error() */

/*
 * Function:	ict_debug_print()
 *
 * This function posts the specified debug message.
 *
 * Input:
 *    dbg_lvl - indicates the severity level of the message.
 *    fmt - message format
 *
 * Output:
 *    None
 *
 * Return:
 *    None
 *
 */
static void
ict_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);

	/*
	 * When dbg_lvl is error this will force the message to start
	 * on a new line and stand out.
	 */
	if (dbg_lvl == ICT_DBGLVL_ERR) {
		(void) ls_write_dbg_message("", ICT_DBGLVL_INFO, "");
	}

	(void) ls_write_dbg_message("ICT", dbg_lvl, buf);
	va_end(ap);
} /* END ict_debug_print() */

/*
 * Function:	ict_log_print()
 *
 * This function logs the specified message.
 *
 * Input:
 *    fmt - message format
 *
 * Output:
 *    None
 *
 * Return:
 *    None
 *
 */
static void
ict_log_print(char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_log_message("ICT", buf);
	va_end(ap);
} /* END ict_log_print() */

/*
 * Function:	ict_configure_user_directory()
 *
 * This function configure the user directory. uid, gid are predefined. The
 * user directory has been created in export/home on the specified install
 * target by liborchestrator.
 * It is possible a new user account is not desired. So if login is NULL
 * or empty do nothing and simply return success.
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    login - The user login name the directory will match.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_configure_user_directory(char *target, char *login)
{
	char *_this_func_ = "ict_configure_user_directory";
	char	homedir[MAXPATHLEN];
	char	filesystem[MAXPATHLEN];
	char	cmd[MAXPATHLEN];
	int	ret;
	int	saverr = 0;
	uid_t	uid;
	gid_t	gid;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "login:%s\n", login);

	/*
	 * Confirm input arguments
	 */
	if ((login == NULL) || (strlen(login) == 0)) {
		ict_log_print(NOLOGIN_SPECIFIED, _this_func_);
		return (ICT_SUCCESS);
	}

	if ((target == NULL) || (strlen(target) == 0)) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	/*
	 * The user directory is created in liborchestrator
	 * perform_slim_install.c function do_ti()
	 */

	(void) snprintf(homedir, sizeof (homedir),
	    "%s%s/%s", target, EXPORT_FS, login);

	/*
	 * Home directory is successfully created.
	 * Change the ownership to the newly created user
	 */

	uid = (uid_t)ICT_USER_UID;
	gid = (gid_t)ICT_USER_GID;
	if (uid != 0 && gid != 0) {
		if (chown(homedir, uid, gid) != 0) {
			saverr = errno;
			ict_log_print(CHOWN_FAIL, _this_func_,
			    homedir, uid, gid,
			    strerror(saverr));
			return (set_error(ICT_CHOWN_FAIL));
		}
	} else {
		ict_log_print(CHOWN_INVALID, _this_func_,
		    homedir, uid, gid);
		return (set_error(ICT_INVALID_ID));
	}

	/*
	 * Change access permission mode of home directory
	 */
	if (chmod(homedir, S_IRWXU|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH) != 0) {
		saverr = errno;
		ict_log_print(CHMOD_FAIL, _this_func_, homedir,
		    strerror(saverr));
		return (set_error(ICT_CHMOD_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_configure_user_directory() */

/*
 * Function:	ict_set_user_profile()
 *
 * This function will create the initial user profile file on
 * the specified installation target.
 * It is possible a new user account is not desired. So if login is NULL
 * or empty do nothing and simply return success.
 *
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    login  - The login name of the user.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_user_profile(char *target, char *login)
{
	char *_this_func_ = "ict_set_user_profile";
	char	cmd[MAXPATHLEN];
	char	user_path[MAXPATHLEN];
	int	ict_status = 0;
	int	saverr = 0;
	uid_t	uid;
	gid_t	gid;
	char	path[MAXPATHLEN] =
	    "export PATH=\\/usr\\/gnu\\/bin:\\/usr\\/bin:\\/usr\\/X11\\/bin:"
	    "\\/usr\\/sbin:\\/sbin:$PATH";

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s login:%s\n",
	    target, login);
	/*
	 * Confirm input arguments
	 */
	if ((login == NULL) || (strlen(login) == 0)) {
		ict_log_print(NOLOGIN_SPECIFIED, _this_func_);
		return (ICT_SUCCESS);
	}

	if ((target == NULL) || (strlen(target) == 0)) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	/*
	 * copy the .profile from /etc/skel to the users home directory
	 * and make it the users .bashrc
	 */
	(void) snprintf(user_path, sizeof (user_path), "%s/%s/%s/%s",
	    target, USER_HOME, login, USER_BASHRC);

	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/sed -e '${G;s/$/%s/;}' %s >%s",
	    path, USER_PROFILE, user_path);
	ict_log_print(ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, B_FALSE);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_CRT_PROF_FAIL));
	}

	/*
	 * Change owner to user. Change group to staff.
	 */
	uid = (uid_t)ICT_USER_UID;
	gid = (gid_t)ICT_USER_GID;
	if (uid != 0 && gid != 0) {
		if (chown(user_path, uid, gid) != 0) {
			saverr = errno;
			ict_log_print(CHOWN_FAIL, _this_func_,
			    user_path, uid, gid,
			    strerror(saverr));
			return (set_error(ICT_CHOWN_FAIL));
		}
	} else {
		ict_log_print(CHOWN_INVALID, _this_func_,
		    user_path, uid, gid);
		return (set_error(ICT_INVALID_ID));
	}

	/*
	 * Change access permission mode of file
	 */
	if (chmod(user_path, S_IRUSR|S_IWUSR|S_IRGRP|S_IROTH) != 0) {
		saverr = errno;
		ict_log_print(CHMOD_FAIL, _this_func_, user_path,
		    strerror(saverr));
		return (set_error(ICT_CHMOD_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_set_user_profile() */

/*
 * Function:	ict_set_user_role()
 *
 * This function will set the user role, if needed, on the specified
 * install target.
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    login  - The login name of the user.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_user_role(char *target, char *login)
{
	char *_this_func_ = "ict_set_user_role";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s login:%s\n",
	    target, login);
	/*
	 * Confirm input arguments
	 */
	if ((target == NULL) || (strlen(target) == 0)) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	/*
	 * If a user login has not been specified then clear out user jack,
	 * and switch root out of being a role since no other user has
	 * been created.
	 *
	 * If a user login has been specified make that user
	 * a primary administrator.
	 *
	 */
	if ((login == NULL) || (strlen(login) == 0)) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e '/^jack/d' -e 's/type=role;//' %s >%s%s",
		    USER_ATTR_FILE, target, USER_ATTR_FILE);
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/^jack/%s/' %s > %s%s",
		    login, USER_ATTR_FILE, target, USER_ATTR_FILE);
	}

	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, B_FALSE);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_, cmd,
		    ict_status);
		return (set_error(ICT_SET_ROLE_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_set_user_role() */

/*
 * Function:	ict_set_lang_locale()
 *
 * This function will set the language locale in init file.
 *
 * Input:
 *    target  - The installation transfer target. A directory used by the
 *              installer as a staging area, historically /a
 *    localep - The language locale
 *    transfer_mode  - A flag indicating the transfer mode, IPS|CPIO.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_lang_locale(char *target, char *localep, int transfer_mode)
{
	char *_this_func_ = "ict_set_lang_locale";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;
	boolean_t redirect = B_FALSE;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s localep:%s\n",
	    target, localep);
	/*
	 * Confirm input arguments
	 */
	if (((localep == NULL) || (strlen(localep) == 0)) ||
	    ((target == NULL) || (strlen(target) == 0))) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	/*
	 * If transfer mode is IPS simply copy the existing file.
	 */
	if (transfer_mode == OM_IPS_TRANSFER) {
		(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s %s%s",
		    INIT_FILE, target, INIT_FILE);
		redirect = B_TRUE;
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/echo 'LANG=%s' >> %s%s",
		    localep, target, INIT_FILE);
		redirect = B_FALSE;
	}
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, redirect);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_, cmd,
		    ict_status);
		return (set_error(ICT_SET_LANG_FAIL));
	}

	if (transfer_mode == OM_IPS_TRANSFER) {
		/*
		 * XXX actually the caller should set the keyboard
		 * by calling om_set_keyboard_by_name() instead of
		 * doing this
		 *
		 */
		(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s %s%s",
		    KBD_DEF_FILE, target, KBD_DEF_FILE);
		redirect = B_TRUE;
		ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
		    _this_func_, cmd);
		ict_status = ict_safe_system(cmd, redirect);
		if (ict_status != 0) {
			ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_, cmd,
			    ict_status);
			return (set_error(ICT_SET_KEYBRD_FAIL));
		}
	}


	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_set_lang_locale() */

/*
 * Function:	ict_set_host_node_name()
 *
 * This function will set the hostname and nodename in the install target.
 * The hostname and nodename are set to the same value.
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    hostname - The hostname to be set.
 *    transfer_mode  - A flag indicating the transfer mode, IPS|CPIO.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_host_node_name(char *target, char *hostname, int transfer_mode)
{
	char *_this_func_ = "ict_set_host_node_name";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;
	boolean_t redirect = B_FALSE;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s hostname:%s\n",
	    target, hostname);
	/*
	 * Confirm input arguments
	 */
	if (((hostname == NULL) || (strlen(hostname) == 0)) ||
	    ((target == NULL) || (strlen(target) == 0))) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	/*
	 * Process host file.
	 *
	 * If transfer mode is IPS simply copy the existing file.
	 */
	if (transfer_mode == OM_IPS_TRANSFER) {
		(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s %s%s",
		    HOSTS_FILE, target, HOSTS_FILE);
		redirect = B_TRUE;
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/host %s/host %s/g' %s >%s%s",
		    DEFAULT_HOSTNAME, hostname, HOSTS_FILE, target, HOSTS_FILE);
		redirect = B_FALSE;
	}
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, redirect);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_SET_HOST_FAIL));
	}

	/*
	 * Process nodename file.
	 *
	 * If transfer mode is IPS simply copy the existing file.
	 */
	if (transfer_mode == OM_IPS_TRANSFER) {
		(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s %s%s",
		    NODENAME, target, NODENAME);
		redirect = B_TRUE;
	} else {
		(void) snprintf(cmd, sizeof (cmd),
		    "/bin/sed -e 's/%s/%s/g' %s >%s%s",
		    DEFAULT_HOSTNAME, hostname, NODENAME, target, NODENAME);
		redirect = B_FALSE;
	}
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, redirect);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_SET_NODE_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_set_host_node_name() */

/*
 * Function:	ict_installgrub()
 *
 * This function installs the GRand Unified Bootloader GRUB stage 1
 * and stage 2 files on the boot area of the specified device.
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    device - The device to install GRUB onto.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_installgrub(char *target, char *device)
{
	char *_this_func_ = "ict_installgrub";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s device:%s\n",
	    target, device);
	/*
	 * Confirm input arguments
	 */
	if (((device == NULL) || (strlen(device) == 0)) ||
	    ((target == NULL) || (strlen(target) == 0))) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/installgrub %s/boot/grub/stage1"
	    " %s/boot/grub/stage2 /dev/rdsk/%s",
	    target, target, device);
	ict_debug_print(ICT_DBGLVL_INFO, INSTALLGRUB_MSG, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);

	ict_status = ict_safe_system(cmd, B_TRUE);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_INST_GRUB_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_installgrub() */

/*
 * Function:	ict_snapshot()
 *
 * This function will create snapshots for the specified data set.
 *
 * Input:
 *    be_ds - The name of the be dataset to take a snapshot of.
 *    snapshot - The name to use for the snapshot.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_snapshot(char *be_ds, char *snapshot)
{
	char *_this_func_ = "ict_snapshot";
	char		cmd[MAXPATHLEN];
	nvlist_t	*be_args = NULL;
	int		ret = 0;

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "be_ds:%s snapshot:%s\n",
	    be_ds, snapshot);

	/*
	 * Confirm input arguments
	 */
	if (((be_ds == NULL) || (strlen(be_ds) == 0)) ||
	    ((snapshot == NULL) || (strlen(snapshot) == 0))) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}
	ict_debug_print(ICT_DBGLVL_INFO, SNAPSHOT_MSG, _this_func_,
	    be_ds, snapshot);

	/*
	 * Put arguments to be_create_snapshot() into an nvlist.
	 */
	if (nvlist_alloc(&be_args, NV_UNIQUE_NAME, 0) != 0) {
		ict_log_print(NVLIST_ALC_FAIL, _this_func_);
		return (set_error(ICT_NVLIST_ALC_FAIL));
	}

	if (nvlist_add_string(be_args, BE_ATTR_ORIG_BE_NAME, be_ds) != 0) {
		ict_log_print(NVLIST_ADD_FAIL, _this_func_, be_ds);
		nvlist_free(be_args);
		return (set_error(ICT_NVLIST_ADD_FAIL));
	}

	if (nvlist_add_string(be_args, BE_ATTR_SNAP_NAME, snapshot) != 0) {
		ict_log_print(NVLIST_ADD_FAIL, _this_func_, snapshot);
		nvlist_free(be_args);
		return (set_error(ICT_NVLIST_ADD_FAIL));
	}

	if ((ret = be_create_snapshot(be_args)) != 0) {
		ict_log_print(SNAPSHOT_FAIL, _this_func_, ret);
		nvlist_free(be_args);
		return (set_error(ICT_BE_CR_SNAP_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	nvlist_free(be_args);
	return (ICT_SUCCESS);

} /* END ict_snapshot() */

/*
 * Function:	ict_transfer_logs()
 *
 * This function will transfer the installation log file to the target.
 *
 * Input:
 *    src - Where to copy the log file from.
 *    dst - Where to copy the log file to.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCERSS - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_transfer_logs(char *src, char *dst)
{
	char *_this_func_ = "ict_transfer_logs";

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "src:%s dst:%s\n", src, dst);

	/*
	 * Confirm input arguments
	 */
	if (((src == NULL) || (strlen(src) == 0)) ||
	    ((dst == NULL) || (strlen(dst) == 0))) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	if (ls_transfer(src, dst) != LS_E_SUCCESS) {
		ict_log_print(TRANS_LOG_FAIL, _this_func_, src, dst);
		return (set_error(ICT_TRANS_LOG_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_transfer_logs() */

/*
 * ict_mark_root_pool_ready
 *
 * Mark ZFS root pool ready in order to let the world know
 * that the pool contains complete Solaris instance
 *
 * Parameters:
 *	pool_name - name of ZFS root pool
 *
 * Return:	ICT_SUCCESS - success
 *		ICT_MARK_POOL_FAIL - failure
 * Notes:
 */
ict_status_t
ict_mark_root_pool_ready(char *pool_name)
{
	char	cmd[MAXPATHLEN];
	int	ret;

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zfs set %s=%s %s", TI_RPOOL_PROPERTY_STATE,
	    TI_RPOOL_READY, pool_name);

	ret = ict_safe_system(cmd, B_TRUE);

	if ((ret == -1) || WEXITSTATUS(ret) != 0) {
		return (set_error(ICT_MARK_RPOOL_FAIL));
	} else {
		return (ICT_SUCCESS);
	}
} /* END ict_mark_root_pool_ready() */

/*
 * ict_safe_system()
 *
 * Function to execute shell commands in a thread-safe manner
 * Parameters:
 *	cmd - the command to execute
 *	redirect - if true
 *		- redirect stderr to stdout
 *		- redirect stdout to /dev/null
 *		- log output redirected from stderr
 * Return:
 *	return code from command
 *	if popen() fails, -1
 * Status:
 *	private
 */
static int
ict_safe_system(char *cmd, boolean_t redirect)
{
	FILE	*p;
	char	buf[MAXPATHLEN];

	/*
	 * catch stderr for debugging purposes
	 */
	if (redirect) {
		strlcpy(buf, cmd, sizeof (buf));
		if (strlcat(buf, " 2>&1 1>/dev/null", MAXPATHLEN) >= MAXPATHLEN)
			ict_debug_print(LS_DBGLVL_WARN,
			    "ict_safe_system: Couldn't redirect stderr\n");
		else
			cmd = buf;
	}

	ict_debug_print(LS_DBGLVL_INFO, "ict cmd: %s\n", cmd);

	if ((p = popen(cmd, "r")) == NULL)
		return (-1);

	if (redirect)
		while (fgets(buf, sizeof (buf), p) != NULL)
			ict_debug_print(LS_DBGLVL_WARN, " stderr:%s", buf);

	return (pclose(p));
}
