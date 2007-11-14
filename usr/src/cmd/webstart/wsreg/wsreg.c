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

#pragma ident	"@(#)wsreg.c	1.21	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <unistd.h>
#include <fcntl.h>
#include <strings.h>
#include <pwd.h>
#include <exec_attr.h>
#include <secdb.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <limits.h>
#include <sys/param.h>
#include <errno.h>
#include <signal.h>
#include <assert.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include "wsreg.h"
#include "wsreg_private.h"
#include "localized_strings.h"
#include "file_util.h"
#include "article.h"
#include "unz_article_input_stream.h"
#include "conversion.h"
#include "progress.h"
#include "string_util.h"
/*
 * This is the main entry point of the product registry.  This module contains
 * the public functions comprising the Product Install Registry API.
 */

#define	OLD_REG_FILE	"/var/sadm/install/swProductRegistry"

#define	PRODREG_CLI	"/usr/bin/prodreg"
#define	RBAC_CLI	"/usr/bin/pfexec"
#define	WSREG_EXEC_FAILED	0xde

/* this will prefix any instance of '\' '{' or '}' with '\' */
#define	ESCAPE(x)	(_escape((x), "\\{}", '\\'))

static _Wsreg_function_table *ftable = NULL;
static Wsreg_init_level initialized = WSREG_NOT_INITIALIZED;
static char *_alternate_root = NULL;

extern _Wsreg_function_table* _wsreg_simple_init(_Wsreg_function_table*);

/*
 * This is the set of initializers used to initialize the function
 * table.  Each successive initializer may take the function table
 * and insert its own methods.
 *
 * For now, we only have the simple text-based registry.
 */
static void* initializers[] = {(void*)_wsreg_simple_init, NULL};

static int		_private_exec(char **);
static boolean_t	_write_auth_granted(void);
static void		verify_function_table(void);
static char		*_escape(char *, char *, char);

/*
 * This function checks to make sure the current user has
 * the right to modify the registry
 */
static boolean_t
_write_auth_granted(void)
{
	uid_t	ruid;
	struct passwd *pwp;

	/* get the user's effective uid */
	ruid = geteuid();

	/* find the passwd entry corresponding to this euid */
	if ((pwp = getpwuid(ruid)) == NULL) {
		/* no passwd entry for this user! */
		return (B_FALSE);
	}

	/*
	 * see if the prodreg command exists in a profile
	 * that has been granted to the user
	 */
	if (getexecuser(pwp->pw_name, KV_COMMAND,
	    PRODREG_CLI, GET_ONE) == NULL) {
		return (B_FALSE);
	} else {
		/*
		 * This means that the prodreg command can
		 * be run by this user and inherit the
		 * security attributes given to it via the
		 * exec_attr RBAC database.
		 */
		return (B_TRUE);
	}
}

/*
 * This function invokes /usr/bin/prodreg register, using
 * pfexec in order to gain the required authorizations
 * needed to modify the registry.
 *
 * Syntax:
 *
 * prodreg register -u uuid
 *   [-b backward-compatible-version ] *
 *   [-c child-uuid '{' instance# '}' '{' version '}'] *
 *   [-d dependent-uuid '{' instance# '}' '{' version '}'] *
 *   [-D attribute '{' value '}' ] *
 *   [-n display-name '{' language-tag '}' ] *
 *   [-p location ]
 *   [-P parent-uuid '{' instance# '}' '{' version '}']
 *   [-r required-uuid '{' instance# '}' '{' version '}'] *
 *   [-R alt_root ]
 *   [-t (PRODUCT | FEATURE | COMPONENT) ] ----> default: COMPONENT
 *   [-U unique-name ]
 *   [-v prod-version ]
 *   [-V vendor-string ]
 *   [-x uninstaller-command ]
 *
 * Anything with a '*' can appear more than once in the command line.
 * Other options can only appear zero or one time.  The -u uuid option
 * *MUST* be present.
 *
 */
