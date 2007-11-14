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
#pragma ident	"@(#)installation-disk-screen.c	1.7	07/10/24 SMI"

#include <ctype.h>

#include <gnome.h>
#include "callbacks.h"
#include "interface-globals.h"
#include "window-graphics.h"
#include "installation-disk-screen.h"
#include "installation-profile.h"
#include "orchestrator-wrappers.h"

/*
 * Made up, hardcoded guess size in the absence of any API
 * Yes, it sucks. Size is in GB
 */
#define	RECOMMENDED_INSTALL_SIZE	20

/* Uncomment these 2 lines to simulate Sparc behaviour on X86 */
/* #define __sparc */
/* #undef __i386 */

typedef enum {
	DISK_STATUS_OK = 0,  /* Disk is fine for installation */
	DISK_STATUS_CANT_PRESERVE, /* Partition table is unreadable */
	DISK_STATUS_TOO_SMALL, /* Disk is too small - unusable */
	DISK_STATUS_NO_MEDIA, /* If size (in kb or mb = 0) */
	DISK_STATUS_NO_DISKINFO, /* Indicates target discovery error */
	DISK_STATUS_WARNING /* For some future use */
} DiskStatus;

/* Num of target disks found, including unusable ones */
gint numdisks = 0;
/* Currently selected disk */
gint activedisk = -1;
gboolean activediskisreadable = FALSE;

DiskStatus *alldiskstatus = NULL;
/* Ptr array of all disks - linked lists suck for random access */
disk_info_t **alldiskinfo = NULL;
/*
 * Original reference copy of actual disk layout
 * (or the default layout if unreadable)
 */
disk_parts_t **originalpartitions = NULL;
/* Working copy of the above. Customisations written here */
disk_parts_t **modifiedpartitions = NULL;
/* Points to either one of the above */
disk_parts_t **proposedpartitions = NULL;
/* A suggested layout that has one Solaris2 partition for the entire disk */
disk_parts_t **defaultpartitions = NULL;

/* Keeps track of which partitions get wiped for each disk */
typedef struct _parttypeflag {
	gboolean partid[GUI_INSTALL_NUMPART];
} PartTypeFlag;

typedef struct _partsizeflag {
	gboolean partid[GUI_INSTALL_NUMPART];
} PartSizeFlag;

PartTypeFlag *parttypechanges = NULL;
PartSizeFlag *partsizechanges = NULL;


/*
 * Signal handler id storage so we can easily block/unblock
 * the partitioning signal handlers that handle text insert
 * and delete events.
 */
gulong spininserthandlers[GUI_INSTALL_NUMPART] = {0, 0, 0, 0};
gulong spindeletehandlers[GUI_INSTALL_NUMPART] = {0, 0, 0, 0};

GtkWidget *hbuttonbox;
GtkWidget **diskbuttons;
GtkAdjustment *viewportadjustment = NULL;
GtkWidget *scanningbox = NULL;
GtkIconTheme *icontheme;

/*
 * Partition type to string mappings.
 * Lifted straight out of fdisk.c
 */
static char Dstr[] = "DOS12";
static char D16str[] = "DOS16";
static char DDstr[] = "DOS-DATA";
static char EDstr[] = "EXT-DOS";
static char DBstr[] = "DOS-BIG";
static char PCstr[] = "PCIX";
static char Ustr[] = "UNIX System";
static char SUstr[] = "Solaris";
static char SU2str[] = "Solaris";
static char X86str[] = "x86 Boot";
static char DIAGstr[] = "Diagnostic";
static char IFSstr[] = "IFS: NTFS";
static char AIXstr[] = "AIX Boot";
static char AIXDstr[] = "AIX Data";
static char OS2str[] = "OS/2 Boot";
static char WINstr[] = "Win95 FAT32";
static char EWINstr[] = "Ext Win95";
static char FAT95str[] = "FAT16 LBA";
static char EXTLstr[] = "EXT LBA";
static char LINUXstr[] = "Linux";
static char LINSWPstr[] = "Linux swap";
static char CPMstr[] = "CP/M";
static char NOVstr[] = "Netware 3.x+";
static char QNXstr[] = "QNX 4.x";
static char QNX2str[] = "QNX part 2";
static char QNX3str[] = "QNX part 3";
static char LINNATstr[] = "Linux native";
static char NTFSVOL1str[] = "NT volset 1";
static char NTFSVOL2str[] = "NT volset 2";
static char BSDstr[] = "BSD OS";
static char NEXTSTEPstr[] = "NeXTSTEP";
static char BSDIFSstr[] = "BSDI FS";
static char EFIPMBRstr[] = "EFI PMBR";
static char EFIstr[] = "EFI";

/* Forward declaration */

static void
disk_selection_set_active_disk(int disknum);

static void
disk_partitioning_set_from_parts_data(disk_info_t *diskinfo,
	disk_parts_t *partitions);

static void
disk_partitioning_adjust_free_space(disk_info_t *diskinfo,
	disk_parts_t *partitions);

static GtkWidget*
disk_toggle_button_new_with_label(const gchar *label,
	DiskStatus status);

static void
disk_viewport_ui_init(GtkViewport *viewport);

static gchar*
disk_viewport_create_disk_tiptext(guint disknum);

static gchar *
disk_viewport_create_disk_label(guint disknum);

static void
disk_viewport_diskbuttons_init(GtkViewport *viewport);

static void
disk_comboboxes_ui_init(void);

static void
disk_combobox_ui_init(GtkComboBox *combobox);

static void
disk_partitioning_block_all_handlers(void);

static void
disk_partitioning_unblock_all_handlers(void);

static void
disk_partitioning_block_combobox_handlers(gint mask);

static void
disk_partitioning_unblock_combobox_handlers(gint mask);

static void
disk_partitioning_block_spinbox_handlers(gint mask);

static void
disk_partitioning_unblock_spinbox_handlers(gint mask);

static void
spinners_insert_text_filter(GtkEntry *widget,
	const gchar *newtext,
	gint length,
	gint *position,
	gpointer user_data);

static void
spinners_delete_text_filter(GtkEditable *widget,
	gint start_pos,
	gint end_pos,
	gpointer user_data);

static void
disk_partitioning_set_sensitive(gboolean sensitive);

static gboolean
disk_partitioning_button_focus_handler(GtkWidget *widget,
	GdkEventFocus *event,
	gpointer user_data);

static void
init_disk_status(void);

static DiskStatus
get_disk_status(guint disknum);

static disk_parts_t *
installation_disk_create_default_layout(disk_info_t *diskinfo);

static gboolean
partition_discovery_monitor(gpointer user_data);

static void
update_disk_partitions_from_ui(
    disk_info_t  *diskinfo,
    disk_parts_t *partitions,
    PartTypeFlag *typechanges,
    PartSizeFlag *sizechanges);

/* Real Glade XML referenced callbacks */
void
installationdisk_wholediskradio_toggled(GtkWidget *widget, gpointer user_data)
{
#if defined(__i386)
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget)) == FALSE)
		return;

	proposedpartitions[activedisk] = defaultpartitions[activedisk];
	gtk_widget_hide(
	    MainWindow.InstallationDiskWindow.custompartitioningvbox);
	gtk_widget_show(
	    MainWindow.InstallationDiskWindow.diskwarninghbox);
#endif
}

void
installationdisk_partitiondiskradio_toggled(GtkWidget *widget,
	gpointer user_data)
{
#if defined(__i386)
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget)) == FALSE)
		return;

	proposedpartitions[activedisk] = modifiedpartitions[activedisk];
	gtk_widget_hide(
	    MainWindow.InstallationDiskWindow.diskwarninghbox);
	gtk_widget_show(
	    MainWindow.InstallationDiskWindow.custompartitioningvbox);
#endif
}

static void
show_warning_message(GtkWidget *warning, gboolean show)
{
	if (show == TRUE)
		gtk_widget_show(warning);
	else
		gtk_widget_hide(warning);
}

static void
update_data_loss_warnings(PartTypeFlag *types, PartSizeFlag *sizes)
{
	gint i = 0;
	static GtkWidget **warnings = NULL;
	if (!warnings) {
		warnings = g_new0(GtkWidget *, GUI_INSTALL_NUMPART);
		for (i = 0; i < GUI_INSTALL_NUMPART; i++)
			warnings[i] =
			    MainWindow.InstallationDiskWindow.partitionwarningboxes[i];
	}

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		if (types->partid[i] ||
			sizes->partid[i]) {
			show_warning_message(warnings[i], TRUE);
		} else
			show_warning_message(warnings[i], FALSE);
	}
}

static void
partition_combo_changed(GtkWidget *widget,
    gint partindex,
    gpointer user_data)
{
#if defined(__i386)
	GtkWidget *spinner = NULL;
	gpointer objectdata = NULL;
	disk_parts_t *partitions;
	int index;

	spinner =
	    MainWindow.InstallationDiskWindow.partitionspinners[partindex];
	index = gtk_combo_box_get_active(GTK_COMBO_BOX(widget));
	if (index == 0) { /* Denotes Unused partition */
		gtk_spin_button_set_range(GTK_SPIN_BUTTON(spinner), 0, 0);
		gtk_spin_button_set_value(GTK_SPIN_BUTTON(spinner), 0);
		gtk_widget_set_sensitive(spinner, FALSE);
		/* Partition size gets nuked so set the flag */
		if (activediskisreadable)
			partsizechanges[activedisk].partid[partindex] = TRUE;
	} else {
		if (gtk_spin_button_get_value(GTK_SPIN_BUTTON(spinner)) == 0) {
			gchar *sizestr;
			gfloat size =
				orchestrator_om_get_disk_sizegb(alldiskinfo[activedisk]);
			sizestr = g_strdup_printf("%.1f", size);
			gtk_spin_button_set_range(GTK_SPIN_BUTTON
			    (spinner),
			    0.1,
			    atof(sizestr));
			g_free(sizestr);
			gtk_spin_button_set_value(GTK_SPIN_BUTTON(spinner), 1.0);
			/* Partition size also changes from 0 to 1gb so set the flag */
			if (activediskisreadable)
				partsizechanges[activedisk].partid[partindex] = TRUE;
		}
		gtk_widget_set_sensitive(spinner, TRUE);
	}

	objectdata = g_object_get_data(G_OBJECT(widget), "extra_fs");
	if ((objectdata != NULL) && (GPOINTER_TO_INT(objectdata) == TRUE)) {
		gtk_combo_box_remove_text(GTK_COMBO_BOX(widget), 2);
		g_object_set_data(G_OBJECT(widget),
		    "extra_fs",
		    GINT_TO_POINTER(FALSE));
	}

	if (activediskisreadable == TRUE) {
		parttypechanges[activedisk].partid[partindex] = TRUE;
		update_data_loss_warnings(
			&parttypechanges[activedisk],
			&partsizechanges[activedisk]);
	}

	partitions = modifiedpartitions[activedisk];
	update_disk_partitions_from_ui(alldiskinfo[activedisk],
		partitions,
		&parttypechanges[activedisk],
		&partsizechanges[activedisk]);
	disk_partitioning_adjust_free_space(alldiskinfo[activedisk], partitions);

	g_object_set_data(G_OBJECT(diskbuttons[activedisk]),
		"modified",
		GINT_TO_POINTER(TRUE));
	gtk_widget_set_sensitive(GTK_WIDGET(
		MainWindow.InstallationDiskWindow.resetbutton),
		TRUE);
#endif
}

