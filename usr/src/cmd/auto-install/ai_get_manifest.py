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
# Copyright (c) 2009, 2011, Oracle and/or its affiliates. All rights reserved.
#
# ai_get_manifest - AI Service Choosing Engine
#
"""
    ai_get_manifest - Obtains AI manifest from AI server
"""

import getopt
import gettext
import httplib
import os
import socket
from subprocess import Popen, PIPE
import re
import sys
import time
import traceback
import urllib

VERSION_FILE = '/usr/share/auto_install/version'


class AILog:
    """
        Class AILog: Logging service
        Description: Provides logging capabilities for AI service choosing
                     and AI service discovery engines.
    """

    # list of implemented logging levels
    AI_DBGLVL_NONE = 0
    AI_DBGLVL_EMERG = 1
    AI_DBGLVL_ERR = 2
    AI_DBGLVL_WARN = 3
    AI_DBGLVL_INFO = 4

    def __init__(self, logid="AI", logfile="/tmp/ai_sd_log",
                 debuglevel=AI_DBGLVL_WARN):
        self.log_file = logfile
        self.logid = logid
        self.dbg_lvl_current = debuglevel
        self.fh_log = None

        # list of prefixes displayed for particular logging levels
        self.log_prefix = {AILog.AI_DBGLVL_EMERG: "!",
            AILog.AI_DBGLVL_ERR: "E", AILog.AI_DBGLVL_WARN: "W",
            AILog.AI_DBGLVL_INFO: "I"}

        # default logging level
        self.dbg_lvl_default = AILog.AI_DBGLVL_INFO

        # if provided, open log file in append mode
        if self.log_file != None:
            try:
                self.fh_log = open(self.log_file, "a+")
            except IOError:
                self.fh_log = None

    def set_debug_level(self, level):
        """
            Set default logging level
                level - new logging level
        """

        if level in self.log_prefix:
            self.dbg_lvl_current = level

    def post(self, level, msg_format, * msg_args):
        """
            Post logging message
                level - logging level
                msg - message to be logged
                msg_args - message parameters
        """

        if level not in self.log_prefix:
            return

        if level > self.dbg_lvl_current:
            return

        timestamp = time.strftime("%m/%d %H:%M:%S", time.gmtime())

        log_msg = "<%s_%s %s> " % (self.logid, self.log_prefix[level],
                                   timestamp)

        if len(msg_args) == 0:
            log_msg += msg_format
        else:
            log_msg += msg_format % msg_args

        # post message to console
        print log_msg

        # post message to file
        if self.fh_log is not None:
            self.fh_log.write(log_msg + '\n')

        return

#
# AI service choosing logging service
#
AIGM_LOG = AILog("AISC")


def ai_exec_cmd(cmd):
    """     Description: Executes provided command using subprocess.Popen()
                         method and captures its stdout & stderr.
                         stderr is captured for debugging purposes

            Parameters:
                cmd - Command to be executed

            Returns:
                captured stdout from 'cmd'
                return code - 0..success, -1..failure
    """

    AIGM_LOG.post(AILog.AI_DBGLVL_INFO, "cmd:" + cmd)

    try:
        cmd_popen = Popen(cmd, shell=True, stdout=PIPE)
        (cmd_stdout, cmd_stderr) = cmd_popen.communicate()

    except OSError:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Popen() raised OSError exception")

        return None, -1

    except ValueError:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Popen() raised ValueError exception")

        return None, -1

    # capture output of stderr for debugging purposes
    if cmd_stderr is not None:
        AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                      " stderr: %s", cmd_stderr)

    # check if child process terminated successfully
    if cmd_popen.returncode != 0:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Command failed: ret=%d", cmd_popen.returncode)

        return None, -1

    return cmd_stdout, 0


class AICriteria:
    """ Class: AICriteria - base class for holding/manipulating AI criteria
    """

    def __init__(self, criteria=None):
        self.criteria = criteria

    def get(self):
        """ return criteria value
        """

        return self.criteria

    def is_known(self):
        """ check if information requried by criteria is available
        """

        return self.criteria is not None


class AICriteriaHostname(AICriteria):
    """ Class: AICriteriaHostname - class for obtaining/manipulating 'hostname'
        criteria
    """

    def __init__(self):
        AICriteria.__init__(self, socket.gethostname())


