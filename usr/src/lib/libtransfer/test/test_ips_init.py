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
from transfer_mod import tm_perform_transfer

execfile('/usr/lib/python2.4/vendor-packages/transfer_defs.py')

num_failed=0

# Test valid server, valid mountpoint, default type
print "Testing valid server, valid mountpoint, default type should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

print "Testing invalid TM_ATTR_MECHANISM, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_IPS_INIT),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid TM_IPS_ACTION, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, "help"),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

# Test valid server, valid mountpoint, type = user 
print "Testing valid server, valid mountpoint, type user should PASS"

status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_USER),
    (TM_IPS_INIT_MNTPT, '/export/home/test2')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

# Test valid server, valid mountpoint, type = partial 
print "Testing valid server, valid mountpoint, type partial should PASS"

status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_PARTIAL),
    (TM_IPS_INIT_MNTPT, '/export/home/test3')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

# Test valid server, valid mountpoint, type = full 
print "Testing valid server, valid mountpoint, type full should PASS"

status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test4')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

# Test valid server, valid mountpoint, invalid type 
print "Testing valid server, valid mountpoint, invalid type, should FAIL"

status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, "Z"),
    (TM_IPS_INIT_MNTPT, '/export/home/test5')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

# Test invalid server, valid mountpoint, type = full 
print "Testing invalid server, valid mountpoint, type full should FAIL"

status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:20047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

# Test invalid attribute 
print "Testing invalid attribute should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    ("tm_ips_a", TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_ATTR_MECHANISM should FAIL"
status = tm_perform_transfer([
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_IPS_ACTION, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_IPS_PKG_SERVER, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"


print "Testing missing TM_IPS_INIT_MNTPT, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_IMAGE_TYPE, TM_IPS_IMAGE_FULL)])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"


print "Testing missing TM_IPS_IMAGE_TYPE, should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
    (TM_IPS_ACTION, TM_IPS_INIT),
    (TM_IPS_PKG_SERVER, 'http://ipkg.sfbay:29047'),
    (TM_IPS_INIT_MNTPT, '/export/home/test6')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

if num_failed != 0:
	print "Check the results, %d tests did not perform as expected" % num_failed
else:
	print "Tests performed as expected"
