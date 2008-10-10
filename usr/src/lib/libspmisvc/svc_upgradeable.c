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



/*
 * Module:	svc_upgradeable.c
 * Group:	libspmisvc
 * Description:	This module contains functions which are used to
 *		assess disks which are in an upgradeable condition.
 */

#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dlfcn.h>
#include <sys/fstyp.h>
#include <sys/fsid.h>
#include <sys/mnttab.h>
#include <sys/mntent.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/fs/ufs_fs.h>
#include "spmisvc_lib.h"
#include "spmistore_api.h"
#include "spmisoft_lib.h"
#include "spmicommon_api.h"
#include "svc_strings.h"
#include "instzones_api.h"

#ifndef	MODULE_TEST
/* public prototypes */

OSList		SliceFindUpgradeable(void);
StringList	*NonUpgradeableZonelist(void);
void		dump_upgradeable(OSList);

/* private prototypes */

static int 	hasSliceBeenFoundInSvm(char *, TList);
static char	*CheckSeparateVar(void);
static int	UfsIsUpgradeable(char *, char *, char *,
			int, char *, svm_info_t **, TList);
static int	InstanceIsUpgradeable(char *);
static int	MediaIsUpgradeable(char *);
static int	FindDeviceForMountedFS(char *, char *);
static void	IndirectFindUpgradeable(TList);

#endif

/* ---------------------- Test Interface ----------------------- */
#ifdef	MODULE_TEST
main(int argc, char **argv, char **env)
{

	OSList		oslist;
	Disk_t		*list = NULL;
	Disk_t		*dp;
	int		n;
	char 		*file = NULL;
	char 		*rootmount = "/a";

	while ((n = getopt(argc, argv, "x:dL")) != -1) {
		switch (n) {
		case 'd':
			(void) SetSimulation(SIM_SYSDISK, 1);
			file = xstrdup(optarg);
			(void) printf("Using %s as an input file\n", file);
			break;
		case 'x':
			(void) set_trace_level(atoi(optarg));
			break;
		case 'L':
			rootmount = "/";
			break;
		default:
			(void) fprintf(stderr,
		"Usage: %s [-x <level>] [-L] [-d <disk file>]\n",
				argv[0]);
			exit(1);
		}
	}

	set_rootdir(rootmount);
	z_set_zone_root(rootmount);

	/* initialize the disk list only for non-direct runs */
	if (!streq(rootmount, "/")) {
		n = DiskobjInitList(file);
		(void) printf("Disks found - %d\n", n);
	}

	oslist = SliceFindUpgradeable();

	dump_upgradeable(oslist);

	OSListFree(&oslist);
	exit(0);
}
#else
/* ---------------------- public functions ----------------------- */

/*
 * Function:	SliceFindUpgradeable
 * Description: This function operates either directly or indirectly:
 *
 *		INDIRECT
 *		--------
 *		Users must have called DiskobjInitList() to create the primary
 *		disk object list before calling this function. This assumes
 *		the primary disks are not currently mounted (i.e. indirect
 *		installation). Search all valid slices on all disks in the
 *		primary disk object list with legal sdisk configs for those
 *		containing a "/" file system in a condition suitable for
 *		upgrading to the current Solaris release. For each slice which
 *		is deemed upgradeable to the current release, add an entry
 *		in the StringList linked list, the head of which is returned
 *		by the call.
 *
 * 		NOTE:	The get_rootdir() directory is used during processing;
 *			any file systems mounted on that directory will be
 *			automatically unmounted.
 *
 *		DIRECT
 *		------
 *		This function is assumed to be running on a live system
 *		(upgrade dry-run) and all file systems are assumed to be
 *		mounted. In this case, get_rootdir() will return "/".
 *		No mounting or unmounting of file systems should occur
 *		when operating in this mode.
 *
 * Scope:	public
 * Parameters:	slices		[RO, *RW, **RW] (StringList **)
 *			Address of a StringList pointer used to retrieve
 *			the head of a linked list of upgradeable slices.
 *			If NULL, no slice data is to be returned.
 *		releases	[RO, *RW, **RW] (StringList **)
 *			Address of a StringList pointer used to retrieve
 *			the head of a linked list of releases positionaly
 *			corresponding to the slice in the slices list.
 *			If NULL, no release data is to be returned.
 * Return:	 none
 */
