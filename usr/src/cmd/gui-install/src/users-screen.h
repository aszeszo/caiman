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

#ifndef __USERS_SCREEN_H
#define	__USERS_SCREEN_H

#define	MAX_LOGIN_NAME_LEN	8

#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glade/glade.h>

typedef struct _UsersWindowXML {
	GtkWidget *userswindowtable;
	GtkWidget *rootpassword1entry;
	GtkWidget *rootpassword2entry;
	GtkWidget *rootpasswordinfotable;
	GtkWidget *rootpasswordinfoimage;
	GtkWidget *rootpasswordinfolabel;
	GtkWidget *usernameentry;
	GtkWidget *loginnameentry;
	GtkWidget *loginnameinfotable;
	GtkWidget *loginnameinfoimage;
	GtkWidget *loginnameinfolabel;
	GtkWidget *userpassword1entry;
	GtkWidget *userpassword2entry;
	GtkWidget *userpasswordinfotable;
	GtkWidget *userpasswordinfoimage;
	GtkWidget *userpasswordinfolabel;
	GtkWidget *hostnameentry;
	GtkWidget *hostnameinfotable;
	GtkWidget *hostnameinfoimage;
	GtkWidget *hostnameinfolabel;

	gboolean error_posted;
} UsersWindowXML;

void		users_window_init(void);

void		users_load_widgets(void);

gboolean	users_validate(void);

void		users_clear_info_warning_labels(void);

gboolean	users_validate_root_passwords(GtkWidget *widget,
				gboolean check_changed);

gboolean	users_validate_login_name(gboolean check_changed);

gboolean	users_validate_user_passwords(GtkWidget *widget,
				gboolean check_changed);

gboolean	users_validate_host_name(gboolean check_changed);

gboolean	user_account_entered(void);

gboolean	root_password_entered(void);

void		users_store_data(void);

void		users_entry_unselect_text(GtkWidget *widget);

void		users_entry_select_text(GtkWidget *widget);

gboolean	users_password_key_press(GtkWidget *entry,
				GdkEventKey *event,
				gpointer user_data);

gboolean	users_password_button_press(GtkWidget *entry,
				GdkEventButton *event,
				gpointer user_data);

#ifdef __cplusplus
}
#endif

#endif /* __USERS_SCREEN_H */
