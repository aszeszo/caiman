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

#include <libsvm.h>

#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <libintl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <ustat.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/mntent.h>
#include <sys/wait.h>
#include <sys/swap.h>

#include <sys/types.h>
#include <sys/statvfs.h>
#include <libnvpair.h>
#include "spmizones_lib.h"

#include <td_lib.h>
#include <td_dd.h>

/* Local Statics and Constants */

#define	MOUNT_DEV	0
#define	SWAP_DEV	1

struct mountentry {
	struct mountentry *next;
	int	op_type;	/* MOUNT_DEV, SWAP_DEV */
	int	errcode;
	char	*mntdev;
	char	*emnt;
	char	*mntpnt;
	char	*fstype;
	char	*options;
};

static struct mountentry *retry_list = NULL;

struct stringlist {
	struct stringlist *next;
	int   command_type;	/* MOUNT_DEV, SWAP_DEV */
	char   stringptr[2];
};

/* Local Globals */

static struct stringlist *umount_head = NULL;
static struct stringlist *unswap_head = NULL;

#define	NO_RETRY	0
#define	DO_RETRIES	1

static char	*rootmntdev;
static char	*rootrawdev;
static char	rootpartition[2];
static char	err_mount_dev[MAXPATHLEN];

/* internal prototypes */

int		gen_mount_script(FILE *, int);
void		gen_umount_script(FILE *);
int		umount_root(void);
void		gen_installboot(FILE *);
char		*td_get_failed_mntdev(void);

/* private prototypes */

static void	save_for_umount(char *, struct stringlist **, int);
static int	add_swap_dev(char *);
static void	free_retry_list(void);
static void	free_mountentry(struct mountentry *);
static void	save_for_swap_retry(char *, char *);
static void	save_for_mnt_retry(char *, char *, char *, char *);

int		ddm_check_for_svm(char *);
svm_info_t	*ddm_svm_alloc(void);
void		ddm_svm_free(svm_info_t *);
int		ddm_start_svm(char *, svm_info_t **, int);

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * Function:	td_mount_and_add_swap()
 * Description: Takes a slice name, which is the slice to be
 *		upgraded. Nothing is mounted when this funciton is called.
 *		First, mount the root. Then find the
 *		/etc/vfstab. Mount everything in the vfstab.
 * Parameters:
 *	diskname	-
 * Return:
 * Status:
 *	public
 */
int
td_mount_and_add_swap(const char *diskname)
{
	char	pathbuf[MAXPATHLEN];
	int	status;
	char	mnt[MAXPATHLEN];
	char	fsckd[MAXPATHLEN];
	int	slice;

	free_retry_list();

	err_mount_dev[0] = 0;
	(void) snprintf(mnt, MAXPATHLEN, "/dev/dsk/%s", diskname);
	(void) snprintf(fsckd, MAXPATHLEN, "/dev/rdsk/%s", diskname);

	rootmntdev = strdup(mnt);

	/*
	 * since we might override what we think the root device
	 * is (think mirrored root), we must remember the original,
	 * unmodified root device, used when writing out the boot-device
	 * setting to bootenv.rc (for x86).
	 */
	rootrawdev = strdup(fsckd);
	/*
	 * The upgrade script will need to know which DOS partition
	 * root is on.  This is a good place to figure that out.
	 * Assume (!) it's a single digit.
	 */
	slice = rootrawdev[strlen(rootrawdev) - 1] - '0';
	if (slice > 0 && slice < 27)
		rootpartition[0] = 'a' + slice;
	else
		rootpartition[0] = 'a';
	rootpartition[1] = '\0';

	if (*td_get_rootdir() == '\0') {
		(void) strcpy(pathbuf, "/etc/vfstab");
	} else {
		(void) strcpy(pathbuf, td_get_rootdir());
		(void) strcat(pathbuf, "/etc/vfstab");
	}

	if ((status = td_mount_filesys(mnt, fsckd, "/", "ufs", "ro", NO_RETRY,
	    NULL)) != 0)
		return (status);

	if ((status = td_mount_and_add_swap_from_vfstab(pathbuf))) {
		return (status);
	}

	if ((status = mount_zones())) {
		return (status);
	}
	return (0);
}

/*
 * Function:	td_mount_and_add_swap_from_vfstab()
 * Description: Takes the path to a vfstab and mounts all ufs file systems
 *		and swaps.
 * Parameters:
 *	vfstab_path	-
 * Return:
 * Status:
 *	public
 */
