/*
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * The copyright in this file is taken from the original
 * Leach & Salz UUID specification, which this implementation
 * is derived from.
 */

/*
 * Copyright (c) 1990- 1993, 1996 Open Software Foundation, Inc.
 * Copyright (c) 1989 by Hewlett-Packard Company, Palo Alto, Ca. &
 * Digital Equipment Corporation, Maynard, Mass.  Copyright (c) 1998
 * Microsoft.  To anyone who acknowledges that this file is provided
 * "AS IS" without any express or implied warranty: permission to use,
 * copy, modify, and distribute this file for any purpose is hereby
 * granted without fee, provided that the above copyright notices and
 * this notice appears in all source code copies, and that none of the
 * names of Open Software Foundation, Inc., Hewlett-Packard Company,
 * or Digital Equipment Corporation be used in advertising or
 * publicity pertaining to distribution of the software without
 * specific, written prior permission.  Neither Open Software
 * Foundation, Inc., Hewlett-Packard Company, Microsoft, nor Digital
 * Equipment Corporation makes any representations about the
 * suitability of this software for any purpose.
 */


/*
 * Module:		main.c
 *
 * Description: 	This module is the starting point for the uuid
 *			generator.  It is responsible for parsing user
 *			options, and calling
 * 			the uuid generator library, and finally printing
 *			the uuid generated.
 */

#include <stdio.h>
#include <stdlib.h>
#include <sys/varargs.h>
#include <libintl.h>
#include <locale.h>

#include "uuid.h"
#include "uuid_strings.h"

#define	DEFAULT_ROOT		"/"
#define	STATE_LOCATION		"var/sadm/system/uuid_state"
#define	ROOT_ENV		"PKG_INSTALL_ROOT"

#ifndef	PROG_NAME
#define	PROG_NAME		"makeuuid"
#endif

/*
 * Local functions
 */
static	int	_scan_node(const char *, uuid_node_t *);
static	int	_generate_uuid(int, char *, char *);
static	int	_generate_uuid(int, char *, char *);

/*
 * Function:	main
 *
 * Description:	Main entry point.  Parses options and calls uuid library to
 *		generate library
 *
 * Returns:    	0 on success, non-zero otherwize
 */
int
main(int argc, char **argv)
{
	int		c = 0;
	char		*user_node_string = NULL;
	char		*root_str = NULL;
	int		cnt = 1;

	setlocale(LC_ALL, "");
	textdomain(TEXT_DOMAIN);

	while ((c = getopt(argc, argv, "n:e:R:")) != EOF) {
		switch (c) {
		case 'e':
			/* alternate ethernet address */
			user_node_string = optarg;
			break;

		case 'n':
			/* number of uuid's to generate */
			cnt = atoi(optarg);
			if (cnt <= 0) {
				progerr(UUID_INVALID_COUNT, optarg);
				return (-1);
			}
			break;

		case 'R':
			/* Alternate root */
			root_str = optarg;
			break;
		default:
			progerr(UUID_USAGE, optarg);
			return (-1);
		}
	}

	if (root_str == NULL) {
		root_str = getenv(ROOT_ENV);
	}

	if (root_str == NULL) {
		root_str = DEFAULT_ROOT;
	}

	return (_generate_uuid(cnt, user_node_string, root_str));
}

/*
 * --------------------------- Local functions -----------------------
 */

/*
 * Name:		_scan_node
 *
 * Description:	Parses a string, looking for a valid ethernet address of the
 * 		form xx:xx:xx:xx:xx:xx, which each xx is a hexidecimal octet.
 *
 * Returns:	0 on success, non-zero otherwise
 */
static int
_scan_node(const char *user_node_string, uuid_node_t *node)
{
	unsigned int	elements[6];
	int		i;

	if (sscanf(user_node_string, "%2x:%2x:%2x:%2x:%2x:%2x",
	    &elements[0],
	    &elements[1],
	    &elements[2],
	    &elements[3],
	    &elements[4],
	    &elements[5]) != 6) {
		return (-1);
	}

	for (i = 0; i < 6; i++) {
		node->nodeID[i] = (uint8_t)(elements[i] & 0xff);
	}
	return (0);
}

/*
 * Name:		_generate_uuid
 *
 * Description:	Actually generates a uuid based on the supplied root
 *		(used to find the statefile) and the node address, in the form
 * 		form xx:xx:xx:xx:xx:xx, which each xx is a hexidecimal octet.
 *		For each uuid generated, it prints it out.
 * Returns:	0 on success, non-zero otherwise
 */
static int
_generate_uuid(int count, char *user_node_string, char *root_str)
{
	char			*name = NULL;
	int			namelen;
	int			result;
	int			i;
	uuid_node_t		user_node;
	uuid_t			*u;
	uuid_node_t		*user_node_p;

	/*
	 * length of location:
	 *
	 * root + "/" + location + trailing \0
	 */
	namelen = strlen(root_str); /* root */
	namelen++;  /* first "/" */
	namelen += strlen(STATE_LOCATION); /* location */
	namelen++; /* trailing \0 */

	name = (char *)malloc(namelen * sizeof (char));

	if (name == NULL) {
		progerr(UUID_NO_MEM);
		return (1);
	}

	(void) sprintf(name, "%s/%s", root_str, STATE_LOCATION);

	/*
	 * Parse user-supplied node
	 */
	if (user_node_string != NULL) {
		if (_scan_node(user_node_string, &user_node) != 0) {
			progerr(UUID_BAD_ETHERNET);
			return (-1);
		}
	}

	/*
	 * Allocate return array
	 */
	u = (uuid_t *)malloc(count * sizeof (uuid_t));
	if (u == NULL) {
		progerr(UUID_NO_MEM);
		return (1);
	}

	/*
	 * If user supplied node, we will pass that into uuid_create.
	 * Otherwise,
	 * pass NULL indicating the system should be queried for the address
	 */
	if (user_node_string != NULL) {
		user_node_p = &user_node;
	} else {
		user_node_p = NULL;
	}

	/*
	 * Make the call to fill in the return array with the
	 * specified # of uuid's
	 */
	result = uuid_create(u, count, user_node_p, name);

	/*
	 * print them out to stdout
	 */
	if (result == 0) {
		for (i = 0; i < count; i++) {
			uuid_print(u[i]);
		}
	}

	/*
	 * Done, free and return
	 */
	free(u);
	free(name);
	return (result);
}

/*
 * Name:		progerr
 *
 * Description:		Prints, on stderr, the specified message,
 *			followed by a newline.
 *
 * Returns:		None.
 */
void
progerr(char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);

	(void) fprintf(stderr, UUID_ERROR, PROG_NAME);

	(void) vfprintf(stderr, fmt, ap);

	va_end(ap);

	(void) fprintf(stderr, "\n");

}
