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

#pragma ident	"@(#)svc_mountall.c	1.36	07/10/09 SMI"


#include "spmistore_api.h"
#include "spmicommon_api.h"
#include "spmisoft_lib.h"
#include "spmisvc_lib.h"

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
#include "svc_templates.h"
#include "spmizones_lib.h"

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
static struct stringlist *umount_script_head = NULL;
static struct stringlist *unswap_head = NULL;

#define	NO_RETRY	0
#define	DO_RETRIES	1

static char	*rootmntdev;
static char	*realrootmntdev;
static char	*rootrawdev;
static char	*stubmntdev;
static char	rootpartition[2];
static char	**root_comps;
static int	root_comp_count;
static char	err_mount_dev[MAXPATHLEN];

/* internal prototypes */

int		gen_mount_script(FILE *, int);
void		gen_umount_script(FILE *);
int		umount_root(void);
void		gen_installboot(FILE *);
char		*get_failed_mntdev(void);

/* private prototypes */

static void	save_for_umount(char *, struct stringlist **, int);
static int	add_swap_dev(char *);
static int	mount_filesys(char *, char *, char *, char *, char *, int);
static void	free_retry_list(void);
static void	free_mountentry(struct mountentry *);
static void	save_for_swap_retry(char *, char *);
static void	save_for_mnt_retry(char *, char *, char *, char *);
static int	_set_mntdev_if_svm(char *, char *, char **,
				char *, int *, char ***);


/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * Function:	mount_and_add_swap()
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
mount_and_add_swap(char *diskname, char *bootdev)
{
	char	pathbuf[MAXPATHLEN];
	int	status;
	char	mnt[MAXPATHLEN+1];
	char	fsckd[MAXPATHLEN+1];
	int	slice;

	if (GetSimulation(SIM_SYSSOFT)) {
		if (profile_upgrade)
			(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
			    "Can't mount if simulating disks"));
		return (ERR_MOUNT_FAIL);
	}
	free_retry_list();

	err_mount_dev[0] = 0;
	(void) snprintf(mnt, MAXPATHLEN, "/dev/dsk/%s", diskname);
	(void) snprintf(fsckd, MAXPATHLEN, "/dev/rdsk/%s", diskname);

	rootmntdev = xstrdup(mnt);

	/*
	 * since we might override what we think the root device
	 * is (think mirrored root), we must remember the original,
	 * unmodified root device, used when writing out the boot-device
	 * setting to bootenv.rc (for x86).
	 */
	realrootmntdev = xstrdup(mnt);
	rootrawdev = xstrdup(fsckd);
	stubmntdev = bootdev ? xstrdup(bootdev) : NULL;
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

	if (*get_rootdir() == '\0') {
		(void) strcpy(pathbuf, "/etc/vfstab");
	} else {
		(void) strcpy(pathbuf, get_rootdir());
		(void) strcat(pathbuf, "/etc/vfstab");
	}

	if ((status = mount_filesys(mnt, fsckd, "/", "ufs", "ro", NO_RETRY))
	    != 0)
		return (status);

	if ((status = run_devmap_scripts()) != 0 && status != ERR_NODIR)
		return (status);

	if ((status = mount_and_add_swap_from_vfstab(pathbuf))) {
		return (status);
	}

	if ((status = mount_zones())) {
		return (status);
	}
	return (0);
}

/*
 * Function:	mount_and_add_swap_from_vfstab()
 * Description: Takes the path to a vfstab and mounts all ufs file systems
 *		and swaps.
 * Parameters:
 *	vfstab_path	-
 * Return:
 * Status:
 *	public
 */
