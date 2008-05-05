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


#ifndef	_SPMIAPP_STRINGS_H
#define	_SPMIAPP_STRINGS_H


/*
 * Module:	spmiapp_strings.h
 * Group:	libspmiapp
 * Description:
 */

#include <libintl.h>

#include <spmiapp_api.h>	/* make sure we get LIBAPPSTR definition */

#ifdef __cplusplus
extern "C" {
#endif

/*
 * i18n:
 * Note: For Warning/Error strings.
 * Unlike in the past, for 2.6 you longer need to hard-code newlines
 * in the error/warning strings.
 */

/*
 * i18n: Common button strings
 * (other than those defined in any spmi_ui* modules)
 */
#define	LABEL_CONTINUE_BUTTON	LIBAPPSTR("Continue")
#define	LABEL_GOBACK_BUTTON	LIBAPPSTR("Go Back")
#define	LABEL_RESET_BUTTON	LIBAPPSTR("Reset")
#define	LABEL_CHANGE_BUTTON	LIBAPPSTR("Change")
#define	LABEL_CUSTOMIZE_BUTTON	LIBAPPSTR("Customize")
#define	LABEL_INITIAL_BUTTON	LIBAPPSTR("Initial")
#define	LABEL_UPGRADE_BUTTON	LIBAPPSTR("Upgrade")
#define	LABEL_AUTOLAYOUT	LIBAPPSTR("Auto-layout")
#define	LABEL_REPEAT_AUTOLAYOUT	LIBAPPSTR("Repeat Auto-layout")
#define	LABEL_ANALYZE		LIBAPPSTR("Analyze")
#define	LABEL_STANDARD		LIBAPPSTR("Standard")
#define	LABEL_FLASH		LIBAPPSTR("Flash")
#define	LABEL_FLASH_ADD_ARCHIVE	LIBAPPSTR("Add")
#define	LABEL_FLASH_EDIT_ARCHIVE	LIBAPPSTR("Edit")
#define	LABEL_FLASH_DEL_ARCHIVE	LIBAPPSTR("Delete")
#define	LABEL_PRODSEL_INFO	LIBAPPSTR("Product Info")
#define	LABEL_ACCEPT_LICENSE    LIBAPPSTR("Accept License")

/*
 * i18n: Common labels
 */
#define	LABEL_SLICE		LIBAPPSTR("Slice")
#define	LABEL_FILE_SYSTEM	LIBAPPSTR("File System")
#define	LABEL_UNKNOWN		LIBAPPSTR("Unknown")

#define	LABEL_SELECT_64		LIBAPPSTR(\
"Select To Include Solaris 64-bit Support")
#define	LABEL_SOLARIS_ROOT_SLICE	LIBAPPSTR("Solaris root slice")
#define	LABEL_STUB_BOOT_PARTITION	LIBAPPSTR("x86boot Partition")

/*
 * Common strings
 */

/*
 * i18n: Common message dialog window titles
 */
#define	TITLE_WARNING	LIBAPPSTR("Warning")
#define	TITLE_ERROR	LIBAPPSTR("Error")
#define	TITLE_INFORMATION	LIBAPPSTR("Information")

/* printed if an app exits ungracefully via a signal */
#define	ABORTED_BY_SIGNAL_FMT	LIBAPPSTR(\
"Exiting (caught signal %d)"\
"\n\n"\
"Type install-solaris to restart.\n")

#define	CAPABILITY_NO_DIRECTORY	LIBAPPSTR(\
	"No capabilitity directory found - using fallbacks.")

#define	INIT_CANT_READ_CAPABILITIES	gettext(\
	"Cannot read the capabilities of this system.\n")

/*
 * Window titles and their corresponding onscreen text...
 */

/*
 * i18n: "The Solaris Installation Program" screen
 */
#define	TITLE_INTRO	LIBAPPSTR("The Solaris Installation Program")

#define	MSG_INTRO	LIBAPPSTR(\
"The Solaris installation program "\
"is divided into a series of short sections "\
"where you'll be prompted to provide "\
"information for the installation. "\
"At the end of each section, you can change "\
"the selections you've made before continuing.")

#define	MSG_INTRO_CUI_NOTE	LIBAPPSTR(\
"\n\n" \
"About navigation..." \
"\n" \
"\t- The mouse cannot be used" \
"\n" \
"\t- If your keyboard does not have function keys, or they do not " \
"\n" \
"\t  respond, press ESC; the legend at the bottom of the screen " \
"\n" \
"\t  will change to show the ESC keys to use for navigation.")

/*
 * i18n: "Solaris Interactive Installation - Initial" screen
 */
#define	TITLE_INTRO_INITIAL	LIBAPPSTR("Solaris Interactive Installation")

#define	MSG_INTRO_INITIAL	LIBAPPSTR(\
"On the following screens, you can accept the defaults " \
"or you can customize how Solaris software will be " \
"installed by:" \
"\n\n" \
"\t- Selecting the type of Solaris software to install" \
"\n" \
"\t- Selecting disks to hold software you've selected" \
"\n" \
"\t- Specifying how file systems are laid out on the disks" \
"\n\n" \
"After completing these tasks, a summary of your "\
"selections (called a profile) will be displayed.")

#define	MSG_INTRO_INITIAL_ICD	LIBAPPSTR(\
"On the following screens, you can accept the defaults " \
"or you can customize how Solaris software will be " \
"installed by:" \
"\n\n" \
"\t- Selecting the type of Solaris software to install" \
"\n" \
"\t- Selecting disks to hold software you've selected" \
"\n" \
"\t- Selecting unbundled products to be installed with Solaris" \
"\n" \
"\t- Specifying how file systems are laid out on the disks" \
"\n\n" \
"After completing these tasks, a summary of your "\
"selections (called a profile) will be displayed.")

#define	MSG_INTRO_INITIAL_OLD	LIBAPPSTR(\
"You'll be using the initial option for installing " \
"Solaris software on the system. The initial option overwrites " \
"the system disks when the new Solaris software is " \
"installed." \
"\n\n" \
"On the following screens, you can accept the defaults " \
"or you can customize how Solaris software will be " \
"installed by:" \
"\n\n" \
"\t- Selecting the type of Solaris software to install" \
"\n" \
"\t- Selecting disks to hold software you've selected" \
"\n" \
"\t- Specifying how file systems are laid out on the disks" \
"\n\n" \
"After completing these tasks, a summary of your "\
"selections (called a profile) will be displayed.")

/*
 * i18n: This is added to the previous string to yield the
 * overall string.  it is separate because some applications
 * do not use flash. Make sure to leave the \n's in there.
 * no lin can be > 79 characters.
 */
#define	MSG_INTRO_INITIAL_FLASH	LIBAPPSTR(\
"\n\nThere are two ways to install your Solaris software:" \
"\n\n" \
" - \"Standard\" installs your system from a standard Solaris Distribution.\n"\
"    Selecting \"Standard\" allows you to choose between initial install\n"\
"    and upgrade, if your system is upgradable.\n"\
" - \"Flash\" installs your system from one or more Flash Archives.")

/*
 * i18n: "Solaris Interactive Installation - Upgrade" screen
 */
#define	TITLE_UPGRADE	LIBAPPSTR("Solaris Interactive Installation")

#define	MSG_UPGRADE	LIBAPPSTR(\
"This system is upgradable, so there are two ways to install the " \
"Solaris software. " \
"\n\n" \
"The Upgrade option updates the Solaris software to the new release, " \
"saving as many modifications to the previous version of Solaris software " \
"as possible.  Back up the system before using the Upgrade option." \
"\n\n" \
"The Initial option overwrites the system disks with the new version of " \
"Solaris software.  This option allows you to preserve any existing file " \
"systems.  Back up any modifications made to the previous version " \
"of Solaris software before starting the Initial option." \
"\n\n" \
"After you select an option and complete the tasks that follow, a summary of " \
"your actions will be displayed.")

/*
 * i18n: this message is sometimes appended to the previous message.
 * The beginning two spaces are important.
 */
#define	MSG_UPGRADE_FLASH	LIBAPPSTR(\
"  If you want to install the system with a Flash archive, select Initial.")

/*
 * i18n: Ask the user if they want to resume an upgrade.
 * 1st %s: root slice we're upgrading (e.g. c0t0d0s0)
 * 2nd %s: Solaris Version of root slice we're upgrading (e.g. Solaris 2.5.1)
 */
#define	UPG_RECOVER_QUERY	LIBAPPSTR(\
"The installation program will resume a "\
"previous upgrade that did not finish. "\
"The slice %s with the %s "\
"version was being upgraded."\
"\n\n" \
"If you don't want to resume the upgrade on this slice, " \
"select Cancel to upgrade a different slice or perform " \
"an initial installation.")

/*
 * i18n: "Allocate Client Services?" screens
 */
#define	TITLE_ALLOCATE_SVC_QUERY	LIBAPPSTR("Allocate Client Services?")

#define	MSG_LOADING_SW	LIBAPPSTR("Loading install media, please wait...")

#define	MSG_ALLOCATE_SVC_QUERY	LIBAPPSTR(\
"Do you want to allocate space for diskless clients and/or AutoClient " \
"systems?")

#define	TITLE_CLIENTALLOC	LIBAPPSTR("Allocate Client Services")

#define	MSG_CLIENTSETUP	LIBAPPSTR(\
"On this screen you can specify the size of root (/) and swap for clients.  " \
"The default number of clients is 5; the default root size is 25 Mbytes; " \
"the default swap size is 32 Mbytes.\n\n" \
"NOTE:  Specifying values on this screen only allocates space for clients. " \
"To complete client setup, you must use Solstice Host Manager after " \
"installing Solaris software.")

#define	TITLE_CLIENTS	LIBAPPSTR("Select Platforms")

#define	MSG_CLIENTS	LIBAPPSTR(\
"On this screen you must specify all platforms for clients that this server " \
"will need to support. The server's platform is selected by default " \
"and cannot be deselected.")

/*
 * i18n: Software selection screens
 */

#define	TITLE_SW	LIBAPPSTR("Select Software")

#define	MSG_SW	LIBAPPSTR(\
"Select the Solaris software to install on " \
"the system.\n\n" \
"NOTE: After selecting a software group, you can add or remove " \
"software by customizing it. However, this requires " \
"understanding of software dependencies and how Solaris " \
"software is packaged.")

#define	MSG_SW64  LIBAPPSTR(\
"Select the Solaris software to install on " \
"the system.\n\n" \
"NOTE: After selecting a software group, you can add or remove " \
"software by customizing it. However, this requires " \
"understanding of software dependencies and how Solaris " \
"software is packaged. The software groups displaying 64-bit " \
"contain 64-bit support.")

#define	MSG_INSUFF_SW	LIBAPPSTR(\
"The following products(s) require more system software than " \
"%s:\n\n%s")

#define	MSG_MORE	LIBAPPSTR(\
"(more)")


#define	TITLE_CUSTOM	LIBAPPSTR("Customize Software")

/*
 * i18n: Select Language screen
 */

#define	TITLE_LOCALES	LIBAPPSTR("Select Languages")

#define	MSG_LOCALES	LIBAPPSTR(\
"Select the languages you want for displaying the user " \
"interface after Solaris software is installed. "\
"English is automatically installed by default.")

#define	TITLE_64	LIBAPPSTR("Select 64 Bit")

#define	MSG_64		LIBAPPSTR(\
"Select 64-bit if you want to install the Solaris " \
"64-bit packages on this system.")

/*
 * i18n: Select Geographic region screen
 */

