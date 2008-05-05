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
#include <libzoneinfo.h>
#include <string.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <gdk-pixbuf/gdk-pixbuf.h>

#include "callbacks.h"
#include "interface-globals.h"
#include "window-graphics.h"
#include "timezone.h"
#include "map.h"

#define	TIMEZONENODE "timezonetoplevel"

struct _TimezonePrivate
{
	GladeXML *xml;

	/* widgets */
	GtkWidget *map;
	GtkWidget *combo;

	GtkWidget *ctnt_combo;
	GtkWidget *ctry_combo;
	GtkWidget *tz_combo;

	GtkWidget *ctnt_label;
	GtkWidget *ctry_label;
	GtkWidget *tz_label;

	GtkListStore *ctnt_store;
	GtkListStore *ctry_store;
	GtkListStore *tz_store;

	guint32 click_time;
};

static GObjectClass *parent_class = NULL;
static char *select_label;

G_DEFINE_TYPE(Timezone, timezone, GTK_TYPE_VBOX)

static void	timezone_class_init(TimezoneClass *klass);
static void	timezone_init(Timezone *timezone);
static void	timezone_destroy(GtkObject *object);
static void timezone_finalize(GObject *object);
static gboolean	on_button_pressed(GtkWidget *widget,
		GdkEventButton *event, gpointer user_data);
static gboolean	on_button_released(GtkWidget *widget,
		GdkEventButton *event, gpointer user_data);
static gboolean	on_motion_notify(GtkWidget *widget,
		GdkEventMotion *event, gpointer user_data);
static void	on_all_timezones_added(GtkWidget *widget, gpointer user_data);
static void	on_region_changed(GtkComboBox *widget, gpointer user_data);
static void	on_country_changed(GtkComboBox *widget, gpointer user_data);
static void	on_timezone_changed(GtkComboBox *widget, gpointer user_data);
static void	timezone_combo_init(Timezone *timezone);
static void	timezone_get_current_tz(Timezone *timezone,
		continent_item **ctnt, gint *ctnt_index,
		country_item **ctry, gint *ctry_index,
		timezone_item **tz, gint *tz_index);

static void
timezone_class_init(TimezoneClass *klass)
{
	GtkObjectClass *object_class;
	GtkWidgetClass *widget_class;

	parent_class = gtk_type_class(GTK_TYPE_WIDGET);

	object_class = (GtkObjectClass *)klass;
	object_class->destroy = timezone_destroy;

	widget_class = (GtkWidgetClass *)klass;

	select_label = _("----- Select -----");
}

static gboolean
on_query_tooltip(GtkWidget *widget, gint x, gint y,
			gboolean keyboard_mode, GtkTooltip *tooltip,
			gpointer user_data)
{
	timezone_item *tz;

	tz = map_get_closest_timezone(MAP(widget), x, y, NULL);
	if (tz) {
		char *str;

		if (tz->timezone->tz_oname) {
			str = strrchr(tz->timezone->tz_oname, '/');
			if (str && (*(str + 1) != 0)) {
				gtk_tooltip_set_text(tooltip, str + 1);

				return TRUE;
			} else if (!str) {
				gtk_tooltip_set_text(tooltip, tz->timezone->tz_oname);

				return TRUE;
			}
		}

		if (tz->timezone->tz_name) {
			str = strrchr(tz->timezone->tz_name, '/');
			if (str && (*(str + 1) != 0))
				gtk_tooltip_set_text(tooltip, str + 1);
			else
				gtk_tooltip_set_text(tooltip, tz->timezone->tz_name);

			return TRUE;
		}
	} else
		return FALSE;
}

