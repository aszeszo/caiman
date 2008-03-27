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
# Slim Install Transfer Module
#
import os
import re
import errno
import time
import sys
import shutil
import traceback
import fcntl
import array
import string
import threading
from stat import *
from subprocess import *

#
# Modules specific to Slim Install
#
import tmod
import logsvc

class Cl_defines(object):
	"""Class that holds some globally used values"""
	def __init__(self):
		self.max_numfiles = 200000.0
		self.find_percent = 4
		self.kbd_device = "/dev/kbd"
		self.cpio = "/usr/bin/cpio"
		self.bunzip2 = "/usr/bin/bunzip2"
		self.archive = "/.cdrom/archive.bz2"
		self.kbd_layout_file = "/usr/share/lib/keytables/type_6/kbd_layouts"
		self.kbd_defaults_file = "etc/default/kbd"
		self.default_image_info = "/.cdrom/.image_info"

class Cpio_spec(object):
	"""Class used to hold values specifying a mountpoint for cpio operation"""
	def __init__(self, chdir_prefix=None, cpio_dir=None,  \
	    match_pattern=None, clobber_files=0, cpio_args="pdum"):
		self.chdir_prefix = chdir_prefix
		self.cpio_dir = cpio_dir
		self.match_pattern = match_pattern
		self.clobber_files = clobber_files
		self.cpio_args = cpio_args

class Flist(object):
	"""Class used to hold file list entries for cpio operation"""
	def __init__(self, name=None, chdir_prefix=None, clobber_files=0, \
	    cpio_args=None):
		self.name = name
		self.chdir_prefix = chdir_prefix
		self.clobber_files = clobber_files
		self.cpio_args = cpio_args

	def open(self):
		self.handle = open(self.name, "w+")

class TError(Exception):
	"""Base class for Transfer Module Exceptions."""
	pass

class TValueError(TError):
	"""Exception raised for errors in the input key/value list.

	Attributes:
	   message -- explanation of the error
	"""

	def __init__(self, message, retcode):
		self.message = message
		self.retcode = retcode

class TAbort(TError):
	"""Exception raised when the caller requests to abort transfer
	operation midway or a failure is detected.
	
	Attributes:
	   message -- explanation of the abort operation
	"""
	
	def __init__(self, message, retcode = 0):
		self.message = message
		self.retcode = retcode

class ProgressMon(object):
	def startmonitor(self, fs, distrosize, message, initpct=0, endpct=100):
		"""Start thread to monitor progress in populating file system
			fs - file system to monitor
			distrosize = full distro size in kilobytes
			initpct = base percent value from which to start
			    calculating.
		"""
		self.message =	message
		self.distrosize = distrosize
		self.initpct = initpct
		self.endpct = endpct
		self.done = False
		self.thread1 = threading.Thread( target=self.__progressthread, \
		    args=( fs,))
		self.thread1.start()
		return 0

	def wait(self):
		self.thread1.join()

	def __progressthread(self, fs):
		"""Monitor progress in populating file system
			fs - file system to monitor
		"""
		dsize = self.distrosize
		initsize = self.__fssize(fs)
		totpct = self.endpct - self.initpct
		prevpct = -1
		maxpct = totpct - 2
		while 1:
			#compute increase in fs size
			fssz = self.__fssize(fs)
			if (fssz == -1): return -1
			fsgain = fssz - initsize

			#compute percentage transfer
			actualpct = fsgain * 100 / self.distrosize
			#compute percentage transfer in terms of stated range
			pct = fsgain * totpct / dsize + self.initpct
			#do not exceed limits
			if pct > maxpct or actualpct > 100: pct = maxpct
			if (pct != prevpct):
				tmod.logprogress(pct, self.message)
				prevpct = pct
			if pct >= maxpct: return 0
			time.sleep(2)
			if tmod.abort_signaled() or self.done:
				return 0

	def __fssize(self, fs):
		cmd = "/usr/bin/df -k "+fs
		bufsize = 512
		p  = os.popen(cmd)
		dfout = p.readline(bufsize)
		if not dfout:
			logsvc.write_log(TRANSFER_ID, "FS size computation " + \
			    "failed for " + fs + "\n")
			return -1
		dfout = p.readline(bufsize)
		if not dfout:
			logsvc.write_log(TRANSFER_ID, "FS size computation " + \
			    "failed for " + fs + "\n")
			return -1
		lin = dfout.split()
		return int(lin[2])


