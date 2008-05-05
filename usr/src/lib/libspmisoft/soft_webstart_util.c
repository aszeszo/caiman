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
#endif

/*
 *	File:		soft_webstart_util.c
 *
 *	Description:	This file contains various routines used by
 *			webstart ttinstall
 */
#include <dirent.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "spmisoft_lib.h"
#include "soft_launcher.h"


static int is_boot_from_disc = 0;
static int install_after_reboot = 0;
static char webstart_locale[LOCSIZE] = "C";

static char *dotswappart = SWAPPART;
static char *dotcdroot = CDROOT;
static char *extradvdswap = EXTRADVDSWAP;
static char *dotInstallDir = DOTINSTALLDIR;
static char *javaloc = JAVALOC;
static char *netcdboot = NETCDBOOT;
static char *textinstall = TEXTINSTALL;

/*
 * Public functions
 */


/*
 * Function:    (swi_)readInText
 * Description: Read in text at fullPath
 * Scope:       public
 * Parameters:  fullPath - path to file to read
 * Return:      char *  - pointer to allocated buffer containing text
 * 		NULL
 */
char *
swi_readInText(char *fullPath)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ +1];
	char *text = (char *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("readInText");
#endif

	/*
	 * open file
	 */
	if ((fp = fopen(fullPath, "r")) != (FILE *)NULL) {
		/*
		 * read in the contents of the file
		 */
		while (fgets(buf, BUFSIZ, fp)) {
			if (buf[strlen(buf) - 1] == '\n')
				buf[strlen(buf) - 1] = '\0';

			if (buf[0] == '#' || buf[0] == '\n' ||
						strlen(buf) == 0) {
				continue;
			} else {
				if (text == NULL) {
					text = xstrdup(buf);
				} else {
					text = (char *)xrealloc(text,
							strlen(text)
							+ strlen(buf) + 2);
					if (text == NULL) {
						break;
					}
					strcat(text, " ");
					strcat(text, buf);
				}
			}
		}
		(void) fclose(fp);
	}

	return (text);
}

/*
 * Function:    (swi_)writeOutText
 * Description:	Write out a line of text to fullPath.  Either append
 *		or overwrite, based on mode.
 * Scope:       public
 * Parameters:  fullPath - path to file to write to
 *		mode	 - mode to write to file ("w" or "a")
 *		line	 - line of text to write out
 * Return:      SUCCESS
 *		FAILURE
 */