int
_private_prodreg_register(Wsreg_component *comp)
{

	int		i;
	char		*argv[1024];
	int		argc = 0;
	char		**tmpp;
	char		*tmp;
	Wsreg_component	**tmpc;
	char		buf[MAXPATHLEN];

	if (access(PRODREG_CLI, X_OK) != 0) {
		/* can't find prodreg */
		return (1);
	}

	/* form arguments to prodreg */
	argv[argc++] = RBAC_CLI;
	argv[argc++] = PRODREG_CLI;
	argv[argc++] = "register";
	argv[argc++] = "-u";
	argv[argc++] = wsreg_get_id(comp);

	/* backwards compatible versions */
	for (tmpp = wsreg_get_compatible_versions(comp);
		(tmpp != NULL) && (*tmpp != NULL);
		tmpp++) {
		argv[argc++] = "-b";
		argv[argc++] = *tmpp;
	}

	/* parent */
	if (wsreg_get_parent(comp) != NULL) {
		argv[argc++] = "-P";
		(void) snprintf(buf, MAXPATHLEN, "%s{%d}{%s}",
		    ESCAPE(wsreg_get_id(wsreg_get_parent(comp))),
		    wsreg_get_instance(wsreg_get_parent(comp)),
		    ESCAPE(wsreg_get_version(wsreg_get_parent(comp))));
		argv[argc++] = strdup(buf);
	}

	/* children */
	for (tmpc = wsreg_get_child_components(comp);
		(tmpc != NULL) && (*tmpc != NULL);
		tmpc++) {
		argv[argc++] = "-c";
		(void) snprintf(buf, MAXPATHLEN, "%s{%d}{%s}",
		    ESCAPE(wsreg_get_id(*tmpc)),
		    wsreg_get_instance(*tmpc),
		    ESCAPE(wsreg_get_version(*tmpc)));
		argv[argc++] = strdup(buf);
	}

	/* dependents */
	for (tmpc = wsreg_get_dependent_components(comp);
		(tmpc != NULL) && (*tmpc != NULL);
		tmpc++) {
		argv[argc++] = "-d";
		(void) snprintf(buf, MAXPATHLEN, "%s{%d}{%s}",
		    ESCAPE(wsreg_get_id(*tmpc)),
		    wsreg_get_instance(*tmpc),
		    ESCAPE(wsreg_get_version(*tmpc)));
		argv[argc++] = strdup(buf);
	}

	/* requirements */
	for (tmpc = wsreg_get_required_components(comp);
		(tmpc != NULL) && (*tmpc != NULL);
		tmpc++) {
		argv[argc++] = "-r";
		(void) snprintf(buf, MAXPATHLEN, "%s{%d}{%s}",
		    ESCAPE(wsreg_get_id(*tmpc)),
		    wsreg_get_instance(*tmpc),
		    ESCAPE(wsreg_get_version(*tmpc)));
		argv[argc++] = strdup(buf);
	}

	/* attributes */
	if ((tmpp = wsreg_get_data_pairs(comp)) != NULL) {
		while (*tmpp != NULL)  {
			argv[argc++] = "-D";
			(void) snprintf(buf, MAXPATHLEN, "%s{%s}",
			    ESCAPE(*tmpp), ESCAPE(*(tmpp + 1)));
			argv[argc++] = strdup(buf);
			tmpp += 2;
		}
	}

	/* display name */
	for (tmpp = wsreg_get_display_languages(comp);
		(tmpp != NULL) && (*tmpp != NULL);
		tmpp++) {
		argv[argc++] = "-n";
		(void) snprintf(buf, MAXPATHLEN, "%s{%s}",
		    ESCAPE(wsreg_get_display_name(comp, *tmpp)),
		    ESCAPE(*tmpp));
		argv[argc++] = strdup(buf);
	}

	/* location */
	if ((tmp = wsreg_get_location(comp)) != NULL) {
		argv[argc++] = "-p";
		argv[argc++] = tmp;
	}

	/* alt root */
	if (((tmp = wsreg_get_alternate_root()) != NULL) &&
	    (strlen(tmp) > 0)) {
		argv[argc++] = "-R";
		argv[argc++] = tmp;
	}

	/* type */
	switch (wsreg_get_type(comp)) {
	case WSREG_PRODUCT:
		argv[argc++] = "-t";
		argv[argc++] = "PRODUCT";
		break;
	case WSREG_FEATURE:
		argv[argc++] = "-t";
		argv[argc++] = "FEATURE";
		break;
	case WSREG_COMPONENT:
		/* the default is COMPONENT so we need not repeat it */
		break;
	}

	/* unique name */
	if ((tmp = wsreg_get_unique_name(comp)) != NULL) {
		argv[argc++] = "-U";
		argv[argc++] = tmp;
	}

	/* version */
	if ((tmp = wsreg_get_version(comp)) != NULL) {
		argv[argc++] = "-v";
		argv[argc++] = tmp;
	}

	/* vendor string */
	if ((tmp = wsreg_get_vendor(comp)) != NULL) {
		argv[argc++] = "-V";
		argv[argc++] = tmp;
	}

	/* uninstaller */
	if ((tmp = wsreg_get_uninstaller(comp)) != NULL) {
		argv[argc++] = "-x";
		argv[argc++] = tmp;
	}

	/* terminate argument array */
	argv[argc++] = NULL;

	/*
	 * Since we must return values following the libwsreg
	 * convention (0 indicates failure, nonzero success),
	 * we must reverse the results returned by prodreg
	 * which follows the Unix command line convention of
	 * 0 indicates success and nonzero means failure.
	 */
	i = _private_exec(argv);
	if (i == 0)
		i = 1;
	else
		i = 0;

	return (i);
}

/*
 * This function invokes /usr/bin/prodreg unregister, using
 * pfexec in order to gain the required authorizations
 * needed to modify the registry.
 *
 * Syntax:
 *
 *   prodreg unregister [-R root] <mnemonic> [<location>]
 *   prodreg unregister --help
 *   prodreg unregister [-R root] [-fr] -u <uuid> [-p <location>]
 *   prodreg unregister [-R root] [-fr] -u <uuid> [-i <instance>]
 *
 */
