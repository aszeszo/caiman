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
 * Copyright 1999 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _PKG_DBH
#define	_PKG_DBH

#pragma ident	"@(#)pkg_db.h	1.3	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#define	Pkg_db struct _Pkg_db

struct _Pkg_db
{
	Wsreg_component **(*get_pkg_db)();
};

Pkg_db *_wsreg_pkgdb_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _PKG_DBH */
