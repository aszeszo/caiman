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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * Module:	td_util.c
 * Group:	libtd
 * Description:
 */

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stropts.h>
#include <time.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/types.h>
#include <sys/fcntl.h>
#include <sys/filio.h>
#include <sys/mntent.h>
#include <sys/mnttab.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/swap.h>
#include <sys/wait.h>

#include "td_lib.h"

/* constants */

#define	N_PROG_LOCKS		10
#define	_SC_PHYS_MB_DEFAULT	0x1000000	/* sixteen MB */

#define	ERR_NODIR	2
#define	DEVMAP_SCRIPTS_DIRECTORY	"/usr/sadm/install/devmap_scripts"
#define	DEVMAP_TABLE_NAME		"devmap_table"

/* globals */

static char	blkdevdir[] = "/dev/dsk/";
static char	rawdevdir[] = "/dev/rdsk/";
static char	mddevdir[] = "/dev/md/";
static char	blkvxdevdir[] = "/dev/vx/dsk/";
static char	rawvxdevdir[] = "/dev/vx/rdsk/";

static char *exempt_swapfile = NULL;
static char *exempt_swapdisk = NULL;

/*
 * function pointers to libdevinfo functions to map a device name between
 * install and target environments.
 */
static int (*target2install)(const char *, const char *, char *, size_t);
static int (*install2target)(const char *, const char *, char *, size_t);

static int	run_devmap_scripts(void);

/* private prototypes */

static char	*_find_abs_path(char *);
static int	_is_bsd_device(char *path);

/* ---------------------- public functions ----------------------- */

/*
 * Function:	mapping_supported
 * Description:	Determine whether the libdevinfo library supports device name
 *		mapping functions. If supported, initialize the function
 *		pointers, target2install and install2target, to point to the
 *		mapping functions.
 * Scope:	private
 * Parameters:  none
 * Return:	1	- if libdevinfo supports device mapping
 *		0	- otherwise
 * Note:	The libdevinfo mapping functions are introduced in solaris 10
 *		and do not exist in the previous releases.
 */
static int
mapping_supported(void)
{
	static int lookup_done = 0;
	static int mapping_support = 0;
	void *lib;

	if (!lookup_done) {
		if ((lib = dlopen("libdevinfo.so.1", RTLD_LAZY)) == NULL)
			lib = dlopen("/lib/libdevinfo.so.1", RTLD_LAZY);

		if (lib != NULL) {
			target2install = (int (*)())dlsym(lib,
			    "devfs_target2install");
			install2target = (int (*)())dlsym(lib,
			    "devfs_install2target");
			if (target2install != NULL && install2target != NULL) {
				mapping_support = 1;
				/* leave the library open until process exit */
			} else
				(void) dlclose(lib);

		}
		lookup_done = 1;
	}

	return (mapping_support);
}

/*
 * Function:	td_map_to_effective_dev
 * Description:	Used during installation and upgrade to retrieve the local
 *		(boot) '/dev/<r>dsk' name which points to the same physical
 *		device (i.e. /devices/...) as 'dev' does in the <bdir>
 *              client device namespace.
 * Scope:	public
 * Parameters:	dev	- [RO] device name on the client system
 *                        (e.g. /dev/rdsk/c0t0d0s3)
 *		edevbuf	- [WO] pathname of device on booted OS (symlink to the
 *			  the /devices/.... entry for the device).
 *                        The calling routine allocates edevbuf.
 * Return:	0	- search completed; edevbuf has whatever value was found
 *		1	- failure; error while scanning links in local /dev dir
 *		2	- failure; cannot read the link /<bdir>/<dev>
 * Algorithm:	Check to see if dev is a character or block device. Then
 *		translate /<bdir>/<dev> to its symbolic link value, and
 *              scan the local (boot) /dev/<r>dsk directory for a device that
 *              has the same symlink destination (e.g. /device/...).
 *              If not found, leave edevbuf NULL, otherwise, copy the
 *              name of the local (boot) device (e.g. /dev/<r>dsk/...)
 *              into edevbuf.
 */
