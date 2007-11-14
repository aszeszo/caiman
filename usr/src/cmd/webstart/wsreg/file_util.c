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

#pragma ident	"@(#)file_util.c	1.11	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/param.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <utime.h>
#include "file_util.h"
#include "string_util.h"
#include "wsreg.h"

/*
 * The File_util object only has static methods.
 * This object is created only once and that
 * single reference is passed to all clients.  There
 * is no free method so the object will not get
 * corrupted inadvertently.
 */
static File_util *file_util = NULL;

/*
 * Returns true if the specified path exists; false otherwise.
 */
static Boolean
futil_exists(const char *path)
{
	Boolean result = FALSE;
	struct stat stat_buffer;
	int stat_result = 0;

	stat_result = stat(path, &stat_buffer);
	if (stat_result == 0) {
		result = TRUE;
	}
	return (result);
}

/*
 * Returns true if the specified path refers to an existing
 * file, false otherwise.
 */
static Boolean
futil_is_file(const char *path)
{
	Boolean result = FALSE;
	struct stat stat_buffer;
	int stat_result = 0;

	stat_result = stat(path, &stat_buffer);
	if (stat_result == 0) {
		result = (stat_buffer.st_mode & S_IFREG) != 0;
	}
	return (result);
}

/*
 * Returns true if the specified path refers to an existing
 * directory; false otherwise.
 */
static Boolean
futil_is_directory(const char *path)
{
	Boolean result = FALSE;
	struct stat stat_buffer;
	int stat_result = 0;

	stat_result = stat(path, &stat_buffer);
	if (stat_result == 0) {
		result = (stat_buffer.st_mode & S_IFDIR) != 0;
	}
	return (result);
}

/*
 * Returns true if the specified path refers to an existing
 * file and the file permissions are such that the file can
 * be read; false otherwise.
 */
static Boolean
futil_can_read(const char *path)
{
	struct stat statStruct;
	int result = stat(path, &statStruct);
	int file = -1;

	/*
	 * Try opening the file for reading.
	 */
	if (result != 0) {
		/*
		 * The file does not exist.
		 */
		return (FALSE);
	}
	file = open(path, O_RDONLY);
	if (file == -1) {
		/*
		 * The open failed.
		 */
		return (FALSE);
	}
	close(file);
	return (TRUE);
}

/*
 * Returns true if the specified path refers to an existing
 * file and the file permissions are such that the file can
 * be modified; false otherwise.
 */
static Boolean
futil_can_write(const char *path)
{
	struct stat statStruct;
	int result = stat(path, &statStruct);
	int file = -1;

	/*
	 * Try opening the file for append.
	 */
	file = open(path, O_APPEND | O_CREAT |O_RDWR);
	if (file == -1) {
		/*
		 * The open failed.
		 */
		return (FALSE);
	}

	close(file);
	if (result != 0) {
		/*
		 * The file did not exist before; remove it.
		 */
		unlink(path);
	} else {
		/*
		 * The file did exist before; reset it's
		 * time info.
		 */
		struct utimbuf timeStruct;
		timeStruct.actime = statStruct.st_atime;
		timeStruct.modtime = statStruct.st_mtime;
		utime(path, &timeStruct);
	}

	return (TRUE);
}

/*
 * Returns the length of the file identified by the specified
 * path.
 */
static off_t
futil_length(const char *path)
{
	off_t result = 0;
	struct stat stat_buffer;
	int stat_result = 0;

	stat_result = stat(path, &stat_buffer);
	if (stat_result == 0) {
		result = stat_buffer.st_size;
	}
	return (result);
}

/*
 * Returns the name of the file from the specified path.
 */
static char *
futil_get_name(const char *path)
{
	char *result = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	int index = sutil->last_index_of(path, '/');

	/*
	 * Always return a valid filename if possible.
	 */
	if (index == -1) {
		index = 0;
	}
	result = sutil->clone(path + index);
	return (result);
}

