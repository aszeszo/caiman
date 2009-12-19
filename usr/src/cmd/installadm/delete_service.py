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
# Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
'''

A/I Delete-Service

'''

import sys
import gettext
import os
import shutil
import signal
import stat
import traceback
import os.path
from optparse import OptionParser

import osol_install.auto_install.installadm_common as com
import osol_install.libaiscf as smf

class Client_Data(object):
    '''
    A class to hold client data and interoperate with an AIservice class.
    '''

    def __init__(self, mac):
        # service name will be the client's identifier
        # add a 01 to MAC to make a DHCP style client ID
        self.serviceName = "01" + str(mac).upper()

        # values can store anything similar to AIservice() object as necessary
        self.values = {}

    def __getitem__(self, key):
        return self.values[key]

def parse_options():
    '''
    Parse and validate options when called as delete-service
    Args: None
    Returns: A tuple of an AIservice object representing service to delete
             and an options object
    '''

    parser = OptionParser(usage=_("usage: %prog [options] install_service"))
    parser.add_option("-x", "--delete-image", dest="deleteImage",
                      action="store_true",
                      default=False,
                      help=_("remove service image, if " +
                      "not otherwise in use"))
    (options, args) = parser.parse_args()

    # check that we got the install service's name passed in
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    serviceName = args[0]

    # check the system has the AI install SMF service available
    try:
        smf_instance = smf.AISCF(FMRI="system/install/server")
    except KeyError:
        raise SystemExit(_("Error:\tThe system does not have the " +
                         "system/install/server SMF service"))

    # check the service exists
    if not serviceName in smf_instance.services.keys():
        raise SystemExit(_("Error:\tThe specified service does not exist: %s") %
                         serviceName)

    # return the AIservice object
    return ((smf.AIservice(smf_instance, serviceName)), options)

def stop_service(service):
    '''
    Sets service state flag to off and restarts the AutoInstaller SMF
    service, killing all processes.
    Args: AIservice object
    Returns: None
    '''

    try:
        service['status'] = "off"
    except KeyError:
        sys.stderr.write(_("SMF data for service %s is corrupt, trying to " +
                         " continue.\n") % service.serviceName)

def remove_DHCP_macro(service):
    '''
    Checks for existence of DHCP macro
    Checks for and prints warning for clients using DHCP macro
    Prints command to remove DHCP macro
    Args:   AIservice object
    Returns: None
    '''

    # if we are handed a Client_Data object instance macro name is just a MAC
    # address otherwise prepend "dhcp_macro_"
    if isinstance(service, Client_Data):
        macro_name = service.serviceName
    else:
        # if we have a boot_file use it instead of serviceName for paths
        try:
            macro_name = "dhcp_macro_" + service['boot_file']
        except KeyError:
            macro_name = "dhcp_macro_" + service.serviceName

    # command to remove DHCP macro
    cmd = ["/usr/sbin/dhtadm", "-D", "-m", macro_name]

    # ensure we are a DHCP server
    if not (smf.AISCF(FMRI="network/dhcp-server").state == "online"):
        print (_("Detected that DHCP is not set up on this machine. To " +
               "delete the DHCP macro, run the following on your " +
               "DHCP server:\n%s\n") %
               " ".join(cmd))
        return

    # if the macro is not configured return
    try:
        if(macro_name not in com.DHCPData.macros()['Name']):
            return
    except com.DHCPData.DHCPError, e:
        sys.stderr.write(str(e) + "\n")
        return

    # if configured with macro see if any clients would be orphaned
    try:
        nets = com.DHCPData.networks()
    except com.DHCPData.DHCPError, e:
        sys.stderr.write(str(e) + "\n")
        return

    # store a list of clients using this macro
    systems = []
    for net in nets:
        # check if any machines use the macro we are removing
        try:
            # get a dictionary of the form:
            # Client ID', 'Flags', 'Client IP', 'Server IP',
            # 'Lease Expiration', 'Macro', 'Comment'
            clients = com.DHCPData.clients(net)
        except com.DHCPData.DHCPError, e:
            sys.stderr.write(str(e) + "\n")
            continue
        if(macro_name in clients['Macro']):
            # store IP addresses for later print out (assumes clients['Client
            # IP'] and clients['Macro'] to be equal length, which they should
            # be)
            systems.append([(clients['Client IP'][idx]) for idx in
                             range(0,len(clients['Client IP'])) if
                             macro_name in clients['Macro'][idx]])

    if (len(systems) > 1):
        sys.stderr.write (_("Warning:\tThe following IP addresses are "
                          "configured to use the macro %s:\n%s") %
                          (macro_name, "\n".join(systems)))
        return

    # tell user to remove DHCP macro
    print (_("To delete DHCP macro, run the following command:\n%s\n") %
           " ".join(cmd))
    return

