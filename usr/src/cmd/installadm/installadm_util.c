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
#include <locale.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>

#include "installadm.h"

/*
 * Installadm utility functions
 */
boolean_t get_service_props(scfutilhandle_t *, char *, service_data_t *);
boolean_t set_service_props(scfutilhandle_t *, char *, service_data_t);
boolean_t check_port_in_use(scfutilhandle_t *, uint16_t);

/*
 * validate_service_name()
 * Verify that characters used in a string are limited to alphanumerics, hyphen
 * and underscore.
 *
 * Input:
 * char *check_this	- String to check
 *
 * Returns:
 * boolean:
 *	B_TRUE: string verifies.
 *	B_FALSE: string doesn't verify or is NULL.
 */
boolean_t
validate_service_name(char *check_this)
{
	char *cchr;

	if (check_this == NULL) {
		return (B_FALSE);
	}

	for (cchr = check_this; *cchr != '\0'; cchr++) {
		/* isalnum can return non-std ASCII when locale is not C */
		if (!((isalnum(*cchr) && isascii(*cchr)) ||
		    (*cchr == '_') || (*cchr == '-'))) {
			return (B_FALSE);
		}
	}
	return (B_TRUE);
}

/*
 * get_a_free_tcp_port
 * This returns the next available tcp port
 *
 * Input:
 * scfutilhandle *handle	- The handle to the aiscf utility library.
 * uint16_t start		- Find a free port starting from this port
 *
 * Returns:
 * uint16_t port	- An unused port
 */
uint16_t
get_a_free_tcp_port(scfutilhandle_t *handle, uint16_t start)
{
	uint16_t port;
	int	sock;
	struct sockaddr_in addr;
	boolean_t found_free_port = B_FALSE;

	port = start;

	sock = socket(AF_INET, SOCK_STREAM, 0);
	if (sock < 0) {
		return (0);
	}

	addr.sin_addr.s_addr = INADDR_ANY;
	addr.sin_family = AF_INET;

	while (!found_free_port) {
		/*
		 * check whether this port is used by a service that is not
		 * active now. If so, find a new port
		 */
		while (check_port_in_use(handle, port)) {
			port++;
		}
		addr.sin_port = htons(port);
		if (bind(sock, (struct sockaddr *)&addr,
		    sizeof (addr)) == 0) {
			found_free_port = B_TRUE;
		} else {
			port++;
		}
	}

	/*
	 * Now close the socket and use the port
	 */
	close(sock);
	return (port);
}

/*
 * check_port_in_use
 * This checks if a port is in use (i.e., is contained in the txt_record
 *	in one of the service properties)
 *
 * Input:
 * scfutilhandle *handle	- The handle to the aiscf utility library.
 * uint16_t port		- port to check
 *
 * Returns:
 * B_TRUE		If the port is in use
 * B_FALSE		If the port is not in use
 */
boolean_t
check_port_in_use(scfutilhandle_t *handle, uint16_t port)
{
	service_data_t	service_data;
	char		*str;
	uint16_t	service_port;
	ai_pg_list_t	*pg = NULL;
	ai_pg_list_t	*pgs = NULL;

	if (ai_get_pgs(handle, &pgs) != AI_SUCCESS)
		return (B_FALSE);

	if (pgs == NULL)
		return (B_FALSE);
	pg = pgs;
	while (pg != NULL && pg->pg_name != NULL) {
		/*
		 * Get the service data from the SMF properies for this
		 * property group.
		 */
		if (get_service_props(handle, pg->pg_name,
		    &service_data) != B_TRUE) {
			(void) fprintf(stderr, MSG_GET_SERVICE_PROPS_FAIL,
			    pg->pg_name);
			ai_free_pg_list(pgs);
			return (B_FALSE);
		}

		/*
		 * Strip the port number out of the text-record property.
		 */
		if (service_data.txt_record != NULL) {
			str = strrchr(service_data.txt_record, ':');
			if (str == NULL) {
				pg = pg->next;
				continue;
			}
			str++;
			/*
			 * If the service port equals the port we're looking
			 * for then it's in use.
			 */
			service_port = strtol(str, (char **)NULL, 10);
			if (port == service_port) {
				ai_free_pg_list(pgs);
				return (B_TRUE);
			}
		}
		pg = pg->next;
	}
	ai_free_pg_list(pgs);
	return (B_FALSE);
}

