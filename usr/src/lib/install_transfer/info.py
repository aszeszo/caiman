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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''
   Transfer checkpoint data objects. These objects are stored in the data
   object cache (DOC) and used by the transfer checkpoints.
'''
import tempfile

from lxml import etree
from solaris_install.data_object import DataObject, ParsingError
from solaris_install.data_object import ObjectNotFoundError

ACTION = "action"
APP_CALLBACK = "app_callback"
CONTENTS = "contents"
CPIO_ARGS = "cpio_args"
INSTALL = "install"
IPS = "IPS"
IPS_ARGS = "ips_args"
PURGE_HISTORY = "purge_history"
SOFTWARE_DATA = "software_data"
SVR4_ARGS = "svr4_args"
TRANSFORM = "transform"
TYPE = "type"
UNINSTALL = "uninstall"
UPDATE_INDEX = "update_index"


def convert_to_TF(conv_str, default_val):
    '''Convert a string from any capitalized version of true/false to True and
       False
    '''

    if conv_str is None:
        return default_val
    return conv_str.capitalize() == "True"


class Software(DataObject):
    '''Subclass of DataObject to contain the transfer checkpoint
       information in the Data Object Cache.
    '''
    SOFTWARE_LABEL = "software"
    SOFTWARE_NAME_LABEL = "name"
    SOFTWARE_TYPE_LABEL = "type"

    def __init__(self, name=None, type="IPS"):
        '''Initialize the DataObject object with name software
           and create a transfer object with the specified name.
        '''
        super(Software, self).__init__(Software.SOFTWARE_LABEL)
        self._name = name
        self.tran_type = type

    def to_xml(self):
        '''Method to create the xml software element with
           its associated name (optional).
        '''
        element = etree.Element(Software.SOFTWARE_LABEL)
        if self._name is not None:
            element.set(Software.SOFTWARE_NAME_LABEL, self._name)
        if self.tran_type is not None:
            element.set(Software.SOFTWARE_TYPE_LABEL, self.tran_type)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag software
           - a valid transfer type
           Returns false otherwise.
        '''
        if element.tag != Software.SOFTWARE_LABEL:
            return False

        val = element.get(Software.SOFTWARE_TYPE_LABEL)

        if val in ["IPS", "CPIO", "SVR4"]:
            return True
        else:
            return False

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC software element'''
        chkpt_obj = Software(element.get(Software.SOFTWARE_NAME_LABEL),
                             element.get(Software.SOFTWARE_TYPE_LABEL))

        # The software type label determines whether the transfer is
        # IPS, CPIO or SVR4
        val = element.get(Software.SOFTWARE_TYPE_LABEL)
        if val is None:
            raise ParsingError("No software type defined in the manifest\n")

        # The software_data element holds the items that will be
        # transferred. The val variable identifies what type of transfer
        # object to create.  The action is either to install or uninstall.
        # The contents is a list of items that will be installed or
        # uninstalled. TODO: This could be improved by making it a "def"
        sub_element = element.getchildren()
        for sub in sub_element:
            if sub.tag == SOFTWARE_DATA:
                if val == "IPS":
                    transfer_obj = IPSSpec()
                    action = sub.get(IPSSpec.IPS_ACTION_LABEL)
                    if action is None:
                        action = IPSSpec.INSTALL

                    pkg_list = []
                    names = sub.getchildren()

                    for name in names:
                        pkg_list.append(name.text.strip('"'))

                    transfer_obj.action = action
                    transfer_obj.contents = pkg_list

                elif val == "CPIO":
                    action = sub.get(CPIOSpec.CPIOSPEC_ACTION_LABEL)
                    transfer_obj = CPIOSpec()

                    # A file_list transfer is specified in the manifest.
                    names = sub.getchildren()
                    if len(names) > 0:
                        file_list = list()

                    for name in names:
                        file_list.append(name.text.strip('"'))

                    transfer_obj.contents = file_list
                    transfer_obj.action = action

                elif val == "SVR4":
                    action = sub.get(SVR4Spec.SVR4_ACTION_LABEL)
                    transfer_obj = SVR4Spec()

                    if action is None:
                        action = "install"

                    pkg_list = []
                    names = sub.getchildren()
                    for name in names:
                        pkg_list.append(name.text.strip('"'))

                    transfer_obj.action = action
                    transfer_obj.contents = pkg_list

                # Insert the transfer object as a child of the
                # software checkpoint
                chkpt_obj.insert_children([transfer_obj])

        return chkpt_obj


class Source(DataObject):
    '''Subclass of DataObject to contain the information needed
       to determine the source for the transfer
    '''
    SOURCE_LABEL = "source"

    def __init__(self):
        super(Source, self).__init__(Source.SOURCE_LABEL)

    def to_xml(self):
        '''Method to create the xml source element'''
        element = etree.Element(Source.SOURCE_LABEL)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
            - tag = source
           Returns false otherwise.
        '''
        return element.tag == Source.SOURCE_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC source element
           from the xml tree.
        '''
        obj = Source()
        return obj


class Destination(DataObject):
    '''Subclass of DataObject to contain the information needed
       to determine the destination for the transfer
    '''
    DESTINATION_LABEL = "destination"

    def __init__(self):
        super(Destination, self).__init__(Destination.DESTINATION_LABEL)

    def to_xml(self):
        '''Method to create the xml destination element'''
        element = etree.Element(Destination.DESTINATION_LABEL)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = destination
           Returns false otherwise.
        '''
        return element.tag == Destination.DESTINATION_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the doc element from the xml tree'''
        obj = Destination()
        return obj


class Dir(DataObject):
    '''Subclass of DataObject to contain the information needed
       to determine the directory path for the transfer
    '''
    DIR_LABEL = "dir"
    DIR_PATH_LABEL = "path"

    def __init__(self, path):
        super(Dir, self).__init__(Dir.DIR_LABEL)
        self.dir_path = path

    def to_xml(self):
        '''Method to create the xml dir element'''
        element = etree.Element(Dir.DIR_LABEL)
        element.set(Dir.DIR_PATH_LABEL, self.dir_path)

        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = destination
           Returns false otherwise.
        '''
        return element.tag == Dir.DIR_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the doc element from the xml tree'''
        obj = Dir(element.get(Dir.DIR_PATH_LABEL))
        return obj


class Image(DataObject):
    '''Subclass of DataObject to contain the information needed
       to determine the destination image attributes.
    '''
    IMAGE_LABEL = "image"
    IMAGE_SSL_KEY_LABEL = "ssl_key"
    IMAGE_SSL_CERT_LABEL = "ssl_cert"
    IMAGE_IMG_ROOT_LABEL = "img_root"
    IMAGE_ACTION_LABEL = "action"
    IMAGE_INDEX_LABEL = "index"

    def __init__(self, img_root, action, index=False):
        super(Image, self).__init__(Image.IMAGE_LABEL)
        self.img_root = img_root
        self.action = action
        self.index = index

    def to_xml(self):
        '''Method to create the xml image element'''
        element = etree.Element(Image.IMAGE_LABEL)

        arg_info = self.get_children(Args.ARGS_LABEL)
        if arg_info:
            if Image.IMAGE_SSL_KEY_LABEL in arg_info[0].arg_dict:
                element.set(Image.IMAGE_SSL_KEY_LABEL,
                            arg_info[0].arg_dict[Image.IMAGE_SSL_KEY_LABEL])
            if Image.IMAGE_SSL_CERT_LABEL in arg_info[0].arg_dict:
                element.set(Image.IMAGE_SSL_CERT_LABEL,
                            arg_info[0].arg_dict[Image.IMAGE_SSL_CERT_LABEL])
        element.set(Image.IMAGE_IMG_ROOT_LABEL, self.img_root)
        element.set(Image.IMAGE_ACTION_LABEL, self.action)
        element.set(Image.IMAGE_INDEX_LABEL, str(self.index))
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = image
           Returns False otherwise.
        '''
        return element.tag == Image.IMAGE_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC element from the xml tree'''

        ssl_key = element.get(Image.IMAGE_SSL_KEY_LABEL)
        ssl_cert = element.get(Image.IMAGE_SSL_CERT_LABEL)
        indx = element.get(Image.IMAGE_INDEX_LABEL)
        indx_bool = convert_to_TF(indx, False)

        obj = Image(element.get(Image.IMAGE_IMG_ROOT_LABEL),
                    element.get(Image.IMAGE_ACTION_LABEL),
                    indx_bool)
        args = {}
        if ssl_key:
            args[Image.IMAGE_SSL_KEY_LABEL] = ssl_key
        if ssl_cert:
            args[Image.IMAGE_SSL_CERT_LABEL] = ssl_cert
        if Image.IMAGE_SSL_KEY_LABEL in args or \
           Image.IMAGE_SSL_CERT_LABEL in args:
            arg_obj = Args(args)
            obj.insert_children([arg_obj])
        return obj


class ImType(DataObject):
    '''Subclass of DataObject to contain the information needed to
       determine the image type.
    '''
    IMTYPE_LABEL = "img_type"
    IMTYPE_COMPLETENESS_LABEL = "completeness"
    IMTYPE_ZONE_LABEL = "zone"

    def __init__(self, completeness, zone=False):
        super(ImType, self).__init__(ImType.IMTYPE_LABEL)
        self.completeness = completeness
        self.zone = zone

    def to_xml(self):
        '''Method to create the xml img_type element'''
        element = etree.Element(ImType.IMTYPE_LABEL)
        element.set(ImType.IMTYPE_COMPLETENESS_LABEL, self.completeness)
        if self.zone:
            element.set(ImType.IMTYPE_ZONE_LABEL,
                        str(self.zone).capitalize())
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = img_type
           Returns False otherwise.
        '''
        return element.tag == ImType.IMTYPE_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC element from the xml tree'''
        completeness = element.get(ImType.IMTYPE_COMPLETENESS_LABEL)
        zone = element.get(ImType.IMTYPE_ZONE_LABEL)
        zone_bool = convert_to_TF(zone, False)

        obj = ImType(completeness, zone_bool)
        return obj


class Facet(DataObject):
    '''Subclass of DataObject to contain the information needed to
       set the image facets
    '''
    FACET_LABEL = "facet"
    FACET_SET_LABEL = "set"

    def __init__(self, facet, val=True):
        super(Facet, self).__init__(Facet.FACET_LABEL)
        self.facet_name = facet
        self.val = val

    def to_xml(self):
        '''Method to create the xml facet element'''
        element = etree.Element(Facet.FACET_LABEL)
        element.set(Facet.FACET_SET_LABEL, self.val)
        element.text = self.facet_name
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = facet
           Returns False otherwise.
        '''
        return element.tag == Facet.FACET_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC element from the xml tree'''
        val = element.get(Facet.FACET_SET_LABEL)
        convert_to_TF(val, True)

        facet = element.text
        obj = Facet(facet, val)
        return obj


class Property(DataObject):
    '''Subclass of DataObject to contain the information needed to
       set image properties.
    '''
    PROPERTY_LABEL = "property"
    PROPERTY_VAL_LABEL = "val"

    def __init__(self, prop, val):
        super(Property, self).__init__(Property.PROPERTY_LABEL)
        self.prop_name = prop
        self.val = val

    def to_xml(self):
        '''Method to create the xml property element'''
        element = etree.Element(Property.PROPERTY_LABEL)
        element.set(Property.PROPERTY_VAL_LABEL, self.val)
        element.text = self.prop_name
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = property
           Returns False otherwise.
        '''
        return element.tag == Property.PROPERTY_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the DOC element from the xml tree'''
        val = element.get(Property.PROPERTY_VAL_LABEL)
        prop = element.text
        obj = Property(prop, val)
        return obj


class CPIOSpec(DataObject):
    '''
       Subclass of DataObject to contain the CPIO transfer checkpoint
       information. The following attributes are available:

        action      The transfer action performed. Valid actions: install,
                    uninstall, and transform
        contents    A file containing files/dirs or a list
                    containing the list of files/dirs to be transferred or
                    removed.
    '''
    # Default CPIO values
    DEF_INSTALL_LIST = ".transfer/install_list"
    DEF_UNINSTALL_LIST = ".transfer/uninstall_list"
    DEF_MEDIA_TRANSFORM = ".transfer/media_transform"
    TRANSFER_LABEL = "transfer"
    SOFTWARE_DATA_LABEL = "software_data"
    CPIOSPEC_ACTION_LABEL = "action"
    CPIOSPEC_NAME_LABEL = "name"

    def __init__(self, action=None, contents=None):

        super(CPIOSpec, self).__init__(CPIOSpec.TRANSFER_LABEL)
        self.action = action
        self.contents = contents

    def to_xml(self):
        '''Method to transfer the DOC CPIO checkpoint information
           to xml format.
        '''
        element = etree.Element(CPIOSpec.SOFTWARE_DATA_LABEL)
        src_info = self.parent.get_children(name=Source.SOURCE_LABEL)[0]
        dir_info = src_info.get_children(Dir.DIR_LABEL)[0]
        src = dir_info.object_path
        file_name = "None"

        if self.action == INSTALL:
            if self.contents == CPIOSpec.DEF_INSTALL_LIST \
               or self.contents is None:
                # Use the default list
                action = INSTALL
            else:
                # If a non-default file_list is specified, then
                # tell transfer where to get the file from.
                action = INSTALL
                file_name = self.contents

        if self.action == UNINSTALL:
            if self.contents == CPIOSpec.DEF_UNINSTALL_LIST \
               or self.contents is None:
                # Use the default skip file list
                action = UNINSTALL
            else:
                # If a non-default skip_file_list is specified, then
                # tell transfer where to get the file from.
                action = UNINSTALL
                file_name = self.contents

        if self.action == TRANSFORM:
            if self.contents == CPIOSpec.DEF_MEDIA_TRANSFORM or \
               self.contents is None:
                # Use the default file list
                action = TRANSFORM
            elif self.contents != CPIOSpec.DEF_MEDIA_TRANSFORM:
                action = TRANSFORM
                file_name = self.contents

        element.set(CPIOSpec.CPIOSPEC_ACTION_LABEL, action)

        # action is either install or uninstall.
        # If a name has been specified, place the files or
        # directories into the sub element.
        if file_name:
            if isinstance(file_name, basestring):
                with open(file_name, 'r') as filehandle:
                    for name in filehandle.readlines():
                        sub_element = etree.SubElement(element,
                                      CPIOSpec.CPIOSPEC_NAME_LABEL)
                        sub_element.text = name.rstrip()
            else:
                while file_name:
                    sub_element = etree.SubElement(element,
                                                 CPIOSpec.CPIOSPEC_NAME_LABEL)
                    sub_element.text = file_name.pop(0)

        return element

    @classmethod
    def can_handle(cls, element):
        '''Always returns False
        '''
        return False

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the CPIO checkpoint xml data to the data object
           cache.
        '''
        action = element.get(CPIOSpec.CPIOSPEC_ACTION_LABEL)
        transfer_obj = CPIOSpec()

        # A file_list transfer is specified in the manifest.
        names = element.getchildren()
        if len(names) > 0:
            file_list = list()

            for name in names:
                file_list.append(name.text.strip('"'))
            transfer_obj.contents = file_list
        transfer_obj.action = action

        return transfer_obj


