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

#ifndef _ICT_API_H
#define	_ICT_API_H

#ifdef __cplusplus
extern "C" {
#endif

#include <libnvpair.h>


/*
 * Root and user default defines
 */
#define	ICT_USER_UID		101
#define	ICT_USER_GID		10 /* staff */

/*
 * Error Codes
 *
 * Upon successful completion ICT IPA will return ICT_SUCCESS.
 * The global symbol ict_errno will be unaltered, therefor unpredictable.
 *
 * When an error is encountered ICT IPA will return a value
 * other than ICT_SUCCESS and set the global symbol ict_errno
 * to indicate the error encountered.
 *
 * The caller should user function ict_get_error() to retrieve the
 * value stored in ict_errno. The call can user macro ICT_STR_ERROR
 * to return a descriptive text string for each value defined in
 * enum ict_status_t.
 *
 */
typedef enum {
	ICT_SUCCESS = 0,
	ICT_FAILURE,
	ICT_UNKNOWN,
	ICT_NO_MEM,
	ICT_SET_USER_FAIL,
	ICT_INVALID_ARG,
	ICT_INVALID_ID,
	ICT_CHOWN_FAIL,
	ICT_CHMOD_FAIL,
	ICT_CRT_PROF_FAIL,
	ICT_MOD_PW_FAIL,
	ICT_MOD_SW_FAIL,
	ICT_SET_HF_FAIL,
	ICT_SET_ROLE_FAIL,
	ICT_SET_LANG_FAIL,
	ICT_SET_KEYBRD_FAIL,
	ICT_SET_HOST_FAIL,
	ICT_SET_NODE_FAIL,
	ICT_INST_BOOT_FAIL,
	ICT_BE_CR_SNAP_FAIL,
	ICT_CR_SNAP_FAIL,
	ICT_NVLIST_ALC_FAIL,
	ICT_NVLIST_ADD_FAIL,
	ICT_TRANS_LOG_FAIL,
	ICT_MARK_RPOOL_FAIL
} ict_status_t;

extern	ict_status_t		ict_errno = ICT_SUCCESS;

/*
 * Return Code Text Strings
 */
#define	ICT_SUCCESS_STR		"ICT - Install Completion Task Succeeded"
#define	ICT_FAILURE_STR		"ICT - Install Completion Task Failed"
#define	ICT_UNKNOWN_STR		"ICT - Unknown error"
#define	ICT_NO_MEM_STR		"ICT - No memory available"
#define	ICT_SET_USER_FAIL_STR	"ICT - Failed to set user data"
#define	ICT_INVALID_ARG_STR	"ICT - Invalid Argument Specified"
#define	ICT_INVALID_ID_STR	"ICT - Invalid GID or UID"
#define	ICT_CHOWN_FAIL_STR	"ICT - Failed to set owner for user directory"
#define	ICT_CHMOD_FAIL_STR	"ICT - Failed to set owner for user directory"
#define	ICT_CRT_PROF_FAIL_STR	"ICT - Failed to create user profile"
#define	ICT_MOD_PW_FAIL_STR	"ICT - Failed to modify the password file"
#define	ICT_MOD_SW_FAIL_STR	"ICT - Failed to modify the shadow file"
#define	ICT_SET_HF_FAIL_STR	"ICT - Failed to set the hosts file"
#define	ICT_SET_ROLE_FAIL_STR	"ICT - Failed to set the user role"
#define	ICT_SET_LANG_FAIL_STR	"ICT - Failed to set the language locale"
#define	ICT_SET_KEYBRD_FAIL_STR	"ICT - Failed to set the keyboard layout"
#define	ICT_SET_HOST_FAIL_STR	"ICT - Failed to set host name in hosts file"
#define	ICT_SET_NODE_FAIL_STR	"ICT - Failed to set nodename in nodename file"
#define	ICT_INST_BOOT_FAIL_STR	"ICT - Failed to install the bootloader"
#define	ICT_BE_CR_SNAP_FAIL_STR	"ICT - Failed to create the BE snapshot"
#define	ICT_CR_SNAP_FAIL_STR	"ICT - Failed to create the ZFS snapshot"
#define	ICT_NVLIST_ALC_FAIL_STR	"ICT - Failed to alloc nvlist"
#define	ICT_NVLIST_ADD_FAIL_STR	"ICT - Failed to add element to nvlist"
#define	ICT_TRANS_LOG_FAIL_STR	"ICT - Failed to transfer the log files."
#define	ICT_MARK_RPOOL_FAIL_STR	"ICT - Failed to mark ZFS root pool as 'ready'"

#define	ICT_STR_ERROR(err) \
( \
	(err) == ICT_FAILURE ? ICT_FAILURE_STR : \
	(err) == ICT_NO_MEM ? ICT_NO_MEM_STR : \
	(err) == ICT_SET_USER_FAIL ? ICT_SET_USER_FAIL_STR : \
	(err) == ICT_INVALID_ARG ? ICT_INVALID_ARG_STR : \
	(err) == ICT_INVALID_ID ? ICT_INVALID_ID_STR : \
	(err) == ICT_CHOWN_FAIL ? ICT_CHOWN_FAIL_STR : \
	(err) == ICT_CHMOD_FAIL ? ICT_CHMOD_FAIL_STR : \
	(err) == ICT_CRT_PROF_FAIL ? ICT_CRT_PROF_FAIL_STR : \
	(err) == ICT_MOD_PW_FAIL ? ICT_MOD_PW_FAIL_STR : \
	(err) == ICT_MOD_SW_FAIL ? ICT_MOD_SW_FAIL_STR : \
	(err) == ICT_SET_HF_FAIL ? ICT_SET_HF_FAIL_STR : \
	(err) == ICT_SET_ROLE_FAIL ? ICT_SET_ROLE_FAIL_STR : \
	(err) == ICT_SET_LANG_FAIL ? ICT_SET_LANG_FAIL_STR : \
	(err) == ICT_SET_KEYBRD_FAIL ? ICT_SET_KEYBRD_FAIL_STR : \
	(err) == ICT_SET_HOST_FAIL ? ICT_SET_HOST_FAIL_STR : \
	(err) == ICT_SET_NODE_FAIL ? ICT_SET_NODE_FAIL_STR : \
	(err) == ICT_INST_BOOT_FAIL ? ICT_INST_BOOT_FAIL_STR : \
	(err) == ICT_BE_CR_SNAP_FAIL ? ICT_BE_CR_SNAP_FAIL_STR : \
	(err) == ICT_CR_SNAP_FAIL ? ICT_CR_SNAP_FAIL_STR : \
	(err) == ICT_NVLIST_ALC_FAIL ? ICT_NVLIST_ALC_FAIL_STR : \
	(err) == ICT_NVLIST_ADD_FAIL ? ICT_NVLIST_ADD_FAIL_STR : \
	(err) == ICT_TRANS_LOG_FAIL ? ICT_TRANS_LOG_FAIL_STR : \
	(err) == ICT_MARK_RPOOL_FAIL ? ICT_MARK_RPOOL_FAIL_STR : \
	(err) == ICT_SUCCESS ? ICT_SUCCESS_STR : ICT_UNKNOWN_STR)

/* libict API supporting function signatures */
char *ict_escape(char *source);

/* libict API function signatures */
ict_status_t ict_configure_user_directory(char *target, char *login);
ict_status_t ict_set_user_profile(char *target, char *login);
ict_status_t ict_set_user_role(char *target, char *login, int transfer_mode);
ict_status_t ict_set_lang_locale(char *target, char *localep,
    int transfer_mode);
ict_status_t ict_set_host_node_name(char *target, char *hostname);
ict_status_t ict_installboot(char *target, char *device);
ict_status_t ict_snapshot(char *pool, char *snapshot);
ict_status_t ict_transfer_logs(char *src, char *dst, int transfer_mode);
ict_status_t ict_mark_root_pool_ready(char *pool_name);

#ifdef __cplusplus
}
#endif

#endif	/* _ICT_API_H */
