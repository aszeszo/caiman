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

#
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#
"""
Common Python Objects for Installadm Commands
"""

import re
import subprocess
import os
import stat
import sys
import gettext
import time
import StringIO
import copy


#
# General constants below
#

# SPARC netboot constant
NETBOOT = '/etc/netboot'

# service type, private
REGTYPE = '_OSInstall._tcp'
DOMAIN = 'local'

# FMRI for AI service and select properties, private
SRVINST = 'svc:/system/install/server:default'
EXCLPROP = 'all_services/exclude_networks'
NETSPROP = 'all_services/networks'
PORTPROP = 'all_services/port'

# Default port for the webserver
DEFAULT_PORT = 5555

#
# General classes below
#


class AIImage(object):
    """
    Class to hold Auto Installer boot image properties and functions
    """
    def __init__(self, dir_path=None):
        if dir_path:
            # store an absolute path
            self._dir_path = os.path.abspath(dir_path)
            # store the path handed in for error reporting
            self._provided_path = dir_path
        else:
            raise AssertionError("ERROR:\tA directory path is "
                                 "required.")
        # _arch holds the cached image architecture
        self._arch = None
        # check validity of image handed in
        self._check_image()

    def _check_image(self):
        """
        Check that the image exists and appears valid (has a solaris.zlib file)
        Raises: AIImage.AIImageError if path checks fail
        Pre-conditions: Expects self.path to return a valid image_path
        Returns: None
        """
        # check image_path exists
        if not os.path.isdir(self.path):
            raise AIImage.AIImageError(_("Error:\tThe image_path (%s) is not "
                                         "a directory. Please provide a "
                                         "different image path.\n") %
                                       self._provided_path)
        # check that the image_path has a solaris.zlib file
        if not os.path.exists(os.path.join(self.path, "solaris.zlib")):
            raise AIImage.AIImageError(_("Error:\tThe path (%s) is not "
                                         "a valid image.\n") %
                                       self._provided_path)

    class AIImageError(Exception):
        """
        Class to report various AI image related errors
        """
        pass

    @property
    def path(self):
        """
        Returns the image path
        """
        # we should have a dir path, simply return it
        return self._dir_path

    @property
    def arch(self):
        """
        Provide the image's architecture (and caches the answer)
        Raises: AssertionError if the image does not have a /platform [sun4u,
                sun4v, i86pc, amd64]
        Pre-conditions: Expects self.path to return a valid image path
        Returns: "SPARC" or "X86" as appropriate
        """
        # check if we have run before
        if self._arch is not None:
            return(self._arch)
        # check if sun4u or sun4v
        if os.path.isdir(os.path.join(self.path, "platform", "sun4u")) or \
           os.path.isdir(os.path.join(self.path, "platform", "sun4v")):
            self._arch = "SPARC"
            return self._arch
        # check if i86pc or amd64
        if os.path.isdir(os.path.join(self.path, "platform", "i86pc")) or \
           os.path.isdir(os.path.join(self.path, "platform", "amd64")):
            self._arch = "X86"
            return self._arch
        raise AIImage.AIImageError(_("Error:\tUnable to determine "
                                     "architecture of image.\n"))


