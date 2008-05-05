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

#ifndef	_UUID_H
#define	_UUID_H


/*
 * Module:	uuid
 *
 * Description:	This is the top-level interface for generating UUIDs.
 */

#ifdef	__cplusplus
extern "C" {
#endif

#include "sysdep.h"
#include "flock.h"

#include <sys/types.h>

#define	STATE_NODE	(0x01)
#define	STATE_CLOCKSEQ	(0x02)
#define	STATE_TIMESTAMP	(0x04)

/*
 * The uuid type used throughout when referencing uuids themselves
 */
typedef struct {
	uint32_t	time_low;
	uint16_t	time_mid;
	uint16_t	time_hi_and_version;
	uint8_t		clock_seq_hi_and_reserved;
	uint8_t		clock_seq_low;
	uint8_t		node_addr[6];
} uuid_t;

/*
 * data type for UUID generator persistent state
 */
typedef struct {
	uuid_time_t	ts;	/* saved timestamp */
	uuid_node_t	node;	/* saved node ID */
	uint16_t	cs;	/* saved clock sequence */
} uuid_state_t;

/* prototypes */
int	uuid_create(uuid_t *, int, uuid_node_t *, char *);
void	uuid_print(uuid_t);
void	progerr(char *, ...);

#ifdef __cplusplus
}
#endif

#endif /* _UUID_H */