void
partition_0_combo_changed(GtkWidget *widget, gpointer user_data)
{
	partition_combo_changed(widget, 0, user_data);
}

void
partition_1_combo_changed(GtkWidget *widget, gpointer user_data)
{
	partition_combo_changed(widget, 1, user_data);
}

void
partition_2_combo_changed(GtkWidget *widget, gpointer user_data)
{
	partition_combo_changed(widget, 2, user_data);
}

void
partition_3_combo_changed(GtkWidget *widget, gpointer user_data)
{
	partition_combo_changed(widget, 3, user_data);
}

static void
partition_spinner_value_changed(GtkWidget *widget,
	gint index,
	gpointer user_data)
{

#if defined(__i386)
	static GtkComboBox **combos = NULL;
	static GtkSpinButton **spinners = NULL;

	if (combos == NULL) {
		gint i = 0;
		combos = g_new0(GtkComboBox *, GUI_INSTALL_NUMPART);
		spinners = g_new0(GtkSpinButton *, GUI_INSTALL_NUMPART);
		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			combos[i] = GTK_COMBO_BOX(MainWindow.InstallationDiskWindow.partitioncombos[i]);
			spinners[i] = GTK_SPIN_BUTTON(MainWindow.InstallationDiskWindow.partitionspinners[i]);
		}
	}

	if (activediskisreadable == TRUE) {
		partsizechanges[activedisk].partid[index] = TRUE;
		/*
		 * Domino effect on subsequent partitions.
		 */
		if (index < GUI_INSTALL_NUMPART - 1) {
			/* If next partition contains an exisiting partition, nuke it */
			if ((partsizechanges[activedisk].partid[index+1] == FALSE) &&
				(gtk_combo_box_get_active(combos[index+1]) != 0)) {
				partsizechanges[activedisk].partid[index+1] = TRUE;
				gtk_combo_box_set_active(combos[index+1], 0);
			}
		}
	}

	update_data_loss_warnings(
		&parttypechanges[activedisk],
		&partsizechanges[activedisk]);
	update_disk_partitions_from_ui(alldiskinfo[activedisk],
		modifiedpartitions[activedisk],
		&parttypechanges[activedisk],
		&partsizechanges[activedisk]);
	disk_partitioning_adjust_free_space(alldiskinfo[activedisk],
		modifiedpartitions[activedisk]);

	g_object_set_data(G_OBJECT(diskbuttons[activedisk]),
		"modified",
		GINT_TO_POINTER(TRUE));
	gtk_widget_set_sensitive(GTK_WIDGET(
		MainWindow.InstallationDiskWindow.resetbutton),
		TRUE);
#endif
}

void
partition_0_spinner_value_changed(GtkWidget *widget, gpointer user_data)
{
	partition_spinner_value_changed(widget, 0, user_data);
}

void
partition_1_spinner_value_changed(GtkWidget *widget, gpointer user_data)
{
	partition_spinner_value_changed(widget, 1, user_data);
}

void
partition_2_spinner_value_changed(GtkWidget *widget, gpointer user_data)
{
	partition_spinner_value_changed(widget, 2, user_data);
}

void
partition_3_spinner_value_changed(GtkWidget *widget, gpointer user_data)
{
	partition_spinner_value_changed(widget, 3, user_data);
}

void
disk_partitioning_reset_button_clicked(GtkWidget *widget, gpointer user_data)
{
#if defined(__i386)
	gint i = 0;

	if (activedisk < 0)
		return;
	om_free_disk_partition_info(omhandle, modifiedpartitions[activedisk]);
	switch (get_disk_status(activedisk)) {
		case DISK_STATUS_OK:
			modifiedpartitions[activedisk] =
				orchestrator_om_partitions_dup(originalpartitions[activedisk]);
			break;
		case DISK_STATUS_CANT_PRESERVE:
			modifiedpartitions[activedisk] =
				orchestrator_om_partitions_dup(defaultpartitions[activedisk]);
			break;
		case DISK_STATUS_TOO_SMALL:
			g_warning("It shouldn't have been possible to"
				"partition a disk that's too small\n");
			break;
	}

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		parttypechanges[activedisk].partid[i] = FALSE;
		partsizechanges[activedisk].partid[i] = FALSE;
	}
	update_data_loss_warnings(
		&parttypechanges[activedisk],
		&partsizechanges[activedisk]);

	/* Flag for the the reset button to be disabled */
	g_object_set_data(G_OBJECT(diskbuttons[activedisk]),
		"modified",
		GINT_TO_POINTER(FALSE));
	disk_selection_set_active_disk(activedisk);
#endif /* (__i386) */
}

/* Internally referenced callbacks */

static void
installationdisk_diskbutton_toggled(GtkWidget *widget, gpointer user_data)
{
	gint disknum;
	disknum = GPOINTER_TO_INT(user_data);
	if (gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(widget)) == FALSE)
		return;

	disk_selection_set_active_disk(disknum);
}


/* Callbacks to make GtkLabel expand to line wrap correctly inside it's container */
static void
partchoicelabel_container_size_allocate(GtkWidget *widget,
	GtkAllocation *allocation,
	gpointer user_data)
{

	g_return_if_fail(GTK_IS_WIDGET(user_data));
	gtk_widget_set_size_request(GTK_WIDGET(user_data),
		allocation->width, -1);

	g_signal_handlers_disconnect_by_func(G_OBJECT(widget),
		(gpointer) partchoicelabel_container_size_allocate,
		user_data);
}

static void
custinfolabel_container_size_allocate(GtkWidget *widget,
	GtkAllocation *allocation,
	gpointer user_data)
{

	g_return_if_fail(GTK_IS_WIDGET(user_data));
	gtk_widget_set_size_request(GTK_WIDGET(user_data),
		allocation->width, -1);
	g_signal_handlers_disconnect_by_func(G_OBJECT(widget),
		(gpointer) custinfolabel_container_size_allocate,
		user_data);
}

static void
partsfoundlabel_container_size_allocate(GtkWidget *widget,
	GtkAllocation *allocation,
	gpointer user_data)
{
	g_return_if_fail(GTK_IS_WIDGET(user_data));
	gtk_widget_set_size_request(GTK_WIDGET(user_data),
		allocation->width, -1);
	g_signal_handlers_disconnect_by_func(G_OBJECT(widget),
		(gpointer) partsfoundlabel_container_size_allocate,
		user_data);
}

static void
unreadpartslabel_container_size_allocate(GtkWidget *widget,
			GtkAllocation *allocation,
			gpointer user_data)
{
	static gboolean beentherdonethat = FALSE;
	if (beentherdonethat == TRUE)
		return;
	g_return_if_fail(GTK_IS_WIDGET(user_data));
	gtk_widget_set_size_request(GTK_WIDGET(user_data),
			allocation->width, -1);
	beentherdonethat = TRUE;
}

/* UI initialisation functoins */

void
installationdisk_xml_init(void)
{
	gint i = 0; /* For preview release hack */

	MainWindow.installationdiskwindowxml = glade_xml_new(GLADEDIR "/" INSTALLATIONDISKFILENAME, DISKNODE, NULL);
	MainWindow.InstallationDiskWindow.diskselectiontoplevel =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskselectiontoplevel");
	MainWindow.InstallationDiskWindow.custompartitioningvbox =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"custompartitioningvbox");
	MainWindow.InstallationDiskWindow.disksviewport =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"disksviewport");
	MainWindow.InstallationDiskWindow.diskselectionhscrollbar =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskselectionhscrollbar");
	MainWindow.InstallationDiskWindow.diskerrorimage =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskerrorimage");
	MainWindow.InstallationDiskWindow.diskwarningimage =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskwarningimage");
	MainWindow.InstallationDiskWindow.diskstatuslabel =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskstatuslabel");
	MainWindow.InstallationDiskWindow.diskwarninghbox =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskwarninghbox");

	/* Partition combo boxes */
	MainWindow.InstallationDiskWindow.partitioncombos[0] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition0combo");
	MainWindow.InstallationDiskWindow.partitioncombos[1] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition1combo");
	MainWindow.InstallationDiskWindow.partitioncombos[2] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition2combo");
	MainWindow.InstallationDiskWindow.partitioncombos[3] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition3combo");

	/* Partition spin buttons */
	MainWindow.InstallationDiskWindow.partitionspinners[0] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition0spinner");
	MainWindow.InstallationDiskWindow.partitionspinners[1] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition1spinner");
	MainWindow.InstallationDiskWindow.partitionspinners[2] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition2spinner");
	MainWindow.InstallationDiskWindow.partitionspinners[3] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition3spinner");

	/* Partition warning messages */
	MainWindow.InstallationDiskWindow.partitionwarningboxes[0] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition0warninghbox");
	MainWindow.InstallationDiskWindow.partitionwarningboxes[1] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition1warninghbox");
	MainWindow.InstallationDiskWindow.partitionwarningboxes[2] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition2warninghbox");
	MainWindow.InstallationDiskWindow.partitionwarningboxes[3] =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partition3warninghbox");

	MainWindow.InstallationDiskWindow.resetbutton =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"fdiskresetbutton");
	MainWindow.InstallationDiskWindow.diskspaceentry =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"diskspaceentry");

/*
 * XXX - Preview release hack
 * Can't create partitions of arbitrary size or position in the
 * preview relase. Can only create a partition spanning the entire
 * disk. So disable all the partitioning comboboxes and spinbuttons.
 */
	for (i = 0; i < 4; i++) {
		gtk_widget_set_sensitive(
		    MainWindow.InstallationDiskWindow.partitionspinners[i],
		    FALSE);
		gtk_widget_set_sensitive(
		    MainWindow.InstallationDiskWindow.partitioncombos[i],
		    FALSE);
	}
}

