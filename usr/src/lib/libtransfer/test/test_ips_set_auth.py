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
from transfer_mod import *

execfile('./transfer_defs.py')
num_failed = 0

print "Testing valid alt-auth, valid mountpoint. Should PASS"
tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_AUTH, 'http://indiana-build.central:10000'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REFRESH),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	print "PASS"
else:
	num_failed += 1
	print "FAIL"

print "Testing missing TM_IPS_ALT_AUTH. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_INIT_MNTPT, '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

print "Testing missing TM_IPS_INIT_MNTPT. Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_AUTH, 'http://indiana-build.central:10000')]) 
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

print "Testing invalid attribute, Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_AUTH, 'http://indiana-build.central:10000'),
	    ("tm_in", '/export/home/test1')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

print "Testing invalid alt-auth, Should FAIL"
tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_AUTH, 'http://jean:10000'),
	    (TM_IPS_INIT_MNTPT, '/export/home/test2')])
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REFRESH),
	    (TM_IPS_INIT_MNTPT, '/export/home/test2')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

print "Testing invalid mountpoint , Should FAIL"
status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_AUTH, 'http://ipkg.sfbay:29047'),
	    (TM_IPS_INIT_MNTPT, '/export/home/testZ')])
if status == TM_E_SUCCESS:
	num_failed += 1
	print "PASS"
else:
	print "FAIL"

if num_failed != 0:
	print "Check your results %d tests didn't perform as expected" % num_failed
else:
	print "Tests performed as expected"
