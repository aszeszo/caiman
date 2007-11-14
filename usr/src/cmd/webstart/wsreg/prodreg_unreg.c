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

#pragma ident	"@(#)prodreg_unreg.c	1.4	06/02/27 SMI"

/*
 * prodreg_unreg.c
 *
 * Unregister a component.
 *
 * The component requested has to not be ambiguous, or else a list of
 * possible components are shown, as for prodreg browse.  This can
 * occur if a uuid without an instance number is given, or a name
 * is given which is ambiguous.
 *
 * Unregister with the -f force option will fail unless the libwsreg
 * registry library supports this, for components which have dependencies.
 * From Solaris 8 update 2 unregister is supported but will not allow a
 * component to be unregistered which has other components which reuqire it.
 * This safety check is removed by the version of the library which will ship
 * with Solaris 10 and Solaris 9 update 3 to enable forced unregister.  It
 * is not safe to some extent since one could remove the registered
 * component of software which is in fact required.  But this is much less
 * of a problem than allowing no way to clean up incorrect entries in the
 * registry.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <wsreg.h>
#include "prodreg_cli.h"

/*
 * rec_unreg
 *
 * This recursive routine will unregister each of a components
 * dependencies and its dependencies.  The termination condition
 * is that a component has no dependencies, or no children of children.
 * We have to either recurse on children or dependencies because there
 * are cycles where children depend on their parents in the registry.
 *
 *  pws  The component to unregister the dependencies of.
 *  type  Whether to unregister by children or dependencies recursively.
 *
 * Returns: Nothing.
 * Side effects:  Unregisters many components, potentially.
 */
#define	CHILDREN	1
#define	DEPENDENCIES	2

static void
rec_unreg(Wsreg_component *pws, int type)
{
	Wsreg_component **ppws = NULL;
	int i;

	assert(type == CHILDREN || type == DEPENDENCIES);
	if (type == CHILDREN) {
		if ((ppws = wsreg_get_child_components(pws)) == NULL)
			return;
	} else {
		if ((ppws = wsreg_get_dependent_components(pws)) == NULL)
			return;
	}

	for (i = 0; ppws[i]; i++) {
		rec_unreg(ppws[i], type);
		_private_wsreg_unregister(ppws[i]);
	}
	wsreg_free_component_array(ppws);
}

/*
 * unreg
 *
 * This routine unregisters a component (either as supplied or it will
 * find the component based upon supplied criteria).  If requested,
 * the routine will unregister recursively.
 *
 *   pws       The component to unregister.  This parameter can be NULL.
 *   criteria  If pws is NULL, use criteria to determine a component
 *             to unregister.
 *   recursive If non zero, unregister recursively.
 *
 * Return: Nothing.
 * Side effects:  Could unregister one or more components.
 */
static void
unreg(Wsreg_component *pws, Criteria criteria, int recursive)
{
	Wsreg_query *pq = NULL;
	int found_here = 0;

	/*
	 * This ugly special case exists because of webstart 2 cli
	 * legacy scripts.  There are several possibilities.
	 *
	 *   1 mnemonic (FIND_UNAME) only (! FIND_LOCN)
	 *	We have to unregister all instances when
	 *	a mnemonic (name) is given, without a location.
	 *
	 *	The algorithm loops on finding and removing the first
	 *	instance, till there are no more instances.  When
	 *	instance #1 is removed, the instance #s of all instances
	 *	change so there is always an instance #1.
	 *
	 *   2 mnemonic (FIND_UNAME) and "-" for location (FIND_LOCN)
	 *	The same as 1.
	 *
	 *   3 mnemonic (FIND_UNAME) and 7*10DIGIT (FIND_LOCN)
	 *	the attribute 'id' == the location #.
	 *
	 *   4 mnemonic (FIND_UNAME) and location (FIND_LOCN)
	 */
	if (criteria.mask & FIND_UNAME) {
		int x = 1, y = 0, total = 0;
		char *pcdata = NULL;
		Wsreg_component *pwsany = NULL;
		Wsreg_query *pqany = wsreg_query_create();
		pq = wsreg_query_create();
		wsreg_query_set_unique_name(pq, criteria.uniquename);
		wsreg_query_set_unique_name(pqany, criteria.uniquename);

		/* x == x is always true.  '1' doesn't satisfy lint. */
		while (x == x) {

			wsreg_query_set_instance(pq, x);
			pws = wsreg_get(pq);

			pwsany = wsreg_get(pqany);
			/*
			 * We have to step through every instance, but
			 * we do not know how many instances there are.
			 * It is not enough to wait for an instance
			 * which is not in the registry, since some
			 * instances can be deregistered discontiguously.
			 * Continue until either 128 instances tried
			 * AN ARBITRARY MAX #, or no more instances exist.
			 */
			if (x > 128 || pwsany == NULL) break;
			wsreg_free_component(pwsany);

			/* Count every time through the loop */
			x++;

			if (pws == NULL) {
				continue;
			}

			y = 0;

			/* Cases 1 and 2 above */
			if (!(criteria.mask & FIND_LOCN) ||
			    ((criteria.mask & FIND_LOCN) &&
				(criteria.location != NULL) &&
				(strncmp("-", criteria.location, 2)  == 0))) {
				y = 1;
			}

			/* Case 3 - check id attribute */
			pcdata = wsreg_get_data(pws, "id");
			if ((criteria.mask & FIND_LOCN) &&
			    (pcdata != NULL) &&
			    (strncmp(pcdata, criteria.location,
				strlen(pcdata)) == 0)) {
				y = 3;
			}

			/* Case 4 - check location */
			pcdata = wsreg_get_location(pws);
			if ((criteria.mask & FIND_LOCN) &&
			    (pcdata != NULL) &&
			    (strncmp(pcdata, criteria.location,
				strlen(pcdata)) == 0)) {
				y = 4;
			}

			if (y != 0) {

				/* Unreg first children then dependents. */
				rec_unreg(pws, CHILDREN);
				rec_unreg(pws, DEPENDENCIES);

				/* Unreg the component itself. */
				if (_private_wsreg_unregister(pws) == 0) {
					fail(PRODREG_UNREGISTER);
				}

				total++;

				/* If y == 1, unregister all instances. */
				if (y != 1) {
					/*
					 * The desired component instance
					 * was found & deregistered.
					 */
					break;
				}
			}

			if (pws != NULL) {
				wsreg_free_component(pws);
				pws = NULL;
			}
		}

		if (total == 0) fail(PRODREG_NOT_UNREGABLE);
		if (pqany) wsreg_query_free(pqany);
		pqany = NULL;

	} else {
		if (NULL == pws) {
			pq = wsreg_query_create();

			wsreg_query_set_id(pq, criteria.uuid);
			if (criteria.mask & FIND_LOCN)
				wsreg_query_set_location(pq,
				    criteria.location);
			pws = wsreg_get(pq);
			found_here = 1;
		}

		if (pws) {
			if (recursive) {
				rec_unreg(pws, CHILDREN);
				rec_unreg(pws, DEPENDENCIES);
			}
			if (_private_wsreg_unregister(pws) == 0) {
				fail(PRODREG_UNREGISTER);
			}
		} else {
			fail(PRODREG_NOT_UNREGABLE);
		}
	}
	if (pq) wsreg_query_free(pq);
	if (found_here) wsreg_free_component(pws);
}

