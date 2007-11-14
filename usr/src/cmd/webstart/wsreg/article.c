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

#pragma ident	"@(#)article.c	1.9	06/02/27 SMI"

#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include "wsreg.h"
#include "boolean.h"
#include "hashtable.h"
#include "article.h"
#include "article_id.h"
#include "string_util.h"

/*
 * The structure used to associate private data with
 * an article object.
 */
struct _Article_private
{
	Hashtable *properties;
	List *revisions;
} _Article;

/*
 * Reads the specified buffer and creates an array of strings
 * from it.  Each string in the resulting array represents
 * one line in the original buffer.
 *
 * The original buffer is modified as a result of this call.
 */
static char **
get_line_array(char *buffer)
{
	char **array = NULL;
	int i = 0;
	int array_pos = 0;
	int buffer_length = strlen(buffer);
	int line_count = 0;
	int first_line = -1;

	/*
	 * Count the number of new lines in the buffer.
	 */
	for (i = 0; i < buffer_length; i++) {
		if (buffer[i] == '\n') {
			line_count++;
		} else if (first_line == -1)
			first_line = i;
	}

	/*
	 * Now fill in the array.
	 */
	array = (char **)wsreg_malloc(sizeof (char *) *
	    (line_count + 1));
	memset(array, 0, sizeof (char *) * (line_count + 1));
	array[array_pos++] = buffer + first_line;
	for (i = first_line; i < buffer_length; i++) {
		if (buffer[i] == '\n') {
			buffer[i] = '\0';
			if (array_pos < line_count) {
				array[array_pos++] = buffer + i + 1;
			}
		}
	}
	return (array);
}

/*
 * Reads a property from the specified line.  The property name is
 * passed back to the caller in the key buffer.  The value is
 * returned.
 */
static char *
read_property(char *line, char *key)
{
	char *value = NULL;
	int pos = 0;
	int key_length = 0;
	int line_length = strlen(line);
	Boolean found_key = FALSE;
	int value_pos = 0;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Search for the end of the key.
	 */
	for (pos = 0; !found_key && pos < line_length; pos++) {
		if (line[pos] == '=') {
			key_length = pos;
			found_key = TRUE;
		}
	}

	/*
	 * Copy the key into the key buffer.
	 */
	strncpy(key, line, key_length);
	key[key_length] = '\0';

	/*
	 * Copy the value into the return buffer.
	 */
	value = (char *)wsreg_malloc(sizeof (char) *
	    (line_length - key_length + 1));
	memset(value, 0, sizeof (char) * (line_length - key_length + 1));
	for (; pos < line_length; pos++) {
		if (line[pos] == '\\') {
			/*
			 * Convert the next character to its escaped
			 * equivalent.
			 */
			value[value_pos++] =
			    sutil->get_escaped_character(line[++pos]);
		} else {
			value[value_pos++] = line[pos];
		}
	}
	return (value);
}

/*
 * Reads an article from the specified buffer.  The format of the
 * text in the specified buffer is that of article files in the
 * prodreg 2.0 registry zip file.
 */
static Article *
art_from_string(char *name, char *buffer)
{
	Article *a = NULL;
	Revision *revision = _wsreg_revision_create();
	int i = 0;
	int r = 0;
	int read_count = 0;
	int format_version = 0;
	int revision_count = 0;
	char **lines = get_line_array(buffer);
	a = _wsreg_article_create();

	read_count = sscanf(lines[i++], "%d%d",
	    &format_version, &revision_count);
	if (read_count != 2 || format_version != 0) {
		(void) fprintf(stderr, "Error - article %s was "
		    "written in an unknown format.\n Trying to "
		    "continue.\n", name);
	}

	/*
	 * Read the revisions.
	 */
	for (r = 0; r < revision_count; r++, i++) {
		Revision *r = revision->from_string(lines[i]);
		a->add_revision(a, r);
	}

	while (lines[i] != NULL) {
		/*
		 * Be sure to ignore comment lines.
		 */
		if (lines[i][0] != '#') {
			char key[1024];
			char *value = NULL;
			value = read_property(lines[i], key);
			if (value != NULL) {
				char *old_value = a->set_property(a,
				    key, value);
				if (old_value != NULL)
					free(old_value);
				free(value);
			}
		}
		i++;
	}
	free(lines);
	revision->free(revision);
	return (a);
}