OSList
SliceFindUpgradeable(void)
{
	OSList		upgradeable;
	Disk_t 		*dp;
	char		rootdev[MAXNAMELEN+1];
	char		stubdev[MAXNAMELEN+1];
	int		stubpno = 0;
	char		release[256] = "";
	char		*c;

	/* initialize return values */
	OSListCreate(&upgradeable);

	/* always return TRUE for disk and execution simulations */
	if (GetSimulation(SIM_SYSDISK)) {
		OSListAdd(upgradeable, "", "", 0, "", NULL);
	} else if (DIRECT_INSTALL &&
	    FsCheckUpgradeability(release, NULL) == 0) {
		/*
		 * if this is a direct install and there is an upgradeable
		 * release, return the release and the slice corresponding
		 * to the currently mounted '/'
		 */
		(void) FindDeviceForMountedFS("/", rootdev);

		stubdev[0] = '\0';
		if (IsIsa("i386") &&
		    FindDeviceForMountedFS("/boot", stubdev)) {

			/*
			 * We just got `/dev/dsk/cxtxdxp0:boot'.  From that
			 * we need the actual partition number.
			 */
			if ((c = strrchr(stubdev, ':'))) {
				*c = '\0';

				if (!(dp = find_disk(stubdev))) {
					(void) strncpy(stubdev, disk_name(dp),
					    sizeof (stubdev));
					stubpno = get_stubboot_part(dp,
								    CFG_EXIST);
				} else {
					/*
					 * Illegal boot disk - erase entire
					 * slice.
					 */
					rootdev[0] = '\0';
					stubdev[0] = '\0';
				}
			} else {
				/* Illegal boot disk - erase entire slice */
				rootdev[0] = '\0';
				stubdev[0] = '\0';
			}
		}

		if (*stubdev) {
			OSListAdd(upgradeable, rootdev, stubdev,
			    stubpno, release, NULL);
		} else {
			OSListAdd(upgradeable, rootdev, NULL, 0,
			    release, NULL);
		}
	} else {
		IndirectFindUpgradeable(upgradeable);
	}

	return (upgradeable);
}

/*
 * Name:	SliceIsUpgradeable
 * Description:	Determine whether or not a single Solaris image is upgradeable.
 *		If it is upgradeable, a single-node OSList is returned
 *		containing information about the upgradeable image.  If not,
 *		NULL is returned.
 * Scope:	public
 * Parameters:	device	- [RO, *RO] (char *)
 *			  The device containing the image to check.  It
 *			  is assumed that the passed value is the name of a
 *			  slice containing the root filesystem of a Solaris
 *			  image.
 * Returns:	OSList	- a single-node OSList list containing information about
 *			  the upgradeable image.
 *		NULL	- the image is not upgradeable
 */
