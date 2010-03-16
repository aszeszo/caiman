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

#ifndef	_PARTITION_H
#define	_PARTITION_H
#include "Python.h"
#include "structmember.h"
#include <sys/dktp/fdisk.h>
#include <sys/dklabel.h>

/* Why is it libtd uses 32-bit for offset and blocks of partition? */
typedef struct {
	PyObject_HEAD
	PyObject *geometry;		/* TgtGeometry */
	PyObject *children;		/* Slice Tuple */
	uint32_t offset;		/* offset of partition in blocks */
	uint32_t blocks;		/* size in blocks */
	uint16_t type;			/* 0x0-0xFF or 0x182 partition type */
	uint8_t id;			/* fdisk id (0-3) */
	uint8_t active		:1;	/* True if this is active partition */
	uint8_t modified	:1;	/* True if the user changed partition */
	uint8_t use_whole	:1;	/* True if installer should use whole */
					/* partition */
} TgtPartition;


/*
 * These valuses courtesy of:
 * http://www.win.tue.nl/~aeb/partitions/partition_types-1.html
 * and ONs usr/src/cmd/fdisk/fdisk.c
 *
 * There is one problem, 0x82 is the original Solaris and is the current
 * Linux Swap.
 *
 * Currently this is a uint8_t value. So to solve our problem we will make the
 * Linux swap be 0x182. That is it is its true type 0x82 ORed with 0x100.
 *
 * This means when creating a type for instantiation, just mask the now 16-bit
 * value with 0xFF.
 *
 * Also it mens legal values are 0-255 and 386.
 *
 *
 * Separate unique and dups into separate macros. This makes our Python
 * dictionary more space efficient.
 *
 * Constants
 * 	value,	string
 */

