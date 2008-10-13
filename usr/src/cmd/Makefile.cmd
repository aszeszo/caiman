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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
include $(SRC)/Makefile.master

FILEMODE = 0755

ROOTINSTALLD	= $(ROOT)/usr/sbin/install.d
ROOTDYNAMICTEST = $(ROOT)/usr/sbin/install.d/dynamic_test
ROOTMERGESCRIPTS	= $(ROOT)/usr/sbin/install.d/mergescripts
ROOTRESD	= $(ROOT)/usr/openwin/lib/locale/C/app-defaults
ROOTHELPDIR	= $(ROOT)/usr/openwin/lib/locale/C/help/install.help
ROOTHDIR	= ${ROOTHELPDIR}/${HELPTYPE}
ROOTMISC	= $(ROOT)/Misc
ROOTPATCHDB	= ${ROOTMISC}/database
ROOTAI		= $(ROOT)/Misc/jumpstart_sample
ROOTAI86	= $(ROOT)/Misc/jumpstart_sample/x86-begin.conf
ROOTTOOLS	= $(ROOT)/Tools
ROOTEA		= $(ROOT)/EA
ROOTUSRMENU	= $(ROOT)/usr/lib/locale/C/LC_MESSAGES
ROOTETC		= $(ROOT)/etc
ROOTLIBSVCMETHOD	= $(ROOT)/lib/svc/method
ROOTUSRINC	= $(ROOT)/usr/include
ROOTINITD	= $(ROOT)/etc/init.d
ROOTCDBUILD	= $(ROOT)/cdbuild
ROOTADMINBIN	= $(ROOT)/usr/snadm/bin
ROOTVARSADM	= $(ROOT)/var/sadm
ROOTVARINSTADM	= $(ROOT)/var/installadm
ROOTVARAIWEB	= $(ROOT)/var/installadm/ai-webserver
ROOTVARAIDATA	= $(ROOT)/var/installadm/ai-webserver/AI_data
ROOTMANIFEST	= $(ROOT)/var/svc/manifest
ROOTVARSVCPROFILE	= $(ROOT)/var/svc/profile
ROOTMANAPP	= $(ROOTMANIFEST)/application
ROOTMANNET	= $(ROOTMANIFEST)/network
ROOTMANNETDNS	= $(ROOTMANNET)/dns
ROOTMANNETLDAP	= $(ROOTMANNET)/ldap
ROOTMANNETNIS	= $(ROOTMANNET)/nis
ROOTMANNETRPC	= $(ROOTMANNET)/rpc
ROOTMANSYS	= $(ROOTMANIFEST)/system
ROOTMANSYSDEV	= $(ROOTMANSYS)/device
ROOTMANSYSFIL	= $(ROOTMANSYS)/filesystem
ROOTMANSYSSVC	= $(ROOTMANSYS)/svc
ROOTMANMILE	= $(ROOTMANIFEST)/milestone
ROOTSBIN	= $(ROOT)/sbin
ROOTUSRBIN	= $(ROOT)/usr/bin
ROOTUSRSBIN	= $(ROOT)/usr/sbin
ROOTUSRSBININSTALLADM	= $(ROOT)/usr/sbin/installadm
ROOTUSRSADMBIN	= $(ROOT)/usr/sadm/bin
ROOTUSRSADMLIB	= $(ROOT)/usr/sadm/lib
ROOTINSTALLBIN	= $(ROOT)/usr/sadm/install/bin
ROOTCLASSACTION = $(ROOT)/usr/sadm/install/scripts
ROOTDEVMAP 	= $(ROOT)/usr/sadm/install/devmap_scripts
ROOTICON	= $(ROOT)/usr/dt/appconfig/icons/C
ROOTTYPE	= $(ROOT)/usr/dt/appconfig/types/C
ROOTDTADMIN	= $(ROOT)/usr/dt/appconfig/appmanager/C/System_Admin
ROOTUSRDTBIN	= $(ROOT)/usr/dt/bin
ROOTUSRLIB	= $(ROOT)/usr/lib
ROOTREGBIN	= $(ROOT)/usr/dt/appconfig/sdtprodreg/bin
ROOTREGLIB	= $(ROOT)/usr/dt/appconfig/sdtprodreg/lib
ROOTREGCLASS	= $(ROOT)/usr/dt/appconfig/sdtprodreg/classes
ROOTREGL10N	= $(ROOT)/usr/dt/appconfig/sdtprodreg/classes/com/sun/prodreg

