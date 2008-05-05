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
 * Module:	svc_flash.c
 * Group:	libspmisvc
 * Description:
 *	Module for handling high-level Flash archive manipulation functions
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <dirent.h>
#include <dlfcn.h>
#include <link.h>

#include "spmicommon_api.h"
#include "spmiapp_api.h"
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "svc_flash.h"

#define	MAXHASHLEN		512
#define	MAX_ARCHIVER_LEN	20

#define	CPIO_WRAPPER	"/usr/sbin/install.d/stripcpioerr"

/* Local globals */
static FlashOps flash_ops[] = {
	{ NULL, NULL, NULL, NULL }, /* Intentionally NULL */
	{
		FLARNFSOpen,
		FLARNFSReadLine,
		FLARNFSExtract,
		FLARNFSClose
	},
	{
		FLARHTTPOpen,
		FLARHTTPReadLine,
		FLARHTTPExtract,
		FLARHTTPClose
	},
	{
		FLARFTPOpen,
		FLARFTPReadLine,
		FLARFTPExtract,
		FLARFTPClose
	},
	{
		FLARLocalFileOpen,
		FLARLocalFileReadLine,
		FLARLocalFileExtract,
		FLARLocalFileClose
	},
	{
		FLARLocalTapeOpen,
		FLARLocalTapeReadLine,
		FLARLocalTapeExtract,
		FLARLocalTapeClose
	},
	{
		FLARLocalDeviceOpen,
		FLARLocalDeviceReadLine,
		FLARLocalDeviceExtract,
		FLARLocalDeviceClose
	},
	{ NULL, NULL, NULL, NULL }  /* The next one */
};

static FlashOps old_http_flashops = {
	_old_FLARHTTPOpen,
	_old_FLARHTTPReadLine,
	_old_FLARHTTPExtract,
	_old_FLARHTTPClose
};

static int		_is_flash_install = 0;
static FlashArchive	**flars = NULL;
static int		flar_count = 0;

static char   archiver[MAX_ARCHIVER_LEN] = "";
static char   archiver_cmd[MAX_ARCHIVER_LEN] = "";
static char   archiver_arguments[MAX_ARCHIVER_LEN] = "";

/* Local functions */
static FlashError	_init_flash_ops(FlashArchive *);
static FlashError	_read_ident_section(FlashArchive *, char ***);
static void		_dump_ident_section(FlashArchive *);
static FlashError	_stop_writer(FlashArchive *, FILE *);
static FlashError	_start_writer(FlashArchive *, FILE **);
static FlashError	_valid_cookie(FlashArchive *, char *);
static FlashError	_parse_ident(FlashArchive *, char **);
static int	_streq(char *, char *);
static FlashError	_dir_state_check(FlashArchive *, int);
static FlashError	_dir_exec(char *);
static FlashError	_file_state_check_s(char *, char *);
static int	_namecmp(char *, char *, int);
static int		_select_archiver_arguments(FlashArchive *);

/* ---------------------- public functions ----------------------- */

/*
 * Name:	FLARInitialize
 * Description:	Initialize a new FlashArchive structure, setting defaults
 *		as appropriate.
 * Scope:	public
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The pre-allocated FlashArchive structure to be
 *			  initialized.
 * Returns:	none
 */
void
FLARInitialize(FlashArchive *flar)
{
	(void) memset(flar, 0, sizeof (FlashArchive));
	flar->type = FlashRetUnknown;
	flar->ident.arc_method = FLARArc_CPIO;
	flar->ident.arc_size = 0;
	flar->ident.unarc_size = 0;
	flar->ident.num_desc_lines = 0;
	flar->ident.numuk = 0;
	flar->ident.type = "";
}

/*
 * Name:	FLAROpen
 * Description:	Open and verify a Flash archive.  The open is done in a method
 *		specific to the retrieval method.  After the archive has been
 *		opened, the archive cookie is checked for compatibility, and
 *		the identification section is read and parsed.
 * Scope:	public
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The initialized archive to open
 * Returns:	FlErrSuccess	- The archive was opened and verified correctly.
 *		<various>	- Failure codes specific to the retrieval
 *				  method used
 */
FlashError
FLAROpen(FlashArchive *flar)
{
	FlashError status;
	char *bufptr;
	char **bufarr;
	int i;

	if (!flar->ops) {
		if ((status = _init_flash_ops(flar)) != FlErrSuccess) {
			return (status);
		}
	}

	/* Open the archive */
	if ((status = flar->ops->open(flar)) != FlErrSuccess) {
		return (status);
	}

	/*
	 * Make sure it's a valid Flash Archive by reading in the version
	 * and identification sections.
	 */

	/* version */
	if ((status = flar->ops->readline(flar, &bufptr)) != FlErrSuccess) {
		write_notice(ERRMSG, MSG_READ_FAILED, FLARArchiveWhere(flar));
		return (status);
	}

	if ((status = _valid_cookie(flar, bufptr)) != FlErrSuccess) {
		return (status);
	}

	/* identification section */
	if ((status = _read_ident_section(flar, &bufarr)) != FlErrSuccess) {
		write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_READ_IDENT,
			FLARArchiveWhere(flar));
		return (status);
	}

	status = _parse_ident(flar, bufarr); /* sets errmsg */
	if (bufarr) {
		for (i = 0; bufarr[i]; i++) {
			free(bufarr[i]);
		}
		free(bufarr);
		if (status != FlErrSuccess) {
			return (status);
		}
	}

	/* setting archiver and its arguments */
	if (_select_archiver_arguments(flar) != 0) {
		write_notice(ERRMSG, MSG0_FLASH_UNKNOWN_ARC_METHOD,
			flar->ident.arc_method);
		return (FlErrInvalid);
	}

	return (FlErrSuccess);
}

/*
 * Processing predeployment stage for Flash Update
 */

FlashError
FLARUpdatePreDeployment(FlashArchive *flar,
			char *local_customization,
			int check_master,
			int check_contents,
			int forced_deployment)
{
	FlashError status;
	char *bufptr;
	char **bufarr;
	int i, sysres;
	FILE *fp;
	char cmd[512];
	char line[PATH_MAX] = "none";
	FlashError res;
	int TestRun = 0;
	int olen = 0;

	write_status(SCR, LEVEL0, MSG0_FLASH_PREDEPLOYMENT);

	if (GetSimulation(SIM_EXECUTE) && !(GetSimulation(SIM_SYSSOFT))) {
		TestRun = 1;
	}

	if (!TestRun) {
		(void) sprintf(cmd,
			"/usr/bin/rm -rf /tmp/flash_tmp;"
			"/usr/bin/mkdir -p /tmp/flash_tmp;");

		if (system(cmd) != 0) {
			write_notice(ERRMSG,
			    MSG0_FLASH_UNABLE_TO_MAKE_FLASH_TMP);
			return (FlErrPredeploymentExtraction);
		}
	}

	write_status(SCR, LEVEL0, MSG0_FLASH_VALIDATION);

	(void) snprintf(line, sizeof (line),
			"%s/etc/flash/master", get_rootdir());
	if ((fp = fopen(line, "r")) != NULL) {
		fgets(line, PATH_MAX, fp);
		i = strlen(line);

		if (line[i - 1] == '\n') {
			line[i - 1] = '\0';
		}
		fclose(fp);
	} else {
		(void) sprintf(line, "none");
	}

	if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
		write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_MANIFEST);
		return (status);
	}

	if (check_master && (!streq(flar->ident.cr_master, line))) {
		write_notice(ERRMSG, MSG0_FLASH_WRONG_MASTER,
		    line, flar->ident.cr_master);
		return (FlErrWrongMaster);
	}

	flar -> manifest = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_MANIFEST)) {
		/* Found the beginning of the manifest section */

		flar -> manifest = 1;

		if (check_contents) {
			/* Process manifest */
			status = _dir_state_check(flar, forced_deployment);
			if (status != FlErrSuccess) {
				return (status);
			}
		} else {
			/* Skip manifest */
			for (;;) {
				if ((status =
					flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
					write_notice(ERRMSG,
					    MSG0_FLASH_UNABLE_TO_SKIP_MANIFEST);
					return (status);
				}
				if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_MANIFEST)) {
		/* Found the beginning of the files section */
					break;
				}
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
			write_notice(ERRMSG,
			    MSG0_FLASH_UNABLE_TO_FIND_PREDEPLOYMENT);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_MANIFEST_NOT_FOUND);
	}

	flar -> predeployment = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_PREDEPLOYMENT)) {
		/*
		 * Found the beginning of the predeployment section.
		 * Store, uudecode, uncompress and expand predeployment archive
		 * in temporary directory
		 */

		flar -> predeployment = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/predeployment", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_READ_PREDEPLOYMENT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_PREDEPLOYMENT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

			/*
			 * Create command for generic type of archive format.
			 * Based on the  archiver, archiver_cmd,
			 * archiver_arguments values command will be modified.
			 */
			olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
			    "/usr/bin/uudecode /tmp/predeployment;"
			    "/usr/bin/uncompress /tmp/predeployment.%s.Z;"
			    "cd /tmp/flash_tmp;"
			    "%s %s /tmp/predeployment.%s;"
			    "/usr/bin/rm -f /tmp/predeployment*",
			    archiver, archiver_cmd, archiver_arguments,
			    archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_PREDEPLOYMENT);
				return (FlErrPredeploymentExtraction);
			}
		}
		if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
			write_notice(ERRMSG,
			    MSG0_FLASH_UNABLE_TO_FIND_POSTDEPLOYMENT);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_PREDEPLOYMENT_NOT_FOUND);
	}

	flar -> postdeployment = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_POSTDEPLOYMENT)) {
		/*
		 * Found the beginning of the postdeployment section.
		 * Store, uudecode, uncompress and expand postdeployment archive
		 * in temporary directory
		 */

		flar -> postdeployment = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/postdeployment", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr)) !=
			    FlErrSuccess) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_READ_POSTDEPLOYMENT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_POSTDEPLOYMENT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

			/*
			 * Create command for generic type of archive format.
			 * Based on the  archiver, archiver_cmd,
			 * archiver_arguments values command will be modified.
			 */
			olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
			    "/usr/bin/uudecode /tmp/postdeployment;"
			    "/usr/bin/uncompress /tmp/postdeployment.%s.Z;"
			    "cd /tmp/flash_tmp;"
			    "%s %s /tmp/postdeployment.%s;"
			    "/usr/bin/rm -f /tmp/postdeployment*",
			    archiver, archiver_cmd, archiver_arguments,
			    archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_POSTDEPLOYMENT);
				return (FlErrPostdeploymentExtraction);
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr)) !=
		    FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_REBOOT);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_POSTDEPLOYMENT_NOT_FOUND);
	}

	flar -> reboot = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_REBOOT)) {
		/*
		 * Found the beginning of the reboot section.
		 * Store, uudecode, uncompress and expand reboot archive
		 * in temporary directory
		 */

		flar -> reboot = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/reboot", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_READ_REBOOT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_REBOOT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

			/*
			 * Create command for generic type of archive format.
			 * Based on the archiver, archiver_cmd and
			 * archiver_arguments values command will be modified.
			 */
			olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
				"/usr/bin/uudecode /tmp/reboot;"
				"/usr/bin/uncompress /tmp/reboot.%s.Z;"
				"cd /tmp/flash_tmp;"
				"%s %s /tmp/reboot.%s;"
				"/usr/bin/rm -f /tmp/reboot*", archiver,
				archiver_cmd, archiver_arguments, archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
					MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_REBOOT);
				return (FlErrRebootExtraction);
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_FILES);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_REBOOT_NOT_FOUND);
	}

	/*
	 * fast-forward to the files section
	 */

	while (!streq(bufptr, FLASH_SECTION_BEGIN "=" FLASH_SECTION_FILES)) {
		if ((status = flar->ops->readline(flar, &bufptr)) !=
		    FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_FILES);
			return (status);
		}
	}

	if (local_customization != NULL) {
		(void) snprintf(cmd, sizeof (cmd), "%s/predeployment",
					local_customization);
		write_status(SCR, LEVEL0, MSG0_LOCAL_CUSTOMIZATION);
		if (!TestRun) _dir_exec(cmd);
		write_status(SCR, LEVEL0, MSG0_LOCAL_CUSTOMIZATION_DONE);
	} else {
		write_status(SCR, LEVEL0, MSG0_NO_LOCAL_CUSTOMIZATION);
	}

	if (!TestRun) {
		if (flar -> predeployment) {
			(void) sprintf(cmd,
				"/tmp/flash_tmp/predeployment_processing");
			if (system(cmd) == 0) {
				return
				    (_dir_exec("/tmp/flash_tmp/predeployment"));
			} else {
				write_notice(ERRMSG,
				    MSG0_FLASH_SYSTEM_PREDEPLOYMENT_FAILURE);
				return (FlErrSysPredeployment);
			}
		}
	}
	return (FlErrSuccess);
}

