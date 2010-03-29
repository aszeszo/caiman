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

#include <fcntl.h>
#include <libintl.h>
#include <stdio.h>
#include <errno.h>
#include <stdlib.h>
#include <strings.h>
#include <unistd.h>
#include <locale.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/wait.h>

#include "auto_install.h"

PyObject *manifest_serv_obj = NULL;

/*
 * Dump errors found during syntactic validation of AI manifest -
 * capture stdout and stderr of xmllint(1M) called with following parameters:
 *
 * /usr/bin/xmllint --noout --relaxng <schema> <manifest> 2>&1
 *
 * Returns
 * 	-1  - failed to dump syntactic errors
 *	>=0 - exit code from xmllint(1M)
 */
static int
dump_ai_manifest_errors(char *manifest, char *schema)
{
	FILE	*p;
	char	*cmd;
	size_t	cmd_ln;
	char	buf[MAXPATHLEN];
	int	ret;

	/* calculate size of command string - account for string terminator */
	cmd_ln = sizeof ("/usr/bin/xmllint --noout --relaxng ") +
	    strlen(manifest) + sizeof (" ") + strlen(schema) +
	    sizeof (" 2>&1") + 1;

	cmd = malloc(cmd_ln);

	if (cmd == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR, "malloc() failed\n");

		return (-1);
	}

	(void) snprintf(cmd, cmd_ln,
	    "/usr/bin/xmllint --noout --relaxng %s %s 2>&1", schema, manifest);

	auto_debug_print(AUTO_DBGLVL_INFO, "exec cmd: %s\n", cmd);

	if ((p = popen(cmd, "r")) == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Could not execute following command: %s\n", cmd);

		free(cmd);
		return (-1);
	}

	while (fgets(buf, sizeof (buf), p) != NULL)
		auto_debug_print(AUTO_DBGLVL_ERR, " %s", buf);

	ret = WEXITSTATUS(pclose(p));

	/*
	 * The validation is expected to fail - command returns
	 * with non-zero exit code - log the exit code.
	 *
	 */

	auto_debug_print(AUTO_DBGLVL_ERR,
	    "xmllint(1M) returned with exit code %d\n", ret);

	free(cmd);
	return (ret);
}

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

	/*
	 * if the validation process failed, capture output of syntactic
	 * validation in log file
	 */
	auto_log_print(gettext("Syntactic validation of the manifest failed "
	    "with following errors\n"));

	if (dump_ai_manifest_errors(filename, AI_MANIFEST_SCHEMA) == -1) {
		auto_log_print(gettext("Failed to obtain result of syntactic "
		    "validation\n"));
	}

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

	value = ai_get_manifest_values(AIM_PARTITION_ACTION, len);

	if (*len > 0)
		return (value);
	return (NULL);
}

/*
 * ai_get_manifest_element_value() - return value given xml element
 */
