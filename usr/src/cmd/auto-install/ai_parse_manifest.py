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
#
""" ai_parse_manifest.py - AI XML manifest parser
"""

from osol_install.ManifestServ import ManifestServ

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_create_manifestserv(manifest_file):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """
        Create an unvalidated manifest object.

        Args:
          manifest_file: file containing the data to read into memory.

        Returns
            ManifestServ object on success
            None on error

        Raises: None
    """

    try:
        manifest_obj = ManifestServ(manifest_file, full_init=False)
    except StandardError, err:
        print "Error creating in-memory copy of Manifest data."
        print str(err)
        return None

    return manifest_obj


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_setup_manifestserv(manifest_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """
        Validates a manifest server object

        Args:
	  manifest_server_obj: ManifestServ object containing data to validate.

        Returns: 0 on success, -1 on error

        Raises: None
    """

    try:
        manifest_obj.schema_validate()
        manifest_obj.semantic_validate()
        return 0

    except StandardError, err:
        print "Error setting up manifest data for use"
        print str(err)
        return -1


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_lookup_manifest_values(manifest_server_obj, path):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Read and return all values of the path specified.

	Args:
	    manifest_server_obj: ManifestServ object
	    path: nodepath to find values for

	Returns:
            A list of strings found at the nodepath given.
	    None: if no value is found

	Raises:
	    ParserError: Error generated while parsing the nodepath
	"""

    node_list = manifest_server_obj.get_values(path, False)
    if (len(node_list) > 0):
        return (node_list)
    return None
