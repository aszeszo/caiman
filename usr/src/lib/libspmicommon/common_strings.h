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


#ifndef _COMMON_STRINGS_H
#define	_COMMON_STRINGS_H

#pragma ident	"@(#)common_strings.h	1.3	07/11/12 SMI"

/*
 * Module:	common_strings.h
 * Group:	libspmicommon
 * Description:	This header contains strings used in libspmicommon
 *		library modules.
 */

#include <libintl.h>

/* constants */

#ifndef	TEXT_DOMAIN
#define	TEXT_DOMAIN	"SUNW_INSTALL_LIBCOMMON"
#endif

#ifndef ILIBSTR
#define	ILIBSTR(x)	dgettext(TEXT_DOMAIN, x)
#endif

/* message strings */

#define	MSG_LEADER_ERROR	ILIBSTR("ERROR")
#define	MSG_LEADER_WARNING	ILIBSTR("WARNING")
#define	MSG_COPY_FAILED		ILIBSTR(\
	"Could not copy file (%s) to (%s)")
#define	CREATING_MNTPNT		ILIBSTR(\
	"Creating mount point (%s)")
#define	CREATE_MNTPNT_FAILED	ILIBSTR(\
	"Could not create mount point (%s)")
#define	SYNC_WRITE_SET_FAILED	ILIBSTR(\
	"Could not access %s to set synchronous writes")

/* common_scriptwrite.c */
#define	MSG1_BAD_TOKEN		ILIBSTR(\
	"Bad Token: %s\n")


#endif /* _COMMON_STRINGS_H */