#define	UNIQUE_PARTITION_TYPE				\
CONSTANT(0x00, "Empty")					\
CONSTANT(0x01, "FAT12")					\
CONSTANT(0x02, "XENIX /")				\
CONSTANT(0x03, "XENIX /usr")				\
CONSTANT(0x04, "FAT16 (Upto 32M)")			\
CONSTANT(0x05, "DOS Extended")				\
CONSTANT(0x06, "FAT16 (>32M, HUGEDOS)")			\
CONSTANT(0x07, "IFS: NTFS")				\
CONSTANT(0x08, "AIX Boot/QNX(qny)")			\
CONSTANT(0x09, "AIX Data/QNX(qnz)")			\
CONSTANT(0x0A, "OS/2 Boot/Coherent swap")		\
CONSTANT(0x0B, "WIN95 FAT32(Upto 2047GB)")		\
CONSTANT(0x0C, "WIN95 FAT32(LBA)")			\
CONSTANT(0x0E, "WIN95 FAT16(LBA)")			\
CONSTANT(0x0F, "WIN95 Extended(LBA)")			\
CONSTANT(0x10, "OPUS")					\
CONSTANT(0x11, "Hidden FAT12")				\
CONSTANT(0x12, "Diagnostic")				\
CONSTANT(0x14, "Hidden FAT16(Upto 32M)")		\
CONSTANT(0x16, "Hidden FAT16(>=32M)")			\
CONSTANT(0x17, "Hidden IFS: HPFS")			\
CONSTANT(0x18, "AST SmartSleep Partition")		\
CONSTANT(0x19, "Unused/Willowtech Photon")		\
CONSTANT(0x1B, "Hidden FAT32")				\
CONSTANT(0x1C, "Hidden FAT32(LBA)")			\
CONSTANT(0x1E, "Hidden FAT16(LBA)")			\
CONSTANT(0x20, "Unused/OSF1")				\
CONSTANT(0x21, "Reserved/FSo2(Oxygen FS)")		\
CONSTANT(0x22, "Unused/(Oxygen EXT)")			\
CONSTANT(0x24, "NEC DOS 3.x")				\
CONSTANT(0x2A, "AtheOS File System")			\
CONSTANT(0x2B, "SyllableSecure")			\
CONSTANT(0x32, "NOS")					\
CONSTANT(0x35, "JFS on OS/2")				\
CONSTANT(0x38, "THEOS 3.2 2GB")				\
CONSTANT(0x39, "Plan9/THEOS 4")				\
CONSTANT(0x3A, "THEOS 4 4GB")				\
CONSTANT(0x3B, "THEOS 4 Extended")			\
CONSTANT(0x3C, "PartitionMagic Recovery")		\
CONSTANT(0x3D, "Hidden NetWare")			\
CONSTANT(0x40, "Venix 80286")				\
CONSTANT(0x41, "MINIX/PPC PReP Boot")			\
CONSTANT(0x42, "Win2K Dynamic Disk/SFS(DOS)")		\
CONSTANT(0x43, "Linux+DRDOS shared")			\
CONSTANT(0x44, "GoBack partition")			\
CONSTANT(0x45, "Boot-US boot manager")			\
CONSTANT(0x4A, "ALFS/THIN FS for DOS")			\
CONSTANT(0x4C, "Oberon partition")			\
CONSTANT(0x4D, "QNX 4,x")				\
CONSTANT(0x4E, "QNX 4,x 2nd Part")			\
CONSTANT(0x4F, "QNX 4,x 3rd Part")			\
CONSTANT(0x50, "OnTrack DM R/O, Lynx RTOS")		\
CONSTANT(0x51, "OnTrack DM R/W, Novell")		\
CONSTANT(0x52, "CP/M")					\
CONSTANT(0x53, "Disk Manager 6.0 Aux3")			\
CONSTANT(0x54, "Disk Manager 6.0 DDO")			\
CONSTANT(0x55, "EZ-Drive")				\
CONSTANT(0x56, "Golden Bow VFeature/AT&T MS-DOS")	\
CONSTANT(0x57, "DrivePro")				\
CONSTANT(0x5C, "Priam EDisk")				\
CONSTANT(0x63, "Unix SysV, Mach, GNU Hurd")		\
CONSTANT(0x64, "PC-ARMOUR, Netware 286")		\
CONSTANT(0x65, "Netware 386")				\
CONSTANT(0x66, "Netware SMS")				\
CONSTANT(0x69, "Netware NSS")				\
CONSTANT(0x70, "DiskSecure Multi-Boot")			\
CONSTANT(0x74, "Scramdisk partition")			\
CONSTANT(0x75, "IBM PC/IX")				\
CONSTANT(0x77, "M2FS/M2CS,Netware VNDI")		\
CONSTANT(0x78, "XOSL FS")				\
CONSTANT(0x80, "MINIX until 1.4a")			\
CONSTANT(0x81, "MINIX since 1.4b, early Linux")		\
CONSTANT(0x82, "Solaris")				\
CONSTANT(0x83, "Linux native")				\
CONSTANT(0x84, "OS/2 hidden,Win Hibernation")		\
CONSTANT(0x85, "Linux extended")			\
CONSTANT(0x86, "Old Linux RAID,NT FAT16 RAID")		\
CONSTANT(0x87, "NTFS volume set")			\
CONSTANT(0x88, "Linux plaintext part table")		\
CONSTANT(0x8A, "Linux Kernel Partition")		\
CONSTANT(0x8D, "Free FDISK hidden PDOS FAT12")		\
CONSTANT(0x8E, "Linux LVM partition")			\
CONSTANT(0x90, "Free FDISK hidden PDOS FAT16")		\
CONSTANT(0x92, "Free FDISK hidden FAT16 Large")		\
CONSTANT(0x93, "Hidden Linux native, Amoeba")		\
CONSTANT(0x94, "Amoeba Bad Block Table")		\
CONSTANT(0x95, "MIT EXOPC Native")			\
CONSTANT(0x97, "Free FDISK hidden PDOS FAT32")		\
CONSTANT(0x98, "Free FDISK hidden FAT32 LBA")		\
CONSTANT(0x99, "DCE376 logical drive")			\
CONSTANT(0x9A, "Free FDISK hidden FAT16 LBA")		\
CONSTANT(0x9F, "BSD/OS")				\
CONSTANT(0xA0, "Laptop hibernation")			\
CONSTANT(0xA1, "Laptop hibernate,HP SpeedStor")		\
CONSTANT(0xA5, "BSD/386,386BSD,NetBSD,FreeBSD")		\
CONSTANT(0xA6, "OpenBSD,HP SpeedStor")			\
CONSTANT(0xA7, "NeXTStep")				\
CONSTANT(0xA8, "Mac OS-X")				\
CONSTANT(0xA9, "NetBSD")				\
CONSTANT(0xAA, "Olivetti FAT12 1.44MB Service")		\
CONSTANT(0xAB, "Mac OS-X Boot")				\
CONSTANT(0xAE, "ShagOS filesystem")			\
CONSTANT(0xAF, "ShagOS swap")				\
CONSTANT(0xB0, "BootStar Dummy")			\
CONSTANT(0xB6, "Corrupted FAT16 NT Mirror Set")		\
CONSTANT(0xB7, "Corrupted NTFS NT Mirror Set")		\
CONSTANT(0xB8, "Old BSDI BSD/386 swap")			\
CONSTANT(0xBB, "Boot Wizard hidden")			\
CONSTANT(0xBE, "Solaris x86 boot")			\
CONSTANT(0xBF, "Solaris2")				\
CONSTANT(0xC0, "REAL/32 or Novell DOS secured")		\
CONSTANT(0xC1, "DRDOS/secured(FAT12)")			\
CONSTANT(0xC2, "Hidden Linux")				\
CONSTANT(0xC3, "Hidden Linux swap")			\
CONSTANT(0xC4, "DRDOS/secured(FAT16,< 32M)")		\
CONSTANT(0xC5, "DRDOS/secured(Extended)")		\
CONSTANT(0xC6, "NT corrupted FAT16 volume")		\
CONSTANT(0xC7, "NT corrupted NTFS volume")		\
CONSTANT(0xCB, "DRDOS7.04+ secured FAT32(CHS)")		\
CONSTANT(0xCC, "DRDOS7.04+ secured FAT32(LBA)")		\
CONSTANT(0xCD, "CTOS Memdump")				\
CONSTANT(0xCE, "DRDOS7.04+ FAT16X(LBA)")		\
CONSTANT(0xCF, "DRDOS7.04+ secure EXT DOS(LBA)")	\
CONSTANT(0xD0, "REAL/32 secure big, MDOS")		\
CONSTANT(0xD1, "Old MDOS secure FAT12")			\
CONSTANT(0xD4, "Old MDOS secure FAT16 <32M")		\
CONSTANT(0xD5, "Old MDOS secure EXT")			\
CONSTANT(0xD6, "Old MDOS secure FAT16 >=32M")		\
CONSTANT(0xD8, "CP/M-86")				\
CONSTANT(0xDA, "Non-FS Data")				\
CONSTANT(0xDB, "CP/M,Concurrent DOS,CTOS")		\
CONSTANT(0xDD, "Hidden CTOS memdump")			\
CONSTANT(0xDE, "Dell PowerEdge utilities(FAT)")		\
CONSTANT(0xDF, "DG/UX virtual disk manager")		\
CONSTANT(0xE0, "ST AVFS(STMicroelectronics)")		\
CONSTANT(0xE1, "SpeedStor 12-bit FAT EXT")		\
CONSTANT(0xE4, "SpeedStor 16-bit FAT EXT")		\
CONSTANT(0xE5, "Tandy MSDOS")				\
CONSTANT(0xE6, "Storage Dimensions SpeedStor")		\
CONSTANT(0xEB, "BeOS BFS")				\
CONSTANT(0xEC, "SkyOS SkyFS")				\
CONSTANT(0xEE, "EFI Header Indicator")			\
CONSTANT(0xEF, "EFI Filesystem")			\
CONSTANT(0xF0, "Linux/PA-RISC boot loader")		\
CONSTANT(0xF2, "DOS 3.3+ secondary")			\
CONSTANT(0xF3, "SpeedStor Reserved")			\
CONSTANT(0xF4, "SpeedStor Large")			\
CONSTANT(0xF5, "Prologue multi-volume")			\
CONSTANT(0xF9, "pCache")				\
CONSTANT(0xFA, "Bochs")					\
CONSTANT(0xFB, "VMware File System")			\
CONSTANT(0xFC, "VMware swap")				\
CONSTANT(0xFD, "Linux raid autodetect")			\
CONSTANT(0xFE, "NT Disk Administrator hidden")		\
CONSTANT(0xFF, "Xenix Bad Block Table")			\
CONSTANT(0x182, "Linux swap")

