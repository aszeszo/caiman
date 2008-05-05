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


#ifndef _SW_PIPE_H
#define	_SW_PIPE_H


#ifdef __cplusplus
extern "C" {
#endif

/*
 *  error codes
 */
#define	SP_PIPE_ERR_READ_MODULE		1
#define	SP_PIPE_ERR_READ_MODINFO	2
#define	SP_PIPE_ERR_READ_MEDIA		3
#define	SP_PIPE_ERR_READ_PRODUCT	4
#define	SP_PIPE_ERR_READ_GEO		5
#define	SP_PIPE_ERR_READ_LOCALE		6
#define	SP_PIPE_ERR_READ_CATEGORY	7
#define	SP_PIPE_ERR_READ_L10N		8
#define	SP_PIPE_ERR_READ_PKGSLOCALIZED	9
#define	SP_PIPE_ERR_READ_MODINFO_NODE	10
#define	SP_PIPE_ERR_READ_MODULE_NODE	11
#define	SP_PIPE_ERR_READ_DEPEND		12
#define	SP_PIPE_ERR_READ_FILEPP		13
#define	SP_PIPE_ERR_READ_FILE		14
#define	SP_PIPE_ERR_READ_PKG_HIST	15
#define	SP_PIPE_ERR_READ_FILEDIFF	16
#define	SP_PIPE_ERR_READ_PATCH_NUM	17
#define	SP_PIPE_ERR_READ_STRINGLIST	18
#define	SP_PIPE_ERR_READ_CONTENTSRECORD	19
#define	SP_PIPE_ERR_READ_CONTENTSBRKDN	20
#define	SP_PIPE_ERR_READ_CHARPP		21
#define	SP_PIPE_ERR_READ_ARCH		22
#define	SP_PIPE_ERR_READ_MODINFO_LIST	23
#define	SP_PIPE_ERR_READ_MODULE_LIST	24
#define	SP_PIPE_ERR_READ_PKG_INFO	25
#define	SP_PIPE_ERR_READ_SW_CONFIG	26
#define	SP_PIPE_ERR_READ_HW_CONFIG	27
#define	SP_PIPE_ERR_READ_PLATGROUP	28
#define	SP_PIPE_ERR_READ_PLATFORM	29
#define	SP_PIPE_ERR_READ_PATCH		30
#define	SP_PIPE_ERR_READ_PATCHPKG	31
#define	SP_PIPE_ERR_READ_N_LOCAL_FS	32
#define	SP_PIPE_ERR_READ_SSCANF_FAILED	33
#define	SP_PIPE_ERR_READ_FINDNODE	34
#define	SP_PIPE_ERR_READ_ADDNODE	35
#define	SP_PIPE_ERR_READ_STRINGLISTADD	36
#define	SP_PIPE_ERR_NO_PROD_PKG_INST	37
#define	SP_PIPE_ERR_READ_INVALID_LINE	38


/* soft_pipe.c */

Module		*read_module_from_pipe(FILE *);
Modinfo		*read_modinfo_from_pipe(FILE *);
Media		*read_media_from_pipe(FILE *);
Product		*read_product_from_pipe(FILE *);
Geo		*read_geo_from_pipe(FILE *);
Locale		*read_locale_from_pipe(FILE *);
Category	*read_category_from_pipe(FILE *);
L10N		*read_l10n_from_pipe(FILE *);
PkgsLocalized	*read_pkgslocalized_from_pipe(FILE *);
Node		*read_modinfo_node_from_pipe(FILE *, boolean_t);
Node		*read_module_node_from_pipe(FILE *, boolean_t);
Depend		*read_depend_from_pipe(FILE *);
File		**read_filepp_from_pipe(FILE *);
File		*read_file_from_pipe(FILE *);
struct pkg_hist	*read_pkg_hist_from_pipe(FILE *);
struct filediff	*read_filediff_from_pipe(FILE *, boolean_t);
struct patch_num	*read_patch_num_from_pipe(FILE *);
StringList	*read_stringlist_from_pipe(FILE *);
ContentsRecord	*read_contentsrecord_from_pipe(FILE *);
int		read_contentsbrkdn_from_pipe(FILE *, ContentsBrkdn *);
char		**read_charpp_from_pipe(FILE *);
Arch		*read_arch_from_pipe(FILE *);
List		*read_modinfo_list_from_pipe(FILE *);
List		*read_module_list_from_pipe(FILE *);
struct pkg_info	*read_pkg_info_from_pipe(FILE *);
SW_config	*read_sw_config_from_pipe(FILE *);
HW_config	*read_hw_config_from_pipe(FILE *);
PlatGroup	*read_platgroup_from_pipe(FILE *);
Platform	*read_platform_from_pipe(FILE *);
struct patch		*read_patch_from_pipe(FILE *);
struct patchpkg	*read_patchpkg_from_pipe(FILE *);
int		read_filediff_owning_pkg_from_pipe(FILE *, Module *);
int		read_zone_fs_analysis_from_pipe(FILE *, Module *, FSspace **,
		    FSspace **, FILE *);
int		read_FSspace_from_pipe(FILE *fd, char *, FSspace **);

int		write_module_to_pipe(FILE *, Module *, boolean_t);
int		write_modinfo_to_pipe(FILE *, Modinfo *);
int		write_media_to_pipe(FILE *, Media *);
int		write_product_to_pipe(FILE *, Product *);
int		write_geo_to_pipe(FILE *, Geo *);
int		write_locale_to_pipe(FILE *, Locale *);
int		write_category_to_pipe(FILE *, Category *);
int		write_l10n_to_pipe(FILE *, L10N *);
int		write_pkgslocalized_to_pipe(FILE *, PkgsLocalized *);
int		write_modinfo_node_to_pipe(FILE *, Node *, boolean_t);
int		write_module_node_to_pipe(FILE *, Node *, boolean_t, boolean_t);
int		write_depend_to_pipe(FILE *, Depend *);
int		write_filepp_to_pipe(FILE *, File **);
int		write_file_to_pipe(FILE *, File *);
int		write_pkg_hist_to_pipe(FILE *, struct pkg_hist *);
int		write_filediff_to_pipe(FILE *, struct filediff *, boolean_t);
int		write_patch_num_to_pipe(FILE *, struct patch_num *);
int		write_stringlist_to_pipe(FILE *, StringList *);
int		write_contentsrecord_to_pipe(FILE *, ContentsRecord *);
int		write_contentsbrkdn_to_pipe(FILE *, ContentsBrkdn *);
int		write_charpp_to_pipe(FILE *, char **);
int		write_arch_to_pipe(FILE *, Arch *);
int		write_modinfo_list_to_pipe(FILE *, List *);
int		write_module_list_to_pipe(FILE *, List *);
int		write_pkg_info_to_pipe(FILE *, struct pkg_info *);
int		write_sw_config_to_pipe(FILE *, SW_config *);
int		write_hw_config_to_pipe(FILE *, HW_config *);
int		write_platgroup_to_pipe(FILE *, PlatGroup *);
int		write_platform_to_pipe(FILE *, Platform *);
int		write_patch_to_pipe(FILE *, struct patch *);
int		write_patchpkg_to_pipe(FILE *, struct patchpkg *);
int		write_filediff_owning_pkg_to_pipe(FILE *, struct filediff *);
int		write_zone_fs_analysis_to_pipe(FILE *, Module *, FSspace **,
		    FSspace **, boolean_t);
void		write_FSspace_to_pipe(FILE *, FSspace *);

char		*fgetspipe(char *, int, FILE *);
void		fgets_start_monitor(void);
void		fgets_stop_monitor(void);

#ifdef __cplusplus
}
#endif

#endif	/* _SW_PIPE_H */