int
swi_writeOutText(char *fullPath, char *mode, char *line)
{
	FILE *fp = (FILE *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("writeOutText");
#endif

	if (line == NULL || fullPath == NULL || mode == NULL)
		return (FAILURE);

	if (strncmp(mode, "w", 1) != 0 && strncmp(mode, "a", 1) != 0)
		return (FAILURE);

	if ((fp = fopen(fullPath, mode)) == (FILE *)NULL)
		return (FAILURE);

	if (fprintf(fp, "%s\n", line) < 0) {
		fclose(fp);
		return (FAILURE);
	}

	fclose(fp);

	return (SUCCESS);
}

/*
 * Name:	(swi_)concatFiles
 * Description:	Concats files together.
 * Scope:	public
 * Arguments:	fileList - StringList containing full pathnames of files
 *		outputfile - where files should be cat'd
 * Returns:	0	- error
 *		1	- success
 */
int
swi_concatFiles(StringList *fileList, char *outputfile) {
	char buf[BUFSIZ + 1];
	char *filePath = (char *)NULL;
	FILE *ifp = (FILE *)NULL;
	FILE *ofp = (FILE *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("concatFiles");
#endif
	if (! outputfile) {
		return (0);
	}

	/*
	 * open output file
	 */
	if ((ofp = fopen(outputfile, "a")) == (FILE *)NULL) {
		return (0);
	}

	/*
	 * copy contents of each input file to end of output file
	 */
	for (; fileList; fileList = fileList->next) {
		filePath = fileList->string_ptr;
		if ((ifp = fopen(filePath, "r")) == (FILE *)NULL) {
			continue;
		}

		while (fgets(buf, BUFSIZ, ifp)) {
			(void) fprintf(ofp, "%s", buf);
		}
		(void) fclose(ifp);
	}
	(void) fclose(ofp);
	return (1);
}


/*
 * Name:	(swi_)copyFile
 * Description:	Copy file from one location to another
 * Scope:	public
 * Arguments:	srcFilePath	- ptr to path of source file
 *		destFilePath	- ptr to path of dest file
 *		preserve_perm	- flag to indicate preserve permissions
 * Returns:	1	- success
 *		0	- error
 */
int
swi_copyFile(char *srcFilePath, char *destFilePath, boolean_t preserve_perm) {
	char cmd[MAXPATHLEN];

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("copyFile");
#endif

	if (srcFilePath == NULL || destFilePath == NULL) {
		return (0);
	}

	/*
	 * Create destination directory
	 */
	if (preserve_perm == B_FALSE) {
		(void) snprintf(cmd, sizeof (cmd),
			"/usr/bin/cp %s %s >/dev/null 2>&1",
			srcFilePath, destFilePath);
	} else {
		(void) snprintf(cmd, sizeof (cmd),
			"/usr/bin/cp -p %s %s >/dev/null 2>&1",
			srcFilePath, destFilePath);
	}

	if (system(cmd) != 0) {
		return (0);
	}
	return (1);

}

/*
 * Name:	(swi_)copyDir
 * Description:	Copies contents of one dir to another.
 * Scope:	public
 * Arguments:	srcDirPath	- ptr to path of source dir
 *		destDirPath	- ptr to path of dest dir
 * Returns:	1	- success
 *		0	- error
 */
int
swi_copyDir(char *srcDirPath, char *destDirPath) {
	char srcPath[MAXPATHLEN+1];
	char destPath[MAXPATHLEN+1];
	int status;
	DIR *srcdir;
	struct dirent *dp;
	struct stat sbdest;
	struct stat sbsrc;
	struct stat sbtmp;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("copyDir");
#endif
	/*
	 * Create destination directory
	 */
	if (stat(destDirPath, &sbdest) || !S_ISDIR(sbdest.st_mode)) {
		if (! mkdirs(destDirPath)) {
			return (0);
		}
	}

	/*
	 * Make sure source dir exists
	 */
	if (stat(srcDirPath, &sbsrc) || !S_ISDIR(sbsrc.st_mode)) {
			return (0);
	}

	if (!(srcdir = opendir(srcDirPath))) {
		return (0);
	}

	/*
	 * Copy the files
	 */
	while ((dp = readdir(srcdir)) != NULL) {
		if (streq(dp->d_name, ".") || streq(dp->d_name, "..")) {
			continue;
		}

		/*
		 * copy file or subdir
		 */
		(void) snprintf(srcPath, sizeof (srcPath),
				"%s/%s", srcDirPath, dp->d_name);
		(void) snprintf(destPath, sizeof (destPath),
				"%s/%s", destDirPath, dp->d_name);

		/*
		 * If srcPath is file, copy to destdir
		 * If srcPath is subdir, recursively call copyDir
		 */
		if (stat(srcPath, &sbtmp) ||
				!S_ISDIR(sbtmp.st_mode)) {
			status = swi_copyFile(srcPath, destPath, B_FALSE);
		} else {
			status = swi_copyDir(srcPath, destPath);
		}

		if (! status) {
			return (0);
		}
	}
	(void) closedir(srcdir);

	return (1);
}



/*
 * Name:	(swi_)mkdirs
 * Description:	make directory, including parent directories
 * Scope:	public
 * Arguments:	dirpath -   ptr to directory
 * Returns:	int	- 1, mkdir -p successful
 *			- 0, mkdir -p not successful
 */
int
swi_mkdirs(char *dirpath) {
	int rc;
	char *cmd;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("mkdirs");
#endif

	/*
	 * if mountpt exists, umount mtpt. Otherwise, mkdir mtpt
	 */
	cmd = xmalloc(55 + strlen(dirpath));
	(void) sprintf(cmd, "/usr/bin/mkdir -p -m 755 %s " \
		"2> /dev/null 2>&1", dirpath);
	rc = system(cmd);
	free(cmd);

	if (rc) {
		return (0);
	}
	return (1);
}

/*
 * Name:        (swi_)pingHost
 * Description: See if host reponds to ping
 * Scope:       public
 * Arguments:   host    - pointer to name of host to ping
 * Returns:     int     - status from ping command, 0 if success
 */
int
swi_pingHost(char *host) {
	char command[256];
	int rc = 1;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("ping_host");
#endif

	if (host == NULL) {
		return (1);
	}

	/*
	 * ping host (3 second t/o) to see if it exists
	 */
	(void) snprintf(command, sizeof (command),
			"/usr/sbin/ping %s 3 >/dev/null 2>&1", host);
	rc = system(command);
	return (rc);
}


/*
 * Name:	(swi_)readCDTOC
 * Description:	read the .cdtoc file
 * Scope:	public
 * Arguments:	mountpt	- ptr to mountpt where .cdtoc lives
 * Returns:	CDToc	- allocated cdtoc containing values or NULL
 *			  Caller should free cdtoc when finished
 */
CDToc *
swi_readCDTOC(char *mountpt)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];
	char cdtocPath[MAXPATHLEN + 1];
	char *str = (char *)NULL;
	CDToc *cdtoc = (CDToc *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("readCDTOC");
#endif

	(void) snprintf(cdtocPath, sizeof (cdtocPath),
			"%s/%s", mountpt, CDTOC_NAME);
	if ((fp = fopen(cdtocPath, "r")) == (FILE *)NULL) {
		/*
		 * if can't open .cdtoc, return
		 */
		return (cdtoc);
	}

	cdtoc = (CDToc *)xcalloc(sizeof (CDToc));
	cdtoc->prodname = "";
	cdtoc->prodvers = "";
	cdtoc->proddir = "";

	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strncmp(buf, "PRODNAME=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdtoc->prodname = xstrdup(str);
			}
		} else if (strncmp(buf, "PRODVERS=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdtoc->prodvers = xstrdup(str);
			}
		} else if (strncmp(buf, "PRODDIR=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdtoc->proddir = xstrdup(str);
			}
		}
	}
	(void) fclose(fp);
	return (cdtoc);
}

