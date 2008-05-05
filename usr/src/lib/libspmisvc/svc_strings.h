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



#ifndef _SVC_STRINGS_H
#define	_SVC_STRINGS_H


/*
 * Module:	spmisvc_strings.h
 * Group:	libspmisvc
 * Description:	This header contains strings used in libspmisvc
 *		library modules.
 */

#include <libintl.h>

#ifdef __cplusplus
extern "C" {
#endif

/* constants */

#ifndef	TEXT_DOMAIN
#define	TEXT_DOMAIN	"SUNW_INSTALL_LIBSVC"
#endif

#ifndef ILIBSTR
#define	ILIBSTR(x)	dgettext(TEXT_DOMAIN, x)
#endif

/* message strings */

#define	MSG0_TRACE_MOUNT_LIST		ILIBSTR(\
	"Mount List")
#define	MSG2_FILESYS_MOUNT_FAILED	ILIBSTR(\
	"Could not mount %s (%s)")
#define	UNKNOWN_STRING			ILIBSTR(\
	"unknown")
#define	FILE_STRING			ILIBSTR(\
	"file")

/*
 * svc_updateconfig.c messages
 */

#define	MSG_OPEN_FAILED			ILIBSTR(\
	"Could not open file (%s)")
#define	MSG0_HOST_ADDRESS		ILIBSTR(\
	"Network host addresses (/etc/hosts)")
#define	MSG0_REBOOT_MESSAGE		ILIBSTR(\
	"The system will not automatically reconfigure devices upon reboot."\
	" You must use 'boot -r' when booting the system.")
#define	MSG1_DIR_ACCESS_FAILED		ILIBSTR(\
	"Could not access directory (%s)")
#define	MSG1_FILE_ACCESS_FAILED		ILIBSTR(\
	"Could not access file (%s)")
#define	MSG0_BOOTRC_INSTALL		ILIBSTR(\
	"Installing boot startup script (/etc/bootrc)")
#define	MSG0_BOOTENV_INSTALL		ILIBSTR(\
	"Updating boot environment configuration file")
#define	VFSTAB_COMMENT_LINE1		ILIBSTR(\
	"# This file contains vfstab entries for file systems on disks which\n")
#define	VFSTAB_COMMENT_LINE2		ILIBSTR(\
	"# were not selected during installation. The system administrator\n")
#define	VFSTAB_COMMENT_LINE3		ILIBSTR(\
	"# should put the entries which are intended to be active in the\n")
#define	VFSTAB_COMMENT_LINE4		ILIBSTR(\
	"# /etc/vfstab file, and create corresponding mount points.\n")
#define	MSG0_BOOT_BLOCK_NOTEXIST	ILIBSTR(\
	"No boot block found")
#define	MSG0_PBOOT_NOTEXIST		ILIBSTR(\
	"No pboot file found")
#define	MSG0_INSTALLBOOT_FAILED		ILIBSTR(\
	"installboot(1M) failed")
#define	MSG0_DEVICES_CUSTOMIZE		ILIBSTR(\
	"Customizing system devices")
#define	MSG0_DEVICES_CLEAN		ILIBSTR(\
	"Cleaning devices")
#define	MSG0_DEVICES_LOGICAL		ILIBSTR(\
	"Logical devices (/dev)")
#define	MSG0_DEVICES_PHYSICAL		ILIBSTR(\
	"Physical devices (/devices)")
#define	MSG0_VFSTAB_UNSELECTED		ILIBSTR(\
	"Unselected disk mount points \
(/var/sadm/system/data/vfstab.unselected)")
#define	MSG0_VFSTAB_INSTALL_FAILED	ILIBSTR(\
	"Could not install new vfstab data")
#define	MSG1_FILE_ACCESS_FAILED		ILIBSTR(\
	"Could not access file (%s)")
#define	MSG1_DEVICE_ACCESS_FAILED	ILIBSTR(\
	"Could not access device (%s)")
#define	MSG1_TRANS_NO_MERGESCRIPT	ILIBSTR(\
	"Transfer list entry (%s) is type MERGE with no mergescript")
#define	MSG2_TRANS_MERGESCRIPT_FAILED	ILIBSTR(\
	"Transfer list entry (%s): mergescript failed (%s)")
#define	MSG1_TRANS_ATTRIB_FAILED	ILIBSTR(\
	"Could not set file attributes (%s)")
#define	MSG0_TRANS_SETUP_FAILED		ILIBSTR(\
	"Could not initialize transfer list")
#define	MSG0_TRANS_CORRUPT		ILIBSTR(\
	"Transfer list corrupted")
#define	MSG0_BOOT_INFO_INSTALL		ILIBSTR(\
	"Installing boot information")
#define	MSG0_BOOT_FIRMWARE_UPDATE	ILIBSTR(\
	"Updating system firmware for automatic rebooting")
#define	MSG1_BOOT_BLOCKS_INSTALL	ILIBSTR(\
	"Installing boot blocks (%s)")
#define	MSG0_ROOT_UNSELECTED		ILIBSTR(\
	"The / mount point is not on a selected disk")
#define	MSG1_DEV_INSTALL_FAILED		ILIBSTR(\
	"Could not install devices (%s)")
#define	MSG1_READLINK_FAILED		ILIBSTR(\
	"readlink() call failed (%s)")
#define	MSG0_INSTALL_LOG_LOCATION	ILIBSTR(\
	"Installation log location")
#define	MSG1_INSTALL_LOG_BEFORE		ILIBSTR(\
	"%s (before reboot)")
#define	MSG1_INSTALL_LOG_AFTER		ILIBSTR(\
	"%s (after reboot)")
#define	MSG0_CLEANUP_LOG_LOCATION	ILIBSTR(\
	"Please examine the file:")
