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

#pragma ident	"@(#)reg_query.c	1.7	06/02/27 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "wsreg.h"
#include "reg_query.h"
#include "string_util.h"
#include "file_util.h"

/*
 * The Reg_query object only has static methods, so there is never
 * a need to create more than one.  Once the object is created,
 * we will save a reference to that object and pass it to all
 * clients requiring a Reg_query object.  This object is never to
 * be freed (hence no free method).
 */
static Reg_query *query_obj = NULL;

/*
 * Creates and returns a new query structure.
 */
static Wsreg_query *
rq_create(void)
{
	Wsreg_query *query = (Wsreg_query*)wsreg_malloc(sizeof (Wsreg_query));
	memset(query, 0, sizeof (Wsreg_query));
	return (query);
}

/*
 * Frees the specified query.
 */
static void
rq_free(Wsreg_query *query)
{
	if (query->id != NULL) {
		free(query->id);
		query->id = NULL;
	}
	if (query->unique_name != NULL) {
		free(query->unique_name);
		query->unique_name = NULL;
	}
	if (query->version != NULL) {
		free(query->version);
		query->version = NULL;
	}
	if (query->location != NULL) {
		free(query->location);
		query->location = NULL;
	}
	free(query);
	query = NULL;
}

/*
 * Sets the specified id into the specified query.
 */
static int
rq_set_id(Wsreg_query *query, const char *id)
{
	if (query->id != NULL) {
		free(query->id);
		query->id = NULL;
	}
	if (id != NULL) {
		String_util *sutil = _wsreg_strutil_initialize();
		query->id = sutil->clone(id);

		/*
		 * Trim the whitespace from the end of the
		 * id.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(query->id);
	}
	return (1);
}

/*
 * Returns the id from the specified query.  The resulting
 * id is not a clone, so the caller should not free it.
 */
static char *
rq_get_id(const Wsreg_query *query)
{
	return (query->id);
}

/*
 * Sets the specified unique name into the specified query.
 */
static int
rq_set_unique_name(Wsreg_query *query, const char *name)
{
	if (query->unique_name != NULL) {
		free(query->unique_name);
		query->unique_name = NULL;
	}
	if (name != NULL) {
		String_util *sutil = _wsreg_strutil_initialize();
		query->unique_name = sutil->clone(name);

		/*
		 * Trim the whitespace from the end of the
		 * unique_name.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(query->unique_name);
	}
	return (1);
}

/*
 * Returns the unique name from the specified query.  The
 * resulting unique name is not a clone, so the caller should
 * not free it.
 */
static char *
rq_get_unique_name(const Wsreg_query *query)
{
	return (query->unique_name);
}

/*
 * Sets the specified version into the specified query.
 */
static int
rq_set_version(Wsreg_query *query, const char *version)
{
	if (query->version != NULL) {
		free(query->version);
		query->version = NULL;
	}
	if (version != NULL) {
		String_util *sutil = _wsreg_strutil_initialize();
		query->version = sutil->clone(version);

		/*
		 * Trim the whitespace from the end of the
		 * version.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(query->version);
	}
	return (1);
}

/*
 * Returns the version from the specified query. The resulting
 * version is not a clone, so the caller should not free it.
 */
static char *
rq_get_version(const Wsreg_query *query)
{
	return (query->version);
}

/*
 * Sets the specified instance into the specified query.
 */
static int
rq_set_instance(Wsreg_query *query, int instance)
{
	query->instance = instance;
	return (1);
}

/*
 * Returns the instance from the specified query.
 */
static int
rq_get_instance(const Wsreg_query *query)
{
	return (query->instance);
}

/*
 * Sets the specified location into the specified query.
 */
static int
rq_set_location(Wsreg_query *query, const char *location)
{
	if (query->location != NULL) {
		free(query->location);
		query->location = NULL;
	}
	if (location != NULL) {
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * Be sure to use the canonical path.  All paths
		 * in the registry are canonical.
		 */
		query->location = futil->get_canonical_path(location);
	}
	return (1);
}

/*
 * Returns the location from the specified query.  The location
 * is not a clone, so the caller should not free it.
 */
static char *
rq_get_location(const Wsreg_query *query)
{
	return (query->location);
}

/*
 * Initializes the Reg_query object.  Since there are no non-static
 * methods and no object-private data, there is no need to ever
 * create more than one Reg_query object.  There is no free
 * method for this object.
 */
Reg_query *
_wsreg_query_initialize()
{
	Reg_query *rq = query_obj;
	if (rq == NULL) {
		rq = (Reg_query *)wsreg_malloc(sizeof (Reg_query));
		/*
		 * Initialize the method set.
		 */
		rq->create = rq_create;
		rq->free = rq_free;
		rq->set_id = rq_set_id;
		rq->get_id = rq_get_id;
		rq->set_unique_name = rq_set_unique_name;
		rq->get_unique_name = rq_get_unique_name;
		rq->set_version = rq_set_version;
		rq->get_version = rq_get_version;
		rq->set_instance = rq_set_instance;
		rq->get_instance = rq_get_instance;
		rq->set_location = rq_set_location;
		rq->get_location = rq_get_location;

		query_obj = rq;
	}
	return (rq);
}
