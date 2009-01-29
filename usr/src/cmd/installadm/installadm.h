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

#ifndef	_INSTALLADM_H
#define	_INSTALLADM_H

#define	INSTALLADM_SUCCESS 	0
#define	INSTALLADM_FAILURE 	-1
#define	INSTALLADM_VERSION	"1.0"
#define	AI_SERVICE_DIR_PATH	"/var/ai/"
#define	AI_NETIMAGE_REQUIRED_FILE "solaris.zlib"
#define	SETUP_IMAGE_SCRIPT	"/usr/lib/installadm/setup-image"
#define	IMAGE_CREATE		"create"
#define	IMAGE_DELETE		"delete"

#define	AIWEBSERVER		"aiwebserver"
#define	SETUP_SERVICE_SCRIPT	"/usr/lib/installadm/setup-service"
#define	SERVICE_LOOKUP		"lookup"
#define	SERVICE_REGISTER	"register"
#define	SERVICE_REMOVE		"remove"
#define	SERVICE_LIST		"list"

#define	MANIFEST_REMOVE_SCRIPT	"/usr/lib/installadm/delete-manifest"
#define	MANIFEST_MODIFY_SCRIPT	"/usr/lib/installadm/publish-manifest"
#define	MANIFEST_LIST_SCRIPT	"/usr/lib/installadm/list-manifests"

#define	CREATE_CLIENT_SCRIPT	"/usr/lib/installadm/create-client"
#define	DELETE_CLIENT_SCRIPT	"/usr/lib/installadm/delete-client"

#define	SETUP_DHCP_SCRIPT	"/usr/lib/installadm/setup-dhcp"
#define	DHCP_SERVER		"server"
#define	DHCP_CLIENT		"client"
#define	DHCP_MACRO		"macro"
#define	DHCP_ASSIGN		"assign"

#define	SETUP_TFTP_LINKS_SCRIPT	"/usr/lib/installadm/setup-tftp-links"
#define	TFTP_SERVER		"server"

#define	SETUP_SPARC_SCRIPT	"/usr/lib/installadm/setup-sparc"
#define	SPARC_SERVER		"server"
#define HTTP_PORT		"5555"
#define	WANBOOTCGI		"cgi-bin/wanboot-cgi"

#define	AI_SERVICE_DATA		"/var/installadm/service_data"
#define	LOCALHOST		"127.0.0.1"
/*
 * For each service, we start a webserver at a port and register the port with
 * the service. We start looking at the port number from 46501
 */
#define	START_WEB_SERVER_PORT	46501

#define	MAX_SERVICE_LINE_LEN	1024
#define	DATALEN			256
#define	LOCAL_DOMAIN		"local"
#define	INSTALL_TYPE		"_OSInstall._tcp"
#define	DEFAULT_SERVICE		"_default"

#define	TEXT_DOMAIN		"SUNW_INSTALL_INSTALLADM"
#define	INSTALLADMSTR(x)	dgettext(TEXT_DOMAIN, x)

#define	MSG_INSTALLADM_USAGE	INSTALLADMSTR(\
	"usage:  installadm <subcommand> <args> ...\n")
#define	MSG_UNKNOWN_SUBCOMMAND	INSTALLADMSTR(\
	"%s: unknown subcommand '%s'.\n")
#define	MSG_UNKNOWN_HELPSUBCOMMAND	INSTALLADMSTR(\
	"%s %s: unknown subcommand '%s'.\n")
#define	MSG_MISSING_OPTIONS	INSTALLADMSTR(\
	"%s: missing one or more required options.\nusage:\n")
#define	MSG_INSTALLADM_VERSION	INSTALLADMSTR(\
	"%s version \"%s\"\n")
#define	MSG_OPTION_NOHELP	INSTALLADMSTR(\
	"%s %s: No help available for subcommand '%s'\n")
#define	MSG_OPTION_VALUE_MISSING	INSTALLADMSTR(\
	"option '-%c' requires a value\nusage: %s\n")
#define	MSG_SUBCOMMAND_FAILED	INSTALLADMSTR(\
	"Failure running subcommand %s.\n")
#define	MSG_OPTION_UNRECOGNIZED	INSTALLADMSTR(\
	"unrecognized option '-%c'\nusage: %s.\n")
#define	MSG_REMOTE_DHCP_SETUP	INSTALLADMSTR(\
	"Remote DHCP setup is not supported.\n")
#define	MSG_TARGET_NOT_EMPTY	INSTALLADMSTR(\
	"Target directory is not empty.\n")
#define	MSG_VALID_IMAGE_ERR	INSTALLADMSTR(\
	"There is a valid image at (%s)." \
	" Please delete the image and try again.\n")
#define	MSG_MKDIR_FAIL	INSTALLADMSTR(\
	"Creating directory (%s) failed.\n")
#define	MSG_DIRECTORY_ACCESS_ERR	INSTALLADMSTR(\
	"Cannot access directory %s, error = %d.\n")
#define	MSG_CREATE_IMAGE_ERR	INSTALLADMSTR(\
	"Create image failed.\n")
#define	MSG_UNABLE_TO_DETERMINE_ARCH	INSTALLADMSTR(\
	"Unable to determine OpenSolaris install image type.\n")
#define	MSG_REGISTER_SERVICE_FAIL	INSTALLADMSTR(\
	"Failed to register Install Service %s.\n")
#define	MSG_LIST_SERVICE_FAIL	INSTALLADMSTR(\
	"Failed to list Install Services.\n")
#define	MSG_SERVICE_DOESNT_EXIST	INSTALLADMSTR(\
	"The specified service does not exist: %s\n")
#define	MSG_SERVICE_PROP_FAIL	INSTALLADMSTR(\
	"Failed to get Install Service properties.\n")
#define	MSG_CREATE_DHCP_SERVER_ERR	INSTALLADMSTR(\
	"Failed to setup DHCP server.\n")
#define	MSG_CREATE_DHCP_MACRO_ERR	INSTALLADMSTR(\
	"Failed to setup DHCP macro.\n")
#define	MSG_GET_HOSTNAME_FAIL	INSTALLADMSTR(\
	"Failed to get the hostname of the server.\n")
#define	MSG_ASSIGN_DHCP_MACRO_ERR	INSTALLADMSTR(\
	"Failed to assign DHCP macro to IP address. Please assign manually.\n")
#define	MSG_CREATE_TFTPBOOT_FAIL	INSTALLADMSTR(\
	"Failed to setup the TFTP bootfile.\n")
#define	MSG_SETUP_SPARC_FAIL	INSTALLADMSTR(\
	"Failed to setup the SPARC configuration file.\n")
#define	MSG_REMOVE_SERVICE_FAIL		INSTALLADMSTR(\
	"Failed to delete Install Service %s.\n")
#define	MSG_SERVICE_DATA_FILE_FAIL	INSTALLADMSTR(\
	"Failed to open service data file %s.\n")
#define	MSG_DELETE_IMAGE_FAIL	INSTALLADMSTR(\
	"Delete image at %s failed.\n")
#define	MSG_CANNOT_FIND_PORT	INSTALLADMSTR(\
	"Cannot find a free port to start the web server.\n")

#endif /* _INSTALLADM_H */
