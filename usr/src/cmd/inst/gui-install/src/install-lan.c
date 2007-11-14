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
#pragma ident	"@(#)install-lan.c	1.2	07/08/22 SMI"

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <gtk/gtk.h>
#include <gnome.h>
#include <glade/glade.h>
#include "error-logging.h"
#include "orchestrator-wrappers.h"

/*
 * Used to set gettext domain for message translation
 * catalogs and for registration of the program name
 * in gnome_program_init()
 */
#define	THIS_PACKAGE_NAME	"install-lan"

#define	FILENAME "install-lan.glade"
#define	ROOTNODE "mainwindow"
#define	APP_NAME "keyboard-layout"

typedef struct _MainWindowXML {
	GladeXML *mainwindowxml;

	GtkWidget *mainwindow;
	GtkWidget *okbutton;
	GtkWidget *lang_vbox;
	GList *radios;

	GList *langs;
	gint nlang;

	lang_info_t *selected;

} MainWindowXML;

MainWindowXML MainWindow;

static void
mainwindow_xml_init()
{
	MainWindow.mainwindowxml =
		glade_xml_new(GLADEDIR "/" FILENAME, ROOTNODE, NULL);

	if (!MainWindow.mainwindowxml) {
		g_warning("something went wrong creating the GUI");
		exit(-1);
	}

	MainWindow.okbutton =
		glade_xml_get_widget(MainWindow.mainwindowxml, "okbutton");
	MainWindow.lang_vbox =
		glade_xml_get_widget(MainWindow.mainwindowxml, "languagevbox");
}

static void
on_radio_toggled(GtkRadioButton *radio, gpointer user_data)
{
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(radio))) {
		g_debug("%s", ((lang_info_t *)user_data)->lang);
		MainWindow.selected = (lang_info_t *)user_data;
	}
}

static void
mainwindow_ui_init()
{
	GList *l = NULL;
	GSList *group = NULL;

	glade_xml_signal_autoconnect(MainWindow.mainwindowxml);

	MainWindow.mainwindow = glade_xml_get_widget(MainWindow.mainwindowxml, "mainwindow");

	orchestrator_om_get_install_languages(&MainWindow.langs, &MainWindow.nlang);
	l = MainWindow.langs;
	while (l) {
		lang_info_t *info;
		GtkWidget *radio;

		info = l->data;
		radio = gtk_radio_button_new_with_label(group,
					_(orchestrator_om_language_get_name(info)));
		g_debug("Adding Language: %s", orchestrator_om_language_get_name(info));
		g_signal_connect(G_OBJECT(radio), "toggled",
					G_CALLBACK(on_radio_toggled), info);
		group = gtk_radio_button_get_group(GTK_RADIO_BUTTON(radio));
		gtk_box_pack_start(GTK_BOX(MainWindow.lang_vbox), radio, TRUE, TRUE, 0);
		if (orchestrator_om_language_is_default(info))
			gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(radio), TRUE);

		MainWindow.radios = g_list_append(MainWindow.radios, radio);
		l = g_list_next(l);
	}
	/*
	 * if no defualt language
	 * use the 1st one
	 */
	if (!MainWindow.selected && MainWindow.langs)
		MainWindow.selected = MainWindow.langs->data;
	gtk_widget_show_all(MainWindow.lang_vbox);
}

void
mainwindow_cleanup(void)
{
	/* free lang_info_t */
	orchestrator_om_free_language(MainWindow.langs->data);
	g_list_free(MainWindow.langs);
	g_list_free(MainWindow.radios);
}

void
on_okbutton_clicked(GtkButton *button, gpointer user_data)
{
	gchar *prog_path = NULL;

	if (!MainWindow.selected) {
		g_warning("OK button clicked but no language is selected");
		return;
	}
	orchestrator_om_set_install_lang_by_value(MainWindow.selected);

	prog_path = g_find_program_in_path(APP_NAME);
	if (prog_path) {
		gtk_widget_destroy(MainWindow.mainwindow);
		g_object_unref(MainWindow.mainwindowxml);
		g_debug("%s path: %s", APP_NAME, prog_path);

		execl(prog_path, APP_NAME, NULL);
		g_critical("Failed to exec %s", prog_path);
		exit(-1);
	} else {
		g_warning("Can not find %s command!", APP_NAME);
		exit(-1);
	}
}

int
main(int argc, char *argv[])
{
#ifdef ENABLE_NLS
	bindtextdomain(THIS_PACKAGE_NAME, PACKAGE_LOCALE_DIR);
	bind_textdomain_codeset(THIS_PACKAGE_NAME, "UTF-8");
	textdomain(THIS_PACKAGE_NAME);
#endif

	gui_error_logging_init(THIS_PACKAGE_NAME);
	gnome_program_init(THIS_PACKAGE_NAME, VERSION, LIBGNOMEUI_MODULE,
					argc, argv,
					GNOME_PARAM_APP_DATADIR, PACKAGE_DATA_DIR,
					NULL);
	glade_init();
	mainwindow_xml_init();
	mainwindow_ui_init();

	gtk_widget_show(MainWindow.mainwindow);
	gtk_main();
	mainwindow_cleanup();
	return (0);
}