int
td_mount_and_add_swap_from_vfstab(char *vfstab_path)
{
	struct stat	statbuf;
	FILE	*fp;
	char	buf[BUFSIZ + 1];
	char	*mntdev = NULL;
	char	*fsckdev, *mntpnt;
	char	*fstype, *fsckpass, *automnt, *mntopts;
	char	pathbuf[MAXPATHLEN];
	int	status;
	char	*cp, *str1;
	char	emnt[MAXPATHLEN], efsckd[50];
	char	options[MAXPATHLEN];
	int	all_have_failed;
	struct mountentry	*mntp, **mntpp;

	free_retry_list();

	if ((fp = fopen(vfstab_path, "r")) == NULL) {
		if (TLW)
			td_debug_print(LS_DBGLVL_WARN,
			    "Unable to open %s\n", vfstab_path);
		(void) umount_root();
		return (ERR_OPENING_VFSTAB);
	}

	while (fgets(buf, BUFSIZ, fp)) {
		/* skip over leading white space */
		for (cp = buf; *cp != '\0' && isspace(*cp); cp++)
			;

		/* ignore comments, newlines and empty lines */
		if (*cp == '#' || *cp == '\n' || *cp == '\0')
			continue;

		cp[strlen(cp) - 1] = '\0';

		if (mntdev)
			free(mntdev);
		mntdev = (char *)strdup(cp);
		fsckdev = mntpnt = fstype = fsckpass = NULL;
		automnt = mntopts = NULL;
		for (cp = mntdev; *cp != '\0'; cp++) {
			if (isspace(*cp)) {
				*cp = '\0';
				for (cp++; isspace(*cp); cp++)
					;
				if (!fsckdev)
					fsckdev = cp;
				else if (!mntpnt)
					mntpnt = cp;
				else if (!fstype)
					fstype = cp;
				else if (!fsckpass)
					fsckpass = cp;
				else if (!automnt)
					automnt = cp;
				else if (!mntopts)
					mntopts = cp;
			}
		}

		if (mntdev == NULL || fsckdev == NULL || mntpnt == NULL ||
		    fstype == NULL || fsckpass == NULL || automnt == NULL ||
		    mntopts == NULL) {
			(void) fclose(fp);
			free(mntdev);
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Error parsing vfstab\n");
			return (ERR_MOUNT_FAIL);
		}

		/* if swap device, add it */
		if (strcmp(fstype, "swap") == 0) {
			(void) strcpy(err_mount_dev, mntdev);
			if ((status = td_map_to_effective_dev(mntdev,
			    emnt, sizeof (emnt))) != 0) {
				if (status != 2) {
					if (TLW)
						td_debug_print(LS_DBGLVL_WARN,
						    "Can't access device %s\n",
						    mntdev);
					(void) fclose(fp);
					free(mntdev);
					return (ERR_MOUNT_FAIL);
				} else {
					if (*td_get_rootdir() == '\0')
						(void) strcpy(emnt, mntdev);
					else {
						(void) strcpy(emnt,
						    td_get_rootdir());
						(void) strcat(emnt, mntdev);
					}
					status = stat(emnt, &statbuf);
					/*
					 *  If swap file isn't present,
					 *  it may be because the file
					 *  containing it hasn't been
					 *  mounted yet.  Save it for
					 *  later retry.
					 */
					if (status != 0)  {
						save_for_swap_retry(emnt,
						    mntdev);
						continue;
					} else if (!S_ISREG(statbuf.st_mode)) {
						td_debug_print(
						    LS_DBGLVL_WARN,
						    "Can't access device "
						    "%s\n", mntdev);

						(void) fclose(fp);
						free(mntdev);
						return (ERR_MOUNT_FAIL);
					}
				}
			}
			if ((status = add_swap_dev(emnt)) != 0) {
				(void) fclose(fp);
				free(mntdev);
				return (status);
			}
			err_mount_dev[0] = '\0';
			continue;
		}
		/* skip root device. it has already been mounted */
		if (strcmp(mntpnt, "/") == 0)
			continue;

		/* skip read-only devices */
		if (strcmp(mntopts, "-") != 0) {
			(void) strcpy(options, mntopts);
			str1 = options;
			while ((cp = strtok(str1, ",")) != NULL) {
				if (strcmp(cp, "ro") == 0)
					break;
				str1 = NULL;
			}
			if (cp != NULL)   /* ro appears in opt list */
				continue;
		}

		/*
		 * mount pcfs stub boot partition
		 * (We do this now rather than after the automnt check
		 * because to do it after the automnt check would require
		 * the addition of some ugly special-casing)
		 */
		if (streq(mntpnt, "/boot") && streq(fstype, "pcfs")) {
			char stubdev[MAXPATHLEN];
			int colonboot = 0;

			/*
			 * Strip the trailing `:boot', because we won't
			 * be able to map it as-is (the :boot part is
			 * magic understood by the mounter, and doesn't
			 * appear as part of the name in /dev/dsk).
			 */
			(void) snprintf(stubdev, sizeof (stubdev),
			    "%s", mntdev);
			if (strlen(stubdev) > 5 &&
			    streq(stubdev + (strlen(stubdev) - 5), ":boot")) {
				colonboot = 1;
				stubdev[strlen(stubdev) - 5] = '\0';
			}

			if (td_map_to_effective_dev(stubdev,
			    emnt, sizeof (emnt)) != 0) {
				(void) strcpy(err_mount_dev, mntdev);
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "Can't access device %s\n",
					    mntdev);
				(void) fclose(fp);
				free(mntdev);
				return (ERR_MOUNT_FAIL);
			}

			if (colonboot) {
				/*
				 * We mapped it to the new /dev/dsk entry,
				 * so put the `:boot' back on.
				 */
				(void) strncat(emnt, ":boot", sizeof (emnt));
			}

			if ((status = td_mount_filesys(emnt, NULL,
			    mntpnt, fstype, mntopts, DO_RETRIES, NULL)) != 0) {
				(void) fclose(fp);
				free(mntdev);
				return (status);
			}
		}

		/* skip non-auto-mounted devices */
		if (strcmp(automnt, "yes") != 0 &&
		    strcmp(mntpnt, "/usr") != 0 &&
		    strcmp(mntpnt, "/usr/kvm") != 0 &&
		    strcmp(mntpnt, "/var") != 0)
			continue;

		/*  mount ufs and s5 file systems */
		if (strcmp(fstype, "ufs") == 0 ||
		    strcmp(fstype, "s5") == 0) {
			if (td_map_to_effective_dev(mntdev, emnt, sizeof (emnt))
			    != 0) {
				(void) strcpy(err_mount_dev, mntdev);
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "Can't access device %s\n",
					    mntdev);
				(void) fclose(fp);
				free(mntdev);
				return (ERR_MOUNT_FAIL);
			}
			if (td_map_to_effective_dev(fsckdev,
			    efsckd, sizeof (efsckd)) != 0) {
				(void) strcpy(err_mount_dev, fsckdev);
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "Can't access device %s\n",
					    fsckdev);
				(void) fclose(fp);
				free(mntdev);
				return (ERR_MOUNT_FAIL);
			}
			if ((status = td_mount_filesys(emnt, efsckd, mntpnt,
			    fstype, mntopts, DO_RETRIES, NULL)) != 0) {
				(void) fclose(fp);
				free(mntdev);
				return (status);
			}

		/* mount VXFS volumes */
		} else if (streq(fstype, "vxfs")) {
			if ((status = td_mount_filesys(mntdev, fsckdev, mntpnt,
			    fstype, mntopts, DO_RETRIES, NULL)) != 0) {
				(void) fclose(fp);
				free(mntdev);
				return (status);
			}
		}
	}
	if (mntdev)
		free(mntdev);
	mntdev = fsckdev = mntpnt = fstype = fsckpass = NULL;
	automnt = mntopts = NULL;

	(void) fclose(fp);

	/*
	 *  Process retry list.  Continue to process it until all operations
	 *  on list have been tried and have failed.
	 */

	all_have_failed = 0;
	while (retry_list && !all_have_failed) {
		all_have_failed = 1;  /* assume failure */
		mntpp = &retry_list;
		while (*mntpp != (struct mountentry *)NULL) {
			mntp = *mntpp;
			if (mntp->op_type == SWAP_DEV) {
				(void) strcpy(err_mount_dev, mntp->mntdev);
				status = stat(mntp->emnt, &statbuf);
				if (status == 0) {
					if (!S_ISREG(statbuf.st_mode)) {
						if (TLW)
							td_debug_print(
							    LS_DBGLVL_WARN,
							    "Can't access "
							    "device %s\n",
							    mntp->mntdev);
						return (ERR_MOUNT_FAIL);
					}
					if ((status =
					    add_swap_dev(mntp->emnt)) != 0) {
						return (status);
					}
					err_mount_dev[0] = '\0';
					all_have_failed = 0;

					/* unlink and free retry entry */
					*mntpp = mntp->next;
					free_mountentry(mntp);
					mntp = NULL;
				} else
					mntpp = &(mntp->next);
			} else {   /* it's a mount request */
				(void) strcpy(err_mount_dev, mntp->mntdev);
				(void) snprintf(pathbuf, MAXPATHLEN,
				    "/sbin/mount -F %s %s %s %s "
				    ">/dev/null 2>&1\n",
				    mntp->fstype, mntp->options, mntp->mntdev,
				    mntp->mntpnt);
				if ((status = td_safe_system(pathbuf)) == 0) {
					err_mount_dev[0] = 0;
					save_for_umount(mntp->mntdev,
					    &umount_head, MOUNT_DEV);
					all_have_failed = 0;

					/* unlink and retry entry */
					*mntpp = mntp->next;
					free_mountentry(mntp);
					mntp = NULL;
				} else {
					mntp->errcode = WEXITSTATUS(status);
					mntpp = &(mntp->next);
				}
			}
		}
	}

	if (retry_list) {
		mntp = retry_list;
		(void) strcpy(err_mount_dev, mntp->mntdev);
		if (mntp->op_type == SWAP_DEV) {
			td_debug_print(LS_DBGLVL_WARN,
			    "Can't access device %s\n", mntp->mntdev);
			return (ERR_MOUNT_FAIL);
		} else {
			td_debug_print(LS_DBGLVL_WARN,
			    "Failure mounting %s, error = %d\n",
			    mntp->mntpnt, mntp->errcode);
			return (ERR_MOUNT_FAIL);
		}
	}

	return (0);
}

