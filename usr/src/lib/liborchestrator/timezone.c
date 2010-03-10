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
 * Copyright 2010 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <dlfcn.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <crypt.h>
#include <unistd.h>

#include "admutil.h"

#include "orchestrator_private.h"

int
om_set_time_zone(char *timezone)
{
	int		status;
	static char	env_tz[256];

	status = set_timezone(timezone, "/");
	if (status != 0) {
		/*
		 * A status of -1 indicates a bad timezone specification.
		 * We don't want to put this value in to the environment
		 * so we return with a failure here. Other errors indicate
		 * rtc errors which are not fatal. We log them and go
		 * on.
		 */

		if (status == -1) {
			om_log_print("Invalid timezone: %s\n", timezone);
			om_set_error(OM_INVALID_TIMEZONE);
			return (OM_FAILURE);
		}
		om_log_print("Failure to set rtc value for %s\n",
		    timezone);
	}
	(void) snprintf(env_tz, sizeof (env_tz), "TZ=%s", timezone);
	om_log_print("Timezone setting will be %s\n", env_tz);
	if ((status = putenv(env_tz)) != 0) {
		om_log_print("Could not set TZ: %s in environment: %d\n",
		    timezone, status);
		om_set_error(OM_TIMEZONE_NOT_SET);
		return (OM_FAILURE);
	}
	om_log_print("Set timezone \n");
	return (OM_SUCCESS);
}