class P5ISpec(DataObject):
    '''Subclass of DataObject to contain the IPS P5i transfer checkpoint
       information
    '''
    P5I_TRANSFER_LABEL = "transfer"
    P5I_SOFTWARE_DATA_LABEL = "software_data"

    def __init__(self, purge_history=False):
        super(P5ISpec, self).__init__(P5ISpec.P5I_TRANSFER_LABEL)
        self.purge_history = purge_history

    def to_xml(self):
        '''Method to transfer the data object cache IPS P5I checkpoint
           information to xml format.
        '''
        element = etree.Element(P5ISpec.P5I_SOFTWARE_DATA_LABEL)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if element has:
           - tag = software_data
           Returns False otherwise.
        '''
        return element.tag == P5ISpec.P5I_SOFTWARE_DATA_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the IPS P5I checkpoint xml data to the data
           object cache
        '''
        obj = P5ISpec()
        return obj


class IPSSpec(DataObject):
    '''Subclass of DataObject to contain the IPS transfer checkpoint
       information. The following attributes are available:
       action      The transfer action performed. Valid actions: install,
                   uninstall, and transform
       contents    A list containing packages to be transferred or
                   removed.
       app_callback:   Holds the value for an application callback
       purge_history : boolean to indicate if the history should be
                       purged. (False)
    '''
    IPS_TRANSFER_LABEL = "transfer"
    IPS_SOFTWARE_DATA_LABEL = "software_data"
    IPS_ACTION_LABEL = "action"
    IPS_NAME_LABEL = "name"
    INSTALL = "install"
    UNINSTALL = "uninstall"

    def __init__(self, action=None, contents=None,
                 app_callback=None, purge_history=False):
        super(IPSSpec, self).__init__(IPSSpec.IPS_TRANSFER_LABEL)
        self.action = action
        self.contents = contents
        self.app_callback = app_callback
        self.purge_history = purge_history

    def to_xml(self):
        '''Method to transfer the data object cache IPS checkpoint information
           to xml format.
        '''
        element = etree.Element(IPSSpec.IPS_SOFTWARE_DATA_LABEL)
        if self.action is IPSSpec.INSTALL:
            element.set(IPSSpec.IPS_ACTION_LABEL, IPSSpec.INSTALL)
        elif self.action is IPSSpec.UNINSTALL:
            element.set(IPSSpec.IPS_ACTION_LABEL, IPSSpec.UNINSTALL)

        for pkg in self.contents:
            sub_element = etree.SubElement(element, IPSSpec.IPS_NAME_LABEL)
            sub_element.text = pkg
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Always returns False
        '''
        return False

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the IPS checkpoint xml data to the data object
           cache
        '''

        transfer_obj = IPSSpec()
        action = element.get(IPSSpec.IPS_ACTION_LABEL)
        if action is None:
            action = IPSSpec.INSTALL

        pkg_list = []
        names = element.getchildren()

        for name in names:
            pkg_list.append(name.text.strip('"'))

        transfer_obj.action = action
        transfer_obj.contents = pkg_list
        return transfer_obj


