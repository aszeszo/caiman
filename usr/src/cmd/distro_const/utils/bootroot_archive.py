#!/usr/bin/python
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

# =============================================================================
# =============================================================================
# bootroot_archive - Release the bootroot mount and archive the bootroot area.
# =============================================================================
# =============================================================================

import os
import sys
import stat
import signal
import platform
from subprocess import Popen, PIPE
from osol_install.ManifestRead import ManifestRead
from osol_install.install_utils import find
from osol_install.install_utils import dir_size
from osol_install.distro_const.DC_ti import ti_create_target
from osol_install.distro_const.DC_ti import ti_release_target
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.DC_defs import BOOT_ROOT_COMPRESSION_LEVEL
from osol_install.distro_const.DC_defs import BOOT_ROOT_COMPRESSION_TYPE
from osol_install.distro_const.DC_defs import BOOT_ROOT_SIZE_PAD
from osol_install.distro_const.DC_defs import BR_FILENAME
from osol_install.distro_const.DC_defs import \
    BOOT_ROOT_CONTENTS_BASE_INCLUDE_NOCOMPRESS

execfile('/usr/lib/python2.4/vendor-packages/osol_install/ti_defs.py')

# A few commands
AWK = "/usr/bin/awk"
CD = "cd"		# Built into the shell
CMD7ZA = "/usr/bin/7za"
CPIO = "/usr/bin/cpio"
FIND = "/usr/bin/find"
MV = "/usr/bin/mv"
TUNEFS = "/usr/sbin/tunefs"
FIOCOMPRESS = "/usr/sbin/fiocompress"
INSTALLBOOT = "/usr/sbin/installboot"
LOFIADM = "/usr/sbin/lofiadm"
SED = "/usr/bin/sed"

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def compress(src, dst):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" fiocompress files in the dst. The files listed in 
	boot/solaris/filelist.ramdisk and files in usr/kernel are recopied
	because we can't have them compressed. 

	Args:
	  src : directory files are copied to dst from.   
	  dst : directory to fiocompress files in.

	Returns: N/A

	Raises: Exception 
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	os.chdir(src)
	compress_flist = find(["."])
	errors = False
	for file in compress_flist:
		# strip off the leading ./ and the trailing \n
		cpio_file = file.lstrip("./").strip()

		if os.access(cpio_file, os.F_OK):
			# copy all files over to preserve hard links
			cmd = "echo " + cpio_file + " | " + CPIO + \
			    " -pdum " + dst + " 2> /dev/null"
			status = os.system(cmd)
			if (status != 0): 
				print >>sys.stderr, (sys.argv[0] + ": cpio " +
				    "error copying file " +  cpio_file +
				    " to bootroot: " + os.strerror(status >> 8))
				errors = True

			# Compress the file if it is a regular file w/ size > 0
			stat_out = os.lstat(cpio_file)
			mode = stat_out.st_mode
			if (stat.S_ISREG(mode) and not (stat_out.st_size == 0)):
				cmd = FIOCOMPRESS + " -mc " + cpio_file + \
				    " " + dst + "/" + cpio_file
				status = os.system(cmd)
				if (status != 0):
					print >>sys.stderr, (sys.argv[0] +
			 		    ": error compressing file " +
					    cpio_file + ": " +
					    os.strerror(status >> 8))
					errors = True
	if (errors):
		raise Exception, (sys.argv[0] + ": Error processing " +
		    "compressed bootroot files")

	# Re-copy a couple of files we don't want compressed.
	# Start with the files/dirs in filelist.ramdisk, and append usr/kernel
	rdfd = open("boot/solaris/filelist.ramdisk", 'r')
	uc_list = []
	for filename in rdfd:
		uc_list.append(filename.strip())
	rdfd.close()
	uc_list.append("usr/kernel")

	# Get expanded uncompressed filelist
	exp_uc_list = find(uc_list)

	# Add (regular) files specified in manifest with fiocompress="false"
	# Verify that they are non-zero-length, regular files first.
	manflist = get_manifest_list(manifest_reader_obj,
	    BOOT_ROOT_CONTENTS_BASE_INCLUDE_NOCOMPRESS)
	if (len(manflist) > 0):
		status = 0
		for nc_file in manflist:
			try:
				stat_out = os.lstat(nc_file)
			except OSError, e:
				print >>sys.stderr, (sys.argv[0] +
				    ": Couldn't stat %s to mark as " +
				    "uncompressed in bootroot: %s") % (
				    nc_file, e.strerror)
				status = 1
				continue
			mode = stat_out.st_mode
			if (stat.S_ISREG(mode) and
			    not (stat_out.st_size == 0)):
				exp_uc_list.append(nc_file)
			else:
				print >>sys.stderr, (sys.argv[0] + ": " +
				    "Couldn't mark " + nc_file +
				    " as uncompressed in bootroot: " +
				    "not a non-zero-sized regular file")
				status = 1
		if (status != 0):
			raise Exception, (sys.argv[0] + ": Error building "
			    "list of uncompressed bootroot files.")

	# List is now built;  now copy the files.
	for file in exp_uc_list:
		cpio_file = file.strip()
		cmd = "echo " + cpio_file + " | cpio -pdum " + dst + \
		    " 2> /dev/null"
		status = os.system(cmd)
		if (status != 0):
			print >>sys.stderr, (sys.argv[0] +
			    ": Error recopying uncompressed file " +
			    cpio_file + ": " + os.strerror(status >> 8))
			# Don't skip out on bad status here.
			# Try whole list before bombing out.

	if (status != 0):
		raise Exception, (sys.argv[0] +
		    ": Error recopying uncompressed files to bootroot")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def release_archive():
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Release archive.

	Args: None

	Returns: Status of ti_release_target()

	Raises: N/A
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	return (ti_release_target({
	    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
	    TI_ATTR_DC_RAMDISK_DEST: BR_LOFI_MNT_PT,
	    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
	    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: BR_ARCHFILE }))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def create_target_intr_handler(signum, frame):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Cleanup when ^C received in the middle of a ti_create_target() call.

	Args:
	  signum: signal number (not used)

	  frame: stack frame number (not used)

	Returns: N/A

	Raises: N/A
	"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	print "^C detected.  Cleaning up..."
	release_archive()
	sys.exit(0)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Archive the bootroot area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_MNT_PT: Package image area mountpoint

  TMP_DIR: Temporary directory to contain the bootroot file

  BR_BUILD: Area where bootroot is put together.

  MEDIA_DIR: Area where the media is put. (Not used)
