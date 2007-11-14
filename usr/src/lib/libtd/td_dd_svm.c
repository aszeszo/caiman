/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
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

#pragma ident	"@(#)td_dd_svm.c	1.1	07/08/03 SMI"

#include <assert.h>

#include <td_dd.h>
#include <td_lib.h>

#include <libsvm.h>
#include <spmicommon_api.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <dlfcn.h>
#include <fcntl.h>
#include <link.h>
#include <unistd.h>

#include <sys/types.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/wait.h>

#include <dirent.h>

/* private constants */
#define	DDM_MKDTEMP_TEMPLATE	"/tmp/ddm_XXXXXX"

#define	DDM_CMD_LEN 1000

static char	blkdevdir[] = "/dev/dsk/";
static char	rawdevdir[] = "/dev/rdsk/";
static char	mddevdir[] = "/dev/md/";
static char	blkvxdevdir[] = "/dev/vx/dsk/";
static char	rawvxdevdir[] = "/dev/vx/rdsk/";

/* private variables */

static boolean_t ddm_svm_enabled = B_TRUE;
static boolean_t ddm_libsvm_opened = B_FALSE;
static boolean_t ddm_libsvm_attempted = B_FALSE;

/* declaration of private functions */

static svm_info_t *(*_svm_alloc)(void);
static void (*_svm_free)(svm_info_t *);
static int (*_svm_check)(char *);
static int (*_svm_start)(char *, svm_info_t **, int);
static int (*_svm_stop)(void);
static int (*_svm_get_components)(char *, svm_info_t **);

/*
 * function pointers to libdevinfo functions to map a device name between
 * install and target environments.
 */
static int (*target2install)(const char *, const char *, char *, size_t);
static int (*install2target)(const char *, const char *, char *, size_t);

/* ------------------------ local functions --------------------------- */

/*
 * Function:	ddm_find_abs_path
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
static char *
ddm_find_abs_path(char *path)
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
 * Function:	ddm_is_bsd_device
 * Description:	Determine whether or not a device path is a BSD-style device.
 *		A BSD-style device is defined as one that does not match the
 *		following regex: '/dev/dsk/(|md|vx)/'.
 * Scope:	private
 * Parameters:	path	- pointer to the device path to be checked.
 * Return:	1	- path is a BSD-style device path
 *		0	- path is not a BSD-style device path
 */
