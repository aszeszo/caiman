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

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <gtk/gtk.h>
#include <gconf/gconf-client.h>
#include "window-graphics.h"

void
window_graphics_set_size_properties(GtkWidget *window)
{
	GConfClient *client = NULL;
	GError *error = NULL;
	gint width = 0;
	gint height = 0;

	client = gconf_client_get_default();
	if (!client) {
		g_warning("Failed to connect to gconf database.\n"
			"Using fallback values for window width and height");
		width = DEFWIDTH;
		height = DEFHEIGHT;
	} else {
		width = gconf_client_get_int(client,
			GCONF_WIDTH_KEY,
			&error);
		height = gconf_client_get_int(client,
			GCONF_HEIGHT_KEY,
			&error);
		if (width == 0 || height == 0 || error != NULL) {
			g_warning("Connected to gconf database but could not retrieve"
				"window geometry schema values.\n"
				"Using fallback values");
			width = DEFWIDTH;
			height = DEFHEIGHT;
		}
		gconf_client_clear_cache(client);
		g_object_unref(G_OBJECT(client));
	}

	gtk_window_set_default_size(GTK_WINDOW(window), width, height);
}

void
window_graphics_dialog_set_size_properties(GtkWidget *dialog)
{
	gtk_window_set_default_size(GTK_WINDOW(dialog),
						DEFDIALOGWIDTH, DEFDIALOGHEIGHT);
}

void
window_graphics_dialog_set_wm_properties(GtkWidget *dialog)
{
	GdkWindow *gdkwindow = NULL;

	if (!GTK_WIDGET_REALIZED(dialog)) {
		gtk_widget_realize(dialog);
	}

	gdkwindow = dialog->window;

	if (gdkwindow) {
		gdk_window_set_functions(gdkwindow,
				GDK_FUNC_MOVE|GDK_FUNC_RESIZE|GDK_FUNC_CLOSE);
	}
}

void
window_graphics_dialog_set_properties(GtkWidget *dialog)
{
	GdkWindow *gdkwindow = NULL;

	if (!GTK_WIDGET_REALIZED(dialog)) {
		window_graphics_dialog_set_size_properties(dialog);
		window_graphics_dialog_set_wm_properties(dialog);
	}

	gdkwindow = dialog->window;
	if (gdkwindow) {
		gdk_window_raise(gdkwindow);
	}
}
