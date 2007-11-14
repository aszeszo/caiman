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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)prodreg_browse.c	1.3	06/02/27 SMI"

/*
 * prodreg_browse.c
 *
 * Show browsing from the top as well as reserved, nodes.
 * This is subtle because the information comes from the registry
 * database as well as the package database.  The tree which is
 * shown in the prodreg GUI must be simulated on the command
 * line interface.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <ndbm.h>
#include <string.h>
#include <sys/fcntl.h>
#include <assert.h>
#include <wsreg.h>

#include "prodreg_cli.h"

/* Declarations of functions present in this module. */

static int browse_reg_pkgs(const char *pcroot, Criteria criteria);
static void browse_sys_component(int, Wsreg_component **, Wsreg_component *,
    Wsreg_component **_c);
static void browse_root(Wsreg_component **, Wsreg_component **);
static void browse_by_criteria(Wsreg_component **,
    const char *, const char *, int);
static void browse_additional(Wsreg_component **);
static void browse_solsw(Wsreg_component **);
static void browse_entire(Wsreg_component **);
static void browse_sysl(Wsreg_component **);
static void browse_locn(Wsreg_component **);
static void browse_uncl(Wsreg_component **);
static void handle_sys_pkg(Wsreg_component **,
    Wsreg_component **,  Wsreg_component **,
    Wsreg_component **, Wsreg_component *, RootType);
static int browse_system_packages(Wsreg_component **, Criteria);
static Wsreg_component ** getCompByDisplayName(Criteria, int *);

/*
 * progress
 *
 * This routine is used in the call convention of the
 * wsreg_get_sys_pkgs() function to give progress feedback
 * for GUI interaction.  We ignore the results for the CLI.
 */
/*ARGSUSED*/
void
progress(int i) {}

/*
 * expand_children
 *
 * Check the pkgs attribute of a registered compnent.
 * If there are any, check the children array (which could be null).
 * If the pkg is in the pkgs attribute, but not in children array
 * create a new component and add it to the children array (which will
 * have to be reallocated to include it.)
 *
 *   pcroot [IN]     The root for obtaining package info
 *   pws    [IN]     The component
 *   pppws  [IN/OUT] The children array.
 *
 * Returns: Nothing.
 * Side Effects: May reallocate the children array and add some stuff.
 */
static void
expand_children(const char *pcroot,
    Wsreg_component *pws, Wsreg_component ***pppws)
{
	int i, count = 0, more = 0, pos = 0;
	char *pc = NULL, *pcpkgs = wsreg_get_data(pws, "pkgs");
	Wsreg_component **ppws_c = NULL;

	if (pcpkgs == NULL)
		return;
	if (pcroot == NULL) pcroot = "";

	for (pc = nextstr(&pos, pcpkgs); pc != NULL;
	    pc = nextstr(&pos, pcpkgs)) {

		/* If we have no children yet, count it.  */
		if (*pppws == NULL) {
			free(pc);
			more++;
			continue;
		}

		/* If we don't have the child already, count it. */
		for (i = 0; (*pppws) != NULL && (*pppws)[i] != NULL; i++) {
			if (strcmp(wsreg_get_id((*pppws)[i]), pc) != 0)
				more++;
		}
		free(pc);
	}

	if (more == 0)
		return;

	for (i = 0; (*pppws) != NULL && (*pppws)[i] != NULL; i++) count++;
	ppws_c = (Wsreg_component **) malloc((count + more + 1) *
		sizeof (Wsreg_component *));
	if (ppws_c == NULL) fail(PRODREG_MALLOC);
	(void *) memset(ppws_c, 0, (count + more + 1) *
	    sizeof (Wsreg_component *));

	/* Copy the existing children to the new buffer. */
	for (i = 0; i < count; i++) ppws_c[i] = (*pppws)[i];

	/* Create new components for the remaining children. */
	pos = 0;
	i = count;
	for (pc = nextstr(&pos, pcpkgs); pc != NULL;
		pc = nextstr(&pos, pcpkgs)) {
		char *info = NULL;
		/* Create a new component. */
		ppws_c[i] = wsreg_create_component(pc);
		wsreg_set_instance(ppws_c[i], 1);
		/* If possible, get the packages name for display purposes. */
		info = NULL;
		if ((okpkg(pcroot, pc, &info) == 1) && info != NULL) {
			char *pcname = getval(info, "NAME");
			if (pcname != NULL) {
				wsreg_add_display_name(ppws_c[i],
				    global_lang, pcname);
			}
			if (info) free(info);
		}
		i++;
		free(pc);
	}

	*pppws = ppws_c;
}


