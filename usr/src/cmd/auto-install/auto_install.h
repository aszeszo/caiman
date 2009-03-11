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

#ifndef _AUTO_INSTALL_H
#define	_AUTO_INSTALL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <Python.h>
#include "orchestrator_api.h"
#include "ti_api.h"
#include "transfermod.h"
#include "ls_api.h"
#include "td_lib.h"

/* AI engine exit codes */
#define	AI_EXIT_SUCCESS		0	/* success - control passed to user */
#define	AI_EXIT_AUTO_REBOOT	64	/* success - auto reboot enabled */
#define	AI_EXIT_FAILURE		1	/* failure */

#define	AUTO_INSTALL_SUCCESS	0
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
#define	AI_MANIFEST_BEGIN_MARKER	"<ai_manifest"
#define	AI_MANIFEST_END_MARKER		"</ai_manifest>"
#define	SC_MANIFEST_BEGIN_MARKER	"<?xml version='1.0'?>"
#define	SC_MANIFEST_END_MARKER		"</service_bundle>"
#define	SC_PROPVAL_MARKER		"<propval"
#define	AUTO_PROPERTY_USERNAME		"username"
#define	AUTO_PROPERTY_USERPASS		"userpass"
#define	AUTO_PROPERTY_USERDESC		"description"
#define	AUTO_PROPERTY_ROOTPASS		"rootpass"
#define	AUTO_PROPERTY_TIMEZONE		"timezone"
#define	KEYWORD_VALUE			"value"
#define	KEYWORD_SIZE	256
#define	VALUE_SIZE	256

/*
 * File that lists which packages need to be installed
 */
#define	AUTO_PKG_LIST		"/tmp/install.pkg.list"
#define	AI_MANIFEST_FILE	"/tmp/ai_manifest.xml"
#define	SC_MANIFEST_FILE	"/tmp/sc_manifest.xml"

#define	TEXT_DOMAIN		"SUNW_INSTALL_AUTOINSTALL"

#define	CONVERT_UNITS_TO_TEXT(units) \
	((units) == AI_SIZE_UNITS_MEGABYTES ? "megabytes": \
	((units) == AI_SIZE_UNITS_GIGABYTES ? "gigabytes": \
	((units) == AI_SIZE_UNITS_TERABYTES ? "terabytes": \
	((units) == AI_SIZE_UNITS_SECTORS ? "sectors": \
	"(unknown)"))))

/*
 * RNG schema definitions - see ai_manifest.rng
 */
#define	AIM_TARGET_DEVICE_NAME "ai_manifest/ai_target_device/target_device_name"
#define	AIM_TARGET_DEVICE_TYPE "ai_manifest/ai_target_device/target_device_type"
#define	AIM_TARGET_DEVICE_SIZE	\
	"ai_manifest/ai_target_device/target_device_size"
#define	AIM_TARGET_DEVICE_VENDOR	\
	"ai_manifest/ai_target_device/target_device_vendor"
#define	AIM_TARGET_DEVICE_USE_SOLARIS_PARTITION	\
	"ai_manifest/ai_target_device/target_device_use_solaris_partition"
#define	AIM_TARGET_DEVICE_OVERWRITE_ROOT_ZFS_POOL \
	"ai_manifest/ai_target_device/target_device_overwrite_root_zfs_pool"
#define	AIM_TARGET_DEVICE_INSTALL_SLICE_NUMBER \
	"ai_manifest/ai_target_device/target_device_install_slice_number"

#define	AIM_PARTITION_ACTION	\
	"ai_manifest/ai_device_partitioning/partition_action"
#define	AIM_PARTITION_NUMBER	\
	"ai_manifest/ai_device_partitioning/partition_number"
#define	AIM_PARTITION_START_SECTOR	\
	"ai_manifest/ai_device_partitioning/partition_start_sector"
#define	AIM_PARTITION_SIZE	\
	"ai_manifest/ai_device_partitioning/partition_size"
#define	AIM_PARTITION_TYPE	\
	"ai_manifest/ai_device_partitioning/partition_type"
#define	AIM_PARTITION_SIZE_UNITS	\
	"ai_manifest/ai_device_partitioning/partition_size_units"

