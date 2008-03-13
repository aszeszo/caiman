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

#ifndef __INSTALLATION_DISK_SCREEN_H
#define	__INSTALLATION_DISK_SCREEN_H

#pragma ident	"@(#)installation-disk-screen.h	1.1	07/08/03 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#define	GUI_INSTALL_NUMPART	4

typedef struct _InstallationDiskWindowXML {
	GtkWidget *diskselectiontoplevel;
	GtkWidget *custompartitioningvbox;
	GtkWidget *disksviewport;
	GtkWidget *diskselectionhscrollbar;
	GtkWidget *diskerrorimage;
	GtkWidget *diskwarningimage;
	GtkWidget *diskstatuslabel;
	GtkWidget *diskwarninghbox;
	GtkWidget *partitioncombos[GUI_INSTALL_NUMPART];
	GtkWidget *partitionspinners[GUI_INSTALL_NUMPART];
	GtkWidget *partitionwarningboxes[GUI_INSTALL_NUMPART];
	GtkWidget *resetbutton;
	GtkWidget *diskspaceentry;
} InstallationDiskWindowXML;

/* Glade XML referenced callback functions */
void		installationdisk_wholediskradio_toggled(GtkWidget *widget,
				gpointer user_data);

void		installationdisk_partitiondiskradio_toggled(GtkWidget *widget,
				gpointer user_data);

/* UI initialisation functions */
void		installationdisk_xml_init(void);

void		installationdisk_ui_init(void);

gboolean	installationdisk_validate(void);

void		installation_disk_store_data(void);

#ifdef __cplusplus
}
#endif

#endif /* __INSTALLATION_DISK_SCREEN_H */
