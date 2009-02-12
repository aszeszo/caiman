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
from transfer_mod import tm_perform_transfer

execfile('/usr/lib/python2.4/vendor-packages/transfer_defs.py')

num_failed = 0

print "Testing valid src, dest. No skip files. should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_DST_MNTPT, '/test'),
    (TM_CPIO_SRC_MNTPT, '/lib')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

print "Testing valid src, dest. No skip files. should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

print "Testing invalid attribute. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_IPS_RETRIEVE, '/export/home/cpio_entire1'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid src. No skip files. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire2'),
    (TM_CPIO_SRC_MNTPT, '/usr/jean')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid dest. No skip files. should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_DST_MNTPT, '/export/home/missing'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing valid skip files. should PASS"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire3'),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, '/export/home/jeanm/transfer_mod_test/skip_files'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	print "PASSED"
else:
	num_failed += 1
	print "FAILED"

print "Testing invalid skip file. should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire4'),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, './skip_missing_files'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing invalid skip file file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire5'),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.image_info'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, '/export/home/jeanm/transfer_mod_test/skip_bad_file'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing image_info attribute. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire5'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, '/export/home/jeanm/transfer_mod_test/skip_bad_file'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing missing image_info file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire5'),
    (TM_ATTR_IMAGE_INFO, './.image_info'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, '/export/home/jeanm/transfer_mod_test/skip_bad_file'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

print "Testing badly formatted image info file. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_CPIO),
    (TM_CPIO_ACTION, TM_CPIO_ENTIRE),
    (TM_CPIO_DST_MNTPT, '/export/home/cpio_entire5'),
    (TM_ATTR_IMAGE_INFO, '/export/home/jeanm/transfer_mod_test/.bad_image_info'),
    (TM_CPIO_ENTIRE_SKIP_FILE_LIST, '/export/home/jeanm/transfer_mod_test/skip_bad_file'),
    (TM_CPIO_SRC_MNTPT, '/usr/sbin')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASSED"
else:
	print "FAILED"

if num_failed != 0:
        print "Check the results, %d tests did not perform as expected" % num_failed
else:
        print "Tests performed as expected"

