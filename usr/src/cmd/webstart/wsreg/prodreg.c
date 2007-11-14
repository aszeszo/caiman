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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)prodreg.c	1.4	06/02/27 SMI"

/*
 * prodreg.c
 *
 * Organization of the code for the prodreg CLI implementation:
 *   prodreg.c	        Parsing code, main.
 *   prodreg_util.c	Shared utilities for error handling and more.
 *   prodreg_browse.c   Handles the browse command.
 *   prodreg_list.c	Handles the list command.
 *   prodreg_uninst.c   Handles the uninstall command.
 *   prodreg_unreg.c    Handles the unregister command.
 *   prodreg_info.c	Handles the info command.
 *   prodreg_browse_num.c  Maps UUIDs to browse numbers, used for easy access.
 *
 * The following header file is used for all internal definitions:
 *   prodreg_cli.h	Internal definitions for the prodreg CLI modules.
 *
 * Code in the prodreg utility will function with versions of libwsreg since
 *   Solaris 8 update 2.  The only feature which requires an updated version
 *   of the library is the -f (force) option of the unregister subcommand.
 *   please see prodreg_unreg.c comments.
 *
 * NOTE ABOUT list and unregister which use <mnemonic> <location> arguments:
 *   This convention stems from Webstart 2.  After LSARC/2002/214, the only
 *   contracts for this interface are terminated.  For continued support of
 *   legacy scripts, this convention will still be accepted, but only in a
 *   simplified form.  <mnemonic> matches the <unique name> attribute of
 *   a component.  The <location> field has a strange interpretation
 *   already in the prodreg 2.1 interface and onwards, as this field
 *   could be NULL or "-" (both wildcards), or the uninstall location (!)
 *   We assume that the uninstall location is the same as the install
 *   location.   We also accept no input (omitted location) and "-"
 *   to accomodate this archaic command.
 *
 * Code organization and implementation notes:
 *   This file contains the parsers required for all commands, as well as
 *   code to handle the trivial cases (version, launch GUI, etc).
 *   The interface to the command handlers (prodreg_X where X is browse,
 *   info, uninstall, unregister, list, etc) is clean.  The current
 *   implementation of those commands are not that clean.  This is because
 *   the commands provide or access a view of three distinct databases:
 *
 *     (1) System package database
 *     (2) Install product registry
 *     (3) Synthetic tree nodes (glue to hold together a tree)
 *
 *   Queries therefore must traverse all three data structures.  Further
 *   complicating this, the interfaces offered by libwsreg are somewhat
 *   broken.  Queries for child, parent, requirements or dependencies
 *   from the registry return fully initialized components.  From the
 *   system package database 'references', only the primary fields are
 *   initialized.  Rather than fix the current libwsreg, this code
 *   accomodates for these failings (so it can coexist with the current
 *   library version).
 *
 *   Future versions of the database will combine all three databases
 *   above and offer consistent and complete results to queries.
 *   The prodreg command line utility code will, at that time,
 *   be much simpler (probably less than half the code required
 *   for the current implementation.)
 *
 * Internationalization
 *
 *   Each version of the software is compiled against a defined set of
 *   localized messages.  The locale is set to the default, using
 *   setlocale(LC_ALL, "").  Note that the product registry will also
 *   use locale settings to control the 'display name' fields.  If
 *   the environment variable 'LANG' is not set to "" or (default),
 *   the value it is set to  will be used.  Otherwise, the setting
 *   defaults to "en" (English).  This should be consistent with
 *   common practice for internationalized applications.
 *
 * Debug tracing
 *
 *   All debug statements go through the debug function or are
 *   #ifndef NDEBUG.  In either case, defining NDEBUG will disable
 *   the compilation of all trace statements.  As a convenience,
 *   even when NDEBUG is not defined in the compilation, defining
 *   an environment variable "NDEBUG" will also disable tracing.
 *   This allows testing of debug build versions without
 *   interference of debug traces in the output.
 *
 * Performance
 *
 *   The database query interfaces offered by libwsreg are primitive
 *   and require that the entire list of components be returned.
 *   This is an expensive operation, since the list of packages have
 *   to be rendered as components.  This list is reused so it only has
 *   to be obtained once.  Still, many operations require that this
 *   list be traversed in a linear search, often multiple times for
 *   the same operation.  In future versions of the registry, better
 *   query operations need to be supported to improve performance.
 *   This will also reduce the complexity of the prodreg CLI and GUI.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <assert.h>
#include <locale.h>
#include <wsreg.h>

#include "prodreg_cli.h"

/* For the syntax_fail() interface. */
#define	BAD_COMMAND  -1
#define	BAD_SYNTAX   -2

static void syntax_fail(int, char *[], int);
static void launch_stdprodreg(char **);
static void check_altroot(int, char **);
static cmd_code getcommand(const char *);
static void interp_browse(int, char *[]);
static void interp_info(int, char *[]);
static void interp_list(int, char *[]);
static void interp_register(int, char *[]);

/* Used by get_sol_ver to extract the version number */
#define	SWVER_PATH  "/var/sadm/system/admin/INST_RELEASE"

static const char *get_sol_ver(void);

/*
 * Global variables:  These parameters are set initially when the program
 * is initialized, then read (only) later on.
 */
char *global_lang = NULL;
char *global_solver = NULL;
char *global_ENTR_UUID = NULL;

/* Global variable.  Will be malloc'ed and must be freed if reset. */
static char *global_alt_root = NULL;

/*
 * getcommand
 *
 * Associate a command number with a command string.
 *
 *    pc  The command string.
 *
 * Returns: A command code.
 *
 * Side effects: None.
 */