#define	TITLE_GEO	LIBAPPSTR("Select Geographic Regions")

#define	MSG_GEO		LIBAPPSTR(\
"Select the geographic regions for which support should be " \
"installed.")

#define	MSG_UPGRADE_LOC_NO_DESELECT	LIBAPPSTR("NOTICE: " \
"The following locale is currently installed " \
"and must remain selected for an upgrade: " \
"\n\n%s")

#define	MSG_UPGRADE_GEO_NO_DESELECT	LIBAPPSTR("NOTICE: " \
"The following locale(s) are currently installed " \
"and must remain selected for an upgrade: " \
"\n\n%s")

/*
 * i18n: Select System locale screen
 */
#define	TITLE_SYS_LOCALE	LIBAPPSTR("Select System Locale")

#define	MSG_SYS_LOCALE		LIBAPPSTR(\
"Select the initial locale to be used after the system has been " \
"installed.")

/*
 * i18n: Select Products screen
 */

#define	TITLE_PRODSEL   LIBAPPSTR("Select Products")

#define	MSG_PRODSEL	LIBAPPSTR(\
"Select the products you would like to install.")

/*
 * i18n: Choose Media screen
 */

#define	TITLE_CHOOSEMEDIA   LIBAPPSTR("Choose Media")

#define	MSG_CHOOSEMEDIA		LIBAPPSTR(\
"Please specify the media from which you will install " \
"the Solaris Operating System." \
"\n\n" \
"Media:" \
"\n\n")

#define	CHOOSEMEDIA_NFS_TITLE LIBAPPSTR("Specify Network File System Path")

#define	MSG_CHOOSEMEDIA_NFS_DESC LIBAPPSTR(\
"Please specify the path to the network file system from which " \
"you will install the Solaris Operating System.  Example:\n\n" \
"   NFS Location: server:/path_to_Solaris_image")

#define	CHOOSEMEDIA_NFS_LOCATION	LIBAPPSTR("NFS Location")

#define	MEDIA_NO_PATH		LIBAPPSTR("ERROR: You must specify a path")
#define	MEDIA_NO_HOST		LIBAPPSTR("ERROR: You must specify a host")
#define	MEDIA_BAD_PATH		LIBAPPSTR("ERROR: Path is not absolute")
#define	MEDIA_NO_PING		LIBAPPSTR("ERROR: Host is not responding")
#define	MEDIA_CANT_MOUNT	LIBAPPSTR("ERROR: Unable to mount image")
#define	MEDIA_CANT_MOUNT_DISC	LIBAPPSTR("ERROR: Unable to mount disc")

#define	MEDIA_NOT_SOLARIS	LIBAPPSTR("ERROR: " \
"The directory you specified does not contain a valid Solaris OS image.")
#define	MEDIA_NOT_SOLARIS_CD	LIBAPPSTR("ERROR: " \
"The disc you inserted is not a Solaris OS CD/DVD.")

#define	MEDIA_WRONG_SOLARIS	LIBAPPSTR("ERROR: " \
"The image you specified is an incorrect Solaris OS image.")
#define	MEDIA_WRONG_SOLARIS_CD	LIBAPPSTR("ERROR: " \
"The disc you inserted is an incorrect Solaris OS CD/DVD.")

#define	MEDIA_WRONG_PLATFORM		LIBAPPSTR("ERROR: " \
"The image you specified is not compatible with the " \
"architecture of your system.")
#define	MEDIA_WRONG_PLATFORM_CD		LIBAPPSTR("ERROR: " \
"The Solaris CD/DVD you inserted is not compatible with the " \
"architecture of your system.")

#define	MEDIA_NO_OS_MATCH	LIBAPPSTR("NOTICE: " \
"The Solaris image you specified is not compatible with this installer. " \
"This installer is compatible with the following Solaris " \
"releases:\n\n%s")

#define	MEDIA_NO_OS_MATCH_CD	LIBAPPSTR("NOTICE: " \
"The Solaris CD/DVD you inserted is not compatible with this installer. " \
"This installer is compatible with the following Solaris " \
"releases:\n\n%s")

#define	MEDIA_SELECT_OS_TITLE		LIBAPPSTR("Select Solaris OS")

#define	MEDIA_SELECT_OS			LIBAPPSTR("NOTICE: " \
"Please select the Solaris image you are installing:\n\n")

#define	MEDIA_INITIALIZING_TITLE	LIBAPPSTR("Initializing")

#define	MEDIA_INITIALIZING		LIBAPPSTR(\
"\n\n\n\nThe system is being initialized.")



#define	MEDIA_INSERT_TITLE	LIBAPPSTR("Insert Disc")

#define	MSG_MEDIA_INSERT_DESC	LIBAPPSTR(\
"Please insert the CD/DVD. \n\n" \
"After you insert the disc, select OK. ")

#define	MEDIA_READINGCD_TITLE	LIBAPPSTR("Reading CD/DVD")

#define	MSG_READINGSOLCD_DESC		LIBAPPSTR(\
"\n\n\n\nReading disc for Solaris Operating System. ")

/*
 * i18n: Add Products screen
 */

#define	TITLE_ADDPRODS   LIBAPPSTR("Additional Products")

#define	MSG_ADDPRODS		LIBAPPSTR(\
"To scan for additional products, select the location you " \
"wish to scan. Products found at the selected location that " \
"are in a Web Start Ready install form will be added to the " \
"Products list. " \
"\n\n" \
"Web Start Ready product scan location:" \
"\n\n")

#define	MSG_SCANNING_WSR_DISC		LIBAPPSTR(\
"\n\n\n\nScanning disc looking for Solaris Web Start Ready products. ")

#define	MSG_ADDPRODS_INSERT_DESC	LIBAPPSTR(\
"Please insert the first Solaris Software disc from which " \
"you will install the Solaris Operating System. ")

#define	MSG_NO_WSR_FOUND		LIBAPPSTR(\
"\n\n\n\nNo Solaris Web Start Ready products were found. ")

#define	MSG_NO_WSR_FOUND_DISC		LIBAPPSTR(\
"\n\n\n\nNo Solaris Web Start Ready products were found on this disc. ")

#define	MSG_MISSING_WSR_FILE		LIBAPPSTR(\
"\n\n\n\nMissing Solaris Web Start Ready file:\n\n%s ")

#define	MSG_EMPTY_WSR_FILE		LIBAPPSTR(\
"\n\n\n\nEmpty Solaris Web Start Ready file:\n\n%s ")

#define	MSG_WSR_CDDIR_NOMATCH	LIBAPPSTR(\
"\n\n\n\nCD subdir in cd.name does not match media_kit.toc file. ")

#define	MSG_WSR_CDNAME_NOMATCH	LIBAPPSTR(\
"\n\n\n\nMissing cd.info entry:\n\n%s ")

#define	MSG_WSR_NO_CDINSTALLER	LIBAPPSTR(\
"\n\n\n\nNo CD_INSTALLER in %s ")

#define	MSG_WSR_NO_MERGE	LIBAPPSTR(\
"\n\n\n\nUnable to merge:\n\n%s ")

#define	MSG_WSR_NO_CREATE	LIBAPPSTR(\
"\n\n\n\nUnable to create:\n\n%s ")

#define	MSG_WSR_NO_COPY		LIBAPPSTR(\
"\n\n\n\nUnable to copy:\n\n%s ")

#define	MSG_WSR_NO_DUPS	LIBAPPSTR(\
"\n\n\n\nIgnoring attempt to add duplicate subdir and/or CD name. ")

#define	TITLE_WSR_REMOUNT   LIBAPPSTR("Remounting Image")

#define	MSG_WSR_REMOUNTING	LIBAPPSTR(\
"\n\n\n\nRemounting Solaris image... ")

#define	LABEL_NONE	LIBAPPSTR("None")
#define	LABEL_CDDVD	LIBAPPSTR("CD/DVD")
#define	LABEL_KIOSK	LIBAPPSTR("Kiosk Download")
#define	LABEL_FILESYS	LIBAPPSTR("Network File System")
#define	LABEL_NETFILESYS	LIBAPPSTR("Network File System")

/*
 * i18n:
 */
#define	ADDPRODS_NFS_TITLE LIBAPPSTR("Specify Network File System Path")

#define	MSG_ADDPRODS_NFS_DESC LIBAPPSTR(\
"Please specify the path to the network file system from which " \
"you will install Additional Products.  For example:\n\n" \
"   NFS Location: server:path_to_install_area")

#define	ADDPRODS_NFS_LOCATION	LIBAPPSTR("NFS Location")


#define	MSG_ADDPRODS_KIOSK_NOTFOUND LIBAPPSTR(\
"No Solaris Web Start Ready products were found in the Kiosk download " \
"area. ")



/*
 * i18n: Patch Analyzer screens
 */

/* i18n: Generic patch analyzer title string */
#define	TITLE_PATCH_ANALYSIS	LIBAPPSTR("Patch Analysis")

/* i18n: Run the Patch Analyzer? screen */
#define	TITLE_PA_REQUEST	TITLE_PATCH_ANALYSIS

/*
 * i18n: The %s's below will be replaced by `Solaris <version>'
 *       (e.g. `Solaris 2.7')
 */
#define	MSG_PA_REQUEST		LIBAPPSTR(\
"You have selected an upgrade from %s to a %s Update Release.  " \
"Any patches that you applied to your system that are not included " \
"in the Update Release will be removed.  An analysis of your system " \
"will determine which (if any) patches will be removed." \
"\n\n" \
"> To perform the analysis, select Analyze.\n\n" \
"> To skip the analysis and proceed with the upgrade, select Continue.")

/*
 * i18n: Patch Analyzer Summary screen
 *
 * Screen layout:
 *   2st string
 *
 *   4rd/5th string
 *   6th/7th string
 *   8th/9th string
 *
 * 3rd string (appears only if one of 4th, 6th, or 8th strings are used)
 */
#define	TITLE_PA_SUMMARY	LIBAPPSTR("Patch Analysis - Summary")

#define	MSG_PA_SUMMARY		LIBAPPSTR(\
"Patch Analysis has determined that the upgrade will have the " \
"following effect(s) on the patches applied to your system:")

#define	MSG_PA_SUMMARY_DETAIL	LIBAPPSTR(\
"The following screens explain the information summarized above.")

/* i18n: These 6 strings must be no more than 1 line each */
#define	MSG_PA_SUMM_REM_NUM	LIBAPPSTR("%3d Patch(es) will be removed.")
#define	MSG_PA_SUMM_REM_NONE	LIBAPPSTR(" No Patches will be removed.")

#define	MSG_PA_SUMM_DWN_NUM	LIBAPPSTR("%3d Patch(es) will be downgraded.")
#define	MSG_PA_SUMM_DWN_NONE	LIBAPPSTR(" No Patches will be downgraded.")

#define	MSG_PA_SUMM_ACC_NUM	LIBAPPSTR("%3d Patch(es) will be accumulated.")
#define	MSG_PA_SUMM_ACC_NONE	LIBAPPSTR(" No Patches will be accumulated.")

/* i18n: Patch Analyzer Patches to be Removed screen */
#define	TITLE_PA_REMOVALS	LIBAPPSTR("Patch Analysis - Removals")

#define	MSG_PA_REMOVALS		LIBAPPSTR(\
"Upgrading your system will cause the following patches to be " \
"removed:")

/*
 * i18n: Patch Analyzer Patches to be Downgraded screen
 *
 * The first string is the title.  The second appears as the explanation
 * at the top of the screen.  The remainder of the screen is a list of
 * patches and revs, formatted using the third string.
 */
