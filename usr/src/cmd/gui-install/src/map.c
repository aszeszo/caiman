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

#include <math.h>
#include <string.h>
#include <libzoneinfo.h>
#include <glib-object.h>
#include <gdk-pixbuf/gdk-pixbuf.h>
#include "pixbufs.h"
#include "map.h"

#define ZOOM_IN_SCALE 1.3

enum {
	TIMEZONE_ADDED,
	ALL_TIMEZONES_ADDED,
	LAST_SIGNAL
};

struct _MapPrivate
{
	/* orignal pixbuf */
	GdkPixbuf *pixbuf;
	/* scaled one */
	GdkPixbuf *scaled_pixbuf;

	GdkPixbuf *city_pixbuf[POINT_STATE][ZOOM_STATE];
	GdkPixbuf *hand;
	GdkPixbuf *magnifier;

	GdkCursor *hand_cursor;
	GdkCursor *magnifier_cursor;
	/*
	 * used to remember the
	 * orignal (x,y) when dragging
	 * the map
	 */
	gdouble x, y;

	/*
	 * the leftup corner of scaled pixbuf
	 * in the map when the map is bigger
	 * than the widget window
	 */
	gint xoffset;
	gint yoffset;

	gdouble scale;
	gdouble zoom_out_scale;

	ZoomState zoom;

	/* loaded timezones */
	GPtrArray *timezones;
	continent_item *continents;
	int nctnt;

	/* seleted timezone */
	timezone_item *selected_zone;
	/* hovered timzone */
	timezone_item *hovered_zone;
};

static GObjectClass *parent_class = NULL;
static guint signals [LAST_SIGNAL] = { 0 };

G_DEFINE_TYPE(Map, map, GTK_TYPE_DRAWING_AREA)

static void	map_class_init(MapClass *klass);
static void	map_init(Map *map);
static void	map_destroy(GtkObject *object);
static void map_finalize(GObject *object);
static void	map_size_request(GtkWidget *widget,
				GtkRequisition *requisition);
static gint	map_expose(GtkWidget *widget,
				GdkEventExpose *event);
static void scale_map(Map *map);
static void update_rectangle(Map *map, gboolean update_timezone);
static void zoom(Map *map, gdouble scale);
static void	map_timezone_cleanup(Map *map);

static void
map_class_init(MapClass *klass)
{
	GtkObjectClass *object_class;
	GtkWidgetClass *widget_class;

	parent_class = gtk_type_class(GTK_TYPE_WIDGET);

	object_class = (GtkObjectClass *)klass;
	object_class->destroy = map_destroy;

	widget_class = (GtkWidgetClass *)klass;
	widget_class->expose_event = map_expose;
	widget_class->size_request = map_size_request;

	signals[TIMEZONE_ADDED] =
		g_signal_new ("timezone-added",
				G_OBJECT_CLASS_TYPE (object_class),
				G_SIGNAL_RUN_LAST,
				G_STRUCT_OFFSET (MapClass, timezone_added),
				NULL, NULL,
				g_cclosure_marshal_VOID__POINTER,
				G_TYPE_NONE, 1,
				G_TYPE_POINTER);
	signals[ALL_TIMEZONES_ADDED] =
		g_signal_new ("all-timezones-added",
				G_OBJECT_CLASS_TYPE (object_class),
				G_SIGNAL_RUN_LAST,
				G_STRUCT_OFFSET (MapClass, all_timezones_added),
				NULL, NULL,
				g_cclosure_marshal_VOID__VOID,
				G_TYPE_NONE, 0);

}

static void
map_init(Map *map)
{
	map->priv = g_new0(MapPrivate, 1);
}

static void
map_destroy(GtkObject *object)
{
	g_return_if_fail(object != NULL);
	g_return_if_fail(IS_MAP(object));

	if (GTK_OBJECT_CLASS(parent_class)->destroy)
		(*GTK_OBJECT_CLASS(parent_class)->destroy)(object);
}