class FileMethods(object):
    """
    A general class to provide convenience functions for file and file-like
    objects (do not instantiate this class directly -- only inherit from it)
    """

    def readlines(self, skip_comments=True, remove_newlines=True,
                  skip_blanklines=True):
        """
        Enhanced readlines to use enhanced readline -- note size is not
        accepted like with file.readlines()
        """
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
        """
        Add options to readline to remove trailing newline, to skip comment
        lines and to skip blank lines (any line with only whitespace) -- note
        size is not accepted like with file.readline()
        """

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
        line = super(FileMethods, self).readline()
        while line:
            # apply newline function (either strip "\n" or leave as is)
            line = newlineFn(line)
            # loop to the next line if we have a comment or blank line and are
            # not returning such lines
            if commentFn(line) or blanklineFn(line):
                line = super(FileMethods, self).readline()
                continue
            return line
        # if we are out of lines return an empty string
        return ''

    def readlines_all(self, skip_comments=True, remove_newlines=True,
                      skip_blanklines=True):
        """
        Read the entire file in and return the split lines back
        """
        self.seek(0)
        return self.readlines(skip_comments=skip_comments,
                              remove_newlines=remove_newlines,
                              skip_blanklines=skip_blanklines)

    def read_all(self):
        """
        Read the entire file in and return the string representation
        Will throw exceptions when errors are encountered.
        """
        if not self.is_readable:
            raise AssertionError("Unable to read from file %s.\n" %
                                 self.file_name)
        self.seek(0)
        return self.read()

    def write_all(self, data):
        """
        Write out data to the file and truncate to the correct length
        Argument is the data to write out.
        Will throw an AssertionError when file mode exceptions are encountered.
        Otherwise, IOErrors are passed through when encountered.
        """
        # StringIO does not support the mode property but always allows writes,
        # otherwise check to see if the mode will prohibit writing the entire
        # file (this prevents a non-obvious IOError when the mode prohibits
        # writing: "IOError: [Errno 9] Bad file number")
        if not self.is_writeable:
            raise AssertionError("Unable to write whole file %s.\n" %
                                 self.file_name)

        # write the file out
        self.seek(0)
        try:
            self.write(data)
            self.truncate()
            self.flush()
        except IOError, msg:
            raise IOError("Unable to write to file %s: %s\n" %
                          (self.file_name, msg))
    # provide the raw text of file as a property
    raw = property(read_all, write_all,
                   doc="Get or write the entirety of file")


class File_(FileMethods, file):
    """
    Implement a class which provides access to the built-in file class with
    convenience methods provided by the local FileMethods class.
    """
    def __init__(self, file_name, mode):
        """
        Record the file name in the class then call the superclass init()
        """
        self.file_name = file_name
        super(File_, self).__init__(file_name, mode)

    @property
    def is_readable(self):
        """
        Check we are not in append only mode, this prevents a
        non-obvious IOError when the mode prohibits reading:
        "IOError: [Errno 9] Bad file number")
        """
        if "r" in self.mode:
            return True
        return False

    @property
    def is_writeable(self):
        """
        Check to see if the mode will prohibit writing the entire
        file (this prevents a non-obvious IOError when the mode prohibits
        writing: "IOError: [Errno 9] Bad file number")
        """
        if "a" in self.mode or ("r" in self.mode and "+" not in self.mode):
            return False
        return True

    @property
    def last_update(self):
        """
        Fuction to answer question when was the file last updated
        """
        # return the file's last update time
        # (overload this function to abstract class for non-file use)
        return os.stat(self.file_name)[stat.ST_MTIME]


class StringIO_(FileMethods, StringIO.StringIO):
    """
    Implement a class which provides access to the built-in file class with
    convenience methods provided by the local FileMethods class.
    """
    def __init__(self, data):
        """
        Record the creation time in the class then call the superclass init()
        """
        # set the mtime for this to creation
        self.last_update = time.time()
        # it would be nicer to set this to whence the string data came
        self.file_name = "string data"
        StringIO.StringIO.__init__(self, data)

    @property
    def is_readable(self):
        """
        StringIO does not suppor thte mode property but always allows reads.
        """
        return True

    @property
    def is_writeable(self):
        """
        StringIO does not support the mode property but always allows writes,
        """
        return True

    # disable writing since these shouldn't be dumped anywhere
    write = None
    writelines = None
    truncate = None


