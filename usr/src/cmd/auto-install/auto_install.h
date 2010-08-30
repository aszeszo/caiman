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
 * Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
 */

#ifndef _AUTO_INSTALL_H
#define	_AUTO_INSTALL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <Python.h>
#include <sys/param.h>
#include "td_lib.h"
#include "td_api.h"
#include "orchestrator_api.h"
#include "ti_api.h"
#include "transfermod.h"
#include "ls_api.h"

/* AI engine exit codes */
#define	AI_EXIT_SUCCESS		0	/* success - control passed to user */
#define	AI_EXIT_AUTO_REBOOT	64	/* success - auto reboot enabled */
#define	AI_EXIT_FAILURE		1	/* general failure */
#define	AI_EXIT_FAILURE_AIM	2	/* failure-invalid manifest provided */

#define	AUTO_INSTALL_SUCCESS	0
#define	AUTO_INSTALL_EMPTY_LIST	1	/* list of packages is empty */
#define	AUTO_INSTALL_FAILURE	-1
#define	AUTO_TD_SUCCESS		0
#define	AUTO_TD_FAILURE		-1

#define	INSTALLED_ROOT_DIR	"/a"
#define	AUTO_UNKNOWN_STRING	"unknown"
#define	AUTO_DBGLVL_INFO	LS_DBGLVL_INFO
#define	AUTO_DBGLVL_WARN	LS_DBGLVL_WARN
#define	AUTO_DBGLVL_ERR		LS_DBGLVL_ERR

#define	AUTO_VALID_MANIFEST	0
#define	AUTO_INVALID_MANIFEST	-1
#define	SC_MANIFEST_BEGIN_MARKER	"<?xml version='1.0'?>"
#define	SC_MANIFEST_END_MARKER		"</service_bundle>"
#define	SC_EMBEDDED_BEGIN_MARKER	"<sc_embedded_manifest"
#define	SC_EMBEDDED_END_MARKER		"</sc_embedded_manifest>"
#define	SC_PROPVAL_MARKER		"<propval"
#define	AUTO_PROPERTY_ROOTPASS		"rootpass"
#define	AUTO_PROPERTY_TIMEZONE		"timezone"
#define	AUTO_PROPERTY_HOSTNAME		"hostname"
#define	KEYWORD_VALUE			"value"
#define	KEYWORD_SIZE		256
#define	VALUE_SIZE		256
#define	AUTO_MAX_ACTION_LEN	32	/* delete, create, preserve... */
#define	MAX_SHELLCMD_LEN	2048

/*
 * File that lists which packages need to be installed
 */
#define	AUTO_INSTALL_PKG_LIST_FILE	"/tmp/install.pkg.list"
/*
 * File that lists which packages will be removed
 * from installed system
 */
#define	AUTO_REMOVE_PKG_LIST_FILE	"/tmp/remove.pkg.list"

#define	AI_MANIFEST_FILE	"/tmp/ai.xml"
#define	AI_MANIFEST_SCHEMA	"/tmp/ai.dtd"
#define	SC_MANIFEST_FILE	"/tmp/sc_manifest.xml"

/* Script for converting legacy System Configuration manifest to new format */
#define	SC_CONVERSION_SCRIPT	"/usr/lib/install/sc_conv.ksh"

#define	TEXT_DOMAIN		"SUNW_INSTALL_AUTOINSTALL"

#define	CONVERT_UNITS_TO_TEXT(units) \
	((units) == AI_SIZE_UNITS_MEGABYTES ? "megabytes": \
	((units) == AI_SIZE_UNITS_GIGABYTES ? "gigabytes": \
	((units) == AI_SIZE_UNITS_TERABYTES ? "terabytes": \
	((units) == AI_SIZE_UNITS_SECTORS ? "sectors": \
	"(unknown)"))))

#define MB_TO_SECTORS	((uint64_t)2048)
#define GB_TO_MB	((uint64_t)1024)
#define TB_TO_GB	((uint64_t)1024)


/*
 * DTD schema nodepaths - see ai.dtd
 */