OSList
SliceIsUpgradeable(char *device)
{
	OSList		upgradeable;
	TList		svmlist;
	char		release[256] = "";
	Disk_t		*dp;
	char		*rootdev, *slice;
	int		sbpno, rootpno = 0, rootslc = 0;
	int		rc;
	svm_info_t 	*svminfo;

	/* Create the svmlist */
	OSListCreate(&svmlist);
	OSListCreate(&upgradeable);

	if (disk_fdisk_req(first_disk())) {
		/*
		 * We have a pointer to a Solaris root slice (or at least we
		 * think we do).  Go see if there's a stub that points to it.
		 */
		WALK_DISK_LIST(dp) {
			WALK_PARTITIONS(sbpno) {

				if (part_id(dp, sbpno) != X86BOOT) {
					continue;
				}

				/* Found one.  What does it point to? */
				if (!StubBootGetBootpath(disk_name(dp), sbpno,
				    &rootdev, &rootpno, &rootslc)) {
					/* Nothing */
					continue;
				}

				/* Does it point to the specified slice? */
				slice =
				    xstrdup(make_slice_name(rootdev, rootslc));
				if (!streq(slice, device)) {
					/* Nope */
					free(slice);
					continue;
				}

				/*
				 * check to make sure it is not a
				 * component of a previously looked
				 * at mirrored root
				 */
				if ((hasSliceBeenFoundInSvm(slice,
				    svmlist) == FALSE) &&
				    (hasSliceBeenFoundInSvm(slice,
					upgradeable) == FALSE)) {
					/*
					 * We've found the stub, so check
					 * upgradeability for the whole mess.
					 */
					release[0] = '\0';
					/*
					 * allocate the svminfo to be
					 * used throughout
					 */
					svminfo = spmi_svm_alloc();
					rc = UfsIsUpgradeable(slice, NULL,
					    disk_name(dp), sbpno, release,
					    &svminfo, svmlist);
					free(slice);

					if (rc == 1) {
						/* Upgradeable */
						OSListAdd(upgradeable,
						    make_slice_name(rootdev,
							rootslc),
						    disk_name(dp),
						    sbpno, release, svminfo);
						return (upgradeable);
					} else {
						/* don't need it, free it */
						spmi_svm_free(svminfo);
					}
				}
			}
		}

		/*
		 * If we got to this point, we've searched for stubs that point
		 * to our specified root slice, and have failed to find one.
		 * We therefore continue on, assuming that this is a root slice
		 * without a stub.  If that turns out not to be the case - if
		 * this root is supposed to have a stub, but the callous user
		 * blew it away - the upgradeability check will fail when it
		 * discovers that /boot is unpopulated.
		 */
	}

	/*
	 * check to make sure it is not a
	 * component of a previously looked
	 * at mirrored root
	 */
	if ((hasSliceBeenFoundInSvm(device, svmlist) == FALSE) &&
	    (hasSliceBeenFoundInSvm(device, upgradeable) == FALSE)) {
		release[0] = '\0';
		svminfo = spmi_svm_alloc();
		if (UfsIsUpgradeable(device, NULL,
		    NULL, 0, release, &svminfo, svmlist) == 1) {
			/* Upgradeable */
			OSListAdd(upgradeable, device, NULL,
			    0, release, svminfo);
			OSListFree(&svmlist);
			return (upgradeable);
		} else {
			OSListFree(&svmlist);
			return (NULL);
		}
	}
	/* Free the oslist since we didn't find any */
	OSListFree(&upgradeable);
	return (NULL);
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	CheckSeparateVar
 * Description: Check the /etc/vfstab file under the current get_rootdir() and
 *		see if it contains a separate active "/var" file system mount
 *		entry. Return the block special device if there is one.
 * Scope:	private
 * Parameters:	none
 * Return:	NULL	- no separate /var entry found
 *		!NULL	- pointer to string containing block special
 *			  device for the "/var" entry
 */
static char *
CheckSeparateVar(void)
{
	static char	emnt[MAXPATHLEN + 1];
	char		buf[MAXPATHLEN + 1];
	FILE		*fp;
	char		*pdev;
	char 		*pfs;

	emnt[0] = '\0';

	(void) snprintf(buf, sizeof (buf), "%s%s", get_rootdir(), VFSTAB);
	if ((fp = fopen(buf, "r")) != NULL) {
		while (fgets(buf, 255, fp) != NULL) {
			if (((pdev = strtok(buf, " \t")) != NULL) &&
			    is_pathname(pdev) &&
			    (strtok(NULL, " \t") != NULL) &&
			    ((pfs = strtok(NULL, " \t")) != NULL) &&
			    streq(pfs, VAR)) {

				/*
				 * Found a separate /var.  Map the device name
				 * to the effective device name if needed
				 * (not needed for VXFS)
				 */
				if (strneq(pdev, "/dev/vx/", 8)) {
					(void) strcpy(emnt, pdev);
				} else {
					(void) _map_to_effective_dev(pdev,
								    emnt);
				}
				break;
			}
		}

		(void) fclose(fp);
	}

	if (emnt[0] == '\0')
		return (NULL);

	return (emnt);
}

/*
 * Function:	UfsIsUpgradeable
 * Description: Mount a slice which represents a UFS "/" file system, and check
 *		to see if it has a "/var" directory configured for upgrading.
 *		The slice is mounted on get_rootdir(). If "/var" is a separate
 *		file system, it is mounted before the verification is performed.
 *
 *		If the slice device specified is a simple slice name (e.g.
 *		c0t3d0s3), the block special device used for mounting is
 *		assumed to exist in /dev/dsk. Otherwise, the user supplied
 *		fully qualified path name is used.
 *
 *		NOTE:	Any file system mounted on get_rootdir() at the time
 *			this function is invoked will automatically be unmounted
 * Scope:	private
 * Parameters:	bdevice	[RO, *RO]
 *			Slice device name for which the block device will be
 *			used for the validation. The device may either be
 *			specified in relative (e.g. c0t3d0s4) or absolute (e.g.
 *			/dev/dsk/c0t3d0s4) form.
 *		cdevice	[RO, *RO] (optional)
 *			Absolute path name for the character device to be used
 *			for restoring the last-mounted-on name for the file
 *			system. This is only specified if the block device is
 *			specified as an absolute path name; otherwise, the value
 *			should be passed as NULL.
 *		release	[RO, *RW] (char *)
 *			Pointer to a character buffer of size 32 used to
 *			retrieve the name of the release associated with the
 *			upgradeable slice. NULL if this information is not
 *			requested. Set to "" if the information is requested
 *			but is not available.
 * Return:	1	- the file system is upgradeable
 *		0	- the file system is not upgradeable
 */
static int
UfsIsUpgradeable(char *bdevice, char *cdevice, char *stubdevice, int stubpno,
		char *release, svm_info_t **svminfo, OSList svmlist)
{
	char		*vardev = NULL;
	char 		mntpnt[MAXPATHLEN+1];
	int		okay = 0;
	int 		svm_started = FALSE;

	/* validate parameters */
	if (is_slice_name(bdevice)) {
		if (cdevice != NULL)
			return (0);
	} else if (is_pathname(bdevice)) {
		if (!is_pathname(cdevice))
			return (0);
	} else {
		return (-1);
	}

	if (get_trace_level() > 5)
		write_status(LOGSCR, LEVEL0,
			"Checking upgradeability for %s\n", bdevice);

	/* always return TRUE for disk and execution simulations */
	if (GetSimulation(SIM_EXECUTE) || GetSimulation(SIM_SYSDISK))
		return (1);

	/* make sure the assembly mount point is cleared */
	if (UmountAllZones(get_rootdir()) != 0 ||
	    DirUmountAll(get_rootdir()) < 0) {
		write_status(LOG, LEVEL1, MSG0_UNABLE_TO_CLEAR_ROOTDIR,
		    get_rootdir());
		return (0);
	}

	/* try to mount the root file system on the get_rootdir() directory */
	if (UfsMount(bdevice, get_rootdir(), "-r") < 0 &&
	    FsMount(bdevice, get_rootdir(), "-r", NULL)) {
		return (0);
	}

	write_status(LOG, LEVEL0, MSG0_UPG_CHECKING_FS, bdevice);

	/* look for SVM devices on the mounted rootdir */
	if (spmi_check_for_svm(get_rootdir()) == SUCCESS) {
		if (spmi_start_svm(get_rootdir(), svminfo,
		    SVM_DONT_CONV) == SUCCESS) {
			/*
			 * If svm->count is > 0, then the volume
			 * in question is a mirror. Otherwise,
			 * the root does not have a mirror but
			 * has some other kind of metadevice.
			 * if it is a mirror, add it to the svmlist
			 */
			if ((*svminfo)->count > 0) {
				if (get_trace_level() > 5)
					write_status(LOGSCR, LEVEL0,
					    "svm_start succeeded, adding "
					    "svminfo to svmlist\n");
				OSListAdd(svmlist,
				    NULL,
				    NULL,
				    NULL,
				    NULL,
				    *svminfo);

				/* add components of it here */
				if (remount_svm(get_rootdir(),
				    *svminfo, "ro") != SUCCESS) {
					return (0);
				} else {
					if (get_trace_level() > 5)
						write_status(LOGSCR, LEVEL0,
						    "SPMI_SVC_UPGRADEABLE: "
						    "UfsIsUpgradeable() : "
						    "Mounted /dev/md/dsk/%s "
						    "on %s\n",
						    (*svminfo)->root_md,
						    get_rootdir());
				}
				svm_started = TRUE;
			}
		} else {
			/* it failed, but add it to the svm list anyway */
			if ((*svminfo)->count > 0) {
				if (get_trace_level() > 5)
					write_status(LOGSCR, LEVEL0,
					    "SPMI_SVC_UPGRADEABLE: "
					    "UfsIsUpgradeable() :check "
					    "succeeded but start failed\n");
				OSListAdd(svmlist,
				    NULL,
				    NULL,
				    NULL,
				    NULL,
				    *svminfo);
				write_status(LOG, LEVEL1,
				    MSG0_SVM_START_FAILED,
				    (*svminfo)->root_md, bdevice);
			} else {
			    write_status(LOG, LEVEL1,
				MSG0_SVM_START_FAILED, "unknown", bdevice);
			}
			svminfo = NULL;
			(void) FsUmount(get_rootdir(), ROOT,
						cdevice ? cdevice : bdevice);
			return (0);
		}
	} else {
		svminfo = NULL;
	}

	/* if there is a stub boot filesystem, mount it */
	if (stubdevice) {
		(void) snprintf(mntpnt, sizeof (mntpnt),
				"%s%s", get_rootdir(), BOOT);
		if (StubBootMount(make_device_name(stubdevice, stubpno),
				mntpnt, "-r") < 0) {
			(void) FsUmount(get_rootdir(), ROOT,
						cdevice ? cdevice : bdevice);
			write_status(LOG, LEVEL1, MSG0_CANT_MOUNT_STUBBOOT);
			return (0);
		}
	}

	/* if there is a separate /var file system, mount it */
	if ((vardev = CheckSeparateVar()) != NULL) {
		/* make sure there is a /var directory for mounting */
		(void) snprintf(mntpnt, sizeof (mntpnt),
				"%s%s", get_rootdir(), VAR);
		if (FsMount(vardev, mntpnt, "-r", "ufs") < 0) {
			if (stubdevice) {
				(void) StubBootUmount(
					make_device_name(stubdevice, stubpno));
			}
			if (svm_started == TRUE) {
				if (spmi_stop_svm(bdevice, get_rootdir()) !=
				    SUCCESS) {
					write_status(LOG, LEVEL1,
					    MSG0_SVM_STOP_FAILED,
					    bdevice);
				}
			}
			(void) FsUmount(get_rootdir(), ROOT,
						cdevice ? cdevice : bdevice);
			write_status(LOG, LEVEL1, MSG0_CANT_MOUNT_VAR,
			    bdevice);
			return (0);
		}
	}

	if (FsCheckUpgradeability(release, NULL) == 0)
		okay = 1;

	/* do some stub-related checks and unmount the stub (if any) */
	if (stubdevice) {
		char longrel[256];
		int rc;

		(void) snprintf(longrel, sizeof (longrel),
				"Solaris_%s", release);
		rc = prod_vcmp(longrel, "Solaris_2.7");
		if (okay && rc == V_LESS_THEN) {
			/*
			 * We have a stub that points to a pre-2.7 root.
			 * This is a bad thing, and shouldn't happen.
			 */
			write_status(LOG, LEVEL1, MSG0_STUB_NOT_SUPPORTED,
			    longrel);
			okay = 0;
		}

		/* unmount the stub */
		(void) StubBootUmount(make_device_name(stubdevice, stubpno));

		/*
		 * Check to see if we have an orphan stub.  We have an orphan
		 * stub if the root filesystem it points to has a populated
		 * /boot directory.
		 */
		if (okay && BootenvExists()) {
			/* We have an orphan.  Don't let them upgrade it */
			write_status(LOG, LEVEL1, MSG0_DANGLING_STUB,
			    get_rootdir(), "/boot/solaris/bootenv.rc");
			okay = 0;
		}
	}

	/* unmount /var if it is a separate file system */
	if (vardev != NULL)
		(void) UfsUmount(vardev, NULL, NULL);

	/*
	 * stop SVM if it was started, this also
	 * mounts the ctds back on rootdir
	 */
	if (svm_started == TRUE) {
		if (spmi_stop_svm(bdevice, get_rootdir()) != SUCCESS) {
			write_status(LOG, LEVEL1, MSG0_SVM_STOP_FAILED,
			    bdevice);
			okay = 0;
		}
	}

	/* unmount "/" */
	(void) FsUmount(get_rootdir(), ROOT, cdevice ? cdevice : bdevice);
	return (okay);
}

/*
 * Function:	InstanceIsUpgradeable
 * Description:	Check to see if there is an INST_RELEASE file relative to
 *		get_rootdir(), and if there is, check to see if the version is
 *		considered acceptable for upgrading. Requirements for
 *		upgradeability are:
 *
 *		(1) SPARC	- all versions after 2.0
 *		(2) Intel	- all versions 2.4 and later, except
 *				  for 2.4 and 2.5 system with a revision 100
 *				  (Core)
 *		(3) PowerPC	- all versions
 * Scope:	private
 * Parameters:	release	[RO, *RW] (char *)
 *			Pointer to a 32 character buffer used to retrieve the
 *			name of the release instance. NULL if this information
 *			is not requested. Set to "" if this information is
 *			requested, but is not available.
 * Return:	1	- the current release is upgradeable
 *		0	- the current release is not upgradeable
 */
static int
InstanceIsUpgradeable(char *release)
{
	char	line[32];
	FILE	*fp;
	int	upgradeable = 0;
	int	minor;

	if (release != NULL)
		release[0] = '\0';

	if ((fp = fopen(INST_RELEASE_read_path(""), "r")) == NULL) {
		return (0);
	}

	/* First line must be OS=Solaris */
	if (fgets(line, sizeof (line), fp) == NULL ||
	    strneq(line, "OS=Solaris", 10) == 0) {
		(void) fclose(fp);
		return (0);
	}

	/* Second line must be VERSION= (actual number checked below) */
	if (fgets(line, sizeof (line), fp) == NULL ||
	    strneq(line, "VERSION=", 8) == 0) {
		(void) fclose(fp);
		return (0);
	}

	/* clear out the newline */
	line[strlen(line) - 1] = '\0';

	/* Version can be either x or x.y */
	if (isdigit(line[8]) && line[9] == '.' && isdigit(line[10])) {
		minor = atoi(&line[10]);
	} else if (isdigit(line[8])) {
		minor = atoi(&line[8]);  /* !@#$ */
	} else {
		(void) fclose(fp);
		return (0);
	}

	/* don't allow downgrades (system release > media) */
	if (!MediaIsUpgradeable(&line[8])) {
		(void) fclose(fp);
		return (0);
	}

	/* return the release version if requested */
	if (release != NULL)
		(void) strcpy(release, &line[8]);

	/* Determine whether or not it's upgradeable */
	if (IsIsa("sparc")) {
		if (minor > 0)
			upgradeable = 1;
	} else if (IsIsa("i386")) {
		/*
		 * all Intel releases > 2.3 are upgradeable
		 * except for those with REV=100 (Solaris Base)
		 */
		if (minor > 3) {
			if (fgets(line, sizeof (line),
			    fp) == NULL ||
			    !strneq(line, "REV=", 4) ||
			    !isdigit(line[5]) ||
			    atoi(&line[4]) != 100)
				upgradeable = 1;
		}
	}

	(void) fclose(fp);

	/* clear release value if not upgradeable */
	if ((upgradeable == 0) && (release != NULL))
		release[0] = '\0';

	return (upgradeable);
}

/*
 * Function:	FsCheckUpgradeability
 * Description:	Check to see that the clustertoc is readable and the
 *		instance is considered to be upgradeable.
 * Scope:	private
 * Parameters:	release	[RO, *RW] (char *)
 *			Pointer to a character buffer of size 32 used to
 *			retrieve the name of the release associated with the
 *			upgradeable slice. NULL if this information is not
 *			requested. Set to "" if the information is requested
 *		rootdir - instance is mounted on rootdir.  If NULL, the
 *			current get_rootdir() dir is used.
 * Return:	 0	Upgradeability checks passed
 *		-1	Upgradeability checks failed
 */
int
FsCheckUpgradeability(char *release, char *rootdir)
{
	char longrel[256];
	int rc;
	char *oldroot = NULL;

	if (rootdir != NULL) {
		oldroot = get_rootdir();
		set_rootdir(rootdir);
		z_set_zone_root(rootdir);
	}

	/* check the upgradeability criteria */
	(void) snprintf(longrel, sizeof (longrel), "Solaris_%s", release);

	/* Does it have .clustertoc and CLUSTER files? */
	if (access(clustertoc_read_path(""), F_OK) != 0 ||
	    access(CLUSTER_read_path(""), F_OK) != 0) {
		write_status(LOG, LEVEL1, MSG0_CANT_READ_CLUSTERTOC);
		if (oldroot != NULL) {
			set_rootdir(oldroot);
			z_set_zone_root(oldroot);
		}
		return (-1);
	}

	/* Can it be upgraded to this version? */
	if (InstanceIsUpgradeable(release) == 0) {
		write_status(LOG, LEVEL1, MSG0_INSTANCE_NOT_UPGRADEABLE,
		    release);
		if (oldroot != NULL) {
			set_rootdir(oldroot);
			z_set_zone_root(oldroot);
		}
		return (-1);
	}

	/* Does it have usr packages? */
	if (UsrpackagesExist(NULL) == 0) {
		write_status(LOG, LEVEL1, MSG0_CANT_FIND_REQ_USR_PKGS);
		if (oldroot != NULL) {
			set_rootdir(oldroot);
			z_set_zone_root(oldroot);
		}
		return (-1);
	}

	/* Check for /boot/solaris/bootenv.rc if warranted (Intel >=2.7) */
	if (IsIsa("i386")) {
		rc = prod_vcmp(longrel, "Solaris_2.7");
		if (rc == V_GREATER_THEN || rc == V_EQUAL_TO) /* sic */
			if (BootenvExists() == 0) {
				write_status(LOG, LEVEL1, MSG0_NO_BOOTENV,
				    get_rootdir(), "/boot/solaris/bootenv.rc");
				if (oldroot != NULL) {
					set_rootdir(oldroot);
					z_set_zone_root(oldroot);
				}
				return (-1);
			}
	}

	if (oldroot != NULL) {
		set_rootdir(oldroot);
		z_set_zone_root(oldroot);
	}
	return (0);
}

/*
 * Function:	MediaIsUpgradeable
 * Description:	Boolean function used to assess if the current release
 *		of the system is considered upgradeable in the context
 *		of current system release.
 * Scope:	private
 * Parameters:	sysver [RO, *RO] (char *)
 *			Non-NULL string containing the release of the current
 *			machine (e.g. "2.5").
 * Return:	0	The media is not upgradeable from the current
 *			system configuration.
 *		1	The media is upgradeble.
 */
static int
MediaIsUpgradeable(char *sysver)
{
	Module	*mod;
	char 	*mediaver = NULL;
	int	status;
	char	sysprod_ver[256], mediaprod_ver[256];

	/*
	 * validate parameters - if the system version is not specified,
	 * then we assume no upgradeability because we don't have
	 * enough information to assess upgradeability (error
	 * conservatively)
	 */
	if (sysver == NULL)
		return (0);

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type != INSTALLED_SVC &&
			    mod->info.media->med_type != INSTALLED &&
			    mod->sub->type == PRODUCT &&
			    streq(mod->sub->info.prod->p_name, "Solaris"))
			mediaver = mod->sub->info.prod->p_version;
	}

	/*
	 * compare media versions (if available media) for a constraint
	 */
	if (mediaver != NULL) {
		(void) strcpy(sysprod_ver, "Solaris_");
		(void) strcat(sysprod_ver, sysver);
		(void) strcpy(mediaprod_ver, "Solaris_");
		(void) strcat(mediaprod_ver, mediaver);
		status = prod_vcmp(sysprod_ver, mediaprod_ver);
		if (status == V_GREATER_THEN || status == V_NOT_UPGRADEABLE)
			return (0);
	}

	return (1);
}

