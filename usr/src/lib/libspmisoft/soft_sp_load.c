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



#include "spmisoft_lib.h"
#include "sw_space.h"
#include "find_mod.h"
#include "pkglib.h"
#include "dbsql.h"
#include "instzones_api.h"

#include <ctype.h>
#include <string.h>
#include <sys/stat.h>
#include <locale.h>
#include <stdlib.h>
#include <assert.h>

/* Local Function Prototypes */
static int	match_missing_file(char *);
static int	sp_load_contents_file(FILE *, Product *, Product *);

int	sp_warn = 0;
int	doing_add_service = 0;

#ifdef DEBUG
extern	FILE	*ef;
#endif

extern	Modinfo *find_owning_inst();
extern	int	errno;

int sp_err_code, sp_err_subcode;
char *sp_err_path = NULL;

/* global variable */
struct missing_file *missing_file_list = NULL;

/* standard paths */
#define	PKGLOC	"var/sadm/pkg"
#define	PKGSAVE	"save/pspool"

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * sp_read_pkg_map()
 *	Read a pkg map file. flags = 0 or SP_CNT_DEVS. Most devs are not
 *	listed. For the final upgrade space check ignore dev entries now
 *	and fudge later using "du".
 * Parameters:
 *	pkgmap_path -
 *	pkgdir	    -
 *	rootdir_p   -
 *	basedir_p   -
 *	flags	    -
 * Return:
 * Status:
 *	public
 * Notes:
 *
 * Starting with Solaris 10, installed packages have additional
 * information stored away to support zones. This information must be
 * taken into account when size calculations are made.
 *
 * For any package "SUNWxxx", a new directory is created:
 *
 * --> /var/sadm/pkg/SUNWxxx/save/pspool/SUNWxxx
 *
 * This directory contains additional information necessary to allow
 * non-global zones to be created:
 *
 * --> original contents of the following are placed in save/pspool/SUNWxxx:
 * ---> "v" files
 * ---> "e" files
 * ---> "i" files
 * ---> pkgmap (file)
 * ---> pkginfo (file)
 * ---> install (directory)
 * ---> reloc (directory)
 *
 */