void
label_resize_handlers_init(void)
{
	GtkWidget *label;
	GtkWidget *container;

	/* Set label requistions to occupy the space allocated to them by their parent widgets */
	label =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partitioningchoicelabel");
	container =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partitioningtypevbox");
	g_signal_connect(G_OBJECT(container),
			"size-allocate",
			G_CALLBACK(partchoicelabel_container_size_allocate),
			(gpointer) label);

	label =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"custominfolabel");
	container =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"custompartitioningvbox");
	g_signal_connect(G_OBJECT(container),
		"size-allocate",
		G_CALLBACK(custinfolabel_container_size_allocate),
		(gpointer) label);

	label =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"partsfoundlabel");
	gtk_widget_set_size_request(label, 500, -1);
	g_signal_connect(G_OBJECT(container),
		"size-allocate",
		G_CALLBACK(partsfoundlabel_container_size_allocate),
		(gpointer) label);

	container =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"unreadablepartslabelhbox");
	label =
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
			"unreadablepartslabel");
	g_signal_connect(G_OBJECT(container),
		"size-allocate",
		G_CALLBACK(unreadpartslabel_container_size_allocate),
		(gpointer) label);
}

/*
 * XXX - this is incomplete because theme switching is not directly possible
 * and certainly not supported in the miniroot. When we move to live DVD and
 * full accessibility support becomes a requirement then theme this will need
 * some enhancement (like memory cleanups and remembering the selected disk).
 * This code is a placeholder stub.
 */
void
icon_theme_changed(GtkIconTheme *theme, gpointer user_data)
{
	gtk_widget_destroy(hbuttonbox);
	disk_viewport_diskbuttons_init(GTK_VIEWPORT
		(MainWindow.InstallationDiskWindow.disksviewport));
}

void
installationdisk_ui_init(void)
{
	GdkColor backcolour;
	gfloat minsize = 0;
	gchar *minsizetext = NULL;
	gint i = 0;

	icontheme = gtk_icon_theme_get_default();

	minsize = orchestrator_om_get_mininstall_sizegb();
	minsizetext = g_strdup_printf(_("Recommended size: %dGB Minimum: %.1fGB"),
	    RECOMMENDED_INSTALL_SIZE,
	    minsize);
	gtk_label_set_text(GTK_LABEL
		(glade_xml_get_widget(MainWindow.installationdiskwindowxml, "minsizelabel")),
		minsizetext);
	g_free(minsizetext);

	disk_viewport_ui_init(
		GTK_VIEWPORT(MainWindow.InstallationDiskWindow.disksviewport));
	disk_comboboxes_ui_init();

	gtk_box_pack_start(GTK_BOX(MainWindow.screencontentvbox),
		MainWindow.InstallationDiskWindow.diskselectiontoplevel,
		TRUE,
		TRUE,
		0);

	gdk_color_parse(WHITE_COLOR, &backcolour);
	gtk_widget_modify_bg(MainWindow.InstallationDiskWindow.disksviewport,
		GTK_STATE_NORMAL, &backcolour);

	/* Set it's size request so it doesn't make the window huge */
	gtk_widget_set_size_request(
		MainWindow.InstallationDiskWindow.disksviewport,
		5,
		-1);

	/* Initially hide all partitioning controls until a disk is selected */
	gtk_widget_hide(glade_xml_get_widget(MainWindow.installationdiskwindowxml,
		"partitioningvbox"));
	/* Custom partitioning is not shown initially */
	gtk_widget_hide(MainWindow.InstallationDiskWindow.custompartitioningvbox);

	label_resize_handlers_init();
	/* Connect up scrollbar's adjustment to the viewport */
	viewportadjustment = gtk_range_get_adjustment(GTK_RANGE
		(MainWindow.InstallationDiskWindow.diskselectionhscrollbar));
	gtk_viewport_set_hadjustment(GTK_VIEWPORT
		(MainWindow.InstallationDiskWindow.disksviewport),
		viewportadjustment);

	/* Filter keyboard input on spinbuttons */
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		spininserthandlers[i] = g_signal_connect(G_OBJECT
			(MainWindow.InstallationDiskWindow.partitionspinners[i]),
			"insert-text",
			G_CALLBACK(spinners_insert_text_filter),
			GINT_TO_POINTER(i));
		spindeletehandlers[i] = g_signal_connect(G_OBJECT
			(MainWindow.InstallationDiskWindow.partitionspinners[i]),
			"delete-text",
			G_CALLBACK(spinners_delete_text_filter),
			GINT_TO_POINTER(i));
	}
	glade_xml_signal_autoconnect(MainWindow.installationdiskwindowxml);

	if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] == FALSE) {
		g_timeout_add(200, partition_discovery_monitor, NULL);
	} else { /* Go straight to disk display function */
		partition_discovery_monitor(NULL);
	}
}

/* Initialises UI widgets for the selected disk */
static void
disk_selection_set_active_disk(int disknum)
{
	GtkToggleButton *usewholediskradio;
	DiskStatus status;
	gchar *markup;
	gint partitionsmodified = 0;

	disk_partitioning_block_all_handlers();

	activedisk = disknum;
	/* First see if the disk is large enough for installation */
	status = get_disk_status(disknum);
	switch (status) {
		case DISK_STATUS_OK:
			markup = g_strdup(" ");
			disk_partitioning_set_sensitive(TRUE);
			gtk_label_set_text(GTK_LABEL
				(MainWindow.InstallationDiskWindow.diskstatuslabel),
				markup);
			gtk_widget_hide(MainWindow.InstallationDiskWindow.diskerrorimage);
			gtk_widget_hide(MainWindow.InstallationDiskWindow.diskwarningimage);

			activediskisreadable = TRUE;
			gtk_widget_hide(
				glade_xml_get_widget(MainWindow.installationdiskwindowxml,
					"unreadablepartsouterhbox"));
			gtk_widget_show(
				glade_xml_get_widget(MainWindow.installationdiskwindowxml,
					"partsfoundlabel"));
			g_free(markup);
			break;
		case DISK_STATUS_TOO_SMALL:
			markup = g_strdup_printf("<span font_desc=\"Bold\">%s</span>",
				_("This disk is too small"));
			disk_partitioning_set_sensitive(FALSE);
			gtk_label_set_markup(GTK_LABEL
				(MainWindow.InstallationDiskWindow.diskstatuslabel),
				markup);
			g_free(markup);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskstatuslabel);
			gtk_widget_hide(MainWindow.InstallationDiskWindow.diskwarningimage);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskerrorimage);
			break;
		case DISK_STATUS_NO_MEDIA:
			markup = g_strdup_printf("<span font_desc=\"Bold\">%s</span>",
				_("This storage device contains no media"));
			disk_partitioning_set_sensitive(FALSE);
			gtk_label_set_markup(GTK_LABEL
				(MainWindow.InstallationDiskWindow.diskstatuslabel),
				markup);
			g_free(markup);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskstatuslabel);
			gtk_widget_hide(MainWindow.InstallationDiskWindow.diskwarningimage);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskerrorimage);
			break;
		case DISK_STATUS_CANT_PRESERVE:
			markup = g_strdup_printf("<span font_desc=\"Bold\">%s</span>",
				_("The entire disk will be erased"));
			disk_partitioning_set_sensitive(TRUE);
			gtk_label_set_markup(GTK_LABEL
				(MainWindow.InstallationDiskWindow.diskstatuslabel),
				markup);
			g_free(markup);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskstatuslabel);
			gtk_widget_hide(MainWindow.InstallationDiskWindow.diskerrorimage);
			gtk_widget_show(MainWindow.InstallationDiskWindow.diskwarningimage);
			break;
	}

#if defined(__i386)
	/* Create a default, single partition layout for the disk */
	if (defaultpartitions[disknum] == NULL) {
		defaultpartitions[disknum] =
			installation_disk_create_default_layout(alldiskinfo[disknum]);
	}
	/* Create initial partitioning layouts if necessary */
	if (originalpartitions[disknum] == NULL) {
		if (status == DISK_STATUS_OK) {
			disk_parts_t *partitions;
			char *diskname = g_strdup(alldiskinfo[disknum]->disk_name);
			partitions = orchestrator_om_get_disk_partitions(omhandle,
				diskname);
			originalpartitions[disknum] =
				orchestrator_om_partitions_dup(partitions);
			om_free_disk_partition_info(omhandle, partitions);
			g_free(diskname);
			modifiedpartitions[disknum] =
				orchestrator_om_partitions_dup(originalpartitions[disknum]);
		} else if (status == DISK_STATUS_CANT_PRESERVE) {
			/*
			 * No original partitions can be read so just set it to the
			 * the default partitioning layout.
			 */
			originalpartitions[disknum] =
				orchestrator_om_partitions_dup(defaultpartitions[disknum]);
			modifiedpartitions[disknum] =
				orchestrator_om_partitions_dup(defaultpartitions[disknum]);
		}
	}

	if (status == DISK_STATUS_CANT_PRESERVE) {
		activediskisreadable = FALSE;
		gtk_widget_hide(
			glade_xml_get_widget(MainWindow.installationdiskwindowxml,
				"partsfoundlabel"));
		gtk_widget_show(
			glade_xml_get_widget(MainWindow.installationdiskwindowxml,
				"unreadablepartsouterhbox"));
	}

	if ((status == DISK_STATUS_OK) || (status == DISK_STATUS_CANT_PRESERVE)) {
		disk_partitioning_set_from_parts_data(alldiskinfo [disknum],
			modifiedpartitions[disknum]);
		usewholediskradio = GTK_TOGGLE_BUTTON
			(glade_xml_get_widget(MainWindow.installationdiskwindowxml,
				"wholediskradio"));
		if (gtk_toggle_button_get_active(usewholediskradio) == TRUE)
			proposedpartitions[disknum] = defaultpartitions[disknum];
		else
			proposedpartitions[disknum] = modifiedpartitions[disknum];
	}

	update_data_loss_warnings(
		&parttypechanges[disknum],
		&partsizechanges[disknum]);

	partitionsmodified = GPOINTER_TO_INT(
		g_object_get_data(G_OBJECT
		(diskbuttons[disknum]),
		"modified"));
	gtk_widget_set_sensitive(GTK_WIDGET
		(MainWindow.InstallationDiskWindow.resetbutton),
		partitionsmodified);

#endif
	disk_partitioning_unblock_all_handlers();

	activedisk = disknum;
}

