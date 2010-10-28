#!/usr/bin/python2.6
#
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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#

'''Some convenience functions that can be used by other test suites that use
   the engine in their testing
'''

import os
import logging
import solaris_install.engine as engine

from solaris_install.logger import InstallLogger

DEBUG_ENGINE = (os.environ.get("DEBUG_ENGINE", "false").lower() == "true")

def get_new_engine_instance(doc_in_tmp=True):
    '''Returns a new install engine instance.  If an existing instance exists,
       it will be cleaned up.
    '''

    reset_engine()
        
    engine.InstallEngine._instance = None

    new_engine = engine.InstallEngine()

    new_engine.debug = DEBUG_ENGINE

    if doc_in_tmp:
        # Run tests with /tmp as directory for DOC snapshots so
        # they do not have to be run as root
        tmp_doc_snapshot_path = ("/tmp/engine_test_doc_path_%s") % os.getpid()
        os.environ[new_engine.TMP_CACHE_ENV] = tmp_doc_snapshot_path

    return (new_engine)

def reset_engine(old_engine=None):

    ''' Clean up the engine for the tests ''' 

    try:
        if old_engine is None:
            old_engine = engine.InstallEngine.get_instance()
        # Force all content of the DOC to be cleared.
        old_engine.data_object_cache.clear()

        if old_engine._tmp_cache_path is not None:
            shutil.rmtree(old_engine._tmp_cache_path, ignore_errors=True)
        old_engine._tmp_cache_path = None
    except:
        pass

    engine.InstallEngine._instance = None

    logging.Logger.manager.loggerDict = {}

    InstallLogger.DEFAULTFILEHANDLER = None
