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


#ifndef	_APP_UTILS_H
#define	_APP_UTILS_H


/*
 * Module:	app_utils.h
 * Group:	libspmiapp
 * Description:
 */

#include "spmiapp_api.h"
#include "app_utils.h"

/*
 * macros usefule for debugging
 */
#define	SPMI_APPLIB_NAME	"LIBSPMIAPP"
#define	APP_DEBUG	\
	LOGSCR, (get_trace_level() > 0), SPMI_APPLIB_NAME, DEBUG_LOC
#define	APP_DEBUG_NOHD	\
	LOGSCR, (get_trace_level() > 0), NULL, DEBUG_LOC
#define	APP_DEBUG_L1		APP_DEBUG, LEVEL1
#define	APP_DEBUG_L1_NOHD	APP_DEBUG_NOHD, LEVEL1

#endif /* _APP_UTILS_H */
