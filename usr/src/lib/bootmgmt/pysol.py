#! /usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

"Solaris-specific library wrappers and functions"

from ctypes import *
import gettext
import errno
import platform
import os

try:
    _ = gettext.translation("SUNW_OST_OSLIB", "/usr/lib/locale",
        fallback=True).gettext
except:
    try:
        import solaris.misc
        _ = solaris.misc.gettext
    except:
        _ = lambda x : x

(LIBZFS_INIT_FAILURE,
 ) = range(1)

_msgs = {
    LIBZFS_INIT_FAILURE: _('libzfs initialization failure')
}

#
# From sys/fstyp.h
#
FSTYPSZ = 16

MAX_PATH = 1024

_libc = CDLL('libc.so', use_errno=True)
_platwidth = platform.architecture()[0][:2]
_libc.fopen.restype = c_void_p
_libc.free.argtypes = [c_void_p]
_libc.free.restype = None
_statvfs_syscall = 'statvfs' + ('64' if _platwidth == '32' else '')
# print 'platwidth = `%s\' | _syscall = `%s\'' % (_platwidth, _syscall)
_statvfs = getattr(_libc, _statvfs_syscall)


def ctype2dict(ctype_struct_instance):
        dictresult = {}

        # A very important side-effect of calling getattr() here is
        # that the ctypes API creates copies of the data we're
        # retrieving from the "structure".  If it did not do that,
        # calling libc APIs that use static data areas would cause
        # the resulting Python strings to refer to the same storage
        # area.
        for x in [x for (x, y) in ctype_struct_instance._fields_]:
                dictresult[x] = getattr(ctype_struct_instance, x)

        return dictresult

# ==============================[ statvfs ]===============================


class StatVFS_Result(Structure):
        """From the manpage:
        int statvfs(const char *restrict path, struct statvfs *restrict buf);

                u_long      f_bsize;     /* preferred file system block size */
                u_long      f_frsize;    /* fundamental filesystem block
                                                  (size if supported) */
                fsblkcnt_t  f_blocks;    /* total # of blocks on file system
                                                  in units of f_frsize */
                fsblkcnt_t  f_bfree;     /* total # of free blocks */
                fsblkcnt_t  f_bavail;    /* # of free blocks avail to
                                                  non-privileged user */
                fsfilcnt_t  f_files;     /* total # of file nodes (inodes) */
                fsfilcnt_t  f_ffree;     /* total # of free file nodes */
                fsfilcnt_t  f_favail;    /* # of inodes avail to
                                                  non-privileged user*/
                u_long      f_fsid;      /* file system id (dev for now) */
                char        f_basetype[FSTYPSZ]; /* target fs type name,
                                                   null-terminated */
                u_long      f_flag;      /* bit mask of flags */
                u_long      f_namemax;   /* maximum file name length */
                char        f_fstr[32];  /* file system specific string */
          if not 64-bit process
               u_long      f_filler[16]; /* reserved for future expansion */
          endif

        We always use the 64-bit statvfs variant (statvfs64 in 32-bit
        processes and statvfs in 64-bit processes)

        """

        _fields_ = [("f_bsize", c_ulong),
                    ("f_frsize", c_ulong),
                    ("f_blocks", c_ulonglong),
                    ("f_bfree", c_ulonglong),
                    ("f_bavail", c_ulonglong),
                    ("f_files", c_ulonglong),
                    ("f_ffree", c_ulonglong),
                    ("f_favail", c_ulonglong),
                    ("f_fsid", c_ulong),
                    ("f_basetype", c_char * FSTYPSZ),
                    ("f_flag", c_ulong),
                    ("f_namemax", c_ulong),
                    ("f_fstr", c_char * 32),
                    ("f_filler", c_int * 16)]


def statvfs(path):
        """Returns a dictionary whose members are the result of the Solaris
        statvfs() call"""

        result = StatVFS_Result()

        if _statvfs(path, pointer(result)) != 0:
                raise IOError(get_errno(), os.strerror(get_errno()))

        return ctype2dict(result)


# ===========================[ mnttab functions ]============================


