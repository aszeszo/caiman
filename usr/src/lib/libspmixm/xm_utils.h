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




/*
 * Module:	xm_utils.h
 * Group:	libspmixm
 * Description:
 */

#ifndef	_XM_UTILS_H
#define	_XM_UTILS_H

#pragma ident	"@(#)xm_utils.h	1.3	07/11/12 SMI"

#include "spmixm_api.h"

/* for debugging */
#define	SPMI_XMLIB_NAME	"LIBSPMIXM"
#define	XM_DEBUG	\
	LOGSCR, (get_trace_level() > 0), SPMI_XMLIB_NAME, DEBUG_LOC
#define	XM_DEBUG_NOHD	\
	LOGSCR, (get_trace_level() > 0), NULL, DEBUG_LOC
#define	XM_DEBUG_L1	XM_DEBUG, LEVEL1
#define	XM_DEBUG_L1_NOHD	XM_DEBUG_NOHD, LEVEL1

/*
 * Help
 */
typedef struct {
	Widget toplevel;
	char *text;
} xm_HelpClientData;

/* xm_adminhelp.c */
extern void xm_HelpCB(Widget w, XtPointer client, XmAnyCallbackStruct *cbs);

#endif	/* _XM_UTILS_H */
