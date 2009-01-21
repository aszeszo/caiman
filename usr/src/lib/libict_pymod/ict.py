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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
#
'''Install Completion Tasks (ICT)

Each ICT is implemented as a method of class ict.

Guide to calling ICTs

The most efficient way to invoke ICTs is to create an ict class instance,
	then to invoke the ICT methods of the ict class:
- create an ict class instance, providing at least root target directory
- call ICT as a method of the class instance just created
- returned status is a tuple of exit status code and any other return information
- logging is done by ICT, but you can return exit status to caller
- logging service options are inherited from the environment
- logging level can be set (second parameter) and overridden in environment
	LS_DBG_LVL=(1-4)
- do not abort if an ICT fails (unless it is an untenable situation)

ICTs can also be invoked singly through a command line using function exec_ict():
	# python ict.py <ICT method> <target root directory> [<ICT-specific parameter>]
	Example command line:  # python ict.py ict_test /a  #runs test ICT

Guide to writing ICTs

- Locate ict class (line starts with "def ict")
- Within the ict class, find "end Install Completion Tasks"
- Add new ICT as method just before that
- ICTs are methods of the ict class
- ICTs have 'self' as 1st parameter - add other parameters as desired
- Create error return code(s)
- ICTs should return either status code, or a tuple with status code first
- See __init__ method for initialization of class members
- self.BASEDIR is the root directory of the target
- for first line of ICT, use _register_task(inspect.currentframe()) as a trace aid
- do not allow unhandled exceptions
- if a critical condition is encountered, log error and sys.exit() with error status
- as a last exception handler, instead of raising the exception, log the traceback,
    e.g.:
	except:
		prerror('Unexpected error doing something.')
		prerror(traceback.format_exc())
- use the module utility routines:
	prerror(string) - log error message
	_dbg_msg(string) - log output debugging message
	info_msg(string) - log informational message
	_cmd_out(cmd) - execute shell command, returning only exit status
	_cmd_status(cmd) - execute shell command, returning exit status and stdout
- place ICT comments just before or after def statement for module pydoc to generate
	documentation

Skeleton ICT:

from osol_install.ict import * #OpenSolaris standard location
icto = ict('/a')
status = icto.<some ICT (class method)>(<parameters depend on ICT>)

ICT initial project tasks from Transfer Module (TM):
	[1G] Setting default keyboard layout TM
	[3B] Creating initial SMF repository TM
	[3C] Creating /etc/mnttab TM
	[3G] Cleanup unnecessary symbolic links and files from the alternate root.
	(clobber files) TM
'''
import os
import os.path
import sys
from stat import *
import fcntl
import array
import shutil
import tempfile
import fnmatch
from osol_install.liblogsvc import *
import inspect
import filecmp
import traceback
import re
import platform
from pkg.cfgfiles import PasswordFile
import signal

ICTID = 'ICT'
(
ICT_INVALID_PARAMETER,
ICT_INVALID_PLATFORM,
ICT_NOT_MULTIBOOT,
ICT_ADD_FAILSAFE_MENU_FAILED,
ICT_KIOCLAYOUT_FAILED,
ICT_OPEN_KEYBOARD_DEVICE_FAILED,
ICT_KBD_LAYOUT_NAME_NOT_FOUND,
ICT_KBD_DEFAULTS_FILE_ACCESS_FAILURE,
ICT_EEPROM_GET_FAILED,
ICT_UPDATE_BOOTPROP_FAILED,
ICT_MKMENU_FAILED,
ICT_SPLASH_IMAGE_FAILURE,
ICT_REMOVE_LIVECD_COREADM_CONF_FAILURE,
ICT_SET_BOOT_ACTIVE_TEMP_FILE_FAILURE,
ICT_FDISK_FAILED,
ICT_UPDATE_DUMPADM_NODENAME_FAILED,
ICT_ENABLE_NWAM_AI_FAILED,
ICT_ENABLE_NWAM_FAILED,
ICT_FIX_FAILSAFE_MENU_FAILED,
ICT_CREATE_SMF_REPO_FAILED,
ICT_CREATE_MNTTAB_FAILED,
ICT_PACKAGE_REMOVAL_FAILED,
ICT_DELETE_BOOT_PROPERTY_FAILURE,
ICT_GET_ROOTDEV_LIST_FAILED,
ICT_SETUP_DEV_NAMESPACE_FAILED,
ICT_UPDATE_ARCHIVE_FAILED,
ICT_REMOVE_FILESTAT_RAMDISK_FAILED,
ICT_COPY_SPLASH_XPM_FAILED,
ICT_SMF_CORRECT_SYS_PROFILE_FAILED,
ICT_REMOVE_BOOTPATH_FAILED,
ICT_ADD_SPLASH_IMAGE_FAILED,
ICT_SYSIDTOOL_ENTRIES_FAILED,
ICT_SYSIDTOOL_CP_STATE_FAILED,
ICT_SET_FLUSH_CONTENT_CACHE_ON_SUCCESS_FAILED,
ICT_FIX_BROWSER_HOME_PAGE_FAILED,
ICT_FIX_GRUB_ENTRY_FAILED,
ICT_CLOBBER_FILE_FAILED,
ICT_CLEANUP_FAILED,
ICT_REBUILD_PKG_INDEX_FAILED,
ICT_PKG_RESET_UUID_FAILED,
ICT_PKG_SEND_UUID_FAILED,
ICT_SET_SWAP_AS_DUMP_FAILED,
ICT_EXPLICIT_BOOTFS_FAILED,
ICT_ENABLE_HAPPY_FACE_BOOT_FAILED,
ICT_POPEN_FAILED,
ICT_REMOVE_LIVECD_ENVIRONMENT_FAILED,
ICT_SET_ROOT_PW_FAILED,
ICT_CREATE_NU_FAILED
) = range(200,248)

#Global variables
debuglvl = LS_DBGLVL_ERR
curICTframe = None #frame info for debugging and tracing

#Module functions - intended for local use, but usable by importers

def _register_task(fm):
	'''register current ICT for logging, debugging and tracing
	By convention, use as 1st executable line in ICT
	'''
	global curICTframe
	curICTframe = fm
	if curICTframe != None:
		cf = inspect.getframeinfo(curICTframe)
		write_log(ICTID, 'current task:' + cf[2] + '\n')

def prerror(msg):
	'''Log an error message to logging service and stderr
	'''
	msg1 = msg + "\n"
	write_dbg(ICTID, LS_DBGLVL_ERR, msg1)

def _move_in_updated_config_file(new, orig):
	'''move in new version of file to original file location, overwriting original
	side effect: deletes temporary file upon failure
	'''
	if os.path.exists(new) and os.path.exists(orig) and filecmp.cmp(new, orig): #if files are identical
		_delete_temporary_file(new) #cleanup temporary file
		return True #success
	try:
		shutil.move(new, orig)
	except IOError:
		prerror('IO error - cannot move file ' + new + ' to ' + orig)
		prerror(traceback.format_exc())
		_delete_temporary_file(new) #cleanup temporary file
		return False #failure
	except:
		prerror('Unrecognized error - failure to move file ' + new + ' to ' + orig)
		prerror(traceback.format_exc())
		_delete_temporary_file(new) #cleanup temporary file
		return False #failure
	return True #success
			
def _cmd_out(cmd):
	'''execute a shell command and return output
	cmd - command to execute
	returns tuple:
		status = command exit status
		dfout = array of lines output to stdout, stderr by command
	'''
	_dbg_msg('_cmd_out: executing cmd=' + cmd)
	status = 0
	dfout = []
	'''Since Python ignores SIGPIPE, according to Python issue 1652,
	UNIX scripts in subprocesses will also ignore SIGPIPE.
	Workaround is to save original signal handler, restore default handler,
	launch script, restore original signal handler
	'''
	orig_sigpipe = signal.getsignal(signal.SIGPIPE) #save SIGPIPE signal handler
	signal.signal(signal.SIGPIPE, signal.SIG_DFL) #restore default signal handler for SIGPIPE
	try:
		fp = os.popen(cmd)
		if fp == None or fp == -1: return ICT_POPEN_FAILED, []
		for rline in fp:
			if len(rline) > 0 and rline[-1] == '\n':
				rline = rline[:-1]
			dfout.append(rline)
			_dbg_msg('_cmd_out: stdout/stderr line=' + rline)
		status = fp.close()
	except:
		prerror('system error in launching shell cmd (' + cmd + ')')
		status = 1
	signal.signal(signal.SIGPIPE, orig_sigpipe) #restore original signal handler for SIGPIPE
	if status == None: status = 0	
	if status != 0:
		write_log(ICTID, 'shell cmd (' + cmd +
		    ') returned status ' + str(status) + "\n")
	if debuglvl >= LS_DBGLVL_INFO:
		print ICTID + ': _cmd_out status =', status, 'stdout/stderr=',dfout
	return status, dfout