static void
on_all_timezones_added(GtkWidget *widget, gpointer user_data)
{
	Map *map;
	TimezonePrivate *priv;
	continent_item *ctnt;
	GtkTreeIter iter;
	GtkTreePath *path;
	continent_item *sys_ctnt = NULL;
	country_item *sys_ctry = NULL;
	timezone_item *sys_tz = NULL;
	gint sys_ctnt_index = 0;
	gint sys_ctry_index = 0;
	gint sys_tz_index = 0;
	gint nctnt;
	gint i, j, k;

	priv = TIMEZONE(user_data)->priv;
	map = MAP(widget);

	ctnt = map_get_continents(map);
	nctnt = map_get_continents_count(map);
	timezone_get_current_tz(TIMEZONE(user_data),
			&sys_ctnt, &sys_ctnt_index,
			&sys_ctry, &sys_ctry_index,
			&sys_tz, &sys_tz_index);
	if (sys_ctnt == NULL || sys_ctry == NULL || sys_tz == NULL) {
		/*
		 * if can not get current timezone,
		 * set the default combo box entry
		 * to "----- select -----".
		 */
		sys_ctnt = &ctnt[0];
		sys_ctry = &ctnt[1].ctry[0];
		sys_tz = &ctnt[1].ctry[1].tz[0];
	}

	for (i = 0; i < nctnt; i++) {
		gtk_list_store_append(priv->ctnt_store, &iter);
		gtk_list_store_set(priv->ctnt_store, &iter, 0, &ctnt[i], -1);
		path =
			gtk_tree_model_get_path(GTK_TREE_MODEL(priv->ctnt_store), &iter);
		if (ctnt[i].ref)
			gtk_tree_row_reference_free(ctnt[i].ref);
		ctnt[i].ref =
			gtk_tree_row_reference_new(GTK_TREE_MODEL(priv->ctnt_store), path);
	}

	gtk_combo_box_set_active(GTK_COMBO_BOX(priv->ctnt_combo), sys_ctnt_index);
	gtk_combo_box_set_active(GTK_COMBO_BOX(priv->ctry_combo), sys_ctry_index);
	gtk_combo_box_set_active(GTK_COMBO_BOX(priv->tz_combo), sys_tz_index);
}

static void
render_region_name(GtkCellLayout *layout,
		GtkCellRenderer *cell,
		GtkTreeModel *model,
		GtkTreeIter *iter,
		gpointer user_data)
{
	continent_item *ctnt = NULL;
	char *text;

	gtk_tree_model_get(model, iter, 0, &ctnt, -1);
	if (!ctnt)
		return;
	if (ctnt->continent) {
#ifdef	USE_LIBZONEINFO_TRANSLATION
		if (ctnt->continent->ctnt_display_desc)
			text = ctnt->continent->ctnt_display_desc;
		else if (ctnt->continent->ctnt_id_desc)
			text = ctnt->continent->ctnt_id_desc;
#else	/* ! USE_LIBZONEINFO_TRANSLATION */
		if (ctnt->continent->ctnt_id_desc)
			text = _(ctnt->continent->ctnt_id_desc);
#endif	/* USE_LIBZONEINFO_TRANSLATION */
		else
			text = ctnt->continent->ctnt_name;
	} else
		text = select_label;
	g_object_set(cell, "text", text, NULL);
}

static void
render_country_name(GtkCellLayout *layout,
		GtkCellRenderer *cell,
		GtkTreeModel *model,
		GtkTreeIter *iter,
		gpointer user_data)
{
	country_item *ctry = NULL;
	char *text;

	gtk_tree_model_get(model, iter, 0, &ctry, -1);
	if (!ctry)
		return;
	if (ctry->country) {
#ifdef	USE_LIBZONEINFO_TRANSLATION
		if (ctry->country->ctry_display_desc)
			text = ctry->country->ctry_display_desc;
		else if (ctry->country->ctry_id_desc)
			text = ctry->country->ctry_id_desc;
#else	/* ! USE_LIBZONEINFO_TRANSLATION */
		if (ctry->country->ctry_id_desc)
			text = _(ctry->country->ctry_id_desc);
#endif	/* USE_LIBZONEINFO_TRANSLATION */
		else
			text = ctry->country->ctry_code;
	} else
		text = select_label;
	g_object_set(cell, "text", text, NULL);
}

