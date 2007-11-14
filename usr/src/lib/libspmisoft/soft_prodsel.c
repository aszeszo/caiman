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

#pragma ident	"@(#)soft_prodsel.c	1.4	07/11/09 SMI"


/*
 *	File:		soft_prodsel.c
 *
 *	Description:	This file contains the routines needed to handle
 *			cds and components
 */

#include <stdio.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <libintl.h>
#include <assert.h>

#include "spmisoft_lib.h"


/* Local functions */
static Module *new_cd_module(char *, char *, char *);
static Module *new_os_module(char *, char *);
static Module *new_comp_module(char *, char *, int);
static void sort_cd(CD_Info *);

static char **separate_zone_FSs = NULL;
static int numseparate_zone_FSs = 0;

/*
 * Public functions
 */

/*
 * Name:	(swi_)get_all_cds
 * Description:	Return the list of cds associated with the current
 *		product.
 * Scope:	public
 * Arguments:	none
 * Returns:	NULL		- no cds associated with the current product
 *		Module *	- pointer to cds list
 */
Module *
swi_get_all_cds(void)
{
	Module *prod = get_current_product();

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_all_cds");
#endif

	return (prod->info.prod->p_cd_info);
}

/*
 * Name:	(swi_)select_cd
 * Description:	Given a cd subdir, select that cd and all of
 *		its components in the provided product.
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		cddir	- [RO] (char *)
 *			  name of the cd subdir to be SELECTED
 *
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_NOPRODUCT	- 'cd' is not part of the cd
 *				  chain for 'mod'
 *		SUCCESS		- cd successfully selected
 */
int
swi_select_cd(Module *prod, char *cddir)
{
	Module		*mod;
	Module *productToc = (Module *)NULL;


#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_cd");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* Find the geographic region */
	for (mod = prod->info.prod->p_cd_info; mod; mod = mod->next) {
		if (streq(mod->info.cdinf->cddir, cddir)) {
			mod->info.cdinf->c_selected = SELECTED;

			/* Select the constituent locales */
			for (productToc = mod->info.cdinf->prodToc; productToc;
				productToc = productToc->next) {
				productToc->info.pdinf->p_selected = SELECTED;
			}
			return (SUCCESS);
		}
	}
	return (ERR_NOPRODUCT);
}

/*
 * Name:	(swi_)deselect_cd
 * Description:	Given a cd subdir, deselect the cd and all of
 *		its components.
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		cddir	- [RO] (char *)
 *			  name of the cd subdir to be DESELECTED
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_NOPRODUCT	- 'cd' is not part of the cd
 *				  chain for 'mod'
 *		SUCCESS		- cd successfully deselected
 */
