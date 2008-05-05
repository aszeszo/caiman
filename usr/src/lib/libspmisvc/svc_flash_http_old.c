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
 * Module:	svc_flash_http_old.c
 * Group:	libspmisvc
 * Description:
 *	The functions as a backup implementation of HTTP when the latest
 *	implementation is not found
 *
 *	This code gets a bit hairy.
 *
 *	At the highest level of abstraction, this code reads an archive from
 *	an HTTP server.  This is complicated a bit by the need to be able to
 *	recover from the loss of the HTTP server.  In this case, the connection
 *	must be reestablished and the retrieval resumed.  A further complication
 *	is the need to read each byte only once.
 *
 *	First, we send the request.  Things begin to get scary once data starts
 *	coming from the server.  We have one read buffer - readbuf, but two
 *	routines that fill it.  The first filler, _http_read_headers,
 *	parses the headers, saving and verifying interesting information
 *	(primarily the file size and variations on the size).  The second
 *	filler is _http_read_block, which is used to feed the routines that
 *	actually process the archive.  _http_read_block determines whether a new
 *	block needs to be read to satisfy the request and returns the unread
 *	fragment of the existing block or reads a new one as appropriate.
 *
 *	When reading the identification section,
 *	_h_r_b is called by a layer that marshals the data into lines.  When
 *	extracting the files section, it is called directly to bulk-read the
 *	archive.  Either way, _h_r_b is fully responsible for tracking the
 *	progress through the archive and restarting the connection if need be.
 *
 *	We have two readbuf fillers because one (_h_r_h) doesn't charge against
 *	the progress through the archive, whereas the other one (_h_r_b) does.
 *	Merging the two would complicate the code for marginal gain.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
#include <unistd.h>
#include <macros.h>
#include <ctype.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>

#include "spmicommon_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

/*
 * Local datatypes
 */

/* The size of the chunks to be read from the server */
#define	READBUF_SIZE	65535

/* The maximum redirects we will allow */
#define	MAX_REDIRS	5

/* HTTP/1.1 request type */
typedef enum {
	HTTP_REQ_TYPE_HEAD = 1,
	HTTP_REQ_TYPE_GET
} HTTPRequestType;

/* Used to store the result of a request */
typedef struct {
	int	code;
	char	*statusmsg;
} RequestStatus;

/* HTTP retrieval-specific private data */
typedef struct {
	int	fd;
	off_t	start;
	off_t	cur;
	off_t	end;
	URL	*actloc;

	/* Where to connect */
	char	*targethost;
	int	targetport;

	/* Read (rhymes with bread) data */
	char	*readbuf;
	int	rbcounted;	/* Has this block been accounted for? */
	char	*rbptr;
	char	*rbendptr;

	/* The HTTP header currently being read */
	char	*curhdr;
	int	curhdrnxt;
	int	curhdrlen;

} HTTPData;
#define	HTTPDATA(flar)	((HTTPData *)flar->data)

/* Macros for determining HTTP response codes */
#define	IS_HTTP_REDIRECT(x)	((x / 100) == 3)
#define	IS_HTTP_OK(x)		((x / 100) == 2)

#define	READBUF(flar)	(HTTPDATA(flar)->readbuf)
#define	RBPTR(flar)	(HTTPDATA(flar)->rbptr)
#define	RBENDPTR(flar)	(HTTPDATA(flar)->rbendptr)
#define	RBCOUNTED(flar)	(HTTPDATA(flar)->rbcounted)

#define	CURHDR(flar)	(HTTPDATA(flar)->curhdr)
#define	CURHDRNXT(flar)	(HTTPDATA(flar)->curhdrnxt)
#define	CURHDRLEN(flar)	(HTTPDATA(flar)->curhdrlen)

/*
 * Local global data
 */

/* Progress information messages for the front end */
static TCallback	*progress_callback;
static void		*progress_userdata;

/*
 * Local functions
 */

static FlashError	_http_head_file(FlashArchive *, RequestStatus *);
static int		_http_open_connection(FlashArchive *);
static int		_http_send_request(FlashArchive *, RequestStatus *,
					HTTPRequestType);
static int		_http_request_file(FlashArchive *, HTTPRequestType);
static int		_http_read_headers(FlashArchive *, RequestStatus *);
static int		_http_close_connection(FlashArchive *);
static FlashError	_http_read_from_block(FlashArchive *, char **, int *,
					int *);
static FlashError	_http_read_block(FlashArchive *, size_t *);
static void		_http_flush_block(FlashArchive *);
static int		_save_header_part(FlashArchive *, char *, char *);
static int		_process_status_header(FlashArchive *, RequestStatus *);
static int		_process_normal_header(FlashArchive *);
static void		_reset_header(FlashArchive *);
static void		_free_header(FlashArchive *);
static void		_alarm_handler(int);
static void		_progress_restart(FLARRestartReason);
static void		_free_http_data(HTTPData *);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARHTTPOpen
 * Description:	The HTTP-specific archive opening routine.  This routine makes
 *		a connection to the HTTP server, and positions the archive
 *		descriptor at the current offset.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be opened
 * Returns:	FlErrSuccess	- The archive was opened successfully
 */
