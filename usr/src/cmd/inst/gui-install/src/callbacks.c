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
#pragma ident	"@(#)callbacks.c	1.7	07/10/30 SMI"

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <sys/wait.h>
#include <gnome.h>

#include "installation-profile.h"
#include "interface-globals.h"
#include "users-screen.h"
#include "confirmation-screen.h"
#include "finish-screen.h"
#include "installation-disk-screen.h"
#include "language-screen.h"
#include "datetimezone-screen.h"
#include "upgrade-screen.h"
#include "failure-screen.h"
#include "installation-screen.h"
#include "welcome-screen.h"
#include "help-dialog.h"

#define	CAT		"cat"
#define	EJECT	"eject"
#define	REBOOT	"reboot"
#define	CDROOTPATH	"/tmp/.cdroot"

#define	HIDE_LANGUAGE_SCREEN

InstallScreen InstallCurrScreen = WELCOME_SCREEN;

/* Forward declaration */
static gboolean
would_you_like_to_install_instead(void);

void
target_discovery_callback(om_callback_info_t *cb_data,
					uintptr_t app_data)
{
	g_return_if_fail(cb_data);
	g_return_if_fail(cb_data->callback_type == OM_TARGET_TARGET_DISCOVERY);

	switch (cb_data->curr_milestone) {
		case OM_DISK_DISCOVERY:
			MainWindow.MileStoneComplete[OM_DISK_DISCOVERY] =
				cb_data->percentage_done == 100 ?  TRUE : FALSE;
			break;
		case OM_PARTITION_DISCOVERY:
			MainWindow.MileStoneComplete[OM_PARTITION_DISCOVERY] =
				cb_data->percentage_done == 100 ?  TRUE : FALSE;
			break;
		case OM_SLICE_DISCOVERY:
			MainWindow.MileStoneComplete[OM_SLICE_DISCOVERY] =
				cb_data->percentage_done == 100 ?  TRUE : FALSE;
			break;
		case OM_UPGRADE_TARGET_DISCOVERY:
			MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] =
				cb_data->percentage_done == 100 ?  TRUE : FALSE;
			break;
	}
}

gboolean
gui_install_prompt_dialog(gboolean ok_cancel,
					gboolean set_ok_default,
					gboolean use_accept,
					GtkMessageType type,
					gchar *primary,
					gchar *secondary)
{
	GtkWidget *dialog;
	gboolean ret_val = FALSE;
	GtkWidget *button;
	GtkWidget *image;

	if (ok_cancel) {
		if (use_accept) {
			/* Want to replace OK with Accept, Which is none standard */
			/* So Create the dialog with just a Cancel button */
			dialog = gtk_message_dialog_new(NULL,
							GTK_DIALOG_MODAL | \
							GTK_DIALOG_DESTROY_WITH_PARENT,
							type,
							GTK_BUTTONS_CANCEL,
							primary);

			/* Add a Accept button which emits the OK response */
			button = gtk_dialog_add_button(GTK_DIALOG(dialog),
							_("_Accept"), GTK_RESPONSE_OK);

			/* Create a new image from stock OK Icon */
			image = gtk_image_new_from_stock(GTK_STOCK_OK, GTK_ICON_SIZE_BUTTON);

			/* Set the image on the Accept button to be the same as OK */
			gtk_button_set_image(GTK_BUTTON(button), image);
		} else {
			dialog = gtk_message_dialog_new(NULL,
							GTK_DIALOG_MODAL | \
							GTK_DIALOG_DESTROY_WITH_PARENT,
							type,
							GTK_BUTTONS_OK_CANCEL,
							primary);
		}
	} else {
		dialog = gtk_message_dialog_new(NULL,
							GTK_DIALOG_MODAL | \
							GTK_DIALOG_DESTROY_WITH_PARENT,
							type,
							GTK_BUTTONS_CLOSE,
							primary);
	}
	if (secondary != NULL && strlen(secondary) > 0) {
		gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
							secondary);
	}

	if (ok_cancel) {
		if (set_ok_default) {
			gtk_dialog_set_default_response(GTK_DIALOG(dialog),
					GTK_RESPONSE_OK);
		}
		if ((gtk_dialog_run(GTK_DIALOG(dialog))) == GTK_RESPONSE_OK) {
			ret_val = TRUE;
		} else {
			ret_val = FALSE;
		}
	} else {
		gtk_dialog_run(GTK_DIALOG(dialog));
	}
	gtk_widget_destroy(dialog);

	return (ret_val);
}

