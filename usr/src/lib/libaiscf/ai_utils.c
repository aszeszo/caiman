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
#include <libintl.h>
#include <string.h>
#include <errno.h>
#include <libscf.h>
#include "libaiscf.h"

/* ************************************************************ */
/*			Public Functions			*/
/* ************************************************************ */

/*
 * Function:    ai_get_instance
 * Description:
 *		Sets handle->instance to the child instance
 *		of the service specified by the instname.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *             	instname - name of the instance to "get"
 * Return:
 *		AI_SUCCESS - Success
 *		ai_errno_t - failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_get_instance(scfutilhandle_t *handle, char *instname)
{
	if (handle == NULL || instname == NULL)
		return (AI_INVAL_ARG);

	/*
	 * Set handle->instance to correspond to the child
	 * instance specified by instname.
	 */
	if (scf_service_get_instance(handle->service, instname,
	    handle->instance) != 0) {
		return (AI_NO_SUCH_INSTANCE);
	}
	return (AI_SUCCESS);
}

/*
 * Function:    ai_create_pg
 * Description:
 *		Create the property group.
 *		Note: This function expects the instance to be in the handle.
 *			The instance is retrieved using the ai_get_instance
 *			function.
 * Parameters:
 *             handle - scfutilhandle_t * for use with scf calls.
 *             pg_name - name of the property group to create.
 * Return:
 *             0 - Success
 *             ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_create_pg(scfutilhandle_t *handle, char *pg_name)
{
	if (handle == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	if (scf_instance_get_pg(handle->instance, pg_name,
	    handle->pg) == 0) {
		/*
		 * The property group exists.
		 * Nothing more to do.
		 */
		return (AI_SUCCESS);
	}

	/*
	 * Create the property group.
	 */
	if (scf_instance_add_pg(handle->instance, pg_name,
	    SCF_GROUP_APPLICATION, 0, handle->pg) != 0) {
		if (scf_error() == SCF_ERROR_PERMISSION_DENIED)
			return (AI_NO_PERMISSION);
		return (AI_NO_SUCH_PG);
	}
	return (AI_SUCCESS);
}

/*
 * Function:    ai_delete_pg
 * Description:
 *		Delete the property group.
 *		Note: This function expects the instance to be in the handle.
 *			The instance is retrieved using the ai_get_instance
 *			function.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - name of the property group to delete.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_delete_pg(scfutilhandle_t *handle, char *pg_name)
{
	int	ret = AI_SUCCESS;

	if (handle == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	/*
	 * First check to see if the property group exists. If it
	 * does, delete it.
	 * If the property group doesn't exist there's no work for
	 * us to do so just return success.
	 */
	if (scf_instance_get_pg(handle->instance, pg_name, handle->pg) == 0) {
		/* does exist so delete it */
		if (scf_pg_delete(handle->pg) != 0)
			ret = AI_NO_SUCH_PG;
	}
	return (ret);
}


/*
 * Function:    ai_get_pg
 * Description:
 *		Get the property group.
 *		Note: This function expects the instance to be in the handle.
 *			The instance is retrieved using the ai_get_instance
 *			function.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - name of the property group to get.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_get_pg(scfutilhandle_t *handle, char *pg_name)
{
	if (handle == NULL || handle->instance == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	if (scf_instance_get_pg(handle->instance, pg_name, handle->pg) != 0) {
		return (AI_NO_SUCH_PG);
	}
	return (AI_SUCCESS);
}

/*
 * Function:    ai_make_pg_name
 * Description:
 *		Prepend AI to the beginning of the name so that we
 *		don't have an issue where our property group name
 *		conflicts with one of the  general names.
 *		The caller should free the memory allocated for
 *		the return property group name.
 * Parameters:
 *		pg_name - Name of the property group.
 * Return:
 *		char * - New name of the property group.
 *		NULL - failure
 * Scope:
 *              Public
 */
char *
ai_make_pg_name(char *pg_name)
{
	char	*ai_name = NULL;

	if (pg_name == NULL)
		return (NULL);

	ai_name = malloc(strlen(pg_name) + 3);
	if (ai_name == NULL)
		return (NULL);
	(void) sprintf(ai_name, "AI%s", pg_name);
	return (ai_name);
}

