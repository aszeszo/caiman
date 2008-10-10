#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License (the "License").
# You may not use this file except in compliance with the License.
#
# You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
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
# Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/export/ws/dwarf/src/common/lib/liborchestrator/pics/sparc:/export/ws/dwarf/src/common/lib/libtd/pics/sparc:/export/ws/dwarf/proto/usr/snadm/lib

export LD_LIBRARY_PATH

cc -xc99=%none -g -xildoff -Xa -I/export/ws/dwarf/proto/usr/include -I/usr/include -I. -c -o om_kbd_locale_test.o om_kbd_locale_test.c

cc -xc99=%none -g -xildoff -Xa -I/export/ws/dwarf/proto/usr/include -I/usr/include -I. -g -xildoff -R/usr/sfw/lib -R/usr/snadm/lib -L/export/ws/dwarf/src/common/lib/libtd/pics/sparc -L/usr/sfw/lib -L/export/ws/dwarf/src/common/lib/liborchestrator/pics/sparc -o om_kbd_locale_test om_kbd_locale_test.o -lorchestrator -ltd  -ldiskmgt -lnvpair -ldl -ldevinfo -ladm -linstzones -lzonecfg -lzoneinfo -lcontract -lwanboot