/*
 * get_service_props
 * Retrieves the properties associated with the service stored in the
 * SMF property group when the service is started.
 *
 * Input:
 * scfutilhandle *handle - The handle to the aiscf utility library.
 * char		*pg_name - The service name we're looking for.
 * service_data_t *data  - The service property data structure used to
 *			   pass back the property values.
 *
 * Output:
 * service_data_t *data	- The values are copied to the structure service_data_t
 *
 * Returns:
 * B_TRUE		If the retrieval is successful
 * B_FALSE		If there is a failure
 */
boolean_t
get_service_props(
	scfutilhandle_t *handle,
	char *pg_name,
	service_data_t *data)
{
	ai_prop_list_t *prop_list = NULL;
	ai_prop_list_t *prop_head = NULL;

	if (handle == NULL || pg_name == NULL || data == NULL)
		return (B_FALSE);

	if (ai_read_all_props_in_pg(handle, pg_name, &prop_head) != 0 ||
	    prop_head == NULL)
		return (B_FALSE);

	/*
	 * The service property group has a number of properties with each
	 * property containing a key-value pair for each of the service
	 * properties as follows:
	 * service_name=<service_name>
	 * image_path=<image_path>
	 * boot_file=<boot_file>
	 * txt_record=<txt_record>
	 * status=on|off
	 */

	prop_list = prop_head;
	while (prop_list != NULL) {
		if (strstr(prop_list->name, SERVICE) != NULL) {
			strlcpy(data->svc_name, prop_list->valstr, DATALEN);
		} else if (strstr(prop_list->name, IMAGE_PATH) != NULL) {
			strlcpy(data->image_path, prop_list->valstr,
			    MAXPATHLEN);
		} else if (strstr(prop_list->name, BOOT_FILE) != NULL) {
			strlcpy(data->boot_file, prop_list->valstr, MAXNAMELEN);
		} else if (strstr(prop_list->name, TXT_RECORD) != NULL) {
			strlcpy(data->txt_record, prop_list->valstr,
			    MAX_TXT_RECORD_LEN);
		} else if (strstr(prop_list->name, SERVICE_STATUS) != NULL) {
			strlcpy(data->status, prop_list->valstr, STATUSLEN);
		}
		prop_list = prop_list->next;
	}
	ai_free_prop_list(prop_head);
	return (B_TRUE);
}

/*
 * set_service_props
 * This function sets the properties associated with the service
 * passed in the service_data_t structure
 *
 * Input:
 * scfutilhandle_t *handle	- The handle to the aiscf utility library.
 * char *pg_name 		- The property group name for this automated
 *				  installer service.
 * service_data_t data		- The values are passed in the structure
 *				  service_data_t
 *
 * Output:
 * None
 *
 * Returns:
 * B_TRUE		If setting the propeties is successful
 * B_FALSE		If there is a failure
 */
boolean_t
set_service_props(scfutilhandle_t *handle, char *pg_name, service_data_t data)
{
	/*
	 * The service property group has a number of properties with each
	 * property containing key-value pair for each of the service
	 * properties as follows:
	 * service_name=<service_name>
	 * image_path=<image_path>
	 * boot_file=<boot_file>
	 * txt_record=<txt_record>
	 * status=on/off
	 */
	if (pg_name == NULL) {
		return (B_FALSE);
	}

	if (data.svc_name != NULL) {
		if (ai_set_property(handle, pg_name, SERVICE,
		    data.svc_name) != AI_SUCCESS) {
			return (B_FALSE);
		}
	}

	if (data.image_path != NULL) {
		if (ai_set_property(handle, pg_name, IMAGE_PATH,
		    data.image_path) != AI_SUCCESS) {
			return (B_FALSE);
		}
	}

	if (data.boot_file != NULL) {
		if (ai_set_property(handle, pg_name, BOOT_FILE,
		    data.boot_file) != AI_SUCCESS) {
			return (B_FALSE);
		}
	}

	if (data.txt_record != NULL) {
		if (ai_set_property(handle, pg_name, TXT_RECORD,
		    data.txt_record) != AI_SUCCESS) {
			return (B_FALSE);
		}
	}

	if (data.status != NULL) {
		if (ai_set_property(handle, pg_name, SERVICE_STATUS,
		    data.status) != AI_SUCCESS) {
			return (B_FALSE);
		}
	}

	return (B_TRUE);
}

/*
 * get_service_data
 * Obtain the information about the service passed as the first parameter
 *
 * Input:
 * scfutilhandle_t *handle	- The handle to the aiscf utility library.
 * char *service		- Name of the service
 * service_data_t data		- The values are passed in the structure
 *				  service_data_t
 *
 * Output:
 * scfutilhandle *handle - The handle to the aiscf utility library.
 * service_data_t *data	 - The info about the service is copied to the
 *			   structure service_data_t
 * Return:
 * B_TRUE		- If the service is found
 * B_FALSE		- If the service cannot be found or an error occurs
 */