class Transfer_cpio(object):
	"""This class contains all the methods used to actually transfer
	LiveCD contents to harddisk."""

	def __init__(self):
		self.dst_mntpt = ""
		self.src_mntpt = ""
		self.cpio_action = TM_CPIO_ENTIRE
		self.list_file = ""
		self.tformat = "%a, %d %b %Y %H:%M:%S +0000"
		self.debugflag = 1
		self.cpio_prefixes = []
		self.image_info = ""
	
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
		self.cpio_prefixes.append(Cpio_spec(chdir_prefix="/.cdrom", \
		    cpio_dir=".", \
		    match_pattern="!.*zlib$|.*cpio$|.*bz2$|.*7zip"))

	def prerror(self, msg):
		"""Log an error message to logging service and stderr"""
		msg1 = msg + "\n"
		logsvc.write_dbg(TRANSFER_ID, logsvc.LS_DBGLVL_ERR, msg1)
		sys.stderr.write(msg1)
		sys.stderr.flush()

	def info_msg(self, msg):
		"""Log an informational message to logging service"""
		msg1 = msg + "\n"
		logsvc.write_log(TRANSFER_ID, msg1)

	def dbg_msg(self, msg):
		"""Log detailed debugging messages to logging service"""
		if (self.debugflag > 0):
			msg1 = msg + "\n"
			logsvc.write_dbg(TRANSFER_ID, logsvc.LS_DBGLVL_INFO, \
			    msg1)

	def do_clobber_files(self, flist_file):
		"""Given a file containing a list of pathnames this function
		will search for those entries in the alternate root and
		delete all matching pathnames from the alternate root that
		are symbolic links.
		This process is required because of the way the LiveCD env
		is constructed. Some of the entries in the microroot are
		symbolic links to files mounted off a compressed lofi file.
		This is done to drastically reduce space usage by the
		microroot."""
		self.dbg_msg("File list for clobber: " + flist_file)
		fh = open(flist_file, "r")
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

	def get_kbd_layout_name(self, lnum):
		"""Given a keyboard layout number return the layout string.
		We should not be doing this here, but unfortunately there
		is no interface in the OpenSolaris keyboard API to perform
		this mapping for us - RFE."""
		fh = open(defines.kbd_layout_file, "r")
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
		if tmod.abort_signaled() == 1:
			raise TAbort("User aborted transfer")

	def perform_transfer(self, args):
		"""Main function for doing the copying of bits"""
		distrosize = 1900
		for opt, val in args:
			print opt, val
			if opt == "mountpoint" or opt == TM_CPIO_DST_MNTPT or \
			    opt == TM_ATTR_TARGET_DIRECTORY:
				self.dst_mntpt = val
			
			if opt == "dbgflag":
				if val == "true":
					self.debugflag = 1
				else:
					self.debugflag = 0

			if opt == TM_CPIO_SRC_MNTPT:
				self.src_mntpt = val

			if opt == TM_CPIO_ACTION:
				self.cpio_action = val

			if opt == TM_CPIO_LIST_FILE:
				self.list_file = val

			if opt == TM_ATTR_IMAGE_INFO:
				self.image_info = val

		#
		# TODO: Handling file list needs to be implemented
		#
		if self.cpio_action == TM_CPIO_LIST and \
		    self.list_file == "":
			raise TValueError("No list file for List Cpio action", \
			    TM_E_INVALID_CPIO_FILELIST_ATTR)

		if self.cpio_action == TM_CPIO_LIST:
			raise TValueError("Not yet implemented", \
			    TM_E_CPIO_LIST_FAILED)

		if self.dst_mntpt == "":
			raise TValueError("Target mountpoint not set", \
			    TM_E_INVALID_CPIO_ACT_ATTR)

		#
		# Read in approx size of the entire distribution from
		# .image_info file. This is used for disk space usage
		# monitoring.
		#
		if self.cpio_action == TM_CPIO_ENTIRE:
			if self.image_info == "":
				self.image_info = defines.default_image_info
			ih = open(self.image_info, "r")
			for line in ih:
				(opt, val) = line.split("=")
				if opt == "IMAGE_SIZE":
					distrosize = int(val)
			ih.close()

		zerolist = os.path.join(self.dst_mntpt, "flist.0length")
		zh = open(zerolist, "w+")
		self.info_msg("-- Starting transfer process, " + \
		    time.strftime(self.tformat) + " --")
		self.check_abort()

		tmod.logprogress(0, "Building file lists for cpio")
		percent = 0.0
		opercent = 0.0
		fent_list = []

		if self.src_mntpt != "" and self.src_mntpt != "/":
			self.cpio_prefixes = []
			self.cpio_prefixes.append(Cpio_spec( \
			    chdir_prefix=self.src_mntpt, cpio_dir="."))

		total_find_percent = (len(self.cpio_prefixes) - 1) * \
		    defines.find_percent

		# Get the optimized libc overlay out of the way.
		# Errors from umount intentionally ignored
		os.system("umount /lib/libc.so.1")
		self.info_msg("Building cpio file lists")
		cprefix = ""
		patt = None
		i = 0
		nfiles = 0.0
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
			self.dbg_msg("Cpio dir: " + cp.cpio_dir + \
			    " Chdir to: " + cp.chdir_prefix)
			patt = cp.match_pattern
			self.check_abort()

			if patt != None and patt[0] == '!':
				negate = 1
				patt = patt[1:]
			else:
				negate = 0

			st = None
			try:
				os.chdir(cp.chdir_prefix)
				st = os.stat(cp.cpio_dir)
			except OSError:
				raise TAbort("Failed to access Cpio dir: " + \
				    traceback.format_exc(), \
				    TM_E_CPIO_ENTIRE_FAILED)

			if (cprefix != cp.chdir_prefix or patt != None or \
			    cp.clobber_files == 1 or cp.cpio_args != None):
				fent = Flist()
				fent_list.append(fent)

				cprefix = cp.chdir_prefix
				fent.name = self.dst_mntpt + "/flist" + str(i)
				fent.open()
				i = i + 1
				
				self.dbg_msg(" File list tempfile:" + \
				    fent.name)
				fent.handle = open(fent.name, "w+")
				fent.chdir_prefix = cp.chdir_prefix
				fent.clobber_files = cp.clobber_files
				if (cp.cpio_args):
					fent.cpio_args = cp.cpio_args
				if (patt != None):
					cpatt = re.compile(patt)

			self.info_msg("Scanning " + cp.chdir_prefix + "/" + \
			    cp.cpio_dir)
			lf = fent.handle

			#
			# os.walk does not recurse into directory symlinks
			# so nftw(..., FTW_PHYS) is satisfied. In addition we
			# want to restrict our search only to the current
			# filesystem which is handled below.
			#
			for root, dirs, files in os.walk(cp.cpio_dir):
				self.check_abort()
				for name in files:
					m = None
					fname = root + "/" + name
					if patt != None:
						m = cpatt.match(name)
						if (m != None and negate == 1) \
						    or (m == None and \
						    negate != 1):
							self.dbg_msg("Non match " + \
							    "Skipped: " + fname)
							continue

					try:
						st1 = os.lstat(fname)
					except:
						continue
					if st1.st_size > 0:
						lf.write(fname + "\n")
					elif S_ISREG(st1.st_mode):
						zh.write(str(S_IMODE(st1.st_mode))+\
						    "," + str(st1.st_uid) + "," + \
						    str(st1.st_gid) + "," + fname \
						    + "\n")

					nfiles = nfiles + 1
					percent = int(nfiles / \
					    defines.max_numfiles * \
					    total_find_percent)
					if percent - opercent > 1:
						tmod.logprogress(percent, \
						    "Building cpio file lists")
						opercent = percent

				#
				# Identify directories that we do not want to
				# traverse. These are those that can't be read
				# for some reason or those holding other
				# mounted filesystems.
				#
				rmlist = []
				for name in dirs:
					dname = root + "/" + name
					try:
						st1 = os.stat(dname);
					except:
						rmlist.append(name)
						continue
					lf.write(dname + "\n")

					# Emulate nftw(..., FTW_MOUNT) for
					# directories.
					if st1.st_dev != st.st_dev:
						rmlist.append(name)

				#
				# Remove directories so that they are not traversed.
				# os.walk allows dirs to be modified in place.
				#
				for dname in rmlist:
					dirs.remove(dname)
			# Flush the list file here for easier debugging
			lf.flush()

		# Flush the zero-length file list
		zh.flush()
		self.info_msg("Beginning cpio actions")

		#
		# Now process each entry in the list. cpio is executed with the
		# -V option where it prints a dot for each pathname processed.
		# This is needed to provide the ability to abort midway.
		#

		#
		# Start the disk space monitor thread
		#
		pmon = ProgressMon()
		pmon.startmonitor(self.dst_mntpt, distrosize, \
		    "Transferring LiveCD Contents", percent, 95)

		for fent in fent_list:
			fent.handle.close()
			fent.handle = None
			self.check_abort()

			if fent.clobber_files == 1:
				self.do_clobber_files(fent.name)
			os.chdir(fent.chdir_prefix)
			cmd = defines.cpio + " -" + fent.cpio_args + "V " + \
			    self.dst_mntpt + " < " + fent.name
			self.dbg_msg("Executing: " + cmd + " CWD: " + \
			    fent.chdir_prefix)
			err_file = os.tmpfile()
			pipe = Popen(cmd, shell=True, stdout=PIPE, \
				stderr=err_file, close_fds=True)
			while 1:
				ch = pipe.stdout.read(1)
				self.check_abort()
				if not ch:
					break
			rt = pipe.wait()

			# cpio copying errors are typically non-fatal
			if rt != 0 and self.debugflag == 1:
				err_file.seek(0)
				self.info_msg("WARNING: " + cmd + " had errors")
				self.info_msg("         " + err_file.read())
			err_file.close()
			os.unlink(fent.name)
			fent.name = ""

		pmon.done = True
		pmon.wait()
		tmod.logprogress(96, "Fixing zero-length files")

		# Process zero-length files if any.
		self.info_msg("Creating zero-length files")
		zh.seek(0)
		for line in zh:
			# Get the newline out of the way
			line = line[:-1]
			(mod, st_uid, st_gid, fname) = line.split(',')
			mod = int(mod)
			st_uid = int(st_uid)
			st_gid = int(st_gid)
			fl = self.dst_mntpt + "/" + fname

			# "touch" the file.
			open(fl, "w").close()
			os.chown(fl, st_uid, st_gid)
			os.chmod(fl, mod)
			self.dbg_msg("Created file " + fl)
			self.check_abort()

		zh.close()
		os.unlink(zerolist)
		tmod.logprogress(97, "Extracting archive")
		self.info_msg("Extracting archive")
		os.chdir(self.dst_mntpt)
		cmd = defines.bunzip2 + " -c " + defines.archive + " | " + \
			defines.cpio + " -idum"
		self.dbg_msg("Executing: " + cmd + ", CWD: " + self.dst_mntpt)

		self.check_abort()
		err_file = os.tmpfile()
		p1 = Popen(cmd, stderr=err_file, shell=True)
		rt = p1.wait()

		# cpio copying errors are typically non-fatal
		if rt != 0 and self.debugflag == 1:
			err_file.seek(0)
			self.info_msg("WARNING: " + cmd + " had errors")
			self.info_msg("         " + err_file.read())
		err_file.close()
		tmod.logprogress(98, "Performing file operations")
		self.check_abort()

		self.info_msg("Performing file operations")
		mp = self.dst_mntpt
		shutil.copyfile(mp + "/lib/svc/seed/global.db", \
		    mp + "/etc/svc/repository.db")
		os.chmod(mp + "/etc/svc/repository.db", S_IRUSR | S_IWUSR)
		tmod.logprogress(99, "Cleaning up")
		open(mp + "/etc/mnttab", "w").close()
		os.chmod(mp + "/etc/mnttab", S_IREAD)
		self.check_abort()

		unlnk_list = []
		unlnk_list.append("/boot/x86.microroot")
		unlnk_list.append("/.livecd")
		unlnk_list.append("/.volumeid")
		unlnk_list.append("/boot/grub/menu.lst")

		for fname in unlnk_list:
			self.check_abort()
			try:
				os.unlink(mp + "/" + fname)
			except:
				pass

		self.info_msg("Fetching and updating keyboard layout")
		os.chdir(self.dst_mntpt)
		self.dbg_msg("Opening keyboard device: " + defines.kbd_device)
		kbd = open(defines.kbd_device, "r+")

		# KIOCLAYOUT is set in our module's dictionary by the C
		# wrapper that calls us.
		k = array.array('h', [0])
		fcntl.ioctl(kbd, KIOCLAYOUT, k, 1)
		kbd_layout = k.tolist()[0]
		kbd.close()
		self.check_abort()

		layout = self.get_kbd_layout_name(kbd_layout)
		kbd_file = open(defines.kbd_defaults_file, "a+")
		kbd_file.write("LAYOUT=" + layout + "\n")
		kbd_file.close()
		self.dbg_msg("Updated keyboard defaults file: " + self.dst_mntpt +
			"/" + defines.kbd_defaults_file)
		self.info_msg("Detected " + layout + " keyboard layout")
		
		os.system("rm -rf " + mp + "/var/tmp/*")
		os.system("rm -rf " + mp + "/mnt/*")

		tmod.logprogress(100, "Complete transfer process")
		self.info_msg("-- Completed transfer process, " + \
		    time.strftime(self.tformat) + " --")