/*
 * Reads an article from the specified File_reader.  The format of
 * the article is a list of properties (key/value pairs separated
 * by an '=' sign.
 */
static Article *
art_read_data_sheet(File_reader *fr)
{
	Article *a = NULL;
	Boolean done = FALSE;
	char *version = NULL;
	char *versiondate = NULL;
	char *versionvector = NULL;
	a = _wsreg_article_create();

	while (!done && fr->has_more_lines(fr)) {
		char *line = fr->read_line(fr);
		if (line != NULL) {
			/*
			 * Did we reach the end of this Article?
			 */
			if (line[0] == '-') {
				done = TRUE;
				break;
			}

			/*
			 * Be sure to ignore comment lines.
			 */
			if (line[0] != '#') {
				char key[1024];
				char *value = NULL;
				value = read_property(line, key);
				if (value != NULL) {
					char *old_value =
					    a->set_property(a,
						key, value);
					if (old_value != NULL)
						free(old_value);
					free(value);
				}
			}
			free(line);

		} else {
			done = TRUE;
		}
	}
	version = a->remove_property(a, "version");
	versiondate = a->remove_property(a, "versiondate");
	versionvector = a->remove_property(a, "versionvector");

	if (version != NULL) {
		Revision *r = _wsreg_revision_create();
		r->set_version(r, version);
		free(version);
		if (versiondate != NULL) {
			/*
			 * TODO: The original prodreg took a build date.
			 * The date was entered via output from
			 * java.util.Date.toString().  We must take
			 * the format of that output and create a
			 * time from it.  See Article.java:230
			 */
			unsigned long builddate = atoll(versiondate);
			r->set_build_date(r, builddate);
		}
		if (versionvector != NULL) {
			/*EMPTY*/
			/*
			 * TODO: to parse the version vector, look at
			 * Revision.java:parseVVector.
			 */
		}

		/*
		 * Add the revision to the article.
		 */
		a->add_revision(a, r);
	}
	if (versiondate != NULL) {
		free(versiondate);
	}
	if (versionvector != NULL) {
		free(versionvector);
	}
	return (a);
}

/*
 * Returns an article that corresponds to the specified component.
 */
static Article *
art_from_component(Wsreg_component *component)
{
	Article *result = NULL;
	Wsreg_component **comps = NULL;
	Revision *rev = _wsreg_revision_create();
	String_util *sutil = _wsreg_strutil_initialize();

	result = _wsreg_article_create();
	rev->set_version(rev, wsreg_get_version(component));
	result->add_revision(result, rev);
	result->set_mnemonic(result, wsreg_get_unique_name(component));
	result->set_id(result, wsreg_get_data(component, "id"));
	result->set_property(result, "installlocation",
	    wsreg_get_location(component));
	result->set_property(result, "vendor",
	    wsreg_get_vendor(component));
	result->set_property(result, "title",
	    wsreg_get_display_name(component, "en"));

	comps = wsreg_get_child_components(component);
	if (comps != NULL) {
		char mnemonic_buffer[1000];
		char id_buffer[1000];
		int index;

		mnemonic_buffer[0] = '\0';
		id_buffer[0] = '\0';
		index = 0;
		while (comps[index] != NULL) {
			char *unique_name = wsreg_get_unique_name(
				comps[index]);
			char *id = wsreg_get_data(comps[index], "id");
			(void) sprintf(mnemonic_buffer, "%s%s ",
			    mnemonic_buffer, unique_name);
			(void) sprintf(id_buffer, "%s%s ", id_buffer, id);
		}
		if (strlen(mnemonic_buffer) > 0) {
			result->set_property(result, "articles",
			    sutil->clone(mnemonic_buffer));
			result->set_property(result, "articleids",
			    sutil->clone(id_buffer));
		}
	}
	return (result);
}

