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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <strings.h>
#include <sys/param.h>
#include <unistd.h>
#include <locale.h>

#include "boolean.h"
#include "ds_article_input_stream.h"
#include "list.h"
#include "file_reader.h"
#include "article_id.h"
#include "conversion.h"
#include "string_util.h"
#include "wsreg.h"
#include "reg_comp.h"
#include "file_util.h"
#include "localized_strings.h"

/*
 * This environment variable is used to prefix an alternate
 * root to all paths used by the registry and prodreg.
 * This is the same environment variable used by pkgadd
 * and other installation tools.
 */
#define	ALTERNATE_ROOT_VARIABLE "PKG_INSTALL_ROOT"

/*
 * The DEBUG_ENV_VARIABLE is used to specify a
 * log file to which debug output should be
 * written.  This is critical for debugging because
 * the prodreg command is called (many times) from
 * an install/uninstall wizard.  Any debug output
 * that is sent to stdio or stderr can disrupt the
 * wizard.
 */
#define	DEBUG_ENV_VARIABLE "PRODREG_DEBUG"

/*
 * The version of this prodreg interface.
 */
#define	PRODREG_INTERFACE_VERSION "3.0.0"

static Boolean debug_on = FALSE;
static char *debug_filename = NULL;
static char *alternate_root = NULL;
static FILE *debug_file = NULL;

/*
 * The commands and the following #defines are used for processing the
 * command line arguments.  All valid options appear in the commands
 * array.  Each entry in the commands array has a corresponding
 * #define, which is used the switch statement in main().
 *
 * The index of each command in the array must correspond to its
 * associated #define value.
 */
static char *commands[] = {
	"swing",
	"awt",
	"register",
	"list",
	"lookup",
	"lookupProducts",
	"lookupComponents",
	"uninstall",
	"unregister",
	"version",
	"-R",
	"help",
	NULL};

#define	PRDRG_SWING		0
#define	PRDRG_AWT		1
#define	PRDRG_REGISTER		2
#define	PRDRG_LIST		3
#define	PRDRG_LOOKUP		4
#define	PRDRG_LOOKUP_PRODUCTS	5
#define	PRDRG_LOOKUP_COMPONENTS	6
#define	PRDRG_UNINSTALL		7
#define	PRDRG_UNREGISTER	8
#define	PRDRG_VERSION		9
#define	PRDRG_ALTERNATE_ROOT	10
#define	PRDRG_HELP		11

static void
vlog_message(const char *, const char *, va_list);
static void
log_message(const char *, const char *, int, ...);
static void
output_text(const char *, int, ...);
static void
input_text(const char *);
static void
syntax_error(int, char **, const char *);
static List *
get_matching_components(const char *, const char *);
static int
launch_sdtprodreg(char **);
static List *
read_articles(FILE *);
static char *
register_articles(List *);
static void
lookup(const char *, const char *);
static void
lookup_components(const char *, const char *);
static void
lookup_products(List *);
static Wsreg_component *
get_by_uninstall_location(List *, const char *);
static void
remove_parent(Wsreg_component *);
static Wsreg_component *
get_component_by_other(const char *, const char *);
static void
unregister(Wsreg_component *);
static void
unregister_articles(const char *, const char *);
static char *
get_component_attribute(Wsreg_component *, const char *);
static void
list_articles(const char *, List *);
static void
uninstall(char *, char *);


/*
 * The entry point for the prodreg legacy command line interface.  This
 * interface (the name of the binary and its options and arguments)
 * cannot change without breaking old clients.
 */