/*
 * Function:	ai_read_property
 * Description:
 *		Read the designated property from the property group.
 *		Return the property value.
 *		Since at this point we are only dealing with strings,
 *		we make the assumption that it will be a string.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - Name of the property group to read from.
 *		prop_name - Name of the property to read.
 *		prop_value - Address to return the value within.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 *
 * Scope:
 *              Public
 */
ai_errno_t
ai_read_property(
	scfutilhandle_t *handle,
	char *pg_name,
	char *prop_name,
	char **prop_value)
{
	scf_property_t	*prop = NULL;
	scf_value_t	*value = NULL;
	char		*valuestr = NULL;
	ssize_t		vallen;
	int		ret = AI_SUCCESS;

	if (handle == NULL || pg_name == NULL || prop_name == NULL)
		return (AI_INVAL_ARG);

	vallen = scf_limit(SCF_LIMIT_MAX_VALUE_LENGTH);
	if (vallen == (ssize_t)-1)
		return (AI_NO_MEM);

	prop = scf_property_create(handle->handle);
	value = scf_value_create(handle->handle);
	valuestr = malloc(vallen + 1);
	if (prop == NULL || value == NULL || valuestr == NULL) {
		ret = AI_NO_MEM;
		goto out;
	}

	if ((ret = ai_get_instance(handle, "default")) != AI_SUCCESS) {
		goto out;
	}

	if (handle->pg == NULL) {
		ret = AI_NO_SUCH_PG;
		goto out;
	}

	if ((ret = ai_get_pg(handle, pg_name)) != AI_SUCCESS) {
		goto out;
	}

	if (scf_pg_get_property(handle->pg, prop_name, prop) == 0) {
		/* Found the property so get the value */
		if (scf_property_get_value(prop, value) == 0) {
			if (scf_value_get_astring(value, valuestr,
			    vallen) >= 0) {
				*prop_value = strdup(valuestr);
				if (*prop_value == NULL) {
					ret = AI_NO_MEM;
					goto out;
				}
			}
		}
	}
out:
	free(valuestr);
	scf_value_destroy(value);
	scf_property_destroy(prop);

	return (ret);

}

/*
 * Function:    ai_change_property
 * Description:
 *		Change the value of the property in the property group.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - Name of the property group to change the
 *			property in.
 *		prop_name - Name of the property to change.
 *		prop_value - Value to change the property to.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_change_property(
	scfutilhandle_t *handle,
	char *pg_name,
	char *prop_name,
	char *prop_value)
{
	scf_property_t	*prop = NULL;
	int		ret = AI_SUCCESS;

	if (handle == NULL || pg_name == NULL || prop_name == NULL ||
	    prop_value == NULL)
		return (AI_INVAL_ARG);

	if ((ret = ai_start_transaction(handle, pg_name)) != AI_SUCCESS) {
		return (ret);
	}

	/*
	 * Make sure the property exists in this property group.
	 * If it doesn't, that's an error and flag it.
	 */
	prop = scf_property_create(handle->handle);
	if (prop == NULL) {
		ai_abort_transaction(handle);
		return (AI_NO_MEM);
	}

	if (scf_pg_get_property(handle->pg, prop_name, prop) != 0) {
		ret = AI_INVAL_ARG;
		ai_abort_transaction(handle);
		goto out;
	}

	/*
	 * Set the property value in the transaction.
	 */
	if ((ret = ai_transaction_set_property(handle, prop_name,
	    prop_value)) != AI_SUCCESS) {
		ai_abort_transaction(handle);
		goto out;
	}

	if ((ret = ai_end_transaction(handle)) != AI_SUCCESS) {
		ai_abort_transaction(handle);
		goto out;
	}

out:
	if (prop != NULL)
		scf_property_destroy(prop);
	return (ret);
}

