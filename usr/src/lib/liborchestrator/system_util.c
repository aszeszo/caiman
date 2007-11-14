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

#pragma ident	"@(#)system_util.c	1.2	07/08/14 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/param.h>
#include <sys/systeminfo.h>

#include "orchestrator_private.h"

/*
 * Global variables
 */
static char current_architecture[MAXNAMELEN] = "";

/*
 * Local functions
 */
char		*get_system_arch();

/*
 * is_system_sparc
 * This function checks whether the underlying system is based on SPARC
 * architecture.
 * Input:	None
 * Output:	None.
 * Return:	B-TRUE, if the system is based on SPARC architecture
 *		B_FALSE, if the system is not based on SPARC architecture.
 */
boolean_t
is_system_sparc()
{
	char	*arch;

	arch = get_system_arch();

	if (arch == NULL) {
		return (B_FALSE);
	}

	return (streq(arch, SPARC_ARCH));
}

/*
 * is_system_x86
 * This function checks whether the underlying system is based on X86
 * architecture.
 * Input:	None
 * Output:	None.
 * Return:	B-TRUE, if the system is based on X86 architecture
 *		B_FALSE, if the system is not based on X86 architecture.
 */
boolean_t
is_system_x86()
{
	char	*arch;

	arch = get_system_arch();

	if (arch == NULL) {
		return (B_FALSE);
	}

	return (streq(arch, X86_ARCH));
}

/*
 * get_system_arch
 * This function returns the architecture (SPARC/X86) of the underlying
 * system.
 * Input:	None
 * Output:	None.
 * Return:	char * - The architecture of the system will be returned.
 *		NULL, If there is a failure
 */
char *
get_system_arch()
{
	int	i;

	if (current_architecture[0] == '\0') {
		i = sysinfo(SI_ARCHITECTURE, current_architecture, MAXNAMELEN);
		if (i < 0 || i > MAXNAMELEN) {
			return (NULL);
		}
	}
	return (current_architecture);
}

/*
 * create_dated_file
 * This function creates a file name by adding year, month and day to the input
 * file and also checks whether the new file can be created.
 * For example, if the file name is log, and the date is 08/06/07, this
 * function will create a new file "log_2007_08_06". If this file already exists
 * then "log_2007_08_06_1" will be created and so on till a unique file is
 * created.
 * Input:	char *dir - The directory where the dated file will be created
 *		char *file - file name whose dated name to be created.
 * Output:	None
 * Return:	char * - The name of the dated file that will be created
 *		NULL, If there is a failure
 * NOTE:	The caller should free the allocated return value
 */
char *
create_dated_file(char *dir, char *filename)
{
	char		date_str[MAXPATHLEN];
	char		new_file[MAXPATHLEN];
	char		temp[MAXPATHLEN];
	char		buf[MAXPATHLEN];
	time_t		current_time;
	int		i;
	boolean_t	status = B_TRUE;

	if (dir == NULL || filename == NULL) {
		return (NULL);
	}
	/*
	 * Get the current working directory and save it
	 * We are going to do a chdir and we need to restore the cwd
	 * once we finish our work.
	 */
	if (getcwd(buf, sizeof (buf)) == NULL) {
		om_debug_print(OM_DBGLVL_WARN, NSI_GETCWD_FAILED, errno);
		return (NULL);
	}

	if (chdir(dir) < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CHDIR_FAILED, dir, errno);
		return (NULL);
	}

	/*
	 * Get the current day/month/year
	 */
	if (time(&current_time) < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_TIME_FAILED, errno);
		status = B_FALSE;
		goto cdf_return;
	}
	(void) strftime(date_str, sizeof (date_str),
	    "%Y_%m_%d", localtime(&current_time));
	(void) snprintf(new_file, sizeof (new_file),
	    "%s_%s", filename, date_str);

	/*
	 * If the file exists, add a suffix to make it unique
	 * We will create maximum of 10 files and reuse the suffix
	 * if needed
	 */
	i = 0;
	if (access(new_file, F_OK) == 0) {
		for (i = 1; i < 10; i++) {
			(void) snprintf(temp, sizeof (temp),
			    "%s_%d", new_file, i);
			if (access(temp, F_OK) != 0) {
				break;
			}
		}
	}
	if (i != 0 && i != 10) {
		(void) strlcpy(new_file, temp, sizeof (new_file));
	}
cdf_return:
	/*
	 * Change the directory back to what it was
	 */
	if (chdir(buf) < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CHDIR_FAILED, dir, errno);
	}
	if (status) {
		return (strdup(new_file));
	} else {
		return (NULL);
	}
}

/*
 * Copy of the contents of src to dest
 */
boolean_t
copy_file(char *src, char *dest)
{
	int	src_fd, dest_fd;
	char	buf[4096];
	int	size;

	if (dest == NULL || src == NULL) {
		return (B_TRUE);
	}

	src_fd = open(src, O_RDONLY);
	if (src_fd < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_OPENFILE_FAILED, src, errno);
		return (B_FALSE);
	}

	dest_fd = open(dest, O_WRONLY | O_CREAT | O_TRUNC,
	    S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
	if (dest_fd < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_OPENFILE_FAILED,
		    dest, errno);
		return (B_FALSE);
	}

	while ((size = read(src_fd, buf, sizeof (buf))) > 0) {
		(void) write(dest_fd, buf, size);
	}
	(void) close(src_fd);
	(void) close(dest_fd);
	return (B_TRUE);
}

/*
 * Remove the destination file if it exists and symlink it to source
 */
boolean_t
remove_and_relink(char *dir, char *src, char *dest)
{
	int		ret;
	char		buf[MAXPATHLEN];
	boolean_t	status = B_TRUE;

	if (dir == NULL || dest == NULL || src == NULL) {
		return (B_TRUE);
	}

	/*
	 * Get the current working directory and save it
	 * We are going to do a chdir and we need to restore the cwd
	 * once we finish our work.
	 */
	if (getcwd(buf, sizeof (buf)) == NULL) {
		om_debug_print(OM_DBGLVL_WARN, NSI_GETCWD_FAILED, errno);
		return (B_FALSE);
	}

	if (chdir(dir) < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CHDIR_FAILED, dir, errno);
		return (B_FALSE);
	}

	errno = 0;
	/*
	 * delete the file if it exists
	 */
	if (access(dest, F_OK) == 0) {
		(void) unlink(dest);
	}

	/*
	 * Create symlink with the source file
	 */
	ret = symlink(src, dest);
	if (ret < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CREATE_SLINK_FAILED,
		    src, errno);
		status = B_FALSE;
	}

	/*
	 * Change the directory back to what it was
	 */
	if (chdir(buf) < 0) {
		om_debug_print(OM_DBGLVL_WARN, NSI_CHDIR_FAILED, dir, errno);
	}
	return (status);
}
