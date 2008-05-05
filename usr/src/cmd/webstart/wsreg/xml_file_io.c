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


#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <ctype.h>
#include "xml_file_io.h"
#include "boolean.h"
#include "stack.h"
#include "wsreg.h"
#include "string_util.h"

static void
nonblocking_usleep(unsigned int);
static void
xfio_write(Xml_file_context *, const char *);
static Boolean
xfio_prepare_files(Xml_file_io *);
static int
file_lock(int, int, int);
static int
file_unlock(int);
static Boolean
file_available(int);
static Boolean
file_complete(Xml_file_io *, char *);
static Boolean
file_lock_test(int, int);

/*
 * Stores data private to an xml file io object.
 */
struct _Xml_file_io_private
{
	char *file_name;
	char *backup_file_name;
	char *new_file_name;

	Xml_file_context *file_context;
	String_map *tag_map;
} _Xml_file_io_private;


/*
 * Frees the specified xml file io object.
 */
static void
xfio_free(Xml_file_io *xf)
{
	if (xf->pdata->file_name != NULL)
		free(xf->pdata->file_name);
	if (xf->pdata->backup_file_name != NULL)
		free(xf->pdata->backup_file_name);
	if (xf->pdata->new_file_name != NULL)
		free(xf->pdata->new_file_name);

	if (xf->pdata->file_context != NULL)
		xf->pdata->file_context->free(
			xf->pdata->file_context);

	/*
	 * The xf->pdata->tag_map was passed in from the client;
	 * do not free it here!
	 */
	free(xf->pdata);
	free(xf);
}

/*
 * Sets the file names of the xml file, the backup file,
 * and the new file.  These file names will be used when
 * making a modification to an xml file.
 */
void
xfio_set_file_names(Xml_file_io *xf,
    const char *file_name,
    const char *backup_file_name,
    const char *new_file_name)
{
	struct _Xml_file_io_private *pdata = xf->pdata;
	String_util *sutil = _wsreg_strutil_initialize();
	if (pdata->file_name != NULL)
		free(pdata->file_name);
	if (pdata->backup_file_name != NULL)
		free(pdata->backup_file_name);
	if (pdata->new_file_name != NULL)
		free(pdata->new_file_name);
	pdata->file_name = sutil->clone(file_name);
	pdata->backup_file_name = sutil->clone(backup_file_name);
	pdata->new_file_name = sutil->clone(new_file_name);
}

/*
 * Returns the name of the xml file.  The caller
 * should not free the resulting filename.
 */
static char *
xfio_get_file_name(Xml_file_io *xf)
{
	return (xf->pdata->file_name);
}

/*
 * Returns the name of the xml backup file.  The
 * caller should not free the resulting filename.
 */
static char *
xfio_get_backup_file_name(Xml_file_io *xf)
{
	return (xf->pdata->backup_file_name);
}

/*
 * Returns the name of the xml new file.  The
 * caller should not free the resulting filename.
 */
static char *
xfio_get_new_file_name(Xml_file_io *xf)
{
	return (xf->pdata->new_file_name);
}

/*
 * Opens the xml file associated with the specified
 * xml file io object with the specified permissions.
 */