/*
 * Returns  the parent directory of the specified path.
 */
static char *
futil_get_parent(const char *path)
{
	char *result = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	int index;
	result = sutil->clone(path);
	index = sutil->last_index_of(result, '/');

	if (index != -1) {
		result[index] = '\0';
	}
	return (result);
}

#if 0
/*
 * Returns a list of files and directories contained in
 * the specified path.  Each element in the list is a
 * string representing the file or directory name.
 */
static List *
futil_list(const char *path)
{
	List *result = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	if (path != NULL &&
	    futil_exists(path)) {
		DIR *dir = opendir(path);
		if (dir != NULL) {
			struct dirent *directory_entry;
			while ((directory_entry = readdir(dir)) != NULL) {
				char *filename =
				    sutil->clone(directory_entry->d_name);
				if (result == NULL) {
					result = _wsreg_list_create();
				}
				/*
				 * Add the filename to the list.
				 */
				result->add_element(result, filename);
			}
			closedir(dir);
		}
	}
	return (result);
}
#endif

/*
 * Creates a list containing all files found in the
 * specified directory.  Each element in the list
 * contains the full path to the file.
 */
static List *
futil_list_files(const char *path)
{
	List *result = NULL;
	if (futil_exists(path) &&
	    futil_is_directory(path)) {
		DIR *dir = opendir(path);
		if (dir != NULL) {
			struct dirent *directory_entry;
			while ((directory_entry = readdir(dir)) != NULL) {
				char *filename = (char *)
				    wsreg_malloc(sizeof (char) * (strlen(path) +
					strlen(directory_entry->d_name) + 2));
				(void) sprintf(filename, "%s/%s",
				    path, directory_entry->d_name);
				if (futil_exists(filename) &&
				    futil_is_file(filename)) {
					if (result == NULL) {
						result = _wsreg_list_create();
					}
					/*
					 * Add the filename to the list.
					 */
					result->add_element(result, filename);
				} else {
					/*
					 * The filename does not exist or is
					 * not a filename.  Do not add it to
					 * the list.
					 */
					free(filename);
				}
			}
			closedir(dir);
		}
	}
	return (result);
}

#if 0
/*
 * Creates a list containing all directories found in the
 * specified directory.  Each element in the list is a
 * string that contains the full path to the directory.
 */
static List *
futil_list_dirs(const char *path)
{
	List *result = NULL;
	if (futil_exists(path) &&
	    futil_is_directory(path)) {
		DIR *dir = opendir(path);
		if (dir != NULL) {
			struct dirent *directory_entry;
			while ((directory_entry = readdir(dir)) != NULL) {
				char *filename = (char *)
				    wsreg_malloc(sizeof (char) * (strlen(path) +
					strlen(directory_entry->d_name) + 2));
				(void) sprintf(filename, "%s/%s",
				    path, directory_entry->d_name);
				if (futil_exists(filename) &&
				    futil_is_directory(filename)) {
					if (result == NULL) {
						result = _wsreg_list_create();
					}
					/*
					 * Add the filename to the list.
					 */
					result->add_element(result, filename);
				} else {
					/*
					 * The filename does not exist or is
					 * not a filename.  Do not add it to
					 * the list.
					 */
					free(filename);
				}
			}
			closedir(dir);
		}
	}
	return (result);
}
#endif

/*
 * Deletes the file or directory identified by the specified
 * path.
 */
static void
futil_remove(const char *path)
{
	if (futil_exists(path)) {
		if (futil_is_file(path)) {
			unlink(path);
		} else if (futil_is_directory(path)) {
			rmdir(path);
		}
	}
}

/*
 * Returns a temporary name that can be used to create either
 * a file or directory.
 */
static char *
futil_get_temp_name(void)
{
	char *result = tempnam(NULL, NULL);
	return (result);
}

/*
 * Returns the current directory.
 */