static int
ddm_is_bsd_device(char *path)
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
 * Function:	ddm_mapping_supported
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
ddm_mapping_supported(void)
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
 * Function:	ddm_map_node_to_devlink
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
static int
ddm_map_node_to_devlink(char *devpath, char *edevbuf)
{
	struct dirent	*dp;
	char		elink[MAXPATHLEN];
	char		linkbuf[MAXPATHLEN];
	DIR		*dirp;
	char		*dirname;
	char		*c;
	ssize_t		len;

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
	if (linkbuf[0] == '/') {
		/*
		 * They gave us an absolute path.  Turn
		 * it into something relative to dirname.
		 */
		c = dirname;
		while (((c = strchr(c, '/')) != NULL) && (c[1] != '\0')) {
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

		(void) snprintf(edevbuf, MAXPATHLEN, "%s%s", dirname,
		    dp->d_name);

		if ((len = readlink(edevbuf, elink, sizeof (elink))) == -1) {
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
 * Function:	ddm_map_old_device_to_new
 * Description:	Uses the /tmp/physdevmap.nawk.* files (if any) to map the
 *		input device name to the new name for the same device.	If
 *		the name can be mapped, copy the mapped name into newdev.
 *		Otherwise, just copy olddev to newdev.
 * Scope:	public
 * Parameters:	olddev	- [RO]
 *			  device name to be mapped (may have leading "../"*)
 *		newdev	- [WO]
 *			  new, equivalent name for same device.
 *		mntpnt	- [RO]
 *			  root moutpoint
 * Return:	 none
 * Note:	If this is the first call to this routine, use the
 *		/tmp/physdevmap.nawk.* files to build a mapping array.
 *		Once the mapping array is built, use it to map olddev
 *		to the new device name.
 */
int
ddm_map_old_device_to_new(char *olddev, char *newdev, char *mntpnt)
{
	static int	nawk_script_known_not_to_exist = 0;
	static char	nawkfile[] = "physdevmap.nawk.";
	static char	sh_env_value[] = "SHELL=/sbin/sh";
	char		cmd[MAXPATHLEN];
	DIR		*dirp;
	FILE		*pipe_fp;
	int		nawk_script_found;
	struct dirent	*dp;
	char		*envp;
	char		*shell_save = NULL;

	if (nawk_script_known_not_to_exist)
		return (1);

	if ((dirp = opendir("/tmp")) == NULL) {
		nawk_script_known_not_to_exist = 1;
		return (1);
	}
	nawk_script_found = 0;

	/*
	 * Temporarily set the value of the SHELL environment variable to
	 * "/sbin/sh" to ensure that the Bourne shell will interpret the
	 * commands passed to popen.  Then set it back to whatever it was
	 * before after doing all the popens. Handle the case, when
	 * SHELL variable is not set
	 */

	envp = getenv("SHELL");

	if (envp != NULL) {
		shell_save = malloc(strlen(envp) + 6 + 1);
		assert(shell_save != NULL);

		(void) strcpy(shell_save, "SHELL=");
		(void) strcat(shell_save, envp);
	} else {
		shell_save = "SHELL=";
	}

	(void) putenv(sh_env_value);

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0)
			continue;

		if (strncmp(nawkfile, dp->d_name, strlen(nawkfile)) != 0)
			continue;

		nawk_script_found = 1;

		/*
		 * This is a nawk script for mapping old device names to new.
		 * Now use it to try to map olddev to a new name.
		 */

		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/bin/echo \"%s\" | "
		    "/usr/bin/nawk -f /tmp/%s -v 'rootdir=\"%s\"' "
		    "2>/dev/null", olddev, dp->d_name,
		    (strcmp(mntpnt, "") == 0) ? "/" : mntpnt);

		if ((pipe_fp = popen(cmd, "r")) == NULL)
			continue;

		if (fgets(newdev, MAXPATHLEN, pipe_fp) != NULL) {
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

	if (nawk_script_found == 0)
		nawk_script_known_not_to_exist = 1;
	return (1);
}

/*
 * Function:	ddm_map_to_effective_dev
 * Description:	Used during installation and upgrade to retrieve the local
 *		(boot) '/dev/<r>dsk' name which points to the same physical
 *		device (i.e. /devices/...) as 'dev' does in the <bdir>
 *              client device namespace.
 * Scope:	private
 * Parameters:	dev	- [RO] device name on the client system
 *                        (e.g. /dev/rdsk/c0t0d0s3)
 *		edevbuf	- [WO] pathname of device on booted OS (symlink to the
 *			  the /devices/.... entry for the device).
 *                        The calling routine allocates edevbuf.
 *		mntpnt	- alternate root mountpoint
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
static int
ddm_map_to_effective_dev(char *dev, char *edevbuf, char *mntpnt)
{
	static char	deviceslnk[] = "../devices/";
	static char	devlnk[] = "../dev/";
	char		linkbuf[MAXNAMELEN];
	char		mapped_name[MAXPATHLEN];
	char		ldev[MAXNAMELEN];
	char		*abs_path;
	ssize_t		len;

	edevbuf[0] = '\0';

	(void) snprintf(ldev, sizeof (ldev), "%s%s", mntpnt, dev);
	if ((len = readlink(ldev, linkbuf, MAXNAMELEN)) == -1)
		return (2);
	linkbuf[len] = '\0';

	/*
	 * We now have the link (this could be to dev/ or ../devices. We now
	 * must make sure that we correctly map the BSD style devices.
	 */
	if (ddm_is_bsd_device(dev)) {
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
			    "%s/dev/%s", mntpnt, linkbuf);
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

	abs_path = ddm_find_abs_path(linkbuf);
	len = strlen(linkbuf) - strlen(abs_path);

	/*
	 * Now that we have the /devices path to the device in the target OS
	 * environment. Map the path to the current boot environment.
	 * (This is the effective device)
	 */
	if (ddm_mapping_supported()) {
		if ((*target2install)(mntpnt, abs_path, mapped_name,
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

			} else if (ddm_map_node_to_devlink(linkbuf, edevbuf)
			    == 0)
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
	if (ddm_map_old_device_to_new(abs_path, mapped_name + len, mntpnt) == 0)
		return (ddm_map_node_to_devlink(mapped_name, edevbuf));
	else
		return (1);

}

/*
 * Function:	ddm_fs_mount
 * Description:	Mount a block special device containing a file system. If
 *		the file system type is unspecified, all possible file
 *		system types are tried until one successfully mounts or
 *		all possibilities are exhausted. If the special device name
 *		specified is a simple slice device name (e.g. c0t3d0s3), the
 *		block special device is assume to exist in /dev/dsk. Otherwise,
 *		the user may supply a fully qualified path name to the block
 *		special device.
 *
 *		NOTE: This function explicitly uses the "mount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.  The caller
 *			of this function is responsible for making sure that
 *			the device name is appropriate for the filesystem
 *			being mounted.
 *		mntpnt	[RO, *RO]
 *			UNIX path name for the mount point directory.
 *			before mounting.
 *		mntopt	[RO, *RO] (optional)
 *			Mount options. If NULL specified, then "mount" command
 *			defaults are used. Options should appear as they would
 *			on the mount line (e.g. "-r").
 *		fstype	[RO, *RO] (optional)
 *			File system type specifier (e.g. "ufs"). If none
 *			is specified, a mount attempt is made for each type
 *			which is defined on the system.
 * Return:	 0	- mount was successful
 *		-1	- mount failed
 */
static int
ddm_fs_mount(char *device, char *mntpnt, char *mntopts, char *fstype)
{
	struct stat	sbuf;
	char		cmd[DDM_CMD_LEN];
	char		disk[MAXPATHLEN];
	int		ret;

	/* only "ufs" filesystem is supported for now */

	if (strcmp(fstype, "ufs") != 0) {
		DDM_DEBUG(DDM_DBGLVL_WARNING, "%s",
		    "ddm_fs_mount(): Only UFS fs supported\n");

		return (DDM_FAILURE);
	}

	/* validate parameters */

	if (!ddm_is_pathname(mntpnt) || (stat(mntpnt, &sbuf) < 0) ||
	    ((sbuf.st_mode & S_IFDIR) == 0)) {

		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_fs_mount(): %s is not valid mountpoint\n", mntpnt);

		return (DDM_FAILURE);
	}

	/* create the block special disk device name */

	if (!ddm_is_pathname(device)) {
		(void) snprintf(disk, sizeof (disk), "/dev/dsk/%s", device);
	} else {
		(void) strcpy(disk, device);
	}

	/*
	 * Before mounting ufs file system
	 * make sure it is clean and mountable
	 */

	(void) snprintf(cmd, sizeof (cmd),
	    "fsck -F %s -m %s >/dev/null 2>>/tmp/install_log.debug", fstype,
	    disk);

	ret = system(cmd);
	if ((ret == -1) || (WEXITSTATUS(ret) != 0)) {

		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_fs_mount(): fsck -F ufs -m %s failed\n", disk);

		return (DDM_FAILURE);
	}

	(void) snprintf(cmd, MAXPATHLEN,
	    "mount -F %s %s %s %s >/dev/null 2>>/tmp/install_log.debug",
	    fstype, mntopts == NULL ? "" : mntopts, disk, mntpnt);

	ret = system(cmd);
	if ((ret == -1) || (WEXITSTATUS(ret) != 0))
		return (DDM_FAILURE);

	return (DDM_SUCCESS);
}

/*
 * Function:	ddm_fs_umount
 * Description:	Unmount a filesystem.
 *
 *		NOTE: This function explicitly uses the "umount" command in
 *		      order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	name		[RO, *RO]
 *				The filesystem to be unmounted.  `name' can
 *				either be the path to the block special device
 *				containing the filesystem to be unmounted, or
 *				it can be the mountpoint of said filesystem.
 *				The caller is responsible for making sure that
 *				the filesystem corresponding to this device is
 *				already mounted.
 *		oldmountpt	[RO, *RO] (char *) (OPTIONAL)
 *				If the filesystem being unmounted is ufs,
 *				rewrite the last mount point field with this
 *				value so it looks like we never mounted it.
 *				Disregarded if the filesystem type isn't ufs.
 *				If the type is ufs, and oldmountpt is NULL,
 *				the name isn't rewritten.
 *		cdevice		[RO, *RO] (char *) (OPTIONAL)
 *				The character device for the filesystem.
 *				Needed only if the last mount name is being
 *				being rewritten (see `oldmountpt').
 * Return:	0	- unmount was successful
 *		1	- unmount failed
 */
static int
ddm_fs_umount(char *name)
{
	char		cmd[MAXPATHLEN * 2 + 128];

	/* validate parameters */
	if (name == NULL || !ddm_is_pathname(name)) {

		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_fs_umount(): Invalid device name %s\n",
		    name == NULL ? "NULL" : name);

		return (DDM_FAILURE);
	}

	/* Unmount it */

	(void) snprintf(cmd, sizeof (cmd), "umount %s >/dev/null 2>&1",
	    name);

	if (WEXITSTATUS(system(cmd)) != 0) {

		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_fs_umount(): umount %s failed\n", name);
	}

	return (0);
}

/*
 * Function:	ddm_ufs_mount
 * Description:	Mount a block special device containing a UFS file system. If
 *		the special device name specified is a simple slice device
 *		name (e.g. c0t3d0s3), the block special device is assumed
 *		to exist in /dev/dsk. Otherwise, the user may supply a
 *		fully qualified path name to the block special device.
 *
 *		NOTE: This function explicitly uses the "mount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Slice device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.
 *		mntpnt	[RO, *RO]
 *			UNIX path name for the mount point directory.
 *			before mounting.
 *		mntopt	[RO, *RO] (optional)
 *			Mount options. If NULL specified, then "mount" command
 *			defaults are used. Options should appear as they would
 *			on the mount line (e.g. "-r").
 * Return:	 0	- the mount completed successfully
 *		-1	- the mount failed
 */
static int
ddm_ufs_mount(char *device, char *mntpnt, char *mntopt)
{
	char	*c;

	/* Check parameters */
	if (device == NULL || mntpnt == NULL)
		return (-1);

	/* Make sure it's a slice name or a path to one */

	if (!ddm_is_slice_name(device)) {
		if (!ddm_is_pathname(device) ||
		    !(c = strrchr(device, '/')) ||
		    !ddm_is_slice_name(c + 1))
			return (-1);
	}

	if (ddm_fs_mount(device, mntpnt, mntopt, "ufs") < 0)
		return (-1);
	else
		return (0);
}

/*
 * Function:	ddm_ufs_umount
 * Description:	Unmount a block special device containing a UFS file system,
 *		with the option to set the "last-mounted-on" field in the
 *		super-block to an explicit value. If the special device name
 *		specified is a simple slice device name (e.g. c0t3d0s3), the
 *		block special device is assume to exist in /dev/dsk. Otherwise,
 *		the user may supply a fully qualified path name to the block
 *		special device. If the user provides a fully qualified
 *		block special device, and a mount point name for restoration,
 *		the user must also provide a fully qualified character
 *		special device. This is the only time a non-NULL value
 *		should be specified for the character special device.
 *
 *		NOTE: This function explicitly uses the "umount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	bdevice	[RO, *RO]
 *			Slice device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.
 *
 * Return:	 0	- the unmount completed successfully
 *		-1	- the unmount failed
 */
static int
ddm_ufs_umount(char *bdevice)
{
	char bdevpath[MAXPATHLEN];

	/* Put the whole path to the block device in bdevpath */
	if (ddm_is_slice_name(bdevice)) {
		(void) snprintf(bdevpath, MAXPATHLEN, "/dev/dsk/%s", bdevice);
	} else if (ddm_is_pathname(bdevice)) {
		(void) strcpy(bdevpath, bdevice);
	} else {
		return (-1);
	}

	return (ddm_fs_umount(bdevpath));
}

/*
 * Function:		ddm_convert_svminfo_if_remapped
 * Description: 	converts the components of an svm_info_t to the
 *			correct device mapping for the miniroot
 *			calls ddm_map_to_effective_dev()
 * Scope:		private
 * Parameters:  	svm_info_t *svm
 *			char *mntpnt
 *
 * Return:		void
 */
static void
ddm_convert_svminfo_if_remapped(svm_info_t *svm, char *mntpnt)
{
	int 	i;
	char	tmpdev[MAXPATHLEN];
	char	emnt[MAXPATHLEN];

	if (svm != NULL && svm->count > 0) {
		for (i = 0; i < svm->count; i++) {
			(void) snprintf(tmpdev, MAXPATHLEN, "/dev/rdsk/%s",
			    svm->md_comps[i]);
			if (ddm_map_to_effective_dev(tmpdev, emnt, mntpnt)
			    == 0) {
				free(svm->md_comps[i]);
				if ((svm->md_comps[i] =
				    strdup(emnt + strlen("/dev/rdsk/"))) ==
				    NULL) {
					DDM_DEBUG(DDM_DBGLVL_ERROR,
					    "ddm_convert_svminfo_if_remapped():"
					    "OOM\n");
				}

				DDM_DEBUG(DDM_DBGLVL_INFO,
				    "ddm_convert_svm_info_if_remapped():"
				    "Mapping successful\n");
			} else {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_convert_svm_info_if_remapped():"
				    "Mapping failed\n");
			}
		}
	}
}

/*
 * Function:	ddm_init_lib_svm
 *
 * description: dlopens the libsvm library and links all interfaces
 *		we need in order to detect and mount metadevices
 *
 * returns:	void
 */

static void
ddm_init_lib_svm(void)
{
	void *lib;

	if (ddm_libsvm_opened || ddm_libsvm_attempted)
		return;

	/* don't attempt this again if it fails the first time */
	ddm_libsvm_attempted = B_TRUE;

	if ((lib = dlopen("/usr/snadm/lib/libsvm.so", RTLD_LAZY)) == NULL) {

		/* library does not exist, set the flag and return */

		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_init_lib_svm(): libsvm.so not found\n");

		ddm_libsvm_opened = B_FALSE;

		return;
	} else {
		/* we found it, so we don't need to check again */

		ddm_libsvm_opened = B_TRUE;
	}

	DDM_DEBUG(DDM_DBGLVL_NOTICE,
	    "ddm_init_lib_svm(): libsvm.so successfully opened\n");

	/* now load the libraries */
	/* svm_check returns an int */
	_svm_check =
	    (int (*)(char *))dlsym(lib, "svm_check");
	/* svm_start returns an int */
	_svm_start =
	    (int (*)(char *, svm_info_t **, int))dlsym(lib, "svm_start");
	/* svm_stop returns an int */
	_svm_stop =
	    (int (*)())dlsym(lib, "svm_stop");
	/* svm_alloc returns a pointer to a svm_info_t */
	_svm_alloc =
	    (svm_info_t *(*)())dlsym(lib, "svm_alloc");
	/* svm_free returns a void */
	_svm_free =
	    (void (*)(svm_info_t *))dlsym(lib, "svm_free");
	/* svm_get_components returns an int */
	_svm_get_components =
	    (int (*)(char *, svm_info_t **))dlsym(lib, "svm_get_components");

	if ((_svm_check == NULL) ||
	    (_svm_start == NULL) ||
	    (_svm_stop == NULL) ||
	    (_svm_alloc == NULL) ||
	    (_svm_free == NULL) ||
	    (_svm_get_components == NULL)) {

		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_init_lib_svm(): failed to load all functions\n");

		ddm_libsvm_opened = B_FALSE;

		return;
	}

	DDM_DEBUG(DDM_DBGLVL_NOTICE,
	    "ddm_init_lib_svm(): all functions loaded\n");
}

/*
 * Function:    ddm_svm_alloc()
 *
 * Description: wrapper around libsvm's svm_alloc()
 * Scope:       public
 * Parameters:  none
 *
 * Return:      svm_info_t * || NULL
 */
svm_info_t *
ddm_svm_alloc(void)
{
	ddm_init_lib_svm();

	if (!ddm_libsvm_opened)
		return (NULL);

	return ((*_svm_alloc)());
}

/*
 * Function:    ddm_svm_free()
 *
 * Description: wrapper around libsvm's svm_free()
 * Scope:       public
 * Parameters:  none
 *
 * Return:      void
 */
void
ddm_svm_free(svm_info_t *svm)
{
	if (!ddm_libsvm_opened) {
		svm = NULL;
		return;
	}

	(*_svm_free)(svm);
}

/*
 * Function:	ddm_check_for_svm
 * Description: Checks the mounted filesystem for the existence of an svm
 *		database
 * Scope:	public
 * Parameters:  mountpoint - non-NULL mount string
 *
 * Return:	0 for success, otherwise -1
 */

int
ddm_check_for_svm(char *mountpoint)
{

	/* if SVM disabled, then return */
	if (!ddm_svm_enabled) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE,
		    "ddm_check_for_svm(): SVM disabled\n");

		return (-1);
	}

	/* initialize the swlib */
	ddm_init_lib_svm();

	/*
	 * If no libraries, return
	 */
	if (!ddm_libsvm_opened) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_check_for_svm(): Couldn't open libsvm library\n");

		return (-1);
	}

	/*
	 * Call the svm_check function in libsvm.so
	 */
	if ((*_svm_check)(mountpoint) == 0) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE,
		    "ddm_check_for_svm(): succeeded on %s\n",
		    mountpoint);

		return (0);
	}

	DDM_DEBUG(DDM_DBGLVL_INFO,
	    "ddm_check_for_svm(): failed on %s\n",
	    mountpoint);

	return (-1);
}

