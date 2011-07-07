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

#
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#

"""
media transfer checkpoint. Sub-class of the checkpoint class.
"""

import os
import platform
import logging

from solaris_install import Popen
from solaris_install.data_object.cache import DataObjectCache
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.manifest.parser import ManifestParser
from solaris_install.target.size import Size
from solaris_install.transfer.info import Software, Source, Destination, \
    CPIOSpec, Dir

from urllib2 import Request, urlopen

TRANSFER_MANIFEST_NAME = ".transfer-manifest.xml"

TRANSFER_ROOT = "transfer-root"
TRANSFER_MISC = "transfer-misc"
TRANSFER_MEDIA = "transfer-media"

INSTALL_TARGET_VAR = "{INSTALL_TARGET}"
MEDIA_DIR_VAR = "{MEDIA}"
INSTALL_TARGET = "/a"

NET_SVC = "svc:/system/filesystem/root-assembly:net"
MEDIA_SVC = "svc:/system/filesystem/root-assembly:media"
SVCS_CMD = "/bin/svcs"
SVC_STATUS_DISABLED = "disabled"
SVC_STATUS_ENABLED = "online"

PRTCONF = "/usr/sbin/prtconf"
DHCPINFO = "/sbin/dhcpinfo"

IMAGE_INFO_FILENAME = ".image_info"
IMAGE_SIZE_KEYWORD = "IMAGE_SIZE"
IMAGE_GRUB_TITLE_KEYWORD = "GRUB_TITLE"


class InvalidInstallEnvError(Exception):
    '''Invalid install environment error
    '''
    pass


def is_net_booted(logger):
    '''Determine whether the application is running from a media booted
       environment or a net booted environment.

       The following SMF services are examined:
           svc:/system/filesystem/root-assembly:net
           svc:/system/filesystem/root-assembly:media

       If root-assembly:net is online and root-assembly:media is disabled.
       The image is running from a net booted environment.  This function
       will return True.

       If root-assembly:net is disabled and root-assembly:media is online.
       The image is running from a media booted environment.  This function
       will return False.

       If both root-assembly:net and root-assembly:media are
       online or disabled, that's considered an error condition.

       Exception: InvalidInstallEnvError: if both filesystem/root:media and
                  filesystem/root:net SMF services are online or disabled.
    '''

    cmd = [SVCS_CMD, "-H", "-o", "STATE", NET_SVC]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger=logger)
    net_status = p.stdout.strip()

    logger.debug("%s: %s" % (NET_SVC, net_status))

    cmd = [SVCS_CMD, "-H", "-o", "STATE", MEDIA_SVC]
    p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                         logger=logger)
    media_status = (p.stdout).strip()
    logger.debug("%s: %s" % (MEDIA_SVC, media_status))

    if net_status == SVC_STATUS_ENABLED and \
        media_status == SVC_STATUS_DISABLED:
        return True

    if net_status == SVC_STATUS_DISABLED and \
        media_status == SVC_STATUS_ENABLED:
        return False

    raise InvalidInstallEnvError("%s is %s, %s is %s" % \
        (NET_SVC, net_status, MEDIA_SVC, media_status))


def get_image_grub_title(logger, image_info_file=None):
    '''Specific boot title of the software in the image is stored in the
       .image_info indicated by the keywoard GRUB_TITLE.
       This function retrieves that string value from the .image_info file

       Inputs:
           logger:
               Instance of Logger to use for logging.
           image_info_file:
               An alternative .image_info file path to use. Useful for unit
               testing. The default value of None uses a .image_info file
               value to be determined based on the boot method used to
               boot the media (network or local media boot).

       Returns:
           GRUB_TITLE string value retrieved from .image_info file or None
    '''
    # Depending on how we are booted, get the .image_info file accordingly.
    if image_info_file is None:
        if is_net_booted(logger):
            image_info_file = os.path.join(
                NetPrepareMediaTransfer.MEDIA_SOURCE,
                IMAGE_INFO_FILENAME)
        else:
            image_info_file = os.path.join(
                PrepareMediaTransfer.MEDIA_SOURCE,
                IMAGE_INFO_FILENAME)

    grub_title = None
    with open(image_info_file, 'r') as ih:
        for line in ih:
            (opt, val) = line.split("=")
            if opt == IMAGE_GRUB_TITLE_KEYWORD:
                grub_title = val.strip()
                break

    if grub_title is not None and len(grub_title) > 0:
        logger.debug("Read GRUB_TITLE from %s of value '%s'" \
                     % (image_info_file, grub_title))
        return grub_title
    logger.debug("GRUB_TITLE not specifed in %s" % image_info_file)
    return None


