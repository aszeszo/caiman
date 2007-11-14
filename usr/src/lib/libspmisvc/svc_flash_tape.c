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

#pragma ident	"@(#)svc_flash_tape.c	1.4	07/10/09 SMI"


/*
 * Module:	svc_flash_tape.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for manipulating archives retrieved from
 *	tape drives.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/condvar.h>	/* Needed for stdef.h - see 4336105 */
#include <sys/kstat.h>		/* Needed for stdef.h - see 4336105 */
#include <sys/mtio.h>
#include <sys/scsi/scsi.h>
#include <sys/scsi/targets/stdef.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

#define	TAPE_LINEBUF_SIZE	1024

/*
 * Use 5MB as the default block size.  If the user specified
 * something different, or the device's maximum supported block
 * size is less than this, then use it instead of the default
 */
#define	TAPE_DEFAULT_BLKSIZE	(5*(int)MBYTE)

typedef struct {
	int	maxblksize;
	int	fd;

	/* Read buffer */
	char	*readbuf;
	char	*readbufptr;
	char	*readbufendptr;
} TapeData;
#define	TAPEDATA(flar)	((TapeData *)flar->data)

#define	READBUF(flar)		(TAPEDATA(flar)->readbuf)
#define	READBUFPTR(flar)	(TAPEDATA(flar)->readbufptr)
#define	READBUFENDPTR(flar)	(TAPEDATA(flar)->readbufendptr)

/* Local functions */
static FlashError	_tape_read_from_block(FlashArchive *, char **, int *,
			    int *);
static FlashError	_tape_read_block(FlashArchive *flar);
static FlashError	_tape_flush_block(FlashArchive *, char **, int *);
static int		_get_max_block_size(int);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARLocalTapeOpen
 * Description:	The local_tape-specific archive opening routine.  Positions the
 *		tape and opens it.  No validation of the actual archive is done.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 * Returns:	FlErrSuccess		- The archive was opened successfully
 *		FlErrFileNotFound	- The specified tape device was not
 *					  found
 *		FlErrCouldNotOpen	- The tape could not be positioned or
 *					  opened correctly
 */