#define	AIM_TARGET_DISK_KEYWORD "auto_install/ai_instance/target/target_device/disk/disk_keyword/key"
#define	AIM_TARGET_DEVICE_NAME "auto_install/ai_instance/target/target_device/disk/disk_name[name_type='ctd']/name"
#define	AIM_TARGET_DEVICE_BOOT_DISK "boot_disk"
#define	AIM_TARGET_DEVICE_SELECT_VOLUME_NAME \
	"auto_install/ai_instance/target/target_device/disk/disk_name[name_type='volid']/name"
#define	AIM_TARGET_DEVICE_SELECT_DEVICE_ID \
	"auto_install/ai_instance/target/target_device/disk/disk_name[name_type='devid']/name"
#define	AIM_TARGET_DEVICE_SELECT_DEVICE_PATH \
	"auto_install/ai_instance/target/target_device/disk/disk_name[name_type='devpath']/name"
#define	AIM_TARGET_DEVICE_TYPE "auto_install/ai_instance/target/target_device/disk/disk_prop/dev_type"
#define	AIM_TARGET_DEVICE_SIZE	\
	"auto_install/ai_instance/target/target_device/disk/disk_prop/dev_size"
#define	AIM_TARGET_DEVICE_VENDOR	\
	"auto_install/ai_instance/target/target_device/disk/disk_prop/dev_vendor"
#define	AIM_TARGET_DEVICE_USE_SOLARIS_PARTITION	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/action"
#define	AIM_TARGET_DEVICE_INSTALL_SLICE_NUMBER \
	"auto_install/ai_instance/target/target_device/disk/slice[is_root='true']/name"
#define	AIM_TARGET_DEVICE_ISCSI_TARGET_NAME \
	"auto_install/ai_instance/target/target_device/disk/iscsi/name"
#define	AIM_TARGET_DEVICE_ISCSI_TARGET_IP \
	"auto_install/ai_instance/target/target_device/disk/iscsi/ip"
#define	AIM_TARGET_DEVICE_ISCSI_TARGET_LUN \
	"auto_install/ai_instance/target/target_device/disk/iscsi/target_lun"
#define	AIM_TARGET_DEVICE_ISCSI_TARGET_PORT \
	"auto_install/ai_instance/target/target_device/disk/iscsi/target_port"
#define	AIM_TARGET_DEVICE_ISCSI_PARAMETER_SOURCE \
	"auto_install/ai_instance/target/target_device/disk/iscsi/source"
#define	AIM_SWAP_SIZE	\
	"auto_install/ai_instance/target/target_device/swap/zvol/size/val"
#define	AIM_DUMP_SIZE	\
	"auto_install/ai_instance/target/target_device/dump/zvol/size/val"

#define	AIM_PARTITION_ACTIONS	\
	"auto_install/ai_instance/target/target_device/disk/partition/action"
#define	AIM_NUMBERED_PARTITIONS	\
	"auto_install/ai_instance/target/target_device/disk/partition/name"
#define	AIM_NUMBERED_PARTITION_NUMBER	\
	"auto_install/ai_instance/target/target_device/disk/partition[name=\"%s\":action=\"%s\"]/name"
#define	AIM_NUMBERED_PARTITION_ACTION	\
	"auto_install/ai_instance/target/target_device/disk/partition[name=\"%s\":action=\"%s\"]/action"
#define	AIM_NUMBERED_PARTITION_START_SECTOR	\
	"auto_install/ai_instance/target/target_device/disk/partition[name=\"%s\":action=\"%s\"]/size/start_sector"
#define	AIM_NUMBERED_PARTITION_SIZE	\
	"auto_install/ai_instance/target/target_device/disk/partition[name=\"%s\":action=\"%s\"]/size/val"
#define	AIM_NUMBERED_PARTITION_TYPE	\
	"auto_install/ai_instance/target/target_device/disk/partition[name=\"%s\":action=\"%s\"]/part_type"

#define	AIM_USE_EXISTING_PARTITIONS	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/action"
#define	AIM_UNNUMBERED_PARTITION_NUMBER	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/name"
#define	AIM_UNNUMBERED_PARTITION_ACTION	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/action"
#define	AIM_UNNUMBERED_PARTITION_START_SECTOR	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/size/start_sector"
#define	AIM_UNNUMBERED_PARTITION_SIZE	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/size/val"
#define	AIM_UNNUMBERED_PARTITION_TYPE	\
	"auto_install/ai_instance/target/target_device/disk/partition[action='use_existing']/part_type"

