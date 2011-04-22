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
x86 Solaris Boot variables backend support for pybootmgmt
"""

import tempfile
import sys
import logging
import shutil
from .... import bootinfo
from .... import BootmgmtMalformedPropertyNameError, BootmgmtArgumentError
from .... import BootmgmtReadError, BootmgmtWriteError

logger = logging.getLogger('bootmgmt')

class BootenvBootVariables(bootinfo.BootVariables):
    """This class supports manipulation of boot variables stored in the
    <root>/boot/solaris/bootenv.rc file."""

    BOOTENV_RC = '/boot/solaris/bootenv.rc'

    def __init__(self, sysroot=None):
        self.BOOTENV_DOT_RC = sysroot + BootenvBootVariables.BOOTENV_RC
        self._dirty = False
        super(BootenvBootVariables, self).__init__(sysroot)

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        if not type(value) is bool:
            raise ValueError('dirty is a bool')
        if self._dirty != value:
            logger.debug(self.__class__.__name__ + ': dirty => %s' % str(value))
            self._dirty = value

    def setprop(self, propname, value):
        # if the property name contains whitespace, it's invalid
        if len(set(propname).intersection(' \t')) > 0:
            raise BootmgmtMalformedPropertyNameError('Invalid property name' +
                                                     ' ("%s")' % propname)
        if value is None: # Not allowed -- there must be a real value here
            raise BootmgmtArgumentError('value must not be None')

        if propname in self._vardict:
            if self._vardict[propname][1] != value:
                # All we need to do is update the value portion of the list
                # (this automatically "updates" the value stored in _rawlines)
                self._vardict[propname][1] = value
                self.dirty = True
        else:
            proplist = [propname, value]
            # The _vardict must use the same object that's added to _rawlines
            # so that updates are seamless across both containers
            self._vardict[propname] = proplist
            self._rawlines.append(proplist)
            self.dirty = True

        

    def getprop(self, propname):
        val_list = self._vardict.get(propname, None)
        # The values stored in the dictionary are 2-element lists
        # The first element is the prop name and the second is the value
        if not val_list is None and len(val_list) == 2:
            return val_list[1]
        else:
            return None

    def delprop(self, propname):
        if propname in self._vardict:
            # Clear the list first so that _rawlines is "updated" to contain
            # a 0-length list for this property
            del self._vardict[propname][:]
            # Now remove the property from the _vardict dict
            del self._vardict[propname]
            self.dirty = True

    def _read(self):
        """Reads the set of properties from the bootenv.rc file under
           sysroot.  Keeps a copy of the file in memory so comments can
           be preserved."""
        bvfile = self.BOOTENV_DOT_RC
        self._rawlines = []
        self._vardict = {}
        try:
            with open(bvfile) as berc:
                for rawline in berc:
                    nextline = rawline.strip()
                    # skip comment lines
                    if len(nextline) > 0 and nextline[0] != '#':
                        # Store the property in the _rawlines list as a
                        # list so that we can make changes via the _vardict
                        # The form of a line is:
                        # setprop <propname> <propval>
                        # If we find a line that's malformed, ignore it and
                        # continue
                        try:
                            keyword, prop, val = nextline.split(None, 2)
                        except ValueError:
                            logger.debug('Malformed line in ' + bvfile +
                                         ': "%s"' % nextline)
                            continue

                        if keyword != 'setprop':
                            logger.debug('Malformed line in ' + bvfile +
                                         ': "%s"' % nextline)
                            continue

                        newbep = [prop, val]
                        self._rawlines.append(newbep)
                        self._vardict[prop] = newbep
                    else:
                        self._rawlines.append(rawline)

                    
        except IOError as e:
            raise BootmgmtReadError('Error while loading boot variables ' +
                                    'from ' + bvfile, e)

    def write(self, inst, alt_dir=None):
        # Open a new file that will contain the new bootenv.rc, dump all
        # the variables to that file, then move that file over to be the
        # real bootenv.rc

        if not alt_dir is None:
            try:
                fileobj = tempfile.NamedTemporaryFile(dir=alt_dir, delete=False)
            except IOError as err:
                raise BootmgmtWriteError('Error while writing to temporary ' +
                                         'bootenv.rc (%s)' % fileobj.name, err)
            bvfile = fileobj.name
            bvtempfile = bvfile
        else:
            # BOOTENV_DOT_RC has a leading slash:
            bvfile = inst.rootpath + self.BOOTENV_DOT_RC
            bvtempfile = bvfile + '.new'
            try:
                fileobj = open(bvtempfile, 'w')
            except IOError as err:
                raise BootmgmtWriteError('Error while writing to temporary ' +
                                         'bootenv.rc (%s)' % bvtempfile, err)

        try:
            with fileobj as berc:
                # Write each line to the output file -- if the item in
                # _rawlines is a list, construct a setprop command string,
                # otherwise, just copy it verbatim
                for line in self._rawlines:
                    if type(line) is list and len(line) == 2:
                        berc.write('setprop ' + line[0] + ' ' + line[1] + '\n')
                    elif type(line) is str:
                        berc.write(line) # newline is already part of line

        except IOError as err:
            raise BootmgmtWriteError('Error while writing to temporary ' +
                                     'bootenv.rc (%s)' % bvtempfile, err)

        # Now move the file over the become the new bootenv.rc:
        try:
            if not alt_dir is None:
                shutil.move(bvtempfile, bvfile)
            self.dirty = False
        except IOError as ioe:
            try:
                # Try to clean up by deleting the temporary file
                os.remove(bvtempfile)
            except OSError as ose:
                logger.debug("Couldn't clean up temporary bootenv.rc: " +
                             ose.strerror)
                pass
            raise BootmgmtWriteError('Error while moving the temporary ' +
                                     'bootenv.rc (%s) to %s' %
                                     (bvtempfile, bvfile), ioe)

        if not alt_dir is None:
            return ('file', bvfile, inst,
                    '%(systemroot)s' + BootenvBootVariables.BOOTENV_RC,
                    'root', 'sys', 0644)
        else:
            return None

    def __len__(self):
        return len(self._vardict)

    def __iter__(self):
        classic_dict = [(x, z) for (x,[y,z]) in self._vardict.items()]
        return classic_dict.__iter__()            

def bootvars_backend():
    return BootenvBootVariables