void
on_helpbutton_clicked(GtkButton *button,
			gpointer   user_data)
{
	help_dialog_show(InstallCurrScreen, TRUE);
}

static gboolean
prompt_quit()
{
	gboolean ret_val = FALSE;

	switch (InstallationProfile.installationtype) {
		case INSTALLATION_TYPE_INITIAL_INSTALL:
			ret_val = gui_install_prompt_dialog(TRUE, FALSE, FALSE,
							GTK_MESSAGE_WARNING,
							_("Do you want to quit this installation ?"),
							NULL);
			break;
		case INSTALLATION_TYPE_INPLACE_UPGRADE:
			ret_val = gui_install_prompt_dialog(TRUE, FALSE, FALSE,
							GTK_MESSAGE_WARNING,
							_("Do you want to quit this installation ?"),
							NULL);
			break;
	}
	return (ret_val);
}

gboolean
on_quitbutton_clicked(GtkButton *button,
			gpointer user_data)
{
	switch (InstallCurrScreen) {
		case WELCOME_SCREEN :
		case DISK_SCREEN :
		case TIMEZONE_SCREEN :
		case LANGUAGE_SCREEN :
		case USER_SCREEN :
		case CONFIRMATION_SCREEN :
			if (prompt_quit()) {
				exit(1);
			}
			break;
		case INSTALLATION_SCREEN :
			/* Should not be able to quit from here */
			g_warning("Cannot quit during installation.\n");
			break;
		case FAILURE_SCREEN :
			/*
			 * Don't exit the app completely if the user is looking at
			 * the installation log.
			 */
			if (GTK_WIDGET_VISIBLE(
			    MainWindow.FailureWindow.installlogdialog))
				gtk_widget_hide(MainWindow.mainwindow);
			else
				/* No prompt for quitting from install/upgrade failure */
				exit(1);
			break;
		case FINISH_SCREEN :
			/*
			 * Don't exit the app completely if the user is looking at
			 * the installation log.
			 */
			if (GTK_WIDGET_VISIBLE(
				MainWindow.FinishWindow.installationlogdialog)) {
				if (prompt_quit())
					gtk_widget_hide(MainWindow.mainwindow);
			} else if (prompt_quit()) {
				exit(0);
			}
			break;
	}
	return TRUE;
}

void
on_nextbutton_clicked(GtkButton *button,
			gpointer user_data)
{
	gchar *title;

	/* Perform required validation before moving to next screen */
	switch (InstallCurrScreen) {
		case WELCOME_SCREEN :
			InstallCurrScreen++;
			break;
		case DISK_SCREEN :
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INPLACE_UPGRADE :
					/*
					 * If there are no upgradeable targets ask the user if they'd
					 * like to install instead and whisk them away to the install
					 * screen.
					 */
					if (upgradeable_instance_found() == FALSE) {
						if (would_you_like_to_install_instead() == TRUE)
							gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
							    WelcomeWindow.installradio),
							    TRUE);
					} else {
						if (is_selected_target_validated() == FALSE)
							validate_upgrade_target();
						else {
							get_upgrade_info();
							/* Short circuit to the comfirmation screen */
							InstallCurrScreen = CONFIRMATION_SCREEN;
						}
					}
					break;
				default: /* Initial Install */
					if (!installationdisk_validate()) {
						return;
					}
					installation_disk_store_data();
					InstallCurrScreen++;
					break;
			}
			break;
		case TIMEZONE_SCREEN :
			/*
			 * Only proceed if we get a valid time zone.
			 */
			if (!get_selected_tz(&InstallationProfile))
				return;
			InstallCurrScreen++;
#ifdef HIDE_LANGUAGE_SCREEN
			InstallCurrScreen++;