ROOTFLASHLIB	= $(ROOT)/usr/lib/flash
ROOTPATCHLIB	= $(ROOT)/usr/lib/patch

ROOTLUBIN	= $(ROOT)/usr/lib/lu
ROOTLUHELP	= $(ROOT)/usr/lib/lu/help/C
ROOTLUMENU	= $(ROOT)/usr/lib/lu/menu
ROOTLUTEST	= $(ROOT)/usr/lib/lu/test
ROOTLUTESTUTIL	= $(ROOT)/usr/lib/lu/test/util
ROOTETCLIBLUPLUGINS	= $(ROOTETCLIBLU)/plugins
ROOTLUETC	= $(ROOTETC)/lu
ROOTLUXMLDTD	= $(ROOT)/usr/share/lib/xml/dtd
ROOTDEFAULT	= $(ROOT)/etc/default
ROOTUSRSADMBIN	= $(ROOT)/usr/sadm/bin
ROOTWBEMMOF	= $(ROOT)/usr/sadm/mof
ROOTWBEMLIB	= $(ROOT)/usr/sadm/lib/wbem
ROOTWBEMIMAGE	= $(ROOT)/usr/sadm/lib/wbem/images
ROOTWBEMHELP	= $(ROOT)/usr/sadm/lib/wbem/help
ROOTWBEMDOC	= $(ROOT)/usr/sadm/lib/wbem/doc
ROOTWBEMSDKDOC	= $(ROOT)/usr/sadm/lib/wbem/sdkdoc
ROOTWBEMEXT	= $(ROOT)/usr/sadm/lib/wbem/extension
ROOTWBEMINCLUDE	= $(ROOT)/usr/sadm/lib/wbem/include
ROOTWBEMAPPCOMM = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/apps/common
ROOTWBEMAPPADMN = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/apps/wbemadmin
ROOTWBEMCIMCLNT = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/client
ROOTWBEMPUTLOG  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/utility/log
ROOTWBEMPUTDTBL = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/utility/directorytable
ROOTWBEMPUTCOMM = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/utility/common
ROOTWBEMPSSPORT = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/serialport
ROOTWBEMPSPERF  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/perfmon
ROOTWBEMPSPROC  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/process
ROOTWBEMPSLOGS  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/logsvc
ROOTWBEMPSFS    = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/fsmgr/common
ROOTWBEMPSUSER  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/usermgr/common
ROOTWBEMPSOSS   = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/osserver
ROOTWBEMPSPROJ  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/project
ROOTWBEMPSPATCH = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/patch
ROOTWBEMPSCOMM  = $(ROOT)/usr/sadm/lib/wbem/com/sun/wbem/solarisprovider/common
ROOTUSRHELPAUTH	= $(ROOT)/usr/lib/help/auths/locale/C
ROOTUSRHELPPROF	= $(ROOT)/usr/lib/help/profiles/locale/C

ROOTINSTALLDPROG= $(PROG:%=$(ROOTINSTALLD)/%)
ROOTHELPFILES	= $(HELPFILES:%=${ROOTHDIR}/%)
ROOTMISCPROG    = $(PROG:%=$(ROOTMISC)/%)
ROOTPATCHDBFILES= $(FILES:%=$(ROOTPATCHDB)/%)
ROOTAIPROG	= $(PROG:%=$(ROOTAI)/%)
ROOTAIFILES	= $(FILES:%=$(ROOTAI)/%)
ROOTAI86FILES	= $(FILES:%=$(ROOTAI86)/%)
ROOTCDBUILDFILES= $(FILES:%=$(ROOTCDBUILD)/%)
ROOTCDBUILDPROG = $(PROG:%=$(ROOTCDBUILD)/%)
ROOTUSRBINPROG	= $(PROG:%=$(ROOTUSRBIN)/%)
ROOTUSRINCHDRS	= $(EXPHDRS:%=$(ROOTUSRINC)/%)
ROOTUSRSBINPROG	= $(PROG:%=$(ROOTUSRSBIN)/%)
ROOTUSRSBINFILES = $(FILES:%=$(ROOTUSRSBIN)/%)
ROOTUSRSADMBINPROG=$(PROG:%=$(ROOTUSRSADMBIN)/%)
ROOTUSRSADMLIBPROG=$(PROG:%=$(ROOTUSRSADMLIB)/%)
ROOTICONFILES	= $(ICONS:%=$(ROOTICON)/%)
ROOTTYPEFILES	= $(TYPES:%=$(ROOTTYPE)/%)
ROOTDTADMINFILES = $(ADMIN:%=$(ROOTDTADMIN)/%)
ROOTUSRDTBINFILES = $(PROG:%=$(ROOTUSRDTBIN)/%)
ROOTREGBINFILES	= $(REG:%=$(ROOTREGBIN)/%)
ROOTREGLIBFILES	= $(REG:%=$(ROOTREGLIB)/%)
ROOTREGCLASSFILES = $(REG:%=$(ROOTREGCLASS)/%)
ROOTREGL10NFILES = $(REGL10N:%=$(ROOTREGL10N)/%)