int
td_map_to_effective_dev(char *dev, char *edevbuf, int edevln)
{
	static char	deviceslnk[] = "../devices/";
	static char	devlnk[] = "../dev/";
	char		linkbuf[MAXNAMELEN];
	char		mapped_name[MAXPATHLEN];
	char		ldev[MAXNAMELEN];
	char		*abs_path;
	int		len;

	edevbuf[0] = '\0';

	(void) snprintf(ldev, sizeof (ldev), "%s%s", td_get_rootdir(), dev);
	if ((len = readlink(ldev, linkbuf, MAXNAMELEN)) == -1)
		return (2);
	linkbuf[len] = '\0';

	/*
	 * We now have the link (this could be to dev/ or ../devices. We now
	 * must make sure that we correctly map the BSD style devices.
	 */
	if (_is_bsd_device(dev)) {
		/* this is a BSD style device, so map it */
		if (strncmp(linkbuf, deviceslnk, strlen(deviceslnk)) == 0) {

			/*
			 * A link to ../devices/, to be compatible with SVR4
			 * devices this link must be ../../devices
			 */
			(void) snprintf(linkbuf, sizeof (linkbuf), "../%s",
			    linkbuf);
		} else {
			if (strncmp(linkbuf, devlnk, strlen(devlnk)) == 0) {
				char		*tmpStr;

				/*
				 * This is a link to ../dev, we can just
				 * strip off the ../dev and use the logic
				 * below to get the linkbuf.
				 */
				if ((tmpStr = strstr(linkbuf, devlnk)) ==
				    NULL)
					return (1);
				/* Step past the ../dev/ */
				tmpStr = tmpStr + strlen(devlnk);
				/* copy the new path into linkbuf */
				(void) strcpy(linkbuf, tmpStr);
			}

			/*
			 * Here we have a link to dev/, we now need to map
			 * this to /a/dev/ and then read that link.
			 */
			(void) snprintf(ldev, sizeof (ldev),
			    "%s/dev/%s", td_get_rootdir(), linkbuf);
			if ((len = readlink(ldev, linkbuf, MAXNAMELEN)) == -1)
				return (2);
			linkbuf[len] = '\0';
		}
	}

	/*
	 * Find the point in the linkbuf where the absolute pathname of the
	 * node begins (that is, skip over the "..[/..]*" part) and save the
	 * length of the leading relative part of the pathname.
	 */

	abs_path = _find_abs_path(linkbuf);
	len = (ptrdiff_t)abs_path - (ptrdiff_t)linkbuf;

	/*
	 * Now that we have the /devices path to the device in the target OS
	 * environment. Map the path to the current boot environment.
	 * (This is the effective device)
	 */
	if (mapping_supported()) {
		if ((*target2install)(td_get_rootdir(), abs_path, mapped_name,
		    sizeof (mapped_name)) != -1) {
			(void) strcpy(edevbuf, mapped_name);
			return (0);
		}
	} else {
		/*
		 * For SVM device paths we don't need to do the search
		 * since the /dev path we have will always match the /dev path
		 * on the installed system.
		 */
		if (access(abs_path, F_OK) == 0) {
			if (strncmp(mddevdir, dev, strlen(mddevdir)) == 0) {
				(void) strcpy(edevbuf, dev);
				return (0);

			} else if (td_map_node_to_devlink(linkbuf,
			    edevbuf, edevln) == 0)
				return (0);
		}
	}

	/*
	 * Couldn't get the effective /dev name. The device may have a new
	 * name in the new release. Attempt to map the old name to a new name.
	 */

	/* copy the leading relative part of the link to the mapped name buf */
	(void) strncpy(mapped_name, linkbuf, len);

	/*
	 * Now fill the rest of the mapped_name buffer with the mapping of
	 * the absolute part of the name (if possible).
	 */
	if (td_map_old_device_to_new(abs_path, mapped_name + len,
	    MAXPATHLEN - len) == 0)
		return (td_map_node_to_devlink(mapped_name, edevbuf, edevln));
	else
		return (1);

}