def _cmd_status(cmd):
	'''execute a shell command using popen and return its exit status
	'''
	_dbg_msg('_cmd_status: executing cmd=' + cmd)
	exitstatus = None

	'''Since Python ignores SIGPIPE, according to Python issue 1652,
	UNIX scripts in subprocesses will also ignore SIGPIPE.
	Workaround is to save original signal handler, restore default handler,
	launch script, restore original signal handler
	'''
	orig_sigpipe = signal.getsignal(signal.SIGPIPE) #save SIGPIPE signal handler
	signal.signal(signal.SIGPIPE, signal.SIG_DFL) #restore default signal handler for SIGPIPE
	try:
		fp = os.popen(cmd)
		if fp == None or fp == -1: return ICT_POPEN_FAILED
		exitstatus = fp.close()
	except:
		prerror('unknown error in launching shell cmd (' + cmd + ')')
		prerror('Traceback:')
		prerror(traceback.format_exc())
		exitstatus = 1
	if exitstatus == None: exitstatus = 0
	signal.signal(signal.SIGPIPE, orig_sigpipe) #restore original signal handler for SIGPIPE
	_dbg_msg('_cmd_status: return exitstatus=' + str(exitstatus))
	return exitstatus

#send an informational message to logging service
def info_msg(msg):
	write_log(ICTID, msg + '\n')

#send informational debugging message to logging service, according to level
def _dbg_msg(msg):
	global debuglvl
	if (debuglvl >= LS_DBGLVL_INFO):
		write_dbg(ICTID, LS_DBGLVL_INFO, msg + '\n')

#delete temporary file - suppress traceback on error
def _delete_temporary_file(filename):
	try:
		os.unlink(filename)
	except:
		pass # ignore failure to delete temp file