/*
 * has_unclassified_pkgs
 *
 * Determine whether there are are any unclassified packages.
 *
 *   ppws_all  The system packages.
 *
 * Returns: 1 means yes, 0 means no.
 * Side Effects: none
 */
static int
has_unclassified_pkgs(Wsreg_component **ppws_all)
{
	int i;
	for (i = 0; ppws_all[i] != NULL; i++) {
		Wsreg_component *pwsp =
			wsreg_get_parent_reference(ppws_all[i]);
		char *pcpa;
		char *pcme;

		pcme = wsreg_get_id(ppws_all[i]);
		pcpa = NULL;

		if (pwsp != NULL) pcpa = wsreg_get_id(pwsp);
		wsreg_free_component(pwsp);

		if ((pcme && strcmp(pcme, UNCL_UUID) == 0) ||
		    (pcpa && strcmp(pcpa, UNCL_UUID) == 0))
			return (1);

	}
	return (0);
}

/*
 * browse_root
 *
 * Outputs the browse view from the synthetic 'root' component.
 *
 * Returns: Nothing
 * Side effects: None
 */
static void
browse_root(Wsreg_component **ppws_all, Wsreg_component **ppws_syspkgs)
{
	int i;

	browse_header();
	show(NODE, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(CHILD, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	if (has_unclassified_pkgs(ppws_syspkgs))
		show(CHILD, 2, 1, get_bn(UNCL_UUID), UNCL_UUID, 1, UNCL_STR);

	/* Do not use browse_by_criteria() - this case is too special. */
	for (i = 0; ppws_all[i] != NULL; i++) {
		Wsreg_component *pws = wsreg_get_parent_reference(ppws_all[i]);
		Wsreg_component *p = ppws_all[i];
		int j = (p->children == NULL)?0:1;

		if (pws == NULL) {
			show(CHILD, 2, j, get_bn(p->id), p->id, p->instance,
			    wsreg_get_display_name(p, global_lang));
		}

		if (pws) wsreg_free_component(pws);
	}
}

/*
 * browse_by_criteria
 *
 * The array ppws_sysp is searched to show (as browse input) a component
 * whose uuid is given, or the uuid of its parent (shows all children).
 *
 * It is an error for both id_self and id_parent to be non-NULL.  If in
 * fact they are, id_self is used.
 *
 *   ppws_sysp   The components on the system.  Reused from elsewhere
 *               to improve performance.
 *   id_self     The uuid of a component to show.  May be NULL
 *   id_parent   The uuid of a parent whose children are to be shown.
 *               May be NULL.
 *   indent      The number of spaces to indent the 'tree' representation.
 *
 * Returns: Nothing
 * Side effects: None
 */
static void
browse_by_criteria(Wsreg_component **ppws_sysp,
			const char *id_self,
			const char * id_parent, int indent)
{
	int i;

	assert(((id_self != NULL) && (id_parent == NULL)) ||
	    ((id_self == NULL) && (id_parent != NULL)));

	for (i = 0; ppws_sysp[i] != NULL; i++) {
		Wsreg_component *pws =
		    wsreg_get_parent_reference(ppws_sysp[i]);
		Wsreg_component *p = ppws_sysp[i];
		int j = (p->children == NULL)?0:1;

		/*
		 * Unclassified software and Solaris {} System Software are
		 * listed.  These are shown elsewhere by the 'top-level'
		 * browsing in the GUI so they must be filtered as special
		 * cases here.
		 */
		if (0 == strcmp(p->id, SYSS_UUID)) continue;
		if (0 == strcmp(p->id, UNCL_UUID)) continue;

		if (id_self != NULL && 0 == strcmp(p->id, id_self)) {

			show(CHILD, indent, j, get_bn(p->id), p->id,
			    p->instance,
			    wsreg_get_display_name(p, global_lang));

		} else if ((id_self == NULL && pws == NULL) ||
		    (pws != NULL && id_parent != NULL &&
			0 == strcmp(pws->id, id_parent))) {

			show(CHILD, indent, j, get_bn(p->id),
			    p->id, p->instance,
			    wsreg_get_display_name(p, global_lang));

		}

		wsreg_free_component(pws);
	}
}

/*
 * hasChildren
 *
 * Determines if a component has children.  This is used for browse output
 * decoration.
 *
 *   pc         The name of a component.
 *   ppws_sysp  The array of components on the system, reused to improve
 *              performance.
 *
 * Returns: 0 if no children, 1 if children.
 * Side effects: None
 */
static int
hasChildren(const char *pc, Wsreg_component **ppws_sysp)
{
	int i;
	for (i = 0; ppws_sysp[i]; i++) {
		if (ppws_sysp[i] != NULL &&
		    strcmp(ppws_sysp[i]->id, pc) == 0) {

			Wsreg_component **p =
			    wsreg_get_child_references(ppws_sysp[i]);
			if (p == NULL)
				return (0);
			wsreg_free_component_array(p);
			return (1);
		}
	}
	return (0);
}

/*
 * browse_additional
 *
 * This outputs the browse view from the additional node.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_additional(Wsreg_component **ppws_sysp)
{

	int x = hasChildren(ADDL_UUID, ppws_sysp);
	browse_header();
	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	show(NODE, 3, x, get_bn(ADDL_UUID), ADDL_UUID, 1, ADDL_STR);
	if (x != 0) browse_by_criteria(ppws_sysp, NULL, ADDL_UUID, 4);
}

/*
 * browse_solsw
 *
 * This outputs the browse view from the solaris software node.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_solsw(Wsreg_component **ppws_sysp)
{
	int i;
	browse_header();

	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(NODE, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	show(CHILD, 3, 1, get_bn(SYSL_UUID), SYSL_UUID, 1, SYSL_STR);

	for (i = 0; ppws_sysp[i] != NULL; i++) {
		Wsreg_component *pws =
		    wsreg_get_parent_reference(ppws_sysp[i]);
		Wsreg_component *p = ppws_sysp[i];
		int j = (p->children == NULL)?0:1;

		/*
		 * Unclassified software and Solaris {} System Software are
		 * listed.  These are shown elsewhere by the 'top-level'
		 * browsing in the GUI so they must be filtered as special
		 * cases here.
		 */
		if (0 == strcmp(p->id, SYSS_UUID)) {
			continue;
		}

		if (0 == strcmp(p->id, UNCL_UUID)) {
			continue;
		}

		if (0 == strcmp(p->id, global_ENTR_UUID)) {
			show(CHILD, 3, j, get_bn(p->id), p->id,  p->instance,
			    wsreg_get_display_name(p, global_lang));
		}

		if (pws == NULL) {
			show(CHILD, 3, j, get_bn(p->id), p->id, p->instance,
			    wsreg_get_display_name(p, global_lang));
		}
		wsreg_free_component(pws);
	}
}

