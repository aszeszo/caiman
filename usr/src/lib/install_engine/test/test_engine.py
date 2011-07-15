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
# Copyright (c) 2010, 2011, Oracle and/or its affiliates. All rights reserved.
#

'''Some unit tests to cover engine functionality'''

import logging
import os
import sys
import shutil
import threading
import unittest
import warnings

from itertools import izip
from logging import ERROR, DEBUG

import solaris_install.engine as engine
import solaris_install.engine.checkpoint_data as checkpoint_data
import osol_install.errsvc as errsvc
import osol_install.liberrsvc as liberrsvc

from empty_checkpoint import EmptyCheckpoint
from solaris_install.engine.test.engine_test_utils import reset_engine, \
    get_new_engine_instance
from solaris_install.data_object import DataObject

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_THIS_DIR)

class MockDataset(object):

    ''' Fake Dataset object so the real ZFS dataset object does
        not need to be used for testing
    '''
    
    def __init__(self, path):
        self.exists = True
        self.mountpoint = path
        self.snapped = (None, None)
        self.snapshot_list = []
    
    def snapshot(self, name, overwrite=False):
        self.snapped = (name, overwrite)
    
    def snapname(self, name):
        return self.mountpoint + '@' + name
    
    def rollback(self, name, recursive=True):
        pass

    def get(self, property):
        return getattr(self, property)

class MockDOC(object):

    ''' Fake DOC object so the real DataObjectCache object we do not rely
        on the actual DataObjectCache class for testing.
    '''
    
    def take_snapshot(self, dummy):
        self.snapshotted = dummy

    def insert_children(self, dummy):
        pass
    
    @property
    def persistent(self):
        return self
    
    def get_first_child(self, name=None):
        return self

    def clear(self):
        pass
    
    def load_from_snapshot(self, filename):
        self.loaded_from = filename

class MockCheckpointRegData(DataObject):

    ''' Fake CheckpointRegData object so we do not rely on the actual
        CheckpointRegData object for testing
    '''

    def __init__(self):
        DataObject.__init__(self, "MokeCheckpointRegData")

    def to_xml(self):
        return None

    def from_xml(cls, xml_node):
        return None

    def can_handle(cls, xml_node):
        return False

class MockCheckpointData(object):
    ''' Fake CheckpointData object so we do not rely on the actual
        CheckpointData object for testing
    '''
    def __init__(self):
        self.cp_info = MockCheckpointRegData()
        self.name = "MockCheckpointData"
        self.prog_reported = 0
        self.prog_est_ratio = 0
    
class EngineTest(unittest.TestCase):

    ''' Tests that validates the interfaces in the install engine code.
        All tests here do not require a user to be
        root to execute.
    '''
    
    def setUp(self):
        self.callback_results = (None, None)
        self.callback_executed = threading.Event()

        self.engine = get_new_engine_instance()
       
    def tearDown(self):

        # Force spawning of fresh singleton for each test.
        reset_engine(self.engine)
        self.engine = None

        self.callback_results = None
        self.callback_executed = None
    
    def _exec_cp_callback(self, status, errsvc):
        ''' Callback function for none-block execute_checkpoints() tests '''

        self.callback_results = (status, errsvc)
        self.callback_executed.set()

    def create_fake_cache_snapshots(self):
        ''' Create a few fake DOC snapshots in /tmp '''
        cp_names = ["cp_one", "cp_two", "cp_three", "cp_four"]
        self.full_cp_names = []

        # create a tmp directory for it
        self.cache_dir_name = ("/tmp/list_doc_snapshot_test_%s") % os.getpid()
        os.mkdir(self.cache_dir_name)

        for cp in cp_names:
            file_name = os.path.join(self.cache_dir_name, 
                           engine.InstallEngine.CACHE_FILE_NAME_PREFIX + cp)
            shutil.copyfile("/etc/hosts", file_name)
            self.full_cp_names.append(file_name)

    def destroy_fake_cache_snapshots(self):
        ''' Destroyes the fake DOC snapshots in /tmp used for testing '''
        shutil.rmtree(self.cache_dir_name)