#define	MSG0_CLEANUP_LOG_MESSAGE	ILIBSTR(\
	"It contains a list of actions that may need to be performed to "\
	"complete\nthe upgrade. After this system is rebooted, this file "\
	"can be found at:")
#define	MSG0_MOUNT_POINTS		ILIBSTR(\
	"Mount points table (/etc/vfstab)")
#define	MSG0_CANT_FIND_DEVICES		ILIBSTR(\
	"Could not open %s to clean devices")
#define	MSG0_CANT_CLEAN_DEVICES		ILIBSTR(\
	"Could not remove device directory (%s)")
#define	MSG0_CANT_REWRITE_PATH_TO_INST	ILIBSTR(\
	"Could not clean device configuration (%s)")
#define	MSG0_REMOVING			ILIBSTR(\
	"Removing %s")
#define	MSG0_ETC_DEFAULT_INIT		ILIBSTR(\
	"Environment variables (/etc/default/init)")

/*
 * svc_updatedisk.c strings
 */

#define	MSG0_DISK_LABEL_FAILED		ILIBSTR(\
	"Could not label disks")
#define	MSG0_DISK_NEWFS_FAILED		ILIBSTR(\
	"Could not check or create system critical file systems")
#define	MSG3_FDISK_PART_CREATE		ILIBSTR(\
	"Creating filesystem on fdisk partition %sp%d")
#define	MSG3_FDISK_PART_CREATE_FAILED	ILIBSTR(\
	"File system creation failed for fdisk partition %sp%d")
#define	MSG3_SLICE_CREATE		ILIBSTR(\
	"Creating %s (%ss%d)")
#define	MSG3_SLICE_CREATE_FAILED	ILIBSTR(\
	"File system creation failed for %s (%ss%d)")
#define	MSG3_SLICE_CHECK		ILIBSTR(\
	"Checking %s (%ss%d)")
#define	MSG3_SLICE_CHECK_FAILED		ILIBSTR(\
	"File system check failed for %s (%ss%d)")
#define	MSG0_PROCESS_FOREGROUND		ILIBSTR(\
	"Process running in foreground")
#define	MSG0_PROCESS_BACKGROUND		ILIBSTR(\
	"Process running in background")
#define	MSG0_SLICE2_ACCESS_FAILED	ILIBSTR(\
	"Could not access slice 2 to create Solaris disk label (VTOC)")
#define	MSG0_ALT_SECTOR_SLICE		ILIBSTR(\
	"Processing the alternate sector slice")
#define	MSG0_ALT_SECTOR_SLICE_FAILED	ILIBSTR(\
	"Could not process the alternate sector slice")
#define	MSG0_VTOC_CREATE		ILIBSTR(\
	"Creating Solaris disk label (VTOC)")
#define	MSG0_VTOC_CREATE_FAILED		ILIBSTR(\
	"Could not create Solaris disk label (VTOC)")
#define	MSG4_FDISK_ENTRY		ILIBSTR(\
	"type: %-3d  active:  %-3d  offset: %-6d  size: %-7d")
#define	MSG0_FDISK_OPEN_FAILED		ILIBSTR(\
	"Could not open Fdisk partition table input file")
#define	MSG1_FDISK_TABLE		ILIBSTR(\
	"Fdisk partition table for disk %s (input file for fdisk(1M))")
#define	MSG0_FDISK_CREATE		ILIBSTR(\
	"Creating Fdisk partition table")
#define	MSG0_FDISK_CREATE_FAILED	ILIBSTR(\
	"Could not create Fdisk partition table")
#define	MSG0_FDISK_INPUT_FAILED		ILIBSTR(\
	"Could not create Fdisk partition table input file")
#define	MSG0_CREATE_CHECK_UFS		ILIBSTR(\
	"Creating and checking UFS file systems")
#define	MSG0_VTOC_CREATE		ILIBSTR(\
	"Creating Solaris disk label (VTOC)")
#define	MSG0_DISK_FORMAT		ILIBSTR(\
	"Formatting disk")
#define	MSG1_DISK_FORMAT_FAILED		ILIBSTR(\
	"format(1M) failed (%s)")
#define	MSG1_DISK_SETUP			ILIBSTR(\
	"Configuring disk (%s)")
#define	MSG4_SLICE_VTOC_ENTRY		ILIBSTR(\
	"slice: %2d (%15s)  tag: 0x%-2x  flag: 0x%-2x")

/*
 * svc_updatesoft.c strings
 */

#define	MSG0_TRANS_SETUP_FAILED		ILIBSTR(\
	"Could not initialize transfer list")
#define	MSG0_TRANS_CORRUPT		ILIBSTR(\
	"Transfer list corrupted")
#define	MSG0_SOLARIS_INSTALL_BEGIN	ILIBSTR(\
	"Beginning Solaris software installation")
#define	MSG0_ADMIN_INSTALL_FAILED	ILIBSTR(\
	"Could not install administration information")
#define	MSG0_REFRESH_FAILED		ILIBSTR(\
	"Could not refresh legacy package database")
#define	MSG0_PKG_PREP_FAILED		ILIBSTR(\
	"Package installation preparation failed")
#define	MSG1_PKG_NONEXISTENT		ILIBSTR(\
	"Non-existent package in cluster (%s)")
#define	MSG0_PKG_INSTALL_INCOMPLETE	ILIBSTR(\
	"Package installation did not complete")
#define	MSG1_PKG_INSTALL_SUCCEEDED	ILIBSTR(\
	"%s software installation succeeded")
#define	MSG0_SOFTINFO_CREATE_FAILED	ILIBSTR(\
	"Could not create the product file")
#define	MSG0_RELEASE_CREATE_FAILED	ILIBSTR(\
	"Could not create the release file")