/*
 * Processing predeployment stage for Flash Install
 */

FlashError
FLARInitialPreDeployment(FlashArchive *flar, char *local_customization)
{
	FlashError status;
	char *bufptr;
	char **bufarr;
	int i, sysres;
	FILE *fp;
	char cmd[512];
	FlashError res;
	int TestRun = 0;
	int olen = 0;

	write_status(SCR, LEVEL0, MSG0_FLASH_PREDEPLOYMENT);

	if (GetSimulation(SIM_EXECUTE) && !(GetSimulation(SIM_SYSSOFT))) {
		TestRun = 1;
	}

	if (!TestRun) {
		(void) sprintf(cmd,
			"/usr/bin/rm -rf /tmp/flash_tmp;"
			"/usr/bin/mkdir -p /tmp/flash_tmp;");
	}

	if (system(cmd) != 0) {
		write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_MAKE_FLASH_TMP);
		return (FlErrPredeploymentExtraction);
	}

	if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
		write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_PREDEPLOYMENT);
		return (status);
	}


	flar -> manifest = 0;
	flar -> predeployment = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_PREDEPLOYMENT)) {

		/*
		 * Found the beginning of the predeployment section.
		 * Store, uudecode, uncompress and expand predeployment archive
		 * in temporary directory
		 */

		flar -> predeployment = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/predeployment", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_READ_PREDEPLOYMENT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
				FLASH_SECTION_PREDEPLOYMENT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

		/*
		 * Create command for generic type of archive format.
		 * Based on the  archiver, archiver_cmd, archiver_arguments
		 * values command will be modified.
		 */
		olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
			"/usr/bin/uudecode /tmp/predeployment;"
			"/usr/bin/uncompress /tmp/predeployment.%s.Z;"
			"cd /tmp/flash_tmp;"
			"%s %s /tmp/predeployment.%s;"
			"/usr/bin/rm -f /tmp/predeployment*",
			archiver, archiver_cmd, archiver_arguments, archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
					MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_PREDEPLOYMENT);
				return (FlErrPredeploymentExtraction);
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr))
						!= FlErrSuccess) {
			write_notice(ERRMSG,
			    MSG0_FLASH_UNABLE_TO_FIND_POSTDEPLOYMENT);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_PREDEPLOYMENT_NOT_FOUND);
	}

	flar -> postdeployment = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_POSTDEPLOYMENT)) {
		/*
		 * Found the beginning of the postdeployment section.
		 * Store, uudecode, uncompress and expand postdeployment archive
		 * in temporary directory
		 */

		flar -> postdeployment = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/postdeployment", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_READ_POSTDEPLOYMENT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_POSTDEPLOYMENT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

			/*
			 * Create command for generic type of archive format.
			 * Based on the  archiver, archiver_cmd,
			 * archiver_arguments values command will be modified.
			 */
			olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
			    "/usr/bin/uudecode /tmp/postdeployment;"
			    "/usr/bin/uncompress /tmp/postdeployment.%s.Z;"
			    "cd /tmp/flash_tmp;"
			    "%s %s /tmp/postdeployment.%s;"
			    "/usr/bin/rm -f /tmp/postdeployment*",
			    archiver, archiver_cmd, archiver_arguments,
			    archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_POSTDEPLOYMENT);
				return (FlErrPostdeploymentExtraction);
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr)) !=
		    FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_REBOOT);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_POSTDEPLOYMENT_NOT_FOUND);
	}

	flar -> reboot = 0;

	if (streq(bufptr, FLASH_SECTION_BEGIN "=" FLASH_SECTION_REBOOT)) {
		/*
		 * Found the beginning of the reboot section.
		 * Store, uudecode, uncompress and expand reboot archive
		 * in temporary directory
		 */

		flar -> reboot = 1;

		if (!TestRun) {
			if ((fp = fopen("/tmp/reboot", "w")) == NULL) {
				return (FlErrWrite);
			}
		}

		for (;;) {
			if ((status = flar->ops->readline(flar, &bufptr))
					!= FlErrSuccess) {
				write_notice(ERRMSG,
					MSG0_FLASH_UNABLE_TO_READ_REBOOT);
				if (!TestRun)
					fclose(fp);
				return (status);
			}
			if (streq(bufptr, FLASH_SECTION_END "="
					FLASH_SECTION_REBOOT)) {
				/* Found the beginning of the files section */
				break;
			}
			if (!TestRun) fprintf(fp, "%s\n", bufptr);
		}

		if (!TestRun) {
			fflush(fp);
			fclose(fp);

			/*
			 * Create command for generic type of archive format.
			 * Based on the  archiver, archiver_cmd and
			 * archiver_arguments values, command will be modified.
			 */
			olen = snprintf(cmd, sizeof (cmd), "cd /tmp;"
			    "/usr/bin/uudecode /tmp/reboot;"
			    "/usr/bin/uncompress /tmp/reboot.%s.Z;"
			    "cd /tmp/flash_tmp;"
			    "%s %s /tmp/reboot.%s;"
			    "/usr/bin/rm -f /tmp/reboot*", archiver,
			    archiver_cmd, archiver_arguments, archiver);

			if (olen >= sizeof (cmd)) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_MAKE_FLASH_CMD);
				return (1);
			}

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_WRITE_REBOOT);
				return (FlErrRebootExtraction);
			}
		}

		if ((status = flar->ops->readline(flar, &bufptr)) !=
		    FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_FILES);
			return (status);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_FLASH_REBOOT_NOT_FOUND);
	}

	/*
	 * fast-forward to the files section
	 */

	while (!streq(bufptr, FLASH_SECTION_BEGIN "="
					FLASH_SECTION_FILES)) {
		if ((status = flar->ops->readline(flar, &bufptr)) !=
		    FlErrSuccess) {
			write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_FILES);
			return (status);
		}
	}

	if (local_customization != NULL) {
		if (!TestRun) {
			(void) snprintf(cmd, sizeof (cmd), "%s/predeployment",
					local_customization);
			write_status(SCR, LEVEL0,
			    MSG0_LOCAL_CUSTOMIZATION);
			_dir_exec(cmd);
			write_status(SCR, LEVEL0,
			    MSG0_LOCAL_CUSTOMIZATION_DONE);
		}
	} else {
		write_status(SCR, LEVEL0, MSG0_NO_LOCAL_CUSTOMIZATION);
	}

	if (!TestRun) {
		if (flar -> predeployment) {
			(void) sprintf(cmd,
			    "/tmp/flash_tmp/predeployment_processing");
			if (system(cmd) == 0) {
				return (_dir_exec(
				"/tmp/flash_tmp/predeployment"));
			} else {
				write_notice(ERRMSG,
				    MSG0_FLASH_SYSTEM_PREDEPLOYMENT_FAILURE);
				return (FlErrSysPredeployment);
			}
		}
	}
	return (FlErrSuccess);
}

/*
 * Postdeployment processing
 */

