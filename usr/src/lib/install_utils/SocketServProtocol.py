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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.

# =============================================================================
# =============================================================================
"""
SocketServProtocol.py: Public definitions for Socket Server protocol.
"""
# =============================================================================
# =============================================================================

# To initiate contact with the server, client sends prerequest with two fields:
#	byte 0: "0"= not key, "1" = key
#	byte 1 blank
#	bytes 2:PRE_REQ_SIZE: size of the request string.

PRE_REQ_SIZE = 8

# Next, server sends PRE_REQ_ACK.  Then client can send the request.

PRE_REQ_ACK = '\001'

# REQ_COMPLETE is sent by server as a final "string" of a
# request to note that the request (which can consist of many
# strings) has been completed

REQ_COMPLETE = '\002'
	
# EMPTY_STR is sent instead of an empty string, when an empty string
# would be returned as part of a request.  This allows clients to use
# split() on the results string, and to still be able to differentiate
# between a true empty string returned from the server vs an empty
# string which could be returned by split() if the split character is
# at the end of the string being split.

EMPTY_STR = '\003'
#
# RECV_PARAMS_RECVD is sent by the client after it gets the count (of
# strings being returned to fulfill a request) and size of total
# results string from the server.  The count and size is sent by the
# server as the first response to a request.  It is of the form
# "count,size"  The server waits for RECV_PARAMS_RECVD before initiating
# the sending of the strings of the request.  If the count of strings is
# zero, the server waits for the next request, and the client expects
# nothing more from the current request.
#
RECV_PARAMS_RECVD = '\004'
#
# TERM_LINK is sent by the client to terminate the socket link, after
# all requests are done.
# 
TERM_LINK = '\005'
#
# String separator, placed between results in the string.
#
STRING_SEP = '\0'
#
# Protocol is as follows:
# Client->server: Prerequest containing is_key and request size is sent.
# Server->client: Sends PRE_REQ_ACK back to the client.
# Client->server: Request in the form of a nodepath is sent.
# Server->client: Send count of matching nodes, and the size of the
#	entire results string (which includes all results).
# Client->server: RECV_PARAMS_RECVD
# Server->client: Send strings of matching node values as a single
#	string with STRING_SEP in between each.  Send EMPTY_STR instead
#	of empty strings, when applicable.  Last string (which is at the
#	index = one more than the count returned to the client) is
#	REQ_COMPLETE
# Client->server: Another request, or TERM_LINK is sent.
# 
# - - - - -
#
# The manifest schema defines the path to key/value pairs.
# Both the client and server have methods which can translate a key into the
# right nodepath to fetch that key's value(s) from the manifest.  KEY_PATH is
# the string used to convert a key into the nodepath.

# Note: This path will work when the key_value_pairs section of the manifest
# is defined just below the root level of the tree like this:
# <root>
#	<key_value_pairs>
#		<pair key="keystring1" value="valuestring1">
#		<pair key="keystring2" value="valuestring2">
#	</key_value_pairs>
#
KEY_PATH = "key_value_pairs/pair[key=%s]/value"
