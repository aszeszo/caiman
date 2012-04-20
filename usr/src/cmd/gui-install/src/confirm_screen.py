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
Confirm Screen for GUI Install app
'''

import pygtk
pygtk.require('2.0')

import locale
import logging

from gnome.ui import url_show_on_screen
import gtk

from solaris_install.engine import InstallEngine
from solaris_install.gui_install.base_screen import BaseScreen, \
    NotOkToProceedError
from solaris_install.gui_install.gui_install_common import \
    empty_container, modal_dialog, COLOR_WHITE, RELEASE, GLADE_ERROR_MSG
from solaris_install.gui_install.install_profile import InstallProfile
from solaris_install.logger import INSTALL_LOGGER_NAME
from solaris_install.sysconfig.profile import from_engine
from solaris_install.sysconfig.profile.support_info import SupportInfo
from solaris_install.target import Target
from solaris_install.target.controller import DEFAULT_VDEV_NAME, \
    DEFAULT_ZPOOL_NAME
from solaris_install.target.physical import Disk, Partition, GPTPartition
from solaris_install.target.size import Size


class ConfirmScreen(BaseScreen):
    '''
     Confirm Screen for GUI Install app
    '''
    LICENSEURL = "http://www.oracle.com/technetwork/licenses/" \
                 "solaris-cluster-express-license-167852.html"
    INDENTED_DETAIL_LINE_MARKUP = '<span font_desc="Arial Bold">' \
        '    &#8226; </span><span font_desc="Arial">%s</span>'
    NON_INDENTED_DETAIL_LINE_MARKUP = '<span font_desc="Arial Bold">' \
        '&#8226; </span><span font_desc="Arial">%s</span>'
    WARNING_MARKUP = '<span size="smaller">%s</span>'

    def __init__(self, builder):
        super(ConfirmScreen, self).__init__(builder)
        self.name = "Confirmation Screen"
        self.logger = logging.getLogger(INSTALL_LOGGER_NAME)

        self.confirmviewport = self.builder.get_object("confirmviewport")
        self.nextbutton = self.builder.get_object("nextbutton")
        self.installbutton = self.builder.get_object("installbutton")
        self.licenseagreementlinkbutton = self.builder.get_object(
            "licenseagreementlinkbutton")
        self.licensecheck = self.builder.get_object("licensecheckbutton")
        self.diskvbox = self.builder.get_object("diskvbox")
        self.softwarevbox = self.builder.get_object("softwarevbox")
        self.timezonevbox = self.builder.get_object("timezonevbox")
        self.languagesvbox = self.builder.get_object("languagesvbox")
        self.accountvbox = self.builder.get_object("accountvbox")
        self.supportvbox = self.builder.get_object("supportvbox")

        if None in [self.confirmviewport, self.nextbutton, self.installbutton,
            self.licenseagreementlinkbutton, self.licensecheck,
            self.diskvbox, self.softwarevbox, self.timezonevbox,
            self.languagesvbox, self.accountvbox, self.supportvbox]:
            modal_dialog(_("Internal error"), GLADE_ERROR_MSG)
            raise RuntimeError(GLADE_ERROR_MSG)

    def enter(self):
        '''enter method for the confirm screen'''
        toplevel = self.set_main_window_content("confirmmainvbox")

        # Screen-specific configuration
        self.activate_stage_label("installationstagelabel")

        self.set_titles(_("Installation"),
            _("Review the settings below before installing. "
                "Click the back button to make changes."),
            None)

        self.confirmviewport.modify_bg(gtk.STATE_NORMAL, COLOR_WHITE)
        self.nextbutton.hide_all()
        self.installbutton.set_sensitive(True)
        self.installbutton.show_all()
        self.licenseagreementlinkbutton.connect("clicked",
            self.licensebutton_callback, None)
        self.licensecheck.set_active(True)
        self.licensecheck.connect('toggled', self.licensechecked_callback,
            None)

        self._show_install_details()

        self.set_back_next(back_sensitive=True, next_sensitive=False)

        toplevel.show_all()

        return False

    def _show_install_details(self):
        '''Internal function to setup the install details on the screen'''
        def add_detail_line(vbox, text_str, indent=False, warning=None):
            '''sets up the details within the widget'''
            detail_hbox = gtk.HBox(homogeneous=False, spacing=5)

            detail_label = gtk.Label()
            detail_label.set_selectable(True)
            detail_label.set_padding(10, 0)
            if indent:
                markup = ConfirmScreen.INDENTED_DETAIL_LINE_MARKUP % text_str
            else:
                markup = ConfirmScreen.NON_INDENTED_DETAIL_LINE_MARKUP % \
                              text_str
            detail_label.set_markup(markup)

            detail_hbox.pack_start(detail_label, expand=False,
                fill=True, padding=0)

            if warning is not None:
                detail_img = gtk.image_new_from_stock(gtk.STOCK_DIALOG_WARNING,
                    gtk.ICON_SIZE_MENU)
                detail_img.show()

                detail_warning = gtk.Label()
                detail_warning.set_selectable(True)
                markup = ConfirmScreen.WARNING_MARKUP % warning
                detail_warning.set_markup(markup)
                detail_warning.show()

                detail_hbox.pack_start(detail_img, expand=False,
                    fill=True, padding=0)
                detail_hbox.pack_start(detail_warning, expand=False,
                    fill=True, padding=0)

            vbox.pack_start(detail_hbox, expand=False, fill=False, padding=0)
            detail_hbox.show_all()

            return detail_label

        # Fetch the user-entered details from the DOC
        engine = InstallEngine.get_instance()
        doc = engine.data_object_cache

        desired_root = doc.get_descendants(class_type=Target,
            name=Target.DESIRED,
            max_depth=2,
            not_found_is_err=True)[0]
        disks = desired_root.get_children(class_type=Disk,
            not_found_is_err=True)

        profile = doc.volatile.get_first_child(
            name="GUI Install",
            class_type=InstallProfile)
        if profile is None:
            raise RuntimeError("INTERNAL ERROR: Unable to retrieve "
                "InstallProfile from DataObjectCache")

        self.logger.info("**** Install Details ****")

        empty_container(self.diskvbox, destroy=True)
        self.logger.info("-- Disk --")
        first_disk = None
        for disk in disks:
            # The Disk screen will have ensured there is an appropriate
            # Solaris(2) partition and that Disk and Partition sizes are valid
            disksize = locale.format('%.1f',
                disk.disk_prop.dev_size.get(units=Size.gb_units))

            # Distinguish between regular and iSCSI targets
            if disk.disk_prop is not None and \
                disk.disk_prop.dev_type == "iSCSI":
                diskdescriptor = _("iSCSI disk")
            else:
                diskdescriptor = _("disk")

            if disk.whole_disk:
                text_str = _("%(disksize)s GB disk (%(disk)s)") % \
                     {"disksize": disksize,
                      "disk": disk.ctd}
                warn_str = _("The whole disk will be erased")
            else:
                if disk.label == "VTOC":
                    parts = disk.get_children(class_type=Partition)
                    target_part = next((p for p in parts if p.is_solaris),
                        None)
                else:  # GPT by default
                    parts = disk.get_children(class_type=GPTPartition)
                    target_part = next((p for p in parts if \
                        p.is_solaris and \
                        p.in_zpool == DEFAULT_ZPOOL_NAME and \
                        p.in_vdev == DEFAULT_VDEV_NAME),
                        None)

                partsize = locale.format('%.1f',
                    target_part.size.get(units=Size.gb_units))

                text_str = _("%(partsize)s GB partition on "
                     "%(disksize)s GB %(diskdescriptor)s (%(disk)s)") % \
                     {"partsize": partsize,
                      "disksize": disksize,
                      "diskdescriptor": diskdescriptor,
                      "disk": disk.ctd}
                warn_str = _("This partition will be erased")

            adisk = add_detail_line(self.diskvbox, text_str, warning=warn_str)
            if first_disk == None:
                first_disk = adisk

            self.logger.info('\t' + text_str + " " + warn_str)

        if first_disk is not None:
            first_disk.grab_focus()

        install_size = locale.format('%.1f',
            profile.target_controller.minimum_target_size.get(
            units=Size.gb_units))
        translated = _("The whole installation will take " \
                "up %s GB hard disk space.")
        text_str = translated % install_size
        add_detail_line(self.diskvbox, text_str)
        self.logger.info('\t' + text_str)

        empty_container(self.softwarevbox, destroy=True)
        add_detail_line(self.softwarevbox, RELEASE)
        self.logger.info("-- Software --")
        self.logger.info('\t' + RELEASE)

        empty_container(self.timezonevbox, destroy=True)
        add_detail_line(self.timezonevbox, profile.timezone)
        self.logger.info("-- Timezone --")
        self.logger.info('\t' + profile.timezone)

        empty_container(self.languagesvbox, destroy=True)
        text_str = _("Default Language: %s") % profile.default_locale
        add_detail_line(self.languagesvbox, text_str)
        self.logger.info("-- Locale --")
        self.logger.info('\t' + text_str)

        text_str = _("Language Support:")
        for lang in profile.languages:
            text_str += " %s" % lang
        add_detail_line(self.languagesvbox, text_str)
        self.logger.info('\t' + text_str)

        empty_container(self.supportvbox, destroy=True)
        support = from_engine().support
        support_str = ""
        if not support.mos_email and not support.mos_password:
            support_str += _("No support configured")
        else:
            if not support.mos_password:
                support_str += _("Anonymous support")
            else:
                support_str += _("My Oracle Support")

            if support.netcfg == SupportInfo.PROXY:
                support_str += " " + _("via Proxy")
            elif support.netcfg == SupportInfo.HUB:
                support_str += " " + _("via Hub")
        text_str = _("Support configuration: %s") % support_str
        add_detail_line(self.supportvbox, text_str)
        self.logger.info("-- Support --")
        self.logger.info('\t' + text_str)

        empty_container(self.accountvbox, destroy=True)
        if profile.loginname is None:
            text_str = _("User Account: %s") % _("No user account.")
        else:
            text_str = _("User Account: %s") % profile.loginname
        add_detail_line(self.accountvbox, text_str)
        self.logger.info("-- Users --")
        self.logger.info('\t' + text_str)
        text_str = _("Root Password: Same as user account.")
        add_detail_line(self.accountvbox, text_str)
        self.logger.info('\t' + text_str)
        text_str = _("Host name: %s") % profile.hostname
        add_detail_line(self.accountvbox, text_str)
        self.logger.info('\t' + text_str)

    def licensechecked_callback(self, widget, data=None):
        '''callback for "clicked" event on license check button'''
        if widget.get_active():
            self.installbutton.set_sensitive(True)
        else:
            self.installbutton.set_sensitive(False)

    def licensebutton_callback(self, widget, data):
        '''callback for "clicked" event on license button'''
        url_show_on_screen(self.LICENSEURL, widget.get_screen())

    def go_back(self):
        ''' Deals with the Back button being pressed.
            Overrides abstract method defined in superclass.'''
        if self.nextbutton is not None and self.installbutton is not None:
            self.installbutton.hide_all()
            self.nextbutton.show_all()

    def validate(self):
        ''' Deals with the Install button being pressed.
            Overrides abstract method defined in superclass.'''
        if self.licensecheck and not self.licensecheck.get_active():
            raise NotOkToProceedError("License agreement not accepted")
