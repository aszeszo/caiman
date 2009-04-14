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

#include <stdio.h>
#include <stdlib.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <string.h>
#include <errno.h>
#include <libscf.h>
#include "libaiscf.h"

/* ************************************************************ */
/*			Public Functions			*/
/* ************************************************************ */

/*
 * Function:	ai_delete_install_service
 * Description:
 *		Delete the smf property group with the name
 *		given in pg_name.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - name of the property group to delete
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *		Public
 */
ai_errno_t
ai_delete_install_service(scfutilhandle_t *handle, char *pg_name)
{
	if (handle == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	/*
	 * If handle->pg is null, then call the scf function
	 * to allocate and initialize the scf_propertygroup_t
	 * bound to handle.
	 */
	if (handle->pg == NULL) {
		if ((handle->pg = scf_pg_create(handle->handle)) == NULL)
			return (AI_CONFIG_ERR);
	}

	/*
	 * Get the default instance.
	 */
	if (ai_get_instance(handle, "default") != AI_SUCCESS) {
		return (AI_NO_SUCH_INSTANCE);
	}

	return (ai_delete_pg(handle, pg_name));
}
