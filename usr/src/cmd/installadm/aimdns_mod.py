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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''
Auto Installer mDNS and DNS Service Discovery class and application.
'''
import gettext
import select
import signal
import sys

import pybonjour as pyb

import osol_install.auto_install.installadm_common as common
import osol_install.auto_install.service_config as config
import osol_install.libaimdns as libaimdns
import osol_install.libaiscf as smf
import osol_install.netif as netif

from osol_install.auto_install.installadm_common import _, cli_wrap as cw


class AIMDNSError(Exception):
    ''' Class for reporting AI mDNS issues
    '''
    pass


class AImDNS(object):
    ''' Class: AImDNS - base class for registering, browsing and looking up
                        AI and ad hoc mDNS records.
    '''
    # a _handle_event() loop control variable, used to restart the loop
    # after modification to the self.sdrefs variable, private
    _restart_loop = False

    # find/browse mode variables, private
    _do_lookup = False
    _found = False

    # mDNS record resolved variable, used as a stack to indicate that the
    # service has been found, private
    _resolved = list()

    def __init__(self, servicename=None, domain='local', comment=None):
        '''Method: __init__, class private
           Parameters:
                        servicename - the AI servicename
                        domain      - the domain for the registered service
                        comment     - the text comment for the service
           Raises:
               AImDNSError - when unable to retrieve setup information from
                             the host about the available interfaces or the
                             AI SMF service.
        '''
        gettext.install("solaris_install_installadm", "/usr/share/locale")

        # find sdref handle
        self._find = None
        self._lookup = False
        self.services = dict()
        self.servicename = servicename
        self.domain = domain
        self.txt = comment
        self.inter = None
        self.port = 0
        self.verbose = False
        self.timeout = 5
        self.done = False
        self.count = 0

        self.sdrefs = dict()

        self.interfaces = libaimdns.getifaddrs()

        self.register_initialized = False
        self.exclude = False
        self.networks = ['0.0.0.0/0']

        self.instance = None
        self.instance_services = None

    def __del__(self):
        '''Method: __del__
           Parameters:
                None

           Raises:
                None
        '''
        self.done = True
        self.clear_sdrefs()

    def _resolve_callback(self, sdref, flags, interfaceindex, errorcode,
                          fullname, hosttarget, port, txtrecord):
        '''Method: _resolve_callback, class private
        Description:
            DNS Callback for the resolve process, stories the service
            information within the self.services variable.

        Args
            sdref          - service reference,
                             standard argument for callback, not used
            flags          - flag to determine what action is taking place
                             standard argument for callback, not used
            interfaceindex - the index for the interface that the service was
                             found on
            errorcode      - flag to determine if a registration error occurred
            fullname       - name of the service, should be
                             <service>._OSInstall._tcp.local.
            hosttarget     - name of the host, should be <nodename>.local.
            port           - the service port being used
            txtrecord      - the text record associated with the service,
                             standard argument for callback

        Returns
            None

        Raises
            None
        '''
        # handle errors from within the _browse_callback
        # after the select() call
        if errorcode == pyb.kDNSServiceErr_NoError:
            self._found = True
            # get the interface name for the index
            interface = netif.if_indextoname(interfaceindex)
            # interested in the service name and the domain only
            parts = fullname.split('.')
            service = dict()
            service['flags'] = not (flags & pyb.kDNSServiceFlagsAdd)
            service['hosttarget'] = hosttarget
            service['servicename'] = parts[0]
            service['domain'] = parts[-2]
            service['port'] = port
            service['comments'] = str(pyb.TXTRecord.parse(txtrecord))[1:]
            self.services.setdefault(interface, list()).append(service)

            # update the resolve stack flag
            self._resolved.append(True)

    def _browse_callback(self, sdref, flags, interfaceindex, errorcode,
                         servicename, regtype, replydomain):
        '''Method: _browse_callback, class private
        Description:
            DNS Callback for the browse process

        Args
            sdref          - service reference,
                             standard argument for callback, not used
            flags          - flag to determine what action is taking place
                             standard argument for callback, not used
            interfaceindex - the index for the interface that the service was
                             found on
            errorcode      - flag to determine if a registration error occurred
            servicename    - name of the service
            hosttarget     - name of the host, should be <nodename>.local.
            regtype        - registration type, should be _OSInstall._tcp.
            replydomain    - DNS domain, either local or remote

        Returns
            None

        Raises
            None
        '''
        if errorcode != pyb.kDNSServiceErr_NoError:
            return  # error handled in the _handle_event() method

        if self._lookup and servicename != self.servicename:
            return

        resolve_sdref = pyb.DNSServiceResolve(0, interfaceindex,
                                              servicename, regtype,
                                              replydomain,
                                              self._resolve_callback)

        # wait for and process resolve the current request
        try:
            while not self._resolved:
                try:
                    ready = select.select([resolve_sdref], list(), list(),
                                           self.timeout)
                except select.error:
                    # purposely ignore errors.
                    continue

                if resolve_sdref not in ready[0]:
                    # not a catastrophic error for the class, therefore,
                    # simply warn that the mDNS service record needed
                    # additional time to process and do not issue an
                    # exception.
                    sys.stderr.write(cw(_('warning: unable to resolve "%s", '
                                          'try using a longer timeout\n') %
                                          servicename))
                    break
                # process the service
                pyb.DNSServiceProcessResult(resolve_sdref)
            else:
                self._resolved.pop()
        # allow exceptions to fall through
        finally:
            # clean up when there is no exception
            resolve_sdref.close()

    def _handle_events(self):
        ''' Method: __handle_events, class private
            Description:
                Handle the event processing for the registered service
                requests.

            Args
                None

            Returns
                None

            Raises
                None
        '''
        self.done = False
        while not self.done:
            # The self.sdrefs is a dictionary of the form:
            #
            #   for the find mode:
            #       { 'find':[list of sdrefs] }
            #
            #   OR for the browse mode:
            #       { 'browse':[list of sdrefs] }
            #
            #   OR for the register mode:
            #       { <service-name>:[list of sdrefs] }
            #
            #   OR for the register all mode:
            #       { <service-name1>:[list of sdrefs],
            #         <service-name2>:[list of sdrefs],
            #         ... }
            #
            # This must be converted to a simple list of sdrefs for the
            # select() call.
            therefs = list()
            # iterate through the dictionary
            for srv in self.sdrefs:
                for refs in self.sdrefs.get(srv, list()):
                    if refs is not None:
                        therefs.append(refs)

            # loop until done or we need to redo the service reference
            # list mentioned above.  The service reference list will be
            # updated when the SMF service is refreshed which sends a
            # SIGHUP to the application in daemon mode.  This processing
            # of the SIGHUP is done in the signal_hup() method below.
            self._restart_loop = False
            count = 0
            while not self._restart_loop and not self.done:
                try:
                    # process the appropriate service reference
                    try:
                        ready = select.select(therefs, list(), list(),
                                              self.timeout)
                    except select.error:
                        continue

                    # check to ensure that the __del__ method was not called
                    # between the select and the DNS processing.
                    if self.done:
                        continue

                    for sdref in therefs:
                        if sdref in ready[0]:
                            pyb.DNSServiceProcessResult(sdref)

                    # if browse or find loop then loop only long enough to
                    # ensure that all the registered mDNS records are
                    # retrieved per interface configured
                    if self._do_lookup is True:
                        count += 1
                        if count >= self.count:
                            self.done = True

                # <CTL>-C will exit the loop, application
                # needed for command line invocation
                except KeyboardInterrupt:
                    self.done = True

    def _register_callback(self, sdref, flags, errorcode, name,
                           regtype, domain):
        '''Method: _register_callback, private to class
           Description:
                DNS Callback for the registration process

            Args
                sdref       - service reference
                              standard argument for callback, not used
                flags       - flag to determine what action is taking place
                              standard argument for callback, not used
                errorcode   - flag to determine if a registration error
                              occurred
                name        - name of the service
                regtype     - registration type, should be _OSInstall._tcp.
                domain      - DNS domain, either local or remote

            Returns
                None

            Raises
                None
        '''
        # note: DNSService Errors are ignored here and handled elsewhere.
        if errorcode == pyb.kDNSServiceErr_NoError and \
           self.verbose:
            print _('Registered service:')
            print _('\tname    = %s') % name
            print _('\tregtype = %s') % regtype
            print _('\tdomain  = %s') % domain

    def _register_a_service(self, name, interfaces=None, port=0,
                            comments=None):
        '''Method: _register_a_service, private to class

        Description:
            Register a single service on the interfaces

        Args
            interfaces - the interfaces to register the service on
            instance   - the SMF service instance handle
            name       - the service name to be registered
            port       - the port that the service is listening on, if
                         port is 0 then registering a service listed in
                         the AI SMF service instance.
            comments   - comments for the ad hoc registered service

        Returns
            list_sdrefs - list of service references

        Raises
            AImDNSError - if SMF status property does not exist, OR
                          if SMF txt_record property does not exist, OR
                          if SMF port property does not exist.
        '''
        if not self.register_initialized:
            self.exclude = libaimdns.getboolean_property(common.SRVINST,
                                                         common.EXCLPROP)
            self.networks = libaimdns.getstrings_property(common.SRVINST,
                                                          common.NETSPROP)
            self.register_initialized = True

        smf_port = None
        # if port is 0 then processing an AI service
        if port == 0:
            serv = config.get_service_props(name)
            if not serv:
                raise AIMDNSError(cw(_('error: aiMDNSError: no such '
                                       'installation service "%s"') % name))

            # ensure the service is enabled
            if config.PROP_STATUS not in serv:
                raise AIMDNSError(cw(_('error: aiMDNSError: installation '
                                       'service key "status" property does '
                                       'not exist')))

            if serv[config.PROP_STATUS] != config.STATUS_ON:
                print(cw(_('warning: Installation service "%s" is not enabled '
                           % name)))
                return None

            smf_port = config.get_service_port(name)
            if not smf_port:
                try:
                    smf_port = libaimdns.getinteger_property(common.SRVINST,
                                                             common.PORTPROP)
                    smf_port = str(smf_port)
                except libaimdns.aiMDNSError, err:
                    raise AIMDNSError(cw(_('error: aiMDNSError: port property '
                                           'failure (%s)') % err))

        # iterate over the interfaces saving the service references
        list_sdrefs = list()
        valid_networks = common.get_valid_networks()
        for inf in interfaces:
            include_it = False
            for ip in valid_networks:
                if interfaces[inf].startswith(ip):
                    include_it = True
                    break

            if not include_it:
                continue

            if self.verbose:
                print cw(_('Registering %(name)s on %(interface)s'
                           '(%(inf)s)') % {'name': name, 'interface': inf, \
                           'inf': interfaces[inf]})

            if smf_port is not None:
                # comments are part of the service record
                commentkey = serv[config.PROP_TXT_RECORD].split('=')[0]
                commenttxt = interfaces[inf].split('/')[0] + ':' + smf_port
                text = pyb.TXTRecord({commentkey: commenttxt})
                try:
                    port = int(smf_port)
                except ValueError:
                    # not a catastrophic error, just
                    # assume the default port of 5555.
                    port = common.DEFAULT_PORT
            # processing an ad hoc registration
            elif comments is None:
                adhoc_dict = {'service': 'ad hoc registration'}
                text = pyb.TXTRecord(adhoc_dict)
            else:
                text = pyb.TXTRecord({'service': comments})

            # register the service on the appropriate interface index
            try:
                interfaceindex = netif.if_nametoindex(inf)
            except netif.NetIFError, err:
                raise AIMDNSError(err)

            sdref = pyb.DNSServiceRegister(name=name,
                                           interfaceIndex=interfaceindex,
                                           regtype=common.REGTYPE,
                                           port=port,
                                           callBack=self._register_callback,
                                           txtRecord=text)

            # DNSServiceUpdateRecord will update the default record if
            # RecordRef is None. Time-to-live (ttl) for the record is being
            # set to 10 seconds.  This value allows enough time for the
            # record to be looked up and it is short enough that when the
            # service is deleted then the mdns daemon will remove it from
            # the cache after this value expires but prior to another service
            # with the same name being created.
            pyb.DNSServiceUpdateRecord(sdRef=sdref, RecordRef=None,
                                       rdata=text, ttl=10)

            # save the registered service reference
            list_sdrefs.append(sdref)

        return list_sdrefs

    def register(self, servicename=None, port=0, interfaces=None,
                 comments=None):
        '''Method: register
           Description:
                Registers an ad hoc service.  This method will loop until the
                the application is killed.

            Args
                servicename - the name of the ad hoc service
                port        - the port to use for the ad hoc service
                interfaces  - the interfaces to register the ad hoc service on
                comments    - the service comments for the ad hoc service

            Returns
                None

            Raises
                SystemError  - if the SMF service instance can not be loaded.
                AImDNSError  - if unable to register the service OR
                               if no servicename is present.
        '''
        self._do_lookup = False

        if servicename is not None:
            self.servicename = servicename

        if self.servicename is None:
            raise ValueError(_('must specify a service to register'))

        if self.verbose:
            print _('Registering "%s"...') % self.servicename

        # get the AI SMF service instance information
        try:
            self.instance = smf.AISCF(FMRI="system/install/server")
        except SystemError:
            raise SystemError(_("error: the system does not have the "
                                "system/install/server SMF service"))

        # use the interfaces within the class if none are passed in
        if interfaces is None:
            interfaces = self.interfaces

        sdrefs = self._register_a_service(name=self.servicename,
                                          interfaces=interfaces,
                                          port=port,
                                          comments=comments)

        if sdrefs is not None:
            self.sdrefs[servicename] = sdrefs
            self._handle_events()
        else:
            raise AIMDNSError(cw(_('error: aiMDNSError: mDNS ad hoc '
                                   'registration failed for "%s" service')
                                   % self.servicename))

    def _signal_hup(self, signum, frame):
        '''Method: _signal_hup, class private
        Description:
            Callback invoked when SIGHUP is received

        Args
            signum - standard argument for callback, not used
            frame  - standard argument for callback, not used

        Returns
            None

        Raises
            None
        '''
        # get the new service keys and iterate over them
        services = config.get_all_service_names()
        for srv in services:
            # is this service already registered
            if srv not in self.instance_services or srv not in self.sdrefs:
                # need to register the service
                if self.verbose:
                    print _('Registering %s') % srv

                sdrefs = self._register_a_service(interfaces=self.interfaces,
                                                  name=srv)

                # save the service reference list in self.sdrefs
                if sdrefs is not None:
                    # self.sdrefs update, force restart of event loop
                    self._restart_loop = True
                    if srv in self.sdrefs:
                        self.sdrefs[srv].extend(sdrefs)
                    else:
                        self.sdrefs[srv] = sdrefs

        # check the old service keys for removed or disabled services
        for srv in self.instance_services:
            # get the service (srv) from the instance
            try:
                serv = config.get_service_props(srv)
            except KeyError:
                # not a catastrophic error for the class as additional
                # services can still be processed.  This error will be
                # caught in the service log file.
                sys.stderr.write(_('warning: No such installation service, '
                                   '%s\n') % srv)

                # remove the service references for the now non-existent
                # service that was just identified.  This can occur when
                # a service is deleted.
                if srv in self.sdrefs:
                    self._restart_loop = True
                    for sdref in self.sdrefs[srv]:
                        sdref.close()
                    del self.sdrefs[srv]

                continue

            # was the service removed or disabled
            if (srv not in services) or \
               (srv in self.sdrefs and
                serv[config.PROP_STATUS] == config.STATUS_OFF):

                if self.verbose:
                    print _('Unregistering %s') % srv

                # remove the registered service
                if srv in self.sdrefs:
                    # self.sdrefs update, force restart of event loop
                    self._restart_loop = True
                    for sdref in self.sdrefs[srv]:
                        sdref.close()
                    del self.sdrefs[srv]

        # save the new services list
        self.instance_services = services

    def register_all(self, interfaces=None):
        '''Method: register_all
           Description:
                Registers all AI services.  This method will loop until the
                the application is killed.  It responds to SIGHUP signals,
                re-checking all registered services for additions and removals
                of a service from the AI SMF service.

            Args
                interfaces  - the interfaces to register the AI services on

            Returns
                None

            Raises
                SystemError  - if the SMF service instance can not be loaded.
                AIMDNSError  - if the Instance keys are not loaded.
        '''
        self._do_lookup = False

        if self.verbose:
            print _('Registering all Auto Install services...')

        # get the AI SMF service instance information
        try:
            self.instance = smf.AISCF(FMRI="system/install/server")
        except SystemError:
            raise SystemError(_("error: the system does not have the "
                                "system/install/server SMF service"))
        self.instance_services = config.get_all_service_names()

        # use interfaces within the class if none are passed
        if interfaces is None:
            interfaces = self.interfaces

        # iterate through each service and register it
        for servicename in self.instance_services:
            sdrefs = self._register_a_service(name=servicename,
                                              interfaces=interfaces)

            # save the service reference within the class
            if sdrefs:
                if servicename in self.sdrefs:
                    self.sdrefs[servicename].extend(sdrefs)
                else:
                    self.sdrefs[servicename] = sdrefs

        signal.signal(signal.SIGHUP, self._signal_hup)
        self._handle_events()

    def browse(self):
        '''Method: browse
        Description:
            browse all available _OSInstall._tcp services.

        Args
            None

        Returns
                True  -- if a service is found -- OR --
                False -- if a service is not found -- OR --
                sdref -- if actually in find mode

        Raises
            AImDNSError - if there are no service references available
        '''
        self.sdrefs = dict()
        self._found = False
        self._resolved = list()

        # only browse over the number of interfaces available
        self.count = len(self.interfaces)

        if self.verbose:
            print _('Browsing for services...')

        # pybonjour bug -- can not Browse on a specific interfaceIndex
        # thus only Browsing on all interfaces (0).  If and when this
        # bug gets fixed up stream then the iteration over the interfaces
        # would be appropriate.  The code should look like what is in
        # the find() method.
        # Resolve the DNS service
        sdref = pyb.DNSServiceBrowse(flags=0, regtype=common.REGTYPE,
                                     domain=common.DOMAIN,
                                     interfaceIndex=0,
                                     callBack=self._browse_callback)

        # save the service reference
        if sdref:
            self.sdrefs['browse'] = [sdref]
        else:
            raise AIMDNSError(_('error: aiMDNSError: mDNS browse failed'))

        # cause the event loop to loop only 5 times
        self._do_lookup = True
        self._handle_events()

        return self._found

    def find(self, servicename=None):
        ''' Method: find
            Description:
                finds the named Auto Install service

            Returns:
                True  -- if the service is found -- OR --
                False -- if the service is not found

            Raises:
                AImDNSError - if there are no service references available
        '''
        self.sdrefs = dict()
        self._found = False
        self._lookup = True
        self.servicename = servicename if servicename else self.servicename

        # only find over the number of interfaces available
        self.count = len(self.interfaces)
        list_sdrefs = list()
        for inf in self.interfaces:
            # register the service on the appropriate interface index
            try:
                interfaceindex = netif.if_nametoindex(inf)
            except netif.NetIFError, err:
                raise AIMDNSError(err)

            sdref = pyb.DNSServiceResolve(0, interfaceindex,
                                          servicename,
                                          regtype=common.REGTYPE,
                                          domain=common.DOMAIN,
                                          callBack=self._resolve_callback)
            list_sdrefs.append(sdref)

        if list_sdrefs:
            self.sdrefs['find'] = list_sdrefs
        else:
            raise AIMDNSError(_('error: aiMDNSError: mDNS find failed'))

        if self.verbose:
            print _('Finding %s...') % self.servicename

        # cause the event loop to loop only for the number of interfaces
        self._do_lookup = True
        self._handle_events()

        return self._found

    def print_services(self):
        '''Method: print_services
        Description:
            Prints the class services dictionary.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        # ensure service list is not blank
        if not self.services:
            if self.verbose:
                print _('"%s" service not found') % self.servicename
            else:
                print _('-:%s') % self.servicename
        else:
            # iterate through the interfaces
            for inter in self.services.keys():
                services = self.services[inter]
                # iterate through the services for the interface
                for service in services:
                    if self.verbose:
                        # save all labels
                        labels = [_('fullname'), _('hosttarget'),
                                  _('port'), _('interface')]
                        if service['comments'].startswith('aiwebserver='):
                            comlabel = service['comments'].split('=')[0]
                            comvalue = service['comments'].split('=')[1]
                        else:
                            comlabel = _('comment')
                            comvalue = service['comments']
                        labels.append(comlabel)
                        # figure out the maximum width of the labels
                        maxlen = max([len(l) for l in labels])
                        # output the label = value, labels are right justified
                        print _('Service:')
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('fullname'), \
                                 service['servicename'])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('hosttarget'), \
                                 service['hosttarget'])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, _('port'), \
                                 service['port'])
                        print '\t%-*.*s = %s (%s)' % \
                                (maxlen, maxlen, _('interface'), inter, \
                                 self.interfaces[inter])
                        print '\t%-*.*s = %s' % \
                                (maxlen, maxlen, comlabel, comvalue)
                    else:
                        # output +:interface:IPv4:domain:servicename:port
                        flag = '+' if service['flags'] is True else '-'
                        print '%s:%s:%s:%s:%s:%d:%s' % \
                                (flag, inter, self.interfaces[inter], \
                                 service['domain'], service['servicename'], \
                                 service['port'], service['comments'])

    def reset(self):
        '''Method: reset
        Description:
            Resets all the class member variables to defaults.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        self._find = None
        self.services = dict()
        self.servicename = None
        self.domain = 'local'
        self.txt = None
        self.inter = None
        self.port = 0
        self._found = False
        self._lookup = False
        self.count = 0
        self.clear_sdrefs()

    def clear_sdrefs(self):
        '''Method: clear_sdrefs
        Description:
            Clears the mDNS service description references.  The side effect
            is that the mDNS records are also de-registered.

        Args
            None

        Returns
            None

        Raises
            None
        '''
        for srv in self.sdrefs.keys():
            for sdref in self.sdrefs[srv]:
                sdref.close()
        self.sdrefs = dict()
