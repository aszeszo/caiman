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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
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
import shutil
import stat
import sys
import time

import pkg.client.api
import pkg.client.imageconfig
import pkg.client.imagetypes
import pkg.client.progress
import pkg.version

import osol_install.auto_install.ai_smf_service as aismf
import osol_install.auto_install.installadm_common as com
import osol_install.auto_install.service_config as config

from osol_install.auto_install.installadm_common import _, cli_wrap as cw
from solaris_install import Popen, PKG5_API_VERSION, SetUIDasEUID


BASE_DEF_SVC_NAME = "solarisx"
_FILE = '/usr/bin/file'


class ImageError(StandardError):
    '''Base class for InstalladmImage-unique errors'''
    pass


class InstalladmImage(object):
    '''Represents an AI client image on the installadm server'''

    INVALID_AI_IMAGE = _("\nError:\tThe image at %(path)s is not a valid "
                         "Automated Installer image.")

    def __init__(self, image_path):
        self._path = image_path
        self._arch = None
        self._version = None
    
    def verify(self):
        '''
        Check that the image directory exists, appears to be a valid net
        boot image (has a solaris.zlib file), and is a valid Automated
        Installer image (has an auto_install/ai.dtd file).
        Raises: ImageError if path checks fail
        Pre-conditions: Expects self.path to return a valid image_path
        Returns: None
        '''
        # check image_path exists
        if not os.path.isdir(self.path):
            raise ImageError(cw(_("\nError:\tThe image path (%s) is not "
                               "a directory. Please provide a "
                               "different image path.\n") % self.path))

         # check that the image_path has solaris.zlib file and
         # either auto_install/ai.dtd file exists or the image type is "AI"
        if not (os.path.exists(os.path.join(self.path, "solaris.zlib")) and
                (os.path.exists(os.path.join(self.path,
                               "auto_install/ai.dtd")) or
                (os.path.exists(os.path.join(self.path, ".image_info")) and 
                self.image_type == "AI"))):
            raise ImageError(cw(self.INVALID_AI_IMAGE % {"path": self.path}))

    @property
    def image_type(self):
        '''Returns the AI client image type.
        
        See also the module docstring.
        
        '''
        return self.read_image_info().get("image_type", "")

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
        '''Move image area to new location and update webserver symlink.
           To rename self._path, caller should ensure new_path does not exist.
           Return new image path
        '''
        self._remove_ai_webserver_symlink()
        try:
            os.makedirs(os.path.dirname(new_path))
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
        # Use shutil.move rather than os.rename to allow move across
        # filesystems.
        shutil.move(self._path, new_path)
        self._path = new_path
        self._prep_ai_webserver()
        return self._path
    
    def copy(self, prefix=''):
        '''Copy an image and set up webserver symlinks
        Input: prefix - prefix for temporary location of new image
        Returns: new image object
        '''
        base_dir = os.path.dirname(self.path)
        new_path = "%s/%s-%f" % (base_dir, prefix, time.time())
        logging.debug("Copying image to %s", new_path)
        shutil.copytree(self.path, new_path, symlinks=True)
        new_image = self.__class__(new_path)
        new_image._prep_ai_webserver()
        return new_image

    def delete(self):
        '''Delete image and remove webserver symlink'''
        logging.debug("Deleting image %s", self.path)
        shutil.rmtree(self.path)
        self._remove_ai_webserver_symlink()

    @property
    def path(self):
        '''Returns the image path'''
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

        # remove empty parent directories up until com.WEBSERVER_DOCROOT
        parent = os.path.dirname(dest)
        while parent != com.WEBSERVER_DOCROOT:
            try:
                os.rmdir(parent)
                parent = os.path.dirname(parent)
            except OSError:
                # break if directory is non-empty
                break

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
    INVALID_AI_IMAGE = _(
        "\nError:\tThe pkg image is not an Automated Installer image.\n")
    
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
                raise ImageError(_("\nError:\tThere are no enabled "
                                 "publishers.\n"))

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
    
    def is_pkg_based(self):
        '''Returns True if image is pkg(5) based, False otherwise'''
        try:
            self.pkg_image
        except pkg.client.api_errors.ImageNotFoundException:
            return False
        return True

    def _install_package(self, fmri_or_p5i):
        try:
            p5i_data = self.pkg_image.parse_p5i(location=fmri_or_p5i)
            
            # Returns a list of tuples; should only be one publisher with
            # one package
            if len(p5i_data) != 1:
                raise ImageError(_("\nError:\tMore than one publisher "
                                 "in p5i file.\n"))
            
            pub, pkgs = p5i_data[0]
            if len(pkgs) != 1:
                raise ImageError(_("\nError:\tMore than one package "
                                 "in p5i file.\n"))
            
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

        self.accept_licenses()
        self.pkg_image.prepare()
        self.pkg_image.execute_plan()
        self.pkg_image.reset()

    def accept_licenses(self):
        '''Accept licenses'''
        plan = self.pkg_image.describe()
        for pfmri, src, dest, accepted, displayed in plan.get_licenses():
            self.pkg_image.set_plan_license_status(pfmri, dest.license,
                displayed=True if dest.must_display else None,
                accepted=True if dest.must_accept else None)

    def check_fmri(self, fmri):
        '''Calls pkg.client.api.ImageInterface.parse_fmri_patterns()
           to check if fmri is valid
        Input: fmri to check
        Returns: PkgFmri object
        Raises: ValueError if there is a problem with the fmri

        '''
        for pattern, err, pfmri, matcher in \
            self.pkg_image.parse_fmri_patterns(fmri):
            if err:
                if isinstance(err, pkg.version.VersionError):
                    # For version errors, include the pattern so
                    # that the user understands why it failed.
                    print >> sys.stderr, \
                        cw(_("Illegal FMRI '%(patt)s': %(error)s" %
                           {'patt': pattern, 'error': err}))
                    raise ValueError(err)
                else:
                    # Including the pattern is redundant for other
                    # exceptions.
                    raise ValueError(err)
            return pfmri

    def check_update(self, fmri=None, publisher=None):
        '''Checks to see if any updates are available for this image.
           If so, self.pkg_image will be left "ready" to complete the
           update.

        Input: fmri - pkg to which to potentially update
               publisher - tuple (prefix, origin) to use for update. If
                           that publisher already exists in the image, its
                           origins/mirrors are reset to the passed in origin.
                           Otherwise, the new publisher is added. All other
                           publishers in the image are removed.
        Returns: True if update available; False if not

        '''
        logging.debug('check_update fmri=%s, publisher=%s', fmri, publisher)
        logging.debug("currently installed pfmri is: %s",
                      self.get_installed_pfmri())
        if fmri is not None:
            # validate fmri specified by user
            pkgfmri = self.check_fmri(fmri)
            fmri = [str(pkgfmri)]

        if publisher is not None:
            new_repo = pkg.client.publisher.Repository(origins=[publisher[1]])
            new_repo_uri = new_repo.origins[0].uri
            new_pub = pkg.client.publisher.Publisher(publisher[0],
                                                     repository=new_repo)
            if fmri:
                # ensure that user didn't specify conflicting publisher names
                if pkgfmri.publisher and pkgfmri.publisher != new_pub.prefix:
                    raise ValueError(cw(
                        _('\nError: FMRI publisher, "%(pub1)s", does not '
                          'match specified --publisher, "%(pub2)s".\n' %
                          {'pub1': pkgfmri.publisher,
                           'pub2': new_pub.prefix})))

            # Replace existing publisher(s) with that specified by user
            same_pub = None
            if self.pkg_image.has_publisher(new_pub.prefix):
                # Specified publisher already exists
                same_pub = self.pkg_image.get_publisher(new_pub.prefix,
                                                        duplicate=True)
                logging.debug('basesvc has same pub %s', same_pub.prefix)
                logging.debug('origins are:\n%s', '\n'.join(orig.uri for
                              orig in same_pub.repository.origins))
                logging.debug('replacing origins with new uri, %s',
                              new_repo_uri)
                same_pub.repository.reset_origins()
                same_pub.repository.reset_mirrors()
                same_pub.repository.add_origin(new_repo_uri)
                self.pkg_image.update_publisher(same_pub, search_first=True)
            else:
                # create a new publisher
                logging.debug('adding pub %s, origin %s',
                              new_pub.prefix, new_repo_uri)
                self.pkg_image.add_publisher(new_pub, search_first=True)

            # Remove any other publishers
            for pub in self.pkg_image.get_publishers(duplicate=True)[1:]:
                logging.debug('removing pub %s', pub.prefix)
                self.pkg_image.remove_publisher(prefix=pub.prefix)

        for plan_desc in self.pkg_image.gen_plan_update(pkgs_update=fmri):
            continue
        return (not self.pkg_image.planned_nothingtodo())

    def update(self, fmri=None, publisher=None):
        '''Check to see if update is needed for image and, if so, do the
        update.
        Input: fmri - pkg to which to potentially update
               publisher - tuple (prefix, origin) to use for update. This
                           replaces any publishers in the image.
        Returns: True if update was needed; False if not

        '''
        logging.debug('in update, fmri=%s, publisher=%s', fmri, publisher)
        update_needed = self.check_update(fmri=fmri, publisher=publisher)
        logging.debug('update_needed=%s', update_needed)
        if update_needed:
            self.accept_licenses()
            self.pkg_image.prepare()
            self.pkg_image.execute_plan()
        self.pkg_image.reset()
        return update_needed

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
                        if (attrval == self.SVC_NAME_ATTR and
                            action.attrs.get("variant.arch", self.arch) ==
                            self.arch):
                            basename = action.attrs["value"].strip()
                             
        except pkg.client.api_errors.ApiException:
            pass

        logging.debug("get_basename returning %s", basename)
        return basename

    def get_installed_pfmri(self):
        '''Get installed pkg fmri'''
        try:
            pkg_list = self.pkg_image.get_pkg_list(
                pkg.client.api.ImageInterface.LIST_INSTALLED,
                raise_unmatched=True, return_fmris=True)
            try:
                pfmri = pkg_list.next()[0]
            except StopIteration:
                raise ImageError(_("\nError:\tUnable to obtain pkg name from "
                                   "image.\n"))
        except pkg.client.api_errors.ApiException:
            raise
        return pfmri


