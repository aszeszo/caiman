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
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <strings.h>
#include <unistd.h>
#include <locale.h>
#include <sys/param.h>
#include <sys/types.h>

#include "auto_install.h"

PyObject *manifest_serv_obj = NULL;

/*
 * Validate the manifest syntactically as well as
 * semantically.
 *
 * As part of the validation process, fill in the
 * defaults for the attributes that aren't specified
 * and import the manifest into an in-memory tree
 * that can subsequently be queried for the various
 * attributes. A handle to the in-memory tree is stored
 * as a ManifestServ object pointed to by manifest_serv_obj.
 *
 * Returns
 * 	AUTO_VALID_MANIFEST if it's a valid manifest
 * 	AUTO_INVALID_MANIFEST if it's an invalid manifest
 */
int
ai_validate_and_setup_manifest(char *filename)
{
	/*
	 * If the manifest_serv_obj is set it means that
	 * the manifest has already been validated and
	 * a server object created for it
	 */
	if (manifest_serv_obj != NULL)
		return (AUTO_VALID_MANIFEST);

	manifest_serv_obj = ai_create_manifestserv(filename);
	if (manifest_serv_obj != NULL)
		return (AUTO_VALID_MANIFEST);

	auto_debug_print(AUTO_DBGLVL_INFO, "error validating the manifest\n");
	return (AUTO_INVALID_MANIFEST);
}

void
ai_teardown_manifest_state()
{
	if (manifest_serv_obj != NULL)
		(void) ai_destroy_manifestserv(manifest_serv_obj);
}

char **
ai_get_manifest_values(char *path, int *len)
{
	if (manifest_serv_obj == NULL) {
		auto_debug_print(AUTO_DBGLVL_INFO, "manifestserv must be "
		    "initialized before values can be retrieved\n");
		return (NULL);
	}

	return (ai_lookup_manifest_values(manifest_serv_obj, path, len));
}

static char **
ai_get_manifest_partition_action(int *len)
{
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_partitioning/partition_action", len);

	if (*len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_partition_number()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_partitioning/partition_number", &len);

	if (len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_partition_start_sector()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_partitioning/partition_start_sector", &len);

	if (len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_partition_size()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_partitioning/partition_size", &len);

	if (len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_partition_type()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_partitioning/partition_type", &len);

	if (len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_slice_action(int *len)
{
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_vtoc_slices/slice_action", len);

	if (*len > 0)
		return (value);
	return (NULL);
}

static char **
ai_get_manifest_slice_number()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_vtoc_slices/slice_number", &len);

	if (len > 0)
		return (value);

	return (NULL);
}

static char **
ai_get_manifest_slice_size()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_device_vtoc_slices/slice_size", &len);

	if (len > 0)
		return (value);
	return (NULL);
}

/*
 * get_manifest_element_value() - return value given xml element
 */
static char *
get_manifest_element_value(char *element)
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(element, &len);

	if (len > 0)
		return (*value);
	return (NULL);
}

/*
 * get_manifest_element_array() - return list of values given xml element
 */
static char **
get_manifest_element_array(char *element)
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(element, &len);

	if (len > 0)
		return (value);
	return (NULL);
}

/*
 * Retrieve the target disk information
 */
void
ai_get_manifest_disk_info(auto_disk_info *adi)
{
	char *p;

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_name");
	if (p != NULL)
		(void) strncpy(adi->diskname, p, sizeof (adi->diskname));

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_type");
	if (p != NULL)
		(void) strncpy(adi->disktype, p, sizeof (adi->disktype));

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_vendor");
	if (p != NULL)
		(void) strncpy(adi->diskvendor, p, sizeof (adi->diskvendor));

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_size");
	if (p != NULL)
		adi->disksize = (uint64_t)strtoull(p, NULL, 0);

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_use_solaris_partition");
	if (p != NULL)
		(void) strncpy(adi->diskusepart, p, sizeof (adi->diskusepart));

	p = get_manifest_element_value(
	    "target_device_overwrite_root_zfs_pool");
	if (p != NULL)
		(void) strncpy(adi->diskoverwrite_rpool, p,
		    sizeof (adi->diskoverwrite_rpool));

	p = get_manifest_element_value(
	    "ai_manifest/ai_target_device/target_device_install_slice_number");
	if (p != NULL) {
		int install_slice_number;

		if (sscanf(p, "%d", &install_slice_number) > 0)
			adi->install_slice_number =
			    (uint8_t)install_slice_number;
	}
}

/*
 * Retrieve the information about the partitions
 * that need to be configured
 *
 * This function allocates memory for an array
 * of auto_partition_info. The caller MUST free this memory
 */
auto_partition_info *
ai_get_manifest_partition_info()
{
	auto_partition_info *api;
	int i, len;
	char **p;

	p = ai_get_manifest_partition_action(&len);

	if (p != NULL) {
		/* len+1 -- '1' for the NULL entry */
		api = calloc(sizeof (auto_partition_info), len + 1);

		for (i = 0; i < len; i++)
			(void) strncpy((api + i)->partition_action,
			    p[i], sizeof ((api + i)->partition_action));
	} else
		return (NULL);

	p = ai_get_manifest_partition_number();
	if (p != NULL) {
		for (i = 0; i < len; i++)
			(api + i)->partition_number = atoi(p[i]);
	}

	p = ai_get_manifest_partition_start_sector();
	if (p != NULL) {
		for (i = 0; i < len; i++)
			(api + i)->partition_start_sector =
			    (uint64_t)strtoull(p[i], NULL, 0);
	}

	p = ai_get_manifest_partition_size();
	if (p != NULL) {
		for (i = 0; i < len; i++)
			(api + i)->partition_size =
			    (uint64_t)strtoull(p[i], NULL, 0);
	}

	p = ai_get_manifest_partition_type();
	if (p != NULL) {
		for (i = 0; i < len; i++)
			(api + i)->partition_type = atoi(p[i]);
	}

	p = get_manifest_element_array(
	    "ai_manifest/ai_device_partitioning/partition_size_units");
	/* partition size units can be sectors, GB, TB, or MB (default) */
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			if (p[i] == NULL) { /* default to MB */
				(api + i)->partition_size_units =
				    AI_SIZE_UNITS_MEGABYTES;
				continue;
			}
			switch (p[i][0]) {
				case 's':
				case 'S':
					(api + i)->partition_size_units =
					    AI_SIZE_UNITS_SECTORS;
					break;
				case 'g':
				case 'G':
					(api + i)->partition_size_units =
					    AI_SIZE_UNITS_GIGABYTES;
					break;
				case 't':
				case 'T':
					(api + i)->partition_size_units =
					    AI_SIZE_UNITS_TERABYTES;
					break;
				case 'm':
				case 'M':
				default:
					(api + i)->partition_size_units =
					    AI_SIZE_UNITS_MEGABYTES;
					break;
			}
		}
	}

	return (api);
}

