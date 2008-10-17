#!/usr/bin/python2.4
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
"""

A/I Webserver Prototype

"""

import os
import sys
import re

sys.path.append("/usr/lib/python2.4/vendor-packages/osol_install/auto_install")
import AI_database as AIdb

from optparse import OptionParser
from pysqlite2 import dbapi2 as sqlite
import cherrypy
from cherrypy.lib.static import serve_file

def parseOptions():
	"""
	Parse and validate options
	"""

	usage = "usage: %prog [options] A/I_data_directory"
	parser = OptionParser(usage=usage, version="%prog 0.5")
	parser.add_option("-p", "--port", dest="port", default=8080,
							metavar="port", type="int", nargs=1,
							help="provide port to start server on")
	parser.add_option("-t", "--threads", dest="thread", default=10,
							metavar="thread count", type="int", nargs=1,
							help="provide the number of threads to run")
	parser.add_option("-l", "--listen", dest="listen", default="0.0.0.0",
							metavar="ipaddress", type="string", nargs=1,
							help="provide the interface to listen on")
	parser.add_option("-d", "--debug", dest="debug", default=False,
							action="store_true",
							help="provide server tracebacks")

	(options, args) = parser.parse_args()
	# check to see the listen directive is a valid IPv4 or IPv6 address
	if options.listen and not (
	    re.search("^\d{1,3}(\.\d{1,3}){3}$", options.listen) or
	    re.search("^[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){1,7}$", options.listen)):
		parser.print_help()
		sys.exit(1)
	elif len(args) != 1:
		parser.print_help()
		sys.exit(1)

	return (options, args[0])

class StaticPages:
	"""
	Class containing the HTML for the static pages
	"""

	def __init__(self, dataLocation):
		self.baseDir = dataLocation
		if os.path.exists(os.path.join(self.baseDir, 'AI.db')):
			self.AISQL = AIdb.DB(os.path.join(self.baseDir, 'AI.db'))
		else:
			raise SystemExit("Error:\tNo AI.db database")
		self.AISQL.verifyDBStructure()

	@cherrypy.expose
	def index(self):
		""" The server's main page """
		response = """
				<html><body>
					<h1>Welcome to the Solaris A/I prototype webserver!</h1>
					<p>This server has the following manifests available, 
						served to clients matching required criteria.</p>
					<table border=1 align=center>
						<tr>
							<th rowspan=2>Number</th>
							<th rowspan=2>Manifest</th>
							<th colspan=%s>Criteria List</th>
						</tr>
						<tr>
		    """ % max(len(list(AIdb.getCriteria(self.AISQL.getQueue(),
		    strip = False))), 1)
		for crit in AIdb.getCriteria(self.AISQL.getQueue(), strip = False):
			response += "<th>" + crit + "</th>"
		response += "</tr>"
		names = AIdb.getManNames(self.AISQL.getQueue())
		for i in range(0, AIdb.numManifests(self.AISQL.getQueue())):
			manifest = names.next()
			for instance in range(0,
				AIdb.numInstances(manifest, self.AISQL.getQueue())):
				response += "<tr>"
				if instance == 0:
					response += """<td align=center
								rowspan=%s>%s</td>
								<td rowspan=%s><a href=/manifests/%s>%s</a></td>
								""" % (AIdb.numInstances(manifest,
								    self.AISQL.getQueue()), str(i + 1),
								    AIdb.numInstances(manifest,
								    self.AISQL.getQueue()), manifest, manifest)
				for crit in AIdb.getManifestCriteria(manifest,
				    instance, self.AISQL.getQueue(), onlyUsed = True,
				    humanOutput = True):
					response += "<td>%s</td>" % str(crit)
				response += "</tr>"
		else:
			response += """
						<tr><td align=center>0</td>
							<td>
								<a href = "/manifests/default.xml">Default</a>
							</td>
							<td colspan=%s align=center>None</td>
						</tr></table></body></html>
						"""%max(len(list(AIdb.getCriteria(self.AISQL.getQueue(),
						    strip=False))), 1)
		return response

	@cherrypy.expose
	def manifest_html(self):
		"""
		This is manifest.html the human useable form of the manifest.xml
		special object to list needed criteria or return a manifest given a
		set of criteria
		"""
		return '''
			<html><body>
				Criteria: %s
				<form action = "manifest.xml" method = "POST">
				<input type = "text" name = "postData" />
				<input type = "submit" />
				</form></body></html>
		''' % list(AIdb.getCriteria(self.AISQL.getQueue(), strip = True))
	staticmethod(manifest_html)

	@cherrypy.expose
	def manifest_xml(self, postData = None):
		"""
		This is manifest.xml the special object to list needed criteria
		or return a manifest given a set of criteria
		"""
		if postData is not None:
			criteria = {}
			while len(postData) > 0:
				try:
					[keyValue, postData] = postData.split(';', 1)
				except Exception:
					keyValue = postData
					postData = ''
				try:
					[key, value] = keyValue.split('=', 1)
					criteria[key] = value
				except Exception:
					criteria = {}
			manifest = AIdb.findManifest(criteria, self.AISQL)
			# check if findManifest() returned a number and one larger than 0
			# (means we got multiple manifests back -- an error)
			if str(manifest).isdigit() and manifest > 0:
				response = """
					<html><body>Criteria indeterminate -- this
					should not happen! Got %s matches.</body></html>
				    """ % str(manifest)
				return response 
			# check if findManifest() returned a number equal to 0
			# (means we got no manifests back -- thus we serve the default)
			elif manifest == 0:
				manifest = "default.xml"
			# else findManifest() returned the name of the manifest to serve
			# (or it is now set to default.xml)
			try:
				return serve_file(os.path.abspath(
					os.path.join(self.baseDir, os.path.join("AI_data",
					manifest))), "application/x-download", "attachment")
			except:
				raise cherrypy.NotFound("/manifests/" + str(manifest))
		# return criteria list for AI-client to know what needs querried
		else:
			# no PostData
			cherrypy.response.headers['Content-Type'] = "text/xml" 
			response = '<CriteriaList>\n'
			for crit in AIdb.getCriteria(self.AISQL.getQueue(), strip = True):
				response += '\t<Criteria>\n'
				response += '\t\t<Name="%s">\n' % crit
				response += '\t</Criteria>\n'
			else:
				response += '</CriteriaList>'
			return response
	staticmethod(manifest_xml)

