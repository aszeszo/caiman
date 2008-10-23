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
import atexit
import logging
from osol_install.finalizer import DCFinalizer
from osol_install.ManifestServ import ManifestServ

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
	distro_const build -R <manifest-file>
	distro_const build -r <step name or number> <manifest-file>
	distro_const build -p <step name or number> <manifest-file>
	distro_const build -l <manifest_file>
	""")
        sys.exit(2)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_get_manifest_server_obj(cp):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        subcommand = sys.argv[1] 
	if subcommand != "build":
		print "Invalid or missing subcommand"
		usage()

	# Read the manifest file from the command line
        try:
		opts2, pargs2 = getopt.getopt(sys.argv[2:], "r:p:hRl?")
        except:
                usage()

	if len(pargs2) == 0:
		usage()

	manifest_file = pargs2[0] 
	err = DC_verify_manifest_filename(manifest_file)
	if err != 0: 
		raise Exception, ""
	cp.set_manifest(manifest_file)
	return  ManifestServ(manifest_file, DC_MANIFEST_DATA)
		

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_start_manifest_server(manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	manifest_server_obj.start_socket_server()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_create_image_info(manifest_server_obj, mntpt):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Create the .image_info file in the pkg image root directory.
        The file should contain the name value pair:
        IMAGE_SIZE=<size of distribution>

        Args:
           manifest_server_obj: The Manifest Server object 
           mntpt: mount point to create .image_info in.

        Returns:
           None

        Raises:
           None
        """
        cmd = "/bin/du -sk %s | awk '{print $1}' " % mntpt
        image_size = int(Popen(cmd, shell=True,
	    stdout=PIPE).communicate()[0].strip())
	dc_log = logging.getLogger(DC_LOGGER_NAME)
        try:
                image_file = open(mntpt + "/.image_info", "w+")
                image_file.write("IMAGE_SIZE=" + str(image_size))
                image_file.flush()
                image_file.close()
        except:
		dc_log.error("Error in creating " + mntpt + "/.image_info")
                pass

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def DC_parse_command_line(cp, manifest_server_obj):
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        """
        Parse the command line options. 
        usage: dist_const build [-R] manifest-file
            dist_const build [-r <integer or string>] manifest-file
            dist_const build [-p <integer or string>] manifest-file
            dist_const build [-l] manifest-file

            -R will resume from the last executed step
            -r will resume from the specified step
            -p will pause at the specified step
            -l will list the valid steps to resume/pause at

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
	stepno = int(get_manifest_value(manifest_server_obj,
	    CHECKPOINT_RESUME))
	if stepno:
		cp.set_resume_step(stepno)	

	# Read the command line arguments and parse them.
        try:
		opts2, pargs2 = getopt.getopt(sys.argv[2:], "r:p:hRl?")
        except:
                usage()
        if subcommand == "build":
		step_resume = False
		resume = False
		pause = False
		list = False
                for opt, arg in opts2:
	                if (opt == "-h") or (opt == "-?"): 
                                usage()

			# Since all command line opts have to do with 
			# checkpointing, check here to see
			# if checkpointing is available.
			if not cp.get_checkpointing_avail():
				print "Checkpointing is not available"
				print "Rerun the build without " + opt 
				return 1

                        if opt == "-r":
				# Check to see if -r has already been specified
				if step_resume == True:
					usage()

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
				step_resume = True
                        elif opt == "-p":
				# Check to see if -p has already been specified
				if pause == True:
					usage()

                                # pause at the specified step. 
                                step = step_from_name(cp, arg)
                                if step == None:
                                        return -1
                                stepno = step.get_step_num()
                                cp.set_pause_step(stepno)
				pause = True
                        elif opt == "-R":
                                # resume from the last executed step. 
                                stepno = DC_determine_resume_step(cp)
				if stepno == -1:
					print "There are no valid steps to resume from." 
					print "Please rerun the build without the -r or -R options."
					return -1
                                cp.set_resume_step(stepno)
				resume = True
                        elif opt == "-l":
				list = True

		# -R and -r not allowed on the same command line.
		if resume == True and step_resume == True:
			print "-R and -r cannot be specified for the same build. "
			usage()

		# -l and -R, -r, or -p combination not allowed. -l must be the only option.
		if list == True and (pause == True or resume == True or step_resume == True):
			print "-l and -R, -r, or -p cannot be specified for the same build"
			usage()
	
		# We've checked for the bad combos. If a -l was specified, print out the info.
		if list == True:
                	# query for valid resume/pause steps
			# All steps are valid to pause at. The
			# steps that are valid to resume from
			# will be marked "resumable"
                        laststep = DC_determine_resume_step(cp)
			print "\nStep           Resumable Description"
			print "-------------- --------- -------------"
                        for step_obj in cp.step_list:
				if not laststep == -1 and step_obj.get_step_num() <= laststep:
					r_flag = "X"
				else:
					r_flag = " "	
				print "%s%s%s" % \
				    (step_obj.get_step_name().ljust(15),
				    r_flag.center(10),
				    step_obj.get_step_message().ljust(10))
			return 1 
    
		# If -r/-R and -p were both specified, the pause step must be later than the resume.
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
		print "Invalid or missing subcommand"
	        usage()
        return 0

#
# Main distribution constructor function.
#
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def main_func():
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

	# Must be root to run DC. Check for that.
	if not os.getuid() == 0:
		print "You must be root to run distro_const"
		return 1

        cp = checkpoints()

	try:
		# Create the object used to extract the data
		manifest_server_obj = DC_get_manifest_server_obj(cp)

		# Start the socket server
		DC_start_manifest_server(manifest_server_obj)

		# Set up to shut down socket server cleanly on exit
		atexit.register(manifest_server_obj.stop_socket_server)
	except:
		return 1

	# create the build area and determine if
	# checkpointing is available. When creating the
	# build area we also create the areas for the
	# package image (pkg_image), output media (media),
	# logfiles (logs) and bootroot (bootroot).
	if DC_create_build_area(cp, manifest_server_obj):
		return 1

        # Set up the structures for all checkpoints
	if cp.get_checkpointing_avail() == True:
        	if DC_checkpoint_setup(cp, manifest_server_obj):
			return 1

        # Parse the command line so we know to resume (and where) or not
        if DC_parse_command_line(cp, manifest_server_obj):
                return 1

	# The build is going to start, will start logging
	(simple_log_name, detail_log_name) = setup_dc_logfile_names(cp.get_build_area_mntpt() + LOGS)
	dc_log = setup_dc_logging(simple_log_name, detail_log_name)
	dc_log.info("Simple Log: " + simple_log_name)
	dc_log.info("Detail Log: " + detail_log_name)

	dc_log.info("Build started " + time.asctime(time.localtime())) 
	dc_log.info("Distribution name: " +
	    (get_manifest_value(manifest_server_obj, DISTRO_NAME)))
	dc_log.info("Build Area dataset: " + cp.get_build_area_dataset())
	dc_log.info("Build Area mount point: " + cp.get_build_area_mntpt())

	# Use IPS to populate the pkg image area
        # Corresponding entry must exist in DC_checkpoint_setup.
        # Entry:
	# self.step_setup("Populating the package image area",
	#     [build_area_dataset])
	status = DC_execute_checkpoint(cp, 0)
	if status == 0:
		cleanup_dir(cp.get_build_area_mntpt() + PKG_IMAGE)
        	if DC_populate_pkg_image(cp.get_build_area_mntpt() + PKG_IMAGE,
		    cp.get_build_area_mntpt() + TMP, manifest_server_obj) != 0:
			cleanup_dir(cp.get_build_area_mntpt() + TMP)
			return 1
		# Create the .image_info file in the pkg_image directory
		DC_create_image_info(manifest_server_obj,
		    cp.get_build_area_mntpt() + PKG_IMAGE) 
	elif status == -1:
		cleanup_dir(cp.get_build_area_mntpt() + TMP)
		return 1

	stop_on_err_bool = (((get_manifest_value(manifest_server_obj,
	    STOP_ON_ERR)).lower()) == "true")

	# register the scripts with the finalizer
	build_area = cp.get_build_area_mntpt()
	pkg_img_area = build_area + PKG_IMAGE
	tmp_area = build_area + TMP
	br_build_area = build_area + BOOTROOT
	media_dir = build_area + MEDIA

	finalizer_obj = DCFinalizer([manifest_server_obj.get_sockname(),
	    pkg_img_area, tmp_area, br_build_area, media_dir])
	if (finalizer_obj.change_exec_params(stop_on_err=stop_on_err_bool,
	    logger_name=DC_LOGGER_NAME) != 0):
		dc_log.error("Unable to set stop on error or logger name for finalizer")
	
	DC_add_finalizer_scripts(cp, manifest_server_obj, finalizer_obj,
	    simple_log_name, detail_log_name)

	# Execute the finalizer scripts
	rv = finalizer_obj.execute()

	cleanup_dir(cp.get_build_area_mntpt() + TMP)
        return (rv)

if __name__ == "__main__":
	rv = 1 #this will be set to 0 if main_func() succeed
	try:
        	try:
                	rv = main_func()
        	except SystemExit, e:
                	raise e
        	except Exception, ex:
			print ex
			pass
	finally:
		dc_log = logging.getLogger(DC_LOGGER_NAME)
		dc_log.info("Build completed " + time.asctime(time.localtime()))
		if (rv != 0):
			dc_log.info("Build failed.")
		else:
			dc_log.info("Build is successful.")

	sys.exit(rv)