static void
xfio_open(Xml_file_io *xf, Xml_file_mode mode, mode_t permissions)
{
	struct stat regstat;
	char *path = xf->pdata->file_name;
	char *newpath = xf->pdata->new_file_name;

	int result = stat(path, &regstat);

	Xml_file_context *xc = NULL;

	if (xf->pdata->file_context != NULL) {
		xf->pdata->file_context->free(xf->pdata->file_context);
		xf->pdata->file_context = NULL;
	}

	(void) xfio_prepare_files(xf);


	switch (mode) {
	case READONLY:
		xc = _wsreg_xfc_create();
		if (result == 0) {
			/*
			 * The file exists.  Try to get a read lock.
			 */
			int fd = open(path, O_RDONLY, 0);
			if (fd != -1) {
				xc->set_readfd(xc, fd);
				(void) file_lock(xc->get_readfd(xc),
				    F_RDLCK, 0);
				xc->set_mode(xc, READONLY);
			}
		}
		break;
	case READWRITE:
	{
		int fd = 0;
		xc = _wsreg_xfc_create();
		if (result == 0) {
			fd = open(path, O_RDONLY, 0);
			if (fd != -1) {
				xc->set_readfd(xc, fd);
				(void) file_lock(xc->get_readfd(xc),
				    F_WRLCK, 0);
				permissions = regstat.st_mode;
			}
		}
		fd = open(newpath, O_CREAT | O_RDWR, permissions);
		if (fd != -1) {
			xc->set_writefd(xc, fd);
			(void) file_lock(xc->get_writefd(xc), F_WRLCK, 0);
			xc->set_mode(xc, READWRITE);
		}
		break;
	}
	}

	xf->pdata->file_context = xc;
}

/*
 * Closes the xml file associated with the specified
 * xml file io object.
 */
static void
xfio_close(Xml_file_io *xf)
{
	Xml_file_context *xc = xf->pdata->file_context;
	if (xc->get_mode(xc) == READWRITE &&
	    xc->get_writefd(xc) != -1) {
		if (xc->get_writefd(xc) != -1) {
			char *path = xf->pdata->file_name;
			char *origpath = xf->pdata->backup_file_name;
			char *newpath = xf->pdata->new_file_name;

			if (xc->get_readfd(xc) != -1)
				(void) rename(path, origpath);
			(void) rename(newpath, path);

			if (xc->get_readfd(xc) != -1) {
				(void) file_unlock(xc->get_readfd(xc));
				(void) close(xc->get_readfd(xc));
				(void) remove(origpath);
			}
			(void) file_unlock(xc->get_writefd(xc));
			(void) close(xc->get_writefd(xc));
		}
	} else if (xc->get_readfd(xc) != -1) {
		(void) file_unlock(xc->get_readfd(xc));
		(void) close(xc->get_readfd(xc));
	}

	xc->free(xc);
	xf->pdata->file_context = NULL;
}

/*
 * Writes the specified xml tag to the xml file.
 */
static void
xfio_write_tag(Xml_file_io *xf, const Xml_tag *xt)
{
	/*
	 * Write the tag into the file.  If the value is non-NULL
	 * write the value.
	 * Format:
	 * (xd->tab)\t<tag>value
	 */
	char buffer[MAX_LINE_LENGTH + 1];
	int index;
	Xml_file_context *xc = xf->pdata->file_context;
	char *tag = xt->get_tag_string(xt);
	char *value = xt->get_value_string(xt);

	for (index = 0; index < xc->get_tab_count(xc); index++) {
		buffer[index] = '\t';
	}
	(void) sprintf(buffer + xc->get_tab_count(xc), "<%s>%s\n",
	    tag, value?value:"");
	xfio_write(xc, buffer);
	xc->tab_increment(xc);
}

/*
 * Writes a close tag for the specified xml tag to
 * the specified xml file.
 */
static void
xfio_write_close_tag(Xml_file_io *xf, const Xml_tag *xt)
{
	/*
	 * Write the tag ending into the file.
	 * Format:
	 * (xd->tab-1)\t < /tag>
	 */
	char buffer[MAX_LINE_LENGTH + 1];
	int index;
	Xml_file_context *xc = xf->pdata->file_context;
	char *tag = xt->get_tag_string(xt);

	if (xc->get_tab_count(xc) > 0)
		xc->tab_decrement(xc);

	for (index = 0; index < xc->get_tab_count(xc); index++) {
		buffer[index] = '\t';
	}
	(void) sprintf(buffer+xc->get_tab_count(xc), "</%s>\n", tag);
	xfio_write(xc, buffer);
}

/*
 * Loads the tag and value with the next tag/value pair
 * found in the file.  If the read buffer is empty or
 * near-empty, the read buffer will be filled with data
 * from the file.
 */