/*
 * td_mount_filesys()
 *
 * Parameters:
 *	mntdev	-
 *	fsckdev	-
 *	mntpnt	-
 *	fstype	-
 *	mntopts	-
 * Return:
 *
 * Status:
 *	public
 */
int
td_mount_filesys(char *mntdev, char *fsckdev, char *mntpnt,
	char *fstype, char *mntopts, int retry, nvlist_t **attr)
{
	char			options[MAXPATHLEN];
	char			fsckoptions[30];
	char			cmd[MAXPATHLEN];
	char			basemount[MAXPATHLEN];
	char			tmpfsckdev[MAXPATHLEN];
	int			status;
	int			cmdstatus;
	int			isslasha = 0;

	(void) strcpy(err_mount_dev, mntdev);

	/*
	 * make local copy of fsckdev, so td_set_mntdev_if_svm can
	 * overwrite it if needed (when a mirrored root is in use)
	 */
	if (fsckdev != NULL)
		(void) strncpy(tmpfsckdev, fsckdev, MAXPATHLEN);

	if (strcmp(mntopts, "-") == 0)
		options[0] = '\0';
	else {
		(void) strcpy(options, "-o ");
		(void) strcat(options, mntopts);
	}

	if (*td_get_rootdir() == '\0') {
		(void) strcpy(basemount, mntpnt);
	} else {
		(void) strcpy(basemount, td_get_rootdir());
		if (strcmp(mntpnt, "/") != 0)
			(void) strcat(basemount, mntpnt);
		else
			isslasha = 1;

	}

	/*
	 * fsck -m checks to see if file system
	 * needs checking.
	 *
	 * if return code = 0, disk is OK, can be mounted.
	 * if return code = 32, disk is dirty, must be fsck'd
	 * if return code = 33, disk is already mounted
	 *
	 * If the file system to be mounted is the true root,
	 * don't bother to do the fsck -m (since the results are
	 * unpredictable).  We know it must be mounted, so set
	 * the cmdstatus to 33.  This will drop us into the code
	 * that verifies that the EXPECTED file system is mounted
	 * as root.
	 *
	 * If no fsckdev was specified, assume that fscking doesn't
	 * need to be done for this filesystem.
	 */
	if (strcmp(basemount, "/") == 0) {
		cmdstatus = 33;
	} else if (!fsckdev) {
		cmdstatus = 0;
	} else {
		(void) snprintf(cmd, MAXPATHLEN,
		    "/usr/sbin/fsck -m -F %s %s >/dev/null 2>&1\n",
		    fstype, fsckdev);
		status = td_safe_system(cmd);
		cmdstatus = WEXITSTATUS(status);
	}
	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "before mount, cmdstatus=%d\n", cmdstatus);

	if (cmdstatus == 0) {
		(void) snprintf(cmd, MAXPATHLEN,
		    "/sbin/mount -F %s %s %s %s >/dev/null 2>&1\n",
		    fstype, options, mntdev, basemount);
		if ((status = td_safe_system(cmd)) != 0) {
			if (retry == NO_RETRY) {
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "Failure mounting %s, "
					    "error=%d <%s>\n",
					    basemount, WEXITSTATUS(status),
					    cmd);
				return (ERR_MOUNT_FAIL);
			} else {
				save_for_mnt_retry(basemount, fstype, options,
				    mntdev);
				err_mount_dev[0] = 0;
				return (0);
			}
		}
		/* set the mntdev to the mirror if there is one */
		if (td_set_mntdev_if_svm(basemount,
		    mntopts, &mntdev, tmpfsckdev, attr) != SUCCESS)
			return (ERR_MOUNT_FAIL);
	} else if (cmdstatus == 32 || cmdstatus == 33 || cmdstatus == 34) {
		dev_t	mntpt_dev;	/* device ID for mount point */
		dev_t	mntdev_dev;	/* dev ID for device */
		struct stat statbuf;

		/*
		 * This may mean the file system is already
		 * mounted. this needs to be checked.
		 */
		/* Get device ID for mount point */
		if (stat(basemount, &statbuf) != 0) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Mount failure, cannot stat %s\n",
				    basemount);
			return (ERR_MOUNT_FAIL);
		}
		mntpt_dev = statbuf.st_dev;

		/* Get device ID for mount device */
		if (stat(mntdev, &statbuf) != 0) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Mount failure, cannot stat %s\n",
				    mntdev);
			return (ERR_MOUNT_FAIL);
		}
		mntdev_dev = statbuf.st_rdev;

		if (mntpt_dev == mntdev_dev) {
			/*
			 * If the two devices are the same that means that
			 * the device is mounted and mounted correctly.
			 */
			return (0);
		} else {
			/*
			 * If these two devices are different that means
			 * that the file system is not mounted or mounted
			 * incorrectly. We need to check to see if the
			 * mount device is alreay mounted. If so that is an
			 * error and we'll returnt that fact.
			 */
			struct	ustat	ustatbuf;

			if (ustat(mntdev_dev, &ustatbuf) == 0) {
				/*
				 * ustat returns 0 if the device is mounted,
				 * which means that the device is not
				 * mounted were we wnat it.
				 */
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "%s not mounted at %s, \n",
					    mntdev, basemount);
				return (ERR_MOUNT_FAIL);
			}
			if (strcmp(fstype, "ufs") == 0)
				(void) strcpy(fsckoptions, "-o p");
			else if (strcmp(fstype, "s5") == 0)
				(void) strcpy(fsckoptions,
				    "-y -t /var/tmp/tmp$$ -D");
			else
				(void) strcpy(fsckoptions, "-y");
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "The %s file system (%s) is being "
				    "checked.\n", mntpnt, fstype);
			(void) snprintf(cmd, MAXPATHLEN,
			    "/usr/sbin/fsck -F %s %s %s >/dev/null 2>&1\n",
			    fstype, fsckoptions, fsckdev);
			status = td_safe_system(cmd);
			cmdstatus = WEXITSTATUS(status);
			if (cmdstatus != 0 && cmdstatus != 40) {
				if (TLW) {
					/* CSTYLE */
					td_debug_print(LS_DBGLVL_WARN,
					    "ERROR: unable to repair the "
					    "%s file system.\n", mntpnt);
					/* CSTYLE */
					td_debug_print(LS_DBGLVL_WARN,
					    "Run fsck manually "
					    "(fsck -F %s %s).\n",
					    fstype, fsckdev);
				}
				return (ERR_MUST_MANUAL_FSCK);
			}
		}
		(void) snprintf(cmd, MAXPATHLEN,
		    "/sbin/mount -F %s %s %s %s >/dev/null 2>&1\n",
		    fstype, options, mntdev, basemount);
		if ((status = td_safe_system(cmd)) != 0) {
			if (retry == NO_RETRY) {
				if (TLW)
					td_debug_print(LS_DBGLVL_WARN,
					    "Failure mounting %s, "
					    "error = %d\n",
					    basemount, WEXITSTATUS(status));
				return (ERR_MOUNT_FAIL);
			} else {
				save_for_mnt_retry(basemount, fstype, options,
				    mntdev);
				err_mount_dev[0] = 0;
				return (0);
			}
		}
		/* set the mntdev to the mirror if there is one */
		if (td_set_mntdev_if_svm(basemount,
		    mntopts, &mntdev, tmpfsckdev, attr) != SUCCESS)
			return (ERR_MOUNT_FAIL);
	} else {
		if (TLW)
			td_debug_print(LS_DBGLVL_WARN,
			    "Unrecognized failure %d from "
			    "'fsck -m -F %s %s'\n",
			    cmdstatus, fstype, fsckdev);
		return (ERR_FSCK_FAILURE);
	}

	/*
	 * We are dealing with / here so mount it rw
	 */
	if (isslasha) {
		(void) snprintf(cmd, MAXPATHLEN,
		    "/sbin/mount -o remount,rw %s %s >/dev/null 2>&1\n",
		    mntdev, basemount);
		if ((status = td_safe_system(cmd)) != 0) {
			td_debug_print(LS_DBGLVL_WARN,
			    "Failure remounting %s on %s, "
			    "error = %d\n",
			    mntdev, basemount, WEXITSTATUS(status));

			return (ERR_MOUNT_FAIL);
		}
		/*
		 * Overwrite what we think the root device is,
		 * in case td_set_mntdev_if_svm gave us a new one.
		 * Also make note of any root metadevice component
		 * names in case we need them later (in gen_installboot).
		 */
		free(rootmntdev);
		free(rootrawdev);
		rootmntdev = strdup(mntdev);
		rootrawdev = strdup(tmpfsckdev);
	}
	err_mount_dev[0] = 0;
	save_for_umount(mntdev, &umount_head, MOUNT_DEV);
	return (0);
}

