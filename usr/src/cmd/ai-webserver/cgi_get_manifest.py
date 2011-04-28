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
'''cgi_get_manifest retrieves the manifest based upon certain criteria
'''
import cgi
import gettext
import logging
import lxml.etree
import mimetypes
import os
import socket
import sys

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from lxml.html import builder as E
from StringIO import StringIO

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.common_profile as sc
import osol_install.libaimdns as libaimdns
import osol_install.libaiscf as smf

from osol_install.auto_install.ai_smf_service import PROP_TXT_RECORD
from osol_install.auto_install.installadm_common import SRVINST, PORTPROP
from osol_install.auto_install.properties import get_default, get_service_info
from solaris_install import AI_DATA, _

VERSION = '2.0'
PROFILES_VERSION = '2.0'  # MIME-encoded profiles started
COMPATIBILITY_VERSION = '0.5'

# Solaris installer debugging levels
AI_DBGLVL_NONE = 0
AI_DBGLVL_INFO = 4


def get_parameters(form):
    '''Gets the CGI parameters.

    Args
        form    - form data in dictionary

    Returns
        protocol_version   - the request version number, 0.5 indicates that the
                             original mechanisms are being used.
        service_name       - the service name
        post_data          - the POST-ed client criteria

    Raises
        None
    '''
    protocol_version = COMPATIBILITY_VERSION  # assume original client
    service_name = None
    post_data = None
    if 'version' in form:
        protocol_version = form['version'].value  # new client
        # new clients have the service name associated with the request
        if 'service' in form:
            service_name = form['service'].value
    if 'logging' in form:
        sol_dbg = form['logging'].value
        # set logging level according to post data from debug level on client
        if sol_dbg is not None:
            if sol_dbg.isdigit() and int(sol_dbg) >= AI_DBGLVL_NONE and \
                    int(sol_dbg) <= AI_DBGLVL_INFO:
                # mapping of installer debug levels to Python logging levels
                dbglogmap = [logging.NOTSET, logging.CRITICAL, logging.ERROR,
                            logging.WARN, logging.DEBUG]
                logging.getLogger().setLevel(dbglogmap[int(sol_dbg)])
            else:
                logging.warning(_(
                        "Unrecognized logging level from POST REQUEST:  ")
                        + str(sol_dbg))
    if 'postData' in form:
        post_data = form['postData'].value

    return (protocol_version, service_name, post_data)


def get_environment_information():
    '''Gets the environment information for old client requests
       for the port number and request type (GET or POST).

    Args
        None

    Returns
        method - either GET or POST -- GET indicates that the client
                 is requesting the required criteria.  POST indicates
                 that the client is sending the required criteria in
                 the postData form information.
        port   - required to distinguish which original service
                 is being requested.

    Raises
        None
    '''
    method = os.environ['REQUEST_METHOD']
    port = int(os.environ['SERVER_PORT'])

    return (method, port)


def send_needed_criteria(port):
    '''Replies to the old client with the needed criteria

    Args
        port - the originating port for the old client

    Returns
        None

    Raises
        None
    '''
    # Establish the service SQL database based upon the
    # port number for the service
    path = os.path.join(os.path.join('/var/ai', str(port)), 'AI.db')
    if os.path.exists(path):
        try:
            aisql = AIdb.DB(path)
            aisql.verifyDBStructure()
        except StandardError, err:
            # internal error, record the error in the server error_log
            sys.stderr.write(_('error:AI database access error\n%s\n') % err)
            # report the error to the requesting client
            print "Content-Type: text/html"    # HTML is following
            print                              # blank line, end of headers
            sys.stdout.write(_("error:AI database access error\n%s\n") % err)
            sys.exit(1)
    else:
        # not an internal error, report to the requesting client only
        print "Content-Type: text/html"    # HTML is following
        print                              # blank line, end of headers
        print _("Error:unable to determine criteria "
                "for service associated with port"), port
        return

    # build the required criteria list
    xml = lxml.etree.Element("CriteriaList")
    # old version number
    version_value = lxml.etree.Element("Version")
    version_value.attrib["Number"] = COMPATIBILITY_VERSION
    xml.append(version_value)
    # pull the required criteria from the SQL database
    for crit in AIdb.getCriteria(aisql.getQueue(), strip=True):
        tag = lxml.etree.Element("Criteria")
        tag.attrib["Name"] = crit
        xml.append(tag)
    xmlstr = lxml.etree.tostring(xml, pretty_print=True)

    # report the results
    print "Content-Length:", len(xmlstr)  # Length of XML reply
    print "Content-Type: text/xml"        # XML is following
    print                                 # blank line, end of headers
    print xmlstr


