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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

'''Python package for icts'''

__all__ = ["apply_sysconfig", "boot_archive", "cleanup_cpio_install",
           "common", "create_snapshot", "device_config", "initialize_smf",
	   "ips", "setup_swap", "transfer_files", "update_dumpadm"]

from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.target import Target
from solaris_install.target.logical import BE

# Define some ICT constants
BOOTADM = '/usr/sbin/bootadm'
DEVFSADM = '/usr/sbin/devfsadm'
DUMPADM_CONF = 'etc/dumpadm.conf'
GENERIC_XML = 'etc/svc/profile/generic.xml'
GEN_LTD_NET_XML = 'generic_limited_net.xml'
INETD_XML = 'inetd_generic.xml'
INETD_SVCS_XML = 'etc/svc/profile/inetd_services.xml'
KBD_DEFAULT = 'US-English'
KBD_DEV = '/dev/kbd'
KBD_LAYOUT_FILE = '/usr/share/lib/keytables/type_6/kbd_layouts'
MNTTAB = 'etc/mnttab'
NAME_SVC_XML = 'etc/svc/profile/name_service.xml'
NS_DNS_XML = 'ns_dns.xml'
NS_FILES_XML = 'ns_files.xml'
PKG = '/usr/bin/pkg'
PLATFORM_XML = 'etc/svc/profile/platform.xml'
PLATFORM_NONE_XML = 'platform_none.xml'
PROFILE_DEST = 'etc/svc/profile/site'
PROFILE_SITE = 'etc/svc/profile/site.xml'
REPO_DB = 'etc/svc/repository.db'
SC_PROFILE = 'etc/svc/profile/sc_profile.xml'
SVCCFG = '/usr/sbin/svccfg'
SVCCFG_DTD = 'SVCCFG_DTD'
SVCCFG_REPOSITORY = 'SVCCFG_REPOSITORY'
SVC_BUNDLE = 'usr/share/lib/xml/dtd/service_bundle.dtd.1'
SVC_REPO = 'etc/svc/repository.db'
SYS = 'sys'
VFSTAB = 'etc/vfstab'

# Variables associated with the package image
DEF_REPO_URI = "http://pkg.oracle.com/solaris/release"
PKG_CLIENT_NAME = "ICT"


class ICTError(Exception):
    '''Base class for ict specific errors'''
    pass


class ICTApplySysConfigError(ICTError):
    '''Errors thrown by apply_sysconfig'''
    pass


class ICTBaseClass(AbstractCheckpoint):
    '''ICTBaseClass is the abstract base class for the ICTs. It
       provides basic functionality for all ICTs.
    '''

    def __init__(self, name):
        '''Initializes the class
           Parameters:
               -name - this arg is required by the AbstractCheckpoint
                       and is not used by the ict checkpoint.
        '''
        super(ICTBaseClass, self).__init__(name)

        # The DOC instance from the engine
        self.doc = InstallEngine.get_instance().data_object_cache

        # The boot environment name for the target
        self.boot_env = None

        # The install target object and target directory
        self.target = None
        self.target_dir = None

    def parse_doc(self):
        '''Get the parameters needed by the ICTs'''

        # Get the target that holds the boot environment
        self.target = self.doc.get_descendants(name=Target.DESIRED,
                                               class_type=Target,
                                               not_found_is_err=True)[0]

        # Get the destination mountpoint
        self.boot_env = self.target.get_descendants(class_type=BE,
                                                    max_count=1,
                                                    not_found_is_err=True)[0]
        # Get the target directory
        self.target_dir = self.boot_env.mountpoint

    def execute(self, dry_run=False):
        '''The AbstractCheckpoint requires this method. It is
           implemented uniquely in each ICT.
        '''
        pass

    def get_progress_estimate(self):
        '''
            The AbstractCheckpoint class requires this method
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.

            For most ICTs, 1 is an accurate estimation. For those
            that need a different value will implement their own version
            of get_progress_estimate.
        '''
        return 1
