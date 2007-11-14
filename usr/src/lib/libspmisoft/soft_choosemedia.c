/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#ifndef lint
#pragma ident	"@(#)soft_choosemedia.c	1.3	07/11/09 SMI"
#endif

/*
 *	File:		soft_choosemedia.c
 *
 *	Description:	This file contains the routines needed to handle
 *			cds and components
 */

#include <stdio.h>
#include <ctype.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/systeminfo.h>

#include "spmisoft_lib.h"
#include "soft_choosemedia.h"


/*
 * local functions
 */
int isCorrectPlatform();

static int autoeject = 1;


/*
 * Public functions
 */

/*
 * Name:    (swi_)setAutoEject
 * Description: Set value of autoeject flag (if disc should
 *		be automatically ejected)
 * Scope:       public
 * Parameters:  auto_ok - 1 if autoEject desired
 *			  0 if autoEject not desired
 * Return:      none
 */
void
swi_setAutoEject(int auto_ok)
{
	autoeject = auto_ok;
}

/*
 * Name:	(swi_)isAutoEject
 * Description:	Return value of autoeject flag
 * Scope:	public
 * Parameters:	none
 * Return:	1 if autoEject set
 *		0 if autoEject not set
 */
int
swi_isAutoEject()
{
	return (autoeject);
}


/*
 * Name:	(swi_)eject_disc
 * Description:	Eject the disc specified by rawdevice
 * Scope:	public
 * Arguments:	rawdevice -  ptr to string of device (/dev/rdsk/ctds)
 *
 * Returns:	none
 */
void
swi_eject_disc(char *rawdevice) {
	char cmd[MAXPATHLEN];

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("eject_disc");
#endif

	if (! autoeject) {
		return;
	}
	(void) snprintf(cmd, sizeof (cmd),
			"/usr/bin/eject %s 2>/dev/null > /dev/null",
			rawdevice);
	system(cmd);

}

/*
 * Name:	(swi_)umount_dir
 * Description:	Unmounts mountpt. If umount fails, does umount -f.
 * Scope:	public
 * Arguments:	mountpt	-  ptr to mounpt to umount
 * Returns:	0
 */
int
swi_umount_dir(char *mountpt) {
	char cmd[MAXPATHLEN];
	int status;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("umount_dir");
#endif
	(void) snprintf(cmd, sizeof (cmd),
			"/sbin/umount %s 2>/dev/null > /dev/null",
			mountpt);
	status = system(cmd);
	if (status != 0) {
		(void) snprintf(cmd, sizeof (cmd),
			"/sbin/umount -f %s 2>/dev/null > /dev/null",
			mountpt);
		(void) system(cmd);

	}
	return (0);

}

/*
 * Name:	(swi_)mount_path
 * Description:	Perform nfs mount of hostpath on mountpt
 * Scope:	public
 * Arguments:	hostpath - [RO] (char *)
 *				ptr to host:/absolutepath
 *		mountpt	- [RO] (char *)
 *			  directory on which to mount
 *
 * Returns:	int	- 1, mount successful
 *			- 0, mount not successful
 */
int
swi_mount_path(char *hostpath, char *mountpt) {
	char cmd[MAXPATHLEN];
	int rc;
	struct stat sb;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("mount_path");
#endif

	/*
	 * if mountpt exists, umount mtpt. Otherwise, mkdir mtpt
	 */
	if (stat(mountpt, &sb) || !S_ISDIR(sb.st_mode)) {
		if (! mkdirs(mountpt)) {
			return (0);
		}
	} else {
		swi_umount_dir(mountpt);
	}

	(void) snprintf(cmd, sizeof (cmd),
		"/sbin/mount -F nfs -o hard,ro,retry=2 %s %s " \
		"2> /dev/null > /dev/null", hostpath, mountpt);
	rc = system(cmd);

	if (rc) {
		return (0);
	}
	return (1);
}


