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

#ifndef _REVISION_H
#define	_REVISION_H

#pragma ident	"@(#)revision.h	1.4	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#include <stdlib.h>
#include "boolean.h"

#define	Revision struct _Revision

struct _Revision_private;

struct _Revision
{
	Revision *(*create)();
	void (*free)(Revision *r);
	Revision *(*from_string)(char *buffer);
	Boolean (*set_version)(Revision *r, const char *version);
	char *(*get_version)(const Revision *r);
	Boolean (*set_build_date)(Revision *r, unsigned long build_date);
	unsigned long (*get_build_date)(const Revision *r);
	Boolean (*set_install_date)(Revision *r, unsigned long install_date);
	unsigned long (*get_install_date)(const Revision *r);
	Boolean (*set_annotation)(Revision *r, const char *annotation);
	char *(*get_annotation)(const Revision *r);
	Revision *(*clone)(const Revision *r);
	void (*print)(Revision *r, FILE *file, const char *prefix);
	void (*free_array)(Revision **array);

	struct _Revision_private *pdata;
};

Revision *_wsreg_revision_create();


#ifdef	__cplusplus
}
#endif

#endif /* _REVISION_H */
