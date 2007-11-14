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

#pragma ident	"@(#)soft_admin.c	1.3	07/11/12 SMI"

#include "spmisoft_lib.h"
#include <string.h>
#include <stdlib.h>

/* Public Function Prototypes */

char *	swi_getset_admin_file(char *);
int     swi_admin_write(char *, Admin_file *);

/* Library Function Prototypes */

void		_setup_admin_file(Admin_file *);
void		_setup_pkg_params(PkgFlags *);
int		_build_admin(Admin_file *);

/* Local Function Prototypes */

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * admin_file()
 * 	Get/set name of current admin file used during pkgadd/pkgrm. If
 *	'filename' is NULL, get the name of the admin file, otherwise, set
 *	the name of the admin file to 'filename'.
 * Parameters:
 *	filename  - pathname of admin file (for setting only)
 * Return:
 *	NULL	  - default return value for set
 *	char *	  - return value for get; name of admin file
 * Status:
 *	public
 */
char *
swi_getset_admin_file(char * filename)
{
	static char	adminfile[MAXPATHLEN+1];

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("getset_admin_file");
#endif

	if (filename != (char *) NULL)
		(void) strcpy((char *) adminfile, filename);

	if (adminfile[0] == '\0')
		return ((char *) NULL);

	return ((char *) adminfile);
}

/*
 * admin_write()
 *	Writes the data contained in 'admin' to the admin file. If 'filename'
 *	is NULL, a temporary name (/tmp/pkg*) is created. 'filename' (or the
 *	temporary file name) is made the default admin_file name via
 *	getset_admin_file().
 *	NOTE:	Data is not logged into the file if execution
 *		simulation is set
 * Parameters:
 *	filename    - user supplied file name to use for admin file (NULL if
 *		      a temporary file is desired)
 *	admin	    - pointer to structure continaing admin file data to be
 *		      stored
 * Return:
 *	SUCCESS	    - successful write to admin file
 *	ERR_INVALID - 'filename' can't be opened for writing
 *	ERR_NOFILE  - 'filename' was NULL and a temporary filename could not
 *		      be created
 *	ERR_SAVE    - call to getset_admin_file() to save 'filename' failed
 * Status:
 *	public
 */
int
swi_admin_write(char * filename, Admin_file * admin)
{
	FILE	*fp;
	static char tmpname[] = "/tmp/pkgXXXXXX";

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("admin_write");
#endif

	if (filename == (char *)NULL) {
		(void) mktemp(tmpname);
		if (tmpname[0] == '\0')
			return (ERR_NOFILE);

		filename = tmpname;
	}
	/* if not simulating execution, write the file */
	if (!GetSimulation(SIM_EXECUTE)) {
		fp = fopen(filename, "w");
		if (fp == (FILE *)0)
			return (ERR_INVALID);

		(void) fprintf(fp, "mail=%s\n", admin->mail);
		(void) fprintf(fp, "instance=%s\n", admin->instance);
		(void) fprintf(fp, "partial=%s\n", admin->partial);
		(void) fprintf(fp, "runlevel=%s\n", admin->runlevel);
		(void) fprintf(fp, "idepend=%s\n", admin->idepend);
		(void) fprintf(fp, "rdepend=%s\n", admin->rdepend);
		(void) fprintf(fp, "space=%s\n", admin->space);
		(void) fprintf(fp, "setuid=%s\n", admin->setuid);
		(void) fprintf(fp, "conflict=%s\n", admin->conflict);
		(void) fprintf(fp, "action=%s\n", admin->action);
		(void) fprintf(fp, "basedir=%s\n", admin->basedir);
		(void) fclose(fp);
	}
	/* set pointer to adminfile for future use */
	if(getset_admin_file(filename) == NULL)
		return(ERR_SAVE);

	return (SUCCESS);
}


/*
 * Function:	_build_admin
 * Description:	Create the admin file for initial install only.
 * Scope:	Internal
 * Parameters:	admin	- non-NULL pointer to an Admin_file structure
 * Return:	NOERR	- success
 *		ERROR	- setup attempt failed
 */
int
_build_admin(Admin_file *admin)
{
	static char	_lbase[MAXPATHLEN] = "";

	/* verify admin is valid */
	if (admin == NULL)
		return (ERROR);

	/* if the basedir hasn't changed, return success */
	if (admin->basedir != NULL &&
			strcmp(admin->basedir, _lbase) == 0)
		return (NOERR);

	/* create and save admin file */
	if (admin_write(getset_admin_file((char *)NULL), admin))
		return (ERROR);

	if (admin->basedir != NULL)
		(void) strcpy(_lbase, admin->basedir);

	return (NOERR);
}

/*
 * Function:	_setup_admin_file
 * Description:	Initialize the fields of an existing admin structure
 * Scope:	internal
 * Parameters:	admin	- non-NULL pointer to the Admin structure
 *			  to be initialized
 * Return:	none
 */
void
_setup_admin_file(Admin_file *admin)
{
	static char 	nocheck[] = "nocheck";
	static char 	unique[] = "unique";
	static char 	quit[] = "quit";
	static char 	blank[] = " ";

	if (admin != NULL) {
		admin->mail = blank;
		admin->instance = unique;
		admin->partial = nocheck;
		admin->runlevel = nocheck;
		admin->idepend = nocheck;
		admin->rdepend = quit;
		admin->space = nocheck;
		admin->setuid = nocheck;
		admin->action = nocheck;
		admin->conflict = nocheck;
		admin->basedir = blank;
	}
}

/*
 * Function:	_setup_pkg_params
 * Description:	Initialize the package params structure to be used
 *		during pkgadd calls.
 * Scope:	internal
 * Parameters:	params	- non-NULL pointer to the PkgFlags structure to be
 *			  initialized
 * Return:	none
 */
void
_setup_pkg_params(PkgFlags *params)
{
	if (params != NULL) {
		params->silent = 1;
		params->checksum = 1;
		params->notinteractive = 1;
		params->accelerated = 1;
		params->spool = NULL;
		params->admin_file = (char *)getset_admin_file(NULL);
		params->basedir = get_rootdir();
	}
}