FlashError
FLARLocalTapeOpen(FlashArchive *flar)
{
	struct mtdrivetype_request mtreq;
	struct mtdrivetype mtdt;
	struct mtop op;
	struct mtget mtg;
	int fd;
	int devmaxblksize;

	/* Does the device exist? */
	if (access(flar->spec.LocalTape.device, F_OK)) {
		write_notice(ERRMSG, MSG1_DEVICE_ACCESS_FAILED,
		    flar->spec.LocalTape.device);
		return (FlErrFileNotFound);
	}

	/* Open it */
	if ((fd = open(flar->spec.LocalTape.device, O_RDONLY)) < 0) {
		write_notice(ERRMSG, MSG0_FLASH_CANT_OPEN_TAPE,
		    flar->spec.LocalTape.device);
		return (FlErrCouldNotOpen);
	}

	/* Is the drive ok? (tape loaded, etc) */
	if (ioctl(fd, MTIOCGET, &mtg) < 0) {
		write_notice((GetSimulation(SIM_EXECUTE) ? WARNMSG : ERRMSG),
		    MSG0_FLASH_CANT_STATUS_TAPE,
		    flar->spec.LocalTape.device);
		if (!GetSimulation(SIM_EXECUTE)) {
			(void) close(fd);
			return (FlErrCouldNotOpen);
		}
	}

	/* Position the tape (if necessary) */
	if (flar->spec.LocalTape.position >= 0) {
		op.mt_op = MTFSF;
		op.mt_count = flar->spec.LocalTape.position - mtg.mt_fileno;
		if (ioctl(fd, MTIOCTOP, &op) < 0) {
			write_notice(
			    (GetSimulation(SIM_EXECUTE) ? WARNMSG : ERRMSG),
			    MSG0_FLASH_CANT_POSITION_TAPE,
			    flar->spec.LocalTape.position);
			if (!GetSimulation(SIM_EXECUTE)) {
				(void) close(fd);
				return (FlErrCouldNotOpen);
			}
		}
	}

	/* Mark the archive as open, and initialize tape-specific data */
	flar_set_open(flar);

	flar->data = xcalloc(sizeof (TapeData));
	TAPEDATA(flar)->fd = fd;

	/*
	 * Set the block size to use.
	 *
	 * If the user specified a block size, use it, unless it's larger than
	 * the max supported by the device.  If it is, use the largest block
	 * size supported by the device, and warn the user.
	 *
	 * If the user did not specify a size, use the default, unless the
	 * default is larger than max supported by the device.  If it is,
	 * use the max size supported by the device, and be quiet
	 * (i.e. not warn).
	 */
	devmaxblksize = _get_max_block_size(TAPEDATA(flar)->fd);

	if (flar->spec.LocalTape.blksize > 0) {
		if (flar->spec.LocalTape.blksize > devmaxblksize) {
			write_notice(WARNMSG, MSG0_TAPE_BLKSIZE_TOOBIG,
			    flar->spec.LocalTape.blksize,
			    flar->spec.LocalTape.device,
			    devmaxblksize, devmaxblksize);
			TAPEDATA(flar)->maxblksize = devmaxblksize;
		} else {
			TAPEDATA(flar)->maxblksize =
			    flar->spec.LocalTape.blksize;
		}
	} else {
		if (TAPE_DEFAULT_BLKSIZE > devmaxblksize) {
			/* don't warn, just do it */
			TAPEDATA(flar)->maxblksize = devmaxblksize;
		} else {
			TAPEDATA(flar)->maxblksize = TAPE_DEFAULT_BLKSIZE;
		}
	}

	READBUF(flar) = (char *)xmalloc(TAPEDATA(flar)->maxblksize);
	READBUFPTR(flar) = NULL;

	/* Tell the user all about what we just did (if they want to know) */
	if (get_trace_level() > 0) {
		mtreq.size = sizeof (struct mtdrivetype);
		mtreq.mtdtp = &mtdt;
		if (ioctl(TAPEDATA(flar)->fd, MTIOCGETDRIVETYPE, &mtreq) < 0) {
			write_notice(WARNMSG, MSG0_CANT_GET_TAPE_INFO);
		} else {
			write_status(LOGSCR, LEVEL0, MSG0_TAPE_DETAILS);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: %s",
			    MSG0_TAPE_DEVICE, flar->spec.LocalTape.device);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: %s",
			    MSG0_TAPE_NAME, mtdt.name);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: %s",
			    MSG0_TAPE_VENDOR_ID, mtdt.vid);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: 0x%02x",
			    MSG0_TAPE_TYPE, (int)mtg.mt_type);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: %d",
			    MSG0_TAPE_MAXBLKSIZE, devmaxblksize);
			write_status(LOGSCR, LEVEL1|LISTITEM, "%-20s: %d",
			    MSG0_TAPE_BLKSIZE, TAPEDATA(flar)->maxblksize);
		}
	}

	return (FlErrSuccess);
}

/*
 * Name:	FLARLocalTapeReadLine
 * Description:	Read a line from a tape or other stream-like device.
 *		The line will be returned in a statically-allocated buffer
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The opened Flash archive from which to read
 *		bufptr	- [RO, *W]  (char **)
 *			  Where the pointer to the statically-allocated buffer
 *			  containing the read line is returned
 * Returns:	FlErrSuccess	- Read successful, *bufptr points to line
 *		FlErrEndOfFile	- End of File was encountered before the read
 *				  successfully completed
 *		FlErrRead	- An error occurred while trying to read
 */
FlashError
FLARLocalTapeReadLine(FlashArchive *flar, char **bufptr)
{
	static char *linebuf = NULL;
	static int linebuflen = 0;
	FlashError status;
	char *readblock;
	int curlboff;			/* Where the copy should start */
	int lenread;
	int foundeol;

	/* reset buffer */
	if (!linebuf) {
		linebuf = xmalloc(TAPE_LINEBUF_SIZE);
		linebuflen = TAPE_LINEBUF_SIZE;
	}
	curlboff = 0;

	/* while line not read */
	do {

		/* read another block */
		if ((status = _tape_read_from_block(flar, &readblock, &lenread,
						&foundeol)) != FlErrSuccess) {
			return (status);
		}

		/*
		 * if read size + existing bits bigger than buf size,
		 * realloc it
		 */
		if ((curlboff + 1) + lenread > linebuflen) {
			linebuflen = (curlboff + 1) + lenread;
			linebuf = xrealloc(linebuf, linebuflen);
		}

		/* copy result onto end of buffer */
		(void) memcpy(linebuf + curlboff, readblock, lenread);
		curlboff += lenread;

	} while (!foundeol);

	/* return buffer in bufptr */
	linebuf[curlboff] = '\0';
	*bufptr = linebuf;

	return (FlErrSuccess);
}

