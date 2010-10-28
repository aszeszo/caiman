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

'''
Test more complex engine interactions with ZFS and DOC
'''

import os
import unittest
import shutil

from nose.plugins.skip import SkipTest

import solaris_install.engine as engine
from solaris_install.data_object.data_dict import DataObjectDict
from solaris_install.target import zfs

from test_engine import EngineCheckpointsBase


# Can override the base zfs dataset area by setting ZFS_TEST_DS env variable
_ZFS_TEST_DS_BASE = os.environ.get("ZFS_TEST_DS", "rpool/__engine_test")

# Setting the LEAVE_ZFS environment variable to "true" will cause the tests
# to leave the ZFS datasets created around for debugging purposes
_LEAVE_ZFS = os.environ.get("LEAVE_ZFS", "false").lower() == "true"

_ZFS_TEST_DS = _ZFS_TEST_DS_BASE + "/%s"
_PERMISSIONS = (os.getuid() == 0)

_DEFER_DESTROY_ZFS = False


def tearDown():
    '''Clean up the base dataset. Note: This is only run when running in 
    a 'nose' environment (which is the case for running via
    tools/test/slim_test). See also setUp()
    
    '''
    if _PERMISSIONS and not _LEAVE_ZFS:
        base_ds = zfs.Dataset(_ZFS_TEST_DS_BASE)
        if base_ds.exists:
            base_ds.destroy(recursive=True)


def setUp():
    '''Like tearDown, only run in a nose execution environment.
    Sets a global that ComplexEngineTests.tearDown() uses to determine if it's
    safe to defer destruction of the ZFS datasets. This improves performance
    when multiple tests are run (since ZFS destruction takes a long time
    relative to execution of a single test)
    
    '''
    global _DEFER_DESTROY_ZFS
    _DEFER_DESTROY_ZFS = True

