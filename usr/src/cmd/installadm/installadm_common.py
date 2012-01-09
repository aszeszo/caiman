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
"""
Common Python Objects for Installadm Commands
"""
import gettext
import logging
import os
import re
import stat
import StringIO
import sys
import time

from textwrap import fill, dedent

from osol_install.libaimdns import getifaddrs, getboolean_property, \
    getstrings_property
from solaris_install import Popen


_ = gettext.translation('AI', '/usr/share/locale', fallback=True).gettext


LOG_FORMAT = ("%(filename)s:%(lineno)d %(message)s")
XDEBUG = 5
logging.addLevelName("xdebug", XDEBUG)
logging.addLevelName(XDEBUG, "xdebug")

#
# General constants below
#

# service type, private
REGTYPE = '_OSInstall._tcp'
DOMAIN = 'local'

# Maximum service name length
MAX_SERVICE_NAME_LEN = 63

# FMRI for AI service and select properties, private
SRVINST = 'svc:/system/install/server:default'
EXCLPROP = 'all_services/exclude_networks'
NETSPROP = 'all_services/networks'
PORTPROP = 'all_services/port'
BASEDIR_PROP = 'all_services/default_imagepath_basedir'

# File used to verify that image is ai netimage
AI_NETIMAGE_REQUIRED_FILE = "solaris.zlib"

# Default port for the webserver
DEFAULT_PORT = 5555

# Location of wanboot-cgi file for sparc dhcp setup
WANBOOTCGI = 'cgi-bin/wanboot-cgi'

# Directory for per service information
AI_SERVICE_DIR_PATH = '/var/ai/service'

# Default image path parent directory
IMAGE_DIR_PATH = '/export/auto_install/'

BOOT_DIR = '/etc/netboot'

# Script paths and arguments
AIWEBSERVER = "aiwebserver"
CHECK_SETUP_SCRIPT = "/usr/lib/installadm/check-server-setup"
IMAGE_CREATE = "create"
SERVICE_DISABLE = "disable"
SERVICE_LIST = "list"
SERVICE_CREATE = "create"
SERVICE_REGISTER = "register"
SETUP_IMAGE_SCRIPT = "/usr/lib/installadm/setup-image"
SETUP_SERVICE_SCRIPT = "/usr/lib/installadm/setup-service"
SETUP_SPARC_SCRIPT = "/usr/lib/installadm/setup-sparc"
SPARC_SERVER = "server"

WEBSERVER_DOCROOT = "/var/ai/image-server/images"

# Needed for the is_multihomed() function
INSTALLADM_COMMON_SH = "/usr/lib/installadm/installadm-common"
KSH93 = "/usr/bin/ksh93"
VALID_NETWORKS = "valid_networks"
WC = "/usr/bin/wc"

# Ripped from installadm.c for now
MULTIHOMED_TEST = ("/usr/bin/test `%(ksh93)s -c 'source %(com-script)s;"
                   " %(valid_net)s | %(wc)s -l'` -eq 1" %
                   {"ksh93": KSH93, "com-script": INSTALLADM_COMMON_SH,
                    "valid_net": VALID_NETWORKS, "wc": WC})


_IS_MULTIHOMED = None

# List of known/supported architectures (reported by uname -m)
KNOWN_ARCHS = ['i86pc', 'sun4u', 'sun4v']

# List of known/supported processor types (reported by uname -p)
KNOWN_CPUS = ['i386', 'sparc']


def is_multihomed():
    ''' Determines if system is multihomed
    Returns True if multihomed, False if not

    '''
    global _IS_MULTIHOMED
    if _IS_MULTIHOMED is None:
        logging.debug("is_multihomed(): Calling %s", MULTIHOMED_TEST)
        _IS_MULTIHOMED = Popen(MULTIHOMED_TEST, shell=True).wait()
    return (_IS_MULTIHOMED != 0)