ROOTFLASHLIBPROG = $(PROG:%=$(ROOTFLASHLIB)/%)
ROOTPATCHLIBPROG = $(PROG:%=$(ROOTPATCHLIB)/%)

ROOTLUBINPROG	= $(PROG:%=$(ROOTLUBIN)/%)
ROOTLUHELPFILES	= $(FILES:%=$(ROOTLUHELP)/%)
ROOTLUMENUFILES	= $(FILES:%=$(ROOTLUMENU)/%)
ROOTLUETCFILES	= $(FILES:%=$(ROOTLUETC)/%)
ROOTETCLIBFILES	= $(FILES:%=$(ROOTETCLIB)/%)
ROOTETCLIBLUFILES	= $(FILES:%=$(ROOTETCLIBLU)/%)
ROOTETCLIBLUPLUGINSFILES	= $(FILES:%=$(ROOTETCLIBLUPLUGINS)/%)

ROOTSBINPROG	= $(PROG:%=$(ROOTSBIN)/%)
ROOTSBINFILES	= $(FILES:%=$(ROOTSBIN)/%)
ROOTAUTHHELPFILES = $(HELPFILES:%=$(ROOTUSRHELPAUTH)/%)
ROOTPROFHELPFILES = $(HELPFILES:%=$(ROOTUSRHELPPROF)/%)
ROOTETCLIBLUPROG	= $(PROG:%=$(ROOTETCLIBLU)/%)
ROOTETCLIBLUPLUGINSPROG	= $(PROG:%=$(ROOTETCLIBLUPLUGINS)/%)

$(ROOTHELPFILES) :=     FILEMODE = 0444
$(ROOTHELPFILES) :=     OWNER = root
$(ROOTHELPFILES) :=     GROUP = bin

# QA partner support
QAPINCPATH11	= -I/net/rmtc.sfbay/usr/rmtc/QApartner/qap_1.1/partner/include
QAPLIBPATH11	= -L/net/rmtc.sfbay/usr/rmtc/QApartner/qap_1.1/partner/lib
QAPINCPATH20	= -I/net/rmtc.sfbay/usr/rmtc/QApartner/qap_2.0/partner/include
QAPLIBPATH20	= -L/net/rmtc.sfbay/usr/rmtc/QApartner/qap_2.0/partner/lib

X_CFLAGS        = -I$(OPENWINHOME)/include
MOTIF_CFLAGS    = -I$(MOTIFHOME)/include
NIHINC          = -I$(ROOT)/usr/include/nihcl
ADMININC        = -I../../lib/libadmobjs
SNAGINC		= -I$(ROOT)/usr/include/admin

X_LIBPATH       = -L$(OPENWINHOME)/lib
MOTIF_LIBPATH   = -L$(MOTIFHOME)/lib
NIHLIB          = -L$(ROOT)/usr/lib
ADMLIB          = -L$(ROOT)/usr/lib
SNAGLIB         = -L$(ROOT)/usr/snadm/classes/lib

RLINK_PATH	= -R/usr/snadm/lib:/usr/lib:/usr/openwin/lib:/usr/dt/lib

LDLIBS.cmd	= -L$(ROOTUSRLIB) -L$(ONLIBDIR) -L$(ONUSRLIBDIR)

ROOTLIB=	$(ROOTUSRLIB)
ROOTAPPDEFAULTS = $(ROOT)/usr/dt/lib/app-defaults
ROOTAPPDEFAULTSPROG = $(PROG:%=$(ROOTAPPDEFAULTS)/%)

ROOTSHFILES=	$(SHFILES:%=$(ROOTBIN)/%)
ROOTLIBPROG=	$(PROG:%=$(ROOTLIB)/%)
ROOTETCPROG=	$(PROG:%=$(ROOTETC)/%)
ROOTADMINBINPROG = $(PROG:%=$(ROOTADMINBIN)/%)

MOTIFLIB_NAME	= Xm
