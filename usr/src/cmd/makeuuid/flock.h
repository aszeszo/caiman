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

#ifndef _FLOCK_H
#define	_FLOCK_H


/*
 * Module:		flock, The file locking library.
 *
 * Description:	This is the file locking library used to obtain and
 *		release file-level locks.
 */

#ifdef	__cplusplus
extern "C" {
#endif

/*
 * local functions
 */
int file_lock(int, int, int);
int file_unlock(int);
int file_available(int);

#ifdef __cplusplus
}
#endif

#endif /* _FLOCK_H */
