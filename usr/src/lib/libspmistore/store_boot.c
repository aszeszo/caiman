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
 * Module:	store_boot.c
 * Group:	libspmistore
 * Description: This module contains functions which get (and
 *		eventually set) data about the default firmware
 *		specified disk device.
 */

#include <ctype.h>
#include <dirent.h>
#include <fcntl.h>
#include <libgen.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/dkio.h>
#include <sys/fcntl.h>
#include <sys/mount.h>
#include <sys/openpromio.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/vtoc.h>
#include <device_info.h>
#include "spmistore_lib.h"
#include "spmicommon_api.h"

#define	BUFSIZE	1024

#ifndef TEST_STUB_GET_BOOTPATH

/* private functions */

static int 		_valid_boot_disk(const char *);
static char 		*_ddi_get_bootdev(void);

/* ---------------------- public functions ----------------------- */

/*
 * Function:	DiskobjFindBoot
 * Description:	Search the disk object list and find the disk with the disk
 *		name matching the disk name in the boot object for the
 *		state specified. This routine will not evaluate the
 *		availability or selection status of the associated disk
 *		when returning the disk object pointer.
 * Scope:	public
 * Parameters:	state	[RO] (Label_t)
 *			Identify boot object state from which to retrieve
 *			configuration information. Valid values are:
 *			    CFG_CURRENT		current boot state info
 *			    CFG_COMMIT		committed boot state info
 *			    CFG_EXIST		existing boot state info
 *		diskp	[RO, *RW] (Disk_t **)
 *			Address of disk object pointer used to retrieve pointer
 *			to the boot disk. Set to NULL if no disk object is
 *			found in the disk object list correponding to the boot
 *			object disk value in the specified state, of if the
 *			boot object disk name is undefined.
 * Return:	D_OK	  disk object successfully found
 * 		D_BADARG  invalid argument
 *		D_FAILED  disk object not found
 */
int
DiskobjFindBoot(Label_t state, Disk_t **diskp)
{
	char	    disk[MAXPATHLEN] = "";
	Disk_t	    *dp;

	/* validate parameters */
	if (state != CFG_CURRENT && state != CFG_COMMIT && state != CFG_EXIST)
		return (D_BADARG);

	if (diskp == NULL)
		return (D_BADARG);

	(void) BootobjGetAttribute(state, BOOTOBJ_DISK, disk, NULL);
	write_debug(SCR, get_trace_level() > 3, "LIBSPMISTORE", DEBUG_LOC,
		LEVEL1, "BootobjGetAttribute: disk = %s", disk);

	WALK_DISK_LIST(dp) {
		if (streq(disk_name(dp), disk))
			break;
	}

	write_debug(SCR, get_trace_level() > 3, NULL, DEBUG_LOC,
		LEVEL1, "BootobjGetAttribute: returns = %s",
		dp ? "D_OK" : "D_FAILED");
	if (dp == NULL) {
		*diskp = NULL;
		return (D_FAILED);
	} else {
		*diskp = dp;
		return (D_OK);
	}
}

/*
 * Function:	DiskobjFindStubBoot
 * Description:	Search the disk object list and find the disk (if any)
 *		containing the stub boot fdisk partition.  This routine
 *		will not evaluate the availability or selection status of
 *		selection status of the associated disk when returning
 *		the disk object pointer.
 * Scope:	public
 * Parameters:	state	[RO] (Label_t)
 *			Identify boot object state from which to retrieve
 *			configuration information.  Valid values are:
 *			    CFG_CURRENT		current boot state info
 *			    CFG_COMMIT		committed boot state info
 *			    CFG_EXIST		existing boot state info
 *		diskp	[RO, *RW] (Disk_t **)
 *			Address of disk object pointer used to retrieve pointer
 *			to the boot disk.  Set to NULL if no disk object is
 *			found in the disk object list corresponding to the boot
 *			object disk value in the specified state, or if the
 *			boot object disk name is undefined.  NULL if the address
 *			is not to be retrieved.
 *		partnum	[RO, *RW] (int *)
 *			Address of the integer used to store the partition
 *			number of the stub boot partition.  Set to D_NODISK if
 *			no stub boot partition exists or if no disk object was
 *			found.  NULL if the partition number is not to be
 *			retrieved.
 * Return:	D_OK	  stub boot partition found	  (success)
 *		D_NODISK  stub boot partition not found	  (success)
 *		D_BADARG  invalid argument		  (failure)
 *		D_FAILED  error trying to find partition  (failure)
 */
