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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)revision.c	1.6	06/02/27 SMI"

#include <strings.h>
#include "revision.h"
#include "list.h"
#include "string_util.h"
#include "wsreg.h"

/*
 * The structure used to associate private data with
 * a revision object.
 */
struct _Revision_private
{
	char *version;
	List* version_list;
	unsigned long build_date;
	unsigned long install_date;
	char *annotation;
} _Revision_private;

/*
 * Creates a revision from the specified buffer.
 */
static Revision *
rev_from_string(char *buffer)
{
	Revision *r = NULL;
	char version1[100];
	char version2[100];
	unsigned long date1;
	unsigned long date2;

	(void) sscanf(buffer, "%s%s%ld%ld",
	    version1, version2,
	    &date1, &date2);
	r = _wsreg_revision_create();
	r->set_version(r, version1);
	r->set_build_date(r, date1);
	r->set_install_date(r, date2);
	return (r);
}

/*
 * Frees the specified revision.
 */
static void
rev_free(Revision *r)
{
	if (r->pdata->version != NULL)
		free(r->pdata->version);
	if (r->pdata->version_list != NULL)
		r->pdata->version_list->free(
			r->pdata->version_list, free);
	if (r->pdata->annotation != NULL)
		free(r->pdata->annotation);
	free(r->pdata);
	free(r);
}

/*
 * Sets the specified version into the specified revision.
 */
static Boolean
rev_set_version(Revision *r, const char *version)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (r->pdata->version != NULL) {
		free(r->pdata->version);
		r->pdata->version = NULL;
	}
	if (version != NULL)
		r->pdata->version = sutil->clone(version);
	return (TRUE);
}

/*
 * Returns the version from the specified revision.  The
 * version is not a clone, so the caller should not
 * free it.
 */
static char *
rev_get_version(const Revision *r)
{
	return (r->pdata->version);
}

/*
 * Sets the specified build date into the specified revision.
 */
static Boolean
rev_set_build_date(Revision *r, unsigned long build_date)
{
	r->pdata->build_date = build_date;
	return (TRUE);
}

/*
 * Returns the build date from the specified revision.
 */
static unsigned long
rev_get_build_date(const Revision *r)
{
	return (r->pdata->build_date);
}

/*
 * Sets the specified install date into the specified revision.
 */
static Boolean
rev_set_install_date(Revision *r, unsigned long install_date)
{
	r->pdata->install_date = install_date;
	return (TRUE);
}

/*
 * Returns the install date from the specified revision.
 */
static unsigned long
rev_get_install_date(const Revision *r)
{
	return (r->pdata->install_date);
}

/*
 * Sets the specified annotation int othe specified revision.
 */
static Boolean
rev_set_annotation(Revision *r, const char *annotation)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (r->pdata->annotation != NULL) {
		free(r->pdata->annotation);
		r->pdata->annotation = NULL;
	}
	if (annotation != NULL)
		r->pdata->annotation = sutil->clone(annotation);
	return (TRUE);
}

/*
 * Returns the annotation from the specified revision.  The
 * resulting annotation is not a clone, so the caller should not
 * free it.
 */
static char *
rev_get_annotation(const Revision *r)
{
	return (r->pdata->annotation);
}

/*
 * Returns a clone of the specified revision.  The caller is
 * responsible for freeing the resulting clone.
 */
static Revision *
rev_clone(const Revision *r)
{
	Revision *clone = NULL;
	clone = r->create();
	clone->set_version(clone, r->get_version(r));
	clone->set_build_date(clone, r->get_build_date(r));
	clone->set_install_date(clone, r->get_install_date(r));
	clone->set_annotation(clone, r->get_annotation(r));

	return (clone);
}

/*
 * Prints the specified revision to the specified file.  The
 * prefix will precede each line printed.
 */
static void
rev_print(Revision *r, FILE *file, const char *prefix)
{
	fprintf(file, "%sRevision{\n", prefix);
	if (r == NULL) {
		fprintf(file, "%s\tNULL\n", prefix);
	} else {
		fprintf(file, "%s\tversion=%s\n", prefix,
		    r->pdata->version?r->pdata->version:"NULL");
		if (r->pdata->version_list != NULL) {
			List *vlist = r->pdata->version_list;
			fprintf(file, "%s\tversion_list={\n", prefix);
			vlist->reset_iterator(vlist);
			while (vlist->has_more_elements(vlist)) {
				char *version = (char *)
				    vlist->next_element(vlist);
				fprintf(file, "%s\t\t%s\n", prefix, version);
			}
			fprintf(file, "%s\t}\n", prefix);
		}
		fprintf(file, "%s\tbuild_date=%ld\n", prefix,
		    r->pdata->build_date);
		fprintf(file, "%s\tinstall_date=%ld\n", prefix,
		    r->pdata->install_date);
		if (r->pdata->annotation != NULL) {
			fprintf(file, "%s\tannotation=%s\n", prefix,
			    r->pdata->annotation);
		}
	}
	fprintf(file, "}\n");
}

/*
 * Frees the specified array of revisions.  The array and
 * its contents will be freed as a result of calling this
 * function.
 */
static void
rev_free_array(Revision **array)
{
	int index = 0;
	while (array[index] != NULL) {
		array[index]->free(array[index]);
		index++;
	}
	free(array);
}

/*
 * Creates a new revision object and returns it to the caller.
 * It is the responsibility of the caller to free the resulting
 * revision.
 */
Revision *
_wsreg_revision_create()
{
	Revision *r = (Revision*)wsreg_malloc(sizeof (Revision));
	struct _Revision_private *p = NULL;

	/*
	 * Load the method set.
	 */
	r->create = _wsreg_revision_create;
	r->free = rev_free;
	r->from_string = rev_from_string;
	r->set_version = rev_set_version;
	r->get_version = rev_get_version;
	r->set_build_date = rev_set_build_date;
	r->get_build_date = rev_get_build_date;
	r->set_install_date = rev_set_install_date;
	r->get_install_date = rev_get_install_date;
	r->set_annotation = rev_set_annotation;
	r->get_annotation = rev_get_annotation;
	r->print = rev_print;
	r->clone = rev_clone;
	r->free_array = rev_free_array;

	p = (struct _Revision_private *)
	    wsreg_malloc(sizeof (struct _Revision_private));
	memset(p, 0, sizeof (struct _Revision_private));
	r->pdata = p;
	return (r);
}
