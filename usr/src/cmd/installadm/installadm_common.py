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
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
'''
Common Python Objects for Installadm Commands
'''

import re
import subprocess
import os
import stat
import sys
import gettext

#
# General classes below
#

class File_(file):
    '''
    A general class to open a file and clean it up upon deallocation. Also
    provides a read_all() and write_all() function to read in the entire file
    and write out the entire file, both as a single string
    '''
    def __init__(self, file_name, mode="r"):
        '''
        Open file with mode requested. Will throw exceptions such as IOErrors
        for permission or file not found errors as passed from file()
        '''
        # call file(file_name, mode)
        super(File_, self).__init__(file_name, mode)

        # store file name for later access
        self.file_name = file_name

    def readlines(self, skip_comments=True, remove_newlines=True,
                  skip_blanklines=True):
        '''
        Enhanced readlines to use enhanced readline -- note size is not
        accepted like with file.readlines()
        '''
        # ensure we got a bool for remove_newlines
        # (everything else is passed to readline)
        if not isinstance(remove_newlines, bool):
            raise TypeError("readlines() got an unexpected value, only " +
                            "booleans accepted.")

        # store lines in a list
        lines = []

        # build a function for removing newlines or not
        if remove_newlines is True:
            # return line after split (newlines removed)
            newlineFn = lambda(a): a.rstrip('\n')
        else:
            # return line with a newline added back on
            newlineFn = lambda(a): a

        # do not strip newlines or else we will not know if we get a blank line
        # or are out of lines
        line = self.readline(skip_comments=skip_comments,
                             remove_newlines=False,
                             skip_blanklines=skip_blanklines)
        while line:
            # apply newlineFn if we are removing "\n" or not
            lines.append(newlineFn(line))
            # read next line in (with same caveats as above about newlines and
            # blanklines
            line = self.readline(skip_comments=skip_comments,
                                 remove_newlines=False,
                                 skip_blanklines=skip_blanklines)
        return lines

    def readline(self, skip_comments=True, remove_newlines=True,
                 skip_blanklines=True):
        '''
        Add options to readline to remove trailing newline, to skip comment lines and
        to skip blank lines (any line with only whitespace) -- note size is not
        accepted like with file.readline()
        '''

        # ensure we got bools for all arguments
        if not isinstance(skip_comments, bool) or \
            not isinstance(remove_newlines, bool) or \
            not isinstance(skip_blanklines, bool):
            raise TypeError("readline() got an unexpected keyword value, " +
                            "only booleans accepted.")

        # to implement a formulaic approach to dropping newlines and comments
        # build a function for removing newlines or not
        if remove_newlines is True:
            # return line after split (newlines removed)
            newlineFn = lambda(a): a.rstrip('\n')
        else:
            # return line with a newline added back on
            newlineFn = lambda(a): a

        # similarly, for dropping comments
        if skip_comments is True:
            # only return lines which do not start with # (i.e. no comments)
            commentFn = lambda(a): a.lstrip().startswith('#')
        else:
            # simply pass through passing comments
            commentFn = lambda(a): False

        # lastly for blanklines
        if skip_blanklines is True:
            # if we do not return blank lines, test for them
            blanklineFn = lambda(a): len(a.strip()) == 0
        else:
            # if we do return blank lines pass through
            blanklineFn = lambda(a): False

        # split the file into a list of lines (w/ or w/o newlines)
        line = super(File_, self).readline()
        while line:
            # apply newline function (either strip "\n" or leave as is)
            line = newlineFn(line)
            # loop to the next line if we have a comment or blank line and are
            # not returning such lines
            if commentFn(line) or blanklineFn(line):
                line = super(File_, self).readline()
                continue
            return line
        # if we are out of lines return an empty string
        return ''

    def readlines_all(self, skip_comments=True, remove_newlines=True,
                      skip_blanklines=True):
        '''
        Read the entire file in and return the split lines back
        '''
        self.seek(0)
        return self.readlines(skip_comments=skip_comments,
                              remove_newlines=remove_newlines,
                              skip_blanklines=skip_blanklines)

    def read_all(self):
        '''
        Read the entire file in and return the string representation
        Will throw exceptions when errors are encountered.
        '''
        self.seek(0)
        return self.read()

    def write_all(self, data):
        '''
        Write out data to the file and truncate to the correct length
        Argument is the data to write out.
        Will throw exceptions when errors are encountered.
        '''
        # write the file out
        self.seek(0)
        self.write(data)
        self.truncate()
        self.flush()


