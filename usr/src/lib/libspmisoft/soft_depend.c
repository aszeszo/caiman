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


#pragma ident	"@(#)soft_depend.c	1.10	07/11/09 SMI"

#include "spmisoft_lib.h"
#include <stdlib.h>
#include <string.h>

/* Local Statics and Constants */

#define	WHITESPACE	" \t\r\n\f\v"
#define	SELECTED(x) 	((x)->m_status == SELECTED || (x)->m_status == REQUIRED)

static Depend  *dependencies = (Depend *) NULL;

/*
 * List of packages that are required to be installed on any system
 * in the event that subsequent installation actions need to happen
 * after install&reboot.
 */
static char *install_deps[] = {
	"SUNWj6rt",
	NULL	/* last entry must be NULL */
};

/* Public function prototypes */
boolean_t swi_check_sw_depends(void);
Depend    *swi_get_depend_pkgs(void);

/* Library function prototypes */

void	read_pkg_depends(Module *, Modinfo *);
void	parse_instance_spec(Depend *, char *);

/* Local function prototypes */

static void 	set_depend_pkgs(Depend *);
static Depend   *add_depend_pkg(Depend *, char *, char *, DependType);
static char 	*parse_depend_pkgid(char *);
static Depend	*add_depend_instance(Depend **, char *);
static Depend	*_check_sw_depends(Module *);


/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * get_depend_pkgs()
 *	Return a pointer to the current list of unresolved package
 *	dependencies.
 * Parameters:
 *	none
 * Returns:
 *	Depend *	- current list of unresolved package dependencies
 * Status:
 *	public
 */
Depend *
swi_get_depend_pkgs(void)
{
	return (dependencies);
}

/*
 * check_sw_depends()
 *	Determine if the current product has any packages which are SELECTED,
 *	but which have dependencies on packages which are not SELECTED.
 * Parameters:
 *	none
 * Return:
 *	B_TRUE	- selected packages have dependencies on unselected
 *		  packages
 *	B_FALSE	- selected packages do not have dependencies on
 *		  unselected packages
 */
boolean_t
swi_check_sw_depends(void)
{
	Module	*prod = get_current_product();
	Module	*mod;
	Depend	*dpnd;
	Depend	*dpnd_pkgs = NULL;
	Depend	*z_dpnd_pkgs = NULL;
	boolean_t	loaded_nonglobal_zone = B_FALSE;

	/* load the view for the global root */
	(void) load_view(prod, get_localmedia());

	/* walks the product view of the global root */
	dpnd_pkgs = _check_sw_depends(prod);

	/* walk the package list for the product of each nonglobal zone */
	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED &&
		    mod->info.media->med_zonename != NULL &&
		    has_view(prod, mod) == SUCCESS) {
			(void) load_view(prod, mod);
			loaded_nonglobal_zone = B_TRUE;
			z_dpnd_pkgs = _check_sw_depends(prod);

			if (z_dpnd_pkgs != NULL) {
				/*
				 * Add the current nonglobal zonename to the
				 * dependencies found.
				 */
				for (dpnd = z_dpnd_pkgs; dpnd != NULL;
				    dpnd = dpnd->d_next) {
					dpnd->d_zname =
					    mod->info.media->med_zonename;
				}

				/*
				 * Append dependecies found for this zone
				 * to the end of the main dependency list.
				 */
				if (dpnd_pkgs != NULL) {
					for (dpnd = dpnd_pkgs;
					    dpnd->d_next != (Depend *)NULL;
					    dpnd = dpnd->d_next)
						;
					dpnd->d_next = z_dpnd_pkgs;
					z_dpnd_pkgs->d_prev = dpnd;
				} else {
					dpnd_pkgs = z_dpnd_pkgs;
				}
			}
		}
	}

	/*
	 * set the view of the product back to global root if we
	 * loaded the view for a nonglobal zone
	 */
	if (loaded_nonglobal_zone) {
		(void) load_view(prod, get_localmedia());
	}

	if (dpnd_pkgs != NULL) {
		set_depend_pkgs(dpnd_pkgs);
		return (B_TRUE);
	} else {
		return (B_FALSE);
	}
}

/*
 * _check_sw_depends()
 *	Walk the product view detecting packages that have dependencies
 *	on other packages which are not SELECTED.
 * Parameters:
 *	prod		- Product Module
 * Return:
 *	Depend *	- list of selected packages that have dependencies
 *			on unselected packages
 *	NULL		- selected packages do not have dependencies on
 *			unselected packages
 */
