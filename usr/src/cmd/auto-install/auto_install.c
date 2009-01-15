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

#include <alloca.h>
#include <fcntl.h>
#include <stdio.h>
#include <errno.h>
#include <stdarg.h>
#include <stdlib.h>
#include <strings.h>
#include <unistd.h>
#include <libnvpair.h>
#include <locale.h>
#include <sys/param.h>
#include <sys/types.h>

#include "auto_install.h"
#include <ls_api.h>

static  boolean_t install_done = B_FALSE;
static	boolean_t install_failed = B_FALSE;

int	install_error = 0;
install_params	params;

void	auto_update_progress(om_callback_info_t *, uintptr_t);
static boolean_t convert_to_sectors(auto_size_units_t,
    uint64_t, uint64_t *);

static void
usage()
{
	fprintf(stderr, "usage: auto-install -d <diskname> | -p <profile>\n");
}

/*
 * auto_debug_print()
 * Description:	Posts debug message
 */
void
auto_debug_print(ls_dbglvl_t dbg_lvl, char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	/*LINTED*/
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("AI", dbg_lvl, buf);
	va_end(ap);
}

/*
 * auto_log_print()
 * Description:	Posts log message
 */
void
auto_log_print(char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1] = "";

	va_start(ap, fmt);
	/*LINTED*/
	(void) vsprintf(buf, fmt, ap);
	fprintf(stderr, buf);
	(void) ls_write_log_message("AI", buf);
	va_end(ap);
}

/*
 * Callback that gets passed to om_perform_install.
 *
 * Sets the install_done variable when an install is
 * finished. If an install fails, it sets the install_failed
 * variable and also sets the install_error variable to
 * indicate the specific reason for the failure.
 */
void
auto_update_progress(om_callback_info_t *cb_data, uintptr_t app_data)
{
	if (cb_data->curr_milestone == -1) {
		install_error = cb_data->percentage_done;
		install_failed = B_TRUE;
	}

	if (cb_data->curr_milestone == OM_SOFTWARE_UPDATE &&
	    cb_data->percentage_done == 100)
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Transfer completed\n");

	if (cb_data->curr_milestone == OM_POSTINSTAL_TASKS &&
	    cb_data->percentage_done == 100)
		install_done = B_TRUE;
}

/*
 * This function splits the file that is passed to AI manifest and SC manifest
 *
 * Input:
 * char *input_file	- The file contains AI manifest (relax NG schema) and
 *			  SC manifest (enhanced SMF profile DTD schema)
 * Output:
 * char *ai_manifest	- Writes the AI manifest portion of the input on this
 *			  file name
 * char *sc_manifest	- Writes the SC manifest portion of the input on this
 *			  file name
 * Returns:
 * AUTO_VALID_MANIFEST (0)	- If the operation is successful
 * AUTO_INVALID_MANIFEST (-1)	- If the operation fails
 */
static int
auto_split_manifests(char *input_file, char *ai_manifest, char *sc_manifest)
{
	FILE		*ifp;	/* Input file */
	FILE		*aifp;	/* AI manifest */
	FILE		*scfp;	/* SC manifest */
	boolean_t	writing_ai_manifest = B_FALSE;
	boolean_t	writing_sc_manifest = B_FALSE;
	char		buf[BUFSIZ];


	if (input_file == NULL || ai_manifest == NULL || sc_manifest == NULL) {
		return (AUTO_INVALID_MANIFEST);
	}

	if (access(input_file, F_OK) != 0) {
		return (AUTO_INVALID_MANIFEST);
	}

	/*
	 * Open the input file in read-only mode
	 */
	ifp = fopen(input_file, "r");
	if (ifp == NULL) {
		auto_log_print(gettext("Cannot open AI manifest %s\n"),
		    input_file);
		return (AUTO_INVALID_MANIFEST);
	}

	/*
	 * Open the output files in write mode
	 */
	aifp = fopen(ai_manifest, "w");
	if (aifp == NULL) {
		auto_log_print(gettext("Cannot open AI manifest %s\n"),
		    ai_manifest);
		return (AUTO_INVALID_MANIFEST);
	}

	scfp = fopen(sc_manifest, "w");
	if (scfp == NULL) {
		auto_log_print(gettext("Cannot open SC manifest %s\n"),
		    sc_manifest);
		return (AUTO_INVALID_MANIFEST);
	}

	while (fgets(buf, sizeof (buf), ifp) != NULL) {

		/*
		 * The AI manifest begins with <ai_manifest and
		 * ends with the line "</ai_manifest>"
		 * The SC manifest begins with <?xml version='1.0'?> and
		 * ends with the line "</service_bundle>"
		 *
		 */
		if (strstr(buf, AI_MANIFEST_BEGIN_MARKER) != NULL) {
			writing_ai_manifest = B_TRUE;
		}
		if (strstr(buf, SC_MANIFEST_BEGIN_MARKER) != NULL) {
			writing_sc_manifest = B_TRUE;
		}
		if (writing_ai_manifest) {
			if (strstr(buf, AI_MANIFEST_END_MARKER) != NULL) {
				writing_ai_manifest = B_FALSE;
			}
			fputs(buf, aifp);
			continue;
		} else if (writing_sc_manifest) {
			if (strstr(buf, SC_MANIFEST_END_MARKER) != NULL) {
				writing_sc_manifest = B_FALSE;
			}
			fputs(buf, scfp);
			continue;
		}
	}

	fclose(ifp);
	fclose(aifp);
	fclose(scfp);
	return (AUTO_VALID_MANIFEST);
}

