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
# Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
#
"""boot_archive_archive - Release the boot arhive mount and archive the
boot archive area.

"""
import os
import sys
import stat
import signal
from subprocess import Popen, PIPE
from math import floor,log
from osol_install.ManifestRead import ManifestRead
from osol_install.install_utils import find
from osol_install.install_utils import dir_size
from osol_install.libti import ti_create_target
from osol_install.libti import ti_release_target
from osol_install.distro_const.dc_utils import get_manifest_value
from osol_install.distro_const.dc_utils import get_manifest_list
from osol_install.distro_const.dc_defs import BOOT_ARCHIVE_COMPRESSION_LEVEL
from osol_install.distro_const.dc_defs import BOOT_ARCHIVE_COMPRESSION_TYPE
from osol_install.distro_const.dc_defs import BOOT_ARCHIVE_SIZE_PAD
from osol_install.distro_const.dc_defs import BOOT_ARCHIVE_BYTES_PER_INODE
from osol_install.distro_const.dc_defs import BA_FILENAME_SUN4U
from osol_install.distro_const.dc_defs import BA_FILENAME_X86
from osol_install.distro_const.dc_defs import BA_FILENAME_AMD64
from osol_install.distro_const.dc_defs import BA_FILENAME_ALL
from osol_install.distro_const.dc_defs import \
    BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_NOCOMPRESS
from osol_install.ti_defs import TI_ATTR_TARGET_TYPE, \
    TI_TARGET_TYPE_DC_RAMDISK, TI_ATTR_DC_RAMDISK_DEST, \
    TI_ATTR_DC_RAMDISK_FS_TYPE, TI_DC_RAMDISK_FS_TYPE_UFS, \
    TI_ATTR_DC_RAMDISK_SIZE, TI_ATTR_DC_RAMDISK_BOOTARCH_NAME, \
    TI_ATTR_DC_RAMDISK_BYTES_PER_INODE

