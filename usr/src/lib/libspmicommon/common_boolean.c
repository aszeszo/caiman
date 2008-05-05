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


/*
 * Module:	common_boolean.c
 * Group:	libspmicommon
 * Description:	This module contains common utilities used by
 *		all spmi applications to determine if a given
 *		object is in an expected configuration.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/openpromio.h>
#include <sys/param.h>
#include <sys/types.h>

#include "spmicommon_lib.h"

/* constants and macros */

#define MAXPROPSIZE     128
#define MAXVALSIZE      (4096 - MAXPROPSIZE - sizeof (u_int))
#define PROPBUFSIZE     (MAXPROPSIZE + MAXVALSIZE + sizeof (u_int))

/* data structures */

typedef union {
        char	buf[PROPBUFSIZE];
        struct openpromio       opp;
} OpenProm;

typedef struct {
        char    device[MAXNAMELEN];
        char    targets[32];
} PromParam;

/* public prototypes */

int		IsIsa(char *);
int		is_allnums(char *);
int		is_disk_name(char *);
int		is_hex_numeric(char *);
int		is_hostname(char *);
int		is_ipaddr(char *);
int		is_numeric(char *);
int		_is_openprom(int);
int		is_slice_name(char *);
int		is_part_name(char *);
int		begins_with(char *, char *);
int		ci_begins_with(char *, char *);

/*---------------------- public functions -----------------------*/

/*
 * Function:	is_allnums
 * Description:	Check if a string syntactically represents a decimal
 *		number sequence.
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid numeric sequence
 *      	1	- valid numeric sequence
 */
int
is_allnums(char *str)
{
	if (str == NULL || *str == '\0')
		return (0);

	if (str && *str) {
		for (; *str; str++) {
			if (isdigit(*str) == 0)
				return (0);
		}
	}

	return (1);
}

/*
 * Function:	is_disk_name
 * Description:	Check if a string syntactically represents a cannonical
 *		disk name (e.g. c0t0d0).
 *		For World Wide name, just make sure that it is not a slice
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid disk name syntax
 *		1       - valid disk name syntax
 */
int
is_disk_name(char *str)
{
	/* validate parameters */
	if ((str == NULL) || (strlen(str) <= 2))
		return (0);

	str = str + strlen(str) - 2 ;
	/*
	 * If it is a slice/part return failure
	 */
	if ((*str == 's' || *str == 'p') && (isdigit(*++str)))
		return(0);
	return (1);
}

/*
 * Function:	is_hex_numeric
 * Description:	Check if a string syntactically represents a hexidecimal
 *		number sequence.
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid hexidecimal digit sequence
 *		1       - valid hexidecimal digit sequence
 */
int
is_hex_numeric(char *str)
{
	if (str == NULL || *str == '\0')
		return (0);

	if (strlen(str) > 2U && *str++ == '0' && strchr("Xx", *str)) {
		for (++str; *str; str++) {
			if (!isxdigit(*str))
				return (0);
		}

		return (1);
	}

	return (0);
}

/*
 * Function:	is_hostname
 * Description:	Check if a string syntactically represents a host name
 *		conforming to the RFC 952/1123 specification.
 * Scope:	public
 * Parameters:	str	- [RO]
 *			  string to be validated
 * Return:	0       - invalid host name syntax
 *		1       - valid host name syntax
 */
int
is_hostname(char *str)
{
	char	*seg;
	char	*cp;
	int	length;
	char	buf[MAXNAMELEN] = "";

	/* validate parameter */
	if (str == NULL)
		return (0);

	(void) strcpy(buf, str);
	if ((seg = strchr(buf, '.')) != NULL) {
		*seg++ = '\0';
		/* recurse with next segment */
		if (is_hostname(seg) == 0)
			return (0);
	}

	/*
	 * length must be 2 to 63 characters (255 desireable, but not
	 * required by RFC 1123)
	 */
	length = (int) strlen(buf);
	if (length < 2 || length > 63)
		return (0);

	/* first character must be alphabetic or numeric */
	if (isalnum((int) buf[0]) == 0)
			return (0);

	/* last character must be alphabetic or numeric */
	if (isalnum((int) buf[length - 1]) == 0)
		return (0);

	/* names must be comprised of alphnumeric or '-' */
	for (cp = buf; *cp; cp++) {
		if (isalnum((int)*cp) == 0 && *cp != '-')
			return (0);
	}

	return (1);
}

/*
 * Function:	is_ipaddr
 * Description:	Check if a string syntactically represents an Internet
 *		address.
 * Scope:	public
 * Parameters:	str	- [RO]
 *			  string containing textual form of an Internet
 *			  address
 * Return:	0       - invalid address syntax
 *		1       - valid address syntax
 */
int
is_ipaddr(char *str)
{
	int	num;
	char	*p;

	if ((p = strchr(str, '.')) == NULL)
		return (0);
	*p = '\0';
	num = atoi(str);
	if (num < 0 || num > 255 || is_allnums(str) == 0)
		return (0);
	*p = '.';
	str = p + 1;
	if ((p = strchr(str, '.')) == NULL)
		return (0);

	*p = '\0';
	num = atoi(str);
	if (num < 0 || num > 255 || is_allnums(str) == 0)
		return (0);

	*p = '.';
	str = p + 1;

	if ((p = strchr(str, '.')) == NULL)
		return (0);
	*p = '\0';
	num = atoi(str);
	if (num < 0 || num > 255 || is_allnums(str) == 0)
		return (0);
	*p = '.';
	str = p + 1;
	num = atoi(str);
	if (num < 0 || num > 255 || is_allnums(str) == 0)
		return (0);

	return (1);
}

