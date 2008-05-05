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
 * Copyright 2006 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include <dirent.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pkgstrct.h>
#include "pkg_db_io.h"
#include "wsreg.h"
#include "string_util.h"

/*
 * Private Function Prototypes
 */
static int pdio_load_pkg_info(char *, Wsreg_component *);
static int pdio_read_pkginfo(char *, Wsreg_component *);
static int pdio_read_depend(char *, Wsreg_component *);
static short pdio_isFile(char *);
static short pdio_isPkg(char *);
static void pdio_add_pkginfo_to_comp(char *, char *, Wsreg_component *);

/*
 * Static data.
 */
#define	MAX_PATH_LENGTH 1024

#define	PKG_DATABASE_DIR "/var/sadm/pkg"
#define	PKGINFO_FILE	"pkginfo"
#define	DEPEND_FILE	"install/depend"
#define	PREREQUISITE	'P'
#define	INCOMPATIBLE	'I'
#define	REVERSE		'R'

typedef enum { KEY = 0, VALUE } _Ws_keyvalue_type;
typedef enum { TYPE = 0, ABBR, NAME } _Ws_depend_field;
typedef enum { INCOMPLETE = 0, COMPLETE } _Ws_field_complete_flag;

Pkg_db_io *pkg_db_io = NULL;


/*
 * Reads a single packages' pkginfo and depend data and returns a
 * component structure
 */
static Wsreg_component *
get_pkg_data(char *package)
{
	char pkg[MAX_PATH_LENGTH];
	Wsreg_component *comp = NULL;
	char *alternate_root = wsreg_get_alternate_root();

	sprintf(pkg, "%s%s/%s", alternate_root, PKG_DATABASE_DIR, package);
	if (! pdio_isPkg(pkg)) {
		return (NULL);
	}

	comp = wsreg_create_component(NULL);
	(void) pdio_load_pkg_info(pkg, comp);

	return (comp);
}

/*
 * Reads the pkg directory inode and iterates through the pkg directory
 * names, their pkginfo KEY = VALUE data, and depend package dependencies.
 * Reading a directory's inode is the most efficient and reliable method of
 * iterating through a directory in C. See struct dirent in <sys/dirent.h>.
 */
static int
get_all_pkg_data(Hashtable *pkg_table, Progress *progress)
{
	char pkg[MAX_PATH_LENGTH];
	char pkgdir[MAX_PATH_LENGTH];
	dirent_t *dp;
	DIR *dfd;
	Wsreg_component *comp = NULL;
	char *alternate_root = wsreg_get_alternate_root();
	List *file_list = _wsreg_list_create();
	String_util *sutil = _wsreg_strutil_initialize();

	sprintf(pkgdir, "%s%s", alternate_root, PKG_DATABASE_DIR);
	if ((dfd = opendir(pkgdir)) == NULL) {
		return (1);
	}

	while ((dp = readdir(dfd)) != NULL) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0) {
			/* skip self and parent */
			continue;
		}
		file_list->add_element(file_list, sutil->clone(dp->d_name));
	}
	closedir(dfd);

	progress->set_item_count(progress, file_list->size(file_list));

	/*
	 * For each package, create a component and add it to the
	 * pkg_table.
	 */
	file_list->reset_iterator(file_list);
	while (file_list->has_more_elements(file_list)) {
		char *d_name = (char *)file_list->next_element(file_list);
		sprintf(pkg, "%s%s/%s", alternate_root, pkgdir, d_name);
		if (! pdio_isPkg(pkg)) {
			continue;   /* directory is not a Solaris package */
		}

		comp = wsreg_create_component(NULL);
		(void) pdio_load_pkg_info(pkg, comp);

		/*
		 * Add the component to the hashtable.
		 */
		pkg_table->put(pkg_table, d_name, comp);
		comp = NULL;
		progress->increment(progress);
	}
	file_list->free(file_list, free);
	progress->finish_section(progress);
	return (0);
}