def setup_logging(log_level):
    '''Initialize the logger, logging to stderr at log_level,
       log_level defaults to warn

    Input:
        Desired log level for logging
    Return:
        None
    '''
    logging.basicConfig(stream=sys.stderr, level=log_level, format=LOG_FORMAT)


if "PYLOG_LEVEL" in os.environ:
    try:
        setup_logging(int(os.environ["PYLOG_LEVEL"]))
    except (TypeError, ValueError):
        pass


def ask_yes_or_no(prompt):
    ''' Prompt user if it is ok to do something.
        Input: prompt - question to ask user
        Returns: True - if user agrees
                 False otherwise (default)
        Raises: KeyboardInterrupt if user hits ctl-c

    '''
    yes_set = set(['yes', 'y', 'ye'])
    no_set = set(['no', 'n', ''])
    while True:
        try:
            choice = raw_input(prompt).lower()
        except EOFError:    # ctrl-D
            return False
        if choice in yes_set:
            return True
        elif choice in no_set:
            return False
        else:
            sys.stdout.write(_("Please respond with 'yes' or 'no'\n"))


_text_wrap = lambda(t): fill(dedent(t), replace_whitespace=False, width=70)


def cli_wrap(text):
    """
    Generic textwrapper for use with installadm. Source modules can use this
    utility to ensure appropriate formatting for the CLI's output when
    printing longer-than-70-character strings. Note that the wrap width is not
    dynamic, it is hardcoded at 70 characters.

    The argument 'text' is processed into a list of strings and returned as a
    rejoined string. The text is first dedented, which removes any leading
    whitespace (as might be seen with a block-quoted string), and it is then
    line-wrapped at 70 characters.
    """
    return ("\n".join(map(_text_wrap, text.splitlines())) + "\n")