static cmd_code
getcommand(const char *pc)
{

	if (strncmp(pc, "awt", 4) == 0)
		return (CMD_AWT);
	else if (strncmp(pc, "browse", 7) == 0)
		return (CMD_BROWSE);
	else if ((strncmp(pc, "--help", 5) == 0) ||
	    (strncmp(pc, "help", 5) == 0) ||
	    (strncmp(pc, "-?", 3) == 0))
		return (CMD_HELP);
	else if (strncmp(pc, "info", 5) == 0)
		return (CMD_INFO);
	else if (strncmp(pc, "swing", 6) == 0)
		return (CMD_SWING);
	else if (strncmp(pc, "uninstall", 10) == 0)
		return (CMD_UNINSTALL);
	else if (strncmp(pc, "unregister", 11) == 0)
		return (CMD_UNREGISTER);
	else if (strncmp(pc, "register", 8) == 0)
		return (CMD_REGISTER);
	else if ((strncmp(pc, "version", 8) == 0) ||
	    (strncmp(pc, "--version", 10) == 0) ||
	    (strncmp(pc, "-V", 3) == 0))
		return (CMD_VERSION);
	else if (strncmp(pc, "-R", 3) == 0)
		return (ALT_ROOT);
	else if (strncmp(pc, "list", 4) == 0)
		return (CMD_LIST);
	else
		return (CMD_UNKNOWN);
}

/*
 * change_root
 *
 * Reset the root global variable.
 *
 *    pc  The new value for the alternate root.
 *
 * Returns: Nothing
 * Side effect: changes the global variable containing the root to use.
 */
static void
change_root(const char *pc)
{
	if (global_alt_root) free(global_alt_root);
	if ((global_alt_root = strdup(pc)) == NULL) fail(PRODREG_MALLOC);
	wsreg_set_alternate_root(global_alt_root);
	debug(DEBUGINFO, "*** use alternate root %s\n", pc);
}


/*
 * syntax_fail
 *
 * General processing when a command line syntax error is encountered.
 * An error diagnostic is output to standard error.  This routine does
 * not return!
 *
 *   argc     The number of arguments in the command line.
 *   argv     The arguments in the command line.
 *   badarg   The position of the bad argument in the command line.
 *
 * Returns: Nothing.
 *
 * Side effects:  This routine exits the program.
 */
static void
syntax_fail(int argc, char *argv[], int badarg)
{
	int i;
	if (badarg == BAD_COMMAND) {

		(void) fprintf(stderr, PRODREG_BAD_COMMAND, argv[1]);
		(void) fprintf(stderr, "\n");

	} else if (badarg == BAD_SYNTAX) {

		(void) fprintf(stderr, PRODREG_BAD_SYNTAX);
		(void) fprintf(stderr, "\n");

	} else {

		(void) fprintf(stderr, PRODREG_BAD_PARAMETER, argv[badarg]);
		(void) fprintf(stderr, "\n");
	}
	(void) fprintf(stderr, "   ");
	for (i = 0; i < argc; i++) {
		(void) fprintf(stderr, "%s ", argv[i]);
	}
	(void) fprintf(stderr, "\n");
	(void) fprintf(stderr, PRODREG_USE_HELP);
	(void) fprintf(stderr, "\n");
	(void) fprintf(stderr, PRODREG_HELP_USAGE, argv[0]);
	(void) fprintf(stderr, "\n");
	exit(1);
}

static char **
alloc_array(int argc, char *argv[], const char *pcArg)
{
	int i, n = 0;
	char **ppc = NULL;

	for (i = 0; i < (argc - 1); i++)
		if (strcmp(argv[i], pcArg) == 0)
			n++;

	ppc = (char **) calloc((n + 1), sizeof (char *));
	if (ppc == NULL) {
		fprintf(stderr, "%s\n", PRODREG_MALLOC);
	}

	n = 0;
	for (i = 0; ppc != NULL && i < (argc - 1); i++) {
		if (strcmp(argv[i], pcArg) == 0) {
			if ((ppc[n++] = strdup(argv[i + 1])) == NULL) {
				fprintf(stderr, "%s\n", PRODREG_MALLOC);
				free(ppc);
				ppc = NULL;
			}
		}
	}

	return (ppc);
}

/*
 * interp_register
 *
 * This interprets the "register" command.  This command has lots of
 * options, but it is fairly straightforward, unlike the webstart commands.
 *
 * prodreg register -u uuid
 *  [-b backward-compatible-version ] *
 *  [-c child-uuid '{' instance# '}' ] *
 *  [-d dependent-uuid '{' instance# '}' ] *
 *  [-D attribute '{' value '}' ] *
 *  [-n display-name '{' language-tag '}' ] *
 *  [-p location ]
 *  [-P parent-uuid '{' instance# '}' ]
 *  [-r required-uuid '{' instance# '}' ] *
 *  [-R alt_root ]
 *  [-t (PRODUCT | FEATURE | COMPONENT) ] ----> default: COMPONENT
 *  [-U unique-name ]
 *  [-v prod-version ]
 *  [-V vendor-string ]
 *  [-x uninstaller-command ]
 *
 * Returns nothing.
 * Side effects: may cause a new component to get registered, or overwrite
 *   an existing entry.
 */
