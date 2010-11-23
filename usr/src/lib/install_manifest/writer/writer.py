#!/usr/bin/python
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

'''ManifestWriter Checkpoint'''

import logging
from lxml import etree
import os
import tempfile

from solaris_install.engine import InstallEngine
from solaris_install.engine.checkpoint import AbstractCheckpoint
from solaris_install.manifest import ManifestError, validate_manifest


class ManifestWriter(AbstractCheckpoint):
    '''
        ManifestWriter - export, transform and validate an XML manifest.


        Summary:
        This class implements the AbstractCheckpoint abstract base class
        which allows it to be executed from within the InstallEngine.
        It also provides an additional API that allow it to be run
        outside of the InstallEngine context.


        Initializer method:
        The parameters of the initializer method give the location
        of the XML manifest to be created and define what transformation
        and validation will be performed.


        execute() and parse() methods:
        When running in an InstallEngine context the execute() method
        performs the main tasks of exporting and, optionally, transforming
        and validating the manifest.

        When run outside the InstallEngine context, the write() method
        performs these same functions.

        The main difference between execute() and write() is from where
        the DataObjectCache (DOC) reference is obtained.  execute()
        assumes an InstallEngine singleton exists and gets the DOC
        reference from it.  With write(), a reference to an existing DOC
        instance must be passed in.

        If an error occurs during the execute() or write() methods,
        including XML syntax errors or failure to validate the
        manifest, a ManifestError exception is raised.

        If no errors occur, the methods simply return, with no return
        value.  The output manifest file will be created as requested.


        Other public methods:
        The get_progress_estimate() method is required by the parent
        AbstractCheckpoint class.

        The cancel() method defined in AbstractCheckpoint is not
        overridden in ManifestParser.
    '''

    def __init__(self, name, manifest, xslt_file=None,
        validate_from_docinfo=False, dtd_file=None):
        '''
            Class initializer method.

            Parameters:
            - name arg is required by AbstractCheckpoint. Not used.
            - manifest must be the path to a writable XML file
            - xslt_file defaults to None.  Otherwise, it must be the
              path to a readable XSLT file which will be applied to
              the manifest XML data to transform it into the required
              format.  Typically, this is used to structure the data
              according to the AI or DC schema.
            - validate_from_docinfo defaults to False.  It is only
              relevant if, following XSL Transformation, the XML document
              contains a reference to a DTD.  This will typically have
              been added by the XSLT file.  If validate_from_docinfo is
              True, the XML document will be validated against its
              referenced DTD, if present.  If validation fails, an
              error is raised.  If validate_from_docinfo is False or
              no DTD is referenced, this validation is skipped.
            - dtd_file defaults to None.  Otherwise, it must be the
              path to a DTD file against which the manifest XML will be
              validated before it is written out.  If validation is
              attempted and fails, an error is raised.  This validation
              is separate from that controlled by validate_from_docinfo.

            Returns:
            - Nothing

            Raises:
            - ManifestError is raised if invalid values are specified
              for any paramaters or if xslt_file or dtd_file are specified
              but do not exist.
        '''

        super(ManifestWriter, self).__init__(name)

        self.logger.debug("Initializing ManifestWriter " \
            "(manifest=%s, xslt_file=%s, " \
            "validate_from_docinfo=%s, dtd_file=%s)",
            manifest, xslt_file,
            validate_from_docinfo, dtd_file)

        # Check and store params

        self._manifest = manifest

        if ((xslt_file is not None) and
            (not os.path.isfile(xslt_file))):
            raise ManifestError("XSLT file [%s] is not a file" % xslt_file)
        self._xslt_file = xslt_file

        self._validate_from_docinfo = validate_from_docinfo

        if ((dtd_file is not None) and
            (not os.path.isfile(dtd_file))):
            raise ManifestError("DTD [%s] is not a file" % dtd_file)
        self._dtd_file = dtd_file


    def get_progress_estimate(self):
        '''
            The parent class requires that this method be implemented
            in sub-classes.

            This returns an estimate of how long the execute() method
            will take to run.
        '''

        return 1


    def write(self, doc):
        '''
            This API method is not part of the AbstractCheckpoint spec.
            It can be used to access the ManifestParser functionality outside
            the InstallEngine context.

            This method is also used as a convenience function within this
            class to do most of the work of the execute() method.

            Parameters:
            - doc, a reference to the DataObjectCache instance from which to
              export the manifest data.

            Returns:
            - Nothing
              On success, this method returns; on error it raises an exception.

            Raises:
            ManifestError is raised if:
            - xslt_file cannot be read or is not a valid XSLT file
            - output file cannot be created or written to
            or if validate_manifest raises an error.
        '''

        self.logger.debug("ManifestWriter.write(doc=%s) called", doc)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        # Get XML data from DOC.  This always returns something
        xml = doc.generate_xml_manifest()

        tree = etree.ElementTree(xml)
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("XML returned from DOC:\n%s\n",
                etree.tostring(tree, pretty_print=True))

        if self._xslt_file is not None:
            # Perform the requested XSL Transform on the XML data
            try:
                xslt_doc = etree.parse(self._xslt_file)
            except IOError, error:
                msg = "Cannot access XSLT file [%s]" % (self._xslt_file)
                self.logger.exception(msg)
                self.logger.exception(error)
                raise ManifestError(msg, orig_exception=error)
            except etree.XMLSyntaxError, error:
                msg = "XML syntax error in XSLT file [%s]" % \
                    (self._xslt_file)
                self.logger.exception(msg)
                self.logger.exception(error)
                raise ManifestError(msg, orig_exception=error)

            transform = etree.XSLT(xslt_doc)

            tree = transform(tree)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        if self._validate_from_docinfo:
            # Validate against the DTD referenced in the headers, if any
            if ((tree.docinfo is not None) and
                (tree.docinfo.system_url is not None)):
                validate_manifest(tree, tree.docinfo.system_url, self.logger)

        if self._dtd_file is not None:
            # Validate against the DTD file passed into the constructor
            validate_manifest(tree, self._dtd_file, self.logger)

        text = etree.tostring(tree, pretty_print=True)

        if self._cancel_requested.is_set():
            self.logger.debug("Cancel requested, returning.")
            return

        self.logger.debug("About to write out:\n%s\n", text)

        # Write to output file
        manifest_file = None
        try:
            manifest_file = open(self._manifest, mode='w')
            manifest_file.write(text)
        except IOError, error:
            msg = "Cannot write to output Manifest [%s]" % (self._manifest)
            self.logger.exception(msg)
            self.logger.exception(error)
            raise ManifestError(msg, orig_exception=error)
        finally:
            if manifest_file is not None:
                manifest_file.close()


    def execute(self, dry_run=False):
        '''
            Abstract method defined in AbstractCheckpoint class.

            Exports data from InstallEngine's DataObjectCache to the
            file named in self._manifest.

            Parameters:
            - dry_run is used to control what actions are taken if
              self._manifest already exists.  If dry_run is False, the
              file will be overwritten if it exists.  if dry_run is
              True, the output will be written to a similarly-named,
              but non-existing file.

            Returns:
            - Nothing
              On success, this method returns; on error it raises an exception.

            Raises:
            - ManifestError is raised if unable to fetch DOC reference or
              if an error occurs in write().
        '''

        self.logger.debug("ManifestWriter.execute(dry_run=%s) called", dry_run)

        engine = InstallEngine.get_instance()

        doc = engine.data_object_cache
        if doc is None:
            raise ManifestError("Cannot get DOC reference from InstallEngine")

        if dry_run and os.path.exists(self._manifest):
            self._manifest = _create_unique_variant(self._manifest)

        self.write(doc)


def _create_unique_variant(orig_filename):
    '''
        Create a variant of the passed-in filename, which does not already
        exist.  This uses the tempfile module to create a file whose name
        is based on orig_filename but with some random letters and numbers
        inserted.
    '''

    dirname, filename = os.path.split(orig_filename)
    prefix, suffix = os.path.splitext(filename)

    file_desc, new_filename = \
        tempfile.mkstemp(suffix=suffix, prefix=prefix+"_", dir=dirname)

    try:
        os.close(file_desc)
    except IOError:
        raise ManifestError("Could not close temp file [%s]" % new_filename)

    return new_filename