#
# General classes below
#

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
        lines = list()

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
        except IOError as msg:
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
    _headers = list()

    def __init__(self, **kwargs):
        """
        Open file and read it in. Will throw exceptions when errors are
        encountered. Expected arguments of a string for a StringIO backed store
        or file_name and mode for a file backed store; e.g.:
        file_foo = DBBase(file_name="/etc/mnttab", mode="w")
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
        fields = list()

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


def validate_service_name(svcname):
    ''' Validate service name

    Verify that characters in a service name are limited to
    alphanumerics, hyphen and underscore, and that the first
    character is not a hyphen.

    Args:
        svcname - Name of service
    Return: nothing
    Raises: ValueError if name is invalid

    '''
    error = cli_wrap(_('\nError:  The service name must contain only '
                       'alphanumeric chars, "_" and "-" and be shorter than '
                       '64 characters in length. The first character may not '
                       'be a "-".\n'))

    if not svcname:
        raise ValueError(error)

    if len(svcname) > MAX_SERVICE_NAME_LEN:
        raise ValueError(error)

    if svcname.startswith('-'):
        raise ValueError(error)

    # Accept alphanumeric chars, '-', and '_'. By removing '-' and
    # '_' from the string, isalnum can be used to test the rest
    # of the characters.
    svcname = svcname.replace("-", "").replace("_", "")
    if not svcname.isalnum():
        raise ValueError(error)


def _convert_ipv4(ip):
    '''Converts an IPv4 address into an integer
       Args:
            ip - IPv4 address to convert

       Returns:
            an integer of the converted IPv4 address

       Raises:
            None
    '''
    seg = ip.split('.')
    return (int(seg[3]) << 24) + (int(seg[2]) << 16) + \
            (int(seg[1]) << 8) + int(seg[0])


def _convert_cidr_mask(cidr_mask):
    '''Converts a CIDR mask into an IPv4 mask
        Args:
            cidr_mask - CIDR mask number

        Returns:
            IPv4 mask address

        Raises:
            None
    '''
    mask_tuple = (0, 128, 192, 224, 240, 248, 252, 254, 255)

    # edge cases
    if cidr_mask > 32:
        return None
    if cidr_mask == 0:
        return '0.0.0.0'

    mask = ['255'] * (cidr_mask // 8)

    if len(mask) != 4:
        # figure out the partial octets
        index = cidr_mask % 8
        mask.append(str(mask_tuple[index]))

    if len(mask) != 4:
        mask.extend(['0'] * (3 - (cidr_mask // 8)))

    # join the mask array together and return it
    return '.'.join(mask)


def compare_ipv4(ipv4_one, ipv4_two):
    '''Compares two IPv4 address for equality
       Args:
           ipv4_one - IPv4 address, can contain CIDR mask
           ipv4_two - IPv4 address, can contain CIDR mask

       Returns:
           True if ipv4_one equals ipv4_two else
           False

       Raises:
           None
    '''
    # ensure there is no '/' (slash) in the first address,
    # effectively ignoring the CIDR mask.
    slash = ipv4_one.find('/')
    if '/' in ipv4_one:
        ipv4_one = ipv4_one[:slash]
    ipv4_one_num = _convert_ipv4(ipv4_one)

    # convert ipv4_two taking into account the possible CIDR mask
    if '/' not in ipv4_two:
        mask_two = _convert_cidr_mask(0)
        ipv4_two_num = _convert_ipv4(ipv4_two)
    else:
        mask_two = _convert_cidr_mask(int(ipv4_two.split('/')[-1]))
        if not mask_two:
            return False  # invalid mask
        ipv4_two_num = _convert_ipv4(ipv4_two.split('/')[0])
    mask_two_num = _convert_ipv4(mask_two)

    if '/' in ipv4_two and \
         mask_two_num & ipv4_two_num == mask_two_num & ipv4_one_num:
        return True
    elif ipv4_one_num == ipv4_two_num:
        return True

    return False


def in_networks(inter_ipv4, networks):
    '''Description:
        Checks to see if a single IPv4 address is in the list of
        networks

    Args:
        inter_ipv4 - an interface IPv4 address
        networks   - a list of networks from the SMF property networks

    Returns:
        True if the interface's IPv4 address is in the network -- OR --
        False if it is not

    Raises:
        None
    '''
    # iterate over the network list
    for network in networks:
        # check if the interface's IPv4 address is in the network
        if compare_ipv4(inter_ipv4, network):
            return True
    return False


def get_valid_networks():
    '''Description:
        Gets the valid networks taking into account the all_services/networks
        and all_services/exclude_networks service properties.

    Args:
        None

    Returns:
        a set of valid networks.

    Raises:
        None
    '''
    # get the currently configured interfaces
    interfaces = getifaddrs()
    # get the exclude and networks service property values
    exclude = getboolean_property(SRVINST, EXCLPROP)
    networks = getstrings_property(SRVINST, NETSPROP)

    valid_networks = set()
    for inf in interfaces:
        # check the interface IP address against those listed in
        # the AI service SMF networks property.  Our logic for the
        # SMF exclude_networks and SMF networks list is:
        #
        #   IF ipv4 is in networks and
        #      SMF exclude_networks == false
        #   THEN include ipv4
        #   IF ipv4 is not in_networks and
        #      SMF exclude_network == true
        #   THEN include ipv4
        #   IF ipv4 is in_networks and
        #      SMF exclude_networks == true
        #   THEN exclude ipv4
        #   IF ipv4 is not in_networks and
        #      SMF exclude_network == false
        #   THEN exclude ipv4
        #
        # Assume that it is excluded and check the first 2 conditions only
        # as the last 2 conditions are covered by the assumption.
        in_net = in_networks(interfaces[inf], networks)
        include_it = False
        if (in_net and not exclude) or (not in_net and exclude):
            include_it = True

        if not include_it:
            continue

        mask = interfaces[inf].find('/')
        if mask == -1:
            mask = len(interfaces[inf])
        valid_networks.add(interfaces[inf][:mask])

    return valid_networks


if __name__ == "__main__":
    import doctest
    doctest.testmod()
