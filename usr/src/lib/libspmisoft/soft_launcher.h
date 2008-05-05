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


#ifndef _SOFT_LAUNCHER_H
#define	_SOFT_LAUNCHER_H



#ifdef __cplusplus
extern "C" {
#endif


#define	SWAPPART		"/.swappart"
#define	CDROOT			"/.cdroot"
#define	EXTRADVDSWAP		"/tmp/.extraDVDSwap"
#define	DOTINSTALLDIR		"/cdrom/.install"
#define	JAVALOC			"/usr/java/bin/java"
#define	NETCDBOOT		"/tmp/.netcdboot"
#define	TEXTINSTALL		"/tmp/.text_install"
#define	LOCSIZE			128

#define	PRODUCT_TABLE		"/tmp/product_table"
#define	VAR_SADM_WEBSTART	"/var/sadm/launcher"
#define	VAR_SADM_DATA		"/a/var/sadm/system/data"
#define	DOTVIRTUALPKGS		".virtualpkgs"
#define	DOTVIRTUALPKGSLANG	".virtualpkgslang"
#define	DOTVIRTUALPKGTOCLANG	".virtual_packagetoc_lang"
#define	LAUNCH_DIR		"/a/var/sadm/launcher"
#define	DISPATCH_TABLE		"/a/var/sadm/launcher/dispatch_table"
#define	POST_FILE		"/a/var/sadm/launcher/post_table"
#define	ITAGS_FILE		"/a/var/sadm/launcher/.itags"
#define	OSDIR_FILE		"/a/var/sadm/launcher/.osDir"
#define	DOT_REBOOT_DIR		"/a/var/sadm/launcher/.autoreboot"
#define	DOT_NOEJECT_DIR		"/a/var/sadm/launcher/.noeject"
#define	DOT_BOOTDISC_DIR	"/a/var/sadm/launcher/.bootDisc"

#define	VCDN_INFO		"/sol.info."
#define	LANG_INFO		"/lang.info."


#ifdef __cplusplus
}
#endif

#endif /* _SOFT_LAUNCHER_H */