/*
 * Function:	is_numeric
 * Description:	Check a character string and ensure that it represents
 *		either a hexidecimal or decimal number.
 * Scope:	public
 * Parameters:	str	- [RO]
 *			  string to be validated
 * Return:	0       - invalid hex/dec sequence
 *		1       - valid hex/dec sequence
 */
int
is_numeric(char *str)
{
	if (str && *str) {
		if (strlen(str) > 2U &&
				str[0] == '0' && strchr("Xx", str[1])) {
			str += 2;
			while (*str) {
				if (!isxdigit(*str))
					return (0);
				else
					str++;
			}
			return (1);
		} else {
			while (*str) {
				if (!isdigit(*str))
					return (0);
				else
					str++;
			}
			return (1);
		}
	}
	return (0);
}

/*
 * Function:	_is_openprom
 * Description:	Boolean test to see if a device is an openprom device.
 *		The test is based on whether the OPROMGETCONS ioctl()
 *		works, and if the OPROMCONS_OPENPROM bits are set.
 * Scope:	public
 * Parameters:	fd	- [RO]
 *			  open file descriptor for openprom device
 * Return:	0	- the device is not an openprom device
 *		1	- the device is an openprom device
 */
int
_is_openprom(int fd)
{
	OpenProm	  pbuf;
	struct openpromio *opp = &(pbuf.opp);
	u_char		  mask;

	opp->oprom_size = MAXVALSIZE;

	if (ioctl(fd, OPROMGETCONS, opp) == 0) {
		mask = (u_char)opp->oprom_array[0];
		if ((mask & OPROMCONS_OPENPROM) == OPROMCONS_OPENPROM)
			return (1);
	}

	return (0);
}

/*
 * Function:	is_slice_name
 * Description:	Check to see a string syntactically represents a
 *		cannonical slice device name (e.g. c0t0d0s3).
 *		slice names cannot be path names (i.e. cannot contain
 *		any /'s.).
 *
 *		With World wide Name, we cannot check the
 * 		whole string, we will check the last two characters.
 *		They should be in the form 'sX', where X is a digit
 *		between 0 and 7.
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid slice name syntax
 *		1       - valid slice name syntax
 */
int
is_slice_name(char *str)
{
	/* validate parameters */
	if ((str == NULL) || (strlen(str) <= 2))
		return (0);

	if (strchr(str, '/') != NULL) {
		return (0);
	}

	if ((str[strlen(str)-2] == 's') && isdigit(str[strlen(str)-1]))
		return (1);
	else
		return (0);
}

/*
 * Function:	is_device_name
 * Description:	Check to see a string syntactically represents a
 *		device on which a filesystem can be placed
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid slice name syntax
 *		1       - valid slice name syntax
 */
int
is_device_name(char *str)
{
	if (begins_with(str, "/dev/dsk/")) {
		return (is_slice_name(str+strlen("/dev/dsk/")));
	} else {
		return (is_slice_name(str));
	}
}

/*
 * Function:	is_part_name
 * Description:	Check to see a string syntactically represents a
 *		cannonical fdisk partition device name (e.g. c0t0d0p2).
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid partition name syntax
 *		1       - valid partition name syntax
 */
int
is_part_name(char *str)
{
	if (str) {
		must_be(str, 'c');
		skip_digits(str);
		if (*str == 't') {
			str++;
			skip_digits(str);
		}
		must_be(str, 'd');
		skip_digits(str);
		must_be(str, 'p');
		skip_digits(str);
	}

	if (str != NULL && *str == '\0')
		return (1);

	return (0);
}

/*
 * Function:	IsIsa
 * Description:	Boolean function indicating whether the instruction set
 *		architecture of the executing system matches the name provided.
 *		The string must match a system defined architecture (e.g.
 *		"i386", "ppc, "sparc") and is case sensitive.
 * Scope:	public
 * Parameters:	name	- [RO, *RO]
 *		string representing the name of instruction set architecture
 *		being tested
 * Return:	0 - the system instruction set architecture is different from
 *			the one specified
 * 		1 - the system instruction set architecture is the same as the
 *			one specified
 */
int
IsIsa(char *name)
{
	return (streq(get_default_inst(), name) ? 1 : 0);
}

/*
 * Function:	begins_with
 * Description:	Boolean function indicating whether one string starts with
 * 		the characters of a second.
 * Scope:	public
 * Parameters:	str1	- [RO, *RO]
 *			  the first string
 *		str2	- [RO, *RO]
 *			  the second string
 * Return:	0  - the first string does not begin with the characters of the
 * 			second
 *		!0 - the first string begins with the characters of the second
 */
int
begins_with(char *str1, char *str2)
{
	if ((str1 == NULL) || (str2 == NULL)) {
		return (0);
	}

	return (strneq(str1, str2, strlen(str2)));
}

/*
 * Function:	ci_begins_with
 * Description:	Boolean function indicating whether one string starts with
 * 		the characters of a second.  The comparison is case-insensitive.
 * Scope:	public
 * Parameters:	str1	- [RO, *RO]
 *			  the first string
 *		str2	- [RO, *RO]
 *			  the second string
 * Return:	0  - the first string does not begin with the characters of the
 * 			second
 *		!0 - the first string begins with the characters of the second
 */
int
ci_begins_with(char *str1, char *str2)
{
	if ((str1 == NULL) || (str2 == NULL)) {
		return (0);
	}

	return (ci_strneq(str1, str2, strlen(str2)));
}
