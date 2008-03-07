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

#ifndef _ORCHESTRATOR_PRIVATE_H
#define	_ORCHESTRATOR_PRIVATE_H

#pragma ident	"@(#)orchestrator_private.h	1.12	07/10/23 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include <orchestrator_api.h>
#include <ls_api.h>
#include "ti_api.h"

extern char *pre_inst_timezone;

/*
 * Password/shadow file defines
 */

#define	SHADOW_FILE	"/etc/shadow"
#define	PASSWORD_FILE	"/etc/passwd"
#define	TRANS_LIST	"/etc/transfer_list"
#define	NODENAME	"/etc/nodename"
#define	PATH_DEVNULL	"/dev/null"

#define	INIT_FILE	"/etc/default/init"

#define	MNTOPTS		"ro"

#define	LOG_HOST	"loghost"
#define	LOOPBACK_IP	"127.0.0.1"
#define	HOSTS_TABLE	"/etc/hosts"

#define	OVERWRITE_STR	"OVERWRITE"

#define	KBDNAME		"/dev/kbd"
#define	KBD_DEF_FILE	"/etc/default/kbd"
#define	NVRAM_VAR	"keyboard-layout"
#define	BUFSIZE	80
#define	KBD_LAYOUT_FILE	"/usr/share/lib/keytables/type_6/kbd_layouts"
#define	MAX_LAYOUT_NUM	128
#define	TEXT_DOMAIN	"SUNW_INSTALL_LIBORCHESTRATOR"
#define	MAX_LINE_SIZE	256
#define	MAX_NUM_LANG	4096

#define	MAX_LOCALE	40

#define	BLOCKS_TO_MB	2048
#define	MIN_ROOT_SIZE	8192
#define	MAX_ROOT_SIZE	15360
#define	HALF_GB_TO_MB	512
#define	ONE_GB_TO_MB	1024
#define	TWO_GB_TO_MB	2048
#define	FOUR_GB_TO_MB	4096
#define	EIGHT_GB_TO_MB	8192
#define	TEN_GB_TO_MB	10240
#define	TWENTY_GB_TO_MB	20480
#define	THIRTY_GB_TO_MB	30720
#define	OVERHEAD_IN_MB	100

#define	streq(a, b) (strcmp((a), (b)) == 0)

#define	SPARC_ARCH	"sparc"
#define	X86_ARCH	"i386"
#define	ALLDISKS	"all"

#define	PART_UNDEFINED		0
#define	SOLARIS			"solaris"
#define	DOSPRIMARY		"dosprimary"
#define	ROOT_FS			"/"
#define	SECOND_ROOT_FS		"/second_root"
#define	SWAP_FS			"swap"
#define	EXPORT_FS		"/export/home"
#define	FREE_KEYWORD		"free"
#define	INSTALL_CMD		"/usr/sbin/install.d/pfinstall"
#define	INSTALL_TEST_CMD	"/usr/bin/dummy_install"
#define	TOOLS_CMD		"/cdrom/DeveloperTools/main.sh"
#define	TOOLS_TEST_CMD		"/usr/bin/dummy_tools_install"
#define	INSTALLED_ROOT_DIR	"/a"
#define	GUI_INSTALL_LOG		"gui-install_log"
#define	INSTALL_LOG		"install_log"
#define	TRANSFER_LOG		"transfer.log"
#define	PROFILE_NAME		"profile"
#define	INSTALL_LOG_DIRECTORY	"/var/sadm/install/logs"
#define	NSI_LOG_DIRECTORY	"/var/sadm/system/nsi"
#define	PROGRESS_FILE		"/tmp/install_update_progress.out"
#define	HOMEDIR_CREATE_FAILED	"mkdir of %s returned error %d\n"
#define	BAD_DISK_SLICE		"Bad disk slice %s\n"
#define	NSI_LOG_DIR_FAILED	"Creating NSI log directory %s failed\n"
#define	NSI_OPENDIR_FAILED	"Open of %s failed with error %d\n"
#define	NSI_OPENFILE_FAILED	"Open of %s failed with error %d\n"
#define	NSI_CHDIR_FAILED	"chdir to %s failed with error %d\n"
#define	NSI_CREATE_FILE_FAILED	"Creating %s failed with error %d\n"
#define	NSI_CREATE_SLINK_FAILED	"Creating symlink of %s failed with error %d\n"
#define	NSI_GETCWD_FAILED	"getcwd() failed with error %d\n"
#define	NSI_TIME_FAILED		"time() failed with error %d\n"
#define	NSI_MOVE_FILE		"Moved %s to %s\n"
#define	NSI_LINK_FILE		"Linked %s to %s\n"