class SolarisMntTab(Structure):
        "Python ctype expression of the Solaris mnttab structure"
        _fields_ = [('mnt_special', c_char_p),
                    ('mnt_mountp', c_char_p),
                    ('mnt_fstype', c_char_p),
                    ('mnt_mntopts', c_char_p),
                    ('mnt_time', c_char_p)]


class SolarisExtMntTab(Structure):
        "Python ctype expression of the Solaris extmnttab structure"
        _fields_ = [('mnt_special', c_char_p),
                    ('mnt_mountp', c_char_p),
                    ('mnt_fstype', c_char_p),
                    ('mnt_mntopts', c_char_p),
                    ('mnt_time', c_char_p),
                    ('mnt_major', c_uint),
                    ('mnt_minor', c_uint)]


def mnttab_err_decode(code):
        """Decodes the following error codes from mnttab.h:
        #define MNT_TOOLONG     1       /* entry exceeds MNT_LINE_MAX */
        #define MNT_TOOMANY     2       /* too many fields in line */
        #define MNT_TOOFEW      3       /* too few fields in line */
        """
        if code == 1:
                return 'Entry exceeds 1024 characters'
        elif code == 2:
                return 'Too many fields in line'
        elif code == 3:
                return 'Too few fields in line'
        else:
                return 'Unknown mnttab error'


def mnttab_open(mtab='/etc/mnttab'):
        global _mnttab_FILE
        _mnttab_FILE = c_void_p(_libc.fopen(mtab, 'r'))
        if _mnttab_FILE.value is None:
                raise IOError(get_errno(), mtab + ': ' + 
                              os.strerror(get_errno()))


def getmntent():
        """Returns the next mnttab entry as a dictionary whose keys
        are:
                mnt_special
                mnt_mountp
                mnt_fstype
                mnt_mntopts
                mnt_time
        or None if there are no more entries
        """
        mntent = SolarisMntTab()
        r = _libc.getmntent(_mnttab_FILE, byref(mntent))
        if r < 0:                # EOF
                return None
        elif r > 0:                # Error
                raise IOError(r, mnttab_err_decode(r))

        return ctype2dict(mntent)


def getmntany(**attrs):
        """Returns a mnttab entry matching the attributes passed in, or
        None if no entry matches.
        """
        mntent = SolarisMntTab()
        mntmatch = SolarisMntTab()
        for x in attrs.keys():
                mntent.__setattr__(x, attrs[x])
        r = _libc.getmntany(_mnttab_FILE, byref(mntmatch), byref(mntent))
        if r < 0:                # EOF
                return None
        elif r > 0:
                raise IOError(r, mnttab_err_decode(r))

        return ctype2dict(mntmatch)


def getextmntent():
        """Returns the next extmnttab entry as a dictionary whose keys
        are:
                mnt_special
                mnt_mountp
                mnt_fstype
                mnt_mntopts
                mnt_time
                mnt_major
                mnt_minor
        or None if there are no more entries.
        """
        extmnt = SolarisExtMntTab()
        r = _libc.getextmntent(_mnttab_FILE, byref(extmnt), sizeof(extmnt))
        if r < 0:                # EOF
                return None
        elif r > 0:
                raise IOError(r, mnttab_err_decode(r))

        return ctype2dict(extmnt)


def resetmnttab(reopen=False):
        """Rewinds the mnttab file to the beginning
        if reopen is True, the mnttab file is closed, then reopened
        """
        if reopen is True:
                mnttab_close()
                mnttab_open()
        else:
                _libc.rewind(_mnttab_FILE)


def mnttab_close():
                _libc.fclose(_mnttab_FILE)


# ==============================[devlink walking]============================

_libdi = CDLL('libdevinfo.so', use_errno=True)
_libdi.di_devlink_init.restype = c_void_p
_libdi.di_devlink_init.argtypes = [c_char_p, c_int]
_libdi.di_devlink_path.restype = c_char_p
_libdi.di_devlink_path.argtypes = [c_void_p]
# The walker function returns an int and takes 2 void *'s: the di_devlink_t,
# and the arg
_devlink_walkfunc_type = CFUNCTYPE(c_int, c_void_p, c_void_p)
_libdi.di_devlink_walk.argtypes = [c_void_p, c_char_p, c_char_p, c_int,
                                   c_void_p, _devlink_walkfunc_type]
