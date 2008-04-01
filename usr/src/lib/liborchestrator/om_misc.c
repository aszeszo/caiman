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

#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/param.h>
#include <sys/types.h>

#include "orchestrator_private.h"

#include <ls_api.h>

/*
 * Global
 */

/*
 * om_get_error
 * This function returns the current error number set by the last called
 * orchestrator function.
 * Input:	None
 * Output:	None.
 * Return:	int16_t - One of the predefined orchestrator errors will
 *		be returned. If there is are no errors, 0 will be returned
 *		Each orchestrator function should set the om_errno to 0
 *		if there are no errors.
 */

int16_t
om_get_error()
{
	return (om_errno);
}

/*
 * om_set_error
 * This function sets the error number passed as the argument
 * Input:	int16_t errno _ the error Number that needs to be set
 * Output:	None.
 * Return:	None
 */
void
om_set_error(int16_t errno)
{
	om_errno = errno;
}

/*
 * om_debug_print()
 * Description:	Posts debug message
 */
void
om_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	/*LINTED*/
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("OM", dbg_lvl, buf);
	va_end(ap);
}

/*
 * om_log_print()
 * Description:	Posts log message
 */
void
om_log_print(char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	/*LINTED*/
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_log_message("OM", buf);
	va_end(ap);
}
