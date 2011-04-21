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
process_dtd.py - Digest DTD info for use by XML processing

Provides info on which elements can follow others, and how many like-tagged
elements can be grouped together.  Attributes are inconsequential.
'''

import os.path
import re

import solaris_install.manifest_input as milib

# Some regular expression definitions used for getting dtd sub-files.
IDENTIFIER = "[:_A-Za-z][:\-\.\w]*"
ENTITY_TITLE = "<!ENTITY"
SPACE = "[\t ]+"
OSPACE = "[\t ]*"   # Optional space
EXT_FILE = re.compile(ENTITY_TITLE + SPACE + "%" + SPACE + "(" + IDENTIFIER +
                      ")" + SPACE + "SYSTEM" + SPACE + "\"(\S*)\"" +
                      OSPACE + ">$")
USE_EXT_FILE = re.compile("%(" + IDENTIFIER + ");$")

ELEMENT_TITLE = "<!ELEMENT"


def _remove_comments(line, com_in_prog):
    '''
    Removes comments from a DTD.

    Designed to be called in a loop, with new lines each iteration and
    com_in_prog passed from iteration to iteration to maintain state.

    Args:
      line: A line to strip comments from.

      com_in_prog: When set, "line" begins as a continuation of an unterminated
        comment.

    Returns:
      line: A line stripped of comments.

      com_in_prog: When set, "line" ends as an unterminated comment.

    Raises:
      MimDTDFmtError - DTD has nested comments
      MimDTDFmtError - DTD has mismatched comment delimiters
    '''

    comstart = line.find("<!--")
    comend = line.find("-->")
    if comstart >= 0:
        if comend > comstart:  # ... <!-- ... --> ...
            if not com_in_prog:
                result = line[0: comstart] + line[comend + 3:]
            else:
                raise milib.MimDTDFmtError(milib.ERR_NESTED_COMMENTS)
        elif comend < 0:  # ... <!-- ...
            if com_in_prog:
                raise milib.MimDTDFmtError(milib.ERR_NESTED_COMMENTS)
            else:
                result = line[0:comstart]
                com_in_prog = True
        else:			# ... --> ... <!-- ...
            if com_in_prog:
                result = line[comend + 3:comstart]
            else:
                raise milib.MimDTDFmtError(milib.ERR_MISMATCHED_DELIM)
    else:
        if comend >= 0:		# ... --> ...
            if com_in_prog:
                result = line[comend + 3:]
                com_in_prog = False
            else:
                raise milib.MimDTDFmtError(milib.ERR_MISMATCHED_DELIM)
        elif com_in_prog:		# No comments delimiters in this line
            result = ""
        else:
            result = line
    return (result, com_in_prog)


def _nonparend_split(line, splitchar):
    '''
    Split a string based on a given character, only when that character is not
    enclosed in parentheses of any nesting level.  Used to tokenize a string.

    Args:
      line: string to tokenize

      splitchar: Character delimiter to split on.  Must not be "(" or ")".

    Returns:
      A list of tokens.

    Raises:
      MimDTDExpnError - Malformed expression: too many ")"
      MimDTDExpnError - Malformed expression: too many "("
    '''

    ret = []
    token_start = 0
    parend_level = 0
    line_len = len(line)
    for idx in range(line_len):
        if line[idx] == "(":
            parend_level += 1
        elif line[idx] == ")":
            parend_level -= 1
            if parend_level < 0:
                raise milib.MimDTDExpnError(milib.ERR_EXTRA_CLOSE_PAREND)
        elif (line[idx] == splitchar) and (parend_level == 0):
            ret.append(line[token_start:idx].strip())
            token_start = idx + 1
    if parend_level != 0:
        raise milib.MimDTDExpnError(milib.ERR_EXTRA_OPEN_PAREND)
    if token_start != line_len:
        ret.append(line[token_start:].strip())
    return ret


class SchemaData(object):
    '''
    Class which digests a DTD.  Presents methods for finding info on an
    element's children, and for printing out all information.

    It makes the following info available:
    1) What elements may follow a given element.
    2) Can there be multiple consecutive instances of an element with a given
       tagname?  (i.e. Does a quantifier ( * + ) follow the tagname in DTD?)

    This module makes the following assumptions about files/data it works with:
    1) Names of DTD files referenced within other DTDs contain only ascii
       characters.  They can start with a letter, colon or _.  Subsequent
       characters can be letters, numbers, .:_- .
    2) Each <!ELEMENT statement must be on a single line.
    3) A child appears only once in a given list of children.  (It may appear
       more than once, but only the first instance is recognized.)
    '''

    # Inner classes used to build internal data structures.

    # The data structure will ultimately consist of lists of lists, constructed
    # of DDObj objects (and subclasses thereof).  All DDObj objects store a
    # type and a quantity ( * + ? 1 ).  DDSeq objects have type SEQ, to
    # differentiate them from DDOr objects (type OR). DDSeq objects have lists
    # where all items all needed). DDOr objects have list where only one item
    # is needed).  DDElt objects are the most atomic, created from individual
    # elements, and have a type ELEM.  List heads are DDHead objects with type
    # HEAD, and they store the name of the parent element.

    class DDObj(list):
        '''
        All internal table items subclass this class.

        Internal table items are lists of lists.  This class provides a common
        method to add the quantity to the standard list printout.

        qty represents the quantity modifier.  It can be +, *, ? or 1.
        '''

        # Types of DDObj items.
        T_HEAD, T_SEQ, T_OR, T_ELEM = range(4)

        def __init__(self):
            super(SchemaData.DDObj, self).__init__()
            self._qty = "1"

        @property
        def qty(self):
            '''Return quantifier'''
            return self._qty

        # pylint doesn't get along well with property decorators
        # pylint: disable-msg=E1101
        @qty.setter
        # pylint: disable-msg=E0102
        def qty(self, arg):
            '''Check and store quantifier'''
            if (len(arg) != 1) or (not arg in "+*?1"):
                # Should never see this.
                raise milib.MimDTDInternalError(milib.ERR_PQS_QTY_INVALID %
                                          {"mspec": arg})
            self._qty = arg

        def __repr__(self):
            return (super(SchemaData.DDObj, self).__repr__() + " " + self.qty)

    class DDHead(DDObj):
        '''
        DTD Data.  Class representing the head object of a new list of children
        '''
        def __init__(self, parent_name):
            super(SchemaData.DDHead, self).__init__()
            self.type = SchemaData.DDObj.T_HEAD
            self.name = parent_name

    class DDSeq(DDObj):
        '''
        Class representing a (comma separated) list of items in a DTD (a,b,c)

        This represents a sequence of items, all of which are required.  Items
        may be individual elements, a sequence of elements and/or items, or an
        OR grouping of elements and/or items.
        '''
        def __init__(self):
            super(SchemaData.DDSeq, self).__init__()
            self.type = SchemaData.DDObj.T_SEQ

    class DDOr(DDObj):
        '''
        Class representing a ("|" separated) list of items in a DTD (a|b|c)

        This represents an OR grouping of items, only one of which is required.
        Items may be individual elements, a sequence of elements and/or items,
        or an OR grouping of elements and/or items.
        '''
        def __init__(self):
            super(SchemaData.DDOr, self).__init__()
            self.type = SchemaData.DDObj.T_OR

    class DDElt(DDObj):
        '''
        Class representing a single element.
        '''
        def __init__(self, elem):
            super(SchemaData.DDElt, self).__init__()
            self.type = SchemaData.DDObj.T_ELEM
            self.append(elem)

        def append(self, item):
            '''
            Apply sanity check that only one item is in DDElt objects.
            extend() and insert() are not impl as not used by this module.
            '''
            if len(self) > 0:
                # Should never see this.
                raise milib.MimDTDInternalError(milib.ERR_PTELT_LIST_FULL %
                                          {"mitem": str(self)})
            super(SchemaData.DDElt, self).append(item)

    def __init__(self, dtdname):
        '''
        Read and digest a DTD.  Set up internal data structures from it.

        Args:
          dtdname: Pathname of the DTD.

        Raises:
          IOErrors dealing with DTD file access
          From _remove_comments:
            MimDTDExpnError - DTD has mismatched comment delimiters
            MimDTDExpnError - DTD has nested comments
          From _process_element:
            MimDTDExpnError - Malformed element line: %s
            MimDTDExpnError - Malformed element line.  Missing final ">"
            From _process_list:
              MimDTDExpnError - "Malformed expression: Parentheses mismatch"
              MimDTDExpnError - "Malformed expression: "
                                       "invalid quantifier: %s"
              MimDTDExpnError - "Malformed expression: "," and "|" "
                                       " at same level"
              From _nonparend_split:
                MimDTDExpnError - Malformed expression: too many ")"
                MimDTDExpnError - Malformed expression: too many "("
        '''

        # Dictionary of each element's child lists, organized by element name
        self.table = {}

        # Store here DTD subfile references found while traversing DTDs
        filerefs = {}

        # If dtdname starts with a directory (either absolute or relative),
        # save that directory to append to subsequent dtd pathnames which
        # contain only a filename.
        self.dtddir = os.path.dirname(dtdname)

        # Create a list of DTD file names.
        dtdlist = []
        dtdlist.append(dtdname)
        dtd_idx = 0

        # Loop until the list of DTD files is exhausted.
        while (True):

            try:
                curr_dtdname = dtdlist[dtd_idx]
            except IndexError:
                break
            if curr_dtdname.startswith("file:///"):
                curr_dtdname = curr_dtdname[7:]

            # This maintains state that a comment between lines is in progress.
            com_in_prog = False

            with open(curr_dtdname, "r") as dtd:
                for line in dtd:
                    line = line.strip()
                    (nocomline, com_in_prog) = _remove_comments(line,
                                                                com_in_prog)
                    # We only care about <!ELEMENT lines, and DTD subfile refs

                    # Note: Rigorous validation of DTD statements is not done
                    # here.  Whereas a malformed statement will give errors
                    # here, the buggy DTD will eventually be caught when the
                    # proper XML validator tries to use it.  Fixing the DTD for
                    # that validator will fix it for here too.

                    # Assume all <!ELEMENT statements are on one line
                    if nocomline.startswith(ELEMENT_TITLE):
                        self._process_element(nocomline)
                        continue

                    # Lines like '<!ENTITY % target SYSTEM "target.dtd">'
                    ext_file_match = EXT_FILE.match(nocomline)
                    if ext_file_match:
                        ext_fileref = ext_file_match.group(1)
                        ext_filename = ext_file_match.group(2)
                        if not len(os.path.dirname(ext_filename)):
                            ext_filename = os.path.join(self.dtddir,
                                                        ext_filename)
                        filerefs[ext_fileref] = ext_filename
                        continue

                    # Lines like '%target;'.  Note that this and the <!ENTITY
                    # line are needed to get to a sub-DTD, to screen out other
                    # <!ENTITY lines which represent things other than sub-DTDs
                    use_ext_file_match = USE_EXT_FILE.match(nocomline)
                    if use_ext_file_match:
                        fileref = use_ext_file_match.group(1)
                        dtdlist.append(filerefs[fileref])

            if com_in_prog:
                raise milib.MimDTDFmtError(milib.ERR_MISMATCHED_DELIM)

            # Onward to the next file.
            dtd_idx += 1

    # ------------------------- List building section -------------------------

    def _process_element(self, line):
        '''
        Process an <!ELEMENT line in the DTD.

        First split it up to get element name and list of children, then
        call _process_list() to process the children.

        Args:
          line: an <!ELEMENT line to process

        Returns:
          Adds an entry for this element into self.table as a side effect.

        Raises:
          MimDTDExpnError - Malformed element line: %s
          MimDTDExpnError - Malformed element line.  Missing final ">"
          From _process_list:
            MimDTDExpnError - "Malformed expression: Parentheses mismatch"
            MimDTDExpnError - "Malformed expression: invalid quantifier: %s"
            MimDTDExpnError - "Malformed expression: "," and "|" at
                same level"
        '''
        # Split the line into three parts: <!ELEMENT name children-list
        # Don't nitpick syntax of children lists.  Just let validator catch
        # problems later on.
        parts = line.split(None, 2)
        try:
            name = parts[1]
            children = parts[2]
        except IndexError:
            raise milib.MimDTDExpnError(milib.ERR_BAD_ELT_LINE %
                                        {"mline": line})

        try:
            children = children.strip().rsplit(">", 1)[0]
        except IndexError:
            raise milib.MimDTDExpnError(milib.ERR_ELT_LINE_NO_BKT)

        child_list = self.DDHead(name)
        self._process_list(children, child_list)
        self.table[name] = child_list

    def _process_list(self, items, parent_list):
        '''
        Recursive routine to process lists of children of an <!ELEMENT line

        This will break down a single list from a DTD into sublists, delimited
        by (), "," and "|".  Each sublist will in turn be broken down until
        only individual elements remain.  As the list is broken into sublists,
        the data structure is built.

        Note: only an element's immediate children are of concern.  The
        search function which uses the data structure needs to return only
        immediate children of an element.

        Args:
          items: a parenthesized (string) list of child elements to process

          parent_list: parent list to which items of a broken-down "items" list
            are attached.

        Raises:
            MimDTDExpnError - "Malformed expression: Parentheses mismatch"
            MimDTDExpnError - "Malformed expression: invalid quantifier: %s"
            MimDTDExpnError - "Malformed expression: "," and "|" at
                same level"
        '''

        items = items.strip()
        if items[-1] in "+*?":  # Remove + or ? or * from end, outside any ()
            qty = items[-1]     # If there are mult items, qty will be stored
            items = items[0:-1]  # in the SEQ or OR list that keeps those items
        else:
            qty = "1"
        items = items.strip()
        if ((items[0] == "(") and (items[-1] == ")")):
            items = items[1:-1]  # Remove enveloping ( )

        # Sanity check number of ()
        if (items.count("(") != items.count(")")):
            raise milib.MimDTDExpnError(milib.ERR_MISMATCHED_PARENDS)

        # Current expression must end in an identifier, valid quantifier or ).
        # _ is included since identifiers can have them but isalnum() doesn't.
        if ((items[-1] not in ")_*+?") and (not items[-1].isalnum())):
            raise milib.MimDTDExpnError(milib.ERR_INVALID_QUANTIFIER %
                                        {"mquant": items})

        # Split on "|" which are outside parentheses.
        or_items = _nonparend_split(items, "|")
        if len(or_items) > 1:

            # Sanity check: nonparend splits at any given level cannot contain
            # both splits on "|" and ",".
            if len(_nonparend_split(items, ",")) > 1:
                raise milib.MimDTDExpnError(milib.ERR_INVALID_DTD_EXPR)

            # Build an OR list of split items.  Append to parent list.
            or_list = self.DDOr()
            or_list.qty = qty
            for or_item in or_items:
                self._process_list(or_item, or_list)
            parent_list.append(or_list)
            return

        # Split on "," which are outside parentheses, to build SEQ list.
        seq_items = _nonparend_split(items, ",")
        if len(seq_items) > 1:
            seq_list = self.DDSeq()
            seq_list.qty = qty
            for seq_item in seq_items:
                self._process_list(seq_item, seq_list)
            parent_list.append(seq_list)
            return

        # Single item.
        if items[-1] in "+*?":      # Remove + or ? or * from the end. () could
            qty = items[-1]         # have shielded +?* from being seen earlier
            items = items[0:-1]

        # A single parenthesized item.
        if (items[0] == "("):       # Really only one item.
            seq_list = self.DDSeq()
            seq_list.qty = qty
            self._process_list(items, seq_list)  # Strip off outside ()
            parent_list.append(seq_list)

        # A single non-parenthesized item.
        else:
            elt = self.DDElt(items)
            elt.qty = qty
            parent_list.append(elt)

    # ------------------------- List display section --------------------------

    def _print_list(self, child_list, indent):
        '''
        Recursively display a list and its children.

        Args:
          child_list: List to recurse down and print.

          indent: indentation level

        Raises: None
        '''

        indentation = ""
        for i in range(indent):
            indentation += " "

        # Main Header, and SEQ and OR list header.
        if isinstance(child_list, self.DDHead):
            print "%sPrinting child list for element \"%s\"..." % (
                indentation, child_list.name)
        else:
            print "%sList type:%s %s" % (
                indentation, child_list.type, child_list.qty)

        # Children.
        indentation += "  "  # Add two more spaces
        for i in range(len(child_list)):
            if isinstance(child_list[i], self.DDElt):
                print "%s%s" % (indentation, str(child_list[i]))
            else:
                self._print_list(child_list[i], indent + 2)

    def print_table(self):
        '''
        Dump the internal data structure.
        '''
        table_keys = self.table.keys()
        table_keys.sort()
        for name in table_keys:
            self._print_list(self.table[name], 0)

# ---------------------------- List search section ----------------------------

    class SearchState(object):
        '''
        Class to maintain state of searches and to aid in returning results.
        '''

        # States kept in state field.
        #    SEARCHING: looking for a match of a given element
        #    RETRIEVING: retrieving possible elements which can come
        #        after matched element
        #    UNWINDING: unwinding recursion back to previous-level list
        SEARCHING, RETRIEVING, UNWINDING = range(3)

        def __init__(self):
            self.mode = SchemaData.SearchState.SEARCHING

            # list of elts before which itm can be inserted.
            # If an empty list, means add item as last child.
            self.ret_list = []

            # Return whether duplicates of found element are allowed
            self.mults_allowed = False

            # Save the list we use to gather the first element after the
            # one we found.  If it is an OR list, we will stop searching when
            # we get to its end.
            self.first_list_gathered_from = None

            # If an item with qty "?" in an OR list is encountered during
            # retrieval, we want to read the next item after the list.  Save
            # this information to check when previous recursion level is
            # restored.
            self.treat_as_0_1_qty = None

    def _search_element_info(self, pt_list, find_this, search_state):
        '''
        Recursively search the data structure for info about a child item.

        The search goes through three modes:
        1) SEARCHING: Search for the child item.  If a child happens to be
           listed twice, the first one found is the one info is returned for.
           Thus it is best that an element has only unique elements as
           children.  (Note: it does not matter if children reuse some child
           elements as grandchildren.)

        2) RETRIEVING: Look for and retrieve possible items which can
           immediately succeed the found item.  (Note: an item can represent a
           single element or a list of them.)

           If the next item is an element, then it is the only item returned in
           ret_list unless it's quanity is "?".  If the next item is a SEQ
           list, return only the first item of that SEQ list (unless that
           latter item's quantity is "?"), since that item will always follow
           the find_this item.  If the next item is an OR list, return all
           items in that list, since any one of them can follow the find_this
           item.  Of course, if the next item is a list, then it will be
           recursively traversed and processed.

        3) UNWINDING: Once all next items have been gathered, unwind recursion
           and return.

        Args:
          pt_list: the list to search through.

          find_this: the child to find information about

          search_state: Maintains state across iterations.

        Returns:
          The search_state object is modified as the routine recurses:

          - mode: changes state once item is found, and once all next-items
              have been gathered.

          - ret_list: holds references to all next-items as they are gathered.

          - mults_allowed: Set to True or False depending on whether multiple
            find_this elements are allowed in the children list.

          - first_list_gathered_from: reference to the list the first "next"
            item was retrieved from.

        Raises: (only due to programming errors):
          MimDTDInternalError - _search_element_info: invalid type %s
          MimDTDInternalError - SearchState mode is invalid: %d

        '''
        last_pt_list_idx = len(pt_list) - 1
        for idx, item in enumerate(pt_list):

            # Searching for a match on element name.
            if search_state.mode == SchemaData.SearchState.SEARCHING:
                if ((item.type == SchemaData.DDObj.T_ELEM) and
                    (find_this == item[0])):
                    search_state.mode = SchemaData.SearchState.RETRIEVING

                    # NOTE: this does nothing fancy:  a,a will return false
                    search_state.mults_allowed = \
                        ((item.qty in "*+") or
                         ((pt_list.type == SchemaData.DDObj.T_OR) and
                          (pt_list.qty in "*+")))

                    # If we found our item in the middle of an OR list, skip
                    # the rest of the OR list at this level.  To not do so
                    # would indicate that it is correct to place a found-type
                    # element before the next type of element in the OR list.
                    # Note: this is correct for a SEQ list, so we don't
                    # break in that case.
                    if pt_list.type == SchemaData.DDObj.T_OR:
                        break

                # If item is another list, iterate until elements are found.
                elif ((item.type == SchemaData.DDObj.T_SEQ) or
                      (item.type == SchemaData.DDObj.T_OR)):
                    self._search_element_info(item, find_this, search_state)

            # We are finding the next item(s) after the one we sought.
            elif search_state.mode == SchemaData.SearchState.RETRIEVING:

                # Save the list we use to gather the first element after the
                # one we found.  We will stop searching when we get to its end.

                # Note that this list was where find_this was found.  This does
                # two things: it delays switching to the UNWINDING state by
                # one item, and it marks the list (so this list isn't confused
                # with any children lists which may need to be traversed before
                # returning.)
                #
                # If the current list is an OR list, don't process more of it
                # if find_this was just found in it.  Instead, fall back to the
                # previous level to iterate to the parent list's next element.
                if search_state.first_list_gathered_from is None:
                    if pt_list.type == SchemaData.DDObj.T_OR:
                        break
                    search_state.first_list_gathered_from = pt_list

                # Take next single item if it is an element.
                if item.type == SchemaData.DDObj.T_ELEM:
                    # Note: ret_list can have dups but it doesn't matter...
                    search_state.ret_list.append(item[0])

                    # Note items with qty "?"
                    if ((item.qty == "?") and
                        (pt_list.type == SchemaData.DDObj.T_OR)):
                        search_state.treat_as_0_1_qty = pt_list

                # Next item is a list.  Iterate on it to find atomic next items
                elif ((item.type == SchemaData.DDObj.T_SEQ) or
                      (item.type == SchemaData.DDObj.T_OR)):
                    self._search_element_info(item, find_this, search_state)

                    # If this list may or may not really exist, the
                    # next item can come after the found element as well.
                    # State was set to UNWINDING when the list traversal
                    # completed, but change back to retrieving to get one more
                    # next item.
                    if ((item.qty == "?") or
                        (search_state.treat_as_0_1_qty == item)):
                        search_state.treat_as_0_1_qty = None
                        search_state.mode = SchemaData.SearchState.RETRIEVING
                        continue

                else:
                    # Should never see this.
                    raise milib.MimDTDInternalError(
                                               milib.ERR_SEI_INVALID_TYPE %
                                               {"mtype": item.type})

                # After processing the item after the found one, change to done
                # state.  Only change to done (UNWINDING) state after
                # processing one child at the same level as the found one
                # (unless current item qty is ? which means item may or may not
                # really be present) if a SEQ list, or all children at the same
                # level if an OR list.
                if ((pt_list == search_state.first_list_gathered_from) and
                    (((pt_list.type == SchemaData.DDObj.T_SEQ) and
                      (item.qty != "?")) or
                     ((pt_list.type == SchemaData.DDObj.T_OR) and
                      (idx == last_pt_list_idx)))):
                    search_state.mode = SchemaData.SearchState.UNWINDING
                    return

            # If we found what we want, break out of all levels and return.
            elif (search_state.mode == SchemaData.SearchState.UNWINDING):
                return

            else:
                # Should never see this.
                raise milib.MimDTDInternalError(milib.ERR_INVALID_STATE %
                                          {"mmode": search_state.mode})

    def find_element_info(self, parent_arg, element_arg):
        '''
        Public method to get information for an element.

        Args:
          parent_arg: Tag of parent element whose children list contains
          element_arg

          element_arg: Element for which to retrieve information.

        Returns:
          List of possible elements which can follow element_arg:
          Values can be:
          - None, DTD reports that element_arg is not a child of parent_arg
          - empty list: DTD reports that element_arg is the last child of
            parent_arg
          - non-empty list: list of elements which can follow element_arg

          Multiples-allowed: True if more than one element_arg can be listed
          in sequence, False otherwise, except returns None if element is not
          a child of parent_arg.

        Raises:
        '''
        # Return name of element after.
        # None = no element found; [] means "add to the end of the list.

        # Find the parent in the table.
        try:
            child_list = self.table[parent_arg]
        except KeyError:
            return (None, None)

        # Note:searching the table for following elements is not reentrant!
        # Only one at a time.
        search_state = self.SearchState()

        # Find the child we're looking for.
        self._search_element_info(child_list, element_arg, search_state)

        if search_state.mode == SchemaData.SearchState.SEARCHING:
            return (None, False)
        elif search_state.mode == SchemaData.SearchState.RETRIEVING:
            return (search_state.ret_list, search_state.mults_allowed)
        elif search_state.mode == SchemaData.SearchState.UNWINDING:
            return (search_state.ret_list, search_state.mults_allowed)
        else:
            raise milib.MimDTDInternalError(milib.ERR_INVALID_STATE %
                                      {"mmode": search_state.mode})