/*
 * browse_entire
 *
 * This outputs the browse view from the 'entire software distribution'.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_entire(Wsreg_component **ppws_sysp)
{
	browse_header();
	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	show(NODE, 3, 1, get_bn(global_ENTR_UUID), global_ENTR_UUID, 1,
	    ENTR_STR);
	browse_by_criteria(ppws_sysp, NULL, global_ENTR_UUID, 4);
}

/*
 * browse_sysl
 *
 * This outputs the browse view from the system localizations node.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_sysl(Wsreg_component **ppws_sysp)
{
	int i = hasChildren(SYSL_UUID, ppws_sysp);
	browse_header();
	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	show(NODE, 3, i, get_bn(SYSL_UUID), SYSL_UUID, 1, SYSL_STR);
	if (i != 0) browse_by_criteria(ppws_sysp, NULL, SYSL_UUID, 4);
}

/*
 * browse_locn
 *
 * This outputs the browse view from the localization node.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_locn(Wsreg_component **ppws_sysp)
{
	int i = hasChildren(LOCL_UUID, ppws_sysp);
	browse_header();
	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1, global_solver);
	show(NODE, 3, i, get_bn(LOCL_UUID), LOCL_UUID, 1, LOCL_STR);
	if (i != 0) browse_by_criteria(ppws_sysp, NULL, LOCL_UUID, 4);
}

/*
 * browse_uncl
 *
 * This outputs the browse view from the unclassified software node.
 *
 * Returns: Nothing
 * Side effects: None
 */

