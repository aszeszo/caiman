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


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wsreg.h>
#include <assert.h>
#include <sys/fcntl.h>
#include <errno.h>
#include "prodreg_cli.h"

/* --------------------------------------------------------------------- */

/*
 * freesafe
 *
 * A safe way of freeing allocated memory.  It will not free a NULL
 * pointer.  After freeing a buffer, it sets the pointer to NULL.
 */
static void
freesafe(char **ppc)
{
	if (ppc == NULL || *ppc == NULL)
		return;
	free(*ppc);
	*ppc = NULL;
}


/* --------------------------------------------------------------------- */

/*
 * free_list
 *
 * As per freesafe, but for NULL terminated arrays of pointers.
 */
static void
free_list(char ***pppc)
{
	int i;
	if (pppc == NULL)
		return;
	for (i = 0; (*pppc)[i] != NULL; i++) {
		free ((*pppc)[i]);
	}
	free(*pppc);
	*pppc = NULL;
}

#ifndef NDEBUG
static void
dump_list(char *pctitle, char **ppc)
{
	int i;
	(void) printf("%s: ", pctitle);
	if (ppc == NULL)
		(void) printf("NULL\n");
	for (i = 0; ppc[i] != NULL; i++) {
		(void) printf("\"%s\" ", (char *)ppc[i]);
	}
	(void) printf("\n");
}
#endif /* NDEBUG */

/* --------------------------------------------------------------------- */
#if 0
/*
 * unquote
 *
 * Anything which is preceded by a backslash is assumed to be quoted.
 * This routine returns a new string which has the quotes removed.
 * The caller must free the returned string.  An error is signaled
 * by returning a NULL.
 */
static char *
unquote(const char *pcStr)
{
	int i, count = 0;
	char *pc;
	if (pcStr == NULL)
		return (NULL);
	pc = (char *)calloc(strlen(pcStr) + 1, 1);
	for (i = 0; pc != NULL && pcStr[i] != '\0'; i++) {

		if (pcStr[i] == '\\') {
			if (pcStr[i + 1] == '\\') {
				pc[count++] = '\\';
				i++; /* skip one backslash */
			}
			continue;
		}

		pc[count++] = pcStr[i];
	}
	return (pc);
}
#endif

/*
 * trim_indexes
 *
 * This routine takes a string and a begin (a) and end (b).  The
 * beginning is advanced past all spaces and returned in *pi1.
 * The end is retreated past all spaces and returned in *pi2.
 * These recalculated indexes will be used to copy the trimmed string
 * in another routine.
 */
static void
trim_indexes(const char *pc, int a, int b, int *pi1, int *pi2)
{
	while (pc[a] != '\0' && a < b &&
		(pc[a] == ' ' || pc[a] == '\t' ||
		pc[a] == '\n' || pc[a] == '\r')) {
		a++;
	}

	while (b > a &&
		(pc[b] == ' ' || pc[b] == '\t' ||
		pc[b] == '\n' || pc[b] == '\r')) {
		b--;
	}
	*pi1 = a;
	*pi2 = b;
}

/*
 * get_field
 *
 * Extract a 'field' from a string which is the first instance
 * bounded by begin and end characters supplied.  The extraction
 * will not count begin and end characters which were escaped
 * using a '\' character.  Finally, a version of the string
 * without the 'field' from begin to end will be returned.
 *
 * It is assumed the 'field' is present only at the end of the
 * supplied string.  For example:
 * " Input string \{ 1, 2, 3 \} { 4, \{ 5 \}, 6 }"
 * will return
 * "4, \{ 5 \}, 6"
 * and set *ppcNofield to
 * "Input string \{ 1, 2, 3 \}"
 *
 * Note that in both cases, white space before and after the
 * data string has been trimmed.
 *
 * These returned strings need to be unquoted in order to return
 * them to their original state.
 *
 * All returned strings must be freed by the caller.
 */
