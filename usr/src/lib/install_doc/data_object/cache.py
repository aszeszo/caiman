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
"""Mechanism for providing a central store of in-memory data in the installer.
"""

import inspect
import pickle

from lxml import etree

from solaris_install.data_object import \
    DataObjectBase, DataObject

# Registry of all classes that use the cache (ie all sub-classes of DataObject)
# Uses a dictionary, with keys being priorities, and values being a list of
# classes at that priority level.
_CACHE_CLASS_REGISTRY = dict()


class DataObjectCacheChild(DataObject):
    '''Object to represent the sub-trees of the DataObjectCache

    Doesn't generate any XML or import any XML it-self.
    '''

    def __init__(self, name):
        '''Initialization function for DataObjectCacheChild class.'''
        super(DataObjectCacheChild, self).__init__(name)

    def delete(self):
        '''Recursively deletes an object

        Override to avoid deletion of DataObjectCacheChildren object itself.
        '''
        for child in self._children:
            child.delete()

    @classmethod
    def can_handle(cls, xml_node):
        '''Children of DataObjectCache don't have XML representation.'''
        return False

    @classmethod
    def from_xml(cls, xml_node):
        '''Children of DataObjectCache don't have XML representation.'''
        return None

    def to_xml(self):
        '''Children of DataObjectCache don't have XML representation.'''
        return None

    def __repr__(self):
        return "DataObjectCacheChild: %s" % self.name


