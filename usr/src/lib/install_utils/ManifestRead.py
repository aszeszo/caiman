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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#

# =============================================================================
# =============================================================================
"""
ManifestRead.py - Remote (AF-UNIX socket-based) XML data access
                  interface module
"""
# =============================================================================
# =============================================================================

import errno
import sys
import socket

import osol_install.SocketServProtocol as SocketServProtocol


# =============================================================================
class ManifestRead(object):
# =============================================================================
    """ Client interface class for retrieving data across socket interface.

    Socket server is an instance of the ManifestServ class.

    Intent is for shell scripts and python programs to be able to retrieve
    XML manifest data.  This class provides mechanism for shell scripts to
    run a program that prints the results, and for python programs to
    retrieve results in a python list.

    """
# =============================================================================

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, sock_name):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor.

        Takes the name of a socket, created by the ManifestServ process.
        The socket remains open as long as this instance is intact.

        Args:
          sock_name: String name of the socket.

        Raises:
          Exceptions for:
            Error creating listener socket
            Error connecting to listener socket

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.debug = False
        try:
            self.client_sock = socket.socket(socket.AF_UNIX,
                                             socket.SOCK_STREAM)
        except socket.error:
            print >> sys.stderr, ("Error creating listener socket " +
                                  sock_name)
            raise

        try:
            self.client_sock.connect(sock_name)
        except socket.error:
            print >> sys.stderr, ("Error connecting to listener socket " +
                                  sock_name)
            raise

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __del__(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Destructor.

        Sends termination protocol to server, and closes the socket

        Args: None

        Returns: None

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        try:
            self.client_sock.send(SocketServProtocol.TERM_LINK)
            self.client_sock.close()
        except socket.error:
            pass

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_values(self, request, is_key=False):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Retrieve a list of values given a request.

        Args:
          request: Nodepath, the found nodes of which values are to be
            retrieved.

          is_key: boolean: if True, the request is interpreted as a key
            in the key_value_pairs section of the manifest.  In this
            case, the proper nodepath will be generated from the
            request and submitted.  If false, the request is
            submitted for searching as provided.

        Returns:
          A list of values which match the request.  Note that if the
            request matches multiple nodes, there won't be a way to
            distinguish which results came from which nodes.  If
            this matters, then refine the request to zoom in on a
            particular node.

        Raises:
            Exceptions due to socket errors.

            (For protocol errors, however, it prints a message and tries
            to muddle along.)

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        results_list = []

        # Specify key and request size in pre_request string.
        # Pre_request string must be SocketServProtocol.PRE_REQ_SIZE
        # bytes total.
        if (is_key):
            pre_request = "1"
        else:
            pre_request = "0"
        pre_request += " "
        pre_request += "%6.6d" % len(request)

        # Sending the pre-request
        if (self.debug):
            print "Sending pre-request: " + pre_request
        try:
            self.client_sock.send(pre_request)
        except socket.error:
            print >> sys.stderr, ("Error sending pre-request to server")
            raise

        # Wait for server to return the pre-request acknowledge
        try:
            pre_req_ack = self.client_sock.recv(1)
        except socket.error:
            print >> sys.stderr, ("Protocol error: Did not " +
                                  "receive pre_request acknowledge.")
            raise

        if (pre_req_ack[0] != SocketServProtocol.PRE_REQ_ACK):
            raise socket.error, (errno.EPROTO, "Protocol error: " +
                                 "pre_request acknowledge is incorrect")

        # Send the request
        if (self.debug):
            print "Sending request: " + request
        try:
            self.client_sock.send(request)
        except socket.error:
            print >> sys.stderr, "Error sending request to server"
            raise

        # Wait for server to return the result count and size first.
        try:
            count_size_list = self.client_sock.recv(1024).split(",")
            count = int(count_size_list[0])
            size = int(count_size_list[1])
        except (socket.error, IndexError, ValueError):
            print >> sys.stderr, ("Protocol error: Did not receive request " +
                                  "count and size.")
            raise

        # Acknowledge to server the receipt of count and size.
        try:
            self.client_sock.send(SocketServProtocol.RECV_PARAMS_RECVD)
        except socket.error:
            print >> sys.stderr, "Error sending params-rcvd message to server"
            raise

        if (self.debug):
            print "Receiving %d results..." % (count)

        # No results.  Done with this transaction.
        if (count == 0):
            return results_list

        results = ""
        size_to_recv = size
        try:
            while (size_to_recv > 0): 
                results += self.client_sock.recv(size_to_recv)
                size_to_recv = size - len(results)
        except socket.error:
            print >> sys.stderr, ("Error receiving results from server")
            raise
        results = results.split(SocketServProtocol.STRING_SEP)

        # Note that the final list element is REQ_COMPLETE and is
        # discarded.  Note also that count doesn't include it, so it
        # will be one less than the actual number of results returned.
        results_list = []
        for i in range(count):
            if (results[i][0] != SocketServProtocol.EMPTY_STR):
                results_list.append(results[i])
            else:
                if (self.debug):
                    print "(empty string)"
                results_list.append("")

        # Last result should be REQ_COMPLETE.
        if (results[count] != SocketServProtocol.REQ_COMPLETE):
            print >> sys.stderr, ("Protocol error: " +
                                  "Improper request termination.")
        elif (self.debug):
            print "Proper Termination protocol seen"

        return results_list

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_debug(self, on_off):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Enable debug messages

        Args:
          on_off: boolean: Enable messages when True.
            Messages are disabled upon object instantiation.

        Returns: None

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.debug = on_off
