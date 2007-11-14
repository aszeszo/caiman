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


#ifndef _SOFT_LOCALE_H
#define	_SOFT_LOCALE_H

#pragma ident	"@(#)soft_locale.h	1.3	07/11/09 SMI"

#ifdef __cplusplus
extern "C" {
#endif


/* path names */
#define	NLSPATH			"/usr/lib/locale"

/* full path files */
#define	LCTTAB			"/usr/lib/locale/lcttab"
#define	INIT_FILE		"/etc/default/init"
#define	TMP_DEFSYSLOC		"/tmp/.defSysLoc"
#define	TMP_INITDEFSYSLOC	"/tmp/.init.defSysLoc"
#define	LOCALES_INSTALLED	"/var/sadm/system/data/locales_installed"

/* filenames */
#define	LOCALE_MAP_FILE		"locale_map"
#define	GEO_MAP_FILE		"geo_map"
#define	LOCALE_DESC_FILE	"locale_description"


#ifdef __cplusplus
}
#endif

#endif /* _SOFT_LOCALE_H */
