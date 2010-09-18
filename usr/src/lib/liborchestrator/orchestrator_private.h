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
 * Copyright (c) 2007, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#ifndef _ORCHESTRATOR_PRIVATE_H
#define	_ORCHESTRATOR_PRIVATE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <orchestrator_api.h>
#include <ls_api.h>
#include <ti_api.h>

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

#define	LOCALHOST	"localhost"
#define	LOG_HOST	"loghost"
#define	LOOPBACK_IP	"127.0.0.1"
#define	HOSTS_DIR	"/etc/inet"
#define	HOSTS_TABLE	HOSTS_DIR "/hosts"

#define	OVERWRITE_STR	"OVERWRITE"

#define	BUFSIZE	80
#define	TEXT_DOMAIN	"SUNW_INSTALL_LIBORCHESTRATOR"
#define	MAX_LINE_SIZE	256
#define	MAX_NUM_LANG	4096

#define	MAX_LOCALE	40

#define	BLOCKS_TO_MB	2048
#define	ONE_GB_TO_MB	1024
#define	ONE_MB_TO_KB	1024
#define	ONE_MB_TO_BYTE	(1024UL * 1024UL)
#define	MIN_SWAP_SIZE	512
#define	MAX_SWAP_SIZE	(32 * ONE_GB_TO_MB)
#define	MIN_DUMP_SIZE	256
#define	MAX_DUMP_SIZE	(16 * ONE_GB_TO_MB)
#define	OVERHEAD_MB	1024
#define	MAX_USABLE_DISK	(2048 * ONE_GB_TO_MB - 1)

/*
 * Minimum amount of physical memory, which is required
 * for allowing swap to be optional. If system has less
 * memory available, installer might hang. Swap is mandatory
 * in that case.
 * Swap is optional on systems with at least 2GB memory
 * installed. We check for less, since part of memory
 * can be dedicated to other consumers (e.g. graphics card).
 */
#define	SWAP_MIN_MEMORY_SIZE	2000

/*
 * Minimum amount of physical memory needed to create a zvol
 * swap device instead of a vtoc slice swap device.  On systems
 * with less than this amount, instantiating a zpool and then
 * creating the swap zvol sometimes hangs/crashes the system
 * hence for this extreme low memory condition, we fall back
 * to creating a vtoc disk slice for swap.  This value is
 * ancillary to the SWAP_MIN_MEMORY_SIZE value, and hence
 * should always be less than that value.
 */
#define	SWAP_MIN_MEMORY_SIZE_CREATE_SLICE	700

#define	streq(a, b) (strcmp((a), (b)) == 0)

#define	SPARC_ARCH	"sparc"
#define	X86_ARCH	"i386"
#define	ALLDISKS	"all"

#define	ROOT_FS			"/"
#define	INSTALLED_ROOT_DIR	"/a"
#define	HOMEDIR_CREATE_FAILED	"mkdir of %s returned error %d\n"
#define	BAD_DISK_SLICE		"Bad disk slice %s\n"
#define	NSI_CHDIR_FAILED	"chdir to %s failed with error %d\n"
#define	NSI_CREATE_FILE_FAILED	"Creating %s failed with error %d\n"
#define	NSI_CREATE_SLINK_FAILED	"Creating symlink of %s failed with error %d\n"
#define	NSI_GETCWD_FAILED	"getcwd() failed with error %d\n"
#define	NSI_TIME_FAILED		"time() failed with error %d\n"
#define	NSI_TRANSFER_FAILED	"Transfer failed with error %d\n"
#define	NSI_MOVE_FILE		"Moved %s to %s\n"
#define	NSI_LINK_FILE		"Linked %s to %s\n"

#define	TMP_INITDEFSYSLOC	"/tmp/.init.defSysLoc"
#define	TMP_DEFSYSLOC		"/tmp/.defSysLoc"

/*
 * Definitions for ZFS pool
 */
#define	ROOTPOOL_NAME		"rpool"
#define	ROOT_DATASET_NAME	ROOTPOOL_NAME
#define	INSTALL_SNAPSHOT_NAME	"@install"
#define	INSTALL_SNAPSHOT	"install"

