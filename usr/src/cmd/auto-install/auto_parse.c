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
 * Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
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

static PyObject *manifest_serv_obj;
static char *manifest_filename;

/*
 * Function to execute shell commands in a thread-safe manner. Output from
 * stdout is captured in install log file.
 *
 * Parameters:
 *	cmd - the command to execute
 *
 * Return:
 *	-1 if popen() failed, otherwise exit code returned by command
 *
 * Status:
 *	private
 */
static int
ai_exec_cmd(char *cmd)
{
	FILE	*p;
	char	buf[MAX_SHELLCMD_LEN];

	auto_debug_print(AUTO_DBGLVL_INFO, "exec cmd: %s\n", cmd);

	if ((p = popen(cmd, "r")) == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Could not execute following command: %s.\n", cmd);

		return (-1);
	}

	/*
	 * capture stdout for debugging purposes
	 */

	while (fgets(buf, sizeof (buf), p) != NULL)
		auto_debug_print(AUTO_DBGLVL_ERR, " %s", buf);

	return (WEXITSTATUS(pclose(p)));
}

/*
 * Dump errors found during syntactic validation of AI manifest -
 * repeat the xmllint(1) call made on the Python side to capture the
 * stdout and stderr.  xmllint will be called with following parameters:
 *
 * /usr/bin/xmllint --noout --dtdvalid <schema> --dtdattr <manifest> 2>&1
 *
 * Returns
 * 	-1  - failed to dump syntactic errors
 *	>=0 - exit code from xmllint(1M)
 */
