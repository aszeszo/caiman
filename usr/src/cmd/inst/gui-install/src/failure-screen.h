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

#ifndef __FAILURE_SCREEN_H
#define	__FAILURE_SCREEN_H

#pragma ident	"@(#)failure-screen.h	1.2	07/08/15 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glade/glade.h>

#define	INSTALLLOGNODE "textviewdialog"

typedef struct _FailureWindowXML {
	GladeXML *installlogxml;

	GtkWidget *failurewindowtable;
	GtkWidget *failureinfolabel;
	GtkWidget *failuredetaillabel;
	GtkWidget *logbuttonlabel;

	GtkWidget *installlogdialog;
	GtkWidget *installlogclosebutton;
	GtkWidget *installlogtextview;
} FailureWindowXML;

void		failure_window_init(void);

void		failure_screen_load_widgets(void);

void		failure_screen_set_contents(void);

#ifdef __cplusplus
}
#endif

#endif /* __FAILURE_SCREEN_H */