int
main(int argc, char **argv)
{
	/*
	 * Valid arguments:
	 *    <none> - launch sdtprodreg
	 *    "swing" - launch sdtprodreg -swing
	 *    "awt"   - launch sdtprodreg -awt
	 *    "register"
	 *    "list"
	 *    "lookup <mnemonic> [id]"
	 *    "lookupProducts <mnemonic>"
	 *    "lookupComponents <mnemonic> <id>"
	 *    "uninstall <mnemonic> <fslocation>" - launch sdtprodreg -uninstall
	 *    "unregister <mnemonic> <fslocation>"
	 */
	int index = 0;
	String_map *arg_map = _wsreg_stringmap_create(commands);

	setlocale(LC_ALL, "");
	textdomain(TEXT_DOMAIN);

	/*
	 * Set the alternate root from the environment variable.
	 * This may be overridden with a "-R" flag.
	 */
	alternate_root = getenv(ALTERNATE_ROOT_VARIABLE);
	if (alternate_root != NULL) {
		wsreg_set_alternate_root(alternate_root);
	} else {
		alternate_root = "";
	}

	debug_filename = getenv(DEBUG_ENV_VARIABLE);
	if (debug_filename != NULL) {
		debug_on = TRUE;
	}

	log_message("COMMAND", "prodreg ", 0);

	for (index = 1; index < argc; index++)
		log_message(NULL, "%s ", 1, argv[index]);
	log_message(NULL, "\n", 0);

	if (!(argc > 1)) {
		/*
		 * No arguments; launch the viewer.
		 */
		char *prodreg_args[] = {
			"-R",
			NULL,
			NULL};
		prodreg_args[1] = alternate_root;
		log_message("COMMAND", " < no arg>\n", 0);
		launch_sdtprodreg(prodreg_args);
	} else {
		index = 1;
		while (index < argc) {
			int command = arg_map->get_id(arg_map, argv[index]);
			switch (command) {
			case PRDRG_SWING:
			{
				char *prodreg_args[] = {
					"-R",
					NULL,
					"-swing",
					NULL};
				prodreg_args[1] = alternate_root;
				launch_sdtprodreg(prodreg_args);
				break;
			}

			case PRDRG_AWT:
			{
				char *prodreg_args[] = {
					"-R",
					NULL,
					"-awt",
					NULL};
				prodreg_args[1] = alternate_root;
				launch_sdtprodreg(prodreg_args);
				break;
			}

			case PRDRG_REGISTER:
			{
				List *arg_list = _wsreg_list_create();
				char *id = NULL;
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
					alternate_root);

				/*
				 * Make a list of the remaining
				 * arguments.
				 */
				if (argc > index + 1) {
					for (++index; index < argc;
						index++) {
						arg_list->add_element(
							arg_list,
							    argv[index]);
					}
				}
				switch (arg_list->size(arg_list)) {
				case 0:
					id =
					    register_articles(arg_list);
					output_text("\n", 0);
					break;

				case 2:
				case 4:
					id = register_articles(
						arg_list);
					output_text("%s\n", 1, id);
					break;

				default:
					syntax_error(argc, argv,
					    PRODREG_BAD_ARG_COUNT);
				}
				fflush(stdout);
				arg_list->free(arg_list, NULL);
				break;
			}

			case PRDRG_LIST: {
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
					alternate_root);

				if (argc > index + 3) {
					char *selector;
					List *fields =
					    _wsreg_list_create();

					index++;
					selector = argv[index];

					/*
					 * Build a list of fields we
					 * are interested in.
					 */
					for (++index; index < argc;
						++index) {
						fields->add_element(
							fields,
							    argv[index]);
					}

					/*
					 * list_articles will print
					 * the requested article
					 * information.
					 */
					list_articles(selector,
					    fields);
				} else {
					syntax_error(argc, argv,
					    PRODREG_BAD_LIST);
				}
				break;
			}

			case PRDRG_LOOKUP:
			{
				char *mnemonic = NULL;
				char *id = NULL;
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
					alternate_root);

				if (argc > index + 1)
					mnemonic = argv[++index];
				if (argc > index + 1)
					id = argv[++index];
				if (mnemonic == NULL) {
					syntax_error(argc, argv,
					    PRODREG_BAD_LOOKUP);
				} else {
					lookup(mnemonic, id);
				}
				break;
			}

			case PRDRG_LOOKUP_PRODUCTS:
			{
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
				    alternate_root);

				if (argc > index + 1) {
					List *mnemonics =
					    _wsreg_list_create();
					for (++index; index < argc;
						index++) {
						mnemonics->add_element(
							mnemonics,
							    argv[index]);
					}
					lookup_products(mnemonics);
					mnemonics->free(mnemonics,
					    NULL);
				} else {
					syntax_error(argc, argv,
					    PRODREG_BAD_LOOKUP_PROD);
				}
				break;
			}

			case PRDRG_LOOKUP_COMPONENTS:
			{
				char *mnemonic = NULL;
				char *id = NULL;
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
				    alternate_root);

				if (argc > index + 1)
					mnemonic = argv[++index];
				if (argc > index + 1)
					id = argv[++index];
				if (mnemonic == NULL || id == NULL) {
					syntax_error(argc, argv,
					    PRODREG_BAD_LOOKUP_COMP);
				} else {
					lookup_components(mnemonic, id);
				}
				break;
			}

			case PRDRG_UNINSTALL:
			{
				char *mnemonic = NULL;
				char *id = NULL;
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
				    alternate_root);

				if (argc > index + 1)
					mnemonic = argv[++index];
				if (argc > index + 1)
					id = argv[++index];
				if (mnemonic == NULL ||
				    id == NULL) {
					syntax_error(argc, argv,
					    PRODREG_BAD_UNINSTALL_ARGS);
				} else {
					uninstall(mnemonic, id);
				}
				break;
			}

			case PRDRG_UNREGISTER:
			{
				char *mnemonic = NULL;
				char *location = NULL;
				(void) wsreg_initialize(WSREG_INIT_NORMAL,
				    alternate_root);

				if (argc > index + 1)
					mnemonic = argv[++index];
				if (argc > index + 1)
					location = argv[++index];
				if (mnemonic == NULL ||
				    location == NULL) {
					/*
					 * Not enough information to perform
					 * the unregister.
					 */
					syntax_error(argc, argv,
					    PRODREG_BAD_UNREGISTER_ARGS);
				} else {
					unregister_articles(mnemonic, location);
				}
				break;
			}

			case PRDRG_VERSION:
				output_text("%s\n\n", 1,
				    PRODREG_INTERFACE_VERSION);
				fflush(stdout);
				break;

			case PRDRG_ALTERNATE_ROOT:
			{
				if (argc > index + 1) {
					/*
					 * The next argument is
					 * interpreted as the
					 * alternate root.  The
					 * command line overrides
					 * the environment variable.
					 */
					alternate_root = argv[++index];
					wsreg_set_alternate_root(
						alternate_root);
				}
				break;
			}

			case PRDRG_HELP:
				output_text(PRODREG_HELP, 0);
				break;

			default:
			{
				char *message = wsreg_malloc(sizeof (char) *
				    (strlen(PRODREG_BAD_SUBCOMMAND) +
					strlen(argv[index]) + 1));
				log_message("DEBUG", "bad command %s\n", 1,
				    argv[index]);
				(void) sprintf(message,
				    PRODREG_BAD_SUBCOMMAND,
				    argv[index]);
				syntax_error(argc, argv,
				    message);
				free(message);
				exit(1);
			}
			}
			index++;
		}
	}
	arg_map->free(arg_map);
	log_message("DEBUG", "prodreg exit\n", 0);
	return (0);
}

