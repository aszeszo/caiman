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

#ifndef	_SLICE_H
#define	_SLICE_H
#include "Python.h"
#include "structmember.h"
#include "td_api.h"
#include <sys/vtoc.h> /* for V_UNMNT and V_RONLY */

typedef struct {
	PyObject_HEAD
	PyObject *geometry;		/* disk geometry */
	char *user;			/* user of this slice */
	char *last_mount;		/* last mount point (for UFS) */
	uint64_t offset;		/* offset in disk blocks */
	uint64_t blocks;		/* size in disk blocks */
	uint8_t number;			/* slice number, (0-15) */
	uint8_t tag;			/* slice tag, mountpoint (sort of) */
	uint8_t type;			/* "used by" of this slice */
	uint8_t unmountable	:1;	/* True if slice may not be unmounted */
	uint8_t readonly	:1;	/* True if slice is read only */
	uint8_t modified	:1;	/* True if the user changed slice */
	uint8_t use_whole	:1;	/* True if install should use entire */
					/* slice */
} TgtSlice;


/*
 * Constants
 * 	v,			cname,	pyname,		value
 */
#define	SLICE_TAG_CONSTANTS						\
CONSTANT(V_UNASSIGNED,	unassigned,	"UNASSIGNED",	"unassigned")	\
CONSTANT(V_BOOT,	boot,		"BOOT",		"boot")		\
CONSTANT(V_ROOT,	root,		"ROOT",		"root")		\
CONSTANT(V_SWAP,	swap,		"SWAP",		"swap")		\
CONSTANT(V_USR,		usr,		"USR",		"usr")		\
CONSTANT(V_BACKUP,	backup,		"BACKUP",	"backup")	\
CONSTANT(V_STAND,	stand,		"STAND",	"stand")	\
CONSTANT(V_VAR,		var,		"VAR",		"var")		\
CONSTANT(V_HOME,	home,		"HOME",		"home")		\
CONSTANT(V_ALTSCTR,	altsctr,	"ALTSCTR",	"alternates")	\
CONSTANT(V_RESERVED,	reserved,	"RESERVED",	"reserved")

#define	SLICE_USED_BY_CONSTANTS						\
CONSTANT(1,	mount,	"MOUNT",	TD_SLICE_USEDBY_MOUNT)		\
CONSTANT(2,	svm,	"SVM",		TD_SLICE_USEDBY_SVM)		\
CONSTANT(3,	lu,	"LU",		TD_SLICE_USEDBY_LU)		\
CONSTANT(4,	dump,	"DUMP",		TD_SLICE_USEDBY_DUMP)		\
CONSTANT(5,	vxvm,	"VXVM",		TD_SLICE_USEDBY_VXVM)		\
CONSTANT(6,	fs,	"FS",		TD_SLICE_USEDBY_FS)		\
CONSTANT(7, 	vfstab,	"VFSTAB",	TD_SLICE_USEDBY_VSFTAB)		\
CONSTANT(8,	ezpool,	"EZPOOL",	TD_SLICE_USEDBY_EXPORT_ZPOOL)	\
CONSTANT(9,	azpool,	"AZPOOL",	TD_SLICE_USEDBY_ACTIVE_ZPOOL)	\
CONSTANT(10,	szpool,	"SZPOOL",	TD_SLICE_USEDBY_SPARE_ZPOOL)	\
CONSTANT(11,	czpool,	"CZPOOL",	TD_SLICE_USEDBY_CACHE_ZPOOL)


#define	CONSTANT(v, cname, pyname, value) PyObject *cname;
typedef struct {
	SLICE_TAG_CONSTANTS
	SLICE_USED_BY_CONSTANTS
	PyObject *unknown;
} slice_const;
#undef CONSTANT

extern slice_const SliceConst;


#endif	/* _SLICE_H */