static void
browse_uncl(Wsreg_component **ppws_sysp)
{
	int i = hasChildren(UNCL_UUID, ppws_sysp);
	if (i == 0) fail(PRODREG_NO_SUCH_COMPONENT);
	browse_header();
	show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
	show(NODE, 2, i, get_bn(UNCL_UUID), UNCL_UUID, 1, UNCL_STR);
	if (i != 0) browse_by_criteria(ppws_sysp, NULL, UNCL_UUID, 3);
}

/*
 * handle_sys_pkg
 *
 * This performs a browse command on all system packages.
 *
 *    ppws_sysp      The array of registered system components.  This is
 *                   allocated elsewhere and reused to improve performance.
 *    ppws_parent    The array of parents, going back to the root.
 *    ppws_children  An array of children of the component to show.
 *    ppws_ambig     An array (which may be absent) of ambiguous nodes.
 *    pws            The node itself, to view.
 *    rtype          The type of the root to view.  If it is a special
 *                   synthetic node, the function handles it with
 *                   distinct code.  If AMBIG, then the ppws_ambig array
 *                   is used to show the ambiguous values.
 *
 * Returns: Nothing
 * Side effects: Input array values are freed.
 */

static void
handle_sys_pkg(Wsreg_component **ppws_sysp,
    Wsreg_component **ppws_parent,
    Wsreg_component **ppws_children,
    Wsreg_component **ppws_ambig,
    Wsreg_component *pws,
    RootType rtype)
{
	int i;
	Wsreg_component **ppws_all = NULL;

	switch (rtype) {

	case NONE:
		/* Criteria match no node in registry tree. No output. */
		break;

	case AMBIG:
		/*
		 * Criteria matches more than one node in the registry tree.
		 * Output possible choices to standard output.
		 */
		(void) printf(PRODREG_AMBIGUOUS_RESULTS);

		browse_header();
		for (i = 0; ppws_ambig[i]; i++) {
			Wsreg_component **p =
			    wsreg_get_child_references(ppws_ambig[i]);
			fill_in_comps(p, ppws_sysp);
			show(NODE, 1, (p)?1:0, get_bn(ppws_ambig[i]->id),
			    ppws_ambig[i]->id, ppws_ambig[i]->instance,
			    wsreg_get_display_name(ppws_ambig[i],
				global_lang));

			if (p) {
				wsreg_free_component_array(p);
			}
		}
		break;

	case LOCL:
		browse_header();
		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
		show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1,
		    global_solver);
		browse_sys_component(3, ppws_parent, pws, ppws_children);
		break;

	case SYSS:
	case ENTIRE:
		browse_header();
		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
		browse_sys_component(3, ppws_parent, pws, ppws_children);
		break;

	case ADDL:
		browse_header();
		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
		show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1,
		    global_solver);
		browse_sys_component(3, ppws_parent, pws, ppws_children);
		break;

	case UNCL:
		browse_header();
		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
		browse_sys_component(2, ppws_parent, pws, ppws_children);
		break;

	case ROOT:
		ppws_all = wsreg_get_all();
		browse_root(ppws_all, ppws_sysp);
		wsreg_free_component_array(ppws_all);
		break;

	case SYSL:
		browse_header();
		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1, ROOT_STR);
		show(PARENT, 2, 1, get_bn(SYSS_UUID), SYSS_UUID, 1,
		    global_solver);
		browse_sys_component(3, ppws_parent, pws, ppws_children);
		break;

	default:
		/* search_sys_pkgs returns only the above values */
		assert(0);
	}

	if (ppws_ambig) {
		wsreg_free_component_array(ppws_ambig);
	}

	if (ppws_parent) {
		wsreg_free_component_array(ppws_parent);
	}

	if (ppws_children) {
		wsreg_free_component_array(ppws_children);
	}

	if (pws) {
		wsreg_free_component(pws);
	}
}

