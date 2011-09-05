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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
'''Transfer SVR4 checkpoint. Sub-class of the checkpoint class'''

import abc
import errno
import httplib
import os
import re
import urllib2

from osol_install.install_utils import dir_size
from solaris_install import Popen
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.engine import InstallEngine
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Dir
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import SVR4Spec
from solaris_install.transfer.info import ACTION, CONTENTS, SVR4_ARGS
from solaris_install.transfer.prog import ProgressMon


class AbstractSVR4(AbstractCheckpoint):
    '''Subclass for transfer SVR4 checkpoint

    self.src can be either a local directory containing SVR4 package
    subdirectories, or it can be datastream file.  Datastream files can be
    local (in the form of /dir/file or the URL form of
    file:///blah/datastream.d) or remote (in the URL form of
    http://blah/datastream.d).  The local URL format is not efficient, but it
    works.  In all cases, self.src can house multiple packages.

    self.dst is a filesystem (or directory during testing).
    '''

    __metaclass__ = abc.ABCMeta

    # For supporting testing.
    ROOT = os.environ.get("ROOT", "")

    # Constants used by svr4 transfer actions
    TMPDIR = "/system/volatile/"
    ADMIN_FILE_DIR = ROOT + TMPDIR
    ADMIN_FILE = ADMIN_FILE_DIR + "/svr4_admin"
    BYTES_PER_KB = 1024
    DEFAULT_PKGADD_ARGS = "-n -a %s -d %s -R %s"
    DEFAULT_PKGRM_ARGS = "-n -a %s -R %s"
    DEFAULT_PROG_EST = 10
    DEFAULT_SIZE = 1024
    PKGADD = "/usr/sbin/pkgadd"
    PKGRM = "/usr/sbin/pkgrm"
    SVR4_DS_HDR_START = "# PaCkAgE DaTaStReAm"
    SVR4_DS_HDR_END = "# end of header"

    # Used to split a URL into its components.
    URL_RE = re.compile("(\w*)://([^/]*)((/.*)*)")

    # Constants related to types of package sources.
    LOCAL_DIR_TYPE = "Local Directory"
    LOCAL_DSTR_TYPE = "Local Datastream"
    REMOTE_DSTR_TYPE = "Remote Datastream"

    # Initial contents of admin file.
    ADMIN_DICT = {
        "mail": "",
        "instance": "quit",
        "partial": "nocheck",
        "runlevel": "nocheck",
        "idepend": "nocheck",
        "rdepend": "nocheck",
        "space": "quit",
        "setuid": "nocheck",
        "conflict": "quit",
        "action": "nocheck",
        "basedir": ""
    }

    def __init__(self, name):
        super(AbstractSVR4, self).__init__(name)

        # Attributes per transfer action
        self.datastream = None
        self.src = None
        self.dst = None
        self.doc = None

        # Used to set for dry run
        self.dry_run = False

        # Use for progress reporting
        self.total_size = -1
        self.give_progress = False
        self.svr4_process = None
        self._cancel_event = False

        # Handle for the progress monitor
        self.pmon = None
        self._transfer_list = []
        self.input_parsed = False

    def get_src_type(self, in_file_name):
        '''Returns type of package source

        LOCAL_DIR_TYPE :   # /path/to/parent_of_pkg_subdirs
        LOCAL_DSTR_TYPE :  # /path/to/datastream
        REMOTE_DSTR_TYPE : # http://url_to_datastream

        Some assumptions are made.  For example, local datastream assumes that
        any file which is local and not a directory is a datastream.  If this
        is not correct, pkgadd will fail later, but that's OK.

        Assumes datastream if file is remote, or is local and not a directory.

        Rejects a non-datastream remote request as pkgadd doesn't support it.

        local datastr   url*  Possible  Notes
              (vs dir)
        0     0         0     0         Remote dir doesn't make sense
        0     0         1     0         Remote dir doesn't make sense
        0     1         0     0         /net/... Treat as local**
        0     1         1     1         -> remote implies datastream and url
        1     0         0     1         -> local directory
        1     0         1     0         Dir URL doesn't make sense
        1     1         0     1         -> local datastream file
        1     1         1     0         file:// not supported by pkgadd

        * starts with http:// or similar, vs a file path /path/to/file
        ** Not worth the effort to treat them as remote.
        '''

        if os.access(in_file_name, os.R_OK):
            if os.path.isdir(in_file_name):
                src_type = AbstractSVR4.LOCAL_DIR_TYPE
            else:
                src_type = AbstractSVR4.LOCAL_DSTR_TYPE
        else:
            try:
                fd = urllib2.urlopen(in_file_name)
                fd.close()
            except (ValueError, urllib2.HTTPError):
                self.logger.error(" Source %s doesn't exist "
                                 "or is unreadable" % in_file_name)
                raise

            # Note: Treat all URLs as remote, since pkgadd doesn't support
            # file:/// local URLs.
            src_type = AbstractSVR4.REMOTE_DSTR_TYPE

        self.logger.debug("get_src_type returns %s" % src_type)
        return src_type

    def get_size_via_http(self, url):
        ''' Returns the size of an http or https URL file in Kb'''

        # Split out the host from the rest of the url
        re_match = AbstractSVR4.URL_RE.match(url)
        if re_match is None:
            raise IOError(errno.EINVAL, "Malformed URL specified: %s" % url)
        protocol = re_match.group(1).lower()

        # Make the query.
        if protocol == "http":
            conn = httplib.HTTPConnection(re_match.group(2))
        elif protocol == "https":
            conn = httplib.HTTPSConnection(re_match.group(2))
        else:
            raise IOError(errno.EINVAL, "Non-http/https URL specified: %s" %
                          url)
        try:
            conn.request("HEAD", re_match.group(3))
            response = conn.getresponse()
            size = response.getheader("content-length")
            try:
                isize = int(size) / AbstractSVR4.BYTES_PER_KB
            except ValueError:
                self.logger.error("Invalid size returned for %s" % url)
                raise
        finally:
            conn.close()
        return isize

    def ds_pkg_size_and_verify(self, ds_name, pkg_list):
        '''Verifies datastream URL and contents, returns size of desired pkgs.

        ds_name is name of the datastream file.
        Verifies datastream header.
        Checks that all packages in pkg_list are contained in datastream.
        Returns combined size in Kb of desired packages.
        '''
        total_size = 0

        ds_fd = open(ds_name, "r")

        # Check the header.  Read package sizes.  Create dict of pkgs and sizes
        line = ds_fd.readline().strip()
        if line != AbstractSVR4.SVR4_DS_HDR_START:
            raise ValueError("%s is not an SVR4 datastream file" % ds_name)
        # Read the header, getting the size of the packages contained.
        # Create a dict of packages and sizes.
        line = ds_fd.readline().strip()
        pkg_dict = dict()
        while line != AbstractSVR4.SVR4_DS_HDR_END:
            try:
                (pkg_name, parts, size) = line.split(" ", 2)
                # Size in datastream is in 512b blocks.  Divide by 2 to get Kb.
                pkg_dict[pkg_name] = ((int(size) * int(parts)) + 1) / 2
            except ValueError:
                self.logger.error("Invalid header found in datastream %s" %
                                 ds_name)
                ds_fd.close()
                raise
            line = ds_fd.readline().strip()

        # Check that all desired pkgs are in the datastream.
        # Check all before failing, so can dump them all out.
        # If pkg is present, add its size.
        bad_pkg_names = list()
        for pkg_name in pkg_list:
            if pkg_name not in pkg_dict:
                bad_pkg_names.append(pkg_name)
            else:
                if not bad_pkg_names:
                    total_size += pkg_dict[pkg_name]
                    self.logger.debug("Found SVR4 pkg to "
                                     "install: %s, size: %sKb" %
                                     (pkg_name, pkg_dict[pkg_name]))
        ds_fd.close()

        # Dump the wad of missing package names.
        if bad_pkg_names:
            raise ValueError("Datastream file %s does not contain "
                             "the following SVR4 packages: %s" %
                             (ds_name, ", ".join(bad_pkg_names)))
        return total_size

    def nonds_pkg_size_and_verify(self, parentdir, pkg_list):
        '''Verifies local packages in form of directory tree.  Checks size.

        Accommodates several package trees under a common parent.

        Checks that all packages in pkg_list are contained under parent dir.
        Returns combined size in Kb of desired packages.
        '''

        # Parent dir must exist and be a directory.
        if not os.path.isdir(parentdir):
            raise ValueError("%s is not a directory" % parentdir)

        total_size = 0

        # Check for subdirs of names in the pkg_list.  Verify that each has a
        # pkginfo and pkgmap file, to know they are proper SVR4 package trees.
        bad_pkg_names = list()
        for pkg in pkg_list:
            # if subdir is missing pkginfo or pkgmap: then err out.
            pkgroot = os.path.join(parentdir, pkg)
            if (not os.path.exists(os.path.join(pkgroot, "pkginfo")) or
                not os.path.exists(os.path.join(pkgroot, "pkgmap"))):
                bad_pkg_names.append(pkg)

            # Continue to get sizes only if no bad packages have been found.
            # Use du on a tree to get the package size.
            # Add size to cumulative total.
            elif not bad_pkg_names:
                pkg_size = dir_size(pkgroot) / AbstractSVR4.BYTES_PER_KB
                self.logger.debug("Found SVR4 pkg to install: %s, size: %sKb" %
                                 (pkgroot, pkg_size))
                total_size += pkg_size

        # Dump the wad of missing package names.
        if bad_pkg_names:
            raise ValueError("The following packages under parent "
                             "%s are missing or invalid: %s" %
                             (parentdir, ", ".join(bad_pkg_names)))
        return total_size

    def get_progress_estimate(self):
        '''Returns an estimate of the time this checkpoint will take'''

        # Initialize self.total_size, among other things.
        self._parse_input_once()

        progress_estimate = \
            int((float(self.total_size) / AbstractSVR4.DEFAULT_SIZE) * \
                AbstractSVR4.DEFAULT_PROG_EST)
        if progress_estimate <= 0:
            progress_estimate = 1
        self.give_progress = True
        return progress_estimate

    def execute(self, dry_run=False):
        '''Execute method for the SVR4 checkpoint module. Will read the
           input parameters and perform the specified transfer.
        '''
        self.logger.info("=== Executing %s Checkpoint ===" % self.name)
        if self.give_progress:
            self.logger.report_progress("Beginning SVR4 transfer", 0)
        self.dry_run = dry_run

        try:
            # Read DOC parameters and put into the local attributes.
            self._parse_input_once()

            # Generate the admin file.  No proxy entry is made as it is
            # expected that http_proxy will be set in the enviroment.
            self.generate_admin_file(AbstractSVR4.ADMIN_FILE)

            # Check to see if a cancel event has been requested.
            self.check_cancel_event()
            # Finally, actually perform the SVR4 transfer.
            self._transfer()
        finally:
            self._cleanup()

    def _parse_input_once(self):
        '''Insures _parse_input() and _validate_input() are called only once

        Note: This method assumes all calls to it are made by the same thread.
        '''
        if not self.input_parsed:
            self._parse_input()
            self._validate_input()
            self.input_parsed = True

    @staticmethod
    def generate_admin_file(filename):
        '''Generate the admin file from the ADMIN_DICT'''
        with open(filename, "w") as fd:
            for (key, value) in AbstractSVR4.ADMIN_DICT.iteritems():
                fd.write(key + "=" + value + "\n")

    @abc.abstractmethod
    def _parse_input(self):
        '''This method is required to be implemented by all subclasses'''
        raise NotImplementedError

    def cancel(self):
        '''Cancel the transfer in progress'''
        self._cancel_event = True
        if self.svr4_process:
            self.svr4_process.kill()

    def check_cancel_event(self):
        '''Check the _cancel_event attribute to see if a cancel event  has been
           requested. If it has, cleanup what has been done already
        '''
        if self._cancel_event:
            self._cleanup()

    def _cleanup(self):
        '''Method to perform any necessary cleanup needed.'''
        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None

        if os.path.exists(AbstractSVR4.ADMIN_FILE):
            os.unlink(AbstractSVR4.ADMIN_FILE)

    def _transfer(self):
        '''Method to transfer from the source to the destination'''
        if self.give_progress:
            # Start up the ProgressMon to report progress
            # while the actual transfer is taking place.
            self.pmon = ProgressMon(logger=self.logger)
            # Note: startmonitor assumes there is another thread creating a
            # file system.  If this is not the case (as may be when testing
            # this module in abnormal conditions), startmonitor will hang.
            # Just create the self.dst as a directory in this case.
            self.pmon.startmonitor(self.dst, self.total_size, 0, 100)

        # Perform the transfer specific operations.

        try:
            for trans_val in self._transfer_list:

                # Get the arguments for the transfer process
                arglist = trans_val.get(SVR4_ARGS).split(' ')

                # Parse the components to determine the transfer action
                if trans_val.get(ACTION) == 'install':
                    self.check_cancel_event()
                    self.logger.info("Installing SVR4 packages")
                    cmd = [AbstractSVR4.PKGADD] + arglist + \
                        trans_val.get(CONTENTS)

                elif trans_val.get(ACTION) == 'uninstall':
                    self.check_cancel_event()
                    self.logger.info("Uninstalling SVR4 packages")
                    cmd = [AbstractSVR4.PKGRM] + arglist + \
                        trans_val.get(CONTENTS)

                else:
                    self.logger.warning("Transfer action, %s, is not valid" %
                                     trans_val.get(ACTION))
                    self.check_cancel_event()
                    continue

                if self.dry_run:
                    self.logger.debug("Would execute the following transfer "
                                     "command: %s" % cmd)
                else:
                    self.logger.debug("Executing the following transfer "
                                     "command: %s" % cmd)
                    self.check_cancel_event()
                    pkg_proc = Popen(cmd, shell=False,
                                     stdout=Popen.PIPE,
                                     stderr=Popen.STDOUT)
                    while 1:
                        self.check_cancel_event()
                        pkgoutput = pkg_proc.stdout.readline()
                        if not pkgoutput:
                            retcode = pkg_proc.poll()
                            if retcode != 0:
                                self.svr4_process = None
                                raise OSError(retcode,
                                              "SVR4 transfer error while "
                                              "adding packages")
                            break
                        pkgoutput = pkgoutput[:-1]
                        if not pkgoutput.strip():
                            continue
                        self.logger.debug("%s", pkgoutput)
                    self.svr4_process = None

        finally:
            if self.pmon:
                self.pmon.done = True
                self.pmon.wait()
                self.pmon = None

    def _validate_input(self):
        '''Check the required input parameters and verify that
           they are set appropriately.
        '''
        self.logger.debug("Validating SVR4 input")

        # destination is a required parameter
        if self.dst is None:
            raise ValueError("SVR4 destination must be specified")

        # source is a required parameter
        if not self.src:
            raise ValueError("SVR4 source must be specified")

        # Check for required attributes
        # Args are required when the transfer action is install
        # Packages are required for both install and uninstall actions
        if not self._transfer_list:
            self.logger.warning("No transfers have been specified")

        for trans_val in self._transfer_list:
            if trans_val.get(ACTION) != "install" and \
               trans_val.get(ACTION) != "uninstall":
                raise ValueError("Transfer action \"%s\" is not a"
                                 "valid SVR4 action" % trans_val.get(ACTION))

            if not trans_val.get(SVR4_ARGS):
                raise ValueError("SVR4 args must be specified")

            if not trans_val.get(CONTENTS):
                raise ValueError("SVR4 packages must be specified")


