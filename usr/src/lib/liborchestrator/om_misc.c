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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <fcntl.h>
#include <libintl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/param.h>
#include <sys/types.h>

#include "orchestrator_private.h"

#include <ls_api.h>

/*
 * array of om_failure_t structures describing all potential failures
 * orchestrator can return back to the main install engine
 *
 * The array element contains following information:
 *  - error code as defined in orchestrator_api.h
 *  - string identifying where the failure happened
 *  - string identifying reason of the failure
 *
 * Strings can be set to NULL - it indicates that the error code doesn't
 * carry this information
 *
 * The array is not public, since it is assumed to be accessed by means
 * of following methods (defined later below):
 *  om_get_failure_source()
 *     - returns string describing where the failure happened
 *  om_get_failure_reason()
 *     - returns string describing why the failure happened
 *
 */

static om_failure_t om_failure_description_array[] =
{
	{ OM_NO_SPACE,
	"Orchestrator",
	"Ran out of free memory" },

	{ OM_NO_INSTALL_TARGET,
	"Orchestrator",
	"No installation target was specified" },

	{ OM_BAD_INSTALL_TARGET,
	"Orchestrator",
	"Invalid installation target" },

	{ OM_NO_PARTITION_FOUND,
	"Orchestrator",
	"Install failed because there is no Solaris partition.\n"
	"To fix the problem, the user can do the following:\n"
	"  - delete all non-Solaris partitions using the manifest,\n"
	"  - or create a Solaris partition using the manifest,\n"
	"  - or create a Solaris partition before running the installer." },

	{ OM_ZFS_ROOT_POOL_EXISTS,
	"Orchestrator",
	"Target disk already contains ZFS root pool 'rpool'" },

	{ OM_ERROR_THREAD_CREATE,
	"Orchestrator",
	"Could not spawn new thread for the installer" },

	{ OM_TRANSFER_FAILED,
	"Transfer",
	"Transferring the files from the source failed."
	" Please see previous messages for more details" },

	{ OM_TARGET_INSTANTIATION_FAILED,
	"Target Instantiation",
	"Please see previous messages for more details" },

	{ OM_NO_TARGET_ATTRS,
	"Orchestrator",
	"Mandatory attributes describing the target not provided" },

	{ OM_ICT_FAILURE,
	"Installation Completion",
	"One or more installation completion tasks failed."
	" Please see previous messages for more details" }
};

/*
 * om_find_failure_in_array
 *
 * Try to find element in array of failures matching given error code.
 *
 * Input:	error code
 * Output:	None
 * Return:	index into array or -1 if element was not found
 */

static int
om_find_failure_in_array(int err_code)
{
	int	index;
	int	total_elem_num = sizeof (om_failure_description_array) /
	    sizeof (om_failure_description_array[0]);

	for (index = 0; index < total_elem_num &&
	    om_failure_description_array[index].code != err_code; index++)
		;

	if (index < total_elem_num)
		return (index);
	else
		return (-1);
}


/*
 * Global
 */

/*
 * om_is_valid_failure_code
 * Check if provided failure code is valid. Valid failure codes have
 * their entries in arrays of failures.
 *
 * Input:	error code
 * Output:	None.
 * Return:	B_TRUE if failure code is valid, otherwise B_FALSE
 */
boolean_t
om_is_valid_failure_code(int16_t err_code)
{
	if (om_find_failure_in_array(err_code) != -1)
		return (B_TRUE);
	else
		return (B_FALSE);
}


/*
 * om_get_failure_source
 * Determine the source of the failure.
 *
 * Input:	error code
 * Output:	None.
 * Return:	string describing where the failure occured or NULL if this
 *		information can't be determined.
 */
char *
om_get_failure_source(int16_t err_code)
{
	int	index;

	if ((index = om_find_failure_in_array(err_code)) != -1)
		return (gettext(om_failure_description_array[index].source));
	else
		return (NULL);
}


/*
 * om_get_failure_reason
 * Determine the reason of the failure.
 *
 * Input:	error code
 * Output:	None.
 * Return:	string describing why the failure occured or NULL if this
 *		information can't be determined.
 */
char *
om_get_failure_reason(int16_t err_code)
{
	int	index;

	if ((index = om_find_failure_in_array(err_code)) != -1)
		return (gettext(om_failure_description_array[index].reason));
	else
		return (NULL);
}

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

/*
 * om_log_std()
 * Description:	Posts log message, then to stdout and/or stderr
 */
void
om_log_std(ls_stdouterr_t stdouterr, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN] = "";

	va_start(ap, fmt);
	/*LINTED*/
	(void) vsprintf(buf, fmt, ap);
	(void) ls_log_std(stdouterr, "OM", buf);
	va_end(ap);
}