class Manifests:
	"""
	Class provides the /manifests path of the server
	"""

	def __init__(self, dataLocation):
		self.baseDir = dataLocation

	@cherrypy.expose
	def index(self):
		"""
		The default for /manifests to redirect to the server's index listing
		all available manifests
		"""
		raise cherrypy.HTTPRedirect("/")
	staticmethod(index)
   
	@cherrypy.expose
	def default(self, path = None):
		"""
		Special path to serve anything (under /manifests/<path>)
		"""
		return serve_file(os.path.abspath(os.path.join(self.baseDir,
		    "AI_data", path)), "application/x-download", "attachment")
	staticmethod(default)

class AIFiles:
	"""
	This handles requests for files served out of /ai-files (zlibs, etc.)
	"""


	def __init__(self, dataLocation):
		self.baseDir = dataLocation

	@cherrypy.expose
	def index(self):
		"""
		The default for /ai-files to redirect to the server's index listing
		all available manifests
		"""
		raise cherrypy.HTTPError(403,"Index listing denied")
	staticmethod(index)
   
	@cherrypy.expose
	def default(self, path = None):
		"""
		Special path to serve anything (under /AI_files/<path>)
		"""
		return serve_file(os.path.abspath(os.path.join(self.baseDir,
		    os.path.join("AI_files", path))), "application/x-download",
		    "attachment")
	staticmethod(default)

if __name__ == '__main__':
	(options, dataLoc) = parseOptions()
	conf = { "/": { } }
	root = cherrypy.tree.mount(StaticPages(dataLoc))
	cherrypy.tree.mount(Manifests(dataLoc), script_name = "/manifests", 
						config = conf)
	cherrypy.tree.mount(AIFiles(dataLoc), script_name = "/ai-files", 
						config = conf)
	cherrypy.config.update({
				"request.show_tracebacks": options.debug,
				"server.socket_host": options.listen,
				"server.socket_port": options.port,
				"server.thread_pool": options.thread,
			})
	cherrypy.quickstart(root, config = conf)
