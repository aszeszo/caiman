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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)transfermod.c	1.9	07/10/30 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ftw.h>
#include <libnvpair.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <limits.h>
#include <unistd.h>
#include <errno.h>
#include <sys/kbio.h>
#include <sys/kbd.h>
#include <stropts.h>
#include <sys/mman.h>
#include <sys/mount.h>
#include <regex.h>
#include <time.h>
#include <pthread.h>

/*
 * Salient definitions
 */

/*
 * These are all relative paths into the alternate root
 * mountpoint.
 */
#define	TM_LOGFILE_NAME "transfer.log"
#define	KBD_DEFAULTS_FILE	"etc/default/kbd"

/*
 * Definitions for copyfile function.
 */
#define	MAXMAPSIZE	(1024*1024*8)	/* map at most 8MB */
#define	SMALLFILESIZE	(32*1024)	/* don't use mmap on little files */

#define	MAX_NUMFILES	200000.0f
#define	FIND_PERCENT    4
#define	KBD_DEVICE	"/dev/kbd"
#define	CPIO		"/usr/bin/cpio"
#define	BUNZIP2		"/usr/bin/bunzip2"
#define	SKELETON	"/.cdrom/skeleton.cpio"
#define	ARCHIVE		"/.cdrom/archive.bz2"
#define	DEFAULT_CPIO_ARGS	"pdum"
#define	BUF_SIZE		(PATH_MAX + 50)

/*
 * Definitions required for translating keyboard numeric IDs to
 * strings - RFE time for the keyboard API.
 */
#define	KBD_LAYOUT_FILE	"/usr/share/lib/keytables/type_6/kbd_layouts"
#define	MAX_LINE_SIZE	512

#define	INFO_MSG1(str) if (lof != NULL) { \
	(void) fprintf(lof, "%s\n", str); \
	(void) fflush(lof); \
}

#define	INFO_MSG2(fmt, arg) if (lof != NULL) { \
	(void) fprintf(lof, fmt, arg); \
	(void) fprintf(lof, "\n"); \
	(void) fflush(lof); \
}

#define	INFO_MSG3(fmt, arg1, arg2) if (lof != NULL) { \
	(void) fprintf(lof, fmt, arg1, arg2); \
	(void) fprintf(lof, "\n"); \
	(void) fflush(lof); \
}

#define	DBG_MSG1(str) if (dbgflag) { INFO_MSG1(str); }
#define	DBG_MSG2(fmt, arg) if (dbgflag) { INFO_MSG2(fmt, arg); }
#define	DBG_MSG3(fmt, arg1, arg2) if (dbgflag) { \
	INFO_MSG3(fmt, arg1, arg2); \
}

#define	CHECK_ABORT if (do_abort) { \
	INFO_MSG1("Transfer process cancelled"); \
	rv = 0; \
	goto done; \
}

#define	CHECK_ABORT1 if (do_abort) { \
	INFO_MSG1("Transfer process cancelled"); \
	return (1); \
}

#define	CHECK_ABORT2 if (do_abort) { \
	INFO_MSG1("Transfer process cancelled"); \
	break; \
}

#define	GET_TOKEN(token, lasts, str1, str2) \
	token = strtok_r(str1, str2, &lasts); \
	if (token == NULL) { \
		continue; \
	}


/*
 * This structure specifies the mountpoints that need to be copied
 * from the currently booted Live environment to the harddisk. First
 * a file tree walk (nftw(3C)) is used to list all the pathnames.
 * These pathnames are then fed to cpio which actually copies the
 * bits. The file tree walk is restricted to the same mounted fs. So
 * all the filesystems needed to be copied are listed in this struct.
 * The structure has the following fields:
 *
 * chdir_prefix: Perform a chdir to this directory before listing
 *               pathnames and before doing a cpio.
 * cpio_dir    : Name of the directory to be cpio-ed. This pathname
 *               is relative to chdir_prefix.
 * match_pattern: An extended regexp, as described in regex(5). This
 *               is used to match pathnames to be passed to cpio.
 *               In addition to what is mentioned in regex(5), a '!'
 *               character can be inserted at the beginning of the
 *               pattern to negate the pattern match (like egrep -v).
 * clobber_files: Setting this to 1 indicates that all existing non-
 *               directory pathnames already existing in the target
 *               harddisk must be deleted before a cpio is done.
 *               This is required to handle a situation arising out
 *               of a necessary optimization performed for the LiveCD.
 * cpio_args	: Arguments to use with cpio. Keeping this as NULL
 *               uses the default cpio arguments of "pdum" which is
 *               what is desired in most cases.
 *
 * NOTE: errors from cpio when copying /mnt/misc listed below are
 *       expected due to the pdm args.
 */
