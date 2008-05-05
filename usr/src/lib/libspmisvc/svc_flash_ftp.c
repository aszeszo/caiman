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
 * Module:	svc_flash_ftp.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for manipulating archives retrieved from
 *	ftp servers.
 */

#include <stdio.h>
#include <wchar.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <libgen.h>
#include <sys/types.h>
#include <sys/condvar.h>	/* Needed for stdef.h - see 4336105 */
#include <sys/kstat.h>		/* Needed for stdef.h - see 4336105 */
#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "spmiapp_strings.h"
#include "svc_strings.h"
#include "svc_flash.h"

/*
 * telnet.h and ftp.h must come after libspmi stuff since spmi stuff
 * redefines some macros.
 *
 * The following items are redefined.
 */
#undef	CONTINUE
#undef	ERROR

#include <arpa/telnet.h>
#include <arpa/ftp.h>
#include <signal.h>

/* 1MB */
#define	D_READBUF_SIZE		(1024 * 1024)

/* The length of longest ftp command */
#define	MAXCMDLEN		10

#define	FTP_LINEBUF_SIZE	((MAXPATHLEN)*2+MAXCMDLEN+4)
#define	FTP_CMD_RETRY_COUNT	5
#define	UC(b)			((b)&0xff)
#define	CLOSED			(-1)

typedef struct {
	FILE		*ctrl_in;	/* the control socket */
	FILE		*ctrl_out;	/* the control socket */
	int		data_fd;	/* the data socket */
	int		data_socket;	/* the data socket */
	uint32_t	local_ip;
	long long	cur;
	long long	end;

	/* Data Read buffer */
	char	*d_readbuf;
	char	*d_readbufptr;
	char	*d_readbufendptr;
	int	d_readbufcounted;

} FtpData;


#define	FTPDATA(flar)		((FtpData *)flar->data)

#define	CTRL_OPEN(flar)		((FTPDATA(flar)->ctrl_in != NULL) && \
				(FTPDATA(flar)->ctrl_out != NULL))

#define	DATA_OPEN(flar)		((FTPDATA(flar)->data_socket == CLOSED) && \
				(FTPDATA(flar)->data_fd != CLOSED))

#define	D_READBUF(flar)		(FTPDATA(flar)->d_readbuf)
#define	D_READBUFCOUNTED(flar)	(FTPDATA(flar)->d_readbufcounted)
#define	D_READBUFPTR(flar)	(FTPDATA(flar)->d_readbufptr)
#define	D_READBUFENDPTR(flar)	(FTPDATA(flar)->d_readbufendptr)

/* Progress information messages for the front end */
static TCallback	*progress_callback;
static void		*progress_userdata;

/* Local functions */
static FlashError	_ftp_read_from_block(FlashArchive *, char **, int *,
			    int *);
static FlashError	_ftp_read_block(FlashArchive *flar, long long *);
static void		_ftp_flush_block(FlashArchive *);

static int 		send_command(FlashArchive *, char **, char *, ...);
static void		alarm_handler(int);
static void		_progress_restart(FLARRestartReason);
static FlashError	_ftp_start_data_stream(FlashArchive *);
static long long	ftp_parse_size(char *);
static int		ftp_open_control_connection(FlashArchive *);
static int		ftp_close_control_connection(FlashArchive *);
static int		ftp_open_data_connection(FlashArchive *);
static int		ftp_close_data_connection(FlashArchive *);
static int		ftp_begin_retr_file(FlashArchive *);
static int		ftp_verify(FlashArchive *);
static FlashError	ftp_get_size(FlashArchive *flar);
static int		get_reply(FlashArchive *, char **, int);
static int		output_command(FlashArchive *, char *);
static int		send_command(FlashArchive *, char **, char *, ...);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARLocalFTPOpen
 * Description:	The ftp-specific archive opening routine.  Positions the
 *		ftp server and opens it.  No validation of the
 *		actual archive is done.
 * Scope:		Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 * Returns:	FlErrSuccess		- The archive was opened successfully
 *		<something else>		- The archive could
 *					not be opened.
 */
FlashError
FLARFTPOpen(FlashArchive *flar)
{
	int rc;
	void (*old_handler)(int);

	/* initialize private date */
	flar->data = xcalloc(sizeof (FtpData));
	FTPDATA(flar)->ctrl_in = NULL;
	FTPDATA(flar)->ctrl_out = NULL;
	FTPDATA(flar)->data_fd = CLOSED;
	FTPDATA(flar)->data_socket = CLOSED;
	FTPDATA(flar)->cur = -1;
	FTPDATA(flar)->end = -1;

	D_READBUF(flar) = (char *)
	    xmalloc(D_READBUF_SIZE * sizeof (char));
	D_READBUFPTR(flar) = NULL;
	D_READBUFENDPTR(flar) = NULL;

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, alarm_handler);

	/* open the control connection */
	if ((rc = ftp_open_control_connection(flar)) != FlErrSuccess) {
		switch (rc) {
		case FlErrHostNotFound:
			write_notice(ERRMSG, MSG0_UNKNOWN_HOST,
		flar->spec.FTP.proxyhost ? flar->spec.FTP.proxyhost :
		(flar->spec.FTP.url->host ? flar->spec.FTP.url->host :
				"**NO HOST**"));
			break;
		case FlErrCouldNotContactHost:
		    write_notice(ERRMSG, MSG0_CANNOT_CONNECT,
			(flar->spec.FTP.url->host ? flar->spec.FTP.url->host :
			    "**NO HOST**"),
			flar->spec.FTP.url->port,
			strerror(errno));
			break;
		case FlErrAuthInvalid:
			write_notice(ERRMSG, ARCHIVE_NO_AUTH,
			    FLARArchiveWhere(flar));
			break;
		case FlErrCorruptedArchive:
			write_notice(ERRMSG, MSG0_FTP_NEED_ARCHIVE_SIZE,
			    flar->spec.FTP.url->host, FLARArchiveWhere(flar));
			break;
		case FlErrFileNotFound:
		default:
			write_notice(ERRMSG, ARCHIVE_NO_OPEN);
		}
		return (rc);
	}

	/* see if the file is available */
	if ((rc = ftp_verify(flar)) != FlErrSuccess) {
		switch (rc) {
		case FlErrFileNotFound:
			write_notice(ERRMSG, ARCHIVE_NO_OPEN,
			    FLARArchiveWhere(flar));
			break;
		case FlErrNetworkError:
			write_notice(ERRMSG, ARCHIVE_BAD_HOST);
			break;
		case FlErrUnsupported:
			write_notice(ERRMSG, ARCHIVE_NO_OPEN_FTP);
			break;
		default:
			write_notice(ERRMSG, ARCHIVE_NO_OPEN);
		}
		return (rc);
	}

	/* Disable the timeout timer */
	(void) alarm(0);
	(void) signal(SIGALRM, old_handler);

	/*
	 * Do we have a size for the file?  We can't extract if we
	 * don't know the size.
	 */
	if (flar->ident.arc_size <= 0) {
		write_notice(ERRMSG, MSG0_FTP_NEED_ARCHIVE_SIZE,
		    flar->spec.FTP.url->host, FLARArchiveWhere(flar));
		free(flar->data);
		ftp_close_control_connection(flar);
		return (FlErrNoSize);
	}

	FTPDATA(flar)->cur = 0;

	flar_set_open(flar);

	return (FlErrSuccess);
}

