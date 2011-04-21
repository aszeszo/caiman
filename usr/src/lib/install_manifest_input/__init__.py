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

""" Module body for manifest_input package
"""

import gettext

_ = gettext.translation("mim", "/usr/share/locale", fallback=True).gettext


# Errors created for this library.


class MimError(StandardError):
    '''
    Granddaddy of all Manifest Input Module errors
    '''
    pass


class MimDTDFmtError(MimError):
    '''
    DTD format error
    '''
    pass


class MimDTDExpnError(MimError):
    '''
    DTD expression error
    '''
    pass


class MimDTDInternalError(MimError):
    '''
    DTD internal error
    '''
    pass


class MimDTDError(MimError):
    '''
    DTD processing error
    '''
    pass


class MimDTDInvalid(MimError):
    '''
    DTD did not validate
    '''

    def __init__(self, validation_error_list):
        '''
        Constructor.

        Args:
          validation_error_list: list of validation errors.
        '''
        super(MimDTDInvalid, self).__init__()
        self._errors = validation_error_list

    @property
    def errors(self):
        '''
        Return validation errors
        '''
        return self._errors


class MimEtreeParseError(MimError, IOError):
    '''
    Etree parsing error
    '''
    pass


class MimEmptyTreeError(MimError):
    '''
    Empty tree (no data) error
    '''
    pass


class MimMatchError(MimError):
    '''
    Matching errors
    '''
    pass


class MimInvalidError(MimError, ValueError):
    '''
    Invalidity errors
    '''
    pass


# Error messages

# IOErrors
IOERR_DTD_ACCESS = _("Could not access DTD file: %(mserr)s: %(mfile)s")
IOERR_DTD_DIGEST = _("Could not digest DTD file: %(mserr)s: %(mfile)s")
IOERR_DTD_DEST = _("Could not open destination file for "
                   "writing: %(mserr)s: %(mdest)s")

# Other MIM module errors
ERR_ARG_INVALID = _("Argument is missing or invalid")
ERR_NO_SCHEMA = _("No schema name provided.")
ERR_NO_OUTFILE = _("No output file name provided.")
ERR_ETREE_PROC = _("Etree error processing DTD data from "
                   "file \"%(mfile)s\": %(merr)s")
ERR_SCHDATA_PROC = _("SchemaData error processing "
                     "DTD data from file \"%(mfile)s\": %(merr)s")
ERR_ETREE_PARSE_FILE = _("Error parsing XML manifest file %(mfile)s: %(merr)s")
ERR_EMPTY_TREE = _("No XML data present.")
ERR_AMBIG_PATH = _("Ambiguity error:  Path matches more than one element")
ERR_AMBIG_PARENT_PATH = _("Ambiguity error: "
                          "Parent path matches more than one element")
ERR_NO_PARENT_PATH = _("Error: no matching parent path exists")
ERR_NO_ELEM_MATCH = _("Error:  Path matches no elements")
ERR_NO_ATTR_MATCH = _("Error: Path matches no attributes")
ERR_FINAL_BRANCH_VAL_INVALID = _("Final path branch has a value or is invalid")
ERR_FINAL_BRANCH_INVALID = _("Final path branch is invalid")
ERR_ETREE_PARSE_XPATH = _("Etree error parsing path %(mxpath)s: %(merr)s")
ERR_NODE_PLACEMENT = _("Node \"%(mnode)s\" cannot be placed as "
                       "child of \"%(mparent)s\"")
ERR_UNBAL_QUOTES_BKTS = _("Unbalanced brackets or quotation marks")
ERR_BRANCH_BEGIN_AT = _("Path branch cannot begin with @")
ERR_INVALID_CHARS = _("Path has invalid characters")
ERR_2ND_ROOT = _("Cannot add a second tree root node")
ERR_LEAF_DUPS = _("Cannot add sibling node with same tag as found leaf node.")

