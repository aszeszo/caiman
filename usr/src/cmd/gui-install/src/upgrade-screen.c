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
#include <pixbufs.h>
#include "installation-profile.h"
#include "interface-globals.h"
#include "window-graphics.h"
#include "callbacks.h"
#include "diskbutton.h"
#include "upgrade-screen.h"
#include "orchestrator-wrappers.h"

#define	UPGRADE_NODE "upgrade_vbox"
#define	UPGRADE_CHECK_NODE "upgrade_space_win"

static void
disable_upgrade_target(upgrade_info_t *uinfo,
    const gchar *reason);

static void
upgrade_validation_cb(om_callback_info_t *cb_data,
    uintptr_t app_data);

static gboolean
upgrade_validation_monitor(gpointer user_data);

static GtkWidget *upgrade_vbox = NULL;
static GtkWidget *upgrade_viewport = NULL;
static GtkWidget *upgrade_scroll = NULL;
static GtkWidget *upgrade_space_win = NULL;
static GtkProgressBar *pbar = NULL;
static GList *disk_buttons = NULL;

static disk_info_t **diskinfo;
static gint ndisks;
static guint upgradeablesfound = 0;

/*
 * upgradecheckstatus
 * Indicates upgrade target validation check status:
 * == 0 : Validation in progress/not yet validated.
 *  > 0 : Validation passed.
 *  < 0 : Validation failed.
 */
static gint upgradecheckstatus = 0;

void
validate_upgrade_target()
{
	gboolean ret = FALSE;
	disk_info_t *dinfo = NULL;
	upgrade_info_t *uinfo = NULL;

	disk_button_get_upgrade_info(&dinfo, &uinfo);
	om_free_disk_info(omhandle, dinfo);
	ret = om_is_upgrade_target_valid(omhandle, uinfo,
	    upgrade_validation_cb);

	if (ret != B_TRUE) {
		g_warning("Upgrade target validation returned with error %d",
		    om_get_error());
		gui_install_prompt_dialog(
		    FALSE,
		    FALSE,
		    FALSE,
		    GTK_MESSAGE_ERROR,
		    _("Upgrade target validation failed"),
		    _("The installer encountered an internal error validating "
		    "the selected OpenSolaris environment. It can not be upgraded."));
		disable_upgrade_target(uinfo,
		    _("Upgrade target validation error."));
		om_free_upgrade_targets(omhandle, uinfo);
		upgradecheckstatus = 0;
		upgradeablesfound--;
		/*
		 * Look for the next upgradeable target and
		 * and auto select it.
		 */
		if (upgradeablesfound > 0) {
			DiskButton *button;
			GList *l = disk_buttons;
			gboolean have_default = FALSE;

			while (l) {
				button = l->data;
				if (!have_default) {
					have_default =
					    disk_button_set_default_active(button);
					if (have_default)
						break;
				}
				l = g_list_next(l);
			}
		}
		return;
	}

	gtk_widget_show(upgrade_space_win);
	g_timeout_add(100, upgrade_validation_monitor, NULL);
	om_free_upgrade_targets(omhandle, uinfo);
}

void
get_upgrade_info()
{
	disk_button_get_upgrade_info(&InstallationProfile.dinfo,
				&InstallationProfile.uinfo);

	InstallationProfile.slicename =
		orchestrator_om_upgrade_instance_construct_slicename(InstallationProfile.uinfo);
	InstallationProfile.disktype =
		orchestrator_om_get_disk_type(InstallationProfile.dinfo);
	InstallationProfile.disksize =
		orchestrator_om_get_disk_sizegb(InstallationProfile.dinfo);
	InstallationProfile.releasename =
		orchestrator_om_upgrade_instance_get_release_name(InstallationProfile.uinfo);
}

