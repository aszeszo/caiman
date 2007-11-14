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

#pragma ident	"@(#)svc_updateserial.c	1.6	07/10/09 SMI"


/*
 * Module:	svc_updateserial.c
 * Group:	libspmisvc
 * Description:	This module is responsible for updating the serial
 *		number for Intel systems.
 */

#include <elf.h>
#include <libelf.h>
#include <fcntl.h>
#include <utime.h>
#include <unistd.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/systeminfo.h>
#include <sys/time.h>
#include <sys/types.h>
#include "spmisvc_lib.h"

/* internal prototypes */

int		_setup_hostid(void);

/* private prototypes */

static int		setser(char *);
static int		patchser_64(char *, char *);
static int		get_serial32(char *, int32_t *, int32_t *);
static int		set_serial64(char *, int32_t, int32_t);

/* constants */

/*
 * These two definitions MUST follow the same definitions as found in
 * the ON consolidation in usr/src/uts/common/io/sysinit.c.  If that
 * file changes, so must this one.
 */
#define	HOSTID_SYMBOL	"t"
#define	V1		0x38d4419a

#define	A	16807
#define	M	2147483647
#define	Q	127773
#define	R	2836
#define	x()	if ((s = ((A*(s%Q))-(R*(s/Q)))) <= 0) s += M

/* ---------------------- public functions ----------------------- */

/*
 * Function:	_setup_hostid
 * Description:	Set the hostid on any system supporting the i386 model of
 *		hostids.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	- set successful
 *		ERROR	- set failed
 */
