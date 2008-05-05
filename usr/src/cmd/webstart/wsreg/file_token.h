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

#ifndef _FILE_TOKEN_H
#define	_FILE_TOKEN_H


#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"

#define	File_token struct _File_token

	struct _File_token_private;
	struct _File_token
	{
		void (*free)(File_token *ft);
		Boolean  (*equals)(File_token *ft1, File_token *ft2);
		Boolean  (*is_newer)(File_token *ft1, File_token *ft2);
		File_token *(*clone)(File_token *ft);
		void (*print)(File_token *ft);

		struct _File_token_private *pdata;
	};

/*
 * Creates a file token
 */
	File_token *_wsreg_ftoken_create(const char *filename);


#ifdef	__cplusplus
}
#endif

#endif /* _FILE_TOKEN_H */
