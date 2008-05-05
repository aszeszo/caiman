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


#include "spmisoft_lib.h"
#include <stdlib.h>

/* Public Prototype Specifications */

/* Library Prototype Specifications */

void		free_np_modinfo(Node *);
void		free_media_module(Module *);
void		free_media(Media *);
void		free_prod(Product *);
void		free_list(List *);
void		free_np_module(Node *);
void		free_np_view(Node *);
void		free_arch(Arch *);
void		free_full_view(Module *, Module *);
void		free_modinfo(Modinfo *);
void		free_sw_config_list(SW_config *swcfg);
void		free_platform(Platform *plat);
void		free_platgroup(PlatGroup *platgrp);
void		free_hw_config(HW_config *hwcfg);
void		free_file(struct file *);
void		free_patch_instances(Modinfo *);
void		free_diff_rev(SW_diffrev *);
void		free_pkgs_lclzd(PkgsLocalized *);
void		free_locale(Module *);
void		free_patch(struct patch *);
void		free_depends(Depend *);

/* Local Prototype Specifications */

static void	free_instances(Modinfo *);
static void	free_prod_module(Module *);
static void	free_tree(Module *);
static void	free_view(View *);
static void	free_categories(Module *);
static void	free_prod_view(Module *);
static void	free_newarch_patches(struct patch_num *);

/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * free_module()
 *	Free a generic Module structure.  This function will check
 *	what type of Module is being free'ed and call the correct
 *	function to free it.
 * Parameters:
 *	mod	- pointer to Module to be free'ed.
 * Return
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_module(Module *mod)
{
	switch (mod->type) {
	case PRODUCT:
	case NULLPRODUCT:
		free_prod_module(mod);
		break;
	case MEDIA:
		free_media_module(mod);
		break;
	case PACKAGE:
	case CLUSTER:
	case METACLUSTER:
	case UNBUNDLED_4X:
		free_modinfo(mod->info.mod);
		free(mod);
		break;
	case CATEGORY:
		free_categories(mod);
		break;
	case LOCALE:
		free_locale(mod);
		break;
	case GEO:
		free_geo(mod);
		break;
	default:
		/* Other mod types not implemented */
		break;
	}
}

/*
 * free_np_modinfo()
 *	Free the Modinfo structure associated with the 'np' node.
 * Parameters:
 *	np	- pointer to Node referencing Modinfo to be freed
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_np_modinfo(Node *np)
{
	np->key = NULL;
	free_modinfo((Modinfo *)np->data);
}


/*
 * free_media_module()
 *	Free the Media structure, it's substructures, its Product chain,
 *	 and its Category chain.
 * Parameters:
 *	mod	- pointer to Media module
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 * Note:
 *	Why were the categories freed up before descending the
 *	product tree?
 */
void
free_media_module(Module * mod)
{
	Module  *mp, *mp_sav;
	Media	*medp;

	/* free the media product tree */
	for (mp_sav = mp = mod->sub; mp != NULL; mp = mp_sav) {
		mp_sav = mp->next;
		free_prod_module(mp);
	}

	/* free the media structure */
	medp = mod->info.media;
	if (medp != NULL) {
		free_media(medp);
	}
	free(mod);
}

