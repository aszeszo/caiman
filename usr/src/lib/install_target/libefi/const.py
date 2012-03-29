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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#
""" C symbolic constants from libefi.so and libefi.h
"""

import ctypes as C
from solaris_install.target.cuuid import cUUID

# The maximum number of partitions, including the required
# Solaris reserved partition at index 8 (zero based index)
EFI_NUMPAR = 9

# Solaris implementation restrictions:
# 1. There are 7 user accessible/mountable (s0-s6) partition nodes
# 2. Device node s7 is the "overlap" or whole disk partition. This is the
#    equivalent of the s2 overlap slice in SMI VTOC labeled disks.
# 3. A reserved partition (EFI_RESERVED) must be defined on Solaris and
#    it must be at least 16384 disk blocks in size. It does not need to
#    occupy one of the user partition nodes though, so by default it would
#    occupy the s8 node
# 4. The EFI system partition needs to be mountable by the Solaris kernel so
#    it must occupy one of the 7 available user partition nodes (s0-s6).
EFI_NUMUSERPAR = 7
EFI_PREFERRED_RSVPAR = 8

EFI_SIGNATURE = "0x5452415020494645ULL"

EFI_LABEL_SIZE = 512
EFI_MIN_ARRAY_SIZE = 16 * 1024
EFI_PART_NAME_LEN = 36
EFI_MIN_RESV_SIZE = 16 * 1024

# Default size in bytes used for the EFI system partition.
# Note: Own definition. Not defined by efi_partition.h
EFI_DEFAULT_SYSTEM_SIZE = 256 * 1024 * 1024

EFI_VERSION102 = 0x00010002
EFI_VERSION100 = 0x00010000
EFI_VERSION_CURRENT = EFI_VERSION100

# primary label corrupt
EFI_GPT_PRIMARY_CORRUPT = "0x1"


# Partition types defined by EFI spec
EFI_UNUSED = cUUID('{00000000-0000-0000-0000-000000000000}')
EFI_SYSTEM = cUUID('{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}')
EFI_LEGACY_MBR = cUUID('{024dee41-33e7-11d3-9d69-0008c781f39f}')
EFI_BIOS_BOOT = cUUID('{21686148-6449-6E6F-744E-656564454649}')

# Microsoft Windows Paritions
EFI_MSFT_RESV = cUUID('{e3c9e316-0b5c-4db8-817d-f92df00215ae}')
EFI_MSFT_BASIC_DATA = cUUID('{ebd0a0a2-b9e5-4433-87c0-68b6b72699c7}')
EFI_MSFT_LDM_METADATA = cUUID('{5808c8aa-7e8f-42e0-85d2-e1e90434cfb3}')
EFI_MSFT_LDM_DATA = cUUID('{af9b60a0-1431-4f62-bc68-3311714a69ad}')
EFI_MSFT_RECOVERY_ENV = cUUID('{de94bba4-06d1-4d40-a16a-bfd50179d6ac}')
EFI_MSFT_IBM_GPFS = cUUID('{37affc90-ef7d-4e96-91c3-2d7ae055b174}')

# Linux Partitions
EFI_LINUX_FS_DATA = cUUID('{0fc63daf-8483-4772-8e79-3d69d8477de4}')
EFI_LINUX_RAID = cUUID('{a19d880f-05fc-4d3b-a006-743f0f84911e}')
EFI_LINUX_SWAP = cUUID('{0657fd6d-a4ab-43c4-84e5-0933c84b4f4f}')
EFI_LINUX_LVM = cUUID('{e6d6d379-f507-44c2-a23c-238f2a3df928}')
EFI_LINUX_RESV = cUUID('{8da63339-0007-60c0-c436-083ac8230908}')

# Dell (these are all just synonyms)
EFI_DELL_BASIC = EFI_MSFT_BASIC_DATA
EFI_DELL_RAID = EFI_LINUX_RAID
EFI_DELL_SWAP = EFI_LINUX_SWAP
EFI_DELL_LVM = EFI_LINUX_LVM
EFI_DELL_RESV = EFI_LINUX_RESV

# FreeBSD Partitions
EFI_FBSD_BOOT = cUUID('{83bd6b9d-7f41-11dc-be0b-001560b84f0f}')
EFI_FBSD_DATA = cUUID('{516e7cb4-6ecf-11d6-8ff8-00022d09712b}')
EFI_FBSD_SWAP = cUUID('{516e7cb5-6ecf-11d6-8ff8-00022d09712b}')
EFI_FBSD_UFS = cUUID('{516e7cb6-6ecf-11d6-8ff8-00022d09712b}')
EFI_FBSD_VINUM = cUUID('{516e7cb8-6ecf-11d6-8ff8-00022d09712b}')
EFI_FBSD_ZFS = cUUID('{516e7cba-6ecf-11d6-8ff8-00022d09712b}')

# Solaris
EFI_BOOT = cUUID('{6a82cb45-1dd2-11b2-99a6-080020736631}')
EFI_ROOT = cUUID('{6a85cf4d-1dd2-11b2-99a6-080020736631}')
EFI_SWAP = cUUID('{6a87c46f-1dd2-11b2-99a6-080020736631}')
EFI_BACKUP = cUUID('{6a8b642b-1dd2-11b2-99a6-080020736631}')
# EFI_USR is the standard Solaris partition we use for installation
EFI_USR = cUUID('{6a898cc3-1dd2-11b2-99a6-080020736631}')
EFI_VAR = cUUID('{6a8ef2e9-1dd2-11b2-99a6-080020736631}')
EFI_HOME = cUUID('{6a90ba39-1dd2-11b2-99a6-080020736631}')
EFI_ALTSCTR = cUUID('{6a9283a5-1dd2-11b2-99a6-080020736631}')
EFI_RESERVED = cUUID('{6a945a3b-1dd2-11b2-99a6-080020736631}')
EFI_SYMC_PUB = cUUID('{6a9630d1-1dd2-11b2-99a6-080020736631}')
EFI_SYMC_CDS = cUUID('{6a980767-1dd2-11b2-99a6-080020736631}')
EFI_RESV1 = cUUID('{6a96237f-1dd2-11b2-99a6-080020736631}')
EFI_RESV2 = cUUID('{6a8d2ac7-1dd2-11b2-99a6-080020736631}')

