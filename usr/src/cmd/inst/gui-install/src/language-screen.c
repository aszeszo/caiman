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
#pragma ident	"@(#)language-screen.c	1.1	07/08/03 SMI"

#include <glib/gi18n.h>
#include <gtk/gtk.h>
#include <gdk/gdkkeysyms.h>
#include <string.h>
#include "installation-profile.h"
#include "interface-globals.h"
#include "window-graphics.h"
#include "language-screen.h"

typedef struct _language_item {
	int index;
	lang_info_t *language;
	GtkWidget *check;
	/*
	 * the list storing the
	 * GtkTreeRowReference
	 */
	GList *ref;
} language_item;

typedef struct _LanguageWindowXML {
	GtkWidget *lang_scrolled;
	GtkWidget *lang_vbox;
	GtkWidget *lang_viewport;
	GtkWidget *default_combo;
	GtkWidget *default_entry;
	GtkCellRenderer *renderer;
	GtkListStore *store;
	language_item *langs;
	gint nlangs;
	gboolean defaultset; /* Used so the default is only set once */
} LanguageWindowXML;

LanguageWindowXML LanguageWindow;

void
get_default_language()
{
	GList *l;

	l = InstallationProfile.languages;
	while (l) {
		g_warning("%s", orchestrator_om_language_get_name(l->data));
		l = g_list_next(l);
	}
}

void
get_default_locale()
{
	GList *l;

	l = InstallationProfile.locales;
	while (l) {
		g_warning("%s", orchestrator_om_locale_get_name(l->data));
		l = g_list_next(l);
	}
}