/*
 * browse_sys_component
 *
 *   Output a particular system component, its ancestors and children.
 *
 *  indentation    The number of nodes indented.
 *  ppws_p         Pointer to the parents of the node.
 *  pws            Pointer to the node.
 *  ppws_c         Pointer to the children of the node.
 *
 * Returns:  Nothing
 * Side effects: None
 */
static void
browse_sys_component(int indentation,
    Wsreg_component **ppws_p,
    Wsreg_component *pws,
    Wsreg_component **ppws_c)
{
	int i;

	if (ppws_p) {
		if (0 == strcasecmp(ppws_p[0]->id, global_ENTR_UUID)) {
			show(PARENT, indentation++, 1, get_bn(SYSS_UUID),
			    SYSS_UUID, 1, global_solver);
		}

		for (i = 0; ppws_p[i]; i++) {
			show(PARENT, indentation++, 1,
			    get_bn(ppws_p[i]->id), ppws_p[i]->id,
			    wsreg_get_instance(ppws_p[i]),
			    wsreg_get_display_name(ppws_p[i],
				global_lang));
		}
	}

	show(NODE, indentation++, (ppws_c)?1:0, get_bn(pws->id), pws->id,
	    wsreg_get_instance(pws),  wsreg_get_display_name(pws,
		global_lang));

	if (ppws_c) {
		for (i = 0; ppws_c[i]; i++) {
			char *pc = wsreg_get_display_name(ppws_c[i],
			    global_lang);
			show(CHILD, indentation, (ppws_c[i]->children)?1:0,
			    get_bn(ppws_c[i]->id), ppws_c[i]->id,
			    wsreg_get_instance(ppws_c[i]), pc);
		}
	}
}

/*
 * browse_system_packages
 *
 * This wraps the handle_sys_pkgs call and ensures that the values
 * have been obtained by search_sys_pkgs and filled in to correct
 * for libwsreg shortcomings before shown.
 *
 *    ppws_sysp      The array of registered system components.  This is
 *                   allocated elsewhere and reused to improve performance.
 *    criteria       The search conditions for the component.
 *
 * Returns: 0 on success, >0 on failure
 * Side effects: none
 */
static int
browse_system_packages(Wsreg_component **ppws_sysp, Criteria criteria)
{
	Wsreg_component **ppws_parent = NULL,
	    **ppws_children = NULL,
	    **ppws_ambig = NULL,
	    *pws = NULL;
	RootType rtype = NONE;

	/*
	 * Get the ancestry and children of the node based on
	 * the criteria.  Do not rely on the search function
	 * to know about how to represent the data - that will
	 * be done here.  The search function will show ambig-
	 * uous results, however.
	 */
	if (search_sys_pkgs(ppws_sysp, &ppws_parent, &ppws_children,
	    &ppws_ambig, &pws, &rtype, criteria)) {

		fill_in_comps(ppws_children, ppws_sysp);

		handle_sys_pkg(ppws_sysp, ppws_parent, ppws_children,
		    ppws_ambig, pws, rtype);
		return (0);
	} else {
		return (1);
	}
}

/*
 * getCompByDisplayName
 *
 *   Search the registry for a uuid corresponding to a particular
 *   display name.  More than one such component can be returned!
 *   Searches only the registry.
 *
 * Parameters:
 *
 *    criteria   The search criteria (by name!)
 *    pi         The number of matches.
 *
 * Return:
 *   NULL if there is no match.
 *   An null terminated array of components is returned if there is a
 *   match.
 *
 * Side effects:  None.
 *
 */