class DBFile(dict):
    '''
    Implements object oriented access to a "database" file -- any file with a
    delimited column/table format. One can query fields through dictionary
    style key look-ups (i.e. dbfile_obj['FIELD']) or attribute access such as
    dbfile_obj.fields.FIELD, both return lists which are indexed so that a
    line from the file can be reconstructed as:
    dbfile_obj.field.DEVICE[idx]\tdbfile_obj.field.FSCK_DEVICE...
    Otherwise, one can read the entire file via dbfile_obj.raw or overwrite the
    entire file by assigning dbfile_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but object.fields.FIELD2,
    object.fields.FIELD1, etc. A list of fields is available through
    object.fields(). This allows the implementation to evolve, if necessary.
    '''

    # field variables (modify this in child classes)
    #_FIELD = "field"

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys() if
        obj.isupper() and obj.startswith("_") and (locals()[obj] is not None)]
    # the order of headers from the file needs to be recorded (should be a list
    # of _FIELD1, _FIELD2, ...
    _headers = []

    def __init__(self, file_name=None, mode="r"):
        '''
        Open file and read it in. Will throw exceptions when errors are
        encountered
        '''
        # run the generic dict() init first
        super(DBFile, self).__init__()

        # create a File_ to work from
        self.file_obj = File_(file_name, mode)
        # mtime holds the file_obj's last read mtime
        self.mtime = None

        # build a dictionary for the full text headers and the objects
        # representing them (e.g. headers = \
        # {"MOUNT_POINT": MOUNT_POINT} == {"MOUNT_POINT": "mount_point"})
        self.headers = dict(
                            zip(self._fields,
                                [eval("self._" + obj) for obj in self._fields]))

        # read data in and throw any errors during init if reading the file is,
        # already broken and going to cause problems (will not prevent future
        # errors if file otherwise breaks)
        self._load_data()

    def _load_data(self):
        '''
        Read file from beginning and load data into fields, one record per row
        '''
        # see if the file has updated since last read (attempt at caching)
        if (self.mtime == os.stat(self.file_obj.file_name)[stat.ST_MTIME]):
            return

        # clear all keys as we'll be repopulating (if we have populated before)
        super(DBFile, self).clear()

        # update the file mtime to keep track (NOTE: there is a potential change
        # between when we store this mtime and do the readline_all() below)
        self.mtime = os.stat(self.file_obj.file_name)[stat.ST_MTIME]

        # store the intermediate split fields
        fields = []

        # now produce a list of lists for each field:
        # [[field1] [field2] [field3]]

        # split the file into a list of lists of fields
        # (ensure we don't split on white space on trailing field so limit the
        # number of splits to the number of headers (well, headers minus one,
        # since 2 fields eq. 1 split))
        fields = [line.split(None, len(self.headers)-1) for line in
            self.file_obj.readlines_all(  skip_comments=True,
                                        remove_newlines=True,
                                        skip_blanklines=True)
            if len(line.split(None, len(self.headers)-1)) == len(self.headers)]

        # build a dict with each header a key to a list
        # built of each row from the file
        super(DBFile, self).update(
                                   dict(
                                   # use _headers which is a list with the correct order
                                   zip(self._headers, [[row[i] for row in fields] for i in
                                   range(0, len(self._headers))])
                                   )
                                   )

    def _attrproperty(wrapped_function):
        '''
        Function to provide attribute look-up on a function as a property
        (obj is the self passed into the function which is wrapped)
        '''
        class _Object(list):
            '''
            An object to return for attribute access
            '''
            def __init__(self, obj):
                # run the generic list() init first
                super(_Object, self).__init__()

                self.obj = obj
                # represent the fields available if wrapped_function is just
                # returning this function
                self = obj.headers
            def __getattr__(self, key):
                '''
                Provide an interface so one can run:
                _object_instance.ATTRIBUTE:
                '''
                return wrapped_function(self.obj, key)
            def __call__(self):
                '''
                Return valid keys if the class is simply called to avoid
                exposing this class
                '''
                return wrapped_function(self.obj)

        # return a property which returns the _Object class
        return property(_Object)

    @_attrproperty
    def fields(self, attr=None):
        '''
        Return a list of fields (with descriptions) if called (i.e.
        self.fields()a
        Otherwise, return a field if called as an attribute accessor (i.e.
        self.fields.DEVICE would return the DEVICE field)
        '''
        # ensure we're getting accurate data
        self._load_data()
        # if we did not get an attribute return the dictionary of fields and
        # descriptions
        if attr is None:
            return self.headers
        # else, we got an attribute
        else:
            # look up the dictionary key associated with key (i.e. MOUNT_POINT
            # will translate to the dictionary key "mount point"
            return self.get(self.headers[attr])

    def __getitem__(self, key):
        '''
        Provide a wrapped interface so one can run
        if "/dev/dsk/c0t0d0s0" in dbfile_obj['DEVICE'] and get the most up to
        date data for the file:
        '''
        # ensure we're getting accurate data
        self._load_data()
        # ensure key is valid
        if not self.has_key(key):
            raise KeyError(key)
        # return a field object, populated from the dictionary
        return self._Result(self, key)

    def get(self, key, default=None):
        '''
        Provide a wrapped interface so one can run
        if "/dev/dsk/c0t0d0s0" in dbfile_obj.get('DEVICE') and get the most up to
        date data for the file:
        '''
        # ensure we're getting accurate data
        self._load_data()
        # ensure key is valid
        if self.has_key(key):
            # return a field object, populated from the dictionary
            return self._Result(self, key)
        # else return default
        return default

    def keys(self):
        '''
        Provide all field titles stored as dictionary keys
        '''
        self._load_data()
        return super(DBFile, self).keys()

    def _read_all(self):
        '''
        Provide the entire file as a single string (with \n's and \t's and
        comments)
        '''
        return self.file_obj.read_all()

    def _write_all(self, data):
        '''
        Replace the contents of file and truncate to the correct length
        Argument is the data to write out.
        Will throw exceptions when errors are encountered.
        '''
        # write the file out
        self.file_obj.write_all(data)

    # provide the raw text of file as a property
    raw = property(_read_all, _write_all,
                   doc="Get or write the entirety of file")

    # we do not want to deal with rewriting by key
    __setitem__ = None

    class _Result(list):
        '''
        Class to represent field data as produced by _load_data used for
        updating and removing entries in the backing file
        '''
        def __init__(self, parent, key):
            # store what we are representing
            self.extend(super(DBFile, parent).get(key))
            # store in what field of the parent we can be found
            self.field = key
            # store the parent object
            self.parent = parent

        def __delitem__(self, index):
            '''
            Remove an item(s) from the result list and remove its backing store's
            record(s) for the particular item, returning the number of
            deletions made -- if one record is repeated.
            This is done constructing a regular expression to match the record
            by matching each field which should be removed separated by white
            space for this record.
            '''
            # iterate over every field in the parent for this index building up
            # a list of field entries for this record
            regex = [re.escape(self.parent[field][index]) for field in
                # need the ordered list of headers which is private at this
                # time and a list stored in _headers
                self.parent._headers]

            # now separate each field entry with a key for whitespace
            regex = r"\s".join(regex)

            # end the reg ex. looking for a newline or the end of file (and
            # grabbing any spacing between
            # store what we end with for the ending match so we can put it back
            regex = regex + r"(?P<end>\s|$)"

            # start the reg ex. looking for the beginning of file or a newline
            regex = r"(?:^|\n)" + regex

            # now match, replace the ending match and write the output
            self.parent.raw = re.sub(regex, "\g<end>", self.parent.raw)

        # we do not want to deal with rewriting by key
        __setitem__ = None


