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
 * Module:		uuid.c
 *
 * Description:		This module is the workhourse for generating abstract
 *			UUIDs.  It delegates system-specific tasks (such
 *			as obtaining the node identifier or system time)
 *			to the sysdep module.
 */

#include "uuid.h"
#include "uuid_strings.h"
#include <sys/stat.h>
#include <stdio.h>
#include <fcntl.h>
#include <libintl.h>
#include <locale.h>


/*
 * Local volatile state
 */
static	uuid_state_t	vol_state;

/*
 * local functions
 */
static	int		_verify(char *);
static	int		_lock_state(char *);
static	int		_unlock_state(int);
static	int		_read_state(char *, uint16_t *,
    uuid_time_t *,
    uuid_node_t *);
static	void		_write_state(char *, uint16_t, uuid_time_t,
    uuid_node_t);
static	void 		_format_uuid(uuid_t *, uint16_t, uuid_time_t,
    uuid_node_t);
static	void		_get_current_time(uuid_time_t *);
static	uint16_t	_get_random(void);

/*
 * Name:		uuid_create.
 *
 * Description:	Generates a uuid, given a node address. If the
 *		node address is NULL, one is generated (either by querying
 *		the system, or generating a random one).
 *
 * Returns:	0 on success, non-zero otherwise
 */
int
uuid_create(uuid_t *uuids, int count, uuid_node_t *user_node, char *loc)
{
	uuid_time_t	timestamp, last_time;
	uint16_t	clockseq;
	uuid_node_t	last_node;
	uuid_node_t	system_node;
	int		result, rtn, i, locked_state_fd;
	char		*seed;
	uuid_t		uuid;


	rtn = 0;
	/*
	 * acquire system wide lock so we're alone
	 */
	locked_state_fd = _lock_state(loc);

	if (locked_state_fd < 0) {
		/*
		 * coulnd't create and/or lock state, must not have access
		 */
		progerr(UUID_NOLOCK, loc);
		return (-1);
	}

	/*
	 * Generate as many uuid's as requested, filling in
	 * passed-in array
	 */
	for (i = 0; i < count; i++) {

		/*
		 * get current time
		 */
		_get_current_time(&timestamp);

		/*
		 * get saved state from NV storage (doesn't actuall
		 * read every time from disk to increase performance)
		 */
		result = _read_state(loc, &clockseq, &last_time, &last_node);

		/*
		 * Attempt to read real system node if user did not specify one
		 */
		if (user_node == NULL) {
			if (get_ethernet_address(&system_node) != 0) {
				/*
				 * couldn't get system node, bail
				 */
				progerr(UUID_NOETHERNET);
				rtn = -1;
				break;
			}
		} else {
			system_node = *user_node;
		}

		if ((result & STATE_CLOCKSEQ) == 0) {
			/*
			 * couldn't read clock sequence.
			 * must generate a random one
			 */
			clockseq = _get_random();
		}

		if ((result & STATE_TIMESTAMP) != 0) {
			/*
			 * *could* read last timestamp.  If it's
			 * in the future, or the node address has
			 * changed, increment clock sequence.
			 */
			if (((result & STATE_CLOCKSEQ) != 0) &&
			    ((last_time > timestamp) ||
				(memcmp(&system_node,
				    &last_node,
				    sizeof (uuid_node_t)) != 0))) {
				clockseq++;
			}
		}

		/*
		 * stuff fields into the UUID
		 */
		_format_uuid(&uuid, clockseq, timestamp, system_node);

		/*
		 * save the state for next time.  (doesn't actually
		 * write to disk every time).
		 */
		_write_state(loc, clockseq, timestamp, system_node);

		uuids[i] = uuid;

	} /* end of 'count' loop */

	/*
	 * Unlock system-wide lock
	 */
	(void) _unlock_state(locked_state_fd);

	/*
	 * Done!
	 */
	return (rtn);
}

/*
 * Name:	_format_uuid
 *
 * Description: Formats a UUID, given the clock_seq timestamp,
 * 		and node address.  Fills in passed-in pointer with
 *		the resulting uuid.
 *
 * Returns:	None.
 */