char *
ai_get_manifest_element_value(char *element)
{
	int len = 0;
	char **value;
	char *evalue;

	value = ai_get_manifest_values(element, &len);

	/*
	 * Return the value and free the pointer
	 */
	if (len > 0) {
		evalue = *value;
		free(value);
		return (evalue);
	}
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
 *
 * If illegal values, return AUTO_INSTALL_FAILURE
 * else return AUTO_INSTALL_SUCCESS
 */
int
ai_get_manifest_disk_info(auto_disk_info *adi)
{
	char *p;

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_NAME);
	if (p != NULL)
		(void) strncpy(adi->diskname, p, sizeof (adi->diskname));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_TYPE);
	if (p != NULL)
		(void) strncpy(adi->disktype, p, sizeof (adi->disktype));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_VENDOR);
	if (p != NULL)
		(void) strncpy(adi->diskvendor, p, sizeof (adi->diskvendor));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_SELECT_VOLUME_NAME);
	if (p != NULL)
		(void) strlcpy(adi->diskvolname, p, sizeof (adi->diskvolname));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_SELECT_DEVICE_ID);
	if (p != NULL)
		(void) strlcpy(adi->diskdevid, p, sizeof (adi->diskdevid));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_SELECT_DEVICE_PATH);
	if (p != NULL)
		(void) strlcpy(adi->diskdevicepath, p,
		    sizeof (adi->diskdevicepath));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_SIZE);
	if (p != NULL)
		adi->disksize = (uint64_t)strtoull(p, NULL, 0);

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_USE_SOLARIS_PARTITION);
	if (p != NULL) {
#ifdef	__sparc
		auto_log_print("Warning: ignoring manifest element "
		    "target_device_use_solaris_partition on SPARC\n");
#else
		(void) strncpy(adi->diskusepart, p, sizeof (adi->diskusepart));
#endif
	}

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_OVERWRITE_ROOT_ZFS_POOL);
	if (p != NULL)
		(void) strncpy(adi->diskoverwrite_rpool, p,
		    sizeof (adi->diskoverwrite_rpool));

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_INSTALL_SLICE_NUMBER);
	if (p != NULL) {
		int install_slice_number;

		if (sscanf(p, "%d", &install_slice_number) > 0)
			adi->install_slice_number =
			    (uint8_t)install_slice_number;
	}

	/*
	 * iSCSI target information
	 */
	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_ISCSI_TARGET_NAME);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.name, p,
		    sizeof (adi->diskiscsi.name));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_ISCSI_TARGET_IP);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.ip, p,
		    sizeof (adi->diskiscsi.ip));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_ISCSI_TARGET_LUN);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.lun, p,
		    sizeof (adi->diskiscsi.lun));

	p = ai_get_manifest_element_value(AIM_TARGET_DEVICE_ISCSI_TARGET_PORT);
	if (p != NULL)
		adi->diskiscsi.port = strtoll(p, NULL, 0);

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_ISCSI_TARGET_CHAP_NAME);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.chapname, p,
		    sizeof (adi->diskiscsi.chapname));

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_ISCSI_TARGET_CHAP_SECRET);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.chapsecret, p,
		    sizeof (adi->diskiscsi.chapsecret));

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_ISCSI_TARGET_INITIATOR);
	if (p != NULL)
		(void) strncpy(adi->diskiscsi.initiator, p,
		    sizeof (adi->diskiscsi.initiator));

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_ISCSI_PARAMETER_SOURCE);
	if (p == NULL)
		adi->diskiscsi.parm_src = AI_ISCSI_PARM_SRC_MANIFEST;
	else {
		if (strcasecmp(p, "manifest") == 0)
			adi->diskiscsi.parm_src = AI_ISCSI_PARM_SRC_MANIFEST;
		else if (strcasecmp(p, "dhcp") == 0)
			adi->diskiscsi.parm_src = AI_ISCSI_PARM_SRC_DHCP;
		else {
			auto_log_print("Invalid iSCSI parameter source "
			    "specified. Tag="
			    AIM_TARGET_DEVICE_ISCSI_PARAMETER_SOURCE "\n");
			auto_log_print("Value=%s\n", p);
			auto_log_print("Possible values: DHCP, MANIFEST "
			    "(default)\n");
			return (AUTO_INSTALL_FAILURE);
		}
	}

	return (AUTO_INSTALL_SUCCESS);
}

/*
 * Retrieve the device swap request information
 *
 * If illegal values, return AUTO_INSTALL_FAILURE
 * else return AUTO_INSTALL_SUCCESS.
 * Existence of these manifest items is optional.
 */