/* Create big disk toggle buttons for the viewport scrollable area */
static GtkWidget *
disk_toggle_button_new_with_label(const gchar *label,
	DiskStatus status)
{
	GtkIconInfo *diskiconinfo;
	GtkIconInfo *emblemiconinfo = NULL;
	GtkRadioButton *button;
	GtkWidget *alignment;
	GtkWidget *vbox;
	GtkWidget *buttonlabel;
	GtkWidget *diskbaseimage;
	GdkPixbuf *diskbasepixbuf;
	GdkPixbuf *emblempixbuf;
	gint diskwidth, diskheight;
	gint emblemwidth, emblemheight;
	static GtkRadioButton *firstbutton = NULL;

	const gchar *diskfilename, *emblemfilename = NULL;

	if (!firstbutton) {
		button = GTK_RADIO_BUTTON(gtk_radio_button_new(NULL));
		firstbutton = button;
	} else
		button = GTK_RADIO_BUTTON(
		    gtk_radio_button_new_from_widget(firstbutton));

	/* Don't draw the check box indicator of the normal radiobutton */
	g_object_set(G_OBJECT(button),
	    "draw-indicator", FALSE,
	    NULL);
	gtk_button_set_relief(GTK_BUTTON(button), GTK_RELIEF_NONE);

	alignment = gtk_alignment_new(0.5, 0.5, 0, 0);
	gtk_widget_show(alignment);
	gtk_container_add(GTK_CONTAINER(button), alignment);

	vbox = gtk_vbox_new(FALSE, 0);
	gtk_widget_show(vbox);
	gtk_container_add(GTK_CONTAINER(alignment), vbox);

	/*
	 * Yuck. Seems like icon size has to be hardcoded to 48 rather than using
	 * GTK_ICON_SIZE_DIALOG
	 */
	if (status == DISK_STATUS_NO_MEDIA) {
		diskiconinfo = gtk_icon_theme_lookup_icon(icontheme,
			"gnome-dev-removable",
			48,
			0);
	} else {
		diskiconinfo = gtk_icon_theme_lookup_icon(icontheme,
			"gnome-dev-harddisk",
			48,
			0);
	}
	diskfilename = gtk_icon_info_get_filename(diskiconinfo);

	diskbasepixbuf = gdk_pixbuf_new_from_file(diskfilename, NULL);

	diskwidth = gdk_pixbuf_get_width(diskbasepixbuf);
	diskheight = gdk_pixbuf_get_height(diskbasepixbuf);
	switch (status) {
		case DISK_STATUS_OK:
		case DISK_STATUS_CANT_PRESERVE:
			break;
		case DISK_STATUS_TOO_SMALL:
			emblemiconinfo =
			gtk_icon_theme_lookup_icon(icontheme,
				"dialog-error",
				16,
				0);
			break;
		case DISK_STATUS_WARNING:
			emblemiconinfo =
			gtk_icon_theme_lookup_icon(icontheme,
				"dialog-warning",
				16,
				0);
			break;
		default:
			break;
	}
	if (emblemiconinfo != NULL) {
		emblemfilename = gtk_icon_info_get_filename(emblemiconinfo);
		emblempixbuf = gdk_pixbuf_new_from_file(emblemfilename, NULL);
		emblemwidth = gdk_pixbuf_get_width(emblempixbuf);
		emblemheight = gdk_pixbuf_get_height(emblempixbuf);

		gdk_pixbuf_composite(emblempixbuf,
			diskbasepixbuf,
			diskwidth - emblemwidth,
			diskheight - emblemheight,
			emblemwidth,
			emblemheight,
			diskwidth - emblemwidth,
			diskheight - emblemheight,
			1,
			1,
			GDK_INTERP_BILINEAR,
			255);
	}
	diskbaseimage = gtk_image_new_from_pixbuf(diskbasepixbuf);
	gtk_widget_show(diskbaseimage);
	gtk_box_pack_start(GTK_BOX(vbox), diskbaseimage, TRUE, TRUE, 0);

	buttonlabel = gtk_label_new(label);
	gtk_widget_show(buttonlabel);
	gtk_box_pack_start(GTK_BOX(vbox), buttonlabel, FALSE, FALSE, 0);

	return (GTK_WIDGET(button));
}

static void
render_partitiontype_name(GtkCellLayout *layout,
	GtkCellRenderer *cell,
	GtkTreeModel *model,
	GtkTreeIter *iter,
	gpointer user_data)
{
	gchar *text = NULL;
	gtk_tree_model_get(model, iter, 0, &text, -1);
	if (!text)
		return;
	g_object_set(cell, "text", text, NULL);
}


static void
disk_partitioning_set_from_parts_data(disk_info_t *diskinfo,
	disk_parts_t *partitions)
{
	partition_info_t *partinfo = NULL;
	GtkComboBox *combo;
	GtkSpinButton *spinner;
	gchar *type;
	gint i;

	gfloat partsizes[GUI_INSTALL_NUMPART] = {0, 0, 0, 0};
	gfloat diskusage = 0;
	gfloat diskcapacity;
	gfloat roundedcapacity = 0;
	gfloat diskfreespace = 0;
	gint parttype;
	gchar *freespacetext = NULL;
	gchar *capacitystr = NULL;
	gchar *partsizestr = NULL;
	gpointer objectdata = NULL;

	diskcapacity = orchestrator_om_get_disk_sizegb(diskinfo);

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = orchestrator_om_get_part_by_blkorder(partitions, i);
		if (!partinfo) {
			partinfo = orchestrator_om_find_unused_partition(partitions,
				UNUSED,
				i);
			}
		g_assert(partinfo != NULL);
		if (partinfo) {
			partsizes[i] =
				orchestrator_om_get_partition_sizegb(partinfo);
			diskusage += partsizes[i];
		}
	}
	diskfreespace = diskcapacity - diskusage;

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = orchestrator_om_get_part_by_blkorder(partitions, i);

		/* Set partition type of each fdisk partition in the comboboxes. */
		combo = GTK_COMBO_BOX
			(MainWindow.InstallationDiskWindow.partitioncombos[i]);
		g_assert(partinfo != NULL);
		parttype = orchestrator_om_get_partition_type(partinfo);
		/*
		 * Remove any items previously added to display
		 * existing, unmodifiable partition types
		 */
		objectdata = g_object_get_data(G_OBJECT(combo), "extra_fs");
		if ((objectdata != NULL) && (GPOINTER_TO_INT(objectdata) == TRUE)) {
			gtk_combo_box_remove_text(GTK_COMBO_BOX(combo), 2);
			g_object_set_data(G_OBJECT(combo),
			    "extra_fs",
			    GINT_TO_POINTER(FALSE));
		}

		switch (parttype) {
			case UNIXOS:
				type = Ustr;
			break;
			case SUNIXOS:
				if (partinfo->content_type == OM_CTYPE_LINUXSWAP)
					type = LINSWPstr;
				else
					type = SUstr;
			break;
			case SUNIXOS2:
				type = SU2str;
			break;
			case X86BOOT:
				type = X86str;
			break;
			case DOSOS12:
				type = Dstr;
			break;
			case DOSOS16:
				type = D16str;
			break;
			case EXTDOS:
				type = EDstr;
			break;
			case DOSDATA:
				type = DDstr;
			break;
			case DOSHUGE:
				type = DBstr;
			break;
			case PCIXOS:
				type = PCstr;
			break;
			case DIAGPART:
				type = DIAGstr;
			break;
			case FDISK_IFS:
				type = IFSstr;
			break;
			case FDISK_AIXBOOT:
				type = AIXstr;
			break;
			case FDISK_AIXDATA:
				type = AIXDstr;
			break;
			case FDISK_OS2BOOT:
				type = OS2str;
			break;
			case FDISK_WINDOWS:
				type = WINstr;
			break;
			case FDISK_EXT_WIN:
				type = EWINstr;
			break;
			case FDISK_FAT95:
				type = FAT95str;
			break;
			case FDISK_EXTLBA:
				type = EXTLstr;
			break;
			case FDISK_LINUX:
				type = LINUXstr;
			break;
			case FDISK_CPM:
				type = CPMstr;
			break;
			case FDISK_NOVELL3:
				type = NOVstr;
			break;
			case FDISK_QNX4:
				type = QNXstr;
			break;
			case FDISK_QNX42:
				type = QNX2str;
			break;
			case FDISK_QNX43:
				type = QNX3str;
			break;
			case FDISK_LINUXNAT:
				type = LINNATstr;
			break;
			case FDISK_NTFSVOL1:
				type = NTFSVOL1str;
			break;
			case FDISK_NTFSVOL2:
				type = NTFSVOL2str;
			break;
			case FDISK_BSD:
				type = BSDstr;
			break;
			case FDISK_NEXTSTEP:
				type = NEXTSTEPstr;
			break;
			case FDISK_BSDIFS:
				type = BSDIFSstr;
			break;
			case EFI_PMBR:
				type = EFIPMBRstr;
			break;
			case EFI_FS:
				type = EFIstr;
				break;
			default:
				type = _("Unknown");
				break;
		}

		if (parttype == UNUSED)
			gtk_combo_box_set_active(combo, 0);
		else if ((parttype == SUNIXOS2) || ((parttype == SUNIXOS) &&
		    (partinfo->content_type != OM_CTYPE_LINUXSWAP))) {
			gtk_combo_box_set_active(combo, 1);
			/*
			 * Solaris partitions will always be erased because
			 * that's what we install onto, and we don't permit
			 * more than one solaris partition per disk. Solaris
			 * partitions can also be created/resized so they
			 * shouldn't be set to Unused:0.0GB like others.
			 * So always set it's size change flag to TRUE
			 */
			partsizechanges[activedisk].partid[i] = TRUE;
			update_data_loss_warnings(
			    &parttypechanges[activedisk],
			    &partsizechanges[activedisk]);
		} else {
			gtk_combo_box_append_text(combo, type);
			gtk_combo_box_set_active(combo, 2);
			g_object_set_data(G_OBJECT(combo),
				"extra_fs",
				GINT_TO_POINTER(TRUE));
		}

		/* Set the partition size of each partition */
		spinner = GTK_SPIN_BUTTON
				(MainWindow.InstallationDiskWindow.partitionspinners [i]);
		/*
		 * This pre-rounding is necessary because the spin button will
		 * round the value before inserting it into the display and
		 * ocassionally cause the insert_text filter to spit it out
		 */
		capacitystr = g_strdup_printf("%.1f", diskcapacity);
		roundedcapacity = atof(capacitystr);
		g_free(capacitystr);
		gtk_spin_button_set_range(GTK_SPIN_BUTTON(spinner),
			parttype == UNUSED ? 0 : 0.1,
			parttype == UNUSED ? 0 : roundedcapacity);
		partsizestr = g_strdup_printf("%.1f", partsizes[i]);
		gtk_spin_button_set_value(spinner, atof(partsizestr));
		g_free(partsizestr);
		/* For now, these types are all we support due to pfinstall limits */
#ifdef POST_PREVIEW_RELEASE
		if ((parttype == SUNIXOS2) ||\
			(parttype == SUNIXOS &&
				partinfo->content_type != OM_CTYPE_LINUXSWAP))
			gtk_widget_set_sensitive(GTK_WIDGET(spinner), TRUE);
		else
#endif /* POST_PREVIEW_RELEASE */
			gtk_widget_set_sensitive(GTK_WIDGET(spinner), FALSE);
	}

	/* Set the free disk space field */
	freespacetext = g_strdup_printf("%.1f", diskfreespace);
	gtk_entry_set_text(GTK_ENTRY
		(MainWindow.InstallationDiskWindow.diskspaceentry),
		freespacetext);
	g_free(freespacetext);
}

