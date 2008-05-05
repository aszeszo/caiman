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
 * Module:	svc_flash_http.c
 * Group:	libspmisvc
 * Description:
 *	The functions used for manipulating archives retrieved via HTTP.
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
#include <boot_http.h>
#include <netboot_paths.h>

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

/* HTTP retrieval-specific private data */
typedef struct {
	http_handle_t	*sid;
	off64_t		start;
	off64_t		cur;
	off64_t		end;
	URL		*actloc;

	/* Read (rhymes with bread) data */
	char	*readbuf;
	int	rbcounted;	/* Has this block been accounted for? */
	char	*rbptr;
	char	*rbendptr;

} HTTPData;
#define	HTTPDATA(flar)	((HTTPData *)flar->data)

/* Macros for determining HTTP response codes */
#define	IS_HTTP_REDIRECT(x)	((x / 100) == 3)
#define	IS_HTTP_OK(x)		((x / 100) == 2)

#define	READBUF(flar)	(HTTPDATA(flar)->readbuf)
#define	HTTPCONN(flar)	(HTTPDATA(flar)->sid)
#define	RBPTR(flar)	(HTTPDATA(flar)->rbptr)
#define	RBENDPTR(flar)	(HTTPDATA(flar)->rbendptr)
#define	RBCOUNTED(flar)	(HTTPDATA(flar)->rbcounted)

/* file to get random data from for feeding to libhttp */
#define	RANDOM_FILE	"/dev/urandom"

/*
 * Local global data
 */

/* Progress information messages for the front end */
static TCallback	*progress_callback;
static void		*progress_userdata;

/*
 * Local functions
 */

static FlashError	_http_head_file(FlashArchive *, http_respinfo_t **);
static int		_http_open_connection(FlashArchive *);
static int		_http_open_ssl_connection(FlashArchive *);
static int		_http_read_headers(FlashArchive *, http_respinfo_t **);
static int		_http_close_connection(FlashArchive *);
static FlashError	_http_read_from_block(FlashArchive *, char **, int *,
					int *);