class AICriteriaArch(AICriteria):
    """ Class: AICriteriaArch class - class for obtaining/manipulating
        'architecture' criteria
    """

    client_arch = None

    def __init__(self):
        if AICriteriaArch.client_arch:
            AICriteria.__init__(self, AICriteriaArch.client_arch)
            return

        cmd = "/usr/bin/uname -m"
        client_arch, ret = ai_exec_cmd(cmd)

        if ret != 0 or client_arch == "":
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain machine architecture")
            AICriteriaArch.client_arch = None
        else:
            AICriteriaArch.client_arch = client_arch.strip()

        AICriteria.__init__(self, AICriteriaArch.client_arch)


class AICriteriaPlatform(AICriteria):
    """ Class: AICriteriaPlatform class - class for obtaining/manipulating
        'platform' criteria
    """

    client_platform = None

    def __init__(self):
        if AICriteriaPlatform.client_platform:
            AICriteria.__init__(self,
                                 AICriteriaPlatform.client_platform)
            return

        cmd = "/usr/bin/uname -i"
        AICriteriaPlatform.client_platform, ret = ai_exec_cmd(cmd)

        if ret != 0 or AICriteriaPlatform.client_platform == "":
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain machine platform")
        else:
            AICriteriaPlatform.client_platform = \
                AICriteriaPlatform.client_platform.strip()

        AICriteria.__init__(self, AICriteriaPlatform.client_platform)


class AICriteriaCPU(AICriteria):
    """ Class: AICriteriaCPU - class for obtaining/manipulating
        'processor type' criteria
    """

    client_cpu = None

    def __init__(self):
        if AICriteriaCPU.client_cpu:
            AICriteria.__init__(self, AICriteriaCPU.client_cpu)
            return

        cmd = "/usr/bin/uname -p"
        AICriteriaCPU.client_cpu, ret = ai_exec_cmd(cmd)

        if ret != 0 or AICriteriaCPU.client_cpu == "":
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain processor type")
        else:
            AICriteriaCPU.client_cpu = \
                AICriteriaCPU.client_cpu.strip()

        AICriteria.__init__(self, AICriteriaCPU.client_cpu)


class AICriteriaMemSize(AICriteria):
    """ Class: AICriteriaMemSize class - class for obtaining/manipulating
        'physical memory size' criteria, value is in MB
    """

    client_mem_size = None
    client_mem_size_initialized = False

    def __init__(self):
        if AICriteriaMemSize.client_mem_size_initialized:
            AICriteria.__init__(self,
                                 AICriteriaMemSize.client_mem_size)
            return

        AICriteriaMemSize.client_mem_size_initialized = True
        cmd = "/usr/sbin/prtconf -vp | /usr/bin/grep '^Memory size: '"
        client_mem_info, ret = ai_exec_cmd(cmd)

        if ret != 0 or client_mem_info == "":
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain memory size")
            AICriteriaMemSize.client_mem_size = None
            AICriteria.__init__(self)
            return

        (client_mem_size, client_mem_unit) = client_mem_info.split()[2:]
        client_mem_size = long(client_mem_size)

        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      "prtconf(1M) reported: %ld %s", client_mem_size,
                      client_mem_unit)

        if client_mem_size == 0 or client_mem_unit == "":
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain memory size")
            AICriteriaMemSize.client_mem_size = None
            AICriteria.__init__(self)
            return

        if client_mem_unit == "Kilobytes":
            client_mem_size /= 1024
        elif client_mem_unit == "Gigabytes":
            client_mem_size *= 1024
        elif client_mem_unit == "Terabytes":
            client_mem_size *= 1024 * 1024
        elif client_mem_unit != "Megabytes":
            AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                          "Unknown mem size units %s", client_mem_unit)
            client_mem_size = 0

        AICriteriaMemSize.client_mem_size = repr(client_mem_size).rstrip('L')

        AICriteria.__init__(self, AICriteriaMemSize.client_mem_size)


