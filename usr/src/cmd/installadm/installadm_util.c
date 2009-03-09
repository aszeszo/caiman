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
#include <dirent.h>

#include "installadm.h"

/*
 * Installadm utility functions
 */
boolean_t read_service_data_file(char *, service_data_t *);
boolean_t write_service_data_file(char *, service_data_t);
boolean_t check_port_in_use(uint16_t);


/*
 * get_a_free_tcp_port
 * This returns the next available tcp port
 *
 * Input:
 * uint16_t start	- Find a free port starting from this port
 *
 * Returns:
 * uint16_t port	- An unused port
 */
uint16_t
get_a_free_tcp_port(uint16_t start)
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
		while (check_port_in_use(port)) {
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
 *	in one of the service data files)
 *
 * Input:
 * uint16_t port	- port to check
 *
 * Returns:
 * B_TRUE		If the port is in use
 * B_FALSE		If the port is not in use
 */
boolean_t
check_port_in_use(uint16_t port)
{
	struct dirent	*dp;
	DIR		*dirp;
	service_data_t	service_data;
	char		*str;
	char		path[MAXPATHLEN];
	uint16_t	service_port;

	/*
	 * opendir /var/installadm/services
	 * read-in the service_name
	 * copy it to the service_list
	 */
	dirp = opendir(AI_SERVICES_DIR);
	if (dirp == NULL) {
		return (B_FALSE);
	}

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0) {
			continue;
		}
		(void) snprintf(path, sizeof (path), "%s/%s",
		    AI_SERVICES_DIR, dp->d_name);

		if (read_service_data_file(path, &service_data) != B_TRUE) {
			(void) fprintf(stderr, MSG_READ_SERVICE_DATA_FILE_FAIL,
			    path);
			return (B_FALSE);
		}

		if (service_data.txt_record != NULL) {
			str = strrchr(service_data.txt_record, ':');
			if (str == NULL) {
				continue;
			}
			str++;
			service_port = strtol(str, (char **)NULL, 10);
			if (port == service_port) {
				return (B_TRUE);
			}
		}
	}
	return (B_FALSE);
}

/*
 * normalize_service_name
 * This function converts spaces and . in the service name to '_'
 * The '.' and space in the service causes problems when creating file names
 * using the service.
 *
 * Input:
 * char	*service 	- The service name to normalize
 *
 * Returns:
 * char	*		- String containing the normalized service name
 *			  or NULL
 *			  Caller needs to free returned string.
 */
char *
normalize_service_name(char *service)
{
	char *ptr;
	char *normalized_service;

	if (service == NULL) {
		return (NULL);
	}

	if ((normalized_service = strdup(service)) == NULL) {
		return (NULL);
	}

	for (ptr = normalized_service; *ptr != '\0'; ptr++) {
		if (!isalnum(*ptr) && (*ptr == ' ' || *ptr == '.')) {
			*ptr = '_';
		}
	}
	return (normalized_service);
}


/*
 * read_service_data_file
 * Reads the properties associated with the service stored in the
 * file when the service is started.
 *
 * Input:
 * char	*path 	- The path name of the service's data file
 *
 * Output:
 * service_data_t *data	- The values are copied to the structure service_data_t
 *
 * Returns:
 * B_TRUE		If the read is successful
 * B_FALSE		If there is a failure
 */
