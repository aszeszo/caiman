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
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#

import getopt
import os
import sys
import subprocess
import shutil
import filecmp
import fnmatch

from osol_install.distro_const.dc_utils import *

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/DC_defs.py")

# =============================================================================
class step:  
# =============================================================================
        """
        step contains the information needed for each different checkpoint step.
        The number of steps on the system is determined by the number of 
        checkpoints the user wishes to create.
        """
        #   _step_num  - number of the checkpoint. Increments by one for
        #			each successive step.
        #   _step_name - name associated with this step. If no name is given it
        #			will default to the text version of the number.
        #   _message - Message to be printed to indicate which step the build is
        #			on.
        #   _state_file - Name of the file to copy the manifest file to for this
        #			step. It is equal to .step_<_step_name>
        #   _zfs_snapshot - Name of the zfs snapshot. It is equal to the 
        #			zfs_dataset_name@step_<_step_name>
        step_num = 0

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_step_num(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._step_num

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_step_name(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._step_name

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_step_message(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._message

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_state_file(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._state_file

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_zfs_snapshot(self, num):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._zfs_snapshot[num]

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def __init__(self, step_name, message, state_file,
                        zfs_dataset):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._step_num = step.step_num 
                self._step_name = step_name 
                self._message = message 
                self._state_file= state_file 
                self._zfs_snapshot = []
	        for i, zfs_dataset_name in enumerate(zfs_dataset) : 
                        self._zfs_snapshot.insert(i,
                            "%s@%s" % (zfs_dataset_name,
                            ".step_" + step_name))
                step.step_num += 1


# =============================================================================
class checkpoints:
# =============================================================================
        """
        Class to hold all of the checkpoint info.
        """
        #    step_list = Information for each step.
        #    _resume_step = step to resume executing at.
        #    _pause_step= step to stop executing at.
        #    _current_step = step currently executing.
        #    _manifest_file = name of the manifest file that holds the
        #        configuration information
        #    _checkpoint_avail = Tells if checkpointing is available.
	#    _zfs_found = Is zfs on the system?
	#    _pkg_image_mntpt = mount point for the package image
	#    _pkg_image_dataset = zfs dataset for the package image 
	
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def incr_current_step(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._current_step += 1

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_current_step(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._current_step

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_resume_step(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._resume_step

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def set_resume_step(self, num):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._resume_step = num

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_pause_step(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._pause_step

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def set_pause_step(self, num):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._pause_step = num

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_manifest(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._manifest_file

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def set_manifest(self, manifest):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._manifest_file = manifest

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def set_checkpointing_avail(self, flag):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._checkpoint_avail = flag 

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def get_checkpointing_avail(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                return self._checkpoint_avail 

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def set_zfs_found(self, flag):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		self._zfs_found = flag

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_zfs_found(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		return self._zfs_found

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def set_pkg_image_mntpt(self, mntpt):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		self._pkg_image_mntpt = mntpt

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_pkg_image_mntpt(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		return self._pkg_image_mntpt

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def set_pkg_image_dataset(self, dataset):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		self._pkg_image_dataset = dataset 

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	def get_pkg_image_dataset(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
		return self._pkg_image_dataset

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def step_setup(self, message, zfs_dataset=[], name=None):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                """
                Setup the step structure with the basic information needed
                to create a step.
     	        step_name - User friendly name for the step. If null, defaults
                        to the ascii version of the number. i.e. "1"
                message - Message to print out at start of the step.
                        i.e. "Downloading IPS packages"
                _state_file - Name of the file to copy the manifest file to
                        for this step. It is equal to .step_<_step_name>
                _zfs_snapshot - Name of the zfs snapshot. It is equal to the 
                	zfs_dataset_name@step_<_step_name>
                """
                index = len(self.step_list)
                if name is None :
                        name = str(len(self.step_list))

		# The .step files goes at the root directory of the image area.
		image_area = self.get_pkg_image_mntpt()
		state_file = image_area.rsplit(image_area[image_area.rfind("/"):])[0] + "/.step_" + name 
                self.step_list.insert(index, step(name, message, state_file,
                        zfs_dataset))

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def create_checkpoint(self, name):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                """
                Create a checkpoint. This involves creating a zfs snapshot and
                copying the manifest file to the .step_<name> file.
                name - name of the checkpoint
                Returns 0 on success
                        non zero error code on error
                """
                # If zfs is not on the system, we just skip the portion that
                # creates the the checkpoint and continue on building.
                if self.get_checkpointing_avail() == False: 
                        return 0
                pausestep = self.get_pause_step()
                for step_obj in self.step_list :
                        if name == step_obj.get_step_name() :
                                stepnum = step_obj.get_step_num()
				for zfs_snapshot in step_obj._zfs_snapshot:
                                        ret = shell_cmd(
                                            "/usr/sbin/zfs snapshot " +
                                            zfs_snapshot) 
                                        if ret :
                                                return ret 
                                        shutil.copy(
                                             self.get_manifest(),
                                             step_obj.get_state_file())
                                if pausestep == stepnum:
                                        print "Stopping at Step %s" % name
                                else :
                                        print "Step %s: %s" % (name,
                                            step_obj.get_step_message())
                                self.incr_current_step()
                                return 0
                print "Unable to create checkpoint at Step %s. " % name
                print "You will not be able to resume from this step."
                return 0 

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def __init__(self):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._resume_step = -1 
                self._pause_step = 9999 
                self._current_step = 0 
                self._manifest_file = ""
		self._pkg_image_mntpt = ""
		self._pkg_image_dataset = ""
                self._checkpoint_avail = True 
		self._zfs_found = True
	        self.step_list = []


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def shell_cmd(cmd):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Execute a shell command
        Input:
            cmd - string specifying the command to execute
        """
        try:
                ret = subprocess.call(cmd, shell=True)
        except OSError, e:
                print >>sys.stderr, "execution failed:", e

        return ret 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def step_from_name(self, name) :
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Determine the step, given the step name. Each step has a 
        unique number and name. Search through the step_list for the given
        name and return the step. If a step with the given name can't be found
        the user must have specified an invalid name. Print a message telling
        them this.
        Input:
            name - name of the step to find.
        Return:
            the step. 
            None 
        """
        for step_obj in self.step_list:
                if name == step_obj.get_step_name():
                        return step_obj 
        print "An invalid step was specified."
        pstr = "Valid step names are: "
        for step_obj in self.step_list :
                pstr += step_obj.get_step_name() + "  "    
        print pstr
        return None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_determine_resume_step(self):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Determine which step to resume from. If the user specifies to resume
        at the latest step via dist-const -r ./manifest_file, then we
        need to determine what the last step started was.
        Returns:
            step number to resume running at.
        """
        highest_step = -1   

        # Search the directory for all .step_* files.
	image_area = self.get_pkg_image_mntpt()
	state_dir = image_area.rsplit(image_area[image_area.rfind("/"):])[0]
        for file in os.listdir(state_dir):
                if fnmatch.fnmatch(file, '.step_*'):
                        for step_obj in self.step_list:
                                # For each file in the list, find the
                                # corresponding state file in our steps.
                                if state_dir + "/" + file == step_obj.get_state_file():
                                        # Look at the step number for that step.
                                        # If it's the biggest step number found,
                                        # save it. Do this for all .step_*'s in
                                        # the list.
                                        highest_step = max(highest_step,
                                            step_obj.get_step_num())
        return highest_step 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_verify_resume_step(self, num):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Verify that the state the user specified execution to resume at was
        valid. The step must be less than or equal to the step at which the
        previous build exited.
        Input:
            num - step number the user specified to resume at.
        Return:
            0 - success 
           -1 - error 
        """
        laststep = DC_determine_resume_step(self)
        if num > laststep:
                print "You must specify an earlier step to resume at."
                pstr = "Valid steps to resume from are: "
                pstr = pstr + self.step_list[0].get_step_name()    
                for i in range (1, laststep):
                        pstr = pstr + " " + self.step_list[i].get_step_name()    
                print pstr
                return -1
        return 0 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_verify_resume_state(self):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Verifies the  state file of each step and or below 'num'. The state
        files must be the same as the current manifest file.
        If the files are not the same, execution continues but a warning is
        printed.
        Input:
            stepno - number of step whose state file to verify
        """
        change = 0
        pstr = ""
	num = self.get_resume_step()
        manifest = self.get_manifest()
        for step_obj in self.step_list:
                if num >= step_obj.get_step_num():
                        # Compare the .step<name> file to the manifest file.
                        # They should be the same since on step creation the
                        # manifest file was copied to the .step_<name> file
                        # unless the user has modified the manifest file. This
                        # could cause indeterminate results so we want to warn
                        # the user of this situation.
                        if cmp(step_obj.get_state_file(), manifest) == -1:
		                change = 1
                                pstr += " %s" % step_obj.get_step_name()
        if (change) :
                print "WARNING: The manifest file, %s, has changed " % manifest
                print "since Step(s) %s was generated." % pstr 
                print "Results may be indeterminate."

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_execute_checkpoint(self, var):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Check to see if the step should be executed. If the step to resume at is
        less than the current step, create a checkpoint with specified name. The
        name must be the same as the name that  will be used in the step_setup
        call.
        NOTE: All checkpoints must have a call to self.step_setup in
        DC_checkpoint_setup and a call to DC_execute_checkpoint. The name MUST
        be the same for both function calls.
        Input:
            name - name of the step to check and the checkpoint to create.
        Returns:
            0 - execute the step
            1 - don't execute the step.
           -1 - stop execution on return 
        """
	if self.get_checkpointing_avail() == False:
		return 0

        if isinstance(var, int):
                name = self.step_list[var].get_step_name()
        elif isinstance(var, str):
	        name = var 
        else :
                print "Unable to execute checkpoint code due to invalid syntax"
                return (0)
        resumestep = self.get_resume_step()
        pausestep = self.get_pause_step()
        currentstep = self.get_current_step()
        if pausestep == currentstep:
                self.create_checkpoint(name)
                return -1 
        if currentstep > resumestep:
                if self.create_checkpoint(name):
                        print "An error occurred when creating the checkpoint. "
                        print "Checkpointing functionality is unavailable" 
        elif currentstep == resumestep:
		# At the specified step to resume from. Rollback
		# to the zfs snapshot.
		for zfs_dataset_nm in self.step_list[resumestep]._zfs_snapshot:
                	shell_cmd("/usr/sbin/zfs rollback "
			    + zfs_dataset_nm + " >/dev/null 2>&1")
                self.incr_current_step()
	else :
		# We're not yet to the specified resume step so
		# increment our step counter and continue on.
                self.incr_current_step()
                return 1
        return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_remove_state_file(self, step):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Remove the specified .step_ file from the system.
        """
        filename = step.get_state_file()
        try:
                os.remove(filename)
   	except OSError:
                pass
 
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_delete_checkpoint(self, step):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Delete the checkpoint. This will delete
        the zfs snapshot and .step file.
        """
	for zfs_dataset_name in step._zfs_snapshot : 
                # Destroy the snapshot!
                shell_cmd("/usr/sbin/zfs destroy " + zfs_dataset_name
		    + " >/dev/null 2>&1")
        DC_remove_state_file(self, step)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_verify_manifest_filename(name):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Verify the specified manifest file is readable.
        Returns
           0 - success
          -1 on error
        """
        try:
                file_name = open("%s" % name, "r")
        except (IOError):
                print "You have specified a file (%s) that is unable to " \
		    "be read." % name
                return -1 
   
        file_name.close() 
        return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_determine_checkpointing_availability(cp, manifest_defs):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Determine if checkpointing is available by reading
	the manifest file variable and checking to see if
	zfs is on they system. 
	"""

	# Check to see if checkpointing is disabled in the manifest file
	# If so, return
	if get_manifest_value(manifest_defs, CHECKPOINT_ENABLE).lower() == False:
		cp.set_checkpointing_enable(False)
		return

	# Check to see if checkpointing is disabled because zfs is not on
	# the system. If so, return
	for file in os.listdir('/usr/sbin'):
		if fnmatch.fnmatch(file, 'zfs'):
			return	

	# zfs not on the system so no checkpointing
	self.set_checkpointing_avail(False)
	self.set_zfs_found(False)
	return

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_checkpoint_setup(self):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Sets up and defines all checkpoints. All checkpoints must
        have an entry (in chronological order) here.
        """
        # for each step, create an entry in chronological order, with the
        # format: 
        # step_setup( message, [dataset list], name)
        #	message: the message to print to the screen to indicate the step
        #	dataset list: list with the names of the datasets to snapshot
        #	name: (optional) ascii name for the step.
        # NOTE: All checkpoints must have an entry here and a call to
        # DC_execute_checkpoint where you wish the checkpoint to actually take
        # place. The name specified in this function MUST be the
        # same as the name used in the DC_execute_checkpoint call. 

	pkg_image_dataset = self.get_pkg_image_dataset()
	# Checkpointing is possible so setup the steps.
        self.step_setup("Populating the package image area", [pkg_image_dataset]) 
        self.step_setup("Executing the Old DC", [pkg_image_dataset])