class DBBase(dict):
    """
    Implements object oriented access to a "database" data -- any data with a
    delimited column/table format. One can query fields through dictionary
    style key look-ups (i.e. dbbase_obj['FIELD']) or attribute access such as
    dbbase_obj.fields.FIELD, both return lists which are indexed so that a
    line from the file can be reconstructed as:
    dbbase_obj.field.DEVICE[idx]\tdbbase_obj.field.FSCK_DEVICE...
    Otherwise, one can read the entire file via dbbase_obj.file_obj.raw or
    overwrite the entire file by assigning dbbase_obj.file_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but object.fields.FIELD2,
    object.fields.FIELD1, etc. A list of fields is available through
    object.fields(). This allows the implementation to evolve, if necessary.
    """

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

    def __init__(self, **kwargs):
        """
        Open file and read it in. Will throw exceptions when errors are
        encountered. Expected arguments of a string for a StringIO backed store
        or file_name and mode for a file backed store; e.g.:
        file_foo = DBBase(file_name="/etc/vfstab", mode="w")
        string_foo = DBBase(big_string_of_databasy-ness)
        """
        # run the generic dict() init first
        super(DBBase, self).__init__()

        # create a File_ to work from if file_name was provided
        if 'file_name' in kwargs:
            # default to read file, if not otherwise set
            self.file_obj = File_(kwargs['file_name'],
                                  kwargs.setdefault('mode', 'r'))
        # if not, this must be a string for StringIO
        else:
            self.file_obj = StringIO_(kwargs)
        # mtime holds the file_obj's last read mtime
        self.mtime = None

        # build a dictionary for the full text headers and the objects
        # representing them (e.g. headers = \
        # {"MOUNT_POINT": MOUNT_POINT} == {"MOUNT_POINT": "mount_point"})
        self.headers = dict(
                            zip(self._fields,
                                [eval("self._" + obj)
                                 for obj in self._fields]))

        # read data in and throw any errors during init if reading the file is,
        # already broken and going to cause problems (will not prevent future
        # errors if file otherwise breaks)
        self._load_data()

    def _load_data(self):
        """
        Read file from beginning and load data into fields, one record per row
        """
        # see if the file has updated since last read (attempt at caching)
        if self.mtime == self.file_obj.last_update:
            return

        # clear all keys as we'll be repopulating (if we have populated before)
        super(DBBase, self).clear()

        # update the file mtime to keep track (NOTE: there is a potential
        # change between when we store this mtime and do the readline_all()
        # below)
        self.mtime = self.file_obj.last_update

        # store the intermediate split fields
        fields = []

        # now produce a list of lists for each field:
        # [[field1] [field2] [field3]]

        # split the file into a list of lists of fields
        # (ensure we don't split on white space on trailing field so limit the
        # number of splits to the number of headers (well, headers minus one,
        # since 2 fields eq. 1 split))
        fields = [line.split(None, len(self.headers) - 1) for line in
            self.file_obj.readlines_all(skip_comments=True,
                                        remove_newlines=True,
                                        skip_blanklines=True)
            if len(line.split(None, len(self.headers) - 1)) == \
               len(self.headers)]

        # build a dict with each header a key to a list
        # built of each row from the file
        super(DBBase, self).update(
            dict(
            # use _headers which is a list with the correct order
                zip(self._headers, [[row[i] for row in fields] for i in
                                     range(0, len(self._headers))])
            )
        )

    def _attrproperty(wrapped_function):
        """
        Function to provide attribute look-up on a function as a property
        (obj is the self passed into the function which is wrapped)
        """
        class _Object(list):
            """
            An object to return for attribute access
            """
            def __init__(self, obj):
                # run the generic list() init first
                super(_Object, self).__init__()

                self.obj = obj
                # represent the fields available if wrapped_function is just
                # returning this function
                self = obj.headers

            def __getattr__(self, key):
                """
                Provide an interface so one can run:
                _object_instance.ATTRIBUTE:
                """
                return wrapped_function(self.obj, key)

            def __call__(self):
                """
                Return valid keys if the class is simply called to avoid
                exposing this class
                """
                return wrapped_function(self.obj)

        # return a property which returns the _Object class
        return property(_Object)

    @_attrproperty
    def fields(self, attr=None):
        """
        Return a list of fields (with descriptions) if called (i.e.
        self.fields()a
        Otherwise, return a field if called as an attribute accessor (i.e.
        self.fields.DEVICE would return the DEVICE field)
        """
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
        """
        Provide a wrapped interface so one can run
        if "/dev/dsk/c0t0d0s0" in dbbase_obj['DEVICE'] and get the most up to
        date data for the file:
        """
        # ensure we're getting accurate data
        self._load_data()
        # ensure key is valid
        if key not in self:
            raise KeyError(key)
        # return a field object, populated from the dictionary
        return self._Result(self, key)

    def get(self, key, default=None):
        """
        Provide a wrapped interface so one can run
        if "/dev/dsk/c0t0d0s0" in dbbase_obj.get('DEVICE') and get the most
        up to date data for the file:
        """
        # ensure we're getting accurate data
        self._load_data()
        # ensure key is valid
        if key in self:
            # return a field object, populated from the dictionary
            return self._Result(self, key)
        # else return default
        return default

    def keys(self):
        """
        Provide all field titles stored as dictionary keys
        """
        self._load_data()
        return super(DBBase, self).keys()

    # we do not want to deal with rewriting by key
    __setitem__ = None

    class _Result(list):
        """
        Class to represent field data as produced by _load_data used for
        updating and removing entries in the backing file
        """
        def __init__(self, parent, key):
            # store what we are representing
            self.extend(super(DBBase, parent).get(key))
            # store in what field of the parent we can be found
            self.field = key
            # store the parent object
            self.parent = parent

        def __delitem__(self, index):
            """
            Remove an item(s) from the result list and remove its backing store
            record(s) for the particular item, returning the number of
            deletions made -- if one record is repeated.
            This is done constructing a regular expression to match the record
            by matching each field which should be removed separated by white
            space for this record.
            """
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
            self.parent.file_obj.raw = re.sub(regex, "\g<end>",
                                              self.parent.file_obj.raw)

        # we do not want to deal with rewriting by key
        __setitem__ = None