# from <libdevinfo.h>:
DI_MAKE_LINK = 1
DI_PRIMARY_LINK = 1
DI_SECONDARY_LINK = 2
DI_WALK_CONTINUE = 0
DI_WALK_TERMINATE = -3


def di_devlink_init(drvname=None, flags=0):
        """Initialize the libdevinfo devlink interfaces"""
        hdl = c_void_p(_libdi.di_devlink_init(drvname, flags))
        if hdl.value is None:
                raise IOError(get_errno(), os.strerror(get_errno()))
        return hdl


def di_devlink_path(dl):
        """Return a string that is the path corresponding to the devlink
        passed in
        """
        r = _libdi.di_devlink_path(dl)
        if r is None:
                raise IOError(get_errno(), os.strerror(get_errno()))
        return r


def di_devlink_walk(hdl, pattern, path, flags, walk_arg, walkfunc):
        """Conduct a walk of all devlinks that patch the given pattern and
        that pertain to the given path.  Note that since ctypes passes
        arguments to callbacks as 'int's, those arguments must be converted
        into a useful Python type (passing a string, then reconstituting
        a list from that string, for example).
        """

        wf = _devlink_walkfunc_type(walkfunc)
        r = _libdi.di_devlink_walk(hdl, pattern, path, flags, walk_arg, wf)
        if r < 0:
                raise IOError(get_errno(), os.strerror(get_errno()))


def di_devlink_fini(hdl):
        """Performs cleanup after use of the devlink interfaces"""
        _libdi.di_devlink_fini(hdl)

# ==========================[ libdevinfo subset ]=============================

_minor_walkfunc_type = CFUNCTYPE(c_int, c_void_p, c_void_p, c_void_p)

_libdi.di_init.restype = c_void_p
_libdi.di_init.argtypes = [c_char_p, c_int]
_libdi.di_fini.argtypes = [c_void_p]
_libdi.di_devfs_path.restype = c_void_p
_libdi.di_devfs_path.argtypes = [c_void_p]
_libdi.di_devfs_path_free.argtypes = [c_void_p]
_libdi.di_minor_spectype.argtypes = [c_void_p]
_libdi.di_minor_name.restype = c_char_p
_libdi.di_minor_name.argtypes = [c_void_p]
_libdi.di_minor_next.restype = c_void_p
_libdi.di_minor_next.argtypes = [c_void_p, c_void_p]
_libdi.di_walk_minor.argtypes = [c_void_p, c_char_p, c_int, c_void_p,
                                        _minor_walkfunc_type]
_libdi.di_prop_lookup_strings.argtypes = [c_ulong, c_void_p,
                                          c_char_p, c_void_p]


class struct_boot_dev(Structure):
    _fields_ = [('bootdev_element', c_char_p),
                ('bootdev_trans', POINTER(c_char_p))]
pp_struct_boot_dev = POINTER(POINTER(struct_boot_dev))
_libdi.devfs_bootdev_get_list.argtypes = [c_char_p, 
                                          POINTER(pp_struct_boot_dev)]
_libdi.devfs_bootdev_free_list.argtypes = [pp_struct_boot_dev]
_libdi.devfs_bootdev_free_list.restype = None


S_IFBLK = 0x6000                                        # from <sys/stat.h>
DDI_NT_BLOCK = "ddi_block"                                # from <sys/sunddi.h>

# from <sys/devinfo_impl.h>:
DIIOC = (0xdf << 8)
DINFOSUBTREE = (DIIOC | 0x01)
DINFOMINOR = (DIIOC | 0x02)
DINFOPROP = (DIIOC | 0x04)
DINFOPATH = (DIIOC | 0x08)
DINFOCPYALL = (DINFOSUBTREE | DINFOPROP | DINFOMINOR)

# from <sys/ddipropdefs.h>
DDI_DEV_T_ANY = -2
DDI_DEV_T_NONE = -1