/*
 * Convenience function that frees the specified revision.
 */
static void
free_revision(void *rev)
{
	Revision *revision = _wsreg_revision_create();
	revision->free((Revision*)rev);
	revision->free(revision);
}

/*
 * Frees the specified article.
 */
static void
art_free(Article *a)
{
	if (a->pdata->properties != NULL) {
		a->pdata->properties->free(
			a->pdata->properties, free);
		a->pdata->properties = NULL;
	}
	if (a->pdata->revisions != NULL) {
		a->pdata->revisions->free(a->pdata->revisions,
		    free_revision);
		a->pdata->revisions = NULL;
	}
	free(a->pdata);
	free(a);
}

/*
 * Sets the specified mnemonic into the specified article object.
 */
static int
art_set_mnemonic(Article *a, const char *mnemonic)
{
	int result = 0;
	char *old_mnemonic = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	if (mnemonic != NULL) {
		old_mnemonic = a->set_property(a, "mnemonic",
		    sutil->clone(mnemonic));
	} else {
		old_mnemonic = a->remove_property(a,
		    "mnemonic");
	}
	if (old_mnemonic != NULL)
		free(old_mnemonic);
	result = 1;
	return (result);
}

/*
 * Returns the currently set mnemonic from the specified article.
 */
static char *
art_get_mnemonic(Article *a)
{
	char *mnemonic = NULL;
	mnemonic = a->get_property(a, "mnemonic");
	return (mnemonic);
}

/*
 * Sets the id of the specified article.
 */
static int
art_set_id(Article *a, const char *id)
{
	int result = 0;
	char *old_id = NULL;
	if (id != NULL) {
		old_id = a->set_property(a, "id", id);
	} else {
		old_id = a->remove_property(a, "id");
	}
	if (old_id != NULL)
		free(old_id);
	result = 1;
	return (result);
}

/*
 * Returns the id of the specified article.
 */
static char *
art_get_id(Article *a)
{
	char *id = NULL;
	id = a->get_property(a, "id");
	return (id);
}

/*
 * This method sets the article id automatically.  This
 * method is meant to be used while reading datasheets
 * from stdin.  Some Articles read that way will have
 * their id set; others won't.  Either way, the article
 * will have a valid id upon completion of this method.
 */
static void
art_generate_id(Article *a)
{
	char *id = NULL;
	Article_id *article_id = _wsreg_artid_initialize();
	id = a->remove_property(a, "chosenid");
	if (id != NULL) {
		/*
		 * The installer chose an id.  Make sure it
		 * is valid.
		 */
		if (!article_id->is_legal_id(id)) {
			/*
			 * Bad id.  Set up so the id will be generated.
			 */
			free(id);
			id = NULL;
		}
	}
	if (id == NULL) {
		/*
		 * No valid ID has been set.  Create one now.
		 */
		id = article_id->create_id();
	}
	a->set_id(a, id);
	free(id);
}

/*
 * Returns a NULL-terminated list of child mnemonics currently
 * set in the specified article.
 */
static char **
art_get_child_mnemonics(Article *a)
{
	char **mnemonics = NULL;
	char *children = a->get_property(a, "articles");
	String_util *sutil = _wsreg_strutil_initialize();
	if (children != NULL) {
		int i;
		int article_count = 0;
		char *s = NULL;

		/*
		 * Be sure not to disturb the original data.
		 */
		s = sutil->clone(children);
		children = s;
		s = strtok(children, " \n");
		while (s != NULL) {
			article_count++;
			s = strtok(NULL, " \n");
		}

		mnemonics = (char **)wsreg_malloc(sizeof (char *) *
		    (article_count + 1));
		memset(mnemonics, 0, sizeof (char *) * (article_count + 1));
		s = children;
		for (i = 0; i < article_count; i++) {
			mnemonics[i] = sutil->clone(s);
			s += strlen(mnemonics[i]) + 1;
		}
		free(children);
	}
	return (mnemonics);
}