/*
 * free_media()
 *	Free the Media structure and its Category chain.
 * Parameters:
 *	med	- pointer to Media structure
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_media(Media *med)
{
	if (med == NULL)
		return;

	free_categories(med->med_cat);
	free(med->med_device);
	free(med->med_dir);
	free(med->med_volume);
	free(med->med_zonename);
	free(med);
}

/*
 * free_arch()
 *	Free an architecture structure chain headed by 'arch'.
 * Parameters:
 *	arch	- pointer to head of architecture chain.
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_arch(Arch * arch)
{
	Arch *ap, *tmp;

	for (ap = arch; ap != NULL; ap = tmp) {
		free(ap->a_arch);
		tmp = ap->a_next;
		free(ap);
	}
}

/*
 * free_list()
 * 	Free a node list referenced by 'list'.
 * Parameters:
 *	list	- pointer to list structure
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_list(List *list)
{
	Node *np, *tmp;

	if (list == NULL)
		return;

	for (np = list->list->next; np != list->list; np = tmp) {
		tmp = np->next;
		/*
		 * XXX HACK ALERT
		 * This test is required due to an error in the building
		 * of the tree wrt METACLUSTERS.
		 * Both the prod->info.prod->p_clusters list and the
		 * prod->sub hierarchy refer to the same METACLUSTER modules.
		 * For the time being, it's easier to free these modules in
		 * free_tree only rather than duplicating the modules (a
		 * complicated, intrusive fix).
		 */
		if (np->delproc != free_np_module ||
		    ((Module *)np->data)->type != METACLUSTER)
			delnode(np);
	}
	dellist(&list);
}

/*
 * free_np_module()
 *
 * Parameters:
 *	np	-
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_np_module(Node * np)
{
	Module *mod;

	if (np != (Node *)NULL && ((mod = (Module *)np->data) != NULL)) {
		np->key = NULL;
		free_modinfo(mod->info.mod);
		free(mod);
	}
}

/*
 * free_np_view()
 *
 * Parameters:
 *	np	- node pointer
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_np_view(Node * np)
{
	free_view((View *)np->data);
	np->key = NULL;
}

/*
 * free_full_view()
 *
 * Parameters:
 *	prod	- pointer to Product
 *	med	- pointer to Media
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_full_view(Module * prod, Module * med)
{
	Product *p, *q;

	if (has_view(prod, med) != SUCCESS || med == NULL)
		return;
	/*
	 * In first pass through this loop (the pass that looks at
	 * the originating info.prod structure), p_view_from will
	 * always be NULL, so q doesn't need to be initialized in
	 * the first pass through the loop.
	 */
	for (p = prod->info.prod; p != NULL; q = p, p = p->p_next_view) {
		if (p->p_view_from == med) {
			/*LINTED [var set before used]*/
			q->p_next_view = p->p_next_view;
			free_list(p->p_view_4x);
			free_list(p->p_view_pkgs);
			free_list(p->p_view_cluster);
			free_list(p->p_view_locale);
			free_list(p->p_view_arches);
			free(p);
			return;
		}
	}
}

/*
 * free_modinfo()
 *
 * Parameters:
 *	mp	- pointer to Modinfo structure to be freed
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_modinfo(Modinfo * mp)
{
	if (mp == NULL)
		return;
	free(mp->m_pkgid);
	free(mp->m_pkg_dir);
	free(mp->m_name);
	free(mp->m_vendor);
	free(mp->m_version);
	free(mp->m_prodname);
	free(mp->m_prodvers);
	free(mp->m_arch);
	free(mp->m_expand_arch);
	free(mp->m_desc);
	free(mp->m_category);
	free(mp->m_instdate);

	/*
	 * free the patch stuff
	 */
	free(mp->m_patchid);
	mp->m_patchof = (Modinfo *)NULL;

	free_newarch_patches(mp->m_newarch_patches);

	free(mp->m_l10n_pkglist);
	free(mp->m_locale);
	if (mp->m_loc_strlist != NULL)
		StringListFree(mp->m_loc_strlist);
	if (mp->m_pkgs_lclzd)
		free_pkgs_lclzd(mp->m_pkgs_lclzd);
	if (mp->m_instdir != mp->m_basedir)
		free(mp->m_instdir);
	free(mp->m_basedir);

	free_depends(mp->m_pdepends);
	free_depends(mp->m_idepends);
	free_depends(mp->m_rdepends);

	free_instances(mp);
	free_patch_instances(mp);

	if (mp->m_text != NULL)
		free_file(*(mp->m_text));

	if (mp->m_demo != NULL)
		free_file(*(mp->m_demo));

	free_file(mp->m_install);
	free_file(mp->m_icon);
	free_history(mp->m_pkg_hist);
	free(mp);
}