static FlashError	_http_read_block(FlashArchive *, size_t *);
static void		_http_flush_block(FlashArchive *);
static int		_save_header_part(FlashArchive *, char *, char *);
static int		_process_normal_headers(FlashArchive *);
static void		_reset_header(FlashArchive *);
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
FLARHTTPOpen(FlashArchive *flar)
{
	http_respinfo_t *reqstat;
	FlashError status;
	char *urlstr;
	int redir = 0;

	flar->data = xmalloc(sizeof (HTTPData));
	HTTPDATA(flar)->start = -1;
	HTTPDATA(flar)->cur = -1;
	HTTPDATA(flar)->end = -1;
	HTTPDATA(flar)->actloc = flar->spec.HTTP.url;
	URLAddRef(flar->spec.HTTP.url);

	READBUF(flar) = xmalloc(READBUF_SIZE);
	RBCOUNTED(flar) = 0;
	RBPTR(flar) = NULL;
	RBENDPTR(flar) = NULL;

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
			    "HEAD", reqstat->code,
			    (HTTPDATA(flar)->end == -1 ? -1 :
				HTTPDATA(flar)->end + 1));
		}

		/*
		 * If we got a redirection, let the user know, and retry the
		 * HEAD.  We only support redirections that give us a Location
		 * header.
		 */
		if (IS_HTTP_REDIRECT(reqstat->code)) {
			if (!HTTPDATA(flar)->actloc) {
				write_notice(ERRMSG, MSG0_HTTP_REDIR_WO_LOC,
				    reqstat->code);
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

		} else if (!IS_HTTP_OK(reqstat->code)) {
			write_notice(ERRMSG, MSG0_HTTP_CANT_ACCESS_ARCHIVE,
			    reqstat->code,
			    (reqstat->statusmsg ? reqstat->statusmsg : ""));
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
FLARHTTPReadLine(FlashArchive *flar, char **bufptr)
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
FLARHTTPExtract(FlashArchive *flar, FILE *xfp, TCallback *cb, void *data)
{
	FLARProgress prog;
	FlashError status;
	FlashError rc;
	size_t amtread;
	size_t last;
	void (*old_handler)(int);

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
FLARHTTPClose(FlashArchive *flar)
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
 *		will be returned in the preallocated http_respinfo_t buffer
 *		passed by the caller.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive being HEADed
 *		reqstat	- [RO, *WO] (http_respinfo_t *)
 *			  Preallocated buffer for storage of the request status
 * Returns:	FlErrSuccess		- The HEAD request succeeded.  reqstat
 *					  is valid.
 *		FlErrCouldNotOpen	- The server could not be contacted.
 */
static FlashError
_http_head_file(FlashArchive *flar, http_respinfo_t **reqstat)
{
	void (*old_handler)(int);
	int errcode = 0;
	FlashError status = FlErrSuccess;

	const char	*httperr_str;
	ulong_t		httperr_code;
	uint_t		httperr_src;

	/* Open the connection */
	if (_http_open_connection(flar) == 0) {
		/* Send the request */
		status = http_head_request(HTTPCONN(flar),
		    HTTPDATA(flar)->actloc->path);
		if (status == 0) {
			status =
			    _http_read_headers(flar, reqstat);
		}
	} else {
		status = FlErrCouldNotOpen;
	}

	if (status != FlErrSuccess) {
	    while ((httperr_code = http_get_lasterr(HTTPCONN(flar),
		&httperr_src)) != 0) {
		httperr_str = http_errorstr(httperr_src, httperr_code);
		write_notice(ERRMSG, MSG0_CANNOT_CONNECT,
		    (HTTPDATA(flar)->actloc->host ?
			HTTPDATA(flar)->actloc->host :
			"**NO HOST**"),
		    HTTPDATA(flar)->actloc->port,
		    httperr_str?httperr_str:MSG0_INTERNAL_ERROR);
	    }
	    _http_close_connection(flar);
	    return (FlErrCouldNotOpen);
	}

	/*
	 * since the connection is closed by the server
	 * after a HEAD, let's offically close our side too
	 */
	(void) _http_close_connection(flar);
	_http_flush_block(flar);

	return (FlErrSuccess);
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
 *		reqstat	- [RO, *RW] (http_respinfo_t *)
 *			  Where the results of the request will be returned
 * Returns:	0	- The headers were processed without error
 *		-1	- An error occurred during header processing.  errno
 *			  has been set.
 */
static int
_http_read_headers(FlashArchive *flar, http_respinfo_t **reqstat)
{
	int amtread;
	int inhdrblk = 1;
	int inhdrblkend = 0;	/* In potential end of header block */
	int firsthdr = 1;
	int idx;
	int rc;
	char *nlptr;

	/* Read the headers */
	rc = http_process_headers(HTTPCONN(flar), reqstat);

	if (rc != 0) {
		write_notice(ERRMSG,
		    MSG0_HTTP_INVALID_HEADERS);
		return (-1);
	}

	/*
	 * If we got a redirection, we need to
	 * clear out the actual URL field so
	 * we can tell if the remaining headers
	 * gave us a location or not.  If said
	 * headers give us a location, actloc
	 * will be repopulated.
	 */
	if (IS_HTTP_REDIRECT((*reqstat)->code)) {
		FreeURL(HTTPDATA(flar)->actloc);
		HTTPDATA(flar)->actloc = NULL;
	}

	/*
	 * now we look for headers we recognize, that tell us
	 * the size, where we were relocated to, etc.
	 */
	rc = _process_normal_headers(flar);
	if (rc == -1) {
	    write_notice(ERRMSG,
		MSG0_HTTP_INVALID_HEADERS);
	}

	if (rc < 0) {
		return (-1);
	}

	return (0);
}



/*
 * Name:	_process_normal_headers
 * Description:	Process non-status HTTP response headers.  If the header is
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
_process_normal_headers(FlashArchive *flar)
{
	HTTPData *d;
	off64_t cur;
	off64_t end;
	off64_t tot;
	off64_t len;
	char *c;
	char	*hdr;

	d = HTTPDATA(flar);

	/*
	 * Content-range should be `bytes xx-yy/zz', where xx
	 * is ad->cur, yy is ad->end (though we'll let it
	 * slide as long as yy <= ad->end), and zz is (ad->end
	 * + 1).
	 */
	if ((hdr = http_get_header_value(d->sid, "Content-range")) != NULL &&
		ci_strneq(hdr, "bytes ", 6)) {

		c = hdr + 6;

		if (!isdigit(*c)) {
			write_notice(ERRMSG,
			    MSG0_HTTP_INVALID_HEADER, hdr);
			return (-1);
		}
		cur = atoll(c);

		for (; *c && isdigit(*c); c++);
		if (!*c || *c != '-' || !isdigit(*(c + 1))) {
			write_notice(ERRMSG,
			    MSG0_HTTP_INVALID_HEADER, hdr);
			return (-1);
		}
		c++;
		end = atoll(c);

		for (; *c && isdigit(*c); c++);
		if (!*c || *c != '/' || !isdigit(*(c + 1))) {
			write_notice(ERRMSG,
			    MSG0_HTTP_INVALID_HEADER, hdr);
			return (-1);
		}
		c++;
		tot = atoll(c);

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
	}


	/*
	 * Content-length should be ad->end + 1, though we'll let it slide as
	 * long as it's <= ad->end + 1.
	 */
	if ((hdr = http_get_header_value(d->sid, "Content-length")) != NULL) {

		if ((len = atoll(hdr)) < 0) {
			write_notice(ERRMSG, MSG0_HTTP_SIZE_INVALID, len);
			return (-1);
		}

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

	}
	/*
	 * If we got a `Location', odds are that we were just redirected.
	 * Save the location so we can process it later.
	 */
	if ((hdr = http_get_header_value(d->sid, "Location")) != NULL) {
		if (ParseHTTPURL(hdr, &d->actloc) < 0) {
			write_notice(ERRMSG, MSG0_HTTP_INVALID_REDIRECT,
			    hdr);
			return (-1);
		}
	}

	return (0);
}

/*
 * Name:	_http_open_connection
 * Description:	Open a TCP connection to a given port on a given server.
 *		If the connection is successful, the descriptor for the
 *		connection is set in the HTTP data.
 *		  errno will be set on failure.
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
	url_t		urlobj;
	url_hport_t	proxyobj;

	/* turn on verboseness if in debug mode */
	if (get_trace_level() > 0) {
		http_set_verbose(B_TRUE);
	}

	/*
	 * initialize object passed to http_srv_init.   If url_parse
	 * could handle basic authorization we could use that instead.
	 */
	strncpy(urlobj.hport.hostname, HTTPDATA(flar)->actloc->host,
	    URL_MAX_HOSTLEN);
	urlobj.hport.port = HTTPDATA(flar)->actloc->port;
	urlobj.https = ci_streq(HTTPDATA(flar)->actloc->scheme, "https");
	strncpy(urlobj.abspath, HTTPDATA(flar)->actloc->path, URL_MAX_PATHLEN);

	/* initialize connection parameters */
	if ((HTTPCONN(flar) = http_srv_init(&urlobj)) == NULL) {
		return (-1);
	}

	/* initialize timeout value */
	http_set_socket_read_timeout(HTTPCONN(flar), flar->spec.HTTP.timeout);

	/* initialize proxy if we're using one */
	if (flar->spec.HTTP.proxyhost) {
		strncpy(proxyobj.hostname, flar->spec.HTTP.proxyhost,
		    URL_MAX_HOSTLEN);
		proxyobj.port = flar->spec.HTTP.proxyport;
		http_set_proxy(HTTPCONN(flar), &proxyobj);
	}

	/* initialize basic authorization if we're using it */
	if (HTTPDATA(flar)->actloc->auth_type == URLAuthTypeBasic) {
		if (http_set_basic_auth(HTTPCONN(flar),
		    HTTPDATA(flar)->actloc->auth.basic.user,
		    HTTPDATA(flar)->actloc->auth.basic.password) != 0) {
			return (-1);
		}
	}

	/* don't use keepalive */
	http_set_keepalive(HTTPCONN(flar), B_FALSE);

	/*
	 * if using SSL, attempt the connection with certificates
	 */
	if (ci_streq(HTTPDATA(flar)->actloc->scheme, "https")) {
		if (_http_open_ssl_connection(flar)) {
			return (0);
		}
	} else {
		/* no SSL, just try to connect */
		if (http_srv_connect(HTTPCONN(flar)) == 0) {
			return (0);
		}
	}

	/* if we got here, we couldn't initiate any connection */
	return (-1);
}

/*
 * Name:	_http_open_ssl_connection
 * Description:	Open a secire connection to a given port on a given server.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive containing the connection data
 * Returns:	TRUE	- Able to set up SSL connection
 *		FALSE otherwise
 */
static int
_http_open_ssl_connection(FlashArchive *flar)
{
	http_set_random_file(HTTPCONN(flar), RANDOM_FILE);

	http_set_p12_format(1);
	http_set_key_file_password(HTTPCONN(flar), WANBOOT_PASSPHRASE);

	/* set up client key, client cert, and trusted certs */
	if ((access(NB_CA_CERT_PATH, R_OK) == 0) &&
	    http_set_certificate_authority_file(NB_CA_CERT_PATH)) {
		return (FALSE);
	}

	/* setting the client cert requires the HTTP connection handle */
	if ((access(NB_CLIENT_CERT_PATH, R_OK) == 0) &&
	    http_set_client_certificate_file(HTTPCONN(flar),
		NB_CLIENT_CERT_PATH)) {
		return (FALSE);
	}

	/* setting the client key requires the HTTP connection handle */
	if ((access(NB_CLIENT_KEY_PATH, R_OK) == 0) &&
	    http_set_private_key_file(HTTPCONN(flar), NB_CLIENT_KEY_PATH)) {
		return (FALSE);
	}

	/* try to connect */
	if (http_srv_connect(HTTPCONN(flar)) == 0) {
		return (TRUE);
	}

	/* if we got here, we couldn't initiate the connection */
	return (FALSE);
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
	http_srv_close(HTTPCONN(flar));
	HTTPCONN(flar) = NULL;
	return (0);
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
	http_respinfo_t *reqstat;
	ssize_t		amtread;
	ulong_t		errcode;
	uint_t		errsrc;
	const char		*errstr;
	int		my_errno = 0;

	for (;;) {
		if (HTTPCONN(flar) == NULL) {
			/* We need to start a new connection */
			if (_http_open_connection(flar) != 0) {
				while ((errcode =
				    http_get_lasterr(HTTPCONN(flar),
					&errsrc)) != 0) {
					/* Have an error - is it EINTR? */
					if (errsrc == ERRSRC_SYSTEM) {
						my_errno = errcode;
						break;
					}
				}

				if (my_errno == EINTR) {
					/* Timed out.  Try, try again */
					_progress_restart(FLARRESTART_TIMEOUT);
					continue;
				} else if (my_errno == ETIMEDOUT ||
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

			if ((http_get_range_request(HTTPCONN(flar),
			    HTTPDATA(flar)->actloc->path,
			    HTTPDATA(flar)->cur,
			    ((HTTPDATA(flar)->end) -
				(HTTPDATA(flar)->cur)) + 1) != 0) ||
			    (_http_read_headers(flar, &reqstat) != 0)) {
				while ((errcode =
				    http_get_lasterr(HTTPCONN(flar),
					&errsrc)) != 0) {
					/* Have an error - is it EINTR? */
					if (errsrc == ERRSRC_SYSTEM) {
						my_errno = errcode;
						break;
					}
				}

				(void) _http_close_connection(flar);
				if (my_errno == EINTR) {
					/* Timed out. */
					_progress_restart(FLARRESTART_TIMEOUT);
					continue;
				} else {
					return (FlErrCouldNotOpen);
				}
			}

			if (get_trace_level() > 0) {
				write_status(LOGSCR, LEVEL1, MSG0_HTTP_STATUS,
				    "GET", reqstat->code,
				    (HTTPDATA(flar)->end -
					HTTPDATA(flar)->cur + 1));
			}

			if (!IS_HTTP_OK(reqstat->code)) {
				write_notice(ERRMSG,
				    MSG0_HTTP_CANT_ACCESS_ARCHIVE,
				    reqstat->code,
				    (reqstat->statusmsg ?
					reqstat->statusmsg : ""));
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

		amtread = http_read_body(HTTPCONN(flar),
		    READBUF(flar), READBUF_SIZE);

		errcode = errno;

		/* Handle aborted or empty reads */
		if (amtread < 0) {
			while ((errcode =
			    http_get_lasterr(HTTPCONN(flar),
				&errsrc)) != 0) {
				/* Have an error - is it EINTR? */
				errstr = http_errorstr(errsrc, errcode);
				if (errsrc == ERRSRC_SYSTEM) {
					my_errno = errcode;
					break;
				}
			}
			(void) _http_close_connection(flar);

			if (my_errno == EINTR) {
				/* Timed out. */
				_progress_restart(FLARRESTART_TIMEOUT);
				continue;
			} else {
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