/*
 * Function:	ddm_start_svm
 * Description: calls _svm_start to get a root mirror running
 *		if one exists, svm_info will be propagated.
 *
 * Scope:	public
 * Parameters:  mountpoint - non-NULL mount string
 * 		svm - initialized svm_info structure
 *		flag - flag to determine conversion of db
 *
 * Return:	DDM_SUCCESS - SVM started successfully
 *		DDM_FAILURE - SVM couldn't be started
 */

int
ddm_start_svm(char *mountpoint, svm_info_t **svm, int flag)
{
	int 	ret;

	/*
	 * Start the SVM on the mounted device.
	 */
	if ((ret = (*_svm_start)(mountpoint, svm, flag)) != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_start_svm(): failed with %d\n", ret);

		return (DDM_FAILURE);
	}

	/*
	 * Check what was returned from svm_start to make sure
	 * the device has not changed locations
	 * Use ddm_map_to_effective_dev()
	 */

	ddm_convert_svminfo_if_remapped(*svm, mountpoint);

	if ((*svm != NULL) && ((*svm)->count > 0)) {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_start_svm(): SVM started on %s\n",
		    mountpoint);
	} else {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_start_svm(): SVM started, no root mirr. found on %s\n",
		    mountpoint);
	}

	return (0);
}

