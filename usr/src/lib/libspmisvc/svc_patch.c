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



/*
 * Module:	svc_patch.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for installing patches specified
 *	with a location in the Custom Jumpstart profile.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <ulimit.h>
#include <wait.h>
#include <signal.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "spmiapp_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

typedef struct {
	int no_backup;
	int no_validation;
	int ignore_signature;
	char *basedir;
} PatchFlags;

static int	_add_patch(char *, char *, PatchFlags *, char *);
static void	_setup_patch_params(PatchFlags *);
static void	_parse_patch_list(char *);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	InstallPatches
 * Description:	This function installs the patches specified in the custom
 *		Jumpstart profile.
 * Scope:	internal
 * Arguments:	Profile	*
 * Returns:	D_OK
 */
int
InstallPatches(Profile *prop)
{
	char	*file;
	PatchStorage  *patch;
	PatchFlags	patch_params;

	if (get_machinetype() == MT_CCLIENT)
		return (D_OK);

	/*
	 * If there are no patches to be installed return D_OK
	 */
	if (PATCH(prop) == NULL) {
		return (D_OK);
	}

	/*
	 * Modify admin file for extra package installation
	 */
	_setup_patch_params(&patch_params);

	/* print the Patches being installed */
	write_status(LOGSCR, LEVEL0, MSG0_PATCH_INSTALL_NOW);

	WALK_LIST(patch, PATCH(prop)) {
		_parse_patch_list(patch->patch_list);
		switch (patch->type) {
		    case NFS_LOCATION:
			install_nfs_patch(patch, &patch_params);
			break;
		    case LOCALFILE_LOCATION:
			install_lf_patch(patch, &patch_params);
			break;
		    case HTTP_LOCATION:
			install_http_patch(patch, &patch_params);
			break;
		    case LOCALDEVICE_LOCATION:
			install_ld_patch(patch, &patch_params);
			break;
		    default:
			break;
		}
	}
}

/*
 * Name:	install_nfs_patch
 * Description:	The patch is available in a NFS server.
 *		This routine mounts the specified directory using NFS, and
 *		call patchadd to install.
 * Scope:	internal
 * Arguments:	PatchStorage * - The patch information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_nfs_patch(PatchStorage *patch, PatchFlags *patch_params)
{
	char *mountpt;
	char *cmd;
	int rc;
	FLARLocSpec *patchloc;

	/* Make the mount point */
	if (!(mountpt = tempnam("/tmp", "patch")) ||
		mkdir(mountpt, S_IRWXU)) {
		write_notice(ERRMSG, MSG0_CANT_MAKE_MOUNTPOINT_PATCH);

		if (mountpt) {
			free(mountpt);
		}

		return;
	}

	/* Mount the archive */
	patchloc = &patch->PatchLocation;
	cmd = xmalloc(52 + count_digits(patchloc->NFSLoc.retry) +
	    strlen(patchloc->NFSLoc.host) +
	    strlen(patchloc->NFSLoc.path) + strlen(mountpt));
	sprintf(cmd, "mount -F nfs -o retry=%d %s:%s %s 2> /dev/null " \
	    "> /dev/null",
	    patchloc->NFSLoc.retry,
	    patchloc->NFSLoc.host,
	    patchloc->NFSLoc.path,
	    mountpt);
	rc = system(cmd);
	free(cmd);

	if (rc) {
		write_notice(ERRMSG, MSG2_CANT_MOUNT_NFS_PATCH,
		    patchloc->NFSLoc.host, patchloc->NFSLoc.path);
		free(mountpt);
		return;
	}

	write_status(LOG, LEVEL1, MSG2_PATCH_INSTALL,
			patchloc->NFSLoc.host, "nfs");

	_add_patch(patch->patch_list, mountpt, patch_params, NULL);

	/*
	 * Unmount the NFS directory
	 */
	cmd = (char *)xmalloc(35 + strlen(mountpt));
	sprintf(cmd, "umount %s 2> /dev/null > /dev/null", mountpt);
	rc = system(cmd);
	free(cmd);

	rmdir(mountpt);
	free(mountpt);

	if (rc) {
		write_notice(ERRMSG, MSG2_CANT_UMOUNT_NFS,
		    patchloc->NFSLoc.path, patchloc->NFSLoc.host);
		return;
	}

	return (0);
}

