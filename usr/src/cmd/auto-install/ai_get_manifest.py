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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# ai_get_manifest - AI Service Choosing Engine
#

import gettext
import shutil
import traceback
import datetime
import random

import string
import os
import sys
import getopt
import mimetools
import re
import time
import httplib, urllib
import socket
from subprocess import *

#
# ai_log class - provides logging capabilities for
# AI service choosing and AI service discovery engines
#
class ai_log:
	# list of implemented logging levels
	AI_DBGLVL_NONE = 0
	AI_DBGLVL_EMERG = 1
	AI_DBGLVL_ERR = 2
	AI_DBGLVL_WARN = 3
	AI_DBGLVL_INFO = 4

	def __init__(self, logid = "AI", logfile = "/tmp/ai_sd_log", \
	    debuglevel = AI_DBGLVL_WARN):
		self.log_file = logfile
		self.logid = logid
		self.dbg_lvl_current = debuglevel
		self.fh_log = None

		# list of prefixes displayed for particular logging levels
		self.log_prefix = {ai_log.AI_DBGLVL_EMERG : "!", \
		    ai_log.AI_DBGLVL_ERR : "E",  ai_log.AI_DBGLVL_WARN : "W", \
		    ai_log.AI_DBGLVL_INFO : "I"}
		
		# default logging level
		self.dbg_lvl_default = ai_log.AI_DBGLVL_INFO

		# if provided, open log file in append mode
		if self.log_file != None:
			try:
				self.fh_log = open(self.log_file, "a+");
			except IOError:
				self.fh_log = None

	#
	# Set default logging level
	# level - new logging level
	#
	def set_debug_level(self, level):
		if self.log_prefix.has_key(level):
			self.dbg_lvl_current = level

	#
	# Post logging message
	# level - logging level
	# msg - message to be logged
	# msg_args - message parameters
	#
	def post(self, level, msg_format, *msg_args):
		if not self.log_prefix.has_key(level):
			return

		if level > self.dbg_lvl_current:
			return
		
		timestamp = time.strftime("%m/%d %H:%M:%S", time.gmtime())

		log_msg = "<%s_%s %s> " % (self.logid, self.log_prefix[level], \
		    timestamp)

		if len(msg_args) == 0:
			log_msg += msg_format
		else:
			log_msg += msg_format % msg_args

		# post message to console
		print log_msg

		# post message to file
		if self.fh_log != None:
			self.fh_log.write(log_msg + '\n')

		return

#
# AI service choosing logging service
#
aigm_log = ai_log("AISC")


#
# ai_criteria class - base class for holding/manipulating AI criteria
#
class ai_criteria:
	def __init__(self, criteria = None):
		self.criteria = criteria

	# return criteria value
	def get(self):
		return self.criteria

	# check, if information requried by criteria is available
	def is_known(self):
		return self.criteria != None

#
# ai_criteria_hostname class - class for obtaining/manipulating 'hostname'
# criteria
#
class ai_criteria_hostname(ai_criteria):
	def __init__(self):
		ai_criteria.__init__(self, socket.gethostname())

#
# ai_criteria_arch class - class for obtaining/manipulating 'architecture'
# criteria
#
class ai_criteria_arch(ai_criteria):
	client_arch = None
	client_arch_initialized = False
	def __init__(self):
		if ai_criteria_arch.client_arch_initialized:
			ai_criteria.__init__(self, ai_criteria_arch.client_arch)
			return

		ai_criteria_arch.client_arch_initialized = True
		cmd = "/usr/bin/uname -m"
		client_arch, ret = ai_exec_cmd(cmd)
	
		if ret != 0 or client_arch == "":
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain machine architecture")
			ai_criteria_arch.client_arch = None
		else:
			ai_criteria_arch.client_arch = client_arch.strip()

		ai_criteria.__init__(self, ai_criteria_arch.client_arch)

