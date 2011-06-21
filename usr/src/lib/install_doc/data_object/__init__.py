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
'''Provides definition of base classes for storage in Data Object Cache.
'''

__all__ = ["cache", "data_dict", "simple"]

import copy
import logging
import re
import sys
from urllib import quote, unquote

from abc import ABCMeta, abstractmethod

from lxml import etree
from solaris_install.logger import INSTALL_LOGGER_NAME

# Define various Data Object specific exceptions


class DataObjectError(Exception):
    '''A common base exception for any DataObject related errors.'''
    pass


class ObjectNotFoundError(DataObjectError):
    '''An exception to be raised if specified objects are not found.'''
    pass


class ParsingError(DataObjectError):
    '''Exception to be raised when parsing of XML failed.'''
    pass


class PathError(DataObjectError):
    '''Exception to be raised when an invalid path is provided.'''
    pass


class DataObjectBase(object):
    '''Core abstract base class for the Data Object Cache contents.

    Every object that is stored in the Data Object Cache is required
    to sub-class the DataObject class, and implement the required
    abstract methods:

    - to_xml()
    - can_handle()
    - from_xml()

    This class provides the basic infrastructure for the Data Object
    Cache:
    - a tree mechanism
      - parent/child relationships
      - allows for insertion, deletion, and fetching of children in
        the tree.
    - the XML import/export mechanism.
    - path-based searching.
    '''
    __metaclass__ = ABCMeta

    # Define regular expressions for matching values in a path specification.
    __NAME_RE = re.compile("^([^\[\].]+)")
    __TYPE_RE = re.compile("^.*\[.*@((\w|\.)+)[#?\.]*.*\].*")
    __COUNT_RE = re.compile("^.*\[.*#(-*\d+).*\].*")
    __DEPTH_RE = re.compile("^.*\[.*\?(-*\d+).*\].*")
    __ATTR_RE = re.compile(".*\.(\w+)$")

    # Define regular expression for extracting paths from strings.
    __STRING_REPLACEMENT_RE = re.compile("%{([^}]+)}")

    # Reference for Install Logger
    __logger = None

    def __init__(self, name):
        self._name = name
        self._parent = None

        self.generates_xml_for_children = False

        # instead of simple list, _children could be a
        # MutatableSequence sub-class
        self._children = []

    @classmethod
    def get_logger(cls):
        ''' Returns reference to logger class

        Use a class method and variable instead of an instance variable as
        pickle has problems when it tries to pickle the reference to the
        logger.

        Mainly used for logging from class methods, so most will just use
        self.logger property if it's an object instance.
        '''
        if cls.__logger is None:
            cls.__logger = logging.getLogger(INSTALL_LOGGER_NAME)

        return cls.__logger

    @property
    def logger(self):
        '''Instance accessor for the logger.

        The use of a property is a nicer interface sub-classes to use.
        '''
        return DataObjectBase.get_logger()

    # Abstract class methods.
    # These methods must be implemented by DataObject sub-classes or an
    # Exception will be raised when they are instantiated.

    @abstractmethod
    def to_xml(self):
        '''
        This method is used in the generation of XML output for a manifest.

        It is defined as an abstract method to require implementors of
        DataObject sub-classes to make a decision on what support is required
        for their implementation.

        The expected return values of this method are:

        None

        - If no XML is to be generated by this method return this.

        etree.Element

        - Return an lxml etree Element implementation which should
          represent this object.

          It is expected that children of this object will in turn
          provide their own XML representation from their to_xml()
          method, which will be added as sub-elements of the returned
          value from this object.

          If a sub-class of this class wishes to handle the XML for its
          children as well as for itself, then set the instance
          variable "generates_xml_for_children" to True and
          return a suitable sub-tree from this method.

          The XML returned here should be as close as possible to
          it's equivalent in the AI/DC Manifest Schema.
        '''
        return None

    @classmethod
    @abstractmethod
    def can_handle(cls, xml_node):
        '''
        This method is used, when importing XML, to quickly determine if a
        class is able to process an XML Element, and convert it
        to an instance of it self.

        The parameter 'xml_node' will be an etree.Element object, and this
        method should be implemented to quickly examine it to decide if
        a subsequent call to the from_xml() method will be able to convert
        it into a DataObject.

        Examination of the XML Element can include examining it's tag,
        attributes, parent, or anything else that is available using the
        etree API.

        Expected Return Values:

        True    - Returned if a subsequent call to 'from_xml()' would work.

        False   - Returned if this XML Element cannot be handled by this
                  class.
        '''
        return False

    @classmethod
    @abstractmethod
    def from_xml(cls, xml_node):
        ''' Generate XML to represent this object.

        This method will only be called if a previous call to 'can_handle()'
        returned True.

        Its purpose is to further parse the XML Element passed and generate
        a DataObject instance that matches it.

        Child elements will usually be processed directly in the same way, but
        if the to_xml() method generates XML for it's children, then it's
        likely this this method should do the same when importing XML, and
        generate children objects.

        Expected Return Values:

            DataObject instance
            - This should be a sub-class of DataObject.

        Exceptions:

            ParsingError
            - On an unexpected parsing error, this method should raise a
              'ParsingError' exception with information on why it failed.

        '''
        return None

    # Read-only properties
    #
    # These are accessor methods for simple class properties.
    # These methods should not be called directly, the Python 'property'
    # syntax should be used instead.

    @property
    def name(self):
        '''Returns the name given to the object when created'''
        return self._name

    @property
    def parent(self):
        '''Returns the parent class, set on insertion into tree'''
        return self._parent

    @property
    def root_object(self):
        '''Returns the root object class following parents to top'''
        root_object = self
        while root_object._parent is not None:
            root_object = root_object._parent
                
        return root_object

    @property
    def has_children(self):
        '''Returns True if the class has any children, False otherwise.'''
        return (len(self._children) > 0)

    # Methods for searching the cache, we provide 3 variants:
    #
    # - get_children:       returns a list of direct children matching
    #                       criteria
    #
    # - get_first_child:    returns only the first matching direct child
    #
    # - get_descendants:    recursively searches tree returning all
    #                       matching descendants
    #
    def get_children(self, name=None, class_type=None, max_count=None,
                     not_found_is_err=False):
        '''Obtains a list of children, possibly filtered by critera.

        This method returns a list of the children objects that match
        the provided criteria.

        By default, if no criteria is specified, a list containing references
        to all the children will be returned.

        You may specify one, or more, of the following to narrow the list of
        children returned:

        name        - When specified, this will search for children objects
                      with the specified name value, and return those objects.

        class_type  - When specified this will return any children with the
                      provided class_type.

        max_count   - Limit the number of children returned, searching stops
                      on reaching this number of matches.

        Exceptions:

        ObjectNotFoundError
            If specific criteria is provided, not_found_is_err is True, and no
            matches are found, then this exception will be thrown, otherwise an
            empty list will be returned.

        Note: the list returned is a copy (but the children aren't copied) so
              modifying the list will not effect the internal list of children,
              but modifying the children will.
        '''

        # Special case request for all children.
        if name is None and class_type is None:
            if max_count is None:
                return copy.copy(self._children)

        # If no class_type given, assume DataObjectBase, otherwise
        # get_descentants will return error.
        if class_type is None:
            class_type = DataObjectBase

        return self.get_descendants(name, class_type, max_depth=1,
            max_count=max_count, not_found_is_err=not_found_is_err)

    # Define children property, don't use @property since get_children is
    # itself part of the exposed API.
    children = property(get_children)

    def get_first_child(self, name=None, class_type=None):
        '''Obtains a reference to the first child matching criteria.

        This method returns a reference to the first child object that matches
        the provided criteria.

        By default, if no criteria is specified, a reference to the first
        child in the list of children will be returned.

        You may specify one, or both, of the following to narrow the list of
        children returned:

        name        - When specified, this will search for children objects
                      with the specified name value, and return the first
                      match.

        class_type  - When specified this will return the first child with
                      the provided class_type.

        If no match is found, then this method will return 'None'.
        '''

        if name is None and class_type is None:
            if len(self._children) > 0:
                return self._children[0]
            else:
                return None

        try:
            child_list = self.get_descendants(name=name,
                class_type=class_type, max_depth=1, max_count=1,
                not_found_is_err=True)
            return child_list[0]
        except ObjectNotFoundError:
            return None

    def get_descendants(self, name=None, class_type=None, max_depth=None,
                        max_count=None, not_found_is_err=False):
        '''Searches tree for a list of descendents that match the criteria.

        This method recursively searches a tree of DataObjects looking for
        objects that match the provided criteria, and returning them in a
        simple list.

        The search is done in a 'depth-first' way, where a tree like:

                                A
                            B       C
                          D   E    F  G

        would result in a list like:

                        A B D E C F G

        You may specify one, or both, of the following to narrow the list of
        children returned:

        name        - When specified, this will search for children objects
                      with the specified name value, and return those objects.

        class_type  - When specified this will return any children with the
                      provided class_type.

        You may further limit the traversal of the tree by specifying the
        following:

        max_depth   - Maximum depth to traverse the tree too, could speed up
                      such a search in a large tree structure. A value of 0,
                      or None, means the depth should not be limited.

        max_count   - Limit the number of children returned, searching stops
                      on reaching this number of matches.

        Exceptions:

            ValueError
                Thrown if both of the name or class_type are not specified,
                or if an invalid value is specified.

            ObjectNotFoundError
                If specific criteria is provided, not_found_is_err is True, and
                no matches are found, then this exception will be thrown,
                otherwise an empty list will be returned.

        '''

        if max_depth is not None and max_depth < 0:
            raise ValueError(
                "max_depth should be greater than or equal to 0, got %d" %
                (max_depth))

        if max_count is not None and max_count < 1:
            raise ValueError(
                "max_count should be greater than or equal to 1, got %d" %
                (max_count))

        if name is None and class_type is None:
            raise ValueError(
                "Please specify at least one of 'name' or 'class_type'")

        # To simplify test in loop below, assume DataObject is the
        # class_type if none given,
        if class_type is None:
            class_type = DataObjectBase

        new_list = list()
        new_max_count = None
        for child in self._children:
            if max_count is not None:
                new_max_count = max_count - len(new_list)
                if new_max_count < 1:
                    # Reached limit, stop now.
                    break

            # Look for matches to criteria
            if isinstance(child, class_type):
                if name is None or name == child.name:
                    new_list.append(child)
                    # Double check max_count after adding to the list.
                    if max_count is not None:
                        if len(new_list) >= max_count:
                            break
                        else:
                            new_max_count -= 1

            # Now search children's children, using recursion...
            if child.has_children:
                new_max_depth = None
                if max_depth is not None:
                    if max_depth > 1:
                        new_max_depth = max_depth - 1
                    elif max_depth == 1:
                        # Don't go any deeper than current child level.
                        continue

                try:
                    children_list = child.get_descendants(name=name,
                        class_type=class_type, max_depth=new_max_depth,
                        max_count=new_max_count)
                    new_list.extend(children_list)
                except ObjectNotFoundError:
                    # Don't throw here, will throw later if still none found.
                    pass

        if len(new_list) == 0 and not_found_is_err:
            raise ObjectNotFoundError(\
                "No matching objects found: name = '%s' "
                "and class_type = %s" %
                (str(name), str(class_type)))

        return new_list

    @staticmethod
    def _check_object_type(obj):
        '''THIS IS A PRIVATE METHOD

        Checks if an object is instance of DataObjectBase, need to check
        for this rather than DataObject to allow for DataObjectDict and
        similar classes to work..

        Will raise a 'TypeError' exception if it fails.
        '''

        if not isinstance(obj, DataObjectBase):
            msg = "Invalid Child Type: %s" % (obj.__class__.__name__)
            DataObjectBase.get_logger().error(msg)
            raise TypeError(msg)

    # Methods for cloning / duplication objects
    def __getstate__(self):
        '''Provide a copy of the internal dictionary to be used in deepcopy'''
        # Take a copy of the internal dictionary using constructor
        state = dict(self.__dict__)
        # Ensure that copy doesn't have a parent to avoid recusion up tree.
        state['_parent'] = None
        return state

    def __setstate__(self, state):
        '''Set the internal dictionary to construct new copy for deepcopy()'''
        self.__dict__ = state
        # Since we removed the parent refs in __getstate__ we need to restore
        # them to our children, which are copies when using deepcopy().
        for child in self._children:
            child._parent = self

    def __copy__(self):
        '''Create a copy of ourselves for use by copy.copy()

        The new copy will have no parent or children.

        Complex objects should consider defining the special method
        __copy__() if they wish to override the default behaviour.
        If overriding this you must call the super-classes __copy__() method
        to ensure correct behaviour.
        '''

        # Construct a new class to match self
        new_copy = self.__class__.__new__(self.__class__)
        # Set the dictionary.
        new_copy.__dict__.update(self.__dict__)
        # Clear the parent and children since we want to omit them.
        new_copy._parent = None
        new_copy._children = []

        return new_copy

    # Methods for creating an XML tree from the cache.
    def __create_xml_tree(self, ancestor):
        '''THIS IS A PRIVATE CLASS METHOD

           Returns an XML tree for this object and all its decendents.
           Converts current object to XML and then recursively calls
           itself on all its children to append them to the XML tree.

           Slightly complicated because any object in the tree
           can return None from its to_xml() function, in which case
           we need to 'skip' that generation and append its children
           to their grandparent (or older ancestor) instead of parent.

           When called initially (ie other than when it calls itself
           recursively), the ancestor parameter should be None.

           If the top-level object's to_xml() returns None, a 'root'
           XML node is created to head the tree.
        '''

        # Need to know if we're using a dummy element.
        using_dummy = False

        element = self.to_xml()

        if ancestor is None:
            # should only be True when called initially
            if element is None:
                # create a dummy XML element
                element = etree.Element("root")
                using_dummy = True

            ancestor = element

        # At this point, at least one of element or ancestor
        # will not be None.  We must attach the current object's
        # children to something, so use element first, or
        # ancestor if that is None
        attach_to = element
        if attach_to is None:
            attach_to = ancestor

        if not self.generates_xml_for_children:
            for child in self._children:
                sub = child.__create_xml_tree(attach_to)
                if sub is not None:
                    attach_to.append(sub)

        # If we created a dummy element, but there are no sub-tags then
        # we should not return it.
        if using_dummy:
            if len(element) != 0:
                return element
            else:
                return None

        return element

    def get_xml_tree(self):
        '''Returns an XML tree for this object and all its decendents.

        Calls self.__create_xml_tree() to do the work.'''

        return self.__create_xml_tree(None)

    #
    # Utility Methods
    #
    def get_xml_tree_str(self):
        '''Returns an string representing the cache contents in XML format.'''
        xml = self.get_xml_tree()
        if xml is not None:
            return etree.tostring(xml, pretty_print=True)
        else:
            return None

    def __str__(self):
        '''For debugging, produce an indented tree of children.

        If you want to change what is output for an sub-class then the
        method __repr__() should be overriden for the sub-class.
        '''
        line = ""
        ancestor = self._parent
        while ancestor is not None:
            # add 1 tab per generation
            line += "\t"
            ancestor = ancestor._parent

        line += "-> [%s] (%s)" % (self.name, repr(self))

        for child in self._children:
            line = line + "\n" + str(child)

        return line

    @property
    def object_path(self):
        ''' Generate path of this object relative to parents.

        The top parent object, the '/' root node doesn't have it's name
        included in the path, since it's releative to that object.

        Unusual characters in the name will be encoded like URLs.
        '''
        # Root node will be simply /, so prefix with "" so join works.
        my_path = [""]

        # Traverse up parents, but stop below root node to get correct which
        # doesn't include the root node's own name.
        parent = self
        while parent is not None and parent._parent is not None:
            my_path.insert(1, quote(parent._name, ""))
            parent = parent._parent

        return "/".join(my_path)

    def find_path(self, path_string, not_found_is_err=False):
        '''Fetches elements of the DataObject tree structure using a path.

        The provided path is broken down using tokens, which map as follows:

            /       => get_children()
                       First '/' would be the current object itself (root)

            //      => get_descendants()

            @type   => A fully-qualified class string which is mapped
                       to a class object. It is possible to omit the
                       qualification for classes in this module (e.g.
                       DataObject, etc).

            #num    => Max count (matches)

            ?num    => Max depth (with //)

            .attr   => An attribute of a matched object - always at the
                       end of the path - got via getattr (but would
                       omit '_' prefixed attrs).

        Special characters in a name can be encoded using URL type encoding,
        to avoid conflict with the above, for example:

            /%2A%2Fa%20b

        matches a child with the name "*/a b".

        Constraints should be in square brackets ([]), and attributes
        outside of the brackets, as follows:

            /<name>[<constraints>].attribute

        e.g.

            /my_name[@my_mod.MyClass].attr

        This method returns a list of matches to the criteria. The list will
        contain objects if no attribute is specified, otherwise it will
        contain the values of the attribute from each matched object.

        The '/' root node is the 'self' reference, so it's name is not
        included in a path, since it's releative to this object.

        Exceptions:

            PathError       - Raised if invalid path is provided.

            ObjectNotFoundError
                            - Raised if no match for the given path is found,
                              and not_found_is_err is True.

            AttributeError  - Raised if there is an attempt to match to an
                              attribute that doesn't exist, or if you try to
                              access an internal attribute (starts with '_')

        '''

        # Used to enforce a max_depth if only one '/' specified.
        max_depth = None
        # Tokenize string specific to this level, will call recursively.
        matched = list()
        remaining_path = None
        if (path_string.startswith("//")):
            # Use descendants
            tokens = path_string.split("/", 3)
            to_eval = tokens[2]
            if (len(tokens) > 3 and tokens[3] != ""):
                remaining_path = "/" + tokens[3]
        elif (path_string.startswith("/")):
            # Use get_children OR max_depth = 1
            tokens = path_string.split("/", 2)
            to_eval = tokens[1]
            if (len(tokens) > 2 and tokens[2] != ""):
                remaining_path = "/" + tokens[2]
            max_depth = 1
        else:
            # Raise error
            raise PathError("Invalid path: '%s'" % (path_string))

        kwargs = self.__convert_to_kwargs(to_eval)

        # Remove attribute if found since it's not a valid parameter
        # to get_descendants
        attribute = None
        if "attribute" in kwargs:
            attribute = kwargs["attribute"]
            del kwargs["attribute"]

            if attribute.startswith("_"):
                raise AttributeError("Invalid attribute: '%s'" % (attribute))

        # Enforce a max_depth is we set one ourselves.
        if max_depth is not None:
            kwargs["max_depth"] = max_depth

        children = self.get_descendants(**kwargs)
        if remaining_path is not None:
             # Keep descending, don't include intermediate matches.
            child_matched = list()
            for child in children:
                try:
                    child_list = child.find_path(remaining_path)
                    child_matched.extend(child_list)
                except ObjectNotFoundError:
                    pass
            matched.extend(child_matched)
        else:
            # As deep as possible, return these children.:
            matched.extend(children)

        if len(matched) == 0 and not_found_is_err:
            raise ObjectNotFoundError("No children found matching : '%s'" %
                (path_string))

        if attribute is not None:
            attr_values = list()
            for match in matched:
                # getattr() will generate AttributeErrors if invalid attribute.
                attr_values.append(getattr(match, attribute))
            return attr_values
        else:
            return matched

    def str_replace_paths_refs(self, orig_string, value_separator=",",
                               quote=False):
        """ Replace the %{...} references to DOC values with strings.

        Returns a new string with the values replaced.

        Multiple matches are concatenated using the value of the argument
        'value_separator', e.g.

            val1,val2,val3

        By, default, with a 'quote' value of False, the value of each matched
        object is created by calling 'str()' on the object or attribute.

        If the value of 'quote' is True, then the value for each matched object
        will be surrounded by single-quotes, unless the value itself is a
        string, then the quoting is done using repr() which handles escaping of
        quotes within strings too.

        If the references are not valid, the exceptions from the
        DataObjectBase.find_path() will be passed on.
        """

        if quote:
            quote_str = "'"
        else:
            quote_str = ""

        new_string = orig_string
        for matches in re.finditer(
            DataObjectBase.__STRING_REPLACEMENT_RE, orig_string):
            path = matches.group(1)
            if path is not None:
                # find_path() throws an exception if no match found.
                found_list = self.find_path(path, not_found_is_err=True)
                value_str = ""
                # Combine with SEPARATOR, using repr to get usable text values
                # since it automatically quotes if it is a string.
                for value in found_list:
                    if quote and isinstance(value, basestring):
                        # Use repr() for strings since it handles quoting and
                        # escaping of quotes in strings well.
                        new_val_str = repr(value)
                    else:
                        new_val_str = "%s%s%s" % \
                            (quote_str, str(value), quote_str)
                    if value_str == "":
                        value_str = new_val_str
                    else:
                        value_str += "%s%s" % (value_separator, new_val_str)

                self.logger.debug("Replacing reference to '%s' with '%s'" %
                    (matches.group(0), value_str))
                new_string = new_string.replace(matches.group(0),
                    value_str, 1)

        return new_string

    @staticmethod
    def __locate_class_by_name(class_name):
        '''Locates a class by name, using modules already loaded

        The class_name should in general be fully-qualified, i.e. it should be
        using something like:

            package.module.Class

        but, we will assume that an un-qualified class name is part of this
        module to allow for short-hand.
        '''

        # Do we have a fully-qualifed class-name - containing dots
        mod_name = None
        class_not_qualified = False
        mods = class_name.split(".")
        if len(mods) > 1:
            mod_name = ".".join(mods[:-1])
            class_name_only = mods[-1:][0]
        else:
            # Assume it's relative to own module, for now.
            mod_name = DataObjectBase.__module__
            class_name_only = class_name
            class_not_qualified = True

        try:
            mod = sys.modules[mod_name]
        except KeyError:
            raise PathError("Invalid module name: %s" %
                (mod_name))

        if hasattr(mod, class_name_only):
            class_obj = getattr(mod, class_name_only)
        else:
            if class_not_qualified:
                # Don't confuse user with reference to module
                # they didn't provide
                raise PathError("Invalid non-qualified class name: %s" %
                    (class_name))
            else:
                raise PathError("No such class %s in module %s" %
                    (class_name_only, mod_name))

        return(class_obj)

    @staticmethod
    def __convert_to_kwargs(value_string):
        '''Convert a path element to a series of kwargs for get_descendants'''
        args = dict()
        match = DataObjectBase.__NAME_RE.match(value_string)
        if match:
            args["name"] = unquote(match.group(1))
        match = DataObjectBase.__TYPE_RE.match(value_string)
        if match:
            args["class_type"] = \
                DataObjectBase.__locate_class_by_name(unquote(match.group(1)))

        # If neither specified assume DataObjectBase for the class_type
        if "name" not in args and "class_type" not in args:
            args["class_type"] = DataObjectBase

        match = DataObjectBase.__COUNT_RE.match(value_string)
        if match:
            args["max_count"] = int(unquote(match.group(1)))
        match = DataObjectBase.__DEPTH_RE.match(value_string)
        if match:
            args["max_depth"] = int(unquote(match.group(1)))
        match = DataObjectBase.__ATTR_RE.match(value_string)
        if match:
            args["attribute"] = unquote(match.group(1))

        return args