#define	NUM_PREFIXES 7
static struct cpio_spec {
	char *chdir_prefix;
	char *cpio_dir;
	char *match_pattern;
	int clobber_files;
	char *cpio_args;

} cpio_prefixes[NUM_PREFIXES] = {
	{"/",         ".",   NULL, 0, NULL},
	{"/",         "usr", NULL, 0, NULL},
	{"/",         "opt", NULL, 0, NULL},
	{"/",         "dev", NULL, 0, NULL},
	{"/mnt/misc", ".",   NULL, 1, "pdm"},
	{"/.cdrom",   ".",   "!zlib$|cpio$|bz2$", 0, NULL},
	{NULL, NULL, NULL, 0, NULL}
};

/*
 * File operations to be performed and the associated pathnames.
 * This array is allows to have a generic loop to process all the
 * pathnames rather than multiple individual statements.
 * %M is the pathname string is replaced with the alternate root
 * mountpoint name.
 */
#define	FILE_OP_UNLINK	1
#define	FILE_OP_RMDIR	2
#define	FILE_OP_MKDIR	3
#define	FILE_OP_COPY	4
#define	FILE_OP_CHMOD	5

#define	NUM_FILEOPS_LIST	16
static struct fileops {
	char *src, *dst;
	int op;
	int perms;

} fileops_list[NUM_FILEOPS_LIST] = {
	{"%M/lib/svc/seed/global.db", "%M/etc/svc/repository.db",
	    FILE_OP_COPY, 0600},
	{"/etc/mnttab", "%M/etc/mnttab",
	    FILE_OP_COPY, 0},
	{"/etc/dfs/sharetab", "%M/etc/dfs/sharetab",
	    FILE_OP_COPY, 0},
	{"%M/etc/svc/volatile", "",
	    FILE_OP_MKDIR, 0755},
	{"%M/var/run", "",
	    FILE_OP_MKDIR, 0755},
	{"%M/boot/x86.microroot", "",
	    FILE_OP_UNLINK, 0},
	{"%M/etc/ssh/ssh_host_dsa_key", "",
	    FILE_OP_UNLINK, 0},
	{"%M/etc/ssh/ssh_host_dsa_key.pub", "",
	    FILE_OP_UNLINK, 0},
	{"%M/etc/ssh/ssh_host_rsa_key", "",
	    FILE_OP_UNLINK, 0},
	{"%M/etc/ssh/ssh_host_rsa_key.pub", "",
	    FILE_OP_UNLINK, 0},
	{"/etc/mnttab", "%M/etc/mnttab",
	    FILE_OP_COPY, 0},
	{"%M/etc/mnttab", "",
	    FILE_OP_CHMOD, 0444},
	{"%M/.livecd", "",
	    FILE_OP_UNLINK, 0},
	{"%M/.volumeid", "",
	    FILE_OP_UNLINK, 0},
	{"%M/.mounted", "",
	    FILE_OP_UNLINK, 0},
	{"%M/boot/grub/menu.lst", "",
	    FILE_OP_UNLINK, 0},
};

struct file_list {
	FILE *handle;
	char name[PATH_MAX];
	char *chdir_prefix;
	int clobber_files;
	char *cpio_args;
	struct file_list *next;
};

static FILE *listfile;
static FILE *lof;
static FILE *zerolength = NULL;
static int do_abort = 0;
static int dbgflag = 0;
static float nfiles = 0;
static int total_find_percent;
static int percent, opercent;
static void (*progress)(int);
static regex_t *mre = NULL;
static int negate;
static char *mntpt = NULL;
static char *tmpenv = "TMPDIR=/tmp";
static pthread_mutex_t tran_mutex = PTHREAD_MUTEX_INITIALIZER;

void TM_abort_transfer();
void TM_enable_debug();
int TM_perform_transfer(nvlist_t *targs, void(*prog)(int));


