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


#include <fcntl.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/stat.h>
#include "spmicommon_lib.h"

/* public prototypes */

MFILE *		mopen(char *, int);
void 		mclose(MFILE *);
char *		mgets(char *, int, MFILE *);

/* ---------------------- public prototypes -------------------------- */

/*
 * Function:	mopen
 * Description: Open and memory-map a file (for reading, only).  This is
 *		optimized for the type of files we'll be reading from CD-ROM,
 *		as it uses madvise(MADV_WILLNEED) to get the kernel to read
 *		in the whole file so we don't have to wait for it. MFILE
 *		structures are dynamically allocated and are destroyed
 *		on close.
 * Scope:	public
 * Parameters:	name		[RO, *RO]
 *				Path name of file to be mmapped in.
 *		read_all	[RO]
 *				Whether or not MADV_WILLNEED is to be used
 *				to tell the kernel to read everything.
 * Return:	NULL 	- mmap failure
 *		!NULL	- pointer to MFILE structure for mmaped/opened file
 */
MFILE *
mopen(char *name, int read_all)
{
	struct stat	sbuf;
	MFILE *		mp;
	caddr_t		addr;
	int		fd;

	/* validate parameter */
	if (name == NULL)
		return (NULL);

	if ((fd = open(name, O_RDONLY)) < 0 || stat(name, &sbuf) < 0)
		return (NULL);

	if ((addr = mmap((caddr_t)0, sbuf.st_size, PROT_READ,
				MAP_PRIVATE, fd, (off_t)0)) == MAP_FAILED) {
		(void)close(fd);
		return (NULL);
	}

	(void) close(fd);

	if (read_all) {
		(void) madvise(addr, sbuf.st_size, MADV_WILLNEED);
	}

	if ((mp = (MFILE *)calloc((size_t)1,
			(size_t)sizeof (MFILE))) != NULL) {
		mp->m_base = addr;
		mp->m_ptr = addr;
		mp->m_size = sbuf.st_size;
	}

	return (mp);
}

/*
 * Function:	mclose
 * Description: Unmap, close, and free resources associated with an mopen'ed
 *		file.
 * Scope:	public
 * Parameters:	mp	[RO, *RO]
 *			mmap file data structure pointer.
 * Return:	none
 */
void
mclose(MFILE *mp)
{
	if (mp != NULL) {
		(void) munmap(mp->m_base, mp->m_size);
		free(mp);
	}
}

/*
 * Function:	mgets
 * Description: Search mmapped data area up to the next '\n'. Advance the
 *		m_ptr passed the next '\n', and return the line.
 * Scope:	public
 * Parameters:	buf	- [RO, *RO]
 *			  Buffer used to retrieve the next line.
 *		len	- [RO]
 *			  Size of buffer.
 *		mp	- [RO, *RW]
 *			  Pointer to an opened mmaped file MFILE structure.
 * Return:	NULL	- EOF without match
 *		!NULL	- pointer to location in 'pattern'
 */
char *
mgets(char *buf, int len, MFILE *mp)
{
	char *	src;
	char *	dest;

	/* validate parameters */
	if (len <= 0 || buf == NULL || mp == NULL ||
			mp->m_base == NULL || mp->m_ptr == NULL)
		return (NULL);

	src = (char *)mp->m_ptr;
	dest = buf;

	/*
	 * search the mmapped area, up to the first NULL character
	 * to include, but not exceed either the buffer length or the
	 * first '\n' character. If previous mgets calls have been
	 * made the search will begin where the last line left off.
	 */
	while ((src < (mp->m_base + mp->m_size)) &&
			(*src != '\0') && (src < (mp->m_ptr + len - 1))) {
		if ((*dest++ = *src++) == '\n')
			break;
	}

	/*
	 * return an EOF indication if no data was read, otherwise
	 * NULL terminate the string, and advance the file pointer
	 */
	if (mp->m_ptr == src)
		return (NULL);

	*dest = '\0';
	mp->m_ptr = src;
	return (dest);
}
