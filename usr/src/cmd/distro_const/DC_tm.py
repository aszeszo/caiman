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

from subprocess import *
from osol_install.libtransfer import *
from osol_install.distro_const.dc_utils import *
from osol_install.transfer_mod import *

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/DC_defs.py")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_init(pkg_url, pkg_auth, mntpt, tmp_dir):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_INIT),
	    (TM_IPS_PKG_URL, pkg_url),
	    (TM_IPS_PKG_AUTH, pkg_auth),
	    (TM_IPS_INIT_MNTPT, mntpt)])
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
			print "Failed to modify cfg_cache to turn on IPS " \
			    "download cache purging"
			os.unlink(tmp_cfg)
			return rval
	except OSError:
		print "Failed to modify cfg_cache to turn on IPS " \
		    "download cache purging"
		os.unlink(tmp_cfg)
		return rval
		
	cmd = "/usr/gnu/bin/cp %s %s" % (tmp_cfg, cfg_file)
	try:
		rval = Popen(cmd, shell=True).wait()
		if rval:
			print "Failed to modified cfg cache to turn on" \
			    "IPS download cache purging"
			os.unlink(tmp_cfg)
			return rval
	except OSError:
		print "Failed to modified cfg cache to turn on" \
		    "IPS download cache purging"
		os.unlink(tmp_cfg)
		return rval
		
	return rval		

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_unset_auth(alt_auth, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	status = tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_UNSET_AUTH),
	    (TM_IPS_ALT_AUTH, alt_auth),
	    (TM_IPS_INIT_MNTPT, mntpt)]) 
	if status == TM_E_SUCCESS:
		return DC_ips_refresh(mntpt)
	else:
		return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_set_auth(alt_url, alt_auth, mntpt, pref_flag=None):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	tm_argslist = [
	    (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_SET_AUTH),
	    (TM_IPS_ALT_URL, alt_url),
	    (TM_IPS_ALT_AUTH, alt_auth),
	    (TM_IPS_INIT_MNTPT, mntpt)] 
	if (pref_flag != None):
		tm_argslist.extend([(TM_IPS_PREF_FLAG, pref_flag)])
	status = tm_perform_transfer(tm_argslist)
	if status == TM_E_SUCCESS:
		return DC_ips_refresh(mntpt)
	else:
		return status

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_refresh(mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	return tm_perform_transfer([
	    (TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REFRESH),
	    (TM_IPS_INIT_MNTPT, mntpt)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_contents_verify(file_name, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	return tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_REPO_CONTENTS_VERIFY),
	    (TM_IPS_PKGS, file_name),
	    (TM_IPS_INIT_MNTPT, mntpt)])

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_ips_retrieve(file_name, mntpt):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	return tm_perform_transfer([(TM_ATTR_MECHANISM, TM_PERFORM_IPS),
	    (TM_IPS_ACTION, TM_IPS_RETRIEVE),
	    (TM_IPS_PKGS, file_name),
	    (TM_IPS_INIT_MNTPT, mntpt)])


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_populate_pkg_image(mntpt, tmp_dir, manifest_server_obj):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	pkg_url = get_manifest_value(manifest_server_obj,
	    DEFAULT_MAIN_URL)
	pkg_auth = get_manifest_value(manifest_server_obj,
	    DEFAULT_MAIN_AUTHNAME)
	if pkg_auth == "":
		pkg_auth = "opensolaris.org"
	if pkg_url == "":
		pkg_url = "http://pkg.opensolaris.org:80"

	quit_on_pkg_failure = get_manifest_value(manifest_server_obj,
	    STOP_ON_ERR).lower()

	
	# Initialize the IPS area. Use the default authority. If that
	# generates an error, then try the mirrors.
	print "Initializing the IPS package image area"
	status = DC_ips_init(pkg_url, pkg_auth, mntpt, tmp_dir)
	if status:
		# The IPS image-create failed, if the user specified any
		# mirrors, try them.
		mirror_url_list = get_manifest_list(manifest_server_obj,
		    DEFAULT_MIRROR_URL)
		for pkg_url in mirror_url_list:
			pkg_auth = get_manifest_value(manifest_server_obj,
			    MIRROR_URL_TO_AUTHNAME % pkg_url)
			status = DC_ips_init(pkg_url, pkg_auth,  mntpt, tmp_dir)
			if status == TM_E_SUCCESS:
				break;	
		if status:
			print "Unable to initialize the IPS area"
			return -1

	# If an alternate authority (authorities) is specified, set
	# the authority and refresh to make sure it's valid. If not
	# valid, the alternate authority mirror(s). 
	add_repo_url_list = get_manifest_list(manifest_server_obj,
	    ADD_AUTH_MAIN_URL)
	for alt_url in add_repo_url_list:
		alt_auth = get_manifest_value(manifest_server_obj,
		    ADD_AUTH_URL_TO_AUTHNAME % alt_url)
		if not len(alt_auth) == 0 and not len(alt_url) == 0:
			status = DC_ips_set_auth(alt_url, alt_auth, mntpt)
			if not status == TM_E_SUCCESS:
				# First unset the authority that failed
				DC_ips_unset_auth(alt_auth, mntpt)

				# Setting of the main alternate authority
				# failed, either through an error setting
				# the alt authority, or the refresh, try
				# the mirrors
				mirror_url_list = get_manifest_list(
				    manifest_server_obj,
				    ADD_AUTH_MIRROR_URL) 
				for alt_url_mirror in mirror_url_list:
					alt_auth_mirror = \
					    get_manifest_value(
					    manifest_server_obj,
					    ADD_AUTH_MIRROR_URL_TO_AUTHNAME \
					    % alt_url)
					status = \
					    DC_ips_set_auth(
					    alt_url_mirror,
					    alt_auth_mirror,
					    mntpt)
					if status == TM_E_SUCCESS:
						break;
					elif quit_on_pkg_failure == \
					    'true':
						print "Unable to set "\
						    "alternate "\
				       		    "authority for "\
						    "IPS image"
						return -1
					else:
						DC_ips_unset_auth(
						    alt_auth_mirror,
						    mntpt)

	pkgs = get_manifest_list(manifest_server_obj, PKG_NAME)
	# Create a temporary file to contain the list of packages
	# to install.
	pkg_file_name = tmp_dir + "/pkgs%s" % str(os.getpid())
	try:
		pkgfile = open(pkg_file_name, 'w+')
	except IOERROR, e:
		print "syserr: Unable to create " + pkg_file_name 

	for pkg in pkgs:
		pkgfile.write(pkg + '\n')
	pkgfile.flush()

	print "Verifing the contents of the IPS repository" 
	status = DC_ips_contents_verify(pkg_file_name, mntpt)
	if status and quit_on_pkg_failure == 'true':
		print "Unable to verify the contents of the " \
		    "specified IPS repository"
		pkgfile.close()
		os.unlink(pkg_file_name)
		return -1
	    
	# And finally install the designated packages.
	print "Installing the designated packages"
	status = DC_ips_retrieve(pkg_file_name, mntpt)
	if status and quit_on_pkg_failure == 'true':
		print "Unable to retrieve all of the specified packages"
		pkgfile.close()
		os.unlink(pkg_file_name)
		return -1

	pkgfile.close()
	os.unlink(pkg_file_name)

	# After all the packages are installed, modify the
        # configuration information in the image so that further
        # packages can be downloaded from the Open Solaris repository

	# set the opensolaris repository
        status = DC_ips_set_auth(FUTURE_URL, FUTURE_AUTH, mntpt,
	    pref_flag=TM_IPS_PREFERRED_AUTH)
	if not status == TM_E_SUCCESS:
		print "Unable to set the future repository" 
		return -1

	# unset any authorities not the auth to use in the future 
	if pkg_auth != FUTURE_AUTH:
		status = DC_ips_unset_auth(pkg_auth, mntpt)
		if not status == TM_E_SUCCESS:
			print "Unable to remove the old authority from the ips image"
			return -1

	return 0
	
execfile('/usr/lib/python2.4/vendor-packages/osol_install/transfer_defs.py')
