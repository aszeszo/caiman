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
#pragma ident	"@(#)error-logging.c	1.1	07/08/03 SMI"


#include <unistd.h>
#include <stdio.h>
#include <config.h>
#include "error-logging.h"

void
gui_error_logging_handler(
	const gchar *log_domain,
	GLogLevelFlags log_level,
	const gchar *message,
	gpointer user_data)
{
	static FILE *fp = NULL;
	static gint pid = -1;
	guint level;
	gchar * leveltext;
	gchar * domain;
	gchar *package = (gchar *)user_data;

	if (pid < 0) {
		pid = (gint) getpid();
	}

	if (log_domain)
		domain = g_strdup_printf("%s-", log_domain);
	else
		domain = g_strdup("");

	if (!fp) {
		const gchar *filename = "/tmp/gui-install_log";
		fp = fopen(filename, "a+b");
		if (!fp) {
			fprintf(stderr,
				"** (%s:%d): %sWARNING **: Couldn't open log file: %s. "
				"Logging to stderr instead\n",
				package, pid, domain, filename);
			fp = stderr;
		}
	}

	level = G_LOG_LEVEL_MASK & log_level;
	switch (level) {
		case G_LOG_LEVEL_ERROR:
			leveltext = "ERROR";
			break;
		case G_LOG_LEVEL_CRITICAL:
			leveltext = "CRITICAL";
			break;
		case G_LOG_LEVEL_WARNING:
			leveltext = "WARNING";
			break;
		case G_LOG_LEVEL_MESSAGE:
			leveltext = "MESSAGE";
			break;
		case G_LOG_LEVEL_INFO:
			leveltext = "INFO";
			break;
		case G_LOG_LEVEL_DEBUG:
			leveltext = "DEBUG";
			break;
		default:
			leveltext = "";
			break;
	}

	fprintf(fp,
		"%s(%s:%d): %s%s **: %s\n",
		log_domain ? "" : "** ",
		package,
		pid,
		domain,
		leveltext,
		message);
	fflush(fp);
	g_free(domain);
}

void
gui_error_logging_init(gchar *name)
{
	g_log_set_default_handler(
		gui_error_logging_handler,
		(gpointer)name);
}