int
_private_prodreg_unregister(const Wsreg_component *comp)
{
	int		i;
	char		*argv[1024];
	int		argc = 0;
	char		*tmp;
	char		buf[MAXPATHLEN];

	if (access(PRODREG_CLI, X_OK) != 0) {
		/* can't find prodreg */
		return (1);
	}

	/* form arguments to prodreg */
	argv[argc++] = RBAC_CLI;
	argv[argc++] = PRODREG_CLI;
	argv[argc++] = "unregister";
	argv[argc++] = "-u";
	argv[argc++] = wsreg_get_id(comp);

	/* 'f'orce a deregistration */
	argv[argc++] = "-f";

	if (((tmp = wsreg_get_alternate_root()) != NULL) &&
	    (strlen(tmp) > 0)) {
		/* alt root */
		argv[argc++] = "-R";
		argv[argc++] = tmp;
	}

	/* instance */
	(void) snprintf(buf, MAXPATHLEN, "%d", wsreg_get_instance(comp));
	argv[argc++] = "-i";
	argv[argc++] = strdup(buf);

	argv[argc++] = NULL;

	/*
	 * Since we must return values following the libwsreg
	 * convention (0 indicates failure, nonzero success),
	 * we must reverse the results returned by prodreg
	 * which follows the Unix command line convention of
	 * 0 indicates success and nonzero means failure.
	 */
	i = _private_exec(argv);
	if (i == 0)
		i = 1;
	else
		i = 0;

	return (i);
}

/*
 * This routine escapes any special characters characters
 * by prefixing them with the escape character.  A new string
 * is allocated to hold the escaped string.
 */
static char
*_escape(char *str, char *to_escape, char esc)
{
	char *result;
	int c;
	int len;
	int result_len = 0;

	if (str == NULL) {
		return (NULL);
	}

	/* worst case is every single character needs escaping */
	result = wsreg_malloc((strlen(str) * 2) + 1);
	len = strlen(str);
	for (c = 0; c < len; c++) {
		if (strchr(to_escape, str[c]) != NULL) {
			result[result_len++] = esc;
			result[result_len++] = str[c];
		} else {
			result[result_len++] = str[c];
		}
	}

	result[result_len++] = '\0';
	return (result);
}

/*
 * invokes a given array of arguments, waits for the return
 * value
 */
static int
_private_exec(char **argv)
{
	int	realStatus;
	int	status;
	pid_t	pid;
	pid_t	resultPid;

	pid = fork();
	if (pid == 0) {
		/* child */
		(void) execvp(argv[0], argv);
		/* NOTREACHED */
		exit(WSREG_EXEC_FAILED);
	}

	/* Get subprocess exit status */

	for (;;) {
		resultPid = waitpid(pid, &status, 0L);

		/* send interrupt to child process if interrupted */

		if ((resultPid == -1) && (errno == EINTR)) {
			if (kill(pid, SIGTERM) == 0) {
				continue;
			}
		}
		break;
	}

	/* if child process did not exit, kill it and get result */

	if (resultPid == -1) {
		(void) kill(pid, SIGTERM);
		resultPid = waitpid(pid, &status, 0L);
	}

	/* return result from child if exit() called else return -1 */

	realStatus = WIFEXITED(status) ? WEXITSTATUS(status) : -1;

	/* error if wait did not succeed */

	if (resultPid == -1) {
		/* error return from waitpid */
		return (1);
	}

	/* wait succeeded: result pid must be pid being waited for */
	assert(resultPid == pid);

	/* child returning WSREG_EXEC_FAILED == exec failed */
	if ((realStatus & 0xFF) == WSREG_EXEC_FAILED) {
		return (1);
	}

	/* return exit status of private execution */
	return (realStatus & 0xFF);

}

/*
 * Verifies that the function table has been initialized.
 * If not, the function table will be initialized as a
 * result of this call.
 */
static void
verify_function_table()
{
	if (ftable == NULL) {
		int i = 0;
		for (i = 0; initializers[i] != NULL; i++) {
			_Wsreg_function_table* (*initializer)(
				_Wsreg_function_table*);
			initializer =
			    (_Wsreg_function_table* (*)(_Wsreg_function_table*))
			    initializers[i];
			ftable = (*initializer)(ftable);
		}
	}
}

/*
 * Returns the function table being used by the registry.
 */
_Wsreg_function_table *
_wsreg_get_function_table()
{
	return (ftable);
}

/*
 * Sets the function table that will be used by the registry.
 * This enables conversion applications to install one function
 * table to read the components and then install another
 * function table to write the components, thus achieving a
 * conversion.
 */
void
_wsreg_set_function_table(_Wsreg_function_table *newTable)
{
	ftable = newTable;
}

/*
 * The level argument indicates the level of initialization:
 *   WSREG_INIT_NORMAL	- Initialize.  If an old conversion file
 *			  is present, perform the conversion.
 *   WSREG_INIT_NO_CONVERSION - Initialize.  If an old conversion file
 *				is present, do not perform the conversion,
 *				but indicate that conversion is recommended.
 *				The conversion can then be performed with
 *				wsreg_convert_registry.
 */