#define	TP_EUMEL_ELAN			"EUMEL/Elan"
#define	EUMEL_ELAN_PARTITION_TYPE				\
CONSTANT(0x46, TP_EUMEL_ELAN) CONSTANT(0x47, TP_EUMEL_ELAN)	\
CONSTANT(0x48, TP_EUMEL_ELAN)

#define	TP_NOVEL			"Novell"
#define	NOVEL_PARTITION_TYPE					\
CONSTANT(0x67, TP_NOVEL) CONSTANT(0x68, TP_NOVEL)

#define	TP_FAULT_TOLERANT_FAT32		"Fault Tolerant FAT32 volume"
#define	FAULT_TOLERANT_FAT32_PARTITION_TYPE			\
CONSTANT(0x8B, TP_FAULT_TOLERANT_FAT32)				\
CONSTANT(0x8C, TP_FAULT_TOLERANT_FAT32)

#define	TP_FREE_FDISK_HDN_DOS_EXT	"Free FDISK hidden DOS EXT"
#define	FREE_FDISK_HDN_DOS_EXT_PARTITION_TYPE			\
CONSTANT(0x91, "Free FDISK hidden DOS EXT")			\
CONSTANT(0x9B, "Free FDISK hidden DOS EXT")

#define	TP_HP_SPEEDSTOR			"HP SpeedStor"
#define	HP_SPEEDSTOR_PARTITION_TYPE				\
CONSTANT(0xA3, TP_HP_SPEEDSTOR) CONSTANT(0xA4, TP_HP_SPEEDSTOR)	\
CONSTANT(0xB1, TP_HP_SPEEDSTOR) CONSTANT(0xB3, TP_HP_SPEEDSTOR)	\
CONSTANT(0xB4, TP_HP_SPEEDSTOR)

