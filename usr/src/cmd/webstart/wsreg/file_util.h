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

#ifndef _FILE_UTIL_H
#define	_FILE_UTIL_H

#pragma ident	"@(#)file_util.h	1.5	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"
#include "list.h"

#define	File_util struct _File_util

struct _File_util
{
	Boolean (*exists)(const char *path);
	Boolean (*is_file)(const char *path);
	Boolean (*is_directory)(const char *path);
	Boolean (*can_read)(const char *path);
	Boolean (*can_write)(const char *path);
	off_t (*length)(const char *path);
	char *(*get_name)(const char *path);
	char *(*get_parent)(const char *path);
	List *(*list_files)(const char *path);
	void (*remove)(const char *path);
	char *(*get_temp_name)();
	Boolean (*is_link)(const char *path);
	char *(*get_canonical_path)(const char *path);
};

File_util *_wsreg_fileutil_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _FILE_UTIL_H */