/*
 * Name:	FLARFTPReadLine

 * Description:	Read a line from a ftp or other stream-like device.
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
FLARFTPReadLine(FlashArchive *flar, char **bufptr)
{
	static char *linebuf = NULL;
	static int linebuflen = 0;
	void (*old_handler)(int);
	FlashError status;
	char *readblock;
	int curlboff;			/* Where the copy should start */
	int lenread;
	int foundeol;

	/* reset buffer */
	if (!linebuf) {
		linebuf = xmalloc(FTP_LINEBUF_SIZE);
		linebuflen = FTP_LINEBUF_SIZE;
	}
	curlboff = 0;

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, alarm_handler);

	/* while line not read */
	do {

		/* read another block */
		if ((status = _ftp_read_from_block(flar, &readblock, &lenread,
						&foundeol)) != FlErrSuccess) {
			if (status == FlErrEndOfFile &&
			    FTPDATA(flar)->cur <= FTPDATA(flar)->end) {
				/*
				 * Server died.  Try again.
				 * Actual backoff is randomly distibuted
				 * from 1 to backoff_ceiling
				 */
				backoff();
				continue;
			}
			/* got EOF.. Reset backoff time for next time */
			reset_backoff();
			return (status);
		}

		/* got good read.. Reset backoff time for next time */
		reset_backoff();

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

	/* Disable the timeout timer */
	(void) alarm(0);
	(void) signal(SIGALRM, old_handler);

	/* return buffer in bufptr */
	linebuf[curlboff] = '\0';
	*bufptr = linebuf;
	return (FlErrSuccess);
}

/*
 * Name:	FLARFTPExtract
 * Description:	The local_ftp-specific archive extraction routine.  This
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
FLARFTPExtract(FlashArchive *flar, FILE *xfp, TCallback *cb,
    void *data)
{
	FLARProgress prog;
	FlashError status;
	FlashError rc;
	long long amtread;
	long long last;
	void (*old_handler)(int);

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, alarm_handler);

	/* Set up the progress callback */
	progress_callback = cb;
	progress_userdata = data;

	prog.type = FLARPROGRESS_STATUS;
	prog.data.status.total =
	    FTPDATA(flar)->end -
	    (FTPDATA(flar)->cur -
		(D_READBUFENDPTR(flar) - D_READBUFPTR(flar))) + 1;
	prog.data.status.cur = last = 0;
	prog.data.status.nfiles = -1;
	cb(data, (void *)&prog);

	for (;;) {
		status = _ftp_read_block(flar, &amtread);
		if (status == FlErrEndOfFile) {
			if (FTPDATA(flar)->cur < FTPDATA(flar)->end) {
				/*
				 * The server died.  Calculate new backoff
				 * time, and Restart.
				 */
				_progress_restart(FLARRESTART_SERVERCLOSE);

				/*
				 * actual backoff is randomly distibuted
				 * from 1 to backoff_ceiling
				 */
				backoff();
				continue;
			} else {
				/* reset backoff */
				reset_backoff();

				/* Reached the end of the archive.  Exit OK */
				if (last != prog.data.status.cur) {
					cb(data, (void *)&prog);
				}
				rc = FlErrSuccess;
				break;
			}
		} else if (status != FlErrSuccess) {
			/* Some other error */
			rc = status;
			/* reset backoff for next time */
			reset_backoff();
			break;
		}

		/* we got a good read, so reset backoff */
		reset_backoff();
		if (fwrite(D_READBUFPTR(flar), 1, amtread, xfp) < amtread) {
			write_notice(ERRMSG, MSG_WRITE_FAILED,
			    FLARArchiveWhere(flar));
			rc = FlErrWrite;
			break;
		}

		/* Advance the pointer; only give an update every megabyte */
		prog.data.status.cur += amtread;
		if (prog.data.status.cur / ((size_t)MBYTE) !=
		    last / ((size_t)MBYTE)) {
			cb(data, (void *)&prog);
			last = prog.data.status.cur;
		}

		/* We're done with this block */
		_ftp_flush_block(flar);
	}

	/* Disable the timeout timer */
	(void) alarm(0);
	(void) signal(SIGALRM, old_handler);

	progress_callback = NULL;

	return (rc);
}

/*
 * Name:	FLARFTPClose
 * Description:	The local_ftp-specific archive closing routine.  This routine
 *		closes the file descriptor associated with the ftp device.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive was not open
 */
FlashError
FLARFTPClose(FlashArchive *flar)
{
	if ((ftp_close_data_connection(flar) != FlErrSuccess) ||
	    (ftp_close_control_connection(flar) != FlErrSuccess)) {
		return (FlErrInternal);
	} else {
		return (FlErrSuccess);
	}
}

/* ---------------------- private functions ----------------------- */

