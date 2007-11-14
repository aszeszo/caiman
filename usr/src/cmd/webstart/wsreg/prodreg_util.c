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

#pragma ident	"@(#)prodreg_util.c	1.3	06/02/27 SMI"

/*
 * prodreg_util.c
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
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdarg.h>
#include <assert.h>
#include <wsreg.h>
#include "prodreg_cli.h"

/*
 * fail
 *
 * This routine prints out a fatal error and exits.
 *
 *  pc  Fatal error message.
 *
 * Returns: nothing (does not return!)
 * Side effects: exits the  program.
 */
void
fail(const char *pc)
{
	(void) printf("%s\n", pc);
	exit(1);
}

/*
 * debug
 *
 * This routine outputs debug lines to standard error.  The code
 * does nothing when NDEBUG is defined as an environment variable
 * or as a compile symbol.
 *
 *   pcFile    The file which called the function.
 *   line      The line which called the function.
 *   pcFormat  The format line for debug output.
 *   (args)    Arguments to the format line.
 *
 * Returns: Nothing
 * Side effects: None
 */

/* VARARGS */
void
debug(char *pcFile, int line, const char *pcFormat, ...)
{
	va_list ap;
	va_start(ap, pcFormat);
#ifndef NDEBUG
	if (getenv("NDEBUG"))
		return;
	(void) fprintf(stderr, "debug [%s, %d]: ", pcFile, line);
	(void) vfprintf(stderr, pcFormat, ap);
#else
	/* To appease lint */
	ap = ap;
#endif
	va_end(ap);
}

/*
 * prodreg_get_component
 *
 * This routine is used by several prodreg CLI commands that only want one
 * component - or none, if the result is ambiguous.  If the criteria are
 * ambiguous, the list of possible results is output.  If there are errors
 * the apropriate error message is returned.
 *
 * What makes this routine complicated is that some of the database keys are
 * not unique and we have to be able to return multiple matches.  Further,
 * since there are two databases, we have to be able to merge the multiple
 * results from one or the other or both together to form a single ambiguous
 * result.
 *
 *   pcRoot   The alternate root, or NULL.
 *   criteria The search criteria for the component.
 *   damage   Indicates whether damaged components should be flagged.
 *   pppws_ambig
 *            If this is not NULL, return the list of ambiguous results.
 *	      The caller has to free them.
 *   pppws_all
 *            Either (1) it is NULL.  Ignore.
 *            (2) pppws_all is not NULL, but *pppws_all is NULL.
 *                Allocate system package component list and return it.
 *            (3) pppws_all is not NULL, *pppws_all is set to sys pkg comps.
 *                Do not allocate them.
 *
 * Returns:  A component structure, which the caller must free, or NULL
 *    if none are found, or results are ambiguous.  If the results are
 *    ambiguous and pppws_ambig is non-NULL, return the ambiguous results
 *    by setting this parameter to the ppws_ambig array.
 * Side effects: None, though an error can cause this routine to exit
 *    via fail.
 */
