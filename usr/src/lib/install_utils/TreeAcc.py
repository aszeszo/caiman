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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.

# =============================================================================
# =============================================================================
"""
TreeAcc.py - XML DOM tree access and manipulation module
"""
# =============================================================================
# =============================================================================

import errno

from xml.dom import Node
from xml.dom import minidom
from xml.dom import DOMException
from xml.parsers.expat import ExpatError
from osol_install.ENParser import ENToken
from osol_install.ENParser import parse_nodepath
from osol_install.ENParser import ParserError

# =============================================================================
# Error handling.
# Declare new classes for errors thrown from this file's classes.
# =============================================================================

class FileOpenError(IOError):
    """Exception for errors opening files. """
    pass
class FileSaveError(IOError):
    """Exception for errors saving the xml tree. """
    pass

class TreeAccError(StandardError):
    """Base exception for non-system errors."""
    pass
class PathNotUniqueError(TreeAccError):
    """Exception for when a given path needs to be unique but is not."""
    pass
class NodeNotFoundError(TreeAccError):
    """Exception for when a given path doesn't refer to an existing node."""
    pass
class NodeExistsError(TreeAccError):
    """Exception for when a given path refers to an existing node."""
    pass
class ParentNodeNotFoundError(TreeAccError):
    """Exception for when a parent node to a given path does not exist."""
    pass
class AmbiguousParentNodeError(TreeAccError):
    """Exception for when a given path could refer to multiple parents."""
    pass
class InvalidArgError(TreeAccError):
    """Exception for when an argument is invalid."""
    pass
class BadNodepathError(TreeAccError):
    """Exception for when a bad nodepath is passed or a parser error ensues."""
    pass

# =============================================================================
class TreeAccNode:
# =============================================================================
    """Tree access node class.

    Methods of the TreeAcc class give and take TreeAccNode objects as
    arguments.  TreeAccNode objects provide easy access to elements in a
    DOM tree as well as those elements' attributes.  They also provide their
    node's path from the root.

    Currently only elements and attributes are supported.

    """
