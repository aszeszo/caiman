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

#ifndef _ICT_PRIVATE_H
#define	_ICT_PRIVATE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <ict_api.h>
#include <ls_api.h>
#include <ti_api.h>

extern char *pre_inst_timezone;

/*
 * General defines
 */
#define	DEFAULT_HOSTNAME	"opensolaris"
#define	SOLARIS			"solaris"

/*
 * Root and user default defines
 */
#define	ROOT_NAME		"root"
#define	ROOT_PATH		"/"

#define	USER_PATH		"/export/home/"
#define	USER_STARTUP_SRC	"/etc/skel"
#define	USER_PROFILE		".profile"
#define	USER_BASHRC		".bashrc"
#define	USER_HOME		"export/home"

/*
 * file path defines
 */
#define	PATH_DEVNULL		"/dev/null"
#define	HOSTS_FILE		"/etc/inet/hosts"
#define	INIT_FILE		"/etc/default/init"
#define	NODENAME		"/etc/nodename"
#define	PASSWORD_FILE		"/etc/passwd"
#define	SHADOW_FILE		"/etc/shadow"
#define	USER_ATTR_FILE		"/etc/user_attr"
#define	EXPORT_FS		"/export/home"
#define	KBD_DEF_FILE		"/etc/default/kbd"

/*
 * Defines used by ict_escape()
 */
#define	APOSTROPHE		'\047'
#define	BACK_SLASH		'\134'

/*
 * ICT message format text
 */
#define	CHOWN_FAIL		"%s chown of %s %d:%d returned error %s\n"
#define	CHMOD_FAIL		"%s chmod of %s returned error %s\n"
#define	CHOWN_INVALID		"%s Cannot change ownership of %s to %d:%d\n"
#define	CREATE_USERDIR_FAIL	"%s mkdir of %s failed with error: %s\n"
#define	CURRENT_ICT		"current task: %s\n"
#define	INSTALLGRUB_MSG		"%s Running installgrub to set MBR\n"
#define	INVALID_ARG		"%s Invalid argument provided\n"
#define	LIST_TBL_ENTRY_FAIL	"%s No Entry. %s.\n\tAttempting to add it.\n"
#define	MALLOC_FAIL		"%s malloc failed for: %s\n"
#define	NOSPACE_USER_PATH	"%s Unable to allocate space for user path.\n"
#define	NOLOGIN_SPECIFIED	"%s No login name was specified.\n"
#define	NVLIST_ALC_FAIL		"%s nvlist_alloc failed\n"
#define	NVLIST_ADD_FAIL		"%s nvlist_add_string %s failed\n"
#define	RM_TBL_ENTRY_FAIL	"%s Could not remove table entry for %s\n%s\n"
#define	SET_TBL_ENTRY_FAIL	"%s Could not set table entry %s\n"
#define	SET_USR_PW		"%s Set %s in password and shadow file\n"
#define	SNAPSHOT_MSG		"%s using: pool %s snapshot %s\n"
#define	SNAPSHOT_FAIL		"%s be_create_snapshot() failed with: %d\n"
#define	SUCCESS_MSG		"%s Succeeded\n"
#define	ICT_SAFE_SYSTEM_CMD	"%s Issuing Command: %s\n"
#define	ICT_SAFE_SYSTEM_FAIL	"%s Command %s failed with %d\n"
#define	TRANS_LOG_FAIL		"%s Transfer Log files from %s to %s failed\n"

/*
 * Debugging levels
 */
#define	ICT_DBGLVL_EMERG	LS_DBG_LVL_EMERG
#define	ICT_DBGLVL_ERR		LS_DBGLVL_ERR
#define	ICT_DBGLVL_WARN		LS_DBGLVL_WARN
#define	ICT_DBGLVL_INFO		LS_DBGLVL_INFO

#ifdef __cplusplus
}
#endif

#endif	/* _ICT_PRIVATE_H */