static void
render_timezone_name(GtkCellLayout *layout,
		GtkCellRenderer *cell,
		GtkTreeModel *model,
		GtkTreeIter *iter,
		gpointer user_data)
{
	timezone_item *tz = NULL;
	char *text;

	gtk_tree_model_get(model, iter, 0, &tz, -1);
	if (!tz)
		return;

	g_assert(tz != NULL);
	/*
	 * If there is only one timezone, use country
	 * to render the cell. Or else, if the timezone is
	 * not NULL, use the timezone to render the cell
	 * . Or else use "select" to render the cell.
	 */
	if (tz->ctry && tz->ctry->ntz == 2) {
		if (tz->ctry->country) {
#ifdef	USE_LIBZONEINFO_TRANSLATION
			if (tz->ctry->country->ctry_display_desc)
				text = tz->ctry->country->ctry_display_desc;
			else if (tz->ctry->country->ctry_id_desc)
				text = tz->ctry->country->ctry_id_desc;
#else	/* ! USE_LIBZONEINFO_TRANSLATION */
			if (tz->ctry->country->ctry_id_desc)
				text = _(tz->ctry->country->ctry_id_desc);
#endif	/* USE_LIBZONEINFO_TRANSLATION */
			else
				text = tz->ctry->country->ctry_code;
		}
	} else if (tz->timezone) {
#ifdef	USE_LIBZONEINFO_TRANSLATION
		if (tz->timezone->tz_display_desc)
			text = tz->timezone->tz_display_desc;
		else if (tz->timezone->tz_id_desc)
			text = tz->timezone->tz_id_desc;
#else	/* ! USE_LIBZONEINFO_TRANSLATION */
		if (tz->timezone->tz_id_desc)
			text = _(tz->timezone->tz_id_desc);
#endif	/* USE_LIBZONEINFO_TRANSLATION */
		else
			text = tz->timezone->tz_name;
	} else
		text = select_label;

	g_object_set(cell, "text", text, NULL);
}

static void
on_region_changed(GtkComboBox *ctnt_combo, gpointer user_data)
{
	TimezonePrivate *priv;
	GtkWidget *ctry_combo;
	GtkListStore *ctry_store;
	continent_item *ctnt;
	GtkTreeIter iter;
	GtkTreePath *path;
	gint ictnt, nctnt;
	gint i, j;

	priv = TIMEZONE(user_data)->priv;
	ctry_combo = priv->ctry_combo;
	ctnt = map_get_continents(MAP(priv->map));
	nctnt = map_get_continents_count(MAP(priv->map));

	/* clear country list store */
	ctry_store =
		GTK_LIST_STORE(gtk_combo_box_get_model(GTK_COMBO_BOX(ctry_combo)));
	gtk_list_store_clear(GTK_LIST_STORE(ctry_store));

	i = gtk_combo_box_get_active(GTK_COMBO_BOX(ctnt_combo));
	if (i > 0 && i <= nctnt) {
		for (j = 0; j < ctnt[i].nctry; j++) {
			gtk_list_store_append(ctry_store, &iter);
			gtk_list_store_set(ctry_store, &iter, 0,
					&ctnt[i].ctry[j], -1);
			path = gtk_tree_model_get_path(GTK_TREE_MODEL(ctry_store), &iter);
			if (ctnt[i].ctry[j].ref)
				gtk_tree_row_reference_free(ctnt[i].ctry[j].ref);
			ctnt[i].ctry[j].ref =
				gtk_tree_row_reference_new(GTK_TREE_MODEL(ctry_store), path);
		}
	} else {
		/*
		 * insert "----- select -----" into
		 * the combo box only
		 */
		gtk_list_store_append(ctry_store, &iter);
		gtk_list_store_set(ctry_store, &iter, 0, &ctnt[1].ctry[0], -1);
	}
	/*
	 * if there is only one entry(plugs "select" is 2),
	 * make it the active one.
	 */
	if (i != 0 && ctnt[i].nctry == 2)
		gtk_combo_box_set_active(GTK_COMBO_BOX(ctry_combo), 1);
	else
		gtk_combo_box_set_active(GTK_COMBO_BOX(ctry_combo), 0);
}

