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
 * Copyright 2002 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


/*
 * prodreg_info.c
 *
 * Show attribute information associated with a particular registered
 * component.
 *
 * The component requested has to not be ambiguous, or else a list of
 * possible components are shown, as for prodreg browse.  This can
 * occur if a uuid without an instance number is given, or a name
 * is given which is ambiguous.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <wsreg.h>
#include "prodreg_cli.h"

/*
 * reg_pkg_info
 *
 * This function fulfills search criteria in attempting to find a package
 * which is listed in the pkgs attribute of a registered package.
 *
 *    pcroot    The alternate root
 *    criteria  The search criteria
 *    pcattr    A specific attribute to print
 *    damage    Output 'isDamaged' value.
 *
 * Returns: 0 if successful, 1 if failed to find the component.
 * Side effects: none.
 */
static int
reg_pkg_info(const char *pcroot, Criteria criteria, const char *pcattr,
    int damage)
{
	int result = 1; /* Assume failure. */
	int i, x, ok = 0;
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

			if ((ok = okpkg(pcroot, pc, &pkgi)) == 1) {
				pcname = getval(pkgi, "NAME");
			}

			if (criteria.mask & FIND_UUID &&
			    strncmp(criteria.uuid, pc, strlen(pc)+1) == 0) {

				/* Found the component! */
				pws_parent = pp[i];
				result = 0;
				break;

			} else if ((criteria.mask & FIND_NAME) &&
			    (pcname != NULL) &&
			    (strncmp(criteria.displayname,
				pcname, strlen(pcname) + 1) == 0)) {

				/* Found the component! */
				pws_parent = pp[i];
				result = 0;
				break;
			}
			free(pc);
			if (pkgi) free(pkgi);
			pkgi = NULL;
			if (pcname) free(pcname);
			pcname = NULL;
		}
	}

	if (result == 0) {
		if (damage) {

			/*
			 * Note:
			 * The following string does not need to be
			 * translated because it is the name of an attribute.
			 * Names of attributes are themselves not translated.
			 */
			(void) printf("isDamaged: %s\n", (ok)?"FALSE":"TRUE");

		} else if (pcattr != NULL) {

			char *val = NULL;

			if (pkgi && strncasecmp(pcattr, "title", 6) == 0) {
				val = getval(pkgi, "NAME");
			} else {
				val = getval(pkgi, pcattr);
			}

			if (val) {
				(void) printf("%s: %s\n", pcattr, val);
				free(val);
			}

		} else {
			if (pcname) (void) printf("Title: %s\n", pcname);
			if (pkgi) (void) printf("%s\n", pkgi);
			(void) printf("Parent Component:\n%s\n",
			    PRODREG_LISTHEAD);
			pretty_comp(pws_parent);
		}
	}

	if (pc) free(pc);
	if (pkgi) free(pkgi);
	if (pp) wsreg_free_component_array(pp);

	return (result);
} 

/*
 * test_damage
 *
 * Determine if a node is damaged.  It is damaged if any pkg it lists
 * in its pkgs attribute is absent in the pkg list, or if isDamaged is
 * set or if any of its children (or their children) is damaged in the
 * ways described above.
 *
 * This is a recursive function whose termination occurs at the leaves
 * of the tree (where the components have no children, or as soon as a
 * damaged component is found.
 *
 *   pws	The component to examine
 *   ppws_sysp  The list of system packages.
 *   pcroot     The alternate root for the prodreg command to run in.
 *
 * Return 1 if damaged, 0 otherwise.
 * Side effects: none.
 */
