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
 * Module:	common_mount.c
 * Group:	libspmicommon
 * Description: Contains all functions used to mount, unmount, and
 *		otherwise deal with special devices containing file
 *		systems.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/fstyp.h>
#include <sys/fsid.h>
#include <sys/mount.h>
#include <sys/mnttab.h>
#include <sys/mntent.h>
#include <sys/statvfs.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/fs/ufs_fs.h>
#include "spmicommon_lib.h"

/* public prototypes */

int		FsMount(char *, char *, char *, char *);
int		FsUmount(char *, char *, char *);
int		UfsRestoreName(char *, char *);
int		UfsMount(char *, char *, char *);
int		UfsUmount(char *, char *, char *);
int		DirUmountAll(char *);
int		DirUmount(char *);

/* local prototypes */

static int	DirUmountRecurse(FILE *, char *);

/* ---------------------- public functions ----------------------- */

/*
 * Function:	FsMount
 * Description:	Mount a block special device containing a file system. If
 *		the file system type is unspecified, all possible file
 *		system types are tried until one successfully mounts or
 *		all possibilities are exhausted. If the special device name
 *		specified is a simple slice device name (e.g. c0t3d0s3), the
 *		block special device is assume to exist in /dev/dsk. Otherwise,
 *		the user may supply a fully qualified path name to the block
 *		special device.
 *
 *		NOTE: This function explicitly uses the "mount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.  The caller
 *			of this function is responsible for making sure that
 *			the device name is appropriate for the filesystem
 *			being mounted.
 *		mntpnt	[RO, *RO]
 *			UNIX path name for the mount point directory. This
 *			will be prepended with get_rootdir() by the function
 *			before mounting.
 *		mntopt	[RO, *RO] (optional)
 *			Mount options. If NULL specified, then "mount" command
 *			defaults are used. Options should appear as they would
 *			on the mount line (e.g. "-r").
 *		fstype	[RO, *RO] (optional)
 *			File system type specifier (e.g. "ufs"). If none
 *			is specified, a mount attempt is made for each type
 *			which is defined on the system.
 * Return:	 0	- mount was successful
 *		-1	- mount failed
 */
int
FsMount(char *device, char *mntpnt, char *mntopts, char *fstype)
{
	struct stat	sbuf;
	char	cmd[MAXPATHLEN];
	char	fsname[MAXNAMELEN];
	char	disk[MAXNAMELEN];
	int	n;
	int	i;

	/* validate parameters */
	if (!is_pathname(mntpnt) || (stat(mntpnt, &sbuf) < 0) ||
			((sbuf.st_mode & S_IFDIR) == 0))
		return (-1);

	/* create the block special disk device name */
	if (!is_pathname(device))
		(void) snprintf(disk, MAXNAMELEN, "/dev/dsk/%s", device);
	else
		(void) strcpy(disk, device);

	/*
	 * if no file system type is specified, run through all possible
	 * types until the mount works or there are no more types
	 */
	if (fstype == NULL) {
		n = sysfs(GETNFSTYP);
		for (i = 0; i < n; i++) {
			if (sysfs(GETFSTYP, i, fsname) == 0) {
				/*
				 * Before mounting ufs/cachefs file systems
				 * make sure they are clean and mountable
				 */
				if (streq(fsname, "ufs") ||
				    streq(fsname, "cachefs")) {
					(void) snprintf(cmd, MAXPATHLEN,
					    "fsck -F %s -m %s >/dev/null 2>&1",
					    fsname, disk);
					if (WEXITSTATUS(system(cmd)) != 0)
						continue;
				}
				(void) snprintf(cmd, MAXPATHLEN,
				    "mount -F %s %s %s %s >/dev/null 2>&1",
				    fsname, mntopts == NULL ? "" : mntopts,
				    disk, mntpnt);
				if (WEXITSTATUS(system(cmd)) == 0)
					return (0);
			}
		}
	} else {
		/*
		 * Before mounting ufs/cachefs file systems
		 * make sure they are clean and mountable
		 */
		if (streq(fstype, "ufs") || streq(fstype, "cachefs")) {
			(void) snprintf(cmd, MAXPATHLEN,
			    "fsck -F %s -m %s >/dev/null 2>&1",
			    fstype, disk);
			if (WEXITSTATUS(system(cmd)) != 0)
				return (-1);
		}
		(void) snprintf(cmd, MAXPATHLEN,
		    "mount -F %s %s %s %s >/dev/null 2>&1",
		    fstype, mntopts == NULL ? "" : mntopts, disk, mntpnt);
		if (WEXITSTATUS(system(cmd)) == 0)
			return (0);
	}

	return (-1);
}