/*
 * td_umount_and_delete_swap()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
int
td_umount_and_delete_swap(void)
{
	int	status;

	if ((status = td_umount_all()) != 0)
		return (status);
	return (td_unswap_all());
}

/*
 * td_umount_all()
 * Description:
 *	Attempt to unmount all mounted filesystems.
 * Parameters:
 *	none
 * Return:
 *	SUCCESS		If all umounts succeed
 *	FAILURE		If any fail
 * Status:
 *	public
 */
int
td_umount_all(void)
{
	struct stringlist	*p, *op;
	char			cmd[MAXPATHLEN];
	int			err = 0;

	if (UmountAllZones(td_get_rootdir()) != 0) {
		td_debug_print(LS_DBGLVL_ERR,
		    "Failed to unmount a nonglobal zone.");

		return (FAILURE);
	}

	p = umount_head;
	while (p) {
		if (p->command_type == MOUNT_DEV) {
			(void) snprintf(cmd, MAXPATHLEN,
			    "/sbin/umount %s >/dev/null 2>&1\n", p->stringptr);
			/*
			 * Keep track of failures
			 */
			if (td_safe_system(cmd) != 0) {
				err++;
				td_debug_print(LS_DBGLVL_ERR,
				    "umount of %s failed", p->stringptr);
			}
		}
		op = p;
		p = p->next;
		free(op);
	}
	umount_head = NULL;
	if (err != 0) {
		return (FAILURE);
	} else {
		return (SUCCESS);
	}
}