/*
 * Varargs version of the log_message function.  This
 * function logs its output if the debug output
 * file has been specified with the appropriate
 * environment variable.
 */
static void
vlog_message(const char *prefix, const char *format, va_list ap)
{
	if (debug_on) {
		if (debug_file == NULL) {
			debug_file = fopen(debug_filename, "a+");
			if (debug_file == NULL) {
				return;
			}

			/*
			 * Make the log file unbuffered so calls
			 * to fflush are not required.
			 */
			setbuf(debug_file, NULL);

		}
		if (debug_file != NULL) {
			if (prefix != NULL) {
				(void) fprintf(debug_file, "%s: ", prefix);
			}
			(void) vfprintf(debug_file, format, ap);
		}
	}
}

/*
 * Logs the specified message to the debug output
 * file, if specified with the appropriate environment
 * variable.
 */
static void
log_message(const char *prefix, const char *format, /*ARGSUSED*/int count, ...)
{
	va_list ap;
	va_start(ap, count);
	vlog_message(prefix, format, ap);
}

/*
 * Sends the specified output to stdout.  If logging is enabled,
 * the output will also be sent to the log file.
 */
static void
output_text(const char *format, /*ARGSUSED*/int count, ...)
{
	static Boolean need_prefix = TRUE;
	char *prefix = "OUT";
	va_list ap;
	va_start(ap, count);
	vlog_message(need_prefix?prefix:NULL, format, ap);
	(void) vfprintf(stdout, format, ap);
	if (format[strlen(format) - 1] == '\n') {
		need_prefix = TRUE;
	} else {
		need_prefix = FALSE;
	}
}

