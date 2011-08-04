#! /usr/bin/python2.6
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
menu.lst parser implementation for pybootmgmt
"""

import errno
import grp
import os
import pwd
import re
import shutil
import stat
import tempfile
from ... import BootmgmtConfigWriteError, BootmgmtArgumentError
from ...bootloader import BootLoaderInstallError
from ...bootconfig import BootConfig


class MenuLstError(Exception):
    def __init__(self, msg):
        super(MenuLstError, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg


class MenuLstComment(object):
    def __init__(self, comment):
        self._comment = comment

    def update_comment(self, comment):
        self._comment = comment

    def __str__(self):
        return self._comment.rstrip('\n')


class MenuLstCommand(object):
    """A menu.lst command and its arguments from the menu.lst file"""

    def __init__(self, command, args=None):
        self._command = command
        self.set_args(args)

    def get_command(self):
        return self._command

    def get_args(self):
        return self._args

    def set_args(self, args):
        if args is None:
            self._args = []
        else:
            # Args can either be a string or a list-like object
            if isinstance(args, basestring):
                # If a plain string is supplied, turn it into a
                # list of arguments:
                pattern = (r'([^ \t"]+"([^\\"]|\\.)*"[^ \t]*|'
                           r'([^ \t\\"]|\\.)*"[^"]*(?![^"]*")|'
                           r'[^ "\t]+)')
                argv = [v[0] for v in re.compile(pattern).findall(args)]
                self._args = argv
            else:
                self._args = args

    def __str__(self):
        if not self._command is None and not self._args is None:
            return self._command + ' ' + ' '.join(self._args)
        elif not self._command is None:
            return self._command
        else:
            return ''

    def __repr__(self):
        ostr = ('(' + repr(self._command) + ',' +
               repr(self._args) + ')')
        return ostr


class MenuLstMenuEntry(object):
    """Representation of a menu.lst menu entry, which consists of a list of
    MenuLstCommand objects (the first of which must be the 'title' command).

    <instance>._cmdlist = [MenuLstCommand #1, MenuLstCommand #2, ...]
    """

    def __init__(self, args=None):
        if args is None:
            self._cmdlist = []
        else:
            self._cmdlist = list(args) # make a copy

    def add_comment(self, comment):
        self._cmdlist.append(MenuLstComment(comment))

    def add_command(self, mlcmd):
        self._cmdlist.append(mlcmd)

    def delete_command(self, cmd):
        for idx, _cmd in enumerate(self._cmdlist):
            if not isinstance(_cmd, MenuLstCommand):
                continue
            if cmd == _cmd.get_command():
                del self._cmdlist[idx]
                return

    def find_command(self, name):
        for cmd in self._cmdlist:
            if isinstance(cmd, MenuLstCommand) and name == cmd.get_command():
                return cmd
        return None

    def update_command(self, cmd, args, create=False):
        entity = self.find_command(cmd)
        if not entity is None:
            entity.set_args(args)
        elif create is True:
            self.add_command(MenuLstCommand(cmd, args))

    def commands(self):
        return [cmd for cmd in self._cmdlist if type(cmd) == MenuLstCommand]

    def __str__(self):
        ostr = ''
        for cmd in self._cmdlist:
            ostr += str(cmd).rstrip('\n') + '\n'
        return ostr.rstrip('\n')

    def __repr__(self):
        ostr = 'MenuLstMenuEntry = ['
        i = 0
        if len(self._cmdlist) >= 1:
            for i in range(len(self._cmdlist) - 1):
                ostr += repr(self._cmdlist[i]) + ', '
        if len(self._cmdlist) >= 2:
            ostr += repr(self._cmdlist[i + 1])
        ostr += ']'
        return ostr


class MenuDotLst(object):

    def __init__(self, filename):
        self.target = self
        self._line = 0
        self._last = ''
        self._entitylist = []        # per-instance list of entities
        self._filename = filename
        self._parse()

    def entities(self):
        """Return a list of entities encapsulated by this MenuDotLst. A new
        list is returned so that deletions can occur in for-loop.
        """
        return list(self._entitylist)

    def delete_entity(self, entity):
        for idx, cur in enumerate(self._entitylist):
            # Yes, I really mean "is" here:
            if cur is entity:
                del self._entitylist[idx]
                return

    def add_comment(self, comment):
        self._entitylist.append(MenuLstComment(comment))

    def add_command(self, cmd):
        "Add a MenuLstCommand or MenuLstMenuEntry to the entitylist"
        self._entitylist.append(cmd)

    def add_global(self, cmd_plus_args):
        "Add a command & args to the end of the global command section"
        # First, find the first menu entry and save that insertion point
        for idx, item in enumerate(self._entitylist):
            if isinstance(item, MenuLstMenuEntry):
                break
        argv = cmd_plus_args.split(' ', 1)
        if len(argv) > 1:
            args = argv[1]
        else:
            args = None
        self._entitylist.insert(idx, MenuLstCommand(argv[0], args))

    def __str__(self):
        ostr = ''
        for entity in self._entitylist:
            ostr += str(entity) + '\n'
        return ostr

    def __repr__(self):
        return (repr(self._entitylist))

    def _parse(self):
        "Parse the menu.lst file"
        fileobj = open(self._filename)
        try:
            for line in fileobj:
                self._parse_line(line)
            self._parse_line(None)    # end of file reached
        finally:
            fileobj.close()

        self._analyze_syntax()

    def _analyze_syntax(self):
        "This can be overridden in child classes, if needed"
        pass

    @staticmethod
    def _process_escapes(istr):
        res = ''
        newline_escaped = False
        for idx in range(len(istr)):
            #
            # Legacy GRUB allows escaping the newline
            #
            # We're guaranteed to always have a character
            # after the backslash, so no try is needed here.
            if istr[idx] == '\\' and istr[idx + 1] == '\n':
                newline_escaped = True
                res += ' '
            elif istr[idx] != '\n':
                res += istr[idx]
        return res, newline_escaped

    def _parse_line(self, nextline):
        """Parses a line of a menu.lst configuration file.
        The grammar of the menu.lst configuration file is simple:
        Comments are lines that begin with '#' (with or without
        preceeding whitespace), and commands are non-comments that
        include one or more non-whitespace character sequences,
        separated by whitespace.  The commands are not checked
        for semantic correctness.  They're just stored for later
        analysis.

        The parser works as follows:

        If the line is None, parsing is complete, so save the last
        entry processed to the statement list.

        If the line (stripped of any leading whitespace) starts with
        '#', then it's a comment, so save it and return.

        Split the line into a command portion and an optional
        argument(s) portion, taking care to process escape sequences
        (including the special escape of the newline)

        If the line begins with the 'title' keyword, then a new entry
        is created and saved so that future commands can be added to
        it.

        If an entry is active (if we're parsing after a title command),
        add the current command and arguments to the current entry.

        If an entry is not active, add the command and arguments to
        the statement list.

        The configuration file entity list contains commands and
        entries::

        [(MenuLstCommand|CommentString)*, (MenuLstMenuEntry|CommentString)*]

        Comments and blank space is stored as a plain string.
        """

        if nextline is None:
            # If there's still text in the last-line buffer,
            # we must have had a dangling backslash
            if self._last != '':
                raise MenuLstError('Dangling backslash detected')
            return

        self._line += 1

        # If found, add whitespace line/comment to the target
        stripped = nextline.strip()
        if stripped == '' or stripped[0] == '#':
            self.target.add_comment(nextline)
            return

        # Remove escape sequences from the line:
        try:
            nextline, newline_escaped = (
                self._process_escapes(nextline))
        except IndexError:
            # The error must have been a dangling backslash
            raise MenuLstError('Dangling backslash detected')

        # If the newline was escaped, save the string for later
        if newline_escaped:
            self._last += nextline
            return        # Wait for the next line
        else:
            nextline = self._last + nextline
            self._last = ''

        pattern = (r'([^ \t"]+"([^\\"]|\\.)*"[^ \t]*|'
              r'([^ \t\\"]|\\.)*"[^"]*(?![^"]*")|'
              # r'"([^ \t\\"]|\\.)*(?![^"]*[^\\]")|'
               r'[^ "\t]+)')
        argv = [v[0] for v in re.compile(pattern).findall(nextline)]

        if (len(argv) > 0):
            if argv[0] == 'title':
                self.target = MenuLstMenuEntry()
                self._entitylist.append(self.target)
            # Check argv[0] (if it exists) for an equals sign, since 
            # that's a valid way to set certain variables
            argv = argv[0].split('=', 1) + argv[1:]

            self.target.add_command(MenuLstCommand(argv[0], argv[1:]))


#
# This MixIn allows us to share some code that would otherwise be cut and
# pasted between several BootLoader implementations
#
class MenuLstBootLoaderMixIn(object):
    def _write_config_generic(self, basepath, boot_data_root_dir):

        # If basepath is not None, the menu.lst should be written to a file
        # under basepath (instead of to the actual location
        # (boot_data_root_dir))
        if basepath is None:
            realmenu = boot_data_root_dir + self.__class__.MENU_LST_PATH
            tempmenu = realmenu + '.new'

            # Create the parent directories for the menu.lst file here:
            try:
                menu_lst_parent = realmenu.rpartition('/')[0]
                os.makedirs(menu_lst_parent, 0755)
            except OSError as ose:
                # Error during making the directory or the chmod
                # If this is anything other an an EEXIST, we'll probably
                # fail below when trying to write the menu.lst, but that'll
                # be handled below.
                if ose.errno != errno.EEXIST:
                    self._debug('Error while making dirs for menu.lst: ' +
                                str(ose))

            try:
                # Don't open the new menu.lst over the old -- create a
                # temporary file, then, if the write is successful, move the
                # temporary file over the old one.
                outfile = open(tempmenu, 'w')
                self._write_menu_lst(outfile)
                self._debug('menu.lst written to %s' % tempmenu)
                outfile.close()
            except IOError as err:
                raise BootmgmtConfigWriteError("Couldn't write to %s" %
                                               tempmenu, err)

            try:
                shutil.move(tempmenu, realmenu)
                self._debug('menu.lst moved into place as %s' % realmenu)
            except IOError as err:
                try:
                    os.remove(tempmenu)
                except OSError as oserr:
                    self._debug('Error while trying to remove %s: %s' %
                                (tempmenu, oserr.strerror))
                raise BootmgmtConfigWriteError("Couldn't move %s to %s" %
                                               (tempmenu, realmenu), err)

            # Move was successful, so now set the owner and mode properly:
            try:
                os.chmod(realmenu, 0644)
                os.chown(realmenu, pwd.getpwnam('root').pw_uid,
                         grp.getgrnam('root').gr_gid)
            except OSError as oserr:
                raise BootmgmtConfigWriteError("Couldn't set mode/perms on "
                      + realmenu, oserr)

            return None

        # basepath is set to a path.  Use it to form the path to a temporary
        # file
        try:
            tmpfile = tempfile.NamedTemporaryFile(dir=basepath, delete=False)
            self._write_menu_lst(tmpfile)
            tmpfile.close()
        except IOError as err:
            raise BootmgmtConfigWriteError("Couldn't create a temporary "
                  'file for menu.lst', err)

        return [(BootConfig.OUTPUT_TYPE_FILE,
                tmpfile.name,
                None,
                self.__class__.MENU_LST_PATH,
                'root',
                'root',
                0644)]

    def _install_generic(self, location):
        """Invoke the current instance's methods to performing the real
        work of installing the boot loader and its configuration files."""

        data_root = self._get_boot_loader_data_root()

        if isinstance(location, basestring):
            try:
                filemode = os.stat(location).st_mode
            except OSError as err:
                raise BootLoaderInstallError('Error stat()ing %s' % location,
                                             err)

            if stat.S_ISDIR(filemode):
                # We have been given an output directory.  Produce the menu.lst
                # there.
                return self._write_config(location)

            elif stat.S_ISCHR(filemode):
                self._write_loader(location, data_root)
                # Now write the menu.lst:
                self._write_config(None)
            else:
                raise BootmgmtArgumentError('Invalid location argument (%s)'
                                            % location)
        else:
            for devname in location:
                try:
                    filemode = os.stat(devname).st_mode
                except OSError as err:
                    self._debug('Error stat()ing %s' % devname)
                    raise BootLoaderInstallError('Error stat()ing %s'
                                                  % devname, err)
                if stat.S_ISCHR(filemode):
                    self._write_loader(devname, data_root)
                else:
                    raise BootmgmtArgumentError('%s is not a \
                                                characters-special'
                                                ' file' % devname)

            self._write_config(None)

        return None
