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

#
# Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

"""pre_boot_archive_pkg_image_mod:
Customizations to the package image area before boot archive
construction begins.
"""

import sys
from osol_install.ManifestRead import ManifestRead
from osol_install.distro_const.dc_utils import get_manifest_value,\
    get_manifest_boolean
from osol_install.distro_const.dc_defs import ROOT_PASSWD, ROOT_PASSWD_PLAINTEXT
from osol_install.install_utils import encrypt_password
from pkg.cfgfiles import PasswordFile

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Customizations to the package image area before boot archive construction begins.  This script must be called after the package image area is populated.

Args:
    mfest_socket: Socket needed to get manifest data via ManifestRead object

    pkg_img_path: Package image area

    TMP_DIR: Temporary directory to contain the boot archive file (not used)

    BA_BUILD: Area where boot archive is put together (not used)

    MEDIA_DIR: Area where the media is put (not used)

Note: This script assumes a populated pkg_image area exists at the location
${pkg_img_path}.

"""

if __name__ == "__main__":

    if (len(sys.argv) != 6): # Don't forget sys.argv[0] is the script itself.
        raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
            "    Reader socket, pkg_image area, temp dir,\n" +
            "    boot archive build area, media area.")
    
    # collect input arguments from what this script sees as a commandline.
    mfest_socket = sys.argv[1]  # Manifest reader socket
    pkg_img_path = sys.argv[2]  # package image area mountpoint
    
    # get the manifest reader object from the socket
    manifest_reader_obj = ManifestRead(mfest_socket)
    
    # Get the password for the root user from the manifest
    root_passwd_text = get_manifest_value(manifest_reader_obj, ROOT_PASSWD)
    is_plaintext = get_manifest_boolean(manifest_reader_obj,
                                        ROOT_PASSWD_PLAINTEXT)

    print "root_passwd_text = " + root_passwd_text
    print "is_plaintext = " + str(is_plaintext)
    
    if is_plaintext:
        encrypted_root_passwd = encrypt_password(root_passwd_text,
                                                 alt_root=pkg_img_path)
    else:
        encrypted_root_passwd = root_passwd_text
    
    print "Encrypted root password: " + encrypted_root_passwd

    try:
        pfile = PasswordFile(pkg_img_path)
        root_entry = pfile.getuser("root")
        root_entry["password"] = encrypted_root_passwd
        pfile.setvalue(root_entry)
        pfile.writefile()
    except StandardError:
        print >> sys.stderr, "Failed to modify image with user" \
                             + "specified root password"
        sys.exit(1)

    sys.exit(0)