static Depend *
_check_sw_depends(Module *prod)
{
	Node	*pkg = prod->info.prod->p_packages->list;
	Depend	*dpnd;
	Depend	*dpnd_pkgs = (Depend *)NULL;
	Node	*np;
	Modinfo	*inst;
	Modinfo *p_data, *n_data;
	int	i;

	for (pkg = pkg->next; pkg != prod->info.prod->p_packages->list;
	    pkg = pkg->next) {
		p_data = (Modinfo *)pkg->data;
		if (SELECTED(p_data)) {
			/*
			 * walk the 'pdepends' list for the given package
			 * for each pdependency of this package
			 *   if pre-requisite package not selected
			 *			(pkgid, arch & version match)
			 *   add pre-requisite package to list of unsat pdepends
			 */
			for (dpnd = p_data->m_pdepends; dpnd;
			    dpnd = dpnd->d_next) {
				if ((np = findnode(prod->info.prod->p_packages,
				    dpnd->d_pkgid)) == (Node *)NULL) {
					/* package is not in hash list */
					continue;
				}
				n_data = (Modinfo *)np->data;

				if (dpnd->d_arch || dpnd->d_version) {
					for (inst = n_data;
					    inst != (Modinfo *)NULL;
					    inst = next_inst(inst)) {
						/*
						 * if dpnd->d_arch == NULL
						 * or dpnd->d_version == NULL
						 * bypass strcmp() calls and
						 * call the test successful
						 */
						if (((dpnd->d_arch == NULL) ||
						    supports_arch(dpnd->d_arch,
						    inst->m_arch)) &&
						    ((dpnd->d_version ==
						    NULL) ||
						    strcmp(inst->m_version,
						    dpnd->d_version) == 0) &&
						    SELECTED(inst) == 0) {
							dpnd_pkgs =
							    add_depend_pkg(
							    dpnd_pkgs,
							    p_data->m_pkgid,
							    inst->m_pkgid,
							    PREREQUISITE);
						}
					}
				} else if (SELECTED(n_data) == 0) {
					dpnd_pkgs = add_depend_pkg(dpnd_pkgs,
					    p_data->m_pkgid, n_data->m_pkgid,
						PREREQUISITE);
				}
			}
			/*
			 * idepends:
			 * for each idependency of this package
			 *   if idependency package is selected
			 *	 (pkgid, arch & version match)
			 *   add idependency package to list of unsat idepends
			 */
			for (dpnd = p_data->m_idepends; dpnd;
			    dpnd = dpnd->d_next) {
				if ((np = findnode(prod->info.prod->p_packages,
				    dpnd->d_pkgid)) == (Node *)NULL) {
					/* unk pkg specified as dependency */
					continue;
				}
				n_data = (Modinfo *)np->data;

				if (SELECTED(n_data) == 0) {
					if (!dpnd->d_arch && !dpnd->d_version) {
						continue; /* error */
					}
				}

				for (inst = n_data; inst != (Modinfo *)NULL;
				    inst = next_inst(inst)) {
					/*
					 * if dpnd->d_arch == NULL
					 * or dpnd->d_version == NULL
					 * bypass strcmp() calls and
					 * call the test successful
					 */
					if (((dpnd->d_arch == NULL) ||
					    supports_arch(
					    dpnd->d_arch, inst->m_arch)) &&
					    ((dpnd->d_version == NULL) ||
					    strcmp(inst->m_version,
					    dpnd->d_version) == 0) &&
					    SELECTED(inst) == 0) {
						dpnd_pkgs = add_depend_pkg(
						    dpnd_pkgs, inst->m_pkgid,
						    p_data->m_pkgid,
						    INCOMPATIBLE);
					}
				}
			}

			/*
			 * If package is a virtual package, add in
			 * the install dependencies.  Virtual
			 * packages require installation of Java so
			 * that they can be installed after the system
			 * is rebooted.
			 */
			if (p_data->m_flags & IS_VIRTUAL_PKG) {
				for (i = 0; install_deps[i]; i++) {
					if ((np = findnode(prod->
						    info.prod->p_packages,
						    install_deps[i]))
					    == (Node *)NULL) {
					/* unk pkg specified as dependency */
						continue;
					}
					n_data = (Modinfo *)np->data;
					if (!SELECTED(n_data)) {
						dpnd_pkgs = add_depend_pkg(
							dpnd_pkgs,
							    p_data->m_pkgid,
							    n_data->m_pkgid,
							    INSTALL);
					}
				}
			}

		} else {   /* package not selected */
			/*
			 * rdepends:
			 * for each rdependency of this package
			 *	if rdependency package is selected
			 *		(pkgid, arch & version match)
			 *		add package to list of unsat rdepends
			 */
			for (dpnd = p_data->m_rdepends; dpnd;
			    dpnd = dpnd->d_next) {
				if ((np = findnode(prod->info.prod->p_packages,
				    dpnd->d_pkgid)) == (Node *)NULL) {
					/* unk pkg specified as dependency */
					continue;
				}
				n_data = (Modinfo *)np->data;

				if (SELECTED(n_data) != 1)
					continue;

				if (!dpnd->d_arch && !dpnd->d_version) {
					dpnd_pkgs = add_depend_pkg(dpnd_pkgs,
					    n_data->m_pkgid, p_data->m_pkgid,
						REVERSE);
					continue;
				}

				for (inst = n_data; inst != (Modinfo *)NULL;
				    inst = next_inst(inst)) {
					/*
					 * if dpnd->d_arch == NULL
					 * or dpnd->d_version == NULL
					 * bypass strcmp() calls and
					 * call the test successful
					 */
					if (((dpnd->d_arch == NULL) ||
					    supports_arch(
					    dpnd->d_arch, inst->m_arch)) &&
					    ((dpnd->d_version == NULL) ||
					    strcmp(inst->m_version,
					    dpnd->d_version) == 0) &&
					    SELECTED(inst) == 0) {
						dpnd_pkgs = add_depend_pkg(
						    dpnd_pkgs, inst->m_pkgid,
							p_data->m_pkgid,
							REVERSE);
					}
				}
			}
		}
	}

	return (dpnd_pkgs);
}