#define	TITLE_PA_DOWNGRADES	LIBAPPSTR("Patch Analysis - Downgrades")

#define	MSG_PA_DOWNGRADES	LIBAPPSTR(\
"Upgrading your system will cause the following downgrades to occur:")

/*
 * i18n: The next three strings are column titles for a table.
 *
 * First string (Patch):
 *			Both lines can be used, max 15 characters per line.
 * Second string (From Revision):
 *			Both lines can be used, max 15 characters per line.
 * Third string (To Revision):
 *			Both lines can be used, max 15 characters per line.
 */
#define	PA_DOWNGRADES_PATCHID	LIBAPPSTR(\
"\n" \
"Patch")
#define	PA_DOWNGRADES_FROM	LIBAPPSTR(\
"From\n" \
"Revision")
#define	PA_DOWNGRADES_TO	LIBAPPSTR(\
"To\n" \
"Revision")

/* i18n: Patch Analyzer Patches to be Accumulated screen */
#define	TITLE_PA_ACCUMULATIONS	LIBAPPSTR("Patch Analysis - Accumulations")

#define	MSG_PA_ACCUMULATIONS	LIBAPPSTR(\
"Upgrading your system will cause the following accumulations to occur:")

/*
 * i18n: The next three strings are column titles for a table.
 *
 * First string (Existing Patch):
 *			Both lines can be used, max 20 characters per line.
 * Second string (Accumulation Patch):
 *			Both lines can be used, max 20 characters per line.
 */
#define	PA_ACCUMULATIONS_EXISTING	LIBAPPSTR(\
"Existing\n" \
"Patch")
#define	PA_ACCUMULATIONS_ACCUMULATOR	LIBAPPSTR(\
"Accumulated\n" \
"By")

/* i18n: Patch Analyzer failed notice */
#define	TITLE_PA_ANALYZE_FAILED LIBAPPSTR("Patch Analysis Failed")

#define	MSG_PA_ANALYZE_FAILED_EXEC LIBAPPSTR(\
"The Patch Analysis failed because the analyzer was unable to be " \
"executed.  Your install media may be corrupt.\n\n" \
"> To ignore this error and continue the upgrade, select Continue.\n\n" \
"> To exit, select Exit.")

#define	MSG_PA_ANALYZE_FAILED_PARSE LIBAPPSTR(\
"The Patch Analysis failed because the analyzer returned unexpected " \
"output.  Your install media may be corrupt.\n\n" \
"> To ignore this error and continue the upgrade, select Continue.\n\n" \
"> To exit, select Exit.")

/* i18n: Patch Analysis finale screen */
#define	TITLE_PA_FINALE		TITLE_PATCH_ANALYSIS

#define	MSG_PA_FINALE	LIBAPPSTR(\
"The Patch Analysis is complete.  You may continue with the upgrade " \
"or exit." \
"\n\n" \
"> To continue the upgrade, select Continue.\n\n" \
"> To exit without upgrading, select Exit.")

/*
 * i18n: Select Disks screens
 */
#define	TITLE_USEDISKS	LIBAPPSTR("Select Disks")

#define	MSG_USEDISKS	LIBAPPSTR(\
"Select the disks for installing Solaris " \
"software. Start by looking at the Required field; this " \
"value is the approximate space needed to install the " \
"software you've selected. Keep selecting disks until the Total " \
"Selected value exceeds the Required value.\n\n" \
"> To move a disk from the Available to the Selected window, " \
"click on the disk, then click on the > button.")

/*
 * i18n: flash screens
 */

/* i18n: Max 72 characters in length */
#define	FLASH_PROGRESS_BEGINNING_ARCHIVE LIBAPPSTR("Extracting Archive:")

/*
 * i18n: The following three messages are components of a single
 * message.  They are used as needed, but always in the order
 * listed here.  That is, the possible messages are:
 *
 * Extracted xx.xx MB
 * Extracted xx.xx MB in xx files
 * Extracted xx.xx MB (xx% of xx.xxMB)
 * Extracted xx.xx MB (xx% of xx.xxMB) in xx files
 */
#define	MSG_FLASH_EXTRACTED_MB			gettext(\
	"Extracted %7.2f MB%s%s")
#define	MSG_FLASH_EXTRACTED_PCT			gettext(\
	" (%3d%% of %7.2f MB archive)")
#define	MSG_FLASH_EXTRACTED_FILES		gettext(\
	" in %5d files")

/*
 * i18n: Each of the following three messages, when translated,
 * should be <= 72 chars
 */
#define	MSG0_RESTART_TIMEOUT		LIBAPPSTR(\
	"Connection timed out.  Attempting to reconnect...")
#define	MSG0_RESTART_REFUSED		LIBAPPSTR(\
	"Unable to connect.  Attempting to reconnect...")
#define	MSG0_RESTART_SERVERCLOSE	LIBAPPSTR(\
	"Connection unexpectedly closed by server.  Attempting to reconnect...")

#define	MSG_FLASH_ARCHIVES_DESC LIBAPPSTR(\
"You selected the following Flash archives to use to install this " \
"system.  If you want to add another archive to install select \"New\".")

#define	FLASH_ARCHIVES_TITLE LIBAPPSTR("Flash Archive Selection")

#define	FLASH_ADD_ARCHIVES_TITLE LIBAPPSTR("Flash Archive Addition")

#define	FLASH_EDIT_ARCHIVES_TITLE LIBAPPSTR("Flash Archive Configuration")

#define	FLASH_ARCHIVE_SCREEN	LIBAPPSTR("Select Flash Archive Screen")

#define	FLASH_RETRIEVAL_METHOD	LIBAPPSTR("Flash Archive Retrieval Method")

#define	FLASH_CURRENT_CONFIG	LIBAPPSTR("Currently Configured Archives")

/*
 * Flash archive access error messages
 */
#define	FLASH_NO_ARCHIVES	LIBAPPSTR("<No Archives Configured...>")

#define	ARCHIVE_BAD_HTTP		LIBAPPSTR("ERROR: Invalid HTTP URL")
#define	ARCHIVE_BAD_HTTP_PROXYPORT	LIBAPPSTR("ERROR: Invalid Proxy Port")
#define	ARCHIVE_NO_DEVICE	LIBAPPSTR("ERROR: You must specify a device")
#define	ARCHIVE_BAD_LOCALTAPE_POSITION	LIBAPPSTR("ERROR: Invalid tape " \
"position")
#define	ARCHIVE_NO_PATH			LIBAPPSTR("ERROR: You must specify " \
"a path")
#define	ARCHIVE_NO_LOCALDEVICE_FSTYPE	LIBAPPSTR("ERROR: You must specify " \
"a device filesystem type")
#define	ARCHIVE_NO_HOST		LIBAPPSTR("ERROR: You must specify a host")
#define	ARCHIVE_NO_USER		LIBAPPSTR("ERROR: You must specify a username")
#define	ARCHIVE_NO_PASS		LIBAPPSTR("ERROR: You must specify a password")


#define	ARCHIVE_OPENING_ARCHIVE	LIBAPPSTR("Attempting to locate archive, " \
"Please Wait...")

#define	ARCHIVE_NO_OPEN		LIBAPPSTR("ERROR: Could not find archive")
#define	ARCHIVE_NO_OPEN_FTP	LIBAPPSTR("ERROR: Could not find archive or" \
" unsupported FTP server")
#define	ARCHIVE_NO_MOUNT		LIBAPPSTR("ERROR: Could not mount " \
"archive")
#define	ARCHIVE_BAD_HOST	LIBAPPSTR("ERROR: Could not connect to host")
#define	ARCHIVE_NO_SIZE		LIBAPPSTR("ERROR: Archive has no size " \
"information")
#define	ARCHIVE_SERVER_REPLY	LIBAPPSTR("Server replied: %s")
#define	ARCHIVE_NOT_VALID	LIBAPPSTR("ERROR: Archive found, but is " \
"not a valid Flash archive")
#define	ARCHIVE_NO_CLOSE	LIBAPPSTR("Could not close archive")
#define	ARCHIVE_NO_AUTH		LIBAPPSTR("Could not authenticate %s")

/* i18n: 21 chars max */
#define	FLASH_RETR_METHOD	LIBAPPSTR("Retrieval Method")
/* i18n: 35 chars max */
#define	FLASH_NAME		LIBAPPSTR("Name")
#define	FLASH_TYPE_LOCALFILE	LIBAPPSTR("Local File")
#define	FLASH_TYPE_LOCALTAPE	LIBAPPSTR("Local Tape")
#define	FLASH_TYPE_LOCALDEVICE	LIBAPPSTR("Local Device")

/*
 * i18n: labels for field entry.  Most have a length limit.
 */

/*
 * i18n: line 3, only "NFS Location" needs localization
 */
#define	MSG_FLASH_NFS_DESC LIBAPPSTR(\
"Please specify the path to the network file system where the " \
"Flash archive is located.  For example:\n\n" \
"   NFS Location: syrinx:/export/archive.flar")

/*
 * i18n: left side of line 3 should be localized.
 */
#define	MSG_FLASH_LF_DESC LIBAPPSTR(\
"Please specify the local file path where the " \
"Flash archive is located.  For example:\n\n" \
"   Path: /export/archive.flar")

/*
 * i18n: the left side of lines 4-5 should be localized.
 * the right side should *not*
 */
#define	MSG_FLASH_LT_DESC LIBAPPSTR(\
"Please specify the local tape device and the position on " \
"the tape where the Flash archive is located.  The position " \
"must be non-negative.  For example:\n\n" \
"    Device: /dev/rmt/0\n" \
"  Position: 3")

/*
 * i18n: the left side of lines 4-6 should be localized.
 * the right side should *not*
 */
#define	MSG_FLASH_LD_DESC LIBAPPSTR(\
"Please specify the local device, the path to the Flash Archive, " \
"and the type of filesystem on which the Flash archive is located. " \
"For example:\n\n" \
"         Device: /dev/dsk/c0t6d0s0\n" \
"           Path: /path/to/archive.flar\n" \
"Filesystem Type: hsfs")

/*
 * i18n: right side of line 2 should not be localized.
 */
#define	MSG_FLASH_HTTP_URL_DESC LIBAPPSTR(\
"First, specify the URL to access the Flash archive.  For example:\n\n" \
"   URL: http://www.host.com:80/path/to/archive.flar\n\n" \
"Second, specify the Proxy information needed to access the Flash archive. " \
"If no proxy is required, leave the \"Proxy Host\" field blank.")

/*
 * i18n: right side of line 2 should not be localized.
 */
#define	MSG_FLASH_HTTPS_URL_DESC LIBAPPSTR(\
"First, specify the URL to access the Flash archive.  For example:\n\n" \
"   URL: http://www.host.com/path/to/archive.flar\n\n" \
"To use HTTPS, the URL must begin with https://" \
"Second, specify the Proxy information needed to access the Flash archive. " \
"If no proxy is required, leave the \"Proxy Host\" field blank.")

/*
 * i18n: the left side of lines 5-10 should be localized.
 * the right side should *not*
 */
#define	MSG_FLASH_FTP_DESC LIBAPPSTR(\
"Please specify the FTP server, path, username, and password for the " \
"Flash Archive.  If you are behind a firewall, enter proxy information. " \
"For example:\n\n" \
"           Host: ftp.sun.com\n" \
"           Path: /path/to/archive.flar\n" \
"           Username: bob\n" \
"           Password: ********\n" \
"           Proxy Host: firewall.eng\n" \
"           Proxy Port: 8080\n")

