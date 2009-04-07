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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
# Slim Install Transfer Module
#
import os
import errno
import time
import sys
import shutil
import traceback
import fcntl
import array
import string
import threading
import logging
import operator
from stat import *
from subprocess import *
from osol_install.install_utils import *

#
# Modules specific to Slim Install
#
import liblogsvc as logsvc
import libtransfer as tmod

class TM_defs(object):
	"""Class that holds some globally used values
        """
	MAX_NUMFILES = 200000.0
	FIND_PERCENT = 4
	KBD_DEVICE = "/dev/kbd"
	CPIO = "/usr/bin/cpio"
	PKG = "/usr/bin/pkg"
	KBD_LAYOUT_FILE = "/usr/share/lib/keytables/type_6/kbd_layouts"
	KBD_DEFAULTS_FILE = "etc/default/kbd"

	def __init__(self):
		self.tm_lock = None
		self.do_abort = 0
		self.percent = 0.0

class Cpio_spec(object):
	"""Class used to hold values specifying a mountpoint for cpio operation
        """
	def __init__(self, chdir_prefix=None, cpio_dir=None,
	    match_pattern=None,  clobber_files=0, cpio_args="pdum",
	    file_list=None):
		self.chdir_prefix = chdir_prefix
		self.cpio_dir = cpio_dir
		self.match_pattern = match_pattern
		self.clobber_files = clobber_files
		self.cpio_args = cpio_args
		self.file_list = file_list

class Flist(object):
	"""Class used to hold file list entries for cpio operation
        """
	def __init__(self, name=None, chdir_prefix=None, clobber_files=0,
	    cpio_args=None):
		self.name = name
		self.chdir_prefix = chdir_prefix
		self.clobber_files = clobber_files
		self.cpio_args = cpio_args

	def open(self):
		self.handle = open(self.name, "w+")

class TError(Exception):
	"""Base class for Transfer Module Exceptions.
        """
	pass

class TValueError(TError):
	"""Exception raised for errors in the input key/value list.

	Attributes:
	   message -- explanation of the error
	   retcode -- error return code
	"""

	def __init__(self, message, retcode):
		self.message = message
		self.retcode = retcode

class TAbort(TError):
	"""Exception raised when the caller requests to abort transfer
	operation midway or a failure is detected.
	
	Attributes:
	   message -- explanation of the abort operation
	   retcode -- error return code
	"""
	
	def __init__(self, message, retcode = errno.EINTR):
		self.message = message
		self.retcode = retcode

class TIPSPkgmissing :
	"""Exception raised if an IPS package is missing
	Attribute: retcode -- error return code
	"""

	def __init__(self, retcode = errno.ENOENT):
		self.retcode = retcode

def tm_abort_transfer() :
	""""Method to signal to abort the transfer
	"""
	if params.tm_lock.locked():
		params.tm_lock.release()	
        else: 
                params.do_abort = 1;

def tm_abort_signaled():
	"""Method to detect abort
	"""
	return params.do_abort

class ProgressMon(object):

	def startmonitor(self, fs, distrosize, message, initpct=0, endpct=100):
		"""Start thread to monitor progress in populating file system
			fs - file system to monitor
			distrosize = full distro size in kilobytes
			message = progress message to log. 
			initpct = base percent value from which to start
			    calculating.
			endpct = percentage value at which to stop calculating
		"""
		self.message =	message
		self.distrosize = distrosize
		self.initpct = initpct
		self.endpct = endpct
		self.done = False
		self.thread1 = threading.Thread( target=self.__progressthread,
		    args=( fs,))
		self.thread1.start()
		return 0

	def wait(self):
		self.thread1.join()

	def __progressthread(self, fs):
		"""Monitor progress in populating file system
			fs - file system to monitor
		"""
		initsize = self.__fssize(fs)
		totpct = self.endpct - self.initpct
		prevpct = -1 

		# Loop until the user aborts or we're done transferring.
		# Keep track of the percentage done and let the user know
		# how far the transfer has progressed.
		while 1:
			# Compute increase in fs size
			fssz = self.__fssize(fs)
			if (fssz == -1):
				return -1
			fsgain = fssz - initsize

			# Compute percentage transfer
			actualpct = fsgain * 100 / self.distrosize
			# Compute percentage transfer in terms of stated range
			pct = fsgain * totpct / self.distrosize + self.initpct
			# Do not exceed limits
			if pct >= self.endpct or actualpct > 100:
				pct = self.endpct	
			# If the percentage has changed at all, log the
			# progress so the user can see something is going on.
			if (pct != prevpct):
				tmod.logprogress(int(pct), self.message)
				prevpct = pct
			if pct >= self.endpct:
				return 0
			time.sleep(2)
			if tm_abort_signaled() or self.done:
				return 0

	def __fssize(self, fs):
		"""Find the current size of the specified file system.
			fs - file system to monitor
		Returns the size of the filesystem in kilobytes
		"""	
		cmd = "/usr/bin/df -k " + fs
		p  = os.popen(cmd)
		# Read the header and throw it away....
		dfout = p.readline()
		if not dfout:
			logsvc.write_log(TRANSFER_ID, "FS size computation " +
			    "failed for " + fs + "\n")
			return -1
		# read the line with the size information.
		dfout = p.readline()
		if not dfout:
			logsvc.write_log(TRANSFER_ID, "FS size computation " +
			    "failed for " + fs + "\n")
			return -1
		# and yank out the size information
		line_tokens = dfout.split()
		return int(line_tokens[2])