#
# ai_criteria_platform class - class for obtaining/manipulating 'platform'
# criteria
#
class ai_criteria_platform(ai_criteria):
	client_platform = None
	client_platform_initialized = False
	def __init__(self):
		if ai_criteria_platform.client_platform_initialized:
			ai_criteria.__init__(self, \
			    ai_criteria_platform.client_platform)
			return

		ai_criteria_platform.client_platform_initialized = True
		cmd = "/usr/bin/uname -i"
		ai_criteria_platform.client_platform, ret = ai_exec_cmd(cmd)
	
		if ret != 0 or ai_criteria_platform.client_platform == "":
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain machine platform")
		else:
			ai_criteria_platform.client_platform = \
			    ai_criteria_platform.client_platform.strip()

		ai_criteria.__init__(self, ai_criteria_platform.client_platform)

#
# ai_criteria_cpu class - class for obtaining/manipulating 'processor type'
# criteria
#
class ai_criteria_cpu(ai_criteria):
	client_cpu = None
	client_cpu_initialized = False
	def __init__(self):
		if ai_criteria_cpu.client_cpu_initialized:
			ai_criteria.__init__(self, ai_criteria_cpu.client_cpu)
			return

		ai_criteria_cpu.client_cpu_initialized = True
		cmd = "/usr/bin/uname -p"
		ai_criteria_cpu.client_cpu, ret = ai_exec_cmd(cmd)
	
		if ret != 0 or ai_criteria_cpu.client_cpu == "":
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain processor type")
		else:
			ai_criteria_cpu.client_cpu = \
			    ai_criteria_cpu.client_cpu.strip()

		ai_criteria.__init__(self, ai_criteria_cpu.client_cpu)

#
# ai_criteria_mem_size class - class for obtaining/manipulating
# 'physical memory size' criteria, value is in MB
#
class ai_criteria_mem_size(ai_criteria):
	client_mem_size = None
	client_mem_size_initialized = False

	def __init__(self):
		if ai_criteria_mem_size.client_mem_size_initialized:
			ai_criteria.__init__(self, \
			    ai_criteria_mem_size.client_mem_size)
			return
		
		ai_criteria_mem_size.client_mem_size_initialized = True
		cmd = "/usr/sbin/prtconf -vp | /usr/bin/grep '^Memory size: '"
		client_mem_info, ret = ai_exec_cmd(cmd)

		if ret != 0 or client_mem_info == "":
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain memory size")
			ai_criteria_mem_size.client_mem_size = None
			ai_criteria.__init__(self)
			return

		(client_mem_size, client_mem_unit) = client_mem_info.split()[2:]
		client_mem_size = long(client_mem_size)
	
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "prtconf(1M) reported: %ld %s", client_mem_size, \
		    client_mem_unit)

		if client_mem_size == 0 or client_mem_unit == "":
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain memory size")
			ai_criteria_mem_size.client_mem_size = None
			ai_criteria.__init__(self)
			return

		if client_mem_unit == "Kilobytes":
			client_mem_size /= 1024
		elif client_mem_unit == "Gigabytes":
			client_mem_size *= 1024
		elif client_mem_unit == "Terabytes":
			client_mem_size *= 1024 * 1024
		elif client_mem_unit != "Megabytes":
			aigm_log.post(ai_log.AI_DBGLVL_WARN, \
			    "Unknown mem size units %s", client_mem_unit)
			client_mem_size = 0

		ai_criteria_mem_size.client_mem_size = \
		    `client_mem_size`.rstrip('L')

		ai_criteria.__init__(self, ai_criteria_mem_size.client_mem_size)