static void
_format_uuid(uuid_t *uuid, uint16_t clock_seq,
    uuid_time_t timestamp, uuid_node_t node)
{

	/*
	 * First set up the first 60 bits from the timestamp
	 */
	uuid->time_low = (uint32_t)(timestamp & 0xFFFFFFFF);
	uuid->time_mid = (uint16_t)((timestamp >> 32) & 0xFFFF);
	uuid->time_hi_and_version = (uint16_t)((timestamp >> 48) &
	    0x0FFF);

	/*
	 * This is version 1, so say so in the UUID version field (4 bits)
	 */
	uuid->time_hi_and_version |= (1 << 12);

	/*
	 * Now do the clock sequence
	 */
	uuid->clock_seq_low = clock_seq & 0xFF;

	/*
	 * We must save the most-significant 2 bits for the reserved field
	 */
	uuid->clock_seq_hi_and_reserved = (clock_seq & 0x3F00) >> 8;

	/*
	 * The variant for this format is the 2 high bits set to 10,
	 * so here it is
	 */
	uuid->clock_seq_hi_and_reserved |= 0x80;

	/*
	 * write result to passed-in pointer
	 */
	(void) memcpy(&uuid->node_addr, &node, sizeof (uuid->node_addr));
}

/*
 * Name:	_read_state
 *
 * Description: Reads non-volatile state from a (possibly) saved statefile.
 * 		For each non-null pointer passed-in, the corresponding
 *		information from the statefile is filled in.
 *		the resulting uuid.
 *
 * Returns:	A 'OR' combination of STATE_TIMESTAMP, STATE_CLOCKSEQ,
 *		and STATE_NODE indicating which pieces of information
 *		were successfully read from the non-volatile state.
 */
static int
_read_state(char *loc, uint16_t *clockseq,
    uuid_time_t *timestamp, uuid_node_t *node)
{
	struct stat	statbuf;
	FILE		*stream;
	static int	already_read_state = 0;
	int		fd;


	if (!already_read_state) {
		fd = open(loc, O_RDONLY);
		if (fd < 0) {
			return (0);
		}

		if (fstat(fd, &statbuf) != 0) {
			return (0);
		}

		/*
		 * If size is unexpected, don't use as state
		 */
		if (statbuf.st_size != sizeof (uuid_state_t)) {
			return (0);
		}

		/*
		 * Ok, this file will work, let's read it and
		 * get it's data
		 */
		stream = fdopen(fd, "rb");

		if (fread(&vol_state, sizeof (uuid_state_t), 1, stream) != 1) {
			/*
			 * invalid state!
			 */
			close(fd);
			return (0);
		}
		close(fd);
		already_read_state = 1;
	}

	if (node != NULL) {
		*node = vol_state.node;
	}

	if (timestamp != NULL) {
		*timestamp = vol_state.ts;
	}

	if (clockseq != NULL) {
		*clockseq = vol_state.cs;
	}

	return (STATE_NODE|STATE_CLOCKSEQ|STATE_TIMESTAMP);
}


/*
 * Name:	_write_state
 *
 * Description: Writes non-volatile state from the passed-in information.
 *
 * Returns:	0 on sucess, non-zero otherwise.  The statefile is not
 *		close()'d.
 */
static void
_write_state(char *loc, uint16_t clockseq,
    uuid_time_t timestamp, uuid_node_t node)
{
	int			fd;
	FILE			*fd_stream;
	static int		initted = 0;
	static uuid_time_t	next_save;

	if (!initted) {
		next_save = timestamp;
		initted = 1;
	}
	/* always save state to volatile shared state */
	vol_state.cs = clockseq;
	vol_state.ts = timestamp;
	vol_state.node = node;

	if (timestamp >= next_save) {
		fd = open(loc, O_RDWR);

		/*
		 * seek to beginning of file
		 */
		(void) lseek(fd, 0, SEEK_SET);

		/*
		 * Write out data
		 */
		fd_stream = fdopen(fd, "wb");
		(void) fwrite(&vol_state, sizeof (uuid_state_t), 1, fd_stream);

		/*
		 * Do not close file.. we didn't open it
		 */

		/* schedule next save for 10 seconds from now */
		next_save = timestamp + (10 * 10 * 1000 * 1000);
	}
}