static void
interp_register(int argc, char *argv[])
{
	char **ppcBack = NULL, **ppcChild = NULL, **ppcDep = NULL,
	    **ppcReq = NULL, **ppcAtt = NULL, **ppcDname = NULL;
	char *pcUname = NULL, *pcLoc = NULL, *pcParent = NULL,
	    *pcVer = NULL, *pcVend = NULL, *pcUninst = NULL, *pcUUID = NULL,
	    *pcType = NULL;
	int c;
	char **argv2 = &argv[1];
	int args = 2;

	if (argc > 2 && 0 == strcmp(argv[2], "--help")) {
		(void) fprintf(stdout, PRODREG_HELP_REGISTER, argv[0]);
		(void) fprintf(stdout, "\n");
		return;
	}

	ppcBack = alloc_array(argc, argv, "-b");
	ppcChild = alloc_array(argc, argv, "-c");
	ppcDep = alloc_array(argc, argv, "-d");
	ppcReq = alloc_array(argc, argv, "-r");
	ppcAtt = alloc_array(argc, argv, "-D");
	ppcDname = alloc_array(argc, argv, "-n");

	while ((c = getopt(argc - 1, argv2, "b:c:d:D:n:p:P:r:R:t:u:U:v:V:x:"))
	    != EOF) {
		switch (c) {
		case 'b':
		case 'c':
		case 'd':
		case 'D':
		case 'n':
		case 'r':
			/* Handled previously, above. */
			args += 2;
			break;

		case 'p':
			if (pcLoc) free(pcLoc);
			pcLoc = strdup(optarg);
			args += 2;
			break;
		case 'P':
			if (pcParent) free(pcParent);
			pcParent = strdup(optarg);
			args += 2;
			break;
		case 'R':
			change_root(optarg);
			args += 2;
			break;
		case 't':
			if (pcType) free(pcType);
			pcType = strdup(optarg);
			args += 2;
			break;
		case 'u':
			if (pcUUID) free(pcUUID);
			pcUUID = strdup(optarg);
			args += 2;
			break;
		case 'U':
			if (pcUname) free(pcUname);
			pcUname = strdup(optarg);
			args += 2;
			break;
		case 'v':
			if (pcVer) free(pcVer);
			pcVer = strdup(optarg);
			args += 2;
			break;
		case 'V':
			if (pcVend) free(pcVend);
			pcVend = strdup(optarg);
			args += 2;
			break;
		case 'x':
			if (pcUninst) free(pcUninst);
			pcUninst = strdup(optarg);
			args += 2;
			break;
		default:
			syntax_fail(argc, argv, optind);
		}
	}

	if (args != argc || pcUUID == NULL) {
		syntax_fail(argc, argv, BAD_SYNTAX);
	}

	prodreg_register(global_alt_root, pcUUID, pcType,
	    ppcBack, ppcChild, ppcDep, ppcReq, ppcAtt, ppcDname,
	    pcLoc, pcParent, pcUname, pcVer, pcVend, pcUninst);
}

/*
 * interp_list
 *
 * This interprets the "list" command.  This command is not officially
 * supported, but is provided for backwards compatibility - so as to not
 * break existing scripts used internally to Sun for upgrade.
 *
 * Returns: Nothing
 * Side effects: none
 */
static void
interp_list(int argc, char *argv[]) {

	int j = 2;

	if (argc > 2 && 0 == strcmp(argv[2], "--help")) {
		(void) fprintf(stdout, PRODREG_HELP_LIST, argv[0]);
		(void) fprintf(stdout, "\n");
		return;
	}

	if (argc < 4)
		syntax_fail(argc, argv, BAD_SYNTAX);

	/* Determine if we have an alternate root */
	if (0 == strcmp(argv[2], "-R")) {
		j = 4;
		change_root(argv[3]);
	}

	/* Is the command long enough? */
	if (argc < (j + 2))
		syntax_fail(argc, argv, BAD_SYNTAX);

	prodreg_list(global_alt_root, argc - j, &argv[j]);
}

/*
 * interp_browse
 *
 * The command line is parsed.
 * Allowable syntax includes:
 *   prodreg browse [-R root]
 *   prodreg browse [-R root] -m <name>
 *   prodreg browse [-R root] -m <name> [-i <instance>]
 *   prodreg browse [-R root] -m <name> [-p <location>]
 *   prodreg browse [-R root] -n <browse-number> [-i <instance> ]
 *   prodreg browse [-R root] -n <browse-number> [-p <location> ]
 *   prodreg browse [-R root] -u <uuid> [-i <instance>]
 *   prodreg browse [-R root] -u <uuid> [-p <location>]
 *   prodreg browse --help
 *
 *    argc    The number of arguments on the command line.
 *    argv    The command line arguments.
 *
 * Returns: Nothing.
 *
 * Side effects: Additional browse numbers might be assigned and saved.
 */
