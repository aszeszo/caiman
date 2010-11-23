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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
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
    
    def __init__(self, address=None):
        if address is not None:
            address = IPAddress.convert_address(address)
        self._address = address
    
    def __str__(self):
        return self.get_address()
    
    def get_address(self):
        '''Returns this IP address as a string'''
        segments = []
        for segment in self._address:
            segments.append(str(segment))
        return ".".join(segments)
    
    def set_address(self, address):
        '''Sets this IPAddress' address'''
        if address is not None:
            address = IPAddress.convert_address(address)
        self._address = address
    
    address = property(get_address, set_address)
    
    @staticmethod
    def convert_address(address):
        '''Convert a string into an array of ints. Also serves as a
        validation function - strings not of the correct form will raise
        a ValueError
        
        '''
        segments = IPAddress.incremental_check(address)
        if len(segments) != 4:
            raise ValueError("Bad length")
        return segments
    
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