/*
 * Name:	FLARLocalTapeExtract
 * Description:	The local_tape-specific archive extraction routine.  This
 *		routine sends, in bulk, all of the data remaining in the
 *		archive beyound the current location to the passed stream.
 *		This routine will return FlErrSuccess if the end of the
 *		archive (read returns 0) is reached successfully.  The amount
 *		of data read from the archive as compared to the size of the
 *		archive (if any) recorded in the identification section is not
 *		taken into account.
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
 *		FlErrRead	- An error occurred trying to read from the
 *				  archive
 *		FlErrWrite	- An error occurred trying to write to the
 *				  extraction stream
 */
FlashError
FLARLocalTapeExtract(FlashArchive *flar, FILE *xfp, TCallback *cb,
    void *data)
{
	FLARProgress prog;
	int amtread;
	long long last;
	char *bufptr;
	char *block;

	block = (char *)xmalloc(TAPEDATA(flar)->maxblksize);

	/* Set up the progress callback */
	prog.type = FLARPROGRESS_STATUS;
	prog.data.status.total = flar->ident.arc_size;
	prog.data.status.cur = last = 0LL;
	prog.data.status.nfiles = -1;
	cb(data, (void *)&prog);

	/*
	 * The FLARLocalTapeReadLine routine reads from the tape in chunks,
	 * but returns data in line-size pieces.  Since there's no way to back
	 * up, like we can with a local file, there may still be an unused
	 * portion of the last chunk read.  This unused portion is the start
	 * of the files section, and needs to be passed to the extraction
	 * stream.
	 */
	if (_tape_flush_block(flar, &bufptr, &amtread) != FlErrSuccess) {
		write_notice(ERRMSG, MSG_READ_FAILED, FLARArchiveWhere(flar));
		free(block);
		return (FlErrRead);
	}

	if (amtread) {
		/* Make sure we wrote everything */
		if (fwrite(bufptr, 1, amtread, xfp) < amtread) {
			write_notice(ERRMSG, MSG_WRITE_FAILED,
			    FLARArchiveWhere(flar));
			free(block);
			return (FlErrWrite);
		}

		prog.data.status.cur += amtread;
	}

	/*
	 * The ReadLine buffer has now been cleared, so we can concentrate
	 * on reading large chunks and sending them to the extraction stream.
	 * The loop exits when we reach the end of the archive - when the
	 * read() returns 0.
	 */
	for (;;) {
		if ((amtread = read(TAPEDATA(flar)->fd, block,
				    TAPEDATA(flar)->maxblksize)) < 0) {
			switch (errno) {
			case ENOMEM:
				/*
				 * When reading from a magnetic tape
				 * (see mtio(7I)), and you get an
				 * ENOMEM, it means your read
				 * buffers are too small for the
				 * records laid down on the tape.
				 */
				write_notice(ERRMSG, MSG0_FLASH_TAPE_NOSPC,
				    TAPEDATA(flar)->maxblksize);
				break;
			default:
				break;
			}
			write_notice(ERRMSG, MSG_READ_FAILED,
			    FLARArchiveWhere(flar));
			free(block);
			return (FlErrRead);
		} else if (amtread == 0) {
			/* We should be done */
			if (last != prog.data.status.cur) {
				cb(data, (void *)&prog);
			}
			free(block);
			return (FlErrSuccess);
		}

		if (fwrite(block, 1, amtread, xfp) < amtread) {
			write_notice(ERRMSG, MSG_WRITE_FAILED,
			    FLARArchiveWhere(flar));
			free(block);
			return (FlErrWrite);
		}

		/* Advance the pointer; only give an update every megabyte */
		prog.data.status.cur += amtread;
		if (prog.data.status.cur / ((int)MBYTE) !=
							last / ((int)MBYTE)) {
			cb(data, (void *)&prog);
			last = prog.data.status.cur;
		}
	}

	/* NOTREACHED */
}