FlashError
FLARPostDeployment(FlashArchive *flar, char *local_customization)
{
	FlashError status;
	char *bufptr;
	char **bufarr;
	struct	stat buf;
	int i;
	FILE *fp;
	char cmd[PATH_MAX];
	char file[PATH_MAX];
	FlashError res;

	int TestRun = 0;

	write_status(SCR, LEVEL0, MSG0_FLASH_POSTDEPLOYMENT);

	if (GetSimulation(SIM_EXECUTE) &&
	    !(GetSimulation(SIM_SYSSOFT))) {
		TestRun = 1;
	}

	/* Storing master name in local file /etc/flash/master on clone */

	if (!TestRun) {
		(void) snprintf(file, sizeof (file),
				"%s/etc/flash", get_rootdir());

		if (lstat(file, &buf) != 0) {
			if (errno == ENOENT) {
				(void) snprintf(cmd, sizeof (cmd),
				    "/usr/bin/mkdir -p %s/etc/flash;",
				    get_rootdir());
				system(cmd);
			}
		}
		(void) snprintf(file, sizeof (file),
				"%s/etc/flash/master", get_rootdir());

		if ((fp = fopen(file, "w")) != NULL) {
			fprintf(fp, "%s", flar->ident.cr_master);
			fclose(fp);
		}

		/* Exec postdeployment scripts */

		/* local */

		if (local_customization != NULL) {
			(void) snprintf(cmd, sizeof (cmd), "%s/postdeployment",
					local_customization);
			write_status(SCR, LEVEL0,
			    MSG0_LOCAL_CUSTOMIZATION);
			_dir_exec(cmd);
			write_status(SCR, LEVEL0,
			    MSG0_LOCAL_CUSTOMIZATION_DONE);
		} else {
			write_status(SCR,
			    LEVEL0, MSG0_NO_LOCAL_CUSTOMIZATION);
		}

		/* from flash */

		if (flar -> postdeployment) {
			(void) sprintf(cmd,
			    "/tmp/flash_tmp/postdeployment_processing");
			if (system(cmd) == 0) {
				res = _dir_exec(
					"/tmp/flash_tmp/postdeployment");
			} else {
				write_notice(ERRMSG,
				    MSG0_FLASH_SYSTEM_POSTDEPLOYMENT_FAILURE);
				res = FlErrSysPostdeployment;
			}
		} else {
			res = FlErrSuccess;
		}

		/* clean up */

		(void) sprintf(cmd, "rm -rf /tmp/flash_tmp");
		system(cmd);
	} else {
		res = FlErrSuccess;
	}

	return (res);
}

/*
 * Name:	checkArch
 * Description:	Validate the archive against the requirements of the clone
 *		system being installed.  If the archive is not appropriate for
 *		this clone architecture, an error message is printed, and an
 *		error code is
 *		returned.
 * Scope:	public
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The open archive to be validated
 * Returns:	FlErrSuccess		- The archive is appropriate for this
 *					  clone
 *		FlErrUnsupported	- The archive is not appropriate for
 *					  this clone
 */

FlashError checkArch(FlashArchive *flar) {

	StringList *arch;
	char *curarch;

	/* Check to see if this machine is of a supported architecture */
	if (flar->ident.cont_arch) {
		curarch = get_default_machine();
		for (arch = flar->ident.cont_arch; arch; arch = arch->next) {
			if (streq(arch->string_ptr, curarch)) {
				break;
			}
		}
		if (!arch) {
			write_notice(ERRMSG, MSG0_FLASH_UNSUP_ARCHITECTURE,
				curarch);
			return (FlErrUnsupported);
		}
	}
	return (FlErrSuccess);
}

/*
 * Name:	FLARValidate
 * Description:	Validate the archive against the requirements of the clone
 *		system being installed.  If the archive is not appropriate for
 *		this clone, an error message is printed, and an error code is
 *		returned.
 * Scope:	public
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The open archive to be validated
 * Returns:	FlErrSuccess		- The archive is appropriate for this
 *					  clone
 *		FlErrUnsupported	- The archive is not appropriate for
 *					  this clone
 *		FlErrInternal		- This function was called without an
 *					  open archive.
 */
FlashError
FLARInstallValidate(FlashArchive *flar)
{
	FlashError res;

	/* Check arguments */
	if (!flar || !flar_is_open(flar)) {
		return (FlErrInternal);
	}

	res = checkArch(flar);
	if (res != FlErrSuccess) {
		return (res);
	}

	if (streq(flar->ident.type, "FULL")) {
		return (FlErrSuccess);
	} else {
		return (FlErrArchType);
	}
}

/*
 * Name:	FLARValidate
 * Description:	Validate the archive against the requirements of the clone
 *		system being installed.  If the archive is not appropriate for
 *		this clone, an error message is printed, and an error code is
 *		returned.
 * Scope:	public
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The open archive to be validated
 * Returns:	FlErrSuccess		- The archive is appropriate for this
 *					  clone
 *		FlErrUnsupported	- The archive is not appropriate for
 *					  this clone
 *		FlErrInternal		- This function was called without an
 *					  open archive.
 */
FlashError
FLARUpdateValidate(FlashArchive *flar)
{
	FlashError res;

	/* Check arguments */
	if (!flar || !flar_is_open(flar)) {
		return (FlErrInternal);
	}

	res = checkArch(flar);
	if (res != FlErrSuccess) {
		return (res);
	}

	if (streq(flar->ident.type, "DIFFERENTIAL")) {
		return (FlErrSuccess);
	} else {
		return (FlErrArchType);
	}
}

/*
 * Name:	FLARExtractArchive
 * Description:	Given an open archive, extract it onto the already-mounted
 *		filesystems of the clone.  Extraction is performed in the
 *		manner appropriate to the archive retrieval method.  Status
 *		information is provided via a TCallback.
 * Scope:	public
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The open archive to be extracted
 *		cb	- [RO, *RW] (TCallback *)
 *			  The callback to be used for status reporting
 *		data	- [RO, *RW] (void *)
 *			  Data specific to the caller of this function to be
 *			  returned via the callback in addition to status
 *			  information, or NULL if none.
 * Returns:	FlErrSuccess	- The archive was extracted successfully
 *		FlErrInternal	- An invalid archive was passed
 *		<various>	- Failure codes specific to the retrieval
 *				  method used.
 */
FlashError
FLARExtractArchive(FlashArchive *flar, TCallback *cb, void *data)
{
	FlashError status = FlErrSuccess;
	FILE *xfp;
	char *tmphashfile;
	FlashError stop_status;
	char *bufptr;

	/*
	 * If not doing software simulation, don't take the
	 * time to extract the archive, it might take a while.
	 */
	if (GetSimulation(SIM_EXECUTE) && !(GetSimulation(SIM_SYSSOFT))) {
		return (FlErrSuccess);
	}

	/*
	 * Identify the archive - use the name if possible, otherwise fall
	 * back on the location.
	 */
	if (flar->ident.cont_name) {
		write_status(LOGSCR, LEVEL0,
			MSG0_FLASH_EXTRACTING_ARCHIVE_NAME,
			flar->ident.cont_name);
	} else {
		write_status(LOGSCR, LEVEL0, MSG0_FLASH_EXTRACTING_ARCHIVE_X,
			FLARArchiveType(flar), FLARArchiveWhere(flar));
	}

	/*
	 * if we have a hash, compute a file name to contain
	 * the hash after extraction is complete.
	 */

	if (flar->ident.hash) {
		if (!(tmphashfile = tempnam("/tmp", "flar"))) {
			return (FlErrInternal);
		}
		flar->hashfile = tmphashfile;
	}

	/* Start the writer */
	if (_start_writer(flar, &xfp) != FlErrSuccess) {
		write_notice(ERRMSG, MSG0_FLASH_CANT_START_XTRACT);
		status = FlErrCouldNotStartWriter;
	} else {

		/* Do the extraction (let the reader feed the writer) */
		status = flar->ops->extract(flar, xfp, cb, data);

		/* Stop the writer, and compare the hash (if computed) */
		if ((stop_status = _stop_writer(flar, xfp)) != FlErrSuccess) {
			if (status == FlErrSuccess) {
				if (stop_status == FlErrCorruptedArchive) {
					/*
					 * allow corrupt archives, but warn
					 * loudly
					 */
					write_status(LOGSCR, LEVEL1,
						MSG0_FLASH_CORRUPT_ARCHIVE);
				} else {
					write_notice(ERRMSG,
						MSG0_FLASH_CANT_STOP_XTRACT);
					status = FlErrCouldNotStopWriter;
				}
			}
		}

		if (status == FlErrSuccess) {
			write_status(LOGSCR, LEVEL1|CONTINUE,
				MSG0_FLASH_EXTRACTION_COMPLETE);
		}
	}
	/* done, free the temp hash filename */
	if (flar->hashfile) {
		free(flar->hashfile);
		flar->hashfile = NULL;
	}
	return (status);
}

/*
 * Name:	FLARClose
 * Description:	Close a Flash archive
 * Scope:	public
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The open archive to be closed
 * Returns:	FlErrSuccess	- The archive was successfully closed
 *		FlErrInternal	- The archive wasn't open
 */
FlashError
FLARClose(FlashArchive *flar)
{
	if (!flar_is_open(flar)) {
		return (FlErrInternal);
	}

	return (flar->ops->close(flar));
}

/* ---------------------- internal functions ----------------------- */

/*
 * Name:	FLARArchiveType
 * Description:	Return a static string containing a human-readable
 *		representation of the retrieval method being used by the
 *		passed archive.
 * Scope:	library internal
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive whose type is to be gathered
 * Returns:	char *	- A pointer to a static buffer containing the
 *			  retrieval type.  This buffer should not be modified
 *			  by the caller.
 */
char *
FLARArchiveType(FlashArchive *flar)
{
	static char buf[50];

	if (!flar) {
		return ("UNKNOWN (NULL)");
	}

	if (flar->type == FlashRetUnknown) {
		(void) sprintf(buf, "UNKNOWN (%d)", flar->type);
		return (buf);
	}

	switch (flar->type) {
	case FlashRetNFS:
		return ("NFS");
	case FlashRetHTTP:
		return ("HTTP");
	case FlashRetFTP:
		return ("FTP");
	case FlashRetLocalFile:
		return (MSG0_FLASH_RET_TYPE_LOCAL_FILE);
	case FlashRetLocalTape:
		return (MSG0_FLASH_RET_TYPE_LOCAL_TAPE);
	case FlashRetLocalDevice:
		if (flar->spec.LocalDevice.fstype) {
			(void) snprintf(buf, sizeof (buf), "%s %s",
				flar->spec.LocalDevice.fstype,
				MSG0_FLASH_RET_TYPE_LOCAL_DEVICE);
			return (buf);
		} else {
			return (MSG0_FLASH_RET_TYPE_LOCAL_DEVICE);
		}
	default:
		(void) sprintf(buf, "INVALID (%d)", flar->type);
		return (buf);
	}
}

/*
 * Name:	FLARArchiveWhere
 * Description:	Return a static string containing a human-readable
 *		representation of the location of the passed archive.
 * Scope:	library internal
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive whose location is to be gathered
 * Returns:	char *	- A pointer to a static buffer containing the
 *			  retrieval location.  This buffer should not be
 *			  modified by the caller.
 */