/*
 * Log an error message to a logfile or stderr.
 */
static void
Perror(const char *str)
{
	char *err;

	err = strerror(errno);
	if (lof != NULL) {
		(void) fprintf(lof, "%s: %s\n", str, err);
		(void) fflush(lof);
	} else {
		perror(str);
	}
}

/*
 * Perform file copy from source to target
 */
static int
copyfile(char *source, char *target)
{
	int fi, fo;
	int mapsize, munmapsize;
	caddr_t cp;
	off_t filesize;
	off_t offset;
	int nbytes;
	int remains;
	int n;
	struct stat s1, s2;
	fi = open(source, O_RDONLY);
	if (fi == -1) {
		Perror(source);
		return (1);
	}

	DBG_MSG3("Copying file %s to %s", source, target);
	fo = open(target, O_WRONLY|O_CREAT|O_TRUNC);
	if (fo == -1) {
		Perror(target);
		(void) close(fi);
		return (1);
	}

	if (fstat(fi, &s1) < 0) {
		Perror(source);
		(void) close(fi);
		(void) close(fo);
		return (1);
	}

	if (fstat(fo, &s2) < 0) {
		Perror(source);
		(void) close(fi);
		(void) close(fo);
		return (1);
	}

	if (s1.st_size > SMALLFILESIZE) {
		/*
		 * Determine size of initial mapping.  This will determine the
		 * size of the address space chunk we work with.  This initial
		 * mapping size will be used to perform munmap() in the future.
		 */
		mapsize = MAXMAPSIZE;
		if (s1.st_size < mapsize) mapsize = s1.st_size;
		munmapsize = mapsize;

		/*
		 * Mmap time!
		 */
		if ((cp = mmap((caddr_t)NULL, mapsize, PROT_READ,
		    MAP_SHARED, fi, (off_t)0)) == MAP_FAILED)
			mapsize = 0;   /* can't mmap today */
	} else
		mapsize = 0;

	filesize = s1.st_size;

	if (mapsize != 0) {
		offset = 0;

		for (;;) {
			nbytes = write(fo, cp, mapsize);
			/*
			 * if we write less than the mmaped size it's due to a
			 * media error on the input file or out of space on
			 * the output file.  So, try again, and look for errno.
			 */
			if ((nbytes >= 0) && (nbytes != (int)mapsize)) {
				remains = mapsize - nbytes;
				while (remains > 0) {
					nbytes = write(fo,
					    cp + mapsize - remains, remains);
					if (nbytes < 0) {
						if (errno == ENOSPC)
							Perror(target);
						else
							Perror(source);
						(void) close(fi);
						(void) close(fo);
						(void) munmap(cp, munmapsize);
						(void) unlink(target);
						return (1);
					}
					remains -= nbytes;
					if (remains == 0)
						nbytes = mapsize;
				}
			}
			/*
			 * although the write manual page doesn't specify this
			 * as a possible errno, it is set when the nfs read
			 * via the mmap'ed file is accessed, so report the
			 * problem as a source access problem, not a target file
			 * problem
			 */
			if (nbytes < 0) {
				if (errno == EACCES)
					Perror(source);
				else
					Perror(target);
				(void) close(fi);
				(void) close(fo);
				(void) munmap(cp, munmapsize);
				(void) unlink(target);
				return (1);
			}
			filesize -= nbytes;
			if (filesize == 0)
				break;
			offset += nbytes;
			if (filesize < mapsize)
				mapsize = filesize;
			if (mmap(cp, mapsize, PROT_READ, MAP_SHARED | MAP_FIXED,
			    fi, offset) == MAP_FAILED) {
				Perror(source);
				(void) close(fi);
				(void) close(fo);
				(void) munmap(cp, munmapsize);
				(void) unlink(target);
				return (1);
			}
		}
		(void) munmap(cp, munmapsize);
	} else {
		char buf[SMALLFILESIZE];
		for (;;) {
			n = read(fi, buf, sizeof (buf));
			if (n == 0) {
				return (0);
			} else if (n < 0) {
				Perror(source);
				(void) close(fi);
				(void) close(fo);
				(void) unlink(target);
				return (1);
			} else if (write(fo, buf, n) != n) {
				Perror(target);
				(void) close(fi);
				(void) close(fo);
				(void) unlink(target);
				return (1);
			}
		}
	}
	return (0);
}