FlashError
_old_FLARHTTPOpen(FlashArchive *flar)
{
	RequestStatus reqstat;
	FlashError status;
	char *urlstr;
	int redir = 0;

	flar->data = xmalloc(sizeof (HTTPData));
	HTTPDATA(flar)->start = -1;
	HTTPDATA(flar)->cur = -1;
	HTTPDATA(flar)->end = -1;
	HTTPDATA(flar)->actloc = flar->spec.HTTP.url;
	URLAddRef(flar->spec.HTTP.url);

	/* These will be set by _http_open_connection */
	HTTPDATA(flar)->targethost = NULL;
	HTTPDATA(flar)->targetport = -1;

	READBUF(flar) = xmalloc(READBUF_SIZE);
	RBCOUNTED(flar) = 0;
	RBPTR(flar) = NULL;
	RBENDPTR(flar) = NULL;

	CURHDR(flar) = NULL;
	CURHDRNXT(flar) = 0;
	CURHDRLEN(flar) = 0;

	for (;;) {
		/*
		 * Does the file exist?  Can we read it?
		 * Do a HEAD to find out
		 */
		if ((status = _http_head_file(flar, &reqstat))
							!= FlErrSuccess) {
			free(flar->data);
			return (status);
		}

		if (get_trace_level() > 0) {
			write_status(LOGSCR, LEVEL1, MSG0_HTTP_STATUS,
			    "HEAD", reqstat.code,
			    (HTTPDATA(flar)->end == -1 ? -1 :
				HTTPDATA(flar)->end + 1));
		}

		/*
		 * If we got a redirection, let the user know, and retry the
		 * HEAD.  We only support redirections that give us a Location
		 * header.
		 */
		if (IS_HTTP_REDIRECT(reqstat.code)) {
			if (!HTTPDATA(flar)->actloc) {
				write_notice(ERRMSG, MSG0_HTTP_REDIR_WO_LOC,
				    reqstat.code);
				_free_http_data(flar->data);
				return (FlErrCouldNotOpen);
			}

			if (++redir > MAX_REDIRS) {
				write_notice(ERRMSG,
				    MSG0_HTTP_TOO_MANY_REDIRS, MAX_REDIRS);
				_free_http_data(flar->data);
				return (FlErrCouldNotOpen);
			}

			/* Try, try again */
			URLString(HTTPDATA(flar)->actloc, &urlstr);
			write_status(LOGSCR, LEVEL1, MSG0_HTTP_REDIRECT,
			    urlstr);
			free(urlstr);

			continue;

		} else if (!IS_HTTP_OK(reqstat.code)) {
			write_notice(ERRMSG, MSG0_HTTP_CANT_ACCESS_ARCHIVE,
			    reqstat.code,
			    (reqstat.statusmsg ? reqstat.statusmsg : ""));
			_free_http_data(flar->data);
			return (FlErrCouldNotOpen);
		}

		/* We got the file */
		break;
	}

	/*
	 * Do we have a size for the file?  We can't extract if we don't know
	 * the size.
	 */
	if (HTTPDATA(flar)->end == -1) {
		write_notice(ERRMSG, MSG0_HTTP_NEED_ARCHIVE_SIZE);
		free(flar->data);
		return (FlErrCouldNotOpen);
	}

	HTTPDATA(flar)->start = HTTPDATA(flar)->cur = 0;

	/*
	 * Tell archive its size, in case the ident section can't
	 */
	flar->ident.arc_size = HTTPDATA(flar)->end;
	flar_set_open(flar);

	return (FlErrSuccess);
}

/*
 * Name:	FLARHTTPReadLine
 * Description:	Read a line from the archive.  The line read will be returned in
 *		a statically-allocated buffer that the caller must not modify.
 *		If the timeout elapses, the connection will be re-established
 *		if possible.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The opened Flash archive from which to read
 *		bufptr	- [RO, *W] (char **)
 *			  Where the pointer to the statically-allocated buffer
 *			  containing the read line is returned.
 * Returns:	FlErrSuccess	- Read successful, *bufptr points to line
 */