int
ai_get_manifest_swap_device_info(auto_swap_device_info *adsi)
{
	char *p;

	adsi->swap_size = -1;
	p = ai_get_manifest_element_value(AIM_SWAP_SIZE);
	if (p != NULL) {
		if (sscanf(p, "%lu", &adsi->swap_size) > 0) {
			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Swap Size Requested=%lu\n",
			    adsi->swap_size);
		} else {
			adsi->swap_size = 0;
			auto_log_print("Invalid swap size "
			    "specified. Tag="
			    AIM_SWAP_SIZE "\n");
			auto_log_print("Value=%s\n", p);
			return (AUTO_INSTALL_FAILURE);
		}
	}

	return (AUTO_INSTALL_SUCCESS);
}

/*
 * Retrieve the device dump request information
 *
 * If illegal values, return AUTO_INSTALL_FAILURE
 * else return AUTO_INSTALL_SUCCESS.
 * Existence of these manifest items is optional.
 */
int
ai_get_manifest_dump_device_info(auto_dump_device_info *addi)
{
	char *p;

	addi->dump_size = -1;
	p = ai_get_manifest_element_value(AIM_DUMP_SIZE);
	if (p != NULL) {
		if (sscanf(p, "%lu", &addi->dump_size) > 0) {
			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Dump Size Requested=%lu\n",
			    addi->dump_size);
		} else {
			addi->dump_size = 0;
			auto_log_print("Invalid dump device size "
			    "specified. Tag="
			    AIM_DUMP_SIZE "\n");
			auto_log_print("Value=%s\n", p);
			return (AUTO_INSTALL_FAILURE);
		}
	}

	return (AUTO_INSTALL_SUCCESS);
}

/*
 * Retrieve the information about the partitions
 * that need to be configured
 *
 * pstatus - return status pointer, must point to valid storage
 *	If no problems in validating partition info,
 *		set to zero, otherwise set to non-zero value
 *
 * This function allocates memory for an array
 * of auto_partition_info. The caller MUST free this memory
 */
