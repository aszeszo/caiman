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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""im_pop.py
DC code to interface with the transfer module.

"""

import sys
import os

from osol_install.libtransfer import TM_E_SUCCESS 
import osol_install.distro_const.dc_utils as dcu 
import osol_install.transfer_mod as tm 
from osol_install.install_utils import dir_size
from osol_install.ManifestRead import ManifestRead

from osol_install.distro_const.dc_defs import DEFAULT_MAIN_URL, \
    DEFAULT_MAIN_AUTHNAME, DEFAULT_MIRROR_URL, \
    ADD_AUTH_MAIN_URL, ADD_AUTH_URL_TO_AUTHNAME, PKG_NAME_INSTALL, \
    GENERATE_IPS_INDEX, PKG_NAME_UNINSTALL, POST_INSTALL_DEFAULT_URL, \
    POST_INSTALL_DEFAULT_AUTH, POST_INSTALL_DEFAULT_MIRROR_URL, \
    POST_INSTALL_ADD_AUTH_URL, POST_INSTALL_ADD_URL_TO_AUTHNAME, \
    POST_INSTALL_ADD_URL_TO_MIRROR_URL, STOP_ON_ERR, \
    ADD_AUTH_URL_TO_MIRROR_URL, IMAGE_INFO_FILE, IMAGE_INFO_IMAGE_SIZE_KEYWORD

from osol_install.transfer_defs import TM_ATTR_MECHANISM, \
    TM_PERFORM_IPS, TM_IPS_ACTION, TM_IPS_INIT, TM_IPS_PKG_URL, \
    TM_IPS_PKG_AUTH, TM_IPS_INIT_MNTPT, TM_IPS_SET_PROP, TM_IPS_PROP_NAME, \
    TM_IPS_PROP_VALUE, TM_IPS_UNSET_AUTH, \
    TM_IPS_ALT_AUTH, TM_IPS_SET_AUTH, TM_IPS_ALT_URL, TM_IPS_PREF_FLAG, \
    TM_IPS_PREFERRED_AUTH, TM_IPS_MIRROR_FLAG, TM_IPS_REFRESH_CATALOG, \
    TM_IPS_PKGS, TM_IPS_GENERATE_SEARCH_INDEX, \
    TM_IPS_UNSET_MIRROR, TM_IPS_PURGE_HIST, TM_IPS_SET_MIRROR, \
    TM_IPS_RETRIEVE, TM_IPS_UNINSTALL, TM_IPS_REPO_CONTENTS_VERIFY

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_image_info(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """
    Create the .image_info file in the pkg image root directory.
    The file should contain the name value pair:
    IMAGE_SIZE=<size of distribution>

    Args:
       mntpt: mount point to create .image_info in.

    Returns:
       None

    Raises:
       None
    """

    # Get the image size.

    try:
        # Need to divide by 1024 because dir_size() return size
        # in bytes, and consumers of .image_info expect the
        # size to be in KB.  Convert it to an int
        image_size = int(round((dir_size(mntpt) / 1024), 0))
    except (TypeError, ValueError):
        print "Error in getting the size of " + mntpt
        return

    if (image_size == 0):
        print "Error in getting the size of " + mntpt
        return

    try:
        image_file = open(mntpt + "/" + IMAGE_INFO_FILE, "w+")
        image_file.write(IMAGE_INFO_IMAGE_SIZE_KEYWORD +
            str(image_size) + "\n")
        image_file.close()
    except IOError:
        print "Error in creating " + mntpt + "/.image_info"
        return

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_init(pkg_url, pkg_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Perform an initialization of the specified IPS area.
    Returns:
            0 Success
            >0 Failure

    """

    status = tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                     (TM_IPS_ACTION, TM_IPS_INIT),
                                     (TM_IPS_PKG_URL, pkg_url),
                                     (TM_IPS_PKG_AUTH, pkg_auth),
                                     (TM_IPS_INIT_MNTPT, mntpt)])
    if status:
        return status

    return (tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                    (TM_IPS_ACTION, TM_IPS_SET_PROP),
                                    (TM_IPS_PROP_NAME,
                                            "flush-content-cache-on-success"),
                                    (TM_IPS_PROP_VALUE, "True"),
                                    (TM_IPS_INIT_MNTPT, mntpt)]))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_unset_auth(alt_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Calls "pkg unset-publisher" to unset the specified publisher/url/mirror
    on the specified mount point.

    Input:
          alt_auth: alternate publisher to unset.
          mntpt: Mount point for the pkg image area.

    Returns:
          Return code from the tm_perform_transfer call.

    """

    return (tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                    (TM_IPS_ACTION, TM_IPS_UNSET_AUTH),
                                    (TM_IPS_ALT_AUTH, alt_auth),
                                    (TM_IPS_INIT_MNTPT, mntpt)]))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_set_auth(alt_url, alt_auth, mntpt, mirr_cmd=None, pref_flag=None,
    refresh_flag=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Calls "pkg set-publisher" to set the specified publisher/url/mirror
    on the specified mount point.

    Input:
            alt_url: URL for the publisher 
            alt_auth: publisher to set
            mntpt: Mount point for the pkg image area.
            mirr_cmd: -m or -M if set. This indicates whether to set or unset
                a mirror.
            pref_flag: indicate whether this is a preferred publisher or not
            refresh_flag: indicate whether the catalog should be refreshed
                while doing the set-publisher call.
    Returns:
            Return code from the TM calls

    """

    # If both mirr_cmd and pref_flag are set that's an error. We
    # can't do both at once.
    if mirr_cmd is not None and pref_flag:
        print "Failed to set-publisher on the IPS " \
                     "image at " + mntpt + "It is illegal to specify " \
                     "setting a mirror and the preferred publisher in the " \
                     " same command"
        return -1
    tm_argslist = [
                  (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                  (TM_IPS_ACTION, TM_IPS_SET_AUTH),
                  (TM_IPS_ALT_URL, alt_url),
                  (TM_IPS_ALT_AUTH, alt_auth),
                  (TM_IPS_INIT_MNTPT, mntpt)]
    if pref_flag:
        tm_argslist.extend([(TM_IPS_PREF_FLAG, TM_IPS_PREFERRED_AUTH)])
    elif mirr_cmd is not None:
        tm_argslist.extend([(TM_IPS_MIRROR_FLAG, mirr_cmd)])
    elif refresh_flag:
        tm_argslist.extend([(TM_IPS_REFRESH_CATALOG, "true")])
    return (tm.tm_perform_transfer(tm_argslist))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_validate_auth(url, auth, mntpt, mirr_cmd=None, pref_flag=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Validate the given publisher, URL or mirror.  This is done on
    an alternate mount point that's passed into this function
    so the original package image area's catalog file doesn't get polluted.

    Input:
            url: URL for the repo to validate
            auth: publisher to validate
            mntpt: Mount point for the pkg image area.
            mirr_cmd: -m if you want to validate a mirror
            pref_flag: indicate whether this is a preferred publisher or not
    Returns:
            Return code from the TM calls

    """

    if (pref_flag):
        return (tm.tm_perform_transfer(
            [(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
            (TM_IPS_ACTION, TM_IPS_INIT),
            (TM_IPS_PKG_URL, url),
            (TM_IPS_PKG_AUTH, auth),
            (TM_IPS_INIT_MNTPT, mntpt)]))
    else:
        return (ips_set_auth(url, auth, mntpt, mirr_cmd,
                                pref_flag=False, refresh_flag=True))

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_contents_verify(file_name, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Verifies that the packages listed in the designated file are in
    the IPS repository associated with the pkg image area.

    Inputs:
            file_name: file containing the list of pkgs to verify
            mntpt: Mount point for the pkg image area.

    Returns:
            Return code from the tm_perform_transfer call.

    """
    
    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
        (TM_IPS_ACTION, TM_IPS_REPO_CONTENTS_VERIFY),
        (TM_IPS_PKGS, file_name),
        (TM_IPS_INIT_MNTPT, mntpt)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_pkg_op(file_name, mntpt, ips_pkg_op, generate_ips_index):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Initiate a IPS pkg install/uninstall of the packages specified in
    the designated file.

    Inputs:
            file_name: file containing the list of pkgs to verify
            mntpt: Mount point for the pkg image area.
            ips_pkg_op: Install or uninstall
            generate_ips_index: true or false indicating whether to
                generate the ips index or not. 

    Returns:
            Return code from the tm_perform_transfer call.

    """

    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                   (TM_IPS_ACTION, ips_pkg_op),
                                   (TM_IPS_PKGS, file_name),
                                   (TM_IPS_INIT_MNTPT, mntpt),
                                   (TM_IPS_GENERATE_SEARCH_INDEX,
                                       generate_ips_index)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_cleanup_authorities(auth_list, future_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Unset all authorities in the list except any that are also the 
    future publisher.

    Inputs:
           auth_list: list of authorities to unset
           future_auth: future publisher. Don't unset this one.
           mntpt: mount point of the pkg image area.

    Returns:
           0 : success
           -1 : failure

    """

    for auth in auth_list:
        if auth != future_auth:
            status = ips_unset_auth(auth, mntpt)
            if status != TM_E_SUCCESS:
                print "Unable to remove the old "\
                             "publisher from the ips image"
                return -1
    return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_cleanup_mirrors(unset_mirror_list, future_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Unset all mirrors in the list except any that are also the 
    future publisher.

    Inputs:
           unset_mirror_list: list of mirrors to remove
           future_auth: future publisher. Don't unset this one.
           mntpt: mount point of the pkg image area.

    Returns:
           0 : success
           -1 : failure

    """

    for url, auth in unset_mirror_list:
        if auth == future_auth:
            status = ips_set_auth(url, auth, mntpt,
                                     mirr_cmd=TM_IPS_UNSET_MIRROR)
            if status != TM_E_SUCCESS:
                print "Unable to remove the old "\
                             "mirror from the ips image"
                return -1
    return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_purge_hist(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Initiate an IPS pkg purge-history

    Inputs:
           mntpt: mount point of the pkg image area

    Returns:
           Return code from the tm_perform_transfer call.

    """

    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                   (TM_IPS_ACTION, TM_IPS_PURGE_HIST),
                                   (TM_IPS_INIT_MNTPT, mntpt)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""Populate the pkg image area indicated by mntpt with the pkgs obtained
from the manifest file pointed to by manifest_server_obj. 

Inputs:
       mntpt: mount point of the pkg image area.
       tmp_dir: temporary directory to use
       manifest_server_obj: Indicates manifest file to use for
           package information.

Returns:
       -1 : failure
        0 : Success

"""

if __name__ == "__main__":

    if (len(sys.argv) != 6): # sys.argv[0] is the script itself.
        raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
                        "    Reader socket, pkg_image area, tmp dir,\n" +
                        "    bootroot build area, media area")

    # Collect input arguments from what
    # this script sees as a commandline.
    MFEST_SOCKET = sys.argv[1]      # Manifest reader socket
    PKG_IMG_MNT_PT = sys.argv[2]    # package image area mountpoint
    TMP_DIR = sys.argv[3]           # temp directory to contain boot archive

    UNSET_AUTH_LIST = []
    UNSET_MIRROR_LIST = []

    MANIFEST_SERVER_OBJ = ManifestRead(MFEST_SOCKET)

    PKG_URL = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                     DEFAULT_MAIN_URL)
    PKG_AUTH = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                      DEFAULT_MAIN_AUTHNAME)

    if PKG_AUTH is None:
        raise Exception, (sys.argv[0] +
                          ": pkg publisher is missing from manifest")
    if PKG_URL is None:
        raise Exception, (sys.argv[0] +
                          ": pkg url is missing from manifest")

    QUIT_ON_PKG_FAILURE = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
        STOP_ON_ERR).lower()


    # Initialize the IPS area. Use the default publisher.
    print "Initializing the IPS package image area: " + PKG_IMG_MNT_PT
    print "Setting preferred publisher: " + PKG_AUTH 
    print "\tOrigin repository: " + PKG_URL 
    STATUS = ips_init(PKG_URL, PKG_AUTH, PKG_IMG_MNT_PT)
    if STATUS != TM_E_SUCCESS:
        raise Exception, (sys.argv[0] +
                          ": Unable to initialize the IPS image")

    # Keep a list of authorities to cleanup at the end.
    UNSET_AUTH_LIST.append(PKG_AUTH)

    # If the user specified any mirrors for the default publisher,
    # set them in the IPS image using the pkg set-publisher -m command.
    MIRROR_URL_LIST = dcu.get_manifest_list(MANIFEST_SERVER_OBJ,
                                            DEFAULT_MIRROR_URL)
    for mirror_url in MIRROR_URL_LIST:
        print "\tMirror repository: " + mirror_url
        STATUS = ips_set_auth(mirror_url, PKG_AUTH, PKG_IMG_MNT_PT,
                              mirr_cmd=TM_IPS_SET_MIRROR, refresh_flag=True)
        if STATUS != TM_E_SUCCESS:
            print "Unable to set the IPS image mirror"
            if QUIT_ON_PKG_FAILURE == 'true':
                raise Exception, (sys.argv[0] +
                                  ": Unable to set the IPS image mirror")

        # Keep a list of mirrors to cleanup at the end.
        UNSET_MIRROR_LIST.append((mirror_url, PKG_AUTH))

    # If an alternate publisher (authorities) is specified, set
    # the publisher and refresh to make sure it's valid.
    ADD_REPO_URL_LIST = dcu.get_manifest_list(MANIFEST_SERVER_OBJ,
                                              ADD_AUTH_MAIN_URL)
    for alt_url in ADD_REPO_URL_LIST:
        # There can be multiple alternate authorities
        # Do a set-publisher for each one.
        alt_auth = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                          ADD_AUTH_URL_TO_AUTHNAME % alt_url)
        if alt_auth is None:
            continue
        print "Setting alternate publisher: " + alt_auth
        print "\tOrigin repository: " + alt_url
        STATUS = ips_set_auth(alt_url, alt_auth, PKG_IMG_MNT_PT,
                              refresh_flag=True)
        if STATUS != TM_E_SUCCESS:
            print "Unable to set alternate publisher for IPS image"
            if QUIT_ON_PKG_FAILURE == 'true':
                raise Exception, (sys.argv[0] +
                                  ": Unable to set alternate publisher " +
                                  "for IPS image")
            else:
                # If the set-auth fails, sometimes
                # the publisher still is listed
                # and we need to unset it.
                ips_unset_auth(alt_auth, PKG_IMG_MNT_PT)
                continue

        # Add onto the list of authorities to cleanup at the end
        UNSET_AUTH_LIST.append(alt_auth)

        # Now set the mirrors if any are specified.
        mirror_url_list = dcu.get_manifest_list(
            MANIFEST_SERVER_OBJ,
            ADD_AUTH_URL_TO_MIRROR_URL % alt_url)
        for alt_url_mirror in mirror_url_list:
            print "\tMirror repository: " + alt_url_mirror
            STATUS = ips_set_auth(alt_url_mirror,
                                  alt_auth,
                                  PKG_IMG_MNT_PT,
                                  mirr_cmd=TM_IPS_SET_MIRROR,
                                  refresh_flag=True)
            if STATUS != TM_E_SUCCESS:
                print "Unable to set alternate publisher mirror for IPS image"
                if QUIT_ON_PKG_FAILURE == 'true':
                    raise Exception, (sys.argv[0] +
                                      ": Unable to set the alternate " +
                                      "publisher mirror for IPS image")

            UNSET_MIRROR_LIST.append((alt_url_mirror, alt_auth))

    # Read the package list from the manifest and verify
    # the packages are in the repository(s)
    PKGS = dcu.get_manifest_list(MANIFEST_SERVER_OBJ, PKG_NAME_INSTALL)

    # Create a temporary file to contain the list of packages
    # to install.
    PKG_FILE_NAME = TMP_DIR + "/pkgs%s" % str(os.getpid())
    try:
        PKGFILE = open(PKG_FILE_NAME, 'w+')
    except IOError:
        print "Unable to create " + PKG_FILE_NAME

    for pkg in PKGS:
        PKGFILE.write(pkg + '\n')
    PKGFILE.close()

    print "Verifying the contents of the IPS repository"
    STATUS = ips_contents_verify(PKG_FILE_NAME, PKG_IMG_MNT_PT)
    if STATUS and QUIT_ON_PKG_FAILURE == 'true':
        os.unlink(PKG_FILE_NAME)
        raise Exception, (sys.argv[0] + ": Unable to verify the " +
                                   "contents of the specified IPS " +
                                   "repository")

    GEN_IPS_INDEX = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                           GENERATE_IPS_INDEX).lower()

    # And finally install the designated packages.
    print "Installing the designated packages"
    STATUS = ips_pkg_op(PKG_FILE_NAME, PKG_IMG_MNT_PT, TM_IPS_RETRIEVE,
                        GEN_IPS_INDEX)

    if STATUS and QUIT_ON_PKG_FAILURE == 'true':
        print "Unable to retrieve all of the specified packages"
        os.unlink(PKG_FILE_NAME)
        raise Exception, (sys.argv[0] + ": Unable to retrieve all " +
                                   "of the specified packages")

    os.unlink(PKG_FILE_NAME)

    #
    # Check to see whether there are any packages that are specified
    # to be removed.  If so, remove them from the package image area.
    #
    PKGS = dcu.get_manifest_list(MANIFEST_SERVER_OBJ, PKG_NAME_UNINSTALL)
    # Create a temporary file to contain the list of packages
    # to uninstall.
    PKG_FILE_NAME = TMP_DIR + "/rm_pkgs%s" % str(os.getpid())
    try:
        PKGFILE = open(PKG_FILE_NAME, 'w+')
    except IOError:
        print "Unable to create " + PKG_FILE_NAME

    for pkg in PKGS:
        PKGFILE.write(pkg + '\n')
    PKGFILE.close()

    print "Uninstalling the designated packages"
    STATUS = ips_pkg_op(PKG_FILE_NAME, PKG_IMG_MNT_PT, TM_IPS_UNINSTALL,
                        GEN_IPS_INDEX)

    os.unlink(PKG_FILE_NAME)

    if STATUS:
        print "Unable to uninstall all of the specified packages"
        if QUIT_ON_PKG_FAILURE == 'true':
            raise Exception, (sys.argv[0] + ": Unable to uninstall " +
                              "all of the specified packages")

    # After all the packages are installed, modify the
    # configuration information in the image so that further
    # packages can be downloaded from the Open Solaris repository

    # set the opensolaris default repository. This is the repository
    # that will be used by the post installed system.
    FUTURE_URL = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                        POST_INSTALL_DEFAULT_URL)
    FUTURE_AUTH = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
                                         POST_INSTALL_DEFAULT_AUTH)

    if FUTURE_URL is None:
        raise Exception, (sys.argv[0] +
                          ": future pkg url is missing from manifest")

    if FUTURE_AUTH is None:
        raise Exception, (sys.argv[0] +
                          ": future pkg publisher is missing from manifest")

    print "Setting post-install preferred publisher: " + FUTURE_AUTH
    print "\tOrigin repository: " + FUTURE_URL

    # This is the mountpoint used for validating whether the post-install
    # authorities, URLs and mirrors are valid or not.  We don't want to
    # refresh the catalog in the package image area, because we don't
    # want that to be polluted.
    VALIDATE_MNTPT = TMP_DIR + "/validate_mntpt"

    STATUS = ips_validate_auth(FUTURE_URL, FUTURE_AUTH,
                               VALIDATE_MNTPT, pref_flag=True)
    if STATUS != TM_E_SUCCESS:
        dcu.cleanup_dir(VALIDATE_MNTPT)
        raise Exception, (sys.argv[0] + ": Post-install publisher or " +
                          "URL is not valid")

    STATUS = ips_set_auth(FUTURE_URL, FUTURE_AUTH, PKG_IMG_MNT_PT,
                          pref_flag=True)
    if STATUS != TM_E_SUCCESS:
        dcu.cleanup_dir(VALIDATE_MNTPT)
        raise Exception, (sys.argv[0] + ": Unable to set the future " +
                          "repository")

    # unset any authorities not the auth to use in the future
    if ips_cleanup_authorities(UNSET_AUTH_LIST, FUTURE_AUTH, PKG_IMG_MNT_PT):
        dcu.cleanup_dir(VALIDATE_MNTPT)
        raise Exception, (sys.argv[0] + ": Unable to cleanup installation " +
                          "authorities")

    # unset any mirrors on the default publisher and any additional
    # authorities.
    if ips_cleanup_mirrors(UNSET_MIRROR_LIST, FUTURE_AUTH, PKG_IMG_MNT_PT):
        dcu.cleanup_dir(VALIDATE_MNTPT)
        raise Exception, (sys.argv[0] + ": Unable to cleanup installation " +
                          "mirrors")

    # If there are any default mirrors specified, set them.
    FUTURE_MIRROR_URL_LIST = dcu.get_manifest_list(MANIFEST_SERVER_OBJ,
        POST_INSTALL_DEFAULT_MIRROR_URL)
    for future_url in FUTURE_MIRROR_URL_LIST:
        print "\tMirror repository: " + future_url
        STATUS = ips_validate_auth(future_url, FUTURE_AUTH,
                                   VALIDATE_MNTPT,
                                   mirr_cmd=TM_IPS_SET_MIRROR)
        if STATUS != TM_E_SUCCESS:
            dcu.cleanup_dir(VALIDATE_MNTPT)
            raise Exception, (sys.argv[0] + ": Post-install mirror " +
                              "repository is not valid")
        STATUS = ips_set_auth(future_url, FUTURE_AUTH, PKG_IMG_MNT_PT,
                              mirr_cmd=TM_IPS_SET_MIRROR)
        if STATUS != TM_E_SUCCESS:
            print "Unable to set the future IPS image mirror"
            if QUIT_ON_PKG_FAILURE == 'true':
                dcu.cleanup_dir(VALIDATE_MNTPT)
                raise Exception, (sys.argv[0] + ": Unable to set the " +
                                  "future IPS image mirror")

    # If there are any additional repositories and mirrors, set them.
    FUTURE_ADD_REPO_URL_LIST = dcu.get_manifest_list(MANIFEST_SERVER_OBJ,
        POST_INSTALL_ADD_AUTH_URL)
    for future_alt_url in FUTURE_ADD_REPO_URL_LIST:
        future_alt_auth = dcu.get_manifest_value(MANIFEST_SERVER_OBJ,
            POST_INSTALL_ADD_URL_TO_AUTHNAME % future_alt_url)
        if future_alt_auth is None:
            continue
        print "Setting post-install alternate publisher: " + future_alt_auth
        print "\tOrigin repository: " + future_alt_url
        STATUS = ips_validate_auth(future_alt_url, future_alt_auth,
                                   VALIDATE_MNTPT)
        if STATUS != TM_E_SUCCESS:
            dcu.cleanup_dir(VALIDATE_MNTPT)
            raise Exception, (sys.argv[0] + ": Post-install alternate " +
                              "publisher or URL is not valid")
        STATUS = ips_set_auth(future_alt_url, future_alt_auth, PKG_IMG_MNT_PT)
        if STATUS != TM_E_SUCCESS:
            if QUIT_ON_PKG_FAILURE == 'true':
                print "Unable to set future alternate publisher for IPS image"
                dcu.cleanup_dir(VALIDATE_MNTPT)
                raise Exception, (sys.argv[0] + ": Unable to set future " +
                                  "alternate publisher for IPS image")
            else:
                # If the set-auth fails, sometimes
                # the publisher still is listed
                # and we need to unset it.
                ips_unset_auth(future_alt_auth, PKG_IMG_MNT_PT)
                continue

        # Now set the mirrors if any are specified.
        future_add_mirror_url_list = dcu.get_manifest_list(
            MANIFEST_SERVER_OBJ,
            POST_INSTALL_ADD_URL_TO_MIRROR_URL % future_alt_url)
        for future_add_mirror_url in future_add_mirror_url_list:
            print "\tMirror repository: " + future_add_mirror_url
            STATUS = ips_validate_auth(future_add_mirror_url,
                                       future_alt_auth, VALIDATE_MNTPT,
                                       mirr_cmd=TM_IPS_SET_MIRROR)
            if STATUS != TM_E_SUCCESS:
                dcu.cleanup_dir(VALIDATE_MNTPT)
                raise Exception, (sys.argv[0] + ": Post-install alternate " +
                                  "mirror is not valid")
            STATUS = ips_set_auth(future_add_mirror_url,
                                  future_alt_auth,
                                  PKG_IMG_MNT_PT,
                                  mirr_cmd=TM_IPS_SET_MIRROR)
            if STATUS != TM_E_SUCCESS:
                print "Unable to set future alternate publisher mirror " + \
                      "for IPS image"
                if QUIT_ON_PKG_FAILURE == 'true':
                    dcu.cleanup_dir(VALIDATE_MNTPT)
                    raise Exception, (sys.argv[0] + ": Unable to set future " +
                                      "alternate publisher mirror for IPS " +
                                      "image")
    dcu.cleanup_dir(VALIDATE_MNTPT)

    # purge the package history in the IPS image.
    # This saves us some space.
    STATUS = ips_purge_hist(PKG_IMG_MNT_PT)
    if STATUS and QUIT_ON_PKG_FAILURE == 'true':
        raise Exception, (sys.argv[0] + ": Unable to purge the IPS package " +
                          "history")

    # Create the .image_info file in the pkg_image directory
    create_image_info(PKG_IMG_MNT_PT)