#define	MSG0_LOCINST_CREATE_FAILED	ILIBSTR(\
	"Could not create the installed locale file")
#define	MSG1_PKG_INSTALL_PARTFAIL	ILIBSTR(\
	"%s software installation partially failed")
#define	PKGS_FULLY_INSTALLED		ILIBSTR(\
	"%s packages fully installed")
#define	PKGS_PART_INSTALLED		ILIBSTR(\
	"%s packages partially installed")
#define	MSG2_LINK_FAILED		ILIBSTR(\
	"Could not link file (%s) to (%s)")
#define	MSG_OPEN_FAILED			ILIBSTR(\
	"Could not open file (%s)")
#define	MSG_READ_FAILED			ILIBSTR(\
	"Could not read file (%s)")
#define	MSG_READ_EOF			ILIBSTR(\
	"Unexpected EOF error while reading (%s)")
#define	MSG_WRITE_FAILED		ILIBSTR(\
	"Could not write to pipe while processing %s")
#define	NONE_STRING			ILIBSTR(\
	"none")
#define	MSG0_PKGADD_EXEC_FAILED		ILIBSTR(\
	"pkgadd exec failed")

/*
 * svc_updatesys.c strings
 */
#define	MSG0_SU_SUCCESS				ILIBSTR(\
	"SystemUpdate completed successfully")
#define	MSG0_SU_INVALID_OPERATION		ILIBSTR(\
	"Invalid requested operation supplied to SystemUpdate")
#define	MSG0_SU_MNTPNT_LIST_FAILED		ILIBSTR(\
	"Could not create a list of mount points")
#define	MSG0_SU_SETUP_DISKS_FAILED		ILIBSTR(\
	"Could not update disks with new configuration")
#define	MSG0_SU_STATE_RESET_FAILED		ILIBSTR(\
	"Could not reinitialize system state")
#define	MSG0_SU_MOUNT_FILESYS_FAILED		ILIBSTR(\
	"Could not mount the configured file system(s)")
#define	MSG0_SU_MOUNT_ZONES_FAILED		ILIBSTR(\
	"Could not mount zone(s)")
#define	MSG0_SU_PKG_INSTALL_TOTALFAIL		ILIBSTR(\
	"Could not install all packages. Product installation failed")
#define	MSG0_SU_ARCHIVE_EXTRACT_FAILED		ILIBSTR(\
	"Could not extract Flash archive")
#define	MSG0_SU_PREDEPLOYMENT_FAILED		ILIBSTR(\
	"Predeployment processing failure")
#define	MSG0_SU_POSTDEPLOYMENT_FAILED		ILIBSTR(\
	"Postdeployment processing failure")
#define	MSG0_SU_CLONE_VALIDATION_FAILED		ILIBSTR(\
	"Deployment validation failure")
#define	MSG0_SU_MASTER_VALIDATION_FAILED	ILIBSTR(\
	"Master validation failure")
#define	MSG0_SU_VFSTAB_CREATE_FAILED		ILIBSTR(\
	"Could not create the file system mount table (/etc/vfstab)")
#define	MSG0_SU_VFSTAB_UNSELECTED_FAILED	ILIBSTR(\
	"Could not create the unselected drive mount point file")
#define	MSG0_SU_HOST_CREATE_FAILED		ILIBSTR(\
	"Could not set up the remote host file (/etc/hosts)")
#define	MSG0_SU_SERIAL_VALIDATE_FAILED		ILIBSTR(\
	"Could not validate the system serial number")
#define	MSG0_SU_SYS_DEVICES_FAILED		ILIBSTR(\
	"Could not set up system devices")
#define	MSG0_SU_DEFAULT_INIT_UPDATE_FAILED	ILIBSTR(\
	"Could not update /etc/default/init file")
#define	MSG0_SU_SYS_RECONFIG_BOOT_FAILED	ILIBSTR(\
	"Could not force reconfiguration boot (/reconfigure)")
#define	MSG0_SU_CREATE_DIR_FAILED		ILIBSTR(\
	"Could not create a target directory")
#define	MSG0_SU_BOOT_BLOCK_FAILED		ILIBSTR(\
	"Could not install boot blocks")
#define	MSG0_SU_PROM_UPDATE_FAILED		ILIBSTR(\
	"Could not update system for automatic rebooting")
#define	MSG0_SU_UPGRADE_SCRIPT_FAILED		ILIBSTR(\
	"The upgrade script terminated abnormally")
#define	MSG0_SU_DISKLIST_READ_FAILED		ILIBSTR(\
	"Unable to read the disk list from file")
#define	MSG0_SU_DSRAL_CREATE_FAILED		ILIBSTR(\
	"Unable to create an instance of the backup list object.")
#define	MSG0_SU_DSRAL_ARCHIVE_BACKUP_FAILED	ILIBSTR(\
	"Unable to save the backup.")
#define	MSG0_SU_DSRAL_ARCHIVE_RESTORE_FAILED	ILIBSTR(\
	"Unable to restore the backup.")
#define	MSG0_SU_DSRAL_DESTROY_FAILED		ILIBSTR(\
	"Unable to destroy the instance of the backup list object.")
#define	MSG0_SU_UNMOUNT_FAILED			ILIBSTR(\
	"Unable to unmount mounted file systems")
#define	MSG0_SU_FATAL_ERROR			ILIBSTR(\
	"An unrecoverable internal error has occurred.")
#define	MSG0_SU_FILE_COPY_FAILED		ILIBSTR(\
	"Unable to copy a temporary file to it's final location")
#define	MSG0_SU_CLEAN_DEVICES_FAILED		ILIBSTR(\
	"Unable to clean devices")