/*
 * Name:	_get_current_time
 *
 * Description:	get-current_time -- get time as 60 bit 100ns ticks
 *		since the beginning of unix time.
 *		Compensate for the fact that real clock resolution is
 *		less than 100ns.
 *
 * Returns:	None.
 *
 */
void
_get_current_time(uuid_time_t *timestamp)
{
	uuid_time_t		time_now;
	static uuid_time_t	time_last;
	static uint16_t		uuids_this_tick;
	static int		initted = 0;
	int			done;

	if (!initted) {
		get_system_time(&time_now);
		uuids_this_tick = UUIDS_PER_TICK;
		initted = 1;
	}
	done = 0;
	while (!done) {
		get_system_time(&time_now);

		/*
		 * if clock reading changed since last UUID generated...
		 */
		if (time_last != time_now) {
			/*
			 * reset count of uuids generatedd with
			 * this clock reading
			 */
			uuids_this_tick = 0;
			done = 1;
		}
		if (uuids_this_tick < UUIDS_PER_TICK) {
			uuids_this_tick++;
			done = 1;
		}
		/*
		 * going too fast for our clock; spin
		 */
	}
	/*
	 * add the count of uuids to low order bits of the clock reading
	 */
	*timestamp = time_now + uuids_this_tick;
}

/*
 * Name:	_get_random
 *
 * Description:	Gets random bits of information.  Uses rand(), which
 *		admittedly isn't very secure.
 *
 * Returns:	16 bits of random information.
 *
 */
static uint16_t
_get_random(void)
{
	static int	initted = 0;
	uuid_time_t	time_now;
	unsigned	seed;

	if (!initted) {
		get_system_time(&time_now);
		time_now = time_now/UUIDS_PER_TICK;
		seed = (unsigned)(((time_now >> 32) ^ time_now)&0xffffffff);
		srand(seed);
		initted = 1;
	}

	return (rand());
}




/*
 * Name:	_uuid_print
 *
 * Description:	Prints a nicely-formatted uuid to stdout.
 *
 * Returns:	None.
 *
 */
void
uuid_print(uuid_t u)
{
	int i;

	(void) printf("%8.8lx-%4.4x-%4.4x-%2.2x%2.2x-", u.time_low, u.time_mid,
	    u.time_hi_and_version, u.clock_seq_hi_and_reserved,
	    u.clock_seq_low);
	for (i = 0; i < 6; i++)
		(void) printf("%2.2x", u.node_addr[i]);
	(void) printf("\n");
}

/*
 * Name:	_lock_state
 *
 * Description:	Locks down the statefile, by first creating the file
 *		if it doesn't exist, then locking it using the system
 *		file locking protocol.
 *
 * Returns:	A non-negative file descriptor referring to the locked
 *		state file, if it was able to be created and/or locked,
 *		or -1 otherwise.
 */
static int
_lock_state(char *loc)
{
	int fd;
	/*
	 * create the file if it doesn't exist
	 */
	fd = open(loc, O_RDWR|O_CREAT|O_EXCL, S_IRUSR|S_IWUSR|S_IXUSR);
	if (fd < 0) {
		/*
		 * If this fails, we weren't able to create the file.
		 * Either we don't have access to make the file, or
		 * the file already existed.  Try and open it without
		 * creating it.  If we don't have access, this will
		 * fail as well.
		 */
	    fd = open(loc, O_RDWR);
	}

	if (fd < 0) {
	    return (-1);
	}

	/*
	 * try and lock it, blocking if necessary
	 */
	if (file_lock(fd, F_WRLCK, 1) == -1) {
		/*
		 * File could not be locked, bail
		 */
		return (-1);
	}

	return (fd);
}

/*
 * Name:	_unlock_state
 *
 * Description:	Unlocks a locked statefile, and close()'s the file.
 *
 * Returns:	0 on success, non-zero otherwise.
 */
static int
_unlock_state(int fd)
{
	int rtn;

	rtn = 0;
	rtn |= file_unlock(fd);
	rtn |= close(fd);
	return (rtn);
}
