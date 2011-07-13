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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
Classes and functions for managing client images on an installadm server

Image version history:

0.0:
    Unversioned image (all images prior to webserver consolidation
      putback). These images require a compatibility port on
      the webserver.

1.0:
    First versioned image. Images at or above this version can share
      the webserver's default port. Clients support $serverIP keyword.

2.0:
    Client-side support for System Configuration Profiles added

3.0:
    Sparc images at or above this level can read the install_service
      parameter from the system.conf file. Images prior to this
      level require an install.conf file in the image path (and thus,
      such images CANNOT be aliased) - this is achieved via a symlink
      from install.conf to the system.conf file, as their content
      is identical.

'''
import errno
import os

import osol_install.auto_install.installadm_common as com

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen


_FILE = '/usr/bin/file'


class ImageError(StandardError):
    '''Base class for InstalladmImage-unique errors'''
    pass


class InstalladmImage(object):
    '''Represents an AI client image on the installadm server'''
    
    def __init__(self, image_path):
        self._path = image_path
        self._arch = None
        self._version = None
    
    def verify(self):
        '''
        Check that the image exists and appears valid (has a solaris.zlib file)
        Raises: ImageError if path checks fail
        Pre-conditions: Expects self.path to return a valid image_path
        Returns: None
        '''
        # check image_path exists
        if not os.path.isdir(self.path):
            raise ImageError(cw(_("\nError:\tThe image_path (%s) is not "
                                  "a directory. Please provide a "
                                  "different image path.\n") % self.path))
        # check that the image_path has a solaris.zlib file
        if not os.path.exists(os.path.join(self.path, "solaris.zlib")):
            raise ImageError(cw(_("\nError:\tThe path (%s) is not "
                                  "a valid image.\n") % self.path))
    
    @property
    def version(self):
        '''Returns the AI client image version.
        
        See also the module docstring.
        
        '''
        if self._version is None:
            version = self.read_image_info().get("image_version", "0.0")
            try:
                version = float(version)
            except (ValueError, TypeError):
                version = 0.0
            self._version = version
        return self._version

    def read_image_info(self):
        '''Reads the .image_info file for this image, returning a dictionary
        of its contents. The keys are set to lower-case.
        
        '''
        image_info = dict()
        with open(os.path.join(self.path, ".image_info"), "r") as info:
            for line in info:
                key, valid, value = line.strip().partition("=")
                if valid:
                    image_info[key.lower()] = value
        return image_info
    
    def move(self, new_path):
        '''Move image area to new location
           Return new image path
        '''
        os.rename(self._path, new_path)
        self._path = new_path
        return self._path
    
    @property
    def path(self):
        '''
        Returns the image path
        '''
        return self._path
    
    @property
    def arch(self):
        '''
        Provide the image's architecture (and caches the answer)
        Raises: AssertionError if the image does not have a /platform [sun4u,
                sun4v, i86pc, amd64]
        Pre-conditions: Expects self.path to return a valid image path
        Returns: "sparc" or "i386" as appropriate
        '''
        if self._arch is None:
            platform = os.path.join(self.path, "platform")
            for root, dirs, files in os.walk(platform):
                if "i86pc" in dirs or "amd64" in dirs:
                    self._arch = "i386"
                elif "sun4v" in dirs or "sun4u" in dirs:
                    self._arch = "sparc"
                else:
                    raise ImageError(_("\nError:\tUnable to determine "
                                       "architecture of image.\n"))
                break
        return self._arch
    
    def _prep_ai_webserver(self):
        '''Enable the AI webserver to access the image path'''
        target_path = os.path.dirname(self.path).lstrip("/")
        try:
            os.makedirs(os.path.join(com.WEBSERVER_DOCROOT, target_path))
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        
        dest = os.path.join(com.WEBSERVER_DOCROOT,
                            self.path.lstrip("/"))

        if os.path.islink(dest) or os.path.exists(dest):
            os.remove(dest)
        os.symlink(self.path, dest)


class InstalladmIsoImage(InstalladmImage):
    '''Handles creation of an InstalladmImage from an AI iso'''
    @classmethod
    def unpack(cls, iso, targetdir):
        '''Unpacks an AI ISO into targetdir, and returns an InstalladmImage
        object representing the unpacked image.
        
        '''
        cmd = [com.SETUP_IMAGE_SCRIPT, com.IMAGE_CREATE, iso, targetdir]
        Popen.check_call(cmd, stderr=Popen.STORE)
        iso_img = cls(targetdir)
        iso_img._prep_ai_webserver()
        return iso_img


def is_iso(filepath):
    '''Check if the supplied file spec is an (hsfs) ISO file,
    by using fstyp(1M)
    
    Input:
        filepath - The file at this path will be checked
    
    Return:
        True - file is an ISO
        False - otherwise
    
    '''
    cmd = [_FILE, filepath]
    file_type = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL)
    return ('ISO 9660' in file_type.stdout)
