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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
"""

A/I Webserver

"""

_DISTRIBUTION="Oracle Solaris"

import os
import sys
import re
import gettext
from optparse import OptionParser

import cherrypy
from cherrypy.lib.static import serve_file
import lxml.etree
from lxml.html import builder as E

import osol_install.auto_install.AI_database as AIdb

def parse_options():
    """
    Parse and validate options
    """

    usage = _("usage: %prog [options] A/I_data_directory")
    parser = OptionParser(usage=usage)
    parser.add_option("-p", "--port", dest="port", default=8080,
                      metavar="port", type="int", nargs=1,
                      help=_("provide port to start server on"))
    parser.add_option("-t", "--threads", dest="thread", default=10,
                      metavar="thread count", type="int", nargs=1,
                      help=_("provide the number of threads to run"))
    parser.add_option("-l", "--listen", dest="listen", default="0.0.0.0",
                      metavar="ipaddress", type="string", nargs=1,
                      help=_("provide the interface to listen on"))
    parser.add_option("-d", "--debug", dest="debug", default=False,
                      action="store_true",
                      help=_("provide server tracebacks"))

    (options, args) = parser.parse_args()
    # check to see the listen directive is a valid IPv4 or IPv6 address
    if options.listen and not (
        re.search("^\d{1,3}(\.\d{1,3}){3}$", options.listen) or
        re.search("^[0-9a-fA-F]{0,4}(:[0-9a-fA-F]{0,4}){1,7}$",
                  options.listen)):
        parser.print_help()
        sys.exit(1)
    elif len(args) != 1:
        parser.print_help()
        sys.exit(1)

    return (options, args[0])

class staticPages:
    """
    Class containing the HTML for the static pages
    """

    def __init__(self, data_loc):
        self.base_dir = data_loc
        if os.path.exists(os.path.join(self.base_dir, 'AI.db')):
            self.AISQL = AIdb.DB(os.path.join(self.base_dir, 'AI.db'))
        else:
            raise SystemExit(_("Error:\tNo AI.db database"))
        self.AISQL.verifyDBStructure()

    @cherrypy.expose
    def index(self):
        """ The server's main page """

        # generate the list of criteria for the criteria table header
        criteriaHeader = E.TR()
        for crit in AIdb.getCriteria(self.AISQL.getQueue(), strip=False):
            criteriaHeader.append(E.TH(crit))

        # generate the manifest rows for the criteria table body
        names = AIdb.getManNames(self.AISQL.getQueue())
        tableBody = E.TR()
        for manifest in names:

            # iterate through each manifest (and instance)
            for instance in range(0,
                    AIdb.numInstances(manifest, self.AISQL.getQueue())):

                tableBody.append(E.TR())
                # print the manifest name only once (key off instance 0)
                if instance == 0:
                    tableBody.append(
                        E.TD(E.A(manifest,
                                 href="/manifests/" + manifest,
                                 rowspan=str(AIdb.numInstances(manifest,
                                    self.AISQL.getQueue())))
                            )
                    )
                else:
                    tableBody.append(E.TD())
                critPairs = AIdb.getManifestCriteria(manifest, instance,
                                                     self.AISQL.getQueue(),
                                                     onlyUsed=True,
                                                     humanOutput=True)
                # critPairs is an SQLite3 row object which doesn't support
                # iteritems(), etc.
                for crit in critPairs.keys():
                    formatted_val = AIdb.formatValue(crit, critPairs[crit])
                    # if we do not get back a valid value ensure a hyphen is
                    # printed (this prevents "" from printing)
                    if formatted_val and critPairs[crit]:
                        tableBody.append(E.TD(formatted_val, align="center"))
                    else:
                        tableBody.append(E.TD(lxml.etree.Entity("nbsp"),
                                              align="center"))

        # print the default manifest at the end of the table
        else:
            tableBody.append(
                             E.TR(
                                  E.TD(
                                       E.A("Default",
                                           href="/manifests/default.xml")),
                                  E.TD(lxml.etree.Entity("nbsp"),
                                       colspan=str(max(len(list(
                                       AIdb.getCriteria(self.AISQL.getQueue(),
                                       strip=False))), 1)),
                                       align="center")
                             )
            )
        web_page = \
                E.HTML(
                       E.HEAD(
                              E.TITLE(_("%s A/I Webserver") % _DISTRIBUTION)
                       ),
                       E.BODY(
                              E.H1(_("Welcome to the %s A/I "
                                     "webserver!") % _DISTRIBUTION),
                              E.P(_("This server has the following "
                                    "manifests available, served to clients "
                                    "matching required criteria.")),
                              E.TABLE(
                                      E.TR(
                                           E.TH(_("Manifest"), rowspan="2"),
                                           E.TH(_("Criteria List"),
                                                colspan=str(max(len(list(
                                                AIdb.getCriteria(self.AISQL.\
                                                getQueue(),
                                                strip=False))), 1)))
                                      ),
                                      criteriaHeader,
                                      tableBody,
                                      border="1", align="center"
                              ),
                       )
                )
        return lxml.etree.tostring(web_page, pretty_print=True)

    @cherrypy.expose
    def manifest_html(self):
        """
        This is manifest.html the human useable form of the manifest.xml
        special object to list needed criteria or return a manifest given a
        set of criteria
        """
        web_page = \
                E.HTML(
                       E.HEAD(
                              E.TITLE(_("%s A/I Webserver -- "
                                        "Maninfest Criteria Test") %
                                        _DISTRIBUTION)
                       ),
                       E.BODY(
                              E.H1(_("Welcome to the %s A/I "
                                     "webserver") % _DISTRIBUTION),
                              E.H2(_("Manifest criteria tester")),
                              E.P(_("To test a system's criteria, all "
                                    "criteria listed are necessary. The "
                                    "format used should be:"),
                                  E.BR(),
                                  E.TT("criteria1=value1;criteria2=value2"),
                                  E.BR(), _("For example:"),
                                  E.BR(),
                                  E.TT("arch=sun4u;mac=EEE0C0FFEE00;"
                                       "ipv4=172020025012;"
                                       "manufacturer=sun microsystems")
                              ),
                              E.H1(_("Criteria:")),
                              E.P(str(list(AIdb.getCriteria(
                                  self.AISQL.getQueue(), strip=True)))),
                              E.FORM(E.INPUT(type="text", name="postData"),
                                     E.INPUT(type="submit"),
                                     action="manifest.xml",
                                     method="POST"
                              )
                       )
                )
        return lxml.etree.tostring(web_page, pretty_print=True)

    @cherrypy.expose
    def manifest_xml(self, postData=None):
        """
        This is manifest.xml the special object to list needed criteria
        or return a manifest given a set of criteria
        """
        if postData is not None:
            criteria = {}

            # process each key/value pair of the POST data
            while postData:
                try:
                    [key_value, postData] = postData.split(';', 1)
                except (ValueError, NameError, TypeError, KeyError):
                    key_value = postData
                    postData = ''
                try:
                    [key, value] = key_value.split('=', 1)
                    criteria[key] = value
                except (ValueError, NameError, TypeError, KeyError):
                    criteria = {}
            manifest = AIdb.findManifest(criteria, self.AISQL)
            # check if findManifest() returned a number and one larger than 0
            # (means we got multiple manifests back -- an error)
            if str(manifest).isdigit() and manifest > 0:
                web_page = \
                    E.HTML(
                           E.HEAD(
                                  E.TITLE(_("Error!"))
                           ),
                           E.BODY(
                                  E.P(_("Criteria indeterminate -- this "
                                        "should not happen! Got %s matches.") %
                                      str(manifest))
                           )
                    )
                return lxml.etree.tostring(web_page, pretty_print=True)

            # check if findManifest() returned a number equal to 0
            # (means we got no manifests back -- thus we serve the default)
            elif manifest == 0:
                manifest = "default.xml"

            # else findManifest() returned the name of the manifest to serve
            # (or it is now set to default.xml)
            try:
                return serve_file(os.path.abspath(
                        os.path.join(self.base_dir, os.path.join("AI_data",
                        manifest))), "application/x-download", "attachment")
            except OSError:
                raise cherrypy.NotFound("/manifests/" + str(manifest))

        # this URI is not being requested using a POST method
        # return criteria list for AI-client to know what needs querried
        else:
            # <CriteriaList>
            #       <Version Number="0.5">
            #       <Criteria Name="MEM">
            #       <Criteria Name="arch">
            # ...
            # </CriteriaList>

            cherrypy.response.headers['Content-Type'] = "text/xml"
            XML = lxml.etree.Element("CriteriaList")
            version_value = lxml.etree.Element("Version")
            version_value.attrib["Number"] = "0.5"
            XML.append(version_value)
            for crit in AIdb.getCriteria(self.AISQL.getQueue(), strip=True):
                tag = lxml.etree.Element("Criteria")
                tag.attrib["Name"] = crit
                XML.append(tag)
            return lxml.etree.tostring(XML, pretty_print=True)