#define	MSG0_SU_UNKNOWN_ERROR_CODE		ILIBSTR(\
	"The error code provided is invalid")
#define	MSG0_SU_INITIAL_INSTALL			ILIBSTR(\
	"Preparing system for Solaris install")
#define	MSG0_SU_FLASH_INSTALL			ILIBSTR(\
	"Preparing system for Flash install")
#define	MSG0_SU_FLASH_INSTALL			ILIBSTR(\
	"Preparing system for Flash install")
#define	MSG0_SU_FLASH_UPDATE			ILIBSTR(\
	"Preparing system for Flash update")
#define	MSG0_SU_UPGRADE				ILIBSTR(\
	"Preparing system for Solaris upgrade")
#define	MSG0_SU_FILES_CUSTOMIZE			ILIBSTR(\
	"Customizing system files")
#define	MSG0_SU_INSTALL_CONFIG_FAILED		ILIBSTR(\
	"Could not install system configuration files")
#define	MSG0_SU_DRIVER_INSTALL			ILIBSTR(\
	"Installing unbundled device driver support")
#define	MSG0_SU_MOUNTING_TARGET			ILIBSTR(\
	"Mounting remaining file systems")
#define	MSG0_SU_INITIAL_INSTALL_COMPLETE	ILIBSTR(\
	"Installation complete")
#define	MSG0_SU_INITIAL_CD1OF2_INSTALL_COMPLETE	ILIBSTR(\
	"Install of CD 1 complete.  The system will ask you for CD 2 " \
	"after you reboot.")
#define	MSG0_SU_INIT_CD1OF2_INSTALL_COMPLETE_WEB	ILIBSTR(\
	"Install of CD 1 complete.")
#define	MSG0_SU_FLASH_INSTALL_COMPLETE		ILIBSTR(\
	"Flash installation complete")
#define	MSG0_SU_FLASH_UPDATE_COMPLETE		ILIBSTR(\
	"Flash update complete")
#define	MSG0_SU_UNCONFIGURE_FAILED		ILIBSTR(\
	"Unable to unconfigure the extracted system")
#define	MSG0_SU_UPGRADE_COMPLETE		ILIBSTR(\
	"Upgrade complete")
#define	MSG0_SU_UPGRADE_CD1OF2_COMPLETE	ILIBSTR(\
	"Upgrade from CD 1 complete.  The system will ask you for CD 2 " \
	"after you reboot.")
#define	MSG0_SU_UPGRADE_CD1OF2_COMPLETE_WEB	ILIBSTR(\
	"Upgrade from CD 1 complete.")

/*
 * svc_vfstab.c strings
 */
#define	MOUNTING_TARGET			ILIBSTR(\
	"Mounting target file systems")
#define	MSG2_FILESYS_MOUNT		ILIBSTR(\
	"Mounting %s (%s)")
#define	MSG1_VFSTAB_ORIG_OPEN		ILIBSTR(\
	"Opening original vfstab file (%s)")

/*
 * svc_dsr_archive_list.c messages
 */

#define	MSG0_DSRAL_SUCCESS			ILIBSTR(\
	"The backup list has been generated for the upgrade.")
#define	MSG0_DSRAL_RECOVERY			ILIBSTR(\
	"A previously interrupted upgrade can be resumed.")
#define	MSG0_DSRAL_CALLBACK_FAILURE		ILIBSTR(\
	"The calling application's callback returned with an error.")
#define	MSG0_DSRAL_PROCESS_FILE_FAILURE		ILIBSTR(\
	"Unable to modify the upgrade's process control file.")
#define	MSG0_DSRAL_MEMORY_ALLOCATION_FAILURE	ILIBSTR(\
	"Unable to allocate dynamic memory.")
#define	MSG0_DSRAL_INVALID_HANDLE		ILIBSTR(\
	"Provided instance handle is invalid.")
#define	MSG0_DSRAL_UPGRADE_CHECK_FAILURE	ILIBSTR(\
	"Unable to determine if a file will be replaced during the upgrade.")
#define	MSG0_DSRAL_INVALID_MEDIA		ILIBSTR(\
	"Invalid media.")
#define	MSG0_DSRAL_NOT_CHAR_DEVICE		ILIBSTR(\
	"Invalid character (raw) device.")
#define	MSG0_DSRAL_UNABLE_TO_WRITE_MEDIA	ILIBSTR(\
	"Unable to write to specified media. Make sure the "\
	"media is loaded and not write protected.")
#define	MSG0_DSRAL_UNABLE_TO_STAT_PATH		ILIBSTR(\
	"Unable to stat media. Make sure the media path is valid.")
#define	MSG0_DSRAL_CANNOT_RSH			ILIBSTR(\
	"Unable to open a remote shell on the system specified "\
	"in the media path. Make sure the system being upgraded "\
	"has .rhosts permissions on the specified system.")
#define	MSG0_DSRAL_UNABLE_TO_OPEN_DIRECTORY	ILIBSTR(\
	"Unable to open a directory that is being backed up.")
#define	MSG0_DSRAL_INVALID_PERMISSIONS		ILIBSTR(\
	"The directory you specified for the backup "\
	"has invalid permissions.\n\n"\
	"The directory must have read/write permissions for "\
	"the \"other\" ownership type. Use the \"chmod o+rw\" "\
	"command to change the directory to the required "\
	"permissions.\n\n"\
	"If you specified a remote file system (NFS) "\
	"for the backup, the NFS file system must also be shared "\
	"with read/write permissions. Use the share(1M) command "\
	"to find out if the NFS file system is shared with the "\
	"required permissions.")
#define	MSG0_DSRAL_INVALID_DISK_PATH		ILIBSTR(\
	"Invalid directory or block device.")