/*
 * This function is used to log input.  This function is passed
 * into the File_reader object as the echo callback.  Each line
 * read in is sent to this function.
 */
static void
input_text(const char *line)
{
	char *prefix = "IN";
	log_message(prefix, "%s\n", 1, line);
}

/*
 * This function is called when a syntax error has been
 * detected.  The arguments passed into prodreg are used
 * in the output.  The specified message is printed to
 * stderr.
 */
static void
syntax_error(int argc, char **argv, const char *message)
{
	int index;

	if (message != NULL) {
		(void) fprintf(stderr, message);
		(void) fprintf(stderr, "\n");
	}

	/*
	 * Recreate the command.
	 */
	(void) fprintf(stderr, "    prodreg ");
	for (index = 0; index < argc; index++) {
		(void) fprintf(stderr, " %s", argv[index]);
	}
	(void) fprintf(stderr, "\n");

	(void) fprintf(stderr, "%s\n", PRODREG_USAGE_TEXT);
}

/*
 * Launches the prodreg viewer (/usr/dt/bin/sdtprodreg)
 * with the specified arguments.  args must be
 * NULL-terminated.
 */
static int
launch_sdtprodreg(char **args)
{
	File_util *file_util = _wsreg_fileutil_initialize();
	char *command_template = "/usr/dt/bin/sdtprodreg";
	char *command_buffer = (char *)
	    wsreg_malloc(sizeof (char) * strlen(command_template) + 1);
	(void) sprintf(command_buffer, command_template);
	if (!file_util->exists(command_buffer)) {
		/*
		 * Prodreg viewer is not available.
		 */
		(void) fprintf(stderr, PRODREG_VIEWER_NOT_FOUND,
		    command_buffer);
		(void) fprintf(stderr, "\n");
		fflush(stderr);
		free(command_buffer);
		return (0);
	} else {
		/*
		 * This does not have a return value because execv does
		 * not return.
		 */
		execv(command_buffer, args);
	}
	free(command_buffer);
	return (0);
}

/*
 * Reads a list of articles from the specified FILE.
 * This function always returns a valid List.
 *
 * This function is used to read datasheets in from
 * stdin during product registration.
 */
static List *
read_articles(FILE *in)
{
	List *result = _wsreg_list_create();

	if (in != NULL) {
		/*
		 * Set up a file reader to read the articles
		 */
		char *end_tokens[] = {
			"--",
			"\5",
			"\255",
			NULL};
		Ds_article_input_stream *ais = NULL;
		File_reader *fr = _wsreg_freader_create(in,
		    end_tokens);
		fr->set_echo_function(fr, input_text);

		/*
		 * Set up the datasheet article input stream.
		 */
		ais = _wsreg_dsais_open(fr);

		if (ais != NULL) {
			/*
			 * Read the articles into a list.
			 */
			while (ais->has_more_articles(ais)) {
				Article *a = ais->get_next_article(ais);
				if (a != NULL) {
					/*
					 * Be sure the new Article has a valid
					 * id.
					 */
					a->generate_id(a);

					log_message("DEBUG",
					    " < adding article %s [id=%s]>\n",
					    2, a->get_mnemonic(a),
					    a->get_id(a));
					result->add_element(result, a);
				}
			}
			ais->close(ais);
		}
		fr->free(fr);
	}

	return (result);
}

/*
 * Registers articles.  The arguments in the specified
 * list are (in order):
 *
 * install location
 * datasheet filename
 * parent mnemonic
 * parent id
 *
 * All of these arguments are optional.
 *
 * The install location refers to the directory in which the software
 * has been installed.
 *
 * The datasheet filename specifies the name of the file that contains
 * the data representing articles to be registered.  If the datasheet
 * filename is not provided, the datasheet information will be read
 * from stdin.
 *
 * The parent mnemonic specifies the name of the article which is the
 * parent of the article(s) being registered with this call.
 *
 * The parent id specifies the instance of the article which is the
 * parent of the article(s) being registered with this call.
 *
 * This function returns the id of the article being registered.
 */
