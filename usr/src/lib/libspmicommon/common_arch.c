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

#pragma ident	"@(#)common_arch.c	1.4	07/11/09 SMI"

/*
 * Module:	common_crch.c
 * Group:	libspmicommon
 * Description:
 *	Module for handling machine or architecture-specific properties
 */

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/openpromio.h>
#include <sys/param.h>
#include <sys/systeminfo.h>
#include <sys/types.h>

#include "spmicommon_lib.h"

/* Local Statics */

static char	default_machine[ARCH_LENGTH] = "";
static char	prom_revision[OPROMMAXPARAM] = "";
static char	default_inst[ARCH_LENGTH] = "";
static char	default_platform[PLATFORM_LENGTH] = "";
static int	default_platform_set = 0;
static char	actual_platform[PLATFORM_LENGTH] = "";
static int	actual_platform_set = 0;

/* Public Function Prototypes */

char		*get_default_inst(void);
char		*get_default_machine(void);
char		*get_default_platform(void);
char		*get_actual_platform(void);

/* Library Function Prototypes */

/* Local Function Prototypes */

#define	MAXPROPSIZE	128
#define	MAXVALSIZE	(4096 - MAXPROPSIZE - sizeof (u_int))
#define	PROMBUFSIZE	(MAXPROPSIZE + MAXVALSIZE + sizeof (u_int))
typedef union {
	char buf[PROMBUFSIZE];
	struct openpromio opp;
} Oppbuf;

#ifndef	SI_PLATFORM
#define	SI_PLATFORM	513
#endif

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * get_default_inst()
 *	Returns the default instruction set architecture of the
 *	machine it is executed on. (eg. sparc, i386, ...)
 *	NOTE:	SYS_INST environment variable may override default
 *		return value
 * Parameters:
 *	none
 * Return:
 *	NULL	- the architecture returned by sysinfo() was too long for
 *		  local variables
 *	char *	- pointer to a string containing the default implementation
 * Status:
 *	public
 */
char *
get_default_inst(void)
{
	int	i;
	char	*envp;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_default_inst");
#endif

	if (default_inst[0] == '\0') {
		if ((envp = getenv("SYS_INST")) != NULL) {
			if ((int)strlen(envp) >= ARCH_LENGTH)
				return (NULL);
			else
				(void) strcpy(default_inst, envp);
		} else  {
			i = sysinfo(SI_ARCHITECTURE, default_inst, ARCH_LENGTH);
			if (i < 0 || i > ARCH_LENGTH)
				return (NULL);
		}
	}
	return (default_inst);
}

/*
 * get_default_machine()
 *	Returns the default machine type (sun4c, i86pc, etc).
 *	NOTE:	SYS_MACHINE environment variable may override default
 *		return value
 * Parameters:
 *	none
 * Return:
 *	NULL	- the machine returned by sysinfo() was too long for
 *		  local variables
 *	char *	- pointer to a string containing the default machine type
 * Status:
 *	public
 */
char *
get_default_machine(void)
{
	int	i;
	char	*envp;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_default_machine");
#endif
	if (default_machine[0] == '\0') {
		if ((envp = getenv("SYS_MACHINE")) != NULL) {
			if ((int)strlen(envp) >= ARCH_LENGTH)
				return (NULL);
			else
				(void) strcpy(default_machine, envp);
		} else  {
			i = sysinfo(SI_MACHINE, default_machine, ARCH_LENGTH);
			if (i < 0 || i > ARCH_LENGTH)
				return (NULL);
		}
	}
	return (default_machine);
}

/*
 * get_default_platform()
 *	Returns the platform name of the machine on which the program is
 *	executing.
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to a string containing the default platform.
 * Status:
 *	public
 */
char *
get_default_platform(void)
{
	int	l;
	char	*envp;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_default_platform");
#endif

	if (!default_platform_set) {
		if ((envp = getenv("SYS_PLATFORM")) != NULL) {
			if ((int)strlen(envp) >= PLATFORM_LENGTH)
				default_platform[0] = '\0';
			else
				(void) strcpy(default_platform, envp);
		} else  {
			l = sysinfo(SI_PLATFORM, default_platform,
			    PLATFORM_LENGTH);
			if (l < 0 || l > PLATFORM_LENGTH)
				default_platform[0] = '\0';
			default_platform_set = 1;
		}
	}

	return (default_platform);
}

/*
 * get_actual_platform()
 *	Returns the actual platform name of the machine on which the
 * 	program is executing. This function reads the openprom to determine
 *	the actual platform name, because currently there is no other way
 *	in which to obtain that information. This may be changed in the
 *	future.
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to a string containing the default platform.
 * Status:
 *	public
 */
