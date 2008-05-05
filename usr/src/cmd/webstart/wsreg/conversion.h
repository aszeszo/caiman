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

#ifndef _CONVERSION_H
#define	_CONVERSION_H


#ifdef __cplusplus
extern "C" {
#endif

#include "wsreg.h"
#include "article.h"
#include "progress.h"

#define	Conversion struct _Conversion
struct _Conversion_private;

struct _Conversion
{
	/*
	 * Creates a new Conversion object.  Same as
	 * the _wsreg_conversion_create function.
	 */
	Conversion *(*create)(Progress *progress);

	/*
	 * Frees the specified Conversion object.
	 */
	void (*free)(Conversion *conversion);

	/*
	 * Adds the specified Article to the specified
	 * Conversion object.  All Articles added can
	 * be registered with a subsequent call to
	 * the register_components method.
	 */
	void (*add_article)(Conversion *c, Article *a);

	/*
	 * Converts the Articles set into the specified Conversion
	 * object into Wsreg_components and registers them into
	 * the product registry.  Returns the number of Articles
	 * converted and registered.  If specified, the parent
	 * component is assigned as the parent of all components
	 * being registered.
	 *
	 * The prunePkgList flag indicates whether or not the
	 * pkg list should be pruned to reflect the packages
	 * actually installed on the system.
	 */
	int (*register_components)(Conversion *c,
	    Wsreg_component *parent_component,
	    Boolean prunePkgList);

	/*
	 * Creates parent/child Article associations.  When
	 * a data sheet is read in from stdin (as a result of
	 * a prodreg "register" command, the Articles read in
	 * do not correctly identify parent/child relationships
	 * because the id (9 digit random number) is generally
	 * created in the prodreg application - not in the
	 * DataSheet object.
	 *
	 * This static method fixes up the parent/child
	 * relationships.
	 */
	void (*create_associations)(List *article_list);

	struct _Conversion_private *pdata;
};

Conversion *_wsreg_conversion_create(Progress *progress);

#ifdef	__cplusplus
}
#endif

#endif /* _CONVERSION_H */
