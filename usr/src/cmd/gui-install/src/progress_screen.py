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
# Copyright (c) 2011, 2012, Oracle and/or its affiliates. All rights reserved.
#

'''
Progress Screen for GUI Install app
'''

from distutils.text_file import TextFile
import logging
import math
import os
import random
import socket
import struct
import sys
import thread

import glib
import g11nsvc
import gtk

import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc
from solaris_install import Popen
from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen
from solaris_install.gui_install.gui_install_common import modal_dialog, \
    CLEANUP_CPIO_INSTALL, COLOR_WHITE, DEFAULT_LOG_LOCATION, FIREFOX, \
    GLADE_DIR, GLADE_ERROR_MSG, LOG_LOCATION_FINAL, TRANSFER_PREP, \
    VAR_SHARED_DATASET
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.logger import INSTALL_LOGGER_NAME, \
    ProgressHandler
from solaris_install.sysconfig.profile import from_engine
from solaris_install.sysconfig.profile.network_info import NetworkInfo
from solaris_install.sysconfig.profile.system_info import SystemInfo
from solaris_install.sysconfig.profile.user_info import UserInfo, \
    UserInfoContainer
from solaris_install.target import Target
from solaris_install.target.controller import DEFAULT_ZPOOL_NAME
from solaris_install.target.logical import BE
from solaris_install.transfer.info import Software, IPSSpec

# location of image files
IMAGE_DIR = GLADE_DIR + '/installmessages/'

# Image callback timeout, every 30 seconds
IMAGES_TIMEOUT = 30000

# Installation callback timeout
INSTALLATION_TIMEOUT = 200

# showurl callback timeout
SHOWURL_TIMEOUT = 250

# finish callback timeout
FINISH_TIMEOUT = 250