/*
 * Function:	ai_set_property
 * Description:
 *		Add the designated property to the property
 *		group with the value given.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - Name of the property group to set the
 *			property in.
 *		prop_name - Name of the property to set.
 *		prop_value - Value to set the property to.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_set_property(
	scfutilhandle_t *handle,
	char *pg_name,
	char *prop_name,
	char *prop_value)
{
	int	ret = AI_SUCCESS;

	if (handle == NULL || pg_name == NULL || prop_name == NULL ||
	    prop_value == NULL)
		return (AI_INVAL_ARG);

	if ((ret = ai_start_transaction(handle, pg_name)) != AI_SUCCESS) {
		return (ret);
	}

	if ((ret = ai_transaction_set_property(handle, prop_name,
	    prop_value)) != AI_SUCCESS) {
		ai_abort_transaction(handle);
		goto out;
	}

	if ((ret = ai_end_transaction(handle)) != AI_SUCCESS) {
		ai_abort_transaction(handle);
		goto out;
	}

out:
	return (ret);
}

/*
 * Function:   	ai_read_all_props_in_pg
 * Description:
 *		Iterate through all of the properties in a property
 *		group. Return the properties and their values.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_name - Name of the property group to read the
 *			properties from.
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_read_all_props_in_pg(
	scfutilhandle_t *handle,
	char *pg_name,
	ai_prop_list_t **p_prop_list)
{
	scf_iter_t	*iter = NULL;
	scf_value_t	*value = NULL;
	scf_property_t	*prop = NULL;
	char		*name = NULL;
	ssize_t		vallen;
	ssize_t		namelen;
	char		*valuestr = NULL;
	int		ret = 0;
	boolean_t	is_first = B_TRUE;
	ai_prop_list_t	*prop_head = NULL;
	ai_prop_list_t	*prop_list = calloc(1, sizeof (ai_prop_list_t));

	if (handle == NULL || pg_name == NULL)
		return (AI_INVAL_ARG);

	if (prop_list == NULL)
		return (AI_NO_MEM);

	prop_head = prop_list;

	vallen = scf_limit(SCF_LIMIT_MAX_VALUE_LENGTH);
	if (vallen == (ssize_t)-1)
		return (AI_NO_MEM);

	namelen = scf_limit(SCF_LIMIT_MAX_NAME_LENGTH);
	if (namelen == (ssize_t)-1)
		return (AI_NO_MEM);
	name = malloc(namelen + 1);
	valuestr = malloc(vallen + 1);
	if (valuestr == NULL || name == NULL) {
		ret = AI_NO_MEM;
		goto out;
	}

	if ((ret = ai_get_instance(handle, "default")) != AI_SUCCESS) {
		goto out;
	}

	if (handle->pg == NULL) {
		ret = AI_NO_SUCH_PG;
		goto out;
	}

	if ((ret = ai_get_pg(handle, pg_name)) != AI_SUCCESS) {
		goto out;
	}

	iter = scf_iter_create(handle->handle);
	prop = scf_property_create(handle->handle);
	value = scf_value_create(handle->handle);

	if (iter == NULL || prop == NULL || value == NULL) {
		ret = AI_NO_MEM;
		goto out;
	}

	/* Iterate over the property group properties */
	if (scf_iter_pg_properties(iter, handle->pg) != 0) {
		ret = AI_PG_ITER_ERR;
		goto out;
	}

	while (scf_iter_next_property(iter, prop) > 0) {
		ssize_t namelen = scf_limit(SCF_LIMIT_MAX_NAME_LENGTH);
		if (namelen == (ssize_t)-1) {
			ai_free_prop_list(prop_head);
			ret = AI_NO_MEM;
			goto out;
		}
		if (scf_property_get_name(prop, name, namelen) > 0) {
			if (scf_property_get_value(prop, value) == 0) {
				if (scf_value_get_astring(value, valuestr,
				    vallen) >= 0) {
					if (is_first) {
						prop_list->name = strdup(name);
						prop_list->valstr =
						    strdup(valuestr);
						prop_list->next = NULL;
						if (prop_list->name == NULL ||
						    prop_list->valstr == NULL) {
							ai_free_prop_list(
							    prop_head);
							ret = AI_NO_MEM;
							goto out;
						}
						is_first = B_FALSE;
						continue;
					}
					prop_list->next = calloc(1,
					    sizeof (ai_prop_list_t));
					if (prop_list->next == NULL) {
						ret = AI_NO_MEM;
						ai_free_prop_list(prop_head);
						goto out;
					}
					prop_list = prop_list->next;
					prop_list->name = strdup(name);
					prop_list->valstr = strdup(valuestr);
					prop_list->next = NULL;
					if (prop_list->name == NULL ||
					    prop_list->valstr == NULL) {
						ret = AI_NO_MEM;
						ai_free_prop_list(prop_head);
						goto out;
					}
				}
			}
		}
	}