int
sp_read_pkg_map(char *pkgmap_path, char *pkgdir, Product *prod,
    char *basedir_p, int flags, FSspace **sp)
{
	MFILE		*mp;
	char		*cp;
	char		*path_p;
	char		buf[BUFSIZ+1];
	char		fType[BUFSIZ+1] = {'\0'};
	char		fA[BUFSIZ+1];
	char		fB[BUFSIZ+1];
	char		fullpath[MAXPATHLEN + 1];
	char		path[MAXPATHLEN + 1];
	daddr_t		fsize;
	daddr_t 	pkgmapsize;
	int		inodes;
	int		type;
	struct stat	sbuf;

	if ((path_is_readable(pkgmap_path) == FAILURE) ||
	    ((mp = mopen(pkgmap_path, TRUE)) == (MFILE *) NULL)) {
		set_sp_err(SP_ERR_OPEN, errno, pkgmap_path);
#ifdef DEBUG
		(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
		(void) fprintf(ef, "Can't open %s\n", pkgmap_path);
#endif
		return (SP_ERR_OPEN);
	}

	/*
	 * stat the pkgmap file and get its size
	 */
	if (lstat(pkgmap_path, &sbuf) < 0) {
		set_sp_err(SP_ERR_STAT, errno, pkgmap_path);
#ifdef DEBUG
		(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
		(void) fprintf(ef, "lstat failed for file %s\n", pkgmap_path);
		perror("lstat");
#endif
		return (SP_ERR_STAT);
	}
	pkgmapsize = (daddr_t)sbuf.st_size;

	if (slasha) {
		if (!do_chroot(slasha))
			return (SP_ERR_CHROOT);
	}

	while (mgets(buf, BUFSIZ, mp)) {
		ProgressAdvance(PROG_PKGMAP_SIZE, strlen(buf),
		    VAL_NEWPKG_SPACE, pkgdir);
		buf[strlen(buf) - 1] = '\0';

		/* set default node type */

		type = SP_NONE;

		/* toss out comments and empty lines */

		if (buf[0] == '#' || buf[0] == '\0' || buf[0] == ':')
			continue;

		/* scan out type in "fType" - must not corrupt afterwards */

		(void) sscanf(buf, "%*s %"STRINGIZE(BUFSIZ)"s", fType);

		/*
		 * *************************************************************
		 * process contents for installed locations of files/directories
		 * *************************************************************
		 */

		switch (fType[0]) {
		/*
		 * Regular, editable and volatile Files
		 */
		case 'f':
		case 'v':
		case 'e':
			(void) sscanf(buf,
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s "
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
				fA, fB);
			path_p = fA;
			fsize = strtoul(fB, (char **)NULL, 10);
			inodes = 1;
			break;
		/*
		 * Char/Block/Pipe Special Files
		 */
		case 'c':
		case 'b':
		case 'p':
			(void) sscanf(buf, "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
			    fA);
			path_p = fA;
			fsize = 0;
			inodes = 1;
			break;
		/*
		 * Hard Links
		 */
		case 'l':
			(void) sscanf(buf, "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
			    fA);
			if (cp = strchr(fA, '='))
				*cp = '\0';
			path_p = fA;
			fsize = 0;
			inodes = 0;
			break;
		/*
		 * Symbolic links
		 */
		case 's':
			(void) sscanf(buf, "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
			    fA);
			if (cp = strchr(fA, '='))
				*cp = '\0';
			path_p = fA;
			fsize = strlen(cp+1);
			inodes = 1;
			break;
		/*
		 * Directories
		 */
		case 'd':
		case 'x':
			(void) sscanf(buf, "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
			    fA);
			(void) strcpy(path, fA);
			if (path[strlen(path) - 1] == '/') {
				path[strlen(path) - 1] = '\0';
			}
			type |= SP_DIRECTORY;	/* node is a directory */
			path_p = path;
			/*
			 * size and inodes captured in stat_each_path()
			 */
			fsize = 0;
			inodes = 0;
			break;
		/*
		 * Packaging files
		 */
		case 'i':
			(void) sscanf(buf, "%*s %*s "
			    "%"STRINGIZE(BUFSIZ)"s "
			    "%"STRINGIZE(BUFSIZ)"s", fA, fB);
			if (strncmp(fA, "pkginfo", 7) == 0) {
				if (snprintf(path, sizeof (path), "/%s/%s/%s",
				    PKGLOC, pkgdir, fA) >= sizeof (path)) {
					continue;
				}
				path_p = path;
				fsize = strtoul(fB, (char **)NULL, 10);
			} else {
				if (snprintf(path, sizeof (path),
				    "/%s/%s/%s/%s", PKGLOC, pkgdir, "install",
				    fA) >= sizeof (path))
					continue;
				path_p = path;
				fsize = strtoul(fB, (char **)NULL, 10);
			}
			inodes = 1;
			break;
		default:
#ifdef DEBUG
			(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
			(void) fprintf(ef, "Unrecognized pkgmap line. %s: %s\n",
			    pkgdir, buf);
#endif
			continue;
		}

#ifdef DEBUG
		if (check_path_for_vars(path_p)) {
			(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
			(void) fprintf(ef, "Warning: File has vars: %s Pkg: "
			    "%s:\n", path_p, pkgdir);
		}
#endif

		if (!(flags & SP_CNT_DEVS)) {
			if (strncmp(path_p, "dev/", 4) == 0) continue;
			if (strncmp(path_p, "devices/", 8) == 0) continue;
			if (strncmp(path_p, "/dev/", 5) == 0) continue;
			if (strncmp(path_p, "/devices/", 9) == 0) continue;
		}

		/* set 'fullpath' from components */

		if (*path_p != '/') {
			set_path(fullpath, prod->p_rootdir, basedir_p, path_p);
		} else {
			set_path(fullpath, prod->p_rootdir, NULL, path_p);
		}

		/*
		 * Skip paths that are inherited.
		 */

		if (prod->p_inheritedDirs != NULL &&
		    *prod->p_inheritedDirs != NULL &&
		    z_path_is_inherited(fullpath,
		    fType[0], prod->p_rootdir)) {
			continue;
		}

		/* add file/directory to space usage */

		add_file(fullpath, fsize, inodes, type, (FSspace **)sp);

		/*
		 * Non-global zones should not have any data in their
		 * var/sadm/pkg/PKG/save/pspool directories so skip
		 * calculating space for those directories if we are
		 * in a non-global zone.
		 */

		if (prod->p_zonename != NULL) {
			continue;
		}

		/*
		 * *************************************************************
		 * process contents for var/sadm/pkg/%s/save/pspool/%s area
		 * *************************************************************
		 */

		/* set default node type */

		type = SP_NONE;

		switch (fType[0]) {
		/*
		 * These types are not stored in save/pspool/%s area
		 */
		case 'b':	/* block special file */
		case 'c':	/* character special file */
		case 'f':	/* regular file */
		case 'l':	/* hard link */
		case 'p':	/* pipe special file */
		case 's':	/* symbolic link */
			inodes = 0;
			fsize = 0;
			path_p = (char *)NULL;
			break;

		/*
		 * record the directory in the reloc directory to make sure that
		 * the inode count does not underflow
		 */
		case 'd':	/* directory */
		case 'x':	/* exclusive directory */
			/* extract path */
			(void) sscanf(buf, "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s",
			    fA);
			if (snprintf(path, sizeof (path),
				"%s/%s/%s/%s/reloc/%s",
				PKGLOC, pkgdir, PKGSAVE, pkgdir, fA)
				>= sizeof (path)) {
				continue;
			}
			type |= SP_DIRECTORY;	/* node is directory */
			path_p = path;
			fsize = 0;
			inodes = 0;
			break;

		/*
		 * editable and volatile Files
		 * entry: part [v|e] class path mode ownr grp size cksum modtime
		 */
		case 'v':	/* volatile file */
		case 'e':	/* editable file */
			/* extract path and size */
			(void) sscanf(buf,
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s "
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s", fA, fB);
			if (snprintf(path, sizeof (path),
				"%s/%s/%s/%s/reloc/%s",
				PKGLOC, pkgdir, PKGSAVE, pkgdir, fA)
				>= sizeof (path)) {
				continue;
			}
			path_p = path;
			fsize = strtoul(fB, (char **)NULL, 10);
			inodes = 1;
			break;

		/*
		 * Packaging files
		 */
		case 'i':	/* information / script file */
			/* extract path and size */
			(void) sscanf(buf,
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s "
			    "%*s %*s %*s %"STRINGIZE(BUFSIZ)"s", fA, fB);
			if (snprintf(path, sizeof (path),
				"%s/%s/%s/%s/install/%s",
				PKGLOC, pkgdir, PKGSAVE, pkgdir, fA)
				>= sizeof (path)) {
				continue;
			}
			path_p = path;
			fsize = strtoul(fB, (char **)NULL, 10);
			inodes = 1;
			break;
		default:
#ifdef DEBUG
			(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
			(void) fprintf(ef, "Unrecognized pkgmap line. %s: %s\n",
			    pkgdir, buf);
#endif
			continue;
		}

#ifdef DEBUG
		if (check_path_for_vars(path_p)) {
			(void) fprintf(ef, "DEBUG: sp_read_pkg_map():\n");
			(void) fprintf(ef, "Warning: File has vars: %s Pkg: "
			    "%s:\n", path_p, pkgdir);
		}
#endif

		/* process if path present */

		if ((path_p != (char *)NULL) && (*path_p != '\0')) {

			/* set 'fullpath' from components */

			if (*path_p != '/') {
				set_path(fullpath, prod->p_rootdir, basedir_p,
				    path_p);
			} else {
				set_path(fullpath, prod->p_rootdir,
				    NULL, path_p);
			}

			/* add file/directory to space usage */

			add_file(fullpath, fsize, inodes, type,
			    (FSspace **)sp);
		}
	}

	mclose(mp);

	/* track "var/sadm/pkg/%s/save" directory */

	if (snprintf(buf, sizeof (buf), "%s/%s/save", PKGLOC, pkgdir)
			< sizeof (buf)) {
		set_path(fullpath, prod->p_rootdir, NULL, buf);
		add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);
	}

	/* track "var/sadm/pkg/%s/save/pspool" directory */

	if (snprintf(buf, sizeof (buf), "%s/%s/%s", PKGLOC, pkgdir, PKGSAVE)
			< sizeof (buf)) {
		set_path(fullpath, prod->p_rootdir, NULL, buf);
		add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);
	}

	/* track "var/sadm/pkg/%s/save/pspool/%s" directory */

	if (snprintf(buf, sizeof (buf),
		"%s/%s/%s/%s", PKGLOC, pkgdir, PKGSAVE, pkgdir)
			< sizeof (buf)) {
		set_path(fullpath, prod->p_rootdir, NULL, buf);
		add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);
	}

	/* track "var/sadm/pkg/%s/save/pspool/%s/reloc" directory */

	if (snprintf(buf, sizeof (buf),
		"%s/%s/%s/%s/reloc", PKGLOC, pkgdir, PKGSAVE, pkgdir)
			< sizeof (buf)) {
		set_path(fullpath, prod->p_rootdir, NULL, buf);
		add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);
	}

	/* track "var/sadm/pkg/%s/save/pspool/%s/install" directory */

	if (snprintf(buf, sizeof (buf),
		"%s/%s/%s/%s/install", PKGLOC, pkgdir, PKGSAVE, pkgdir)
			< sizeof (buf)) {
		set_path(fullpath, prod->p_rootdir, NULL, buf);
		add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);
	}

	/* track /var/sadm/install directory */

	set_path(fullpath, prod->p_rootdir, NULL, "var/sadm/install");
	add_file(fullpath, 0, 1, SP_DIRECTORY, (FSspace **)sp);

	if (doing_add_service == 1) {
		/*
		 * use the size of the pkgmap file as an approximation of
		 * the size added to the contents file.
		 * Pkgadd/pkgrm make a tmp copy of the contents file so we
		 * need 2*sizeof(contents_file).
		 */
		set_path(fullpath, prod->p_rootdir, NULL,
			    "var/sadm/install/contents");
		add_file(fullpath, (pkgmapsize * 2), 1, SP_NONE,
		    (FSspace **)sp);
	}

	if (slasha) {
		if (!do_chroot("/"))
			return (SP_ERR_CHROOT);
	}

	return (SUCCESS);
}

/*
 * sp_load_contents()
 *
 * Parameters:
 *	prod1	-
 *	prod2	-
 * Return:
 *
 * Status:
 *	public
 */
int
sp_load_contents(Product *prod1, Product *prod2)
{
	char	contname[MAXPATHLEN];
	FILE	*fp;
	int	ret;

	sp_warn = 0;

	if (slasha) {
		if (!do_chroot(slasha))
			return (SP_ERR_CHROOT);
	}

	set_path(contname, prod1->p_rootdir, NULL,
		    "var/sadm/install/contents");
	fp = fopen(contname, "r");
	if (fp == (FILE *)NULL) {
		set_sp_err(SP_ERR_OPEN, errno, contname);
		if (slasha) {
			if (!do_chroot("/")) {
				return (SP_ERR_CHROOT);
			}
		}
		return (SP_ERR_OPEN);
	} else {
		ret = sp_load_contents_file(fp, prod1, prod2);
		(void) fclose(fp);
	}

	if (slasha) {
		if (!do_chroot("/"))
			return (SP_ERR_CHROOT);
	}

	return (ret);
}

/*
 * sp_load_contents_file()
 *
 * Parameters:
 *	fp	- FILE pointer to opened legacy contents file
 *	prod1	-
 *	prod2	-
 * Return:
 *
 * Status:
 *	public
 */
static int
sp_load_contents_file(FILE *fp, Product *prod1, Product *prod2)
{
	int	n;
	off_t	size;
	char	fullpath[MAXPATHLEN];
	static	struct	cfent	centry;
	struct	pinfo	*pp;
	Modinfo	*mi, *cur_mi;
	struct  crsave {
		struct crsave	*next;
		List	*pathlist;
		Modinfo	*crmi;
		ContentsRecord	*cr;
	};
	struct crsave *crsavehead = NULL;
	struct crsave *crp, *crnext;
	char	cur_cr_pkg[PKGSIZ+1] = "";
	FSspace	**fsp;
	struct	stat	sbuf;
	static	int	first = 1;
	int	type;

	if (first) {
		centry.pinfo = NULL;
		first = 0;
	}

	load_inherited_FSs(prod1);

	fsp = get_current_fs_layout();
	while ((n = get_next_contents_entry(fp, &centry)) != 0) {
		ProgressAdvance(PROG_CONTENTS_LINES, 1, VAL_CONTENTS_SPACE,
		    NULL);

		if (n < 0) {
			/* garbled entry, just skip it */
			continue;
		}
		if (match_missing_file(centry.path))
			continue;

		/*
		 * We are going to assign this space to a Modinfo struct.
		 */
		for (pp = centry.pinfo; pp != NULL; pp = pp->next) {
			mi = map_pinfo_to_modinfo(prod1, pp->pkg);
			if (mi == NULL && prod2 != NULL)
				mi = map_pinfo_to_modinfo(prod2, pp->pkg);
			/*
			 *  If the package is one that could not possibly be
			 *  updated by the upgrade or add_service operation,
			 *  don't add it up.  Let it be considered "extra" space
			 *  on the system.  Note that this isn't sufficient if
			 *  we ever want to support removal of unbundled
			 *  packages through this library (and we want to know
			 *  how much space is freed by removing a particular
			 *  package, so that it can be considered available for
			 *  adding additional packages).
			 */

			if (mi != NULL) {
				if (mi->m_flags & IS_UNBUNDLED_PKG)
					mi = NULL;
			}
			if (mi != NULL)
				break;
		}

		if (mi == NULL)
			continue;	/* no bundled owning pkg; skip it */

		/* prod1 and prod2 (if non-NULL) always have same rootdir */
		set_path(fullpath, prod1->p_rootdir, NULL, centry.path);

		if (prod1->p_inheritedDirs != NULL &&
		    *prod1->p_inheritedDirs != NULL &&
		    z_path_is_inherited(fullpath,
		    centry.ftype, prod1->p_rootdir)) {
			continue;
		}

		if (lstat(fullpath, &sbuf) < 0)
			continue;

		if (!streq(pp->pkg, cur_cr_pkg)) {
			if (cur_cr_pkg[0] != '\0') {
				/* must save the current package's record */
				for (crp = crsavehead; crp != NULL;
				    crp = crp->next) {
					/*LINTED [var set before used]*/
					if (crp->crmi == cur_mi)
						break;
				}
				if (crp == NULL) {
					crp = (struct crsave *)xcalloc((size_t)
					    sizeof (struct crsave));
					crp->crmi = cur_mi;
					link_to((Item **)&crsavehead,
					    (Item *)crp);
				}
				crp->cr = contents_record_from_stab(fsp,
				    crp->cr);
				crp->pathlist = (List *)(fsp[0]->fsp_internal);
			}

			/* now load the new package's contents record */
			(void) strcpy(cur_cr_pkg, pp->pkg);
			cur_mi = mi;
			for (crp = crsavehead; crp != NULL; crp = crp->next)
				if (crp->crmi == mi)
					break;
			if (crp == NULL) {
				reset_stab(fsp);
				begin_specific_space_sum(fsp);
			} else {
				stab_from_contents_record(fsp, crp->cr);
				fsp[0]->fsp_internal = (void *)(crp->pathlist);
			}
		}
		if (S_ISDIR(sbuf.st_mode)) {
			type = SP_DIRECTORY;
		} else {
			type = SP_NONE;
		}

		if (S_ISBLK(sbuf.st_mode) || S_ISCHR(sbuf.st_mode))
			size = 0;
		else
			size = sbuf.st_size;

		add_file(fullpath, size, 1, type, (FSspace**)fsp);
	}

	if (cur_cr_pkg[0] != '\0') {
		/* must save the current package's record */
		for (crp = crsavehead; crp != NULL; crp = crp->next)
			if (crp->crmi == cur_mi)
				break;
		if (crp == NULL) {
			crp = (struct crsave *)xcalloc((size_t)
			    sizeof (struct crsave));
			crp->crmi = cur_mi;
			link_to((Item **)&crsavehead, (Item *)crp);
		}
		crp->cr = contents_record_from_stab(fsp, crp->cr);
		crp->pathlist = (List *)(fsp[0]->fsp_internal);
	}

	for (crp = crsavehead; crp != NULL; crp = crnext) {
		stab_from_contents_record(fsp, crp->cr);
		fsp[0]->fsp_internal = (void *)(crp->pathlist);
		end_specific_space_sum(fsp);
		crp->crmi->m_fs_usage = contents_record_from_stab(fsp, crp->cr);
		/* record the space in the running total */
		add_spacetab(fsp, NULL, NULL);
		crnext = crp->next;
		free(crp);
	}

	return (SUCCESS);
}

/*
 * sp_read_space_file()
 *
 * Parameters:
 *	s_path	  - file pathname to space file
 *	rootdir_p -
 *	basedir_p -
 * Return:
 *	SUCCESS
 *	SP_ERR_CHROOT	- coudn't chroot() to "/a"
 *	SP_ERR_OPEN	- couldn't open specified space file, or couldn't
 *			  mmap (open) it
 * Note:
 *	The space file format is:
 *		<file>	<size in 512 byte blocks> <# inodes>
 */
int
sp_read_space_file(char *s_path, Product *prod, char *basedir_p,
    FSspace **sp)
{
	MFILE		*mp;
	char		fullpath[MAXPATHLEN + 1];
	char		buf[BUFSIZ + 1];
	char		f0[BUFSIZ+1], f1[BUFSIZ+1], f2[BUFSIZ+1];

	if ((path_is_readable(s_path) == FAILURE) ||
	    ((mp = mopen(s_path, TRUE)) == (MFILE *) NULL)) {
		set_sp_err(SP_ERR_OPEN, errno, s_path);
		return (SP_ERR_OPEN);
	}

	if (slasha) {
		if (!do_chroot(slasha))
			return (SP_ERR_CHROOT);
	}
	/*
	 * read in a line, strip off the '\n', ignore comments and null
	 * lines, and read in the 3 fields
	 */
	while (mgets(buf, BUFSIZ, mp)) {
		buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '#' || buf[0] == '\0' || buf[0] == ':')
			continue;

		(void) sscanf(buf,
		    "%"STRINGIZE(BUFSIZ)"s "
		    "%"STRINGIZE(BUFSIZ)"s "
		    "%"STRINGIZE(BUFSIZ)"s",
		    f0, f1, f2);
		set_path(fullpath, prod->p_rootdir, basedir_p, f0);
		/*
		 * Space field is specified in 512 byte blocks, so expand
		 * to bytes
		 */

		if (prod->p_inheritedDirs != NULL &&
		    *prod->p_inheritedDirs != NULL &&
		    z_path_is_inherited(fullpath,
		    '\0', prod->p_rootdir)) {
			continue;
		}

		add_file(fullpath, (strtoul(f1, (char **)NULL, 10) * 512),
		    strtoul(f2, (char **)NULL, 10), SP_DIRECTORY,
		    (FSspace **)sp);
	}

	(void) mclose(mp);
	/* return "/" to its original state */
	if (slasha) {
		if (!do_chroot("/"))
			return (SP_ERR_CHROOT);
	}
	return (SUCCESS);
}

