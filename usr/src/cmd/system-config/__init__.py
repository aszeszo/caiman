#!/usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#


'''System Configuration Interactive (SCI) Tool'''


import gettext
import atexit
import curses
import locale
import logging
from optparse import OptionParser
import os
import shutil
import signal
import sys

from solaris_install import engine
from solaris_install.data_object import DataObject
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install import Popen, CalledProcessError
from solaris_install.engine import InstallEngine, RollbackError
from solaris_install.ict.apply_sysconfig import APPLY_SYSCONFIG_DICT, \
    APPLY_SYSCONFIG_PROFILE_KEY

_ = gettext.translation("sysconfig", "/usr/share/locale",
                        fallback=True).ugettext
SCI_HELP = "/usr/share/sysconfig/help"
COMMA = ","
DASH_G = "-g"
SUPPORT_ERR = "system is the only supported grouping for configure " \
                "and unconfigure"
SUBCOMMANDS = "unconfigure, configure, create-profile"

# system configuration groups
# hostname
SC_GROUP_IDENTITY = 'identity'
# networking
SC_GROUP_NETWORK = "network"
# naming services
SC_GROUP_NS = 'naming_services'
# keyboard layout
SC_GROUP_KBD = 'kbd_layout'
# date and time
SC_GROUP_DATETIME = 'date_time'
# timezone and locale
SC_GROUP_LOCATION = 'location'
# user and root account
SC_GROUP_USERS = 'users'
# pseudo-group - includes all available groups
SC_GROUP_SYSTEM = 'system'

# list of configuration groups
SC_ALL_GROUPS = [SC_GROUP_IDENTITY, SC_GROUP_NETWORK, SC_GROUP_NS,
                 SC_GROUP_KBD, SC_GROUP_LOCATION, SC_GROUP_DATETIME,
                 SC_GROUP_USERS]

# all valid configuration groups including 'system' pseudo-group
SC_VALID_GROUPS = SC_ALL_GROUPS + [SC_GROUP_SYSTEM]

SMF_REPOSITORY = "etc/svc/repository.db"

CUSTOM_PROFILE_DIR = "etc/svc/profile/sc"


def get_sc_options_from_doc():
    '''Obtains list of sysconfig CLI options from Data Object Cache'''
    doc = InstallEngine.get_instance().doc.persistent
    sc_options = doc.get_first_child(name=SC_OPTIONS_LABEL)

    if sc_options is not None:
        return sc_options.options
    else:
        return None


def configure_group(group=None):
    '''Returns True if specified group is to be configured,
    otherwise returns False'''

    sc_options = get_sc_options_from_doc()

    # if list of groups can't be obtained, assume everything
    # is to be configured
    if sc_options is None:
        return True
    elif group in sc_options.grouping:
        return True
    else:
        return False

from solaris_install.logger import FileHandler, INSTALL_LOGGER_NAME
from solaris_install.sysconfig.date_time import DateTimeScreen
from solaris_install.sysconfig.network_nic_configure import NICConfigure
from solaris_install.sysconfig.network_nic_select import NICSelect
from solaris_install.sysconfig.network_type import NetworkTypeScreen
from solaris_install.sysconfig.profile import ConfigProfile, SMFConfig, \
                                              SMFInstance, SMFPropertyGroup, \
                                              SMFProperty
from solaris_install.sysconfig.nameservice import NSDNSChooser, NSAltChooser, \
                                                  NSDomain, \
                                                  NSDNSServer, NSDNSSearch, \
                                                  NSLDAPProfile, \
                                                  NSLDAPProxyBindChooser, \
                                                  NSLDAPProxyBindInfo, \
                                                  NSNISAuto, NSNISIP
from solaris_install.sysconfig.summary import SummaryScreen
from solaris_install.sysconfig.timezone import TimeZone
from solaris_install.sysconfig.users import UserScreen
from solaris_install.sysconfig.welcome import WelcomeScreen

import terminalui
from terminalui import LOG_LEVEL_INPUT, LOG_NAME_INPUT
from terminalui.action import Action
from terminalui.base_screen import BaseScreen, QuitException
from terminalui.help_screen import HelpScreen
from terminalui.i18n import get_encoding, set_wrap_on_whitespace
from terminalui.main_window import MainWindow
from terminalui.screen_list import ScreenList

SU_OK = 0
SU_FATAL_ERR = 1

# profile names
# profile configuring svc:/milestone/config:default service
CONFIG_PROFILE = "enable_sci.xml"
# profile configuring svc:/milestone/unconfig milestone
UNCONFIG_PROFILE = "unconfig.xml"

# directories
# temporary directory
VOLATILE_PATH = "/system/volatile"
# smf site-profile directory
PROFILE_PATH = "/etc/svc/profile/site"

# temporary profiles
TMP_CONFIG_PROFILE = os.path.join(VOLATILE_PATH, CONFIG_PROFILE)
TMP_UNCONFIG_PROFILE = os.path.join(VOLATILE_PATH, UNCONFIG_PROFILE)