auto_partition_info *
ai_get_manifest_partition_info(int *pstatus)
{
	auto_partition_info *api;
	int i, len;
	char **p;

	*pstatus = 0;	/* assume no parsing errors */

	p = ai_get_manifest_partition_action(&len);
	if (p == NULL)
		return (NULL);

	/* len+1 -- '1' for the NULL entry */
	api = calloc(sizeof (auto_partition_info), len + 1);

	for (i = 0; i < len; i++) {
		if (strlcpy((api + i)->partition_action, p[i],
		    AUTO_MAX_ACTION_LEN) >= AUTO_MAX_ACTION_LEN) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Partition action in manifest is too long (%s)\n",
			    p[i]);
			*pstatus = 1;
			free(api);
			return (NULL);
		}
	}
	free(p);

	p = get_manifest_element_array(AIM_PARTITION_NUMBER);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			(api + i)->partition_number = atoi(p[i]);
		}
		free(p);
	}

	/*
	 * set default for starting sector (unspecified)
	 * stored as unsigned in C, * but signed in XML
	 * so that -1 can be used in default value manifest
	 * to tell AI to find best location when starting sector not specified
	 * see om_create_partition()
	 */
	for (i = 0; i < len; i++) /* if not specified, AI finds best location */
		(api + i)->partition_start_sector = (uint64_t)-1LL;
	p = get_manifest_element_array(AIM_PARTITION_START_SECTOR);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			(api + i)->partition_start_sector =
			    (uint64_t)strtoll(p[i], NULL, 0);
		}
		free(p);
	}

	p = get_manifest_element_array(AIM_PARTITION_SIZE);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			/* if action is create, size is mandatory */
			if (strcmp((api + i)->partition_action, "create") != 0)
				continue;
			if (p[i] == NULL)	{ /* if size not provided */
				/* size required for create action */
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Partition size for create action "
				    "is missing from manifest.\n");
				*pstatus = 1;
				free(api);
				return (NULL);
			}
			if (strcasecmp(p[i], "max_size") == 0) {
				(api + i)->partition_size = OM_MAX_SIZE;
				/* zero will indicate maximum size */
				auto_log_print("Maximum size requested for "
				    "new partition.  (%d)\n", i);
			} else {
				char *endptr;

				errno = 0;
				(api + i)->partition_size =
				    strtoull(p[i], &endptr, 0);
				if (errno == 0 && endptr != p[i])
					continue;
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Partition size in manifest (%s) is "
				    "not a valid number or \"max_size\".\n",
				    p[i]);
				*pstatus = 1;
				free(api);
				errno = 0;
				return (NULL);
			}
		}
		free(p);
	}

	p = get_manifest_element_array(AIM_PARTITION_TYPE);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			/* allow some common partition type names */
			if (strcasecmp(p[i], "SOLARIS") == 0) {
				(api + i)->partition_type = SUNIXOS2;
				auto_log_print(
				    "New Solaris2 partition requested\n");
			} else if (strcasecmp(p[i], "DOS16") == 0) {
				(api + i)->partition_type = DOSOS16;
				auto_log_print(
				    "New 16-bit DOS partition requested\n");
			} else if (strcasecmp(p[i], "FAT32") == 0) {
				(api + i)->partition_type = FDISK_WINDOWS;
				auto_log_print(
				    "New FAT32 partition requested\n");
			} else if (strcasecmp(p[i], "DOSEXT") == 0) {
				(api + i)->partition_type = EXTDOS;
				auto_log_print(
				    "New DOS extended partition requested\n");
			} else if (strcasecmp(p[i], "DOSEXTLBA") == 0) {
				(api + i)->partition_type = FDISK_EXTLBA;
				auto_log_print(
				    "New DOS extended LBA partition requested"
				    "\n");
			} else {	/* use partition type number */
				char *endptr;

				errno = 0;
				(api + i)->partition_type =
				    strtoull(p[i], &endptr, 0);
				if (errno == 0 && endptr != p[i])
					continue;
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Partition type in manifest (%s) is "
				    "not a valid number or partition type.\n",
				    p[i]);
				*pstatus = 1;
				free(api);
				errno = 0;
				return (NULL);
			}
		}
		free(p);
	}

	p = get_manifest_element_array(AIM_PARTITION_SIZE_UNITS);
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
		free(p);
	}
	/*
	 * mark any partitions marked as logical
	 */
	p = get_manifest_element_array(AIM_PARTITION_IS_LOGICAL);
	if (p != NULL)
		for (i = 0; i < len; i++)
			if (strcasecmp(p[i], "true") == 0)
				(api + i)->partition_is_logical = B_TRUE;
	return (api);
}

/*
 * Retrieve the vtoc slice information
 *
 * pstatus - return status pointer, must point to valid storage
 *	If no problems in validating slice info,
 *		set to zero, otherwise set to non-zero value
 *
 * This function allocates memory for an array
 * of auto_slice_info. The caller MUST free this memory
 */