def remove_files(service, removeImageBool):
    '''
    Removes /var/ai/<port number>

    If requested for removal and not in use:
        Removes image
        Unmounts directory pointed to by /tftpboot/<service name> and
            removes /etc/vfstab entry for mount point
        Removes directory for mount point pointed to by /tftpboot/<service name>

    Calls /tftpboot/rm.<service name>
        Removes /tftpboot/<service name>
        Removes /tftpboot/menu.lst.<service name>
    Removes /tftpboot/rm.<service name>

    Removes /etc/netboot/serviceName (if exists)
    Removes /etc/netboot/wanboot.conf symlink (if dangling)

    Args:   AIservice object, image directory removal boolean
    Returns: None
    Raises: SystemError if any subcommand reports an error
    '''

    def removeFile(filename):
        '''
        Determines file type and removes file as appropriate (handles regular
        files (which symlinks fall under) and directories)
        '''
        def handleError(function, path, excinfo):
            '''
            Handle errors from shutil.rmtree. Function is one of:
            os.path.islink(), os.listdir(), os.remove() or os.rmdir()
            Path is the path being removed. Excinfo is the exception info.
            '''
            exc_info_err_val = excinfo[1]
            sys.stderr.write (_("Function %s, erred on file:\n%s\n" +
                              "With error: %s\n") %
                              (function, path, exc_info_err_val))
        # ensure file exists
        if not os.path.lexists(filename):
            sys.stderr.write (_("Unable to find path %s\n") % filename)
        elif(os.path.isdir(filename)):
            # run rmtree on filename (really a directory) and do not stop on
            # errors (False), while passing errors to handleError for user
            # output
            shutil.rmtree(filename, False, handleError)
        elif(os.path.isfile(filename) or os.path.islink(filename)):
            try:
                os.remove(filename)
            except OSError, e:
                sys.stderr.write (_("Unable to remove path %s:\n%s\n") %
                                  (filename, e))
        else:
            sys.stderr.write (_("Unknown file type, path %s\n") %
                              (filename))
        return

    def check_wanboot_conf(service):
        '''
        Checks to see if /etc/netboot/wanboot.conf is a dangling symlink and if
        so returns its path. Further, if removing the last entry under /etc/netboot,
        also return /etc/netboot. All of these paths are compiled into a list.
        Otherwise, returns None
        '''
        netboot = '/etc/netboot/'
        wanbootConf = 'wanboot.conf'
        # see if wanboot.conf is dangling but the symlink still exists
        if not os.path.exists(os.path.join(netboot, wanbootConf)) and \
            os.path.lexists(os.path.join(netboot, wanbootConf)):
            files = [os.path.join(netboot, wanbootConf)]
            # add to deletion list empty directories
            # (i.e. /etc/netboot/172.20.24.0) under /etc/netboot
            # (and /etc/netboot itself, if emptied)

            # iterate over all directories in netboot
            for directory in filter(os.path.isdir,
                                    # specify a full path for the entry
                                    [os.path.join(netboot, entry) for entry in
                                    # get a list of all entries in netboot
                                    os.listdir(netboot)]):

                # if directory is empty add it to the files to remove list
                if len(os.listdir(directory)) == 0:
                    files.append(directory)

            # if everything in /etc/netboot is slated to be removed just use
            # the path for netboot
            if len(os.listdir(netboot)) == len(files):
                return netboot
            else:
                return files
        # return none if /etc/netboot/wanboot.conf is still valid
        return

    def find_service_directory(service):
        '''
        Returns path to AI service directory parsing service txt_record SMF
        property, returns None if a failure occurs or we are not handed an
        AIservice instance
        '''
        # no need to find a service directory for a delete_client run,
        # return since this is not applicable
        if isinstance(service, Client_Data):
            return

        # first ensure the txt_record property exists
        try:
            txt_record = service['txt_record']
        except KeyError:
            sys.stderr.write (_("Text record for service %s is missing.\n") %
                              service.serviceName)
            return
        # ensure splitting the txt_record returns two parts
        if (len(txt_record.split(":")) != 2):
            sys.stderr.write (_("Text record for service %s is " +
                              "missing port: %s\n") %
                              (service.serviceName, txt_record))
            return
        # return the service directory
        return ("/var/ai/" + txt_record.split(":")[-1])

    def find_image_path(service):
        '''
        Handles finding image, ensuring image is not in use other than current
        service being removed and returns image path, as well as, the longest
        empty path to the image-server image.
        Will return, if not handed an AIservice instance.
        '''
        # check if we are tasked with removing the image
        if not removeImageBool:
            return

        # first, ensure the image_path property exists
        try:
            image_path = service['image_path']
        except KeyError:
            sys.stderr.write (_("Image-path record for service %s is " +
                              "missing.\n") % service.serviceName)
            return

        # next, ensure no other service uses the same image
        # avoid doing this in list comprehension so we can continue through
        # KeyErrors
        # dependent_services will be a list of all the services using this image
        dependent_services = []

        # iterate over a list of AIservice objects. Get the SMF instance object
        # of the service which will then provide a dictionary of services via
        # the services property (we just need the service names which are the
        # values of the dictionary)
        for serv in (service.instance.services.values()):
            try:
                if serv['image_path'] == image_path:
                    dependent_services.append(serv.serviceName)
            # if the service doesn't have a valid image-path (or the service
            # has been removed since we got the handle) ignore that service
            except KeyError:
                pass

        # lastly, if the image is found to be used more than once,
        # warn and return
        if (len(dependent_services) > 1):
            sys.stderr.write (_("Not removing image path; %s is used by " +
                              "services:\n") % image_path)
            # print service names
            for svc in dependent_services:
                # filter out service we are deleting
                if svc != service.serviceName:
                    sys.stderr.write (svc + "\n")
            return

        # lastly, all is good, return the image and image-server path
        else:
            # find the longest empty path leading up to webserver image path
            files = [image_path,
                     # must strip the leading path separator from image_path as
                     # os.join won't concatenate two absolute paths
                     os.path.join('/var/ai/image-server/images/',
                                  image_path.lstrip(os.sep))]
            # the webserver image path will remain at index 1 in the files list
            webServerImagePathIdx = 1
            # if webserver image path is non-existent return now
            # yes return the non-existent webserver path to raise the issue to
            # the user
            if not os.path.lexists(files[webServerImagePathIdx]):
                return files
            # get the parent dir of the webserver path
            directory = os.path.dirname(files[webServerImagePathIdx])

            # iterate up the directory structure (toward / from the
            # image server's image path) adding empty directories
            while len(os.listdir(directory)) == 1:
                # stop at /var/ai/image-server/images,
                # if we have gotten that far in the traversal
                if directory == "/var/ai/image-server/images":
                    break
                files.append(directory)
                directory = os.path.dirname(directory)
            return files

    def removeBootArchiveFromVFSTab(boot_archive):
        '''
        Remove boot_archive file system from vfstab
        '''
        try:
            vfstabObj = com.VFSTab(mode="r+")
        except IOError, e:
            sys.stderr.write(str(e) + "\n")
            return
        # look for filesystem in /etc/vfstab
        try:
            # calculate index for mount point
            idx = vfstabObj.fields.MOUNT_POINT.index(boot_archive)
            try:
                # remove line containing boot archive (updates /etc/vfstab)
                del(vfstabObj.fields.MOUNT_POINT[idx])
            except IOError, e:
                sys.stderr.write(str(e) + "\n")
        # boot archive was not found in /etc/vfstab
        except (ValueError, IndexError):
            sys.stderr.write (_("Boot archive (%s) for service %s " +
                              "not in vfstab.\n") %
                              (boot_archive, service.serviceName))
        return

    def removeTFTPBootFiles(service):
        '''
        Handle file removal in /tftpboot by building a list of files to remove:
        First, adds pxegrub.<directory pointed to by /tftpboot/<service
         name> i.e. pxegrub.I86PC.OpenSolaris-1
        Unmounts directory which is boot archive (will be something like
         I86PC.OpenSolaris-4) and removes /etc/vfstab entry for mount point

        Calls /tftpboot/rm.<service name> which should remove:
            /tftpboot/<service name>
            /tftpboot/menu.lst.<service name>
            (if the above aren't removed by the rm.<service name> script they
             are added to the remove list)
        Adds /tftpboot/rm.<service name>
        
        Returns: If unable to find tftp root - None
                 Success - A list of file paths to remove
        '''
        # store files to pass back for removal
        files = []

        # check that we have a valid tftpboot directory and set baseDir to it
        baseDir = com.findTFTProot()
        if not baseDir:
            sys.stderr.write (_("Unable to remove the grub executable, boot " +
                              "archive, or menu.lst file\nwithout a valid " +
                              "tftp root directory.\n"))
            return

        # if we have a boot_file use it instead of serviceName for paths
        try:
            service_name = service['boot_file']
        except KeyError:
            service_name = service.serviceName

        # see if the directory pointed to by /tftpboot/<service name> exists
        curPath = os.path.join(baseDir, service_name)
        if (not os.path.exists(curPath)):
            sys.stderr.write (_("The grub executable %s " +
                              "for service %s is missing.\n") %
                              (curPath, service.serviceName))
        else:
            # find the target of the sym link for /tftpboot/<service name>
            pxe_grub = os.readlink(curPath)
            # see if the target still exists
            if(os.path.exists(os.path.join(baseDir, pxe_grub))):
                # get a list of all symlinks in /tftpboot, and then resolve
                # their target path

                # get all files in baseDir
                baseDirFiles = [os.path.join(baseDir, f) for f in
                    os.listdir(baseDir)]
                # get all links in baseDir
                links = filter(os.path.islink, baseDirFiles)
                # get all paths in baseDir
                paths = [os.readlink(l) for l in links]
                # there's only one symlink pointing to our boot archive,
                # it is fine to remove it
                if (paths.count(pxe_grub) == 1):
                    pxe_grub = os.path.join(baseDir, pxe_grub)
                    files.append(pxe_grub)

        # Use GRUB menu to check for boot_archive, see that it exists
        grub_menu_prefix = "menu.lst."
        grub_menu = grub_menu_prefix + service_name
        if not os.path.exists(os.path.join(
                              baseDir, grub_menu)):
            sys.stderr.write (_("Unable to find GRUB menu at %s, and thus " +
                              "unable to find boot archive.\n") % grub_menu)
        else:
            # check the menu.lst file for the boot archive(s) in use
            menuLst = com.GrubMenu(file_name=os.path.join(baseDir, grub_menu))

            # iterate over both module and module$ of the service's grub menus
            # looking for boot_archive
            for boot_archive in [menuLst[entry].get('module') or
                                 menuLst[entry].get('module$') for
                                 entry in menuLst.entries]:

                # iterate over all grub menus to see if this boot_archive
                # is in use by another service
                inUse = []
                # build a list of grub menus from baseDir
                menus = [filename for filename in os.listdir(baseDir) if
                    # only select files which start with grub menu prefix
                    filename.startswith(grub_menu_prefix) and
                    # do not select the menu file the service uses
                    filename != os.path.basename(menuLst.file_obj.file_name)]
                # iterate over all menus except the current service's
                for menuName in menus:
                    otherMenu = com.GrubMenu(file_name=
                                             os.path.join(baseDir, menuName))

                    # iterate over all entries looking for boot_archive
                    if boot_archive in [otherMenu[entry].get('module') or
                                        otherMenu[entry].get("module$") for
                                        entry in otherMenu.entries]:
                    # boot_archive was in use add service/client name
                        inUse.append(menuName.lstrip(grub_menu_prefix))

                # if this boot_archive is in use, skip it (but explain why)
                if inUse:
                    sys.stderr.write (_("Not removing boot archive %s. " +
                                      "Boot archive is in-use by " +
                                      "service/clients:\n") % boot_archive)
                    for obj in inUse:
                        print obj
                    continue

                # boot_archive will be relative to /tftpboot so will appear to
                # be an absolute path (i.e. will have a leading slash) and will
                # point to the RAM disk
                boot_archive = baseDir + "/" + \
                               boot_archive.split(os.path.sep, 2)[1]


                # see if it is a mount point
                # os.path.ismount() doesn't work for a lofs FS so use
                # /etc/mnttab instead
                if boot_archive in com.MNTTab().fields.MOUNT_POINT:
                    # unmount filesystem
                    try:
                        com.run_cmd({"cmd": ["/usr/sbin/umount", boot_archive]})
                    # if run_cmd errors out we should continue
                    except SystemError, e:
                        sys.stderr.write(str(e) + "\n")

                # boot archive directory not a mountpoint
                else:
                    sys.stderr.write (_("Boot archive %s for service is " +
                                      "not a mountpoint.\n") %
                                      os.path.join(baseDir,
                                      boot_archive))
                removeBootArchiveFromVFSTab(boot_archive)
                files.append(boot_archive)

        # call /tftpboot/rm.<service name> which should remove:
        # /tftpboot/menu.lst.<service name>
        # /tftpboot/<service name>
        rmCMD = os.path.join(baseDir, "rm." + service_name)
        # ensure /tftpboot/rm.<service name> exists
        if os.path.exists(rmCMD):
            try:
                # make the rm script rwxr--r--
                os.chmod(rmCMD,
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IRWXU |
                         stat.S_IRGRP | stat.S_IROTH)
                com.run_cmd({"cmd": [rmCMD]})

            # if run_cmd errors out we should continue
            except (IOError, SystemError, OSError), e:
                sys.stderr.write(str(e) + "\n")

        # check that files which should have been removed, were and if not
        # append them for removal from this script:

        # check remove script (/tftpboot/rm.<service name>) removed itself
        if os.path.exists(rmCMD):
            files.append(rmCMD)

        # check GRUB menu (/tftpboot/menu.lst.<service name>)
        if os.path.exists(os.path.join(baseDir, grub_menu)):
            files.append(os.path.join(baseDir, grub_menu))

        # check GRUB executable (/tftpboot/<service name>)
        if os.path.exists(os.path.join(baseDir, service_name)):
            files.append(os.path.join(baseDir, service_name))

        return files

    #
    # Begin actual remove_files() code below
    #

    # All files to remove are specified by a path or a callable function
    # (which returns None or a list of file paths). (The filesToRemove list is
    # a fantastic tool for debugging to watch the order in which files are added
    # and which function is adding which files)
    filesToRemove = [
                     find_service_directory, # /var/ai/<port>
                     find_image_path         # image path
                    ]
    # try to determine if we are a SPARC or X86 image.
    # first see if the image_path property exists.
    arch = None
    try:
        image_path = service['image_path']
        # see if we have an X86 service
        if os.path.exists(os.path.join(image_path, "platform", "i86pc")):
            arch = "X86"
        # see if we have a SPARC service
        elif(os.path.exists(os.path.join(image_path, "platform", "sun4u")) or
             os.path.exists(os.path.join(image_path, "platform", "sun4v"))):
            arch = "SPARC"
            # /etc/netboot/<service name>
            filesToRemove.append("/etc/netboot/" + service.serviceName)
    except KeyError:
        # os.walk returns files in the 3rd index of its tuple return
        osWalkDirIdx = 1
        # if we have an /etc/netboot entry then we should be SPARC
        if os.path.exists("/etc/netboot/" + service.serviceName):
            arch = "SPARC"
            # /etc/netboot/<service name>
            filesToRemove.append("/etc/netboot/" + service.serviceName)
        # if the client's ID is a file under /etc/netboot add it
        elif True in [service.serviceName in file_[osWalkDirIdx] for file_ in
                      os.walk("/etc/netboot")]:
            arch = "SPARC"
            # add to the deletion list each entry under /etc/netboot which
            # appears with this client ID
            for (path, dirs, files) in os.walk("/etc/netboot"):
                if service.serviceName in dirs:
                    # this may match more than once if there are multiple
                    # entries for the machine add them all
                    filesToRemove.append(os.path.join(path,
                                         service.serviceName))
        else:
            # No SMF properties found, nor files to identify this arch as
            # SPARC; so, try looking for X86 files.
            # If /tftpboot/<service_name> exists, we know it's X86 architecture.
            tftpDir = com.findTFTProot()
            if tftpDir:
                if os.path.exists(os.path.join(tftpDir, service.serviceName)):
                    arch = "X86"

    if arch == "SPARC":
        # see if /etc/netboot/wanboot.conf is left dangling and if so clean
        # it up too
        filesToRemove.append(check_wanboot_conf)
    elif arch == "X86":
        # /etc/tftpboot files
        filesToRemove.append(removeTFTPBootFiles)
    # if arch was never set we can not figure out what to delete
    # error and return now
    else:
        sys.stderr.write (_("Unable to find service or client %s.\n") %
                          (service.serviceName))
        return

    # iterate over all paths to remove (detect their type dynamically)
    for obj in filesToRemove:
        # see if we have a None
        if not obj:
            continue
        # see if we have a function
        # (which will return a list of files to remove)
        elif callable(obj):
            result = obj(service)
            # check if we get a string back
            if isinstance(result, str):
                removeFile(result)
            # check if we get a string back
            elif isinstance(result, list):
                for item in result:
                    removeFile(item)
            # check if we get a None back
            elif not result:
                pass
            # error, as what is this?
            else:
                raise TypeError(_("Error:\tUnexpected data: %s\n") % result)
        # this should be a single file, hand it to removeFile for removal
        else:
            removeFile(obj)