char *
FLARArchiveWhere(FlashArchive *flar)
{
	static char buf[MAXPATHLEN * 2 + 2];
	char *urlbuf;

	if (!flar) {
		return ("UNKNOWN (NULL)");
	}

	if (flar->type == FlashRetUnknown) {
		(void) sprintf(buf, "UNKNOWN (%d)", flar->type);
		return (buf);
	}

	switch (flar->type) {
	case FlashRetNFS:
		(void) snprintf(buf, sizeof (buf), "%s:%s",
			flar->spec.NFSLoc.host, flar->spec.NFSLoc.path);
		break;
	case FlashRetHTTP:
		if (URLString(flar->spec.HTTP.url, &urlbuf) != 0) {
			(void) sprintf(buf, "Internal ERROR");
			return (buf);
		}
		(void) snprintf(buf, MAXPATHLEN * 2, urlbuf);
		free(urlbuf);
		break;
	case FlashRetFTP:
		if (URLString(flar->spec.FTP.url, &urlbuf) != 0) {
			(void) sprintf(buf, "Internal ERROR");
			return (buf);
		}
		(void) snprintf(buf, MAXPATHLEN * 2, urlbuf);
		free(urlbuf);
		break;
	case FlashRetLocalFile:
		(void) strcpy(buf, flar->spec.LocalFile.path);
		break;
	case FlashRetLocalTape:
		if (flar->spec.LocalTape.position >= 0) {
			(void) snprintf(buf, sizeof (buf), "%s %s %d",
				flar->spec.LocalTape.device, FILE_STRING,
				flar->spec.LocalTape.position);
		} else {
			(void) strcpy(buf, flar->spec.LocalTape.device);
		}
		break;
	case FlashRetLocalDevice:
		(void) snprintf(buf, sizeof (buf), "%s:%s",
			flar->spec.LocalDevice.device,
			flar->spec.LocalDevice.path);
		break;
	default:
		(void) sprintf(buf, "INVALID (%d)", flar->type);
	}

	return (buf);
}

/* ---------------------- private functions ----------------------- */

/*
 * Name:	_init_flash_ops
 * Description:	Initialize the operations vector in a given archive to point
 *		to the functions appropriate for the given retrieval type
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose operations vector is to be set
 * Returns:	FlErrSuccess		- The vector was set successfully
 *		FlErrInternal		- The retrieval type has not yet been
 *					  set for this archive
 *		FlErrUnsupported	- The selected retrieval type is not
 *					  supported
 */
static FlashError
_init_flash_ops(FlashArchive *flar)
{
	void *dlh;

	if (flar->type == FlashRetUnknown ||
		flar->type >= FlashRetLastItem) {
		return (FlErrInternal);
	}

	if (!(flash_ops[flar->type].open)) {
		write_notice(ERRMSG, "Unimplemented retrieval method");
		return (FlErrUnsupported);
	}

	flar->ops = &(flash_ops[flar->type]);

	if (flar->type == FlashRetHTTP) {
		/*
		 * Thanks to 4864280, we have to fallback to an old
		 * implementation of HTTP if we cannot load the
		 * library that gives us a better one (and supports
		 * HTTPS)
		 */
		if ((dlh = dlopen(WANBOOT_DYNLIB_NAME,
			    RTLD_NOW|RTLD_GLOBAL)) == NULL) {

			/* no libwanboot available.  use old impl */
			flar->ops = &old_http_flashops;

			/* don't allow anything other than HTTP */
			if (!ci_streq(flar->spec.HTTP.url->scheme, "http")) {
				write_notice(ERRMSG,
				    "Unimplemented retrieval method %s",
				    flar->spec.HTTP.url->scheme);
				return (FlErrUnsupported);
			}
		} else {
			/* found libwanboot. */
			(void) dlclose(dlh);
		}
	}
	return (FlErrSuccess);
}

/*
 * Name:	_valid_cookie
 * Description:	Validate the cookie read from the archive.  The cookie must
 *		be of the proper format, and must contain a major version
 *		number understood by this program.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose cookie is to be validated
 *		buf	- [RO, *RO] (char *)
 *			  The cookie string to be validated
 * Returns:	FlErrSuccess		- The cookie is valid
 *		FlErrInvalid		- The cookie is not valid
 *		FlErrUnsupported	- The major version in the cookie is
 *					  not supported by this program.
 */
static FlashError
_valid_cookie(FlashArchive *flar, char *buf)
{
	char *version;
	char *c, *c2;
	char ch;

	/* Make sure the static part is right */
	if (!begins_with(buf, FLASH_COOKIE_STATIC)) {
		write_notice(ERRMSG, MSG0_FLASH_CORRUPT_COOKIE);
		return (FlErrInvalid);
	}

	/* Extract the version number */
	version = buf + strlen(FLASH_COOKIE_STATIC);
	for (c = version; isdigit(*c); c++);
	if (c == version || *c != '.') {
		write_notice(ERRMSG, MSG0_FLASH_CORRUPT_COOKIE);
		return (FlErrInvalid);
	}

	*c = '\0';
	flar->maj_ver = atoi(version);
	*c++ = '.';

	for (c2 = c; isdigit(*c2); c2++);
	if (c == c2 || (*c2 != '.' && *c2 != '\0')) {
		write_notice(ERRMSG, MSG0_FLASH_CORRUPT_COOKIE);
		return (FlErrInvalid);
	}

	ch = *c2;
	*c2 = '\0';
	flar->min_ver = atoi(version);
	*c2 = ch;

	/* Check the version */
	if (flar->maj_ver < FLASH_MINIMUM_MAJOR ||
		flar->maj_ver > FLASH_MAXIMUM_MAJOR) {
		write_notice(ERRMSG, MSG0_FLASH_ARCHIVE_BAD_MAJOR, version);
		return (FlErrUnsupported);
	}
	/*
	 * Before this major all archives was FULL
	 * and type keyward did not exist
	 */
	if (flar->maj_ver < FLASH_TYPE_INTRODUCED_MAJOR) {
		flar->ident.type = "FULL";
	}

	return (FlErrSuccess);
}

/*
 * Name:	_read_ident_section
 * Description:	Read the identification section from the archive, storing it in
 *		a dynamically-allocated, NULL-terminated array that will be
 *		freed by the caller.  Each line of the section, excluding the
 *		begin and end of section markers, will be returned as an
 *		individual element of the array.
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose identification section is to be read
 *		bufarr	- [RO, *RW] (char ***)
 *			  A pointer to where the location of the array
 *			  containing the elements of the identification section
 *			  will be stored
 * Returns:	FlErrSuccess	- The identification section was read
 *				  successfully
 *		FlErrInvalid	- The section read was invalid, and could not
 *				  be parsed.
 *		FlErrEndOfFile	- The identification section ended prematurely
 *		FlErrRead	- An error occurred reading the identification
 *				  section
 */
static FlashError
_read_ident_section(FlashArchive *flar, char ***bufarr)
{
	FlashError status;
	char **lines = NULL;
	char *line;
	int numlines = 0;

	/* Read the first line */
	if ((status = flar->ops->readline(flar, &line))  != FlErrSuccess) {
		if (status == FlErrEndOfFile) {
			write_notice(ERRMSG, MSG0_FLASH_PREM_END_IDENT);
		} else {
			write_notice(ERRMSG, MSG0_FLASH_CANT_READ_IDENT);
		}
		return (status);
	}

	/* Is this an identification section header? */
	if (!streq(line, FLASH_SECTION_BEGIN "=" FLASH_SECTION_IDENT)) {
		write_notice(ERRMSG, MSG0_FLASH_UNABLE_TO_FIND_IDENT);
		return (FlErrInvalid);
	}

	/* Yes, so start reading pairs */
	for (;;) {
		if ((status = flar->ops->readline(flar, &line))
							!= FlErrSuccess) {
			if (status == FlErrEndOfFile) {
				write_notice(ERRMSG, MSG0_FLASH_PREM_END_IDENT);
			} else {
				write_notice(ERRMSG,
					MSG0_FLASH_CANT_READ_IDENT);
			}
			return (status);
		}

		/* Is this an end section marker? */
		if (streq(line, FLASH_SECTION_END"="FLASH_SECTION_IDENT)) {
			/* Yes, so we're done */
			break;
		}

		lines = (char **)xrealloc(lines, sizeof (char *) *
			(++numlines + 1));
		lines[numlines - 1] = xstrdup(line);
	}

	lines[numlines] = NULL;
	*bufarr = lines;

	return (FlErrSuccess);
}

/*
 * Name:	_parse_ident
 * Description:	Given an array of strings comprising the lines in an archive
 *		identification section, parse those lines and store them in
 *		the FLARIdentSection portion of a FlashArchive
 * Scope:	private
 * Arguments:	flar	- [RO, *RW] (FlashArchive *)
 *			  The archive whose FLARIdentSection is to be
 *			  populated.
 *		lines	- [RO, *RO] (char **)
 *			  The NULL-terminated array of identification section
 *			  lines
 * Returns:	FlErrSuccess	- The identification section was parsed
 *				  successfully
 */