static void
disk_partitioning_adjust_free_space(disk_info_t *diskinfo,
	disk_parts_t *partitions)
{
	partition_info_t *partinfo;
	int i;
	guint64 *partsizes = NULL;
	guint64 diskusage = 0;
	guint64 diskcapacity;
	gint64 diskfreespace = 0;
	gchar *freespacetext = NULL;

	partsizes = g_new0(guint64, GUI_INSTALL_NUMPART);
	diskcapacity = orchestrator_om_get_disk_sizemb(diskinfo);

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = &partitions->pinfo[i];
		if (partinfo) {
			partsizes[i] =
				orchestrator_om_get_partition_sizemb(partinfo);
			diskusage += partsizes[i];
		} else
			g_warning("Missing partition_info_t data from disk_parts_t type");
	}
	diskfreespace = diskcapacity - diskusage;
	freespacetext = g_strdup_printf("%.1f", (gfloat)diskfreespace/MBPERGB);
	gtk_entry_set_text(GTK_ENTRY
		(MainWindow.InstallationDiskWindow.diskspaceentry),
		freespacetext);
	g_free(freespacetext);
	g_free(partsizes);
}

/* Populates the comboboxes with the supported fdisk partition types */
static void
disk_combobox_ui_init(GtkComboBox *combobox)
{
	GtkCellRenderer *renderer;
	GtkListStore *partitiontype_store;
	GtkTreeIter iter;

	partitiontype_store = gtk_list_store_new(1, G_TYPE_STRING);

	/*
	 * The only valid partition *selectable* types are Unused & Solaris
	 * Everything else is is non selectable.
	 */
	gtk_list_store_append(partitiontype_store, &iter);
	gtk_list_store_set(partitiontype_store, &iter, 0, _("Unused"), -1);
	gtk_list_store_append(partitiontype_store, &iter);
	gtk_list_store_set(partitiontype_store, &iter, 0, SU2str, -1);

	gtk_combo_box_set_model(GTK_COMBO_BOX(combobox),
	    GTK_TREE_MODEL(partitiontype_store));
	renderer = gtk_cell_renderer_text_new();
	gtk_cell_layout_pack_start(GTK_CELL_LAYOUT(combobox), renderer,  TRUE);
	gtk_cell_layout_set_cell_data_func(GTK_CELL_LAYOUT(combobox),
	    renderer,
	    render_partitiontype_name,
	    NULL,
	    NULL);

	gtk_combo_box_set_active(GTK_COMBO_BOX(combobox), 0);
}

static void
disk_comboboxes_ui_init(void)
{
	gint i;
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		disk_combobox_ui_init(GTK_COMBO_BOX
			(MainWindow.InstallationDiskWindow.partitioncombos[i]));
	}
}

static void
init_disk_status(void)
{
	disk_parts_t *partitions;
	disk_info_t *diskinfo = NULL;
	DiskStatus *status = NULL;
	gint i = 0;

	g_return_if_fail(alldiskstatus != NULL);
	g_return_if_fail(numdisks > 0);
	for (i = 0; i < numdisks; i++) {
		diskinfo = alldiskinfo[i];
		status = &alldiskstatus[i];

		if (diskinfo == NULL) {
			g_warning("%d disks were detected but no information about disk "
				"%d was found", numdisks, i);
			*status = DISK_STATUS_NO_DISKINFO;
			continue;
		}
		if (orchestrator_om_get_disk_sizemb(diskinfo) == 0) {
			*status = DISK_STATUS_NO_MEDIA;
			continue;
		}
	    if (orchestrator_om_get_disk_sizegb(diskinfo) < \
			orchestrator_om_get_mininstall_sizegb()) {
			*status = DISK_STATUS_TOO_SMALL;
			continue;
		}

		if (diskinfo->label != OM_LABEL_VTOC &&
		    diskinfo->label != OM_LABEL_FDISK) {
			*status = DISK_STATUS_CANT_PRESERVE;
			continue;
		}
#if defined(__i386)
		partitions = orchestrator_om_get_disk_partitions(omhandle,
			diskinfo->disk_name);
		if (!partitions) {
			g_message("Can't find disks partitions on device: %s",
				diskinfo->disk_name);
			*status = DISK_STATUS_CANT_PRESERVE;
			continue;
		}

		*status = DISK_STATUS_OK;
#else /* (__sparc) */
		/* On SPARC, the disk always gets wiped */
		*status = DISK_STATUS_CANT_PRESERVE;
#endif /* (__i386) */
	}
}

static DiskStatus
get_disk_status(guint disknum)
{
	g_return_val_if_fail(disknum < numdisks, -1);
	g_return_val_if_fail(alldiskstatus != NULL, -1);

	return (alldiskstatus[disknum]);
}

/*
 * Called when target discovery is complete and we're ready to query
 * the orchestrator for disk info
 */
static void
populate_data_from_orchestrator_discovery(void)
{
	gint i = 0, j = 0;

	alldiskinfo = orchestrator_om_get_disk_info(omhandle, &numdisks);
	alldiskstatus = g_new0(DiskStatus, numdisks);

	originalpartitions = g_new0(disk_parts_t *, numdisks);
	modifiedpartitions = g_new0(disk_parts_t *, numdisks);
	proposedpartitions = g_new0(disk_parts_t *, numdisks);
	defaultpartitions  = g_new0(disk_parts_t *, numdisks);

	init_disk_status();

	parttypechanges = g_new0(PartTypeFlag, numdisks);
	partsizechanges = g_new0(PartSizeFlag, numdisks);
	for (i = 0; i < numdisks; i++) {
		for (j = 0; j < GUI_INSTALL_NUMPART; j++) {
			parttypechanges[i].partid[j] = FALSE;
			partsizechanges[i].partid[j] = FALSE;
		}
	}
}

static void
disk_viewport_diskbuttons_init(GtkViewport *viewport)
{
	gchar **disklabels;
	gchar *disktiptext;
	GtkTooltips *disktip;
	int disknum;
	DiskStatus status;

	/* Create the hbutton box first */
	hbuttonbox = gtk_hbutton_box_new();
	g_signal_connect(G_OBJECT(icontheme), "changed",
		G_CALLBACK(icon_theme_changed),
		(gpointer) hbuttonbox);

	gtk_button_box_set_spacing(hbuttonbox, 35);
	gtk_button_box_set_layout(GTK_BUTTON_BOX(hbuttonbox),
		GTK_BUTTONBOX_START);

	diskbuttons = g_new0(GtkWidget *, numdisks);
	disklabels = g_new0(gchar *, numdisks);

	for (disknum = 0; disknum < numdisks; disknum++) {
		status = get_disk_status(disknum);
		if (status == DISK_STATUS_NO_DISKINFO) {
			g_warning("Skipping over installation target disk %d: "
				"no disk info provided.",
				disknum);
			continue;
		}
		disklabels[disknum] = disk_viewport_create_disk_label(disknum);
		disktip = gtk_tooltips_new();
		disktiptext = disk_viewport_create_disk_tiptext(disknum);
		diskbuttons[disknum] =
			disk_toggle_button_new_with_label(disklabels[disknum], status);
		gtk_tooltips_set_tip(disktip, diskbuttons[disknum], disktiptext, NULL);
		g_free(disklabels[disknum]);
		g_free(disktiptext);
		gtk_widget_show(diskbuttons[disknum]);
		gtk_box_pack_start(GTK_BOX(hbuttonbox),
			diskbuttons[disknum],
			FALSE,
			FALSE,
			0);

		g_signal_connect(G_OBJECT(diskbuttons[disknum]),
			"toggled",
			G_CALLBACK(installationdisk_diskbutton_toggled),
			GINT_TO_POINTER(disknum));
		g_signal_connect(G_OBJECT(diskbuttons[disknum]),
			"focus-in-event",
			G_CALLBACK(disk_partitioning_button_focus_handler),
			GINT_TO_POINTER(disknum));

	}

	g_free(disklabels);
	gtk_widget_show(hbuttonbox);
	gtk_container_add(GTK_CONTAINER(viewport), hbuttonbox);
}

static gboolean
partition_discovery_monitor(gpointer user_data)
{
	gboolean bootdevfound = FALSE;
	gint chosendisk = -1;
	gint i = 0;

	/*
	 * Don't to anything until both target discovery and
	 * UI initialisation has been completed
	 */
	if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] == FALSE)
		return (TRUE);

	GtkViewport *viewport;
	viewport = GTK_VIEWPORT(MainWindow.InstallationDiskWindow.disksviewport);
	populate_data_from_orchestrator_discovery();
	if (scanningbox) {
		gtk_widget_destroy(scanningbox);
	}
	disk_viewport_diskbuttons_init(viewport);

	/*
	 * Auto select the boot disk, or failing that, the first suitable disk
	 * and toggle the custom partitioning controls.
	 */
	for (i = 0; i < numdisks; i++) {
		if (get_disk_status(i) == DISK_STATUS_OK ||
		    get_disk_status(i) == DISK_STATUS_CANT_PRESERVE) {
			/* If boot device is found and it's usable, look no further */
			if (orchestrator_om_disk_is_bootdevice(alldiskinfo[i])) {
				chosendisk = i;
				break;
			} else if (chosendisk < 0)
				chosendisk = i;
		}
	}

	/*
	 * If no suitable disk was found, something still has to be
	 * selected because we are using radio buttons. So just select
	 * the first device.
	 */
	if (numdisks > 0 && chosendisk < 0)
		chosendisk = 0;
	if (chosendisk >= 0) {
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
		    diskbuttons[chosendisk]),
		    TRUE);
		/*
		 * It's safe to call this on SPARC also since the callback
		 * is a no-op.
		 */
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
		    glade_xml_get_widget(MainWindow.installationdiskwindowxml,
		    "partitiondiskradio")),
		    TRUE);
		/* Force a toggle emission */
		gtk_toggle_button_toggled(GTK_TOGGLE_BUTTON(
		    diskbuttons[chosendisk]));

#if defined(__i386)
		/* Show partitioning options on X86 only */
		gtk_widget_show(glade_xml_get_widget(
		    MainWindow.installationdiskwindowxml,
		    "partitioningvbox"));
#endif
	}
	return (FALSE);
}

static void
disk_viewport_ui_init(GtkViewport *viewport)
{
	GtkWidget *busyimage;
	GtkWidget *label;
	gchar *markup;

	markup = g_strdup_printf("<span font_desc=\"Bold\">%s</span>",
		_("Finding Disks"));
	label = gtk_label_new(NULL);
	gtk_label_set_markup(GTK_LABEL(label), markup);
	g_free(markup);

	/*
	 * XXX: Doesn't use image from the icon theme. Switch this to a stock
	 * animation in future releases when A11Y and theme support become a
	 * requirement.
	 */
	if (MainWindow.MileStoneComplete[OM_UPGRADE_TARGET_DISCOVERY] == FALSE) {
		busyimage = gtk_image_new_from_file(PIXMAPDIR "/" "gnome-spinner.gif");
		gtk_widget_show(busyimage);

		scanningbox = gtk_vbox_new(FALSE, 0);
		gtk_box_pack_start(GTK_BOX(scanningbox), label, FALSE, FALSE, 0);
		gtk_box_pack_end(GTK_BOX(scanningbox), busyimage, FALSE, FALSE, 0);
		gtk_widget_show(label);
		gtk_widget_show(busyimage);
		gtk_widget_show(scanningbox);

		gtk_container_add(GTK_CONTAINER(viewport), scanningbox);
	}
}