static char *
register_articles(List *arg_list)
{
	/*
	 * The default datasheet file is stdin.
	 */
	FILE *in = stdin;
	char *result = NULL;
	char *location = NULL;
	char *parent_mnemonic = NULL;
	char *parent_id = NULL;
	Wsreg_component *parent_component = NULL;
	List *matches = NULL;
	List *article_list = NULL;
	Conversion *conversion;

	if (arg_list->size(arg_list) > 0) {
		/*
		 * Install location, datasheet filename.
		 */
		char *path;
		location = (char *)arg_list->element_at(arg_list, 0);
		if (strcmp(location, "-") == 0) {
			location = NULL;
		}
		path = (char *)arg_list->element_at(arg_list, 1);
		in = NULL;
		if (path != NULL) {
			in = fopen(path, "r");
		}
		if (in == NULL) {
			(void) fprintf(stderr, PRODREG_CANT_READ_FILE,
			    path);
			(void) fprintf(stderr, "\n");
			return ("");
		}

		if (arg_list->size(arg_list) > 2) {
			/*
			 * Parent mnemonic, parent id.
			 */
			parent_mnemonic =
			    (char *)arg_list->element_at(arg_list, 2);
			parent_id = (char *)arg_list->element_at(arg_list, 3);
			if (parent_mnemonic != NULL &&
			    parent_id != NULL) {
				matches =
				    get_matching_components(parent_mnemonic,
					parent_id);
				if (matches != NULL &&
				    matches->size(matches) == 1) {
					parent_component =
					    (Wsreg_component *)
					    matches->element_at(matches, 0);
				} else {
					(void) fprintf(stderr,
					    PRODREG_NO_SUCH_COMPONENT,
					    parent_mnemonic, parent_id);
					(void) fprintf(stderr, "\n");

				}
			}
		}
	}

	article_list = read_articles(in);
	conversion = _wsreg_conversion_create(NULL);

	/*
	 * Creates associations between parent Article and
	 * child Article.
	 */
	conversion->create_associations(article_list);

	/*
	 * Convert the articles to Wsreg_component structures
	 * and register.
	 */
	article_list->reset_iterator(article_list);
	while (article_list->has_more_elements(article_list)) {
		Article *a =
		    (Article *)article_list->next_element(article_list);
		/*
		 * The install location passed in overrides that in the
		 * datasheet.  I am not sure where this would be applicable.
		 * Is it really that the datasheet is incorrect and the
		 * user knows best here?
		 */
		if (location != NULL) {
			a->set_property(a, "installlocation", location);
		}
		conversion->add_article(conversion, a);
		result = a->get_id(a);
	}
	conversion->register_components(conversion, parent_component, TRUE);
	conversion->free(conversion);

	if (matches != NULL) {
		matches->free(matches, (Free)wsreg_free_component);
	}
	return (result);
}

/*
 * Returns a list of registered components that have the
 * specified mnemonic as a unique_name and the specified
 * id is registered in the component-specific data.
 *
 * If the id is NULL, only the unique_name is compared.
 */
static List *
get_matching_components(const char *mnemonic, const char *id)
{
	Reg_comp *comp_obj = _wsreg_comp_initialize();
	List *result = _wsreg_list_create();
	if (mnemonic != NULL) {
		/*
		 * We cannot use a standard registry query because
		 * the old prodreg performed a case-insensitive
		 * compare to the mnemonic.
		 */
		Wsreg_component **comps = wsreg_get_all();
		if (comps != NULL) {
			int index = 0;
			String_util *sutil = _wsreg_strutil_initialize();
			while (comps[index] != NULL) {
				Wsreg_component *comp = comps[index];
				if (sutil->equals_ignore_case(mnemonic,
				    wsreg_get_unique_name(comp))) {
					if (id == NULL ||
					    strcmp(id,
						wsreg_get_data(comp,
						    "id")) == 0) {
						/*
						 * Found a matching component.
						 */
						result->add_element(result,
						    comp_obj->clone(comp));
					}
				}
				index++;
			}
			comp_obj->free_array(comps);
		}
	}
	return (result);
}

/*
 * Takes a mnemonic as an argument, if the
 * mnemonic (unique id) has been registered,
 * the output looks like this:
 *
 *   test 1.0.1
 * ID=534724607   mnemonic = test
 * installLocation = /tmp
 * versionVector = 1.0.1
 *
 */