#define	MSG0_DSRAL_DISK_NOT_FIXED		ILIBSTR(\
	"The media cannot be used for the "\
	"backup because it is being changed or moved during "\
	"the upgrade.")
#define	MSG0_DSRAL_UNABLE_TO_MOUNT		ILIBSTR(\
	"Unable to mount the media.")
#define	MSG0_DSRAL_NO_MACHINE_NAME		ILIBSTR(\
	"The media path requires a system name.")
#define	MSG0_DSRAL_ITEM_NOT_FOUND		ILIBSTR(\
	"The requested item was not found in the list of installed services.")
#define	MSG0_DSRAL_CHILD_PROCESS_FAILURE	ILIBSTR(\
	"An error occurred managing the archiving process.")
#define	MSG0_DSRAL_LIST_MANAGEMENT_ERROR	ILIBSTR(\
	"An internal error occurred in the list management functions.")
#define	MSG0_DSRAL_INSUFFICIENT_MEDIA_SPACE	ILIBSTR(\
	"The media has insufficient space for the backup.")
#define	MSG0_DSRAL_SYSTEM_CALL_FAILURE		ILIBSTR(\
	"An internal system call returned a failure.")
#define	MSG0_DSRAL_INVALID_FILE_TYPE		ILIBSTR(\
	"An unrecognized file type has been encountered on the system.")
#define	MSG0_DSRAL_INVALID_ERROR_CODE		ILIBSTR(\
	"The provided error code is invalid for the upgrade object.")

/*
 * svc_be.c messages
 */
#define	MSG_BE_UNKNOWN_TYPE			ILIBSTR(\
	"Unknown bootenv command type (%d)")

#define	MSG_BE_TMPFILE				ILIBSTR(\
	"Cannot create BE configuration temporary file")

#define	MSG_BE_INSTALL_FAILED				ILIBSTR(\
	"Cannot create BE configuration file <%s>")

/*
 * svc_flash.c messages
 */

#define	MSG0_INTERNAL_ERROR			ILIBSTR(\
	"Internal error")
#define	MSG0_FLASH_NO_EXCLUSION_LIST		ILIBSTR(\
	"No exclusion list detected.")
#define	MSG0_FLASH_CORRUPT_COOKIE		ILIBSTR(\
	"The archive is corrupt - bad cookie.")
#define	MSG0_FLASH_ARCHIVE_BAD_MAJOR		ILIBSTR(\
	"Unsupported version (%s).")
#define	MSG0_FLASH_UNABLE_TO_READ_IDENT		ILIBSTR(\
	"Unable to read identification section")
#define	MSG0_FLASH_PREM_END_IDENT		ILIBSTR(\
	"Identification section ended prematurely")
#define	MSG0_FLASH_CANT_READ_IDENT		ILIBSTR(\
	"Could not read the identification section")
#define	MSG0_FLASH_UNABLE_TO_FIND_IDENT		ILIBSTR(\
	"Could not find the identification section")
#define	MSG0_FLASH_UNABLE_TO_FIND_FILES		ILIBSTR(\
	"Could not find the files section")
#define	MSG0_FLASH_UNKNOWN_ARC_METHOD		ILIBSTR(\
	"Unknown archive method (%s)")
#define	MSG0_FLASH_UNKNOWN_COMP_METHOD		ILIBSTR(\
	"Unknown compression method (%s)")
#define	MSG0_FLASH_BAD_ARC_SIZE			ILIBSTR(\
	"Bad archived size (%s)")
#define	MSG0_FLASH_BAD_UNARC_SIZE		ILIBSTR(\
	"Bad unarchived size (%s)")
#define	MSG0_FLASH_BAD_CREATE_DATE		ILIBSTR(\
	"Bad creation date (%s)")
#define	MSG0_FLASH_IDENT_SECTION		ILIBSTR(\
	"Archive Identification Section")
#define	MSG0_FLASH_IDENT_SECTION_UNK_KW		ILIBSTR(\
	"Unknown keywords")
#define	MSG0_FLASH_UNSUP_HASH			ILIBSTR(\
	"NOTE: Archive ID verification unsupported on this release of Solaris")
#define	MSG0_FLASH_UNSUP_X86BOOT1		ILIBSTR(\
	"NOTE: An x86 boot partition has been detected.  Flash extraction")
#define	MSG0_FLASH_UNSUP_X86BOOT2		ILIBSTR(\
	"may not succeed if the Flash archive contains files in /boot")
#define	MSG0_FLASH_CORRUPT_ARCHIVE		ILIBSTR(\
	"WARNING: Flash Archive IDs do not match (possible corrupt archive)")
#define	MSG0_FLASH_UNSUP_ARCHITECTURE		ILIBSTR(\
	"Archive does not support this architecture (%s)")
#define	MSG0_FLASH_INSTALL_BEGIN		ILIBSTR(\
	"Beginning Flash archive processing")
#define	MSG0_FLASH_CANT_START_XTRACT		ILIBSTR(\
	"Could not start the extraction")
#define	MSG0_FLASH_CANT_STOP_XTRACT		ILIBSTR(\
	"Could not stop the extraction")
#define	MSG0_FLASH_RET_TYPE_LOCAL_FILE		ILIBSTR(\
	"local file")
#define	MSG0_FLASH_RET_TYPE_LOCAL_TAPE		ILIBSTR(\
	"tape")
#define	MSG0_FLASH_RET_TYPE_LOCAL_DEVICE	ILIBSTR(\
	"local device")
#define	MSG0_FLASH_EXTRACTING_ARCHIVE_NAME	ILIBSTR(\
	"Extracting archive: %s")
#define	MSG0_FLASH_EXTRACTION_COMPLETE		ILIBSTR(\
	"Extraction complete")