static void
interp_browse(int argc, char *argv[])
{
	int c;
	char *pc_name = NULL;
	char *pc_uuid = NULL;
	char *pc_locn = NULL;
	char **argv2  = &argv[1];
	int  inst = 1;
	int mask = 0;
	uint32_t bnum = 0;
	int  i;
	Criteria criteria;

	(void) memset(&criteria, 0, sizeof (Criteria));

	/*
	 *  If --help is present on command line, show help and ignore
	 *  the other options.
	 */
	for (i = 2; (i < argc) && (argv[i] != NULL); i++) {
		if (0 == strcmp(argv[i], "--help")) {
			(void) fprintf(stdout, "%s\n", PRODREG_HELP_BROWSE);
			return;
		}
	}

	i = 0;
	while ((c = getopt(argc-1, argv2, "R:m:n:i:u:p:")) != EOF) {
		switch (c) {
		case 'R':
			change_root(optarg);
			i += 2;
			break;
		case 'p':
			if (pc_locn) free(pc_locn);
			pc_locn = strdup(optarg);
			mask |= FIND_LOCN;
			i += 2;
			break;
		case 'm':
			if (pc_name) free(pc_name);
			pc_name = strdup(optarg);
			i += 2;
			break;
		case 'n':
			{
				int x;
				for (x = 0; x < strlen(optarg); x++) {
					if (optarg[x] < '0' ||
					    optarg[x] > '9') {
						syntax_fail(argc,
						    argv, optind);
					}
				}
			}

			bnum = (uint32_t) strtoul(optarg, NULL, 10);
			if (errno != 0) {
				syntax_fail(argc, argv, optind);
			}
			i += 2;
			break;
		case 'i':
			/*
			 * Use the optind index (counts from 1) to
			 * point at the instance # string to convert.
			 */
			inst = atoi(argv2[optind - 1]);
			if (inst < 1 || inst > 100) {
				syntax_fail(argc, argv, optind);
			}
			mask |= FIND_INST;
			i += 2;
			break;
		case 'u':
			if (pc_uuid) free(pc_uuid);
			pc_uuid = strdup(optarg);
			i += 2;
			break;
		default:
			syntax_fail(argc, argv, optind);
		}
	}

	if (i != (argc - 2)) {
		syntax_fail(argc, argv, BAD_SYNTAX);
	}

	if (NULL == pc_name && 0 == bnum && NULL == pc_uuid) {

		debug(DEBUGINFO, "*** browse from root\n");
		CFILL(criteria, ROOT_UUID, NULL, NULL, 1, FIND_UUID | mask);

	} else if (pc_name && 0 == bnum && NULL == pc_uuid) {

		debug(DEBUGINFO, "*** browse by name \"%s\"\n", pc_name);
		CFILL(criteria, NULL, pc_locn, pc_name, inst,
		    FIND_NAME | mask);

	} else if (NULL == pc_name && bnum != 0 && NULL == pc_uuid) {

		db_open();
		pc_uuid = getUUIDbyBrowseNum(bnum);
		if (pc_uuid == NULL)
			fail(PRODREG_NO_SUCH_COMPONENT);

		debug(DEBUGINFO, "*** browse by number \"%u\" "
		    "-> uuid \"%s\" locn \"%s\" instance \"%d\"\n",
		    bnum, pc_uuid, (pc_locn)?(pc_locn):"NULL", inst);
		CFILL(criteria, pc_uuid, pc_locn, NULL, inst,
		    FIND_UUID | mask);

	} else if (NULL == pc_name && 0 == bnum && pc_uuid) {

		debug(DEBUGINFO, "*** browse by uuid \"%s\" "
		    "inst \"%d\" location \"%s\"\n",
		    pc_uuid, inst, (pc_locn)?(pc_locn):"NULL");
		CFILL(criteria, pc_uuid, pc_locn, NULL, inst,
		    FIND_UUID | mask);

	} else {
		syntax_fail(argc, argv, BAD_SYNTAX);
	}

	browse_request(global_alt_root, criteria);

	if (pc_uuid) free(pc_uuid);
	if (pc_name) free(pc_name);
	if (pc_locn) free(pc_locn);
}

/*
 * interp_info
 *
 * Interpret the "info" command line and output results.
 *
 * Allowable syntax includes:
 *   prodreg info [-R root] -u <uuid> [(-i <inst> | -p <locn>)]
 *     [(-a <attr> | -d)]
 *   prodreg info [-R root] -n <browse-number> [(-i <inst> | -p <locn> )]
 *     [(-a <attr> | -d)]
 *   prodreg info [-R root] -m <name> [(-a <attr> | -d)]
 *   prodreg info --help
 *
 * Returns: Nothing
 * Side effects: none
 */
static void
interp_info(int argc, char *argv[])
{
	int c;
	char *pc_name = NULL;
	char *pc_uuid = NULL;
	char *pc_inst = NULL;
	char *pc_attr = NULL;
	char *pc_locn = NULL;
	uint32_t bnum = 0;
	char **argv2  = &argv[1];
	int damage = 0, mask = 0, inst = 0, i, args = 2;
	Criteria criteria;

	/*
	 *  If --help is present on command line, show help and ignore
	 *  the other options.
	 */
	for (i = 2; (i < argc) && (argv[i] != NULL); i++) {
		if (0 == strcmp(argv[i], "--help")) {
			(void) fprintf(stdout, "%s\n", PRODREG_HELP_INFO);
			return;
		}
	}

	while ((c = getopt(argc-1, argv2, "dm:n:i:u:a:R:p:")) != EOF) {
		switch (c) {
		case 'R':
			change_root(optarg);
			args += 2;
			break;
		case 'p':
			if (pc_locn) free(pc_locn);
			pc_locn = strdup(optarg);
			mask |= FIND_LOCN;
			args += 2;
			break;
		case 'd':
			damage = 1;
			args++;
			break;
		case 'a':
			if (pc_attr) free(pc_attr);
			pc_attr = strdup(optarg);
			args += 2;
			break;
		case 'm':
			if (pc_name) free(pc_name);
			pc_name = strdup(optarg);
			args += 2;
			break;
		case 'n':
			bnum = (uint32_t) strtoul(optarg, NULL, 10);
			if (errno != 0) {
				syntax_fail(argc, argv, optind);
			}
			args += 2;
			break;
		case 'i':
			if (pc_inst) free(pc_inst);
			/*
			 * Use the optind index (counts from 1) to
			 * point at the instance # string to convert.
			 */
			inst = atoi(argv2[optind - 1]);
			if (inst < 1 || inst > 100) {
				syntax_fail(argc, argv, optind);
			}
			args += 2;
			mask |= FIND_INST;
			break;
		case 'u':
			if (pc_uuid) free(pc_uuid);
			pc_uuid = strdup(optarg);
			args += 2;
			break;
		default:
			syntax_fail(argc, argv, optind);
		}
	}

	if ((args != argc) || (pc_attr && damage != 0)) {
		syntax_fail(argc, argv, BAD_SYNTAX);
	}

	if (pc_name && 0 == bnum && NULL == pc_uuid) {

		debug(DEBUGINFO, "*** info by name \"%s\"%s%s"
		    "locn \"%s\" inst \"%d\"\n",
		    pc_name, (damage)?" is damaged? ":"",
		    (pc_attr)?(pc_attr):"", (pc_locn)?(pc_locn):"", inst);
		CFILL(criteria, pc_uuid, pc_locn, pc_name, inst,
		    FIND_NAME | mask);

	} else if (NULL == pc_name && 0 != bnum && NULL == pc_uuid) {

		db_open();
		pc_uuid = getUUIDbyBrowseNum(bnum);
		if (pc_uuid == NULL)
			fail(PRODREG_NO_SUCH_COMPONENT);

		debug(DEBUGINFO, "*** info by number \"%u\" -> uuid %s "
		    "%s%s%s\n",
		    bnum, pc_uuid, (damage)?" is damaged ":"",
		    (pc_attr)?"attr = ":"", (pc_attr)?(pc_attr):"");
		CFILL(criteria, pc_uuid, pc_locn, pc_name, inst,
		    FIND_UUID | mask);

	} else if (NULL == pc_name && 0 == bnum && pc_uuid) {

		debug(DEBUGINFO, "*** info by uuid \"%s\"%s%s"
		    "locn \"%s\" inst \"%d\"\n",
		    pc_uuid, (damage)?" is damaged? ":"",
		    (pc_attr)?(pc_attr):"", (pc_locn)?(pc_locn):"", inst);
		CFILL(criteria, pc_uuid, pc_locn, pc_name, inst,
		    FIND_UUID | mask);

	} else {

		syntax_fail(argc, argv, BAD_SYNTAX);
	}

	prodreg_info(global_alt_root, criteria, pc_attr, damage);

	if (pc_name) free(pc_name);
	if (pc_uuid) free(pc_uuid);
	if (pc_attr) free(pc_attr);
	if (pc_locn) free(pc_locn);
}

