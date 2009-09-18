#!/usr/bin/python2.4
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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
from libtransfer import *
from transfer_mod import *
execfile('./transfer_defs.py')
num_failed = 0

# Test valid server, pkg file, and mntpt. Should PASS
print "Testing valid server, pkg file and mntpt. Should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, '/export/home/jeanm/transfer_mod_test/pkg_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test2')])
if status == TM_E_SUCCESS:
	print "PASS"
else:
	num_failed += 1
	print "FAIL"

# Test missing TM_IPS_PKG_SERVER, should FAIL
print "Testing missing TM_IPS_PKG_SERVER. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKGS, './pkg_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test missing TM_IPS_PKGS, should FAIL
print "Testing missing TM_IPS_PKGS. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test missing TM_IPS_INIT_MNTPT, should FAIL
print "Testing missing TM_IPS_INIT_MNTPT. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, './pkg_file.txt')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test invalid server, valid pkg file, and valid mntpt. Should FAIL 
print "Testing invalid server. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:20047'),
	    (TM_IPS_PKGS, './pkg_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test valid server, invalid pkg file, and valid mntpt. Should FAIL 
print "Testing invalid pkg file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, './pkg_f.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test valid server, valid pkg file, and invalid mntpt. Should FAIL 
print "Testing invalid mntpt. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, './pkg_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/testZ')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test valid server, valid pkg file, and valid mntpt. Pkg not there. Should FAIL
print "Testing pkg not there.  Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, './pkg_missing_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

# Test invalid attributes. Should FAIL 
print "Testing invalid attributes.  Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_CONTENTS_VERIFY),
	    ("tm_help", 'http://ipkg.sfbay:29047'),
	    (TM_IPS_PKGS, './pkg_file.txt'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"


if num_failed != 0:
	print "Check the results %d tests didn't perform as expected" % num_failed
else:
	print "Tests performed as expected"
