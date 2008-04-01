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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


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
	ls_dbglvl_t level;
	gchar * domain;

	if (log_domain)
		domain = g_strdup_printf("GUI:%s", log_domain);
	else
		domain = g_strdup("GUI");

	level = G_LOG_LEVEL_MASK & log_level;
	/*
	 * Map glib logging levels to comparable liblogsvc levels.
	 * G_LOG_LEVEL_ERROR is the highest error condition causing
	 * an abort() so it needs to be mapped to LS_DBGLVL_EMERG
	 * instead of LS_DBGLVL_ERR which is non fatal.
	 */
	switch (level) {
		case G_LOG_LEVEL_ERROR:
			level = LS_DBGLVL_EMERG;
			break;
		case G_LOG_LEVEL_CRITICAL:
			level = LS_DBGLVL_ERR;
			break;
		case G_LOG_LEVEL_WARNING:
			level = LS_DBGLVL_WARN;
			break;
		case G_LOG_LEVEL_MESSAGE:
			level = LS_DBGLVL_INFO;
			break;
		case G_LOG_LEVEL_INFO:
			level = LS_DBGLVL_INFO;
			break;
		case G_LOG_LEVEL_DEBUG:
			level = LS_DBGLVL_INFO;
			break;
		default:
			level = LS_DBGLVL_NONE;
			break;
	}

	ls_write_dbg_message(domain, level, "%s\n", message);
	g_free(domain);
}

void
gui_error_logging_init(gchar *name)
{
	ls_init(NULL);
	g_log_set_default_handler(
	    gui_error_logging_handler,
	    (gpointer)name);
}