/*
 * Name:	_ftp_read_from_block
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
_ftp_read_from_block(FlashArchive *flar, char **bufptr, int *avail,
    int *foundeol)
{
	FlashError status;
	char *start;
	char *eolp;

	/* if no space left in block, read new block */
	if (!D_READBUFPTR(flar)) {
		if ((status = _ftp_read_block(flar, NULL)) != FlErrSuccess) {
			return (status);
		}
	}

	/* scan to \n or end of block, which ever comes first */
	for (eolp = start = D_READBUFPTR(flar);
	    eolp <= D_READBUFENDPTR(flar); eolp++) {
		if (*eolp == '\n') {
			break;
		}
	}

	/*
	 * eolp now points either to a \n or to readbufendptr + 1
	 * adjust current-position-in-block pointer.  NULL means read another
	 */
	if (eolp == D_READBUFENDPTR(flar) + 1) {
	    _ftp_flush_block(flar);
	} else {
		D_READBUFPTR(flar) = eolp + 1;
	}

	/*
	 * return:
	 *	pointer to the place from which we started searching,
	 *	number of bytes available,
	 *	whether the given block of bytes marks the end of a line
	 */
	*bufptr = start;
	*avail = eolp - start;
	*foundeol = (eolp != D_READBUFENDPTR(flar) + 1);

	return (FlErrSuccess);
}

/*
 * Name:	_ftp_read_block
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
_ftp_read_block(FlashArchive *flar, long long *amtreadptr)
{
	ssize_t	amtread;
	int errcode;
	char *donereply;
	int donecode;
	int rc;

	for (;;) {
		/*
		 * If there's anything left in the read buffer, use it first.
		 */
		if (D_READBUFPTR(flar) && D_READBUFPTR(flar)
		    <= D_READBUFENDPTR(flar)) {
			amtread = D_READBUFENDPTR(flar) -
			    D_READBUFPTR(flar) + 1;
			if (!D_READBUFCOUNTED(flar)) {
				D_READBUFCOUNTED(flar) = 1;
				FTPDATA(flar)->cur += amtread;
			}

			if (amtreadptr) {
				*amtreadptr = amtread;
			}
			write_debug(FLASH_DEBUG, "existing data read");

			return (FlErrSuccess);
		}

		/* need to read stuff from server */
		if ((rc = _ftp_start_data_stream(flar)) != FlErrSuccess) {
			return (rc);
		}

		/* connected! reset backoff */
		reset_backoff();

		(void) alarm(flar->spec.FTP.timeout);
		errno = 0;

		/* now do the read */
		amtread = read(FTPDATA(flar)->data_fd,
		    D_READBUF(flar), D_READBUF_SIZE);
		errcode = errno;
		(void) alarm(0);

		/* Handle aborted or empty reads */
		if (amtread < 0) {
			write_debug(FLASH_DEBUG, "aborted read");
			(void) ftp_close_data_connection(flar);
			(void) ftp_close_control_connection(flar);

			if (errcode == EINTR) {
				/* Timed out. */
				_progress_restart(FLARRESTART_TIMEOUT);

				continue;
			} else if (errcode) {
				return (FlErrRead);
			}
		} else if (amtread == 0) {

			/*
			 * We should be done.  First, close the data
			 * connection.  Then consume the return code
			 * from the server on the control channel.
			 */
			(void) ftp_close_data_connection(flar);
			donecode = get_reply(flar, &donereply, 0);

			if (donecode != COMPLETE) {
				/*
				 * the file was done, but the server
				 * said uh-uh.  Let's re-try
				 */
				ftp_close_control_connection(flar);
				_progress_restart(FLARRESTART_SERVERCLOSE);
				continue;
			}

			/* now close control */
			(void) ftp_close_control_connection(flar);
			return (FlErrEndOfFile);
		}

		/* Set the pointers to the newly-read data. */
		D_READBUFPTR(flar) = D_READBUF(flar);
		D_READBUFCOUNTED(flar) = 1;
		D_READBUFENDPTR(flar) = D_READBUF(flar) + (amtread - 1);
		FTPDATA(flar)->cur += amtread;
		if (amtreadptr) {
			*amtreadptr = amtread;
		}

		return (FlErrSuccess);
	}
}

/*
 * Name:	_ftp_start_data_stream
 * Description:	Begins transferring the archive across an FTP connection.
 *
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive from which to read
 * Returns:	FlErrSuccess	- The data stream was setup properly.
 */
static FlashError
_ftp_start_data_stream(FlashArchive *flar)
{
	int errnum;
	int ctrltries = 0, datatries = 0;
	/* we migh need to start up a new control connection */
	while (!CTRL_OPEN(flar) || !DATA_OPEN(flar)) {
		if (!CTRL_OPEN(flar)) {
			if (ftp_open_control_connection(flar) !=
			    FlErrSuccess) {
				ctrltries++;
				errnum = errno;
				write_debug(FLASH_DEBUG,
				    "can't open control: %s", strerror(errno));
				errno = errnum;
				if (ctrltries >= FTP_CMD_RETRY_COUNT) {
					reset_backoff();
					return (FlErrRead);
				}
				switch (errno) {
				case EINTR:
					_progress_restart(FLARRESTART_TIMEOUT);
					backoff();
					continue;
				case ETIMEDOUT:
				case ECONNREFUSED:
				case EHOSTDOWN:
					_progress_restart(FLARRESTART_REFUSED);
					backoff();
					continue;
				default:
					/* something bad */
					reset_backoff();
					return (FlErrRead);
				}
			}
		}

		/* we might need to start up a new data connection */
		if (!DATA_OPEN(flar)) {
			if (!ftp_begin_retr_file(flar)) {
				/* data connection failed.  Try again */
				datatries++;
				if (datatries >= FTP_CMD_RETRY_COUNT) {
					ftp_close_control_connection(flar);
					reset_backoff();
					return (FlErrRead);
				}
				_progress_restart(FLARRESTART_SERVERCLOSE);
				ftp_close_control_connection(flar);
				backoff();
				continue;
			}
		}
	}
	return (FlErrSuccess);
}