class INETd_CONF(DBBase):
    """
    Allow OO access to the /etc/inet/inetd.conf file. All DBBase methods are
    available.
    """

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


class MNTTab(DBBase):
    """
    Implements object oriented access to the /etc/mnttab file. One can query
    fields through dictionary style key look-ups (i.e. mnttab_obj['DEVICE']) or
    attribute access such as mnttab_obj.DEVICE both return lists which are
    indexed so that a line from the file can be reconstructed as
    mnttab_obj[device][idx]\tmnttab_obj[fsckDevice]...
    Otherwise, one can read and write the entire file via
    mnttab_obj.file_obj.raw.

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'device', 'fsckDev', etc.) but MNTTab.DEVICE, MNTTab.FSCK_DEVICE,
    etc. to allow the implementation to evolve, if necessary.

    One can remove a record in the file by running:
    del(mnttab_obj.fields.FIELD[idx])
    """

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


class VFSTab(DBBase):
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

    One can remove a record in the file by ruining:
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


class MACAddress(list):
    """
    Class to store and verify MAC addresses
    """

    class MACAddressError(Exception):
        """
        Class to report MAC address mal-formatted problems
        """
        pass

    def __init__(self, MAC):
        """
        Initialize a MAC address object. Will verify the address is reasonable.
        Can accept ':' or '-' delimited addresses or hex strings with no
        punctuation (and is case insensitive)
        Raises: MACAddressError if not acceptable.
        """
        # ensure a MACAddress was passed in
        if not MAC:
            raise AssertionError("MACAddress class expects an argument")
        # check if MAC has a delimiter
        elif ':' in MAC:
            values = MAC.split(":")
        elif '-' in MAC:
            values = MAC.split("-")

        # MAC doesn't appear to have a delimiter, split it into pairs
        else:
            # ensure we are zero padded and the correct length
            if len(MAC) != 12:
                raise self.MACAddressError, (_("Malformed MAC address"))
            # group into octets (lists of two digits each)
            values = [MAC[x:x + 2] for x in range(0, len(MAC) - 1, 2)]

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

        # run the generic list() init (with the MAC address passed in as an
        # upper-case 6-tupple with every octet of length two)
        value = [value.upper().zfill(2) for value in values]
        super(MACAddress, self).__init__(value)

    def join(self, sep=":"):
        """
        Return a delimiter punctuated representation
        """
        return sep.join(self)

    def __str__(self):
        """
        Return a non-delimiter punctuated representation
        """
        return "".join(self)