/*
 * Retrieve the vtoc slice information
 *
 * This function allocates memory for an array
 * of auto_slice_info. The caller MUST free this memory
 */
auto_slice_info *
ai_get_manifest_slice_info()
{
	auto_slice_info *asi;
	int i, len = 0;
	char **p;

	p = ai_get_manifest_slice_action(&len);

	if (p == NULL)
		return (NULL);

	/* len+1 -- '1' for end of array marker */
	asi = calloc(sizeof (auto_slice_info), len + 1);

	for (i = 0; i < len; i++) {
		(void) strncpy((asi + i)->slice_action, p[i],
		    sizeof ((asi + i)->slice_action));
	}

	p = ai_get_manifest_slice_number();
	if (p != NULL)
		for (i = 0; i < len; i++)
			(asi + i)->slice_number = atoi(p[i]);

	p = ai_get_manifest_slice_size();
	if (p != NULL)
		for (i = 0; i < len; i++)
			(asi + i)->slice_size =
			    (uint64_t)strtoull(p[i], NULL, 0);

	p = get_manifest_element_array(
	    "ai_manifest/ai_device_vtoc_slices/slice_size_units");
	/* slice size units can be sectors, GB, TB, or MB (default) */
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			if (p[i] == NULL) { /* default to MB */
				(asi + i)->slice_size_units =
				    AI_SIZE_UNITS_MEGABYTES;
				continue;
			}
			switch (p[i][0]) {
				case 's':
				case 'S':
					(asi + i)->slice_size_units =
					    AI_SIZE_UNITS_SECTORS;
					break;
				case 'g':
				case 'G':
					(asi + i)->slice_size_units =
					    AI_SIZE_UNITS_GIGABYTES;
					break;
				case 't':
				case 'T':
					(asi + i)->slice_size_units =
					    AI_SIZE_UNITS_TERABYTES;
					break;
				case 'm':
				case 'M':
				default:
					(asi + i)->slice_size_units =
					    AI_SIZE_UNITS_MEGABYTES;
					break;
			}
		}
	}
	return (asi);
}

/*
 * Retrieve the IPS repo information
 */
char *
ai_get_manifest_ipsrepo_url()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_pkg_repo_default_authority/main/url", &len);

	if (len > 0)
		return (value[0]);
	return (NULL);
}

/*
 * Retrieve the IPS repo authority name
 */