static int
test_damage(Wsreg_component *pws, Wsreg_component **ppws_sysp,
    const char *pcroot)
{
	int i, j = 0;
	char *pcdam = wsreg_get_data(pws, "isDamaged");
	char *pcpkg = wsreg_get_data(pws, "pkgs");
	char *pc = NULL;

	Wsreg_component **ppws_children = NULL;

	/*
	 * Get sys pkgs.  It is likely it has not been retrieved yet, as
	 * most of the time damaged components are in the registry.
	 */
	if (ppws_sysp == NULL) ppws_sysp = wsreg_get_sys_pkgs(progress);

	/* Test component first.  If damaged return 1. */
	if (pcdam && strcmp(pcdam, "isDamaged: TRUE") == 0) {
		debug(DEBUGINFO, "isDamaged: TRUE found\n");
		return (1);
	}

	debug(DEBUGINFO, "pkgs = [%s], got ppws_sysp? [%s]\n",
	    (pcpkg)?pcpkg:"", (ppws_sysp)?"yes":"no");

	/* For each pkg in the pkgs attribute, ensure it is installed. */
	while (pcpkg && ((pc = nextstr(&j, pcpkg)) != NULL)) {

		debug(DEBUGINFO, "check pkg component '%s' is installed\n",
		    pc);
		if (okpkg(pcroot, pc, NULL) == 0) {
			debug(DEBUGINFO, "did not find pkg %s\n", pc);
			free(pc);
			return (1);
		}
		free(pc);
	}

	/* Test all children.  If any are damaged, return 1. */

	ppws_children = wsreg_get_child_components(pws);
	if (ppws_children == NULL)
		ppws_children = wsreg_get_child_references(pws);

	if (ppws_children == NULL)
		debug(DEBUGINFO, "%s has no children\n", pws->id);

	for (i = 0; ppws_children != NULL && ppws_children[i] != NULL; i++) {

		debug(DEBUGINFO, "-->recursive check of %s\n",
		    ppws_children[i]->id);

		if (test_damage(ppws_children[i], ppws_sysp, pcroot) == 1) {
			wsreg_free_component_array(ppws_children);

			debug(DEBUGINFO, "child [%s] is damaged, so is "
			    "parent [%s]\n",
			    (ppws_children[i]->id)?(ppws_children[i]->id):"",
			    (pws->id)?(pws->id):"");

			return (1);
		}
	}

	if (ppws_children) wsreg_free_component_array(ppws_children);

	/* Once we get to the bottom, we have checked everything, return 0. */
	debug(DEBUGINFO, "no damage for [%s], return 0\n",
	    (pws->id)?(pws->id):"");
	return (0);
}

/*
 * prodreg_create_root
 *
 * Synthesize the root component for viewing the information associated
 * with it.
 *
 *   pp_parent  [OUT]  Root has now parent, returns NULL.
 *   ppp_child  [OUT]  Children of root.
 *
 * Returns:  A newly allocated component.  It must be freed by the caller.
 * Side effects: None.
 */
static Wsreg_component *
prodreg_create_root(Wsreg_component **pp_parent, Wsreg_component ***ppp_child)
{
	int i, count = 0;
	Wsreg_component *pws = wsreg_create_component("root");
	Wsreg_component *pwsu = wsreg_create_component(UNCL_UUID);
	Wsreg_component *pwss = wsreg_create_component(SYSS_UUID);
	Wsreg_component **pp = wsreg_get_all();

	*pp_parent = NULL;

	if ((pws == NULL) || (pwsu == NULL) ||
	    (pwss == NULL) || (pp == NULL) ||
	    (wsreg_set_instance(pws, 1) == 0) ||
	    (wsreg_set_instance(pwsu, 1) == 0) ||
	    (wsreg_set_instance(pwss, 1) == 0) ||
	    (wsreg_add_display_name(pwss, global_lang, global_solver) == 0) ||
	    (wsreg_add_display_name(pwsu, global_lang, UNCL_STR) == 0) ||
	    (wsreg_add_display_name(pws, global_lang, ROOT_STR) == 0))
		fail(PRODREG_FAILED);

	/* All orphan components in the registry have root as parent. */
	for (i = 0; pp[i] != NULL; i++) {
		Wsreg_component *pwsp = wsreg_get_parent(pp[i]);
		if (pwsp == NULL) {
			count++;
		} else {
			wsreg_free_component(pwsp);
		}
	}
	*ppp_child = (Wsreg_component **) malloc((count + 3) *
	    sizeof (Wsreg_component *));
	if (*ppp_child == NULL) fail(PRODREG_MALLOC);

	count = 0;
	for (i = 0; pp[i] != NULL; i++) {
		Wsreg_component *pwsp = wsreg_get_parent(pp[i]);
		if (pwsp == NULL) {
			(*ppp_child)[count] = wsreg_clone_component(pp[i]);
			count++;
		} else {
			wsreg_free_component(pwsp);
		}
	}
	(*ppp_child)[count++] = pwsu;
	(*ppp_child)[count++] = pwss;
	(*ppp_child)[count] = NULL;
	return (pws);
}

