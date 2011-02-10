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

#include <locale.h>
#include <sys/stat.h>
#include <unistd.h>
#include <netdb.h>
#include <errno.h>

#include "installadm.h"

static boolean_t is_multihomed(void);

char	instance[sizeof (INSTALL_SERVER_FMRI_BASE) +
	    sizeof (INSTALL_SERVER_DEF_INST) + 1];

static char *cmd_usage = {
	"\tcreate-service\t[-b <property>=<value>,...] \n"
	"\t\t\t[-f <bootfile>] [-n <svcname>]\n"
	"\t\t\t[-i <dhcp_ip_start> -c <count_of_ipaddr>]\n"
	"\t\t\t[-s <srcimage>] <targetdir>"
};

int
main(int argc, char *argv[])
{
	scfutilhandle_t	*handle;
	int ret = 0;

	(void) setlocale(LC_ALL, "");

	(void) snprintf(instance, sizeof (instance), "%s:%s",
	    INSTALL_SERVER_FMRI_BASE, INSTALL_SERVER_DEF_INST);

	/*
	 * Check for privileges
	 */
	if (geteuid() > 0) {
		(void) fprintf(stderr, MSG_ROOT_PRIVS_REQD,
		    "installadm", "create-service");
		exit(INSTALLADM_FAILURE);
	}

	handle = ai_scf_init();
	if (handle == NULL) {
		(void) fprintf(stderr, MSG_AI_SMF_INIT_FAIL);
		exit(INSTALLADM_FAILURE);
	}

	/*
	 * set the umask, for all subcommands to inherit
	 */
	(void) umask(022);

	if (do_create_service(argc , &argv[0], handle, cmd_usage)) {
		ret = INSTALLADM_FAILURE;
	} else {
		ret = INSTALLADM_SUCCESS;
	}

	/* clean-up SMF handle */
	ai_scf_fini(handle);
	exit(ret);
}

/*
 * get_ip_from_hostname:
 *
 * Description:
 *   Resolves given hostname to IPv4 address. Result is stored as string
 *   into given buffer. If more than one IP address is returned, the first
 *   one is picked.
 *
 * parameters:
 *   name        - simple or fully qualified hostname to be resolved
 *   ip_string   - pointer to string buffer where IP address will
 *                 be stored
 *   buffer_size - size of ip_string
 *
 * return:
 *   0  - success
 *   -1 - resolve process failed - string buffer is left untouched
 */
static int
get_ip_from_hostname(char *name, char *ip_string, int buffer_size)
{
	struct hostent	*hp;
	struct in_addr	in;

	hp = gethostbyname(name);
	if (hp == NULL) {
		return (-1);
	} else {
		(void) memcpy(&in.s_addr, hp->h_addr_list[0],
		    sizeof (in.s_addr));

		(void) snprintf(ip_string, buffer_size, "%s", inet_ntoa(in));
	}

	return (0);
}


/*
 * smf_service_enable_attempt
 * Description:
 *		Attempt to enable the designated smf service.
 *		If the service goes into maintenance mode,
 *		return an error to the caller.
 * Parameters:
 *		instance - The instance to attempt to enable
 * Return:
 *		None
 * Scope:
 *		Private
 */
static void
smf_service_enable_attempt(char *instance)
{
	char		*orig_state = NULL;
	int		enable_tried = 0;

	/*
	 * Check the service status here.
	 * Algorithm:
	 *	If the service is online, everything is OK. return.
	 *	If the service is offline, SMF is settling. Return
	 *	    or we get caught in recursion.
	 * 	If the service is disabled, try to enable it.
	 *	If the service is in maintenance, try to clear it and
	 *	    then enable it.
	 */
	orig_state = smf_get_state(instance);
	if (orig_state == NULL) {
		(void) smf_enable_instance(instance, 0);
	} else if (strcmp(orig_state, SCF_STATE_STRING_ONLINE) == 0) {
		/*
		 * Instance is online and running.
		 */
		free(orig_state);
		return;
	} else if (strcmp(orig_state, SCF_STATE_STRING_OFFLINE) == 0) {
		free(orig_state);
		return;
	} else if (strcmp(orig_state, SCF_STATE_STRING_DISABLED) == 0) {
		/*
		 * Instance is disabled try to enable it.
		 */
		(void) smf_enable_instance(instance, 0);
	} else if (strcmp(orig_state, SCF_STATE_STRING_MAINT) == 0) {
		(void) smf_restore_instance(instance);
		/*
		 * Instance is now disabled try to enable it.
		 */
		(void) smf_enable_instance(instance, 0);
	}
	free(orig_state);

}

