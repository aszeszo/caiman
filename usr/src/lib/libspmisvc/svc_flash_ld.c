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

#pragma ident	"@(#)svc_flash_ld.c	1.4	07/10/09 SMI"


/*
 * Module:	svc_flash_ld.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for manipulating archives retrieved from
 *	local devices.
 *
 *	The mechanisms used to manipulate archives retrieved from Local Devices
 *	are a superset of those used for archives retrieved from local files.
 *	The only difference is that need to mount the
 *	filesystem containing the archive before we can process it, and we
 *	need to unmount said filesystem when we're done.  Mounting and
 *	unmounting is handled here; everything else is passed off to the
 *	local file code.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/mnttab.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

typedef struct {
	char		*mountpt;
	char		*fullpath;
	int		mount_owner;
	FileData	filedata;
} LDData;
#define	LDDATA(flar)	((LDData *)flar->data)
#define	LDFDATA(flar)	(&(((LDData *)flar->data)->filedata))

/* Local Functions */
static int _try_mount(char *, char *, char *);
static int _is_mount(char *, char *, char **, char **);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARLocalDeviceOpen
 * Description:	The Local Device archive opening routine.  This routine mounts
 *		the specified archive, and opens it.  Note that we
 *		only mount the archive file itself - we do not mount the
 *		directory containing it.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 * Returns:	FlErrSuccess		- The archive was opened successfully
 *		FlErrFileNotFound	- The specified tape device was not
 *					  found
 *		FlErrCouldNotOpen	- The archive, once mounted, could not
 *					  be opened
 *		FlErrCouldNotMount	- The specified filesystem could not
 *					  be mounted
 */