/*
 * Returns a NULL-terminated list of child mnemonics currently set
 * into the specified article.
 */
static char **
art_get_child_ids(Article *a)
{
	char **ids = NULL;
	char *children = a->get_property(a, "articleids");
	String_util *sutil = _wsreg_strutil_initialize();
	if (children != NULL) {
		int i;
		int article_count = 0;
		char *s = NULL;

		/*
		 * Be sure not to disturb the original data.
		 */
		s = children = sutil->clone(children);
		s = strtok(children, " \n");
		while (s != NULL) {
			article_count++;
			s = strtok(NULL, " \n");
		}

		ids = (char **)wsreg_malloc(sizeof (char *) *
		    (article_count + 1));
		memset(ids, 0, sizeof (char *) * (article_count + 1));
		s = children;
		for (i = 0; i < article_count; i++) {
			ids[i] = sutil->clone(s);
			s += strlen(ids[i]) + 1;
		}
		free(children);
	}
	return (ids);
}

/*
 * Sets a property into the specified article.  If the property_value
 * is NULL, the specified property_name is unset from the article.
 *
 * The previous value associated with the specified property_name
 * is returned.
 */
static char *
art_set_property(Article *a, const char *property_name,
    const char *property_value)
{
	char *old_property_value = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	if (a->pdata->properties == NULL)
		a->pdata->properties = _wsreg_hashtable_create();
	if (property_value != NULL) {
		old_property_value =
		    a->pdata->properties->put(a->pdata->properties,
			property_name,
			sutil->clone(property_value));
	}
	return (old_property_value);
}

/*
 * Returns the value associated with the specified property_name
 * in the specified article.  If no value is associated with
 * the property_name, NULL is returned.
 */
static char *
art_get_property(Article *a, const char *property_name)
{
	char *property_value = NULL;

	property_value =
	    a->pdata->properties->get(a->pdata->properties,
		property_name);
	return (property_value);
}

/*
 * Removes the specified property from the specifed article.
 * The value associated with the specified property name before
 * the call to this function is returned.
 */
static char *
art_remove_property(Article *a, const char *property_name)
{
	char *old_property_value = NULL;
	old_property_value =
	    (char *)a->pdata->properties->remove(a->pdata->properties,
		property_name);
	return (old_property_value);
}

/*
 * Returns a NULL-terminated array of property names associated
 * with the specified article.
 */
static char **
art_get_property_names(Article *a)
{
	char **names = NULL;
	int names_length;
	List *property_names = a->pdata->properties->keys(a->pdata->properties);
	int i;

	/*
	 * Get the size of the list.
	 */
	names_length = property_names->size(property_names);

	/*
	 * Create the array
	 */
	names = (char **)wsreg_malloc(sizeof (char *) * (names_length + 1));
	memset(names, 0, sizeof (char *) * (names_length + 1));
	i = 0;
	property_names->reset_iterator(property_names);
	while (property_names->has_more_elements(property_names)) {
		names[i] = (char *)
		    property_names->next_element(property_names);
		i++;
	}

	property_names->free(property_names, NULL);
	return (names);
}

/*
 * Adds the specified revision to the specified article.
 */
static int
art_add_revision(Article *a, Revision *r)
{
	int result = 0;

	if (a->pdata->revisions == NULL)
		a->pdata->revisions = _wsreg_list_create();
	a->pdata->revisions->add_element(a->pdata->revisions, r);
	result = 1;
	return (result);
}

/*
 * Returns a NULL-terminated array of revision objects associated
 * with the specified article.
 */