void
on_language_toggled(GtkToggleButton *button, gpointer user_data)
{
	GList *ref = NULL;
	GtkTreeIter iter;
	GtkTreeIter sibling;
	language_item *item;
	gboolean toggled;

	item = g_object_get_data(G_OBJECT(button), "item");
	toggled = gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(button));
	if (toggled) {
		GtkTreeRowReference *ref = NULL;
		GtkTreePath *path;
		locale_info_t *locale =
				orchestrator_om_language_get_locales(item->language);

		InstallationProfile.languages = g_list_append(
				InstallationProfile.languages, item->language);
		/*
		 * Insert all the locales belonging to one language
		 * into the combo box.
		 */
		g_assert(item->ref == NULL);
		item->ref = NULL;
		while (locale) {
			/*
			 * add every locale into the locale list and
			 * combo box and set the default locale of the
			 * default language as the default one.
			 */
			InstallationProfile.locales = g_list_append(
					InstallationProfile.locales, locale);
			if (orchestrator_om_locale_is_cposix(locale) ||
					orchestrator_om_locale_is_utf8(locale)) {
				gboolean valid;

				/*
				 * find out the right place
				 *  to insertthe new entry.
				 */
				valid = gtk_tree_model_get_iter_from_string(
					GTK_TREE_MODEL(LanguageWindow.store), &sibling, "1");
				while (valid) {
					locale_info_t *tmp_locale = NULL;
					gchar *desc = NULL;
					gchar *iter_desc = NULL;

					gtk_tree_model_get(GTK_TREE_MODEL(LanguageWindow.store),
											&sibling, 1, &tmp_locale, -1);
					desc = orchestrator_om_locale_get_desc(locale);
					iter_desc = orchestrator_om_locale_get_desc(tmp_locale);
					if (desc && iter_desc && strcmp(iter_desc, desc) > 0) {
						/*
						 * got a valid iter.
						 */
						valid = TRUE;
						break;
					}
					valid = gtk_tree_model_iter_next(
						GTK_TREE_MODEL(LanguageWindow.store), &sibling);
				}

				if (valid) {
					gtk_list_store_insert_before(LanguageWindow.store, &iter, &sibling);
				} else {
					gtk_list_store_append(LanguageWindow.store, &iter);
				}
				gtk_list_store_set(LanguageWindow.store, &iter,
						0, item, 1, locale, -1);
				if (orchestrator_om_language_is_default(item->language) &&
					orchestrator_om_locale_is_default(locale) &&
					LanguageWindow.defaultset == FALSE) {
					gtk_combo_box_set_active_iter(GTK_COMBO_BOX(
							LanguageWindow.default_combo), &iter);
					LanguageWindow.defaultset = TRUE;
				}

				/* save the GtkTreeRowReference */
				path = gtk_tree_model_get_path(GTK_TREE_MODEL(
								LanguageWindow.store), &iter);
				ref = gtk_tree_row_reference_new(GTK_TREE_MODEL(
								LanguageWindow.store), path);
				gtk_tree_path_free(path);
				item->ref = g_list_append(item->ref, ref);
			}
			locale = locale->next;
		}
	} else {
		gboolean setcposix = FALSE;
		GtkTreeIter activeiter;
		language_item *activeitem = NULL;
		locale_info_t *activelocale = NULL;

		locale_info_t *locale =
				orchestrator_om_language_get_locales(item->language);
		GtkTreePath *path;

		InstallationProfile.languages = g_list_remove(
					InstallationProfile.languages, item->language);

		gtk_combo_box_get_active_iter(GTK_COMBO_BOX(
		    LanguageWindow.default_combo),
		    &activeiter);
		gtk_tree_model_get(GTK_TREE_MODEL(LanguageWindow.store),
		    &activeiter, 0, &activeitem, 1, &activelocale, -1);

		/*
		 * Remove all the locales from the combo box. The
		 * locales should be already in the combo box.
		 */
		ref = item->ref;
		while (locale) {
			InstallationProfile.locales = g_list_remove(
						InstallationProfile.locales, locale);

			if (orchestrator_om_locale_is_cposix(locale) ||
					orchestrator_om_locale_is_utf8(locale)) {
				/* remove the entry and free GtkTreeRowReference */
				path = gtk_tree_row_reference_get_path(ref->data);
				gtk_tree_model_get_iter(GTK_TREE_MODEL(
							LanguageWindow.store), &iter, path);
				/* Check if locale matches the active locale in the combo box */
				if (strcmp(locale->locale_name, activelocale->locale_name) == 0)
					setcposix = TRUE;
				gtk_tree_path_free(path);
				gtk_list_store_remove(LanguageWindow.store, &iter);
				gtk_tree_row_reference_free(ref->data);

				ref = g_list_next(ref);
			}
			locale = locale->next;
		}
		g_list_free(item->ref);
		item->ref = NULL;
		if (setcposix == TRUE) {
			gtk_combo_box_set_active(GTK_COMBO_BOX(LanguageWindow.default_combo), 0);
		}
	}
}

static gboolean
on_focus_in_event(GtkToggleButton *button,
	GdkEventFocus *event,
	gpointer user_data)
{
	GtkAdjustment *adjustment = GTK_ADJUSTMENT(user_data);
	language_item *item;
	gfloat newvalue = 0.0;
	gfloat buttonval = 0.0;
	gfloat buttonposition = 0.0;
	gdouble value, lower, upper, pagesize;
	gfloat buttonsize;

	item = g_object_get_data(G_OBJECT(button), "item");

	g_object_get(G_OBJECT(adjustment), "value", &value, NULL);
	g_object_get(G_OBJECT(adjustment), "lower", &lower, NULL);
	g_object_get(G_OBJECT(adjustment), "upper", &upper, NULL);
	g_object_get(G_OBJECT(adjustment), "page-size", &pagesize, NULL);

	buttonsize = (gfloat)((upper - lower) / LanguageWindow.nlangs);
	buttonposition = (gfloat)item->index / LanguageWindow.nlangs;
	buttonval = buttonposition * (gfloat)(upper - lower);

	if (value+pagesize <= buttonval+buttonsize) {
		newvalue = buttonval + buttonsize - pagesize;
		gtk_adjustment_set_value(adjustment, (gdouble)newvalue);
		gtk_adjustment_value_changed(adjustment);
	} else if (value >= buttonval) {
		newvalue = buttonval;
		gtk_adjustment_set_value(adjustment, (gdouble)newvalue);
		gtk_adjustment_value_changed(adjustment);
	}
	return (FALSE);
}