/*
 * count_args
 *
 * interp_uninst has to parse the command line using getopt, but there can
 * be arbitrary arguments at the end of the line.  In order to avoid
 * getting spurious diagnostic messages from getopt, we count the number of
 * arguments which are legal before the non-legal arguments appear.
 *
 *  num   The number of arguments initially
 *  argv  The command line
 *
 * Returns:  The number of arguments including only those which getopt
 *	   should parse.  If there is junk, we just return what we
 *	   can and let the parse fail.
 *
 * Side effects: None
 */
static int
count_args(int num, char *argv[])
{
	/* Initialize the count to 1, to skip the subcommand name. */
	int i = 1;
	while (i < num) {
		if (strncmp(argv[i], "-f", strlen("-f") + 1) == 0) {
			i++;
		} else if (strncmp(argv[i], "-i", strlen("-i") + 1) == 0) {
			i += 2;
		} else if (strncmp(argv[i], "-R", strlen("-R") + 1) == 0) {
			i += 2;
		} else if (strncmp(argv[i], "-p", strlen("-p") + 1) == 0) {
			i += 2;
		} else if (strncmp(argv[i], "-u", strlen("-u") + 1) == 0) {
			i += 2;
		} else {
			break;
		}
	}
	/*
	 * Guard against the possibility that the last thing is a -[iRpu]
	 * with no argument following.  This would make i > num which would
	 * walk past the end of argv.
	 */
	if (i > num) i = num;

	debug(DEBUGINFO, "getopt command line options for uninstall = %d\n", i);
	return (i);
}

/*
 * interp_uninstall
 *
 * Interpret and execute this command.
 *
 * Allowable syntax:
 *   prodreg uninstall [-R root] <mnemonic> <location> [ARGS]...
 *   prodreg uninstall --help
 *   prodreg uninstall [-R root] [-f] -u <uuid> -p <location>  [ARGS]...
 *   prodreg uninstall [-R root] [-f] -u <uuid> -i <instance>  [ARGS]...
 *
 * SEE NOTE ABOUT mnemonic AT THE TOP OF THIS MODULE.
 * Returns: Nothing
 * Side effect: executes an uninstall program.
 */