boolean_t
get_service_data(scfutilhandle_t *handle, char *service, service_data_t *data)
{
	char		*ai_name = NULL;

	if (handle == NULL || service == NULL || data == NULL) {
			return (B_FALSE);
	}

	ai_name = ai_make_pg_name(service);
	if (ai_name == NULL) {
		(void) fprintf(stderr, MSG_GET_PG_NAME_FAILED,
		    service);
		return (B_FALSE);
	}

	if (get_service_props(handle, ai_name, data) != B_TRUE) {
		(void) fprintf(stderr, MSG_GET_SERVICE_PROPS_FAIL,
		    ai_name);
		free(ai_name);
		return (B_FALSE);
	}
	free(ai_name);
	return (B_TRUE);
}


/*
 * remove_install_service
 * Remove the smf property group associated with the install service.
 *
 * Input:
 * scfutilhandle_t *handle	- The handle to the aiscf utility library.
 * char *service		- Name of the service
 *
 * Return:
 * B_TRUE		- If the smf property group is removed
 * B_FALSE		- If there is a problem with the service name
 *			  or the smf property group couldn't be removed.
 */
boolean_t
remove_install_service(scfutilhandle_t *handle, char *service)
{
	char 	*ai_name = NULL;

	if (service == NULL) {
		return (B_FALSE);
	}

	ai_name = ai_make_pg_name(service);
	if (ai_name == NULL) {
		(void) fprintf(stderr, MSG_GET_PG_NAME_FAILED,
		    service);
		return (B_FALSE);
	}

	if (ai_delete_install_service(handle, ai_name) != 0) {
		free(ai_name);
		return (B_FALSE);
	}
	free(ai_name);
	return (B_TRUE);
}


/*
 * save_service_data
 *
 * The passed in information about a service is saved to a smf property group.
 *
 * Input:
 * scfutilhandle_t *handle	- The handle to the aiscf utility library.
 * service_data_t data		- Service data in structure service_data_t
 *
 * Return:
 * B_TRUE		- If the property is saved
 * B_FALSE		- If there is a problem saving the property
 */
boolean_t
save_service_data(scfutilhandle_t *handle, service_data_t data)
{
	char	*ai_name;

	ai_name = ai_make_pg_name(data.svc_name);
	if (ai_name == NULL) {
		(void) fprintf(stderr, MSG_GET_PG_NAME_FAILED,
		    data.svc_name);
		return (B_FALSE);
	}

	if (set_service_props(handle, ai_name, data) != B_TRUE) {
		(void) fprintf(stderr, MSG_SET_SERVICE_PROPS_FAIL,
		    ai_name);
		free(ai_name);
		return (B_FALSE);
	}

	free(ai_name);
	return (B_TRUE);
}


/*
 * service_exists
 *
 * Checks if an install service exists.
 *
 * Input:
 * scfutilhandle_t *handle	- The handle to the aiscf utility library.
 * char *service_name 		- Service name of install service to check
 *
 * Return:
 * B_TRUE	- If the install service exists
 * B_FALSE	- If the install service does not exist
 */
boolean_t
service_exists(scfutilhandle_t *handle, char *service_name)
{
	char	*ai_name;

	if (service_name == NULL || handle == NULL) {
		return (B_FALSE);
	}

	ai_name = ai_make_pg_name(service_name);
	if (ai_name == NULL) {
		(void) fprintf(stderr, MSG_GET_PG_NAME_FAILED,
		    service_name);
		return (B_FALSE);
	}

	if (ai_get_instance(handle, "default") != AI_SUCCESS) {
		(void) fprintf(stderr, MSG_GET_SMF_INSTANCE_FAILED);
		free(ai_name);
		return (B_FALSE);
	}

	if (ai_get_pg(handle, ai_name) != AI_SUCCESS) {
		free(ai_name);
		return (B_FALSE);
	}

	free(ai_name);
	return (B_TRUE);
}


/*
 * installadm_system()
 *
 * Function to execute shell commands in a thread-safe manner
 * Parameters:
 *	cmd - the command to execute
 * Return:
 *	return code from command
 *	if popen() fails, -1
 * Status:
 *	private
 */
int
installadm_system(char *cmd)
{
	FILE	*p;

	if ((p = popen(cmd, "w")) == NULL)
		return (-1);

	return (pclose(p));
}
