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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.

# =============================================================================
# =============================================================================
"""
ENParser.py - Enhanced Nodepath Parser module
"""
# =============================================================================
# =============================================================================

import sys

# =============================================================================
# Error handling.
# Declare new classes for errors thrown from this file's classes.
# =============================================================================

class ParserError(StandardError):
    """ Exceptions encountered or generated during parsing. """
    pass

# =============================================================================
class ENToken(object):
# =============================================================================
    """Contains the contents of one parsed token.

    A list of these is returned by parse_nodepath() below.

    Each contains a name, a list of valpaths and a list of values.
    See the Enhanced Nodepath Parser description for explanation of these
    terms.

    """
# =============================================================================

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, name, valpaths=None, values=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """Constructor

        Args:
          name: The name string of the token.

          valpaths: List of value paths.

          values: List of values

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (valpaths is None):
            valpaths = []
        if (values is None):
            values = []

        self.name = name
        self.valpaths = valpaths
        self.values = values


# =============================================================================
""" Enhanced Nodepath Parser

Offers functions to parse a tree path of nodes.  Desired node(s) can be
narrowed down by looking at values along the path, and at values of
nodes below an ancestor node.  These functions parse enhanced nodepaths
which specify values and their paths, as well as node names.

For example, given the following tree:

                                        A
                                        |
                             -----------------------
                             |                     |
                             B                     B
                         (value=v1)            (value=v2)
                             |                     |
             -----------------------         -------------------------
             |          |          |         |           |           |
             D          C          C         C           C           D
         (value=v3) (value=v4) (value=v5) (value=v6) (value=v7)  (value=v8)

	In the simplest case, 
		A/B/C would return all 4 C nodes.
	However, these functions allow specification of values to narrow down
	the search:

	Syntax: Path strings are broken into tokens on / not inside [] and not
	inside quotes or double quotes.

	Token syntax:
		name=value |
		name[valpath=value] |
		name[valpath1=value1:valpath2=value2:...]

	String				token		parse_nodepath()
							returns an ENToken
							containing:
	----------------------------------------------------------------------
	A/B=v1/C			A		name:A
							values: []
							valpaths: []
	                ------------------------------------------------------
					B=v1		name:B
							values: [v1]
							valpaths: []
	                ------------------------------------------------------
					C		name:C
							values: []
							valpaths: []
	----------------------------------------------------------------------
	A[B/C=v5]/B=v1/D		A[B/C=v5]	name:A
							values: [v5]
							valpaths: [B/C]
	                ------------------------------------------------------
					B=v1		name:B
							values: [v1]
							valpaths: []
	                ------------------------------------------------------
					D		name:D
							values: []
							valpaths: []
	                ------------------------------------------------------
	----------------------------------------------------------------------
	A[B/C=v6:B/D=v8]/B		A[B/C=v6:B/D=v8] name:A
							values: [v6, v8]
							valpaths: [B/C, B/D]
	                ------------------------------------------------------
							name:B
							values: []
							valpaths: []
	----------------------------------------------------------------------

ENTokens can be passed to a search routine for use in finding appropriate
matches.

String limitations:

1) Values can have ' inside "" or " inside '' but cannot have both kinds of
quotes.

2) Only values support any kind of quotes.  Names and valpaths do not support
quotes.

