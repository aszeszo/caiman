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
# ENParser.py - Enhanced Nodepath Parser module
# =============================================================================
# =============================================================================

import sys

# =============================================================================
# Error handling.
# Declare new classes for errors thrown from this file's classes.
# =============================================================================

class ParserError(Exception):
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
	def __init__(self, name, valpaths=[], values=[]):
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		"""Constructor

		Args:
		  name: The name string of the token.

		  valpaths: List of value paths.

		  values: List of values

		Returns:
		  an initialized ENToken object

		Raises: None
		"""
	# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
__st_start, __st_stsl, __st_n0, __st_n, __st_p0, __st_p, __st_v0, __st_v, \
    __st_dqon, __st_dqoff, __st_sqon, __st_sqoff, __st_cbkt, __st_tcmpl, \
    __st_exsl, __st_err = range(16)

# __st_err has no "current state" storage in the table.
# When __st_err is hit, the method using the table exits.

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


# Class of state table item obects, used only by the state table.
class __st_tbl_item(object):

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
__special_chars = "[]=:/\"\'"

__state_table = []
__state_table.insert(__st_start, __st_tbl_item())
__state_table.insert(__st_n0, __st_tbl_item())
__state_table.insert(__st_n, __st_tbl_item())
__state_table.insert(__st_p0, __st_tbl_item())
__state_table.insert(__st_p, __st_tbl_item())
__state_table.insert(__st_v0, __st_tbl_item())
__state_table.insert(__st_v, __st_tbl_item())
__state_table.insert(__st_dqon, __st_tbl_item())
__state_table.insert(__st_dqoff, __st_tbl_item())
__state_table.insert(__st_sqon, __st_tbl_item())
__state_table.insert(__st_sqoff, __st_tbl_item())
__state_table.insert(__st_cbkt, __st_tbl_item())
__state_table.insert(__st_tcmpl, __st_tbl_item())
__state_table.insert(__st_exsl, __st_tbl_item())
__state_table.insert(__st_stsl, __st_tbl_item())

__state_table[__st_start].special_non_err_dict['/'] = __st_stsl
__state_table[__st_start].normal_char_next_state = __st_n0

__state_table[__st_stsl].normal_char_next_state = __st_err

__state_table[__st_n0].special_non_err_dict['['] = __st_p0
__state_table[__st_n0].special_non_err_dict['='] = __st_v0
__state_table[__st_n0].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_n0].normal_char_next_state = __st_n

__state_table[__st_n].special_non_err_dict['['] = __st_p0
__state_table[__st_n].special_non_err_dict['='] = __st_v0
__state_table[__st_n].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_n].normal_char_next_state = __st_n

__state_table[__st_p0].normal_char_next_state = __st_p

__state_table[__st_p].special_non_err_dict['='] = __st_v0
__state_table[__st_p].special_non_err_dict['/'] = __st_p
__state_table[__st_p].normal_char_next_state = __st_p

__state_table[__st_v0].special_non_err_dict['\"'] = __st_dqon
__state_table[__st_v0].special_non_err_dict['\''] = __st_sqon
__state_table[__st_v0].normal_char_next_state = __st_v

__state_table[__st_v].special_non_err_dict[']'] = __st_cbkt
__state_table[__st_v].special_non_err_dict[':'] = __st_p0
__state_table[__st_v].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_v].special_non_err_dict['\"'] = __st_dqoff
__state_table[__st_v].special_non_err_dict['\''] = __st_sqoff
__state_table[__st_v].normal_char_next_state = __st_v

__state_table[__st_dqon].special_non_err_dict['['] = __st_v
__state_table[__st_dqon].special_non_err_dict[']'] = __st_v
__state_table[__st_dqon].special_non_err_dict['='] = __st_v
__state_table[__st_dqon].special_non_err_dict[':'] = __st_v
__state_table[__st_dqon].special_non_err_dict['/'] = __st_v
__state_table[__st_dqon].special_non_err_dict['\"'] = __st_dqoff
__state_table[__st_dqon].special_non_err_dict['\''] = __st_v
__state_table[__st_dqon].normal_char_next_state = __st_v

__state_table[__st_dqoff].special_non_err_dict[']'] = __st_cbkt
__state_table[__st_dqoff].special_non_err_dict[':'] = __st_p0
__state_table[__st_dqoff].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_dqoff].normal_char_next_state = __st_err

__state_table[__st_sqon].special_non_err_dict['['] = __st_v
__state_table[__st_sqon].special_non_err_dict[']'] = __st_v
__state_table[__st_sqon].special_non_err_dict['='] = __st_v
__state_table[__st_sqon].special_non_err_dict[':'] = __st_v
__state_table[__st_sqon].special_non_err_dict['/'] = __st_v
__state_table[__st_sqon].special_non_err_dict['\"'] = __st_v
__state_table[__st_sqon].special_non_err_dict['\''] = __st_sqoff
__state_table[__st_sqon].normal_char_next_state = __st_v

__state_table[__st_sqoff].special_non_err_dict[']'] = __st_cbkt
__state_table[__st_sqoff].special_non_err_dict[':'] = __st_p0
__state_table[__st_sqoff].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_sqoff].normal_char_next_state = __st_err

