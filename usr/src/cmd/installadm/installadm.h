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
 * Copyright (c) 2008, 2011, Oracle and/or its affiliates. All rights reserved.
 */

#ifndef	_INSTALLADM_H
#define	_INSTALLADM_H

#include <libaiscf.h>

#define	INSTALLADM_SUCCESS 	0
#define	INSTALLADM_FAILURE 	-1

#define	AI_NETIMAGE_REQUIRED_FILE "solaris.zlib"
#define	SETUP_IMAGE_SCRIPT	"/usr/lib/installadm/setup-image"
#define	IMAGE_CREATE		"create"
#define	CHECK_IMAGE_VERSION	"check_image_version"

#define	AIWEBSERVER		"aiwebserver"
#define	SETUP_SERVICE_SCRIPT	"/usr/lib/installadm/setup-service"
#define	SERVICE_REGISTER	"register"

#define	CHECK_SETUP_SCRIPT	"/usr/lib/installadm/check-server-setup"

#define	SETUP_DHCP_SCRIPT	"/usr/lib/installadm/setup-dhcp"
#define	DHCP_SERVER		"server"
#define	DHCP_MACRO		"macro"
#define	DHCP_ASSIGN		"assign"

#define	SETUP_TFTP_LINKS_SCRIPT	"/usr/lib/installadm/setup-tftp-links"
#define	TFTP_SERVER		"server"

#define	SETUP_SPARC_SCRIPT	"/usr/lib/installadm/setup-sparc"
#define	SPARC_SERVER		"server"
#define	WANBOOTCGI		"cgi-bin/wanboot-cgi"

#define	INSTALLADM_COMMON_SCRIPT	"/usr/lib/installadm/installadm-common"
#define	KSH93	"/usr/bin/ksh93"
#define	WC	"/usr/bin/wc"

#define	SRV_INSTANCE		"svc:/system/install/server:default"
#define	PORT_PROP		"all_services/port"
#define	DEFAULT_HTTP_PORT	5555

#define	MAXSERVICENAMELEN	63

/*
 * For each service, we start a webserver at a port and register the port with
 * the service. We start looking at the port number from 46501
 */
#define	START_WEB_SERVER_PORT	46501

#define	MAX_TXT_RECORD_LEN	1024
#define	DATALEN			256
#define	STATUSLEN		16
#define	INSTALL_SERVER_FMRI_BASE	"svc:/system/install/server"
#define	INSTALL_SERVER_DEF_INST	"default"

/*
 * For each service, store service data in the SMF repository. Use the
 * following keys to locate and store the data:
 */
#define	SERVICE			"service_name"
#define	IMAGE_PATH		"image_path"
#define	BOOT_FILE		"boot_file"
#define	TXT_RECORD		"txt_record"
#define	SERVICE_STATUS		"status"

#define	STATUS_ON		"on"

typedef struct service_data {
	char	svc_name[DATALEN];
	char	image_path[MAXPATHLEN];
	char	boot_file[MAXNAMELEN];
	char	txt_record[MAX_TXT_RECORD_LEN];
	char	status[STATUSLEN];
} service_data_t;

/*
 * function prototypes
 */
boolean_t validate_service_name(char *);
boolean_t save_service_data(scfutilhandle_t *, service_data_t);
boolean_t get_service_data(scfutilhandle_t *, char *, service_data_t *);
boolean_t service_exists(scfutilhandle_t *, char *);
uint16_t get_a_free_tcp_port(scfutilhandle_t *, uint16_t);
int installadm_system(char *);

/*
 * installadm messages
 */
#define	TEXT_DOMAIN		"SUNW_INSTALL_INSTALLADM"
#define	INSTALLADMSTR(x)	dgettext(TEXT_DOMAIN, x)

#define	MSG_MISSING_OPTIONS	INSTALLADMSTR(\
	"%s: missing one or more required options.\nusage:\n")
#define	MSG_OPTION_UNRECOGNIZED	INSTALLADMSTR(\
	"unrecognized option '-%c'\nusage: %s.\n")
#define	MSG_TARGET_NOT_EMPTY	INSTALLADMSTR(\
	"Target directory is not empty.\n")
#define	MSG_VALID_IMAGE_ERR	INSTALLADMSTR(\
	"There is a valid image at (%s)." \
	" Please delete the image and try again.\n")
#define	MSG_DIRECTORY_ACCESS_ERR	INSTALLADMSTR(\
	"Cannot access directory %s, error = %d.\n")
#define	MSG_CREATE_IMAGE_ERR	INSTALLADMSTR(\
	"Create image failed.\n")
#define	MSG_UNABLE_TO_DETERMINE_ARCH	INSTALLADMSTR(\
	"Unable to determine Oracle Solaris install image type.\n")
#define	MSG_REGISTER_SERVICE_FAIL	INSTALLADMSTR(\
	"Failed to register Install Service %s.\n")
#define	MSG_SERVICE_EXISTS	INSTALLADMSTR(\
	"The service %s already exists\n")
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
#define	MSG_AI_SMF_INIT_FAIL	INSTALLADMSTR(\
	"AI SMF initialization failed\n")
#define	MSG_GET_PG_NAME_FAILED	INSTALLADMSTR(\
	"Failed to get the SMF property group for service %s\n")
#define	MSG_GET_SMF_INSTANCE_FAILED	INSTALLADMSTR(\
	"Failed to get the SMF instance.\n")
#define	MSG_CREATE_INSTALL_SERVICE_FAILED	INSTALLADMSTR(\
	"Failed to create Install Service : %s\n")
#define	MSG_GET_SERVICE_PROPS_FAIL	INSTALLADMSTR(\
	"Failed to get SMF properties for service %s\n")
#define	MSG_SET_SERVICE_PROPS_FAIL	INSTALLADMSTR(\
	"Failed to set SMF properties for service %s\n")
#define	MSG_SAVE_SERVICE_PROPS_FAIL	INSTALLADMSTR(\
	"Failed to save SMF properties for service %s\n")
#define	MSG_CANNOT_FIND_PORT	INSTALLADMSTR(\
	"Cannot find a free port to start the web server.\n")
#define	MSG_ROOT_PRIVS_REQD	INSTALLADMSTR(\
	"Root privileges are required to run the %s %s command.\n")
#define	MSG_BAD_SERVICE_NAME    INSTALLADMSTR(\
	"Service name must contain only alphanumeric chars, \"_\" and \"-\" " \
	"and shorter then 64 characters in length\n")
#define	MSG_BAD_SERVER_SETUP	INSTALLADMSTR(\
	"Please check server network settings and try again.\n")
#define	MSG_MULTIHOMED_DHCP_DENY	INSTALLADMSTR(\
	"Setting up a DHCP server is not available on machines with " \
	"multiple network interfaces (-i and -c options unavailable).\n")

#endif /* _INSTALLADM_H */
