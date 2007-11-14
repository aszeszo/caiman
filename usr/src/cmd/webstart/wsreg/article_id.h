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

#ifndef _ARTICLE_ID_H
#define	_ARTICLE_ID_H

#pragma ident	"@(#)article_id.h	1.4	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"

#define	Article_id struct _Article_id

struct _Article_id_private;
struct _Article_id
{
	char *(*create_id)();
	Boolean (*is_legal_id)(const char *id);
};

Article_id *_wsreg_artid_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _ARTICLE_ID_H */