/*
 * free_prod()
 *	Free the Product structure.
 * Parameters:
 *	prod	- pointer to Product structure
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_prod(Product *prod)
{
	if (prod == NULL)
		return;

	free_arch(prod->p_arches);
	free_locale(prod->p_locale);
	free_categories(prod->p_categories);

	/* free all lists associated with product */
	free_list(prod->p_sw_4x);
	free_list(prod->p_packages);
	free_list(prod->p_clusters);

	/* free the view tree and the current view */
	free_list(prod->p_view_4x);
	free_list(prod->p_view_pkgs);
	free_list(prod->p_view_cluster);
	free_list(prod->p_view_locale);
	free_list(prod->p_view_arches);

	if (prod->p_orphan_patch != NULL)
		free_instances((Modinfo *)prod->p_orphan_patch->data);

	free(prod->p_name);
	free(prod->p_version);
	free(prod->p_rev);
	free(prod->p_id);
	free(prod->p_pkgdir);
	free(prod->p_instdir);
	free(prod->p_rootdir);
	free(prod->p_zonename);
	free_patch(prod->p_patches);

	free(prod);
}

void
free_sw_config_list(SW_config *swcfg)
{
	SW_config	*nextone;

	while (swcfg) {
		nextone = swcfg->next;
		free(swcfg->sw_cfg_name);
		if (swcfg->sw_cfg_members)
			StringListFree(swcfg->sw_cfg_members);
		free(swcfg);
		swcfg = nextone;
	}
}

void
free_platform(Platform *plat)
{
	Platform	*nextone;

	while (plat) {
		nextone = plat->next;
		free(plat->plat_name);
		free(plat->plat_uname_id);
		free(plat->plat_machine);
		free(plat->plat_group);
		free(plat->plat_isa);
		free(plat);
		plat = nextone;
	}
}

void
free_platgroup(PlatGroup *platgrp)
{
	PlatGroup	*nextone;

	while (platgrp) {
		nextone = platgrp->next;
		free(platgrp->pltgrp_name);
		free(platgrp->pltgrp_isa);
		if (platgrp->pltgrp_members)
			free_platform(platgrp->pltgrp_members);
		free(platgrp);
		platgrp = nextone;
	}
}

void
free_hw_config(HW_config *hwcfg)
{
	HW_config	*nextone;

	while (hwcfg) {
		nextone = hwcfg->next;
		free(hwcfg->hw_node);
		free(hwcfg->hw_testprog);
		free(hwcfg->hw_testarg);
		if (hwcfg->hw_support_pkgs)
			StringListFree(hwcfg->hw_support_pkgs);
		free(hwcfg);
		hwcfg = nextone;
	}
}

void
free_patch_instances(Modinfo *mi)
{
	Modinfo	*j;
	Node	*tmp_np;

	for (j = next_patch(mi); j != NULL; j = next_patch(mi)) {
		tmp_np = mi->m_next_patch;
		mi->m_next_patch = j->m_next_patch;
		j->m_next_patch = NULL;
		delnode(tmp_np);
	}
}


void
free_pkgs_lclzd(PkgsLocalized *pkg)
{
	PkgsLocalized	*nextone;

	while (pkg) {
		nextone = pkg->next;
		free(pkg);
		pkg = nextone;
	}
}

/*
 * free_locale()
 *
 * Parameters:
 *	mod	-
 * Return:
 *
 * Status:
 *	semi-private (internal library use only)
 */
void
free_locale(Module * mod)
{
	Module *mp, *tmp;

	for (mp = mod; mp != NULL; mp = tmp) {
		free_tree(mp);
		if (mp->info.locale != NULL)
			free(mp->info.locale->l_locale);
		free(mp->info.locale);
		tmp = mp->next;
		free(mp);
	}
}