static Xml_tag *
xfio_read_tag(Xml_file_io *xf)
{
	char _tag[MAX_TAG_LENGTH + 1];
	char _value[MAX_VALUE_LENGTH + 1];
	char readbuffer[MAX_LINE_LENGTH + 1];
	unsigned int bytesRead;
	char *tagpos;
	int bufferptr;
	unsigned int fileoffset = 0;
	int i = 0;

	Xml_file_context *xc = xf->pdata->file_context;
	Xml_tag *xt = NULL;

	if (xc->get_readfd(xc) < 0) {
		return (xt);
	}

	xt = _wsreg_xtag_create();

	fileoffset = lseek(xc->get_readfd(xc), 0, SEEK_CUR);

	_tag[0] = '\0';
	bytesRead = read(xc->get_readfd(xc), readbuffer, MAX_LINE_LENGTH);
	readbuffer[bytesRead] = '\0';

	if (bytesRead == 0)
		return (0);

	tagpos = strstr(readbuffer, "<");
	/*
	 * Get the line number.
	 */
	for (i = 0; i < bytesRead && i < (tagpos - readbuffer); i++) {
		if (readbuffer[i] == '\n')
			xc->line_increment(xc);
	}

	if (bytesRead > 0 && tagpos != NULL) {
		int tagptr = 0;
		bufferptr = tagpos - readbuffer;

		/*
		 * Skip the "<"
		 */
		bufferptr++;
		while (readbuffer[bufferptr] != '>' &&
		    bufferptr < bytesRead) {
			if (readbuffer[bufferptr] == '\n')
				xc->line_increment(xc);
			_tag[tagptr++] = readbuffer[bufferptr++];
		}

		/*
		 * Skip the ">" and terminate the tag string.
		 */
		bufferptr++;
		_tag[tagptr] = '\0';

		if (strlen(_tag) > 0) {
			int offset = 0;
			if (_tag[0] == '/') {
				xt->set_end_tag(xt, 1);
				offset++;
			}
			xt->set_tag(xt, xf->pdata->tag_map, _tag + offset);
		}


		/*
		 * If the tag is not a close tag, look to see if there is
		 * a value.
		 */
		if (xt->get_tag_string(xt) != NULL &&
		    !xt->is_end_tag(xt)) {
			char *valueEnd =
			    strstr(readbuffer + bufferptr + 1, "<");
			if (valueEnd != NULL) {
				int valueptr = 0;

				/*
				 * Trim whitespace from the beginning
				 * of the value.
				 */
				while (isspace((int)readbuffer[bufferptr]) &&
				    bufferptr < bytesRead) {
					if (readbuffer[bufferptr] == '\n')
						xc->line_increment(xc);
					bufferptr++;
				}
				while (readbuffer[bufferptr] != '<' &&
				    bufferptr < bytesRead) {
					if (readbuffer[bufferptr] == '\n')
						xc->line_increment(xc);
					_value[valueptr++] =
					    readbuffer[bufferptr++];
				}
				_value[valueptr] = '\0';

				/*
				 * Trim whitespace from the end of the value.
				 */
				for (valueptr = valueptr - 1;
					valueptr >= 0 &&
						isspace((int)_value[valueptr]);
					valueptr--) {
					_value[valueptr] = '\0';
				}

				if (strlen(_value) > 0) {
					/*
					 * Set the value.
					 */
					xt->set_value_string(xt, _value);
				}
			}
		}

		/*
		 * reset the filepointer.
		 */
		(void) lseek(xc->get_readfd(xc),
		    bufferptr + fileoffset, SEEK_SET);
	}
	if (xt->get_tag_string(xt) == NULL) {
		/*
		 * There was a problem reading the tag.
		 */
		xt->free(xt);
		xt = NULL;
	}

	return (xt);
}


/*
 * This function is responsible for fixing the
 * state of the registry.  This function waits until
 * the state of the registry files would allow a new
 * process to open the registry for writing.
 */