static int
dump_ai_manifest_errors(char *manifest, char *schema)
{
	char	*cmd;
	size_t	cmd_ln;
	int	ret;
	char *dtd_xmllint =
	    "/usr/bin/xmllint --noout --dtdvalid %s --dtdattr %s 2>&1";

	/* calculate size of command string */
	cmd_ln = snprintf(NULL, 0, dtd_xmllint, schema, manifest);
	cmd = (char *)malloc(cmd_ln + 1);

	if (cmd == NULL) {
		auto_debug_print(AUTO_DBGLVL_ERR, "malloc() failed\n");

		return (-1);
	}

	(void) snprintf(cmd, cmd_ln + 1, dtd_xmllint, schema, manifest);

	ret = ai_exec_cmd(cmd);

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
 * Translate size units from manifest into auto_size_units_t values.
 *
 * Defaults to AI_SIZE_UNITS_MEGABYTES if no value given or value
 * not recognized.
 *
 * Returns
 *  auto_size_units_t
 */
static auto_size_units_t
get_size_units(char *p_str)
{
	if ((p_str == NULL) || (! strlen(p_str))) {
		return (AI_SIZE_UNITS_MEGABYTES);
	}

	switch (p_str[0]) {
		case 's':
		case 'S':
			return (AI_SIZE_UNITS_SECTORS);
		case 'g':
		case 'G':
			return (AI_SIZE_UNITS_GIGABYTES);
		case 't':
		case 'T':
			return (AI_SIZE_UNITS_TERABYTES);
		case 'm':
		case 'M':
		default:
			return (AI_SIZE_UNITS_MEGABYTES);
	}
}

/*
 * Convert size from one unit of measurement to another.
 *
 * Supported units are the auto_size_units_t enumeration:
 *  AI_SIZE_UNITS_SECTORS
 *  AI_SIZE_UNITS_MEGABYTES
 *  AI_SIZE_UNITS_GIGABYTES
 *  AI_SIZE_UNITS_TERABYTES
 * If either from_units or to_units params are not recognized, disk_size is
 * returned unaltered.
 *
 * Returns
 *  uint64_t
 */
static uint64_t
convert_disk_size(uint64_t disk_size, auto_size_units_t from_units,
    auto_size_units_t to_units)
{
	uint64_t retval = disk_size;

	switch (to_units) {
		case AI_SIZE_UNITS_SECTORS:
			switch (from_units) {
				case AI_SIZE_UNITS_SECTORS:
					retval = disk_size;
				case AI_SIZE_UNITS_MEGABYTES:
					retval = disk_size * MB_TO_SECTORS;
				case AI_SIZE_UNITS_GIGABYTES:
					retval = disk_size * GB_TO_MB *
					    MB_TO_SECTORS;
				case AI_SIZE_UNITS_TERABYTES:
					retval = disk_size * TB_TO_GB *
					    GB_TO_MB * MB_TO_SECTORS;
			}
		case AI_SIZE_UNITS_MEGABYTES:
			switch (from_units) {
				case AI_SIZE_UNITS_SECTORS:
					retval = disk_size / MB_TO_SECTORS;
				case AI_SIZE_UNITS_MEGABYTES:
					retval = disk_size;
				case AI_SIZE_UNITS_GIGABYTES:
					retval = disk_size * GB_TO_MB;
				case AI_SIZE_UNITS_TERABYTES:
					retval = disk_size * TB_TO_GB *
					    GB_TO_MB;
			}
		case AI_SIZE_UNITS_GIGABYTES:
			switch (from_units) {
				case AI_SIZE_UNITS_SECTORS:
					retval = disk_size / GB_TO_MB /
					    MB_TO_SECTORS;
				case AI_SIZE_UNITS_MEGABYTES:
					retval = disk_size / GB_TO_MB;
				case AI_SIZE_UNITS_GIGABYTES:
					retval = disk_size;
				case AI_SIZE_UNITS_TERABYTES:
					retval = disk_size * TB_TO_GB;
			}
		case AI_SIZE_UNITS_TERABYTES:
			switch (from_units) {
				case AI_SIZE_UNITS_SECTORS:
					retval = disk_size / MB_TO_SECTORS /
					    GB_TO_MB / TB_TO_GB;
				case AI_SIZE_UNITS_MEGABYTES:
					retval = disk_size / GB_TO_MB /
					    TB_TO_GB;
				case AI_SIZE_UNITS_GIGABYTES:
					retval = disk_size / TB_TO_GB;
				case AI_SIZE_UNITS_TERABYTES:
					retval = disk_size;
			}
	}

	return (retval);
}

/*
 * Create the manifest data image in memory.  (Does not validate it.)
 *
 * Import the manifest into an in-memory tree
 * that can subsequently be queried for the various
 * attributes. A handle to the in-memory tree is stored
 * as a ManifestServ object pointed to by manifest_serv_obj.
 *
 * The manifest filename is saved for later use, in manifest_filename.
 *
 * Note that this function must be called before anything else which
 * references manifest_serv_obj or manifest_filename in this module.
 *
 * Returns
 * 	AUTO_VALID_MANIFEST if it's a valid manifest
 * 	AUTO_INVALID_MANIFEST if it's an invalid manifest
 */
int
ai_create_manifest_image(char *filename)
{
	/*
	 * If the manifest_serv_obj is set it means that
	 * the manifest has already been validated and
	 * a server object created for it
	 */
	if (manifest_serv_obj != NULL)
		return (AUTO_VALID_MANIFEST);

	manifest_filename = NULL;
	manifest_serv_obj = ai_create_manifestserv(filename);
	if (manifest_serv_obj != NULL) {
		manifest_filename = strdup(filename);
		return (AUTO_VALID_MANIFEST);
	}

	auto_log_print(gettext("Failure to create manifest data in memory.\n"));
	return (AUTO_INVALID_MANIFEST);
}

/*
 * Validate the manifest syntactically as well as
 * semantically.
 *
 * As part of the validation process, fill in the
 * defaults for the attributes that aren't specified.
 *
 * Returns
 * 	AUTO_VALID_MANIFEST if it's a valid manifest
 * 	AUTO_INVALID_MANIFEST if it's an invalid manifest
 */
int
ai_setup_manifest_image()
{
	if (ai_setup_manifestserv(manifest_serv_obj) == AUTO_INSTALL_SUCCESS) {
		return (AUTO_VALID_MANIFEST);
	}

	/*
	 * if the validation process failed, capture output of syntactic
	 * validation in log file
	 */
	auto_log_print(gettext("Syntactic validation of the manifest failed "
	    "with following errors\n"));

	if (dump_ai_manifest_errors(
	    manifest_filename, AI_MANIFEST_SCHEMA) == -1) {
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

/*
 * Free memory allocated by ai_get_manifest_values().
 */
void
ai_free_manifest_values(char **value_list)
{
	ai_free_manifest_value_list(value_list);
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

	p = ai_get_manifest_element_value(AIM_TARGET_DISK_KEYWORD);
	if (p != NULL)
		(void) strncpy(adi->diskkeyword, p, sizeof (adi->diskkeyword));

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
	if (p != NULL) {
		char *endptr;
		uint64_t disk_size;
		auto_size_units_t size_units;

		errno = 0;

		/* Get the numerical portion of the size value */
		disk_size = (uint64_t)strtoull(p, &endptr, 0);

		if (errno == 0 && endptr != p) {
			/*
			 * Get the units portion of the size val and then
			 * convert the size from given units into number
			 * of disk sectors.
			 */
			size_units = get_size_units(endptr);
			adi->disksize = convert_disk_size(disk_size, size_units,
			    AI_SIZE_UNITS_SECTORS);

			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Requested target size [%s] converted "
			    "to [%lld] sectors\n",
			    p, adi->disksize);
		} else {
			auto_log_print(
			    "Invalid target device size specified: [%s]",
			    p);
			return (AUTO_INSTALL_FAILURE);
		}
	}

	p = ai_get_manifest_element_value(
	    AIM_TARGET_DEVICE_USE_SOLARIS_PARTITION);
	if (p != NULL) {
#ifdef	__sparc
		auto_log_print("Warning: ignoring manifest element "
		    "partition action='use_existing' on SPARC\n");
#else
		/*
		 * In this Schema, a partition with attribute
		 * action="use_existing" corresponds to
		 * target_device_use_solaris_partition="true"
		 * in the previous schema.
		 */
		(void) strncpy(adi->diskusepart, "true",
		    sizeof (adi->diskusepart));
#endif
	}

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

	/* Debug - print disk info out to log */
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "Disk info from Manifest:\n");
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskkeyword\t\t\t: [%s]\n", adi->diskkeyword);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskname\t\t\t: [%s]\n", adi->diskname);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdisktype\t\t\t: [%s]\n", adi->disktype);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskvendor\t\t\t: [%s]\n", adi->diskvendor);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskvolname\t\t\t: [%s]\n", adi->diskvolname);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskdevid\t\t\t: [%s]\n", adi->diskdevid);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskdevicepath\t\t: [%s]\n", adi->diskdevicepath);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdisksize\t\t\t: [%d]\n", adi->disksize);
#ifndef	__sparc
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskusepart\t\t\t: [%s]\n", adi->diskusepart);
#endif
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskiscsi.name\t\t: [%s]\n", adi->diskiscsi.name);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskiscsi.ip\t\t: [%s]\n", adi->diskiscsi.ip);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskiscsi.port\t\t: [%d]\n", adi->diskiscsi.port);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskiscsi.lun\t\t: [%s]\n", adi->diskiscsi.lun);
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tdiskiscsi.parm_src\t: [%d] (= %s)\n", adi->diskiscsi.parm_src,
	    adi->diskiscsi.parm_src ? "DHCP" : "MANIFEST");
	auto_debug_print(AUTO_DBGLVL_INFO,
	    "\tinstall_slice_num.\t: [%d]\n", adi->install_slice_number);

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
		char *endptr;
		int32_t swap_size;
		auto_size_units_t size_units;

		errno = 0;

		/* Get the numerical portion of the size value */
		swap_size = (int32_t)strtol(p, &endptr, 0);

		if (errno == 0 && endptr != p) {
			/*
			 * Get the units portion of the size val and
			 * then convert the size from given units into MB.
			 */
			size_units = get_size_units(endptr);
			adsi->swap_size = (int32_t)convert_disk_size(swap_size,
			    size_units,
			    AI_SIZE_UNITS_MEGABYTES);

			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Requested swap size [%s] converted to [%d] MB\n",
			    p, adsi->swap_size);
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
		char *endptr;
		int32_t dump_size;
		auto_size_units_t size_units;

		errno = 0;

		/* Get the numerical portion of the size value */
		dump_size = (int32_t)strtol(p, &endptr, 0);

		if (errno == 0 && endptr != p) {
			/*
			 * Get the units portion of the size val and
			 * then convert the size from given units into MB.
			 */
			size_units = get_size_units(endptr);
			addi->dump_size = (int32_t)convert_disk_size(dump_size,
			    size_units,
			    AI_SIZE_UNITS_MEGABYTES);

			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Requested dump size [%s] converted to [%d] MB\n",
			    p, addi->dump_size);
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
 * Create a partition info struct and populate it with details
 * from the manifest matching the specified tags (enhanced
 * nodepaths).
 *
 * pstatus - return status pointer, must point to valid storage
 *		If no problems in validating partition info,
 *		set to zero, otherwise set to non-zero value
 *
 * This function allocates memory for an auto_partition_info
 * struct. The caller MUST free this memory.
 */