def _di_minor_spectype(minor):
        """Returns the type (block or char) of the special node whose minor
        info is passed in
        """
        return _libdi.di_minor_spectype(minor)


def di_init(path='/', flags=(DINFOPATH | DINFOCPYALL)):
        """Initialize the device tree snapshot, starting from the device path
        specified.  flags are (DINFOPATH|DINFOCPYALL) by default.
        """
        hdl = c_void_p(_libdi.di_init(path, flags))
        if hdl.value is None:
                raise IOError(get_errno(), os.strerror(get_errno()))
        return hdl


def di_minor_is_block(minor):
        return (True if _di_minor_spectype(minor) == S_IFBLK else False)


def di_minor_name(minor):
        "Returns the string name of the minor passed in"
        return _libdi.di_minor_name(minor)


def di_devfs_path(node):
        "Returns the string name of the node passed in"
        r = c_void_p(_libdi.di_devfs_path(node))
        if r.value is None:
                raise IOError(get_errno(), os.strerror(get_errno()))
        rs = c_char_p(r.value).value
        _libdi.di_devfs_path_free(r)
        return rs


def di_minor_next(node, minor=None):
        """Returns the next minor node, relative to the minor passed in.
        If minor isn't specified, or is passed in as None, the first minor
        associated with the node is returned.  None is returned when no
        more minors exist.
        """
        r = c_void_p(_libdi.di_minor_next(node, minor))
        if r.value is None:
                e = get_errno()
                # NXIO is a special case-- an indicator of no more minors
                if e == errno.ENXIO:
                        return None
                else:
                        raise IOError(e, os.strerror(e))
        return r


def di_walk_minor(rootnode, minortype, walkarg, walkfunc, flag=0):
        """Perform a walk of all minor nodes attached to device nodes
        in a subtree rooted at `root'.  walkargs should be a simple Python
        type, since it will need to be reconstituted in the walkfunc callback.
        """

        wf = _minor_walkfunc_type(walkfunc)
        r = _libdi.di_walk_minor(rootnode, minortype, flag, walkarg, wf)
        print r
        if r < 0:
                raise IOError(get_errno(), os.strerror(get_errno()))


def di_fini(hdl):
        _libdi.di_fini(hdl)


def devfs_bootdev_get_list():

        bdl = pp_struct_boot_dev()

        rv = _libdi.devfs_bootdev_get_list('/', pointer(bdl))

        # No exception is raised on error, because there is no errno
        # value that accompanies the failure
        if rv < 0 or bool(bdl) is False:
                return None

        i = 0
        bootdevs = []
        while not bool(bdl[i]) is False:
                physical = bdl[i][0].bootdev_element
                j = 0
                logicals = []
                while not bool(bdl[i][0].bootdev_trans[j]) is False:
                        logicals.append(bdl[i][0].bootdev_trans[j])
                        j += 1
                bootdevs.append((physical, tuple(logicals)))
                i += 1

        _libdi.devfs_bootdev_free_list(bdl)

        return tuple(bootdevs)


def di_prop_lookup_strings(dev, node, prop_name, prop_data):
    rv = _libdi.di_prop_lookup_strings(dev, node, prop_name, prop_data)
    if rv < 0:
        raise IOError(get_errno(), os.strerror(get_errno()))
    return rv


def di_find_root_prop(propname):
    return di_find_prop(propname, '/')


def di_find_prop(propname, root):
    hdl = di_init(root, DINFOPROP)
    propval = None
    try:
        # This is a bit tricky, sicne di_prop_lookup_strings returns ONE
        # string with several embedded NUL terminators (if multiple strings
        # are returned).  To deal with this in ctypes, we use a pointer to
        # a c_void_p as the last parameter and manually pull out each string
        # To pull out each string, we cast the c_void_p to a c_char_p, which
        # automatically gets us the first string (ctypes extracts it for us)
        # To get subsequent strings, we need to manually index the pointer,
        # adding the length of the previous string + 1 (since len() includes
        # the NUL and one to get us past it).

        value = pointer(c_void_p())
        rv = di_prop_lookup_strings(DDI_DEV_T_ANY, hdl, propname,
                                    value)
        stringvalue = cast(value.contents, c_char_p)
        if rv == 1:
            propval = stringvalue.value
        elif rv > 1:
            stringlen = len(stringvalue.value)
            propval = [stringvalue.value]
            rv -= 1
            while rv > 0:
                value.contents.value += stringlen + 1
                stringvalue = cast(value.contents, c_char_p)
                propval.append(stringvalue.value)
                stringlen = len(stringvalue.value)
                rv -= 1
    except IOError as e:
        if e.errno == errno.ENXIO:
            propval = None
        else:
            raise
    finally:
        di_fini(hdl)
    return propval