static Revision **
art_get_revisions(Article *a)
{
	Revision **revisions = NULL;
	int revisions_length;

	if (a->pdata->revisions != NULL) {
		List *rev_list = a->pdata->revisions;
		int i;

		/*
		 * Get the size of the list.
		 */
		revisions_length = rev_list->size(rev_list);

		/*
		 * Create the array
		 */
		revisions = (Revision **)wsreg_malloc(sizeof (Revision *) *
		    (revisions_length + 1));
		memset(revisions, 0, sizeof (Revision *) *
		    (revisions_length + 1));
		i = 0;
		rev_list->reset_iterator(rev_list);
		while (rev_list->has_more_elements(rev_list)) {
			Revision *r = (Revision *)
			    rev_list->next_element(rev_list);
			revisions[i] = r->clone(r);
			i++;
		}
	}
	return (revisions);
}

/*
 * Returns the version associated with the specified article.
 */
static char *
art_get_version(Article *a)
{
	char *version = NULL;

	Revision **revisions = a->get_revisions(a);
	if (revisions != NULL) {
		int index = 0;
		char *tmp_version = NULL;
		while (revisions[index] != NULL) {
			tmp_version =
			    revisions[index]->get_version(revisions[index]);
			if (tmp_version != NULL) {
				/*
				 * Update the version.
				 */
				if (version != NULL)
					free(version);
				version = tmp_version;
			}
			revisions[index]->free(revisions[index]);
		}
		free(revisions);
	}
	return (version);
}

/*
 * Diagnostic function that prints the specified article to
 * the specified file.
 */
static void
art_print(Article *a, FILE *file)
{
	(void) fprintf(file, "Article{\n");
	if (a == NULL) {
		(void) fprintf(file, "\tNULL\n");
	} else {
		Revision **revisions = a->get_revisions(a);
		int index = 0;
		while (revisions != NULL &&
		    revisions[index] != NULL) {
			Revision *revision = revisions[index];
			revision->print(revision, file, "\t");
			index++;
		}
		(void) fprintf(file, "\tProperties{\n");
		{
			Hashtable *properties = a->pdata->properties;
			List *keys = properties->keys(properties);
			keys->reset_iterator(keys);
			while (keys->has_more_elements(keys)) {
				char *key = (char *)keys->next_element(keys);
				char *value = (char *)
				    properties->get(properties, key);
				(void) fprintf(file, "\t\t%s=%s\n", key, value);
			}
			keys->free(keys, NULL);
		}
		(void) fprintf(file, "\t}\n");
	}
	(void) fprintf(file, "}\n");
}

/*
 * Creates a new article object.
 */
Article*
_wsreg_article_create()
{
	Article *a = (Article*)wsreg_malloc(sizeof (Article));
	struct _Article_private *p = NULL;

	/*
	 * Load the method set.
	 */
	a->create = _wsreg_article_create;
	a->free = art_free;
	a->from_string = art_from_string;
	a->read_data_sheet = art_read_data_sheet;
	a->from_component = art_from_component;
	a->set_mnemonic = art_set_mnemonic;
	a->get_mnemonic = art_get_mnemonic;
	a->set_id = art_set_id;
	a->get_id = art_get_id;
	a->generate_id = art_generate_id;
	a->get_child_mnemonics = art_get_child_mnemonics;
	a->get_child_ids = art_get_child_ids;
	a->set_property	= art_set_property;
	a->get_property	= art_get_property;
	a->remove_property = art_remove_property;
	a->get_property_names = art_get_property_names;
	a->add_revision	= art_add_revision;
	a->get_revisions = art_get_revisions;
	a->get_version = art_get_version;
	a->print = art_print;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Article_private *)wsreg_malloc(
		sizeof (struct _Article_private));
	memset(p, 0, sizeof (struct _Article_private));
	a->pdata = p;
	return (a);
}