"""
# =============================================================================

# State machine for parsing the tokens:
#
# State table.  Next state determined by current state and current character.
# Descriptions of the states are below.
#
__ST_START, __ST_STSL, __ST_N0, __ST_N, __ST_P0, __ST_P, __ST_V0, __ST_V, \
    __ST_DQON, __ST_DQOFF, __ST_SQON, __ST_SQOFF, __ST_CBKT, __ST_TCMPL, \
    __ST_EXSL, __ST_ERR = range(16)

# __ST_ERR has no "current state" storage in the table.
# When __ST_ERR is hit, the method using the table exits.

# Pictorial of the state table.
#	Vertical = current state.
#	Horizontal = current character.
# Together these determine the next state.
#
# For example, if while getting the name portion of the token (state "n0" or
# "n") a "=" is read, then the next state will be "v0" to prepare to read a
# value.  If in state "n" and a "[" is encountered, the next state will be "p"
# to prepare to read a valpath.
#
# parse_token() will add the character following the special characters
# to the appropriate string or list, depending on the state.  For
# example, parse_token() will then put the new character in a value
# string if the state is "v" or put the new character in a valpath
# string if the state is "p"
#
# Some state transitions (e.g. n0 and n) look redundant.  However, each
# redundant state is necessary because the different states require different
# actions.  This becomes clear when looking at parse_nodepath().
#
# current / input
#	   '['     ']'     '='     ':'     '/'     '\"'    '\''  (other)
# ====================================================================== 
# start: 1st state.  1st regular character goes to n0 state.
# start    ERR     ERR     ERR     ERR     ERR     ERR     ERR     n0
# ----------------------------------------------------------------------
# stsl: starting slash received.  Always an error.
# stsl     ERR     ERR     ERR     ERR     ERR     ERR     ERR     ERR
# ----------------------------------------------------------------------
# n0: 1st char of new name (and new token) recd.  Init token; init name.
# n0       p0      ERR     v0      ERR     tcmpl   ERR     ERR     n
# ----------------------------------------------------------------------
# n: more name chars received.  Append to name string.
# n        p0      ERR     v0      ERR     tcmpl   ERR     ERR     n
# ----------------------------------------------------------------------
# p0: Init new valpath to blank string (as when open bracket rcvd).
# Could also be called obkt
# p0       ERR     ERR     ERR     ERR     ERR     ERR     ERR     p
# ----------------------------------------------------------------------
# p: Append more characters (including /)to valpath.
# p        ERR     ERR     v0      ERR     p       ERR     ERR     p
# ----------------------------------------------------------------------
# v0: Init new value sring to blank string.
# v0       ERR     ERR     ERR     ERR     ERR     dqon    sqon    v
# ----------------------------------------------------------------------
# v: Append more characters (including /) to valpath.
# Note: all chars except " keep this state if dqon
# Note: all chars except ' keep this state if sqon
# v        ERR     cbkt    ERR     p0      tcmpl   dqoff   sqoff   v
# ----------------------------------------------------------------------
# dqon: Turn double quote on to accept all chars (except ") for value.
# dqon     v       v       v       v       v       dqoff   v       v
# ----------------------------------------------------------------------
# dqoff: Turn double quote off so special characters are seen as such.
# Err out if dq not already on.
# dqoff    ERR     cbkt    ERR     p0      tcmpl   ERR     ERR     ERR
# ----------------------------------------------------------------------
# sqon: Turn single quote on to accept all chars (except ') for value.
# Err out if sq not already on.
# sqon     v       v       v       v       v       v       sqoff   v
# ----------------------------------------------------------------------
# sqoff: Turn single quote off so special characters are seen as such.
# sqoff    ERR     cbkt    ERR     p0      tcmpl   ERR     ERR     ERR
# ----------------------------------------------------------------------
# cbkt: Close bracket received.  Only / allowed (unless end of string)
# cbkt     ERR     ERR     ERR     ERR     tcmpl   ERR     ERR     ERR
# ----------------------------------------------------------------------
# tcmpl: token complete.  Need to check for open brackets and mismatches
#	If all is OK, then save token.
# tcmpl    ERR     ERR     ERR     ERR     exsl    ERR     ERR     n0
# ----------------------------------------------------------------------
# exsl: extra slash after end of token.  Just eat it.
# exsl     ERR     ERR     ERR     ERR     ERR     ERRR    ERR     n0
# ----------------------------------------------------------------------


class _stTblItem(object):
    """ Class of state table item obects, used only by the state table.
    """

    def __init__(self):

        # Dict contains special characters which don't send the machine
        # to the error state.  Dict values are the chars' next states.
        # Special characters which are listed in __special_chars, which
        # are not in this dict, send the state machine to the error
        # state.
        self.special_non_err_dict = {}

        # Where non-special chars (not listed above) send next state.
        self.normal_char_next_state = 0

# Chars which can trigger a state change by the table.
__SPECIAL_CHARS = "[]=:/\"\'"

__STATE_TABLE = []
__STATE_TABLE.insert(__ST_START, _stTblItem())
__STATE_TABLE.insert(__ST_N0, _stTblItem())
__STATE_TABLE.insert(__ST_N, _stTblItem())
__STATE_TABLE.insert(__ST_P0, _stTblItem())
__STATE_TABLE.insert(__ST_P, _stTblItem())
__STATE_TABLE.insert(__ST_V0, _stTblItem())
__STATE_TABLE.insert(__ST_V, _stTblItem())
__STATE_TABLE.insert(__ST_DQON, _stTblItem())
__STATE_TABLE.insert(__ST_DQOFF, _stTblItem())
__STATE_TABLE.insert(__ST_SQON, _stTblItem())
__STATE_TABLE.insert(__ST_SQOFF, _stTblItem())
__STATE_TABLE.insert(__ST_CBKT, _stTblItem())
__STATE_TABLE.insert(__ST_TCMPL, _stTblItem())
__STATE_TABLE.insert(__ST_EXSL, _stTblItem())
__STATE_TABLE.insert(__ST_STSL, _stTblItem())

__STATE_TABLE[__ST_START].special_non_err_dict['/'] = __ST_STSL
__STATE_TABLE[__ST_START].normal_char_next_state = __ST_N0

__STATE_TABLE[__ST_STSL].normal_char_next_state = __ST_ERR

__STATE_TABLE[__ST_N0].special_non_err_dict['['] = __ST_P0
__STATE_TABLE[__ST_N0].special_non_err_dict['='] = __ST_V0
__STATE_TABLE[__ST_N0].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_N0].normal_char_next_state = __ST_N

__STATE_TABLE[__ST_N].special_non_err_dict['['] = __ST_P0
__STATE_TABLE[__ST_N].special_non_err_dict['='] = __ST_V0
__STATE_TABLE[__ST_N].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_N].normal_char_next_state = __ST_N

__STATE_TABLE[__ST_P0].normal_char_next_state = __ST_P

__STATE_TABLE[__ST_P].special_non_err_dict['='] = __ST_V0
__STATE_TABLE[__ST_P].special_non_err_dict['/'] = __ST_P
__STATE_TABLE[__ST_P].normal_char_next_state = __ST_P

__STATE_TABLE[__ST_V0].special_non_err_dict['\"'] = __ST_DQON
__STATE_TABLE[__ST_V0].special_non_err_dict['\''] = __ST_SQON
__STATE_TABLE[__ST_V0].normal_char_next_state = __ST_V

__STATE_TABLE[__ST_V].special_non_err_dict[']'] = __ST_CBKT
__STATE_TABLE[__ST_V].special_non_err_dict[':'] = __ST_P0
__STATE_TABLE[__ST_V].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_V].special_non_err_dict['\"'] = __ST_DQOFF
__STATE_TABLE[__ST_V].special_non_err_dict['\''] = __ST_SQOFF
__STATE_TABLE[__ST_V].normal_char_next_state = __ST_V

__STATE_TABLE[__ST_DQON].special_non_err_dict['['] = __ST_V
__STATE_TABLE[__ST_DQON].special_non_err_dict[']'] = __ST_V
__STATE_TABLE[__ST_DQON].special_non_err_dict['='] = __ST_V
__STATE_TABLE[__ST_DQON].special_non_err_dict[':'] = __ST_V
__STATE_TABLE[__ST_DQON].special_non_err_dict['/'] = __ST_V
__STATE_TABLE[__ST_DQON].special_non_err_dict['\"'] = __ST_DQOFF
__STATE_TABLE[__ST_DQON].special_non_err_dict['\''] = __ST_V
__STATE_TABLE[__ST_DQON].normal_char_next_state = __ST_V

__STATE_TABLE[__ST_DQOFF].special_non_err_dict[']'] = __ST_CBKT
__STATE_TABLE[__ST_DQOFF].special_non_err_dict[':'] = __ST_P0
__STATE_TABLE[__ST_DQOFF].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_DQOFF].normal_char_next_state = __ST_ERR

__STATE_TABLE[__ST_SQON].special_non_err_dict['['] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict[']'] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict['='] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict[':'] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict['/'] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict['\"'] = __ST_V
__STATE_TABLE[__ST_SQON].special_non_err_dict['\''] = __ST_SQOFF
__STATE_TABLE[__ST_SQON].normal_char_next_state = __ST_V

__STATE_TABLE[__ST_SQOFF].special_non_err_dict[']'] = __ST_CBKT
__STATE_TABLE[__ST_SQOFF].special_non_err_dict[':'] = __ST_P0
__STATE_TABLE[__ST_SQOFF].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_SQOFF].normal_char_next_state = __ST_ERR

__STATE_TABLE[__ST_CBKT].special_non_err_dict['/'] = __ST_TCMPL
__STATE_TABLE[__ST_CBKT].normal_char_next_state = __ST_ERR

__STATE_TABLE[__ST_TCMPL].special_non_err_dict['/'] = __ST_EXSL
__STATE_TABLE[__ST_TCMPL].normal_char_next_state = __ST_N0

__STATE_TABLE[__ST_EXSL].special_non_err_dict['/'] = __ST_EXSL
__STATE_TABLE[__ST_EXSL].normal_char_next_state = __ST_N0


# Error messages
__MSG_BKT_MISMATCH = "Mismatching brackets in path token"
__MSG_BKT_ORDER = "] before [ in path token"
__MSG_STARTING_SLASH = "Path cannot start with a /"
__MSG_QUOTE_MISMATCH = "Quote mistmatch in path token"
__MSG_PARSER_ERROR = "Error parsing path token"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __get_next_state(curr_state, curr_char, double_quote_active,
                     single_quote_active):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Private method used to parse a token.  Given current token, character
    index into that token, and current state, return the next state.

    Args:
      curr_state: current parser state

      curr_char: current character

      double_quote_active: Is current char part of a double-quoted string

      single_quote_active: Is current char part of a single-quoted string

    Returns:
      next state (which determines what to do with the current character)

    Raises:
      ParserError (but is never expected)

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Let all chars pass through if quoting is on, except quotes
    # to turn off quoting.
    if ((curr_state == __ST_V) and
        (((double_quote_active) and (curr_char != "\"")) or
        ((single_quote_active) and (curr_char != "'")))):
        return __ST_V

    if (curr_char in __SPECIAL_CHARS):

        try:
            # Explicit next state listed in the table for this
            # current state and special char.
            return __STATE_TABLE[
                curr_state].special_non_err_dict[curr_char]

        # Special characters which are to go to the error state, are
        # not explicitly listed in the table for current state and char
        except KeyError:
            return __ST_ERR

        # Missing state in the table.  Programming error.
        except IndexError:
            print >> sys.stderr, ("Unexpected Internal " +
                                  "IndexError: curr state:%d, curr char:%s" % (
                                  curr_state, curr_char))
            raise ParserError, __MSG_PARSER_ERROR

    # Non-special character.
    return __STATE_TABLE[curr_state].normal_char_next_state


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_nodepath(nodepath):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Parse a token as returned from parse_path_into_tokens()

	See module header for parsing syntax.

	Args:
	  nodepath: nodepath to parse

	Returns:
	  A list of parsed tokens as ENTokens

	Raises:
	  ParserError: Mismatching brackets in path token
	  ParserError: ] before [ in path token
	  ParserError: Path cannot start with a /
	  ParserError: Quote mistmatch in path token
	  ParserError: Error parsing path token

	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Initialize variables and lists to return, to empty values.
    parsed_tokens = []

    # Declare / initialize some local variables.
    curr_state = __ST_START
    new_state = __ST_ERR
    curr_char = ""
    curr_char_idx = 0

    double_quote_active = False
    single_quote_active = False
    bracket_active = False

    name = ""
    values = []
    valpaths = []
    valpathindex = -1
    valindex = -1
    token_in_progress = False

    error_msg = None

    nodepath = nodepath.strip()

    # Special case: empty string
    if (len(nodepath) == 0):
        return parsed_tokens

    # Parse character by character.
    while (curr_char_idx < len(nodepath)):
        curr_char = nodepath[curr_char_idx]

        new_state = __get_next_state(curr_state, curr_char,
                                     double_quote_active, single_quote_active)

        # Brand new token.  Initialize and store first char as the
        # first char of a new name.
        if (new_state == __ST_N0):
            name = curr_char
            values = []
            valpaths = []
            valpathindex = -1
            valindex = -1
            token_in_progress = True

        # Continue appending chars to the name string.
        elif (new_state == __ST_N):
            name += curr_char

        # Prepare to receive chars for a new valpath.
        # An open bracket or colon has been received.
        elif (new_state == __ST_P0):
            bracket_active = True
            valpathindex += 1
            valpaths.insert(valpathindex, "")

        # Receive valpath chars.
        elif (new_state == __ST_P):
            valpaths[valpathindex] += curr_char

        # Prepare to receive chars for a new value string.
        elif (new_state == __ST_V0):
            valindex += 1
            values.insert(valindex, "")

        # Receive value string chars.
        elif (new_state == __ST_V):
            values[valindex] += curr_char

        # Got a double quote.  Turn on double quoting, eat curr char.
        elif (new_state == __ST_DQON):
            double_quote_active = True

        # Got a double quote.  Turn off double quoting, eat curr char.
        elif (new_state == __ST_DQOFF):
            double_quote_active = False

        # Got a single quote.  Turn on single quoting, eat curr char.
        elif (new_state == __ST_SQON):
            single_quote_active = True

        # Got a single quote.  Turn off single quoting, eat curr char.
        elif (new_state == __ST_SQOFF):
            single_quote_active = False

        # Got a closing bracket.  Check that open bracket received.
        elif (new_state == __ST_CBKT):
            if (bracket_active):
                bracket_active = False
            else:
                error_msg = __MSG_BKT_ORDER
                new_state = __ST_ERR

        # Token complete.
        elif (new_state == __ST_TCMPL):
            parsed_tokens.append(ENToken(name, valpaths, values))
            token_in_progress = False

        # Error.
        elif (new_state == __ST_ERR):
            print >> sys.stderr, "Error parsing nodepath"
            print >> sys.stderr, (
                                  "At index %d, remaining string:%s" % (
                                  curr_char_idx, nodepath[curr_char_idx:]))

        # Extra slash received.  Just eat it.
        elif (new_state == __ST_EXSL):
            pass

        # Starting slash received.  Set appropriate error and bomb.
        elif (new_state  == __ST_STSL):
            error_msg = __MSG_STARTING_SLASH
            new_state = __ST_ERR

        else:	# Shouldn't get here
            print >> sys.stderr, ("Oops!  parse_nodepath " +
                                  "unexpected state: %d" % (new_state))
            new_state = __ST_ERR

        # Note: Explicit transition to the start state will never occur.

        # An error has been found.
        if (new_state == __ST_ERR):
            break

        # Prepare to iterate.
        curr_state = new_state
        curr_char_idx += 1

    # Handle errors.
    if (new_state == __ST_ERR):
        if (error_msg is None):
            error_msg = __MSG_PARSER_ERROR
        raise ParserError, error_msg

    if (double_quote_active or single_quote_active):
        raise ParserError, __MSG_QUOTE_MISMATCH

    if (bracket_active):
        raise ParserError, __MSG_BKT_MISMATCH

    # No errors.  Append the token in progress.
    if (token_in_progress):
        parsed_tokens.append(ENToken(name, valpaths, values))

    # Done!
    return parsed_tokens