class DataObject(DataObjectBase):
    '''A variant of DataObjectBase which allows insertion and deletion.

    This is the class that most people will sub-class when creating
    an object for insertion in to the Data Object Cache.
    '''

    # Methods for adding objects to the cache and deleting them from it.
    def insert_children(self, new_children, before=None, after=None):
        '''Inserts new_children into the list of children.

        By default, 'new_children' will be appended to the existing list. The
        value for 'new_children' may be a single DataObject instance,
        or a list of DataObject instances.

        If 'before' is specified, and is an existing child, then this method
        will insert the new_children before it.

        If 'after' is specified, and is an existing child, then this method
        will insert the new_children after it.

        Exceptions:

        ObjectNotFoundError
            If either 'before' or 'after' are not existing children then this
            exception will be raised.

        TypeError
            This is raised if new_children is not a DataObjectBase instance,
            or is a list containing objects that are not DataObjectBase
            instances.

        ValueError
            This is raised if both 'before' and 'after' are specified, only
            one should be specified.

        '''

        insert_at = 0  # Where in list to insert new_children

        if before is not None and after is not None:
            msg = "Both 'before' and 'after' should not be specified."
            self.logger.error(msg)
            raise ValueError(msg)
        elif before is not None:
            self._check_object_type(before)
            try:
                insert_at = self._children.index(before)
            except ValueError:
                msg = "Invalid value for 'before' while inserting children"
                self.logger.error(msg)
                raise ObjectNotFoundError(msg)
        elif after is not None:
            self._check_object_type(after)
            try:
                insert_at = self._children.index(after) + 1
            except ValueError:
                msg = "Invalid value for 'after' while inserting children"
                self.logger.error(msg)
                raise ObjectNotFoundError(msg)
        else:
            insert_at = len(self._children)

        # Prefer to use DataObject i/f over an iterable object.
        if isinstance(new_children, DataObjectBase):
            # Single instance of DataObject, and put it in a list.
            new_children = [new_children]

        # Check for iterator support on object, raises exception if not
        offset = 0
        for child in new_children:
            self._check_object_type(child)
            self._children.insert(insert_at + offset, child)
            child._parent = self
            offset += 1

    def __delete_child(self, child, not_found_is_err=False):
        '''THIS IS A PRIVATE CLASS METHOD

        Internal utility method, to remove a specfic child, primarily
        used by delete_children() method.

        Will attempt to remove from self._children list and if it succeeds,
        then it will set the removed child's parent to None.
        '''
        self._check_object_type(child)
        try:
            self._children.remove(child)
            child._parent = None
        except ValueError:
            if not_found_is_err:
                raise ObjectNotFoundError(
                    "Failed to remove non-existant object '%s'" %
                    (str(child)))

    def delete_children(self, children=None, name=None, class_type=None,
                        not_found_is_err=False):
        '''This method deletes children from this DataObject.

        Without any parameters, it will delete all children of this object.

        You can limit the deletion, by specifying either:

        children    - This can be either a single DataObject, or a list of
                      DataObjects. When specified, only these specific objects
                      will be deleted.

                      If this is provided, then the name and class_type
                      parameters will be ignored.

        or one, or both of the following:

        name        - When specified, this will search for children objects
                      with the specified name value, and delete those objects.

        class_type  - When specified this will delete any children with the
                      provided class_type.

        The following exceptions are thrown by this method:

        ObjectNotFoundError  - This will be thrown if no suitable match for the
                          criteria is found, and not_found_is_err is True,
                          otherwise a non-existant object will be ignored.

        TypeError       - This will be returned if any of the parameters
                          have invalid types.

        '''

        if not self.has_children and name is None and class_type is None:
            # Nothing to be done.
            return

        # If a list of specific children is provided, it takes precedence
        # over any criteria. Handle these specific children now and return
        # when finished.
        if children is not None:
            if isinstance(children, DataObjectBase):
                self.__delete_child(children, not_found_is_err)
            else:
                # Assume iterable
                for child in children:
                    self.__delete_child(child, not_found_is_err)
            # All done now, so return.
            return

        # Delete based on search criteria, or all children
        deleted_children = False

        # Need to loop over a copy of the list since doing otherwise
        # causes some items to be missed, so uses .children property
        # as opposed to self._children.
        for child in self.children:
            delete_child = False
            if name is None and class_type is None:
                delete_child = True
            elif class_type is None and name == child.name:
                delete_child = True
            elif name is None and isinstance(child, class_type):
                delete_child = True
            elif name == child.name and isinstance(child, class_type):
                delete_child = True

            if delete_child:
                self.__delete_child(child, not_found_is_err)
                deleted_children = True

        if not deleted_children and not_found_is_err:
            raise ObjectNotFoundError(\
                "No matching objects found: name = '%s' "
                "and class_type = %s" %
                (str(name), str(class_type)))

    def delete(self):
        '''Recursively deletes an object

        Will remove itself from it's parent and removes it's children
        from the tree too.
        '''
        for child in self._children:
            child.delete()

        if self._parent is not None:
            self._parent._children.remove(self)