class ict(object):
	def __init__(self, BASEDIR, 
	    debuglvlparm = -1,
	    BOOTENVRC = '/boot/solaris/bootenv.rc',
	    LOCGRUBMENU = '/boot/grub/menu.lst'):
		'''main class to support ICT
			ICT object must first be created and initialized
				BASEDIR - root directory (only required parameter)
				debuglvlparm - debugging message level for liblogsvc
				BOOTENVRC - normal location of bootenv.rc
				LOCGRUBMEN - normal location of GRUB menu

		class initializer will exit with error status if:
			- BASEDIR is missing or empty
			- BASEDIR is '/', in order to protect against accidental usage
		'''
		if BASEDIR == '':
			prerror('Base directory must be passed')
			sys.exit(1)
		if BASEDIR == '/':
			prerror('Base directory cannot be root ("/")')
			sys.exit(1)
		self.BASEDIR = BASEDIR
		self.BOOTENVRC = BASEDIR + BOOTENVRC #/boot/solaris/bootenv.rc

		#Is the current platform a SPARC system?
		self.IS_SPARC = (platform.platform().find('sparc') >= 0)

		#take debugging level first from environment, then from parameter
		global debuglvl
		try:
			debuglvl = int(os.getenv('LS_DBG_LVL', -1))
		except:
			prerror('Could not parse enviroment variable LS_DBG_LVL to integer')
		if debuglvl == -1: debuglvl = debuglvlparm
		if debuglvl == -1:
			debuglvl = LS_DBGLVL_ERR #default logging
		else:
			if debuglvl != LS_DBGLVL_ERR and \
			    init_log(debuglvl) != 1: #set in logging service
				prerror('Setting logging service debug level to ' +
				    str(debuglvl) + ' failed.')

		self.KBD_DEVICE = '/dev/kbd'
		self.KBD_DEFAULTS_FILE = '/etc/default/kbd'
		self.KBD_LAYOUT_FILE = '/usr/share/lib/keytables/type_6/kbd_layouts'

		#take root poolname from mnttab
		cmd = 'grep "^[^	]*	' + BASEDIR + '	" /etc/mnttab | '+\
		    ' nawk \'{print $1}\' | sed \'s,/.*,,\''
		sts, rpa = _cmd_out(cmd)
		if len(rpa) == 0:
			prerror('Cannot determine root pool name. exit status=' + str(sts) +
			    ' command=' + cmd)
			sys.exit(ICT_GET_ROOTDEV_LIST_FAILED)
		self.rootpool = rpa[0]
		_dbg_msg('Root pool name discovered: ' + self.rootpool)
		self.GRUBMENU = '/' + self.rootpool + LOCGRUBMENU #/boot/grub/menu.lst

	#support methods
	def _get_bootprop(self, property):
		'''support method - get property from bootenv.rc
		Parameter: property - bootenv.rc property ID
		returns property value or '' if not found
		'''
		fp = open(self.BOOTENVRC)
		for rline in fp:
			if rline[0] == '#': continue
			try:
				(setprop, field, value) = rline.split()
			except:
				continue
			if field == property:
				fp.close()
				return value
		fp.close()
		return ''

	def _delete_bootprop(self, property):
		'''support method  - from bootenv.rc, delete property
		Parameter: property - bootenv.rc property ID
		return 0 for success, otherwise ICT failure status code
		'''
		newRC = self.BOOTENVRC + '.new'
		try:
			fp = open(self.BOOTENVRC)
			op = open(newRC, 'w')
			for rline in op:
				if rline[0] == '#':
					op.write(rline)
					continue
				try:
					(setprop, field, value) = rline.split()
				except ValueError:
					op.write(rline)
					continue
				if field == property: continue
				op.write(rline)
			fp.close()
			op.close()
			os.rename(newRC, self.BOOTENVRC)
		except OSError, (errno, strerror):
			prerror('Error in deleting property in ' + self.BOOTENVRC + ': ' + strerror)
			prerror('Failure. Returning: ICT_DELETE_BOOT_PROPERTY_FAILURE')
			return ICT_DELETE_BOOT_PROPERTY_FAILURE
		except:
			prerror('Unexpected error when deleting property in ' + self.BOOTENVRC)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_DELETE_BOOT_PROPERTY_FAILURE')
			return ICT_DELETE_BOOT_PROPERTY_FAILURE
		return 0

	def _update_bootprop(self, property, newvalue):
		'''support method - set bootenv.rc property to value
		Parameters:
			property - bootenv.rc property ID
			newvalue - value to assign to property
		return 0 for success or ICT status code
		'''
		newRC = self.BOOTENVRC + '.new'
		return_status = 0
		fp = op = None
		try:
			fp = open(self.BOOTENVRC)
			op = open(newRC, 'w')
			#copy all lines that do not contain the property
			for rline in fp:
				if rline[0] == '#':
					op.write(rline)
					continue
				try:
					(setprop, field, value) = rline.split()
				except ValueError:
					op.write(rline) #just copy
					continue
				if field != property: op.write(rline)
			#add the line with the updated property
			op.write('setprop ' + property + ' ' + newvalue + '\n')
			os.rename(newRC, self.BOOTENVRC)
		except OSError, (errno, strerror):
			prerror('Update boot property failed. ' + strerror + ' file=' +
			    self.BOOTENVRC + ' property=' + property + ' value=' + newvalue)
			prerror('Failure. Returning: ICT_UPDATE_BOOTPROP_FAILED')
			return_status = ICT_UPDATE_BOOTPROP_FAILED
		except:
			prerror('Unexpected error during updating boot property. file=' + self.BOOTENVRC +
			    ' property=' + property + ' value=' + newvalue)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_UPDATE_BOOTPROP_FAILED')
			return_status = ICT_UPDATE_BOOTPROP_FAILED
		if fp != None: fp.close()
		if op != None: op.close()
		return return_status

	def set_boot_active(self, RAW_SLICE):
		'''support method - set boot device as active in fdisk disk formatter
		Parameter: RAW_SLICE is a /dev path
		launches fdisk -F <format file> /dev/rdsk/cXtXdXpX on partitions if changes required
		return 0 upon success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		mtch = re.findall('p(\d+):boot$', RAW_SLICE)
		if mtch and mtch[0]:
			P0 = RAW_SLICE.replace('p'+mtch[0]+':boot', 'p0')
		else:
			mtch = re.findall('s(\d+)$', RAW_SLICE)
			if mtch and mtch[0]:
				P0 = RAW_SLICE.replace('s'+mtch[0], 'p0')
			else:
				P0 = RAW_SLICE
		cmd = 'fdisk -W - %s | grep -v \* | grep -v \'^[	 ]*$\'' % (P0)
		status, fdisk = _cmd_out(cmd)
		if status != 0:
			prerror('fdisk command fails to set ' + RAW_SLICE + ' active. exit status=' + str(status))
			prerror('command was ' + cmd)
			prerror('Failure. Returning: ICT_FDISK_FAILED')
			return ICT_FDISK_FAILED
		# make sure there is a Solaris partition before doing anything
		hasSolarisSystid = hasSolaris2Systid = False
		for ln in fdisk:
			if ln[0] == '*': continue
			cols = ln.split()
			if len(cols) < 2: continue
			if not hasSolarisSystid:
				hasSolarisSystid = (cols[0] == '130')
			if not hasSolaris2Systid:
				hasSolaris2Systid = (cols[0] == '191')
		if not hasSolarisSystid and not hasSolaris2Systid:
			return 0 # no changes
		fdiskout = []
		madeFdiskChanges = False
		for ln in fdisk:
			if ln[0] == '*': continue
			cols = ln.split()
			if len(cols) < 2: continue
			if hasSolaris2Systid:
				if cols[0] == '191':
					if cols[1] != '128':
						cols[1] = '128' #active partition
						madeFdiskChanges = True
				else:
					if cols[1] != 0:
						cols[1] = '0'
						madeFdiskChanges = True
			else: #systid Linux swap
				if cols[0] == '130':
					if cols[1] != '128':
						cols[1] = '128' #active partition
						madeFdiskChanges = True
				else:
					if cols[1] != '0':
						cols[1] = '0'
						madeFdiskChanges = True
			lnout = '  '
			for lno in cols:
				lnout += lno.ljust(6) + ' '
			lnout += '\n'
			fdiskout.append(lnout)
		if not madeFdiskChanges:
			_dbg_msg('No disk format changes - fdisk not run')
			return 0
		_dbg_msg('Disk format changes needed - fdisk will be run.')
		#write fdisk format to temporary file
		try:
			(fop,fdisk_tempfile) = tempfile.mkstemp('.txt', 'fdisk', '/tmp')
			for ln in fdiskout:
				os.write(fop,ln)
			os.close(fop)
		except OSError, (errno, strerror):
			prerror('Error in writing to temporary file. ' + strerror)
			prerror('Failure. Returning: ICT_SET_BOOT_ACTIVE_TEMP_FILE_FAILURE')
			return ICT_SET_BOOT_ACTIVE_TEMP_FILE_FAILURE
		except:
			prerror('Unexpected error in writing to temporary file. ' + strerror)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_SET_BOOT_ACTIVE_TEMP_FILE_FAILURE')
			return ICT_SET_BOOT_ACTIVE_TEMP_FILE_FAILURE
		cmd = 'fdisk -F %s %s 2>&1' % (fdisk_tempfile , P0)
		status = _cmd_status(cmd)
		#delete temporary file
		try:
			os.unlink(fdisk_tempfile)
		except OSError:
			pass # ignore failure to delete temporary file
		if status != 0:
			prerror('Error executing ' + cmd + '. exit status=' + str(status))
			prerror('Failure. Returning: ICT_FDISK_FAILED')
			return ICT_FDISK_FAILED
		return 0

	def _get_osconsole(self):
		'''support method - determine console device
		returns console device found in bootenv.rc, from prtconf command, or default 'text'

		If osconsole is not set (initial/flash install), we set it here based on
		what the current console device is.
		'''
		osconsole = self._get_bootprop('output-device')
		if osconsole != '':
			return osconsole

		# get console setting from prtconf command - console
		cmd = 'prtconf -v /devices | sed -n \'/console/{n;p;}\' | cut -f 2 -d \\\''
		sts, co = _cmd_out(cmd)
		if sts != 0:
			prerror('Error from command to get console. exit status=' + str(sts))
			prerror('Command in error=' + cmd)
		if len(co) > 0: osconsole = co[0]
		if osconsole == '':
			# get console setting from prtconf command - output-device
			cmd = 'prtconf -v /devices | sed -n \'/output-device/{n;p;}\' | cut -f 2 -d \\\''
			sts, co = _cmd_out(cmd)
			if sts != 0:
				prerror('Error from command to get console. exit status=' + str(sts))
				prerror('Command in error=' + cmd)
			if len(co) > 0:
				osconsole = co[0]
			if osconsole == 'screen':
				osconsole = 'text'
		# default console to text
		if osconsole == '':
			osconsole = 'text'
		return osconsole

	def get_rootdev_list(self):
		'''ICT and support method - get list of disks with zpools associated with root pool
		launch zpool iostat -v + rootpool
		return tuple:
			status - 0 for success, error code otherwise
			device list - list of raw device names: /dev/rdsk/cXtXdXsX, empty list if failure
		'''
		_register_task(inspect.currentframe())
		cmd = 'zpool iostat -v ' + self.rootpool
		sts, zpool_iostat = _cmd_out(cmd)
		if sts != 0:
			prerror('Error from command to get rootdev list. exit status=' + str(sts))
			prerror('Command in error=' + cmd)
			prerror('Failure. Returning: ICT_GET_ROOTDEV_LIST_FAILED')
			return ICT_GET_ROOTDEV_LIST_FAILED, []
		i = 0
		rootdevlist = []
		while i < len(zpool_iostat):
			p1 = zpool_iostat[i].split()
			if len(p1) > 1 and p1[0] == self.rootpool:
				i += 1
				while i < len(zpool_iostat):
					if len(zpool_iostat[i]) > 1 and zpool_iostat[i][0] == ' ':
						la = zpool_iostat[i].split()
						if len(la) > 1 and la[0] != 'mirror' and la[0][0] != '-':
							rootdevlist.append('/dev/rdsk/' + la[0])
					i += 1
			i += 1
		return 0, rootdevlist

	def _get_kbd_layout_name(self, layout_number):
		'''support method - given a keyboard layout number return the layout string.
		parameter layout_number - keyboard layout number from:
			/usr/share/lib/keytables/type_6/kbd_layouts
		We should not be doing this here, but unfortunately there
		is no interface in the OpenSolaris keyboard API to perform
		this mapping for us - RFE.'''
		try:
			fh = open(self.KBD_LAYOUT_FILE, "r")
		except:
			prerror('keyboard layout file open failure: filename=' +
			    self.KBD_LAYOUT_FILE)
			return ''
		kbd_layout_name = ''
		for line in fh: #read file until number matches
			if line[0] == '#': continue
			if line.find('=') == -1: continue
			(kbd_layout_name, num) = line.split('=')
			if int(num) == layout_number:
				fh.close()
				return kbd_layout_name
		fh.close()
		return ''

	def bootadm_update_menu(self, RDSK):
		'''ICT and support method - add failsafe menu entry for disk
		parameter RDSK - raw disk device name in ctds format: /dev/rdsk/cXtXdXsX
		Does bootadm update-menu -R BASEDIR -Z -o <raw disk>
		returns 0 if command succeeded, error code otherwise
		'''
		_register_task(inspect.currentframe())
		cmd = 'bootadm update-menu -R %s -Z -o %s 2>&1' % (self.BASEDIR, RDSK)
		info_msg('update GRUB boot menu on device ' + RDSK)
		_dbg_msg('editing GRUB menu: ' + cmd)
		status, cmdout = _cmd_out(cmd)
		if status != 0:
			prerror('Adding failsafe menu with command: %s failed.  exit status=%d'
			    % (cmd, status))
			for ln in cmdout:
				prerror('bootadm_update_menu output: ' + ln)
			prerror('Failure. Returning: ICT_ADD_FAILSAFE_MENU_FAILED')
			return ICT_ADD_FAILSAFE_MENU_FAILED
		for ln in cmdout:
			info_msg('bootadm_update_menu output: ' + ln)
		return 0

	def _get_root_dataset(self):
		'''support routine - using beadm list, get the root dataset of the root pool
		return root dataset active on reboot or '' if not found
		log error if not found
		'''
		_register_task(inspect.currentframe())
		cmd = 'beadm list -aH 2>&1'
		status,  belist = _cmd_out(cmd)
		if status != 0:
			prerror('BE list command %s failed. Exit status=%d' % (cmd,status))
			for msg in belist:
				prerror(msg)
			return ''
		for ln in belist:
			arg = ln.split(';') #parse datasets
			if not arg[2]: continue
			if arg[2].find('R') != -1: #check if active on reboot
				_dbg_msg('found root dataset %s ' % arg[1])
				return arg[1]
		return ''

	#end support routines

	#Install Completion Tasks start here

	def remove_bootpath(self):
		'''ICT - no bootpath needed for zfs boot - remove property from bootenv.rc
		blatant hack:  _setup_bootblock should be fixed
		in the spmisvc library to not put bootpath in bootenv.rc
		in the first place for zfs boot
		returns 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		newbootenvrc =  self.BOOTENVRC + '.tmp'
		bootpath = self._get_bootprop('bootpath')
		if bootpath != '':
			status = _cmd_status('sed \'/^setprop[ 	][ 	]*bootpath[ 	]/d\' ' +
			    self.BOOTENVRC + ' > ' + self.BOOTENVRC + '.tmp')
			if status != 0:
				prerror('bootpath not removed from bootenv.rc - exit status=' + str(status))
				prerror('Failure. Returning: ICT_REMOVE_BOOTPATH_FAILED')
				return ICT_REMOVE_BOOTPATH_FAILED
			if not _move_in_updated_config_file(newbootenvrc, self.BOOTENVRC):
				prerror('bootpath not removed from bootenv.rc')
				prerror('Failure. Returning: ICT_REMOVE_BOOTPATH_FAILED')
				return ICT_REMOVE_BOOTPATH_FAILED
		_dbg_msg('bootpath property removed from ' + self.BOOTENVRC)
		return 0

	def keyboard_layout(self):
		'''ICT - Get keyboard layout using ioctl KIOCLAYOUT on /dev/kbd
		Add LAYOUT to /etc/default/kbd' (see kbd(1))
		TM 1G
		return 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())

		#ioctl codes taken from /usr/include/sys/kbio.h
		KIOC = ord('k') << 8
		KIOCLAYOUT = KIOC | 20
		_dbg_msg("Opening keyboard device: " + self.KBD_DEVICE)
		try:
			kbd = open(self.KBD_DEVICE, "r+")
		except:
			prerror('Failure to open keyboard device ' + self.KBD_DEVICE)
			prerror('Failure. Returning: ICT_OPEN_KEYBOARD_DEVICE_FAILED')
			return ICT_OPEN_KEYBOARD_DEVICE_FAILED 
		if kbd == None:
			prerror('Failure to open keyboard device ' + self.KBD_DEVICE)
			prerror('Failure. Returning: ICT_OPEN_KEYBOARD_DEVICE_FAILED')
			return ICT_OPEN_KEYBOARD_DEVICE_FAILED 

		k = array.array('i', [0])
		status = fcntl.ioctl(kbd, KIOCLAYOUT, k, 1)
		if status != 0:
			kbd.close()
			prerror('fcntl ioctl KIOCLAYOUT_FAILED: status=' + str(status))
			prerror('Failure. Returning: ICT_KIOCLAYOUT_FAILED')
			return ICT_KIOCLAYOUT_FAILED 
		kbd_layout = k.tolist()[0]
		kbd.close()

		layout = self._get_kbd_layout_name(kbd_layout)
		if layout == '':
			prerror('keyboard layout name not found')
			prerror('Failure. Returning: ICT_KBD_LAYOUT_NAME_NOT_FOUND')
			return ICT_KBD_LAYOUT_NAME_NOT_FOUND

		kbd_file_name = self.BASEDIR + self.KBD_DEFAULTS_FILE
		try:
			kbd_file = open(kbd_file_name, "a+")
			kbd_file.write("LAYOUT=" + layout + "\n")
			kbd_file.close()
		except:
			prerror('Failure. Returning: ICT_KBD_DEFAULTS_FILE_ACCESS_FAILURE')
			return ICT_KBD_DEFAULTS_FILE_ACCESS_FAILURE
		
		_dbg_msg('Updated keyboard defaults file: ' + kbd_file_name)
		info_msg('Detected ' + layout + ' keyboard layout')
		return 0

	def delete_misc_trees(self):
		'''ICT - delete miscellanous directory trees used as work areas during installation
		TM
		always return success
		'''
		_register_task(inspect.currentframe())
		_cmd_status('rm -rf ' + self.BASEDIR + '/var/tmp/*')
		_cmd_status('rm -rf ' + self.BASEDIR + '/mnt/*')
		return 0

	def set_prop_from_eeprom(self, field):
		'''ICT - using eeprom(1M), fetch property and assign to bootenv.rc
		return 0 or error code
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		cmd = 'eeprom ' + field + ' | cut -f 2 -d ='
		try:
			status, ar = _cmd_out(cmd)
		except:
			prerror('eeprom command failed: cmd=' + cmd)
			prerror('Failure. Returning: ICT_EEPROM_GET_FAILED')
			return ICT_EEPROM_GET_FAILED
		if len(ar) == 0:
			prerror('Failure. Returning: ICT_EEPROM_GET_FAILED')
			return ICT_EEPROM_GET_FAILED
		return self._update_bootprop(field, ar[0])

	def create_smf_repository(self):
		'''ICT - copies /lib/svc/seed/global.db to /etc/svc/repository.db
		TM 3B
		returns 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		src = self.BASEDIR + '/lib/svc/seed/global.db'
		dst = self.BASEDIR + '/etc/svc/repository.db'
		try:
			shutil.copyfile(src, dst)
			os.chmod(dst,  S_IRUSR | S_IWUSR)
			os.chown(dst, 0, 3) # chown root:sys
		except OSError, (errno, strerror):
			prerror('Cannot create smf repository due to error in copying ' +
			    src + ' to ' + dst + ': ' + strerror)
			prerror('Failure. Returning: ICT_CREATE_SMF_REPO_FAILED')
			return ICT_CREATE_SMF_REPO_FAILED
		except:
			prerror('Unrecognized error - cannot create smf repository. source=' + src + ' destination=' + dst)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_CREATE_SMF_REPO_FAILED')
			return ICT_CREATE_SMF_REPO_FAILED
		return 0

	def create_mnttab(self):
		'''ICT - create /etc/mnttab if it doesn't already exist and chmod
		TM 3C
		returns 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		mnttab = self.BASEDIR + '/etc/mnttab'
		try:
			open(mnttab, 'w').close() # equivalent to touch(1)
			os.chmod(mnttab, S_IREAD | S_IRGRP | S_IROTH)
		except OSError, (errno, strerror):
			prerror('Cannot create ' + mnttab + ': ' + strerror)
			prerror('Failure. Returning: ICT_CREATE_MNTTAB_FAILED')
			return ICT_CREATE_MNTTAB_FAILED
		except:
			prerror('Unrecognized error - Cannot create ' + mnttab)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_CREATE_MNTTAB_FAILED')
			return ICT_CREATE_MNTTAB_FAILED
		return 0

	def add_splash_image_to_grub_menu(self):
		'''ICT - append splashimage and timeout commands to GRUB menu
		IF (TODO not listed in ICT design document)
		return 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		grubmenu = self.GRUBMENU
		try:
			fp = open(self.GRUBMENU, 'a+')
			fp.write('splashimage /boot/grub/splash.xpm.gz\n')
			fp.write('background 215ECA\n')
			fp.write('timeout 30\n')
			fp.close()
		except OSError, (errno, strerror):
			prerror('Error in appending splash image grub commands to ' + grubmenu + ': ' + strerror)
			prerror('Failure. Returning: ICT_ADD_SPLASH_IMAGE_FAILED')
			return ICT_ADD_SPLASH_IMAGE_FAILED
		except:
			prerror('Unrecognized error in appending splash image grub commands to ' + grubmenu)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_ADD_SPLASH_IMAGE_FAILED')
			return ICT_ADD_SPLASH_IMAGE_FAILED
		return 0

	def update_dumpadm_nodename(self):
		'''ICT - Update nodename in dumpadm.conf
		Note: dumpadm -r option does not work!!
		returns 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		nodename = self.BASEDIR + '/etc/nodename'
		dumpadmfile = self.BASEDIR + '/etc/dumpadm.conf'
		try:
			fnode = open(nodename, 'r')
			na = fnode.readlines()
			fnode.close()
		except OSError, (errno, strerror):
			prerror('Error in accessing ' + nodename + ': ' + strerror)
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED
		except:
			prerror('Unrecognized error in accessing ' + nodename)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED
		nodename = na[0][:-1]
		try:
			(fp, newdumpadmfile) = tempfile.mkstemp('.conf', 'dumpadm', '/tmp')
			os.close(fp)
		except OSError, (errno, strerror):
			prerror('Error in writing to temporary file: ' + strerror)
			prerror('Cannot update dumpadm nodename ' + filename)
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED
		except:
			prerror('Unrecognized error - cannot update dumpadm nodename ' + filename)
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED

		status = _cmd_status('cat ' + dumpadmfile + ' | '+
		    'sed s/opensolaris/' + nodename + '/ > ' + newdumpadmfile)
		if status != 0:
			try:
				os.unlink(newdumpadmfile)
			except OSError:
				pass
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED

		if not _move_in_updated_config_file(newdumpadmfile, dumpadmfile):
			prerror('Failure. Returning: ICT_UPDATE_DUMPADM_NODENAME_FAILED')
			return ICT_UPDATE_DUMPADM_NODENAME_FAILED
		return 0

	def explicit_bootfs(self):
		'''ICT - For libbe to be able to support the initial boot environment,
		we need an explicit bootfs value in our menu entry.  Add it
		to the entry before the ZFS-BOOTFS line.  This, along with the
		rest of the grub menu entry manipulation code in this file, will
		eventually need to get ripped out when we have support in libbe
		to create and activate the grub entry for the initial boot
		environment.
		returns 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		rootdataset = self._get_root_dataset()
		if rootdataset == '':
			prerror('Could not determine root dataset from vfstab')
			prerror('Failure. Returning: ICT_EXPLICIT_BOOTFS_FAILED')
			return ICT_EXPLICIT_BOOTFS_FAILED
		newgrubmenu = self.GRUBMENU + '.new'
		sedcmd = 'sed \'/\-B[ 	]*\\$ZFS-BOOTFS/ i\\\nbootfs ' +\
		    rootdataset + '\' ' + self.GRUBMENU + ' > ' + newgrubmenu
		status = _cmd_status(sedcmd)
		if status != 0:
			prerror('Adding bootfs command to grub menu fails. exit status=' + int(status))
			prerror('Failure. Returning: ICT_EXPLICIT_BOOTFS_FAILED')
			return ICT_EXPLICIT_BOOTFS_FAILED
		try:
			shutil.move(newgrubmenu, self.GRUBMENU)
		except OSError, (errno, strerror):
			prerror('Moving GRUB menu ' + newgrubmenu + ' to ' +
			    self.GRUBMENU + ' failed. ' + strerror)
			prerror('Failure. Returning: ICT_EXPLICIT_BOOTFS_FAILED')
			return ICT_EXPLICIT_BOOTFS_FAILED
		except:
			prerror('Unrecognized error - cannot move GRUB menu ' +
			    newgrubmenu + ' to ' + self.GRUBMENU)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_EXPLICIT_BOOTFS_FAILED')
			return ICT_EXPLICIT_BOOTFS_FAILED
		return 0

	def enable_happy_face_boot(self):
		'''ICT - Enable happy face boot
		Find the first entry in the menu.lst file and enable graphical
		Happy Face boot for that entry.

		To enable Happy Face boot:
		above the ZFS-BOOTFS line add:
			splashimage /boot/solaris.xpm
			foreground d25f00
			background 115d93
		and to the end of the kernel line add: console=graphics

		The original content of the first entry will be saved to
		create an additional "text boot" entry, that doesn't
		support graphical Happy Face boot. Comments and white
		space from the original entry will not be included in
		the additional entry. The "text boot" entry will be inserted
		as the last entry.

		If more than one entry exist in the original menu.lst file,
		only the first entry will be modified to enable graphical
		Happy Face boot.

		returns 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		splash = 'splashimage /boot/solaris.xpm\n'
		foreground = 'foreground d25f00\n'
		background = 'background 115d93\n'

		all = []
		one_entry = []
		copying_entry  = 0
		need_entry  = 1
		need_graphical  = 1
		line = ''
		op = None

		try:
			op = open(self.GRUBMENU, 'r')
		except IOError, (errno, strerror):
			prerror('Error opening GRUB menu.lst file for reading' +
			    strerror + ' file=' + self.GRUBMENU + '\n')
			return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED

		# Read the GRUB menu file into list all.
		# Adjust the contents of list all to enable graphical boot.
		# Copy the one menu entry found in the GRUB menu file to list one_entry.
		# Modify the title in list one_entry.
		# Append list one_entry to list all.
		try:
			try:
				for line in op:
					# Adjust the contents of list all to
					# enable graphical boot.
					if need_graphical:
						if line.startswith('kernel'):
							all.append(line.strip()
							    + ',console=graphics\n')
							need_graphical = 0
						else:
							all.append(line)

						if line.startswith('findroot'):
							all.append(splash)
							all.append(foreground)
							all.append(background)
					else:
						all.append(line)

					if line.startswith('title'):
						if need_entry:
							# If this is the first entry set flags so
							# it will be copied.
							need_entry = 0
							copying_entry = 1
						else:
							# The first entry has been copied set flags
							# so no other entries will be copied.
							copying_entry = 0

					if copying_entry:
						if line.startswith('title'):
							# strip the newline char and
							# add text boot
							line = line.strip() + ' text boot\n'
						# Don't copy blank lines or comments to the
						# one_entry list.
						if ((len(line.strip()) != 0) and
						    (line.startswith('#') == False)):
							one_entry.append(line)

			except IOError, (errno, strerror):
				prerror('Error reading GRUB menu.lst file \n' +
				    strerror + ' file=' + self.GRUBMENU + '\n')
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED
			except:
				prerror('Unexpected error encountered while updating \n' +
				    ' file=' + self.GRUBMENU + '\n')
				#traceback to stdout and log)
				prerror(traceback.format_exc())
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED
		finally:
			try:
				op.close()
			except IOError, (errno, strerror):
				prerror('Error closing the GRUB menu.lst file' +
				    strerror + ' file=' + self.GRUBMENU + '\n')
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED

		one_entry.append('\n')
		all.append('\n')

		# Append the single entry saved list one_entry to list all.
		all.extend(one_entry)

		# Update the GRUB menu.lst with the updates made.
		try:
			op = open(self.GRUBMENU, 'w')
		except IOError, (errno, strerror):
			prerror('Error opening GRUB menu.lst file for writing \n' +
			    strerror + ' file=' + self.GRUBMENU + '\n')
			return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED

		try:
			try:
				for line in all:
					op.write(line)
			except IOError, (errno, strerror):
				prerror('Error writting GRUB menu.lst file' +
				    strerror + ' file=' + self.GRUBMENU + '\n')
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED
			except:
				prerror('Unexpected error encountered while updating \n' +
				    ' file=' + self.GRUBMENU + '\n')
				#traceback to stdout and log)
				prerror(traceback.format_exc())
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED
		finally:
			try:
				op.close()
			except IOError, (errno, strerror):
				prerror('Error closing the GRUB menu.lst file' +
				    strerror + ' file=' + self.GRUBMENU + '\n')
				return ICT_ENABLE_HAPPY_FACE_BOOT_FAILED

		return 0

	def setup_dev_namespace(self):
		# ICT - Setup the dev namespace on the target using devfsadm(1M)
		# if installing from IPS.
		#
		# Test if installing from IPS.
		# launch devfsadm -R BASEDIR
		# return 0 for success, error code otherwise
		#
		_register_task(inspect.currentframe())

		# launch devfsadm -R BASEDIR
		cmd = '/usr/sbin/devfsadm -R ' + self.BASEDIR + ' 2>&1'
		status, cmdout = _cmd_out(cmd)
		if status != 0:
			prerror('Setting up dev namespace fails. exit status=' + str(status) +
			    ' command=' + cmd)
			prerror('Failure. Returning: ICT_SETUP_DEV_NAMESPACE_FAILED')
			return ICT_SETUP_DEV_NAMESPACE_FAILED
		for ln in cmdout:
			info_msg('devfsadm command output: ' + ln)
		return 0

	def update_boot_archive(self):
		'''ICT - update archive using bootadm(1M)
		launch bootadm update-archive -R BASEDIR
		return 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		cmd = 'bootadm update-archive -R ' + self.BASEDIR + ' 2>&1'
		status, cmdout = _cmd_out(cmd)
		if status != 0:
			prerror('Updating boot archive fails. exit status=' + str(status) +
			    ' command=' + cmd)
			prerror('Failure. Returning: ICT_UPDATE_ARCHIVE_FAILED')
			return ICT_UPDATE_ARCHIVE_FAILED
		for ln in cmdout:
			info_msg('bootadm update-archive output: ' + ln)
		return 0

	def remove_files(self, filelist):
		'''ICT - remove list of files
		return 0 if successful, error code otherwise
		'''
		_register_task(inspect.currentframe())
		return_status = 0
		for delfile in filelist:
			delfile = self.BASEDIR + delfile
			_dbg_msg('Removing ' + delfile)
			try:
				os.unlink(delfile)
			except OSError, (errno, strerror):
				if errno == 2: # not found
					_dbg_msg(delfile + ' not found during deletion attempt')
				else:
					prerror('Remove ' + delfile + ' failed. ' + strerror)
					prerror('Failure. Returning: ICT_REMOVE_FILESTAT_RAMDISK_FAILED')
					return ICT_REMOVE_FILESTAT_RAMDISK_FAILED
			except:
				prerror('Unrecognized error - cannot delete ' + delfile)
				prerror(traceback.format_exc())
				prerror('Failure. Returning: ICT_REMOVE_FILESTAT_RAMDISK_FAILED')
				return_status = ICT_REMOVE_FILESTAT_RAMDISK_FAILED
		return return_status

	def copy_splash_xpm(self):
		'''ICT - copy splash file to grub directory in new root pool
		returns 0 for success or ICT status code
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		src = self.BASEDIR + '/boot/grub/splash.xpm.gz'
		dst = '/' + self.rootpool + '/boot/grub/splash.xpm.gz'
		try:
			shutil.copy(src, dst)
		except OSError, (errno, strerror):
			prerror('Copy splash file ' + src + ' to ' + dst + ' failed. ' + strerror)
			prerror('Failure. Returning: ICT_COPY_SPLASH_XPM_FAILED')
			return ICT_COPY_SPLASH_XPM_FAILED
		except:
			prerror('Unrecognized error - Could not copy splash file ' + src + ' to ' + dst)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_COPY_SPLASH_XPM_FAILED')
			return ICT_COPY_SPLASH_XPM_FAILED
		return 0

	def smf_correct_sys_profile(self):
		'''ICT - Point SMF at correct system profile
		return 0 if all files deleted and symlinks created, error status otherwise
		'''
		_register_task(inspect.currentframe())
		return_status = 0 #assume success until proven otherwise
		#delete and recreate links
		for src, dst in (
		    ('generic_limited_net.xml',  self.BASEDIR + '/var/svc/profile/generic.xml'),
		    ('ns_dns.xml', self.BASEDIR + '/var/svc/profile/name_service.xml'),
		    ('inetd_generic.xml', self.BASEDIR + '/var/svc/profile/inetd_services.xml')):
			try:
				os.unlink(dst)
			except OSError, (errno, strerror):
				if errno != 2: #file not found
					prerror('Error deleting file ' + dst +
					    ' for smf profile. ' + strerror)
					prerror('Failure. Returning: ICT_SMF_CORRECT_SYS_PROFILE_FAILED')
					return_status = ICT_SMF_CORRECT_SYS_PROFILE_FAILED
			except:
				prerror('Unrecognized error - could not delete file ' +
				    dst + ' for smf profile. ')
				prerror(traceback.format_exc())
				prerror('Failure. Returning: ICT_SMF_CORRECT_SYS_PROFILE_FAILED')
				return_status = ICT_SMF_CORRECT_SYS_PROFILE_FAILED
			try:
				os.symlink(src, dst)
			except OSError, (errno, strerror):
				prerror('Error making symlinks for system profile. ' + strerror)
				prerror('source=' + src + ' destination=' + dst)
				prerror('Failure. Returning: ICT_SMF_CORRECT_SYS_PROFILE_FAILED')
				return_status = ICT_SMF_CORRECT_SYS_PROFILE_FAILED
			except:
				prerror('Unrecognized error making symlinks for system profile.')
				prerror('source=' + src + ' destination=' + dst)
				prerror(traceback.format_exc())
				prerror('Failure. Returning: ICT_SMF_CORRECT_SYS_PROFILE_FAILED')
				return_status = ICT_SMF_CORRECT_SYS_PROFILE_FAILED
		return return_status

	def add_sysidtool_sys_unconfig_entries(self, more_entries = None):
		'''ICT - Add entries for sysidtool and sys-unconfig to run all known external apps.
		creates /etc/.sysidconfig.apps
		touches /etc/.UNCONFIGURED
		copy .sysIDtool.state to the target
		Parameter: more_entries - list of additional entries for .sysidconfig.apps
		return 0 if everything worked, error code if anything failed
		'''
		_register_task(inspect.currentframe())
		sys_unconfig_entries = [
			'/lib/svc/method/sshd',
			'/usr/sbin/sysidkbd',
			'/usr/lib/cc-ccr/bin/eraseCCRRepository',
			'/usr/sbin/sysidpm',
			'/usr/lib/scn/bin/cleanup-scn-base',
			'/lib/svc/method/net-nwam',
			]
		return_status = 0
		try:
			sysidconfigapps = self.BASEDIR + '/etc/.sysidconfig.apps'
			fp = open(sysidconfigapps, 'w')
			if more_entries: sys_unconfig_entries.extend(more_entries)
			for sys_unconfig_entry in sys_unconfig_entries:
				fp.write(sys_unconfig_entry + '\n')
			fp.close()
		except OSError, (errno, strerror):
			if errno != 2:
				prerror('Error creating ' + sysidconfigapps + ' - ' + strerror)
				prerror('Failure. Returning: ICT_SYSIDTOOL_ENTRIES_FAILED')
				return_status = ICT_SYSIDTOOL_ENTRIES_FAILED
		except IOError, (errno, strerror):
			if errno != 2:
				prerror('Error creating ' + sysidconfigapps + ' - ' + strerror)
				prerror('Failure. Returning: ICT_SYSIDTOOL_ENTRIES_FAILED')
				return_status = ICT_SYSIDTOOL_ENTRIES_FAILED
		except:
			prerror('Unrecognized error creating ' + sysidconfigapps)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_SYSIDTOOL_ENTRIES_FAILED')
			return_status = ICT_SYSIDTOOL_ENTRIES_FAILED
		#touch /etc/.UNCONFIGURED
		try:
			unconfigured = self.BASEDIR + '/etc/.UNCONFIGURED'
			open(unconfigured, 'w').close()
		except OSError, (errno, strerror):
			prerror('Error touching ' + unconfigured + ' - ' + strerror)
			prerror('Failure. Returning: ICT_SYSIDTOOL_ENTRIES_FAILED')
			return_status = ICT_SYSIDTOOL_ENTRIES_FAILED
		except:
			prerror('Unrecognized error touching ' + unconfigured)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_SYSIDTOOL_ENTRIES_FAILED')
			return_status = ICT_SYSIDTOOL_ENTRIES_FAILED


		#copy .sysIDtool.state to the target
		try:
			src = '/etc/.sysIDtool.state'
			dst = self.BASEDIR + '/etc/.sysIDtool.state'
			shutil.copy(src, dst)
		except OSError, (errno, strerror):
			prerror('Failed to copy the contents of file src to file dst' +
			    strerror + ' src=' + src + '\n dst=' + dst + '\n')
			prerror('Failure. Returning: ICT_SYSIDTOOL_CP_STATE_FAILED')
			return_status = ICT_SYSIDTOOL_CP_STATE_FAILED
		except:
			prerror('Unexpected error during copy of src to dst' +
			    ' src=' + src + '\n dst=' + dst + '\n')
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_SYSIDTOOL_CP_STATE_FAILED')
			return_status = ICT_SYSIDTOOL_CP_STATE_FAILED

		return return_status

	def enable_nwam_AI(self):
		'''ICT - Enable nwam service in AI environment
			If running in an autoinstall environment, 
			add file /var/svc/profile/upgrade, which is a 
			hack to enable nwam and can be taken out once 
			the nwam profile is included
			in the SMF global seed repository

		return 0, otherwise error status
		'''
		_register_task(inspect.currentframe())

		return_status = 0
		op = None

		upgradefile = self.BASEDIR + '/var/svc/profile/upgrade'
		disable_net_def = '/usr/sbin/svcadm disable network/physical:default'
		enable_net_nwam = '/usr/sbin/svcadm enable network/physical:nwam'

		try:
			op = open(upgradefile, 'a')
			#add the line with the updated property
			op.write(disable_net_def + '\n')
			op.write(enable_net_nwam + '\n')
		except OSError, (errno, strerror):
			prerror('Update to <target>/var/svc/profile/upgrade to enable nwam failed. ' +
			    strerror + ' file=' + upgradefile + 'failed to add the lines:\n' +
			    disable_net_def + '\n' + enable_net_nwam + '\n')
			prerror('Failure. Returning: ICT_ENABLE_NWAM_AI_FAILED')
			return_status = ICT_ENABLE_NWAM_AI_FAILED
		except:
			prerror('Unexpected error during updating to <target>/var/svc/profile/upgrade to enable nwam. ' +
			    ' file=' + upgradefile + 'failed to add the lines:\n' +
			    disable_net_def + '\n' + enable_net_nwam + '\n')
			prerror(traceback.format_exc()) #traceback to stdout and log
			prerror('Failure. Returning: ICT_ENABLE_NWAM_AI_FAILED')
			return_status = ICT_ENABLE_NWAM_AI_FAILED

		if op != None: op.close()

		return return_status

	def enable_nwam(self):
		'''ICT - Enable nwam service
			SVCCFG_DTD=BASEDIR + '/usr/share/lib/xml/dtd/service_bundle.dtd.1'
			SVCCFG_REPOSITORY=BASEDIR + '/etc/svc/repository.db'
			svccfg apply BASEDIR + '/var/svc/profile/network_nwam.xml'
		return 0, otherwise error status
		'''
		_register_task(inspect.currentframe())

		return_status = 0
		op = None

		nwam_profile = self.BASEDIR + '/var/svc/profile/network_nwam.xml'
		os.putenv('SVCCFG_DTD', self.BASEDIR + '/usr/share/lib/xml/dtd/service_bundle.dtd.1')
		os.putenv('SVCCFG_REPOSITORY', self.BASEDIR + '/etc/svc/repository.db')
		cmd = '/usr/sbin/svccfg apply ' + nwam_profile + ' 2>&1'
		status, oa = _cmd_out(cmd)
		if status != 0:
			prerror('Command to enable nwam failed. exit status=' + str(status))
			prerror('Command to enable nwam was: ' + cmd)
			for ln in oa:
				prerror(ln)

			prerror('Failure. Returning: ICT_ENABLE_NWAM_FAILED')
			return_status = ICT_ENABLE_NWAM_FAILED

		return return_status

	def remove_liveCD_environment(self):
		'''ICT - Copy saved configuration files to remove vestiges of live CD environment
		return 0 for success, error code otherwise
		'''
		savedir = self.BASEDIR + '/save'
		if not os.path.exists(savedir):
			info_msg('saved configuration files directory is missing')
			return 0 # empty - assume no config files to back up
		cmd = '(cd %s && find . -type f -print | cpio -pmu %s) && rm -rf %s' \
		    % (savedir, self.BASEDIR, savedir)
		status = _cmd_status(cmd)
		if status == 0:
			return 0
		prerror('remove liveCD environment failed: exit status ' + str(status))
		prerror('command was ' + cmd)
		prerror('Failure. Returning: ICT_REMOVE_LIVECD_ENVIRONMENT_FAILED')
		return ICT_REMOVE_LIVECD_ENVIRONMENT_FAILED

	def remove_install_specific_packages(self, pkg_list):
		'''ICT - Remove install-specific packages
		launch pkg -R BASEDIR uninstall PACKAGE
		Parameter: pkg_list - list of pkg names
		return 0 for success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		return_status = 0
		for pkg in pkg_list:
			cmd = 'pkg -R %s uninstall -q --no-index %s 2>&1' % (self.BASEDIR, pkg)
			status, cmdout = _cmd_out(cmd)
			if status != 0:
				prerror('Removal of package %s failed.  pkg exit status =%d' %
				    (pkg, status))
				prerror('Failed package removal command=' + cmd)
				for ln in cmdout:
					prerror(ln)
				prerror('Failure. Returning: ICT_PACKAGE_REMOVAL_FAILED')
				return_status = ICT_PACKAGE_REMOVAL_FAILED
		return return_status

	def set_flush_content_cache_on_success_false(self):
		'''ICT - The LiveCD can be configured to purge the IPS download cache.
		Restore the original IPS default to not purge the IPS download cache.
		There is no command line interface in IPS to modify the option for now,
		so, we will manually modify the IPS configuration file.

		In /var/pkg/cfg_cache, set flush-content-cache-on-success-on-success = False

		Bug 2266 is filed to track the feature of having a
		command line option purge the download cache.
		http://defect.opensolaris.org/bz/show_bug.cgi?id=2266
		return 0 upon success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		cfg_file = self.BASEDIR + '/var/pkg/cfg_cache'
		new_cfg_file = '/tmp/cfg_cache.mod'

		cmd = 'sed \'s/^flush-content-cache-on-success.*/flush-content-cache-on-success = False/\' ' + \
		    cfg_file + ' > ' + new_cfg_file
		status = _cmd_status(cmd)
		if status != 0:
			prerror('Error setting flush-content-cache-on-success in ' + 
				cfg_file + ' exit status=' + str(status))
			prerror('Failure. Returning: ICT_SET_FLUSH_CONTENT_CACHE_ON_SUCCESS_FAILED')
			return ICT_SET_FLUSH_CONTENT_CACHE_ON_SUCCESS_FAILED
		if not _move_in_updated_config_file(new_cfg_file, cfg_file):
			prerror('Failure. Returning: ICT_SET_FLUSH_CONTENT_CACHE_ON_SUCCESS_FAILED')
			return ICT_SET_FLUSH_CONTENT_CACHE_ON_SUCCESS_FAILED
		return 0

	def set_console_boot_device_property(self):
		'''ICT - update bootenv.rc 'console' property
		determines console boot device from bootenv.rc properties 'output-device' and 'console'
		updates 'console' bootenv.rc property
		return status = 0 if success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		# put it in bootenv.rc
		curosconsole = self._get_bootprop('output-device')
		osconsole = self._get_osconsole()
		if curosconsole != osconsole and osconsole != '':
			info_msg('Setting console boot device property to ' + osconsole)
			status = self._update_bootprop('console', osconsole)
			if status != 0:
				return status
		return 0

	#set web browser home page
	#return 0 for success, otherwise error code
	def fix_browser_home_page(self):
		'''ICT - The default browser home page on the live CD provides installation
		information. After installation a different page provides information
		for what else the user can or should do.
		edit browser.startup.homepage in /usr/lib/firefox/browserconfig.properties
		return 0 on success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		browsercfg = self.BASEDIR + '/usr/lib/firefox/browserconfig.properties'
		indexURL = 'file:///usr/share/doc/opensolaris-welcome/html/index.html'
		try:
			(fp,tmpbrowsercfg) = tempfile.mkstemp('.properties', 'browserconfig', '/tmp')
			os.close(fp)
		except OSError, (errno, strerror):
			prerror('I/O error in creating temporary file for web browser configuration: ' + strerror)
			prerror('Failure. Returning: ICT_FIX_BROWSER_HOME_PAGE_FAILED')
			return ICT_FIX_BROWSER_HOME_PAGE_FAILED
		except:
			prerror('Unrecognized error - cannot delete file ' + filename)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_FIX_BROWSER_HOME_PAGE_FAILED')
			return ICT_FIX_BROWSER_HOME_PAGE_FAILED
		sedcmd = 'sed -e \'s+browser.startup.homepage=.*$+browser.startup.homepage=' + indexURL + '+\' '+\
		    '-e \'s+browser.startup.homepage_reset=.*$+browser.startup.homepage_reset=' +\
		    indexURL + '+\' '+ browsercfg + ' > '+ tmpbrowsercfg
		status = _cmd_status(sedcmd)
		if (status != 0):
			prerror('Setting browser home page command failed. exit status=' + str(status))
			prerror('Failed command was ' + sedcmd)
			prerror('Failure. Returning: ICT_FIX_BROWSER_HOME_PAGE_FAILED')
			return ICT_FIX_BROWSER_HOME_PAGE_FAILED
		if not _move_in_updated_config_file(tmpbrowsercfg, browsercfg):
			prerror('Could not update browser configuration file ' + browsercfg)
			prerror('Failure. Returning: ICT_FIX_BROWSER_HOME_PAGE_FAILED')
			return ICT_FIX_BROWSER_HOME_PAGE_FAILED
		return 0

	def remove_liveCD_coreadm_conf(self):
		'''ICT - Remove LiveCD-specific /etc/coreadm.conf config file. Coreadm will
		create its initial configuration on first boot 
		see also coreadm(1m)
		returns 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		filename = self.BASEDIR + '/etc/coreadm.conf'
		try:
			os.unlink(filename)
		except OSError, (errno, strerror):
			if errno != 2: #file does not exist
				prerror('I/O error - cannot delete file ' + filename + ': ' + strerror)
				prerror('Failure. Returning: ICT_REMOVE_LIVECD_COREADM_CONF_FAILURE')
				return ICT_REMOVE_LIVECD_COREADM_CONF_FAILURE
		except:
			prerror('Unrecognized error - cannot delete file ' + filename)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_REMOVE_LIVECD_COREADM_CONF_FAILURE')
			return ICT_REMOVE_LIVECD_COREADM_CONF_FAILURE
		return 0

	def set_Solaris_partition_active(self):
		'''ICT - set the Solaris partition on the just installed drive to active
		rewrites disk format tables - see set_boot_active()
		return 0 if no errors for any drive, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		# since the root device might be a metadevice, all the components need to
		# be located so each can be operated upon individually
		return_status, rdlist = self.get_rootdev_list()
		if return_status == 0:
			for rootdev in rdlist:
				_dbg_msg('root device: ' + rootdev)
				status = self.set_boot_active(rootdev)
				if status != 0:
					return_status = status
				status = self.bootadm_update_menu(rootdev)
				if status != 0:
					return_status = status
		#if any operation fails, return error status
		return return_status

	def fix_grub_entry(self):
		'''ICT - Fix up the grub entry. This is required because bootadm 'assumes'
		Solaris. And, even though /etc/release says OpenSolaris it truncates
		the 'Open' off. Replace this globally.
		return 0 on success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		newgrubmenu = self.GRUBMENU + '.new'
		cmd = '/bin/sed -e \'s/title Solaris/title OpenSolaris/g\' ' +\
		    self.GRUBMENU + ' > ' + newgrubmenu
		status = _cmd_status(cmd)
		if status == 0:
			if not _move_in_updated_config_file(newgrubmenu, self.GRUBMENU):
				prerror('Failure. Returning: ICT_FIX_GRUB_ENTRY_FAILED')
				return ICT_FIX_GRUB_ENTRY_FAILED
		else:
			prerror('fix grub entry cmd=' + cmd + ' returns ' + str(status))
			prerror('Failure. Returning: ICT_FIX_GRUB_ENTRY_FAILED')
			return ICT_FIX_GRUB_ENTRY_FAILED
		return 0

	def add_other_OS_to_grub_menu(self):
		'''ICT - add entries for other installed OS's to the grub menu
		Launch /sbin/mkmenu <target GRUB menu>
		return 0 on success, error code otherwise
		'''
		_register_task(inspect.currentframe())
		#This ICT is not supported on SPARC platforms.
		#If invoked on a SPARC platform quietly return success.
		if self.IS_SPARC:
			prerror('This ICT is not supported on this hardware platform.')
			prerror('Failure. Returning: ICT_INVALID_PLATFORM')
			return ICT_INVALID_PLATFORM

		cmd = '/sbin/mkmenu ' + self.GRUBMENU
		cwd_start = os.getcwd()
		os.chdir('/')
		status = _cmd_status(cmd)
		os.chdir(cwd_start)
		if status != 0:
			prerror('Add other OS to grub menu failed. command=' + cmd + 
			    ' exit status=' + str(status))
			prerror('Failure. Returning: ICT_MKMENU_FAILED')
			return ICT_MKMENU_FAILED
		return 0

	def do_clobber_files(self, flist_file):
		'''ICT - Given a file containing a list of pathnames,
                search for those entries in the alternate root and
                delete all matching pathnames from the alternate root that
                are symbolic links.
                This process is required because of the way the LiveCD env
                is constructed. Some of the entries in the boot_archive are
                symbolic links to files mounted off a compressed lofi file.
                This is done to drastically reduce space usage by the boot_archive.
		TM 3G
		side effect: current directory changed to BASEDIR
		returns 0 if all processing completed successfully, error code if any problems
		'''
		_register_task(inspect.currentframe())
                _dbg_msg("File with list of pathnames with symbolic links to clobber: " + flist_file)
		try:
                	fh = open(flist_file, 'r')
                	os.chdir(self.BASEDIR)
		except OSError, (errno, strerror):
			prerror('I/O error - cannot access clobber list file ' + flist_file + ': ' + strerror)
			prerror('Failure. Returning: ICT_CLOBBER_FILE_FAILED')
			return ICT_CLOBBER_FILE_FAILED
                except:
			prerror('Unrecognized error processing clobber list file ' + flist_file)
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_CLOBBER_FILE_FAILED')
			return ICT_CLOBBER_FILE_FAILED
		return_status = 0
		for line in fh:
                        line = line[:-1]
                        try:
                                mst = os.lstat(line)
                                if S_ISLNK(mst.st_mode):
                                        _dbg_msg("Unlink: " + line)
                                        os.unlink(line)
			except OSError, (errno, strerror):
				if errno == 2: #file does not exist
					_dbg_msg('Pathname ' + line + ' not found - nothing deleted')
				else:
					prerror('I/O error - cannot delete soft link ' + filename + ': ' + strerror)
					prerror('Failure. Returning: ICT_CLOBBER_FILE_FAILED')
					return_status = ICT_CLOBBER_FILE_FAILED #one or more items fail processing
                        except:
				prerror('Unrecognized error during file ' + line + ' clobber')
				prerror(traceback.format_exc())
                fh.close()
		return return_status

	def cleanup_unneeded_files_and_directories(self, more_cleanup_files = None, more_cleanup_dirs = None):
		'''ICT - removes list of files and directories that should not have been copied
		If these are of appreciable size, they should be withheld from cpio file
			list instead
		Parameters:
			more_cleanup_files - list of additional files to delete
			more_cleanup_dirs - list of additional directories to delete
		TM 3G
		returns 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		# Cleanup the files and directories that were copied into
		# the BASEDIR directory that are not needed by the installed OS.
		file_cleanup_list = [
		    "/boot/boot_archive",
		    "/.livecd",
		    "/.volumeid",
		    "/boot/grub/menu.lst",
		    "/etc/sysconfig/language",
		    "/.liveusb",
		    "/.image_info",
		    "/.catalog"
		    ]
		dir_cleanup_list = [
		    "/a",
		    "/bootcd_microroot"
		    ]
		if more_cleanup_files: file_cleanup_list.extend(more_cleanup_files)
		if more_cleanup_dirs: dir_cleanup_list.extend(more_cleanup_dirs)
		return_status = 0
		for basefname in file_cleanup_list:
			fname = self.BASEDIR + "/" + basefname
			_dbg_msg('Removing file ' + fname)
			try:
				os.remove(fname)
			except OSError, (errno, strerror):
				if errno == 2: # file not found
					_dbg_msg('File to delete was not found: ' + fname)
				else:
					prerror('Error deleting file ' + fname + ': ' + strerror)
					prerror('Failure. Returning: ICT_CLEANUP_FAILED')
					return_status = ICT_CLEANUP_FAILED
			except:
				prerror('Unexpected error deleting directory.')
				prerror(traceback.format_exc())

		# The bootcd_microroot directory should be cleaned up in the
		# Distribution Constructor once they have finished the redesign.
		for basedname in dir_cleanup_list:
			dname = self.BASEDIR + "/" + basedname
			_dbg_msg('removing directory' + dname)
			try:
				os.rmdir(dname)
			except OSError, (errno, strerror):
				if errno == 2: # file not found
					_dbg_msg('Path to delete was not found: ' + dname)
				else:
					prerror('Error deleting directory ' + dname + ': ' + strerror)
					prerror('Failure. Returning: ICT_CLEANUP_FAILED')
					return_status = ICT_CLEANUP_FAILED
			except:
				prerror('Unexpected error deleting file.')
				prerror(traceback.format_exc())
		return return_status

	def reset_image_UUID(self):
		'''ICT - reset pkg(1) image UUID for opensolaris.org
		launch pkg -R BASEDIR set-authority --reset-uuid --no-refresh opensolaris.org
		launch pkg -R BASEDIR pkg set-property send-uuid True
		return 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		cmd = 'pkg -R ' + self.BASEDIR + ' set-authority --reset-uuid --no-refresh opensolaris.org'
		status = _cmd_status(cmd)
		if status != 0:
			prerror('Reset uuid failed - exit status = ' + str(status) +
			    ', command was ' + cmd)
			prerror('Failure. Returning: ICT_PKG_RESET_UUID_FAILED')
			return ICT_PKG_RESET_UUID_FAILED

		cmd = 'pkg -R ' + self.BASEDIR + ' set-property send-uuid True'
		status = _cmd_status(cmd)
		if status != 0:
			prerror('Set property send uuid - exit status = ' + str(status) +
			    ', command was ' + cmd)
			prerror('Failure. Returning: ICT_PKG_SEND_UUID_FAILED')
			return ICT_PKG_SEND_UUID_FAILED

		return 0

	def rebuild_pkg_index(self):
		'''ICT - rebuild pkg(1) index
		launch pkg -R BASEDIR rebuild-index
		return 0 for success, otherwise error code
		'''
		_register_task(inspect.currentframe())
		cmd = 'pkg -R ' + self.BASEDIR + ' rebuild-index'
		status = _cmd_status(cmd)
		if status == 0:
			return 0
		prerror('Rebuild package index failed - exit status = ' + str(status) +
		    ', command was ' + cmd)
		prerror('Failure. Returning: ICT_REBUILD_PKG_INDEX_FAILED')
		return ICT_REBUILD_PKG_INDEX_FAILED

	def create_new_user(self, gcos, login, pw, gid, uid):
		'''ICT - create the new user.
		using IPS class PasswordFile from pkg.cfgfiles
		It is possible no new user was requested. If none was
		specified do nothing and return 0.
		return 0 on success, error code otherwise
		'''
		_register_task(inspect.currentframe())

		return_status = 0
		_dbg_msg('creating new user on target: ' + self.BASEDIR)

		if not login:
			_dbg_msg('No login specified')
			return return_status

		try:
			p = PasswordFile(self.BASEDIR)
			nu = p.getuser('nobody')
			nu['username'] = login
			nu['gid'] = gid
			nu['uid'] = uid
			nu['gcos-field'] = gcos
			nu['home-dir'] = '/export/home/' + login
			nu['login-shell'] = '/bin/bash'
			nu['password'] = pw
			p.setvalue(nu)
			p.writefile()

		except:
			prerror('Failure to modify the root password')
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_CREATE_NU_FAILED')
			return_status = ICT_CREATE_NU_FAILED

		return return_status

	def set_root_password(self, newpw):
		'''ICT - set the root password on the specified install target.
		using IPS class PasswordFile from pkg.cfgfiles
		return 0 on success, error code otherwise
		'''
		_register_task(inspect.currentframe())

		return_status = 0
		_dbg_msg('setting root password on target: ' + self.BASEDIR)

		try:
			p = PasswordFile(self.BASEDIR)
			ru = p.getuser('root')
			ru['password'] = newpw
			p.setvalue(ru)
			p.writefile()
		except:
			prerror('Failure to modify the root password')
			prerror(traceback.format_exc())
			prerror('Failure. Returning: ICT_SET_ROOT_PW_FAILED')
			return_status = ICT_SET_ROOT_PW_FAILED

		return return_status

	def ict_test(self):
		info_msg('ict test called')
		return 0

	#end Install Completion Tasks

def exec_ict(ICT, BASEDIR, debuglvl=None, optparm=None):
	'''run one ICT with a single command line using 'eval()'
	This will be called automatically if 2 or more command line arguments are provided
	ICT - name of ICT in text string
	BASEDIR - root directory of target
	debuglvl - logging service debugging level to override default
	optparm - parameter passed to ICT if required by ICT
	returns status of ICT
	'''
	info_msg('Executing single ICT=' + ICT + ' basedir=' + BASEDIR)
	if debuglvl != None:
		print 'setting debug level to',debuglvl
		myict = ict(BASEDIR, debuglvl)
	else:
		myict = ict(BASEDIR)
	if optparm != None:
		status = eval('myict.' + ICT + '(optparm)')
	else:
		status = eval('myict.' + ICT + '()')
	sys.exit(status)

if __name__ == '__main__' and sys.argv[2:] and sys.argv[1] in dir(ict):
	'''if 2 or more command line arguments are provided, assume that script is launched
	in order to run one individual ICT
	tests for valid ICT in second parameter - ignore if not class method

	Example command line:  # python ict.py ict_test /a  #runs test ICT
	'''
	if sys.argv[4:]:
		status = exec_ict(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
	elif sys.argv[3:]:
		status = exec_ict(sys.argv[1], sys.argv[2], sys.argv[3])
	else:
		status = exec_ict(sys.argv[1], sys.argv[2])