# destination for profile configuring svc:/milestone/config:default service
CONFIG_PROFILE_DEST = os.path.join(PROFILE_PATH, CONFIG_PROFILE)
# destination for profile configuring svc:/milestone/unconfig milestone
UNCONFIG_PROFILE_DEST = os.path.join(PROFILE_PATH, UNCONFIG_PROFILE)

# default locations
DEFAULT_SC_PROFILE = "sc_profile.xml"
DEFAULT_SC_LOCATION = os.path.join(VOLATILE_PATH, "profile",
                                   DEFAULT_SC_PROFILE)

DEFAULT_LOG_LOCATION = "/var/tmp/install/sysconfig.log"
DEFAULT_LOG_LEVEL = "info"
LOG_FORMAT = ("%(asctime)s - %(levelname)-8s: "
              "%(filename)s:%(lineno)d %(message)s")
LOGGER = None
XSLT_FILE = os.environ.get('SC_XSLT',
                           '/usr/share/sysconfig/xslt/doc2sc_profile.xslt')
SC_FILE = DEFAULT_SC_LOCATION
GENERATE_SC_PROFILE_CHKPOINT = 'generate-sc-profile'

# sysconfig subcommands
CONFIGURE = "configure"
UNCONFIGURE = "unconfigure"
CREATE_PROFILE = "create-profile"
SVCADM = "/usr/sbin/svcadm"
SVCPROP = "/usr/bin/svcprop"
SVCCFG = "/usr/sbin/svccfg"
SYSTEM = "system"

# Commands for the console
CTSTAT = "/usr/bin/ctstat"
SVCPROP = "/usr/bin/svcprop"
CONSOLE_LOGIN = "svc:/system/console-login:default"
TTY = "/usr/bin/tty"
CONSOLE = "/dev/console"

ALT_ROOT_ENV_VAR = "_UNCONFIG_ALT_ROOT"

# DOC label for SysConfig options
SC_OPTIONS_LABEL = "sc_options"


class SysConfigOptions(DataObject):
    '''System Configuration options'''

    def __init__(self, options=None):
        super(SysConfigOptions, self).__init__(SC_OPTIONS_LABEL)
        self.options = options

    def to_xml(self):
        return None

    @classmethod
    def can_handle(cls, element):
        return False

    @classmethod
    def from_xml(cls, element):
        return None


# Public functions for consumers of sysconfig

def get_all_screens(main_win):
    '''Initializes a full set of configuration screens'''

    result = []
    result.append(NetworkTypeScreen(main_win, True))
    result.append(NICSelect(main_win))
    result.append(NICConfigure(main_win))
    _append_nameservice_screens(result, main_win)
    result.append(TimeZone(main_win, screen=TimeZone.REGIONS))
    result.append(TimeZone(main_win, screen=TimeZone.LOCATIONS))
    result.append(TimeZone(main_win))
    result.append(DateTimeScreen(main_win))
    result.append(UserScreen(main_win))

    return result


def get_screens_from_groups(main_win):
    '''Initializes subset of configuration screens matching list of specified
    configuration groups'''

    result = []

    # hostname
    if configure_group(SC_GROUP_IDENTITY):
        result.append(NetworkTypeScreen(main_win,
                                        configure_group(SC_GROUP_NETWORK)))

    # network
    if configure_group(SC_GROUP_NETWORK):
        result.append(NICSelect(main_win))
        result.append(NICConfigure(main_win))

    # name services
    if configure_group(SC_GROUP_NS):
        _append_nameservice_screens(result, main_win)

    # timezone
    if configure_group(SC_GROUP_LOCATION):
        result.append(TimeZone(main_win, screen=TimeZone.REGIONS))
        result.append(TimeZone(main_win, screen=TimeZone.LOCATIONS))
        result.append(TimeZone(main_win))

    # date and time
    if configure_group(SC_GROUP_DATETIME):
        result.append(DateTimeScreen(main_win))

    # initial user
    if configure_group(SC_GROUP_USERS):
        result.append(UserScreen(main_win))

    return result


def _append_nameservice_screens(result, main_win):
    ''' Initialize and append all name service screens '''
    result.append(NSDNSChooser(main_win))
    result.append(NSDNSServer(main_win))
    result.append(NSDNSSearch(main_win))
    result.append(NSAltChooser(main_win))
    result.append(NSDomain(main_win))
    result.append(NSLDAPProfile(main_win))
    result.append(NSLDAPProxyBindChooser(main_win))
    result.append(NSLDAPProxyBindInfo(main_win))
    result.append(NSNISAuto(main_win))
    result.append(NSNISIP(main_win))