Wsreg_component * prodreg_get_component(const char *pcRoot, Criteria criteria,
    int damage, Wsreg_component ***pppws_ambig, Wsreg_component ***pppws_all)
{
	Wsreg_component **ppws_syspkgs = NULL;
	Wsreg_component *pws = NULL;
	Wsreg_component **ppws_a = NULL;
	Wsreg_component **ppws_c = NULL;
	Wsreg_component **ppws_ambig = NULL;
	Wsreg_component **ppws_ambig_temp = NULL;
	Wsreg_query *pq = NULL;
	RootType rootType = NONE;
	int i, found = 0, max = 0;

	if (pcRoot && pcRoot[0] == '\0') pcRoot = NULL;

	if (wsreg_initialize(WSREG_INIT_NORMAL, pcRoot) != WSREG_SUCCESS) {
		fail(PRODREG_CONVERT_NEEDED_ACCESS);
	}

	if (wsreg_can_access_registry(O_RDONLY) == 0) {
		fail(PRODREG_CANNOT_READ);
	}

	/* First search the registry.  Only if that fails, try the sys pkgs. */
	pq = wsreg_query_create();

	if ((criteria.mask & FIND_UNAME) != 0) {
		wsreg_query_set_unique_name(pq, criteria.uniquename);
		if (criteria.mask & FIND_LOCN) {
			wsreg_query_set_location(pq, criteria.location);
		}
		pws = wsreg_get(pq);
		wsreg_query_free(pq);
		return (pws);
	} else if ((criteria.mask & FIND_UUID) != 0) {
		wsreg_query_set_id(pq, criteria.uuid);
		if ((criteria.mask & FIND_INST) != 0) {
			wsreg_query_set_instance(pq, criteria.instance);
		} else if (criteria.mask & FIND_LOCN) {
			wsreg_query_set_location(pq, criteria.location);
		} else {
			/* check to see if we have ambiguous instances! */
			int j = 1, done = 0;
			Wsreg_component *pws_temp;
			for (j = 1; done == 0; j++) {
				wsreg_query_set_instance(pq, j);
				pws_temp = wsreg_get(pq);
				if (pws_temp == NULL) done = 1;
				else {
					if (found == 0) {
						pws = pws_temp;
					} else {
						/*
						 * Ensure enough space for
						 * ambiguous entries.
						 */
						/* Save the initial entry */
						if (found == 1) {
							resize_if_needed(0,
							    &max, &ppws_ambig,
							    sizeof (pws));
							ppws_ambig[0] = pws;
							pws = NULL;
						} else {
							resize_if_needed(found,
							    &max, &ppws_ambig,
							    sizeof (pws));
						}
						ppws_ambig[found] = pws_temp;
						rootType = AMBIG;
					}
					found++;
				}
			}
			if (found == 1) {
				wsreg_query_free(pq);
				return (pws);
			}
		}

		/*
		 * If we haven't found any ambiguous matches,
		 * try for a single match.
		 */
		if (ppws_ambig == NULL) {
			pws = wsreg_get(pq);
			wsreg_query_free(pq);
			if (pws != NULL)
				return (pws);
		}

	} else if ((criteria.mask & FIND_NAME) != 0) {
		Wsreg_component **a = wsreg_get_all();

		for (i = 0; a && a[i]; i++) {
			char *pc =
			    wsreg_get_display_name(a[i], global_lang);

			if (pc == NULL ||
			    criteria.displayname == NULL ||
			    strcmp(criteria.displayname, pc) != 0 ||
			    (((criteria.mask & FIND_INST) != 0) &&
				(criteria.instance != a[i]->instance)) ||
			    (((criteria.mask & FIND_LOCN) != 0) &&
				(a[i]->location == NULL ||
				criteria.location == NULL ||
				strcmp(criteria.location,
				    a[i]->location) != 0)))
				continue;
			if (found == 0) {
				pws = wsreg_clone_component(a[i]);
			} else {
				if (found == 1) {
					resize_if_needed(0, &max,
					    &ppws_ambig, sizeof (pws));
					ppws_ambig[0] = pws;
					pws = NULL;
				} else {
					resize_if_needed(found, &max,
					    &ppws_ambig, sizeof (pws));
				}
				ppws_ambig[found] =
				    wsreg_clone_component(a[i]);
				rootType = AMBIG;
			}
			found++;
		}
	}
	ppws_ambig_temp = ppws_ambig;
	ppws_ambig = NULL;

	if (pppws_all == NULL || *pppws_all == NULL) {
		ppws_syspkgs = wsreg_get_sys_pkgs(progress);
		if (ppws_syspkgs == NULL)
			fail(PRODREG_INIT);
	} else {
		/* The pppws_all is the system pkg component list. */
		ppws_syspkgs = *pppws_all;
	}

	if (damage)
		wsreg_flag_broken_components(ppws_syspkgs);

	db_open();

	/*
	 * Search system packages will try to find any system packages
	 * which are mapped to components.  If one component has already
	 * been found, search_sys_pkgs will add it to the ambiguous list.
	 * If more than one component has already been found, 'pws' will
	 * be NULL and the ppws_ambig_temp list will contain the previously
	 * found ambiguous names.
	 */
	if (search_sys_pkgs(ppws_syspkgs, &ppws_a, &ppws_c, &ppws_ambig,
	    &pws, &rootType, criteria) == 0 &&
	    ppws_ambig == NULL && /* no ambiguous reg &| pkg names */
	    ppws_ambig_temp == NULL) { /* no ambig registry names */

		if (ppws_a) wsreg_free_component_array(ppws_a);
		if (ppws_c) wsreg_free_component_array(ppws_c);

		return (NULL);
	}

	/* Merge in ambiguous names with the sys pkg names. */
	if (ppws_ambig_temp != NULL) {
		if (ppws_ambig != NULL) {
			for (i = 0; ppws_ambig[i] != NULL; i++) {
				resize_if_needed(found, &max, &ppws_ambig_temp,
				    sizeof (Wsreg_component *));
				ppws_ambig_temp[found++] = ppws_ambig[i];
			}
			wsreg_free_component_array(ppws_ambig);
		} else if (pws != NULL) {
			resize_if_needed(found, &max, &ppws_ambig_temp,
			    sizeof (Wsreg_component *));
			ppws_ambig_temp[found++] = pws;
		}

		ppws_ambig = ppws_ambig_temp;
		*pppws_ambig = ppws_ambig_temp;
		rootType = AMBIG;
	}

	if (rootType == AMBIG && pppws_ambig != NULL) {

		(void) printf(PRODREG_AMBIGUOUS_RESULTS);
		(void) printf("\n");

		browse_header();
		for (i = 0; ppws_ambig[i]; i++) {
			Wsreg_component **p =
			    wsreg_get_child_references(ppws_ambig[i]);
			fill_in_comps(p, ppws_syspkgs);

			show(NODE, 1, 0, get_bn(ppws_ambig[i]->id),
			    ppws_ambig[i]->id, ppws_ambig[i]->instance,
			    wsreg_get_display_name(ppws_ambig[i],
				global_lang));

			if (p) {
				wsreg_free_component_array(p);
			}
		}
		if (pws) wsreg_free_component(pws);
		pws = NULL;
	}
	if (pppws_all == NULL) {
		wsreg_free_component_array(ppws_syspkgs);
	} else {
		*pppws_all = ppws_syspkgs;
	}

	if (ppws_ambig) {
		if (pppws_ambig) {
			*pppws_ambig = ppws_ambig;
		} else {
			wsreg_free_component_array(ppws_ambig);
		}
	}
	if (ppws_a) wsreg_free_component_array(ppws_a);
	if (ppws_c) wsreg_free_component_array(ppws_c);

	return (pws);
}