out:
	*p_prop_list = prop_head;
	if (value != NULL)
		scf_value_destroy(value);
	if (prop != NULL)
		scf_property_destroy(prop);
	if (iter != NULL)
		scf_iter_destroy(iter);
	free(name);
	free(valuestr);

	return (ret);
}

/*
 * Function: 	ai_get_pgs
 * Description:
 *		Get all the property groups with AI as the
 *		first 2 letters.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 *		pg_list - return list of property groups
 * Return:
 *		0 - Success
 *		ai_errno_t - Failure
 * Scope:
 *              Public
 */
ai_errno_t
ai_get_pgs(scfutilhandle_t *handle, ai_pg_list_t **p_pg_list)
{
	ai_pg_list_t	*pg_head, *pg_list;
	scf_iter_t	*iter = NULL;
	char		*buff = NULL;
	ssize_t		namelen = 0;
	int		ret = AI_SUCCESS;
	boolean_t	is_first = B_TRUE;

	namelen = scf_limit(SCF_LIMIT_MAX_NAME_LENGTH);
	if (namelen == (ssize_t)-1)
		return (AI_NO_MEM);

	buff = malloc(namelen + 1);
	if (buff == NULL) {
		return (AI_NO_MEM);
	}

	pg_head = pg_list = calloc(1, sizeof (ai_pg_list_t));
	if (pg_list == NULL) {
		ret = AI_NO_MEM;
		goto out;
	}

	if (ai_get_instance(handle, "default") != AI_SUCCESS) {
		ret = AI_NO_SUCH_INSTANCE;
		goto out;
	}

	iter = scf_iter_create(handle->handle);
	if (iter == NULL) {
		ret = AI_PG_ITER_ERR;
		goto out;
	}

	if (scf_iter_instance_pgs(iter, handle->instance) != 0) {
		ret = AI_NO_MEM;
		goto out;
	}

	while (scf_iter_next_pg(iter, handle->pg) > 0) {
		ssize_t namelen = scf_limit(SCF_LIMIT_MAX_NAME_LENGTH);
		if (namelen == (ssize_t)-1) {
			ai_free_pg_list(pg_head);
			pg_list = NULL;
			ret = AI_NO_MEM;
			goto out;
		}
		if (scf_pg_get_name(handle->pg, buff, namelen) >= 0) {
			if (strncmp("AI", buff, 2) == 0) {
				if (is_first) {
					pg_list->pg_name = strdup(buff);
					pg_list->next = NULL;
					if (pg_list->pg_name == NULL) {
						ret = AI_NO_MEM;
						ai_free_pg_list(pg_head);
						pg_list = NULL;
						goto out;
					}
					is_first = B_FALSE;
					continue;
				}
				pg_list->next = calloc(1,
				    sizeof (ai_pg_list_t));
				if (pg_list->next == NULL) {
					ret = AI_NO_MEM;
					ai_free_pg_list(pg_head);
					pg_list = NULL;
					goto out;
				}
				pg_list = pg_list->next;
				pg_list->pg_name = strdup(buff);
				pg_list->next = NULL;
				if (pg_list->pg_name == NULL) {
					ret = AI_NO_MEM;
					ai_free_pg_list(pg_head);
					pg_list = NULL;
					goto out;
				}
			}
		}
	}
out:
	*p_pg_list = pg_head;
	if (iter != NULL)
		scf_iter_destroy(iter);
	free(buff);

	return (ret);
}

/*
 * Function:   	ai_scf_fini
 * Description:
 *		Close down the scf data structures.
 * Parameters:
 *		handle - scfutilhandle_t * for use with scf calls.
 * Return:
 *		None
 * Scope:
 *              Public
 */
void
ai_scf_fini(scfutilhandle_t *handle)
{
	boolean_t	unbind = B_FALSE;

	if (handle == NULL)
		return;

	if (handle->scope != NULL) {
		unbind = B_TRUE;
		scf_scope_destroy(handle->scope);
	}
	if (handle->instance != NULL)
		scf_instance_destroy(handle->instance);
	if (handle->service != NULL)
		scf_service_destroy(handle->service);
	if (handle->pg != NULL)
		scf_pg_destroy(handle->pg);
	if (handle->handle != NULL) {
		if (unbind)
			(void) scf_handle_unbind(handle->handle);
		scf_handle_destroy(handle->handle);
	}
	free(handle);
}

