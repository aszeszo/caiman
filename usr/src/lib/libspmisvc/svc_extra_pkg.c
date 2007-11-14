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

#pragma ident	"@(#)svc_extra_pkg.c	1.3	07/10/09 SMI"


/*
 * Module:	svc_extra_pkg.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for installing additional packages specified
 *	with a non-wos location in the Custom Jumpstart profile.
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

static int	_add_ext_pkg(char *, char *, PkgFlags *, char *);
static int	_set_extpkg_admin_file(char *);
static Module *	_get_wos_package(Module *, char *);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	InstallExtraPkgs
 * Description:	This function adds the extra package specified in the custom
 *		Jumpstart profile.
 * Scope:	internal
 * Arguments:	Profile	*
 * Returns:	D_OK
 */
int
InstallExtraPkgs(Profile *prop)
{
	char	*file;
	PackageStorage  prev_pkg, *expkg;
	PkgFlags	pkg_params;
	char	*temp;
	Module		*softmedia = get_default_media();

	if (get_machinetype() == MT_CCLIENT)
		return (D_OK);

	/*
	 * If there are no extra packages to be installed return D_OK
	 */
	if (EXTRA_SOFT_PACKAGE(prop) == NULL) {
		return (D_OK);
	}

	/*
	 * Modify admin file for extra package installation
	 */
	file = getset_admin_file(NULL);

	_set_extpkg_admin_file(file);

	_setup_pkg_params(&pkg_params);

	/* print the Extra packages being installed */
	write_status(LOGSCR, LEVEL0, MSG0_EXTRA_PACKAGE_INSTALL_NOW);

	bzero(&prev_pkg, sizeof (PackageStorage));

	WALK_LIST(expkg, EXTRA_SOFT_PACKAGE(prop)) {
		/*
		 * If a wos package is specified, do not install and
		 * log in to the install/upgrade log
		 */
		if (_get_wos_package(softmedia, expkg->name) != NULL) {
			write_notice(WARNMSG, MSG1_WOS_PKG, expkg->name);
			continue;
		}
		/*
		 * If the location is not specified, fill it up with the
		 * previous location
		 */
		if (expkg->type == NO_LOCATION) {
			/*
			 * If this package doesn't have a location and there
			 * is no previous location, we cannot proceed with
			 * this package. If it is a WOS package, it would have
			 * been taken care as the part of regular pkgadd.
			 * If not log in the install/upgrade log as an anomoly
			 */
			if (prev_pkg.type == 0) {
				write_status(LOGSCR, LEVEL0,
					MSG1_SKIP_PKG, expkg->name);
				continue;
			}
			/*
			 * Copy the location and type from the previous package
			 * Keep the package name
			 */
			temp = strdup(expkg->name);
			memcpy(&expkg->PkgLocation, &prev_pkg.PkgLocation,
				sizeof (FLARLocSpec));
			expkg->type = prev_pkg.type;
			strcpy(expkg->name, temp);
			free(temp);
		} else {
			/*
			 * save the current package for future use
			 */
			memcpy(&prev_pkg, expkg, sizeof (PackageStorage));
		}

		switch (expkg->type) {
		    case NFS_LOCATION:
			install_nfs_package(expkg, &pkg_params);
			break;
		    case LOCALFILE_LOCATION:
			install_lf_package(expkg, &pkg_params);
			break;
		    case HTTP_LOCATION:
			install_http_package(expkg, &pkg_params);
			break;
		    case LOCALDEVICE_LOCATION:
			install_ld_package(expkg, &pkg_params);
			break;
		    default:
			break;
		}
	}
	return (D_OK);
}