/*
 * Initial BE name
 */
#define	INIT_BE_NAME		"solaris"

/*
 * Default file systems
 */
#define	ZFS_FS_NUM		1
#define	ZFS_SHARED_FS_NUM	3

/*
 * file containing image information
 */
#define	IMAGE_INFO_FILE_NAME		"/.cdrom/.image_info"
#define	IMAGE_INFO_TOTAL_SIZE		"IMAGE_SIZE"
#define	IMAGE_INFO_COMPRESSION_RATIO	"COMPRESSION_RATIO"
#define	IMAGE_INFO_COMPRESSION_TYPE	"COMPRESSION_TYPE"
#define	IMAGE_INFO_LINE_MAXLN		1000

/* If following file exists, we are in Automated Installer environment */
#define	AUTOMATED_INSTALLER_MARK	"/.autoinstall"

/* Path to live CD root archive */
#define	ARCHIVE_PATH			"/.cdrom/platform/i86pc/%s/boot_archive"

/*
 * Debugging levels
 */
#define	OM_DBGLVL_EMERG	LS_DBG_LVL_EMERG
#define	OM_DBGLVL_ERR	LS_DBGLVL_ERR
#define	OM_DBGLVL_WARN	LS_DBGLVL_WARN
#define	OM_DBGLVL_INFO	LS_DBGLVL_INFO

#define	MAX_TERM	256

#define	limit_min_max(v, min, max)	\
	((v) < (min) ? (min) : (v) > (max) ? (max) : (v))

/*
 * Following two macros can be only used when passing partition geometry
 * information from GUI (uses MiB) to orchestrator (works with sectors)
 * (om_set_part_sec_size_from_mb) or from orchestrator to GUI
 * (om_set_part_mb_size_from_sec).
 *
 * They shouldn't be used for other purposes, since they
 * might cause rounding issues.
 */

#define	om_set_part_mb_size_from_sec(part)	\
    part->partition_size = part->partition_size_sec/BLOCKS_TO_MB

#define	om_set_part_sec_size_from_mb(part)	\
    part->partition_size_sec = part->partition_size*BLOCKS_TO_MB

/*
 * is partition a logical partition?
 */
#define	IS_LOG_PAR(num) ((num) > FD_NUMPART)

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

typedef struct {
	boolean_t	initialized;
	uint64_t	image_size;
	float		compress_ratio;
	char		*compress_type;
} image_info_t;

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
extern	boolean_t	create_swap_and_dump;
extern	boolean_t	create_swap_slice;
extern	int16_t		om_errno;
extern	om_handle_t	omh;
extern	boolean_t	whole_disk; /* slim install */

/*
 * private prototypes
 */

/*
 * om_misc.c
 */
void	om_set_error(int16_t value);
void	om_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...);
void	om_log_print(char *fmt, ...);
void	om_log_std(ls_stdouterr_t stdouterr, const char *fmt, ...);

/*
 * disk_target.c
 */
void	*handle_disk_discovery(void *args);
int	allocate_target_disk_info(const disk_info_t *);
void	free_target_disk_info(void);
char	*part_size_or_max(uint64_t partition_size);

/*
 * disk_parts.c
 */
int	om_set_fdisk_target_attrs(nvlist_t *, char *);
boolean_t is_used_partition(partition_info_t *);

/*
 * disk_slices.c
 */
int	om_set_vtoc_target_attrs(nvlist_t *, char *);

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
 * perform_slim_install.c
 */
void *handle_install_callback(void *arg);
int set_root_password(char *passwd);
int set_user_name_password(char *user, char *login, char *passwd);
int set_password_common(char *user, char *login, char *e_passwd);
int set_hostname_nodename(char *hostname);
int16_t get_the_percentage(char *str);
om_install_type_t get_user_install_type(char *file);
uint64_t calc_required_swap_size(void);

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
void		sort_partitions_by_offset(disk_parts_t *dp_ptr, int num);
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
