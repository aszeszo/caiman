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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef __INSTALLATION_DISK_SCREEN_H
#define	__INSTALLATION_DISK_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#define	GUI_INSTALL_FDISK_TABLE_ROWS	6
#define	LOGICAL_COMBOBOX_INDENT	12
#define	IS_EXT_PAR(type)	((type) == EXTDOS || \
	(type) == FDISK_EXT_WIN || \
	(type) == FDISK_EXTLBA)
#define	IS_SOLARIS_PAR(type, contenttype)	((type) == SUNIXOS2 || \
	((type) == SUNIXOS && contenttype != OM_CTYPE_LINUXSWAP)) \

typedef enum {
	UNUSED_PARTITION = 0,
	SOLARIS_PARTITION,
	EXTENDED_PARTITION,
	NUM_DEFAULT_PARTITIONS  /* Not an actual partition type */
} DefaultPartType;

/* Linked list of logical partitions displayed */
typedef struct _LogicalPartition {
	GtkWidget *typealign;
	GtkWidget *typecombo;
	GtkWidget *sizespinner;
	GtkWidget *availlabel;
	GtkWidget *warningbox;
	GtkWidget *warningimage;
	GtkWidget *warninglabel;
	int partcombosaved;
	gboolean sizechange;
	gboolean typechange;
	gulong combochangehandler;
	gulong spinnerchangehandler;
	gulong spinnerinserthandler;
	gulong spinnerdeletehandler;
	gint logpartindex;
	struct _LogicalPartition *next;
} LogicalPartition;

typedef struct _InstallationDiskWindowXML {
	GtkWidget *diskselectiontoplevel;
	GtkWidget *custompartitioningvbox;
	GtkWidget *disksviewport;
	GtkWidget *diskselectionhscrollbar;
	GtkWidget *diskerrorimage;
	GtkWidget *diskwarningimage;
	GtkWidget *diskstatuslabel;
	GtkWidget *diskwarninghbox;
	GtkWidget *partcombo[FD_NUMPART];
	GtkWidget *partspin[FD_NUMPART];
	GtkWidget *partwarnbox[FD_NUMPART];
	GtkWidget *partavail[FD_NUMPART];
	GtkWidget *resetbutton;
	GtkWidget *fdiskscrolledwindow;
	GtkWidget *fdiskviewport;
	GtkWidget *fdisktable;
	guint fdisktablerows;
	int partcombosaved[FD_NUMPART];
	guint partrow[FD_NUMPART];
	gboolean parttypechanges[FD_NUMPART];
	gboolean partsizechanges[FD_NUMPART];
	gboolean initialsizechange[FD_NUMPART];
	LogicalPartition *startlogical[FD_NUMPART];
	guint numpartlogical[FD_NUMPART];
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

void		installationdisk_screen_set_default_focus(gboolean back_button);

gchar *		installationdisk_parttype_to_string(partition_info_t *partinfo);


#ifdef __cplusplus
}
#endif

#endif /* __INSTALLATION_DISK_SCREEN_H */