/*
 * td_unswap_all
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
int
td_unswap_all(void)
{
	int			status;

	if ((status = td_delete_all_swap()) != 0) {
		td_debug_print(LS_DBGLVL_WARN,
		    "Error freeing swap, error = %x",
		    WEXITSTATUS(status));

		return (ERR_DELETE_SWAP);
	}
	unswap_head = NULL;
	return (0);
}

/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * umount_root()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	semi-private (internal library use only)
 */
int
umount_root(void)
{
	char	cmd[MAXPATHLEN];
	int	status;

	(void) snprintf(cmd, MAXPATHLEN, "/sbin/umount %s", rootmntdev);
	if ((status = td_safe_system(cmd)) != 0) {
		td_debug_print(LS_DBGLVL_WARN,
		    "Error from umount, error = %x",
		    WEXITSTATUS(status));

		return (ERR_UMOUNT_FAIL);
	}
	return (0);
}

/*
 * Function:	mount_zones()
 * Description: Finds all mountable non-global zones and changes their state to
 *		ZONE_STATE_MOUNTED.
 *
 *		NOTES:
 *			- Assumes that the root filesystem to be upgraded is
 *			already mounted on td_get_rootdir().
 *
 * Parameters:
 *	None	-
 * Return:
 *	0			- All mountable zones successfully mounted,
 *				or no mountable zones found.
 *	ERR_ZONE_MOUNT_FAIL	- A mountable zone failed to mount.
 * Status:
 *	semi-private (internal library use only)
 */