def register_checkpoint(sc_profile=SC_FILE, xslt=XSLT_FILE):
    '''Registers the GENERATE_SC_PROFILE_CHKPOINT checkpoint with the engine.
    Also adds config_profile to InstallEngine.doc.persistent'''
    eng = InstallEngine.get_instance()

    sc_kwargs = {'xslt_file': xslt}
    sc_args = [sc_profile]
    eng.register_checkpoint(GENERATE_SC_PROFILE_CHKPOINT,
                            "solaris_install/manifest/writer",
                            "ManifestWriter", args=sc_args, kwargs=sc_kwargs)

    # Add profile location to the ApplySysconfig checkpoint's data dict.
    # Try to find the ApplySysconfig data dict from the DOC in case it
    # already exists.
    as_doc_dict = None
    as_doc_dict = eng.doc.volatile.get_first_child(name=APPLY_SYSCONFIG_DICT)
    if as_doc_dict is None:
        # Initialize new dictionary in DOC
        as_dict = {APPLY_SYSCONFIG_PROFILE_KEY: sc_profile}
        as_doc_dict = DataObjectDict(APPLY_SYSCONFIG_DICT, as_dict)
        eng.doc.volatile.insert_children(as_doc_dict)
    else:
        # Add to existing dictionary in DOC
        as_doc_dict.data_dict[APPLY_SYSCONFIG_PROFILE_KEY] = sc_profile

    eng.doc.persistent.insert_children([ConfigProfile()])


def vararg_callback(option, opt_str, value, parser):
    '''Callback function to parse the -g option. Multiple groups are
    allowed to be specified.
    '''
    value = list()

    def floatable(arg_str):
        '''Checks for a float variable'''
        try:
            float(arg_str)
            return True
        except ValueError:
            return False

    for arg in parser.rargs:
        if arg[:2] == "--" and len(arg) > 2:
            break
        if arg[:1] == "-" and len(arg) > 1 and not floatable(arg):
            break
        # Strip off the comma separating the groups if it's there
        # and check that the user hasn't specified the same grouping
        # more than once. If they have, only keep one.
        if arg.strip(",") not in value:
            value.append(arg.strip(","))
    del parser.rargs[:len(value)]
    setattr(parser.values, option.dest, value)


def create_config_profiles(sub_cmd, options):
    ''' Create two separate SMF profiles configuring milestone/config and
    milestone/unconfig services. Place them in /etc/svc/profile/site
    directory.
    '''
    # Remove any old profile files.
    if os.path.exists(TMP_CONFIG_PROFILE):
        os.unlink(TMP_CONFIG_PROFILE)
    if os.path.exists(TMP_UNCONFIG_PROFILE):
        os.unlink(TMP_UNCONFIG_PROFILE)

    # create profile configuring milestone/config service
    fhdl = open(TMP_CONFIG_PROFILE, "w")

    # Header and DTD
    fhdl.writelines("<?xml version='1.0'?>\n")
    fhdl.writelines("<!DOCTYPE service_bundle SYSTEM "
                    "'/usr/share/lib/xml/dtd/service_bundle.dtd.1'>\n")

    fhdl.writelines("<service_bundle type=\"profile\" "
                    "name=\"config_profile\">\n")
    fhdl.writelines("<service name=\"milestone/config\" version=\"1\" "
                    "type=\"service\">\n")
    fhdl.writelines("<instance name=\"default\" enabled=\"true\">\n")

    # sysconfig property group
    fhdl.writelines("<property_group name=\"sysconfig\" "
                    "type=\"application\">\n")

    # interactive_config property
    # Set to true if no profiles were provided in reconfiguration scenario.
    # Othwerwise set it to false.
    if sub_cmd == CONFIGURE and not options.profile:
        fhdl.writelines("<propval name=\"interactive_config\" type=\"boolean\""
                        " value=\"true\"/>\n")
    else:
        fhdl.writelines("<propval name=\"interactive_config\" type=\"boolean\""
                        " value=\"false\"/>\n")

    # config_group from -g option
    fhdl.writelines("<propval name=\"config_groups\" type=\"astring\""
                    " value=\"")
    for grp in options.grouping:
        fhdl.writelines("%s " % grp)
    fhdl.writelines("\"/>\n")

    # configure flag
    # Set to true in reconfiguration scenario, otherwise set to false.
    if sub_cmd == CONFIGURE:
        fhdl.writelines("<propval name=\"configure\" type=\"boolean\" "
                        "value=\"true\"/>\n")
    else:
        fhdl.writelines("<propval name=\"configure\" type=\"boolean\" "
                        "value=\"false\"/>\n")

    fhdl.writelines("</property_group>\n")
    fhdl.writelines("</instance>\n")
    fhdl.writelines("</service>\n")
    fhdl.writelines("</service_bundle>\n")
    fhdl.close()

    profile = CONFIG_PROFILE_DEST
    if options.alt_root:
        profile = options.alt_root + profile
    # Move file to target destination
    shutil.move(TMP_CONFIG_PROFILE, profile)

    # create profile configuring milestone/unconfig milestone
    fhdl = open(TMP_UNCONFIG_PROFILE, "w")

    # Header and DTD
    fhdl.writelines("<?xml version='1.0'?>\n")
    fhdl.writelines("<!DOCTYPE service_bundle SYSTEM "
                    "'/usr/share/lib/xml/dtd/service_bundle.dtd.1'>\n")
    fhdl.writelines("<service_bundle type=\"profile\" "
                    "name=\"unconfig_profile\">\n")

    # unconfig milestone
    fhdl.writelines("<service name=\"milestone/unconfig\" version=\"1\" "
                    "type=\"service\">\n")

    # configuration property group
    fhdl.writelines("<property_group name=\"sysconfig\" "
                    "type=\"application\">\n")

    # shutdown property default is false, true if -s was specified.
    if options.shutdown:
        fhdl.writelines("<propval name=\"shutdown\" type=\"boolean\" "
                        "value=\"true\"/>\n")
    else:
        fhdl.writelines("<propval name=\"shutdown\" type=\"boolean\" "
                        "value=\"false\"/>\n")

    # destructive property default is false, true if --destructive
    # was specified.
    if options.destructive:
        fhdl.writelines("<propval name=\"destructive_unconfig\" "
                        "type=\"boolean\" value=\"true\"/>\n")
    else:
        fhdl.writelines("<propval name=\"destructive_unconfig\" "
                        "type=\"boolean\" value=\"false\"/>\n")

    # unconfig_groups from -g option
    fhdl.writelines("<propval name=\"unconfig_groups\" type=\"astring\" "
                    "value=\"")
    for grp in options.grouping:
        fhdl.writelines("%s " % grp)
    fhdl.writelines("\"/>\n")

    # unconfigure flag, always true
    fhdl.writelines("<propval name=\"unconfigure\" type=\"boolean\" "
                    "value=\"true\"/>\n")
    fhdl.writelines("</property_group>\n")
    fhdl.writelines("</service>\n")
    fhdl.writelines("</service_bundle>\n")
    fhdl.close()

    profile = UNCONFIG_PROFILE_DEST
    if options.alt_root:
        profile = options.alt_root + profile
    # Move file to target destination
    shutil.move(TMP_UNCONFIG_PROFILE, profile)