/* i18n: 24 chars max */
#define	FLASH_NFS_LOCATION	LIBAPPSTR("NFS Location")

/* i18n: 24 chars max */
#define	FLASH_HTTP_URL		LIBAPPSTR("URL")

/* i18n: 24 chars max */
#define	FLASH_HTTP_PROXYHOST	LIBAPPSTR("Proxy Host")

/* i18n: 24 chars max */
#define	FLASH_HTTP_PROXYPORT	LIBAPPSTR("Proxy Port")


/* i18n: 24 chars max */
#define	FLASH_LF_PATH		LIBAPPSTR("Path")

/* i18n: 24 chars max */
#define	FLASH_LT_DEVICE		LIBAPPSTR("Device")

/* i18n: 24 chars max */
#define	FLASH_LT_POSITION	LIBAPPSTR("Position")

/* i18n: 24 chars max */
#define	FLASH_LD_FILESYS	LIBAPPSTR("Filesystem Type")

/* i18n: 40 chars max */
#define	FLASH_AVAILABLE_RETR	LIBAPPSTR("Available Retrieval Methods")

/* i18n: 24 chars max */
#define	FLASH_FTP_HOST		LIBAPPSTR("FTP Server")

/* i18n: 24 chars max */
#define	FLASH_FTP_PATH		LIBAPPSTR("Path to file")

/* i18n: 24 chars max */
#define	FLASH_FTP_USER		LIBAPPSTR("FTP Username")

/* i18n: 24 chars max */
#define	FLASH_FTP_PASS		LIBAPPSTR("FTP Password")




/*
 * i18n: Edit Disks screens
 */
#define	TITLE_STUB_DELETE_EXISTING	LIBAPPSTR(\
"Delete existing x86boot partition?")

#define	MSG_STUB_DELETE_QUESTION	LIBAPPSTR(\
"Do you really want to delete this x86boot partition?\n\n" \
"%s" \
"\n\n" \
"%s")

#define	MSG_STUB_DELETE_EXISTING	LIBAPPSTR(\
"This partition appears to point to a Solaris installation whose root " \
"filesystem is on %s.  No attempt has been made to verify that a valid " \
"Solaris installation exists at that location.  By deleting this x86boot " \
"partition, you could render that Solaris installation unusable.")

#define	MSG_STUB_DELETE_IS_BOOT		LIBAPPSTR(\
"This partition is the x86boot partition for the current installation.  " \
"By deleting it, you are indicating that this installation should not " \
"use an x86boot partition.  If you want to use an x86boot partition for " \
"this installation, you should select another one (if any) on the disk " \
"selection screen or create another one.")

/*
 * i18n: Boot Device screens
 */
#define	TITLE_SELECT_BOOT_DISK	LIBAPPSTR("Select Boot Disk")

/* i18n: Window Title and Label (x86) */
#define	UPDATE_PROM_QUERY_x86	LIBAPPSTR("Reconfigure BIOS?")

/* i18n: Window Title and Label (sparc) */
#define	UPDATE_PROM_QUERY_SPARC	LIBAPPSTR("Reconfigure EEPROM?")

/* i18n: List Selection */
#define	APP_NOPREF_CHOICE	LIBAPPSTR("No Preference")

/* i18n: These words get subbed into the messages according to conditions */
#define	APP_SLICE	LIBAPPSTR("slice")
#define	APP_DISK	LIBAPPSTR("disk")
#define	APP_PARTITION	LIBAPPSTR("partition")

/*
 * i18n: messages for dialogs that ask the user which stub boot (x86boot)
 * partitions (if any) to use.
 */
#define	TITLE_CHOOSE_STUB	LIBAPPSTR("Use x86boot partition?")

#define	MSG_CHOOSE_STUB_ONE	LIBAPPSTR(\
"An x86boot partition has been detected on %s.  It points to a Solaris " \
"root filesystem on %s, though no attempt has been made to verify that " \
"a valid Solaris system exists at that location.  Do you want to use this " \
"x86boot partition to be reused now when you install the system?\n\n" \
"WARNING: If you elect to reuse this x86boot partition, the Solaris system " \
"whose root filesystem is on %s will be rendered unusable.")

#define	MSG_CHOOSE_STUB_MANY	LIBAPPSTR(\
"x86boot partitions have been detected on the disks listed below.  They " \
"point to the indicated Solaris root filesystems.  No attempt has been " \
"made to determine whether or not the listed root filesystems are valid " \
"installations of Solaris.  If you would like to reuse one of the listed " \
"x86boot partitions when you install, select it and press `OK'.  If not, " \
"select `%s' and press `OK'.")

#define	MSG_CHOOSE_STUB_MANY_WARNING	LIBAPPSTR(\
"WARNING: If you choose one of the above x86boot partitions, the Solaris " \
"installation whose root filesystem is on the corresponding disk will be " \
"rendered unusable.")

#define	MSG_CHOOSE_STUB_NOTA	LIBAPPSTR("None of the above")

#define	MSG_STUB_TARGET_UNKNOWN		LIBAPPSTR(\
"an unknown disk.")

#define	TITLE_ABANDON_STUB_PARTITION	LIBAPPSTR(\
"Deselect existing x86boot partition?")

#define	MSG_ABANDON_STUB_PARTITION	LIBAPPSTR(\
"Do you really want to change the boot disk to %s?  The previous " \
"boot disk (%s) was configured to use the x86boot partition on that " \
"disk.  If you change the boot disk to %s, the x86boot partition on " \
"%s will no longer be used and may need to be deleted.")

#define	TITLE_SELECT_BOOT_PARTITION	LIBAPPSTR(\
"Use x86boot partition?")

#define	MSG_SELECT_BOOT_PARTITION	LIBAPPSTR(\
"The disk you selected (%s) contains both an x86boot partition and a " \
"Solaris partition.  Do you want to use the x86boot partition on this " \
"disk?  If you don't want to use the x86boot partition, the Solaris " \
"partition will be used instead." \
"\n\n%s")

#define	MSG_SELECT_BOOT_PART_EXIST_WARN	LIBAPPSTR(\
"NOTE: The x86boot partition on this disk existed before this installation " \
"session began.  It may be in use by another Solaris installation.")

/*
 * i18n: Preserve Data? screens
 */
#define	TITLE_PREQUERY	LIBAPPSTR("Preserve Data?")

#define	MSG_PREQUERY	LIBAPPSTR(\
"Do you want to preserve existing data? At least one of the disks you've " \
"selected for installing Solaris software has file systems or unnamed "\
"slices that you may want to save.")

/* i18n: Preserve Data screen */
#define	TITLE_PRESERVE	LIBAPPSTR("Preserve Data")

#define	MSG_PRESERVE	LIBAPPSTR(\
"On this screen you can preserve the data on some or all disk slices. " \
"Any slice you preserve will not be touched when Solaris software is " \
"installed. " \
"If you preserve data on / (root), /usr, or /var you must " \
"rename them because new versions of these file systems are created " \
"when Solaris software is installed.\n\n" \
"WARNING: Preserving an `overlap' slice will not preserve any data within it. "\
"To preserve this data, you must explicitly set the mount point name.")

/*
 * i18n: Auto Layout screens
 */

/* i18n: Warning Message Title */
#define	TITLE_AUTOLAYOUT_BOOT_WARNING	LIBAPPSTR(\
"Warning: Different Boot Device")

/* i18n: Warning Message Text */
#define	MSG_AUTOLAYOUT_BOOT_WARNING	LIBAPPSTR(\
"Because you have changed the boot device (where the " \
"root ('/') file system will be created) from %s, you must " \
"re-layout your disks to sync up file systems.")

#define	MSG_BOOT_PREVIOUS	LIBAPPSTR(\
"its previous location")

/*
 * i18n: File System and Disk Layout screen
 */
#define	TITLE_FILESYS	LIBAPPSTR("File System and Disk Layout")

#define	MSG_FILESYS	LIBAPPSTR(\
"The summary below is your current file system and disk layout, " \
"based on the information you've supplied.\n\n" \
"NOTE: If you choose to customize, you should understand file " \
"systems, their intended purpose on the disk, and how changing " \
"them may affect the operation of the system.")

/*
 * i18n: Customize Disks screen
 */
#define	TITLE_CUSTDISKS	LIBAPPSTR("Customize Disks")

/*
 * i18n: Customize Disks by Cylinder screen
 */
#define	TITLE_CYLINDERS	LIBAPPSTR("Customize Disks by Cylinders")

/*
 * i18n: Profile screen
 */
#define	TITLE_PROFILE	LIBAPPSTR("Profile")

#define	MSG_SUMMARY	LIBAPPSTR(\
"The information shown below is your profile for " \
"installing Solaris software. It reflects the choices " \
"you've made on previous screens.")

#define	BOOTOBJ_SUMMARY_NOTE	LIBAPPSTR(\
"\n\n" \
"NOTE:  You must change the BIOS because you " \
"have changed the default boot device.")

/*
 * i18n: the various install type labels on the Profile summary screen
 */
#define	INSTALL_TYPE_INITIAL_STR	LIBAPPSTR(\
"Initial")
#define	INSTALL_TYPE_FLASH_STR		LIBAPPSTR(\
"Flash")
#define	INSTALL_TYPE_FLASH_ARCHIVE_STR	LIBAPPSTR(\
"Flash Archive")
#define	INSTALL_TYPE_FLASH_ARCHIVES_STR	LIBAPPSTR(\
"Flash Archives")
#define	INSTALL_TYPE_UPGRADE_STR	LIBAPPSTR(\
"Upgrade")
#define	INSTALL_TYPE_UPGRADE_DSR_STR	LIBAPPSTR(\
"Upgrade")

/* i18n: prom upgrade required in profile screen */
#define	PROM_UPGRADE_REQUIRED		LIBAPPSTR(\
"\n\n" \
"ATTENTION: You must upgrade the OpenBoot " \
"flash PROM before this system can run in " \
"64-bit mode. Until you perform this upgrade, " \
"this system can run only in 32-bit mode. " \
"For upgrade instructions, see the " \
"hardware platform documentation for this Solaris " \
"release.\n")

/* i18n: upgrade slice label in profile screen */
#define	APP_SUMMARY_UPG_TARGET	LIBAPPSTR("\nUpgrade Target:")

/* i18n: backup media label in profile screen */
#define	APP_SUMMARY_DSR_BACKUP_MEDIA	LIBAPPSTR(\
"\nBackup media:")

#define	APP_SUMMARY_FSLAYOUT	LIBAPPSTR(\
"\nFile System and Disk Layout:\n")

#define	APP_ER_CHECK_DISKS	LIBAPPSTR(\
"The following disk configuration condition(s) "\
"have been detected. Errors must be fixed "\
"to ensure a successful installation. "\
"Warnings can be ignored without causing the "\
"installation to fail.")

#define	APP_ER_ROOT_PAST_CYL_1023	LIBAPPSTR(\
"The root (/) file system must lie entirely within the " \
"first 1023 cylinders of the disk drive which contains it.\n\n" \
"To fit the root file system into the first 1023 cylinders of the " \
"disk drive,\n\n" \
" - Install the root file system on the lowest-numbered available\n" \
"   slice\n\n" \
"and\n\n" \
" - Reduce the size of the root slice to %d MB or less.\n\n" \
"You can reduce the required size of the root slice by creating one " \
"or more subdirectories of root (e.g. /usr, /opt, /var, or /usr/openwin) " \
"on remaining unused slices, reserving slice 2 as the overlap slice.")