/*
 * Create a file that contains the list
 * of packages to be installed. If 'hardcode'
 * is set to B_TRUE, hardcode the list of
 * packages to be added to the package list file.
 *
 * Returns:
 *	AUTO_INSTALL_SUCCESS for success
 *	AUTO_INSTALL_FAILURE for failure
 */
static int
create_package_list_file(boolean_t hardcode)
{
	FILE *fp;
	char **package_list;
	int i, num_packages = 0;
	int retval = AUTO_INSTALL_FAILURE;

	if ((fp = fopen(AUTO_PKG_LIST, "wb")) == NULL)
		return (retval);

	if (hardcode) {
		if (fputs("SUNWcsd", fp) < strlen("SUNWcsd"))
			goto errorout;
		if (fputs("SUNWcs", fp) < strlen("SUNWcs"))
			goto errorout;
		if (fputs("slim_install", fp) < strlen("slim_install"))
			goto errorout;
		if (fputs("entire", fp) < strlen("entire"))
			goto errorout;

		(void) fclose(fp);
		return (AUTO_INSTALL_SUCCESS);
	}

	package_list = ai_get_manifest_packages(&num_packages);

	if (num_packages <= 0)
		goto errorout;

	assert(package_list != NULL);

	auto_log_print(gettext("list of packages to be installed is: \n"));
	for (i = 0; i < num_packages; i++) {
		if (fputs(package_list[i], fp) < strlen(package_list[i]))
			goto errorout;
		if (fputs("\n", fp) < strlen("\n"))
			goto errorout;
		auto_log_print("%s\n", package_list[i]);
	}

	retval = AUTO_INSTALL_SUCCESS;

errorout:
	(void) fclose(fp);
	return (retval);
}

/*
 * Create/delete/preserve vtoc slices as specified
 * in the manifest
 */
static int
auto_modify_target_slices(auto_slice_info *asi, uint8_t install_slice_id)
{
	for (; asi->slice_action[0] != '\0'; asi++) {
		uint64_t slice_size_sec;

		auto_debug_print(AUTO_DBGLVL_INFO,
		    "slice action %s, size=%lld units=%s\n",
		    asi->slice_action, asi->slice_size,
		    CONVERT_UNITS_TO_TEXT(asi->slice_size_units));

		if (!convert_to_sectors(asi->slice_size_units,
		    asi->slice_size, &slice_size_sec)) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "conversion failure from %lld %s to sectors\n",
			    asi->slice_size,
			    CONVERT_UNITS_TO_TEXT(asi->slice_size_units));
			return (AUTO_INSTALL_FAILURE);
		}
		if (strcmp(asi->slice_action, "create") == 0) {
			if (!om_create_slice(asi->slice_number,
			    slice_size_sec,
			    asi->slice_number == install_slice_id))
				return (AUTO_INSTALL_FAILURE);
		} else if (strcmp(asi->slice_action, "delete") == 0) {
			if (!om_delete_slice(asi->slice_number))
				return (AUTO_INSTALL_FAILURE);
		} else if (strcmp(asi->slice_action, "preserve") == 0) {
			if (!om_preserve_slice(asi->slice_number))
				return (AUTO_INSTALL_FAILURE);
		}
	}
	return (AUTO_INSTALL_SUCCESS);
}

