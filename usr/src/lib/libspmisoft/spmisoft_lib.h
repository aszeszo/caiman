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


#ifndef _SPMISOFT_LIB_H
#define	_SPMISOFT_LIB_H


#ifdef __cplusplus
extern "C" {
#endif

#include <spmicommon_lib.h>
#include <instzones_lib.h>
#include <spmisoft_api.h>
#include <sw_pipe.h>
#include <sw_space.h>
#include <sw_swi.h>
#include <sw_swi_defines.h>

struct softinfo_desc {
	StringList *soft_arches;
	StringList *soft_packages;
};

struct patch_space_reqd {
	struct	patch_space_reqd *next;
	char	*patsp_arch;
	struct	patdir_entry {
		struct	patdir_entry *next;
		char	*patdir_dir;
		int	patdir_spooled;
		ulong	patdir_kbytes;
		ulong	patdir_inodes;
		char	*patdir_pkgid;
	}	*patsp_direntry;
};

struct missing_file {
	struct missing_file *next;
	int    misslen;
	char   missing_file_name[2];
};

typedef enum progress_action_type {
	PROG_BEGIN,
	PROG_DIR_DU,
	PROG_CONTENTS_LINES,
	PROG_PKGMAP_SIZE,
	PROG_FIND_MODIFIED,
	PROG_END
} ProgressActionType;

/* Open file descriptors passed into non-global zones */
typedef enum zone_fd_name {
	ZONE_FD_INST_RELEASE = 0,
	ZONE_FD_CLUSTER = 1,
	ZONE_FD_CLUSTERTOC = 2,
	ZONE_FD_LOCALES_INSTALLED = 3,
	ZONE_FD_NUM = 4		/* Has to be last */
} Zone_FD_Name;

/* library globals */

extern struct missing_file *missing_file_list;
extern int 	profile_upgrade;
extern int	in_final_upgrade_stage;
extern int	upg_state;
extern char	*slasha;
extern int	zone_fd[ZONE_FD_NUM];

/*	FUNCTION PROTOTYPES 	*/

/* soft_admin.c */

void		_setup_admin_file(Admin_file *);
void		_setup_pkg_params(PkgFlags *);
int		_build_admin(Admin_file *);

/* soft_arch.c */

void	expand_arch(Modinfo *);
void	add_arch(Module *, char *);
void	add_package(Module *, Modinfo *);
void	add_4x(Module *, Modinfo *);
int	update_selected_arch(Node *, caddr_t);
int	supports_arch(char *, char *);
int	media_supports_arch(Product *, char *);
void	extract_isa(char *, char *);
int	media_supports_isa(Product *, char *);
int	fullarch_is_selected(Product *, char *);
int	fullarch_is_loaded(Product *, char *);
int	isa_is_selected(Product *, char *);
int	isa_is_loaded(Product *, char *);
int	isa_of_arch_is(char *, char *);
int	arch_is_selected(Product *, char *);
int	_arch_cmp(char *, char *, char *);

/* soft_depend.c */

void	parse_instance_spec(Depend *, char *);
void	read_pkg_depends(Module *, Modinfo *);

/* soft_dump.c */
boolean_t dump_media_mod(FILE *, Module *);

/* soft_free.c */

void    free_np_modinfo(Node *);
void    free_media_module(Module *);
void    free_media(Media *);
void    free_prod(Product *);
void    free_list(List *);
void    free_np_module(Node *);
void    free_np_view(Node *);
void    free_arch(Arch *);
void    free_full_view(Module *, Module *);
void    free_modinfo(Modinfo *);
void    free_sw_config_list(SW_config *swcfg);
void    free_platform(Platform *plat);
void    free_platgroup(PlatGroup *platgrp);
void    free_hw_config(HW_config *hwcfg);
void    free_file(struct file *);
void    free_patch_instances(Modinfo *);
void    free_diff_rev(SW_diffrev *);
void    free_pkgs_lclzd(PkgsLocalized *);
void    free_locale(Module *);
void	free_geo(Module *);
void	free_module(Module *);
void	free_module(Module *);
void	free_patch(struct patch *);
void	free_depends(Depend *);
void	free_patch_num(struct patch_num *);
void	free_pkg_info(struct pkg_info *);

/* soft_geo.c */
void	read_geo_code_name_map(char *);
StringList *read_geo_map_file(char *, char *);
int	add_geo(Module *, char *);
int	add_installed_geos(Module *, char *);
void	sort_geos(Module *);

/* soft_install.c */
Modinfo	*find_owning_inst(char *, Modinfo *);
int	is_new_var_sadm(char *);
char	*INST_RELEASE_read_path(char *);
char	*services_read_path(char *);
char	*CLUSTER_read_path(char *);
char	*clustertoc_read_path(char *);
void	split_svr_svc(Module *, Module *);
void	set_cluster_status(Module *);
Module  *add_new_service(char *);
Module	*load_installed_zone(char *);
boolean_t	open_zone_fd(void);
void	close_zone_fd(void);
FILE	*get_fp_from_zone_fd(int);

/* soft_locale.c */
void	sync_l10n(Module *);
void	localize_packages(Module *);
int	add_locale_list(Module *, StringList *);
int	add_subset_locale_list(Module *, StringList *);
void	sort_locales(Module *);
char	*get_lang_from_loc_array(char *);
char	*get_lang_from_locale(char *);
char	*get_C_lang_from_locale(char *);
void	load_installed_locales(Module *);

/* soft_locale_lookup.c */
void	read_locale_table(Module *media);
char	*get_locale_description(char *, char *);
char	*get_locale_desc_from_media(char *, char *);
void	update_init(FILE *, char *);
int	locale_is_multibyte(char *);
char	*get_system_locale_from_file(void);
int	read_locale_file(FILE *fp, char *, char *, char *,
					char *, char *, char *, char *);
void	trim(char *);

/* soft_media.c */

Module	*duplicate_media(Module *);
void	dup_clstr_tree(Module *, Module *);
Module	*find_service_media(char *);
Depend	*duplicate_depend(Depend *);
Module	*get_newmedia(void);

/* soft_module.c */

void	mark_submodules(Module *, ModStatus);
int	mark_pkg_required(char *);
int	pkg_installed(char *);
Module	*get_pkg_module(char *);

/* soft_pkghist.c */

void	read_pkg_history_file(char *);
void	read_cls_history_file(char *);
void	free_history(struct pkg_hist *);

/* soft_platform.c */
int	load_platforms(Module *);
void	load_installed_platforms(Module *, boolean_t);
void	upg_write_platform_file(FILE *, char *, Product *, Product *);
void	upg_write_plat_softinfo(FILE *, Product *, Product *);

/* soft_prod.c */

int	load_all_products(Module *, int);
int	load_clusters(Module *, char *);
void	promote_packages(Module *, Module *, Module *);
int	load_pkginfo(Module *, char *, int);
void	reset_size_comp(Size_comp *);

/* soft_progress.c */
void	ProgressBeginActionCount(void);
int	ProgressInCountMode(void);
void	ProgressCountActions(ProgressActionType, ulong);
void	ProgressBeginMetering(int (*)(void *, void*), void *);
void	ProgressEndMetering(void);
void	ProgressAdvance(ProgressActionType, ulong, ValStage, char *);

/* soft_service.c */

void	remove_all_services(void);
int	remove_service(Module *, char *);
int	add_service(Module *, char *, Module *);

/* soft_sp_calc.c */
void	do_spacecheck_init(void);
void record_FS_info(FSspace **, char *, char *, ContentsBrkdn *, int);

/* soft_sp_load.c */
int	sp_load_contents(Product *, Product *);
void	set_add_service_mode(int);
int	get_add_service_mode();


/* soft_sp_space.c */
int	calc_pkg_space(char *, Modinfo *, Product *);
void	sp_contents_progress(void);

/* soft_sp_spacetab.c */
FSspace	**get_master_spacetab(void);

/* soft_update_actions.c */
int	update_module_actions(Module *, Module *, Action, Environ_Action);
char	*split_name(char **);
void	unreq_nonroot(Module *);
Modinfo	*find_new_package(Product *, char *, char *, Arch_match_type *);
void	generate_swm_script(char *);
int	is_server(void);
void	mark_preserved(Module *);
void	mark_removed(Module *);
void	set_final_upgrade_mode(int);
int	is_KBI_service(Product *);
Arch_match_type	compatible_arch(char *, char *);

/* soft_util.c */

File	*crackfile(char *, char *, FileType);
int	sort_packages(Module *, char *);
Module	*sort_modules(Module *);
int	isa_handled(char *);
void	isa_handled_clear(void);
void	set_primary_arch(Module *);
void	link_to(Item **, Item *);
void	sort_ordered_pkglist(Module *);
int	UsrpackagesExist(char *);
int	BootenvExists(void);
void	set_is_upgrade(int);
void	gen_pkgmap_path(char *, char *, Modinfo *);

/* soft_view.c */
void	clear_all_view(Module *);
int	load_default_view(Module *);
Module	*get_current_view(Module *);
void	clear_view(Module *);
int	has_view(Module *, Module *);

/* soft_version.c */
extern	int	pkg_fullver_cmp(Modinfo *, Modinfo *);

/* soft_walktree.c */

void	walktree(Module *, int (*)(Modinfo *, caddr_t), caddr_t);

#ifdef __cplusplus
}
#endif

#endif	/* _SPMISOFT_LIB_H */