/*
 * Function:	ddm_stop_svm
 * Description: stops the metadevice
 * Scope:	public
 * Parameters:
 *
 * Return:	DDM_SUCCESS - successful
 *		DDM_FAILURE - not successful
 *
 */
int
ddm_stop_svm(void)
{
	int ret;

	if ((ret = (*_svm_stop)()) != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_stop_svm(): failed with %d\n", ret);

		return (DDM_FAILURE);
	}

	DDM_DEBUG(DDM_DBGLVL_INFO,
	    "ddm_stop_svm(): succeeded\n");

	return (DDM_SUCCESS);
}

/*
 * Function:	ddm_start_svm_and_get_root_comps()
 *
 * Description:	Start SVM, then get physical components of root SVM metadevice
 *		and add them to the nvlist of attributes
 *
 * Parameters:
 *	char		*md_name - /dev/md/dsk/<md_name> metadevice name
 *	nvlist_t	*attr - nvlist of attributes
 *
 * Return:
 *	int	DDM_SUCCESS - finished successfully
 *		DDM_FAILURE - failed
 * Scope:
 *	public
 *
 * Algorithm:
 *		[1] Look for valid SVM database on mntpnt
 *		[2] If valid database found, start SVM
 *		[3] If root on SVM device, add root metadevice components
 *		    to the list of attributes
 * Pre-requisities:
 *		[1] attribute list must already exist
 */