static void
map_finalize(GObject *object)
{
	Map *map;
	MapPrivate *priv;

	g_return_if_fail(object != NULL);
	g_return_if_fail(IS_MAP(object));

	map = MAP(object);
	priv = map->priv;

	if (priv) {
		if (priv->pixbuf) {
			gdk_pixbuf_unref(priv->pixbuf);
			priv->pixbuf = NULL;
		}

		if (priv->hand) {
			gdk_pixbuf_unref(priv->hand);
			priv->hand = NULL;
		}

		if (priv->hand_cursor) {
			gdk_cursor_unref(priv->hand_cursor);
			priv->hand_cursor = NULL;
		}

		if (priv->magnifier) {
			gdk_pixbuf_unref(priv->magnifier);
			priv->magnifier = NULL;
		}

		if (priv->magnifier_cursor) {
			gdk_cursor_unref(priv->magnifier_cursor);
			priv->magnifier_cursor = NULL;
		}

		for (gint i = 0; i < POINT_STATE; i++) {
			for (gint j = 0; i < ZOOM_STATE; j++) {
				gdk_pixbuf_unref(priv->city_pixbuf[i][j]);
				priv->city_pixbuf[i][j] = NULL;
			}
		}

		if (priv->scaled_pixbuf) {
			gdk_pixbuf_unref(priv->scaled_pixbuf);
			priv->scaled_pixbuf = NULL;
		}

		if (priv->continents) {
			map_timezone_cleanup(map);
			priv->continents = NULL;
			priv->nctnt = 0;
		}
		if (priv->timezones) {
			g_ptr_array_free(priv->timezones, FALSE);
		}
	}
	if (G_OBJECT_CLASS(parent_class)->finalize)
		G_OBJECT_CLASS(parent_class)->finalize(object);
}

static void
map_size_request(GtkWidget *widget,
				GtkRequisition *requisition)
{
	MapPrivate *priv;

	g_return_if_fail(widget != NULL);
	g_return_if_fail(IS_MAP(widget));

	priv = MAP(widget)->priv;
	if (GTK_WIDGET_VISIBLE(widget)) {
		requisition->width =
			gdk_pixbuf_get_width(priv->pixbuf) * 0.64; 
		requisition->height =
			gdk_pixbuf_get_height(priv->pixbuf) * 0.64;
	}
}

static void
draw_point(Map *map, gint x, gint y, GdkPixbuf *pixbuf)
{
	GtkWidget *widget;

	g_return_if_fail(IS_MAP(map));

	widget = GTK_WIDGET(map);

	gdk_draw_pixbuf(widget->window,
			widget->style->black_gc,
			pixbuf,
			0, 0,
			x - gdk_pixbuf_get_width(pixbuf) / 2,
			y - gdk_pixbuf_get_height(pixbuf) / 2,
			gdk_pixbuf_get_width(pixbuf),
			gdk_pixbuf_get_height(pixbuf),
			GDK_RGB_DITHER_NORMAL,
			0, 0);
}

static void
map_draw_timezones(Map *map)
{
	MapPrivate *priv;
	timezone_item *zone;
	gint i;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	for (i = 0; i < priv->timezones->len; i++) {
		zone = g_ptr_array_index(priv->timezones, i);
		map_draw_timezone(map, zone);
	}
	if (priv->hovered_zone)
		map_draw_timezone(map, priv->hovered_zone);
	if (priv->selected_zone)
		map_draw_timezone(map, priv->selected_zone);
}

