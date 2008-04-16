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

#ifndef _MAP_H_
#define _MAP_H_

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define MAP_TYPE	(map_get_type())
#define MAP(obj)	(G_TYPE_CHECK_INSTANCE_CAST((obj),\
								MAP_TYPE, Map))
#define MAP_CLASS(klass)	(G_TYPE_CHECK_CLASS_CAST((klass),\
										MAP_TYPE, MapClass))
#define MAP_GET_CLASS(obj)	(G_TYPE_INSTANCE_GET_CLASS((obj),\
										MAP_TYPE, MapClass))
#define IS_MAP(obj)		(G_TYPE_CHECK_INSTANCE_TYPE((obj),\
										MAP_TYPE))
#define IS_MAP_CLASS(klass)	(G_TYPE_CHECK_CLASS_TYPE((klass),\
											MAP_TYPE))
typedef enum _ZoomState
{
	ZOOM_IN,
	ZOOM_OUT,
	ZOOM_STATE
} ZoomState;

typedef enum _ZoneState
{
	POINT_NORMAL,
	POINT_HOVERED,
	POINT_SELECTED,
	POINT_STATE
} ZoneState;

typedef struct _continent_item continent_item;
typedef struct _country_item country_item;
typedef struct _timezone_item timezone_item;

struct _continent_item
{
	struct tz_continent *continent;
	country_item *ctry;
	int nctry;

	GtkTreeRowReference *ref;
};

struct _country_item
{
	struct tz_country *country;
	timezone_item *tz;
	int ntz;
	continent_item *ctnt;

	GtkTreeRowReference *ref;
};

struct _timezone_item
{
	struct tz_timezone *timezone;
	country_item *ctry;

	/* geometry */
	gint x, y;
	/* geography */
	gdouble longitude, latitude;

	ZoneState state;

	GtkTreeRowReference *ref;
};

typedef struct _Map	Map;
typedef struct _MapPrivate	MapPrivate;
typedef struct _MapClass	MapClass;

struct _Map
{
	GtkDrawingArea widget;

	MapPrivate *priv;
};

struct _MapClass
{
	GtkDrawingAreaClass parent_class;

	void (*timezone_added)(GtkWidget *widget,
			gpointer *timezone,
			gpointer *user_data);
	void (*all_timezones_added)(GtkWidget *widget,
			gpointer *timezones,
			gpointer *user_data);
};

GtkType	map_get_type(void);
GtkWidget*	map_new(void);
void	map_geography_to_geometry(Map *map,
					gdouble longitude, gdouble latitude,
					gint *x, gint *y);
void	map_zoom_in(Map *map);
void	map_zoom_out(Map *map);
void	map_load_timezones(Map *map);
void	map_add_timezones(Map *map, continent_item *timezones);
continent_item	*map_get_continents(Map *map);
gint	map_get_continents_count(Map *map);
void	map_set_timezone_hovered(Map *map, timezone_item *zone);
void	map_set_timezone_selected(Map *map, timezone_item *zone);
timezone_item	*map_get_closest_timezone(Map *map, gint x, gint y, gint *distance);
void	map_draw_timezone(Map *map, timezone_item *zone);
void	map_unset_hoverd_timezone(Map *map);
ZoomState	map_get_state(Map *map);
void	map_update_offset(Map *map, gdouble newx, gdouble newy);
void	map_update_offset_with_scale(Map *map, gdouble x, gdouble y);
void	map_set_offset(Map *map, gdouble x, gdouble y);
void	map_set_hand_cursor(Map *map);
void	map_set_magnifier_cursor(Map *map);
void	map_set_cursor(Map *map);
void	map_set_default_cursor(Map *map);

G_END_DECLS

#endif