static FlashError
_parse_ident(FlashArchive *flar, char **lines)
{
	FlashError status = FlErrSuccess;
	char *val;
	int i;

	for (i = 0; status == FlErrSuccess && lines && lines[i]; i++) {
		if ((val = get_value(lines[i], '=')) == NULL) {
		if (flar->ident.num_desc_lines) {
			flar->ident.cont_desc =
				(char **)xrealloc(flar->ident.cont_desc,
				++flar->ident.num_desc_lines * sizeof (char *));
			flar->ident.cont_desc[flar->ident.num_desc_lines - 1] =
				xstrdup(lines[i]);
			continue;
		} else {
			/* Invalid format - lines must be key=value pairs */
			status = FlErrInvalid;
			break;
			}
		}

		/*
		 * Assigning arc_method from identification section of
		 * flash archive. Otherthan cpio/pax it gives error.
		 */
		if (ci_begins_with(lines[i], "FILES_ARCHIVED_METHOD=")) {
			if (ci_streq(val, "cpio")) {
				flar->ident.arc_method = FLARArc_CPIO;
			} else if (ci_streq(val, "pax")) {
				flar->ident.arc_method = FLARArc_PAX;
			} else {
				write_notice(ERRMSG,
					MSG0_FLASH_UNKNOWN_ARC_METHOD, val);
				status = FlErrInvalid;
			}

		} else if (ci_begins_with(lines[i],
				"FILES_COMPRESSED_METHOD=")) {
			if (ci_streq(val, "none")) {
				flar->ident.comp_method = FLARComp_None;
			} else if (ci_streq(val, "compress")) {
				flar->ident.comp_method = FLARComp_Compress;
			} else {
				write_notice(ERRMSG,
					MSG0_FLASH_UNKNOWN_COMP_METHOD, val);
				status = FlErrInvalid;
			}

		} else if (ci_begins_with(lines[i], "FILES_ARCHIVED_SIZE=")) {
			if ((flar->ident.arc_size = atoll(val)) < 1) {
				write_notice(ERRMSG,
					MSG0_FLASH_BAD_ARC_SIZE, val);
				status = FlErrInvalid;
			}

		} else if (ci_begins_with(lines[i], "FILES_UNARCHIVED_SIZE=")) {
			if ((flar->ident.unarc_size = atoll(val)) < 1) {
				write_notice(ERRMSG,
					MSG0_FLASH_BAD_UNARC_SIZE, val);
				status = FlErrInvalid;
			}

		} else if (ci_begins_with(lines[i], "CREATION_DATE=")) {
			if ((flar->ident.cr_date =
					ParseISO8601(val)) < 0) {
				write_notice(ERRMSG,
					MSG0_FLASH_BAD_CREATE_DATE, val);
				status = FlErrInvalid;
			}
			flar->ident.cr_date_str = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_MASTER=")) {
			flar->ident.cr_master = xstrdup(val);

		} else if (ci_begins_with(lines[i], "ARCHIVE_ID=")) {
			flar->ident.hash = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CONTENT_NAME=")) {
			flar->ident.cont_name = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CONTENT_TYPE=")) {
			flar->ident.cont_type = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CONTENT_DESCRIPTION=")) {
			flar->ident.cont_desc =
				(char **)xrealloc(flar->ident.cont_desc,
				++flar->ident.num_desc_lines * sizeof (char *));
			flar->ident.cont_desc[flar->ident.num_desc_lines - 1] =
				xstrdup(val);

		} else if (ci_begins_with(lines[i], "CONTENT_AUTHOR=")) {
			flar->ident.cont_auth = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CONTENT_ARCHITECTURES=")) {
			flar->ident.cont_arch = StringListBuild(val, ',');

		} else if (ci_begins_with(lines[i], "CREATION_NODE=")) {
			flar->ident.cr_node = xstrdup(val);

		} else if (ci_begins_with(lines[i],
				"CREATION_HARDWARE_CLASS=")) {
			flar->ident.cr_hardware_class = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_PLATFORM=")) {
			flar->ident.cr_platform = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_PROCESSOR=")) {
			flar->ident.cr_processor = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_RELEASE=")) {
			flar->ident.cr_release = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_OS_NAME=")) {
			flar->ident.cr_os_name = xstrdup(val);

		} else if (ci_begins_with(lines[i], "CREATION_OS_VERSION=")) {
			flar->ident.cr_os_version = xstrdup(val);

		} else if (ci_begins_with(lines[i], "TYPE=")) {
			flar->ident.type = xstrdup(val);

		} else if (ci_begins_with(lines[i], "X-")) {
			/* User-defined keyword - ignore it */
			/*EMPTY*/
		} else {
			/*
			 * We save unrecognized keywords - but only the
			 * keywords - so we can whine about them later
			 */

			/* Remove the '=' */
			if (val) {
				*(val - 1) = '\0';
			}

			flar->ident.unk_kws =
				(char **)xrealloc(flar->ident.unk_kws,
				++flar->ident.numuk * sizeof (char *));
			flar->ident.unk_kws[flar->ident.numuk - 1] =
				xstrdup(lines[i]);
		}
	}

	if (status == FlErrSuccess && get_trace_level() > 2) {
		_dump_ident_section(flar);
	}

	return (status);
}

/*
 * Name:	_select_archiver_arguments
 * Description:	Assigns archiver command and its arguments based on
 *		 the archiver method
 *
 * Scope:
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive whose FLARIdentSection structure is to
 *			  be used to assign archiver command and its arguments.
 * Returns:	0	for valid archiver
 *		1	for invalid archiver
 */
static int
_select_archiver_arguments(FlashArchive *flar)
{

	switch (flar->ident.arc_method) {
	case FLARArc_CPIO:
		(void) snprintf(archiver, sizeof (archiver), "cpio");
		(void) snprintf(archiver_cmd, sizeof (archiver_cmd),
				"/usr/bin/cpio");
		(void) snprintf(archiver_arguments,
				sizeof (archiver_arguments), "-dumic -I");
		return (0);
		break;
	case FLARArc_PAX:
		(void) snprintf(archiver, sizeof (archiver), "pax");
		(void) snprintf(archiver_cmd, sizeof (archiver_cmd),
				"/usr/bin/pax");
		(void) snprintf(archiver_arguments,
				sizeof (archiver_arguments), "-r -p e -f");
		return (0);
		break;
	default:
		return (1);
		break;
	}
}

/*
 * Name:	_dump_ident
 * Description:	Print the values in the FLARIdentSection contained in the
 *		archive structure.  This function is intended for debugging
 *		purposes only.
 * Scope:	Debugging private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive whose FLARIdentSection structure is to
 *			  be printed.
 * Returns:	none
 */
static void
_dump_ident_section(FlashArchive *flar)
{
	StringList *arch;
	char *c;
	int i;

	write_status(SCR, LEVEL0, "\t%s", MSG0_FLASH_IDENT_SECTION);

	/* Archive method */
	switch (flar->ident.arc_method) {
	case FLARArc_Unknown:
		c = UNKNOWN_STRING;
		break;
	case FLARArc_CPIO:
		c = "cpio";
		break;
	case FLARArc_PAX:
		c = "pax";
		break;
	default:
		c = "** INVALID **";
		break;
	}
	write_status(SCR, LEVEL1, "\tarc_method:\t%s (%d)", c,
		flar->ident.arc_method);

	/* Compression method */
	switch (flar->ident.comp_method) {
	case FLARComp_Unknown:
		c = UNKNOWN_STRING;
		break;
	case FLARComp_None:
		c = NONE_STRING;
		break;
	case FLARComp_Compress:
		c = "compress";
		break;
	default:
		c = "** INVALID **";
		break;
	}
	write_status(SCR, LEVEL1, "\tcomp_method:\t%s (%d)", c,
		flar->ident.comp_method);

	/* Archived file size */
	write_status(SCR, LEVEL1, "\tarc_size:\t%lld", flar->ident.arc_size);

	/* Unarchived file size */
	write_status(SCR, LEVEL1, "\tunarch_size:\t%lld",
		flar->ident.unarc_size);

	/* Creation date */
	c = ctime(&flar->ident.cr_date);
	c[strlen(c) - 1] = '\0';
	write_status(SCR, LEVEL1, "\tcr_date:\t%ld (%s)",
		flar->ident.cr_date, c ? c : "NULL");

	/* Creation master */
	write_status(SCR, LEVEL1, "\tcr_master:\t%s",
		flar->ident.cr_master ? flar->ident.cr_master : "NULL");

	/* Archive id */
	write_status(SCR, LEVEL1, "\tid:\t%s",
		flar->ident.hash ? flar->ident.hash : "NULL");

	/* Content name, type, and author */
	write_status(SCR, LEVEL1, "\tcont_name:\t%s",
		flar->ident.cont_name ? flar->ident.cont_name : "NULL");
	write_status(SCR, LEVEL1, "\tcont_type:\t%s",
		flar->ident.cont_type ? flar->ident.cont_type : "NULL");
	write_status(SCR, LEVEL1, "\tcont_auth:\t%s",
		flar->ident.cont_auth ? flar->ident.cont_auth : "NULL");

	/* Content description */
	if (flar->ident.num_desc_lines) {
		write_status(SCR, LEVEL1, "\tcont_desc:");
		for (i = 0; i < flar->ident.num_desc_lines; i++) {
			write_status(SCR, LEVEL2, flar->ident.cont_desc[i]);
		}
	}

	/* Architectures */
	if (flar->ident.cont_arch == NULL) {
		write_status(SCR, LEVEL1, "\tcont_arch:\t%s", NONE_STRING);
	} else {
		for (c = NULL, arch = flar->ident.cont_arch; arch;
		    arch = arch->next) {
			if (!c) {
				c = xmalloc(strlen(arch->string_ptr) + 1);
				(void) strcpy(c, arch->string_ptr);
			} else {
				c = xrealloc(c, strlen(c) +
				    strlen(arch->string_ptr) + 2);
				(void) strcat(c, " ");
				(void) strcat(c, arch->string_ptr);
			}
		}

		write_status(SCR, LEVEL1, "\tcont_arch:\t%s", c);

		free(c);
	}

	/* Unknown keywords */
	if (flar->ident.numuk) {
		write_status(SCR, LEVEL1|CONTINUE,
		    MSG0_FLASH_IDENT_SECTION_UNK_KW);

		for (i = 0; i < flar->ident.numuk; i++) {
			write_status(SCR, LEVEL2, flar->ident.unk_kws[i]);
		}
	}

	write_status(SCR, LEVEL0|CONTINUE, "");
}

/*
 * Name:	_start_writer
 * Description:	Spawn the command that, when fed the files section of the
 *		archive, will unarchive (and possibly uncompress) said files
 *		onto the disk.  It will also compute the hash of the archive
 *		if supported on the current runtime.
 * Scope:	private
 * Arguments:	flar	- [RO, *RO] (FlashArchive *)
 *			  The archive to be extracted
 *		fpp	- [RO, *WO] (FILE **)
 *			  Where the pointer to the extraction stream is to
 *			  be stored.
 *
 * Returns:	FlErrSuccess			- writer started successfully
 *		FlErrCouldNotStartWriter	- the writer couldn't be started
 */