class SimpleEngineTests(EngineTest):
    '''Tests the less complicated engine functionality'''
    
    def test_engine_is_singleton(self):
        engine.InstallEngine._instance = None
        
        self.assertRaises(engine.SingletonError,
                          engine.InstallEngine.get_instance)
        
        install_engine = engine.InstallEngine()
        self.assertTrue(isinstance(install_engine, engine.InstallEngine))
        
        self.assertRaises(engine.SingletonError, engine.InstallEngine)
        
        engine_instance = engine.InstallEngine.get_instance()
        self.assertTrue(install_engine is engine_instance)
    
    def test_check_callback_None(self):
        '''Assert InstallEngine._check_callback accepts None '''
        try:
            self.engine._check_callback(None)
        except TypeError:
            self.fail("Engine did not accept 'None' for callback")
    
    def test_check_callback_varargs(self):
        '''Assert InstallEngine._check_callback accepts a vararg function'''
        def vararg_func(*args):
            pass
        
        try:
            self.engine._check_callback(vararg_func)
        except TypeError:
            self.fail("Engine did not accept function with *args param")
    
    def test_check_callback_two_args(self):
        '''Assert InstallEngine._check_callback accepts a two argument function'''
        def arg_func(arg1, arg2):
            pass
        
        try:
            self.engine._check_callback(arg_func)
        except TypeError:
            self.fail("Engine did not accept function with exactly two args")
    
    def test_check_callback_under_two_args(self):
        '''Asserts InstallEngine._check_callback fails on a single argument function'''
        def arg_func(arg1):
            pass
        
        self.assertRaises(TypeError, self.engine._check_callback, arg_func)
    
    def test_check_callback_over_two_required_args(self):
        '''Asserts InstallEngine._check_callback fails if 3 or more args are required'''
        def arg_func(arg1, arg2, arg3):
            pass
        
        self.assertRaises(TypeError, self.engine._check_callback, arg_func)
    
    def test_check_callback_with_kwargs(self):
        '''Asserts InstallEngine._check_callback handles functions with keyword args'''
        def kwarg_func_all(arg1=None, arg2=None, arg3=None):
            pass
        
        try:
            self.engine._check_callback(kwarg_func_all)
        except TypeError:
            self.fail("Engine did not accept function with kwargs for all"
                      "arguments")
    
    def test_check_callback_2_arg_optional_kwarg(self):
        '''Asserts InstallEngine._check_callback handles a function with an optional keyword argument'''
        def optional_kwarg(arg1, arg2, arg3=None):
            pass
        
        try:
            self.engine._check_callback(optional_kwarg)
        except TypeError:
            self.fail("Engine did not accept function with optional kwarg")
    
    def test_check_callback_bound_class_method(self):
        '''Asserts InstallEngine._check_callback handles bound class methods'''
        class DummyClass(object):
            def callback(self, status, errsvc):
                pass
        
        instance = DummyClass()
        
        try:
            self.engine._check_callback(instance.callback)
        except TypeError:
            self.fail("Engine did not accept bound class method")
    
    def test_check_callback_unbound_class_method(self):
        '''Asserts InstallEngine._check_callback rejects unbound class methods.
        (Unbound methods require a class instance as the first argument)'''
        class DummyClass(object):
            def callback(self, status, errsvc):
                pass
        
        self.assertRaises(TypeError, self.engine._check_callback,
                          DummyClass.callback)

    def test_snapshot_tmp_no_dataset(self):
        self.engine._dataset = None
        self.engine.data_object_cache = MockDOC()
        
        cp_data = MockCheckpointData()
        
        self.engine.snapshot(cp_data=cp_data)
        
        self.assertEqual(cp_data.zfs_snap, None)
        self.assertEqual(self.engine.doc.snapshotted,
                         cp_data.data_cache_path,
                         "DOC path for Checkpoint not set")
    
    def test_snapshot_tmp_dataset_no_exist(self):
        ds = MockDataset("mock")
        self.engine._dataset = ds
        self.engine.dataset.exists = False
        self.engine.data_object_cache = MockDOC()
        
        cp_data = MockCheckpointData()
        
        self.engine.snapshot(cp_data=cp_data)
        
        self.assertEqual(cp_data.zfs_snap, None)
        self.assertEqual(self.engine.doc.snapshotted,
                         cp_data.data_cache_path,
                         "DOC path for Checkpoint not set")
    
    def test_snapshot_zfs_dataset_exists(self):
        ds = MockDataset("mock")
        self.engine._dataset = ds
        self.engine.dataset.exists = True
        self.engine.data_object_cache = MockDOC()
        
        cp_data = MockCheckpointData()
        
        self.engine.snapshot(cp_data=cp_data)
        
        self.assertEqual(cp_data.zfs_snap, ds.snapped[0])
        self.assertEqual(self.engine.doc.snapshotted,
                         cp_data.data_cache_path,
                         "DOC path for Checkpoint not set")


class EngineCheckpointsBase(EngineTest):
    
    def setUp(self):
        EngineTest.setUp(self)
        
        if _THIS_DIR == ".":
            self.cp_data_args = ("empty_checkpoint", "EmptyCheckpoint")
            self.failed_cp_data_args = ("empty_checkpoint",
                                        "FailureEmptyCheckpoint")
        else:
            self.cp_data_args = (_THIS_DIR + "/empty_checkpoint",
                                 "EmptyCheckpoint")
            self.failed_cp_data_args = (_THIS_DIR + "/empty_checkpoint",
                                        "FailureEmptyCheckpoint")

        if _THIS_DIR.startswith("/"):
            self.expected_mod_name = "empty_checkpoint"
            self.expected_mod_path = _THIS_DIR
        else:
            self.expected_mod_name = self.cp_data_args[0]
            self.expected_mod_path = None

        self.name_list = ["one", "two", "three", "four", "five"]
        
        # Squelch the logging during checkpoint registration
        # (it clutters the test output)
        level = engine.LOGGER.level
        engine.LOGGER.level = 100
        for name in self.name_list:
            self.engine.register_checkpoint(name, *self.cp_data_args)
        engine.LOGGER.level = level
    
    def tearDown(self):
        EngineTest.tearDown(self)