static Wsreg_component **
getCompByDisplayName(Criteria criteria, int *pi) {

	int max = 0, num = 0, h;

	Wsreg_component **ppws_byname = NULL;
	char *pcstr = NULL;
	Wsreg_component **ppws_scan = NULL;
	*pi = 0;

	resize_if_needed(num, &max, &ppws_byname, sizeof (Wsreg_component *));

	ppws_scan = wsreg_get_all();

	for (h = 0; ppws_scan[h]; h++) {
		pcstr = wsreg_get_display_name(ppws_scan[h], global_lang);
		if (pcstr == NULL) {
			/* This component has no display name, can't match. */
			continue;
		}

		if (0 == strcasecmp(pcstr, criteria.displayname)) {

			if (criteria.mask & FIND_INST &&
			    criteria.instance !=
			    ppws_scan[h]->instance) {
				continue;
			}

			if (criteria.mask & FIND_LOCN &&
			    strcmp(ppws_scan[h]->location,
				criteria.location)) {
				continue;
			}

			ppws_byname[num++] =
			    wsreg_clone_component(ppws_scan[h]);

			resize_if_needed(num, &max, &ppws_byname,
			    sizeof (Wsreg_component *));
		}
	}

	*pi = num;

	if (ppws_scan) {
		wsreg_free_component_array(ppws_scan);
	}

	if (num == 0) {
		free(ppws_byname);
		ppws_byname = NULL;
	}

	return (ppws_byname);
}

/*
 * check_ambig
 *
 * Returns an ambiguous array by making a special request to the
 * prodreg_get_component function.
 *
 *  pcRoot     The possibly alternate root for registry operations.
 *  criteria   The search criteria for the component.
 *  ppws       The array of system components are requested by
 *             prodreg_get_component.  If this is NULL, nothing
 *             is returned.  If ppws is the location of a valid
 *             pointer, then the array of system components is
 *             returned - to facilitate optimized query performance.
 *             The array can then be reused elsewhere and later freed.
 *  pidone     Determines if we have found the component, and are done.
 *
 * Returns: A newly allocated array of components.  The caller must free them.
 *    If NULL, there is no ambiguous component.
 * Side effects: None
 */

static Wsreg_component **
check_ambig(const char *pcRoot, Criteria criteria, Wsreg_component **ppws,
	int *pidone)
{
	Wsreg_component **ppws_ambig = NULL;
	Wsreg_component *pws = NULL;
	pws = prodreg_get_component(pcRoot, criteria, 0, &ppws_ambig, &ppws);
	*pidone = 0;
	if (!pws) {
		if (browse_reg_pkgs(pcRoot, criteria) > 0)
			fail(PRODREG_NO_SUCH_COMPONENT);
		else
			*pidone = 1;
	}
	if (pws) wsreg_free_component(pws);
	return (ppws_ambig);
}

/*
 * browse_reg_pkgs
 *
 * This searches for pkgs under registry items.  It will output browse
 * information for the pkgs, if found.
 *
 *   pcroot      The alternate root.
 *   criteria    The search criteria.
 *
 * Return: 0 if successful.  > 0 otherwise.
 * Side effects: none
 */