/*
 * add_depend_instance()
 * Insert a new depend structure into the linked list referenced
 * by 'dpp'. Initialize with 'pkgid'.
 * Parameters:	dpp	- pointer to head of depend link list; modified
 *			  only if the list was NULL
 *		pkgid	- package id initialization string
 * Return:	NULL	- Error: could not allocate a Depend structure
 *		Depend*	- pointer to newly created Depend structure
 * Note:	alloc routine. Should add the entries to the front of
 *		the list to improve performance
 */
static Depend *
add_depend_instance(Depend **dpp, char *pkgid)
{
	Depend 	*newdp, *walkdp;

	/* create the new depend structure and initialize it */
	newdp = (Depend *)xcalloc(sizeof (Depend));
	if (newdp == (Depend *)NULL)
		return ((Depend *)NULL);

	newdp->d_pkgid = xstrdup(pkgid);

	/* add the new structure to the *dpp linked list */
	if (*dpp == (Depend *)NULL)
		*dpp = newdp;
	else {
		for (walkdp = *dpp; walkdp->d_next; walkdp = walkdp->d_next)
			;
		walkdp->d_next = newdp;
		newdp->d_prev = walkdp;
	}

	return (newdp);
}

/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * parse_instance_spec()
 *	Set the 'arch' or the 'version' fields of the Depend parameter
 *	structure according to the value in the 'cp' instance specification
 *	string. Valid values for 'cp' are:
 *
 * 		(<arch>)<version>
 *		(<arch>)
 *		version
 * Parameters:
 *	dp	- pointer to depend structure
 *	cp	- string containing instance specification string
 * Returns:
 *	none
 * Status:
 *	semi-private
 * Note:
 *	There is nothing to handle error conditions in this routine
 */
void
parse_instance_spec(Depend *dp, char *cp)
{
	char	*cp1, *cp2;

	if (dp == (Depend *)NULL)
		return;

	if (*cp == '(') {
		if ((cp1 = strrchr(cp, ')')) == NULL)
			/*
			 * This is an error, but there is no way to return
			 * that fact.
			 */
			return;
		cp2 = cp1 + 1;
		if (cp2 && *cp2) {
			/* (<arch>)<version> */
			dp->d_version = (char *)xstrdup(cp2);
			*cp1 = '\0';
			dp->d_arch = (char *)xstrdup(cp+1);
		} else {
			/* (<arch>) only */
			*cp1 = '\0';
			dp->d_arch = (char *)xstrdup(cp+1);
		}
	} else
		/* <version> */
		dp->d_version = (char *)xstrdup(cp);
}

/*
 * read_pkg_depends()
 *	Open the "depend" file and create depend chains from the input.
 * Parameters:
 *	prod	- product module pointer
 *	info	- modinfo structure pointer
 * Return:
 *	none
 * Note:
 *	This routine does not check to see if there are already
 *	depend chains hooked to 'info'. This could be a possible
 *	memory leak.
 * Status:
 *	semi-private (internal library use only)
 */