static auto_partition_info *
get_partition_by_tags(char *number_tag, char *action_tag,
    char *start_tag, char *size_tag, char *type_tag, int *pstatus)
{
	auto_partition_info *api;
	char *p;
	char *endptr;

	api = calloc(sizeof (auto_partition_info), 1);
	if (api == NULL)
		return (NULL);

	/* Get the name (number) for this partition */
	p = ai_get_manifest_element_value(number_tag);
	if (p != NULL) {
		errno = 0;
		api->partition_number = (int) strtoul(p, &endptr, 10);
		if (errno != 0 || endptr == p) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Partition name in manifest (%s) is "
			    "not a valid value.\n",
			    p);
			*pstatus = 1;
			free(api);
			errno = 0;
			return (NULL);
		}
	}

	/* Get the action for this partition */
	p = ai_get_manifest_element_value(action_tag);
	if (p != NULL)
		(void) strlcpy(api->partition_action, p,
		    sizeof (api->partition_action));

	/*
	 * Get the start_sector for this partition
	 *
	 * set default for starting sector (unspecified)
	 * stored as unsigned in C, * but signed in XML
	 * so that -1 can be used in default value manifest
	 * to tell AI to find best location when starting sector not specified
	 * see om_create_partition()
	 */
	api->partition_start_sector = (uint64_t)-1LL;
	p = ai_get_manifest_element_value(start_tag);
	if (p != NULL) {
		api->partition_start_sector =
		    (uint64_t)strtoll(p, NULL, 0);
	}

	/*
	 * Get the size (value + units) for this partition.
	 * This is only used for "create" action.
	 */
	if (strcmp(api->partition_action, "create") == 0) {
		p = ai_get_manifest_element_value(size_tag);
		if (p != NULL) {
			errno = 0;

			/* Get the numerical portion of the size value */
			api->partition_size = strtoull(p, &endptr, 0);

			if (errno == 0 && endptr != p) {
				/* Get the units portion of the size value */
				api->partition_size_units =
				    get_size_units(endptr);
			} else {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Partition size in manifest (%s) is "
				    "not a valid value.\n",
				    p);
				*pstatus = 1;
				free(api);
				errno = 0;
				return (NULL);
			}
		} else {
			/*
			 * Default to 0mb.  This is not strictly necessary,
			 * as both these values correspond to 0, which was
			 * the value they were already set to when the struct
			 * was calloc()ed.
			 */
			api->partition_size = (uint64_t) 0;
			api->partition_size_units = AI_SIZE_UNITS_MEGABYTES;
		}
	}

	/* Get the filesystem type for this partition */
	p = ai_get_manifest_element_value(type_tag);
	if (p != NULL) {
		/* allow some common partition type names */
		if (strcasecmp(p, "SOLARIS") == 0) {
			api->partition_type = SUNIXOS2;
			auto_log_print(
			    "New Solaris2 partition requested\n");
		} else if (strcasecmp(p, "DOS16") == 0) {
			api->partition_type = DOSOS16;
			auto_log_print(
			    "New 16-bit DOS partition requested\n");
		} else if (strcasecmp(p, "FAT32") == 0) {
			api->partition_type = FDISK_WINDOWS;
			auto_log_print(
			    "New FAT32 partition requested\n");
		} else if (strcasecmp(p, "DOSEXT") == 0) {
			api->partition_type = EXTDOS;
			auto_log_print(
			    "New DOS extended partition requested\n");
		} else if (strcasecmp(p, "DOSEXTLBA") == 0) {
			api->partition_type = FDISK_EXTLBA;
			auto_log_print(
			    "New DOS extended LBA partition requested"
			    "\n");
		} else {
            /*
             * Use partition type number, eg "191" to
             * represent a Solaris partition.
             */
			char *endptr;

			errno = 0;
			api->partition_type =
			    strtoull(p, &endptr, 0);
			if (errno != 0 || endptr == p) {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Partition type in manifest (%s) is "
				    "not a valid number or partition type.\n",
				    p);
				*pstatus = 1;
				free(api);
				errno = 0;
				return (NULL);
			}
		}
	}

	/*
	 * Determine if this is a logical partition
	 * This is inferred from the partition number.  Numbers of
	 * 5 or greater imply the partition must be logical.
	 */
	if (api->partition_number >= 5) {
		api->partition_is_logical = B_TRUE;
	}

	return (api);
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
	auto_partition_info *ret_api;
	auto_partition_info *api;
	int i, j;
	int actions_len = 0;
	int numbered_len = 0;
	int unnumbered_len = 0;
	char **partition_actions;
	char **numbered_partitions;
	char **unnumbered_partitions;
	char *p;
	char number_tag[MAXPATHLEN];
	char action_tag[MAXPATHLEN];
	char start_tag[MAXPATHLEN];
	char size_tag[MAXPATHLEN];
	char type_tag[MAXPATHLEN];

	*pstatus = 0;	/* assume no parsing errors */

	/*
	 * The name (number) is not mandatory for partitions, but if a partition
	 * does not have a name then it must have the action 'use_existing'.
	 * There can only be one 'use_existing' partition specified and it may
	 * or may not be named.
	 * We will first see if there is an un-named 'use_existing' partition
	 * in the manifest and if so, fetch its details.  Then we will fetch
	 * details for all the named partitions, using name+action as a unique
	 * key.
	 */

	unnumbered_partitions = ai_get_manifest_values(
	    AIM_USE_EXISTING_PARTITIONS, &unnumbered_len);
	numbered_partitions = ai_get_manifest_values(
	    AIM_NUMBERED_PARTITIONS, &numbered_len);

	if (unnumbered_partitions == NULL) {
		/* ai_get_manifest_values sets len to -1 if none found */
		unnumbered_len = 0;
	} else {
		if (unnumbered_len > 1) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Only one 'use_existing' partition is permitted, "
			    "%d were specified.\n", unnumbered_len);
			*pstatus = 1;
			return (NULL);
		}

		p = ai_get_manifest_element_value(
		    AIM_UNNUMBERED_PARTITION_NUMBER);
		if (p != NULL) {
			/*
			 * There is one 'use_existing' partition but a
			 * name (number) was specified with it, so it
			 * will be handled along with numbered
			 * partitions - no need for specical handling here.
			 */
			unnumbered_len = 0;
		}
	}

	if (numbered_partitions == NULL) {
		/* ai_get_manifest_values sets len to -1 if none found */
		numbered_len = 0;
	}

	if ((unnumbered_len + numbered_len) == 0)
		return (NULL);

	/* len+1 -- '1' for the NULL entry */
	ret_api = calloc(sizeof (auto_partition_info),
	    numbered_len + unnumbered_len + 1);
	if (ret_api == NULL)
		return (NULL);

	if (unnumbered_len) {
		/*
		 * We have exactly one partition whose action is 'use_existing'
		 * which does not have a name (number) specified.  We need
		 * to fetch its details seperately from the numbered partitions.
		 */
		(void) snprintf(number_tag, sizeof (number_tag),
		    AIM_UNNUMBERED_PARTITION_NUMBER);
		(void) snprintf(action_tag, sizeof (action_tag),
		    AIM_UNNUMBERED_PARTITION_ACTION);
		(void) snprintf(start_tag, sizeof (start_tag),
		    AIM_UNNUMBERED_PARTITION_START_SECTOR);
		(void) snprintf(size_tag, sizeof (size_tag),
		    AIM_UNNUMBERED_PARTITION_SIZE);
		(void) snprintf(type_tag, sizeof (type_tag),
		    AIM_UNNUMBERED_PARTITION_TYPE);

		api = get_partition_by_tags(number_tag, action_tag,
		    start_tag, size_tag, type_tag, pstatus);

		if (api == NULL) {
			free(unnumbered_partitions);
			free(ret_api);
			return (NULL);
		}

		(void) memcpy(ret_api, api, sizeof (auto_partition_info));
		free(api);

		free(unnumbered_partitions);
	}

	if (numbered_len) {
		partition_actions = ai_get_manifest_values(
		    AIM_PARTITION_ACTIONS, &actions_len);

		if (partition_actions == NULL) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Error fetching partition actions.\n");
			*pstatus = 1;
			free(numbered_partitions);
			free(ret_api);
			return (NULL);
		}

		if (unnumbered_len) {
			/*
			 * Remove the unnamed 'use_existing' partition from
			 * partition_actions.
			 */
			for (i = 0; i < actions_len; i++) {
				if (strcmp(partition_actions[i],
				    "use_existing") == 0) {
					/*
					 * Shuffle the remaining items up
					 * one position.
					 */
					for (j = i; j < (actions_len - 1);
					    j++) {
						partition_actions[j] =
						    partition_actions[j+1];
					}
					partition_actions[actions_len] = NULL;
					actions_len--;
				}
			}
		}

		if (numbered_len != actions_len) {
			if (numbered_len < actions_len) {
				/*
				 * If this mismatch occurs, there must have
				 * been an unnamed partion whose action is
				 * not 'use_existing'.
				 */
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Invalid unnamed partition specified in "
				    "manifest. Only one unnamed partition "
				    "allowed, whose action must be "
				    "'use_existing'.\n");
				*pstatus = 1;
				free(numbered_partitions);
				free(partition_actions);
				free(ret_api);
				return (NULL);
			} else {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Error matching partition actions to "
				    "names.\n");
				*pstatus = 1;
				free(numbered_partitions);
				free(partition_actions);
				free(ret_api);
				return (NULL);
			}
		}

		/*
		 * One or more numbered partitions have been specified.
		 * Fetch the necessary details for each.
		 */
		for (i = 0; i < numbered_len; i++) {
			(void) snprintf(number_tag, sizeof (number_tag),
			    AIM_NUMBERED_PARTITION_NUMBER,
			    numbered_partitions[i], partition_actions[i]);
			(void) snprintf(action_tag, sizeof (action_tag),
			    AIM_NUMBERED_PARTITION_ACTION,
			    numbered_partitions[i], partition_actions[i]);
			(void) snprintf(start_tag, sizeof (start_tag),
			    AIM_NUMBERED_PARTITION_START_SECTOR,
			    numbered_partitions[i], partition_actions[i]);
			(void) snprintf(size_tag, sizeof (size_tag),
			    AIM_NUMBERED_PARTITION_SIZE,
			    numbered_partitions[i], partition_actions[i]);
			(void) snprintf(type_tag, sizeof (type_tag),
			    AIM_NUMBERED_PARTITION_TYPE,
			    numbered_partitions[i], partition_actions[i]);

			api = get_partition_by_tags(number_tag, action_tag,
			    start_tag, size_tag, type_tag, pstatus);

			if (api == NULL) {
				free(numbered_partitions);
				free(ret_api);
				return (NULL);
			}

			(void) memcpy((ret_api + unnumbered_len + i),
			    api, sizeof (auto_partition_info));
			free(api);
		}

		free(numbered_partitions);
	}

	/* Debug - print partition info out to log */
	api = ret_api;
	for (; api->partition_action[0] != '\0'; api++) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Partition details from Manifest:\n");
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_action\t\t: [%s]\n",
		    api->partition_action);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_number\t\t: [%d]\n",
		    api->partition_number);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_start_sector\t: [%lld]\n",
		    api->partition_start_sector);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_size\t\t\t: [%lld]\n",
		    api->partition_size);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_type\t\t\t: [%d]\n",
		    api->partition_type);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_size_units\t: [%d] (= %s)\n",
		    (int)api->partition_size_units,
		    CONVERT_UNITS_TO_TEXT(api->partition_size_units));
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tpartition_is_logical\t: [%d] (= %s)\n",
		    (int)api->partition_is_logical,
		    api->partition_is_logical ? "true" : "false");
	}

	return (ret_api);
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
	auto_slice_info *tmp_asi;
	int i, names_len = 0, actions_len = 0;
	char *p;
	char **slice_names;
	char **slice_actions;
	char tag[MAXPATHLEN];
	char *endptr;

	*pstatus = 0;	/* assume no parsing errors */

	/*
	 * The name (number) and action attributes are mandatory for slices, so
	 * we will use these two values as the unique key for slice elements.
	 * First we fetch all the slice numbers and actions, then we query the
	 * manifest using these values to fetch the additional details for
	 * each slice.
	 */

	slice_names = ai_get_manifest_values(AIM_SLICE_NUMBER, &names_len);

	if (slice_names == NULL || names_len <= 0)
		return (NULL);

	slice_actions = ai_get_manifest_values(AIM_SLICE_ACTION, &actions_len);

	if (actions_len != names_len) {
		auto_debug_print(AUTO_DBGLVL_ERR,
		    "Error matching slice names to actions.\n");
		*pstatus = 1;
		free(slice_names);
		free(slice_actions);
		return (NULL);
	}

	/* len+1 -- '1' for end of array marker */
	asi = calloc(sizeof (auto_slice_info), names_len + 1);

	if (asi == NULL) {
		free(slice_names);
		free(slice_actions);
		return (NULL);
	}

	for (i = 0; i < names_len; i++) {
		/* Get the number for this slice */
		(asi + i)->slice_number = atoi(slice_names[i]);

		/* Get the action for this slice */
		if (strlcpy((asi + i)->slice_action, slice_actions[i],
		    AUTO_MAX_ACTION_LEN) >= AUTO_MAX_ACTION_LEN) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Slice action in manifest is too long (%s)\n", p);
			*pstatus = 1;
			free(asi);
			free(slice_names);
			free(slice_actions);
			return (NULL);
		}

		/* Get the size (value + units) for this slice */
		(void) snprintf(tag, sizeof (tag), AIM_SLICE_SIZE,
		    slice_names[i], slice_actions[i]);
		p = ai_get_manifest_element_value(tag);
		if (p == NULL) {
			/*
			 * Default to 0mb.  This is not strictly necessary,
			 * as both these values correspond to 0, which was
			 * the value they were already set to when the struct
			 * was calloc()ed.
			 */
			(asi + i)->slice_size = (uint64_t) 0;
			(asi + i)->slice_size_units = AI_SIZE_UNITS_MEGABYTES;
		} else {
			errno = 0;

			/* Get the numerical portion of the size value */
			(asi + i)->slice_size = strtoull(p, &endptr, 0);

			if (errno == 0 && endptr != p) {
				/* Get the units portion of the size value */
				(asi + i)->slice_size_units =
				    get_size_units(endptr);
			} else {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "Slice size in manifest (%s) is "
				    "not a valid number.\n",
				    p);
				*pstatus = 1;
				free(asi);
				free(slice_names);
				free(slice_actions);
				errno = 0;
				return (NULL);
			}
		}

		/*
		 * Determine behavior for create action on existing slices.
		 */
		(void) snprintf(tag, sizeof (tag),
		    AIM_SLICE_ON_EXISTING, slice_names[i], slice_actions[i]);
		p = ai_get_manifest_element_value(tag);
		if (p != NULL) {
			/*
			 * Since the slice information array is initialized
			 * to zero, and the default enum value is also zero,
			 * the "error" case will also be the default in the
			 * slice information array.
			 *
			 * In the new schema, the slice attribute 'force'
			 * controls this.  If force="false" (the default)
			 * then we leave on_existing=0, which equates to
			 * OM_ON_EXISTING_ERROR. If force="true", then we
			 * set it to OM_ON_EXISTING_OVERWRITE.
			 */
			if (strcasecmp(p, "true") == 0)
				(asi + i)->on_existing =
				    OM_ON_EXISTING_OVERWRITE;
		}
	}

	free(slice_names);
	free(slice_actions);

	/* Debug - print slice info out to log */
	tmp_asi = asi;
	for (; tmp_asi->slice_action[0] != '\0'; tmp_asi++) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Slice details from Manifest:\n");
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tslice_action\t\t: [%s]\n",
		    tmp_asi->slice_action);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tslice_number\t\t: [%d]\n",
		    tmp_asi->slice_number);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tslice_size\t\t\t: [%lld]\n",
		    tmp_asi->slice_size);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\tslice_size_units\t: [%d] (= %s)\n",
		    (int)tmp_asi->slice_size_units,
		    CONVERT_UNITS_TO_TEXT(tmp_asi->slice_size_units));
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "\ton_existing\t: [%d] (= %s)\n",
		    (int)tmp_asi->on_existing,
		    tmp_asi->on_existing ? "OVERWRITE" : "ERROR");
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

	value = ai_get_manifest_values(AIM_IPS_PUBLISHER_URL, len);

	if (*len > 0) {
		url = value[0];
		free(value);
		return (url);
	}
	return (NULL);
}