#define	TP_DRDOS8			"DRDOS8.0+"
#define	DRDOS8_PARTITION_TYPE					\
CONSTANT(0xC8, TP_DRDOS8) CONSTANT(0xC9, TP_DRDOS8)		\
CONSTANT(0xCA, TP_DRDOS8)

#define	TP_SPEEDSTOR			"SpeedStor"
#define	SPEEDSTOR_PARTITION_TYPE				\
CONSTANT(0x61, TP_SPEEDSTOR) CONSTANT(0xE3, TP_SPEEDSTOR)	\
CONSTANT(0xF1, TP_SPEEDSTOR) CONSTANT(0xF6, TP_SPEEDSTOR)

#define	TP_RESERVED			"reserved"
#define	RESERVED_PARTITION_TYPE				\
CONSTANT(0x23, TP_RESERVED) CONSTANT(0x26, TP_RESERVED)	\
CONSTANT(0x31, TP_RESERVED) CONSTANT(0x33, TP_RESERVED)	\
CONSTANT(0x34, TP_RESERVED) CONSTANT(0x36, TP_RESERVED)	\
CONSTANT(0x71, TP_RESERVED) CONSTANT(0x73, TP_RESERVED)	\
CONSTANT(0x76, TP_RESERVED)

#define	TP_UNUSED			"unused"
#define	UNUSED_PARTITION_TYPE \
CONSTANT(0x0D, TP_UNUSED) CONSTANT(0x1D, TP_UNUSED) CONSTANT(0x7E, TP_UNUSED) \
CONSTANT(0x7F, TP_UNUSED) CONSTANT(0xED, TP_UNUSED) CONSTANT(0xF7, TP_UNUSED)


