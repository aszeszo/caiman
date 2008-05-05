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
 *	local files.
 *
 *	The functions in this file are separated into two different groups.
 *	First are the Flash internal functions, which are the standard
 *	local_file operations accessed through a FlashOps structure.  The
 *	second set are the Flash private functions.  Flash private functions
 *	are to be called by other Flash internal functions.  They are designed
 *	to allow access to the local_file machinery, but with a few more
 *	knobs to tweak.  For example, the Flash private archive open function
 *	allows the override of the path.  That is, it can use a supplied path
 *	to the archive in preference to the one in the FlashArchive structure.
 *	This is useful for other retrieval methods, such as NFS, which need
 *	90% of the local file infrastructure, but with a tweak here and there.
 *	The Flash private functions allow these tweaks while still exposing
 *	(through their corresponding Flash internal functions) the standard
 *	FlashOps interface.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

#define	LOCAL_LINEBUF_SIZE	1024
#define	LOCAL_READ_CHUNK	MBYTE /* 1MB */

#define	FILEDATA(flar)	((FileData *)flar->data)

/* ------------------ Flash internal functions -------------------- */

/*
 * Name:	FLARLocalFileOpen
 * Description:	The local_file-specific archive opening routine.  It opens
 *		the specified archive.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 * Returns:	FlErrSuccess		- The archive was opened successfully
 *		FlErrFileNotFound	- The specified tape device was not
 *					  found
 *		FlErrCouldNotOpen	- The archive, once mounted, could not
 *					  be opened
 */
FlashError
FLARLocalFileOpen(FlashArchive *flar)
{
	flar->data = xcalloc(sizeof (FileData));

	return (FLARLocalFileOpenPriv(flar, FILEDATA(flar), NULL));
}

/*
 * Name:	FLARLocalFileReadLine
 * Description:	Read a line from a local_file archive.  The line will be
 *		returned in a statically-allocated buffer that the caller must
 *		not modify.
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
FLARLocalFileReadLine(FlashArchive *flar, char **bufptr)
{
	return (FLARLocalFileReadLinePriv(flar, FILEDATA(flar), bufptr));
}

/*
 * Name:	FLARLocalFileExtract
 * Description:	The local_file-specific archive extraction routine.  This
 *		routine sends, in bulk, all of the data remaining in the archive
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
FLARLocalFileExtract(FlashArchive *flar, FILE *xfp, TCallback *cb, void *data)
{
	return (FLARLocalFileExtractPriv(flar, FILEDATA(flar), xfp, cb, data));
}

/*
 * Name:	FLARLocalFileClose
 * Description:	The local_file-specific archive closing routine.  The descriptor
 *		associated with the archive is closed and reset.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive wasn't open
 */
FlashError
FLARLocalFileClose(FlashArchive *flar)
{
	FlashError status;

	if ((status = FLARLocalFileClosePriv(flar, FILEDATA(flar))) ==
								FlErrSuccess) {
		if (flar->data) {
			free(flar->data);
			flar->data = NULL;
		}
	}

	return (status);
}

/* ------------------- Flash private functions -------------------- */

/*
 * Name:	FLARLocalFileOpenPriv
 * Description:	The Flash private local file archive opening routine.  The
 *		path to be used, normally retrieved from the FlashArchive
 *		structure, can be overridden by the `path' argument to this
 *		function.
 * Scope:	Flash private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 *		path	- [RO, *RO] (char *)
 *			  The override path, or NULL if the path is to be
 *			  retrieved from the FlashArchive structure.
 * Returns:	FlErrSuccess		- The archive was opened successfully
 *		FlErrFileNotFound	- The specified tape device was not
 *					  found
 *		FlErrCouldNotOpen	- The archive, once mounted, could not
 *					  be opened
 */
FlashError
FLARLocalFileOpenPriv(FlashArchive *flar, FileData *filedata, char *path)
{

	struct stat64 sbuf;

	/* Use the override, if it's there */
	if (!path) {
		/* No override */
		path = flar->spec.LocalFile.path;
	}

	/* Does the file exist? */
	if (access(path, F_OK) < 0) {
		write_notice(ERRMSG, MSG1_FILE_ACCESS_FAILED, path);
		return (FlErrFileNotFound);
	}

	/* Open it */
	if (!(filedata->file = fopen64(path, "r"))) {
		write_notice(ERRMSG, MSG_OPEN_FAILED, path);
		return (FlErrCouldNotOpen);
	}

	/*
	 * Tell it how big it is, in case the ident section doesn't
	 */
	if ((stat64(path, &sbuf)) != 0) {
		write_notice(ERRMSG, MSG0_FLASH_BAD_ARC_SIZE, path);
		fclose(filedata->file);
		return (FlErrCouldNotOpen);
	}

	if ((flar->ident.arc_size = filedata->fsize = sbuf.st_size) < 1) {
	    write_notice(ERRMSG, MSG0_FLASH_BAD_ARC_SIZE, path);
	    fclose(filedata->file);
	    filedata->fsize = -1;
	    return (FlErrCouldNotOpen);
	}

	flar_set_open(flar);

	return (FlErrSuccess);
}