int
swi_deselect_cd(Module *prod, char *cddir)
{
	Module		*mod;
	Module *productToc = (Module *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("deselect_cd");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* Find the cd */
	for (mod = prod->info.prod->p_cd_info; mod; mod = mod->next) {
		if (streq(mod->info.cdinf->cddir, cddir)) {
			mod->info.cdinf->c_selected = UNSELECTED;

			/* Deselect the constituent locales */
			for (productToc = mod->info.cdinf->prodToc; productToc;
				productToc = productToc->next) {
				productToc->info.pdinf->p_selected = UNSELECTED;
			}

			return (SUCCESS);
		}
	}
	return (ERR_NOPRODUCT);
}

/*
 * Name:	(swi_)select_component
 * Description:	Given a component's pd suffix, select that component
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		pdsuffix- [RO] (char *)
 *			  pd file suffix of component to be SELECTED
 *
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_NOPRODUCT	- 'pdsuffix' is not part of the cd
 *				  chain for 'mod'
 *		SUCCESS		- component successfully selected
 */
int
swi_select_component(Module *prod, char *pdsuffix)
{
	Module		*mod;
	Module *productToc = (Module *)NULL;


#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_cd");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* For each cd... */
	for (mod = prod->info.prod->p_cd_info; mod; mod = mod->next) {

		/* Find and select the component */
		for (productToc = mod->info.cdinf->prodToc; productToc;
			productToc = productToc->next) {
			if (streq(productToc->info.pdinf->pdname, pdsuffix)) {
				productToc->info.pdinf->p_selected = SELECTED;
				return (SUCCESS);
			}
		}
	}
	return (ERR_NOPRODUCT);
}

/*
 * Name:	(swi_)deselect_component
 * Description:	Given a component's pd suffix, deselect that component
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		pdsuffix- [RO] (char *)
 *			  pd file suffix of component to be DESELECTED
 *
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_NOPRODUCT	- 'pdsuffix' is not part of the cd
 *				  chain for 'mod'
 *		SUCCESS		- component successfully deselected
 */
int
swi_deselect_component(Module *prod, char *pdsuffix)
{
	Module		*mod;
	Module *productToc = (Module *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("deselect_cd");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* Find the cd */
	for (mod = prod->info.prod->p_cd_info; mod; mod = mod->next) {

		/* Find and deselect the component */
		for (productToc = mod->info.cdinf->prodToc; productToc;
			productToc = productToc->next) {
			if (streq(productToc->info.pdinf->pdname, pdsuffix)) {
				productToc->info.pdinf->p_selected = UNSELECTED;
				return (SUCCESS);
			}
		}
	}
	return (ERR_NOPRODUCT);
}

/*
 * Name:	(swi_)get_cd_fs_size
 * Description:	Return a filesystem size for the selected components from
 *		this CD based on the current locales selected and the
 *		architecture of system
 * Scope:	public
 * Arguments:	cdinf	- [RO] (CD_Info *)
 *			  non-NULL pointer to a CD_Info
 *		      fs	- FileSys index to filesystem name
 *		      p_rootdir	- product root directory
 * Returns:	total - total size required for the filesystem fs for this CD.
 */
long
swi_get_cd_fs_size(CD_Info *cdinf, FileSys fs)
{
	Module *mod;
	long total = 0;

	if (fs < 0 || fs >= N_LOCAL_FS)
		return (0);

	/* For each component in this CD */
	for (mod = cdinf->prodToc; mod; mod = mod->next) {
		/* if the component is selected */
		if (mod->info.pdinf->p_selected == SELECTED) {
			/* add its size into total */
			total += get_component_fs_size(mod->info.pdinf, fs);
		}
	}

	return (total);
}

/*
 * Name:	(swi_)get_cd_size
 * Description:	Return the size of this CD based on the selected
 *		components, the current locales selected and the
 *		architecture of system
 * Scope:	public
 * Arguments:	cdinf	- [RO] (CD_Info *)
 *			  non-NULL pointer to a CD_Info
 *
 * Returns:	total - total size required for this CD.
 */
long
swi_get_cd_size(CD_Info *cdinf)
{
	Module *mod;
	long total = 0;

	/* For each component in this CD */
	for (mod = cdinf->prodToc; mod; mod = mod->next) {
		/* if the component is selected */
		if (mod->info.pdinf->p_selected == SELECTED) {
			/* add its size into total */
			total += get_component_size(mod->info.pdinf);
		}
	}

	return (total);
}

/*
 * Name:	(swi_)get_component_fs_size
 * Description:	Return a filesystem size for this product based on the
 *		current locales selected and the architecture of system
 * Scope:	public
 * Arguments:	pdinfo	- [RO] (Product_Toc *)
 *			  non-NULL pointer to a Product_Toc
 *		      fs	- FileSys index to filesystem name
 *		      p_rootdir	- product root directory
 * Returns:	total - total size required for the filesystem fs for
 *		this product.
 */
long
swi_get_component_fs_size(Product_Toc *pdinfo, FileSys fs)
{
	PD_Size *pds = (PD_Size *)NULL;
	PDFile *pdf = (PDFile *)(pdinfo->pdfile);
	char *arch = get_default_inst();
	long total = 0;

	if (fs < 0 || fs >= N_LOCAL_FS)
		return (0);

	/* first start with the generic fs size total for this component */
	total = pdf->gen_size->fs_size[fs];

	/* for each PD_Size component for this product component */
	for (pds = pdf->head_sizes; pds; pds = pds->next) {
		/*
		 * if arch matches AND the locale list intersects with
		 * currently chosen locales, then add to total.
		 */
		if ((strcmp(pds->info->arch, "*") == 0 ||
				strcmp(pds->info->arch, arch) == 0) &&
			locale_list_selected(&(pds->info->locales))) {
			total += pds->info->fs_size[fs];
	    }
	}

	return (total);
}


/*
 * Name:	(swi_)get_component_size
 * Description:	Return the size of this product based on the current locales
 *		selected and the architecture of system
 * Scope:	public
 * Arguments:	pdinfo	- [RO] (Product_Toc *)
 *			  non-NULL pointer to a Product_Toc
 *
 * Returns:	total - total size required for this product.
 */
long
swi_get_component_size(Product_Toc *pdinfo)
{
	PD_Size *pds = (PD_Size *)NULL;
	PDFile * pdf = (PDFile *)(pdinfo->pdfile);
	char *arch = get_default_inst();
	long total = 0;
	int i;

	/* first start with the generic size total for this component */
	for (i = 0; i < N_LOCAL_FS; i++)
		total += pdf->gen_size->fs_size[i];

	/* for each PD_Size component for this product component */
	for (pds = pdf->head_sizes; pds; pds = pds->next) {
		/*
		 * if arch matches AND the locale list intersects with
		 * currently chosen locales, then add to total.
		 */
		if ((strcmp(pds->info->arch, "*") == 0 ||
				strcmp(pds->info->arch, arch) == 0) &&
			locale_list_selected(&(pds->info->locales))) {
			for (i = 0; i < N_LOCAL_FS; i++)
				total += pds->info->fs_size[i];
	    }
	}

	return (total);
}

/*
 * Name:	(swi_)add_os_module
 * Description:	Create a new os module, populate it, and add it to the front of
 *		the current list.
 * Scope:	public
 * Arguments:	list	- The current os list
 *		osfilename	- The os. filename (os.core.1)
 *		ospath	- The path of the os directory
 *		(eg. /usr/lib/install/data/os/5.10)
 * Returns:	Module *	- The new head of the geo list
 */
Module *
swi_add_os_module(Module *list, char *osfilename, char *ospath)
{
	Module *m;

	m = new_os_module(osfilename, ospath);

	m->next = list;
	if (list)
		list->prev = m;

	return (m);
}

/*
 * Name:	(swi_)add_cd_module
 * Description:	Create a new cd module, populate it, and add it to the front of
 *		the current list.
 * Scope:	public
 * Arguments:	list	- The current geo list
 *		geo	- The geo code
 *		locale	- The inital locale to add to the geo
 * Returns:	Module *	- The new head of the geo list
 */
Module *
swi_add_cd_module(Module *list, char *cdname, char *locname, char *cdsubdir)
{
	Module *m;

	m = new_cd_module(cdname, locname, cdsubdir);

	m->next = list;
	if (list)
		list->prev = m;

	return (m);
}

/*
 * Name:	(swi_)add_comp_module
 * Description:	Create a new component module and add it to the front of
 *		the current list.
 * Scope:	public
 * Arguments:	list	- The current component list
 *           	name    - The pd file suffix (name) of the component
 *		defins  - Whether the component is installed by default
 * Returns:	Module *	- The new head of the component list
 */
Module *
swi_add_comp_module(Module *list, char *pdname, char *locpdname, int defins)
{
	Module *m;

	m = new_comp_module(pdname, locpdname, defins);

	m->next = list;
	if (list)
		list->prev = m;

	return (m);
}

/*
 * Library-private functions
 */

/*
 * Name:	sort_cds
 * Description:	Given a list of cds, sort the components in each of those cds.
 * Scope:	semi-private (internal library use only)
 * Arguments:	prod	- [RO, *RO] (Module *)
 *			  The list of cds whose locales are to be sorted.
 * Returns:	none
 */
void
sort_cds(Module *prod)
{
	Module *cds;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("sort_cds");
#endif

	if (prod->info.prod->p_cd_info == NULL)
		return;

	for (cds = prod->info.prod->p_cd_info; cds; cds = cds->next) {
		sort_cd(cds->info.cdinf);
	}
}

/*
 * Name:	add_to_separate_zone_FSs
 * Description:	Add a zones separate mount point to a list of mount
 *              points to be skipped when space is being calculated.
 * Scope:	public
 * Arguments:	mntpnt - The mntpnt to add
 */
void
add_to_separate_zone_FSs(char *mntpnt)
{
	assert(mntpnt != NULL);

	if (separate_zone_FSs == NULL) {
		separate_zone_FSs = (char **)xcalloc(sizeof (char **));
	} else {
		separate_zone_FSs = (char **)xrealloc(separate_zone_FSs,
		    sizeof (char **)*(numseparate_zone_FSs+1));
	}

	separate_zone_FSs[numseparate_zone_FSs++] = xstrdup(mntpnt);
	separate_zone_FSs[numseparate_zone_FSs] = NULL;
}

/*
 * Private functions
 */

/*
 * Name:	new_os_module
 * Description:	Creates a new os module
 * Scope:	private
 * Arguments:	osfilename	- The os. filename (os.core.1)
 *		ospath	- The path of the os directory
 *		(eg. /usr/lib/install/data/os/5.10)
 * Returns:	Module *	- The new os module
 */
static Module *
new_os_module(char *osfilename, char *ospath)
{
	Module *m;

	m = (Module *)xcalloc(sizeof (Module));
	m->type = OSFILE;

	m->info.osinf = (OS_Info *)xcalloc(sizeof (OS_Info));
	m->info.osinf->osfile = xstrdup(osfilename);
	m->info.osinf->ospath = xstrdup(ospath);

	return (m);
}

/*
 * Name:	new_cd_module
 * Description:	Creates a new cd module with a given locale name for that
 *		region.
 * Scope:	private
 * Arguments:	name    - The English name for the CD
 *		subdir	- The name of the subdir in the cds directory
 * Returns:	Module *	- The new cd module
 */
static Module *
new_cd_module(char *name, char *locname, char *subdir)
{
	Module *m;

	m = (Module *)xcalloc(sizeof (Module));
	m->type = CD;

	m->info.cdinf = (CD_Info *)xcalloc(sizeof (CD_Info));
	m->info.cdinf->cdname = xstrdup(name);
	if (locname == NULL || strlen(locname) == 0) locname = name;
	m->info.cdinf->loccdname = xstrdup(locname);
	m->info.cdinf->cddir = xstrdup(subdir);
	m->info.cdinf->installer_wsr = B_TRUE;

	return (m);
}

/*
 * Name:	new_comp_module
 * Description:	Creates a new component module
 * Scope:	private
 * Arguments:	name    - The pd file suffix (name) of the component
 *		defins  - Whether the component is installed by default
 * Returns:	Module *	- The new component module
 */
static Module *
new_comp_module(char *name, char *locname, int defins)
{
	Module *m;

	m = (Module *)xcalloc(sizeof (Module));
	m->type = COMPONENT;

	m->info.pdinf = (Product_Toc *)xcalloc(sizeof (Product_Toc));
	m->info.pdinf->pdname = xstrdup(name);
	if (locname == NULL || strlen(locname) == 0) locname = name;
	m->info.pdinf->locprodname = xstrdup(locname);
	m->info.pdinf->defInstall = defins;

	return (m);
}

/*
 * Name:	sort_cd
 * Description:	Sort the list of components that make up a cd.  The list is
 *		sorted alphabetically according to the component name.
 * Scope:	private
 * Arguments:	g	- [RO, *RW] (Geo *)
 *			  The cd whose components are to be sorted.
 * Returns:	none
 */
static void
sort_cd(CD_Info *cd)
{
	Module *new, *pr, *olpr, *cur, *ocur;
	char *curdesc = (char *)NULL;
	char *desc = (char *)NULL;

	if (cd->prodToc == NULL)
		return;

	new = NULL;
	while (cd->prodToc) {
		/* Look for name highest in the sorting order */
		cur = NULL;
		for (pr = cd->prodToc, olpr = NULL; cd; olpr = pr,
							pr = pr->next) {
			if (!cur) {
				cur = pr;
				ocur = olpr;
				curdesc = cur->info.pdinf->pdname;
			} else {
				desc = pr->info.pdinf->pdname;
				if (strcoll(desc, curdesc) > 0) {
					cur = pr;
					ocur = olpr;
					curdesc = desc;
				}
			}
		}

		/* Remove cur from prodToc */
		if (ocur) {
			ocur->next = cur->next;
		} else {
			cd->prodToc = cur->next;
		}

		/* Add cur to beginning of new */
		cur->next = new;
		new = cur;
	}

	/* new now contains the sorted list */
	cd->prodToc = new;
}