/*
 * convert value to sectors given basic unit size
 * TODO uint64_t overflow check
 */

static boolean_t
convert_to_sectors(auto_size_units_t units, uint64_t src,
    uint64_t *psecs)
{
	if (psecs == NULL)
		return (B_FALSE);
	switch (units) {
		case AI_SIZE_UNITS_SECTORS:
			*psecs = src;
			break;
		case AI_SIZE_UNITS_MEGABYTES:
			*psecs = src*2048;
			break;
		case AI_SIZE_UNITS_GIGABYTES:
			*psecs = src*2048*1024; /* sec=>MB=>GB */
			break;
		case AI_SIZE_UNITS_TERABYTES:
			*psecs = src*2048*1024*1024; /* sec=>MB=>GB=>TB */
			break;
		default:
			return (B_FALSE);
	}
	if (units != AI_SIZE_UNITS_SECTORS)
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "converting from %lld %s to %lld sectors\n",
		    src, CONVERT_UNITS_TO_TEXT(units), *psecs);
	return (B_TRUE);
}

#ifndef	__sparc
/*
 * Create/delete/preserve fdisk partitions as specifed
 * in the manifest
 */
static int
auto_modify_target_partitions(auto_partition_info *api)
{
	for (; api->partition_action[0] != '\0'; api++) {
		uint64_t partition_size_sec;

		auto_debug_print(AUTO_DBGLVL_INFO,
		    "partition action %s, size=%lld units=%s\n",
		    api->partition_action, api->partition_size,
		    CONVERT_UNITS_TO_TEXT(api->partition_size_units));

		if (!convert_to_sectors(api->partition_size_units,
		    api->partition_size, &partition_size_sec)) {
			auto_debug_print(AUTO_DBGLVL_ERR,
			    "conversion failure from %lld %s to sectors\n",
			    api->partition_size,
			    CONVERT_UNITS_TO_TEXT(api->partition_size_units));
			return (AUTO_INSTALL_FAILURE);
		}
		if (strcmp(api->partition_action, "create") == 0) {
			if (!om_create_partition(api->partition_start_sector,
			    partition_size_sec, B_FALSE))
				return (AUTO_INSTALL_FAILURE);
		} else if (strcmp(api->partition_action, "delete") == 0) {
			if (!om_delete_partition(api->partition_start_sector,
			    partition_size_sec))
				return (AUTO_INSTALL_FAILURE);
		}
	}
	return (AUTO_INSTALL_SUCCESS);
}
#endif

/*
 * Given a disk description specified as an
 * argument, select a disk that matches the
 * specification.
 *
 * If a diskname is specified, return that.
 * Otherwise, return a disk that matches the
 * specified type, vendor and size
 */
static char *
auto_select_install_target(auto_disk_info adi)
{
	char *diskname = NULL;

	if (adi.diskname != NULL)
		diskname = adi.diskname;

	/*
	 * XXX the target_device_overwrite_root_zfs_pool attribute
	 * isn't supported right now -- we ignore it
	 */
#ifndef	__sparc
	/*
	 * Should an existing Solaris fdisk partition be used
	 * on the selected target disk?
	 *
	 * If not, then we want to create a Solaris fdisk
	 * partitioning encompassing the entire disk
	 */
	if (strncasecmp(adi.diskusepart, "true",
	    sizeof (adi.diskusepart)) == 0)
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "use existing fdisk partition set to true\n");
#endif
	if (auto_validate_target(&diskname, &params, &adi) !=
	    AUTO_TD_SUCCESS) {
		auto_log_print(gettext("Target validation failed\n"));
		return (NULL);
	}

	return (diskname);
}

/*
 * Install the target based on the criteria specified in
 * the ai_manifest.xml.
 *
 * NOTE: ai_validate_manifest() MUST have been called prior
 * to calling this function.
 *
 * RETURNS:
 *	AUTO_INSTALL_SUCCESS on success
 *	AUTO_INSTALL_FAILURE on failure
 */
