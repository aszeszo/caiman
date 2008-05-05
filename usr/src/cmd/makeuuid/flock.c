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


#include "flock.h"

#include <fcntl.h>
#include <unistd.h>

/*
 * Global functions
 */
static int _file_lock_test(int, int);


/*
 * Local functions
 */

/*
 * Name:	_file_lock_test.
 *
 * Description:	Tests whether a file is able to be locked without waiting.
 *
 * Returns:	0 if it would not block if locked, non-zero otherwise.
 */
static int
_file_lock_test(int fd, int type)
{
	struct flock lock;
	int result;

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
			return (1);
		}
	}

	/*
	 * The file is not locked.
	 */
	return (0);
}

/*
 * Name:	_file_lock.
 *
 * Description:	Locks a file, with optional blocking if lock held by other
 *		process.
 *
 * Returns:	0 on success, non-zero otherwise.
 */
int
file_lock(int fd, int type, int wait)
{
	struct flock lock;

	lock.l_type = type;
	lock.l_start = 0;
	lock.l_whence = SEEK_SET;
	lock.l_len = 0;

	if (!wait) {
		if (_file_lock_test(fd, type)) {
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
 * Name:	_file_unlock.
 *
 * Description:	Unlocks a file.  The file is not closed.
 *
 * Returns:	0 on success, non-zero otherwise.
 */
int
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
 * Name:	_file_available.
 *
 * Description:	Tests whether a file is lockable, without attempting
 *		to lock it.
 *
 * Returns:	0 if the file can be locked, non-zero otherwise.
 */
int
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