class INETd_CONF(DBFile):
    '''
    Allow OO access to the /etc/inet/inetd.conf file. All DBFile methods are
    available.
    '''

    # field variables
    _SERVICE_NAME = "service-name"
    _ENDPOINT_TYPE = "endpoint-type"
    _PROTOCOL = "protocol"
    _WAIT_STATUS = "wait-status"
    _UID = "uid"
    _SERVER_PROGRAM = "server-program"
    _SERVER_ARGUMENTS = "server-arguments"

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys()
        if obj.isupper() and locals()[obj] is not None]

    # the order of headers from the file needs to be recorded
    _headers = [_SERVICE_NAME, _ENDPOINT_TYPE, _PROTOCOL, _WAIT_STATUS, _UID,
        _SERVER_PROGRAM, _SERVER_ARGUMENTS]

    def __init__(self, file_name="/etc/inet/inetd.conf", mode="r"):
        super(INETd_CONF, self).__init__(file_name=file_name, mode=mode)

class MNTTab(DBFile):
    '''
    Implements object oriented access to the /etc/mnttab file. One can query
    fields through dictionary style key look-ups (i.e. mnttab_obj['DEVICE']) or
    attribute access such as mnttab_obj.DEVICE both return lists which are
    indexed so that a line from the file can be reconstructed as
    mnttab_obj[device][idx]\tmnttab_obj[fsckDevice]...
    Otherwise, one can read and write the entire file via mnttab_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but MNTTab.DEVICE, MNTTab.FSCK_DEVICE,
    etc. to allow the implementation to evolve, if necessary.

    One can remove a record in the file by running:
    del(mnttab_obj.fields.FIELD[idx])
    '''

    # field variables
    _DEVICE = "special"
    _MOUNT_POINT = "mount_point"
    _FS_TYPE = "fstype"
    _FS_OPTS = "options"
    _MNT_TIME = "time"

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys()
        if obj.isupper() and locals()[obj] is not None]

    # the order of headers from the file needs to be recorded
    _headers = [_DEVICE, _MOUNT_POINT, _FS_TYPE, _FS_OPTS, _MNT_TIME]

    def __init__(self, file_name="/etc/mnttab", mode="r"):
        super(MNTTab, self).__init__(file_name=file_name, mode=mode)