auto_slice_info *
ai_get_manifest_slice_info(int *pstatus)
{
	auto_slice_info *asi;
	int i, len = 0;
	char **p;

	*pstatus = 0;	/* assume no parsing errors */
	p = ai_get_manifest_values(AIM_SLICE_ACTION, &len);
	if (p == NULL || len <= 0)
		return (NULL);

	/* len+1 -- '1' for end of array marker */
	asi = calloc(sizeof (auto_slice_info), len + 1);

	for (i = 0; i < len; i++) {
		if (strlcpy((asi + i)->slice_action, p[i],
		    AUTO_MAX_ACTION_LEN) >= AUTO_MAX_ACTION_LEN) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Slice action in manifest is too long (%s)\n",
			    p[i]);
			*pstatus = 1;
			free(asi);
			return (NULL);
		}
	}
	free(p);

	p = get_manifest_element_array(AIM_SLICE_NUMBER);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			(asi + i)->slice_number = atoi(p[i]);
		}
		free(p);
	}

	p = get_manifest_element_array(AIM_SLICE_SIZE);
	if (p != NULL) {
		for (i = 0; i < len; i++) {
			/* if action is create, size is mandatory */
			if (p[i] == NULL)	/* if size not provided */
				/* size required for create action */
				if (strcmp((asi + i)->slice_action, "create")
				    != 0)
					continue;
				else {
					auto_debug_print(AUTO_DBGLVL_ERR,
					    "Slice size for create action "
					    "is missing from manifest.\n");
					*pstatus = 1;
					free(asi);
					return (NULL);
				}
			if (strcasecmp(p[i], "max_size") == 0) {
				(asi + i)->slice_size = OM_MAX_SIZE;
				/* zero will indicate maximum size */
				auto_log_print("Maximum size requested for "
				    "new slice.  (%d)\n", i);
			} else {
				char *endptr;

				errno = 0;
				(asi + i)->slice_size =
				    strtoull(p[i], &endptr, 0);
				if (errno == 0 && endptr != p[i])
					continue;
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Slice size in manifest (%s) is "
				    "not a valid number or \"max_size\".\n",
				    p[i]);
				*pstatus = 1;
				free(asi);
				errno = 0;
				return (NULL);
			}
		}
		free(p);
	}

	p = get_manifest_element_array(AIM_SLICE_SIZE_UNITS);
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
		free(p);
	}
	return (asi);
}

/*
 * Retrieve the URL for the default publisher
 */
char *
ai_get_manifest_default_url(int *len)
{
	char	**value;
	char	*url;

	value = ai_get_manifest_values(AIM_IPS_DEFAULT_PUBLISHER_URL, len);

	/*
	 * If publisher is not supplied, check for authority
	 */
	if (*len <= 0) {
		value = ai_get_manifest_values(
		    AIM_IPS_DEFAULT_AUTH_URL, len);
	}

	if (*len > 0) {
		url = value[0];
		free(value);
		return (url);
	}
	return (NULL);
}

/*
 * Retrieve the URL for the additional publisher
 */
char **
ai_get_manifest_addl_url(int *len)
{
	char	**value;

	value = ai_get_manifest_values(AIM_IPS_ADDL_PUBLISHER_URL, len);

	/*
	 * If publisher is not supplied, check for authority
	 */
	if (*len <= 0) {
		value = ai_get_manifest_values(
		    AIM_IPS_ADDL_AUTH_URL, len);
	}
	if (*len > 0) {
		return (value);
	}
	return (NULL);
}

/*
 * Retrieve an publisher name from the manifest using url value
 * This is the common function for default publisher and
 * additional publisher. If the value of the flag is_default_publisher
 * is true, then the default publisher tag is used.
 */
char *
ai_get_manifest_repo_publisher(boolean_t is_default_publisher, char *url)
{
	char	**value;
	char	*publisher;
	int	len;
	char	tag[MAXPATHLEN];

	if (is_default_publisher) {
		(void) snprintf(tag, sizeof (tag),
		    AIM_ADD_DEFAULT_URL_PUBLISHER_NAME, url);
	} else {
		(void) snprintf(tag, sizeof (tag),
		    AIM_ADD_ADDL_URL_PUBLISHER_NAME, url);
	}
	value = ai_get_manifest_values(tag, &len);

	/*
	 * If publisher is not supplied, check for authority
	 */
	if (len <= 0) {
		if (is_default_publisher) {
			snprintf(tag, sizeof (tag),
			    AIM_ADD_DEFAULT_URL_AUTH_NAME, url);
		} else {
			snprintf(tag, sizeof (tag),
			    AIM_ADD_ADDL_URL_AUTH_NAME, url);
		}
		value = ai_get_manifest_values(tag, &len);
	}

	if (len > 0) {
		publisher = value[0];
		free(value);
		return (publisher);
	}
	return (NULL);
}

