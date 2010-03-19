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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef	_DISK_H
#define	_DISK_H
#include "Python.h"
#include "structmember.h"

/* We just need some constants, but it fails unless _FILE_OFFSET_BITS=32 */
#undef	_FILE_OFFSET_BITS
#define	_FILE_OFFSET_BITS	32
#include <libdiskmgt.h>
#include <sys/dklabel.h>


typedef struct {
	PyObject_HEAD
	PyObject *geometry;		/* disk geometry */
	PyObject *children;		/* Partition or Slice Tuple */
	PyObject *controller;		/* controller type */
	char *name;			/* disk name */
	char *vendor;			/* Manufacturer */
	char *serialno;			/* Manufacturer assigned */
	uint64_t blocks;		/* nmber of blocks (size in blocks) */
	uint8_t vtoc		:1;	/* disk label has VTOC */
	uint8_t gpt		:1;	/* disk has GTP */
	uint8_t fdisk		:1;	/* disk label has fdisk */
					/* (implies partitions) */
	uint8_t boot 		:1;	/* is it a boot disk */
	uint8_t removable	:1;	/* is it removable */
	uint8_t use_whole	:1;	/* flag to indicate whole disk use */
} TgtDisk;


/*
 * Constants
 * 	v,			cname,	pyname,		value
 *
 * The CONTROLLER_CONSTANTS values need to be the values target instantiation
 * expects (even though they are PyStringObjects).
 * label is converted from td_disk_label_t to a string when it is requested.
 *
 * XXX DM_ seems to be missing SATA and FIREWIRE ?
 */
#define	CONTROLLER_CONSTANTS	\
CONSTANT(DM_CTYPE_ATA,		ata,	"ATA",		DM_CTYPE_ATA)	\
CONSTANT(DM_CTYPE_SCSI,		scsi,	"SCSI",		DM_CTYPE_SCSI)	\
CONSTANT(DM_CTYPE_FIBRE,	fibre,	"FIBRE",	DM_CTYPE_FIBRE)	\
CONSTANT(DM_CTYPE_USB,		usb,	"USB",		DM_CTYPE_USB)

#define	CONSTANT(v, cname, pyname, value) PyObject *cname;
typedef struct {
	CONTROLLER_CONSTANTS
	PyObject *unknown;
} disk_const;
#undef CONSTANT

extern disk_const DiskConst;


#endif	/* _DISK_H */