#
# ai_criteria_network_iface class - class for obtaining/manipulating
# information about network interface - this criteria is currently
# private and not exposed to the server
#
class ai_criteria_network_iface(ai_criteria):
	network_iface = None
	ifconfig_iface_info = None
	network_iface_initialized = False

	def __init__(self):
		ai_criteria.__init__(self)

		# initialize class variables only once
		if ai_criteria_network_iface.network_iface_initialized:
			return

		ai_criteria_network_iface.network_iface_initialized = True
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
		ai_criteria_network_iface.network_iface, ret = ai_exec_cmd(cmd)

		if ret != 0:
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain name of valid network interface")
			ai_criteria_network_iface.network_iface = None
		else:
			ai_criteria_network_iface.network_iface = \
			    ai_criteria_network_iface.network_iface. \
			    split(':')[0]

			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "Network interface obtained: %s", \
			    ai_criteria_network_iface.network_iface)

			#
			# Collect all available information about network interface
			#
			cmd = "/usr/sbin/ifconfig %s" % \
			    ai_criteria_network_iface.network_iface

			ai_criteria_network_iface.ifconfig_iface_info, ret = \
			    ai_exec_cmd(cmd)

			if ret != 0 or \
			    ai_criteria_network_iface.ifconfig_iface_info == "":
				aigm_log.post(ai_log.AI_DBGLVL_ERR, \
				    "Couldn't obtain information about "
				    "network interface %s", \
				    ai_criteria_network_iface.network_iface)
				
				ai_criteria_network_iface.\
				    ifconfig_iface_info = None

#
# ai_criteria_mac class - class for obtaining/manipulating
# information about client MAC address
#
class ai_criteria_mac(ai_criteria_network_iface):
	client_mac = None
	client_mac_initialized = False
		
	def __init__(self):
		ai_criteria_network_iface.__init__(self)

		# initialize class variables only once
		if ai_criteria_mac.client_mac_initialized:
			ai_criteria.__init__(self, ai_criteria_mac.client_mac)
			return

		ai_criteria_mac.client_mac_initialized = True

		if ai_criteria_network_iface.ifconfig_iface_info == None:
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain MAC address")
		else:
			ai_criteria_mac.client_mac = ai_criteria_network_iface.\
			    ifconfig_iface_info.split("ether", 1)

			if len(ai_criteria_mac.client_mac) < 2:
				aigm_log.post(ai_log.AI_DBGLVL_ERR, \
				    "Couldn't obtain client MAC address")
				ai_criteria_mac.client_mac = None
			else:
				ai_criteria_mac.client_mac = ai_criteria_mac.\
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
				    ai_criteria_mac.client_mac.split(":")

				ai_criteria_mac.client_mac = "%s%s%s%s%s%s" % \
				    (string.zfill(client_mac_parts[0], 2), \
				    string.zfill(client_mac_parts[1], 2), \
				    string.zfill(client_mac_parts[2], 2), \
				    string.zfill(client_mac_parts[3], 2), \
				    string.zfill(client_mac_parts[4], 2), \
				    string.zfill(client_mac_parts[5], 2))

				aigm_log.post(ai_log.AI_DBGLVL_INFO, \
				    "Client MAC address: %s", \
				    ai_criteria_mac.client_mac)

		ai_criteria.__init__(self, ai_criteria_mac.client_mac)


#
# ai_criteria_ip class - class for obtaining/manipulating
# information about client IP address
#
class ai_criteria_ip(ai_criteria_network_iface):
	client_ip = None
	client_ip_string = None
	client_ip_initialized = False

	def __init__(self):
		ai_criteria_network_iface.__init__(self)

		# initialize class variables only once
		if ai_criteria_ip.client_ip_initialized:
			ai_criteria.__init__(self, ai_criteria_ip.client_ip_string)
			return

		ai_criteria_ip.client_ip_initialized = True
		if ai_criteria_network_iface.ifconfig_iface_info == None:
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain IP address")
		else:
			ai_criteria_ip.client_ip = ai_criteria_network_iface.\
			    ifconfig_iface_info.split("inet", 1)[1].strip().\
			    split()[0].strip()

			# remove '.'
			ip_split = ai_criteria_ip.client_ip.split('.')
			ai_criteria_ip.client_ip_string = "%03d%03d%03d%03d" % \
			    (int(ip_split[0]), int(ip_split[1]), \
			    int(ip_split[2]), int(ip_split[3]))

			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "Client IP address: %s", \
			    ai_criteria_ip.client_ip_string)

		ai_criteria.__init__(self, ai_criteria_ip.client_ip_string)

