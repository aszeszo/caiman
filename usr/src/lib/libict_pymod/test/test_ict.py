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
# Copyright (c) 2010, Oracle and/or its affiliates. All rights reserved.
#
'''Tests for ICTs'''

import os
import unittest

import osol_install.ict as ict_mod
ICT = ict_mod.ICT

SAMPLE_TITLE_LINE = "Solaris Next Development snv_144 X86"
SAMPLE_MENU_LST = '''default 0
#----------- ADDED BY BOOTADM - DO NOT EDIT -----------
title %s
findroot (pool_rpool,0,a)
kernel$ /platform/i86pc/kernel/$ISADIR/unix -B $ZFS-BOOTFS
module$ /platform/i86pc/$ISADIR/boot_archive
#----------------------END BOOTADM---------------------
'''


class TestICTBase(unittest.TestCase):
    '''Define default setUp/tearDown methods'''
    
    def new_special_grub_entry(self):
        '''Replacement method for ICT.get_special_grub_menu (see setUp)'''
        return self.special_grub_entry
    
    def setUp(self):
        debuglvl = 4 # Max output
        
        # Raises a warning, but can be ignored
        self.loc_grubmenu = os.tempnam("/tmp", "menu")
        self.new_grub = self.loc_grubmenu + ".new"
        
        self.ict = ICT("/", debuglvl, loc_grubmenu=self.loc_grubmenu)
        
        self.ict.grubmenu = self.loc_grubmenu
        
        self.special_grub_entry = None
        
        # Override the get_special_grub_entry definition
        self.orig_special_grub_entry = ICT.get_special_grub_entry
        ICT.get_special_grub_entry = self.new_special_grub_entry
    
    def tearDown(self):
        try:
            os.remove(self.loc_grubmenu)
        except StandardError:
            pass
        
        try:
            os.remove(self.new_grub)
        except StandardError:
            pass
        
        # Restore the get_special_grub_entry function
        ICT.get_special_grub_entry = self.orig_special_grub_entry


class TestICTFixGrubEntry(TestICTBase):
    '''Tests for ICT.fix_grub_entry()'''
    
    def setUp(self):
        super(TestICTFixGrubEntry, self).setUp()
        
        with open(self.loc_grubmenu, "a") as grub:
            grub.write(SAMPLE_MENU_LST % SAMPLE_TITLE_LINE)
    
    def test_no_special_entry(self):
        '''Ensure nothing changes if no special grub entry'''
        self.special_grub_entry = None
        
        result = self.ict.fix_grub_entry()
        self.assertEqual(0, result)
        
        with open(self.loc_grubmenu) as new_grub:
            new_grub_str = new_grub.read()
        
        self.assertEqual(SAMPLE_MENU_LST % SAMPLE_TITLE_LINE, new_grub_str)
    
    def test_swap_special_grub_entry(self):
        '''Ensure properly changed if special grub entry given'''
        self.special_grub_entry = "SPECIAL GRUB ENTRY"
        result = self.ict.fix_grub_entry()
        self.assertEqual(0, result)
        
        with open(self.loc_grubmenu) as new_grub:
            new_grub_str = new_grub.read()
        
        self.assertEqual(SAMPLE_MENU_LST % self.special_grub_entry,
                         new_grub_str)
    
    def test_no_fix_grub_on_sparc(self):
        '''Assert that fix_grub_entry can't run on sparc'''
        self.ict.is_sparc = True
        
        result = self.ict.fix_grub_entry()
        self.assertEqual(result, ict_mod.ICT_INVALID_PLATFORM)
    
    def test_bad_file(self):
        '''Verify that exits with failure when source menu.lst can't be read'''
        noexist = os.tempnam()
        self.special_grub_entry = "SPECIAL GRUB ENTRY"
        self.ict.grubmenu = noexist
        result = self.ict.fix_grub_entry()
        self.assertEqual(result, ict_mod.ICT_FIX_GRUB_ENTRY_FAILED)