int
mount_zones(void)
{
	zoneList_t		zlst;
	int			k;
	char			*zone_name;

	if (z_zones_are_implemented()) {
		zlst = z_get_nonglobal_zone_list();
		if (zlst == (zoneList_t)NULL) {
			return (0);
		}
		for (k = 0; (zone_name = z_zlist_get_zonename(zlst, k)) != NULL;
		    k++) {

			/* If zone state not installed, skip it */
			if (z_zlist_get_current_state(zlst, k) <
			    ZONE_STATE_INSTALLED) {
				td_debug_print(LS_DBGLVL_INFO,
				    "Skipping mount of uninstalled "
				    "nonglobal zone environment: %s",
				    zone_name);
				continue;
			}

			/*
			 * If failed to mount zone, write error message
			 * to log and return error
			 */
			if (!z_zlist_change_zone_state(zlst, k,
			    ZONE_STATE_MOUNTED)) {
				td_debug_print(LS_DBGLVL_ERR,
				    "Failed to mount nonglobal zone "
				    "environment: %s", zone_name);

				return (ERR_ZONE_MOUNT_FAIL);
			}
		}
	}

	return (0);
}

char *
td_get_failed_mntdev(void)
{
	return (err_mount_dev);
}

/*
 * returns filesystem type of specified path in a statically-allocated
 * buffer that the caller should not modify.
 */