/*
 * Function:	ai_scf_init
 * Description:
 *		Initialize the smf interfaces.
 * Parameters:
 * Return:
 *		scfutilhandle_t * - handle to scf
 *		NULL - failure
 * Scope:
 *              Public
 */
scfutilhandle_t *
ai_scf_init()
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
	 * Allocates a new scf_scope_t bound to handle.
	 */
	handle->scope = scf_scope_create(handle->handle);

	/*
	 * Allocates and initializes a new scf_service_t bound
	 * to our handle.
	 */
	handle->service = scf_service_create(handle->handle);

	/*
	 * Allocate and initialze an scf_propertygroup_t bound to
	 * our handle.
	 */
	handle->pg = scf_pg_create(handle->handle);

	/* Make sure we have everything for SMF running */
	handle->instance = scf_instance_create(handle->handle);
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
	    AI_DEFAULT_SERVER_SVC_NAME, handle->service) != 0) {
		(void) ai_scf_fini(handle);
		return (NULL);
	}

	return (handle);
}

/*
 * Function:	ai_strerror
 * Description:
 *		Determine error message to print
 *		based upon error code.
 * Parameters:
 *		ai_err - Error code to determine
 *		    print from.
 * Return:
 *		char * - error string to print
 * Scope:
 *              Public
 */
char *
ai_strerror(int ai_err)
{

	switch (ai_err) {
		case AI_SUCCESS:
			return (gettext("No Error"));
		case AI_NO_SUCH_INSTANCE:
			return (gettext("SMF instance doesn't exist"));
		case AI_NO_SUCH_PG:
			return (gettext("Property group doesn't exist"));
		case AI_CONFIG_ERR:
			return (gettext("Server Configuration error"));
		case AI_SYSTEM_ERR:
			return (gettext("SMF System Error"));
		case AI_NO_PERMISSION:
			return (gettext("Permission Denied"));
		case AI_INVAL_ARG:
			return (gettext("Invalid argument"));
		case AI_TRANS_ERR:
			return (gettext("Transaction failed"));
		case AI_NO_MEM:
			return (gettext("Memory Allocation failure"));
		case AI_PG_CREAT_ERR:
			return (gettext("Failed to create PG"));
		case AI_PG_DELETE_ERR:
			return (gettext("Failed to delete PG"));
		case AI_PG_ITER_ERR:
			return (gettext("Property iteration failure"));
		case AI_PG_EXISTS_ERR:
			return (gettext("Property group already exists"));
	}
	if (ai_err >= 6000 && ai_err < 7000) {
		const char *error_str = NULL;
		/*
		 * This is most likely an scf library error so grab the
		 * error string from there if possible.
		 */
		if ((error_str = scf_strerror(ai_err)) != NULL)
			return ((char *)error_str);
	}
	return (gettext("Unknown Error"));
}

/*
 * Function:	ai_free_prop_list
 * Description:
 *		Frees the memory in ai_prop_list_t
 * Parameters:
 *		plist - point to an ai_prop_list_t struct.
 * Return:
 *		None
 * Scope:
 *              Public
 */
void
ai_free_prop_list(ai_prop_list_t *plist)
{
	ai_prop_list_t *tmp_plist = NULL;

	while (plist != NULL) {
		free(plist->name);
		free(plist->valstr);
		tmp_plist = plist->next;
		free(plist);
		plist = tmp_plist;
	}
}

/*
 * Function:	ai_free_pg_list
 * Description:
 *		Frees the memory in ai_pg_list
 * Parameters:
 *		plist - pointer to an ai_pg_list_t struct.
 * Return:
 *		None
 * Scope:
 *              Public
 */
void
ai_free_pg_list(ai_pg_list_t *plist)
{
	ai_pg_list_t	*tmp_plist = NULL;

	while (plist != NULL) {
		free(plist->pg_name);
		tmp_plist = plist->next;
		free(plist);
		plist = tmp_plist;
	}
}
