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

#ifndef	_SYSDEP_H
#define	_SYSDEP_H

#pragma ident	"@(#)sysdep.h	1.3	06/02/27 SMI"

/*
 * Module:	sysdep
 *
 * Description:	This is the system-dependent interface for doing
 *		system-dependent things.  Conceiviably, a different
 *		module for different systems could be plugged in here,
 *		and the uuid generator can then run on the other
 *		platforms.
 */

#ifdef	__cplusplus
extern "C" {
#endif

#include <sys/types.h>

/*
 * The number of 100ns ticks of the actual
 * resolution of the system clock
 */
#define	UUIDS_PER_TICK	1024
#define	I64(C)		C##LL


typedef uint64_t	uuid_time_t;

typedef struct {
	uint8_t		nodeID[6];
} uuid_node_t;

int	get_ethernet_address(uuid_node_t *);
void	get_system_time(uuid_time_t *_time);
int	get_random_info(char *, int);

#ifdef __cplusplus
}
#endif

#endif /* _SYSDEP_H */