def profile_is_valid(profile_name):
    '''Validate system configuration profile:
        - profile has to have .xml extension,
          otherwise smf(5) refuses to apply it
        - profile has to syntactically validate using 'svccfg apply -n'

        Return: True if profile is valid, otherwise False
    '''
    # Check if profile contains .xml suffix.
    if not profile_name.endswith(".xml"):
        print _("Custom site profile %s is invalid, missing .xml suffix."
                 % profile_name)
        return False

    # Validate file syntactically.
    try:
        Popen.check_call([SVCCFG, "apply", "-n", profile_name])
    except CalledProcessError:
        print _("Custom site profile %s is invalid or has"
                 "invalid permissions." % profile_name)
        return False

    return True


def apply_profiles(profile_list):
    '''Apply config profiles to the SMF repository.'''

    for profile in profile_list:
        cmd = [SVCCFG, "apply", profile]
        try:
            Popen.check_call(cmd, stderr=Popen.PIPE,
                             check_result=(Popen.STDERR_EMPTY, 0))
        except CalledProcessError as err:
            print err.popen.stderr
            print _("Unable to apply SMF profile %s." % profile)
            raise


def valid_group_check(groupings, sub_cmd, parser):
    '''Check to see if the grouping(s) specified are valid.'''
    if sub_cmd[0] == CREATE_PROFILE:

        # Check that the grouping specified is valid.
        for grp in groupings:
            if grp not in SC_VALID_GROUPS:
                err = "Grouping must be one of "
                for grping in SC_VALID_GROUPS:
                    err += grping + " "
                parser.error(err)
    else:

        if len(groupings) > 1:
            parser.error(SUPPORT_ERR)
        if groupings[0] != SYSTEM:
            parser.error(SUPPORT_ERR)


def parse_create_profile_args(parser, args):
    '''Parses command line options for 'create-profile' sysconfig subcommand.
    '''
    (options, sub_cmd) = parser.parse_args(args)

    # List of configuration groups - entries are separated by commas
    options.grouping = options.grouping.split(',')

    # Check that the functional groups requested are valid
    valid_group_check(options.grouping, sub_cmd, parser)

    # If the user specified 'system' in a list of groups, configure all groups.
    if SC_GROUP_SYSTEM in options.grouping:
        options.grouping = SC_ALL_GROUPS

    # Run Install Engine in debug mode
    options.debug = (options.log_level.lower() in ['debug', 'input'])

    log_level = options.log_level.upper()
    if hasattr(logging, log_level):
        options.log_level = getattr(logging, log_level.upper())
    elif log_level == LOG_NAME_INPUT:
        options.log_level = LOG_LEVEL_INPUT
    else:
        raise IOError(2, "Invalid --log-level parameter", log_level.lower())

    #
    # Most of filesystems (modulo tmpfs(7FS) ones) are read-only
    # in ROZR non-global zone booted in read-only mode. In such case,
    # redirect log file to writable directory.
    #
    if _in_rozr_zone():
        log_file_basename = os.path.basename(options.logname)
        options.logname = os.path.join(VOLATILE_PATH, log_file_basename)

    return (options, sub_cmd)