def kill_processes(service):
    '''
    Kill dns-sd, AI webserver and Apache image-server processes.
    Returns None and prints errors catching exceptions raised
    '''

    procsToKill = [{"proc": "dns-sd", "searchStr":
        # match a dns-sd with the serviceName and "_" from service type
        # (which is "_OSInstall")
        # Note: this means the maximum serviceName we can match on is 59
        # characters long
        "/usr/bin/dns-sd -R " + service.serviceName + " _"}]

    try:
        procsToKill.append({
                           "proc": "ai-webserver",
                           "searchStr": "/usr/bin/python2.6 "+
                                        "/usr/lib/installadm/webserver -p " +
                                        # port number (as txt_record is
                                        # serverName:port (we want the second
                                        # item from the split which is the port
                                        # number)
                                        service['txt_record'].split(':')[1]})
    # if txt_record key not found error and continue
    except KeyError:
        sys.stderr.write(_("Unable to kill ai-webserver process.\n"))

    ps = {}
    try:
        ps = com.run_cmd({"cmd": ["/usr/bin/ps", "-efo", "pid args"]})
    # if run_cmd errors out we should return
    except SystemError, e:
        sys.stderr.write(str(e) + "\n")
        return

    # split into a list of ["pid command"] elements
    ps['out'] = ps['out'].split('\n')
    # kill for each service listed in procsToKill
    # (a dict with keys "proc" and "searchStr")
    for killInfo in procsToKill:
        # filter only processes matched by searchStr
        pids = [pid for (pid, proc) in
            # split into pid and cmd objs. and strip header
            # and trailing newline
            [line.strip().split(None, 1) for line in ps['out']][1:-1] if
             # match on the searchStr
             proc.startswith(killInfo['searchStr'])]

        # see if we got any PIDs
        if len(pids) == 0:
            sys.stderr.write (_("Unable to find %s process.\n") %
                              killInfo['proc'])
            continue

        # iterate over processes, killing them
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            # a failure of int() will result in a ValueError
            except ValueError:
                sys.stderr.write(_("Unable to kill %s process.\n") %
                                 killInfo['proc'])
            except OSError, e:
                sys.stderr.write(_("Unable to kill %s process: %s\n") %
                                 (killInfo['proc']), e)