class EngineCheckpointsTest(EngineCheckpointsBase):
    '''More complicated InstallEngine tests requiring DOC, checkpoints, etc.'''
    
    def test_register_checkpoint(self):
        
        self.assertEquals(len(self.name_list), len(self.engine._checkpoints))
        for cp_data in self.engine._checkpoints:
            self.assertEquals(cp_data.cp_info.mod_name, self.expected_mod_name,
                              "Module name: Expected '%s', got '%s'" %
                              (self.expected_mod_name, cp_data.cp_info.mod_name))
            self.assertEquals(cp_data.cp_info.module_path, self.expected_mod_path,
                              "Module path: Expected '%s', got '%s'" %
                              (self.expected_mod_path, cp_data.cp_info.module_path))
    
    def test_register_duplicate_checkpoint(self):
        '''Assert cannot register two checkpoints with the same name'''
        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint,
                          self.name_list[1], *self.cp_data_args)
    
    def test_get_full_checkpoint_list(self):
        '''InstallEngine.get_exec_list - Default args (full list)'''
        
        exec_list = self.engine.get_exec_list()
        
        self.assertEquals(len(self.name_list), len(exec_list))
        
        for exec_cp, cp_name in zip(exec_list, self.name_list):
            self.assertEquals(exec_cp.name, cp_name, "Exec list returned "
                            "checkpoints out of order")
    
    def test_get_cp_list_pause_before(self):
        '''InstallEngine.get_exec_list - pause_before arg works'''
        stop_at = 2
        
        exec_list = self.engine.get_exec_list(pause_before=self.name_list[stop_at])
        
        self.assertEquals(len(self.name_list[:stop_at]), len(exec_list))
        
        for exec_cp, cp_name in zip(exec_list, self.name_list):
            self.assertEquals(exec_cp.name, cp_name, "Exec list returned "
                            "checkpoints out of order")
    
    def test_get_cp_list_resume_from(self):
        '''InstallEngine.get_exec_list - resume_from arg works'''
        
        for cp_data in self.engine._checkpoints:
            cp_data.completed = True
        
        resume_from = 1
        
        exec_list = self.engine.get_exec_list(start_from=self.name_list[resume_from])
        
        self.assertEquals(len(self.name_list[resume_from:]), len(exec_list))
        
        for exec_cp, cp_name in zip(exec_list, self.name_list[resume_from:]):
            self.assertEquals(exec_cp.name, cp_name, "Exec list returned "
                            "checkpoints out of order")
    
    def test_get_cp_list_pause_before_resume(self):
        '''InstallEngine.get_exec_list - Error when pause_before cp is before the start_from cp in sequence'''
        
        for cp_data in self.engine._checkpoints:
            cp_data.completed = True
        
        resume_from = 2
        pause_before = 1
        
        self.assertRaises(engine.UsageError,
                          self.engine.get_exec_list, start_from=self.name_list[resume_from],
                          pause_before=self.name_list[pause_before])
    
    def test_get_cp_list_resume_prev_cp_not_complete(self):
        '''InstallEngine.get_exec_list - Error when prior cp's not complete'''
        resume_from = 1
        
        self.assertRaises(engine.UsageError,
                          self.engine.get_exec_list, start_from=self.name_list[resume_from])
    
    def test_resume_from_last_complete(self):
        '''InstallEngine.get_exec_list - Verify correct exec list is returned when some checkpoints are completed '''
        
        self.engine._checkpoints[0].completed = True
        
        first_inc = self.engine.get_first_incomplete()
        
        self.assertTrue(first_inc is self.engine._checkpoints[1])
        
        exec_list = self.engine.get_exec_list(start_from=None)
        
        self.assertFalse(self.engine._checkpoints[0] in exec_list)
    
    def test_resume_from_last_none_complete(self):
        '''InstallEngine.get_exec_list - Verify when none of the checkpoints are complete'''
        
        first_inc = self.engine.get_first_incomplete()
        
        self.assertTrue(first_inc is self.engine._checkpoints[0])
        
        exec_list = self.engine.get_exec_list()
        self.assertEquals(len(self.name_list), len(exec_list))
        for exec_cp, cp_name in zip(exec_list, self.name_list):
            self.assertEquals(exec_cp.name, cp_name, "Exec list returned "
                              "checkpoints out of order")
    
    def test_resume_from_last_all_complete(self):
        '''InstallEngine.get_exec_list - Verify nothing is returned when all cp's complete'''
        for cp_data in self.engine._checkpoints:
            cp_data.completed = True
        first_inc = self.engine.get_first_incomplete()
        self.assertTrue(first_inc is None)
        
        exec_list = self.engine.get_exec_list()
        self.assertEquals(0, len(exec_list))
    
    def test_get_cp_list_resume_no_exist(self):
        '''InstallEngine.get_exec_list - Verify UsageError on nonexistent start_from cp'''
        
        self.assertRaises(engine.UsageError,
                          self.engine.get_exec_list, start_from="NOEXIST")
    
    def test_get_cp_list_pause_before_no_exist(self):
        '''InstallEngine.get_exec_list - Verify UsageError on nonexistent pause_before cp'''
        self.assertRaises(engine.UsageError,
                          self.engine.get_exec_list, pause_before="NOEXIST")
    
    def test_get_cache_filename_no_dataset(self):
        self.engine.dataset = None
        path = self.engine.get_cache_filename("cp")
        self.assertEquals(path, os.path.join(self.engine._tmp_cache_path,
                                             ".data_cache.cp"))
    
    def test_get_cache_filename_dataset(self):
        self.engine._tmp_cache_path = "/a/b/c"
        dataset = MockDataset(self.engine._tmp_cache_path)
        self.engine._dataset = dataset
        path = self.engine.get_cache_filename("cp")
        self.assertEquals(path, os.path.join(dataset.mountpoint,
                                             ".data_cache.cp"))
        self.engine._tmp_cache_path = None
    
    def test_get_cache_filename_dataset_no_exist(self):
        self.engine._tmp_cache_path = "/x/y/z"
        dataset = MockDataset(self.engine._tmp_cache_path)
        dataset.exists = False
        dataset.mountpoint = "/a/b/c"
        self.engine._dataset = dataset
        path = self.engine.get_cache_filename("cp")
        self.assertNotEquals(path, os.path.join(dataset.mountpoint,
                                                ".data_cache.cp"))
        expected = os.path.join(self.engine._tmp_cache_path, ".data_cache.cp")
        self.assertEquals(path, expected)
        self.engine._tmp_cache_path = None
    
    def test_rollback_in_process_no_zfs(self):
        '''Assert in process rollbacks w/o ZFS function'''
        cp = self.engine._checkpoints[0]
        cp.completed = True
        cp.data_cache_path = "/dev/null"
        self.engine.data_object_cache = MockDOC()
        
        self.engine._rollback(cp.name)
        
        for cp in self.engine._checkpoints:
            self.assertFalse(cp.completed)
    
    def test_out_process_rollback(self):
        cp = self.engine._checkpoints[0]
        cp.completed = False
        cp_doc = self.engine.get_cache_filename(cp.name)
        with open(cp_doc, "w") as tmp_file:
            tmp_file.write("")
        ds = MockDataset(os.path.dirname(cp_doc))
        self.engine._dataset = ds
        self.engine.data_object_cache = MockDOC()
        ds.snapshot_list.append(ds.mountpoint + "@.step_" + cp.name)
        self.engine._rollback(cp.name)
        
        for cp in self.engine._checkpoints:
            self.assertFalse(cp.completed)
    
    def test_in_process_rollback_cache_no_exist(self):
        '''Test that rollbacks fail when the cache doesn't exist'''
        cp = self.engine._checkpoints[0]
        cp.completed = True
        cp.data_cache_path = os.tempnam() # Guaranteed to not exist yet
        self.engine.data_object_cache = MockDOC()
        
        self.assertRaises(engine.NoCacheError, self.engine._rollback, cp.name)
    
    def test_out_process_rollback_cache_no_exist(self):
        cp = self.engine._checkpoints[0]
        cp.completed = False
        ds = MockDataset(os.tempnam())
        self.engine._dataset = ds
        ds.snapshot_list.append(ds.mountpoint + "@.step_" + cp.name)
        self.engine.data_object_cache = MockDOC()
        
        self.assertRaises(engine.NoCacheError, self.engine._rollback, cp.name)
    
    def test_out_process_rollback_no_dataset(self):
        cp = self.engine._checkpoints[0]
        cp.completed = False
        self.engine._dataset = None
        self.engine.data_object_cache = MockDOC()
        
        self.assertRaises(engine.RollbackError, self.engine._rollback,
                          cp.name)
    
    def test_out_process_rollback_no_snapshot(self):
        cp = self.engine._checkpoints[0]
        cp.completed = False
        self.engine._dataset = MockDataset(os.tempnam())
        self.engine.data_object_cache = MockDOC()
        
        self.assertRaises(engine.RollbackError, self.engine._rollback,
                          cp.name)