/*
 * free_geo()
 *
 * Parameters:
 *	mod	- The Geo module to be freed
 * Return:
 *	none
 *
 * Status:
 *	semi-private (internal library use only)
 */
void
free_geo(Module *mod)
{
	Module *mp, *tmp;

	for (mp = mod; mp != NULL; mp = tmp) {
		free_tree(mp);
		if (mp->info.geo != NULL) {
			free(mp->info.geo->g_geo);
			free(mp->info.geo->g_name);
			StringListFree(mp->info.geo->g_locales);
		}
		free(mp->info.geo);
		tmp = mp->next;
		free(mp);
	}
}

/*
 * free_pkg_info
 *	Free a pkg_info structure, and its substructures.
 * Parameters:
 *	pi	- pkg_info structure to free.
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_pkg_info(struct pkg_info *pi)
{
	struct pkg_info *pi_cur, *pi_save;
	if (pi == NULL)
		return;

	for (pi_cur = pi; pi_cur; pi_cur = pi_save) {
		pi_save = pi_cur->next;
		free(pi_cur->name);
		free(pi_cur->arch);
		free(pi_cur);
	}
}

/*
 * free_patch_num
 *	Free a patch_num structure, and its substructures.
 * Parameters:
 *	pn	- patch_num structure to free.
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
free_patch_num(struct patch_num *pn)
{
	struct patch_num *pn_cur, *pn_save;
	if (pn == NULL)
		return;

	for (pn_cur = pn; pn_cur; pn_cur = pn_save) {
		pn_save = pn_cur->next;
		free(pn_cur->patch_num_id);
		free(pn_cur->patch_num_rev_string);
		free(pn_cur);
	}
}

void
free_patch(struct patch *p)
{
	struct patch *next_p;
	struct patchpkg *ppkg, *next_ppkg;

	while (p) {
		next_p = p->next;
		p->patchid = (char *)NULL;
		p->next = (struct patch *)NULL;
		free(p->patchid);
		ppkg = p->patchpkgs;
		while (ppkg) {
			next_ppkg = ppkg->next;
			ppkg->next = (struct patchpkg *)NULL;
			ppkg->pkgmod = (Modinfo *)NULL;
			free(ppkg);
			ppkg = next_ppkg;
		}
		p->patchpkgs = (struct patchpkg *)NULL;
		free(p);
		p = next_p;
	}
}

/*
 * free_depends()
 *	Free the Depend structure chain referenced by 'dpd'.
 * Parameters:
 *	dpd	- pointer to Depend structure to be freed
 * Return:
 *	none
 * Status:
 *	private
 * Note:
 *	The Depend list is assumed to be non-circular
 */