/*
 * fill_in_comps
 *
 * Components obtained from the wsreg library using the get_reference(s)
 * API do not fill in the display name.  This routine searches the database
 * exhaustively to find the corresponding node *which is* filled in, and
 * copies over the name to the nameless node.
 *
 *   pp_c   The components to fill in.
 *   pp_s   The array of components returned by wsreg.  This list is
 *          reused as much as possible as obtaining it is slow.
 *
 * NOTE:  This function should not be required.  It is covering up for
 * deficiencies (bugs) in the current libwsreg implementation.  Fixing
 * these bugs is not an option since this software has to coexist with
 * old versions of the library.
 *
 * Return: Nothing.
 * Side effects:  ppc is modified to now include names, if possible.
 *
 */
void
fill_in_comps(Wsreg_component **pp_c, Wsreg_component **pp_s) {
	int i, j;
	if (!pp_s || !pp_c)
		return;

	for (i = 0; pp_s[i] != NULL; i++) {
		for (j = 0; pp_c[j] != NULL; j++) {
			if (strcmp(pp_s[i]->id, pp_c[j]->id) == 0) {
				char *pc = NULL;
				Wsreg_component *pws;

				if (pp_s[i]->instance !=
				    pp_c[j]->instance)
					continue;

				pc = wsreg_get_display_name(pp_s[i],
				    global_lang);
				if (pc && wsreg_get_display_name(pp_c[j],
				    global_lang)
				    == NULL) {
					wsreg_add_display_name(pp_c[j],
					    global_lang, pc);
				}

				if ((pws = wsreg_get_parent(pp_c[j]))
				    != NULL) {
					wsreg_free_component(pws);
					continue;
				}

				pws = wsreg_get_parent(pp_s[i]);
				if (pws == NULL) {
					pws = wsreg_get_parent_reference(
						pp_s[i]);
				}
				if (pws != NULL) {
					wsreg_set_parent(pp_c[j], pws);
					wsreg_free_component(pws);
				}
			}
		}
	}
}

void
fill_in_comp(Wsreg_component *pws, Wsreg_component **ppws_sys)
{
	Wsreg_component *ppws[2];
	ppws[0] = pws;
	ppws[1] = NULL;
	fill_in_comps(ppws, ppws_sys);
}

/*
 * resize_if_needed
 *
 * Manage the dynamic array so that when it is about to outgrow its size
 * it will be ajusted by the DYNA_INCR.  If the array is not yet allocated,
 * this routine will initialize it.
 *
 *  num    IN      The number of items already allocated in the array.
 *                 NOTE:  If num > 0, then *ppp can't be NULL.  The
 *                 array may have to be copied over.  To init
 *  pmax   IN/OUT  The size of the array.  This will be changed when the
 *                 num is 0 or 2 less than the current max.
 *  ppp    IN/OUT  The array.  If num is 0 or 2 less than the current
 *                 max a new array will be allocated with a *pmax value
 *                 one increment larger than the previous.  The previous
 *                 contents of the array are copied to the new array.
 *  sz     IN      The size of a single item in the array.
 *
 * Returns:  Always succeeds or the program will terminate (malloc error).
 * Side effects:  It may reallocate the array and adjust the pmax parameter.
 */
