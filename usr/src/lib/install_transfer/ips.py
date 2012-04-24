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
# Copyright (c) 2010, 2012, Oracle and/or its affiliates. All rights reserved.
#
'''Transfer IPS checkpoint. Sub-class of the checkpoint class'''

import abc
import copy
import gettext
import locale
import os
import shutil

import pkg.client.api as api
import pkg.client.api_errors as api_errors
import pkg.client.image as image
import pkg.client.progress as progress
import pkg.client.publisher as publisher
import pkg.misc as misc

from pkg.client import global_settings
from pkg.client.api import IMG_TYPE_ENTIRE, IMG_TYPE_PARTIAL
from solaris_install import PKG5_API_VERSION
from solaris_install.engine.checkpoint import AbstractCheckpoint as Checkpoint
from solaris_install.engine import InstallEngine
from solaris_install.transfer.info import Args
from solaris_install.transfer.info import Destination
from solaris_install.transfer.info import Facet
from solaris_install.transfer.info import Image
from solaris_install.transfer.info import ImType
from solaris_install.transfer.info import IPSSpec
from solaris_install.transfer.info import Mirror
from solaris_install.transfer.info import Origin
from solaris_install.transfer.info import Property
from solaris_install.transfer.info import Publisher
from solaris_install.transfer.info import Software
from solaris_install.transfer.info import Source
from solaris_install.transfer.info import ACTION, CONTENTS, \
PURGE_HISTORY, APP_CALLBACK, IPS_ARGS, UPDATE_INDEX, REJECT_LIST
from solaris_install.transfer.prog import ProgressMon

LICENSE_ACCEPTED = "automatically accepted"
LICENSE_NOT_DISP = "not displayed"

PKG_CLIENT_NAME = "transfer module"

global_settings.client_name = PKG_CLIENT_NAME
misc.setlocale(locale.LC_ALL, "")
gettext.install("pkg", "/usr/share/locale")


class InstallCLIProgressTracker(progress.NullProgressTracker):
    ''' Subclass of the IPS api's NullProgressTracker to handle a simple
        form of progress reporting.  If requested with 'show_stdout', we
        output progress to stdout by posting a logging INFO message.
        Otherwise we just output progress to log files by posting a
        logging DEBUG message.
    '''

    def __init__(self, trans_logger, show_stdout=False):
        super(InstallCLIProgressTracker, self).__init__()
        self.trans_logger = trans_logger
        self.show_stdout = show_stdout
        self._dl_cur_pkg = None
        self._dl_started = False
        self._act_started = False
        self._ind_started = False
        self._item_started = False

    def _logger_output(self, message):
        if self.show_stdout:
            self.trans_logger.info(message)
        else:
            self.trans_logger.debug(message)

    def eval_output_start(self):
        self._logger_output("Creating Plan ... Started.")

    def eval_output_done(self):
        self._logger_output("Creating Plan ... Done.")

    def refresh_output_start(self):
        self._logger_output("Refreshing Catalog ... Started.")

    def refresh_output_done(self):
        self._logger_output("Refreshing Catalog ... Done.")

    def dl_output(self):
        if not self._dl_started:
            self._logger_output("Download Phase ... Started.")
            self._dl_started = True

        if self._dl_cur_pkg != self.cur_pkg:
            self._logger_output("Download: %s ..." % self.cur_pkg)
            self._dl_cur_pkg = self.cur_pkg

    def dl_output_done(self):
        self._logger_output("Download Phase ... Done.")
        self._dl_started = False
        self._dl_cur_pkg = None

    def act_output(self, force=False):
        if not self._act_started:
            self._logger_output("%s ... Started." % self.act_phase)
            self._act_started = True

    def act_output_done(self):
        self._logger_output("%s ... Done." % self.act_phase)
        self._act_started = False

    def ind_output(self, force=False):
        if not self._ind_started:
            self._logger_output("%s ... Started." % self.ind_phase)
            self._ind_started = True

    def ind_output_done(self):
        self._logger_output("%s ... Done." % self.ind_phase)
        self._ind_started = False

    def item_output(self, force=False):
        if not self._item_started:
            self._logger_output("%s ... Started." % self.item_phase)
            self._item_started = True

    def item_output_done(self):
        self._logger_output("%s ... Done." % self.item_phase)
        self._item_started = False