int
wsreg_initialize(Wsreg_init_level level, const char *alternate_root)
{
	int result = WSREG_SUCCESS;

	if (initialized == WSREG_NOT_INITIALIZED) {
		char *reg_filename = NULL;
		Boolean conversion_recommended = FALSE;
		File_util *futil = NULL;
		initialized = WSREG_INITIALIZING;

		/*
		 * Set up the function table and the alternate root
		 * before checking to see if there is an old
		 * registry to convert.
		 */
		verify_function_table();
		wsreg_set_alternate_root(alternate_root);

		reg_filename = wsreg_get_old_registry_name();
		futil = _wsreg_fileutil_initialize();
		if (futil->exists(reg_filename)) {
			conversion_recommended = TRUE;
		}

		/*
		 * Use the initialization level to determine what
		 * other initialization processing should be completed.
		 */
		switch (level) {
		case WSREG_INIT_NORMAL:
		{
			/*
			 * If conversion from a prior registry
			 * required, perform that now.
			 */
			if (conversion_recommended) {
				if (wsreg_can_convert_registry(reg_filename)) {
					result = wsreg_convert_registry(
						reg_filename, NULL, NULL);
				} else {
					/*
					 * Conversion cannot be performed
					 * because of permissions.
					 */
					result = WSREG_CONVERSION_RECOMMENDED;
				}
			}

			/*
			 * Even if the conversion could not be performed,
			 * we are as initialized as we will get.
			 */
			initialized = WSREG_INIT_NORMAL;
			break;
		}

		case WSREG_INIT_NO_CONVERSION:
			/*
			 * Simply indicate whether a conversion
			 * is recommended (i.e. an old registry
			 * file exists).
			 */
			if (conversion_recommended) {
				result = WSREG_CONVERSION_RECOMMENDED;
			}
			initialized = WSREG_INIT_NO_CONVERSION;
			break;
		}
		free(reg_filename);
	}
	return (result);
}

/*
 * Returns true if the specifed registry file can be converted
 * by the current user; false otherwise.
 */
int
wsreg_can_convert_registry(const char *filename)
{
	int result = FALSE;
	if (initialized == WSREG_NOT_INITIALIZED) {
		return (WSREG_NOT_INITIALIZED);
	}

	if (filename != NULL) {
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * We must be able to read and write the old registry
		 * file AND be able to read and write to the new
		 * registry.
		 */
		if (futil->can_read(filename) && futil->can_write(filename)) {
			if (wsreg_can_access_registry(O_RDWR)) {
				result = TRUE;
			}
		}
	}
	return (result);
}

/*
 * Returns the filename of the old registry file.
 */
char *
wsreg_get_old_registry_name()
{
	char *result = NULL;
	if (initialized == WSREG_NOT_INITIALIZED) {
		return (NULL);
	}
	result = (char *)wsreg_malloc(sizeof (char) * (strlen(OLD_REG_FILE) +
	    strlen(_alternate_root) + 1));
	if (result != NULL) {
		(void) sprintf(result, "%s%s", _alternate_root, OLD_REG_FILE);
	}
	return (result);
}

/*
 * Converts the specified registry file.  The specified file is
 * removed if the conversion is successful.  If conversion_count
 * is not NULL, the total number of Articles converted will be
 * passed back.
 */
int
wsreg_convert_registry(const char *filename, int *conversion_count,
    Progress_function progress_callback)
{
	File_util *futil = _wsreg_fileutil_initialize();

	if (initialized == WSREG_NOT_INITIALIZED) {
		return (WSREG_NOT_INITIALIZED);
	}

	if (!futil->exists(filename)) {
		/*
		 * Bad filename.
		 */
		return (WSREG_FILE_NOT_FOUND);
	}
	if (futil->can_read(filename) && futil->can_write(filename)) {
		/*
		 * The registry file can be read and removed.
		 */
		if (wsreg_can_access_registry(O_RDWR)) {
			/*
			 * The conversion permissions are appropriate.
			 * Perform the conversion.
			 */
			int result;
			int article_count = 0;
			Progress *progress =
			    _wsreg_progress_create(
				    (Progress_callback)*progress_callback);
			int count = 0;
			Unz_article_input_stream *ain = NULL;
			Conversion *c = NULL;

			/*
			 * The first progress section represents the
			 * unzipping of the data file.
			 */
			progress->set_section_bounds(progress, 5, 1);
			ain = _wsreg_uzais_open(filename, &result);
			progress->finish_section(progress);
			if (result != WSREG_SUCCESS) {
				/*
				 * The open failed.  Clean up and
				 * return the error code.
				 */
				if (ain != NULL) {
					ain->close(ain);
				}
				progress->free(progress);
				return (result);
			}

			c = _wsreg_conversion_create(progress);

			/*
			 * The second progress section represents
			 * the reading of articles.
			 */
			article_count = ain->get_article_count(ain);
			progress->set_section_bounds(progress, 8,
			    article_count);
			while (ain->has_more_articles(ain)) {
				Article *a = ain->get_next_article(ain);
				if (a != NULL) {
					c->add_article(c, a);
				}
				progress->increment(progress);
			}
			progress->finish_section(progress);
			ain->close(ain);

			/*
			 * The third progress section represents
			 * the conversion and registration of the
			 * resulting components.
			 */
			progress->set_section_bounds(progress, 100,
			    article_count);
			count = c->register_components(c, NULL, FALSE);
			progress->finish_section(progress);

			/*
			 * Pass the count back to the caller.
			 */
			if (conversion_count != NULL) {
				*conversion_count = count;
			}

			/*
			 * Remove the old registry file.
			 */
			futil->remove(filename);

			/*
			 * Cleanup objects.
			 */
			c->free(c);
			progress->free(progress);

			return (WSREG_SUCCESS);
		} else {
			/*
			 * No permission to modify the registry.
			 */
			return (WSREG_NO_REG_ACCESS);
		}
	} else {
		/*
		 * No permission to read and delete the specified file.
		 */
		return (WSREG_NO_FILE_ACCESS);
	}
}

