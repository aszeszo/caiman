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

'''
mim.py: Manifest Input Module.

Provides functionality to load, modify (via set, add, overlay), retrieve info,
validate and write out an XML manifest file.

Nodes are specified as a path from the root.  Throughout this module, a
"branch" is a part of a path between two unquoted or unbracketed slashes.

Nodepath provided can have branches of the following form:
/a              # element defined by tag
/a=5            # element defined by tag and value (non-leaf) or
                # assign a value to element defined by tag (leaf)
/a[b=6]         # element defined by tag, and tag and value of a child
/a[b/c=7]       # element defined by tag, and tag and value of
                # non-direct decendent
/a[2]           # element defined by tag and ID in tree
/a@attr         # (leaf) attribute defined by name and the element
                # it is a part of
/a@attr=8       # (leaf) element defined by tag, and the name and value
                # of an attribute it has.
/a[@attr=8]     # element defined by tag, and the name and value of an
                # attribute it has.
'''

import errno
import os
import re

from lxml import etree

import solaris_install.manifest_input as milib
import solaris_install.manifest_input.process_dtd as pdtd

STRIP_FINAL_UNBKT_VALUE = True

# --------------------------------------------------------------------------
# Regular expression definitions used by this module

IDENTIFIER = "[A-Za-z]\w*"

# Allowed element values are:
# - Any non-whitespace char except double quote, enveloped by double quotes
DBL_QUOTED_VALUE = "(\"[^ \t\n\r\f\v/\[\]=@\"]+\")"
# - Any non-whitespace char except single quote, enveloped by single quotes
SGL_QUOTED_VALUE = "('[^ \t\n\r\f\v/\[\]=@\']+')"
# - Any non-whitespace char except quotes and @/[]= when not enveloped by
#   quotes.
UNQUOTED_VALUE = "([^ \t\n\r\f\v\'\"/\[\]=@]+)"

# Any value, quoted or not.
VALUE = "(" + SGL_QUOTED_VALUE + "|" + DBL_QUOTED_VALUE + "|" + \
    UNQUOTED_VALUE + ")"

SUBPATH = IDENTIFIER + "(/" + IDENTIFIER + ")*"

# For handling .../node=value/... branches
UNBKT_NODE_VALUE_RE = re.compile("^" + IDENTIFIER + "=" + VALUE + "$")

# For handling .../node[subpath@attr=value]/... branches
# where node and attr may be left off.  (subpath and value are mandatory.)
ELEMENT_SUBPATH_RE = re.compile("^" + "(" + IDENTIFIER + ")?" + "\[" + \
    SUBPATH + "(@" + IDENTIFIER + ")?" + "=" + VALUE + "\]$")

# For handling .../node/... branches
IDENT_ONLY_RE = re.compile("^" + IDENTIFIER + "$")

# For unquoted values.
UNQUOTED_VALUE_RE = re.compile("^" + UNQUOTED_VALUE + "$")

# For handling .../node[subnode@attr=value]
# where node, and either subnode or attr are mandatory
BKT_NODE_UNQUOTED_VALUE_RE = re.compile("^" + IDENTIFIER + "\[" + \
    "((" + IDENTIFIER + ")?" + "@)?" + \
    IDENTIFIER + "=" + UNQUOTED_VALUE + "\]")

# Non-specific bracketed expression
BKT_NODE_VALUE_RE = re.compile("^" + IDENTIFIER + "\[.*=.*\]$")

# --------------------------------------------------------------------------


