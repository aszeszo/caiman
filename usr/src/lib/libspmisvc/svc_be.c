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



/*
 * Module:	svc_be.c
 * Group:	libspmisvc
 * Description:
 *	Module for handling high-level Boot Environment functions
 */

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <assert.h>

#include "spmicommon_api.h"
#include "spmiapp_api.h"
#include "svc_strings.h"

/* Local functions */
static void	print_arg(FILE *, char *, char *);
static void	begin_service(FILE *, char *);
static void	end_service(FILE *);
static boolean_t in_service = B_FALSE;


/* ---------------------- public functions ----------------------- */

/*
 * Name:		save_bootenv_config
 * Description:	Writes out the bootenv configuration file
 * Scope:	public
 * Arguments:	cmds - The commands representing the bootenv configuration
 *		cmdnum - How many commands
 *		rootdir - The root directory of the BE to save them in
 * Returns:	B_TRUE - write was successful
 *		B_FALSE otherwise
 */
boolean_t
save_bootenv_config(BootEnvCommand *cmds, int cmdnum, char *file)
{
	int i, j;
	BootEnvCommand *cmd;
	BootEnvCreateFilesys *fs;
	char	*tmpfp;
	FILE	*outfp;
	char	fsspec[MAXPATHLEN];

	/* open temporary file for writing */

	if ((tmpfp = tempnam("/tmp", "be_conf")) == NULL) {
		write_notice(ERRMSG, MSG_BE_TMPFILE);
		return (B_FALSE);
	}

	if ((outfp = fopen(tmpfp, "w")) == NULL) {
		write_notice(ERRMSG, MSG_BE_TMPFILE);
		return (B_FALSE);
	}

	for (i = 0; i < cmdnum; i++) {
		cmd = &cmds[i];
		switch (cmd->cmdtype) {
		case BootEnvCreate:
			begin_service(outfp, "createBootEnvironment");
			if (cmd->cmd.createbe.bename != NULL) {
				print_arg(outfp, "bootEnvironmentName",
				    cmd->cmd.createbe.bename);
			}
			if (cmd->cmd.createbe.source_bename != NULL) {
				print_arg(outfp, "sourceBootEnvironmentName",
				    cmd->cmd.createbe.source_bename);
			}
			for (j = 0; j < cmd->cmd.createbe.num_filesys; j++) {
				fs = &(cmd->cmd.createbe.filesys[j]);

				/* make the fsspec line */
				snprintf(fsspec, MAXPATHLEN, "%s:%s:%s",
				    fs->mntpt, fs->device, fs->fstyp);
				print_arg(outfp, "fileSystem", fsspec);
			}
			end_service(outfp);
			break;
		default:
		    /* unknown command type */
		    write_notice(ERRMSG, MSG_BE_UNKNOWN_TYPE, cmd->cmdtype);
		    return (B_FALSE);
		}
	}

	fclose(outfp);

	/*
	 * only do the actual installation of the temporary file if this
	 * is a live run.  If a simulation, leave the
	 * temp file around for debugging.
	 */
	if (!GetSimulation(SIM_EXECUTE)) {
		if (_copy_file(file, tmpfp) == ERROR) {
			write_notice(ERRMSG, MSG_BE_INSTALL_FAILED, file);
			return (B_FALSE);
		}

		(void) unlink(tmpfp);
	}

	return (B_TRUE);

}

/* ---------------------- private functions ----------------------- */

/*
 * Name:		print_arg
 * Description:	Writes out the a bootenv service argument
 * Scope:	public
 * Arguments:	outfp - where to write the argument
 *		name - Name of argument
 *		rootdir - The root directory of the BE to save them in
 * Returns:	none
 */
static void
print_arg(FILE *outfp, char *name, char *val)
{
	assert(in_service);
	fprintf(outfp,
	    "<argument name=\"%s\" value=\"%s\" />\n",
	    name, val);
}

/*
 * Name:		begin_service
 * Description:	Begins a new bootenv service in the BE config file
 * Scope:	public
 * Arguments:	outfp - where to write the argument
 *		name - Name of service
 * Returns:	none
 */
static void
begin_service(FILE *outfp, char *name)
{
	assert(!in_service);
	fprintf(outfp,
	    "<bootenv service=\"%s\">\n", name);
	in_service = B_TRUE;
}

/*
 * Name:		end_service
 * Description:	Ends current service being output to BE config file
 * Scope:	public
 * Arguments:	outfp - where to write the terminator
 * Returns:	none
 */
static void
end_service(FILE *outfp)
{
	assert(in_service);
	fprintf(outfp,
	    "</bootenv>\n");
	in_service = B_FALSE;
}

/*
 * Name:	validate_be_name
 * Description:	Give a BE name, determine whether or not the BE name is valid.
 *		If it's invalid, give error msg and die.
 * Arguments:	beName	- [RO, *RO] (char *)
 *			Pointer to string containg name of the boot environment.
 * Returns:	none
 */

BeNameErr_t
validate_be_name(char *beName)
{
	int cnt;
	char *p;
	int mbcnt = 0;
	wchar_t wd;

	for (cnt = 0, p = beName; *p != '\0'; cnt++,
		p += (mbcnt > 0) ? mbcnt : 1) {
		mbcnt = mbtowc(&wd, p, MB_CUR_MAX);
		if (mbcnt == 1) {
			/*
			 * Character is single-byte: check for
			 * disallowed ascii characters.
			 */
			switch (wd) {
			case '\t':	/* control-i (tab) */
			case '"':	/* double quote (") */
			case ' ':	/* space () */
			case ':':	/* colon (:) */
			case '<':	/* less than (<) */
			case '>':	/* greater than (>) */
			case '?':	/* question-mark (?) */
			case '$':	/* dollar-sign ($) */
			case '\'':	/* single quote (') */
			case '\\':	/* back slash (\) */
			case '`':	/* back quote (`) */
			    return (BE_NAME_INVALID_CHAR);
			}
		} else if (mbcnt > 1) {
			return (BE_NAME_MB_CHAR);
		}
	}

	/*
	 * cnt is the number of characters (not bytes) in the
	 * BE name: an empty string is illegal.
	 */

	if (cnt < BE_NAME_MIN) {
		return (BE_NAME_TOO_SHORT);
	} else if (cnt > BE_NAME_MAX) {
		return (BE_NAME_TOO_LONG);
	}

	return (BE_NAME_OK);
}
