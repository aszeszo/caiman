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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <sys/types.h>
#include <sys/stat.h>
#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <dirent.h>
#include <procfs.h>
#include <limits.h>
#include <errno.h>
#include <ctype.h>

#include "orchestrator_private.h"

#define	MAX_PID_LEN 16
#define	PROCDIR "/proc"	/* standard /proc directory */

/*
 * Messages
 */
#define	PROC_INFO_ERR "Failed to access process information %s\n"
#define	PROC_INFO_ERR_ERRNO "Failed to access process information %s\n%s\n"
#define	PROC_DIR_ERR  "Failed to open /proc directory %s\n%s\n"
#define	ALREADY_RUNNING "Program %s is already running at PID %d\n"

static	om_proc_return_t	get_cur_prog_name(char *, pid_t);
static	om_proc_return_t	check_each_proc(char *, pid_t);

/*
 * om_process_running()
 * Determine if another process is already this program. Actually
 * it checks if another process is running a program with the same
 * name as the current program.
 *
 * Input: None
 *
 * Output: None
 *
 * Returns:
 *
 *  OM_PROC_NOT_RUNNING
 *	Did not detect another process running a program with the
 *      same name as the current program.
 *  OM_PROC_ALREADY_RUNNING
 *	Detected another process running a program with the
 *      same name as the current program.
 *  OM_PROC_DIR_ERR
 *      Failed to open /proc directory.
 *  OM_PROC_INFO_ERR
 *      Failed to access process information for a specific process.
 */
om_proc_return_t
om_process_running()
{
	pid_t		cpid; /* current PID */
	char		cpr_fname[PRFNSZ];
	char		*cpr_fname_p;

	cpr_fname_p = cpr_fname;

	/*
	 * Retrieve the fname from /proc/<current pid>
	 */
	memset((char *)cpr_fname_p, '\000', sizeof (cpr_fname));
	cpid = getpid();
	if (get_cur_prog_name(cpr_fname_p, cpid) != OM_PROC_SUCCESS) {
		om_debug_print(OM_DBGLVL_WARN, PROC_INFO_ERR);
		return (OM_PROC_INFO_ERR);
	}

	return (check_each_proc(cpr_fname_p, cpid));

} /* END om_process_running() */

/*
 * get_cur_prog_name()
 *
 * Gather the fname from the /proc/X/psinfo file for the current
 * process.
 *
 * Input:
 *	return_fname: where to return program name (fname)
 *	cpid: PID to return information about
 *
 * Output:
 *	return_fname: The matching PID program name (fname)
 *
 * Returns:
 *
 *  OM_PROC_SUCCESS
 *	Successfully obtained program name running at PID: cpid.
 *  OM_PROC_INFO_ERR
 *      Failed to access process information for a specific process.
 */
static om_proc_return_t
get_cur_prog_name(char *return_fname, pid_t cpid)
{
	char		pname[PATH_MAX];
	int		procfd;		/* filedescriptor for /proc/x/psinfo */
	psinfo_t	info;		/* process information from /proc */
	int		saverr;

	snprintf(pname, sizeof (pname), "%s/%d/psinfo", PROCDIR, cpid);
	if ((procfd = open(pname, O_RDONLY)) == -1) {
		saverr = errno;
		om_debug_print(OM_DBGLVL_WARN, PROC_INFO_ERR_ERRNO, pname,
		    strerror(saverr));
		return (OM_PROC_INFO_ERR);
	}


	/*
	 * Get the info structure for the process and close quickly.
	 */
	if (read(procfd, (char *)&info, sizeof (info)) < 0) {
		saverr = errno;
		(void) close(procfd);
		om_debug_print(OM_DBGLVL_WARN, PROC_INFO_ERR_ERRNO,
		    pname, strerror(saverr));
		return (OM_PROC_INFO_ERR);
	} /* END if () */
	(void) close(procfd);

	strncpy(return_fname, info.pr_fname, strlen(info.pr_fname)+1);

	return (OM_PROC_SUCCESS);

} /* END get_cur_prog_name() */

/*
 * check_each_proc()
 *
 * Gather the fname from the /proc/X/psinfo file for each process
 * listed in the /prod directory check for a match to the supplied
 * input arguments, cpr_fname and cpid.
 *
 * Input:
 *	cpr_fname: The current program name (fname)
 *	cpid: The current PID.
 *
 * Output: None
 *
 * Returns:
 *
 *  OM_PROC_NOT_RUNNING
 *	Did not detect another process running a program with the
 *      same name as the current program.
 *  OM_PROC_ALREADY_RUNNING
 *	Detected another process running a program with the
 *      same name as the current program.
 *  OM_PROC_DIR_ERR
 *      Failed to open /proc directory.
 *  OM_PROC_INFO_ERR
 *      Failed to access process information for a specific process.
 */
static om_proc_return_t
check_each_proc(
	char	*cpr_fname,
	pid_t	cpid)
{
	DIR		*dirp;
	struct dirent	*dentp;
	char		pname[PATH_MAX];
	int		procfd; /* filedescriptor for /proc/nnnnn/psinfo */
	psinfo_t 	info;  /* process information from /proc */
	int		saverr;

	if ((dirp = opendir(PROCDIR)) == NULL) {
		saverr = errno;
		om_debug_print(OM_DBGLVL_WARN, PROC_DIR_ERR, PROCDIR,
		    strerror(saverr));
		return (OM_PROC_DIR_ERR);
	}

	/* for each active process --- */
	while (dentp = readdir(dirp)) {
		if (dentp->d_name[0] == '.') {   /* skip . and .. */
			continue;
		}

		snprintf(pname, sizeof (pname), "%s/%s/psinfo", PROCDIR,
		    dentp->d_name);
		if ((procfd = open(pname, O_RDONLY)) == -1) {
			/* Process exited or could be junk in /proc */
			continue;
		}

		/*
		 * Get the info structure for the process and close quickly.
		 */
		if (read(procfd, (char *)&info, sizeof (info)) < 0) {
			saverr = errno;
			(void) close(procfd);
			(void) closedir(dirp);
			om_debug_print(OM_DBGLVL_WARN, PROC_INFO_ERR_ERRNO,
			    pname, strerror(saverr));
			return (OM_PROC_INFO_ERR);
		} /* END if () */
		(void) close(procfd);

		if (strncmp(info.pr_fname,
		    cpr_fname,
		    sizeof (info.pr_fname)) == 0) {
			if (cpid != (pid_t)info.pr_pid) {
				(void) closedir(dirp);
				om_debug_print(OM_DBGLVL_WARN,
				    ALREADY_RUNNING, cpr_fname,
				    info.pr_pid);
				return (OM_PROC_ALREADY_RUNNING);

			}
		}

	} /* while () for each active process */

	(void) closedir(dirp);
	return (OM_PROC_NOT_RUNNING);

} /* END check_each_proc() */
