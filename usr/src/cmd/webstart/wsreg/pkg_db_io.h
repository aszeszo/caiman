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
 * Copyright 2006 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef	_PKG_DB_IO_H
#define	_PKG_DB_IO_H


#ifdef	__cplusplus
extern "C" {
#endif

#include "wsreg.h"
#include "hashtable.h"
#include "progress.h"

#define	Pkg_db_io struct _Pkg_db_io

struct _Pkg_db_io
{
	Wsreg_component *(*get_pkg_data)(char *pkg_name);
	int (*load_pkg_info)(char *pkg, Wsreg_component *comp);
	int (*get_all_pkg_data)(Hashtable *pkg_table, Progress *progress);
};

Pkg_db_io *_wsreg_pkgdbio_initialize();

/* libadm: pkgparam.c */

extern char *fpkgparam(FILE *, char *);


#ifdef	__cplusplus
}
#endif

#endif	/* _PKG_DB_IO_H */