/*
 * Name:	(swi_)getCDdevice
 * Description:	Get device of cdrom
 * Scope:	public
 * Arguments:	none
 * Returns:	char *	- pointer to allocated string containing device
 */
char *
swi_getCDdevice() {

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("getCDdevice");
#endif

	/*
	 * if mountpt exists, umount mtpt. Otherwise, mkdir mtpt
	 */
/*
 * change this to handle more than one cdrom
 */
return ((char *)readInText(FIND_DEVICE_OUT));
}

/*
 * Name:	(swi_)have_disc_in_drive
 * Description:	Returns 1 if there is a disc detected in drive
 * Scope:	public
 * Arguments:	device	- pointer to device of drive to check
 * Returns:	int	- 1, disc detected in drive
 *			- 0, otherwise
 */
int
swi_have_disc_in_drive(char *device) {
	char cmd[MAXPATHLEN];
	int rc;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("have_disc_in_drive");
#endif

	/*
	 * if mountpt exists, umount mtpt. Otherwise, mkdir mtpt
	 */

	/*
	 * eject -q - "Query to see if the media is present"
	 */
	(void) snprintf(cmd, sizeof (cmd),
		"/usr/bin/eject -q %s 2> /dev/null > /dev/null", device);
	rc = system(cmd);

	/*
	 * if result is 0, have disc in drive
	 */
	if (rc) {
		return (0);
	}
	return (1);
}

/*
 * Name:	(swi_)mount_disc
 * Description:	Mount disc on mountpt
 * Scope:	public
 * Arguments:	mountpt	- [RO] (char *)
 *			  directory on which to mount
 *
 * Returns:	int	- 1, mount successful
 *			- 0, mount not successful
 */
int
swi_mount_disc(char *mountpt, char *device) {
	char cmd[MAXPATHLEN];
	int attempts;
	int i;
	int rc;
	struct stat sb;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("mount_disc");
#endif

	/*
	 * if mountpt exists, umount mtpt. Otherwise, mkdir mtpt
	 */
	if (stat(mountpt, &sb) || !S_ISDIR(sb.st_mode)) {
		if (! mkdirs(mountpt)) {
			return (0);
		}
	} else {
		swi_umount_dir(mountpt);
	}

	/*
	 * Make sure disc is in drive
	 */
	attempts = 6;
	for (i = 0; i < attempts; i++) {
		if (swi_have_disc_in_drive(device)) {
			break;
		}

		/*
		 * Sleep for a while
		 */
		(void) sleep(2);
	}

	/*
	 * Command to mount a physical disc
	 */
	(void) snprintf(cmd, sizeof (cmd),
		"/sbin/mount -F hsfs -o ro %s %s " \
		"2> /dev/null > /dev/null", device, mountpt);
	rc = system(cmd);

	if (rc) {
		return (0);
	}
	return (1);
}

/*
 * Name:	(swi_)verify_solaris_image
 * Description:	Verify that mounted image is solaris image and
 *		that it matches webstart os tables
 * Scope:	public
 * Arguments:	mountpt	- mountpt where image is found
 * 		nameslist	- StringList of OS's for notice
 * 		dirslist	- StringList of OS dir's for notice
 * Returns:	SUCCESS	- if image verified
 *		ERR_INVALID	- no .cdtoc file or null mountpt
 *		ERR_NOFILE	- no .packagetoc file
 *		ERR_NOPRODUCT 	- .cdtoc PRODNAME doesn't say Solaris
 *		ERR_INVARCH	- platform doesn't match
 *		ERR_NOMATCH	- no tables match image
 */
