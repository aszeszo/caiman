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
Python packge with ctypes wrapper for libdiskmgt.so (undocumented).

TODO write a blurb about this.

This is how everything is related in libdiskmgt.so:

                               DMAlias        +--- DMPartition
  +---+                           |           |      |
  |   |                           |           |      |
  | DMBus --- DMController --- DMDrive --- DMMedia   |
  |   |            |              |           |      |
  +---+            |              |           |      |
                   +--- DMPath ---+           +--- DMSlice

This means if you have a DMBus object, you can use its
get_associated_descriptors() method to get to the DMController.

All DM* types are subclasses of DMDescriptor class.

All DM* types have attributes and stats property which return
objects derived from solaris_install.target.libnvpair.NVList
(NVList is dictionary like).
"""