/*
 * Name:	(swi_)free_cdtoc
 * Description:	free cdtoc structure
 * Scope:	public
 * Arguments:	cdtoc	- pointer to cdtoc
 * Returns:	none
 */
void
swi_free_cdtoc(CDToc *cdtoc) {
#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("free_cdtoc");
#endif
	free(cdtoc->prodname);
	free(cdtoc->proddir);
	free(cdtoc->prodvers);
	free(cdtoc);
}


/*
 * Function:    (swi_)setWebstartLocale
 * Description: Set default webstart locale
 * Scope:       public
 * Parameters:  locale
 * Return:      none
 */
void
swi_setWebstartLocale(char *locale)
{
	char locstring[LOCSIZE];
	char *cp = (char *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("setWebstartLocale");
#endif

	if (! locale) {
		return;
	}

	if (locale[0] == '/') {	/* it's a composite locale */
		locale++;	/* skip over '/' */
		if ((cp = strchr(locale, '/')) != NULL) {
			(void) strncpy(locstring, locale, cp - locale);
			locstring[cp - locale] = '\0';
		} else {
			(void) strncpy(locstring, locale, LOCSIZE);
		}
		(void) strcpy(webstart_locale, locstring);
	} else {
		(void) strcpy(webstart_locale, locale);
	}
}

/*
 * Function:    (swi_)getWebstartLocale
 * Description: Returns the default locale used by webstart. A ptr to
 *		a static buffer (that should *not* be overwritten by the
 *		caller) is returned.
 * Scope:       public
 * Parameters:  none
 * Return:      char *  - pointer to static buffer containing locale
 */
char *
swi_getWebstartLocale()
{
	return (webstart_locale);
}
/*
 * Function:    (swi_)getLocString
 * Description: Get string of selected locales
 * Scope:       public
 * Parameters:  none
 * Return:      char *  - pointer to allocated, comma separated string of
 *			locales which caller should free.
 */
char *
swi_getLocString()
{
	char *loctext = (char *)NULL;
	char *locid = (char *)NULL;
	Module *locmod;
	Locale *locinfo;
	int curmem;
	int incr = 128;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("getLocString");
#endif

	loctext = (char *)xmalloc(incr);
	curmem = incr;

	/*
	 * create comma separated string of locales (starting with comma)
	 */
	*loctext = '\0';
	for (locmod = get_all_locales(); locmod; locmod = locmod->next) {
		locinfo = locmod->info.locale;
		if (locinfo->l_selected) {
			locid = locinfo->l_locale;
			if ((strlen(loctext) + strlen(locid) + 2) > curmem) {
				loctext = (char *)xrealloc(loctext,
							curmem + incr);
				curmem += incr;
			}

			if (*loctext != '\0') {
				strcat(loctext, ",");
			}
			strcat(loctext, locid);
		}
	}

	return (loctext);
}


/*
 * Function:    (swi_)check_boot_environment
 * Description: Check if we booted from disc, if java is present
 * Scope:       public
 * Parameters:  none
 * Return:      none (sets is_boot_from_disc, install_after_reboot)
 */
void
swi_check_boot_environment(void)
{
	int swappartExists = 0;
	int cdrootExists = 0;
	int extradvdswapExists = 0;
	char *rootfstype = (char *)NULL;
	struct stat sbdest;

	/*
	 * Did we boot from disc (DVD/CD1)???
	 *
	 *	If we booted from DVD/CD1, we set a flag which has effects
	 *	in various places in ttinstall. The flag is also
	 *	passed, by way of an empty directory, to the launcher.
	 *
	 *	We booted from a DVD/CD1 IF:
	 *		A) Neither /.swappart (see note) nor /.cdroot exists
	 *			AND
	 *		B) FileSystemType for "/" is ufs or hsfs
	 *		where FSType is from 4th field of mount -p
	 *
	 *	Note: If there is not enough memory for a dvd
	 *	install, a cd0-like swap partition is used.
	 *	The flag extraDVDSwapExists to signal that
	 *	although the /.swappart file exists, this is
	 *	not a real cd0 install, but a dvd install.
	 */

	is_boot_from_disc = 0;
	if (access(dotswappart, R_OK) == 0) {
		swappartExists = 1;
	}
	if (access(dotcdroot, R_OK) == 0) {
		cdrootExists = 1;
	}
	if (access(extradvdswap, R_OK) == 0) {
		extradvdswapExists = 1;
	}
	if (extradvdswapExists || (!swappartExists && !cdrootExists)) {
		if (((rootfstype = (char *)get_fs_type("/cdrom")) != NULL) &&
				((ci_streq(rootfstype, "hsfs")) ||
				(ci_streq(rootfstype, "ufs")))) {
			is_boot_from_disc = 1;

		}

		/*
		 * If install is from a CD1 disc/image,
		 * install all products after reboot
		 */
		if (stat(dotInstallDir, &sbdest) ||
					!S_ISDIR(sbdest.st_mode)) {
			install_after_reboot = 1;
		}
	}


	/*
	 * Check to see if java is in the miniroot
	 */
	if (access(javaloc, X_OK) != 0) {
		install_after_reboot = 1;
	}

	/*
	 * Check to see if "- text" boot option used. If so, want
	 * to install products after reboot.
	 */
	if (access(textinstall, F_OK) == 0) {
		install_after_reboot = 1;
	}

	/*
	 * Check to see if "- cd" boot option used. If so, want
	 * to install products after reboot.
	 */
	if (access(netcdboot, F_OK) == 0) {
		install_after_reboot = 1;
	}
}

/*
 * Function:    (swi_)isBootFromDisc
 * Description: Returns value of is_boot_from_disc
 * Scope:       public
 * Parameters:  none
 * Return:      1 if booted from disc (cd/dvd)
 *		0 if not
 */
int
swi_isBootFromDisc(void)
{
	return (is_boot_from_disc);
}

/*
 * Function:    (swi_)installAfterReboot
 * Description: Returns value of install_after_reboot
 * Scope:       public
 * Parameters:  none
 * Return:      1 if products should be installed after reboot
 *		0 if not
 */
int
swi_installAfterReboot(void)
{
	return (install_after_reboot);
}