# ==============================[ libfstyp ]==================================

_libfstyp = CDLL('libfstyp.so.1', use_errno=True)
_libfstyp.fstyp_init.argtypes = [c_int, c_uint64, c_char_p, c_void_p]
_libfstyp.fstyp_ident.argtypes = [c_void_p, c_char_p, c_void_p]
_libfstyp.fstyp_fini.argtypes = [c_void_p]
_libfstyp.fstyp_strerror.argtypes = [c_void_p, c_int]
_libfstyp.fstyp_strerror.restype = c_char_p


def fstyp_init(fd, offset=0, module_dir=None):
        "Returns a handle that can be used with other fstyp functions"
        handle = c_void_p()
        r = _libfstyp.fstyp_init(fd, offset, module_dir, byref(handle))
        if r != 0:
                raise IOError(r, _libfstyp.fstyp_strerror(r))
        return handle


def fstyp_ident(handle, name=None):
        result = c_char_p(0)
        r = _libfstyp.fstyp_ident(handle, name, byref(result))
        if r == 1:                # No Match Found
                return None
        elif r != 0:
                raise IOError(r, _libfstyp.fstyp_strerror(handle, r))
        return result.value


def fstyp_fini(handle):
        _libfstyp.fstyp_fini(handle)


# ================================[ isalist ]=================================

SI_MACHINE = 5
SI_PLATFORM = 513
SI_ISALIST = 514     # return supported isa list
SYSINFO_LEN = 257    # max buffer size, as per manpage

_libc.sysinfo.argtypes = [c_int, c_char_p, c_long]
_libc.sysinfo.restype = c_int

_isalist_cache = None


def isalist():
        "Returns a list of ISAs supported on the currently-running system"

        global _isalist_cache

        if not _isalist_cache is None:
            return _isalist_cache

        b = create_string_buffer(SYSINFO_LEN)
        r = _libc.sysinfo(SI_ISALIST, b, SYSINFO_LEN)
        if r < 0:
                raise OSError(get_errno(), os.strerror(get_errno()))

        _isalist_cache = b.value.split()
        return _isalist_cache


_platform_name_cache = None


def platform_name():
        global _platform_name_cache

        if not _platform_name_cache is None:
            return _platform_name_cache

        b = create_string_buffer(SYSINFO_LEN)
        r = _libc.sysinfo(SI_PLATFORM, b, SYSINFO_LEN)
        if r < 0:
                raise OSError(get_errno(), os.strerror(get_errno()))

        _platform_name_cache = b.value
        return b.value


_machine_name_cache = None


def machine_name():
        global _machine_name_cache

        if not _machine_name_cache is None:
            return _machine_name_cache

        b = create_string_buffer(SYSINFO_LEN)
        r = _libc.sysinfo(SI_MACHINE, b, SYSINFO_LEN)
        if r < 0:
                raise OSError(get_errno(), os.strerror(get_errno()))

        _machine_name_cache = b.value
        return b.value


# =================================[ libscf ]=================================

SCF_STATE_STRING_ONLINE = 'online'

_libscf = CDLL('libscf.so.1', use_errno=True)
_libscf.smf_get_state.argtypes = [c_char_p]
_libscf.smf_get_state.restype = c_void_p  # Why c_void_p ? See comment below.
_libscf.smf_enable_instance.argtypes = [c_char_p, c_int]
_libscf.smf_enable_instance.restype = c_int
_libscf.scf_error.argtypes = None
_libscf.scf_error.restype = c_int
_libscf.scf_strerror.argtypes = [c_int]
_libscf.scf_strerror.restype = c_char_p


