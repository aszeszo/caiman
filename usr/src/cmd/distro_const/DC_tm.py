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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
import sys
import os
import logging

from subprocess import *
from osol_install.libtransfer import *
from osol_install.distro_const.dc_utils import *
from osol_install.transfer_mod import *

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/" \
    "DC_defs.py")
execfile('/usr/lib/python2.4/vendor-packages/osol_install/transfer_defs.py')

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_init(pkg_url, pkg_auth, mntpt, tmp_dir):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	dc_log = logging.getLogger(DC_LOGGER_NAME)
	status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_INIT),
	    (TM_IPS_PKG_URL, pkg_url),
	    (TM_IPS_PKG_AUTH, pkg_auth),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)])
	if status:
		return status

	cfg_file = os.path.join(mntpt, "var/pkg/cfg_cache")

	tmp_cfg = os.path.join(tmp_dir, "cfg_cache.mod")
	open(tmp_cfg, "w+")

	cmd = "sed 's/^flush-content-cache-on-success.*/" \
	    "flush-content-cache-on-success = True/' %s >> %s" % \
	    (cfg_file, tmp_cfg)
	try:
		rval = Popen(cmd, shell=True).wait()
		if rval:
			dc_log.error("Failed to modify cfg_cache to turn on " \
			    "IPS download cache purging")
			os.unlink(tmp_cfg)
			return rval
	except OSError:
		dc_log.error("Failed to modify cfg_cache to turn on IPS " \
		    "download cache purging")
		os.unlink(tmp_cfg)
		return rval
		
	cmd = "/usr/gnu/bin/cp %s %s" % (tmp_cfg, cfg_file)
	try:
		rval = Popen(cmd, shell=True).wait()
		if rval:
			dc_log.error("Failed to modified cfg cache to turn on" \
			    "IPS download cache purging")
			os.unlink(tmp_cfg)
			return rval
	except OSError:
		dc_log.error("Failed to modified cfg cache to turn on" \
		    "IPS download cache purging")
		os.unlink(tmp_cfg)
		return rval
		
	return rval		

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_unset_auth(alt_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_UNSET_AUTH),
	    (TM_IPS_ALT_AUTH, alt_auth),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)]) 
	if status == TM_E_SUCCESS:
		return DC_ips_refresh(mntpt)
	else:
		return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_set_auth(alt_url, alt_auth, mntpt, mirr_flag=None, pref_flag=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	dc_log = logging.getLogger(DC_LOGGER_NAME)
	# If both mirr_flag and pref_flag are set that's an error. We
	# can't do both at once.
	if mirr_flag == True and pref_flag == True:
		dc_log.error("Failed to set-authority on the IPS " \
		    "image at " + mntpt + "It is illegal to specify " \
		    "setting a mirror and the preferred authority in the" \
		    " same command")
		return -1 
	tm_argslist = [
	    (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_URL, alt_url),
	    (TM_IPS_ALT_AUTH, alt_auth),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)] 
	if (pref_flag == True):
		tm_argslist.extend([(TM_IPS_PREF_FLAG, TM_IPS_PREFERRED_AUTH)])
	elif (mirr_flag == True):
		tm_argslist.extend([(TM_IPS_MIRROR_FLAG, TM_IPS_MIRROR)])
	status = tm_perform_transfer(tm_argslist)
	if status == TM_E_SUCCESS:
		return DC_ips_refresh(mntpt)
	else:
		return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_refresh(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	return tm_perform_transfer([
	    (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REFRESH),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_contents_verify(file_name, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	return tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REPO_CONTENTS_VERIFY),
	    (TM_IPS_PKGS, file_name),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_pkg_op(file_name, mntpt, ips_pkg_op, generate_ips_index):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	return tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, ips_pkg_op),
	    (TM_IPS_PKGS, file_name),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_IPS_GENERATE_SEARCH_INDEX, generate_ips_index),
	    (TM_PYTHON_LOG_HANDLER, dc_log)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_cleanup_authorities(auth_list, future_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	for auth in auth_list:
		if auth != future_auth:
			status = DC_ips_unset_auth(auth, mntpt)
			if not status == TM_E_SUCCESS:
				dc_log.error("Unable to remove the old "\
				    "authority from the ips image")
				return -1
	return 0

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_purge_hist(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	dc_log = logging.getLogger(DC_LOGGER_NAME)
	return tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_PURGE_HIST),
	    (TM_IPS_INIT_MNTPT, mntpt),
	    (TM_PYTHON_LOG_HANDLER, dc_log)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_populate_pkg_image(mntpt, tmp_dir, manifest_server_obj):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	unset_auth_list = []

	dc_log = logging.getLogger(DC_LOGGER_NAME)
	pkg_url = get_manifest_value(manifest_server_obj,
	    DEFAULT_MAIN_URL)
	pkg_auth = get_manifest_value(manifest_server_obj,
	    DEFAULT_MAIN_AUTHNAME)
	if pkg_auth is None:
		pkg_auth = "opensolaris.org"
	if pkg_url is None:
		pkg_url = "http://pkg.opensolaris.org/release"

	quit_on_pkg_failure = get_manifest_value(manifest_server_obj,
	    STOP_ON_ERR).lower()

	
	# Initialize the IPS area. Use the default authority.
	dc_log.info("Initializing the IPS package image area: " + mntpt)
	dc_log.info("Setting preferred authority: " + pkg_auth)
	dc_log.info("\tOrigin repository: " + pkg_url)
	status = DC_ips_init(pkg_url, pkg_auth, mntpt, tmp_dir)
	if not status == TM_E_SUCCESS:
		dc_log.error("Unable to initialize the IPS image")
		return -1

	# Keep a list of authorities to cleanup at the end.
	unset_auth_list.append(pkg_auth)

	# If the user specified any mirrors for the default authority,
	# set them in the IPS image using the pkg set-authority -m command. 
	mirror_url_list = get_manifest_list(manifest_server_obj,
	   DEFAULT_MIRROR_URL)
	for mirror_url in mirror_url_list:
		if len(mirror_url) == 0:
			continue
		dc_log.info("\tMirror repository: " + mirror_url)
		status = DC_ips_set_auth(mirror_url, pkg_auth, mntpt,
		    mirr_flag=True)
		if not status == TM_E_SUCCESS:
			dc_log.error("Unable to set the IPS image mirror")
			if quit_on_pkg_failure == 'true':
				return -1

	# If an alternate authority (authorities) is specified, set
	# the authority and refresh to make sure it's valid.
	add_repo_url_list = get_manifest_list(manifest_server_obj,
	    ADD_AUTH_MAIN_URL)
	for alt_url in add_repo_url_list:
		# There can be multiple alternate authorities
		# Do a set-authority for each one.
		if len(alt_url) == 0:
			continue
		alt_auth = get_manifest_value(manifest_server_obj,
		    ADD_AUTH_URL_TO_AUTHNAME % alt_url)
		if len(alt_auth) == 0:
			continue
		dc_log.info("Setting alternate authority: " + alt_auth)
		dc_log.info("\tOrigin repository: " + alt_url)
		status = DC_ips_set_auth(alt_url, alt_auth, mntpt)
		if not status == TM_E_SUCCESS:
			dc_log.error("Unable to set "\
			    "alternate "\
			    "authority for IPS image")
			if quit_on_pkg_failure == 'true':
				return -1
			else:
				# If the set-auth fails, sometimes
				# the authority still is listed
				# and we need to unset it.
				DC_ips_unset_auth(alt_auth, mntpt)
				continue

		# Add onto the list of authorities to cleanup at the end
		unset_auth_list.append(alt_auth)

		# Now set the mirrors if any are specified.
		mirror_url_list = get_manifest_list(
		    manifest_server_obj,
		    ADD_AUTH_URL_TO_MIRROR_URL % alt_url) 
		for alt_url_mirror in mirror_url_list:
			dc_log.info("\tMirror repository: " + alt_url_mirror)
			status = DC_ips_set_auth(
			    alt_url_mirror,
			    alt_auth,
			    mntpt, mirr_flag=True)
			if not status == TM_E_SUCCESS: 
				dc_log.error("Unable to set "\
				    "alternate "\
		       		    "authority mirror for "\
				    "IPS image")
				if quit_on_pkg_failure == 'true':
					return -1

	# Read the package list from the manifest and verify
	# the packages are in the repository(s)
	pkgs = get_manifest_list(manifest_server_obj, PKG_NAME_INSTALL)

	# Create a temporary file to contain the list of packages
	# to install.
	pkg_file_name = tmp_dir + "/pkgs%s" % str(os.getpid())
	try:
		pkgfile = open(pkg_file_name, 'w+')
	except IOERROR, e:
		dc_log.error("Unable to create " + pkg_file_name)

	for pkg in pkgs:
		pkgfile.write(pkg + '\n')
	pkgfile.flush()

	dc_log.info("Verifying the contents of the IPS repository")
	status = DC_ips_contents_verify(pkg_file_name, mntpt)
	if status and quit_on_pkg_failure == 'true':
		dc_log.error("Unable to verify the contents of the " \
		    "specified IPS repository")
		pkgfile.close()
		os.unlink(pkg_file_name)
		return -1

	gen_ips_index = get_manifest_value(manifest_server_obj,
	    GENERATE_IPS_INDEX).lower()
	    
	# And finally install the designated packages.
	dc_log.info("Installing the designated packages")
	status = DC_ips_pkg_op(pkg_file_name, mntpt, TM_IPS_RETRIEVE,
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
	pkgs = get_manifest_list(manifest_server_obj, PKG_NAME_UNINSTALL)
	# Create a temporary file to contain the list of packages
	# to uninstall.
	pkg_file_name = tmp_dir + "/rm_pkgs%s" % str(os.getpid())
	try:
		pkgfile = open(pkg_file_name, 'w+')
	except IOERROR, e:
		dc_log.error("Unable to create " + pkg_file_name)

	for pkg in pkgs:
		pkgfile.write(pkg + '\n')
	pkgfile.flush()

	dc_log.info("Uninstalling the designated packages")
	status = DC_ips_pkg_op(pkg_file_name, mntpt, TM_IPS_UNINSTALL,
	    gen_ips_index)

	pkgfile.close()
	os.unlink(pkg_file_name)

	if status:
		dc_log.error("Unable to uninstall all of the specified " \
		    "packages")
		if quit_on_pkg_failure == 'true':
			return -1

	# After all the packages are installed, modify the
        # configuration information in the image so that further
        # packages can be downloaded from the Open Solaris repository

	# set the opensolaris default repository. This is the repository
	# that will be used by the post installed system.
	future_url = get_manifest_value(manifest_server_obj,
	    POST_INSTALL_DEFAULT_URL)
	future_auth = get_manifest_value(manifest_server_obj,
	    POST_INSTALL_DEFAULT_AUTH)
	if future_auth is None:
		future_auth = "opensolaris.org"
	if future_url is None:
		future_url = "http://pkg.opensolaris.org/release"

	dc_log.info("Setting post-install preferred authority: " + future_auth)
	dc_log.info("\tOrigin repository: " + future_url)

	status = DC_ips_set_auth(future_url, future_auth, mntpt,
	    pref_flag=True)
	if not status == TM_E_SUCCESS:
		dc_log.error("Unable to set the future repository") 
		return -1

	# unset any authorities not the auth to use in the future
	if DC_ips_cleanup_authorities(unset_auth_list, future_auth,
	    mntpt):
		return -1

	# If there are any default mirrors specified, set them.
	future_mirror_url_list = get_manifest_list(manifest_server_obj,
	    POST_INSTALL_DEFAULT_MIRROR_URL)
	for future_url in future_mirror_url_list:
		if len(future_url) == 0:
			continue
		dc_log.info("\tMirror repository: " + future_url)
		status = DC_ips_set_auth(future_url, future_auth, mntpt,
		    mirr_flag=True)
		if not status == TM_E_SUCCESS:
			dc_log.error("Unable to set the future IPS image " \
			    "mirror")
			if quit_on_pkg_failure == 'true':
				return -1

	# If there are any additional repositories and mirrors, set them.
	future_add_repo_url_list = get_manifest_list(manifest_server_obj,
	    POST_INSTALL_ADD_AUTH_URL)
	for future_alt_url in future_add_repo_url_list:
		if len(future_alt_url) == 0:
			continue
		future_alt_auth = get_manifest_value(manifest_server_obj,
		    POST_INSTALL_ADD_URL_TO_AUTHNAME % future_alt_url)
		if len(future_alt_auth) == 0:
			continue
		dc_log.info("Setting post-install alternate authority: "
		    + future_alt_auth)
		dc_log.info("\tOrigin repository: " + future_alt_url)
		status = DC_ips_set_auth(future_alt_url,
		    future_alt_auth, mntpt)
		if not status == TM_E_SUCCESS:
			if quit_on_pkg_failure == 'true':
				dc_log.error("Unable to set "\
				    "future alternate"\
				    " authority for "\
				    "IPS image")
				return -1
			else:
				# If the set-auth fails, sometimes
				# the authority still is listed
				# and we need to unset it.
				DC_ips_unset_auth(
				    future_alt_auth, mntpt)
				continue

		# Now set the mirrors if any are specified.
		future_add_mirror_url_list = get_manifest_list(
		    manifest_server_obj,
		    POST_INSTALL_ADD_URL_TO_MIRROR_URL % future_alt_url)
		for future_add_mirror_url in future_add_mirror_url_list:
			if len(future_add_mirror_url) == 0:
				continue
			dc_log.info("\tMirror repository: "
			    + future_add_mirror_url)
			status = DC_ips_set_auth(
			    future_add_mirror_url,
			    future_alt_auth,
			    mntpt, mirr_flag=True)
			if not status == TM_E_SUCCESS:
				dc_log.error("Unable to set "\
				    "future alternate "\
				    "authority mirror for "\
				    "IPS image")
				if quit_on_pkg_failure == 'true':
					return -1
 
	# purge the package history in the IPS image.
	# This saves us some space.
	status = DC_ips_purge_hist(mntpt)
	if status and quit_on_pkg_failure == 'true':
		dc_log.error("Unable to purge the IPS package history")
		return -1
	return 0