#
# ai_criteria_network class - class for obtaining/manipulating
# information about client network address
#
class ai_criteria_network(ai_criteria_ip):
	client_net = None;
	client_net_initialized = False

	def __init__(self):
		ai_criteria_ip.__init__(self)

		# initialize class variables only once
		if ai_criteria_network.client_net_initialized:
			ai_criteria.__init__(self, ai_criteria_network.\
			    client_net)
			return

		ai_criteria_network.client_net_initialized = True
			
		if ai_criteria_network_iface.ifconfig_iface_info == None or \
		    ai_criteria_ip.client_ip == None:
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain network address")
		else:
			# extract network mask
			client_netmask = string.atol( \
			    ai_criteria_network_iface.ifconfig_iface_info. \
			    split("netmask", 1)[1].strip().split()[0].strip(), \
			    16)

			# Translate IP address in string format to long
			ip_part = ai_criteria_ip.client_ip.split('.')
			ip_long = long(ip_part[0]) << 24 | long(ip_part[1]) << \
			    16 | long(ip_part[2]) << 8 | long(ip_part[3])

			client_network_long = ip_long & client_netmask
	
			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "Mask: %08lX, IP: %08lX, Network: %08lX", \
			    client_netmask, ip_long, client_network_long)

			ai_criteria_network.client_net = \
			    "%03ld%03ld%03ld%03ld" % \
			    (client_network_long >> 24,
			    client_network_long >> 16 & 0xff,
			    client_network_long >> 8 & 0xff,
			    client_network_long & 0xff)

			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "Client net: %s", ai_criteria_network.client_net)

		ai_criteria.__init__(self, ai_criteria_network.client_net)

