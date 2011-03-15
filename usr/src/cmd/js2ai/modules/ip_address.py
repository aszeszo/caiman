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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
Class representing IP Addresses
'''


class IPAddress(object):
    '''Simple class to represent IP addresses

    This implementation represents purely the IP. Netmask, if needed,
    should be represented by a second IPAddress.

    '''

    DEFAULT = "0.0.0.0"

    def __init__(self, address=None, netmask=None):
        self._address = None
        self._netmask = None

        self.address = address
        self.netmask = netmask

    def __str__(self):
        return self.get_address()

    def get_address(self):
        '''Returns this IP address as a string'''
        segments = []
        if self._address is None:
            address = IPAddress.DEFAULT
        else:
            for segment in self._address:
                segments.append(str(segment))
            address = ".".join(segments)
        if self._netmask:
            netmask = "/" + str(self.shorthand_netmask())
            return address + netmask
        else:
            return address

    def set_address(self, address):
        '''Sets this IPAddress' address'''
        if address is not None:
            address = IPAddress.convert_address(address)
        self._address = address

    address = property(get_address, set_address)

    @property
    def netmask(self):
        """Get netmask"""
        return self._netmask

    @netmask.setter
    def netmask(self, new_mask):
        """Set netmask"""
        if new_mask is not None:
            new_mask = str(new_mask)
            new_mask = IPAddress.convert_address(new_mask, check_netmask=True)

        self._netmask = new_mask

    @staticmethod
    def convert_address(address, check_netmask=False):
        '''Convert a string into an array of ints. Also serves as a
        validation function - strings not of the correct form will raise
        a ValueError

        '''
        segments = IPAddress.incremental_check(address)
        if len(segments) != 4:
            raise ValueError("Bad length")
        if check_netmask:
            bin_rep = IPAddress.as_binary_string(segments)
            if "1" in bin_rep.lstrip("1"):
                raise ValueError("Not a valid netmask")
        return segments

    @staticmethod
    def as_binary_string(segments):
        '''Convert a set of 4 octets into its binary string representation
        For example, 255.255.255.0 becomes:
        11111111 11111111 11111111 00000000
        (without the spaces)

        '''
        return "".join([bin(x)[2:] for x in segments])

    def shorthand_netmask(self):
        '''Convert a long form netmask into a short form (CIDR).
        e.g. 255.255.255.0 -> /24
        The returned value is undefined for IPAddress's not representing
        valid netmasks.

        '''
        binary_rep = IPAddress.as_binary_string(self._netmask)
        return binary_rep.count("1")

    @staticmethod
    def incremental_check(address):
        '''Incrementally check an IP Address. Useful for checking a partial
        address, e.g., one that is partly typed into the UI

        '''
        ip = address.split(".")
        segments = []
        if len(ip) > 4:
            raise ValueError("Too many octets")
        for segment in ip:
            if not segment:
                continue
            int_seg = int(segment)
            if int_seg < 0 or int_seg > 255:
                raise ValueError("Values should be between 0 and 255")
            else:
                segments.append(int_seg)
        return segments
