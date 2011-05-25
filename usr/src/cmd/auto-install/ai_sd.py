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
# Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
#
# ai_sd - AI Service Discovery Engine
#
""" AI Service Discovery Engine
"""

import sys

import getopt
import gettext
import traceback
from solaris_install import system_temp_path
from solaris_install.auto_install.ai_get_manifest import AILog
import osol_install.auto_install.aimdns_mod as aimdns
from osol_install.auto_install.installadm_common import REGTYPE

#
# AI service discovery logging service
#
AISD_LOG = AILog("AISD")


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class AIService:
    """ Class: AIService - base class for holding/manipulating AI service
    """

    # service type
    type = '_OSInstall._tcp'

    def __init__(self, name="_default", timeout=5, domain="local"):
        """ Method:    __init__

            Parameters:
                name - name of the service instance
                timeout - max time to lookup the service
                domain - .local for multicast DNS

            Returns:
                True..service found, False..service not found
        """
        self.name = name
        self.domain = domain
        self.found = False
        self.svc_info = self.svc_txt_rec = None
        self.mdns = aimdns.AImDNS()
        self.mdns.timeout = timeout

        return

    def get_found(self):
        """    Returns:
                True..service found, False..service not found
        """
        return self.found

    def get_txt_rec(self):
        """ Method:    get_txt_rec

            Returns:
                Service TXT record
        """
        return self.svc_txt_rec

    def lookup(self):
        """ Method:    lookup

            Description:
                Tries to look up service instance

            Returns:
                0..service found, -1..service not found
        """
        self.found = self.mdns.find(servicename=self.name)

        if self.found:
            # Use only the first interface within the services list.
            # This should be fine as the clients only bring up a single
            # interface.
            interface = self.mdns.services.keys()[0]

            # Find will have exactly 1 service.
            service = self.mdns.services[interface][0]
            svc_txt_rec = service['comments']
            svc_info = service['servicename'] + '.' + REGTYPE + '.' + \
                       service['domain'] + ':' + \
                       str(service['port'])

            AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Valid service found:\n\tsvc: %s\n\tTXT: %s",
                          svc_info, svc_txt_rec)

            self.svc_info = svc_info
            self.svc_txt_rec = svc_txt_rec
            return 0

        return -1


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
    """ Description: Print usage message and exit
    """
    print >> sys.stderr, ("Usage:\n"
                          "    ai_sd -s service type -n service_name"
                          " -o discovered_services_file -t timeout"
                          " [-d debug_level] [-h]")
    sys.exit(1)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_cli(cli_opts_args):
    """ Description:
            Main function - parses command line arguments and
                            carries out service discovery

            Parameters:
                cli_opts_args - command line arguments

            Returns:
                0 - service discovery succeeded
                2 - service discovery failed
    """
    if len(cli_opts_args) == 0:
        usage()

    opts_args = cli_opts_args[1:]

    try:
        opts = getopt.getopt(opts_args, "t:s:n:o:d:h")[0]
    except getopt.GetoptError:
        AISD_LOG.post(AILog.AI_DBGLVL_ERR,
                      "Invalid options or arguments provided")
        usage()

    service_name = ""
    service_lookup_timeout = 5

    service_file = system_temp_path("service_list")

    for option, argument in opts:
        if option == "-s":
            AIService.type = argument
        if option == "-n":
            service_name = argument
        elif option == "-o":
            service_file = argument
        elif option == "-t":
            service_lookup_timeout = int(argument)
        elif option == "-d":
            AISD_LOG.set_debug_level(int(argument))
        elif option == "-h":
            usage()

    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Service file: %s", service_file)

    service_list = []

    #
    # if service name was specified, add it to the list
    # of services to be looked up
    #
    if service_name:
        service_list.append(AIService(service_name,
                            service_lookup_timeout))

    # add default service
    service_list.append(AIService('_default', service_lookup_timeout))

    # Go through the list of services and try to look up them
    for i in range(len(service_list)):
        svc_instance = "%s.%s.%s" % (service_list[i].name,
                                     AIService.type, service_list[i].domain)

        AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                      "Service to look up: %s", svc_instance)

        # look up the service
        ret = service_list[i].lookup()
        if ret == 0:
            svc_found_index = i
            break

    if ret == -1:
        AISD_LOG.post(AILog.AI_DBGLVL_ERR,
                      "No valid AI service found")
        return 2

    #
    # parse information captured from dns-sd in order
    # to obtain source of service (address and port)
    # extract value from 'aiwebserver' name-value pair
    #
    svc_address = service_list[svc_found_index].get_txt_rec()
    svc_name = service_list[svc_found_index].name
    svc_address = svc_address.strip().split('aiwebserver=', 1)[1]
    svc_address = svc_address.split(',')[0]
    (svc_address, svc_port) = svc_address.split(':')

    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                  "%s can be reached at: %s:%s", svc_instance,
                  svc_address, svc_port)

    # write the information to the given location
    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                  "Storing service list into %s", service_file)

    try:
        fh_svc_list = open(service_file, 'w')
    except IOError:
        AISD_LOG.post(AILog.AI_DBGLVL_ERR,
                    "Could not open %s for saving service list", service_file)
        return 2

    fh_svc_list.write("%s:%s:%s\n" % (svc_address, svc_port, svc_name))
    fh_svc_list.close()

    return 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    gettext.install("ai", "/usr/lib/locale")
    try:
        RET_CODE = parse_cli(sys.argv)
    except StandardError:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(RET_CODE)
