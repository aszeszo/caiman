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
#pragma ident	"@(#)diskbutton.c	1.2	07/08/23 SMI"

#include <glib/gi18n.h>
#include <gtk/gtk.h>
#include <pixbufs.h>
#include <strings.h>
#include "interface-globals.h"
#include "window-graphics.h"
#include "diskbutton.h"

#define	DISKBUTTON_FILENAME "diskbutton.glade"
#define	DISKBUTTON_NODE "diskbutton_vbox"
#define	SYSTEMENTRY_NODE "entry_hbox"

struct _DiskButtonPrivate
{
	/* the list of radio buttons */
	GList *radios;

	GtkWidget *image;
	GtkWidget *system_vbox;
	GtkWidget *disk_label;
	GtkWidget *boot_label;
	GtkWidget *nofound_label;
	GtkWidget *disk_eventbox;
	GtkTooltips *tooltip;
	GtkWidget *bar;

	disk_info_t *disk;
	upgrade_info_t *instances;
	gint ninstance;
};

disk_info_t *selected_disk;
upgrade_info_t *selected_instance;

GObjectClass *parent_class = NULL;

static void disk_button_class_init(DiskButtonClass *klass);
static void disk_button_init(DiskButton *button);
static void disk_button_dispose(GObject *object);

G_DEFINE_TYPE(DiskButton, disk_button, GTK_TYPE_HBOX)

/*
 * The order of error messages must be the
 * same as the corresponding error code.
 */
static const gchar *error_messages[] =
{
	N_("Unknown error."),
	N_("The instance is a mirror."),
	N_("Contains a misconfigured non-global zone."),
	N_("This release is not supported."),
	N_("The release information is missing."),
	N_("The instance is incomplete."),
	N_("Root fs is corrupted."),
	N_("Failed to mount root."),
	N_("Failed to mount var."),
	N_("Cluster file is missing."),
	N_("Clustertoc file is missing."),
	N_("Bootenvrc file is missing."),
	N_("Meta cluster is wrong.")
};


static void
disk_button_class_init(DiskButtonClass *klass)
{
	GObjectClass *object_class = (GObjectClass*) klass;

	parent_class = g_type_class_peek_parent(klass);

	object_class->dispose = disk_button_dispose;
	klass->disk_image[DISK_SELECTED] =
		gdk_pixbuf_new_from_inline(-1, selected_pixbuf, TRUE, NULL);
	klass->disk_image[DISK_UNSELECTED] =
		gdk_pixbuf_new_from_inline(-1, unselected_pixbuf, TRUE, NULL);
}

static void
disk_button_dispose(GObject *object)
{
	DiskButton *button;

	g_return_if_fail(object != NULL);
	g_return_if_fail(IS_DISKBUTTON(object));

	button = (DiskButton *)object;
	if (button->priv) {
		/* FIXME: free instances */

		g_list_free(button->priv->radios);
		button->priv->radios = NULL;

		g_free(button->priv);
		button->priv = NULL;
	}

	G_OBJECT_CLASS(parent_class)->dispose(object);
}

static void
disk_button_init(DiskButton *button)
{
	DiskButtonClass *class = DISKBUTTON_GET_CLASS(button);
	GladeXML *xml;
	GtkWidget *vbox;
	GtkWidget *viewport;
	GdkColor  backcolour;

	button->priv = g_new0(DiskButtonPrivate, 1);
	xml = glade_xml_new(GLADEDIR "/" DISKBUTTON_FILENAME,
				DISKBUTTON_NODE, NULL);
	button->priv->system_vbox = glade_xml_get_widget(xml, "system_vbox");
	vbox = glade_xml_get_widget(xml, DISKBUTTON_NODE);
	viewport = glade_xml_get_widget(xml, "diskbutton_viewport");
	button->priv->bar = glade_xml_get_widget(xml, "diskbutton_bar");
	gtk_container_add(GTK_CONTAINER(&button->widget), vbox);

	button->priv->image = glade_xml_get_widget(xml, "disk_image");
	gtk_image_set_from_pixbuf(GTK_IMAGE(button->priv->image),
			class->disk_image[DISK_UNSELECTED]);
	button->priv->disk_label = glade_xml_get_widget(xml, "disk_label");
	button->priv->boot_label = glade_xml_get_widget(xml, "boot_label");
	button->priv->nofound_label = glade_xml_get_widget(xml, "diskwarning_hbox");
	button->priv->disk_eventbox = glade_xml_get_widget(xml, "disk_eventbox");

	/* FIXME: white background color */
	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(viewport, GTK_STATE_NORMAL, &backcolour);
	gtk_widget_modify_bg(button->priv->disk_eventbox, GTK_STATE_NORMAL,
			&backcolour);

	/* FIXME: backgound of diskbutton bar */
	gdk_color_parse("#DCDEE4", &backcolour);
	gtk_widget_modify_bg(button->priv->bar, GTK_STATE_NORMAL, &backcolour);

	gtk_widget_show((GTK_WIDGET(&button->widget)));
}

