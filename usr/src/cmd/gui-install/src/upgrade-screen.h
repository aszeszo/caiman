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

#ifndef __UPGRADE_SCREEN_H
#define	__UPGRADE_SCREEN_H


#ifdef __cplusplus
extern "C" {
#endif

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

void		show_upgrade_screen(gboolean show);

gboolean	is_selected_target_validated(void);

void		validate_upgrade_target(void);

void		get_upgrade_info(void);

void		upgrade_info_cleanup(void);

void		upgrade_disk_screen_init(void);

void		upgrade_xml_init(void);

void		upgrade_detection_screen_init(void);

gboolean	add_timeout(void);

gboolean	upgradeable_instance_found(void);

#ifdef __cplusplus
}
#endif

#endif /* __UPGRADE_SCREEN_H */