/*
 * Log the percentage completion to a logfile in an XML format that
 * the Orchestrator can understand. This is used if a callback func
 * has not been provided.
 */
static void
log_progress(int percent) {
	static FILE *plog = NULL;

	if (plog == NULL) {
		plog = fopen("/tmp/install_update_progress.out", "a+");
	}

	if (plog != NULL) {
		(void) fprintf(plog, "<progressStatus source=\"TransferMod\" "
		    "type=\"solaris-install\" percent=\"%d\" />\n", percent);
		(void) fflush(plog);
		if (percent == 100) {
			(void) fclose(plog);
		}
	}
}

/*
 * Callback function that is invoked for every pathname when doing a
 * file tree walk via nftw. The pathname is matched with a regexp if
 * provided and then appended to a temporary file.
 */
/* ARGSUSED */
static int
add_files(const char *fpath,
    const struct stat *finfo,
    int ftw_flag,
    struct FTW *ftw_prop)
{
	int rstatus;

	CHECK_ABORT1;
	if (fpath[0] == '.' && fpath[1] == NULL) {
		return (0);
	}

	if (ftw_flag != FTW_DNR) {
		if (mre != NULL) {
			rstatus = regexec(mre, fpath, (size_t)0,
			    NULL, 0);
			if ((negate && rstatus == 0) ||
			    (!negate && rstatus != 0)) {
				DBG_MSG2("Non pattern match. "
				    "Skipped: %s", fpath);
				return (0);
			}
		}
		if (finfo->st_size > 0) {
			(void) fprintf(listfile, "%s\n", fpath);
		} else {
			/*
			 * Handle zero-length regular files differently since
			 * they will be hardlinked on hsfs.
			 */
			if (S_ISREG(finfo->st_mode)) {
				(void) fprintf(zerolength, "%d,%d,%d,%s\n",
				    finfo->st_mode & S_IAMB, finfo->st_uid,
				    finfo->st_gid, fpath);
			}
		}

		DBG_MSG2("Added pathname: %s", fpath);
		nfiles++;
		percent = (int)(nfiles / MAX_NUMFILES * total_find_percent);
		if (percent - opercent >= 1) {
			(*progress)(percent);
			opercent = percent;
		}
	}
	return (0);
}

static void
free_flist(struct file_list *flist)
{
	struct file_list *tmp;

	while (flist != NULL) {
		tmp = flist->next;
		if (flist->handle != NULL)
			(void) fclose(flist->handle);

		if (flist->name[0] != '\0')
			(void) unlink(flist->name);

		free(flist);
		flist = tmp;
	}
}

static void
expand_symbols(char *fpath, char *buf, size_t buflen)
{
	char *pos;
	ptrdiff_t diff1, diff2;
	int len;

	buf[0] = '\0';
	len = strlen(fpath);
	pos = strstr(fpath, "%M");

	DBG_MSG2("Expanding: %s", fpath);
	if (pos != NULL) {
		diff1 = pos - fpath;
		if (diff1 > 0 && diff1 < buflen) {
			(void) strncpy(buf, fpath, diff1);
		}
		(void) strlcat(buf, mntpt, buflen);
		diff2 = len - (diff1 + 2);
		len = strlen(buf);

		if (diff2 > 0 && diff2 + len < buflen) {
			(void) strncat(buf, pos+2, diff2);
		}
	} else {
		(void) strlcpy(buf, fpath, buflen);
	}
}

/*
 * Given a keyboard layout number return the layout string.
 * We should not be doing this here, but unfortunately there
 * is no interface in the OpenSolaris keyboard API to perform
 * this mapping for us - RFE.
 */
static char *
get_layout_name(int lnum)
{
	FILE *stream;
	char buffer[MAX_LINE_SIZE];
	char *result = NULL;
	int  num;
	char *tmpbuf;

	if ((stream = fopen(KBD_LAYOUT_FILE, "r")) == 0) {
		Perror(KBD_LAYOUT_FILE);
		return (NULL);
	}

	while (fgets(buffer, MAX_LINE_SIZE, stream) != NULL) {
		if (buffer[0] == '#')
			continue;
		if ((result = strtok(buffer, "=")) == NULL)
			continue;
		if ((tmpbuf = strdup(result)) == NULL) {
			Perror("out of memory getting layout names");
			(void) fclose(stream);
			return (NULL);
		}
		if ((result = strtok(NULL, "\n")) == NULL)
			continue;
		num = atoi(result);
		if (num == lnum) {
			break;
		}
		free(tmpbuf);
	}

	(void) fclose(stream);
	return (tmpbuf);
}

