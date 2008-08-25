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
import sys
import os

from osol_install.TreeAcc import TreeAcc
from osol_install.distro_const.DC_checkpoint import *
from osol_install.distro_const.DC_ti import *
from osol_install.distro_const.DC_tm import *
from osol_install.distro_const.dc_utils import *

execfile("/usr/lib/python2.4/vendor-packages/osol_install/distro_const/DC_defs.py")

#
# Print the usage statement and exit
def usage():
        print ("""\
Usage:
        dist_const command [options] [operands] <manifest-file>

Basic subcommands:
        dist_const build [-Rq] [-r <step>] [-p <step>] <manifest-file>
	""")
        sys.exit(2)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_get_manifest_file_defs(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Read the manifest file from the command line
        try:
		opts2, pargs2 = getopt.getopt(sys.argv[2:], "r:p:hRq?")
        except:
                usage()

	if len(pargs2) == 0:
		usage()

	manifest_file = pargs2[0] 
	err = DC_verify_manifest_filename(manifest_file)
	if err != 0: 
		return -1
	cp.set_manifest(manifest_file)
	return TreeAcc(manifest_file)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_image_info(manifest_defs, mntpt):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Create the .image_info file in the pkg image root directory.
        The file should contain the name value pair:
        IMAGE_SIZE=<size of distribution>

        Args:
           manifest_defs: An initialized TreeAcc instance
           mntpt: mount point to create .image_info in.

        Returns:
           None

        Raises:
           None
        """
        cmd = "/bin/du -sk %s | awk '{print $1}' " % mntpt
        image_size = int(Popen(cmd, shell=True,
	    stdout=PIPE).communicate()[0].strip())
        try:
                image_file = open(mntpt + "/.image_info", "w+")
                image_file.write("IMAGE_SIZE=" + str(image_size))
                image_file.flush()
                image_file.close()
        except:
                pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_parse_command_line(cp, manifest_defs):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Parse the command line options. 
        usage: dist_const build [-R] manifest-file
            dist_const build [-r <integer or string>] manifest-file
            dist_const build [-p <integer or string>] manifest-file
            dist_const build [-q] manifest-file

            -R will resume from the last executed step
            -r will resume from the specified step
            -p will pause at the specified step
            -q will list the valid steps to resume/pause at

        Also, verify that the pause step and the resume step are valid. The
        pause step must be one of the steps. The resume step must be less than
        or equal to the last step executed.  This method will also remove the
        zfs snapshots and the .step file for steps equal to or that come after
        the step where execution will start. For a full build or a pause, this
        means all checkpoints will be removed. For a resume, the checkpoint to
        be resumed from and all later checkpoints are removed.
        Return 0 = success
               1 = success but don't continue on with building.
              -1 = Error
        """

        subcommand = sys.argv[1] 

	# See if the user has specified a step to resume from in the manifest
	# file. If so, keep it around. If the user has also specified one on
	# the command line, that will overwrite the manifest value.
	stepno = int(get_manifest_value(manifest_defs,
	    CHECKPOINT_RESUME))
	if stepno:
		cp.set_resume_step(stepno)	

	# Read the command line arguments and parse them.
        try:
		opts2, pargs2 = getopt.getopt(sys.argv[2:], "r:p:hRq?")
        except:
                usage()
        if subcommand == "build":
                for opt, arg in opts2:
	                if (opt == "-h") or (opt == "-?"): 
                                usage()
                        if opt == "-r":
                                # resume from the specified step. 
                                step = step_from_name(cp, arg)
                                if step == None:
                                        return -1
                                stepno = step.get_step_num()
                                err = DC_verify_resume_step(
                                    cp, stepno)
                                if err != 0 :
                                        return -1
                                cp.set_resume_step(stepno)
                        elif opt == "-p":
                                # pause at the specified step. 
                                step = step_from_name(cp, arg)
                                if step == None:
                                        return -1
                                stepno = step.get_step_num()
                                cp.set_pause_step(stepno)
                        elif opt == "-R":
                                # resume from the last executed step. 
                                stepno = DC_determine_resume_step(cp)
                                cp.set_resume_step(stepno)
                        elif opt == "-q":
				if not cp.get_checkpointing_avail():
					print "Checkpointing is not available"
					return 1

                                # query for valid resume/pause steps
                                laststep = DC_determine_resume_step(cp)
		                if laststep == -1 : 
                                        print "The -r option is not valid " \
                                            "until you perform a build"
                                else :
                                        pstr = "Valid steps to resume from are: "
                                        pstr += cp.step_list[0].get_step_name()
                                        for step_obj in \
					    cp.step_list[1: laststep+1]:
                                                pstr += ", " + \
						    step_obj.get_step_name()  

                                pstr += "\nValid steps to pause at are: "
                                pstr += cp.step_list[0].get_step_name()
                                for step_obj in cp.step_list[1:] :
                                        pstr += ", " + step_obj.get_step_name()
				print pstr
                                return 1 
    
                if cp.get_pause_step() <= cp.get_resume_step() :
                        print "The resume step must be earlier than "\
                            "the pause step."
                        usage()
                if cp.get_resume_step() != -1 :
                        DC_verify_resume_state(cp)
                        # destroy all zfs snapshots and .step files for 
                        # steps after the resume step 
                        for step_obj in cp.step_list[cp.get_resume_step() + 1:]:
                                DC_delete_checkpoint(cp, step_obj)
                else : 
                        # Delete all zfs snapshots and .step files
                        for step_obj in cp.step_list:
                                DC_delete_checkpoint(cp, step_obj)

        else :
                # Currently we only support the build subcommand
	        usage()
        return 0
     
#
# Main distribution constructor function.
#
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main_func():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        cp = checkpoints()

	manifest_defs = DC_get_manifest_file_defs(cp)

	# create the pkg image area and determine if
	# checkpointing is available.
	if DC_create_pkg_image_area(cp, manifest_defs):
		return 

        # Set up the structures for all checkpoints
	if cp.get_checkpointing_avail() == True:
        	DC_checkpoint_setup(cp)

        # Parse the command line so we know to resume (and where) or not
        if DC_parse_command_line(cp, manifest_defs):
                return 

	# Create the tmp directory we use for multiple purposes.
	tmp_dir = create_tmpdir()

	if tmp_dir == None:
               	print "Unable to create the tmp directory"
               	return -1

	# Use IPS to populate the pkg image area
        # Corresponding entry must exist in DC_checkpoint_setup.
        # Entry:
	# self.step_setup("Populating the package image area", [pkg_image])
	status = DC_execute_checkpoint(cp, 0)
	if status == 0:
		cleanup_dir(cp.get_pkg_image_mntpt())
        	if DC_populate_pkg_image(cp.get_pkg_image_mntpt(),
		    tmp_dir, manifest_defs) != 0:
			cleanup_tmpdir(tmp_dir)
			return
		# Create the .image_info file in the pkg_image directory
		DC_create_image_info(manifest_defs, cp.get_pkg_image_mntpt())
	elif status == -1:
		cleanup_tmpdir(tmp_dir)
		return

	# Call the old DC script to finish the build. 
        # Corresponding entry must exist in DC_checkpoint_setup.
        # Entry: self.step_setup("Executing the Old DC", [pkg_image])
	status = DC_execute_checkpoint(cp, 1)
	if status == 0:
		output_area = get_manifest_value(manifest_defs,
		   OUTPUT_PATH)
		dist_iso = output_area + "/" + get_manifest_value(manifest_defs,
		    "name") + ".iso "
        	cmd = "./build_dist.bash " + \
	  	    cp.get_pkg_image_mntpt() + " " + dist_iso + " " + tmp_dir
		shell_cmd(cmd)

	cleanup_tmpdir(tmp_dir)
        return

if __name__ == "__main__":
        try:
                main_func()
        except SystemExit, e:
                raise e
        except:
                sys.exit(1)