def do_create_profile(options):
    '''Run System Configuration Interactive Tool in order to create
    System Configuration profile'''
    try:
        _prepare_engine(options)

        # insert sysconfig CLI options into DOC
        doc_options = SysConfigOptions(options)
        doc = InstallEngine.get_instance().doc.persistent
        doc.insert_children(doc_options)

        # Navigate user through the set of configuration screens. Generate
        # resulting profile only if user went through the complete set of
        # sysconfig screens.
        if _show_screens(options):
            # First set the umask read-only by user (root).
            # Then let the ManifestWriter generate resulting SC profile.
            # Finally, reset umask to the original value.
            orig_umask = os.umask(0377)
            eng = InstallEngine.get_instance()
            (status, failed_cps) = eng.execute_checkpoints()
            os.umask(orig_umask)

            # If ManifestWriter failed to create SC profile, inform user
            # and exit with error.
            if status != InstallEngine.EXEC_SUCCESS:
                print _("Failed to generate SC profile.")
                _exit(options.logname, errcode=1)
            else:
                print _("SC profile successfully generated.")

        _exit(options.logname, errcode=0)
    except SystemExit:
        raise
    except:
        if LOGGER is None:
            # Error occurred before logging is setup; no place to
            # dump the traceback
            raise
        LOGGER.exception(_("An unhandled exception occurred."))
        exc_type, exc_value = sys.exc_info()[:2]

        try:
            doc = InstallEngine.get_instance().doc.persistent
            sc_prof = doc.get_first_child(name="sysconfig")
            LOGGER.error("Sysconfig profile:\n%s", sc_prof)
        except:
            # Ignore any errors to avoid masking the original exception
            pass

        print _("An unhandled exception occurred.")
        if exc_value:
            print '\t%s: "%s"' % (exc_type.__name__, exc_value)
        else:
            print "\t%s" % exc_type.__name__
        print _("Full traceback data is in the log")
        _exit(options.logname, errcode=1)


def do_unconfigure(sub_cmd, options):
    '''Performs the requested unconfigure operations'''
    try:
        create_config_profiles(sub_cmd, options)
    except IOError:
        print _("IO error creating profile")
        sys.exit(SU_FATAL_ERR)

    if not options.alt_root:
        try:
            apply_profiles([CONFIG_PROFILE_DEST, UNCONFIG_PROFILE_DEST])
        except:
            print _("Unable to apply the unconfigure parameters to the image")
            sys.exit(SU_FATAL_ERR)

        # system-unconfig is an SMF milestone. Bring the
        # system down to the milestone.
        cmd = [SVCADM, "milestone", "unconfig"]
        try:
            Popen.check_call(cmd, stderr=Popen.PIPE,
                check_result=(Popen.STDERR_EMPTY, 0))
        except CalledProcessError as err:
            print err.popen.stderr
            print _("Unable to initiate unconfiguration process.")
            sys.exit(SU_FATAL_ERR)