/*
 * Reads the pkg directory inode and iterates through the pkg directory names
 * names their pkginfo KEY = VALUE data, and depend's package dependencies.
 * Reading a directory's inode is the most efficient and reliable method of
 * reading a directory. See struct dirent in <sys/dirent.h > .
 */
static int
pdio_load_pkg_info(char *pkg, Wsreg_component *comp)
{
	(void) pdio_read_pkginfo(pkg, comp);  /* get pkginfo data */
	(void) pdio_read_depend(pkg, comp);   /* get depend data */
	return (0);
}

/*
 * Read through pkginfo file KEY = VALUE pairs passing their
 * values to pdio_add_pkginfo_to_comp().
 */
static int
pdio_read_pkginfo(char *pkg, Wsreg_component *comp)
{
	FILE *pkginfo_fp = NULL;
	char key[ATRSIZ];
	char *value = NULL;
	char buf[MAX_PATH_LENGTH];

	/* Construct the file path and open the pkginfo file */
	(void) snprintf(buf, MAX_PATH_LENGTH, "%s/%s", pkg, PKGINFO_FILE);

	*key = '\0';

	if ((pkginfo_fp = fopen(buf, "r")) != NULL) {
		while ((value = fpkgparam(pkginfo_fp, key)) != NULL) {
			pdio_add_pkginfo_to_comp(key, value, comp);
			*key = '\0';
			free(value);
		}
	} else {
		return (1);
	}

	wsreg_set_instance(comp, 1);

	(void) fclose(pkginfo_fp);

	return (0);
}

/*
 * Adds the specified key/value pair to the specified component.
 * Certain key names are set into the component in other ways:
 *   "PKG" - id and unique name
 *   "VERSION" - version
 *   "VENDOR" - vendor
 *   "NAME" - display name
 */
static void
pdio_add_pkginfo_to_comp(char *key, char *value, Wsreg_component *comp)
{
	/* All keys must be inspected for specific GUI display data. All */
	/* pairs are added to app_data whether used for display or not.  */

	wsreg_set_data(comp, key, value);

	if (strcmp(key, "PKG") == 0) {
		wsreg_set_id(comp, value);
		wsreg_set_unique_name(comp, value);

		/*
		 * Set the package name into the app data.  This key/value
		 * pair is used by the registry viewer to present an
		 * uninstall button.
		 */
		wsreg_set_data(comp, "pkgs", value);
	} else if (strcmp(key, "VERSION") == 0) {
		wsreg_set_version(comp, strtok(value, ", "));

	} else if (strcmp(key, "VENDOR") == 0) {
		wsreg_set_vendor(comp, value);

	} else if (strcmp(key, "NAME") == 0) {
		wsreg_add_display_name(comp, "en", value);
	} else if (strcmp(key, "BASEDIR") == 0) {
		wsreg_set_location(comp, value);
	}
}

/*
 * Reads the depend file for the specified package (if any)
 * and adds the required components to the specified
 * component.
 */