class Transfer_cpio(object):
	"""This class contains all the methods used to actually transfer
	files from the src_mntpt or / to the dst_mntpt
        """

	def __init__(self):
		self.dst_mntpt = ""
		self.src_mntpt = ""
		self.cpio_action = "" 
		self.cpio_args = "pdum"
		self.list_file = ""
		self.skip_file_list = ""
		self.tformat = "%a, %d %b %Y %H:%M:%S +0000"
		self.debugflag = 0 
		self.cpio_prefixes = []
		self.image_info = ""
		self.distro_size = 0
		self.log_handler = None

		# TODO: This is live media specific and shouldn't be part
		# of transfer mod.
		# List of toplevel directories that should be transferred
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/", \
		    cpio_dir="."))
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/", \
		    cpio_dir="usr"))
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/", \
		    cpio_dir="opt"))
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/", \
		    cpio_dir="dev"))
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/mnt/misc", \
		    cpio_dir=".", clobber_files=1, cpio_args="pdm"))
		# When a file_list is provided, the cpio operation
		# will be done to the list of files provided in that file.
		# There will not be a os.walk() of the "chdir_prefix".
		# The "chdir_prefix" value is still important here, because
		# the content list is generated assuming "chdir_prefix"
		# is the root.
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/.cdrom", \
		    cpio_dir=".", file_list="/.cdrom/.livecd-cdrom-content"))
			
	
	def info_msg(self, msg):
		"""Log an informational message to logging service
                """
		if (self.log_handler != None):
			self.log_handler.info(msg)
		else:
			logsvc.write_log(TRANSFER_ID, msg + "\n")

	def prerror(self, msg):
		"""Log an error message to logging service and stderr
                """
		if (self.log_handler != None):
			self.log_handler.error(msg)
		else:
			msg1 = msg + "\n"
			logsvc.write_dbg(TRANSFER_ID, logsvc.LS_DBGLVL_ERR,
			    msg1)
			sys.stderr.write(msg1)
			sys.stderr.flush()

	def dbg_msg(self, msg):
		"""Log detailed debugging messages to logging service
                """
		if (self.log_handler != None):
			self.log_handler.debug(msg)
		else:
			if (self.debugflag > 0):
				logsvc.write_dbg(TRANSFER_ID,
				    logsvc.LS_DBGLVL_INFO, msg + "\n")

	# TODO : This shouldn't be part of transfer_mod
	def do_clobber_files(self, flist_file):
		"""Given a file containing a list of pathnames this function
                will search for those entries in the alternate root and
                delete all matching pathnames from the alternate root that
                are symbolic links.
                This process is required because of the way the LiveCD env
                is constructed. Some of the entries in the boot_archive are
                symbolic links to files mounted off a compressed lofi file.
                This is done to drastically reduce space usage by the
                boot_archive.
		"""
                self.dbg_msg("File list for clobber: " + flist_file)
                fh = open(flist_file, 'r')
                os.chdir(self.dst_mntpt)
		for line in fh:
                        line = line[:-1]

                        try:
                                mst = os.lstat(line)
                                if S_ISLNK(mst.st_mode):
                                        self.dbg_msg("Unlink: " + line)
                                        os.unlink(line)
                        except OSError:
                                pass
                fh.close()

	# TODO: This shouldn't be part of transfer_mod
	def get_kbd_layout_name(self, lnum):
		"""Given a keyboard layout number return the layout string.
		We should not be doing this here, but unfortunately there
		is no interface in the OpenSolaris keyboard API to perform
		this mapping for us - RFE.
                """
		fh = open(TM_defs.KBD_LAYOUT_FILE, 'r')

		name = ""
		for line in fh:
			if line[0] == '#':
				continue

			if line.find('=') == -1:
				continue

			(name, num) = line.split('=')
			if int(num) == lnum:
				break
		fh.close()
		return name

	def check_abort(self):
		if tm_abort_signaled() == 1:
			raise TAbort("User aborted transfer")

	def build_cpio_entire_file_list(self):
		"""Do a file tree walk of all the mountpoints provided and
		build up pathname lists. Pathname lists of all mountpoints
		under the same prefix are aggregated in the same file to
		reduce the number of cpio invocations.
		"""	
		
		self.info_msg("-- Starting transfer process, " +
		    time.strftime(self.tformat) + " --")
		self.check_abort()

		tmod.logprogress(0, "Building file lists for cpio")

		if self.src_mntpt != "" and self.src_mntpt != "/":
			self.cpio_prefixes = []
			self.cpio_prefixes.append(Cpio_spec(
			    chdir_prefix=self.src_mntpt, cpio_dir=".",
			    cpio_args=self.cpio_args))

		total_find_percent = (len(self.cpio_prefixes) - 1) * \
		    TM_defs.FIND_PERCENT

		# Get the optimized libc overlay out of the way.
		# Errors from umount intentionally ignored
		os.system("umount /lib/libc.so.1")

		self.info_msg("Building cpio file lists")

		# set up some variables with startup values.
		opercent = 0.0

		# Original values to compare against to see if
		# we need to generate a different list of files
		# to cpio.
		old_cprefix = ""
		patt = None
		i = 0
		nfiles = 0.0
		# file entry list. List of files containing the files
		# to cpio.
		fent_list = []
		fent = None
		self.check_abort()

		#
		# Do a file tree walk of all the mountpoints provided and
		# build up pathname lists. Pathname lists of all mountpoints
		# under the same prefix are aggregated in the same file to
		# reduce the number of cpio invocations.
		#
		# This loop builds a list where each entry points to a file
		# containing a pathname list and mentions other info like the
		# mountpoint from which to copy etc.
		#
		for cp in self.cpio_prefixes:
			self.dbg_msg("Cpio dir: " + cp.cpio_dir +
			    " Chdir to: " + cp.chdir_prefix)
			patt = cp.match_pattern
			self.check_abort()

			if patt != None and patt[0] == '!':
				negate = 1
				patt = patt[1:]
			else:
				negate = 0

			# Check to be sure the specified cpio source
			# directory is accessable.
			st = None
			try:
				os.chdir(cp.chdir_prefix)
				st = os.stat(cp.cpio_dir)
			except OSError:
				raise TAbort("Failed to access Cpio dir: " +
				    traceback.format_exc(),
				    TM_E_CPIO_ENTIRE_FAILED)

			# Create a new file if the prefix, or cpio_args 
			# or clobber files, have changed, or a
			# file containing a pre-generated list of
			# content is provided.
			if (old_cprefix != cp.chdir_prefix or
			    patt != None or
			    cp.clobber_files == 1 or cp.cpio_args != None or
			    cp.file_list != None):
				# create a file in the dst_mntpt area of
				# name flist<number> that will contain the
				# list of files to cpio
				fent = Flist()
				fent_list.append(fent)
				old_cprefix = cp.chdir_prefix
				fent.name = self.dst_mntpt + "/flist" + str(i)
				fent.open()
				i = i + 1
				self.dbg_msg(" File list tempfile:" +
				    fent.name)
				fent.handle = open(fent.name, "w+")
				fent.chdir_prefix = cp.chdir_prefix
				fent.clobber_files = cp.clobber_files
				if (cp.cpio_args):
					fent.cpio_args = cp.cpio_args

			# If the matching pattern is negated (!)
			# flag this and remove the ! from the pattern
			# before compiling it.
			if (patt != None):
				cpatt = re.compile(patt)

			self.info_msg("Scanning " + cp.chdir_prefix + "/" +
			    cp.cpio_dir)

			# This is for temporarily storing the list of inode
			# numbers and their corresponding file names.  This
			# list will later be sorted by the inode number before
			# it is written out to the cpio file list.
			tmp_flist=[]

			if (cp.file_list):
				try:
					image_content = open(cp.file_list, 'r')
				except IOError:
					raise TAbort("Failed to access " +
					    cp.file_list,
					    TM_E_INVALID_CPIO_FILELIST_ATTR)

				for fname in image_content:

					# Remove the '\n' character from
					# each of the lines read from the file
					if (fname[-1:] == '\n'):
						fname = fname[:-1]
					try:
						st1 = os.lstat(fname)
					except Exception, ex:
						self.info_msg("Warning: Error" +
						    " processing " + fname +
						    "from file " + cp.file_list)
						continue

					# Store the extent location of the
					# hsfs file and the filename to a 
					# temporary list
					tmp_flist.append((st1.st_ino, fname))
			else:
				#
				# os.walk does not recurse into directory
				# symlinks so nftw(..., FTW_PHYS) is satisfied.
				# In addition, we want to restrict our search
				# only to the current filesystem which is
				# handled below.
				#
				for root, dirs, files in os.walk(cp.cpio_dir):
					self.check_abort()
					for name in files:
						match = None
						fname = root + "/" + name
						if patt != None:
							match = \
							    cpatt.match(name)
							# If we have a match on
							# the name but the
							# pattern was !, then
							# that's really a
							# non-match.  Also, if
							# no match is found
							# but the pattern
							# was not ! it's a
							# non-match.
							if (match != None \
							    and negate == 1) \
							    or (match == None \
							    and negate != 1):
								self.dbg_msg(
								    "Non " \
								    "match. " \
								    "Skipped:" \
								    + fname)
								continue

						try:
							st1 = os.lstat(fname)
						except:
							self.info_msg(
							    "Warning: Error" +
							    " processing " +
							    fname)
							continue

						# Store the extent location of 
						# the hsfs file and the
						# filename to a temporary list
						tmp_flist.append((st1.st_ino,
						    fname))

						nfiles = nfiles + 1
						params.percent = int(nfiles /
						    TM_defs.MAX_NUMFILES *
						    total_find_percent)
						if params.percent - opercent \
						    > 1:
							tmod.logprogress(
							    params.percent,
							    "Building cpio " \
							    "file lists")
							opercent = \
							    params.percent

					#
					# Identify directories that we do not
					# want to traverse.  These are those
					# that can't be read for some reason
					# or those holding other mounted
					# filesystems.
					#
					rmlist = []
					for name in dirs:
						dname = root + "/" + name
						try:
							st1 = os.stat(dname);
						except:
							rmlist.append(name)
							continue

						# Store the extent location of 
						# the hsfs file and the
						# filename to a temporary list
						tmp_flist.append((st1.st_ino,
						    dname))

						# Emulate nftw(..., FTW_MOUNT)
						# for directories.
						if st1.st_dev != st.st_dev:
							rmlist.append(name)

					#
					# Remove directories so that they are
					# not traversed.   os.walk allows dirs
					# to be modified in place.
					#
					for dname in rmlist:
						dirs.remove(dname)

			# Write file list out to the file, after sorting
			# by the inode number, which is the first item
			tmp_flist.sort(key=operator.itemgetter(0))
			lf = fent.handle
			for f in map(operator.itemgetter(1), tmp_flist):
				lf.write(f + "\n")
			lf.flush()
				
		for fent in fent_list:
			fent.handle.close()
			fent.handle = None
		return fent_list

	def cpio_skip_files(self):
		"""Function to remove the files listed in the skip file list.
		Copying and then deleting the files is equivalent to not copying
		them at all or "skipping" them.
		"""
		try:
			skip_file = open(self.skip_file_list, 'r')
		except IOError:
			raise TAbort("Failed to access " +
			    self.skip_file_list, TM_E_INVALID_CPIO_ACT_ATTR)

		for line in skip_file:
			os.unlink(self.dst_mntpt + "/" + line.rstrip())
			
		skip_file.close()
		
	def cpio_transfer_entire_directory(self):
		fent_list = self.build_cpio_entire_file_list()
		self.cpio_transfer_filelist(fent_list, TM_E_CPIO_ENTIRE_FAILED)
		for fent in fent_list:
			os.unlink(fent.name)
			fent.name = ""

		if self.skip_file_list:
			self.cpio_skip_files()

	def cpio_transfer_filelist(self, fent_list, err_code):
		self.info_msg("Beginning cpio actions")

		#
		# Now process each entry in the list. cpio is executed with the
		# -V option where it prints a dot for each pathname processed.
		# This is needed to provide the ability to abort midway.
		#

		#
		# Start the disk space monitor thread
		#
		if self.distro_size:
			pmon = ProgressMon()
			pmon.startmonitor(self.dst_mntpt, self.distro_size,
			    "Transferring Contents", params.percent, 95)

		# There may be more than 1 file with a list of files to
		# cpio. If so, cycle through them.	
		for fent in fent_list:
			self.check_abort()

			if fent.clobber_files == 1:
				self.do_clobber_files(fent.name)

			try:
				os.chdir(fent.chdir_prefix)
			except OSError:
				raise TAbort("Failed to access " +
				    fent.chdir_prefix, err_code)
			cmd = TM_defs.CPIO + " -" + fent.cpio_args + "V " + \
			    self.dst_mntpt + " < " + fent.name
			self.dbg_msg("Executing: " + cmd + " CWD: " +
			    fent.chdir_prefix)
			err_file = os.tmpfile()
			if (self.log_handler != None): 
				rt = exec_cmd_outputs_to_log(cmd.split(),
				    self.log_handler)
				if (rt != 0):
					self.log_handler.error(cmd +
					    " had errors")
			else:
				pipe = Popen(cmd, shell=True, stdout=PIPE,
				    stderr=err_file, close_fds=True)
				while 1:
					ch = pipe.stdout.read(1)
					self.check_abort()
					if not ch:
						break;
				rt = pipe.wait()

				if rt != 0 and self.debugflag == 1:
					err_file.seek(0)
					self.info_msg("WARNING: " + cmd
					    + " had errors")
					self.info_msg("         "
					    + err_file.read())

				err_file.close()

		if self.distro_size:
			pmon.done = True
			pmon.wait()


	def perform_transfer(self, args):
		"""Main function for doing the copying of bits
                """
		for opt, val in args:
                        if opt == TM_ATTR_MECHANISM:
				continue
			elif opt == "dbgflag":
				if val == "true":
					self.debugflag = 1
				else:
					self.debugflag = 0

			elif opt == TM_CPIO_DST_MNTPT:
				self.dst_mntpt = val
			elif opt == TM_CPIO_SRC_MNTPT:
				self.src_mntpt = val
			elif opt == TM_CPIO_ACTION:
				self.cpio_action = val
			elif opt == TM_CPIO_LIST_FILE:
				self.list_file = val
			elif opt == TM_ATTR_IMAGE_INFO:
				self.image_info = val
			elif opt == TM_CPIO_ENTIRE_SKIP_FILE_LIST:
				self.skip_file_list = val
			elif opt == TM_CPIO_ARGS:
				self.cpio_args = val
			elif opt == TM_PYTHON_LOG_HANDLER:
				self.log_handler = val
			else:
				raise TValueError("Invalid attribute " +
				    str(opt), TM_E_INVALID_TRANSFER_TYPE_ATTR)

		if self.cpio_action == TM_CPIO_LIST and \
		    self.list_file == "":
			raise TValueError("No list file for List Cpio action",
			    TM_E_INVALID_CPIO_FILELIST_ATTR)

		if self.dst_mntpt == "":
			raise TValueError("Target mountpoint not set",
			    TM_E_INVALID_CPIO_ACT_ATTR)

		if self.cpio_action == TM_CPIO_ENTIRE and \
		    self.image_info == "":
			self.image_info = "/.cdrom/.image_info"

		# Check that the dst_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self.dst_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Destination mountpoint "
				    "doesn't exist", TM_E_INVALID_CPIO_ACT_ATTR)
		except OSError:
			raise TValueError("Destination mountpoint is "
			    "inaccessible", TM_E_INVALID_CPIO_ACT_ATTR)

		#
		# Read in approx size of the entire distribution from
		# .image_info file. This is used for disk space usage
		# monitoring.
		#
		if self.image_info:
			try:
				ih = open(self.image_info, 'r')
			except IOError:
				raise TAbort("Failed to access " +
				    self.image_info, TM_E_INVALID_CPIO_ACT_ATTR)

			for line in ih:
				(opt, val) = line.split("=")
				if opt == "IMAGE_SIZE":
					self.distro_size = int(val)
				else:
					raise TAbort("Unable to read " \
					    "IMAGE_SIZE in " + self.image_info,
					    TM_E_INVALID_CPIO_ACT_ATTR)
			ih.close()

		try:
			os.putenv('TMPDIR', '/tmp')
		except:
			pass

		if self.cpio_action == TM_CPIO_ENTIRE:
			self.cpio_transfer_entire_directory()
		elif self.cpio_action == TM_CPIO_LIST:
			try:
				open(self.list_file, 'r') 
			except:
				raise TAbort("Unable to open " + self.list_file,
				    TM_E_INVALID_CPIO_ACT_ATTR);
			fent_list = []
			fent = Flist()
			fent_list.append(fent)
			fent.name = self.list_file 
			fent.chdir_prefix = self.src_mntpt
			fent.cpio_args = self.cpio_args 
			self.cpio_transfer_filelist(fent_list,
			    TM_E_CPIO_LIST_FAILED)
		else:
			raise TAbort("Invalid CPIO action",
			    TM_E_INVALID_CPIO_ACT_ATTR)

		tmod.logprogress(100, "Complete transfer process")
		self.info_msg("-- Completed transfer process, " +
		    time.strftime(self.tformat) + " --")