FlashError
_old_FLARHTTPReadLine(FlashArchive *flar, char **bufptr)
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
		linebuf = xmalloc(READBUF_SIZE);
		linebuflen = READBUF_SIZE;
	}
	curlboff = 0;

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, _alarm_handler);

	/* while line not read */
	do {

		/* read another block */
		if ((status = _http_read_from_block(flar, &readblock, &lenread,
						&foundeol)) != FlErrSuccess) {
			if (status == FlErrEndOfFile &&
			    HTTPDATA(flar)->cur <= HTTPDATA(flar)->end) {
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
 * Name:	FLARHTTPExtract
 * Description:	The HTTP-specific archive extraction routine.  This routine
 *		sends, in bulk, all of the data remaining in the archive
 *		beyond the current location to the passed stream.  If the
 *		timeout occurs, the archive will be reopened at the current
 *		position.  The amount of data read from the archiev as
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
 */
FlashError
_old_FLARHTTPExtract(FlashArchive *flar, FILE *xfp, TCallback *cb, void *data)
{
	FLARProgress prog;
	FlashError status;
	FlashError rc;
	size_t amtread;
	size_t last;
	void (*old_handler)(int);

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, _alarm_handler);

	/* Set up the progress callback */
	progress_callback = cb;
	progress_userdata = data;

	prog.type = FLARPROGRESS_STATUS;
	prog.data.status.total =
	    HTTPDATA(flar)->end -
	    (HTTPDATA(flar)->cur -
		(RBENDPTR(flar) - RBPTR(flar))) + 1;
	prog.data.status.cur = last = 0;
	prog.data.status.nfiles = -1;
	cb(data, (void *)&prog);

	for (;;) {
		status = _http_read_block(flar, &amtread);

		if (status == FlErrEndOfFile) {
			if (HTTPDATA(flar)->cur <= HTTPDATA(flar)->end) {
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

		if (fwrite(RBPTR(flar), 1, amtread, xfp) < amtread) {
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
		_http_flush_block(flar);
	}

	/* Disable the timeout timer */
	(void) alarm(0);
	(void) signal(SIGALRM, old_handler);

	progress_callback = NULL;

	return (rc);
}

/*
 * Name:	FLARHTTPClose
 * Description:	The HTTP-specific archive closing routine.
 * Scope:	Flash internal
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive to be closed
 * Returns:	FlErrSuccess	- The archive was closed successfully
 *		FlErrInternal	- The archive was not open
 */
FlashError
_old_FLARHTTPClose(FlashArchive *flar)
{
	if (_http_close_connection(flar) < 0) {
		return (FlErrInternal);
	}

	if (HTTPDATA(flar)->readbuf) {
		free(HTTPDATA(flar)->readbuf);
	}
	free(HTTPDATA(flar));
	flar->data = NULL;

	return (FlErrSuccess);
}

/* ---------------------- private functions ----------------------- */

/*
 * Name:	_http_head_file
 * Description:	Send an HTTP HEAD request to get the accessibility status
 *		for a file.  If the file exists, the size of the file will
 *		also be noted for later comparison.  The status of the file
 *		will be returned in the preallocated RequestStatus buffer
 *		passed by the caller.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being HEADed
 *		reqstat	- [RO, *WO] (RequestStatus *)
 *			  Preallocated buffer for storage of the request status
 * Returns:	FlErrSuccess		- The HEAD request succeeded.  reqstat
 *					  is valid.
 *		FlErrCouldNotOpen	- The server could not be contacted.
 */
static FlashError
_http_head_file(FlashArchive *flar, RequestStatus *reqstat)
{
	void (*old_handler)(int);
	int errcode = 0;
	FlashError status = FlErrSuccess;

	/* Set up the handler for the timeout (if any) */
	old_handler = sigset(SIGALRM, _alarm_handler);

	/* Open the connection */
	if (_http_open_connection(flar) == 0) {
		/* Send the request */
		status = _http_send_request(flar, reqstat, HTTP_REQ_TYPE_HEAD);

		/* Just in case */
		(void) alarm(flar->spec.HTTP.timeout);

		(void) _http_close_connection(flar);
	} else {
		errcode = errno;

		status = FlErrCouldNotOpen;
	}

	/* Disable the timeout timer */
	(void) alarm(0);
	(void) signal(SIGALRM, old_handler);

	if (status != FlErrSuccess) {
		write_notice(ERRMSG, MSG0_CANNOT_CONNECT,
		    (HTTPDATA(flar)->targethost ? HTTPDATA(flar)->targethost :
			"**NO HOST**"),
		    HTTPDATA(flar)->targetport,
		    strerror(errcode));
		return (FlErrCouldNotOpen);
	}

	_http_flush_block(flar);

	return (FlErrSuccess);
}

/*
 * Name:	_http_send_request
 * Description:	Send an HTTP request to an HTTP server and read the resulting
 *		headers.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being requested
 *		reqstat	- [RO, *WO] (RequestStatus *)
 *			  Where the results of the request will be returned
 *		type	- [RO] (HTTPRequestType)
 *			  The type of request (HEAD or GET)
 * Returns:	0	- The request succeeded
 *		-1	- The request failed.  errno has been set.
 */
static int
_http_send_request(FlashArchive *flar, RequestStatus *reqstat,
    HTTPRequestType type)
{
	if (_http_request_file(flar, type) < 0 ||
	    _http_read_headers(flar, reqstat) < 0) {
		return (-1);
	}

	return (0);
}

/*
 * Name:	_http_request_file
 * Description:	Create and send the actual HTTP request to the server
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being requested
 *		type	- [RO] (HTTPRequestType)
 *			  The type of request being made (HEAD or GET)
 * Returns:	0	- The request was sent successfully
 *		-1	- An error ocurred while sending the request.  errno
 *			  has been set.
 */
static int
_http_request_file(FlashArchive *flar, HTTPRequestType type)
{
	char *request = NULL;
	int requestlen;
	char *reqtypename = NULL;
	int errorcode;

	/* Determine the name for the request type */
	switch (type) {
	case HTTP_REQ_TYPE_GET:
		reqtypename = "GET";
		break;
	case HTTP_REQ_TYPE_HEAD:
		reqtypename = "HEAD";
		break;
	default:
		errno = EINVAL;
		return (-1);
	}

	/*
	 * Size the request.
	 *
	 * With proxy:
	 *   reqtypename + " http://" + host + ":" + port + path +
	 *						" HTTP/1.1\n" +
	 * Without proxy:
	 *   reqtypename + " " + path + " HTTP/1.1\n" +
	 */
	requestlen = strlen(reqtypename) + 8 +
	    strlen(HTTPDATA(flar)->actloc->host) + 1 +
	    count_digits(HTTPDATA(flar)->actloc->port) +
	    strlen(HTTPDATA(flar)->actloc->path) + 10;

	/*
	 * Plus the rest:
	 *   "Host: " + targethost + ":" + count_digits(port) + "\n" +
	 *   "Connection: close\n" plus trailing "\n\0"
	 */
	requestlen += 6 + strlen(HTTPDATA(flar)->actloc->host) + 1 +
	    count_digits(HTTPDATA(flar)->actloc->port) + 1 +
	    18 + 2;
	request = xmalloc(requestlen);

	/* The request line */
	if (flar->spec.HTTP.proxyhost != NULL) {
		(void) sprintf(request,
		    "%s http://%s:%d%s HTTP/1.1\n",
		    reqtypename,
		    HTTPDATA(flar)->actloc->host,
		    HTTPDATA(flar)->actloc->port,
		    HTTPDATA(flar)->actloc->path);
	} else {
		(void) sprintf(request,
		    "%s %s HTTP/1.1\n",
		    reqtypename,
		    HTTPDATA(flar)->actloc->path);
	}

	/* Ancillary headers */
	(void) sprintf(request + strlen(request),
	    "Host: %s:%d\n"
	    "Connection: close\n",
	    HTTPDATA(flar)->actloc->host,
	    HTTPDATA(flar)->actloc->port);

	/*
	 * We only send the range header on GET requests
	 *
	 * "Range: bytes=" + from + "-" + end + "\n" or
	 * "Range: bytes=" + from + "-" +       "\n"
	 */
	if (type == HTTP_REQ_TYPE_GET && HTTPDATA(flar)->cur >= 0) {
		requestlen += 13 + count_digits(HTTPDATA(flar)->cur) + 1 + 1;
		if (HTTPDATA(flar)->end >= 0) {
			requestlen += count_digits(HTTPDATA(flar)->end);
		}

		request = xrealloc(request, requestlen);

		(void) sprintf(request + strlen(request),
		    (HTTPDATA(flar)->end >= 0 ? "%s%d-%d\n" : "%s%d-\n"),
		    "Range: bytes=",
		    HTTPDATA(flar)->cur, HTTPDATA(flar)->end);
	}

	/*
	 * Authorization is added only if provided
	 *
	 * "Authorization: Basic " + authencstr + "\n"
	 */
	if (HTTPDATA(flar)->actloc->auth_type == URLAuthTypeBasic) {
		char *authstr;
		char *authencstr;

		authstr = (char *)xmalloc(
		    strlen(HTTPDATA(flar)->actloc->auth.basic.user) + 1 +
		    strlen(HTTPDATA(flar)->actloc->auth.basic.password) + 1);
		(void) sprintf(authstr, "%s:%s",
		    HTTPDATA(flar)->actloc->auth.basic.user,
		    HTTPDATA(flar)->actloc->auth.basic.password);

		authencstr = EncodeBase64(authstr, strlen(authstr));

		requestlen += 21 + strlen(authencstr) + 1;
		request = xrealloc(request, requestlen);

		(void) sprintf(request + strlen(request),
		    "Authorization: Basic %s\n", authencstr);

		free(authencstr);
		free(authstr);
	}

	(void) strcat(request, "\n");

	/* Start the timer */
	(void) alarm(flar->spec.HTTP.timeout);

	/* Make and send the request */
	if (write(HTTPDATA(flar)->fd, request, strlen(request)) <
							strlen(request)) {
		errorcode = errno;
		free(request);
		errno = errorcode;
		return (-1);
	}
	free(request);

	(void) alarm(0);

	return (0);
}

/*
 * Name:	_http_read_headers
 * Description:	Read the HTTP headers resulting from an HTTP request.  The
 *		headers consist of an initial status line followed by
 *		`key: value' pairs.  Pairs relating to the archive size are
 *		noted if the size is unknown, and verified if it is.  A
 *		midstream change in the archive size is a fatal error.
 *		This routine reads the headers from blocks, correctly handling
 *		headers that span blocks.  Processing concludes when "\n\n"
 *		is encountered.  At this point, there may be unread data in
 *		readbuf for other routines to process.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being requested
 *		reqstat	- [RO, *RW] (RequestStatus *)
 *			  Where the results of the request will be returned
 * Returns:	0	- The headers were processed without error
 *		-1	- An error occurred during header processing.  errno
 *			  has been set.
 */
static int
_http_read_headers(FlashArchive *flar, RequestStatus *reqstat)
{
	int amtread;
	int inhdrblk = 1;
	int inhdrblkend = 0;	/* In potential end of header block */
	int firsthdr = 1;
	int idx;
	int rc;
	char *nlptr;

	/*
	 * Forward through the header (look for the first \n\n), then
	 * start printing the rest, unless we're supposed to be quiet.
	 */
	while (inhdrblk) {

		(void) alarm(flar->spec.HTTP.timeout);

		/* Read the block */
		if ((amtread = read(HTTPDATA(flar)->fd,
				    READBUF(flar),
				    READBUF_SIZE)) <= 0) {
			return ((errno == EINTR) ? -2 : -1);
		}
		RBCOUNTED(flar) = 0;
		RBPTR(flar) = READBUF(flar);
		RBENDPTR(flar) = READBUF(flar) + (amtread - 1);

		/* Reset the timeout timer */
		(void) alarm(0);

		if (inhdrblk && inhdrblkend) {
			/*
			 * We were part way into a potential header block end
			 * when we were doing the last read.  See if this is
			 * in fact the end of a header block.
			 */
			while (RBPTR(flar) <= RBENDPTR(flar) &&
			    inhdrblk &&
			    (*RBPTR(flar) == '\r' || *RBPTR(flar) == '\n')) {
				if (*RBPTR(flar) == '\n') {
					if (++inhdrblkend == 2) {
						/*
						 * This is the end of the
						 * header block.
						 */
						inhdrblk = 0;
						inhdrblkend = 0;
					}
				}
				RBPTR(flar)++;
			}

			/* If we fell off the end of the block, start over */
			if (RBPTR(flar) > RBENDPTR(flar)) {
				continue;
			} else {
				/*
				 * We didn't fall off the end, so we must have
				 * hit something that's neither a \r nor a \n.
				 * Let the rest of the code deal with it.
				 */
				inhdrblkend = 0;
			}
		}

		if (inhdrblk) {
			/*
			 * Still reading normal headers.  Try to find the
			 * end of the current one in this block.
			 */
			idx = 0;

			if (!(nlptr = memchr(RBPTR(flar), '\n', amtread))) {
				/*
				 * We're in a header that starts before this
				 * block and doesn't end until after this
				 * block.  Save the part we see, and jump
				 * to the next read.
				 */
				if (_save_header_part(flar, RBPTR(flar),
				    READBUF(flar) + (amtread - 1)) < 0) {
					return (-1);
				}
				continue;
			}

			/* Found a newline */
			do {
				idx = nlptr - READBUF(flar);

				/* Process this header */
				if (RBPTR(flar) != nlptr) {
					/*
					 * The start of this block contains the
					 * end of the current header.
					 * of the current header
					 */
					if (_save_header_part(flar,
					    RBPTR(flar), nlptr - 1) < 0) {
						return (-1);
					}
				}

				if (firsthdr) {
					if (_process_status_header(flar,
								reqstat) < 0) {
						write_notice(ERRMSG,
						    MSG0_HTTP_INVALID_STATUS,
						    CURHDR(flar));
						return (-1);
					}
					firsthdr = 0;

					/*
					 * If we got a redirection, we need to
					 * clear out the actual URL field so
					 * we can tell if the remaining headers
					 * gave us a location or not.  If said
					 * headers give us a location, actloc
					 * will be repopulated.
					 */
					if (IS_HTTP_REDIRECT(reqstat->code)) {
						FreeURL(HTTPDATA(flar)->actloc);
						HTTPDATA(flar)->actloc = NULL;
					}
				} else {
					rc = _process_normal_header(flar);
					if (rc == -1) {
						write_notice(ERRMSG,
						    MSG0_HTTP_INVALID_HEADER,
						    CURHDR(flar));
					}

					if (rc < 0) {
						return (-1);
					}
				}
				_reset_header(flar);

				if (idx == amtread - 1) {
					/*
					 * We're at the end of the block. Note
					 * this for the next trip through.
					 */
					inhdrblkend = 1;
					RBPTR(flar) = READBUF(flar) + amtread;
					break;

				} else if (READBUF(flar)[idx + 1] == '\r') {
					if (idx == amtread - 2) {
						/*
						 * No space left to read, but
						 * we're probably in the middle
						 * of an end of header block.
						 */
						inhdrblkend = 1;
						break;
					} else if (READBUF(flar)[idx + 2] ==
									'\n') {
						/* The end. */
						RBPTR(flar) =
						    READBUF(flar) + idx + 3;
						inhdrblk = 0;
						break;
					} else {
						/*
						 * Not an end of header block,
						 * but not quite legal either.
						 * You can't have \r's in
						 * headers.  Skip past the \r.
						 */
						RBPTR(flar) = nlptr + 2;
					}

				} else if (READBUF(flar)[idx + 1] == '\n') {
					/*
					 * In the middle of the block, and the
					 * next character is a \n.  That's the
					 * end of the header block.
					 */
					RBPTR(flar) = READBUF(flar) + idx + 2;
					inhdrblk = 0;
					break;
				} else {
					/*
					 * Middle of the block, and the next
					 * character isn't another \n.  That
					 * means we're in a header block, and
					 * are starting a new header.  Save
					 * its beginning, and advance hbptr so
					 * we can start the search anew.
					 */
					RBPTR(flar) = nlptr + 1;
				}

			} while ((nlptr = memchr(RBPTR(flar), '\n',
			    amtread - idx - 1)));

			/*
			 * We fell off the end.  If we didn't find the end of
			 * the headers, and didn't stop at the end of a header,
			 * then we fell off while in the middle of a header.
			 * Save the part we see.
			 */
			if (inhdrblk && !inhdrblkend) {
				if (_save_header_part(flar, RBPTR(flar),
				    READBUF(flar) + (amtread - 1)) < 0) {
					return (-1);
				}
			}
		}
	}

	return (0);
}

/*
 * Name:	_save_header_part
 * Description:	Save part of a header.  If some of the header has already
 *		been read and saved, the new part will be appended to the
 *		existing part.  Trailing carriage returns are removed from
 *		saved headers.
 * Scope:	private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive that owns the connection generating this
 *			  header
 *		start	- [RO, *RO] (char *)
 *			  A pointer to the first character in the header part
 *		end	- [RO, *RO] (char *)
 *			  A pointer to the last character in the header part
 * Returns:	0	- The part was saved successfully
 *		-1	- An error occurred saving the part.  errno has been set
 */
static int
_save_header_part(FlashArchive *flar, char *start, char *end)
{
	int needlen;

	needlen = CURHDRNXT(flar) + (end - start + 1);
	if (needlen + 1 > CURHDRLEN(flar)) {
		if (!(CURHDR(flar) =
		    (char *)realloc(CURHDR(flar), needlen + 1))) {
			return (-1);
		}
		CURHDRLEN(flar) = needlen + 1;
	}
	(void) memcpy(CURHDR(flar) + CURHDRNXT(flar), start, (end - start + 1));

	CURHDRNXT(flar) = needlen;
	if (*end == '\r') {
		/* There's a trailing \r - remove it */
		CURHDRNXT(flar)--;
	}
	CURHDR(flar)[CURHDRNXT(flar)] = '\0';

	return (0);
}

/*
 * Name:	_reset_header
 * Description:	Reset any saved header parts
 * Scope:	private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive that owns these connection headers.
 * Returns:	none
 */
static void
_reset_header(FlashArchive *flar)
{
	CURHDRNXT(flar) = 0;
	CURHDR(flar)[0] = '\0';
}

/*
 * Name:	_free_header
 * Description:	Free storage used to save header parts
 * Scope:	private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive that owns these connection headers.
 * Returns:	none
 */
static void
_free_header(FlashArchive *flar)
{
	free(CURHDR(flar));
	CURHDR(flar) = NULL;
	CURHDRNXT(flar) = 0;
	CURHDRLEN(flar) = 0;
}	

/*
 * Name:	_process_status_header
 * Description:	Parse a status header (RFC 2068 Section 6.1) from an HTTP
 *		response, populating a passed RequestStatus structure as
 *		appropriate.
 * Scope:	private
 * Arguments:	d	- [RO, *RO] (HTTPData *)
 *			  HTTP-specific archive status data
 *		rs	- [RO, *RW] (RequestStatus *)
 *			  Where the results of the request will be returned
 * Returns:	0	- The header was parsed correctly
 *		-1	- An error occurred during parsing.  rs has not been set
 */
static int
_process_status_header(FlashArchive *flar, RequestStatus *rs)
{
	HTTPData *d;
	char *c, *c2;
	int code;
	char *msg;

	d = HTTPDATA(flar);

	/*
	 * This had better be the request status.  If not, we're looking
	 * at an invalid response.
	 */
	if (!ci_strneq(d->curhdr, "HTTP/", 5)) {
		return (-1);
	}

	/* Skip to the code */
	for (c = d->curhdr + 5; *c && !isspace(*c); c++);
	for (; *c && isspace(*c); c++);

	if (!*c) {
		return (-1);
	}

	/* Make sure it's three digits */
	for (c2 = c; *c2 && isdigit(*c2); c2++);
	if (c2 - c != 3) {
		return (-1);
	}
	code = atoi(c);

	/* Save the message */
	msg = NULL;
	if (*c2) {
		for (c = c2; isspace(*c); c++);
		if (*c) {
			msg = strdup(c);
		}
	}

	rs->code = code;
	rs->statusmsg = msg;

	return (0);
}

/*
 * Name:	_process_normal_header
 * Description:	Process a non-status HTTP response header.  If the header is
 *		related to the size of the archive, the sizing information is
 *		saved or verified as appropriate.
 * Scope:	private
 * Arguments:	d	- [RO, *RO] (HTTPData *)
 *			  HTTP-specific archive status data
 * Returns:	0	- The header was parsed correctly
 *		-1	- Parsing failed
 *		-2	- The parsed information did not match saved
 *			  information.  An error message has been printed.
 */
static int
_process_normal_header(FlashArchive *flar)
{
	HTTPData *d;
	off_t cur;
	off_t end;
	off_t tot;
	off_t len;
	char *c;

	d = HTTPDATA(flar);

	/* Lop off any trailing '\r' */
	if (d->curhdr[strlen(d->curhdr) - 1] == '\r') {
		d->curhdr[strlen(d->curhdr) - 1] = '\0';
	}

	/*
	 * Content-range should be `bytes xx-yy/zz', where xx is ad->cur,
	 * yy is ad->end (though we'll let it slide as long as yy <= ad->end),
	 * and zz is (ad->end + 1).
	 */
	if (ci_strneq(d->curhdr, "Content-range: bytes ", 21)) {
		/* Parse */
		c = d->curhdr + 21;

		if (!isdigit(*c)) {
			return (-1);
		}
		cur = atol(c);

		for (; *c && isdigit(*c); c++);
		if (!*c || *c != '-' || !isdigit(*(c + 1))) {
			return (-1);
		}
		c++;
		end = atol(c);

		for (; *c && isdigit(*c); c++);
		if (!*c || *c != '/' || !isdigit(*(c + 1))) {
			return (-1);
		}
		c++;
		tot = atol(c);

		/* Check */
		if (cur != d->cur) {
			write_notice(ERRMSG, MSG0_HTTP_INVALID_START,
			    (long long)cur, (long long)d->cur);
			return (-2);
		}

		if (d->end == -1) {
			/* Save the length we just got */
			d->end = end;
		} else if (end > d->end) {
			write_notice(ERRMSG, MSG0_HTTP_SIZE_CHANGED,
			    (long long)end, (long long)d->end);
			return (-2);
		}

		if (d->end != -1 && tot != d->end + 1) {
			write_notice(ERRMSG, MSG0_HTTP_SIZE_CHANGED,
			    (long long)(d->end + 1), (long long)tot);
			return (-2);
		}

	/*
	 * Content-length should be ad->end + 1, though we'll let it slide as
	 * long as it's <= ad->end + 1.
	 */
	} else if (ci_strneq(d->curhdr, "Content-length: ", 16)) {
		len = atol(d->curhdr + 16);

		if (d->end == -1) {
			/*
			 * We don't already know the length, so save the
			 * one we just got.
			 */
			d->end = (d->cur == -1 ? 0 : d->cur) + len - 1;
		} else if (len > d->end - d->cur + 1) {
			write_notice(ERRMSG, MSG0_HTTP_SIZE_CHANGED,
			    (long long)(d->end + 1), (long long)(d->cur + len));
			return (-2);
		}

	/*
	 * If we got a `Location', odds are that we were just redirected.
	 * Save the location so we can process it later.
	 */
	} else if (ci_strneq(d->curhdr, "Location: ", 10)) {
		if (ParseHTTPURL(d->curhdr + 10, &d->actloc) < 0) {
			write_notice(ERRMSG, MSG0_HTTP_INVALID_REDIRECT,
			    d->curhdr + 10);
			return (-1);
		}

		/* We have to update the target host too */
		if (flar->spec.HTTP.proxyhost == NULL) {
			HTTPDATA(flar)->targethost =
			    HTTPDATA(flar)->actloc->host;
			HTTPDATA(flar)->targetport =
			    HTTPDATA(flar)->actloc->port;
		}
	}

	return (0);
}

/*
 * Name:	_http_open_connection
 * Description:	Open a TCP connection to a given port on a given server.
 *		If the connection is successful, the descriptor for the
 *		socket is set in the HTTP data.  errno will be set on failure.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive containing the connection data
 * Returns:	0	- Connection succeeded - return value is socket
 *			  file descriptor
 *		-1	- Connection failed
 *		-2	- Connection timed out
 */
static int
_http_open_connection(FlashArchive *flar)
{
	struct hostent *hep;
	struct in_addr *ip;
	struct sockaddr_in dest;
	int errcode;
	int fd;

	/*
	 * Figure out where we're supposed to connect, if we haven't
	 * done so already
	 */
	if (!HTTPDATA(flar)->targethost) {
		if (flar->spec.HTTP.proxyhost) {
			HTTPDATA(flar)->targethost = flar->spec.HTTP.proxyhost;
			HTTPDATA(flar)->targetport = flar->spec.HTTP.proxyport;
		} else {
			HTTPDATA(flar)->targethost =
			    HTTPDATA(flar)->actloc->host;
			HTTPDATA(flar)->targetport =
			    HTTPDATA(flar)->actloc->port;
		}
	}

	/* Get the address of the remote machine */
	if (!(hep = gethostbyname(HTTPDATA(flar)->targethost))) {
		return (-1);
	}

	/*LINTED*/
	ip = (struct in_addr *)hep->h_addr;

	(void) memset(&dest, 0, sizeof (dest));
	dest.sin_family = AF_INET;
	dest.sin_port = htons(HTTPDATA(flar)->targetport);
	dest.sin_addr.s_addr = ip->s_addr;

	/* Connect to the remote machine */
	if ((fd = socket(PF_INET, SOCK_STREAM, IPPROTO_TCP)) < 0) {
		return (-1);
	}

	if (connect(fd, (struct sockaddr *)&dest,
	    sizeof (struct sockaddr_in)) < 0) {
		errcode = errno;
		(void) close(fd);
		errno = errcode;
		return (-1);
	}

	HTTPDATA(flar)->fd = fd;

	return (0);
}

/*
 * Name:	_http_close_connection
 * Description:	Close the socket connection to the server, resetting HTTP
 *		header processing state.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose connection is being closed
 * Returns:	0	- The connection was closed
 *		-1	- An error occurred during closing.  errno has been set
 */
static int
_http_close_connection(FlashArchive *flar)
{
	if (HTTPDATA(flar)->fd >= 0 &&
	    close(HTTPDATA(flar)->fd) < 0) {
		return (-1);
	}

	if (CURHDR(flar) != NULL) {
		_free_header(flar);
	}

	HTTPDATA(flar)->fd = -1;

	return (0);
}

/*
 * Name:	alarm_handler
 * Description:	Used to implement the timeout restart, this handler exists
 *		solely to catch SIGALRM.  The content of the handler is
 *		unimportant - we just want to interrupt any system calls that
 *		may be in process so we can close down any connections and
 *		restart them.
 * Scope:	private
 * Arguments:	junk	- [RO] (int)
 *			  unused
 * Returns:	none
 */
/*ARGSUSED*/
static void
_alarm_handler(int junk)
{
	/*
	 * The sole purpose of this handler is to interrupt any read() or
	 * write() system calls that may be going on.
	 */
}

/*
 * Name:	_http_read_from_block
 * Description:	Attempt to read a line of data from the current block (or from
 *		a new block, if there is no data left in the current one).  A
 *		full line, or the data up to the end of the block will be
 *		returned, whichever is shorter.  It is the responsibility of
 *		the caller to marshal fragments into complete lines.  The data
 *		returned is statically-allocated, and should not be modified by
 *		the caller.
 * Scope:	private
 * Arguments:	flar		- [RO, *RW] (FlashArchive *)
 *				  The archive whose data is being read
 *		bufptr		- [RO, *RW] (char **)
 *				  Where the beginning of the data being returned
 *				  is to be stored
 *		avail		- [RO, *RW] (int *)
 *				  Where the number of bytes in the data being
 *				  returned is to be stored
 *		foundeol	- [RO, *RW] (int *)
 *				  Where a flag saying whether or not the data
 *				  returned marks the end of a line is returned
 * Returns:	FlErrSuccess	- The data was read and returned successfully
 *		FlErrEndOfFile	- The end of the stream was encountered while
 *				  trying to read the data
 *		FlErrRead	- An error occurred reading the data
 */
static FlashError
_http_read_from_block(FlashArchive *flar, char **bufptr, int *avail,
    int *foundeol)
{
	FlashError status;
	char *start;
	char *eolp;

	/* if no space left in block, read new block */
	if (!RBPTR(flar)) {
		if ((status = _http_read_block(flar, NULL)) != FlErrSuccess) {
			return (status);
		}
	}

	/* scan to \n or end of block, which ever comes first */
	for (eolp = start = RBPTR(flar); eolp <= RBENDPTR(flar); eolp++) {
		if (*eolp == '\n') {
			break;
		}
	}

	/*
	 * eolp now points either to a \n or to rbendptr + 1
	 * adjust current-position-in-block pointer.  NULL means read another
	 */
	if (eolp == RBENDPTR(flar) + 1) {
		_http_flush_block(flar);
	} else {
		RBPTR(flar) = eolp + 1;
	}

	/*
	 * return:
	 *	pointer to the place from which we started searching,
	 *	number of bytes available,
	 *	whether the given block of bytes marks the end of a line
	 */
	*bufptr = start;
	*avail = eolp - start;
	*foundeol = (eolp != RBENDPTR(flar) + 1);

	return (FlErrSuccess);
}

/*
 * Name:	_http_read_block
 * Description:	Read a block of data from the HTTP server.  If a connection to
 *		the server hasn't been opened, this routine will open it prior
 *		to reading.  If the data returned in readbuf by a prior call to
 *		this function or the header reading code has not been fully
 *		consumed (if rbptr is non-NULL and is <= rbendptr), the unused
 *		portion is returned.
 * Scope:	private
 * Arguments:	flar		- [RO, *RW] (FlashArchive *)
 *				  The archive being read
 *		amtreadptr	- [RO, *RW] (size_t *) [OPTIONAL]
 *				  If non-NULL, where the number of bytes read
 *				  in this block will be returned
 * Returns:	FlErrSuccess		- The data was read and returned
 *					  successfully
 *		FlErrEndOfFile		- The end of the stream was encountered
 *					  while trying to read the data
 *		FlErrRead		- An error occurred reading the data
 *		FlErrCouldNotOpen	- A (re)connection was required but was
 *					  not successful
 */
static FlashError
_http_read_block(FlashArchive *flar, size_t *amtreadptr)
{
	RequestStatus reqstat;
	ssize_t amtread;
	int errcode;

	for (;;) {
		if (HTTPDATA(flar)->fd == -1) {
			/* We need to start a new connection */
			if (_http_open_connection(flar) != 0) {
				if (errno == EINTR) {
					/* Timed out.  Try, try again */
					_progress_restart(FLARRESTART_TIMEOUT);
					continue;
				} else if (errno == ETIMEDOUT ||
				    errno == ECONNREFUSED ||
				    errno == EHOSTDOWN) {
					/*
					 * We're going to be tenacious.  If the
					 * server goes away, we're going to keep
					 * trying to connect until the server
					 * comes back up.
					 */
					_progress_restart(FLARRESTART_REFUSED);

					/*
					 * actual backoff is randomly distibuted
					 * from 1 to backoff_ceiling
					 */
					backoff();
					continue;
				} else {
					/* give up, and reset backoff */
					reset_backoff();
					return (FlErrCouldNotOpen);
				}
			}

			/* finally connected, reset backoff */
			reset_backoff();

			if (_http_send_request(flar, &reqstat,
						    HTTP_REQ_TYPE_GET) < 0) {
				(void) _http_close_connection(flar);
				if (errno == EINTR) {
					/* Timed out. */
					_progress_restart(FLARRESTART_TIMEOUT);
					continue;
				} else {
					return (FlErrCouldNotOpen);
				}
			}

			if (get_trace_level() > 0) {
				write_status(LOGSCR, LEVEL1, MSG0_HTTP_STATUS,
				    "GET", reqstat.code,
				    (HTTPDATA(flar)->end -
					HTTPDATA(flar)->cur + 1));
			}

			if (!IS_HTTP_OK(reqstat.code)) {
				write_notice(ERRMSG,
				    MSG0_HTTP_CANT_ACCESS_ARCHIVE,
				    reqstat.code,
				    (reqstat.statusmsg ?
					reqstat.statusmsg : ""));
				return (FlErrCouldNotOpen);
			}
		}

		/*
		 * now we're connected, reset the backoff in case that we get
		 * a timeout from the server on the first connection attempt,
		 * and went around again to re-try the connection.
		 */
		reset_backoff();

		/*
		 * If there's anything left in the read buffer, use it first.
		 */
		if (RBPTR(flar) && RBPTR(flar) <= RBENDPTR(flar)) {
			amtread = RBENDPTR(flar) - RBPTR(flar) + 1;
			if (!RBCOUNTED(flar)) {
				RBCOUNTED(flar) = 1;
				HTTPDATA(flar)->cur += amtread;
			}

			if (amtreadptr) {
				*amtreadptr = amtread;
			}

			return (FlErrSuccess);
		}

		(void) alarm(flar->spec.HTTP.timeout);
		amtread = read(HTTPDATA(flar)->fd,
				READBUF(flar), READBUF_SIZE);
		errcode = errno;
		(void) alarm(0);

		/* Handle aborted or empty reads */
		if (amtread < 0) {
			(void) _http_close_connection(flar);

			if (errcode == EINTR) {
				/* Timed out. */
				_progress_restart(FLARRESTART_TIMEOUT);
				continue;
			} else if (errcode) {
				return (FlErrRead);
			}
		} else if (amtread == 0) {
			/* We should be done */
			(void) _http_close_connection(flar);
			return (FlErrEndOfFile);
		}

		/* Set the pointers to the newly-read data. */
		RBPTR(flar) = READBUF(flar);
		RBCOUNTED(flar) = 1;
		RBENDPTR(flar) = READBUF(flar) + (amtread - 1);
		HTTPDATA(flar)->cur += amtread;
		if (amtreadptr) {
			*amtreadptr = amtread;
		}

		return (FlErrSuccess);
	}
}

/*
 * Name:	_http_flush_block
 * Description:	Mark the currently-read block as used.
 * Scope:	private
 * Arguments:	none
 * Returns:	none
 */
static void
_http_flush_block(FlashArchive *flar)
{
	RBPTR(flar) = NULL;
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

/*
 * Name:	_free_http_data
 * Description:	Free the HTTP-connection-specific data.
 * Scope:	private
 * Arguments:	d	- [RO, *RW] (HTTPData *)
 *			  The connection-specific data to be freed.
 * Returns:	none
 */
static void
_free_http_data(HTTPData *d)
{
	if (d->actloc) {
		FreeURL(d->actloc);
	}

	free(d);
}