/*
 * Returns true if the registry can be read and modified
 * by the current user; false otherwise.
 */
int
wsreg_is_available()
{
	if (initialized == WSREG_NOT_INITIALIZED) {
		/*
		 * This function is called from older clients
		 * that do not know about the new wsreg_initialize
		 * function.  This is the first registry call they
		 * make (other than wsreg_set_alternate_root, which
		 * must be done before initialization.
		 * If the registry is not initialized at this point
		 * try to initialize it now.
		 */
		if (wsreg_initialize(WSREG_INIT_NORMAL,
		    wsreg_get_alternate_root()) != WSREG_SUCCESS) {
			return (FALSE);
		}
	}
	verify_function_table();
	return ((*ftable->is_available)());
}

/*
 * This interface is needed in addition to wsreg_can_access_registry
 * since prodreg has to be able to to determine whether it has access
 * to the product registry without reentering via pfexec.  wsreg_can_access
 * registry checks to see if one can do that for root.  But for prodreg
 * running as a normal user, without having been pfexec'ed, this is not
 * appropriate.
 */
int
_private_wsreg_can_access_registry(int access_flag)
{

	if (initialized == WSREG_NOT_INITIALIZED) {
		return (WSREG_NOT_INITIALIZED);
	}
	if (ftable->can_access_registry(access_flag) == 1)
		return (1);
	return (0);
}

/*
 * Returns true if the current user has the specified access
 * to the registry.  Legal values for access_flag are:
 * O_RDONLY and O_RDWR.
 */
int
wsreg_can_access_registry(int access_flag)
{
	char *altroot;

	if (initialized == WSREG_NOT_INITIALIZED) {
		return (WSREG_NOT_INITIALIZED);
	}
	if (ftable->can_access_registry(access_flag) == 1)
		return (1);

	/* see if the user has been granted the appropriate RBAC role */
	if (access_flag == O_RDWR) {
		altroot = wsreg_get_alternate_root();
		if (altroot == NULL || altroot[0] == '\0')
			altroot = "/";

		if (strcmp(altroot, "/") == 0) {
			if (!_write_auth_granted()) {
				return (0);
			} else {
				return (1);
			}
		}
	}

	return (0);
}

/*
 * Returns the alternate root.
 */
char *
wsreg_get_alternate_root()
{
	if (initialized == WSREG_NOT_INITIALIZED) {
		return (NULL);
	}
	if (_alternate_root == NULL) {
		wsreg_set_alternate_root(NULL);
	}
	return (_alternate_root);
}

/*
 * Sets the alternate root to the specified
 * path prefix.
 */
void
wsreg_set_alternate_root(const char *alternate_root)
{
	String_util *sutil = _wsreg_strutil_initialize();
	verify_function_table();
	(*ftable->set_alternate_root)(alternate_root);

	/*
	 * Set the alternate root for this library.
	 */
	if (_alternate_root != NULL) {
		free(_alternate_root);
		_alternate_root = NULL;
	}
	if (alternate_root != NULL && alternate_root[0] == '/') {
		int len;
		_alternate_root = sutil->clone(alternate_root);

		/*
		 * Remove the trailing '/'.
		 */
		len = strlen(_alternate_root);
		if (_alternate_root[len - 1] == '/') {
			_alternate_root[len - 1] = '\0';
		}
	} else {
		_alternate_root = sutil->clone("");
	}
}

/*
 * Creates a new registry component with the specified
 * id.
 */
Wsreg_component *
wsreg_create_component(const char *compID)
{
	verify_function_table();
	return ((*ftable->create_component)(compID));
}

/*
 * Frees the specified component.
 */
void
wsreg_free_component(Wsreg_component *comp)
{
	verify_function_table();
	(*ftable->free_component)(comp);
}

/*
 * Sets the specified id into the specified component.
 */
int
wsreg_set_id(Wsreg_component *comp, const char *compID)
{
	verify_function_table();
	return ((*ftable->set_id)(comp, compID));
}

/*
 * Returns the id from the specified component.  The
 * resulting component id must not be freed by the
 * caller.
 */
char *
wsreg_get_id(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_id)(comp));
}

/*
 * Sets the specified instance into the specified
 * component.
 */
int
wsreg_set_instance(Wsreg_component *comp, int instance)
{
	verify_function_table();
	return ((*ftable->set_instance)(comp, instance));
}

/*
 * Returns the instance from the specified component.
 */
int
wsreg_get_instance(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_instance)(comp));
}

/*
 * Sets the specified version into the specified component.
 */
int
wsreg_set_version(Wsreg_component *comp, const char *version)
{
	verify_function_table();
	return ((*ftable->set_version)(comp, version));
}

/*
 * Returns the version from the specified component.  The
 * resulting version should not be freed by the caller.
 */