static char *get_field(const char *pcStr, char begin, char end,
	char **ppcNofield)
{
	int i, a = -1, b = -1, count = 0, a_after, b_before;
	char *pc = NULL, *pc2;

	*ppcNofield = NULL;

	if (pcStr == NULL)
		return (NULL);

	for (i = 0; pcStr[i] != '\0'; i++) {
		if (a == -1) {
			if (pcStr[i] == begin &&
			    (i == 0 ||
			    (i > 0 && pcStr[i - 1] != '\\'))) {
				a = i + 1;
				continue;
			}
		} else if (b == -1) {
			if (pcStr[i] == end &&
				pcStr[i - 1] != '\\') {
				b = i - 1;
				break;
			}
		}
	}

	if (a == -1 || b == -1)
		return (NULL);

	trim_indexes(pcStr, a, b, &a_after, &b_before);
	pc = (char *)calloc((b_before - a_after) + 2, 1);

	for (i = a_after; pc != NULL && i <= b_before; i++) {

		pc[count++] = pcStr[i];

	}

	pc2 = (char *)calloc(a + 2, 1);
	if (pc2 == NULL) {
		if (pc)
			free(pc);
		return (NULL);
	}

	/*
	 * We must set the end of the initial string to a-2 since a is
	 * pointing at the first character after the 'begin' character.
	 * a-1 points at the begin character. a-2 is the character which
	 * precedes the begin character.
	 */
	trim_indexes(pcStr, 0, a - 2, &a_after, &b_before);
	count = 0;
	for (i = a_after; i <= b_before; i++)
		pc2[count++] = pcStr[i];

	*ppcNofield = pc2;

	return (pc);
}

static void
get_2_fields(const char *pcStr, char begin, char end,
    char **ppcID, char **ppcInst, char **ppcVer)
{
	int i, a = -1, b = -1, c = -1, d = -1, count = 0, a_after, b_before;
	char *pc1 = NULL, *pc2 = NULL, *pc3 = NULL;

	if (pcStr == NULL)
		return;

	for (i = 0; pcStr[i] != '\0'; i++) {
		if (a == -1) {
			if (pcStr[i] == begin &&
			    (i == 0 ||
			    (i > 0 && pcStr[i - 1] != '\\'))) {
				a = i + 1;
				continue;
			}
		} else if (b == -1) {
			if (pcStr[i] == end &&
				pcStr[i - 1] != '\\') {
				b = i - 1;
				continue;
			}
		} else if (c == -1) {
			if (pcStr[i] == begin &&
			    (pcStr[i - 1] != '\\')) {
				c = i + 1;
				continue;
			}
		} else if (d == -1) {
			if (pcStr[i] == end &&
			    pcStr[i - 1] != '\\') {
				d = i - 1;
				break;
			}
		}
	}

	if (a == -1 || b == -1 || c == -1 || d == -1)
		return;

	/* Calculate the ID field. */
	pc1 = (char *)calloc(a + 2, 1);
	if (pc1 == NULL) {
		return;
	}

	/*
	 * We must set the end of the initial string to a-2 since a is
	 * pointing at the first character after the 'begin' character.
	 * a-1 points at the begin character. a-2 is the character which
	 * precedes the begin character.
	 */
	trim_indexes(pcStr, 0, a - 2, &a_after, &b_before);
	count = 0;
	for (i = a_after; i <= b_before; i++)
		pc1[count++] = pcStr[i];

	/* Calculate the Instance field */
	trim_indexes(pcStr, a, b, &a_after, &b_before);
	pc2 = (char *)calloc((b_before - a_after) + 2, 1);
	if (pc2 == NULL) {
		free(pc1);
		return;
	}
	count = 0;
	for (i = a_after; pc2 != NULL && i <= b_before; i++) {
		pc2[count++] = pcStr[i];
	}

	/* Calculate the version field. */
	trim_indexes(pcStr, c, d, &a_after, &b_before);
	pc3 = (char *)calloc((b_before - a_after) + 2, 1);
	if (pc3 == NULL) {
		free(pc1);
		free(pc2);
		return;
	}

	count = 0;
	for (i = a_after; i <= b_before; i++)
		pc3[count++] = pcStr[i];

	*ppcID = pc1;
	*ppcInst = pc2;
	*ppcVer = pc3;
}


