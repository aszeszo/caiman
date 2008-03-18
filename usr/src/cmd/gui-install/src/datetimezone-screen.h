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

#ifndef __DATETIMEZONE_SCREEN_H
#define	__DATETIMEZONE_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glade/glade.h>
#include <libzoneinfo.h>
#include <installation-profile.h>

typedef struct _DateTimeZoneWindowXML {
	GtkWidget *datetimezonetoplevel;
	GtkWidget *timezonetoplevel;
	GtkWidget *regioncombobox;
	GtkWidget *countrycombobox;
	GtkWidget *timezonecombobox;
	GtkWidget *yearspinner;
	GtkWidget *monthspinner;
	GtkWidget *dayspinner;
	GtkWidget *hourspinner;
	GtkWidget *minutespinner;
	GtkWidget *ampmcombobox;
	GtkWidget *timezonealign;
	GtkWidget *timezone;
} DateTimeZoneWindowXML;

/* Callbacks referenced in the Glade XML file */
void		on_yearspinner_value_changed(GtkWidget *widget,
				gpointer user_data);

void		on_monthspinner_value_changed(GtkWidget *widget,
				gpointer user_data);

void		on_dayspinner_value_changed(GtkWidget *widget,
				gpointer user_data);

void		on_hourspinner_value_changed(GtkWidget *widget,
				gpointer user_data);

void		on_minutespinner_value_changed(GtkWidget *widget,
				gpointer user_data);

void		datetimezone_xml_init(void);

void		datetimezone_ui_init(void);

void		timezone_cleanup(void);

gboolean	get_selected_tz(InstallationProfileType *profile);

void		datetimezone_set_system_clock(gboolean reallysetit);

#ifdef __cplusplus
}
#endif

#endif /* __DATETIMEZONE_SCREEN_H */