/*
 * i18n: for warning screen at end of install parade
 * Appears when the boot device is different from the current
 * one and the user has not chosen to have install automatically
 * change the bios.
 */
#define	APP_WARN_BOOT_PROM_CHANGE_REQ_x86	LIBAPPSTR(\
"CHANGE DEFAULT BOOT DEVICE\n" \
"If you want the system to always reboot Solaris " \
"from the boot device that you have specified, " \
"you must change the system's BIOS default boot device " \
"after installing Solaris software.")

/*
 * i18n: for warning screen at end of install parade
 * Appears when the boot device is different from the current
 * one and the user has not chosen to have install automatically
 * change the prom.
 */
#define	APP_WARN_BOOT_PROM_CHANGE_REQ_SPARC	LIBAPPSTR(\
"CHANGE DEFAULT BOOT DEVICE\n" \
"If you want the system to always reboot Solaris "\
"from the boot device that you've specified, you must "\
"change the system's default boot device using the eeprom(1M) "\
"command after installing Solaris software.")

/*
 * i18n: for warning screen at end of install parade
 * Appears when the boot device is different from the current
 * one and the user has not chosen to have install automatically
 * change the bios.
 *
 * This currently (in 2.6) never can happen on an x86,
 * but is in here is case in the future the library can do
 * BIOS configuration
 * changes.
 */
#define	APP_WARN_BOOT_PROM_CHANGING_x86	LIBAPPSTR(\
"CHANGING DEFAULT BOOT DEVICE\n" \
"You have either explicitly changed the "\
"default boot device, or accepted the "\
"default to \"Reconfigure BIOS\". In either "\
"case, the system's BIOS will be changed "\
"so it will always boot Solaris from the "\
"device that you've specified. If this is "\
"not what you had in mind, "\
"go back to the disk selection screens and "\
"change the \"Reconfigure BIOS\" setting.")

/*
 * i18n: for warning screen at end of install parade
 * Appears when the boot device is different from the current
 * one and the user has chosen to have install automatically
 * change the bios.
 */
#define	APP_WARN_BOOT_PROM_CHANGING_SPARC	LIBAPPSTR(\
"CHANGING DEFAULT BOOT DEVICE\n" \
"You have either explicitly changed the "\
"default boot device, or accepted the "\
"default to \"Reconfigure EEPROM\". In either "\
"case, the system's EEPROM will be changed "\
"so it will always boot Solaris from the "\
"device that you've specified. If this is "\
"not what you had in mind, "\
"go back to the disk selection screens and "\
"change the \"Reconfigure EEPROM\" setting.")

/*
 * i18n: Auto Eject of CDs/DVDs screen
 */
#define	TITLE_AUTOEJECT	LIBAPPSTR("Eject a CD/DVD Automatically?")

#define	MSG_AUTOEJECT	LIBAPPSTR(\
"During the installation of Solaris software, you may be using "\
"one or more CDs/DVDs. You can choose to have the system eject each CD/DVD "\
"automatically after it is installed or you can " \
"choose to manually eject each CD/DVD.")

#define	MSG_X86_AUTOEJECT	LIBAPPSTR(\
"During the installation of Solaris software, you may be using "\
"one or more CDs/DVDs. With the exception of the currently booted CD/DVD, "\
"you can choose to have the system eject each CD/DVD "\
"automatically after it is installed or you can " \
"choose to manually eject each CD/DVD. "\
"\n\nNote: The currently booted CD/DVD must be manually ejected during system "\
"reboot.")

/*
 * i18n: Reboot After Installation? screen
 */
#define	TITLE_REBOOT	LIBAPPSTR("Reboot After Installation?")

#define	MSG_REBOOT	LIBAPPSTR(\
"After Solaris software is installed, the system must be rebooted. "\
"You can choose to have the system automatically reboot, or you can " \
"choose to manually reboot the system if you want to run scripts " \
"or do other customizations before the reboot.  You can manually " \
"reboot a system by using the reboot(1M) command.")

#define	X86_CD_REBOOT_INFO	LIBAPPSTR(\
"\n\nYou may need to manually eject the CD/DVD or select a different " \
"boot device after reboot to avoid repeating the " \
"installation process.")

/*
 * i18n: Special formatting needed for this string in pfinstall
 */
#define	PF_X86_CD_REBOOT_INFO	LIBAPPSTR(\
"\n\nYou may need to eject the CD or select a different\n" \
"boot device after reboot to avoid repeating the\n" \
"installation process.")

/*
 * i18n: "Installing Solaris Software - Progress" screen
 */
#define	TITLE_PROGRESS	LIBAPPSTR(\
"Installing Solaris Software - Progress")

#define	MSG_PROGRESS	LIBAPPSTR(\
"The Solaris software is now being installed on the system " \
"using the profile you created. Installing Solaris software can take " \
"up to 2 hours depending on the software you've " \
"selected and the speed of the network or local CD-ROM. " \
"\n\n" \
"When Solaris software is completely installed, the message " \
"`Installation complete' will be displayed.\n")

#define	LABEL_PROGRESS_PARTITIONING	LIBAPPSTR(\
"Partitioning disks...")
#define	LABEL_PROGRESS_INSTALL	LIBAPPSTR("Installing: ")
#define	LABEL_PROGRESS_COMPLETE	LIBAPPSTR("Installation complete")

/*
 * i18n: "Upgrading Solaris Software - Progress" screen
 */
#define	TITLE_UPG_PROGRESS	LIBAPPSTR(\
"Upgrading Solaris Software - Progress")

#define	MSG_UPG_PROGRESS	LIBAPPSTR(\
"The Solaris software is now being upgraded on the system "\
"using the profile you created. Upgrading Solaris software can take "\
"up to 2 hours (may be longer on servers) depending on the software you've "\
"selected, the reallocation of any space if needed, and the speed of "\
"the network or local CD-ROM. "\
"\n\n"\
"When Solaris software is completely upgraded, the message "\
"`Upgrade complete' will be displayed.")


/* i18n: 28 chars max */
#define	LABEL_PROGRESS_INSTALLING	LIBAPPSTR("Installing")

/* i18n: 65 chars max */
#define	LABEL_FLASH_INSTALL	LIBAPPSTR(\
"Solaris Flash Install")

/* i18n: 65 chars max */
#define	LABEL_INITIAL_INSTALL	LIBAPPSTR(\
"Solaris Initial Install")

/* i18n: 28 chars max */
#define	LABEL_MBYTES_INSTALLED	LIBAPPSTR(\
"MBytes Installed")

/* i18n: 28 chars max */
#define	LABEL_MBYTES_REMAINING	LIBAPPSTR(\
"MBytes Remaining")

#define	LABEL_UPG_PROGRESS	LIBAPPSTR(\
"Upgrading")

/*
 * i18n: Mount Remote File Systems? screen
 */
#define	TITLE_MOUNTQUERY	LIBAPPSTR("Mount Remote File Systems?")

#define	MSG_MOUNTQUERY	LIBAPPSTR(\
"Do you want to mount software from a remote file server? This may be " \
"necessary if you had to remove software because of disk space problems.")

/*
 * i18n: Mount Remote File Systems screen
 */
#define	TITLE_MOUNTREMOTE	LIBAPPSTR("Mount Remote File Systems")

#define	TITLE_REMOTEMOUNT_STATUS	LIBAPPSTR("Mount Remote File Systems")

/*
 * i18n: "Automatically Layout File Systems" screen
 */
#define	TITLE_AUTOLAYOUT	LIBAPPSTR(\
"Automatically Layout File Systems")

#define	MSG_AUTOLAYOUT	LIBAPPSTR(\
"On this screen you must select all the file systems you want auto-layout " \
"to create, or accept the default file systems shown.\n\n" \
"NOTE: For small disks, it may be necessary " \
"for auto-layout to break up some of the file systems you request " \
"into smaller file systems to fit the available disk space. So, after " \
"auto-layout completes, you may find file systems in the layout " \
"that you did not select from the list below.")

/*
 * i18n: "Automatically Layout File Systems?" screen
 */
#define	TITLE_AUTOLAYOUTQRY	LIBAPPSTR(\
"Automatically Layout File Systems?")

#define	MSG_AUTOLAYOUTQRY	LIBAPPSTR(\
"Do you want to use auto-layout to automatically layout " \
"file systems? Manually laying out file systems requires advanced system " \
"administration skills.")

/*
 * i18n: "Repeat Auto-layout?" screen
 */
#define	TITLE_REDO_AUTOLAYOUT	LIBAPPSTR("Repeat Auto-layout?")

#define	MSG_REDO_AUTOLAYOUT	LIBAPPSTR(\
"Do you want to repeat the auto-layout of your file systems? " \
"Repeating the auto-layout will destroy the current layout of file " \
"systems, except those marked as preserved.")

/*
 * i18n: "Create Solaris fdisk Partition" screen
 */
#define	TITLE_CREATESOLARIS	LIBAPPSTR("Create Solaris fdisk Partition")

#define	MSG_CREATESOLARIS	LIBAPPSTR(\
"There is no Solaris fdisk partition on this disk. " \
"You must create a Solaris fdisk partition if you want to use this " \
"disk to install Solaris software.\n\n" \
"One or more of the following methods are available: " \
"have the software install a boot partition and a Solaris partition " \
"that will fill the entire fdisk, install just a Solaris partition " \
"that will fill the entire fdisk (both of these options will " \
"overwrite any existing fdisk partitions), install a Solaris partition " \
"on the remainder of the disk, install a boot partition on the disk, or " \
"manually lay out the Solaris fdisk partition.")

#define	MSG_CREATESOLARIS_W_DIAG_PRESERVE	LIBAPPSTR(\
"There is no Solaris fdisk partition on this disk. " \
"You must create a Solaris fdisk partition if you want to use this " \
"disk to install Solaris software.\n\n" \
"A Service fdisk partition has been detected.  Choose a method from the " \
"following list to create a Solaris fdisk partition.\n\n" \
"Note: if you choose to save the service partition, the installation " \
"program preserves all service partitions and overwrites all other existing " \
"fdisk partitions.")

/*
 * i18n: "Customize fdisk Partitions" screen
 */
#define	TITLE_CUSTOMSOLARIS	LIBAPPSTR("Customize fdisk Partitions")

#define	MSG_CUSTOMSOLARIS	LIBAPPSTR(\
"On this screen you can create, delete, and customize fdisk partitions. " \
"The Free field is updated as you assign sizes to fdisk partitions " \
"1 through 4.")

/*
 * i18n: Exit screen
 */
#define	TITLE_EXIT	LIBAPPSTR("Exit")

#define	MSG_EXIT	LIBAPPSTR(\
"If you exit the Solaris Interactive Installation program, " \
"your profile is deleted. " \
"However, you can restart the Solaris Interactive Installation program " \
"from the console window.")

/*
 * i18n: "Customize Existing Software?" (upgrade) screen
 */
#define	TITLE_UPG_CUSTOM_SWQUERY	LIBAPPSTR("Customize Software?")

#define	MSG_UPG_CUSTOM_SWQUERY		LIBAPPSTR(\
"Do you want to customize (add or delete) software "\
"for the upgrade? By default, the existing software on "\
"the system will be upgraded.")

#define	MSG_64_UPG_CUSTOM_SWQUERY	LIBAPPSTR(\
"Do you want to customize (add or delete) software "\
"for the upgrade? By default, the existing software on "\
"the system will be upgraded. If the Select 64-bit choice is " \
"unselectable then 64-bit is currently installed and cannot be " \
"removed without customizing.")