/* --------------------------------------------------------------------- */
static Wsreg_component *
create_comp(const char *pcUUID, const char *pcinst, const char *pcVer)
{
	int i;
	Wsreg_component *pws = NULL;

	errno = 0;
	i = atoi(pcinst);
	if (errno != 0 || i == 0)
		return (NULL);
	pws = wsreg_create_component(pcUUID);
	if (pws != NULL)  {
		if (wsreg_set_instance(pws, i) == 0 ||
		    wsreg_set_version(pws, pcVer) == 0) {
			wsreg_free_component(pws);
			return (NULL);
		}
	}
	return (pws);
}

/* --------------------------------------------------------------------- */
static int
set_parent(Wsreg_component *pws, char *pcParent)
{
	Wsreg_component *pws1 = NULL;
	int result = 1; /* success */
	char *pcID = NULL, *pcInst = NULL, *pcVer = NULL;
	char buf[2048];

	if (pcParent) {

		get_2_fields(pcParent, '{', '}', &pcID, &pcInst, &pcVer);
		if (pcID && pcInst && pcVer)
			pws1 = create_comp(pcID, pcInst, pcVer);
		else
			result = 0;
		if (pws1) {
			wsreg_set_parent(pws, pws1);
			wsreg_free_component(pws1);
		}

		freesafe(&pcID);
		freesafe(&pcInst);
		freesafe(&pcVer);

		if (pws1 == NULL) {
			(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD,
			    "-P", pcParent);
			(void) fprintf(stderr, buf);
			result = 0;
		}
	}
	return (result); /* success */
}

static int
set_back(Wsreg_component *pws, char **ppcBack)
{
	int i;
	char buf[2048];

	for (i = 0; ppcBack && ppcBack[i]; i++) {
		if (wsreg_add_compatible_version(pws, ppcBack[i]) == 0) {
			(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD,
			    "-b", ppcBack[i]);
			(void) fprintf(stderr, buf);
			return (0); /* failure */
		}
	}
	return (1); /* success */
}

static int
set_att(Wsreg_component *pws, char **ppcAtt)
{
	int i, e;
	char *pcA = NULL, *pcB = NULL;
	char buf[2048];

	for (i = 0; ppcAtt && ppcAtt[i]; i++) {

		pcB = get_field(ppcAtt[i], '{', '}', &pcA);
		if (pcB == NULL)
			pcB = strdup("");

		if (pcA && pcB)
			e = wsreg_set_data(pws, pcA, pcB);
		if (pcA == NULL || pcB == NULL || e == 0) {
			(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD,
			    "-D", ppcAtt[i]);
			(void) fprintf(stderr, buf);
			return (0); /* failure */
		}
		freesafe(&pcA);
		freesafe(&pcB);
	}

	return (1); /* success */
}

static int
set_dname(Wsreg_component *pws, char **ppcDname)
{
	int i, e;
	char *pcA = NULL, *pcB = NULL;
	char buf[2048];

	for (i = 0; ppcDname && ppcDname[i]; i++) {

		pcB = get_field(ppcDname[i], '{', '}', &pcA);
		if (pcA && pcB)
			e = wsreg_add_display_name(pws, pcB, pcA);
		if (pcA == NULL || pcB == NULL || e == 0) {
			(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD,
			    "-n", ppcDname[i]);
			(void) fprintf(stderr, buf);
			return (0); /* failure */
		}
		freesafe(&pcA);
		freesafe(&pcB);
	}
	return (1); /* success */
}

