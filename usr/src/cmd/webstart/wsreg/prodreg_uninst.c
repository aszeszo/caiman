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

#pragma ident	"@(#)prodreg_uninst.c	1.2	06/02/27 SMI"

/*
 * prodreg_uninst.c
 *
 *  Handle uninstall.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/fcntl.h>
#include <locale.h>
#include <wsreg.h>

#include "prodreg_cli.h"

static char *
prodreg_strdup(const char *pc)
{
	int i = strlen(pc);
	char *pc1 = (char *) malloc(i+1);
	if (!pc1) fail(PRODREG_MALLOC);
	(void) memset(pc1, 0, i+1);
	(void) strncat(pc1, pc, i);
	return (pc1);
}

/*
 * create_cmd
 *
 *  pc_path   This is a command line, like "java -c foo class"
 *  arglist   This is a set of arguments to put at the end of the
 *	    output arg array.  It is null terminated.
 *  ppc_exec   The executable
 *  pppc_args  The argument list, starting with the executable.
 */
static void
create_cmd(const char *pc_path, char **arglist, const char *pcRoot,
    char **ppc_exec, char ***pppc_args) {
	int i, start, count = 0;
	char **ppc;
	char *pc;

	if (pcRoot && strlen(pcRoot) > 0) {
		/* Leave room in the resulting array for -R <altroot> */
		count += 2;
	}

	*ppc_exec = NULL;
	*pppc_args = NULL;
	for (i = 0; pc_path[i] != '\0'; i++) {
		if (pc_path[i] == ' ') {
			count++;
		}
	}
	for (i = 0; arglist && arglist[i] != NULL; i++) count++;

	/* Add 2 positions in array, one for cmd, one for terminating NULL. */
	ppc = (char **) malloc(sizeof (char *) * (count + 2));
	if (! ppc) fail(PRODREG_MALLOC);
	(void) memset(ppc, 0, sizeof (char *) * (count + 2));

	start = 0;
	count = 0;
	for (i = 0; pc_path[i] != '\0'; i++) {
		if (pc_path[i] == ' ') {
			if (count == 0) {
				pc = (char *) malloc(i+1);
				if (!pc) fail(PRODREG_MALLOC);
				(void) memset(pc, 0, i+1);
				(void) strncat(pc, pc_path, i);
				pc[i] = '\0';
				ppc[0] = pc;
			} else if (i == start) {
				/*
				 * This is the case where there are
				 * multiple spaces between arguments.
				 * Skip the blank.
				 */
				start = i + 1;
				continue;
			} else {
				ppc[count] =
				    (char *) malloc(i - start + 1);
				if (ppc[count] == NULL) fail(PRODREG_MALLOC);
				(void) memset(ppc[count], 0, i - start + 1);
				(void) strncat(ppc[count],
				    &pc_path[start], (i - start));
				ppc[count][i - start] = '\0';
			}
			start = i+1;
			count++;
		}
	}

	ppc[count] = (char *) malloc(i - start + 1);
	if (ppc[count] == NULL) fail(PRODREG_MALLOC);
	(void) memset(ppc[count], 0, i - start + 1);
	(void) strncat(ppc[count], &pc_path[start], (i - start));
	ppc[count][i - start] = '\0';
	count++;

	for (i = 0;  arglist != NULL && arglist[i] != NULL; i++) {
		ppc[count] = prodreg_strdup(arglist[i]);
		count++;
	}

	/*
	 * If pcRoot is included, we have an alternate root.
	 * Create new -R altroot command line options and stick them on.
	 */
	if (pcRoot && strlen(pcRoot) > 0) {
		ppc[count++] = prodreg_strdup("-R");
		ppc[count++] = prodreg_strdup(pcRoot);
	}

	pc = prodreg_strdup(ppc[0]);

	/* Terminate the command line option array. */
	ppc[count] = NULL;

	/* Set the return options. */
	*pppc_args = ppc;
	*ppc_exec = pc;
}

/*
 * prodreg_uninstall
 *
 * This routine launches an uninstaller, if the location of one is supplied.
 * Otherwise, it will attempt to find the uninstaller associated with a
 * component registered, and launch it.
 *
 *   arglist  The list of arguemnts to supply to the installer.
 *   pcRoot   The alternate root to use for registry operations.
 *   criteria The component to unregister (if no pc_path supplied).
 *   force    Whether to perform uninstallation even if there are
 *	      other components which depend on the component to uninstall.
 *
 * Returns: Nothing
 * Side effects:  Depend on the uninstaller executed.
 */
void
prodreg_uninstall(char **arglist, const char *pcRoot,
    Criteria criteria, int force)
{
	char *pc_path;
	Wsreg_query *pq = NULL;
	Wsreg_component *pws = NULL;

	if (wsreg_initialize(WSREG_INIT_NORMAL, pcRoot) != WSREG_SUCCESS) {
		fail(PRODREG_CONVERT_NEEDED_ACCESS);
	}

	if (wsreg_can_access_registry(O_RDONLY) == 0) {
		fail(PRODREG_CANNOT_READ);
	}

	db_open();
	pq = wsreg_query_create();

	if (criteria.mask & FIND_UUID) {

		wsreg_query_set_id(pq, criteria.uuid);
		if (criteria.mask & FIND_INST) {
			wsreg_query_set_instance(pq, criteria.instance);
		} else if (criteria.mask & FIND_LOCN) {
			wsreg_query_set_location(pq, criteria.location);
		} else {
			fail(PRODREG_BAD_SYNTAX);
		}
	} else if (criteria.mask & FIND_UNAME) {
		char *pc_val = NULL;

		wsreg_query_set_unique_name(pq, criteria.uniquename);

		/*
		 * It is possible that the location value is actually an
		 * 'id' attribute.  Try this.
		 */
		pws = wsreg_get(pq);
		if (pws != NULL) {
			pc_val = wsreg_get_data(pws, "id");
			if (pc_val == NULL ||
			    strcmp(pc_val, criteria.location) != 0) {
				pws = NULL;
			}
		}

		if ((pws == NULL) && (criteria.mask & FIND_LOCN)) {
			wsreg_query_set_location(pq, criteria.location);
		}

	} else {
		fail(PRODREG_BAD_SYNTAX);
	}

	if (pws == NULL)
		pws = wsreg_get(pq);

	if (pws == NULL)
		fail(PRODREG_UNINSTALL_IMPOSSIBLE);
	/*
	 * If component is depended upon, complain & exit, unless forced.
	 * This check is not recursive - do not check the children of the
	 * node.
	 */
	check_dependent(0, force, pws, PRODREG_UNINSTALL_WOULD_BREAK);

	pc_path = wsreg_get_uninstaller(pws);
	if (pc_path) {
		char *pc, **ppc;
		create_cmd(pc_path, arglist, pcRoot, &pc, &ppc);
#ifndef NDEBUG
		if (getenv("NDEBUG") == NULL) {
			int x;
			(void) printf("command for uninstall: '%s'\n", pc);
			(void) printf("command line arguments for uninstall:");
			for (x = 0; ppc && ppc[x]; x++) {
				(void) printf("[%s] ", ppc[x]);
			}
			(void) printf("\n");
		}
#endif
		launch_installer(pc, ppc); /* Never returns. */
	} else {
		fail(PRODREG_NO_UNINSTALLER);
	}
	if (pws) wsreg_free_component(pws);
	if (pq) wsreg_query_free(pq);
	db_close();
}