def send_manifest(form_data, port=0, servicename=None,
        protocolversion=COMPATIBILITY_VERSION):
    '''Replies to the client with matching service for a service.

    Args
        form_data   - the postData passed in from the client request
        port        - the port of the old client
        servicename - the name of the service being used
        protocolversion - the version of the AI service RE: handshake

    Returns
        None

    Raises
        None
    '''
    # figure out the appropriate path for the AI database,
    # and get service name if necessary.
    # currently service information is stored in a port directory.
    # When the cherrypy webserver new service directories should be
    # separated via service-name only.  Old services will still use
    # port numbers as the separation mechanism.
    path = None
    found_servicename = None
    if servicename:
        path = os.path.join(os.path.join('/var/ai', servicename), 'AI.db')
    if not path or not os.path.exists(path):
        inst = smf.AISCF(FMRI="system/install/server")
        services = inst.services.keys()
        if servicename:
            for akey in services:
                if akey == servicename:
                    serv = smf.AIservice(inst, akey)
                    if PROP_TXT_RECORD in serv.keys():
                        port = serv[PROP_TXT_RECORD].partition(':')[-1]
                        path = os.path.join(os.path.join('/var/ai', port),
                                            'AI.db')
        else:
            # No service name, but we have port.  Get service name from port
            for akey in services:
                serv = smf.AIservice(inst, akey)
                if PROP_TXT_RECORD in serv.keys():
                    servs_port = serv[PROP_TXT_RECORD].partition(':')[-1]
                    if int(port) == int(servs_port):
                        found_servicename = akey
                        break

            path = os.path.join(os.path.join('/var/ai/', str(int(port))),
                                'AI.db')

    # Check to insure that a valid path was found
    if not path or not os.path.exists(path):
        print 'Content-Type: text/html'     # HTML is following
        print                               # blank line, end of headers
        if servicename:
            print '<pre><b>Error</b>:unable to find<i>', servicename + '</i>.'
        else:
            print '<pre><b>Error</b>:unable to find<i>', port + '</i>.'
        print 'Available services are:<p><ol><i>'
        hostname = socket.gethostname()
        for akey in inst.services.keys():
            serv = smf.AIservice(inst, akey)
            if PROP_TXT_RECORD in serv.keys():
                port = int(serv[PROP_TXT_RECORD].split(':')[-1])
            else:
                port = libaimdns.getinteger_property(SRVINST, PORTPROP)
            sys.stdout.write('<a href="http://%s:%d/cgi-bin/'
                   'cgi_get_manifest.py?version=%s&service=%s">%s</a><br>\n' %
                   (hostname, port, VERSION, akey, akey))
        print '</i></ol>Please select a service from the above list.'
        return

    if found_servicename:
        servicename = found_servicename

    # load to the AI database
    aisql = AIdb.DB(path)
    aisql.verifyDBStructure()

    # convert the form data into a criteria dictionary
    criteria = {}
    orig_data = form_data
    while form_data:
        try:
            [key_value, form_data] = form_data.split(';', 1)
        except (ValueError, NameError, TypeError, KeyError):
            key_value = form_data
            form_data = ''
        try:
            [key, value] = key_value.split('=')
            criteria[key] = value
        except (ValueError, NameError, TypeError, KeyError):
            criteria = {}

    # find the appropriate manifest
    try:
        manifest = AIdb.findManifest(criteria, aisql)
    except StandardError, err:
        print 'Content-Type: text/html'     # HTML is following
        print                               # blank line, end of headers
        print '<pre><b>Error</b>:findManifest criteria<br>'
        print err, '<br>'
        print '<ol>servicename =', servicename
        print 'port        =', port
        print 'path        =', path
        print 'form_data   =', orig_data
        print 'criteria    =', criteria
        print 'servicename found by port =', str(found_servicename), '</ol>'
        print '</pre>'
        return

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
        print "Content-Type: text/html"     # HTML is following
        print                               # blank line, end of headers
        print lxml.etree.tostring(web_page, pretty_print=True)
        return

    # check if findManifest() returned a number equal to 0
    # (means we got no manifests back -- thus we serve the default)
    elif manifest == 0:
        manifest = get_default(servicename)

    # findManifest() returned the name of the manifest to serve
    # (or it is now set to default.xml)
    try:
        # construct the fully qualified filename
        path = os.path.join(os.path.dirname(path), AI_DATA)
        filename = os.path.abspath(os.path.join(path, manifest))
        # open and read the manifest
        with open(filename, 'rb') as mfp:
            manifest_str = mfp.read()
        # maintain compability with older AI client
        if servicename is None or \
                float(protocolversion) < float(PROFILES_VERSION):
            content_type = mimetypes.types_map.get('.xml', 'text/plain')
            print 'Content-Length:', len(manifest_str)  # Length of the file
            print 'Content-Type:', content_type         # XML is following
            print                                 # blank line, end of headers
            print manifest_str
            logging.info('Manifest sent from %s.' % filename)
            return

    except OSError, err:
        print 'Content-Type: text/html'     # HTML is following
        print                               # blank line, end of headers
        print '<pre>'
        # report the internal error to error_log and requesting client
        sys.stderr.write(_('error:manifest (%s) %s\n') % (str(manifest), err))
        sys.stdout.write(_('error:manifest (%s) %s\n') % (str(manifest), err))
        print '</pre>'
        return

    # get AI service image path
    service_info = get_service_info(servicename)
    # construct object to contain MIME multipart message
    outermime = MIMEMultipart()
    client_msg = list()  # accumulate message output for AI client
    # add manifest as attachment
    msg = MIMEText(manifest_str, 'xml')
    # indicate manifest using special name
    msg.add_header('Content-Disposition', 'attachment',
                   filename=sc.AI_MANIFEST_ATTACHMENT_NAME)
    outermime.attach(msg)  # add manifest as an attachment

    # search for any profiles matching client criteria
    # formulate database query to profiles table
    q_str = "SELECT DISTINCT name, file FROM " + \
        AIdb.PROFILES_TABLE + " WHERE "
    nvpairs = list()  # accumulate criteria values from post-data
    # for all AI client criteria
    for crit in AIdb.getCriteria(aisql.getQueue(), table=AIdb.PROFILES_TABLE,
                                 onlyUsed=False):
        if crit not in criteria:
            msgtxt = _("Warning: expected client criteria \"%s\" " \
                       "missing from post-data. Profiles may be missing.") \
                       % crit
            client_msg += [msgtxt]
            logging.warn(msgtxt)
            # fetch only global profiles destined for all clients
            if AIdb.isRangeCriteria(aisql.getQueue(), crit,
                                    AIdb.PROFILES_TABLE):
                nvpairs += ["MIN" + crit + " IS NULL"]
                nvpairs += ["MAX" + crit + " IS NULL"]
            else:
                nvpairs += [crit + " IS NULL"]
            continue
        # prepare criteria value to add to query
        envval = AIdb.sanitizeSQL(criteria[crit])
        if AIdb.isRangeCriteria(aisql.getQueue(), crit, AIdb.PROFILES_TABLE):
            if crit == "mac":
                nvpairs += ["(MIN" + crit + " IS NULL OR "
                    "HEX(MIN" + crit + ")<=HEX(X'" + envval + "'))"]
                nvpairs += ["(MAX" + crit + " IS NULL OR HEX(MAX" +
                        crit + ")>=HEX(X'" + envval + "'))"]
            else:
                nvpairs += ["(MIN" + crit + " IS NULL OR MIN" +
                        crit + "<='" + envval + "')"]
                nvpairs += ["(MAX" + crit + " IS NULL OR MAX" +
                        crit + ">='" + envval + "')"]
        else:
            nvpairs += ["(" + crit + " IS NULL OR " +
                    crit + "='" + envval + "')"]
    q_str += " AND ".join(nvpairs)

    # issue database query
    logging.info("Profile query: " + q_str)
    query = AIdb.DBrequest(q_str)
    aisql.getQueue().put(query)
    query.waitAns()
    if query.getResponse() is None or len(query.getResponse()) == 0:
        msgtxt = _("No profiles found.")
        client_msg += [msgtxt]
        logging.info(msgtxt)
    else:
        for row in query.getResponse():
            profpath = row['file']
            profname = row['name']
            if profname is None:  # should not happen
                profname = 'unnamed'
            try:
                if profpath is None:
                    msgtxt = "Database record error - profile path is empty."
                    client_msg += [msgtxt]
                    logging.error(msgtxt)
                    continue
                msgtxt = _('Processing profile %s') % profname
                client_msg += [msgtxt]
                logging.info(msgtxt)
                with open(profpath, 'r') as pfp:
                    raw_profile = pfp.read()
                # do any template variable replacement {{AI_xxx}}
                tmpl_profile = sc.perform_templating(raw_profile,
                                                     validate_only=False)
                # precautionary validation or profile, logging only
                sc.validate_profile_string(tmpl_profile, service_info[2],
                                           dtd_validation=True,
                                           warn_if_dtd_missing=True)
            except IOError, err:
                msgtxt = _("Error:  I/O error: ") + str(err)
                client_msg += [msgtxt]
                logging.error(msgtxt)
                continue
            except OSError:
                msgtxt = _("Error:  OS error on profile ") + profpath
                client_msg += [msgtxt]
                logging.error(msgtxt)
                continue
            except KeyError:
                msgtxt = _('Error:  could not find criteria to substitute in '
                        'template: ') + profpath
                client_msg += [msgtxt]
                logging.error(msgtxt)
                logging.error('Profile with template substitution error:' +
                        raw_profile)
                continue
            except lxml.etree.XMLSyntaxError, err:
                # log validation error and proceed
                msgtxt = _(
                        'Warning:  syntax error found in profile: ') \
                        + profpath
                client_msg += [msgtxt]
                logging.error(msgtxt)
                for error in err.error_log:
                    msgtxt = _('Error:  ') + error.message
                    client_msg += [msgtxt]
                    logging.error(msgtxt)
                logging.info([_('Profile failing validation:  ') +
                             lxml.etree.tostring(root)])
            # build MIME message and attach to outer MIME message
            msg = MIMEText(tmpl_profile, 'xml')
            # indicate in header that this is an attachment
            msg.add_header('Content-Disposition', 'attachment',
                           filename=profname)
            # attach this profile to the manifest and any other profiles
            outermime.attach(msg)
            msgtxt = _('Parsed and loaded profile: ') + profname
            client_msg += [msgtxt]
            logging.info(msgtxt)

    # any profiles and AI manifest have been attached to MIME message
    # specially format list of messages for display on AI client console
    if client_msg:
        outtxt = ''
        for msgtxt in client_msg:
            msgtxt = _('SC profile locator:') + msgtxt
            outtxt += str(msgtxt) + '\n'
        # add AI client console messages as single plain text attachment
        msg = MIMEText(outtxt, 'plain')  # create MIME message
        outermime.attach(msg)  # attach MIME message to response

    print outermime.as_string()  # send MIME-formatted message