static void
do_redraw(Map *map)
{
	MapPrivate *priv;
	GtkWidget *widget;
	GtkAllocation *allocation;
	gint x, y;
	gint width, height;
	gint rwidth, rheight;
	gint rxoff, ryoff;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (!priv->scaled_pixbuf)
		return;

	widget = GTK_WIDGET(map);
	allocation = &widget->allocation;
	rwidth = width =
		gdk_pixbuf_get_width(priv->scaled_pixbuf);
	rxoff = priv->xoffset;
	if (width < allocation->width) {
		x = (allocation->width - width) / 2;
	} else {
		x = 0;
		width = allocation->width;
	}

	rheight = height =
		gdk_pixbuf_get_height(priv->scaled_pixbuf);
	ryoff = priv->yoffset;
	if (height < allocation->height) {
		y = (allocation->height - height) / 2;
	} else {
		y = 0;
		height = allocation->height;
	}

	gdk_window_clear_area(widget->window,
			0, 0,
			widget->allocation.width,
			widget->allocation.height);
	gdk_draw_pixbuf(widget->window,
			widget->style->black_gc,
			priv->scaled_pixbuf,
			rxoff, ryoff,
			x, y,
			(rwidth - rxoff), (rheight - ryoff),
			GDK_RGB_DITHER_NORMAL,
			0, 0);
	if (rxoff + width > rwidth) {
		gdk_draw_pixbuf(widget->window,
				widget->style->black_gc,
				priv->scaled_pixbuf,
				0, ryoff,
				x + (rwidth - rxoff), y,
				(width + rxoff - rwidth),
				(rheight - ryoff),
				GDK_RGB_DITHER_NORMAL,
				0, 0);
	}
	if (ryoff + height > rheight) {
		gdk_draw_pixbuf(widget->window,
				widget->style->black_gc,
				priv->scaled_pixbuf,
				rxoff, 0,
				x, (y + (rheight - ryoff)),
				(rwidth - rxoff),
				(height + ryoff - rheight),
				GDK_RGB_DITHER_NORMAL,
				0, 0);
	}
	if (rxoff + width > rwidth &&
			ryoff + height > rheight) {
		gdk_draw_pixbuf(widget->window,
				widget->style->black_gc,
				priv->scaled_pixbuf,
				0, 0,
				(x + (rwidth - rxoff)),
				(y + (rheight - ryoff)),
				(width + rxoff - rwidth),
				(height + ryoff - rheight),
				GDK_RGB_DITHER_NORMAL,
				0, 0);
	}
}

static void
scale_pixbuf(Map *map, gdouble scale)
{
	MapPrivate *priv;
	gint width, height;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (priv->scale < scale)
		priv->zoom = ZOOM_IN; 
	else if (priv->scale > scale)
		priv->zoom = ZOOM_OUT;
	priv->scale = scale;

	width = gdk_pixbuf_get_width(priv->pixbuf) * priv->scale;
	height = gdk_pixbuf_get_height(priv->pixbuf) * priv->scale;
	if (priv->scaled_pixbuf)
		gdk_pixbuf_unref(priv->scaled_pixbuf);
	priv->scaled_pixbuf =
		gdk_pixbuf_new(GDK_COLORSPACE_RGB, FALSE, 8,
				width, height);
	gdk_pixbuf_scale(priv->pixbuf,
			priv->scaled_pixbuf,
			0, 0,
			width, height,
			0, 0,
			priv->scale, priv->scale,
			GDK_INTERP_BILINEAR);
}

static void
scale_map(Map *map)
{
	MapPrivate *priv;
	gdouble scale;
	GtkWidget *parent;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (priv->zoom == ZOOM_IN) {
		scale_pixbuf(map, ZOOM_IN_SCALE);
	} else if (priv->zoom == ZOOM_OUT) {
		parent = gtk_widget_get_parent(GTK_WIDGET(map));
		if (parent && priv->zoom_out_scale == 0.0) {
			gdouble scale;

			scale = (gdouble) parent->allocation.width /
				gdk_pixbuf_get_width(map->priv->pixbuf);
			if (scale > ZOOM_IN_SCALE)
				priv->zoom_out_scale = ZOOM_IN_SCALE;
			else
				priv->zoom_out_scale = scale;
		}

		scale_pixbuf(map, priv->zoom_out_scale);
	}
}

static void
update_rectangle(Map *map, gboolean update_timezone)
{
	scale_map(map);
	do_redraw(map);
	if (update_timezone) {
		map_draw_timezones(map);
	}
}

static gboolean
map_expose(GtkWidget *widget, GdkEventExpose *event)
{
	MapPrivate *priv;

	g_return_val_if_fail(widget != NULL, FALSE);
	g_return_val_if_fail(IS_MAP(widget), FALSE);
	g_return_val_if_fail(event != NULL, FALSE);

	if (event->count > 0)
		return FALSE;

	priv = MAP(widget)->priv;

	if (priv->scaled_pixbuf &&
			(gdk_pixbuf_get_height(priv->scaled_pixbuf) <
			widget->allocation.height))
		priv->yoffset = 0;
	update_rectangle(MAP(widget), TRUE);

	return TRUE;
}