static void
lookup(const char *mnemonic, const char *id)
{
	List *matches = get_matching_components(mnemonic, id);
	if (matches != NULL) {
		matches->reset_iterator(matches);
		while (matches->has_more_elements(matches)) {
			Wsreg_component *comp =
			    (Wsreg_component *)matches->next_element(matches);
			char *location = NULL;
			char *id = NULL;

			output_text("  %s", 1,
			    wsreg_get_display_name(comp, "en"));
			output_text(" %s\n", 1, wsreg_get_version(comp));

			id = wsreg_get_data(comp, "id");
			if (id == NULL) {
				/*
				 * If the component does not currently have
				 * an id, generate one and set it into
				 * the component.
				 */
				Article_id *article_id =
				    _wsreg_artid_initialize();
				id = article_id->create_id();
				wsreg_set_data(comp, "id", id);
			}
			output_text("ID=%s", 1, id);
			free(id);
			output_text("    mnemonic=%s", 1,
			    wsreg_get_unique_name(comp));
			location = wsreg_get_location(comp);
			if (location != NULL) {
				output_text("\ninstallLocation=%s", 1,
				    location);
			}
			output_text("\nversionVector=%s", 1,
			    wsreg_get_version(comp));
			output_text("\n\n", 0); /* from Registry.lookup() */
		}
		matches->free(matches, (Free)wsreg_free_component);
	}
}

/*
 * Outputs the component mnemonics for the product
 * matching the specified mnemonic and id.
 */
static void
lookup_components(const char *mnemonic, const char *id)
{
	if (mnemonic != NULL && id != NULL) {
		Reg_comp *comp_obj = _wsreg_comp_initialize();
		List *matches = get_matching_components(mnemonic, id);
		if (matches != NULL && matches->size(matches) != 0) {
			matches->reset_iterator(matches);
			if (matches->has_more_elements(matches)) {
				Wsreg_component *comp =
				    (Wsreg_component *)
				    matches->next_element(matches);
				Wsreg_component **children =
				    wsreg_get_child_components(comp);
				if (children != NULL) {
					int index = 0;
					while (children[index] != NULL) {
						output_text("%s ", 1,
						    wsreg_get_unique_name(
							    children[index]));
						index++;
					}
					output_text("\n", 0);
					comp_obj->free_array(children);
				}
			}
			matches->free(matches, (Free)wsreg_free_component);
		} else {
			(void) fprintf(stderr, PRODREG_NOT_REGISTERED,
			    mnemonic, id);
			(void) fprintf(stderr, "\n");
		}
	}
}   

/*
 * This function is called to fulfill the "lookupProducts"
 * prodreg command.
 *
 * Each mnemonic in the specified list for which there is
 * a component registered is printed on a single line of output.
 */
static void
lookup_products(List *mnemonics)
{
	if (mnemonics != NULL && mnemonics->size(mnemonics) > 0) {
		mnemonics->reset_iterator(mnemonics);
		while (mnemonics->has_more_elements(mnemonics)) {
			char *mnemonic =
			    (char *)mnemonics->next_element(mnemonics);
			List *matches = get_matching_components(mnemonic, NULL);
			if (matches != NULL && matches->size(matches) > 0) {
				output_text("%s ", 1, mnemonic);
				matches->free(matches,
				    (Free)wsreg_free_component);
			}
		}
	}
	output_text("\n", 0);
}

/*
 * Returns the component from the specified list of components
 * that has an uninstaller in the specified location.
 */
static Wsreg_component *
get_by_uninstall_location(List *comp_list, const char *location)
{
	Wsreg_component *result = NULL;
	if (comp_list != NULL) {
		String_util *sutil = _wsreg_strutil_initialize();
		Wsreg_component *comp = NULL;
		comp_list->reset_iterator(comp_list);
		while (comp_list->has_more_elements(comp_list)) {
			Wsreg_component *parent = NULL;
			comp = (Wsreg_component *)
			    comp_list->next_element(comp_list);
			/*
			 * We are looking for the component with the
			 * specified uninstaller location.  Check all
			 * parents until a match is found.
			 */
			for (parent = comp; parent != NULL;
				parent = wsreg_get_parent(parent)) {
				char *loc = wsreg_get_uninstaller(parent);

				/*
				 * The component will be freed from the
				 * list upon return.
				 */
				if (parent != comp)
					wsreg_free_component(parent);

				if (loc != NULL &&
				    sutil->contains_substring(loc, location)) {
					/*
					 * Return the component, not the
					 * component's parent.
					 */
					return (comp);
				}
			}
		}
	}
	return (result);
}

