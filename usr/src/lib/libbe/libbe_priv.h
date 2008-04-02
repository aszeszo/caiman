/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
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

#include <libnvpair.h>
#include <libzfs.h>

#ifndef	_LIBBE_PRIV_H
#define	_LIBBE_PRIV_H

#define	BE_AUTO_NAME_MAX_TRY	3
#define	BE_AUTO_NAME_DELIM	'-'
#define	BE_POLICY_PROPERTY	"com.sun.libbe:policy"
#define	BE_PLCY_STATIC		"static"
#define	BE_PLCY_VOLATILE	"volatile"
#define	BE_GRUB_COMMENT		"#============ End of LIBBE entry ============="

typedef struct be_transaction_data {
	char		*obe_name;	/* Original BE name */
	char		*obe_root_ds;	/* Original BE root dataset */
	char		*obe_zpool;	/* Original BE pool */
	char		*obe_snap_name;	/* Original BE snapshot name */
	char 		*nbe_name;	/* New BE name */
	char		*nbe_root_ds;	/* New BE root dataset */
	char		*nbe_zpool;	/* New BE pool */
	char		*nbe_desc;	/* New BE description */
	nvlist_t	*nbe_zfs_props;	/* New BE dataset properties */
	char		*policy;	/* BE policy type */
} be_transaction_data_t;

typedef struct be_mount_data {
	char		*altroot;	/* Location of where to mount BE */
	uint_t		mount_flags;	/* Special flags for mounting */
} be_mount_data_t;

typedef struct be_plcy_list{
	char			*be_plcy_name;
	int			be_num_max;
	int			be_num_min;
	time_t			be_age_max;
	int			be_usage_pcnt;
	struct be_plcy_list	*be_next_plcy;
}be_plcy_list_t;

/* Library globals */
extern libzfs_handle_t *g_zfs;

/* be_list.c */
int _be_list(char *, be_node_list_t **);

/* be_mount.c */
int _be_mount(char *, char *, int);
int _be_unmount(char *);

/* be_snapshot.c */
int _be_create_snapshot(char *, char **, char *);
int _be_destroy_snapshot(char *, char *);

/* be_utils.c */
boolean_t be_zfs_init(void);
void be_zfs_fini(void);
void be_make_root_ds(const char *, const char *, char *, int);
void be_make_container_ds(const char *, char *, int);
int be_append_grub(char *, char *, char *, char *);
int be_remove_grub(char *, char *, char *);
int be_update_grub(char *, char *, char *, char *);
int be_change_grub_default(char *, char *);
int be_update_vfstab(char *, char *, char *);
int be_maxsize_avail(zfs_handle_t *, uint64_t *);
char *be_auto_snap_name(char *);
char *be_auto_be_name(char *);
char *be_default_policy(void);
boolean_t valid_be_policy(char *);
boolean_t be_valid_auto_snap_name(char *);
boolean_t be_valid_be_name(char *);

/* callback functions */
int be_exists_callback(zpool_handle_t *, void *);
int be_find_zpool_callback(zpool_handle_t *, void *);
int be_zpool_find_current_be_callback(zpool_handle_t *, void *);
int be_zfs_find_current_be_callback(zfs_handle_t *, void *);

#endif	/* _LIBBE_PRIV_H */