#
# dictionary defining list of supported criteria and relationship
# between AI criteria and appropriate class which serves for obtaining
# and manipulating that criteria
#
# It also contains short informative description of the criteria
#
# Use following steps if support for new criteria is required:
# [1] Define name of criteria (like 'MEM'), create new class
#     which inherits ai_criteria and implements method for
#     obtaining the criteria.
# [2] Add name of criteria, class and short description in following
#     dictionary
# [3] Test ;-)
#
ai_criteria_supported = {
    'MEM'      : (ai_criteria_mem_size, "Physical memory size"),
    'arch'     : (ai_criteria_arch,     "Client machine architecture"),
    'cpu'      : (ai_criteria_cpu,      "Client processor type"),
    'platform' : (ai_criteria_platform, "Client platform"),
    'Hostname' : (ai_criteria_hostname, "Client hostname"),
    'Ip'       : (ai_criteria_ip,       "Client IP address"),
    'Network'  : (ai_criteria_network,  "Client network address"),
    'MAC'      : (ai_criteria_mac,      "Client MAC address")}
	
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def usage():
	print >> sys.stderr, ("Usage:\n" \
	    "    ai_get_manifest -s service_list -o destination " \
	    "[-d debug_level] [-l] [-h]")
	sys.exit(1)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_exec_cmd(cmd):
	""" Function:    ai_exec_cmd

	    Description: Executes provided command using subprocess.Popen()
	                 method and captures its stdout & stderr.
			 stderr is captured for debugging purposes

	    Parameters:
		cmd - Command to be executed

	    Returns:
	        captured stdout from 'cmd'
		return code - 0..success, -1..failure
	"""

	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "cmd:" + cmd)

	try:
		cmd_popen = Popen(cmd, shell=True, stdout=PIPE)
		(cmd_stdout, cmd_stderr) = cmd_popen.communicate()
		
	except OSError:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Popen() raised OSError exception")

		return None, -1

	except ValueError:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Popen() raised ValueError exception")

		return None, -1

	# capture output of stderr for debugging purposes
	if cmd_stderr != None:
		aigm_log.post(ai_log.AI_DBGLVL_WARN, \
		    " stderr: %s", cmd_stderr)

	# check if child process terminated successfully
	if cmd_popen.returncode != 0:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Command failed: ret=%d", cmd_popen.returncode)
		
		return None, -1

	return cmd_stdout, 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_get_http_file(address, file, method, *nv_pairs):
	""" Function:    ai_get_http_file

		Description: Downloads file from url using HTTP protocol

		Parameters:
		    address - address of webserver to connect
		    file - path to file
		    method - 'POST' or 'GET'
		    nv_pairs - dictionary containing name-value pairs to be sent
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
			post_data = "postData="
			for key in nv_pairs[0].keys():
				post_data += "%s=%s;" % (key, nv_pairs[0][key])

			# remove trailing ';' and replace all ';' with "%3B",
			# so that the data is correctly passed to AI web server
			post_data = post_data.rstrip(';').replace(";", "%3B")

			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "%s", post_data)

			http_headers = {"Content-Type": \
			    "application/x-www-form-urlencoded"}

			http_conn.request("POST", file, post_data, http_headers)
		else:
			http_conn.request("GET", file)
	except:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Connection to %s refused", address)
		return None, -1

	http_response = http_conn.getresponse()
	url_content = http_response.read()
	http_status = http_response.status
	http_conn.close()

	return url_content, http_status


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ai_extract_requested_criteria_list(xml_file):
	""" Function:    ai_extract_requested_criteria_list

		Description: List of requested criteria is extracted from
		             given the XML file

		Parameters:
		    xml_file - XML file with criteria

		Returns:
		    list of criteria
		    return code: 0 - Success, -1 - Failure
	"""

	# '\n' is removed in order to safely use re module
	crit_required = xml_file.replace('\n', '').split("<Criteria Name=\"")[1:]

	# Extract criteria names
	for i in range(len(crit_required)):
		crit_required[i] = re.sub(r"\"/>.*$", "", crit_required[i])
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "Required criteria %d: %s", i + 1, crit_required[i])

	return crit_required, 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def parse_cli(cli_opts_args):
	rc = 0;

	if len(cli_opts_args) == 0:
		usage()
		
	opts_args = cli_opts_args[1:]

	try:
		opts, args  = getopt.getopt(opts_args, "s:o:d:lh")
	except getopt.GetoptError:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Invalid options or arguments provided")
		usage()

	service_list = "/tmp/service_list"
	manifest_file = "/tmp/manifest.xml"
	list_criteria_only = False

	for o, a in opts:
		if o == "-s":
			service_list = a
		elif o == "-o":
			manifest_file = a
		elif o == "-d":
			aigm_log.set_debug_level(int(a))
		elif o == "-l":
			list_criteria_only = True
		elif o == "-h":
			usage()

	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "Service list: %s", service_list)

	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "Manifest file: " + manifest_file)

	ai_criteria_known = {}

	# Obtain all available information about client
	for key in ai_criteria_supported.keys():
		ai_crit = ai_criteria_supported[key][0]()
		if ai_crit.is_known():
			ai_criteria_known[key] = ai_crit.get()

	# List all criteria which client can understand and provide
	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "Client can supply following criteria")
	for key in ai_criteria_known.keys():
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    " %s=%s, '%s'", key, ai_criteria_known[key], \
		    ai_criteria_supported[key][1])

	# if "-l" option was provided, list known criteria and exit
	if list_criteria_only:
		print "Client can supply following criteria"
		print "------------------------------------"
		index = 0
		for key in ai_criteria_known.keys():
			index += 1
			print " [%d] %s=%s (%s)" % (index, key, \
			    ai_criteria_known[key], \
			    ai_criteria_supported[key][1])
		return 0

	#
	# Go through the list of services.
	# Contact each of them and try to obtain valid manifest by
	# following handshake using HTTP protocol:
	# [1] Ask for list of criteria server is interested in
	#     GET <service>/manifest. xml
	# [2] Return criteria as a list of name,value pairs
	#     POST "postData=cr_name1=cr_value1;cr_name2=cr_value2"
	#     <service>/manifest.xml
	# [3] If valid manifest is not returned, continue with next
	#     service
	#

	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "Starting to contact AI services provided by %s", service_list)

	ai_manifest_obtained = False
	try:
		service_list_fh = open(service_list, 'r')
	except IOError:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Couldn't open %s file", service_list)
		return 2

	for ai_service in service_list_fh.readlines():
		ai_service = ai_service.strip()
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "AI service: %s", ai_service)

		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "Asking for criteria list:")
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    " HTTP GET %s/manifest.xml", ai_service)

		xml_criteria, ret = ai_get_http_file(ai_service, \
		    "/manifest.xml", "GET")

		if ret != httplib.OK:
			aigm_log.post(ai_log.AI_DBGLVL_ERR, \
			    "Couldn't obtain criteria list from %s, ret=%d", \
			    ai_service, ret)
			continue

		#
		# Extract list of required criteria from XML file provided
		# format of XML file is not validated, information is being
		# extracted in simple way. This is just interim solution
		# TODO: Switch to DC XML validator
		#
		# The format of file for November is following (it might become
		# more complex and will be docummented in design spec):
		#
		# <CriteriaList>
		#	<Version Number="0.5">
		# 	<Criteria Name="MEM">
		#	<Criteria Name="arch">
		# ...
		# </CriteriaList>
		#
		criteria_required, ret = \
		    ai_extract_requested_criteria_list(xml_criteria)

		# Fill in dictionary with criteria name-value pairs
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "List of criteria to be sent:")

		ai_crit_response = {}
		for i in range(len(criteria_required)):
			cr_key = criteria_required[i]
			if ai_criteria_known.has_key(cr_key) \
			    and ai_criteria_known[cr_key] != None:
				ai_crit_response[cr_key] = ai_criteria_known[cr_key]
				aigm_log.post(ai_log.AI_DBGLVL_INFO, \
				    " %s=%s", cr_key, ai_crit_response[cr_key])

		# Send back filled in list of criteria to server
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    "Sending list of criteria, asking for manifest:")
		aigm_log.post(ai_log.AI_DBGLVL_INFO, \
		    " HTTP POST %s %s", ai_crit_response, ai_service)

		ai_manifest, ret = ai_get_http_file(ai_service, \
		    "/manifest.xml", "POST", ai_crit_response)

		#
		# If valid manifest was provided, it is not necessary
		# to connect next AI service, 
		#
		if ret == httplib.OK:
			aigm_log.post(ai_log.AI_DBGLVL_INFO, \
			    "%s AI service provided valid manifest", \
			    ai_service)
			ai_manifest_obtained = True
			break
		else:
			aigm_log.post(ai_log.AI_DBGLVL_WARN, \
			    "%s AI service didn't provide valid manifest, " \
			    "ret=%d", ai_service, ret)

	service_list_fh.close()

	if not ai_manifest_obtained:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "None of contacted AI services provided valid manifest")
		return 2

	# Save the manifest
	aigm_log.post(ai_log.AI_DBGLVL_INFO, \
	    "Saving manifest to %s", manifest_file)

	try:
		fh_manifest = open(manifest_file, 'w')
	except IOError:
		aigm_log.post(ai_log.AI_DBGLVL_ERR, \
		    "Couldn't open %s for saving obtained manifest", \
		    manifest_file)
		return 2

	fh_manifest.write(ai_manifest)
	fh_manifest.close()

	return 0


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main():
	return(parse_cli(sys.argv))


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
	try:
		rc = main()
	except SystemExit, e:
		raise e
	except:
		traceback.print_exc()
		sys.exit(99)
	sys.exit(rc)