/*
 * Name:	install_nfs_package
 * Description:	The package is available in a NFS server.
 *		This routine mounts the specified directory using NFS, and
 *		call pkgadd to install. We unmount the directory
 *		after the package is installed
 * Scope:	internal
 * Arguments:	PackageStorage * - The package information
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_nfs_package(PackageStorage *pkg, PkgFlags *pkg_params)
{
	char *mountpt;
	char *cmd;
	int rc;
	FLARLocSpec *pkgloc;
	char	*pkg_dir;

	/* Make the mount point */
	if (!(mountpt = tempnam("/tmp", "extra_pkg")) ||
		mkdir(mountpt, S_IRWXU)) {
		write_notice(ERRMSG, MSG0_CANT_MAKE_MOUNTPOINT_PKG);

		if (mountpt) {
			free(mountpt);
		}

		return;
	}

	/* Mount the archive */
	pkgloc = &pkg->PkgLocation;
	cmd = xmalloc(52 + count_digits(pkgloc->NFSLoc.retry) +
	    strlen(pkgloc->NFSLoc.host) +
	    strlen(pkgloc->NFSLoc.path) + strlen(mountpt));
	sprintf(cmd, "mount -F nfs -o retry=%d %s:%s %s 2> /dev/null " \
	    "> /dev/null",
	    pkgloc->NFSLoc.retry,
	    pkgloc->NFSLoc.host,
	    pkgloc->NFSLoc.path,
	    mountpt);
	rc = system(cmd);
	free(cmd);

	if (rc) {
		write_notice(ERRMSG, MSG2_CANT_MOUNT_NFS_PKG,
		    pkgloc->NFSLoc.host, pkgloc->NFSLoc.path);
		free(mountpt);
		return;
	}

	if (streq(pkg->name, "all")) {
		write_status(LOG, LEVEL1, MSG2_EXTRA_PKG_ALL,
			pkgloc->NFSLoc.host, "nfs");
	} else {
		write_status(LOG, LEVEL1, MSG3_EXTRA_PKG,
			pkg->name, pkgloc->NFSLoc.host, "nfs");
	}

	_add_ext_pkg(pkg->name, mountpt, pkg_params, NULL);

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
		    pkgloc->NFSLoc.path, pkgloc->NFSLoc.host);
		return;
	}
}