static FlashError
_start_writer(FlashArchive *flar, FILE **fpp)
{
	char cmd[512] = "";
	char hashcmd[512] = "";
	FILE *fp;
	struct stat sbuf;
	int stubused;

	/*
	 * Build the command
	 */

	if (!GetSimulation(SIM_EXECUTE)) {
		(void) snprintf(cmd, sizeof (cmd), "(cd %s; ", get_rootdir());
	}

	switch (flar->ident.comp_method) {
	case FLARComp_None:
		/* Nothing */
		break;

	case FLARComp_Compress:
		(void) strcat(cmd, "/usr/bin/uncompress -c 2>/dev/null |");
		break;

	default:
		return (FlErrCouldNotStartWriter);
	}

	/*
	 * if we're computing a hash, insert the hash computer
	 * in the extraction pipeline.
	 */
	if (flar->hashfile) {
		if (system("/usr/sbin/computehash -n > /dev/null 2>&1")) {
			free(flar->hashfile);
			flar->hashfile = NULL;
			/*
			 * we have a precomputed hash, but the current
			 * system cannot compute hashes.
			 */

			write_status(LOGSCR, LEVEL1,
			    MSG0_FLASH_UNSUP_HASH);
		} else {
			(void) snprintf(hashcmd, sizeof (hashcmd),
					"/usr/sbin/computehash -f %s |",
					flar->hashfile);
			strcat(cmd, hashcmd);
		}
	}

	switch (flar->ident.arc_method) {
	case FLARArc_CPIO:
		/*
		 * When doing cpio, we need a special utility to ignore
		 * cpio errors, which can sometimes occur.  If that
		 * utility does not exist, then we don't use it, but
		 * we pop up a warning on x86 when a stub boot is being
		 * used, since that is whenx it (currently) might fail.
		 */
	    if (stat(CPIO_WRAPPER, &sbuf) == 0) {
		    if (GetSimulation(SIM_EXECUTE)) {
			    (void) strcat(cmd, "/usr/bin/cpio -ict  2>&1 1> "
				"/tmp/files.extr | "
				CPIO_WRAPPER);
		    } else {
			    (void) strcat(cmd, "/usr/bin/cpio -dumic 2>&1 1> "\
				"/dev/null | "
				CPIO_WRAPPER);
		    }
	    } else {
		    /* output warning on x86 with a stub boot partition */
		    stubused =
			(DiskobjFindStubBoot(CFG_CURRENT, NULL, NULL)
			    == D_OK) ? TRUE : FALSE;
		    if (IsIsa("i386") && stubused) {
			    /* i18n: 70 characters max width */
			    write_status(LOGSCR, LEVEL1,
				MSG0_FLASH_UNSUP_X86BOOT1);
			    /* i18n: 70 characters max width */
			    write_status(LOGSCR, LEVEL1,
				MSG0_FLASH_UNSUP_X86BOOT2);
		    }
		    if (GetSimulation(SIM_EXECUTE)) {
			    (void) strcat(cmd, "/usr/bin/cpio -ict > "
				"/tmp/files.extr 2>&1");
		    } else {
			    (void) strcat(cmd, "/usr/bin/cpio -dumic > "\
				"/dev/null 2>&1");
		    }
		}
		break;
	case FLARArc_PAX:
		/*
		 * Appending /usr/bin/pax command and its arguments
		 * to extract pax formatted archives.
		 */
		if (GetSimulation(SIM_EXECUTE)) {
			(void) strcat(cmd, "/usr/bin/pax > "
				"/tmp/files.extr 2>&1");
		} else {
			(void) strcat(cmd, "/usr/bin/pax -r -p e > "\
				"/dev/null 2>&1");
		}
		break;
	default:
		return (FlErrCouldNotStartWriter);
	}

	if (!GetSimulation(SIM_EXECUTE)) {
		(void) strcat(cmd, ")");
	}

	/*
	 * Start the process
	 */
	if (!(fp = popen(cmd, "w"))) {
		return (FlErrCouldNotStartWriter);
	}

	*fpp = fp;

	return (FlErrSuccess);
}

/*
 * Name:	_stop_writer
 * Description:	Attempt to stop the writer by closing its stream. If success,
 *		compare hashes (if available).  The hash filename is
 *		deallocated if existing.
 * Scope:	private
 * Arguments:	fp	- [RO, *RO] (FILE *)
 *			  The writer's stream
 *		flar	- The archive being extracted
 * Returns:	FlErrSuccess		- the writer was stopped successfully
 *		FlErrCouldNotStopWriter	- the writer could not be stopped
 *					  (there's a movie in there somewhere)
 */

static FlashError
_stop_writer(FlashArchive *flar, FILE *fp)
{
	char filehash[MAXHASHLEN];
	FILE *hashfilep;

	if (pclose(fp) != 0) {
		return (FlErrCouldNotStopWriter);
	}
	if (flar->hashfile) {
		if (!flar->ident.hash) {
			/*
			 * somehow we computed a hash for an archive
			 * that had no hash.  This should not happen.
			 */
			return (FlErrInternal);
		}
		if (!(hashfilep = fopen(flar->hashfile, "r"))) {
			/* hash not computed */
			return (FlErrInternal);
		}
		if (!fgets(filehash, MAXHASHLEN, hashfilep)) {
			/* could not read hash */
			return (FlErrInternal);
		}
		(void) fclose(hashfilep);

		if (strcmp(flar->ident.hash, filehash) != 0) {
			/*
			 * compare computed hash with what
			 * was computed when archive was created.
			 */
			return (FlErrCorruptedArchive);
		}
	}
	return (FlErrSuccess);
}


/*
 * Name:		equals
 * Description:	Compares two FlashArchives, checking for equality.
 * Scope:		public
 * Arguments:	f1	- The first archive
 *		f2	- The second archive
 * Returns:	0 if the archive descriptors  do not refer to the same archive,
 *		1 otherwise.  The archive type must be the same, and
 *		the associated entries for the particular type must be
 *		the same, for the two to be considered equal.
 */
int
equals(FlashArchive *f1, FlashArchive *f2) {

	if (f1 == f2) {
		return (1);
	}
	if ((f1 == NULL) && (f2 == NULL)) {
		return (1);
	}

	if (((f1 == NULL) && (f2 != NULL)) ||
	    ((f1 != NULL) && (f2 == NULL))) {
		return (0);
	}

	if (f1->type  != f2->type) {
		return (0);
	}

	switch (f1->type) {
	case FlashRetUnknown:
	case FlashRetLastItem:
		return (1);
		break;
	case FlashRetNFS:
		if (_streq(f1->spec.NFSLoc.host, f1->spec.NFSLoc.host) &&
		    _streq(f1->spec.NFSLoc.host, f1->spec.NFSLoc.host)) {
			return (1);
		}
		break;
	case FlashRetHTTP:
		if ((f1->spec.HTTP.url == NULL) &&
		    (f2->spec.HTTP.url == NULL)) {
			return (1);
		}
		if (((f1->spec.HTTP.url == NULL) &&
		    (f2->spec.HTTP.url != NULL)) ||
		    ((f1->spec.HTTP.url != NULL) &&
			(f2->spec.HTTP.url == NULL))) {
			return (0);
		}

		if (_streq(f1->spec.HTTP.url->host, f2->spec.HTTP.url->host) &&
		    _streq(f1->spec.HTTP.url->path, f2->spec.HTTP.url->path) &&
		    (f1->spec.HTTP.url->port == f2->spec.HTTP.url->port)) {
			return (1);
		}
		break;
	case FlashRetFTP:
		if (_streq(f1->spec.FTP.url->host, f2->spec.FTP.url->host) &&
		    _streq(f1->spec.FTP.url->path, f2->spec.FTP.url->path) &&
		    (f1->spec.FTP.url->port == f2->spec.FTP.url->port)) {
			return (1);
		}
		break;
	case FlashRetLocalTape:
		if (_streq(f1->spec.LocalTape.device,
		    f2->spec.LocalTape.device) &&
		    (f1->spec.LocalTape.position ==
			f2->spec.LocalTape.position)) {
			return (1);
		}
		break;
	case FlashRetLocalFile:
		if (_streq(f1->spec.LocalFile.path,
		    f2->spec.LocalFile.path)) {
			return (1);
		}
		break;
	case FlashRetLocalDevice:
		if (_streq(f1->spec.LocalDevice.device,
		    f2->spec.LocalDevice.device) &&
		    (_streq(f1->spec.LocalDevice.path,
			f2->spec.LocalDevice.path)) &&
		    (strcmp(f1->spec.LocalDevice.fstype,
			f2->spec.LocalDevice.fstype))) {
			return (1);
		}
		break;
	default:
		return (0);
	}
	/* archives are not equal */
	return (0);
}

/*
 * Name:		_streq
 * Description:	Compares two strings.  null strings are acceptable.
 * Scope:		public
 * Arguments:	s1	- The first string
 *		s2	- The second sstring
 * Returns:	0 if the strings are not equal, non-zero otherwise.
 *		Strings are equal if a)they are both null, or b)they are
 *		both non-null and are equal according to strcmp
 */
static int
_streq(char *s1, char *s2) {
	if ((s1 == NULL) && (s2 == NULL)) {
		return (0);
	}
	if ((s1 == NULL) && (s2 != NULL)) {
		return (0);
	}
	if ((s1 != NULL) && (s2 == NULL)) {
		return (0);
	}

	if (strcmp(s1, s2) == 0) {
		return (1);
	} else {
		return (0);
	}
}

/*
 * Name:	is_flash_install
 * Description:	Determines if this is a flash install or not.
 * Scope:	public
 * Returns:	non-zero if this is a flash install, zero otherwise.
 */
int
is_flash_install(void)
{
	return (_is_flash_install);
}


/*
 * Name:	set_flash_install
 * Description:	Says if this is a flash install or not
 * Scope:	public
 * Returns:	none.
 */
void
set_flash_install(int fi)
{
	_is_flash_install = fi;
}


/*
 * Name:	count_archives
 * Description:	Determine how many valid archives will be installed
 * Scope:	public
 * Returns:	# of archives to install
 */
int
count_archives()
{
	return (flar_count);
}

/*
 * Name:	count_archives
 * Description:	Determine how many valid archives will be installed
 * Scope:	public
 * Returns:	# of archives to install
 */
FlashArchive
*get_archive(int i)
{
	return (flars[i]);
}

/*
 * Name:	add_archive
 * Description:	Adds an archive to be installed
 * Scope:	public
 * Returns:	0 if we could add, 1 otherwise
 */
int
add_archive(FlashArchive *archive)
{
	flars = xrealloc(flars, (flar_count+1) * sizeof (FlashArchive *));
	flar_count++;
	flars[flar_count-1] = archive;
}

/*
 * Name:	archive_total_reqd_space
 * Description:	Adds archive sizes up to determine how much aggregate disk
 *		space is needed for installation.
 * Scope:	public
 * Returns:	# of megabytes necessary for all archives.
 */