/*
 * Name:	_ftp_flush_block
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
static void
_ftp_flush_block(FlashArchive *flar)
{

	D_READBUFPTR(flar) = NULL;
}

/*
 * Name:	ftp_open_control_connection
 * Description:	Open a TCP connection to a given port on a given server.
 *		If the connection is successful, the descriptor for the
 *		socket is set in the FTP data.  errno will be set on failure.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive containing the connection data
 * Returns:	FlErrSuccess - Connection succeeded - return value is socket
 *		FlErrCouldNotOpen - couldn't open connection
 */
static int
ftp_open_control_connection(FlashArchive *flar)
{
	struct hostent *hep;
	struct in_addr *ip;
	static struct sockaddr_in dest;
	int errcode;
	int fd, n;
	FILE *stream_in;
	FILE *stream_out;
	char *intro;
	char *resp;
	unsigned char *a, *p;
	int len;
	char *targethost;
	int targetport;
	char *targetuser = NULL;
	int rc;

	/*
	 * Figure out where we're supposed to connect, if we haven't
	 * done so already
	 */
	targethost = flar->spec.FTP.proxyhost ? flar->spec.FTP.proxyhost :
	    flar->spec.FTP.url->host;

	if (flar->spec.FTP.proxyhost) {
	    /* user@host */
	    targetuser = xmalloc(strlen(flar->spec.FTP.url->auth.basic.user) +
		1 + strlen(flar->spec.FTP.url->host) + 1);
	    sprintf(targetuser, "%s@%s",
		flar->spec.FTP.url->auth.basic.user,
		flar->spec.FTP.url->host);
	} else {
	    targetuser = flar->spec.FTP.url->auth.basic.user;
	}

	targetport = flar->spec.FTP.proxyhost ? flar->spec.FTP.proxyport :
	    flar->spec.FTP.url->port;

	/* Get the address of the remote machine */
	if (!(hep = getipnodebyname(targethost, AF_INET,
	    AI_DEFAULT, &rc))) {
		switch (rc) {
		case HOST_NOT_FOUND:
			return (FlErrHostNotFound);
			break;
		default:
			return (FlErrCouldNotContactHost);
		}
	}

	/*LINTED*/
	ip = (struct in_addr *)hep->h_addr;

	(void) memset(&dest, 0, sizeof (dest));
	dest.sin_family = AF_INET;
	dest.sin_port = htons(targetport);
	dest.sin_addr.s_addr = ip->s_addr;

	/* Connect to the remote machine */
	if ((fd = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
		return (FlErrCouldNotContactHost);
	}

	if (connect(fd, (struct sockaddr *)&dest,
	    sizeof (struct sockaddr_in)) < 0) {
		errcode = errno;
		(void) close(fd);
		errno = errcode;
		return (FlErrCouldNotContactHost);
	}

	/* figure out which port we're using locally */
	len = sizeof (dest);
	if (getsockname(fd, (struct sockaddr *)&dest, &len) < 0) {
	    write_debug(FLASH_DEBUG,
		"getsockname() failed during control init");
	}

	FTPDATA(flar)->local_ip = dest.sin_addr.s_addr;
	a = (unsigned char *)&dest.sin_addr.s_addr;

	p = (unsigned char *)&dest.sin_port;
	write_debug(FLASH_DEBUG, "local port seems to be %d,%d,%d,%d,%d,%d",
	    UC(a[0]), UC(a[1]), UC(a[2]), UC(a[3]),
	    UC(p[0]), UC(p[1]));

	/* open streams to the other side */
	if ((stream_in = fdopen(fd, "r")) == NULL) {
		write_debug(FLASH_DEBUG, "cant open stream_in");
		errcode = errno;
		(void) close(fd);
		errno = errcode;
		return (FlErrNetworkError);
	}
	if ((stream_out = fdopen(fd, "w")) == NULL) {
		write_debug(FLASH_DEBUG, "cant open stream_out");
		errcode = errno;
		(void) close(fd);
		errno = errcode;
		return (FlErrNetworkError);
	}

	FTPDATA(flar)->ctrl_in = stream_in;
	FTPDATA(flar)->ctrl_out = stream_out;

	/* listen to startup message */
	rc = get_reply(flar, &intro, 0);
	if (rc != COMPLETE) {
		errcode = errno;
		write_debug(FLASH_DEBUG,
		    "Bad startup message (return code=%d)", rc);
		if (rc > 0) {
			write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, intro);
		}
	    ftp_close_control_connection(flar);
	    errno = errcode;
	    return (FlErrCouldNotOpen);
	}
	write_debug(FLASH_DEBUG, "got startup mesage: %s", intro);

	/*
	 * login
	 *
	 * With proxy: USER user@host
	 * Without: USER user
	 */
	n = send_command(flar, &resp, "USER %s", targetuser);

	if (n == CONTINUE) {
	    n = send_command(flar, &resp, "PASS %s",
		flar->spec.FTP.url->auth.basic.password);
	} else {
	    /* USER was not accepted.  We're hosed. */
	    write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, resp);
	    ftp_close_control_connection(flar);
	    return (FlErrAuthInvalid);
	}

	if (n != COMPLETE) {
		errcode = errno;
		write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, resp);
		ftp_close_control_connection(flar);
		errno = errcode;
		return (FlErrAuthInvalid);
	}
	return (FlErrSuccess);
}

/*
 * Name:	ftp_close_data_connection
 * Description:	Closes the data connection.
 *		socket is set in the FTP data.  errno will be set on failure.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive containing the connection data
 * Returns:	0	- Close succeeded.
 */
static int
ftp_close_data_connection(FlashArchive *flar)
{
	/*
	 * we must shutdown first to let the otherside know that
	 * we know what's going on.  Otherwise very strict RFC959-compliant
	 * servers (like wuftpd) will hang.
	 */
	(void) shutdown(FTPDATA(flar)->data_fd, 2);
	(void) shutdown(FTPDATA(flar)->data_socket, 2);
	(void) close(FTPDATA(flar)->data_fd);
	(void) close(FTPDATA(flar)->data_socket);
	FTPDATA(flar)->data_socket = CLOSED;
	FTPDATA(flar)->data_fd = CLOSED;
	D_READBUFPTR(flar) = NULL;
	D_READBUFENDPTR(flar) = NULL;
	return (FlErrSuccess);
}