boolean_t
read_service_data_file(char *path, service_data_t *data)
{
	char	*ptr;
	FILE	*fp;
	char	buf[MAXPATHLEN];

	if (path == NULL || data == NULL) {
		return (B_FALSE);
	}

	fp = fopen(path, "r");
	if (fp == NULL) {
		(void) fprintf(stderr, MSG_OPEN_SERVICE_DATA_FILE_FAIL, path);
		return (B_FALSE);
	}

	/*
	 * The service data file has a number of lines with each line
	 * containing a key-value pair for each of the service properties
	 * as follows:
	 * service_name=<service_name>
	 * image_path=<image_path>
	 * boot_file=<boot_file>
	 * txt_record=<txt_record>
	 * status=on|off
	 */
	while (fgets(buf, sizeof (buf), fp) != NULL) {
		/*
		 * strip off '\n'
		 */
		ptr = strchr(buf, '\n');
		if (ptr != NULL) {
			*ptr = '\0';
		}
		if (strstr(buf, SERVICE) != NULL) {
			ptr = strchr(buf, '=');
			if (ptr != NULL) {
				strlcpy(data->svc_name, ptr+1, DATALEN);
			}
		} else if (strstr(buf, IMAGE_PATH) != NULL) {
			ptr = strchr(buf, '=');
			if (ptr != NULL) {
				strlcpy(data->image_path, ptr+1, MAXPATHLEN);
			}
		} else if (strstr(buf, BOOT_FILE) != NULL) {
			ptr = strchr(buf, '=');
			if (ptr != NULL) {
				strlcpy(data->boot_file, ptr+1, MAXNAMELEN);
			}
		} else if (strstr(buf, TXT_RECORD) != NULL) {
			ptr = strchr(buf, '=');
			if (ptr != NULL) {
				strlcpy(data->txt_record,
				    ptr+1, MAX_TXT_RECORD_LEN);
			}
		} else if (strstr(buf, SERVICE_STATUS) != NULL) {
			ptr = strchr(buf, '=');
			if (ptr != NULL) {
				strlcpy(data->status, ptr+1, STATUSLEN);
			}
		}
	}
	fclose(fp);
	return (B_TRUE);
}


/*
 * write_service_data_file
 * This function writes the properties associated with the service
 * passed in the service_data_t structure to the service_data file
 *
 * Input:
 * char	*path 	- The path name of the service_data file
 * service_data_t data	- The values are passed in the structure service_data_t
 *
 * Output:
 * None
 *
 * Returns:
 * B_TRUE		If the write is successful
 * B_FALSE		If there is a failure
 */
boolean_t
write_service_data_file(char *path, service_data_t data)
{
	char	*value;
	FILE	*fp;
	char	buf[MAXPATHLEN];

	if (path == NULL) {
		return (B_FALSE);
	}

	fp = fopen(path, "w");
	if (fp == NULL) {
		(void) fprintf(stderr, MSG_OPEN_SERVICE_DATA_FILE_FAIL, path);
		return (B_FALSE);
	}

	/*
	 * The service data file has a number of lines with each line
	 * containing key-value pair for each of the service properties
	 * as follows:
	 * service_name=<service_name>
	 * image_path=<image_path>
	 * boot_file=<boot_file>
	 * txt_record=<txt_record>
	 * status=on/off
	 */
	if (data.svc_name != NULL) {
		(void) snprintf(buf, sizeof (buf), "%s=%s\n",
		    SERVICE, data.svc_name);
		if (fputs(buf, fp) == EOF) {
			return (B_FALSE);
		}
	}

	if (data.image_path != NULL) {
		(void) snprintf(buf, sizeof (buf), "%s=%s\n",
		    IMAGE_PATH, data.image_path);
		if (fputs(buf, fp) == EOF) {
			return (B_FALSE);
		}
	}

	if (data.boot_file != NULL) {
		(void) snprintf(buf, sizeof (buf), "%s=%s\n",
		    BOOT_FILE, data.boot_file);
		if (fputs(buf, fp) == EOF) {
			return (B_FALSE);
		}
	}

	if (data.txt_record != NULL) {
		(void) snprintf(buf, sizeof (buf), "%s=%s\n",
		    TXT_RECORD, data.txt_record);
		if (fputs(buf, fp) == EOF) {
			return (B_FALSE);
		}
	}

	if (data.status != NULL) {
		(void) snprintf(buf, sizeof (buf), "%s=%s\n",
		    SERVICE_STATUS, data.status);
		if (fputs(buf, fp) == EOF) {
			return (B_FALSE);
		}
	}

	fclose(fp);
	return (B_TRUE);
}