int
ddm_start_svm_and_get_root_comps(char *slice, char *mntpnt, nvlist_t *attr)
{
	svm_info_t 	*svminfo;
	char		*md_name;
	char		**md_comps;
	uint_t		md_num;

	/*
	 * if attributes already present, don't discover them
	 * again
	 */

	if ((nvlist_lookup_string(attr, TD_SLICE_ATTR_MD_NAME, &md_name)
	    == 0) ||
	    (nvlist_lookup_string_array(attr, TD_SLICE_ATTR_MD_COMPS, &md_comps,
	    &md_num) == 0)) {

		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_start_svm_and_get_root_comps(): "
		    "SVM already discovered for %s\n", slice);
	}

	/* allocate smv_info_t structure */

	svminfo = ddm_svm_alloc();

	/* look for SVM devices on the mounted rootdir */

	if (ddm_check_for_svm(mntpnt) == 0) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE,
		    "ddm_start_svm_and_get_root_comps(): "
		    "Valid SVM database found on %s\n", slice);

		if (ddm_start_svm(mntpnt, &svminfo, SVM_DONT_CONV) == 0) {

			DDM_DEBUG(DDM_DBGLVL_NOTICE,
			    "ddm_start_svm_and_get_root_comps(): "
			    "SVM started\n");

			/*
			 * If svm->count is > 0, then the volume
			 * in question is a mirror. Otherwise,
			 * the root does not have a mirror but
			 * has some other kind of metadevice.
			 * if it is a mirror, add it to the svmlist
			 */
			if (svminfo->count > 0) {
				int rc;

				DDM_DEBUG(DDM_DBGLVL_NOTICE,
				    "ddm_start_svm_and_get_root_comps(): "
				    "Root md %s found\n", svminfo->root_md);

				for (rc = 0; (svminfo->md_comps[rc] != NULL) &&
				    (rc < svminfo->count); rc++) {

					DDM_DEBUG(DDM_DBGLVL_NOTICE,
					    "ddm_start_svm_and_get_root_comps()"
					    ": md submirror %s\n",
					    svminfo->md_comps[rc]);
				}
			}
		} else {
			DDM_DEBUG(DDM_DBGLVL_NOTICE,
			    "ddm_start_svm_and_get_root_comps(): "
			    "Couldn't start SVM\n");

			/* it failed, but add it to the svm list anyway */
			if (svminfo->count > 0) {
				int rc;

				DDM_DEBUG(DDM_DBGLVL_NOTICE,
				    "ddm_start_svm_and_get_root_comps(): "
				    "Root md %s found\n", svminfo->root_md);

				for (rc = 0; (svminfo->md_comps[rc] != NULL) &&
				    (rc < svminfo->count); rc++) {

					DDM_DEBUG(DDM_DBGLVL_NOTICE,
					    "ddm_start_svm_and_get_root_comps()"
					    ": md submirror %s\n",
					    svminfo->md_comps[rc]);
				}
			}

			/* release smv_info_t structure */

			ddm_svm_free(svminfo);
			return (0);
		}
	}

	/*
	 * if the root slice is part of mirrored root,
	 * add information to the list of slice
	 * attributes
	 */
	if (svminfo->count > 0) {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_start_svm_and_get_root_comps(): "
		    "Adding attributes into nvlist\n");

		nvlist_add_string(attr, TD_SLICE_ATTR_MD_NAME,
		    svminfo->root_md);

		nvlist_add_string_array(attr, TD_SLICE_ATTR_MD_COMPS,
		    svminfo->md_comps, (uint_t)svminfo->count);
	}

	/* release smv_info_t structure */

	ddm_svm_free(svminfo);

	return (DDM_SUCCESS);
}