static gchar*
disk_viewport_create_disk_tiptext(guint disknum)
{
	/*
	 * Tooltip consists of:
	 *  Size: <size>
	 *  Type: <usb|scsi|etc.>
	 *  Vendor: <vendor>
	 *  Devicename: <cXtXdX>
	 *  Bootdisk <Y/N>
	 *  <instance 1>
	 *  <instance 2>
	 *  <...>
	 */
	disk_info_t *diskinfo;
	upgrade_info_t *uinfos = NULL;
	upgrade_info_t *uinfo = NULL;
	guint16 ninstance;
	gfloat size;
	gchar *type;
	const gchar *vendor;
	gboolean isbootdisk;
	const gchar *devicename;
	gchar *newtiptext;
	gchar *instancetext;
	gchar *tiptext;

	diskinfo = alldiskinfo[disknum];
	orchestrator_om_get_upgrade_targets_by_disk(diskinfo,
			&uinfos, &ninstance);

	size = orchestrator_om_get_disk_sizegb(diskinfo);
	type = orchestrator_om_get_disk_type(diskinfo);
	vendor = orchestrator_om_get_disk_vendor(diskinfo);
	devicename = orchestrator_om_get_disk_devicename(diskinfo);
	isbootdisk = orchestrator_om_disk_is_bootdevice(diskinfo);
	tiptext = g_strdup_printf(_("Size: %.1fGB\n"
		"Type: %s\n"
		"Vendor: %s\n"
		"Device: %s\n"
		"Boot device: %s"),
		size,
		type,
		vendor,
		devicename,
		isbootdisk ? _("Yes") : _("No"));

	uinfo = uinfos;
	while (uinfo) {
		instancetext =
			orchestrator_om_upgrade_instance_get_release_name(uinfo);
		if (instancetext) {
			newtiptext = g_strconcat(tiptext, _("\n"),
								instancetext, NULL);
			g_free(tiptext);
			tiptext = newtiptext;
		}
		uinfo = orchestrator_om_upgrade_instance_get_next(uinfo);
	}
	g_free(type);
	return (tiptext);
}

static gchar*
disk_viewport_create_disk_label(guint disknum)
{
	/* Label consists of: "<sizeinGB>[GB|MB] <disktype> */
	gfloat disksizegb = 0;
	gchar *disktype  = NULL;
	gchar *label = NULL;

	disktype = orchestrator_om_get_disk_type(alldiskinfo[disknum]);
	disksizegb = orchestrator_om_get_disk_sizegb(alldiskinfo[disknum]);
		label = g_strdup_printf("%.1fGB %s", disksizegb, disktype);
	g_free(disktype);
	return (label);
}


static void
disk_partitioning_block_all_handlers(void)
{
	gint mask = (1<<0 | 1<<1 | 1<<2 | 1<<3);
	disk_partitioning_block_spinbox_handlers(mask);
	disk_partitioning_block_combobox_handlers(mask);
}

static void
disk_partitioning_unblock_all_handlers(void)
{
	gint mask = (1<<0 | 1<<1 | 1<<2 | 1<<3);
	disk_partitioning_unblock_spinbox_handlers(mask);
	disk_partitioning_unblock_combobox_handlers(mask);
}

static void
disk_partitioning_block_spinbox_handlers(gint mask)
{
	gint i = 0;

	if (mask == 0)
		return;

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		if (mask & 1<<i) {
			g_signal_handler_block(
			    (gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[i],
			    spininserthandlers[i]);
			g_signal_handler_block(
			    (gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[i],
			    spindeletehandlers[i]);
		}
	}
	if (mask & 1<<0)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[0],
			(gpointer *)partition_0_spinner_value_changed,
			NULL);

	if (mask & 1<<1);
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[1],
			(gpointer *)partition_1_spinner_value_changed,
			NULL);
	if (mask & 1<<2)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[2],
			(gpointer *)partition_2_spinner_value_changed,
			NULL);
	if (mask & 1<<3)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[3],
			(gpointer *)partition_3_spinner_value_changed,
			NULL);
}

static void
disk_partitioning_unblock_spinbox_handlers(gint mask)
{
	gint i  = 0;

	if (mask == 0)
		return;
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		if (mask & 1<<i) {
			g_signal_handler_unblock(
			    (gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[i],
			    spininserthandlers[i]);
			g_signal_handler_unblock(
			    (gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[i],
			    spindeletehandlers[i]);
		}
	}
	if (mask & 1<<0)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[0],
			(gpointer *)partition_0_spinner_value_changed,
			NULL);
	if (mask & 1<<1)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[1],
			(gpointer *)partition_1_spinner_value_changed,
			NULL);
	if (mask & 1<<2)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[2],
			(gpointer *)partition_2_spinner_value_changed,
			NULL);
	if (mask & 1<<3)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitionspinners[3],
			(gpointer *)partition_3_spinner_value_changed,
			NULL);
}

static void
disk_partitioning_block_combobox_handlers(gint mask)
{
	if (mask == 0)
		return;
	if (mask & 1<<0)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[0],
			(gpointer *)partition_0_combo_changed,
			NULL);
	if (mask & 1<<1)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[1],
			(gpointer *)partition_1_combo_changed,
			NULL);
	if (mask & 1<<2)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[2],
			(gpointer *)partition_2_combo_changed,
			NULL);
	if (mask & 1<<3)
		g_signal_handlers_block_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[3],
			(gpointer *)partition_3_combo_changed,
			NULL);
}

static void
disk_partitioning_unblock_combobox_handlers(gint mask)
{
	if (mask == 0)
		return;

	if (mask & 1<<0)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[0],
			(gpointer *)partition_0_combo_changed,
			NULL);
	if (mask & 1<<1)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[1],
			(gpointer *)partition_1_combo_changed,
			NULL);
	if (mask & 1<<2)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[2],
			(gpointer *)partition_2_combo_changed,
			NULL);
	if (mask & 1<<3)
		g_signal_handlers_unblock_by_func(
			(gpointer *)MainWindow.InstallationDiskWindow.partitioncombos[3],
			(gpointer *)partition_3_combo_changed,
			NULL);
}

static void
spinners_insert_text_filter(GtkEntry *widget,
	const gchar *newtext,
	gint length,
	gint *position,
	gpointer user_data)
{
	const gchar *currenttext;
	const gchar *textptr;
	gchar *newnumstring = NULL;
	gchar *freespacetext = NULL;
	gfloat newnum;
	gdouble min, max;

	disk_parts_t *partitions = NULL;
	partition_info_t *partinfo = NULL;
	guint64 *partsizes = NULL;
	guint64 diskusage = 0;
	gint64 diskfreespace = 0;
	guint64 diskcapacity = 0;
	gint newstrlen = 0;
	gint decimalplaces = 0;
	gint i = 0;
	int partid = GPOINTER_TO_INT(user_data);

	currenttext = gtk_entry_get_text(GTK_ENTRY(widget));
	gtk_spin_button_get_range(GTK_SPIN_BUTTON(widget), &min, &max);
	partitions = modifiedpartitions[activedisk];
	partsizes = g_new0(guint64, GUI_INSTALL_NUMPART);

	static GtkComboBox **combos = NULL;

	if (combos == NULL) {
		combos = g_new0(GtkComboBox *, GUI_INSTALL_NUMPART);
		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			combos[i] = GTK_COMBO_BOX(
			    MainWindow.InstallationDiskWindow.partitioncombos[i]);
		}
	}

	diskcapacity =
		orchestrator_om_get_disk_sizemb(alldiskinfo[activedisk]);
	if (strcmp(newtext, "=") == 0) {
		gchar *newnumstr;
		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			partinfo = orchestrator_om_get_part_by_blkorder(partitions, i);
			if (partinfo) {
				if (i != partid)  {
					/* Ignore GUI's existing size for the partition */
					partsizes[i] =
						orchestrator_om_get_partition_sizemb(partinfo);
					diskusage += partsizes[i];
				}
			}
		}
		diskfreespace = diskcapacity - diskusage;
		if (diskfreespace < 1) {
			gdk_beep();
			g_free(partsizes);
			return;
		}
		newnum = (gfloat)(diskfreespace) / MBPERGB;
		newnumstr = g_strdup_printf("%.1f", newnum);
		gtk_spin_button_set_value(GTK_SPIN_BUTTON(widget), atof(newnumstr));
		g_free(newnumstr);
		g_free(partsizes);
		return;
	}

	/*
	 * Need to generate newnumstring based on insertion position
	 */

	newstrlen = strlen(currenttext) + length;
	newnumstring = g_new0(gchar, newstrlen + 1);

	strncat(newnumstring, currenttext, *position);
	strncat(newnumstring, newtext, length);
	if (*position < strlen(currenttext)) {
		textptr = &currenttext[*position];
		strcat(newnumstring, textptr);
	}

	/*
	 * Check to make sure there's no more than 1 decimal
	 * place in the new number. Note that the decimal place
	 * character literal is dependant on locale environment,
	 * hence the use of "isdigit()" instead of checking for
	 * a "." or "," character.
	 */
	textptr = newnumstring;
	while (*textptr != '\0') {
		if (!isdigit(*textptr)) {
			decimalplaces = strlen(textptr+1);
			break;
		}
		textptr++;
	}
	newnum = atof(newnumstring);

	if (newnum > max || decimalplaces > 1) {
		gdk_beep();
		g_signal_stop_emission_by_name(GTK_OBJECT(widget), "insert_text");
		g_free(newnumstring);
		g_free(partsizes);
		return;
	}

	partsizechanges[activedisk].partid[partid] = TRUE;
	update_data_loss_warnings(
	    &parttypechanges[activedisk],
	    &partsizechanges[activedisk]);
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = orchestrator_om_get_part_by_blkorder(partitions, i);
		if (partinfo) {
			if (i == partid)
				partsizes[i] = (guint64)(newnum * MBPERGB);
			else
				partsizes[i] =
					orchestrator_om_get_partition_sizemb(partinfo);
			diskusage += partsizes[i];
		}
	}

	diskfreespace = diskcapacity - diskusage;
	freespacetext = g_strdup_printf("%.1f",
	    (gfloat)diskfreespace / MBPERGB);
	gtk_entry_set_text(GTK_ENTRY
		(MainWindow.InstallationDiskWindow.diskspaceentry),
		freespacetext);

	if (activediskisreadable == TRUE) {
		partsizechanges[activedisk].partid[partid] = TRUE;
		/*
		 * Domino effect on subsequent partitions.
		 */
		if (partid < GUI_INSTALL_NUMPART - 1) {
			/* If next partition contains an exisiting partition, nuke it */
			if ((partsizechanges[activedisk].partid[partid+1] == FALSE) &&
				(gtk_combo_box_get_active(combos[partid+1]) != 0)) {
				partsizechanges[activedisk].partid[partid+1] = TRUE;
				gtk_combo_box_set_active(combos[partid+1], 0);
			}
		}
	}
	update_data_loss_warnings(
	    &parttypechanges[activedisk],
	    &partsizechanges[activedisk]);
	g_free(newnumstring);
	g_free(freespacetext);
	g_free(partsizes);
}