class GrubMenu(DBBase):
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
                super(DBBase, parent).get(key))

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
        super(DBBase, self).clear()

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
                # timeout = 30 opposed to timeout 30, replace the = with a
                # space
                line = re.sub('^(?P<key>[^\s=]*?)=', '\g<key> ', line)
                entry_dict.update([line.lstrip().split(None, 1)])

            # add this GRUB entry to the GrubMenu object's dict
            # key is the entry's title and entry_dict is its object
            super(DBBase, self).update({title: entry_dict})

    # provide the entries of the grub menu as a property
    @property
    def entries(self):
        """
        Return a list of all Grub title entries in the GRUB menu
        """
        # need to return all keys except "" which are the general menu commands
        return [key for key in self.keys() if key]

    # do not support writing to the GRUB menu yet
    __setitem__ = None
    __delitem__ = None


class LOFI(DBBase):
    """
    Implements object oriented access to lofiadm(1). One can query
    fields through dictionary style key look-ups (i.e. lofi_obj['DEVICE']) or
    attribute access such as lofi_obj.fields.DEVICE both return lists which
    are indexed so that a line from the file can be reconstructed as
    lofi_obj[device][idx]\tlofi_obj[file]...
    Otherwise, one can add and remove lofi devices via
    lofi_obj.add(path), lofi_obj.remove(lofi # or path).

    For accessing fields it is recommended one not use the direct strings
    (i.e. 'Block Device', 'File', etc.) but using the attribute,
    etc. to allow the implementation to evolve, if necessary.
    """
    # field variables
    _DEVICE = "Block Device"
    _FILE = "File"
    _OPTIONS = "Options"

    # command interface
    _lofi_state = {"cmd": ["/usr/sbin/lofiadm"]}

    # single class instance
    _instance = None

    # the order of headers from the file needs to be recorded
    _headers = [_DEVICE, _FILE, _OPTIONS]

    # the attribute accessor names (all capital variables of the class with
    # their leading underscore stripped) should be stored for building a list
    # of field names
    _fields = [obj.lstrip("_") for obj in locals().keys()
        if obj.isupper() and locals()[obj] is not None]

    def __new__(cls):
        """
        Upon class instantion return the one class object (make class a
        singleton)
        """
        if not cls._instance:
            # create the instance object
            cls._instance = super(LOFI, cls).__new__(cls)
            # initialize the instance object
            cls._instance.__init__()
        else:
            # refresh the already existing instance object
            cls._instance._load_data()
        return cls._instance

    def add(self, path, device=None):
        """
        Add a file to the lofi system
        arguments: file path to create a loop-back mount on
        returns: lofidevice path (i.e. /dev/lofi/1)
        raises: SystemExit if lofiadm(1) returns an error (passed from
                run_cmd())
        """
        # copy the path to lofiadm(1)
        cmd = {'cmd': copy.copy(self._lofi_state['cmd'])}
        # add the a option and file path
        cmd['cmd'].extend(["-a", path])
        if device:
            cmd['cmd'].extend(device)
        cmd = run_cmd(cmd)
        # return the /dev/lofi device returned (with trailing \n striped)
        return cmd['out'].strip()

    def remove(self, path):
        """
        Remove a lofi device from the system
        arguments: path to remove /dev/lofi/ device or filepath mounted
        returns: nothing
        raises: SystemExit if lofiadm(1) returns an error (passed from
                run_cmd())
        """
        # copy the path to lofiadm(1)
        cmd = {'cmd': copy.copy(self._lofi_state['cmd'])}
        # add the a option and file path
        cmd['cmd'].extend(["-d", path])
        cmd = run_cmd(cmd)

    def _load_data(self):
        """
        Private method to refresh the LOFI object
        pre-conditions: class has an initialized instance
        post-conditions: the class dictionary _lofi_state['out'] object will
                         contain the current output of "/usr/sbin/lofiadm"
                         (i.e. added lofi mounts)
        """
        # run lofiadm(1) to get a list output (store this once across all
        # instances since lofi(7) is kernel wide)
        self.__class__._lofi_state = run_cmd(self._lofi_state)
        # note index will throw a value error if it can not find a newline,
        # however, if lofiadm(1) works at all we should have at least headers
        # and a newline
        self._lofi_state['out'] = \
            self._lofi_state['out'][self._lofi_state['out'].index("\n") + 1:]
        # update the file_obj backing store
        self.file_obj = StringIO_(self._lofi_state['out'])
        # reparse the output
        super(LOFI, self)._load_data()