GtkWidget*
map_new(void)
{
	GtkWidget *map;
	MapPrivate *priv;
	GdkPixbuf *pixbuf;
	GdkPixbuf *city_normal_l;
	GdkPixbuf *city_mouseover_l;
	GdkPixbuf *city_selected_l;
	GdkPixbuf *city_normal_s;
	GdkPixbuf *city_mouseover_s;
	GdkPixbuf *city_selected_s;
	GdkPixbuf *hand;
	GdkPixbuf *magnifier;
	GtkSettings *settings;
	guint event_mask;
	gdouble scale;

	pixbuf =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "worldmap.png", NULL);
	hand =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "hand.png", NULL);
	magnifier =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "magnifier.png", NULL);
	city_normal_l =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_normal_l.png", NULL);
	city_mouseover_l =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_mouseover_l.png", NULL);
	city_selected_l =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_selected_l.png", NULL);
	city_normal_s =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_normal_s.png", NULL);
	city_mouseover_s =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_mouseover_s.png", NULL);
	city_selected_s =
		gdk_pixbuf_new_from_file(PIXMAPDIR "/" "city_selected_s.png", NULL);
	if (!pixbuf || !hand || !magnifier ||
			!city_normal_l || !city_mouseover_l || !city_selected_l ||
			!city_normal_s || !city_mouseover_s || !city_selected_s) {
		gdk_pixbuf_unref(pixbuf);
		gdk_pixbuf_unref(hand);
		gdk_pixbuf_unref(city_normal_l);
		gdk_pixbuf_unref(city_mouseover_l);
		gdk_pixbuf_unref(city_selected_l);
		gdk_pixbuf_unref(city_normal_s);
		gdk_pixbuf_unref(city_mouseover_s);
		gdk_pixbuf_unref(city_selected_s);
		return NULL;
	}

	map = g_object_new(map_get_type(), NULL);
	priv = MAP(map)->priv;
	priv->zoom = ZOOM_OUT;
	priv->scale = ZOOM_IN_SCALE;
	priv->zoom_out_scale = 0.0;
	priv->pixbuf = pixbuf;
	priv->hand = hand;
	priv->magnifier = magnifier;
	priv->city_pixbuf[POINT_NORMAL][ZOOM_IN] = city_normal_l;
	priv->city_pixbuf[POINT_HOVERED][ZOOM_IN] = city_mouseover_l;
	priv->city_pixbuf[POINT_SELECTED][ZOOM_IN] = city_selected_l;
	priv->city_pixbuf[POINT_NORMAL][ZOOM_OUT] = city_normal_s;
	priv->city_pixbuf[POINT_HOVERED][ZOOM_OUT] = city_mouseover_s;
	priv->city_pixbuf[POINT_SELECTED][ZOOM_OUT] = city_selected_s;
	priv->timezones = g_ptr_array_new();
	priv->hand_cursor =
		gdk_cursor_new_from_pixbuf(gdk_display_get_default(),
				priv->hand, 0, 0);
	priv->magnifier_cursor =
		gdk_cursor_new_from_pixbuf(gdk_display_get_default(),
				priv->magnifier, 0, 0);

	event_mask = gtk_widget_get_events(map);
	gtk_widget_set_events(map,
			event_mask | GDK_BUTTON_PRESS_MASK | GDK_BUTTON_RELEASE_MASK);

	g_object_set (G_OBJECT(map), "has-tooltip", TRUE, NULL);
	settings = gtk_widget_get_settings (map);
	g_object_set (settings, "gtk-tooltip-timeout", 50, NULL);


	return map;
}

static void
zoom(Map *map, gdouble scale)
{
	MapPrivate *priv;
	GtkWidget *widget;

	g_return_if_fail(IS_MAP(map));

	widget = GTK_WIDGET(map);
	priv = map->priv;

	scale_pixbuf(map, scale);

	map_draw_timezones(map);
	gdk_window_invalidate_rect(widget->window, &widget->allocation, FALSE);
}

void
map_zoom(Map *map, gdouble scale)
{
	g_return_if_fail(IS_MAP(map));

	zoom(map, scale);
}

void
map_zoom_in(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	map_set_hand_cursor(map);
	zoom(map, ZOOM_IN_SCALE);
}

void
map_zoom_out(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	map_set_magnifier_cursor(map);
	zoom(map, map->priv->zoom_out_scale);
}