/*
 * Function:	FsUmount
 * Description:	Unmount a filesystem.
 *
 *		NOTE: This function explicitly uses the "umount" command in
 *		      order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	name		[RO, *RO]
 *				The filesystem to be unmounted.  `name' can
 *				either be the path to the block special device
 *				containing the filesystem to be unmounted, or
 *				it can be the mountpoint of said filesystem.
 *				The caller is responsible for making sure that
 *				the filesystem corresponding to this device is
 *				already mounted.
 *		oldmountpt	[RO, *RO] (char *) (OPTIONAL)
 *				If the filesystem being unmounted is ufs,
 *				rewrite the last mount point field with this
 *				value so it looks like we never mounted it.
 *				Disregarded if the filesystem type isn't ufs.
 *				If the type is ufs, and oldmountpt is NULL,
 *				the name isn't rewritten.
 *		cdevice		[RO, *RO] (char *) (OPTIONAL)
 *				The character device for the filesystem.
 *				Needed only if the last mount name is being
 *				being rewritten (see `oldmountpt').
 * Return:	0	- unmount was successful
 *		1	- unmount failed
 */
int
FsUmount(char *name, char *oldmountpt, char *cdevice)
{
	char cmd[MAXPATHLEN * 2 + 128];
	char mountpt[MAXPATHLEN + 2];
	struct statvfs st;
	struct mnttab mpref, mp;
	int ufs = 0, found = 0;
	FILE *fp;

	/* validate parameters */
	if (name == NULL || !is_pathname(name)) {
		return (-1);
	}

	/* Determine whether or not `name' is a ufs filesystem */
	if ((fp = fopen(MNTTAB, "r")) != NULL) {
		/* First, look for it as a device name in the mnttab */
		(void) memset(&mpref, 0, sizeof (struct mnttab));
		mpref.mnt_special = name;
		if (getmntany(fp, &mp, &mpref) == 0) {
			/*
			 * Found it.  Save the mount point and determine
			 * whether or not it is a UFS filesystem.
			 */
			(void) strcpy(mountpt, mp.mnt_mountp);

			if (streq(mp.mnt_fstype, "ufs")) {
				ufs = 1;
			}
			found = 1;
		}

		(void) fclose(fp);
	}

	if (!found) {
		/*
		 * It's not in the mnttab, so it must be a mount point.
		 */
		if (statvfs(name, &st) != 0) {
			return (-1);
		}

		(void) strcpy(mountpt, name);

		if (streq(st.f_basetype, "ufs")) {
			ufs = 1;
		}
	}

	/* Unmount it */
	(void) snprintf(cmd, sizeof (cmd), "umount %s >/dev/null 2>&1",
	    name);
	if (WEXITSTATUS(system(cmd)) != 0) {

		/*
		 * The umount just failed.  Assuming fuser tells us that
		 * nobody has a lock on the filesystem and that nothing is
		 * mounted under it, we'll try to force it down.  Note that
		 * the force will only work on S8 or later.
		 */

		/* Check for locks on the filesystem */
		(void) snprintf(cmd, MAXPATHLEN * 2 + 128,
		    "if [ \"X`/usr/sbin/fuser -c %s 2>&1`\" = \"X%s: \" ] ; "
		    "then /bin/true ; else /bin/false ; fi", mountpt, mountpt);
		if (WEXITSTATUS(system(cmd)) != 0) {
			/*
			 * Someone has a lock on the filesystem and fuser knows
			 * who they are, so don't force the umount.  We're
			 * primarily interested in locks that fuser doesn't
			 * know about.
			 */
			return (-1);
		}

		/* Is anyone mounted within the filesystem? */
		(void) strcat(mountpt, "/");
		if ((fp = fopen(MNTTAB, "r")) != NULL) {
			while (getmntent(fp, &mp) == 0) {
				if (strneq(mp.mnt_mountp, mountpt,
							strlen(mountpt))) {
					/*
					 * Yes, someone is mounted within the
					 * filesystem, so the umount failure
					 * was valid, and we shouldn't force
					 * the umount.
					 */
					(void) fclose(fp);
					return (-1);
				}
			}
			(void) fclose(fp);
		}

		/* OK - try the forced umount */
		(void) snprintf(cmd, MAXPATHLEN * 2 + 128,
		    "umount -f %s >/dev/null 2>&1", name);
		if (WEXITSTATUS(system(cmd)) != 0) {
			return (-1);
		}
	}

	/*
	 * If it's a UFS filesystem, restore the original mount point name
	 * if the caller supplied one.
	 */
	if (ufs && oldmountpt && cdevice) {
		(void) UfsRestoreName(cdevice, oldmountpt);
	}

	return (0);
}