int
mount_and_add_swap_from_vfstab(char *vfstab_path)
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

	if ((fp = fopen(vfstab_path, "r")) == (FILE *)NULL) {
		if (profile_upgrade)
			(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
			    "Unable to open %s\n"), vfstab_path);
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
		mntdev = (char *)xstrdup(cp);
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
			if (profile_upgrade)
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				    "Error parsing vfstab\n"));
			return (ERR_MOUNT_FAIL);
		}

		/* if swap device, add it */
		if (strcmp(fstype, "swap") == 0) {
			(void) strcpy(err_mount_dev, mntdev);
			if ((status =
			    _map_to_effective_dev(mntdev, emnt)) != 0) {
				if (status != 2) {
					if (profile_upgrade)
						(void) printf(
						    dgettext(
						    "SUNW_INSTALL_LIBSVC",
						    "Can't access device %s\n"),
							    mntdev);
					(void) fclose(fp);
					free(mntdev);
					return (ERR_MOUNT_FAIL);
				} else {
					if (*get_rootdir() == '\0')
						(void) strcpy(emnt, mntdev);
					else {
						(void) strcpy(emnt,
						    get_rootdir());
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
						if (profile_upgrade)
							(void) printf(
							dgettext(
							"SUNW_INSTALL_LIBSVC",
							"Can't access device "
							"%s\n"), mntdev);
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
			char stubdev[MAXPATHLEN+1];
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

			if (_map_to_effective_dev(stubdev, emnt) != 0) {
				(void) strcpy(err_mount_dev, mntdev);
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Can't access device %s\n"),
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

			if ((status = mount_filesys(emnt, NULL, mntpnt, fstype,
						mntopts, DO_RETRIES)) != 0) {
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
			if (_map_to_effective_dev(mntdev, emnt) != 0) {
				(void) strcpy(err_mount_dev, mntdev);
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Can't access device %s\n"),
					    mntdev);
				(void) fclose(fp);
				free(mntdev);
				return (ERR_MOUNT_FAIL);
			}
			if (_map_to_effective_dev(fsckdev, efsckd) != 0) {
				(void) strcpy(err_mount_dev, fsckdev);
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Can't access device %s\n"),
					    fsckdev);
				(void) fclose(fp);
				free(mntdev);
				return (ERR_MOUNT_FAIL);
			}

			if ((status = mount_filesys(emnt, efsckd, mntpnt,
			    fstype, mntopts, DO_RETRIES)) != 0) {
				(void) fclose(fp);
				free(mntdev);
				return (status);
			}

		/* mount VXFS volumes */
		} else if (streq(fstype, "vxfs")) {
			if ((status = mount_filesys(mntdev, fsckdev, mntpnt,
			    fstype, mntopts, DO_RETRIES)) != 0) {
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
						if (profile_upgrade)
							(void) printf(
							dgettext(
							"SUNW_INSTALL_LIBSVC",
							"Can't access device "
							"%s\n"), mntp->mntdev);
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
				if ((status = system(pathbuf)) == 0) {
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
			if (profile_upgrade && !GetSimulation(SIM_EXECUTE))
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				    "Can't access device %s\n"), mntp->mntdev);
			return (ERR_MOUNT_FAIL);
		} else {
			if (profile_upgrade && !GetSimulation(SIM_EXECUTE))
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
					"Failure mounting %s, error = %d\n"),
					mntp->mntpnt, mntp->errcode);
			return (ERR_MOUNT_FAIL);
		}
	}

	return (0);
}

