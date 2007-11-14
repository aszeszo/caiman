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

#ifndef _SW_SWI_H
#define	_SW_SWI_H

#pragma ident	"@(#)sw_swi.h	1.17	07/11/09 SMI"


#ifdef __cplusplus
extern "C" {
#endif

#include <spmisoft_api.h>

/*		FUNCTION PROTOTYPES 		*/

void	enter_swlib(char *);
void	exit_swlib(void);

/*
 * internal version of external functions.  These functions are all
 * called by "wrappers" when used by external functions.
 */

/* soft_admin.c */

char	*swi_getset_admin_file(char *);
int	swi_admin_write(char *, Admin_file *);

/* soft_arch.c */

char	*swi_get_default_arch(void);
char	*swi_get_default_impl(void);
Arch	*swi_get_all_arches(Module *);
int	swi_package_selected(Node *, char *);
int	swi_select_arch(Module *, char *);
int	swi_deselect_arch(Module *, char *);
void	swi_mark_arch(Module *);
int	swi_valid_arch(Module *, char *);

/* soft_choosemedia.c */
void	swi_setAutoEject(int);
char 	*swi_getCDdevice();
void	swi_eject_disc(char *);
int	swi_mount_disc(char *, char *);
int	swi_verify_solaris_image(char *, StringList **, StringList **);
int	swi_isAutoEject();
int	swi_have_disc_in_drive(char *);
int	swi_umount_dir(char *);
int	swi_mount_path(char *, char *);


/* soft_depend.c */

boolean_t swi_check_sw_depends(void);
Depend	*swi_get_depend_pkgs(void);

/* soft_geo.c */

Module	*swi_get_all_geos(void);
int	swi_valid_geo(Module *, char *);
int	swi_select_geo(Module *, char *);
int	swi_deselect_geo(Module *, char *);
void	swi_generate_locgeo_lists(char ***, char ***);
char	*swi_geo_name_from_code(char *);

/* soft_install.c */

Module	*swi_load_installed(char *, boolean_t);
Modinfo	*swi_next_patch(Modinfo *);
Modinfo	*swi_next_inst(Modinfo *);

/* soft_launcher.c */
void	swi_parsePackagesToBeAdded();
void	swi_create_dispatch_table();
void	swi_setup_launcher(int);

/* soft_locale.c */

Module	*swi_get_all_locales(void);
int	swi_select_locale(Module *, char *, int);
int	swi_deselect_locale(Module *, char *);
int	swi_valid_locale(Module *, char *);
char	*swi_get_default_system_locale(void);
int	swi_set_default_system_locale(char *);
char	*swi_get_system_locale(void);
char	*swi_get_locale_geo(char *);
int	swi_save_locale(char *, char *);
int	swi_get_sys_locale_list(char *, char ***);
void	swi_build_locale_list(void);
char	*swi_get_init_default_system_locale(void);
char	*swi_get_composite_locale(char *);

/* soft_media.c */

Module	*swi_add_media(char *);
Module	*swi_add_specific_media(char *, char *);
int	swi_load_media(Module *, int);
int	swi_unload_media(Module *);
void	swi_set_eject_on_exit(int);
Module	*swi_get_media_head(void);
Module	*swi_find_media(char *, char *);

/* soft_module.c */

int 	swi_set_current(Module *);
int	swi_set_default(Module *);
Module	*swi_get_current_media(void);
Module	*swi_get_current_service(void);
Module	*swi_get_current_product(void);
Module	*swi_get_current_category(ModType);
Module	*swi_get_current_metacluster(void);
Module	*swi_get_local_metacluster(void);
Module	*swi_get_current_cluster(void);
Module	*swi_get_current_package(void);
Module	*swi_get_default_media(void);
Module	*swi_get_default_service(void);
Module	*swi_get_default_product(void);
Module	*swi_get_default_category(ModType);
Module	*swi_get_default_metacluster(void);
Module	*swi_get_default_cluster(void);
Module	*swi_get_default_package(void);
Module	*swi_get_next(Module *);
Module	*swi_get_sub(Module *);
Module	*swi_get_prev(Module *);
Module	*swi_get_head(Module *);
int	swi_mark_required(Module *);
int	swi_mark_module(Module *, ModStatus);
int	swi_mod_status(Module *);
int	swi_toggle_module(Module *);
char	*swi_get_current_locale(void);
void	swi_set_current_locale(char *);
char	*swi_get_default_locale(void);
int	swi_toggle_product(Module *, ModStatus);
int	swi_mark_module_action(Module *, Action);
int	swi_partial_status(Module *);

/* soft_prod.c */

char	*swi_get_clustertoc_path(Module *);
void	swi_media_category(Module *);

/* soft_prodsel.c */

Module	*swi_add_cd_module(Module *, char *, char *, char *);
Module	*swi_add_os_module(Module *, char *, char *);
Module	*swi_add_comp_module(Module *, char *, char *, int);
Module	*swi_get_all_cds();
int	swi_select_cd(Module *, char *);
int	swi_deselect_cd(Module *, char *);
int	swi_select_component(Module *, char *);
int	swi_deselect_component(Module *, char *);
long	swi_get_cd_fs_size(CD_Info *, FileSys);
long	swi_get_cd_size(CD_Info *);
long	swi_get_component_fs_size(Product_Toc *, FileSys);
long	swi_get_component_size(Product_Toc *);

/* soft_util.c */

void	swi_sw_lib_init(int);
int	swi_set_instdir_svc_svr(Module *);
void	swi_clear_instdir_svc_svr(Module *);
char	*swi_gen_bootblk_path(char *);
char	*swi_gen_pboot_path(char *);
char	*swi_gen_openfirmware_path(char *);
int	swi_map_fs_idx_from_mntpnt(char *);
int	swi_map_zone_fs_idx_from_mntpnt(char *, char *);
int	swi_writeStringListToFile(char *, StringList *);
StringList	*readStringListFromFile(char *);
void	swi_run_parse_dynamic_clustertoc();
void	swi_set_useAltImage(int);
int	swi_get_useAltImage();
void	swi_set_devices(char *);
char	*swi_get_device();
char	*swi_get_rawdevice();

/* soft_dump.c */

int	swi_dumptree(char *);

/* soft_update_actions.c */

int	swi_load_clients(void);
int	swi_load_zones(void);
void	swi_update_action(Module *);
int	swi_upg_select_locale(Module *, char *);
int	swi_upg_deselect_locale(Module *, char *);
int	swi_upg_select_geo(Module *, char *);
int	swi_upg_deselect_geo(Module *, char *);

/* soft_platform.c */

int	swi_write_platform_file(char *, Module *);

/* soft_v_version.c */

int	swi_prod_vcmp(char *, char *);
int	swi_pkg_vcmp(char *, char *);
int	swi_is_patch(Modinfo *);
int	swi_is_patch_of(Modinfo *, Modinfo *);

/* soft_sp_util.c */
int	swi_valid_mountp(char *);

/* soft_sp_space.c */

FSspace **swi_calc_cluster_space(Module *, ModStatus);
FSspace **swi_calc_package_space(Module *, ModStatus);
ulong	swi_calc_tot_space(Product *);
ulong	swi_tot_pkg_space(Modinfo *);
int	swi_calc_sw_fs_usage(FSspace **, int (*)(void *, void *), void *);
void    swi_free_fsspace(FSspace *);

/* soft_webstart_tables.c */
int	swi_readProductTables();
void	swi_readCDInfo(CD_Info *);
void	swi_readProductToc(CD_Info *);
char	*swi_get_loc_cdname(char *);
char	*swi_get_loc_cdhelp(char *);
char	*swi_get_loc_license_path();
char	*swi_get_loc_prodhelp(char *);
void	swi_parsePDfile(CD_Info *);
void	swi_setMkit(Media_Kit_Info *);
Media_Kit_Info	*swi_getMkit();

/* soft_webstart_util.c */
char	*swi_readInText(char *);
int	swi_writeOutText(char *, char *, char *);
int	swi_concatFiles(StringList *, char *);
int	swi_copyFile(char *, char *, boolean_t);
int	swi_copyDir(char *, char *);
int	swi_mkdirs(char *);
int	swi_pingHost(char *);
CDToc	*swi_readCDTOC(char *);
void	swi_free_cdtoc(CDToc *);
void	swi_setWebstartLocale(char *);
char	*swi_getWebstartLocale();
char	*swi_getLocString();
void	swi_check_boot_environment();
int	swi_isBootFromDisc();
int	swi_installAfterReboot();


#ifdef __cplusplus
}
#endif

#endif /* _SW_SWI_H */
