#!/usr/bin/python2.6
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

'''Contains the get_console() function and the values it returns.
DO NOT put any other code in this file.  We do not
want to create any other dependencies.  This file will be
imported as the very first thing for text installer and sysconfig tool to
determine whether the system is running from a physical console or not
so the appropriate locale information can be setup.

'''


import array
import fcntl
import struct

PHYSICAL_CONSOLE = "Physical Console"
SERIAL_CONSOLE = "Serial Console"
UNKNOWN_CONSOLE = "Unknown Console"


def get_console():
    prom_device = "/dev/openprom"

    # the following OPROM ioctl codes are taken from
    # /usr/include/sys/openpromio.h

    oioc = ord('O') << 8

    # OPROMGETCONS
    opromgetcons = oioc | 10

    # OPROMCONS_STDIN_IS_KBD: stdin device is kbd
    opromcons_stdin_is_kbd = 0x1  

    # OPROMCONS_STDOUT_IS_FB: stdout is a framebuffer
    opromcons_stdout_is_fb = 0x2  

    try:
        with open(prom_device, "r") as prom:

            # Set up a mutable array for ioctl to read from and write
            # to. Standard Python objects are not usable here.
            # fcntl.ioctl requires a mutable buffer pre-packed with the
            # correct values (as determined by the device-driver).
            # In this case,openprom(7D) describes the following C
            # stucture as defined in <sys.openpromio.h>
            # struct openpromio {
            #     uint_t  oprom_size; /* real size of following data */
            #     union {
            #         char  b[1];  /* NB: Adjacent, Null terminated */
            #         int   i;
            #     } opio_u;
            # };

            value = '\0'
            buf = array.array('c', struct.pack('Ic', 1, value))

            # use ioctl to query the prom device.
            fcntl.ioctl(prom, opromgetcons, buf, True)

            # Unpack the mutable array, buf, which ioctl just wrote into.
            new_oprom_size, new_value = struct.unpack('Ic', buf)

            new_value_hex = ord(new_value)
            if (new_value_hex & opromcons_stdin_is_kbd) and \
                (new_value_hex & opromcons_stdout_is_fb):
                return PHYSICAL_CONSOLE
            else:
                return SERIAL_CONSOLE
    except:
        return UNKNOWN_CONSOLE

if __name__ == '__main__':
    print "Running from " + get_console()