int
_setup_hostid(void)
{
	char	buf[32] = "";
	char	orig[64] = "";
	char	path32[MAXPATHLEN] = "";
	char	path64[MAXPATHLEN] = "";

	/* cache client hostids are set by hostmanager */
	if (get_machinetype() == MT_CCLIENT)
		return (NOERR);

	/* take no action when running dry-run */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	(void) sprintf(orig, "/tmp/root%s", IDKEY);
	(void) sprintf(path32, "%s%s", get_rootdir(), IDKEY);
	(void) sprintf(path64, "%s%s", get_rootdir(), IDKEY64);

	/* only set if the original was not saved */
	if (access(path32, F_OK) == 0) {
		if (access(orig, F_OK) < 0 &&
			(sysinfo(SI_HW_SERIAL, buf, 32) < 0 ||
				buf[0] == '0')) {
			if (setser(path32) < 0) {
				return (ERROR);
			}
		}	
		/*
	 	 * Get the hostid from 32-bit sysinit module and set it 
	 	 * to 64-bit sysinit module so that both 32-bit and
		 * 64-bit hostid are same
	 	 */
		if (access(path64, F_OK) == 0) {
			if (patchser_64(path32, path64) < 0) {
				return (ERROR);
			}
		}
	}

	return (NOERR);
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	setser
 * Description: Generate a hardware serial number in the range 1 to (10**9-1)
 *		and sets appropriate constants in the sysinit module with name
 *		fn.  Uses elf(3ELF) libraries.
 * Scope:	private
 * Parameters:	fn	- module file name
 * Return:	ERROR	- couldn't generate serial number
 *		NOERROR - could
 */
static int
setser(char *fn)
{
	struct timeval tv;
	struct stat statbuf;
	struct utimbuf utimbuf;
	int rc, fd, count, i;
	Elf *elf;
	Elf_Scn *scn;
	Elf_Scn *dscn;
	Elf32_Ehdr *ehdr;
	Elf32_Shdr *dscnhdr;
	Elf32_Shdr *shdr;
	Elf32_Sym *sym;
	Elf_Data *data;
	char *dbuf = NULL;
	Elf_Data *elfdata;
	int32_t s;
	int32_t ver;
	char *symname;
	int32_t t[3];

	/* open the module file */
	if ((fd = open(fn, O_RDWR)) < 0)
		return (ERROR);

	/* get file status for times */
	if (fstat(fd, &statbuf) < 0)
		goto out;

	/* open the ELF */
	elf_version(EV_CURRENT);
	elf = elf_begin(fd, ELF_C_RDWR, (Elf *)0);
	if (elf == NULL)
		goto out;

	/* find the symbol table */
	scn = NULL;
	ehdr = elf32_getehdr(elf);
	while ((scn = elf_nextscn(elf, scn)) != NULL) {
		shdr = elf32_getshdr(scn);
		if (shdr->sh_type == SHT_SYMTAB) {
			/* found the symbol table, so lets go search it. */
			break;
		}
	}

	if (scn == NULL) {
		/* no symbol table, so silently bail */
		goto elfout;
	}

	/* how many symbols in the symbol table */
	data = elf_getdata(scn, NULL);
	count = shdr->sh_size / shdr->sh_entsize;

	/* find the super-secret symbol we are looking for */
	for (i = 0; i < count; ++i) {
		sym = (Elf32_Sym *)((char *)data->d_buf +
		    (i * sizeof (Elf32_Sym)));
		symname = elf_strptr(elf, shdr->sh_link, sym->st_name);
		if (symname == NULL) {
			/* ignore null symbols */
			continue;
		}
		if (strcmp(symname, HOSTID_SYMBOL) == 0) {
			/*
			 * We found the right symbol.
			 * Now go find the section it's in.
			 */
			dscn = elf_getscn(elf, sym->st_shndx);

			/* Now find its header */
			dscnhdr = elf32_getshdr(dscn);

			/* Finally find the section contents (dbuf) */
			elfdata = elf_getdata(dscn, NULL);
			dbuf = (char *)elfdata->d_buf;

			/*
			 * dbuf + symbol offset points to the version
			 * identifier
			 */
			ver = *((uint32_t *)(dbuf+sym->st_value));

			/*
			 * Version must match the super-secret one we
			 * are expecting
			 */
			if (ver != (uint32_t)V1) {
				goto elfout;
			}
			break;
		}
	}

	if (dbuf == NULL) {
		/* didn't find the symbol, bail */
		goto elfout;
	}

	/* generate constants and serial number */
	(void) gettimeofday(&tv, (void *)NULL);
	s = tv.tv_sec + tv.tv_usec - (22*365*24*60*60);
	do {
		x();
		t[1] = s;
		x();
		t[2] = s;
		x();
		s %= 1000000000;
	} while (s == 0);

	/* store constants */
	*(((uint32_t *)dbuf) + 1) = t[1];
	*(((uint32_t *)dbuf) + 2) = t[2];

	/* ensure that the memory image of the ELF file is complete */
	elf_update(elf, ELF_C_NULL);
	elf_update(elf, ELF_C_WRITE);   /* update ELF file on disk */
	elf_end(elf);
	(void) close(fd);

	/* restore file access and modification times */
	utimbuf.actime = statbuf.st_atime;
	utimbuf.modtime = statbuf.st_mtime;
	if (utime(fn, &utimbuf) < 0)
		return (ERROR);

	return (NOERR);	/* return success */

elfout:	elf_end(elf);

	/* close file and return error code */
out:    (void) close(fd);
	return (ERROR);

}

/*
 * function:	patchser_64 
 * Description:	Get the serial number (hostid) from the 32-bit sysinit
 *		module and patch the 64-bit sysinit module
 * Scope:	private
 * Parameters:	src	- Source module file name
		dst	- Destnation module file name
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
patchser_64(char *src, char *dst)
{
	int32_t l1, l2;

	if (get_serial32(src, &l1, &l2) == NOERR) {
		if (set_serial64(dst, l1, l2) == NOERR) {
			return (NOERR);
		}
	}
	return (ERROR);
}

/*
 * function:	get_serial32
 * Description:	Get the serial number from 32-bit sysinit module
 *		This has been populated either with the serial number from
 *		the OS instance on the disk or created a new one using setser
 *		function.
 * Scope:	private
 * Parameters:	fn	- module file name
		value1	- The first 32-byte of the serial number
		value2	- The second 32-byte of the serial number
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
get_serial32(char *fn, int32_t *value1, int32_t *value2)
{
	Elf32_Ehdr Ehdr;
	Elf32_Shdr Shdr;
	int fd;
	int rc;
	char name[6];
	off_t offset;
	off_t shstrtab_offset;
	off_t data_offset;
	int i;
	int32_t t[3];

	rc = ERROR;	/* assume module doesn't exist */

	/* open the module file */
	if ((fd = open(fn, O_RDONLY)) < 0) {
		return (rc);
	}

	/* read the elf header */
	offset = 0;
	if (pread(fd, &Ehdr, sizeof (Ehdr), offset) < 0) {
		goto out;
	}

	/* read the section header for the section string table */
	offset = Ehdr.e_shoff + (Ehdr.e_shstrndx * Ehdr.e_shentsize);
	if (pread(fd, &Shdr, sizeof (Shdr), offset) < 0) {
		goto out;
	}

	/* save the offset of the section string table */
	shstrtab_offset = Shdr.sh_offset;

	/* find the .data section header */
	/*CSTYLED*/
	for (i = 1; ; ) {
		offset = Ehdr.e_shoff + (i * Ehdr.e_shentsize);
		if (pread(fd, &Shdr, sizeof (Shdr), offset) < 0) {
			goto out;
		}
		offset = shstrtab_offset + Shdr.sh_name;
		if (pread(fd, name, sizeof (name), offset) < 0) {
			goto out;
		}
		if (strcmp(name, ".data") == 0)
			break;
		if (++i >= (int)Ehdr.e_shnum) {
			/* reached end of table */
			goto out;
		}
	}

	/* save the offset of the data section */
	data_offset = Shdr.sh_offset;

	/* read and check the version number and initial seed values */
	offset = data_offset;
	if (pread(fd, &t[0], sizeof (t[0]) * 3, offset) < 0) {
		goto out;
	}

	*value1 = t[1];
	*value2 = t[2];
	rc = NOERR;

out:    (void) close(fd);
	return (rc);
}