char *
td_get_fs_type(char *path)
{
	struct statvfs statb;
	static char fstype[FSTYPSZ];

	if (path == NULL) {
		return (NULL);
	}

	if (statvfs(path, &statb) != 0) {
		return (NULL);
	}

	(void) strncpy(fstype, statb.f_basetype, FSTYPSZ);
	return (fstype);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * save_for_umount()
 * Parameters:
 *	mntdev	-
 *	head	-
 *	type	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
save_for_umount(char *mntdev, struct stringlist **head, int type)
{
	struct stringlist *p;

	p = malloc(sizeof (struct stringlist) + strlen(mntdev));

	(void) strcpy(p->stringptr, mntdev);
	p->command_type = type;
	p->next = *head;
	*head = p;
}

static int
add_swap_dev(char *mntdev)
{

	char	cmd[MAXPATHLEN];
	int	status;
	char	*exempt_swapdisk;

	exempt_swapdisk = td_GetExemptSwapdisk();
	if ((exempt_swapdisk != NULL) &&
	    (strcmp(mntdev, exempt_swapdisk) == 0)) {
		/* swapdisk and mntdev are equal do not add */
		return (0);
	}
	(void) snprintf(cmd, MAXPATHLEN,
	    "(/usr/sbin/swap -l 2>&1) | /bin/grep %s >/dev/null 2>&1", mntdev);
	if ((status = td_safe_system(cmd)) != 0) {
		/* swap not already added */
		(void) snprintf(cmd, MAXPATHLEN,
		    "/usr/sbin/swap -a %s > /dev/null 2>&1", mntdev);
		if ((status = td_safe_system(cmd)) != 0) {
			if (TLW)
				td_debug_print(LS_DBGLVL_WARN,
				    "Error adding swap, error = %x\n",
				    WEXITSTATUS(status));
			return (ERR_ADD_SWAP);
		}
	}
	save_for_umount(mntdev, &unswap_head, SWAP_DEV);
	return (0);
}

static void
save_for_swap_retry(char *emnt, char *mntdev)
{
	struct mountentry	*m, *p;

	m = calloc(1, sizeof (struct mountentry));
	m->op_type = SWAP_DEV;
	m->mntdev = strdup(mntdev);
	m->emnt = strdup(emnt);
	m->next = NULL;

	/* queue it to the retry list */
	if (retry_list == NULL)
		retry_list = m;
	else {
		p = retry_list;
		while (p->next != NULL)
			p = p->next;
		p->next = m;
	}
}

static void
save_for_mnt_retry(char *basemount, char *fstype, char *options, char *mntdev)
{
	struct mountentry	*m, *p;

	m = calloc(1, sizeof (struct mountentry));
	m->op_type = MOUNT_DEV;
	m->mntpnt = strdup(basemount);
	m->mntdev = strdup(mntdev);
	m->fstype = strdup(fstype);
	m->options = strdup(options);
	m->next = NULL;

	/* queue it to the retry list */
	if (retry_list == NULL)
		retry_list = m;
	else {
		p = retry_list;
		while (p->next != NULL)
			p = p->next;
		p->next = m;
	}
}

static void
free_retry_list()
{
	struct mountentry *mntp, *next;

	mntp = retry_list;
	retry_list = NULL;
	while (mntp != NULL) {
		next = mntp->next;
		free_mountentry(mntp);
		mntp = next;
	}
}

static void
free_mountentry(struct mountentry *mntp)
{
	if (mntp->mntdev)
		free(mntp->mntdev);
	if (mntp->emnt)
		free(mntp->emnt);
	if (mntp->mntpnt)
		free(mntp->mntpnt);
	if (mntp->fstype)
		free(mntp->fstype);
	if (mntp->options)
		free(mntp->options);
	free(mntp);
}

/*
 * Function:	td_remount_svm
 * Description: Trys to mount the metadevice on the mountpoint
 * Scope:	public
 * Parameters:  mountpoint - non-NULL path string
 *		svm- non-NULL structure that will contain the svm info
 *		mntopt - flag to determine mounting ro or rw.
 *
 * Return:	SUCCESS
 *		FAILURE
 */

int
td_remount_svm(char *mountpoint, svm_info_t *svm, char *mntopts)
{
	char cmd[MAXPATHLEN];
	char options[MAXPATHLEN];

	if ((mntopts == NULL) || (strcmp(mntopts, "-") == 0)) {
		options[0] = '\0';
	} else {
		(void) snprintf(options, sizeof (options), "-o %s", mntopts);
	}

	/*
	 * umount the mounted root filesystem
	 */
	(void) snprintf(cmd, sizeof (cmd),
	    "/usr/sbin/umount %s > /dev/null 2>&1", mountpoint);
	if (td_safe_system(cmd) != 0) {
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "remount_svm() %s failed\n", cmd);
		return (FAILURE);
	} else {
		/*
		 * now mount the mirror
		 */
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/mount -F ufs %s /dev/md/dsk/%s %s > "
		    "/dev/null 2>&1", options, svm->root_md, mountpoint);
		if (td_safe_system(cmd) != 0) {
			if (TLI)
				td_debug_print(LS_DBGLVL_INFO,
				    "remount_svm(): %s failed\n", cmd);
			return (FAILURE);
		}
	}

	if (TLI)
		td_debug_print(LS_DBGLVL_INFO,
		    "SPMI_STORE_SVM : remount_svm(): Mounted "
		    "/dev/md/dsk/%s on %s\n", svm->root_md, mountpoint);
	return (SUCCESS);
}