class AICriteriaNetworkInterface(AICriteria):
    """ Class: AICriteriaNetworkInterface class - class for
        obtaining/manipulating information about network interface -
        this criteria is currently private and not exposed to the server
    """

    network_iface = None
    ifconfig_iface_info = None
    network_iface_initialized = False

    def __init__(self):
        AICriteria.__init__(self)

        # initialize class variables only once
        if AICriteriaNetworkInterface.network_iface_initialized:
            return

        AICriteriaNetworkInterface.network_iface_initialized = True
        #
        # Obtain network interface name, which will be queried in next
        # step in order to obtain required network parameters
        #
        # Search for the first interface, which is UP - omit loopback
        # interfaces. Then use ifconfig for query the information about
        # that interface and store the result.
        #
        cmd = "/usr/sbin/ifconfig -au | /usr/bin/grep '[0-9]:' " \
            "| /usr/bin/grep -v 'LOOPBACK'"
        AICriteriaNetworkInterface.network_iface, ret = ai_exec_cmd(cmd)

        if ret != 0:
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain name of valid network interface")
            AICriteriaNetworkInterface.network_iface = None
        else:
            AICriteriaNetworkInterface.network_iface = \
                AICriteriaNetworkInterface.network_iface.split(':')[0]

            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Network interface obtained: %s",
                          AICriteriaNetworkInterface.network_iface)

            #
            # Collect all available information about network interface
            #
            cmd = "/usr/sbin/ifconfig %s" % \
                AICriteriaNetworkInterface.network_iface

            AICriteriaNetworkInterface.ifconfig_iface_info, ret = \
                ai_exec_cmd(cmd)

            if ret != 0 or \
               AICriteriaNetworkInterface.ifconfig_iface_info == "":
                AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                              "Could not obtain information about "
                              "network interface %s",
                              AICriteriaNetworkInterface.network_iface)

                AICriteriaNetworkInterface.ifconfig_iface_info = None


class AICriteriaMAC(AICriteriaNetworkInterface):
    """ Class: AICriteriaMAC - class for obtaining/manipulating
        information about client MAC address
    """

    client_mac = None
    client_mac_initialized = False

    def __init__(self):
        AICriteriaNetworkInterface.__init__(self)

        # initialize class variables only once
        if AICriteriaMAC.client_mac_initialized:
            AICriteria.__init__(self, AICriteriaMAC.client_mac)
            return

        AICriteriaMAC.client_mac_initialized = True

        if AICriteriaNetworkInterface.ifconfig_iface_info is None:
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain MAC address")
        else:
            AICriteriaMAC.client_mac = AICriteriaNetworkInterface. \
                ifconfig_iface_info.split("ether", 1)

            if len(AICriteriaMAC.client_mac) < 2:
                AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                              "Could not obtain client MAC address")
                AICriteriaMAC.client_mac = None
            else:
                AICriteriaMAC.client_mac = AICriteriaMAC.\
                    client_mac[1].strip().split()[0].strip()

                #
                # remove ':' and pad with '0's
                #
                # This step makes sure that the criteria are
                # passed to the server in the format which
                # server can understand. This is just an interim
                # solution.
                #
                # For longer term, all criteria should be
                # passed to the server in native format letting
                # the server side control the process of
                # conversion.
                #

                client_mac_parts = \
                    AICriteriaMAC.client_mac.split(":")

                AICriteriaMAC.client_mac = "%s%s%s%s%s%s" % \
                    (client_mac_parts[0].zfill(2),
                     client_mac_parts[1].zfill(2),
                     client_mac_parts[2].zfill(2),
                     client_mac_parts[3].zfill(2),
                     client_mac_parts[4].zfill(2),
                     client_mac_parts[5].zfill(2))

                AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                              "Client MAC address: %s",
                              AICriteriaMAC.client_mac)

        AICriteria.__init__(self, AICriteriaMAC.client_mac)


class AICriteriaIP(AICriteriaNetworkInterface):
    """ Class: AICriteriaIP class - class for obtaining/manipulating
        information about client IP address
    """

    client_ip = None
    client_ip_string = None
    client_ip_initialized = False

    def __init__(self):
        AICriteriaNetworkInterface.__init__(self)

        # initialize class variables only once
        if AICriteriaIP.client_ip_initialized:
            AICriteria.__init__(self, AICriteriaIP.client_ip_string)
            return

        AICriteriaIP.client_ip_initialized = True
        if AICriteriaNetworkInterface.ifconfig_iface_info == None:
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain IP address")
        else:
            AICriteriaIP.client_ip = AICriteriaNetworkInterface. \
                ifconfig_iface_info.split("inet", 1)[1].strip().\
                split()[0].strip()

            # remove '.'
            ip_split = AICriteriaIP.client_ip.split('.')
            AICriteriaIP.client_ip_string = "%03d%03d%03d%03d" % \
                (int(ip_split[0]), int(ip_split[1]),
                 int(ip_split[2]), int(ip_split[3]))

            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Client IP address: %s",
                          AICriteriaIP.client_ip_string)

        AICriteria.__init__(self, AICriteriaIP.client_ip_string)