/*
 * Modifies the parent of the specified component
 * (if applicable) such that the specified component
 * is no longer a child of the parent and is not
 * required by the parent.
 */
static void
remove_parent(Wsreg_component *comp)
{
	if (comp != NULL) {
		Wsreg_component *parent = wsreg_get_parent(comp);
		if (parent != NULL) {
			wsreg_remove_child_component(parent, comp);
			wsreg_remove_required_component(parent, comp);
			wsreg_register(parent);
		}
	}
}

/*
 * Finds the Wsreg_component identified by the mnemonic and
 * other information.
 *
 * "other" can be: "-": wildcard - matches any Article registered
 *			with the specified mnemonic.  Seems
 *			dangerous, but that's the way the old prodreg works.
 *		 uninstaller directory
 *		 id (9-digit random number assigned to the article)
 *
 * This is not a good interface, but we cannot change
 * the functionality of the original product registry.  This method's
 * arguments come directly from the command line.
 */
static Wsreg_component *
get_component_by_other(const char *mnemonic, const char *other)
{
	Wsreg_component *result = NULL;
	if (mnemonic != NULL && other != NULL) {
		Article_id *article_id = _wsreg_artid_initialize();
		Boolean other_is_id = article_id->is_legal_id(other);
		Boolean other_is_wildcard = (strcmp(other, "-") == 0);
		char *id = NULL;
		List *matches = NULL;
		String_util *sutil = _wsreg_strutil_initialize();

		if (other_is_id)
			id = sutil->clone(other);

		matches = get_matching_components(mnemonic, id);
		if (matches != NULL) {
			/*
			 * Find the Article to unregister.
			 */
			if (other_is_id || other_is_wildcard) {
				result =
				    matches->element_at(matches,
					0);
			} else {
				result =
				    get_by_uninstall_location(
					    matches, other);
			}

			if (result != NULL) {
				/*
				 * Found the correct
				 * component.  Remove the component from
				 * the list.
				 */
				matches->remove(matches, result, NULL);
			}
			matches->free(matches,
			    (Free)wsreg_free_component);
		}
		if (id != NULL)
			free(id);
	}
	return (result);
}

/*
 * Unregisteres the specified component and its children.
 */
static void
unregister(Wsreg_component *comp)
{
	if (comp != NULL) {
		Wsreg_component **children = wsreg_get_child_components(comp);
		wsreg_unregister(comp);
		if (children != NULL) {
			int index = 0;
			while (children[index] != NULL) {
				unregister(children[index]);
				index++;
			}
			wsreg_free_component_array(children);
		}
	}
}

/*
 * Unregisters the article specified by the mnemonic and
 * "other".  This function fulfills the "unregister" prodreg
 * command.
 *
 * "other" can be: "-": wildcard - matches any Article registered
 *			with the specified mnemonic.  Seems
 *			dangerous, but that's the way it works.
 *		 uninstaller directory
 *		 id (9-digit random number assigned to the article)
 *
 * This is not a good function prototype, but we cannot change
 * the functionality of the original product registry.  See
 * Article.java:lookupByUnloc for the original comments.
 */
static void
unregister_articles(const char *mnemonic, const char *other)
{
	if (mnemonic != NULL && other != NULL) {
		Wsreg_component *comp = get_component_by_other(mnemonic, other);
		if (comp != NULL) {
			/*
			 * Found the correct
			 * component.  Now unregister.
			 */
			remove_parent(comp);
			unregister(comp);
		} else {
			/*
			 * The specified component is not registered.
			 */
			(void) fprintf(stderr, PRODREG_NO_SUCH_COMPONENT,
			    mnemonic, other);
			(void) fprintf(stderr, "\n");
		}
	}
}

/*
 * Returns data associated with the specified prodreg 2.0
 * attribute.  This function takes into account the mapping
 * between attributes in Prodreg 2.0 Article objects and
 * the Product Install Registry Wsreg_component structure
 * fields.
 */