int
archive_total_reqd_space() {
	int total;
	int i;
	long long arcsize;

	total = 0;
	/* calculate total bytes we will be installing */
	for (i = 0; i < count_archives(); i++) {
		/*
		 * size used for each archive is:
		 * a)unarchived size if available
		 * b)archived size for non-compressed archives
		 * c)archived size + 30%  for compressed archives
		 * d)archived size for unknown compression type archives
		 */
		if (get_archive(i)->ident.unarc_size > 0) {
			total +=
			    (int)((double)get_archive(i)->ident.unarc_size /
			    (double)MBYTE);
		} else {
			arcsize = get_archive(i)->ident.arc_size;
			if (get_archive(i)->ident.comp_method ==
			    FLARComp_Compress) {
				total +=
				    (int)((((double)arcsize) / MBYTE) * 1.30);
			} else if (get_archive(i)->ident.comp_method ==
			    FLARComp_None) {
				total += (int)((double)arcsize / MBYTE);
			} else {
				/* who knows, we sure don't */
				total += (int)((double)arcsize / MBYTE);
			}
		}
	}
	return (total);
}

/*
 * Name:	remove_archive
 * Description:	Removes an archive to be installed
 * Scope:	public
 * Returns:	0 if we could find it and remove it, 1 otherwise
 */
int
remove_archive(FlashArchive *archive)
{
	FlashArchive **new_archives;
	int idx;

	if ((idx = _indexof(flars, flar_count, archive)) == -1) {
		return (1);
	}
	new_archives = xmalloc((flar_count-1) * sizeof (FlashArchive *));
	/* copy the objects before the one we're removing */
	memcpy(new_archives, flars, (idx) * sizeof (FlashArchive *));

	/* copy the rest, skipping the one we're removing */
	memcpy(new_archives+idx, flars+idx+1,
	    (flar_count-idx+1) * sizeof (FlashArchive *));

	flar_count--;
	free(flars);
	flars = new_archives;
}

/*
 * Name:	_indexof
 * Description:	Returns index into current archive array of the passed-in
 *		archive.
 * Scope:	public
 * Returns:	index into archive array of archive if found, -1 otherwise.
 */
static int
_indexof(FlashArchive **flars, int count, FlashArchive *flar) {
	int i;

	for (i = 0; i < count; i++) {
		if (equals(flars[i], flar)) {
			return (i);
		}
	}
	return (-1);
}

/*
 * Name:	get_archive_array
 * Description:	Returns all archives in a FlashArchive array.
 * Scope:	public
 * Arguments:	arrayp		- where to store array pointer.
 * Returns:	count of # of archives in array.  Passed array pointer
 *		pointer is updated with location of array.
 */
int
get_archive_array(FlashArchive **arrayp) {
	FlashArchive* tmpa;
	int c, i;

	c = count_archives();
	tmpa = (FlashArchive *)xmalloc(c * sizeof (FlashArchive));
	for (i = 0; i < c; i++) {
		memcpy(tmpa+i, get_archive(i), sizeof (FlashArchive));
	}
	*arrayp = tmpa;
	return (c);
}

/*
 * Name:	free_archive_array
 * Description:	Frees archive array that is passed in.
 * Scope:	public
 * Arguments:	arrayp		- pointer to archive to free
 *		c		- number of array elements
 * Returns:	None.
 */
void
free_archive_array(FlashArchive *arrayp, int c) {
	free(arrayp);
}

/*
 * Name:	dir_state_check
 * Description:	Compare directory state with states stored in manifest
 * Scope:	privat
 * Arguments:	flar		  - pointer to archive
 *		Forced_deployment - type of deployment
 * Returns:	None.
 */
static FlashError
_dir_state_check(FlashArchive *flar, int Forsed_deployment)
{
	char	*line;
	char	lline[PATH_MAX];
	char	file[PATH_MAX];
	char	cmd[PATH_MAX];

	char	*val;
	char	*name;
	char	type;
	int	len;
	FILE    *fp;

	char	**names = xcalloc(sizeof (char *));
	char	**files = xcalloc(sizeof (char *));
	char	**dlist = xcalloc(sizeof (char *));
	char	*types = xcalloc(sizeof (char));
	int	lens[PATH_MAX];
	int	flens[PATH_MAX];

	long long	num = 1;
	long long	fnum = 1;
	long long	dnum = 0;
	int	i, j, k, l, m, n;

	DIR	 *in_dir;
	dirent_t *entry;
	char *dir;

	FlashError status;
	FlashError result = FlErrSuccess;
	char *bufptr;
	char **bufarr;

	int	TestRun = 0;

	FILE *lin;

	int root_shift = strlen(get_rootdir());

	if (GetSimulation(SIM_EXECUTE) && !(GetSimulation(SIM_SYSSOFT))) {
		TestRun = 1;
	}

	names[0] = "none";
	files[0] = "none";
	dlist[0] = NULL;

	/* init index */

	bzero(lens, PATH_MAX * sizeof (int));
	bzero(flens, PATH_MAX * sizeof (int));

	if ((lin = fopen("/usr/lib/flash/flash_exclusion_list", "r")) != NULL) {

		while (fgets(lline, PATH_MAX, lin) != NULL) {

			FILE *pin;
			int len;

			len = strlen(lline);

			if (lline[len - 1] == '\n') {
				lline[len - 1] = '\0';
				len --;
			}

			if (len == 0) continue;
			if (lline[0] == '#') continue;

			(void) snprintf(cmd, sizeof (cmd),
					"/usr/bin/ls -1 %s%s 2>/dev/null",
					get_rootdir(), lline);
			if (TestRun)
				write_status(SCR, LEVEL1,
					"check exclusion for %s", lline);

			pin = popen(cmd, "r");

			while (fgets(lline, PATH_MAX, pin) != NULL) {

				int len;

				if (TestRun)
					write_status(SCR, LEVEL1,
						"excluded %s", lline);

				len = strlen(lline);

				if (lline[len - 1] == '\n') {
					lline[len - 1] = '\0';
					len --;
				}

				name = xstrdup(lline + root_shift);

				len = strlen(name);

				for (k = lens[len];
				    k < lens[len - 1];
				    k ++) {
					if (_namecmp(names[k], name, len)) {
						len = 0;
						break;
					}
				}

				if (len == 0) {
					continue;
				}

				len = strlen(name);
				if (name[len - 1] == ':') {
					len--;
					name[len] = 0;
				}

				num++;
				names = xrealloc(names, sizeof (char *) * num);
				types = xrealloc(types, sizeof (char) * num);
				i = lens[len];
				memmove(names + i + 1,
				    names + i,
				    (num - i - 1) * sizeof (char *));
				memmove(types + i + 1,
				    types + i,
				    (num - i - 1) * sizeof (char));
				names[i] = name;
				types[i] = '-';

				for (k = len - 1;
				    k >= 0;
				    k --) {
					lens[k] ++;
				}
			}
			pclose(pin);
		}
		fclose(lin);

	} else {
		write_notice(WARNMSG, MSG0_FLASH_NO_EXCLUSION_LIST, file);
	}

	/* first load a filter from te beginning of manifest */

	while (1) {

		int len;

		if ((status = flar->ops->readline(flar, &line))
							!= FlErrSuccess) {
			write_notice(ERRMSG,
				MSG0_FLASH_UNABLE_TO_READ_MANIFEST);
			return (status);
		}

		if (streq(line, FLASH_SECTION_END "="
					FLASH_SECTION_MANIFEST)) {
			/* Found the end of the manifest section */
			write_notice(ERRMSG,
				MSG0_FLASH_UNEXPECTED_MANIFEST_END);
			status = FlErrCorruptedArchive;
			return (status);
		}

		len = strlen(line);

		if (line[len - 1] == '\n') {
			line[len - 1] = '\0';
			len --;
		}

		if (strcmp(line, "checklist") == 0) {
			break;
		}

		if (len < 3 || ((line[0] != '-') && (line[0] != '+') &&
			(line[0] != '.')) || line[1] != ' ') {
			continue;
		}
		type = line[0];

		name = xstrdup(line + 2);
		len = strlen(name);

		/* insert name */

		num++;
		names = xrealloc(names, sizeof (char *) * num);
		types = xrealloc(types, sizeof (char) * num);
		i = lens[len];
		memmove(names + i + 1,
			names + i,
			(num - i - 1) * sizeof (char *));
		memmove(types + i + 1,
			types + i,
			(num - i - 1) * sizeof (char));
		names[i] = name;
		types[i] = type;

		/* update index */

		for (k = len - 1;
		    k >= 0;
		    k --) {
			lens[k] ++;
		}
	}

	/* process file list */

	while (1) {

		int len, res;
		if ((status = flar->ops->readline(flar, &line))
							!= FlErrSuccess) {
			write_notice(ERRMSG,
				MSG0_FLASH_UNABLE_TO_READ_MANIFEST);
			return (status);
		}

		if (streq(line, FLASH_SECTION_END "="
					FLASH_SECTION_MANIFEST)) {
			/* Found the end of the files section */
			break;
		}

		len = strlen(line);
		if (line[len - 1] == '\n') {
			line[len - 1] = '\0';
			len --;
		}

		if (line[0] == '\\') {
			if (line[1] == 'd') {

				/* end of directory list reached */

				dir = line + 2;
				(void) snprintf(file, sizeof (file),
					"%s%s", get_rootdir(), line + 2);
				if (in_dir = opendir(file)) {
					if (strcmp(dir, "/") == 0) {
						dir = "";
					}
			for (rewinddir(in_dir); entry = readdir(in_dir); ) {
						if (strcmp(".", entry->d_name)
						    == 0) continue;
						if (strcmp("..", entry->d_name)
						    == 0) continue;
						if (strcmp("lost+found",
							entry->d_name) == 0)
							continue;
						(void) snprintf(file,
							sizeof (file), "%s/%s",
							dir, entry->d_name);
						len = strlen(file);

						/* skip excluded files */

						for (k = lens[len];
						    k != lens[len - 1];
						    k ++) {
							if (_namecmp(names[k],
								file, len)) {

							if ((types[k] == '.') ||
							    (types[k] == '-')) {
								k = -1;
							}
								break;
							}
						}
						if (k == -1) {
							continue;
						}

						/* skipping processed files */

						for (k = flens[len];
							k != flens[len - 1];
							k ++) {
							if (_namecmp(files[k],
								file, len)) {
								k = -1;
								break;
							}
						}

		/* new file founded */

		if (k != -1) {
			if (Forsed_deployment) {
				/* put it in list to delete */

				write_notice(WARNMSG, MSG0_FLASH_NEW_FILES,
					file);
				dnum++;
				dlist = xrealloc(dlist,
						sizeof (char *) * dnum);
				dlist[dnum - 1] = xstrdup(file);
			} else {

				/* submit error */

				write_notice(ERRMSG, MSG0_FLASH_NEW_FILES,
					file);
				result = FlErrNewFile;
			}
		}
					}
					closedir(in_dir);
				}
			}

			/* clean up file stack */

			for (k = 0;
			    k < fnum - 1;
			    k++) {
				free(files[k]);
			}
			free(files);
			files = xcalloc(sizeof (char *));
			files[0] = "none";
			fnum = 1;

			for (k = 0;
			    k < PATH_MAX;
			    k++) {
				flens[k] = 0;
			}
		} else {

			/* compare manifest entry with real file */

			status = _file_state_check_s(line, get_rootdir());

			len = strlen(line);
			for (k = lens[len]; k != lens[len - 1]; k++) {
				if (_namecmp(names[k], line, len)) {
					if ((types[k] == '.') ||
						(types[k] == '-')) {
						k = -1;
					}
					break;
				}
			}

			if (k != -1) {
				switch (status) {
				case FlErrDeletedFile:
					write_notice(ERRMSG,
						MSG0_FLASH_DELETED_FILES, line);
					result = status;
					break;
				case FlErrModifiedFile:
					write_notice(ERRMSG,
						MSG0_FLASH_MODIFIED_FILES,
						line);
					result = status;
					break;
				case FlErrNewFile:
					if (Forsed_deployment) {
						write_notice(WARNMSG,
						MSG0_FLASH_NEW_FILES, line);
						dnum++;
						dlist = xrealloc(dlist,
							sizeof (char *) * dnum);
						dlist[dnum - 1] = xstrdup(line);
					} else {
						write_notice(ERRMSG,
						MSG0_FLASH_NEW_FILES, line);
						result = status;
					}
					break;
				case FlErrOldFile:
					if (TestRun) {
						write_notice(WARNMSG,
						    MSG0_FLASH_OLD_FILES, line);
					}
					dnum++;
					dlist = xrealloc(dlist,
							sizeof (char *) * dnum);
					dlist[dnum - 1] = xstrdup(line);
					break;
				}
			}
			name = xstrdup(line);
			len = strlen(name);

			/* insert name in processed list */

			fnum++;
			files = xrealloc(files, sizeof (char *) * fnum);
			i = flens[len];
			memmove(files + i + 1, files + i,
				(fnum - i - 1) * sizeof (char *));
			files[i] = name;

			/* update index */

			for (k = len -1; k >= 0; k --) {
				flens[k] ++;
			}
		}
	}

	/* delete all new and deleted files */

	for (k = 0;
	    k < dnum;
	    k ++) {
		if (TestRun) {
			write_notice(WARNMSG, MSG0_FLASH_DEL_FILES, dlist[k]);
		} else {
			(void) snprintf(file, sizeof (file),
					"%s%s", get_rootdir(), dlist[k]);
			write_notice(WARNMSG, MSG0_FLASH_RM_FILES, dlist[k]);
			(void) snprintf(cmd, sizeof (cmd), "/usr/bin/rm -rf %s",
				file);
			if (system(cmd) != 0) {
				write_notice(ERRMSG,
				    MSG0_FLASH_UNABLE_TO_CLEAN_CLONE);
				return (FlErrDelete);
			}
			remove(file);
		}
	}
	return (result);
}