/*
 * Name:	install_ld_patch
 * Description:	The patch is available in a local device.
 *		This routine mounts the specified local device, and
 *		call patchadd to install. We unmount the local device
 *		after the patch is installed
 * Scope:	internal
 * Arguments:	PatchStorage * - The patch information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_ld_patch(PatchStorage *patch, PatchFlags *patch_params)
{
	char *mountpt;
	char *fstype;
	char *prev_mnt;
	char *prev_fstype;
	char *cmd;
	int owner;
	int ret;
	FLARLocSpec *patchloc;
	char *patch_dir;

	patchloc = &patch->PatchLocation;

	/* see if it's already mounted */
	if (is_local_device_mounted(patchloc->LocalDevice.device, NULL,
	    &prev_mnt, &prev_fstype)) {
		/*
		 * we are not the owner, so say so.  This is so we
		 * don't inadvertantly umount the filesystem out from
		 * other archives waiting to be read
		 */
		owner = FALSE;

		/* see if fstype lines up with what user said */
		if (patchloc->LocalDevice.fstype && prev_fstype &&
		    (strcmp(patchloc->LocalDevice.fstype, prev_fstype) != 0)) {
			write_notice(ERRMSG, MSG1_CANT_MOUNT_DEVICE_PATCH,
				patchloc->LocalDevice.device);
			return;
		}
		mountpt = prev_mnt;
		fstype = prev_fstype;
	} else {
		/*
		 * we are the owner, and will be the one responsible for
		 * mounting and unmounting the filesystem.
		 */
		owner = TRUE;

		/* Make the mount point */
		if (!(mountpt = tempnam("/tmp", "extra_pkg")) ||
		    mkdir(mountpt, S_IRWXU)) {
			write_notice(ERRMSG, MSG0_CANT_MAKE_MOUNTPOINT_PATCH);

			if (mountpt) {
				free(mountpt);
			}

			return;
		}

		if (patchloc->LocalDevice.fstype) {
			/* The user specified a filesystem type */
			if (try_mount_local_device(patchloc->LocalDevice.device,
			    mountpt, patchloc->LocalDevice.fstype) < 0) {
				write_notice(ERRMSG,
				    MSG1_CANT_MOUNT_DEVICE_PATCH,
				    patchloc->LocalDevice.device);
				return;
			} else {
				fstype = patchloc->LocalDevice.fstype;
			}

		} else {
			/* No specified type, so try UFS then HSFS */
			if (try_mount_local_device(patchloc->LocalDevice.device,
			    mountpt, "ufs") < 0) {
				if (try_mount_local_device(
				    patchloc->LocalDevice.device,
				    mountpt,
				    "hsfs") < 0) {
					write_notice(ERRMSG,
					    MSG1_CANT_MOUNT_DEVICE_PATCH,
					    patchloc->LocalDevice.device);
					return;
				} else {
					fstype = "hsfs";
				}
			} else {
				fstype = "ufs";
			}
		}

		if (get_trace_level() > 0) {
			write_status(LOGSCR, LEVEL1, MSG2_MOUNTED_FS,
			    patchloc->LocalDevice.device, fstype);
		}
	}

	write_status(LOG, LEVEL1, MSG2_PATCH_INSTALL,
		patchloc->LocalDevice.device, "local_device");

	patch_dir = (char *)xmalloc(strlen(mountpt) +
		strlen(patchloc->LocalDevice.path) + 2);
	sprintf(patch_dir, "%s/%s", mountpt, patchloc->LocalDevice.path);
	_add_patch(patch->patch_list, patch_dir, patch_params, NULL);

	/*
	 * Only try and unmount the filesystem if we were the one who
	 * mounted it.
	 */
	if (owner) {
		/*
		 * Unmount the filesystem containing the archive
		 * "umount " + mountpt
		 */
		cmd = (char *)xmalloc(7 + strlen(mountpt) + 1);
		sprintf(cmd, "umount %s", mountpt);
		ret = system(cmd);
		free(cmd);

		if (ret) {
			write_notice(ERRMSG, MSG1_CANT_UMOUNT_DEVICE,
			    patchloc->LocalDevice.device);
			return;
		}

		rmdir(mountpt);
	}

	return (0);
}