class TransferSVR4(AbstractSVR4):
    '''Transfer subclass uses checkpoint interface. Takes data from the DOC

    Relevant manifest fields look like this:

    <software type="SVR4">
      <source>
        <publisher>
          <origin name="/path/to/parentdir"/>
        </publisher>
      </source>
      <software_data action="install">
        <name>SUNWpkg1</name>
        <name>SUNWpkg2</name>
      </software_data>
    </software>

    Origin name can also be a datastream file, in the form of:
         <origin name="/path/to/datastream_file.d"/>
         <origin name="http://host/path/to/datastream_file.d"/>
    '''

    def __init__(self, name):
        super(TransferSVR4, self).__init__(name)

        # Holds the list of transfer dictionaries
        self._transfer_list = []

        # Get the reference to the data object cache
        self.doc = InstallEngine.get_instance().data_object_cache

        # Get the checkpoint info from the DOC
        self.soft_list = self.doc.get_descendants(name=self.name,
                                                  class_type=Software)

        # Check that the soft_list only has one entry
        if len(self.soft_list) != 1:
            raise ValueError("Only one value for Software node must be "
                             "specified with name " + self.name)

    def _parse_input(self):
        '''Method to read the parameters from the data object cache and
           place them into the local lists.
        '''
        # Get a reference to the data object cache
        self.doc = InstallEngine.get_instance().data_object_cache

        soft_node = self.soft_list[0]

        # Get the destination info
        dst_list = soft_node.get_children(Destination.DESTINATION_LABEL,
                                          Destination, not_found_is_err=True)
        self.dst = dst_list[0].get_children(Dir.DIR_LABEL, Dir,
                                            not_found_is_err=True)[0].dir_path
        self.dst = self.doc.str_replace_paths_refs(self.dst)

        if len(dst_list) > 1:
            raise ValueError("Invalid to specify more than one destination")

        # Get the source info
        src_list = soft_node.get_children(Source.SOURCE_LABEL, Source,
                                          not_found_is_err=True)

        if len(src_list) > 1:
            raise ValueError("Invalid to specify more than one source")

        pub = src_list[0].get_children(Publisher.PUBLISHER_LABEL, Publisher,
                                       not_found_is_err=True)
        origin = pub[0].get_children(Origin.ORIGIN_LABEL, Origin,
                                     not_found_is_err=True)[0].origin
        self.src = self.doc.str_replace_paths_refs(origin)

        # Find out if URL is/isn't a datastream, and whether local/remote.
        src_type = self.get_src_type(self.src)

        # Get the list of transfers from this specific node in the DOC
        # and parse the information into a list of transfers that will
        # be performed
        transfer_list = soft_node.get_children(class_type=SVR4Spec)

        for trans in transfer_list:

            # If an install, check that packages exist and get total size.
            if trans.action == "install":
                if src_type == AbstractSVR4.REMOTE_DSTR_TYPE:
                    self.total_size = self.get_size_via_http(self.src)
                elif src_type == AbstractSVR4.LOCAL_DSTR_TYPE:
                    self.total_size = self.ds_pkg_size_and_verify(self.src,
                        trans.contents)
                else:
                    self.total_size = self.nonds_pkg_size_and_verify(
                        self.src, trans.contents)
                self.logger.debug("total size of pkgs: %.1fMb (%dKb)",
                                 float(self.total_size) / 1024,
                                 self.total_size)

            trans_attr = dict()
            trans_attr[ACTION] = trans.action
            trans_attr[CONTENTS] = trans.contents
            # Get the Args from the DOC if they exist.
            args = trans.get_children(Args.ARGS_LABEL, Args)
            if len(args) == 0:
                args = None

            # Args not specified.
            # Take default set of args for pkgadd or pkgrm
            if not args:
                if trans_attr.get(ACTION) == "install":
                    trans_attr[SVR4_ARGS] = \
                         AbstractSVR4.DEFAULT_PKGADD_ARGS % \
                         (self.ADMIN_FILE, self.src, self.dst)
                else:
                    # Use the default pkgrm args
                    trans_attr[SVR4_ARGS] = \
                         AbstractSVR4.DEFAULT_PKGRM_ARGS % \
                         (self.ADMIN_FILE, self.dst)
            else:
                if trans_attr.get(ACTION) != "install":
                    raise ValueError("Custom args can be used only "
                                    "with an \"install\" action.")
                # Custom pkgadd.
                # if an argument was specified, validate that the user
                # only specified one and that it was svr4_args. Anything
                # else is invalid.
                if len(args) > 1:
                    self._cleanup()
                    raise ValueError("Invalid: multiple svr4 args "
                                    "specified ")

                self.logger.debug("pkgadd(1M) will be called using args "
                                 "from the manifest")
                self.logger.debug("  for the following packages: %s" %
                                 ", ".join(trans_attr[CONTENTS]))
                try:
                    trans_attr[SVR4_ARGS] = args[0].arg_dict[SVR4_ARGS]
                except KeyError:
                    self._cleanup()
                    raise ValueError("Error defining svr4_args")

            # Append the transfer to the list of transfers to be performed
            self._transfer_list.append(trans_attr)


