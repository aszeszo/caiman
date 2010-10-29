#
##
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''ManifestParser Checkpoint'''

import logging
from lxml import etree
import os

from solaris_install.data_object import ParsingError
from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.manifest import ManifestError, validate_manifest


class ManifestParser(AbstractCheckpoint):
    '''
        ManifestParser - parse, validate and import an XML manifest.


        Summary:
        This class implements the AbstractCheckpoint abstract base class
        which allows it to be executed from within the InstallEngine.
        It also provides an additional API that allow it to be run
        outside of the InstallEngine context.


        Initializer method:
        The parameters of the initializer method give the location
        of the XML manifest to be parsed and define what validation and
        other optional operations will be performed.


        execute() and parse() methods:
        When running in an InstallEngine context the execute() method
        performs the main tasks of parsing and, optionally, validating
        the manifest.

        When run outside the InstallEngine context, the parse() method
        performs these same functions.

        The main difference between execute() and parse() is whether or
        not the manifest data is imported into a DataObjectCache (DOC)
        instance and from where the reference to the DOC is obtained.
        execute() assumes an InstallEngine singleton exists and gets
        the DOC reference from it.  With parse(), importing to the DOC
        is optional and if required, a reference to an existing DOC
        instance must be passed in.

        If an error occurs during the execute() or parse() methods,
        including XML syntax errors or failure to validate the
        manifest, a ManifestError exception is raised.

        If no errors occur, the methods simply return, with no return
        value.  If importing to a DOC has been requested, the data
        will be available in the DOC for retrieval by other system
        components.


        Other public methods:
        The get_progress_estimate() method is required by the parent
        AbstractCheckpoint class.

        The cancel() method defined in AbstractCheckpoint is not
        overridden in ManifestParser.
    '''

    def __init__(self, name, manifest, validate_from_docinfo=None,
        dtd_file=None, load_defaults=True, call_xinclude=False):
        '''
            Class initializer method.

            Parameters:
            - name arg is required by AbstractCheckpoint.  Not used.
            - manifest must be the path to a readable XML file
            - validate_from_docinfo controls whether the manifest is
              validated against the DTD in the file's XML headers, if any.
              The default value is None.  This parameter can have 3 values:
              None: validate against the DTD, if present; if DTD URI is not
                present, no error is raised
              True: attempt to validate against the DTD on-the-fly as it is
                loaded.  If DTD is not specified, raise an error
              False: whether or not a DTD is specified, do not attempt to
                validate against it
              If validation is attempted and fails, an error is raised.
            - dtd_file specifes the path to a DTD against which the manifest
              will be validated.  This validation may be performed instead
              of, or as well as, the validation controlled by
              validate_from_docinfo, or it may be skipped by leaving dtd_file
              as None (the default).  If validation is attempted and fails,
              an error is raised.
              Note: default attribute values (see below) cannot be loaded
              during this form of validation - they can only be loaded if
              the manifest directly references a DTD in its headers.
            - load_defaults must be either True or False.  The default value
              is True.  load_defaults is only relevant when the manifest
              references a DTD.  If True, default attribute values from the
              DTD are loaded when the manifest is parsed.  If the manifest
              does not reference a DTD, no defaults are loaded and no error
              is raised.  (Note: Defaults can be loaded even if
              validate_from_docinfo is False.)
            - call_xinclude must be either True or False and controls
              whether XInclude statements in the manifest will be processed
              or not.  It defaults to False
              Note: Currently, the on-the-fly validation performed if
              validate_from_docinfo=True occurs *before* XInclude statements
              are processed and validation triggered when
              validate_from_docinfo=None or when dtd_file is specified occurs
              *after* XInclude processing.  XInclude processing may affect
              whether validation succeeds or not, so this ordering may need
              to be considered.

            Returns:
            - Nothing

            Raises:
            - ManifestError is raised if invalid values are specified
              for any paramaters or if manifest and/or dtd_file are
              specified but are not actual files
        '''

        super(ManifestParser, self).__init__(name)

        self.logger.debug("Initializing ManifestParser " \
            "(manifest=%s, validate_from_docinfo=%s, dtd_file=%s, " \
            "load_defaults=%s, call_xinclude=%s)",
            manifest, validate_from_docinfo, dtd_file,
            load_defaults, call_xinclude)

        # Check params

        if manifest is None:
            raise ManifestError("No manifest specified")
        if not os.path.isfile(manifest):
            raise ManifestError("Manifest [%s] is not a file" % manifest)
        self._manifest = manifest

        self._validate_from_docinfo = validate_from_docinfo

        if ((dtd_file is not None) and
            (not os.path.isfile(dtd_file))):
            raise ManifestError("DTD [%s] is not a file" % dtd_file)
        self._dtd_file = dtd_file

        self._load_defaults = load_defaults

        self._call_xinclude = call_xinclude


    def get_progress_estimate(self):
        '''
            The parent class requires that this method be implemented
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.
        '''

        return 1


    def parse(self, doc=None):
        '''
            This API method is not part of the AbstractCheckpoint spec.
            It can be used to access the ManifestParser functionality outside
            the InstallEngine context.

            This method is also used as a convenience function within this
            class to do most of the work of the execute() method.

            Parameters:
            - doc, a reference to the DataObjectCache in which to store
              the manifest data.  If None, the manifest data will not be
              stored anywhere, in which case this method only serves to
              confirm whether the manifest can be parsed and, optionally,
              validated.

            Returns:
            - Nothing
              On success, this method returns; on error it raises an exception.

            Raises:
            - ManifestError is raised if an error occurs in _load_manifest()
              or validate_manifest() or if
              DataObjectCache.import_from_manifest_xml() raises a ParsingError
              exception.
        '''

        self.logger.debug("ManifestParser.parse(doc=%s) called", doc)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        self.logger.debug("loading manifest (dtd_validation=%s)",
            self._validate_from_docinfo)
        tree = self._load_manifest(dtd_validation=self._validate_from_docinfo,
            attribute_defaults=self._load_defaults)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        if self._validate_from_docinfo is None:
            if ((tree.docinfo is not None) and
                (tree.docinfo.system_url is not None)):
                validate_manifest(tree, tree.docinfo.system_url, self.logger)

        if self._dtd_file is not None:
            validate_manifest(tree, self._dtd_file, self.logger)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        if doc is not None:
            # import the Manifest data into the Volatile sub-tree
            # of the DataObjectCache

            try:
                doc.import_from_manifest_xml(tree.getroot(), volatile=True)
            except ParsingError, error:
                msg = "Unable to import manifest into data_object_cache"
                self.logger.exception(msg)
                self.logger.exception(error)
                raise ManifestError(msg, orig_exception=error)


    def execute(self, dry_run=False):
        '''
            Abstract method defined in AbstractCheckpoint class.

            Loads the specified Manifest and does the requested validation.
            Imports resulting data into DOC.

            Parameters:
            - the dry_run keyword paramater, specified in AbstractCheckpoint,
              is ignored in this method.

            Returns:
            - Nothing
              On success, this method returns; on error it raises an exception.

            Raises:
            - ManifestError is raised if unable to fetch DOC reference or
              if an error occurs in parse().
        '''

        self.logger.debug("ManifestParser.execute(dry_run=%s) called", dry_run)

        engine = InstallEngine.get_instance()

        doc = engine.data_object_cache
        if doc is None:
            raise ManifestError("Cannot get DOC reference from InstallEngine")

        self.parse(doc=doc)


    def _load_manifest(self, dtd_validation=False, attribute_defaults=True):
        '''
            Loads the manifest contained in self._manifest.

            Parameters:
            - dtd_validation must be True or False.  Default is False.  If
              True, then the document will also be validated on-the-fly as
              it is loaded.
            - attribute_defaults must be True or False.  Default is True.
              Only relevant if the manifest references a DTD.  If True, then
              default values for XML attributes given in the DTD will be
              loaded as the document is parsed.

            Returns:
            - an etree.ElementTree object

            Raises:
            - ManifestError is raised if the manifest file cannot be
              accessed or if XMLSyntaxError is raised while parsing
              and, optionally, validating it.
        '''

        # Create the XML parser to be used when processing the manifest.
        parser = etree.XMLParser(remove_blank_text=True,
            dtd_validation=dtd_validation,
            attribute_defaults=attribute_defaults)

        try:
            tree = etree.parse(self._manifest, parser)
        except IOError, error:
            msg = "Cannot access Manifest file [%s]" % (self._manifest)
            self.logger.exception(msg)
            self.logger.exception(error)
            raise ManifestError(msg, orig_exception=error)
        except etree.XMLSyntaxError, error:
            msg = "XML syntax error in manifest [%s]" % \
                (self._manifest)
            self.logger.exception(msg)
            self.logger.exception(error)
            raise ManifestError(msg, orig_exception=error)

        if self._call_xinclude:
            tree.xinclude()

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("Parsed XML document:\n%s",
                etree.tostring(tree, pretty_print=True, method="xml"))

        return tree