/*
 * prodreg_info
 *
 * This will display a list of attribute value pairs associated with a
 * particular component unless (a) the criteria is ambiguous, in which
 * case a list of possible components is output, (b) pcAttr is not null,
 * in which case this one attribute is output, if it is defined,
 * (c) damage is nonzero, in which case the attribute isDamaged=true
 * or isDamaged=false is output.
 *
 * To determine if a product is damaged, one has to look at
 *   o Whether the isDamaged flag attribute is set by libwsreg
 *   o Whether the packages listed in the pkg attribute exist on the
 *     system
 *   o Whether any of the *children* of the component have packages
 *     listed which are not present.
 *
 *   pcRoot    An alternate root, if non-null.
 *   criteria  The component's name, uuid, browse number, etc.
 *   pcAttr    The name of an attribute to return, if the component has it.
 *   damage    If nonzero, show whether a component is damaged or not.
 *
 * Returns: Nothing.
 * Side effects: None.
 */
void prodreg_info(const char *pcRoot, Criteria criteria, const char *pcAttr,
    int damage)
{
	Wsreg_component **pp = NULL, *p, **all = NULL, **ppws_a;
	Wsreg_component *pws = NULL;
	Wsreg_component *parent = NULL, **children = NULL;
	char ** data = NULL;
	const char *pc = NULL;
	int i, j;

	if (SPECIALROOT(criteria, ROOT_UUID, ROOT_STR) &&
		((criteria.mask & FIND_INST) == 0 ||
			criteria.instance == 1)) {

		/*
		 * We have to initialize here since we will not be
		 * calling prodreg_get_component which does the init.
		 */
		if (wsreg_initialize(WSREG_INIT_NORMAL, pcRoot) !=
		    WSREG_SUCCESS) {
			fail(PRODREG_CONVERT_NEEDED_ACCESS);
		}

		if (wsreg_can_access_registry(O_RDONLY) == 0) {
			fail(PRODREG_CANNOT_READ);
		}

		pws = prodreg_create_root(&parent, &children);

	} else {
		pws = prodreg_get_component(pcRoot, criteria, damage,
		    &ppws_a, &all);
	}

	if (pws == NULL) {
		if (reg_pkg_info(pcRoot, criteria, pcAttr, damage) != 0)
			fail(PRODREG_NO_SUCH_COMPONENT);

		if (all != NULL) wsreg_free_component_array(all);
		return;
	}

	data = wsreg_get_data_pairs(pws);

	if (damage) {

		if (test_damage(pws, all, pcRoot) == 1) {
			(void) printf("isDamaged: TRUE\n");
		} else {
			(void) printf("isDamaged: FALSE\n");
		}
	} else {

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "title") == 0)) &&
		    (pc = wsreg_get_display_name(pws, global_lang)) != NULL)
			(void) printf("%s: %s\n", PRODREG_TITLE, pc);

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "version") == 0)) &&
		    (pc = wsreg_get_version(pws)) != NULL)
			(void) printf("%s: %s\n", PRODREG_VERSIONT, pc);

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "location") == 0)) &&
		    (pc = wsreg_get_location(pws)) != NULL)
			(void) printf("%s: %s\n", PRODREG_LOCATION, pc);

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "uniquename") == 0 ||
			strcasecmp(pcAttr, "unique name") == 0 ||
			strcasecmp(pcAttr, "name") == 0)) &&
		    (pc = wsreg_get_unique_name(pws)) != NULL)
			(void) printf("%s: %s\n",
			    PRODREG_UNINAME, pc);

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "vendor") == 0)) &&
		    (pc = wsreg_get_vendor(pws)) != NULL)
			(void) printf("%s: %s\n", PRODREG_VENDOR, pc);

		if ((pcAttr == NULL ||
		    (strcasecmp(pcAttr, "uninstallprogram") == 0)) &&
		    (pc = wsreg_get_uninstaller(pws)) != NULL)
			(void) printf("%s: %s\n",
			    PRODREG_UNINSTPROG, pc);

		for (i = 0; data && data[i]; i += 2) {
			if (pcAttr == NULL ||
			    (strcasecmp(pcAttr, data[i]) == 0))
				(void) printf("%s: %s\n",
				    (data[i])?(data[i]):"",
				    (data[i+1])?(data[i+1]):"");
		}

		if (pcAttr == NULL ||
		    (strcasecmp(pcAttr, "supported languages") == 0)) {
			data = wsreg_get_display_languages(pws);
			if (data != NULL) {
				(void) printf("%s: ", PRODREG_SUPLANG);
				for (j = 0; data[j]; j++) {
					(void) printf("%s ", data[j]);
				}
				(void) printf("\n");
			}
		}

		if (pcAttr == NULL ||
		    (strcasecmp(pcAttr, "dependent components")) == 0) {
			if ((pp = wsreg_get_dependent_components(pws))
			    != NULL) {

				(void) printf("\n%s:\n%s\n",
				    PRODREG_DEPCOMP,
				    PRODREG_LISTHEAD);
				for (j = 0; pp[j]; j++) {
					pretty_comp(pp[j]);
				}
				wsreg_free_component_array(pp);
			}

			/*
			 * The prodreg GUI does this strange
			 * thing:  It shows children as dependencies.
			 */
			if (children != NULL) {
				pp = children; /* from special nodes */
			} else {
				pp = wsreg_get_child_components(pws);
			}
			if (pp == NULL) {
				pp = wsreg_get_child_references(pws);
				if (pp != NULL) {
					fill_in_comps(pp, all);
				}
			}
			if (pp != NULL) {
				(void) printf("\n%s:\n%s\n",
				    PRODREG_CHILCOMP,
				    PRODREG_LISTHEAD);
				for (i = 0; pp[i] != NULL; i++) {
					pretty_comp(pp[i]);
				}
				wsreg_free_component_array(pp);
			}
		}

		if (pcAttr == NULL ||
		    (strcasecmp(pcAttr, "required components")) == 0) {
			pp = wsreg_get_required_components(pws);

			if (pp) {
				(void) printf("\n%s\n%s\n",
				    PRODREG_REQCOMP,
				    PRODREG_LISTHEAD);

				for (j = 0; pp[j]; j++) {
					pretty_comp(pp[j]);
				}
				wsreg_free_component_array(pp);
			}

			/*
			 * Use prodreg GUI convention of considering
			 * a parent as a required component.
			 *
			 * First try registry components.  If this
			 * fails, try syspkg references.  If the
			 * latter - fill in components since syspkg
			 * references have no names,
			 */
			if (parent != NULL) {
				p = parent;
			} else {
				p = wsreg_get_parent(pws);
			}

			if (p == NULL) {
				p = wsreg_get_parent_reference(pws);
				if (p != NULL) {
					fill_in_comp(p, all);
				}
			}

			if (p != NULL) {
				(void) printf("\n%s:\n%s\n",
				    PRODREG_PARCOMP,
				    PRODREG_LISTHEAD);
				pretty_comp(p);
			}
		}
	}
	wsreg_free_component(pws);
	if (all != NULL) wsreg_free_component_array(all);
}