# A few commands
AWK = "/usr/bin/awk"
CD = "cd"               # Built into the shell
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
    for cfile in compress_flist:
        # strip off the leading ./ and the trailing \n
        cpio_file = cfile.lstrip("./").strip()

        if os.access(cpio_file, os.F_OK):
            # copy all files over to preserve hard links
            cmd = "echo " + cpio_file + " | " + CPIO + \
                " -pdum " + dst + " 2> /dev/null"
            status = os.system(cmd)
            if (status != 0):
                print >> sys.stderr, (sys.argv[0] + ": cpio " +
                    "error copying file " +  cpio_file +
                    " to boot_archive: " + os.strerror(status >> 8))
                errors = True

            # Compress the file if it is a regular file w/ size > 0
            stat_out = os.lstat(cpio_file)
            mode = stat_out.st_mode
            if (stat.S_ISREG(mode) and not (stat_out.st_size == 0)):
                cmd = FIOCOMPRESS + " -mc " + cpio_file + \
                    " " + dst + "/" + cpio_file
                status = os.system(cmd)
                if (status != 0):
                    print >> sys.stderr, (sys.argv[0] +
                        ": error compressing file " +
                        cpio_file + ": " +
                        os.strerror(status >> 8))
                    errors = True
    if (errors):
        raise Exception, (sys.argv[0] + ": Error processing " +
                          "compressed boot_archive files")

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
    manflist = get_manifest_list(MANIFEST_READER_OBJ,
                                 BOOT_ARCHIVE_CONTENTS_BASE_INCLUDE_NOCOMPRESS)
    if manflist:
        status = 0
        for nc_file in manflist:
            try:
                stat_out = os.lstat(nc_file)
            except OSError, err:
                print >> sys.stderr, (sys.argv[0] +
                    ": Couldn't stat %s to mark as " +
                    "uncompressed in boot_archive: %s") % (
                    nc_file, err.strerror)
                status = 1
                continue
            mode = stat_out.st_mode
            if (stat.S_ISREG(mode) and
                not (stat_out.st_size == 0)):
                exp_uc_list.append(nc_file)
            else:
                print >> sys.stderr, (sys.argv[0] + ": " +
                    "Couldn't mark " + nc_file +
                    " as uncompressed in boot_archive: " +
                    "not a non-zero-sized regular file")
                status = 1
        if (status != 0):
            raise Exception, (sys.argv[0] + ": Error building "
                "list of uncompressed boot_archive files.")

    # List is now built;  now copy the files.
    for uc_file in exp_uc_list:
        cpio_file = uc_file.strip()
        cmd = "echo " + cpio_file + " | cpio -pdum " + dst + \
            " 2> /dev/null"
        status = os.system(cmd)
        if (status != 0):
            print >> sys.stderr, (sys.argv[0] +
                ": Error recopying uncompressed file " +
                cpio_file + ": " + os.strerror(status >> 8))
            # Don't skip out on bad status here.
            # Try whole list before bombing out.

    if (status != 0):
        raise Exception, (sys.argv[0] +
            ": Error recopying uncompressed files to boot_archive")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def get_boot_archive_nbpi(size, rootpath):
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    """ Get the number of bytes per inode for boot archive. 

	Args:
	  size : boot archive size in bytes.   
	  rootpath : boot archive directory.

	Returns: number of bytes per inode

	Raises: None

    """
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    nbpi = 0
    fcount = 0
    ioverhead = 0
    
    # Get total number of inodes needed for boot archive
    for root, subdirs, files in os.walk(rootpath):
	for f in (files + subdirs):
	    fcount += 1

    # Add inode overhead for multiple disk systems using 500 disks as a target
    # upper bound. For sparc we need 16 inodes per target device:
    # 8 slices * 2 (block device + character device), for x86 we need
    # 42 inodes: (5 partitions + 16 slices) * 2

    if IS_SPARC:
        ioverhead = 16 * 500
    else:
        ioverhead = 42 * 500

    # Find optimal nbpi
    nbpi = int(round(size / (fcount + ioverhead)))

    # round the nbpi value to the largest power of 2
    # which is less than or equal to calculated value
    if (nbpi != 0):
	nbpi = pow(2,floor(log(nbpi,2)))

    if (nbpi != 0):
	print "Calculated number of bytes per inode: %d." % (nbpi)
    else:
	print "Calculation of nbpi failed, default will be used."

    return nbpi


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
        TI_ATTR_DC_RAMDISK_DEST: BA_LOFI_MNT_PT,
        TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
        TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: BA_ARCHFILE }))


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# pylint: disable-msg=W0613
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
# pylint: enable-msg=W0613

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Main
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""" Archive the boot_archive area.

Args:
  MFEST_SOCKET: Socket needed to get manifest data via ManifestRead object

  PKG_IMG_MNT_PT: Package image area mountpoint

  TMP_DIR: Temporary directory to contain the boot archive file

  BA_MASTER: Area where boot archive is put together.

  MEDIA_DIR: Area where the media is put. (Not used)

  KERNEL_ARCH: Machine type for archive

"""
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

if (len(sys.argv) != 7): # Don't forget sys.argv[0] is the script itself.
    raise Exception, (sys.argv[0] + ": Requires 6 args:\n" +
        "    Reader socket, pkg_image area, tmp dir,\n"
        "    boot archive build area, media area, machine type")

# Collect input arguments from what this script sees as a commandline.
MFEST_SOCKET = sys.argv[1]      # Manifest reader socket
PKG_IMG_MNT_PT = sys.argv[2]    # package image area mountpoint
TMP_DIR = sys.argv[3]           # temp directory to contain boot archive file
BA_MASTER = sys.argv[4]         # Boot archive build area
KERNEL_ARCH = sys.argv[6]       # Machine type for this archive

# Destination and name of boot archive file depends on platform and
# machine type
IS_SPARC = False

if (KERNEL_ARCH == "sparc"):
    BA_ARCHFILE = PKG_IMG_MNT_PT + BA_FILENAME_SUN4U
    BA_BUILD = BA_MASTER
    STRIP_ARCHIVE = False
    IS_SPARC = True
elif (KERNEL_ARCH == "x86"):
    BA_ARCHFILE = PKG_IMG_MNT_PT + BA_FILENAME_X86
    BA_BUILD = TMP_DIR + "/" + KERNEL_ARCH
    STRIP_ARCHIVE = True
elif (KERNEL_ARCH == "amd64"):
    BA_ARCHFILE = PKG_IMG_MNT_PT + BA_FILENAME_AMD64
    BA_BUILD = TMP_DIR + "/" + KERNEL_ARCH
    STRIP_ARCHIVE = True