# =============================================================================

    # Classbound constants

    # Specify this node represents an attribute or an element.
    ATTRIBUTE = Node.ATTRIBUTE_NODE
    ELEMENT = Node.ELEMENT_NODE

    # Instance methods

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, name, node_type, value, attr_dict, element_node, tree):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor.

        Args:
          name:        String to identify this node.  Used as part of a
                pathname when the tree is traversed.  Must be specified.
                No default.

          node_type: Value describing what this node represents. Must be
                one of TreeAccNode.ATTRIBUTE or TreeAccNode.ELEMENT.
                Must be specified.  No default.

          value: String value of the represented attribute or element.
                No default.  May be set to None for ELEMENTS if there
                is no value.

          attr_dict: For elements, dictionary of attribute name-value
                pairs.  Ignored for ATTRIBUTEs.

          element_node: The corresponding DOM tree element node
                represented.  For ELEMENTs, "element_node" corresponds
                directly to the path piece represented by the "name"
                arg.  For ATTRIBUTEs, "element_node" corresponds to the
                path piece immediately preceding the piece represented
                by the "name" arg.  Must be specified.  No default.

          tree: Current tree instance.

        Raises:
          InvalidArgError: An invalid argument was specified.  A more
                specific message is embedded in the exception object.
                See description of args above for details.
        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (name is None):
            raise InvalidArgError, ("TreeAccNode init: name cannot be None")

        if ((node_type != TreeAccNode.ELEMENT) and
            (node_type != TreeAccNode.ATTRIBUTE)):
            raise InvalidArgError, ("TreeAccNode init: invalid node type")

        if ((node_type == TreeAccNode.ATTRIBUTE) and (value is None)):
            raise InvalidArgError, ("TreeAccNode init: " +
                                    "missing attribute value")

        if (element_node is None):
            raise InvalidArgError, ("TreeAccNode init: " +
                                    "missing element_node arg")

        self.__name = name
        self.__type = node_type
        if (value is None):
            self.__value = ""
        else:
            self.__value = value
        self.__attr_dict = attr_dict
        self.__element_node = element_node
        self.__tree = tree
        if (node_type == TreeAccNode.ATTRIBUTE):
            self.__path = self.__path_to_parent(name)
        else:
            self.__path = self.__path_to_parent()


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __eq__(self, other):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Implementation for == between two TreeAccNode objects.

        Args:
          other: Another object with which to compare the current object.

        Returns:
          True: The two objects are equivalent (though not necessarily
                identical).
          False: The two objects are not equivalent.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        try:
            # Unique nodes will have unique DOM node and type
            # combinations.
            rval = ((self.__element_node == other.get_element_node()) and
                    (self.is_element() == other.is_element()))
        except AttributeError:
            rval = False
        return rval


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __ne__(self, other):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Implementation for != between two TreeAccNode objects.

        Args:
          other: Another object with which to compare the current object.

        Returns:
          True: The two objects are not equivalent.
          False: The two objects are equivalent (though not necessarily
                identical).

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        return (not self.__eq__(other))


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Accessor methods
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_name(self):
        """ Return the string name of this node. """
        return self.__name

    def get_path(self):
        """ Return the path from the root to this node. """
        return self.__path

    def get_value(self):
        """ Return the string value of this node. """
        return self.__value

    def get_attr_dict(self):
        """ Return the attributes as name-value pairs. """
        return self.__attr_dict

    def get_tree(self):
        """ Return a reference to the tree instance. """
        return self.__tree

    def get_element_node(self):
        """ Return the corresponding DOM element of this node. """
        return self.__element_node

    def is_leaf(self):
        """ Return True or False that this node has no children.

        This is most relevant to elements, which are checked
        dynamically for children.  Only child elements are considered
        to be children here.

        Accommodate queries to attribute nodes by always returning True
        for them.

        """

        if (self.is_attr()):
            return True
        return (self.__element_node.getElementsByTagName("*").length == 0)

    def is_attr(self):
        """ Return True or False that this node represents an ATTRIBUTE. """
        return (self.__type == TreeAccNode.ATTRIBUTE)

    def is_element(self):
        """ Return True or False that this node represents an ELEMENT. """
        return (self.__type == TreeAccNode.ELEMENT)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __path_to_parent(self, attr_string=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Build path string from root to current TreeAccNode.  This path
        string may be used to get to this node from the tree root.

        Args:
          attr_string: If this TreeAccNode represents an ATTRIBUTE, this arg
                is the final branch string in the path being built
                (representing the attribute name).  Intended to be left off
                for ELEMENTs.  Defaults to None.

        Returns:
          String pathname with "/" in between the parts.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        path = ""
        curr_node = self.__element_node

        while ((curr_node is not None) and
               (curr_node.nodeType != Node.DOCUMENT_NODE) and
               (curr_node.parentNode.nodeType != Node.DOCUMENT_NODE)):
            if (path != ""):
                path = curr_node.nodeName + "/" + path
            else:
                path = curr_node.nodeName
            curr_node = curr_node.parentNode

        # Attribute name goes last in string if applicable.
        if (attr_string is not None):
            if (path != ""):
                path = path + "/"
            path = path + attr_string

        return path


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __repr__(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Build and return a full string representation of this object.

        Args: None.

        Returns: a full string representation of this object.

        Raises: None.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        is_element = is_attr = is_leaf = 'F'
        if (self.__type == TreeAccNode.ELEMENT):
            is_element = 'T'
        if (self.__type == TreeAccNode.ATTRIBUTE):
            is_attr = 'T'
        if self.is_leaf():
            is_leaf = 'T'
        ret_string = ("Name:%s, element:%c, attr:%c, leaf:%c" %
                      (self.__name, is_element, is_attr, is_leaf))
        ret_string += "\n    Value:" + self.__value
        ret_string += "\n    Path:" + self.__path
        ret_string += "\n    Attributes:"
        for key, value in self.__attr_dict.iteritems():
            ret_string += "\n        " + key + ": " + value
        return ret_string


# =============================================================================
class TreeWalker:
# =============================================================================
    """ Obtuse objects of this class are handed between
        TreeAcc.get_tree_walker() and TreeAcc.walk_tree()

    """
# =============================================================================

    def __init__(self, walker, curr_node):
        self.walker = walker
        self.curr_node = curr_node


# =============================================================================
class TreeAcc:
# =============================================================================
    """ Tree Access class.

    An abstraction layer representing a DOM tree.  Tree traversals are done
    with paths.  Similar to Unix pathnames, branches are separated by "/".
    Each branch represents an element by name or an attribute by name (last
    branch only). Parent nodes can be represented by ".."

    More sophisticated searching, where results are narrowed by matching
    values both along the way to the desired node, and values below the
    desired node, is supported.  Search methods take ENTokens, which
    represent tokens with names, subsearch paths and values, to support
    this more sophisticated searching.

    The tree as seen by users of this class supports only ELEMENTs and
    ATTRIBUTEs.

    Functionality exists to search the tree from the root and from the
    middle, add new elements and attributes, replace values of existing
    elements and attributes, and saving the tree in an XML document.

    The underlying DOM tree is created when an instance of this class is
    instantiated.

    """
# =============================================================================

    # Classbound constants

    # Set to True when adding a node which has to be unique.  Unique means
    # there would be no other node with the same parent and pathname.  It
    # does not extend to nodes with the same pathname but with different
    # parents.
    IS_UNIQUE = True

    # Classbound methods

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    def __create_attr_dict(element_node):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Create attributes dictionary from a DOM element node

        Args:
          element_node: DOM node to return attributes of.

        Returns:
          dictionary of attributes.  Can be empty.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        attr_dict = {}
        attr_map = element_node.attributes
        for i in range(attr_map.length):
            attr_node = attr_map.item(i)
            attr_dict[attr_node.nodeName] = attr_node.nodeValue.strip()
        return attr_dict


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    def __get_element_value(element_node):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method.  Return the value associated with a given element.

        Operates on a DOM element node to traverse its children looking for
        a text node containing its value.  Assume there is only one child
        text node.  (Multiple text nodes are more for HTML where, say bolded
        parts of a string are in their own text nodes.  Not applicable here.)

        Args:
          element_node: The node to get the associated value.

        Returns:
          The string value of the element.  Returns None if there is no value.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        value = ""
        for child in element_node.childNodes:
            if (child.nodeType == Node.TEXT_NODE):
                value = value + child.nodeValue

        value = value.strip()

        # Strip off any enveloping double or single quotes.  Such
        # quotes may surround element values in the manifest in order
        # to treat space characters as normal characters.  It is
        # undesirable for the enveloping quotes to be treated as part
        # of the string, for example, during comparisons.
        #
        # Note: this quote stripping isn't needed for strings stored as
        # attribute node values as such values already have their
        # enveloping single- or double quotes stripped off.
        #
        if ((len(value) > 2) and (value[0] == value[-1]) and
            ((value[0] == "\"") or (value[0] == "'"))):
	
            # Remove middle escaped quote chars for comparison.
            non_esc = value.replace(("\\" + value[0]), "")

            # if have more than the two quotes on the ends, keep all
            # as this is a list and quotes are needed..
            if (non_esc.count(non_esc[0]) == 2):
                return value[1:-1]

        return value


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    def __pathlist_has_dots(path_tokens):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method.  Checks the name of each path piece, and returns
            True if at least one is ".."

        Args:
          path_tokens: list of ENTokens to check

        Returns:
          True: at least one piece is named ".."
          False: otherwise

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        for ptoken in path_tokens:
            if (ptoken.name == ".."):
                return True
        return False


    # Instance methods
	
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, xml_file):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor.  Given an xml file, creates the DOM tree and
        its TreeAcc representation.

        Args:
          xml_file: XML file name.  No default.

        Raises:
          TreeAccError: Error opening xml file
          TreeAccError: Error parsing xml file

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Read file into memory.
        try:
            self.treedoc = minidom.parse(xml_file.strip())
        except IOError, err:
            raise TreeAccError, ("Error opening xml file %s: %s" %
                                (xml_file.strip(), errno.errorcode[err.errno]))
        except (DOMException, ExpatError), err:
            raise TreeAccError, ("Error parsing xml file %s" %
                                 (xml_file.strip()))

        # Save root document element.
        self.treeroot = self.treedoc.documentElement

        # Create a TreeAccNode representation of the root element.
        # It will be used as a default for find_node() and other methods
        value = TreeAcc.__get_element_value(self.treeroot)
        attrs = TreeAcc.__create_attr_dict(self.treeroot)
        self.treeroot_ta_node = TreeAccNode(self.treeroot.nodeName,
                                            TreeAccNode.ELEMENT, value, attrs,
                                            self.treeroot, self)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def find_node(self, path, starting_ta_node=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Initiate a search.  Node to find is specified by path

        Args:
          path: Specifies node to search for.  This is a
            starting-node-to-destination node path of
            element and attribute names separated by "/".
            Path for a search starting from the root does
            not have to start with the root node; if not
            given, it is implied.  No default.

          starting_ta_node: Where to start the search from.
            A TreeAccNode may be given to specify starting
            from the middle of the tree.  If left off or
            set to None, search starts from the tree root.
            Starting a search from the middle of the tree is
            useful to narrow the search to a unique node.

        Returns:
          If at least one matching node is found:
            A list of nodes which match the given path.
            These nodes could share the same parent or have
            a different ancestry (as cousins).
          If no matching node is found:
            An empty list

        Raises:
          BadNodepathError: Error parsing nodepath

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        try:
            return self.__find_node_w_pathlist(parse_nodepath(path),
                                               starting_ta_node)
        except ParserError, err:
            raise BadNodepathError, "Error parsing nodepath: " + str(err)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __find_node_w_pathlist(self, path_tokens, starting_ta_node=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private. Initiate a search.  Node to find is specified by
            path_tokens

        Args:
          path_tokens: Specifies nodes to search for.  This is a list of
          ENTokens, a parsed starting-node-to-destination node path
          of element and attribute names and values.  A list for a
          search starting from the root does not have to start with
          the root node; if not given, it is implied.  No default.

          starting_ta_node: Where to start the search from.
          A TreeAccNode may be given to specify starting from the
          middle of the tree.  If set to None, search starts from
          the tree root.  Starting a search from the middle of
          the tree is useful to narrow the search to a unique node.

        Returns:
          If at least one matching node is found:
            A list of nodes which match the given path.  These
            nodes could share the same parent or have a different
            ancestry (as cousins).
          If no matching node is found:
            An empty list

        Raises:
          ParserError: Errors generated while parsing the nodepath
          (see parser module for details)

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # List of found nodes.  __search_node will add to it.
        found_nodes = []

        # Start at tree root.
        if (starting_ta_node is None):
            starting_ta_node = self.treeroot_ta_node

            # As a convenience, the name of the root element doesn't
            # have to be provided as part of the pathname.  If it
            # is not at the beginning of element 0 (whether alone
            # or part of a more complicated element-0 string,
            # prepend just the name to path_tokens.

            root_name = starting_ta_node.get_name()
            if ((len(path_tokens) == 0) or
                (path_tokens[0].name != root_name)):
                path_tokens.insert(0, ENToken(root_name))

            # Note whether ".." is part of the path.
            pathlist_has_dots = self.__pathlist_has_dots(path_tokens)

            # Actual searching uses DOM tree elements.
            # No searching on an attribute is necessary here, since
            # beginning will always be the root element.
            self.__search_node(starting_ta_node.get_element_node(),
                               Node.ELEMENT_NODE, path_tokens,
                               found_nodes, None)

        # Start in the middle of the tree.
        else:
            # Handle empty path.
            if (len(path_tokens) == 0):
                found_nodes.append(starting_ta_node)
                return found_nodes

            # Get rid of leading "..".  If run out of tokens,
            # append the element ended up at and return
            start_node = self.__do_dots(path_tokens,
                                        starting_ta_node.get_element_node(),
                                        found_nodes, None)
            if (len(path_tokens) == 0):
                return found_nodes

            # Note whether ".." is part of the path.
            pathlist_has_dots = self.__pathlist_has_dots(path_tokens)

            #__search_node requires the first path token match the
            # starting node.  At this point starting_node is the
            # parent of the node represented by path_tokens[0].
            num_found_nodes = len(found_nodes)

            # pylint gets confused and thinks curr_node is a list.
            # pylint: disable-msg=E1103
            for child in start_node.childNodes:
                if ((child.nodeType == Node.ELEMENT_NODE) and
                    (child.nodeName == path_tokens[0].name)):
                    self.__search_node(child,
                                       Node.ELEMENT_NODE, path_tokens,
                                       found_nodes, None)
            if ((num_found_nodes == len(found_nodes)) and
                (len(path_tokens) == 1)):
                self.__search_node(start_node, Node.ATTRIBUTE_NODE,
                                   path_tokens, found_nodes, None)

        # If ".." is specified as part of the path, duplicate finds
        # of a single node are possible.  For example, given two nodes
        # "B" from a common parent "A", specifying "A/B/.." will return
        # two finds of (the same) A. This is because the search finds
        # both B's and then finds A when it goes up the tree following
        # the ".." from each B.  The search finds the same parent when
        # it searches for it through each of the parent's children.
        #
        # Check for and remove duplicates if ".." specified in the path.
        # There is no need to do this otherwise, and this checking can
        # be compute intensive if there are many nodes to check.
        # Chances are, though, that paths with ".." in them will be few
        # and far between, and that they will be for starting mid-tree
        # searches and so won't return many nodes.
        if (pathlist_has_dots):
            i = len(found_nodes) - 1
            while (i > 0):	# Don't need to check element 0

                # Search backwards looking for duplicates.
                check_node = found_nodes[i]
                count = found_nodes.count(check_node)

                # Remove count-1 nodes
                j = 1
                while (j < count):
                    # This removes the lower indexed dup.
                    found_nodes.remove(check_node)
                    j += 1
                i -= count	# Decr one beyond number removed

        return found_nodes


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __search_node(self, curr_node, node_type, path_tokens, found_nodes,
                      search_value):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private recursive workhorse method used to search the tree.

        Args:
          curr_node: Current DOM node being checked.  Supports checking
                only for elements and attributes.

        node_type: Node.ELEMENT_NODE or Node.ATTRIBUTE_NODE (unvalidated)

        path_tokens: list of path ENTokens which make up the nodepath
                (branches or names of current and subsequent nodes to
                search)

        found_nodes: list of TreeAccNodes, one per found node.

        search_value: Value to search for.
          If not None: Return the first node found which matches
                the nodepath, containing this value.  This mode
                is used when searching valpaths for a first
                match.
          If None: return all nodes which match the nodepath.
                This mode is used for all other (non valpath)
                searches.

        Returns: N/A
          Appends found nodes to the list passed in as found_nodes

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Dismiss empty paths.
        if (len(path_tokens) == 0):
            return

        # Search no further if a match is found and only one is needed.
        if ((search_value is not None) and found_nodes):
            return

        name = self.__match(path_tokens[0], curr_node, node_type)
        if (name is None):
            return

        # More path to follow.
        if ((len(path_tokens) > 1) and
            (node_type != Node.ATTRIBUTE_NODE)):

            path_tokens = path_tokens[1:]

            # Eat any next tokens with ".."
            # If run out of tokens, append the element ended up at,
            # conditionally on search_value, then return.
            curr_node = self.__do_dots(path_tokens, curr_node,
                                       found_nodes, search_value)
            if (len(path_tokens) == 0):
                return

            num_nodes_at_start = len(found_nodes)
            for child in curr_node.childNodes:
                if (child.nodeType != Node.ELEMENT_NODE):
                    continue
                self.__search_node(child, Node.ELEMENT_NODE,
                                   path_tokens, found_nodes, search_value)

                # Quit as specific sought value found.
                if ((search_value is not None) and
                    (len(found_nodes) > 0)):
                    break

            # No child elements match.  If at the end of the path,
            # maybe the remaining path piece represents an attribute
            if ((len(found_nodes) == num_nodes_at_start) and
                (len(path_tokens) == 1)):
                self.__search_node(curr_node, Node.ATTRIBUTE_NODE, path_tokens,
                                   found_nodes, search_value)

        elif (node_type == Node.ELEMENT_NODE):

            value = self.__get_element_value(curr_node)

            # Save if want all values, or if want a
            # specific value and node value matches.
            if ((search_value is None) or (search_value == value)):
                attrs = TreeAcc.__create_attr_dict(curr_node)
                found_nodes.append(TreeAccNode(name, TreeAccNode.ELEMENT,
                                               value, attrs, curr_node, self))

        else:	# Node.ATTRIBUTE_NODE
            attr_node = curr_node.getAttributeNode(name)

            # Save if all found nodes are desired, or if a specific
            # value is desired and node value matches.
            if ((search_value is None) or
                (search_value == attr_node.nodeValue)):

                # Append match to found_nodes.
                attr_dict = {}
                attr_dict[name] = attr_node.nodeValue
                found_nodes.append(TreeAccNode(name,
                                   TreeAccNode.ATTRIBUTE, attr_node.nodeValue,
                                   attr_dict, curr_node, self))


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __match(self, token, curr_node, node_type):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Check the current node for a match against the given token.  Return
        the name from the token if a match found, None otherwise.

        The token will be parsed into a name, and zero or more values and
        paths to those values (valpaths).

        The name of curr_node must match the name in the token in order for an
        affirmative value to be returned.  Value(s), if specified, are
        checked as well.

        If a value is specified in the token, then at least one node matching
        the valpath and value must be found in order for a "match" to be
        affirmed.  If only one value and no valpath is given, the current
        node is checked for a match on the value.

        Args:
          token: The path piece that is the match specification of the
                current node.

          curr_node: The current location (node) in the tree.  Name in token
                is checked against this node.  Any valpath specified is
                relative to this node.  If the token specifies a value but no
                valpath, the value is checked against this node.

          node_type: type of node: TreeAccNode.ELEMENT or TreeAccNode.ATTRIBUTE
                (Assumed to be valid.)

        Returns:
          the name from the given token, if all given parts of the token
                specification show a match.
        None: if at least one given part of the token specification does
                not match.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Current node name must match the name in the token.
        # Get value for later.
        if (node_type == TreeAccNode.ELEMENT):
            if (curr_node.nodeName != token.name):
                return None
            chk_value = self.__get_element_value(curr_node)
        else:
            attr_node = curr_node.getAttributeNode(token.name)
            if (attr_node is None):
                return None
            chk_value = attr_node.nodeValue

        # At least one value was specified.
        if (len(token.values) != 0):

            # No valpath specified.  Check value against this node.
            if (len(token.valpaths) == 0):
                if (token.values[0] != chk_value):
                    return None

            else:
                if (not self.__is_bracket_match(curr_node,
                    token.valpaths, token.values)):
                    return None
        return token.name


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __is_bracket_match(self, curr_node, valpaths, values):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Traverse valpaths looking for given values.  Recurse down the tree
        to traverse valpaths as appropriate.  If at least one node per each
        nodepath has a matching value, then a match on curr_node is
        considered found.

        Args:
          curr_node: Current location (node) in the tree.

          valpaths: List of nodepaths relative to curr_node, to be checked
                one-for-one for a value in values.

          values: List of values to check valpaths for.

        Returns:
          True: Every valpath[i] has at least one node with a value that
                matches values[i]
          False: otherwise

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Search each valpath and check against value
        for i in range(len(valpaths)):

            cmp_match = False
            vp_matches = []
            path_tokens = parse_nodepath(valpaths[i])

            # Eat any next tokens with ".."
            # If run out of tokens, append the element ended up at,
            # if its value matches values[i].

            curr_node = self.__do_dots(path_tokens, curr_node,
                                       vp_matches, values[i])
            if (len(vp_matches) > 0):
                cmp_match = True
                continue

            # do_dots() ate up the path, and no match found
            if ((len(path_tokens) == 0) and (not cmp_match)):
                return False

            if (not cmp_match):
                # pylint gets confused and thinks curr_node is a list.
                # pylint: disable-msg=E1103
                for child in curr_node.childNodes:
                    if (child.nodeType !=
                        Node.ELEMENT_NODE):
                        continue
                    self.__search_node(child, Node.ELEMENT_NODE, path_tokens,
                                       vp_matches, values[i])

                    # If no match, keep looping through
                    # other children.  There may be other
                    # nodes with the same path.  If found a
                    # match, go on to the next valpath to
                    # check.
                    if (len(vp_matches) > 0):
                        cmp_match = True
                        break

            # No child elements match.  If at the end of the path,
            # maybe the remaining path piece represents an attribute
            if ((not cmp_match) and (len(path_tokens) == 1)):
                self.__search_node(curr_node, Node.ATTRIBUTE_NODE, path_tokens,
                                   vp_matches, values[i])
                if (len(vp_matches) > 0):
                    cmp_match = True

            # If after checking all possibilities for a particular
            # valpath, nothing is found, then quit.  Must have a
            # match for all valpaths.
            if (not cmp_match):
                return False

        return True


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __do_dots(self, path_tokens, curr_node, found_nodes, search_value):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method.  Eats ".." in the path.  Moves curr_node up the
        tree one level with each ".." eaten, unless it is already at the top
        of the tree.  Append to found_nodes the final node arrived at if the
        path gets depleted, depending on search_value.

        NOTE: LIMITATION: attributes have to be the last thing in a nodepath
        when specified.  Having a ".." token after an attribute will always
        fail a search.  This limitation is justified as ".." is used to
        traverse elements to move about in the data tree, and it doesn't make
        much sense to use it with attributes.

        Args:
          path_tokens: list of path tokens.  Altered during execution.

          curr_node: current DOM node

          found_nodes: list of found nodes.  New current node is conditionally
                appended here if path_tokens are depleted.  (See search_value
                arg)

          search_value:
            if None: append the current node to found_nodes unconditionally.
            otherwise: append the current node to found_nodes if the
                current node's value matches this arg.

        Returns:
          New DOM node arrived at after eating ".."s.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        while ((len(path_tokens) > 0) and
               (path_tokens[0].name == "..")):

            # Here we pop instead of path_tokens = path_tokens[1:]
            # because we want the change to path_tokens to
            # propagate to the caller.  This is because the caller
            # will likely use the changed path to continue
            # recursing down the tree, and it needs the dots gone.
            #
            # Calling pop() is different than doing
            # path_tokens = path_tokens[1:].  The latter keeps the
            # original list in its original state.  It also creates
            # a new list without the first element and assigns
            # path_tokens to it.  In this case, the original list
            # will be intact for the caller's parent method (e.g. a
            # previous frame of __search_node) so that it can
            # recurse down the tree down a different path once
            # recursion down the current path is completed.
            path_tokens.pop(0)

            if ((curr_node.parentNode is not None) and
               (curr_node.parentNode.nodeType == Node.ELEMENT_NODE)):
                curr_node = curr_node.parentNode

        # Path tokens list exhausted.  Add current node to found_nodes.
        if (len(path_tokens) == 0):
            value = self.__get_element_value(curr_node)
            if ((search_value is None) or (value == search_value)):
                attrs = TreeAcc.__create_attr_dict(curr_node)
                found_nodes.append(TreeAccNode(curr_node.nodeName,
                                               TreeAccNode.ELEMENT, value,
                                               attrs, curr_node, self))

        # Return current DOM node in all cases.
        return curr_node


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def replace_value(self, path, new_value, starting_ta_node=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Replace the string value of an ELEMENT or ATTRIBUTE.

        Together, path and starting_ta_node define the target node.
        Replacement occurs only if one target matches.

        Args:
          path: path to ELEMENT or ATTRIBUTE to change, from the element
            passed as starting_ta_node, or full path from tree root
            if starting_ta_node is set to None or left off.
            No default.

          new_value: Replacement value.

          starting_ta_node: TreeAccNode to start a search from.
            If set to None or left off, search starts from the
            tree root.

        Returns: N/A

        Raises:
          NodeNotFoundError: No matches were found.

          PathNotUniqueError: multiple matches were found.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        path_tokens = parse_nodepath(path)

        # Search for the target.
        matches = self.__find_node_w_pathlist(path_tokens, starting_ta_node)

        # No match.
        if (len(matches) == 0):
            raise NodeNotFoundError, (("replace_value: node %s not " +
                                      "found") % path)

        # Multiple matches.
        if (len(matches) > 1):
            raise PathNotUniqueError, (("replace_value: path %s matches " +
                                        "multiple nodes") % path)

        # Get the DOM element node of the one match.  If the target
        # is an attribute, retrieve the element node that attribute is
        # associated with.
        element_node = matches[0].get_element_node()

        # Attribute.
        if (matches[0].is_attr()):

            # Change the attribute value.
            # The last branch of the path is the attribute name.
            element_node.setAttribute(path_tokens[-1].name, new_value)

        # Element.
        else:
            # Change the element value.
            self.__set_element_value(element_node, new_value)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def add_node(self, path, value, node_type, starting_ta_node=None,
                 is_unique=True):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Add a new element or attribute node at "path".

        Args:
          path: Location to add the new node.

          value: value of the new node.  Must be provided for
            ATTRIBUTEs.  May be None for ELEMENTs.

          node_type: One of TreeAccNode.ELEMENT or TreeAccNode.ATTRIBUTE.

          starting_ta_node: TreeAccNode to start a search from.
            If set to None or left off, search starts from the
            tree root.

          is_unique: If True, reject requests to add a second node with
            a given path and parent.  Must be True when adding
            ATTRIBUTEs.  Defaults to True.
            Note: TreeAcc.IS_UNIQUE = True

        Returns: On success, returns a new TreeAccNode representing the
            new node added to the tree.

        Raises:
          InvalidArgError:
            - node_type is not TreeAccNode.ELEMENT nor
                TreeAccNode.ATTRIBUTE
            - no value is specified when adding an ATTRIBUTE
            - is_unique is False when adding an ATTRIBUTE

          NodeExistsError: A node with identical parent and path
            already exists, and is_unique is True

          AmbiguousParentNodeError: Multiple nodes with identical path
            exist but with different parents.  Don't know which
            parent to add the new node to.

          ParentNodeNotFoundError: No parent to which to attach the new
            node has been found.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Type must be an ELEMENT or an ATTRIBUTE
        if ((node_type != TreeAccNode.ELEMENT) and
            (node_type != TreeAccNode.ATTRIBUTE)):
            raise InvalidArgError, "invalid type specified"

        # Enforce arg restrictions applicable when adding attributes.
        if (node_type == TreeAccNode.ATTRIBUTE):
            if (value is None):
                raise InvalidArgError, ("add_node: missing attribute value")
            if (not is_unique):
                raise InvalidArgError, ("add_node: is_unique must be True " +
                                        "when adding attributes")

        path_tokens = parse_nodepath(path)
        if (len(path_tokens) == 0):
            raise InvalidArgError, (
                                    "add_node: provided path is empty")

        # Note: can have non-unique attribute paths, as can have same
        # attribute on sibling elements, e.g. two users both have
        # username attributes.

        # Note: cannot optimize by checking parent first and then
        # searching for matches below it.  Code is more optimal the way
        # it is.  If there are multiple (cousin) parent nodes with same
        # path, we would have to do separate searches below each parent,
        # for matches on the node path we want to add.

        # Search for an existing node with the given path.
        matches = self.__find_node_w_pathlist(path_tokens, starting_ta_node)

        # Have at least one match for an existing node.
        if (len(matches) > 0):
            if (is_unique):
                raise NodeExistsError, ("add_node: Node with given " +
                                        "path %s exists" % path)

            # More than one match.
            # OK if all matching nodes have a comment parent.
            # Assume in this case that the caller wants the same
            # parent and has called this method with the right args
            # to achieve this.
            # If there is more than one parent, reject the request.
            if (len(matches) > 1):
                parent_element =	\
                    matches[0].get_element_node().parentNode
                for i in range(1, len(matches)):
                    if (parent_element is not
                        matches[i].get_element_node().
                        parentNode):
                        raise AmbiguousParentNodeError, (("add_node: " +
                                                          "multiple nodes " +
                                                          "matching %s " +
                                                          "don't have " +
                                                          "common parent") %
                                                          path)

        # Strip off the last part of the path.  Save the result as the
        # parent.  Save the stripped part as the name of the new element
        # If there is only one path_piece, then treat starting_ta_node
        # as the parent.
        new_name = path_tokens[-1].name
        if (len(path_tokens) == 1):
            if (starting_ta_node is None):
                parent_element = self.treeroot
            else:
                parent_element = starting_ta_node.get_element_node()
        else:
            # / in the path.  Need to search.
            parent_path_tokens = path_tokens[:-1]

            # Make sure parent exists.  Still need to do this even
            # if found parent above, to make sure that some other
            # node with matching parent path (but without a matching
            # child node) doesn't exist and introduce an ambiguity
            # of which parent is desired.
            matches = self.__find_node_w_pathlist(parent_path_tokens,
                                                  starting_ta_node)
            if (len(matches) == 0):
                raise ParentNodeNotFoundError, ("add_node: parent node to " +
                                                "%s not found" % path)
            if (len(matches) > 1):
                raise AmbiguousParentNodeError, (("add_node: multiple nodes " +
                                                  "matching %s don't have " +
                                                  "common parent") % path)

            # No conflicts.  Do it.
            parent_element = matches[0].get_element_node()

        # Add the new node and return a new TreeAccNode.
        if (node_type == TreeAccNode.ATTRIBUTE):
            # Note: parent_element here means the (element) node
            # corresponding to the parent path.  The attribute will
            # belong to this element.
            parent_element.setAttribute(new_name, value)
            attr_dict = {}
            attr_dict[new_name] = value
            return TreeAccNode(new_name, TreeAccNode.ATTRIBUTE,
                               value, attr_dict, parent_element, self)
        else:
            # For elements, add a new element node, and a new text
            # node to hold its value if a value is given.
            new_element = self.treedoc.createElement(new_name)
            parent_element.appendChild(new_element)
            if (value is not None):
                new_text = self.treedoc.createTextNode(value)
                new_element.appendChild(new_text)
            return TreeAccNode(new_name, TreeAccNode.ELEMENT, value,
                               {}, new_element, self)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_tree_walker(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Return an object to pass repeatedly to walk_tree()

        Passing the same object to walk_tree() facilitates a DOM
        tree walk. Holds state of the walk.

        Args: None

        Returns: a fresh object to pass to walk_tree() which will
            have walk_tree() start a new walk with its first call.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        return TreeWalker(self.__get_tree_walker_worker(self.treeroot),
                          self.treeroot)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __get_tree_walker_worker(self, curr_node):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Workhorse behind get_tree_walker.  Walks the tree.

        Args:
          curr_node: current node in the tree to resume walking from

        Yields: a generator representing a tree element node, which is updated
            with every call, and which can be passed repeatedly back into
            this iterator to get to the next tree element node.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Filter out non-element nodes
        if (curr_node.nodeType != Node.ELEMENT_NODE):
            return

        # Return current node and then iterate through children.
        yield curr_node

        for child in curr_node.childNodes:
            for child_gen in self.__get_tree_walker_worker(child):
                yield child_gen


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def walk_tree(self, tree_walker):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Walks the DOM tree.

        Args:
          walker object returned by get_tree_walker.  This arg gets
              changed with each call, and holds the state of the walk.

        Returns:
          A list of TreeAccNodes which correspond to the element node
            found plus its attributes.
          None: No more nodes to return for this walk.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        ret_node = tree_walker.curr_node
        if (ret_node is None):
            return None

        try:
            tree_walker.curr_node = tree_walker.walker.next()
        except StopIteration:
            tree_walker.curr_node = None
        return self.get_treeaccnode_clust_fm_elem(ret_node)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def save_tree(self, out_file):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Save the DOM tree to an XML file

        Args:
          out_file: File to write the XML to.  Any existing file
            contents will be overwritten.

        Returns: N/A

        Raises:
          FileOpenError: If file could not be opened.  Errno is
            embedded

          FileSaveError: If file could not be written.  Errno is
            embedded.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Open the file.
        try:
            fp = open(out_file, "w")
        except IOError, err:
            raise FileOpenError, errno.errorcode[err.errno]

        # If the original document contained a reference to an external
        # DTD, then reconstruct the DOCTYPE field and write it out at
        # the top of the output file.
        # (This is essential for loading DTD attribute defaults later.)
        if ((self.treedoc.doctype is not None) and
            (self.treedoc.doctype.name is not None) and
            (self.treedoc.doctype.systemId is not None) and
            (self.treedoc.doctype.systemId.endswith(".dtd"))):
            doctype_str = "<!DOCTYPE %s SYSTEM \"%s\">\n" % \
                (self.treedoc.doctype.name, self.treedoc.doctype.systemId)
            fp.write(doctype_str)

        # Write the data.
        # Pylint bug: See http://www.logilab.org/ticket/8764
        # pylint: disable-msg=C0321
        try:
            fp.write(self.treeroot.toprettyxml(
                     indent="", newl=""))
            fp.write("\n")
        except IOError, err:
            raise FileSaveError, errno.errorcode[err.errno]

        finally:
            # Ignore errors on close.
            try:
                fp.close()
            except IOError:
                pass


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_treeaccnode_from_element(self, element_node):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Create a TreeAccNode from a DOM element node.

        Args:
          element_node: DOM node to convert.
            Only element nodes are supported.

        Returns:
          TreeAccNode corresponding to the given DOM element node
          None: Given node is not a DOM element node.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Not a supported node.
        if (element_node.nodeType != Node.ELEMENT_NODE):
            return None

        # Build the TreeAccNode to return and return it
        name = element_node.nodeName
        value = TreeAcc.__get_element_value(element_node)
        attrs = TreeAcc.__create_attr_dict(element_node)
        return TreeAccNode(name, TreeAccNode.ELEMENT, value, attrs,
                           element_node, self)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_treeaccnode_clust_fm_elem(self, element_node):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Return a list of TreeAccNodes from a DOM element node.

        List of TreeAccNodes includes the TreeAccNode of the element
        node itself (always the first node in the returned list),
        plus any attribute nodes it carries.

        Args:
          element_node: DOM node to convert.
            Only element nodes are supported.

        Returns:
          The first node in the returned list corresponds to the DOM
            element itself.  Subsequent nodes correspond to any
              attribute nodes below it.
          None: Given node is not a DOM element node.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Not a supported node.
        if (element_node.nodeType != Node.ELEMENT_NODE):
            return None

        retlist = []

        retlist.append(self.get_treeaccnode_from_element(element_node))
        elem_attr_dict = retlist[0].get_attr_dict()

        # Build TreeAccNodes for any attributes.
        try:
            for attr, attrvalue in elem_attr_dict.items():
                attr_attr_dict = {}
                attr_attr_dict[attr] = attrvalue
                retlist.append(TreeAccNode(attr,
                               TreeAccNode.ATTRIBUTE, attrvalue,
                               attr_attr_dict, element_node, self))
        except StopIteration:
            pass

        return retlist

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __set_element_value(self, element_node, new_value):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method.  Set the value associated with a given element.

        Operates on a DOM element node to traverse its children looking for
        a text node containing its value.  Assume there is only one child
        text node.  Changes the value of the text node.  Add a text node and
        set its value, in case a text node doesn't already exist.

        Args:
          element_node: The node to set the associated value.

          new_value: The new value to set.

          Returns: N/A

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        for child in element_node.childNodes:
            if (child.nodeType == Node.TEXT_NODE):
                child.nodeValue = new_value
                return
        new_text = self.treedoc.createTextNode(new_value)
        element_node.appendChild(new_text)