class EngineExecuteTests(EngineCheckpointsBase):
    '''Test InstallEngine.execute_checkpoints(...) scenarios'''
    
    def setUp(self):
        EngineCheckpointsBase.setUp(self)
        self.engine.data_object_cache = MockDOC()
        errsvc.clear_error_list()

    def check_expected_failures(self, expected_failure, status,
                                failed_checkpoints):

        self.assertEquals(status, self.engine.EXEC_FAILED)

        self.assertEqual(len(expected_failure), len(failed_checkpoints))

        for (exp_name, failed_name) in (izip(expected_failure,
                                             failed_checkpoints)):
            self.assertEqual(exp_name, failed_name)

        for failed_name in failed_checkpoints:
            err_data_list = errsvc.get_errors_by_mod_id(failed_name)
            self.assertEqual(1, len(err_data_list))
            err_data = err_data_list[0]
            self.assertTrue(isinstance(err_data.error_data[liberrsvc.ES_DATA_EXCEPTION], RuntimeError))

    def test_execute_checkpoints_basic(self):
        '''Runs InstallEngine._execute_checkpoints with empty checkpoints'''
        
        # Remove the dependency on CheckpointData objects
        self.engine.get_cp_data = lambda x: MockCheckpointData()
        checkpoints = [EmptyCheckpoint("one")]
        
        self.engine._execute_checkpoints(checkpoints, True,
                                         self._exec_cp_callback)
        
        status, failed_checkpoints = self.callback_results
        self.assertEqual(status, engine.InstallEngine.EXEC_SUCCESS,
                         "Execution reported non-success")
        # failed_checkpoints should be None or an empty list,
        # which evaluate to False in a boolean context
        self.assertFalse(failed_checkpoints,
                         "Execution call encountered errors")
    
    def test_blocking_execute(self):
        '''Run InstallEngine.execute_checkpoints in a blocking fashion (all cp's run)'''
        status, failed_checkpoints = self.engine.execute_checkpoints(dry_run=True)
        
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.assertEqual(0, len(failed_checkpoints))
        
        # All checkpoints should be completed
        self.assertEqual(self.engine.get_first_incomplete(), None)
        
        self.assertEqual(self.engine.checkpoint_thread, None)
    
    def test_non_blocking_execute(self):
        '''Run InstallEngine.execute_checkpoints in a non-blocking fashion (all cp's run)'''
        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)
        
        # Empty checkpoints shouldn't take long - if they do, something's wrong
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")
        self.engine.checkpoint_thread.join(10)
        
        self.assertEquals(self.callback_results[0], self.engine.EXEC_SUCCESS,
                          "Engine returned non-success")
        self.assertEqual(0, len(self.callback_results[1]))
        
        # All checkpoints should be completed
        self.assertTrue(self.engine.get_first_incomplete() is None,
                        "Not all checkpoints completed!")
        
        self.assertFalse(self.engine.checkpoint_thread.is_alive(),
                         "Checkpoint thread still running")
    
    def test_in_process_continue(self):
        '''Run a few checkpoints, then run the rest'''
        pause_before = self.name_list[2]
        status, failed_checkpoints = self.engine.execute_checkpoints(
                                         pause_before=pause_before,
                                         dry_run=True)
        
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.assertEqual(0, len(failed_checkpoints))
        
        # First incomplete checkpoint should be 'pause_before'
        self.assertEquals(self.engine.get_first_incomplete().name,
                          pause_before,
                          "Engine didn't pause at correct checkpoint")
        
        self.assertEqual(self.engine.checkpoint_thread, None)
        
        status, failed_checkpoints = self.engine.execute_checkpoints(
                                         start_from=pause_before,
                                         dry_run=True)
        
        self.assertEquals(status, self.engine.EXEC_SUCCESS,
                          "Engine returned non-success")
        self.assertEqual(0, len(failed_checkpoints))
        
        # All checkpoints should be completed now
        self.assertTrue(self.engine.get_first_incomplete() is None,
                        "Not all checkpoints completed")
        
        self.assertEqual(self.engine.checkpoint_thread, None)

    def test_blocking_cp_init_failed(self):
        '''Failed to initalize a checkpoint in InstallEngine.execute_checkpoints, blocking mode '''

        # Add the checkpoint that will fail to beginning of list
        failed_chkpt_name = "fail_init_1"
        self.engine.register_checkpoint(failed_chkpt_name, "empty_checkpoint",
                                        "InitFailureEmptyCheckpoint")

        status, failed_checkpoints = self.engine.execute_checkpoints(
                                                                   dry_run=True)
        self.assertEquals(status, self.engine.CP_INIT_FAILED)
        self.assertEqual(len(failed_checkpoints), 1)
        self.assertEqual(failed_checkpoints[0], failed_chkpt_name)

        # Make sure the execute thread is not created
        self.assertEqual(self.engine.checkpoint_thread, None)

    def test_non_blocking_cp_init_failed(self):
        '''Failed to inistalize a checkpoint in InstallEngine.execute_checkpoints non-blocking mode '''

        # Add the checkpoint that will fail to beginning of list
        failed_chkpt_name = "fail_init_1"
        self.engine.register_checkpoint(failed_chkpt_name, "empty_checkpoint",
                                        "InitFailureEmptyCheckpoint")

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)
        
        # Empty checkpoints shouldn't take long - if they do, something's wrong
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")

        self.assertEquals(self.callback_results[0], self.engine.CP_INIT_FAILED)
        self.assertEqual(len(self.callback_results[1]), 1)
        self.assertEqual((self.callback_results[1])[0], failed_chkpt_name)

        # Make sure the execute thread is not created
        self.assertEquals(self.engine.checkpoint_thread, None)

    def test_blocking_execute_first_cp_failed(self):
        '''First checkpoint failed in InstallEngine.execute_checkpoints, blocking mode '''

        # Add the checkpoint that will fail to beginning of list
        failed_chkpt_name = "fail1"
        self.engine.register_checkpoint(failed_chkpt_name,
                                        *self.failed_cp_data_args,
                                        insert_before="one")

        status, failed_checkpoints = self.engine.execute_checkpoints(
                                                                   dry_run=True)

        self.check_expected_failures([failed_chkpt_name], status,
                                     failed_checkpoints)
        
        # Make sure the first incomplete checkpoint is the failed checkpoint.
        cp = self.engine.get_first_incomplete()
        self.assertEqual(cp.name, failed_chkpt_name)
        
        self.assertEqual(self.engine.checkpoint_thread, None)

    def test_blocking_execute_middle_cp_failed(self):
        '''Checkpoint in middle of list failed in InstallEngine.execute_checkpoints blocking mode '''

        # Add the checkpoint that will fail to middle of list
        failed_chkpt_name = "fail1"
        self.engine.register_checkpoint(failed_chkpt_name,
                                        *self.failed_cp_data_args,
                                        insert_before="four")

        status, failed = self.engine.execute_checkpoints(dry_run=True)
        
        self.check_expected_failures([failed_chkpt_name], status, failed)
        
        # Make sure the incomplete checkpoint is the failed checkpoint.
        cp = self.engine.get_first_incomplete()
        self.assertEqual(cp.name, failed_chkpt_name)
        
        self.assertEqual(self.engine.checkpoint_thread, None)
    
    def test_non_blocking_execute_first_cp_failed(self):
        '''First checkpoint failed in InstallEngine.execute_checkpoints non-blocking mode '''

        # Add the checkpoint that will fail to beginning of list
        failed_chkpt_name = "fail1"
        self.engine.register_checkpoint(failed_chkpt_name,
                                        *self.failed_cp_data_args,
                                        insert_before="one")

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)
        
        # Empty checkpoints shouldn't take long - if they do, something's wrong
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")
        self.engine.checkpoint_thread.join(10)

        self.check_expected_failures([failed_chkpt_name],
                                     self.callback_results[0],
                                     self.callback_results[1])

        # Make sure the incomplete checkpoint is the failed checkpoint.
        cp = self.engine.get_first_incomplete()
        self.assertEqual(cp.name, failed_chkpt_name)
        
        self.assertFalse(self.engine.checkpoint_thread.is_alive(),
                         "Checkpoint thread still running")

    def test_non_blocking_execute_middle_cp_failed(self):
        '''Checkpoint in middle of list failed in InstallEngine.execute_checkpoints non-blocking mode '''

        # Add the checkpoint that will fail to middle of list
        failed_chkpt_name = "fail1"
        self.engine.register_checkpoint(failed_chkpt_name,
                                        *self.failed_cp_data_args,
                                        insert_before="four")

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)
        
        # Empty checkpoints shouldn't take long - if they do, something's wrong
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")
        self.engine.checkpoint_thread.join(10)

        self.check_expected_failures([failed_chkpt_name],
                                     self.callback_results[0],
                                     self.callback_results[1])

        # Make sure the incomplete checkpoint is the failed checkpoint.
        cp = self.engine.get_first_incomplete()
        self.assertEqual(cp.name, failed_chkpt_name)
        
        self.assertFalse(self.engine.checkpoint_thread.is_alive(),
                         "Checkpoint thread still running")

    def test_cp_failed_stop_on_error(self):
        '''Validate that when stop_on_error is set to false, all errors are reported '''

        # Add a few checkpoints that will fail to various spots on
        # list of checkpoints to run
        expected_failed_cp = ["failed1", "failed2", "failed3"]
        insert_before_list = ["one", "three", "five"]

        for (failed_cp, insert_name) in izip(expected_failed_cp,
                                             insert_before_list):
            self.engine.register_checkpoint(failed_cp,
                                            *self.failed_cp_data_args,
                                            insert_before=insert_name)

        self.engine.stop_on_error = False
        status, failed = self.engine.execute_checkpoints(dry_run=True)
        
        self.check_expected_failures(expected_failed_cp, status, failed)

        # Make sure the first incomplete checkpoint is the
        # first failed checkpoint.
        cp = self.engine.get_first_incomplete()
        self.assertNotEqual(cp, None)
        self.assertEqual(cp.name, expected_failed_cp[0])

    def test_nothing_to_exec(self): 
        '''Validate a warning is issued when there's no checkpoint to execute'''
        with warnings.catch_warnings(record=True) as w:
            self.engine.execute_checkpoints(start_from="one",
                                            pause_before="one")

            self.assertEqual(len(w), 1)
            self.assertTrue(w[-1].category, UserWarning)

    def test_gen_tmp_dir_w_env(self):
        '''Validate path of tmp DOC dir is determined correctly with TEMP_DOC_DIR env variable '''

        cache_path_env = "/tmp/__engine_doc_path_test"

        os.environ[self.engine.TMP_CACHE_ENV] = cache_path_env
        path_result = self.engine._gen_tmp_dir()

        # clean up the values set for this test
        del os.environ[self.engine.TMP_CACHE_ENV]

        self.assertEqual(path_result, cache_path_env)

