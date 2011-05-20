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

""" execution_checkpoint

 Execution object class for handling the <execution> elements
 in the manifest. This class is a container for the manifest checkpoint
 objects.

"""
import sys

from lxml import etree

from solaris_install.data_object import DataObject, ParsingError
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.data_object.simple import SimpleXmlHandlerBase


class Execution(SimpleXmlHandlerBase):
    """ class to define Execution objects
    """
    TAG_NAME = "execution"
    STOP_ON_ERROR_LABEL = "stop_on_error"

    def __init__(self, name):
        super(Execution, self).__init__(name)

        self.stop_on_error = "true"

    def to_xml(self):
        element = etree.Element(Execution.TAG_NAME)
        element.set(Execution.STOP_ON_ERROR_LABEL, self.stop_on_error)

        return element

    @classmethod
    def can_handle(cls, element):
        '''
        Returns True if element has:
        - a tag 'execution'
        - a 'stop_on_error' attribute
        '''
        if element.tag != cls.TAG_NAME:
            return False

        stop_on_error = element.get(cls.STOP_ON_ERROR_LABEL)
        if stop_on_error is None:
            return False

        return True

    @classmethod
    def from_xml(cls, element):
        stop_on_error = element.get(cls.STOP_ON_ERROR_LABEL)

        execution = Execution(cls.TAG_NAME)
        execution.stop_on_error = stop_on_error

        return execution


class Checkpoint(SimpleXmlHandlerBase):
    """ class to define Checkpoint objects
    """
    TAG_NAME = "checkpoint"
    NAME_LABEL = "name"
    DESC_LABEL = "desc"
    MOD_PATH_LABEL = "mod_path"
    LOG_LEVEL_LABEL = "log_level"
    CHECKPOINT_CLASS_LABEL = "checkpoint_class"
    ARGS_LABEL = "args"
    KWARGS_LABEL = "kwargs"

    def __init__(self, name):
        super(Checkpoint, self).__init__(name)

        self.desc = None
        self.mod_path = None
        self.log_level = None
        self.checkpoint_class = None
        self.args = None
        self.kwargs = None

    def to_xml(self):
        element = etree.Element(Checkpoint.TAG_NAME)

        element.set(Checkpoint.NAME_LABEL, self.name)
        element.set(Checkpoint.MOD_PATH_LABEL, self.mod_path)
        element.set(Checkpoint.CHECKPOINT_CLASS_LABEL, self.checkpoint_class)

        if self.desc is not None:
            element.set(Checkpoint.DESC_LABEL, self.desc)

        if self.log_level is not None:
            element.set(Checkpoint.LOG_LEVEL_LABEL, self.log_level)

        if self.args is not None:
            args_element = etree.SubElement(element, Checkpoint.ARGS_LABEL)
            args_element.text = str(self.args)

        if self.kwargs is not None:
            kwargs_element = etree.SubElement(element, Checkpoint.KWARGS_LABEL)
            Kwargs(Checkpoint.NAME_LABEL).do_to_xml(kwargs_element,
                                                    self.kwargs)
            # indicate that the child tags (kwargs) have
            # already been handled by this class and
            # the DOC should not try to call can_handle
            # on them
            self.generates_xml_for_children = True

        return element

    @classmethod
    def can_handle(cls, element):
        '''
        Returns True if element has:
        - the tag 'checkpoint'
        - a name attribute
        - a mod_path attribute
        - a checkpoint_class attribute

        Otherwise returns False
        '''
        if element.tag != cls.TAG_NAME:
            return False

        for entry in [cls.NAME_LABEL, cls.MOD_PATH_LABEL,
            cls.CHECKPOINT_CLASS_LABEL]:
            if element.get(entry) is None:
                return False

        return True

    @classmethod
    def from_xml(cls, element):
        name = None
        desc = None
        mod_path = None
        checkpoint_class = None
        log_level = None
        args = []
        kwargs = None

        name = element.get(cls.NAME_LABEL)
        desc = element.get(cls.DESC_LABEL)
        mod_path = element.get(cls.MOD_PATH_LABEL)
        checkpoint_class = element.get(cls.CHECKPOINT_CLASS_LABEL)
        log_level = element.get(cls.LOG_LEVEL_LABEL)

        for subelement in element.iterchildren():
            if subelement.tag == cls.ARGS_LABEL:
                args.append(subelement.text)
            if subelement.tag == cls.KWARGS_LABEL:
                kwargs = Kwargs(cls.NAME_LABEL).do_from_xml(subelement)

        checkpoint = Checkpoint(name)
        checkpoint.mod_path = mod_path
        checkpoint.checkpoint_class = checkpoint_class
        if desc:
            checkpoint.desc = desc
        if log_level:
            checkpoint.log_level = log_level
        if args:
            checkpoint.args = args
        if kwargs:
            checkpoint.kwargs = kwargs

        return checkpoint


class Kwargs(object):
    NAME_LABEL = "name"
    KWARGS_LABEL = "kwargs"
    ARG_LABEL = "arg"
    ARGLIST_LABEL = "arglist"
    ARGITEM_LABEL = "argitem"

    def __init__(self, name):
        self.name = name
        self.args = {}
        self.arglist = {}

    def do_to_xml(self, kwargs_element, kwargs):
        for (arg_type, values) in kwargs.items():
            if arg_type == Kwargs.ARG_LABEL:
                for (key, value) in values.items():
                    arg_element = etree.SubElement(kwargs_element,
                                                   Kwargs.ARG_LABEL)
                    arg_element.set(Kwargs.NAME_LABEL, key)
                    arg_element.text = value
            elif arg_type == Kwargs.ARGLIST_LABEL:
                for (key, value) in values.items():
                    arglist_element = etree.SubElement(kwargs_element,
                                                       Kwargs.ARGLIST_LABEL)
                    arglist_element.set(Kwargs.NAME_LABEL, key)
                    for val in value:
                        argitem_element = etree.SubElement(arglist_element,
                                                          Kwargs.ARGITEM_LABEL)
                        argitem_element.text = val

    def do_from_xml(self, element):
        kwargs = Kwargs(Kwargs.KWARGS_LABEL)
        for arg_element in element.iterfind(Kwargs.ARG_LABEL):
            kwargs.args[arg_element.get(Kwargs.NAME_LABEL)] = arg_element.text

        for arglist_element in element.iterfind(Kwargs.ARGLIST_LABEL):
            arglist = [argitem.text for argitem in \
                       arglist_element.iterfind(Kwargs.ARGITEM_LABEL)]
            kwargs.arglist[arglist_element.get(Kwargs.NAME_LABEL)] = arglist

        # kwargs must be in the form of a dictionary to
        # allow the engine to validate them. The engine
        # cannot validate (Kwargs) objects.
        kwargs_dct = dict()
        if kwargs.args:
            kwargs_dct[Kwargs.ARG_LABEL] = kwargs.args
        if kwargs.arglist:
            kwargs_dct[Kwargs.ARGLIST_LABEL] = kwargs.arglist

        return kwargs_dct

# register all the classes with the DOC
DataObjectCache.register_class(sys.modules[__name__])