/*
 * Given a file containing a list of pathnames this function
 * will search for those entries in the alternate root and
 * delete all matching pathnames from the alternate root that
 * are symbolic links.
 * This process is required because of the way the LiveCD env
 * is constructed. Some of the entries in the microroot are
 * symbolic links to files mounted off a compressed lofi file.
 * This is done to drastically reduce space usage by the microroot.
 */
static int
do_clobber_files(char *flist_file)
{
	FILE *fh;
	char line[PATH_MAX];
	struct stat mst;

	DBG_MSG2("File list for clobber: %s", flist_file);
	fh = fopen(flist_file, "r");
	if (fh == NULL) {
		Perror(flist_file);
		return (1);
	}

	if (chdir(mntpt) != 0) {
		Perror("Cannot change dir to alt root");
		(void) fclose(fh);
		return (1);
	}

	while (fgets(line, PATH_MAX, fh) != NULL) {
		CHECK_ABORT2;

		line[strlen(line) - 1] = '\0';
		if (lstat(line, &mst) == 0) {
			if (S_ISLNK(mst.st_mode)) {
				DBG_MSG2("Unlink: %s", line);
				(void) unlink(line);
			}
		}
	}

	(void) fclose(fh);
	return (0);
}


/*
 * Main function for doing the copying of bits
 */
