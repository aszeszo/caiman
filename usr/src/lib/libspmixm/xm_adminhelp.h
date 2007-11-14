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



/*
 * Module:	xm_adminhelp.h
 * Group:	libspmixm
 * Description:
 */

#ifndef	_ADMINHELP_H_
#define	_ADMINHELP_H_

#pragma ident	"@(#)xm_adminhelp.h	1.2	07/11/12 SMI"

#include "xm_strings.h"

#define	XM_HELP_TITLE	ILIBSTR("Help")
#define	XM_AH_TOPICS	ILIBSTR("Topics")
#define	XM_AH_HOWTO	ILIBSTR("How To")
#define	XM_AH_REFER	ILIBSTR("Reference")
#define	XM_AH_PREV	ILIBSTR("Previous")
#define	XM_AH_DONE	ILIBSTR("Done")
#define	XM_AH_CANTOP	ILIBSTR("Can't open %s\n")
#define	XM_AH_LDTAB	ILIBSTR("unexpected leading tab")
#define	XM_AH_BLANK	ILIBSTR("blank line")
#define	XM_AH_TOOMANY	ILIBSTR("too many tokens")
#define	XM_AH_EMPTY	ILIBSTR("empty file")
#define	XM_AH_SEEK	ILIBSTR("can't seek in file: %s\n")
#define	XM_AH_READ	ILIBSTR("can't read file: %s\n")
#define	XM_AH_SYNTAX	\
	ILIBSTR("syntax error, file=%s\n\tline number=%d, \t=%s=\n")

#endif	/* _ADMINHELP_H_ */