class VFSTab(DBFile):
    '''
    Implements object oriented access to the /etc/vfstab file. One can query
    fields through dictionary style key look-ups (i.e. vfstab_obj['DEVICE']) or
    attribute access such as vfstab_obj.fields.DEVICE both return lists which
    are indexed so that a line from the file can be reconstructed as
    vfstab_obj[device][idx]\tvfstab_obj[fsckDevice]...
    Otherwise, one can read and write the entire file via vfstab_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but using the attribute,
    etc. to allow the implementation to evolve, if necessary.

    One can remove a record in the file by ruining:
    del(vfstab_obj.fields.FIELD[idx])
    '''
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

class MACAddress(list):
    '''
    Class to store and verify MAC addresses
    '''

    class MACAddressError(Exception):
        '''
        Class to report MAC address mal-formatted problems
        '''
        pass

    def __init__(self, MAC):
        '''
        Initialize a MAC address object. Will verify the address is reasonable.
        Can accept ':' or '-' delimited addresses or hex strings with no
        punctuation (and is case insensitive)
        Raises: MACAddressError if not acceptable.
        '''
        # run the generic list() init first
        super(MACAddress, self).__init__()

        # check if MAC has a delimiter
        if ':' in MAC:
            values = MAC.split(":")
        elif '-' in MAC:
            values = MAC.split("-")

        # MAC doesn't appear to have a delimiter, split it into pairs
        else:
            # ensure we are zero padded and the correct length
            if len(MAC) != 12:
                raise self.MACAddressError, (_("Malformed MAC address"))
            # group into octets (lists of two digits each)
            values = [MAC[x:x + 2] for x in range(0, len(MAC)-1, 2)]

        # ensure we only have 6 octets of two characters each
        if ((len(values) != 6) or True in
            [(1 > len(octet) or len(octet) > 2) for octet in values]):
            raise self.MACAddressError, (_("Malformed MAC address"))

        # ensure all octets are 8-bit -- and valid HEX
        try:
            if False in [0 <= int(value, 16) <= 255 for value in values]:
                raise self.MACAddressError, (_("Malformed MAC address"))
        # if value was non-numeric we will have had a type error or value error
        except (TypeError, ValueError):
            raise self.MACAddressError, (_("Malformed MAC address"))

        self.extend([value.zfill(2) for value in values])

    def join(self, sep=":"):
        '''
        Return a delimiter punctuated representation
        '''
        return sep.join(self)

    def __str__(self):
        '''
        Return a non-delimiter punctuated representation
        '''
        return "".join(self)


