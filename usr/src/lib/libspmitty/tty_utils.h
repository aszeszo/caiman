/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */
/*
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */



#ifndef	_TTY_UTILS_H
#define	_TTY_UTILS_H

#pragma ident	"@(#)tty_utils.h	1.5	07/10/09 SMI"

/*
 * Module:	tty_utils.h
 * Group:	libspmitty
 * Description:
 */

#include "spmitty_api.h"

/*
 * macros usefule for debugging
 */
#define	SPMI_TTYLIB_NAME	"LIBSPMITTY"
#define	TTY_DEBUG	\
	LOGSCR, (get_trace_level() > 0), SPMI_TTYLIB_NAME, DEBUG_LOC
#define	TTY_DEBUG_NOHD	\
	LOGSCR, (get_trace_level() > 0), NULL, DEBUG_LOC
#define	TTY_DEBUG_L1		TTY_DEBUG, LEVEL1
#define	TTY_DEBUG_L1_NOHD	TTY_DEBUG_NOHD, LEVEL1

/* globals */
extern int erasech;
extern int killch;

/*
 * tty_color.c
 */
extern void wcolor_init(void);

extern Fkey_check_func	_fkey_notice_check_func;
extern Fkey_check_func	_fkey_mvwgets_check_func;
extern Fkeys_init_func _fkeys_init_func;
extern Fkey *_fkeys;
extern int _num_fkeys;

/*
 * tty_utils.c
 */
extern int tty_GetForceAlternates(void);

#endif /* _TTY_UTILS_H */