static int
browse_reg_pkgs(const char *pcroot, Criteria criteria)
{
	int i, result = 1, x;
	char *pkgs = NULL;
	char *pc = NULL;
	char *pcname = NULL;
	char *pkgi = NULL;
	Wsreg_component **pp = wsreg_get_all();
	Wsreg_component *pws_parent = NULL;

	if (pcroot == NULL) pcroot = "";

	/* Only instance = 1 is possible, with these packages. */
	if (criteria.mask & FIND_INST && criteria.instance != 0)
		return (result);

	for (i = 0; result == 1 && pp != NULL && pp[i] != NULL; i++) {
		if ((pkgs = wsreg_get_data(pp[i], "pkgs")) == NULL)
			continue;
		x = 0;
		for (pc = nextstr(&x, pkgs); result == 1 && pc != NULL;
		    pc = nextstr(&x, pkgs)) {

			if (okpkg(pcroot, pc, &pkgi) == 1) {
				pcname = getval(pkgi, "NAME");
			}

			if (criteria.mask & FIND_UUID &&
			    strncmp(criteria.uuid, pc, strlen(pc)+1) == 0) {

				/* Found the component & parent ! */
				pws_parent = pp[i];
				result = 0;
				break;

			} else if ((criteria.mask & FIND_NAME) &&
			    (pcname != NULL) &&
			    (strncmp(criteria.displayname,
				pcname, strlen(pcname) + 1) == 0)) {

				/* Found the component & parent ! */
				pws_parent = pp[i];
				result = 0;
				break;
			}
			if (pc) free(pc);
			if (pkgi) free(pkgi);
			if (pcname) free(pcname);
			pcname = NULL;
			pkgi = NULL;
		}
	}

	if (result == 0) {

		Wsreg_component *ppwsp[32];
		Wsreg_component *pwst = NULL, *pwsx = NULL;
		int i, count = 0;

		if (pcname == NULL) pcname = "";

		/* Get the ancestry stuffed into the ppwsp array in order. */
		for (i = 0; i < 32; i++) ppwsp[i] = NULL;

		ppwsp[count++] = pws_parent;
		pwsx = pws_parent;
		while ((pwst = wsreg_get_parent(pwsx)) != NULL) {
			if (count == 32) break;
			ppwsp[count++] = pwst;
			pwsx = pwst;
		}

		browse_header();

		show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1,
		    ROOT_STR);

		for (i = (count - 1); i >= 0; i--) {
			show(PARENT, (count - i) + 2, 1,
			    get_bn(wsreg_get_id(ppwsp[i])),
			    wsreg_get_id(ppwsp[i]),
			    wsreg_get_instance(ppwsp[i]),
			    wsreg_get_display_name(ppwsp[i], global_lang));

			/* Free parents, but not 1st parent (its in pp). */
			if (i > 0)
				wsreg_free_component(ppwsp[i]);
		}

		show(NODE, count + 3, 0, get_bn(pc), pc, 1, pcname);
	}

	if (pc) free(pc);
	if (pcname) free(pcname);
	if (pp) wsreg_free_component_array(pp);

	return (result);
}

/*
 * browse_request
 *
 * This is the entry point for browse requests.
 *
 *   pcroot    The (potentially) alternate root for registry operations.
 *   criteria  The search parameters for components to browse.
 *
 * Returns: Nothing
 * Side effects: None
 */