/*
 * mount_filesys()
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
static int
mount_filesys(char *mntdev, char *fsckdev, char *mntpnt,
	char *fstype, char *mntopts, int retry)
{
	char			options[MAXPATHLEN];
	char			fsckoptions[30];
	char			cmd[MAXPATHLEN];
	char			basemount[MAXPATHLEN];
	char			tmpfsckdev[MAXPATHLEN+1];
	int			status;
	int			cmdstatus;
	int			isslasha = 0;
	int			tmpcompcount;
	char			**tmpcomps;

	(void) strcpy(err_mount_dev, mntdev);

	/*
	 * make local copy of fsckdev, so _set_mntdev_if_svm can
	 * overwrite it if needed (when a mirrored root is in use)
	 */
	if (fsckdev != NULL)
		(void) strncpy(tmpfsckdev, fsckdev, MAXPATHLEN+1);

	if (strcmp(mntopts, "-") == 0)
		options[0] = '\0';
	else {
		(void) strcpy(options, "-o ");
		(void) strcat(options, mntopts);
	}

	if (*get_rootdir() == '\0') {
		(void) strcpy(basemount, mntpnt);
	} else {
		(void) strcpy(basemount, get_rootdir());
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
		status = system(cmd);
		cmdstatus = WEXITSTATUS(status);
	}
	if (cmdstatus == 0) {
		(void) snprintf(cmd, MAXPATHLEN,
		    "/sbin/mount -F %s %s %s %s >/dev/null 2>&1\n",
		    fstype, options, mntdev, basemount);
		if ((status = system(cmd)) != 0) {
			if (retry == NO_RETRY) {
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Failure mounting %s, "
					    "error = %d\n"),
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
		if (_set_mntdev_if_svm(basemount,
		    mntopts, &mntdev, tmpfsckdev,
		    &tmpcompcount, &tmpcomps) != SUCCESS)
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
			if (profile_upgrade)
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				    "Mount failure, cannot stat %s\n"),
				    basemount);
			return (ERR_MOUNT_FAIL);
		}
		mntpt_dev = statbuf.st_dev;

		/* Get device ID for mount device */
		if (stat(mntdev, &statbuf) != 0) {
			if (profile_upgrade)
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				    "Mount failure, cannot stat %s\n"),
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
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "%s not mounted at %s, \n"),
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

			if (profile_upgrade)
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				"The %s file system (%s) is being checked.\n"),
				    mntpnt, fstype);
			(void) snprintf(cmd, MAXPATHLEN,
			    "/usr/sbin/fsck -F %s %s %s >/dev/null 2>&1\n",
			    fstype, fsckoptions, fsckdev);
			status = system(cmd);
			cmdstatus = WEXITSTATUS(status);
			if (cmdstatus != 0 && cmdstatus != 40) {
				if (profile_upgrade) {
					/* CSTYLE */
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "ERROR: unable to repair the "
					    "%s file system.\n"), mntpnt);
					/* CSTYLE */
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Run fsck manually "
					    "(fsck -F %s %s).\n"),
					    fstype, fsckdev);
				}
				return (ERR_MUST_MANUAL_FSCK);
			}
		}
		(void) snprintf(cmd, MAXPATHLEN,
		    "/sbin/mount -F %s %s %s %s >/dev/null 2>&1\n",
		    fstype, options, mntdev, basemount);
		if ((status = system(cmd)) != 0) {
			if (retry == NO_RETRY) {
				if (profile_upgrade)
					(void) printf(
					    dgettext("SUNW_INSTALL_LIBSVC",
					    "Failure mounting %s, "
					    "error = %d\n"),
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
		if (_set_mntdev_if_svm(basemount,
		    mntopts, &mntdev, tmpfsckdev,
		    &tmpcompcount, &tmpcomps) != SUCCESS)
			return (ERR_MOUNT_FAIL);
	} else {
		if (profile_upgrade)
			(void) printf(
			    dgettext("SUNW_INSTALL_LIBSVC",
			    "Unrecognized failure %d from "
			    "'fsck -m -F %s %s'\n"),
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
		if ((status = system(cmd)) != 0) {
			(void) printf(
				dgettext("SUNW_INSTALL_LIBSVC",
				    "Failure remounting %s on %s, "
				    "error = %d\n"),
				    mntdev, basemount, WEXITSTATUS(status));
			return (ERR_MOUNT_FAIL);
		}

		/*
		 * Overwrite what we think the root device is,
		 * in case _set_mntdev_if_svm gave us a new one.
		 * Also make note of any root metadevice component
		 * names in case we need them later (in gen_installboot).
		 */
		free(rootmntdev);
		free(rootrawdev);
		rootmntdev = xstrdup(mntdev);
		rootrawdev = xstrdup(tmpfsckdev);
		root_comp_count = tmpcompcount;
		root_comps = tmpcomps;
	}

	err_mount_dev[0] = 0;
	save_for_umount(mntdev, &umount_head, MOUNT_DEV);
	return (0);
}

/*
 * Function:	gen_mount_script
 * Description:
 * Scope:	public
 * Parameters:	script_fp
 *		do_root
 * Return:	ERR_OPEN_VFSTAB
 *		ERR_MOUNT_FAIL
 *		0		    no errors
 */
/*ARGSUSED0*/
int
gen_mount_script(FILE *script_fp, int do_root)
{
	FILE	*fp;
	char	buf[BUFSIZ + 1];
	char	*mntdev = NULL;
	char	*fsckdev, *mntpnt;
	char	*fstype, *fsckpass, *automnt, *mntopts;
	char	vfstabpath[MAXPATHLEN];
	char	*cp;
	char	emnt[50], efsckd[50];

	if (*get_rootdir() == '\0') {
		(void) strcpy(vfstabpath, "/etc/vfstab");
	} else {
		(void) strcpy(vfstabpath, get_rootdir());
		(void) strcat(vfstabpath, "/etc/vfstab");
	}

	if ((fp = fopen(vfstabpath, "r")) == (FILE *)NULL) {
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				"Unable to open /a/etc/vfstab\n"));
		return (ERR_OPEN_VFSTAB);
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
		mntdev = (char *)xstrdup(cp);
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

		/* if swap device, add it */
		if (strcmp(fstype, "swap") == 0) {
			if (_map_to_effective_dev(mntdev, emnt) != 0) {
				if (profile_upgrade)
					(void) printf(dgettext(
						"SUNW_INSTALL_LIBSVC",
						    "Can't access device %s\n"),
					    mntdev);
				free(mntdev);
				(void) fclose(fp);
				return (ERR_MOUNT_FAIL);
			}

			save_for_umount(emnt, &umount_script_head, SWAP_DEV);
			continue;
		}

		/*  if root, only mount if do_root is set */
		if (strcmp(mntpnt, "/") == 0 && !do_root)
			continue;

		/*  mount ufs and s5 file systems */
		if (strcmp(fstype, "ufs") == 0 ||
		    strcmp(fstype, "s5") == 0) {
			if (_map_to_effective_dev(mntdev, emnt) != 0) {
				(void) strcpy(err_mount_dev, mntdev);
				if (profile_upgrade)
					(void) printf(dgettext(
						"SUNW_INSTALL_LIBSVC",
						    "Can't access device %s\n"),
					    mntdev);
				free(mntdev);
				(void) fclose(fp);
				return (ERR_MOUNT_FAIL);
			}
			if (_map_to_effective_dev(fsckdev, efsckd) != 0) {
				(void) strcpy(err_mount_dev, fsckdev);
				if (profile_upgrade)
					(void) printf(dgettext(
						"SUNW_INSTALL_LIBSVC",
						    "Can't access device %s\n"),
					    fsckdev);
				free(mntdev);
				(void) fclose(fp);
				return (ERR_MOUNT_FAIL);
			}

			save_for_umount(mntdev, &umount_script_head, MOUNT_DEV);

		/* mount VXFS filesystems */
		} else if (streq(fstype, "vxfs")) {
			save_for_umount(mntdev, &umount_script_head, MOUNT_DEV);
		}
	}
	if (mntdev)
		free(mntdev);
	(void) fclose(fp);
	return (0);
}

