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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''ManifestParser/ManifestWriter test common module'''

import os

TEST_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MANIFEST_DC = "%s/manifests/manifest_simple.xml" % TEST_BASE_DIR
MANIFEST_DC_DTD_PATH = "%s/manifests/manifest_simple_dtd_path.xml" % TEST_BASE_DIR
MANIFEST_NO_DTD_REF = "%s/manifests/manifest_no_dtd_ref.xml" % TEST_BASE_DIR
MANIFEST_XINCLUDE = "%s/manifests/manifest_xinclude_main.xml" % TEST_BASE_DIR
MANIFEST_INVALID = "%s/manifests/manifest_invalid.xml" % TEST_BASE_DIR
MANIFEST_PARSE_ERROR = "%s/manifests/manifest_parse_error.xml" % TEST_BASE_DIR
MANIFEST_SYNTAX_ERROR = "%s/manifests/manifest_syntax_error.xml" % TEST_BASE_DIR
MANIFEST_NON_EXISTENT = "non/existent/dir/manifest.dtd"

MANIFEST_OUT_OK = "/tmp/test_manifest_writer_01.xml"
MANIFEST_OUT_NON_EXISTENT = "non/existent/dir/test_manifest_writer_01.xml"

DTD_DC = "%s/manifests/manifest.dtd" % TEST_BASE_DIR
DTD_INVALID = "/etc/release"
DTD_INVALID_2 = "/tmp"
DTD_NON_EXISTENT = "non/existent/dir/manifest.dtd"

XSLT_DOC_TO_DC = "%s/manifests/doc-to-manifest.xslt" % TEST_BASE_DIR
XSLT_INVALID = "/etc/release"
XSLT_NON_EXISTENT = "non/existent/dir/file.xslt"


def file_line_matches(filename, lineno, string):
    '''
        Returns True if line number 'lineno' of file 'filename'
        matches the string 'string'.  Returns False if file
        cannot be read, does not contain enough lines or if
        the text doesn't match.

        lineno is the line number within the file, starting at 0.
        If lineno is a negative number it is taken to indicate a
        number of lines from the end of the file, where -1 indicates
        the last line of the file, -2 indicates the second last
        line, etc.

        Examples:
        file_line_matches(filename, 0, string)  # match first line of file
        file_line_matches(filename, -1, string) # match last line of file

    '''

    try:
        file_obj = open(filename)
        # read in entire file
        lines = file_obj.readlines()
    except IOError:
        return False
    finally:
        file_obj.close()

    try:
        line = lines[lineno].strip()
    except IndexError:
        return False

    return (line == string) 