void
change_button_icon(GtkWidget *radio, gpointer user_data)
{
	DiskButton *button = DISKBUTTON(user_data);
	DiskButtonClass *class = DISKBUTTON_GET_CLASS(button);

	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(radio))) {
		gtk_image_set_from_pixbuf(GTK_IMAGE(button->priv->image),
				class->disk_image[DISK_SELECTED]);
	} else {
		gtk_image_set_from_pixbuf(GTK_IMAGE(button->priv->image),
				class->disk_image[DISK_UNSELECTED]);
	}

	selected_disk = button->priv->disk;
}

void
on_disk_radio_toggled(GtkWidget *radio, gpointer user_data)
{
	selected_instance = g_object_get_data(G_OBJECT(radio), "upgrade_info");
}

static void
disk_button_add_instance(DiskButton *button, upgrade_info_t *uinfo)
{
	DiskButtonClass *class = DISKBUTTON_GET_CLASS(button);
	GladeXML *xml;
	GtkWidget *entry;
	GtkWidget *radio;
	GtkWidget *label;
	GtkWidget *hbox;
	GtkWidget *warning;
	gchar *markup;

	g_assert(button->priv != NULL);
	xml = glade_xml_new(GLADEDIR "/" DISKBUTTON_FILENAME,
				SYSTEMENTRY_NODE, NULL);
	entry = glade_xml_get_widget(xml, SYSTEMENTRY_NODE);
	hbox = glade_xml_get_widget(xml, "warning_hbox");
	warning = glade_xml_get_widget(xml, "syswarning_label");
	radio = gtk_radio_button_new(class->group);
	class->radios = g_list_append(class->radios, radio);
	g_object_set_data(G_OBJECT(radio), "upgrade_info", uinfo);
	g_object_set_data(G_OBJECT(radio), "radios", class->radios);
	g_object_set_data(G_OBJECT(radio), "warning_hbox", hbox);
	g_object_set_data(G_OBJECT(radio), "warning", warning);
	g_object_set_data(G_OBJECT(radio), "validated", GINT_TO_POINTER(FALSE));

	label = gtk_label_new(NULL);
	gtk_container_add(GTK_CONTAINER(radio), label);

	markup = g_markup_printf_escaped("<span font_desc=\"Bold\">%s</span>",
					orchestrator_om_upgrade_instance_get_release_name(uinfo));
	gtk_label_set_markup(GTK_LABEL(label), markup);
	g_free(markup);

	g_signal_connect(G_OBJECT(radio), "toggled",
						G_CALLBACK(change_button_icon), button);
	g_signal_connect(G_OBJECT(radio), "toggled",
						G_CALLBACK(on_disk_radio_toggled), NULL);

	/* show warning label? */
	if (!orchestrator_om_is_upgrade_target(uinfo)) {
		gint index;

		/*
		 * If we can not get the correct index,
		 * Unknow error will be shown.
		 */
		index = uinfo->upgrade_message_id -
					OM_UPGRADE_UNKNOWN_ERROR;
		if (index >= 0 &&
			index <= sizeof (error_messages) / sizeof (error_messages[0]))
			gtk_label_set_text(GTK_LABEL(warning),
							_(error_messages[index]));
		gtk_widget_set_sensitive(radio, FALSE);
		gtk_widget_show(hbox);
	}

	button->priv->radios = g_list_append(button->priv->radios, radio);

	gtk_widget_show_all(radio);
	gtk_box_pack_start(GTK_BOX(entry), radio, TRUE, TRUE, 0);
	gtk_widget_show(entry);
	gtk_box_pack_start(GTK_BOX(button->priv->system_vbox), entry,
			TRUE, TRUE, 0);
	class->group = gtk_radio_button_get_group(GTK_RADIO_BUTTON(radio));
}