/*
 * Name:	ftp_open_data_connection
 * Description:	Open a TCP connection to a given port on a given server,
 *		or listen for connection for passive ftp.
 *		If the connection is successful, the descriptor for the
 *		socket is set in the FTP data.  errno will be set on failure.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive containing the connection data
 * Returns:	0	- Connection succeeded - return value is socket
 *			  file descriptor
 *		-1	- Connection failed
 */
static int
ftp_open_data_connection(FlashArchive *flar)
{
	struct sockaddr_in src;
	int result;
	int fd;
	unsigned char *p, *a;
	int len;
	int t;
	int bufsize;
	char *resp;
	/* Connect to the remote machine */
	if ((fd = socket(PF_INET, SOCK_STREAM, 0)) < 0) {
		write_debug(FLASH_DEBUG, "open_data: can't create socket");
		return (-1);
	}

	/* set various options */

	/*
	 * Only set the send and receive buffer size if the default size
	 * is smaller than socksize.
	 */
	len = sizeof (bufsize);
	if (getsockopt(fd, SOL_SOCKET, SO_RCVBUF, (char *)&bufsize,
	    &len) < 0) {
		write_debug(FLASH_DEBUG, "open_data: getsockopt failed"
		    " for SO_RCVBUF");
	    return (-1);
	}
	if (bufsize < D_READBUF_SIZE) {
	    bufsize = D_READBUF_SIZE;
		if (setsockopt(fd, SOL_SOCKET, SO_RCVBUF, (char *)&bufsize,
		    sizeof (bufsize)) < 0) {
			write_debug(FLASH_DEBUG,
			    "open_data: setsockopt failed for SO_RCVBUF");
		}
	}

	write_debug(FLASH_DEBUG, "open_data: bufsize: %d", bufsize);

	/* start listening */
	memset(&src, 0, sizeof (src));
	src.sin_family = AF_INET;
	src.sin_port = htons(0);
	src.sin_addr.s_addr = htonl(INADDR_ANY);
	if ((t = bind(fd, (struct sockaddr *)&src,
	    sizeof (struct sockaddr_in))) != 0) {
		write_debug(FLASH_DEBUG,
		    "open_data: bad bind (%d) (errno=%d)",
		    t, errno);
		return (-1);
	}


	if (listen(fd, 1) < 0) {
	    write_debug(FLASH_DEBUG, "open_data: Could not listen()");
	    return (-1);
	}

	len = sizeof (src);
	getsockname(fd, (struct sockaddr *)&src, &len);

	a = (unsigned char *)&(FTPDATA(flar)->local_ip);

	p = (unsigned char *)&src.sin_port;

	write_debug(FLASH_DEBUG,
	    "open_data: setting port to %d,%d,%d,%d,%d,%d (%d)",
	    UC(a[0]), UC(a[1]), UC(a[2]), UC(a[3]),
	    UC(p[0]), UC(p[1]), (UC(p[0]) << 8) | UC(p[1]));

	if ((result =
	    send_command(flar, &resp, "PORT %d,%d,%d,%d,%d,%d",
		UC(a[0]), UC(a[1]), UC(a[2]), UC(a[3]),
		UC(p[0]), UC(p[1]))) == ERROR) {
		write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, resp);
		write_debug(FLASH_DEBUG,
		    "open_data: can't set port to %d,%d,%d,%d,%d,%d",
		    UC(a[0]), UC(a[1]), UC(a[2]), UC(a[3]),
		    UC(p[0]), UC(p[1]));
		return (-1);
	}

	FTPDATA(flar)->data_socket = fd;

	/* we return 0 on succcess, so we must invert here */
	return (result != COMPLETE);
}

/*
 * Name:	ftp_close_control_connection
 * Description:	Close the socket connection to the server
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose connection is being closed
 * Returns:	0	- The connection was closed
 *		-1	- An error occurred during closing.  errno has been set
 */
static int
ftp_close_control_connection(FlashArchive *flar)
{

	/*
	 * we don't care what the result of this command is.
	 * we're about to close the connection anyway.
	 */
	send_command(flar, NULL, "QUIT");

	(void) fclose(FTPDATA(flar)->ctrl_out);
	(void) fclose(FTPDATA(flar)->ctrl_in);
	FTPDATA(flar)->ctrl_in = NULL;
	FTPDATA(flar)->ctrl_out = NULL;
	FTPDATA(flar)->local_ip = 0;
	return (0);
}


/*
 * Name:	ftp_accept_data_connection
 * Description:	Begins the data transfer
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 * Returns:	TRUE	- The accept succeeded
 *		FALSE	- The accept failed or timed out
 */
static int
ftp_accept_data_connection(FlashArchive *flar)
{
	int s;
	int fromlen;
	struct sockaddr_in from;

	if (FTPDATA(flar)->data_socket == CLOSED) {
		write_debug(FLASH_DEBUG,
		    "accept_data: can't connect to dry socket");
		return (FALSE);
	}

	fromlen = sizeof (from);
	s = accept(FTPDATA(flar)->data_socket,
	    (struct sockaddr *)&from, &fromlen);
	if (s < 0) {
		write_debug(FLASH_DEBUG, "accept_data: accept failed");
		return (FALSE);
	}
	(void) close(FTPDATA(flar)->data_socket);
	FTPDATA(flar)->data_socket = CLOSED;
	FTPDATA(flar)->data_fd = s;
	return (TRUE);
}

/*
 * Name:	ftp_begin_retr_file
 * Description:	Begins the transfer of the archive over
 *		the data connection.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 * Returns:	TRUE	- The file transfer has begun
 *		FALSE	- There was a problem.
 */