#
# TODO: Not yet implemented
#
class Transfer_ips(object):
	"""This class contains all the methods used to create an IPS
	image and populate it"""

	def __init__(self):
		pass

	def perform_transfer(self, args):
		pass

def perform_transfer(args):
	action = -1
	for opt, val in args:
		if opt == TM_ATTR_MECHANISM:
			action = val
			break

	if action == -1:
		logsvc.write_dbg(TRANSFER_ID, logsvc.LS_DBGLVL_ERR, \
		    "Invalid or no Transfer type specified\n")
		return (TM_E_INVALID_TRANSFER_TYPE_ATTR)

	if action == TM_PERFORM_IPS:
		tobj = Transfer_ips()
	elif action == TM_PERFORM_CPIO:
		tobj = Transfer_cpio()
	else:
		return (TM_E_INVALID_TRANSFER_TYPE_ATTR)
	rv = TM_E_SUCCESS

	try:
		tobj.perform_transfer(args)
	except IOError, (errno, strerror):
		tobj.prerror("File operation error: ")
		tobj.prerror(traceback.format_exc())
		rv = TM_E_CPIO_ENTIRE_FAILED

	except (TValueError, TAbort), v:
		tobj.prerror(v.message)
		rv = v.retcode

	except:
		tobj.prerror(traceback.format_exc())
		rv = TM_E_CPIO_ENTIRE_FAILED

	return rv

defines = Cl_defines()