char *
wsreg_get_version(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_version)(comp));
}

/*
 * Sets the specified unique name into the specified component.
 */
int
wsreg_set_unique_name(Wsreg_component *comp, const char *unique_name)
{
	verify_function_table();
	return ((*ftable->set_unique_name)(comp, unique_name));
}

/*
 * Returns the unique name from the specified component.  The
 * resulting unique name must not be freed by the caller.
 */
char *
wsreg_get_unique_name(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_unique_name)(comp));
}

/*
 * Adds the specified display name to the specified component.
 */
int
wsreg_add_display_name(Wsreg_component *comp, const char *language,
    const char *display_name)
{
	verify_function_table();
	return ((*ftable->add_display_name)(comp, language, display_name));
}

/*
 * Removes the specified display name from the specified component.
 */
int
wsreg_remove_display_name(Wsreg_component *comp, const char *language)
{
	verify_function_table();
	return ((*ftable->remove_display_name)(comp, language));
}

/*
 * Returns the display name associated with the specified
 * language from the specified component.  The resulting
 * display name must not be freed by the caller.
 */
char *
wsreg_get_display_name(const Wsreg_component *comp, const char *language)
{
	verify_function_table();
	return ((*ftable->get_display_name)(comp, language));
}

/*
 * Returns a NULL-terminated array of display languages from the
 * specified component.  The array should be freed by the caller,
 * but the contents of the array should not.
 */
char **
wsreg_get_display_languages(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_display_languages)(comp));
}

/*
 * Sets the component type of the specified component.
 */
int
wsreg_set_type(Wsreg_component *comp, Wsreg_component_type type)
{
	verify_function_table();
	return ((*ftable->set_type)(comp, type));
}

/*
 * Returns the component type of the specified component.
 */
Wsreg_component_type
wsreg_get_type(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_type)(comp));
}

/*
 * Sets the specified location into the specified component.
 */
int
wsreg_set_location(Wsreg_component *comp, const char *location)
{
	verify_function_table();
	return ((*ftable->set_location)(comp, location));
}

/*
 * Returns the location from the specified location.  The
 * resulting location should not be freed by the caller.
 */
char *
wsreg_get_location(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_location)(comp));
}

/*
 * Sets the specified uninstaller into the specified component.
 */
int
wsreg_set_uninstaller(Wsreg_component *comp, const char *uninstaller)
{
	verify_function_table();
	return ((*ftable->set_uninstaller)(comp, uninstaller));
}

/*
 * Returns the uninstaller from the specified component.
 * The resulting uninstaller should not be freed by the
 * caller.
 */
char *
wsreg_get_uninstaller(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_uninstaller)(comp));
}

/*
 * Sets the specified vendor into the specified component.
 */
int
wsreg_set_vendor(Wsreg_component *comp, const char *vendor)
{
	verify_function_table();
	return ((*ftable->set_vendor)(comp, vendor));
}

/*
 * Returns the vendor from the specified component.  The
 * resulting vendor should not be freed by the caller.
 */
char *
wsreg_get_vendor(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_vendor)(comp));
}

/*
 * Returns true if the specified components are equal;
 * false otherwise.
 */
int
wsreg_components_equal(const Wsreg_component *comp1,
    const Wsreg_component *comp2)
{
	verify_function_table();
	return ((*ftable->components_equal)(comp1, comp2));
}

/*
 * Returns a clone of the specified component.  It is
 * the responsibility of the caller to free the resulting
 * component.
 */
Wsreg_component *
wsreg_clone_component(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->clone_component)(comp));
}

/*
 * Adds the specified required component to the specified
 * component.
 */
int
wsreg_add_required_component(Wsreg_component *comp,
    const Wsreg_component *requiredComp)
{
	verify_function_table();
	return ((*ftable->add_required_component)(comp, requiredComp));
}

/*
 * Removes the specified required component from the
 * specified component.
 */
int
wsreg_remove_required_component(Wsreg_component *comp,
    const Wsreg_component *requiredComp)
{
	verify_function_table();
	return ((*ftable->remove_required_component)(comp, requiredComp));
}

/*
 * Returns a NULL-terminated array of required components from
 * the specified component.  It is the responsibility of the
 * caller to free the resulting array and its contents.
 */
Wsreg_component **
wsreg_get_required_components(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_required_components)(comp));
}

/*
 * Adds the specified dependent component to the specified
 * component
 */
int
wsreg_add_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp)
{
	verify_function_table();
	return ((*ftable->add_dependent_component)(comp, dependentComp));
}

/*
 * Removes the specified dependent component from the
 * specified component.
 */
int
wsreg_remove_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp)
{
	verify_function_table();
	return ((*ftable->remove_dependent_component)(comp, dependentComp));
}

/*
 * Returns a NULL-terminated array of dependent components
 * from the specified component.  It is the responsibility
 * of the caller to free the resulting array and its
 * contents.
 */
Wsreg_component **
wsreg_get_dependent_components(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_dependent_components)(comp));
}

/*
 * Adds the specified child component to the specified
 * component.
 */
int
wsreg_add_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp)
{
	verify_function_table();
	return ((*ftable->add_child_component)(comp, childComp));
}