static void
on_country_changed(GtkComboBox *ctry_combo, gpointer user_data)
{
	TimezonePrivate *priv;
	GtkWidget *ctnt_combo;
	GtkWidget *tz_combo;
	GtkListStore *tz_store;
	continent_item *ctnt;
	GtkTreeIter iter;
	GtkTreePath *path;
	gint nctnt;
	gint i, j, k;

	priv = TIMEZONE(user_data)->priv;
	ctnt_combo = priv->ctnt_combo;
	tz_combo = priv->tz_combo;
	ctnt = map_get_continents(MAP(priv->map));
	nctnt = map_get_continents_count(MAP(priv->map));

	/* clear timezone list store */
	tz_store =
		GTK_LIST_STORE(gtk_combo_box_get_model(GTK_COMBO_BOX(tz_combo)));
	gtk_list_store_clear(GTK_LIST_STORE(tz_store));

	i = gtk_combo_box_get_active(GTK_COMBO_BOX(ctnt_combo));
	j = gtk_combo_box_get_active(GTK_COMBO_BOX(ctry_combo));
	if (i > 0 && i <= nctnt &&
			j > 0 && j <= ctnt[i].nctry) {
		for (k = 0; k < ctnt[i].ctry[j].ntz; k++) {
			gtk_list_store_append(tz_store, &iter);
			gtk_list_store_set(tz_store, &iter, 0,
					&ctnt[i].ctry[j].tz[k], -1);
			path =
				gtk_tree_model_get_path(GTK_TREE_MODEL(tz_store), &iter);
			if (ctnt[i].ctry[j].tz[k].ref)
				gtk_tree_row_reference_free(ctnt[i].ctry[j].tz[k].ref);
			ctnt[i].ctry[j].tz[k].ref =
				gtk_tree_row_reference_new(GTK_TREE_MODEL(tz_store), path);
		}
	} else {
		/*
		 * insert "----- select -----" into
		 * the combo box only
		 */
		gtk_list_store_append(tz_store, &iter);
		gtk_list_store_set(tz_store, &iter, 0, &ctnt[1].ctry[1].tz[0], -1);
	}
	/*
	 * if there is only one entry(plus "select" is 2),
	 * make it the active one.
	 */
	if (i != 0 && j != 0 && ctnt[i].ctry[j].ntz == 2)
		gtk_combo_box_set_active(GTK_COMBO_BOX(tz_combo), 1);
	else
		gtk_combo_box_set_active(GTK_COMBO_BOX(tz_combo), 0);
}

static void
on_timezone_changed(GtkComboBox *widget, gpointer user_data)
{
	TimezonePrivate *priv;
	GtkTreeModel *model;
	GtkTreeIter iter;
	Map *map;

	priv = TIMEZONE(user_data)->priv;
	map = MAP(priv->map);
	model = GTK_TREE_MODEL(priv->tz_store);
	if (gtk_combo_box_get_active_iter(widget, &iter)) {
		timezone_item *tz;

		gtk_tree_model_get(model, &iter, 0, &tz, -1);
		if (tz && GTK_WIDGET_REALIZED(GTK_WIDGET(map))) {
			GdkRectangle rect;

			map_set_timezone_selected(map, tz);

			rect.x = rect.y = 0;
			rect.width = GTK_WIDGET(map)->allocation.width;
			rect.height = GTK_WIDGET(map)->allocation.height;
			gdk_window_invalidate_rect(GTK_WIDGET(map)->window,
					&rect, FALSE);
		}
	}
}


static void
timezone_init(Timezone *timezone)
{
	TimezonePrivate *priv;
	GdkColor backcolour;

	priv = g_new0(TimezonePrivate, 1);
	timezone->priv = priv;

	/* timezone map */
	priv->map = map_new();
	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(priv->map, GTK_STATE_NORMAL, &backcolour);

	gtk_widget_show(priv->map);
	gtk_box_pack_start(GTK_BOX(timezone), priv->map, FALSE, FALSE, 0); 
	g_signal_connect(G_OBJECT(priv->map), "button-press-event",
						G_CALLBACK(on_button_pressed), timezone);
	g_signal_connect(G_OBJECT(priv->map), "button-release-event",
						G_CALLBACK(on_button_released), timezone);
	g_signal_connect(G_OBJECT(priv->map), "motion-notify-event",
						G_CALLBACK(on_motion_notify), NULL);
	g_signal_connect(G_OBJECT(priv->map), "query-tooltip",
						G_CALLBACK(on_query_tooltip), NULL);
	g_signal_connect(G_OBJECT(priv->map), "all-timezones-added",
						G_CALLBACK(on_all_timezones_added), timezone);

	/* region, country and timezone combo */
	timezone_combo_init(timezone);

	priv->ctnt_label =
		glade_xml_get_widget(priv->xml, "regionlabel");
	priv->ctry_label =
		glade_xml_get_widget(priv->xml, "countrylabel");
	priv->tz_label =
		glade_xml_get_widget(priv->xml, "timezonelabel");
}

static void
timezone_destroy(GtkObject *object)
{
	Timezone *timezone;

	g_return_if_fail(object != NULL);
	g_return_if_fail(IS_TIMEZONE(object));

	timezone = TIMEZONE(object);

	if (GTK_OBJECT_CLASS(parent_class)->destroy)
		(*GTK_OBJECT_CLASS(parent_class)->destroy)(object);
}