void
map_geography_to_geometry(Map *map,
					gdouble longitude, gdouble latitude,
					gint *x, gint *y)
{
	MapPrivate *priv;
	gint width, height;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	width = gdk_pixbuf_get_width(priv->pixbuf);
	height = gdk_pixbuf_get_height(priv->pixbuf);
	*x = width / 2.0 * (1 + longitude / 180.0);
	*y = height / 2.0 * (1 - latitude / 90.0);
}

void
map_draw_timezone(Map *map, timezone_item *zone)
{
	MapPrivate *priv;
	gint x, y;
	gint origx, origy;
	gint width, height;

	g_return_if_fail(IS_MAP(map));
	priv = map->priv;
	if (!priv->scaled_pixbuf)
		return;

	x = zone->x * priv->scale;
	y = zone->y * priv->scale;
	width = gdk_pixbuf_get_width(priv->scaled_pixbuf);
	height = gdk_pixbuf_get_height(priv->scaled_pixbuf);

	/* handle the points at the border */
	if (x - 3 < 0)
		x += 3;
	if (x + 3 > width)
		x -= 3;
	if (y - 3 < 0)
		y += 3;
	if (y + 3 > height)
		y -= 3;

	if (GTK_WIDGET(map)->allocation.width > width)
		origx = (GTK_WIDGET(map)->allocation.width - width) / 2;
	else
		origx = 0;
	if (GTK_WIDGET(map)->allocation.height > height)
		origy = (GTK_WIDGET(map)->allocation.height - height) /2;
	else
		origy = 0;
	x = (x - priv->xoffset + width) % width + origx;
	y = (y - priv->yoffset + height) % height + origy;

	draw_point(map, x, y, priv->city_pixbuf[zone->state][priv->zoom]);
}

void
map_set_timezone_selected(Map *map, timezone_item *zone)
{
	MapPrivate *priv;

	g_return_if_fail(IS_MAP(map));

	/*
	 * filter the fake timezone
	 * we created for
	 * "- Select -" label
	 */
	if (!zone->timezone)
		return;

	priv = map->priv;
	if (priv->selected_zone) {
		priv->selected_zone->state = POINT_NORMAL;
	}
	zone->state = POINT_SELECTED;
	priv->selected_zone = zone;
}

void
map_set_timezone_hovered(Map *map, timezone_item *zone)
{
	MapPrivate *priv;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (zone->state != POINT_SELECTED) {
		if (priv->hovered_zone &&
			priv->hovered_zone->state != POINT_SELECTED) {
			priv->hovered_zone->state = POINT_NORMAL;
		}
		zone->state = POINT_HOVERED;
		priv->hovered_zone = zone;
	}
}

void
map_unset_hoverd_timezone(Map *map)
{
	MapPrivate *priv;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (priv->hovered_zone &&
			priv->hovered_zone->state == POINT_HOVERED) {
		priv->hovered_zone->state = POINT_NORMAL;
	}
	priv->hovered_zone = NULL;
}

static void
map_timezone_cleanup(Map *map)
{
	continent_item *continents = NULL;
	gint nctnt;
	gint i, j;

	g_return_if_fail(IS_MAP(map));

	continents = map->priv->continents;
	nctnt = map->priv->nctnt;
	for (i = 1; i < nctnt; i++) {
		for (j = 1; j < continents[i].nctry; j++) {
			free_timezones(continents[i].ctry[j].tz[1].timezone);
			gtk_tree_row_reference_free (continents[i].ctry[j].tz[1].ref);
			g_free(continents[i].ctry[j].tz);
		}
		free_tz_countries(continents[i].ctry[1].country);
		gtk_tree_row_reference_free (continents[i].ctry[j].ref);
		g_free(continents[i].ctry);
	}
	free_tz_continents(continents[1].continent);
	gtk_tree_row_reference_free (continents[i].ref);
	g_free(continents);

	map->priv->continents = NULL;
	map->priv->nctnt = 0;
}

static gdouble
parse_longitude(struct tz_timezone *tzs)
{
	gdouble longitude;

	longitude = 
		tzs->tz_coord.long_degree +
		tzs->tz_coord.long_minute / 60.0 +
		tzs->tz_coord.long_second / (60.0 * 60.0);
	if (tzs->tz_coord.long_sign < 0)
		longitude = 0.0 - longitude;

	return longitude;
}

