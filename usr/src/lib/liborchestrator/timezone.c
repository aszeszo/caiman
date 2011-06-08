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
 * Copyright (c) 2007, 2011, Oracle and/or its affiliates. All rights reserved.
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

#include "orchestrator_private.h"

int
om_set_time_zone(char *timezone)
{
	int		status;
	static char	env_tz[256];

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
