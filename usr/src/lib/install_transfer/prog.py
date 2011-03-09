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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''Progress monitor for the transfer checkpoint'''
import os
import time
import threading


class ProgressMon(object):
    '''The ProgressMon class contains methods to monitor the
       progress of the transfer.
    '''
    def __init__(self, distrosize=0, initpct=0, endpct=0, done=0, logger=None,
                 sleep_for=.5):
        self.distrosize = distrosize
        self.initpct = initpct
        self.endpct = endpct
        self.done = done
        self.logger = logger
        self.sleep_for = sleep_for
        self.thread1 = None

    def startmonitor(self, filesys, distrosize, initpct=0, endpct=100):
        '''Start a thread to monitor the progress populating a file system.
           Input: filesys - file system to monitor
                  distrosize - full distro size in kilobytes
                  initpct - base percent value from which to start calculating
                  endpct - percentage value at which to stop calculating
        '''
        self.distrosize = distrosize
        self.initpct = initpct
        self.endpct = endpct
        self.done = False
        self.thread1 = threading.Thread(target=self.__progressthread,
                                        args=(filesys, ))
        self.thread1.start()

    def wait(self):
        '''Wait until the thread whose join() method is called terminates.'''
        self.thread1.join()

    def __fssize(self, filesystem):
        '''Find the current size of the specified file system.
           Input: filesystem  - filesystem to find size of.
           Returns: size of the filesystem in kilobytes.
        '''
        try:
            stat = os.statvfs(filesystem)
            return ((stat.f_blocks - stat.f_bfree) * stat.f_frsize) / 1024
        except OSError, msg:
            # The file system hasn't been created yet
            pass

    def __progressthread(self, filesystem):
        '''Monitor the progress in populating the file system.
           Input: filesystem - the file system to monitor
        '''
        initsize = None

        while initsize is None:
            initsize = self.__fssize(filesystem)

        totpct = self.endpct - self.initpct
        prevpct = -1

        # Loop until the user aborts or we're done transferring.
        # Keep track of the percentage done and lets the user know
        # how far the transfer has progressed.
        while True:
            # Compute increase in filesystem size
            fssz = self.__fssize(filesystem)
            if fssz is None:
                continue
            fsgain = fssz - initsize

            # Compute percentage transferred
            actualpct = fsgain * 100 / self.distrosize

            # Compute the percentage transfer in terms of the perc range.
            pct = fsgain * totpct / self.distrosize + self.initpct

            # Do not exceed the limit.
            if pct >= self.endpct or actualpct > 100:
                pct = self.endpct

            # If the percentage has changed at all, log the progress
            if pct != prevpct:
                self.logger.report_progress("Transferring contents", int(pct))
                prevpct = pct

            if pct >= self.endpct or self.done:
                return
            time.sleep(self.sleep_for)
