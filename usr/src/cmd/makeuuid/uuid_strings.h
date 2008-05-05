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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef	_UUID_STRINGS_H
#define	_UUID_STRINGS_H


#ifdef	__cplusplus
extern "C" {
#endif

/*
 * This file contains text strings generic to the makeuuid program.
 *
 */

/*
 * main.c
 */
#define	UUID_USAGE		dgettext(TEXT_DOMAIN, \
	"usage: makeuuid [-e ethernet_address] [-n count] " \
	    "[-R alternate_root]")

#define	UUID_INVALID_COUNT	dgettext(TEXT_DOMAIN, \
	"invalid count: %s")

#define	UUID_NO_MEM		dgettext(TEXT_DOMAIN, \
	"out of memory")

#define	UUID_BAD_ETHERNET	dgettext(TEXT_DOMAIN, \
	"Invalid ethernet address (must be xx:xx:xx:xx:xx:xx)")

#define	UUID_ERROR		dgettext(TEXT_DOMAIN, \
	"%s: ERROR: ")

#define	UUID_NOLOCK		dgettext(TEXT_DOMAIN, \
	"Cannot lock <%s> for reading and writing")

#define	UUID_NOETHERNET		dgettext(TEXT_DOMAIN, \
	"Cannot determine system ethernet address")

#ifdef __cplusplus
}
#endif

#endif /* _UUID_STRINGS_H */