/*
 * get_service_data
 * Obtain the information about the service passed as the first parameter
 *
 * Input:
 * char *service	- Name of the service
 *
 * Output:
 * service_data_t *data - The info about the service is copied to the
 *				structure service_data_t
 * Return:
 * B_TRUE		- If the service is found
 * B_FALSE		- If the service cannot be found or an error occurs
 */
boolean_t
get_service_data(char *service, service_data_t *data)
{
	int		size;
	char		path[MAXPATHLEN];
	char		*norm_service_name;

	if (service == NULL || data == NULL) {
			return (B_FALSE);
	}

	norm_service_name = normalize_service_name(service);
	if (norm_service_name == NULL) {
		(void) fprintf(stderr, MSG_UNABLE_NORMALIZE_SVC_NAME,
		    service);
		return (B_FALSE);
	}
	(void) snprintf(path, sizeof (path), "%s/%s",
	    AI_SERVICES_DIR, norm_service_name);
	(void) free(norm_service_name);

	if (read_service_data_file(path, data) != B_TRUE) {
		(void) fprintf(stderr, MSG_READ_SERVICE_DATA_FILE_FAIL,
		    path);
		return (B_FALSE);
	}
	return (B_TRUE);
}


/*
 * remove_service_data
 * The information about a service is removed by deleting its associated
 * data file.
 *
 * Input:
 * char *service	- Name of the service
 *
 * Return:
 * B_TRUE		- If the data file is removed
 * B_FALSE		- If there is a problem with the service name
 */
boolean_t
remove_service_data(char *service)
{
	char	path[MAXPATHLEN];
	char	*norm_service_name;

	if (service == NULL) {
		return (B_FALSE);
	}

	norm_service_name = normalize_service_name(service);
	if (norm_service_name == NULL) {
		(void) fprintf(stderr, MSG_UNABLE_NORMALIZE_SVC_NAME,
		    service);
		return (B_FALSE);
	}
	(void) snprintf(path, sizeof (path), "%s/%s",
	    AI_SERVICES_DIR, norm_service_name);
	(void) free(norm_service_name);

	/*
	 * If the file doesn't exist, there is nothing to remove
	 */
	if (access(path, F_OK) != 0) {
		return (B_TRUE);
	}

	unlink(path);
	return (B_TRUE);
}


/*
 * save_service_data
 *
 * The passed in information about a service is saved to a data file.
 * If the file already exists, it is removed and recreated.
 *
 * Input:
 * service_data_t data	- Service data in structure service_data_t
 *
 * Return:
 * B_TRUE		- If the data file is saved
 * B_FALSE		- If there is a problem saving the data file
 */
boolean_t
save_service_data(service_data_t data)
{
	char	path[MAXPATHLEN];
	char	file[DATALEN];
	char	*norm_service_name;

	norm_service_name = normalize_service_name(data.svc_name);
	if (norm_service_name == NULL) {
		(void) fprintf(stderr, MSG_UNABLE_NORMALIZE_SVC_NAME,
		    data.svc_name);
		return (B_FALSE);
	}
	(void) snprintf(path, sizeof (path), "%s/%s",
	    AI_SERVICES_DIR, norm_service_name);
	(void) free(norm_service_name);
	if (access(path, F_OK) == 0) {
		if (remove_service_data(data.svc_name) != B_TRUE) {
			(void) fprintf(stderr,
			    MSG_REMOVE_SERVICE_DATA_FILE_FAIL,
			    data.svc_name);
			return (B_FALSE);
		}
	}

	if (write_service_data_file(path, data) != B_TRUE) {
		(void) fprintf(stderr, MSG_WRITE_SERVICE_DATA_FILE_FAIL,
		    path);
	}
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
