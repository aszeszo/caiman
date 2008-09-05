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
import osol_install.finalizer
from osol_install.distro_const.dc_utils import get_manifest_value, get_manifest_list

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
        #   _zfs_snapshots - Name of the zfs snapshot. It is equal to the 
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
                return self._zfs_snapshots[num]

	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        def __init__(self, step_name, message, state_file,
                        zfs_dataset):
	#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                self._step_num = step.step_num 
                self._step_name = step_name 
                self._message = message 
                self._state_file= state_file 
                self._zfs_snapshots = []
	        for i, zfs_dataset_name in enumerate(zfs_dataset) : 
                        self._zfs_snapshots.insert(i,
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
                _zfs_snapshots - Name of the zfs snapshot. It is equal to the 
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
				for zfs_snapshot in step_obj._zfs_snapshots:
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
def step_from_name(cp, name) :
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
        for step_obj in cp.step_list:
                if name == step_obj.get_step_name():
                        return step_obj 
        print "An invalid step was specified."
        pstr = "Valid step names are: "
        for step_obj in cp.step_list :
                pstr += step_obj.get_step_name() + "  "    
        print pstr
        return None

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_determine_resume_step(cp):
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
	image_area = cp.get_pkg_image_mntpt()
	state_dir = image_area.rsplit(image_area[image_area.rfind("/"):])[0]
        for file in os.listdir(state_dir):
                if fnmatch.fnmatch(file, '.step_*'):
                        for step_obj in cp.step_list:
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
def DC_verify_resume_step(cp, num):
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
        laststep = DC_determine_resume_step(cp)
	if laststep == -1:
		print "There are no valid steps to resume from. "
		print "Please rerun the build without the -r or -R options."
		return -1
        if num > laststep:
                print "You must specify an earlier step to resume at."
                pstr = "Valid steps to resume from are: "
                pstr = pstr + cp.step_list[0].get_step_name()    
                for i in range (1, laststep):
                        pstr = pstr + " " + cp.step_list[i].get_step_name()    
                print pstr
                return -1
        return 0 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_verify_resume_state(cp):
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
	num = cp.get_resume_step()
        manifest = cp.get_manifest()
        for step_obj in cp.step_list:
                if num >= step_obj.get_step_num():
                        # Compare the .step<name> file to the manifest file.
                        # They should be the same since on step creation the
                        # manifest file was copied to the .step_<name> file
                        # unless the user has modified the manifest file. This
                        # could cause indeterminate results so we want to warn
                        # the user of this situation.
                       	if filecmp.cmp(step_obj.get_state_file(),
			    manifest, 0) == False:
		                change = 1
                                pstr += " %s" % step_obj.get_step_name()
        if (change) :
                print "WARNING: The manifest file, %s, has changed " % manifest
                print "since Step(s) %s was generated." % pstr 
                print "Results may be indeterminate."


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_checkpoint_script(cp, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	arglist = []
        currentstep = cp.get_current_step()
        pausestep = cp.get_pause_step()
	arglist.append(cp.get_manifest())
	arglist.append(cp.step_list[currentstep].get_state_file()) 
	for snapshot in cp.step_list[currentstep]._zfs_snapshots:
		arglist.append(snapshot)
	if currentstep == pausestep:
		arglist.append(" Stopping at Step %s. " % \
		    cp.step_list[currentstep].get_step_name())
	else:
		arglist.append(" Step %s: %s " % \
		    (cp.step_list[currentstep].get_step_name(),
		    cp.step_list[currentstep].get_step_message()))
	finalizer_obj.register(FINALIZER_CHECKPOINT_SCRIPT, arglist)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_rollback_script(cp, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	arglist = [] 
        currentstep = cp.get_current_step()
	for snapshot in cp.step_list[currentstep]._zfs_snapshots:
		arglist.append(snapshot)
	arglist.append(" Step %s: %s" % \
	    (cp.step_list[currentstep].get_step_name(),
	    cp.step_list[currentstep].get_step_message()))
	finalizer_obj.register(FINALIZER_ROLLBACK_SCRIPT, arglist)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def queue_up_finalizer_script(cp, finalizer_obj, manifest_server_obj, script,
    old_stdout_log, old_stderr_log):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	script_args = get_manifest_list(manifest_server_obj,
	    FINALIZER_SCRIPT_NAME_TO_ARGSLIST % script)
	stdout_log = get_manifest_value(manifest_server_obj,
	    FINALIZER_SCRIPT_NAME_TO_STDOUT_LOG % script)
	stderr_log = get_manifest_value(manifest_server_obj,
	    FINALIZER_SCRIPT_NAME_TO_STDERR_LOG % script)
	stop_on_err = get_manifest_value(manifest_server_obj,
	    STOP_ON_ERR)

	if not old_stdout_log == stdout_log or \
	    not old_stderr_log == stderr_log:
		finalizer_obj.change_exec_params(stdout_log,
		    stderr_log, stop_on_err)
		old_stdout_log = stdout_log
		old_stderr_log = stderr_log
	finalizer_obj.register(script, script_args) 
	cp.incr_current_step()
	return (old_stdout_log, old_stderr_log)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_add_finalizer_scripts(cp, manifest_server_obj, finalizer_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	"""
	Check to see if the finalizer script should be executed. It should only
	be executed if 1) checkpointing is available/on and 2) the steps to
	pause or resume at don't exclude it.
	
	Input:
		manifest_server_obj - Manifest server object 
		finalizer_obj - finalizer object
	Returns:
	"""

	finalizer_script_list = get_manifest_list(manifest_server_obj,
	    FINALIZER_SCRIPT_NAME)

	old_stdout_log = ""
	old_stderr_log = ""
        resumestep = cp.get_resume_step()
        pausestep = cp.get_pause_step()
	for script in finalizer_script_list:
		if script == "":
			continue

		if cp.get_checkpointing_avail() == False:
			# Queue up the finalizer script and return
			(old_stdout_log, old_stderr_log) = \
			    queue_up_finalizer_script(cp, finalizer_obj,
			    manifest_server_obj, script,
			    old_stdout_log, old_stderr_log)
			continue	

        	currentstep = cp.get_current_step()
        	if currentstep == pausestep:
			# Pause after checkpointing. This means we queue up the
			# checkpoint script but not the finalizer script. 
			queue_up_checkpoint_script(cp, finalizer_obj)
                	return 
        	if currentstep > resumestep:
			# We're past the resume step and we have checkpointing,
			# so register the checkpointing script and the finalizer
			# script.
			queue_up_checkpoint_script(cp, finalizer_obj)
			(old_stdout_log, old_stderr_log) = \
			    queue_up_finalizer_script(cp, finalizer_obj,
			    manifest_server_obj, script,
			    old_stdout_log, old_stderr_log)
			continue	
        	elif currentstep == resumestep:
			# At the specified step to resume from.
			# Register the rollback script and the finalizer script.
			queue_up_rollback_script(cp, finalizer_obj)
			(old_stdout_log, old_stderr_log) = \
			    queue_up_finalizer_script(cp, finalizer_obj,
			    manifest_server_obj, script,
			    old_stdout_log, old_stderr_log)
			continue	
		else :
			# We're not yet to the specified resume step so
			# increment our step counter and continue on.
                	cp.incr_current_step()
                	continue	

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_execute_checkpoint(cp, var):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Check to see if the step should be executed. If the step to resume at is
        less than the current step, create a checkpoint with specified name. The
        name must be the same as the name that  will be used in the step_setup
        call.
        NOTE: All checkpoints must have a call to step_setup in
        DC_checkpoint_setup and a call to DC_execute_checkpoint. The name MUST
        be the same for both function calls.
        Input:
            name - name of the step to check and the checkpoint to create.
        Returns:
            0 - execute the step
            1 - don't execute the step.
           -1 - stop execution on return 
        """
	if cp.get_checkpointing_avail() == False:
		return 0

        if isinstance(var, int):
                name = cp.step_list[var].get_step_name()
        elif isinstance(var, str):
	        name = var 
        else :
                print "Unable to execute checkpoint code due to invalid syntax"
                return (0)
        resumestep = cp.get_resume_step()
        pausestep = cp.get_pause_step()
        currentstep = cp.get_current_step()
        if pausestep == currentstep:
                cp.create_checkpoint(name)
                return -1 
        if currentstep > resumestep:
                if cp.create_checkpoint(name):
                        print "An error occurred when creating the checkpoint. "
                        print "Checkpointing functionality is unavailable" 
        elif currentstep == resumestep:
		# At the specified step to resume from. Rollback
		# to the zfs snapshot.
		for zfs_dataset_nm in cp.step_list[resumestep]._zfs_snapshots:
                	shell_cmd("/usr/sbin/zfs rollback "
			    + zfs_dataset_nm + " >/dev/null 2>&1")
                cp.incr_current_step()
	else :
		# We're not yet to the specified resume step so
		# increment our step counter and continue on.
                cp.incr_current_step()
                return 1
        return 0

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_remove_state_file(step):
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
def DC_delete_checkpoint(cp, step):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Delete the checkpoint. This will delete
        the zfs snapshot and .step file.
        """
	for zfs_dataset_name in step._zfs_snapshots : 
                # Destroy the snapshot!
                shell_cmd("/usr/sbin/zfs destroy " + zfs_dataset_name
		    + " >/dev/null 2>&1")
        DC_remove_state_file(step)

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
def DC_determine_checkpointing_availability(cp, manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
	""" Determine if checkpointing is available by reading
	the manifest file variable and checking to see if
	zfs is on they system. 
	"""

	# The checkpointing available is set to true by default in the
	# checkpointing class __init__ method. Here we check to see if
	# checkpointing is disabled in the manifest file. If so, return
	if get_manifest_value(manifest_server_obj,
	    CHECKPOINT_ENABLE).lower() == "false":
		cp.set_checkpointing_avail(False)
		return

	# Check to see if checkpointing is disabled because zfs is not on
	# the system. If so, return
	for file in os.listdir('/usr/sbin'):
		if fnmatch.fnmatch(file, 'zfs'):
			return	

	# zfs not on the system so no checkpointing
	cp.set_checkpointing_avail(False)
	cp.set_zfs_found(False)
	return

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_checkpoint_setup(cp, manifest_server_obj):
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

	pkg_image_dataset = cp.get_pkg_image_dataset()
	finalizer_script_list = get_manifest_list(manifest_server_obj,
	    FINALIZER_SCRIPT_NAME)

        cp.step_setup("Populating the package image area",
	    [pkg_image_dataset]) 

	# Set up a checkpoint for each finalizer script specified.
	for script in finalizer_script_list:
		cp.step_setup("Executing " + script, [pkg_image_dataset])