class SVR4Spec(DataObject):
    '''Subclass of DataObject to contain the SVR4 transfer checkpoint
       information. The following attributes are available:

       action      The transfer action performed. Valid actions: install,
                   uninstall, and transform
       contents    A list containing packages to be transferred or
                   removed.
    '''
    SOFTWARE_DATA_LABEL = "software_data"
    SVR4_TRANSFER_LABEL = "transfer"
    SVR4_ACTION_LABEL = "action"
    SVR4_NAME_LABEL = "name"

    def __init__(self, action=None, contents=None):
        super(SVR4Spec, self).__init__(SVR4Spec.SVR4_TRANSFER_LABEL)
        self.action = action
        self.contents = contents

    def to_xml(self):
        '''Method to transfer the data object cache SVR4 checkpoint information
           to xml format.
        '''
        element = etree.Element(SVR4Spec.SOFTWARE_DATA_LABEL)
        element.set(SVR4Spec.SVR4_ACTION_LABEL, self.action)
        for svr4_pkg in self.contents:
            sub_element = etree.SubElement(element,
                                           Software.SOFTWARE_NAME_LABEL)
            sub_element.text = svr4_pkg
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Always returns False
        '''
        return False

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the SVR4 checkpoint xml data to the data object
           cache
        '''
        action = element.get(SVR4Spec.SVR4_ACTION_LABEL)
        transfer_obj = SVR4Spec()

        if action is None:
            action = "install"

        pkg_list = []
        names = element.getchildren()
        for name in names:
            pkg_list.append(name.text.strip('"'))

        transfer_obj.action = action
        transfer_obj.contents = pkg_list
        return transfer_obj


