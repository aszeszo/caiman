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

/* Copyright (c) 1984, 1986, 1987, 1988, 1989 AT&T */
/* All Rights Reserved */




/* Public Function Prototypes */

void    	canoninplace(char *);

void
canoninplace(char *src)
{
	char *dst;
	char *src_start;

	/* keep a ptr to the beginning of the src string */
	src_start = src;

	dst = src;
	while (*src) {
		if (*src == '/') {
			*dst++ = '/';
			while (*src == '/')
				src++;
		} else
			*dst++ = *src++;
	}

	/*
	 * remove any trailing slashes, unless the whole string is just "/".
	 * If the whole string is "/" (i.e. if the last '/' cahr in dst
	 * in the beginning of the original string), just terminate it
	 * and return "/".
	 */
	if ((*(dst - 1) == '/') && ((dst - 1) != src_start))
		dst--;
	*dst = '\0';
}