static int
install_from_manifest()
{
	char *diskname = NULL, *p = NULL;
	char *url = NULL, *authname = NULL;
	char *proxy = NULL;
	auto_disk_info adi;
#ifndef	__sparc
	auto_partition_info *api;
#endif
	auto_slice_info *asi;
	auto_sc_params asp;
	nvlist_t *install_attr, **transfer_attr;
	int status;
	uint8_t install_slice_id;

	/*
	 * Start out by getting the install target and
	 * validating that target
	 */
	(void) bzero(&adi, sizeof (auto_disk_info));
	ai_get_manifest_disk_info(&adi);
	/*
	 * grab target slice number
	 */
	install_slice_id = adi.install_slice_number;

	p = auto_select_install_target(adi);
	if (p == NULL) {
		auto_log_print(gettext("ai target device not found\n"));
		return (AUTO_INSTALL_FAILURE);
	}
	diskname = strdup(p);
	auto_log_print(gettext("diskname selected for installation is %s\n"),
	    diskname);
#ifndef	__sparc
	/*
	 * Configure the partitions as specified in the
	 * manifest
	 */
	api = ai_get_manifest_partition_info();
	if (api == NULL)
		auto_log_print(gettext("no manifest partition "
		    "information found\n"));
	else {
		if (auto_modify_target_partitions(api) !=
		    AUTO_INSTALL_SUCCESS) {
			free(api);
			auto_log_print(gettext("failed to modify partition(s) "
			    "specified in the manifest\n"));
			return (AUTO_INSTALL_FAILURE);
		}

		/* we're done with futzing with partitions, free the memory */
		free(api);
	}

	/*
	 * if no partition exists and no partitions were specified in manifest,
	 *	there is no info about partitions for TI,
	 *	so create info table from scratch
	 */
	om_create_target_partition_info_if_absent();

	/* finalize modified partition table for TI to apply to target disk */
	if (!om_finalize_fdisk_info_for_TI()) {
		auto_log_print(gettext("failed to finalize fdisk info\n"));
		return (AUTO_INSTALL_FAILURE);
	}
#endif
	/*
	 * Configure the vtoc slices as specified in the
	 * manifest
	 */
	asi = ai_get_manifest_slice_info();
	if (asi == NULL)
		auto_log_print(gettext(
		    "no manifest slice information found\n"));
	else {
		if (auto_modify_target_slices(asi, install_slice_id) !=
		    AUTO_INSTALL_SUCCESS) {
			free(asi);
			auto_log_print(gettext(
			    "failed to modify slice(s) specified "
			    "in the manifest\n"));
			return (AUTO_INSTALL_FAILURE);
		}

		/* we're done with futzing with slices, free the memory */
		free(asi);
	}

	/* finalize modified vtoc for TI to apply to target disk partition */
	if (!om_finalize_vtoc_for_TI(install_slice_id)) {
		auto_log_print(gettext("failed to finalize vtoc info\n"));
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_alloc(&install_attr, NV_UNIQUE_NAME, 0) != 0) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint8(install_attr, OM_ATTR_INSTALL_TYPE,
	    OM_INITIAL_INSTALL) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_INSTALL_TYPE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DISK_NAME,
	    diskname) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_DISK_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}
	free(diskname);

	/*
	 * Parse the SC (system configuration manifest)
	 */
	if (auto_parse_sc_manifest(SC_MANIFEST_FILE, &asp) !=
	    AUTO_INSTALL_SUCCESS) {
		nvlist_free(install_attr);
		auto_log_print(gettext("Failed to parse the system "
		    "configuration manifest\n"));
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_ROOT_PASSWORD,
	    strdup(om_encrypt_passwd(asp.rootpass, "root"))) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_ROOT_PASSWORD failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_NAME,
	    asp.userdesc) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_USER_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_PASSWORD,
	    strdup(om_encrypt_passwd(asp.userpass, asp.username))) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_USER_PASSWORD failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_LOGIN_NAME,
	    asp.username) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_LOGIN_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_HOST_NAME,
	    "opensolaris") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_HOST_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_TIMEZONE_INFO,
	    asp.timezone) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_DEFAULT_LOCALE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DEFAULT_LOCALE,
	    "C") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_DEFAULT_LOCALE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	transfer_attr = malloc(sizeof (nvlist_t *) * 2);

	if (nvlist_alloc(&transfer_attr[0], NV_UNIQUE_NAME, 0) != 0) {
		free(transfer_attr);
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[0], TM_ATTR_MECHANISM,
	    TM_PERFORM_IPS) != 0) {
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_ATTR_MECHANISM failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[0], TM_IPS_ACTION,
	    TM_IPS_INIT) != 0) {
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TMP_IPS_ACTION failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[0], TM_IPS_INIT_MNTPT,
	    INSTALLED_ROOT_DIR) != 0) {
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_INIT_MNTPT failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	p = ai_get_manifest_ipsrepo_url();
	if (p == NULL) {
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_log_print(gettext("IPS default authority url not "
		    "specified\n"));
		return (AUTO_INSTALL_FAILURE);
	}
	url = strdup(p);

	p = ai_get_manifest_http_proxy();
	if (p != NULL) {
		int proxy_len;
		proxy_len = strlen("http_proxy=") + strlen(p) + 1;
		proxy = malloc(proxy_len);
		snprintf(proxy, proxy_len, "%s%s", "http_proxy=", p);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting http_proxy environment variable to %s\n", p);
		if (putenv(proxy)) {
			auto_debug_print(AUTO_DBGLVL_INFO,
			    "Setting of http_proxy environment variable failed:"
			    " %s\n", strerror(errno));
			return (AUTO_INSTALL_FAILURE);
		}
	}

	if (nvlist_add_string(transfer_attr[0], TM_IPS_PKG_URL, url) != 0) {
		free(url);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKG_URL failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	p = ai_get_manifest_ipsrepo_authname();
	if (p == NULL) {
		free(url);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_log_print(gettext("IPS default authority authname not "
		    "specified\n"));
		return (AUTO_INSTALL_FAILURE);
	}
	authname = strdup(p);
	auto_log_print(gettext("installation will be performed "
	    "from %s (%s)\n"), url, authname);

	if (nvlist_add_string(transfer_attr[0], TM_IPS_PKG_AUTH, authname)
	    != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKG_AUTH failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	/*
	 * We need to ask IPS to force creating IPS image, since when
	 * default path is chosen, IPS refuses to create the image.
	 * The reason is that even if we created empty BE to be
	 * populated by IPS, it contains ZFS shared and non-shared
	 * datasets mounted on appropriate mount points. And
	 * IPS complains in the case the target mount point contains
	 * subdirectories.
	 */

	if (nvlist_add_boolean_value(transfer_attr[0],
	    TM_IPS_IMAGE_CREATE_FORCE, B_TRUE) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_IMAGE_CREATE_FORCE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_alloc(&transfer_attr[1], NV_UNIQUE_NAME, 0) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[1], TM_ATTR_MECHANISM,
	    TM_PERFORM_IPS) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_ATTR_MECHANISM failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[1], TM_IPS_ACTION,
	    TM_IPS_RETRIEVE) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TMP_IPS_ACTION failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[1], TM_IPS_INIT_MNTPT,
	    INSTALLED_ROOT_DIR) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_INIT_MNTPT failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	/*
	 * list out the list of packages to be installed
	 * from the manifest and add it into a file
	 */
	if (create_package_list_file(B_FALSE) != AUTO_INSTALL_SUCCESS) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_log_print(gettext("Failed to create a file with list "
		    "of packages to be installed\n"));
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[1], TM_IPS_PKGS,
	    AUTO_PKG_LIST) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKGS failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_nvlist_array(install_attr, OM_ATTR_TRANSFER,
	    transfer_attr, 2) != 0) {
		free(url);
		free(authname);
		free(transfer_attr);
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_TRANSFER failed\n");
		return (AUTO_INSTALL_FAILURE);
	}
	status = om_perform_install(install_attr, auto_update_progress);

	while (!install_done && !install_failed)
		sleep(10);

	free(url);
	free(authname);
	free(transfer_attr);
	nvlist_free(install_attr);
	nvlist_free(transfer_attr[0]);
	nvlist_free(transfer_attr[1]);

	if (install_failed) {
		auto_log_print(gettext("om_perform_install failed with "
		    "error %d\n"), install_error);
		return (AUTO_INSTALL_FAILURE);
	}
	return (status);
}