# Apple Partitions
EFI_AAPL_HFS = cUUID('{48465300-0000-11aa-aa11-00306543ecac}')
EFI_AAPL_UFS = cUUID('{55465300-0000-11aa-aa11-00306543ecac}')
EFI_AAPL_ZFS = EFI_USR  # Mac uses this as the generic ZFS GUID
EFI_AAPL_RAID = cUUID('{52414944-0000-11aa-aa11-00306543ecac}')
EFI_AAPL_RAID_OFFLINE = cUUID('{52414944-5f4f-11aa-aa11-00306543ecac}')
EFI_AAPL_BOOT = cUUID('{426f6f74-0000-11aa-aa11-00306543ecac}')
EFI_AAPL_LABEL = cUUID('{4c616265-6c00-11aa-aa11-00306543ecac}')
EFI_AAPL_TV_RECOVERY = cUUID('{5265636f-7665-11aa-aa11-00306543ecaC}')
EFI_AAPL_CORE_STORAGE = cUUID('{53746f72-6167-11aa-aa11-00306543ecac}')

# Shortened aliases that we support in the manifest (see target.dtd):
# - "solaris": Solaris partition (EFI_USR)
# - "esp": EFI System Partition (EFI_SYSTEM)
# - "bbp": Bios Boot Partition (EFI_BIOS_BOOT)
PARTITION_GUID_ALIASES = {
    "solaris":  EFI_USR,
    "esp":      EFI_SYSTEM,
    "bbp":      EFI_BIOS_BOOT,
    "reserved": EFI_RESERVED
}

# GPT Partition GUID map (from rdwr_efi.c): {GUID: (Name, P_TAG)}
PARTITION_GUID_PTAG_MAP = {
    EFI_UNUSED:             ("Unused", 0),
    EFI_BOOT:               ("Solaris Boot Partition", 1),
    EFI_ROOT:               ("Solaris Root Partition", 2),
    EFI_SWAP:               ("Solaris Swap Partition", 3),
    EFI_USR:                ("Solaris", 4),
    EFI_BACKUP:             ("Solaris Backup Partition", 5),
    # "STAND" is never used but occupies p_tag 6
    EFI_VAR:                ("Solaris /var Partition", 7),
    EFI_HOME:               ("Solaris /home Partition", 8),
    EFI_ALTSCTR:            ("Solaris Alternate Sector", 9),
    # "cachefs" is never used but occupies p_tag 10
    EFI_RESERVED:           ("Solaris Reserved Partition", 11),
    EFI_SYSTEM:             ("EFI System Partition", 12),
    EFI_LEGACY_MBR:         ("MBR Partition Scheme", 13),
    EFI_SYMC_PUB:           ("Solaris Reserved Partition", 14),
    EFI_SYMC_CDS:           ("Solaris Reserved Partition", 15),
    EFI_MSFT_RESV:          ("Microsoft Reserved", 16),
    EFI_DELL_BASIC:         ("Windows Basic Data", 17),
    EFI_DELL_RAID:          ("Linux RAID Partition", 18),
    EFI_DELL_SWAP:          ("Linux Swap Partition", 19),
    EFI_LINUX_LVM:          ("Linux Logical Volume Manager", 20),
    EFI_LINUX_RESV:         ("Linux Reserved", 21),
    EFI_AAPL_HFS:           ("Apple HFS+ Partition", 22),
    EFI_AAPL_UFS:           ("Apple UFS Partition", 23),
    EFI_BIOS_BOOT:          ("BIOS Boot Partition", 24),

    # The following are NOT assigned a p_tag value by libefi
    EFI_MSFT_LDM_METADATA:  ("Windows Logical Disk Manager Metadata", None),
    EFI_MSFT_LDM_DATA:      ("Windows Logical Disk Manager", None),
    EFI_MSFT_RECOVERY_ENV:  ("Windows Recovery Environment", None),
    EFI_MSFT_IBM_GPFS:      ("IBM General Parallel File System", None),
    EFI_LINUX_FS_DATA:      ("Linux File System Data", None),
    EFI_FBSD_BOOT:          ("FreeBSD Boot Partition", None),
    EFI_FBSD_DATA:          ("FreeBSD Data", None),
    EFI_FBSD_SWAP:          ("FreeBSD Swap Partition", None),
    EFI_FBSD_UFS:           ("FreeBSD UFS Partition", None),
    EFI_FBSD_VINUM:         ("Vinum Volume Manager Partition", None),
    EFI_FBSD_ZFS:           ("FreeBSD ZFS Partition", None),
    EFI_RESV1:              ("Solaris Reserved Partition", None),
    EFI_RESV2:              ("Solaris Reserved Partition", None),
    EFI_AAPL_RAID:          ("Apple RAID Partition", None),
    EFI_AAPL_RAID_OFFLINE:  ("Apple RAID Partition, offline", None),
    EFI_AAPL_BOOT:          ("Apple Boot Partition", None),
    EFI_AAPL_LABEL:         ("Apple Label", None),
    EFI_AAPL_TV_RECOVERY:   ("Apple TV Recovery Partition", None),
    EFI_AAPL_CORE_STORAGE:  ("Apple Core Storage Partition", None)
}