void
upgrade_xml_init(void)
{
	GladeXML *upgrade_xml;
	GladeXML *upgrade_check_xml;

	upgrade_xml = glade_xml_new(GLADEDIR "/" FILENAME, UPGRADE_NODE, NULL);
	upgrade_vbox = glade_xml_get_widget(upgrade_xml, "upgrade_vbox");
	upgrade_viewport = glade_xml_get_widget(upgrade_xml, "upgrade_viewport");
	upgrade_scroll = glade_xml_get_widget(upgrade_xml, "upgrade_scroll");

	upgrade_check_xml = glade_xml_new(GLADEDIR "/" FILENAME,
	    UPGRADE_CHECK_NODE, NULL);
	upgrade_space_win = glade_xml_get_widget(upgrade_check_xml,
	    "upgrade_space_win");
	pbar = GTK_PROGRESS_BAR(
	    glade_xml_get_widget(upgrade_check_xml, "ugcheckprogressbar"));
}

static gdouble
get_vertical_slider_pos(GtkWidget *button, GtkAdjustment *adjustment)
{
	GList *l;
	gdouble pos;
	gdouble old_pos;

	l = g_object_get_data(G_OBJECT(button), "radios");
	old_pos = gtk_adjustment_get_value(adjustment);
	pos =  ((adjustment->upper - adjustment->lower) /
				g_list_length(l)) * g_list_index(l, button);

	if (pos > old_pos && pos < old_pos + adjustment->page_size)
		pos = old_pos;
	if (pos > (adjustment->upper - adjustment->page_size))
		pos = adjustment->upper - adjustment->page_size;
	if (pos < adjustment->lower)
		pos = adjustment->lower;

	return (pos);
}

static void
on_radio_toggled(GtkRadioButton *radio, gpointer user_data)
{
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(radio))) {
		GtkAdjustment *adjustment = GTK_ADJUSTMENT(user_data);
		gdouble pos;

		pos = get_vertical_slider_pos(GTK_WIDGET(radio), adjustment);
		gtk_adjustment_set_value(adjustment, pos);
		gtk_adjustment_value_changed(adjustment);
	}
}

static void
activate_previous_radio(GtkWidget *button)
{
	GList *l;
	GList *previous;

	/*
	 * deactivate current radio button
	 * and activate the previous one
	 */
	l = g_object_get_data(G_OBJECT(button), "radios");
	previous = g_list_find(l, button);
	/*
	 * find the previous sensitive button
	 * in the list
	 */
	do {
		previous = g_list_previous(previous);
		if (!previous)
			previous = g_list_last(l);
		if (GTK_WIDGET_SENSITIVE(previous->data))
			break;
		/*
		 * traversed all the elements in
		 * the link and found nothing
		 * this should not happen
		 */
		if (previous->data == button)
			break;
	} while (1);

	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(button), FALSE);
	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(previous->data), TRUE);
	gtk_widget_grab_focus(GTK_WIDGET(previous->data));
}

static void
activate_next_radio(GtkWidget *button)
{
	GList *l;
	GList *next;

	/*
	 * deactivate current radio button
	 * and activate the next one
	 */
	l = g_object_get_data(G_OBJECT(button), "radios");
	next = g_list_find(l, button);
	/*
	 * find the next sensitive button
	 * in the list
	 */
	do {
		next = g_list_next(next);
		if (!next)
			next = l;
		if (GTK_WIDGET_SENSITIVE(next->data))
			break;
		/*
		 * traversed all the elements in
		 * the link and found nothing
		 * this should not happen
		 */
		if (next->data == button)
			break;
	} while (1);

	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(button), FALSE);
	gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(next->data), TRUE);
	gtk_widget_grab_focus(GTK_WIDGET(next->data));
}

static gboolean
on_key_press_event_up_down(GtkToggleButton *button,
			GdkEventKey *event,
			gpointer user_data)
{
	/*
	 * Handle up and down key ourself
	 * because set radio button contained by
	 * different container in a same group
	 * results in confusing behaviour.
	 * But leave other keys to system.
	 */
	switch (event->keyval) {
	case	GDK_Up:
		activate_previous_radio(GTK_WIDGET(button));
		return (TRUE);
	case	GDK_Down:
		activate_next_radio(GTK_WIDGET(button));
		return (TRUE);
	default:
		break;
	}

	return (FALSE);
}