static gdouble
parse_latitude(struct tz_timezone *tzs)
{
	gdouble latitude;

	latitude = 
		tzs->tz_coord.lat_degree +
		tzs->tz_coord.lat_minute / 60.0 +
		tzs->tz_coord.lat_second / (60.0 * 60.0);
	if (tzs->tz_coord.lat_sign < 0)
		latitude = 0.0 - latitude;

	return latitude;
}

/*
 * The timezone is valid if it belongs to
 * the continent.
 */
gboolean
timezone_is_valid(struct tz_continent *pctnt, struct tz_timezone *ptz)
{
	gchar *str1;
	gchar *str2;
	gchar *s;
	gint len;
	gint equal;

	str1 = g_strdup(ptz->tz_oname);
	s = strchr(str1, '/');
	if (s != NULL)
		*s = '\0';
	else
		g_warning("Unexpected timezone name:%s\n", ptz->tz_oname);
	len = strlen(str1);
	str2 = g_strndup(pctnt->ctnt_id_desc, len);

	equal = !g_utf8_collate(str2, str1);
	
	g_free (str1);
	g_free (str2);
	return (equal);
}

/*
 * build the tree structure of region, and timzone
 * be aware of that all entry indexed with 0 are empty
 * and are used to show "- Select -". Real
 * datas start from index 1.
 */
void
map_load_timezones(Map *map)
{
	MapPrivate *priv;
	struct tz_continent *ctnts = NULL;
	struct tz_continent *pctnt = NULL;
	continent_item *continents = NULL;
	gint nctnt;
	gint i, j, k;

	g_return_if_fail(IS_MAP(map));
	priv = map->priv;

	nctnt = get_tz_continents(&ctnts);
	if (nctnt == -1) {
		g_warning("can not initialize timezone info\n");
		return;
	}

	continents = g_new0(continent_item, nctnt + 2);
	if (!continents) {
		g_warning("no enough memory\n");
		map_timezone_cleanup(map);
		return;
	}

	/* Add item to continent/country/timelist lists for GMT/UTC */
	continents[1].continent = g_new0(struct tz_continent, 1);
	sprintf(continents[1].continent->ctnt_name, "GMT/UTC");
	continents[1].continent->ctnt_id_desc = g_strdup("GMT/UTC");
	continents[1].continent->ctnt_display_desc = NULL;
	continents[1].continent->ctnt_next = ctnts;
	continents[1].nctry = 2;

	continents[1].ctry = g_new0(country_item, 2);
	continents[1].ctry[1].country = g_new0(struct tz_country, 1);
	sprintf(continents[1].ctry[1].country->ctry_code, "GMT/UTC");
	continents[1].ctry[1].country->ctry_id_desc = g_strdup("--");
	continents[1].ctry[1].country->ctry_display_desc = NULL;
	continents[1].ctry[1].ntz = 2;
	continents[1].ctry[1].ctnt = &continents[1];

	continents[1].ctry[1].tz = g_new0(timezone_item, 2);
	continents[1].ctry[1].tz[1].timezone = g_new0(struct tz_timezone, 1);
	sprintf(continents[1].ctry[1].tz[1].timezone->tz_name, "UTC");
	continents[1].ctry[1].tz[1].timezone->tz_id_desc = g_strdup("GMT/UTC");
	continents[1].ctry[1].tz[1].timezone->tz_display_desc = NULL;
	continents[1].ctry[1].tz[1].ctry = NULL;

	/* Add Rest of continents */
	for (i = 2, pctnt = ctnts; pctnt != NULL;
			pctnt = pctnt->ctnt_next, i++) {
		struct tz_country *ctries;
		struct tz_country *pctry;
		int nctry;

		continents[i].continent = pctnt;
		nctry = get_tz_countries(&ctries, pctnt);
		if (nctry == -1) {
			g_warning("can not initialize timezone info\n");
			map_timezone_cleanup(map);
			return;
		}
		continents[i].ctry = g_new0(country_item, nctry + 1);
		if (!continents[i].ctry) {
			g_warning("no enough memory\n");
			map_timezone_cleanup(map);
			return;
		}

		for (j = 1, pctry = ctries; pctry != NULL;
				pctry = pctry->ctry_next, j++) {
			struct tz_timezone *tzs;
			struct tz_timezone *ptz;
			int ntz;

			continents[i].ctry[j].country = pctry;
			continents[i].ctry[j].ctnt = &continents[i];
			ntz = get_timezones_by_country(&tzs, pctry);
			if (ntz == -1) {
				g_warning("can not initialize timezone info\n");
				map_timezone_cleanup(map);
				return;
			}
			continents[i].ctry[j].tz =
				g_new0(timezone_item, ntz + 1);
			if (!continents[i].ctry[j].tz) {
				g_warning("no enough memory\n");
				map_timezone_cleanup(map);
				return;
			}
			for (k = 1, ptz = tzs; ptz != NULL; ptz = ptz->tz_next) {
				timezone_item *zone;

				if (!timezone_is_valid(pctnt, ptz)) {
					continue;
				}
				zone = &continents[i].ctry[j].tz[k];
				zone->timezone = ptz;
				zone->ctry = &continents[i].ctry[j];
				zone->longitude = parse_longitude(ptz);
				zone->latitude = parse_latitude(ptz);
				map_geography_to_geometry(map,
						zone->longitude,
						zone->latitude,
						&zone->x, &zone->y);
				g_ptr_array_add(priv->timezones, zone);
				k++;
			}
			continents[i].ctry[j].ntz = k;
		}
		continents[i].nctry = j;
	}
	priv->continents = continents;
	priv->nctnt = i;

	g_signal_emit (map, signals[ALL_TIMEZONES_ADDED], 0);
	map_draw_timezones(map);
}