"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 6): # Don't forget sys.argv[0] is the script itself.
	raise Exception, (sys.argv[0] + ": Requires 5 args:\n" +
	    "    Reader socket, pkg_image area, tmp dir,\n"
	    "    bootroot build area, media area.")

# Collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]	# Manifest reader socket
PKG_IMG_MNT_PT = sys.argv[2]	# package image area mountpoint
TMP_DIR = sys.argv[3]		# temporary directory to contain bootroot file
BR_BUILD = sys.argv[4]		# Bootroot build area

# Destination and name of bootroot file.
is_sparc = (platform.platform().find('sparc') >= 0)

BR_ARCHFILE = PKG_IMG_MNT_PT + BR_FILENAME

# Location of the lofi file mountpoint, known only to this file.
BR_LOFI_MNT_PT = TMP_DIR + "/br_lofimnt"

# get the manifest reader object from the socket
manifest_reader_obj = ManifestRead(MFEST_SOCKET)

# Bootroot compression type and level, and padding amount.
BR_COMPR_LEVEL = get_manifest_value(manifest_reader_obj,
    BOOT_ROOT_COMPRESSION_LEVEL)
if (BR_COMPR_LEVEL == None):
	raise Exception, (sys.argv[0] +
	    ": bootroot compression level missing from manifest")

BR_COMPR_TYPE = get_manifest_value(manifest_reader_obj,
    BOOT_ROOT_COMPRESSION_TYPE)
if (BR_COMPR_TYPE == None):
	raise Exception, (sys.argv[0] +
	    ": bootroot compression type missing from manifest")

padding = -1
br_pad_size_str = get_manifest_value(manifest_reader_obj,
    BOOT_ROOT_SIZE_PAD)
if (br_pad_size_str != None):
	try:
		padding = int(br_pad_size_str)
	except:
		pass
if (padding < 0):
	raise Exception, (sys.argv[0] +
	    ": Bootroot padding size is missing from manifest or invalid.")

# Remove any old stale archive.
gz_arch_file = BR_ARCHFILE + ".gz"
if (os.path.exists(gz_arch_file)):
	os.remove(gz_arch_file)
if (os.path.exists(BR_ARCHFILE)):
	os.remove(BR_ARCHFILE)

print "Sizing bootroot requirements..."
# dir_size() returns size in bytes, need to convert to KB
bootroot_size = (dir_size(BR_BUILD)) / 1024
print "    Raw uncompressed: %d MB." % (bootroot_size / 1024)

# Add 10% to the reported size for overhead, and add padding size,
# if specified.  Padding size need to be converted to KB
# Also need to make sure that the resulting size is an integer after
# all the calculations
bootroot_size = int(round(((bootroot_size * 1.1) + (padding * 1024)), 0))
print "Creating bootroot archive with padded size of %d MB..." % (
    (bootroot_size / 1024))