def parse_unconfig_args(parser, args):
    # Now parse options specific to the subcommand
    (options, sub_cmd) = parser.parse_args(args)

    options.alt_root = os.getenv(ALT_ROOT_ENV_VAR)

    # If operating on alternate root, verify given path.
    if options.alt_root:
        if not os.access(options.alt_root, os.W_OK):
            print _("Root filesystem provided for the non-global zone"
                    " does not exist")
            sys.exit(SU_FATAL_ERR)

    #
    # unconfiguration/reconfiguration is not permitted in ROZR non-global
    # zone unless such zone is booted in writable mode.
    # When operating in alternate root mode, skip that check, since in that
    # case ROZR zone would be manipulated from global zone. That along with
    # previous check guarantees writable access.
    #
    if not options.alt_root and _in_rozr_zone():
        print _("Root filesystem mounted read-only, '%s' operation"
                 " not permitted." % sub_cmd[0])
        print _("The likely cause is that sysconfig(1m) was invoked"
                 " in ROZR non-global zone.")
        print _("In that case, see mwac(5) and zonecfg(1m) man pages"
                 " for additional information.")

        sys.exit(SU_FATAL_ERR)

    # At this time, it is believed that there is no point in allowing
    # the prompt to be displayed in the alternate root case. Since there is no
    # use case, let's not explode our test matrix.
    if options.alt_root and options.shutdown:
        parser.error("Invalid to specify -s option with an alternate root")

    # If no grouping is specified, that implies a system level unconfiguration.
    # Confirm with the user that this is what they want for security reasons.
    if not options.grouping:
        if sub_cmd[0] == CONFIGURE:
            print _("This program will re-configure your system.")
        else:
            print _("This program will unconfigure your system.")
            print _("The system will be reverted to a \"pristine\" state.")
            print _("It will not have a name or know about other systems"
                    " or networks.")

        msg = _("Do you want to continue (y/[n])? ")
        confirm = raw_input(msg.encode(get_encoding()))
        if confirm.lower() != "y":
            sys.exit(SU_OK)

        # They have confirmed, set grouping to system.
        options.grouping = [SYSTEM]

    # Formulate the comma separated string into a list
    for grp in options.grouping:
        if COMMA in grp:
            options.grouping.extend(map(str.strip, grp.split(",")))
            options.grouping.remove(grp)
            break

    # If the user specifies a list of groups and one of them is system set
    # to just system since it is a superset of all other groupings.
    if len(options.grouping) > 1 and SYSTEM in options.grouping:
        options.grouping = [SYSTEM]

    if options.alt_root:
        svccfg_repository = os.path.join(options.alt_root, SMF_REPOSITORY)
        os.environ["SVCCFG_REPOSITORY"] = svccfg_repository

    # Check that the functional groups requested are valid
    valid_group_check(options.grouping, sub_cmd, parser)

    # If not operating on the alternate root, we can and must check to make
    # sure that the grouping specified has services of that grouping on the
    # image.
    if not options.alt_root and SYSTEM not in options.grouping:
        # Check that there exist unconfigurable services with the specified
        # grouping on the machine.
        cmd = [SVCPROP, "-p", "unconfigure/exec", "*"]
        p_ret = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL,
                                 check_result=Popen.ANY)
        unconfigurable_svcs = p_ret.stdout.split("\n")
        for opt_grp in options.grouping:
            found = False
            for svcs in unconfigurable_svcs:
                if svcs:
                    svc = svcs.split("/:properties")[0]
                    cmd = [SVCPROP, "-p", "sysconfig/group", svc]
                    p_ret = Popen.check_call(cmd, stdout=Popen.STORE,
                        stderr=Popen.DEVNULL, check_result=Popen.ANY)
                    grping = p_ret.stdout.strip()
                    if grping == opt_grp:
                        found = True

            if not found:
                print _("There are no services on the system with grouping "
                        "of %s" % opt_grp)
                sys.exit(1)

    #
    # The user specified a profile file or a directory with profiles to use
    # on the configure. Verify that supplied profiles contain .xml suffix
    # (otherwise smf(5) will not apply them) and syntactically
    # validate them. Then copy them to the temporary location,
    # /etc/svc/profile/sc/ directory. The unconfig milestone will move
    # them to the site area when it runs. We can't put profiles
    # to site directory right now because they may end up applied before
    # unconfiguration runs and then removed during unconfiguration.
    #
    if sub_cmd[0] == CONFIGURE and options.profile:
        # Verify that supplied path (file or directory) exists.
        if not os.path.exists(options.profile):
            parser.error("%s does not exist." % options.profile)

        # Remove all of /etc/svc/profile/sc
        custom_profile_dir = CUSTOM_PROFILE_DIR
        if options.alt_root:
            custom_profile_dir = os.path.join(options.alt_root,
                                              custom_profile_dir)
        else:
            custom_profile_dir = os.path.join("/", custom_profile_dir)

        if os.path.exists(custom_profile_dir):
            for root, dirs, files in os.walk(custom_profile_dir):
                for profile_file in files:
                    os.unlink(os.path.join(root, profile_file))
        else:
            os.mkdir(custom_profile_dir)

        if os.path.isdir(options.profile):
            #
            # Profile directory is specified.
            # Directory has to contain at least one profile. Start with
            # assumption that given directory does not contain any
            # profile.
            #
            profile_dir_is_empty = True

            # Validate profiles - all supplied profiles have to validate.
            for root, dirs, files in os.walk(options.profile):
                for pfile in files:
                    profile_file = os.path.join(root, pfile)
                    # Abort if profile is invalid.
                    if not profile_is_valid(profile_file):
                        sys.exit(SU_FATAL_ERR)

                    # Place profile in the temporary site profile area.
                    orig_umask = os.umask(0377) 
                    shutil.copyfile(profile_file,
                                    os.path.join(custom_profile_dir, pfile))
                    os.umask(orig_umask) 
                    profile_dir_is_empty = False

            # If no profile was found in given directory, abort.
            if profile_dir_is_empty:
                print _("Directory %s does not contain any profile."
                         % options.profile)
                sys.exit(SU_FATAL_ERR)

        else:
            # Profile is a file - validate it.
            if not profile_is_valid(options.profile):
                sys.exit(SU_FATAL_ERR)

            # Place profile in the temporary site profile area.
            orig_umask = os.umask(0377)
            shutil.copyfile(options.profile, os.path.join(custom_profile_dir,
                            os.path.basename(options.profile)))
            os.umask(orig_umask) 

    #
    # if there is a request to re-configure system in interactive way
    # (using SCI tool), check if we are on console, since this is where SCI
    # tool will be lauched. If we are not on console, let user confirm this
    # is really what one wants to do.
    #
    if sub_cmd[0] == CONFIGURE and not options.profile \
        and not options.alt_root:

        # For now, sysconfig should halt when the user runs sysconfig configure
        # after running sysconfig unconfigure. When the functionality that
        # enables the unconfiguration of individual groupings is implemented,
        # this may need to be revisited. Currently, system is the only group
        # that can be configured/unconfigured.
        cmd = [SVCPROP, "-c", "-p", "sysconfig/unconfigure",
               "milestone/unconfig"]
        p_ret = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL,
                             check_result=Popen.ANY)

        unconfigure_has_occurred = p_ret.stdout.strip()

        cmd = [SVCPROP, "-c", "-p", "sysconfig/configure", "milestone/config"]
        p_ret = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL,
                             check_result=Popen.ANY)

        config_has_occurred = p_ret.stdout.strip()

        if unconfigure_has_occurred == 'true' \
            and config_has_occurred == 'false':
            print _("Error: system has been unconfigured. Reboot to invoke "
               "the SCI Tool and configure the system.")
            sys.exit(SU_FATAL_ERR)

        print _("Interactive configuration requested.")
        print _("System Configuration Interactive (SCI) tool will be" +
            " launched on console.")

        cmd = [TTY]
        try:
            p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.PIPE,
                                 check_result=(Popen.STDERR_EMPTY, 0))
        except CalledProcessError as err:
            print err.popen.stderr
            # if tty fails, we may not be able to interact with user.
            # In this case, skip the confirmation prompt.
        else:
            terminal_device = p.stdout.strip()

            if terminal_device != CONSOLE:
                print _("Since you are currently not logged on console,\n"
                         "you may not be able to navigate SCI tool.")
                msg = _("Would you like to proceed with re-configuration "
                        "(y/[n])? ")
                confirm = raw_input(msg.encode(get_encoding()))
                if confirm.lower() != "y":
                    sys.exit(SU_OK)

    return (options, sub_cmd)


