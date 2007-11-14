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

#ifndef _DISKBUTTON_H_
#define	_DISKBUTTON_H_

#pragma ident	"@(#)diskbutton.h	1.2	07/08/23 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif
#include <glib.h>
#include <glib-object.h>
#include <gtk/gtkwidget.h>
#include <orchestrator-wrappers.h>

G_BEGIN_DECLS

#define	DISKBUTTON_TYPE			(disk_button_get_type())
#define	DISKBUTTON(obj)			(G_TYPE_CHECK_INSTANCE_CAST((obj),\
				DISKBUTTON_TYPE, DiskButton))
#define	DISKBUTTON_CLASS(klass)		(G_TYPE_CHECK_CLASS_CAST((klass),\
				DISKBUTTON_TYPE, DiskButtonClass))
#define	DISKBUTTON_GET_CLASS(obj)	(G_TYPE_INSTANCE_GET_CLASS((obj),\
				DISKBUTTON_TYPE, DiskButtonClass))
#define	IS_DISKBUTTON(obj)		(G_TYPE_CHECK_INSTANCE_TYPE((obj),\
				DISKBUTTON_TYPE))
#define	IS_DISKBUTTON_CLASS(klass)	(G_TYPE_CHECK_CLASS_TYPE((klass),\
				DISKBUTTON_TYPE))


typedef struct _DiskButton DiskButton;
typedef struct _DiskButtonPrivate DiskButtonPrivate;
typedef struct _DiskButtonClass  DiskButtonClass;

enum diskstate
{
	DISK_SELECTED = 0,
	DISK_UNSELECTED,
	DISK_STATE
};

struct _DiskButton
{
	GtkHBox widget;

	DiskButtonPrivate *priv;
};

struct _DiskButtonClass
{
	GtkHBoxClass parent_class;

	/* all radio buttons belong to one group */
	GSList *group;
	GList *radios;

	GdkPixbuf *disk_image[DISK_STATE];
};

GType		disk_button_get_type(void);

guint		disk_button_get_nactive(DiskButton *button);

/* set the first sensitive system radio button in the disk button as active */
gboolean	disk_button_set_default_active(DiskButton *button);

void		disk_button_hide_bar(DiskButton *button);

void		disk_button_get_upgrade_info(disk_info_t **dinfo,
    upgrade_info_t **uinfo);

GList*		disk_button_get_radio_buttons(DiskButton *button);

GtkWidget*	disk_button_new(disk_info_t *disk);

void		disk_button_disable_radio_button(GtkRadioButton *radiobutton,
    const gchar *reason);

G_END_DECLS

#ifdef __cplusplus
}
#endif

#endif /* _DISKBUTTON_H_ */