class GrubMenu(DBFile):
    '''
    Class to handle opening and reading GRUB menu, see
    http://www.gnu.org/software/grub/manual/grub.html for more on GRUB menu
    format
    Keys will be the grub menu entries and key "" will be the general commands
    which begins the menu before the first title
    '''

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
        '''
        Wrap dict class to ignore the parent reference passed to the _Result
        class (which would be used for updating the backing store of a
        DBFile() instance normally)
        '''
        def __init__(self, parent, key):
            # store what we are representing
            self.update(super(DBFile, parent).get(key))

    def __init__(self, file_name="/boot/grub/menu.lst", mode="r"):
        super(GrubMenu, self).__init__(file_name=file_name, mode=mode)

    def _load_data(self):
        '''
        Load each entry and the keys for each grub menu entry (such as module,
        kernel$, splashimage, etc. lines)
        Miscellaneous note: the module and kernel lines may have a '$' after
        them or not, consumer beware
        '''
        # see if the file has changed since last read
        if self.mtime == os.stat(self.file_obj.file_name)[stat.ST_MTIME]:
            return

        # file has changed since last read
        file_data = self.file_obj.read_all()

        # update the file mtime to keep track
        self.mtime = os.stat(self.file_obj.file_name)[stat.ST_MTIME]

        # need to clear current entries
        super(DBFile, self).clear()

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
            return {}

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
            entry_dict = {}

            # iterate over all lines
            for line in entry:
                # skip empty lines or comments
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                # some GRUB menus have things like
                # timeout = 30 opposed to timeout 30, replace the = with a space
                line = re.sub('^(?P<key>[^\s=]*?)=', '\g<key> ', line)
                entry_dict.update([line.lstrip().split(None, 1)])

            # add this GRUB entry to the GrubMenu object's dict
            # key is the entry's title and entry_dict is its object
            super(DBFile, self).update({title: entry_dict})

    # provide the entries of the grub menu as a property
    @property
    def entries(self):
        '''
        Return a list of all Grub title entries in the GRUB menu
        '''
        # need to return all keys except "" which are the general menu commands
        return [key for key in self.keys() if key]

    # do not support writing to the GRUB menu yet
    __setitem__ = None
    __delitem__ = None