class ComplexEngineTests(EngineCheckpointsBase):
    
    __dataset = None
    
    def get_dataset(self):
        '''Returns a zfs.Dataset for test purposes. If the ZFS dataset already
        exists, the test is aborted, to prevent accidental destruction of data.
        If a dataset is given, it is stored and destroyed (as well as any
        descendants) after test execution'''
        if not _PERMISSIONS:
            raise SkipTest("Insufficient permissions to run ZFS test")
        
        test_ids = (self.id()).split(".")

        # Use name of the test case as the name of the function.
        # name of test case is found in the last field of the test id.
        ds_name = _ZFS_TEST_DS % test_ids[-1] + "_%s"
      
        tried = []
        # try to look for a unique name for the ZFS dataset to be used
        # for the tests.  If can not find a unique name within 15 tries, 
        # notify the user, so, they can do some cleanup of their test datasets.
        for x in xrange(15):
            dataset = zfs.Dataset(ds_name % x)
            tried.append(dataset.name)
            if not dataset.exists:
                break
        else:
            raise SkipTest("Could not generate unique ZFS dataset to safely"
                           " test. Tried: %s" % tried)
        
        dataset.create()
        self.__dataset = dataset
        return dataset
    
    def tearDown(self):
        # Clear out ZFS dataset
        if (self.__dataset is not None and self.__dataset.exists and
            not _LEAVE_ZFS and not _DEFER_DESTROY_ZFS):
            self.__dataset.destroy(recursive=True)
            self.__dataset = None
        
        EngineCheckpointsBase.tearDown(self)
    
    def verify_resumable_cp_result(self, expected_list, actual_list):

        ''' Verify return value from get_resumeable_checkpoints() function '''

        for expected_name, actual_name in zip(expected_list, actual_list):
            self.assertEqual(expected_name, actual_name, "%s != %s (from "
                             "lists %s and %s)" % (expected_name, actual_name,
                                                   expected_list, actual_list))
        self.assertEqual(len(expected_list), len(actual_list), "%s != %s" %
                         (expected_list, actual_list))
    
    def test_snapshot_new_zfs_snap(self):
        '''Test InstallEngine.snapshot where the given snapshot doesn't yet exist'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        cp_data = self.engine.get_cp_data(self.name_list[0])
        snap = zfs.Dataset(dataset.snapname(".step_" + cp_data.name))
        
        self.engine.snapshot(cp_data)
        self.assertTrue(os.path.exists(cp_data.data_cache_path),
                        "Path doesn't exist: " + cp_data.data_cache_path)
        self.assertTrue(snap.exists)
    
    def test_snapshot_overwrite_zfs_snap(self):
        '''Ensure InstallEngine.snapshot overwrites an existing snapshot'''
        cp_data = self.engine.get_cp_data(self.name_list[0])
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        snapname = self.engine.get_zfs_snapshot_name(cp_data.name)
        dataset.snapshot(snapname)
        
        snap = zfs.Dataset(dataset.snapname(snapname))
        
        self.engine.snapshot(cp_data)
        self.assertTrue(os.path.exists(cp_data.data_cache_path),
                        "Path doesn't exist: " + cp_data.data_cache_path)
        self.assertTrue(snap.exists)
    
    def test_restore_data_zfs_rollback(self):
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()
        
        self.engine._rollback(self.name_list[1]) # Rollback to 'two'
        
        snapnames = [self.engine.get_zfs_snapshot_name(x) for x in self.name_list[:2]]
        snaps_exist = [self.engine.dataset.snapname(snap) for snap in snapnames]

        # Snapshots for checkpoints 'one' and 'two' should still be around,
        # but no others
        
        snap_list = self.engine.dataset.snapshot_list
        
        for name in snaps_exist:
            self.assertTrue(name in snap_list, "'%s' not in %s" %
                            (name, snap_list))
        
        for name in self.name_list[2:]:
            snap_name = self.engine.dataset.name + "@.step_" + name
            self.assertFalse(snap_name in snap_list, "'%s' should not be in %s" % (snap_name, snap_list))
    
    def test_restore_data_tmp(self):
        '''Slightly more than a "Unit" test, this verifies that rollback interacts as expected with the DOC'''
        
        string_data = DataObjectDict("TESTKEY", {"TESTKEY" : "TESTVALUE"})
        doc = self.engine.data_object_cache.persistent
        doc.insert_children([string_data])
        
        stored_data = doc.get_first_child(name="TESTKEY")
        self.assertNotEqual(stored_data, None)
        
        self.engine.execute_checkpoints(pause_before=self.name_list[1])
        
        stored_data = doc.get_first_child(name="TESTKEY")
        self.assertNotEqual(stored_data, None)
        self.assertEquals("TESTVALUE", stored_data.data_dict["TESTKEY"])
        
        stored_data.data_dict["TESTKEY"] = "new value"
        
        stored_data_2 = doc.get_first_child(name="TESTKEY")
        self.assertTrue(stored_data is stored_data_2)
        
        # Rollback to beginning and run all checkpoints
        self.engine.execute_checkpoints(start_from=self.name_list[0])
        
        stored_data_3 = doc.get_first_child(name="TESTKEY")
        self.assertNotEqual("new value", stored_data_3.data_dict["TESTKEY"])
        self.assertEqual("TESTVALUE", stored_data_3.data_dict["TESTKEY"])

    def test_get_resumable_cp_basic(self):
        '''Verify basic functionality of get_resumable_checkpoints'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()
        
        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(self.name_list, cp_list)

    def test_get_resumable_cp_two_exec(self):
        '''Verify get_resumable_checkpoints() works correctly with 2 execute_checkpoints() calls '''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints(pause_before="three")
        self.engine.execute_checkpoints()
        
        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(self.name_list, cp_list)

    def test_get_resumable_cp_subset_reg(self):
        '''Verify get_resumable_checkpoints() with more registered checkpoints than successfully executed checkpoints'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints(pause_before="three")
        
        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(self.name_list[:3], cp_list)

    def test_get_resumable_cp_no_exec(self):
        '''Verify get_resumable_checkpoints() without previously executing any checkpoints'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset

        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(self.name_list[:1], cp_list)

    def test_get_resumable_cp_missing_last_zfs_snapshot(self):
        '''Verify get_resumable_checkpoints() handling missing last ZFS snapshot for executed checkpoints'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        # manually snapshots
        dataset.destroy(self.engine.get_zfs_snapshot_name(self.engine._LAST.name))
        dataset.destroy(self.engine.get_zfs_snapshot_name(self.name_list[-1]))
        dataset.destroy(self.engine.get_zfs_snapshot_name(self.name_list[-2]))
        
        cp_list = self.engine.get_resumable_checkpoints()
        expected_result = self.name_list[:-1]
        self.verify_resumable_cp_result(expected_result, cp_list)

    def test_get_resumable_cp_missing_middle_zfs_snapshot(self):
        '''Verify get_resumable_checkpoints() handling missing snapshot checkpoint in middle of executed checkpoints list'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        # manually remove a snapshot in middle of checkpoint list
        snap_path = self.engine.get_zfs_snapshot_name("three")
        dataset.destroy(snap_path)
        snap_path = self.engine.get_zfs_snapshot_name(self.engine._LAST.name)
        dataset.destroy(snap_path)
        
        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(["one", "two", "three"], cp_list)

    def test_get_resumable_cp_diff_cp_set(self):
        '''Verify get_resumable_checkpoints() with different set of checkpoint than previous execution'''

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        self.engine._checkpoints = []

        new_name_list = ["six", "seven", "eight", "nine", "ten"]
        for name in new_name_list:
            self.engine.register_checkpoint(name, *self.cp_data_args)
        
        cp_list = self.engine.get_resumable_checkpoints()
        # Can only start from the beginning of the new list
        self.verify_resumable_cp_result(["six"], cp_list)

    def test_get_resumable_cp_diff_middle_cp(self):
        '''Verify get_resumable_checkpoints() with a different checkpoint in middle of list '''

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        # Give the third checkpoint a different checkpoint name
        self.engine._checkpoints = []
        new_name_list = self.name_list[:]
        new_name_list[2] = "six"
        for name in new_name_list:
            self.engine.register_checkpoint(name, *self.cp_data_args)
        
        cp_list = self.engine.get_resumable_checkpoints()
        # Since 'one' and 'two' have completed, it's legal to start from 'six'
        # as well.
        self.verify_resumable_cp_result(["one", "two", "six"], cp_list)

    def test_get_resumable_cp_diff_cp_class(self):
        '''Verify get_resumable_checkpoints() with different checkpoint class for 1 checkpoint'''

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        self.engine._checkpoints = []

        expected_result = self.name_list[:-2]
        for name in expected_result:
            self.engine.register_checkpoint(name, *self.cp_data_args)

        # register the checkpoint "four" with different checkpoint class name
        # It should no longer be possible to resume from checkpoints after
        # "four" (in this case, only "five" is disqualified).
        self.engine.register_checkpoint("four", "empty_checkpoint",
                                        "FailureEmptyCheckpoint")
        expected_result.append("four")
        
        self.engine.register_checkpoint(self.name_list[-1], *self.cp_data_args)

        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(expected_result, cp_list)

    def test_get_resumable_cp_missing_last_DOC_snapshot(self):
        '''Verify get_resumable_checkpoints() with last DOC snapshot missing'''
        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()
        
        # Remove DOC snapshot of last executed checkpoint
        snapshot_name = self.engine.get_cache_filename(self.engine._LAST)
        os.remove(snapshot_name)

        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(["one"], cp_list)
        
    def test_get_resumable_cp_no_cp_registered(self):
        '''Verify get_resumable_checkpoints() with no checkpoint registered in subsequent run'''

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()
        self.engine._checkpoints = []

        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result([], cp_list)

    def test_get_resumable_cp_initial_cp_no_zfs_snapshot(self):
        '''Verify get_resumable_checkpoints() where first couple checkpoints have no ZFS snapshots '''

        self.engine.execute_checkpoints(pause_before="four")

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        self.engine.execute_checkpoints()

        cp_list = self.engine.get_resumable_checkpoints()
        self.verify_resumable_cp_result(["four", "five"], cp_list)

    def test_get_resumable_cp_zfs_not_set(self):
        '''Verify get_resumable_checkpoints() without setting a ZFS dataset '''

        self.assertRaises(engine.NoDatasetError,
                          self.engine.get_resumable_checkpoints)

    def test_get_resumable_cp_zfs_not_exist(self):
        '''Verify get_resumable_checkpoints() with ZFS dataset, but the ZFS dataset does not exist '''
        self.engine.dataset = "junk"

        self.assertRaises(engine.FileNotFoundError,
                          self.engine.get_resumable_checkpoints)

    def test_gen_tmp_dir_no_env(self):
        '''Validate path of tmp DOC dir is determined correctly without TEMP_DOC_DIR env variable '''

        # make sure the env variable is not defined
        del os.environ[self.engine.TMP_CACHE_ENV]

        path_result = self.engine._gen_tmp_dir()
        self.assertEqual(os.path.dirname(path_result),
                         self.engine.TMP_CACHE_PATH_ROOT_DEFAULT)

        # Get the full path of the directory that's generated.
        dir_path = os.path.basename(path_result)

        if not dir_path.startswith(self.engine.TMP_CACHE_PATH_PREFIX):
            self.fail("Temp DOC dir not determined correctly when TEMP_DOC_DIR env variable not set")