static gboolean
on_key_press_event_left_right(GtkToggleButton *button, GdkEventKey *event, gpointer user_data)
{
	GtkAdjustment *adjustment = GTK_ADJUSTMENT(user_data);
	gdouble pos;

	pos = gtk_adjustment_get_value(adjustment);

	switch (event->keyval) {
	case	GDK_Left:
		pos = pos - adjustment->step_increment;
		if (pos > (adjustment->upper - adjustment->page_size))
			pos = adjustment->upper - adjustment->page_size;
		if (pos < adjustment->lower)
			pos = adjustment->lower;
		gtk_adjustment_set_value(adjustment, pos);
		gtk_adjustment_value_changed(adjustment);
		return (TRUE);
	case	GDK_Right:
		pos = pos + adjustment->step_increment;
		if (pos > (adjustment->upper - adjustment->page_size))
			pos = adjustment->upper - adjustment->page_size;
		if (pos < adjustment->lower)
			pos = adjustment->lower;
		gtk_adjustment_set_value(adjustment, pos);
		gtk_adjustment_value_changed(adjustment);
		return (TRUE);
	default:
		break;
	}

	return (FALSE);
}

void
upgrade_disk_screen_init(void)
{
	GtkWidget *button;
	GtkWidget *disk_vbox;
	GtkWidget *upgradedetection_vbox = NULL;
	GtkAdjustment *hadj;
	GtkAdjustment *vadj;
	GdkColor  backcolour;
	disk_info_t *diskptr;
	gboolean have_default = FALSE;
	GList *l = NULL;

	diskinfo = orchestrator_om_get_disk_info(omhandle, &ndisks);
	upgradedetection_vbox = gtk_bin_get_child(GTK_BIN(upgrade_viewport));
	gtk_container_remove(GTK_CONTAINER(upgrade_viewport), upgradedetection_vbox);
	disk_vbox = gtk_vbox_new(FALSE, 10);
	gtk_widget_show(disk_vbox);
	gtk_container_add(GTK_CONTAINER(upgrade_viewport), disk_vbox);

	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(upgrade_viewport, GTK_STATE_NORMAL, &backcolour);

	/* If 0 disks then don't waste any time in here */
	if (ndisks <= 0) {
		g_message("No disks found by target discovery, disabling upgrade");
		return;
	}

	for (gint i = 0; i < ndisks; i++) {
		diskptr = diskinfo[i];
		if (!diskptr) {
			g_warning("Skipping over upgrade target disk %d: "
				"no disk info provided.", i);
			continue;
		}
		button = disk_button_new(diskptr);
		gtk_box_pack_start(GTK_BOX(disk_vbox), button, FALSE, FALSE, 0);
		disk_buttons = g_list_append(disk_buttons, button);
	}

	l = disk_buttons;
	while (l) {
		button = l->data;
		/* Important: Indicates that the system is upgradeable */
		upgradeablesfound += disk_button_get_nactive(DISKBUTTON(button));
		if (!have_default) {
			have_default = disk_button_set_default_active(DISKBUTTON(button));
		}
		l = g_list_next(l);
	}

	hadj = gtk_scrolled_window_get_hadjustment
					(GTK_SCROLLED_WINDOW(upgrade_scroll));
	vadj = gtk_scrolled_window_get_vadjustment
					(GTK_SCROLLED_WINDOW(upgrade_scroll));
	l = disk_button_get_radio_buttons(DISKBUTTON(button));
	while (l) {
		GtkRadioButton *radio = GTK_RADIO_BUTTON(l->data);

		g_signal_connect(G_OBJECT(radio), "key-press-event",
				G_CALLBACK(on_key_press_event_left_right), hadj);
		g_signal_connect(G_OBJECT(radio), "key-press-event",
				G_CALLBACK(on_key_press_event_up_down), vadj);
		g_signal_connect(G_OBJECT(radio), "toggled",
							G_CALLBACK(on_radio_toggled), vadj);
		l = g_list_next(l);
	}

	if (upgradeablesfound > 0)
		gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
}

void
upgrade_info_cleanup()
{
	g_list_free(disk_buttons);
}

gboolean
upgrade_discovery_monitor(gpointer user_data)
{
	/*
	 * Don't to anything until both target discovery and
	 * UI initialisation has been completed
	 */
	if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] == FALSE)
		return (TRUE);

	upgrade_disk_screen_init();
	return (FALSE);
}