/*
 * Name:	_file_state_check
 * Description:	Compare file state with state stored in manifest entry
 * Scope:	privat
 * Arguments:	line - manifest entry (filename included)
 *		root - system image root
 * Returns:	None.
 */

static FlashError
_file_state_check_s(char *line, char *root)
{
	char	file[PATH_MAX];
	char	link_to[PATH_MAX];
	struct	stat64  buf;

	int	mode;
	int	uid;
	int	gid;
	long	mtime;
	long long	size;
	int	len;
	char    *val;
	char	*fname;
	int	old_file = 0;

	len = strlen(line);

	if (!(val = strtok(line, "\t"))) {
		return (FlErrCorruptedArchive);
	}

	fname = val;

	if (!(val = strtok(NULL, "\t"))) {
		return (FlErrCorruptedArchive);
	}

	/* OK for files from delta (presented in differential archive */

	if ((val[0] == 'N') && (val[1] == 0)) {
		return (FlErrSuccess);
	}

	/*
	 * File from old image supposed to be deleted,
	 * but must be same as in old image
	 */

	if ((val[0] == 'O') && (val[1] == 0)) {
		old_file = 1;
		if (!(val = strtok(NULL, "\t"))) {
			return (FlErrCorruptedArchive);
		}
	}

	(void) snprintf(file, sizeof (file), "%s/%s", root, fname);

	if (lstat64(file, &buf) != 0) {
		if (errno == ENOENT) {
			if (old_file)
				return (FlErrSuccess);
			else
				return (FlErrDeletedFile);
		} else {
			return (FlErrFileStat);
		}
	}

	/* compare attributes */

	mode =	(val[0] & 0xF) |
		((val[1] & 0xF) << 4)  |
		((val[2] & 0xF) << 8)  |
		((val[3] & 0xF) << 12) |
		((val[4] & 0xF) << 16) |
		((val[5] & 0xF) << 20) |
		((val[6] & 0xF) << 24) |
		((val[7] & 0xF) << 28);
	if (mode != buf.st_mode) {
		if (old_file)
			return (FlErrNewFile);
		else
			return (FlErrModifiedFile);
	}

	if (!(val = strtok(NULL, "\t"))) {
		return (FlErrCorruptedArchive);
	}
	uid =	(val[0] & 0xF) |
		((val[1] & 0xF) << 4)  |
		((val[2] & 0xF) << 8)  |
		((val[3] & 0xF) << 12) |
		((val[4] & 0xF) << 16) |
		((val[5] & 0xF) << 20) |
		((val[6] & 0xF) << 24) |
		((val[7] & 0xF) << 28);

	if (uid != buf.st_uid) {
		if (old_file)
			return (FlErrNewFile);
		else
			return (FlErrModifiedFile);
	}

	if (!(val = strtok(NULL, "\t"))) {
		return (FlErrCorruptedArchive);
	}
	gid =	(val[0] & 0xF) |
		((val[1] & 0xF) << 4) |
		((val[2] & 0xF) << 8) |
		((val[3] & 0xF) << 12) |
		((val[4] & 0xF) << 16) |
		((val[5] & 0xF) << 20) |
		((val[6] & 0xF) << 24) |
		((val[7] & 0xF) << 28);
	if (gid != buf.st_gid) {
		if (old_file)
			return (FlErrNewFile);
		else
			return (FlErrModifiedFile);
	}

	if (!(val = strtok(NULL, "\t"))) {
		return (FlErrCorruptedArchive);
	}

	if (val[0] == 'd') {
		if (old_file)
			return (FlErrOldFile);
		else
			return (FlErrSuccess);
	} else if (val[0] == 'l') {
		if (!(val = strtok(NULL, "\t"))) {
			return (FlErrCorruptedArchive);
		}
		link_to[readlink(file, link_to, PATH_MAX)] = 0;
		if (streq(val, link_to)) {
			if (old_file)
				return (FlErrOldFile);
			else
				return (FlErrSuccess);
		} else {
			if (old_file)
				return (FlErrNewFile);
			else
				return (FlErrModifiedFile);
		}
	} else {
		mtime =	(val[0] & 0xF) |
			((val[1] & 0xF) << 4) |
			((val[2] & 0xF) << 8) |
			((val[3] & 0xF) << 12) |
			((val[4] & 0xF) << 16) |
			((val[5] & 0xF) << 20) |
			((val[6] & 0xF) << 24) |
			((val[7] & 0xF) << 28);
		if (mtime != buf.st_mtime) {
			if (old_file)
				return (FlErrNewFile);
			else
				return (FlErrModifiedFile);
		}

		if (!(val = strtok(NULL, "\t"))) {
			return (FlErrCorruptedArchive);
		}
		if (val[0] != 's') {
			sscanf(val, "%lld", &size);
			if (size != buf.st_size) {
				if (old_file)
					return (FlErrNewFile);
				else
					return (FlErrModifiedFile);
			}
		}
	}
	if (old_file)
		return (FlErrOldFile);
	else
		return (FlErrSuccess);
}

/*
 * Name:	_dir_exec
 * Description:	execute all executable from this directory
 * Scope:	privat
 * Arguments:	exec_dir - directory
 * Returns:	None.
 */

static FlashError
_dir_exec(char *exec_dir)
{
	char	file[PATH_MAX];
	char	cmd[PATH_MAX];
	char	dir[PATH_MAX];
	char	**list = xcalloc(sizeof (char *));
	int	lnum = 1;
	int	k;
	struct	stat buf;
	char	*pfx;

	DIR	 *in_dir;
	dirent_t *entry;

	list[0] = NULL;

	(void) snprintf(dir, sizeof (dir), "%s", exec_dir);

	if (in_dir = opendir(dir)) {

		if (strcmp(dir, "/") == 0) {
			pfx = "";
		} else {
			pfx = dir;
		}

		for (rewinddir(in_dir); entry = readdir(in_dir); ) {

			if (strcmp(".", entry->d_name) == 0) continue;
			if (strcmp("..", entry->d_name) == 0) continue;

			(void) snprintf(file, sizeof (file),
					"%s/%s", pfx, entry->d_name);

			if (lstat(file, &buf) != 0) {
				return (FlErrFileStat);
			}

			if (buf.st_mode & S_IFDIR) continue;
			if (!(buf.st_mode & S_IXUSR)) continue;

			for (k = 0;
				(list[k] != NULL) &&
				(strcmp(entry->d_name, list[k]) > 0);
				k ++);
			lnum++;
			list = xrealloc(list, sizeof (char *) * lnum);
			memmove(list + k + 1,
				list + k,
				(lnum - k - 1) * sizeof (char *));
			list[k] = xstrdup(entry->d_name);
		}
		for (k = 0;
			list[k] != NULL;
			k ++) {

			(void) snprintf(cmd, sizeof (cmd), "cd %s;"
				"./%s",
				dir,
				list[k]);

			if (system(cmd) != 0) {
				write_notice(ERRMSG,
					MSG0_FLASH_CUSTOM_SCRIPT_FAILURE, cmd);
				return (FlErrCustomScriptError);
			}
		}

		closedir(in_dir);
	}
	return (FlErrSuccess);
}

/*
 * Name:	_name_cmp
 * Description:	compare filenames
 * Scope:	privat
 * Arguments:	a - first name
 *		b - last name
 *		n - compare length
 * Returns:	True or False
 */

static
int _namecmp(char *a, char *b, int n) {

	int k;

	for (k = n - 1;
		k >= 0;
		k --) {
		if (a[k] != b[k]) {
			return (0);
		}
	}
	return (1);
}