class InstalladmIsoImage(InstalladmImage):
    '''Handles creation of an InstalladmImage from an AI iso'''
    @classmethod
    def unpack(cls, iso, targetdir):
        '''Unpacks an AI ISO into targetdir, and returns an InstalladmImage
        object representing the unpacked image.
        
        '''
        cmd = [com.SETUP_IMAGE_SCRIPT, com.IMAGE_CREATE, iso, targetdir]
        with SetUIDasEUID():
            Popen.check_call(cmd, stderr=Popen.STORE)
        iso_img = cls(targetdir)
        iso_img.verify()
        iso_img._prep_ai_webserver()
        return iso_img


def default_path_ok(svc_name, specified_path=None):
    ''' check if default path for service image is available

    Returns: True if default path is ok to use (doesn't exist)
             False otherwise

    '''
    # if path specified by the user, we won't be using the
    # default path, so no need to check
    if specified_path is not None:
        return True

    def_imagepath = os.path.join(aismf.get_imagedir(), svc_name)
    return not os.path.exists(def_imagepath)


def get_default_service_name(image_path=None, image=None, iso=False):
    ''' get default service name
   
    Input:   image_path - imagepath, if specified by user
             image - image object created from image
             iso - boolean, True if service is iso based, False otherwise
    Returns: default name for service.
             For iso-based services, the default name is based
             on the SERVICE_NAME from the .image_info file if available,
             otherwise is BASE_DEF_SVC_NAME_<num>
             For pkg based services, the default name is obtained
             from pkg metadata, otherwise BASE_DEF_SVC_NAME_<num>

    '''
    if image is not None:
        # Try to generate a name based on the metadata. If that
        # name exists, append a number until a unique name is found.
        count = 0
        if iso:
            basename = image.read_image_info().get('service_name')
        else:
            basename = image.get_basename()
        try:
            com.validate_service_name(basename)
            svc_name = basename
        except ValueError:
            basename = BASE_DEF_SVC_NAME
            count = 1
            svc_name = basename + "_" + str(count)
    else:
        count = 1
        basename = BASE_DEF_SVC_NAME
        svc_name = basename + "_" + str(count)
   
    while (config.is_service(svc_name) or
        not default_path_ok(svc_name, image_path)):
        count += 1
        svc_name = basename + "_" + str(count)
    return svc_name