def get_image_size(logger):
    '''Total size of the software in the image is stored in the
       .image_info indicated by the keywoard IMAGE_SIZE.
       This function retrieves that value from the .image_file
       The size recorded in the .image_file is in KB, other functions
       in this file uses the value in MB, so, this function will
       return the size in MB

       Returns:
           size of retrieved from the .image_info file in MB

    '''

    # Depending on how we are booted, get the .image_info file accordingly.
    if is_net_booted(logger):
        image_info_file = os.path.join(NetPrepareMediaTransfer.MEDIA_SOURCE,
                                       IMAGE_INFO_FILENAME)
    else:
        image_info_file = os.path.join(PrepareMediaTransfer.MEDIA_SOURCE,
                                       IMAGE_INFO_FILENAME)

    img_size = 0
    with open(image_info_file, 'r') as ih:
        for line in ih:
            (opt, val) = line.split("=")
            if opt == IMAGE_SIZE_KEYWORD:
                # Remove the '\n' character read from
                # the file, and convert to integer
                img_size = int(val.rstrip('\n'))
                break

    if (img_size == 0):
        # We should have read in a size by now
        logger.error("Unable to read the image size from %s", image_info_file)
        raise RuntimeError

    logger.debug("Read from %s size of %s" % (image_info_file, img_size))
    return (Size(str(img_size) + Size.kb_units).get(Size.mb_units))


def download_files(url, dst, logger):
    '''Download the file specified in the URL to a
       specified local location.
    '''

    logger.debug("Planning to download: " + url)

    request = Request(url)

    url_request = urlopen(request)
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    with open(dst, "w") as dst_file:
        dst_file.write(url_request.read())


def init_prepare_media_transfer(name):
    '''This function instantiates either the PrepareMediaTransfer
       or the NetePrepareMediaTransfer checkpoint depending on how the
       image is booted.

       If the image is booted from the media, the
       PrepareMediaTransfer checkpoint is instantiated.

       If the image is booted from the net, the
       NetPrepareMediaTransfer checkpoint is instantiated.

       Arguments: None

       Returns: An instantiated instance of PrepareMediaTransfer checkpoint or
                NetPrepareMediaTransfer checkpoint

    '''

    logger = logging.getLogger(INSTALL_LOGGER_NAME)

    if is_net_booted(logger):
        logger.debug("Going to init NetPrepareMediaTransfer")
        return NetPrepareMediaTransfer(name)
    else:
        logger.debug("Going to init PrepareMediaTransfer")
        return PrepareMediaTransfer(name)


def setup_doc_content(manifest_name, media_source):
    '''Loads the content of media manifest into a
       SEPARATE DOC instance.  Then, copy the data into the
       DOC that's used by the application, engine and other checkpoints.
    '''

    # create a separate DOC
    another_doc = DataObjectCache()

    # load the transfer manifest into the separate DOC
    manifest_parser = ManifestParser("manifest-parser", manifest_name,
                                     validate_from_docinfo=False)
    manifest_parser.parse(doc=another_doc)

    software_nodes = another_doc.get_descendants(class_type=Software)

    if len(software_nodes) != 3:
        raise RuntimeError("3 software nodes expected.  Only %d found" %
                           len(software_nodes))

    # Modify the install target values and the media mountpoint
    for software in software_nodes:
        # get the destination object
        dst_node = software.get_children(class_type=Destination,
                                         not_found_is_err=True)[0]
        dir_node = dst_node.get_children(class_type=Dir,
                                         not_found_is_err=True)[0]
        path = dir_node.dir_path
        path = path.replace(INSTALL_TARGET_VAR, INSTALL_TARGET)
        dir_node.dir_path = path

        # if this is the media transfer software node, also update the
        # value for source
        if software._name == TRANSFER_MEDIA:
            src_node = software.get_children(class_type=Source,
                                             not_found_is_err=True)[0]
            dir_node = src_node.get_children(class_type=Dir,
                                             not_found_is_err=True)[0]
            path = dir_node.dir_path
            path = path.replace(MEDIA_DIR_VAR, media_source)
            dir_node.dir_path = path

    # copy the Software classes into the common DOC
    doc = InstallEngine.get_instance().data_object_cache
    doc.volatile.insert_children(software_nodes)


class PrepareMediaTransfer(AbstractCheckpoint):
    '''This checkpoint is used by installation environments booted from
       the media.  It prepares the DOC for CPIO based transfer.
       This checkpoint will load the /.cdrom/.transfer-manifest.xml content
       into the transient subtree of the DOC and fill in values of
       various mountpoints in the DOC
    '''

    MEDIA_SOURCE = "/.cdrom"

    def __init__(self, name):
        super(PrepareMediaTransfer, self).__init__(name)
        self.logger.debug("PrepareMediaTransfer init")

    def get_progress_estimate(self):
        return 5

    def execute(self, dry_run=False):

        manifest_name = os.path.join(PrepareMediaTransfer.MEDIA_SOURCE,
                                     TRANSFER_MANIFEST_NAME)

        setup_doc_content(manifest_name, PrepareMediaTransfer.MEDIA_SOURCE)