else:
    BA_ARCHFILE = PKG_IMG_MNT_PT + BA_FILENAME_ALL
    BA_BUILD = BA_MASTER
    STRIP_ARCHIVE = False

# Location of the lofi file mountpoint, known only to this file.
BA_LOFI_MNT_PT = TMP_DIR + "/ba_lofimnt"

# get the manifest reader object from the socket
MANIFEST_READER_OBJ = ManifestRead(MFEST_SOCKET)

# Boot archive compression type and level, and padding amount.
BA_COMPR_LEVEL = get_manifest_value(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_COMPRESSION_LEVEL)
if BA_COMPR_LEVEL is None:
    raise Exception, (sys.argv[0] +
        ": boot archive compression level missing from manifest")

BA_COMPR_TYPE = get_manifest_value(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_COMPRESSION_TYPE)
if BA_COMPR_TYPE is None:
    raise Exception, (sys.argv[0] +
        ": boot archive compression type missing from manifest")

PADDING = -1
BA_PAD_SIZE_STR = get_manifest_value(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_SIZE_PAD)
if BA_PAD_SIZE_STR is not None:
    try:
        PADDING = int(BA_PAD_SIZE_STR)
    except ValueError:
        pass
if (PADDING < 0):
    raise Exception, (sys.argv[0] +
                      ": Boot archive padding size is missing from manifest "
                      "or invalid.")

BA_BYTES_PER_INODE_STR = get_manifest_value(MANIFEST_READER_OBJ,
    BOOT_ARCHIVE_BYTES_PER_INODE)
if BA_BYTES_PER_INODE_STR is not None:
    try:
	BA_BYTES_PER_INODE = int(BA_BYTES_PER_INODE_STR)
    except ValueError:
	pass
    if (BA_BYTES_PER_INODE == 0):
	print "Boot archive nbpi has not been specified in manifest, " \
	    "it will be calculated"

# Remove any old stale archive.
GZ_ARCH_FILE = BA_ARCHFILE + ".gz"
if (os.path.exists(GZ_ARCH_FILE)):
    os.remove(GZ_ARCH_FILE)
if (os.path.exists(BA_ARCHFILE)):
    os.remove(BA_ARCHFILE)
if not (os.path.exists(os.path.dirname(BA_ARCHFILE))):
    os.mkdir(os.path.dirname(BA_ARCHFILE))

# If creating a single-architecture archive, copy full contents to temporary
# area and strip unused architecture
if STRIP_ARCHIVE:
    CMD = "/usr/share/distro_const/boot_archive_strip "
    CMD += BA_MASTER + " " + BA_BUILD + " " + KERNEL_ARCH
    COPY_STATUS = os.system(CMD)
    if (COPY_STATUS != 0):
        raise Exception, (sys.argv[0] + ": Unable to strip boot archive: " +
                          os.strerror(COPY_STATUS >> 8))

print "Sizing boot archive requirements..."
# dir_size() returns size in bytes, need to convert to KB
BOOT_ARCHIVE_SIZE = (dir_size(BA_BUILD)) / 1024
print "    Raw uncompressed: %d MB." % (BOOT_ARCHIVE_SIZE / 1024)

# Add 10% to the reported size for overhead (20% for smaller archives),
# and add padding size, if specified. Padding size needs to be converted to KB.
# Also need to make sure that the resulting size is an integer
if (BOOT_ARCHIVE_SIZE < 150000):
    OVERHEAD = 1.2
else:
    OVERHEAD = 1.1

BOOT_ARCHIVE_SIZE = \
    int(round((BOOT_ARCHIVE_SIZE * OVERHEAD) + (PADDING * 1024)))

if (BA_BYTES_PER_INODE == 0):
    BA_BYTES_PER_INODE = get_boot_archive_nbpi(
	BOOT_ARCHIVE_SIZE * 1024, BA_BUILD) 

print "Creating boot archive with padded size of %d MB..." % (
    (BOOT_ARCHIVE_SIZE / 1024))

# Create the file for the boot archive and mount it
signal.signal (signal.SIGINT, create_target_intr_handler)
STATUS = ti_create_target({
    TI_ATTR_TARGET_TYPE:TI_TARGET_TYPE_DC_RAMDISK,
    TI_ATTR_DC_RAMDISK_DEST: BA_LOFI_MNT_PT,
    TI_ATTR_DC_RAMDISK_FS_TYPE: TI_DC_RAMDISK_FS_TYPE_UFS,
    TI_ATTR_DC_RAMDISK_SIZE: BOOT_ARCHIVE_SIZE,
    TI_ATTR_DC_RAMDISK_BYTES_PER_INODE: BA_BYTES_PER_INODE,
    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME: BA_ARCHFILE })