/*
 * Retrieve the URL for an IPS repo mirrors
 * This is the common function for default publisher and
 * additional publisher. If the value of the flag is_default_publisher
 * is true, then the default publisher tag is used.
 */
auto_mirror_repo_t *
ai_get_manifest_repo_mirrors(boolean_t is_default_publisher, char *url)
{
	int			i, len = 0;
	char			**value;
	char			buf[MAXPATHLEN];
	auto_mirror_repo_t	*ptr, *tmp_ptr;
	auto_mirror_repo_t	*mirror = NULL;

	if (is_default_publisher) {
		(void) snprintf(buf, sizeof (buf),
		    AIM_ADD_DEFAULT_URL_PUBLISHER_MIRROR, url);
	} else {
		(void) snprintf(buf, sizeof (buf),
		    AIM_ADD_ADDL_URL_PUBLISHER_MIRROR, url);
	}

	value = ai_get_manifest_values(buf, &len);

	/*
	 * If publisher is not supplied, check for authority
	 */
	if (len <= 0) {
		if (is_default_publisher) {
			(void) snprintf(buf, sizeof (buf),
			    AIM_ADD_DEFAULT_URL_AUTH_MIRROR, url);
		} else {
			(void) snprintf(buf, sizeof (buf),
			    AIM_ADD_ADDL_URL_AUTH_MIRROR, url);
		}
		value = ai_get_manifest_values(buf, &len);
	}

	if (len <= 0) {
		return (NULL);
	}

	for (i = 0; i < len; i++) {
		/*
		 * Ignore the empty string
		 */
		if (strcmp(value[i], "") == 0) {
			continue;
		}
		ptr = calloc(sizeof (auto_mirror_repo_t), 1);
		if (ptr == NULL) {
			goto get_out;
		}
		ptr->mirror_url = strdup(value[i]);
		ptr->next_mirror = NULL;
		if (mirror == NULL) {
			mirror = ptr;
			tmp_ptr = ptr;
		} else {
			tmp_ptr->next_mirror = ptr;
			tmp_ptr = tmp_ptr->next_mirror;
		}
	}
	free(value);
	return (mirror);
get_out:
	free(value);
	free_repo_mirror_list(mirror);
	return (NULL);
}

/*
 * Collect the information about default publisher from
 * the manifest before processing them
 *
 * This function allocates memory for auto_repo_info_t and
 * the members publisher, url and mirror information.
 * The caller MUST free this memory
 */
auto_repo_info_t *
ai_get_default_repo_info()
{
	char			*p;
	char			*current_url, *default_url;
	int			num_url;
	auto_repo_info_t 	*repo, *default_repo;
	boolean_t		is_default_publisher = B_TRUE;

	default_repo = NULL;

	/*
	 * Get the url of the default publisher
	 */
	current_url = ai_get_manifest_default_url(&num_url);
	if (current_url == NULL) {
		return (NULL);
	}

	repo = calloc(sizeof (auto_repo_info_t), 1);
	if (repo == NULL) {
		return (NULL);
	}

	/*
	 * Save the value before calling another ai_get_manifest_*()
	 */
	default_url = strdup(current_url);
	p = ai_get_manifest_repo_publisher(is_default_publisher, default_url);
	if (p == NULL) {
		goto get_out;
	}
	repo->publisher = strdup(p);
	repo->url = strdup(default_url);
	if (repo->publisher == NULL || repo->url == NULL) {
		goto get_out;
	}

	/*
	 * get the mirrors for this publishers
	 */
	repo->mirror_repo =
	    ai_get_manifest_repo_mirrors(is_default_publisher, default_url);
	repo->next_repo = NULL;
	default_repo = repo;

	free(default_url);
	return (default_repo);
get_out:
	free(default_url);
	if (repo != NULL)  {
		free(repo->publisher);
		free(repo->url);
		free(repo);
	}
	return (NULL);
}