/*
 * Function:	ddm_get_svm_comps_from_md_name()
 *
 * Description:	Get physical components of SVM metadevice and
 *		add them to the nvlist of attributes
 *
 * Parameters:
 *	char		*md_name - /dev/md/dsk/<md_name> metadevice name
 *	nvlist_t	*attr - nvlist of attributes
 *	char		*mntpnt - alternate root mountpoint
 *
 * Return:
 *	int	DDM_SUCCESS - finished successfully
 *		DDM_FAILURE - failed
 * Scope:
 *	public
 *
 * Pre-requisities:
 *		[1] SVM must be running (started by ddm_svm_start())
 *		[2] attr list must already exist
 */
int
ddm_get_svm_comps_from_md_name(char *md_name, char *mntpnt, nvlist_t *attr)
{
	char		device[MAXPATHLEN];
	svm_info_t 	*svminfo;

	/* sanity checking */
	assert(md_name != NULL);

	if (strncmp(md_name, "/dev/md/dsk/", strlen("/dev/md/dsk/")) != 0) {
		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_get_svm_comps_from_md_name():"
		    " %s is not valid metadevice", md_name);

		return (DDM_FAILURE);
	}

	svminfo = ddm_svm_alloc();
	device[0] = '\0';

	if ((*_svm_get_components)(md_name, &svminfo) != 0) {

		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_get_svm_comps_from_md_name(): "
		    "Can't get SVM components for %s", md_name);

		/* release SVM information */

		ddm_svm_free(svminfo);
		return (DDM_FAILURE);
	}

	/*
	 * Check what was returned to make sure
	 * the device has not changed locations
	 * Use _map_to_effective_dev()
	 */

	ddm_convert_svminfo_if_remapped(svminfo, mntpnt);

	/*
	 * add information about metadevice to the attribute list
	 */

	if (svminfo->count > 0) {
		nvlist_add_string(attr, TD_OS_ATTR_MD_NAME,
		    md_name);

		nvlist_add_string_array(attr, TD_OS_ATTR_MD_COMPS,
		    svminfo->md_comps, (uint_t)svminfo->count);
	}

	/* release SVM information */

	ddm_svm_free(svminfo);

	return (DDM_SUCCESS);
}