void
resize_if_needed(int num, int *pmax, Wsreg_component ***ppp, int sz) {

	Wsreg_component **ppws_temp = NULL;

	if (num == 0) {
		*pmax = 0;
	}

	if (num < (*pmax -2))
		return;

	*pmax += DYNA_INCR;
	ppws_temp = (Wsreg_component **) malloc(*pmax * sz);
	if (NULL == ppws_temp) {
		fail(PRODREG_MALLOC);
	}
	(void *) memset(ppws_temp, 0, (*pmax)*sz);
	if (num > 0) {
		assert(*ppp);
		(void *) memcpy(ppws_temp, *ppp, sz * num);
		free(*ppp);
	}
	*ppp = ppws_temp;
}

/*
 * pretty_comp
 *
 * This outputs a component in a pretty fashion.  The loops in the
 * output pad out the name and ID to make columns in the output
 * unless the strings concerned are too long.  In this case, they
 * just print the string followed by a space.
 *
 *   pws  The component to output.
 *
 * Returns: Nothing.
 * Side effects: None.
 */
void
pretty_comp(const Wsreg_component *pws)
{
	char *pcName = wsreg_get_display_name(pws, global_lang);
	char *pcID = wsreg_get_id(pws);
	uint32_t ui = 0;
	int inst = wsreg_get_instance(pws);
	if (NULL == pcName) pcName = "";
	(void) printf("%s ", pcName);
	for (ui = strlen(pcName); ui > 0 && ui < 38; ui++)
		(void) printf(" ");
	(void) printf("%s ", pcID);
	for (ui = strlen(pcID); ui > 0 && ui < 37; ui++)
		(void) printf(" ");
	(void) printf("%d\n", inst);
}

/*
 * check_dep
 *
 * Obtain the list of child components for a node using the same
 * technique as the GUI.  Display these dependents.  Apply this
 * technique recursively.
 *
 *   pws   The component whose dependent list has to be displayed.
 *
 * Returns: Nothing
 * Side effects: None
 */
static void
check_dep(Wsreg_component *pws)
{
	Wsreg_component **ppws = NULL;
	int i;
	if ((ppws = wsreg_get_dependent_components(pws)) == NULL &&
	    (ppws = wsreg_get_child_components(pws)) == NULL) {
		return;
	}
	for (i = 0; ppws[i]; i++) {
		show(NODE, 1, 0, get_bn(ppws[i]->id),
		    ppws[i]->id, ppws[i]->instance,
		    wsreg_get_display_name(ppws[i], global_lang));
		check_dep(ppws[i]);
	}
	wsreg_free_component_array(ppws);
}

/*
 * check_dependent
 *
 * This routine outputs a list of dependencies depending on the
 * parameters supplied then exits.  This is used to prevent deregistrations
 * of components for which there are dependencies in the registry, unless
 * forced.
 *
 *    recursive    If non zero then do not perform the check.  The unreg
 *                 will be of all components and those that depend on this
 *                 component.
 *    force        If non zero then do not perform the check.  The unreg
 *                 will occur even if it breaks dependencies.
 *    pws          The component to show the dependent list of.
 *    msg          The message to precede the output with (which will vary).
 *
 * Return: Nothing.
 * Side effects: May terminate the program.
 */
void
check_dependent(int recursive, int force, Wsreg_component *pws,
    const char *msg)
{
	Wsreg_component **ppws = NULL;
	int i;

	if (force || recursive)
		return;
	if ((ppws = wsreg_get_dependent_components(pws)) == NULL)
		return;

	(void) printf(msg);
	(void) printf("\n");
	browse_header();
	for (i = 0; ppws[i]; i++) {
		show(NODE, 1, 0, get_bn(ppws[i]->id),
		    ppws[i]->id, ppws[i]->instance,
		    wsreg_get_display_name(ppws[i], global_lang));
	}
	(void) printf("\n%s\n", PRODREG_COMPLETE_DEPENDENCIES);
	browse_header();
	check_dep(pws);

	exit(1);
}


/*
 * This procedure does not return.  The command either succeeds in
 * launching a prodreg GUI or fails and outputs an error to stderr.
 */