char *
get_actual_platform(void)
{
	Oppbuf			oppbuf;
	struct openpromio	*opp = &(oppbuf.opp);
	int			fd, error = 0;
	char			*envp, *cp;


#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_actual_platform");
#endif

	if (!actual_platform_set) {
		if ((envp = getenv("SYS_PLATFORM")) != NULL) {
			if ((int)strlen(envp) >= PLATFORM_LENGTH)
				actual_platform[0] = '\0';
			else
				(void) strcpy(actual_platform, envp);
		} else if ((fd = open("/dev/openprom", O_RDONLY)) >= 0 &&
		    _is_openprom(fd) != 0) {
			(void) memset(oppbuf.buf, 0, PROMBUFSIZE);
			opp->oprom_size = MAXVALSIZE;

			if (ioctl(fd, OPROMNEXT, opp) < 0) {
				perror("ioctl(OPROMNEXT)");
				actual_platform[0] = '\0';
				error = 1;
			}

			(void) strcpy(opp->oprom_array, "name");
			opp->oprom_size = MAXVALSIZE;

			if (!error && ioctl(fd, OPROMGETPROP, opp) < 0) {
				perror("ioctl(OPROMGETPROP)");
				actual_platform[0] = '\0';
				error = 1;
			}

			if (! error) {
				/*
				 * Crush filesystem-awkward characters. See
				 * PSARC/1992/170. (Convert the property to
				 * a sane directory name in UFS)
				 */
				for (cp = opp->oprom_array; *cp; cp++)
					if (*cp == '/' || *cp == ' ' ||
					    *cp == '\t')
						*cp = '_';

				(void) strcpy(actual_platform,
				    opp->oprom_array);

				if (opp->oprom_size < 0 ||
				    opp->oprom_size > PLATFORM_LENGTH)
					actual_platform[0] = '\0';
				actual_platform_set = 1;
			}
		} else
			error = 1;

		if (error)
			/*
			 * If there was any type of error, we will just
			 * return the value from sysinfo. This will at least
			 * be what the kernel thinks the platform is.
			 */
			(void) strcpy(actual_platform,
			    get_default_platform());
	}

	return (actual_platform);
}

/*
 * get_prom_revision
 *	Returns the version string representing the
 *	underlying firmware version of the prom.
 *	NOTE:	SYS_PROM environment variable may override default
 *		return value
 *
 * Parameters:
 *	none
 * Return:
 *	NULL	- unable to determine prom version
 *	char *	- pointer to a string containing the version string
 * Status:
 *	public
 */
char *
get_prom_revision(void)
{
	struct openpromio	*opp;
	int			fd;
	char			*envp, *ver_start, *ver_end;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_prom_revision");
#endif

	/* if we've been here, no need to figure it out again */
	if (prom_revision[0] != '\0') {
		if (prom_revision[0] == 'b')
			return (NULL);
		return (prom_revision);
	}

	/*
	 * environment variable override
	 */
	if ((envp = getenv("SYS_PROM")) != NULL) {
		strncpy(prom_revision, envp, OPROMMAXPARAM);
		return (prom_revision);
	}

	/* open the prom device */
	if ((fd = open("/dev/openprom", O_RDONLY)) <= 0)
		return (NULL);

	if (!_is_openprom(fd))
		goto bad;

	/* get prom version string */
	opp = xmalloc(sizeof (struct openpromio) + OPROMMAXPARAM);
	(void) memset(opp, 0, sizeof (struct openpromio) + OPROMMAXPARAM);
	opp->oprom_size = OPROMMAXPARAM;

	/* do the ioctl to get the version string */
	if (ioctl(fd, OPROMGETVERSION, opp) < 0) {
		perror("ioctl(OPROMGETVERSION)");
		goto bad;
	}

	/*
	 * parse the version string, assume the second
	 * token is the version we are interested in
	 */

	/* skip over first token */
	for (ver_start = opp->oprom_array;
	    !isspace(*ver_start) && *ver_start != '\0'; ver_start++)
		;

	/* find start of second token  (the revision string) */
	for (; *ver_start != '\0' && isspace(*ver_start); ver_start++)
		;

	/* fail if we fell off the end of the string */
	if (*ver_start == '\0') {
		goto bad;
	}

	/* find end of second token token */
	for (ver_end = ver_start;
	    *ver_end != '\0' && !isspace(*ver_end); ver_end++)
		;

	if (ver_end != ver_start) {
		*ver_end = '\0';
	}

	/* found it.  copy it into final resting place */
	strncpy(prom_revision, ver_start, ver_end - ver_start);
	prom_revision[ver_end-ver_start] = '\0';
	(void) close(fd);
	return (prom_revision);

bad:
	strcpy(prom_revision, "bad");
	(void) close(fd);
	return (NULL);
}