static GtkRadioButton *
upgrade_get_radiobutton_from_info(upgrade_info_t *uinfo)
{
	GtkRadioButton *radiobutton = NULL;
	DiskButton *button = NULL;
	GList *radios;
	GList *radio = NULL;
	GList *l = NULL;
	upgrade_info_t *tmpinfo;

	l = disk_buttons;
	while (l && radiobutton == NULL) {
		button = l->data;
		radios = disk_button_get_radio_buttons(button);
		radio = radios;
		while ((radio != NULL) && (radiobutton == NULL)) {
			tmpinfo = g_object_get_data(G_OBJECT(radio->data), "upgrade_info");
			if (uinfo->instance_type == tmpinfo->instance_type) {
				switch (uinfo->instance_type) {
					case OM_INSTANCE_UFS:
						if ((strcmp(uinfo->instance.uinfo.disk_name,
						    tmpinfo->instance.uinfo.disk_name) == 0) &&
						    (uinfo->instance.uinfo.slice ==
						    tmpinfo->instance.uinfo.slice))
							radiobutton = (GtkRadioButton *)radio->data;
						break;
					case OM_INSTANCE_ZFS:
						/*
						 * XXX: Unused code until zfs support is
						 * added. Multiple instances can be present
						 * on a zfs pool so dataset or some additional
						 * comparison is probably necessary. This is
						 * place holder code.
						 */
						if (strcmp(uinfo->instance.zinfo.pool_name,
						    tmpinfo->instance.zinfo.pool_name) == 0)
						    radiobutton = (GtkRadioButton *)&radio->data;
						break;
				}
			}
			radio = g_list_next(radio);
		}
		l = g_list_next(l);
	}

	return (radiobutton);
}

gboolean
is_target_validated(upgrade_info_t *uinfo)
{
	GtkRadioButton *radiobutton = NULL;

	radiobutton = upgrade_get_radiobutton_from_info(uinfo);
	g_assert(radiobutton != NULL);
	return (GPOINTER_TO_INT(
	    g_object_get_data(G_OBJECT(radiobutton), "validated")));
}

gboolean
is_selected_target_validated()
{
	gboolean retval;
	disk_info_t *dinfo = NULL;
	upgrade_info_t *uinfo = NULL;

	disk_button_get_upgrade_info(&dinfo, &uinfo);
	retval = is_target_validated(uinfo);
	om_free_upgrade_targets(omhandle, uinfo);
	om_free_disk_info(omhandle, dinfo);
	return (retval);
}

static void
set_target_validated(upgrade_info_t *uinfo)
{
	GtkRadioButton *radiobutton = NULL;

	radiobutton = upgrade_get_radiobutton_from_info(uinfo);
	g_assert(radiobutton != NULL);
	g_object_set_data(G_OBJECT(radiobutton), "validated",
		GINT_TO_POINTER(TRUE));
}

static void
disable_upgrade_target(upgrade_info_t *uinfo,
    const gchar *reason)
{
	GtkRadioButton *radiobutton = NULL;

	radiobutton = upgrade_get_radiobutton_from_info(uinfo);
	g_assert(radiobutton != NULL);
	disk_button_disable_radio_button(radiobutton, reason);
}