/*
 * gen_umount_script()
 *
 * Parameters:
 *	fp	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
gen_umount_script(FILE *fp)
{
	struct stringlist *p, *op;

	p = umount_script_head;
	while (p) {
		if (p->command_type == MOUNT_DEV)
			scriptwrite(fp, LEVEL1, umount_cmd,
			    "MNTDEV", p->stringptr, NULL);
		else
			scriptwrite(fp, LEVEL1, del_swap_cmd,
			    "MNTDEV", p->stringptr, NULL);
		op = p;
		p = p->next;
		free(op);
	}
	umount_script_head = NULL;
}

/*
 * umount_and_delete_swap()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
int
umount_and_delete_swap(void)
{
	int	status;

	if ((status = umount_all()) != 0)
		return (status);
	return (unswap_all());
}

/*
 * umount_all()
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
umount_all(void)
{
	struct stringlist	*p, *op;
	char			cmd[MAXPATHLEN];
	int			err = 0;

	if (UmountAllZones(get_rootdir()) != 0) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_LIBSVC",
		    "Failed to unmount a nonglobal zone."));
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
			if (system(cmd) != 0) {
				err++;
				write_message(LOGSCR, ERRMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_LIBSVC",
				    "umount of %s failed"), p->stringptr);
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
 * unswap_all
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
int
unswap_all(void)
{
	int			status;

	if ((status = delete_all_swap()) != 0) {
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Error freeing swap, error = %x"),
		    WEXITSTATUS(status));
		return (ERR_DELETE_SWAP);
	}
	unswap_head = NULL;
	return (0);
}

void
set_profile_upgrade(void)
{
	profile_upgrade = 1;
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
	if ((status = system(cmd)) != 0) {
		(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
		    "Error from umount, error = %x"),
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
 *			already mounted on get_rootdir().
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
	zone_state_t		cur_state;

	if (z_zones_are_implemented()) {
		zlst = z_get_nonglobal_zone_list();
		if (zlst == (zoneList_t)NULL) {
			return (0);
		}
		for (k = 0; (zone_name = z_zlist_get_zonename(zlst, k)) != NULL;
		    k++) {

			/* If zone state not installed, skip it */
			if ((cur_state = z_zlist_get_current_state(zlst, k)) <
			    ZONE_STATE_INSTALLED) {
				write_message(LOG, STATMSG, LEVEL1,
				    dgettext("SUNW_INSTALL_LIBSVC",
				    "Skipping mount of uninstalled "
				    "nonglobal zone environment: %s"),
				    zone_name);
				continue;
			}

			/*
			 * If failed to mount zone, write error message
			 * to log and return error
			 */
			if (!z_zlist_change_zone_state(zlst, k,
			    ZONE_STATE_MOUNTED)) {
				write_message(LOG, ERRMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_LIBSVC",
			    "Failed to mount nonglobal zone environment: %s"),
				    zone_name);
				return (ERR_ZONE_MOUNT_FAIL);
			}
		}
	}

	return (0);
}

