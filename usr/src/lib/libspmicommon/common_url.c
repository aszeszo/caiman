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
 * Routines for manipulating URLs
 */

#include <stdio.h>
#include <stdlib.h>
#include <netdb.h>

#include "spmicommon_lib.h"

/*
 * Name:	ParseHTTPURL
 * Description:	Parse an HTTP-style URL.  The scheme used is unimportant; what
 *		is important is that the url follows the following style typical
 *		of HTTP URLs:
 *
 *		    scheme://[user:password@]host[:port]/path
 *
 *		The parsed data is returned in a newly-allocated URL structure.
 *		The returned URL structure *must* be freed using FreeURL.
 * Scope:	public
 * Arguments:	urlstr	- [RO, *RO] (char *)
 *			  The URL to be parsed
 *		urlp	- [RO, *WO] (URL **)
 *			  Where the newly-allocated URL is to be returned.
 * Returns:	0			- The URL was parsed successfully
 *		ERR_HTTP_BAD_SCHEME	- The scheme could not be parsed
 *		ERR_HTTP_BAD_PASSWORD	- The user:password@ authentication
 *					  portion appeared to be present,
 *					  but could not be parsed
 *		ERR_HTTP_BAD_PATH	- The path could not be found
 *		ERR_HTTP_BAD_HOSTNAME	- The `host[:port]' could not be parsed
 *		ERR_HTTP_INVALID_PORT	- An invalid port number/name was
 *					  specified.
 */
int
ParseHTTPURL(char *urlstr, URL **urlp)
{
	URL	*url;
	char	*fullhost;
	char	*user;
	char	*pw;
	char	*c, *c2, *c3;
	char	*slash;
	int	rc;

	/* Check arguments */
	if (!urlstr || !urlp) {
		return (ERR_INVALID);
	}

	url = NewURL();

	/* Skip the scheme */
	for (c = urlstr; isalnum(*c) || strchr("+-.", *c); c++);
	if (!strneq(c, "://", 3)) {
		return (ERR_HTTP_BAD_SCHEME);
	}
	url->scheme = (char *)xmalloc(c - urlstr + 1);
	(void) strncpy(url->scheme, urlstr, c - urlstr);
	url->scheme[c - urlstr] = '\0';
	c += 3;

	/*
	 * Do we have a user and password?  If we do, we'll see a `@'
	 * before we see our next `/'.
	 */
	slash = strchr(c, '/');
	c3 = strchr(c, '@');
	if (c3 && slash && (c3 < slash)) {
		url->auth_type = URLAuthTypeBasic;

		/* Yup - back up and look for the separator (":") */
		if (!(c2 = strchr(c, ':')) || c2 > c3) {
			FreeURL(url);
			return (ERR_HTTP_BAD_PASSWORD);
		}

		/*
		 * http://user:password@hostname/...
		 *    c---/   \--c2    \--c3    \--slash
		 */

		user = xmalloc(c2 - c + 1);
		(void) strncpy(user, c, c2 - c);
		user[c2 - c] = '\0';
		url->auth.basic.user = user;

		pw = xmalloc(c3 - c2);
		(void) strncpy(pw, c2 + 1, c3 - c2 - 1);
		pw[c3 - c2 - 1] = '\0';
		url->auth.basic.password = pw;
		c = c3 + 1;
	} else {
		/* No */
		url->auth_type = URLAuthTypeNone;
	}

	/* Look for the end of the host name */
	if (!slash) {
		FreeURL(url);
		return (ERR_HTTP_BAD_PATH);
	}

	/* Get the host name and optional port number */
	fullhost = xmalloc(slash - c + 1);
	(void) strncpy(fullhost, c, slash - c);
	fullhost[slash - c] = '\0';
	rc = ParseHostPort(fullhost, &url->host, &url->port);
	free(fullhost);
	if (rc != 0) {
		FreeURL(url);
		return (rc);
	}

	/* Get the path */
	url->path = xstrdup(slash);

	/* We're done */
	*urlp = url;

	return (0);
}

/*
 * Name:	ParseHostPort
 * Description:	Given a host name and an optional port number or name of the
 *		form `host[:port]', extract the host name and port number.  Upon
 *		successful parsing, a newly-allocated copy of the host name is
 *		returned, as is the port number.  The caller is responsible for
 *		freeing the host name.  If a service name was specified, the
 *		port number corresponding to that service name will be returned.
 *		If no port number is found, -1 is returned in `portp'.
 * Scope:	public
 * Arguments:	hostport	- [RO, *RO] (char *)
 *				  The string to be parsed
 *		hostp		- [RO, *WO] (char **)
 *				  Where the newly-allocated host name is to be
 *				  returned.
 *		portp		- [RO, *WO] (int *)
 *				  Where the port number is to be returned.
 * Returns:	0			- The string was parsed successfully
 *		ERR_HTTP_BAD_HOSTNAME	- The host name could not be
 *					  found/parsed.
 *		ERR_HTTP_INVALID_PORT	- A port number or service name was
 *					  found, but was either invalid or
 *					  could not be resolved.
 */