class InstallFancyProgressTracker(progress.FancyUNIXProgressTracker):
    ''' Subclass of the IPS api's FancyUNIXProgressTracker; we leverage
        that class's progress reporting, allowing it to output straight to
        stdout.  The overridden methods we define allow us to capture the
        parts of the progress that we want recorded to the install log.

        This progress tracking class should only be used when the
        application is being run on a terminal with UNIX-like semantics
        and will fail to initialize otherwise.
    '''
    def __init__(self, trans_logger, quiet=False, verbose=0):
        super(InstallFancyProgressTracker, self).__init__(quiet=quiet,
            verbose=verbose)

        self.trans_logger = trans_logger
        self._dl_cur_pkg = None
        self._dl_started = False
        self._act_started = False
        self._ind_started = False
        self._item_started = False

    def eval_output_start(self):
        super(InstallFancyProgressTracker, self).eval_output_start()
        self.trans_logger.debug("Creating Plan ... Started.")

    def eval_output_done(self):
        super(InstallFancyProgressTracker, self).eval_output_done()
        self.trans_logger.debug("Creating Plan ... Done.")

    def refresh_output_start(self):
        super(InstallFancyProgressTracker, self).refresh_output_start()
        self.trans_logger.debug("Refreshing Catalog ... Started.")

    def refresh_output_done(self):
        super(InstallFancyProgressTracker, self).refresh_output_done()
        self.trans_logger.debug("Refreshing Catalog ... Done.")

    def dl_output(self, force=False):
        super(InstallFancyProgressTracker, self).dl_output(force=force)
        if not self._dl_started:
            self.trans_logger.debug("Download Phase ... Started.")
            self._dl_started = True

        if self._dl_cur_pkg != self.cur_pkg:
            self.trans_logger.debug("Download: %s ..." % self.cur_pkg)
            self._dl_cur_pkg = self.cur_pkg

    def dl_output_done(self):
        super(InstallFancyProgressTracker, self).dl_output_done()
        self.trans_logger.debug("Download Phase ... Done.")
        self._dl_started = False
        self._dl_cur_pkg = None

    def act_output(self, force=False):
        super(InstallFancyProgressTracker, self).act_output(force=force)
        if not self._act_started:
            self.trans_logger.debug("%s ... Started." % self.act_phase)
            self._act_started = True

    def act_output_done(self):
        super(InstallFancyProgressTracker, self).act_output_done()
        self.trans_logger.debug("%s ... Done." % self.act_phase)
        self._act_started = False

    def ind_output(self, force=False):
        super(InstallFancyProgressTracker, self).ind_output(force=force)
        if not self._ind_started:
            self.trans_logger.debug("%s ... Started." % self.ind_phase)
            self._ind_started = True

    def ind_output_done(self):
        super(InstallFancyProgressTracker, self).ind_output_done()
        self.trans_logger.debug("%s ... Done." % self.ind_phase)
        self._ind_started = False

    def item_output(self, force=False):
        super(InstallFancyProgressTracker, self).item_output(force=force)
        if not self._item_started:
            self.trans_logger.debug("%s ... Started." % self.item_phase)
            self._item_started = True

    def item_output_done(self):
        super(InstallFancyProgressTracker, self).item_output_done()
        self.trans_logger.debug("%s ... Done." % self.item_phase)
        self._item_started = False


