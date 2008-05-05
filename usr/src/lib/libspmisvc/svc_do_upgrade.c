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



#include <assert.h>
#include <fcntl.h>
#include <libintl.h>
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include "spmicommon_api.h"
#include "spmisoft_lib.h"
#include "spmisvc_lib.h"

/* Public Function Prototypes */

int		execute_upgrade(OpType, char *,
		    int (*)(void *, void *), void *);
void		log_spacechk_failure(int);
void		MakePostKBIDirectories(void);
int 		SetupPreKBI(void);

/* Local Function Prototypes */

extern int sp_err_code;
extern int sp_err_subcode;
extern char *sp_err_path;

static char *old_scriptpath = "/var/sadm/install_data/upgrade_script";
static char *new_scriptpath = "/var/sadm/system/admin/upgrade_script";

static void	catch_prog_sig(int);
static int	(*exec_callback_proc)(void *, void *);
static void	*exec_callback_arg;

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * Function:	MakePostKBIDirectories()
 * Description: This function creates the necessary directories for a
 *		post KBI system
 *
 * Scope:	public
 * Parameters:
 *		None
 * Return:
 *		int		0 	= Success
 *				not 0 	= Failure
 */

void
MakePostKBIDirectories(void)
{
	char	dir[MAXPATHLEN];
	char	tdir[MAXPATHLEN];

	/*
	 * Since this root is pre var/sadm change make the
	 * directories.
	 */

	(void) snprintf(dir, MAXPATHLEN, "%s/var/sadm/system",
	    get_rootdir());
	(void) mkdir(dir, (mode_t)00755);
	(void) snprintf(tdir, MAXPATHLEN, "%s/logs", dir);
	(void) mkdir(tdir, (mode_t)00755);
	(void) snprintf(tdir, MAXPATHLEN, "%s/data", dir);
	(void) mkdir(tdir, (mode_t)00755);
	(void) snprintf(tdir, MAXPATHLEN, "%s/admin", dir);
	(void) mkdir(tdir, (mode_t)00755);
	(void) snprintf(tdir, MAXPATHLEN, "%s/admin/services", dir);
	(void) mkdir(tdir, (mode_t)00755);
}

/*
 * Function:	SetupPreKBI()
 * Description: This function creates the necessary directories on pre
 *		KBI systems
 *
 * Scope:	private
 * Parameters:
 *		None
 * Return:
 *		int		0 	= Success
 *				not 0 	= Failure
 */

int
SetupPreKBI(void)
{

	Module		*mod;
	Module		*prodmod;

	/*
	 * Loop through the module list to find the product that is
	 * going to be used to upgrade the system.
	 */

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type != INSTALLED_SVC &&
		    mod->info.media->med_type != INSTALLED &&
		    mod->sub->type == PRODUCT &&
		    strcmp(mod->sub->info.prod->p_name, "Solaris") == 0)
			break;
	}

	/*
	 * If we found the upgrade product then assign the product module
	 * structure.
	 */

	if (mod)
		prodmod = mod->sub;

	/*
	 * Otherwise, we could not find the Product to use to upgrade the
	 * system.  This is a problem, so we're out of here.
	 */

	else
		return (-1);
	/*
	 * If we are not running in simulation and the system being upgraded
	 * is pre-KBI.
	 */

	if (is_KBI_service(prodmod->info.prod)) {

		/* make new directories if need be */

		if (! is_new_var_sadm("/")) {
			MakePostKBIDirectories();
		}
	}
	return (0);
}

/*
 * Function:	log_spacechk_failure
 * Description:
 *
 * Scope:	PUBLIC
 * Parameters:
 */
