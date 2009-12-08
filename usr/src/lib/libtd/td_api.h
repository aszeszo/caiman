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

#ifndef _TD_API_H
#define	_TD_API_H

/*
 * This header file is for users of the Target Discovery library
 */

#include <libnvpair.h>
#include <sys/types.h>

#ifdef __cplusplus
extern "C" {
#endif

/* type definitions */

typedef uint64_t td_handle_t;

typedef enum {
	TD_E_SUCCESS = 0,	/* command succeeded */
	TD_E_END,		/* end of enumerated list */
	TD_E_MEMORY,		/* memory allocation failure */
	TD_E_NO_DEVICE,		/* no device for specified name */
	TD_E_NO_OBJECT,		/* specified object does not exist */
	TD_E_INVALID_ARG,	/* invalid argument passed */
	TD_E_THREAD_CREATE,	/* no resources for thread */
	TD_E_SEMAPHORE,		/* error on semaphore */
	TD_E_MNTTAB,		/* error on open of mnttab */
	TD_E_NOT_FOUND,		/* iSCSI-specific */
	TD_E_LUN_NOT_FOUND,	/* iSCSI target exists, but LUN not found */
	TD_E_WRONG_LUN,		/* LUN not found, non-specified LUNs found */
	TD_E_UNKNOWN_IMA_ERROR,	/* unknown error in IMA layer */
	TD_E_INVALID_PARAMETER,	/* invalid iSCSI parameter */
	TD_E_LUN_BUSY		/* iSCSI LUN busy */
} td_errno_t;

/* object types */
typedef enum {
	TD_OT_DISK = 0,		/* writeable disk - install candidate */
	TD_OT_PARTITION,	/* disk partition */
	TD_OT_SLICE,		/* ufs file system slice */
	TD_OT_OS		/* Solaris OS instance/BE */
} td_object_type_t;

#define	TD_IOCTL_TIMEOUT 10 /* seconds to timeout blocking ioctls */

/* nv attribute names for disk */

#define	TD_DISK_ATTR_NAME	"ddm_disk_name"
#define	TD_DISK_ATTR_BLOCKSIZE	"ddm_disk_block_size"
#define	TD_DISK_ATTR_SIZE	"ddm_disk_size"
#define	TD_DISK_ATTR_MTYPE	"ddm_disk_mtype"
#define	TD_DISK_ATTR_CTYPE	"ddm_disk_ctype"
#define	TD_DISK_ATTR_BTYPE	"ddm_disk_btype"
#define	TD_DISK_ATTR_STATUS	"ddm_disk_status"
#define	TD_DISK_ATTR_REMOVABLE	"ddm_disk_removable"
#define	TD_DISK_ATTR_MLOADED	"ddm_disk_loaded"
#define	TD_DISK_ATTR_VENDOR	"ddm_disk_vendor_id"
#define	TD_DISK_ATTR_PRODUCT	"ddm_disk_product_id"
#define	TD_DISK_ATTR_DEVID	"ddm_disk_dev_id"
#define	TD_DISK_ATTR_CURRBOOT	"ddm_disk_currboot"
#define	TD_DISK_ATTR_NHEADS	"ddm_disk_nheads"
#define	TD_DISK_ATTR_NSECTORS	"ddm_disk_nsectors"

/*
 * specifies, which label type disk contains
 * this is handled as bitmap, since there
 * might be several labels on one disk
 */

#define	TD_DISK_ATTR_LABEL	"ddm_disk_label"

typedef enum {
	TD_DISK_LABEL_NONE	= 0,
	TD_DISK_LABEL_VTOC	= 0x01,
	TD_DISK_LABEL_GPT	= 0x02,
	TD_DISK_LABEL_FDISK	= 0x04
} td_disk_label_t;

/* drive media types - TD_DISK_ATTR_MTYPE */

typedef enum {
	TD_MT_UNKNOWN = 0,
	TD_MT_FIXED,
	TD_MT_FLOPPY,
	TD_MT_CDROM,
	TD_MT_ZIP,
	TD_MT_JAZ,
	TD_MT_CDR,
	TD_MT_CDRW,
	TD_MT_DVDROM,
	TD_MT_DVDR,
	TD_MT_DVDRAM,
	TD_MT_MO_ERASABLE,
	TD_MT_MO_WRITEONCE,
	TD_MT_AS_MO
} ddm_media_type_t;

/* specifies status of drive - TD_DISK_ATTR_STATUS */

typedef enum {
	TD_DISK_DOWN = 0,
	TD_DISK_UP = 1
} ddm_drive_status_t;

/* nv attribute names for partition */

#define	TD_PART_ATTR_NAME	"ddm_part_name"
#define	TD_PART_ATTR_BOOTID	"ddm_part_bootid"
#define	TD_PART_ATTR_TYPE	"ddm_part_type"
#define	TD_PART_ATTR_START	"ddm_part_start"
#define	TD_PART_ATTR_SIZE	"ddm_part_size"

/*
 * specifies, what particular partition actually
 * contains - only "linux swap" is detected
 * for now
 */

#define	TD_PART_ATTR_CONTENT	"ddm_part_content"

/*
 * use TD_UPGRADE_FAIL to check byte array for OS upgrade failure reasons
 */
#define	TD_UPGRADE_FAIL(bitmap) (*((uint32_t *)&(bitmap)) != 0)

typedef enum {
	TD_PART_CONTENT_UNKNOWN	= 0,
	TD_PART_CONTENT_LSWAP	= 0x01
} td_part_content_t;

/* nv attribute names for slices */
#define	TD_SLICE_ATTR_NAME	"ddm_slice_name"
#define	TD_SLICE_ATTR_INDEX	"ddm_slice_index"
#define	TD_SLICE_ATTR_DEVT	"ddm_slice_devt"
#define	TD_SLICE_ATTR_LASTMNT	"ddm_slice_lastmnt"
#define	TD_SLICE_ATTR_START	"ddm_slice_start"
#define	TD_SLICE_ATTR_SIZE	"ddm_slice_size"
#define	TD_SLICE_ATTR_TAG	"ddm_slice_tag"
#define	TD_SLICE_ATTR_FLAG	"ddm_slice_flag"
#define	TD_SLICE_ATTR_INUSE	"ddm_slice_inuse"
#define	TD_SLICE_ATTR_MD_NAME	"ddm_slice_md_name"
#define	TD_SLICE_ATTR_MD_COMPS	"ddm_slice_md_comps"
#define	TD_SLICE_ATTR_DEVID	"ddm_slice_devid"

typedef enum {
	TD_SLICE_INUSE_NONE	= 0x00,
	TD_SLICE_INUSE_SVM	= 0x01
} td_slice_inuse_t;

/* nv attribute names for Solaris instances */
#define	TD_OS_ATTR_SLICE_NAME		"os_slice_name"
#define	TD_OS_ATTR_VERSION		"os_version"
#define	TD_OS_ATTR_VERSION_MINOR	"os_version_minor"
#define	TD_OS_ATTR_MD_NAME		"os_md_name"
#define	TD_OS_ATTR_BUILD_ID		"os_build_id"

/* nv iSCSI attribute names */
#define	TD_ISCSI_ATTR_DEVICE_NAME	"iscsi_device_name"
#define	TD_ISCSI_ATTR_NAME		"iscsi_name"
#define	TD_ISCSI_ATTR_IP		"iscsi_ip"
#define	TD_ISCSI_ATTR_PORT		"iscsi_port"
#define	TD_ISCSI_ATTR_LUN		"iscsi_lun"
#define	TD_ISCSI_ATTR_INITIATOR		"iscsi_initiator"
#define	TD_ISCSI_ATTR_CHAP_NAME		"iscsi_chap_name"
#define	TD_ISCSI_ATTR_CHAP_SECRET	"iscsi_chap_secret"

/* string array of SVM root mirror components */
#define	TD_OS_ATTR_MD_COMPS	"os_md_comps"

/*
 * byte array containing bitfields for upgrade failure reasons
 * parse with td_upgrade_fail_reasons
 */
#define	TD_OS_ATTR_NOT_UPGRADEABLE	"os_not_upgradeable"

/* string array of SVM root mirror components */
#define	TD_OS_ATTR_ZONES_NOT_UPGRADEABLE	"os_zones_not_upgradeable"

/* target type */
#define	TD_ATTR_TARGET_TYPE		"ti_target_type"

/* target method identifier */
#define	TD_TARGET_TYPE_ISCSI_STATIC_CONFIG	0

/* size definitions for iSCSI boot */
#define	INSTISCSI_MAX_ISCSI_NAME_LEN	233
#define	INSTISCSI_MAX_CHAP_LEN		16
#define	INSTISCSI_MAX_CHAP_NAME_LEN	512
#define	INSTISCSI_MAX_OS_DEV_NAME_LEN	64
#define	INSTISCSI_IP_ADDRESS_LEN	128
#define	INSTISCSI_MAX_LUN_LEN		32
#define	INSTISCSI_MAX_INITIATOR_LEN	INSTISCSI_MAX_ISCSI_NAME_LEN

/*
 * bitfields indicate reasons for upgrade failure
 */
struct td_upgrade_fail_reasons {
	uint32_t root_not_mountable	: 1;
	uint32_t var_not_mountable	: 1;
	uint32_t no_inst_release	: 1;
	uint32_t no_cluster		: 1;
	uint32_t no_clustertoc		: 1;
	uint32_t no_bootenvrc		: 1;
	uint32_t zones_not_upgradeable	: 1;
	uint32_t no_usr_packages	: 1;
	uint32_t no_version		: 1;
	uint32_t svm_root_mirror	: 1;
	uint32_t wrong_metacluster	: 1;
	uint32_t os_version_too_old	: 1;
};

/* for use in cross-reference object comparisons */
typedef enum {
	TD_OPER_CONTAINS,
	TD_OPER_CONTAINED_BY,
	TD_OPER_EQUALS
} td_operator_t;

/* function prototypes */

td_errno_t td_discover(td_object_type_t, int *);

td_errno_t td_target_search(nvlist_t *);

td_errno_t td_discovery_release(void);
nvlist_t **td_discover_partition_by_disk(const char *, int *);
nvlist_t **td_discover_slice_by_disk(const char *, int *);

td_errno_t td_get_next(td_object_type_t);
td_errno_t td_reset(td_object_type_t);

boolean_t td_is_slice(const char *);

#define	TD_ERRNO td_get_errno()

td_errno_t td_get_errno(void);

nvlist_t *td_attributes_get(td_object_type_t);
void td_list_free(nvlist_t *);
void td_attribute_list_free(nvlist_t **);
nvlist_t **td_xref(td_object_type_t, const char *, const char *,
    td_operator_t, td_object_type_t, const char *);

#ifdef __cplusplus
}
#endif

#endif /* _TD_API_H */