char *
ai_get_manifest_ipsrepo_authname()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_pkg_repo_default_authority/main/authname", &len);

	if (len > 0)
		return (value[0]);
	return (NULL);
}

/*
 * Retrieve the proxy to use to access the IPS repo.
 */
char *
ai_get_manifest_http_proxy()
{
	int len = 0;
	char **value;

	value = ai_get_manifest_values(
	    "ai_manifest/ai_http_proxy/url", &len);

	if (len > 0)
		return (value[0]);
	return (NULL);
}

/*
 * Retrieve the list of packages to be installed
 */
char **
ai_get_manifest_packages(int *len)
{
	char **package_list;

	package_list = ai_get_manifest_values(
	    "ai_manifest/ai_packages/package_name", len);

	if (*len > 0)
		return (package_list);
	return (NULL);
}

static int
parse_property(char *str, char *keyword, char *value)
{
	char	*token;

	if (str == NULL) {
		return (NULL);
	}

	if (*str == '#') {
		return (NULL);
	}

	*keyword = '\0';
	token = strtok(str, " ");

	while ((token = strtok(NULL, " ")) != NULL) {
		if (strstr(token, AUTO_PROPERTY_USERNAME) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_USERNAME, KEYWORD_SIZE);
			break;
		} else if (strstr(token, AUTO_PROPERTY_USERPASS) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_USERPASS, KEYWORD_SIZE);
			break;
		} else if (strstr(token, AUTO_PROPERTY_USERDESC) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_USERDESC, KEYWORD_SIZE);
			break;
		} else if (strstr(token, AUTO_PROPERTY_ROOTPASS) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_ROOTPASS, KEYWORD_SIZE);
			break;
		} else if (strstr(token, AUTO_PROPERTY_TIMEZONE) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_TIMEZONE, KEYWORD_SIZE);
			break;
		}
	}

	if (*keyword == '\0') {
		return (AUTO_INSTALL_FAILURE);
	}
	while ((token = strtok(NULL, " ")) != NULL) {
		char	*ptr, *ptr1, *ptr2;

		ptr = strstr(token, KEYWORD_VALUE);
		if (ptr == NULL) {
			continue;
		}

		ptr1 = strchr(ptr, '\'');
		if (ptr1 == NULL) {
			ptr1 = strchr(ptr, '\"');
			if (ptr1 == NULL)
				return (AUTO_INSTALL_FAILURE);
		}
		ptr2 = strrchr(ptr, '\"');
		if (ptr2 == NULL) {
			ptr2 = strchr(ptr, '\"');
			if (ptr2 == NULL)
				return (AUTO_INSTALL_FAILURE);
		}
		ptr1++;
		*ptr2 = '\0';
		strlcpy(value, ptr1, VALUE_SIZE);
		return (AUTO_INSTALL_SUCCESS);
	}
	return (AUTO_INSTALL_FAILURE);
}

/*
 * Parse the system configuration (SC) manifest
 * and return the information in the passed in
 * auto_sc_params
 */
int
auto_parse_sc_manifest(char *profile_file, auto_sc_params *sp)
{
	FILE	*profile_fp;
	char	line[BUFSIZ];
	char	keyword[KEYWORD_SIZE];
	char	value[VALUE_SIZE];
	int	ret;

	profile_fp = fopen(profile_file, "r");
	if (profile_fp == NULL) {
		auto_log_print(gettext("Profile %s missing\n"), profile_file);
		return (AUTO_INSTALL_FAILURE);
	}

	while (fgets(line, sizeof (line), profile_fp) != NULL) {
		if (strstr(line, SC_PROPVAL_MARKER) != NULL) {
			ret = parse_property(line, keyword, value);
			if (ret == AUTO_INSTALL_SUCCESS) {
				if (strcmp(keyword, AUTO_PROPERTY_USERNAME)
				    == 0) {
					sp->username = strdup(value);
				}
				if (strcmp(keyword, AUTO_PROPERTY_USERDESC)
				    == 0) {
					sp->userdesc = strdup(value);
				}
				if (strcmp(keyword, AUTO_PROPERTY_USERPASS)
				    == 0) {
					sp->userpass = strdup(value);
				}
				if (strcmp(keyword, AUTO_PROPERTY_ROOTPASS)
				    == 0) {
					sp->rootpass = strdup(value);
				}
				if (strcmp(keyword, AUTO_PROPERTY_TIMEZONE)
				    == 0) {
					sp->timezone = strdup(value);
				}
			} else {
				auto_log_print(gettext("Invalid property "
				    "%s specified in the SC manifest. "
				    "Ignoring\n"), value);
			}
		}
	}
	fclose(profile_fp);
	return (AUTO_INSTALL_SUCCESS);
}
