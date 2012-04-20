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
""" Python packge with ctypes wrapper for libdiskmgt.so (undocumented).
"""

import ctypes as C
import errno
import fcntl
import numbers
import os

from bootmgmt.pysol import di_find_prop
from solaris_install.target.cgc import CTypesStructureRef
from solaris_install.target.libdiskmgt import cfunc, const, cstruct
from solaris_install.target.libdiskmgt.attributes import DMDriveAttr, \
    DMControllerAttr, DMMediaAttr, DMSliceAttr, DMPartAttr, DMPathAttr, \
    DMAliasAttr, DMBusAttr
from solaris_install.target.libnvpair.cfunc import nvlist_free

"""
This is how everything is related in libdiskmgt.so:

                             alias        +--> partition
 +---+                         ^          |      ^
 |   |                         |          |      |
 |   v                         v          v      |
 |  bus <--> controller <--> drive <--> media    |
 |   |           ^             ^          ^      |
 +---+           |             |          |      v
                 +--> path <---+          +--> slice

This means if you have a DMBus you can use the
get_associated_descriptors(cont.CONTROLLER) to get the DMController for
that DMBus.

This is accessed at run time via cfunc.dm_get_associated_types()
"""

# #defines from /usr/include/sys/dkio.h
DKIOCGGEOM = (0x04 << 8) | 1
DKIOCINFO = (0x04 << 8) | 3
DKIOCSETWCE = (0x04 << 8) | 37
DKIOCGMEDIAINFO = (0x04 << 8) | 42
DKC_CDROM = 1


class DMDescriptor(cstruct.dm_desc):
    """DMDescriptor Base class"""
    @property
    def ref(self):
        """GC reference"""
        try:
            return self._ref
        except AttributeError:
            return None

    @ref.setter
    def ref(self, val):
        """set GC reference"""
        self._ref = val

    @property
    def name(self):
        """Name of this descriptor, a str"""
        err = C.c_int()
        cstr = cfunc.dm_get_name(self, C.byref(err))
        if err.value != 0:
            if err.value == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            else:
                raise OSError(err.value, "dm_get_name: %s" % \
                              (os.strerror(err.value)))

        # will copy so we can free
        rstr = cstr.value
        cfunc.dm_free_name(cstr)
        return rstr

    @property
    def dtype(self):
        """type of this descriptor, one of DESC_TYPE an int"""
        result = cfunc.dm_get_type(self)
        if result == -1:
            # Lost the cache.
            raise OSError(errno.EBADF, "dm_get_type: %s" % \
                          (os.strerror(errno.EBADF)))
        return result

    @property
    def associated_dtypes(self):
        """associated types for this descriptor, a tuple of DESC_TYPE"""
        intp = cfunc.dm_get_associated_types(self.dtype)
        rlist = list()
        idx = 0
        while True:
            val = intp[idx]
            if val == -1:
                break
            rlist.append(val)
            idx += 1
        return tuple(rlist)

    @property
    def attributes(self):
        """attributes of this descriptor, an NVList or None"""
        # Subclasses must set ATYPE.
        try:
            atype = type(self).ATYPE
        except AttributeError:
            return None
        err = C.c_int()
        cfunc.dm_get_attributes.restype = atype
        attr = cfunc.dm_get_attributes(self, C.byref(err))
        cfunc.dm_get_attributes.restype = _dm_get_attributes_restype
        if err.value != 0:
            if err.value == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            else:
                raise OSError(err.value, "dm_get_attributes: %s" % \
                              (os.strerror(err.value)))
        CTypesStructureRef(attr, nvlist_free)
        return attr

    def get_associated_descriptors(self, dtype):
        """
        get_associated_descriptors(int or str) -> tuple of DMDescriptor

        raises AttributeError if dtype not in self.associated_dtypes
        """
        # First be sure we have this dtype.
        if isinstance(dtype, str):
            try:
                dtype = const.DESC_TYPE_MAP[dtype]
            except KeyError:
                raise ValueError("dtype: '%s' not in %s" % (dtype,
                                 set([const.DESC_TYPE_MAP[key] for
                                      key in const.DESC_TYPE_MAP])))
        else:
            if not isinstance(dtype, numbers.Integral):
                raise TypeError("dtype: '%s' object is not int or str" % \
                                (dtype.__class__.__name__))
            try:
                if dtype not in set(const.DESC_TYPE):
                    raise ValueError("dtype: %d not in %s" % (dtype,
                                     set(const.DESC_TYPE)))
            except TypeError:
                raise

        if dtype not in self.associated_dtypes:
            raise AttributeError("dtype: %d ('%s') not valid for %d ('%s')" % \
                                 (dtype, const.DESC_TYPE_MAP[dtype],
                                  self.dtype, const.DESC_TYPE_MAP[self.dtype]))

        # Finally... all is well so lets look it up.
        err = C.c_int()

        # By setting restype we get the right class
        cfunc.dm_get_associated_descriptors.restype = \
            C.POINTER(_RESTYPE[dtype])
        descp = cfunc.dm_get_associated_descriptors(self, dtype, C.byref(err))
        cfunc.dm_get_associated_descriptors.restype = \
            _dm_get_associated_descriptors_restype

        if err.value != 0:
            if err.value == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            else:
                raise OSError(err.value, "dm_get_associated_descriptors: " \
                              "%s" % (os.strerror(err.value)))

        rlist = list()
        idx = 0
        while True:
            val = descp[idx]
            # NULL
            if val.value == 0:
                break
            # GC Alert
            val.ref = descp
            rlist.append(val)
            idx += 1
        if idx > 0:
            # Got descriptors so we have to track them.
            CTypesStructureRef(descp, cfunc.dm_free_descriptors)
        else:
            cfunc.dm_free_descriptors(descp)

        return tuple(rlist)

    def __repr__(self):
        """__repr__(x) <==> repr(x)"""
        attr = self.attributes

        rlist = ["%s <%d>" % (self.__class__.__name__, id(self))]
        rlist.append('\tname = "%s"' % (self.name))

        astr = ["\t%s" % (line) for line in str(attr).split('\n')[0:]]
        rlist.extend(astr)
        return "\n".join(rlist)


