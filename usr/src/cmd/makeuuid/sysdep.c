/*
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
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

#pragma ident	"@(#)sysdep.c	1.4	06/02/27 SMI"

#include <stdio.h>
#include "sysdep.h"
#include "etheraddr.h"
#include "flock.h"

/*
 * Name:	get_ethernet_address
 *
 * Description:	Obtains the system ethernet address.
 *
 * Returns:	0 on success, non-zero otherwise.  The system ethernet
 *		address is copied into the passed-in variable.
 */
int
get_ethernet_address(uuid_node_t *node)
{
	char			**ifnames;
	char			*ifname;
	int			i;
	struct ether_addr	addr;
	int			found;

	/*
	 * go get all interface names
	 */
	if (get_net_if_names(&ifnames) != 0) {
		return (-1);
	}

	/*
	 * Assume failure
	 */
	found = -1;

	/*
	 * for each interface, query it through dlpi to get its physical
	 * (ethernet) address
	 */
	if (ifnames != NULL) {
		i = 0;
		while ((ifnames[i] != NULL) && found) {
			ifname = ifnames[i];
			/* Gross hack to avoid getting errors from /dev/lo0 */
			if (strcmp(ifname, LOOPBACK_IF) != 0) {
			    if (dlpi_get_address(ifname, &addr) == 0) {
				ether_copy(&addr, node);
				/*
				 * found one, set result to successful
				 */
				found = 0;
				continue;
			    }
			}
			i++;
		}
		free_net_if_names(ifnames);
	}

	/*
	 * Couldn't get ethernet address from any interfaces...
	 */
	return (found);
}



/*
 * Name:	get_system_time
 *
 * Description:	system dependent call to get the current system time.
 *		Returned as 100ns ticks since Oct 15, 1582, but
 *		resolution may be less than 100ns.
 *
 * Returns:	None
 */
void
get_system_time(uuid_time_t *uuid_time)
{
	struct timeval tp;

	(void) gettimeofday(&tp, (struct timezone *)0);

	/*
	 * Offset between UUID formatted times and Unix formatted times.
	 * UUID UTC base time is October 15, 1582.
	 * Unix base time is January 1, 1970.
	 */
	*uuid_time = (tp.tv_sec * 10000000) + (tp.tv_usec * 10) +
	    I64(0x01B21DD213814000);
}

/*
 * Name:	get_random_info
 *
 * Description:	system dependent call to generate an amount of random
 *		bits.
 *
 * Returns:	0 on success, non-zero otherwise.  The buffer is filled
 *		with the amount of bytes of random data specified.
 */
int
get_random_info(char *buf, int size)
{
	typedef struct {
		struct timeval t;
		long hostid;
	} randomness;
	randomness r;
	int len;
	(void) gettimeofday(&r.t, (struct timezone *)0);
	r.hostid = gethostid();
	if (sizeof (r) < size) {
		/*
		 * Can't copy correctly
		 */
		return (-1);
	}
	memcpy(buf, &r, size);
	return (0);
}
