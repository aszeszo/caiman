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
import logging
import os

import pkg.client.api
import pkg.client.imageconfig
import pkg.client.imagetypes
import pkg.client.progress

import osol_install.auto_install.installadm_common as com

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen, PKG5_API_VERSION


_FILE = '/usr/bin/file'


class ImageError(StandardError):
    '''Base class for InstalladmImage-unique errors'''
    pass


class InstalladmImage(object):
    '''Represents an AI client image on the installadm server'''
    
    NO_ZLIB = _("\nError:\tThe image at %(path)s is not a valid autoinstall "
                "image.\n")

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
            raise ImageError(cw(self.NO_ZLIB % {"path": self.path}))
    
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
        '''Move image area to new location and update webserver symlinks
           Return new image path
        '''
        self._remove_ai_webserver_symlink()
        os.rename(self._path, new_path)
        self._path = new_path
        self._prep_ai_webserver()
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
    
    def _remove_ai_webserver_symlink(self):
        '''Remove the ai webserver symlink for this image'''
        dest = os.path.join(com.WEBSERVER_DOCROOT,
                            self.path.lstrip("/"))
        if os.path.islink(dest) or os.path.exists(dest):
            os.remove(dest)

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


class InstalladmPkgImage(InstalladmImage):
    '''Handles creation of a pkg(5)-based InstalladmImage'''

    _PKG_CLIENT_NAME = "installadm"
    DEFAULT_PKG_NAME = 'install-image/solaris-auto-install'
    ARCH_VARIANT = u'variant.arch'
    SVC_NAME_ATTR = 'com.oracle.install.service-name'
    NO_ZLIB = _("\nError: The pkg image is not an autoinstall image.\n")
    
    def __init__(self, image_path, pkg_image=None):
        super(InstalladmPkgImage, self).__init__(image_path)
        self._pkgimg = pkg_image
    
    @classmethod
    def image_create(cls, fmri_or_p5i, targetdir, arch=None, publisher=None):
        logging.debug("image_create, install from=%s", fmri_or_p5i)
        tracker = pkg.client.progress.CommandLineProgressTracker()
        root_img = pkg.client.api.ImageInterface(
            "/", PKG5_API_VERSION, tracker, None, cls._PKG_CLIENT_NAME)
        
        # In the future, handle:
        #    * SSL repos (keys/certs may need explicit flags from user)
        if publisher is not None:
            prefix = publisher[0]
            order = [prefix]
            repo = pkg.client.publisher.Repository(origins=[publisher[1]])
            pub = pkg.client.publisher.Publisher(prefix, repository=repo)
            publishers = {prefix: pub}
        else:
            publishers = dict()
            order = list()
            for pub in root_img.get_publishers(duplicate=True):
                if pub.disabled:
                    logging.debug("skipping disabled publisher '%s'", 
                                  pub.prefix)
                    continue
                publishers[pub.prefix] = pub
                order.append(pub.prefix)
            
            if not publishers:
                raise ImageError(_("Error: There are no enabled publishers."))

        if arch is None:
            arch = root_img.img.get_variants()[cls.ARCH_VARIANT]
        variants = {cls.ARCH_VARIANT: arch}
        
        props = {pkg.client.imageconfig.FLUSH_CONTENT_CACHE: True}
        pkgimg = pkg.client.api.image_create(
                        cls._PKG_CLIENT_NAME,
                        PKG5_API_VERSION,
                        targetdir,
                        pkg.client.imagetypes.IMG_USER,
                        is_zone=False,
                        progtrack=tracker,
                        props=props,
                        variants=variants
                        )

        # Add publishers to the new image, preserving the original
        # search order
        search_after = None
        for pub_prefix in order:
            add_pub = publishers[pub_prefix]
            pkgimg.add_publisher(add_pub, search_after=search_after)
            logging.debug("adding publisher '%s' after '%s'",
                          add_pub.prefix, search_after)
            search_after = pub_prefix
        
        ai_img = cls(targetdir, pkg_image=pkgimg)
        ai_img._install_package(fmri_or_p5i)
        ai_img.verify()
        ai_img._prep_ai_webserver()
        
        return ai_img
    
    @property
    def pkg_image(self):
        if self._pkgimg is None:
            tracker = pkg.client.progress.CommandLineProgressTracker()
            # installadm is non-interactive, so we don't need to track
            # the "cancel_state" like, for example, packagemanager
            cancel_state_callable = None
            self._pkgimg = pkg.client.api.ImageInterface( 
                                self.path,
                                PKG5_API_VERSION,
                                tracker,
                                cancel_state_callable,
                                self._PKG_CLIENT_NAME)
        return self._pkgimg
    
    def _install_package(self, fmri_or_p5i):
        try:
            p5i_data = self.pkg_image.parse_p5i(location=fmri_or_p5i)
            
            # Returns a list of tuples; should only be one publisher with
            # one package
            if len(p5i_data) != 1:
                raise ImageError("Error: More than one publisher in p5i file")
            
            pub, pkgs = p5i_data[0]
            if len(pkgs) != 1:
                raise ImageError("Error: More than one package in p5i file")
            
            if pub and self.pkg_image.has_publisher(prefix=pub.prefix):
                img_pub = self.pkg_image.get_publisher(prefix=pub.prefix,
                                                       duplicate=True)
                for origin in pub.repository.origins:
                    if not img_pub.repository.has_origin(origin):
                        img_pub.repository.add_origin(origin)
                for mirror in pub.repository.mirrors:
                    if not img_pub.repository.has_mirror(mirror):
                        img_pub.repository.add_mirror(mirror)
                self.pkg_image.update_publisher(img_pub)
            elif pub:
                self.pkg_image.add_publisher(pub)
        except (pkg.client.api_errors.InvalidP5IFile,
                pkg.client.api_errors.RetrievalError):
            pkgs = [fmri_or_p5i]
        
        self.pkg_image.plan_install(pkgs)
        self.pkg_image.prepare()
        self.pkg_image.execute_plan()
        self.pkg_image.reset()
    
    def get_basename(self):
        '''Get pkg service basename '''
        basename = "solarisx"
        try:
            pkg_list = self.pkg_image.get_pkg_list(
                pkg.client.api.ImageInterface.LIST_INSTALLED,
                raise_unmatched=True, return_fmris=True)

            for pfmri, summ, cats, states, attrs in pkg_list:
                manifest = self.pkg_image.get_manifest(pfmri)
                for action in manifest.gen_actions_by_type("set"):
                    for attrval in action.attrlist("name"):
                        if attrval == self.SVC_NAME_ATTR:
                            basename = action.attrs["value"].strip()
                             
        except pkg.client.api_errors.ApiException:
            pass

        logging.debug("get_basename returning %s", basename)
        return basename


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
    if not filepath:
        return False
    cmd = [_FILE, filepath]
    file_type = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.DEVNULL)
    return ('ISO 9660' in file_type.stdout)