/*
 * load_inherited_FSs()
 *
 * Description:
 *	Load the global array of inherited directories in libinstzones.
 * Parameters:
 *	prod	- pointer to a Product module
 * Return:
 *  None.
 * Status:
 *	public
 */

void
load_inherited_FSs(Product *prod)
{
	int  i = 0;

	assert(prod != (Product *)NULL);

	if (z_zones_are_implemented()) {
		z_free_inherited_file_systems();
		for (i = 0; prod->p_inheritedDirs != NULL &&
		    prod->p_inheritedDirs[i] != NULL; i++) {
			(void) z_add_inherited_file_system(
			    prod->p_inheritedDirs[i]);
		}
	}
}

/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

void
set_add_service_mode(int mode)
{
	doing_add_service = mode;
}

int
get_add_service_mode()
{
	return (doing_add_service);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

void
set_sp_err(int errcode, int specific_err, char *arg)
{
	if (sp_err_path) {
		free(sp_err_path);
		sp_err_path = NULL;
	}
	if (arg)
		sp_err_path = xstrdup(arg);
	sp_err_code = errcode;
	sp_err_subcode = specific_err;
}

static int
match_missing_file(char *path)
{
	int n;
	struct missing_file *missp;

	if (missing_file_list == NULL)
		return (0);
	n = strlen(path);
	path[n] = '/';
	for (missp = missing_file_list; missp != NULL; missp = missp->next) {
		if (strncmp(missp->missing_file_name, path, missp->misslen)
		    == 0) {
			path[n] = '\0';
			return (1);
		}
	}
	path[n] = '\0';
	return (0);
}