#define	AIM_SLICE_NUMBER "auto_install/ai_instance/target/target_device/disk/slice/name"
#define	AIM_SLICE_ACTION "auto_install/ai_instance/target/target_device/disk/slice/action"
#define	AIM_SLICE_SIZE "auto_install/ai_instance/target/target_device/disk/slice[name=\"%s\":action=\"%s\"]/size/val"
#define	AIM_SLICE_ON_EXISTING	\
	"auto_install/ai_instance/target/target_device/disk/slice[name=\"%s\":action=\"%s\"]/force"
#define	AIM_AUTO_REBOOT	"auto_install/ai_instance/auto_reboot"

#define	AIM_PROXY_URL "auto_install/ai_instance/http_proxy"

#define	AIM_PACKAGE_INSTALL_NAME "auto_install/ai_instance/software/software_data[action='install']/name"

#define	AIM_PACKAGE_REMOVE_NAME "auto_install/ai_instance/software/software_data[action='uninstall']/name"

/*
 * Primary and secondary publishers
 */
#define	AIM_IPS_PUBLISHER_URL	\
	"auto_install/ai_instance/software/source/publisher/origin/name"
#define	AIM_FALLBACK_PUBLISHER_URL	"http://pkg.opensolaris.org/release"
#define	AIM_FALLBACK_PUBLISHER_NAME	"opensolaris.org"

/*
 * Find publisher name and mirror based on url
 */
#define	AIM_ADD_URL_PUBLISHER_NAME \
	"auto_install/ai_instance/software/source/publisher[origin/name=\"%s\"]/name"
#define	AIM_ADD_URL_PUBLISHER_MIRROR \
	"auto_install/ai_instance/software/source/publisher[origin/name=\"%s\"]/mirror/name"

/* type of package list to be obtained from manifest */
typedef enum {
	AI_PACKAGE_LIST_INSTALL,
	AI_PACKAGE_LIST_REMOVE
} auto_package_list_type_t;

/* hardcoded lists of packages for testing purposes */
#define	AI_TEST_PACKAGE_LIST_INSTALL	\
	"SUNWcsd\nSUNWcs\nbabel_install\nentire\n"
#define	AI_TEST_PACKAGE_LIST_REMOVE	"babel_install\n"

/* size units can be user-defined */
typedef enum {
	AI_SIZE_UNITS_MEGABYTES = 0,
	AI_SIZE_UNITS_SECTORS,
	AI_SIZE_UNITS_GIGABYTES,
	AI_SIZE_UNITS_TERABYTES
} auto_size_units_t;

/* define source of iSCSI parameters */
typedef enum {
	AI_ISCSI_PARM_SRC_MANIFEST = 0,
	AI_ISCSI_PARM_SRC_DHCP
} iscsi_parm_src_t;

/*
 * information needed to mount iSCSI boot target during installation
 */
typedef struct {
	char		name[INSTISCSI_MAX_ISCSI_NAME_LEN + 1];
	char		ip[INSTISCSI_IP_ADDRESS_LEN + 1];
	uint32_t	port;
	char		lun[INSTISCSI_MAX_LUN_LEN + 1];
	iscsi_parm_src_t parm_src;
} iscsi_info_t;

typedef struct {
	/*
	 * disk criteria for selection of target disk
	 */
	char		diskkeyword[10];		/* 'boot_disk' */
	char		diskname[MAXNAMELEN];
	char		disktype[MAXNAMELEN];
	char		diskvendor[MAXNAMELEN];
	char		diskvolname[MAXNAMELEN];
	char		diskdevid[MAXNAMELEN];
	char		diskdevicepath[MAXPATHLEN];
	uint64_t	disksize;
#ifndef	__sparc
	char		diskusepart[6];		/* 'true' or 'false' */
#endif
	iscsi_info_t	diskiscsi;		/* iSCSI target parameters */
	/*
	 * other data related to disk target
	 */
	uint8_t		install_slice_number;	/* install Solaris here */
} auto_disk_info;

