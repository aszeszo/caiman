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

#ifndef __CONFIRMATION_SCREEN_H
#define	__CONFIRMATION_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glade/glade.h>

#define	LICENSEAGREEMENTNODE "licenseagreementdialog"

typedef struct _ConfirmationWindowXML {
	GladeXML *licenseagreementxml;

	GtkWidget *confirmationtoplevel;
	GtkWidget *infolabel;
	GtkWidget *confirmmainvbox;
	GtkWidget *confirmscrolledwindow;
	GtkWidget *confirmviewport;
	GtkWidget *confirmdetailvbox;
	GtkWidget *diskvbox;
	GtkWidget *softwarevbox;
	GtkWidget *timezonevbox;
	GtkWidget *languagesvbox;
	GtkWidget *accountvbox;

	GtkWidget *licensecheckbutton;
	GtkWidget *licenseagreementdialog;
	GtkWidget *licenseagreementlinkbutton;
	GtkWidget *licenseagreementclosebutton;
	GtkWidget *licenseagreementtextview;
} ConfirmationWindowXML;

void		confirmation_window_init(void);

void		confirmation_load_widgets(void);

void		confirmation_screen_set_contents(void);

gboolean	confirmation_agree_license(void);

gboolean	confirmation_check_label_button_release(GtkWidget *widget,
				GdkEvent *event,
				gpointer data);

void		confirmation_screen_set_default_focus(void);

#ifdef __cplusplus
}
#endif

#endif /* __CONFIRMATION_SCREEN_H */