int
ParseHostPort(char *hostport, char **hostp, int *portp)
{
	struct servent	*se;
	char		*host;
	int		port;
	char		*c;

	if ((c = strchr(hostport, ':'))) {
		/* We got ourselves a port number */
		if (c == hostport || !(*(c + 1)) || strchr(c + 1, ':')) {
			return (ERR_HTTP_BAD_HOSTNAME);
		}

		if (is_allnums(c + 1)) {
			port = atoi(c + 1);
		} else {
			if (!(se = getservbyname(c + 1, "tcp"))) {
				return (ERR_HTTP_INVALID_PORT);
			}
			port = htons(se->s_port);
		}

		if (port < 0 || port > 65535) {
			return (ERR_HTTP_INVALID_PORT);
		}

		host = xmalloc(c - hostport + 1);
		(void) strncpy(host, hostport, c - hostport);
		host[c - hostport] = '\0';
	} else {
		port = -1;
		host = xstrdup(hostport);
	}

	*hostp = host;
	*portp = port;

	return (0);
}

/*
 * Name:	URLString
 * Description:	Given a URL structure, return the text representationd of
 *		that URL in a newly-allocated string.  The caller is
 *		responsible for freeing the returned string.
 * Scope:	public
 * Arguments:	url		- [RO, *RO] (URL *)
 *				  The URL whose representation is to be
 *				  generated
 *		urlstrp		- [RO, *WO] (char **)
 *				  The newly-allocated text version of the URL
 * Returns:	0		- success
 *		ERR_INVALID	- invalid arguments
 *		ERR_NOSPACE	- a buffer was provided that was too small
 */
int
URLString(URL *url, char **urlstrp)
{
	char *urlstr = NULL;
	int actlen = 0;

	if (!url || !urlstrp) {
		return (ERR_INVALID);
	}

	/*
	 * Count the length of the resulting URL
	 */

	/* scheme */
	actlen = strlen(url->scheme) + 3 + 1;

	/* authentication */
	if (url->auth_type == URLAuthTypeBasic) {
		actlen += strlen(url->auth.basic.user) + 1 +
		    strlen(url->auth.basic.password) + 1;
	}

	/* host:port/path */
	actlen += strlen(url->host) + 1 + count_digits(url->port) + 1 +
	    strlen(url->path);

	/* Allocate space for the string */
	urlstr = xmalloc(actlen);

	/*
	 * Create the URL string
	 */

	/* http:// */
	(void) sprintf(urlstr, "%s://", url->scheme);

	if (url->auth_type == URLAuthTypeBasic) {
		/* user:password@ */
		(void) sprintf(urlstr + strlen(urlstr), "%s:%s@",
		    url->auth.basic.user,
		    url->auth.basic.password);
	}

	/* host:port/path */
	(void) sprintf(urlstr + strlen(urlstr), "%s:%d%s",
	    url->host, url->port, url->path);

	*urlstrp = urlstr;

	return (0);
}

/*
 * Name:	NewURL
 * Description:	Allocate a new URL structure.  Most applications won't need
 *		this - they should use ParseHTTPURL instead.
 * Scope:	public
 * Returns:	URL *	- The newly-allocated URL
 */
URL *
NewURL(void)
{
	URL *url;

	url = (URL *)xcalloc(sizeof (URL));
	url->refcnt++;

	return (url);
}

/*
 * Name:	URLAddRef
 * Description:	Indicate that another entity is referring to this URL.  See
 *		FreeURL.
 * Scope:	public
 * Arguments:	url	- [RO, *RW] (URL *)
 *			  The URL being referred to
 * Returns:	0	- Success
 *		-1	- Invalid arguments
 */
int
URLAddRef(URL *url)
{
	if (!url) {
		return (-1);
	}

	url->refcnt++;

	return (0);
}

/*
 * Name:	FreeURL
 * Description:	Decrease the count of entities referring to this URL.  If the
 *		count is zero, free the contents of the URL and the URL
 *		structure itself.
 * Scope:	public
 * Arguments:	url	- [RO, *RW] (URL *)
 *			  The URL to be freed
 * Returns:	none
 */
void
FreeURL(URL *url)
{
	url->refcnt--;
	if (url->refcnt) {
		return;
	}

	if (url->scheme) {
		free(url->scheme);
	}

	if (url->host) {
		free(url->host);
	}

	if (url->path) {
		free(url->path);
	}

	switch (url->auth_type) {
	case URLAuthTypeBasic:
		if (url->auth.basic.user) {
			free(url->auth.basic.user);
		}

		if (url->auth.basic.password) {
			free(url->auth.basic.password);
		}

		break;

	case URLAuthTypeNone:
	default:
		/* Nothing to do */
		break;
	}

	free(url);
}

#ifdef MODULE_TEST

/*
 * This test will, given urls as arguments, attempt to parse and re-print
 * them.
 */
void
main(int argc, char **argv)
{
	URL *url;
	char *urlstring;
	int i;
	int rc;

	if (argc == 1) {
		fprintf(stderr, "Usage: %s url [url ...]\n", argv[0]);
		exit(1);
	}

	for (i = 1; i < argc; i++) {
		printf("   URL: %s\n", argv[i]);
		rc = ParseHTTPURL(argv[i], &url);
		printf("    rc: %d\n", rc);
		if (rc == 0) {
			rc = URLString(url, &urlstring);
			if (rc == 0) {
				printf("String: %s\n", urlstring);
				free(urlstring);
			}
			FreeURL(url);
		}
	}
}

#endif