def list_manifests(service):
    '''Replies to the client with criteria list for a service.
       The output should be similar to installadm list.

    Args
        service - the name of the service being listed

    Returns
        None

    Raises
        None
    '''
    print 'Content-Type: text/html'     # HTML is following
    print                               # blank line, end of headers
    print '<html>'
    print '<head>'
    sys.stdout.write('<title>%s %s</title>' %
                     (_('Manifest list for'), service))
    print '</head><body>'

    port = 0
    try:
        inst = smf.AISCF(FMRI="system/install/server")
    except KeyError:
        # report the internal error to error_log and requesting client
        sys.stderr.write(_("error:The system does not have the " +
                         "system/install/server SMF service."))
        sys.stdout.write(_("error:The system does not have the " +
                         "system/install/server SMF service."))
        return
    services = inst.services.keys()
    if not services:
        # report the error to the requesting client only
        sys.stdout.write(_('error:no services on this server.\n'))
        return

    found = False
    for akey in inst.services.keys():
        serv = smf.AIservice(inst, akey)
        if 'service_name' not in serv.keys():
            # report the internal error to error_log and requesting client
            sys.stderr.write(_('error:SMF service key "service_name"'
                               'property does not exist\n'))
            sys.stdout.write(_('error:SMF service key "service_name"'
                               'property does not exist\n'))
            return
        if serv['service_name'] == service:
            found = True
            if PROP_TXT_RECORD not in serv.keys():
                # report the internal error to error_log and requesting client
                sys.stderr.write(_('error:SMF service key \"' +
                                   PROP_TXT_RECORD +
                                   '\"property does not exist\n'))
                sys.stdout.write(_('error:SMF service key \"' +
                                   PROP_TXT_RECORD +
                                   '\"property does not exist\n'))
                return

            # assume new service setup
            path = os.path.join('/var/ai', service, 'AI.db')
            if not os.path.exists(path):
                # Establish the service SQL database based upon the
                # port number for the service
                port = serv[PROP_TXT_RECORD].split(':')[-1]
                path = os.path.join('/var/ai', str(port), 'AI.db')

            if os.path.exists(path):
                try:
                    aisql = AIdb.DB(path)
                    aisql.verifyDBStructure()
                except StandardError, err:
                    # report the internal error to error_log and
                    # requesting client
                    sys.stderr.write(_('error:AI database access '
                                       'error\n%s\n') % err)
                    sys.stdout.write(_('error:AI database access '
                                       'error\n%s\n') % err)
                    return

                # generate the list of criteria for the criteria table header
                criteria_header = E.TR()
                for crit in AIdb.getCriteria(aisql.getQueue(), strip=False):
                    criteria_header.append(E.TH(crit))

                # generate the manifest rows for the criteria table body
                names = AIdb.getManNames(aisql.getQueue())
                table_body = E.TR()
                allcrit = AIdb.getCriteria(aisql.getQueue(), strip=False)
                colspan = str(max(len(list(allcrit)), 1))
                for manifest in names:

                    # iterate through each manifest (and instance)
                    for instance in range(0,
                            AIdb.numInstances(manifest, aisql.getQueue())):

                        table_body.append(E.TR())
                        # print the manifest name only once (from instance 0)
                        if instance == 0:
                            href = '../' + service + '/' + manifest
                            row = str(AIdb.numInstances(manifest,
                                                       aisql.getQueue()))
                            table_body.append(E.TD(
                                    E.A(manifest, href=href, rowspan=row)))
                        else:
                            table_body.append(E.TD())

                        crit_pairs = AIdb.getManifestCriteria(manifest,
                                                  instance,
                                                  aisql.getQueue(),
                                                  onlyUsed=True,
                                                  humanOutput=True)

                        # crit_pairs is an SQLite3 row object which doesn't
                        # support iteritems(), etc.
                        for crit in crit_pairs.keys():
                            formatted_val = AIdb.formatValue(crit,
                                                             crit_pairs[crit])
                            # if we do not get back a valid value ensure a
                            # hyphen is printed (prevents "" from printing)
                            if formatted_val and crit_pairs[crit]:
                                table_body.append(E.TD(formatted_val,
                                                      align="center"))
                            else:
                                table_body.append(E.TD(
                                                    lxml.etree.Entity("nbsp"),
                                                        align="center"))

                # print the default manifest at the end of the table,
                # which has the same colspan as the Criteria List label
                else:
                    href = '../' + service + '/default.xml'
                    table_body.append(
                                     E.TR(
                                         E.TD(
                                             E.A("Default", href=href)),
                                         E.TD(lxml.etree.Entity("nbsp"),
                                             colspan=colspan,
                                             align="center")
                                     )
                        )
                web_page = E.HTML(
                             E.HEAD(
                                E.TITLE(_("Solaris Automated "
                                          "Installation Webserver"))
                                ),
                             E.BODY(
                                E.H1(_("Welcome to the Solaris "
                                       "Automated Installation webserver!")),
                                E.P(_("Service '%s' has the following "
                                    "manifests available, served to clients "
                                    "matching required criteria.") % service),
                                E.TABLE(
                                   E.TR(
                                        E.TH(_("Manifest"), rowspan="2"),
                                        E.TH(_("Criteria List"),
                                            colspan=colspan)),
                                        criteria_header,
                                        table_body,
                                        border="1", align="center"),
                              )
                         )
                print lxml.etree.tostring(web_page, pretty_print=True)

    # service is not found, provide available services on host
    if not found:
        sys.stdout.write(_('Service <i>%s</i> not found.  ') % service)
        sys.stdout.write(_('Available services are:<p><ol><i>'))
        host = socket.gethostname()
        for akey in inst.services.keys():
            serv = smf.AIservice(inst, akey)
            # assume new service setup
            port = libaimdns.getinteger_property(SRVINST, PORTPROP)
            if not os.path.exists('/var/ai/' + service):
                if PROP_TXT_RECORD in serv.keys():
                    port = int(serv[PROP_TXT_RECORD].split(':')[-1])
            sys.stdout.write('<a href="http://%s:%d/cgi-bin/'
                   'cgi_get_manifest.py?version=%s&service=%s">%s</a><br>\n' %
                   (host, port, VERSION, akey, akey))
        sys.stdout.write('</i></ol>%s' % _('Please select a service '
                   'from the above list.'))

    print '</body></html>'

