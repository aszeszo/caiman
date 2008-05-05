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
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>

#include "orchestrator_private.h"

void
generate_install_callback_data(char *progress, int period)
{
	int	sleep_time = 10;
	int	i, j, percent, max;
	int 	ti_period, pi_period;
	FILE	*fp;
	char	milestone_string[128];

	/*
	 * Set the target instantiation period to first 2 minutes
	 */
	ti_period = 2*60;
	/*
	 * Set the postinstall period to last 2 minutes
	 */
	pi_period = 2*60;
	period -= (ti_period + pi_period);
	/*
	 * for install, there are 3 milestones
	 * target instantiation, software_update and post install
	 */
	for (i = 0; i < 3; i++) {
		if (i == 0) {
			max = ti_period;
			(void) strcpy(milestone_string,
			    "targetInstantiationStatus ");
		} else if (i == 1) {
			max = period;
			(void) strcpy(milestone_string,
			    "progressStatus ");
		} else {
			max = pi_period;
			(void) strcpy(milestone_string,
			    "postInstallStatus ");
		}

		for (j = 0; j <= max; j += sleep_time) {
			percent = (j*100)/max;
			if (percent > 100) {
				percent = 100;
			}


			fp = fopen(progress, "a");
			if (fp != NULL) {
				(void) fprintf(fp,
				    "<%s " \
				    " source=\"pfinstall\"" \
				    " type=\"solaris-install\"" \
				    " percent=\"%d\" />\n",
				    milestone_string, percent);
				/* WRITE it out */
				(void) fclose(fp);
			}
			(void) sleep(sleep_time);
		}
	}
}

void
generate_upgrade_callback_data(char *progress, int period)
{
	int	sleep_time = 10;
	int	i, j, percent, max;
	int 	pi_period;
	FILE	*fp;
	char	milestone_string[128];

	/*
	 * Set the postinstall period to last 2 minutes
	 */
	pi_period = 2*60;
	period -= pi_period;
	/*
	 * for upgrade, there are 2 milestones
	 * software_update and post install
	 */
	for (i = 0; i < 2; i++) {
		if (i == 0) {
			max = period;
			(void) strcpy(milestone_string,
			    "progressStatus ");
		} else {
			max = pi_period;
			(void) strcpy(milestone_string,
			    "postInstallStatus ");
		}

		for (j = 0; j <= max; j += sleep_time) {
			percent = (j*100)/max;
			if (percent > 100) {
				percent = 100;
			}

			fp = fopen(progress, "a");
			if (fp != NULL) {
				(void) fprintf(fp,
				    "<%s " \
				    " source=\"pfinstall\"" \
				    " type=\"solaris-upgrade\"" \
				    " percent=\"%d\" />\n",
				    milestone_string, percent);
				/* WRITE it out */
				(void) fclose(fp);
			}
			(void) sleep(sleep_time);
		}
	}
}

int
main(int argc, char **argv)
{
	FILE	*fp, *fp1;
	char	buf[1024];
	char	profile[1024];
	char	progress[1024];
	int	period;
	boolean_t upgrade_flag;

	if (argc < 4) {
		(void) printf(
		    "Usage %s [-u] -r <progress_output> <profile_path>\n",
		    argv[0]);
		exit(1);
	}

	if (argc == 5) {
		upgrade_flag = B_TRUE;
		(void) strcpy(profile, argv[4]);
		(void) strcpy(progress, argv[3]);
	}

	if (argc == 4) {
		upgrade_flag = B_FALSE;
		(void) strcpy(profile, argv[3]);
		(void) strcpy(progress, argv[2]);
	}

	fp = fopen(profile, "r");
	if (fp == NULL) {
		(void) printf("Profile %s is not valid\n", profile);
		(void) printf("Usage %s [-u] -r <progress_output>" \
		    "<profile_path>\n", argv[0]);
		exit(2);
	}

	fp1 = fopen("/tmp/dummy_install.out", "w");
	if (fp1 == NULL) {
		(void) printf("cannot create dummy output file\n");
		exit(3);
	}

	while (fgets(buf, sizeof (buf), fp) != NULL) {
		(void) fputs(buf, fp1);
	}
	(void) fclose(fp1);

	/*
	 * callback for 20 minutes
	 */
	period = 20 * 60;
	if (upgrade_flag) {
		generate_upgrade_callback_data(progress, period);
	} else {
		generate_install_callback_data(progress, period);
	}
	exit(0);
}