void
free_depends(Depend * dpd)
{
	if (dpd == NULL)
		return;

	free(dpd->d_pkgidb);
	free(dpd->d_pkgid);
	free(dpd->d_version);
	free(dpd->d_arch);
	if (dpd->d_next != NULL)
		free_depends(dpd->d_next);

	free(dpd);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * free_view()
 *
 * Parameters:
 *	view	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_view(View * view)
{
	free(view->v_instdir);
	if (view->v_instances != NULL)
		free_view(view->v_instances);
	free(view);
}

/* free_locale promoted to semi-private (internal library use only) */

/*
 * free_categories()
 * Parameters:
 *	cat	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_categories(Module * cat)
{
	Module *cp, *tmp;

	for (cp = cat; cp != NULL; cp = tmp) {
		tmp = cp->next;
		free_tree(cp);
		if (cp->info.cat != NULL)
			free(cp->info.cat->cat_name);
		free(cp->info.cat);
		free(cp);
	}
}

/*
 * free_prod_view()
 *
 * Parameters:
 *	mod	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_prod_view(Module * mod)
{
	Product *pp, *tmp;

	for (pp = mod->info.prod->p_next_view; pp != NULL; pp = tmp) {
		tmp = pp->p_next_view;
		free_list(pp->p_view_4x);
		free_list(pp->p_view_pkgs);
		free_list(pp->p_view_cluster);
		free_list(pp->p_view_locale);
		free_list(pp->p_view_arches);
		free(pp);
	}
}

/*
 * free_instances()
 *	Free the instance chain associated with 'mp' Modinfo structure.
 * Parameters:
 *	mp	- pointer to Modinfo structure which has the
 *		  instance chain to be freed
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_instances(Modinfo * mp)
{
	Modinfo *i;
	Node    *tmp_np;

	for (i = next_inst(mp); i != NULL; i = next_inst(mp)) {
		tmp_np = mp->m_instances;
		mp->m_instances = i->m_instances;
		i->m_instances = NULL;
		delnode(tmp_np);
	}
}

/*
 * free_file()
 *	Free a file structure, and all its substructures.
 * Parameters:
 *	fp	-
 * Return:
 *	none
 * Status:
 *	private
 */
void
free_file(struct file *fp)
{
	if (fp == NULL)
		return;
	free(fp->f_path);
	free(fp->f_name);
	free(fp->f_args);

	/* added 6/30/93 */
	if (fp->f_data)
		free(fp->f_data);

	free(fp);
}


/*
 * free_tree()
 *	Free an entire tree rooted by 'mod'.
 * Parameters:
 *	mod	- pointer to Module heading the tree to be freed
 * Return:
 *	none
 * Note:
 *	Recursive function . WARNING: shouldn't something be called
 *	other than free(mp) to free the Module structure???
 */
static void
free_tree(Module * mod)
{
	Module *mp, *tmp;

	if (mod == (Module *)NULL)
		return;

	for (mp = mod->sub; mp != NULL; mp = tmp) {
		if (mp->sub != NULL)
			free_tree(mp);
		tmp = mp->next;
		if (mp->type == METACLUSTER) {
			/*
			 *  Null all pointers into the hierarchy because
			 *  all modules remaining after free_tree will
			 *  only be accessible through the p_cluster
			 *  hash list.  Any module not freed here must
			 *  be freed in a subsequent call to
			 *  free_list(p_clusters).
			 */
			mp->next = NULL;
			mp->prev = NULL;
			mp->sub = NULL;
			mp->head = NULL;
			mp->parent = NULL;
		} else
			free(mp);
	}
}

/*
 * free_prod_module()
 *	Free the Product structure associated with the 'mod' Module.
 * Parameters:
 *	mod	- pointer to Product's Module structure
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_prod_module(Module * mod)
{
	Module  *mp, *mp_sav;
	Product	*pp;	/* Product structure pointer */

	for (mp = mod; mp != NULL; mp = mp_sav) {
		mp_sav = mp->next;
		pp = (Product *)mp->info.prod;
		free_tree(mp);

		if (pp != NULL) {
			/* free the view tree and the current view */
			free_prod_view(mp);
			free_prod(pp);
		}

		free(mp);
	}
	free(mod);
}


void
free_diff_rev(SW_diffrev *sdr)
{
	if (sdr->sw_diffrev_pkg)
		free(sdr->sw_diffrev_pkg);
	if (sdr->sw_diffrev_arch)
		free(sdr->sw_diffrev_arch);
	if (sdr->sw_diffrev_curver)
		free(sdr->sw_diffrev_curver);
	if (sdr->sw_diffrev_newver)
		free(sdr->sw_diffrev_newver);
	free(sdr);
}

static void
free_newarch_patches(struct patch_num *nap)
{
	struct patch_num	*nextone;

	while (nap) {
		nextone = nap->next;
		free(nap->patch_num_id);
		free(nap->patch_num_rev_string);
		free(nap);
		nap = nextone;
	}
}