class EngineRegisterTests(EngineTest):

    def setUp(self):
        EngineTest.setUp(self)
        
        name_list = ["one", "two", "three", "four", "five"]

        # a generic list of test checkpoints
        self.test_chkpt_list = []

        if _THIS_DIR.startswith("/"):
            self.cp_mod_name = "empty_checkpoint"
            self.cp_mod_path = _THIS_DIR
            self.cp_path = _THIS_DIR + "/empty_checkpoint"
        else:
            self.cp_mod_name = _THIS_DIR + "/empty_checkpoint"
            self.cp_mod_path = None
            self.cp_path = self.cp_mod_name

        for n in name_list:
            chkpt = checkpoint_data.CheckpointData(n, self.cp_mod_name,
                                   self.cp_mod_path, "EmptyCheckpoint", None,
                                   None, None)
            self.test_chkpt_list.append(chkpt)
            

    def check_result(self, expected_list):

        self.assertEquals(len(expected_list), len(self.engine._checkpoints))

        for expected_data, cp_data in zip(expected_list,
                                          self.engine._checkpoints):  

            self.assertEquals(cp_data.cp_info.cp_name,
                              expected_data.cp_info.cp_name,
                              "Module name: Expected %s, got %s" %
                              (expected_data.cp_info.cp_name,
                              cp_data.cp_info.cp_name))

            self.assertEquals(cp_data.cp_info.mod_name,
                              expected_data.cp_info.mod_name,
                              "Module name: Expected %s, got %s" %
                              (expected_data.cp_info.mod_name,
                              cp_data.cp_info.mod_name))

            self.assertEquals(cp_data.cp_info.module_path,
                              expected_data.cp_info.module_path,
                              "Module path: Expected %s, got %s" %
                              (expected_data.cp_info.module_path,
                              cp_data.cp_info.module_path))

            self.assertEquals(cp_data.cp_info.checkpoint_class_name,
                              expected_data.cp_info.checkpoint_class_name,
                              "Checkpoint class name: Expected %s, got %s" %
                              (expected_data.cp_info.checkpoint_class_name,
                              cp_data.cp_info.checkpoint_class_name))

    def test_reg_one_chkpt_min_arg_ok(self):
        '''Verify that register a checkpoint works with minimal required args '''

        chkpt = self.test_chkpt_list[0]
        try:
            self.engine.register_checkpoint(chkpt.name,
                self.cp_path, chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register 1 checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_multi_chkpt_min_arg_ok(self):
        '''Verify that register multiple checkpoint works with minimal required args '''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name,
                    self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        self.check_result(self.test_chkpt_list)

    def test_reg_chkpt_no_name(self):
        '''Verify that register a checkpoint without checkpoint name fails '''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(TypeError,
                          self.engine.register_checkpoint,
                          self.cp_path,
                          chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_blank_name(self):
        '''Verify that register a checkpoint with a name of "" fails '''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint,
                          "",
                          self.cp_path,
                          chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_None_name(self):
        '''Verify that register a checkpoint with a name of None fails '''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint,
                          None,
                          self.cp_path,
                          chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_dup_name(self):
        '''Verify that register a checkpoint with duplicate checkpoint name fails'''

        chkpt = self.test_chkpt_list[0]
        try:
            self.engine.register_checkpoint(chkpt.name,
                self.cp_path,
                chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint, chkpt.name,
                          self.cp_path,
                          chkpt.cp_info.checkpoint_class_name)

        # Make sure only 1 checkpoint is registered.
        self.check_result([chkpt])

    def test_reg_chkpt_no_path(self):
        '''Verify that register a checkpoint without module path fails'''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(TypeError,
                          self.engine.register_checkpoint, chkpt.name,
                          chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_blank_path(self):
        '''Verify that register a checkpoint with module path of "" fails'''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint, chkpt.name,
                          "", chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_none_path(self):
        '''Verify that register a checkpoint with module path of None fails'''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint, chkpt.name,
                          None, chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_invalid_path(self):
        '''Verify that register a checkpoint with invalid module path fails'''

        chkpt = self.test_chkpt_list[0]

        self.assertRaises(ImportError,
                          self.engine.register_checkpoint, chkpt.name,
                          chkpt.cp_info.mod_name+"/junk", 
                          chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_chkpt_no_chkp_class(self):
        '''Verify that register a checkpoint without checkpoint class name fails '''

        chkpt = self.test_chkpt_list[0]
        self.assertRaises(TypeError,
                          self.engine.register_checkpoint, chkpt.name,
                          self.cp_path)

        self.check_result([])

    def test_reg_chkpt_blank_chkp_class(self):
        '''Verify that register a checkpoint with checkpoint class name of "" fails '''

        chkpt = self.test_chkpt_list[0]

        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint, chkpt.name,
                          self.cp_path,
                          "")

        self.check_result([])

    def test_reg_chkpt_none_chkp_class(self):
        '''Verify that register a checkpoint with checkpoint class name of None fails '''

        chkpt = self.test_chkpt_list[0]

        self.assertRaises(engine.ChkptRegistrationError,
                          self.engine.register_checkpoint, chkpt.name,
                          self.cp_path,
                          None)

        self.check_result([])

    def test_reg_chkpt_invalid_chkp_class(self):
        '''Verify that register a checkpoint with invalid checkpoint class name fails '''

        chkpt = self.test_chkpt_list[0]

        self.assertRaises(AttributeError,
                          self.engine.register_checkpoint, chkpt.name,
                          self.cp_path,
                          "Junk")

        self.check_result([])

    def test_reg_with_one_arg(self):
        '''Verify that register a checkpoint that expects 1 arg to instantiate works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithArgs"
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, args=["arg1"])
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_with_one_missing_arg(self):
        '''Verify that register a checkpoint that expects 1 arg to instantiate, don't specify arg fails'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithArgs"
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name)

        self.check_result([])

    def test_reg_with_multi_arg(self):
        '''Verify that register a checkpoint that expects multiple args to instantiate works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithMultipleArgs"
        try:
            args = ["arg1", "arg2"]
            self.engine.register_checkpoint(chkpt.name,
                self.cp_path,
                chkpt.cp_info.checkpoint_class_name, args=args)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_with_one_missing_multiple_arg(self):
        '''Verify that register a checkpoint that expects multiple args to instantiate, only specify 1 arg fails'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithMultipleArgs"
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, args=["arg1"])
        self.check_result([])

    def test_reg_expect_1_kw_arg_provide_none(self):
        '''Verify that register a checkpoint that takes 1 keyword to instantiate, no providing keyword arg works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithKWArgs"
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_1_kw_arg_provide_1(self):
        '''Verify that register a checkpoint that takes 1 keyword to instantiate, providing value keyword arg works '''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithKWArgs"
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, kwargs={"kw1":"kw1"})
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_1_kw_arg_provide_2(self):
        '''Verify that register a checkpoint that takes 1 keyword to instantiate, providing 2 keyword arg fails'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithKWArgs"
        kwargs = {"kw1":"kw1", "other_kw":"other_kw"}
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, kwargs=kwargs)
        self.check_result([])

    def test_reg_expect_multi_kw_arg_provide_none(self):
        '''Verify that register a checkpoint that takes multiple keyword args to instantiate, not providing keyword arg works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithMultipleKWArgs"
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_multi_kw_arg_provide_1(self):
        '''Verify that register a checkpoint that takes multiple keyword args to instantiate, providing one of them works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithMultipleKWArgs"
        try:
            kwargs = {"kw2":"kw2"}
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, kwargs=kwargs)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_multi_kw_arg_provide_multiple(self):
        '''Verify that register a checkpoint that takes multiple keyword args to instantiate, providing all of them works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithMultipleKWArgs"
        try:
            kwargs = {"kw1":"kw1", "kw2":"kw2"}
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, kwargs=kwargs)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_args_and_multi_kw_arg_ok(self):
        '''Verify that register a checkpoint that takes multiple arguments and multiple keyword args to instantiate, providing all of them works'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithArgsAndKW"
        args = ["arg1", "arg2"]
        kwargs = {"kw1":"kw1", "kw2":"kw2"}
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, args=args, kwargs=kwargs)
        except Exception:
            self.fail("Failed to register checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_expect_args_and_multi_kw_arg_missing_arg(self):
        '''Verify that register a checkpoint that takes multiple arguments and multiple keyword args to instantiate, not providing 1 required argument fails'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithArgsAndKW"
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                          chkpt.name, self.cp_path,
                          chkpt.cp_info.checkpoint_class_name,
                          args=["arg1"], kwargs={"kw1":"kw1", "kw2":"kw2"})

        self.check_result([])

    def test_reg_missing_required_arg_with_arg(self):
        '''Verify that register a checkpoint with 1 required arg. Provide the arg, but do not provide classname, which is required for register_checkpoint function fails.'''

        chkpt = self.test_chkpt_list[0]
        chkpt.cp_info.checkpoint_class_name = "EmptyCheckpointWithArgs"
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                chkpt.name, self.cp_path, args=["hello"])

        self.check_result([])

    def test_reg_one_chkpt_loglevel_ok(self):
        '''Verify that register a checkpoint specifying loglevel works'''

        chkpt = self.test_chkpt_list[0]
        try:
            self.engine.register_checkpoint(chkpt.name, self.cp_path,
                chkpt.cp_info.checkpoint_class_name, loglevel=DEBUG)
        except Exception:
            self.fail("Failed to register 1 checkpoint with valid arguments")

        self.check_result([chkpt])

    def test_reg_insert_before_beginning(self):
        '''Verify that register a checkpoint at beginning of list using insert_before works.'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another",
                               self.cp_mod_name, self.cp_mod_path,
                               "EmptyCheckpoint", None, None, None)
        self.engine.register_checkpoint(new_chkpt.name, self.cp_path,
            new_chkpt.cp_info.checkpoint_class_name, insert_before="one")

        new_list = [new_chkpt]
        new_list.extend(self.test_chkpt_list)
        self.check_result(new_list)

    def test_reg_insert_before_middle_list(self):
        '''Verify that register a checkpoint at middle of list using insert_before works.'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another", self.cp_mod_name,
                               self.cp_mod_path, "EmptyCheckpoint", None,
                               None, None)
        self.engine.register_checkpoint(new_chkpt.name, self.cp_path,
            new_chkpt.cp_info.checkpoint_class_name, insert_before="four")

        new_list = [self.test_chkpt_list[0], self.test_chkpt_list[1],
                    self.test_chkpt_list[2], new_chkpt,
                    self.test_chkpt_list[3], self.test_chkpt_list[4]]

        self.check_result(new_list)

    def test_reg_insert_before_invalid_name(self):
        '''Verify that register a checkpoint specifying invalid name for insert_before fails.'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another", self.cp_mod_name,
                               self.cp_mod_path, "EmptyCheckpoint", None,
                               None, None)
        self.assertRaises(engine.ChkptRegistrationError,
            self.engine.register_checkpoint, new_chkpt.name,
            self.cp_path, new_chkpt.cp_info.checkpoint_class_name,
            insert_before="invalid_name")

        self.check_result(self.test_chkpt_list)

    def test_reg_insert_before_and_loglevel(self):
        '''Verify that register a checkpoint with both loglevel and insert_before argument works.'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another",
                               self.cp_mod_name, self.cp_mod_path,
                               "EmptyCheckpoint", None, None, None)
        self.engine.register_checkpoint(new_chkpt.name, self.cp_path,
            new_chkpt.cp_info.checkpoint_class_name, insert_before="one",
            loglevel=ERROR)

        new_list = [new_chkpt]
        new_list.extend(self.test_chkpt_list)
        self.check_result(new_list)

    def test_reg_insert_before_and_loglevel_and_args(self):
        '''Verify that register a checkpoint with both loglevel, insert_before argument, and arguments for checkpoint works'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another", self.cp_mod_name,
                                self.cp_mod_path,
                                "EmptyCheckpointWithArgsAndKW", None,
                                None, None)
        args = ["arg1", "arg2"]
        kwargs = {"kw1":"kw1"}
        self.engine.register_checkpoint(new_chkpt.name, self.cp_path,
            new_chkpt.cp_info.checkpoint_class_name, args=args,
            insert_before="one", loglevel=ERROR, kwargs=kwargs)

        new_list = [new_chkpt]
        new_list.extend(self.test_chkpt_list)
        self.check_result(new_list)

    def test_reg_insert_before_and_loglevel_and_missing_args(self):
        '''Verify that register a checkpoint with loglevel, insert_before argument, but missing arg for checkpoint fails'''

        try:
            for chkpt in self.test_chkpt_list:
                self.engine.register_checkpoint(chkpt.name, self.cp_path,
                    chkpt.cp_info.checkpoint_class_name)
        except Exception:
            self.fail("Failed to register checkpoint %s with valid arguments" %
                       chkpt.name)

        new_chkpt = checkpoint_data.CheckpointData("another",
                               self.cp_mod_name, self.cp_mod_path,
                               "EmptyCheckpointWithArgsAndKW", None,
                               None, None)
        self.assertRaises(TypeError, self.engine.register_checkpoint,
                          new_chkpt.name, self.cp_path,
                          new_chkpt.cp_info.checkpoint_class_name,
                          args=["arg1"], insert_before="one",
                          loglevel=ERROR, kwargs={"kw1":"kw1"})

        self.check_result(self.test_chkpt_list)

    def test_reg_none_arg_ok(self):
        '''Verify that register a checkpoint providing None as args and kwargs works'''

        chkpt = self.test_chkpt_list[0]
        try:
            self.engine.register_checkpoint(chkpt.name,
                self.cp_path, chkpt.cp_info.checkpoint_class_name, args=None,
                kwargs=None)
        except Exception:
            self.fail("Failed to register 1 checkpoint with args=None, kwargs=None")

        self.check_result([chkpt])

