/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
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


#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include <locale.h>
#include "wsreg.h"
#include "boolean.h"
#include "localized_strings.h"

/*
 * The regconvert utility converts from prodreg version 2.0
 * datastore format to product install registry datastore
 * format.
 */

#define	ALTERNATE_ROOT_VARIABLE "PKG_INSTALL_ROOT"

static Boolean batch_mode = FALSE;

static void
initialize_progress();
static void
show_progress(int);
static void
syntax_error(int, char **, char *);

/*
 * The entry point for the regconvert utility.  The regconvert
 * command-line options are:
 *
 * -R alternate_root	- Specifies the alternate root.
 * -f registry_file	- Specifies the registry file to convert.
 * -b			- Batch mode; no progress should be displayed.
 */
int
main(int argc, char **argv)
{
	/*
	 * Parse command line.
	 */
	int c;
	int result;
	int count;
	extern char *optarg;
	char *alternate_root = getenv(ALTERNATE_ROOT_VARIABLE);
	char *reg_file = NULL;
	
	setlocale(LC_ALL, "");
	textdomain(TEXT_DOMAIN);

	while ((c = getopt(argc, argv, "R:f:b")) != EOF) {
		switch (c) {
		case 'R':
			/*
			 * Setting the alternate root on the
			 * command line overrides the environment
			 * variable.
			 */
			alternate_root = optarg;
			break;

		case 'f':
			/*
			 * Set the filename of the file to convert.
			 */
			reg_file = optarg;
			break;

		case 'b':
			/*
			 * Turn on batch mode.  No output of
			 * progress.
			 */
			batch_mode = TRUE;
			break;

		case '?':
			/*
			 * Bad argument. Print help and exit.
			 */
			syntax_error(argc, argv, NULL);
			return (1);
		}
	}

	result = wsreg_initialize(WSREG_INIT_NO_CONVERSION, alternate_root);
	if (result == WSREG_CONVERSION_RECOMMENDED ||
		reg_file != NULL) {
		/*
		 * We should try to perform the conversion.
		 */
		if (reg_file == NULL) {
			reg_file = wsreg_get_old_registry_name();
		}
		initialize_progress();
		result = wsreg_convert_registry(reg_file, &count,
		    show_progress);
		switch (result) {
		case WSREG_FILE_NOT_FOUND:
			/*
			 * The specified registry file does not exist.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_FILE_NOT_FOUND, reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_NO_FILE_ACCESS:
			/*
			 * We do not have permission to modify the
			 * original registry file.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_PERMISSION_DENIED,
			    reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_NO_REG_ACCESS:
			/*
			 * We do not have permission to modify the
			 * registry.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_BAD_REG_PERMISSION,
			    reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_UNZIP_ERROR:
			/*
			 * Some other problem unzipping the registry
			 * file.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_COULDNT_UNZIP,
			    reg_file, reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_BAD_REGISTRY_FILE:
			/*
			 * The file is not a valid zip file.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_BAD_REGISTRY_FILE,
			    reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_CANT_CREATE_TMP_DIR:
			/*
			 * Could not create the temporary directory.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_CANT_CREATE_TMP_DIR);
			(void) printf("\n");
			return (result);

		case WSREG_UNZIP_NOT_INSTALLED:
			/*
			 * Unzip binary is not installed, so the
			 * conversion cannot be performed.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_NO_UNZIP,
			    reg_file);
			(void) printf("\n");
			return (result);

		case WSREG_SUCCESS:
			(void) printf("\n");
			(void) printf(REGCONVERT_COMPLETE, count);
			(void) printf("\n");
			return (0);

		default:
			/*
			 * Unknown error code.
			 */
			(void) printf("\n");
			(void) printf(REGCONVERT_UNRECOGNIZED_FAILURE,
			    reg_file, result);
			(void) printf("\n");
			return (result);
		}
	}
	return (0);
}


/*
 * Initializes the progress display by showing 0% progress.
 * Progress is not shown in batch mode.
 */
static void
initialize_progress()
{
	if (!batch_mode) {
		(void) printf(REGCONVERT_PROGRESS, 0);
		fflush(stdout);
	}
}

/*
 * Displays progress.  This function is a callback that is passed
 * into the wsreg_convert_registry function.  Progress is not
 * shown in batch mode.
 */
static void
show_progress(int percent)
{
	if (!batch_mode) {
		char *progress_text = REGCONVERT_PROGRESS;
		int text_length = strlen(progress_text);
		int index;
		for (index = 0; index < text_length; index++) {
			(void) printf("\b");
		}
		(void) printf(progress_text, percent);
		fflush(stdout);
	}
}

/*
 * This function is called if the user passes an invalid
 * command line option.
 */
static void
syntax_error(int argc, char **argv, char *message)
{
	int index;
	if (message != NULL) {
		(void) fprintf(stderr, message);
		(void) fprintf(stderr, "\n");
	}

	/*
	 * Recreate the command.
	 */
	(void) fprintf(stderr, "regconvert ");
	for (index = 0; index < argc; index++) {
		(void) fprintf(stderr, " %s", argv[index]);
	}
	(void) fprintf(stderr, "\n");

	(void) fprintf(stderr, "%s\n", REGCONVERT_USAGE);
}
