#/usr/bin/python

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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.

# =============================================================================
# =============================================================================
# TreeAcc.py - XML DOM tree access and manipulation module
# =============================================================================
# =============================================================================

import new
import xml.dom.ext
from xml.dom.ext.reader import Sax2
from xml.dom import Node
from xml.dom.NodeFilter import NodeFilter
from xml.dom import Document
import errno

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

class TreeAccError(Exception):
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

	# Classbound constants

	# Specify this node represents an attribute or an element.
	ATTRIBUTE = Node.ATTRIBUTE_NODE
	ELEMENT = Node.ELEMENT_NODE

	# Instance methods

	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __init__(self, name, type, value, attr_dict, element_node, tree):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Constructor.

		Args:
		  name:	String to identify this node.  Used as part of a
			pathname when the tree is traversed.  Must be specified.
			No default.

		  type:	Value describing what this node represents. Must be one
			of TreeAccNode.ATTRIBUTE or TreeAccNode.ELEMENT.
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

		Returns:
		  an initialized TreeAccNode element

		Raises:
		  InvalidArgError: An invalid argument was specified.  A more
			specific message is embedded in the exception object.
			See description of args above for details.
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		if (name == None):
			raise InvalidArgError, (
			    "TreeAccNode init: name cannot be None")

		if ((type != TreeAccNode.ELEMENT) and
		    (type != TreeAccNode.ATTRIBUTE)):
			raise InvalidArgError, (
			    "TreeAccNode init: invalid type")

		if ((type == TreeAccNode.ATTRIBUTE) and (value == None)):
			raise InvalidArgError, (
			    "TreeAccNode init: missing attribute value")

		if (element_node == None):
			raise InvalidArgError, (
			    "TreeAccNode init: missing element_node arg")

		self.__name = name
		self.__type = type
		if (value == None):
			self.__value = ""
		else:
			self.__value = value
		self.__attr_dict = attr_dict
		self.__element_node = element_node
		self.__tree = tree
		if (type == TreeAccNode.ATTRIBUTE):
			self.__path = self.__path_to_parent(name)
		else:
			self.__path = self.__path_to_parent()


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Accessor methods
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_name(self):
		"""Return the string name of this node."""
		return self.__name

	def get_path(self):
		"""Return the path from the root to this node."""
		return self.__path

	def get_value(self):
		"""Return the string value of this node."""
		return self.__value

	def get_attr_dict(self):
		"""Return the attributes as name-value pairs."""
		return self.__attr_dict

	def get_tree(self):
		""" Return a reference to the tree instance."""
		return self.__tree

	def get_element_node(self):
		"""Return the corresponding DOM element of this node."""
		return self.__element_node

	def is_leaf(self):
		"""Return True or False that this node has no children.

		This is most relevant to elements, which are checked
		dynamically for children.  Only child elements are considered
		to be children here.

		Accommodate queries to attribute nodes by always returning True
		for them.
		"""

		if (self.is_attr()):
			return True
		return (
		    self.__element_node.getElementsByTagName("*").length == 0)

	def is_attr(self):
		"""Return True or False that this node represents an ATTRIBUTE.
		"""
		return (self.__type == TreeAccNode.ATTRIBUTE)

	def is_element(self):
		"""Return True or False that this node represents an ELEMENT."""
		return (self.__type == TreeAccNode.ELEMENT)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __path_to_parent(self, attr_string=None):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Build path string from root to current TreeAccNode.  This path string
	# may be used to get to this node from the tree root.
	#
	# Args:
	#   attr_string: If this TreeAccNode represents an ATTRIBUTE, this arg
	#	is the final branch string in the path being built
	#	(representing the attribute name).  Intended to be left off
	#	for ELEMENTs.  Defaults to None.
	#
	# Returns:
	#   String pathname with "/" in between the parts.
	#
	# Raises: None
	#
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		path = ""
		curr_node = self.__element_node

		while ((curr_node != None) and
		    (curr_node.nodeType != Node.DOCUMENT_NODE) and
		    (curr_node.parentNode.nodeType != Node.DOCUMENT_NODE)):
			if (path != ""):
				path = curr_node.nodeName + "/" + path
			else:
				path = curr_node.nodeName
			curr_node = curr_node.parentNode

		# Attribute name goes last in string if applicable.
		if (attr_string != None):
			path = path + "/" + attr_string

		return path


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __repr__(self):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Build and return a full string representation of this object.
	#
	# Args: None.
	#
	# Returns: a full string representation of this object.
	#
	# Raises: None.
	#
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
	"""Tree Access class.

	An abstraction layer representing a DOM tree.  Tree traversals are done
	with paths.  Similar to Unix pathnames, branches are separated by "/".
	Each branch represents an element by name or an attribute by name (last
	branch only). Parent nodes can be represented by ".."

	The tree as seen by users of this class supports only ELEMENTs and
	ATTRIBUTEs.

	Functionality exists to search the tree from the root and from the
	middle, add new elements and attributes, replace values of existing
	elements and attributes, and saving the tree in an XML document.

	The underlying DOM tree is created when an instance of this class is
	instantiated.
	"""

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
			attr_dict[
			    attr_node.nodeName] = attr_node.nodeValue.strip()
		return attr_dict


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	@staticmethod
	def __get_element_value(element_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	# Private method.  Return the value associated with a given element.
	#
	# Operates on a DOM element node to traverse its children looking for
	# a text node containing its value.  Assume there is only one child
	# text node.  (Multiple text nodes are more for HTML where, say bolded
	# parts of a string are in their own text nodes.  Not applicable here.)
	#
	# Args:
	#   element_node: The node to get the associated value.
	#
	# Returns:
	#   The string value of the element.  Returns None if there is no value.
	#
	# Raises: None
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		value = ""
		for child in element_node.childNodes:
			if (child.nodeType == Node.TEXT_NODE):
				value = value + child.nodeValue
		return value.strip()


	# Instance methods
	
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __init__(self, xml_file):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Constructor.  Given an xml file, creates the DOM tree and
		its TreeAcc representation.

		Args:
		  xml_file: XML file name.  No default.

		Returns:
		  an initialized TreeAcc instance

		Raises:
		  IOError: xml_file could not be opened.
		  SAXParseException: xml_file is not a well formed XML file

		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		# create Reader object
		reader = Sax2.Reader()

		# parse the document
		self.treedoc = reader.fromStream(open(xml_file.strip()))

		# Save root document element.
		self.treeroot = self.treedoc.documentElement

		# Create a TreeAccNode representation of the root element.
		# It will be used as a default for find_node() and other methods
		value = TreeAcc.__get_element_value(self.treeroot)
		attrs = TreeAcc.__create_attr_dict(self.treeroot)
		self.treeroot_ta_node = TreeAccNode(self.treeroot.nodeName,
		    TreeAccNode.ELEMENT, value, attrs, self.treeroot, self)

		# Define find_node() here.  Must be done inside __init__()
		# in order for find_node to take an instance variable as an
		# argument default.
		# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		def find_node(self, path,
		    starting_ta_node=self.treeroot_ta_node):
		# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			"""Initiate a search.  Node to find is specified by path

			Args:
			  path: Specifies node to search for.  This is a
				starting-node-to-destination node path of
				element and attribute names separated by "/".
				No default.

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
			  None: An empty list if no matching node is found.

			Raises:
			  InvalidArgError: path cannot start with a /

			"""
		# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
			if (starting_ta_node == None):
				starting_ta_node = self.treeroot_ta_node

			# Actual searching uses DOM tree elements.
			starting_node = starting_ta_node.get_element_node()

			# List of found nodes.  __search_node will add to it.
			found_nodes = []

			# Break path into a list.
			path = path.strip()

			# Disallow paths which start with a /
			if ((len(path) > 0) and (path[0] == '/')):
				raise InvalidArgError, (
				    "find_node: path cannot start with a /")

			pathlist = path.split("/")

			# Strip list of blank elements caused by extra "/"
			try:
				for i in range(len(pathlist)):
					pathlist.remove("")
			except ValueError:
				pass

			# Perform the search.
			self.__search_node(starting_node, pathlist, found_nodes)

			return found_nodes

		# Enlarge the scope of find_node() to be per instance.
		self.find_node = new.instancemethod(find_node, self, TreeAcc)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def __search_node(self, curr_node, path_pieces, found_nodes):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		""" Private recursive workhorse method used to search the tree.

		Args:
		  curr_node: Current DOM node being checked.  Supports checking
			only for elements and attributes.

		  path_pieces: list of path pieces (branches or names of
			current and subsequent nodes to search)

		  found_nodes: list of TreeAccNodes, one per found node.

		Returns: N/A

		  Appends found nodes to the list passed in as found_nodes

		Raises: None
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		value = None	# Value of found items, marks if something found

		# Handle "parent node" processing.  No need to recurse.
		while ((len(path_pieces) > 0) and (path_pieces[0] == "..")):

			path_pieces = path_pieces[1:]
			if ((curr_node.parentNode != None) and
			    (curr_node.parentNode.nodeType ==
			    Node.ELEMENT_NODE)):
				curr_node = curr_node.parentNode

				# Handle ".." at the end of a path, mid-tree.
				# Must be an element as we've stepped back from
				# a possible path end.
				value = self.__get_element_value(curr_node)
				attrs = TreeAcc.__create_attr_dict(curr_node)
				if (len(path_pieces) == 0):
					found_nodes.append(TreeAccNode(
					    curr_node.nodeName,
					    TreeAccNode.ELEMENT,
					    value, attrs, curr_node, self))
					return

		# At treetop because of too many ".." branches
		if (len(path_pieces) == 0):
			found_nodes.append(self.treeroot_ta_node)
			return

		# Search children of current node for elements matching the
		# name of this path branch (path_pieces[0]).
		for child in curr_node.childNodes:

			# Disregard anything that is not an element.
			if (child.nodeType != Node.ELEMENT_NODE):
				continue

			# Found a match.
			if (child.nodeName == path_pieces[0]):

				# Not at the end of the path.  Recurse.
				if (len(path_pieces) > 1):
					self.__search_node(child,
					    path_pieces[1:], found_nodes)
					continue

				# At the end of the path.  Get the value and
				# attributes.
				value = self.__get_element_value(child)
				attrs = TreeAcc.__create_attr_dict(child)

				# Save the result for return.
				found_nodes.append(TreeAccNode(child.nodeName,
				    TreeAccNode.ELEMENT, value, attrs, child,
				    self))
				continue # Could have mult matching children

		# If trying to resolve the last part of the path, the name
		# could represent either an element or an attribute.  No element
		# was found.  Check attributes.
		if ((len(path_pieces) == 1) and (value == None)):
			attr_node = curr_node.getAttributeNode(path_pieces[0])
			if (attr_node == None):	# No matching attribute.
				return

			# Append found match to found_nodes.
			attr_dict = {}
			attr_dict[path_pieces[0]] = attr_node.nodeValue
			found_nodes.append(TreeAccNode(path_pieces[0],
			    TreeAccNode.ATTRIBUTE, attr_node.nodeValue,
			    attr_dict, curr_node, self))
		return


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
		# Search for the target.
		if (starting_ta_node == None):
			matches = self.find_node(path)
		else:
			matches = self.find_node(path, starting_ta_node)

		# No match.
		if (len(matches) == 0):
			raise NodeNotFoundError, (
			    "replace_value: node %s not found" % path)

		# Multiple matches.
		if (len(matches) > 1):
			raise PathNotUniqueError, (
			    "replace_value: path %s matches multiple nodes" %
			    path)

		# Get the DOM element node of the one match.  If the target
		# is an attribute, retrieve the element node that attribute is
		# associated with.
		element_node = matches[0].get_element_node()

		# Attribute.
		if (matches[0].is_attr()):

			# The last branch of the path is the attribute name.
			attr_name_delim = path.rfind("/")
			if (attr_name_delim >= 0):
				attr_name = path[attr_name_delim+1:]
			else:
				# Special case: whole path is only one branch
				attr_name = path

			# Change the attribute value.
			element_node.setAttribute(attr_name, new_value)

		# Element.
		else:
			# Change the element value.
			self.__set_element_value(element_node, new_value)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def add_node(self, path, value, type, starting_ta_node=None,
	    is_unique=True):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		""" Add a new element or attribute node at "path".

		Args:
		  path: Location to add the new node.

		  value: value of the new node.  Must be provided for
			ATTRIBUTEs.  May be None for ELEMENTs.

		  type: One of TreeAccNode.ELEMENT or TreeAccNode.ATTRIBUTE.

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
			- type is not TreeAccNode.ELEMENT nor
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
		if ((type != TreeAccNode.ELEMENT) and
		    (type != TreeAccNode.ATTRIBUTE)):
			raise InvalidArgError, "invalid type specified"

		# Enforce arg restrictions applicable when adding attributes.
		if (type == TreeAccNode.ATTRIBUTE):
			if (value == None):
				raise InvalidArgError, (
				    "add_node: missing attribute value")
			if (is_unique == False):
				raise InvalidArgError, (
				    "add_node: is_unique must be True when "
				    "adding attributes")

		# Note: can have non-unique attribute paths, as can have same
		# attribute on sibling elements, e.g. two users both have
		# username attributes.

		# Note: cannot optimize by checking parent first and then
		# searching for matches below it.  Code is more optimal the way
		# it is.  If there are multiple (cousin) parent nodes with same
		# path, we would have to do separate searches below each parent,
		# for matches on the node path we want to add.

		# Search for an existing node with the given path.
		if (starting_ta_node == None):
			matches = self.find_node(path)
		else:
			matches = self.find_node(path, starting_ta_node)

		# Have at least one match for an existing node.
		if (len(matches) > 0):
			if (is_unique):
				raise NodeExistsError, (
				    "add_node: Node with given path %s exists" %
				    path)

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
						raise AmbiguousParentNodeError,(
						    "add_node: multiple nodes "
						    "matching %s don't have "
						    "common parent" % path)

		# Strip off the last part of the path.  Save the result as the
		# parent.  Save the stripped part as the name of the new element
		# If there is no / then treat starting_ta_node as the parent.
		delim = path.rfind("/")
		if (delim == -1):
			new_name = path
			if (starting_ta_node == None):
				parent_element = self.treeroot
			else:
				parent_element = \
				    starting_ta_node.get_element_node()
		else:
			# / in the path.  Need to search.
			new_name = path[delim+1:]
			parent_path = path[:delim]

			# Make sure parent exists.  Still need to do this even
			# if found parent above, to make sure that some other
			# node with matching parent path (but without a matching
			# child node) doesn't exist and introduce an ambiguity
			# of which parent is desired.
			if (starting_ta_node == None):
				matches = self.find_node(parent_path)
			else:
				matches = self.find_node(parent_path,
				    starting_ta_node)
			if (len(matches) == 0):
				raise ParentNodeNotFoundError, (
				    "add_node: parent node to %s not found" %
				    path)
			if (len(matches) > 1):
				raise AmbiguousParentNodeError, (
				    "add_node: multiple nodes matching %s "
				    "don't have common parent" % path)

			# No conflicts.  Do it.
			parent_element = matches[0].get_element_node()

		# Add the new node and return a new TreeAccNode.
		if (type == TreeAccNode.ATTRIBUTE):
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
			if (value != None):
				new_text = self.treedoc.createTextNode(value)
				new_element.appendChild(new_text)
			return TreeAccNode(new_name, TreeAccNode.ELEMENT, value,
			    {}, new_element, self)


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_tree_walker(self):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return an object to pass repeatedly to walk_tree()

		Passing the same object to walk_tree() facilitates a DOM
		tree walk. Holds state of the walk.

		Args: None

		Returns: a fresh object to pass to walk_tree() which will
			have walk_tree() start a new walk with its first call.

		Raises: None
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		walker = self.treedoc.createTreeWalker(
		    self.treedoc.documentElement,
		    NodeFilter.SHOW_ELEMENT, None, 0)
		curr_node = walker.currentNode
		return TreeWalker(walker, curr_node)


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

		Raises: XXX Try a bogus walker and find out!!!
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		ret_node = tree_walker.curr_node
		if (ret_node == None):
			return None

		tree_walker.curr_node = tree_walker.walker.nextNode()
		return self.get_TreeAccNode_cluster_from_element(ret_node)


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
			print "open out_file = " + out_file
			fp = open(out_file, "w")
		except IOError, err:
			raise FileOpenError, errno.errorcode[err.errno]

		# Write the data.
		try:
        		xml.dom.ext.Print(self.treedoc, fp)
		except IOError, err:
			raise FileSaveError, errno.errorcode[err.errno]

		# Ignore errors on close.
		try:
			fp.close()
		except:
			pass


	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_TreeAccNode_from_element(self, element_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Create a TreeAccNode from a DOM element node.

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
	def get_TreeAccNode_cluster_from_element(self, element_node):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Return a list of TreeAccNodes from a DOM element node.

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

		retlist.append(self.get_TreeAccNode_from_element(element_node))
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
	# __set_element_value: Private method.  Set the value associated with
	# a given element.
	#
	# Operates on a DOM element node to traverse its children looking for
	# a text node containing its value.  Assume there is only one child
	# text node.  Changes the value of the text node.  Add a text node and
	# set its value, in case a text node doesn't already exist.
	#
	# Args:
	#   element_node: The node to set the associated value.
	#
	#   new_value: The new value to set.
	#
	# Returns: N/A
	#
	# Raises: None
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		for child in element_node.childNodes:
	 		if (child.nodeType == Node.TEXT_NODE):
 				child.nodeValue = new_value
 				return
		new_text = self.treedoc.createTextNode(new_value)
		element_node.appendChild(new_text)