if __name__ == '__main__':
    gettext.install("ai", "/usr/lib/locale")
    DEFAULT_PORT = libaimdns.getinteger_property(SRVINST, PORTPROP)
    (PARAM_VERSION, SERVICE, FORM_DATA) = get_parameters(cgi.FieldStorage())
    print >> sys.stderr, PARAM_VERSION, SERVICE, FORM_DATA
    if PARAM_VERSION == COMPATIBILITY_VERSION or SERVICE is None:
        # Old client
        (REQUEST_METHOD, REQUEST_PORT) = get_environment_information()
        if REQUEST_PORT == DEFAULT_PORT:  # only new clients use default port
            HOST = socket.gethostname()
            print 'Content-Type: text/html'     # HTML is following
            print                               # blank line, end of headers
            print '<pre>'
            sys.stdout.write(_('error:must supply a service name\n'))
            sys.stdout.write(_('The request should look like:\n'))
            sys.stdout.write('<ol>http://%s:%d/cgi_get_manifest.py?'
                             'version=%s&service=<i>servicename</i></ol>' %
                             (HOST, DEFAULT_PORT, VERSION))
            print '</pre>'
            sys.exit(0)
        if REQUEST_METHOD == 'GET':
            send_needed_criteria(REQUEST_PORT)
        else:
            send_manifest(FORM_DATA, port=REQUEST_PORT)
    elif FORM_DATA is None:
        # do manifest table list
        list_manifests(SERVICE)
    else:
        # do manifest criteria match
        try:
            send_manifest(FORM_DATA, servicename=SERVICE,
                          protocolversion=PARAM_VERSION)
        except StandardError:
            # send error report to client (through stdout), log
            print "Content-Type: text/html"     # HTML is following
            print                               # blank line, end of headers
            ERRMSG = _(
                'Unexpected error in AI server script locating SC profiles. '
                'Script traceback from server:')
            print ERRMSG
            logging.error(ERRMSG)
            # traceback to stdout and log
            import traceback
            TB = traceback.format_exc()  # traceback to stdout and log
            logging.error(TB)
            print TB