#define	MSG0_FLASH_CANT_MAKE_MOUNTPOINT		ILIBSTR(\
	"Could not create mount point")
#define	MSG0_FLASH_CANT_MOUNT_NFS		ILIBSTR(\
	"Could not mount %s:%s")
#define	MSG0_FLASH_CANT_MOUNT			ILIBSTR(\
	"Could not mount %s")
#define	MSG0_FLASH_CANT_UMOUNT_NFS		ILIBSTR(\
	"Could not unmount %s:%s")
#define	MSG0_FLASH_CANT_UMOUNT			ILIBSTR(\
	"Could not unmount %s")
#define	MSG0_FLASH_MOUNTED_FS			ILIBSTR(\
	"Device %s mounted with fstype %s")
#define	MSG0_FLASH_BAD_FSTYPE			ILIBSTR(\
	"Invalid filesytem type (%s)")
#define	MSG0_FLASH_CANT_POSITION_TAPE		ILIBSTR(\
	"Could not move tape to position %d")
#define	MSG0_FLASH_CANT_OPEN_TAPE		ILIBSTR(\
	"Could not open tape device (%s)")
#define	MSG0_FLASH_TAPE_NOSPC			ILIBSTR(\
	"Block size (%d bytes) too small for archive")
#define	MSG0_FLASH_CANT_STATUS_TAPE		ILIBSTR(\
	"Could not get tape device status (is a tape loaded?)")

#define	MSG0_FLASH_UNABLE_TO_MAKE_FLASH_TMP	ILIBSTR(\
	"Could not create temporary directory")
#define	MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD	ILIBSTR(\
	"Could not create temporary command - Buffer Overflow")

#define	MSG0_FLASH_PREDEPLOYMENT		ILIBSTR(\
	"Predeployment processing")
#define	MSG0_FLASH_POSTDEPLOYMENT		ILIBSTR(\
	"Postdeployment processing")
#define	MSG0_FLASH_VALIDATION			ILIBSTR(\
	"Clone validation")

#define	MSG0_FLASH_MANIFEST_NOT_FOUND			ILIBSTR(\
	"Manifest section not found")
#define	MSG0_FLASH_PREDEPLOYMENT_NOT_FOUND			ILIBSTR(\
	"Predeployment customization section not found")
#define	MSG0_FLASH_POSTDEPLOYMENT_NOT_FOUND			ILIBSTR(\
	"Postdeployment customization section not found")
#define	MSG0_FLASH_REBOOT_NOT_FOUND			ILIBSTR(\
	"Reboot customization section not found")

#define	MSG0_FLASH_UNABLE_TO_FIND_PREDEPLOYMENT		ILIBSTR(\
	"Read error while searching for predeployment section")
#define	MSG0_FLASH_UNABLE_TO_FIND_POSTDEPLOYMENT	ILIBSTR(\
	"Read error while searching for postdeployment section")
#define	MSG0_FLASH_UNABLE_TO_FIND_REBOOT		ILIBSTR(\
	"Read error while searching for reboot section")
#define	MSG0_FLASH_WRONG_MASTER				ILIBSTR(\
	"Clone master differs from archive master (\"%s\" ws \"%s\")")
#define	MSG0_FLASH_UNABLE_TO_FIND_MANIFEST		ILIBSTR(\
	"Read error while searching for manifest section")
#define	MSG0_FLASH_UNABLE_TO_SKIP_MANIFEST		ILIBSTR(\
	"Read error while skipping manifest section")
#define	MSG0_FLASH_UNEXPECTED_EOF		ILIBSTR(\
	"Unexpected EOF while skipping manifest section")
#define	MSG0_NO_LOCAL_CUSTOMIZATION		ILIBSTR(\
	"No local customization defined")
#define	MSG0_LOCAL_CUSTOMIZATION		ILIBSTR(\
	"Start local customization")
#define	MSG0_LOCAL_CUSTOMIZATION_DONE		ILIBSTR(\
	"Local customization. Done")

#define	MSG0_FLASH_UNABLE_TO_READ_PREDEPLOYMENT		ILIBSTR(\
	"Read error while reading predeployment section")
#define	MSG0_FLASH_UNABLE_TO_WRITE_PREDEPLOYMENT	ILIBSTR(\
	"Error while processing predeployment section")
#define	MSG0_FLASH_SYSTEM_PREDEPLOYMENT_FAILURE	ILIBSTR(\
	"Error while processing system predeployment script")
#define	MSG0_FLASH_UNABLE_TO_READ_POSTDEPLOYMENT	ILIBSTR(\
	"Read error while reading postdeployment section")
#define	MSG0_FLASH_UNABLE_TO_WRITE_POSTDEPLOYMENT	ILIBSTR(\
	"Error while processing postdeployment section")
#define	MSG0_FLASH_SYSTEM_POSTDEPLOYMENT_FAILURE	ILIBSTR(\
	"Error while processing system postdeployment script")
#define	MSG0_FLASH_CUSTOM_SCRIPT_FAILURE		ILIBSTR(\
	"Error while processing custom script - %s")
#define	MSG0_FLASH_UNABLE_TO_READ_REBOOT		ILIBSTR(\
	"Read error while reading reboot section")
#define	MSG0_FLASH_UNABLE_TO_WRITE_REBOOT		ILIBSTR(\
	"Error while processing reboot section")
#define	MSG0_FLASH_UNABLE_TO_READ_MANIFEST		ILIBSTR(\
	"Read error while reading manifest")
#define	MSG0_FLASH_UNEXPECTED_MANIFEST_END		ILIBSTR(\
	"Unexpected manifest end")
#define	MSG0_FLASH_UNABLE_TO_CLEAN_CLONE		ILIBSTR(\
	"Remove failure. Can not clean clone")

