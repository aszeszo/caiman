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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef __WELCOME_SCREEN_H
#define	__WELCOME_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

/* In future this will be provided via an API */
#define	RELEASENOTESURL \
    "http://opensolaris.org/os/project/indiana/resources/relnotes/200811/x86"

typedef struct _WelcomeWindowXML {
	GladeXML *welcomewindowxml;

	GtkWidget *welcomescreenvbox;
	GtkWidget *releasebutton;

	gint installationtype;

} WelcomeWindowXML;

void		welcome_screen_init(void);

void		welcome_screen_set_default_focus(void);

#ifdef __cplusplus
}
#endif

#endif /* __WELCOME_SCREEN_H */