class DHCPData:
    '''
    Class to query Solaris DHCP server configuration material
    '''

    def __init__(self):
        '''
        No state stored and this is server wide data, so do not make an
        instance of this class
        '''
        raise TypeError("class does not support creating an instance.")

    class DHCPError(Exception):
        '''
        Class to report various DHCP related errors
        '''
        pass

    @staticmethod
    def networks():
        '''
        Return a list of networks configured on the DHCP server, if any error
        is generated raise it as a DHCPError.
        '''
        # first get a list of networks served
        try:
            data = run_cmd({"cmd": ["/usr/sbin/pntadm", "-L"]})
        except SystemError, e:
            # return a DHCPError on failure
            raise DHCPData.DHCPError (e)

        # produce a list of networks like
        # ["172.20.24.0",
        #  "172.20.48.0"]
        return data["out"].split()

    @staticmethod
    def macros():
        '''
        Returns a dictionary of macros and symbols with keys: Name, Type and
        Value. In case of an error raises a DHCPError
        '''
        # get a list of all server macros
        try:
            macro = run_cmd({"cmd": ["/usr/sbin/dhtadm", "-P"]})
        # if run_cmd errors out we should too
        except SystemError, e:
            raise DHCPData.DHCPError (e)

        # produce a list like:
        # ['Name", "Type", "Value",
        #  "==================================================",
        #  "0100093D143663", "Macro",
        #  ":BootSrvA=172.20.25.12:BootFile="0100093D143663":"]

        # split into fields
        macro["data"] = [ln.split(None, 2) for ln in macro["out"].split("\n")]

        # headers will consist of "Name", "Type", "Value"
        # (will be the first line)
        headers = macro["data"][0]

        # remove the headers, line of ='s and trailing newline
        # (first three lines)
        del(macro["data"][0:2])
        # strip the trailing newline
        del(macro["data"][-1])

        # build a dict with each header a key to a list built of each row
        macro['macros'] = dict(zip(headers, [[row[i] for row in macro['data']]
                               for i in range(0, len(headers))]))
        return (macro["macros"])

    @staticmethod
    def clients(net):
        '''
        Return a dictionary with keys 'Client ID', 'Flags', 'Client IP',
        'Server IP', 'Lease Expiration', 'Macro', 'Comment', on error raise a
        DHCPError
        '''
        # iterate over the networks looking for clients
        # keep state in the dictionary so initialize it out side the loop
        systems = {}
        systems['cmd'] = ["/usr/sbin/pntadm", "-P", net]
        try:
            systems = run_cmd(systems)
        # if run_cmd errors out we should too
        except SystemError, e:
            raise DHCPData.DHCPError (e)

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
            ln in systems["out"].split("\n")]

        # the first line will be the headers
        headers = systems['out'][0]
        # strip white space
        headers = [obj.strip() for obj in headers]

        # strip headers, intermediate blank and footer blank
        # (the first three lines)
        del(systems['out'][0:2])
        # strip the trailing newline
        del(systems['out'][-1])

        # build a dict with each header a key to a list built of each row
        systems['data'] = dict(zip(headers, [[row[i] for row in systems['out']]
                               for i in range(0, len(headers))]))

        # strip white space in data
        for key in systems['data']:
            systems['data'][key] = [obj.strip() for
                obj in systems['data'][key]]
        return (systems['data'])

#
# General functions below
#

def run_cmd(data):
    '''
    Run a command given by a dictionary and run the command, check for stderr
    output, return code, and populate stdout and stderr. One can check the
    return code, if catching SystemError, via data["subproc"].returncode.
    Raises: SystemError if command errors in some way
    '''
    try:
        data["subproc"] = subprocess.Popen(data["cmd"],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # unable to find command will result in an OSError
    except OSError, e:
        raise SystemError (_("Failure running subcommand %s:\n%s\n") %
                           (" ".join(data["cmd"]), str(e)))

    # fill data["out"] with stdout and data["err"] with stderr
    data.update(zip(["out", "err"], data["subproc"].communicate()))

    # if we got anything on stderr report it and exit
    if(data["err"]):
        raise SystemError (_("Failure running subcommand %s.\n" +
                           "Got output:\n%s") %
                           (" ".join(data["cmd"]), data["err"]))
    # see if command returned okay, if not then there is not much we can do
    if(data["subproc"].returncode):
        raise SystemError (_("Failure running subcommand %s result %s\n") %
                           (" ".join(data["cmd"]),
                           str(data["subproc"].returncode)))
    return data

def find_TFTP_root():
    '''
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

    Throws
        None
    '''
    # default tftpboot dir
    defaultbasedir = "/tftpboot"

    # baseDir is set to the root of in.tftpd
    basedir = ""

    svclist = [ "/usr/bin/svcprop", "-p", "inetd_start/exec", "tftp/udp6" ]
    try:
        pipe = subprocess.Popen(svclist,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        stdout, stderr = pipe.communicate()
    except (OSError, ValueError):
        sys.stderr.write(_('%s: error: retrieving SMF service '
                           'key property for tftp/udp6 service\n') %
                           os.path.basename(sys.argv[0]))
        return defaultbasedir

    # check for stderr output
    if stderr:
        sys.stderr.write(_('%s: warning: unable to locate SMF service '
                           'key property inetd_start/exec for '
                           'tftp/udp6 service. Using default value.\n') %
                           os.path.basename(sys.argv[0]))
        basedir = defaultbasedir
    else:
        # svcprop returns "<tftpd command>\ -s\ <directory>\n"
        # split the line up around " -s\ ".
        svcprop_out = stdout.partition(" -s\ ")
        # be sure to remove the '\n' character.
        basedir = svcprop_out[2].rstrip("\n")
        if not basedir:
            basedir = defaultbasedir

    return basedir