class Args(DataObject):
    '''Subclass of Args to contain the transfer implementation specific
       arguments
    '''
    ARGS_LABEL = "args"
    ARGS_DICT_LABEL = "arg_dict"

    def __init__(self, arg_dict=None):
        super(Args, self).__init__(Args.ARGS_LABEL)
        self.arg_dict = arg_dict

    def to_xml(self):
        '''Method to create the xml args element'''
        element = etree.Element(Args.ARGS_LABEL)
        element.set(Args.ARGS_DICT_LABEL, self.arg_dict)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
            Returns True if element has:
            - tag = destination
            Returns false otherwise.
        '''
        return element.tag == Args.ARGS_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to create the doc element from the xml tree'''
        obj = Args(element.get(Args.ARGS_DICT_LABEL))
        return obj


class Publisher(DataObject):
    '''Subclass of DataObject to contain the information needed for IPS
       publishers.
    '''
    PUBLISHER_LABEL = "publisher"
    PUB_NAME_LABEL = "name"

    def __init__(self, publisher_name=None):
        super(Publisher, self).__init__(Publisher.PUBLISHER_LABEL)
        self.publisher = publisher_name

    def to_xml(self):
        '''Method to create xml publisher element'''
        element = etree.Element(Publisher.PUBLISHER_LABEL)
        if self.publisher:
            element.set(Publisher.PUB_NAME_LABEL, self.publisher)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if
           - tag = publisher
           Returns False otherwise
        '''
        return element.tag == Publisher.PUBLISHER_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the publisher xml data to the data object
           cache
        '''
        name = None
        name = element.get(Publisher.PUB_NAME_LABEL)
        obj = Publisher(name)
        return obj