void
on_default_combo_changed(GtkComboBox *combo, gpointer user_data)
{
	GtkTreeIter iter;
	language_item *item = NULL;
	locale_info_t *locale = NULL;

	gtk_combo_box_get_active_iter(combo, &iter);
	gtk_tree_model_get(GTK_TREE_MODEL(LanguageWindow.store),
		&iter, 0, &item, 1, &locale, -1);
	if (item) {
		/*
		 * a none cposix locale
		 * is selected.
		 */
		InstallationProfile.def_lang = item->language;
	} else
		InstallationProfile.def_lang = NULL;
	InstallationProfile.def_locale = locale;
	g_warning("default languge:%s",
		orchestrator_om_language_get_name(InstallationProfile.def_lang) ?
		orchestrator_om_language_get_name(InstallationProfile.def_lang) : "NULL");
	g_warning("default locale:%s",
		orchestrator_om_locale_get_name(InstallationProfile.def_locale));
}

static void
insert_cposix_locale(void)
{
	GtkTreeIter iter;

	/*
	 * insert C/POSIX into combobox
	 */
	gtk_list_store_append(LanguageWindow.store, &iter);
	gtk_list_store_set(LanguageWindow.store, &iter,
		0, NULL,
		1, orchestrator_om_locale_get_cposix(), -1);
	gtk_combo_box_set_active(GTK_COMBO_BOX(LanguageWindow.default_combo), 0);
}

static void
language_init(GtkWidget *widget)
{
	GtkAdjustment *adjustment;
	GtkWidget *def_check = NULL;
	GList *list = NULL;
	GList *l = NULL;
	int i;

	InstallationProfile.languages = NULL;
	InstallationProfile.locales = NULL;

	LanguageWindow.defaultset = FALSE;
	orchestrator_om_get_available_languages(&list, &LanguageWindow.nlangs);
	LanguageWindow.langs = g_new0(language_item, LanguageWindow.nlangs);
	if (!LanguageWindow.langs) {
		g_warning("not enough memory");
		return;
	}

	adjustment = gtk_scrolled_window_get_vadjustment
					(GTK_SCROLLED_WINDOW(LanguageWindow.lang_scrolled));
	i = 0;
	l = list;
	while (l) {
		lang_info_t *info = l->data;
		GtkWidget *check;
		GtkWidget *label;
		char *markup;

		g_assert(i < LanguageWindow.nlangs);
		LanguageWindow.langs[i].language = info;
		LanguageWindow.langs[i].index = i;
		LanguageWindow.langs[i].language = info;

		label = gtk_label_new(NULL);
		markup = g_markup_printf_escaped(
					"<span font_desc=\"Arial Bold\">%s</span>",
					orchestrator_om_language_get_name(info));
		gtk_label_set_markup(GTK_LABEL(label), markup);
		g_free(markup);

		check = gtk_check_button_new();
		g_object_set_data(G_OBJECT(check), "item",
				&LanguageWindow.langs[i]);
		g_signal_connect(G_OBJECT(check), "toggled",
				G_CALLBACK(on_language_toggled), NULL);
		g_signal_connect(G_OBJECT(check), "focus-in-event",
			G_CALLBACK(on_focus_in_event), adjustment);
		gtk_container_add(GTK_CONTAINER(check), label);
		gtk_box_pack_start(GTK_BOX(widget), check, TRUE, TRUE, 0);
		LanguageWindow.langs[i].check = check;

		/*
		 * FIXME:
		 * English is active by default
		 */
		if (orchestrator_om_language_is_default(info)) {
			def_check = check;
		}

		l = g_list_next(l);
		i++;
	}

	insert_cposix_locale();
	if (def_check)
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(def_check), TRUE);
	g_list_free(list);

}