static void
spinners_delete_text_filter(GtkEditable *widget,
	gint start_pos,
	gint end_pos,
	gpointer user_data)
{
	gchar *freespacetext = NULL;
	gchar *currenttext;
	const gchar *str1 = NULL, *str2 = NULL;
	gchar *newnumstring = NULL;
	gfloat newnum;
	gdouble min, max;

	disk_parts_t *partitions = NULL;
	partition_info_t *partinfo = NULL;
	guint64 *partsizes = NULL;
	guint64 diskusage = 0;
	guint64 diskcapacity = 0;
	gint64 diskfreespace = 0;
	gint i = 0;
	int partid = GPOINTER_TO_INT(user_data);
	static GtkComboBox **combos = NULL;

	if (combos == NULL) {
		combos = g_new0(GtkComboBox *, GUI_INSTALL_NUMPART);
		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			combos[i] = GTK_COMBO_BOX(MainWindow.InstallationDiskWindow.partitioncombos[i]);
		}
	}

	currenttext = g_strdup(gtk_entry_get_text(GTK_ENTRY(widget)));
	if (atof(currenttext) == 0) {
		g_free(currenttext);
		return;
	}

	diskcapacity = orchestrator_om_get_disk_sizemb(alldiskinfo[activedisk]);
	gtk_spin_button_get_range(GTK_SPIN_BUTTON(widget), &min, &max);
	partitions = modifiedpartitions[activedisk];
	partsizes = g_new0(guint64, GUI_INSTALL_NUMPART);

	/*
	 * Need to generate newstring based on deletion span
	 */
	str1 = currenttext;
	currenttext[start_pos] = '\0';
	str2 = &currenttext[end_pos];
	newnumstring = g_strdup_printf("%s%s", str1, str2);
	newnum = atof(newnumstring);

	if (newnum > max) {
		gdk_beep();
		g_signal_stop_emission_by_name(GTK_OBJECT(widget), "delete_text");
		g_free(currenttext);
		g_free(newnumstring);
		g_free(partsizes);
		return;
	}

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = orchestrator_om_get_part_by_blkorder(partitions, i);
		if (partinfo) {
			if (i == partid)
				partsizes[i] = (guint64) (newnum * MBPERGB);
			else
				partsizes[i] =
					orchestrator_om_get_partition_sizemb(partinfo);
			diskusage += partsizes[i];
		}
	}
	diskfreespace = diskcapacity - diskusage;
	freespacetext = g_strdup_printf("%.1f", (gfloat)diskfreespace/MBPERGB);
	gtk_entry_set_text(GTK_ENTRY
		(MainWindow.InstallationDiskWindow.diskspaceentry),
		freespacetext);

	if (activediskisreadable == TRUE) {
		partsizechanges[activedisk].partid[partid] = TRUE;
		/*
		 * Domino effect on subsequent partitions.
		 */
		if (partid < GUI_INSTALL_NUMPART - 1) {
			/* If next partition contains an exisiting partition, nuke it */
			if ((partsizechanges[activedisk].partid[partid+1] == FALSE) &&
				(gtk_combo_box_get_active(combos[partid+1]) != 0)) {
				partsizechanges[activedisk].partid[partid+1] = TRUE;
				gtk_combo_box_set_active(combos[partid+1], 0);
			}
		}
	}
	update_data_loss_warnings(
	    &parttypechanges[activedisk],
	    &partsizechanges[activedisk]);

	g_free(currenttext);
	g_free(newnumstring);
	g_free(freespacetext);
	g_free(partsizes);
}

static void
disk_partitioning_set_sensitive(gboolean sensitive)
{
	if (sensitive == FALSE) {
		/* Collapse the custom partitioning controls */
		gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(
			glade_xml_get_widget(MainWindow.installationdiskwindowxml,
				"wholediskradio")),
			TRUE);
	}
	gtk_widget_set_sensitive(
		glade_xml_get_widget(MainWindow.installationdiskwindowxml,
		"partitioningvbox"), sensitive);
}

/* Makes the scrollbar and viewport adjust to follow the focussed button */
static gboolean
disk_partitioning_button_focus_handler(GtkWidget *widget,
	GdkEventFocus *event,
	gpointer user_data)
{
	gint disknum = 0;
	gfloat newvalue = 0.0;
	gfloat buttonval = 0.0;
	gfloat buttonposition = 0.0;
	gdouble value, lower, upper, pagesize;
	gfloat buttonsize;

	disknum = GPOINTER_TO_INT(user_data);

	g_object_get(G_OBJECT(viewportadjustment), "value", &value, NULL);
	g_object_get(G_OBJECT(viewportadjustment), "lower", &lower, NULL);
	g_object_get(G_OBJECT(viewportadjustment), "upper", &upper, NULL);
	g_object_get(G_OBJECT(viewportadjustment), "page-size", &pagesize, NULL);

	/* double precision is too expensive and overkill - use float */
	buttonsize = (gfloat)((upper - lower)/numdisks);
	buttonposition = (gfloat)disknum / numdisks;
	buttonval = buttonposition * (gfloat)(upper - lower);

	/*
	 * Increment scrolling adjustment just enough to keep
	 * the button visible in the viewport
	 */
	if (value+pagesize <= buttonval+buttonsize) {
		newvalue = buttonval + buttonsize - pagesize;
		gtk_adjustment_set_value(viewportadjustment, (gdouble)newvalue);
		gtk_adjustment_value_changed(viewportadjustment);
	} else if (value >= buttonval) {
		newvalue = buttonval;
		gtk_adjustment_set_value(viewportadjustment, (gdouble)newvalue);
		gtk_adjustment_value_changed(viewportadjustment);
	}
	return (FALSE);
}

static gboolean
disk_partitions_match(disk_parts_t *old, disk_parts_t *new)
{
	gboolean retval = TRUE;
	partition_info_t *parta, *partb;
	guint64 sizea = 0, sizeb = 0;
	gint i = 0;
	g_return_val_if_fail(old, FALSE);
	g_return_val_if_fail(new, FALSE);

	g_debug("Comparing partitioning requisition.....");
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		parta = orchestrator_om_get_part_by_blkorder(old, i);
		partb = orchestrator_om_get_part_by_blkorder(new, i);
		g_assert(parta != NULL);
		g_assert(partb != NULL);

		sizea = orchestrator_om_get_partition_sizemb(parta);
		sizeb = orchestrator_om_get_partition_sizemb(partb);
		/* Ignore small differences due to rounding: <= 1GB */
		if ((sizea - sizeb) > MBPERGB) {
			retval = FALSE;
			g_warning("Partition %d sizes don't match:", i+1);
		}
		g_debug("Part %d: Requested: %lld Received: %lld",
			i, sizea, sizeb);
	}
	return (retval);
}

gboolean
installationdisk_validate()
{
	disk_parts_t *partitions = NULL;
	disk_parts_t *newpartitions = NULL;
	partition_info_t *partition = NULL;
	gchar *errorprimarytext = NULL;
	gchar *errorsecondarytext = NULL;
	gchar *warningprimarytext = NULL;
	gchar *warningsecondarytext = NULL;
	gint i = 0;
	gint numpartitions = 0;
	gfloat solarispartitionsize = 0;
	gint64 freespace = 0;
	guint64 diskusage = 0;
	guint64 diskcapacity = 0;
	gboolean partitionsmatch = FALSE;

	/* 1. No disk selected */
	if (activedisk < 0) {
		errorprimarytext =
			g_strdup(_("No disk has been selected for OpenSolaris installation."));
		errorsecondarytext =
			g_strdup(_("Select a disk."));
		goto errors;
	}
	/* 2. No suitable disk selected */
	/* Only condition I can think of is disk too small */
	if (orchestrator_om_get_disk_sizemb(alldiskinfo[activedisk]) <
		orchestrator_om_get_mininstall_sizemb()) {
		errorprimarytext =
			g_strdup(_("The selected disk is not suitable for OpenSolaris installation."));
		errorsecondarytext =
			g_strdup(_("Select another disk."));
		goto errors;
	}

/* Partitioning related errors are not applicable to SPARC - yet */
#if defined(__i386)

		g_assert(proposedpartitions != NULL);
		g_assert(proposedpartitions[activedisk] != NULL);
		partitions = proposedpartitions[activedisk];
		/* 3. No Solaris partitions defined */
		numpartitions =
			orchestrator_om_get_numparts_of_type(partitions, SUNIXOS2);
		numpartitions +=
			orchestrator_om_get_numparts_of_type(partitions, SUNIXOS);
		diskcapacity = orchestrator_om_get_disk_sizemb(alldiskinfo[activedisk]);

		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			partition = &partitions->pinfo[i];
			if (partition) {
				diskusage +=
					orchestrator_om_get_partition_sizemb(partition);
			}
		}
		freespace = diskcapacity - diskusage;

		if (numpartitions == 0) {
			errorprimarytext =
				g_strdup(_("The selected disk contains no Solaris partitions."));
#ifdef POST_PREVIEW_RELEASE
			errorsecondarytext =
				g_strdup(_("Create one Solaris partition or use the whole disk."));
#else
			errorsecondarytext =
				g_strdup(_("Use the whole disk instead."));
#endif /* POST_PREVIEW_RELEASE */
			goto errors;

		/* 4. Must be only one Solaris partition */
		} else if (numpartitions > 1) {
			errorprimarytext =
				g_strdup(_("There must be only one Solaris partition."));
			errorsecondarytext =
				g_strdup(_("Change the extra Solaris partitions to another type."));
			goto errors;

		/* 5. Disk space over allocated */
		} else if (freespace < -(MBPERGB / 10)) {
			errorprimarytext =
				g_strdup(_("The disk space has been over allocated."));
			errorsecondarytext =
				g_strdup(_("Reduce the size of one or more partitions "
					"until the available disk space is zero."));
			goto errors;
		}
		/* 6. Check if the Solaris partition is too small */
		/* Find the first Solaris partition, should be the only one at this stage */
		for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
			partition =
				orchestrator_om_get_part_by_blkorder(partitions, i);
			if ((orchestrator_om_get_partition_type(partition) ==
				SUNIXOS2) ||
				(orchestrator_om_get_partition_type(partition) ==
				SUNIXOS && partition->content_type != OM_CTYPE_LINUXSWAP)) {
				solarispartitionsize =
					orchestrator_om_get_partition_sizegb(partition);
				break;
			}
		}
		if (solarispartitionsize < orchestrator_om_get_mininstall_sizegb()) {
			errorprimarytext =
				g_strdup(_("The Solaris partition is too "
				    "small for Solaris installation."));
			errorsecondarytext =
				g_strdup(_("Increase the size of the Solaris partition."));
		}