def remove_service(service):
    '''
    Removes service from the AutoInstaller SMF service
    Args: AIservice object
    Returns:
    '''

    # if we are the instance's last service, transition the SMF instance to
    # maintenance
    if len(service.instance.services) <= 1:
        service.instance.state = "MAINTENANCE"

    # remove the service
    try:
        service.instance.del_service(service.serviceName)
    # if the service can not be found a KeyError will be raised
    except KeyError:
        pass

if __name__ == "__main__":
    # store application name for error string use
    prog = os.path.basename(sys.argv[0])

    # wrap whole command's execution to catch exceptions as we should not throw
    # them anywhere
    try:
        # initialize gettext
        gettext.install("ai", "/usr/lib/locale")

        # check that we are root
        if os.geteuid() != 0:
            raise SystemExit(_("Error:\tRoot privileges are required to run "
                             # argv is our application name
                             "the %s %s command.\n") %
                             ("installadm", prog))

        # parse server options
        (service, options) = parse_options()

        # stop the service first (avoid pulling files out from under programs)
        stop_service(service)

        # kill processes
        kill_processes(service)

        # everything should be down, remove files
        remove_files(service, options.deleteImage)

        # check if this machine is a DHCP server
        remove_DHCP_macro(service)

        # remove the service last
        remove_service(service)

    # catch SystemExit exceptions and pass them as raised
    except SystemExit, e:
        # append the program name, colon and newline to any errors raised
        raise SystemExit("%s:\n\t%s" % (prog, str(e)))
    # catch all other exceptions to print a disclaimer clean-up failed and may
    # be incomplete, they should run again to see if it will work
    except:
        # write an abbreviated traceback for the user to report
        traceback.print_exception(sys.exc_info()[0], sys.exc_info()[1],
                                  sys.exc_info()[2], file=sys.stdout)
        sys.stderr.write(_("%s:\n"
                           "\tPlease report this as a bug at "
                           "http://defect.opensolaris.org:\n"
                           "\tUnhandled error encountered:\n") % prog)