class AICriteriaNetwork(AICriteriaIP):
    """ Class: AICriteriaNetwork class - class for obtaining/manipulating
        information about client network address
    """

    client_net = None
    client_net_initialized = False

    def __init__(self):
        AICriteriaIP.__init__(self)

        # initialize class variables only once
        if AICriteriaNetwork.client_net_initialized:
            AICriteria.__init__(self, AICriteriaNetwork.client_net)
            return

        AICriteriaNetwork.client_net_initialized = True

        if AICriteriaNetworkInterface.ifconfig_iface_info == None or \
            AICriteriaIP.client_ip == None:
            AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Could not obtain network address")
        else:
            # extract network mask
            client_netmask = \
                long(AICriteriaNetworkInterface.ifconfig_iface_info.
                    split("netmask", 1)[1].strip().split()[0].strip(), 16)

            # Translate IP address in string format to long
            ip_part = AICriteriaIP.client_ip.split('.')
            ip_long = long(ip_part[0]) << 24 | long(ip_part[1]) << \
                16 | long(ip_part[2]) << 8 | long(ip_part[3])

            client_network_long = ip_long & client_netmask

            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Mask: %08lX, IP: %08lX, Network: %08lX",
                          client_netmask, ip_long, client_network_long)

            AICriteriaNetwork.client_net = \
                "%03ld%03ld%03ld%03ld" % \
                (client_network_long >> 24,
                 client_network_long >> 16 & 0xff,
                 client_network_long >> 8 & 0xff,
                 client_network_long & 0xff)

            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Client net: %s", AICriteriaNetwork.client_net)

        AICriteria.__init__(self, AICriteriaNetwork.client_net)