#endif /* HIDE_LANGUAGE_SCREEN */
			datetimezone_set_system_clock(TRUE);
			break;
		case LANGUAGE_SCREEN :
			InstallCurrScreen++;
			get_default_language();
			break;
		case USER_SCREEN :
			if (MainWindow.UsersWindow.userswindowtable) {
				if (!users_validate()) {
					return;
				}
			}
			users_store_data();
			InstallCurrScreen++;
			break;
		case CONFIRMATION_SCREEN :
			InstallCurrScreen++;
			break;
		case INSTALLATION_SCREEN :
			if (InstallationProfile.installfailed) {
				InstallCurrScreen++;
			} else {
				InstallCurrScreen = InstallCurrScreen + 2;
			}
			break;
		case FAILURE_SCREEN :
			g_warning("Next button should not be available after failure\n");
			break;
		case FINISH_SCREEN :
			InstallCurrScreen++;
			break;
	}

	switch (InstallCurrScreen) {
		case DISK_SCREEN :
			gtk_widget_hide(MainWindow.welcomescreenvbox);
			gtk_label_set_label(GTK_LABEL(MainWindow.welcomelabel),
				MainWindow.InactiveStageTitles[WELCOME_SCREEN]);

			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					show_upgrade_screen(FALSE);
					gtk_widget_show(
						MainWindow.InstallationDiskWindow.diskselectiontoplevel);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY]
							== FALSE)
						gtk_widget_set_sensitive(MainWindow.nextbutton, FALSE);
					gtk_widget_hide(
						MainWindow.InstallationDiskWindow.diskselectiontoplevel);
					show_upgrade_screen(TRUE);
					break;
			}

			gtk_widget_set_sensitive(MainWindow.backbutton, TRUE);

			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[DISK_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.disklabel),
				MainWindow.ActiveStageTitles[DISK_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);

			break;

		case TIMEZONE_SCREEN :
			gtk_widget_hide(
				MainWindow.InstallationDiskWindow.diskselectiontoplevel);
			gtk_label_set_label(GTK_LABEL(MainWindow.disklabel),
				MainWindow.InactiveStageTitles[DISK_SCREEN]);

			gtk_widget_show(MainWindow.DateTimeZoneWindow.datetimezonetoplevel);

			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[TIMEZONE_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.timezonelabel),
				MainWindow.ActiveStageTitles[TIMEZONE_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;

		case LANGUAGE_SCREEN :
			if (!MainWindow.languagewindowtable) {
				MainWindow.languagewindowtable =
					language_screen_init(MainWindow.languagewindowxml);
				gtk_box_pack_start(GTK_BOX(MainWindow.screencontentvbox),
					MainWindow.languagewindowtable, TRUE, TRUE, 0);
			}
			gtk_widget_hide(MainWindow.DateTimeZoneWindow.datetimezonetoplevel);
			gtk_label_set_label(GTK_LABEL(MainWindow.timezonelabel),
				MainWindow.InactiveStageTitles[TIMEZONE_SCREEN]);

			gtk_widget_show(MainWindow.languagewindowtable);

			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[LANGUAGE_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.languagelabel),
				MainWindow.ActiveStageTitles[LANGUAGE_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;

		case USER_SCREEN :
			if (!MainWindow.UsersWindow.userswindowtable) {
				users_load_widgets();
				gtk_box_pack_start(GTK_BOX(MainWindow.screencontentvbox),
						MainWindow.UsersWindow.userswindowtable,
						TRUE, TRUE, 0);
			}

#ifdef HIDE_LANGUAGE_SCREEN
			gtk_widget_hide(MainWindow.DateTimeZoneWindow.datetimezonetoplevel);
			gtk_label_set_label(GTK_LABEL(MainWindow.timezonelabel),
				MainWindow.InactiveStageTitles[TIMEZONE_SCREEN]);
#else
			gtk_widget_hide(MainWindow.languagewindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.languagelabel),
				MainWindow.InactiveStageTitles[LANGUAGE_SCREEN]);
#endif /* HIDE_LANGUAGE_SCREEN */

			gtk_widget_show(MainWindow.UsersWindow.userswindowtable);

			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[USER_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.userlabel),
				MainWindow.ActiveStageTitles[USER_SCREEN]);
			gtk_widget_grab_focus(MainWindow.UsersWindow.rootpassword1entry);
			help_dialog_refresh(InstallCurrScreen);
			break;

		case CONFIRMATION_SCREEN:
			if (!MainWindow.ConfirmationWindow.confirmationwindowtable) {
				confirmation_load_widgets();
				gtk_box_pack_start(GTK_BOX(MainWindow.screencontentvbox),
						MainWindow.ConfirmationWindow.confirmationwindowtable,
						TRUE, TRUE, 0);
			}
			gtk_widget_hide(MainWindow.nextbutton);
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_hide(MainWindow.UsersWindow.userswindowtable);
					gtk_widget_show(MainWindow.installbutton);
					gtk_widget_set_sensitive(MainWindow.installbutton, TRUE);
					gtk_label_set_label(GTK_LABEL(MainWindow.userlabel),
						MainWindow.InactiveStageTitles[USER_SCREEN]);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					show_upgrade_screen(FALSE);
					gtk_widget_show(MainWindow.upgradebutton);
					gtk_widget_set_sensitive(MainWindow.upgradebutton, TRUE);
					gtk_label_set_label(GTK_LABEL(MainWindow.disklabel),
						MainWindow.InactiveStageTitles[DISK_SCREEN]);
					break;
			}
			confirmation_screen_set_contents();
			gtk_widget_show(
					MainWindow.ConfirmationWindow.confirmationwindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[CONFIRMATION_SCREEN]);
			title = g_strdup_printf(ActiveStageTitleMarkup,
							gtk_label_get_text(
								GTK_LABEL(MainWindow.installationlabel)));
			gtk_label_set_label(GTK_LABEL(MainWindow.installationlabel),
									title);
			g_free(title);
			help_dialog_refresh(InstallCurrScreen);
			break;

		case INSTALLATION_SCREEN :
			if (!MainWindow.InstallationWindow.installationwindowtable) {
				MainWindow.InstallationWindow.installationwindowtable =
					glade_xml_get_widget(MainWindow.installationwindowxml,
						"installationwindowtable");
				installation_window_load_widgets();
				gtk_box_pack_start(
					GTK_BOX(MainWindow.screencontentvbox),
					MainWindow.InstallationWindow.installationwindowtable,
					TRUE, TRUE, 0);
			}
			gtk_widget_hide(
				MainWindow.ConfirmationWindow.confirmationwindowtable);

			installation_window_set_contents();

			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_set_sensitive(MainWindow.installbutton, FALSE);
					break;

				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					gtk_widget_set_sensitive(MainWindow.upgradebutton, FALSE);
					break;
			}

			gtk_widget_show(
				MainWindow.InstallationWindow.installationwindowtable);
			gtk_widget_set_sensitive(MainWindow.backbutton, FALSE);
			gtk_widget_set_sensitive(MainWindow.quitbutton, FALSE);
			gtk_widget_hide(MainWindow.backbutton);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[INSTALLATION_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.installationlabel),
				MainWindow.ActiveStageTitles[INSTALLATION_SCREEN]);

			installation_window_start_install();
			help_dialog_refresh(InstallCurrScreen);
			break;

		case FAILURE_SCREEN :
			if (!MainWindow.FailureWindow.failurewindowtable) {
				MainWindow.FailureWindow.failurewindowtable =
					glade_xml_get_widget(MainWindow.failurewindowxml,
						"failurewindowtable");
				failure_screen_load_widgets();
				gtk_box_pack_start(
					GTK_BOX(MainWindow.screencontentvbox),
					MainWindow.FailureWindow.failurewindowtable,
					TRUE, TRUE, 0);
			}
			gtk_widget_hide(
				MainWindow.InstallationWindow.installationwindowtable);

			failure_screen_set_contents();

			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_set_sensitive(MainWindow.installbutton, FALSE);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					gtk_widget_set_sensitive(MainWindow.upgradebutton, FALSE);
					break;
			}

			gtk_widget_show(
				MainWindow.FailureWindow.failurewindowtable);
			gtk_widget_set_sensitive(MainWindow.backbutton, FALSE);
			gtk_widget_set_sensitive(MainWindow.quitbutton, TRUE);
			gtk_widget_hide(MainWindow.backbutton);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[FAILURE_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;

		case FINISH_SCREEN :
			gtk_label_set_label(GTK_LABEL(MainWindow.installationlabel),
				MainWindow.InactiveStageTitles[INSTALLATION_SCREEN]);
			gtk_widget_hide(
				MainWindow.InstallationWindow.installationwindowtable);
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_hide(MainWindow.installbutton);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					gtk_widget_hide(MainWindow.upgradebutton);
					break;
			}

			finish_screen_set_contents();

			gtk_widget_show(MainWindow.rebootbutton);
			gtk_widget_set_sensitive(MainWindow.quitbutton, TRUE);
			gtk_widget_show(MainWindow.FinishWindow.finishbox);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[FINISH_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.finishlabel),
				MainWindow.ActiveStageTitles[FINISH_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;
	}
}