static void
disk_button_set_disk_label(DiskButton *button, disk_info_t *disk)
{
	gchar *str;

	str = g_markup_printf_escaped(_("%.1f GB %s"),
								orchestrator_om_get_disk_sizegb(disk),
								orchestrator_om_get_disk_type(disk));
	gtk_label_set_markup(GTK_LABEL(button->priv->disk_label), str);
	g_free(str);

	if (orchestrator_om_disk_is_bootdevice(disk))
		gtk_widget_show(button->priv->boot_label);

}

static void
disk_button_set_tooltip(DiskButton *button, disk_info_t *disk)
{
	gchar *str;

	button->priv->tooltip = gtk_tooltips_new();
	str = g_strdup_printf(_("Size: %.1fGB\n"
				"Type: %s\n"
				"Vendor: %s\n"
				"Device: %s\n"
				"Boot device: %s"),
				orchestrator_om_get_disk_sizegb(disk),
				orchestrator_om_get_disk_type(disk),
				orchestrator_om_get_disk_vendor(disk),
				orchestrator_om_get_disk_devicename(disk),
				orchestrator_om_disk_is_bootdevice(disk) ? _("YES") : _("NO"));
	gtk_tooltips_set_tip(button->priv->tooltip, button->priv->disk_eventbox,
							str, NULL);
	g_free(str);
}

GtkWidget*
disk_button_new(disk_info_t *disk)
{
	DiskButton *button;
	upgrade_info_t *instance = NULL;

	g_assert(disk != NULL);

	button = DISKBUTTON(g_object_new(disk_button_get_type(), NULL));
	button->priv->disk = disk;
	orchestrator_om_get_upgrade_targets_by_disk(disk,
			&button->priv->instances, (guint16 *)&button->priv->ninstance);
	instance = button->priv->instances;
	if (instance)
		while (instance) {
			disk_button_add_instance(DISKBUTTON(button), instance);
			instance = orchestrator_om_upgrade_instance_get_next(instance);
		}
	else
		gtk_widget_show(button->priv->nofound_label);

	/* set disk label and tooltip */
	disk_button_set_disk_label(button, disk);
	disk_button_set_tooltip(button, disk);

	return (GTK_WIDGET(button));
}

/*
 * Returns the number of selectable instances
 */
guint
disk_button_get_nactive(DiskButton *button)
{
	GList *l;
	guint n = 0;

	l = g_list_nth(button->priv->radios, 0);
	while (l) {
		if (GTK_WIDGET_SENSITIVE(l->data))
			n++;
		l = g_list_next(l);
	}

	return (n);
}

/*
 * Return true if find a sensitive radio button
 */
gboolean
disk_button_set_default_active(DiskButton *button)
{
	GList *l;

	l = g_list_nth(button->priv->radios, 0);
	while (l) {
		if (!GTK_WIDGET_SENSITIVE(l->data)) {
			l = g_list_next(l);
			continue;
		} else {
			/*
			 * in case that the 1st button is alreay active
			 * we call change_button_icon manually.
			 */
			change_button_icon(l->data, button);
			gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(l->data),
												TRUE);
			g_signal_emit_by_name(G_OBJECT(l->data), "toggled", NULL);

			return (TRUE);
		}
	}

	return (FALSE);
}

void
disk_button_hide_bar(DiskButton *button)
{
	gtk_widget_hide(button->priv->bar);
}

void
disk_button_get_upgrade_info(disk_info_t **dinfo, upgrade_info_t **uinfo)
{
	*dinfo = orchestrator_om_duplicate_disk_info(selected_disk);
	*uinfo = orchestrator_om_duplicate_upgrade_targets(selected_instance);
}

void
disk_button_disable_radio_button(GtkRadioButton *radiobutton,
    const gchar *reason)
{
	GtkWidget *hbox;
	GtkWidget *label;

	gtk_widget_set_sensitive(GTK_WIDGET(radiobutton), FALSE);
	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(radiobutton), FALSE);
	hbox = g_object_get_data(G_OBJECT(radiobutton), "warning_hbox");
	label = g_object_get_data(G_OBJECT(radiobutton), "warning");
	gtk_label_set_text(GTK_LABEL(label), reason ? reason : "");
	gtk_widget_show(hbox);
}

GList *
disk_button_get_radio_buttons(DiskButton *button)
{
	DiskButtonClass *class = DISKBUTTON_GET_CLASS(button);

	return (class->radios);
}