FlashError
FLARLocalDeviceOpen(FlashArchive *flar)
{
	char *mountpt;
	char *fstype;
	char *prev_mnt;
	char *prev_fstype;
	int owner;

	/* see if it's already mounted */
	if (_is_mount(flar->spec.LocalDevice.device, NULL,
	    &prev_mnt, &prev_fstype)) {
		/*
		 * we are not the owner, so say so.  This is so we
		 * don't inadvertantly umount the filesystem out from
		 * other archives waiting to be read
		 */
		owner = FALSE;

		/* see if fstype lines up with what user said */
		if (flar->spec.LocalDevice.fstype && prev_fstype &&
		    (strcmp(flar->spec.LocalDevice.fstype, prev_fstype) != 0)) {
			return (FlErrCouldNotMount);
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
		if (!(mountpt = tempnam("/tmp", "flar")) ||
		    mkdir(mountpt, S_IRWXU)) {
			write_notice(ERRMSG, MSG0_FLASH_CANT_MAKE_MOUNTPOINT);

			if (mountpt) {
				free(mountpt);
			}

			return (FlErrCouldNotMount);
		}

		if (flar->spec.LocalDevice.fstype) {
			/* The user specified a filesystem type */
			if (_try_mount(flar->spec.LocalDevice.device, mountpt,
			    flar->spec.LocalDevice.fstype) < 0) {
				write_notice(ERRMSG, MSG0_FLASH_CANT_MOUNT,
				    flar->spec.LocalDevice.device);
				return (FlErrCouldNotMount);
			} else {
				fstype = flar->spec.LocalDevice.fstype;
			}

		} else {
			/* No specified type, so try UFS then HSFS */
			if (_try_mount(flar->spec.LocalDevice.device, mountpt,
			    "ufs") < 0) {
				if (_try_mount(flar->spec.LocalDevice.device,
				    mountpt,
				    "hsfs") < 0) {
					write_notice(ERRMSG,
					    MSG0_FLASH_CANT_MOUNT,
					    flar->spec.LocalDevice.device);
					return (FlErrCouldNotMount);
				} else {
					fstype = "hsfs";
				}
			} else {
				fstype = "ufs";
			}
		}

		if (get_trace_level() > 0) {
			write_status(LOGSCR, LEVEL1, MSG0_FLASH_MOUNTED_FS,
			    flar->spec.LocalDevice.device, fstype);
		}
	}

	/* Save LocalDevice-specific data */
	flar->data = xcalloc(sizeof (LDData));
	LDDATA(flar)->mount_owner = owner;
	LDDATA(flar)->mountpt = xstrdup(mountpt);
	LDDATA(flar)->fullpath = xmalloc(strlen(mountpt) +
	    strlen(flar->spec.LocalDevice.path) + 2);
	(void) sprintf(LDDATA(flar)->fullpath, "%s/%s", mountpt,
	    flar->spec.LocalDevice.path);
	canoninplace(LDDATA(flar)->fullpath);

	/*
	 * We have now mounted the archive on the mount point.
	 * Let the local_file code take care of the rest of the open.
	 */
	return (FLARLocalFileOpenPriv(flar, LDFDATA(flar),
				    LDDATA(flar)->fullpath));
}

/*
 * Name:	FLARLocalDeviceReadLine
 * Description:	Read a line from the archive.  The line read will be returned
 *		in a statically-allocated buffer that the caller must not
 *		modify.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The opened Flash archive from which to read
 *		bufptr	- [RO, *W]  (char **)
 *			  Where the pointer to the statically-allocated buffer
 *			  containing the read line is returned
 * Returns:	FlErrSuccess	- Read successful, *bufptr points to line
 *		FlErrEndOfFile	- End of File was encountered before the read
 *				  successfully completed
 */
FlashError
FLARLocalDeviceReadLine(FlashArchive *flar, char **bufptr)
{
	/*
	 * There's nothing special about reading lines from Local Device
	 * archives, so let the local_file code do it.
	 */
	return (FLARLocalFileReadLinePriv(flar, LDFDATA(flar), bufptr));
}

/*
 * Name:	FLARLocalDeviceExtract
 * Description:	The Local Defice archive extraction routine.  This routine
 *		sends, in bulk, all of the data remaining in the archive
 *		beyond the current location to the passed stream.  This routine
 *		will return FlErrSuccess if the end of the archive is reached
 *		successfully.  The amount of data read from the archive as
 *		compared to the size of the archive (if any) recorded in the
 *		identification section is not taken into account.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being extracted
 *		xfp	- [RO, *RO] (FILE *)
 *			  The stream to which the archive is to be extracted
 *		cb	- [RO, *RO] (TCallback *)
 *			  The application progress callback
 *		data	- [RO, *RO] (void *)
 *			  Application-specific data to be passed to the callback
 * Returns:	FlErrSuccess	- The archive was extracted successfully
 *		FlErrWrite	- An error occurred trying to write to the
 *				  extraction stream
 */
FlashError
FLARLocalDeviceExtract(FlashArchive *flar, FILE *xfp, TCallback *cb, void *data)
{
	return (FLARLocalFileExtractPriv(flar, LDFDATA(flar), xfp, cb, data));
}

/*
 * Name:	FLARLocalDeviceClose
 * Description:	The Local Device archive closing routine.  First, we close
 *		the archive using the standard local file close routine.
 *		Next, we unmount the filesystem containing the archive.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive was not open
 */
FlashError
FLARLocalDeviceClose(FlashArchive *flar)
{
	FlashError status;
	int rc;
	char *cmd;

	/* Close the archive */
	if ((status = FLARLocalFileClosePriv(flar, LDFDATA(flar))) !=
								FlErrSuccess) {
		return (status);
	}

	/*
	 * Only try and unmount the filesystem if we were the one who mounted it.
	 */
	if (LDDATA(flar)->mount_owner) {
		/*
		 * Unmount the filesystem containing the archive
		 * "umount " + mountpt
		 */
		cmd = (char *)xmalloc(7 + strlen(LDDATA(flar)->mountpt) + 1);
		sprintf(cmd, "umount %s", LDDATA(flar)->mountpt);
		rc = system(cmd);
		free(cmd);
		
		if (rc) {
			write_notice(ERRMSG, MSG0_FLASH_CANT_UMOUNT,
			    flar->spec.LocalDevice.device);
			return (FlErrCouldNotUmount);
		}
		
		rmdir(LDDATA(flar)->mountpt);
	}

	/* We're done */
	free(LDDATA(flar)->mountpt);
	free(LDDATA(flar)->fullpath);
	free(flar->data);
	flar->data = NULL;

	return (FlErrSuccess);
}


/*
 * Name:	try_mount_local_device
 * Description:	Public function which is a wrapper to call _try_mount
 */
int
try_mount_local_device(char *device, char *mountpt, char *fstype)
{
	return (_try_mount(device, mountpt, fstype));
}

/*
 * Name:	is_local_device_mounted
 * Description:	Public function which is a wrapper to call _is_mount
 */
int
is_local_device_mounted(char *old_device, char *old_fstype,
	char **mntpnt, char **fstype)
{
	return (_is_mount(old_device, old_fstype, mntpnt, fstype));
}

/*
 * Name:	_try_mount
 * Description:	Attempt to mount a filesystem using a given filesystem type.
 * Scope:	private
 * Arguments:	device	- [RO, *RO] (char *)
 *			  The device to be mounted
 *		mountpt	- [RO, *RO] (char *)
 *			  Where the device is to be mounted
 *		fstype	- [RO, *RO] (char *)
 *			  The filesystem type for the device
 * Returns:	0	- Mount succeeded
 *		-1	- Mount failed
 */
static int
_try_mount(char *device, char *mountpt, char *fstype)
{
	char *mount_cmd;
	int rc;

	/*
	 * "mount -F " + fstype + " -o ro " + device + " " + mountpt
	 */
	mount_cmd = (char *)xmalloc(9 + strlen(fstype) + 7 + strlen(device) +
	    1 + strlen(mountpt) + 16  + 1);
	(void) sprintf(mount_cmd, "mount -F %s -o ro %s %s >/dev/null 2>&1",
	    fstype, device, mountpt);

	rc = system(mount_cmd);

	free(mount_cmd);

	if (rc) {
		return (-1);
	} else {
		return (0);
	}
}

/*
 * Name:		_is_mount
 * Description:	See if a device is already mounted with the given fstype.
 *		If so, return the mountpoint.
 * Scope:	private
 * Arguments:	old_device	- [RO, *RO] (char *)
 *			  The device to be mounted
 *		old_fstype	- [RO, *RO] (char *)
 *			  The filesystem type for the device
 * Returns:	0 if found, non-zero otherwise.
 *		If found, a pointer pointing to the
 *		mountpoint of the device is placed in *result.
 */
static int
_is_mount(char *old_device, char *old_fstype, char **mntpnt, char **fstype)
{
	struct mnttab mp;
	struct mnttab mpref;
	FILE *fp;
	static char prev_mntpnt[MAXPATHLEN];
	static char prev_fstype[MAXPATHLEN];

	if ((fp = fopen(MNTTAB, "r")) == NULL) {
		return (FALSE);
	}

	(void) memset(&mpref, 0, sizeof (struct mnttab));

	if (old_device != NULL) {
		mpref.mnt_special = old_device;
	}

	if (old_fstype != NULL) {
		mpref.mnt_fstype = old_fstype;
	}

	if (getmntany(fp, &mp, &mpref) == 0) {
		strcpy(prev_mntpnt, mp.mnt_mountp);
		strcpy(prev_fstype, mp.mnt_fstype);
		if (mntpnt != NULL) {
			*mntpnt = prev_mntpnt;
		}
		if (fstype != NULL) {
			*fstype = prev_fstype;
		}
		(void) fclose(fp);
		return (TRUE);
	} else {
		(void) fclose(fp);
		return (FALSE);
	}
}