class SCFError(Exception):
    "Wrap for smf errors"

    def __init__(self, errcode, errstring):
        self.errno = errcode
        self.strerror = errstring


def smf_get_state(svc):
    "Returns the current state of the specified service"

    # Need to store the result in a c_void_p because if a c_char_p were
    # specified as the return type, it would be automatically converted
    # to a Python string and we'd love the original pointer value, which
    # we need for the call to free()

    alloced_str = c_void_p(_libscf.smf_get_state(svc))
    if alloced_str.value == 0:
        return None
    result = c_char_p(alloced_str.value).value
    _libc.free(alloced_str)
    return result


def smf_enable_instance(svc, flags=0):
    "Enables the given smf service with the specified flags"

    ret = _libscf.smf_enable_instance(svc, flags)
    if ret == -1:
        scferr = _libscf.scf_error()
        raise SCFError(scferr, _libscf.scf_strerror(scferr))
    else:
        return ret


# =================================[ libzfs ]=================================

LIBZFS_PROPLEN_MAX = 1024

_libzfs = CDLL('libzfs.so.1', use_errno=True)
_libzfs.libzfs_init.restype = c_void_p

_libzfs.libzfs_fini.argtypes = [c_void_p]
_libzfs.libzfs_fini.restype = None

_libzfs.libzfs_error_description.argtypes = [c_void_p]
_libzfs.libzfs_error_description.restype = c_char_p

_libzfs.zfs_open.restype = c_void_p
_libzfs.zfs_open.argtypes = [c_void_p, c_char_p, c_int]

_libzfs.zfs_close.argtypes = [c_void_p]
_libzfs.zfs_close.restype = None

zif_callback = CFUNCTYPE(c_int, c_void_p, c_void_p)
_libzfs.zfs_iter_filesystems.argtypes = [c_void_p, zif_callback, c_void_p]

_libzfs.zfs_get_type.argtypes = [c_void_p]

_libzfs.zfs_get_name.restype = c_char_p
_libzfs.zfs_get_name.argtypes = [c_void_p]

_libzfs.zfs_name_valid.argtypes = [c_char_p, c_int]

_libzfs.zpool_open.restype = c_void_p
_libzfs.zpool_open.argtypes = [c_void_p, c_char_p]

_libzfs.zpool_close.restype = None
_libzfs.zpool_close.argtypes = [c_void_p]

_libzfs.zpool_get_physpath.argtypes = [c_void_p, c_char_p, c_int]

_libzfs.zpool_get_prop.argtypes = [c_void_p, c_int, c_char_p, c_int,
                                   POINTER(c_int)]

_libzfs.zpool_set_prop.argtypes = [c_void_p, c_char_p, c_char_p]


# zprop_source_t values:
ZPROP_SRC_NONE = 0x1
ZPROP_SRC_DEFAULT = 0x2
ZPROP_SRC_TEMPORARY = 0x4
ZPROP_SRC_LOCAL = 0x8
ZPROP_SRC_INHERITED = 0x10
ZPROP_SRC_RECEIVED = 0x20


ZFS_TYPE_FILESYSTEM = 1
ZFS_TYPE_SNAPSHOT = 2
ZFS_TYPE_VOLUME = 4
ZFS_TYPE_POOL = 8

# ZPOOL_PROP values:

(ZPOOL_PROP_NAME,
ZPOOL_PROP_SIZE,
ZPOOL_PROP_CAPACITY,
ZPOOL_PROP_ALTROOT,
ZPOOL_PROP_HEALTH,
ZPOOL_PROP_GUID,
ZPOOL_PROP_VERSION,
ZPOOL_PROP_BOOTFS,
ZPOOL_PROP_DELEGATION,
ZPOOL_PROP_AUTOREPLACE,
ZPOOL_PROP_CACHEFILE,
ZPOOL_PROP_FAILUREMODE,
ZPOOL_PROP_LISTSNAPS,
ZPOOL_PROP_AUTOEXPAND,
ZPOOL_PROP_DEDUPDITTO,
ZPOOL_PROP_DEDUPRATIO,
ZPOOL_PROP_FREE,
ZPOOL_PROP_ALLOCATED,
ZPOOL_PROP_READONLY) = range(19)


