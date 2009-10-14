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
#include <libintl.h>
#include "libaiscf.h"

/*
 * Function:    libaiscf_scf_init
 * Description:
 *              Initialize the smf interface.
 * Parameters:	FMRI to connect the handle to
 * Return:
 *              scfutilhandle_t * - handle to scf
 *              NULL - failure
 * Scope:
 *              Private
 */
scfutilhandle_t *
libaiscf_scf_init(char *FMRI)
{
	scfutilhandle_t	*handle = NULL;

	handle = calloc(1, sizeof (scfutilhandle_t));
	if (handle == NULL)
		return (NULL);

	/*
	 * Create a handle to use for all communication
	 * with the smf repository
	 */
	handle->handle = scf_handle_create(SCF_VERSION);
	if (handle->handle == NULL) {
		free(handle);
		return (NULL);
	}

	/*
	 * Bind the handle to a running svc.configd daemon.
	 */
	if (scf_handle_bind(handle->handle) != 0) {
		(void) ai_scf_fini(handle);
		return (NULL);
	}

	/*
	 * Allocates a new scf_scope_t stored in the handle.
	 */
	handle->scope = scf_scope_create(handle->handle);

	/*
	 * Allocates a new scf_service_t in the handle.
	 */
	handle->service = scf_service_create(handle->handle);

	/*
	 * Allocate an scf_propertygroup_t in the handle.
	 */
	handle->pg = scf_pg_create(handle->handle);

	/* Allocate an scf_instance in the handle */
	handle->instance = scf_instance_create(handle->handle);

	/* Make sure we have everything to communicate with SMF */
	if (handle->scope == NULL || handle->service == NULL ||
	    handle->pg == NULL || handle->instance == NULL) {
		(void) ai_scf_fini(handle);
		return (NULL);
	}
	if (scf_handle_get_scope(handle->handle,
	    SCF_SCOPE_LOCAL, handle->scope) != 0) {
		(void) ai_scf_fini(handle);
		return (NULL);
	}
	if (scf_scope_get_service(handle->scope,
	    FMRI, handle->service) != 0) {
		(void) ai_scf_fini(handle);
		return (NULL);
	}

	return (handle);
}