void
on_backbutton_clicked(GtkButton *button,
			gpointer user_data)
{
	gchar *title;
	/* Possible perform some validation before moving to next screen */
	switch (InstallCurrScreen) {
		case WELCOME_SCREEN :
			InstallCurrScreen--;
			break;
		case DISK_SCREEN :
			InstallCurrScreen--;
			break;
		case TIMEZONE_SCREEN :
			InstallCurrScreen--;
			break;
		case LANGUAGE_SCREEN :
			InstallCurrScreen--;
			break;
		case USER_SCREEN :
			InstallCurrScreen--;
#ifdef HIDE_LANGUAGE_SCREEN
			InstallCurrScreen--;
#endif /* HIDE_LANGUAGE_SCREEN */
			break;
		case CONFIRMATION_SCREEN:
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_hide(MainWindow.installbutton);
					InstallCurrScreen--;
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					/* Short circuit back to the DISK_SCREEN */
					gtk_widget_hide(MainWindow.upgradebutton);
					InstallCurrScreen = DISK_SCREEN;
					break;
			}
			gtk_widget_show(MainWindow.nextbutton);
			break;
		case INSTALLATION_SCREEN:
			/*
			 * Nothing because the back button shouldn't be sensitive
			 * once the installation/upgrade is underway.
			 */
			g_warning(
				"Back button should not be available from install/upgrade progress Screen\n");
			break;
		case FAILURE_SCREEN:
			/*
			 * Nothing because the back button shouldn't be sensitive
			 * once the installation/upgrade has failed.
			 */
			g_warning(
				"Back button should not be available from Install/Upgrade failure Screen\n");
			break;
		case FINISH_SCREEN:
			/*
			 * Nothing because the back button shouldn't be sensitive
			 * once the installation/upgrade is underway.
			 */
			g_warning(
				"Back button should not be available from Finish Screen\n");
			break;
	}

	switch (InstallCurrScreen) {
		case WELCOME_SCREEN :
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_hide(
						MainWindow.InstallationDiskWindow.diskselectiontoplevel);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					show_upgrade_screen(FALSE);
					break;
			}
			gtk_label_set_label(GTK_LABEL(MainWindow.disklabel),
				MainWindow.InactiveStageTitles[DISK_SCREEN]);
			gtk_widget_show(MainWindow.welcomescreenvbox);
			gtk_widget_set_sensitive(MainWindow.backbutton, FALSE);
			gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[WELCOME_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.welcomelabel),
				MainWindow.ActiveStageTitles[WELCOME_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;
		case DISK_SCREEN :
			switch (InstallationProfile.installationtype) {
				case INSTALLATION_TYPE_INITIAL_INSTALL:
					gtk_widget_hide(
						MainWindow.DateTimeZoneWindow.datetimezonetoplevel);
					gtk_label_set_label(GTK_LABEL(MainWindow.timezonelabel),
						MainWindow.InactiveStageTitles[TIMEZONE_SCREEN]);
					gtk_widget_show(
						MainWindow.InstallationDiskWindow.diskselectiontoplevel);
					break;
				case INSTALLATION_TYPE_INPLACE_UPGRADE:
					gtk_widget_hide(
						MainWindow.ConfirmationWindow.confirmationwindowtable);
					gtk_widget_hide(MainWindow.upgradebutton);
					title = g_strdup_printf(InactiveStageTitleMarkup,
								gtk_label_get_text(GTK_LABEL(
									MainWindow.installationlabel)));
					gtk_label_set_label(GTK_LABEL(MainWindow.installationlabel),
							title);
					gtk_widget_show(MainWindow.nextbutton);
					show_upgrade_screen(TRUE);
					g_free(title);
					break;
			}
			gtk_widget_set_sensitive(MainWindow.backbutton, TRUE);
			gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[DISK_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.disklabel),
				MainWindow.ActiveStageTitles[DISK_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;
		case TIMEZONE_SCREEN :
#ifdef HIDE_LANGUAGE_SCREEN
			gtk_widget_hide(MainWindow.UsersWindow.userswindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.userlabel),
				MainWindow.InactiveStageTitles[USER_SCREEN]);
#else
			gtk_widget_hide(MainWindow.languagewindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.languagelabel),
				MainWindow.InactiveStageTitles[LANGUAGE_SCREEN]);
