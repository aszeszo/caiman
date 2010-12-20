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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

""" testlib.py - library containing common testing functions needed for testing
DC
"""

import os
import os.path
import tempfile

from lxml import etree


def create_filesystem(*args):
    """ create_filesystem - function to create a dummy filesystem in /var/tmp

    *args - a list of specific files to create inside the filesystem

    create_filesystem(*["/etc/foo", "/etc/bar/fleeb"]) will create a filesystem
    with those two files in it.  if empty directories are wanted, append a
    slash to the end of the specific path:  /etc/, /lib/amd64/, etc
    """
    # get a temporary directory
    tdir = tempfile.mkdtemp(dir="/var/tmp", prefix="dc_test_")

    # walk each entry in args and create the files and directories as needed
    for arg in args:
        # strip the leading slash
        arg = arg.lstrip("/")

        # check for a directory entry
        if arg.endswith("/"):
            if not os.path.exists(os.path.join(tdir, arg)):
                os.makedirs(os.path.join(tdir, arg))
            continue

        # create the directory if needed
        if not os.path.exists(os.path.join(tdir, os.path.dirname(arg))):
            os.makedirs(os.path.join(tdir, os.path.dirname(arg)))

        # touch the file
        with open(os.path.join(tdir, arg), "w+") as fh:
            pass

    os.chmod(tdir, 0777)
    return tdir


def create_smf_xml_file(filetype, name, path):
    """ function to create a dummy manifest or profile for smf

    filetype - must be either 'manifest' or 'profile'
    name - name of the service
    path - path the xml should go
    """
    if filetype not in ["manifest", "profile"]:
        raise RuntimeError("filetype is invalid " + filetype)

    # create a service_bundle element
    sb = etree.Element("service_bundle")
    sb.set("type", filetype)
    sb.set("name", "apply")

    # create a service sub element
    service = etree.SubElement(sb, "service")
    service.set("name", name)
    service.set("type", "service")
    service.set("version", "1")

    def_instance = etree.SubElement(service, "create_default_instance")
    if filetype == "manifest":
        def_instance.set("enabled", "true")
    elif filetype == "profile":
        def_instance.set("enabled", "false")

    # create a start and stop method for manifests
    if filetype == "manifest":
        start_method = etree.SubElement(service, "exec_method")
        start_method.set("name", "start")
        start_method.set("type", "method")
        start_method.set("exec", ":true")
        start_method.set("timeout_seconds", "60")
        stop_method = etree.SubElement(service, "exec_method")
        stop_method.set("name", "stop")
        stop_method.set("type", "method")
        stop_method.set("exec", ":true")
        stop_method.set("timeout_seconds", "60")

    # add the <?xml and <!DOCTYPE tags
    raw_string = etree.tostring(sb, pretty_print=True)

    raw_list = raw_string.split("\n")
    raw_list.insert(0, '<?xml version="1.0"?>\n')
    raw_list.insert(1, '<!DOCTYPE service_bundle SYSTEM ' + \
                    '"/usr/share/lib/xml/dtd/service_bundle.dtd.1">\n')
    with open(path, "w+") as fh:
        for line in raw_list:
            fh.write(line + "\n")


def create_transient_manifest(name, path, script):
    """ function to create a transient manifest for smf.  The execution scripts
    are /bin/date for simplicity

    name - name of the manifest
    path - path to put the xml file
    script - script to run by the start/stop/refresh methods
    """
    # create a service_bundle element
    sb = etree.Element("service_bundle")
    sb.set("type", "manifest")
    sb.set("name", "apply")

    # create a service sub element
    service = etree.SubElement(sb, "service")
    service.set("name", name)
    service.set("type", "service")
    service.set("version", "1")

    def_instance = etree.SubElement(service, "create_default_instance")
    def_instance.set("enabled", "false")

    start_method = etree.SubElement(service, "exec_method")
    start_method.set("name", "start")
    start_method.set("type", "method")
    start_method.set("exec", "%s %%m" % script)
    start_method.set("timeout_seconds", "60")
    stop_method = etree.SubElement(service, "exec_method")
    stop_method.set("name", "stop")
    stop_method.set("type", "method")
    stop_method.set("exec", "%s %%m" % script)
    stop_method.set("timeout_seconds", "60")
    refresh_method = etree.SubElement(service, "exec_method")
    refresh_method.set("name", "refresh")
    refresh_method.set("type", "method")
    refresh_method.set("exec", "%s %%m" % script)
    refresh_method.set("timeout_seconds", "60")

    pg = etree.SubElement(service, "property_group")
    pg.set("name", "startd")
    pg.set("type", "framework")

    prop = etree.SubElement(pg, "propval")
    prop.set("name", "duration")
    prop.set("type", "astring")
    prop.set("value", "transient")

    # add the <?xml and <!DOCTYPE tags
    raw_string = etree.tostring(sb, pretty_print=True)

    raw_list = raw_string.split("\n")
    raw_list.insert(0, '<?xml version="1.0"?>\n')
    raw_list.insert(1, '<!DOCTYPE service_bundle SYSTEM ' + \
                    '"/usr/share/lib/xml/dtd/service_bundle.dtd.1">\n')
    with open(path, "w+") as fh:
        for line in raw_list:
            fh.write(line + "\n")
