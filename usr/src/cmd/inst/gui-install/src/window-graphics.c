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
#pragma ident	"@(#)window-graphics.c	1.3	07/10/23 SMI"

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <gtk/gtk.h>
#include <gconf/gconf-client.h>
#include "window-graphics.h"
#include "pixbufs.h"

/* Forward declaration */
static GdkPixmap *
window_graphics_create_bg_graphic(GtkWidget *window);
/*
 * Set the background graphic of a GtkWindow to the Sun Curve with a
 * white background.
 * Scales the sun curve pixbuv vertically to match the window height and
 * composites it onto a white coloured background pixbuf matching the
 * window's dimensions.
 * Suitable only for non user resizeable windows only since the scaling and
 * compositing is expensive.
 */

gint scaledcurvewidth = 0;

gint
window_graphics_set_bg_graphic(GtkWidget *window)
{
	static GdkColor  backcolour;
	static GdkPixmap *pixmap = NULL;
	GtkStyle *style, *newstyle;

	gtk_widget_realize(window);
	gdk_color_parse(WHITE_COLOR, &backcolour);

	gtk_widget_modify_bg(window, GTK_STATE_NORMAL, &backcolour);
#ifdef DRAW_S_CURVE
	if (!pixmap) {
		gdk_color_parse(WHITE_COLOR, &backcolour);
		pixmap = window_graphics_create_bg_graphic(window);
		g_object_ref(pixmap);
	}

	newstyle = g_new0(GtkStyle, 1);
	style = gtk_widget_get_style(window);
	newstyle = gtk_style_copy(style);
	newstyle->bg_pixmap[GTK_STATE_NORMAL] = pixmap;
	gtk_widget_set_style(window, newstyle);
#endif
	return (scaledcurvewidth);
}

static GdkPixmap *
window_graphics_create_bg_graphic(GtkWidget *window)
{

	GdkPixbuf *suncurvepixbuf;
	GdkPixbuf *basepixbuf;
	GdkPixmap *basepixmap;
	GdkPixmap *basemask;
	GtkStyle *style;
	gint winwidth, winheight;
	double suncurve_y_scale;
	int suncurvewidth, suncurveheight;

	suncurvepixbuf = gdk_pixbuf_new_from_inline(-1, suncurve_pixbuf, FALSE,
							NULL);
	suncurvewidth = gdk_pixbuf_get_width(suncurvepixbuf);
	suncurveheight = gdk_pixbuf_get_height(suncurvepixbuf);
	gtk_window_get_default_size(GTK_WINDOW(window), &winwidth, &winheight);

	basepixbuf = gdk_pixbuf_new(GDK_COLORSPACE_RGB, TRUE, 8, winwidth,
							winheight);
	if (basepixbuf == NULL)
		return (NULL);
	suncurve_y_scale = (double)winheight / (double)suncurveheight;
	scaledcurvewidth = (gint)((double)suncurve_y_scale *
						(double)suncurvewidth);

	gdk_pixbuf_render_pixmap_and_mask(basepixbuf, &basepixmap, &basemask, 255);

	style = gtk_widget_get_style(window);
	gdk_draw_rectangle(GDK_DRAWABLE(basepixmap),
		style->bg_gc[GTK_STATE_NORMAL],
		TRUE,
		0, 0,
		winwidth, winheight);

	gdk_pixbuf_get_from_drawable(basepixbuf,
		GDK_DRAWABLE(basepixmap),
		NULL,
		0, 0,
		0, 0,
		winwidth,
		winheight);

	gdk_pixbuf_composite(suncurvepixbuf,
		basepixbuf,
		0, 0,
		scaledcurvewidth, winheight,
		0, 0,
		/* Scale horizontally and vertically equally */
		suncurve_y_scale, suncurve_y_scale,
		GDK_INTERP_NEAREST,
		255);
	gdk_pixbuf_render_pixmap_and_mask(basepixbuf, &basepixmap, &basemask, 255);

	g_object_unref(G_OBJECT(basepixbuf));
	g_object_unref(G_OBJECT(basemask));
	return (basepixmap);
}

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
	gtk_widget_set_size_request(window, width, height);
}

void
window_graphics_set_wm_properties(GtkWidget *window)
{
	GdkWindow *gdkwindow = window->window;
	gdk_window_set_decorations(gdkwindow, GDK_DECOR_BORDER|GDK_DECOR_TITLE);
	gdk_window_set_functions(gdkwindow, GDK_FUNC_MOVE|GDK_FUNC_MINIMIZE|GDK_FUNC_CLOSE);
	gtk_window_set_resizable(GTK_WINDOW(window), FALSE);
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