/*
 * Name:	FLARLocalTapeClose
 * Description:	The local_tape-specific archive closing routine.  This routine
 *		closes the file descriptor associated with the tape device.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive was not open
 */
FlashError
FLARLocalTapeClose(FlashArchive *flar)
{
	if (TAPEDATA(flar)->fd < 0) {
		write_notice(ERRMSG, MSG0_INTERNAL_ERROR);
		return (FlErrInternal);
	}

	(void) close(TAPEDATA(flar)->fd);

	if (READBUF(flar)) {
		free(READBUF(flar));
		READBUFPTR(flar) = NULL;
	}

	if (flar->data) {
		free(flar->data);
		flar->data = NULL;
	}

	return (FlErrSuccess);
}

/* ---------------------- private functions ----------------------- */

/*
 * Name:	_tape_read_from_block
 * Description:	Read data from the current block, stopping either at the end
 *		of the block or at the end of the current line.  If there is
 *		no current block (it's the first time through, or the last
 *		call exhausted the then-current block), read another one,
 *		and return the data as described above from it.  Data is
 *		returned in the connection-specific read buffer.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive from which the data should be read.
 *		bufptr	- [RO, *WO] (char **)
 *			  The data read from the block.  This data is
 *			  *NOT* NULL-terminated.
 *		avail	- [RO, *WO] (int *)
 *			  The number of bytes returned in bufptr.
 *		foundeol- [RO, *WO] (int *)
 *			  Whether (TRUE) or not (FALSE) the data returned in
 *			  *bufptr represents a read through the end of a line.
 * Returns:	FlErrSuccess	- The data was read successfully
 *		FlErrRead	- An error occurred reading a block
 *		FlErrEndOfFile	- No data was available for reading, because
 *				  the end of the archive was encountered.
 */
static FlashError
_tape_read_from_block(FlashArchive *flar, char **bufptr, int *avail,
    int *foundeol)
{
	FlashError status;
	char *start;
	char *eolp;

	/* if no space left in block, read new block */
	if (!READBUFPTR(flar)) {
		if ((status = _tape_read_block(flar)) != FlErrSuccess) {
			return (status);
		}
	}

	/* scan to \n or end of block, which ever comes first */
	for (eolp = start = READBUFPTR(flar);
	    eolp <= READBUFENDPTR(flar); eolp++) {
		if (*eolp == '\n') {
			break;
		}
	}

	/*
	 * eolp now points either to a \n or to readbufendptr + 1
	 * adjust current-position-in-block pointer.  NULL means read another
	 */
	if (eolp == READBUFENDPTR(flar) + 1) {
		READBUFPTR(flar) = NULL;
	} else {
		READBUFPTR(flar) = eolp + 1;
	}

	/*
	 * return:
	 *	pointer to the place from which we started searching,
	 *	number of bytes available,
	 *	whether the given block of bytes marks the end of a line
	 */
	*bufptr = start;
	*avail = eolp - start;
	*foundeol = (eolp != READBUFENDPTR(flar) + 1);

	return (FlErrSuccess);
}

/*
 * Name:	_tape_read_block
 * Description:	Read a block of data from the archive.  If EOF is encountered
 *		during the read, only a partial block will be read, but success
 *		will be returned.  The maximum block length that will be read
 *		is the maximum block size supported by the drive.
 *
 *		This routine reads into readbuf, and sets readbufptr and
 *		readbufendptr.
 *
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive from which to read
 * Returns:	FlErrSuccess	- The data was read successfully
 *		FlErrRead	- An error occurred reading a block
 *		FlErrEndOfFile	- No data was available for reading, because
 *				  the end of the archive was encountered.
 */
static FlashError
_tape_read_block(FlashArchive *flar)
{
	ssize_t	amtread;

	/* Read the block */
	if ((amtread = read(TAPEDATA(flar)->fd, READBUF(flar),
			    TAPEDATA(flar)->maxblksize)) < 0) {
		switch (errno) {
		case ENOMEM:
			/*
			 * When reading from a magnetic tape
			 * (see mtio(7I)), and you get an
			 * ENOMEM, it means your read
			 * buffers are too small for the
			 * records laid down on the tape.
			 */
			write_notice(ERRMSG, MSG0_FLASH_TAPE_NOSPC,
			    TAPEDATA(flar)->maxblksize);
			break;
		default:
			break;
		}
		return (FlErrRead);
	} else if (amtread == 0) {
		return (FlErrEndOfFile);
	}

	/* Set up the position pointers */
	READBUFPTR(flar) = READBUF(flar);
	READBUFENDPTR(flar) = READBUF(flar) + (amtread - 1);

	return (FlErrSuccess);
}

