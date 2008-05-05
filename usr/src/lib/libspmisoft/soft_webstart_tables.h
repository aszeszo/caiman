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


#ifndef _SOFT_WEBSTART_TABLES_H
#define	_SOFT_WEBSTART_TABLES_H


#ifdef __cplusplus
extern "C" {
#endif


/* common path names */
/* directories */

#define	OS_DIR		"/usr/lib/install/data/os"
#define	MEDIA_KIT_DIR	"/tmp/root/install/data/media_kits"

#define	PD_DIR		"/tmp/root/install/data/media_kits/products/pd_files"
#define	PD_NAME_DIR	"/tmp/root/install/data/media_kits/products/pd_files/names"
#define	PD_HELP_DIR	"/tmp/root/install/data/media_kits/products/pd_files/help"
#define	CDS_DIR		"/tmp/root/install/data/media_kits/products/cds"
#define	CD_NAME_DIR	"/tmp/root/install/data/media_kits/products/cds/names"
#define	CD_HELP_DIR	"/tmp/root/install/data/media_kits/products/cds/help"
#define	HELP_DIR	"/help"
#define	LAUNCH_DIR	"/a/var/sadm/launcher"


#define	METACLUSTERS	"/meta_clusters"
#define	METALOCALE	"/meta_clusters/locale"
#define	OS_BASE_DIR	"/usr/lib/install/data/os"

/* files */
#define	OSCORE1		"os.core.1"
#define	SLASHOSCORE1	"/os.core.1"
#define	OSTOC		"/usr/lib/install/data/os/os.toc"
#define	MEDIA_KIT_TOC	"/media_kit.toc"
#define	MEDIA_KITS_TOC	"/media_kits.toc"
#define	PRODUCT_DOT_TOC	"/product.toc"
#define	CD_DOT_INFO	"/cd.info"
#define	VOL_INF		"/.volume.inf"
#define	DISPATCH_TABLE	"/a/var/sadm/launcher/dispatch_table"


#define	DEFAULT_OFF	0
#define	DEFAULT_ON	1

Media_Kit_Info *mkit;

#ifdef __cplusplus
}
#endif

#endif /* _SOFT_WEBSTART_TABLES_H */