/*
 * ddm_slice_inuse_by_svm()
 */

ddm_err_t
ddm_slice_inuse_by_svm(char *slice, nvlist_t *attrs, int *errp)
{
	char		*tmp_mntpnt;
	char		mkdir_template[] = DDM_MKDTEMP_TEMPLATE;

	DDM_DEBUG(DDM_DBGLVL_INFO,
	    "-> ddm_slice_inuse_by_svm(): \n");

	*errp = DDM_SUCCESS;

	/* create temporary mount point */

	tmp_mntpnt = mkdtemp(mkdir_template);

	if (tmp_mntpnt == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_slice_inuse_by_svm(): mkdtemp() failed\n");

		return (DDM_FAILURE);
	} else {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_slice_inuse_by_svm(): tmp mountpoint %s created\n",
		    tmp_mntpnt);
	}

	/* try to mount the slice on temporary mountpoint */

	if (ddm_ufs_mount(slice, tmp_mntpnt, "-r") < 0) {

		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_slice_inuse_by_svm(): Slice mount failed\n");

		return (DDM_FAILURE);
	} else {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_slice_inuse_by_svm(): Slice %s mounted\n", slice);
	}

	/*
	 * check if slice is part of SVM
	 * If it is, add appropriate attributes to the
	 * attribute list
	 */

	if (ddm_start_svm_and_get_root_comps(slice, tmp_mntpnt, attrs)
	    != DDM_SUCCESS) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_slice_inuse_by_svm(): Unable to run SVM\n");
	}

	/* unmount temporary mounted slice */

	(void) ddm_ufs_umount(tmp_mntpnt);

	DDM_DEBUG(DDM_DBGLVL_INFO,
	    "ddm_slice_inuse_by_svm(): Slice %s unmounted\n", slice);

	/* delete temporary mountpoint */

	if (rmdir(tmp_mntpnt) != 0) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE,
		    "ddm_slice_inuse_by_svm(): Couldn't delete temp dir %s\n",
		    tmp_mntpnt);
	} else {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_slice_inuse_by_svm(): Temp dir %s deleted\n",
		    tmp_mntpnt);
	}

	DDM_DEBUG(DDM_DBGLVL_INFO, "<- ddm_slice_inuse_by_svm(): \n");

	return (DDM_SUCCESS);
}