static char *
get_current_directory()
{
	static size_t buffer_size = MAXPATHLEN;
	static char *dir_buffer = NULL;
	Boolean can_continue = TRUE;
	String_util *sutil = _wsreg_strutil_initialize();

	if (dir_buffer == NULL) {
		/*
		 * Initialize the buffer.
		 */
		dir_buffer = (char *)wsreg_malloc(sizeof (char) *
		    (buffer_size + 1));
	}

	errno = 0;
	while (can_continue && !getcwd(dir_buffer, buffer_size)) {
		if (errno == ERANGE) {
			/*
			 * The buffer is not large enough.  Make it bigger.
			 */
			buffer_size *= 2;
			dir_buffer = (char *)realloc(dir_buffer,
			    sizeof (char) * (buffer_size + 1));
			errno = 0;
		} else {
			can_continue = FALSE;
		}
	}
	if (can_continue) {
		/*
		 * No unrecoverable error was encountered.
		 */
		return (sutil->clone(dir_buffer));
	} else {
		/*
		 * An error was encountered that we did not recover
		 * from.
		 */
		return (NULL);
	}
}

/*
 * Returns true if the specified path is a link; false otherwise.
 */
static Boolean
futil_is_link(const char *path)
{
	Boolean result = FALSE;
	if (path != NULL) {
		struct stat stat_buffer;
		if (!lstat(path, &stat_buffer)) {
			if ((stat_buffer.st_mode & S_IFLNK) == S_IFLNK) {
				result = TRUE;
			}
		}
	}
	return (result);
}

/*
 * Returns a path equivalent to that specified except that
 * it will contain no links.  If the specified path contains
 * no links, a copy of that path will be returned.
 */
static char *
futil_get_linkless_path(const char *path)
{
	char path_buffer[MAXPATHLEN + 1];
	char *path_copy = NULL;
	Boolean encountered_link = FALSE;
	char *filename;
	String_util *sutil = _wsreg_strutil_initialize();
	path_buffer[0] = '\0';

	path_copy = sutil->clone(path);

	/*
	 * Walk through the specified path looking for
	 * directory separators.  Before each directory
	 * separator, check to see if the path so far
	 * is a link.
	 */
	filename = strtok(path_copy, "/");
	while (filename != NULL) {
		char tmp_path[MAXPATHLEN + 1];
		(void) sprintf(tmp_path, "%s/%s", path_buffer, filename);
		if (futil_is_link(tmp_path)) {
			/*
			 * Found a link.  Resolve the link
			 * and start over (the link may have
			 * links in it.
			 */
			char link_buffer[MAXPATHLEN + 1];
			int link_result;

			encountered_link = TRUE;
			link_result = readlink(tmp_path, link_buffer,
			    MAXPATHLEN);
			if (link_result != -1) {
				/*
				 * Null-terminate the resulting path.
				 */
				link_buffer[link_result] = '\0';

				if (link_buffer[0] == '/') {
					/*
					 * This is an absolute path.
					 * Replace the current path
					 * (stored in path_buffer)
					 * with the link's target.
					 */
					strcpy(path_buffer, link_buffer);
				} else {
					/*
					 * This is a relative path.
					 * Append the link_buffer
					 * to the current path.
					 */
					(void) sprintf(path_buffer, "%s/%s",
					    path_buffer, link_buffer);
				}

			} else {
				/*
				 * Bad readlink call.
				 */
				return (NULL);
			}
		} else {
			/*
			 * Use the new path as the current path.
			 */
			strcpy(path_buffer, tmp_path);
		}

		filename = strtok(NULL, "/");
	}
	if (strlen(path_buffer) == 0) {
		/*
		 * The path is empty.  This can occur if the path argument
		 * was "/", because the code that constructs the path is in
		 * the above while loop, and the "/" path contains no valid
		 * tokens.  In this case, simply return "/".
		 */
		(void) sprintf(path_buffer, "/");
	}
	free(path_copy);
	if (encountered_link) {
		/*
		 * If we encountered a link, try this function again
		 * to ensure that our link resolution did not result
		 * in yet another link.
		 */
		char *final_path = futil_get_linkless_path(path_buffer);
		return (final_path);
	}
	return (sutil->clone(path_buffer));
}