/*
 * Install the target based on the specified diskname
 * or if no diskname is specified, install it based on
 * the criteria specified in the ai_manifest.xml.
 *
 * Returns
 *	AUTO_INSTALL_SUCCESS on a successful install
 *	AUTO_INSTALL_FAILURE on a failed install
 */
static int
auto_perform_install(char *diskname)
{
	nvlist_t	*install_attr, *transfer_attr[2];
	int 		status;

	if (*diskname == '\0')
		return (install_from_manifest());

	/*
	 * We're installing on the specified diskname
	 * Since this is usually called from a test
	 * program, we hardcode the various system
	 * configuration parameters
	 */

	/*
	 * Initiate target discovery
	 */
	if (auto_validate_target(&diskname, &params, NULL) != 0) {
		auto_log_print(gettext("Error: Target disk name %s is "
		    "not valid\n"), diskname);
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_alloc(&install_attr, NV_UNIQUE_NAME, 0) != 0) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint8(install_attr, OM_ATTR_INSTALL_TYPE,
	    OM_INITIAL_INSTALL) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_INSTALL_TYPE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DISK_NAME,
	    diskname) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_DISK_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_ROOT_PASSWORD,
	    strdup(om_encrypt_passwd("opensolaris", "root"))) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_ROOT_PASSWORD failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_NAME,
	    "fool") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_USER_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_PASSWORD,
	    strdup(om_encrypt_passwd("ass", "fool"))) != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_USER_PASSWORD failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_LOGIN_NAME,
	    "fool") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_LOGIN_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_HOST_NAME,
	    "opensolaris") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_HOST_NAME failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DEFAULT_LOCALE,
	    "C") != 0) {
		nvlist_free(install_attr);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_DEFAULT_LOCALE failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_alloc(&transfer_attr[0], NV_UNIQUE_NAME, 0) != 0) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[0], TM_ATTR_MECHANISM,
	    TM_PERFORM_IPS) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_ATTR_MECHANISM failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[0], TM_IPS_ACTION,
	    TM_IPS_INIT) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TMP_IPS_ACTION failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[0], TM_IPS_INIT_MNTPT,
	    INSTALLED_ROOT_DIR) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_INIT_MNTPT failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[0], TM_IPS_PKG_URL,
	    "http://ipkg.sfbay:10004") != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKG_URL failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[0], TM_IPS_PKG_AUTH,
	    "ipkg.sfbay") != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKG_AUTH failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_alloc(&transfer_attr[1], NV_UNIQUE_NAME, 0) != 0) {
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "nvlist allocation failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[1], TM_ATTR_MECHANISM,
	    TM_PERFORM_IPS) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_ATTR_MECHANISM failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_uint32(transfer_attr[1], TM_IPS_ACTION,
	    TM_IPS_RETRIEVE) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TMP_IPS_ACTION failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[1], TM_IPS_INIT_MNTPT,
	    INSTALLED_ROOT_DIR) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_INIT_MNTPT failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (create_package_list_file(B_TRUE) != AUTO_INSTALL_SUCCESS) {
		auto_log_print(gettext("Failed to create a file with list "
		    "of packages to be installed\n"));
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_string(transfer_attr[1], TM_IPS_PKGS,
	    AUTO_PKG_LIST) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of TM_IPS_PKG_URL failed\n");
		return (AUTO_INSTALL_FAILURE);
	}

	if (nvlist_add_nvlist_array(install_attr, OM_ATTR_TRANSFER,
	    transfer_attr, 2) != 0) {
		nvlist_free(install_attr);
		nvlist_free(transfer_attr[0]);
		nvlist_free(transfer_attr[1]);
		auto_debug_print(AUTO_DBGLVL_INFO,
		    "Setting of OM_ATTR_TRANSFER failed\n");
		return (AUTO_INSTALL_FAILURE);
	}
	status = om_perform_install(install_attr, auto_update_progress);

	while (!install_done && !install_failed)
		sleep(10);

	nvlist_free(install_attr);
	nvlist_free(transfer_attr[0]);
	nvlist_free(transfer_attr[1]);

	if (install_failed) {
		auto_log_print(gettext("om_perform_install failed with "
		    "error %d\n"), install_error);
		return (AUTO_INSTALL_FAILURE);
	}

	return (status);
}