/*
 * Generate scripts to install bootblocks and update grub menu.
 *  - If root is a mirror, we run installgrub on the Solaris fdisk
 *    partition on each submirror.
 *  - If there is a stub (pcfs) boot partition, we install grub and
 *    the grub menu on the boot partition as well.
 *
 * Note that the stub partition (if present) is mounted at /a/boot at
 * this point. So all the menu are written on pcfs. We disentangle
 * this mess in the /sbin/install-finish script at the end of install.
 */
void
gen_installboot(FILE *script_fp)
{
	int	i;
	char *stubrawroot;
	if (rootrawdev == NULL)
		return;

	/*
	 * Sparc is simple, run installboot either on raw slice
	 * or a metadisk slice
	 */
	if (IsIsa("sparc")) {
		scriptwrite(script_fp, LEVEL0, gen_installboot_sparc,
		    "RAWROOT", rootrawdev, NULL);
		return;
	}

	/*
	 * If a metadevice is in use on x86, we write the boot
	 * block out to the underlying disk.
	 */
	if (root_comp_count > 0) {
		/*
		 * one installgrub per disk that has a metadevice
		 * component on it.
		 */
		for (i = 0; i < root_comp_count; i++) {
			scriptwrite(script_fp, LEVEL0,
			    gen_installboot_i386,
			    "RAWROOT", root_comps[i], NULL);
		}
		stubrawroot = root_comps[0];
	} else {
		scriptwrite(script_fp, LEVEL0, gen_installboot_i386,
		    "RAWROOT", rootrawdev, NULL);
		stubrawroot = rootrawdev;
	}

	/*
	 * If there is a stub boot partition, we put grub there
	 * as well since it is likely the BIOS boot disk.
	 */
	if (stubmntdev) {
		scriptwrite(script_fp, LEVEL0, gen_installboot_stub,
		    "RAWROOT", stubrawroot, NULL);
	}
}

char *
get_failed_mntdev(void)
{
	return (err_mount_dev);
}

/*
 * returns filesystem type of specified path in a statically-allocated
 * buffer that the caller should not modify.
 */
char
*get_fs_type(char *path)
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
 * run_devmap_scripts()
 * Parameters:
 *	none
 * Return:
 *	int
 * Status:
 *	private
 */