void
read_pkg_depends(Module * prod, Modinfo * info)
{
	FILE	*fp = (FILE *)NULL;
	char	path[MAXPATHLEN];
	char	buf[BUFSIZ + 1];
	Depend	*dp, **dpp;
	int	len;
	boolean_t has_whitespace;

	/*
	 * open "depend" file for package, and reset the P, I, R fields in the
	 * modinfo structure
	 */
	if (prod->parent->info.media->med_type == INSTALLED ||
	    prod->parent->info.media->med_type == INSTALLED_SVC)
		len = snprintf(path, sizeof (path), "%s/%s/%s/install/depend",
		    get_rootdir(), prod->info.prod->p_pkgdir, info->m_pkg_dir);
	else
		len = snprintf(path, sizeof (path), "%s/%s/install/depend",
		    prod->info.prod->p_pkgdir, info->m_pkg_dir);

	if (len >= sizeof (path))	/* buffer over flow */
		return;

	if (path_is_readable(path) == FAILURE)
		return;

	fp = fopen(path, "r");
	info->m_pdepends = info->m_idepends = info->m_rdepends = NULL;
	dp = (Depend *)NULL;

	/*
	 * parse out dependency info.  keep three lists, one each for P, I, R
	 * dependenecies.  Remember most recent dependency package(dp) since
	 * we may have to deal with instance specifiers later.
	 */
	while (fgets(buf, BUFSIZ, fp)) {

		if (isspace(buf[0])) {
			has_whitespace = B_TRUE;
		} else {
			has_whitespace = B_FALSE;
		}

		trim_whitespace(buf);

		/* ignore comment fields and NULL lines */
		if (strlen(buf) == 0 || buf[0] == '#') {
			continue;
		}

		/*
		 * instance specifications for previous depend lines
		 * start with white space
		 */
		if (has_whitespace) {
			parse_instance_spec(dp, buf);
		} else {
			switch (buf[0]) {
			case 'P':
				dpp = &info->m_pdepends;
				break;
			case 'I':
				dpp = &info->m_idepends;
				break;
			case 'R':
				dpp = &info->m_rdepends;
				break;
			default:
				continue;
			}
			dp = add_depend_instance(dpp, parse_depend_pkgid(buf));
		}
	}
	(void) fclose(fp);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * parse_depend_pkgid()
 *	Parse a depend line for the pkgid.
 * Parameters:
 *	buf	- buffer containing line from depend file
 * Return:
 *	char *	- pkgid  string parsed out of 'buf'
 *	NULL 	- invalid string
 * Status:
 *	private
 */
static char *
parse_depend_pkgid(char *buf)
{
	char *cp;

	if (strtok(buf, WHITESPACE) == NULL) {
		/* no tokens at all */
		return (NULL);
	}

	if ((cp = strtok(NULL, WHITESPACE)) == NULL) {
		/* only one token on the line */
		return (NULL);
	}

	/* return the second token (the package name) */
	return (cp);
}

/*
 * add_depend_pkg()
 *	Create a Depend structure, initialize it to the parameter data, and add
 *	it to the end of the list of of Depend structures pointed to by
 *	'dpnd_pkgs'.
 * Parameters:
 *	dpnd_pkgs	- pointer to existing Depend list, or NULL
 *			  if starting a new list
 *	pkgid		- package ID to initialize the depend structure
 *	pkgidb		- data structure to initialize the depend structure
 *	type		- Type of dependency (prereq, reverse,
 *			  incompatible, install)
 * Return:
 *	Depend *	- pointer to new Depend structure if new depend list,
 *			  or 'dpnd_pkgs' if adding to an existing list
 *	NULL		- xalloc failed
 * Status:
 *	private
 * Note:
 *	alloc routine
 */
static Depend *
add_depend_pkg(Depend *dpnd_pkgs, char *pkgid, char *pkgidb, DependType type)
{
	Depend	*dp = (Depend *)xcalloc(sizeof (Depend));
	Depend	*tmp, *last;

	/* xalloc check */
	if (dp == (Depend *)NULL)
		return ((Depend *)NULL);

	dp->d_pkgid = pkgid;
	dp->d_pkgidb = (char *)xstrdup(pkgidb);
	dp->d_type = type;

	if (dpnd_pkgs == (Depend *)NULL)
		dpnd_pkgs = dp;
	else {
		for (last = tmp = dpnd_pkgs; tmp; last = tmp, tmp = tmp->d_next)
			;
		last->d_next = dp;
		dp->d_prev = last;
	}

	return (dpnd_pkgs);
}

/*
 * set_depend_pkgs()
 *	Set the global "dependencies" to the parameter value.
 *	If the global "dependencies" is not null, free it first.
 * Parameters:
 *	dp	- depend packages structure pointer
 * Returns:
 *	none
 * Status:
 *	private
 */
static void
set_depend_pkgs(Depend * dp)
{
	Depend	*next;

	/* Free the existing global "dependencies" if they exist. */
	while (dependencies != NULL) {
		next = dependencies->d_next;
		free(dependencies->d_pkgidb);
		free(dependencies);
		dependencies = next;
	}

	dependencies = dp;
}