class Transfer_ips(object):
	"""This class contains all the methods used to create an IPS
	image and populate it
        """

	def __init__(self):
		self._action = "" 
		self._pkg_url = ""
		self._pkg_auth = ""
		self._init_mntpt = ""
		self._pkgs_file = "" 
		self.debugflag = 0 
		self._image_type = "F"
		self._image_create_force_flag = ""
		self._alt_auth = ""
		self._alt_url = ""
		self._pref_flag = ""
		self._mirr_flag = ""
		self._no_index_flag = ""
		self._refresh_flag = "--no-refresh"
		self._prop_name = ""
		self._prop_value = ""
		self._log_handler = None
		self._verbose_mode = ""
		
	def prerror(self, msg):
		"""Log an error message to logging service and stderr
                """
		msg1 = msg + "\n"
		logsvc.write_dbg(TRANSFER_ID, logsvc.LS_DBGLVL_ERR, msg1)
		sys.stderr.write(msg1)
		sys.stderr.flush()

	def perform_ips_init(self):
		"""Perform an IPS image-create call. 
		Raises TAbort if unable to create the IPS image
		"""
		# Check that the required values have been set.
		if self._pkg_url == "":
			raise TValueError("IPS repository not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		if self._pkg_auth== "":
			raise TValueError("IPS publisher not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		# Generate the command to create the IPS image
		cmd = TM_defs.PKG + " image-create %s -%s -p %s=%s %s" % \
		    (self._image_create_force_flag, self._image_type,
		    self._pkg_auth, self._pkg_url, self._init_mntpt)

		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
	       			raise TAbort("Unable to initialize the "
				    "pkg image area at "
				    + self._init_mntpt, TM_E_IPS_INIT_FAILED)	
		except OSError:
			raise TAbort("Unable to initialize the pkg image area "
			    "at " + self._init_mntpt, TM_E_IPS_INIT_FAILED)	

	def perform_ips_repo_contents_verify(self):
		"""Verify the packages specified by the user are actually
		contained in the repository they specify.
		Raises TAbort if unable to verify the IPS repository
		"""
		# Verifying that needed packages are in the repository...
		# Fetching list of repository packages...

		# Check that the required parameters are set.
		if self._pkgs_file == "":
			raise TValueError("IPS pkg list not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)


		# Checking against list of requested packages..
		try:
			pkgfile = open(self._pkgs_file, 'r')
		except:
			raise TAbort("Unable to open the IPS packages file "
			    + self._pkgs_file,
			    TM_E_IPS_REPO_CONTENTS_VERIFY_FAILED)	

		# For each package in our pkgs file, see if it's in the
		# IPS repository.
		pkglist = ""
		for line in pkgfile:
			pkglist += " " + line.rstrip()
		pkgfile.close()
		cmd = TM_defs.PKG + " -R %s list %s -a %s" %  \
		    (self._init_mntpt, self._verbose_mode, pkglist)
		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TIPSPkgmissing(TM_E_IPS_PKG_MISSING)
		except OSError:
			raise TAbort("Unable to verify the contents of"
			    " the IPS repository",
			    TM_E_IPS_REPO_CONTENTS_VERIFY_FAILED)	


	def perform_ips_set_prop(self):
		"""Perform an IPS set-property of the property 
		specified.
		Raises: TAbort if unable to set property. 
		"""

		# Check that the required parameters are set.
		if self._prop_name == "":
			raise TValueError("IPS property name not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		if self._prop_value == "":
			raise TValueError("IPS property value not set",
			    TM_E_INVALID_IPS_ACT_ATTR)
	
		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)

		cmd = TM_defs.PKG + \
		    " -R %s set-property %s %s" % \
		    (self._init_mntpt, self._prop_name, self._prop_value)

		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TAbort("Unable to set property", \
				    TM_E_IPS_SET_PROP_FAILED)	
		except OSError:
			raise TAbort("Unable to set property",
			    TM_E_IPS_SET_PROP_FAILED)	
		
	def perform_ips_set_auth(self):
		"""Perform an IPS set-publisher of the additional publisher
		specified. By default, the --no-refresh flag is used
		so the catalog doesn't get refreshed when set-publisher
		is run.  If the caller wants the catalog to be refreshed,
		specify the TM_IPS_REFRESH_CATALOG=true option when calling
		this function.
		Raises: TAbort if unable to set the additional publisher. 
		"""

		# Check that the required parameters are set.
		if self._alt_auth == "":
			raise TValueError("IPS alternate publisher not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		if self._alt_url == "":
			raise TValueError("IPS alternate publisher url not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccesible", TM_E_INVALID_IPS_ACT_ATTR)

		if self._pref_flag and self._mirr_flag:
			raise TValueError("Unable to perform IPS set-publisher "
			    "with -p and -m flags in same transaction",
			    TM_E_INVALID_IPS_ACT_ATTR)

		if self._mirr_flag:
			cmd = TM_defs.PKG + \
			    " -R %s set-publisher %s %s %s %s" % \
			    (self._init_mntpt, self._mirr_flag, self._alt_url,
			    self._refresh_flag, self._alt_auth)
		else:
			cmd = TM_defs.PKG + \
			    " -R %s set-publisher %s -O %s %s %s" % \
			    (self._init_mntpt, self._pref_flag, self._alt_url,
			    self._refresh_flag, self._alt_auth)
		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TAbort("Unable to set an additional " \
				    "publisher", TM_E_IPS_SET_AUTH_FAILED)	
		except OSError:
			raise TAbort("Unable to set an additional publisher",
			    TM_E_IPS_SET_AUTH_FAILED)	
		

	def perform_ips_refresh(self):
		"""Perform an IPS refresh if the image area 
		Raises: TAbort if unable to refresh the IPS image 
		"""

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)


		cmd = TM_defs.PKG + " -R %s refresh" % self._init_mntpt
		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TAbort("Unable to refresh the IPS image",
				    TM_E_IPS_REFRESH_FAILED)	
		except OSError:
			raise TAbort("Unable to refresh the IPS image",
			    TM_E_IPS_REFRESH_FAILED)	
		

	def perform_ips_unset_auth(self):
		"""Perform an IPS unset-publisher of the specified publisher 
		Raises: TAbort if unable to unset the publisher 
		"""

		# Check that the required parameters are set.
		if self._alt_auth == "":
			raise TValueError("IPS alternate publisher not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)

		cmd = TM_defs.PKG +" -R %s unset-publisher %s" % \
		    (self._init_mntpt, self._alt_auth)
		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TAbort("Unable to unset-publisher",
				    TM_E_IPS_UNSET_AUTH_FAILED)	
		except OSError:
			raise TAbort("Unable to unset-publisher",
			    TM_E_IPS_UNSET_AUTH_FAILED)	
		

	def perform_ips_pkg_op(self, action_str):
		"""Perform an IPS pkg install/uninstall of the packages
		specified.
		argument:
			action_str: "install" indicates that this is for doing
				a "pkg install" of packages.  "uninstall"
				means this is for doing a "pkg uninstall"
				of packages.
		Raises: TAbort if unable to install/uninstall the packages.
		"""

		# make sure action_str is defined and it is a valid action
		if ((action_str != "install") and (action_str != "uninstall")):
			raise TValueError("Invalid action string: "
			    + action_str)

		# Check that the required parameters are set.
		if self._pkgs_file == "":
			raise TValueError("IPS package file not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)

		# Open the file that contains the packages to work on
		try:
			pkgfile = open(self._pkgs_file, 'r')
		except IOError:
			raise TAbort("Unable to read list of packages "
			    " to " + action_str, TM_E_IPS_RETRIEVE_FAILED)

		# install/uninstall each package, keeping track if
		# any are missing.
		missingpkg = 0
		for line in pkgfile:
			cmd = (TM_defs.PKG + " -R %s %s %s %s %s") % \
			    (self._init_mntpt, action_str, self._verbose_mode,
			    self._no_index_flag, line)
			try:
				if (self._log_handler != None):
					status = exec_cmd_outputs_to_log \
					    (cmd.split(), self._log_handler)
				else:
					status = call(cmd, shell=True)
				if status:
					missingpkg = 1
					err_str = ("Unable to " + action_str + \
					    " %s in %s") \
					    % (str.rstrip(line),
					    self._init_mntpt)
					if (self._log_handler != None):
						self._log_handler.error(err_str)
					else:
						print err_str
			except OSError:
				raise TAbort("Unable to "
				    + action_str + " %s in %s"
				    % (line, self._init_mntpt),
				    TM_E_IPS_RETRIEVE_FAILED)

		pkgfile.close()

		# If there was a missing package, raise an exception
		# so the caller can decide what to do.
		if missingpkg:
			raise TIPSPkgmissing(TM_E_IPS_PKG_MISSING)

	def perform_ips_purge_hist(self):
		"""Perform an IPS pkg purge-history.
		Raises: TAbort if unable to purge the history.
		"""

		# Check that the init_mntpt really exists. If not, error.
		try:
			mst = os.lstat(self._init_mntpt)
			if not S_ISDIR(mst.st_mode):
				raise TValueError("Specified IPS image area "
				    "doesn't exist", TM_E_INVALID_IPS_ACT_ATTR)
		except OSError:
			raise TValueError("Specified IPS image area is "
			    "inaccessible", TM_E_INVALID_IPS_ACT_ATTR)

		cmd = TM_defs.PKG + " -R %s purge-history" % \
		    (self._init_mntpt)
		try:
			if (self._log_handler != None):
				status = exec_cmd_outputs_to_log(cmd.split(),
				    self._log_handler)
			else:
				status = call(cmd, shell=True)
			if status:
				raise TAbort("Unable to pkg purge-history "
				    " the IPS image at " + self._init_mntpt)	
		except OSError:
			raise TAbort("Unable to pkg purge-history "
			    "the IPS image at " + self._init_mntpt,
			    TM_E_IPS_RETRIEVE_FAILED)

	def perform_transfer(self, args):
		"""Perform a transfer using IPS.
		Input: args - specifies what IPS action to
		    perform, init, contents verify, retrieve/install,
		    set-publisher, refresh, or unset-publisher.
		Raises: TAbort
		"""	

		for opt, val in args:
                        if opt == TM_ATTR_MECHANISM:
				continue
                        elif opt == TM_IPS_ACTION:
                                self._action = val
                        elif opt == TM_IPS_PKG_URL:
				self._pkg_url = val
			elif opt == TM_IPS_PKG_AUTH:
				self._pkg_auth = val
                        elif opt == TM_IPS_INIT_MNTPT:
				self._init_mntpt = val
                        elif opt == TM_IPS_PKGS:
				self._pkgs_file = val
			elif opt == TM_IPS_IMAGE_TYPE:
				self._image_type = val
			elif opt == TM_IPS_IMAGE_CREATE_FORCE:
				if val == "true":
					self._image_create_force_flag = "-f"
			elif opt == TM_IPS_VERBOSE_MODE:
				if val == "true":
					self._verbose_mode = "-v"
			elif opt == TM_IPS_ALT_AUTH:
				self._alt_auth = val
			elif opt == TM_IPS_ALT_URL:
				self._alt_url = val
			elif opt == TM_IPS_PREF_FLAG:
				self._pref_flag = val
			elif opt == TM_IPS_MIRROR_FLAG:
				self._mirr_flag = val
			elif opt == TM_IPS_GENERATE_SEARCH_INDEX:
				# This is only used for install/uninstall
				# operations
				if val.lower() != "true":
					self._no_index_flag = "--no-index"
			elif opt == TM_IPS_REFRESH_CATALOG:
				# This is only used for set-publisher
				if (self._action != TM_IPS_SET_AUTH):
					raise TValueError("Attribute "
					    + str(opt) + "is only used " \
					    "for set-publisher",
					    TM_E_INVALID_TRANSFER_TYPE_ATTR)
				if val.lower() == "true":
					self._refresh_flag = ""
			elif opt == TM_IPS_PROP_NAME:
				# The prop name has already been set. Only one
				# property name is allowed so error out.
				if self._prop_name != "":
					raise TValueError("Only one property "
					    "can be set per call.", TM_E_INVALID_IPS_ACT_ATTR)
				self._prop_name = val
			elif opt == TM_IPS_PROP_VALUE:
				# The prop value has already been set. Only one
				# property value is allowed so error out.
				if self._prop_value != "":
					raise TValueError("Only one property value"
					    " can be specified per call.",
					    TM_E_INVALID_IPS_ACT_ATTR)
				self._prop_value = val
			elif opt == TM_PYTHON_LOG_HANDLER:
				self._log_handler = val
			elif opt == "dbgflag":
				if val == "true":
					self.debugflag = 1
				else:
					self.debugflag = 0
			else:
				raise TValueError("Invalid attribute " +
				    str(opt), TM_E_INVALID_TRANSFER_TYPE_ATTR)
			
		if self._init_mntpt == "":
			raise TValueError("Image mountpoint not set",
			    TM_E_INVALID_IPS_ACT_ATTR)

		if self._action == "":
			raise TValueError("TM_IPS_ACTION not set",
			    TM_E_INVALID_IPS_ACT_ATTR)
		elif self._action == TM_IPS_INIT:
			self.perform_ips_init()
		elif self._action == TM_IPS_REPO_CONTENTS_VERIFY:
			self.perform_ips_repo_contents_verify()
		elif self._action == TM_IPS_RETRIEVE:
			self.perform_ips_pkg_op("install")
		elif self._action == TM_IPS_SET_AUTH:
			self.perform_ips_set_auth()
		elif self._action == TM_IPS_REFRESH:
			self.perform_ips_refresh()
		elif self._action == TM_IPS_UNSET_AUTH:
			self.perform_ips_unset_auth()
		elif self._action == TM_IPS_PURGE_HIST:
			self.perform_ips_purge_hist()
		elif self._action == TM_IPS_UNINSTALL:
			self.perform_ips_pkg_op("uninstall")
		elif self._action == TM_IPS_SET_PROP:
			self.perform_ips_set_prop()
		else:
			raise TValueError("Invalid TM_IPS_ACTION",
			    TM_E_INVALID_IPS_ACT_ATTR)

def tm_perform_transfer(args, callback=None):
	"""Transfer data via cpio or IPS from a specified source to 
	destination. The cpio transfer can be either an entire directory
	or a list of files. The IPS functionality that is supported is
	image-create, content verification, set-publisher, refresh,
	unset-publisher, and retrieval.
	Arguments: nvlist specifying the transfer characteristics
		callback function for logging.
	Returns: TM_E_SUCCESS
		 TM_E_IPS_PKG_MISSING
		 TM_E_IPS_RETRIEVE_FAILED
		 TM_E_IPS_SET_AUTH_FAILED
		 TM_E_IPS_UNSET_AUTH_FAILED
		 TM_E_IPS_REFRESH_FAILED
		 TM_E_IPS_REPO_CONTENTS_VERIFY_FAILED
		 TM_E_IPS_INIT_FAILED
		 TM_E_INVALID_CPIO_ACT_ATTR
		 TM_E_INVALID_CPIO_FILELIST_ATTR
	"""

	# lock, so there isn't more than 1 transfer running at a time 
	params.tm_lock = threading.Lock()

	try:
		params.tm_lock.acquire()

		rv = TM_E_SUCCESS

		# If the callback is specified, set the python
		# callback function in the associated transfer mod
		# C code.
		if callback != None:
			# Set the python callback function
			tmod.set_py_callback(callback);

		action = ""
		for opt, val in args:
			if opt == TM_ATTR_MECHANISM:
				action = val
				break

		if action == TM_PERFORM_IPS:
			tobj = Transfer_ips()
		elif action == TM_PERFORM_CPIO:
			tobj = Transfer_cpio()
		else:
			if params.tm_lock.locked():
				params.tm_lock.release()	
			rv = TM_E_INVALID_TRANSFER_TYPE_ATTR
			return rv

		try:
			tobj.perform_transfer(args)
		except IOError, (errno, strerror):
			tobj.prerror("File operation error: ")
			tobj.prerror(traceback.format_exc())
			logsvc.write_log(TRANSFER_ID, "IOERROR\n")
			rv = TM_E_PYTHON_ERROR

		except (TValueError, TAbort), v:
			tobj.prerror(v.message)
			logsvc.write_log(TRANSFER_ID, "TValueError or TABort\n")
			rv = v.retcode

		except TIPSPkgmissing, v:
			logsvc.write_log(TRANSFER_ID, "pkg missing\n")
			rv = v.retcode

		except:
			logsvc.write_log(TRANSFER_ID, "everything else\n")
			tobj.prerror(traceback.format_exc())
			rv = TM_E_PYTHON_ERROR

	finally:
		if params.tm_lock.locked():
			params.tm_lock.release()	

	return rv

# global parameters 
params = TM_defs()
# Grab defines from transfermod.h
execfile('/usr/lib/python2.4/vendor-packages/osol_install/transfer_defs.py')