class Manifests:
    """
    Class provides the /manifests path of the server
    """

    def __init__(self, data_loc):
        self.base_dir = data_loc

    @cherrypy.expose
    def index(self):
        """
        The default for /manifests to redirect to the server's index listing
        all available manifests
        """
        raise cherrypy.HTTPRedirect("/")

    @cherrypy.expose
    def default(self, path=None):
        """
        Special path to serve anything (under /manifests/<path>)
        """
        return serve_file(os.path.abspath(os.path.join(self.base_dir,
                          "AI_data", path)), "application/x-download",
                          "attachment")


class AIFiles:
    """
    This handles requests for files served out of /ai-files (zlibs, etc.)
    """


    def __init__(self, data_loc):
        self.base_dir = data_loc

    @cherrypy.expose
    def index(self):
        """
        The default for /ai-files to redirect to the server's index listing
        all available manifests
        """
        raise cherrypy.HTTPError(403,"Index listing denied")

    @cherrypy.expose
    def default(self, path=None):
        """
        Special path to serve anything (under /AI_files/<path>)
        """
        return serve_file(os.path.abspath(os.path.join(self.base_dir,
                          os.path.join("AI_files", path))),
                          "application/x-download",
                          "attachment")

if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    (OPTIONS, DATA_LOC) = parse_options()
    CONF = { "/": { } }
    ROOT = cherrypy.tree.mount(staticPages(DATA_LOC))
    cherrypy.tree.mount(Manifests(DATA_LOC), script_name="/manifests",
                        config=CONF)
    cherrypy.tree.mount(AIFiles(DATA_LOC), script_name="/ai-files",
                        config=CONF)
    cherrypy.config.update({"request.show_tracebacks": OPTIONS.debug,
                            "server.socket_host": OPTIONS.listen,
                            "server.socket_port": OPTIONS.port,
                            "server.thread_pool": OPTIONS.thread})
    cherrypy.quickstart(ROOT, config=CONF)
