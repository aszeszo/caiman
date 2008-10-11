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

/*
 * transfermod.h
 *
 * Slim Install Transfer Module API
 */

#ifndef __TRANSFERMOD__
#define	__TRANSFERMOD__

#ifdef __cplusplus
extern "C" {
#endif

#define	TM_SUCCESS	0
#define	TM_ATTR_IMAGE_INFO		"TM_ATTR_IMAGE_INFO"
#define	TM_ATTR_MECHANISM		"TM_ATTR_MECHANISM"
#define	TM_CPIO_ACTION			"TM_CPIO_ACTION"
#define	TM_IPS_ACTION			"TM_IPS_ACTION"
#define	TM_ATTR_TARGET_DIRECTORY	"TM_ATTR_TARGET_DIRECTORY"
#define	TM_CPIO_SRC_MNTPT		"TM_CPIO_SRC_MNTPT"
#define	TM_CPIO_DST_MNTPT		"TM_CPIO_DST_MNTPT"
#define	TM_CPIO_LIST_FILE		"TM_CPIO_LIST_FILE"
#define	TM_IPS_PKG_URL			"TM_IPS_PKG_URL"
#define	TM_IPS_PKG_AUTH			"TM_IPS_PKG_AUTH"
#define	TM_IPS_INIT_MNTPT		"TM_IPS_INIT_MNTPT"
#define	TM_IPS_PKGS			"TM_IPS_PKGS"
#define	TM_IPS_IMAGE_TYPE		"TM_IPS_IMAGE_TYPE"
#define	TM_IPS_IMAGE_FULL		"F"
#define	TM_IPS_IMAGE_PARTIAL		"P"
#define	TM_IPS_IMAGE_USER		"U"
#define TM_IPS_ALT_AUTH			"TM_IPS_ALT_AUTH"
#define	TM_IPS_ALT_URL			"TM_IPS_ALT_URL"
#define	TM_IPS_PREF_FLAG		"TM_IPS_PREF_FLAG"
#define	TM_IPS_PREFERRED_AUTH		"-P"
#define	TM_IPS_MIRROR_FLAG		"TM_IPS_MIRROR_FLAG"
#define	TM_IPS_MIRROR			"-m"
#define	TM_CPIO_ENTIRE_SKIP_FILE_LIST	"TM_CPIO_ENTIRE_SKIP_FILE_LIST"
#define	TM_CPIO_ARGS			"TM_CPIO_ARGS"

#define	TM_PERFORM_CPIO		0
#define	TM_PERFORM_IPS		1
#define	TM_CPIO_ENTIRE		0
#define	TM_CPIO_LIST		1
#define	TM_IPS_INIT		0
#define	TM_IPS_REPO_CONTENTS_VERIFY	1
#define	TM_IPS_RETRIEVE		2
#define	TM_IPS_REFRESH		3
#define	TM_IPS_SET_AUTH		4
#define	TM_IPS_UNSET_AUTH	5
#define	TM_IPS_PURGE_HIST	6
#define	TM_IPS_UNINSTALL	7

typedef enum {
	TM_E_SUCCESS = 0,		/* command succeeded */
	TM_E_INVALID_TRANSFER_TYPE_ATTR, /* transfer type attr invalid */
	TM_E_INVALID_CPIO_ACT_ATTR,	/* cpio transfer type attr invalid */
	TM_E_CPIO_ENTIRE_FAILED,	/* cpio of entire dir failed */
	TM_E_INVALID_CPIO_FILELIST_ATTR, /* cpio filelist attr invalid */
	TM_E_CPIO_LIST_FAILED,		/* cpio of file list failed */
	TM_E_INVALID_IPS_ACT_ATTR,	/* ips transfer type attr invalid */
	TM_E_INVALID_IPS_URL_ATTR,	/* ips url attribute invalid */
	TM_E_INVALID_IPS_AUTH_ATTR,	/* ips authority attribute invalid */
	TM_E_INVALID_IPS_MNTPT_ATTR,	/* ips init mountpoint invalid */
	TM_E_IPS_INIT_FAILED,		/* ips initialization failed */
	TM_E_IPS_REPO_CONTENTS_VERIFY_FAILED,	/* ips repo contents verification failed */
	TM_E_IPS_RETRIEVE_FAILED,	/* ips retrieval failed */
	TM_E_ABORT_FAILED,		/* abort failed */
	TM_E_REP_FAILED,		/* progress report failed */
	TM_E_IPS_PKG_MISSING,		/* ips package not found in repository */
	TM_E_IPS_REFRESH_FAILED,	/* ips refresh failed */
	TM_E_IPS_SET_AUTH_FAILED,	/* ips set-auth failed */
	TM_E_IPS_UNSET_AUTH_FAILED,	/* ips unset-auth failed */
	TM_E_PYTHON_ERROR		/* General Python error */
} tm_errno_t;

typedef void (*tm_callback_t)(const int percentage,
    const char *localized_GUI_message);

tm_errno_t TM_perform_transfer(nvlist_t *targs, tm_callback_t progress);
void TM_abort_transfer(void);
void TM_enable_debug(void);

#ifdef __cplusplus
}
#endif

#endif /* __TRANSFERMOD__ */