#endif /* (__i386) */

errors:
	if (errorprimarytext != NULL) {
		gui_install_prompt_dialog(FALSE, FALSE, FALSE,
			GTK_MESSAGE_ERROR,
			errorprimarytext,
			errorsecondarytext);
		g_free(errorprimarytext);
		g_free(errorsecondarytext);
		return (FALSE);
	}

	/* Now check for non-fatal warning conditions */
	/* For X86 - unallocated disk space */
#if defined(__i386)
	g_debug("Original partitioning on device %s:",
		partitions->disk_name ? partitions->disk_name : "NULL");
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		g_debug("\tPartition %d: type: %d size: %d",
			i,
		    originalpartitions[activedisk]->pinfo[i].partition_type,
		    originalpartitions[activedisk]->pinfo[i].partition_size);
	}
	g_debug("Attempting to set partitioning on device %s:",
		partitions->disk_name ? partitions->disk_name : "NULL");
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		g_debug("\tPartition %d: type: %d size: %d",
			i, partitions->pinfo[i].partition_type,
			partitions->pinfo[i].partition_size);
	}
	newpartitions =
		om_validate_and_resize_disk_partitions(omhandle, partitions);
	if (newpartitions == NULL) {
		gchar *warningcode = NULL;
		int16_t error;

		g_warning("Orchestrator not happy with partitioning");
		error = om_get_error();
		switch (error) {
			case OM_UNSUPPORTED_CONFIG:
				warningcode =
					g_strdup("OM_UNSUPPORTED_CONFIG");
				break;
			case OM_NO_DISKS_FOUND:
				warningcode =
					g_strdup("OM_NO_DISKS_FOUND");
				break;
			case OM_NO_SPACE:
				warningcode =
					g_strdup("OM_NO_SPACE");
				break;
			case OM_INVALID_DISK_PARTITION:
				warningcode =
					g_strdup("OM_INVALID_DISK_PARTITION");
				break;
			case OM_FORMAT_UNKNOWN:
				warningsecondarytext =
					g_strdup("OM_FORMAT_UNKNOWN");
				break;
			case OM_BAD_DISK_NAME:
				warningcode =
					g_strdup("OM_BAD_DISK_NAME");
				break;
			case OM_CONFIG_EXCEED_DISK_SIZE:
				warningcode =
					g_strdup("OM_CONFIG_EXCEED_DISK_SIZE");
				break;
			default:
				warningcode =
					g_strdup(_("An unknown internal error (Orchestrator) occured."));
				break;
		}

		g_warning("om_validate_and_resize_disk_partitions () failed.");
		g_warning("\tReason: %s", warningcode);
		if (error == OM_UNSUPPORTED_CONFIG) {
			/* Create a specific error message */
			warningprimarytext =
				g_strdup(_("Unsupported partitioning configuration."));
			warningsecondarytext =
				g_strdup(_("OpenSolaris does not support changing the "
					"partition type when two or more of that "
					"type exist on the disk. Please Quit the "
					"installer, run fdisk in the terminal window "
					"to create the Solaris partition, then restart "
					"the installer."));
		} else {
			/* Create a generic error message */
			warningprimarytext =
			g_strdup(_("Internal partitioning error."));
			warningsecondarytext =
				g_strdup_printf(_("Error code: %s\nThis is an unexpected, "
					"internal error. It is not safe to continue with "
					"installation of this system and you should quit the "
					"installation process now."),
					warningcode);
		}
		g_free(warningcode);
	} else {
		if (partitions == modifiedpartitions[activedisk]) {
			/*
			 * If the user didn't use the default partitioning layout,
			 * update the display if necessary to reflect actual partitioning
			 */
			modifiedpartitions[activedisk] = newpartitions;
			proposedpartitions[activedisk] = modifiedpartitions[activedisk];
			partitionsmatch = disk_partitions_match(partitions, newpartitions);
			om_free_disk_partition_info(omhandle, partitions);
			disk_partitioning_block_all_handlers();
			disk_partitioning_set_from_parts_data(alldiskinfo [activedisk],
				modifiedpartitions[activedisk]);
			disk_partitioning_unblock_all_handlers();
			if (!partitionsmatch) {
				warningprimarytext =
					g_strdup(_("Adjuments were made to the new partitions"));
				warningsecondarytext =
					g_strdup(_("A size adjustment was necessary for one or more of "
						"the new partitions you created. This is due to "
						"existing partitions on the disk. "
						"Click cancel to review the adjustments made"));
			}
		} else if (partitions == defaultpartitions[activedisk]) {
			/*
			 * Even though the default layout shouldn't need any corrections
			 * from the validate_and_resize function, it can happen, probably
			 * because of rounding errors mapping megabytes to disk blocks etc.
			 * So we need to overwrite the defaultlayout we created for the disk
			 * and replace it with what the orchestrator gave us back. But don't
			 * display this to the user or it will look stupid.
			 */
			defaultpartitions[activedisk] = newpartitions;
			proposedpartitions[activedisk] = defaultpartitions[activedisk];
			om_free_disk_partition_info(omhandle, partitions);
		}
	}
#endif /* (__i386) */
	/* Nothing else right now */
	if (warningprimarytext != NULL) {
		gui_install_prompt_dialog(FALSE, FALSE, FALSE,
			GTK_MESSAGE_WARNING,
			warningprimarytext,
			warningsecondarytext);
		g_free(warningprimarytext);
		if (warningsecondarytext)
			g_free(warningsecondarytext);
		return (FALSE);
	}

	return (TRUE);
}

void
installation_disk_store_data()
{
	disk_parts_t *partitions = NULL;
	const gchar *diskname = (alldiskinfo[activedisk]->disk_name);
	partition_info_t *partition = NULL;
	gint i = 0;
	int status = 0;

	partitions = proposedpartitions[activedisk];
	InstallationProfile.diskname = diskname;
	InstallationProfile.disktype =
		orchestrator_om_get_disk_type(alldiskinfo[activedisk]);
	InstallationProfile.disksize =
		orchestrator_om_get_disk_sizegb(alldiskinfo[activedisk]);
#if defined(__i386)
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partition = &partitions->pinfo[i];
		if (partition->partition_type == SUNIXOS2 || \
			(partition->partition_type == SUNIXOS && \
				partition->content_type != OM_CTYPE_LINUXSWAP)) {
			InstallationProfile.installpartsize =
				orchestrator_om_get_partition_sizegb(partition);
			break;
		}
	}

	/*
	 * Tell orchestrator to use this partitioning layout for install
	 * Only gets applied after om_perform_install() is called so not
	 * too late yet.
	 */
	status = om_set_disk_partition_info(omhandle,
		proposedpartitions[activedisk]);
	if (status != OM_SUCCESS) {
		status = om_get_error();
		/*
		 * If setting the partition info failed, things are
		 * screwed but this is unlikely since the partition
		 * data was already validated with any necessary
		 * adjustments already made by the validation call
		 */
		g_critical("Failed to set proposed partitioning layout");
		g_critical("Error code is: %d", status);
	}
#endif
}

static disk_parts_t *
installation_disk_create_default_layout(disk_info_t *diskinfo)
{
	disk_parts_t *partitions;
	partition_info_t *partinfo;
	gint i = 0;

	partitions = g_new0(disk_parts_t, 1);
	partitions->disk_name = g_strdup(diskinfo->disk_name);
	/*
	 * New suggested partition layout:
	 * partition   0:  type = Solaris, size = diskcapacity, active = TRUE
	 * partition 1-3:  type = Unused,  size = 0, active = FALSE
	 */
	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partinfo = &partitions->pinfo[i];
		partinfo->partition_id = i+1;
		partinfo->partition_order = i+1;
		partinfo->partition_offset = 0;
		partinfo->content_type = OM_CTYPE_UNKNOWN;
		if (i == 0) {
			partinfo->partition_type = SUNIXOS2;
			partinfo->partition_size = (uint64_t)
				orchestrator_om_get_disk_sizemb(diskinfo);
			partinfo->active = B_TRUE;
		} else {
			partinfo->partition_type = UNUSED;
			partinfo->partition_size = 0;
			partinfo->active = B_FALSE;
		}
	}
	return (partitions);
}

/*
 * Updates partition structure based on GUI's partitioning controls
 * Skips over partitions that haven't been modified so as not to
 * bork an unsupported partition type or the precise size of the
 * partition.
 */
static void
update_disk_partitions_from_ui(disk_info_t *diskinfo,
	disk_parts_t *partitions,
	PartTypeFlag *typechanges,
	PartSizeFlag *sizechanges)
{
	GtkSpinButton *spinner = NULL;
	GtkComboBox *combo = NULL;
	partition_info_t *partition = NULL;
	gint i = 0;

	g_return_if_fail(diskinfo);
	g_return_if_fail(partitions);
	g_return_if_fail(typechanges);
	g_return_if_fail(sizechanges);

	for (i = 0; i < GUI_INSTALL_NUMPART; i++) {
		partition = orchestrator_om_get_part_by_blkorder(partitions, i);
		combo = GTK_COMBO_BOX
			(MainWindow.InstallationDiskWindow.partitioncombos[i]);
		spinner = GTK_SPIN_BUTTON
			(MainWindow.InstallationDiskWindow.partitionspinners[i]);

		if ((!activediskisreadable) ||\
			(typechanges->partid[i] == TRUE) ||\
			(sizechanges->partid[i] == TRUE)) {
			gfloat size = 0;
			gint index = gtk_combo_box_get_active(combo);
			if (!partition) {
				partition =
					orchestrator_om_find_unused_partition(partitions,
						UNUSED,
						i);
			}
			g_assert(partition != NULL);
			/* Only read part size from UI if it's it's not the initial val */
			size = (gfloat) gtk_spin_button_get_value(spinner);
			if ((!activediskisreadable) ||\
				(sizechanges->partid[i] == TRUE)) {
				orchestrator_om_set_partition_sizegb(partition, size);
			}

			if ((!activediskisreadable) ||\
				(typechanges->partid[i] == TRUE)) {
				switch (index) {
					case 0:
						g_assert(size == 0);
						partition->partition_type = UNUSED;
						break;
					case 1: /* Solaris2 */
						partition->partition_type = SUNIXOS2;
						break;
					default:
						g_warning("Partition %d type is invalid", i+1);
						break;
				}
			}
		}
	}
}