int
DiskobjFindStubBoot(Label_t state, Disk_t **diskp, int *partno)
{
	char	disk[MAXPATHLEN] = "";
	Disk_t *dp;
	int	pn;
	int	rc = D_BADARG;

	/* validate parameters */
	if (state != CFG_CURRENT && state != CFG_COMMIT && state != CFG_EXIST)
		return (D_BADARG);

	if (diskp)  *diskp = NULL;
	if (partno) *partno = D_NODISK;

	(void) BootobjGetAttribute(state,
				BOOTOBJ_STUBBOOT_DISK, disk,
				BOOTOBJ_STUBBOOT_PARTNO, &pn,
				NULL);
	write_debug(SCR, get_trace_level() > 3, "LIBSPMISTORE", DEBUG_LOC,
		LEVEL1, "BootobjGetAttribute: stubdisk = %s, stubpartno = %d",
		disk, pn);

	if (disk[0] == '\0') {
		/* No stub boot partition */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISTORE",
			    DEBUG_LOC, LEVEL1,
			    "DiskobjFindStubBoot: No stub boot partition");
		return (D_NODISK);
	}

	/* Look for the disk object */
	WALK_DISK_LIST(dp) {
		if (streq(disk_name(dp), disk))
			break;
	}

	if (dp == NULL) {
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISTORE",
			    DEBUG_LOC, LEVEL1,
			    "DiskobjFindStubBoot: Can't find disk object");
		rc = D_FAILED;
	} else if (invalid_fdisk_part(pn)) {
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISTORE",
			    DEBUG_LOC, LEVEL1,
			    "DiskobjFindStubBoot: invalid partition number");
		rc = D_FAILED;
	} else {
		rc = D_OK;
	}

	if (rc == D_OK) {
		if (diskp)  *diskp = dp;
		if (partno) *partno = pn;
	}

	return (rc);
}

/*
 * Function:	StubBootGetBootpath
 * Description:	Mount a stub boot partition, and get the Solaris partition
 *		it points to.
 * Scope:	private
 * Parameters:	sdev	- [RO], [*RO] (char *)
 *			  pointer to name of stub boot device
 *		spno	- [RO] (int)
 *			  partition number for stub boot device
 *		devp	- [RO], [*RW] (char **)
 *			  Address of character pointer used to retrieve
 *			  the name of the device containing the Solaris
 *			  partition (if found)
 *		pnop	- [RO], [*RW] (int *)
 *			  Address of integer used to retrieve the partition
 *			  number of the Solaris partition (if found)
 *		slcp	- [RO], [*RW] (int *)
 *			  Address of integer used to retrieve the slice
 *			  number of the root slice on the Solaris partition
 * Return:	0	- Solaris partition not found or an error occurred
 *			  (dev and pno undefined)
 *		1	- Solaris partition found (dev and pno set)
 */