class ManifestInput(object):
    '''
    Class which implements the Manifest Input Module proper.
    Provides the functionality to manipulate XML files.
    '''

    def __init__(self, dest_file, schema_file=None):
        '''
        Instantiate a new object.  Initialization includes:

        - querying the environment for AIM_MANIFEST to get the manifest
        filename.  If named file is present, initialize data tree from it.
        If not set or file is not available, display a warning and continue.

        - Opening and storing the schema data.  Err out if not accessible or
        incorrect.

        - Call process_dtd module to create tables from DTD for ordering child
        nodes in the data tree.  These tables will be used for doing overlays.

        Args:
          dest_file: Pathname to the output file.

          schema_file: Pathname to the DTD file used.  Used only if the
              manifest does not name a DTD.  Optional, but if not specified
              here and manifest does not specify either, then an exception
              is raised.

        Raises:
          IOError - Could not access DTD file
          IOError - Could not digest DTD file
          MimDTDError - Etree error processing DTD data from file
          MimDTDError - SchemaData error processing DTD data from file
          MimEtreeParseError - Error parsing XML manifest file
          MimInvalidError - No output file name provided
          MimInvalidError - No schema name provided
          OSError from not being able to access the manifest

        Produces a warning, retrievable via get_warnings(), if AIM_MANIFEST
        environment variable is not defined.
        '''

        self._warnings = None

        if dest_file is None:
            raise milib.MimInvalidError(milib.ERR_NO_OUTFILE)

        self.dest_name = dest_file
        self.tree = None

        # Set up parser to remove blank text and processing instructions.
        # Have parser leave in comments, so they can be written out later.
        self.parser = etree.XMLParser(remove_blank_text=True, remove_pis=True)

        # Read manifest, if pathname provided in environment.
        # Continue on IO errors, as file may not exist yet.
        self.manifest_name = os.environ.get("AIM_MANIFEST")
        if not self.manifest_name:
            self._add_warning(milib.ERR_MFEST_NOENV)
        else:
            try:
                # Treat a zero length manifest as if it didn't exist.
                mfest_size = os.path.getsize(self.manifest_name)
            except OSError as err:
                if err.errno == errno.ENOENT:
                    mfest_size = 0
                else:
                    raise

            # Treat a zero length manifest as if it didn't exist.
            if mfest_size:
                self.tree = self.parse_xml_file(self.manifest_name,
                                                self.parser)

        # Open schema for validator, and build table of children order.

        # Use the schema refered to in the manifest itself, if it is listed in
        # the manifest and it exists.  Else use the schema passed in as an arg.
        if (self.tree and self.tree.docinfo and
            self.tree.docinfo.system_url and
            os.access(self.tree.docinfo.system_url, os.R_OK)):
            schema_file = self.tree.docinfo.system_url

        if schema_file is None:
            raise milib.MimInvalidError(milib.ERR_NO_SCHEMA)

        # Open schema for validator, and build table of children order.
        try:
            self.schema = etree.DTD(schema_file)  # For lxml validator
        except IOError as err:
            raise IOError(err.args[0], milib.IOERR_DTD_ACCESS %
                          {"mserr": err.strerror, "mfile": schema_file})
        except StandardError as err:
            raise milib.MimDTDError(milib.ERR_ETREE_PROC %
                              {"mfile": schema_file, "merr": str(err)})

        try:
            self.schema_data = pdtd.SchemaData(schema_file)  # For order table
        except IOError as err:
            raise IOError(err.args[0], milib.IOERR_DTD_DIGEST %
                          {"mserr": err.strerror, "mfile": schema_file})
        except milib.MimError as err:
            raise milib.MimDTDError(milib.ERR_SCHDATA_PROC %
                                {"mfile": schema_file, "merr": str(err)})

    def _add_warning(self, message):
        '''
        Add a warning message to return through the initialized object.

        Warnings are messages to be reported, but which are not serious enough
        to raise exceptions and impede progress.  Warnings must be requested by
        the calling program;  they are not printed by this module.

        Args:
          message: the message to add.

        Raises: N/A
        '''
        if self._warnings is None:
            self._warnings = [message]
        else:
            self._warnings.append(message)

    def get_warnings(self):
        '''
        Return warning messages.

        Since messages accumulate in the cache, they are returned only once.

        Args: N/A

        Raises: N/A

        Returns: list of warning messages
        '''
        ret = self._warnings
        self._warnings = None
        return ret

    @staticmethod
    def parse_xml_file(manifest_name, parser):
        '''
        Call etree.parse with proper exception handling.

        Args:
          manifest_name: XML file to parse

          parser: parser to use

        Returns:
          tree: XML data tree as set up by etree.parse

        Raises:
          MimEtreeParseError: Error parsing XML manifest.
        '''
        try:
            tree = etree.parse(manifest_name, parser)
        except IOError as err:
            # Note: errno or strerror not currently initialized
            # in IOErrors raised by etree.parse().
            raise milib.MimEtreeParseError(str(err))
        except StandardError as err:
            raise milib.MimEtreeParseError(milib.ERR_ETREE_PARSE_FILE %
                                     {"mfile": manifest_name,
                                      "merr": str(err)})
        return tree

    def load(self, overlay_filename, incremental=False):
        '''
        Args:
          overlay_filename: pathname or URL of XML file containing
          replacement data (if incremental=False) or data to overlay
          (incremental=True)

          incremental:
              True: overlay data on top of existing.
              False: replace existing data.

        Raises:
          MimInvalidError - Argument is missing or invalid
          MimEtreeParseError - IO errors or parser errors while parsing.
        '''
        if overlay_filename is None:
            raise milib.MimInvalidError(milib.ERR_ARG_INVALID)

        if (not incremental) or not self.tree:
            # Load a fresh tree.  Discard old data.
            self.tree = self.parse_xml_file(overlay_filename, self.parser)
        else:
            # Read tree of overlay data, then overlay it.
            overlay_tree = self.parse_xml_file(overlay_filename, self.parser)
            self._overlay_recurse(self.tree.getroot(), overlay_tree.getroot(),
                                  None)

    def getpath(self, element):
        '''
        Get path to current element, in a form to return to the user.

        If Xpath doesn't append an identifier to a node since there is only one
        of that node, append a [1] to it.  Do this because when a second
        like-tagged node is added,  Xpath will automatically append the [1] to
        the current node and we want the path to be consistent.

        Args:
          element: The element to return the path to.

        Returns:
          path to the given element.
        '''
        rpath = self.tree.getpath(element)
        branches = rpath.lstrip("/").split("/")
        rpath = ""
        for branch in branches:
            # No explicit node identifier.  Append "[1]" to that branch.
            rpath += "/" + branch
            if branch[-1] != ']':
                rpath += "[1]"
        return (rpath)

    def validate(self):
        '''
        Perform XML validation against the DTD.

        Raises:
          MimEmptyTreeError - No XML data present
          Various lxml.etree (StandardError subclass) exceptions
        '''
        if not self.tree:
            raise milib.MimEmptyTreeError(milib.ERR_EMPTY_TREE)
        try:
            self.schema.assertValid(self.tree)
        except Exception:
            # pylint says that filter_from_errors() doesn't exist but it does.
            # pylint: disable-msg=E1101
            # Assume these messages are already localized.
            raise milib.MimDTDInvalid(
                [msg.__repr__() for msg in
                 self.schema.error_log.filter_from_errors()])

    def commit(self, validate=True):
        '''
        Write XML data out to destination file (set up through __init__()).
        Optionally validate first.

        Args:
          validate:
            True: Do validation first.  Don't write file if validation fails.
            False: Don't validate first.

        Raises:
          MimEmptyTreeError - No XML data present
          Various lxml.etree (StandardError subclass) exceptions when
              validating
          IOError = "Could not open destination file for writing"
        '''
        if not self.tree:
            raise milib.MimEmptyTreeError(milib.ERR_EMPTY_TREE)
        if validate:
            self.validate()
        try:
            self.tree.write(self.dest_name, pretty_print=True)
        except IOError as err:
            raise IOError(milib.IOERR_DTD_DEST %
                          {"mserr": err.strerror, "mdest": self.dest_name})

    def set(self, path, value):
        '''
        Change an element's value or add/change an attribute.
        path argument must match only one element or attribute.

        Args:
          path: Xpath-like expression of element to change or
              attribute to change/set.  (see header of this file for syntax)

          value: Value to set.

        Raises:
          MimInvalidError - Argument is missing or invalid
          MimEmptyTreeError - No XML data present
          MimMatchError - Ambiguity error:  Path matches more than one element
          MimMatchError - Error:  Path matches no elements
          Errors raised by etree.getpath()
        '''
        # Explicitly test for a None value as etree accepts it and we don't.
        # Test other values for consistency.
        if path is None or value is None:
            raise milib.MimInvalidError(milib.ERR_ARG_INVALID)

        if not self.tree:
            raise milib.MimEmptyTreeError(milib.ERR_EMPTY_TREE)

        xpath, final_val, attr = ManifestInput._path_preprocess(path)
        orig_list = self._xpath_search(xpath, final_val)

        if len(orig_list) > 1:
            raise milib.MimMatchError(milib.ERR_AMBIG_PATH)
        elif len(orig_list) == 0:
            raise milib.MimMatchError(milib.ERR_NO_ELEM_MATCH)

        if attr is None:
            orig_list[0].text = value
        else:
            # Create/update an attribute.
            orig_list[0].set(attr, value)

        rpath = self.getpath(orig_list[0])
        if attr is not None:
            rpath += "@" + attr
        return rpath

    def get(self, path):
        '''
        Retrieve an element value or attribute.
        path argument must match only one element or attribute.

        Args:
          path: Xpath-like expression of element or attribute to retrieve.
              (see header of this file for syntax)

        Returns:
          rval: value requested, stripped of any enveloping white space

          rpath: Xpath-like expression of retrieved element or attribute.
              Narrowing-values are expressed via element IDs rather than
              "element=value or attr=value expressions.

        Raises:
          MimInvalidError - Argument is missing or invalid
          MimMatchError - Ambiguity error:  Path matches more than one element
          MimMatchError - Error:  Path matches no elements
          MimMatchError - Error: Path matches no attributes
          Errors raised by etree.getpath()
        '''
        if not path:
            raise milib.MimInvalidError(milib.ERR_ARG_INVALID)

        if not self.tree:
            raise milib.MimEmptyTreeError(milib.ERR_EMPTY_TREE)

        xpath, final_val, attr = ManifestInput._path_preprocess(path)
        orig_list = self._xpath_search(xpath, final_val)

        if len(orig_list) > 1:
            raise milib.MimMatchError(milib.ERR_AMBIG_PATH)
        elif len(orig_list) == 0:
            raise milib.MimMatchError(milib.ERR_NO_ELEM_MATCH)

        if attr is not None:
            try:
                rval = orig_list[0].attrib[attr]
            except StandardError:
                raise milib.MimMatchError(milib.ERR_NO_ATTR_MATCH)
        else:
            rval = orig_list[0].text

        rpath = self.getpath(orig_list[0])
        if attr is not None:
            rpath += "@" + attr

        if rval is not None:
            rval = rval.strip()

        return rval, rpath

    @staticmethod
    def find_insertion_index(list_insert_before, curr_elem):
        '''
        Return index of where to insert an element in curr_elem's children.

        Find which element in list_insert_before exists as a child of
        curr_elem, and return its index.  (The child to insert can be inserted
        at that position, before the found element.)

        Args:
          list_insert_before: list of elements curr_elem can be inserted before
              It is assumed that list_insert_before was generated based on the
              element to insert.  It can be empty but not None.

          curr_elem: parent element under which the child will be inserted.

        Returns:
          Index of where to insert the child.
        '''

        # If non-empty, list_insert_before contains a list of possible
        # elements to insert the new element before.  Find the first element
        # that exists as a child in the current element which matches one of
        # the possible elements in the list_insert_before list.
        for child in list_insert_before:
            insert_at_idx = ManifestInput.search_children_for_tag_match(
                curr_elem, child)
            if insert_at_idx != -1:
                break
        else:
            # List could be empty, meaning that the search indicates that
            # the new element should be the last child.  Add to the end.
            # Alternatively, the element to follow is not yet in the list.
            # The best we can do is to add child to the end of the list.
            insert_at_idx = -1
        return insert_at_idx

    def add(self, path, value):
        '''
        Add an element.

        Parent portion of the given path must match only one element.

        Element must be given a value, or alternatively, the path may go to an
        attribute of the new element.  (Note: use set to change or add an
        attribute to an existing element.)

        General algorithm:
        - If path has non-simple* branches, the portion of the path from the
          beginning until the last non-simple branch inclusive, must lead to a
          unique node.
        - From that unique node and beyond, or if the entire path is simple,
          from the beginning of the path, the path is checked branch by
          branch, and if duplicates are allowed (or, of course, if the node
          does not exist), a new node is created.  Otherwise, an existing one
          is followed.

        * A simple branch is simply an idenfier. /a/b are two simple branches.
        A non-simple branch is any other kind of branch, such as /a=5 or
        /b[c/d@e=123].  Non-simple branches always specify a value and may
        specify a subpath.

        The goal here is to honor subpaths which may be specified to narrow
        down where to add new items, but to still create a second node of a
        given tag where duplicates are allowed, where appropriate.

        Args:
          path: Xpath-like expression of element or attribute to retrieve.
              (see header of this file for syntax)

          value: Value to set.

        Returns:
          rpath: Xpath-like expression of retrieved element or attribute.
              Narrowing-values are expressed via element IDs.

        Raises:
          MimInvalidError - Argument is missing or invalid
          MimInvalidError - Final path branch has a value or is invalid
          MimInvalidError - Cannot add a second tree root node
          MimMatchError - Ambiguity error:  Parent path matches more than
              one element
          MimMatchError - No matching parent path exists
          Errors raised by etree.getpath()
        '''
        # Explicitly test for a None value as etree accepts it and we don't.
        # Test other values for consistency.
        if path is None or value is None:
            raise milib.MimInvalidError(milib.ERR_ARG_INVALID)

        # pylint: disable-msg=W0612
        xpath, final_val, attr = ManifestInput._path_preprocess(path,
                                               not STRIP_FINAL_UNBKT_VALUE)
        # left_set has all branches, temporarily...
        left_set = milib.branch_split(xpath)

        if not IDENT_ONLY_RE.match(left_set[-1]):
            raise milib.MimInvalidError(milib.ERR_FINAL_BRANCH_VAL_INVALID)

        # Special case: adding to a non-existant tree.
        if not self.tree:
            # Split off the root from the path, and create a tree based on it.
            new_element = etree.Element(left_set[0])
            self.tree = etree.ElementTree(new_element)
        elif (len(left_set) == 1 or
             (IDENT_ONLY_RE.match(left_set[0]) and
              left_set[0] != self.tree.getroot().tag)):
            raise milib.MimInvalidError(milib.ERR_2ND_ROOT)

        # Split branches into the left set which can contain non-simple
        # branches (and possibly simple branches too), and the right set which
        # may contain only simple branches.  The left set is delimited by the
        # last non-simple branch of the full path.

        right_set = []
        while left_set and IDENT_ONLY_RE.match(left_set[-1]):
            right_set.insert(0, left_set.pop())

        # Phase one of the search: use xpath to handle the non-simple portion
        # of the path, if a non-simple portion exists.
        if left_set:
            # A non-simple path was given.  Use Xpath to find its target.

            # If last branch of non-simple set has an =, split out the value
            final_branch_value = None
            if not BKT_NODE_VALUE_RE.match(left_set[-1]):
                left_set, final_branch_value = self._strip_final_value(
                                                                     left_set)
            left_path = '/' + '/'.join(left_set)
            nonsimple_targets = self._xpath_search(left_path,
                                                   final_branch_value)
            if len(nonsimple_targets) > 1:
                raise milib.MimMatchError(milib.ERR_AMBIG_PARENT_PATH)
            elif len(nonsimple_targets) < 1:
                raise milib.MimMatchError(milib.ERR_NO_PARENT_PATH)
            curr_elem = nonsimple_targets[0]
        else:
            curr_elem = self.tree.getroot()
            right_set = right_set[1:]

        # Phase two of the search: search branch by branch, checking whether
        # duplicate elements with the desired tag name are allowed, and
        # diverging the path to the new element from the first branch which
        # allows duplicates.

        # This loop will deal only with simple branches.
        # There must be at least one simple branch at the end of the path.

        # In this loop, don't do first (already done).

        for branch in right_set:
            # insert_before holds a list of names which can follow
            # an element named "branch" as children of curr_elem.
            (insert_before, mults_ok) =  \
                self.schema_data.find_element_info(curr_elem.tag, branch)

            # Check for no list (as oppoosed to empty list)
            if insert_before == None:
                # Child doesn't belong under this parent
                raise milib.MimInvalidError(milib.ERR_NODE_PLACEMENT %
                                      {"mnode": branch,
                                       "mparent": curr_elem.tag})

            # Current element has no children.  Just insert new element.
            if not len(curr_elem):
                # Create new element and set curr_elem to it.
                curr_elem = etree.SubElement(curr_elem, branch)

            else:
                node_w_same_tag = \
                    ManifestInput.search_children_for_tag_match(curr_elem,
                                                                branch)
                # Node with the branchname doesn't exist.
                if node_w_same_tag < 0:

                    # Find the index in curr_elem's list of children to place
                    # new "branch" element.  This will be behind a child in
                    # insert_before.  Find a child under curr_elem which is in
                    # insert_before, and then add new element behind it.

                    insertion_idx = ManifestInput.find_insertion_index(
                        insert_before, curr_elem)
                    new_elem = etree.SubElement(curr_elem, branch)
                    if (insertion_idx >= 0):
                        curr_elem.insert(insertion_idx, new_elem)
                    else:
                        curr_elem.append(new_elem)
                    curr_elem = new_elem

                # Node with branchname exists and duplicates are OK.
                elif mults_ok:
                    new_elem = etree.SubElement(curr_elem, branch)
                    # Insert after the last node with the same tag.
                    insert_after = node_w_same_tag
                    for list_elem_idx in range(node_w_same_tag + 1,
                                               len(curr_elem)):
                        if (curr_elem[insert_after].tag !=
                           curr_elem[list_elem_idx].tag):
                            insert_after = list_elem_idx
                            break
                        insert_after = list_elem_idx
                    curr_elem.insert(insert_after, new_elem)
                    curr_elem = new_elem

                # Otherwise duplicates not allowed.  Follow existing node.
                # Err out if this is the leaf node, as we cannot add here.
                else:
                    if branch == right_set[-1]:
                        raise milib.MimInvalidError(milib.ERR_LEAF_DUPS)
                    curr_elem = curr_elem[node_w_same_tag]

        # Add the value (element value or attribute) to the final node.
        if attr is not None:
            curr_elem.set(attr, value)
            return (self.getpath(curr_elem) + "@" + attr)

        curr_elem.text = value
        return self.getpath(curr_elem)

    def _xpath_search(self, xpath, final_val=None):
        '''
        Perform an xpath search

        Args:
          xpath: xpath of the elements to retrieve.

          final_val: value of path's final element, or None if none

        Returns:
          A list of elements which match the xpath.  Can be an empty list.

        Raises:
          MimEtreeParseError - Error parsing path <path>: <error>
        '''
        try:
            rval = self.tree.xpath(xpath)
        except etree.XPathEvalError as err:
            raise milib.MimEtreeParseError(milib.ERR_ETREE_PARSE_XPATH %
                                     {"mxpath": xpath, "merr": err.args[0]})

        # If get back multiple elements, see if final value can narrow to one.
        if (len(rval) > 1) and final_val:
            new_rval = []
            # Strip leading and trailing single- or double-quotes.
            final_val = final_val.strip("'\"")
            for elem in rval:
                if elem.text == final_val:
                    new_rval.append(elem)
            rval = new_rval
        return rval

    # ---------------------------- Overlay Section ----------------------------

    @staticmethod
    def _is_comment(node):
        '''
        Checks to see if node is a comment.

        Args:
          node: node to check

        Returns:
          True: node is a comment;  False: node is an element.
        '''
        return (type(node.tag) != str)

    @staticmethod
    def _clone_element(orig_element):
        '''
        Clone an element, for inclusion into the main tree.  Clone its tag,
        text and attributes.  Do not clone or attach its children.

         Handles comment and regular elements.  Does not currently handle other
         types of elements, but it could be enhanced to do so if needed.

        Args:
          orig_element: Element to clone

        Returns: A copy of the orig_element, but without its children.

        Raises:
          Whatever is raised by etree.Comment or etree.Element.
        '''
        if ManifestInput._is_comment(orig_element):
            new_element = etree.Comment(orig_element.text)
        else:  # Normal element.
            new_element = etree.Element(orig_element.tag, orig_element.attrib)
            new_element.text = orig_element.text
            new_element.tail = orig_element.tail
        return new_element

    @staticmethod
    def _clone_subtree(orig_element):
        '''
        Recursively clone a tree of elements.

        Args:
          orig_element: Root of the tree to clone.

        Returns: the root of the clone.

        Raises:
          Whatever is raised by etree.Comment or etree.Element.
        '''
        new_element = ManifestInput._clone_element(orig_element)
        for child in orig_element:
            new_element.append(ManifestInput._clone_subtree(child))
        return new_element

    @staticmethod
    def search_children_for_tag_match(parent, tag):
        '''
        Search children of "parent" element for the first with a matching tag.

        Args:
          parent: Parent element containing children to search.

          tag: tag name to search for.

        Returns:
          Child element with matching tag.

        Raises: N/A
        '''
        for idx, value in enumerate(parent):
            if (value.tag == tag):
                return idx
        return -1

    def _overlay_process(self, main_parent, overlay_element,
                         comments_to_install):
        '''
        Determine how to add a node (overlay_element) to its potential future
        parent (main_parent), and add it.

        If overlay_element has a tag that matches an existing child of
        main_parent, additional handling is needed.
        - If two elements with the same tag are allowed (mults_ok) then just
          add the new node.
        - If two elements with the same tag are not allowed, then see if the
          overlay_element has children.
          - If the overlay_element has children, keep the like-tagged element
            already in the tree.  It will be used to get to the next node in
            the path, to travel to the spot where something new can be added.
            Add any attributes of the new element to the original one.
          - If the overlay_element is a leaf node, then replace the node in
            the main tree with the overlay_element.

        Args:
          main_parent: Parent of where new element would be added.

          overlay_element: New element to add.  May have attributes.

          comments_to_install: comments to add to main tree just before the
              element being added.

        Returns:
          A reference to the affected element in the tree.  This could be an
              added element, or an original element.

        Raises:
          Various exceptions from schema module's find_element_info() method
          MimInvalidError - Node <node> cannot be placed as child of <node>
        '''

        # Find where the overlay_element belongs among its siblings, and
        # whether or not multiples of its tag are allowed.
        (insert_before, mults_ok) = \
            self.schema_data.find_element_info(main_parent.tag,
                                               overlay_element.tag)
        if insert_before is None:
            # Child doesn't belong under this parent
            raise milib.MimInvalidError(milib.ERR_NODE_PLACEMENT %
                                  {"mnode": overlay_element.tag,
                                   "mparent": main_parent.tag})
        insert_at_idx = -1
        if not len(main_parent):
            # Parent has no children.  Add new child subtree.
            if comments_to_install is not None:
                main_parent.extend(comments_to_install)
            main_parent.append(self._clone_subtree(overlay_element))
            return None
        else:
            if comments_to_install is not None:
                comments_to_install.reverse()

            # Parent has children.  Add new element next to an existing element
            # with same tag, if such an element already exists in the list.
            insert_at_idx = ManifestInput.search_children_for_tag_match(
                        main_parent, overlay_element.tag)
            if insert_at_idx != -1:

                # If the simplifying assumption is made that all elements with
                # a given tag appear together in the list, then mults_ok will
                # be deterministic for any given tag.

                if mults_ok:
                    # Child of same tag exists, and multiples with same tag
                    # are allowed.  Insert subtree after the last node with the
                    # same tag and any comments that follow it.
                    insert_after = -1
                    insert_after_tag = main_parent[insert_at_idx].tag
                    for list_elem_idx in range(insert_at_idx + 1,
                                               len(main_parent)):
                        if isinstance(main_parent[list_elem_idx].tag, str):
                            if (insert_after_tag !=
                                main_parent[list_elem_idx].tag):
                                insert_after = list_elem_idx
                                break
                    else:
                        insert_after = len(main_parent)
                    main_parent.insert(insert_after,
                                       self._clone_subtree(overlay_element))
                    # Add comments last;  inserting puts items before existing
                    # ones.  Comments will be before the element this way.
                    if comments_to_install is not None:
                        for comment in comments_to_install:
                            main_parent.insert(insert_after, comment)
                    return None

                elif (not len(overlay_element)):
                    # An element reads like a list of its children.
                    # Here, overlay_element has no children (is a leaf).
                    # Replace element with matching tag, with new element.
                    main_parent[insert_at_idx] = \
                        self._clone_subtree(overlay_element)
                    if comments_to_install is not None:
                        for comment in comments_to_install:
                            main_parent.insert(insert_at_idx, comment)
                    return None

                else:
                    # Overlay element is not a leaf.  Don't add.  However, add
                    # any attributes of new element to original one.
                    # Prepare to return main_parent[insert_at_idx]
                    ret_element = main_parent[insert_at_idx]
                    ret_element.attrib.update(
                        overlay_element.attrib.iteritems())
                    if comments_to_install is not None:
                        for comment in comments_to_install:
                            main_parent.insert(insert_at_idx, comment)

            # NOTE: since xml allows child elements with the same tag to appear
            # in multiple places in a list of children, there is no way to know
            # the correct placement of the new element until other elements are
            # in place, but that is a chicken and egg problem here.  Assume
            # that there is only one child element of a given type under a
            # given parent.

            # The best we can do here is to add behind an element that we know
            # the element can follow.  If that cannot be done, then just add
            # the element to the end of the list; that way, at least the items
            # will be correctly placed if they are added in the order they are
            # to appear.

            elif not len(insert_before):
                # The search says the new element should be the
                # last in the children list.  Add to the end.
                if comments_to_install is not None:
                    for comment in comments_to_install:
                        main_parent.append(comment)
                main_parent.append(self._clone_subtree(overlay_element))
                return None
            else:
                # insert_before contains a list of possible elements to insert
                # the new element before.  Find the first element that exists
                # as a child in main_parent which matches one of the possible
                # elements in insert_before.
                for child in insert_before:
                    insert_at_idx = \
                        ManifestInput.search_children_for_tag_match(
                        main_parent, child)
                    if insert_at_idx != -1:
                        break
                else:
                    # The element to follow is not yet in the list.
                    # The best we can do is to add it to the end of the list.
                    insert_at_idx = len(main_parent)
                main_parent.insert(insert_at_idx,
                                   self._clone_subtree(overlay_element))
                if comments_to_install is not None:
                    for comment in comments_to_install:
                        main_parent.insert(insert_at_idx, comment)
                return None

        return ret_element

    def _overlay_recurse(self, main_parent, overlay_element,
                         comments_to_install):
        '''
        Recurse through the tree in pre-order fashion, calling _overlay_process
        on encountered nodes.  Orchestrates overlay of full subtree starting
        with overlay_element.

        Args:
          main_parent: node in main tree where overlay_element will be
              attached.

          overlay_element: New node to overlay into main tree.

          comments_to_install: List of comments to install before the
              overlay_element under the main_parent.

        Raises: Exceptions raised by _overlay_process().
        '''

        # amassed_comments vs comments_to_install:
        #
        # amassed_comments is a list being built, of comments to place before
        # an inserted element.  The inserted element has not been found yet.
        # The list of comments gets built at this level in the tree, as
        # children at this level are traversed.
        #
        # Note that this is different than the argument passed in:
        # comments_to_install, which is a complete list passed through to
        # _overlay_process() along with a found element to insert.  The
        # comments will be inserted in the main tree just before the
        # overlay_element.

        amassed_comments = None

        # Special processing if both trees are at their root.
        #
        # Normally this method is called with main_parent being a parent node
        # to overlay_element.  (main_parent is one level higher in the tree
        # than overlay_element.)  However, the first time through,
        # overlay_element can be the root of the overlay tree.  Recurse to have
        # overlay_element descend the tree by one level.
        if (overlay_element.getroottree().getroot() == overlay_element):

            # If overlay_element is a leaf, replace main tree's root with it
            # and we're done.
            if not len(overlay_element):
                new_element = self._clone_element(overlay_element)
                self.tree = etree.ElementTree(element=new_element)
                # XXX Don't know what to do with the comments...  element is
                # the root, and the root can have no siblings so comments can't
                # live alongside the root.  lxml somehow stores comments that
                # show before the root element though...

            # For subsequent recursions, the element of the main tree is one
            # level higher than that of the overlay tree.
            else:
                for i in range(len(overlay_element)):
                    child = overlay_element[i]
                    if ManifestInput._is_comment(child):
                        if amassed_comments is None:
                            amassed_comments = []
                        amassed_comments.append(etree.Comment(child.text))
                    else:
                        self._overlay_recurse(main_parent, child,
                                              amassed_comments)
                        amassed_comments = None

        # Normal non-root processing.
        else:
            new_main_parent = self._overlay_process(main_parent,
                                                    overlay_element,
                                                    comments_to_install)
            if new_main_parent is not None:
                for child in overlay_element:
                    if ManifestInput._is_comment(child):
                        if amassed_comments is None:
                            amassed_comments = []
                        amassed_comments.append(etree.Comment(child.text))
                    else:
                        self._overlay_recurse(new_main_parent, child,
                                              amassed_comments)
                        amassed_comments = None

    # ---------------------------- General Section ----------------------------

    @staticmethod
    def _strip_final_value(branches):
        '''
        Strip the value off the final branch and return as final_branch_value

        Args:
          branches: list of path branches

        Returns:
          branches: list of path branches with its final value stripped.

          final_branch_value: value of the path's stipped final value
        '''
        left, equals, final_branch_value = branches[-1].partition("=")
        if equals:
            if not final_branch_value:
                raise milib.MimInvalidError(milib.ERR_FINAL_BRANCH_INVALID)
            branches[-1] = left
        else:
            final_branch_value = None
        return branches, final_branch_value

    @staticmethod
    def _path_preprocess(path, strip_unbkt_final_value=True):
        '''
        Return a proper element Xpath based on the nodepath provided.

        See header of this module for nodepath syntax.

        This routine knows not to split branches inside [ ], knows where to
        split off leaf node attributes, and changes the /a=5 syntax to what
        Xpath understands: e.g. /a[normalize-space(text())=5]

        Args:
          path: nodepath to translate into a proper Xpath

          strip_unbkt_final_value: when True, strip the final value if
              unbracketed and return it as final_branch_value.

        Returns:
          xpath: xpath to the desired element.

          final_branch_value: value of path's final element, or None if none.

          attr: name of attribute to get from desired element, or None if none.

        Raises:
          MimInvalidError - Path has invalid characters
          MimInvalidError - Argument is missing or invalid
          MimInvalidError - Unbalanced brackets or quotation marks.
          MimInvalidError - Path branch cannot begin with @
        '''

        # Spaces not allowed in paths.
        if " " in path:
            raise milib.MimInvalidError(milib.ERR_INVALID_CHARS)

        # Split path into branches, handling multiple consecutive slashes.
        branches = [branch for branch in milib.branch_split(path) if branch]

        if not branches:
            raise milib.MimInvalidError(milib.ERR_ARG_INVALID)

        # Process tail @attr=value
        #    Change path to [@attr=value]
        #    Return attribute name so caller can retrieve attr from results

        # Backward search last branch for rightmost @ which is not in brackets.
        attr = None
        left = right = None
        brkt_active_lvl = 0
        idx = len(branches[-1])
        while (idx >= 0):
            idx, brkt_active_lvl = \
                milib.search_and_get_context(branches[-1], "@", idx - 1,
                                             brkt_active_lvl, backward=True)
            if idx == 0:
                raise milib.MimInvalidError(milib.ERR_BRANCH_BEGIN_AT)
            if (idx > 0) and (brkt_active_lvl == 0):
                # Split at that @.
                left = branches[-1][:idx]
                right = branches[-1][idx + 1:]

                if UNBKT_NODE_VALUE_RE.match(right):
                    # @attr=value.  Enclose the right part in []
                    branches.pop()
                    branches.append(left + "[@" + right + "]")
                    break

                if IDENT_ONLY_RE.match(right):
                    # @attr.  Leave it stripped off of the path and return it
                    # separately.  It will be used later to find the attr in
                    # the element returned by xpath.
                    branches.pop()
                    branches.append(left)
                    attr = right
                    break

        # If last branch has an =, split out the value if requested.
        final_branch_value = None
        if (strip_unbkt_final_value and
            not BKT_NODE_VALUE_RE.match(branches[-1])):
            branches, final_branch_value = ManifestInput._strip_final_value(
                                                                    branches)
        for idx, branch in enumerate(branches):

            # a=val
            # Change all /node=value to /node[normalize-space(text())=value]
            if UNBKT_NODE_VALUE_RE.match(branch):
                node, _none, value = branch.partition("=")
                if UNQUOTED_VALUE_RE.match(value):
                    value = "\"" + value + "\""
                branches[idx] = node + \
                                      "[normalize-space(text())=" + value + "]"

            elif ELEMENT_SUBPATH_RE.match(branch):
                # IDENT + [IDENT/IDENT...@ATTR=VALUE]
                # matches when IDENT/IDENT is given,
                # and first IDENT and ATTR are optional.
                #
                # Change a[b/c@attr=val] to a[b/c[@attr="val"]]
                # "a" is optional.
                # "b/c" represents a path of any length of 1 node or more
                # "@attr" os optional
                # "val" is required but quotes will be added if needed.

                #  a        [        b/c        @attr    =    val ]
                #  -------------left_eq-----------------      right_eq
                #  loob              roob---------------      right_eq
                #  loob              left_at    right_at      right_eq

                left_eq, _none, right_eq = branch.partition("=")

                # Add quotes around value if needed.
                if UNQUOTED_VALUE_RE.match(right_eq[:-1]):
                    right_eq = "\"" + right_eq[:-1] + "\"]"

                # Now split the stuff to the left of the = on the opening [.
                left_of_open_bkt, _none, right_of_open_bkt = \
                    left_eq.partition("[")

                # and split stuff inside the [, on the @
                left_at, _at, right_at = right_of_open_bkt.partition("@")

                # a[b/c@attr=val] or a[b@attr=val]
                if _at and left_at and right_at:
                    branches.pop(idx)
                    branches.insert(idx, left_of_open_bkt + "[" + left_at +
                                    "[@" + right_at + "=" + right_eq + "]")

                # a[b/c=val] or a[b=val]
                else:
                    branches.pop(idx)
                    branches.insert(idx, left_eq +
                                    "[normalize-space(text())=" +
                                    right_eq + "]")

            # Catchall for all bracketed items not caught above,
            # e.g. [@name=value], or where no subpaths are given
            # Add quotes around all values.
            elif BKT_NODE_UNQUOTED_VALUE_RE.match(branch):
                preequal, _none, postequal = branch.partition("=")
                branches.pop(idx)
                branches.insert(idx, preequal + "=\"" + postequal[:-1] + "\"]")

            # Other (simple) cases not caught above fall through unchanged.

        path = "/" + "/".join(branches)
        return path, final_branch_value, attr