__state_table[__st_cbkt].special_non_err_dict['/'] = __st_tcmpl
__state_table[__st_cbkt].normal_char_next_state = __st_err

__state_table[__st_tcmpl].special_non_err_dict['/'] = __st_exsl
__state_table[__st_tcmpl].normal_char_next_state = __st_n0

__state_table[__st_exsl].special_non_err_dict['/'] = __st_exsl
__state_table[__st_exsl].normal_char_next_state = __st_n0


# Error messages
__msg_bkt_mismatch = "Mismatching brackets in path token"
__msg_bkt_order = "] before [ in path token"
__msg_starting_slash = "Path cannot start with a /"
__msg_quote_mismatch = "Quote mistmatch in path token"
__msg_parser_error = "Error parsing path token"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __get_next_state(curr_state, curr_char, double_quote_active,
    single_quote_active):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Private method used to parse a token.  Given current token, character
# index into that token, and current state, return the next state.
#   
# Args:
#   curr_state: current parser state
#
#   curr_char: current character
#
#   double_quote_active: Is current char part of a double-quoted string
#
#   single_quote_active: Is current char part of a single-quoted string
#
# Returns:
#   next state (which determines what to do with the current character)
#
# Raises:
#   ParserError (but is never expected)
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Let all chars pass through if quoting is on, except quotes
	# to turn off quoting.
	if ((curr_state == __st_v) and
	    (((double_quote_active) and (curr_char != "\"")) or
	    ((single_quote_active) and (curr_char != "'")))):
		return __st_v

	if (__special_chars.find(curr_char) != -1):

		try:
			# Explicit next state listed in the table for this
			# current state and special char.
			return __state_table[
			    curr_state].special_non_err_dict[curr_char]

		# Special characters which are to go to the error state, are 
		# not explicitly listed in the table for current state and char 
		except KeyError:
			return __st_err

		# Missing state in the table.  Programming error.
		except IndexError:
			print >>sys.stderr, ("Unexpected Internal " +
			    "IndexError: curr state:%d, curr char:%s" % (
			    curr_state, curr_char))
			raise ParserError, __msg_parser_error

	# Non-special character.
	return __state_table[curr_state].normal_char_next_state


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
	curr_state = __st_start
	new_state = __st_err
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
		if (new_state == __st_n0):
			name = curr_char
			values = []
			valpaths = []
			valpathindex = -1
			valindex = -1
			token_in_progress = True

		# Continue appending chars to the name string.
		elif (new_state == __st_n):
			name += curr_char

		# Prepare to receive chars for a new valpath.
		# An open bracket or colon has been received.
		elif (new_state == __st_p0):
			bracket_active = True
			valpathindex += 1
			valpaths.insert(valpathindex, "")

		# Receive valpath chars.
		elif (new_state == __st_p):
			valpaths[valpathindex] += curr_char

		# Prepare to receive chars for a new value string.
		elif (new_state == __st_v0):
			valindex += 1
			values.insert(valindex, "")

		# Receive value string chars.
		elif (new_state == __st_v):
			values[valindex] += curr_char

		# Got a double quote.  Turn on double quoting, eat curr char.
		elif (new_state == __st_dqon):
			double_quote_active = True

		# Got a double quote.  Turn off double quoting, eat curr char.
		elif (new_state == __st_dqoff):
			double_quote_active = False

		# Got a single quote.  Turn on single quoting, eat curr char.
		elif (new_state == __st_sqon):
			single_quote_active = True

		# Got a single quote.  Turn off single quoting, eat curr char.
		elif (new_state == __st_sqoff):
			single_quote_active = False

		# Got a closing bracket.  Check that open bracket received.
		elif (new_state == __st_cbkt):
			if (bracket_active):
				bracket_active = False
			else:
				error_msg = __msg_bkt_order
				new_state = __st_err

		# Token complete.
		elif (new_state == __st_tcmpl):
			parsed_tokens.append(ENToken(name, valpaths, values))
			token_in_progress = False

		# Error.
		elif (new_state == __st_err):
			print >>sys.stderr, "Error parsing nodepath"
			print >>sys.stderr, (
			    "At index %d, remaining string:%s" % (
			    curr_char_idx, nodepath[curr_char_idx:]))

		# Extra slash received.  Just eat it.
		elif (new_state == __st_exsl):
			pass

		# Starting slash received.  Set appropriate error and bomb.
		elif (new_state  == __st_stsl):
			error_msg = __msg_starting_slash
			new_state = __st_err

		else:	# Shouldn't get here
			print >>sys.stderr, ("Oops!  parse_nodepath " +
			    "unexpected state: %d" % (new_state))
			new_state = __st_err

		# Note: Explicit transition to the start state will never occur.

		# An error has been found.
		if (new_state == __st_err):
			break

		# Prepare to iterate.
		curr_state = new_state
		curr_char_idx += 1

	# Handle errors.
	if (new_state == __st_err):
		if (error_msg == None):
			error_msg = __msg_parser_error
		raise ParserError, error_msg

	if (double_quote_active or single_quote_active):
		raise ParserError, __msg_quote_mismatch

	if (bracket_active):
		raise ParserError, __msg_bkt_mismatch

	# No errors.  Append the token in progress.
	if (token_in_progress):
		parsed_tokens.append(ENToken(name, valpaths, values))

	# Done!
	return parsed_tokens