# Create the file for the bootroot and mount it
signal.signal (signal.SIGINT, create_target_intr_handler)
status = ti_create_target({
    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
    TI_ATTR_DC_RAMDISK_DEST: BR_LOFI_MNT_PT,
    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
    TI_ATTR_DC_RAMDISK_SIZE: bootroot_size,
    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: BR_ARCHFILE })
signal.signal (signal.SIGINT, signal.SIG_DFL)
if (status != 0):
	release_archive()
	raise Exception, (sys.argv[0] +
	    ": Unable to create boot archive: ti_create_target returned: " + 
	    os.strerror(status))

# Allow all space to be used.
# Saving 10% space as typical on UFS buys nothing for a ramdisk.
cmd = TUNEFS + " -m 0 " + BR_LOFI_MNT_PT + " >/dev/null"
copy_status = os.system(cmd)
if (copy_status != 0):	# Print a warning and forge ahead anyway...
	print >>sys.stderr, (
	    "Warning: Could not tunefs the bootroot to use all space:" +
	    os.strerror(copy_status >> 8))

if is_sparc:
	etc_system = open(BR_BUILD + "/etc/system", "a+")
	etc_system.write("set root_is_ramdisk=1\n")
	etc_system.write("set ramdisk_size=" + str(bootroot_size) + "\n")
	etc_system.close()

# Copy files to the archive.
cmd = CD + " " + BR_BUILD + "; "
cmd += FIND + " . | " + CPIO + " -pdum " + BR_LOFI_MNT_PT
copy_status = os.system(cmd)
if (copy_status != 0):
	release_archive()
	raise Exception, (sys.argv[0] + ": Error copying files to bootroot " +
	    "container; find/cpio command returns: " +
	    os.strerror(copy_status >> 8)) 

if is_sparc:
	print "Doing compression..."
	try:
		compress(BR_BUILD, BR_LOFI_MNT_PT)
	except Exception, e:
		release_archive()
		raise
	
	# Install the boot blocks. This only is done on a sparc image.
	cmd = PKG_IMG_MNT_PT + LOFIADM + " " + PKG_IMG_MNT_PT + \
	    BR_FILENAME + " | " + PKG_IMG_MNT_PT + SED + " s/lofi/rlofi/"
	try:
		phys_dev = Popen(cmd, shell=True,
		    stdout=PIPE).communicate()[0]
	except:
		release_archive()
		raise Exception, (sys.argv[0] + ": Error finding the " +
		    "lofi mountpoint for the bootroot")
	
	cmd = PKG_IMG_MNT_PT + INSTALLBOOT + " " + PKG_IMG_MNT_PT + \
	    "/usr/platform/sun4u/lib/fs/ufs/bootblk " + phys_dev 

	status = os.system(cmd)
	if (status != 0):
		release_archive()
		raise Exception, (sys.argv[0] + ": Error installing " +
		    "the boot blocks in the bootroot")

# Unmount the bootroot file and delete the lofi device
status = release_archive()
if (status != 0):
	raise Exception, (sys.argv[0] +
	    ": Unable to release boot archive: ti_release_target returned: " + 
	    os.strerror(status))

# We did the sparc compression above, now do it for x86
if not is_sparc:
	if (BR_COMPR_TYPE == "none"):
		print "Skipping compression..."
	else:
		print "Doing compression..."

		# archive file using 7zip command and gzip compression
		cmd = CMD7ZA + " a "
		if (BR_COMPR_TYPE == "gzip"):
			cmd += "-tgzip -mx=" + BR_COMPR_LEVEL + " "
		else:
			raise Exception, (sys.argv[0] + \
			    ": Unrecognized bootroot " +
			    "compression type: " + BR_COMPR_TYPE)
		cmd += BR_ARCHFILE + ".gz " + BR_ARCHFILE
		status = os.system(cmd)
		if (status != 0):
			raise Exception, (sys.argv[0] +
			    ": Error compressing bootroot: " +
			    "7za command returns: " + os.strerror(status >> 8)) 

		# move compressed file to proper location in pkg image area
		mvcmd = MV + " " + BR_ARCHFILE + ".gz " + BR_ARCHFILE
		status = os.system(mvcmd)
		if (status != 0):
			raise Exception, (sys.argv[0] + ": Error moving " +
			    "bootroot from %s to %s: %s" % 
			    (BR_ARCHFILE + '.gz', BR_ARCHFILE,
			    os.strerror(status >> 8)))

os.chmod(BR_ARCHFILE, 0644)

sys.exit(0)
