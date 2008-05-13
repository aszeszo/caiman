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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _ORCHESTRATOR_API_H
#define	_ORCHESTRATOR_API_H

#ifdef __cplusplus
extern "C" {
#endif

#include <sys/dktp/fdisk.h>
#include <sys/vtoc.h>
#include <libnvpair.h>

extern	int16_t		om_errno;
typedef int16_t		om_handle_t;

/*
 * Callbacks definitions and functions
 */
typedef enum {
	OM_TARGET_TARGET_DISCOVERY = 0,
	OM_SYSTEM_VALIDATION,
	OM_INSTALL_TYPE,
	OM_UPGRADE_TYPE,
	OM_TOOLS_INSTALL_TYPE
} om_callback_type_t;

typedef enum {
	OM_DISK_DISCOVERY = 0,
	OM_PARTITION_DISCOVERY,
	OM_SLICE_DISCOVERY,
	OM_UPGRADE_TARGET_DISCOVERY,
	OM_INSTANCE_DISCOVERY,
	OM_TARGET_INSTANTIATION,
	OM_UPGRADE_CHECK,
	OM_SOFTWARE_UPDATE,
	OM_POSTINSTAL_TASKS,
	OM_TOOLS_SUNSTUDIO,
	OM_TOOLS_NETBEANS,
	OM_TOOLS_JAVAAPPSVR,
	OM_INSTALLER_FAILED
} om_milestone_type_t;

typedef struct om_callback_info {
	int			num_milestones; /* number to track for op */
	om_milestone_type_t	curr_milestone;
	om_callback_type_t	callback_type;
	int16_t			percentage_done;
	const char		*message;	/* progress text for GUI */
} om_callback_info_t;

typedef void (*om_callback_t)(om_callback_info_t *, uintptr_t);

typedef enum {
	OM_DTYPE_UNKNOWN = 0,
	OM_DTYPE_ATA,
	OM_DTYPE_SCSI,
	OM_DTYPE_FIBRE,
	OM_DTYPE_USB,
	OM_DTYPE_SATA,
	OM_DTYPE_FIREWIRE
} om_disk_type_t;

typedef enum {
	OM_CTYPE_UNKNOWN = 0,
	OM_CTYPE_SOLARIS,
	OM_CTYPE_LINUXSWAP,
	OM_CTYPE_LINUX
} om_content_type_t;

typedef enum {
	OM_LABEL_UNKNOWN = 0,
	OM_LABEL_VTOC,
	OM_LABEL_GPT,
	OM_LABEL_FDISK
} om_disklabel_type_t;

typedef enum {
	OM_INSTANCE_UFS = 1,
	OM_INSTANCE_ZFS
} om_instance_type_t;

typedef enum {
	OM_UPGRADE_UNKNOWN_ERROR = 2000,
	OM_UPGRADE_INSTANCE_IS_MIRROR,
	OM_UPGRADE_NG_ZONE_CONFIURE_PROBLEM,
	OM_UPGRADE_RELEASE_NOT_SUPPORTED,
	OM_UPGRADE_RELEASE_INFO_MISSING,
	OM_UPGRADE_INSTANCE_INCOMPLETE,
	OM_UPGRADE_ROOT_FS_CORRUPTED,
	OM_UPGRADE_MOUNT_ROOT_FAILED,
	OM_UPGRADE_MOUNT_VAR_FAILED,
	OM_UPGRADE_MISSING_CLUSTER_FILE,
	OM_UPGRADE_MISSING_CLUSTERTOC_FILE,
	OM_UPGRADE_MISSING_BOOTENVRC_FILE,
	OM_UPGRADE_WRONG_METACLUSTER
} om_upgrade_message_t;

typedef enum {
	OM_UNASSIGNED = 0,
	OM_BOOT,
	OM_ROOT,
	OM_SWAP,
	OM_USR,
	OM_BACKUP,
	OM_STAND,
	OM_VAR,
	OM_HOME,
	OM_ALTSCTR,
	OM_CACHE,
	OM_RESERVED
} om_slice_tag_type_t;

typedef	enum {
	KBD_NUM = 1,
	KBD_NAME,
	KBD_VALUE
} kbd_data_t;

typedef enum {
	OM_INITIAL_INSTALL = 1,
	OM_UPGRADE
} om_install_type_t;

typedef struct disk_info {
	char			*disk_name;	/* For example c0t0d0 */
	uint32_t		disk_size;	/* Size in MB */
	om_disk_type_t		disk_type;	/* SCSI, IDE, USB etc. */
	char			*vendor;	/* Manufacturer */
	boolean_t		boot_disk;	/* Is it a boot disk? */
	om_disklabel_type_t	label;		/* disk label */
	boolean_t		removable;	/* Is it removable (USB?) */
	char			*serial_number; /* Manufacturer assigned */
	uint32_t		disk_cyl_size;	/* Cylinder Size in sectors */
	uint64_t		disk_size_sec;	/* Disk size in sectors */
	struct disk_info	*next;		/* pointer to next disk */
} disk_info_t;

typedef struct {
	uint8_t			partition_id;	/* fdisk id (1-4) */
	uint32_t		partition_size;	/* Size in MB */
	uint32_t		partition_offset;
				/* Offset in MB from start of the disk */
	uint8_t			partition_order; /* Order in the disk */
	uint8_t			partition_type;	/* Solaris/linux swap/X86boot */
	om_content_type_t	content_type;	/* Solaris/Linux */
	boolean_t		active;		/* Is the partition active */
	uint64_t		partition_size_sec;	/* Size in sectors */
	uint64_t		partition_offset_sec;	/* offset in sectors */
} partition_info_t;

typedef struct {
	char			*disk_name;	/* Disk Name for look up */
	partition_info_t	pinfo[FD_NUMPART];	/* fdisk partitions */
} disk_parts_t;

typedef struct {
	uint8_t			slice_id;	/* sdisk id (0-15) */
	uint32_t		slice_size;	/* Size in MB */
	uint32_t		slice_offset;	/* in MB */
	om_slice_tag_type_t	tag;		/* root/swap/unassigned etc. */
	uint8_t			flags;		/* RO/RW, (un)mountable */
} slice_info_t;

typedef struct {
	uint8_t		partition_id;	/* For look up, only for X86 */
	char		*disk_name;	/* Disk Name for look up */
	slice_info_t	sinfo[NDKMAP];	/* vtoc slices */
} disk_slices_t;

typedef	struct {
	char		*disk_name;	/* Where the Instance resides */
	uint8_t		slice;		/* Which Slice (0-15) */
	boolean_t	svm_configured;	/* Part of SVM root */
	char		*svm_info;	/* mirror components */
} ufs_instance_t;

typedef	struct {
	char		*pool_name;	/* More info will be added */
} zfs_instance_t;

typedef struct upgrade_info {
	om_instance_type_t	instance_type;	/* UFS or ZFS */
	union {
		ufs_instance_t	uinfo;
		zfs_instance_t	zinfo;
	} instance;
	char			*solaris_release;
		/* Some thing like "Solaris Developer Express Release 1" */
	boolean_t		zones_installed;
		/* Non global zones configured in the Solaris Instance */
	boolean_t		upgradable;
		/* Does the instance looks okay */
	om_upgrade_message_t	upgrade_message_id;
		/* If an instance can't be upgraded, why? */
	char			*incorrect_zone_list;
		/* List of non-globlal zones not configured correctly */
	struct upgrade_info	*next;	/* link to next Instance */
} upgrade_info_t;

typedef struct keyboard_type {
	int		kbd_num;
	char		*kbd_name;
	boolean_t	is_default;
	struct keyboard_type	*next;
} keyboard_type_t;

typedef struct locale_info {
	char			*locale_name;
	char			*locale_desc;
	boolean_t 		def_locale;
	struct	locale_info	*next;
} locale_info_t;

typedef struct lang_info {
	/* pointer to all locale_info_t's for language */
	locale_info_t		*locale_info;
	boolean_t 		def_lang; /* Is this the default language */
	char			*lang;	 /* language code name, i.e, 'en' */
	int			n_locales;
	/* Fully expanded language name, translated appropriately */
	char			*lang_name;
	struct 	lang_info	*next;
} lang_info_t;

#define	OM_PREINSTALL	1

#define	ONEMB		1048576

#define	OM_SUCCESS	0
#define	OM_FAILURE	-1

#define	OM_UNKNOWN_STRING	"unknown"
#define	OM_PARTITION_UNKNOWN	99
#define	OM_SLICE_UNKNOWN	99
#define	OM_INVALID_MILESTONE	-1

#define	OM_MIN_MEDIA_SIZE	8192

#define	OM_MAX_VOL_NUM		1

/*
 * Attributes for nv_list to pass data to perform install/upgrade
 */
#define	OM_ATTR_INSTALL_TYPE		"install_type"
#define	OM_ATTR_UPGRADE_TARGET		"upgrade_target"
#define	OM_ATTR_DISK_NAME		"disk_name"
#define	OM_ATTR_TIMEZONE_INFO		"timezone"
#define	OM_ATTR_DEFAULT_LOCALE		"default_locale"
#define	OM_ATTR_HOST_NAME		"host_name"
#define	OM_ATTR_ROOT_PASSWORD		"root_password"
#define	OM_ATTR_USER_NAME		"user_name"
#define	OM_ATTR_LOGIN_NAME		"login_name"
#define	OM_ATTR_USER_PASSWORD		"user_password"
#define	OM_ATTR_LOCALES_LIST		"locales_list"
#define	OM_ATTR_INSTALL_TEST		"install_test"

#define	OM_DEFAULT_ROOT_PASSWORD	""
#define	OM_DEFAULT_USER_PASSWORD	""
/*
 * Target discovery - Disk related error ids
 */
#define	OM_TD_DISCOVERY_FAILED			101
#define	OM_DISCOVERY_NEEDED			102
#define	OM_NO_DISKS_FOUND			103
#define	OM_TD_IN_PROGRESS			104
#define	OM_NO_PARTITION_FOUND			105
#define	OM_NO_SPACE				106
#define	OM_INVALID_DISK_PARTITION		107
#define	OM_NO_UPGRADE_TARGETS_FOUND		108
#define	OM_FORMAT_UNKNOWN			109
#define	OM_BAD_DISK_NAME			110
#define	OM_CONFIG_EXCEED_DISK_SIZE		111
#define	OM_NO_UPGRADE_TARGET_NAME		112
#define	OM_UNSUPPORTED_CONFIG			113
#define	OM_TRANSFER_FAILED			114
#define	OM_ZFS_ROOT_POOL_EXISTS			115

#define	OM_NO_INSTALL_TARGET			201
#define	OM_BAD_INSTALL_TARGET			202
#define	OM_NO_INSTALL_TYPE			203
#define	OM_BAD_INSTALL_TYPE			204
#define	OM_INITIAL_INSTALL_PROFILE_FAILED	205
#define	OM_INITIAL_INSTALL_FAILED		206
#define	OM_SIZE_IS_SMALL			207
#define	OM_TARGET_INSTANTIATION_FAILED		208
#define	OM_NO_TARGET_ATTRS			209

#define	OM_NO_UPGRADE_TARGET			301
#define	OM_BAD_UPGRADE_TARGET			302
#define	OM_NOT_UFS_UPGRADE_TARGET		303
#define	OM_UPGRADE_PROFILE_FAILED		304
#define	OM_UPGRADE_FAILED			305
#define	OM_CANNOT_LOAD_MEDIA			306
#define	OM_NOT_ENOUGH_SPACE			307
#define	OM_SPACE_CHECK_FAILURE			308
#define	OM_CANNOT_UMOUNT_ROOT_SWAP		309
#define	OM_UPGRADE_NOT_ALLOWED			310

#define	OM_ERROR_THREAD_CREATE			901
#define	OM_NO_PROGRESS_FILE			902
#define	OM_NO_PROCESS				903
#define	OM_PFINSTALL_FAILURE			904
#define	OM_INVALID_USER				905
#define	OM_TOOLS_INSTALL_FAILURE		906
#define	OM_MISSING_TOOLS_SCRIPT			907
#define	OM_CANT_CREATE_VTOC_TARGET		908
#define	OM_CANT_CREATE_ZPOOL			909
#define	OM_BAD_INPUT				999

/*
 * Locale, language discovery related error codes
 */
#define	OM_NO_LOCALE_DIR			401
#define	OM_PERMS				402
#define	OM_TOO_MANY_FD				403
#define	OM_FOUND				404
#define	OM_NO_LOCALES				405
#define	OM_NOT_LANG				406
#define	OM_INVALID_LANG_LIST			407
#define	OM_INVALID_LOCALE			408

/*
 * Timezone related error codes
 */
#define	OM_TIMEZONE_NOT_SET			600
#define	OM_INVALID_TIMEZONE			601

/*
 * Keyboard related error codes
 */

#define	OM_UNKNOWN_KEYBOARD			700
#define	OM_NO_KBD_LAYOUT			701

/*
 * User/root account related error codes
 */
#define	OM_SET_USER_FAIL			800

/*
 * Nodename/hostname failures
 */

#define	OM_SET_NODENAME_FAILURE			500
#define	OM_NO_SUCH_DB_FILE			501
#define	OM_CANT_OPEN_FILE			502
#define	OM_CANT_CREATE_TMP_FILE			503
#define	OM_CANT_WRITE_TMP_FILE			504
#define	OM_CANT_WRITE_FILE			505
#define	OM_SETNODE_FAILURE			506
#define	OM_INVALID_NODENAME			507
#define	OM_CANT_DUP_DESC			508
#define	OM_EEPROM_ERROR				509

#define	OM_CANT_EXEC				1001


/* disk_target.c */
om_handle_t	om_initiate_target_discovery(om_callback_t td_cb);
void		om_free_target_data(om_handle_t handle);

/* disk_info.c */
disk_info_t	*om_get_disk_info(om_handle_t handle, int *total);
void		om_free_disk_info(om_handle_t handle, disk_info_t *dinfo);
disk_info_t	*om_duplicate_disk_info(om_handle_t handle, disk_info_t *dinfo);
disk_info_t	**om_convert_linked_disk_info_to_array(om_handle_t handle,
		    disk_info_t *dinfo, int total);
void		om_free_disk_info_array(om_handle_t handle,
		    disk_info_t **dinfo);

/* disk_parts.c */
disk_parts_t	*om_get_disk_partition_info(om_handle_t handle, char *diskname);
void		om_free_disk_partition_info(om_handle_t handle,
			disk_parts_t *dpinfo);
disk_parts_t	*om_validate_and_resize_disk_partitions(om_handle_t handle,
			disk_parts_t *dpinfo);
disk_parts_t    *om_duplicate_disk_partition_info(om_handle_t handle,
			disk_parts_t *dparts);
int		om_set_disk_partition_info(om_handle_t handle,
			disk_parts_t *dp);

/* disk_slices.c */
disk_slices_t   *om_get_disk_slices_info(om_handle_t handle, char *diskname);
void		om_free_disk_slices_info(om_handle_t handle,
			disk_slices_t *dsinfo);
disk_slices_t   *om_duplicate_disk_slices_info(om_handle_t handle,
			disk_slices_t *dslices);

/* upgrade_target.c */
upgrade_info_t	*om_get_upgrade_targets(om_handle_t handle, uint16_t *found);
upgrade_info_t  *om_get_upgrade_targets_by_disk(om_handle_t handle,
		    char *diskname, uint16_t *found);
void		om_free_upgrade_targets(om_handle_t handle,
		    upgrade_info_t *uinfo);
upgrade_info_t  *om_duplicate_upgrade_targets(om_handle_t handle,
		    upgrade_info_t *uiptr);
boolean_t	om_is_upgrade_target_valid(om_handle_t handle,
		    upgrade_info_t *uinfo, om_callback_t ut_cb);

/* perform_slim_install.c */
int	om_perform_install(nvlist_t *uchoices, om_callback_t inst_cb);
uint64_t	om_get_min_size(char *media, char *distro);
uint64_t	om_get_recommended_size(char *media, char *distro);
uid_t		om_get_user_uid(void);
char		*om_encrypt_passwd(char *passwd, char *username);

/* keyboards.c */
keyboard_type_t *om_get_keyboard_types(int *total);
int   		om_set_keyboard_by_num(int num);
int   		om_set_keyboard_by_name(char *name);
int   		om_set_keyboard_by_value(keyboard_type_t *kbd);
void  		om_free_keyboard_types(keyboard_type_t *kbd);
boolean_t 	om_is_self_id_keyboard(void);

/* locale.c */
locale_info_t	*om_get_def_locale(locale_info_t *loclist);
lang_info_t	*om_get_install_lang_info(int *total);
char		**om_get_install_lang_names(int *total);
lang_info_t  	*om_get_lang_info(int *total);
char		**om_get_lang_names(int *total);
locale_info_t	*om_get_locale_info(char *lang, int *total);
char		**om_get_locale_names(char *lang, int *total);
void		om_save_locale(char *locale, boolean_t install_only);
int   		om_set_install_lang_by_value(lang_info_t *localep);
int   		om_set_install_lang_by_name(char *lang);
int		om_set_default_locale_by_name(char *locale);
void		om_free_lang_info(lang_info_t *langp);
void		om_free_lang_names(char **listp);
void		om_free_locale_info(locale_info_t *localep);

/* timezone.c */
int		om_set_time_zone(char *timezone);
int		om_set_preinstall_timezone(char *country, char *timezone);
char		*om_get_preinstall_timezone();

/* om_misc.c */
int16_t	om_get_error();

/* Test functions */
int	om_test_target_discovery();

#ifdef __cplusplus
}
#endif

#endif	/* _ORCHESTRATOR_API_H */