int
swi_verify_solaris_image(char *mountpt, StringList **nameslist,
						StringList **dirslist) {
	char buf[MAXPATHLEN];
	CDToc *cdtoc = (CDToc *)NULL;
	StringList *slist = (StringList *)NULL;
	StringList *dlist = (StringList *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("verify_solaris_image");
#endif

	if (mountpt == NULL) {
		return (ERR_INVALID);
	}

	/*
	 * check for .cdtoc file
	 */
	(void) snprintf(buf, sizeof (buf), "%s/.cdtoc", mountpt);
	if (access(buf, R_OK) != 0) {
		return (ERR_INVALID);
	}

	cdtoc = (CDToc *) readCDTOC(mountpt);
	/*
	 * check for .packagetoc file
	 */
	(void) snprintf(buf, sizeof (buf),
			"%s/%s/%s", mountpt, cdtoc->proddir,
					PACKAGE_TOC_NAME);
	if (access(buf, R_OK) != 0) {
		free_cdtoc(cdtoc);
		return (ERR_NOFILE);
	}

	/*
	 * check that .cdtoc prodname says Solaris
	 */
	if (strcmp(cdtoc->prodname, "Solaris") != 0) {
		free_cdtoc(cdtoc);
		return (ERR_NOPRODUCT);
	}

	/*
	 * check for correct platform
	 */
	if (! isCorrectPlatform()) {
		free_cdtoc(cdtoc);
		return (ERR_INVARCH);
	}

	/*
	 * So far, it still looks like a Solaris CD/image.
	 * Now, check to see if any of the OS tables match the
	 * CD/image by comparing PRODVERS info. If we have no
	 * matching os's, then give warning saying incompatible cd.
	 */
	if (! checkTables(mountpt, cdtoc->prodvers, &slist, &dlist)) {
		*nameslist = slist;
		*dirslist = dlist;
		free_cdtoc(cdtoc);
		return (ERR_NOMATCH);
	}

	if (slist) {
		*nameslist = slist;
		*dirslist = dlist;
	}

	free_cdtoc(cdtoc);
	return (SUCCESS);
}


/*
 * Private functions
 */

/*
 * Name:	getOSDirs
 * Description:	Get list of directories under /usr/lib/install/data/os
 *		 e.g. /usr/lib/install/data/os/5.10
 * Scope:	private
 * Arguments:	none
 * Returns:	StringList *	- pointer to StringList
 *		NULL
 */
StringList *
getOSDirs()
{
	StringList *osDirs = (StringList *)NULL;
	DIR *dirp;
	struct stat sb;
	struct dirent *dp;
	char subdir[MAXPATHLEN + 1];

	/* see if os base dir exists  */
	if (stat(WEBSTART_OS_DIR, &sb) || !S_ISDIR(sb.st_mode)) {
		return (NULL);
	}

	if (!(dirp = opendir(WEBSTART_OS_DIR))) {
		return (NULL);
	}

	while ((dp = readdir(dirp)) != NULL) {
		if (streq(dp->d_name, ".") || streq(dp->d_name, "..")) {
			continue;
		}

		/*
		 * skip if not directory
		 */
		(void) snprintf(subdir, sizeof (subdir),
				"%s/%s", WEBSTART_OS_DIR, dp->d_name);
		if (! opendir(subdir)) {
			continue;
		}
		StringListAdd(&osDirs, subdir);
	}

	return (osDirs);
}

/*
 * Name:	getOSNames
 * Description:	Get list of names of os's in direcories in slist
 *		(e.g. /usr/lib/install/data/os/5.10) Names are found in
 *		soe.info files, key PRODNAME
 *		 e.g. PRODNAME=Solaris 10 Software
 * Scope:	private
 * Arguments:	slist	- ptr to StringList of directories
 * Returns:	StringList *	- pointer to StringList of names
 *		NULL
 */
StringList *
getOSNames(StringList *slist)
{
	char path[MAXPATHLEN+1];
	StringList *osNames = (StringList *)NULL;
	StringList *osDirs = (StringList *)NULL;
	char *osname = (char *)NULL;
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];

	osDirs = slist;
	for (; osDirs; osDirs = osDirs->next) {
		(void) snprintf(path, sizeof (path),
			"%s/%s", osDirs->string_ptr, "soe.info");
		if ((fp = fopen(path, "r")) == (FILE *)NULL) {
			/*
			 * if can't open soe.info, go to next dir
			 */
			continue;
		}

		while (fgets(buf, BUFSIZ, fp)) {
			buf[strlen(buf) - 1] = '\0';
			if (buf[0] == '#' || buf[0] == '\n' ||
					strlen(buf) == 0) {
				continue;
			} else if (strncmp(buf, "PRODNAME=", 9) == 0) {
				osname = get_value(buf, '=');
				if (osname != NULL) {
					StringListAdd(&osNames, osname);
				}
			}
		}
		(void) fclose(fp);
	}
	return (osNames);
}

