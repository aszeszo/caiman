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

#ifndef _TIMEZONE_H_
#define _TIMEZONE_H_

#include <gtk/gtk.h>

G_BEGIN_DECLS

#define TIMEZONE_TYPE	(timezone_get_type())
#define TIMEZONE(obj)	(G_TYPE_CHECK_INSTANCE_CAST((obj),\
								TIMEZONE_TYPE, Timezone))
#define TIMEZONE_CLASS(klass)	(G_TYPE_CHECK_CLASS_CAST((klass),\
										TIMEZONE_TYPE, TimezoneClass))
#define TIMEZONE_GET_CLASS(obj)	(G_TYPE_INSTANCE_GET_CLASS((obj),\
										TIMEZONE_TYPE, TimezoneClass))
#define IS_TIMEZONE(obj)		(G_TYPE_CHECK_INSTANCE_TYPE((obj),\
										TIMEZONE_TYPE))
#define IS_TIMEZONE_CLASS(klass)	(G_TYPE_CHECK_CLASS_TYPE((klass),\
											TIMEZONE_TYPE))
typedef struct _Timezone	Timezone;
typedef struct _TimezonePrivate	TimezonePrivate;
typedef struct _TimezoneClass	TimezoneClass;

struct _Timezone
{
	GtkVBox widget;

	TimezonePrivate *priv;
};

struct _TimezoneClass
{
	GtkVBoxClass parent_class;
};

GtkType	timezone_get_type(void);
GtkWidget	*timezone_new(void);
GtkWidget	*timezone_get_continent_combo(Timezone *timezone);
GtkWidget	*timezone_get_country_combo(Timezone *timezone);
GtkWidget	*timezone_get_timezone_combo(Timezone *timezone);
GtkWidget	*timezone_get_continent_label(Timezone *timezone);
GtkWidget	*timezone_get_country_label(Timezone *timezone);
GtkWidget	*timezone_get_timezone_label(Timezone *timezone);
gboolean	timezone_get_selected_tz(Timezone *timezone,
		InstallationProfileType *profile);
void		timezone_set_default_focus(Timezone *timezone);

G_END_DECLS

#endif
