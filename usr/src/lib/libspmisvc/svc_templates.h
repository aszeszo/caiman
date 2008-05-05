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



#ifndef	_SVC_TEMPLATES_H_
#define	_SVC_TEMPLATES_H_


#ifdef __cplusplus
extern "C" {
#endif

extern char *script_start[];
extern char *init_swm_coalesce[];
extern char *init_coalesce[];
extern char *add_swap_cmd[];
extern char *del_swap_cmd[];
extern char *mount_fs_cmd[];
extern char *build_admin_file[];
extern char *touch_upgrade[];
extern char *init_virtual_pkg_log[];
extern char *do_local_pkgadd[];
extern char *do_virtual_pkgadd[];
extern char *print_copyright[];
extern char *do_pkgrm[];
extern char *do_pkgrm_f[];
extern char *rename_file[];
extern char *do_prodrm[];
extern char *do_rm_fr[];
extern char *do_rm[];
extern char *do_removef[];
extern char *zone_do_removef[];
extern char *spool_local_pkg[];
extern char *spool_virtual_pkg[];
extern char *echo_locales_installed[];
extern char *echo_INST_RELEASE[];
extern char *zone_echo_INST_RELEASE[];
extern char *echo_softinfo[];
extern char *end_softinfo[];
extern char *touch_reconfig[];
extern char *rm_tmp[];
extern char *zone_rm_tmp[];
extern char *umount_cmd[];
extern char *rm_service[];
extern char *mv_varsadm_usr[];
extern char *add_varsadm_usr[];
extern char *link_varsadm_usr[];
extern char *mv_kvm_svc[];
extern char *add_kvm_svc[];
extern char *link_kvm_svc[];
extern char *rm_kvm_svc[];
extern char *start_softinfo[];
extern char *kvm_softinfo[];
extern char *usr_softinfo[];
extern char *root_softinfo[];
extern char *locale_softinfo[];
extern char *rm_softinfo[];
extern char *rm_svc_dfstab[];
extern char *add_usr_svc_dfstab[];
extern char *sed_dfstab_usr[];
extern char *add_kvm_svc_dfstab[];
extern char *share_usr_svc_dfstab[];
extern char *share_kvm_svc_dfstab[];
extern char *init_inetboot_dir[];
extern char *cp_shared_inetboot[];
extern char *cp_svc_inetboot[];
extern char *cp_inetboot[];
extern char *upgrade_client_inetboot[];
extern char *sed_vfstab[];
extern char *sed_vfstab_rm_kvm[];
extern char *touch_client_reconfigure[];
extern char *rm_inetboot[];
extern char *remove_restart_files[];
extern char *exit_ok[];
extern char *remove_coalesce[];
extern char *print_cleanup_msg[];
extern char *remove_patch[];
extern char *zone_remove_patch[];
extern char *move_template[];
extern char *rm_template_dir[];
extern char *write_CLUSTER[];
extern char *zone_write_CLUSTER[];
extern char *write_clustertoc[];
extern char *start_rmlist[];
extern char *zone_start_rmlist[];
extern char *addto_rmlist[];
extern char *zone_addto_rmlist[];
extern char *end_rmlist[];
extern char *zone_end_rmlist[];
extern char *log_file_diff[];
extern char *gen_installboot_sparc[];
extern char *gen_installboot_i386[];
extern char *gen_installboot_stub[];
extern char *chmod_file[];
extern char *chown_file[];
extern char *chgrp_file[];
extern char *start_perm_restores[];
extern char *end_perm_restores[];
extern char *remove_template[];
extern char *print_rmpkg_msg[];
extern char *link_usr_svc[];
extern char *add_usr_svc[];
extern char *mk_varsadm_dirs[];
extern char *mv_varsadm_files[];
extern char *refresh_db[];
extern char *mv_whole_svc[];
extern char *mv_isa_svc[];
extern char *mv_svc_link[];
extern char *move_files_in_contents[];

#ifdef __cplusplus
}
#endif

#endif	/* _SVC_TEMPLATES_H_ */