/*
 * Function:	UfsRestoreName
 * Description: Restore the "last-mounted-on" field in the superblock of the
 *		device referenced to the file system name specified. If the
 *		special device name specified is a simple slice device name
 *		(e.g. c0t3d0s3), the character special device is assumed to
 *		exist in /dev/rdsk. Otherwise, the user may supply a fully
 *		qualified path name to the character special device.
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Slice device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/rdsk/c0t3d0s4) form.
 *		name	[RO, *RO]
 *			The non-NULL name to set the last-mounted-on value.
 * Return:	 0	- successfully restored the file system name
 *		-1	- failed to restore the file system name
 */
int
UfsRestoreName(char *device, char *name)
{
	struct stat	sbuf;
	char	  disk[MAXNAMELEN];
	int	  fd;
	int	  sblock[SBSIZE/sizeof (int)];
	struct fs *fsp = (struct fs *)sblock;

	/* validate parameters */
	if (!is_slice_name(device) && !is_pathname(device))
		return (-1);

	if (!is_pathname(name))
		return (-1);

	if (is_slice_name(device))
		(void) snprintf(disk, sizeof (disk), "/dev/rdsk/%s", device);
	else
		(void) strcpy(disk, device);

	/* make sure the device is a character special device */
	if ((stat(disk, &sbuf) < 0) ||
			((sbuf.st_mode & S_IFCHR) == 0) ||
			((fd = open(disk, O_RDWR)) < 0))
		return (-1);

	if (lseek(fd, SBOFF, SEEK_SET) < 0 ||
			read(fd, fsp, sizeof (sblock)) < 0) {
		(void) close(fd);
		return (-1);
	}

	(void) strcpy(fsp->fs_fsmnt, name);
	if (lseek(fd, SBOFF, SEEK_SET) < 0) {
		(void) close(fd);
		return (-1);
	}

	(void) write(fd, fsp, sizeof (sblock));
	(void) close(fd);
	return (0);
}

/*
 * Function:	UfsMount
 * Description:	Mount a block special device containing a UFS file system. If
 *		the special device name specified is a simple slice device
 *		name (e.g. c0t3d0s3), the block special device is assumed
 *		to exist in /dev/dsk. Otherwise, the user may supply a
 *		fully qualified path name to the block special device.
 *
 *		NOTE: This function explicitly uses the "mount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Slice device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.
 *		mntpnt	[RO, *RO]
 *			UNIX path name for the mount point directory. This
 *			will be prepended with get_rootdir() by the function
 *			before mounting.
 *		mntopt	[RO, *RO] (optional)
 *			Mount options. If NULL specified, then "mount" command
 *			defaults are used. Options should appear as they would
 *			on the mount line (e.g. "-r").
 * Return:	 0	- the mount completed successfully
 *		-1	- the mount failed
 */