static int
ftp_begin_retr_file(FlashArchive *flar)
{
	char dirnamec[PATH_MAX];
	char basenamec[PATH_MAX];
	char *dirnamep;
	char *basenamep;
	char *resp;
	int manual_skip = FALSE;
	char seekbuf[D_READBUF_SIZE];
	long long amtleft;
	int amttoread, amtread;

	if (!CTRL_OPEN(flar)) {
		write_debug(FLASH_DEBUG,
		    "retr_file: can't start RETR, not connected");
		return (FALSE);
	}

	strcpy(dirnamec, (const char *)flar->spec.FTP.url->path);
	strcpy(basenamec, flar->spec.FTP.url->path);
	dirnamep = dirname(dirnamec);
	basenamep = basename(basenamec);
	write_debug(FLASH_DEBUG,
	    "retr_file: RETRieving file %s/%s", dirnamep, basenamep);

	send_command(flar, NULL, "CWD %s", dirnamep);

	if (ftp_open_data_connection(flar) != 0) {
		write_debug(FLASH_DEBUG,
		    "retr_file: can't open data connection");
		return (FALSE);
	}

	if (send_command(flar, &resp, "TYPE I") != COMPLETE) {
		write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, resp);
		return (FALSE);
	}

	/* position the file if we have already read some of it */
	if (FTPDATA(flar)->cur > 0) {
	/*
	 * if the quick seek (using REST) failed, we must do it manually,
	 * once the data connection is established.
	 */
	    manual_skip =
		(send_command(flar, &resp, "REST %lld",
		    FTPDATA(flar)->cur) != CONTINUE);
	}

	if (send_command(flar, &resp, "RETR %s",
	    basenamep) != PRELIM) {
		write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, resp);
		ftp_close_data_connection(flar);
		return (FALSE);
	}

	if (!ftp_accept_data_connection(flar)) {
		write_debug(FLASH_DEBUG,
		    "retr_file: can't accept connection");
		return (FALSE);
	}

	/*
	 * manually skip through the file (which is really bad
	 * for performance) if we have to.
	 */
	if (manual_skip) {
		/* Read the block */
		amtleft = FTPDATA(flar)->cur;
		write_notice(WARNMSG, MSG0_ARCHIVE_FF, amtleft);

		while (amtleft > 0) {
			amttoread = (int)((amtleft > D_READBUF_SIZE) ?
			    D_READBUF_SIZE : amtleft);
			if ((amtread = read(FTPDATA(flar)->data_fd, seekbuf,
			    amttoread)) <= 0) {
				return (FALSE);
			}
			amtleft -= amtread;
		}
	}
	return (TRUE);
}

/*
 * Name:	ftp_verify
 * Description:	Verifies the archive exists
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 * Returns:	TRUE	- The archive was found
 *		FALSE	- The archive was not found
 */
static int
ftp_verify(FlashArchive *flar)
{
	int rc;

	/* figure out the size */
	if ((rc = ftp_get_size(flar)) != FlErrSuccess) {
		return (rc);
	}

	/* you might add more verification here */
	return (FlErrSuccess);
}


/*
 * Name:	ftp_parse_size
 *
 * Description:	Parses the size of the file from The passed line.
 *		since RFC959 does not specify a standard way of
 *		reporting the size, we take the output from the FTP
 *		command "LIST" and try and do something with it.  This
 *		is a horribly-broken scheme that exists only to
 *		support servers withouth the SIZE feature (such as
 *		Solaris' FTP server)
 *
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 *		line	- The output from "LIST xxx"
 * Returns: The size of the archive, or -1 if it could not be parsed */
static long long
ftp_parse_size(char *line)
{
	char **tokens = NULL;
	char *token;
	int tokencount, i;
	long long size;

	write_debug(FLASH_DEBUG,
	    "parse_size: line: \"%s\"", line);

	tokencount = 0;
	size = -1LL;

	/*
	 * first count the number of tokens, and remember each
	 * token.
	 */
	tokens = NULL;
	tokencount = 0;
	for (token = strtok(line, " \t");
		    token != NULL;
		    token = strtok(NULL, " \t")) {
		tokencount++;
		tokens = xrealloc(tokens, tokencount * sizeof (char *));
		tokens[tokencount-1] = xstrdup(token);
	}

	/*
	 * Now figure out which token contains the size of the
	 * file.  Admittedly this stinks, but thanks to RFC959
	 * we have no alternative.
	 */
	if (tokencount == 9) {
		/* 9 tokens? You must be on a unix system. */
		write_debug(FLASH_DEBUG,
		    "parse_size: on a familiar system: "
		    "%s (string)", tokens[4]);
		size = atoll(tokens[4]);
		/*
		 * Tell archive its size, in case the ident section can't
		 */
	} else {
		write_debug(FLASH_DEBUG, "can't figure size");
		return (-1LL);
	}

	/* now free borrowed memory */
	for (i = 0; i < tokencount; i++) {
		free(tokens[i]);
	}

	free(tokens);
	write_debug(FLASH_DEBUG,
	    "parse_size: parsed size: %lld", size);

	return (size);
}

/*
 * Name:	ftp_get_size
 * Description:	Verifies the archive size
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 * Returns:	FlErrSuccess - file was opened and sized
 *
 */