#define	MSG0_FLASH_DELETED_FILES		ILIBSTR(\
	"Deleted files detected: %s")
#define	MSG0_FLASH_MODIFIED_FILES		ILIBSTR(\
	"Modified files detected: %s")
#define	MSG0_FLASH_NEW_FILES			ILIBSTR(\
	"New files detected: %s")
#define	MSG0_FLASH_OLD_FILES			ILIBSTR(\
	"Old files detected: %s")
#define	MSG0_FLASH_DEL_FILES			ILIBSTR(\
	"File to delete: %s")
#define	MSG0_FLASH_RM_FILES			ILIBSTR(\
	"Removing old file: %s")

#define	MSG0_UNCONFIGURING_SYSTEM		ILIBSTR(\
	"Unconfiguring system")
#define	MSG0_TAPE_BLKSIZE_UNAVAIL		ILIBSTR(\
	"Unable to read tape drive maximum block size - defaulting to %d bytes")
#define	MSG0_TAPE_BLKSIZE_TOOBIG		ILIBSTR(\
	"The specified block size (%d bytes) is larger than " \
	"the maximum supported by %s (%d bytes).  Using block size of %d.")
#define	MSG0_TAPE_DETAILS			ILIBSTR(\
	"Opened tape device:")
#define	MSG0_TAPE_DEVICE			ILIBSTR(\
	"Device")
#define	MSG0_TAPE_NAME				ILIBSTR(\
	"Name")
#define	MSG0_TAPE_VENDOR_ID			ILIBSTR(\
	"Vendor ID")
#define	MSG0_TAPE_TYPE				ILIBSTR(\
	"Drive type")
#define	MSG0_TAPE_MAXBLKSIZE			ILIBSTR(\
	"Maximum block size")
#define	MSG0_TAPE_BLKSIZE			ILIBSTR(\
	"Current block size")
#define	MSG0_CANT_GET_TAPE_INFO			ILIBSTR(\
	"Cannot retrieve tape drive identification information")
#define	MSG0_HTTP_CANT_ACCESS_ARCHIVE		ILIBSTR(\
	"Unable to access the archive.  The server returned %d: %s")
#define	MSG0_HTTP_NEED_ARCHIVE_SIZE		ILIBSTR(\
	"The HTTP server did not return the size of the archive file")
#define	MSG0_CANNOT_CONNECT			ILIBSTR(\
	"Cannot connect to %s port %d: %s")
#define	MSG0_UNKNOWN_HOST			ILIBSTR(\
	"Unknown host: %s")
#define	MSG0_HTTP_STATUS			ILIBSTR(\
	"Response to %s request: %d (Length: %d bytes)")
#define	MSG0_HTTP_INVALID_STATUS		ILIBSTR(\
	"Invalid HTTP status line: %s")
#define	MSG0_HTTP_INVALID_HEADERS		ILIBSTR(\
	"Invalid HTTP headers were returned from the server")
#define	MSG0_HTTP_INVALID_HEADER		ILIBSTR(\
	"Invalid HTTP header: %s")
#define	MSG0_HTTP_SIZE_CHANGED			ILIBSTR(\
	"The archive size has changed from %lld to %lld")
#define	MSG0_HTTP_SIZE_INVALID			ILIBSTR(\
	"HTTP server returned an invalid archive file size: <%ld> bytes")
#define	MSG0_HTTP_INVALID_START			ILIBSTR(\
	"Unexpected HTTP start position %lld (expecting %lld)")
#define	MSG0_HTTP_INVALID_REDIRECT		ILIBSTR(\
	"Unable to parse redirect address: %s")
#define	MSG0_HTTP_REDIR_WO_LOC			ILIBSTR(\
	"HTTP server returned a redirect (%d) without a location")
#define	MSG0_HTTP_TOO_MANY_REDIRS		ILIBSTR(\
	"HTTP server redirected more than %d times")
#define	MSG0_HTTP_REDIRECT			ILIBSTR(\
	"Redirected to: %s")
#define	MSG0_FTP_NEED_ARCHIVE_SIZE		ILIBSTR(\
	"The FTP server %s did not return the size of the archive file %s")
#define	MSG0_FTP_CANT_PARSE_SIZE		ILIBSTR(\
	"Cannot parse size from \"%s\": Unsupported FTP server")
#define	MSG0_FTP_TRANSFER_COMPLETE		ILIBSTR(\
	"Transfer complete")
#define	MSG0_FTP_REPLY_LONG			ILIBSTR(\
	"Reply too long")
#define	MSG0_FTP_BAD_TRANSFER			ILIBSTR(\
	"The FTP server indicated incomplete transfer: %s")
#define	MSG0_FTP_DEFAULT_TIMEOUT		ILIBSTR(\
	"Connection timed out")

/*
 * Extra package and patch install strings
 */
#define	MSG0_EXTRA_PACKAGE_INSTALL_NOW		ILIBSTR(\
	"Installing additional packages now")
#define	MSG1_WOS_PKG				ILIBSTR(\
	"Cannot install package %s from alternate location")
#define	MSG1_SKIP_PKG				ILIBSTR(\
	"Skipping package %s")
#define	MSG3_EXTRA_PKG				ILIBSTR(\
	"Installing package %s from %s of location type \"%s\"")
#define	MSG2_EXTRA_PKG_ALL			ILIBSTR(\
	"Installing all packages from %s of location type \"%s\"")
#define	MSG0_CANT_MAKE_MOUNTPOINT_PKG		ILIBSTR(\
	"Could not create mount point for additional package install")
#define	MSG2_CANT_MOUNT_NFS_PKG			ILIBSTR(\
	"Could not mount %s:%s for additonal package install ")