/*
 * i18n: "Solaris Version to Upgrade"  (upgrade) screen
 */
#define	TITLE_OS_MULTIPLE	LIBAPPSTR(\
"Select Version to Upgrade")

#define	MSG_OS	LIBAPPSTR(\
"More than one version of Solaris has been found on the system. "\
"Select the version of Solaris to upgrade from.")

#define	OS_SOLARIS_PREFIX	LIBAPPSTR("Solaris")
#define	OS_VERSION_LABEL	LIBAPPSTR("Solaris Version")

/*
 * i18n: "Analyzing System" (upgrade) screen
 */
#define	TITLE_SW_ANALYZE	LIBAPPSTR("Analyzing System")

#define	MSG_SW_ANALYZE	LIBAPPSTR(\
"The Solaris software on the system is being analyzed for "\
"the upgrade.")

#define	LABEL_SW_ANALYZE	LIBAPPSTR("Analyzing System...")
#define	LABEL_SW_ANALYZE_COMPLETE	LIBAPPSTR(\
"Analysis Complete")

/*
 * i18n: the labels for the various phases of software space checking
 * Where appropriate, the software will add on a ": pkgname" tag to the
 * end.
 * In the GUI overall length (including the ": pkgname" add on
 * must fit within the
 * Installtool*dsr_analyze_dialog*panelhelpText*columns: value.
 * In the CUI it must be < 60 chars.
 */
#define	LABEL_UPG_VAL_FIND_MODIFIED	LIBAPPSTR(\
"Checking modified files")
#define	LABEL_UPG_VAL_CURPKG_SPACE	LIBAPPSTR(\
"Calculating database size for packages on system")
#define	LABEL_UPG_VAL_CURPATCH_SPACE	LIBAPPSTR(\
"Calculating database size for patches on system")
#define	LABEL_UPG_VAL_SPOOLPKG_SPACE	LIBAPPSTR(\
"Calculating database size for spooled packages on system")
#define	LABEL_UPG_VAL_CONTENTS_SPACE	LIBAPPSTR(\
"Calculating size of packages on system")
#define	LABEL_UPG_VAL_NEWPKG_SPACE	LIBAPPSTR(\
"Calculating size of new packages")
#define	LABEL_UPG_VAL_EXEC_LOCAL_PKGADD	LIBAPPSTR(\
"Adding package")
#define	LABEL_UPG_VAL_EXEC_VIRTUAL_PKGADD	LIBAPPSTR(\
"Logging virtual package")
#define	LABEL_UPG_VAL_EXEC_PKGRM	LIBAPPSTR(\
"Removing package")
#define	LABEL_UPG_VAL_EXEC_REMOVEF	LIBAPPSTR(\
"Removing obsolete files in package")
#define	LABEL_UPG_VAL_EXEC_LOCAL_SPOOL	LIBAPPSTR(\
"Adding spooled package")
#define	LABEL_UPG_VAL_EXEC_VIRTUAL_SPOOL	LIBAPPSTR(\
"Logging spool of virtual package")
#define	LABEL_UPG_VAL_EXEC_RMTEMPLATE	LIBAPPSTR(\
"Removing spooled package")
#define	LABEL_UPG_VAL_EXEC_RMDIR	LIBAPPSTR(\
"Removing directory")
#define	LABEL_UPG_VAL_EXEC_RMSVC	LIBAPPSTR(\
"Removing service")
#define	LABEL_UPG_VAL_EXEC_RMPATCH	LIBAPPSTR(\
"Removing patch")
#define	LABEL_UPG_VAL_EXEC_RMTEMPLATEDIR	LIBAPPSTR(\
"Removing template directory")

/*
 * i18n: "Change Auto-layout Constraints" (upgrade) screen
 *
 * This screen has column headings in English that look like:
 *
 *      File System      Slice      Free    Space    Constraints   Minimum
 *                                  Space   Needed                 Size
 * ----------------------------------------------------------------------
 * [X]  /               c0t0d0s0      86        0    Changeable  115
 * etc...
 *
 * The total width across the screen for all these
 * headings must be <= 67 chars in the CUI
 * (which includes 3 spaces between columns)
 */

#define	TITLE_DSR_FSREDIST	LIBAPPSTR(\
"Change Auto-layout Constraints")

/* %s is the additional CUI note (found in the CUI message file) */
#define	MSG_DSR_FSREDIST	LIBAPPSTR(\
"On this screen you can change the "\
"constraints on the file systems and repeat auto-layout "\
"until it can successfully reallocate space "\
"(file systems requiring more space are marked with an '*'). "\
"%s " \
"All size and space values are in Mbytes."\
"\n\n"\
"TIP: To help auto-layout reallocate space, change "\
"more file systems from the Constraints menus to be "\
"changeable or movable, especially those that reside on the same "\
"disks as the file systems that need more space.")

/*
 * i18n:
 * Used throughout the DSR upgrade screens.
 * 12 chars max
 * File system name tag when the last mounted on field for a file system
 * cannot be found or the slice has no file system name.
 */
#define	APP_FS_UNNAMED	"<       >"

/* i18n: "Change Auto-layout Constraints" error/warning messages */
#define	TITLE_APP_ER_DSR_MSG_FINAL_TOO_SMALL	LIBAPPSTR(\
"Invalid Minimum Size")

#define	APP_ER_DSR_MSG_FINAL_TOO_SMALL	LIBAPPSTR(\
"The minimum sizes for the following slices are invalid. "\
"The minimum size must be "\
"equal to or greater than the required size for that slice:")

/*
 * i18n:
 * 1st %s: prepended message consisting of above message +
 *	any number of this current message.
 * 2nd %s: file system name (e.g. /usr)
 * 3rd %s: slice specifier (e.g. c0t0d0s0)
 * 4th %s: required slice size in string format
 * 5th %s: minimum slice size as entered by user.
 */
#define	APP_ER_DSR_ITEM_FINAL_TOO_SMALL	LIBAPPSTR(\
"%s\n\n"\
"File system: %s\n"\
"    Slice: %s\n"\
"    Required Size: %s MB\n"\
"    Minimum Size Entered: %s MB")

#define	APP_ER_DSR_AVAILABLE_LOSE_DATA		LIBAPPSTR(\
"Auto-layout will use all the space on the following "\
"file systems to reallocate space (these are the file systems "\
"that you marked as Available). All the data in the "\
"file systems will be lost. "\
"\n\n")

/*
 * i18n:
 * 1st %s: prepended message consisting of above message +
 *	any number of this current message.
 * 2nd %s: file system name (e.g. /usr)
 * 3rd %s: slice specifier (e.g. c0t0d0s0)
 */
#define	APP_ER_DSR_AVAILABLE_LOSE_DATA_ITEM		LIBAPPSTR(\
"%sFile system: %*s    Slice: %s")

/*
 * i18n: "Change Auto-layout Constraints"
 * labels on top for currently 'active" slice
 */
#define	LABEL_DSR_FSREDIST_SLICE	LIBAPPSTR("Slice:")
#define	LABEL_DSR_FSREDIST_REQSIZE	LIBAPPSTR("Required Size:")
#define	LABEL_DSR_FSREDIST_CURRSIZE	LIBAPPSTR("Existing Size:")

/* i18n: "Change Auto-layout Constraints" column label headings */
#define	LABEL_DSR_FSREDIST_CURRFREESIZE	LIBAPPSTR("Free\nSpace")
#define	LABEL_DSR_FSREDIST_SPACE_NEEDED	LIBAPPSTR("Space\nNeeded")
#define	LABEL_DSR_FSREDIST_OPTIONS	LIBAPPSTR("Constraints")
#define	LABEL_DSR_FSREDIST_FINALSIZE	LIBAPPSTR("Minimum\nSize")

#define	LABEL_DSR_FSREDIST_ADDITIONAL_SPACE	LIBAPPSTR(\
"Total Space Needed:")
#define	LABEL_DSR_FSREDIST_ALLOCATED_SPACE	LIBAPPSTR(\
"Total Space Allocated:")

#define	LABEL_DSR_FSREDIST_LEGENDTAG_FAILED	LIBAPPSTR("*")
#define	LABEL_DSR_FSREDIST_LEGEND_FAILED	LIBAPPSTR("Failed File System")

#define	LABEL_DSR_FSREDIST_COLLAPSE	LIBAPPSTR("Collapse...")
#define	LABEL_DSR_FSREDIST_FILTER	LIBAPPSTR("Filter...")

/*
 * i18n: "Change Auto-layout Constraints"
 * Unlike most message boxes, the buttons in this message box are
 * not all the same size because the Repeat Auto-layout button is so
 * long that it forces all buttons to be to big and forces the overall
 * width of the whole screen to be huge.
 * So, put space around the buttons to make them a reasonable size.
 */
#define	LABEL_DSR_FSREDIST_GOBACK_BUTTON	LIBAPPSTR(" Go Back ")
#define	LABEL_DSR_FSREDIST_RESET_BUTTON		LIBAPPSTR(" Defaults ")
#define	LABEL_DSR_FSREDIST_EXIT_BUTTON		LIBAPPSTR("   Exit   ")
#define	LABEL_DSR_FSREDIST_HELP_BUTTON		LIBAPPSTR("   Help   ")

/*
 * i18n: "Change Auto-layout Constraints"
 * labels in Contraints option menu
 */
#define	LABEL_DSR_FSREDIST_FIXED	LIBAPPSTR("Fixed")
#define	LABEL_DSR_FSREDIST_MOVE		LIBAPPSTR("Movable")
#define	LABEL_DSR_FSREDIST_CHANGE	LIBAPPSTR("Changeable")
#define	LABEL_DSR_FSREDIST_AVAILABLE	LIBAPPSTR("Available")
#define	LABEL_DSR_FSREDIST_COLLAPSED	LIBAPPSTR("Collapsed")

#define	MSG_FSREDIST_GOBACK_LOSE_EDITS	LIBAPPSTR(\
"If you go back, all the selections you've made "\
"in the Auto-layout Constraints screen will be lost.")

/* i18n: "Change Auto-layout Constraints": Filter File Systems screen */
#define	TITLE_DSR_FILTER	LIBAPPSTR("Filter File Systems")

/* i18n: GUI Filter text */
#define	MSG_GUI_DSR_FILTER		LIBAPPSTR(\
"Select which file systems to display on the Auto-layout "\
"Constraints screen. If you select \"%s\" or \"%s\", "\
"you must also specify a search string. You can "\
"use wildcards (* and ?) in the search string to display "\
"groups of slices or file systems.")

/* i18n: CUI Filter text */
#define	MSG_CUI_DSR_FILTER		LIBAPPSTR(\
"Select which file systems to display on the Auto-layout "\
"Constraints screen.")

/* i18n: filter radio button choices */
#define	LABEL_DSR_FSREDIST_FILTER_RADIO	LIBAPPSTR(\
"Filter:")
#define	LABEL_DSR_FSREDIST_FILTER_ALL	LIBAPPSTR(\
"All")
#define	LABEL_DSR_FSREDIST_FILTER_FAILED	LIBAPPSTR(\
"Failed File Systems")
#define	LABEL_DSR_FSREDIST_FILTER_VFSTAB	LIBAPPSTR(\
"Mounted by vfstab")
#define	LABEL_DSR_FSREDIST_FILTER_NONVFSTAB	LIBAPPSTR(\
"Not mounted by vfstab")
#define	LABEL_DSR_FSREDIST_FILTER_SLICE	LIBAPPSTR(\
"By slice name")
#define	LABEL_DSR_FSREDIST_FILTER_MNTPNT	LIBAPPSTR(\
"By file system name")