/*
 * td_set_mntdev_if_svm()
 *
 * Function to determine if the mounted fs is a metadevice
 * If it is then mount it instead.
 * Parameters:
 *	basemount - the base to check for svm info
 *	mntopts - the options to use for the mount
 *	mntdev - the device path that is to be mounted
 *		if non-NULL, name will be altered to remount SVM root mirror
 *		expected to accommodate MAXPATHLEN chars
 *	fsckdev - the raw device that could be fsck'd
 *		if non-NULL, name will be altered for SVM root mirror
 *		expected to accommodate MAXPATHLEN chars
 *	md_comp_count - where to store count of sides of mirror,
 *	if "basemount" is mirrored.  Stores 0 if not a mirror.
 *	md_comps - string array of component names
 * Return:
 *	SUCCESS : if mirror is mounted or there is no mirror
 *	FAILURE : if mirror is present and unable to start the SVM
 * Status:
 *	private
 */
int
td_set_mntdev_if_svm(char *basemount, char *mntopts, char **mntdev,
    char *fsckdev, nvlist_t **attr)
{
	svm_info_t	*svminfo;
	int		ret;

	if (ddm_check_for_svm(basemount) == SUCCESS) {
		svminfo = ddm_svm_alloc();
		if ((ret = ddm_start_svm(basemount, &svminfo, SVM_DONT_CONV))
		    != SUCCESS) {
			td_debug_print(LS_DBGLVL_WARN,
			    "svm on %s fails code=%d\n", basemount, ret);
			ddm_svm_free(svminfo);
			return (FAILURE);
		}
		if (TLI)
			td_debug_print(LS_DBGLVL_INFO,
			    "start_svm on %s succeeds comp cnt=%d\n",
			    basemount, svminfo->count);

		if (svminfo->count > 0) {
			if (td_remount_svm(basemount,
			    svminfo, mntopts) == SUCCESS) {
				if (mntdev != NULL && *mntdev != NULL)
					(void) snprintf(*mntdev, MAXPATHLEN,
					    "/dev/md/dsk/%s", svminfo->root_md);
				if (fsckdev != NULL)
					(void) snprintf(fsckdev, MAXPATHLEN,
					    "/dev/md/rdsk/%s",
					    svminfo->root_md);
			}
			if (attr != NULL) {
				/* root is a mirror - get component names */
				(void) nvlist_alloc(attr, NV_UNIQUE_NAME, 0);
				(void) nvlist_add_string(*attr,
				    TD_SLICE_ATTR_MD_NAME, svminfo->root_md);
				(void) nvlist_add_string_array(*attr,
				    TD_SLICE_ATTR_MD_COMPS,
				    svminfo->md_comps, (uint_t)svminfo->count);
			}
		}
		ddm_svm_free(svminfo);
		return (SUCCESS);
	}
	/*
	 * No mirror, return success, meaning the ctds is OK
	 * to continue using
	 */
	return (SUCCESS);
}

/*
 * td_safe_system()
 *
 * Function to execute shell commands in a thread-safe manner
 * Parameters:
 *	cmd - the command to execute
 * Return:
 *	return code from command
 *	if popen() fails, -1
 * Status:
 *	private
 */
int
td_safe_system(const char *cmd)
{
	FILE *p;

	if ((p = popen(cmd, "w")) == NULL)
		return (-1);
	return (pclose(p));
}