# process_DTD module errors
ERR_NESTED_COMMENTS = _("DTD has nested comments")
ERR_MISMATCHED_DELIM = _("DTD has mismatched comment delimiters")
ERR_EXTRA_CLOSE_PAREND = _("Malformed expression: too many \")\"")
ERR_EXTRA_OPEN_PAREND = _("Malformed expression: too many \"(\"")
ERR_BAD_ELT_LINE = _("Malformed element line: %(mline)s")
ERR_ELT_LINE_NO_BKT = _("Malformed element line.  Missing final \">\"")
ERR_PQS_QTY_INVALID = _("DDObj.qty.setter: Invalid quantity "
                        "specification: %(mspec)s")
ERR_PTELT_LIST_FULL = _("DDElt list already has one item: %(mitem)s")
ERR_MISMATCHED_PARENDS = _("Malformed expression: Parentheses mismatch")
ERR_INVALID_QUANTIFIER = _("Malformed expression: invalid "
                           "quantifier: %(mquant)s")
ERR_INVALID_DTD_EXPR = _("Malformed expression: \",\" and \"|\" at same level")
ERR_SEI_INVALID_TYPE = _("_search_element_info: invalid type \"%(mtype)s\"")
ERR_INVALID_STATE = _("SearchState mode is invalid: %(mmode)d")

# Other notices
IOERR_MFEST_ACCESS = _("Notice: Error reading XML manifest "
                       "file \"%(mfile)s\"")
ERR_MFEST_NOENV = _("Manifest name could not be determined from "
                    "environment (AIM_MANIFEST)")


# Utility functions

def search_and_get_context(path, ch, start_idx=0, brkt_active_lvl=0,
                           backward=False):
    '''
    Return indices of where unquoted "ch" occur in a string.

    This function is used in parsing a nodepath.

    Return bracket level along with each index.  Bracket level is
        incremented only if found bracket is not quoted.

    Args:
      path: path to search through.

      ch: character to search for.

      start_idx: where in "path" to start searching.
          If zero and backward = True, starting index is the last character.

      brkt_active_lvl: nesting level of [ ].  Usually carried over from a
          previous search, which terminated at (start_idx - 1).

      backward: Search from the end if set to True.

    Returns:
      idx: index of found character

      brkt_active_lvl: nesting level of [ ].

    Raises: N/A
    '''

    idx = 0
    single_active = double_active = False

    if backward:
        if start_idx == 0:
            start_idx = len(path) - 1
        stop = -1
        step = -1
    else:
        stop = len(path)
        step = 1

    curr = None  # Set to something not found in a string.
    for idx in range(start_idx, stop, step):
        curr = path[idx]
        if curr == "'":
            single_active = (single_active == False)
        if curr == '"':
            double_active = (double_active == False)
        if not (double_active or single_active):
            if curr == ch:
                break
            elif curr == "[":
                brkt_active_lvl += 1
            elif curr == "]":
                brkt_active_lvl -= 1

    else:
        idx = -1
    return idx, brkt_active_lvl


def branch_split(path):
    '''
    Break path into branches on non-quoted, non-bracketed slashes.

    Args:
      path: path to split

    Returns:
      list of branches

    Raises:
      MimInvalidError - Unbalanced brackets or quotation marks
    '''

    # So _search_and_get_context() can split only on inner /.
    path = path.strip("/")

    return noquote_nobkt_split(path, "/")


def noquote_nobkt_split(path, split_char):
    '''
    Break path into branches on non-quoted, non-bracketed slashes.

    Args:
      path: path to split

      split_char: character to split on

    Returns:
      list of branches

    Raises:
      MimInvalidError - Unbalanced brackets or quotation marks
    '''
    branches = []
    idx = start_idx = 0
    brkt_active_lvl = 0

    while (True):
        idx, brkt_active_lvl = \
             search_and_get_context(path, split_char, idx, brkt_active_lvl)
        if brkt_active_lvl == 0:
            if idx > 0:
                branches.append(path[start_idx:idx])
            else:
                branches.append(path[start_idx:])
                break
            start_idx = idx + 1
        elif idx < 0:
            raise MimInvalidError(ERR_UNBAL_QUOTES_BKTS)
        idx += 1

    return branches