class AbstractIPS(Checkpoint):
    '''Subclass for transfer IPS checkpoint'''
    __metaclass__ = abc.ABCMeta

    # Variables associated with the package image
    DEF_REPO_URI = "http://pkg.opensolaris.org/release"
    DEF_PROG_TRACKER = progress.CommandLineProgressTracker()

    # Variables used in calculating the image size
    DEFAULT_PROG_EST = 10
    DEFAULT_SIZE = 1000
    DEFAULT_PKG_NUM = 5

    # Variables used to check system version info
    SYSTEM_IMAGE = "/"
    ENT_PKG = ["entire"]
    SYSTEM_CLIENT_NAME = "host"
    INFO_NEEDED = api.PackageInfo.ALL_OPTIONS

    # Action variables
    CREATE = "create"
    EXISTING = "use_existing"
    UPDATE = "update"

    def __init__(self, name, zonename=None, show_stdout=False):
        super(AbstractIPS, self).__init__(name)

        # attributes per image
        self.dst = None
        self.img_action = self.CREATE
        self.index = False
        self.src = None   # [(pub_name, [origin], [mirror])]
        self.image_args = {}
        self.completeness = IMG_TYPE_ENTIRE
        self.is_zone = False
        self.zonename = zonename
        self.show_stdout = show_stdout
        self.facets = {}
        self.properties = {}

        # To be used for progress reporting
        self.distro_size = 0
        self.give_progress = False

        # Handle for the progress monitor
        self.pmon = None

        # handle for the ips api
        self.api_inst = None

        # Determines whether a dry run occurs
        self.dry_run = False

        # Flag to cancel whatever action is going on.
        self._cancel_event = False

        # Set the progress tracker for IPS operations.
        if self.show_stdout:
            # If we've been requested to show progress to stdout, try to
            # intantiate the Fancy progress tracker.  If we're not running
            # on a capable terminal, fall back to the CLI progress tracker.
            try:
                self.prog_tracker = InstallFancyProgressTracker(self.logger)
            except progress.ProgressTrackerException:
                self.prog_tracker = InstallCLIProgressTracker(self.logger,
                    show_stdout=self.show_stdout)
        else:
            # Else if we've not been requested to show progress at all,
            # instantiate the the CLI progress tracker.
            self.prog_tracker = InstallCLIProgressTracker(self.logger,
                show_stdout=self.show_stdout)

        # local attributes used to create the publisher.
        self._publ = None
        self._origin = []
        self._mirror = []
        self._add_publ = []
        self._add_origin = []
        self._add_mirror = []
        self._image_args = {}

        # publisher list to hold a reference between publishers and
        # origins/mirrors
        self.publisher_list = list()

        # List to hold dictionaries of transfer actions
        self._transfer_list = []

    def get_size(self):
        '''Compute the size of the transfer specified.'''
        self._parse_input()
        self._validate_input()
        num_pkgs = 0
        for trans in self._transfer_list:
            num_pkgs += len(trans.get(CONTENTS))
        return self.DEFAULT_SIZE * (num_pkgs / self.DEFAULT_PKG_NUM)

    def get_progress_estimate(self):
        '''Returns an estimate of the time this checkpoint will
           take.
        '''
        if self.distro_size == 0:
            self.distro_size = self.get_size()

        progress_estimate = \
            int((float(self.distro_size) / self.DEFAULT_SIZE) * \
                self.DEFAULT_PROG_EST)
        self.give_progress = True
        return progress_estimate

    def cancel(self):
        '''Cancel the transfer in progress'''
        self._cancel_event = True
        if self.api_inst:
            self.api_inst.cancel()

    def execute(self, dry_run=False):
        '''Execute method for the IPS checkpoint module. Will read the
           input parameters and perform the specified transfer.
        '''
        self.logger.debug("=== Executing %s Checkpoint ===" % self.name)
        try:
            if self.give_progress:
                self.logger.report_progress("Beginning IPS transfer", 0)

            self.dry_run = dry_run

            # Read the parameters from the DOC and put into the
            # local attributes.
            self._parse_input()

            # Validate the attributes
            self._validate_input()

            # Get the handle to the IPS image api.
            if not self.dry_run:
                self.get_ips_api_inst()

            # Perform the transferring of the bit/updating of the image.
            self._transfer()

            if not self.dry_run:
                # Check to see that the entire package on the host system
                # matches the package in the target image, if the entire
                # package is included in the package list.  Log a warning
                # message if the versions don't match.
                # If it isn't found in the package list or on the system,
                # this isn't an error. Continue with the installation.
                for trans_val in self._transfer_list:
                    if trans_val.get(ACTION) == "install":
                        for pkg in trans_val.get(CONTENTS):
                            if "entire" in pkg:
                                sysinst = api.ImageInterface(self.SYSTEM_IMAGE,
                                                       PKG5_API_VERSION,
                                                       self.prog_tracker,
                                                       False,
                                                       self.SYSTEM_CLIENT_NAME)

                                installer_entire_info = \
                                     sysinst.info(fmri_strings=self.ENT_PKG,
                                                  local=True,
                                                  info_needed=self.INFO_NEEDED)

                                target_entire_info = self.api_inst.info(
                                                  fmri_strings=self.ENT_PKG,
                                                  local=True,
                                                  info_needed=self.INFO_NEEDED)

                                if not installer_entire_info[
                                    api.ImageInterface.INFO_FOUND] or \
                                    not target_entire_info[
                                    api.ImageInterface.INFO_FOUND]:
                                    continue

                                installer_entire_pi = \
                                    installer_entire_info[ \
                                        api.ImageInterface.INFO_FOUND][0]
                                target_entire_pi = \
                                    target_entire_info[ \
                                        api.ImageInterface.INFO_FOUND][0]

                                if installer_entire_pi.branch != \
                                    target_entire_pi.branch:
                                    self.logger.warning("Version mismatch: ")
                                    self.logger.warning(
                                        "Installer build version: %s" %
                                        (installer_entire_pi.fmri))
                                    self.logger.warning(
                                        "Target build version: %s" %
                                        (target_entire_pi.fmri))
            self.check_cancel_event()

        except api_errors.CatalogRefreshException, cre:
            '''Handle CatalogRefreshException especially since it doesn't
               pretty-print it's contents in a __str__() impl.
            '''
            raise RuntimeError(self.catalog_failures_to_str(cre))
        finally:
            self._cleanup()

    @abc.abstractmethod
    def _parse_input(self):
        '''This method is required to be implemented by all subclasses.'''
        raise NotImplementedError

    def _validate_input(self):
        '''Do whatever validation is necessary on the attributes.'''
        self.logger.debug("Validating IPS input")

        # dst is required
        if self.dst is None:
            raise ValueError("IPS destination must be specified")

        if self.img_action not in (self.EXISTING, self.CREATE, self.UPDATE):
            raise ValueError("The IPS action is not valid: %s" %
                              self.img_action)

        self.logger.debug("Destination: %s", self.dst)
        self.logger.debug("Image action: %s", self.img_action)
        if self.completeness == "full":
            self.completeness = IMG_TYPE_ENTIRE
            self.logger.debug("Image Type: full")
        elif self.completeness == "partial":
            self.completeness = IMG_TYPE_PARTIAL
            self.logger.debug("Image Type: partial")

        if self.is_zone:
            self.logger.debug("Image Variant: zone")
            # For images of type zone, we need the zonename so that
            # we can construct the linked image name when attaching
            # it to the parent image.
            if not self.zonename:
                raise ValueError("For images of type 'zone', a zonename "
                                 "must be provided.")

        not_allowed = set(["prefix", "repo_uri", "origins", "mirrors"])
        img_args = set(self.image_args.keys())
        overlap = list(not_allowed & img_args)
        if overlap:
            raise ValueError("The following components may be specified "
                             "with the source component of the manifest but "
                             "are invalid as args: " + str(overlap))

        self.prog_tracker = self.image_args.get("progtrack", self.prog_tracker)

        # Set the image args we always want set.
        if self.img_action == self.CREATE:
            self.set_image_args()

    def _transfer(self):
        '''If an update of the image has been specified, the publishers of the
           existing image are examined.  If a matching publisher is found, the
           origins and mirrors (if present) are reset to the desired entries.
           All other publishers in the image are removed and the new additional
           publishers are added.  Then properties are set, if specified and the
           transfer specific operations of install, uninstall and purge history
           are performed.
           If creation of the image has been specified, the additional
           publishers are added to the image, properties are set and the
           transfer specific operations of install, uninstall and purge history
           are performed.
        '''
        if self.give_progress and self.distro_size != 0:
            # Start up the ProgressMon to report progress
            # while the actual transfer is taking place.
            self.pmon = ProgressMon(logger=self.logger)
            self.pmon.startmonitor(self.dst, self.distro_size, 0, 100)

        if self.img_action == self.EXISTING and self._publ \
           and not self.dry_run:
            # See what publishers/origins/mirrors we have
            self.logger.debug("Updating the publishers")
            pub_list = self.api_inst.get_publishers(duplicate=True)

            self.logger.info("Setting post-install publishers to:")
            self.print_repository_uris()

            # Look to see if the publisher in _publ is already in the Image
            if self.api_inst.has_publisher(prefix=self._publ):
                # update the publisher
                pub = self.api_inst.get_publisher(prefix=self._publ,
                                                  duplicate=True)
                self.logger.debug("Updating publisher information for " \
                                  "%s" % str(self._publ))
                repository = pub.repository
                repository.reset_origins()
                repository.reset_mirrors()
                for origin in self._origin:
                    repository.add_origin(origin)
                if self._mirror is not None:
                    for mirror in self._mirror:
                        repository.add_mirror(mirror)
                self.api_inst.update_publisher(pub=pub, refresh_allowed=False,
                                               search_first=True)
            else:
                # create a new publisher and set it to the highest ranked
                # publisher
                if self._mirror:
                    repo = publisher.Repository(mirrors=self._mirror,
                                                origins=self._origin)
                else:
                    repo = publisher.Repository(origins=self._origin)
                pub = publisher.Publisher(prefix=self._publ, repository=repo)
                self.api_inst.add_publisher(pub=pub, refresh_allowed=False,
                                            search_first=True)

            # the highest ranking publisher has been set.  Walk the other
            # publishers in the list and remove them.
            for pub in self.api_inst.get_publishers(duplicate=True)[1:]:
                self.api_inst.remove_publisher(prefix=pub.prefix)

        # Add specified publishers/origins/mirrors to the image.
        for idx, element in enumerate(self._add_publ):
            # If this publisher doesn't already exist, add it.  (In dry_run
            # mode, api_inst is not initialized so always add these publishers
            # as additionals because we know they won't be pre-existing.)
            if self.dry_run or not self.api_inst.has_publisher(prefix=element):
                self.logger.debug("Adding additional publisher %s" % \
                                  str(element))
                if self._add_mirror[idx]:
                    repo = publisher.Repository(mirrors=self._add_mirror[idx],
                                                origins=self._add_origin[idx])
                else:
                    repo = publisher.Repository(origins=self._add_origin[idx])
                pub = publisher.Publisher(prefix=element, repository=repo)
                if not self.dry_run:
                    self.api_inst.add_publisher(pub=pub, refresh_allowed=False)
            # Else update the existing publisher with this spec
            else:
                self.logger.debug("Updating publisher information for " \
                                  "%s" % str(element))
                pub = self.api_inst.get_publisher(prefix=element,
                                                  duplicate=True)
                repository = pub.repository
                if self._add_origin[idx]:
                    for origin in self._add_origin[idx]:
                        if not repository.has_origin(origin):
                            repository.add_origin(origin)
                if self._add_mirror[idx]:
                    for mirror in self._add_mirror[idx]:
                        if not repository.has_mirror(mirror):
                            repository.add_mirror(mirror)
                self.api_inst.update_publisher(pub=pub, refresh_allowed=False)

        # Get the publisher information of what the image is set with now.
        # Re-set publisher_list to that list, so that it can be used later
        # to be printed out
        if not self.dry_run:
            pub_list = self.api_inst.get_publishers(duplicate=True)
            pub_list_for_print = list()
            for pub in pub_list:
                repo = pub.repository
                origin_uris = list()
                mirror_uris = list()
                if repo.origins:
                    for origin in repo.origins:
                        origin_uris.append(origin.uri)
                if repo.mirrors:
                    for mirror in repo.mirrors:
                        mirror_uris.append(mirror.uri)
                pub_list_for_print.append((pub.prefix, origin_uris,
                    mirror_uris))
            self.publisher_list = pub_list_for_print

        if self.dry_run:
            self.logger.debug("Dry Run: publishers updated")

        self.check_cancel_event()

        if self.properties and not self.dry_run:
            # Update properties if needed.
            self.logger.debug("Updating image properties")
            img = self.api_inst.img
            for prop in self.properties.keys():
                if prop == "preferred-publisher":
                    # Can't set preferred-publisher via set_property, you
                    # must use set_preferred_publisher
                    img.set_highest_ranked_publisher(
                        prefix=self.properties[prop])
                else:
                    if isinstance(self.properties[prop], bool):
                        self.properties[prop] = str(self.properties[prop])
                    img.set_property(prop, self.properties[prop])

        # Refresh publishers now that we've set the publishers,  otherwise
        # avoid/unavoid will not work and will cause install failures
        if not self.dry_run:
            self.api_inst.refresh(immediate=True)

        # Perform the transfer specific operations.
        for trans_val in self._transfer_list:
            if trans_val.get(ACTION) == "install":
                self.check_cancel_event()
                callback = trans_val.get(APP_CALLBACK)
                if trans_val.get(CONTENTS):
                    self.logger.info("Installing packages from:")
                    self.print_repository_uris()

                    reject_list = trans_val.get(REJECT_LIST)
                    if reject_list:
                        self.logger.info(
                            "Transfer set to reject packages matching:")
                        for pkg in reject_list:
                            self.logger.info("  %s", pkg)
                    else:
                        # Set the reject list to be the default value rather
                        # than None
                        self.logger.debug(
                            "Transfer reject package list is empty")
                        reject_list = misc.EmptyI

                    if not self.dry_run:
                        # Install packages
                        if trans_val.get(IPS_ARGS):
                            self.api_inst.plan_install(
                                     pkg_list=trans_val.get(CONTENTS),
                                     reject_list=reject_list,
                                     **trans_val.get(IPS_ARGS))
                        else:
                            self.api_inst.plan_install(
                                    pkg_list=trans_val.get(CONTENTS),
                                    reject_list=reject_list)

                        if callback:
                            # execute the callback function passing it
                            # the api object we are using to perform the
                            # transfer to perform additional inspection or
                            # deal with things such as license acceptance.
                            callback(self.api_inst)

                        licensed = dict()
                        plan = self.api_inst.describe()
                        for pfmri, src, dest, accepted, displayed \
                            in plan.get_licenses():

                            if not dest.must_accept and not dest.must_display:
                                continue

                            # Use just the package name, no publisher or
                            # version, neater output.
                            fmri = pfmri.get_name()
                            licensed[fmri] = list()
                            if dest.must_accept:
                                licensed[fmri].append(LICENSE_ACCEPTED)
                            if dest.must_display:
                                licensed[fmri].append(LICENSE_NOT_DISP)

                            self.api_inst.set_plan_license_status(pfmri,
                                dest.license, displayed=True, accepted=True)

                        if licensed:
                            self.logger.info("Please review the licenses "
                                "for the following packages post-install:")
                            for fmri in licensed:
                                if len(licensed[fmri]) == 2:
                                    # Looks better to output over two lines,
                                    # when there are two flags to output
                                    self.logger.info("  %-40s (%s,", fmri,
                                                     licensed[fmri][0])
                                    self.logger.info("  %-40s  %s)", "",
                                                     licensed[fmri][1])
                                else:
                                    # Always at least one, otherwise wouldn't
                                    # be in the dictionary at all.
                                    self.logger.info("  %-40s (%s)", fmri,
                                                     licensed[fmri][0])
                            self.logger.info("Package licenses may be viewed "
                                "using the command:")
                            self.logger.info("  pkg info --license <pkg_fmri>")

                        # Execute the transfer action
                        self.api_inst.prepare()
                        self.api_inst.execute_plan()
                        self.api_inst.reset()

                        # The above call will end up leaving our process's cwd
                        # in the image's root area, which will cause pain later
                        # in trying to unmount the image.  So we manually
                        # change dir back to "/".
                        os.chdir("/")

                    else:
                        self.logger.debug("Dry Run: Installing packages")

            elif trans_val.get(ACTION) == "uninstall":
                self.logger.debug("Uninstalling packages")
                if not self.dry_run:
                    # Uninstall packages
                    if IPS_ARGS in trans_val:
                        self.api_inst.plan_uninstall(trans_val.get(CONTENTS),
                            **trans_val.get(IPS_ARGS))
                    else:
                        self.api_inst.plan_uninstall(trans_val.get(CONTENTS))

                    # Execute the transfer action
                    self.api_inst.prepare()
                    self.api_inst.execute_plan()
                    self.api_inst.reset()

            elif trans_val.get(ACTION) == "avoid":
                self.logger.info("Setting packages to avoid:")
                avoid_list = trans_val.get(CONTENTS)
                for pkg in avoid_list:
                    self.logger.info("  %s", pkg)
                if not self.dry_run:
                    # Avoid packages
                    self.api_inst.avoid_pkgs(avoid_list)

            elif trans_val.get(ACTION) == "unavoid":
                self.logger.info("Removing packages from list to avoid:")
                unavoid_list = trans_val.get(CONTENTS)
                for pkg in unavoid_list:
                    self.logger.info("  %s", pkg)
                if not self.dry_run:
                    # Avoid packages
                    self.api_inst.avoid_pkgs(unavoid_list, unavoid=True)

            if trans_val.get(PURGE_HISTORY):
                # purge history if requested.
                self.logger.debug("Purging History")
                if not self.dry_run:
                    img = self.api_inst.img
                    img.history.purge()

    def check_cancel_event(self):
        '''Check to see if a cancel event of the transfer is requested. If so,
           cleanup changes made to the system and raise an exception.
        '''
        if self._cancel_event:
            self._cleanup()

    def _cleanup(self):
        '''Method to perform any necessary cleanup needed.'''
        self.logger.debug("Cleaning up")
        if self.pmon:
            self.pmon.done = True
            self.pmon.wait()
            self.pmon = None

    def set_image_args(self):
        '''Set the image args we need set because the information
           was passed in via other attributes. These include progtrack,
           prefix, repo_uri, origins, and mirrors.  If we're creating a
           zone image, we also need to set the use-system-repo property
           in the props argument.
        '''
        self._image_args = copy.copy(self.image_args)
        self._image_args["progtrack"] = self.prog_tracker
        if self._publ and self._publ is not None:
            self._image_args["prefix"] = self._publ
        if self._origin and self._origin is not None:
            self._image_args["repo_uri"] = self._origin[0]
        if self._origin[1:]:
            self._image_args["origins"] = self._origin[1:]
        if self._mirror and self._mirror is not None:
            self._image_args["mirrors"] = self._mirror
        if self.is_zone:
            if "props" in self._image_args:
                props_dict = self._image_args["props"]
                props_dict["use-system-repo"] = True
            else:
                props_dict = {"use-system-repo": True}
                self._image_args["props"] = props_dict

    def get_ips_api_inst(self):
        '''Get a handle to the api instance. If it is specified to use
           the existing image grab the handle for the appropriate
           image. If it's specified to create, remove any image that may
           be located at the destination and create a new one there.
           If any facets are specified, set them upon image creation.
        '''
        if self.img_action == self.EXISTING:
            # An IPS image should exist and we are to use it.
            self.logger.debug("Using existing image")
            _img = image.Image(root=self.dst, user_provided_dir=True)

            try:
                self.api_inst = api.ImageInterface(self.dst,
                    PKG5_API_VERSION, self.prog_tracker, None, PKG_CLIENT_NAME)
            except api_errors.VersionException, ips_err:
                raise ValueError("The IPS API version specified, "
                                       + str(ips_err.received_version) +
                                       " does not agree with "
                                       "the expected version, "
                                       + str(ips_err.expected_version))

        elif self.img_action == self.CREATE:
            # Create a new image, destroy the old one if it exists.
            self.logger.info("Creating IPS image")
            if self.facets:
                allow = {"TRUE": True, "FALSE": False}
                for fname in self.facets.keys():
                    if not fname.startswith("facet."):
                        raise ValueError("Facet name, %s, must "
                                         "begin with \"facet\"." % fname)
                    if not isinstance(self.facets[fname], bool):
                        if self.facets[fname].upper() not in allow:
                            raise ValueError("Facet argument must be "
                                             "True|False")
                        self.facets[fname] = \
                            allow[self.facets[fname].upper()]

                self._image_args.update({"facets": self.facets})

            if os.path.exists(self.dst):
                shutil.rmtree(self.dst, ignore_errors=True)

            try:
                self.api_inst = api.image_create(
                    pkg_client_name=PKG_CLIENT_NAME,
                    version_id=PKG5_API_VERSION, root=self.dst,
                    imgtype=self.completeness, is_zone=self.is_zone,
                    refresh_allowed=False, force=True, **self._image_args)

                # The above call will end up leaving our process's cwd in
                # the image's root area, which will cause pain later on
                # in tyring to unmount the image.  So we manually change
                # dir back to "/".
                os.chdir("/")

                if self.is_zone:
                    # If installing a zone image, attach its image as a
                    # linked image to the global zone.

                    # Get an api object for the current global system image.
                    gz_api_inst = api.ImageInterface(self.SYSTEM_IMAGE,
                        PKG5_API_VERSION, self.prog_tracker, False,
                        self.SYSTEM_CLIENT_NAME)

                    # For a zone's linked image name, we construct it as:
                    #     "zone:<zonename>"
                    lin = gz_api_inst.parse_linked_name(
                        "zone:" + self.zonename, allow_unknown=True)
                    self.logger.debug("Linked image name: %s" % lin)

                    # Attach the zone image as a linked image.
                    (ret, err, _none) = gz_api_inst.attach_linked_child(lin,
                        self.dst, force=True, li_md_only=True)
                    if err != None:
                        raise ValueError("Linked image error while attaching "
                                         "zone image '%s':\n%s" %
                                         (self.zonename, str(err)))

                    # Refresh the zone's api object now that it has been
                    # attached as a linked image.
                    self.api_inst.reset()

            except api_errors.VersionException, ips_err:
                self.logger.exception("Error creating the IPS image")
                raise ValueError("The IPS API version specified, "
                                       + str(ips_err.received_version) +
                                       " does not agree with "
                                       "the expected version, "
                                       + str(ips_err.expected_version))

    def print_repository_uris(self):
        '''print_repository_uris() - simple method to print out the
           repository uris used
        '''
        indent = 4 * " "
        indent2 = indent * 2
        for publisher, origin_list, mirror_list in self.publisher_list:
            self.logger.info(indent + publisher)
            for origin in origin_list:
                self.logger.info(indent2 + "origin:  " + origin)
            for mirror in mirror_list:
                self.logger.info(indent2 + "mirror:  " + mirror)


