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

#ifndef __ERROR_LOGGING_H
#define	__ERROR_LOGGING_H

#ifdef __cplusplus
extern "C" {
#endif

#include <config.h>
#include <glib.h>
#include <ls_api.h>

void
gui_error_logging_init(gchar *name);

void
print_from_parts(gboolean header_only,
	const gchar *parttype,
	gint partindex,
	partition_info_t *partinfo,
	gfloat partsize,
	GtkSpinButton *spinner,
	gfloat avail_size);

void
print_partinfo(gint index,
	partition_info_t *partinfo,
	gboolean header);

void
print_partinfos(gint activedisk,
	disk_info_t **alldiskinfo,
	disk_parts_t **modpartitions);

void
print_orig_vs_modified(disk_info_t *diskinfo,
	disk_parts_t *origpartitions,
	disk_parts_t *modpartitions);

void
print_combo_box_number_of_items(GtkComboBox *combo);

void
print_blkorder(disk_info_t *diskinfo,
	DiskBlockOrder *primary,
	DiskBlockOrder *logical);

void
print_gui(InstallationDiskWindowXML instdisk);

#ifdef __cplusplus
}
#endif

#endif /* __ERROR_LOGGING_H */