static void
timezone_finalize(GObject *object)
{
	Timezone *timezone;
	TimezonePrivate *priv;

	g_return_if_fail(object != NULL);
	g_return_if_fail(IS_TIMEZONE(object));

	timezone = TIMEZONE(object);
	priv = timezone->priv;

	if (priv) {
		if (priv->xml) {
			g_object_unref(priv->xml);
			priv->xml = NULL;
		}
	}
	if (G_OBJECT_CLASS(parent_class)->finalize)
		G_OBJECT_CLASS(parent_class)->finalize(object);
}

GtkWidget*
timezone_new(void)
{
	Timezone *timezone;
	TimezonePrivate *priv;

	timezone = TIMEZONE(gtk_type_new(timezone_get_type()));
	priv = timezone->priv;
	map_load_timezones(MAP(priv->map));

	return GTK_WIDGET(timezone);
}

static gboolean
on_button_pressed(GtkWidget *widget, GdkEventButton *event,
					gpointer user_data)
{
	TimezonePrivate *priv;
	Map *map;
	GtkTreeModel *ctnt_model;
	GtkTreeModel *ctry_model;
	GtkTreeModel *tz_model;
	GtkRequisition requisition;

	priv = TIMEZONE(user_data)->priv;
	map = MAP(widget);
	ctnt_model = GTK_TREE_MODEL(priv->ctnt_store);
	ctry_model = GTK_TREE_MODEL(priv->ctry_store);
	tz_model = GTK_TREE_MODEL(priv->tz_store);

	/* save the time */
	priv->click_time = event->time;

	if (event->button == 1) {
		timezone_item *tz;

		map_set_offset(map, event->x, event->y);
		tz = map_get_closest_timezone(map, event->x, event->y, NULL);
		if (tz) {
			continent_item *ctnt;
			country_item *ctry;
			GtkTreePath *path;
			GtkTreeIter iter;

			/*
			 * The timezone point is seletced
			 *  in the "changed" callback of the combo box.
			 */
			ctnt = tz->ctry->ctnt;
			path = gtk_tree_row_reference_get_path(ctnt->ref);
			if (gtk_tree_model_get_iter(ctnt_model, &iter, path))
				gtk_combo_box_set_active_iter(GTK_COMBO_BOX(priv->ctnt_combo),
						&iter);
			ctry = tz->ctry;
			path = gtk_tree_row_reference_get_path(ctry->ref);
			if (gtk_tree_model_get_iter(ctry_model, &iter, path))
				gtk_combo_box_set_active_iter(GTK_COMBO_BOX(priv->ctry_combo),
						&iter);
			path = gtk_tree_row_reference_get_path(tz->ref);
			if (gtk_tree_model_get_iter(tz_model, &iter, path))
				gtk_combo_box_set_active_iter(GTK_COMBO_BOX(priv->tz_combo),
						&iter);
			}

	}

	gtk_widget_size_request(widget, &requisition);
	widget->requisition.width = requisition.width;
	widget->requisition.height = requisition.height;
	gtk_widget_queue_resize(widget);

	return FALSE;
}

static gboolean
on_button_released(GtkWidget *widget, GdkEventButton *event,
					gpointer user_data)
{
	TimezonePrivate *priv;
	Map *map;
	GtkTreeModel *ctnt_model;
	GtkTreeModel *ctry_model;
	GtkTreeModel *tz_model;
	GtkRequisition requisition;
	gint interval;

	priv = TIMEZONE(user_data)->priv;
	map = MAP(widget);
	ctnt_model = GTK_TREE_MODEL(priv->ctnt_store);
	ctry_model = GTK_TREE_MODEL(priv->ctry_store);
	tz_model = GTK_TREE_MODEL(priv->tz_store);

	interval = event->time - priv->click_time;
	if (interval <= 0 || interval >= 200)
		return FALSE;

	/*
	* if click above on city,
	* do not zoom in
	*/
	if (event->button == 1 &&
			map_get_state(map) != ZOOM_IN &&
			(!map_get_closest_timezone(map, event->x, event->y, NULL))) {
			map_update_offset_with_scale(map, event->x, event->y);
			map_zoom_in(map);
	} else if (event->button == 3 &&
			map_get_state(map) != ZOOM_OUT) {
		map_update_offset_with_scale(map, event->x, event->y);
		map_zoom_out(map);
	}

	gtk_widget_size_request(widget, &requisition);
	widget->requisition.width = requisition.width;
	widget->requisition.height = requisition.height;
	gtk_widget_queue_resize(widget);

	return FALSE;
}