def libzfs_init():
        hdl = _libzfs.libzfs_init()
        if hdl is None:
                raise IOError(0, _msgs[LIBZFS_INIT_FAILURE])
        return c_void_p(hdl)


def libzfs_error_description(lzfsh):
        return _libzfs.libzfs_error_description(lzfsh)


def zfs_open(lzfsh, zfsname, type=ZFS_TYPE_FILESYSTEM):
        hdl = _libzfs.zfs_open(lzfsh, zfsname, type)
        if hdl is None:
                raise IOError(0, libzfs_error_description(lzfsh))
        return c_void_p(hdl)


def zfs_close(zfsh):
        _libzfs.zfs_close(zfsh)


def zfs_get_type(zfsh):
        return _libzfs.zfs_get_type(zfsh)


def zfs_get_name(zfsh):
        return _libzfs.zfs_get_name(zfsh)


def zfs_name_valid(beName, type):
        ret = _libzfs.zfs_name_valid(beName, type)
        return False if ret is 0 else True


def zpool_open(lzfsh, poolname):
        hdl = _libzfs.zpool_open(lzfsh, poolname)
        if hdl is None:
                raise IOError(0, libzfs_error_description(lzfsh))
        return c_void_p(hdl)


def zpool_close(zph):
        _libzfs.zpool_close(zph)


def zpool_get_physpath(lzfsh, zph):
        buf = create_string_buffer(MAX_PATH)
        ret = _libzfs.zpool_get_physpath(zph, buf, MAX_PATH)
        if not ret is 0:
                raise IOError(0, libzfs_error_description(lzfsh))
        return buf.value.split()


def zpool_get_prop(lzfsh, zph, propid, get_source=False):
        buf = create_string_buffer(LIBZFS_PROPLEN_MAX)
        if get_source is True:
                src = c_int()
                srcp = pointer(src)
        else:
                srcp = None

        ret = _libzfs.zpool_get_prop(zph, propid, buf, LIBZFS_PROPLEN_MAX,
                                     srcp)
        if not ret is 0:
                raise IOError(0, libzfs_error_description(lzfsh))
        if get_source is True:
                return [buf.value, src.value]
        else:
                return buf.value


def zpool_set_prop(zph, propname, propval):
        return _libzfs.zpool_set_prop(zph, propname, propval)


def libzfs_fini(handle):
        _libzfs.libzfs_fini(handle)


__all__ = ["statvfs",
           "mnttab_open",
           "mnttab_close",
           "getmntent",
           "getmntany",
           "getextmntent",
           "resetmnttab",
           "DI_MAKE_LINK",
           "DI_PRIMARY_LINK",
           "DI_SECONDARY_LINK",
           "DI_WALK_CONTINUE",
           "DI_WALK_TERMINATE",
           "di_devlink_init",
           "di_devlink_path",
           "di_devlink_walk",
           "di_devlink_fini",
           "DDI_NT_BLOCK",
           "DINFOPATH",
           "DINFOCPYALL",
           "di_init",
           "di_minor_is_block",
           "di_minor_name",
           "di_devfs_path",
           "di_minor_next",
           "di_walk_minor",
           "di_fini",
           "devfs_bootdev_get_list",
           "fstyp_init",
           "fstyp_ident",
           "fstyp_fini",
           "isalist",
           "platform_name",
           "machine_name",
           "ZFS_TYPE_FILESYSTEM",
           "ZFS_TYPE_POOL",
           "ZPOOL_PROP_BOOTFS",
           "libzfs_init",
           "libzfs_fini",
           "zfs_open",
           "zfs_close",
           "zpool_open",
           "zpool_close",
           "zfs_get_type",
           "zfs_get_name",
           "zfs_name_valid",
           "zpool_get_physpath",
           "zpool_get_prop",
           "zpool_set_prop"]