int
StubBootGetBootpath(char *sdev, int spno, char **devp, int *pnop, int *slcp)
{
	static char	dev[MAXPATHLEN+1];
	char	mtdir[] = "/tmp/.stubboot.XXXXXX";
	char	mtpt[MAXPATHLEN+1];
	char	mtcmd[BUFSIZE];
	char	bepath[MAXPATHLEN+1];
	char	linebuf[BUFSIZE];
	char	soldev[MAXPATHLEN+1];
	char	soldevice[MAXPATHLEN+1];
	char	*c;
	Disk_t	*dp;
	FILE	*fp;
	int	slice;
	int	pid;

	/*
	 * If we're in simulation mode, assume the target is the last
	 * root filesystem on the disk list.
	 */
	if (GetSimulation(SIM_SYSDISK)) {
		Mntpnt_t info;
		int found = 0;

		/* whaddya know - it's a valid stub.  go figure */
		WALK_DISK_LIST(dp) {
			if ((pid = get_solaris_part(dp, CFG_EXIST))) {
				if (find_mnt_pnt(dp, NULL, ROOT, &info,
						CFG_EXIST)) {
					*devp = disk_name(dp);
					*pnop = pid;
					*slcp = info.slice;
					found = 1;
					/*
					 * We don't stop after the first
					 * one we find.  It makes testing
					 * easier.
					 */
				}
			}
		}

		return (found);
	}

	if (!mktemp(mtdir))
		return (0);

	(void) snprintf(mtpt, sizeof (mtpt), "%s/mnt", mtdir);
	(void) snprintf(mtcmd, BUFSIZE,
		"/sbin/mount -F pcfs /dev/dsk/%sp0:boot %s 1>/dev/null 2>&1",
		sdev, mtpt);

	if (mkdir(mtdir, S_IRUSR|S_IWUSR|S_IXUSR) ||
	    mkdir(mtpt, S_IRUSR|S_IWUSR|S_IXUSR) ||
	    system(mtcmd)) {
		(void) rmdir(mtpt);
		(void) rmdir(mtdir);
		return (0);
	}

	/* We now have the pcfs partition mounted on `mtpt' */

	/* If boot/grub exists, ignore the stub */
	(void) snprintf(bepath, sizeof (bepath),
	    "%s/boot/grub/menu.lst", mtpt);
	if ((fp = fopen(bepath, "r")) != NULL) {
		(void) fclose(fp);
		(void) umount(mtpt);
		(void) rmdir(mtpt);
		(void) rmdir(mtdir);
		return (0);
	}

	/* Look for the bootpath property in the bootenv.rc file */
	(void) snprintf(bepath, sizeof (bepath),
	    "%s/solaris/bootenv.rc", mtpt);
	if ((fp = fopen(bepath, "r")) == NULL) {
		(void) umount(mtpt);
		(void) rmdir(mtpt);
		(void) rmdir(mtdir);
		return (0);
	}

	soldevice[0] = '\0';
	while (fgets(linebuf, BUFSIZE, fp)) {
		/* Fail if line too long */
		if (strlen(linebuf) == BUFSIZE - 1)
			break;

		if (strncmp(linebuf, "setprop bootpath ", 17) == 0) {
			char *c = linebuf + 17;
			char *end = c + strlen(c);
			/* strip off any leading ' or " */
			while ((c < end) && (strchr("'\"", *c) != 0)) {
				c++;
			}
			/* strip off trailing \n */
			while ((strlen(c) > 0) &&
			    (strchr("'\"\n", c[strlen(c) - 1]) != 0)) {
				c[strlen(c) -  1] = '\0';
			}

			(void) snprintf(soldevice, sizeof (soldevice),
			    "/devices%s", c);
			break;
		}
	}

	/* Done with the file.  Unmount the filesystem */
	(void) fclose(fp);

	(void) snprintf(mtcmd, BUFSIZE, "/sbin/umount %s 1>/dev/null 2>&1",
	    mtpt);
	(void) system(mtcmd);

	(void) rmdir(mtpt);
	(void) rmdir(mtdir);

	if (soldevice[0] == '\0')
		return (0);  /* Didn't find it */

	/* Found a Solaris device - now we need to turn it into a disk name */
	soldev[0] = '\0';

	/* First, look for it as-is */
	if (_map_node_to_devlink(soldevice, soldev) != 0) {
		/* Not found - try translating it */
		char newsoldevice[MAXPATHLEN+1];

		_map_old_device_to_new(soldevice, newsoldevice);
		if (_map_node_to_devlink(newsoldevice, soldev) != 0)
			/*
			 * Couldn't find the disk for the referenced Solaris
			 * partition, so return failure
			 */
			return (0);
	}

	/*
	 * Get the slice number - _map_* gave us /dev/dsk/..., but we can only
	 * give the `...' to get_slice_number.
	 */
	if (((c = strrchr(soldev, '/')) != NULL) &&
	    (slice = get_slice_number(c + 1)) == -1)
		/* No slice number - bad soldev */
		return (0);

	/* We have the disk name - look for the disk object */
	if ((dp = find_disk(soldev)))
		/* Is there a Solaris partition on that disk? */
		if ((pid = get_solaris_part(dp, CFG_EXIST))) {
			/* Got everything */
			(void) strlcpy(dev, disk_name(dp), sizeof (dev));
			*devp = dev;
			*pnop = pid;
			*slcp = slice;
			return (1);
		}

	/* No disk object or no Solaris partition - failure */
	return (0);
}