static gboolean
on_motion_notify(GtkWidget *widget, GdkEventMotion *event,
					gpointer user_data)
{
	GdkRectangle rect;
	timezone_item *tz;
	gint distance;

	if (event->state & GDK_BUTTON1_MASK) {
		map_update_offset(MAP(widget), event->x, event->y);
	}

	tz = map_get_closest_timezone(MAP(widget), event->x, event->y, &distance);
	if (distance < 100)
		map_set_default_cursor(MAP(widget));
	else
		map_set_cursor(MAP(widget));
	if (tz) {
		map_set_timezone_hovered(MAP(widget), tz);
	} else {
		map_unset_hoverd_timezone(MAP(widget));
	}

	rect.x = rect.y = 0;
	rect.width = widget->allocation.width;
	rect.height = widget->allocation.height;
	gdk_window_invalidate_rect(widget->window,
			&rect, FALSE);

	return TRUE;
}

GtkWidget *
timezone_get_continent_combo(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->ctnt_combo;
}

GtkWidget *
timezone_get_country_combo(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->ctry_combo;
}

GtkWidget *
timezone_get_timezone_combo(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->tz_combo;
}

GtkWidget *
timezone_get_continent_label(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->ctnt_label;
}

GtkWidget *
timezone_get_country_label(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->ctry_label;
}

GtkWidget *
timezone_get_timezone_label(Timezone *timezone)
{
	g_return_val_if_fail(IS_TIMEZONE(timezone), NULL);

	return timezone->priv->tz_label;
}

gboolean
timezone_get_selected_tz(Timezone *timezone,
		InstallationProfileType *profile)
		
{
	continent_item *ctnt;
	GtkWidget *ctnt_combo;
	GtkWidget *ctry_combo;
	GtkWidget *tz_combo;
	gint ictnt;
	gint ictry;
	gint itz;
	static gboolean first_time = TRUE;

	g_return_val_if_fail(IS_TIMEZONE(timezone), FALSE);

	ctnt_combo = timezone->priv->ctnt_combo;
	ctry_combo = timezone->priv->ctry_combo;
	tz_combo = timezone->priv->tz_combo;

	ictnt = gtk_combo_box_get_active(GTK_COMBO_BOX(ctnt_combo));
	ictry = gtk_combo_box_get_active(GTK_COMBO_BOX(ctry_combo));
	itz = gtk_combo_box_get_active(GTK_COMBO_BOX(tz_combo));
	if (ictnt == 0 || ictry == 0 || itz == 0) {
		gui_install_prompt_dialog(FALSE, FALSE, FALSE, GTK_MESSAGE_ERROR,
				_("Time Zone Invalid"),
				_("Please select a valid time zone"));
		return (FALSE);
	} else {
		ctnt = map_get_continents(MAP(timezone->priv->map));

		profile->continent = ctnt[ictnt].continent;
		g_warning("continent:%s", ctnt[ictnt].continent->ctnt_name);

		profile->country = ctnt[ictnt].ctry[ictry].country;
		g_warning("country:%s",
			ctnt[ictnt].ctry[ictry].country->ctry_code);

		profile->timezone =
			ctnt[ictnt].ctry[ictry].tz[itz].timezone;
		g_warning("timezone:%s",
			ctnt[ictnt].ctry[ictry].tz[itz].timezone->tz_name);
		if (first_time) {
			/*
			 * This is used to
			 * determine the default
			 * language and should be
			 * called for only one time.
			 */
			orchestrator_om_set_preinstal_time_zone(profile->country->ctry_code,
									profile->timezone->tz_name);
			first_time = FALSE;
		}
		return (TRUE);
	}
}