#endif /* HIDE_LANGUAGE_SCREEN */
			gtk_widget_show(MainWindow.DateTimeZoneWindow.datetimezonetoplevel);
			gtk_widget_set_sensitive(MainWindow.backbutton, TRUE);
			gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[TIMEZONE_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.timezonelabel),
				MainWindow.ActiveStageTitles[TIMEZONE_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;
		case LANGUAGE_SCREEN :
			gtk_widget_hide(MainWindow.UsersWindow.userswindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.userlabel),
				MainWindow.InactiveStageTitles[USER_SCREEN]);
			gtk_widget_show(MainWindow.languagewindowtable);
			gtk_widget_set_sensitive(MainWindow.backbutton, TRUE);
			gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[LANGUAGE_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.languagelabel),
				MainWindow.ActiveStageTitles[LANGUAGE_SCREEN]);
			help_dialog_refresh(InstallCurrScreen);
			break;
		case USER_SCREEN :
			gtk_widget_hide(
					MainWindow.ConfirmationWindow.confirmationwindowtable);
			gtk_label_set_label(GTK_LABEL(MainWindow.installationlabel),
				MainWindow.InactiveStageTitles[INSTALLATION_SCREEN]);
			gtk_widget_show(MainWindow.UsersWindow.userswindowtable);
			gtk_widget_set_sensitive(MainWindow.backbutton, TRUE);
			gtk_widget_set_sensitive(MainWindow.nextbutton, TRUE);
			gtk_label_set_label(GTK_LABEL(MainWindow.screentitlelabel),
				MainWindow.ScreenTitles[USER_SCREEN]);
			gtk_label_set_label(GTK_LABEL(MainWindow.userlabel),
				MainWindow.ActiveStageTitles[USER_SCREEN]);
			gtk_widget_grab_focus(MainWindow.UsersWindow.rootpassword1entry);
			help_dialog_refresh(InstallCurrScreen);
			break;
	}
}