#define	AIM_SLICE_ACTION "ai_manifest/ai_device_vtoc_slices/slice_action"
#define	AIM_SLICE_NUMBER "ai_manifest/ai_device_vtoc_slices/slice_number"
#define	AIM_SLICE_SIZE "ai_manifest/ai_device_vtoc_slices/slice_size"
#define	AIM_SLICE_SIZE_UNITS	\
	"ai_manifest/ai_device_vtoc_slices/slice_size_units"
#define	AIM_AUTO_REBOOT	"ai_manifest/ai_auto_reboot"

#define	AIM_PROXY_URL "ai_manifest/ai_http_proxy/url"
#define	AIM_PACKAGE_NAME "ai_manifest/ai_packages/package_name"

#define	AIM_IPS_AUTH_NAME	\
	"ai_manifest/ai_pkg_repo_default_authority/main/authname"
#define	AIM_IPS_AUTH_URL	\
	"ai_manifest/ai_pkg_repo_default_authority/main/url"
#define	AIM_IPS_AUTH_MIRROR	\
	"ai_manifest/ai_pkg_repo_default_authority/mirror/url"
#define	AIM_IPS_ADDL_AUTH_URL	\
	"ai_manifest/ai_pkg_repo_addl_authority/main/url"
#define	AIM_IPS_ADDL_AUTH_NAME	\
	"ai_manifest/ai_pkg_repo_addl_authority/main/authname"
#define	AIM_IPS_ADDL_AUTH_MIRROR	\
	"ai_manifest/ai_pkg_repo_addl_authority/mirror/url"

/* size units can be user-defined */
typedef enum {
	AI_SIZE_UNITS_MEGABYTES = 0,
	AI_SIZE_UNITS_SECTORS,
	AI_SIZE_UNITS_GIGABYTES,
	AI_SIZE_UNITS_TERABYTES
} auto_size_units_t;

typedef struct {
	/*
	 * disk criteria for selection of target disk
	 */
	char		diskname[MAXNAMELEN];
	char		disktype[MAXNAMELEN];
	char		diskvendor[MAXNAMELEN];
	uint64_t	disksize;
#ifndef	__sparc
	char		diskusepart[6];		/* 'true' or 'false' */
#endif
	char 		diskoverwrite_rpool[6];	/* 'true' or 'false' */
	/*
	 * other data related to disk target
	 */
	uint8_t		install_slice_number;	/* install Solaris here */
} auto_disk_info;

typedef struct {
	char		partition_action[MAXNAMELEN];
	int		partition_number;
	uint64_t	partition_start_sector;
	uint64_t	partition_size;
	int		partition_type;
	auto_size_units_t	partition_size_units;
} auto_partition_info;

typedef struct {
	char		slice_action[MAXNAMELEN];
	int		slice_number;
	uint64_t	slice_size;
	auto_size_units_t	slice_size_units;
} auto_slice_info;

typedef struct {
	char		*username;
	char		*userpass;
	char		*userdesc;
	char		*rootpass;
	char		*timezone;
} auto_sc_params;

typedef struct {
	uint32_t	size;
	char		diskname[MAXNAMELEN];
	boolean_t	whole_disk;
} install_params;

void	auto_log_print(char *fmt, ...);
void	auto_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...);

int	auto_validate_target(char **diskname, install_params *iparam,
	    auto_disk_info *adi);

int	auto_parse_sc_manifest(char *profile_file, auto_sc_params *sp);

int	ai_validate_and_setup_manifest(char *filename);
void	ai_teardown_manifest_state();
void 	ai_get_manifest_disk_info(auto_disk_info *);
auto_partition_info *ai_get_manifest_partition_info(int *);
auto_slice_info *ai_get_manifest_slice_info(int *);
char	*ai_get_manifest_ipsrepo_url(void);
char	*ai_get_manifest_ipsrepo_authname(void);
char	*ai_get_manifest_ipsrepo_mirror(void);
char	*ai_get_manifest_ipsrepo_addl_url(void);
char	*ai_get_manifest_ipsrepo_addl_authname(void);
char	*ai_get_manifest_ipsrepo_addl_mirror(void);
char	*ai_get_manifest_http_proxy(void);
char	**ai_get_manifest_packages(int *num_packages);
char	*ai_get_manifest_element_value(char *element);

PyObject *ai_create_manifestserv(char *filename);
void	ai_destroy_manifestserv(PyObject *server_obj);
char	**ai_lookup_manifest_values(PyObject *server_obj, char *path, int *len);


#ifdef __cplusplus
}
#endif

#endif /* _AUTO_INSTALL_H */