static int
pdio_read_depend(char *pkg, Wsreg_component *comp)
{
	char buf[BUFSIZ+1];
	char abbr[BUFSIZ+1];
	char file[MAX_PATH_LENGTH];
	int readfd = -1, n_read = -1;
	int abbr_count = 0;
	short next_line = FALSE;
	short whitespace = FALSE;
	char *depend = NULL;
	register int i;
	_Ws_depend_field dep_flag = TYPE;   /* (enum) KEY or VALUE */

	/*
	 * Construct the file path and open the depend file. If package
	 * won't have a depend file it has no dependencies.
	 */
	sprintf(file, "%s/%s", pkg, DEPEND_FILE);
	if ((readfd = open(file, O_RDONLY, 0)) == -1) {
		return (-1);   /* The open failed */
	}

	/*
	 * Read through the depend file to get the package dependencies for
	 * a package. The 3 fields needed are TYPE, ABBR, and NAME. See the
	 * depend(4) man page for format, etc. Since BUFSIZ (1024 on Solar-
	 * is BUFSIZ (1024 on Solaris), only one efficient read is required.
	 */
	while ((n_read = read(readfd, buf, BUFSIZ)) > 0) {
		for (i = 0; i < n_read; i++) {
			switch (dep_flag) {
			case TYPE:
				/* Read buf 1 character at a time and look  */
				/* for a 'P' (dependency) in the first char */
				/* of every line. */
				if (buf[i] == PREREQUISITE && !next_line) {
					whitespace = TRUE;
					/* Remove 1 space after the TYPE. */
				} else if (whitespace) {
					whitespace = FALSE;
					dep_flag = ABBR;
				} else {
					/* Move to the beg of the next line */
					/* when we don't have a dependency. */
					if (buf[i] == '\n') {
						next_line = FALSE;
					} else {
						next_line = TRUE;
					}
				}
				break;
			case ABBR:
				if (buf[i] != '\t' && buf[i] != ' ') {
					/* Append char to ABBR field */
					abbr[abbr_count++] = buf[i];
				} else {
					abbr[abbr_count] = '\0';
					dep_flag = NAME;
					abbr_count = 0;
				}
				break;
			case NAME:
				/* ABBR field is complete skip to the  */
				/* beginning of next line after adding */
				/* the dependency to app_data. */
				next_line = TRUE;
				dep_flag = TYPE;
				depend = wsreg_get_data(comp, "PREREQUISITE");
				if (depend == NULL) {
					/* No dependencies have been */
					/* into the component yet.   */
					wsreg_set_data(comp, "PREREQUISITE",
					    abbr);
				} else {
					/* Create a comma-separated list */
					/* of dependencies. */
					int len = strlen(depend) +
					    strlen(abbr) + 1;
					char *tmp_buf = (char *)
					    wsreg_malloc(sizeof (char) *
						len + 1);
					sprintf(tmp_buf, "%s,%s", depend,
					    abbr);
					wsreg_set_data(comp, "PREREQUISITE",
					    tmp_buf);
					free(tmp_buf);
				}
				break;
			}
		}
	}

	(void) close(readfd);
	return (0);
}

/*
 * isPkg returns 1, non-zero (TRUE) if the file is a Solaris package, and 0
 * if it is not.
 */
static short
pdio_isPkg(char *pkg)
{
	char file[MAX_PATH_LENGTH];

	sprintf(file, "%s/%s", pkg, PKGINFO_FILE);
	if (! pdio_isFile(file)) {
		return (0);   /* doesn't have a pkginfo file, so not a pkg */
	} else {
		return (1);   /* file is a Solaris package */
	}
}

/*
 * isFile returns 1, non-zero (TRUE) if the file is a directory, and 0
 * if the file can't be opened or is a directory.
 */
static short
pdio_isFile(char *name)
{
	struct stat stbuf;    /* file inode and name information */

	if (stat(name, &stbuf) == -1) {
		return (0);    /* can't access file */
	}
	if ((stbuf.st_mode & S_IFMT) != S_IFDIR) {
		return (1);    /* file is a file other than a directory */
	} else {
		return (0);    /* file is a directory */
	}
}


/*
 * Initializes the Pkg_db_io object.  Since there are no non-static
 * methods and no object-private data, there is no need to ever
 * create more than one Pkg_db_io object.  There is no free method
 * for this object.
 */
Pkg_db_io *
_wsreg_pkgdbio_initialize()
{
	Pkg_db_io *pkgdb = pkg_db_io;
	if (pkgdb == NULL) {
		pkgdb = (Pkg_db_io *)wsreg_malloc(sizeof (Pkg_db_io));
		pkgdb->get_pkg_data = get_pkg_data;
		pkgdb->get_all_pkg_data = get_all_pkg_data;
		pkgdb->load_pkg_info = pdio_load_pkg_info;
		pkg_db_io = pkgdb;
	}
	return (pkgdb);
}
