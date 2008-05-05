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
#

cc -xc99=%none -g -xildoff -Xa -I/home/sy25831/ws/caiman/dwarf/root.i386/usr/include -I/usr/include -I. -I../liblogsvc -Di386 -c -o test_driver.o test_driver.c
cc -xc99=%none -g -xildoff -Xa -I/home/sy25831/ws/caiman/dwarf/root.i386/usr/include -I/usr/include -I. -I../liblogsvc -Di386 -c -o om_disk_test.o om_disk_test.c

cc -xc99=%none -g -xildoff -Xa -I/home/sy25831/ws/caiman/dwarf/root.i386/usr/include -I/usr/include -I. -g -xildoff -R/usr/sfw/lib -R/usr/snadm/lib -R. -L/home/sy25831/ws/caiman/dwarf/root.i386/usr/snadm/lib -L/usr/sfw/lib -L. -L../libtd -o om_disk_test om_disk_test.o test_driver.o -lorchestrator -lnvpair

cc -xc99=%none -g -xildoff -Xa -I/home/sy25831/ws/caiman/dwarf/root.i386/usr/include -I/usr/include -I. -I../liblogsvc -Di386 -c -o om_kbd_locale_test.o om_kbd_locale_test.c

cc -xc99=%none -g -xildoff -Xa -I/home/sy25831/ws/caiman/dwarf/root.i386/usr/include -I/usr/include -I. -g -xildoff -R/usr/sfw/lib -R/usr/snadm/lib -R. -L/home/sy25831/ws/caiman/dwarf/root.i386/usr/snadm/lib -L/usr/sfw/lib -L. -L../libtd -o om_kbd_locale_test om_kbd_locale_test.o -Bdynamic -lorchestrator 

cc -o dummy_install -I. -I../liblogsvc dummy_install.c