/*
 * Function:	td_map_node_to_devlink
 * Description:	Search the /dev/dsk or /dev/rdsk directory for a device link
 *		to the device node identified by devpath.  Copy the absolute
 *		pathname of that device link to the buffer pointed to by
 *		edevbuf.
 * Scope:	public
 * Parameters:	devpath	- [RO]
 *			  device node path
 *		edevbuf	- [WO]
 *			  pathname which is a symlink to the device node
 *			  identified by linkbuf.
 * Return:	0	- search completed; edevbuf has whatever value was found
 *		1	- failure; error while scanning links in local /dev dir
 *		2	- failure; cannot read the link /<bdir>/<dev>
 */
int
td_map_node_to_devlink(char *devpath, char *edevbuf, int edevln)
{
	struct dirent	*dp;
	char		elink[MAXPATHLEN];
	char		linkbuf[MAXPATHLEN];
	DIR		*dirp;
	char		*dirname;
	char		*c;
	int		len;

	/*
	 * Figure out the /dev directory to use for searching
	 */
	if (strstr(devpath, ",raw") != NULL) {
		if (strstr(devpath, "/vx@")) {
			/* VXFS character device */
			dirname = rawvxdevdir;
		} else {
			/* native character device */
			dirname = rawdevdir;
		}
	} else {
		if (strstr(devpath, "/vx@")) {
			/* VXFS block device */
			dirname = blkvxdevdir;
		} else {
			/* native block device */
			dirname = blkdevdir;
		}
	}

	/*
	 * Make the passed device node relative to the search directory
	 * found above if the device node was passed in as an absolute
	 * path.  For example, native device node /foo/bar@0,0:a
	 * would be turned into ../../foo/bar@0,0:a to make it relative
	 * to /dev/dsk.
	 */
	(void) strcpy(linkbuf, devpath);
	if (_find_abs_path(linkbuf) == linkbuf) {
		/*
		 * They gave us an absolute path.  Turn
		 * it into something relative to dirname.
		 */
		c = dirname;
		while ((c = strchr(c, '/')) != NULL && *(c + 1) != '\0') {
			if (*linkbuf == '/')
				/* Avoid double / */
				(void) memmove(linkbuf + 2, linkbuf,
				    strlen(linkbuf) + 1);
			else
				(void) memmove(linkbuf + 3, linkbuf,
				    strlen(linkbuf) + 1);

			(void) strncpy(linkbuf, "../", 3);
			c++;
		}
	}

	/*
	 * Search the search directory for a link whose target is the
	 * passed device node.
	 */
	if ((dirp = opendir(dirname)) == NULL)
		return (0);

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0)
			continue;

		(void) snprintf(edevbuf, edevln, "%s%s", dirname, dp->d_name);

		if ((len = readlink(edevbuf, elink, MAXNAMELEN)) == -1) {
			edevbuf[0] = '\0';
			(void) closedir(dirp);
			return (1);
		}
		elink[len] = '\0';

		if (strcmp(linkbuf, elink) == 0) {
			(void) closedir(dirp);
			return (0);
		}
	}
	edevbuf[0] = '\0';
	(void) closedir(dirp);
	return (1);
}

/*
 * Function:	td_map_old_device_to_new
 * Description:	Uses the /tmp/physdevmap.nawk.* files (if any) to map the
 *		input device name to the new name for the same device.	If
 *		the name can be mapped, copy the mapped name into newdev.
 *		Otherwise, just copy olddev to newdev.
 * Scope:	public
 * Parameters:	olddev	- [RO]
 *			  device name to be mapped (may have leading "../"*)
 *		newdev	- [WO]
 *			  new, equivalent name for same device.
 *		n_size	- [RO]
 *			  size of newdev buffer
 * Return:	 none
 * Note:	If this is the first call to this routine, use the
 *		/tmp/physdevmap.nawk.* files to build a mapping array.
 *		Once the mapping array is built, use it to map olddev
 *		to the new device name.
 */