/*
 * Name:	install_ld_package
 * Description:	The package is available in a local device.
 *		This routine mounts the specified local device, and
 *		call pkgadd to install. We unmount the local device
 *		after the package is installed
 * Scope:	internal
 * Arguments:	PackageStorage * - The package information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_ld_package(PackageStorage *pkg, PkgFlags *pkg_params)
{
	char *mountpt;
	char *fstype;
	char *prev_mnt;
	char *prev_fstype;
	char *cmd;
	int owner;
	int ret;
	FLARLocSpec *pkgloc;
	char *pkg_dir;

	pkgloc = &pkg->PkgLocation;

	/* see if it's already mounted */
	if (is_local_device_mounted(pkgloc->LocalDevice.device, NULL,
	    &prev_mnt, &prev_fstype)) {
		/*
		 * we are not the owner, so say so.  This is so we
		 * don't inadvertantly umount the filesystem out from
		 * other archives waiting to be read
		 */
		owner = FALSE;

		/* see if fstype lines up with what user said */
		if (pkgloc->LocalDevice.fstype && prev_fstype &&
		    (strcmp(pkgloc->LocalDevice.fstype, prev_fstype) != 0)) {
			write_notice(ERRMSG, MSG1_CANT_MOUNT_DEVICE_PKG,
				    pkgloc->LocalDevice.device);
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
			write_notice(ERRMSG, MSG0_CANT_MAKE_MOUNTPOINT_PKG);

			if (mountpt) {
				free(mountpt);
			}

			return;
		}

		if (pkgloc->LocalDevice.fstype) {
			/* The user specified a filesystem type */
			if (try_mount_local_device(pkgloc->LocalDevice.device,
			    mountpt, pkgloc->LocalDevice.fstype) < 0) {
				write_notice(ERRMSG, MSG1_CANT_MOUNT_DEVICE_PKG,
				    pkgloc->LocalDevice.device);
				return;
			} else {
				fstype = pkgloc->LocalDevice.fstype;
			}

		} else {
			/* No specified type, so try UFS then HSFS */
			if (try_mount_local_device(pkgloc->LocalDevice.device,
			    mountpt, "ufs") < 0) {
				if (try_mount_local_device(
				    pkgloc->LocalDevice.device,
				    mountpt,
				    "hsfs") < 0) {
					write_notice(ERRMSG,
					    MSG1_CANT_MOUNT_DEVICE_PKG,
					    pkgloc->LocalDevice.device);
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
			    pkgloc->LocalDevice.device, fstype);
		}
	}

	if (streq(pkg->name, "all")) {
		write_status(LOG, LEVEL1, MSG2_EXTRA_PKG_ALL,
			pkgloc->LocalDevice.device, "local_device");
	} else {
		write_status(LOG, LEVEL1, MSG3_EXTRA_PKG,
			pkg->name, pkgloc->LocalDevice.device, "local_device");
	}

	pkg_dir = (char *)xmalloc(strlen(mountpt) +
		strlen(pkgloc->LocalDevice.path) + 2);
	sprintf(pkg_dir, "%s/%s", mountpt, pkgloc->LocalDevice.path);
	_add_ext_pkg(pkg->name, pkg_dir, pkg_params, NULL);
	free(pkg_dir);

	/*
	 * Only try and unmount the filesystem if we were the one who mounted
	 * it.
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
			    pkgloc->LocalDevice.device);
			return;
		}

		rmdir(mountpt);
		free(mountpt);
	}
}

/*
 * Name:	install_lf_package
 * Description:	The package is available in a local diretcory
 *		This routine calls pkgadd to install the local file package.
 * Scope:	internal
 * Arguments:	PackageStorage * - The package information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_lf_package(PackageStorage *pkg, PkgFlags *pkg_params)
{
	if (streq(pkg->name, "all")) {
		write_status(LOG, LEVEL1, MSG2_EXTRA_PKG_ALL,
			pkg->PkgLocation.LocalFile.path, "local_file");
	} else {
		write_status(LOG, LEVEL1, MSG3_EXTRA_PKG,
			pkg->name, pkg->PkgLocation.LocalFile.path,
				"local_file");
	}

	_add_ext_pkg(pkg->name, pkg->PkgLocation.LocalFile.path,
		pkg_params, NULL);
}

/*
 * Name:	install_http_package
 * Description:	The package is available in a HTTP server.
 *		This routine mounts the specified directory using NFS, and
 *		call pkgadd to install. We unmount the directory at the caller
 *		once all the packages are installed
 * Scope:	internal
 * Arguments:	PackageStorage * - The package information
 *		admin - The admin file to be used
 *		pkgparams - The default package parameters
 * Returns:	D_OK if successful
 *		D_FAIL if there is an error
 */

int
install_http_package(PackageStorage *pkg, PkgFlags *pkg_params)
{
	char	*path;
	char	*proxy;
	FLARLocSpec	*pkgloc;

	pkgloc = &pkg->PkgLocation;

	if (pkgloc->HTTP.url->host == NULL ||
	    pkgloc->HTTP.url->path == NULL) {
		/* Error Message */
		return;
	}

	if (streq(pkg->name, "all")) {
		write_status(LOG, LEVEL1, MSG2_EXTRA_PKG_ALL,
			pkgloc->HTTP.url->host, "http");
	} else {
		write_status(LOG, LEVEL1, MSG3_EXTRA_PKG,
			pkg->name, pkgloc->HTTP.url->host, "http");
	}

	path = xmalloc(strlen(pkgloc->HTTP.url->host) +
	    sizeof (pkgloc->HTTP.url->port) +
		strlen(pkgloc->HTTP.url->path) + 10);

	sprintf(path, "http://%s:%d%s", pkgloc->HTTP.url->host,
	    pkgloc->HTTP.url->port, pkgloc->HTTP.url->path);

	if (pkgloc->HTTP.proxyhost != NULL) {
		proxy = xmalloc(strlen(pkgloc->HTTP.proxyhost)
			+ sizeof (pkgloc->HTTP.proxyport) + 2);
		sprintf(proxy, "%s:%d", pkgloc->HTTP.proxyhost,
			pkgloc->HTTP.proxyport);
		_add_ext_pkg(pkg->name, path, pkg_params, proxy);
		free(proxy);
	} else {
		_add_ext_pkg(pkg->name, path, pkg_params, NULL);
	}
	free(path);
}

/*
 * Function:	_add_ext_pkg
 * Description:	Adds the package specified by "pkgdir", using the command line
 *		arguments specified by "pkg_params".  "prod_dir" specifies the
 *		location of the package to be installed. Has both an interactive
 *		and non-interactive mode.
 * Scope:	private
 * Parameters:	pkg_dir		- directory containing package
 *		pkg_params	- packaging command line arguments
 *		prod_dir	- pathname for package to be installed
 * Returns	NOERR		- successful
 *		ERROR		- Exit Status of pkgadd
 */
static int
_add_ext_pkg(char *pkg_inst,
    char *prod_dir,
    PkgFlags *pkg_params,
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
	int	spool = FALSE;

	if (GetSimulation(SIM_ANY)) {
		return (SUCCESS);
	}

	/* set up pipes to collect output from pkgadd */
	if ((pipe(fdout) == -1) || (pipe(fderr) == -1))
		return (ERROR);

	if ((pkg_params->notinteractive == 0) && (pipe(fdin) == -1))
		return (ERROR);

	if ((pid = fork()) == 0) {
		/*
		 * set stderr and stdout to pipes; set stdin if interactive
		 */
		if (pkg_params->notinteractive == 0)
			(void) dup2(fdin[0], 0);

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
		cmdline[n++] = "/usr/sbin/pkgadd";

		/* use pkg_params to set command line */
		if (pkg_params != NULL) {
			if (pkg_params->spool != NULL) {
				spool = TRUE;
				n = 0;
				cmdline[n++] = "/usr/bin/pkgtrans";
				cmdline[n++] = "-o";
				if (prod_dir != NULL)
					cmdline[n++] = prod_dir;
				else
					cmdline[n++] = "/var/spool/pkg";

				if (pkg_params->basedir != NULL) {
					(void) snprintf(buf, sizeof (buf)-1,
						"%s/%s",
						pkg_params->basedir,
						pkg_params->spool);
					cmdline[n++] = buf;
				} else
					cmdline[n++] = pkg_params->spool;
			} else {
				if (pkg_params->accelerated == 1)
					cmdline[n++] = "-I";
				if (pkg_params->silent == 1)
					cmdline[n++] = "-S";
				if (pkg_params->checksum == 1)
					cmdline[n++] = "-C";
				if (pkg_params->basedir != NULL) {
					cmdline[n++] = "-R";
					cmdline[n++] = pkg_params->basedir;
				}
				if (getset_admin_file(NULL) != NULL) {
					cmdline[n++] = "-a";
					cmdline[n++] =
					    (char *)getset_admin_file(NULL);
				}
				if (pkg_params->notinteractive == 1)
					cmdline[n++] = "-n";
			}
		} else {
			if (getset_admin_file(NULL) != NULL) {
				cmdline[n++] = "-a";
				cmdline[n++] = (char *) getset_admin_file(NULL);
			}
		}

		if (proxy != NULL && spool == FALSE) {
			cmdline[n++] = "-x";
			cmdline[n++] = proxy;
		}

		if (prod_dir != NULL && spool == FALSE) {
			cmdline[n++] = "-d";
			cmdline[n++] = prod_dir;
		}

		cmdline[n++] = pkg_inst;
		cmdline[n++] = (char *) 0;

		(void) sigignore(SIGALRM);
		(void) execv(cmdline[0], cmdline);
		write_notice(ERROR, MSG0_PKGADD_EXEC_FAILED);

		return (ERROR);

	} else if (pid == -1) {
		if (pkg_params->notinteractive == 0)
			(void) close(fdin[0]);

		(void) close(fdout[1]);
		(void) close(fdout[0]);
		(void) close(fderr[1]);
		(void) close(fderr[0]);
		return (ERROR);
	}

	if (pkg_params->notinteractive == 0) {
		(void) close(fdin[0]);
		(void) close(fdin[1]);
	} else {
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
	}

	(void) close(fdout[0]);
	(void) close(fdout[1]);
	(void) close(fderr[0]);
	(void) close(fderr[1]);

	return (WEXITSTATUS(status_loc) == 0 ? NOERR : ERROR);
}

/*
 * Function:	_set_extpkg_admin_file
 * Description: Set up the new admin file to be used for installing extra
 *		packages specified by package keyword
 * Scope:	private
 * Parameters:	filename    - user supplied file name to use for admin file
 *		NULL if temporary file is desired.
 * Returns	NOERR		- successful
 *		ERR_INVALID - 'filename' can't be opened for writing
 *		ERR_NOFILE  - 'filename' was NULL and a temporary filename
 *		could not be created
 *		ERR_SAVE    - call to getset_admin_file() to save 'filename'
 *		failed
 */
static int
_set_extpkg_admin_file(char *filename)
{
	FILE	*fp;
	static char tmpname[] = "/tmp/pkgXXXXXX";

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("admin_write");
#endif

	if (filename == (char *)NULL) {
		(void) mktemp(tmpname);
		if (tmpname[0] == '\0')
			return (ERR_NOFILE);

		filename = tmpname;
	}
	/* if not simulating execution, write the file */
	if (!GetSimulation(SIM_EXECUTE)) {
		fp = fopen(filename, "w");
		if (fp == (FILE *)0)
			return (ERR_INVALID);

		(void) fprintf(fp, "mail=%s\n", "");
		(void) fprintf(fp, "instance=%s\n", "overwrite");
		(void) fprintf(fp, "partial=%s\n", "nocheck");
		(void) fprintf(fp, "runlevel=%s\n", "nocheck");
		(void) fprintf(fp, "idepend=%s\n", "nocheck");
		(void) fprintf(fp, "rdepend=%s\n", "quit");
		(void) fprintf(fp, "space=%s\n", "nocheck");
		(void) fprintf(fp, "setuid=%s\n", "nocheck");
		(void) fprintf(fp, "conflict=%s\n", "nocheck");
		(void) fprintf(fp, "action=%s\n", "nocheck");
		(void) fprintf(fp, "basedir=%s\n", "");
		(void) fclose(fp);

		/* set pointer to adminfile for future use */
		if (getset_admin_file(filename) == NULL)
			return (ERR_SAVE);
	}

	return (SUCCESS);
}

/*
 * _get_wos_package()
 *	finds the module that owns the package
 *
 * Parameters:	mod	[RW] - pointer to Module structure
 *		name	[RO] - pointer to name to search for
 *
 * Return:	mod 	- set to matching package or NULL on failure
 *
 * Status: 	private
 *
 * Note:	recursive
 *
 */
static Module *
_get_wos_package(Module *mod, char *name)
{
	Modinfo *mi;
	Module	*child;

	if (mod == NULL || name == NULL)
		return (NULL);

	/*
	 * Do a depth-first search of the module tree, marking
	 * modules appropriately.
	 */
	mi = mod->info.mod;
	if ((mod->type == PACKAGE) && streq(mi->m_pkgid, name))
		return (mod);

	child = mod->sub;
	while (child) {
		mod = _get_wos_package(child, name);
		if (mod != NULL)
			return (mod);
		child = child->next;
	}
	return (NULL);
}
