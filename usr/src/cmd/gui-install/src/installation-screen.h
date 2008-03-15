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

#ifndef __INSTALLATION_SCREEN_H
#define	__INSTALLATION_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glade/glade.h>

#define	TWO_SECONDS		2000
#define	FIVE_SECONDS	5000
#define	TEN_SECONDS		10000
#define	SIXTY_SECONDS	60000
#define	INSTALLATION_TIMEOUT_SECONDS	TWO_SECONDS

#define	INSTALLATION_IMAGE_CYCLE		(SIXTY_SECONDS/1000)

typedef struct _InstallationWindowXML {
	GtkWidget *installationwindowtable;
	GtkWidget *installationframe;
	GtkWidget *installationalignment;
	GtkWidget *installationeventbox;
	GtkWidget *installationimage;
	GtkWidget *installationinfolabel;
	GtkWidget *installationprogressbar;

	GList *install_files;
	GList *current_install_file;
	gchar *current_install_message;
	double progress_bar_fraction;
	double current_fraction;

	GTimer *marketing_timer;
	gboolean marketing_entered;
	gboolean tools_install_started;
} InstallationWindowXML;

void		installation_window_init(void);

void		installation_window_load_widgets(void);

void		installation_window_set_contents(void);

gboolean	installation_next_step(gpointer data);

gboolean	installation_file_enter(GtkWidget *widget,
				GdkEventCrossing *event,
				gpointer user_data);

gboolean	installation_file_leave(GtkWidget *widget,
				GdkEventCrossing *event,
				gpointer user_data);

gboolean	installation_file_key_release(GtkWidget *widget,
				GdkEventKey *event,
				gpointer user_data);

void		installation_window_start_install(void);

const gchar*	lookup_callback_type(int callback);

const gchar*	lookup_milestone_type(int milestone);

void		installation_update_progress(om_callback_info_t *cb_data,
				uintptr_t app_data);

gboolean	installation_get_dummy_install(void);

#ifdef __cplusplus
}
#endif

#endif /* __INSTALLATION_SCREEN_H */
