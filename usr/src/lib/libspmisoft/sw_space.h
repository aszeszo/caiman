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


#ifndef	_SW_SPACE_H
#define	_SW_SPACE_H

#pragma ident	"@(#)sw_space.h	1.12	07/11/09 SMI"

#include <spmisoft_api.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 *  component type flags, passed in the type_flags argument for
 *  add_file() and add_file_blks();
 */
#define	SP_NONE		0x0000
#define	SP_DIRECTORY	0x0001
#define	SP_MOUNTP	0x0002

/* sp_calc.c */

void	begin_global_space_sum(FSspace **);
void	begin_global_qspace_sum(FSspace **);
FSspace	**end_global_space_sum(void);
void	begin_specific_space_sum(FSspace **);
void	begin_specific_qspace_sum(FSspace **);
void	end_specific_space_sum(FSspace **);
void	add_file(char *, daddr_t, daddr_t, int, FSspace **);
void	add_file_blks(char *, daddr_t, daddr_t, int, FSspace **);
void	add_product(CD_Info *, FSspace **, char *);
int	record_save_file(char *fname, FSspace **);
void	do_spacecheck_init(void);
void	add_contents_record(ContentsRecord *, FSspace **);
void	add_spacetab(FSspace **, FSspace **, char *);

/* sp_load.c */

int  sp_read_pkg_map(char *, char *, Product *, char *, int, FSspace **);
int  sp_read_space_file(char *, Product *, char *, FSspace **);
void load_inherited_FSs(Product *);
void set_sp_err(int, int, char *);

/* sp_spacetab.c */

FSspace **	load_defined_spacetab(char **);
void	sort_spacetab(FSspace **);
FSspace	**load_def_spacetab(FSspace **);

/* sp_util.c */

int	valid_mountp_list(char **);
int	do_chroot(char *);
int	check_path_for_vars(char *);
void	set_path(char [], char *, char *, char *);
void	reset_stab(FSspace **);
int	meets_reqs(Modinfo *);
ContentsRecord *contents_record_from_stab(FSspace **, ContentsRecord *);
void	stab_from_contents_record(FSspace **, ContentsRecord *);

#ifdef __cplusplus
}
#endif

#endif	/* _SW_SPACE_H */