/*
 * Removes "./" and "../" from the specified path.  The specified
 * path is modified.
 */
static void
futil_remove_path_duplication(char *path)
{
	/*
	 * Create a list of names in the path.
	 */
	List *path_list = _wsreg_list_create();
	String_util *sutil = _wsreg_strutil_initialize();
	char *name = strtok(path, "/");

	/*
	 * As we fill the path list, omit "/." and
	 * "/.." directories.
	 */
	while (name != NULL) {
		if (strcmp(name, ".") == 0) {
			/*
			 * Don't put "." into the list.
			 */
			/*EMPTY*/
		} else if (strcmp(name, "..") == 0) {
			/*
			 * Don't put this in the list either.  Also,
			 * be sure to pull out the last item in the
			 * list.
			 */
			int pos = path_list->size(path_list) - 1;
			char *removed = path_list->remove_element_at(
				path_list, pos);
			free(removed);
		} else {
			path_list->add_element(path_list, sutil->clone(name));
		}
		name = strtok(NULL, "/");
	}

	/*
	 * Go back through the list and fill in the path.
	 */
	sprintf(path, "\0");
	path_list->reset_iterator(path_list);
	while (path_list->has_more_elements(path_list)) {
		name = (char *)path_list->next_element(path_list);
		(void) sprintf(path, "%s/%s", path, name);
	}
	if (strlen(path) == 0) {
		/*
		 * The removal of duplication resulted in an
		 * empty path string.  The real path is "/".
		 */
		sprintf(path, "/");
	}
	path_list->free(path_list, free);
}

/*
 * Returns the canonical path that refers to the specified
 * path.
 */
static char *
futil_get_canonical_path(const char *path)
{
	char *canonical_path = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	if (path != NULL) {
		String_util *str = _wsreg_strutil_initialize();
		char *tmp_path = NULL;
		if (!str->starts_with(path, "/")) {
			/*
			 * This is a relative path.  Prepend the current
			 * directory.
			 */
			tmp_path = str->append(get_current_directory(),
			    "/");
			tmp_path = str->append(tmp_path, path);
		} else {
			tmp_path = sutil->clone(path);
		}

		/*
		 * Reduce the path.  This will involve:
		 *   1. Remove symbolic links.
		 *   2. Remove "./" and "../" from the path.
		 */
		canonical_path = futil_get_linkless_path(tmp_path);
		futil_remove_path_duplication(canonical_path);
		free(tmp_path);
	}
	return (canonical_path);
}

/*
 * Initializes the file_util object.  All methods
 * in this class are static, so no need to create
 * multiple copies of this object.  Notice that
 * there is no free method.
 */
File_util *
_wsreg_fileutil_initialize()
{
	File_util *futil = file_util;
	if (futil == NULL) {
		futil = (File_util *)wsreg_malloc(sizeof (File_util));
		/*
		 * Initalize the method set.
		 */
		futil->exists		= futil_exists;
		futil->is_file		= futil_is_file;
		futil->is_directory	= futil_is_directory;
		futil->can_read	 = futil_can_read;
		futil->can_write	= futil_can_write;
		futil->length		= futil_length;
		futil->get_name		= futil_get_name;
		futil->get_parent = futil_get_parent;
		futil->list_files	= futil_list_files;
		futil->remove		= futil_remove;
		futil->get_temp_name	= futil_get_temp_name;
		futil->is_link	  = futil_is_link;
		futil->get_canonical_path = futil_get_canonical_path;
		file_util = futil;
	}
	return (futil);
}