static FlashError
ftp_get_size(FlashArchive *flar)
{
	char dirnamec[PATH_MAX];
	char basenamec[PATH_MAX];
	char *dirnamep;
	char *basenamep;
	char line[FTP_LINEBUF_SIZE];
	char linecopy[FTP_LINEBUF_SIZE];
	FILE *listfp;
	char *sizereply;
	char *sizep;
	long long size;
	strcpy(dirnamec, (const char *)flar->spec.FTP.url->path);
	strcpy(basenamec, (const char *)flar->spec.FTP.url->path);
	dirnamep = dirname(dirnamec);
	basenamep = basename(basenamec);
	write_debug(FLASH_DEBUG,
	    "dirname: \"%s\" basename \"%s\"", dirnamep, basenamep);

	/* go to the directory containing the file */
	if (send_command(flar, NULL, "CWD %s", dirnamep) != COMPLETE) {
	    /* dir not existant */
	    return (FlErrFileNotFound);
	}

	/* check if the archive exists */
	if (send_command(flar, NULL, "NLST %s", basenamep) == ERROR) {
		return (FlErrFileNotFound);
	}

	/*
	 * some servers that implement SIZE do it very ineffeciently for
	 * ASCII-type files.  Let's not do that.
	 */
	send_command(flar, NULL, "TYPE I");

	/*
	 * first try the SIZE command, for those ftp servers
	 * that support it.
	 */
	if (send_command(flar, &sizereply, "SIZE %s", basenamep) == COMPLETE) {
		/* The server recognized it.  Parse the size */
		write_debug(FLASH_DEBUG,
		    "get_size: server knows SIZE command.  Reports \"%s\"",
		    sizereply);
		/*
		 * find the beginning of the last string token, which might be
		 * the whole string
		 */
		for (sizep = sizereply + (strlen(sizereply) - 1);
			(sizep > sizereply) && !isspace(*sizep);
			sizep--);
		if (isspace(*sizep)) sizep++;
		errno = 0;
		if ((size = atoll(sizep)) == 0) {
			if (errno != 0) {
				write_debug(FLASH_DEBUG,
				    "get_size: bad size parse  \"%s\" (%s)",
				    sizereply,
				    sizep);
				return (FlErrUnsupported);
			}
		}
	} else {
		/*
		 * get size the hard way, basically we do a LIST
		 * operation on the file, which returns a line
		 * containing information about the file, then we try
		 * to parse it.  Yes, this is horrible, but thanks to
		 * the insufficient RFC959 spec, we no choice for
		 * servers that don't support the SIZE command.
		 */
		if (ftp_open_data_connection(flar) != 0) {
			write_debug(FLASH_DEBUG,
			    "get_size: can't open data connection");

			return (FlErrNetworkError);
		}

		if (send_command(flar, &sizereply, "LIST %s",
		    basenamep) != PRELIM) {
			write_notice(ERRMSG, ARCHIVE_SERVER_REPLY, sizereply);
			ftp_close_data_connection(flar);
			return (FlErrNetworkError);
		}

		if (!ftp_accept_data_connection(flar)) {
			write_debug(FLASH_DEBUG,
			    "get_size: can't accept connection");
			ftp_close_data_connection(flar);
			return (FlErrNetworkError);
		}
		if ((listfp = fdopen(FTPDATA(flar)->data_fd, "r")) == NULL) {
			write_debug(FLASH_DEBUG, "Cannot open data stream");
			ftp_close_data_connection(flar);
			return (FlErrNetworkError);
		}

		if (fgets(line, FTP_LINEBUF_SIZE, listfp) == NULL) {
			write_debug(FLASH_DEBUG, "Can't read LIST line");
			ftp_close_data_connection(flar);
			return (FlErrNetworkError);
		}

		/* strip any extra whitespace from the string */

		trim_whitespace(line);
		write_debug(FLASH_DEBUG,
		    "get_size: READ LINE: \"%s\"", line);

		/* make a copy, since ftp_parse_size might mess with it */
		strcpy(linecopy, line);
		if ((size = ftp_parse_size(line)) < 0) {
			/* Tell the user */
			write_notice(ERRMSG, MSG0_FTP_CANT_PARSE_SIZE,
			    linecopy);
			ftp_close_data_connection(flar);
			return (FlErrUnsupported);
		}

		if (get_reply(flar, NULL, 0) != COMPLETE) {
			write_debug(FLASH_DEBUG,
			    "get_size: can't complete LIST");
			ftp_close_data_connection(flar);
			return (FlErrNetworkError);
		}

		ftp_close_data_connection(flar);
	}

	FTPDATA(flar)->end = flar->ident.arc_size = size;

	return (FlErrSuccess);
}

/*
 * Name:		alarm_handler
 * Description:	Called when timeout occurs.
 * Scope:	private
 * Arguments:	sig	- The signal received
 *			  The archive to check
 */
/*ARGSUSED*/
static void
alarm_handler(int sig)
{
	write_debug(FLASH_DEBUG, "alarm_handler triggered");
}

/*
 * Name:	send_command
 * Description: 	Formats and sends a command down the control
 *		channel.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive in progress
 *		response	- holds the response to the command
 *		fmt	- the "printf"-style format
 *		...	- the arguments to the format
 * Returns:	first digit of response code from server, or -1 on error.
 */
static int
send_command(FlashArchive *flar, char **response, char *fmt, ...)
{
	int r;
	va_list ap;
	char *cmdbuf;
	int cmdsize;
	int cmdsizeguess;
	int errorcode;

	/* set up default return cmd used when alarm() is triggered */
	if (response != NULL) {
		*response = MSG0_FTP_DEFAULT_TIMEOUT;
	}

	va_start(ap, fmt);

	/* guess at the size, then re-size if necessary */
	cmdsizeguess = strlen(fmt) + 1;
	cmdbuf = (char *)xmalloc(cmdsizeguess * sizeof (char));
	if ((cmdsize =
	    vsnprintf(cmdbuf, cmdsizeguess, fmt, ap)) > (cmdsizeguess - 1)) {
		va_end(ap);
		va_start(ap, fmt);
		cmdbuf = (char *)xrealloc(cmdbuf,
		    (cmdsize + 1) * sizeof (char));
		vsnprintf(cmdbuf, cmdsize + 1, fmt, ap);
	}
	va_end(ap);

	write_debug(FLASH_DEBUG,
	    "svc_flash_ftp: send: \"%s\"", cmdbuf);

	if (FTPDATA(flar)->ctrl_out == NULL) {
		write_debug(FLASH_DEBUG,
		    "No control connection for command %s",
		    cmdbuf);
		return (-1);
	}

	cmdbuf = (char *)xrealloc(cmdbuf,
	    (cmdsize + 2 + 1) * sizeof (char));
	strcat(cmdbuf, "\r\n");

	/* Start the timer */
	(void) alarm(flar->spec.FTP.timeout);

	/* send the command */
	if (output_command(flar, cmdbuf) < strlen(cmdbuf)) {
	    errorcode = errno;
	    free(cmdbuf);
	    errno = errorcode;
	    write_debug(FLASH_DEBUG,
		"send_command: write error");
	    return (errno == EINTR ? -2 : -1);
	}

	/* Stop the timer */
	(void) alarm(0);

	r = get_reply(flar, response, strncmp(cmdbuf, "QUIT", 4) == 0);
	free(cmdbuf);

	return (r);
}