class DataObjectCache(DataObjectBase):
    '''Primary access class for the Data Object Cache infrastructure.

    Usually accessed by the Engine singleton, but may be used independently
    of the Engine.

    Provides the following functionality:

    - Has two sub-trees:

      - persistent - will be written to disk if snapshot mechanism is used,
                     and is overwritten if snapshots are loaded.
      - volatile   - exists only in-memory and is not effected by snapshot
                     loading or written when a snapshot is taken.

    - Snapshot and Roll-back

      - It is possible to write out data from the 'persistent' sub-tree to a
        file or file-like object.

      - It is possible to roll-back the 'persistent' sub-tree to the contents
        of a provided file or file-like object.

    - XML Manifest Import and Generation

      - Drives the import of an XML manifest into a DataObject based tree
      - Drives the generation of XML suitable for conversion in to an XML
        manifest via XSLT.

    Sub-classes DataObjectBase to ensure that its not possible to
    add or remove the "persistent" and "volatile" children.

    Consumsers of the Data Object Cache should not insert/delete children
    to/from the DataObjectCache object, but instead should insert/delete
    them to/from the 'persistent' or 'volatile' sub-trees.

    '''

    VOLATILE_LABEL = "volatile"
    PERSISTENT_LABEL = "persistent"

    def __init__(self):
        '''Initialization function for DataObjectCache class.'''
        super(DataObjectCache, self).__init__("DataObjectCache")

        # Create 'persistent' and 'volatile' sub-trees
        self._persistent_tree = DataObjectCacheChild(
            DataObjectCache.PERSISTENT_LABEL)
        self._volatile_tree = DataObjectCacheChild(
            DataObjectCache.VOLATILE_LABEL)

        # Add children to tree, and update parent references.
        self._children = [self._persistent_tree, self._volatile_tree]
        self._persistent_tree._parent = self
        self._volatile_tree._parent = self

    @property
    def persistent(self):
        '''Returns the persistent tree child_node'''
        return self._persistent_tree

    @property
    def volatile(self):
        '''Returns the volatile tree child_node'''
        return self._volatile_tree

    #
    # Utility Methods
    #
    def clear(self):
        '''Delete all objects from the sub-trees.

        This will delete all objects from cache, except for the root,
        persistent and volatile nodes.
        '''

        for child in self._children:
            child.delete_children()

        msg = "DataObjectCache cleared!"
        self.logger.info(msg)

    @property
    def is_empty(self):
        '''Returns True if the contents of the cache is deemed empty.

        Empty is defined as the sub-nodes, 'persistent' and 'volatile'
        having no children.
        '''
        return not self._persistent_tree.has_children and \
                not self._volatile_tree.has_children

    def take_snapshot(self, file_obj):
        '''Takes a snapshot of the 'persistent' sub-tree.

        This method writes the contents of the 'persistent' sub-tree to the
        destination provided by 'file_obj'.

        'file_obj' may be one of the following:

        a string    - this is used as the path of a file to open for writing.

        an object   - this object is required to have a 'write(str)' method
                      that takes a single string as a parameter. It can thus
                      be  an open file object, a StringIO object, or any
                      other custom object that meets this interface.

        Exceptions:

        ValueError  - This will be thrown if wrong type is passed for
                      'file_obj'

        IOError     - This will be thrown if there is a problem opening the
                      specified file_obj path string.
        '''

        close_at_end = False
        if isinstance(file_obj, str):
            # If it's a string, then open the file_obj.
            outfile = open(file_obj, 'wb')
            close_at_end = True
        # Check if it has a write() method...
        elif hasattr(file_obj, "write"):
            outfile = file_obj
        else:
            # Object isn't acceptable for output to, needs write() method.
            raise ValueError("'file_obj' should be either a file path string \
                               or object with write(string) method")

        pickle.dump(self._persistent_tree, outfile)

        if close_at_end:
            outfile.close()

    def load_from_snapshot(self, file_obj):
        '''Load a snapshot in to the 'persistent' sub-tree.

        This method load the contents of the 'persistent' sub-tree from the
        provide file_obj parameter.

        'file_obj' may be one of the following:

        a string    - this is used as the path of a file to open for reading.

        an object   - This is a file_obj-like object for reading a data
                      stream.

                      The file_obj-like object must have two methods, a read()
                      method that takes an integer argument, and a readline()
                      method that requires no arguments. Both methods should
                      return a string. This file-like object can be a file
                      object opened for reading, a StringIO object, or any
                      other custom object that meets this interface.

        Exceptions:

        ValueError  - This will be thrown if wrong type is passed for
                      'file_obj'

        IOError     - This will be thrown if there is a problem opening the
                      specified file_obj path string.

        '''

        close_at_end = False
        if isinstance(file_obj, str):
            # If it's a string, then open the file_obj.
            infile = open(file_obj, 'rb')
            close_at_end = True
        # Check if it has a write() method...
        elif (hasattr(file_obj, "read") and hasattr(file_obj, "readline")):
            infile = file_obj
        else:
            # Object isn't acceptable for output to, needs write() method.
            raise ValueError("'file_obj' should be either a file path string \
                               or object with read and readline methods")

        new_cache_peristent_tree = pickle.load(infile)

        if close_at_end:
            infile.close()

        self._persistent_tree.delete_children()
        self._persistent_tree.insert_children(
            new_cache_peristent_tree.children)

    @classmethod
    def register_class(cls, new_class_obj, priority=50):
        '''Register a class with the DataObjectCache for importing XML.

        Registers sub-classes of DataObject, which are then used when
        importing XML to find classes that support the handling of XML
        snippets by calling the 'can_handle()' and 'from_xml()' methods.

        'new_class_obj' may be either any of:
        - a single class object or module
        - an iterable object containing class objects and/or modules

        Modules to be registered should contain classes that are sub-classes
        of DataObjectBase.

        The priority defines the order in which classes are checked, with
        lower numbers being checked first - the default is for all registered
        classes to be at priority 50.

        Exceptions:

            TypeError
            - thrown if class_obj is not a sub-class of DataObjectBase,
              a Module, or an iterable object containing either of them.

            ValueError
            - thrown if priority is not in the range 0-100 inclusive.
        '''

        if priority < 0 or priority > 100:
            raise ValueError("Invald priority value %d" % (priority))

        try:
            # Check if it's an iterable object, if so, pass through
            iter(new_class_obj)
            class_list = new_class_obj
        except TypeError:
            # Assume single instance of DataObjectBase, and put it in a list.
            class_list = [new_class_obj]

        # Should have iterable at this point, so loop through.
        for class_ref in class_list:
            if inspect.ismodule(class_ref):
                # It's not really a class, it's a module, so get it's classes
                to_register = []
                for name, value in \
                    inspect.getmembers(class_ref, inspect.isclass):

                    if inspect.getmodule(value) != class_ref:
                        # Skip anything that didn't originate from the module
                        # itself (e.g. DataObject imported into the module)
                        continue
                    if issubclass(value, DataObjectBase):
                        to_register.append(value)

                if len(to_register) > 0:
                    # Do a recursive call to self to register found classes
                    DataObjectCache.register_class(to_register, priority)

            elif issubclass(class_ref, DataObjectBase):
                # It's definitely a valid class to register it.
                _CACHE_CLASS_REGISTRY.setdefault(priority, [])\
                    .append(class_ref)
            else:
                raise TypeError("Class '%s' is not a sub-class of %s" %
                                (str(class_ref), str(DataObject)))

    @classmethod
    def get_registered_classes_str(cls):
        '''Generates a string of all registered classes to standard out.'''
        string_list = ["============================", "Registered Classes:"]
        for prio in sorted(_CACHE_CLASS_REGISTRY.keys()):
            string_list.append("[Priority = %d]" % (prio))
            for cls in _CACHE_CLASS_REGISTRY[prio]:
                string_list.append("    %s" % repr(cls))
        string_list.extend(["============================", ""])

        return "\n".join(string_list)

    @classmethod
    def find_class_to_handle(cls, node):
        """Find a class that handles a node in the known_classes list."""
        for prio in sorted(_CACHE_CLASS_REGISTRY.keys()):
            for cls in _CACHE_CLASS_REGISTRY[prio]:
                if cls.can_handle(node):
                    return cls

        return None

    @classmethod
    def __create_doc_from_xml(cls, parent, node):
        '''Given an XML tree, generates the contents of the DataObjectCache'''
        # Use same parent, skip level by default
        new_parent = parent

        found_class = cls.find_class_to_handle(node)
        if found_class:
            obj = found_class.from_xml(node)
            if obj:
                parent.insert_children(obj)
                new_parent = obj

        for child in node:
            cls.__create_doc_from_xml(new_parent, child)

    def import_from_manifest_xml(self, dom_root_node, volatile=False):
        '''Imports the provided XML tree into the Data Object cache

        By default, because 'volatile' is False, the XML will be imported
        into the DataObjectCache.persistent sub-tree.

        Otherwise, if 'volatile' is True, then the XML will be imported into
        the DataObjectCache.volatile sub-tree.

        Exceptions:

            ParsingError
            - Because from_xml() is used to import the XML, it is possible
              that there could be some bad XML which will result in this
              exception being thrown.
        '''

        if volatile:
            import_base = self.volatile
        else:
            import_base = self.persistent

        for child in dom_root_node:
            DataObjectCache.__create_doc_from_xml(import_base, child)

    def generate_xml_manifest(self):
        '''Generates XML from the DataObjectCache'''
        return self.get_xml_tree()

    # XML Generation
    def to_xml(self):
        '''Return the 'root' node of the DataObjectCache.'''
        return etree.Element("root")

    # XML Import
    @classmethod
    def can_handle(cls, xml_node):
        '''The DataObjectCache class doesn't import any XML itself.'''
        return False

    @classmethod
    def from_xml(cls, xml_node):
        '''The DataObjectCache class doesn't import any XML itself.'''
        return None