void
launch_installer(const char *pcExec, char **args)
{
	struct stat sb;

	if (stat(pcExec, &sb) < 0) {
		if (errno == ENOENT)
			fail(INSTALLER_NO_PROG);

		fail(INSTALLER_NO_STAT);
	}

	if ((sb.st_mode & S_IXOTH) == 0)
		fail(INSTALLER_NO_EXEC);

	/* This has no return value, since it doesn't return. */
	(void) execv(pcExec, args);

}

/*
 * okpkg
 *
 * Check that there is a pkg directory as named, that there is a pkginfo
 * file under it and that file is >0 length.  If ppcinfo is not NULL,
 * return the pkginfo file contents in a newly allocated buffer.
 *
 *   pcroot   [IN]  Alternate root directory to find the pkg files.
 *   pcpkg    [IN]  package name
 *   ppcinfo  [OUT] Returns the pkginfo file contents if ppcinfo not null.
 *                  ppcinfo must be a valid pointer to a char *.
 *                  Caller must free the returned buffer, if any.
 *
 * Returns: 1 if pkg OK, 0 otherwise.
 * Side effects: none
 */
int
okpkg(const char *pcroot, const char *pcpkg, char **ppcinfo)
{
	struct stat statpkg;
	struct stat statpkginfo;
	char *pcpath = NULL;
	char *pcinfo = NULL;
	int len = strlen("/var/sadm/pkg/");

	if (pcroot == NULL) pcroot = "";

	len += (strlen(pcroot) + strlen(pcpkg) + 1);
	pcpath = (char *) malloc(len);
	pcinfo = (char *) malloc(len + strlen("/pkginfo"));
	if (pcpath == NULL || pcinfo == NULL)
		fail(PRODREG_MALLOC);

	(void *) memset(pcpath, 0, len);
	(void) strcat(pcpath, pcroot);
	(void) strcat(pcpath, "/var/sadm/pkg/");
	(void) strcat(pcpath, pcpkg);

	(void *) memset(pcinfo, 0, len);
	(void) strcat(pcinfo, pcpath);
	(void) strcat(pcinfo, "/pkginfo");

	if (stat(pcpath, &statpkg) != 0 ||
	    stat(pcinfo, &statpkginfo) != 0)
		return (0);

	if (S_ISDIR(statpkg.st_mode) == 0 ||
	    S_ISREG(statpkginfo.st_mode) == 0 ||
	    statpkginfo.st_size == 0)
		return (0);

	if (ppcinfo != NULL) {
		int fd;
		int sofar = 0, t, total = statpkginfo.st_size;
		FILE *fp = fopen(pcinfo, "r");

		*ppcinfo = (char *) malloc(statpkginfo.st_size + 1);
		if ((*ppcinfo) == NULL) fail(PRODREG_MALLOC);
		(void *) memset((*ppcinfo), 0, statpkginfo.st_size + 1);

		while (fp && (total > 0)) {
			fd = fileno(fp);
			t = read(fd, &(*ppcinfo)[sofar], total);
			if (t < 0)
				fail(PRODREG_FAILED);
			sofar += t;
			total -= t;
		}
	}
	return (1);
}

/*
 * nextstr
 *
 * Read from the location of *pi to the end of the string, or to the next
 * white space and return a newly allocated string for that value.  Advance
 * pi to indicate the next space to use.  If there are successive white spaces
 * before or after the word, elide (skip) them.
 *
 *  *pi   [IN/OUT]  The location in the string to scan.
 *  pc    [IN]      The string to scan.
 *
 * Returns a newly allocated string with the next string.  If there are
 * no more allocatable strings, return NULL.
 * Side effects:  Changes *pi as the scanning advances.
 */
char *
nextstr(int *pi, const char *pc)
{
	char *pc_str = NULL;
	int start = 0;
	if (pc == NULL || *pi >= strlen(pc))
		return (NULL);

	/* Remove initial spaces. */
	while ((*pi < strlen(pc)) && isspace(pc[*pi])) (*pi) += 1;

	/* Start string scan */
	start = *pi;
	while ((*pi < strlen(pc)) && !isspace(pc[*pi])) (*pi) += 1;

	if (start < *pi) {
		pc_str = (char *) malloc(*pi - start + 1);
		if (pc_str == NULL)
			fail(PRODREG_MALLOC);
		(void *) memset(pc_str, 0, *pi - start + 1);
		(void) strncpy(pc_str, &pc[start], *pi - start);
		pc_str[*pi - start] = '\0';
		return (pc_str);
	}

	return (NULL);
}

