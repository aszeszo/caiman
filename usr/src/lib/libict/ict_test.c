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

/*
 * This file contains a simple, brute force, test exerciser  for the libict API.
 */

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "ict_private.h"
#include "ict_api.h"

#define	SET_HOST_NODE_NAME	"ict_set_host_node_name"	/* 22 */
#define	SET_LANG_LOCALE		"ict_set_lang_locale"		/* 19 */
#define	CREATE_USER_DIRECTORY	"ict_configure_user_directory"	/* 25 */
#define	SET_USER_PROFILE	"ict_set_user_profile"		/* 20 */
#define	INSTALLBOOT		"ict_installboot"		/* 15 */
#define	SET_USER_ROLE		"ict_set_user_role"		/* 17 */
#define	SNAPSHOT		"ict_snapshot"			/* 12 */
#define	TRANSFER_LOGS		"ict_transfer_logs"		/* 17 */
#define	MARK_ROOT_POOL_READY	"ict_mark_root_pool_ready"	/* 24 */

void
usage_exit(char *_this)
{
	(void) fprintf(stderr, "Usage:  %s <ICT> <ICT args>\n", _this);
	(void) fprintf(stderr, "ICT options:\n");
	(void) fprintf(stderr,
	    "\t%s ict_set_host_node_name <target> <hostname>\n",
	    _this);
	(void) fprintf(stderr,
	    "\t%s ict_set_lang_locale <target> <localep> <transfer mode>\n",
	    _this);
	(void) fprintf(stderr,
	    "\t%s ict_configure_user_directory <target> <login>\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_set_user_profile <target> <login>\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_installboot <target> <device>\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_set_user_role <target> [login]\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_snapshot <pool> <snapshot>\n",
	    _this);
	(void) fprintf(stderr,
	    "\t%s ict_transfer_logs <src> <dst> <transfer mode>\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_mark_root_pool_ready <pool>\n",
	    _this);
	(void) fprintf(stderr, "\nICT e.g.:\n");
	(void) fprintf(stderr,
	    "\t%s ict_set_host_node_name \"/a\" \"MY_HOST\"\n",
	    _this);
	(void) fprintf(stderr,
	    "\t%s ict_set_lang_locale \"/a\" \"en_US.UTF-8\" 0\n",
	    _this);
	(void) fprintf(stderr,
	    "\t%s ict_configure_user_directory \"/a\" \"guest\"\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_set_user_profile \"/a\" \"guest\"\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_installboot \"/a\" \"c5d0s0\"\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_set_user_role \"/a\" \"guest\"\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_snapshot \"rpool\" \"install\"\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_transfer_logs \"/\" \"/a\" 0\n",
	    _this);
	(void) fprintf(stderr, "\t%s ict_mark_root_pool_ready \"rpool\"\n",
	    _this);

	exit(1);
} /* END usage_exit() */

int
main(int argc, char **argv)
{

	ict_status_t ict_result = ICT_SUCCESS;
	int i;

	(void) fprintf(stdout, "argc ->%d<-\n", argc);
	for (i = 0; i < argc; i++) {
		(void) fprintf(stdout, "argv[%d] ->%s<-\n", i, argv[i]);
	}

	if ((argc < 3) || (argc > 6)) {
		usage_exit(argv[0]);
	}

	if (strncmp(argv[1], SET_HOST_NODE_NAME, 22) == 0) {
		if ((argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s)\n",
			    SET_HOST_NODE_NAME, argv[2], argv[3]);
			ict_set_host_node_name(argv[2], argv[3]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], SET_LANG_LOCALE, 19) == 0) {
		if ((argc != 5)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s, %d)\n",
			    SET_LANG_LOCALE, argv[2], argv[3], atoi(argv[4]));
			ict_set_lang_locale(argv[2], argv[3], atoi(argv[4]));
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], CREATE_USER_DIRECTORY, 25) == 0) {
		if ((argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s)\n",
			    CREATE_USER_DIRECTORY, argv[2], argv[3]);
			ict_configure_user_directory(argv[2], argv[3]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], SET_USER_PROFILE, 20) == 0) {
		if ((argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s)\n",
			    SET_USER_PROFILE, argv[2], argv[3]);
			ict_set_user_profile(argv[2], argv[3]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], INSTALLBOOT, 15) == 0) {
		if ((argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s)\n",
			    INSTALLBOOT, argv[2], argv[3]);
			ict_installboot(argv[2], argv[3]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], SET_USER_ROLE, 17) == 0) {
		/*
		 * The second argument to ict_set_user_role, login is
		 * optional.
		 */
		if ((argc != 3) && (argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			if ((argc == 4)) {
				(void) fprintf(stdout, "%s(%s, %s)\n",
				    SET_USER_ROLE, argv[2], argv[3]);
				ict_set_user_role(argv[2], argv[3]);
			} else {
				(void) fprintf(stdout, "%s(%s, NULL)\n",
				    SET_USER_ROLE, argv[2]);
				ict_set_user_role(argv[2], (char *)NULL);
			}
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], SNAPSHOT, 12) == 0) {
		if ((argc != 4)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s)\n",
			    SNAPSHOT, argv[2], argv[3]);
			ict_snapshot(argv[2], argv[3]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], TRANSFER_LOGS, 17) == 0) {
		if ((argc != 5)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s, %s, %d)\n",
			    TRANSFER_LOGS, argv[2], argv[3], atoi(argv[4]));
			ict_transfer_logs(argv[2], argv[3], atoi(argv[4]));
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else if (strncmp(argv[1], MARK_ROOT_POOL_READY, 24) == 0) {
		if ((argc != 3)) {
			usage_exit(argv[0]);
		} else {
			(void) fprintf(stdout, "Invoking ICT: \n");
			(void) fprintf(stdout, "%s(%s)\n",
			    MARK_ROOT_POOL_READY, argv[2]);
			ict_mark_root_pool_ready(argv[2]);
			(void) fprintf(stdout, "Result \n\t%s\n",
			    ICT_STR_ERROR(ict_errno));
		}
	} else {
		usage_exit(argv[0]);
	}

	exit(0);
}