def check_imagepath(imagepath):
    '''
    Check if image path exists.  If it exists, check whether it has
    a valid net image. An empty dir is ok.

    Raises: ValueError if a problem exists with imagepath

    '''
    # imagepath must be a full path
    if not os.path.isabs(imagepath):
        raise ValueError(_("\nA full pathname is required for the "
                           "image path.\n"))

    # imagepath must not exist, or must be empty
    if os.path.exists(imagepath):
        try:
            dirlist = os.listdir(imagepath)
        except OSError as err:
            raise ValueError(err)

        if dirlist:
            if com.AI_NETIMAGE_REQUIRED_FILE in dirlist:
                raise ValueError(_("\nThere is a valid image at (%s)."
                                   "\nPlease delete the image and try "
                                   "again.\n") % imagepath)
            else:
                raise ValueError(_("\nTarget directory is not empty: %s\n") %
                                 imagepath)


def set_permissions(imagepath):
    ''' Set the permissions for the imagepath to 755 (rwxr-xr-x).
        Read, Execute other permissions are necessary for the
        webserver and tftpd to be able to read the imagepath.

        Raises SystemExit if the stat and fstat st_ino differ.
    '''
    image_stat = os.stat(imagepath)
    fd = os.open(imagepath, os.O_RDONLY)
    fd_stat = os.fstat(fd)
    if fd_stat.st_ino == image_stat.st_ino:
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | \
                      stat.S_IRGRP | stat.S_IXGRP | \
                      stat.S_IROTH | stat.S_IXOTH)
    else:
        raise SystemExit(_("The imagepath (%s) changed during "
                           "permission assignment") % imagepath)
    os.close(fd)


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
