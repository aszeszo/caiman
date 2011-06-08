#!/usr/bin/python2.6
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


from lxml import etree

from solaris_install.data_object import DataObject, ObjectNotFoundError
from solaris_install.engine import InstallEngine
from solaris_install.sysconfig.profile.ip_address import IPAddress

USER_LABEL = "user_account"
NETWORK_LABEL = "nic"
NAMESERVICE_LABEL = "nsv"
SYSTEM_LABEL = 'system_info'


def from_engine():
    '''Convenience function for getting the ConfigProfile from
    the engine's DOC instance.

    '''
    doc = InstallEngine.get_instance().doc
    sysconfig = doc.get_descendants(class_type=ConfigProfile)
    if sysconfig:
        return sysconfig[0]
    else:
        return None


def to_engine(profile, override=True):
    '''Convenience function for putting a ConfigProfile into
    the engine's DOC instance. By default, removes any existing
    ConfigProfiles - set override=False to bypass that
    behavior.

    '''
    parent = InstallEngine.get_instance().doc.persistent
    if override:
        remove = parent.get_children(name=profile.name)
        parent.delete_children(children=remove)
    parent.insert_children(profile)


class XMLElement(DataObject):
    '''Bare XML Element'''

    def __init__(self, name, attribs=None):
        if attribs is None:
            attribs = {}
        self.attribs = attribs
        super(XMLElement, self).__init__(name)

    def to_xml(self):
        return etree.Element(self.name, **self.attribs)

    @classmethod
    def can_handle(cls, element):
        return False

    @classmethod
    def from_xml(cls, element):
        return None


class ConfigProfile(DataObject):
    '''Config profile will hold SMFConfig objects as children'''

    LABEL = "sysconfig"
    
    def __init__(self, nic=None, system=None, user_infos=None):
        super(ConfigProfile, self).__init__(self.LABEL)

        self.system = system
        self.nic = nic
        self.users = user_infos
        self.generates_xml_for_children = True

    # pylint: disable-msg=E0202
    @property
    def system(self):
        '''Retrieve SystemInfo child object'''
        return self.get_first_child(name=SYSTEM_LABEL)

    # pylint: disable-msg=E1101
    # pylint: disable-msg=E0102
    # pylint: disable-msg=E0202
    @system.setter
    def system(self, sysinfo):
        '''Replace SystemInfo child object with sysinfo'''
        old = self.system
        if old:
            self.remove_children(old)
        if sysinfo:
            self.insert_children([sysinfo])

    @property
    def nic(self):
        '''Retrieve NetworkInfo child object'''
        return self.get_first_child(name=NETWORK_LABEL)

    @nic.setter
    def nic(self, netinfo):
        '''Replace NetworkInfo child object with netinfo'''
        old = self.nic
        if old:
            self.remove_children(old)
        if netinfo:
            self.insert_children([netinfo])

    @property
    def nameservice(self):
        '''Retrieve NetworkServiceInfo child object'''
        return self.get_first_child(name=NAMESERVICE_LABEL)

    @nameservice.setter
    def nameservice(self, nsvinfo):
        '''Replace NetworkServiceInfo child object with nsvinfo'''
        old = self.nameservice
        if old:
            self.remove_children(old)
        if nsvinfo:
            self.insert_children([nsvinfo])

    @property
    def users(self):
        '''Retrieve UserInfoContainer child object'''
        return self.get_first_child(name=USER_LABEL)
    
    @users.setter
    def users(self, user_infos):
        '''Replace UserInfo child object with user_infos'''
        old = self.users
        if old:
            self.remove_children(old)
        if user_infos:
            self.insert_children(user_infos)
    
    def to_xml(self):
        '''Generate an SC profile XML tree'''
        element = etree.Element('service_bundle', type='profile',
                              name=self.name)
        
        if self.users:
            element.extend(self.users.to_xml())
        if self.system:
            element.extend(self.system.to_xml())

        # generate network configuration only if network group was configured
        if self.nic and self.nic.type is not None:
            element.extend(self.nic.to_xml())
        if self.nameservice:
            element.extend(self.nameservice.to_xml())

        return element

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False

    
class SMFConfig(DataObject):
    '''Represent a single SMF service. Stores SMFInstances
       or SMFPropertyGroups'''

    def __init__(self, name):
        super(SMFConfig, self).__init__(name)

        # For now, store data in a rather flat fashion

    def to_xml(self):
        element = etree.Element('service', name=self.name,
                              version='1', type='service')
        return element

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False

    
class SMFInstance(DataObject):
    '''Represent an instance of SMF service. Stores SMFPropertyGroups'''

    def __init__(self, name, enabled=True):
        super(SMFInstance, self).__init__(name)
        self.enabled = enabled

    def to_xml(self):
        enabled = 'true' if self.enabled else 'false'
        element = etree.Element('instance', enabled=enabled, name=self.name)
        return element

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False