/*
 * getval
 *
 * Assume that pcdb is a KEY=VAL\n database string.  This routine searches
 * linearly till it finds a key which equals pckey.  In that case it returns
 * the corresponding value in a newly allocated array that the caller must
 * free.  Blank lines and NULL terminated buffers are accepted, but a buffer
 * with no '=' on a line with text will briefly confuse the parser.  Some
 * lines of db data may be unread in this case.
 *
 *    pcdb   The database file (zero or more lines of KEY=VAL\n pairs.)
 *    pckey  The key in the db whose value is sought.
 *
 * Returns: NULL if nothing available.
 *          Zero length string "" if KEY=\n
 *          String (newly allocated buffer) if found
 * Side effects: none
 */
char *
getval(const char *pcdb, const char *pckey)
{
	int i, start = 0;
	char *pc1 = NULL, *pc2 = NULL;

	/* i = i is for cstyle. */
	for (i = 0; i < strlen(pcdb) && pcdb[i] != NULL; i = i) {

		/* get first field */

		pc1 = NULL;
		start = i;
		while (i < strlen(pcdb) && pcdb[i] != NULL) {
			if (pcdb[i] == '=') {
				pc1 = (char *) malloc(i - start + 1);
				if (pc1 == NULL)
					fail(PRODREG_MALLOC);
				(void *) memset(pc1, 0, i - start + 1);
				(void) strncpy(pc1, &pcdb[start], (i - start));
				i++; /* skip past the token */
				break;
			} else if (pcdb[i] == '\n') {
				pc1 = NULL;
				i++;
				break;
			}
			i++;
		}

		/*
		 * Do not get 2nd string if we couldn't get 1st one.
		 * We may get realigned on the next line if this is just
		 * a line with no value.
		 */
		if (pc1 == NULL) continue;

		/* get second field */

		pc2 = NULL;
		start = i;
		while (i < strlen(pcdb) && pcdb[i] != NULL) {
			if (pcdb[i] == '\n') {
				pc2 = (char *) malloc(i - start + 1);
				if (pc2 == NULL) fail(PRODREG_MALLOC);
				(void *) memset(pc2, 0, i - start + 1);
				(void) strncpy(pc2, &pcdb[start], (i - start));

				/* move past the \n */
				i++;
				break;
			}
			i++;
			/*
			 * Handle the case where the final line is not
			 * terminated by a \n, rather by a NULL at the
			 * end of the string.
			 */
			if (pcdb[i] == '\0') {
				pc2 = (char *) malloc(i - start + 1);
				if (pc2 == NULL) fail(PRODREG_MALLOC);
				(void *) memset(pc2, 0, (i - start + 1));
				(void) strncpy(pc2, &pcdb[start], (i - start));
				/* loop will terminate - do not advance! */
				break;
			}
		}

		if (pc1 != NULL && pckey != NULL &&
		    (strcmp(pc1, pckey) == 0)) {
			free(pc1);
			return (pc2);
		}
		if (pc1) free(pc1);
		if (pc2) free(pc2);
		pc1 = NULL;
		pc2 = NULL;
	}
	return (NULL);
}


/*
 * show
 *
 * Print out important identifiers of a a component on a single line.
 *
 *   m           The type (CHILD | PARENT | NODE).
 *   treeIndent  If negative, show a '.' node at absolute value - no children.
 *               If >0 it is the number of spaces to indent the marker.
 *   b           The browse id #.
 *   pcUUID      The UUID.
 *   i           The instance #.
 *   pcNM        The name of the node.
 *
 * Return: nothing.
 * Side effects: none.
 */
void
show(int m, int treeIndent, int hasChildren, uint32_t b,
    const char *pcUUID, int i, const char *pcNM) {

	char c, s[9];

	if (treeIndent > 8) {
		treeIndent = 8;
	}

	if (treeIndent < 1) {
		treeIndent = 1;
	}

	(void *) memset(s, ' ', 8);
	s[8] = '\0';

	switch (m) {
	case CHILD:
		if (hasChildren) {
			c = '+';
		} else {
			c = '.';
		}
		break;
	case PARENT:
		c = '-';
		break;
	case NODE:
		if (hasChildren) {
			c = '-';
		} else {
			c = '.';
		}
		break;
	default:
		break;
	}

	if (pcNM == NULL && pcUUID) {
		if (0 == strcmp(pcUUID, UNCL_UUID)) pcNM = UNCL_STR;
		else if (0 == strcmp(pcUUID, ADDL_UUID)) pcNM = ADDL_STR;
		else if (0 == strcmp(pcUUID, LOCL_UUID)) pcNM = LOCL_STR;
		else if (0 == strcmp(pcUUID, global_ENTR_UUID)) pcNM = ENTR_STR;
		else if (0 == strcmp(pcUUID, SYSL_UUID)) pcNM = SYSL_STR;
		else if (0 == strcmp(pcUUID, SYSS_UUID)) pcNM = global_solver;
		else pcNM = "";
	}

	s[treeIndent-1] = c;

	(void) printf("%-8u  %s  %-36s  %2i  %s\n", b,  s, pcUUID, i, pcNM);
}