void
on_installbutton_clicked(GtkButton *button,
			gpointer user_data)
{
	if (!confirmation_agree_license()) {
		g_warning("Must agree to license...\n");
	} else {
		on_nextbutton_clicked(GTK_BUTTON(MainWindow.nextbutton), user_data);
	}
}

void
on_upgradebutton_clicked(GtkButton *button,
			gpointer user_data)
{
	if (!confirmation_agree_license()) {
		g_warning("Must agree to license\n");
	} else {
		on_nextbutton_clicked(GTK_BUTTON(MainWindow.nextbutton), user_data);
	}
}

void
on_rebootbutton_clicked(GtkButton *button,
			gpointer user_data)
{
	gchar *command_path = NULL;
	gchar *command_output = NULL;
	gchar *command_error = NULL;
	gint status = 0;

	/*
	 * Reboot the system.  We don't eject the media first because reboot is
	 * actually on the media.
	 */
	g_message("Rebooting the system NOW!.....\n");
	command_path = g_find_program_in_path(REBOOT);
	if (command_path) {
		execl(command_path, REBOOT, NULL);
		g_warning("Failed to exec %s: %s",
		    command_path,
		    g_strerror(errno));
		g_free(command_path);
	} else
		g_warning("Can't find reboot command in PATH!\n");
	exit(0); /* Not normally reached */
}