class TransferSVR4Attr(AbstractSVR4):
    '''SVR4 Transfer subclass that uses non-checkpoint interface

    To use, declare an instance, then fill in:
    - src (parent dir of local pkgs, or datastream file containing pkgs)
    - dst (filesystem to install into)
    - action ("install" or "uninstall")
    - contents (list of package names)
    '''

    def __init__(self, name):
        super(TransferSVR4Attr, self).__init__(name)

        # Transfer attributes
        self.action = None
        self.contents = None
        self.transfer_list = []

    def _parse_input(self):
        '''Parse the input parameters and put them into local attributes'''

        # src is required
        if not self.src:
            raise ValueError("Source must be specified")

        #dst is required
        if not self.dst:
            raise ValueError("Destination must be specified")

        trans_attr = dict()
        trans_attr[ACTION] = self.action
        trans_attr[CONTENTS] = self.contents

        # Analyze the source.
        src_type = self.get_src_type(self.src)

        # Apply appropriate args for pkgadd or pkgrm
        if trans_attr.get(ACTION) == "install":
            if src_type == AbstractSVR4.REMOTE_DSTR_TYPE:
                self.total_size = self.get_size_via_http(self.src)
            elif src_type == AbstractSVR4.LOCAL_DSTR_TYPE:
                self.total_size = self.ds_pkg_size_and_verify(self.src,
                    trans_attr[CONTENTS])
            else:
                self.total_size = self.nonds_pkg_size_and_verify(self.src,
                    trans_attr[CONTENTS])
            self.logger.debug("total size of pkgs in %s: %.1fMb (%dKb)",
                             self.src, float(self.total_size) / 1024,
                             self.total_size)

            trans_attr[SVR4_ARGS] = AbstractSVR4.DEFAULT_PKGADD_ARGS % \
                                      (self.ADMIN_FILE, self.src, self.dst)

        elif trans_attr.get(ACTION) == "uninstall":
            trans_attr[SVR4_ARGS] = AbstractSVR4.DEFAULT_PKGRM_ARGS % \
                                          (self.ADMIN_FILE, self.dst)
        else:
            raise ValueError("SVR4 Action must be install or uninstall.")

        self._transfer_list.append(trans_attr)