class DMDrive(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.DRIVE"""
    ATYPE = DMDriveAttr

    class DKCinfo(C.Structure):
        """ dk_cinfo structure from usr/src/uts/common/sys/dkio.h
        """
        _fields_ = [
            ("dki_cname", C.c_char * 16),
            ("dki_ctype", C.c_ushort),
            ("dki_flags", C.c_ushort),
            ("dki_cnum", C.c_ushort),
            ("dki_addr", C.c_uint),
            ("dki_space", C.c_uint),
            ("dki_prio", C.c_uint),
            ("dki_vec", C.c_uint),
            ("dki_dname", C.c_char * 16),
            ("dki_unit", C.c_uint),
            ("dki_slave", C.c_uint),
            ("dki_partition", C.c_ushort),
            ("dki_maxtransfer", C.c_ushort)]

    class DKMinfo(C.Structure):
        """ dk_minfo structure from usr/src/uts/common/sys/dkio.h
        """
        _fields_ = [
            ("dki_media_type", C.c_uint),
            ("dki_lbsize", C.c_uint),
            ("dki_capacity", C.c_longlong)
        ]

    class DKGeom(C.Structure):
        """ dk_geom structure from usr/src/uts/common/sys/dkio.h
        """
        _fields_ = [
            ("dkg_ncyl", C.c_ushort),
            ("dkg_acyl", C.c_ushort),
            ("dkg_bcyl", C.c_ushort),
            ("dkg_nhead", C.c_ushort),
            ("dkg_obs1", C.c_ushort),
            ("dkg_nsect", C.c_ushort),
            ("dkg_intrlv", C.c_ushort),
            ("dkg_obs2", C.c_ushort),
            ("dkg_obs3", C.c_ushort),
            ("dkg_arc", C.c_ushort),
            ("dkg_rpm", C.c_ushort),
            ("dkg_pcyl", C.c_ushort),
            ("dkg_write_reinstruct", C.c_ushort),
            ("dkg_read_reinstruct", C.c_ushort),
            ("dkg_extra", C.c_ushort * 7)
        ]

    @property
    def controllers(self):
        """tuple of controllers associated with this drive"""
        return self.get_associated_descriptors(const.CONTROLLER)

    @property
    def aliases(self):
        """tuple of alias associated with this drive"""
        return self.get_associated_descriptors(const.ALIAS)

    @property
    def paths(self):
        """tuple of paths associated with this drive"""
        return self.get_associated_descriptors(const.PATH)

    @property
    def media(self):
        """media associated with this drive or None"""
        try:
            return self.get_associated_descriptors(const.MEDIA)[0]
        except IndexError:
            # removable and not loaded
            return None

    @property
    def cdrom(self):
        """ property to indicate if the drive is a cd-rom drive
        """
        dk_cinfo = self.DKCinfo()

        fd = os.open(self.attributes.opath, os.O_RDONLY | os.O_NDELAY)
        try:
            fcntl.ioctl(fd, DKIOCINFO, C.addressof(dk_cinfo))
        finally:
            os.close(fd)
        if dk_cinfo.dki_ctype == DKC_CDROM:
            return True
        return False

    @property
    def use_stats(self):
        """use_stats of drive"""
        # The usage stats are an NVList that has no unique properties,
        # names or name/type combo. So really it is only usable as an
        # iterator which we will turn into a Python dictionary.
        err = C.c_int()
        nvl = cfunc.dm_get_stats(self, const.DSTAT_DIAGNOSTIC, C.byref(err))
        if err.value != 0:
            if err.value == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            raise OSError(err.value, "dm_get_stats: %s" % \
                          (os.strerror(err.value)))

        # create a Python dictionary but we combine all the values
        # from NVList that have the same key. So every value in the
        # result dictionary is a tuple.
        result = dict()
        for key, val in nvl.iteritems():
            # When the key doesn't exist put it in a list.
            # When it does add it to the end of the list.
            try:
                # list from tuple
                lst = list(result[key.name])
            except KeyError:
                # new list
                lst = list()
            lst.append(val)
            # values put in tuple
            result[key.name] = tuple(lst)
        nvlist_free(nvl)
        return result


class DMController(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.CONTROLLER"""
    ATYPE = DMControllerAttr

    @property
    def floppy_controller(self):
        """ property to indicate if the controller is a floppy drive USB
        controller.
        """

        if self.attributes is not None and \
           self.attributes.type == const.CTYPE_USB:
            try:
                di_props = di_find_prop("compatible", self.name)
            except Exception:
                di_props = list()
            return const.DI_FLOPPY in di_props
        return False

    @property
    def bus(self):
        """bus associated with this controller"""
        return self.get_associated_descriptors(const.BUS)[0]

    @property
    def paths(self):
        """tuple of paths associated with this controller"""
        return self.get_associated_descriptors(const.PATH)

    @property
    def drives(self):
        """tuple of drives associated with this controller"""
        return self.get_associated_descriptors(const.DRIVE)


class DMMedia(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.MEDIA"""
    ATYPE = DMMediaAttr

    @property
    def drive(self):
        """drive associated with this media"""
        return self.get_associated_descriptors(const.DRIVE)[0]

    @property
    def partitions(self):
        """tuple of partitions associated with this media"""
        return self.get_associated_descriptors(const.PARTITION)

    @property
    def slices(self):
        """tuple of slices associated with this media"""
        return self.get_associated_descriptors(const.SLICE)


class DMSlice(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.SLICE"""
    ATYPE = DMSliceAttr

    @property
    def media(self):
        """media associated with this slice"""
        return self.get_associated_descriptors(const.MEDIA)[0]

    @property
    def partitions(self):
        """tuple of partitions associated with this slice"""
        # it does not narrow it down. basically you get the partitions
        # associated with the same media this slice is asociated with.
        return self.get_associated_descriptors(const.PARTITION)

    @property
    def use_stats(self):
        """use_stats of slice"""
        # The usage stats are an NVList that has no unique properties,
        # names or name/type combo. So really it is only usable as an
        # iterator which we will turn into a Python dictionary.
        err = C.c_int()
        nvl = cfunc.dm_get_stats(self, const.SSTAT_USE, C.byref(err))
        if err.value != 0:
            if err.value == errno.ENOMEM:
                raise MemoryError("insufficient memory")
            raise OSError(err.value, "dm_get_stats: %s" % \
                          (os.strerror(err.value)))

        # create a Python dictionary but we combine all the values
        # from NVList that have the same key. So every value in the
        # result dictionary is a tuple.
        result = dict()
        for key, val in nvl.iteritems():
            # When the key doesn't exist put it in a list.
            # When it does add it to the end of the list.
            result.setdefault(key.name, []).append(val)
        nvlist_free(nvl)
        return result


class DMPartition(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.PARTITION"""
    ATYPE = DMPartAttr

    @property
    def media(self):
        """media associated with this partition"""
        return self.get_associated_descriptors(const.MEDIA)[0]


class DMPath(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.PATH"""
    ATYPE = DMPathAttr

    @property
    def conroller(self):
        """controller or None associated with this path"""
        try:
            return self.get_associated_descriptors(const.CONTROLLER)[0]
        except IndexError:
            return None

    @property
    def drives(self):
        """tuple of drives associated with this path"""
        return self.get_associated_descriptors(const.DRIVE)


class DMAlias(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.ALIAS"""
    ATYPE = DMAliasAttr

    @property
    def drive(self):
        """drive associated with this alias"""
        return self.get_associated_descriptors(const.DRIVE)[0]


class DMBus(DMDescriptor):
    """A libdiskmgt.so descriptor that is of type const.BUS"""
    ATYPE = DMBusAttr

    @property
    def controllers(self):
        """list of controllers associated with this bus"""
        return self.get_associated_descriptors(const.CONTROLLER)


def descriptor_from_key(dtype, name):
    """
    descriptor_from_name(int or str, str) -> DMDescriptor object

    raises KeyError if the descriptor does not exist.
    """
    # First validate dtype
    if isinstance(dtype, str):
        if dtype not in const.DESC_TYPE_MAP:
            raise ValueError("dtype: '%s' not in %s" % (dtype,
                             set([const.DESC_TYPE_MAP[key]
                                 for key in const.DESC_TYPE_MAP])))
    else:
        if not isinstance(dtype, numbers.Integral):
            raise TypeError("dtype: '%s' object is not int or str" % \
                            (dtype.__class__.__name__))
        if dtype not in set(const.DESC_TYPE):
            raise ValueError("dtype: %d not in %s" % (dtype,
                             set(const.DESC_TYPE)))

    err = C.c_int()
    desc = cfunc.dm_get_descriptor_by_name(dtype, name, C.byref(err))
    if err.value != 0:
        if err.value == errno.ENODEV:
            raise KeyError("(%d '%s', '%s')" % \
                           (dtype, const.DESC_TYPE_MAP[dtype], name))
        if err.value == errno.ENOMEM:
            raise MemoryError("insufficient memory")
        raise OSError(err.value, "dm_get_descriptor_by_name: %s" % \
                      (os.strerror(err.value)))

    # GC ALERT
    dmd = DMDescriptor(desc.value)
    CTypesStructureRef(dmd, cfunc.dm_free_descriptor)

    return dmd


def descriptors_by_type(dtype):
    """descriptors_by_type(int or str) -> tuple of DMDescriptor objects"""
    # First validate dtype
    if isinstance(dtype, str):
        try:
            dtype = const.DESC_TYPE_MAP[dtype]
        except KeyError:
            raise ValueError("dtype: '%s' not in %s" % (dtype,
                             set([const.DESC_TYPE_MAP[key]
                                 for key in const.DESC_TYPE_MAP])))
    else:
        if not isinstance(dtype, numbers.Integral):
            raise TypeError("dtype: '%s' object is not int or str" % \
                            (dtype.__class__.__name__))
        if dtype not in set(const.DESC_TYPE):
            raise ValueError("dtype: %d not in %s" % \
                             (dtype, set(const.DESC_TYPE)))

    err = C.c_int()
    cfunc.dm_get_descriptors.restype = C.POINTER(_RESTYPE[dtype])
    descp = cfunc.dm_get_descriptors(dtype, None, C.byref(err))
    cfunc.dm_get_descriptors.restype = _dm_get_descriptors_restype

    if err.value != 0:
        if err.value == errno.ENOMEM:
            raise MemoryError("insufficient memory")
        raise OSError(err.value, "dm_get_descriptors: %s" % \
                      (os.strerror(err.value)))

    rlist = list()
    idx = 0
    while True:
        val = descp[idx]
        # NULL
        if val.value == 0:
            break
        # GC Alert
        val.ref = descp
        rlist.append(val)
        idx += 1

    if idx > 0:
        CTypesStructureRef(descp, cfunc.dm_free_descriptors)
    else:
        cfunc.dm_free_descriptors(descp)
    return tuple(rlist)


def cache_update(event_type=const.DM_EV_DISK_ADD, devname=None):
    """ Rebuild libdiskmgt's controller and drive cache.  This is done so new
    drives (mapped iSCSI LUNs) can be added after local discovery has started.
    """

    cfunc.dm_cache_update(event_type, devname)


# Used to change the result of a call to a C function.
# This way we don't have to create a factory function.
_RESTYPE = {
    const.DRIVE:      DMDrive,
    const.CONTROLLER: DMController,
    const.MEDIA:      DMMedia,
    const.SLICE:      DMSlice,
    const.PARTITION:  DMPartition,
    const.PATH:       DMPath,
    const.ALIAS:      DMAlias,
    const.BUS:        DMBus,
}
_dm_get_associated_descriptors_restype = \
    cfunc.dm_get_associated_descriptors.restype
_dm_get_descriptors_restype = cfunc.dm_get_descriptors.restype
_dm_get_attributes_restype = cfunc.dm_get_attributes.restype
