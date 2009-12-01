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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# ai_sd - AI Service Discovery Engine
#
""" AI Service Discovery Engine
"""

import sys

import getopt
import os
import re
import signal
from subprocess import Popen, PIPE
import traceback
from osol_install.auto_install.ai_get_manifest import AILog

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
        """ Metod:    __init__

		    Parameters:
		        name - name of the service instance
			timeout - max time to lookup the service
			domain - .local for multicast DNS

		    Returns:
		        True..service found, False..service not found

		"""
        self.name = name
        self.timeout = timeout
        self.domain = domain
        self.found = False
        self.svc_info = self.svc_txt_rec = None

        #
        # ID of process running dns-sd(1M) command. It will be used by
        # os.kill() to terminate the process.
        #

        self.pid = -1

        #
        # Flag which indicates that timer expired for running dns-sd(1M)
        #

        self.timeout_expired = False

        return
	
    def _svc_lookup_timeout_handler(self, signum, frame):
        """     Description:
		    Handles raising of SIGALRM signal - kill the process
		    with ID saved in SD_PID by sending SIGTERM signal

		    Parameters:
		        signum - number of signal
			frame - current stack frame

		    Returns:
        """

        if self.pid >= 0:
            os.kill(self.pid, signal.SIGTERM)

        # set the flag and disable the alarm
        self.timeout_expired = True
        signal.alarm(0)

    def get_found(self):
        """    Returns:
		        True..service found, False..service not found

		"""
        return self.found

    def get_txt_rec(self):
        """ Metod:    get_txt_rec

		    Returns:
		        Service TXT record

		"""
        return self.svc_txt_rec

    def lookup(self):
        """ Metod:    lookup

		    Description:
		        Tries to look up service instance

		    Returns:
		        0..service found, -1..service not found

	"""

        #
        # discard the information we obtained so far
        # and start new look up process
        #
        self.svc_info = self.svc_txt_rec = None
        self.found = False

        # dns-sd(1M) is used for look up the service
        cmd = "/usr/bin/dns-sd -L %s %s %s" % (self.name,
                                               self.__class__.type,
                                               self.domain)

        AISD_LOG.post(AILog.AI_DBGLVL_INFO, "cmd: %s", cmd)

        cmd_args = cmd.split()

        #
        # spawn new process which will take care of looking up
        # the service. If the service is not found within specified
        # time, raise the SIGALRM signal and kill the process
        #
        try:
            cmd_popen = Popen(cmd_args, stdout=PIPE, stderr=PIPE)

        except OSError:
            AISD_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Popen() raised OSError exception")

            return -1

        except ValueError:
            AISD_LOG.post(AILog.AI_DBGLVL_ERR,
                          "Popen() raised ValueError exception")

            return -1

        #
        # save ID of new process - os.kill() will use it later
        # to terminate the process
        #
        self.pid = cmd_popen.pid
        AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                      "dns-sd pid: %d", self.pid)
	
        signal.signal(signal.SIGALRM, self._svc_lookup_timeout_handler)

        # activate timeout
        self.timeout_expired = False
        signal.alarm(self.timeout)

        #
        # Save file descriptors for stdout, stderr
        # from dns-sd for later purposes
        #
        cmd_stdout_fd = cmd_popen.stdout
        cmd_stderr = None

        svc_info = svc_txt_rec = None
        svc_info_found = svc_txt_rec_found = False

        #
        # process output from dns-sd(1M) until either service
        # is found or timeout expires
        #
        while cmd_popen.poll() is None and not self.timeout_expired:
            try:
                # read main service info - wait for the line
                # containing service name
                line = cmd_stdout_fd.readline().strip()

                # search for exact match of given service name
                svc = line.split()
                if len(svc) > 1 and re.search("^%s." % self.name,
                                              svc[1].strip()):

                    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                                  " Svc: %s", line)

                    svc_info_found = True
                    svc_info = line
                    svc_txt_rec_found = False
                    continue

                #
                # read and verify TXT records -
                # following format is expected:
                #
                # aiwebserver=<address>:<port>
                #
                if re.search(r"^aiwebserver=", line):
                    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                                  " TXT: %s", line)
                    svc_txt_rec = line
                    svc_txt_rec_found = True
                else:
                    svc_info_found = \
                        svc_txt_rec_found = False

                #
                # Abort look up process, if service was found
                #

                if svc_info_found and svc_txt_rec_found:
                    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                                  " %s service found", self.name)
                    break

            #
            # IOError exception is raised when the process
            # is terminated during I/O operation. This will
            # happen if service can't be found, since in this case
            # we would be waiting in cmd_stdout_fd.readline()
            #
            except IOError:
                # wait for process to finish
                cmd_stderr = cmd_popen.communicate()[1]

                if self.timeout_expired:
                    AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                                  "Timeout expired, dns-sd (pid=%d)" \
                                  " terminated", self.pid)

                else:
                    AISD_LOG.post(AILog.AI_DBGLVL_WARN,
                                  "IOError raised for unknown reason")

        # disable alarm
        signal.alarm(0)

        #
        # if the process didn't finish yet, it is either
        # still running or in the phase of finishing its job.
        #
        if cmd_popen.poll() is None:
            # If process is running, terminate it
            if not self.timeout_expired:
                AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                              "dns-sd (pid=%d) is running, will be " \
                              "terminated", self.pid)

                os.kill(self.pid, signal.SIGTERM)

        if cmd_popen.poll() is not None:
            AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                          "dns-sd return code: %d", cmd_popen.returncode)

        # capture output of stderr for debugging purposes
        if cmd_stderr:
            AISD_LOG.post(AILog.AI_DBGLVL_WARN,
                          " stderr: %s", cmd_stderr)

        if svc_info_found and svc_txt_rec_found:
            AISD_LOG.post(AILog.AI_DBGLVL_INFO,
                          "Valid service found:\n svc: %s\n TXT: %s",
                          svc_info, svc_txt_rec)

            self.found = True
            self.svc_info = svc_info
            self.svc_txt_rec = svc_txt_rec
            return 0

        return -1

	
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
    """         Description: Print usage message and exit
    """
    print >> sys.stderr, ("Usage:\n"
                          "    ai_sd -s service type -n service_name"
                          " -o discovered_services_file -t timeout"
                          " [-d debug_level] [-h]")
    sys.exit(1)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_cli(cli_opts_args):
    """	        Description:
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
	
    service_file = "/tmp/service_list"

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
                      "Couldn't open %s for saving service list", service_file)
        return 2

    fh_svc_list.write("%s:%s\n" % (svc_address, svc_port))
    fh_svc_list.close()

    return 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    try:
        RET_CODE = parse_cli(sys.argv)
    except StandardError:
        traceback.print_exc()
        sys.exit(1)
    sys.exit(RET_CODE)