class CleanupCheckpointTests(ComplexEngineTests):

#    def tearDown(self):
#        ComplexEngineTests.tearDown()

    def test_cleanup_no_registered_cp(self):
        '''Verify cleanup_checkpoints() does not result in any errors if no checkpoints are registered '''

        # force the registered checkpoint list to be empty.  The setup()
        # function of EngineCheckpointsBase registered some checkpoints
        self.engine._checkpoints = []

        self.engine.cleanup_checkpoints()

    def test_cleanup_no_exec(self):
        '''Verify cleanup_checkpoints() does not result in any errors when checkpoints are registered, but they are not executed. '''

        self.engine.cleanup_checkpoints()

    def test_cleanup_no_zfs(self):
        '''Verify cleanup_checkpoints() does not result in any errors when ZFS dataset is not set. '''

        # Make sure ZFS dataset is None
        self.engine._dataset = None
        
        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
 
        # save value for _tmp_cache_path before the cleanup to make
        # sure it is indeed removed by cleanup
        saved_tmp_cache_path = self.engine._tmp_cache_path

        self.engine.cleanup_checkpoints()

        # Make sure all DOC snapshots in temp DOC dir is removed
        self.assertEquals(self.engine._tmp_cache_path, None)
        self.assertFalse(os.path.exists(saved_tmp_cache_path))

    def test_cleanup_exec_all(self):
        '''Verify cleanup_checkpoints() cleans up all snapshots after executing. '''
        dataset = self.get_dataset()
        self.engine.dataset = dataset

        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)

        self.engine.cleanup_checkpoints()

        # make sure all ZFS snapshots are removed
        zfs_snapshots = self.engine.dataset.snapshot_list
        for cp_name in self.name_list:
            zfs_snap_path = self.engine.get_zfs_snapshot_fullpath(cp_name)
            self.assertFalse(zfs_snap_path in zfs_snapshots)

    def test_cleanup_exec_some(self):
        '''Verify cleanup_checkpoints() cleans up all snapshots after executing a few of the registered checkpoints '''

        dataset = self.get_dataset()
        self.engine.dataset = dataset
        
        status, failed_cp = self.engine.execute_checkpoints(dry_run=True,
                                                            pause_before="four")
        self.assertEquals(status, self.engine.EXEC_SUCCESS)

        self.engine.cleanup_checkpoints()

        # make sure ZFS snapshots for checkpoints "one", "two", and
        # "three" are removed.

        zfs_snapshots = self.engine.dataset.snapshot_list
        for cp_name in ["one", "two", "three"]:
            zfs_snap_path = self.engine.get_zfs_snapshot_fullpath(cp_name)
            self.assertFalse(zfs_snap_path in zfs_snapshots)

    def test_cleanup_during_execute(self):
        '''Verify cleanup_checkpoint() is not allowed in the middle of an execute '''

        # Insert a checkpoint that will loop until cancelled to make sure the
        # execute_checkpoint() operation is running

        self.engine.register_checkpoint("cancel_cp",
                                        *self.cp_data_args,
                                        insert_before="one",
                                        kwargs={"wait_for_cancel":True})

        self.engine.execute_checkpoints(callback=self._exec_cp_callback,
                                        dry_run=True)

        # verify cleanup_checkpoint() is not allowed
        self.assertRaises(engine.EngineError, self.engine.cleanup_checkpoints)

        # cancel the checkpoint that hangs
        self.engine.cancel_checkpoints()

    def test_exec_after_cleanup_with_zfs(self):
        '''Verify execute_checkpoints() still correctly execute all the checkpoints after cleanup_checkpoints().  ZFS dataset is provided '''

        dataset = self.get_dataset()
        self.engine.dataset = dataset

        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.engine.cleanup_checkpoints()

        # make sure first un-executed checkpoint is now "one"
        first_incomplete = self.engine.get_first_incomplete()
        self.assertEqual(first_incomplete.name, "one")

        # execute everything now.
        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)

    def test_exec_after_cleanup_no_zfs(self):
        '''Verify execute_checkpoints() still correctly execute all the checkpoints after cleanup_checkpoints(). ZFS dataset is not provided '''

        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.engine.cleanup_checkpoints()

        # make sure first un-executed checkpoint is now "one"
        first_incomplete = self.engine.get_first_incomplete()
        self.assertEqual(first_incomplete.name, "one")

        # execute everything now.
        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)

    def test_cleanup_get_resumable(self):
        '''Verify nothing is resumable after cleanup_checkpoints() '''

        dataset = self.get_dataset()
        self.engine.dataset = dataset

        status, failed_cp = self.engine.execute_checkpoints(dry_run=True)
        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.engine.cleanup_checkpoints()

        cp_list = self.engine.get_resumable_checkpoints()
        self.assertEquals(len(cp_list), 1)
        self.assertEquals(cp_list[0], "one")

    def test_cleanup_get_resumable_not_allowed(self):
        '''Register 5 checkpoints, execute first 3, call cleanup_checkpoints().  Verify that continue executing the rest is not allowed  '''

        dataset = self.get_dataset()
        self.engine.dataset = dataset

        status, failed_cp = self.engine.execute_checkpoints(pause_before="four",
                                                            dry_run=True)

        self.assertEquals(status, self.engine.EXEC_SUCCESS)
        self.engine.cleanup_checkpoints()

        # Make sure we are not able to continue with the previous execution.
        self.assertRaises(engine.EngineError, self.engine.execute_checkpoints,
                          start_from="four", dry_run=True)
        
if __name__ == '__main__':
    unittest.main()
