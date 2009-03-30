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

#include <errno.h>
#include <stdarg.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <wait.h>
#include <sys/utsname.h>
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
 * Function:	ict_escape()
 *
 * This function prepares a string, which could contain a single quote,
 * to be passed to the shell without the risk of the shell misinterpreting
 * the single quote.
 *
 * For example "Sepl O'Mally" would become "Sepl O'\''Mally"
 * This is required when a string, which could contain a single quote
 * will be passed to the shell using SYSTEM(3F).
 *
 * Note:
 *    This routine allocates memory which the caller must free.
 *
 * Input:
 *    The source string.
 *
 * Return:
 *    A copy of the resultant string with every occurance of
 *    a single quote replaced by '\''
 *
 *    If the result buffer res_buf is filled NULL is returned.
 *
 */
char *
ict_escape(char *source)
{
	char *cur = NULL;
	char *res_buf = NULL;
	char *src = source;
	int alloc_size = 0;
	int i = 0;
	int quote_cnt = 0;
	int src_len = 0;

	src_len = strlen(src);
	while (*src != '\0') {
		if (*src++ == APOSTROPHE) {
			quote_cnt++;
		}
	}

	/*
	 * If no quotes were found simply return strdup( source )
	 */
	if (quote_cnt == 0) {
		return (strdup(source));
	}

	/*
	 * Need enough memory to replace 1 quote with 4 characters.
	 * For each quote 3 new characters will be added.
	 * The extra 1 is for the null terminator.
	 */
	alloc_size = src_len + (quote_cnt * 3) + 1;
	if ((res_buf = calloc(alloc_size, sizeof (char))) == NULL) {
		return (NULL);
	}

	/*
	 * There is no need to check for buffer overflow of
	 * res_buf because enough memory was just allocated
	 * to hold the updated result string.
	 */

	cur = res_buf;
	src = source;
	while (*src != '\0') {
		if (*src != APOSTROPHE) {
			*cur++ = *src++;
		} else {
			src++;
			*cur++ = APOSTROPHE;
			*cur++ = BACK_SLASH;
			*cur++ = APOSTROPHE;
			*cur++ = APOSTROPHE;
		} /* END else */
	} /* END while() */

	return (res_buf);

} /* END ict_escape() */

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
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
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
	if (chown(homedir, uid, gid) != 0) {
		saverr = errno;
		ict_log_print(CHOWN_FAIL, _this_func_,
		    homedir, uid, gid,
		    strerror(saverr));
		return (set_error(ICT_CHOWN_FAIL));
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
 * This function will create the initial user profile on the specified
 * installation target, to include both a .profile file and a .bashrc file.
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
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
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
	 * copy the .profile file from /etc/skel to the user's home directory.
	 * Then set the owner and access permission.
	 */
	(void) snprintf(user_path, sizeof (user_path), "%s/%s/%s/%s",
	    target, USER_HOME, login, USER_PROFILE);
	(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s/%s %s",
	    USER_STARTUP_SRC, USER_PROFILE, user_path);

	ict_log_print(ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, B_TRUE);
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
	if (chown(user_path, uid, gid) != 0) {
		saverr = errno;
		ict_log_print(CHOWN_FAIL, _this_func_,
		    user_path, uid, gid,
		    strerror(saverr));
		return (set_error(ICT_CHOWN_FAIL));
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
	/*
	 * copy the .bashrc file from /etc/skel to the user's home directory.
	 * Then set the owner and access permission.
	 */
	(void) snprintf(user_path, sizeof (user_path), "%s/%s/%s/%s",
	    target, USER_HOME, login, USER_BASHRC);
	(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s/%s %s",
	    USER_STARTUP_SRC, USER_BASHRC, user_path);

	ict_log_print(ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, B_TRUE);
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
	if (chown(user_path, uid, gid) != 0) {
		saverr = errno;
		ict_log_print(CHOWN_FAIL, _this_func_,
		    user_path, uid, gid,
		    strerror(saverr));
		return (set_error(ICT_CHOWN_FAIL));
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
 *    transfer_mode  - A flag indicating the transfer mode, IPS|CPIO.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_user_role(char *target, char *login, int transfer_mode)
{
	char *_this_func_ = "ict_set_user_role";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;

	/*
	 * Confirm input arguments
	 */
	if ((target == NULL) || (strlen(target) == 0)) {
		ict_log_print(INVALID_ARG, _this_func_);
		return (set_error(ICT_INVALID_ARG));
	}

	ict_log_print(CURRENT_ICT, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, "target:%s login:%s\n",
	    target, login != NULL ? login : "NULL");


	if (transfer_mode == OM_CPIO_TRANSFER) {
		/*
		 * If a user login has not been specified then clear out user
		 * jack, and switch root out of being a role since no other
		 * user has been created.
		 *
		 * If a user login has been specified make that user
		 * a primary administrator.
		 *
		 */
		if ((login == NULL) || (strlen(login) == 0)) {
			/*
			 * Remove jack entry if it exists, and switch root
			 * from being a role if it is set to that.
			 */
			(void) snprintf(cmd, sizeof (cmd),
			    "/bin/sed -e '/^jack/d' "
			    "-e 's/^root::::type=role;/root::::/' %s > %s%s",
			    USER_ATTR_FILE, target, USER_ATTR_FILE);
		} else {
			(void) snprintf(cmd, sizeof (cmd),
			    "/bin/sed -e 's/^jack/%s/' %s > %s%s",
			    login, USER_ATTR_FILE, target, USER_ATTR_FILE);
		}

		ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
		    _this_func_, cmd);
		ict_status = ict_safe_system(cmd, B_FALSE);
		if (ict_status != 0) {
			ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_, cmd,
			    ict_status);
			return (set_error(ICT_SET_ROLE_FAIL));
		}
	} else if (transfer_mode == OM_IPS_TRANSFER) {
		/*
		 * If a user login name has been specified, change the root
		 * entry to be of type 'role' and add an entry for the login
		 * name.
		 */
		if ((login != NULL) && (strlen(login) != 0)) {
			char *tmp_ua = NULL;

			/* Generate a temporary file name to use */
			if ((tmp_ua = tmpnam(NULL)) == NULL) {
				ict_log_print(TMPNAM_FAIL, _this_func_);
				return (set_error(ICT_SET_ROLE_FAIL));
			}

			/* Change root entry to be of type 'role' */
			(void) snprintf(cmd, sizeof (cmd),
			    "/bin/sed -e 's/^root::::/root::::type=role;/' "
			    "%s%s > %s", target, USER_ATTR_FILE, tmp_ua);

			ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
			    _this_func_, cmd);
			ict_status = ict_safe_system(cmd, B_FALSE);
			if (ict_status != 0) {
				ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
				   cmd, ict_status);
				return (set_error(ICT_SET_ROLE_FAIL));
			}

			/* Add entry for login name */
			(void) snprintf(cmd, sizeof (cmd),
			    "/bin/echo '%s::::profiles=Primary "
			    "Administrator;roles=root' >> %s", login, tmp_ua);

			ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
			    _this_func_, cmd);
			ict_status = ict_safe_system(cmd, B_FALSE);
			if (ict_status != 0) {
				ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
				    cmd, ict_status);
				return (set_error(ICT_SET_ROLE_FAIL));
			}

			/* Copy updated file into place */
			(void) snprintf(cmd, sizeof (cmd),
			    "/bin/cp %s %s%s ; /bin/rm %s", tmp_ua, target,
			    USER_ATTR_FILE, tmp_ua);

			ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
			    _this_func_, cmd);
			ict_status = ict_safe_system(cmd, B_FALSE);
			if (ict_status != 0) {
				ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
				    cmd, ict_status);
				return (set_error(ICT_SET_ROLE_FAIL));
			}
		}
	} else {
		/* Unsupported transfer mode */
		ict_log_print(INVALID_ARG, _this_func_);
                return (set_error(ICT_INVALID_ARG));
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
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
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
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_set_host_node_name(char *target, char *hostname)
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
	 * host file processing will need to be reevaluated when
	 * hostname support is available in AI.
	 */
	(void) snprintf(cmd, sizeof (cmd),
	    "/bin/sed "
	    "-e 's/^127.*$/127.0.0.1 %s %s.local localhost loghost/' "
	    "-e 's/^::1.*$/::1 %s %s.local localhost loghost/' "
	    "%s >%s%s",
	    hostname, hostname, hostname, hostname, HOSTS_FILE,
	    target, HOSTS_FILE);
	redirect = B_FALSE;

	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);
	ict_status = ict_safe_system(cmd, redirect);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_SET_HOST_FAIL));
	}

	/*
	 * place host name in nodename file
	 */
	(void) snprintf(cmd, sizeof (cmd), "/bin/echo %s > %s%s",
	    hostname, target, NODENAME);
	redirect = B_FALSE;

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
 * Function:	ict_installboot()
 *
 * This function prepares a bootloader or bootblock on the specified device.
 *
 * For x86 platforms this involves the installation of the GRand Unified
 * Bootloader GRUB stage 1 and stage 2 files on the boot area of the
 * specified device using installboot(1M).
 *
 * For SPARC platforms this involves the installation of bootblocks in
 * a disk partition using installboot(1M).
 *
 *
 * Input:
 *    target - The installation transfer target. A directory used by the
 *             installer as a staging area, historically /a
 *    device - The device to install bootloader
 *    onto.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_installboot(char *target, char *device)
{
	char *_this_func_ = "ict_installboot";
	char	cmd[MAXPATHLEN];
	int	ict_status = 0;
#ifdef __sparc
	struct utsname name;
#endif

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

#ifdef __sparc
	if (uname(&name) < 0) {
		ict_debug_print(ICT_DBGLVL_ERR, INSTALLBOOT_UNAME_ERROR,
		    _this_func_);
		return (set_error(ICT_INST_BOOT_FAIL));
	}
	ict_debug_print(ICT_DBGLVL_INFO, "karch:%s\n", name.machine);

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/bin/env -i PATH=/usr/bin /usr/sbin/installboot -F zfs "
	    "%s/platform/%s/lib/fs/zfs/bootblk /dev/rdsk/%s",
	    target, name.machine, device);
