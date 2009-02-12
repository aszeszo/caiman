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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
from libtransfer import *
from transfer_mod import tm_perform_transfer

execfile('/usr/lib/python2.4/vendor-packages/transfer_defs.py')
num_failed = 0

print "Testing valid src, dest, and file.  should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

print "Testing missing TM_CPIO_ACTION, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_CPIO_LIST_FILE, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_CPIO_DST_MNTPT, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing TM_CPIO_SRC_MNTPT, should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid attribute. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_IPS_INIT, '/export/home/cpio_entire1'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"


print "Testing invalid src. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire2'),
    (TM_CPIO_SRC_MNTPT, '/usr/jean')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid dst. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/missing'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, './file_missing_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire3'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing file with bad file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_LIST),
    (TM_CPIO_LIST_FILE, '/export/home/jeanm/transfer_mod_test/file_bad_list'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire3'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

if num_failed != 0:
	print "Check your results %d tests did not perform as expected" % num_failed
else:
	print "Tests performed as expected"