class TransferIPS(AbstractIPS):
    '''IPS Transfer class to take input from the DOC. It implements the
       checkpoint interface.
    '''
    VALUE_SEPARATOR = ","

    # Default values for arguments
    DEFAULT_ARG = {'zonename': None, 'show_stdout': False}

    def __init__(self, name, arg=DEFAULT_ARG):
        super(TransferIPS, self).__init__(name, zonename=arg.get('zonename'),
                                          show_stdout=arg.get('show_stdout'))

        # Holds the list of transfer dictionaries
        self._transfer_list = []

        # get the handle to the DOC
        self._doc = InstallEngine.get_instance().data_object_cache

        # Get the checkpoint info from the DOC
        self.soft_list = self._doc.get_descendants(name=self.name,
                                              class_type=Software)

        # Add check that soft_list has only one entry
        if len(self.soft_list) != 1:
            raise ValueError("Only one value for Software node can be "
                             "specified with name " + self.name)

    def _parse_input(self):
        '''Method to read the parameters from the DOC and place
           them into the local lists.
        '''
        self._publ = None
        self._origin = []
        self._mirror = []
        self._add_publ = []
        self._add_origin = []
        self._add_mirror = []

        self.logger.debug("Parsing the Data Object Cache")

        soft_node = self.soft_list[0]

        # Read the destination which for IPS involves reading the
        # image node. The image node contains the action, img_root,
        # and index. The image type node contains the completeness,
        # and zone info.
        dst_list = soft_node.get_children(Destination.DESTINATION_LABEL,
                                          Destination, not_found_is_err=True)
        dst_image = dst_list[0].get_children(Image.IMAGE_LABEL,
                                             Image, not_found_is_err=True)[0]
        self.dst = self._doc.str_replace_paths_refs(dst_image.img_root)

        self.img_action = dst_image.action
        self.index = dst_image.index

        im_type = dst_image.get_first_child(ImType.IMTYPE_LABEL, ImType)
        if im_type:
            self.completeness = im_type.completeness
            self.is_zone = bool(im_type.zone)
        else:
            self.completeness = "full"
            self.is_zone = False

        # Read properties to be set and put them into the properties
        # dictionary.
        prop_list = dst_image.get_children(Property.PROPERTY_LABEL,
                                           Property)
        for prop in prop_list:
            self.properties[prop.prop_name] = prop.val

        # Read the facets to be used in image creation and put them
        # into the facet dictionary.
        facet_list = dst_image.get_children(Facet.FACET_LABEL, Facet)
        for facet in facet_list:
            self.facets[facet.facet_name] = facet.val

        # Parse the Source node
        self._parse_src(soft_node)

        # Get the IPS Image creations Args from the DOC if they exist.
        img_arg_list = dst_image.get_children(Args.ARGS_LABEL, Args)

        # If arguments were specified, validate that the
        # user only specified them once, and that they
        # didn't specify arguments they're not allowed to.
        for args in img_arg_list:
            # ssl_key and ssl_cert are part of the image specification.
            # If the user has put them into the args that's an error
            # since we wouldn't know which one to use if they were
            # specified in both places.
            not_allowed = set(["ssl_key", "ssl_cert"])
            cur_img_args = set(args.arg_dict.keys())
            overlap = list(not_allowed & cur_img_args)
            if overlap:
                raise ValueError("The following components may be specified "
                                 "with the destination image of the manifest "
                                 "but are invalid as args: %s" % str(overlap))

            # Check that the current set of image args being processed
            # are not duplicates of one we've already processed.
            image_args = set(self.image_args.keys())
            overlap = list(image_args & cur_img_args)
            if overlap:
                raise ValueError("The following components are specified "
                                 "twice in the manifest: %s" % str(overlap))

            # Update the image args with the current image args being
            # processed.
            self.image_args.update(args.arg_dict)

        # Parse the transfer specific attributes.
        self._parse_transfer_node(soft_node)

    def _parse_transfer_node(self, soft_node):
        '''Parse the DOC for the attributes that are specific for each
           transfer specified. Create a list with the attributes for each
           transfer.
        '''
        # Get the list of transfers from this specific node in the DOC
        transfer_list = soft_node.get_children(class_type=IPSSpec)
        for trans in transfer_list:
            trans_attr = dict()
            trans_attr[ACTION] = trans.action
            trans_attr[CONTENTS] = trans.contents
            trans_attr[REJECT_LIST] = trans.reject_list
            trans_attr[PURGE_HISTORY] = trans.purge_history
            trans_attr[APP_CALLBACK] = trans.app_callback

            trans_args = trans.get_first_child(Args.ARGS_LABEL, Args)
            if trans_args:
                if not self.index:
                    trans_args.arg_dict[UPDATE_INDEX] = False
                trans_attr[IPS_ARGS] = trans_args.arg_dict
            else:
                if not self.index:
                    trans_arg_dict = {UPDATE_INDEX: False}
                    trans_attr[IPS_ARGS] = trans_arg_dict
                else:
                    trans_attr[IPS_ARGS] = None

            # Append the information found to the list of
            # transfers that will be performed
            if trans_attr not in self._transfer_list:
                self._transfer_list.append(trans_attr)

    def _set_publisher_info(self, pub, preferred=False):
        '''Set the preferred or additional publishers. Which publisher type to
           set is determined by the boolean, preferred.
        '''
        if preferred:
            self._publ = pub.publisher
            if pub.publisher:
                self.logger.debug("Primary Publisher Info: %s", pub.publisher)
            else:
                self.logger.debug("Primary Publisher Info:")
        else:
            self._add_publ.append(pub.publisher)
            if pub.publisher:
                self.logger.debug("Additional Publisher Info: %s",
                                  pub.publisher)
            else:
                self.logger.debug("Additional Publisher Info: ")

        origin_name = []
        origin_uris = []
        # Get the origins for this publisher. If one isn't specified,
        # use the default origin.
        origin_list = pub.get_children(Origin.ORIGIN_LABEL, Origin)
        if origin_list:
            for origin in origin_list:
                if preferred:
                    or_repo = origin.origin
                else:
                    or_repo = publisher.RepositoryURI(uri=origin.origin)
                origin_name.append(or_repo)
                origin_uris.append(origin.origin)
                self.logger.debug("    Origin Info: %s", origin.origin)
        else:
            origin_name = self.DEF_REPO_URI
            origin_uris.append(self.DEF_REPO_URI)

        # Get the mirrors for the publisher if they are specified.
        mirror_name = []
        mirror_uris = []
        mirror_list = pub.get_children(Mirror.MIRROR_LABEL, Mirror)
        for mirror in mirror_list:
            mirror_uris.append(mirror.mirror)
            if preferred:
                mir_repo = mirror.mirror
            else:
                mir_repo = publisher.RepositoryURI(uri=mirror.mirror)
            mirror_name.append(mir_repo)
            self.logger.debug("    Mirror Info: %s", mirror.mirror)

        if len(mirror_name) == 0:
            mirror_name = None

        if preferred:
            self._origin = origin_name
            self._mirror = mirror_name
        else:
            self._add_origin.append(origin_name)
            self._add_mirror.append(mirror_name)

        # set the publisher_list for this publisher, only if it's not already
        # been inserted.
        entry = (pub.publisher, origin_uris, mirror_uris)
        if entry not in self.publisher_list:
            self.publisher_list.append(entry)

    def _parse_src(self, soft_node):
        '''Parse the DOC Source, filling in the local attributes for
           _publ, _origin, _mirror, _add_publ, _add_origin, _add_mirror.
        '''
        self.logger.debug("Reading the IPS source")

        src_list = soft_node.get_children(Source.SOURCE_LABEL, Source)
        if len(src_list) > 1:
            raise ValueError("Only one IPS image source may be specified")

        if len(src_list) == 1:
            src = src_list[0]
            pub_list = src.get_children(Publisher.PUBLISHER_LABEL, Publisher,
                                        not_found_is_err=True)

            # If we're not installing a zone image, the first publisher is
            # treated as the preferred one (i.e. it's passed as arguments to
            # the image_create() call); for a zone, all publishers should
            # be processed as additional publishers since a zone image will
            # be created with the system repository already in place.
            if not self.is_zone:
                pub = pub_list.pop(0)
                self._set_publisher_info(pub, preferred=True)
            for pub in pub_list:
                self._set_publisher_info(pub, preferred=False)
        else:
            if self.img_action != self.EXISTING:
                # If the source isn't specified, use the defaults for create.
                # For a zone image, the system repo will already be set up
                # as the default repo so we don't need to set up a the default
                # here if source isn't specified.
                if not self.is_zone:
                    self._origin = [self.DEF_REPO_URI]
                    self.logger.debug("    Origin Info: %s", self.DEF_REPO_URI)
                    self._mirror = None

    def catalog_failures_to_str(self, cre):
        '''Convert a CatalogRefreshException into a formatted string.

           This is based on the IPS pkg/client.py display_catalog_failures()
           implementation.
        '''
        total = cre.total
        succeeded = cre.succeeded

        lines = list()
        lines.append("Error refreshing publishers, %s/%s "
                     "catalogs successfully updated:" %
                     (succeeded, total))

        for pub, err in cre.failed:
            lines.append("")
            lines.append(str(err))

        if cre.errmessage:
            lines.append(cre.errmessage)

        return "\n".join(lines)