static gboolean
upgrade_validation_monitor(gpointer user_data)
{
	DiskButton *button = NULL;
	GtkWidget *dialog;
	gboolean retval = FALSE;
	disk_info_t *dinfo = NULL;
	upgrade_info_t *uinfo = NULL;

	switch (upgradecheckstatus) {
		case 0:
			gtk_progress_bar_pulse(pbar);
			retval = TRUE;
			break;
		case 1:
			disk_button_get_upgrade_info(&dinfo, &uinfo);
			set_target_validated(uinfo);
			gtk_widget_hide(upgrade_space_win);
			/* Automatically go forward to next screen - Confirmation */
			on_nextbutton_clicked(GTK_BUTTON(MainWindow.nextbutton), NULL);
			retval = FALSE;
			om_free_upgrade_targets(omhandle, uinfo);
			om_free_disk_info(omhandle, dinfo);
			break;
		case -1:
			gtk_widget_hide(upgrade_space_win);
			gui_install_prompt_dialog(
			    FALSE,
			    FALSE,
			    FALSE,
			    GTK_MESSAGE_ERROR,
			    _("Free space checking failed"),
			    _("There is insufficient free space to upgrade "
			    "the selected OpenSolaris environment."));
			disk_button_get_upgrade_info(&dinfo, &uinfo);
			disable_upgrade_target(uinfo,
			    _("Insufficient free space."));
			om_free_upgrade_targets(omhandle, uinfo);
			om_free_disk_info(omhandle, dinfo);
			retval = FALSE;
			upgradeablesfound--;

			if (upgradeablesfound > 0) {
				DiskButton *button;
				GList *l = disk_buttons;
				gboolean have_default = FALSE;

				while (l) {
					button = l->data;
					if (!have_default) {
						have_default =
						    disk_button_set_default_active(button);
						if (have_default)
							break;
					}
					l = g_list_next(l);
				}
			}
			break;
	}

	return (retval);
}

void
upgrade_detection_screen_init(void)
{
	GtkWidget *upgradedetection_vbox = NULL;
	GdkColor  backcolour;
	GList *l = NULL;

	upgradedetection_vbox = gtk_bin_get_child(GTK_BIN(upgrade_viewport));
	l = gtk_container_get_children(GTK_CONTAINER(upgradedetection_vbox));
	while (l) {
		if (G_OBJECT_TYPE(l->data) == GTK_TYPE_IMAGE) {
			gtk_image_set_from_file(GTK_IMAGE(l->data), PIXMAPDIR "/" "gnome-spinner.gif");
			break;
		}
		l = g_list_next(l);
	}

	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(upgrade_viewport, GTK_STATE_NORMAL, &backcolour);
	gtk_box_pack_start(GTK_BOX(MainWindow.screencontentvbox),
							upgrade_vbox, TRUE, TRUE, 0);
	show_upgrade_screen(FALSE);

	if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] == FALSE) {
		g_timeout_add(200, upgrade_discovery_monitor, NULL);
	} else { /* Go straight to upgrade target display function */
		upgrade_discovery_monitor(NULL);
	}
}

void
show_upgrade_screen(gboolean show)
{
	if (show)
		gtk_widget_show(upgrade_vbox);
	else
		gtk_widget_hide(upgrade_vbox);
}

gboolean
upgradeable_instance_found(void)
{
	if (upgradeablesfound > 0)
		return (TRUE);
	else
		return (FALSE);
}

static void
upgrade_validation_cb(om_callback_info_t *cb_data,
    uintptr_t app_data)
{
	g_return_if_fail(cb_data);
	g_message("upgrade_validation_cb : milestones = %d\n",
	    cb_data->num_milestones);
	g_message("\t: curr_milestone = %d : %s\n",
	    cb_data->curr_milestone,
	    lookup_milestone_type(cb_data->curr_milestone));
	g_message("\t: callback_type = %d : %s\n",
	    cb_data->callback_type,
	    lookup_callback_type(cb_data->callback_type));
	g_message("\t: percentage_done = %d\n",
	    cb_data->percentage_done);

	/*
	 * Fields to process
	 * cb->num_milestones = 1;
	 * cb->callback_type = OM_SYSTEM_VALIDATION;
	 * cb->percent_done = 0;
	 * cb->curr_milestone = OM_UPGRADE_CHECK;
	 * cb(cb_info, NULL);
	 */

	switch (cb_data->curr_milestone) {
		case OM_UPGRADE_CHECK :
			if (cb_data->percentage_done == 100)
				upgradecheckstatus = 1;
			else if (cb_data->percentage_done == -1) {
				upgradecheckstatus = -1;
				g_warning("Upgrade validation check failed: %s",
				    g_strerror(cb_data->percentage_done));
			}
			break;
		default :
			g_warning("Invalid update curr_milestone : %d : %s\n",
				cb_data->curr_milestone,
				lookup_milestone_type(cb_data->curr_milestone));
			break;
	}
}
