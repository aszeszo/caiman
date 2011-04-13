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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
test_td.py - script for testing target discovery.  Parses what is generated via
td.py for easy human readable output.
"""
import optparse
import sys

from solaris_install import Popen
from solaris_install.engine.test import engine_test_utils
from solaris_install.target import discovery
from solaris_install.target import Target
from solaris_install.target.logical import Logical, Zpool
from solaris_install.target.physical import Disk, Partition, Slice
from solaris_install.target.size import Size

ENGINE = None


def parse_args():
    """ parse_args() - function to parse the command line arguments
    """
    parser = optparse.OptionParser()
    parser.add_option("-d", "--disk", dest="disk", action="store_true",
                      help="print disk information")
    parser.add_option("-p", "--partition", dest="partition",
                      action="store_true", help="print partition information")
    parser.add_option("-s", "--slice", dest="slc", action="store_true",
                      help="print slice information")
    parser.add_option("-z", "--zpool", dest="zpool", action="store_true",
                      help="print zpool information")

    options, args = parser.parse_args()

    return options, args


def print_disk():
    """ prints the output from test_td.py -d
    """
    print "Disk discovery"
    # walk the DOC and print only what the user requested
    target = ENGINE.doc.persistent.get_children(class_type=Target)[0]
    disk_list = target.get_children(class_type=Disk)
    header_format = "%15s | %15s | %15s |"
    entry_format = "%15s | %15s | %15.3f |"
    print "Total number of disks:  %d" % len(disk_list)
    print '-' * 53
    print header_format % ("name", "boot disk?", "size [GB]")
    print '-' * 53
    for disk in disk_list:
        if disk.disk_keyword is not None and \
           disk.disk_keyword.key == "boot_disk":
            boot = "yes"
        else:
            boot = "no"
        print entry_format % (disk.ctd, boot, \
                              disk.disk_prop.dev_size.get(Size.gb_units))
    print '-' * 53


def print_partition():
    """ prints the output from test_td.py -p
    """
    print "Partition discovery"
    # walk the DOC and print only what the user requested
    target = ENGINE.doc.persistent.get_children(class_type=Target)[0]
    disk_list = target.get_children(class_type=Disk)
    header_format = "{0:>15} | {1:>5} | {2:>7} | {3:>5} | {4:>11} |"
    disk_format = "{0:>15} |" + 39 * " " + "|"
    line_format = " " * 16 + "| {0:>5} | {1:>7} | {2:>5} | {3:>11} |"

    entry_line = '-' * 57

    print entry_line
    print header_format.format(*["disk_name", "index", "active?", "ID",
                               "Linux Swap?"])
    print entry_line
    for disk in disk_list:
        print disk_format.format(disk.ctd)
        partition_list = disk.get_children(class_type=Partition)
        for partition in partition_list:
            if partition.bootid == Partition.ACTIVE:
                active = "yes"
            else:
                active = "no"

            if partition.is_linux_swap:
                linux_swap = "yes"
            else:
                linux_swap = "no"
            print line_format.format(*[partition.name.split("/")[-1], active,
                                     partition.part_type, linux_swap])
        print entry_line


def print_slice():
    """ prints the output from test_td.py -s
    """
    print "Slice discovery"
    # walk the DOC and print only what the user requested
    target = ENGINE.doc.persistent.get_children(class_type=Target)[0]
    disk_list = target.get_children(class_type=Disk)

    header_format = "{0:>15} | {1:>5} | {2:>40} |"
    disk_format = "{0:>15} |" + 7 * " " + "|" + 42 * " " + "|"
    entry_format = " " * 16 + "| {0:>5} | {1:>40} |"

    disk_line = '-' * 67
    entry_line = disk_line + "|"

    print disk_line
    print header_format.format(*["disk name", "index", "in use?"])
    print entry_line
    for disk in disk_list:
        print disk_format.format(disk.ctd)
        slice_list = disk.get_descendants(class_type=Slice)
        for slc in slice_list:
            if slc.in_use is None:
                in_use = "no"
            else:
                if "used_by" in slc.in_use:
                    in_use = "used by:  %s" % slc.in_use["used_by"][0]
                    if "used_name" in slc.in_use:
                        in_use += " (%s)" % slc.in_use["used_name"][0]
            print entry_format.format(*[slc.name, in_use])
        print entry_line


def print_zpool():
    """ prints the output from test_td.py -z
    """
    print "Zpool discovery"
    target = ENGINE.doc.persistent.get_children(class_type=Target)[0]
    logical = target.get_children(class_type=Logical)[0]
    zpool_list = logical.get_children(class_type=Zpool)

    print_format = "{0:>10} | {1:>20} | {2:>20} | {3:>7} | {4:>8} |"

    zpool_line = '-' * 79

    print zpool_line
    print print_format.format(*["name", "bootfs", "guid", "size", "capacity"])
    print zpool_line
    for zpool in zpool_list:
        # extract zpool information
        cmd = ["/usr/sbin/zpool", "get", "bootfs,guid,size,capacity",
               zpool.name]
        p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE)
        # strip out just the third column.  Exclude the header row and trailing
        # newline
        (bootfs, guid, size, capacity) = \
            [line.split()[2] for line in p.stdout.split("\n")[1:-1]]
        print print_format.format(*[zpool.name, bootfs, guid, size, capacity])
    print zpool_line


def main():
    # parse command line arguments
    options, args = parse_args()

    # set up Target Discovery and execute it, finding the entire system
    global ENGINE
    ENGINE = engine_test_utils.get_new_engine_instance()
    TD = discovery.TargetDiscovery("Test TD")
    TD.execute()

    if options.disk:
        print_disk()
    if options.partition:
        print_partition()
    if options.slc:
        print_slice()
    if options.zpool:
        print_zpool()

    engine_test_utils.reset_engine()

if __name__ == "__main__":
    main()
