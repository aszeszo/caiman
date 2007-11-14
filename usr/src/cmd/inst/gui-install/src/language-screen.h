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

#ifndef __LANGUAGE_SCREEN_H
#define	__LANGUAGE_SCREEN_H

#pragma ident	"@(#)language-screen.h	1.1	07/08/03 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#define	MAX_LANG_STR_LEN 70

GtkWidget*	language_screen_init(GladeXML *winxml);

void		get_default_language(void);

void		get_default_locale(void);

void		language_cleanup(void);

void		construct_language_string(gchar **str,
				gboolean include_CR,
				gchar delimeter);

void		construct_locale_string(gchar **str,
				gboolean include_CR,
				gchar delimeter);

#ifdef __cplusplus
}
#endif

#endif /* __LANGUAGE_SCREEN_H */
