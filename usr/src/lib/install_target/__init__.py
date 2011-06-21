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
Python package for targets

cgc is a module for "ctypes garbage collection" and is only used
by the libnvpair and libdiskmgt sub-packages.
"""
import copy
import platform

import logical
import physical

import osol_install.errsvc as errsvc

from solaris_install.data_object.simple import SimpleXmlHandlerBase
from solaris_install.data_object.cache import DataObject, DataObjectCache


__all__ = ["cgc", "controller", "discovery", "instantiation", "libdiskmgt",
           "libnvpair", "logical", "physical", "vdevs"]

CRO_LABEL = "croinfo output"


# simple DOC object for the target element
class Target(SimpleXmlHandlerBase):
    DISCOVERED = "discovered"
    DESIRED = "desired"
    TAG_NAME = "target"

    class InvalidError(Exception):
        """ user defined exception to handle exceptions that arise during
        final_validation
        """
        pass

    def validate_node(self, node):
        """ validate_node() - method to add children to a temporary DataObject
        to look for valdation errors.

        node - DataObject to test.  Recursively call validate_node on any child
        object that has children of its own.
        """
        # copy the the node to clear out the children.  Keep the parent so the
        # tree rebuilds correctly
        node_copy = copy.copy(node)
        node_copy._parent = node._parent

        # walk the original list of children
        for child in node.get_children():
            # look to see if the child object has children of its own.
            if child.has_children:
                # recurse
                self.validate_node(child)

            # Make a copy of the child object, insert it into node_copy, and
            # check the errsvc
            child_copy = copy.copy(child)
            node_copy.insert_children(child_copy)
            if errsvc._ERRORS:
                raise Target.InvalidError("DOC object which caused the " +
                                          "failure: " + str(child))

    def final_validation(self):
        """ final_validiation() - method to validate the entire Target sub-tree
        """
        try:
            # for x86, check for at least one active Solaris2 partition
            # specified
            if platform.processor() == "i386":
                old_solaris = \
                    physical.Partition.name_to_num("Solaris/Linux swap")
                solaris2 = physical.Partition.name_to_num("Solaris2")
                p_list = self.get_descendants(class_type=physical.Partition)
                found_old_solaris = False
                for partition in p_list:
                    # look for the old solaris partition id (130)
                    if partition.part_type == old_solaris:
                        found_old_solaris = True

                    # if the partition is a solaris2 partition (191), verify
                    # it's an active primary partition or a logical partition
                    if partition.part_type == solaris2:
                        if partition.bootid == physical.Partition.ACTIVE or \
                           partition.is_logical:
                            break
                else:
                    # check to see if an older solaris partition was found.  If
                    # so, warn the user before failing
                    if found_old_solaris:
                        self.logger.warning("Only found an older 'solaris' "
                                            "partition.  Consider using "
                                            "fdisk to change the partition ID "
                                            "to 'solaris2'")

                    raise Target.InvalidError("No active 'Solaris2' "
                                              "partitions found")

            # verify one zpool is specified with is_root set to "true"
            zpool_list = self.get_descendants(class_type=logical.Zpool)
            for zpool in zpool_list:
                if zpool.is_root:
                    # XXX Do we really need this check for whole_disk?
                    # a zpool is configured to be the root pool.  Now find any
                    # Disk objects where whole_disk is set to true and ensure
                    # that the disk does *not* have in_zpool set to the name of
                    # this pool.
                    disk_list = self.get_descendants(class_type=physical.Disk)
                    for disk in disk_list:
                        if disk.whole_disk:
                            if disk.in_zpool == zpool.name:
                                raise Target.InvalidError("%s " % disk.ctd +
                                   "has 'whole_disk' set to 'true', but " +
                                   "is part of the root pool")

                    # verify this root pool has one BE associated with it
                    if not zpool.get_children(class_type=logical.BE):
                        raise Target.InvalidError("%s " % zpool.name +
                            "has no Boot Environments associated with it")

                    # if the code has gotten this far, the zpool is a valid
                    # root pool
                    break
            else:
                raise Target.InvalidError("A root pool must be specified.  " +
                                          "No zpools are marked as a root " +
                                          "pool")

            # reset the errsvc completely
            errsvc.clear_error_list()

            # re-insert every node in the Target tree to re-run validation
            for disk in self.get_descendants(class_type=physical.Disk):
                # only validate the disks that have children elements
                if disk.has_children:
                    self.validate_node(disk)

            # validate the logical targets next
            logical_list = self.get_children(class_type=logical.Logical)
            if logical_list:
                self.validate_node(logical_list[0])

        except Target.InvalidError as err:
            self.logger.debug("Final Validation failed")
            self.logger.debug(str(err))
            return False
        else:
            # everything validates
            self.logger.debug("Final Validation succeeded")
            return True

    def get_children(self, name=None, class_type=None, max_count=None,
                     not_found_is_err=False):
        """ overload the parent object's get_children method to also provide
        sorting for croinfo output
        """
        # call the parent's method first
        unsorted_children = super(Target, self).get_children(name, class_type,
            max_count, not_found_is_err)

        # get_children may be called before this Target DOC object is
        # inserted into the DOC so simply return the unsorted_children list.
        if self.parent is None or class_type is None or \
           not hasattr(class_type, "_label_disk"):
            return unsorted_children

        # retreive the DataObjectDict from the DOC
        cro_data = self.root_object.persistent.get_first_child(
            name=CRO_LABEL)

        # not all systems support croinfo so if the data_dict is empty or not
        # present in the DOC, return the unsorted list
        if not cro_data:
            return unsorted_children

        cro_dict = cro_data.data_dict

        # compare the first element of the croinfo tuple (the position)
        def compare(x, y):
            if isinstance(x, physical.Disk) and isinstance(y, physical.Disk):
                return cmp(cro_dict[x.ctd][0], cro_dict[y.ctd][0])

        # sort the children by croinfo order
        return sorted(unsorted_children, cmp=compare)


# register all the DOC classes
DataObjectCache.register_class(Target)
DataObjectCache.register_class(logical)
DataObjectCache.register_class(physical)
