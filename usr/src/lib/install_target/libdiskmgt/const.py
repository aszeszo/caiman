#!/usr/bin/python
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
constants and enums from libdiskmgt.h

libdiskmgt.h is not installed by default, the pkg is:
    system/library/libdiskmgt/header-libdiskmgt
"""

DESC_TYPE = ( \
    DRIVE,
    CONTROLLER,
    MEDIA,
    SLICE,
    PARTITION,
    PATH,
    ALIAS,
    BUS,
) = xrange(8)

DESC_TYPE_MAP = {
    DRIVE:      "DRIVE",      "DRIVE":      DRIVE,
    CONTROLLER: "CONTROLLER", "CONTROLLER": CONTROLLER,
    MEDIA:      "MEDIA",      "MEDIA":      MEDIA,
    SLICE:      "SLICE",      "SLICE":      SLICE,
    PARTITION:  "PARTITION",  "PARTITION":  PARTITION,
    PATH:       "PATH",       "PATH":       PATH,
    ALIAS:      "ALIAS",      "ALIAS":      ALIAS,
    BUS:        "BUS",        "BUS":        BUS,
}

DRIVE_TYPE = ( \
    DT_UNKNOWN,
    DT_FIXED,
    DT_ZIP,
    DT_JAZ,
    DT_FLOPPY,
    DT_MO_ERASABLE,
    DT_MO_WRITEONCE,
    DT_AS_MO,
    DT_CDROM,
    DT_CDR,
    DT_CDRW,
    DT_DVDROM,
    DT_DVDR,
    DT_DVDRAM,
    DT_DVDRW,
    DT_DDCDROM,
    DT_DDCDR,
    DT_DDCDRW,
) = xrange(18)

DRIVE_TYPE_MAP = {
    DT_UNKNOWN:      "UNKNOWN",      "UNKNOWN":      DT_UNKNOWN,
    DT_FIXED:        "FIXED",        "FIXED":        DT_FIXED,
    DT_ZIP:          "ZIP",          "ZIP":          DT_ZIP,
    DT_JAZ:          "JAZ",          "JAZ":          DT_JAZ,
    DT_FLOPPY:       "FLOPPY",       "FLOPPY":       DT_FLOPPY,
    DT_MO_ERASABLE:  "MO_ERASABLE",  "MO_ERASABLE":  DT_MO_ERASABLE,
    DT_MO_WRITEONCE: "MO_WRITEONCE", "MO_WRITEONCE": DT_MO_WRITEONCE,
    DT_AS_MO:        "AS_MO",        "AS_MO":        DT_AS_MO,
    DT_CDROM:        "CDROM",        "CDROM":        DT_CDROM,
    DT_CDR:          "CDR",          "CDR":          DT_CDR,
    DT_CDRW:         "CDRW",         "CDRW":         DT_CDRW,
    DT_DVDROM:       "DVDROM",       "DVDROM":       DT_DVDROM,
    DT_DVDR:         "DVDR",         "DVDR":         DT_DVDR,
    DT_DVDRAM:       "DVDRAM",       "DVDRAM":       DT_DVDRAM,
    DT_DVDRW:        "DVDRW",        "DVDRW":        DT_DVDRW,
    DT_DDCDROM:      "DDCDROM",      "DDCDROM":      DT_DDCDROM,
    DT_DDCDR:        "DDCDR",        "DDCDR":        DT_DDCDR,
    DT_DDCDRW:       "DDCDRW",       "DDCDRW":       DT_DDCDRW,
}

MEDIA_TYPE = ( \
    MT_UNKNOWN,
    MT_FIXED,
    MT_FLOPPY,
    MT_CDROM,
    MT_ZIP,
    MT_JAZ,
    MT_CDR,
    MT_CDRW,
    MT_DVDROM,
    MT_DVDR,
    MT_DVDRAM,
    MT_MO_ERASABLE,
    MT_MO_WRITEONCE,
    MT_AS_MO,
) = xrange(14)

MEDIA_TYPE_MAP = {
    MT_UNKNOWN:      "MT_UNKNOWN",      "MT_UNKNOWN":      MT_UNKNOWN,
    MT_FIXED:        "MT_FIXED",        "MT_FIXED":        MT_FIXED,
    MT_FLOPPY:       "MT_FLOPPY",       "MT_FLOPPY":       MT_FLOPPY,
    MT_CDROM:        "MT_CDROM",        "MT_CDROM":        MT_CDROM,
    MT_ZIP:          "MT_ZIP",          "MT_ZIP":          MT_ZIP,
    MT_JAZ:          "MT_JAZ",          "MT_JAZ":          MT_JAZ,
    MT_CDR:          "MT_CDR",          "MT_CDR":          MT_CDR,
    MT_CDRW:         "MT_CDRW",         "MT_CDRW":         MT_CDRW,
    MT_DVDROM:       "MT_DVDROM",       "MT_DVDROM":       MT_DVDROM,
    MT_DVDR:         "MT_DVDR",         "MT_DVDR":         MT_DVDR,
    MT_DVDRAM:       "MT_DVDRAM",       "MT_DVDRAM":       MT_DVDRAM,
    MT_MO_ERASABLE:  "MT_MO_ERASABLE",  "MT_MO_ERASABLE":  MT_MO_ERASABLE,
    MT_MO_WRITEONCE: "MT_MO_WRITEONCE", "MT_MO_WRITEONCE": MT_MO_WRITEONCE,
    MT_AS_MO:        "MT_AS_MO",        "MT_AS_MO":        MT_AS_MO,
}

FILTER_END = -1

DRIVE_STAT = ( \
    DSTAT_PERFORMANCE,
    DSTAT_DIAGNOSTIC,
    DSTAT_TEMPERATURE,
) = xrange(3)

DRIVE_STAT_MAP = {
    DSTAT_PERFORMANCE: "DSTAT_PERFORMANCE",
    "DSTAT_PERFORMANCE": DSTAT_PERFORMANCE,
    DSTAT_DIAGNOSTIC:  "DSTAT_DIAGNOSTIC",
    "DSTAT_DIAGNOSTIC":  DSTAT_DIAGNOSTIC,
    DSTAT_TEMPERATURE: "DSTAT_TEMPERATURE",
    "DSTAT_TEMPERATURE": DSTAT_TEMPERATURE,
}

SLICE_STAT = ( \
    SSTAT_USE,
) = xrange(1)

SLICE_STAT_MAP = {
    SSTAT_USE: "SSTAT_USE", "SSTAT_USE": SSTAT_USE,
}

PARTITION_TYPE = ( \
    PRIMARY,
    EXTENDED,
    LOGICAL,
) = xrange(3)

PARTITION_TYPE_MAP = {
    PRIMARY:  "PRIMARY",  "PRIMARY":  PRIMARY,
    EXTENDED: "EXTENDED", "EXTENDED": EXTENDED,
    LOGICAL:  "LOGICAL",  "LOGICAL":  LOGICAL,
}

PARTITION_WHO_TYPE = ( \
    DM_WHO_MKFS,
    DM_WHO_ZPOOL,
    DM_WHO_ZPOOL_FORCE,
    DM_WHO_FORMAT,
    DM_WHO_SWAP,
    DM_WHO_DUMP,
    DM_WHO_ZPOOL_SPARE
) = xrange(7)

PARTITION_WHO_TYPE_MAP = {
    DM_WHO_MKFS: "DM_WHO_MKFS", "DM_WHO_MKFS": DM_WHO_MKFS,
    DM_WHO_ZPOOL: "DM_WHO_ZPOOL", "DM_WHO_ZPOOL": DM_WHO_ZPOOL,
    DM_WHO_ZPOOL_FORCE: "DM_WHO_ZPOOL_FORCE",
    "DM_WHO_ZPOOL_FORCE": DM_WHO_ZPOOL_FORCE,
    DM_WHO_FORMAT: "DM_WHO_FORMAT", "DM_WHO_FORMAT": DM_WHO_FORMAT,
    DM_WHO_SWAP: "DM_WHO_SWAP", "DM_WHO_SWAP": DM_WHO_SWAP,
    DM_WHO_DUMP: "DM_WHO_DUMP", "DM_WHO_DUMP": DM_WHO_DUMP,
    DM_WHO_ZPOOL_SPARE: "DM_WHO_ZPOOL_SPARE",
    "DM_WHO_ZPOOL_SPARE": DM_WHO_ZPOOL_SPARE
}

PARTITION_ID_MAP = {
    0: "Empty",
    1: "FAT12",
    2: "XENIX /",
    3: "XENIX /usr",
    4: "FAT16 (Upto 32M)",
    5: "DOS Extended",
    6: "FAT16 (>32M, HUGEDOS)",
    7: "IFS: NTFS",
    8: "AIX Boot/QNX(qny)",
    9: "AIX Data/QNX(qnz)",
    10: "OS/2 Boot/Coherent swap",
    11: "WIN95 FAT32(Upto 2047GB)",
    12: "WIN95 FAT32(LBA)",
    13: "Unused",
    14: "WIN95 FAT16(LBA)",
    15: "WIN95 Extended(LBA)",
    16: "OPUS",
    17: "Hidden FAT12",
    18: "Diagnostic",
    19: "Unknown",
    20: "Hidden FAT16(Upto 32M)",
    21: "Unknown",
    22: "Hidden FAT16(>=32M)",
    23: "Hidden IFS: HPFS",
    24: "AST SmartSleep Partition",
    25: "Unused/Willowtech Photon",
    26: "Unknown",
    27: "Hidden FAT32",
    28: "Hidden FAT32(LBA)",
    29: "Unused",
    30: "Hidden FAT16(LBA)",
    31: "Unknown",
    32: "Unused/OSF1",
    33: "Reserved/FSo2(Oxygen FS)",
    34: "Unused/(Oxygen EXT)",
    35: "Reserved",
    36: "NEC DOS 3.x",
    37: "Unknown",
    38: "Reserved",
    39: "Unknown",
    40: "Unknown",
    41: "Unknown",
    42: "AtheOS File System",
    43: "SyllableSecure",
    44: "Unknown",
    45: "Unknown",
    46: "Unknown",
    47: "Unknown",
    48: "Unknown",
    49: "Reserved",
    50: "NOS",
    51: "Reserved",
    52: "Reserved",
    53: "JFS on OS/2",
    54: "Reserved",
    55: "Unknown",
    56: "THEOS 3.2 2GB",
    57: "Plan9/THEOS 4",
    58: "THEOS 4 4GB",
    59: "THEOS 4 Extended",
    60: "PartitionMagic Recovery",
    61: "Hidden NetWare",
    62: "Unknown",
    63: "Unknown",
    64: "Venix 80286",
    65: "MINIX/PPC PReP Boot",
    66: "Win2K Dynamic Disk/SFS(DOS)",
    67: "Linux+DRDOS shared",
    68: "GoBack partition",
    69: "Boot-US boot manager",
    70: "EUMEL/Elan",
    71: "EUMEL/Elan",
    72: "EUMEL/Elan",
    73: "Unknown",
    74: "ALFS/THIN FS for DOS",
    75: "Unknown",
    76: "Oberon partition",
    77: "QNX 4,x",
    78: "QNX 4,x 2nd Part",
    79: "QNX 4,x 3rd Part",
    80: "OnTrack DM R/O, Lynx RTOS",
    81: "OnTrack DM R/W, Novell",
    82: "CP/M",
    83: "Disk Manager 6.0 Aux3",
    84: "Disk Manager 6.0 DDO",
    85: "EZ-Drive",
    86: "Golden Bow VFeature/AT&T MS-DOS",
    87: "DrivePro",
    88: "Unknown",
    89: "Unknown",
    90: "Unknown",
    91: "Unknown",
    92: "Priam EDisk",
    93: "Unknown",
    94: "Unknown",
    95: "Unknown",
    96: "Unknown",
    97: "SpeedStor",
    98: "Unknown",
    99: "Unix SysV, Mach, GNU Hurd",
    100: "PC-ARMOUR, Netware 286",
    101: "Netware 386",
    102: "Netware SMS",
    103: "Novell",
    104: "Novell",
    105: "Netware NSS",
    106: "Unknown",
    107: "Unknown",
    108: "Unknown",
    109: "Unknown",
    110: "Unknown",
    111: "Unknown",
    112: "DiskSecure Multi-Boot",
    113: "Reserved",
    114: "Unknown",
    115: "Reserved",
    116: "Scramdisk partition",
    117: "IBM PC/IX",
    118: "Reserved",
    119: "M2FS/M2CS,Netware VNDI",
    120: "XOSL FS",
    121: "Unknown",
    122: "Unknown",
    123: "Unknown",
    124: "Unknown",
    125: "Unknown",
    126: "Unused",
    127: "Unused",
    128: "MINIX until 1.4a",
    129: "MINIX since 1.4b, early Linux",
    130: "Solaris/Linux swap",
    131: "Linux native",
    132: "OS/2 hidden,Win Hibernation",
    133: "Linux extended",
    134: "Old Linux RAID,NT FAT16 RAID",
    135: "NTFS volume set",
    136: "Linux plaintext part table",
    137: "Unknown",
    138: "Linux Kernel Partition",
    139: "Fault Tolerant FAT32 volume",
    140: "Fault Tolerant FAT32 volume",
    141: "Free FDISK hidden PDOS FAT12",
    142: "Linux LVM partition",
    143: "Unknown",
    144: "Free FDISK hidden PDOS FAT16",
    145: "Free FDISK hidden DOS EXT",
    146: "Free FDISK hidden FAT16 Large",
    147: "Hidden Linux native, Amoeba",
    148: "Amoeba Bad Block Table",
    149: "MIT EXOPC Native",
    150: "Unknown",
    151: "Free FDISK hidden PDOS FAT32",
    152: "Free FDISK hidden FAT32 LBA",
    153: "DCE376 logical drive",
    154: "Free FDISK hidden FAT16 LBA",
    155: "Free FDISK hidden DOS EXT",
    156: "Unknown",
    157: "Unknown",
    158: "Unknown",
    159: "BSD/OS",
    160: "Laptop hibernation",
    161: "Laptop hibernate,HP SpeedStor",
    162: "Unknown",
    163: "HP SpeedStor",
    164: "HP SpeedStor",
    165: "BSD/386,386BSD,NetBSD,FreeBSD",
    166: "OpenBSD,HP SpeedStor",
    167: "NeXTStep",
    168: "Mac OS-X",
    169: "NetBSD",
    170: "Olivetti FAT12 1.44MB Service",
    171: "Mac OS-X Boot",
    172: "Unknown",
    173: "Unknown",
    174: "ShagOS filesystem",
    175: "ShagOS swap",
    176: "BootStar Dummy",
    177: "HP SpeedStor",
    178: "Unknown",
    179: "HP SpeedStor",
    180: "HP SpeedStor",
    181: "Unknown",
    182: "Corrupted FAT16 NT Mirror Set",
    183: "Corrupted NTFS NT Mirror Set",
    184: "Old BSDI BSD/386 swap",
    185: "Unknown",
    186: "Unknown",
    187: "Boot Wizard hidden",
    188: "Unknown",
    189: "Unknown",
    190: "Solaris x86 boot",
    191: "Solaris2",
    192: "REAL/32 or Novell DOS secured",
    193: "DRDOS/secured(FAT12)",
    194: "Hidden Linux",
    195: "Hidden Linux swap",
    196: "DRDOS/secured(FAT16,< 32M)",
    197: "DRDOS/secured(Extended)",
    198: "NT corrupted FAT16 volume",
    199: "NT corrupted NTFS volume",
    200: "DRDOS8.0+",
    201: "DRDOS8.0+",
    202: "DRDOS8.0+",
    203: "DRDOS7.04+ secured FAT32(CHS)",
    204: "DRDOS7.04+ secured FAT32(LBA)",
    205: "CTOS Memdump",
    206: "DRDOS7.04+ FAT16X(LBA)",
    207: "DRDOS7.04+ secure EXT DOS(LBA)",
    208: "REAL/32 secure big, MDOS",
    209: "Old MDOS secure FAT12",
    210: "Unknown",
    211: "Unknown",
    212: "Old MDOS secure FAT16 <32M",
    213: "Old MDOS secure EXT",
    214: "Old MDOS secure FAT16 >=32M",
    215: "Unknown",
    216: "CP/M-86",
    217: "Unknown",
    218: "Non-FS Data",
    219: "CP/M,Concurrent DOS,CTOS",
    220: "Unknown",
    221: "Hidden CTOS memdump",
    222: "Dell PowerEdge utilities(FAT)",
    223: "DG/UX virtual disk manager",
    224: "ST AVFS(STMicroelectronics)",
    225: "SpeedStor 12-bit FAT EXT",
    226: "Unknown",
    227: "SpeedStor",
    228: "SpeedStor 16-bit FAT EXT",
    229: "Tandy MSDOS",
    230: "Storage Dimensions SpeedStor",
    231: "Unknown",
    232: "Unknown",
    233: "Unknown",
    234: "Unknown",
    235: "BeOS BFS",
    236: "SkyOS SkyFS",
    237: "Unused",
    238: "EFI Header Indicator",
    239: "EFI System",
    240: "Linux/PA-RISC boot loader",
    241: "SpeedStor",
    242: "DOS 3.3+ secondary",
    243: "SpeedStor Reserved",
    244: "SpeedStor Large",
    245: "Prologue multi-volume",
    246: "SpeedStor",
    247: "Unused",
    248: "Unknown",
    249: "pCache",
    250: "Bochs",
    251: "VMware File System",
    252: "VMware swap",
    253: "Linux raid autodetect",
    254: "NT Disk Administrator hidden",
    255: "Xenix Bad Block Table"
}

# drive
CLUSTERED     = "clustered"
DRVTYPE       = "drvtype"
FAILING       = "failing"
LOADED        = "loaded"        # also in media
NDNRERRS      = "ndevice_not_ready_errors"
NBYTESREAD    = "nbytes_read"
NBYTESWRITTEN = "nbytes_written"
NHARDERRS     = "nhard_errors"
NILLREQERRS   = "nillegal_req_errors"
NMEDIAERRS    = "nmedia_errors"
NNODEVERRS    = "nno_dev_errors"
NREADOPS      = "nread_ops"
NRECOVERRS    = "nrecoverable_errors"
NSOFTERRS     = "nsoft_errors"
NTRANSERRS    = "ntransport_errors"
NWRITEOPS     = "nwrite_ops"
OPATH         = "opath"
PRODUCT_ID    = "product_id"
REMOVABLE     = "removable"     # also in media
RPM           = "rpm"
STATUS        = "status"
SYNC_SPEED    = "sync_speed"
TEMPERATURE   = "temperature"
VENDOR_ID     = "vendor_id"
WIDE          = "wide"
WWN           = "wwn"

# bus
BTYPE         = "btype"
CLOCK         = "clock"         # also on controller
PNAME         = "pname"

# controller
FAST          = "fast"
FAST20        = "fast20"
FAST40        = "fast40"
FAST80        = "fast80"
MULTIPLEX     = "multiplex"
PATH_STATE    = "path_state"

CTYPE_ATA     = "ata"
CTYPE_SCSI    = "scsi"
CTYPE_FIBRE   = "fibre channel"
CTYPE_USB     = "usb"
CTYPE_UNKNOWN = "unknown"

# media
BLOCKSIZE        = "blocksize"
FDISK            = "fdisk"
MTYPE            = "mtype"
NACTUALCYLINDERS = "nactual_cylinders"
NALTCYLINDERS    = "nalt_cylinders"
NCYLINDERS       = "ncylinders"
NHEADS           = "nheads"
NPHYSCYLINDERS   = "nphys_cylinders"
NSECTORS         = "nsectors"      # also in partition
SIZE             = "size"          # also in slice
NACCESSIBLE      = "naccessible"
LABEL            = "label"

# partition
BCYL             = "bcyl"
BHEAD            = "bhead"
BOOTID           = "bootid"
BSECT            = "bsect"
ECYL             = "ecyl"
EHEAD            = "ehead"
ESECT            = "esect"
PTYPE            = "ptype"  # this references the partition id
PARTITION_TYPE   = "part_type"  # primary, extended, logical
RELSECT          = "relsect"

# slice
DEVICEID           = "deviceid"
DEVT               = "devt"
INDEX              = "index"
EFI_NAME           = "name"
MOUNTPOINT         = "mountpoint"
LOCALNAME          = "localname"
START              = "start"
TAG                = "tag"
FLAG               = "flag"
EFI                = "efi"   # also on media
USED_BY            = "used_by"
USED_NAME          = "used_name"
USE_MOUNT          = "mount"
USE_SVM            = "svm"
USE_LU             = "lu"
USE_DUMP           = "dump"
USE_VXVM           = "vxvm"
USE_FS             = "fs"
USE_VFSTAB         = "vfstab"
USE_EXPORTED_ZPOOL = "exported_zpool"
USE_ACTIVE_ZPOOL   = "active_zpool"
USE_SPARE_ZPOOL    = "spare_zpool"
USE_L2CACHE_ZPOOL  = "l2cache_zpool"

# event
EV_NAME    = "name"
EV_DTYPE   = "edtype"
EV_TYPE    = "evtype"
EV_TADD    = "add"
EV_TREMOVE = "remove"
EV_TCHANGE = "change"

# findisks
CTYPE  = "ctype"
LUN    = "lun"
TARGET = "target"

DRIVE_UP   = 1
DRIVE_DOWN = 0

# USB floppy drive di_prop string
DI_FLOPPY = "usbif,class8.4"
