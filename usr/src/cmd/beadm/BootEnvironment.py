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
# Boot Environment classes used by beadm.

import datetime

class BootEnvironment:
	"""Boot Environment object that is used by beadm to manage command line 
	options, arguments and the log."""

	def __init__(self):
		self.trgtRpool = None
		self.trgtBeNameOrSnapshot = None
		self.srcBeNameOrSnapshot = None
		self.properties = {}
		self.logID = None
		self.log = None
	
class listBootEnvironment:
	"""Base class for beadm list
	Determine the BE's to display. Prints command output according to option:
	-d - dataset
	-s - snapshot
	-a - all (both dataset and snapshot)
	<none> - only BE information
	The -H option produces condensed, parseable output
	    The ';' delimits BE's, Datasets and Snapshots. 
	    The ':' delimits attributes for BE's, Datasets and Snapshots.
	    The ',' delimits multiple Datasets and Snapshots.
	    Multiple BE's are delimited with a carriage return.
	"""
	def list(self, beList, ddh, beName):
		""" print all output for beadm list command
		beList - list of all BEs
		ddh - if True, Do not Display Headers - just parseable data
		beName - user-specified BE, if any

		returns 0 for success
		side effect: beadm list output printed to stdout
		"""

		#find max column widths for headers
		bemaxout = [0 for i in range(len(self.hdr[0]))]
		for h in self.hdr:
			for lat in self.lattrs:
				icol = 0 #first column
				for at in self.lattrs.get(lat):
					s = h[icol]
					if len(s) + 1 > bemaxout[icol]:
						bemaxout[icol] = len(s) + 1
					icol += 1 #next column
		#collect BEs
		beout = {}	#matrix of output text [row][attribute]
		beoutname = {}	#list of BE names [row]
		beSpace = {}	#space used totals for BE [BE name]['space_used','ibe']
		ibe = 0		#BE index
		spacecol = -1	#to contain column where space used is displayed
		for be in beList:
			if be.has_key('orig_be_name'):
				curBE = be['orig_be_name']
				curBEobj = be
			#if BE name specified, collect matching BEs
			if beName != None and not self.beMatch(be, beName): continue
			attrs = ()
			#identify BE|dataset|snapshot attributes
			for att in ('orig_be_name', 'dataset', 'snap_name'):
				if be.has_key(att) and self.lattrs.has_key(att):
					attrs = self.lattrs[att]
					break
			if att == 'orig_be_name':
				beSpace[curBE] = {}
				beSpace[curBE]['space_used'] = 0
				beSpace[curBE]['ibe'] = ibe
				if not ddh and len(curBE) + 1 > bemaxout[0]:
					bemaxout[0] = len(curBE) + 1
			beout[ibe] = {}
			beoutname[ibe] = curBE
			icol = 0 #first column
			for at in attrs:
				#for option -s, withhold subordinate datasets
				if self.__class__.__name__ == 'SnapshotList' and \
				    att == 'snap_name' and be.has_key('snap_name') and \
				    be['snap_name'].find('/') != -1:
					break
				#convert output to readable format and save
				s = self.getAttr(at, be, ddh, curBEobj)
				beout[ibe][at] = s
				#maintain maximum column widths
				if not ddh and len(s) + 1 > bemaxout[icol]:
					bemaxout[icol] = len(s) + 1
				#sum all snapshots for BE
				if at == 'space_used' and be.has_key('space_used'):
					spacecol = icol
				icol += 1 #next column
			ibe += 1
			if be.has_key('space_used'):
				#sum all snapshots and datasets for BE in 'beadm list'
				if self.__class__.__name__ == 'BEList':
					beSpace[curBE]['space_used'] += be.get('space_used')
				elif beSpace.has_key(curBE) and \
				    (not beSpace[curBE].has_key('space_used') or beSpace[curBE]['space_used'] == 0):
					#list space used separately for other options
					beSpace[curBE]['space_used'] = be.get('space_used')
		#output format total lengths for each BE with any snapshots
		for curBE in beSpace:
			s = self.getSpaceValue(beSpace[curBE]['space_used'], ddh)
			ibe = beSpace[curBE]['ibe']
			beout[ibe]['space_used'] = s
			#expand column if widest column entry
			if spacecol != -1 and not ddh and len(s) + 1 > bemaxout[spacecol]:
				bemaxout[spacecol] = len(s) + 1
		#print headers in columns
		if not ddh:
			for h in self.hdr:
				outstr = ''
				for icol in range(len(h)):
					outstr += h[icol].ljust(bemaxout[icol])
				if outstr != '': print outstr
		#print collected output in columns
		outstr = ''
		prevBE = None
		curBE = None
		prevtype = None
		for ibe in beout: #index output matrix
			if beoutname[ibe] != None: curBE = beoutname[ibe]
			#find attributes for BE type
			curtype = None
			for att in ('orig_be_name', 'dataset', 'snap_name'):
				if beout[ibe].has_key(att):
					attrs = self.lattrs[att]
					curtype = att
					break
			if curtype == None: #default to BE
				curtype = 'orig_be_name'
				if self.lattrs.has_key('orig_be_name'):
					attrs = self.lattrs['orig_be_name']
				else: attrs = ()
			if ddh:
				outitem = '' #text for 1 BE or dataset or snapshot item
				if outstr != '':
					if prevBE != curBE: #BE changed
						#new BE - finish output for current BE
						if prevBE != None:
							#output parseable string
							outstr = outstr.rstrip(';,')
							if outstr != '':
								print self.prependBEifAbsent(prevBE, outstr) + outstr
							outstr = ''
						prevBE = curBE
					elif prevtype == curtype: #still within dataset/snapshot cluster
						outstr = outstr.rstrip(',')
						if outstr != '' and outstr[len(outstr) - 1] != ';':
							outstr += ',' #item separator
					else: #add type separator (supersedes item separator)
						outstr = outstr.rstrip(';,')
						outstr += ';'
				prevtype = curtype
			else:
				if prevBE != curBE and curBE != None:
					#for -d,-s, print BE alone on line
					if self.__class__.__name__ == 'SnapshotList' or \
					    self.__class__.__name__ == 'DatasetList':
						    print curBE
					prevBE = curBE
			#print for one BE/snapshot/dataset
			icol = 0 #first column
			for at in attrs: #for each attribute specified in table
				if ddh: #add separators for parsing
					if outitem != '': outitem += ':' #attribute separator
					if beout[ibe].has_key(at) and beout[ibe][at] != '-' and \
					    beout[ibe][at] != '':
						outitem += beout[ibe][at]
				else: #append text justified in column
					if beout[ibe].has_key(at):
						outstr += beout[ibe][at].ljust(bemaxout[icol])
				icol += 1 #next column
			if ddh: #append parseable output, printing if line is complete
				outstr += outitem
				if prevBE != curBE:
					#new BE - finish output for current BE
					if prevBE != None:
						if outstr != '':
							print self.prependBEifAbsent(prevBE, outstr) + outstr
						outstr = ''
					prevBE = curBE
			else:
				if outstr != '': print outstr
				outstr = ''
		#finish parseable output for final BE
		if ddh and outstr != '':
			#output final line
			outstr = outstr.rstrip(';,')
			if outstr != '':
				print self.prependBEifAbsent(prevBE, outstr) + outstr
		return 0

	#find match on user-specified BE
	def beMatch(self, be, beName):
		if be.has_key('orig_be_name'):
			return be.get('orig_be_name') == beName
		if be.has_key('dataset'):
			if be.get('dataset') == beName: return True
			a = be.get('dataset').split("/")
			return a[0] == beName
		if be.has_key('snap_name'):
			if be.get('snap_name') == beName: return True
			a = be.get('snap_name').split('@')
			if a[0] == beName: return True
			a = be.get('snap_name').split('/')
			return a[0] == beName
		return False

	#extract information by attribute and format for printing
	#returns '?' if normally present attribute not found - error
	def getAttr(self, at, be, ddh, beobj):
		if at == 'blank': return ' '
		if at == 'dash': return '-'
		if at == 'orig_be_name':
			if not be.has_key(at): return '-'
			return be[at]
		if at == 'snap_name':
			if not be.has_key(at): return '-'
			if self.__class__.__name__ == 'CompleteList':
				ret = self.prependRootDS(be[at], beobj)
			else: ret = be[at]
			if ddh: return ret
			return '   ' + ret #indent
		if at == 'dataset':
			if not be.has_key(at): return '-'
			if self.__class__.__name__ == 'DatasetList' or \
			    self.__class__.__name__ == 'CompleteList':
				ret = self.prependRootDS(be[at], beobj)
			else: ret = be[at]
			if ddh: return ret
			return '   ' + ret #indent
		if at == 'active':
			if not be.has_key(at): return '-'
			ret = ''
			if be.has_key('active') and be['active']: ret += 'N'
			if be.has_key('active_boot') and be['active_boot']: ret += 'R'
			if ret == '': return '-'
			return ret
		if at == 'mountpoint':
			if not be.has_key(at): return '-'
			if not be.has_key('mounted') or not be['mounted']: return '-'
			return be[at]
		if at == 'space_used':
			if not be.has_key(at): return '0'
			return self.getSpaceValue(be[at], ddh)
		if at == 'mounted':
			if not be.has_key(at): return '-'
			return be[at]
		if at == 'date':
			if not be.has_key(at): return '?'
			if ddh: return str(be[at]) #timestamp in seconds
			s = str(datetime.datetime.fromtimestamp(be[at]))
			return s[0:len(s)-3] #trim seconds
		if at == 'policy':
			if not be.has_key(at): return '?'
			return be[at]
		if at == 'root_ds':
			if not be.has_key(at): return '?'
			if ddh or self.__class__.__name__ == 'BEList': return be[at]
			return '   ' + be[at]
		#default case - no match on attribute
		return be[at]
		
	#readable formatting for disk space size
	def getSpaceValue(self, num, ddh):

		if ddh: return str(num) #return size in bytes as string

		K = 1024.0
		M = 1048576.0
		G = 1073741824.0
		T = 1099511627776.0

		if num == None: return '0'
		if num < K: return str(num) + 'B'
		if num < M: return str('%.1f' % (num / K)) + 'K'
		if num < G: return str('%.2f' % (num / M)) + 'M'
		if num < T: return str('%.2f' % (num / G)) + 'G'
		return str('%.2f' % (num / T)) + 'T'

	#prepend root dataset name with BE name stripped
	def prependRootDS(self, val, beobj):
		root_ds = beobj.get('root_ds')
		return root_ds[0:root_ds.rfind('/')+1] + val

	def prependBEifAbsent(self, BE, outstr):
		#if BE is not the first attribute in output,
		if BE != outstr[0:len(BE)] or outstr[len(BE)] != ':':
			#return BE as its own entry for prepending
			return BE + ';'
		return ''