void
on_all_button_clicked(GtkButton *button, gpointer user_data)
{
	for (gint i = 0; i < LanguageWindow.nlangs; i++) {
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
				LanguageWindow.langs[i].check), TRUE);
	}
}

void
on_deall_button_clicked(GtkButton *button, gpointer user_data)
{
	for (gint i = 0; i < LanguageWindow.nlangs; i++) {
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
				LanguageWindow.langs[i].check), FALSE);
	}
	/*
	 * set default locale
	 * to C/Posix.
	 */
	gtk_combo_box_set_active(GTK_COMBO_BOX(LanguageWindow.default_combo), 0);
}

void
on_reset_button_clicked(GtkButton *button, gpointer user_data)
{
	for (gint i = 0; i < LanguageWindow.nlangs; i++) {
		if (!orchestrator_om_language_is_default(
				LanguageWindow.langs[i].language)) {
			gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
					LanguageWindow.langs[i].check), FALSE);
		} else {
			gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
					LanguageWindow.langs[i].check), TRUE);
		}
	}
}

void
set_select_languages()
{
}

static void
render_locale_name(GtkCellLayout *layout,
			GtkCellRenderer *cell,
			GtkTreeModel *model,
			GtkTreeIter *iter,
			gpointer user_data)
{
	language_item *item = NULL;
	locale_info_t *locale = NULL;
	gchar *text = NULL;

	gtk_tree_model_get(model, iter, 0, &item, 1, &locale, -1);
	if (locale != NULL) {
		text = g_strdup(orchestrator_om_locale_get_desc(locale));
		g_object_set(cell, "text", text, NULL);
		g_free(text);
	}
}

GtkWidget *
language_screen_init(GladeXML *winxml)
{
	GtkWidget *widget;
	GdkColor  backcolour;

	glade_xml_signal_autoconnect(winxml);

	widget = glade_xml_get_widget(winxml, "languagewindowtable");

	LanguageWindow.default_combo =
		glade_xml_get_widget(winxml, "default_combo");
	LanguageWindow.store =
		gtk_list_store_new(2, G_TYPE_POINTER, G_TYPE_POINTER);
	LanguageWindow.renderer = gtk_cell_renderer_text_new();
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(LanguageWindow.default_combo),
		LanguageWindow.renderer, TRUE);
	gtk_cell_layout_set_cell_data_func(GTK_CELL_LAYOUT(
			LanguageWindow.default_combo), LanguageWindow.renderer,
			render_locale_name, NULL, NULL);
	gtk_combo_box_set_model(GTK_COMBO_BOX(LanguageWindow.default_combo),
			GTK_TREE_MODEL(LanguageWindow.store));
	g_object_unref(LanguageWindow.store);
	g_signal_connect(G_OBJECT(LanguageWindow.default_combo), "changed",
			G_CALLBACK(on_default_combo_changed), NULL);

	LanguageWindow.lang_scrolled = glade_xml_get_widget(winxml, "language_scroll");

	LanguageWindow.lang_vbox = glade_xml_get_widget(winxml, "language_vbox");
	language_init(LanguageWindow.lang_vbox);

	LanguageWindow.lang_viewport =
		glade_xml_get_widget(winxml, "language_viewport");
	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(LanguageWindow.lang_viewport,
			GTK_STATE_NORMAL, &backcolour);
	gtk_widget_show_all(widget);

	return (widget);
}

void
language_cleanup(void)
{
	gint i = 0;

	for (i = 0; i < LanguageWindow.nlangs; i++) {
		GList *l = LanguageWindow.langs[i].ref;

		while (l) {
			/* free tree row reference */
			gtk_tree_row_reference_free(l->data);
			l = g_list_next(l);
		}
		/* free reference list */
		g_list_free(LanguageWindow.langs[i].ref);
	}
	/* free lang_info_t */
	orchestrator_om_free_language(LanguageWindow.langs[0].language);
	g_free(LanguageWindow.langs);
}