#
# dictionary defining list of supported criteria and relationship
# between AI criteria and appropriate class which serves for obtaining
# and manipulating that criteria
#
# It also contains short informative description of the criteria
#
# Use following steps if support for new criteria is required:
# [1] Define name of criteria (like 'MEM'), create new class
#     which inherits AICriteria and implements method for
#     obtaining the criteria.
# [2] Add name of criteria, class and short description in following
#     dictionary
# [3] Test ;-)
#
AI_CRITERIA_SUPPORTED = {
    'arch': (AICriteriaArch, "Client machine architecture"),
    'cpu': (AICriteriaCPU, "Client processor type"),
    'hostname': (AICriteriaHostname, "Client hostname"),
    'ipv4': (AICriteriaIP, "Client IP address"),
    'mac': (AICriteriaMAC, "Client MAC address"),
    'mem': (AICriteriaMemSize, "Physical memory size"),
    'network': (AICriteriaNetwork, "Client network address"),
    'platform': (AICriteriaPlatform, "Client platform")
}


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
    """ Print usage message and exit
    """
    sys.stderr.write(_("Usage:\n"
                       "    %s -s service_list -o destination"
                       " [-d debug_level] [-l] [-h]\n") %
                       os.path.basename(sys.argv[0]))
    sys.exit(1)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_image_version(fname):
    """Dscription: Retrieves the IMAGE_VERSION from the on line file.
       Parameters:
           fname - the filename that contains the version information

       Returns:
           '0.5' when no version file exists
           '1.0' when no IMAGE_VERSION within the file
           the string value of IMAGE_VERSION from the file
	"""
    try:
        with open(fname, 'r') as fh:
            data = fh.read()
    except IOError:
        # No version file, thus prior to the protocol change version was 0.5
        return '0.5'

    # find the value for the IMAGE_VERSION variable
    for line in data.splitlines():
        key, match, value = line.partition("=")
        if match and key == "IMAGE_VERSION":
            return value

    AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                  "IMAGE_VERSION not found in the version file")
    return None


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_get_http_file(address, service_name, file_path, method, nv_pairs):
    """		Description: Downloads file from url using HTTP protocol

        Parameters:
            address      - address of webserver to connect
            service_name - requested service name, might be None
            file_path    - path to file
            method       - 'POST' or 'GET'
            nv_pairs     - dictionary containing name-value pairs to be sent
                           to the server using 'POST' method

        Returns:
            file
            return code: >= 100 - HTTP Response status code
                             -1 - Connection to web server failed
    """

    # try to connect to the provided web server
    http_conn = httplib.HTTPConnection(address)

    # turn on debug mode in order to track HTTP connection
    # http_conn.set_debuglevel(1)
    try:
        if (method == "POST"):
            post_data = ""
            for key in nv_pairs.keys():
                post_data += "%s=%s;" % (key, nv_pairs[key])
            # remove trailing ';'
            post_data = post_data.rstrip(';')
            if service_name:
                version = get_image_version(VERSION_FILE)
                if not version:
                    return None, -1

                params = urllib.urlencode({'version': version,
                                           'service': service_name,
                                           'postData': post_data})
            else:
                # compatibility mode only needs to send the data
                params = urllib.urlencode({'postData': post_data})

            AIGM_LOG.post(AILog.AI_DBGLVL_INFO, "%s", params)

            http_headers = {"Content-Type": "application/x-www-form-urlencoded",
                            "Accept": "text/plain"}
            http_conn.request("POST", file_path, params, http_headers)
        else:
            http_conn.request("GET", file_path)

    except httplib.InvalidURL:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "%s is not valid URL", address)
        return None, -1
    except StandardError, err:
        msg = "Connection to %s failed (%s)" % (address, err)
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "%s", msg)
        return None, -1

    http_response = http_conn.getresponse()
    url_content = http_response.read()
    http_status = http_response.status
    http_conn.close()

    return url_content, http_status


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_get_requested_criteria_list(xml_file):
    """ Description:
            List of requested criteria is extracted from given the XML file

            If the format of the XML file is validated, then the information
            is extracted without using an XML parser.  This is just an interim
            solution.

            todo: Switch to DC XML validator - bug 12494

            The format of the criteria file before the protocol change is as
            follows: 

                <CriteriaList>
                    <Version Number="0.5">
                    <Criteria Name="MEM">
                    <Criteria Name="arch">
                    ...
                </CriteriaList>

        Parameters:
            xml_file - XML file with criteria

        Returns:
            list of criteria
    """

    # '\n' is removed in order to safely use re module
    crit_required = xml_file.replace('\n', '').split("<Criteria Name=\"")[1:]

    # Extract criteria names
    for i in range(len(crit_required)):
        crit_required[i] = re.sub(r"\"/>.*$", "", crit_required[i])
        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      "Required criteria %d: %s", i + 1, crit_required[i])

    return crit_required


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_do_compatibility(service_name, known_criteria):
    """	Description: retrieve the manifest via compatibility mechanisms

        Parameters:
            service_name   - requested service name
            known_criteria - the known criteria for the system.

        Returns:
            the retrieved manifest
            return code: 0 - Success, -1 - Failure
    """
    xml_criteria, ret = ai_get_http_file(service_name, None,
                                         "/manifest.xml", "GET", None)
    if ret != httplib.OK:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Could not obtain criteria list from %s, ret=%d",
                      service_name, ret)
        return None, ret

    # extract the required criteria list
    criteria_required = ai_get_requested_criteria_list(xml_criteria)

    # Fill in dictionary with criteria name-value pairs
    AIGM_LOG.post(AILog.AI_DBGLVL_INFO, "List of criteria to be sent:")

    ai_crit_response = {}
    for criteria in criteria_required:
        if known_criteria.get(criteria, None):
            ai_crit_response[criteria] = known_criteria[criteria] 
            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          " %s=%s", criteria, ai_crit_response[criteria])

    # Send back filled in list of criteria to server
    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Sending list of criteria, asking for manifest:")
    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  " HTTP POST %s %s", ai_crit_response, service_name)

    ai_manifest, ret = ai_get_http_file(service_name, None,
                                        "/manifest.xml", 'POST',
                                        ai_crit_response)

    return ai_manifest, ret


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_cli(cli_opts_args):
    """ main application
    """

    if len(cli_opts_args) == 0:
        usage()

    opts_args = cli_opts_args[1:]

    try:
        opts = getopt.getopt(opts_args, "s:o:d:lh")[0]
    except getopt.GetoptError:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Invalid options or arguments provided")
        usage()

    service_list = "/tmp/service_list"
    manifest_file = "/tmp/manifest.xml"
    list_criteria_only = False

    for option, argument in opts:
        if option == "-s":
            service_list = argument
        elif option == "-o":
            manifest_file = argument
        elif option == "-d":
            AIGM_LOG.set_debug_level(int(argument))
        elif option == "-l":
            list_criteria_only = True
        elif option == "-h":
            usage()

    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Service list: %s", service_list)

    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Manifest file: " + manifest_file)

    ai_criteria_known = {}

    # Obtain all available information about client
    for key in AI_CRITERIA_SUPPORTED.keys():
        ai_crit = AI_CRITERIA_SUPPORTED[key][0]()
        if ai_crit.is_known():
            ai_criteria_known[key] = ai_crit.get()

    # List all criteria which client can understand and provide
    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Client can supply following criteria")
    for key in ai_criteria_known.keys():
        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      " %s=%s, '%s'", key, ai_criteria_known[key],
                      AI_CRITERIA_SUPPORTED[key][1])

    # if "-l" option was provided, list known criteria and exit
    if list_criteria_only:
        print "Client can supply the following criteria"
        print "----------------------------------------"
        index = 0
        for key in ai_criteria_known.keys():
            index += 1
            print " [%d] %s=%s (%s)" % (index, key,
                                        ai_criteria_known[key],
                                        AI_CRITERIA_SUPPORTED[key][1])
        return 0

    #
    # Go through the list of services.
    # Contact each of them and try to obtain valid manifest.
    #

    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Starting to contact AI services provided by %s",
                  service_list)

    ai_manifest_obtained = False
    try:
        service_list_fh = open(service_list, 'r')
    except IOError:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Could not open %s file", service_list)
        return 2

    for ai_service in service_list_fh.readlines():
        service = ai_service.strip()
        (ai_service, ai_port, ai_name) = service.split(':')
        ai_service += ':' + str(ai_port)
        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      "AI service: %s", ai_service)
        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      "AI service name: %s", ai_name)

        AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                      " HTTP POST cgi-bin/cgi_get_manifest.py?service=%s",
                      ai_service)

        ai_manifest, ret = ai_get_http_file(ai_service, ai_name,
                                            "/cgi-bin/cgi_get_manifest.py",
                                            'POST', ai_criteria_known)

        #
        # If valid manifest was provided, it is not necessary
        # to connect next AI service,
        #
        if ret == httplib.OK:
            AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                          "%s AI service provided valid manifest",
                          ai_service)
            ai_manifest_obtained = True
            break
        else:
            AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                          "%s AI service did not provide a valid manifest, " \
                          "ret=%d", ai_service, ret)
            AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                          "Checking compatibility mechanism.")
            ai_manifest, ret = ai_do_compatibility(ai_service, 
                                                   ai_criteria_known)

            if ret == httplib.OK:
                AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                              "Compatibility mechanism provided a valid " \
                              "manifest.")
                ai_manifest_obtained = True
                break
            else:
                AIGM_LOG.post(AILog.AI_DBGLVL_WARN,
                              "Compatibility mechanism did not provide valid" \
                              " manifest, ret=%d", ret)

    service_list_fh.close()

    if not ai_manifest_obtained:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "None of contacted AI services provided valid manifest")
        return 2

    # Save the manifest
    AIGM_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Saving manifest to %s", manifest_file)

    try:
        fh_manifest = open(manifest_file, 'w')
    except IOError:
        AIGM_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Could not open %s for saving obtained manifest",
                      manifest_file)
        return 2

    fh_manifest.write(ai_manifest)
    fh_manifest.close()

    return 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
    """ main program
    """
    return(parse_cli(sys.argv))


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    gettext.install("ai", "/usr/lib/locale")
    try:
        RET_CODE = main()
    except StandardError:
        traceback.print_exc()
        sys.exit(99)
    sys.exit(RET_CODE)