void
log_spacechk_failure(int code)
{
	char *nullstring = "NULL";

	/*
	 *  If sp_err_path is null, make sure it points to a valid
	 *  string so that none of these printfs coredump.
	 */
	if (sp_err_path == NULL)
		sp_err_path = nullstring;

	switch (code) {
	case SP_ERR_STAT:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Stat failed: %s\n"), sp_err_path);
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "errno = %d\n"), sp_err_subcode);
		break;

	case SP_ERR_STATVFS:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Statvfs failed: %s\n"), sp_err_path);
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "errno = %d\n"), sp_err_subcode);
		break;

	case SP_ERR_GETMNTENT:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Getmntent failed: errno = %d\n"), sp_err_subcode);
		break;

	case SP_ERR_MALLOC:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Malloc failed.\n"));
		break;

	case SP_ERR_PATH_INVAL:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Internal error: invalid path: %s\n"), sp_err_path);
		break;

	case SP_ERR_CHROOT:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Failure doing chroot.\n"));
		break;

	case SP_ERR_NOSLICES:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "No upgradable slices found.\n"));
		break;

	case SP_ERR_POPEN:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Popen failed: %s\n"), sp_err_path);
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "error = %d\n"), sp_err_subcode);
		break;

	case SP_ERR_OPEN:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Open failed: %s\n"), sp_err_path);
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "errno = %d\n"), sp_err_subcode);
		break;

	case SP_ERR_PARAM_INVAL:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Internal error: invalid parameter.\n"));
		break;

	case SP_ERR_STAB_CREATE:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Space check failed: couldn't create file-system "
		    "table.\n"));
		if (sp_err_code != SP_ERR_STAB_CREATE) {
			(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
			    "Reason for failure:\n"));
			log_spacechk_failure(sp_err_code);
		}
		break;

	case SP_ERR_CORRUPT_CONTENTS:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Space check failed: package database is corrupted.\n"));
		break;

	case SP_ERR_CORRUPT_PKGMAP:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Space check failed: package's pkgmap is not in "
		    "the correct format.\n"));
		break;

	case SP_ERR_CORRUPT_SPACEFILE:
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Space check failed: package's spacefile "
		    "is not in the correct format.\n"));
		break;

	}
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*ARGSUSED0*/
/*
 * Function:	catch_prog_sig
 * Description:
 *
 * Scope:	PUBLIC
 * Parameters:
 */
static void
catch_prog_sig(int sig)
{
/* localized buffer length definitions-used for sscanf */
#define	STAGESTRSIZE 32		/* stage string */
#define	STSZONENAMESIZE 132	/* status display line zone list */
	FILE		*fp;
	char		buf[BUFSIZ + 1];
	char		stagestr[STAGESTRSIZE + 1];
	char		detail[MAXPATHLEN + 1];
	ValProgress	Progress;
	int		num_fields = 0;
	ValStage	stage = VAL_UNKNOWN;
	int		total, completed;
	char		zonename[STSZONENAMESIZE + 1]; /* status line zones */

	/*
	 * We may get another signal before we're done handling this
	 * one, so hold one in the queue if it comes in.  If more than
	 * one comes in, they get dropped - harmless.
	 */
	(void) sighold(SIGUSR1);

	if ((fp = fopen("/tmp/upg_prog", "r")) != NULL) {
		if (fgets(buf, BUFSIZ, fp))
			num_fields = sscanf(buf,
			    "%"STRINGIZE(STAGESTRSIZE)"s "
			    "%"STRINGIZE(MAXPATHLEN)"s "
			    "%d %d "
			    "%"STRINGIZE(STSZONENAMESIZE)"s",
			    stagestr, detail, &total, &completed, zonename);
	}
	(void) fclose(fp);
	if (num_fields == 4 || num_fields == 5) {
		if (num_fields < 5) /* zone name list optional */
			zonename[0] = '\0';
		if (streq(stagestr, "local_pkgadd"))
			stage = VAL_EXEC_LOCAL_PKGADD;
		else if (streq(stagestr, "virtual_pkgadd"))
			stage = VAL_EXEC_VIRTUAL_PKGADD;
		else if (streq(stagestr, "pkgrm"))
			stage = VAL_EXEC_PKGRM;
		else if (streq(stagestr, "removef"))
			stage = VAL_EXEC_REMOVEF;
		else if (streq(stagestr, "spool_local_pkg"))
			stage = VAL_EXEC_LOCAL_SPOOL;
		else if (streq(stagestr, "spool_virtual_pkg"))
			stage = VAL_EXEC_VIRTUAL_SPOOL;
		else if (streq(stagestr, "rm_template"))
			stage = VAL_EXEC_RMTEMPLATE;
		else if (streq(stagestr, "rmdir"))
			stage = VAL_EXEC_RMDIR;
		else if (streq(stagestr, "remove_svc"))
			stage = VAL_EXEC_RMSVC;
		else if (streq(stagestr, "remove_patch"))
			stage = VAL_EXEC_RMPATCH;
		else if (streq(stagestr, "rm_template_dir"))
			stage = VAL_EXEC_RMTEMPLATEDIR;
		if (stage != VAL_UNKNOWN &&
		    total > 0 &&
		    exec_callback_proc) {
			Progress.valp_stage = stage;
			Progress.valp_detail = detail;
			Progress.valp_zonename = zonename;
			Progress.valp_percent_done =
			    (int)(((float)completed/(float)total) * 100);
			(void) exec_callback_proc(exec_callback_arg,
			    (void *)&Progress);
		}
	}
	(void) signal(SIGUSR1, catch_prog_sig);
}

/*
 * Function:	gen_upgrade_script
 * Description:
 *
 * Scope:	PUBLIC
 * Parameters:
 */