/*
 * Removes the specified child component from the
 * specified component
 */
int
wsreg_remove_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp)
{
	verify_function_table();
	return ((*ftable->remove_child_component)(comp, childComp));
}

/*
 * Returns a NULL-terminated array of child components from
 * the specified component.  It is the responsibility of the
 * caller to free the resulting array and its contents.
 */
Wsreg_component **
wsreg_get_child_components(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_child_components)(comp));
}

/*
 * Returns the specified version to the list of versions
 * the specified component is backward compatible with.
 */
int
wsreg_add_compatible_version(Wsreg_component *comp, const char *version)
{
	verify_function_table();
	return ((*ftable->add_compatible_version)(comp, version));
}

/*
 * Removes the specified version from the list of versions
 * the specified component is backward compatible with.
 */
int
wsreg_remove_compatible_version(Wsreg_component *comp, const char *version)
{
	verify_function_table();
	return ((*ftable->remove_compatible_version)(comp, version));
}

/*
 * Returns a NULL-terminated array of versions the
 * specified component is backward compatible with.
 */
char **
wsreg_get_compatible_versions(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_compatible_versions)(comp));
}

/*
 * Returns the parent of the specified component.  The
 * resulting component should be freed by the caller.
 */
Wsreg_component *
wsreg_get_parent(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_parent)(comp));
}

/*
 * Sets the specified parent into the specified component.
 */
void
wsreg_set_parent(Wsreg_component *comp,
    const Wsreg_component *parent)
{
	verify_function_table();
	(*ftable->set_parent)(comp, parent);
}

/*
 * Returns the value associated with the specified key in
 * the specified component.  The resulting value should
 * not be freed by the caller.
 */
char *
wsreg_get_data(const Wsreg_component *comp, const char *key)
{
	verify_function_table();
	return ((*ftable->get_data)(comp, key));
}

/*
 * Sets the specified key/value pair into the specified
 * component.
 */
int
wsreg_set_data(Wsreg_component *comp, const char *key, const char *value)
{
	verify_function_table();
	return ((*ftable->set_data)(comp, key, value));
}

/*
 * Returns a NULL-terminated array of key/value pairs
 * from the specified component.
 *
 * The even indexes of the resulting array represent the keys;
 * the odd indexes represent the values.
 *
 * It is the responsibility of the caller to free the resulting
 * array, but not the contents of that array.
 */
char **
wsreg_get_data_pairs(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_data_pairs)(comp));
}

/*
 * Returns the component from the registry that best conforms
 * to the specified query.  It is the responsibility of the
 * caller to free the resulting component.
 */
Wsreg_component *
wsreg_get(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->get)(query));
}

/*
 * Registers the specified component.  This function sets
 * up component relationships complimentary to required
 * components and child components automatically.
 */
int
_private_wsreg_register(Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->register_)(comp));
}

/*
 * Registers the specified component.  This function first
 * checks that the invoking user has been granted the
 * appropriate RBAC Rights Profile to register.
 */
int
wsreg_register(Wsreg_component *comp)
{

	char *altroot = wsreg_get_alternate_root();
	if (altroot == NULL || altroot[0] == '\0')
		altroot = "/";

	if ((strcmp(altroot, "/") != 0 &&
	    wsreg_can_access_registry(O_RDWR)) ||
	    (strcmp(altroot, "/") == 0 && getuid() == 0)) {
		return (_private_wsreg_register(comp));
	}

	/* see if the user has been granted the appropriate RBAC role */
	if (strcmp(altroot, "/") == 0) {
		if (!_write_auth_granted()) {
			return (0);
		}
	}

	return (_private_prodreg_register(comp));
}

/*
 * Unregisters the specified component.  This function first
 * checks that the invoking user has been granted the
 * appropriate RBAC Rights Profile to unregister.
 */
int
wsreg_unregister(const Wsreg_component *comp)
{

	char *altroot = wsreg_get_alternate_root();
	if (altroot == NULL || altroot[0] == '\0')
		altroot = "/";

	if ((strcmp(altroot, "/") != 0 &&
	    wsreg_can_access_registry(O_RDWR)) ||
	    (strcmp(altroot, "/") == 0 && getuid() == 0)) {

		return (_private_wsreg_unregister(comp));
	}


	/* see if the user has been granted the appropriate RBAC role */
	if (strcmp(altroot, "/") == 0) {
		if (!_write_auth_granted()) {
			return (0);
		}
	}

	return (_private_prodreg_unregister(comp));
}

/*
 * Unregisters the specified component.
 */
int
_private_wsreg_unregister(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->unregister)(comp));
}

/*
 * Returns a sparse component representing the parent of the
 * specified component.  This call does not completely fill out
 * the component structure because it does no registry access
 */
Wsreg_component *
wsreg_get_parent_reference(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_parent_reference)(comp));
}