/*
 * Retrieve the URL(s) for the additional publisher(s)
 *
 * Default and additional (or primary and secondary) publishers
 * now use the same nodepaths, so this function repeats the same
 * search as ai_get_manifest_default_url() but the results are
 * handled differently.
 */
char **
ai_get_manifest_addl_url(int *len)
{
	char	**value;

	value = ai_get_manifest_values(AIM_IPS_PUBLISHER_URL, len);

	if (*len > 0) {
		return (value);
	}
	return (NULL);
}

/*
 * Retrieve an publisher name from the manifest using url value
 */
char *
ai_get_manifest_repo_publisher(char *url)
{
	char	**value;
	char	*publisher;
	int	len;
	char	tag[MAXPATHLEN];

	(void) snprintf(tag, sizeof (tag),
	    AIM_ADD_URL_PUBLISHER_NAME, url);
	value = ai_get_manifest_values(tag, &len);

	if (len > 0) {
		publisher = value[0];
		free(value);
		return (publisher);
	}
	return (NULL);
}

/*
 * Retrieve the URL for an IPS repo mirrors
 */
auto_mirror_repo_t *
ai_get_manifest_repo_mirrors(char *url)
{
	int			i, len = 0;
	char			**value;
	char			buf[MAXPATHLEN];
	auto_mirror_repo_t	*ptr, *tmp_ptr;
	auto_mirror_repo_t	*mirror = NULL;

	(void) snprintf(buf, sizeof (buf),
	    AIM_ADD_URL_PUBLISHER_MIRROR, url);
	value = ai_get_manifest_values(buf, &len);

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

	default_repo = NULL;

	/*
	 * Get the url of the default publisher
	 */
	current_url = ai_get_manifest_default_url(&num_url);
	if (current_url == NULL) {
		/*
		 * If the publisher wasn't specified in the manifest,
		 * provide a default value.
		 */
		current_url = AIM_FALLBACK_PUBLISHER_URL;
	}

	repo = calloc(sizeof (auto_repo_info_t), 1);
	if (repo == NULL) {
		return (NULL);
	}

	/*
	 * Save the value before calling another ai_get_manifest_*()
	 */
	default_url = strdup(current_url);
	p = ai_get_manifest_repo_publisher(default_url);
	if (p == NULL) {
		/*
		 * If the primary publisher URL is AIM_FALLBACK_PUBLISHER_URL
		 * and no name was specified, then provide a default value.
		 * For all other URLs, if a name is not specified for the
		 * publisher, then it is an error.
		 */
		if (strcasecmp(current_url, AIM_FALLBACK_PUBLISHER_URL) == 0)
			p = AIM_FALLBACK_PUBLISHER_NAME;
		else
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
	    ai_get_manifest_repo_mirrors(default_url);
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
	 * We start iterating through the urls at index 1
	 * instead of index 0, because the first url returned
	 * is the primary publisher.  All subsequent urls are
	 * secondary, or additional, publishers, which is what
	 * we want here.
	 * Allocate space and save the urls because the next
	 * call to ai_get_manifest_*() will overwrite them
	 */
	for (i = 1; i < num_url; i++) {
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
		p = ai_get_manifest_repo_publisher(repo->url);
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
		repo->mirror_repo = ai_get_manifest_repo_mirrors(repo->url);
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
		if (strstr(token, AUTO_PROPERTY_ROOTPASS) != NULL) {
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

	/*
	 * Tolerate unrecognized SMF properties, they might belong to SMF
	 * services which will process those properties later during first boot.
	 */

	if (*keyword == '\0') {
		return (AUTO_INSTALL_SUCCESS);
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
	FILE		*profile_fp;
	char		line[BUFSIZ];
	char		keyword[KEYWORD_SIZE];
	char		value[VALUE_SIZE];
	int		ret;
	boolean_t	is_legacy_sc_manifest = B_FALSE;
	char		cmd[MAX_SHELLCMD_LEN];

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
			} else if (keyword[0] == '\0') {
				/*
				 * Tolerate unrecognized SMF properties, they
				 * might belong to SMF services which will
				 * process those properties later during
				 * first boot.
				 */

				continue;
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
			if (strcmp(keyword,
			    AUTO_PROPERTY_ROOTPASS) == 0) {
				is_legacy_sc_manifest = B_TRUE;
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_TIMEZONE) == 0) {
				sp->timezone = strdup(value);
			} else if (strcmp(keyword,
			    AUTO_PROPERTY_HOSTNAME) == 0) {
				sp->hostname = strdup(value);
			} else {
				auto_debug_print(AUTO_DBGLVL_ERR,
				    "unrecognized SC manifest keyword "
				    "%s ignored\n", keyword);
			}
		}
	}
	fclose(profile_fp);

	/*
	 * If System Configuration has legacy format, convert it to new format
	 */
	if (is_legacy_sc_manifest) {
		auto_log_print(gettext(
		    "Legacy System Configuration manifest provided, an attempt"
		    " will be made to convert it to the latest format.\n"));
		auto_log_print(gettext(
		    "Please be aware that support for the legacy format can be "
		    "removed at any time without prior notice.\n"));
		auto_log_print(gettext(
		    "Thus it is strongly recommended that the latest format "
		    "of the System Configuration manifest be used.\n"));

		/* Create copy of legacy manifest for purposes of conversion */
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/bin/cp %s %s.legacy 2>&1 1>/dev/null",
		    profile_file, profile_file);

		ret = ai_exec_cmd(cmd);

		if (ret != 0) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Could not create a copy of the legacy System"
			    " Configuration manifest, err=%d.\n", ret);

			return (AUTO_INSTALL_FAILURE);
		}

		/* Now convert SC manifest */
		(void) snprintf(cmd, sizeof (cmd),
		    SC_CONVERSION_SCRIPT" %s.legacy %s 2>&1 1>/dev/null",
		    profile_file, profile_file);

		ret = ai_exec_cmd(cmd);

		if (ret != 0) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "Could not convert the legacy System Configuration"
			    " manifest to the new format, err=%d.\n", ret);

			return (AUTO_INSTALL_FAILURE);
		}
	} else {
		auto_log_print(gettext(
		    "Detected the latest format of System Configuration"
		    " manifest.\n"));
	}

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
