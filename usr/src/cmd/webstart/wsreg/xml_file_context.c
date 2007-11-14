/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)xml_file_context.c	1.7	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "xml_file_context.h"
#include "wsreg.h"

/*
 * Stores the private data associated with each
 * Xml file context object.
 */
typedef struct _Xml_file_context_private
{
	Xml_file_mode mode;
	int read_fd;
	int write_fd;
	unsigned short tab_count;
	int line_number;
} _Xml_file_context_private;

/*
 * Frees the specified file context.
 */
static void
xc_free(Xml_file_context *xc)
{
	free(xc->pdata);
	free(xc);
}

/*
 * Sets the specified file descriptor into the
 * specified file context.
 */
static void
xc_set_readfd(Xml_file_context *xc, int read_fd)
{
	xc->pdata->read_fd = read_fd;
}

/*
 * Returns the file descriptor used for reading
 * from the specified file context.
 */
static int
xc_get_readfd(Xml_file_context *xc)
{
	return (xc->pdata->read_fd);
}

/*
 * Sets the specified file descriptor into the
 * specified file context.
 */
static void
xc_set_writefd(Xml_file_context *xc, int write_fd)
{
	xc->pdata->write_fd = write_fd;
}

/*
 * Returns the file descriptor used for writing
 * from the specified file context.
 */
static int
xc_get_writefd(Xml_file_context *xc)
{
	return (xc->pdata->write_fd);
}

/*
 * Sets the access mode of the specified
 * file context.
 */
static void
xc_set_mode(Xml_file_context *xc, Xml_file_mode mode)
{
	xc->pdata->mode = mode;
}

/*
 * Returns the access mode of the specified
 * file context.
 */
static Xml_file_mode
xc_get_mode(Xml_file_context *xc)
{
	return (xc->pdata->mode);
}

/*
 * Increments the tab count of the specified
 * file context.
 */
static void
xc_tab_increment(Xml_file_context *xc)
{
	xc->pdata->tab_count++;
}

/*
 * Decrements the tab count of the specified
 * file context.
 */
static void
xc_tab_decrement(Xml_file_context *xc)
{
	xc->pdata->tab_count--;
}

/*
 * Returns the tab count from the specified
 * file context.
 */
static int
xc_get_tab_count(Xml_file_context *xc)
{
	return (xc->pdata->tab_count);
}

/*
 * Increments the line count of the specified
 * file context.
 */
static void
xc_line_increment(Xml_file_context *xc)
{
	xc->pdata->line_number++;
}

/*
 * Returns the line number from the specified
 * file context.
 */
static int
xc_get_line_number(Xml_file_context *xc)
{
	return (xc->pdata->line_number);
}

/*
 * Creates a new file context.
 */
Xml_file_context*
_wsreg_xfc_create()
{
	Xml_file_context *xc = (Xml_file_context*)
	    wsreg_malloc(sizeof (Xml_file_context));
	struct _Xml_file_context_private *p = NULL;
	memset(xc, 0, sizeof (Xml_file_context));

	/*
	 * Load the method set.
	 */
	xc->free = xc_free;
	xc->set_readfd = xc_set_readfd;
	xc->get_readfd = xc_get_readfd;
	xc->set_writefd = xc_set_writefd;
	xc->get_writefd = xc_get_writefd;
	xc->set_mode = xc_set_mode;
	xc->get_mode = xc_get_mode;
	xc->tab_increment = xc_tab_increment;
	xc->tab_decrement = xc_tab_decrement;
	xc->get_tab_count = xc_get_tab_count;
	xc->line_increment = xc_line_increment;
	xc->get_line_number = xc_get_line_number;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Xml_file_context_private *)
	    wsreg_malloc(sizeof (struct _Xml_file_context_private));
	memset(p, 0, sizeof (struct _Xml_file_context_private));
	p->read_fd = -1;
	p->write_fd = -1;
	p->line_number = 1;
	xc->pdata = p;
	return (xc);
}
