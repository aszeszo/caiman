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

#pragma ident	"@(#)svc_upg_recover.c	1.11	07/10/09 SMI"


#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include "spmicommon_lib.h"
#include "spmisoft_lib.h"
#include "spmisvc_lib.h"

/* Public Function Prototypes */
TUpgradeResumeState 	UpgradeResume(void);

/* Private Function Prototypes */
static int		partial_upgrade(void);

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * *********************************************************************
 * FUNCTION NAME: UpgradeResume
 *
 * DESCRIPTION:
 *  This function checks to see if an upgrade can be resumed from a
 *  previous attempt.
 *
 * RETURN:
 *  TYPE                   DESCRIPTION
 *  TUpgradeResumeState    This is the enumerated type that defines
 *                         the state of the recovery.  The valid
 *                         states are:
 *                           UpgradeResumeNone
 *                             An upgrade cannot be restarted.
 *                           UpgradeResumeRestore
 *                             An upgrade can be resumed from the restore
 *                             phase.
 *                           UpgradeResumeScript
 *                             An upgrade can be resumed from the final
 *                             upgrade script execution phase.
 *
 * PARAMETERS:
 *  TYPE                   DESCRIPTION
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

TUpgradeResumeState
UpgradeResume(void)
{
	TDSRALError	ArchiveError;
	TDSRALMedia	Media;
	char		MediaString[PATH_MAX];

	/*
	 * Check to see if we can recover from an interrupted adaptive upgrade
	 */

	if ((ArchiveError = DSRALCanRecover(&Media, MediaString))) {
		switch (ArchiveError) {
		case DSRALRecovery:
			return (UpgradeResumeRestore);
		default:
			return (UpgradeResumeNone);
		}
	}

	/*
	 * Ok, we wern't interrupted during the DSR portion of the upgrade
	 * so now lets check to see if we were interrupted during the
	 * upgrade script portion.
	 */

	if (partial_upgrade()) {
		return (UpgradeResumeScript);
	}
	return (UpgradeResumeNone);
}

/* ******************************************************************** */
/*			PRIVATE SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * partial_upgrade()
 * Parameters:
 *	none
 * Return:
 *
 * Status:
 *	private
 */
static int
partial_upgrade(void)
{
	char restart_file[MAXPATHLEN];
	char *root_path;
	struct stat	status;

	root_path = get_rootdir();

	if (*root_path == '\0') {
		(void) strcpy(restart_file,
		    "/var/sadm/system/admin/upgrade_restart");
	} else {
		(void) strcpy(restart_file, root_path);
		(void) strcat(restart_file,
		    "/var/sadm/system/admin/upgrade_restart");
	}

	if (stat(restart_file, &status) == 0)
		return (1);
	else if (is_new_var_sadm("/") != 1) {
		/*
		 * In this case the restart file in the new location is not
		 * present, and we do not have the new var/sadm structure
		 * yet. (thus an interrupted upgrade from pre to post-KBI)
		 * Therefore we need to look in the old location for
		 * completeness.
		 */

		if (*root_path == '\0') {
			(void) strcpy(restart_file,
			    "/var/sadm/install_data/upgrade_restart");
		} else {
			(void) strcpy(restart_file, root_path);
			(void) strcat(restart_file,
			    "/var/sadm/install_data/upgrade_restart");
		}

		if (stat(restart_file, &status) == 0)
			return (1);
	}

	/*
	 * The restart file was not found, but there may be a backup laying
	 * around. Look for it.
	 */
	if (*root_path == '\0') {
		(void) strcpy(restart_file,
		    "/var/sadm/system/admin/upgrade_restart.bkup");
	} else {
		(void) strcpy(restart_file, root_path);
		(void) strcat(restart_file,
		    "/var/sadm/system/admin/upgrade_restart.bkup");
	}
	if (stat(restart_file, &status) == 0)
		return (1);
	else if (is_new_var_sadm("/") != 1) {
		if (*root_path == '\0') {
			(void) strcpy(restart_file,
			    "/var/sadm/install_data/upgrade_restart.bkup");
		} else {
			(void) strcpy(restart_file, root_path);
			(void) strcat(restart_file,
			    "/var/sadm/install_data/upgrade_restart.bkup");
		}

		if (stat(restart_file, &status) == 0)
			return (1);
	}

	return (0);
}

#ifdef INCLUDE_RESUME_UPGRADE

/*
 * resume_upgrade()
 * Parameters:
 *	none
 * Return:
 *
 * Status:
 *	public
 */
int
resume_upgrade(void)
{
	char	cmd[MAXPATHLEN];
	int	status;
	struct stat	statStatus;
	char	restart_file[MAXPATHLEN];
	char	upg_script[MAXPATHLEN];
	char	upg_log[MAXPATHLEN];

	(void) sprintf(restart_file,
	    "%s/var/sadm/system/admin/upgrade_restart", get_rootdir());

	if (stat(restart_file, &statStatus) == 0) {
		(void) sprintf(upg_script,
		    "%s/var/sadm/system/admin/upgrade_script",
		    get_rootdir());
		(void) sprintf(upg_log,
		    "%s/var/sadm/system/logs/upgrade_log",
		    get_rootdir());
	} else {
		(void) sprintf(restart_file,
		    "%s/var/sadm/install_data/upgrade_restart", get_rootdir());
		(void) sprintf(upg_script,
		    "%s/var/sadm/install_data/upgrade_script", get_rootdir());
		(void) sprintf(upg_log,
		    "%s/var/sadm/install_data/upgrade_log", get_rootdir());
	}

	(void) sprintf(cmd, "/bin/mv %s %s.save", upg_log, upg_log);
	status = system(cmd);

	(void) sprintf(cmd, "/bin/sh %s %s restart 2>&1 | tee %s",
	    upg_script, get_rootdir(), upg_log);
	status = system(cmd);

	if (IsIsa("i386")) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/sbin/install-finish %s upgrade >> %s 2>&1",
		    get_rootdir(), upg_log);
		(void) system(cmd);
	}
	return (status);
}
#endif