void
on_users_entry_changed(GtkEditable *editable,
			gpointer user_data)
{
	g_object_set_data(G_OBJECT(editable), "changed", GINT_TO_POINTER(TRUE));

	/* Clear the info/warning labels */
	users_clear_info_warning_labels();
}

gboolean
on_username_focus_out_event(GtkWidget *widget,
			GdkEventFocus *event,
			gpointer user_data)
{
	/* For fields that don't have a specific focus out event */
	/* Just check if field is selected and unselect */
	users_entry_unselect_text(widget);

	return (FALSE);
}

gboolean
on_hostname_focus_out_event(GtkWidget *widget,
			GdkEventFocus *event,
			gpointer user_data)
{
	/* For fields that don't have a specific focus out event */
	/* Just check if field is selected and unselect */
	if (users_validate_host_name(FALSE)) {
		if (MainWindow.UsersWindow.error_posted == TRUE) {
			MainWindow.UsersWindow.error_posted = FALSE;
		} else {
			users_clear_info_warning_labels();
			users_entry_unselect_text(widget);
		}
	}

	return (FALSE);
}

gboolean
on_rootpassword_focus_out_event(GtkWidget *widget,
			GdkEventFocus *event,
			gpointer user_data)
{
	if (users_validate_root_passwords(widget, FALSE)) {
		/* Clear the info/warning labels */
		if (MainWindow.UsersWindow.error_posted == TRUE) {
			MainWindow.UsersWindow.error_posted = FALSE;
		} else {
			users_clear_info_warning_labels();
			users_entry_unselect_text(widget);
		}
	}
	return (FALSE);
}

gboolean
on_loginname_focus_out_event(GtkWidget *widget,
			GdkEventFocus *event,
			gpointer user_data)
{
	if (users_validate_login_name(FALSE)) {
		/* Clear the info/warning labels */
		if (MainWindow.UsersWindow.error_posted == TRUE) {
			MainWindow.UsersWindow.error_posted = FALSE;
		} else {
			users_clear_info_warning_labels();
			users_entry_unselect_text(widget);
		}
	}
	return (FALSE);
}

gboolean
on_userpassword_focus_out_event(GtkWidget *widget,
			GdkEventFocus *event,
			gpointer user_data)
{
	if (users_validate_user_passwords(widget, FALSE)) {
		/* Clear the info/warning labels */
		if (MainWindow.UsersWindow.error_posted == TRUE) {
			MainWindow.UsersWindow.error_posted = FALSE;
		} else {
			users_clear_info_warning_labels();
			users_entry_unselect_text(widget);
		}
	}
	return (FALSE);
}


void
on_licensecheckbutton_toggled(GtkToggleButton *togglebutton,
			gpointer user_data)
{
	GtkWidget *button;

	switch (InstallationProfile.installationtype) {
		case INSTALLATION_TYPE_INITIAL_INSTALL:
			button = MainWindow.installbutton;
			break;
		case INSTALLATION_TYPE_INPLACE_UPGRADE:
			button = MainWindow.upgradebutton;
			break;
	}

	gtk_widget_set_sensitive(button,
			gtk_toggle_button_get_active(togglebutton));
}

/* How about a nice cup of tea */
static gboolean
would_you_like_to_install_instead(void)
{
	gboolean retval;

	retval = gui_install_prompt_dialog(TRUE, FALSE, FALSE,
	    GTK_MESSAGE_WARNING,
	    _("No upgradeable OpenSolaris Environments"),
	    _("Would you like to install?"));
	return (retval);
}