static Boolean
xfio_prepare_files(Xml_file_io *xf)
{
	struct stat regnewstat;
	char *newpath = xf->pdata->new_file_name;

	int newresult = stat(newpath, &regnewstat);

	if (newresult == 0) {
		/*
		 * The new file exists.  This new file will
		 * represent the current state of the registry.  If
		 * a process owns this file, We must
		 * wait until this file has been removed.
		 */
		int file = open(newpath, O_RDONLY, 0);
		while (!file_available(file)) {
			nonblocking_usleep(100000 * 5);
		}
		(void) close(file);
		newresult = stat(newpath, &regnewstat);

		if (newresult == 0) {
			/*
			 * The new file still exists with now owner
			 * process.  If the file is incomplete, it
			 * should be removed.  If it is complete,
			 * we should move it into place.
			 */
			if (file_complete(xf, newpath)) {
				/*
				 * The new file is complete.  Move it into
				 * position.
				 */
				char *path = xf->pdata->file_name;
				char *origpath = xf->pdata->backup_file_name;

				(void) rename(path, origpath);
				(void) rename(newpath, path);
				(void) remove(origpath);
			} else {
				/*
				 * The new file is not complete.  Remove
				 * it.
				 */
				(void) remove(newpath);
			}
		}
	}
	return (TRUE);
}

/*
 * Sleeps for the specified number of microseconds.
 * This call does not hang the application during
 * the sleep.
 */
static void
nonblocking_usleep(unsigned int microseconds)
{
	int descriptorTableSize = 0;
	struct timeval waitTime;

	if (0 == microseconds)
		return;
	descriptorTableSize = sysconf(_SC_OPEN_MAX);
	waitTime.tv_sec = microseconds / 1000000;
	waitTime.tv_usec = microseconds % 1000000;
	(void) select(descriptorTableSize,
	    0, 0, 0,
	    &waitTime);
}

/*
 * Writes the specified data to the specified file.
 */
static void
xfio_write(Xml_file_context *xc, const char *data)
{
	int len = strlen(data);
	int flushcount = 0;

	while (flushcount < len) {
		flushcount += write(xc->get_writefd(xc),
		    data + flushcount,
		    len - flushcount);
	}
}

/*
 * Returns FALSE if the file is not locked; TRUE
 * otherwise.
 */
static Boolean
file_lock_test(int fd, int type)
{
	struct flock lock;
	Boolean result = FALSE;

	lock.l_type = type;
	lock.l_start = 0;
	lock.l_whence = SEEK_SET;
	lock.l_len = 0;

	result = fcntl(fd, F_GETLK, &lock);
	if (result != -1) {
		if (lock.l_type != F_UNLCK) {
			/*
			 * The caller would have to wait to get the
			 * lock on this file.
			 */
			return (TRUE);
		}
	}

	/*
	 * The file is not locked.
	 */
	return (FALSE);
}

/*
 * Locks the specified file.
 */
static int
file_lock(int fd, int type, int wait)
{
	struct flock lock;

	lock.l_type = type;
	lock.l_start = 0;
	lock.l_whence = SEEK_SET;
	lock.l_len = 0;

	if (!wait) {
		if (file_lock_test(fd, type)) {
			/*
			 * The caller would have to wait to get the
			 * lock on this file.
			 */
			return (-1);
		}
	}

	return (fcntl(fd, F_SETLKW, &lock));
}

/*
 * Unlocks the specified file.
 */
static int
file_unlock(int fd)
{
	struct flock lock;

	lock.l_type = F_UNLCK;
	lock.l_start = 0;
	lock.l_whence = SEEK_SET;
	lock.l_len = 0;

	return (fcntl(fd, F_SETLK, &lock));
}

/*
 * Returns true if the specified file is
 * not locked.
 */
static Boolean
file_available(int fd)
{
	struct flock lock;

	lock.l_type = F_WRLCK;
	lock.l_start = 0;
	lock.l_whence = SEEK_SET;
	lock.l_len = 0;
	(void) fcntl(fd, F_GETLK, &lock);

	return (lock.l_type == F_UNLCK);
}