#define	TMP_INITDEFSYSLOC	"/tmp/.init.defSysLoc"
#define	TMP_DEFSYSLOC		"/tmp/.defSysLoc"

/*
 * Definitions for ZFS pool
 */
#define	ROOTPOOL_NAME		"rpool"
#define	ROOTPOOL_SNAPSHOT	ROOTPOOL_NAME "@install"

/*
 * Initial BE name
 */
#define	INIT_BE_NAME		"preview2"

/*
 * Default file systems
 */
#define	ZFS_FS_NUM		1
#define	ZFS_SHARED_FS_NUM	2

/*
 * Signature for the Install callbacks
 */
#define	PROGRESS_STATUS			"<progressStatus"
#define	TARGET_INSTANTIATION_STATUS	"<targetInstantiationStatus"
#define	POST_INSTALL_STATUS		"<postInstallStatus"
#define	UPGRADE_SPACE_CHECK		"<UpgradeSpaceCheck"
#define	INSTALLER_FAILED		"<installerFailure"

/*
 * Debugging levels
 */
#define	OM_DBGLVL_EMERG	LS_DBG_LVL_EMERG
#define	OM_DBGLVL_ERR	LS_DBGLVL_ERR
#define	OM_DBGLVL_WARN	LS_DBGLVL_WARN
#define	OM_DBGLVL_INFO	LS_DBGLVL_INFO
#define	OM_DBGLVL_TRACE	LS_DBGLVL_TRACE

#define	MAX_TERM	256

int read_locale_file(FILE *fp, char *lang, char *lc_collate,
    char *lc_ctype, char *lc_messages, char *lc_monetary,
    char *lc_numeric, char *lc_time);

/* Data from the state file */
typedef struct {
	int configured;
	int bootparamed;
	int networked;
	int extnetwork;
	int autobound;
	int subnetted;
	int passwdset;
	int localeset;
	int security;
	int nfs4domain;
	char termtype[MAX_TERM+2];  /* I don't know why it's +2 */
} sys_config;


typedef struct disk_target {
	disk_info_t		dinfo;
		/* Disk Characteristics like size, type etc. */
	disk_parts_t		*dparts;
		/* fdisk partitions, valid only for X86 */
	disk_slices_t		*dslices;
		/* Slice information like size, mount point etc. */
	struct disk_target	*next;
} disk_target_t;

typedef struct {
	char		*locales;
	char		*diskname;
} initial_install_t;

typedef struct {
	char		*slice;
} upgrade_t;

typedef struct {
	om_install_type_t	operation;
	char			*profile_name;
	union {
		initial_install_t	install;
		upgrade_t		upgrade;
	} install_type;
} om_profile_t;

typedef struct {
	om_install_type_t	install_type;
	pid_t			pid;
} install_callback_t;

typedef struct {
	int			num_disks;
} td_callback_t;

typedef struct {
	char			*target;
} validate_callback_t;

typedef struct {
	union {
		install_callback_t	install;
		td_callback_t		td;
		validate_callback_t	valid;
	} cb_type;
	om_callback_t		cb;
} callback_args_t;

/*
 * Global variables
 */