/*
 * Automated Installer allows specifying more than one additional
 * publishers. Collect all the additional publishers from
 * the manifest before processing them
 *
 * This function allocates memory for auto_repo_info_t and
 * the members publisher, url and mirror information.
 * The caller MUST free this memory
 */
auto_repo_info_t *
ai_get_additional_repo_info()
{
	char			*p;
	char			**urls;
	int			i,  num_url;
	auto_repo_info_t 	*repo, *tmp_repo, *addl_repo;
	boolean_t		is_default_publisher = B_FALSE;

	addl_repo = NULL;
	tmp_repo = NULL;

	/*
	 * This function will return one url per publisher
	 * num_url contains the number of publishers
	 */
	urls = ai_get_manifest_addl_url(&num_url);
	if (urls == NULL)
		return (NULL);

	/*
	 * Allocate space and save the urls because the next
	 * call to ai_get_manifest_*() will overwrite them
	 */
	for (i = 0; i < num_url; i++) {
		/*
		 * Ignore the empty string
		 */
		if (strcmp(urls[i], "") == 0) {
			continue;
		}
		repo = calloc(sizeof (auto_repo_info_t), 1);
		if (repo == NULL) {
			return (NULL);
		}
		repo->url = strdup(urls[i]);
		if (repo->url == NULL) {
			free(repo);
			goto get_out;
		}
		repo->next_repo = NULL;

		if (addl_repo == NULL) {
			addl_repo = repo;
			tmp_repo = repo;
		} else {
			tmp_repo->next_repo = repo;
			tmp_repo = tmp_repo->next_repo;
		}
	}

	/*
	 * For each url (publisher), get the publisher name and
	 * mirrors (if any).
	 */
	for (repo = addl_repo; repo != NULL; repo = repo -> next_repo) {
		p = ai_get_manifest_repo_publisher(
		    is_default_publisher, repo->url);
		if (p == NULL) {
			goto get_out;
		}
		repo->publisher = strdup(p);
		if (repo->publisher == NULL) {
			goto get_out;
		}

		/*
		 * get the mirrors for this publisher
		 */
		repo->mirror_repo = ai_get_manifest_repo_mirrors(
		    is_default_publisher, repo->url);
	}

	free(urls);
	return (addl_repo);
get_out:
	free(urls);
	free_repo_info_list(addl_repo);
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
	char *proxy;

	value = ai_get_manifest_values(AIM_PROXY_URL, &len);

	if (len > 0) {
		proxy = value[0];
		free(value);
		return (proxy);
	}
	return (NULL);
}

/*
 * Retrieve the list of packages to be installed
 *
 * Parameters:
 *    *num_packages - set to number of obtained packages
 *    pkg_list_tag - path to XML node which contents is to be obtained
 *
 * Returns:
 *    - array of strings specified for given tag
 *    - NULL, if tag is empty or not defined
 */
char **
ai_get_manifest_packages(int *num_packages_p, char *pkg_list_tag_p)
{
	char **package_list;

	package_list = ai_get_manifest_values(pkg_list_tag_p, num_packages_p);

	if (*num_packages_p > 0)
		return (package_list);
	return (NULL);
}

