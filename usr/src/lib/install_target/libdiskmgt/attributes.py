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
Python packge with ctypes wrapper for libdiskmgt.so descriptor attributes.

All DMDescriptors have an attributes property.

The attributes is an NVList. These classes simply know the correct keys
for each type of NVList attribute.

NOTE: when subclassing libnvpair.nvl.NVList it is imperative to
      set the _type_ of the class for ctypes.
"""

import ctypes as C
import numbers

from solaris_install.target.libdiskmgt import cfunc, const, cstruct
from solaris_install.target.libnvpair.nvl import NVList, NVKey
from solaris_install.target.libnvpair.cfunc import nvlist_free
from solaris_install.target.libnvpair.const import DATA_TYPE_BOOLEAN, \
    DATA_TYPE_UINT32, DATA_TYPE_UINT64, DATA_TYPE_STRING


class DMDriveAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    REMOVABLE  = NVKey(const.REMOVABLE, DATA_TYPE_BOOLEAN)
    LOADED     = NVKey(const.LOADED, DATA_TYPE_BOOLEAN)
    STATUS     = NVKey(const.STATUS, DATA_TYPE_UINT32) # 1 UP, 0 DOWN
    DRVTYPE    = NVKey(const.DRVTYPE, DATA_TYPE_UINT32)
    PRODUCT_ID = NVKey(const.PRODUCT_ID, DATA_TYPE_STRING)
    VENDOR_ID  = NVKey(const.VENDOR_ID, DATA_TYPE_STRING)
    SYNC_SPEED = NVKey(const.SYNC_SPEED, DATA_TYPE_UINT32)
    WIDE       = NVKey(const.WIDE, DATA_TYPE_BOOLEAN)
    RPM        = NVKey(const.RPM, DATA_TYPE_UINT32) # not always present
    CLUSTERED  = NVKey(const.CLUSTERED, DATA_TYPE_BOOLEAN)
    OPATH      = NVKey(const.OPATH, DATA_TYPE_STRING)

    @property
    def removable(self):
        """bool indicating if the disk media is removable"""
        return self[DMDriveAttr.REMOVABLE]

    @property
    def loaded(self):
        """bool indicating if the disk media is loaded"""
        # Note it should always be True if non-removable
        if self.removable:
            return self[DMDriveAttr.LOADED]
        else:
            return True

    @property
    def status(self):
        """dive status, "UP", "DOWN", or None"""
        return self[DMDriveAttr.STATUS] == const.DRIVE_UP and "UP" or "DOWN"

    @property
    def type(self):
        """drive type, a str (see cont.DRIVE_TYPE_MAP)"""
        return const.DRIVE_TYPE_MAP[self[DMDriveAttr.DRVTYPE]]

    @property
    def product_id(self):
        """string representing product ID or None"""
        return self.get(DMDriveAttr.PRODUCT_ID)

    @property
    def vendor_id(self):
        """string representing vendor ID or None"""
        return self.get(DMDriveAttr.VENDOR_ID)

    @property
    def sync_speed(self):
        """int sync speed or None"""
        return self.get(DMDriveAttr.SYNC_SPEED)

    @property
    def wide(self):
        """bool indicating disk is wide"""
        return self[DMDriveAttr.WIDE]

    @property
    def rpm(self):
        """int rpm or None"""
        return self.get(DMDriveAttr.RPM)

    @property
    def clustered(self):
        """bool indicating drive is clustered"""
        return self[DMDriveAttr.CLUSTERED]

    @property
    def opath(self):
        """str of drive opath or None"""
        return self.get(DMDriveAttr.OPATH)

    def __repr__(self):
        rlist = ["DMDriveAttr <%d>" % (id(self))]
        rlist.append("\tdrive type: %s" % (self.type))
        rlist.append("\tproduct/vendor = %s/%s" % \
                     (self.product_id or "UNKNOWN",
                      self.vendor_id or "UNKNOWN"))
        rlist.append("\tremovable = %s (loaded = %s)" % \
                     (self.removable, self.loaded))
        rlist.append("\tstatus is %s" % (self.status))
        speed = self.sync_speed
        rlist.append("\tsync speed is %s" % (speed and str(speed) or "UNKNOWN"))
        rlist.append("\tdisk is%s wide" % (not self.wide and "n't" or ""))
        rpm = self.rpm
        rlist.append("\tRPM is %s" % (rpm and str(rpm) or "UNKNOWN"))
        rlist.append("\tdisk is%s clustered" % \
                     (not self.clustered and "n't" or ""))
        rlist.append('\topath = "%s"' % (self.opath or "UNKNOWN"))
        return "\n".join(rlist)

class DMControllerAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    CTYPE     = NVKey(const.CTYPE, DATA_TYPE_STRING)
    MULTIPLEX = NVKey(const.MULTIPLEX, DATA_TYPE_BOOLEAN)
    # SCSI keys
    WIDE      = NVKey(const.WIDE, DATA_TYPE_BOOLEAN)
    FAST      = NVKey(const.FAST, DATA_TYPE_BOOLEAN)
    FAST20    = NVKey(const.FAST20, DATA_TYPE_BOOLEAN)
    FAST40    = NVKey(const.FAST40, DATA_TYPE_BOOLEAN)
    FAST80    = NVKey(const.FAST80, DATA_TYPE_BOOLEAN)

    CLOCK     = NVKey(const.CLOCK, DATA_TYPE_UINT32)

    @property
    def type(self):
        """controller type, a str"""
        # already a string like CTYPE_ATA, strange libdiskmgt.h
        # didn't have an enum for these.
        return self[DMControllerAttr.CTYPE]

    @property
    def multiplex(self):
        """True if controller is multiplex"""
        return self[DMControllerAttr.MULTIPLEX]

    @property
    def wide(self):
        """True if controller is SCSI-wide"""
        return self[DMControllerAttr.WIDE]

    @property
    def fast(self):
        """True if controller is SCSI-fast"""
        return self[DMControllerAttr.FAST]

    @property
    def fast20(self):
        """True if controller is SCSI-fast20"""
        return self[DMControllerAttr.FAST20]

    @property
    def fast40(self):
        """True if controller is SCSI-fast40"""
        return self[DMControllerAttr.FAST40]

    @property
    def fast80(self):
        """True if controller is SCSI-fast80"""
        return self[DMControllerAttr.FAST80]

    @property
    def clock(self):
        """controller clock, an int or None"""
        return self.get(DMControllerAttr.CLOCK)

    def __repr__(self):
        rlist = ["DMControllerAttr <%d>" % (id(self))]
        rlist.append("\ttype: %s" % (self.type))
        rlist.append("\tclock = %d" % (self.clock and self.clock or -1))
        rlist.append("\tcontroller is%s multiplex" % \
                     (self.multiplex and "n't" or ""))
        rlist.append("\tcontroller is%s wide" % (self.wide and "n't" or ""))
        rlist.append("\tcontroller is%s fast" % (self.fast and "n't" or ""))
        rlist.append("\tcontroller is%s fast20" % (self.fast20 and "n't" or ""))
        rlist.append("\tcontroller is%s fast40" % (self.fast40 and "n't" or ""))
        rlist.append("\tcontroller is%s fast80" % (self.fast80 and "n't" or ""))
        return "\n".join(rlist)

class DMMediaAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    BLOCKSIZE        = NVKey(const.BLOCKSIZE, DATA_TYPE_UINT32)
    SIZE             = NVKey(const.SIZE, DATA_TYPE_UINT64)
    FDISK            = NVKey(const.FDISK, DATA_TYPE_BOOLEAN)
    REMOVABLE        = NVKey(const.REMOVABLE, DATA_TYPE_BOOLEAN)
    LOADED           = NVKey(const.LOADED, DATA_TYPE_BOOLEAN)
    MTYPE            = NVKey(const.MTYPE, DATA_TYPE_UINT32)
    START            = NVKey(const.START, DATA_TYPE_UINT64)
    NACCESSIBLE      = NVKey(const.NACCESSIBLE, DATA_TYPE_UINT64)

    # These only exist for drives < 1TB
    NCYLINDERS       = NVKey(const.NCYLINDERS, DATA_TYPE_UINT32)
    NPHYSCYLINDERS   = NVKey(const.NPHYSCYLINDERS, DATA_TYPE_UINT32)
    NALTCYLINDERS    = NVKey(const.NALTCYLINDERS, DATA_TYPE_UINT32)
    NHEADS           = NVKey(const.NHEADS, DATA_TYPE_UINT32)
    NSECTORS         = NVKey(const.NSECTORS, DATA_TYPE_UINT32)
    NACTUALCYLINDERS = NVKey(const.NACTUALCYLINDERS, DATA_TYPE_UINT32)
    # Must be drive < 1TB and have a label (not EFI/GPT)
    LABEL            = NVKey(const.LABEL, DATA_TYPE_STRING)
    EFI              = NVKey(const.EFI, DATA_TYPE_BOOLEAN)

    @property
    def type(self):
        """media type, a str (see const.MEDIA_TYPE_MAP)"""                
        return const.MEDIA_TYPE_MAP[self[DMMediaAttr.MTYPE]]

    @property
    def removable(self):
        """True if media is removable"""
        return self[DMMediaAttr.REMOVABLE]

    @property
    def loaded(self):
        """True if media is removable and is loaded"""
        return self[DMMediaAttr.LOADED]

    @property
    def blocksize(self):
        """block size, an int"""
        return self[DMMediaAttr.BLOCKSIZE]

    @property
    def fdisk(self):
        """True if the media has fdisk partitions"""
        return self[DMMediaAttr.FDISK]

    @property
    def efi(self):
        """True if drive is EFI"""
        return self[DMMediaAttr.EFI]

    @property
    def size(self):
        """size, an int"""
        return self[DMMediaAttr.SIZE]

    @property
    def start(self):
        """start, and int"""
        return self[DMMediaAttr.START]
        
    @property
    def naccessible(self):
        """number of accessible blocks, an int"""
        return self[DMMediaAttr.NACCESSIBLE]

    @property
    def ncylinders(self):
        """ number of cylinders, an int or None (available for drive < 1TB) """
        return self.get(DMMediaAttr.NCYLINDERS)

    @property
    def nphyscylinders(self):
        """
        number of physical cylinders, an int or None
        (available for drives < 1TB)
        """
        return self.get(DMMediaAttr.NPHYSCYLINDERS)

    @property
    def naltcylinders(self):
        """
        number of alternate cylinders, an int or None
        (available for drives < 1TB)
        """
        return self.get(DMMediaAttr.NALTCYLINDERS)

    @property
    def nheads(self):
        """ heads, an int or None (available for drives < 1TB) """
        return self.get(DMMediaAttr.NHEADS)

    @property
    def nsectors(self):
        """ number of sectors, an int or None (available for drives < 1TB) """
        return self.get(DMMediaAttr.NSECTORS)

    @property
    def nactualcylinders(self):
        """
        number of actual cylinders, an int or None (available for drives < 1TB)
        """
        return self.get(DMMediaAttr.NACTUALCYLINDERS)

    @property
    def label(self):
        """drive label, a str or None"""
        return self.get(DMMediaAttr.LABEL)

    def __repr__(self):
        rlist = ["DMMediaAttr <%d>" % (id(self))]
        rlist.append("\ttype = %s" % (self.type))
        rlist.append("\tremovable/loaded = %s/%s" % \
                     (self.removable, self.loaded))
        rlist.append("\tfdisk = %s, efi = %s" % (self.fdisk, self.efi))
        rlist.append("\tlabel = %s" % (self.label and self.label or "-"))
        rlist.append("\tblocksize = %d, size = %d, naccessible = %d" % \
                     (self.blocksize, self.size, self.naccessible))
        # Since these may not be available try one before adding them
        if self.ncylinders is None:
            return "\n".join(rlist)
        rlist.append("\tgeometry:")
        rlist.append("\t\tcylinders:")
        rlist.append("\t\t\tnumber           = %d" % (self.ncylinders))
        rlist.append("\t\t\tphysical number  = %d" % (self.nphyscylinders))
        rlist.append("\t\t\talternate number = %d" % (self.naltcylinders))
        rlist.append("\t\t\tactual number    = %d" % (self.nactualcylinders))
        rlist.append("\t\theads = %d" % (self.nheads))
        rlist.append("\t\tsectors = %d" % (self.nsectors))
        return "\n".join(rlist)

class DMPathAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    CTYPE  = NVKey(const.CTYPE, DATA_TYPE_STRING)
    # only paths for drives have this
    PSTATE = NVKey(const.PATH_STATE, DATA_TYPE_STRING)
    WWN    = NVKey(const.WWN, DATA_TYPE_STRING)

    @property
    def type(self):
        """type, a str"""
        return self[DMPathAttr.CTYPE]

    @property
    def state(self):
        """state, a str or None (only paths for drives have state)"""
        return self.get(DMPathAttr.PSTATE)

    @property
    def wwn(self):
        """wwn, a str or None (only pahts for drives have wwn)"""
        return self.get(DMPathAttr.WWN)

    def __repr__(self):
        rlist = ["DMPathAttr <%d>" % (id(self))]
        rlist.append("\ttype = %s" % (self.type))
        if self.state:
            rlist.append("\tstate = %s" % (self.state))
        if self.state:
            rlist.append("\twwn = %s" % (self.wwn))
        return "\n".join(rlist)

class DMAliasAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    LUN    = NVKey(const.LUN, DATA_TYPE_UINT32)
    TARGET = NVKey(const.TARGET, DATA_TYPE_UINT32)
    WWN    = NVKey(const.WWN, DATA_TYPE_STRING)
    STATUS = NVKey(const.STATUS, DATA_TYPE_UINT32)

    @property
    def lun(self):
        """lun number, an int or None"""
        return self.get(DMAliasAttr.LUN)

    @property
    def target(self):
        """target number, an int or None"""
        return self.get(DMAliasAttr.TARGET)

    @property
    def wwn(self):
        """wwn, a str or None"""
        return self.get(DMAliasAttr.WWN)

    @property
    def status(self):
        """status, a str or None"""
        return self[DMAliasAttr.STATUS] == const.DRIVE_UP and "UP" or "DOWN"

    def __repr__(self):
        rlist = ["DMAliasAttr <%d>" % (id(self))]
        rlist.append("\tlun/target = %s/%s" % (str(self.lun), str(self.target)))
        rlist.append("\twwn = %s" % (self.wwn))
        rlist.append("\tstatus = %s" % (self.status))
        return "\n".join(rlist)


class DMBusAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    TYPE  = NVKey(const.BTYPE, DATA_TYPE_STRING)
    CLOCK = NVKey(const.CLOCK, DATA_TYPE_UINT32)
    PNAME = NVKey(const.PNAME, DATA_TYPE_STRING)

    @property
    def type(self):
        """type, a str"""
        return self[DMBusAttr.TYPE]

    @property
    def clock(self):
        """clock, an int or None"""
        return self.get(DMBusAttr.CLOCK)

    @property
    def pname(self):
        """pname, a str or None"""
        return self.get(DMBusAttr.PNAME)

    def __repr__(self):
        rlist = ["DMBusAttr <%d>" % (id(self))]
        rlist.append("\ttype = %s" % (self.type))
        rlist.append("\tclock = %s" % (str(self.clock)))
        rlist.append("\tpname = %s" % (self.pname))
        return "\n".join(rlist)


class DMPartAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    TYPE     = NVKey(const.PARTITION_TYPE, DATA_TYPE_UINT32)
    BOOTID   = NVKey(const.BOOTID, DATA_TYPE_UINT32)
    PTYPE    = NVKey(const.PTYPE, DATA_TYPE_UINT32)
    BHEAD    = NVKey(const.BHEAD, DATA_TYPE_UINT32)
    BSECT    = NVKey(const.BSECT, DATA_TYPE_UINT32)
    BCYL     = NVKey(const.BCYL, DATA_TYPE_UINT32)
    EHEAD    = NVKey(const.EHEAD, DATA_TYPE_UINT32)
    ESECT    = NVKey(const.ESECT, DATA_TYPE_UINT32)
    ECYL     = NVKey(const.ECYL, DATA_TYPE_UINT32)
    RELSECT  = NVKey(const.RELSECT, DATA_TYPE_UINT32)
    NSECTORS = NVKey(const.NSECTORS, DATA_TYPE_UINT32)
    #INUSE    = NVKey(const.PARTITION_WHO_TYPE, DATA_TYPE_UINT32)
    
    @property
    def type(self):
        """partition type, a str (see const.PARTITION_TYPE_MAP)"""
        return const.PARTITION_TYPE_MAP[self[DMPartAttr.TYPE]]

    @property
    def bootid(self):
        """bootid, an int"""
        return self[DMPartAttr.BOOTID]

    @property
    def id(self):
        """partition ID, an int"""
        return self[DMPartAttr.PTYPE]

    @property
    def bhead(self):
        """partition bhead, an int"""
        return self[DMPartAttr.BHEAD]

    @property
    def bsect(self):
        """partition ehead, an int"""
        return self[DMPartAttr.BSECT]

    @property
    def bcyl(self):
        """partition bcyl, an int"""
        return self[DMPartAttr.BCYL]

    @property
    def ehead(self):
        """partition bhead, an int"""
        return self[DMPartAttr.EHEAD]

    @property
    def esect(self):
        """partition ehead, an int"""
        return self[DMPartAttr.ESECT]

    @property
    def ecyl(self):
        """partition bcyl, an int"""
        return self[DMPartAttr.ECYL]

    @property
    def relsect(self):
        """partition relsect, an int"""
        return self[DMPartAttr.RELSECT]

    @property
    def nsectors(self):
        """partiion size in sectors, an int"""
        return self[DMPartAttr.NSECTORS]

    def __repr__(self):
        rlist = ["DMPartAttr <%d>" % (id(self))]
        rlist.append("\tpartition type: %s" % (self.type))
        rlist.append("\tpartition bootid = %d" % (self.bootid))
        rlist.append("\tpartition ID = %s" % (self.id))
        rlist.append("\tbhead/bsect/bcyl = %d/%d/%d" % \
                     (self.bhead, self.bsect, self.bcyl))
        rlist.append("\tehead/esect/ecyl = %d/%d/%d" % \
                     (self.ehead, self.esect, self.ecyl))
        rlist.append("\trelsect = %d" % (self.relsect))
        rlist.append("\tnsectors = %d" % (self.nsectors))
        return "\n".join(rlist)

class DMSliceAttr(NVList):
    """NVList with specific keys"""

    _type_ = NVList._type_

    INDEX     = NVKey(const.INDEX, DATA_TYPE_UINT32)
    START     = NVKey(const.START, DATA_TYPE_UINT64)
    SIZE      = NVKey(const.SIZE, DATA_TYPE_UINT64)
    EFI       = NVKey(const.EFI, DATA_TYPE_BOOLEAN)

    # TAG FLAG only valid if EFI is False (VTOC)
    TAG       = NVKey(const.TAG, DATA_TYPE_UINT32)
    FLAG      = NVKey(const.FLAG, DATA_TYPE_UINT32)
    # EFI_NAME only valid if EFI is True
    EFI_NAME  = NVKey(const.EFI_NAME, DATA_TYPE_STRING)
    # Only valid for "cluster slices"
    LOCALNAME = NVKey(const.LOCALNAME, DATA_TYPE_STRING)

    DEVT      = NVKey(const.DEVT, DATA_TYPE_UINT64)
    DEVICEID  = NVKey(const.DEVICEID, DATA_TYPE_STRING)
    
    @property
    def index(self):
        """slice index, an int"""
        return self[DMSliceAttr.INDEX]

    @property
    def start(self):
        """slice start, an int"""
        return self[DMSliceAttr.START]

    @property
    def size(self):
        """slice size, an int"""
        return self[DMSliceAttr.SIZE]

    @property
    def efi(self):
        """True if slice is EFI, false if slice is VTOC"""
        return self[DMSliceAttr.EFI]

    @property
    def tag(self):
        """slice tag, an int (if EFI False) or None"""
        if self.efi is True:
            return None
        else:
            return self[DMSliceAttr.TAG]

    @property
    def flag(self):
        """slice flag, an int (if EFI False) or None"""
        if self.efi is True:
            return None
        else:
            return self[DMSliceAttr.FLAG]

    @property
    def efi_name(self):
        """slice EFI name, a str (if EFI is True) or None"""
        if self.efi is False:
            return None
        else:
            return self.get(DMSliceAttr.EFI_NAME)

    @property
    def localname(self):
        """slice localname, a str or None"""
        return self.get(DMSliceAttr.LOCALNAME)

    @property
    def devt(self):
        """slice devt, an int"""
        return self[DMSliceAttr.DEVT]

    @property
    def deviceid(self):
        """slice deviceid, a str or None"""
        # not all slices have this, and zvols show up as slices
        return self.get(DMSliceAttr.DEVICEID)

    def __repr__(self):
        rlist = ["DMSliceAttr <%d>" % (id(self))]
        rlist.append("\tindex: %d" % (self.index))
        rlist.append("\tstart: %d" % (self.start))
        rlist.append("\tsize:  %d" % (self.size))
        if self.efi is False:
            rlist.append("\tVTOC: tag/flag = %d/%d" % (self.tag, self.flag))
        else:
            rlist.append("\tEFI: %s" % (self.efi_name))
        if self.localname is not None:
            rlist.append("\tLocalname: %s" % (self.localname))
        rlist.append("\tdevt = %d" % (self.devt))
        rlist.append("\tdeviceid = %s" % (self.deviceid))
        return "\n".join(rlist)
