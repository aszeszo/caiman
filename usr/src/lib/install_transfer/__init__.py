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

"""init module for the transfer checkpoint"""
import info
import sys
from solaris_install.data_object.cache import DataObjectCache

from cpio import TransferCPIO
from ips import TransferIPS
from p5i import TransferP5I
from svr4 import TransferSVR4


__all__ = ["ips", "p5i", "cpio", "info", "prog", "svr4"]

module_func_map = {
    "IPS": [TransferIPS.__module__, TransferIPS.__name__],
    "SVR4": [TransferSVR4.__module__, TransferSVR4.__name__],
    "CPIO": [TransferCPIO.__module__, TransferCPIO.__name__],
    "P5I": [TransferP5I.__module__, TransferP5I.__name__]
}


# register all the classes with the DOC
DataObjectCache.register_class(info)


def create_checkpoint(software_node):
    """ Generate a suitable Transfer checkpoint tuple.

    Given a specific Software data object, this method will generate a
    suitable set of arguments:

    checkpoint_name, module_path, checkpoint_class_name

    to pass to a call into InstallEngine.register_checkpoint(), e.g.

    ckpt_info = create_checkpoint(my_software)
    InstallEngine.register_checkpoint(*ckpt_info)

    The assumption is that the Software node has already been validated
    semantically by the time this is called.

    Return Values:
    checkpoint_name, module_path and checkpoint_class_name
    """

    if software_node is None:
        return None

    ckpt_name = software_node.name

    module_path = None
    ckpt_class_name = None

    if software_node.tran_type in module_func_map:
        module_path, ckpt_class_name = module_func_map[software_node.tran_type]
        return ckpt_name, module_path, ckpt_class_name