typedef struct {
	char		partition_action[AUTO_MAX_ACTION_LEN];
	int		partition_number;
	uint64_t	partition_start_sector;
	uint64_t	partition_size;
	int		partition_type;
	auto_size_units_t	partition_size_units;
	boolean_t	partition_is_logical;
} auto_partition_info;

typedef struct {
	char		slice_action[AUTO_MAX_ACTION_LEN];
	int		slice_number;
	uint64_t	slice_size;
	auto_size_units_t	slice_size_units;
	om_on_existing_t	on_existing; /* action to take if it exists */
} auto_slice_info;

typedef struct auto_mirror_repo {
	char			*mirror_url;
	struct auto_mirror_repo	*next_mirror;
} auto_mirror_repo_t;

typedef struct auto_repo_info {
	char			*publisher;
	char			*url;
	auto_mirror_repo_t	*mirror_repo; /* point to the list of mirrors */
	struct auto_repo_info	*next_repo; /* Point to the next repo */
} auto_repo_info_t;

typedef struct {
	int32_t		swap_size;	/* Swap Size in MB */
} auto_swap_device_info;

typedef struct {
	int32_t		dump_size;	/* Dump Size in MB */
} auto_dump_device_info;

typedef struct {
	char		*timezone;
	char		*hostname;
} auto_sc_params;

typedef struct {
	uint32_t	size;
	char		diskname[MAXNAMELEN];
	boolean_t	whole_disk;
} install_params;

void	auto_log_print(char *fmt, ...);
void	auto_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...);
void	auto_debug_dump_file(ls_dbglvl_t dbg_lvl, char *filename);

int	auto_target_discovery(void);
int	auto_select_install_target(char **diskname, auto_disk_info *adi);

int	auto_parse_sc_manifest(char *profile_file, auto_sc_params *sp);

int	ai_create_manifest_image(char *filename);
int	ai_setup_manifest_image();
void	ai_teardown_manifest_state();
char	**ai_get_manifest_values(char *path, int *len);
void	ai_free_manifest_values(char **value_list);
int 	ai_get_manifest_disk_info(auto_disk_info *);
int 	ai_get_manifest_swap_device_info(auto_swap_device_info *adsi);
int 	ai_get_manifest_dump_device_info(auto_dump_device_info *addi);
auto_partition_info *ai_get_manifest_partition_info(int *);
auto_slice_info *ai_get_manifest_slice_info(int *);
char	*ai_get_manifest_ipsrepo_url(void);
char	*ai_get_manifest_ipsrepo_authname(void);
char	*ai_get_manifest_ipsrepo_mirror(void);
char	*ai_get_manifest_ipsrepo_addl_url(void);
char	*ai_get_manifest_ipsrepo_addl_authname(void);
char	*ai_get_manifest_ipsrepo_addl_mirror(void);
auto_repo_info_t *ai_get_default_repo_info(void);
auto_repo_info_t *ai_get_additional_repo_info(void);
char	*ai_get_manifest_http_proxy(void);
char	**ai_get_manifest_packages(int *num_packages_p, char *pkg_list_tag_p);
char	*ai_get_manifest_element_value(char *element);
void	free_repo_info_list(auto_repo_info_t *repo);
void	free_repo_mirror_list(auto_mirror_repo_t *mirror);

PyObject *ai_create_manifestserv(char *filename);
int	ai_setup_manifestserv(PyObject *server_obj);
void	ai_destroy_manifestserv(PyObject *server_obj);
char	**ai_lookup_manifest_values(PyObject *server_obj, char *path, int *len);
void	ai_free_manifest_value_list(char **value_list);

int	ai_du_get_and_install(char *install_root, boolean_t honor_noinstall,
	    boolean_t update_boot_archive);
int	ai_du_install(char *install_root, boolean_t honor_noinstall,
	    boolean_t update_boot_archive);

int	mount_iscsi_target_if_requested(auto_disk_info *, char *, int);

#ifdef __cplusplus
}
#endif

#endif /* _AUTO_INSTALL_H */