int
TM_perform_transfer(nvlist_t *targs, void(*prog)(int))
{
	char *logfile = NULL, *buf = NULL, *cprefix;
	char *buf1 = NULL, *layout = NULL, *dbg;
	FILE *cpipe = NULL, *kbd_file;
	float ipercent, rem_percent, cpfiles;
	float calc_factor;
	int kbd = -1, kbd_layout;
	int rv = 0, i;
	struct file_list flist, *cflist;
	clock_t tm;
	struct stat st;
	char zerolist[PATH_MAX];


	flist.next = NULL;

	if (pthread_mutex_lock(&tran_mutex) != 0) {
		Perror("Unable to acquire Transfer lock ");
		return (1);
	}

	if (nvlist_lookup_string(targs, "mountpoint", &mntpt) != 0) {
		Perror("Alternate root mountpoint not provided. Bailing. ");
		return (1);
	}

	if (prog == NULL) {
		progress = log_progress;
	} else {
		progress = prog;
	}

	logfile = malloc(PATH_MAX);
	if (logfile == NULL) {
		Perror("Malloc failed ");
		return (1);
	}

	(void) snprintf(logfile, PATH_MAX, "%s/%s", mntpt,
	    TM_LOGFILE_NAME);

	lof = fopen(logfile, "w+");
	if (lof == NULL) {
		Perror("Unable to open logfile ");
		goto error_done;
	}

	buf = malloc(BUF_SIZE);
	if (buf == NULL) {
		Perror("Malloc failed ");
		goto error_done;
	}

	buf1 = malloc(BUF_SIZE);
	if (buf1 == NULL) {
		Perror("Malloc failed ");
		goto error_done;
	}

	dbg = getenv("TM_DEBUG");
	if (dbg != NULL && strcmp(dbg, "1") == 0) {
		TM_enable_debug();
	}

	/*
	 * Set TMPDIR to avoid cpio depleting ramdisk space
	 */
	if (putenv(tmpenv) != 0) {
		Perror(tmpenv);
		goto error_done;
	}

	/*
	 * Zero length file list.
	 */
	(void) strlcpy(zerolist, mntpt, PATH_MAX);
	(void) strlcat(zerolist, "/flist.0length", PATH_MAX);
	if ((zerolength = fopen(zerolist, "w+")) == NULL) {
		Perror(zerolist);
		goto error_done;
	}

	tm = time(NULL);
	(void) strftime(buf, PATH_MAX, (char *)0, localtime(&tm));
	INFO_MSG2("-- Starting transfer process, %s --", buf);
	(void) chdir("/");
	CHECK_ABORT;

	(*progress)(0);
	percent = 0;
	opercent = 0;
	total_find_percent = (NUM_PREFIXES - 1) * FIND_PERCENT;


	/*
	 * Get the optimized libc overlay out of the way.
	 */
	if (umount("/lib/libc.so.1") != 0) {
		if (errno != EINVAL) {
			Perror("Can't unmount /lib/libc.so.1 ");
			goto error_done;
		}
	}
	CHECK_ABORT;
	INFO_MSG1("Building file lists for cpio");

	/*
	 * Do a file tree walk of all the mountpoints provided and
	 * build up pathname lists. Pathname lists of all mountpoints
	 * under the same prefix are aggregated in the same file to
	 * reduce the number of cpio invocations.
	 *
	 * This loop builds a linked list where each entry points to
	 * a file containing a pathname list and mentions other info
	 * like the mountpoint from which to copy etc.
	 */
	cprefix = "";
	cflist = &flist;
	for (i = 0; cpio_prefixes[i].chdir_prefix != NULL; i++) {
		char *patt;
		regex_t re;

		CHECK_ABORT;
		DBG_MSG3("Cpio dir: %s, Chdir to: %s",
		    cpio_prefixes[i].cpio_dir,
		    cpio_prefixes[i].chdir_prefix);
		patt = cpio_prefixes[i].match_pattern;
		if (strcmp(cprefix,
		    cpio_prefixes[i].chdir_prefix) != 0 ||
		    patt != NULL ||
		    cpio_prefixes[i].clobber_files == 1 ||
		    cpio_prefixes[i].cpio_args != NULL) {

			cprefix = cpio_prefixes[i].chdir_prefix;
			cflist->next = (struct file_list *)
			    malloc(sizeof (struct file_list));
			cflist = cflist->next;
			cflist->next = NULL;
			(void) snprintf(cflist->name, PATH_MAX, "%s/flist%d",
			    mntpt, i);
			DBG_MSG2(" File list tempfile: %s", cflist->name);

			cflist->handle = fopen(cflist->name, "w+");
			if (cflist->handle == NULL) {
				Perror("Unable to open file list ");
				goto error_done;
			}

			cflist->chdir_prefix =
			    cpio_prefixes[i].chdir_prefix;
			if (patt != NULL) {
				DBG_MSG2(" Compiling regexp: %s", patt);
				if (patt[0] == '!') {
					negate = 1;
					patt++;
				} else {
					negate = 0;
				}
				if (regcomp(&re, patt,
				    REG_EXTENDED|REG_NOSUB) != 0) {
					Perror("Regexp error ");
					goto error_done;
				}
				mre = &re;
			} else {
				mre = NULL;
			}

			listfile = cflist->handle;
			cflist->clobber_files =
			    cpio_prefixes[i].clobber_files;
			if (cpio_prefixes[i].cpio_args != NULL) {
				cflist->cpio_args =
				    cpio_prefixes[i].cpio_args;
			} else {
				cflist->cpio_args = DEFAULT_CPIO_ARGS;
			}
		}

		INFO_MSG3("Scanning %s/%s", cflist->chdir_prefix,
		    cpio_prefixes[i].cpio_dir);
		(void) chdir(cflist->chdir_prefix);
		if (nftw(cpio_prefixes[i].cpio_dir, add_files, 10,
		    FTW_MOUNT|FTW_PHYS) < 0) {
			Perror("Nftw failed ");
			goto error_done;
		}
		(void) fflush(cflist->handle);
	}
	(void) fflush(zerolength);

	/*
	 * Now process each entry in the list. cpio is executed with the
	 * -V option where it prints a dot for each pathname processed.
	 * Since we already know the number of files we can show accurate
	 * percentage completion.
	 */
	INFO_MSG1("Beginning cpio actions ...");

	rem_percent = 95 - percent;
	ipercent = percent;
	cflist = flist.next;
	cpfiles = 0;
	opercent = 0;
	percent = 0;
	calc_factor = rem_percent / nfiles;
	while (cflist != NULL) {
		(void) fclose(cflist->handle);
		cflist->handle = NULL;
		CHECK_ABORT;
		if (cflist->clobber_files) {
			if (do_clobber_files(cflist->name) != 0) {
				goto error_done;
			}
		}

		(void) chdir(cflist->chdir_prefix);
		(void) snprintf(buf, PATH_MAX, "%s -%sV %s < %s",
		    CPIO, cflist->cpio_args, mntpt, cflist->name);
		DBG_MSG3("Executing: %s, CWD: %s", buf,
		    cflist->chdir_prefix);

		cpipe = popen(buf, "r");
		if (cpipe == NULL) {
			Perror("Unable to cpio files ");
			goto error_done;
		}

		while (!feof(cpipe)) {
			int ch = fgetc(cpipe);
			if (ch == '.') {
				cpfiles++;
				percent = (int)(cpfiles * calc_factor +
				    ipercent);
				if (percent - opercent >= 1) {
					if (progress != NULL) {
						(*progress)(percent);
					}
					opercent = percent;
				}
			}
			CHECK_ABORT;
		}
		if (ferror(cpipe)) {
			Perror(CPIO);
			goto error_done;
		}

		(void) fclose(cpipe);
		cpipe = NULL;

		(void) unlink(cflist->name);
		cflist->name[0] = '\0';
		cflist = cflist->next;
	}
	(*progress)(percent);
	cpipe = NULL;

	/*
	 * Process zero-length files if any.
	 */
	INFO_MSG1("Creating zero-length files");
	rewind(zerolength);
	while (fgets(buf, BUF_SIZE, zerolength) != NULL) {
		int fd;
		mode_t mod;
		uid_t st_uid, st_gid;
		char *token, *lasts;

		/* Get the newline out of the way */
		buf[strlen(buf) - 1] = '\0';

		/* Parse out ownership and perms */
		GET_TOKEN(token, lasts, buf, ",");
		mod = atoi(token);
		GET_TOKEN(token, lasts, NULL, ",");
		st_uid = atoi(token);
		GET_TOKEN(token, lasts, NULL, ",");
		st_gid = atoi(token);

		GET_TOKEN(token, lasts, NULL, ",");
		(void) snprintf(buf1, PATH_MAX, "%s/%s", mntpt, token);

		fd = open(buf1, O_WRONLY | O_CREAT | O_TRUNC, mod);
		if (fd != -1) {
			(void) fchown(fd, st_uid, st_gid);
			(void) close(fd);
			DBG_MSG2("Created file %s", buf1);
		} else {
			INFO_MSG1("Unable to create file:");
			Perror(buf1);
		}
	}
	(*progress)(97);

	CHECK_ABORT;
	INFO_MSG1("Extracting archive");
	(void) chdir(mntpt);
	(void) snprintf(buf, PATH_MAX, "%s -c %s | %s -idum",
	    BUNZIP2, ARCHIVE, CPIO);
	DBG_MSG3("Executing: %s, CWD: %s", buf, mntpt);
	if (system(buf) != 0) {
		Perror("Extracting archive failed ");
		goto error_done;
	}
	(*progress)(98);
	CHECK_ABORT;

	/*
	 * Check for the presence of skeleton.cpio before extracting it.
	 * This file may not be present in a Distro Constructor image.
	 */
	if (lstat(SKELETON, &st) == 0 && (S_ISREG(st.st_mode) ||
	    S_ISLNK(st.st_mode))) {
		INFO_MSG1("Extracting skeleton archive");
		(void) snprintf(buf, PATH_MAX, "%s -imu < %s", CPIO,
		    SKELETON, mntpt);
		DBG_MSG3("Executing: %s, CWD: %s", buf, mntpt);
		if (system(buf) != 0) {
			Perror("Skeleton cpio failed ");
			goto error_done;
		}
	}
	(*progress)(99);

	CHECK_ABORT;
	INFO_MSG1("Performing file operations");
	for (i = 0; i < NUM_FILEOPS_LIST; i++) {
		int rv;

		CHECK_ABORT;
		expand_symbols(fileops_list[i].src, buf, PATH_MAX);

		switch (fileops_list[i].op) {
			int op;

		case FILE_OP_UNLINK:
			DBG_MSG2("Unlink: %s", buf);
			(void) unlink(buf);
			rv = 0; /* unlink errors are non-fatal */
			break;

		case FILE_OP_RMDIR:
			DBG_MSG2("Rmdir: %s", buf);
			(void) rmdir(buf);
			rv = 0; /* Ignore rmdir errors for now */
			break;

		case FILE_OP_MKDIR:

			DBG_MSG2("Mkdir: %s", buf);
			rv = 0;
			if (lstat(buf, &st) == 0) {
				op = 0;
				if ((st.st_mode & S_IFMT)
				    != S_IFDIR) {
					rv = unlink(buf);
					op = 1;
				}
				if (rv == 0 && op) {
					rv = mkdir(buf,
					    fileops_list[i].perms);
				}
			} else {
				rv = mkdir(buf,
				    fileops_list[i].perms);
			}
			break;

		case FILE_OP_COPY:
			expand_symbols(fileops_list[i].dst, buf1,
			    PATH_MAX);
			rv = copyfile(buf, buf1);
			break;
		case FILE_OP_CHMOD:
			expand_symbols(fileops_list[i].dst, buf1,
			    PATH_MAX);
			rv = chmod(buf, fileops_list[i].perms);
			break;
		default:
			Perror("Unsupported file operation ");
			rv = 1;
			break;
		}
		if (rv != 0) {
			Perror("File ops error ");
			Perror(buf);
			goto error_done;
		}
	}

	CHECK_ABORT;
	INFO_MSG1("Fetching and updating keyboard layout");
	(void) chdir(mntpt);

	DBG_MSG2("Opening keyboard device: %s", KBD_DEVICE);
	kbd = open(KBD_DEVICE, O_RDWR);
	if (kbd < 0) {
		Perror("Error opening keyboard");
		goto error_done;
	}

	if (ioctl(kbd, KIOCLAYOUT, &kbd_layout)) {
		Perror("ioctl keyboard layout");
		goto error_done;
	}

	CHECK_ABORT;
	if ((layout = get_layout_name(kbd_layout)) == NULL) {
		goto error_done;
	}

	kbd_file = fopen(KBD_DEFAULTS_FILE, "a+");
	if (kbd_file == NULL) {
		Perror("Unable to open kbd defaults file ");
		goto error_done;
	}

	(void) fprintf(kbd_file, "LAYOUT=%s\n", layout);
	(void) fclose(kbd_file);
	DBG_MSG3("Updated keyboard defaults file: %s/%s", mntpt,
	    KBD_DEFAULTS_FILE);

	INFO_MSG2("Detected %s keyboard layout", layout);
	tm = time(NULL);
	(void) strftime(buf, PATH_MAX, (char *)0, localtime(&tm));
	INFO_MSG2("-- Completed transfer process, %s --", buf);

	(*progress)(100);

	goto done;
error_done:
	rv = 1;

done:
	if (lof != NULL)
		(void) fclose(lof);

	if (cpipe != NULL)
		(void) fclose(cpipe);

	free_flist(flist.next);

	if (logfile != NULL)
		free(logfile);

	if (kbd > 0)
		(void) close(kbd);

	if (buf != NULL)
		free(buf);

	if (buf1 != NULL)
		free(buf1);

	if (layout != NULL)
		free(layout);

	if (zerolength != NULL) {
		(void) fclose(zerolength);
		(void) unlink(zerolist);
	}

	do_abort = 0;
	(void) pthread_mutex_unlock(&tran_mutex);

	return (rv);
}

/*
 * Indicate cancellation of a transfer process if any.
 */
void
TM_abort_transfer()
{
	if (pthread_mutex_trylock(&tran_mutex) == EBUSY) {
		/*
		 * The mutex is unlocked so there is no transfer
		 * process running.
		 */
		(void) pthread_mutex_unlock(&tran_mutex);
	} else {
		do_abort = 1;
	}
}

void
TM_enable_debug()
{
	dbgflag = 1;
}

#ifdef __TM_TEST__

void
show_progress(int percent)
{
	(void) fprintf(stderr, "%d\n", percent);
}

void
main(void) {
	nvlist_t *nvl;

	nvlist_alloc(&nvl, NV_UNIQUE_NAME, 0);
	nvlist_add_string(nvl, "mountpoint", "/mnt/altroot");
	TM_perform_transfer(nvl, show_progress);
	nvlist_free(nvl);
}

#endif