/*
 * Name:	_tape_flush_block
 * Description:	Used to access the remaining unused chunk of readbuf, this
 *		routine returns a pointer to that chunk, along with the
 *		number of bytes in it.  If no data is available, *buf will
 *		be NULL, and *avail will be 0.  The data will be returned
 *		in a statically allocated buffer that the caller must not
 *		modify.
 * Scope:	private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive whose buffer is to be flushed
 *		buf	- [RO, *RW] (char **)
 *			  The pointer to the unused chunk.  This chunk is
 *			  *NOT* NULL-terminated.
 *		avail	- [RO, *RW] (int *)
 *			  The number of bytes returned in *buf
 * Returns:	FlErrSuccess	- The chunk was successfully flushed.
 */
/*ARGSUSED*/
static FlashError
_tape_flush_block(FlashArchive *flar, char **buf, int *avail)
{
	if (!READBUFPTR(flar)) {
		*avail = 0;
		*buf = NULL;
	} else {
		*avail = READBUFENDPTR(flar) -
		    READBUFPTR(flar) + 1;
		*buf = READBUFPTR(flar);
	}

	READBUFPTR(flar) = NULL;

	return (FlErrSuccess);
}

/*
 * Name:	_get_max_block_size
 * Description:	If we try to read(2) an n-byte chunk from a tape file that has
 *		been recorded with block size n + 1 or greater, the read will
 *		fail (see mtio(7i)) with ENOMEM.  Since we can't figure out the
 *		blocksize of a given file without reading it, by which time it's
 *		too late, we have to always ask for a chunk whose size is equal
 *		to or greater than the maximum block size the drive can handle.
 *		Reads bigger than the block size in the tape file are OK.  This
 *		routine sends a SCSI-2 READ BLOCK LIMITS command to the drive,
 *		asking it for said maximum size.  If the size cannot be
 *		retrieved from the drive, we guess at a megabyte.  For
 *		reference, an EXB-8500 (a really old 8mm) has a maximum block
 *		size of 240k, as does the Exabyte Mammoth M2 (a new 8mm).
 * Scope:	private
 * Arguments:	fd	- [RO] (int)
 *			  An open file descriptor to the tape drive
 * Returns:	int	- the maximum block size in bytes
 */
static int
_get_max_block_size(int fd)
{
	struct uscsi_cmd ucmd;
	struct read_blklim rb;
	union scsi_cdb cdb;
	int maxblksize;

	(void) memset(&ucmd, 0, sizeof (ucmd));
	(void) memset(&cdb, 0, sizeof (cdb));
	(void) memset(&rb, 0, RBLSIZE);

	cdb.scc_cmd = SCMD_READ_BLKLIM;

	ucmd.uscsi_cdb = (caddr_t)&cdb;
	ucmd.uscsi_cdblen = CDB_GROUP0;
	ucmd.uscsi_bufaddr = (caddr_t)&rb;
	ucmd.uscsi_buflen = RBLSIZE;
	ucmd.uscsi_flags = USCSI_READ;

	if (ioctl(fd, USCSICMD, &ucmd) < 0 ||
	    ucmd.uscsi_status != 0) {
		/*
		 * We failed to find the block size, so guess.  This either
		 * means that the the command just plain failed (which would
		 * be odd, since it's a mandatory SCSI-2 command), or we're
		 * running as non-root (simulation mode).
		 */
		maxblksize = (size_t)MBYTE;

		if (get_trace_level() > 0) {
			write_notice(WARNMSG, MSG0_TAPE_BLKSIZE_UNAVAIL,
			    maxblksize);
		}
		return (maxblksize);
	}

	/* Use the biggest block size supported by the drive */
	maxblksize = rb.max_hi << 16 | rb.max_mid << 8 | rb.max_lo;

	return (maxblksize);
}