class DHCPData:
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
    def networks():
        """
        Return a list of networks configured on the DHCP server, if any error
        is generated raise it as a DHCPError.
        """
        # first get a list of networks served
        try:
            data = run_cmd({"cmd": ["/usr/sbin/pntadm", "-L"]})
        except SystemExit, e:
            # return a DHCPError on failure
            raise DHCPData.DHCPError(e)

        # produce a list of networks like
        # ["172.20.24.0",
        #  "172.20.48.0"]
        return data["out"].split()

    @staticmethod
    def macros():
        """
        Returns a dictionary of macros and symbols with keys: Name, Type and
        Value. In case of an error raises a DHCPError
        """
        # get a list of all server macros
        try:
            macro = run_cmd({"cmd": ["/usr/sbin/dhtadm", "-P"]})
        # if run_cmd errors out we should too
        except SystemExit, e:
            raise DHCPData.DHCPError(e)

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
        """
        Return a dictionary with keys 'Client ID', 'Flags', 'Client IP',
        'Server IP', 'Lease Expiration', 'Macro', 'Comment', on error raise a
        DHCPError
        """
        # iterate over the networks looking for clients
        # keep state in the dictionary so initialize it out side the loop
        systems = {}
        systems['cmd'] = ["/usr/sbin/pntadm", "-P", net]
        try:
            systems = run_cmd(systems)
        # if run_cmd errors out we should too
        except SystemExit, e:
            raise DHCPData.DHCPError(e)

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
    r"""
    Run a command given by a dictionary and run the command, check for stderr
    output, return code, and populate stdout and stderr. One can check the
    return code, if catching SystemExit, via data["subproc"].returncode.
    Raises: SystemExit if command errors in any way (i.e. a non-zero return
            code or anything in standard error). OSError if command is not
            found or cannot be executed.
    >>> test={"cmd": ["/bin/true"]}
    >>> test=run_cmd(test)
    >>> test={"cmd": ["/usr/bin/echo", "python"]}
    >>> run_cmd(test) # doctest:+ELLIPSIS, +NORMALIZE_WHITESPACE
    {'cmd': ['/usr/bin/echo', 'python'],
     'subproc': <subprocess.Popen object at 0x...>,
     'err': '',
     'out': 'python\n'}
    >>> import gettext
    >>> gettext.install("")
    >>> test={"cmd": ["/bin/false"]}
    >>> try:
    ...  run_cmd(test)
    ... except SystemExit, msg:
    ...  print msg
    ...
    Failure running subcommand /bin/false result 255
    <BLANKLINE>
    >>> test={"cmd": ["/bin/ksh","-c", "print -nu2 foo"]}
    >>> try:
    ...  run_cmd(test)
    ... except SystemExit, msg:
    ...  print msg
    ...
    Failure running subcommand /bin/ksh -c print -nu2 foo.
    Got output:
    foo
    >>> test['err']
    'foo'
    >>> run_cmd({"cmd": ["/does_not_exist"]}) # doctest:+ELLIPSIS
    Traceback (most recent call last):
                    ...
    OSError: Failure executing subcommand /does_not_exist:
    [Errno 2] No such file or directory
    <BLANKLINE>
    """
    try:
        data["subproc"] = subprocess.Popen(data["cmd"],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)
    # unable to find command will result in an OSError
    except OSError, e:
        raise OSError(_("Failure executing subcommand %s:\n%s\n") %
                           (" ".join(data["cmd"]), str(e)))

    # fill data["out"] with stdout and data["err"] with stderr
    data.update(zip(["out", "err"], data["subproc"].communicate()))

    # if we got anything on stderr report it and exit
    if(data["err"]):
        raise SystemExit(_("Failure running subcommand %s.\n" +
                           "Got output:\n%s") %
                           (" ".join(data["cmd"]), data["err"]))
    # see if command returned okay, if not then there is not much we can do
    if(data["subproc"].returncode):
        raise SystemExit(_("Failure running subcommand %s result %s\n") %
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

    svclist = ["/usr/bin/svcprop", "-p", "inetd_start/exec", "tftp/udp6"]
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

if __name__ == "__main__":
    import doctest
    doctest.testmod()