#define	REG_DEPENDER	1
#define	REG_REQUIRER	2
#define	REG_CHILD		3
static int
set_comp(Wsreg_component *pws, char **ppcComp, int i)
{
	int x;
	char *pcID = NULL, *pcInst = NULL, *pcVer = NULL;
	char *pcCmd = NULL;
	char buf[2048];
	Wsreg_component *pws1 = NULL;
	int result = 1; /* Assume we will succeed. */

	assert(i == REG_DEPENDER || i == REG_REQUIRER || i == REG_CHILD);

	switch (i) {
	case REG_DEPENDER:
		pcCmd = "-d";
		break;
	case REG_REQUIRER:
		pcCmd = "-r";
		break;
	case REG_CHILD:
		pcCmd = "-c";
		break;
	default:
		/* should never happen */
		return (1);
	}

	for (x = 0; ppcComp && ppcComp[x]; x++) {

		get_2_fields(ppcComp[x], '{', '}', &pcID, &pcInst, &pcVer);
		if (pcID == NULL || pcInst == NULL || pcVer == NULL) {
			result = 0; /* failure */
			goto set_comp_done;
		}

		pws1 = create_comp(pcID, pcInst, pcVer);
		if (pws1 == NULL) {
			result = 0;
			goto set_comp_done;
		}
		switch (i) {
		case REG_DEPENDER:
			if (wsreg_add_dependent_component(pws, pws1) == 0)
				result = 0;
			break;
		case REG_REQUIRER:
			if (wsreg_add_required_component(pws, pws1) == 0)
				result = 0;
			break;
		case REG_CHILD:
			if (wsreg_add_child_component(pws, pws1) == 0)
				result = 0;
			break;
		}
		freesafe(&pcInst);
		freesafe(&pcVer);
		freesafe(&pcID);
		wsreg_free_component(pws1);
	}

set_comp_done:
	freesafe(&pcInst);
	freesafe(&pcVer);
	freesafe(&pcID);
	if (pws1)
		wsreg_free_component(pws1);
	if (result == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, pcCmd,
		    ppcComp[x]);
		(void) fprintf(stderr, buf);
	}
	return (result);
}

/* --------------------------------------------------------------------- */

/*
 * prodreg_register
 *
 *   Given a set of registered values, attempt to register a new service.
 *   This registration uses a different library entry point - instead of
 *   wsreg_register() it uses wsreg_().
 *
 *     pcroot 	The install root.
 *     pcUUID	The UUID of the service to register, must not be NULL.
 *     t	The component type to register.
 *     ppcBack	A list of backwards compatible versions.  May be NULL.
 *     ppcChild	A list of child components.  May be NULL.
 *     ppcDep   A list of dependent components.  May be NULL.
 *     ppcReq	A list of required components.  May be NULL.
 *     ppcAtt	A list of attributes.  May be NULL.
 *     ppcDname	A list of display names.  May be NULL.
 *     pcLoc	The install location.  Should not be NULL.
 *     pcParent	The parent of this component.  May be NULL.
 *     pcUname  The unique name of the component.  May be NULL.
 *     pcVer	The version string of this component.  Should not be NULL.
 *     pcVend   The vendor string of this component.  May be NULL.
 *     pcUninst	The uninstaller command for this component.  May be NULL.
 *
 * Returns:  This routine does not return.  It will exit with code 0 on
 *     success, nonzero on failure.
 * Side effects:  The requested componnet may be registered - if the user
 *     has permission, the entry is well formed and the operation succeeds.
 *     An existing registration of the same component at the same location
 *     will be overwritten, replaced by the new registration.
 */