/*
 * Name:	FLARLocalFileReadLine
 * Description:	Read a line from a local file.  This is the Flash private
 *		version that can be used by any of the retrieval methods that
 *		need to read archives from local files.  The line read will be
 *		returned in a statically-allocated buffer that the caller must
 *		not modify.
 * Scope:	Flash private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The opened Flash archive from which to read
 *		bufptr	- [RO, *W]  (char **)
 *			  Where the pointer to the statically-allocated buffer
 *			  containing the read line is returned
 * Returns:	FlErrSuccess	- Read successful, *bufptr points to line
 *		FlErrEndOfFile	- End of File was encountered before the read
 *				  successfully completed
 */
/*ARGSUSED*/
FlashError
FLARLocalFileReadLinePriv(FlashArchive *flar, FileData *filedata, char **bufptr)
{
	static char *linebuf = NULL;
	static int buflen;
	char *end;

	if (!linebuf) {
		buflen = LOCAL_LINEBUF_SIZE;
		linebuf = xmalloc(buflen);
	}

	if (!fgets(linebuf, buflen, filedata->file)) {
		return (FlErrEndOfFile);
	}

	/*
	 * Grow the buffer and add to the string if we didn't get the
	 * entire thing.
	 */
	while (linebuf[strlen(linebuf) - 1] != '\n') {
		buflen += LOCAL_LINEBUF_SIZE;
		linebuf = xrealloc(linebuf, buflen);
		end = linebuf + strlen(linebuf);

		if (!fgets(end, LOCAL_LINEBUF_SIZE + 1, filedata->file)) {
			return (FlErrEndOfFile);
		}
	}

	/* Whew.  We now have an entire line.  Lose the trailing \n. */
	linebuf[strlen(linebuf) - 1] = '\0';

	*bufptr = linebuf;

	return (FlErrSuccess);
}

/*
 * Name:	FLARLocalFileExtractPriv
 * Description:	The Flash private function used for extracting from an archive
 *		contained in a local file.  This routine sends, in bulk, all of
 *		the data remaining in the archive beyond the current location
 *		to the passed stream.  This routine will return FlErrSuccess
 *		if the end of the archive is reached successfully.  The amount
 *		of data read from the archive as compared to the size of the
 *		archive (if any) recorded in the identification section is not
 *		taken into account.
 * Scope:	Flash private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being extracted
 *		filedata- [RO, *RW] (FileData *)
 *			  Extraction state data for the file containing the
 *			  archive.
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
FLARLocalFileExtractPriv(FlashArchive *flar, FileData *filedata, FILE *xfp,
    TCallback *cb, void *data)
{
	FLARProgress prog;
	size_t towrite;
	long long left;
	FILE *f;
	char *buf = NULL;

	f = filedata->file;

	left = filedata->fsize - ftello64(filedata->file);

	prog.type = FLARPROGRESS_STATUS;
	prog.data.status.total = left;
	prog.data.status.cur = 0LL;
	prog.data.status.nfiles = -1;
	cb(data, (void *)&prog);

	buf = (char *)xmalloc(LOCAL_READ_CHUNK * sizeof (char));

	/*
	 * If this is redone with a fork, one process should probably just
	 * read one byte per page to get the kernel to do a pre-fetch.
	 * Needless to say, said process would need a throttle.
	 */
	while (left) {
		towrite = (left > LOCAL_READ_CHUNK) ? LOCAL_READ_CHUNK : left;

		/* fill the buffer from the archive */
		if (fread(buf, towrite, 1, filedata->file) != 1) {
			/*
			 * we shouldn't get an EOF since we
			 * shouldn't ever attempt to read off
			 * the end of the archive.
			 */
			if (feof(filedata->file)) {
				write_notice(ERRMSG, MSG_READ_EOF,
				    FLARArchiveWhere(flar));
				(void) free(buf);
				return (FlErrRead);
			} else if (ferror(filedata->file)) {
				write_notice(ERRMSG, MSG_READ_FAILED,
				    FLARArchiveWhere(flar));
				(void) free(buf);
				return (FlErrRead);
			}
			/* NOTREACHED */
		}

		/* write out the buffer to the consumer */
		if (fwrite(buf, 1, towrite, xfp) < towrite) {
			write_notice(ERRMSG, MSG_WRITE_FAILED,
			    FLARArchiveWhere(flar));
			(void) free(buf);
			return (FlErrWrite);
		}
		left -= towrite;

		prog.data.status.cur += towrite;
		cb(data, (void *)&prog);
	}

	(void) free(buf);
	return (FlErrSuccess);
}

/*
 * Name:	FLARLocalFileClose
 * Description:	The Flash private function used for closing archives contained
 *		in local files.  The descriptor	associated with the archive is
 *		closed and reset.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive wasn't open
 */
/*ARGSUSED*/
FlashError
FLARLocalFileClosePriv(FlashArchive *flar, FileData *filedata)
{
	if (!filedata->file) {
		write_notice(ERRMSG, MSG0_INTERNAL_ERROR);
		return (FlErrInternal);
	}

	fclose(filedata->file);

	filedata->file = NULL;
	filedata->fsize = -1;

	return (FlErrSuccess);
}