def _in_rozr_zone():
    '''Return True if immutable (aka ROZR) zone booted in read only
    mode is detected. Otherwise return False.'''

    rozr_test_binary = '/sbin/sh'
    return (not os.access(rozr_test_binary, os.W_OK))


def _parse_options(arguments):
    ''' Parses sysconfig subcommands'''

    usage = "\t%prog unconfigure [-s] [-g system] " + \
            "[--destructive]" + \
            "\n\t%prog configure [-s] [-g system] " + \
            "[-c config_profile.xml | dir] [--destructive]" + \
            "\n\t%prog create-profile [-g system] " + \
            "[-o output_file] [-l logfile] [-v verbosity] [-b]"

    parser = OptionParser(usage=usage)

    try:
        i = arguments.index(DASH_G)
        try:
            if ' ' in arguments[i + 1]:
                parser.error("groupings must be a comma separated list")
                sys.exit(SU_FATAL_ERR)
        except IndexError:
            # Not necessarily an error if there isn't something at the
            # index value. The user may have passed in configuration with
            # no options, which defaults to system
            pass
    except ValueError:
        # no -g option found
        pass

    # This allows parsing of different subcommand options. It stops
    # parsing after the subcommand is populated.
    parser.disable_interspersed_args()
    (options, sub_cmd) = parser.parse_args(arguments)
    parser.enable_interspersed_args()

    if not sub_cmd:
        parser.error("Subcommand not specified\n"
            "Please select one of the following subcommands: "
            "%s" % SUBCOMMANDS)

    if sub_cmd[0] == CONFIGURE or sub_cmd[0] == UNCONFIGURE:
        # Set up valid options shared by configure and unconfigure subcommands.
        parser.add_option("-g", dest="grouping", action="callback",
                          callback=vararg_callback,
                          help="Grouping to %s" % sub_cmd[0])
        parser.add_option("-s", action="store_true",
                          dest="shutdown", default=False,
                          help="Shuts down the system after the "
                          "unconfiguration")
        parser.add_option("--destructive", dest="destructive",
                          default=False, action="store_true",
                          help="Do not preserve system data for a "
                          "group")

        # configure subcommand additionally supports '-c profile'.
        if sub_cmd[0] == CONFIGURE:
            parser.add_option("-c", dest="profile",
                              help="Custom site profile to use")

        (options, sub_cmd) = parse_unconfig_args(parser, arguments)
    elif sub_cmd[0] == CREATE_PROFILE:
        parser.add_option("-g", dest="grouping",
                          help=_("Grouping to configure"),
                          default=SC_GROUP_SYSTEM)
        parser.add_option("-o", dest="profile", metavar="FILE",
                          help=_("Saves created system configuration profile "
                          "into FILE.\t\t[default: %default]"),
                          default=DEFAULT_SC_LOCATION)
        parser.add_option("-l", "--log-location", dest="logname",
                          help=_("Set log location to FILE "
                          "(default: %default)"),
                          metavar="FILE", default=DEFAULT_LOG_LOCATION)
        parser.add_option("-v", "--log-level", dest="log_level",
                          default=DEFAULT_LOG_LEVEL,
                          help=_("Set log verbosity to LEVEL. In order of "
                          "increasing verbosity, valid values are 'error' "
                          "'warn' 'info' 'debug' or 'input'\n[default:"
                          " %default]"),
                          choices=["error", "warn", "info", "debug", "input"],
                          metavar="LEVEL")
        parser.add_option("-b", "--no-color", action="store_true",
                          dest="force_bw", default=False,
                          help=_("Force the tool to run in "
                          "black and white. This may be useful on some SPARC "
                          "machines with unsupported frame buffers\n"))
        (options, sub_cmd) = parse_create_profile_args(parser, arguments)
    else:
        parser.error("Invalid subcommand \n"
            "Please select one of the following subcommands: "
            "%s" % SUBCOMMANDS)

    return (options, sub_cmd)