#define	MSG2_CANT_UMOUNT_NFS			ILIBSTR(\
	"Could not unmount %s:%s")
#define	MSG1_CANT_MOUNT_DEVICE_PKG		ILIBSTR(\
	"Could not mount %s for additonal package install")
#define	MSG1_CANT_UMOUNT_DEVICE			ILIBSTR(\
	"Could not unmount %s")
#define	MSG2_MOUNTED_FS				ILIBSTR(\
	"Device %s mounted with fstype %s")

#define	MSG0_PATCH_INSTALL_NOW		ILIBSTR(\
	"Installing patches now")
#define	MSG2_PATCH_INSTALL		ILIBSTR(\
	"Installing patch(es) from %s of location type \"%s\"")
#define	MSG0_PATCHADD_EXEC_FAILED		ILIBSTR(\
	"patchadd command failed")
#define	MSG0_CANT_MAKE_MOUNTPOINT_PATCH		ILIBSTR(\
	"Could not create mount point for patch install")
#define	MSG2_CANT_MOUNT_NFS_PATCH		ILIBSTR(\
	"Could not mount %s:%s for patch install ")
#define	MSG1_CANT_MOUNT_DEVICE_PATCH		ILIBSTR(\
	"Could not mount %s for patch install")

/*
 * i18n: next message describes a specific archive.
 * The first %s is the retrieval method; the second is
 * the location of the archive.  Example:
 *
 *    Extracting local file archive from /tmp/foo
 *
 * `local file' is the first %s; `/tmp/foo' is the second.
 */
#define	MSG0_FLASH_EXTRACTING_ARCHIVE_X		ILIBSTR(\
	"Extracting %s archive from %s")

#define	MSG0_ARCHIVE_FF		ILIBSTR(\
	"FTP Server does not support REST command.  Manually " \
	"skipping %lld bytes...")

/* svc_upgradeable strings */

#define	MSG0_UPG_CHECKING_FS			ILIBSTR(\
	"Checking %s for an upgradeable Solaris image")

#define	MSG0_UNABLE_TO_CLEAR_ROOTDIR		ILIBSTR(\
	"Unable to unmount all devices for %s")

#define	MSG0_CANT_MOUNT_ROOT 			ILIBSTR(\
	"Unable to mount root device %s")

#define	MSG0_SVM_START_FAILED			ILIBSTR(\
	"Unable to start Solaris Volume Manager for %s, %s is not upgradeable")

#define	MSG0_CANT_MOUNT_STUBBOOT		ILIBSTR(\
	"Unable to mount the X86 Boot fdisk partition")

#define	MSG0_CANT_MOUNT_VAR			ILIBSTR(\
	"Unable to mount the var filesystem, %s is not upgradeable")

#define	MSG0_STUB_NOT_SUPPORTED			ILIBSTR(\
	"%s does not support X86 Boot fdisk partition")

#define	MSG0_DANGLING_STUB			ILIBSTR(\
	"The X86 Boot fdisk partition is missing %s%s")

#define	MSG0_SVM_STOP_FAILED			ILIBSTR(\
	"Unable to stop the Solaris Volume Manager, %s is not upgradeable")

#define	MSG0_CANT_READ_CLUSTERTOC		ILIBSTR(\
	"Unable to read clustertoc")

#define	MSG0_INSTANCE_NOT_UPGRADEABLE		ILIBSTR(\
	"Unable to upgrade from %s to this release")

#define	MSG0_CANT_FIND_REQ_USR_PKGS		ILIBSTR(\
	"Unable to find the required user packages, eg. SUNWcsu")

/* BEGIN CSTYLED */
#define	MSG0_LOCAL_ZONES_PRESENT		ILIBSTR(\
	"Unable to upgrade %s mounted at %s: one or more non-global \
	zones detected. Currently Solaris upgrade does not support upgrading \
	systems configured with non-global zones. Please refer to \
	http://sun.com/msg/SUNOS-8000-91 \
	for current information on upgrading systems with non-global zones \
	installed.")
/* END CSTYLED */

#define	MSG0_NO_BOOTENV				ILIBSTR(\
	"%s%s does not exist")

#define	MSG0_CREATE_SVM_METADEVICES		ILIBSTR(\
	"Creating SVM Meta Devices. Please wait ...")

#define	MSG0_ZONE_UPGRADEABLE			ILIBSTR(\
	"Non-global zone %s is upgradeable.")

#define	MSG0_ZONE_NOT_UPGRADEABLE		ILIBSTR(\
	"Non-global zone %s is installed, but not upgradeable.")

#define	MSG0_ZONE_NOT_INSTALLED			ILIBSTR(\
	"Non-global zone %s is not installed and will not be upgraded.")

#define	MSG0_COULD_NOT_GET_NONGLOBAL_ZONE_LIST	ILIBSTR(\
	"Cannot find non-global zone list.")

#define	MSG0_MISSING_ZONE_PKG_DIR		ILIBSTR(\
	"Cannot find usr packages for non-global zone %s - not upgradeable.")

#define	MSG0_ZONES_NOT_UPGRADEABLE		ILIBSTR(\
	"One or more non-global zones are installed but not upgradeable. \
	This instance of Solaris cannot be upgraded while non-global zones \
	are in the installed state.")

#define	MSG0_INVALID_ZONE_PATH		ILIBSTR(\
	"Non-global zone %s has an invalid pathname. This non-global zone \
	will not be upgraded.")

#define	MSG1_COULD_NOT_GET_SCRATCHNAME		ILIBSTR(\
	"Unable to get the scratchname of non-global zone %s. This non-global \
	zone will not be upgraded.")

#ifdef __cplusplus
}
#endif

#endif /* _SVC_STRINGS_H */
