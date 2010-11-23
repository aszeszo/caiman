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
#

# =============================================================================
# =============================================================================
"""
ManifestServ.py - XML data access interface module
"""
# =============================================================================
# =============================================================================

import errno
import sys
import thread
import os
import socket
import osol_install.SocketServProtocol as SocketServProtocol

from osol_install.DefValProc import add_defaults
from osol_install.DefValProc import init_defval_tree
from osol_install.DefValProc import schema_validate
from osol_install.DefValProc import validate_content
from osol_install.DefValProc import ManifestProcError
from osol_install.TreeAcc import TreeAcc
from osol_install.TreeAcc import TreeAccError
from osol_install.TreeAcc import FileOpenError
from osol_install.TreeAcc import FileSaveError
from osol_install.install_utils import space_parse

# =============================================================================
# Error handling.
# Declare new classes for errors thrown from this file's classes.
# =============================================================================

class ManifestServError(StandardError):
    """Base Exception for ManifestServ errors"""
    pass

# =============================================================================
class ManifestServ(object):
# =============================================================================
    """ Module with public programming interfaces for XML data
        initialization and access

    """
# =============================================================================

    # Project manifest has a name.
    # Append these suffixes to get the files keyed off the manifest name.

    # Project manifest XML file.
    XML_SUFFIX = ".xml"

    # Project manifest schema against which P.M. XML file is validated.
    SCHEMA_SUFFIX = ".rng"
    DTD_SCHEMA_SUFFIX = ".dtd"

    # Defaults and content validation XML file, defining defaults and how
    # to validate the project manifest for symantics/content.
    DEFVAL_XML_SUFFIX = ".defval.xml"

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, manifest_name, valfile_base=None,
                 out_manifest_name=None, verbose=False,
                 keep_temp_files=False, full_init=True,
                 dtd_schema=False):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor.  Initialize the in-memory data tree.  Take care
            of other initialization tasks if full_init = True.

        Validation and initialization consists of the following steps:
        - Initialize and validate defaults/content-validation tree.
        - Initialize the project data (manifest) tree.
        - Add defaults to the manifest tree.
        - Validate semantics/content of manifest tree.
        - Validate the manifest tree against the manifest schema.
        - Optionally save a nicely-formatted XML file containing all
            adjustments.  This is the output_manifest.  Name is of
            the format:
                "/tmp/<manifest_basename>_temp_<pid>

        Note: Socket server is not started from this method.

        Args:
          manifest_name: Name of the project manifest file.  If it
            doesn't have a suffix, one will be appended.  Default names
            of the schema and defaults/content-validation manifest
            files are keyed off the basename of this file (without
            the suffix).

          full_init: (optional): if True, the data is read into memory, and
            data processing (verification or default setting) is done.
            If False, no data processing is done.  Defaults to True.

          valfile_base: (optional): rootname (excluding suffix) of the
            defval manifest XML and manifest schema files.  defval-manifest
            will be called <valfile_base>.defval.xml and manifest schema
            will be called <valfile_base>.rng valfile_base may contain
            prepended directory structure.  If given as None,
            valfile_base will take <manifest> as its value.

          out_manifest_name: (optional): Name of the nicely-formatted
            output manifest file.  Defaults to None if not provided.

          verbose: (optional): When True, enables on-screen printout of
            defaults, content validation and schema validation.
            Defaults to False.

          keep_temp_files: (optional): When True, leaves the temporary
            file around after termination.  Default is False, to
            delete the temporary file.

          dtd_schema: (optional): Only relevant if full_init=True.
            When True, validate Manifest against DTD Schema file and
            skip set_detaults() and semantic_validate().
            Default is to validate against RelaxNG Schema file and
            perform set_detaults() and semantic_validate().

        Raises:
          - TreeAccError exceptions during initialization of the project
            manifest data tree.
          - Exceptions during initialization of the
            defaults/content-validation tree.
          - Exceptions during initialization of the project manifest
            data tree.
          - Exceptions during adding of defaults to the project
            manifest data tree.
          - Exceptions during semantic / content validation of the
            project manifest data tree.
          - Exceptions during schema validation of the project manifest
            data tree.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.defval_tree = None
        self.manifest_tree = None

        # Set up defaults for ancillary files.
        manifest_name = manifest_name.strip()
        if (manifest_name.endswith(ManifestServ.XML_SUFFIX)):

            # Strip the suffix from the manifest file name, to get the base
            # name used for temporary file and maybe for other files used
            # in procsessing the manifest.
            full_manifest_basename = \
                manifest_name.replace(ManifestServ.XML_SUFFIX, "")
        else:
            full_manifest_basename = manifest_name
            manifest_name += ManifestServ.XML_SUFFIX

        # Initialize the project manifest data tree.
        try:
            self.manifest_tree = TreeAcc(manifest_name)
        except TreeAccError:
            print >> sys.stderr, "Error instantiating manifest tree:"
            raise

        # Initialize default for valfile_base, if necessary.
        if (valfile_base is None):
            valfile_base = full_manifest_basename
        self.valfile_base = valfile_base

        # Schema and defval_manifest root names are taken from
        # valfile_base.
        if dtd_schema:
            self.schema_name = valfile_base + ManifestServ.DTD_SCHEMA_SUFFIX
        else:
            self.schema_name = valfile_base + ManifestServ.SCHEMA_SUFFIX
            self.defval_manifest_name = valfile_base + \
                ManifestServ.DEFVAL_XML_SUFFIX

        # Create a new string without any prepended directories
        # from before the basename.  This will be used in creation
        # of the temporary filename.
        manifest_basename = full_manifest_basename.rsplit("/")[-1]

        # Get process ID in string form, to use in file- and socket-names.
        self.strpid = str(os.getpid())

        # This is name of temporary file, that includes defaults,
        # before reformatting.
        self.temp_manifest_name = ("/tmp/" + manifest_basename + "_temp_" +
                                   self.strpid + ManifestServ.XML_SUFFIX)

        self.out_manifest_name = out_manifest_name
        self.verbose = verbose
        self.keep_temp_files = keep_temp_files
        self.dtd_schema = dtd_schema

        # Do this here in case cleanup() is called without
        # start_socket_server() having been called first.
        self.listen_sock_name = ("/tmp/ManifestServ." + self.strpid)
        self.listen_sock = None    # Filled in by start_server()
        self.server_run = False
        self.socket_debug = False

        # Preprocess if full_init is specified.
        if (full_init):
            if not dtd_schema:
                self.set_defaults(self.defval_manifest_name,
                                  self.temp_manifest_name, self.verbose,
                                  self.keep_temp_files)

            self.schema_validate(self.schema_name, self.temp_manifest_name,
                                 self.out_manifest_name, self.verbose,
                                 self.keep_temp_files, self.dtd_schema)

            if not dtd_schema:
                self.semantic_validate(self.defval_manifest_name,
                                       self.temp_manifest_name, self.verbose,
                                       self.keep_temp_files)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def schema_validate(self, schema_name=None, temp_manifest_name=None,
                        out_manifest_name=None, verbose=None,
                        keep_temp_files=None, dtd_schema=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Validate manifest against the given schema

        Args:
          schema_name: (optional): Filename of the schema to validate
            against.  If not supplied here, the default name of
            <manifest_name>.rng is used.

          temp_manifest_name: (optional): Name of the (temporary) manifest
            file to validate.  If not supplied here, the default name of
            /tmp/<manifest_name>_temp<PID>.xml is used.

          out_manifest_name: (optional): Filename to write out a
            nicely-formatted manifest.  If not supplied here, the name
            specified in the constructor is used.

          verbose: boolean: True = extra messages.  If not supplied here,
            the value specified in the constructor is used.

          keep_temp_files: boolean: True = Do not delete the temp_manifest.
            If the value is not supplied here, the value specified in the
            constructor is used.

          dtd_schema: boolean: True = validate against DTD Schema file
            (and perform loading of attribute defaults from DTD).
            False = validate against RelaxNG (and skip loading attribute
            defaults).  If the value is not supplied here, the value
            specified in the constructor is used.
        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Validate the project manifest data tree against its schema.
        # Save a nicely-formatted copy if out_manifest is specified.

        if (schema_name is None):
            schema_name = self.schema_name
        if (temp_manifest_name is None):
            temp_manifest_name = self.temp_manifest_name
        if (out_manifest_name is None):
            out_manifest_name = self.out_manifest_name
        if (verbose is None):
            verbose = self.verbose
        if (keep_temp_files is None):
            keep_temp_files = self.keep_temp_files
        if (dtd_schema is None):
            dtd_schema = self.dtd_schema

        delete_out_manifest = False
        # In order to set attribute defaults (DTD only), there MUST be
        # an output file from schema_validate().  So, if one wasn't
        # specified, make up a temporary one (and delete it later).
        if (dtd_schema == True) and (out_manifest_name is None):
            out_manifest_name = temp_manifest_name.replace(
                                    ManifestServ.XML_SUFFIX,
                                    "_out" + ManifestServ.XML_SUFFIX)
            delete_out_manifest = True

        # Pylint bug: See http://www.logilab.org/ticket/8764
        # pylint: disable-msg=C0321
        try:
            self.__save_tree(temp_manifest_name)
            schema_validate(schema_name, temp_manifest_name, out_manifest_name,
                            dtd_schema=dtd_schema)

            # For DTD Manifests, setting defaults entails taking the
            # validation output file (out_manifest_name) and
            # repopulating self.manifest_tree using this file.
            if dtd_schema:
                try:
                    self.manifest_tree = TreeAcc(out_manifest_name)
                except TreeAccError:
                    print >> sys.stderr, "Error re-instantiating manifest tree:"
                    raise

        except ManifestProcError, err:
            print >> sys.stderr, ("Error validating " +
                                  "manifest against schema " + schema_name)
            print >> sys.stderr, str(err)
            raise

        # Check to delete the temporary file(s) whether or not an
        # exception occurred.
        finally:
            if (not keep_temp_files):
                if (verbose):
                    print ("Removing temporary file: " + temp_manifest_name)
                os.unlink(temp_manifest_name)

                if delete_out_manifest:
                    if verbose:
                        print ("Removing temporary file: " + out_manifest_name)
                    os.unlink(out_manifest_name)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __load_defval_tree__(self, defval_manifest_name):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Initialize and validate the defaults/content validation tree
        if not already done.

        Args:
          defval_manifest_name: Name of the defaults/content-validation
            (defval) manifest file.

        Returns: None

        Raises:
          ManifestProcError: Error initializing defaults/content-validation
            tree.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (self.defval_tree is None):

            # Initialize and validate the defaults/content-validation tree.
            try:
                self.defval_tree = init_defval_tree(defval_manifest_name)
            except ManifestProcError, err:
                print >> sys.stderr, ("Error initializing defaults/" +
                                     "content-validation tree")
                print >> sys.stderr, str(err)
                raise


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_defaults(self, defval_manifest_name=None,
                     temp_manifest_name=None, verbose=None,
                     keep_temp_files=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Set defaults into the (project) data tree.  Defaults defined by
        the defval_manifest.

        Args:
          defval_manifest_name: Filename of the defaults/content-validation
            (defval) manifest.  Used only if defval_manifest is not already
            opened.  If not supplied here, the default name of
            <manifest_name>.defval.xml is used.  No verification of consistency
            between this defval_manifest_name and a defval_manifest file which
            is already opened.

          temp_manifest_name: Name of the (temporary) manifest file.  Can
            be used to verify setting of defaults.  If not supplied here, the
            default name of /tmp/<manifest_name>_temp<PID>.xml is used.

          keep_temp_files: boolean: True = Do not delete the temp_manifest.
            If the value is not supplied here, the value specified in the
            constructor is used.

          verbose: boolean: True = extra messages.  If the value is not
            supplied here, the value specified in the constructor is used.

        Returns: None

        Raises:
          ManifestServError: If self.dtd_schema is True
          KeyError: As raised from add_defaults()
          ManifestProcError: As raised from add_defaults()

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if (self.dtd_schema):
            raise ManifestServError, \
			    ("set_defaults() called for DTD manifest")

        if (defval_manifest_name is None):
            defval_manifest_name = self.defval_manifest_name
        if (temp_manifest_name is None):
            temp_manifest_name = self.temp_manifest_name
        if (verbose is None):
            verbose = self.verbose
        if (keep_temp_files is None):
            keep_temp_files = self.keep_temp_files

        # Stores self.defval_tree on success
        self.__load_defval_tree__(defval_manifest_name)

        # Add defaults to the project manifest data tree.
        try:
            add_defaults(self.manifest_tree, self.defval_tree, verbose)
        except (KeyError, ManifestProcError), err:
            print >> sys.stderr, "Error adding defaults to manifest tree"
            print >> sys.stderr, str(err)

            # Create temp manifest for debugging
            if (keep_temp_files):
                self.__save_tree(temp_manifest_name)
            raise


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def semantic_validate(self, defval_manifest_name=None,
                          temp_manifest_name=None, verbose=None,
                          keep_temp_files=None):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Perform semantic validation of the (project) data tree.
        Validation tasks defined by the defval_manifest.

        Args:
          defval_manifest_name: Filename of the defaults/content-validation
            (defval) manifest.  Used only if defval_manifest is not already
            opened.  If not supplied here, the default name of
            <manifest_name>.defval.xml is used.  No verification of consistency
            between this defval_manifest_name and a defval_manifest file which
            is already opened.

          temp_manifest_name: Name of the (temporary) manifest file.  Can
            be used to double-check validation.  If not supplied here, the
            default name of /tmp/<manifest_name>_temp<PID>.xml is used.

          keep_temp_files: boolean: True = Do not delete the temp_manifest.
           If the value is not supplied here, the value specified in the
            constructor is used.

          verbose: boolean: True = extra messages.  If not supplied here,
            the value specified in the constructor is used.

        Returns: None

        Raises:
          ManifestServError: If self.dtd_schema is True
          KeyError: As raised from add_defaults()
          ManifestProcError: As raised from add_defaults()

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if (self.dtd_schema):
            raise ManifestServError, \
			    ("semantic_validate() called for DTD manifest")

        if (defval_manifest_name is None):
            defval_manifest_name = self.defval_manifest_name
        if (temp_manifest_name is None):
            temp_manifest_name = self.temp_manifest_name
        if (verbose is None):
            verbose = self.verbose
        if (keep_temp_files is None):
            keep_temp_files = self.keep_temp_files

        # Stores self.defval_tree on success
        self.__load_defval_tree__(defval_manifest_name)

        # Do semantic / content validation on the project manifest
        # data tree.
        try:
            validate_content(self.manifest_tree, self.defval_tree, verbose)
        except (KeyError, ManifestProcError), err:
            print >> sys.stderr, "Error validating manifest tree content:"
            print >> sys.stderr, str(err)

            # Create temp manifest for debugging
            if (keep_temp_files):
                self.__save_tree(temp_manifest_name)
            raise


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __save_tree(self, save_manifest):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Save memory-resident XML tree to a file.

        Args:
          save_manifest: name of the file to save data to

        Returns: none

        Raises:
          FileOpenError: Could not open save_manifest file
          FileSaveError: Could not save data to save_manifest file

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        try:
            self.manifest_tree.save_tree(save_manifest)
        except (FileOpenError, FileSaveError), err:
            print >> sys.stderr, ("Error saving temporary manifest %s:" %
                                  save_manifest)
            print >> sys.stderr, str(err)
            raise


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def start_socket_server(self, debug=False):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Start socket server.

        The socket server serves up the same data as get_values()
        returns, as string values, through an AF-UNIX socket.  Client
        and server must be on the same system.

        This method returns after starting a thread which runs the
        server in the background.

        Args:
          debug: Turn on debugging output when True

        Returns: None

        Raises: ManifestServError: Error starting socket server

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.socket_debug = debug
        self.server_run = True
        try:
            thread.start_new_thread(self.__socket_server_main, ())
        except thread.error, err:
            print >> sys.stderr, "Error starting socket server"
            raise ManifestServError, ("Error starting socket server: %s" %
                                      (str(err)))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def stop_socket_server(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Shut down the socket server.

        There is no way to directly kill the server.  Instead, clear
        the run flag which is monitored by the server
        (__socket_server_main()), then connect to the server to get it's
        socket accept() method to return.  The server will then see the
        flag is clear, and will voluntarily exit.

        Args: None

        Returns: None

        Raises: None, even if the server isn't running.

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if (not self.server_run):
            return

        try:
            # Clear run flag, then get the server to drop out of
            # waiting for a new client in accept(), so it can check
            # the flag.
            self.server_run = False
            client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client_sock.connect(self.listen_sock_name)
        except OSError:
            pass

        try:
            if (self.listen_sock is not None):
                self.listen_sock.close()
        except OSError:
            pass

        try:
            if (self.listen_sock_name is not None):
                os.unlink(self.listen_sock_name)
        except OSError:
            pass
        

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_values(self, request, is_key=False, verbose=False):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Method for the project's main process (which invoked this
            module) to retrieve XML data directly (no sockets).

        Args:
           request: Path in the main XML data tree to nodes with data
            to retrieve.  More than one node may match a nodepath.

          is_key: boolean: if True, the request is interpreted as a key
            in the key_value_pairs section of the manifest.  In this
            case, the proper nodepath will be generated from the
            request and submitted.  If false, the request is
            submitted for searching as provided.

           verbose: boolean: if True, print messages

        Returns:
           list of string values from nodes which match the nodepath

        Raises:
          ParserError: Errors generated while parsing the nodepath

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        strlist = []

        # Convert keys to proper requests.
        if (is_key):
            request = SocketServProtocol.KEY_PATH % (request)

        nodelist = self.manifest_tree.find_node(request.strip())
        for node in nodelist:
            value = node.get_value()
            if (value == ""):
                strlist.append("")
            else:
                strlist.extend(space_parse(value))

        if (verbose):
            print "get_values: request = \"" + request + "\""
            print (("   %d results found: " % len(strlist)) +
                   str(strlist))
        return strlist


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def get_sockname(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Return the name of the socket.

        The name returned may be passed to client programs which will
        create sockets to communicate with this server to retrieve data.

        Args: None

        Returns:
          The string name of the AF-UNIX socket to communiate with.
            AF-UNIX implies that both the client and server must be
            on the same system.

        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        return self.listen_sock_name


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __process_srvr_requests(self, srvsock):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method used to process remote (socket) request.
    
        Utilize the srvsock socket to communicate with a client using
        the protocol set forth in the SocketServProtocol.py module.
        Accepts a request, and then answers it.  Can accept and answer
        multiple requests before terminating, all per the protocol.
    
        Please see the SocketServProtocol module for public definitions
        for protocol, and their explanations.
    
        Args:
          srvsock: socket to communicate with the client
    
        Returns: None
    
        Raises:
          socket.error: ManifestServ Prerequest Protocol Error:key
          socket.error: ManifestServ Prerequest Protocol Error:size
          socket.error: ManifestServ Protocol Error
          Other exceptions which can be raised by socket send() and recv()
    
        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Receive a new request.
        pre_request = srvsock.recv(SocketServProtocol.PRE_REQ_SIZE)

        # Loop until client terminated (unexpectedly or per protocol)
        while (pre_request and
            (pre_request[0] != SocketServProtocol.TERM_LINK)):

            if (pre_request[0] == '0'):
                is_key = False
            elif (pre_request[0] == '1'):
                is_key = True
            else:
                raise socket.error, (errno.EPROTO, "ManifestServ Prerequest " +
                                     "Protocol Error:key")
            try:
                request_size = int(pre_request[2:SocketServProtocol.
                                   PRE_REQ_SIZE])
            except ValueError:
                raise socket.error, (errno.EPROTO, "ManifestServ Prerequest " +
                                     "Protocol Error:size")
            if (self.socket_debug):
                print ("Prerequest received: key is " + str(is_key) +
                       " and size = " + str(request_size))

            # Send the pre_request ack and wait for the request
            srvsock.send(SocketServProtocol.PRE_REQ_ACK)
            request = srvsock.recv(request_size)

            # Query the request
            if (self.socket_debug):
                print "Received Request: " + request.strip()

            try:
                values = self.get_values(request.strip(), is_key)
            except TreeAccError, err:

                print ("Error parsing remote request \"" + request.strip() +
                       "\": " + str(err))

                # Treat bad search strings like good ones with no results.
                srvsock.send("0,0")

                values = []
            else:

                # Send the count and size.  In the case of found
                # results, calculate the results string first to get
                # the size.
                if not values:    # No results found
                    srvsock.send("0,0")
                else:
                    results = ""
                    for value in values:

                        # Handle "empty string" results.
                        if (value == ""):
                            value = SocketServProtocol.EMPTY_STR

                        # Concatenate results into single string
                        results += (value + SocketServProtocol.STRING_SEP)

                    # Protocol results terminator.
                    results += SocketServProtocol.REQ_COMPLETE

                    # Send results count and size.
                    srvsock.send(str(len(values)) + "," + str(len(results)))

            # Wait for the count/size acknowledge from the client.
            request = srvsock.recv(1)
            if ((not request) or
                (request[0] != SocketServProtocol.RECV_PARAMS_RECVD)):
                raise socket.error, (errno.EPROTO,
                                     "ManifestServ Protocol Error")

            # Send the results.
            if values:
                srvsock.sendall(results)

            # Receive a new request.
            pre_request = srvsock.recv(SocketServProtocol.PRE_REQ_SIZE)

        if (self.socket_debug):
            print "termination requested"


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __serve(self, srvsock):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Private method invoked by thread used to process client requests
    
        Catches all socket exceptions so server keeps running to
        process other clients even if a particular client had a problem.
    
        Args:
          srvsock: socket used to process a set of client requests.
              Note that this socket is assumed already opened.
    
        Returns: None
    
        Raises: None

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (self.socket_debug):
            print "Starting new serve thread"

        # Process client requests.  Eat all exceptions, some of
        # which can come in somewhat expectedly (as when a
        # client terminates).
        # Pylint bug: See http://www.logilab.org/ticket/8764
        # pylint: disable-msg=C0321
        try:
            self.__process_srvr_requests(srvsock)
        except socket.error, err:
            if (err.args[0] != errno.EPIPE):
                print >> sys.stderr, "Exception in socket serve:"
                print >> sys.stderr, str(err)
            elif (self.socket_debug):
                print "Socket closed"

        # Always close the socket when done with it.
        finally:
            srvsock.close()

        if (self.socket_debug):
            print "Terminating client-specific server thread"


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __socket_server_main(self):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Initialize and start the socket server.  Wait for clients.
    
        Args: None
    
        Returns: None
    
        Raises: None
            (However, it reports errors when setting up socket.)          
    
        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # Initialize server socket.
        try:
            self.listen_sock = socket.socket(socket.AF_UNIX,
                                             socket.SOCK_STREAM)
        except socket.error, err:
            print >> sys.stderr, "Error creating listener socket:"
            print >> sys.stderr, str(err)
            return

        try:
            self.listen_sock.bind(self.listen_sock_name)
        except socket.error, err:
            print >> sys.stderr, "Error binding receptor socket:"
            print >> sys.stderr, str(err)
            return

        try:
            self.listen_sock.listen(5)
        except socket.error, err:
            print >> sys.stderr, "Error listening on receptor socket:"
            print >> sys.stderr, str(err)
            return

        # Now wait for clients.  Start a new thread for each client.
        while (self.server_run):
            try:
                srvsock, addr = self.listen_sock.accept()
                del addr
            except KeyboardInterrupt:
                break
            except socket.error, err:
                print >> sys.stderr, "Error accepting new connection"
                print >> sys.stderr, str(err)
                continue

            # stop_socket_server() clears this flag when it's time to stop.
            if (not self.server_run):
                if (self.socket_debug):
                    print "Server terminating"
                break
            try:
                thread.start_new_thread(self.__serve, (srvsock, ))
            except thread.error, err:
                print >> sys.stderr, "Error starting new connection thread:"
                print >> sys.stderr, str(err)