/*
 * browse_header
 *
 * Outputs the common header used in every list of components.
 *
 * Returns: Nothing
 * Side effects: None
 */
void
browse_header()
{
	(void) printf("%s", PRODREG_BH);
}

/*
 * search_sys_pkgs
 *
 *    Get the ancestry and children of a given node based on the
 *    criteria.  Do not rely on the wsreg search function to know
 *    how to represent the data - as this data is not present in
 *    the registry database.  The search function will also return
 *    ambiguous results.
 *
 *    Note:  This function will not locate special nodes like root
 *           syss, entr, etc.  These have to be tested for and dealt
 *           with by individual commands before calling this function.
 *
 *  ppws_sysp        IN:   This is the array of all system packages.
 *  pppws_parent     OUT:  The ancestor array is allocated, if found.
 *  pppws_children   OUT:  The children array is allocated, if found.
 *  pppws_ambig      OUT:  The ambiguous array is allocated, if found.
 *  ppws             IN/OUT:  The node itself is allocated, if found.
 *                         Note:  This value may be allocated and set
 *                         already - if, for example, a registry based
 *                         component has already been found!
 *                         The caller must set this to either NULL or
 *                         a pointer to a component prior to calling
 *                         the function.
 *  proot            OUT:  This value is set to a search result value.
 *  criteria         IN:   The query.
 *
 *
 * Returns: 1 if found (proot set to non-NONE),
 *          0 otherwise (proot set to NONE)
 *
 *          'Out' parameters may include newly allocated arrays.
 *          These must be freed by the caller with
 *          wsreg_free_component_array() for parent, children and ambig,
 *          or wsreg_free_component() for the node itself.
 *
 *          RootType is set to one of the following values to indicate
 *          the results of the search - is it an ancestor of
 *             ENTIRE = entire distribution, ADDL = additional software,
 *             LOCL = localization software, UNCL = unclassified software,
 *             AMBIG = ambiguous in tree - use only the ambiguous list,
 *             NONE = component is not in the tree - show nothing.
 *
 * Side effects:  If there are any parameter or system errors,
 *                they are logged.  Memory is allocated to return data.
 */