static int
run_devmap_scripts()
{
	FILE *fp;
	DIR *dirp;
	struct dirent *dp;
	int status;
	char cmd[MAXPATHLEN];

	if ((dirp = opendir(DEVMAP_SCRIPTS_DIRECTORY)) == NULL) {
		return (ERR_NODIR);
	}

	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
		    strcmp(dp->d_name, "..") == 0)
			continue;

		(void) sprintf(cmd,
		    "%s/%s %s "
		    ">/dev/null 2>&1\n",
		    DEVMAP_SCRIPTS_DIRECTORY,
		    dp->d_name,
		    get_rootdir());

		if ((status = system(cmd)) != 0) {
			return (status);
		}
	}
	return (0);
}

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

	p = (struct stringlist *) xmalloc((size_t) sizeof (struct stringlist) +
				strlen(mntdev));
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

	exempt_swapdisk = GetExemptSwapdisk();
	if ((exempt_swapdisk != NULL) &&
	    (strcmp(mntdev, exempt_swapdisk) == 0)) {
		/* swapdisk and mntdev are equal do not add */
		return (0);
	}
	(void) snprintf(cmd, MAXPATHLEN,
	    "(/usr/sbin/swap -l 2>&1) | /bin/grep %s >/dev/null 2>&1", mntdev);
	if ((status = system(cmd)) != 0) {
		/* swap not already added */
		(void) snprintf(cmd, MAXPATHLEN,
		    "/usr/sbin/swap -a %s > /dev/null 2>&1", mntdev);
		if ((status = system(cmd)) != 0) {
			if (profile_upgrade)
				(void) printf(dgettext("SUNW_INSTALL_LIBSVC",
				    "Error adding swap, error = %x\n"),
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

	m = (struct mountentry *)xcalloc((size_t)sizeof (struct mountentry));
	m->op_type = SWAP_DEV;
	m->mntdev = xstrdup(mntdev);
	m->emnt = xstrdup(emnt);
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

	m = (struct mountentry *)xcalloc((size_t)sizeof (struct mountentry));
	m->op_type = MOUNT_DEV;
	m->mntpnt = xstrdup(basemount);
	m->mntdev = xstrdup(mntdev);
	m->fstype = xstrdup(fstype);
	m->options = xstrdup(options);
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
 * _set_mntdev_if_svm()
 *
 * Functin to determine if the mounted fs is a metadevice
 * If it is then mount it instead.
 * Parameters:
 *	basemount - the base to check for svm info
 *	mntopts - the options to use for the mount
 *	mntdev - the device path that is to be mounted
 *	fcskdev - the raw device that could be fsck'd
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
_set_mntdev_if_svm(char *basemount, char *mntopts, char **mntdev,
    char *fsckdev, int *md_comp_count, char ***md_comps)
{
	svm_info_t	*svminfo;
	int		i;
	char		compname[MAXPATHLEN+1];

	if (spmi_check_for_svm(basemount) == SUCCESS) {
		svminfo = spmi_svm_alloc();
		if (spmi_start_svm(basemount,
		    &svminfo, SVM_CONV) == SUCCESS) {
		    if (svminfo->count > 0) {
			/* root is a mirror */
			if (remount_svm(basemount,
			    svminfo, mntopts) == SUCCESS) {
				(void) sprintf(*mntdev,
				    "/dev/md/dsk/%s", svminfo->root_md);
				(void) sprintf(fsckdev, "/dev/md/rdsk/%s",
				    svminfo->root_md);
			}
			/*
			 * Remember component names in case we have to write the
			 * boot block to one or more mirror devices.  See
			 * gen_installboot for information about when this
			 * might happen.
			 */
			*md_comp_count = svminfo->count;
			*md_comps = (char **)
			    (xcalloc(svminfo->count * sizeof (char *)));
			for (i = 0; i < svminfo->count; i++) {
				(void) snprintf(compname, MAXPATHLEN,
				    "/dev/rdsk/%s", svminfo->md_comps[i]);
				(*md_comps)[i] = xstrdup(compname);

			}
			spmi_svm_free(svminfo);
			return (SUCCESS);
		    }
		    spmi_svm_free(svminfo);
		} else {
		    spmi_svm_free(svminfo);
		    return (FAILURE);
		}
	}
	/*
	 * No mirror, return success, meaning the ctds is OK
	 * to continue using
	 */
	*md_comp_count = 0;
	return (SUCCESS);
}
