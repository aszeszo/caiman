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

#include <glib/gi18n.h>
#include <gtk/gtk.h>
#include <gdk/gdkkeysyms.h>
#include <string.h>
#include "installation-profile.h"
#include "interface-globals.h"
#include "window-graphics.h"
#include "language-screen.h"

typedef struct _language_item {
	gint index;
	gchar *markup;
	lang_info_t *language;
	GtkWidget *button;
	/*
	 * the list storing the
	 * GtkTreeRowReference
	 */
	GList *refs;
} language_item;

typedef struct _LanguageWindowXML {
	GtkWidget *lang_scrolled;
	GtkWidget *language_tree;
	GtkWidget *default_combo;
	GtkWidget *default_entry;
	GtkCellRenderer *renderer;
	GtkListStore *locale_store;
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

static gchar *
get_locale_desc(locale_info_t *locale)
{
	gchar *text = NULL;
	gchar *str = NULL;

	if (locale != NULL) {
		text = g_strdup(orchestrator_om_locale_get_desc(locale));
		if (text) {
			gchar *left;
			gchar *right;

			left = strrchr(text, '(');
			if (left) {
				right = strrchr(left + 1, ')');
				*right = 0;
				str = g_strdup(left + 1);
			} else
				str = g_strdup(text);
		}
		g_free(text);
	}

	return str;
}

void
on_language_selected(language_item *item)
{
	locale_info_t *locale =
		orchestrator_om_language_get_locales(item->language);

	if (item->refs)
		return;

	InstallationProfile.languages = g_list_append(
			InstallationProfile.languages, item->language);
	/*
	 * Insert all the locales belonging to one language
	 * into the combo box.
	 */
	item->refs = NULL;
	LanguageWindow.defaultset = FALSE;
	while (locale) {
		GtkTreeRowReference *ref = NULL;
		GtkTreeIter iter;
		GtkTreePath *path;

		/*
		 * add every locale into the locale list and
		 * combo box and set the default locale of the
		 * default language as the default one.
		 */
		InstallationProfile.locales = g_list_append(
				InstallationProfile.locales, locale);
		if (orchestrator_om_locale_is_cposix(locale) ||
				orchestrator_om_locale_is_utf8(locale)) {
			gchar *text = get_locale_desc(locale);

			gtk_list_store_append(LanguageWindow.locale_store, &iter);
			gtk_list_store_set(LanguageWindow.locale_store, &iter,
					0, item, 1, locale, 2, text, -1);
			g_free(text);
			if (orchestrator_om_locale_is_default(locale) &&
					LanguageWindow.defaultset == FALSE) {
				gtk_combo_box_set_active_iter(GTK_COMBO_BOX(
							LanguageWindow.default_combo), &iter);
				LanguageWindow.defaultset = TRUE;
			}

			/* save the GtkTreeRowReference */
			path = gtk_tree_model_get_path(GTK_TREE_MODEL(
						LanguageWindow.locale_store), &iter);
			ref = gtk_tree_row_reference_new(GTK_TREE_MODEL(
						LanguageWindow.locale_store), path);
			gtk_tree_path_free(path);
			item->refs = g_list_append(item->refs, ref);
		}
		locale = locale->next;
	}
	if (!LanguageWindow.defaultset) {
		gtk_combo_box_set_active(GTK_COMBO_BOX(
					LanguageWindow.default_combo), 0);
	}
}

void
on_language_unselected(language_item *item)
{
	locale_info_t *locale =
			orchestrator_om_language_get_locales(item->language);
	GList *refs = NULL;

	if (!item->refs)
		return;

	InstallationProfile.languages = g_list_remove(
				InstallationProfile.languages, item->language);

	/*
	 * Remove all the locales from the combo box. The
	 * locales should be already in the combo box.
	 */
	refs = item->refs;
	while (locale) {
		GtkTreePath *path;
		GtkTreeIter iter;
		gboolean valid;

		InstallationProfile.locales = g_list_remove(
					InstallationProfile.locales, locale);

		if (orchestrator_om_locale_is_cposix(locale) ||
				orchestrator_om_locale_is_utf8(locale)) {
			/* remove the entry and free GtkTreeRowReference */
			path = gtk_tree_row_reference_get_path(refs->data);
			valid = gtk_tree_model_get_iter(GTK_TREE_MODEL(
						LanguageWindow.locale_store), &iter, path);
			if (!valid) {
				continue;
			}
			gtk_tree_path_free(path);
			gtk_list_store_remove(LanguageWindow.locale_store, &iter);
			gtk_tree_row_reference_free(refs->data);

			refs = g_list_next(refs);
		}
		locale = locale->next;
	}
	g_list_free(item->refs);
	item->refs = NULL;
}

gboolean
language_selection_func (GtkTreeSelection *selection,
		GtkTreeModel     *model,
		GtkTreePath      *path,
		gboolean          path_currently_selected,
		gpointer          user_data)
{
	GtkAdjustment *adjustment = GTK_ADJUSTMENT(user_data);
	static language_item *old_item = NULL;
	GtkTreeIter iter;

	if (gtk_tree_model_get_iter(model, &iter, path)) {
		language_item *new_item;

		gtk_tree_model_get(model, &iter, 0, &new_item, -1);
		if (!path_currently_selected) {
			if (old_item) {
				on_language_unselected(old_item);
			}

			on_language_selected(new_item);
			old_item = new_item;
		}
	}

	return TRUE;
}

void
on_default_combo_changed(GtkComboBox *combo, gpointer user_data)
{
	locale_info_t *locale = NULL;
	GtkTreeIter iter;
	gboolean valid;

	valid = gtk_combo_box_get_active_iter(combo, &iter);
	if (!valid) {
		return;
	}
	gtk_tree_model_get(GTK_TREE_MODEL(LanguageWindow.locale_store),
		&iter, 1, &locale, -1);
	InstallationProfile.def_locale = locale;
}

static void
language_init(GtkWidget *treeview)
{
	static GtkWidget *first_button = NULL;
	GtkWidget *button;
	GtkListStore *liststore;
	GtkTreeIter iter;
	GtkTreeSelection *selection;
	GList *list = NULL;
	GList *l = NULL;
	gint def_button;
	gint i;

	InstallationProfile.languages = NULL;
	InstallationProfile.locales = NULL;

	selection = gtk_tree_view_get_selection(GTK_TREE_VIEW(LanguageWindow.language_tree));
	LanguageWindow.defaultset = FALSE;
	orchestrator_om_get_available_languages(&list, &LanguageWindow.nlangs);
	LanguageWindow.langs = g_new0(language_item, LanguageWindow.nlangs);
	if (!LanguageWindow.langs) {
		g_warning("not enough memory");
		return;
	}

	liststore = GTK_LIST_STORE(gtk_tree_view_get_model(GTK_TREE_VIEW(treeview)));
	i = 0;
	l = list;
	while (l) {
		lang_info_t *info = l->data;
		char *markup;

		g_assert(i < LanguageWindow.nlangs);
		LanguageWindow.langs[i].language = info;
		LanguageWindow.langs[i].index = i;

		LanguageWindow.langs[i].markup = g_markup_printf_escaped(
				"<span font_desc=\"Arial Bold\">%s</span>",
				orchestrator_om_language_get_name(info));
		gtk_list_store_append(liststore, &iter);
		gtk_list_store_set(liststore, &iter,
				0, &LanguageWindow.langs[i],
				-1);

		if (orchestrator_om_language_is_default(info)) {
			gtk_tree_selection_select_iter(selection, &iter);
		}

		l = g_list_next(l);
		i++;
	}
	g_list_free(list);
}

void
set_select_languages()
{
}

static void
render_language_text(GtkTreeViewColumn *column,
		GtkCellRenderer *cell,
		GtkTreeModel *model,
		GtkTreeIter *iter,
		gpointer user_data)
{
	language_item *item;
	gchar *text = NULL;

	gtk_tree_model_get(model, iter, 0, &item, -1);
	if (item != NULL) {
		text = g_strdup(item->markup);
		g_object_set(cell, "markup", text, NULL);
		g_free(text);
	}
}

GtkWidget *
language_screen_init(GladeXML *winxml)
{
	GtkWidget *widget;
	GtkListStore *liststore;
	GtkCellRenderer *renderer;
	GtkTreeViewColumn *col;
	GtkTreeSelection *selection;
	GtkAdjustment *adjustment;

	glade_xml_signal_autoconnect(winxml);

	widget = glade_xml_get_widget(winxml, "languagewindowtable");

	LanguageWindow.default_combo =
		glade_xml_get_widget(winxml, "default_combo");
	LanguageWindow.locale_store =
		gtk_list_store_new(3, G_TYPE_POINTER, G_TYPE_POINTER, G_TYPE_STRING);
	LanguageWindow.renderer = gtk_cell_renderer_text_new();
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(LanguageWindow.default_combo),
		LanguageWindow.renderer, TRUE);
	gtk_cell_layout_set_attributes (GTK_CELL_LAYOUT (
			LanguageWindow.default_combo),
			LanguageWindow.renderer, "text", 2, NULL);
	gtk_combo_box_set_model(GTK_COMBO_BOX(LanguageWindow.default_combo),
			GTK_TREE_MODEL(LanguageWindow.locale_store));
	g_object_unref(LanguageWindow.locale_store);
	g_signal_connect(G_OBJECT(LanguageWindow.default_combo), "changed",
			G_CALLBACK(on_default_combo_changed), NULL);

	LanguageWindow.lang_scrolled = glade_xml_get_widget(winxml, "language_scroll");
	adjustment = gtk_scrolled_window_get_vadjustment
					(GTK_SCROLLED_WINDOW(LanguageWindow.lang_scrolled));

	LanguageWindow.language_tree = glade_xml_get_widget(winxml, "language_tree");
	liststore = gtk_list_store_new(1, G_TYPE_POINTER);
	gtk_tree_view_set_model(GTK_TREE_VIEW(LanguageWindow.language_tree),
			GTK_TREE_MODEL(liststore));
	g_object_unref(liststore);

	selection = gtk_tree_view_get_selection(GTK_TREE_VIEW(LanguageWindow.language_tree));
	gtk_tree_selection_set_mode(selection, GTK_SELECTION_BROWSE);
	gtk_tree_selection_set_select_function(selection, language_selection_func, adjustment, NULL);

	col = gtk_tree_view_column_new();
	renderer = gtk_cell_renderer_text_new();
	gtk_tree_view_column_pack_start(col, renderer, FALSE);
	gtk_tree_view_column_set_cell_data_func (col, renderer, render_language_text, NULL, NULL);
	gtk_tree_view_append_column(GTK_TREE_VIEW(LanguageWindow.language_tree), col);
	gtk_tree_view_set_headers_visible(GTK_TREE_VIEW(LanguageWindow.language_tree),
			FALSE);
	language_init(LanguageWindow.language_tree);

	gtk_widget_show_all(widget);

	return (widget);
}

void
language_cleanup(void)
{
	gint i = 0;

	for (i = 0; i < LanguageWindow.nlangs; i++) {
		GList *l = LanguageWindow.langs[i].refs;

		while (l) {
			/* free tree row reference */
			gtk_tree_row_reference_free(l->data);
			l = g_list_next(l);
		}
		/* free reference list */
		g_list_free(LanguageWindow.langs[i].refs);
		g_free(LanguageWindow.langs[0].markup);
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