static void
interp_uninstall(int argc, char *argv[])
{
	char **arglist = NULL;
	Criteria criteria;
	int force = 0, max = 0, i;
	int c;

	(void) memset(&criteria, 0, sizeof (criteria));

	/*
	 * Parsing this command is more tricky than the others because
	 * of the legacy '<mnemonic> [<location>]' option.  We first
	 * eliminate the other options and we check to see if we have
	 * a 3rd arg which is not one of the command flags ('-x', etc)
	 * nor --help, and we have at least 4 args.  If this is the case,
	 * we assume argument 3 is <mnemonic> and 4 is <location>, if
	 * present.
	 */

	if (argc < 3) {

		syntax_fail(argc, argv, BAD_SYNTAX);

	} else if (argc == 3) {

		/* The only allowable case is 'prodreg uninstall --help' */
		if (0 == strcmp(argv[2], "--help")) {
			(void) fprintf(stdout, "%s\n",
			    PRODREG_HELP_UNINSTALL);
			return;
		} else {
			criteria.uniquename = argv[2];
			criteria.mask |= FIND_UNAME;
		}

	} else if ((argc >= 4 && argv[2][0] != '-') ||
	    (argc >= 6 && argv[4][0] != '-' && 0 == strcmp(argv[2], "-R"))) {

		max = 4;

		criteria.mask |= FIND_UNAME;

		if (argv[2][0] != '-') {
			/* We have no '-R altroot' */
			criteria.uniquename = argv[2];

			/* If 4th arg is '-' then its a wildcard */
			if (strcmp(argv[3], "-")) {
				criteria.mask |= FIND_LOCN;
				criteria.location = argv[3];
			}
		} else {
			/* We have '-R altroot' */
			change_root(argv[3]);
			max = 6;
			criteria.uniquename = argv[4];

			/* If 6th arg is '-' then its a wildcard */
			if (strcmp(argv[5], "-")) {
				criteria.location = argv[5];
				criteria.mask |= FIND_LOCN;
			}
		}

	} else {
		char **argv2 = &argv[1];
		int done = 0;
		int numargs = count_args(argc - 1, argv2);

		while (!done &&
		    (c = getopt(numargs, argv2, "fp:i:u:R:")) != EOF) {
			switch (c) {
			case 'R':
			    change_root(optarg);
			    break;
			case 'f':
			    force = 1;
			    max = optind;
			    break;
			case 'p':
			    criteria.location = strdup(optarg);
			    max = optind + 1;
			    criteria.mask |= FIND_LOCN;
			    break;
			case 'i':
			    criteria.instance = atoi(optarg);
			    max = optind + 1;
			    criteria.mask |= FIND_INST;
			    break;
			case 'u':
			    criteria.uuid = strdup(optarg);
			    max = optind + 1;
			    criteria.mask |= FIND_UUID;
			    break;
			default:
			    /* Arbitrary Args could be on this line. */
			    done = 1;
			    break;
			}
		}
	}

#ifndef NDEBUG
	if (getenv("NDEBUG") == NULL) {
		char *pcarglist = make_arglist(max, argc, argv);
		if (criteria.mask & FIND_UNAME)
			(void) printf("*** uninstall mnemonic "
			    "\"%s\", args= %s\n",
			    criteria.uniquename, pcarglist);
		if (criteria.mask & FIND_UUID)
			debug(DEBUGINFO, "*** uninstall force [%s] "
			    "uuid [%s] locn [%s] inst [%d] "
			    " arglist = %s\n", (force == 0)?"no":"yes",
			    CHK(criteria.uuid),
			    CHK(criteria.location),
			    criteria.instance, pcarglist);
		free(pcarglist);
	}
#endif

	if (max < argc) {

		arglist = (char **) malloc((argc - max + 1) *
		    (size_t) sizeof (char *));
		if (arglist == NULL) fail(PRODREG_MALLOC);
		(void) memset(arglist, 0, (argc - max + 1) * sizeof (char *));
		for (i = max; i < argc; i++)
			arglist[i - max] = argv[i];
	} else {
		arglist = (char **) malloc(2 * sizeof (char *));
		if (arglist == NULL) fail(PRODREG_MALLOC);
		(void) memset(arglist, 0, 2 * sizeof (char *));
	}

	prodreg_uninstall(arglist, global_alt_root, criteria, force);
}

/*
 * interp_unregister
 *
 * Interpret the unregister subcommand line.  Note that the mnemonic
 * and location (if given) MUST be given in the order
 *
 * Allowable syntax:
 *   prodreg unregister [-R root] <mnemonic> [<location>]
 *   prodreg unregister --help
 *   prodreg unregister [-R root] [-fr] -u <uuid> [-p <location>]
 *   prodreg unregister [-R root] [-fr] -u <uuid> [-i <instance>]
 *
 * Returns: nothing
 * Side effect:  Will unregister one or more components from the registry.
 */
static void
interp_unregister(int argc,  char *argv[])
{
	char *pc_uuid = NULL, *pc_locn = NULL;
	int c;
	int force = 0;
	int inst = 0;
	int mask = 0;
	int rec  = 0; /* Recursive deregistration */
	Criteria criteria;

	(void) memset(&criteria, 0, sizeof (criteria));

	/*
	 * Parsing this command is more tricky than the others because
	 * of the legacy '<mnemonic> <location>' option takes no flags.
	 */

	if (argc < 3) {

		syntax_fail(argc, argv, BAD_SYNTAX);

	} else if (argc == 3 ||
		(argc == 4 && argv[2][0] != '-' && strlen(argv[2]) > 2) ||
		((argc == 6 || argc == 5) &&
		    0 == strcmp(argv[2], "-R") &&
		    (argv[4][0] != '-'))) {

		/*
		 * This parsing case above is complicated by irregularities.
		 * [1]  The 'location' in a mnemonic line can be omitted.
		 * [2]  The only way to identify a mnemonic is that it
		 *	does not start with a '-' flagging it as an option.
		 * [3]  The mnemonic must follow not precede a -R <root>
		 *	option.
		 *
		 * The above conditional tests whether there is the
		 * 3 or 4 argument condition for a mnemonic line, where
		 * the 3rd arg does not begin with a '-'.  It also checks
		 * if -R <root> is followed by mnemonic or mnemonic location.
		 */

		if (0 == strcmp(argv[2], "--help")) {
			(void) fprintf(stdout, "%s\n",
			    PRODREG_HELP_UNREGISTER);
			return;
		}

		/*
		 * prodreg unregister -R argv[3] <mnemonic> [<location>]
		 * or prodreg unregister <mnemonic> [<location>]
		 */
		if (argc == 5 || argc == 6) {
			change_root(argv[3]);
			criteria.uniquename = argv[4];
			if (argc == 6) {
				criteria.location = argv[5];
				criteria.mask |= FIND_LOCN;
			}
		} else {
			criteria.uniquename = argv[2];
			if (argc == 4) {
				criteria.location = argv[3];
				criteria.mask |= FIND_LOCN;
			}
		}
		debug(DEBUGINFO, "*** unregister mnemonic \"%s\""
		    "location \"%s\"\n",
		    criteria.uniquename,
		    (criteria.location)?(criteria.location):"");
		criteria.mask |= FIND_UNAME;
		force = 1;

	} else {
		char **argv2 = &argv[1];

		while ((c = getopt(argc-1, argv2, "rfp:i:u:R:")) != EOF) {
			switch (c) {
			case 'R':
				change_root(optarg);
				break;
			case 'r':
				rec = 1;
				break;
			case 'f':
				force = 1;
				break;
			case 'p':
				if (pc_locn) free(pc_locn);
				pc_locn = strdup(optarg);
				mask |= FIND_LOCN;
				break;
			case 'i':
				/*
				 * Use the optind index (counts from 1) to
				 * point at the instance # string to convert.
				 */
				inst = atoi(argv2[optind - 1]);
				if (inst < 1 || inst > 100)
					syntax_fail(argc, argv, optind);
				mask |= FIND_INST;
				break;
			case 'u':
				if (pc_uuid) free(pc_uuid);
				mask |= FIND_UUID;
				pc_uuid = strdup(optarg);
				break;
			default:
				syntax_fail(argc, argv, optind);
			}
		}

		if (pc_uuid && 0 != inst && NULL == pc_locn) {

			debug(DEBUGINFO,
			    "*** unregister uuid [%s] inst [%d] force [%s]\n",
			    pc_uuid, inst, (force == 0)?"no":"yes");
			CFILL(criteria, pc_uuid, pc_locn, NULL, inst, mask);

		} else if (pc_uuid && 0 == inst && NULL != pc_locn) {

			debug(DEBUGINFO,
			    "*** unregister uuid [%s] locn [%s] force [%s]"
			    " recursive [%s]\n",
			    pc_uuid, pc_locn, (force == 0)?"no":"yes",
			    (rec == 0)?"no":"yes");
			CFILL(criteria, pc_uuid, pc_locn, NULL, inst, mask);

		} else if (criteria.mask != FIND_UNAME) {

			syntax_fail(argc, argv, BAD_SYNTAX);

		}
	}

	prodreg_unregister(global_alt_root, criteria, force, rec);
}