#define	LABEL_DSR_FSREDIST_FILTER_RETEXT	LIBAPPSTR(\
"Search %s:")
#define	LABEL_DSR_FSREDIST_FILTER_RE_EG	LIBAPPSTR(\
"(For example, c0t3 or /export.*)")

/* i18n: "Change Auto-layout Constraints": Collapse File Systems screen */
#define	TITLE_DSR_FS_COLLAPSE	LIBAPPSTR(\
"Collapse File Systems")

#define	MSG_DSR_FS_COLLAPSE	LIBAPPSTR(\
"The file systems selected below will remain on the system "\
"after the upgrade. To reduce the number of file systems, "\
"deselect one or more file systems from the list. The data in a "\
"deselected file system will be moved (collapsed) into its "\
"parent file system.")

#define	LABEL_DSR_FS_COLLAPSE_FS	LIBAPPSTR(\
"File System")

#define	LABEL_DSR_FS_COLLAPSE_PARENT	LIBAPPSTR(\
"Parent File System")

#define	LABEL_DSR_FS_COLLAPSE_CHANGED	LIBAPPSTR(\
"If you change the number of file systems, "\
"the system will be reanalyzed and the "\
"changes you've made in the Auto-layout "\
"Constraints screen will be lost.")

#define	APP_DSR_COLLAPSE_SPACE_OK	LIBAPPSTR(\
"After changing the number of file systems, the "\
"system now has enough space for the upgrade. Choose "\
"Repeat Auto-layout in the Auto-layout Constraints screen "\
"to continue with the upgrade.")

/*
 * i18n: "Change Auto-layout Constraints"
 * for tagging fields that are not applicable in
 *
 */
#define	LABEL_DSR_FSREDIST_NA	LIBAPPSTR("-----")

/*
 * i18n: Summary screen strings
 */
#define	LABEL_SOFTWARE		LIBAPPSTR("Software")

/*
 * i18n: "File System Modification Summary" screen
 *
 * This screen has column headings in English that look like:
 *
 * File System      Slice     Size    Modification   Existing   Existing
 *                            (MB)                   Slice      Size (MB)
 *
 * The total width across the screen for all these
 * headings must be <= 76 chars in the CUI
 * (which includes 3 spaces between columns)
 */
#define	TITLE_DSR_FSSUMMARY	LIBAPPSTR("File System Modification Summary")

#define	MSG_DSR_FSSUMMARY	LIBAPPSTR(\
"Auto-layout has determined how to reallocate space on "\
"the file systems. The list below shows what modifications "\
"will be made to the file systems and what the final "\
"file system layout will be after the upgrade. "\
"\n\n"\
"To change the constraints on the file system that auto-layout "\
"uses to reallocate space, choose Change.")

#define	LABEL_DSR_FSSUMM_NEWSLICE	LIBAPPSTR("Slice")
#define	LABEL_DSR_FSSUMM_NEWSIZE	LIBAPPSTR("Size\n(MB)")
#define	LABEL_DSR_FSSUMM_ORIGSLICE	LIBAPPSTR("Existing\nSlice")
#define	LABEL_DSR_FSSUMM_ORIGSIZE	LIBAPPSTR("Existing\nSize (MB)")
#define	LABEL_DSR_FSSUMM_WHAT_HAPPENED	LIBAPPSTR("Modification")

/* i18n: possible values for the "Modification" column */
#define	LABEL_DSR_FSSUMM_NOCHANGE	LIBAPPSTR(\
"None")
#define	LABEL_DSR_FSSUMM_CHANGED	LIBAPPSTR(\
"Changed")
#define	LABEL_DSR_FSSUMM_DELETED	LIBAPPSTR(\
"Deleted")
#define	LABEL_DSR_FSSUMM_CREATED	LIBAPPSTR(\
"Created")
#define	LABEL_DSR_FSSUMM_UNUSED	LIBAPPSTR(\
"Unused")
#define	LABEL_DSR_FSSUMM_COLLAPSED	LIBAPPSTR(\
"Collapsed")

/*
 * i18n: "Select Media for Backup" (upgrade) screen
 */
#define	TITLE_DSR_MEDIA	LIBAPPSTR("Select Media for Backup")

#define	MSG_DSR_MEDIA	LIBAPPSTR(\
"Select the media that will be used to "\
"temporarily back up the file systems "\
"that auto-layout will modify."\
"\n\n"\
"Space required for backup: %*d MB")

/* i18n: %s is one of "diskettes" or "tapes" below */
#define	MSG_DSR_MEDIA_MULTIPLE	LIBAPPSTR(\
"NOTE: If multiple %s are required for the backup, "\
"you'll be prompted to insert %s during the upgrade.")

#define	LABEL_DSR_MEDIA_MFLOPPY	LIBAPPSTR("diskettes")
#define	LABEL_DSR_MEDIA_MTAPES	LIBAPPSTR("tapes")

#define	LABEL_DSR_MEDIA_FLOPPY	LIBAPPSTR("diskette")
#define	LABEL_DSR_MEDIA_TAPE	LIBAPPSTR("tape")

#define	LABEL_DSR_MEDIA_MEDIA	LIBAPPSTR("Media:")
#define	LABEL_DSR_MEDIA_PATH	LIBAPPSTR("Path:")

#define	TEXT_DSR_MEDIA_ORIG_FLOPPY	LIBAPPSTR("/dev/rdiskette")
#define	TEXT_DSR_MEDIA_ORIG_TAPE	LIBAPPSTR("/dev/rmt/0")

/*
 * i18n: only the "For example" and perhaps the /export/temp
 * should need translating here...
 */
#define	LABEL_DSR_MEDIA_DEV_LFLOPPY	LIBAPPSTR(\
"(For example, /dev/rdiskette)")
#define	LABEL_DSR_MEDIA_DEV_LTAPE	LIBAPPSTR(\
"(For example, /dev/rmt/0)")
#define	LABEL_DSR_MEDIA_DEV_LDISK	LIBAPPSTR(\
"(For example, /export/temp or /dev/dsk/c0t0d0s1)")
#define	LABEL_DSR_MEDIA_DEV_NFS	LIBAPPSTR(\
"(For example, host:/export/temp)")
#define	LABEL_DSR_MEDIA_DEV_RSH	LIBAPPSTR(\
"(For example, user@host:/export/temp)")

/* i18n: the possible media types */
#define	LABEL_DSR_MEDIA_OPT_LFLOPPY	LIBAPPSTR("Local diskette")
#define	LABEL_DSR_MEDIA_OPT_LTAPE	LIBAPPSTR("Local tape")
#define	LABEL_DSR_MEDIA_OPT_LDISK	LIBAPPSTR("Local file system")
#define	LABEL_DSR_MEDIA_OPT_NFS	LIBAPPSTR("Remote file system (NFS)")
#define	LABEL_DSR_MEDIA_OPT_RSH	LIBAPPSTR("Remote system (rsh)")

/* i18n: dialog title */
#define	TITLE_DSR_MEDIA_INSERT	LIBAPPSTR("Insert Media")

#define	MSG_DSR_MEDIA_INSERT_FIRST	LIBAPPSTR(\
"Please insert the first %s "\
"so the installation program can validate it."\
"%s")

#define	MSG_DSR_MEDIA_INSERT_TAPE_NOTE	LIBAPPSTR(\
"\n\n" \
"NOTE: Make sure the %s is not write protected.")

#define	MSG_DSR_MEDIA_INSERT_FLOPPY_NOTE	LIBAPPSTR(\
"\n\n" \
"NOTE: Make sure the %s is formatted and that it is not write protected. "\
"You can use the fdformat command to format diskettes.")

/*
 * i18n: 2nd %s is in order to tack on the "make sure it's not write
 * protected note, if necessary.
 */
#define	MSG_DSR_MEDIA_ANOTHER	LIBAPPSTR(\
"Please insert %s number %d."\
"%s")

/*
 *  i18n: "Generating Backup List" (upgrade) screen
 */
#define	TITLE_DSR_ALGEN	LIBAPPSTR("Generating Backup List")

#define	MSG_DSR_ALGEN	LIBAPPSTR(\
"A list is being generated of all the file systems that "\
"auto-layout needs to modify. The file systems in the list "\
"will be temporarily backed up during the upgrade.")

#define	LABEL_DSR_ALGEN_COMPLETE	LIBAPPSTR(\
"Generation complete")

#define	LABEL_DSR_ALGEN_FAIL	LIBAPPSTR(\
"(failure)")

#define	LABEL_DSR_ALGEN_FS	LIBAPPSTR(\
"Searching file system:")

/*
 * i18n: Upgrade Progress - Archive backup/restore/newfs/upgrade
 */
#define	LABEL_DSR_ALBACKUP_PROGRESS	LIBAPPSTR(\
"Backing up:")
#define	LABEL_DSR_ALBACKUP_COMPLETE	LIBAPPSTR(\
"Backup complete")

#define	LABEL_DSR_ALRESTORE_PROGRESS	LIBAPPSTR(\
"Restoring:")
#define	LABEL_DSR_ALRESTORE_COMPLETE	LIBAPPSTR(\
"Restore complete")

#define	LABEL_UPGRADE_PROGRESS_COMPLETE	LIBAPPSTR(\
"Upgrade complete")

/*
 * i18n: "More Space Needed" (upgrade) screen
 */
#define	TITLE_DSR_SPACE_REQ	LIBAPPSTR("More Space Needed")

#define	MSG_DSR_SPACE_REQ	LIBAPPSTR(\
"The system's file systems do not have enough space for the upgrade. "\
"The file systems that need more space are listed "\
"below. "\
"You can either go back and delete software that "\
"installs into the file systems listed, "\
"or you can let auto-layout reallocate space on the file "\
"systems. "\
"\n\n" \
"If you choose auto-layout, it will reallocate space on the "\
"file systems by:\n" \
"\t- Backing up file systems that it needs to change\n"\
"\t- Repartitioning the disks based on the file system changes\n"\
"\t- Restoring the file systems that were backed up\n\n"\
"You'll be able to confirm any file system changes "\
"before auto-layout reallocates space.")

#define	LABEL_DSR_SPACE_REQ_CURRSIZE	LIBAPPSTR("Existing\nSize (MB)")
#define	LABEL_DSR_SPACE_REQ_REQSIZE	LIBAPPSTR("Required\nSize (MB)")

/*
 * i18n: "More Space Needed" (upgrade) screen
 * (2nd dialog - not on main aprade path, but off of collapse file
 * systems screen.
 */
#define	MSG_DSR_SPACE_REQ_FS_COLLAPSE	LIBAPPSTR(\
"Because of the changes you've made on the Collapse File "\
"Systems screen, the following file systems do not have "\
"enough space for the upgrade.")

#define	MSG_SVM_FOUND_NO_DSR	LIBAPPSTR(\
	"The selected Software exceeds the available disk space.\n\n" \
	"The Solaris operating system selected to upgrade contains\n"\
	"a metadevice. Disk Space Re-allocation is not allowed.\n\n" \
	"Please do one of the following:\n\n" \
	"> Deselect some software to be installed.\n"\
	"> Choose another version of Solaris to upgrade. (If available)\n"\
	"> Go back and select Initial Install.\n" \
	"> Exit the installation.")

/*
 * Error/Warning messages
 */

/*
 * i18n: "Select Versionto Upgrade" errors
 */
#define	APP_ER_NOUPDSK	LIBAPPSTR("You must select a Solaris OS to upgrade.")