class ProgressScreen(BaseScreen):
    '''Progress Screen Class'''
    URLMAPPING = 'imageurl.txt'

    def __init__(self, builder, finishapp):
        super(ProgressScreen, self).__init__(builder)
        self.name = "Progress Screen"
        self.finishapp = finishapp
        self.timer = None
        self.finish_timer = None
        self.success = False
        self.fraction = 0.0
        self.message = None
        self.update_screen = False
        self.show_url = None
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

        self.installationeventbox = self.builder.get_object(
            "installationeventbox")
        self.installationimage = self.builder.get_object("installationimage")
        self.installationprogressbar = self.builder.get_object(
            "installationprogressbar")
        self.installationinfolabel = self.builder.get_object(
            "installationinfolabel")
        self.installbutton = self.builder.get_object("installbutton")
        self.quitbutton = self.builder.get_object("quitbutton")

        if None in [self.installationeventbox, self.installationimage,
            self.installationprogressbar, self.installationinfolabel,
            self.installbutton, self.quitbutton]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

        # get the current locale
        locale_ops = g11nsvc.G11NSvcLocaleOperations()
        locale = locale_ops.getlocale()

        # check for a localized image directory
        path = os.path.join(IMAGE_DIR, locale)
        if not os.path.exists(path):
            path = os.path.join(IMAGE_DIR, 'C')
            if not os.path.exists(path):
                self.logger.debug("Unable to determine image directory")

        try:
            self.urlimage_dictionary = self.get_urlimage_dictionary(path)
        except IOError:
            self.urlimage_dictionary = dict()
        self.image_index = 0
        self.image_pause = False

        self.installationprogressbar.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self.installationeventbox.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)

        self.install_complete = False

    def enter(self):
        '''enter method for the progress screen'''
        toplevel = self.set_main_window_content("installationwindowtable")

        # Screen-specific configuration
        self.activate_stage_label("installationstagelabel")

        self.set_titles(_("Installing"), _(" "), None)

        self.set_back_next(back_sensitive=False, next_sensitive=False)

        self.installbutton.set_sensitive(False)
        self.quitbutton.set_sensitive(False)
        self.installationeventbox.connect('button-press-event',
            self.installation_file_button_press, None)

        if len(self.urlimage_dictionary):
            # initialize the image index and display the first image
            image_keys = sorted(self.urlimage_dictionary.keys())
            self.image_index = 0
            self.installationimage.set_from_file(image_keys[self.image_index])

            # setup the timer callback for INSTALLATION_TIMEOUT
            self.timer = glib.timeout_add(IMAGES_TIMEOUT, self.update_image)

        self.set_progress_fraction(0.0)

        toplevel.show_all()

        # start the installation after a few seconds to allow
        # the screen to refresh
        timer = glib.timeout_add(INSTALLATION_TIMEOUT,
                                 self.perform_installation)

        self.finish_timer = glib.timeout_add(FINISH_TIMEOUT,
                                             self.check_finished)

    def get_urlimage_dictionary(self, path):
        '''method to retrieve the image/url mappings from the
           imageurl.txt file
        '''
        urlimage_dict = dict()
        image_fh = TextFile(filename=os.path.join(path, self.URLMAPPING),
                            lstrip_ws=True)
        for line in image_fh.readlines():
            if '=' in line:
                filename, sep, url = line.partition('=')
                filename = os.path.join(path, filename)
                urlimage_dict[filename] = url

        return urlimage_dict

    def update_image(self):
        '''Timer callback that updated the image'''
        if not self.image_pause:
            self._show_next_image()

        return True

    def set_progress_fraction(self, fraction):
        '''updates the progressbar with the current percent complete'''
        if fraction >= 0.0 and fraction <= 1.0:
            self.installationprogressbar.set_fraction(fraction)

    def start_server(self, host, port):
        '''method to start the message communication.'''
        def parse_msg(the_socket):
            '''Parse the messages sent by the client.'''
            total_len = 0
            total_data = list()
            size = sys.maxint
            size_data = sock_data = ''
            recv_size = 8192
            percent = None
            msg = None

            while total_len < size:
                sock_data = the_socket.recv(recv_size)
                if not total_data:
                    if len(sock_data) > 4:
                        size_data += sock_data
                        size = struct.unpack('@i', size_data[:4])[0]
                        recv_size = size
                        if recv_size > 524288:
                            recv_size = 524288
                        total_data.append(size_data[4:])
                    else:
                        size_data += sock_data
                else:
                    total_data.append(sock_data)
                total_len = sum([len(i) for i in total_data])
                message = ''.join(total_data)
                if message:
                    percent, msg = message.split(' ', 1)
                break
            return percent, msg

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.listen(5)

        engine_sock, address = sock.accept()
        while True:
            while not self.install_complete:
                percentage, msg = parse_msg(engine_sock)

                if percentage is not None:
                    log_msg = "Progress update received: " \
                        "Installation is %f percent complete [%s]" % \
                        (float(percentage), msg)
                    self.logger.debug(log_msg)

                    fraction = math.floor(float(percentage)) / 100.0

                    if fraction >= 1.0:
                        self.update_screen = True
                        self.fraction = 1.0
                        self.set_progress_fraction(1.0)
                        break
                    self.update_screen = True
                    self.fraction = fraction
                    self.message = msg

        engine_sock.close()

    def setup_progress_handling(self):
        '''method to setup the progress handler.'''
        # NB - this doesn't give us anything very helpful, currently.
        # But we just have to wait for the checkpoints to provide
        # some useful progress reporting

        host = 'localhost'
        port = random.randint(10000, 30000)

        proghdlr = ProgressHandler(host=host, port=port)
        self.logger.addHandler(proghdlr)
        thread.start_new_thread(self.start_server, (host, port))

    def perform_installation(self):
        '''method which actually does the installation.'''
        # establish the timer that will update the screen messaging
        timer = glib.timeout_add(INSTALLATION_TIMEOUT,
                                 self._update_screen_message)

        eng = InstallEngine.get_instance()
        errsvc.clear_error_list()
        eng.execute_checkpoints(start_from=TRANSFER_PREP,
                               pause_before=VAR_SHARED_DATASET)

        # Setup progress handling
        self.setup_progress_handling()

        self.logger.info("Setting up software to install/uninstall")

        # Add the list of packages to be removed after the install to the DOC
        pkg_remove_list = ['pkg:/system/install/media/internal',
                           'pkg:/system/install/gui-install']
        pkg_spec = IPSSpec(action=IPSSpec.UNINSTALL, contents=pkg_remove_list)
        pkg_rm_node = Software(CLEANUP_CPIO_INSTALL, type="IPS")
        pkg_rm_node.insert_children(pkg_spec)

        eng.doc.volatile.insert_children(pkg_rm_node)

        # Setup system configuration data
        profile = from_engine()
        gui_profile = eng.data_object_cache.volatile.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        if gui_profile is None:
            SystemExit('Internal Error, GUI Install DOC not found')

        profile.system = SystemInfo(hostname=gui_profile.hostname,
                                    tz_region=gui_profile.continent,
                                    tz_country=gui_profile.country,
                                    tz_timezone=gui_profile.timezone,
                                    locale=gui_profile.default_locale)
        profile.nic = NetworkInfo(net_type="automatic")

        # Setup user configuration data
        root = UserInfo(login_name="root",
                        is_role=True,
                        password=gui_profile.userpassword,
                        expire="0")
        user = UserInfo(gid=10, shell="/usr/bin/bash",
                        login_name=gui_profile.loginname,
                        real_name=gui_profile.username,
                        password=gui_profile.userpassword,
                        roles="root",
                        profiles="System Administrator",
                        sudoers="ALL=(ALL) ALL")
        profile.users = UserInfoContainer(user, root)
        self.logger.debug('from_engine returned %s', profile)

        gui_profile.set_log(DEFAULT_LOG_LOCATION, LOG_LOCATION_FINAL)

        # Run the registered checkpoints
        errsvc.clear_error_list()
        eng.execute_checkpoints(callback=self.install_callback)
        self.logger.info("Install Started")

        return False

    def install_callback(self, status, failed_cps):
        '''This is the callback registered with the InstallEngine to
           be called when the checkpoints complete execution.'''

        self.logger.debug("Callback for installation called")
        # Ensure that execution succeeded
        if status != InstallEngine.EXEC_SUCCESS:
            self.logger.error("ERROR: Execution FAILED")

            for failed_cp in failed_cps:
                err_data_list = errsvc.get_errors_by_mod_id(failed_cp)
                if len(err_data_list):
                    err_data = err_data_list[0]
                    err = err_data.error_data[liberrsvc.ES_DATA_EXCEPTION]
                else:
                    err = "Unknown error"

                self.logger.error("Checkpoint [%s] logged error: [%s]" % \
                    (failed_cp, err))
            self.success = False
            self.install_complete = True
        else:
            eng = InstallEngine.get_instance()
            doc = eng.data_object_cache
            profile = doc.volatile.get_first_child(name="GUI Install",
                class_type=InstallProfile)
            if profile is None:
                raise RuntimeError("INTERNAL ERROR: Unable to retrieve "
                    "InstallProfile from DataObjectCache")

            # If swap was created, add appropriate entry to <target>/etc/vfstab
            desired_root = doc.persistent.get_descendants(name=Target.DESIRED,
                class_type=Target, max_depth=2, not_found_is_err=True)[0]
            new_bes = desired_root.get_descendants(class_type=BE)
            if not new_bes:
                self.logger.debug("No new BE created!")
            else:
                new_be = new_bes[0]
                install_mountpoint = new_be.mountpoint
                self.logger.debug("New BE: %s", new_be)
                self.logger.debug("install mountpoint: %s", install_mountpoint)
                self.logger.debug("Setting up /etc/vfstab for swap")
                profile.target_controller.setup_vfstab_for_swap(
                    DEFAULT_ZPOOL_NAME, install_mountpoint)

            self.logger.info("INSTALL FINISHED SUCCESSFULLY!")
            self.set_progress_fraction(1.0)
            self.success = True
            self.install_complete = True

    def check_finished(self):
        '''method to check if the installation has completed'''
        if self.install_complete:
            self.finishapp(success=self.success)
            return False

        return True

    def go_back(self):
        '''method from the super that deals with
           the back button being pressed'''
        # changing screens stop the timer
        glib.source_remove(self.timer)  # should really never happen
        glib.source_remove(self.finish_timer)

    def validate(self):
        '''method from the super that deals with the update
           button being pressed'''
        # changing screens stop the timer
        glib.source_remove(self.timer)
        glib.source_remove(self.finish_timer)

    #--------------------------------------------------------------------------
    # Signal handler methods

    def installation_file_enter(self, widget, event, user_data=None):
        ''' Pause the cycling of marketing images while the mouse
            is hovered over the image.
        '''

        self.image_pause = True

    def installation_file_leave(self, widget, event, user_data=None):
        ''' Resume cycling of marketing images when the mouse
            moves away from the image.
        '''

        self.image_pause = False

    def installation_file_key_release(self, widget, event, user_data=None):
        ''' Allow the user to manually cycle back and forth through the
            marketing images when the left and right arrow buttons are pressed.
        '''

        if gtk.gdk.keyval_name(event.keyval) == "Left":
            self._show_prev_image()
        elif gtk.gdk.keyval_name(event.keyval) == "Right":
            self._show_next_image()

    def installation_file_button_press(self, widget, event, user_data=None):
        '''Allow the user to click the image and open the associated URL.
        '''

        image_keys = sorted(self.urlimage_dictionary.keys())
        index = (self.image_index) % len(image_keys)
        url = self.urlimage_dictionary[image_keys[index]]
        if url:
            self.show_url = url
            timer = glib.timeout_add(SHOWURL_TIMEOUT, self._show_url_cb)

    #--------------------------------------------------------------------------
    # Private methods

    def _show_url_cb(self):
        '''timer callback to show the URL outside the
           main thread.
        '''
        if self.show_url:
            Popen([FIREFOX, self.show_url])
            self.show_url = None

        return False

    def _update_screen_message(self):
        ''' Updates the information on the screen.
            if update_screen is True then it will update the percent and
            messaging on the screen otherwise it simply re-establishes the
            the timer for the function.
        '''
        if self.update_screen:
            self.installationinfolabel.set_label(self.message)
            self.set_progress_fraction(self.fraction)
            self.update_screen = False

        return True

    def _show_prev_image(self):
        ''' Show the next image from image_names_list.
        '''
        image_keys = sorted(self.urlimage_dictionary.keys())
        index = (self.image_index - 1) % len(image_keys)
        self.installationimage.set_from_file(image_keys[index])
        self.image_index = index

    def _show_next_image(self):
        ''' Show the previous image from image_names_list.
        '''
        image_keys = sorted(self.urlimage_dictionary.keys())
        index = (self.image_index + 1) % len(image_keys)
        self.installationimage.set_from_file(image_keys[index])
        self.image_index = index
