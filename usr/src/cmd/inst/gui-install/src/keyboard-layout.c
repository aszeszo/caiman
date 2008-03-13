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
#pragma ident	"@(#)keyboard-layout.c	1.1	07/08/03 SMI"

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>
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
#define	THIS_PACKAGE_NAME	"keyboard-layout"

#define	FILENAME "keyboard-layout.glade"
#define	ROOTNODE "mainwindow"
#define	APP_NAME "gui-install"

typedef struct _MainWindowXML {
	GladeXML *mainwindowxml;

	GtkWidget *mainwindow;
	GtkWidget *okbutton;
	GSList *kbd_layouts;
	GList *layouts;
	keyboard_type_t *selected_layout;
} MainWindowXML;

MainWindowXML MainWindow;
pid_t pid;

static void
mainwindow_xml_init()
{
	MainWindow.kbd_layouts = NULL;
	MainWindow.okbutton = NULL;

	MainWindow.mainwindowxml =
		glade_xml_new(GLADEDIR "/" FILENAME, ROOTNODE, NULL);

	if (!MainWindow.mainwindowxml) {
		g_critical("something went wrong creating the GUI");
		exit(-1);
	}

	MainWindow.okbutton =
		glade_xml_get_widget(MainWindow.mainwindowxml, "okbutton");
}

void
keyboard_cleanup(void)
{
	g_slist_free(MainWindow.kbd_layouts);
	g_list_free(MainWindow.layouts);
}

/* Makes the scrollbar and viewport adjust to follow the focussed button */
static gboolean
button_focus_handler(GtkRadioButton *button,
	GdkEventFocus *event,
	gpointer user_data)
{
	GtkAdjustment *adjustment = GTK_ADJUSTMENT(user_data);
	gint index = 0;
	gint numbuttons = 1;
	gfloat newvalue = 0.0;
	gfloat buttonval = 0.0;
	gfloat buttonposition = 0.0;
	gdouble value, lower, upper, pagesize;
	gfloat buttonsize;

	index = g_slist_index(MainWindow.kbd_layouts, button);
	numbuttons = g_slist_length(MainWindow.kbd_layouts);

	g_object_get(G_OBJECT(adjustment), "value", &value, NULL);
	g_object_get(G_OBJECT(adjustment), "lower", &lower, NULL);
	g_object_get(G_OBJECT(adjustment), "upper", &upper, NULL);
	g_object_get(G_OBJECT(adjustment), "page-size", &pagesize, NULL);

	/* double precision is too expensive and overkill - use float */
	buttonsize = (gfloat)((upper - lower)/numbuttons);
	buttonposition = (gfloat)index / numbuttons;
	buttonval = buttonposition * (gfloat)(upper - lower);

	/*
	 * Increment scrolling adjustment just enough to keep
	 * the button visible in the viewport
	 */
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

static void
on_radio_toggled(GtkRadioButton *radio, gpointer user_data)
{
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(radio))) {
		MainWindow.selected_layout =
			(keyboard_type_t *)g_object_get_data(G_OBJECT(radio), "keyboard");
	}
}

static void
mainwindow_ui_init()
{
	GtkWidget *scrollwindow;
	GtkWidget *english;

#ifdef MAKE_EVERYTHING_WHITE
	GdkColor  backcolour;
	GtkWidget *viewport;
#endif

	glade_xml_signal_autoconnect(MainWindow.mainwindowxml);
	MainWindow.mainwindow = glade_xml_get_widget(MainWindow.mainwindowxml, "mainwindow");

	/* create keyboard layout vbox */
	if (MainWindow.layouts) {
		GtkWidget *layout_vbox;
		GtkWidget *radio;
		GtkAdjustment *adjustment;
		GSList *group = NULL;
		GList *layouts = MainWindow.layouts;
		keyboard_type_t *type;

		layout_vbox =
			glade_xml_get_widget(MainWindow.mainwindowxml, "layout_vbox");
		scrollwindow =
			glade_xml_get_widget(MainWindow.mainwindowxml, "keyboard_scroll");
		adjustment = gtk_scrolled_window_get_vadjustment
						(GTK_SCROLLED_WINDOW(scrollwindow));
		while (layouts) {
			type = (keyboard_type_t *)layouts->data;
			radio = gtk_radio_button_new_with_label(
						NULL, orchestrator_om_keyboard_get_name(type));
			g_object_set_data(G_OBJECT(radio), "keyboard", type);
			g_signal_connect(G_OBJECT(radio),
			    "toggled",
			    G_CALLBACK(on_radio_toggled),
			    NULL);
			g_signal_connect(G_OBJECT(radio),
			    "focus-in-event",
			    G_CALLBACK(button_focus_handler),
			    adjustment);

			gtk_radio_button_set_group(GTK_RADIO_BUTTON(radio), group);
			group = gtk_radio_button_get_group(GTK_RADIO_BUTTON(radio));
			gtk_box_pack_start(GTK_BOX(layout_vbox), radio, TRUE, TRUE, 2);
			MainWindow.kbd_layouts =
					g_slist_append(MainWindow.kbd_layouts, radio);
			/* 33 means English-US => default */
			if (orchestrator_om_keyboard_get_num(type) == 33)
				english = radio;

			layouts = g_list_next(layouts);
		}
		gtk_widget_show_all(layout_vbox);
		MainWindow.selected_layout =
				(keyboard_type_t *)MainWindow.layouts->data;
	} else {
		g_warning("Can not get keyboard layout");
	}

/*
 * The main installer overrides the background window colour to white.
 * If it's decided that this dialog has to be white also then enable
 * this block of code. For now, standard look and feel.
 */
#ifdef MAKE_EVERYTHING_WHITE
	viewport =
		glade_xml_get_widget(MainWindow.mainwindowxml, "keyboard_viewport");
	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_realize(scrollwindow);
	gtk_widget_modify_bg(viewport, GTK_STATE_NORMAL, &backcolour);
	gtk_widget_modify_bg(gtk_scrolled_window_get_vscrollbar(
							GTK_SCROLLED_WINDOW(scrollwindow)),
							GTK_STATE_NORMAL, &backcolour);
	gtk_widget_modify_bg(gtk_scrolled_window_get_hscrollbar(
							GTK_SCROLLED_WINDOW(scrollwindow)),
							GTK_STATE_NORMAL, &backcolour);
#endif
	/*
	 * activate the radio button after the scrolled window
	 * has been realized and focus it to set the scrolling right.
	 */
	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(english), TRUE);
	gtk_widget_grab_focus(english);
}