/*
 * Function:    is_multihomed
 * Description:
 *              Check the if the machine is multihomed or not
 * Parameters:
 *		None
 * Return:
 *		B_TRUE  - Machine is multihomed
 *		B_FALSE - Machine is not multihomed
 * Scope:
 *              Private
 */
static boolean_t
is_multihomed(void)
{
	char	cmd[MAXPATHLEN];

	/*
	 * use the shell to see if system is multihomed by calling
	 * valid_networks() from installadm-common and using wc(1) to count
	 */
	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/bin/test `%s -c 'source %s; valid_networks' | "
	    "%s -l` -eq '1' ]",
	    KSH93, INSTALLADM_COMMON_SCRIPT, WC);

	if (installadm_system(cmd) != 0) {
		return (B_TRUE);
	}
	return (B_FALSE);
}

/*
 * do_create_service:
 * This function parses the command line arguments and sets up
 * the image, the DNS service, the network configuration for the
 * the clients to boot from this image (/tftpboot) and dhcp if desired.
 * This function calls shell scripts to handle each of the tasks
 */
static int
do_create_service(
	int argc,
	char *argv[],
	scfutilhandle_t *handle,
	const char *use)
{
	int		opt;
	boolean_t	named_service = B_FALSE;
	boolean_t	named_boot_file = B_FALSE;
	boolean_t	dhcp_setup_needed = B_FALSE;
	boolean_t	create_netimage = B_FALSE;
	boolean_t	create_service = B_FALSE;
	boolean_t	have_sparc = B_FALSE;
	boolean_t	compatibility_port = B_FALSE;

	char		*bootargs = NULL;
	char		*boot_file = NULL;
	char		*ip_start = NULL;
	short		ip_count = 0;
	char		*service_name = NULL;
	char		*source_path = NULL;
	char		*target_directory = NULL;

	struct stat	stat_buf;
	struct stat 	sb;
	char		cmd[MAXPATHLEN];
	char		mpath[MAXPATHLEN];
	char		bfile[MAXPATHLEN];
	char		server_hostname[DATALEN];
	char		server_ip[DATALEN];
	char		srv_name[MAXPATHLEN];
	char		srv_address[DATALEN] = "unknown";
	char		txt_record[DATALEN];
	char		dhcp_macro[MAXNAMELEN+12]; /* dhcp_macro_<filename> */
	int		size;
	service_data_t	data;
	char		*pg_name;
	int		port;
	int		http_port;

	while ((opt = getopt(argc, argv, ":b:f:n:i:c:s:")) != -1) {
		switch (opt) {
		/*
		 * Create a boot file for this service with the supplied name
		 */
		case 'b':
			bootargs = optarg;
			break;
		case 'f':
			named_boot_file = B_TRUE;
			boot_file = optarg;
			break;
		/*
		 * The name of the service is supplied.
		 */
		case 'n':
			if (!validate_service_name(optarg)) {
				(void) fprintf(stderr, MSG_BAD_SERVICE_NAME);
				return (INSTALLADM_FAILURE);
			}
			named_service = B_TRUE;
			service_name = optarg;
			break;
		/*
		 * The starting IP address is supplied.
		 */
		case 'i':
			dhcp_setup_needed = B_TRUE;
			ip_start = optarg;
			break;
		/*
		 * Number of IP addresses to be setup
		 */
		case 'c':
			ip_count = atoi(optarg);
			if (ip_count < 1)  {
				(void) fprintf(stderr, "%s\n", gettext(use));
				return (INSTALLADM_FAILURE);
			}
			break;
		/*
		 * Source image is supplied.
		 */
		case 's':
			create_netimage = B_TRUE;
			source_path = optarg;
			break;
		default:
			(void) fprintf(stderr, "%s\n", gettext(use));
			return (INSTALLADM_FAILURE);
		}
	}

	/*
	 * The last argument is the target directory.
	 */
	target_directory = argv[optind++];

	if (target_directory == NULL) {
		(void) fprintf(stderr, "%s\n", gettext(use));
		return (INSTALLADM_FAILURE);
	}

	/*
	 * Verify that the server settings are not obviously broken.
	 * These checks cannot be complete, but check for things which will
	 * definitely cause failure.
	 */
	(void) snprintf(cmd, sizeof (cmd), "%s %s",
	    CHECK_SETUP_SCRIPT, ((ip_start != NULL) ? ip_start : ""));
	if (installadm_system(cmd) != 0) {
		(void) fprintf(stderr, MSG_BAD_SERVER_SETUP);
		return (INSTALLADM_FAILURE);
	}

	/*
	 * The options -i and -c should either both be set or
	 * neither argument should be set.
	 */
	if (((ip_count != 0) && (ip_start == NULL)) ||
	    ((ip_count == 0) && (ip_start != NULL))) {
		(void) fprintf(stderr, MSG_MISSING_OPTIONS, argv[0]);
		(void) fprintf(stderr, "%s\n", gettext(use));
		return (INSTALLADM_FAILURE);
	}

	/*
	 * The options -i and -c are not to be allowed when the system is
	 * multi-homed, see if we're asked to do dhcp_setup
	 */
	if (dhcp_setup_needed && is_multihomed() == B_TRUE) {
		(void) fprintf(stderr, MSG_MULTIHOMED_DHCP_DENY);
		return (INSTALLADM_FAILURE);
	}

	/*
	 * obtain server hostname and resolve it to IP address
	 * If this operation fails, something is wrong with network
	 * configuration - exit
	 */
	if (gethostname(server_hostname, sizeof (server_hostname)) != 0) {
		(void) fprintf(stderr, MSG_GET_HOSTNAME_FAIL);
		return (INSTALLADM_FAILURE);
	}

	/*
	 * if the machine is multihomed, use the keyword $serverIP for
	 * server_ip; otherwise, set server_ip to the IP address resolved
	 * for the machine's hostname -- which may or may not resolve to
	 * something sensible
	 */
	if (is_multihomed() == B_TRUE) {
		(void) snprintf(server_ip, sizeof (server_ip), "$serverIP");
	} else {
		if (get_ip_from_hostname(server_hostname, server_ip,
		    sizeof (server_ip)) != 0) {
			(void) fprintf(stderr, MSG_GET_HOSTNAME_FAIL);
			return (INSTALLADM_FAILURE);
		}
	}

	/*
	 * Check to see if service exists -- error if it does
	 */
	if (named_service) {
		if (service_exists(handle, service_name)) {
			(void) fprintf(stderr, MSG_SERVICE_EXISTS,
			    service_name);
			return (INSTALLADM_FAILURE);
		}
		/* service does not exist use the provided name */
		strlcpy(srv_name, service_name, sizeof (srv_name));
	}

	/*
	 * Check whether target exists
	 * If it doesn't exist, the setup-image script will
	 * create the directory.
	 * If it exists, check whether it has a valid net image
	 */
	if (access(target_directory, F_OK) == 0) {
		if (stat(target_directory, &stat_buf) == 0) {
			char	path[MAXPATHLEN];
			/*
			 * If the directory is empty, then it is okay
			 */
			if (stat_buf.st_nlink > 2) {
				/*
				 * Check whether it has valid file solaris.zlib
				 */
				(void) snprintf(path, sizeof (path), "%s/%s",
				    target_directory,
				    AI_NETIMAGE_REQUIRED_FILE);
				if (access(path, R_OK) != 0) {
					(void) fprintf(stderr,
					    MSG_TARGET_NOT_EMPTY);
					return (INSTALLADM_FAILURE);
				}
				/*
				 * Already have an image. We can't create a
				 * new one w/o removing the old one.
				 * Display error
				 */
				if (create_netimage) {
					(void) fprintf(stderr,
					    MSG_VALID_IMAGE_ERR,
					    target_directory);
					return (INSTALLADM_FAILURE);
				}
			}
		} else {
			(void) fprintf(stderr,
			    MSG_DIRECTORY_ACCESS_ERR,
			    target_directory, errno);
			return (INSTALLADM_FAILURE);
		}
	}

	/*
	 * call the script to create the netimage
	 */
	if (create_netimage) {
		(void) snprintf(cmd, sizeof (cmd), "%s %s %s %s",
		    SETUP_IMAGE_SCRIPT, IMAGE_CREATE,
		    source_path, target_directory);
		if (installadm_system(cmd) != 0) {
			(void) fprintf(stderr, MSG_CREATE_IMAGE_ERR);
			return (INSTALLADM_FAILURE);
		}
		(void) snprintf(cmd, sizeof (cmd), "%s %s %s",
		    SETUP_IMAGE_SCRIPT, CHECK_IMAGE_VERSION,
		    target_directory);
		if (installadm_system(cmd) != 0)
			compatibility_port = B_TRUE;
	}

	/*
	 * Check whether image is sparc or x86 by checking existence
	 * of key directories
	 */
	(void) snprintf(mpath, sizeof (mpath), "%s/%s", target_directory,
	    "platform/sun4v");
	if ((stat(mpath, &sb) == 0) && S_ISDIR(sb.st_mode)) {
		have_sparc = B_TRUE;
	} else {
		(void) snprintf(mpath, sizeof (mpath), "%s/%s",
		    target_directory, "platform/i86pc");
		if (stat(mpath, &sb) || !S_ISDIR(sb.st_mode)) {
			(void) fprintf(stderr, MSG_UNABLE_TO_DETERMINE_ARCH);
			return (INSTALLADM_FAILURE);
		}
	}

	/*
	 * The net-image is created, now setup the port and service name
	 */
	txt_record[0] = '\0';
	srv_name[0] = '\0';

	http_port = get_http_port(handle);
	if (compatibility_port == B_TRUE) {
		port = (int)get_a_free_tcp_port(handle, START_WEB_SERVER_PORT);
		if (port == 0) {
			(void) fprintf(stderr, MSG_CANNOT_FIND_PORT);
			return (INSTALLADM_FAILURE);
		}
	} else {
		port = http_port;
	}

	/*
	 * set text record to "aiwebserver=$serverIP:<port>"
	 * (if multihomed) or to "aiwebserver=<server hostname>:<port>"
	 * (if single-homed)
	 */
	snprintf(txt_record, sizeof (txt_record), "%s=%s:%u",
	    AIWEBSERVER, server_hostname, port);
	if (!named_service) {
		int count = 1;

		snprintf(srv_name, sizeof (srv_name),
		    "_install_service_%d", count);
		while (service_exists(handle, srv_name)) {
			count++;
			snprintf(srv_name, sizeof (srv_name),
			    "_install_service_%d", count);
		}
	} else {
		strlcpy(srv_name, service_name, sizeof (srv_name));
	}

	/*
	 * save location of service in format <server_ip_address>:<port>
	 * It will be used later for setting service discovery fallback
	 * mechanism
	 */

	snprintf(srv_address, sizeof (srv_address), "%s:%u",
	    is_multihomed()?"\\$serverIP":server_ip, port);

	bfile[0] = '\0';
	if (named_boot_file) {
		strlcpy(bfile, boot_file, sizeof (bfile));
	} else {
		strlcpy(bfile, srv_name, sizeof (bfile));
	}

	/*
	 * Register the information about the service, image and boot file
	 * so that it can be used later
	 */
	pg_name = ai_make_pg_name(srv_name);
	if (pg_name == NULL) {
		(void) fprintf(stderr, MSG_GET_PG_NAME_FAILED, srv_name);
		return (INSTALLADM_FAILURE);
	}
	if (ai_create_pg(handle, pg_name) != AI_SUCCESS) {
		free(pg_name);
		(void) fprintf(stderr, MSG_CREATE_INSTALL_SERVICE_FAILED,
		    srv_name);
		return (INSTALLADM_FAILURE);
	}
	free(pg_name);

	strlcpy(data.svc_name, srv_name, DATALEN);
	strlcpy(data.image_path, target_directory, MAXPATHLEN);
	strlcpy(data.boot_file, bfile, MAXNAMELEN);
	strlcpy(data.txt_record, txt_record, MAX_TXT_RECORD_LEN);
	strlcpy(data.status, STATUS_ON, STATUSLEN);

	if (save_service_data(handle, data) != B_TRUE) {
		(void) fprintf(stderr, MSG_SAVE_SERVICE_PROPS_FAIL,
		    data.svc_name);
		return (INSTALLADM_FAILURE);
	}

	/* if needed, enable install service */
	smf_service_enable_attempt(instance);

	/*
	 * Register service
	 */
	snprintf(cmd, sizeof (cmd), "%s %s %s %s %s",
	    SETUP_SERVICE_SCRIPT, SERVICE_REGISTER,
	    srv_name, txt_record, target_directory);
	if (installadm_system(cmd) != 0) {
		(void) fprintf(stderr,
		    MSG_REGISTER_SERVICE_FAIL, srv_name);
		return (INSTALLADM_FAILURE);
	}

	/*
	 * Setup dhcp
	 */
	if (dhcp_setup_needed && create_netimage) {
		snprintf(cmd, sizeof (cmd), "%s %s %s %d",
		    SETUP_DHCP_SCRIPT, DHCP_SERVER, ip_start, ip_count);
		if (installadm_system(cmd) != 0) {
			(void) fprintf(stderr,
			    MSG_CREATE_DHCP_SERVER_ERR);
			return (INSTALLADM_FAILURE);
		}
	}

	if (create_netimage) {
		char	dhcpbfile[MAXPATHLEN];

		snprintf(dhcp_macro, sizeof (dhcp_macro),
		    "dhcp_macro_%s", bfile);

		/*
		 * determine contents of bootfile info passed to dhcp script
		 * as well as rootpath for sparc
		 */
		if (have_sparc) {
			/*
			 * Always use $serverIP keyword as setup-dhcp will
			 * substitute the correct IP addresses in
			 */
			snprintf(dhcpbfile, sizeof (dhcpbfile),
			    "http://%s:%u/%s", "\\$serverIP",
			    http_port, WANBOOTCGI);
		} else {
			strlcpy(dhcpbfile, bfile, sizeof (dhcpbfile));
		}

		snprintf(cmd, sizeof (cmd), "%s %s %s %s %s",
		    SETUP_DHCP_SCRIPT, DHCP_MACRO, have_sparc?"sparc":"x86",
		    dhcp_macro, dhcpbfile);
		/*
		 * The setup-dhcp script takes care of printing output for the
		 * user so there is no need to print anything for non-zero
		 * return value.
		 */
		installadm_system(cmd);
	}

	if (dhcp_setup_needed && create_netimage) {
		snprintf(cmd, sizeof (cmd), "%s %s %s %d %s",
		    SETUP_DHCP_SCRIPT, DHCP_ASSIGN,
		    ip_start, ip_count, dhcp_macro);
		if (installadm_system(cmd) != 0) {
			(void) fprintf(stderr,
			    MSG_ASSIGN_DHCP_MACRO_ERR);
		}
	}

	/*
	 * Perform sparc/x86 specific actions.
	 */
	if (have_sparc) {
		/* sparc only */
		snprintf(cmd, sizeof (cmd), "%s %s %s %s %s",
		    SETUP_SPARC_SCRIPT, SPARC_SERVER, target_directory,
		    srv_name, srv_address);

		if (installadm_system(cmd) != 0) {
			(void) fprintf(stderr, MSG_SETUP_SPARC_FAIL);
			return (INSTALLADM_FAILURE);
		}
	} else {
		/* x86 only */
		snprintf(cmd, sizeof (cmd), "%s %s %s %s %s %s",
		    SETUP_TFTP_LINKS_SCRIPT, TFTP_SERVER, srv_name,
		    target_directory, bfile,
		    bootargs == NULL ? "null" : bootargs);

		if (installadm_system(cmd) != 0) {
			(void) fprintf(stderr, MSG_CREATE_TFTPBOOT_FAIL);
			return (INSTALLADM_FAILURE);
		}
	}

	return (INSTALLADM_SUCCESS);
}
