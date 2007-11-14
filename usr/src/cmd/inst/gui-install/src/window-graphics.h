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

#ifndef __WINDOW_GRAPHICS_H
#define	__WINDOW_GRAPHICS_H

#pragma ident	"@(#)window-graphics.h	1.1	07/08/03 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <gtk/gtk.h>

/*
 * Default window width and height values if the localisation
 * Doesn't provide values
 */
#define	GCONF_WIDTH_KEY		"/apps/solaris-gui-install/windowwidth"
#define	GCONF_HEIGHT_KEY	"/apps/solaris-gui-install/windowheight"

#define	DEFWIDTH 855
#define	DEFHEIGHT 641

#define	DEFDIALOGWIDTH 750
#define	DEFDIALOGHEIGHT 450

#define	WHITE_COLOR "white"
#define	WHITE_GDK_COLOR 65535

/*
 * Returns: Horizontal width in pixels of scaled image
 */
gint		window_graphics_set_bg_graphic(GtkWidget *window);

void		window_graphics_set_size_properties(GtkWidget *window);

void		window_graphics_set_wm_properties(GtkWidget *window);

void		window_graphics_dialog_set_size_properties(GtkWidget *dialog);

void		window_graphics_dialog_set_wm_properties(GtkWidget *dialog);

void		window_graphics_dialog_set_properties(GtkWidget *dialog);

#ifdef __cplusplus
}
#endif

#endif /* __WINDOW_GRAPHICS_H */