#define	TP_UNKNOWN			"unknown"
#define	UNKNOWN_PARTITION_TYPE \
CONSTANT(0x13, TP_UNKNOWN) CONSTANT(0x15, TP_UNKNOWN)	\
CONSTANT(0x1A, TP_UNKNOWN) CONSTANT(0x1F, TP_UNKNOWN)	\
CONSTANT(0x25, TP_UNKNOWN) CONSTANT(0x27, TP_UNKNOWN)	\
CONSTANT(0x28, TP_UNKNOWN) CONSTANT(0x29, TP_UNKNOWN)	\
CONSTANT(0x2C, TP_UNKNOWN) CONSTANT(0x2D, TP_UNKNOWN)	\
CONSTANT(0x2E, TP_UNKNOWN) CONSTANT(0x2F, TP_UNKNOWN)	\
CONSTANT(0x30, TP_UNKNOWN) CONSTANT(0x37, TP_UNKNOWN)	\
CONSTANT(0x3E, TP_UNKNOWN) CONSTANT(0x3F, TP_UNKNOWN)	\
CONSTANT(0x49, TP_UNKNOWN) CONSTANT(0x4B, TP_UNKNOWN)	\
CONSTANT(0x58, TP_UNKNOWN) CONSTANT(0x59, TP_UNKNOWN)	\
CONSTANT(0x5A, TP_UNKNOWN) CONSTANT(0x5B, TP_UNKNOWN)	\
CONSTANT(0x5D, TP_UNKNOWN) CONSTANT(0x5E, TP_UNKNOWN)	\
CONSTANT(0x5F, TP_UNKNOWN) CONSTANT(0x60, TP_UNKNOWN)	\
CONSTANT(0x62, TP_UNKNOWN) CONSTANT(0x6A, TP_UNKNOWN)	\
CONSTANT(0x6B, TP_UNKNOWN) CONSTANT(0x6C, TP_UNKNOWN)	\
CONSTANT(0x6D, TP_UNKNOWN) CONSTANT(0x6E, TP_UNKNOWN)	\
CONSTANT(0x6F, TP_UNKNOWN) CONSTANT(0x72, TP_UNKNOWN)	\
CONSTANT(0x79, TP_UNKNOWN) CONSTANT(0x7A, TP_UNKNOWN)	\
CONSTANT(0x7B, TP_UNKNOWN) CONSTANT(0x7C, TP_UNKNOWN)	\
CONSTANT(0x7D, TP_UNKNOWN) CONSTANT(0x89, TP_UNKNOWN)	\
CONSTANT(0x8F, TP_UNKNOWN) CONSTANT(0x96, TP_UNKNOWN)	\
CONSTANT(0x9C, TP_UNKNOWN) CONSTANT(0x9D, TP_UNKNOWN)	\
CONSTANT(0x9E, TP_UNKNOWN) CONSTANT(0xA2, TP_UNKNOWN)	\
CONSTANT(0xAC, TP_UNKNOWN) CONSTANT(0xAD, TP_UNKNOWN)	\
CONSTANT(0xB2, TP_UNKNOWN) CONSTANT(0xB5, TP_UNKNOWN)	\
CONSTANT(0xB9, TP_UNKNOWN) CONSTANT(0xBA, TP_UNKNOWN)	\
CONSTANT(0xBC, TP_UNKNOWN) CONSTANT(0xBD, TP_UNKNOWN)	\
CONSTANT(0xD2, TP_UNKNOWN) CONSTANT(0xD3, TP_UNKNOWN)	\
CONSTANT(0xD7, TP_UNKNOWN) CONSTANT(0xD9, TP_UNKNOWN)	\
CONSTANT(0xDC, TP_UNKNOWN) CONSTANT(0xE2, TP_UNKNOWN)	\
CONSTANT(0xE7, TP_UNKNOWN) CONSTANT(0xE8, TP_UNKNOWN)	\
CONSTANT(0xE9, TP_UNKNOWN) CONSTANT(0xEA, TP_UNKNOWN)	\
CONSTANT(0xF8, TP_UNKNOWN)


/*
 * There are way to many string constants for partition types.
 * ptype_to_str() does that lookup.
 */
typedef struct {
	PyObject *type; /* a dictionary from CONSTANTs above */
	PyObject *unknown;
} part_const;

extern part_const PartConst;


#endif /* _PARTITION_H */