def _exit(logname, errcode=0):
    '''Close out the logger and exit with errcode'''
    LOGGER.info("**** END ****")
    # LOGGER.close() # LOGGER.close() is broken - CR 7012566
    print _("Exiting System Configuration Tool. Log is available at:\n"
            "%s") % logname
    if isinstance(errcode, unicode):
        # pylint: disable-msg=E1103
        errcode = errcode.encode(get_encoding())
    sys.exit(errcode)


def _make_screen_list(main_win):
    screens = []
    screens.append(WelcomeScreen(main_win))
    screens.extend(get_screens_from_groups(main_win))
    screens.append(SummaryScreen(main_win))

    return screens


def _show_screens(options):
    '''Navigate user through the set of configuration screens.
    Return True if user went through the complete set of screens,
    otherwise return False.'''
    with terminalui as initscr:
        win_size_y, win_size_x = initscr.getmaxyx()
        if win_size_y < 24 or win_size_x < 80:
            msg = _("     Terminal too small. Min size is 80x24."
                    " Current size is %(x)ix%(y)i.") % \
                    {'x': win_size_x, 'y': win_size_y}
            sys.exit(msg)
        screen_list = ScreenList()

        actions = [Action(curses.KEY_F2, _("Continue"), screen_list.get_next),
                   Action(curses.KEY_F3, _("Back"),
                          screen_list.previous_screen),
                   Action(curses.KEY_F6, _("Help"), screen_list.show_help),
                   Action(curses.KEY_F9, _("Quit"), screen_list.quit)]

        main_win = MainWindow(initscr, screen_list, actions,
                              force_bw=options.force_bw)
        screen_list.help = HelpScreen(main_win, _("Help Topics"),
                                      _("Help Index"),
                                      _("Select a topic and press Continue."))

        win_list = _make_screen_list(main_win)
        screen_list.help.setup_help_data(win_list)
        screen_list.screen_list = win_list
        screen = screen_list.get_next()

        signal.signal(signal.SIGINT, signal.SIG_IGN)

        try:
            while screen is not None:
                eng = InstallEngine.get_instance()
                sc_prof = eng.doc.persistent.get_first_child(name="sysconfig")
                LOGGER.debug("Sysconfig profile:\n%s", sc_prof)
                LOGGER.debug("Displaying screen: %s", type(screen))
                screen = screen.show()
        except QuitException:
            LOGGER.info("User quit the application prematurely.")
            return False
        else:
            return True


def _prepare_engine(options):
    '''Initialize the InstallEngine'''
    InstallEngine(default_log=options.logname, loglevel=options.log_level,
                  debug=options.debug)

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    # Don't set the global LOGGER until we're certain that logging
    # is up and running, so the main() except clause can figure out
    # if exception data can be written to the log or if it needs to
    # dump to stdout
    global LOGGER
    LOGGER = logger

    terminalui.init_logging(INSTALL_LOGGER_NAME)

    # if no directory in output profile path
    if not os.path.dirname(options.profile):
        # explicitly provide default directory for manifest writer
        options.profile = './' + options.profile
    register_checkpoint(sc_profile=options.profile)


def _init_locale():
    '''Initializes the locale'''
    locale.setlocale(locale.LC_ALL, "")
    gettext.install("sysconfig", "/usr/share/locale", unicode=True)
    set_wrap_on_whitespace(_("DONT_TRANSLATE_BUT_REPLACE_msgstr_WITH_True_"
                             "OR_False: Should wrap text on whitespace in"
                             " this language"))
    BaseScreen.set_default_quit_text(_("Confirm: Quit?"),
                                     _("Do you really want to quit?"),
                                     _("Cancel"),
                                     _("Quit"))


def main():
    '''Main Function'''
    _init_locale()

    # Check that the command is executed by the root user
    if os.geteuid() != 0:
        print _("Error: Root privileges are required for "
               "this command.")
        sys.exit(SU_FATAL_ERR)

    (options, sub_cmd) = _parse_options(sys.argv[1:])

    if sub_cmd[0] == CONFIGURE or sub_cmd[0] == UNCONFIGURE:
        do_unconfigure(sub_cmd[0], options)
    elif sub_cmd[0] == CREATE_PROFILE:
        do_create_profile(options)

    sys.exit(SU_OK)

if __name__ == '__main__':
    main()