class SMFPropertyGroup(DataObject):
    '''Stores SMFProperties'''

    def __init__(self, pg_name, pg_type='application'):
        super(SMFPropertyGroup, self).__init__(pg_name)

        self.pg_name = pg_name
        self.pg_type = pg_type

    def to_xml(self):
        element = etree.Element('property_group', name=self.pg_name,
                                type=self.pg_type)
        return element

    def setprop(self, tag='propval', name=None, ptype=None, value=None):
        '''Create a child SMFProperty with given name and value'''
        existing = self.get_first_child(name=name)
        if existing is None:
            new = SMFProperty(name, tag, value, ptype)
            self.insert_children([new])
            return new
        else:
            existing.propval = value
            return existing

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False

    def add_props(self, **properties):
        '''Create a series of child SMFProperties from all
        keyword arguments

        '''
        smf_properties = []
        for propname, propval in properties.iteritems():
            prop = SMFProperty(propname, propval=propval)
            smf_properties.append(prop)

        self.insert_children(smf_properties)


class SMFProperty(DataObject):
    '''Represents an SMF property'''

    def __init__(self, propname=None, tagname='propval', propval=None,
                 proptype=None):

        super(SMFProperty, self).__init__(propname)

        self.propname = propname
        self.tagname = tagname
        self.propval = propval
        if proptype is not None:
            self.proptype = proptype
        else:
            self.proptype = self.determine_proptype(propval, proptype)

    @staticmethod
    def determine_proptype(propval, iproptype, is_list=False):
        '''Determine the SMF property type for propval
        One of: astring, host, net_address, net_address_v4, or count
        iproptype distinguishes between possible IP address types
        If propval is a list of properties, return the
        list equivalent (e.g., "astring_list" instead of
        "astring")

        '''
        if is_list:
            if propval:
                propval = propval[0]
            else:
                # Empty list
                return "astring_list"

        if propval is None:
            proptype = "astring"
        elif isinstance(propval, IPAddress):
            if iproptype == "host" or iproptype == "net_address":
                proptype = iproptype
            else:
                proptype = "net_address_v4"
        else:
            try:
                IPAddress(propval)
                if iproptype == "host" or iproptype == "net_address":
                    proptype = iproptype
                else:
                    proptype = "net_address_v4"
            except:
                try:
                    int(propval)
                    proptype = "count"
                except:
                    proptype = "astring"

        if is_list:
            proptype += "_list"

        return proptype

    def add_value_list(self, proptype="astring", propvals=None):
        '''Create a child DataObject structure to represent an
        SMF property list

        '''
        if propvals is None:
            propvals = []

        elem_name = self.determine_proptype(propvals, proptype, is_list=True)

        elem_type = self.get_first_child(name=elem_name)
        if elem_type is None:
            elem_type = XMLElement(elem_name)
            self.insert_children([elem_type])

        elem_vals = []
        for val in propvals:
            if not isinstance(val, basestring):
                raise ValueError("'%s' must be a string or unicode object" %
                                 val)
            elem_vals.append(XMLElement('value_node', {'value': val}))

        elem_type.delete_children()
        elem_type.insert_children(elem_vals)

    def to_xml(self):
        elem_kwargs = {}
        # map attributes of SMFProperty class to xml attributes in smf profile
        obj_attr2xml_attr = {'proptype': 'type',
                             'propname': 'name',
                             'propval': 'value'}

        for attr in ['proptype', 'propname', 'propval']:
            val = getattr(self, attr)
            if val:
                elem_kwargs[obj_attr2xml_attr[attr]] = str(val)

        # pylint: disable-msg=W0142
        element = etree.Element(self.tagname, **elem_kwargs)

        return element

    @classmethod
    def from_xml(cls, xml_node):
        return None

    @classmethod
    def can_handle(cls, xml_node):
        return False


def create_prop_group(name, **kwargs):
    '''Create an SMFPropertyGroup instance with SMFProperties
    determined by any arbitrary keyword arguments passed in.

    '''
    group = SMFPropertyGroup(name)

    properties = []
    for propname, propval in kwargs.iteritems():
        prop = SMFProperty(propname, propval=propval)
        properties.append(prop)

    group.insert_children(properties)
    return group


def create_other(timezone="GMT", hostname="Solaris"):
    '''Create an SMFPropertyGroup to encapsulate misc. install
    parameters (currently, timezone and hostname)

    '''
    return create_prop_group("other_sc_params", timezone=timezone,
                             hostname=hostname)