static char *
get_component_attribute(Wsreg_component *comp, const char *selector)
{
	if (comp != NULL && selector != NULL) {
		if (strcmp(selector, "mnemonic") == 0) {
			return (wsreg_get_unique_name(comp));
		} else if (strcmp(selector, "version") == 0) {
			return (wsreg_get_version(comp));
		} else if (strcmp(selector, "vendor") == 0) {
			return (wsreg_get_vendor(comp));
		} else if (strcmp(selector, "installlocation") == 0) {
			return (wsreg_get_location(comp));
		} else if (strcmp(selector, "title") == 0) {
			return (wsreg_get_display_name(comp, "en"));
		} else if (strcmp(selector, "uninstallprogram") == 0) {
			return (wsreg_get_uninstaller(comp));
		} else {
			return (wsreg_get_data(comp, selector));
		}
	}
	return (NULL);
}

/*
 * This function supports the prodreg 2.0 "list" command.
 * The list command takes an attribute name to select on.
 * Any component that has data (any data other than NULL)
 * stored under the specified attribute name will be selected
 * for the list.
 *
 * The "fields" specifies attributes we want to list for each
 * selected component.  The output of this function is a
 * table of data, one line for each selected component.
 */
static void
list_articles(const char *selector, List *fields)
{
	Wsreg_component **components = wsreg_get_all();

	if (components != NULL) {
		int index = 0;
		while (components[index] != NULL) {
			Wsreg_component *comp = components[index];

			/*
			 * Select components based on the selector.  If
			 * the component has the specified information,
			 * a line of text containing the component's
			 * specified field values.
			 */
			if (get_component_attribute(comp, selector) != NULL) {
				/*
				 * We found a matching component.  Print out
				 * a line of text with our attributes.
				 */
				int field_index = 0;
				fields->reset_iterator(fields);
				while (fields->has_more_elements(fields)) {
					char *field = (char *)
					    fields->next_element(fields);
					char *value =
					    get_component_attribute(comp,
						field);
					if (field_index > 0) {
						output_text("\t", 0);
					}
					output_text("%s", 1,
					    value?value:"NULL");
					field_index++;
				}
				output_text("\n", 0);
			}
			index++;
		}
	}
}

/*
 * Uninstall the product identified by the specified
 * mnemonic and other information.  The "other" can be one of:
 *
 * "other" can be: "-": wildcard - matches any Article registered
 *			with the specified mnemonic.  Seems
 *			dangerous, but that's the way the old prodreg works.
 *		 uninstaller directory
 *		 id (9-digit random number assigned to the article)
 *
 * This is not a good interface, but we cannot change
 * the functionality of the original product registry.  This method's
 * arguments come directly from the command line.
 */
static void
uninstall(char *mnemonic, char *other)
{
	Wsreg_component *comp = NULL;
	if (mnemonic == NULL || other == NULL) {
		/*
		 * Bad arguments passed in.  Log a message and exit.
		 */
		log_message("ERROR", "uninstall called with bad arguments "
		    "(%s, %s)\n", 2,
		    mnemonic?mnemonic:"NULL", other?other:"NULL");
		return;
	}
	comp = get_component_by_other(mnemonic, other);
	if (comp != NULL) {
		/*
		 * Found the correct
		 * component.  Now uninstall.
		 */
		char *uninstaller = wsreg_get_uninstaller(comp);
		if (uninstaller != NULL) {
			if (!system(uninstaller)) {
				output_text("%s\n", 1,
				    PRODREG_UNINSTALL_SUCCESS);
			} else {
				/*
				 * The uninstall call failed.
				 */
				(void) fprintf(stderr, PRODREG_BAD_SYSTEM_CALL,
				    uninstaller);
				(void) fprintf(stderr, "\n");
			}
		} else {
			/*
			 * This component has no uninstaller.
			 */
			(void) fprintf(stderr, PRODREG_NO_UNINSTALLER,
			    wsreg_get_display_name(comp, "en"));
			(void) fprintf(stderr, "\n");
		}
	} else {
		/*
		 * The component is not registered.
		 */
		(void) fprintf(stderr, PRODREG_NO_SUCH_COMPONENT,
		    mnemonic, other);
		(void) fprintf(stderr, "\n");
	}
}
