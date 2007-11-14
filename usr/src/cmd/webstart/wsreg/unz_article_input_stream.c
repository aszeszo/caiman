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

#pragma ident	"@(#)unz_article_input_stream.c	1.12	06/02/27 SMI"

#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <strings.h>
#include "wsreg.h"
#include "unz_article_input_stream.h"
#include "list.h"
#include "string_util.h"
#include "file_util.h"

/*
 * Defines for unzip exit codes.
 */
#define	ZIP_NO_ERROR				0
#define	ZIP_WARNING				1
#define	ZIP_GENERIC_ERROR			2
#define	ZIP_SEVERE_ERROR			3
#define	ZIP_INIT_ERROR				4
#define	ZIP_TTY_MEMORY_ERROR			5
#define	ZIP_DISK_DECOMPRESSION_MEMORY_ERROR	6
#define	ZIP_MEMORY_DECOMPRESSION_MEMORY_ERROR	7
#define	ZIP_FILE_NOT_FOUND			9
#define	ZIP_INVALID_OPTIONS			10
#define	ZIP_NO_MATCHING_FILES			11
#define	ZIP_DISK_FULL				50
#define	ZIP_PREMATURE_EOF			51
#define	ZIP_USER_ABORT				80
#define	ZIP_EXTRACTION_FAILED			81
#define	ZIP_BAD_PASSWORD			82

/*
 * Stores data that is private to the unzip article input stream
 * object.
 */
struct _Unz_article_input_stream_private
{
	char *tmp_dirname;
	List *file_list;
} _Unz_article_input_stream_private;

/*
 * Frees the specified article input stream.
 */
static void
uzais_free(Unz_article_input_stream *uzain)
{
	if (uzain->pdata->tmp_dirname != NULL) {
		free(uzain->pdata->tmp_dirname);
	}
	if (uzain->pdata->file_list != NULL) {
		uzain->pdata->file_list->free(
			uzain->pdata->file_list, free);
	}
	free(uzain->pdata);
	free(uzain);
}

/*
 * Deletes all files associated with the specified
 * article input stream.  The files being deleted
 * were created by unzip.
 */
static void
remove_tmp_files(Unz_article_input_stream *uzain)
{
	if (uzain->pdata->file_list != NULL) {
		List *files = uzain->pdata->file_list;
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * Remove all files created by unzip.
		 */
		if (files != NULL) {
			files->reset_iterator(files);
			while (files->has_more_elements(files)) {
				char *filename = (char *)
				    files->next_element(files);
				futil->remove(filename);
			}
		}

		/*
		 * Remove the temporary directory.
		 */
		if (uzain->pdata->tmp_dirname != NULL) {
			futil->remove(uzain->pdata->tmp_dirname);
		}
	}
}

/*
 * Closes the specified article input stream.  The article
 * input stream is freed and all files created by the
 * article input stream are removed as a result of this
 * call.
 */
static void
uzais_close(Unz_article_input_stream *uzain)
{
	remove_tmp_files(uzain);
	uzais_free(uzain);
}

/*
 * Returns true if the specified article input stream has
 * more articles to read; false otherwise.
 */
static Boolean
uzais_has_more_articles(Unz_article_input_stream *uzain)
{
	Boolean result = FALSE;
	if (uzain->pdata->file_list != NULL) {
		List *files = uzain->pdata->file_list;
		result = files->has_more_elements(files);
	}
	return (result);
}

/*
 * Reads the next article from the specified article
 * input stream.  The caller is responsible for freeing
 * the resulting article.
 */
static Article *
uzais_get_next_article(Unz_article_input_stream *uzain)
{
	Article *_article = _wsreg_article_create();
	Article *article = NULL;

	if (uzain->has_more_articles(uzain)) {
		List *files = uzain->pdata->file_list;
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * Get the next filename from the list.
		 */
		char *filename = (char *)files->next_element(files);
		if (futil->exists(filename) &&
		    futil->is_file(filename)) {
			int file = open(filename, O_RDONLY, 0);
			if (file > 0) {
				char *article_name = futil->get_name(filename);
				int buffer_size = futil->length(filename);
				char *buffer = (char *)
				    wsreg_malloc(sizeof (char) *
				    (buffer_size + 1));
				ssize_t read_size = 0;
				memset(buffer, 0, sizeof (char) *
				    (buffer_size + 1));

				/*
				 * Read the file's contents.
				 */
				read_size = read(file, buffer, buffer_size);

				if (read_size > 0) {
					/*
					 * Convert the buffer into an article.
					 */
					article = _article->from_string(
						article_name, buffer);
				}

				free(buffer);
				free(article_name);
				close(file);
			}
		}
	}
	_article->free(_article);
	return (article);
}