int
td_map_old_device_to_new(char *olddev, char *newdev, int n_size)
{
	static boolean_t	nawk_script_known_not_to_exist = B_FALSE;
	static boolean_t	devmap_table_known_not_to_exist = B_FALSE;
	static boolean_t	devmap_scripts_run = B_FALSE;
	static char	nawkfile[] = "physdevmap.nawk.";
	static char	sh_env_value[] = "SHELL=/sbin/sh";
	char		cmd[512];
	char		line[DDM_CMD_LEN];
	DIR		*dirp;
	FILE		*pipe_fp;
	FILE		*fp;
	char		*p;
	boolean_t	nawk_script_found;
	int		status;
	boolean_t	devmap_table_found;
	struct dirent	*dp;
	char		*envp;
	char		*shell_save = NULL;

	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "Size of newdev buffer is %d\n", n_size);

	if (nawk_script_known_not_to_exist &&
	    devmap_table_known_not_to_exist)
		return (1);

	/*
	 * Initialize device mapping table by running devmap scripts.
	 * Mapping table is created in /tmp directory.
	 */

	if (!devmap_scripts_run) {
		devmap_scripts_run = B_TRUE;

		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "Running devmap scripts...\n");

		if ((status = run_devmap_scripts()) != 0 &&
		    status != ERR_NODIR) {
			devmap_table_known_not_to_exist = B_TRUE;

			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "devmap scripts failed with error %d\n",
				    status);
		}
	}

	if ((dirp = opendir("/tmp")) == NULL) {
		nawk_script_known_not_to_exist = B_TRUE;
		devmap_table_known_not_to_exist = B_TRUE;
		return (1);
	}
	nawk_script_found = B_FALSE;
	devmap_table_found = B_FALSE;

	/*
	 * Temporarily set the value of the SHELL environment variable to
	 * "/sbin/sh" to ensure that the Bourne shell will interpret the
	 * commands passed to popen.  Then set it back to whatever it was
	 * before after doing all the popens.
	 */

	if ((envp = getenv("SHELL")) != NULL) {
		shell_save = malloc(strlen(envp) + 6 + 1);
		(void) strcpy(shell_save, "SHELL=");
		(void) strcat(shell_save, envp);
		(void) putenv(sh_env_value);
	}
	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0)
			continue;

		if (strcmp(DEVMAP_TABLE_NAME, dp->d_name) == 0) {
			devmap_table_found = B_TRUE;
			continue;
		}

		if (strncmp(nawkfile, dp->d_name, strlen(nawkfile)) != 0)
			continue;

		nawk_script_found = B_TRUE;

		/*
		 * This is a nawk script for mapping old device names to new.
		 * Now use it to try to map olddev to a new name.
		 */

		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/bin/echo \"%s\" | "
		    "/usr/bin/nawk -f /tmp/%s -v 'rootdir=\"%s\"' "
		    "2>/dev/null", olddev, dp->d_name,
		    streq(td_get_rootdir(), "") ? "/" : td_get_rootdir());

		if ((pipe_fp = (FILE *)popen(cmd, "r")) == NULL)
			continue;

		if (fgets(newdev, n_size, pipe_fp) != NULL) {
			/* remove the trailing new-line */
			newdev[strlen(newdev) - 1] = '\0';
			(void) pclose(pipe_fp);
			(void) closedir(dirp);
			if (shell_save != NULL)
				(void) putenv(shell_save);
			return (0);
		}
		(void) pclose(pipe_fp);
	}
	(void) closedir(dirp);

	if (shell_save != NULL)
		(void) putenv(shell_save);

	if (!nawk_script_found)
		nawk_script_known_not_to_exist = B_TRUE;

	if (!devmap_table_found) {
		devmap_table_known_not_to_exist = B_TRUE;

		return (1);
	}

	fp = (FILE *)fopen("/tmp/" DEVMAP_TABLE_NAME, "r");
	if (fp == NULL) {
		if (TLW)
			td_debug_print(LS_DBGLVL_WARN,
			    "File %s was created, "
			    "but can't be opened\n",
			    "</tmp/" DEVMAP_TABLE_NAME ">");

		devmap_table_known_not_to_exist = B_TRUE;
		return (1);
	}

	while (fgets(line, sizeof (line), fp) != NULL) {
		if ((p = strtok(line, "\t")) == NULL)
			continue;

		if (strcmp(p, olddev) != 0)
			continue;

		p = strtok(NULL, "\t");
		if (strlcpy(newdev, p, n_size) >= n_size) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "New device pathname too "
				    "long, it was truncated. "
				    "Mapping will fail\n");

			(void) fclose(fp);
			return (1);
		}

		/* Remove trailing newline */

		newdev[strlen(newdev) - 1] = '\0';

		(void) fclose(fp);
		return (0);
	}

	(void) fclose(fp);
	return (1);
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	_find_abs_path
 * Description: Find the absolute part of a relative pathname (that is,
 *		find the part that starts after the "..[/..]*".	 If no "."
 *		or ".." pathname segments exist at the beginning of the path,
 *		just return the beginning of the input string.	Don't modify
 *		the input string. Just return a pointer to the character in the
 *		input string where the absolute part begins.
 * Scope:	private
 * Parameters:	path	- pointer to the pathname whose absolute portion is
 *			  to be found.
 * Return:	pointer to the absolute part of the pathname.
 */
static char    *
_find_abs_path(char *path)
{
	enum parse_state {
		AFTER_SLASH,
		AFTER_FIRST_DOT,
		AFTER_SECOND_DOT
	}		state;
	char		*cp;
	char		*last;

	for (cp = path, last = path, state = AFTER_SLASH; *cp; cp++) {
		switch (*cp) {
		case '.':
			if (state == AFTER_SLASH)
				state = AFTER_FIRST_DOT;
			else if (state == AFTER_FIRST_DOT)
				state = AFTER_SECOND_DOT;
			else if (state == AFTER_SECOND_DOT)
				return (last);
			break;

		case '/':
			if (state == AFTER_SLASH)
				last = cp;
			else if (state == AFTER_FIRST_DOT ||
			    state == AFTER_SECOND_DOT) {
				last = cp;
				state = AFTER_SLASH;
			}
			break;

		default:
			return (last);
		}
	}
	/* NOTREACHED */
}

/*
 * Function:	_is_bsd_device
 * Description:	Determine whether or not a device path is a BSD-style device.
 *		A BSD-style device is defined as one that does not match the
 *		following regex: '/dev/dsk/(|md|vx)/'.
 * Scope:	private
 * Parameters:	path	- pointer to the device path to be checked.
 * Return:	1	- path is a BSD-style device path
 *		0	- path is not a BSD-style device path
 */
static int
_is_bsd_device(char *path)
{
	if (strncmp(path, blkdevdir, strlen(blkdevdir)) != 0 &&
	    strncmp(path, mddevdir, strlen(mddevdir)) != 0 &&
	    strncmp(path, blkvxdevdir, strlen(blkvxdevdir)) != 0 &&
	    strncmp(path, rawdevdir, strlen(rawdevdir)) != 0 &&
	    strncmp(path, rawvxdevdir, strlen(rawvxdevdir)) != 0) {
		/* this must be a BSD style device */
		return (1);
	} else {
		return (0);
	}
}

/*
 * Function:	td_SetExemptSwapfile
 * Description: Set the exempt_swapfile global to string sf passed in.
 * Status: public
 * Parameters:
 *	sf	- exempt_swapfile name
 * Return: none
 *
 */
void
td_SetExemptSwapfile(char *sf)
{
	if (exempt_swapfile) {
		free(exempt_swapfile);
		exempt_swapfile = NULL;
	}
	if (sf) {
		exempt_swapfile = strdup(sf);
	}
}

/*
 * Function:	td_SetExemptSwapdisk
 * Description: Set the exempt_swapdisk global to string sd passed in.
 * Status: public
 * Parameters:
 *	sd	- exempt_swapdisk name
 * Return: none
 */
void
td_SetExemptSwapdisk(char *sd)
{
	if (exempt_swapdisk) {
		free(exempt_swapdisk);
		exempt_swapdisk = NULL;
	}

	if (sd) {
		exempt_swapdisk = strdup(sd);
	}
}

/*
 * Function:	td_GetExemptSwapfile
 * Description: Get the exempt_swapfile global
 * Status: public
 * Parameters:
 * Return: char * exempt_swapfile
 *
 */
char *
td_GetExemptSwapfile()
{
	return (exempt_swapfile);
}

/*
 * Function:	td_GetExemptSwapdisk
 * Description: Get the exempt_swapdisk global
 * Scope: public
 * Parameters:
 * Return: char * exempt_swapdisk
 *
 */
char *
td_GetExemptSwapdisk()
{
	return (exempt_swapdisk);
}

/*
 * Function:	td_delete_all_swap
 * Description: deletes all swap devices and files except
 *              the exempt swapfile if set.
 * Scope: public
 * Parameters:
 * Return: 0 - no devices configured or success
 *         2 - malloc failed
 *         -1 - swap cannot be deleted
 */
int
td_delete_all_swap(void)
{
	struct swaptable *st;
	struct swapent *swapent;
	int i;
	int num;
	swapres_t swr;
	char *path;
	char *pathcopy;
	char *exempt_swapfile;

	/* get the path to the swapfile */
	exempt_swapfile = td_GetExemptSwapfile();
	/* get the number of swap devices */
	if ((num = swapctl(SC_GETNSWP, NULL)) == -1) {
		return (2);
	}

	if (num == 0) {
		/* no swap devices configured */
		return (0);
	}
	/* allocate the swaptable */
	if ((st = malloc(num * sizeof (swapent_t) + sizeof (int)))
	    == NULL) {
		return (2);
	}
	/* allocate the tmppath */
	if ((path = malloc(num * (MAXPATHLEN + 1))) == NULL) {
		/* malloc failed */
		return (2);
	}
	/*
	 * set swapent to point to the beginning of
	 * the swaptables swapent array
	 */
	swapent = st->swt_ent;
	/* initialize the swapent path to path */
	pathcopy = path;
	for (i = 0; i < num; i++, swapent++) {
		swapent->ste_path = pathcopy;
		pathcopy += MAXPATHLEN;
	}
	/* get the swaptable list from the swap ctl */
	st->swt_n = num;
	if ((num = swapctl(SC_LIST, st)) == -1) {
		return (2);
	}
	/* point swapent at the beginning of the list of swap ents in st */
	swapent = st->swt_ent;
	for (i = 0; i < num; i++, swapent++) {
		/* check to make sure the ste_path is not the exempt_swapfile */
		if ((exempt_swapfile == NULL) ||
		    (strcmp(swapent->ste_path, exempt_swapfile) != 0)) {
				/* delete the swapfile */
				swr.sr_name = swapent->ste_path;
				swr.sr_start = swapent->ste_start;
				swr.sr_length = swapent->ste_length;
				/* do the delete */
				if (swapctl(SC_REMOVE, &swr) < 0) {
					return (-1);
				}
		}
	}
	/* free up what was created */
	free(st);
	free(path);
	return (0);
}

/*
 * run_devmap_scripts()
 * Parameters:
 *    none
 * Return:
 *    int
 * Status:
 *    private
 */
static int
run_devmap_scripts(void)
{
	DIR		*dirp;
	struct dirent	*dp;
	int		status;
	char		cmd[DDM_CMD_LEN];
	boolean_t	script_run = B_FALSE;

	if ((dirp = opendir(DEVMAP_SCRIPTS_DIRECTORY)) == NULL) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "Directory %s doesn't exist. No scripts to run\n",
			    DEVMAP_SCRIPTS_DIRECTORY);

		return (ERR_NODIR);
	}

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0)
		continue;

		(void) snprintf(cmd, sizeof (cmd), "%s/%s %s >/dev/null\n",
		    DEVMAP_SCRIPTS_DIRECTORY,
		    dp->d_name,
		    td_get_rootdir());

		status = td_safe_system(cmd);

		if (status == -1) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "popen(3C) for command %s failed\n", cmd);

			(void) closedir(dirp);
			return (status);
		}

		if (WEXITSTATUS(status) != 0) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Command %s exited with error code %d\n",
				    cmd, WEXITSTATUS(status));

			(void) closedir(dirp);
			return (WEXITSTATUS(status));
		}

		/*
		 * Script was run and finished successfully, set the flag
		 */

		script_run = B_TRUE;
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "Command %s finished successfully\n",
			    cmd);
	}

	(void) closedir(dirp);

	/*
	 * If there was no script to run, mapping table was not
	 * generated - return with failure in this case. Otherwise
	 * report successs.
	 */
	if (script_run)
		return (0);
	else
		return (1);
}