/*
 * Function:	auto_get_disk_name_from_slice
 * Description: Convert a conventional disk name into the internal canonical
 *		form. Remove the trailing index reference. The return status
 *		reflects whether or not the 'src' name is valid.
 *
 *				src			 dst
 *			---------------------------------------
 *			[/dev/rdsk/]c0t0d0s0	->	c0t0d0
 *			[/dev/rdsk/]c0t0d0p0	->	c0t0d0
 *			[/dev/rdsk/]c0d0s0	->	c0d0
 *			[/dev/rdsk/]c0d0p0	->	c0d0
 *
 * Scope:	public
 * Parameters:	dst	- used to retrieve cannonical form of drive name
 *			  ("" if not valid)
 *		src	- name of drive to be processed (see table above)
 * Return:	 0	- valid disk name
 *		-1	- invalid disk name
 */
static void
auto_get_disk_name_from_slice(char *dst, char *src)
{
	char		name[MAXPATHLEN];
	char		*cp;

	*dst = '\0';

	(void) strcpy(name, src);
	/*
	 * The slice could be like s2 or s10
	 */
	cp = name + strlen(name) - 3;
	if (*cp) {
		if (*cp == 'p' || *cp == 's') {
			*cp = '\0';
		} else {
			cp++;
			if (*cp == 'p' || *cp == 's') {
				*cp = '\0';
			}
		}
	}

	/* It could be full pathname like /dev/dsk/disk_name */
	if ((cp = strrchr(name, '/')) != NULL) {
		cp++;
		(void) strcpy(dst, cp);
	} else {
		/* Just the disk name is provided, so return the name */
		(void) strcpy(dst, name);
	}
}