int
search_sys_pkgs(Wsreg_component **ppws_sysp,
    Wsreg_component ***pppws_parent,
    Wsreg_component ***pppws_children,
    Wsreg_component ***pppws_ambig,
    Wsreg_component **ppws,
    RootType *proot,
    Criteria criteria)
{
	int i;
	int amb_max = 0;
	int amb_sum = 0;

	/* Make sure we return a reasonable default value */
	*pppws_parent = NULL;
	*pppws_children = NULL;
	*pppws_ambig = NULL;
	*proot = ENTIRE; /* default */

	assert((criteria.mask & FIND_UUID) != 0 ||
	    (criteria.mask & FIND_NAME) != 0);

	/* Find the requested value - check either UUID or NAME sought for */
	for (i = 0; ppws_sysp[i]; i++) {
		if ((((criteria.mask & FIND_UUID) != 0) &&
		    (criteria.uuid &&
		    0 == strcasecmp(ppws_sysp[i]->id, criteria.uuid))) ||
		    (((criteria.mask & FIND_NAME) != 0) &&
			(global_lang &&
			0 == strcasecmp(wsreg_get_display_name(ppws_sysp[i],
			    global_lang), criteria.displayname)))) {

			/*
			 * If instance or location criteria supplied,
			 * filter on them.
			 */
			if (((criteria.mask & FIND_INST) != 0) &&
			    criteria.instance !=
			    wsreg_get_instance(ppws_sysp[i])) {
				continue;
			}

			if (((criteria.mask & FIND_LOCN) != 0) &&
			    criteria.location != NULL &&
			    strcmp(criteria.location,
				wsreg_get_location(ppws_sysp[i]))) {
				continue;
			}

			if (*ppws == NULL) {
				*ppws = wsreg_clone_component(ppws_sysp[i]);
				continue;
			}

			/* We have ambiguous results. */

			resize_if_needed(amb_sum, &amb_max,
			    pppws_ambig, sizeof (Wsreg_component *));

			if (amb_sum == 0) {

				/* Save first value, next saved next below */
				(*pppws_ambig)[amb_sum++] = *ppws;
				*ppws = NULL;
			}

			/* Add the new result to the dynamic array. */
			(*pppws_ambig)[amb_sum++] =
			    wsreg_clone_component(ppws_sysp[i]);
			*proot = AMBIG;
		}
	}

	if (*ppws != NULL) {
		int j = 0;
		Wsreg_component *pws_temp = *ppws, *pws_parent = NULL;
		Wsreg_component **pp = NULL;

		*pppws_children = wsreg_get_child_components(*ppws);
		/*
		 * If we found no children in the registry, try to get
		 * references also for system package based components.
		 */
		if (*pppws_children == NULL) {
			*pppws_children = wsreg_get_child_references(*ppws);
		}
		fill_in_comps(*pppws_children, ppws_sysp);

		/*
		 * Count the number of parents till root.  First try to get
		 * real parents (for things in the registry).  Only if that
		 * fails, attempt to get parent references.
		 */
		for (j = 1;
		    (pws_parent = wsreg_get_parent(pws_temp)) != NULL ||
		    (pws_parent = wsreg_get_parent_reference(pws_temp))
		    != NULL; j++) {

			fill_in_comp(pws_parent, ppws_sysp);
			if (pws_temp != *ppws)
				wsreg_free_component(pws_temp);

			pws_temp = pws_parent;
		}

		/*
		 * Allocate an array of pointers to components, with space
		 * for the null terminator at the end of the array.
		 */
		if ((pp = (Wsreg_component **)
		    malloc((uint32_t) sizeof (Wsreg_component *) * (j+1)))
		    == NULL)
			fail(PRODREG_MALLOC);

		for (i = 0; i < (j+1); i++) {
			pp[i] = NULL;
		}

		pws_temp = *ppws;
		for (j = 0;
		    (pws_parent = wsreg_get_parent(pws_temp)) != NULL ||
		    (pws_parent = wsreg_get_parent_reference(pws_temp))
		    != NULL; j++) {

			/* Figure out what the parent is. */
			if (0 == strcmp(wsreg_get_id(pws_parent), ADDL_UUID)) {
				*proot = ADDL;
			}
			if (0 == strcmp(wsreg_get_id(pws_parent), LOCL_UUID)) {
				*proot = LOCL;
			}
			if (0 == strcmp(wsreg_get_id(pws_parent), UNCL_UUID)) {
				*proot = UNCL;
			}
			if (0 == strcmp(wsreg_get_id(pws_parent), SYSS_UUID)) {
				*proot = SYSS;
			}
			if (0 == strcmp(wsreg_get_id(pws_parent), SYSL_UUID)) {
				*proot = SYSL;
			}
			if (0 == strcmp(wsreg_get_id(pws_parent),
			    global_ENTR_UUID)) {
				*proot = ENTIRE;
			}

			fill_in_comp(pws_parent, ppws_sysp);
			pp[j] = pws_parent;

			pws_temp = pws_parent;
		}

		/*
		 * Reverse the ordre of the parents as they are currently
		 * listed as they were found, not as they should be displayed.
		 */
		for (i = 0; j > 1 && i < (j / 2); i++) {
			int k = j - i - 1;
			Wsreg_component *pws_temp;
			pws_temp = pp[i];
			pp[i] = pp[k];
			pp[k] = pws_temp;
		}

		*pppws_parent = pp;
		return (1);
	}
	return (0);
}


/*
 * make_arglist
 *
 * This routine is only used to create a string which is the concatenation
 * of all items in an argument list.  This is used to output a debug trace
 * of commands given to prodreg.
 *
 *   i     The number of the argument to start outputting.
 *   j     The number of the argument to stop outputting (usually argc)
 *   argv  The argument list.
 *
 * Returns:  A newly allocated string.  The caller must free this string.
 * Side effects: None.
 */
#ifndef NDEBUG
char *
make_arglist(int i, int j, char **argv)
{
	int h;
	uint32_t sz = 0;
	char *pc = NULL;

	for (h = i; (h < j) && (argv[h] != NULL); h++)
		sz += strlen(argv[h]) + 1;

	pc = (char *) malloc(sz + 1);
	if (pc == NULL) fail(PRODREG_MALLOC);
	(void *) memset(pc, 0, (sz + 1));

	for (h = i; (h < j) && (argv[h] != NULL); h++)
		(void) sprintf(&pc[strlen(pc)], "%s ", argv[h]);

	return (pc);
}
#endif