"""Top level "beadm list" derived classes defined here.
	Only table definition is done here - all methods are in the base class.
	Tables driving list:
		hdr - list of text to output for each column
		lattrs - dictionary of attributes
			Each entry specifies either BE, dataset, snapshot with an attribute key:
				orig_be_name - for BEs
				dataset - for datasets
				snap_name - for snapshots
			Each list item in entry indicates specific datum for column
		Number of hdr columns must equal number of lattrs entries.
"""
class BEList(listBootEnvironment):
	"""specify header and attribute information for BE-only output"""
	def __init__(self):
		self.hdr =\
		    ('BE','Active','Mountpoint','Space','Policy','Created'),\
		    ('--','------','----------','-----','------','-------')
		self.lattrs = {'orig_be_name':('orig_be_name', 'active', 'mountpoint', 'space_used', 'policy', 'date')}

class DatasetList(listBootEnvironment):
	"""specify header and attribute information for dataset output, -d option"""
	def __init__(self):
		self.hdr =\
		    ('BE/Dataset','Active','Mountpoint','Space','Policy','Created'),\
		    ('----------','------','----------','-----','------','-------')
		self.lattrs ={\
		    'orig_be_name':('root_ds', 'active', 'mountpoint', 'space_used', 'policy', 'date'),
		    'dataset':('dataset', 'dash', 'mountpoint', 'space_used', 'policy', 'date')}

class SnapshotList(listBootEnvironment):
	"""specify header and attribute information for snapshot output, -s option"""
	def __init__(self):
		self.hdr =\
		    ('BE/Snapshot','Space','Policy','Created'),\
		    ('-----------','-----','------','-------')
		self.lattrs = {'snap_name':('snap_name', 'space_used', 'policy', 'date')}

class CompleteList(listBootEnvironment):
	"""specify header and attribute information for BE and/or dataset and/or snapshot output,
	    -a or -ds options """
	def __init__(self):
		self.hdr =\
		    ('BE/Dataset/Snapshot','Active','Mountpoint','Space','Policy','Created'),\
		    ('-------------------','------','----------','-----','------','-------')
		self.lattrs = {\
		    'orig_be_name':('orig_be_name', 'active', 'mountpoint', 'space_used', 'policy', 'date'),
		    'dataset':('dataset', 'dash', 'mountpoint', 'space_used', 'policy', 'date'),
		    'snap_name':('snap_name', 'dash', 'dash', 'space_used', 'policy', 'date')}
