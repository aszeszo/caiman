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

#ifndef _TD_LIB_H
#define	_TD_LIB_H

/*
 * This header file is for private use within the Target Discovery library
 */

#include <libnvpair.h>
#include <ls_api.h>	/* logging service */

#ifdef __cplusplus
extern "C" {
#endif

#define	SUCCESS		0
#define	FAILURE		1

#define	streq(a, b)		(strcmp((a), (b)) == 0)

#define	ERR_OPENING_VFSTAB	46
#define	ERR_ADD_SWAP		47
#define	ERR_MOUNT_FAIL		48
#define	ERR_MUST_MANUAL_FSCK	49
#define	ERR_FSCK_FAILURE	50
#define	ERR_DELETE_SWAP		52
#define	ERR_UMOUNT_FAIL		53
#define	ERR_ZONE_MOUNT_FAIL	65

#define	DDM_CMD_LEN		1000

/* debug/trace aids for TD manager */
#define	TLI (ls_get_dbg_level() >= LS_DBGLVL_INFO)
#define	TLW (ls_get_dbg_level() >= LS_DBGLVL_WARN)
#define	TLE (ls_get_dbg_level() >= LS_DBGLVL_ERR)

/* td_mg.c */
int	td_is_new_var_sadm(const char *);
void	td_debug_print(ls_dbglvl_t, const char *, ...);
char	*td_get_rootdir(void);

/* td_version.c */
boolean_t	td_get_release(const char *, char *, int, char *, int);
boolean_t	td_get_build_id(const char *, char *, size_t);

/* td_mountall.c */
int	mount_zones(void);
char	*td_GetExemptSwapdisk(void);
int	td_mount_and_add_swap(const char *);
int	td_mount_and_add_swap_from_vfstab(char *);
int	td_umount_and_delete_swap(void);
int	td_mount_filesys(char *mntdev, char *fsckdev, char *mntpnt,
	    char *fstype, char *mntopts, int retry, nvlist_t **attr);
int	td_umount_all(void);
int	td_unswap_all(void);
void	td_set_profile_upgrade(void);
char	*td_get_failed_mntdev(void);
char	*td_get_fs_type(char *path);
int	td_set_mntdev_if_svm(char *, char *, char **, char *, nvlist_t **);
int	td_safe_system(const char *);

/* td_util.c */
int	td_map_node_to_devlink(char *, char *, int);
int	td_map_old_device_to_new(char *, char *, int);
int	td_map_to_effective_dev(char *, char *, int);
int	td_delete_all_swap(void);

#ifdef __cplusplus
}
#endif

#endif /* _TD_LIB_H */
