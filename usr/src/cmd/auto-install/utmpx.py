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

# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.

'''Python CTypes interface to utmpx methods.

Used to determine if someone is logged in to the console.
'''

import ctypes as C

_LIBC = C.CDLL("/usr/lib/libc.so", use_errno=True)

# Definitions for ut_type
UT_TYPE = (
    EMPTY,
    RUN_LVL,
    BOOT_TIME,
    OLD_TIME,
    NEW_TIME,
    INIT_PROCESS,
    LOGIN_PROCESS,
    USER_PROCESS,
    DEAD_PROCESS,
    ACCOUNTING,
    DOWN_TIME
) = xrange(11)


# Typedef the descriptor type.
class StructUtmpx(C.Structure):
    """ struct utmpx ctypes definition

        struct utmpx {
          char    ut_user[32];           /* user login name */
          char    ut_id[4];              /* inittab id */
          char    ut_line[32];           /* device name (console, lnxx) */
          pid_t   ut_pid;                /* process id */
          short   ut_type;               /* type of entry */
          struct ut_exit_status ut_exit; /* process termination/exit status */
          struct timeval ut_tv;          /* time entry was made */
          int     ut_session;            /* session ID, used for windowing */
          int     pad[5];                /* reserved for future use */
          short   ut_syslen;             /* significant length of ut_host */
                                         /*   including terminating null */
          char    ut_host[257];          /* remote host name */
        };
    """
    _fields_ = [
        ("ut_user",     C.c_char * 32),
        ("ut_id",       C.c_char * 4),
        ("ut_line",     C.c_char * 32),
        ("ut_pid",      C.c_uint),
        ("ut_type",     C.c_short),
        ("ut_exit",     C.c_short * 2),  # Shouldn't need it, so no need for
                                         # struct here just yet.
        ("ut_tv",       C.c_long * 2),   # or here either.
        ("ut_session",  C.c_int),
        ("pad",         C.c_int * 5),
        ("ut_syslen",   C.c_short),
        ("ut_host",     C.c_char * 257)
    ]

_FUNCS = [
    ("setutxent", None, None),
    ("endutxent", None, None),
    ("getutxent", C.POINTER(StructUtmpx), None),
    ("getutxid", C.POINTER(StructUtmpx), [C.POINTER(StructUtmpx)]),
    ("getutxline", C.POINTER(StructUtmpx), [C.POINTER(StructUtmpx)])
]

# update the namespace of this module
variables = vars()
for (function, restype, args) in _FUNCS:
    variables[function] = getattr(_LIBC, function)
    variables[function].restype = restype
    variables[function].argtypes = args


def users_on_console(print_entry=False):
    '''Check is there is any user logged in on the console'''
    setutxent()
    ret_val = False
    while True:
        entry = getutxent()
        try:
            # Just match on console or first VT.
            if entry.contents.ut_type == USER_PROCESS and \
               (entry.contents.ut_line.startswith("console") or \
                entry.contents.ut_line == "vt/1"):
                ret_val = True
                if print_entry:
                    print "%32s %4s %4s %32s" % (
                        str(entry.contents.ut_user),
                        str(entry.contents.ut_id),
                        str(entry.contents.ut_type),
                        str(entry.contents.ut_line))
        except ValueError:  # Catch NULL reference
            break
    endutxent()

    return ret_val

if __name__ == '__main__':
    users_on_console(True)