/*
 * function:	set_serial64
 * Description:	Set the serial number in the 64-bit sysinit module using
 *		the serial number got from 32-bit sysinit module
 *		This has been populated either with the serial number from
 *		the OS instance on the disk or created a new one using setser
 *		function.
 * Scope:	private
 * Parameters:	fn	- module file name
		value1	- The first 32-byte of the serial number
		value2	- The second 32-byte of the serial number
 * Return:	ERROR	- Failed to patch the module
 *		NOERR   - Success
 */
static int
set_serial64(char *fn, int32_t value1, int32_t value2)
{
	struct stat statbuf;
	struct utimbuf utimbuf;
	int rc, fd, count, i;
	Elf *elf;
	Elf_Scn *scn;
	Elf_Scn *dscn;
	Elf64_Ehdr *ehdr;
	Elf64_Shdr *dscnhdr;
	Elf64_Shdr *shdr;
	Elf64_Sym *sym;
	Elf_Data *data;
	char *dbuf = NULL;
	Elf_Data *elfdata;
	int32_t s;
	uint32_t ver;
	char *symname;

	/* open the module file */
	if ((fd = open(fn, O_RDWR)) < 0)
		return (ERROR);

	/* get file status for times */
	if (fstat(fd, &statbuf) < 0)
		goto out;

	/* open the ELF */
	elf_version(EV_CURRENT);
	elf = elf_begin(fd, ELF_C_RDWR, (Elf *)0);
	if (elf == NULL)
		goto out;

	/* find the symbol table */
	scn = NULL;
	ehdr = elf64_getehdr(elf);
	while ((scn = elf_nextscn(elf, scn)) != NULL) {
		shdr = elf64_getshdr(scn);
		if (shdr->sh_type == SHT_SYMTAB) {
			/* found the symbol table, so lets go search it. */
			break;
		}
	}

	if (scn == NULL) {
		/* no symbol table, so silently bail */
		goto elfout;
	}

	/* how many symbols in the symbol table */
	data = elf_getdata(scn, NULL);
	count = shdr->sh_size / shdr->sh_entsize;

	/* find the super-secret symbol we are looking for */
	for (i = 0; i < count; ++i) {
		sym = (Elf64_Sym *)((char *)data->d_buf +
		    (i * sizeof (Elf64_Sym)));
		symname = elf_strptr(elf, shdr->sh_link, sym->st_name);
		if (symname == NULL) {
			/* ignore null symbols */
			continue;
		}
		if (strcmp(symname, HOSTID_SYMBOL) == 0) {
			/*
			 * We found the right symbol.
			 * Now go find the section it's in.
			 */
			dscn = elf_getscn(elf, sym->st_shndx);

			/* Now find its header */
			dscnhdr = elf64_getshdr(dscn);

			/* Finally find the section contents (dbuf) */
			elfdata = elf_getdata(dscn, NULL);
			dbuf = (char *)elfdata->d_buf;

			/*
			 * dbuf + symbol offset points to the version
			 * identifier
			 */
			ver = *((uint32_t *)(dbuf+sym->st_value));

			/*
			 * Version must match the super-secret one we
			 * are expecting
			 */
			if (ver != (uint32_t)V1) {
				goto elfout;
			}
			break;
		}
	}

	if (dbuf == NULL) {
		/* didn't find the symbol, bail */
		goto elfout;
	}

	/* Set the hostid  */
	*(((uint32_t *)dbuf) + 1) = value1;
	*(((uint32_t *)dbuf) + 2) = value2;

	/* ensure that the memory image of the ELF file is complete */
	elf_update(elf, ELF_C_NULL);
	elf_update(elf, ELF_C_WRITE);   /* update ELF file on disk */
	elf_end(elf);
	(void) close(fd);

	/* restore file access and modification times */
	utimbuf.actime = statbuf.st_atime;
	utimbuf.modtime = statbuf.st_mtime;
	if (utime(fn, &utimbuf) < 0)
		return (ERROR);

	return (NOERR);	/* return success */

elfout:	elf_end(elf);

	/* close file and return error code */
out:    (void) close(fd);
	return (ERROR);
}