int
UfsMount(char *device, char *mntpnt, char *mntopt)
{
	char	*c;

	/* Check parameters */
	if (device == NULL || mntpnt == NULL)
		return (-1);

	/* Make sure it's a slice name or a path to one */
	if (!is_slice_name(device)) {
		if (!is_pathname(device) ||
		    !(c = strrchr(device, '/')) ||
		    !is_slice_name(c + 1))
			return (-1);
	}

	if (FsMount(device, mntpnt, mntopt, "ufs") < 0)
		return (-1);
	else
		return (0);
}

/*
 * Function:	UfsUmount
 * Description:	Unmount a block special device containing a UFS file system,
 *		with the option to set the "last-mounted-on" field in the
 *		super-block to an explicit value. If the special device name
 *		specified is a simple slice device name (e.g. c0t3d0s3), the
 *		block special device is assume to exist in /dev/dsk. Otherwise,
 *		the user may supply a fully qualified path name to the block
 *		special device. If the user provides a fully qualified
 *		block special device, and a mount point name for restoration,
 *		the user must also provide a fully qualified character
 *		special device. This is the only time a non-NULL value
 *		should be specified for the character special device.
 *
 *		NOTE: This function explicitly uses the "umount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	bdevice	[RO, *RO]
 *			Slice device name for which the block device
 *			will be used for the mount. The device may
 *			either be specified in relative (e.g. c0t3d0s4)
 *			or absolute (e.g. /dev/dsk/c0t3d0s4) form.
 *		mntpnt	[RO, *RO] (optional)
 *			UNIX path name for the mount point directory.
 *			NULL if no last mounted file system name
 *			restoration if required.
 *		cdevice	[RO, *RO] (optional)
 *			Absolute path for the character device associated
 *			with the block device being unmounted. This field
 *			must only be specified when the block device is
 *			specified as an absolute path, and a non-NULL mount
 *			point restoration value is provided. NULL, otherwise.
 * Return:	 0	- the unmount completed successfully
 *		-1	- the unmount failed
 */
int
UfsUmount(char *bdevice, char *mntpnt, char *cdevice)
{
	char bdevpath[MAXPATHLEN];
	char cdevpath[MAXPATHLEN];

	/* Put the whole path to the block device in bdevpath */
	if (is_slice_name(bdevice)) {
		(void) snprintf(bdevpath, MAXPATHLEN, "/dev/dsk/%s", bdevice);
	} else if (is_pathname(bdevice)) {
		(void) strcpy(bdevpath, bdevice);
	} else {
		return (-1);
	}

	if (mntpnt) {
		/* Put the whole path to the character device in cdevpath */
		if (cdevice) {
			if (!is_slice_name(bdevice) &&
			    is_pathname(cdevice)) {
				(void) strcpy(cdevpath, cdevice);
			} else {
				return (-1);
			}
		} else {
			if (is_slice_name(bdevice)) {
				(void) snprintf(cdevpath, MAXPATHLEN,
				    "/dev/rdsk/%s", bdevice);
			} else {
				return (-1);
			}
		}
	}

	return (FsUmount(bdevpath, mntpnt, cdevpath));
}

/*
 * Function:	StubBootMount
 * Description:	Mount a block special device containing PCFS Stub Boot (X86BOOT)
 *		partition.  The device name must be a partition name (e.g.
 *		c0t0d0p0) rather than a slice name.  If just the device is
 *		specified, it is assumed to live in /dev/dsk.  If a fully
 *		qualified path is supplied, it will be used as-is.
 *
 *		NOTES:
 *		  1. The pcfs mounter doesn't allow the mounting of Stub Boot
 *		     partitions by partition number.  As such, this routine
 *		     will remove the partition number, and will mount the
 *		     first Stub Boot partition on the specified disk.
 *
 *		  2. This function explicitly uses the "mount" command in order
 *		     to ensure that the mnttab file is kept up-to-date.
 *
 * Scope:	public
 * Parameters:	device	[RO, *RO]
 *			Partition device name containing the Stub Boot
 *			partition.  The device may either be specified in
 *			relative (e.g. c0t0d0p1) or absolute
 *			(e.g. /dev/dsk/c0t0d0p1) form.
 *		mntpnt	[RO, *RO]
 *			UNIX path name for the mount point directory. This
 *			will be prepended with get_rootdir() by the function
 *			before mounting.
 *		mntopt	[RO, *RO] (optional)
 *			Mount options. If NULL specified, then "mount" command
 *			defaults are used. Options should appear as they would
 *			on the mount line (e.g. "-r").
 * Return:	0	- the mount completed successfully
 *		-1	- the mount failed
 */