/*
 * Name:	install_lf_patch
 * Description:	The patch is available in a local diretcory
 *		This routine calls patchadd to install the local file patch(es).
 * Scope:	internal
 * Arguments:	PatchStorage * - The patch information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_lf_patch(PatchStorage *patch, PatchFlags *patch_params)
{
	write_status(LOG, LEVEL1, MSG2_PATCH_INSTALL,
		patch->PatchLocation.LocalFile.path, "local_file");
	_add_patch(patch->patch_list, patch->PatchLocation.LocalFile.path,
		patch_params, NULL);
}

/*
 * Name:	install_http_patch
 * Description:	The patch is available in a HTTP server.
 *		This routine mounts the specified directory using NFS, and
 *		call patchadd to install.
 * Scope:	internal
 * Arguments:	PatchStorage * - The patch information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_http_patch(PatchStorage *patch, PatchFlags *patch_params)
{
	char	*path;
	char	*proxy;
	FLARLocSpec	*patchloc;

	patchloc = &patch->PatchLocation;

	if (patchloc->HTTP.url->host == NULL ||
	    patchloc->HTTP.url->path == NULL) {
		/* Error Message */
		return;
	}

	path = xmalloc(strlen(patchloc->HTTP.url->host) +
	    sizeof (patchloc->HTTP.url->port) +
		strlen(patchloc->HTTP.url->path) + 10);

	sprintf(path, "http://%s:%d%s", patchloc->HTTP.url->host,
	    patchloc->HTTP.url->port,
		patchloc->HTTP.url->path);

	write_status(LOG, LEVEL1, MSG2_PATCH_INSTALL,
		patchloc->HTTP.url->host, "http");
	if (patchloc->HTTP.proxyhost != NULL) {
		proxy = xmalloc(strlen(patchloc->HTTP.proxyhost)
			+ sizeof (patchloc->HTTP.url->port) + 2);
		sprintf(proxy, "%s:%d", patchloc->HTTP.proxyhost,
			patchloc->HTTP.proxyport);
		_add_patch(patch->patch_list, path, patch_params, proxy);
	} else {
		_add_patch(patch->patch_list, path, patch_params, NULL);
	}
}

/*
 * Function:	_add_patch
 * Description:	Adds the patch(es) specified by "patch_list", using the command
 *		line arguments specified by "patch_params".
 *		"patch_dir" specifies the location of the patches to be
 *		installed. Has both an interactive and non-interactive mode.
 * Scope:	private
 * Parameters:	patch_dir	- directory containing patches
 *		patch_params	- packaging command line arguments
 *		patch_list	- List of patches
 * Returns	NOERR		- successful
 *		ERROR		- Exit Status of pkgadd
 */