void
on_okbutton_clicked(GtkButton *button, gpointer user_data)
{
	if (MainWindow.selected_layout) {
		g_debug("Selected keyboard layout: %s",
		    orchestrator_om_keyboard_get_name(MainWindow.selected_layout));
		orchestrator_om_set_keyboard_type(MainWindow.selected_layout);
	}

	gtk_widget_destroy(MainWindow.mainwindow);
	g_object_unref(MainWindow.mainwindowxml);

	/* Signal gui-install that it should display the UI now */
	kill(pid, SIGUSR1);
	gtk_main_quit();
}

void
call_gui_install(gboolean waitforsignal)
{
	char *prog_path = NULL;

	prog_path = g_find_program_in_path(APP_NAME);
	if (prog_path) {
		g_debug("%s path: %s", APP_NAME, prog_path);

		if ((pid = fork()) < 0) {
			g_critical("fork failed");
			exit(-1);
		}
		if (pid == 0) {
			/* Child */
			if (waitforsignal == TRUE)
				execl(prog_path, APP_NAME, "-w", "--disable-crash-dialog", NULL);
			else
				execl(prog_path, APP_NAME, "--disable-crash-dialog", NULL);
			/* Shouldn't get here */
			exit(-1);
		}
	} else
		g_critical("Can not find %s command!", APP_NAME);
}

gboolean
init_kbd_type()
{
	gint ret;
	gint total;

	ret = orchestrator_om_get_keyboard_type(&MainWindow.layouts, &total);
	if (ret == OM_SUCCESS) {
		return (TRUE);
	} else if (ret == OM_FAILURE) {
		g_warning("Failed to get keyboard type from orchestrator: OM_FAILURE");
		return (FALSE);
	} else {
		/* keyboard layout has been set, do noting */
		return (FALSE);
	}
}

int
main(int argc, char *argv[])
{
	int guistatus = 0;
#ifdef ENABLE_NLS
	bindtextdomain(THIS_PACKAGE_NAME, PACKAGE_LOCALE_DIR);
	bind_textdomain_codeset(THIS_PACKAGE_NAME, "UTF-8");
	textdomain(THIS_PACKAGE_NAME);
#endif
	gui_error_logging_init(THIS_PACKAGE_NAME);
	if (orchestrator_om_keyboard_is_self_id() == TRUE) {
		g_log("", G_LOG_LEVEL_DEBUG, "Keyboard is self identifying");
		call_gui_install(FALSE);
	} else {
		call_gui_install(TRUE);
		gnome_program_init(THIS_PACKAGE_NAME, VERSION, LIBGNOMEUI_MODULE,
					argc, argv,
					GNOME_PARAM_APP_DATADIR, PACKAGE_DATA_DIR,
					NULL);
		glade_init();

		if (init_kbd_type() == TRUE) {
			mainwindow_xml_init();
			mainwindow_ui_init();

			gtk_widget_show(glade_xml_get_widget(MainWindow.mainwindowxml,
						"mainwindow"));
			gtk_main();
			keyboard_cleanup();
		}
	}
	/*
	 * Wait for gui-install to exit before returning.
	 * Prevents breakage of the calling script which
	 * assumes only 1 process
	 */
	waitpid(pid, &guistatus, 0);

	if (WIFEXITED(guistatus)) {
		int exitval = WEXITSTATUS(guistatus);

		/*
		 * If exit value is > 128, then subract 256 to make it look like a
		 * negative number. WEXITSTATUS ignores the sign of the 8th bit.
		 */
		if (exitval > 128)
			exitval -= 256;
		g_debug("%s exit status: %d", APP_NAME, exitval);
		exit(exitval);
	} else if (WCOREDUMP(guistatus)) {
		g_warning("%s appears to have core dumped", APP_NAME);
	}
	exit(-1);
}