int
StubBootMount(char *device, char *mntpnt, char *mntopt)
{
	char	stubdev[MAXPATHLEN+1];
	char	*c;

	/* Check parameters */
	if (device == NULL || mntpnt == NULL)
		return (-1);

	/* Make sure it's a device name or a path to one */
	if (!is_part_name(device) && !is_pathname(device))
		return (-1);

	(void) strcpy(stubdev, device);

	/* Find the beginning of the device name */
	if (!(c = strrchr(stubdev, '/')))
		c = stubdev;

	/* Is it a valid partition name? */
	if (!is_part_name(c))
		return (-1);

	/*
	 * The end of the device name looks like 'p1'.  Replace
	 * it with 'p0:boot' because the pcfs mounter will only
	 * mount X86BOOT partitions if we use 'p0:boot'
	 */
	if (!(c = strrchr(stubdev, 'p')))
		/* Shouldn't happen */
		return (-1);

	(void) strcpy(c, "p0:boot");

	if (FsMount(stubdev, mntpnt, mntopt, "pcfs") < 0)
		return (-1);
	else
		return (0);
}

/*
 * Function:	StubBootUmount
 * Description:	Unmount a block special device containing a pcfs Stub Boot
 *		partition.  If the special device name is a simple partition
 *		device name (e.g. c0t0d0p1), the device is assumed to exist
 *		in /dev/dsk.  Otherwise, the user may supply a fully qualified
 *		path name to the block special device.
 *
 *		NOTES:
 *		  1. The pcfs mounter doesn't allow the mounting of Stub Boot
 *		     partitions by partition number.  The StubBootMount routine
 *		     removed the partition number, and mounted the first Stub
 *		     Boot partition on the specified disk.  This routine mangles
 *		     the name in the same way, because otherwise umount won't
 *		     work.
 *
 *		  2. This function explicitly uses the "umount" command in order
 *		     to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	device [RO, *RO]
 *			Partition device name to unmount.  The device may either
 *			be specified in relative (e.g. c0t0d0p1) or absolute
 *			(e.g. /dev/dsk/c0t0d0p1) form.
 * Return:	 0	- the mount completed successfully
 *		-1	- the mount failed
 */
int
StubBootUmount(char *device)
{
	char	stubdev[MAXPATHLEN+1];
	char	*c;

	/* Check parameters */
	if (device == NULL)
		return (-1);

	/* Make sure it's a device name or a path to one */
	if (!is_part_name(device) && !is_pathname(device))
		return (-1);

	if (is_pathname(device))
		(void) strcpy(stubdev, device);
	else
		(void) snprintf(stubdev, MAXPATHLEN, "/dev/dsk/%s", device);

	/* Is it a valid partition name? */
	if (!is_part_name(strrchr(stubdev, '/') + 1))
		return (-1);

	/*
	 * The end of the device name looks like 'p1'.  Replace
	 * it with 'p0:boot' because the pcfs mounter will only
	 * mount X86BOOT partitions if we use 'p0:boot'.  We have
	 * to unmount using the same name that was used for mounting.
	 */
	if (!(c = strrchr(stubdev, 'p')))
		/* Shouldn't happen */
		return (-1);

	(void) strcpy(c, "p0:boot");

	return (FsUmount(stubdev, NULL, NULL));
}