/*
 * get_sol_ver
 *
 * Returns: A string which includes the version # of Solaris to use in
 *   output strings.
 * Side effects: None.
 */
static const char
*get_sol_ver()
{
	char path[1024];
	FILE *fp;
	char buf[80];
	uint32_t len;
	(void) sprintf(path, "%s%s", global_alt_root, SWVER_PATH);
	fp = fopen(path, "r");

	while (fp != NULL && fgets(buf, 80, fp) != NULL) {
		len = strlen("VERSION=");

		if (0 == strncmp("VERSION=", buf, len)) {
			char *pcdup = malloc(strlen(buf) - len +1);
			if (pcdup == NULL) fail(PRODREG_MALLOC);
			(void *) memset(pcdup, 0, strlen(buf) - len +1);
			(void *) memcpy(pcdup, &buf[len], strlen(buf)-len);
			/*
			 * Strip off the carriage return that fgets
			 * left on the end
			 */
			pcdup[strlen(pcdup)-1] = '\0';
			return (pcdup);
		}
	}

	return ("");

}

/*
 * Determine whether there is a -R <altroot> in the command line
 * and if so change the alternate_root global value.
 */
static void
check_altroot(int argc, char **argv)
{
	int i;
	for (i = 2; i < argc; i++)  {
		if (0 == strcmp(argv[i], "-R") && ((i+1) < argc)) {
			change_root(argv[i + 1]);
		}
	}
}

/*
 * This procedure does not return.  The command either succeeds in
 * launching a prodreg GUI or fails and outputs an error to stderr.
 */
static void
launch_stdprodreg(char **args)
{
	struct stat sb;

	if (stat(PRODREG_GUI, &sb) < 0) {
		if (errno == ENOENT)
			fail(PRODREG_NO_PROG);

		fail(PRODREG_NO_STAT);
	}

	if ((sb.st_mode & S_IXOTH) == 0)
		fail(PRODREG_NO_EXEC);

	/* This has no return value, since it doesn't return. */
	(void) execv(PRODREG_GUI, args);

}

/*
 * init_locale
 *
 * Set locale and textdomain for localization.  Note that the return value
 * of setlocale is the locale string.  It is in the form
 *
 *   "/" LC_CTYPE "/" LC_COLLATE "/" LC_CTIME "/" LC_NUMERIC "/"
 *      LC_MONETARY "/ LC_MESSAGES
 *
 *  This routine parses this result line to determine the value of
 *  the LC_MESSAGES field.  If it is "C", the default language "en"
 *  is selected.  If not, the string is disected to get only the
 *  ISO 639 two letter tag:  "en_US.ISO8859-1" becomes "en".
 *
 * Returns: nothing
 * Side effects:
 * (1) setlocale changes behavior of the application.
 * (2) textdomain changes behavior for returned messages.
 * (3) setting global_lang changes behavior for the displayed
 *     names of components (which are internationalized, sometimes).
 */
static void
init_locale()
{
	int i = 0, c, n;
	char lang[32];
	char *pc = setlocale(LC_ALL, "");
	(void) textdomain(TEXT_DOMAIN);

	(void *) memset(lang, 0, 32);
	if (pc[0] == '/') {

		/* Skip to the 6th field, which is 'LC_MESSAGES.' */
		c = 0;
		for (i = 0; (pc[i] != NULL) && (c < 6); i++) {
			if (pc[i] == '/') c++;
		}

		/* Strip off any dialect tag and character encoding. */
		n = 0;
		while ((pc[i] != NULL) && (pc[i] != '_') &&
		    (n < 32) && (pc[i] != '.')) {
			lang[n++] = pc[i++];
		}
	}

	if (i > 2) {
		if (strcmp(lang, "C") == 0) {
			global_lang = strdup("en");
		} else {
			global_lang = strdup(lang);
		}
	} else {
		global_lang = strdup("en");
	}

	debug(DEBUGINFO, "Initialize language display tag to %s\n",
	    global_lang);
}