void
browse_request(const char *pcroot, Criteria criteria)
{
	Wsreg_component **ppws_all = NULL, **ppws_sysp = NULL;

	if (pcroot[0] == '\0') pcroot = NULL;

	if (wsreg_initialize(WSREG_INIT_NORMAL, pcroot) != WSREG_SUCCESS) {
		fail(PRODREG_CONVERT_NEEDED_ACCESS);
	}

	if (wsreg_can_access_registry(O_RDONLY) == 0) {
		fail(PRODREG_CANNOT_READ);
	}

	db_open();

	ppws_sysp = wsreg_get_sys_pkgs(progress);

	/* Determine if the pcUUID is any of the special values. */
	if (SPECIALROOT(criteria, ROOT_UUID, ROOT_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		ppws_all = wsreg_get_all();
		browse_root(ppws_all, ppws_sysp);
		wsreg_free_component_array(ppws_all);
		goto browse_request_done;
	}

	if (SPECIALROOT(criteria, UNCL_UUID, UNCL_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_uncl(ppws_sysp);

	} else if (SPECIALROOT(criteria, LOCL_UUID, LOCL_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_locn(ppws_sysp);

	} else if (SPECIALROOT(criteria, ADDL_UUID, ADDL_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_additional(ppws_sysp);

	} else if (SPECIALROOT(criteria, SYSS_UUID, global_solver)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_solsw(ppws_sysp);

	} else if (SPECIALROOT(criteria, global_ENTR_UUID, ENTR_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_entire(ppws_sysp);

	} else if (SPECIALROOT(criteria, SYSL_UUID, SYSL_STR)) {

		if (criteria.mask & FIND_INST && criteria.instance != 1)
			fail(PRODREG_NO_SUCH_COMPONENT);
		browse_sysl(ppws_sysp);

	} else {

		/* Search for the desired element */

		Wsreg_component *pws = NULL;
		int done = 0;
		Wsreg_component **ppws_ambig =
		    check_ambig(pcroot, criteria, ppws_sysp, &done);

		if (done) goto browse_request_done;

		if (ppws_ambig != NULL) {
			goto browse_request_done;
		}

		if (criteria.mask & FIND_NAME) {

			int j = 0;
			Wsreg_component **ppws_byname =
			    getCompByDisplayName(criteria, &j);

			if (ppws_byname == NULL) {

				(void) browse_system_packages(ppws_sysp,
					criteria);
				goto browse_request_done;
			} else {

				pws = ppws_byname[0];
				free(ppws_byname);
			}
		}

		if (criteria.mask & FIND_UUID) {
			Wsreg_query *pq = wsreg_query_create();
			wsreg_query_set_id(pq, criteria.uuid);

			if (criteria.mask & FIND_LOCN) {

				wsreg_query_set_location(pq,
				    criteria.location);

			} else if (criteria.mask & FIND_INST) {

				wsreg_query_set_instance(pq,
				    criteria.instance);

			} else {
				/*
				 * The UUID is supplied without a
				 * disambiguating instance or location
				 * criteria.  Check to see if it is
				 * ambiguous.
				 */
				wsreg_query_set_instance(pq, 1);
			}
			pws = wsreg_get(pq);
			wsreg_query_free(pq);
		}

		/*
		 * If we find anything here, it is in the registry,
		 * under root.
		 */
		if (pws != NULL) {

			int j, i = 0, max = 0;
			Wsreg_component **ppws_p = NULL;
			Wsreg_component **ppws_c =
			    wsreg_get_child_components(pws);

			if (NULL == ppws_c) {
				ppws_c = wsreg_get_child_references(pws);
				fill_in_comps(ppws_c, ppws_sysp);
				expand_children(pcroot, pws, &ppws_c);
			}

			if (pws->parent != NULL) {
				resize_if_needed(i, &max, &ppws_p,
				    sizeof (Wsreg_component *));

				if ((ppws_p[i] = wsreg_get_parent(pws))
				    == NULL) {
					ppws_p[i] =
					    wsreg_get_parent_reference(pws);
				}

				/* i = i is for lint. */
				for (i = i; (ppws_p[i + 1] =
				    wsreg_get_parent(ppws_p[i])) != NULL ||
					(ppws_p[i + 1] =
					    wsreg_get_parent_reference(
						    ppws_p[i])) != NULL;
				    i = i) {
					i++;
					resize_if_needed(i, &max, &ppws_p,
					    sizeof (Wsreg_component*));
				}
				/*
				 * Unfortunately,  the list is in reverse
				 * order.  We must now reverse it so we
				 * can go from last ancestor to the first.
				 */
				if (i == 1) {

					/* special case: only 2 elements */
					Wsreg_component *pws_temp =
					    ppws_p[0];
					ppws_p[0] = ppws_p[1];
					ppws_p[1] = pws_temp;

				} else {
					for (j = 0; (j < (i / 2)); j++) {
						Wsreg_component *pws_temp;
						int k = i - j - 1;
						pws_temp = ppws_p[j];
						ppws_p[j] = ppws_p[k];
						ppws_p[k] = pws_temp;
					}
				}
			}

			fill_in_comps(ppws_p, ppws_sysp);

			browse_header();
			show(PARENT, 1, 1, get_bn(ROOT_UUID), ROOT_UUID, 1,
			    ROOT_STR);
			browse_sys_component(2, ppws_p, pws,
			    ppws_c);
			wsreg_free_component(pws);
			if (ppws_p) {
				wsreg_free_component_array(ppws_p);
			}

			if (ppws_c) {
				wsreg_free_component_array(ppws_c);
			}

		} else if (browse_system_packages(ppws_sysp, criteria) > 0) {

			fail(PRODREG_NO_SUCH_COMPONENT);

		}
	}

browse_request_done:
	if (ppws_sysp != NULL)
		wsreg_free_component_array(ppws_sysp);
	db_close();
}