class NetPrepareMediaTransfer(AbstractCheckpoint):
    ''' The NetPrepareMediaTransfer checkpoint is instantiated by the
        init_prepare_media_transfer() function for installation environments
        booted from the net. This checkpoint will first download the
        transfer-manifest.xml from the server, then, load it into the DOC.
        Based on content of the DOC, the checkpoint will also download any
        other files that needs to be copied into the install target,
        but not yet present in the booted environment. Similar to
        PrepareMediaTransfer, this checkpoint will also download and
        mount the root archives we are not booted with and fill in values
        of mountpoints.
    '''

    # For SPARC, The URL for the AI server is stored in wanboot.conf.
    # This file should have been mounted during boot
    # so, it has to exist
    WANBOOT_CONF = "/etc/netboot/wanboot.conf"

    MEDIA_SOURCE = "/tmp"

    def __init__(self, name):
        super(NetPrepareMediaTransfer, self).__init__(name)
        self.logger.debug("NetPrepareMediaTransfer init")

    def get_progress_estimate(self):
        return 5

    def get_server_url(self):
        '''Get server URL for downloading files '''
        if platform.processor() == "sparc":
            with open(NetPrepareMediaTransfer.WANBOOT_CONF) as wanboot_conf:

                ai_server = None
                ai_image = None

                for line in wanboot_conf:
                    if line.startswith("root_server="):
                        # AI server line have the following format:
                        # root_server=http://<ai_server>:<port>/\
                        #                                 <path_to_wanboot-cgi>
                        # and extract out the http://<ai_server>:<port> portion
                        (not_used, val) = line.split("=")
                        split_val = val.split("/", 3)
                        #remove the last part, since it is not useful
                        split_val.remove(split_val[3])
                        self.logger.debug("URL: " + "/".join(split_val))
                        ai_server = "/".join(split_val)  # re-create the URL
                        self.logger.debug("ai_server: " + ai_server)
                    elif line.startswith("root_file="):
                        # AI image line have the following format
                        # root_file=<ai_image>/boot/platform/sun4v/boot_archive
                        # extract out the <ai_image> part
                        (not_used, val) = line.split("=")
                        split_val = val.rsplit("/", 4)
                        ai_image = split_val[0]
                        self.logger.debug("ai_image: " + ai_image)

                if ai_server is None:
                    raise RuntimeError("Unable to find AI server value "
                                       "from %s",
                                       NetPrepareMediaTransfer.WANBOOT_CONF)

                if ai_image is None:
                    raise RuntimeError("Unable to find AI image value "
                                       "from %s",
                                       NetPrepareMediaTransfer.WANBOOT_CONF)
                return(ai_server + ai_image)
        else:
            cmd = [PRTCONF, "-v", "/devices"]
            p = Popen.check_call(cmd, stdout=Popen.STORE, stderr=Popen.STORE,
                                 logger=self.logger)
            use_next_line = False
            val = None
            for line in p.stdout.splitlines():
                line = line.strip()
                self.logger.debug("line: " + line)
                if use_next_line:
                    val = line
                    break
                if line.startswith("name='install_media'"):
                    use_next_line = True

            if val is None:
                raise RuntimeError("Unable to find install_media line")

            self.logger.debug("found line: " + val)

            # want the value after the equal sign
            (not_used, url) = val.split("=")

            # remove the "'"
            url = url.strip("'")

            if len(url) == 0:
                raise RuntimeError("Unable to find url, found string = " + val)

            # If the $serverIP is specified, need to find the server IP address
            # and fill it in
            if url.find("$serverIP") >= 0:
                cmd = [DHCPINFO, "BootSrvA"]
                p = Popen.check_call(cmd, stdout=Popen.STORE,
                                     stderr=Popen.STORE, logger=self.logger)
                ip_out = p.stdout.strip()
                if len(ip_out) == 0:
                    raise RuntimeError("Unable to find server IP address")

                url = url.replace("$serverIP", ip_out)

            self.logger.debug("Going to return URL: " + url)
            return(url)

    def execute(self, dry_run=False):

        # get AI server URL
        server_url = self.get_server_url()

        self.logger.debug("server URL: " + server_url)

        manifest_name = os.path.join(NetPrepareMediaTransfer.MEDIA_SOURCE,
                                     TRANSFER_MANIFEST_NAME)
        # download the media manifest from the server
        download_files(server_url + "/" + TRANSFER_MANIFEST_NAME,
                       manifest_name, self.logger)

        setup_doc_content(manifest_name, NetPrepareMediaTransfer.MEDIA_SOURCE)

        # Take a look at "transfer-media" node of the DOC, and download
        # all listed files

        doc = InstallEngine.get_instance().data_object_cache

        software_nodes = doc.volatile.get_descendants(class_type=Software)

        for software in software_nodes:
            if software._name == TRANSFER_MEDIA:
                cpio_spec = software.get_children(class_type=CPIOSpec,
                                                  not_found_is_err=True)
                file_list = (cpio_spec[0]).contents
                for file in file_list:
                    # download each file
                    dst_name = \
                        os.path.join(NetPrepareMediaTransfer.MEDIA_SOURCE, \
                        file)
                    self.logger.debug("Downloading " + file)
                    download_files(server_url + "/" + file, dst_name,
                                   self.logger)
