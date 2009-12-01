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

"""dc_tm.py
DC code to interface with the transfer module.

"""

import os
import logging

from osol_install.libtransfer import TM_E_SUCCESS 
import osol_install.distro_const.dc_utils as dcu 
import osol_install.transfer_mod as tm 

from osol_install.distro_const.dc_defs import DC_LOGGER_NAME, \
    DEFAULT_MAIN_URL, DEFAULT_MAIN_AUTHNAME, DEFAULT_MIRROR_URL, \
    ADD_AUTH_MAIN_URL, ADD_AUTH_URL_TO_AUTHNAME, PKG_NAME_INSTALL, \
    GENERATE_IPS_INDEX, PKG_NAME_UNINSTALL, POST_INSTALL_DEFAULT_URL, \
    POST_INSTALL_DEFAULT_AUTH, POST_INSTALL_DEFAULT_MIRROR_URL, \
    POST_INSTALL_ADD_AUTH_URL, POST_INSTALL_ADD_URL_TO_AUTHNAME, \
    POST_INSTALL_ADD_URL_TO_MIRROR_URL, STOP_ON_ERR, \
    ADD_AUTH_URL_TO_MIRROR_URL

from osol_install.transfer_defs import TM_ATTR_MECHANISM, \
    TM_PERFORM_IPS, TM_IPS_ACTION, TM_IPS_INIT, TM_IPS_PKG_URL, \
    TM_IPS_PKG_AUTH, TM_IPS_INIT_MNTPT, TM_PYTHON_LOG_HANDLER, \
    TM_IPS_SET_PROP, TM_IPS_PROP_NAME, TM_IPS_PROP_VALUE, TM_IPS_UNSET_AUTH, \
    TM_IPS_ALT_AUTH, TM_IPS_SET_AUTH, TM_IPS_ALT_URL, TM_IPS_PREF_FLAG, \
    TM_IPS_PREFERRED_AUTH, TM_IPS_MIRROR_FLAG, TM_IPS_REFRESH_CATALOG, \
    TM_IPS_PKGS, TM_IPS_GENERATE_SEARCH_INDEX, \
    TM_IPS_UNSET_MIRROR, TM_IPS_PURGE_HIST, TM_IPS_SET_MIRROR, \
    TM_IPS_RETRIEVE, TM_IPS_UNINSTALL, TM_IPS_REPO_CONTENTS_VERIFY

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def ips_init(pkg_url, pkg_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """Perform an initialization of the specified IPS area.
    Returns:
            0 Success
            >0 Failure

    """

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    status = tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                     (TM_IPS_ACTION, TM_IPS_INIT),
                                     (TM_IPS_PKG_URL, pkg_url),
                                     (TM_IPS_PKG_AUTH, pkg_auth),
                                     (TM_IPS_INIT_MNTPT, mntpt),
                                     (TM_PYTHON_LOG_HANDLER, dc_log)])
    if status:
        return status

    return (tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                    (TM_IPS_ACTION, TM_IPS_SET_PROP),
                                    (TM_IPS_PROP_NAME,
                                            "flush-content-cache-on-success"),
                                    (TM_IPS_PROP_VALUE, "True"),
                                    (TM_IPS_INIT_MNTPT, mntpt),
                                    (TM_PYTHON_LOG_HANDLER, dc_log)]))

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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    return (tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                    (TM_IPS_ACTION, TM_IPS_UNSET_AUTH),
                                    (TM_IPS_ALT_AUTH, alt_auth),
                                    (TM_IPS_INIT_MNTPT, mntpt),
                                    (TM_PYTHON_LOG_HANDLER, dc_log)]))

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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    # If both mirr_cmd and pref_flag are set that's an error. We
    # can't do both at once.
    if mirr_cmd is not None and pref_flag:
        dc_log.error("Failed to set-publisher on the IPS " \
                     "image at " + mntpt + "It is illegal to specify " \
                     "setting a mirror and the preferred publisher in the" \
                     " same command")
        return -1
    tm_argslist = [
                  (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                  (TM_IPS_ACTION, TM_IPS_SET_AUTH),
                  (TM_IPS_ALT_URL, alt_url),
                  (TM_IPS_ALT_AUTH, alt_auth),
                  (TM_IPS_INIT_MNTPT, mntpt),
                  (TM_PYTHON_LOG_HANDLER, dc_log)]
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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    if (pref_flag):
        return (tm.tm_perform_transfer(
            [(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
            (TM_IPS_ACTION, TM_IPS_INIT),
            (TM_IPS_PKG_URL, url),
            (TM_IPS_PKG_AUTH, auth),
            (TM_IPS_INIT_MNTPT, mntpt),
            (TM_PYTHON_LOG_HANDLER, dc_log)]))
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
    
    dc_log = logging.getLogger(DC_LOGGER_NAME)
    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
        (TM_IPS_ACTION, TM_IPS_REPO_CONTENTS_VERIFY),
        (TM_IPS_PKGS, file_name),
        (TM_IPS_INIT_MNTPT, mntpt),
        (TM_PYTHON_LOG_HANDLER, dc_log)])

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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                   (TM_IPS_ACTION, ips_pkg_op),
                                   (TM_IPS_PKGS, file_name),
                                   (TM_IPS_INIT_MNTPT, mntpt),
                                   (TM_IPS_GENERATE_SEARCH_INDEX,
                                       generate_ips_index),
                                   (TM_PYTHON_LOG_HANDLER, dc_log)])

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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    for auth in auth_list:
        if auth != future_auth:
            status = ips_unset_auth(auth, mntpt)
            if status != TM_E_SUCCESS:
                dc_log.error("Unable to remove the old "\
                             "publisher from the ips image")
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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    for url, auth in unset_mirror_list:
        if auth == future_auth:
            status = ips_set_auth(url, auth, mntpt,
                                     mirr_cmd=TM_IPS_UNSET_MIRROR)
            if status != TM_E_SUCCESS:
                dc_log.error("Unable to remove the old "\
                             "mirror from the ips image")
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

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    return tm.tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
                                   (TM_IPS_ACTION, TM_IPS_PURGE_HIST),
                                   (TM_IPS_INIT_MNTPT, mntpt),
                                   (TM_PYTHON_LOG_HANDLER, dc_log)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def populate_pkg_image(mntpt, tmp_dir, manifest_server_obj):
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

    unset_auth_list = []
    unset_mirror_list = []

    dc_log = logging.getLogger(DC_LOGGER_NAME)
    pkg_url = dcu.get_manifest_value(manifest_server_obj,
                                     DEFAULT_MAIN_URL)
    pkg_auth = dcu.get_manifest_value(manifest_server_obj,
                                      DEFAULT_MAIN_AUTHNAME)

    if pkg_auth is None:
        return -1
    if pkg_url is None:
        return -1

    quit_on_pkg_failure = dcu.get_manifest_value(manifest_server_obj,
        STOP_ON_ERR).lower()


    # Initialize the IPS area. Use the default publisher.
    dc_log.info("Initializing the IPS package image area: " + mntpt)
    dc_log.info("Setting preferred publisher: " + pkg_auth)
    dc_log.info("\tOrigin repository: " + pkg_url)
    status = ips_init(pkg_url, pkg_auth, mntpt)
    if status != TM_E_SUCCESS:
        dc_log.error("Unable to initialize the IPS image")
        return -1

    # Keep a list of authorities to cleanup at the end.
    unset_auth_list.append(pkg_auth)

    # If the user specified any mirrors for the default publisher,
    # set them in the IPS image using the pkg set-publisher -m command.
    mirror_url_list = dcu.get_manifest_list(manifest_server_obj,
       DEFAULT_MIRROR_URL)
    for mirror_url in mirror_url_list:
        dc_log.info("\tMirror repository: " + mirror_url)
        status = ips_set_auth(mirror_url, pkg_auth, mntpt,
                                 mirr_cmd=TM_IPS_SET_MIRROR, refresh_flag=True)
        if status != TM_E_SUCCESS:
            dc_log.error("Unable to set the IPS image mirror")
            if quit_on_pkg_failure == 'true':
                return -1

        # Keep a list of mirrors to cleanup at the end.
        unset_mirror_list.append((mirror_url, pkg_auth))

    # If an alternate publisher (authorities) is specified, set
    # the publisher and refresh to make sure it's valid.
    add_repo_url_list = dcu.get_manifest_list(manifest_server_obj,
                                              ADD_AUTH_MAIN_URL)
    for alt_url in add_repo_url_list:
        # There can be multiple alternate authorities
        # Do a set-publisher for each one.
        alt_auth = dcu.get_manifest_value(manifest_server_obj,
                                          ADD_AUTH_URL_TO_AUTHNAME % alt_url)
        if alt_auth is None:
            continue
        dc_log.info("Setting alternate publisher: " + alt_auth)
        dc_log.info("\tOrigin repository: " + alt_url)
        status = ips_set_auth(alt_url, alt_auth, mntpt,
                                 refresh_flag=True)
        if status != TM_E_SUCCESS:
            dc_log.error("Unable to set "\
                         "alternate "\
                         "publisher for IPS image")
            if quit_on_pkg_failure == 'true':
                return -1
            else:
                # If the set-auth fails, sometimes
                # the publisher still is listed
                # and we need to unset it.
                ips_unset_auth(alt_auth, mntpt)
                continue

        # Add onto the list of authorities to cleanup at the end
        unset_auth_list.append(alt_auth)

        # Now set the mirrors if any are specified.
        mirror_url_list = dcu.get_manifest_list(
            manifest_server_obj,
            ADD_AUTH_URL_TO_MIRROR_URL % alt_url)
        for alt_url_mirror in mirror_url_list:
            dc_log.info("\tMirror repository: " + alt_url_mirror)
            status = ips_set_auth(alt_url_mirror,
                                  alt_auth,
                                  mntpt,
                                  mirr_cmd=TM_IPS_SET_MIRROR,
                                  refresh_flag=True)
            if status != TM_E_SUCCESS:
                dc_log.error("Unable to set alternate "\
                             "publisher mirror for IPS image")
                if quit_on_pkg_failure == 'true':
                    return -1

            unset_mirror_list.append((alt_url_mirror, alt_auth))

    # Read the package list from the manifest and verify
    # the packages are in the repository(s)
    pkgs = dcu.get_manifest_list(manifest_server_obj, PKG_NAME_INSTALL)

    # Create a temporary file to contain the list of packages
    # to install.
    pkg_file_name = tmp_dir + "/pkgs%s" % str(os.getpid())
    try:
        pkgfile = open(pkg_file_name, 'w+')
    except IOError:
        dc_log.error("Unable to create " + pkg_file_name)

    for pkg in pkgs:
        pkgfile.write(pkg + '\n')
    pkgfile.flush()

    dc_log.info("Verifying the contents of the IPS repository")
    status = ips_contents_verify(pkg_file_name, mntpt)
    if status and quit_on_pkg_failure == 'true':
        dc_log.error("Unable to verify the contents of the " \
                     "specified IPS repository")
        pkgfile.close()
        os.unlink(pkg_file_name)
        return -1

    gen_ips_index = dcu.get_manifest_value(manifest_server_obj,
                                           GENERATE_IPS_INDEX).lower()

    # And finally install the designated packages.
    dc_log.info("Installing the designated packages")
    status = ips_pkg_op(pkg_file_name, mntpt, TM_IPS_RETRIEVE,
                        gen_ips_index)

    if status and quit_on_pkg_failure == 'true':
        dc_log.error("Unable to retrieve all of the specified packages")
        pkgfile.close()
        os.unlink(pkg_file_name)
        return -1

    pkgfile.close()
    os.unlink(pkg_file_name)

    #
    # Check to see whether there are any packages that are specified
    # to be removed.  If so, remove them from the package image area.
    #
    pkgs = dcu.get_manifest_list(manifest_server_obj, PKG_NAME_UNINSTALL)
    # Create a temporary file to contain the list of packages
    # to uninstall.
    pkg_file_name = tmp_dir + "/rm_pkgs%s" % str(os.getpid())
    try:
        pkgfile = open(pkg_file_name, 'w+')
    except IOError:
        dc_log.error("Unable to create " + pkg_file_name)

    for pkg in pkgs:
        pkgfile.write(pkg + '\n')
    pkgfile.flush()

    dc_log.info("Uninstalling the designated packages")
    status = ips_pkg_op(pkg_file_name, mntpt, TM_IPS_UNINSTALL,
                        gen_ips_index)

    pkgfile.close()
    os.unlink(pkg_file_name)

    if status:
        dc_log.error("Unable to uninstall all of the specified packages")
        if quit_on_pkg_failure == 'true':
            return -1

    # After all the packages are installed, modify the
    # configuration information in the image so that further
    # packages can be downloaded from the Open Solaris repository

    # set the opensolaris default repository. This is the repository
    # that will be used by the post installed system.
    future_url = dcu.get_manifest_value(manifest_server_obj,
                                        POST_INSTALL_DEFAULT_URL)
    future_auth = dcu.get_manifest_value(manifest_server_obj,
                                         POST_INSTALL_DEFAULT_AUTH)

    if future_url is None:
        return -1

    if future_auth is None:
        return -1

    dc_log.info("Setting post-install preferred publisher: " + future_auth)
    dc_log.info("\tOrigin repository: " + future_url)

    # This is the mountpoint used for validating whether the post-install
    # authorities, URLs and mirrors are valid or not.  We don't want to
    # refresh the catalog in the package image area, because we don't
    # want that to be polluted.
    validate_mntpt = tmp_dir + "/validate_mntpt"

    status = ips_validate_auth(future_url, future_auth,
                               validate_mntpt, pref_flag=True)
    if status != TM_E_SUCCESS:
        dc_log.error("Post-install publisher or URL is not valid")
        dcu.cleanup_dir(validate_mntpt)
        return -1

    status = ips_set_auth(future_url, future_auth, mntpt, pref_flag=True)
    if status != TM_E_SUCCESS:
        dc_log.error("Unable to set the future repository")
        dcu.cleanup_dir(validate_mntpt)
        return -1

    # unset any authorities not the auth to use in the future
    if ips_cleanup_authorities(unset_auth_list, future_auth, mntpt):
        dcu.cleanup_dir(validate_mntpt)
        return -1

    # unset any mirrors on the default publisher and any additional
    # authorities.
    if ips_cleanup_mirrors(unset_mirror_list, future_auth, mntpt):
        dcu.cleanup_dir(validate_mntpt)
        return -1

    # If there are any default mirrors specified, set them.
    future_mirror_url_list = dcu.get_manifest_list(manifest_server_obj,
        POST_INSTALL_DEFAULT_MIRROR_URL)
    for future_url in future_mirror_url_list:
        dc_log.info("\tMirror repository: " + future_url)
        status = ips_validate_auth(future_url, future_auth,
                                   validate_mntpt,
                                   mirr_cmd=TM_IPS_SET_MIRROR)
        if status != TM_E_SUCCESS:
            dc_log.error("Post-install mirror repository is not valid")
            dcu.cleanup_dir(validate_mntpt)
            return -1
        status = ips_set_auth(future_url, future_auth, mntpt,
                              mirr_cmd=TM_IPS_SET_MIRROR)
        if status != TM_E_SUCCESS:
            dc_log.error("Unable to set the future IPS image mirror")
            if quit_on_pkg_failure == 'true':
                dcu.cleanup_dir(validate_mntpt)
                return -1

    # If there are any additional repositories and mirrors, set them.
    future_add_repo_url_list = dcu.get_manifest_list(manifest_server_obj,
        POST_INSTALL_ADD_AUTH_URL)
    for future_alt_url in future_add_repo_url_list:
        future_alt_auth = dcu.get_manifest_value(manifest_server_obj,
            POST_INSTALL_ADD_URL_TO_AUTHNAME % future_alt_url)
        if future_alt_auth is None:
            continue
        dc_log.info("Setting post-install alternate publisher: "
                    + future_alt_auth)
        dc_log.info("\tOrigin repository: " + future_alt_url)
        status = ips_validate_auth(future_alt_url, future_alt_auth,
                                   validate_mntpt)
        if status != TM_E_SUCCESS:
            dc_log.error("Post-install alternate publisher or " \
                         "URL is not valid")
            dcu.cleanup_dir(validate_mntpt)
            return -1
        status = ips_set_auth(future_alt_url, future_alt_auth, mntpt)
        if status != TM_E_SUCCESS:
            if quit_on_pkg_failure == 'true':
                dc_log.error("Unable to set future alternate"\
                             " publisher for IPS image")
                dcu.cleanup_dir(validate_mntpt)
                return -1
            else:
                # If the set-auth fails, sometimes
                # the publisher still is listed
                # and we need to unset it.
                ips_unset_auth(future_alt_auth, mntpt)
                continue

        # Now set the mirrors if any are specified.
        future_add_mirror_url_list = dcu.get_manifest_list(
            manifest_server_obj,
            POST_INSTALL_ADD_URL_TO_MIRROR_URL % future_alt_url)
        for future_add_mirror_url in future_add_mirror_url_list:
            dc_log.info("\tMirror repository: "
                        + future_add_mirror_url)
            status = ips_validate_auth(future_add_mirror_url,
                                       future_alt_auth, validate_mntpt,
                                       mirr_cmd=TM_IPS_SET_MIRROR)
            if status != TM_E_SUCCESS:
                dc_log.error("Post-install alternate mirror is not valid")
                dcu.cleanup_dir(validate_mntpt)
                return -1
            status = ips_set_auth(future_add_mirror_url,
                                  future_alt_auth,
                                  mntpt,
                                  mirr_cmd=TM_IPS_SET_MIRROR)
            if status != TM_E_SUCCESS:
                dc_log.error("Unable to set future alternate "\
                             "publisher mirror for IPS image")
                if quit_on_pkg_failure == 'true':
                    dcu.cleanup_dir(validate_mntpt)
                    return -1
    dcu.cleanup_dir(validate_mntpt)

    # purge the package history in the IPS image.
    # This saves us some space.
    status = ips_purge_hist(mntpt)
    if status and quit_on_pkg_failure == 'true':
        dc_log.error("Unable to purge the IPS package history")
        return -1
    return 0