static int
parse_property(char *str, char *keyword, char *value)
{
	char	*token;
	char	*eol;

	if (str == NULL) {
		return (NULL);
	}

	if (*str == '#') {
		return (NULL);
	}
	strcpy(value, "[not found]"); /* assume failure to parse value */

	eol = str + strlen(str);
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
		} else if (strstr(token, AUTO_PROPERTY_HOSTNAME) != NULL) {
			strlcpy(keyword, AUTO_PROPERTY_HOSTNAME, KEYWORD_SIZE);
			break;
		}
	}

	if (*keyword == '\0') {
		return (AUTO_INSTALL_FAILURE);
	}
	while ((token = strtok(NULL, " ")) != NULL) {
		char	*pkeyword_value, *pbeg, *pend;

		/* find keyword 'value=<something>' */
		pkeyword_value = strstr(token, KEYWORD_VALUE);
		if (pkeyword_value == NULL) {
			continue;
		}
		/* find beginning value delimiter */
		pbeg = strchr(pkeyword_value, '\'');
		if (pbeg == NULL) {
			pbeg = strchr(pkeyword_value, '\"');
			if (pbeg == NULL) /* no starting delimiter */
				return (AUTO_INSTALL_FAILURE);
		}
		if (eol > pbeg + strlen(pbeg)) /* if strtok inserted NULL */
			*(pbeg + strlen(pbeg)) = ' '; /* restore orig delim */
		/* find ending value delimiter */
		pend = strchr(pbeg + 1, *pbeg);
		if (pend == NULL) /* no ending delimiter */
			return (AUTO_INSTALL_FAILURE);
		*pend = '\0';
		if (strlcpy(value, ++pbeg, VALUE_SIZE) >= VALUE_SIZE) {
			if (strcmp(keyword, AUTO_PROPERTY_ROOTPASS) == 0 ||
			    strcmp(keyword, AUTO_PROPERTY_USERPASS) == 0) {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "A password (%s) in the SC manifest is "
				    "too long (>%d bytes). Shorten password "
				    "and retry installation.\n",
				    keyword, VALUE_SIZE);
				return (AUTO_INSTALL_FAILURE);
			}
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "SC manifest value for %s is too long (>%d bytes) "
			    "and will be truncated to |%s|\n",
			    keyword, VALUE_SIZE, pbeg);
		}
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

			/*
			 * if couldn't parse the property, log the error
			 * message and return
			 */
			if (ret != AUTO_INSTALL_SUCCESS) {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Could not parse %s property from SC"
				    " manifest\n", keyword);

				return (AUTO_INSTALL_FAILURE);
			}

			/*
			 * log the property and value obtained as a result
			 * of parsing SC manifest for debugging purposes
			 */

			auto_debug_print(AUTO_DBGLVL_INFO,
			    "SC manifest keyword=|%s| value=|%s|\n",
			    keyword, value);

			/*
			 * if property is set to empty string, complain and
			 * exit, since this is invalid value
			 */

			if (value[0] == '\0') {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Property '%s' in system configuration"
				    " manifest is set to empty string which is"
				    " invalid value.\n"
				    "If you do not want to configure this"
				    " property, please remove it from SC"
				    " manifest.\n",
				    keyword);

				return (AUTO_INSTALL_FAILURE);
			}

			if (strcmp(keyword, AUTO_PROPERTY_USERNAME) == 0) {
				sp->username = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_USERDESC) == 0) {
				sp->userdesc = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_USERPASS) == 0) {
				sp->userpass = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_ROOTPASS) == 0) {
				sp->rootpass = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_TIMEZONE) == 0) {
				sp->timezone = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_HOSTNAME) == 0) {
				sp->hostname = strdup(value);
			} else
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "unrecognized SC manifest keyword "
				    "%s ignored\n", keyword);
		}
	}
	fclose(profile_fp);
	return (AUTO_INSTALL_SUCCESS);
}

/*
 * Free the mirror list created while the parsing the manifest
 */
void
free_repo_mirror_list(auto_mirror_repo_t *mirror)
{
	auto_mirror_repo_t *mptr;
	while (mirror != NULL) {
		free(mirror->mirror_url);
		mptr = mirror;
		mirror = mirror->next_mirror;
		free(mptr);
	}
}

/*
 * Free the IPS repo list created while the parsing the manifest
 */
void
free_repo_info_list(auto_repo_info_t *repo)
{
	auto_repo_info_t  *rptr;

	while (repo != NULL) {
		free(repo->publisher);
		free(repo->url);
		free_repo_mirror_list(repo->mirror_repo);
		rptr = repo;
		repo = repo->next_repo;
		free(rptr);
	}
}