#else
	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/installgrub %s/boot/grub/stage1"
	    " %s/boot/grub/stage2 /dev/rdsk/%s",
	    target, target, device);
#endif
	ict_debug_print(ICT_DBGLVL_INFO, INSTALLBOOT_MSG, _this_func_);
	ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD, _this_func_, cmd);

	ict_status = ict_safe_system(cmd, B_TRUE);
	if (ict_status != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ict_status);
		return (set_error(ICT_INST_BOOT_FAIL));
	}

	ict_log_print(SUCCESS_MSG, _this_func_);
	return (ICT_SUCCESS);

} /* END ict_installboot() */

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
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_snapshot(char *be_ds, char *snapshot)
{
	char *_this_func_ = "ict_snapshot";
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
 * Attempt to copy all of the desired log files. Return an error if
 * any are not successfully copied.
 *
 * Input:
 *    src - Where to copy the log file from.
 *    dst - Where to copy the log file to.
 *    transfer_mode  - A flag indicating the transfer mode, IPS|CPIO.
 *
 * Return:
 *    ICT_SUCCESS   - Successful Completion
 *    !ICT_SUCCESS  - Set failed and ict_errno is set indicate why.
 *
 */
ict_status_t
ict_transfer_logs(char *src, char *dst, int transfer_mode)
{
	char *_this_func_ = "ict_transfer_logs";

	char		cmd[MAXPATHLEN];
	int		ict_status = 0;
	ict_status_t	return_status = ICT_SUCCESS;
	int		i;
	char		*ai_logfiles_array[] = {
	    "/var/svc/log/application-auto-installer:default.log",
	    "/var/adm/messages",
	    "/tmp/ai_combined_manifest.xml",
	    "/tmp/ai_sd_log",
	    NULL };
	boolean_t	redirect = B_FALSE;

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
		return_status = set_error(ICT_TRANS_LOG_FAIL);
	}

	/*
	 * If transfer mode is IPS save some extra Auto Installer log files.
	 */
	if (transfer_mode == OM_IPS_TRANSFER) {
		for (i = 0; ai_logfiles_array[i] != NULL; i++) {
			(void) snprintf(cmd, sizeof (cmd), "/bin/cp %s %s%s",
			    ai_logfiles_array[i], dst, LS_LOGFILE_DST_PATH);
			redirect = B_TRUE;
			ict_debug_print(ICT_DBGLVL_INFO, ICT_SAFE_SYSTEM_CMD,
			    _this_func_, cmd);
			ict_status = ict_safe_system(cmd, redirect);
			if (ict_status != 0) {
				ict_log_print(ICT_SAFE_SYSTEM_FAIL,
				    _this_func_, cmd, ict_status);
				return_status = set_error(ICT_TRANS_LOG_FAIL);
			}
		}
	}

	if (return_status == ICT_SUCCESS)
		ict_log_print(SUCCESS_MSG, _this_func_);

	return (return_status);

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
	char *_this_func_ = "ict_mark_root_pool_ready";

	char	cmd[MAXPATHLEN];
	int	ret;

	ict_log_print(CURRENT_ICT, _this_func_);

	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/zfs set %s=%s %s", TI_RPOOL_PROPERTY_STATE,
	    TI_RPOOL_READY, pool_name);

	ret = ict_safe_system(cmd, B_TRUE);

	if ((ret == -1) || WEXITSTATUS(ret) != 0) {
		ict_log_print(ICT_SAFE_SYSTEM_FAIL, _this_func_,
		    cmd, ret);
		return (set_error(ICT_MARK_RPOOL_FAIL));
	} else {
		ict_log_print(SUCCESS_MSG, _this_func_);
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