continent_item *
map_get_continents(Map *map)
{
	g_return_val_if_fail(IS_MAP(map), NULL);

	return map->priv->continents;
}

gint
map_get_continents_count(Map *map)
{
	g_return_val_if_fail(IS_MAP(map), 0);

	return map->priv->nctnt;
}

ZoomState
map_get_state(Map *map)
{
	g_return_val_if_fail(IS_MAP(map), 0);

	return map->priv->zoom;
}

timezone_item *
map_get_closest_timezone(Map *map, gint x, gint y, gint *distance)
{
	MapPrivate *priv;
	timezone_item *chosen = NULL;
	timezone_item *zone;
	gint min_dist = 0, dist;
	gint dx, dy;
	gint origx, origy;
	gint width, height;
	int i;

	g_return_val_if_fail(IS_MAP(map), NULL);

	priv = map->priv;
	if (!priv->scaled_pixbuf)
		return NULL;

	width = gdk_pixbuf_get_width(priv->scaled_pixbuf);
	height = gdk_pixbuf_get_height(priv->scaled_pixbuf);
	if (GTK_WIDGET(map)->allocation.width > width)
		origx = (GTK_WIDGET(map)->allocation.width - width) / 2;
	else
		origx = 0;
	if (GTK_WIDGET(map)->allocation.height > height)
		origy = (GTK_WIDGET(map)->allocation.height - height) /2;
	else
		origy = 0;
	x = (x - origx + priv->xoffset) % width;
	y = (y - origy + priv->yoffset) % height;

	for (i = 0; i < priv->timezones->len; i++) {
		zone = g_ptr_array_index (priv->timezones, i);

		dx = zone->x * priv->scale - x;
		dy = zone->y * priv->scale - y;
		dist = dx * dx + dy * dy;

		if (!chosen || dist < min_dist) {
			min_dist = dist;
			chosen = zone;
		}
	}

	if (distance)
		*distance = min_dist;
	if (min_dist < 25)
		return chosen;

	return NULL;
}