class Origin(DataObject):
    '''Subclass of DataObject to contain the information needed for IPS
       Origins.
    '''
    ORIGIN_LABEL = "origin"
    ORIGIN_NAME_LABEL = "name"

    def __init__(self, origin_name=None):
        super(Origin, self).__init__(Origin.ORIGIN_LABEL)
        self.origin = origin_name

    def to_xml(self):
        '''Method to create xml origin element'''
        element = etree.Element(Origin.ORIGIN_LABEL)
        element.set(Origin.ORIGIN_NAME_LABEL, self.origin)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if
           - tag = origin
           Returns False otherwise
        '''
        return element.tag == Origin.ORIGIN_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the origin xml data to the data object
           cache
        '''
        name = element.get(Origin.ORIGIN_NAME_LABEL)
        obj = Origin(name)
        return obj


class Mirror(DataObject):
    '''Subclass of DataObject to contain the information needed for IPS
       Mirrors.
    '''
    MIRROR_LABEL = "mirror"
    MIRROR_NAME_LABEL = "name"

    def __init__(self, mirror_name=None):
        super(Mirror, self).__init__(Mirror.MIRROR_LABEL)
        self.mirror = mirror_name

    def to_xml(self):
        '''Method to create xml mirror element'''
        element = etree.Element(Mirror.MIRROR_LABEL)
        if self.mirror:
            element.set(Mirror.MIRROR_NAME_LABEL, self.mirror)
        return element

    @classmethod
    def can_handle(cls, element):
        '''
           Returns True if
           - tag = mirror
           Returns False otherwise
        '''
        return element.tag == Mirror.MIRROR_LABEL

    @classmethod
    def from_xml(cls, element):
        '''Method to transfer the publisher xml data to the data object
           cache
        '''
        name = element.get(Mirror.MIRROR_NAME_LABEL)

        obj = Mirror(name)
        return obj