/*
 * Returns the number of articles to be converted.
 */
static int
uzais_get_article_count(Unz_article_input_stream *ain)
{
	int count = 0;
	List *file_list = ain->pdata->file_list;
	if (file_list != NULL) {
		count = file_list->size(file_list);
	}
	return (count);
}

/*
 * Creates a new article input stream.  The caller is
 * responsible for freeing the new article input stream.
 */
static Unz_article_input_stream *
uzais_create()
{
	Unz_article_input_stream *uzain =
	    (Unz_article_input_stream*)
	    wsreg_malloc(sizeof (Unz_article_input_stream));
	struct _Unz_article_input_stream_private *p = NULL;

	/*
	 * Load the method set.
	 */
	uzain->open = _wsreg_uzais_open;
	uzain->close = uzais_close;
	uzain->has_more_articles = uzais_has_more_articles;
	uzain->get_next_article = uzais_get_next_article;
	uzain->get_article_count = uzais_get_article_count;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Unz_article_input_stream_private *)
	    wsreg_malloc(sizeof (struct _Unz_article_input_stream_private));
	memset(p, 0, sizeof (struct _Unz_article_input_stream_private));
	uzain->pdata = p;
	return (uzain);
}

/*
 * Expands the specified zip file into the specified
 * target path using /usr/bin/unzip.  The resulting
 * exit code is returned.
 */
static int
zip_expand(const char *zipfile, const char *targetpath)
{
	char *unzip_path = "/usr/bin/unzip";
	char *zip_command_template =
	    "%s -j -qq %s -d %s 2> /dev/null > /dev/null";
	char *zip_command = NULL;
	int result = ZIP_FILE_NOT_FOUND;

	if (zipfile != NULL && targetpath != NULL) {
		File_util *futil = _wsreg_fileutil_initialize();
		if (futil->exists(unzip_path)) {
			zip_command = (char *)wsreg_malloc(sizeof (char) *
			    (strlen(zip_command_template) +
				strlen(unzip_path) +
				strlen(zipfile) +
				strlen(targetpath) + 1));
			sprintf(zip_command, zip_command_template,
			    unzip_path,
			    zipfile, targetpath);

			/*
			 * Call the zip command.
			 */
			result = system(zip_command);

			free(zip_command);
		} else {
			/*
			 * The unzip binary is not installed.
			 */
			result = WSREG_UNZIP_NOT_INSTALLED;
		}
	}
	return (result);
}

/*
 * Creates a new article input stream that reads articles
 * from the zip file identified by the specified filename.
 * The exit code from unzip is returned in the specified
 * error.
 */
Unz_article_input_stream *
_wsreg_uzais_open(const char *filename, int *error)
{
	Unz_article_input_stream *ais = NULL;

	File_util *futil = _wsreg_fileutil_initialize();
	if (futil->exists(filename) &&
	    futil->is_file(filename)) {
		int result = 0;
		List *files = NULL;
		char *tmp_dirname = NULL;

		/*
		 * Create a temporary directory in which the zip
		 * file can be expanded.
		 */
		tmp_dirname = futil->get_temp_name();
		result = mkdir(tmp_dirname, S_IRWXU);
		if (result != 0) {
			*error = WSREG_CANT_CREATE_TMP_DIR;
			return (NULL);
		}

		/*
		 * The specified file exists and a temporary
		 * directory has been created.  Create the
		 * article input stream.
		 */
		ais = uzais_create();
		ais->pdata->tmp_dirname = tmp_dirname;

		/*
		 * Expand the zip file.
		 */
		result = zip_expand(filename, tmp_dirname);
		if (result != ZIP_NO_ERROR &&
		    result != ZIP_WARNING) {
			/*
			 * Bad decompress.
			 */
			remove_tmp_files(ais);
			uzais_free(ais);
			switch (result) {
			case WSREG_BAD_REGISTRY_FILE:
			case WSREG_UNZIP_NOT_INSTALLED:
				*error = result;
				break;
			default:
				*error = WSREG_UNZIP_ERROR;
			}
			return (NULL);
		}

		/*
		 * Load the file list.
		 */
		files = futil->list_files(tmp_dirname);
		if (files != NULL) {
			files->reset_iterator(files);
			ais->pdata->file_list = files;
		}
		*error = WSREG_SUCCESS;
	}
	return (ais);
}