/*
 * Function:	FindDeviceForMountedFS
 * Description:	Look for a filesystem with the given name in the
 *		mnttab.  If it's there, return the device from
 *		which it's mounted.
 * Scope:	private
 * Parameters:	fs	- [RO, *RO] (char *)
 *			  The filesystem to look for
 *		device	- [RO, *RW] (char *)
 *			  A buffer into which the device name (if any)
 *			  should be copied.  Not touched if `fs' isn't
 *			  the root of a filesystem.
 * Return:	0	`fs' is not the mount point for a filesystem
 *		1	Filesystem found, and device name returned.
 */
static int
FindDeviceForMountedFS(char *fs, char *device)
{
	struct mnttab	mnt;
	struct mnttab	mpref;
	FILE 		*mntp;
	char 		*cp;
	int		found = 0;

	if ((mntp = fopen(MNTTAB, "r")) != NULL) {
		mpref.mnt_mountp = xstrdup(fs);
		mpref.mnt_special = NULL;
		mpref.mnt_fstype = NULL;
		mpref.mnt_mntopts = NULL;
		mpref.mnt_time = NULL;

		if (getmntany(mntp, &mnt, &mpref) == 0 &&
		    (cp = strrchr(mnt.mnt_special, '/')) != NULL) {
			(void) strcpy(device, cp + 1);
			found = 1;
		}

		(void) fclose(mntp);
	}
	return (found);
}