/*
 * i18n:
 * 1st %s is solaris release string (i.e. Solaris 2.5.1)
 * 2nd %s is slice name (i.e. c0t0d0s0)
 * 3rd %s is an additional error message from those below...
 * The intent is to end up with a message that looks like:
 * The Solaris Version (Solaris 2.5.1) on slice c0t0d0s0
 * cannot be upgraded.
 *
 * A file system listed in the file system table (vfstab)
 * could not be mounted.
 */
#define	APP_ER_SLICE_CANT_UPGRADE	LIBAPPSTR(\
"The Solaris Version (%s) on slice %s cannot be upgraded." \
"\n\n" \
"%s")

#define	APP_MSG_VFSTAB_OPEN_FAILED	LIBAPPSTR(\
"The file system table (vfstab) could not be opened.")

#define	APP_MSG_MOUNT_FAILED	LIBAPPSTR(\
"A file system listed in the file system table (vfstab) " \
"could not be mounted.")

#define	APP_MSG_UMOUNT_FAILED	LIBAPPSTR(\
"A file system listed in the file system table (vfstab) "\
"could not be unmounted.")

#define	APP_MSG_ZONE_MOUNT_FAILED	LIBAPPSTR(\
"A non-global zone could not be mounted.")

#define	APP_MSG_FSCK_FAILED	LIBAPPSTR(\
"A file system listed in the file system table (vfstab) " \
"could not be checked by fsck.")

#define	APP_MSG_ZONE_FAILED	LIBAPPSTR(\
"This slice can't be upgraded because of missing usr packages " \
"for the following zones:\n\n")

#define	APP_MSG_ADD_SWAP_FAILED	LIBAPPSTR(\
"Swap could not be added to the system.")

#define	APP_MSG_DELETE_SWAP_FAILED	LIBAPPSTR(\
"Swap could not be removed from the system.")

#define	APP_MSG_LOAD_INSTALLED	LIBAPPSTR(\
"There is an unknown problem with the software " \
"configuration installed on this disk.")

#define	APP_ER_FORCE_INSTALL	LIBAPPSTR(\
"There are no other upgradeable versions "\
"of Solaris on this system. You can choose "\
"to do an initial installation, or you can "\
"exit and fix any errors that are preventing "\
"you from upgrading. "\
"\n\n"\
"WARNING: If you choose Initial, you'll be "\
"presented with screens to do an initial "\
"installation, which will overwrite your file "\
"systems with the new version of Solaris. "\
"Backing up any modifications that you've "\
"made to the previous version of Solaris "\
"is recommended before starting the initial "\
"option. The initial option also lets you "\
"preserve existing file systems.")

/*
 * i18n: generic error message:
 * this one should have hard-coded newlines since it may just be printf'd
 */
#define	APP_ER_UNMOUNT	LIBAPPSTR(\
"Please reboot the system.\n" \
"There are inconsistencies in the current state of \n" \
"the system which only a system reboot can solve.")

/*
 * Disk checking errors
 */

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	APP_ER_NOKNOWNDISKS	LIBAPPSTR(\
"No disks found.\n\n"\
" > Check to make sure disks are cabled and\n"\
"   powered up.")

/*
 * i18n: disk error
 */
#define	DISK_ERROR_NO_INFO	LIBAPPSTR(\
	"There is no detailed information available about the disk drive or "\
	"its current state.")

/*
 * i18n: disk error
 */
#define	DISK_PREP_BAD_CONTROLLER	LIBAPPSTR(\
	"It appears that this disk drive is not responding to requests or "\
	"commands from the disk controller it is attached to.  As a result, "\
	"no information about this drive is available to the controller and "\
	"it cannot be probed, formatted or used.")

/*
 * i18n: disk error
 */
#define	DISK_PREP_UNKNOWN_CONTROLLER	LIBAPPSTR(\
	"It appears that this disk drive is attached to a disk controller "\
	"which is not recognized by the device driver software.  As a result, "\
	"no information about this controller is available to the driver and "\
	"none of the attached devices may be probed, formatted or used.")

/*
 * i18n: disk error
 */
#define	DISK_PREP_CANT_FORMAT	LIBAPPSTR(\
	"This drive has no label.  Solaris Install tried to provide a default "\
	"label using the `format' program but failed.  Since the drive cannot "\
	"be labeled, any changes to the partitioning cannot be saved.  As a "\
	"result, this drive may not be used by Solaris software.")

/*
 * i18n: disk error
 */
#define	DISK_PREP_NOPGEOM	LIBAPPSTR(\
	"This disk drive does not have a valid label.  If you want to use "\
	"this disk for the install, exit the Solaris Interactive Installation "\
	"program, use the format(1M) command from the command line to label "\
	"the disk, and type 'install-solaris' to restart the installation "\
	"program.")

/*
 * i18n: disk error
 */
#define	DISK_PREP_CREATE_PART_ERR_TITLE1	LIBAPPSTR(\
	"fdisk Partition In Use")

/*
 * i18n: disk error
 */
#define	DISK_PREP_CREATE_PART_ERR1	LIBAPPSTR(\
	"This fdisk partition is currently being used.\n\n"\
	"You must delete the existing partition before you can create "\
	"a new one.")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_CREATE_PART_ERR_TITLE	LIBAPPSTR(\
	"No Space Available")

/*
 * i18n: disk error
 */
#define	DISK_PREP_CREATE_PART_ERR	LIBAPPSTR(\
	"All space on this disk is currently assigned to existing fdisk "\
	"partitions. You cannot create a new partition until you delete "\
	"an existing one.")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_DISK_HOSED	LIBAPPSTR(\
	"This disk (%s) cannot be used to install Solaris software.\n\n%s\n\n")

/*
 * i18n: disk error
 */
#define	DISK_PREP_NO_FDISK_LABEL_TITLE	LIBAPPSTR(\
	"Disk Not Formatted")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_NO_FDISK_LABEL	LIBAPPSTR(\
	"This disk drive is not formatted.  Unformatted disks cannot be used "\
	"to install Solaris software.\n\n"\
	"CAUTION: The Solaris Interactive Installation program will format "\
	"this disk now, but existing data will be overwritten. If this disk "\
	"has data on it that you want to preserve, exit the Solaris "\
	"Interactive Installation program and back up the data.")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_NO_SOLARIS_PART_TITLE	LIBAPPSTR(\
	"No Solaris fdisk Partition")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_NO_SOLARIS_PART	LIBAPPSTR(\
	"There is no Solaris fdisk partition on this disk. "\
	"You must create a Solaris fdisk partition if you want to use it to "\
	"install Solaris software.")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_NO_FREE_FDISK_PART_TITLE	LIBAPPSTR(\
	"No Free Partition")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_NO_FREE_FDISK_PART	LIBAPPSTR(\
	"All available fdisk partitions on this disk are in use.  "\
	"Therefore, an fdisk partition cannot be created for "\
	"Solaris software.\n\n"\
	"You must manually create a Solaris fdisk partition, or not use "\
	"this disk.")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_CANNOT_DELETE_X86BOOT_PART	LIBAPPSTR(\
	"Cannot delete x86boot fdisk partition because default swap in use. ")
/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	DISK_PREP_CANNOT_DELETE_SOLARIS_PART	LIBAPPSTR(\
	"Cannot delete Solaris fdisk partition because default swap in use. ")

/*
 * i18n: resource error - requires newline formatting since it's just printf'd
 */
#define	APP_ER_NOKNOWNRESOURCES	LIBAPPSTR(\
"No default resources found.\n\n")

/*
 * i18n: disk error - requires newline formatting since it's just printf'd
 */
#define	APP_ER_NOUSABLEDISKS	LIBAPPSTR(\
"One or more disks are found, but one of the\n"\
"following problems exists:\n\n"\
" > Hardware failure\n\n"\
" > Unformatted disk.")

/*
 * i18n: DSR upgrade warnings
 */
#define	TITLE_APP_ER_CANT_AUTO_LAYOUT	LIBAPPSTR(\
"Auto-layout Unsuccessful")

#define	APP_ER_DSR_CANT_AUTO	LIBAPPSTR(\
"Auto-layout could not determine how to reallocate space on "\
"the file systems. On the next screen, change the "\
"constraints on the file systems to help auto-layout reallocate space.")

#define	APP_ER_DSR_AUTOLAYOUT_FAILED	LIBAPPSTR(\
"Auto-layout could not determine how to reallocate "\
"space on the file systems "\
"with the constraints you specified. "\
"Try other constraints.")

#define	APP_ER_DSR_RE_COMPFAIL	LIBAPPSTR(\
"Invalid regular expression `%s`.")

#define	APP_ER_DSR_RE_MISSING	LIBAPPSTR(\
"Please enter a regular expression to filter by.")

#define	APP_ER_DSR_FILTER_NOMATCH	LIBAPPSTR(\
"There are no file systems that match this filter criteria.")

#define	APP_ER_DSR_MEDIA_NODEVICE	LIBAPPSTR(\
"Please enter a media device path.")

/*
 * i18n: DSR Archive list media validation error strings
 */
#define	APP_ER_DSR_MEDIA_SUMM	LIBAPPSTR(\
"%s\n\n" \
"Current Media Selection:\n"\
"\tMedia: %s\n" \
"\tPath: %s\n")

#define	APP_ER_DSR_NOT_ENOUGH_SWAP	LIBAPPSTR(\
"The total amount of swap that you have allocated does not "\
"meet the minimum system requirements." \
"\n\n"\
"    Total Required Swap Size: %*lu MB\n"\
"    Total Swap Size Entered: %*lu MB")

#define	APP_DISKERR_SLICENOSPACE	LIBAPPSTR(\
"Slice %d does not have enough free space for the " \
"%d %s you specified.  " \
"You can either specify a smaller size for the slice " \
"or reduce the size of another slice to free up more space.\n\n" \
"NOTE:  If there are preserved slices surrounding slice %d, " \
"you must unpreserve one of the surrounding slices to free " \
"up more space for slice %d.")

#define	APP_DISKERR_PARTNOSPACE	LIBAPPSTR(\
"Partition %d does not have enough free space for the " \
"%d MB you specified.  " \
"You can either specify a smaller size for the partition or " \
"delete other partitions to free up more space.\n\n" \
"NOTE:  If there are fdisk partitions surrounding partition %d, " \
"you must delete one of the surrounding partitions to free up " \
"more space for partition %d.")

#define	APP_DISKERR_PARTMINSPACE LIBAPPSTR(\
"%s partitions must be at least %d MB in size.  There is not enough " \
"space in this location for a partition of this type.  " \
"You can delete other partitions to free up more space.\n\n" \
"NOTE:  If there are partitions surrounding this partition, " \
"you must delete one or more of them to free up more space for " \
"this partition.")

#define	APP_DISKERR_GENERIC_NOSPACE	LIBAPPSTR(\
"The size you entered exceeds the amount of free space " \
"available.  You can either specify a smaller size or " \
"free up more space on the disk.")

#define	TITLE_DISKERR_SECOND_STUB		LIBAPPSTR(\
"Add another x86boot partition?")

#define	APP_DISKERR_SECOND_STUB		LIBAPPSTR(\
"Do you really want to create an x86boot partition on %s?  " \
"You have already selected the x86boot partition on %s as " \
"the boot partition.  If you create one now on %s, the " \
"x86boot partition on %s will not be used, and should be " \
"deleted.  In addition, the disk containing the new x86boot " \
"partition will become the boot disk.")

#ifdef __cplusplus
}
#endif

#endif	/* _SPMIAPP_STRINGS_H */