/* ---------------------- internal functions ----------------------- */

/*
 * Function:	BootDefault
 * Description:	Retrieve the default boot disk and device.
 * Scope:	internal
 * Parameters:	diskp	[RO, *RW, **RW] (char **)
 *			Address of character pointer used to retrieve boot
 *			disk name.
 *		devp	[RO, *RW] (int *)
 *			Address of integer used to retrieve device index.
 *		sdiskp	[RO, *RW, **RW] (char **)
 *			Address of character pointer used to retrieve stub
 *			boot disk name (if any).
 *		spnop	[RO, *RW] (int *)
 *			Address of integer used to retrieve stub boot
 *			partition number (if any).
 * Return:	none
 */
void
BootDefault(char **diskp, int *devp, char **sdiskp, int *spnop)
{
	static char	disk[MAXPATHLEN];
	static char	stubdisk[MAXPATHLEN];
	Mntpnt_t	info;
	Disk_t		*dp;
	char		*dev = NULL, *sdev = NULL;
	char		*cp;
	int		pid = 0, spid = 0;
	int		slice;

	if (diskp == NULL || devp == NULL || sdiskp == NULL || spnop == NULL)
		return;

	*diskp = NULL;
	*devp = 0;
	*sdiskp = NULL;
	*spnop = 0;

	if (first_disk() == NULL)
		return;

	/* look for the ENV variable first */
	if ((dev = getenv("SYS_BOOTDEVICE")) == NULL) {
		dev = _ddi_get_bootdev();
	}

	/*
	 * For simulations which haven't been resolved:
	 * (1) SPARC, use the slice with the first "/" file system found in
	 *	the disk list.
	 * (2) Intel, the first x86boot partition in the disk list (if any).
	 *	If there are no x86boot partitions, look for the Solaris
	 *	partition containing the first "/" file system found in the
	 *	disk list.
	 * (3) PPC, the DOS partition on the disk containing the first "/"
	 *	file system found in the disk list.
	 */
	if (dev == NULL && GetSimulation(SIM_SYSDISK)) {
		WALK_DISK_LIST(dp) {
			if (find_mnt_pnt(dp, NULL, ROOT, &info, CFG_EXIST))
				break;
		}

		if (dp != NULL) {
			/* Found a root slice */
			if (IsIsa("sparc")) {
				dev = make_slice_name(disk_name(dp),
					info.slice);
			} else if (IsIsa("i386")) {

				pid = get_solaris_part(dp, CFG_EXIST);
				dev = make_device_name(disk_name(dp), pid);
			} else if (IsIsa("ppc")) {
				WALK_PARTITIONS(pid) {
					if (part_id(dp, pid) == DOSOS12 ||
						    part_id(dp, pid) ==
							DOSOS16) {
						dev = make_device_name(
							disk_name(dp), pid);
						break;
					}
				}
			}

			/*
			 * Look for an x86boot partition to go with the
			 * chosen root slice.  NOTE: This is a simulation,
			 * so we can't mount the partition to figure out
			 * which solaris partition it points to.  So,
			 * we guess (we took the first solaris partition
			 * we saw above).
			 */
			if (IsIsa("i386")) {
				WALK_DISK_LIST(dp) {
					if ((spid = get_stubboot_part(dp,
								CFG_EXIST))) {
						sdev = make_device_name(
							disk_name(dp), spid);
						break;
					}
				}
			}
		}
	}

	/*
	 * Look for a stub boot partition on Intel machines.
	 */
	if (IsIsa("i386") && !GetSimulation(SIM_SYSDISK)) {
		/* We found a boot device.  Look for a stub on it. */
		if (dev != NULL) {
			if ((dp = find_disk(dev))) {
				if ((spid = get_stubboot_part(dp, CFG_EXIST))) {
					/*
					 * Found one on this disk.  (Try to)
					 * figure out the corresponding Solaris
					 * partition.
					 */
					sdev = disk_name(dp);

					(void) StubBootGetBootpath(sdev, spid,
					    &dev, &pid, &slice);
				}
			}
		} else {
			/*
			 * We don't have a boot device.  If we can find a stub
			 * boot partition, we'll assume that to be the boot
			 * device.
			 */
			WALK_DISK_LIST(dp) {
				if ((spid = get_stubboot_part(dp, CFG_EXIST))) {
					/*
					 * Found one on this disk.  (Try to)
					 * figure out the corresponding Solaris
					 * partition.
					 */
					sdev = disk_name(dp);

					if (StubBootGetBootpath(sdev, spid,
								&dev, &pid,
								&slice))
						break;
				}
			}
		}

		/*
		 * If we didn't find a stub/solaris combination, null out the
		 * stub variables.
		 */
		if (dev == NULL) {
			sdev = NULL;
			spid = 0;
		} else if (sdev != NULL) {
			/* We've got everything */
			(void) strlcpy(stubdisk, sdev, sizeof (stubdisk));
			*sdiskp = &stubdisk[0];
			*spnop = spid;

			(void) strlcpy(disk, dev, sizeof (disk));
			*diskp = &disk[0];
			*devp = pid;
			return;
		}
	}

	/* No stub boot - figure out the name of the boot device */
	disk[0] = '\0';
	if (dev == NULL) {
		*diskp = NULL;
		*devp = -1;
	} else if (is_disk_name(dev)) {
		(void) strcpy(disk, dev);
		*diskp = &disk[0];
		*devp = -1;
	} else if (IsIsa("sparc") && is_slice_name(dev) &&
			(cp = strrchr(dev, 's')) != NULL) {
		*cp = NULL;
		(void) strcpy(disk, dev);
		*diskp = &disk[0];
		*devp = atoi(++cp);
	} else if ((IsIsa("ppc") || IsIsa("i386")) && is_part_name(dev) &&
			(cp = strrchr(dev, 'p')) != NULL) {
		*cp = NULL;
		(void) strcpy(disk, dev);
		*diskp = &disk[0];
		*devp = atoi(++cp);
		/*
		 * if the returned device was p0, the firmware did not
		 * have an explicit partition configured and is relying
		 * on the current configuration of the fdisk table instead
		 */
		if (*devp == 0)
			*devp = -1;
	} else {
		*diskp = NULL;
		*devp = -1;
	}
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	_valid_boot_disk
 * Description:	Determine whether the input parameter is a valid disk.
 *		The following must be true in order to be a valid disk:
 *		- it is of the form:
 *			/dev/dsk/c[0-9][t[0-9]]d[0-9]{s[0-9]]|p[0-3]
 *		- it is openable (the device exists)
 *		- it is not a CD
 *
 * Scope:	private
 * Parameters:	boot_device [RO, *RO] (char *)
 * Return:	0	- parameter is not a valid boot disk
 *		1	- parameter is a valid boot disk
 */
static int
_valid_boot_disk(const char *boot_device)
{
	char 		*dev_name;
	char 		*dev_path;
	int  		ret_val;
	struct dk_cinfo	dkc;
	char		buf[MAXNAMELEN];
	char		dev_buf[MAXNAMELEN];
	int		n;
	int		fd;

	if (!boot_device || *boot_device == '\0')
		return (0);

	ret_val = 0;
	(void) strcpy(dev_buf, boot_device);
	dev_name = basename(dev_buf);
	dev_path = dirname(dev_buf);

	/* the device must be in /dev/dsk and be in the correct format */
	if (streq(dev_path, "/dev/dsk") &&
		(is_slice_name(dev_name) || is_part_name(dev_name))) {

		/*
		 * the ioctl() used to check to see if
		 * the device is a cdrom must be run on
		 * the raw device
		 */
		(void) snprintf(buf, sizeof (buf),
		    "/dev/rdsk/%s", dev_name);
		if ((fd = open(buf, O_RDONLY)) >= 0) {
			n = ioctl(fd, DKIOCINFO, &dkc);
			(void) close(fd);
			if (n == 0 && dkc.dki_ctype !=
					DKC_CDROM) {
				ret_val = 1;
			}
		}
	}

	return (ret_val);
}

/*
 * Function:	_ddi_get_bootdev
 * Description:	Retrieve the disk boot device information using the DDI
 *		interfaces for accessing the PROM configuration variable.
 * Scope:	private
 * Parameters:	none
 * Return:	NULL	- unable to access a boot device
 *		char *	- pointer to local buffer with disk boot device
 */
/*
 * To get around a problem with dbx and libthread, define NODEVINFO
 * to 'comment out' code references to functions in libdevinfo,
 * which is threaded.
 */
static char *
_ddi_get_bootdev(void)
{
	static char bootdev_str[MAXPATHLEN];
	struct boot_dev **boot_devices;
	struct boot_dev **boot_devices_orig;
	char *int_boot_dev_str;
	char **trans_list;
	int  dev_found;

	/* if this is dryrun then return NULL */
	if (GetSimulation(SIM_SYSDISK))
		return (NULL);

	dev_found = 0;
	/* Retrieve the list of boot device values */
#ifndef NODEVINFO
	if ((devfs_bootdev_get_list("/", &boot_devices) == SUCCESS) &&
	    (boot_devices != NULL)) {
		boot_devices_orig = boot_devices;
		/*
		 * For each boot device entry a list of resolvable
		 * /dev device translations are returned - scan
		 * the lists for the first viable candidate
		 */
		while (*boot_devices && !dev_found) {
			trans_list = (*boot_devices)->bootdev_trans;
			while (*trans_list && !dev_found) {
				int_boot_dev_str = *trans_list;
				if (_valid_boot_disk(int_boot_dev_str)) {
					(void) strcpy(bootdev_str,
						int_boot_dev_str);
					dev_found = 1;
				}
				trans_list++;
			}
			boot_devices++;
		}
		/* free the space allocated by devfs_bootdev_get_list */
		devfs_bootdev_free_list(boot_devices_orig);
	}
#endif

	errno = 0;
	if (dev_found) {
		return (basename(bootdev_str));
	} else {
		return (NULL);
	}
}

#else /* TEST_STUB_GET_BOOTPATH */
/*
 * Test harness for StubBootGetBootpath.  Invoke with the simple stub
 * boot device name (no partition number, no slice number) and stub
 * boot partition number.
 *
 */
void
main(int argc, char **argv)
{
	char *dev;
	int pno;
	int spno;
	int slice;

	if (argc != 3 || !valid_fdisk_part((spno = atoi(argv[2])))) {
		printf("%s: stub_device stub_partno\n", argv[0]);
		exit(1);
	}

	printf("Stub device: %s\n", argv[1]);
	printf("Stub partno: %d\n", spno);

	if (!DiskobjInitList(NULL)) {
		printf("no disks found\n");
		exit(1);
	}

	if (!StubBootGetBootpath(argv[1], spno, &dev, &pno, &slice)) {
		printf("error getting solaris partition info\n");
	} else {
		printf("Solaris dev: %s\n", (dev ? dev : "NULL"));
		printf("Solaris pno: %d\n", spno);
		printf("Solaris slc: %d\n", slice);
	}
}
#endif