/*
 * Function:	IndirectFindUpgradeable
 * Description:	Look for a stub boot partition that points to a root filesystem
 *		or a root filesystem that isn't pointed to by a stub boot
 *		partition.  For each such root filesystem, check to see if they
 *		are upgradeable.
 * Scope:	private
 * Parameters:	upgradeable	- [RO, *RW] (OSList)
 *			  The list of upgradeable images.  The list must be
 *			  initialized (via OSListCreate) prior to the invocation
 *			  of this function.
 * Return:	none
 */
static void
IndirectFindUpgradeable(TList upgradeable)
{
	char		release[256] = "";
	char		**stubtgts = NULL;
	char		*rootdev;
	char		*slice;
	int		rootpno, rootslc;
	int 		i, s;
	int		stubpno;
	int		stubtgtcnt = 0;
	Disk_t		*dp, *stubdp, *soldp;
	svm_info_t	*svminfo;
	OSList		svmlist;

	/* Create the svmlist to maintain */
	OSListCreate(&svmlist);

	/* Look for stub boot partitions */
	if (disk_fdisk_req(first_disk())) {
		WALK_DISK_LIST(stubdp) {
			WALK_PARTITIONS(stubpno) {
				if (part_id(stubdp, stubpno) == X86BOOT &&
				    StubBootGetBootpath(disk_name(stubdp),
					stubpno,
					&rootdev, &rootpno,
					&rootslc)) {

					/*
					 * Make sure we know about the root,
					 * and that it's on a valid disk.
					 */
					if (!(soldp = find_disk(rootdev)) ||
					    !disk_okay(soldp) ||
					    sdisk_geom_null(soldp) ||
					    !sdisk_legal(soldp) ||
					    slice_locked(soldp, rootslc) ||
					    !streq(orig_slice_mntpnt(soldp,
						rootslc),
						ROOT)) {
						continue;
					}

					/*
					 * Add this stub/root pair to the list
					 * of pairs so we can skip this root
					 * later (when we scan for roots that
					 * don't have boots)
					 */
					stubtgts = (char **)xrealloc(stubtgts,
					    sizeof (char *) * (stubtgtcnt + 1));

					slice = stubtgts[stubtgtcnt++] =
					    xstrdup(make_slice_name(rootdev,
								    rootslc));
					/*
					 * check to make sure it is not a
					 * component of a previously looked
					 * at mirrored root
					 */
					if ((hasSliceBeenFoundInSvm(slice,
					    svmlist) == FALSE) &&
					    (hasSliceBeenFoundInSvm(slice,
						upgradeable) == FALSE)) {
						release[0] = '\0';
						svminfo = spmi_svm_alloc();
						if (!UfsIsUpgradeable(slice,
						    NULL,
						    disk_name(stubdp),
						    stubpno, release,
						    &svminfo, &svmlist))
							continue;

						/*
						 * The pair can be upgraded,
						 * so add them
						 * to the list.
						 */
						OSListAdd(upgradeable,
						    make_slice_name(
							    rootdev,
								rootslc),
						    disk_name(stubdp),
						    stubpno,
						    release,
						    svminfo);
					}
				}
			}
		}
	}

	/*
	 * process all disks with legal sdisk configurations looking
	 * for at least one slice on the disk which contains a "/"
	 * file system which is in an upgradeable condition.
	 */
	WALK_DISK_LIST(dp) {
		/* Is it legal? */
		if (!disk_okay(dp) || sdisk_geom_null(dp) ||
		    !sdisk_legal(dp))
			continue;

		/*
		 * walk all slices looking for an unlocked slice which
		 * has "/" as it's existing mount point.  If said slice
		 * is the target of a stub boot partition, skip it.  If not,
		 * Check to see if the slice is upgradeable.  If it is, add
		 * it to the list.
		 */
		WALK_SLICES(s) {
			release[0] = '\0';
			/* check slice viability and upgradeability */
			slice = make_slice_name(disk_name(dp), s);
			/*
			 * check to make sure it is not a
			 * component of a previously looked
			 * at mirrored root
			 */
			if ((hasSliceBeenFoundInSvm(slice,
			    svmlist) == FALSE) &&
			    (hasSliceBeenFoundInSvm(slice,
				upgradeable) == FALSE)) {
				/* Make sure it's not a stub boot target */
				for (i = 0; i < stubtgtcnt; i++)
					if (streq(slice, stubtgts[i]))
						break;
				if (i != stubtgtcnt)
					/* Slice is a stub boot target */
					continue;

				/* create the svminfo struct for use later */
				svminfo = spmi_svm_alloc();
				if (!slice_locked(dp, s) &&
				    streq(orig_slice_mntpnt(dp, s), ROOT) &&
				    UfsIsUpgradeable(slice,
					NULL, NULL, 0,
					release, &svminfo, svmlist)) {
					OSListAdd(upgradeable, slice,
					    NULL, 0, release,
					    svminfo);
				} else {
					spmi_svm_free(svminfo);
				}
			}
		}
	}

	/* Free the stub target list */
	for (i = 0; i < stubtgtcnt; i++)
		free(stubtgts[i]);

	OSListFree(&svmlist);
	free(stubtgts);
}


