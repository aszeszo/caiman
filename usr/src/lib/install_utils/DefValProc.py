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
Module to validate defaults and contents info.
"""
# =============================================================================
# =============================================================================

import sys
import subprocess

from osol_install.TreeAcc import TreeAcc
from osol_install.TreeAcc import TreeAccNode
from osol_install.TreeAcc import TreeAccError
from osol_install.install_utils import canaccess
from osol_install.install_utils import space_parse

# =============================================================================
# Constants
# =============================================================================

# Error status
GENERAL_ERR = 1
SUCCESS = 0

# XML validator program, run on XML docs to validate against a schema.
XML_VALIDATOR = "/bin/xmllint --relaxng "
XML_REFORMAT_SW = "--format"

# Defaults and validation manifest doc and schema filenames.
DEFVAL_SCHEMA = "/usr/share/lib/xml/rng/defval-manifest.rng "

# Schema to validate manifest XML doc against.
MANIFEST_SCHEMA = "/usr/lib/python2.6/vendor-packages/osol_install/" + \
                  "distro_const/DC-manifest.rng "

# Default XML value if invert isn't specified in the defval-manifest.
DEFAULT_INVERT_VALUE_STR = "False"

# =============================================================================
# General module initializion code
# =============================================================================

DEFAULT_INVERT_VALUE = (DEFAULT_INVERT_VALUE_STR == "True")

# =============================================================================
# Error handling classes
# =============================================================================
class ManifestProcError(StandardError):
    """Exception for manifest_proc errors"""
    pass



# =============================================================================
class _HelperDicts:
# =============================================================================
    """ Class of objects containing modules, methods and optionally invert
        statuses indexed by a reference (ref) string.

    These objects contain dictionaries which allow a module, method and
    invert status combination to be referenced by a common string.

    """
# =============================================================================

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, module_dict, method_dict, invert_dict=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor

        Args:
          module_dict: Dictionary of modules indexed by a ref string

          method_dict: Dictionary of methods indexed by a ref string

          invert_dict: Optional dictionary of boolean invert statuses
            indexed by a ref string

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.modules = module_dict
        self.methods = method_dict
        self.inverts = invert_dict


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @staticmethod
    def new(defval_tree, nodepath):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Return a new helper object containing modules and methods
            indexed by a reference (ref) string.

        Args:
          defval_tree: Tree of defaults and validation nodes (TreeAccNodes)
            containing the information.  This tree has been read in from the
            defval manifest and contains references to the validator and default
            setter methods and their host modules.  It is assumed that the
            methods are part of a class of the same name as their host module.

          nodepath: Root of tree branch containing information on helper
            methods of interest.  For example, the part of the tree
            containing validator methods or the part containing
            methods filling in defaults.

        Returns:
          If information is found under "nodepath" in the defval_tree:
            returns a new helper object containing dictionaries for
            module and method.  Both dictionaries are indexed by a
            ref string.
          Otherwise returns an object with empty module and method dicts

        Raises:
          ManifestProcError: Helper ref (index string) is not unique
          ManifestProcError: Invalid python helper module name
          ImportError: Helper module cannot be imported

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        modules = {}	# Dict of modules indexed by ref
        methods = {}	# Dict of methods indexed by ref
        inverts = {}	# Dict of boolean invert statuses indexed by ref
        class_names = {}	# Used for internal processing

        # Extract helpers from the tree.
        helpers = defval_tree.find_node(nodepath)
        if (len(helpers) == 0):
            return _HelperDicts(modules, methods, None)

        # Each helper element contains attributes for module, method
        # and ref.
        for helper in helpers:
            # Get list of attributes for current helper element.
            helper_attrs = helper.get_attr_dict()

            # This is the ref string used to index into the
            # dictionaries for a given method in a given module.
            ref = helper_attrs["ref"]

            # Make sure the helper ref is unique.
            if ref in methods:
                raise ManifestProcError, ("HelperDicts.new: helper ref " +
                                          ref + " is not unique")

            # Get and validate module name.
            module_name = helper_attrs["module"]
            if not module_name.endswith(".py"):
                raise ManifestProcError, ("HelperDicts.new: Invalid python " +
                                         "helper module name: " + module_name)

            # Assume class is same name as the module it's in.
            class_name = module_name[:-3]

            # Maintain a list of class names.  This list is used
            # to prevent multiple compilations of the same module.

            # Search list of class names for a match.  If a match
            # is found, refer to the corresponding module instance
            # instead of creating a new one.
            for key, name in class_names.items():
                if (class_name == name):
                    modules[ref] = modules[key]
                    break

            # Note: in trouble if rename helper_module to
            # helpers.  (Maybe can use local_dicts?)

            # Module not in list.
            else:
                # Add name to the list and compile the module.
                class_names[ref] = class_name

                # Import the module.
                # The ugly-looking rfind below strips all to
                # the left of the final dot (e.g package names).
                # __import__ returns package, not module, unless a method
                # name is given as fourth arg.
                constr_name = class_name[(class_name.rfind(".") + 1):]
                module_imp = __import__(class_name, globals(), locals(),
                                        [constr_name], -1)

                # Instantiate and save a module instance.
                constr = getattr(module_imp,
                                 class_name[(class_name.rfind(".") + 1):])
                modules[ref] = constr()

            # Save the method in the instance's methods dictionary.
            methods[ref] = helper_attrs["method"]

            # Save invert status in instance's inverts dictionary.
            # If not specified, assume DEFAULT_INVERT_VALUE_STR.
            try:
                ivalue = helper_attrs["invert"]
            except KeyError:
                ivalue = DEFAULT_INVERT_VALUE_STR
            inverts[ref] = (ivalue == "True")

        # If all inverts values are the default, it may be that this
        # HelperDict is not for validation and inverts aren't used.
        # Optimize that if all invert values are the default, don't
        # store inverts in this _HelperDicts instance.
        keep_inverts = False
        for ivalue in inverts.itervalues():
            if (ivalue != DEFAULT_INVERT_VALUE):
                keep_inverts = True
                break
        if (not keep_inverts):
            inverts = None

        return _HelperDicts(modules, methods, inverts)


# =============================================================================
# Procedural functions, not part of a class
# =============================================================================

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __validate_vs_schema(schema, in_xml_doc, out_xml_doc=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Validate an XML document against a schema.

    Runs the command given by XML_VALIDATOR.  Schema must follow the
    XML_VALIDATOR string.  If out_xml_doc is specified, reformat the
    xml doc  using the XML_REFORMAT_SW passed to the validator.

    Args:
      schema: The schema to validate against.

      in_xml_doc: The XML document to validate.

      out_xml_doc: Reformatted XML doc

    Returns: N/A

    Raises:
      OSError: Error starting or running shell
      ManifestProcError: The validator returned an error status or
        was terminated by a signal.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    schema = schema.strip()
    in_xml_doc = in_xml_doc.strip()

    # Need to check file access explicitly since the XML
    # validator doesn't return proper errno if files not accessible.
    # IOError exceptions (from canaccess()) require no special
    # handling here, except for closing outfile.
    # Just let IOErrors get thrown and propagated.
    canaccess(schema, "r")
    canaccess(in_xml_doc, "r")

    command_list = XML_VALIDATOR.split()
    command_list.append(schema)

    if (out_xml_doc is not None):
        command_list.append(XML_REFORMAT_SW)
        outfile = file(out_xml_doc.strip(), "w")
    else:
        outfile = file("/dev/null", "w")

    command_list.append(in_xml_doc)

    try:
        try:
            rval = subprocess.Popen(command_list, stdout=outfile).wait()
            if (rval < 0):
                print >> sys.stderr, ("validate_vs_schema: " +
                                      "Validator terminated by signal" +
                                      str(-rval))
            elif (rval > 0):
                print >> sys.stderr, ("validate_vs_schema: " +
                                      "Validator terminated with status " +
                                      str(rval))
            if (rval != 0):
                raise ManifestProcError, ("validate_vs_schema: " +
                                          "Validator terminated abnormally")

        # Print extra error message here for OSErrors as unexpected.
        except OSError:
            print >> sys.stderr, ("validate_vs_schema: " +
                                  "Error starting or running shell:")
            print >> sys.stderr, "shell_list = " + str(command_list)
            raise
    finally:
        outfile.close()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __generate_ancestor_nodes(tree, nodepath):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Create ancestor nodes along given nodepath from root on down, as
        needed.

    Nodes created will have no value, and all but the last node created
    will have one child, the next node in the created nodepath.

    Nodepath is assumed to be from the tree root and deterministic at each
    piece.  Since created nodepath is to a soon-to-be non-leaf node, all
    nodepath items created will be elements.

    Args:
      tree: Tree in which the nodes are created.

      nodepath: Path defining where nodes are created in the tree.

    Returns:
      The node created furthest from the root.

    Raises:
      ManifestProcError: non-deterministic nodepath specified.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    nodepath_pieces = nodepath.split("/")

    # Note current_node starts out and remains a one-item list.
    ancestor_node = current_node = tree.find_node(nodepath_pieces[0])

    # Err out if the nodepath (from the defval manifest) doesn't jibe
    # with the project manifest.  At a minimum, the tops of the trees
    # should be the same.
    if (len(ancestor_node) == 0):
        raise ManifestProcError, ("generate_ancestor_nodes: " +
                                  "manifest and defval manifest " +
                                  "are incompatible")

    # Iterate from the top of the nodepath, filling in nodes which are
    # missing.  New nodes will have no value.
    for i in range(1, len(nodepath_pieces)):
        current_node = tree.find_node(nodepath_pieces[i],
                                      ancestor_node[0])

        # Add missing ancestor node.
        if (len(current_node) == 0):
            new_node = tree.add_node(nodepath_pieces[i], "",
                                     TreeAccNode.ELEMENT, ancestor_node[0])
            current_node = [new_node]

        elif (len(current_node) > 1):
            raise ManifestProcError, ("generate_ancestor_nodes: " +
                                      "non-deterministic nodepath specified")

        ancestor_node = current_node

    return current_node


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __get_value_from_helper(method_ref, deflt_setter_dicts,
                            parent_node, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Consult a helper method to calculate/retrieve a value.

    Args:
      method_ref: Nickname reference of the helper method to call.

      deflt_setter_dicts: _HelperDicts object containing helper information

      parent_node: Parent node of the new node (for whose value the helper
        is being consulted).  The helper method will be called with
        this node, from which it can get a pointer to the tree as well
        as context to perform its calculation.

      debug: Print tracing / debug messages when True

    Returns:
      A string representation of the value as returned by the helper method.
          Convert any python boolean value strings to all-lowercase, to
        match how booleans are represented in XML documents.

    Raises:
      ManifestProcError: Helper method missing from defval manifest file
      AttributeError: Helper method is not in module
      StandardError: Helper method raised an exception

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    if ((method_ref not in deflt_setter_dicts.modules) or
        (method_ref not in deflt_setter_dicts.methods)):
        raise ManifestProcError, ("get_value_from_helper: Helper method " +
                                  "ref %s missing from defval manifest file" %
                                  method_ref)

    module = deflt_setter_dicts.modules[method_ref]
    method = deflt_setter_dicts.methods[method_ref]

    if (debug):
        print ("Call helper method " +
               deflt_setter_dicts.methods[method_ref] + "()")

    # Note: methods calculating defaults take only the parent node as arg.
    try:
        func = getattr(module, method)
    except AttributeError:
        print >> sys.stderr, ("get_value_from_helper: Helper method " +
                              "%s not in module %s" % (method, module))
        raise

    try:
        value = func(parent_node)

    except StandardError:
        print >> sys.stderr, ("get_value_from_helper: Helper method " +
                                  "%s raised an exception: " % method_ref)
        raise

    # Convert all return values to strings.
    #
    # Booleans are a special case.  Python boolean values (and their string
    # equivalents when converted) begin with capital letters.  However, XML
    # boolean string values are all in lower case.

    if (isinstance(value, bool)):
        retvalue = str(value).lower()
    else:
        retvalue = str(value)
    return retvalue


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __do_skip_if_no_exist(attributes, manifest_tree, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Determines whether or not to skip processing of a node because an
        ancestral node to it doesn't exist.

    Check if the "skip_if_no_exist" attribute exists in the attributes
    list passed in.  If it does, and if the (ancestral) node it refers to
    doesn't exist in manifest_tree, then return True, that it's OK to skip
    creating/processing.

    Args:
      attributes: Attributes list to check for skip_if_no_exist in.

      manifest_tree: tree to search for the node identified by the
        skip_if_no_exist attribute.

      debug: Print tracing / debug messages when True

    Returns:
      True: skip_if_no_exist attribute exists and identifies a node which
        doesn't exist.
      False: otherwise

    Raises: None

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    skip_if_no_exist = attributes.get("skip_if_no_exist", "")
    if (skip_if_no_exist != ""):
        if (debug):
            print ("Skip_if_no_exist = %s specified.  checking" %
                   skip_if_no_exist)
        if (len(manifest_tree.find_node(skip_if_no_exist)) == 0):
            if (debug):
                print skip_if_no_exist + " node doesn't exist"
            return True
    return False


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def add_defaults(manifest_tree, defval_tree, debug=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Add defaults to manifest_tree, based on defval_tree specifications.

    This method processes defval_tree nodes with the nodepath "default",
    each of which specifies a new default.  This method is a noop if
    defval_tree has no "default" nodes.  "default" nodes have the following
    attributes:
    - nodepath: The nodepath of the node for which the default is specified.
    - type: type of node (TreeAccNode): must be "attribute" or "element"
    - from: how to derive the default: must be either "value" or "helper".
        Node's value is a helper method reference when from = "helper"
        Node's value is the default value when from = "value"
    - missing_parent: (optional) What to do if a node whose nodepath matches
        the nodepath of an immediate parent node (the nodepath less the
        item beyond the final /) is missing.  When specified, must be
        one of the following:
        - "create": Create a new empty parent node and then create a
            new node with the specified nodepath and default value.
            Parent node to create must be deterministic from
            nodepath.
        - "skip": Do nothing.
        - "error": Err out.
        - default if not specified = "error"
    - empty_str: (optional) What to do when an empty string is encountered.
        An empty string is defined here as a zero length string, or ""
        or '' to handled quote-enveloped empty strings.  When specified,
        must be one of the following:
        - "set_default": Determine the default as if no node was
            present, then change the value of any matching
            empty-string nodes to the default value.
        - "valid": Accept the empty string as a valid value.  Do
            nothing.
        - "error": Flag the empty string as an error.
        Note that all matching nodes with empty strings will have their
        default value calculated and plugged.

    - skip_if_no_exist: (optional) The nodepath of an ancestor node.  If the
        ancestor node is missing, skip processing.

    Args:
      manifest_tree: The tree to which default nodes are added.

      defval_tree: The tree containing "default" nodes defined as above.

      debug: Turn on debug / tracing messages when True

    Returns: N/A

    Raises:
      KeyError: A required attribute of a "default" node is missing.
      ManifestProcError: Error getting helper methods
      ManifestProcError: Parent for node at a given nodepath does not exist,
        and the missing_parent attribute is either missing or set to
        "error"
      ManifestProcError: non-deterministic nodepath specified (for parent
        when creating parents of default nodes).
      ManifestProcError: Invalid missing_parent attribute value specified

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    errors = False

    # Fetch dictionaries used to reference the helper methods and modules.
    try:
        deflt_setters = _HelperDicts.new(defval_tree, "helpers/deflt_setter")
    except ManifestProcError, err:
        print >> sys.stderr, ("add_defaults: Error getting default setter " +
                              "methods from defval XML file")
        print >> sys.stderr, str(err)
        raise

    # Get a list of all defaults to process.
    defaults = defval_tree.find_node("default")
    if (len(defaults) == 0):
        return

    for curr_def in defaults:
        attributes = curr_def.get_attr_dict()

        manifest_nodepath = attributes["nodepath"]
        if (debug):
            print "Checking defaults for " + manifest_nodepath

        if __do_skip_if_no_exist(attributes, manifest_tree, debug):
            if (debug):
                print "Ancestor doesn't exist.  Skipping..."
            continue

        value_from_xml = curr_def.get_value()
        type_str = attributes["type"]
        via = attributes["from"]

        if (type_str == "element"):
            node_type = TreeAccNode.ELEMENT
        else:
            node_type = TreeAccNode.ATTRIBUTE

        # Nodepaths which are direct children of the root are special cases
        try:
            (parent_nodepath, child_nodepath) = manifest_nodepath.rsplit("/",
                                                                         1)
        except ValueError:	# No slashes present in nodepath
            parent_nodepath = ""
            child_nodepath = manifest_nodepath

        # Fetch the parent nodes.  We cannot just search for the
        # children directly because we want to guarantee that every
        # viable parent has at least one child which matches the default
        # nodepath.  We need to correlate every element containing a
        # default nodepath to its parent.
        parent_nodes = manifest_tree.find_node(parent_nodepath)

        # Missing parent nodes anywhere along the tree are errors
        # if they are those nodes are required.  This is not always the
        # case though...
        #
        # When a node is a parent to an as-yet-unspecified element to
        # be filled in with a default, just create it if it is missing.
        #
        # When a parent is itself an optional item, and it is being
        # sought so that it can be filled in with default attributes or
        # children elements if it exists, do nothing if it is not there.

        # A parent somewhere in the chain back to the root is missing.
        if (len(parent_nodes) == 0):

            # Treat no "missing_parent" attribute for this nodepath
            # as missing_parent = "error"
            no_parent_handling = attributes.get("missing_parent", "error")

            if (no_parent_handling == "error"):
                print >> sys.stderr, ("add_defaults: " +
                                      "Parent for node at nodepath " +
                                      manifest_nodepath + " does not exist")
                errors = True
                continue

            elif (no_parent_handling == "create"):
                try:
                    parent_nodes = __generate_ancestor_nodes(manifest_tree,
                                                             parent_nodepath)
                except ManifestProcError, err:
                    print str(err)
                    print >> sys.stderr, ("add_defaults: Cannot create " +
                                          "ancestor nodes for node at " +
                                          "nodepath " + manifest_nodepath)
                    errors = True
                    continue

            elif (no_parent_handling == "skip"):
                continue

            else:
                # Shouldn't get here if defaults / validation
                # manifest passed schema validation.
                print >> sys.stderr, ("add_defaults: Invalid missing_parent " +
                                      "attribute value specified: " +
                                      no_parent_handling)
                errors = True
                continue

        # Check how to handle an empty string.  Sometimes an empty
        # string is a valid value.  Other times it may be as valid as a
        # missing value, and a default should be set in its place.  The
        # latter case may prove useful for documentation purposes: as a
        # placeholder in the XML file for something which can be filled
        # in later by defaults processing.  Additionally, an empty
        # string can be an error.
        empty_str = attributes.get("empty_str", "set_default")

        if ((empty_str != "set_default") and (empty_str != "valid") and
            (empty_str != "error")):

            # Shouldn't get here if defaults / validation manifest
            # passed schema validation.
            print >> sys.stderr, ("add_defaults: Invalid \"empty_str\" " +
                                  "attribute = " + empty_str)
            errors = True
            continue

        # Check each parent node for children.
        for parent_node in parent_nodes:

            # Assume each parent must have at least one child
            # (element or attribute) which matches the nodepath of
            # the default.  If a parent has no such child, give it
            # one with the default value.

            # Handle any values present as empty strings.
            nodes = manifest_tree.find_node(child_nodepath, parent_node)
            if nodes:
                for node in nodes:

                    # Zero length strings and "" and ''
                    # are considered empty here.
                    node_value = node.get_value()
                    if (node_value and not
                        ((len(node_value) == 2) and
                        ((node_value == '""') or (node_value == "''")))):
                        continue

                    elif (empty_str == "valid"):
                        if (debug):
                            print "Valid empty string found"
                        continue

                    elif (empty_str != "set_default"):
                        print >> sys.stderr, ("add_defaults: Unpermitted " +
                                              "empty string found for " +
                                              "nodepath " + manifest_nodepath)
                        errors = True
                        continue

                    # Install default.
                    try:
                        default_value = __get_default(via, value_from_xml,
                                                      deflt_setters,
                                                      parent_node, debug)
                    except ManifestProcError:
                        errors = True
                        continue

                    if (debug):
                        print ("Replacing %s value at %s with %s..." %
                               (type_str, manifest_nodepath, default_value))
                    manifest_tree.replace_value(child_nodepath, default_value,
                                                parent_node)
                continue

            # No value is present.
            # A new node w/a default value is needed.
            try:
                default_value = __get_default(via, value_from_xml,
                                              deflt_setters, parent_node,
                                              debug)
            except ManifestProcError:
                errors = True
                continue

            if (debug):
                print ("Adding %s value at %s with %s..." %
                       (type_str, manifest_nodepath, default_value))
            manifest_tree.add_node(child_nodepath, default_value,
                                   node_type, parent_node)

    if errors:
        raise ManifestProcError, ("One or more errors occured while " +
                                  "setting defaults")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __get_default(via, value_from_xml, deflt_setters, parent_node, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Get or calculate a default value.

    Args:
      via: "from" field of the relevant default entry in the defval XML doc:
        set to either "helper" or "value"

      value_from_xml: "value" of a default entry in the default XML doc

      deflt_setters: dictionary of default setter helper methods.

      parent_node: Parent node of the nodes receiving defaults

      debug: Turn on debug / tracing messages when True

    Returns: String value of the sought default

    Raises:
      ManifestProcError: exceptions from __get_value_from_helper
      ManifestProcError: Invalid "from" attribute

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Call helper method to determine the value.
    if (via == "helper"):
        try:
            default_value = __get_value_from_helper(value_from_xml,
                                                    deflt_setters, parent_node,
                                                    debug)

        # Skip and muddle along as best we can on error
        except StandardError, err:
            print >> sys.stderr, str(err)
            print >> sys.stderr, ("add_defaults: Error getting " +
                                  "default value from helper method for " +
                                  value_from_xml)
            raise ManifestProcError, str(err)

    # Get the value from the defaults / validation manifest.
    elif (via == "value"):
        default_value = value_from_xml

    # Shouldn't get here if defaults / validation manifest
    # passed schema validation.
    else:
        raise ManifestProcError, ("add_defaults: " +
                          'Invalid "from" attribute = ' + via)

    return default_value


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __validate_node(validator_ref, validator_dicts, node, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Perform semantic validation on a given node.

    Args:
      method_ref: Nickname reference of the helper method to call.

      validator_dicts: _HelperDicts object containing helper information.

      node: The TreeAccNode to validate.

      debug: Print debug / tracing messages when True

    Returns:
        True: The given node has a valid value.
        False: The given node has an invalid value or there was
            a problem calling the validator helper method.

    Raises:
      ManifestProcError: Validator missing from the defval manifest file.
      AttributeError: Helper method not in module.
      StandardError: Validator method threw an exception.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Get the module and method to call.
    module = validator_dicts.modules.get(validator_ref)
    method = validator_dicts.methods.get(validator_ref)

    if ((module is None) or (method is None)):
        raise ManifestProcError, ("validate_node: Validator ref " +
                                  validator_ref +
                                  " missing from defval manifest file")

    if (validator_dicts.inverts is not None):
        invert = validator_dicts.inverts.get(validator_ref,
                                             DEFAULT_INVERT_VALUE)
    else:
        invert = DEFAULT_INVERT_VALUE

    if (debug):
        print "    call validator method " + method + "()"

    valid = True
    try:
        func = getattr(module, method)
    except AttributeError:
        print >> sys.stderr, ("validate_node: Helper method " +
                              "%s not in module %s" % (method, module))
        raise

    try:
        # Note: methods doing validation return True if valid
        is_valid = func(node) ^ invert
        if (not is_valid):
            print >> sys.stderr, ("validate_node: Content \"" +
                                  node.get_value() + "\" at " +
                                  node.get_path() + " did not validate")
            valid = False

    except StandardError, err:
        print >> sys.stderr, "Validator method threw an exception:"
        print >> sys.stderr, str(err)
        print >> sys.stderr, ("validate_node: Error validating content \"" +
                              node.get_value() + "\" at " + node.get_path() +
                              " using validator " + validator_ref)
        raise
    return valid


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def validate_content(manifest_tree, defval_tree, debug=False):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Validate nodes of manifest_tree, based on defval_tree specifications.

    This method processes defval_tree nodes with the nodepath "validate",
    each of which specifies one or more nodes in the manifest_tree, and a
    helper method called to do the validation.  This method is a noop if
    defval_tree has no "validate" nodes.
    There are different kinds of "validate" nodes.

    - "validate nodepath=" nodes have the following characteristics:
        - "nodepath" attribute: The nodepath of the node(s) to validate.
        - "missing" attribute: (optional) What to do if a node which
            would match the given nodepath is missing.  When
            specified, must be one of the following:
            - "ok_if_no_parent": The missing node is acceptable only
                if it's parent node is also missing.
            - "ok": The missing node is always acceptable.
            - "error": The missing node is not acceptable.
            Defaults to "error" if "missing" attribute not specified
        - skip_if_no_exist: (optional) The nodepath of an ancestor node.
            If the ancestor node is missing, skip processing.
        - The value of the node is a comma-separated list of one or more
            helper methods called to do the validation.

    - "validate group=" nodes have the following characteristics:
        - "group" attribute: The name of a helper method to call to do
            the validation.
        - The value of the node is a comma-separated list of one or
            more nodepaths, whose matching manifest_tree nodes are
            to be validated.
        - There is no error handling for missing nodes.

    - "validate exclude=" nodes have the following characteristics:
        - "exclude" attribute: The name of a helper method to call to
            do the validation.
        - The value of the node is a comma-separated list of one or
            more nodepaths, whose matching manifest_tree nodes are
            to be EXCLUDED from validation.

    Args:
      manifest_tree: The tree containing nodes to validate.

      defval_tree: The tree containing "validate" nodes defined as above.

      debug: When true, prints debug / tracing messages

    Returns: N/A

    Raises:
      KeyError: A required attribute of a "validate" node is missing.
      ManifestProcError: Error getting helper methods
      ManifestProcError: One or more validation errors found.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    group_validate = []
    singles_validate = []
    exclude_validate = []

    # Fetch dictionaries used to reference the helper methods, modules and
    # invert statuses.
    try:
        validator_dicts = _HelperDicts.new(defval_tree, "helpers/validator")
    except ManifestProcError, err:
        print >> sys.stderr, ("validate_content: Error getting validator " +
                              "methods from defval XML file")
        print >> sys.stderr, str(err)
        raise

    # Fetch all "validate" nodes from the defval tree.
    to_validate = defval_tree.find_node("validate")
    if not to_validate:
        return

    # Create separate lists of the different kinds of "validate" nodes.
    for validateme in to_validate:
        attributes = validateme.get_attr_dict()

        # Do specific nodes specified with "nodepath" attribute, for
        # this pass.
        if ("nodepath" in attributes):
            if (debug):
                print ("Checking skip_if_no_exist for " +
                       "validate nodepath=" + attributes["nodepath"])
            if __do_skip_if_no_exist(attributes, manifest_tree, debug):
                if (debug):
                    print "Node doesn't exist.  Skipping..."
                continue

            singles_validate.append(validateme)
            continue

        if ("group" in attributes):
            group_validate.append(validateme)
            continue

        if ("exclude" in attributes):
            exclude_validate.append(validateme)
            continue

        # Schema should protect from ever getting here...
        print >> sys.stderr, ("Nodepath, group or exclude attribute " +
                              "missing from \"validate\" entry")
        raise

    if (len(singles_validate) > 0):
        if (debug):
            print "Processing singles validation"
        __validate_singles(singles_validate, validator_dicts,
                           manifest_tree, debug)

    if (len(group_validate) > 0):
        if (debug):
            print "Processing group validation"
        __validate_group(group_validate, validator_dicts,
                         manifest_tree, debug)

    if (len(exclude_validate) > 0):
        if (debug):
            print "Processing global validation"
        __validate_exclude(exclude_validate, validator_dicts,
                           manifest_tree, debug)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __validate_singles(to_validate, validator_dicts, manifest_tree, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Process a list of "validate nodepath=" nodes.

    Args:
      to_validate: List of items to validate.

      validator_dicts: _HelperDicts object containing validator method
         information.

      manifest_tree: Tree containing nodes to validate.

      debug: When true, prints debug / tracing messages

    Returns: N/A

    Raises:
      ManifestProcError: One or more validation errors found.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    errors = False
    for validateme in to_validate:
        attributes = validateme.get_attr_dict()
        manifest_nodepath = attributes["nodepath"]

        if (debug):
            print "Validating node(s) at nodepath " + manifest_nodepath

        validator_list = space_parse(validateme.get_value())

        # Nodepaths which are direct children of the root are special cases
        try:
            (parent_nodepath, child_nodepath) = manifest_nodepath.rsplit("/",
                                                                         1)
        except ValueError:	# No slashes present in nodepath
            parent_nodepath = ""
            child_nodepath = manifest_nodepath

        # Treat no "missing" attribute for this nodepath
        # as missing_parent = "error"
        missing_handling = attributes.get("missing", "error")

        # Try to get the parent nodes which match the nodepath less the
        # final branch.
        parent_nodes = manifest_tree.find_node(parent_nodepath)

        # An ancestor somewhere in the chain back to the root is missing
        if (len(parent_nodes) == 0):
            # If parent doesn't exist, the item sought can't either.
            if (missing_handling == "error"):
                print >> sys.stderr, ("validate_content: Parent for node at " +
                                      "nodepath " + manifest_nodepath +
                                      " does not exist")
                errors = True

            # Shouldn't get here if defaults / validation
            # manifest passed schema validation.
            elif ((missing_handling != "ok") and
                  (missing_handling != "ok_if_no_parent")):
                print >> sys.stderr, ("validate_content: Invalid " +
                                      "missing_handling attribute value " +
                                      "specified: " + missing_handling)
                errors = True
            continue

        # Check each parent node for children.
        for parent_node in parent_nodes:
            if (debug):
                print "  Processing new parent node"

            # Each parent must have at least one child
            # (element or attribute) which matches the nodepath to
            # validate, unless missing_handling = "ok".
            nodes = manifest_tree.find_node(child_nodepath, parent_node)
            if (len(nodes) == 0):
                if (missing_handling != "ok"):
                    print >> sys.stderr, ("validate_content: node with " +
                                          "nodepath " + manifest_nodepath +
                                          " does not exist")
                    errors = True
                continue

            # At this point at least one node to validate exists
            # for each parent node.

            # Loop through each child.
            for node in nodes:

                # Call helper methods to do the validation.
                for validator in validator_list:
                    validator_ref = validator.strip()
                    try:
                        if (not __validate_node(validator_ref,
                            validator_dicts, node, debug)):
                            errors = True
                    except StandardError, err:
                        print >> sys.stderr, ("Exception while validating " +
                                              "node " + node.get_path())
                        print >> sys.stderr, str(err)
                        errors = True
    if errors:
        raise ManifestProcError, ("validate_singles: One or more validation " +
                                  "errors found.")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __validate_group(to_validate, validator_dicts, manifest_tree, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Process a list of "validate group=" nodes.

    Args:
      to_validate: List of items to validate.

      validator_dicts: _HelperDicts object containing validator method
         information.

      manifest_tree: Tree containing nodes to validate.

      debug: Print tracing / debug messages when True

    Returns: N/A

    Raises:
      ManifestProcError: One or more validation errors found.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    errors = False
    for validateme in to_validate:
        attributes = validateme.get_attr_dict()
        validator_ref = attributes["group"].strip()

        if (debug):
            print "  Processing group validated by " + validator_ref + "()"

        # Get the list of nodepaths of nodes to validate as a string,
        # then break into individual strings.
        nodepaths = space_parse(validateme.get_value())

        for raw_nodepath in nodepaths:
            nodepath = raw_nodepath.strip()
            if (debug):
                print "  Validating nodes matching nodepath " + nodepath
            nodes = manifest_tree.find_node(nodepath)

            if (len(nodes) == 0):
                if (debug):
                    print "    ... No matching nodes"
                continue

            # Check each node.
            for node in nodes:
                value = node.get_value()
                if (debug):
                    print "new_node: value = " + value

                try:
                    if (not __validate_node(validator_ref,
                        validator_dicts, node, debug)):
                        errors = True
                except StandardError, err:
                    print >> sys.stderr, ("Exception while validating node " +
                                          node.get_path())
                    print >> sys.stderr, str(err)
                    errors = True

    if errors:
        raise ManifestProcError, ("validate_group: One or more validation " +
                                  "errors found.")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def __validate_exclude(to_exclude, validator_dicts, manifest_tree, debug):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Process a list of "validate exclude=" nodes.

    Args:
      to_validate: List of items to validate.

      validator_dicts: _HelperDicts object containing validator method
         information.

      manifest_tree: Tree containing nodes to validate.

      debug: Print tracing / debug messages when True

    Returns: N/A

    Raises:
      ManifestProcError: One or more validation errors found.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    errors = False
    for excludeme in to_exclude:
        attributes = excludeme.get_attr_dict()
        validator_ref = attributes["exclude"].strip()

        if (debug):
            print ("  Processing unexcluded nodes validated by " +
                   validator_ref + "()")
        nodepaths = space_parse(excludeme.get_value())

        # For every node in the tree do
        walker = manifest_tree.get_tree_walker()

        # Get an element and its attributes as a list of nodes
        # (TreeAccNodes)
        curr_list = manifest_tree.walk_tree(walker)
        while (curr_list is not None):

            # Cycle through all returned nodes.
            for node in curr_list:

                if (debug):
                    print "Checking current node: " + node.get_path()

                # Check through the list of nodepaths to be
                # inhibited.  Note if the path of the current
                # node is in the list.
                inhibit = False
                for raw_nodepath in nodepaths:
                    nodepath = raw_nodepath.strip()
                    if (debug):
                        print "%s vs %s" % (nodepath, node.get_path())
                    if (nodepath == node.get_path()):
                        inhibit = True
                        break

                if (not inhibit):
                    if (debug):
                        print "Not inbibited.  Checking node"
                    try:
                        if (not __validate_node(validator_ref,
                            validator_dicts, node, debug)):
                            errors = True
                    except StandardError, err:
                        print >> sys.stderr, ("Exception while validating " +
                                              "node " + node.get_path())
                        print >> sys.stderr, str(err)
                        errors = True

            curr_list = manifest_tree.walk_tree(walker)

    if errors:
        raise ManifestProcError, ("validate_exclude: One or more validation " +
                                  "errors found.")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def init_defval_tree(defval_xml):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Prepare the defaults / validation tree.  Must be called before any
        other method in this module.

    Validates the default / validation manifest against its schema, then
    reads it in, and creates and returns the tree (in-memory representation)
    used by other methods in this module.

    Args:
      defval_xml: Name of the Defaults and Content Validation XML spec.

    Returns:
      Tree of nodes (TreeAccNodes) that represents the defaults and
        validation requests specified in the
        default / validation manifest.

    Raises:
      ManifestProcError: Schema validation failed for default and content
        validation manifest.
      ManifestProcError: Error creating tree for default and content
        validation manifest.

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Validate XML file used for defaults and contents validation.
    try:
        schema_validate(DEFVAL_SCHEMA, defval_xml)
    except StandardError, err:
        print >> sys.stderr, ("init_defval_tree: Schema validation " +
                              "failed for default and content " +
                              "validation manifest:" + str(err))
        raise

    try:
        defval_tree = TreeAcc(defval_xml)
    except TreeAccError, err:
        raise ManifestProcError, ("init_defval_tree: " +
                                  "Error creating tree for default " +
                                  "and content validation manifest " +
                                  defval_xml + ":" + str(err))
    return defval_tree


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def schema_validate(schema_file, in_dc_manifest, out_dc_manifest=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Validate a DC-manifest against its schema.

    Args:
      schema_file: Schema to validate the manifest against.

      in_dc_manifest: Manifest to validate against the MANIFEST_SCHEMA.

      out_dc_manifest: Name of reformatted file of in_dc_manifest.

    Returns: N/A

    Raises:
      ManifestProcError: Schema validation failed for DC manifest

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    try:
        __validate_vs_schema(schema_file, in_dc_manifest, out_dc_manifest)
    except StandardError, err:
        print >> sys.stderr, str(err)
        raise ManifestProcError, ("schema_validate: Schema validation " +
                                  "failed for DC manifest " + in_dc_manifest)
