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
 * Module:	svc_flash_lf.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for manipulating archives retrieved from
 *	NFS servers.
 *
 *	The mechanisms used to manipulate archives retrieved from NFS servers
 *	are a superset of those used for archives retrieved from local files.
 *	The only difference is that, in the NFS case, we need to mount the
 *	filesystem containing the archive before we can process it, and we
 *	need to unmount said filesystem when we're done.  Mounting and
 *	unmounting is handled here; everything else is passed off to the
 *	local file code.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

typedef struct {
	char		*mountpt;
	FileData	filedata;
} NFSData;
#define	NFSDATA(flar)	((NFSData *)flar->data)
#define	NFSFDATA(flar)	(&(((NFSData *)flar->data)->filedata))

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARNFSOpen
 * Description:	The NFS-specific archive opening routine.  This routine mounts
 *		the specified archive using NFS, and opens it.  Note that we
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
FLARNFSOpen(FlashArchive *flar)
{
	char *mountpt;
	char *cmd;
	int rc;

	/* Make the mount point */
	if (!(mountpt = tempnam("/tmp", "flar")) || mkdir(mountpt, S_IRWXU)) {
		write_notice(ERRMSG, MSG0_FLASH_CANT_MAKE_MOUNTPOINT);

		if (mountpt) {
			free(mountpt);
		}

		return (FlErrCouldNotMount);
	}

	/* Mount the archive */
	cmd = xmalloc(52 + count_digits(flar->spec.NFSLoc.retry) +
	    strlen(flar->spec.NFSLoc.host) +
	    strlen(flar->spec.NFSLoc.path) + strlen(mountpt));
	sprintf(cmd, "mount -F nfs -o retry=%d %s:%s %s 2> /dev/null " \
	    "> /dev/null",
	    flar->spec.NFSLoc.retry,
	    flar->spec.NFSLoc.host,
	    flar->spec.NFSLoc.path,
	    mountpt);
	rc = system(cmd);
	free(cmd);

	if (rc) {
		write_notice(ERRMSG, MSG0_FLASH_CANT_MOUNT_NFS,
		    flar->spec.NFSLoc.host, flar->spec.NFSLoc.path);
		free(mountpt);
		return (FlErrCouldNotMount);
	}

	/* Save NFS-specific data */
	flar->data = xcalloc(sizeof (NFSData));
	NFSDATA(flar)->mountpt = mountpt;

	/*
	 * We have now mounted the archive on the mount point.  Let the
	 * local_file code take care of the rest of the open.
	 */
	return (FLARLocalFileOpenPriv(flar, NFSFDATA(flar),
				    NFSDATA(flar)->mountpt));
}

/*
 * Name:	FLARNFSReadLine
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
FLARNFSReadLine(FlashArchive *flar, char **bufptr)
{
	/*
	 * There's nothing special about reading lines from NFS-mounted
	 * archives, so let the local_file code do it.
	 */
	return (FLARLocalFileReadLinePriv(flar, NFSFDATA(flar), bufptr));
}

/*
 * Name:	FLARNFSExtract
 * Description:	The NFS-specific archive extraction routine.  This routine
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
FLARNFSExtract(FlashArchive *flar, FILE *xfp, TCallback *cb, void *data)
{
	return (FLARLocalFileExtractPriv(flar, NFSFDATA(flar), xfp, cb, data));
}

/*
 * Name:	FLARNFSClose
 * Description:	The NFS-specific archive closing routine.  First, we close
 *		the archive using the standard local file close routine.
 *		Next, we unmount the filesystem containing the archive.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive was not open
 */
FlashError
FLARNFSClose(FlashArchive *flar)
{
	FlashError status;
	int rc;
	char *cmd;

	/* Close the archive */
	if ((status = FLARLocalFileClosePriv(flar, NFSFDATA(flar))) !=
								FlErrSuccess) {
		return (status);
	}

	/* Unmount the filesystem containing the archive */
	cmd = (char *)xmalloc(35 + strlen(NFSDATA(flar)->mountpt));
	sprintf(cmd, "umount %s 2> /dev/null > /dev/null",
	    NFSDATA(flar)->mountpt);
	rc = system(cmd);
	free(cmd);

	if (rc) {
		write_notice(ERRMSG, MSG0_FLASH_CANT_UMOUNT_NFS,
		    flar->spec.NFSLoc.path, flar->spec.NFSLoc.host);
		return (FlErrCouldNotUmount);
	}

	rmdir(NFSDATA(flar)->mountpt);

	/* We're done */
	free(NFSDATA(flar)->mountpt);
	free(flar->data);
	flar->data = NULL;

	return (FlErrSuccess);
}
