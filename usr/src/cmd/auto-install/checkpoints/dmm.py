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
Derived Manifest Module (DMM) checkpoint module

This module runs a Derived Manifests script as a checkpoint.  The script is run
as user "aiuser", with the intent of setting up a manifest for the automated
installer to use.  This module sets up various environment variables the
script can query to help it understand the system it is running on, so that it
sets up the manifest properly.
'''

import os
import linecache
import pwd
import platform
import re
import shutil
import stat
import sys
import tempfile

from lxml import etree

from solaris_install import Popen, KSH93_SHEBANG, PYTHON_SHEBANG
from solaris_install.auto_install.ai_get_manifest import AICriteriaNetwork
from solaris_install.data_object import DataObject
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.manifest import ManifestError, validate_manifest
from solaris_install.manifest.parser import ManifestParserData, \
    MANIFEST_PARSER_DATA
from solaris_install.target.libdiskmgt import const, diskmgt

# Non-privileged account under which scripts are run / manifests are built.
AIUSER_ACCOUNT_NAME = "aiuser"

BYTES_PER_MB = 1048576

MSG_HEADER = "Derived Manifest Module: "

# Other configurables
WORKING_DIR = "/system/volatile/"
DEFAULT_AIM_MANIFEST = WORKING_DIR + "manifest.xml"
DEFAULT_AIM_LOGFILE = WORKING_DIR + "aimanifest_log"
INSTALL_CONF = WORKING_DIR + "install.conf"
DEFAULT_AI_SCHEMA = "/usr/share/install/ai.dtd"

# Commands
SU = "/usr/bin/su"
PRTCONF = ["/usr/sbin/prtconf", "-v"]
ISAINFO = ["/usr/bin/isainfo", "-n"]
XMLLINT = ["/usr/bin/xmllint"]
DERIVED_MANIFEST_DATA = "derived_manifest_data"

# Derived Manifest Module error classes


class DMMError(StandardError):
    '''
    Granddaddy of all Derived Manifest Module errors.
    '''
    pass


class DMMScriptAccessError(DMMError):
    '''
    Error opening script file.
    '''
    pass


class DMMScriptInvalidError(DMMError):
    '''
    Unsupported script type.
    '''
    pass


class DMMAccountError(DMMError):
    '''
    Account information not found for aiuser.
    '''
    pass


class DMMExecutionError(DMMError):
    '''
    Error when running the DMM script.
    '''
    pass


class DMMValidationError(DMMError):
    '''
    Error validating resulting manifest after running DMM script.
    '''
    pass


# The checkpoint module itself.
class DerivedManifestModule(AbstractCheckpoint):
    '''
    Derived Manifests Module - checkpoint class to derive a manifest
    '''
    def __init__(self, name, script=None, manifest=None):
        '''
        Checkpoint constructor.

        Args:
          name: Name of the checkpoint.

          script: Name of script to run.  Must be provided if the Data Object
                  Cache (DOC) does not provide it.  Used when the DOC does not
                  provide the script name.

          manifest: Name of the manifest to create.  Used when the DOC
                  does not provide the manifest name.  If not provided here nor
                  by the DOC, take a default name.
        '''

        super(DerivedManifestModule, self).__init__(name)

        # Check DOC for script name before checking input arg.
        doc = InstallEngine.get_instance().data_object_cache
        self.dmd = doc.volatile.get_first_child(name=DERIVED_MANIFEST_DATA)
        if self.dmd is None:
            self.dmd = DerivedManifestData(DERIVED_MANIFEST_DATA, script)
            doc.volatile.insert_children(self.dmd)

        # Use script name passed in if script name not available in the DOC.
        if script is None:
            if  self.dmd.script is None:
                errmsg = (MSG_HEADER + "Scriptfile must be specified or " +
                    "stored in data object cache.")
                self.logger.critical(errmsg)
                raise DMMScriptInvalidError(errmsg)
        else:
            self.dmd.script = script

        # Read the location of the manifest.
        # Check DOC first.
        # If not there, see if it was specified as an input argument.
        # Take a default name if it has not been provided in either place.

        self.mpd = doc.volatile.get_first_child(name=MANIFEST_PARSER_DATA)
        if self.mpd is None:
            self.mpd = ManifestParserData(MANIFEST_PARSER_DATA)
            doc.volatile.insert_children(self.mpd)

        # If DOC doesn't have a manifest, get name from input arg if provided.
        if self.mpd.manifest is None:
            self.mpd.manifest = manifest

        # If still nothing, take a default.
        if self.mpd.manifest is None:
            self.mpd.manifest = DEFAULT_AIM_MANIFEST

        # Get aiuser account information for accessing the manifest.
        try:
            self.aiuser = pwd.getpwnam(AIUSER_ACCOUNT_NAME)
        except KeyError:
            errmsg = MSG_HEADER + "Account \"%s\" information not found" % (
                                   AIUSER_ACCOUNT_NAME)
            self.logger.critical(errmsg)
            raise DMMAccountError(errmsg)

        msg = (MSG_HEADER + "Creating/modifying manifest at \"%s\"" %
            self.mpd.manifest)
        self.logger.info(msg)

        # Copy the script into the same dir where the derived manifest will be.
        derived_dir = os.path.dirname(self.mpd.manifest)
        script_name = os.path.basename(self.dmd.script)
        shutil.copyfile(self.dmd.script,
                        os.path.join(derived_dir, script_name))

        # Set up name of logfile aimanifest command can use.
        # This log will be collected after the script completes.
        tempfile.tempdir = WORKING_DIR
        self.aim_logfile = tempfile.mktemp()

    def get_progress_estimate(self):
        '''
        Returns an estimate of the time this checkpoint will take
        '''
        # Since scripts can vary, it's hard to pin down an exact time.
        # Assume that the average script will (include one network download)
        # and take 5 seconds.
        return 5

    def setup_prtconf_vars_in_env(self, arch):
        '''
        Set up prtconf-based environment variables for DMM environment.

        This includes environment info for:
            SI_MODEL
            SI_PLATFORM
            SI_MEMSIZE
            SI_INSTALL_SERVICE

        Args:
          arch: Architecture.  Currently either "sparc" or other.
        '''

        # Call prtconf.
        subproc = Popen(PRTCONF, stderr=Popen.STDOUT, stdout=Popen.PIPE)
        if subproc.returncode:
            self.logger.critical(MSG_HEADER +
                "Error running following command: " + " ".join(PRTCONF))
            model = ""
            mem_size = ""
            install_service = ""

        else:
            # Extract relevant info specific to architecture.
            # pylint: disable-msg=E1103
            prtconf_list = subproc.stdout.readlines()

            # Model / platform is prtconf line 5
            model = prtconf_list[4]

            # Memory size is the numeric value in the middle of prtconf line 2
            mem_size_pat = re.compile(r'\D*(\d*)\D*')
            mem_size = mem_size_pat.search(prtconf_list[1]).groups()[0]

            # Since install_service is extracted from prtconf output for X86,
            # just set it up here even though prtconf output is not used for it
            # for SPARC.
            install_service = ""
            if arch == "sparc":
                # Value we want is after the "=" on the line that starts with
                # "install_service"
                with open(INSTALL_CONF, "r") as insconf_file:
                    for service_line in insconf_file:
                        if "install_service" in service_line:
                            install_service = service_line.split("=")[1]
                            break
            else:
                # Take the prtconf output line just past the one that has
                #    "name='install_service'"
                # and parse it.  It will be of the form
                #    "value='xxx'"
                service_line = None
                for index, entry in enumerate(prtconf_list):
                    if "name='install_service' " in entry:
                        service_line = prtconf_list[index + 1]
                        break
                if service_line is not None:
                    install_service = service_line.split("'")[1]

        os.environ["SI_MODEL"] = model
        os.environ["SI_PLATFORM"] = model
        os.environ["SI_MEMSIZE"] = mem_size
        os.environ["SI_INSTALL_SERVICE"] = install_service

    def setup_isa_in_env(self):
        '''
        Set up SI_NATISA environment info for DMM environment.
        '''

        # Extract info from isainfo command.
        subproc = Popen(ISAINFO, stderr=Popen.STDOUT, stdout=Popen.PIPE)
        if subproc.returncode:
            self.logger.critical(MSG_HEADER + "Error running following " +
                "command: " + " ".join(ISAINFO))
            output = ""
        else:
            output = subproc.stdout.read().strip()
        os.environ["SI_NATISA"] = output

    @classmethod
    def setup_net_in_env(cls):
        '''
        Set up networking variables for DMM environment.
        This includes:
            SI_HOSTADDRESS
            SI_NETWORK
        '''
        net_params = AICriteriaNetwork()

        if net_params.client_ip is not None:
            os.environ["SI_HOSTADDRESS"] = net_params.client_ip
        else:
            os.environ["SI_HOSTADDRESS"] = ""

        if net_params.client_net is not None:
            os.environ["SI_NETWORK"] = net_params.client_net
        else:
            os.environ["SI_NETWORK"] = ""

    @classmethod
    def setup_disks_in_env(cls):
        '''
        Set up disk info for DMM environment.
        This includes:
            SI_DISKNAME_#
            SI_DISKSIZE_#
            SI_NUMDISKS
        '''
        disknum = 0

        # Show only fixed, operational drives.
        for drive in diskmgt.descriptors_by_type(const.DRIVE):
            if drive.attributes.type != "FIXED":
                continue
            if drive.attributes.status != "UP":
                continue
            if drive.media is None:
                continue

            size = long(drive.media.attributes.blocksize *
                        drive.media.attributes.size) / BYTES_PER_MB
            if (size == 0):
                continue

            disknum += 1
            os.environ["SI_DISKNAME_%d" % disknum] = drive.attributes.opath
            os.environ["SI_DISKSIZE_%d" % disknum] = "%ld" % size

        os.environ["SI_NUMDISKS"] = "%d" % disknum

    # pylint: disable-msg=E1103
    def subproc_env_setup(self):
        '''
        main function for setting up the environment in which DMM script is run
        '''

        # Prepare the manifest location for the script.  Script will be running
        # with minimal privileges, so have the aiuser own it.
        if not os.path.exists(self.mpd.manifest):
            self.logger.info(MSG_HEADER +
                             "No previous manifest at %s exists." %
                             self.mpd.manifest)
            self.logger.info(MSG_HEADER + "Creating empty manifest with "
                             "(uid,gid) = (%d,%d)" % (
                             self.aiuser.pw_uid, self.aiuser.pw_gid))
            mfd = open(self.mpd.manifest, "w+")
            os.fchown(mfd.fileno(), self.aiuser.pw_uid, self.aiuser.pw_gid)
            mfd.close()
        else:
            self.logger.info(MSG_HEADER + "Previous manifest at %s exists." %
                self.mpd.manifest)
        os.environ["AIM_MANIFEST"] = self.mpd.manifest

        # Set the logfile into the environment.
        os.environ["AIM_LOGFILE"] = self.aim_logfile
        lfd = open(self.aim_logfile, "a")
        os.fchown(lfd.fileno(), self.aiuser.pw_uid, self.aiuser.pw_gid)
        lfd.close()

        # Export the loglevel so the aimanifest command can use the same level.
        os.environ["AIM_LOGLEVEL"] = str(self.logger.getEffectiveLevel())

        # Set up legacy info variables for the script.

        # pylint: disable-msg=W0612
        (system, nodename, release, version, machine, processor) = \
            platform.uname()
        os.environ["SI_ARCH"] = processor
        os.environ["SI_CPU"] = processor  # Same as SI_ARC
        os.environ["SI_HOSTNAME"] = nodename
        os.environ["SI_KARCH"] = machine

        self.setup_prtconf_vars_in_env(processor)
        os.environ["SI_MANIFEST_SCRIPT"] = self.dmd.script
        self.setup_isa_in_env()
        self.setup_net_in_env()
        self.setup_disks_in_env()

    def execute(self, dry_run=False):
        '''Validate script and then run it.'''

        script_name = os.path.abspath(self.dmd.script)

        # Verify type of script.  Assumes this module is being run with enough
        # privilege to read the script.
        first_line = linecache.getline(script_name, 1)
        if (first_line == ""):
            errmsg = (MSG_HEADER + "Error opening scriptfile %s" % script_name)
            self.logger.critical(errmsg)
            raise DMMScriptAccessError(errmsg)

        # Look for appropriate shebang line to denote a supported script.
        # Note their appearance may have "/usr" prepended to them.
        first_line = first_line.strip()
        if ((not first_line.startswith("#!")) or
            (not (KSH93_SHEBANG in first_line or
                  PYTHON_SHEBANG in first_line))):
            errmsg = (MSG_HEADER + "Scriptfile %s first line does not " +
                "reference %s or %s" %
                (script_name, KSH93_SHEBANG, PYTHON_SHEBANG))
            self.logger.critical(errmsg)
            raise DMMScriptInvalidError(errmsg)

        # Verify accessibility of script.

        # Owner must be aiuser, or file mode must include o+rx.
        script_stat = os.stat(script_name)
        mode = stat.S_IMODE(script_stat.st_mode)
        own_rx = stat.S_IRUSR | stat.S_IXUSR
        grp_rx = stat.S_IRGRP | stat.S_IXGRP
        oth_rx = stat.S_IROTH | stat.S_IXOTH

        self.logger.info(MSG_HEADER + "Script to run: " + script_name)
        self.logger.info(MSG_HEADER +
                         "script mode is 0%o, uid is %d, gid is %d\n" %
                         (mode, script_stat.st_uid, script_stat.st_gid))

        if script_stat.st_uid == self.aiuser.pw_uid:
            perms_ok = ((mode & own_rx) == own_rx)
        elif script_stat.st_gid == self.aiuser.pw_gid:
            perms_ok = ((mode & grp_rx) == grp_rx)
        else:
            perms_ok = ((mode & oth_rx) == oth_rx)
        if not perms_ok:
            errmsg = MSG_HEADER + (("Script %s not readable and " +
                "executable by \"%s\" account") %
                (script_name, AIUSER_ACCOUNT_NAME))
            self.logger.critical(errmsg)
            raise DMMScriptInvalidError(errmsg)

        self.logger.info(MSG_HEADER +
                         "Script validated.  Running in subprocess...")

        cmdlist = [SU, AIUSER_ACCOUNT_NAME, script_name]
        subproc = Popen(cmdlist, stderr=Popen.STDOUT, stdout=Popen.PIPE,
                        preexec_fn=self.subproc_env_setup)

        self.logger.info(MSG_HEADER + "script output follows: ")

        outerr, dummy = subproc.communicate()
        while (subproc.returncode is None):
            outerr = outerr.split("\n")
            for line in outerr:
                self.logger.info("> " + line)
            outerr, dummy = subproc.communicate()

        outerr = outerr.split("\n")
        for line in outerr:
            self.logger.info("> " + line)

        self.logger.info(MSG_HEADER + "aimanifest logfile output follows: ")
        try:
            with open(self.aim_logfile, 'r') as aim_log:
                for line in aim_log:
                    self.logger.info(">> " + line.strip())
        except (OSError, IOError) as err:
            self.logger.error("Error reading aimanifest logfile: %s:%s" %
                              (err.filename, err.strerror))

        try:
            os.unlink(self.aim_logfile)
        except OSError as err:
            self.logger.warning("MSG_HEADER: Warning: Could not delete "
                                "aimanifest logfile %s: %s" %
                                (self.aim_logfile, err.strerror))

        if subproc.returncode < 0:
            # Would be nice to convert number to signal string, but no
            # facility for this exists in python.
            errmsg = (MSG_HEADER +
                      "Script was terminated by signal %d" %
                      -subproc.returncode)
        elif subproc.returncode > 0:
            # Note: can't get 128 or 129 (as can be returned by a shell when it
            # cannot access or run a script) because that has already been
            # checked for.
            errmsg = (MSG_HEADER + "Script \"" + self.dmd.script + \
                    "\" terminated on error.")
        if subproc.returncode != 0:
            self.logger.critical(errmsg)
            raise DMMExecutionError(errmsg)
        else:
            self.logger.info(MSG_HEADER + "script completed successfully")

        # Try to validate against a schema specified in the manifest DOCTYPE
        # header, if it is there.  Else fallback to a hardwired default.
        try:
            tree = etree.parse(self.mpd.manifest)
        except etree.XMLSyntaxError as err:
            self.logger.critical(MSG_HEADER + "Error parsing final manifest")
            self.logger.critical(str(err))
            errmsg = MSG_HEADER + "Final manifest failed XML validation"
            self.logger.critical(errmsg)
            raise DMMValidationError(errmsg)

        if ((tree.docinfo is not None) and
            (tree.docinfo.system_url is not None)):
            dtd = tree.docinfo.system_url
            self.logger.info(MSG_HEADER + "Using DTD from header of manifest.")
        else:
            dtd = DEFAULT_AI_SCHEMA
            self.logger.info(MSG_HEADER + "Manifest header refers to no DTD.")
        self.logger.info(MSG_HEADER + "Validating against DTD: %s" % dtd)

        try:
            validate_manifest(tree, dtd, self.logger)
        except (ManifestError) as err:
            # Note: validate_manifest already logged the errors.
            errmsg = MSG_HEADER + "Final manifest failed XML validation"
            self.logger.critical(errmsg)
            raise DMMValidationError(errmsg)
        else:
            self.logger.info(MSG_HEADER +
                             "XML validation completed successfully ")


class DerivedManifestData(DataObject):
    '''
    Derived Manifest xml tag handler class
    '''
    def __init__(self, name, script=None):
        '''
        Class constructor
        '''
        super(DerivedManifestData, self).__init__(name)
        self.script = script

    def to_xml(self):
        '''
        Convert DataObject DOM to XML
        '''
        # NO-OP method as DerivedManfest is never stored in XML manifest
        return None

    # pylint: disable-msg=W0613
    @classmethod
    def can_handle(cls, element):
        '''
        can_handle notification method for ai_instance tags
        '''
        # NO-OP method as DerivedManfest is never stored in XML manifest
        return None

    @classmethod
    def from_xml(cls, element):
        '''
        Convert from xml for DOM for DataObject storage
        '''
        # NO-OP method as DerivedManfest is never stored in XML manifest
        return None


# pylint: disable-msg=C0103
if __name__ == "__main__":

    from optparse import OptionParser

    def dmm(script, manifest):
        '''
        Main test program.
        '''
        inst = DerivedManifestModule("Derived Manifest Module", script,
                                     manifest)
        status = inst.execute()
        print "execute() returned %d\n" % status

    parser = OptionParser()
    parser.add_option("-m", "--manifest", dest="manifest")
    parser.add_option("-s", "--script", dest="script")
    (options, args) = parser.parse_args()

    sys.exit(dmm(options.script, options.manifest))