static gint
compare_language_strings(gconstpointer a, gconstpointer b)
{
	/*
	 * Returns negative if a < b
	 * Returns positive if a > b
	 * Returns 0 if a == b
	 */
	return ((gint)strcoll((const char *)a, (const char *)b));
}

void
construct_language_string(gchar **str,
				gboolean include_CR,
				gchar delimeter)
{
	GList *lang_list = NULL;
	GList *sorted_lang_list = NULL;
	GList *tmp_lang_list = NULL;
	gint len = 0;
	gint i = 0;
	lang_info_t *info;
	gchar *tmpStr;

	/* Sort lang_list into sorted_lang_list */

	/* Generate list of language strings for sorting */
	tmp_lang_list = InstallationProfile.languages;
	while (tmp_lang_list) {
		info = tmp_lang_list->data;
		lang_list =
			g_list_append(lang_list,
				g_strdup(orchestrator_om_language_get_name(info)));
		tmp_lang_list = g_list_next(tmp_lang_list);
	}

	/* Sort lang_list into sorted_lang_list */
	sorted_lang_list = g_list_sort(lang_list, compare_language_strings);

	while (sorted_lang_list) {
		if (*str) {
			if (include_CR) {
				len = strlen(*str + i);
				if (len > MAX_LANG_STR_LEN) {
					i = i + len;
					if (g_list_next(sorted_lang_list)) {
						tmpStr =
							g_strdup_printf(_("%s%c\n%s,"),
								*str, delimeter,
								sorted_lang_list->data);
					} else {
						tmpStr =
							g_strdup_printf(_("%s%c\n%s"),
								*str, delimeter,
								sorted_lang_list->data);
					}
				} else {
					if (g_list_next(sorted_lang_list)) {
						tmpStr =
							g_strdup_printf(_("%s%c%s,"),
								*str, delimeter,
								sorted_lang_list->data);
					} else {
						tmpStr =
							g_strdup_printf(_("%s%c%s"),
								*str, delimeter,
								sorted_lang_list->data);
					}
				}
			} else {
				tmpStr =
					g_strdup_printf(_("%s%c%s"),
						*str, delimeter,
						sorted_lang_list->data);
			}
			g_free(*str);
		} else {
				tmpStr = g_strdup_printf(_("%s"), sorted_lang_list->data);
		}
		*str = tmpStr;

		sorted_lang_list = g_list_next(sorted_lang_list);
	}

	/* Free up strdup'd language strings */
	tmp_lang_list = lang_list;
	while (tmp_lang_list) {
		g_free(tmp_lang_list->data);
		tmp_lang_list = g_list_next(tmp_lang_list);
	}
}

void
construct_locale_string(gchar **str,
				gboolean include_CR,
				gchar delimeter)
{
	GList *lang_list;
	gint len = 0;
	gint i = 0;

	lang_list = InstallationProfile.locales;
	while (lang_list) {
		locale_info_t *info;
		gchar *tmpStr;

		info = lang_list->data;
		if (*str) {
			if (include_CR) {
				len = strlen(*str + i);
				if (len > MAX_LANG_STR_LEN) {
					tmpStr = g_strdup_printf(_("%s\n"), *str);
					i = i + len;
				} else {
					if (g_list_next(lang_list))
						tmpStr = g_strdup_printf(_("%s%c%s,"), *str, delimeter,
									orchestrator_om_locale_get_name(info));
					else
						tmpStr = g_strdup_printf(_("%s%c%s"), *str, delimeter,
									orchestrator_om_locale_get_name(info));
				}
			} else {
				tmpStr = g_strdup_printf(_("%s%c%s"), *str, delimeter,
									orchestrator_om_locale_get_name(info));
			}
			g_free(*str);
		} else {
				tmpStr = g_strdup_printf(_("%s"),
									orchestrator_om_locale_get_name(info));
		}
		*str = tmpStr;

		lang_list = g_list_next(lang_list);
	}
}