/*
 * Returns true if the specified xml file is complete.
 * This is judged based on the completeness of the
 * xml tags (all open tags should have end tags), and
 * there should be at least 2 tags (one open tag and
 * one end tag).
 */
static Boolean
file_complete(Xml_file_io *xfile, char *filename)
{
	Boolean result = FALSE;
	Boolean has_tags = FALSE;
	Boolean content_ok = TRUE;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Create a stack, read the xml file, and
	 * ensure the tags are all matched.
	 */
	Xml_file_io *xf = _wsreg_xfio_create(xfile->pdata->tag_map);
	Xml_file_context *xc = _wsreg_xfc_create();
	Stack *tag_stack = _wsreg_stack_create();
	Boolean done = FALSE;
	int fd = 0;

	xf->pdata->file_name = sutil->clone(filename);
	fd = open(filename, O_RDONLY, 0);
	if (fd != -1) {
		xc->set_readfd(xc, fd);
		(void) file_lock(xc->get_readfd(xc),
		    F_RDLCK, 0);
		xc->set_mode(xc, READONLY);
		xf->pdata->file_context = xc;
	} else {
		xf->free(xf);
		xc->free(xc);
		tag_stack->free(tag_stack, free);
		return (FALSE);
	}
	while (!done) {
		Xml_tag *tag;
		tag = xf->read_tag(xf);
		if (tag == NULL) {
			/*
			 * This is the exit case
			 */
			done = TRUE;
		} else {
			int tag_id = tag->get_tag(tag);
			if (tag_id == -1) {
				/*
				 * Found an unrecognized tag.  This
				 * is not a good sign.
				 */
				done = TRUE;
				content_ok = FALSE;
			} else {
				/*
				 * If this is an end tag, pop a value
				 * off of the stack and it should
				 * match this tag.
				 *
				 * If this is not and end tag, push
				 * the tag onto the stack.
				 */
				if (tag->is_end_tag(tag)) {
					char *tag_string =
					    tag_stack->pop(tag_stack);
					if (tag_string != NULL &&
					    strcmp(tag_string,
						tag->get_tag_string(
							tag)) == 0) {
						/*
						 * Found an end tag
						 * that doesn't match.
						 */
						done = TRUE;
						content_ok = FALSE;
						free(tag_string);
					}
				} else {
					/*
					 * This is not an end tag.
					 * Push it onto the stack.
					 */
					tag_stack->push(tag_stack,
					    sutil->clone(tag->get_tag_string(
						    tag)));
				}
			}
			tag->free(tag);
		}
	}

	if (content_ok && has_tags) {
		/*
		 * Be sure there are no more tags in the stack,
		 * which would mean the file was not complete.
		 */
		if (tag_stack->size(tag_stack) == 0) {
			result = TRUE;
		}
	}

	/*
	 * Cleanup.
	 */
	tag_stack->free(tag_stack, (Free)free);
	xf->close(xf);

	return (result);
}

/*
 * Creates a new xml file io object that can be used
 * to read and modify an xml file.
 */
Xml_file_io *
_wsreg_xfio_create(String_map *tag_map)
{
	Xml_file_io *xf = (Xml_file_io*)wsreg_malloc(sizeof (Xml_file_io));
	struct _Xml_file_io_private *p = NULL;

	/*
	 * Load the method set.
	 */
	xf->free = xfio_free;
	xf->set_file_names = xfio_set_file_names;
	xf->get_file_name = xfio_get_file_name;
	xf->get_backup_file_name = xfio_get_backup_file_name;
	xf->get_new_file_name = xfio_get_new_file_name;
	xf->open = xfio_open;
	xf->close = xfio_close;
	xf->write_tag = xfio_write_tag;
	xf->write_close_tag = xfio_write_close_tag;
	xf->read_tag = xfio_read_tag;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Xml_file_io_private *)
	    wsreg_malloc(sizeof (struct _Xml_file_io_private));
	memset(p, 0, sizeof (struct _Xml_file_io_private));
	p->tag_map = tag_map;
	xf->pdata = p;
	return (xf);
}