/*
 * Name:	getOSMatches
 * Description:	Get list of osdirs whose prodvers value matches
 *		that in the image .cdtoc file
 * Scope:	private
 * Arguments:	cdtocProdVers	- ptr to cdtoc prodvers value to match
 * Returns:	StringList *	- pointer to StringList of dirs
 *				 e.g. /usr/lib/install/data/os/5.10
 *		NULL
 */
StringList *
getOSMatches(char *cdtocProdVers)
{
	char path[MAXPATHLEN];
	StringList *osMatches = (StringList *)NULL;
	StringList *osDirs = (StringList *)NULL;
	char *osprodvers = (char *)NULL;

	if (strlen(cdtocProdVers) == 0) {
		return (osMatches);
	}
	osDirs = getOSDirs();
	for (; osDirs; osDirs = osDirs->next) {
		(void) snprintf(path, sizeof (path),
			"%s/%s", osDirs->string_ptr, "prodvers");
		if (access(path, R_OK) != 0) {
			continue;
		}
		osprodvers = (char *)readInText(path);
		if (osprodvers && strcmp(osprodvers, cdtocProdVers) == 0) {
			StringListAdd(&osMatches, osDirs->string_ptr);
			free(osprodvers);
		}
	}
	return (osMatches);
}

/*
 * Name:	getVOLIDMatches
 * Description:	Get list of osdirs whose volid value matches
 *		that in the image .volume.inf file
 * Scope:	private
 * Arguments:	volid
 *		osmatches	ptr to StringList containing osdirs,
 *				e.g., /usr/lib/install/data/os/5.10
 * Returns:	StringList *	- pointer to StringList of dirs
 *				 e.g. /usr/lib/install/data/os/5.10
 *		NULL
 */
StringList *
getVOLIDMatches(char *volid, StringList *osmatches)
{
	FILE *fp = (FILE *)NULL;
	char *cdvolid = (char *)NULL;
	char buf[BUFSIZ + 1];
	char path[MAXPATHLEN+1];
	StringList *volidMatches = (StringList *)NULL;
	StringList *osDirs = (StringList *)NULL;

	osDirs = osmatches;
	for (; osDirs; osDirs = osDirs->next) {
		(void) snprintf(path, sizeof (path),
				"%s/%s", osDirs->string_ptr, "soe.info");
		if ((fp = fopen(path, "r")) == (FILE *)NULL) {
			/*
			 * if can't open soe.info, go to next dir
			 */
			continue;
		}

		while (fgets(buf, BUFSIZ, fp)) {
			buf[strlen(buf) - 1] = '\0';
			if (buf[0] == '#' || buf[0] == '\n' ||
					strlen(buf) == 0) {
				continue;
			} else if (strncmp(buf, "CD_VOLID=", 9) == 0) {
				cdvolid = get_value(buf, '=');
				if ((cdvolid != NULL) &&
				    (strcasecmp(cdvolid, volid) == 0)) {
					StringListAdd(&volidMatches,
							osDirs->string_ptr);
				}
			}
		}
		(void) fclose(fp);
	}
	return (volidMatches);
}

/*
 * Name:	getIDfromVolInf
 * Description:	read the .volume.inf file
 * Scope:	private
 * Arguments:	mountpt	- ptr to image mountpt where .volume.inf lives
 * Returns:	char *	- ptr to allocated volid
 */
