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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef __DISK_BLOCK_ORDER_H
#define	__DISK_BLOCK_ORDER_H


#ifdef __cplusplus
extern "C" {
#endif

/* Structure to contain block order layout of disk including free space */
typedef struct _DiskBlockOrder {
	gboolean displayed;
	partition_info_t partinfo;
	struct _DiskBlockOrder *next;
} DiskBlockOrder;

void
installationdisk_reorder_to_blkorder(disk_parts_t *partitions);

void
installationdisk_get_blkorder_layout(disk_info_t *diskinfo,
	disk_parts_t *partitions,
	DiskBlockOrder **_primaryblkorder,
	DiskBlockOrder **_logicalblkorder);

DiskBlockOrder *
installationdisk_blkorder_dup(DiskBlockOrder *srcblkorder);

void
installationdisk_blkorder_free_list(DiskBlockOrder *blkorder);

DiskBlockOrder *
installationdisk_blkorder_getlast(DiskBlockOrder *startblkorder);

DiskBlockOrder *
installationdisk_blkorder_getprev(DiskBlockOrder *startblkorder,
	DiskBlockOrder *blkorder);

DiskBlockOrder *
installationdisk_blkorder_get_by_partition_order(
	DiskBlockOrder *startblkorder,
	gint order);

DiskBlockOrder *
installationdisk_blkorder_get_by_partition_id(
	DiskBlockOrder *startblkorder,
	gint id);

gint
installationdisk_blkorder_get_index(DiskBlockOrder *startblkorder,
	DiskBlockOrder *blkordertoget);

gboolean
update_blkorder_from_partinfo(DiskBlockOrder *startblkorder,
	partition_info_t *partinfo);

gboolean
update_partinfo_from_blkorder(gboolean is_primary,
	DiskBlockOrder *blkorder,
	disk_parts_t *partitions);

void
update_partinfo_from_blkorder_and_display(disk_parts_t *partitions,
	partition_info_t *modpartinfo,
	DiskBlockOrder *curblkorder);

DiskBlockOrder *
installationdisk_blkorder_remove(gboolean is_primary,
	DiskBlockOrder **_startblkorder,
	DiskBlockOrder *blkordertoremove,
	gboolean ret_next_item);

void
installationdisk_blkorder_insert_displayed(
	DiskBlockOrder *startblkorder,
	DiskBlockOrder *newblkorder);

void
installationdisk_blkorder_insert_after(DiskBlockOrder *startblkorder,
	DiskBlockOrder *addafterblkorder,
	DiskBlockOrder *newblkorder,
	gboolean increment_partition_order);

void
installationdisk_blkorder_empty_partinfo_sync(
	disk_parts_t *partitions,
	DiskBlockOrder *startblkorder,
	DiskBlockOrder *curblkorder,
	DiskBlockOrder *newblkorder);

partition_info_t *
installationdisk_get_largest_free_block(gint disknum,
	gboolean setunused,
	DiskBlockOrder *startblkorder,
	partition_info_t *partinfo);

#ifdef __cplusplus
}
#endif

#endif /* __DISK_BLOCK_ORDER_H */