void
map_update_offset_with_scale(Map *map, gdouble x, gdouble y)
{
	MapPrivate *priv;
	gint origx, origy;
	gint new_origx, new_origy;
	gint width, height;
	gint new_width, new_height;
	gint awidth, aheight;
	gdouble scale;

	g_return_if_fail(IS_MAP(map));

	priv = map->priv;
	if (!priv->scaled_pixbuf)
		return;

	/*
	 * Beware that ZOOM_IN means that the map is already zoomed in.
	 * So this is a zoom out.
	 */
	if (priv->zoom != ZOOM_IN)
		scale = ZOOM_IN_SCALE / priv->zoom_out_scale;
	else
		scale = priv->zoom_out_scale / ZOOM_IN_SCALE;

	awidth = GTK_WIDGET(map)->allocation.width;
	aheight = GTK_WIDGET(map)->allocation.height;

	/*
	 * width and height of the worldmap before zooming
	 */
	width = gdk_pixbuf_get_width(priv->scaled_pixbuf);
	height = gdk_pixbuf_get_height(priv->scaled_pixbuf);
	/*
	 * width and height of the worldmap after zooming
	 */
	new_width = width * scale;
	new_height = height * scale;

	/*
	 * Calculate the (x, y) of left top corner of
	 * the worldmap in the widget window before zooming.
	 */
	if (awidth > width)
		origx = (awidth - width) / 2;
	else
		origx = 0;
	if (aheight > height)
		origy = (aheight - height) /2;
	else
		origy = 0;

	/*
	 * Calculate the (x, y) of left top corner of
	 * the worldmap in the widget window after zooming.
	 */
	if (awidth > new_width)
		new_origx = (awidth - new_width) / 2;
	else
		new_origx = 0;
	if (aheight > new_height)
		new_origy = (aheight - new_height) /2;
	else
		new_origy = 0;

	/*
	 * Calculate the new offset between the worldmap
	 * and the map widget window.
	 * If we are zooming out, y offset should be 0.
	 * Beware that ZOOM_IN means that the map is already zoomed in
	 * So this is a zoomed out.
	 */
	priv->xoffset = (gint)((x + priv->xoffset - origx) * scale - x + new_origx);
	priv->yoffset = (gint)((y + priv->yoffset - origy) * scale - y + new_origy);
	if (priv->zoom == ZOOM_IN)
		priv->yoffset = 0;

	priv->xoffset = (priv->xoffset + new_width) % new_width;
	priv->yoffset = (priv->yoffset + new_height) % new_height;
}

void
map_update_offset(Map *map, gdouble newx, gdouble newy)
{
	GtkWidget *widget;
	MapPrivate *priv;
	gint xoff, yoff;
	gint width, height;

	g_return_if_fail(IS_MAP(map));

	widget = GTK_WIDGET(map);
	priv = map->priv;
	if (!priv->scaled_pixbuf)
		return;

	xoff = (gint)(newx - priv->x);
	yoff = (gint)(newy - priv->y);
	width = gdk_pixbuf_get_width(priv->scaled_pixbuf);
	height = gdk_pixbuf_get_height(priv->scaled_pixbuf);
	if (xoff != 0 ) {
		priv->xoffset =
			(priv->xoffset - xoff + width) % width;
	}
	if (yoff != 0) {
		if (priv->yoffset - yoff < 0)
			priv->yoffset = 0;
		else if ((priv->yoffset -yoff) > height - widget->allocation.height)
			priv->yoffset = height - widget->allocation.height;
		else
			priv->yoffset =
				(priv->yoffset - yoff + height) % height;
	}
	priv->x = newx;
	priv->y = newy;
}

void
map_set_offset(Map *map, gdouble x, gdouble y)
{
	g_return_if_fail(IS_MAP(map));

	map->priv->x = x;
	map->priv->y = y;
}

void
map_set_cursor(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	if (map->priv->zoom == ZOOM_OUT) {
		if (map->priv->scale < ZOOM_IN_SCALE)
			gdk_window_set_cursor(GTK_WIDGET(map)->window, map->priv->magnifier_cursor);
	} else
		gdk_window_set_cursor(GTK_WIDGET(map)->window, map->priv->hand_cursor);
}

void
map_set_hand_cursor(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	gdk_window_set_cursor(GTK_WIDGET(map)->window, map->priv->hand_cursor);
}

void
map_set_magnifier_cursor(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	if (map->priv->scale < ZOOM_IN_SCALE)
		gdk_window_set_cursor(GTK_WIDGET(map)->window, map->priv->magnifier_cursor);
}

void
map_set_default_cursor(Map *map)
{
	g_return_if_fail(IS_MAP(map));

	gdk_window_set_cursor(GTK_WIDGET(map)->window, NULL);
}