/*
 * Function:	DirUmountAll
 * Description: Unmount all file systems mounted under a specified directory.
 *		This routine first attempts to unmount all zones that may
 *		have been mounted under the specified directory.
 *		This routine assumes that all mounted file systems are logged
 *		in /etc/mnttab and are unmounted in the reverse order in which
 *		they appear in /etc/mnttab.
 *
 *		NOTE: This function explicitly uses the "unmount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	mntpnt	[RO, *RO]
 *			Non-NULL pointer to name of directory to be unmounted.
 * Return:	 0	- successfull
 *		-1	- unmount failed; see errno for reason
 */
int
DirUmountAll(char *mntpnt)
{
	struct stat	sbuf;
	FILE		*fp;
	int		retval = 0;

	/* validate parameters */
	if (!is_pathname(mntpnt) || (stat(mntpnt, &sbuf) < 0) ||
			((sbuf.st_mode & S_IFDIR) == 0))
		return (-1);

	/*
	 * open the mnttab and recursively begin unmounting file systems
	 * which are ultimately mounted on the specified directory
	 */
	if ((fp = fopen(MNTTAB, "r")) == NULL) {
		retval = -1;
	} else {
		retval = DirUmountRecurse(fp, mntpnt);
		(void) fclose(fp);
	}

	return (retval);
}

/*
 * Function:	DirUmount
 * Description:	Unmount the file system mounted on the specified directory.
 *
 *		NOTE: This function explicitly uses the "unmount" command in
 *			order to ensure that the mnttab file is kept up-to-date.
 * Scope:	public
 * Parameters:	mntpnt	[RO, *RO]
 *			Non-NULL name of directory to unmount.
 * Return:	 0	- the directory was successfully unmounted
 *		-1	- the directory unmount attempt failed
 */
int
DirUmount(char *mntpnt)
{
	struct stat	sbuf;

	/* validate parameter */
	if (!is_pathname(mntpnt) || (stat(mntpnt, &sbuf) < 0) ||
			((sbuf.st_mode & S_IFDIR) == 0))
		return (-1);

	return (FsUmount(mntpnt, NULL, NULL));
}

/*
 * Function:	FSTypeValid
 * Description:	Determine whether or not a given filesystem type is known
 *		to the system (and thus whether a filesystem of this type
 *		can be mounted).
 * Scope:	public
 * Parameters:	fstype	[RO, *RO]
 *			The type to be checked
 * Return:	1	- The type is valid
 *		0	- The type is unknown
 */
int
FSTypeValid(char *fstype)
{
	char fsbuf[FSTYPSZ + 1];
	int num, i;

	num = sysfs(GETNFSTYP);
	for (i = 0; i < num; i++) {
		sysfs(GETFSTYP, i, fsbuf);
		if (streq(fstype, fsbuf)) {
			return (1);
		}
	}

	return (0);
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	DirUmountRecurse
 * Description:	Recursively process the mnttab unmounting file systems
 *		which are children of the specified file system name.
 * Scope:	private
 * Parameters:	fp	[RO, *RO]
 *			FILE pointer to /etc/mnttab file.
 *		name	[RO, *RO]
 *			Non-NULL base name of directory being unmounted.
 * Return:	 0	- processing successful
 *		-1	- processing failed
 */
static int
DirUmountRecurse(FILE *fp, char *name)
{
	struct mnttab	ment;
	char		buf[MAXPATHLEN];
	char		mountp[MAXPATHLEN];

	/* validate parameters */
	if (fp == NULL || name == NULL)
		return (-1);

	(void) snprintf(buf, MAXPATHLEN, "%s/", name);
	while (getmntent(fp, &ment) == 0) {
		if (strneq(ment.mnt_mountp, buf, strlen(buf)) ||
				streq(ment.mnt_mountp, name)) {
			/*
			 * Save mountp because it'll get clobbered by
			 * DirUmountRecurse
			 */
			(void) strcpy(mountp, ment.mnt_mountp);

			if (DirUmountRecurse(fp, name) < 0)
				return (-1);

			if (DirUmount(mountp) < 0)
				return (-1);

			break;
		}
	}

	return (0);
}
