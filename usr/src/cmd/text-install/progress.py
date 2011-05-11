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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

import random
import socket
import struct
import sys
import thread
import time

from select import select

from solaris_install.logger import ProgressHandler

''' Progress handler for the text installer '''


class InstallProgressHandler(ProgressHandler):
    """ Server and message receiver functionality for the ProgressHandler. """

    def __init__(self, logger, hostname="localhost", portno=None):

        self.server_up = False
        self.logger = logger
        self.hostname = hostname
        self.engine_skt = None
        self.msg_buf = ""

        # Get a port number
        self.skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if portno is not None:
            self.portno = portno
            try:
                self.skt.bind((self.hostname, self.portno))
                self.skt.listen(5)
            except socket.error:
                self.logger.exception("InstallProgresHandler init failed.")
                return None
        else:
            random.seed()
            # Continue looping until skt.listen(5) does not cause socket.error
            while True:
                try:
                    self.portno = random.randint(10000, 30000)
                    self.skt.bind((self.hostname, self.portno))
                    self.skt.listen(5)
                    break
                except socket.error:
                    self.skt.close()
                    self.skt = None

        ProgressHandler.__init__(self, self.hostname, self.portno)

    def startProgressServer(self, cb=None):
        """ Starts the socket server stream to receive progress messages. """

        if not self.server_up:
            self.server_up = True
            self.engine_skt, address = self.skt.accept()
            if cb is not None:
                thread.start_new_thread(self.progressServer, (cb, ))
            time.sleep(1)

    def stopProgressServer(self):
        """ Stop the socket server stream. """
        if self.server_up:
            self.server_up = False

    def progressServer(self, cb):
        """ Actual spawned progressServer process. """
        try:
            while self.server_up:
                ready_to_read = select([self.engine_skt], [], [], 0.25)[0]
                if len(ready_to_read) > 0:
                    percentage, mssg = self.parseProgressMsg( \
                        ready_to_read[0], cb)
            self.engine_skt.close()
        except Exception:
            self.logger.exception("progressServer Error")
 
    def get_one_message(self):

        self.logger.debug("1-msg: %s", self.msg_buf)
        if len(self.msg_buf) > 4:
            # Something is available to be processed.  Try to process it.
            size = struct.unpack('@i', self.msg_buf[:4])[0]
            self.logger.debug("size of message expected: %s", size)

            # does the buffer have enough data?
            if len(self.msg_buf[4:]) >= size:
                msg = self.msg_buf[4:4 + size]
                self.msg_buf = self.msg_buf[(4 + size):]
                self.logger.debug("message: %s", msg)
                self.logger.debug("msg_buf: %s", self.msg_buf)
                return msg
            else:
                return None
        else:
            return None

    def parseProgressMsg(self, skt, cb=None):
        """Parse the messages sent by the client."""
        recv_size = 8192
        percent = None
        msg = None

        message = self.get_one_message()
        self.logger.debug("step 1: message: %s", message)
        while not message:
            try:
                sock_data = skt.recv(recv_size)
            except:
                pass

            self.logger.debug("sock: %s", sock_data)
            self.msg_buf += sock_data
            self.logger.debug("after sock: %s", self.msg_buf)
            message = self.get_one_message()
            self.logger.debug("step 2: message: %s", message)

        self.logger.debug("parseProgressMsg: %s", message)
        if cb:
            cb(message)

        percent, msg = message.split(' ', 1)
        return percent, msg
     
    def progressReceiver(self, msg):
        print "%s" % (msg)