extern	disk_target_t	*system_disks;
extern	disk_target_t	*committed_disk_target;
extern	upgrade_info_t	*solaris_instances;
extern	boolean_t	disk_discovery_done;
extern	boolean_t	disk_discovery_failed;
extern	int		disks_total;
extern	int		disks_found;
extern	int16_t		om_errno;
extern	om_handle_t	omh;
extern	boolean_t	whole_disk; /* slim install */
extern	char		*zfs_fs_names[ZFS_FS_NUM];
extern	char		*zfs_shared_fs_names[ZFS_SHARED_FS_NUM];

/*
 * private prototypes
 */

/*
 * om_misc.c
 */
void	om_set_error(int16_t value);
void	om_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...);
void	om_log_print(char *fmt, ...);

/*
 * disk_target.c
 */
void	*handle_disk_discovery(void *args);

/*
 * disk_util.c
 */
void		local_free_disk_info(disk_info_t *dinfo, boolean_t follow_link);
void		local_free_part_info(disk_parts_t *dpinfo);
void		local_free_slice_info(disk_slices_t *dsinfo);
void		local_free_upgrade_info(upgrade_info_t *uinfo);
int		just_the_disk_name(char *dst, char *src);
boolean_t	is_diskname_valid(char *diskname);
boolean_t	is_slicename_valid(char *slicename);
disk_target_t	*find_disk_by_name(char *diskname);
disk_parts_t	*find_partitions_by_disk(char *diskname);
disk_slices_t	*find_slices_by_disk(char *diskname);

/*
 * perform_install.c
 */
int create_pfinstall_profile(om_profile_t pf);
int call_pfinstall(om_install_type_t install_type,
    char *profile, om_callback_t cb);
void *run_pfinstall(void *arg);
void *handle_install_callback(void *arg);
int call_tools_install(om_callback_t);
void *run_tools_script(void *);
void *handle_tools_install_callback(void *);
int set_root_password(char *passwd);
int set_user_name_password(char *user, char *login, char *passwd);
int set_password_common(char *user, char *login, char *e_passwd);
int set_hostname_nodename(char *hostname);
boolean_t setup_profile_fdisk_entries(FILE *fp, char *diskname);
boolean_t setup_profile_filesys_entries(FILE *fp, char *diskname);
boolean_t setup_profile_locale_entries(FILE *fp, char *locales);
int16_t get_the_percentage(char *str);
int get_the_milestone(char *str);
om_install_type_t get_user_install_type(char *file);

/*
 * system_util.c
 */
boolean_t	is_system_sparc();
boolean_t	is_system_x86();
char		*create_dated_file(char *dir, char *filename);
boolean_t	copy_file(char *src, char *dest);
boolean_t	remove_and_relink(char *dir, char *src, char *dest);

/*
 * target_discovery.c
 */
int start_td_disk_discover(int *ndisks);
disk_target_t *get_td_disk_info_discover(int *ndisks, om_callback_t cb);
void get_td_disk_parts_discover(disk_target_t *disks, om_callback_t cb);
void get_td_disk_slices_discover(disk_target_t *disks, om_callback_t cb);
upgrade_info_t *get_td_solaris_instances(om_callback_t cb);
void send_discovery_complete_callback(om_callback_t cb);
om_disk_type_t ctype_to_disktype_enum(char *str);
disk_target_t	*enumerate_next_disk();
upgrade_info_t  *enumerate_next_instance();
disk_parts_t	*enumerate_partitions(char *disk_name);
disk_slices_t	*enumerate_slices(char *disk_name);
disk_parts_t	*sort_partitions_by_offset(disk_parts_t *dp_ptr, int num);
om_disk_type_t ctype_to_disktype_enum(char *str);
om_upgrade_message_t convert_td_value_to_om_upgrade_message(uint32_t *value);

/*
 * upgrade_target.c
 */
upgrade_info_t *copy_one_upgrade_target(upgrade_info_t *ui);

#ifdef __cplusplus
}
#endif

#endif	/* _ORCHESTRATOR_PRIVATE_H */
