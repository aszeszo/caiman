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
 * Copyright 2002 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)prodreg_browse_num.c	1.3	06/02/27 SMI"

/*
 * prodreg_browse_num.c
 *
 * The browse number functions provide a persistant mapping from
 * UUIDs to browse numbers, and the reverse.  This is used to
 * make browsing easier from the command line and to display
 * browse information consistently.
 *
 * The implementation uses the "ndbm" database facility.  The
 * browse database is constructed in the /tmp/prodregbrowse####
 * directory, where #### is the UID.  This will provide consistent
 * browsing, at least on a per log in session basis.
 */

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#include <fcntl.h>
#include <ndbm.h>
#include <errno.h>
#include <assert.h>
#include <wsreg.h>
#include "prodreg_cli.h"

#define	NEXT_B	"browsenext"
#define	DBBASEDIR	"/tmp/prodregbrowse%ld"
#define	DBNAME	"/numdb"

#define	BROWSE_UUID_GETERROR	"dbm_store get"
#define	BROWSE_UUID_INIT	"Could not initialize browse number database."

/*
 * Global value:  This is used by the process to access the database.
 *   Since it is a global, and static, the value will be transparent
 *   to other modules.  Note:  This is not thread safe.  If the prodreg
 *   CLI were to become multithreaded, this global variable would have
 *   to be eliminated in favor of a per thread handle to the db.
 */
static DBM *db = NULL;

/*
 * word2ulong
 *
 * Conversion routine.
 *
 *   b    The 4 byte array that has to be deserialized as an uint32_t.
 *
 * Return: uint32_t value corresponding to the 4 bytes in b.
 *
 * Side effects: None.
 */

static uint32_t
word2ulong(const char b[])
{
	uint32_t ul = 0;

	assert(b != NULL);

	ul  = (((uint32_t) 0xff) & b[0]) << 24;
	ul += (((uint32_t) 0xff) & b[1]) << 16;
	ul += (((uint32_t) 0xff) & b[2]) << 8;
	ul += (((uint32_t) 0xff) & b[3]);

	return (ul);
}

/*
 * get_next_bn
 *
 * A wrapper for access to the database which is used to obtain the
 * next incremental browse number from it.
 *
 * Returns: Next browse number.
 *
 * Side effects: None.
 */
static uint32_t
get_next_bn()
{
	datum key = { NEXT_B, sizeof (NEXT_B) };
	datum val = dbm_fetch(db, key);
	if (val.dptr == NULL) {
		return ((uint32_t) 0xffffffff);
	}
	return (word2ulong(val.dptr));
}

/*
 * set_bn
 *
 * This function converts an uint32_t to a buffer which can be
 * stored in the database.  It stores the value under the key supplied.
 *
 *   pc    The key supplied.  This key is a 'UUID' associated with a
 *         registry component.
 *   ul    The uint32_t value of the browse number to associate
 *         with the given browse number.
 *
 * Returns: Nothing.  If the operation fails, the program prints out
 *          a failure message to standard output and exits (fail).
 *
 * Side effects:  The database changes its persistent value.
 */
static void
set_bn(const char *pc, uint32_t ul)
{
	datum key;
	unsigned char buf[4];
	datum val;

	key.dptr  = (void*) pc;
	key.dsize = strlen(pc) + 1;
	val.dptr  = (void*) buf;
	val.dsize = 4;

	/*
	 * The following intentionally read the low order byte of the
	 * 32 bit data into a single 8 byte array.
	 */

	buf[0] = (unsigned char) (0xff & ((0xff000000 & ul) >> 24));
	buf[1] = (unsigned char) (0xff & ((0x00ff0000 & ul) >> 16));
	buf[2] = (unsigned char) (0xff & ((0x0000ff00 & ul) >> 8));
	buf[3] = (unsigned char) (0xff & (0x000000ff & ul));

	if (dbm_store(db, key, val, DBM_REPLACE) != 0) {
		fail(BROWSE_UUID_GETERROR);
	}

}

/*
 * db_open
 *
 * This function opens up the existing database if there is one,
 * or creates a new one, otherwise.  If this function fails, the
 * program will exit, emitting an error message to standard error.
 * (fail).
 *
 * Returns: Nothing.
 *
 * Side effects: This command may create a database.
 */
void
db_open()
{
	char pcName[80];
	int32_t perms = S_IRUSR | S_IWUSR | S_IXUSR;
	int32_t mode  = O_RDWR | O_CREAT | O_EXCL;
	uid_t id;

	/* Prevent this from being called twice per session. */
	if (db != NULL)
		return;

	id = getuid();
	(void) sprintf(pcName, DBBASEDIR, id);
	if (mkdir(pcName, perms) != (int) 0 && errno != (int) EEXIST) {
		return;
	}
	(void *) strcat(pcName, DBNAME);
	/* Create a new database, if none exists. */
	if ((db = dbm_open(pcName, mode, perms)) == NULL) {
		/* Open an existing database. */
		db = dbm_open(pcName, (int32_t) O_RDWR, perms);
		if (db == NULL) {
			fail(BROWSE_UUID_INIT);
		}
	} else {
		set_bn(NEXT_B, 0);
		assert(get_next_bn() == 0);
	}
}

/*
 * db_close
 *
 * This wraps the dbm_close routine.  The caller has no access to the
 * implementation of the dbm - so this is the only way that the db
 * can be closed.
 *
 * Returns: None
 *
 * Side effects: Will close the global ndbm database handle.
 */
void
db_close()
{
	dbm_close(db);
	db = NULL;
}

/*
 * get_bn
 *
 *   db      The database for the uuid to browse # mappings.
 *   pcuuid  The uuid to map.
 *
 * Return value: A new browse #.
 *
 * Side effects: If the uuid does not yet have a number,
 *               one will be assigned.
 */
uint32_t
get_bn(char *pcuuid)
{
	datum key, val;
	uint32_t ul = 0;

	key.dptr = pcuuid;
	key.dsize = strlen(pcuuid)+1;
	val = dbm_fetch(db, key);

	if (val.dptr == NULL) {

		ul = get_next_bn();
		ul++;

		/* Save the next value, to increment from and use. */
		set_bn(NEXT_B, ul);

		/* Associate this value with the uuid passed in. */
		set_bn(pcuuid, ul);

	} else {

		ul = word2ulong(val.dptr);

	}

	return (ul);

}

/*
 * getUUIDbyBrowseNum
 *
 *   Search the db for a uuid corresponding to the browse number.
 *
 * Parameters:
 *
 *   bn      Browse number
 *
 * Returns:  UUID string or NULL if browse # not found.
 *           If anything is returned,  the caller must free it with free().
 *
 * Side effects:  None.
 */
char *
getUUIDbyBrowseNum(uint32_t ul)
{
	datum key, val;
	uint32_t uld;
	char *pc = NULL;

	for (key = dbm_firstkey(db);
		key.dptr != NULL;
		key = dbm_nextkey(db)) {

		val = dbm_fetch(db, key);
		if (val.dsize != 4) {
			/* this record is not a browse number. */
			continue;
		}
		if (memcmp(key.dptr, NEXT_B, key.dsize) == 0) {
			/* This record is the browse # 'next' value. */
			continue;
		}

		uld = word2ulong(val.dptr);

		if (uld == ul) {
			pc = (char *) malloc((size_t) (key.dsize + 1L));
			if (pc == NULL) fail(PRODREG_MALLOC);
			pc[key.dsize] = '\0';
			(void *) memcpy(pc, key.dptr, (size_t) key.dsize);
			break;
		}
	}
	return (pc);
}
