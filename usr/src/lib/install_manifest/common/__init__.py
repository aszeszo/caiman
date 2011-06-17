#!/usr/bin/python
#
##
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

"""init module for ManifestParser and ManifestWriter"""

import sys

from lxml import etree


class ManifestError(Exception):
    '''
        Raised if an error occurs during ManifestParser or ManifestWriter.

        Instances of this class have the following attributes:
        - msg (mandatory), a text string
        - orig_exception (optional), another Exception object
          This attribute is used to encapsulate another exception
    '''

    def __init__(self, msg, orig_exception=None):
        Exception.__init__(self)
        self.msg = msg
        self.orig_exception = orig_exception
        self.orig_traceback = sys.exc_info()[2]

    def __str__(self):
        msg = self.msg

        if self.orig_exception is not None:
            # Return a useful message that includes the original msg,
            # the name of the encapsulated exception's class (eg
            # "IOError" or "XMLSyntaxError") and the the msg from
            # the encapsulated exception.
            msg = "%s: %s - %s" % (msg,
                self.orig_exception.__class__.__name__,
                self.orig_exception)

        return msg


def validate_manifest(tree, dtd_file, logger):
    '''
        Validates the given XML tree against the given DTD.

        This is a common function used by ManifestParser and ManifestWriter.

        Parameters:
        - tree, an etree.ElementTree
        - dtd_file, the path to a DTD file
        - logger, where to log errors to

        Returns:
        - Nothing
          On success, this method returns; on error it raises an exception.

        Raises:
        - ManifestError is raised if the DTD file cannot be loaded,
          or if validation fails.
    '''

    try:
        dtd = etree.DTD(dtd_file)
    except etree.DTDParseError, error:
        msg = "Unable to parse DTD file [%s]:" % (dtd_file)
        logger.exception(msg)
        logger.exception(str(error))
        raise ManifestError(msg, orig_exception=error)

    if not dtd.validate(tree.getroot()):
        msg = "Validation against DTD [%s] failed" % (dtd_file)
        logger.error(msg)

        for error in dtd.error_log.filter_from_errors():
            logger.error(str(error))
            msg = msg + " : " + str(error)

        raise ManifestError(msg)


__all__ = ["parser", "writer"]