/*
 * Name:	output_command
 * Description:	Sends the formatted command through
 *		the control connection.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive in progress
 *		cmd    	- The command to send
 * Returns:	the amount of data actually sent.
 */
static int
output_command(FlashArchive *flar, char *cmd)
{
	int amtwritten;

	amtwritten = fwrite(cmd, strlen(cmd), 1, FTPDATA(flar)->ctrl_out);
	fflush(FTPDATA(flar)->ctrl_out);
	return (amtwritten * strlen(cmd));
}

/*
 * Name:		get_reply
 * Description:	Verifies the archive size.  This code is mostly
 *		taken from the Solaris FTP server.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to check
 *		reply	- buffer to hold reply string
 *		expecteof	- if false, and we get
 *			an EOF after reply,
 *			it's considered an error.
 * Returns:	1-5 for FTP return code classes,
 *		-1: connection failure
 *		-2: connection timeout
 */
static int
get_reply(FlashArchive *flar, char **reply, int expecteof)
{
	register int c, n;
	register int dig;
	int code;
	int originalcode = 0, continuation = 0;
	int pflag = 0;
	int	len;
	char	pasv[64];
	char *pt = pasv;
	static char reply_text[BUFSIZ];
	char *cp;

	if (!FTPDATA(flar)->ctrl_in) {
		write_debug(FLASH_DEBUG,
		    "get_reply: no control open");
		return (-1);
	}
	for (;;) {
		dig = n = code = 0;
		cp = reply_text;
		(void) alarm(flar->spec.FTP.timeout);
		while ((c = fgetwc(FTPDATA(flar)->ctrl_in)) != '\n') {
			if (c == WEOF) {
				alarm(0);
				return ((errno == EINTR) ? -2: -1);
			}

			if (c == IAC) {	/* handle telnet commands */
				switch (c = fgetwc(FTPDATA(flar)->ctrl_in)) {
				case WILL:
				case WONT:
					c = fgetwc(FTPDATA(flar)->ctrl_in);
					fprintf(FTPDATA(flar)->ctrl_out,
					    "%c%c%wc", IAC,
					    WONT, c);
					(void) fflush(FTPDATA(flar)->ctrl_out);
					break;
				case DO:
				case DONT:
					c = fgetwc(FTPDATA(flar)->ctrl_in);
					fprintf(FTPDATA(flar)->ctrl_out,
					    "%c%c%wc", IAC,
					    DONT, c);
					(void) fflush(FTPDATA(flar)->ctrl_out);
					break;
				case WEOF:
					alarm(0);
					write_debug(FLASH_DEBUG,
					    "fgetwc timed out");
					return ((errno == EINTR) ? -2: -1);
				default:
					break;
				}
				alarm(flar->spec.FTP.timeout);
				continue;
			}
			dig++;
			if (c == EOF) {
				if (expecteof) {
					alarm(0);
					code = 221;
					if (reply != NULL)
						*reply =
						    MSG0_FTP_TRANSFER_COMPLETE;
					return (2);
				}
				ftp_close_control_connection(flar);
				write_debug(FLASH_DEBUG,
				    "get_reply: svc_flash_ftp: 421 lost peer");
				code = 421;
				alarm(0);
				return (-1);
			}
			if (dig < 4 && isascii(c) && isdigit(c))
				code = code * 10 + (c - '0');
			if (!pflag && code == 227)
				pflag = 1;
			if (dig > 4 && pflag == 1 && isascii(c) && isdigit(c))
				pflag = 2;
			if (pflag == 2) {
				if (c != '\r' && c != ')') {
					char mb[MB_LEN_MAX];
					int avail;

					/*
					 * space available in pasv[], accounting
					 * for trailing NULL
					 */
					avail = &pasv[sizeof (pasv)] - pt - 1;

					len = wctomb(mb, c);
					if (len <= 0 && avail > 0) {
						*pt++ = (unsigned char)c;
					} else if (len > 0 && avail >= len) {
						bcopy(mb, pt, (size_t)len);
						pt += len;
					} else {
						/*
						 * no room in pasv[];
						 * close connection
						 */
						alarm(0);
						write_debug(FLASH_DEBUG,
						    "get_reply: Reply too "
						    "long-closing connection");
					ftp_close_control_connection(flar);
						if (reply != NULL)
							*reply =
						    MSG0_FTP_REPLY_LONG;
						return (4);
					}
				} else {
					*pt = '\0';
					pflag = 3;
				}
			}
			if (dig == 4 && c == '-') {
				if (continuation)
					code = 0;
				continuation++;
			}
			if (n == 0)
				n = c;
			if (cp < &reply_text[sizeof (reply_text) - 1]) {
				*cp++ = (char)c;
			}
			alarm(flar->spec.FTP.timeout);
		}
		if (continuation && code != originalcode) {
			if (originalcode == 0)
				originalcode = code;
			continue;
		}
		*cp = '\0';

		alarm(0);

		/* trim off any trailing whitespace */
		cp--;
		while (isspace(*cp)) *cp-- = '\0';

		if (code == 421 || originalcode == 421)
			ftp_close_control_connection(flar);
		if (reply != NULL)
		    *reply = reply_text;
		write_debug(FLASH_DEBUG,
		    "get_reply: rc: %d reply: %s", code,
		    reply_text);
		return (n - '0');
	}

}

/*
 * Name:	_progress_restart
 * Description:	Send a connection restart message to the front end UI (if one
 *		has been registered)
 * Scope:	private
 * Arguments:	reason	- [RO] (FLARRestartReason)
 *			  The reason for the restart
 * Returns:	none
 */
static void
_progress_restart(FLARRestartReason reason)
{
	FLARProgress prog;

	if (!progress_callback) {
		return;
	}

	prog.type = FLARPROGRESS_RESTART;
	prog.data.restart.reason = reason;

	progress_callback(progress_userdata, &prog);
}