/*
 * prodreg_unregister
 *
 * This will unregister a component unless (a) the component has
 * dependencies, in which case the command will fail and an error
 * will be output UNLESS the 'force' option is set, (b) the
 * component criteria is ambiguous, in which case the list of
 * possible matching components is returned.
 *
 *   pcRoot    An alternate root, if non-null.
 *   criteria  The component's name, uuid, browse number, etc.
 *   force     If this is set, unregister even if the component
 *             has others which depend on it.
 *   recursive Will deregister the component and all children and
 *             nodes which depend upon it.
 *
 * Returns: Nothing.
 * Side effects: Changes the state of the registry, if the user
 *     has permission to do so.
 */
void
prodreg_unregister(const char *pcRoot, Criteria criteria, int force,
    int recursive)
{
	Wsreg_component **ppws_ambig = NULL;
	Wsreg_component **ppws_dep = NULL;
	Wsreg_component *pws = NULL;
	Wsreg_component **ppws_syspkgs = NULL;
	int i;
	int result;

	if (SPECIALROOT(criteria, ROOT_UUID, ROOT_STR) ||
	    SPECIALROOT(criteria, UNCL_UUID, UNCL_STR) ||
	    SPECIALROOT(criteria, LOCL_UUID, LOCL_STR) ||
	    SPECIALROOT(criteria, ADDL_UUID, ADDL_STR) ||
	    SPECIALROOT(criteria, SYSS_UUID, SYSS_STR) ||
	    SPECIALROOT(criteria, global_ENTR_UUID, ENTR_STR) ||
	    SPECIALROOT(criteria, SYSL_UUID, SYSL_STR)) {
		fail(PRODREG_UNREGISTER);
	}

	if (pcRoot && pcRoot[0] == '\0') pcRoot = NULL;

	if ((result = wsreg_initialize(WSREG_INIT_NORMAL, pcRoot))
	    != WSREG_SUCCESS) {
		debug(DEBUGINFO, "Could not init, reason = %d\n",
		    result);
		fail(PRODREG_CONVERT_NEEDED_ACCESS);
	}

	/*
	 * Check uid is 0, otherwise we may fail later.
	 * This is a work around for the case where sometimes
	 * wsreg_can_access_registry says YES, but the answer is NO.
	 */
	if (_private_wsreg_can_access_registry(O_RDWR) == 0) {
		fail(PRODREG_CANNOT_WRITE);
	}

	/*
	 * Handle the simple mnemonic case.
	 */
	if (criteria.mask & FIND_UNAME) {
		unreg(pws, criteria, recursive);
		return;
	}

	pws = prodreg_get_component(pcRoot, criteria, 0, &ppws_ambig,
	    &ppws_syspkgs);
	if (pws == NULL)
		fail(PRODREG_NO_SUCH_COMPONENT);

	db_open();

	if (ppws_ambig) {
		if (force == 0) {
			(void) printf(PRODREG_AMBIGUOUS_RESULTS);
			(void) printf("\n");
			browse_header();
		}

		for (i = 0; ppws_ambig[i]; i++) {
			if (force) {
				unreg(ppws_ambig[i], criteria, 0);
			} else {
				Wsreg_component **p =
				    wsreg_get_child_references(ppws_ambig[i]);
				fill_in_comps(p, ppws_syspkgs);

				show(NODE, 1, 0, get_bn(ppws_ambig[i]->id),
				    ppws_ambig[i]->id, ppws_ambig[i]->instance,
				    wsreg_get_display_name(ppws_ambig[i],
					global_lang));

				if (p) {
					wsreg_free_component_array(p);
					p = NULL;
				}
			}
		}
		if (ppws_syspkgs)
			wsreg_free_component_array(ppws_syspkgs);

		return;
	}

	/* This will exit if pws has dependents, unless forced. */
	check_dependent(recursive, force, pws, PRODREG_UNREG_WOULD_BREAK);

	unreg(pws, criteria, recursive);

	wsreg_free_component(pws);
	if (ppws_dep) wsreg_free_component_array(ppws_dep);
	if (ppws_syspkgs) wsreg_free_component_array(ppws_syspkgs);
	db_close();
}