signal.signal (signal.SIGINT, signal.SIG_DFL)
if (STATUS != 0):
    release_archive()
    raise Exception, (sys.argv[0] +
        ": Unable to create boot archive: ti_create_target returned: " +
        os.strerror(STATUS))

if IS_SPARC:
    ETC_SYSTEM = open(BA_BUILD + "/etc/system", "a+")
    ETC_SYSTEM.write("set root_is_ramdisk=1\n")
    ETC_SYSTEM.write("set ramdisk_size=" + str(BOOT_ARCHIVE_SIZE) + "\n")
    ETC_SYSTEM.close()

# Copy files to the archive.
CMD = CD + " " + BA_BUILD + "; "
CMD += FIND + " . | " + CPIO + " -pdum " + BA_LOFI_MNT_PT
COPY_STATUS = os.system(CMD)
if (COPY_STATUS != 0):
    release_archive()
    raise Exception, (sys.argv[0] + ": Error copying files to boot_archive " +
        "container; find/cpio command returns: " +
        os.strerror(COPY_STATUS >> 8))

# Remove lost+found so it doesn't get carried along to ZFS by an installer
os.rmdir(BA_LOFI_MNT_PT + "/lost+found")

if IS_SPARC:
    print "Doing compression..."
    try:
        compress(BA_BUILD, BA_LOFI_MNT_PT)
    except Exception:
        release_archive()
        raise

    # Install the boot blocks. This only is done on a sparc image.
    CMD = PKG_IMG_MNT_PT + LOFIADM + " " + PKG_IMG_MNT_PT + \
          BA_FILENAME_SUN4U + " | " + PKG_IMG_MNT_PT + SED + " s/lofi/rlofi/"
    try:
        PHYS_DEV = Popen(CMD, shell=True,
                         stdout=PIPE).communicate()[0]
    except OSError:
        release_archive()
        raise Exception, (sys.argv[0] + ": Error finding the " +
            "lofi mountpoint for the boot archive")

    CMD = PKG_IMG_MNT_PT + INSTALLBOOT + " " + PKG_IMG_MNT_PT + \
          "/usr/platform/sun4u/lib/fs/ufs/bootblk " + PHYS_DEV 

    STATUS = os.system(CMD)
    if (STATUS != 0):
        release_archive()
        raise Exception, (sys.argv[0] + ": Error installing " +
            "the boot blocks in the boot archive")

# Unmount the boot archive file and delete the lofi device
STATUS = release_archive()
if (STATUS != 0):
    raise Exception, (sys.argv[0] +
        ": Unable to release boot archive: ti_release_target returned: " +
        os.strerror(STATUS))

# We did the sparc compression above, now do it for x86
if not IS_SPARC:
    if (BA_COMPR_TYPE == "none"):
        print "Skipping compression..."
    else:
        print "Doing compression..."

        # archive file using 7zip command and gzip compression
        CMD = CMD7ZA + " a "
        if (BA_COMPR_TYPE == "gzip"):
            CMD += "-tgzip -mx=" + BA_COMPR_LEVEL + " "
        else:
            raise Exception, (sys.argv[0] + \
                ": Unrecognized boot archive" +
                "compression type: " + BA_COMPR_TYPE)
        CMD += BA_ARCHFILE + ".gz " + BA_ARCHFILE
        STATUS = os.system(CMD)
        if (STATUS != 0):
            raise Exception, (sys.argv[0] +
                ": Error compressing boot archive: " +
                "7za command returns: " + os.strerror(STATUS >> 8))

        # move compressed file to proper location in pkg image area
        MVCMD = MV + " " + BA_ARCHFILE + ".gz " + BA_ARCHFILE
        STATUS = os.system(MVCMD)
        if (STATUS != 0):
            raise Exception, (sys.argv[0] + ": Error moving " +
                "boot archive from %s to %s: %s" %
                (BA_ARCHFILE + '.gz', BA_ARCHFILE,
                os.strerror(STATUS >> 8)))

os.chmod(BA_ARCHFILE, 0644)

sys.exit(0)
