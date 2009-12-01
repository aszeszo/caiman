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

    # Defaults and content validation XML file, defining defaults and how
    # to validate the project manifest for symantics/content.
    DEFVAL_XML_SUFFIX = ".defval.xml"

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __init__(self, manifest, valfile_base=None, out_manifest=None,
                 verbose=False, keep_temp_files=False):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Constructor.  Validate and initialize all XML data for
            retrieval from an in-memory tree.

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
          manifest: Name of the project manifest file.  If it doesn't
            have a suffix, one will be appended.  Names of the
            schema and defaults/content-validation manifest files
            are keyed off the basename of this file (without the
            suffix).

        valfile_base: rootname (excluding suffix) of the defval
            manifest XML and manifest schema files.  defval-manifest
            will be called <valfile_base>.defval.xml and manifest
            schema will be called <valfile_base>.rng valfile_base
            may contain prepended directory structure.  If given as
            None, valfile_base will take <manifest> as its value.

          out_manifest: (optional): Name of the nicely-formatted output
            manifest file.  Defaults to None if not provided.

          verbose: (optional): When True, enables on-screen printout of
            defaults, content validation and schema validation.
            Defaults to False.

          keep_temp_files: (optional): When True, leaves the temporary
            file around after termination.  Default is False, to
            delete the temporary file.

        Raises: 
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

        self.socket_debug = False

        # Save verbose setting as other methods use it too.
        self.verbose = verbose

        # Strip the suffix from the manifest file name, to get the base
        # name used for temporary file and maybe for other files used
        # in procsessing the manifest.
        full_manifest_basename = manifest.replace(ManifestServ.XML_SUFFIX, "")

        # Initialize default for valfile_base, if necessary.
        if (valfile_base is None):
            valfile_base = full_manifest_basename

        # Schema and defval_manifest root names are taken from
        # valfile_base.
        schema = valfile_base + ManifestServ.SCHEMA_SUFFIX
        defval_manifest = (valfile_base + ManifestServ.DEFVAL_XML_SUFFIX)

        # Get process ID in string form, to use in file- and
        # socket-names.
        strpid = str(os.getpid())

        # Create a new string without any prepended directories
        # from before the basename.  This will be used in creation
        # of the temporary filename.
        manifest_basename = full_manifest_basename.rsplit("/")[-1]

        # This is name of temporary file, that includes defaults,
        # before reformatting.
        temp_manifest = ("/tmp/" + manifest_basename + "_temp_" + strpid +
                         ManifestServ.XML_SUFFIX)

        # Do this here in case cleanup() is called without
        # start_socket_server() having been called first.
        self.listen_sock_name = ("/tmp/ManifestServ." + strpid)
        self.listen_sock = None    # Filled in by start_server()
        self.server_run = False

        # Initalize and validate the defaults/content-validation tree.
        try:
            defval_tree = init_defval_tree(defval_manifest)
        except ManifestProcError, err:
            print >> sys.stderr, ("Error initializing " +
                                  "defaults/content-validation tree:")
            print >> sys.stderr, str(err)
            raise

        # Initialize the project manifest data tree.
        try:
            self.manifest_tree = TreeAcc(manifest)
        except TreeAccError, err:
            print >> sys.stderr, "Error instantiating manifest tree:"
            print >> sys.stderr, str(err)
            raise

        # Add defaults to the project manifest data tree.
        try:
            add_defaults(self.manifest_tree, defval_tree, verbose)
        except (KeyError, ManifestProcError), err:
            print >> sys.stderr, "Error adding defaults to manifest tree"
            print >> sys.stderr, str(err)

            # Create temp manifest for debugging
            if (keep_temp_files):
                self.__save_tree(temp_manifest)
            raise

        # Do semantic / content validation on the project manifest
        # data tree.
        try:
            validate_content(self.manifest_tree, defval_tree, verbose)
        except (KeyError, ManifestProcError), err:
            print >> sys.stderr, "Error validating manifest tree content:"
            print >> sys.stderr, str(err)

            # Create temp manifest for debugging
            if (keep_temp_files):
                self.__save_tree(temp_manifest)
            raise

        # Validate the project manifest data tree against its schema.
        # Save a nicely-formatted copy if out_manifest is specified.
        self.__save_tree(temp_manifest)

        # Pylint bug: See http://www.logilab.org/ticket/8764
        # pylint: disable-msg=C0321
        try:
            schema_validate(schema, temp_manifest, out_manifest)
        except ManifestProcError, err:
            print >> sys.stderr, ("Error validating " +
                                  "manifest against schema " + schema)
            print >> sys.stderr, str(err)
            raise

        # Check to delete the temporary file whether or not an
        # exception occurred.
        finally:
            if (not keep_temp_files):
                if (verbose):
                    print ("Removing temporary file: " + temp_manifest)
                os.unlink(temp_manifest)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def __save_tree(self, save_manifest):
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """ Save memory-resident XML tree to a file.

        Args:
          save_manifest: name of the file to save data to

        Returns: none

        Raises: none

        """
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        try:
            self.manifest_tree.save_tree(save_manifest)
        except (FileOpenError, FileSaveError), err:
            print >> sys.stderr, ("Error saving temporary manifest %s:" %
                                  save_manifest)
            print >> sys.stderr, str(err)


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
    def get_values(self, request, is_key=False):
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

        if (self.verbose):
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
                srvsock.send(results)

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