int
gen_upgrade_script(int mountfirst, int writeboot, int do_sync)
{
	Module	*mod, *prodmod;
	int (*mountscript)(FILE *, int) = NULL;
	void (*installbootscript)(FILE *) = NULL;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type != INSTALLED_SVC &&
		    mod->info.media->med_type != INSTALLED &&
		    mod->sub->type == PRODUCT &&
		    strcmp(mod->sub->info.prod->p_name, "Solaris") == 0)
			break;
	}
	if (mod)
		prodmod = mod->sub;
	else
		return (FAILURE);

	/*
	 * If there is a symbolic link in the old location,
	 * remove it.  If there is a file, not a sym link,
	 * move it to the new location in the dated form.
	 */
	rm_link_mv_file(old_scriptpath, new_scriptpath);

	/*
	 * If there is a symbolic link in the new location,
	 * remove it.  If there is a file, not a sym link,
	 * move it to the new location in the dated form.
	 */
	rm_link_mv_file(new_scriptpath, new_scriptpath);

	if (mountfirst != 0) {
		mountscript = gen_mount_script;
	}

	if (writeboot != 0) {
		installbootscript = gen_installboot;
	}

	set_umount_script_fcn(mountscript, installbootscript);

	(void) write_script(prodmod, do_sync);

	return (SUCCESS);
}

/*
 * Function:	execute_upgrade
 * Description:
 *
 * Scope:	PUBLIC
 * Parameters:
 */

int
execute_upgrade(OpType Operation, char *logFileName,
    int (*callback_proc)(void *, void *),
    void *callback_arg)
{
	Module	*mod, *prodmod;
	int	status;
	char	cmd[MAXPATHLEN];
	int	pid;
	pid_t	w;
	int	fd;
	ValProgress Progress;
	char	*restart_flag;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type != INSTALLED_SVC &&
		    mod->info.media->med_type != INSTALLED &&
		    mod->sub->type == PRODUCT &&
		    strcmp(mod->sub->info.prod->p_name, "Solaris") == 0)
			break;
	}
	if (mod)
		prodmod = mod->sub;
	else
		return (-1);

	/*
	 * Set up the upgrade command
	 */

	if (Operation == SI_RECOVERY) {
		restart_flag = "restart";
	} else {
		restart_flag = "";
	}
	(void) snprintf(cmd, MAXPATHLEN, "/bin/sh %s/%s %s %ld %s",
	    get_rootdir(), upgrade_script_path(prodmod->info.prod),
	    (streq(get_rootdir(), "") ? "/" : get_rootdir()),
	    getpid(), restart_flag);

	exec_callback_proc = callback_proc;
	exec_callback_arg = callback_arg;
	(void) signal(SIGUSR1, catch_prog_sig);

	/*
	 * Call the user's callback if provided with the begin state
	 */

	if (exec_callback_proc) {
		Progress.valp_percent_done = 0;
		Progress.valp_stage = VAL_UPG_BEGIN;
		Progress.valp_detail = NULL;

		if (exec_callback_proc(exec_callback_arg,
		    (void *) &Progress)) {
			return (-1);
		}
	}

	if ((pid = fork()) == 0) {
		fd = open(logFileName, O_WRONLY);
		if (fd == -1) {
			/* report error */
			return (-1);
		}
		(void) close(1);
		(void) dup(fd);
		(void) close(2);
		(void) dup(fd);
		(void) execlp("/bin/sh", "sh", "-c", cmd, (char *)NULL);
		/* shouldn't be here, but ... */
		return (-1);
	} else if (pid == -1) {
		return (-1);
	} else {

		/*
		 * Wait for the chlid process to exit
		 */

		do {
			w = waitpid(pid, &status, 0);
		} while (w == -1 && errno == EINTR);

		/*
		 * Get the exit status from the child process
		 */

		if (WIFEXITED(status)) {
			status = (int)((char)(WEXITSTATUS(status)));
		} else if (WIFSIGNALED(status)) {
			return (-1);
		} else if (WIFSTOPPED(status)) {
			return (-1);
		}

		/*
		 * Call the user's callback if provided with the end state
		 */

		if (exec_callback_proc) {
			Progress.valp_percent_done = 100;
			Progress.valp_stage = VAL_UPG_END;
			Progress.valp_detail = NULL;

			if (exec_callback_proc(exec_callback_arg,
			    (void *) &Progress)) {
				return (-1);
			}
		}
	}
	(void) sigignore(SIGUSR1);

	/*
	 * Finish up the upgrade process by applying driver updates
	 * and creating multiboot archive.
	 */
	if (IsIsa("i386")) {
		(void) snprintf(cmd, sizeof (cmd),
		    "/sbin/install-finish %s upgrade >> %s 2>&1",
		    get_rootdir(), logFileName);
		(void) system(cmd);
	}
	return (status);
}