class EngineCancelTests(EngineCheckpointsBase):
    '''Test InstallEngine.cancel_checkpoints(...) scenarios'''
    
    CANCEL_CP_NAME = "cancel_cp"

    def setUp(self):
        EngineCheckpointsBase.setUp(self)
        self.engine.data_object_cache = MockDOC()
        errsvc.clear_error_list()

    def reg_cancel_checkpoint(self):
        # register a check that looks for the cancel flag in the middle
        # of the previouly registered checkpoint list.
        self.engine.register_checkpoint(EngineCancelTests.CANCEL_CP_NAME,
                                        *self.cp_data_args,
                                        insert_before="three",
                                        kwargs={"wait_for_cancel":True})

    def test_cancel(self):
        '''Test InstallEngine.cancel_checkpoints for the success case'''

        # register a checkpoint that looks for the cancel flag
        self.reg_cancel_checkpoint()

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)
 
        # Wait a little bit so we get to the checkpoint we expect to cancel
        self.callback_executed.wait(5)

        self.engine.cancel_checkpoints()

        # Wait for the cancel request to end the execute_checkpoints(),
        # it should not take too long.
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")
 
        # Wait 15 seconds for the cancel to take place.  It should
        # not take that long.
        self.engine.checkpoint_thread.join(15)

        self.assertEqual(self.callback_results[0], self.engine.EXEC_CANCELED,
                          "Engine did not return EXEC_CANCELED")

        # Name of the checkpoint canceled should be returned.
        self.assertEqual(1, len(self.callback_results[1]))

        self.assertEqual(EngineCancelTests.CANCEL_CP_NAME,
                         (self.callback_results[1])[0])

    def test_cancel_did_not_start_exec(self):
        '''Verify InstallEngine.cancel_checkpoints behave correctly when checkpoints are registered, but nothing is executing.'''

        # register a checkpoint that looks for the cancel flag
        self.reg_cancel_checkpoint()

        # Call cancel_checkpoints 
        self.engine.cancel_checkpoints()

        # Make sure the cancel checkpoint is not executed
        cp_data = self.engine.get_cp_data(EngineCancelTests.CANCEL_CP_NAME)
        self.assertFalse(cp_data.completed)

    def test_cancel_finished_exec(self):
        '''Verify InstallEngine.cancel_checkpoints behave correctly when all checkpoints finished executing and there's nothing to cancel.'''

        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.assertEqual(0, len(failed_cp))
        
        # All checkpoints should be completed
        self.assertEqual(self.engine.get_first_incomplete(), None)
        self.assertEqual(self.engine.checkpoint_thread, None)

        # Call cancel_checkpoints, should be a no op, make sure no exception
        # is raised.
        try:
            self.engine.cancel_checkpoints()
        except Exception, ex:
            self.fail("cancel checkpoint failed after execute completed")


    def test_exec_after_cancel(self):
        '''Verify execute_checkpoint() works correctly after cancel_checkpoints is called. '''

        # register a checkpoint that looks for the cancel flag
        self.reg_cancel_checkpoint()

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)

        # Wait a little bit so we get to the checkpoint we expect to cancel
        self.callback_executed.wait(5)
 
        self.engine.cancel_checkpoints()

        # Wait for the cancel request to end the execute_checkpoints(),
        # it should not take too long.
        self.callback_executed.wait(10)
        self.assertTrue(self.callback_executed.is_set(),
                        "Callback wasn't called-back")
        # Wait 15 seconds for the cancel to take place.  It should
        # not take that long.
        self.engine.checkpoint_thread.join(15)

        self.assertEqual(self.callback_results[0], self.engine.EXEC_CANCELED,
                          "Engine did not return EXEC_CANCELED")

        # Name of the checkpoint canceled should be returned.
        self.assertEqual(1, len(self.callback_results[1]))

        self.assertEqual(EngineCancelTests.CANCEL_CP_NAME,
                         (self.callback_results[1])[0])

        # Change the parameter of the checkpoint that would wait for the
        # cancel, to not do the waiting
        cp_data = self.engine.get_cp_data(EngineCancelTests.CANCEL_CP_NAME)
        cp_data.cp_info.reg_kwargs["wait_for_cancel"] = False

        # continue execution.  Make sure rest of checkpoints are executed.
        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.assertEqual(0, len(failed_cp))
        
        # All checkpoints should be completed
        self.assertEqual(self.engine.get_first_incomplete(), None)
        self.assertEqual(self.engine.checkpoint_thread, None)


if __name__ == '__main__':
    unittest.main()