#define	CLUSTER_ROOT "/var/sadm/system/admin/CLUSTER"

static char *
get_metacluster()
{
	char *buf;
	FILE *fp;
	int len = strlen(global_alt_root) + strlen(CLUSTER_ROOT);

	buf = (char *) malloc(len + 1);
	if (buf == NULL) fail(PRODREG_MALLOC);
	(void) sprintf(buf, "%s%s", global_alt_root, CLUSTER_ROOT);

	if ((fp = fopen(buf, "r")) != NULL) {
		char line[256];
		int x = strlen("CLUSTER=");

		if ((fgets(line, 256, fp) != NULL) &&
		    (0 == strncmp("CLUSTER=", line, x))) {
			char *pcdup = malloc(strlen(line) - x + 1);
			if (pcdup == NULL) fail(PRODREG_MALLOC);
			(void *) memset(pcdup, 0, strlen(line) - x + 1);
			(void *) memcpy(pcdup, &line[x], strlen(line) - x);
			/*
			 * Strip off the carriage return that fgets
			 * left on the end
			 */
			pcdup[strlen(pcdup) - 1] = '\0';
			return (pcdup);
		}
	}
	/* A default value which makes sense on many systems. */
	return ("SUNWCall");
}

int
main(int argc, char *argv[]) {

	/*
	 * prodreg_args is initialized so that it will be a terminated
	 * array no matter what gets initialized into the first fields.
	 */
	char *pc, *prodreg_args[] = { NULL, NULL, NULL, NULL, NULL, NULL };
	const char *ver;

	init_locale();

	if ((pc = getenv(ALTERNATE_ROOT_VARIABLE)) != NULL) {
		global_alt_root = strdup(pc);
		wsreg_set_alternate_root(global_alt_root);
	} else {
		global_alt_root = strdup("");
	}
	debug(DEBUGINFO, "PKG_INSTALL_ROOT '%s'\n", global_alt_root);

	/* Initialize Solaris Version string, for browse output */
	global_solver = (char *) malloc(80);
	ver = get_sol_ver();
	if (ver == NULL)
		fail(PRODREG_INIT);
	if (global_solver == NULL)
		fail(PRODREG_MALLOC);
	(void) sprintf(global_solver, SYSS_STR, ver);
	debug(DEBUGINFO, "sol ver = '%s'\n", global_solver);

	/* Initialize the global_ENTR_UUID string. */
	global_ENTR_UUID = get_metacluster();
	debug(DEBUGINFO, "metacluster = '%s'\n", global_ENTR_UUID);

	if (argc == 1) {

		debug(DEBUGINFO, "***launch default prodreg gui\n");
		prodreg_args[0] = PRODREG_GUI;
		launch_stdprodreg(prodreg_args);

	} else {

		switch (getcommand(argv[1])) {

		case ALT_ROOT:
			prodreg_args[0] = PRODREG_GUI;
			prodreg_args[1] = "-R";
			prodreg_args[2] = argv[2];
			global_alt_root = argv[2];
			launch_stdprodreg(prodreg_args);
			break;

		case CMD_AWT:
			if (argc > 2 && 0 == strcmp(argv[2], "--help")) {
				(void) fprintf(stdout, "%s\n",
				    PRODREG_HELP_AWT);
			} else {
				check_altroot(argc, argv);
				if (global_alt_root != NULL &&
				    global_alt_root[0] != '\0') {

					debug(DEBUGINFO,
					    "***launch awt gui with "
					    "alternate root = %s\n",
					    global_alt_root);
					prodreg_args[0] = PRODREG_GUI;
					prodreg_args[1] = "-R";
					prodreg_args[2] = global_alt_root;
					prodreg_args[3] = "-awt";
				} else {
					prodreg_args[0] = PRODREG_GUI;
					prodreg_args[1] = "-awt";
				}
				launch_stdprodreg(prodreg_args);
			}

			break;

		case CMD_BROWSE:
			interp_browse(argc, argv);
			break;

		case CMD_HELP:
			(void) fprintf(stdout, "%s\n", PRODREG_HELP);
			break;

		case CMD_INFO:
			interp_info(argc, argv);
			break;

		case CMD_SWING:
			if (argc > 2 && 0 == strcmp(argv[2], "--help")) {
				(void) fprintf(stdout, "%s\n",
				    PRODREG_HELP_SWING);
			} else {
				check_altroot(argc, argv);
				if (global_alt_root != NULL &&
				    global_alt_root[0] != '\0') {

					debug(DEBUGINFO,
					    "***launch awt gui with "
					    "alternate root = %s\n",
					    global_alt_root);
					prodreg_args[0] = PRODREG_GUI;
					prodreg_args[1] = "-R";
					prodreg_args[2] = global_alt_root;
					prodreg_args[3] = "-swing";
				} else {
					prodreg_args[0] = PRODREG_GUI;
					prodreg_args[1] = "-swing";
				}
				launch_stdprodreg(prodreg_args);
			}
			break;

		case CMD_UNINSTALL:
			interp_uninstall(argc, argv);
			break;

		case CMD_UNREGISTER:
			interp_unregister(argc, argv);
			break;

		case CMD_REGISTER:
			interp_register(argc, argv);
			break;

		case CMD_LIST:
			interp_list(argc, argv);
			break;

		case CMD_VERSION:
			(void) printf(PRODREG_VERSION);
			(void) printf("\n");
			break;

		case CMD_UNKNOWN:
			syntax_fail(argc, argv, BAD_COMMAND);

		default:
			syntax_fail(argc, argv, BAD_COMMAND);
		}
	}
	return (0);
}