class TransferIPSAttr(AbstractIPS):
    '''IPS Transfer class to take input from the attributes.'''
    def __init__(self, name):
        super(TransferIPSAttr, self).__init__(name)
        # Attributes per transfer
        self.action = None
        self.contents = None
        self.reject_list = None
        self.purge_history = False
        self.app_callback = None
        self.args = {}

        self._transfer_list = []

    def _parse_input(self):
        '''Parse the source and transfer specific attributes and put
           into local versions. The attributes to be parsed are:
           src (for publisher, origin, mirror), pkg_install, pkg_uninstall,
           purge_history, and args.
        '''
        self._publ = None
        self._origin = []
        self._mirror = []
        self._add_publ = []
        self._add_origin = []
        self._add_mirror = []
        trans_attr = dict()

        self.logger.debug("Reading the Source")
        if self.src:
            self._publ, self._origin, self._mirror = self.src[0]
            self.logger.debug("Source Info:")
            if self._publ:
                self.logger.debug("Primary Publisher name: %s",
                                  str(self._publ))

            for origin in self._origin:
                self.logger.debug("    Origin name: %s", str(origin))
            if self._mirror:
                for mirror in self._mirror:
                    self.logger.debug("    Mirror name: %s", str(mirror))

            for pub in self.src[1:]:
                pub_name, origin_lst, mirror_lst = pub
                if pub_name:
                    self.logger.debug("Additional publisher: %s",
                                       str(pub_name))
                origin_name = []
                if origin_lst:
                    for origin in origin_lst:
                        or_repo = publisher.RepositoryURI(uri=origin)
                        origin_name.append(or_repo)
                        self.logger.debug("    Origin name: %s", str(origin))
                else:
                    origin_name = [self.DEF_REPO_URI]
                    self.logger.debug("    Origin name: %s",
                                       str(self.DEF_REPO_URI))

                mirror_name = []
                if mirror_lst:
                    for mirror in mirror_lst:
                        mir_repo = publisher.RepositoryURI(uri=mirror)
                        mirror_name.append(mir_repo)
                        self.logger.debug("    Mirror name: %s", str(mirror))
                else:
                    mirror_name = None

                self._add_publ.append(pub_name)
                self._add_origin.append(origin_name)
                self._add_mirror.append(mirror_name)

        elif self.img_action != self.EXISTING:
            # The source isn't specified so use the default.
            self._origin = [self.DEF_REPO_URI]
            self.logger.debug("Origin name: %s", str(self.DEF_REPO_URI))
            self._mirror = None

        trans_attr[ACTION] = self.action
        trans_attr[CONTENTS] = self.contents
        trans_attr[REJECT_LIST] = self.reject_list
        trans_attr[PURGE_HISTORY] = self.purge_history
        trans_attr[APP_CALLBACK] = self.app_callback
        if not self.index:
            self.args[UPDATE_INDEX] = False
        trans_attr[IPS_ARGS] = self.args
        self._transfer_list.append(trans_attr)