int
main(int argc, char **argv)
{
	int	opt;
	extern char *optarg;
	char	profile[MAXNAMELEN];
	char	diskname[MAXNAMELEN];
	char	slicename[MAXNAMELEN];

	(void) setlocale(LC_ALL, "");
	(void) textdomain(TEXT_DOMAIN);

	profile[0] = '\0';
	slicename[0] = '\0';
	while ((opt = getopt(argc, argv, "p:d:")) != -1) {
		switch (opt) {
		/*
		 * profile is provided
		 */
		case 'p':
			(void) strlcpy(profile, optarg, sizeof (profile));
			break;
		case 'd':
			(void) strlcpy(slicename, optarg, sizeof (slicename));
			break;
		}
	}

	if (profile[0] == '\0' && slicename[0] == '\0') {
		usage();
		exit(-1);
	}

	ls_init(NULL);

	if (profile[0] != '\0') {
		/*
		 * We are passed in a combined AI and SC manifest.
		 * Before we doing anything meaningful, they must
		 * be separated since they're in two different
		 * formats
		 *
		 * The AI manifest is in RelaxNG format whereas the
		 * SC manifest is in a DTD format.
		 */
		if (auto_split_manifests(profile, AI_MANIFEST_FILE,
		    SC_MANIFEST_FILE) != AUTO_VALID_MANIFEST) {
			auto_log_print(gettext("Auto install failed. Invalid "
			    "manifest file %s specified\n"), profile);
			exit(-1);
		}

		/*
		 * Validate the AI manifest. If it validates, set
		 * it up in an in-memory tree so searches can be
		 * done on it in the future to retrieve the values
		 */
		if (ai_validate_and_setup_manifest(AI_MANIFEST_FILE) ==
		    AUTO_VALID_MANIFEST) {
			auto_log_print(gettext("%s is a valid manifest\n"),
			    profile);
		} else {
			auto_log_print(gettext("Auto install failed. Invalid "
			    "manifest %s specified\n"), profile);
			exit(-1);
		}
		diskname[0] = '\0';
	}

	if (slicename[0] != '\0') {
		auto_get_disk_name_from_slice(diskname, slicename);
	}

	if (auto_perform_install(diskname) != AUTO_INSTALL_SUCCESS) {
		(void) ai_teardown_manifest_state();
		auto_log_print(gettext("Auto install failed\n"));
		exit(-1);
	}

	(void) ai_teardown_manifest_state();

	auto_log_print(gettext("Auto install succeeded. You may wish to "
	    "reboot the system at this time\n"));
	exit(0);

}