/*
 * Function:	hasSliceBeenFoundInSvm
 * Description: Looks at a ctds and determines if it has already
 *		  been found, if it has then returns TRUE
 * Scope:	public
 * Parameters:  rootslice - non-NULL cXtXdXsX string
 *		list - list of known OSLists's
 *
 * Return:	TRUE
 *		FALSE
 */
static int
hasSliceBeenFoundInSvm(char *rootslice, OSList list)
{

	TLink		curnode;
	TLLError	err;
	OSListItem	*oli;
	int 		i;

	if (OSListCount(list) > 0) {
		LL_WALK(list, curnode, oli, err) {
			if (oli != NULL && oli->svminfo != NULL) {
				for (i = 0; i < oli->svminfo->count; i++) {
					if (strcasecmp(
						oli->svminfo->md_comps[i],
						    rootslice) == 0) {
						if (get_trace_level() > 5)
							write_status(LOGSCR,
							    LEVEL0,
			"SPMI_SVC_UPGRADEABLE: hasSliceBeenFoundInSvm() "
			"found %s in oli, md is %s",
							    rootslice,
							    oli->svminfo->
							    md_comps[i]);
						return (TRUE);
					}
				}
			}
		}
	}
	return (FALSE);
}

void
dump_upgradeable(OSList oslist)
{
	TLink		curnode;
	TLLError	err;
	OSListItem	*data;
	int		n;

	n = OSListCount(oslist);

	write_status(LOGSCR, LEVEL1,
	    "%d Upgradeable Image%s\n", n, (n == 1) ? "" : "s");

	if (n) {
		LL_WALK(oslist, curnode, data, err) {
			if (sliceExistsInSvm(data->rootslice,
			    data->svminfo) == TRUE) {
				write_status(LOGSCR, LEVEL1,
				    "\tRoot slice: %s",
				    data->rootslice);
				write_status(LOGSCR, LEVEL1,
				    "mirrored root device : %s",
				    data->svminfo->root_md);
				write_status(LOGSCR, LEVEL1,
				    "svmstring : %s",
				    data->svmstring);
			} else {
				write_status(LOGSCR, LEVEL1,
				    "root slice : %s", data->rootslice);
			}
			if (data->stubdevice) {
				write_status(LOGSCR, LEVEL1,
				    "\tStub device: %s",
				    data->stubdevice);
				write_status(LOGSCR, LEVEL1,
				    "\tStub partno: %d",
				    data->stubpartno);
			}
			write_status(LOGSCR, LEVEL1,
			    "release: %s\n\n", data->release);
		}
	}
}