/*
 * Returns an array of sparse components representing the children
 * of the specified component.  This call does not completely fill
 * out the component structure because it does no registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
Wsreg_component **
wsreg_get_child_references(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_child_references)(comp));
}

/*
 * Returns an array of sparse components representing the components
 * that the specified component requires.  This call does not
 * completely fill out the component structure because it does no
 * registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
Wsreg_component **
wsreg_get_required_references(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_required_references)(comp));
}

/*
 * Returns an array of sparse components representing the components
 * that require the specified component.  This call does not
 * completely fill out the component structure because it does no
 * registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
Wsreg_component **
wsreg_get_dependent_references(const Wsreg_component *comp)
{
	verify_function_table();
	return ((*ftable->get_dependent_references)(comp));
}

/*
 * Returns a component array representing all components currently
 * registered.  The array and all components in the array must
 * be freed by the caller.
 */
Wsreg_component **
wsreg_get_all(void)
{
	verify_function_table();
	return ((*ftable->get_all)());
}

/*
 * Returns a component array representing all clusters and packages
 * installed on the sysetm that are not registered.  The resulting
 * array must be freed by the caller.  The specified progress callback
 * will be called to report the progress of this function.  If no
 * progress callback is specified, progress reporting will be
 * disabled.
 */
Wsreg_component **
wsreg_get_sys_pkgs(Progress_function progress_callback)
{
	verify_function_table();
	return ((*ftable->get_sys_pkgs)(progress_callback));
}

/*
 * Returns a component array representing all components currently
 * registered, and all packages referenced by the registered
 * components.
 */
Wsreg_component **
wsreg_get_xall(void)
{
	verify_function_table();
	return ((*ftable->get_xall)());
}

/*
 * This function sets the application data
 * "isDamaged" to "TRUE" for all components that
 * represent Solaris packages that are not currently
 * installed on the system.
 */
void
wsreg_flag_broken_components(Wsreg_component **comps)
{
	verify_function_table();
	ftable->flag_broken_components(comps);
}

/*
 * Frees the specified component array.  The specified array
 * must be NULL-terminated.  All components in the array are
 * also freed as a result of this call.
 */
int
wsreg_free_component_array(Wsreg_component **complist)
{
	verify_function_table();
	return ((*ftable->free_component_array)(complist));
}

/*
 * Creates and returns a new query structure.
 */
Wsreg_query *
wsreg_query_create()
{
	verify_function_table();
	return ((*ftable->query_create)());
}

/*
 * Frees the specified query.
 */
void
wsreg_query_free(Wsreg_query *query)
{
	verify_function_table();
	(*ftable->query_free)(query);
}

/*
 * Sets the specified id into the specified query.
 */
int
wsreg_query_set_id(Wsreg_query *query, const char *compID)
{
	verify_function_table();
	return ((*ftable->query_set_id)(query, compID));
}

/*
 * Returns the id from the specified query.  The resulting
 * id is not a clone, so the caller should not free it.
 */
char *
wsreg_query_get_id(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->query_get_id)(query));
}

/*
 * Sets the specified unique name into the specified query.
 */
int
wsreg_query_set_unique_name(Wsreg_query *query, const char *unique_name)
{
	verify_function_table();
	return ((*ftable->query_set_unique_name)(query, unique_name));
}

/*
 * Returns the unique name from the specified query.  The
 * resulting unique name is not a clone, so the caller should
 * not free it.
 */
char *
wsreg_query_get_unique_name(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->query_get_unique_name)(query));
}

/*
 * Sets the specified version into the specified query.
 */
int
wsreg_query_set_version(Wsreg_query *query, const char *version)
{
	verify_function_table();
	return ((*ftable->query_set_version)(query, version));
}

/*
 * Returns the version from the specified query. The resulting
 * version is not a clone, so the caller should not free it.
 */
char *
wsreg_query_get_version(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->query_get_version)(query));
}

/*
 * Sets the specified instance into the specified query.
 */
int
wsreg_query_set_instance(Wsreg_query *query, int instance)
{
	verify_function_table();
	return ((*ftable->query_set_instance)(query, instance));
}

/*
 * Returns the instance from the specified query.
 */
int
wsreg_query_get_instance(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->query_get_instance)(query));
}

/*
 * Sets the specified location into the specified query.
 */
int
wsreg_query_set_location(Wsreg_query *query, const char *location)
{
	verify_function_table();
	return ((*ftable->query_set_location)(query, location));
}

/*
 * Returns the location from the specified query.  The location
 * is not a clone, so the caller should not free it.
 */
char *
wsreg_query_get_location(const Wsreg_query *query)
{
	verify_function_table();
	return ((*ftable->query_get_location)(query));
}

/*
 * Diagnostic function that prints logging messages.
 */
/*ARGSUSED*/
void
diag(const char *format, int cnt, ...)
{
	static int printDiags = 0;
	static int init = 0;

	if (!init) {
		char *str = getenv("DEBUG_REGISTRY");
		if (str != NULL) {
			printDiags = 1;
		}
		init = 1;
	}

	if (printDiags) {
		va_list ap;
		va_start(ap, cnt);
		(void) vprintf(format, ap);
	}
}

/*
 * This function allocates memory of the specified size.  If the
 * specified amount of memory cannot be allocated, a message is
 * printed and the application will exit.
 */
void *
wsreg_malloc(size_t size)
{
	void *result = malloc(size);
	if (result == NULL) {
		(void) fprintf(stderr, WSREG_OUT_OF_MEMORY);
		exit(WSREG_EXIT_NOT_ENOUGH_MEMORY);
	}
	return (result);
}
