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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
This file contains the code necessary to convert an AI server configuration
from S11 Express to S11 FCS.  The changes made convert any existing AI
services, clients, and DHCP configuration created before installing S11 FCS.
"""
import fileinput
import glob
import logging
import optparse
import os
import re
import shutil
import socket
import struct
import sys
import tempfile

import osol_install.auto_install.AI_database as AIdb
import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.dhcp as dhcp
import osol_install.auto_install.installadm_common as com
import osol_install.libaiscf as smf

from osol_install.auto_install import create_client
from osol_install.auto_install.installadm_common import _
from osol_install.auto_install.service import AIService
from solaris_install import Popen, CalledProcessError

VERSION = _("%prog: version 1.0")

# old AI service property group keys and values
PROP_BOOT_FILE = 'boot_file'
PROP_DEF_MANIFEST = 'default-manifest'
PROP_IMAGE_PATH = 'image_path'
PROP_SERVICE_NAME = 'service_name'
PROP_STATUS = 'status'
PROP_TXT_RECORD = 'txt_record'
PROP_VERSION = 'version'

EXIT_SUCCESS = 0
EXIT_FAILURE = 1

DEFAULT_LOG_LEVEL = logging.WARN
DEBUG_LOG_LEVEL = logging.DEBUG
TFTPBOOT = '/tftpboot'
NETBOOT = '/etc/netboot'
SERVICE_DIR = '/var/ai/service'
AI_SVC_FMRI = 'system/install/server:default'
ISC_DHCP_CONFIG = '/var/ai/isc_dhcp.conf'
NETBOOT_ERR = """Conversion continuing.  To manually complete this step:
    Move all required non Automated Install file from /tftpboot to /etc/netboot
    Delete /tftpboot
    Create /tftpboot as a symlink to /etc/netboot\n"""


class ServiceConversionError(Exception):
    """
    Some type of error occurred while upgrading an AI service.  The exact cause
    of the error should have been logged.
    """
    pass


class SUNDHCPData:
    """
    Class to query Solaris DHCP server configuration material
    """

    def __init__(self):
        """
        No state stored and this is server wide data, so do not make an
        instance of this class
        """
        raise NotImplementedError("class does not support "
                                  "creating an instance.")

    class DHCPError(Exception):
        """
        Class to report various DHCP related errors
        """
        pass

    @staticmethod
    def _unpack_addr(ipaddr):
        """
        Return the integer equivalent of the input ascii IP address
        """
        return struct.unpack('L', socket.inet_aton(ipaddr))[0]

    @staticmethod
    def _pack_addr(ipaddr):
        """
        Return the ascii IP address equivalent of the input value
        """
        return socket.inet_ntoa(struct.pack('L', ipaddr))

    @staticmethod
    def generate_ip_ranges(clients):
        """
        Generate the set of ip ranges from the list of clients
        """
        ranges = list()
        in_range = False
        last_ip_tuple = -2

        # Set up a regular expression to pull the last tuple from an IP
        regexp = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.(\d{1,3})$")

        # Get a sorted list of the ip addresses by unpacking, sorting, and
        # then returning it to its original form
        sorted_clients = map(SUNDHCPData._pack_addr,
            sorted([SUNDHCPData._unpack_addr(client) for \
            client in clients['Client IP']]))
        last_addr = ''
        start_addr = ''
        for client_addr in sorted_clients:
            # Create a list of dictionaries each containing the range and the
            # server IP for that range
            m = regexp.match(client_addr)
            if m is None:
                raise SUNDHCPData.SUNDHCPError("generate_ip_ranges: bad IP "
                                               "format [%s]" % client_addr)

            client_ip_tuple = m.group(1)
            # Is this tuple part of the current range
            if int(client_ip_tuple) != int(last_ip_tuple) + 1:
                if in_range:
                    ranges.append({'nextserver': clients['Server IP'][0],
                                  'loaddr': start_addr, 'hiaddr': last_addr})
                    in_range = False
                start_addr = client_addr
            else:
                in_range = True

            last_addr = client_addr
            last_ip_tuple = client_ip_tuple

        if in_range:
            ranges.append({'nextserver': clients['Server IP'][0],
                          'loaddr': start_addr, 'hiaddr': last_addr})

        return ranges

    @staticmethod
    def subnets():
        """
        Return a list of networks configured on the DHCP server, if any error
        is generated raise it as a DHCPError.
        """
        # first get a list of networks served
        cmd = ["/usr/sbin/pntadm", "-L"]
        try:
            pipe = Popen.check_call(cmd, stdout=Popen.STORE,
                                    stderr=Popen.DEVNULL)
        except CalledProcessError as err:
            # return a DHCPError on failure
            raise SUNDHCPData.DHCPError(err)

        # produce a list of networks like
        # ["172.20.24.0",
        #  "172.20.48.0"]
        #
        # get the list of clients, sort it and generate the IP ranges
        subnets = dict()
        for net in pipe.stdout.split():
            try:
                clients = SUNDHCPData.clients(net)
            except SUNDHCPData.DHCPError as err:
                sys.stderr.write(str(err) + "\n")
                continue

            # Produce a dictionary of the form:
            #  {<subnet>:[{start_ip: <ip addr> count:<num>}...]}
            try:
                subnets[net] = SUNDHCPData.generate_ip_ranges(clients)
            except SUNDHCPData.DHCPError as err:
                sys.stderr.write(str(err) + "\n")
                continue

        return subnets

    @staticmethod
    def _get_include_vals(name, macros):
        """
        Expand the include keyword with it's underlying key/value pairs in
        the macro that includes it.
        """
        include_expansion = dict()
        # Expansion is done only on 'Include' keywords
        if 'Include' in macros[name]:
            # Add the value of the Include keyword expansion
            include_value = macros[name]['Include']
            include_expansion.update(macros[include_value])
            # Recursively call this method to pick up any embedded Includes
            include_expansion.update(SUNDHCPData._get_include_vals(
                                  include_value, macros))

        return include_expansion

    @staticmethod
    def _parse_macro_options(macro_vals):
        """
        Parse the macro values into a dictionary to be used in generating the
        ISC configuration
        """
        # translation table to change keywords in the Solaris DHCP
        # configuration tables correspond to those expected when creating the
        # ISC DHCP stanzas
        keyword_map = {'Subnet': 'netmask',
                       'Router': 'routers',
                       'Broadcst': 'broadcast',
                       'BootFile': 'bootfile',
                       'DNSdmain': 'domainname',
                       'DNSserv': 'nameservers'}

        keyval_dict = dict()
        for keyval in macro_vals[1:-1].split(':'):
            key_pair = keyval.split('=')
            if len(key_pair) != 2:
                continue

            # Add the entry into the dict making sure to translate the
            # key names if they are in the translation table otherwise
            # keep the original keyword name. Remove any enclosing quotes
            keyval_dict[keyword_map.get(key_pair[0], key_pair[0])] = \
                key_pair[1].replace('"', '')

        return keyval_dict

    @staticmethod
    def macros():
        """
        Returns a dictionary of macros and symbols with keys: Name, Type and
        Value. In case of an error raises a DHCPError
        """
        # get a list of all server macros
        cmd = ["/usr/sbin/dhtadm", "-P"]
        try:
            pipe = Popen.check_call(cmd, stdout=Popen.STORE,
                                    stderr=Popen.DEVNULL)
        except CalledProcessError as err:
            raise SUNDHCPData.DHCPError(err)

        # produce a list like:
        # ['Name", "Type", "Value",
        #  "==================================================",
        #  "0100093D143663", "Macro",
        #  ":BootSrvA=172.20.25.12:BootFile="0100093D143663":"]

        # split into fields and create a dictionary with the name and 
        # keyword/value pairs
        config_list = [ln.split(None, 2) for ln in
                       pipe.stdout.splitlines()][2:]
        macro_dict = dict()
        # Create a dictionary that contains {name: {key:val, ...}}
        for config_line in config_list:
            if config_line[1] == 'Macro':
                macro_dict[config_line[0]] = \
                    SUNDHCPData._parse_macro_options(config_line[2])

        # Each Solaris DHCP macro is comprised of keyword value pairs as 
        # shown above.  The following block will expand the Include keyword
        # into its keyword value pairs
        # {v20z-brm-02 :  {Include : Locale, Timeserv : 10.80.127.2}
        #  Locale : {UTCoffset : -25200}}
        # will be expanded to  
        # {v20z-brm-02 : {UTCoffset : -25200, Timeserv : 10.80.127.2} ...}
        for mname in macro_dict:
            # Add the expansion of the Include keywords to the macro
            macro_dict[mname].update(
                SUNDHCPData._get_include_vals(mname, macro_dict))
            # If this entry contains the 'netmask' keyword then the
            # macro name is a subnet specification.  This is needed to form
            # the ISC DHCP subnet stanza so add it to the dictionary
            if 'netmask' in macro_dict[mname]:
                macro_dict[mname].update({"subnet": mname})
        return macro_dict

    @staticmethod
    def clients(net):
        """
        Return a dictionary with keys 'Client ID', 'Flags', 'Client IP',
        'Server IP', 'Lease Expiration', 'Macro', 'Comment', on error raise a
        DHCPError
        """
        # iterate over the networks looking for clients
        # keep state in the dictionary so initialize it out side the loop
        systems = dict()
        cmd = ["/usr/sbin/pntadm", "-P", net]
        try:
            pipe = Popen.check_call(cmd, stdout=Popen.STORE,
                                    stderr=Popen.DEVNULL)
        except CalledProcessError as err:
            raise SUNDHCPData.DHCPError(err)

        # use split to produce a list like:
        # ['Client ID', 'Flags', 'Client IP', 'Server IP',
        #  'Lease Expiration', 'Macro', 'Comment']
        # ['']
        # ['01001B21361F85', '00', '172.20.24.228', '172.20.25.12',
        #  '08/21/2009', 'dhcp_macro_clay_ai_x86', '']
        # ['0100093D1432AD', '01', '172.20.24.214', '172.20.25.12',
        #  '08/21/2009', 'dhcp_macro_clay_ai_sparc', '']
        # ['01002128262DD2', '00', '172.20.24.215', '172.20.25.12',
        #  '08/21/2009', 'install', '']
        # ['']

        # split on newlines, then split on tabs (for a maximum of 7 fields)
        systems['out'] = [ln.split("\t", 6) for
            ln in pipe.stdout.splitlines()]

        # the first line will be the headers
        headers = systems['out'][0]
        # strip white space
        headers = [obj.strip() for obj in headers]

        # strip headers, intermediate blank and footer blank
        del(systems['out'][0:2])

        # build a dict with each header a key to a list built of each row
        systems['data'] = dict(zip(headers, [[row[i] for row in systems['out']]
                               for i in range(0, len(headers))]))

        # strip white space in data
        for key in systems['data']:
            systems['data'][key] = [obj.strip()
                                   for obj in systems['data'][key]]
        return systems['data']


def find_tftp_root():
    """
    Uses get_exec_prop to get tftp root directory via the property
    inetd_start/exec.

    Args
        None

    Returns
        directory name (type string) - default /tftpboot

    Raises
        None
    """
    return get_exec_prop().partition(" -s\ ")[2] or TFTPBOOT


class VFSTab(com.DBBase):
    """
    Implements object oriented access to the /etc/vfstab file. One can query
    fields through dictionary style key look-ups (i.e. vfstab_obj['DEVICE']) or
    attribute access such as vfstab_obj.fields.DEVICE both return lists which
    are indexed so that a line from the file can be reconstructed as
    vfstab_obj[device][idx]\tvfstab_obj[fsckDevice]...
    Otherwise, one can read and write the entire file via
    vfstab_obj.file_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but using the attribute,
    etc. to allow the implementation to evolve, if necessary.

    One can remove a record in the file by running:
    del(vfstab_obj.fields.FIELD[idx])
    """
    # field variables
    _DEVICE = "device to mount"
    _FSCK_DEVICE = "device to fsck"
    _MOUNT_POINT = "mount point"
    _FS_TYPE = "FS type"
    _FSCK_PASS = "fsck pass"
    _MOUNT_AT_BOOT = "mount at boot"
    _FS_OPTS = "mount options"

    # the order of headers from the file needs to be recorded
    _headers = [_DEVICE, _FSCK_DEVICE, _MOUNT_POINT, _FS_TYPE, _FSCK_PASS,
        _MOUNT_AT_BOOT, _FS_OPTS]

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys()
        if obj.isupper() and locals()[obj] is not None]

    def __init__(self, file_name="/etc/vfstab", mode="r"):
        super(VFSTab, self).__init__(file_name=file_name, mode=mode)


class GrubMenu(com.DBBase):
    """
    Class to handle opening and reading GRUB menu, see
    http://www.gnu.org/software/grub/manual/grub.html for more on GRUB menu
    format
    Keys will be the grub menu entries and key "" will be the general commands
    which begins the menu before the first title
    """

    # field variables
    _TITLE = "title"

    # the order of headers from the file needs to be recorded
    _headers = [_TITLE]

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys()
        if obj.isupper() and locals()[obj] is not None]

    # overload the _Result class to be a dictionary instead of the default list
    class _Result(dict):
        """
        Wrap dict class to ignore the parent reference passed to the _Result
        class (which would normally be used for updating the backing store of a
        DBBase() instance)
        """
        def __init__(self, parent, key):
            # store what we are representing (initialize a dictionary with the
            # data to store)
            super(GrubMenu._Result, self).__init__(
                super(com.DBBase, parent).get(key))

    def __init__(self, file_name="/boot/grub/menu.lst", mode="r"):
        super(GrubMenu, self).__init__(file_name=file_name, mode=mode)

    def _load_data(self):
        """
        Load each entry and the keys for each grub menu entry (such as module,
        kernel$, splashimage, etc. lines)
        Miscellaneous note: the module and kernel lines may have a '$' after
        them or not, consumer beware
        """
        # see if the file has changed since last read
        if self.mtime == self.file_obj.last_update:
            return

        # file has changed since last read
        file_data = self.file_obj.read_all()

        # update the file mtime to keep track
        self.mtime = self.file_obj.last_update

        # need to clear current entries
        super(com.DBBase, self).clear()

        # the menu begins with general commands. The keyword "title" must
        # begin boot entries and they are either terminated by other title
        # entries or the end of the file. Split on the title keyword as such
        # (first "entry" from the split contains the general commands and is
        # not an actual entry therefore, but prepend a "\n" in case we have no
        # general commands)
        entries = re.compile("\n\s*title\s*").split("\n" + file_data)
        # check that we got a general commands section and at least one title
        # if not, return an empty dictionary
        if len(entries) < 2:
            return dict()

        # parse each entry splitting title and data off - expecting all title
        # lines to be followed by at least one line of keyword data
        # produces a list of lists: [entry title, [entry lines]]
        entry_data = [[entry.split('\n', 1)[0], entry.split('\n')[1:]] for
            entry in entries]

        # add to self a list of [entry title, dictionary]
        # with the dictionary containing GRUB keywords as keys and the
        # values of those keys being the keyword arguments
        for (title, entry) in entry_data:

            # hold key/value tags in a dictionary for this entry
            entry_dict = dict()

            # iterate over all lines
            for line in entry:
                # skip empty lines or comments
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                # some GRUB menus have things like
                # timeout = 30 opposed to timeout 30, replace the = with a
                # space
                line = re.sub('^(?P<key>[^\s=]*?)=', '\g<key> ', line)
                entry_dict.update([line.lstrip().split(None, 1)])

            # add this GRUB entry to the GrubMenu object's dict
            # key is the entry's title and entry_dict is its object
            super(com.DBBase, self).update({title: entry_dict})

    # provide the entries of the grub menu as a property
    @property
    def entries(self):
        """
        Return a list of all Grub title entries in the GRUB menu
        """
        # need to return all keys except "" which are the general menu commands
        return filter(bool, self.keys())


def which_arch(path):
    """
    Looks to see if the platform pointed to by path is x86 or sparc.
    If the path does not exist then we are unable to determine the
    architecture.

    Args
        path = directory path to examine

    Returns
        x86     if <path>/platform/i86pc exists
        sparc   if <path>/platform/sun4v exists
        -       if neither exists

    Raises
        None
    """
    platform = os.path.join(path, 'platform/i86pc')
    for root, dirs, files in os.walk(platform):
        if 'i86pc' in dirs or 'amd64' in dirs:
            return 'i386'
        elif 'sun4v' in dirs or 'sun4u' in dirs:
            return 'sparc'
        else:
            return '-'


def get_exec_prop():
    """
    Uses svcprop on the service svc:/network/tftp/udp6 to get
    tftp root directory via the property inetd_start/exec.
    The svcprop command is either (stdout):

        /usr/sbin/in.tftpd -s /tftpboot\n

    Or (stderr):

        svcprop: Pattern 'tftp/udp6' doesn't match any entities

    Args
        None

    Returns
        directory name (type string) - default /tftpboot

    Raises
        None
    """

    cmd = ["/usr/bin/svcprop", "-p", "inetd_start/exec", "tftp/udp6"]
    try:
        pipe = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL)
    except CalledProcessError:
        sys.stderr.write(_('%s: warning: unable to locate SMF service '
                           'key property inetd_start/exec for '
                           'tftp/udp6 service. Using default value.\n') %
                           os.path.basename(sys.argv[0]))
        exec_line = ''
    else:
        # remove the '\n' character
        exec_line = pipe.stdout.rstrip("\n")

    return exec_line


def set_exec_prop(val):
    """
    Uses svccfg to set the specified inetd_start/exec property value

    Args
        prop_name - property to set
        prop_value - value to set property to

    Returns
        None

    Raises
        None
    """

    cmd = ['/usr/sbin/svccfg', '-s', 'tftp/udp6', 'setprop',
           'inetd_start/exec="%s"' % val]

    try:
        Popen.check_call(cmd, stdout=Popen.STORE,
            stderr=Popen.STORE, logger='',
            stderr_loglevel=logging.DEBUG)
    except CalledProcessError:
        sys.stderr.write(_('%s: warning: Unable to set the value of '
                           'key property inetd/start_exec for '
                           'tftp/udp6 service to "%s"\n' %
                           (os.path.basename(sys.argv[0]), val)))


def del_prop_group(ai_service, dry_run):
    """
    Remove a property group from the AI service
    Input:
        ai_service - An AI service property group name
    Return:
        None

    """
    pg_name = 'AI' + ai_service
    print _('Delete SMF property %s') % pg_name
    if not dry_run:
        cmd = ['/usr/sbin/svccfg', '-s', AI_SVC_FMRI, 'delprop', pg_name]

        try:
            Popen.check_call(cmd, stdout=Popen.STORE,
                stderr=Popen.STORE, logger='',
                stderr_loglevel=logging.DEBUG)
        except CalledProcessError as err:
            sys.stderr.write(_('%s failed with: %s') % (cmd, err.popen.stderr))
            sys.stderr.write(_('%s: warning: Unable to delete the '
                               'property group: %s' % (cmd, pg_name)))


def remove_boot_archive_from_vfstab(ai_service, service):
    """
    Remove boot_archive file system from vfstab
    """

    # check that we have a valid tftpboot directory and set base_dir to it
    base_dir = find_tftp_root()
    if not base_dir:
        sys.stderr.write(_("Unable to remove the vfstab entries for " +
                          "install boot archives\nwithout a valid " +
                          "tftp root directory.\n"))
        return

    # if we have a boot_file use it instead of serviceName for paths
    service_name = service.get('boot_file', ai_service)
    try:
        service_name = service['boot_file']
    except KeyError:
        service_name = ai_service

    # Use GRUB menu to check for boot_archive, see that it exists
    grub_menu_prefix = "menu.lst."
    grub_menu = grub_menu_prefix + service_name
    if not os.path.exists(os.path.join(
                          base_dir, grub_menu)):
        sys.stderr.write(_("Unable to find GRUB menu at %s, and thus " +
                          "unable to find boot archive.\n") % grub_menu)
    else:
        # check the menu.lst file for the boot archive(s) in use
        menu_lst = GrubMenu(file_name=os.path.join(base_dir, grub_menu))

        # iterate over both module and module$ of the service's grub menus
        # looking for boot_archive
        for boot_archive in set(menu_lst[entry].get('module') or
                                menu_lst[entry].get('module$') for
                                entry in menu_lst.entries):

            # boot_archive will be relative to /tftpboot so will appear to
            # be an absolute path (i.e. will have a leading slash) and will
            # point to the RAM disk
            boot_archive = base_dir + "/" + \
                           boot_archive.split(os.path.sep, 2)[1]

            # see if it is a mount point
            # os.path.ismount() doesn't work for a lofs FS so use
            # /etc/mnttab instead
            if boot_archive in com.MNTTab().fields.MOUNT_POINT:
                # unmount filesystem
                try:
                    cmd = ["/usr/sbin/umount", boot_archive]
                    Popen.check_call(cmd, stdout=Popen.STORE,
                        stderr=Popen.STORE, logger='',
                        stderr_loglevel=logging.DEBUG,
                        check_result=Popen.SUCCESS)

                # if run_cmd errors out we should continue
                except CalledProcessError as err:
                    sys.stderr.write(str(err) + "\n")
                    sys.stderr.write(_("Unable to unmount boot archive %s" +
                        " for service\n") % os.path.join(base_dir,
                        boot_archive))

            # boot archive directory not a mountpoint
            else:
                sys.stderr.write(_("Boot archive %s for service is " +
                                  "not a mountpoint.\n") %
                                  os.path.join(base_dir, boot_archive))

            try:
                vfstab_obj = VFSTab(mode="r+")
            except IOError as err:
                sys.stderr.write(str(err) + "\n")
                return
            # look for filesystem in /etc/vfstab
            try:
                # calculate index for mount point
                idx = vfstab_obj.fields.MOUNT_POINT.index(boot_archive)
                try:
                    # remove line containing boot archive (updates /etc/vfstab)
                    del(vfstab_obj.fields.MOUNT_POINT[idx])
                except IOError as err:
                    sys.stderr.write(str(err) + "\n")
            # boot archive was not found in /etc/vfstab
            except (ValueError, IndexError):
                sys.stderr.write(_("Boot archive (%s) for service %s " +
                                  "not in vfstab.\n") %
                              (boot_archive, service_name))


def generate_new_service_name(services, ai_service):
    """
    Generate a unique service name based on ai_service
    """
    new_service_name = ai_service
    iter = 1
    while new_service_name in services:
        new_service_name = ai_service + '_%s' % iter
        iter = iter + 1

    return new_service_name


def find_sparc_clients(lservices, sname=None):
    """
    find_sparc_clients() searches /etc/netboot for all clients and
    returns a dictionary that contains a list of dictionaries.

    The service name is the key for the main dictionary and the
    client and image path are members of the subdictionary.  The
    dictionary will look something like:

        {
            'service1': [
                        { 'ipath':<path1>, 'client':<client1> },
                        ....
                        ],
            ....
        }

    The information is spread out across a couple of different
    files within the server.  The Client is embedded within a
    directory path (/etc/netboot/<IP Network>/01<client>).  The
    Image Path is in the wanboot.conf file pointed to by the
    Client path.  The Service Name is contained in the install.conf
    file pointed to by the Image Path.

    We first get the IP addresses for the host.  Then while only
    using IPv4 address we iterate over the client directories within
    /etc/netboot/<IP Network> to get the Image Path and Service Name.
    The client and image path are then added to the named service
    dictionary list.

    Args
        lservices =
        sname =

    Returns
        dictionary of a list of dictionaries

    Raises
        None
    """

    INSTALLCONF = 'install.conf'
    WANBOOTCONF = 'wanboot.conf'

    def get_image_path(lpath):
        """
        gets the Image Path for the client pointed to by lpath.
        The Image Path on sparc is stored in the wanboot.conf file.

        Args
            lpath = path for directory which contains wanboot.conf file

        Returns
            image path for client

        Raises
            None
        """
        try:
            confpath = os.path.join(lpath, WANBOOTCONF)
            sinfo = os.stat(confpath)
            with open(confpath) as filepointer:
                fstr = filepointer.read(sinfo.st_size)
        except (OSError, IOError):
            sys.stderr.write("Error: while accessing wanboot.conf file "
                             "(%s/wanboot.conf)\n" % lpath)
            return

        start = fstr.find('boot_file=') + len('boot_file=')
        end = fstr[start:].find('/platform')

        return fstr[start:start + end]

    def get_service_name(lpath):
        """
        gets the Service Name for the client from the lpath pointed
        to by the wanboot.conf file.  The Service Name is in the
        Image Path install.conf file.

        Args
            lpath = path to directory containing install.conf file

        Returns
            install service for client

        Raises
            None
        """
        try:
            confpath = os.path.join(lpath, INSTALLCONF)
            sinfo = os.stat(confpath)
            with open(confpath) as filepointer:
                fstr = filepointer.read(sinfo.st_size)
        except (OSError, IOError):
            sys.stderr.write("Error: while accessing "
                             "install.conf file\n")
            return

        start = fstr.find('install_service=') + len('install_service=')
        end = fstr[start:].find('\n')

        return fstr[start:start + end]

    # start of find_sparc_clients
    if not os.path.exists(NETBOOT):
        return dict()

    sdict = dict()
    hostname = socket.getfqdn()
    ipaddr = socket.gethostbyname(hostname)
    # get the Network IP path for the host
    end = ipaddr.rfind('.')
    compatibility_path = os.path.join(NETBOOT, ipaddr[:end] + '.0')

    for path in [compatibility_path, NETBOOT]:
        if not os.path.exists(path) or not os.path.isdir(path):
            continue
        for clientdir in os.listdir(path):
            if not clientdir.startswith('01'):
                continue
            # strip off the 01 in the clientdir
            client = AIdb.formatValue('mac', clientdir[2:])

            # get the Image from the clientdir/wanboot.conf file
            ipath = get_image_path(os.path.join(path, clientdir))

            if not ipath or not os.path.exists(ipath):
                continue

            # get the service name from the ipath/install.conf file
            servicename = get_service_name(ipath)

            # Store the client and image path in the dictionary under the
            # service name.  First, check to see if the service name key
            # already exists.  If the service name key does not already exist
            # then add it to the dictionary.  If the service name key does
            # exist then extend the list and update the dictionary.
            if servicename in lservices and \
              (not sname or servicename == sname):
                tdict = {'client': client, 'ipath': [ipath], 'arch': 'sparc'}
                if servicename in sdict:  # existing service name key
                    slist = sdict[servicename]
                    slist.extend([tdict])
                    sdict[servicename] = slist
                else:  # new service name key
                    sdict[servicename] = [tdict]

    return sdict


def find_x86_clients(lservices, sname=None):
    """
    find_x86_clients() searches TFTPDir for all clients and
    returns a dictionary that contains a list of dictionaries.

    The service name is the key for the main dictionary and the
    client and image path are members of the subdictionary.  The
    dictionary will look something like:

        {
            'service1': [
                        { 'ipath':<path1>, 'client':<client1> },
                        ....
                        ],
            ....
        }

    The information is contained within the menu.lst.01<client>
    file.  Though not the best approach architecturally it is
    the only method currently available.

    We first get the TFTProot directory.  Then iterate over the
    files within the TFTProot directory to get the client menu
    which contains the Image Path and Service Name.  The client
    and image path are then added to the named service dictionary
    list.
    """
    def get_menu_info(path):
        """
        Reads TFTPboot/menu.list file pointed to by 'path' via
        GrubMenu class in installadm_common.py.  Getting the
        install path from the install_media field, service name
        from install_service

        Args
            path = path for the menu.list.01<client> file.

        Returns
            a dictionary of services made up of a list of tuples of
            port, install path

        Raises
            None
        """
        iaddr = 'install_svc_address='
        iserv = 'install_service='
        imedia = 'install_media=http://'

        rdict = dict()
        menu = GrubMenu(file_name=path)
        try:
            entries = menu.entries[0]
        except IndexError:
            sys.stderr.write(_("Error: No entries found in %s\n") % path)
            return ''
        if entries:
            if 'kernel$' in menu[entries]:
                mdict = menu[entries]['kernel$']
                start = mdict.find(iserv) + len(iserv)
                service = mdict[start:].split(',')[0]
                start = mdict.find(iaddr) + len(iaddr)
                port = mdict[start:].split(',')[0].split(':')[-1]
                start = mdict.find(imedia) + len(imedia)
                pstart = mdict[start:].split(',')[0].find('/')
                path = mdict[start:].split(',')[0][pstart:]
                if service in rdict:
                    tlist = rdict[service]
                    tlist.extend([(port, path)])
                    rdict[service] = tlist
                else:
                    rdict[service] = [(port, path)]

        return rdict

    # start of find_x86_clients
    sdict = dict()
    tftp_dir = find_tftp_root()
    if tftp_dir and os.path.exists(tftp_dir):
        for filenames in os.listdir(tftp_dir):
            if filenames.find("menu.lst.01") >= 0:
                path = os.path.join(tftp_dir, filenames)
                pservices = get_menu_info(path)
                tdict = {'arch': 'i386'}
                for servicename in pservices:
                    if servicename in lservices and \
                      (not sname or servicename == sname):
                        client = AIdb.formatValue('mac', filenames[11:])
                        tdict['client'] = client
                        # create a list of image_paths for the client
                        ipath = list()
                        for tup in pservices[servicename]:
                            ipath.insert(0, tup[1])
                        tdict['ipath'] = ipath
                        if servicename in sdict:  # existing service name
                            slist = sdict[servicename]
                            slist.extend([tdict])
                            sdict[servicename] = slist
                        else:  # new service name key
                            sdict[servicename] = [tdict]
    return sdict


def get_local_services(linst, sname=None):
    """
    Iterates over the local services on a host creating a dictionary
    with the service name as the key and status, path, architecture
    and port as the value.  If name is not None then it ensures that
    only the named services is retrieved.

    Args
        linst = smf.AISCF()
        name = service name

    Returns
        a service dictionary made up of a list of dictionary of services.

        {
            service1:
              [
                { 'status':on1, 'path':path1, 'arch':arch1, 'port':port1 },
                ...
              ],
            ...
        }

    Raises
        None
    """
    sdict = dict()
    for akey in linst.services:
        serv = smf.AIservice(linst, akey)
        # Grab the keys since serv is not a dictionary
        service_keys = serv.keys()
        # ensure that the current service has the keys we need.
        # if not then report the error and exit.
        if not (PROP_SERVICE_NAME in service_keys and
                PROP_STATUS in service_keys and
                PROP_IMAGE_PATH in service_keys and
                PROP_TXT_RECORD in service_keys):
            sys.stderr.write(_('Error: SMF service: %s key '
                               'property does not exist\n') % linst)
            sys.exit(1)

        servicename = serv[PROP_SERVICE_NAME]
        info = dict()
        # if a service name is passed in then
        # ensure it matches the current name
        if not sname or sname == servicename:
            info['status'] = serv[PROP_STATUS]
            info['path'] = serv[PROP_IMAGE_PATH]
            info['txt'] = serv[PROP_TXT_RECORD]
            info['port'] = serv[PROP_TXT_RECORD].split(':')[-1]
            info['arch'] = which_arch(info['path'])

            # try to add the optional elements
            if PROP_BOOT_FILE in service_keys:
                info['boot_file'] = serv[PROP_BOOT_FILE]

            if PROP_DEF_MANIFEST in service_keys:
                info['default-manifest'] = serv[PROP_DEF_MANIFEST]

            if PROP_VERSION in service_keys:
                info['version'] = serv[PROP_VERSION]

            if servicename in sdict:
                slist = sdict[servicename]
                slist.extend([info])
                sdict[servicename] = slist
            else:
                sdict[servicename] = [info]

    return sdict


def get_clients(lservices, sname=None):
    """
    Gets the clients (x86 and sparc) for the services of a local host.
    If a service name is passed in the only get the clients for the
    named service on the local host.

    Args
        lservices = services on a host
        sname = a named service

    Returns
        a service dictionary of both x86 and sparc clients

            {
                'service1': [
                              {
                                'ipath':[path1, path2],
                                'client':client1,
                                'arch':arch1
                              },
                            ....
                            ],
                ....
            }

    Raises
        None
    """
    def merge_dictionaries(first, second):
        """
        Merges two similar dictionaries and returns the resulting
        dictionary.  The dictionaries are the same as in get_clients()
        description.
        """
        rdict = dict()
        rdict.update(first)
        rdict.update(second)
        for key in set(first.keys()) & set(second.keys()):
            rdict[key] = first[key] + second[key]

        return rdict

    sdict = find_sparc_clients(lservices, sname=sname)
    xdict = find_x86_clients(lservices, sname=sname)
    botharchs = dict()
    if sdict and xdict:
        botharchs = merge_dictionaries(sdict, xdict)
    elif sdict:
        botharchs = sdict
    elif xdict:
        botharchs = xdict

    return botharchs


def build_option_list():
    """
    Parse command line arguments to ISIM conversion
    """
    desc = _("Utility for converting Solaris 11 Express services and clients "
             "to Solaris 11 FCS format")
    usage = _("usage: %prog [-h][--version]\n"
              "       %prog [-n][--dryrun] [-d][--debug] [-p][--dhcp]\n")

    parser = optparse.OptionParser(version=VERSION, description=desc,
        usage=usage)

    parser.add_option("-n", "--dryrun", dest="dryrun", default=False,
                      action="store_true", help=_(
                      "dry run mode. No changes made to AI configuration"))

    parser.add_option("-d", "--debug", dest="debug", default=0,
                      action="store_true", help=optparse.SUPPRESS_HELP)

    parser.add_option("-p", "--dhcp", dest="dhcp", default=False,
                      action="store_true",
                      help=_("DHCP mode.  Create an ISC DHCP configuration "
                             "from the current Solaris DHCP configuration"))

    return parser


def create_config(services, dryrun, ai_service):
    """
    For the specified service create the .config file in
    /var/ai/service/<service name> with service_name, txt_record, and
    image_path from the SMF properties
    """

    logging.debug("create_config\n")

    config_path = os.path.join(SERVICE_DIR, ai_service, '.config')

    # Create .config file in the service directory
    config_list = list()
    config_list.append("[service]")
    for service in services[ai_service]:
        config_list.append("status = %s" % service['status'])
        config_list.append("service_name = %s" % ai_service)
        config_list.append("version = 2")
        config_list.append("txt_record = %s" % service['txt'])
        config_list.append("image_path = %s" % service['path'])
        if service['arch'] == 'i386':
            config_list.append("global_menu = True")
        else:
            config_list.append("global_menu = False")

    # Write the .config file output to the log
    print _("Create configuration file for service: %s") % ai_service
    for item in config_list:
        print "    ", item

    if not dryrun:
        config_file = open(config_path, "w")
        for item in config_list:
            config_file.write(item + "\n")
        config_file.close()

    # If install.conf exists in the image directory then move it to
    # the service directory, rename it system.conf, and then create
    # a symlink back to install.conf
    install_conf = os.path.join(service['path'], 'install.conf')
    system_conf = os.path.join(SERVICE_DIR, ai_service, 'system.conf')
    print _("Move %s to %s") % (install_conf, system_conf)
    if not dryrun:
        if os.path.exists(install_conf):
            shutil.move(install_conf, system_conf)
            os.symlink(system_conf, install_conf)


def move_service_directory(services, dryrun, ai_service):
    """
    Move the directory associated with the service from
    /var/ai/<service name> to /var/ai/service/<service name>.
    If /var/ai/<service name> does not exist then check for
    /var/ai/46xxx where 46xxx is the value specified in the txt_record

    - /var/ai/<service name>
        Move the directory
    - /var/ai/46xxx
        Move the directory to /var/ai/service/<service name>
        Create a relative sym link from dir to /var/ai/service/46xxx
    Move the netboot files to the service directory
    - sparc
        move the wanboot.conf file from /etc/netboot/<service name> to
        /var/ai/service/<service name> and remove the symbolic link to
        /etc/netboot/wanboot.conf if it exists.
    - x86
        move menu.lst file from /tftpboot/menu.lst.<service name> to
        /var/ai/service/<service name>/menu.lst
        clean up pxegrub files
    """

    logging.debug("move_service_directory")

    # Ensure that the image path directory exists
    for service in services[ai_service]:
        print _("Convert service: %s") % ai_service
        ipath = service['path']
        if not (os.path.exists(ipath) and os.path.isdir(ipath)):
            raise ServiceConversionError(
                _("Error: Image path directory does not exist: %s" % ipath))
        # Make sure that the image appears valid (has a solaris.zlib file)
        if not os.path.exists(os.path.join(ipath, "solaris.zlib")):
            raise ServiceConversionError(
                _('Error: Image path directory does not'
                  ' contain a valid image: %s' % ipath))

    sdpath = os.path.join('/var/ai', ai_service)
    new_service_path = os.path.join(SERVICE_DIR, ai_service)
    if not dryrun and not os.path.exists(SERVICE_DIR):
        os.mkdir(SERVICE_DIR)
    elif not os.path.isdir(SERVICE_DIR):
        raise ServiceConversionError(
            _("Error: %s exists and is not a directory" % SERVICE_DIR))

    if os.path.exists(sdpath) and os.path.isdir(sdpath):
        print _("    Move %s to %s") % (sdpath, new_service_path)
        # Move the service path to the new service location
        if not dryrun:
            try:
                shutil.move(sdpath, new_service_path)
            except OSError as err:
                raise ServiceConversionError(str(err))
    else:
        # grab the port number for the service and see if /var/ai/<port>
        # exists.  If so move it to /var/ai/service/<service name>
        for service in services[ai_service]:

            portpath = os.path.join('/var/ai', service['port'])
            if os.path.exists(portpath) and os.path.isdir(portpath):
                # /var/ai/<port> exists so move it
                print _("    Move %s to %s") % (portpath, new_service_path)
                print _("    Create link from %s to %s") % (new_service_path,
                        os.path.join(SERVICE_DIR, service['port']))
                if not dryrun:
                    try:
                        shutil.move(portpath, new_service_path)
                        # Create a relative symlink from /var/ai/service/
                        # <service name> to /var/ai/service/<port>
                        os.chdir(SERVICE_DIR)
                        os.symlink(os.path.join('./', ai_service),
                                   os.path.join(SERVICE_DIR, service['port']))
                    except OSError as err:
                        raise ServiceConversionError(str(err))

    if service['arch'] == 'i386':
        print _("    Remove vfstab entry for %s if it exists" % ai_service)
        if not dryrun:
            try:
                remove_boot_archive_from_vfstab(ai_service, service)
            except OSError as err:
                raise ServiceConversionError(str(err))

        grub_path = TFTPBOOT + '/menu.lst.' + ai_service
        if os.path.exists(grub_path) and os.path.isfile(grub_path):
            new_grub = os.path.join(new_service_path, 'menu.lst')
            print _("    Move %s to %s") % (grub_path, new_grub)

            if not dryrun:
                try:
                    shutil.move(grub_path, new_grub)
                except OSError as err:
                    raise ServiceConversionError(str(err))
        else:
            raise ServiceConversionError(_("Error: menu.lst for service: %s"
                                         "was not found" % ai_service))

        # if symlink from /tftpboot/<service name> to
        # /tftpboot/PXEGRUB.* exists then delete it
        pxegrub_path = os.path.join(TFTPBOOT, ai_service)
        if os.path.islink(pxegrub_path):
            print _("    Remove link %s") % pxegrub_path
            if not dryrun:
                try:
                    os.remove(pxegrub_path)
                # If error encountered continue with the conversion
                except OSError as err:
                    sys.stderr.write(str(err) + "\n")

    else:
        netboot_path = os.path.join(NETBOOT, ai_service, 'wanboot.conf')
        if os.path.exists(netboot_path) and os.path.isfile(netboot_path):
            new_netboot = os.path.join(new_service_path, 'wanboot.conf')
            print _("    Move %s to %s") % (netboot_path, new_netboot)
            if not dryrun:
                try:
                    shutil.move(netboot_path, new_netboot)
                except OSError as err:
                    raise ServiceConversionError(str(err))

            # if symlink from /etc/netboot/wanboot.conf to
            # /etc/netboot/<service>/wanboot.conf then delete it
            netboot_lnk = os.path.join(NETBOOT, 'wanboot.conf')
            if os.path.islink(netboot_lnk):
                print _("    Remove link %s") % netboot_lnk
                if not dryrun:
                    try:
                        os.remove(netboot_lnk)
                    # If error encountered continue with the conversion
                    except OSError as err:
                        sys.stderr.write(str(err) + "\n")
        else:
            raise ServiceConversionError(_("Warning: wanboot.conf file for "
                                         "service: %s was not found" %
                                         ai_service))


def get_bootargs(menupath):
    """
    Get the bootargs from the menu.lst that were specified by the user with
    the '-b' option to installadm create-client
    """
    generated_bootargs = ['install', 'install_media', 'install_service',
                          'install_svc_address']
    bootargs = ''
    for line in fileinput.input(menupath):
        parts = line.partition(' -B')
        if parts[1]:
            ending = parts[2]
            # Parse out the bootargs that are generated by installadm
            for keyval in ending.split(','):
                boot_pair = keyval.split('=')
                if boot_pair[0].strip() in generated_bootargs:
                    continue
                bootargs += keyval.strip() + ','

    return bootargs.rstrip(',')


def convert_client(clients, dry_run, ai_service):
    """
    Remove the clients from the specified server and then recreate them.
    x86 - save the bootargs from menu.lst
        Remove /tftpboot/<clientid> and /tfpboot/menu.lst.<clientid>
    sparc - remove the /etc/netboot/<clientid> directory

    Recreate each client using 'installadm create-client'
    """
    logging.debug("convert_client")
    print _("Client conversion:")

    for service in clients[ai_service]:
        # Strip : from client
        print _("    client: %s") % service['client']
        clientid = '01' + service['client'].replace(':', '')
        if service['arch'] == 'i386':
            client_menu_lst = os.path.join(TFTPBOOT, 'menu.lst.' + clientid)
            boot_args = get_bootargs(client_menu_lst)

            # remove the client specific entries in tftpboot
            print _("    Remove %s") % client_menu_lst
            print _("    Remove %s/%s") % (TFTPBOOT, clientid)
            if not dry_run:
                try:
                    # /tftpboot/<clientid> is a symlink - remove it
                    os.remove(os.path.join(TFTPBOOT, clientid))
                    os.remove(client_menu_lst)
                # If error encountered continue with the conversion
                except OSError as err:
                    sys.stderr.write(str(err) + "\n")

        else:
            boot_args = None
            # remove the /etc/netboot client directory
            netboot_dir = os.path.join(NETBOOT, clientid)
            print _("    Remove %s") % netboot_dir
            if not dry_run:
                try:
                    shutil.rmtree(netboot_dir)
                # If error encountered continue with the conversion
                except OSError as err:
                    sys.stderr.write(str(err) + "\n")

        print _("    Recreate client with ")
        print _("        arch: %s") % service['arch']
        print _("        service: %s") % ai_service
        print _("        client: %s") % service['client']
        if service['arch'] == 'i386':
            print _("        boot_args: %s") % boot_args
        if not dry_run:
            # recreate the client
            create_client.create_new_client(service['arch'],
                AIService(ai_service),
                service['client'].replace(':', ''), boot_args)


def copy_netboot_files(dry_run):
    """
    Move all of the non-AI files from /tftpboot to /etc/netboot
    Make /tftpboot a symlink to /etc/netboot
    Convert inetd_start/exec property of tftp/udp6 to /etc/netboot
    """
    logging.debug("copy_netboot_files")
    copy_error = False
    print _("Clean up pxegrub files from /tftpboot")
    if not dry_run:
        try:
            for rm_file in glob.glob(os.path.join(TFTPBOOT, "rm.*")):
                os.remove(rm_file)
            for pxegrub_file in glob.glob(os.path.join(TFTPBOOT, "pxegrub.*")):
                os.remove(pxegrub_file)
            for i86pc_dir in glob.glob(os.path.join(TFTPBOOT,
                                                    "I86PC.Solaris-*")):
                shutil.rmtree(i86pc_dir, True)
        except OSError as err:
            sys.stderr.write(str(err) + "\n")
            copy_error = True

    print _("Copy non-AI files from /tftpboot to /etc/netboot")
    print _("Change inetconv/source_line property in "
            "service tftp/udp6 to /etc/netboot")
    if not dry_run:
        for netfile in os.listdir(TFTPBOOT):
            print _("  Move %s from /tftpboot to /etc/netboot" % netfile)
            try:
                shutil.move(os.path.join(TFTPBOOT, netfile),
                    os.path.join(NETBOOT, netfile))
            except OSError as err:
                sys.stderr.write(str(err) + "\n")
                copy_error = True

        # Remove /tftpboot and recreate it as a link to /etc/netboot
        if not copy_error:
            try:
                os.rmdir(TFTPBOOT)
                os.symlink(NETBOOT, TFTPBOOT)
            except OSError as err:
                sys.stderr.write(str(err) + "\n")
                copy_error = True

        if copy_error:
            sys.stderr.write(NETBOOT_ERR)

        inet_exec = get_exec_prop()
        if inet_exec != '':
            set_exec_prop(inet_exec.replace(TFTPBOOT, NETBOOT))


def upgrade_svc_vers_0_1(services, dry_run, ai_service):
    """
    Re-register the default manifest for the input service managed in
    pre Derived Manifest services to be compatible with Derived Manifest
    services
    """
    logging.debug("upgrade_svc_vers_0_1")

    # if running in dry run mode then the service hasn't been moved to
    # /var/ai/service.  Look for the manifest in /var/ai instead.
    if dry_run:
        sdpath = os.path.join('/var/ai', ai_service)
    else:
        sdpath = os.path.join('/var/ai/service', ai_service)

    print _("Upgrade existing default manifests for %s to version 1") % \
            ai_service

    if os.path.exists(sdpath) and os.path.isdir(sdpath):
        manifest_dir = sdpath
    else:
        # grab the port number for the service and see if /var/ai/<port>
        # exists.  If so use it as the manifest directory
        for service in services[ai_service]:

            # if running in dry run mode then the service hasn't been moved to
            # /var/ai/service/<port>.  Look for the manifest in
            # /var/ai/<port> instead.
            if dry_run:
                portpath = os.path.join('/var/ai', service['port'])
            else:
                portpath = os.path.join('/var/ai/service', service['port'])
            if os.path.exists(portpath) and os.path.isdir(portpath):
                # The port path exists so use it as the manifest directory
                manifest_dir = portpath
                break
            else:
                raise ServiceConversionError(_('Unable to find the service'
                                            ' directory for %s' % ai_service))

    default_file = os.path.join(manifest_dir, 'AI_data', 'default.xml')
    print _("Search for default manifest %s") % default_file
    if os.path.isfile(default_file):
        # Upgrade the service
        print _("Default manifest found - upgrade service")
        if not dry_run:
            # Create a temp file and move the manifest into it
            temp_fd, temp_nm = tempfile.mkstemp()
            shutil.move(default_file, temp_nm)
            # call add-manifest with the default
            cmd = ['/usr/sbin/installadm', 'add-manifest', '-n',
                ai_service, '-d', '-f', temp_nm]

            try:
                Popen.check_call(cmd, stdout=Popen.STORE,
                                 stderr=Popen.STORE, logger='',
                                 stderr_loglevel=logging.DEBUG)
            except CalledProcessError:
                # Move the default manifest back into place
                shutil.move(temp_nm, default_file)
                sys.stderr.write(_('Warning: Unable to add the '
                                   'default manifest: %s for service: %s\n' %
                                   (default_file, ai_service)))
                return

            # delete the temporary file 
            try:
                os.remove(temp_nm)
            except OSError:
                pass
    else:
        print ' No default manifest found for service %s' % ai_service


def upgrade_svc_vers_1_2(services, dry_run, ai_service):
    """
    Make the changes to the AI service necessary for ISIM
    """

    # Remove all of the AI property groups
    del_prop_group(ai_service, dry_run)

    move_service_directory(services, dry_run, ai_service)
    create_config(services, dry_run, ai_service)


def copy_image_path(service_name, service_info, dry_run):
    """
    Copy specified image to a unique location
    """

    new_image_path = service_info['path']
    iter = 1
    while True:
        new_image_path = service_info['path'] + '_%s' % iter
        if not os.path.exists(new_image_path):
            break
        iter += 1

    print _("Create a unique instance of image path for %s at %s") % \
        (service_name, new_image_path)
    if not dry_run:
        # copy the image directory
        shutil.copytree(service_info['path'], new_image_path, symlinks=True)
        # update the service information to reflect the new image location
        service_info['path'] = new_image_path


def convert_image_paths(services, dry_run):
    """
    If multiple services use the same image path make copies for each
    """

    print 'Ensure that all image paths are unique'
    image = dict()
    for service_name in services:
        for service in services[service_name]:
            # services cannot share images
            ipath = service['path']
            if ipath in image:
                # only copy if the image path exists
                # don't throw an exception - this will get caught later
                if not (os.path.exists(ipath) and os.path.isdir(ipath)):
                    continue
                copy_image_path(service_name, service, dry_run)

            image[service['path']] = service_name


def is_sun_dhcp_host():
    """
    Is Solaris DHCP configured and enabled on this system
    """

    cmd = ['/usr/sbin/dhtadm', '-P']
    try:
        Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL)
    except CalledProcessError:
        return False

    return True


def create_isc_dhcp_configuration(dhcp_config):
    """
    Create the configuration file that would convert the existing SUN
    DHCP configuration to the equivalent ISC DHCP configuration
    """
    try:
        subnets = SUNDHCPData.subnets()
        macros = SUNDHCPData.macros()
    except SUNDHCPData.DHCPError as err:
        sys.stderr.write(str(err) + "\n")
        return

    # add the subnet ranges and the DHCP server IP to each of the subnet
    # macros so that all of the necessary to create the subnet stanza
    # will be available/
    for subnet in subnets:
        if subnet in macros:
            macros[subnet].update({'ip_ranges': subnets[subnet]})
            macros[subnet].update({'nextserver':
                                   subnets[subnet][0]['nextserver']})

    # Attempt to open the dhcp configuration file.  If unsuccessful then
    # flag an error and return
    try:
        config_file = open(dhcp_config, "w")
    except IOError as err:
        sys.stderr.write(str(err) + "\n")
        return

    # Build each of the ISC DHCP stanzas
    print _("Build ISC DHCP Configuration File: %s\n" % dhcp_config)

    cfgfile_base_printed = False
    for mname in macros:
        if 'broadcast' in macros[mname]:
            # Build the Configuration file base
            # Grab one of the macros and use the domain name and name servers
            # to populate the global definitions
            if not cfgfile_base_printed:
                config_file.write(dhcp.CFGFILE_BASE % macros[mname])
                cfgfile_base_printed = True

            # Build the subnet stanza
            config_file.write(dhcp.CFGFILE_SUBNET_HEADER_STRING %
                              macros[mname] % "\n")
            # build a range string for each subnet range found
            for subnet_range in macros[mname]['ip_ranges']:
                config_file.write(dhcp.CFGFILE_SUBNET_RANGE_STRING %
                                  subnet_range + "\n") 

            config_file.write(dhcp.CFGFILE_SUBNET_FOOTER_STRING %
                              macros[mname] + "\n")
            # Save off the server IP value for use in the Sparc class stanza
            server_ip = macros[mname]['nextserver']
            
    # Build the architecture class stanzas
    config_file.write(dhcp.CFGFILE_PXE_CLASS_STANZA % {'bootfile':
                      '<x86 service name>/boot/grub/pxegrub'} + "\n")
    config_file.write(_("NOTE: Specify the desired x86 AI service name "
                      "that will be used as the default boot service" + "\n"))
    sparc_server_string = 'http://%s:5555/cgi-bin/wanboot-cgi' % server_ip
    config_file.write(dhcp.CFGFILE_SPARC_CLASS_STANZA % {'bootfile':
                      sparc_server_string} + "\n")

    # Build each of the host stanzas
    for  mname in macros:
        if macro.startswith('01') and 'bootfile' in macros[mname]:
            # Generate the string equivalent of the IP address from
            # the macro name
            raw_mac = mname[2:]
            macros[mname].update({'macaddr': ':'.join(a + b for a, b in
                                  zip(raw_mac[::2], raw_mac[1::2])),
                                  'hostname': raw_mac}) 
            config_file.write(dhcp.CFGFILE_HOST_STANZA % macros[mname] + "\n")

    config_file.close()

        
def main():
    """
    Server Image Management Conversion
    Exit Codes:
        0 - Success
        1 - Failure

    Options:
        -n, --dryrun - List but do not apply changes
        -p, --dhcp - Only generate the ISC configuration file
                     for this AI server

    """

    parser = build_option_list()

    (options, args) = parser.parse_args()

    # check for root
    if os.geteuid() != 0:
        raise SystemExit(_("Error: Root privileges are required for "
                           "this command."))

    try:
        inst = smf.AISCF(FMRI="system/install/server")
    except KeyError:
        raise SystemExit(_("Error: The system does not have the "
                           "system/install/server SMF service"))

    # Set up logging to the specified level of detail
    if options.debug == 0:
        options.log_level = DEFAULT_LOG_LEVEL
    elif options.debug == 1:
        options.log_level = DEBUG_LOG_LEVEL
    elif options.debug >= 2:
        options.log_level = com.XDEBUG

    try:
        com.setup_logging(options.log_level)
    except IOError as err:
        parser.error("%s '%s'" % (err.strerror, err.filename))

    logging.debug("installadm conversion options: verbosity = %s",
                  options.log_level)

    # Create an ISC DHCP configuration from the existing Solaris DHCP if
    # the AI server has been setup as the DHCP server
    # If the --dhcp option was specified then exit after creating the config
    if is_sun_dhcp_host():
        create_isc_dhcp_configuration(ISC_DHCP_CONFIG)
    else:
        print _("There is no DHCP configuration to convert on the AI server")

    if options.dhcp:
        sys.exit(EXIT_SUCCESS)

    service_names = inst.services.keys()
    services = get_local_services(inst)

    if not services:
        output =  \
            _('There are no upgradeable services configured on this server.\n')
        sys.stdout.write(output)
        sys.exit(EXIT_SUCCESS)

    if options.dryrun:
        print _("Dry run mode - no changes will be made to the system")
    else:
        prompt = \
            (_('\nWARNING: The conversion process will make changes to '
               'the file system.\nIt is advisable to make a copy of the '
               'boot environment\nusing beadm(1M) before proceeding.\n'
               '\nAre you sure you want to proceed [y/N]: '))
        if not com.ask_yes_or_no(prompt):
            raise SystemExit(1)

    print _("Disable the AI SMF service")
    # Disable the AI service
    if not options.dryrun:
        aismf.disable_instance()

    # If multiple services use the same image path then convert them so that
    # they each have their own copy
    convert_image_paths(services, options.dryrun)

    # Make all of the AI service conversions
    unconverted_services = dict()
    for service_name in services:
        try:
            # Upgrade the service from 1 to 2 (ISIM)
            upgrade_svc_vers_1_2(services, options.dryrun, service_name)

            # Grab the attributes for the specified service. There
            # is only one set of attributes associated so grab the first
            # entry in the list.
            service_attributes = services[service_name][0]

            # if is only necessary to upgrade when the default-manifest
            # property isn't defined for the service and the service version
            # is not 1 or greater
            service_version = int(service_attributes.get('version', 0))
            if service_version >= 1:
                continue

            if not 'default-manifest' in service_attributes:
                # Upgrade the service version from 0 to 1
                # It is necessary to call upgrade_svc_vers_0_1 after 
                # upgrade_svc_vers_1_2 because it is necessary to upgrade the
                # service to ISIM before calling installadm to upgrade
                # the manifests
                upgrade_svc_vers_0_1(services, options.dryrun, service_name)

        except ServiceConversionError as err:
            print str(err)
            # Add the service to the list of services that were not converted
            # and keep the reason so that this list can be presented to the
            # user at the end of the conversion
            unconverted_services[service_name] = err

    # Make all of the client conversions
    clients = get_clients(service_names)
    if not clients:
        output = _('There are no clients configured on this server.\n')
        sys.stdout.write(output)
    else:
        for service_name in clients:
            # Only convert the client if the service was converted successfully
            if not service_name in unconverted_services:
                convert_client(clients, options.dryrun, service_name)

    copy_netboot_files(options.dryrun)

    # If there are existing default-i386 or default-sparc services
    # rename them to default-<arch>_1 (or the first unused number)
    for service_name in services:
        if not service_name in unconverted_services:
            if service_name == 'default-i386' or \
                service_name == 'default-sparc':
                new_service_name = generate_new_service_name(services,
                                                         service_name)
                print _("Change service name %s to %s") % (service_name,
                        new_service_name)

                # Create a new service entry in the service dictionary
                # and delete the old entry
                services[new_service_name] = services[service_name]
                del services[service_name]        

                if not options.dryrun:
                    svc = AIService(service_name)
                    svc.rename(new_service_name)

    if len(unconverted_services) > 0:
        print "\nThe following services were not converted:"
        for errored_service in unconverted_services:
            # Print out the service and the reason that it wasn't converted
            print _("  %s: %s" % (errored_service,
                str(unconverted_services[errored_service]).lstrip("Error: "))) 

    # Enable the AI service
    print _("Enable the AI SMF service")
    if not options.dryrun:
        try:
            aismf.service_enable_attempt()
        except aismf.ServicesError as err: 
            raise SystemExit(err)

    sys.exit(EXIT_SUCCESS)

if __name__ == "__main__":
    main()