void
prodreg_register(const char *pcroot, char *pcUUID, char *pcType,
    char *ppcBack[], char *ppcChild[], char *ppcDep[],
    char *ppcReq[], char *ppcAtt[], char *ppcDname[],
    char *pcLoc, char *pcParent, char *pcUname,
    char *pcVer, char *pcVend, char *pcUninst)
{
	Wsreg_component *pws = NULL;
	int result = 0, e = 0;
	char buf[2048];

	/* The following code is useful for debugging prodreg_register */
#if 0
	printf("prodreg_register parameters:\n root[%s] uuid[%s] type[%s]\n",
	    pcroot?pcroot:"NULL", pcUUID?pcUUID:"NULL", pcType?pcType:"NULL");
	printf(" loc[%s] parent[%s] uname[%s]\n version[%s] vendor[%s]\n"
	    " uninstaller[%s]\n",
	    pcLoc?pcLoc:"NULL", pcParent?pcParent:"NULL",
	    pcUname?pcUname:"NULL", pcVer?pcVer:"NULL",
	    pcVend?pcVend:"NULL", pcUninst?pcUninst:"NULL");
	dump_list(" backward compatible versions", ppcBack);
	dump_list(" child components", ppcChild);
	dump_list(" dependent components", ppcDep);
	dump_list(" required components", ppcReq);
	dump_list(" attributes", ppcAtt);
	dump_list(" display names", ppcDname);
#endif

	/* Initialize wsreg. */
	if (pcroot == NULL) pcroot = "/";

	if (wsreg_initialize(WSREG_INIT_NORMAL, pcroot) != WSREG_SUCCESS) {
		(void) fprintf(stderr, "%s\n", PRODREG_INIT);
		result = 1;
		goto prodreg_register_done;
	}

	if (_private_wsreg_can_access_registry(O_RDWR) == 0) {
		(void) fprintf(stderr, "%s\n", PRODREG_CANNOT_WRITE);
		result = 1;
		goto prodreg_register_done;
	}

	/* Create the component and fill in its fields. */
	pws = wsreg_create_component(pcUUID);

	if ((pcParent && set_parent(pws, pcParent) == 0) ||
	    (ppcBack && set_back(pws, ppcBack) == 0) ||
	    (ppcChild && set_comp(pws, ppcChild, REG_CHILD) == 0) ||
	    (ppcReq && set_comp(pws, ppcReq, REG_REQUIRER) == 0) ||
	    (ppcDep && set_comp(pws, ppcDep, REG_DEPENDER) == 0) ||
	    (ppcAtt && set_att(pws, ppcAtt) == 0) ||
	    (ppcDname && set_dname(pws, ppcDname) == 0)) {
		result = 1;
		goto prodreg_register_done;
	}

	if (pcType == NULL || strcmp(pcType, "COMPONENT") == 0)
		wsreg_set_type(pws, WSREG_COMPONENT);
	else if (strcmp(pcType, "FEATURE") == 0)
		wsreg_set_type(pws, WSREG_FEATURE);
	else if (strcmp(pcType, "PRODUCT") == 0)
		wsreg_set_type(pws, WSREG_PRODUCT);
	else {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-t", pcType);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (pcUname != NULL) e = wsreg_set_unique_name(pws, pcUname);
	if (pcUname && e == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-U", pcUname);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (pcLoc != NULL) e = wsreg_set_location(pws, pcLoc);
	if (pcLoc && e == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-p", pcUname);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (pcVer != NULL) e = wsreg_set_version(pws, pcVer);
	if (pcVer && e == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-v", pcUname);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (pcVend != NULL) e = wsreg_set_vendor(pws, pcVend);
	if (pcVend && e == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-V", pcUname);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (pcUninst != NULL) e = wsreg_set_uninstaller(pws, pcUninst);
	if (pcUninst && e == 0) {
		(void) sprintf(buf, PRODREG_REGISTER_PARAM_BAD, "-x", pcUname);
		(void) fprintf(stderr, buf);
		result = 1;
		goto prodreg_register_done;
	}

	if (_private_wsreg_register(pws) == 0) {
		(void) fprintf(stderr, "%s\n", PRODREG_REGISTER_FAILED);
		result = 1;
		goto prodreg_register_done;
	}

prodreg_register_done:

	if (pws)
		wsreg_free_component(pws);

	freesafe(&pcUUID);
	freesafe(&pcType);
	freesafe(&pcLoc);
	freesafe(&pcParent);
	freesafe(&pcUname);
	freesafe(&pcVend);
	freesafe(&pcVer);
	freesafe(&pcUninst);
	free_list(&ppcBack);
	free_list(&ppcChild);
	free_list(&ppcDep);
	free_list(&ppcReq);
	free_list(&ppcAtt);
	free_list(&ppcDname);

	exit(result);
}