char *
getIDfromVolInf(char *mountpt)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];
	char volinfPath[MAXPATHLEN];
	char *volid = (char *)NULL;

	(void) snprintf(volinfPath, sizeof (volinfPath),
			"%s/%s", mountpt, VOLINF_NAME);
	if ((fp = fopen(volinfPath, "r")) == (FILE *)NULL) {
		/*
		 * if can't open .volume.inf, return
		 */
		return (NULL);
	}

	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strstr(buf, "VI\"")) {
			/*
			 * get the second token
			 */
			volid = strtok(buf, "\"");
			volid = strtok(NULL, "\"");
			break;
		}
	}
	(void) fclose(fp);
	return (xstrdup(volid));
}


/*
 * Name:	checkTables
 * Description:	Checks if image matches any os supported by installer
 *		based on tables in /usr/lib/install/data/os
 * Scope:	private
 * Arguments:	mounpt	- ptr to mountpt
 *		cdtocProdVers	- ptr to value of cdtoc prodvers
 * Modifies	nlistp	- StringList * containing list of os names if
 *				none match or multiples match or NULL
 * 		dlistp	- StringList * containing list of path names
 *				 or NULL
 * Returns:	int	- 1 if platform is compatible with image
 *			- 0 if not
 */
int
checkTables(char *mountpt, char *cdtocProdVers, StringList **nlistp,
							StringList **dlistp)
{
	char *volinfid = (char *)NULL;
	StringList *osMatches = (StringList *)NULL;
	StringList *volidMatches = (StringList *)NULL;

	osMatches = getOSMatches(cdtocProdVers);
	if (! osMatches) {
		/* get names of OS's to show in notice */
		*nlistp = getOSNames(getOSDirs());
		*dlistp = getOSDirs();
		return (0);
	}

	/*
	 * We have at least one table where prodvers matches.
	 * Now, of the tables where we have the correct prodvers,
	 * check to see if the CD_VOLID in soe.info matches the
	 * volume ID in .volume.inf. If there are multiple
	 * matches, let user  choose from list. If
	 * .volume.inf doesn't match any of the CD_VOLIDs in the
	 * soe.info tables, give notice saying image isn't
	 * compatible with installer.
	 */

	/*
	 * get volid from .volume.inf file of image
	 */
	volinfid = getIDfromVolInf(mountpt);
	if (! volinfid) {
		/* get names of OS's to show in notice */
		*nlistp = getOSNames(osMatches);
		*dlistp = osMatches;
		return (1);
	}

	volidMatches = getVOLIDMatches(volinfid, osMatches);
	free(volinfid);

	/*
	 * If no volids match the image Volume ID.
	 * Give user not compatible message
	 */
	if (! volidMatches) {
		/* get names of OS's to show in notice */
		*nlistp = getOSNames(osMatches);
		*dlistp = osMatches;
		return (0);
	}

	/*
	 *
	 */
	if (StringListCount(volidMatches) == 1) {
		*nlistp = getOSNames(volidMatches);
		*dlistp = volidMatches;
		return (1);
	}

	/*
	 * Multiple volids match the image Volume ID.
	 * Give user choice of matches.
	 */
	*nlistp = getOSNames(volidMatches);
	*dlistp = volidMatches;
	return (1);
}

/*
 * Name:	isCorrectPlatform
 * Description:	Checks if platform of system is compatible with image
 *		by grep'ing the .slicemapfile.
 * Scope:	private
 * Arguments:	none
 * Returns:	int	- 1 if platform is compatible with image
 *			- 0 if not
 */
int
isCorrectPlatform()
{
	int i;
	int status;
	char cmd[MAXPATHLEN];
	char machinetype[ARCH_LENGTH] = "";

	i = sysinfo(SI_MACHINE, machinetype, ARCH_LENGTH);
	if (i < 0 || i > ARCH_LENGTH)
		return (1);

	(void) snprintf(cmd, sizeof (cmd),
			"/usr/bin/egrep -s %s$ /cdrom/.slicemapfile",
			machinetype);
	if ((status = system(cmd)) != 0) {
		return (0);
	} else {
		return (1);
	}
}