static int
_add_patch(char *patch_list,
    char *patch_dir,
    PatchFlags *patch_params,
    char *proxy)
{
	int	pid;
	u_int	status_loc = 0;
	int	options = WNOHANG;
	int	n;
	pid_t	waitstat;
	int	fdout[2];
	int	fderr[2];
	int	fdin[2];
	char	buffer[256];
	char	buf[MAXPATHLEN];
	int	size, nfds;
	struct timeval timeout;
	fd_set	readfds, writefds, execptfds;
	long	fds_limit;
	char	*cmdline[20];

	if (GetSimulation(SIM_ANY)) {
		return (SUCCESS);
	}

	/* set up pipes to collect output from pkgadd */
	if ((pipe(fdout) == -1) || (pipe(fderr) == -1))
		return (ERROR);

	if ((pid = fork()) == 0) {
		/*
		 * set stderr and stdout to pipes; set stdin if interactive
		 */
		(void) dup2(fdout[1], 1);
		(void) dup2(fderr[1], 2);
		(void) close(fdout[1]);
		(void) close(fdout[0]);
		(void) close(fderr[1]);
		(void) close(fderr[0]);

		/* close all file descriptors in child */
		closefrom(3);

		/* build args for pkgadd command line */
		n = 0;
		cmdline[n++] = "/usr/sbin/patchadd";

		/* use patch_params to set command line */
		if (patch_params != NULL) {
			if (patch_params->no_backup == 1)
				cmdline[n++] = "-d";
			if (patch_params->no_validation == 0)
				cmdline[n++] = "-u";
			if (patch_params->ignore_signature == 1)
				cmdline[n++] = "-n";
			if (patch_params->basedir != NULL) {
				cmdline[n++] = "-R";
				cmdline[n++] = patch_params->basedir;
			}
		}

		if (proxy != NULL) {
			cmdline[n++] = "-x";
			cmdline[n++] = proxy;
		}

		if (patch_dir != NULL) {
			cmdline[n++] = "-M";
			cmdline[n++] = patch_dir;
		}

		/*
		 * If patches are listed in the profile as comma separated items
		 * replace the comma with space
		 */
		cmdline[n++] = patch_list;

		cmdline[n++] = (char *) 0;

		(void) sigignore(SIGALRM);
		(void) execv(cmdline[0], cmdline);
		write_notice(ERROR, MSG0_PATCHADD_EXEC_FAILED);

		return (ERROR);

	} else if (pid == -1) {
		(void) close(fdout[1]);
		(void) close(fdout[0]);
		(void) close(fderr[1]);
		(void) close(fderr[0]);
		return (ERROR);
	}

	nfds = (fdout[0] > fderr[0]) ? fdout[0] : fderr[0];
	nfds++;
	timeout.tv_sec = 1;
	timeout.tv_usec = 0;

	do {
		FD_ZERO(&execptfds);
		FD_ZERO(&writefds);
		FD_ZERO(&readfds);
		FD_SET(fdout[0], &readfds);
		FD_SET(fderr[0], &readfds);

		if (select(nfds, &readfds, &writefds,
				&execptfds, &timeout) != -1) {
			if (FD_ISSET(fdout[0], &readfds)) {
				if ((size = read(fdout[0], buffer,
				    sizeof (buffer))) != -1) {
					buffer[size] = '\0';
					write_status_nofmt(LOG,
					    LEVEL0|CONTINUE|FMTPARTIAL,
					    buffer);
				}
			}

			if (FD_ISSET(fderr[0], &readfds)) {
				if ((size = read(fderr[0], buffer,
				    sizeof (buffer))) != -1) {
					buffer[size] = '\0';
					write_status_nofmt(LOG,
					    LEVEL0|CONTINUE|FMTPARTIAL,
					    buffer);
				}
			}
		}

		waitstat = waitpid(pid, (int *)&status_loc, options);
	} while ((!WIFEXITED(status_loc) &&
		!WIFSIGNALED(status_loc)) || (waitstat == 0));

	(void) close(fdout[0]);
	(void) close(fdout[1]);
	(void) close(fderr[0]);
	(void) close(fderr[1]);

	return (WEXITSTATUS(status_loc) == 0 ? NOERR : ERROR);
}

/*
 * Function:	_setup_patch_params
 * Description:	Initialize the patch params structure to be used
 *		during patchadd calls.
 * Scope:	internal
 * Parameters:	params	- non-NULL pointer to the PatchFlags structure to be
 *			  initialized
 * Return:	none
 */
static void
_setup_patch_params(PatchFlags *params)
{
	if (params != NULL) {
		params->no_backup = 0;
		params->no_validation = 0;
		params->ignore_signature = 1;
		params->basedir = get_rootdir();
	}
}

/*
 * Function:	_parse_patch_list
 * Description:	Replace the comma with space from the patch_list string
 * Scope:	internal
 * Parameters:	char *	- non-NULL pointer to the patch_list string
 * Return:	none
 */
static void
_parse_patch_list(char *patch_list)
{
	int comma_found;
	char *ptr;

	comma_found = 1;
	while (comma_found) {
		ptr = strchr(patch_list, ',');
		if (ptr == NULL) {
			comma_found = 0;
		} else {
			*ptr = ' ';
		}
	}
}
