#!/usr/bin/python2.6
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
# Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
#
'''
functions supporting creating and modifying menu.lst
'''
import fileinput
import logging
import os
import sys

from osol_install.auto_install.installadm_common import XDEBUG

MENULST = 'menu.lst'


def update_bootargs(menulstpath, oldbootargs, bootargs):
    '''Update bootargs in menu.lst
    
     Input:
        menulstpath - path to menu.lst file to update
        oldbootargs - bootargs to replace 
        bootargs - replacement bootargs

    '''
    logging.log(XDEBUG, 'in update_bootargs menu.lst=%s oldbootargs=%s '
                'bootargs=%s', menulstpath, oldbootargs, bootargs)

    bootargs = bootargs.strip()
    for line in fileinput.input(menulstpath, inplace=1):
        newline = line
        parts = line.partition(' -B')
        if parts[1]:
            ending = parts[2].lstrip()
            # Need to check for oldbootargs because '' is
            # a valid value
            if oldbootargs and oldbootargs in ending:
                ending = ending.replace(oldbootargs, bootargs)
            else:
                ending = bootargs + ending
            newline = parts[0] + ' -B ' + ending
        sys.stdout.write(newline)


def update_svcname(menulstpath, newsvcname, mountdir):
    ''' Update the svcname/mountdir in menu.lst

     Input:
        menulstpath - path to menu.lst file to update
        newsvcname - replacement svcname
        mountdir - mountdir to replace with new svcname

    '''
    logging.log(XDEBUG, 'in update_menulst %s %s %s',
                menulstpath, newsvcname, mountdir)
    install_svc = 'install_service='
    kernel_str = '\tkernel$ /' 
    module_str = '\tmodule$ /'
    for line in fileinput.input(menulstpath, inplace=1):
        newline = line
        parts = newline.partition(kernel_str)
        if parts[1]:
            ending = parts[2].partition('/')[2]
            newline = kernel_str + mountdir + '/' + ending
            parts = newline.partition(install_svc)
            if parts[1]:
                ending = parts[2].partition(',')[2]
                newline = parts[0] + install_svc + newsvcname + ',' + \
                          ending
        else:
            parts = newline.partition(module_str)
            if parts[1]:
                ending = parts[2].partition('/')[2]
                newline = module_str + mountdir + '/' + ending
        sys.stdout.write(newline)


def setup_grub(svc_name, image_path, image_info, srv_address, menu_path,
               bootargs):
    '''Configure GRUB for this AIService instance.
    
    Input:
        svc_name - service name
        image_path - image path for service
        image_info - dict of image info
        srv_address - address from service.py
        menu_path - where to put menu.lst file
        bootargs - string of user specified bootargs or '' if none
    
    '''
    # Move the install media's grub menu out of the way so we do not boot it.
    media_grub = os.path.join(image_path, "boot/grub", MENULST)
    if os.path.exists(media_grub):
        os.remove(media_grub)
    
    # Create a new menu.lst for the AI client to use during boot
    with open(os.path.join(menu_path, MENULST), "w") as menu:
        # First setup the the global environment variables 
        menu.write("default=0\n")
        menu.write("timeout=30\n")

        if "grub_min_mem64" in image_info:
            menu.write("min_mem64=%s\n\n" % image_info["grub_min_mem64"])

        # Add the 'no install' entry. It may not have a title in
        # the image_info, so set a default.
        menu.write("title %s\n" %
                   image_info.get("no_install_grub_title",
                                  "Text Installer and command line"))
        menu.write("\tkernel$ /%s/platform/i86pc/kernel/$ISADIR/unix -B "
                   "%sinstall_media=http://%s/%s,install_service=%s,"
                   "install_svc_address=%s\n" %
                   (svc_name, bootargs, srv_address, image_path, svc_name,
                    srv_address))
        menu.write("\tmodule$ /%s/platform/i86pc/$ISADIR/boot_archive\n\n" %
                   svc_name)
        
        # Finally, add the 'install' entry
        menu.write("title %s\n" % image_info.get("grub_title",
                                              "Solaris " + svc_name))
        menu.write("\tkernel$ /%s/platform/i86pc/kernel/$ISADIR/unix -B "
                   "%sinstall=true,install_media=http://%s/%s,"
                   "install_service=%s,install_svc_address=%s,"
                   "livemode=text\n" %
                   (svc_name, bootargs, srv_address, image_path, svc_name,
                    srv_address))
        menu.write("\tmodule$ /%s/platform/i86pc/$ISADIR/boot_archive\n" %
                   svc_name)