/*
 * Function:	NonUpgradeableZonelist
 * Description:	Takes a mounted slice which represents a UFS "/" file system,
 * 		check for any viable Solaris zones which are not upgradeable
 *
 * Scope:	private
 * Parameters:	NONE
 * Return:	NULL	- any and all non-global zones that should be upgraded
 * 			are upgradeable (or no non-local zones at all)
 *		StringList * - at least one zone should be
 *			upgradeable but is not upgradeable
 *			List of zones-if not NULL, should be returned to heap
 *
 * Upgradeability criteria. Candidate zones must be:
 * 	o non-global zones
 * 	o installed
 * Disqualification criteria.
 * 	o SUNWcsu package directory missing
 */
StringList *
NonUpgradeableZonelist()
{
	zoneList_t	zoneList;
	int		zoneIndex;
	char		*zonename;
	char		*zname;
	StringList	*zoneStringList = NULL;

	if (z_zones_are_implemented() == B_FALSE) {
		return (NULL); /* no non-upgradeable zones */
	}
	z_set_zone_root(get_rootdir());

	if ((zoneList = z_get_nonglobal_zone_list()) == NULL) {
		write_status(LOG, LEVEL1,
			MSG0_COULD_NOT_GET_NONGLOBAL_ZONE_LIST);
		return (NULL);	/* no alternate zones */
	}

	/* scan all non-global zones */

	for (zoneIndex = 0;
		(zonename = z_zlist_get_zonename(zoneList, zoneIndex)) != NULL;
		zoneIndex++) {

		/* non-global zone - installed? */

		if (z_zlist_get_current_state(zoneList, zoneIndex) <
				ZONE_STATE_INSTALLED) {
			write_status(LOG, LEVEL1,
				MSG0_ZONE_NOT_INSTALLED, zonename);
			continue;
		}

		/*
		 * zone must be upgradeable - identify anything wrong
		 * that would break an upgrade
		 */

		/*
		 * If root mounted on an alternate root,
		 * get the scratchname.
		 */
		if (!streq(get_rootdir(), "/")) {
			zname = z_zlist_get_scratch(zoneList, zoneIndex);
			if (zname == NULL) {
				write_notice(ERRMSG,
				    MSG1_COULD_NOT_GET_SCRATCHNAME, zonename);
				continue;
			}
		} else {
			zname = zonename;
		}

		if (UsrpackagesExist(zname) == 0) {
			/* add zonename to list of nonupgradeable zones */
			StringListAdd(&zoneStringList, zonename);

			write_status(LOG, LEVEL1, MSG0_MISSING_ZONE_PKG_DIR,
			    zonename);
			continue; /* finish zone scan for messages */
		}

		/* non-global zone is upgradeable */

		write_status(LOG, LEVEL1, MSG0_ZONE_UPGRADEABLE, zonename);
	}

	(void) z_free_zone_list(zoneList);

	return (zoneStringList);
}
#endif /* MODULE_TEST */