static void
timezone_get_current_tz(Timezone *timezone,
		continent_item **ctnt, gint *ctnt_index,
		country_item **ctry, gint *ctry_index,
		timezone_item **tz, gint *tz_index)
{
	continent_item *ctnts;
	gchar *system_timezone;
	gint nctnt;
	gint i, j, k;

	g_return_if_fail(IS_TIMEZONE(timezone));

	ctnts = map_get_continents(MAP(timezone->priv->map));
	nctnt = map_get_continents_count(MAP(timezone->priv->map));
	system_timezone = get_system_tz("/");
	if (!system_timezone)
		return;

	for (i = 1; i < nctnt; i++) {
		for (j = 1; j < ctnts[i].nctry; j++) {
			for (k = 1; k < ctnts[i].ctry[j].ntz; k++) {
				if (strncmp(
					ctnts[i].ctry[j].tz[k].timezone->tz_name,
					system_timezone, strlen(system_timezone)) == 0) {
					*ctnt = &ctnts[i];
					*ctry = &ctnts[i].ctry[j];
					*tz = &ctnts[i].ctry[j].tz[k];
					*ctnt_index = i;
					*ctry_index = j;
					*tz_index = k;
					break;
				}
			}
		}
	}
	free(system_timezone);
}

static void
timezone_combo_init(Timezone *timezone)
{
	TimezonePrivate *priv;
	GtkCellRenderer *renderer;

	priv = timezone->priv;
	priv->xml = glade_xml_new(GLADEDIR "/" DATETIMEZONEFILENAME,
			TIMEZONENODE, NULL);
	priv->combo = glade_xml_get_widget(priv->xml, "timezonetoplevel");
	gtk_widget_show(priv->combo);
	gtk_box_pack_start(GTK_BOX(timezone), priv->combo, FALSE, FALSE, 6);

	priv->ctnt_store = gtk_list_store_new(1, G_TYPE_POINTER);
	priv->ctnt_combo =
		glade_xml_get_widget(priv->xml, "regioncombobox");
	gtk_combo_box_set_model(GTK_COMBO_BOX(priv->ctnt_combo),
			GTK_TREE_MODEL(priv->ctnt_store));
	g_object_unref(priv->ctnt_store);
	renderer = gtk_cell_renderer_text_new();
	g_object_set(G_OBJECT(renderer), "ellipsize", PANGO_ELLIPSIZE_MIDDLE, NULL);
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(priv->ctnt_combo),
			renderer, TRUE);
	gtk_cell_layout_set_cell_data_func(GTK_CELL_LAYOUT(priv->ctnt_combo),
			renderer, render_region_name, NULL, NULL);

	g_signal_connect(G_OBJECT(priv->ctnt_combo), "changed",
						G_CALLBACK(on_region_changed), timezone);

	priv->ctry_store = gtk_list_store_new(1, G_TYPE_POINTER);
	priv->ctry_combo =
		glade_xml_get_widget(priv->xml, "countrycombobox");
	gtk_combo_box_set_model(GTK_COMBO_BOX(priv->ctry_combo),
			GTK_TREE_MODEL(priv->ctry_store));
	g_object_unref(priv->ctry_store);
	renderer = gtk_cell_renderer_text_new();
	g_object_set(G_OBJECT(renderer), "ellipsize", PANGO_ELLIPSIZE_MIDDLE, NULL);
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(priv->ctry_combo),
			renderer, TRUE);
	gtk_cell_layout_set_cell_data_func(GTK_CELL_LAYOUT(priv->ctry_combo),
			renderer, render_country_name, NULL, NULL);

	g_signal_connect(G_OBJECT(priv->ctry_combo), "changed",
						G_CALLBACK(on_country_changed), timezone);

	priv->tz_store = gtk_list_store_new(1, G_TYPE_POINTER);
	priv->tz_combo =
		glade_xml_get_widget(priv->xml, "timezonecombobox");
	gtk_combo_box_set_model(GTK_COMBO_BOX(priv->tz_combo),
			GTK_TREE_MODEL(priv->tz_store));
	g_object_unref(priv->tz_store);
	renderer = gtk_cell_renderer_text_new();
	g_object_set(G_OBJECT(renderer), "ellipsize", PANGO_ELLIPSIZE_MIDDLE, NULL);
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(priv->tz_combo),
			renderer, TRUE);
	gtk_cell_layout_set_cell_data_func(GTK_CELL_LAYOUT(priv->tz_combo),
			renderer, render_timezone_name, NULL, NULL);

	g_signal_connect(G_OBJECT(priv->tz_combo), "changed",
						G_CALLBACK(on_timezone_changed), timezone);
}
