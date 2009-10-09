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
 * Function:    ai_start_transaction
 * Description:
 *		Start an SMF transaction so we can deal with properties.
 *		Hold the transaction in the handle and allow property
 *		adds/deletes/updates and then close the transaction.
 *		An ai_start_transaction must be followed by an
 *		ai_end_transaction before another ai_start_transaction can
 *		be done.
 * Parameters:
 *              handle - scfutilhandle_t * for use with scf calls.
 *              pg_name - name of the property group to start the
 *			transaction on.
 * Return:
 *              0 - Success
 *              ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_start_transaction(scfutilhandle_t *handle, char *pg_name)
{
	if (handle == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	/*
	 * Get the default instance.
	 */
	if (ai_get_instance(handle, "default") != AI_SUCCESS) {
		return (AI_NO_SUCH_INSTANCE);
	}

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
	 * Get the property group specified in pg_name. That
	 * is the pg the transaction will be performed upon.
	 */
	if (ai_get_pg(handle, pg_name) != AI_SUCCESS) {
		return (AI_NO_SUCH_PG);
	}

	/*
	 * Allocates and initializes an scf_transaction_t bound
	 * to handle.
	 */
	handle->trans = scf_transaction_create(handle->handle);
	if (handle->trans == NULL)
		return (AI_TRANS_ERR);

	/*
	 * Setup the transaction to modify the property
	 * group.
	 */
	if (scf_transaction_start(handle->trans, handle->pg) != 0) {
		scf_transaction_destroy(handle->trans);
		handle->trans = NULL;
		return (AI_TRANS_ERR);
	}

	return (AI_SUCCESS);
}

/*
 * Function:    ai_end_transaction
 * Description:
 *		Commmit the changes that were added to the transaction in
 *		the handle. Cleanup.
 * Parameters:
 *              handle - scfutilhandle_t * for use with scf calls.
 * Return:
 *              0 - Success
 *              ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_end_transaction(scfutilhandle_t *handle)
{
	if (handle == NULL || handle->trans == NULL)
		return (AI_INVAL_ARG);

	if (scf_transaction_commit(handle->trans) == -1)
		return (AI_SYSTEM_ERR);

	scf_transaction_destroy_children(handle->trans);
	scf_transaction_destroy(handle->trans);
	handle->trans = NULL;

	return (AI_SUCCESS);
}

/*
 * Function:    ai_transaction_set_property
 * Description:
 *		Set the designated smf property.
 * Parameters:
 *              handle - scfutilhandle_t * for use with scf calls.
 *              prop_name - Name of the property to set the value.
 *		prop_value - Value to set on the property
 * Return:
 *              0 - Success
 *              ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_transaction_set_property(
	scfutilhandle_t *handle,
	char *prop_name,
	char *prop_value)
{
	scf_value_t		*value = NULL;
	scf_transaction_entry_t *entry = NULL;
	int			ret = AI_SUCCESS;

	if (handle == NULL || prop_name == NULL || prop_value == NULL)
		return (AI_INVAL_ARG);

	value = scf_value_create(handle->handle);
	entry = scf_entry_create(handle->handle);

	if (value != NULL && entry != NULL) {
		/*
		 * Add a new transaction entry to the transaction.
		 */
		if (scf_transaction_property_change(handle->trans, entry,
		    prop_name, SCF_TYPE_ASTRING) == 0 ||
		    scf_transaction_property_new(handle->trans, entry,
		    prop_name, SCF_TYPE_ASTRING) == 0) {
			if (scf_value_set_astring(value, prop_value) == 0) {
				if (scf_entry_add_value(entry, value) != 0) {
					ret = AI_SYSTEM_ERR;
				}
				/* The value is in the transaction */
				value = NULL;
			} else {
				ret = AI_SYSTEM_ERR;
			}
			/* The entry is in the transaction */
			entry = NULL;
		} else {
			ret = AI_SYSTEM_ERR;
		}
	} else {
		ret = AI_SYSTEM_ERR;
	}

	if (ret == AI_SYSTEM_ERR) {
		switch (scf_error()) {
		case SCF_ERROR_PERMISSION_DENIED:
			ret = AI_NO_PERMISSION;
			break;
		}
	}

	if (value != NULL)
		scf_value_destroy(value);
	if (entry != NULL)
		scf_entry_destroy(entry);

	return (ret);
}

/*
 * ai_abort_transaction(handle)
 * Description:
 *		Abort the changes that were added to the transaction in the
 *		handle. Do the necessary cleanup.
 * Parameters:
 *              handle - scfutilhandle_t * for use with scf calls.
 * Return:
 *		None
 * Scope:
 *              Public
 */
void
ai_abort_transaction(scfutilhandle_t *handle)
{
	if (handle->trans != NULL) {
		scf_transaction_reset_all(handle->trans);
		scf_transaction_destroy_children(handle->trans);
		scf_transaction_destroy(handle->trans);
		handle->trans = NULL;
	}
}
