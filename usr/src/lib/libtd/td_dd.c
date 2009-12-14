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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#include <assert.h>
#include <errno.h>
#include <libgen.h>

#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#include <unistd.h>
#include <stropts.h>

#include <sys/types.h>

#include <sys/dkio.h>
#include <sys/dktp/fdisk.h>
#include <sys/fs/ufs_fs.h>

#include <sys/stat.h>
#include <sys/vtoc.h>
#include <fcntl.h>

#include <device_info.h>

#include <libdiskmgt.h>
#include <td_dd.h>
#include <ls_api.h>

/* global variables */

int ddm_inuse_svm_enabled = 0;

/* local constants */

#define	DDM_LSWAP_PSIZE_MIN	(4*1024)	/* minimal page size - 4k */
#define	DDM_LSWAP_PSIZE_MAX	(8*1024*1024)	/* maximal page size - 8M */
#define	DDM_LSWAP_BSIZE		512		/* disk block size */
#define	DDM_LSWAP_MAGICV0	"SWAP-SPACE"	/* magic word for swap v0 */
#define	DDM_LSWAP_MAGICVx	"SWAPSPACE"	/* magic word for swap v1 */
#define	DDM_LSWAP_MAGIC_SIZE	10		/* size of magic word */

typedef struct ddm_conv_attr_t {
	char	*nv_name_src;
	char	*nv_name_dst;
} ddm_conv_attr_t;

/* nvlist namespace conversion table for disks */

static char *ddm_disk_attr_conv_tbl[][2] = {
	{ DM_BLOCKSIZE,		TD_DISK_ATTR_BLOCKSIZE },
	{ DM_SIZE,		TD_DISK_ATTR_SIZE },
	{ DM_MTYPE,		TD_DISK_ATTR_MTYPE },
	{ DM_STATUS,		TD_DISK_ATTR_STATUS },
	{ DM_REMOVABLE,		TD_DISK_ATTR_REMOVABLE },
	{ DM_LOADED,		TD_DISK_ATTR_MLOADED },
	{ DM_VENDOR_ID,		TD_DISK_ATTR_VENDOR },
	{ DM_PRODUCT_ID,	TD_DISK_ATTR_PRODUCT },
	{ DM_OPATH,		TD_DISK_ATTR_DEVID },
	{ DM_NHEADS,		TD_DISK_ATTR_NHEADS },
	{ DM_NSECTORS,		TD_DISK_ATTR_NSECTORS },
	{ NULL,			NULL }
};

/* nvlist namespace conversion table for partitions */

static char *ddm_part_attr_conv_tbl[][2] = {
	{ DM_BOOTID,		TD_PART_ATTR_BOOTID },
	{ DM_PTYPE,		TD_PART_ATTR_TYPE },
	{ DM_PARTITION_TYPE,    TD_PART_ATTR_PART_TYPE },
	{ DM_RELSECT,		TD_PART_ATTR_START },
	{ DM_NSECTORS,		TD_PART_ATTR_SIZE },
	{ NULL, 		NULL }
};

/* nvlist namespace conversion table for slices */

static char *ddm_slice_attr_conv_tbl[][2] = {
	{ DM_INDEX,		TD_SLICE_ATTR_INDEX },
	{ DM_DEVT,		TD_SLICE_ATTR_DEVT },
	{ DM_START,		TD_SLICE_ATTR_START },
	{ DM_SIZE,		TD_SLICE_ATTR_SIZE },
	{ DM_TAG,		TD_SLICE_ATTR_TAG },
	{ DM_FLAG,		TD_SLICE_ATTR_FLAG },
	{ DM_DEVICEID,		TD_SLICE_ATTR_DEVID },
	{ NULL, 		NULL }
};

/* private variables */

/*
 * Pointer to array of disk descriptors obtained from libdiskmgt
 * library. We need to keep it, because we pass to Management
 * module array of filtered disk descriptors created here in Disk
 * module. When it is required to free disk discovery information,
 * the pointer to array of filtered disk descriptors is passed
 * from Management module and we need to also free original list
 * of drive descriptors returned from libdiskmgt library.
 */
static dm_descriptor_t	*ddm_drive_desc = NULL;

/* ------------------------ local functions --------------------------- */

/*
 * Function:	ddm_conv_attr_list
 * Description:	Convert libdiskmgt namespace to libtd namespace
 *		New nvlist is created and only attributes present
 *		in conversion table are modified and add to the
 *		new nvlist. Original nvlist is kept unmodified.
 * Scope:	private
 * Parameters:	nv_src
 *		nv_dst
 *		conv_table
 * Return:	DDM_SUCCESS - conversion done successfully
 *		DDM_FAILURE - conversion failed
 */

static ddm_err_t
ddm_conv_attr_list(nvlist_t *nv_src, char *conv_table[][2], nvlist_t **nv_dst)
{
	nvpair_t	*nvpair_src = NULL;
	uint32_t	ui32;
	uint64_t	ui64;
	char		*str;
	ddm_err_t	ret = DDM_SUCCESS;

	if (nvlist_alloc(nv_dst, DDM_NVATTRS, 0) != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_conv_attr_list(): Can't alloc new nvlist\n");

		return (DDM_FAILURE);
	}

	/*
	 * Enumerate through overall original nvlist of attributes
	 * If there is an attribute with name to be converted, do this
	 * conversion and add new nvpair to the generated list.
	 */

	while ((nvpair_src = nvlist_next_nvpair(nv_src, nvpair_src)) != NULL) {
		char		*nvp_name = nvpair_name(nvpair_src);
		data_type_t	nvp_type = nvpair_type(nvpair_src);
		int		i;
		char		*name_src = NULL;
		char		*name_dst;

		/* try to lookup original attribute name in table */

		for (i = 0; conv_table[i][0] != NULL; i++) {
			if (strcmp(nvp_name, conv_table[i][0]) == 0) {
				name_src = conv_table[i][0];
				name_dst = conv_table[i][1];

				break;
			}
		}

		/*
		 * if attribute name not found in conversion table,
		 * skip conversion procedure and continue with
		 * next attribute
		 */

		if (name_src == NULL) {
			DDM_DEBUG(DDM_DBGLVL_INFO,
			    "ddm_conv_attr_list(): %s not in table\n",
			    nvp_name);

			continue;
		}

		/*
		 * Since there is no libnvpair interface for renaming
		 * name in name-value pair, it is necessary to grab
		 * original value by type and store it to the new list
		 * with new name
		 */

		switch (nvp_type) {
		case DATA_TYPE_BOOLEAN:
			if (nvlist_add_boolean(*nv_dst, name_dst) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't add "
				    "boolean %s to new nvlist\n",
				    name_dst);

				ret = DDM_FAILURE;
			}
			break;

		case DATA_TYPE_UINT32:
			if (nvpair_value_uint32(nvpair_src, &ui32) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't get "
				    "uint32 value from %s\n",
				    name_src);

				ret = DDM_FAILURE;
			}

			if (nvlist_add_uint32(*nv_dst, name_dst, ui32) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't add "
				    "uint32 %s to new nvlist\n",
				    name_dst);

				ret = DDM_FAILURE;
			}
			break;

		case DATA_TYPE_UINT64:
			if (nvpair_value_uint64(nvpair_src, &ui64) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't get "
				    "uint64 value from %s\n",
				    name_src);

				ret = DDM_FAILURE;
			}

			if (nvlist_add_uint64(*nv_dst, name_dst, ui64) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't add "
				    "uint64 %s to new nvlist\n",
				    name_dst);

				ret = DDM_FAILURE;
			}
			break;

		case DATA_TYPE_STRING:
			if (nvpair_value_string(nvpair_src, &str) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't get "
				    "string value from %s\n",
				    name_src);

				ret = DDM_FAILURE;
			}

			if (nvlist_add_string(*nv_dst, name_dst, str) != 0) {
				DDM_DEBUG(DDM_DBGLVL_ERROR,
				    "ddm_conv_attr_list(): Can't "
				    "add string %s to new nvlist\n",
				    name_dst);

				ret = DDM_FAILURE;
			}
			break;

		/*
		 * Handle the case when there is nvpair type found
		 * which is not processed here. Display error message
		 * since the current attribute is going to be lost
		 */

		default:
			DDM_DEBUG(DDM_DBGLVL_ERROR,
			    "ddm_conv_attr_list(): "
			    "Unknown attr type for %s\n",
			    name_src);

			ret = DDM_FAILURE;
			break;

		}
	}

	return (ret);
}

/*
 * Function:	ddm_is_part_name
 * Description:	Check to see a string syntactically represents a
 *		cannonical fdisk partition device name (e.g. c0t0d0p2).
 *
 *		With World wide Name, we cannot check the
 * 		whole string, we will check the last two characters.
 *		They should be in the form 'pN', where N is a number
 *
 * Scope:	private
 * Parameters:	str - device name to be checked
 *			  string to be validated
 * Return:	B_FALSE - invalid partition name syntax
 *		B_TRUE  - valid partition name syntax
 */
static boolean_t
ddm_is_part_name(char *str)
{
	char	*pstart;

	if (strchr(str, '/') != NULL) {
		return (B_FALSE);
	}

	/* check for pN format, where N must be a number */

	pstart = strrchr(str, 'p');

	if ((pstart == NULL) || (pstart == str))
		return (B_FALSE);

	pstart++;

	do {
		if (!isdigit(*pstart))
			return (B_FALSE);
	} while (*(++pstart) != '\0');

	return (B_TRUE);
}

/*
 * Function:	ddm_is_valid_boot_disk
 * Description:	Determine whether the input parameter is a valid disk.
 *		The following must be true in order to be a valid disk:
 *		- it is of the form:
 *			/dev/dsk/.*{s[0-15]|p[0-9]+}
 *		- it is openable (the device exists)
 *		- it is not a CD
 *
 * Scope:	private
 * Parameters:	boot_device
 * Return:	B_FALSE - parameter is not a valid boot disk
 *		B_TRUE - parameter is a valid boot disk
 */
static int
ddm_is_valid_boot_disk(const char *boot_device)
{
	char 		*dev_name;
	int  		ret_val = B_FALSE;
	struct dk_cinfo	dkc;
	char		buf[MAXPATHLEN];
	int		n;
	int		fd;
	const char	devdsk[] = "/dev/dsk/";

	assert(boot_device != NULL);

	if (*boot_device == '\0')
		return (B_FALSE);

	dev_name = strrchr(boot_device, '/');

	if ((dev_name == NULL) || (dev_name[1] == '\0'))
		return (B_FALSE);

	/* the device must be in /dev/dsk and be in the correct format */
	if (strncmp(boot_device, devdsk, strlen(devdsk)) == 0) {
		/*
		 * the ioctl() used to check to see if
		 * the device is a cdrom must be run on
		 * the raw device
		 */
		(void) snprintf(buf, sizeof (buf), "/dev/rdsk%s", dev_name);

		if ((fd = open(buf, O_RDONLY | O_NONBLOCK | O_NOCTTY)) >= 0) {
			n = ioctl(fd, DKIOCINFO, &dkc);
			(void) close(fd);

			if ((n == 0) && (dkc.dki_ctype != DKC_CDROM)) {
				ret_val = B_TRUE;
			}
		}
	}

	return (ret_val);
}

/*
 * Function:	ddm_create_sname_from_dname
 * Description: Creates /dev/rdsk slice name from ctd disk name
 * Scope:	private
 * Parameters:	disk_name
 *
 * Return:	char *	- pointer to slice name
 */
static char *
ddm_create_sname_from_dname(char *disk_name)
{
	int		maxln;
	char		*dn_cdts;

	/*
	 * always create device name for slice 0
	 */

	maxln = strlen(disk_name) + strlen("/dev/rdsk/s0");
	dn_cdts = malloc(maxln + 1);

	if (dn_cdts == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_create_sname_from_dname(): malloc() OOM\n");

		return (NULL);
	}

	(void) snprintf(dn_cdts, maxln + 1, "/dev/rdsk/%ss0", disk_name);
	return (dn_cdts);
}

/*
 * Function:	ddm_disk_open
 * Description: Tries to open disk
 * Scope:	private
 * Parameters:	device_name
 *
 * Return:	-1 - disk open failed
 *		>= 0	- file descriptor returned by open(2)
 */
static int
ddm_disk_open(char *device_name)
{
	return (open(device_name, O_RDONLY | O_NDELAY | O_NOCTTY));
}

/*
 * Function:	ddm_disk_has_vtoc
 * Description: Checks, if disk contains valid VTOC
 * Scope:	private
 * Parameters:
 *
 * Return:	B_FALSE - no valid VTOC found
 *		B_TRUE - disk contains valid VTOC
 */
static int
ddm_disk_has_vtoc(char *disk_name)
{
	int		fd;
	struct extvtoc	extvtoc;
	int		disk_has_vtoc = B_FALSE;
	char		*slice_name;

	slice_name = ddm_create_sname_from_dname(disk_name);

	if (slice_name == NULL)
		return (B_FALSE);

	fd = ddm_disk_open(slice_name);

	if (fd == -1) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_disk_has_vtoc(): Couldn't open %s\n",
		    slice_name);

		free(slice_name);
		return (B_FALSE);
	}

	/* check, if the disk contains valid VTOC */

	if (read_extvtoc(fd, &extvtoc) >= 0)
		disk_has_vtoc = B_TRUE;

	(void) close(fd);

	free(slice_name);
	return (disk_has_vtoc);
}

/*
 * Function:	ddm_get_curr_bootdisk
 * Description: Returns name of bootdisk in ctd format
 * Scope:	private
 * Parameters:
 *
 * Return:	NULL	- no valid bootdisk name found
 *		char *	- pointer to the name of the current bootdisk
 */
static char *
ddm_get_curr_bootdisk(void)
{
	struct boot_dev **boot_devices;
	struct boot_dev **boot_devices_orig;
	char 		*int_boot_dev_str;
	char 		**trans_list;
	int		dev_found = B_FALSE;
	char		*curr_bootdisk = NULL;

	if ((devfs_bootdev_get_list("/", &boot_devices) == 0) &&
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

				if (ddm_is_valid_boot_disk(int_boot_dev_str)) {
					dev_found = B_TRUE;
				}

				trans_list++;
			}

			boot_devices++;
		}

		/* return disk name in cdt format - omit partition/slice name */

		if (dev_found) {
			size_t	sln;
			char	*bname = basename(int_boot_dev_str);
			char	*spname;

			if (ddm_is_part_name(bname)) {
				spname = strchr(bname, 'p');
			} else if (ddm_is_slice_name(bname)) {
				spname = strchr(bname, 's');
			} else
				spname = "";

			sln = strlen(bname) - strlen(spname);

			curr_bootdisk = malloc(sln + 1);

			if (curr_bootdisk != NULL) {
				(void) strncpy(curr_bootdisk, bname, sln);
				curr_bootdisk[sln] = '\0';
			}
		}

		/* free the space allocated by devfs_bootdev_get_list */

		devfs_bootdev_free_list(boot_devices_orig);
	}

	return (curr_bootdisk);
}

/*
 * Function:	ddm_ufs_get_lastmount
 * Description: Get the last mountpoint from superblock from a slice
 *		(if available).
 * Scope:	private
 * Parameters:	slice_name
 *		Valid slice name in /dev/dsk/ctds format
 *
 * Return:	NULL	- no valid FS name found
 *		char *	- pointer to the last mountpoint
 * Note:	Open the raw device, scan to the superblock offset, and read
 *		what should be the first superblock (assuming there was one -
 *		check the "magic" field to see). If the name given is "/a...",
 *		then strip off the leading "/a" to get the name of the real file
 *		system, otherwise, just copy the name.
 */
static char *
ddm_ufs_get_lastmount(char *slice_name)
{
	int			sblock[SBSIZE/sizeof (int)];
	struct fs		*fsp = (struct fs *)sblock;
	char			devpath[MAXPATHLEN];
	int			fd;

	(void) snprintf(devpath, sizeof (devpath), "/dev/rdsk/%s",
	    basename(slice_name));

	/* attempt to open the disk; if it fails, skip it */

	if ((fd = open(devpath, O_RDONLY|O_NDELAY)) < 0)
		return (NULL);

	if (lseek(fd, SBOFF, SEEK_SET) == -1) {
		(void) close(fd);
		return (NULL);
	}

	if (read(fd, fsp, sizeof (sblock)) != sizeof (sblock)) {
		(void) close(fd);
		return (NULL);
	}

	(void) close(fd);

	/* make sure you aren't going to load bogus data */

	if ((fsp->fs_magic != FS_MAGIC) || (fsp->fs_fsmnt[0] != '/') ||
	    (strlen(fsp->fs_fsmnt) > (size_t)(MAXMNTLEN - 1)))
		return (NULL);

	return (fsp->fs_fsmnt);
}


/*
 * Function:	ddm_is_linux_swap()
 * Description:	Test if partition is dedicated to Linux swap.
 * Parameters:
 *	char	*part_name - /dev/rdsk/c#t#d#p# device name of partition
 * Return:
 *	int	B_FALSE - partition does not contain Linux swap
 *		B_TRUE - partition contains Linux swap
 * Scope:
 *	private
 *
 * Algorithm:	Linux puts magic string at the end of the first swap logical
 *		unit (its size equals to size of memory page). It is necessary
 *		to read last block of this unit into the memory and look if
 *		magic string is present. There are following issues function
 *		has to deal with:
 *	[1] The page size can vary. Try reasonable amount of page sizes.
 *	    Start with 4k and go up to DDM_LSWAP_PSIZE_MAX. Since page size
 *	    is always power of two, the number of loops is acceptable.
 *	[2] The magic string depends on Linux swap version. For now
 *	    "SWAP-SPACE" is used for version 0 and "SWAPSPACE2" for version 1.
 *	    Current implementaion looks for "SWAP-SPACE" or "SWAPSPACE".
 *	    trying to anticipate that future version might still contain
 *	    "SWAPSPACE" magic string.
 *	    If one of them matches, declare 'this is Linux Swap'.
 *	[3] Due to the problem with pages sizes, there is proposal recommending
 *	    moving magic string to the place right after the 1st kB. So try
 *	    to search for magic string also at the start of the 2nd kb within
 *	    the 1st unit (bytes 1025 - 1033(4)).
 *
 */
static int
ddm_is_linux_swap(char *part_name)
{
	int	fd;
	int	pg_size;
	int	fl_lswap_found = B_FALSE;
	char	buf[DDM_LSWAP_BSIZE + 1];

	/* try to open partition for reading */

	fd = ddm_disk_open(part_name);

	if (fd == -1) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_is_linux_swap(): open(%s) failed\n", part_name);

		return (B_FALSE);
	}

	/*
	 * iterate through page sizes within interval
	 * <DDM_LSWAP_PSIZE_MIN; DDM_LSWAP_PSIZE_MAX>. Keep in mind
	 * that page size is always power of two.
	 */

	for (pg_size = DDM_LSWAP_PSIZE_MIN; (pg_size <= DDM_LSWAP_PSIZE_MAX);
	    pg_size <<= 1) {

		/*
		 * seek & read the last block(512 bytes)
		 * of currently inspected page from disk
		 */

		if (lseek(fd, pg_size - DDM_LSWAP_BSIZE, SEEK_SET)
		    != pg_size - DDM_LSWAP_BSIZE) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_is_linux_swap(): "
			    "lseek() failed, errno=%d\n", errno);

			(void) close(fd);
			return (B_FALSE);
		}

		if (read(fd, buf, DDM_LSWAP_BSIZE)
		    != DDM_LSWAP_BSIZE) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_is_linux_swap(): "
			    "read() failed, errno=%d\n", errno);

			(void) close(fd);
			return (B_FALSE);
		}

		if (strncmp(buf + DDM_LSWAP_BSIZE - DDM_LSWAP_MAGIC_SIZE,
		    DDM_LSWAP_MAGICV0, sizeof (DDM_LSWAP_MAGICV0) - 1) == 0) {

			DDM_DEBUG(DDM_DBGLVL_NOTICE, "ddm_is_linux_swap(): "
			    "Linux SWAPv0 found, ps=0x%X\n", pg_size);

			fl_lswap_found = B_TRUE;

			break;
		}

		/*
		 * When comparing to the magic string for version > 0,
		 * don't compare last char, which will be probably changed for
		 * future versions of Linux Swap (for now it is '2')
		 */

		if (strncmp(buf + DDM_LSWAP_BSIZE - DDM_LSWAP_MAGIC_SIZE,
		    DDM_LSWAP_MAGICVx, sizeof (DDM_LSWAP_MAGICVx) - 1) == 0) {

			DDM_DEBUG(DDM_DBGLVL_NOTICE, "ddm_is_linux_swap(): "
			    "Linux SWAPv1 found, ps=0x%X\n", pg_size);

			fl_lswap_found = B_TRUE;

			break;
		}
	}

	/*
	 * If not successful so far, try to look also at the
	 * beginning of the Linux swap configuration information
	 * stored in the 3rd block of the 1st unit that might
	 * in future contain magic string
	 */

	if (!fl_lswap_found) {
		if (lseek(fd, 2 * DDM_LSWAP_BSIZE, SEEK_SET)
		    != 2 * DDM_LSWAP_BSIZE) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_is_linux_swap():"
			"lseek() failed, errno=%d\n", errno);

			(void) close(fd);
			return (B_FALSE);
		}

		if (read(fd, buf, DDM_LSWAP_BSIZE)
		    != DDM_LSWAP_BSIZE) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_is_linux_swap(): "
			    "read() failed, errno=%d\n", errno);

			(void) close(fd);
			return (B_FALSE);
		}

		/*
		 * Compare only to the magic string for version > 0,
		 * since for version 0, the magic string can't be
		 * stored here.
		 */

		if (strncmp(buf, DDM_LSWAP_MAGICVx,
		    sizeof (DDM_LSWAP_MAGIC_SIZE) - 1) == 0) {

			DDM_DEBUG(DDM_DBGLVL_NOTICE,  "ddm_is_linux_swap(): "
			    "Linux SWAPv1 found, ps=0\n");

			fl_lswap_found = B_TRUE;
		}
	}

	(void) close(fd);

	/* return cached value */
	return (fl_lswap_found);
}

/*
 * Function:	ddm_drive_set_ctype()
 *
 * Description:	Retrieves disk controller type (usb,ata,...) and add it
 *		to the nvlist of disk attributes.
 *
 * Parameters:
 *	ddm_handle_t d	- disk handle
 *	nvlist_t *attr	- list of disk attributes
 *
 * Return:
 *	0 - finished successfully
 *
 * Scope:
 *	private
 */
static int
ddm_drive_set_ctype(ddm_handle_t d, nvlist_t *attr)
{
	dm_descriptor_t	*ad;
	int		errn;
	nvlist_t	*nv_tmp;
	char		*ctype;
	int		ctype_recognized = B_FALSE;

	ad = dm_get_associated_descriptors((dm_descriptor_t)d, DM_CONTROLLER,
	    &errn);

	if ((errn != 0) || (ad == NULL) || (ad[0] == 0)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_drive_get_ctype():"
		    "Can't get DM_CONTROLLER assoc. w/ DM_DRIVE, err=%d\n",
		    errn);

		/* free unused descriptors */

		if ((errn == 0) && (ad != NULL))
			dm_free_descriptors(ad);
	} else {
		/* get attributes for controller */
		nv_tmp = dm_get_attributes(ad[0], &errn);

		dm_free_descriptors(ad);

		if ((errn == 0) &&
		    (nvlist_lookup_string(nv_tmp, DM_CTYPE, &ctype) == 0)) {

			nvlist_add_string(attr, TD_DISK_ATTR_CTYPE, ctype);

			nvlist_free(nv_tmp);

			ctype_recognized = B_TRUE;
		} else {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_drive_get_ctype():"
			    "Can't get attr. for DM_CONTROLLER, err=%d\n",
			    errn);
		}
	}

	/* if drive type not recognized so far, set it to "unknown" */

	if (!ctype_recognized) {
		nvlist_add_string(attr, TD_DISK_ATTR_CTYPE, "unknown");
	}

	return (errn);
}

/*
 * Function:	ddm_drive_set_btype()
 *
 * Description:	Retrieves disk bus type and add it
 *		to the nvlist of disk attributes.
 *
 * Parameters:
 *	ddm_handle_t d	- disk handle
 *	nvlist_t *attr	- list of disk attributes
 *
 * Return:
 *	0 - finished successfully
 *	error code - failed
 *
 * Scope:
 *	private
 */
static int
ddm_drive_set_btype(ddm_handle_t d, nvlist_t *attr)
{
	dm_descriptor_t	*ad;
	int		errn;
	nvlist_t	*nv_tmp;
	char		*btype;
	int		btype_recognized = B_FALSE;

	ad = dm_get_associated_descriptors((dm_descriptor_t)d, DM_BUS,
	    &errn);

	if ((errn != 0) || (ad == NULL) || (ad[0] == 0)) {
		DDM_DEBUG(DDM_DBGLVL_INFO, "ddm_drive_get_btype():"
		    "Can't get DM_BUS assoc. w/ DM_DRIVE, err=%d\n",
		    errn);

		/* free unused descriptors */

		if ((errn == 0) && (ad != NULL))
			dm_free_descriptors(ad);
	} else {
		/* get attributes for bus */
		nv_tmp = dm_get_attributes(ad[0], &errn);

		dm_free_descriptors(ad);

		if ((errn == 0) &&
		    (nvlist_lookup_string(nv_tmp, DM_BTYPE, &btype) == 0)) {

			nvlist_add_string(attr, TD_DISK_ATTR_BTYPE, btype);

			nvlist_free(nv_tmp);

			btype_recognized = B_TRUE;
		} else {
			nvlist_free(nv_tmp);
			DDM_DEBUG(DDM_DBGLVL_INFO, "ddm_drive_get_btype():"
			    "Can't get attr. for DM_BUS, err=%d\n",
			    errn);
		}
	}

	/* if bus type not recognized so far, set it to "unknown" */

	if (!btype_recognized) {
		nvlist_add_string(attr, TD_DISK_ATTR_BTYPE, "unknown");
	}

	return (errn);
}

/*
 * ddm_drive_get_name()
 *	Gets name of the drive from handle
 *
 * Parameters:
 *	ddm_handle_t d
 * Return:
 *	char *
 * Status:
 *	public
 */
static char *
ddm_drive_get_name(ddm_handle_t d)
{
	dm_descriptor_t	*ad;
	char		*name;
	int		errn;

	ad = dm_get_associated_descriptors((dm_descriptor_t)d, DM_ALIAS, &errn);

	if ((ad == NULL) || (errn != 0)) {
		DDM_DEBUG(DDM_DBGLVL_INFO, "ddm_drive_get_name(): "
		    "Can't get DM_ALIAS assoc. w/ DM_DRIVE, err=%d\n",
		    errn);

		return (NULL);
	}

	/* get "name" for ALIAS */
	name = dm_get_name(*ad, &errn);

	dm_free_descriptors(ad);

	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_INFO,
		    "ddm_drive_get_name(): Can't get alias name, err=%d\n",
		    errn);

		return (NULL);
	}

	return (name);
}

/*
 * ddm_drive_is_cdrom()
 *	Checks if drive is CD/DVD by means of DKIOCINFO ioctl
 *
 * Parameters:
 *	ddm_handle_t *d
 * Return:
 *	int
 * Status:
 *	public
 */
static int
ddm_drive_is_cdrom(ddm_handle_t d)
{
	int		fd;
	struct dk_cinfo	dk;
	char		*dn;
	char		*dn_cdt;

	/* get name of driver from handle */

	dn = ddm_drive_get_name(d);

	/*
	 * If drive name can't be obtained, filter the drive out as well
	 */

	if (dn == NULL)
		return (1);

	/* convert drive name to the device name, so that it can be opened */

	dn_cdt = ddm_create_sname_from_dname(dn);

	if (dn_cdt == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "ddm_drive_is_cdrom(): malloc() OOM\n");

		dm_free_name(dn);
		return (0);
	}

	fd = ddm_disk_open(dn_cdt);

	if (fd == -1) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_drive_is_cdrom(): Couldn't open %s\n",
		    dn_cdt);

		free(dn_cdt);
		dm_free_name(dn);
		return (0);
	}

	/* get controller info */

	if (ioctl(fd, DKIOCINFO, &dk) == -1) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "ddm_drive_is_cdrom(): ioctl(DKIOCINFO) failed\n");

		(void) close(fd);

		free(dn_cdt);
		dm_free_name(dn);
		return (0);
	} else {
		DDM_DEBUG(DDM_DBGLVL_NOTICE, "Controller name: %s\n",
		    dk.dki_cname);

		DDM_DEBUG(DDM_DBGLVL_NOTICE, "Controller type: %d\n",
		    (int)dk.dki_ctype);

		DDM_DEBUG(DDM_DBGLVL_NOTICE, "Drive name: %s\n", dk.dki_dname);
	}

	(void) close(fd);
	free(dn_cdt);
	dm_free_name(dn);

	/* test if it is CDROM */

	DDM_DEBUG(DDM_DBGLVL_NOTICE, "ddm_drive_is_cdrom(): CD:%s\n",
	    dk.dki_ctype == DKC_CDROM ? "Yes" : "No");

	if (dk.dki_ctype == DKC_CDROM) {
		return (1);
	} else {
		return (0);
	}
}

/*
 * ddm_drive_is_floppy()
 *	Checks if drive is FLOPPY by means of DKIOCINFO ioctl
 *
 * Parameters:
 *	ddm_handle_t *d
 * Return:
 *	int
 * Status:
 *	public
 */
static int
ddm_drive_is_floppy(ddm_handle_t d)
{
	char		*dn;
	int		drive_is_diskette;

	/* get name of driver from handle */

	dn = ddm_drive_get_name(d);

	/*
	 * If drive name can't be obtained, filter the drive out as well
	 */

	if (dn == NULL)
		return (1);

	/*
	 * look at the drive name - if it contains "diskette" string,
	 * report it as floppy disk
	 */

	if (strstr(dn, "diskette") != NULL)
		drive_is_diskette = 1;
	else
		drive_is_diskette = 0;

	dm_free_name(dn);
	return (drive_is_diskette);
}


/*
 * ddm_drive_is_zvol()
 *	Checks if drive is ZVOLUME
 *
 * Parameters:
 *	ddm_handle_t *d
 * Return:
 *	boolean_t
 * Status:
 *	public
 */
static boolean_t
ddm_drive_is_zvol(ddm_handle_t d)
{
	int		errn;
	nvlist_t	*dz;
	char		*devid;
	boolean_t	drive_is_zvol = B_FALSE;

	dz = dm_get_attributes(d, &errn);

	if (errn == 0) {
		if (nvlist_lookup_string(dz, DM_OPATH, &devid) == 0) {
			if (strncmp(devid, "/dev/zvol",
			    strlen("/dev/zvol")) == 0)
				drive_is_zvol = B_TRUE;
		}
	}
	return (drive_is_zvol);

}

/*
 * ddm_filter_disks()
 *	Excludes all drives not applicable as install target media from
 *	list of dm_descriptor_t and creates list of all possible target
 *	drives.	CD/DVD drives are excluded from list for now.
 *
 * Parameters:
 *	dm_descriptor_t *drives
 * Return:
 *
 * Status:
 *	public
 */
static dm_descriptor_t *
ddm_filter_disks(dm_descriptor_t *drives)
{
	int		i;
	int		df_num;

	dm_descriptor_t	*df;

	/*
	 * Obtain size of drives descriptor array and allocate memory
	 * for filtered array with the same size.
	 * Filtered array might be smaller than original one. In this
	 * case, part of it is left unused.
	 */

	for (i = 0; drives[i] != NULL; i++)
		;

	df = malloc((i + 1) * sizeof (dm_descriptor_t));

	if (df == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s", "malloc() OOM :-(\n");
		return (NULL);
	}

	for (i = df_num = 0; drives[i] != NULL; i++) {
		/* omit floppy disks */

		if (ddm_drive_is_floppy(drives[i]))
			continue;

		/* omit zvolumes */

		if (ddm_drive_is_zvol(drives[i]))
			continue;

		/* omit CD/DVD drives */

		if (ddm_drive_is_cdrom(drives[i]))
			continue;

		df[df_num++] = drives[i];
	}

	df[df_num] = NULL;
	return (df);
}

/* ----------------------- public functions --------------------------- */

/*
 * Function:	ddm_is_slice_name
 * Description:	Check to see a string syntactically represents a
 *		cannonical slice device name (e.g. c0t0d0s3).
 *		slice names cannot be path names (i.e. cannot contain
 *		any /'s.).
 *
 *		With World wide Name, we cannot check the
 * 		whole string, we will check the last two characters.
 *		They should be in the form 'sN', where N is a number
 *		between 0 and 15.
 * Scope:	public
 * Parameters:	str     - [RO]
 *			  string to be validated
 * Return:	0       - invalid slice name syntax
 *		1       - valid slice name syntax
 */
int
ddm_is_slice_name(char *str)
{
	/* validate parameters */
	if ((str == NULL) || (strlen(str) <= 2))
		return (0);

	if (strchr(str, '/') != NULL) {
		return (0);
	}

	/* first check for sX format, where X must be a digit */

	if ((str[strlen(str)-2] == 's') && isdigit(str[strlen(str)-1]))
		return (1);

	/*
	 * now try to check for sXX format, where XX must be
	 * in range <10;15>
	 */

	if (strlen(str) <= 3)
		return (0);

	if ((str[strlen(str)-3] == 's') &&
	    ((str[strlen(str)-2] == '0') || (str[strlen(str)-2] == '1')) &&
	    ((str[strlen(str)-1] >= '0') || (str[strlen(str)-1] <= '5')))
		return (1);

	return (0);
}

/*
 * ddm_get_disks()
 *	Disk discovery
 *
 * Parameters:
 *	none
 * Return:
 *	ddm_handle_t * - list of drive handles
 * Status:
 *	public
 */
ddm_handle_t *
ddm_get_disks(void)
{
	ddm_handle_t	*df;
	int		errn;

	DDM_DEBUG(DDM_DBGLVL_NOTICE, "%s",
	    "-> ddm_get_disks()\n");

	/*
	 * check if memory was freed appropriatelly
	 * (by calling ddm_free_handle_list()
	 * before we allocate it again
	 */

	assert(ddm_drive_desc == NULL);

	ddm_drive_desc = dm_get_descriptors(DM_DRIVE, NULL, &errn);

	if (ddm_drive_desc == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_disks(): Can't get disk info, err=%d\n", errn);

		return (NULL);
	}

	/* filter all drives, which are not applicable as target for install */

	df = (ddm_handle_t *)ddm_filter_disks(ddm_drive_desc);

	if (df == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "Couldn't filter the disks\n");
	}

	return (df);
}

/*
 * ddm_get_disks_attributes()
 * 	Get attributes for particular disk
 * Parameters:	d	handle of drive
 *
 * Return:	pointer to nvlist containing attributes
 */
nvlist_t *
ddm_get_disk_attributes(ddm_handle_t disk)
{
	dm_descriptor_t	*ad;
	nvlist_t	*nv_src, *nv_dst, *nv_tmp;
	int		errn;
	char		*dn;
	char		*id;
	uint32_t	disk_label;
	char		*curr_bootdisk;

	/* ask for current boot disk name */

	curr_bootdisk = ddm_get_curr_bootdisk();

	if (curr_bootdisk != NULL) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE, "ddm_get_disk_attributes():"
		    "Current bootdisk: %s\n", curr_bootdisk);
	} else {
		DDM_DEBUG(DDM_DBGLVL_WARNING,
		    "ddm_get_disk_attributes():Can't get current bootdisk\n");
	}

	/*
	 * Since DM_DRIVE contains only limited set of information,it is
	 * necessary to collect disk attributes from DM_CONTROLLER and
	 * DM_MEDIA associated with DM_DRIVE. Acquire information about
	 * name, size, media type (fixed, floppy, ...), drive type
	 * (ata, usb, scsi, ...).
	 */

	ad = dm_get_associated_descriptors(disk, DM_MEDIA, &errn);

	/*
	 * If there is no associated DM_MEDIA descriptor it might be due
	 * to the fact that drive is removable and media is not loaded.
	 * In this case, it still would be useful to provide available
	 * information about the drive.
	 */

	if ((errn != 0) || (ad == NULL) || (ad[0] == 0)) {
		DDM_DEBUG(DDM_DBGLVL_WARNING, "ddm_get_disk_attributes():"
		    "Can't get DM_MEDIA assoc. w/ DM_DRIVE, err=%d\n",
		    errn);

		/*
		 * free media descriptors, if they were alocated, because
		 * they are not to be used
		 */

		if ((errn == 0) && (ad != NULL))
			dm_free_descriptors(ad);

		/*
		 * get nvlist attributes from libdiskmgt and convert to libtd
		 * namespace. Keep original nvlist for later processing.
		 */

		nv_src = dm_get_attributes(disk, &errn);

		if (errn != 0) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes():"
			    " Can't get attr. for DM_DRIVE, err=%d\n", errn);

			return (NULL);
		}

		if (ddm_conv_attr_list(nv_src, ddm_disk_attr_conv_tbl, &nv_dst)
		    != DDM_SUCCESS) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes()"
			    " Can't convert nvlist to libtd namespace\n");

			nvlist_free(nv_src);
			return (NULL);
		}

		/* get disk name and add it to the attribute list */
		dn = ddm_drive_get_name(disk);

		if (dn == NULL) {
			DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes()"
			    " Couldn't get disk name\n");

			nvlist_free(nv_src);
			return (NULL);
		}

		nvlist_add_string(nv_dst, TD_DISK_ATTR_NAME, dn);

		/*
		 * if the disk is set as current bootdisk, add
		 * TD_DISK_ATTR_CURRBOOT to the list
		 */

		if ((curr_bootdisk != NULL) &&
		    (strcmp(curr_bootdisk, dn) == 0)) {

			nvlist_add_boolean(nv_dst, TD_DISK_ATTR_CURRBOOT);

			free(curr_bootdisk);
		}

		dm_free_name(dn);

		/* add controller type to the list of attributes */

		(void) ddm_drive_set_ctype(disk, nv_dst);

		/* add bus type to the list of attributes */
		(void) ddm_drive_set_btype(disk, nv_dst);

		/* free original libdiskmgt nvlist and return */

		nvlist_free(nv_src);
		return (nv_dst);
	}

	/* get attributes for media and convert to libtd namespace */

	nv_src = dm_get_attributes(ad[0], &errn);

	dm_free_descriptors(ad);

	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes()"
		    " Can't get attr. for DM_MEDIA, err=%d\n", errn);

		return (NULL);
	}

	if (ddm_conv_attr_list(nv_src, ddm_disk_attr_conv_tbl, &nv_dst)
	    != DDM_SUCCESS) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes()"
		    " Can't convert nvlist to libtd namespace\n");

		nvlist_free(nv_src);
		return (NULL);
	}

	/* get disk name and add it to the attribute list */
	dn = ddm_drive_get_name(disk);

	if (dn == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_disk_attributes()"
		    " Couldn't get disk name\n");

		nvlist_free(nv_src);
		nvlist_free(nv_dst);
		return (NULL);
	}

	nvlist_add_string(nv_dst, TD_DISK_ATTR_NAME, dn);

	/*
	 * if the disk is set as current bootdisk, add
	 * TD_DISK_ATTR_CURRBOOT to the list
	 */

	if ((curr_bootdisk != NULL) &&
	    (strcmp(curr_bootdisk, dn) == 0)) {

		nvlist_add_boolean(nv_dst, TD_DISK_ATTR_CURRBOOT);
	}

	free(curr_bootdisk);

	/*
	 * add vendor ID, product ID, device ID - they are
	 * DM_DRIVE attributes
	 */

	nv_tmp = dm_get_attributes(disk, &errn);

	if (errn == 0) {
		if (nvlist_lookup_string(nv_tmp, DM_VENDOR_ID, &id) == 0)
			nvlist_add_string(nv_dst, TD_DISK_ATTR_VENDOR, id);
		else
			nvlist_add_string(nv_dst, TD_DISK_ATTR_VENDOR,
			    "unknown");

		if (nvlist_lookup_string(nv_tmp, DM_PRODUCT_ID, &id) == 0)
			nvlist_add_string(nv_dst, TD_DISK_ATTR_PRODUCT, id);
		else
			nvlist_add_string(nv_dst, TD_DISK_ATTR_PRODUCT,
			    "unknown");

		if (nvlist_lookup_string(nv_tmp, DM_OPATH, &id) == 0)
			nvlist_add_string(nv_dst, TD_DISK_ATTR_DEVID, id);
		else
			nvlist_add_string(nv_dst, TD_DISK_ATTR_DEVID,
			    "unknown");

		nvlist_free(nv_tmp);
	} else {
		DDM_DEBUG(DDM_DBGLVL_INFO, "ddm_get_disk_attributes()"
		    " Can't get \"vendor, product id or device id\" "
		    "for DM_DRIVE, err=%d\n", errn);

		nvlist_add_string(nv_dst, TD_DISK_ATTR_VENDOR, "unknown");
		nvlist_add_string(nv_dst, TD_DISK_ATTR_PRODUCT, "unknown");
		nvlist_add_string(nv_dst, TD_DISK_ATTR_DEVID, "unknown");
	}

	/*
	 * ask for drive type - usb, ata, scsi, fibre channel.
	 * If it is not possible to determine the type, it is
	 * set it to "unknown"
	 */

	(void) ddm_drive_set_ctype(disk, nv_dst);

	/*
	 * try to recognize which labels disk actually contains
	 */
	disk_label = TD_DISK_LABEL_NONE;

	/* check for GPT label */
	if (nvlist_lookup_boolean(nv_src, DM_EFI) == 0)
		disk_label |= TD_DISK_LABEL_GPT;

	/* check for fdisk label */
	if (nvlist_lookup_boolean(nv_src, DM_FDISK) == 0)
		disk_label |= TD_DISK_LABEL_FDISK;

	/*
	 * check for VTOC label
	 */

	if (ddm_disk_has_vtoc(dn)) {
		disk_label |= TD_DISK_LABEL_VTOC;
	}

	nvlist_add_uint32(nv_dst, TD_DISK_ATTR_LABEL, disk_label);

	dm_free_name(dn);

	nvlist_free(nv_src);
	return (nv_dst);
}

/*
 * ddm_get_partitions()
 * 	Discovers partitions for particular disk
 * Parameters: d	handle of drive, which is subject of partition discovery
 *			process. If set to DDM_DISCOVER_ALL, all partitions for
 *			all drives are reported.
 */
ddm_handle_t *
ddm_get_partitions(ddm_handle_t d)
{
	dm_descriptor_t	*am;
	dm_descriptor_t	*ddm_part_desc;
	int		errn;

	/* discover all partitions for all drives */

	if (d == DDM_DISCOVER_ALL) {
		ddm_part_desc = dm_get_descriptors(DM_PARTITION, NULL, &errn);

		if ((ddm_part_desc == NULL) || (errn != 0)) {
			DDM_DEBUG(DDM_DBGLVL_ERROR,
			    "ddm_get_partitions(): Can't get partition desc,"
			    "err=%d\n", errn);

			return (NULL);
		}

		return ((ddm_handle_t *)ddm_part_desc);
	}

	/* discover partitions for particular drive */

	/*
	 * since there is no association between drive and partition,
	 * we need to acquire ask for media, which is associated with drive
	 * on the one side and with partition on the other side.
	 */

	am = dm_get_associated_descriptors(d, DM_MEDIA, &errn);

	if ((am == NULL) || (errn != 0)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_partitions(): No DM_MEDIA assoc. w/ DM_DRIVE,"
		    "err=%d\n", errn);

		return (NULL);
	}

	/*
	 * since there is 1:1 relationship between drive and media, use
	 * the first (and the only) descriptor when asking for partitions
	 */

	ddm_part_desc = dm_get_associated_descriptors(am[0], DM_PARTITION,
	    &errn);

	if ((ddm_part_desc == NULL) || (errn != 0)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_partitions(): No DM_PARTITION assoc. w/ DM_MEDIA,"
		    "err=%d\n", errn);

		dm_free_descriptors(am);
		return (NULL);
	}

	dm_free_descriptors(am);
	return ((ddm_handle_t *)ddm_part_desc);
}

/*
 * ddm_get_partition_attributes()
 * 	Get attributes for particular partition
 * Parameters:	p	handle of partition
 *
 * Return:	pointer to nvlist containing attributes
 */
nvlist_t *
ddm_get_partition_attributes(ddm_handle_t p)
{
	nvlist_t	*nv_src, *nv_dst;
	int		errn;
	int		ln;
	char		*name, *bname;
	uint32_t	part_id;

	/*
	 * get attributes from libdiskmgt and convert nvlist
	 * to the libtd namespace
	 */

	nv_src = dm_get_attributes(p, &errn);

	if (errn) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_partition_attributes(): Can't get part attr,"
		    "err=%d\n", errn);

		return (NULL);
	}

	if (ddm_conv_attr_list(nv_src, ddm_part_attr_conv_tbl, &nv_dst)
	    != DDM_SUCCESS) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_partition_attributes()"
		    " Can't convert nvlist to libtd namespace\n");

		nvlist_free(nv_src);
		return (NULL);
	}

	/* we don't need source attribute list anymore - free it */

	nvlist_free(nv_src);

	/*
	 * The name is not part of nvlist, we need to
	 * add it to the attribute list
	 */
	name = dm_get_name(p, &errn);

	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_partition_attributes(): Can't get part name,"
		    "err=%d\n", errn);

		/*
		 * Free list of attributes, we already acquired,
		 * because it is useless w/o partition name
		 */

		nvlist_free(nv_dst);
		return (NULL);
	}

	/* strip /dev/[r]dsk/ prefix - report only ctdp basename */

	bname = basename(name);

	if (bname == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "ddm_get_partition_attributes(): Can't get part bname\n");

		/*
		 * Free list of attributes, we already acquired,
		 * because it is useless w/o partition name
		 */
		dm_free_name(name);
		nvlist_free(nv_dst);
		return (NULL);
	}

	nvlist_add_string(nv_dst, TD_PART_ATTR_NAME, bname);

	/*
	 * check if it is Linux swap partition - do
	 * it only for partitions with ID 0x82 which
	 * might be also Solaris partition
	 */

	if ((nvlist_lookup_uint32(nv_dst, TD_PART_ATTR_TYPE, &part_id) == 0) &&
	    (part_id == SUNIXOS) && ddm_is_linux_swap(name)) {
		nvlist_add_uint32(nv_dst, TD_PART_ATTR_CONTENT,
		    TD_PART_CONTENT_LSWAP);
	} else {
		nvlist_add_uint32(nv_dst, TD_PART_ATTR_CONTENT,
		    TD_PART_CONTENT_UNKNOWN);
	}

	dm_free_name(name);
	return (nv_dst);
}

/*
 * ddm_get_slices()
 * 	Discovers slices for particular disk/partition or discover all
 *	slices
 * Parameters:	h	handle of drive/partition, for which slices will be
 *			discovered. If NULL, all slices are reported.
 */
ddm_handle_t *
ddm_get_slices(ddm_handle_t h)
{
	dm_descriptor_t	*ddm_slice_desc;
	dm_descriptor_t	*am;
	dm_desc_type_t	desc_type;

	int		errn;


	/* discover all slices */

	if (h == DDM_DISCOVER_ALL) {
		ddm_slice_desc = dm_get_descriptors(DM_SLICE, NULL, &errn);

		if ((ddm_slice_desc == NULL) || (errn != 0)) {
			DDM_DEBUG(DDM_DBGLVL_ERROR,
			    "ddm_get_slices(): Can't get slice info, err=%d\n",
			    errn);

			return (NULL);
		}

		return ((ddm_handle_t *)ddm_slice_desc);
	}

	/*
	 * Discover slices for particular drive/partition.
	 * first check, if slice type is associated with
	 * the type provided by handle
	 */

	desc_type = dm_get_type((dm_descriptor_t)h);

	/* slice can be only discovered for particular disk or partition */

	if ((desc_type != DM_DRIVE) && (desc_type != DM_PARTITION)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "ddm_get_slices(): This handle is not assoc with slice\n");

		return (NULL);
	}

	/*
	 * Slices are directly associated with partition, so it is easy to
	 * get list of them from given partiton
	 */
	if (desc_type == DM_PARTITION) {
		ddm_slice_desc = dm_get_associated_descriptors(h, DM_SLICE,
		    &errn);

		if ((ddm_slice_desc == NULL) || (errn != 0)) {
			DDM_DEBUG(DDM_DBGLVL_ERROR,
			    "ddm_get_slices(): No slices from part., err=%d\n",
			    errn);

			return (NULL);
		}

		return ((ddm_handle_t *)ddm_slice_desc);
	}

	/*
	 * Since there is no direct association between slices and drive
	 * it is necessary to discover media associated 1:1 with drive.
	 * And since media is associated with slices, it is possible to
	 * discover them
	 */

	am = dm_get_associated_descriptors(h, DM_MEDIA, &errn);

	if ((am == NULL) || (errn != 0)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_slices(): Can't get media info, err=%d\n",
		    errn);

		return (NULL);
	}

	ddm_slice_desc = dm_get_associated_descriptors(am[0], DM_SLICE,
	    &errn);

	if ((ddm_slice_desc == NULL) || (errn != 0)) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_slices(): No slices from disk., err=%d\n",
		    errn);

		return (NULL);
	}

	dm_free_descriptors(am);
	return ((ddm_handle_t *)ddm_slice_desc);
}

/*
 * ddm_get_slice_attributes()
 * 	Get attributes for particular slice
 * Parameters:	s	handle of slice
 *
 * Return:	pointer to nvlist containing attributes
 */
nvlist_t *
ddm_get_slice_attributes(ddm_handle_t s)
{
	nvlist_t	*nv_src, *nv_dst;
	int		errn;
	char		*name, *bname, *last_mount;

	/*
	 * get nvlist of attributes from libdiskmgt library and
	 * convert it to the libtd namespace
	 */

	nv_src = dm_get_attributes(s, &errn);

	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_slice_attributes(): Can't get slice attr,"
		    "err=%d\n", errn);

		return (NULL);
	}

	if (ddm_conv_attr_list(nv_src, ddm_slice_attr_conv_tbl, &nv_dst)
	    != DDM_SUCCESS) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "ddm_get_slice_attributes()"
		    " Can't convert nvlist to libtd namespace\n");

		nvlist_free(nv_src);
		return (NULL);
	}

	/* free libdiskmgt attributes - they are not needed anymore */

	nvlist_free(nv_src);

	/*
	 * The name is not part of nvlist, we need to
	 * add it to the attribute list
	 */
	name = dm_get_name(s, &errn);

	if (errn != 0) {
		DDM_DEBUG(DDM_DBGLVL_ERROR,
		    "ddm_get_slice_attributes(): Can't get slice name,"
		    "err=%d\n", errn);

		/*
		 * Free list of attributes, we already acquired,
		 * because it is useless w/o slice name
		 */

		nvlist_free(nv_dst);
		return (NULL);
	}

	/* strip /dev/[r]dsk/ prefix - report only ctds basename */

	bname = basename(name);

	if (bname == NULL) {
		DDM_DEBUG(DDM_DBGLVL_ERROR, "%s",
		    "ddm_get_slice_attributes(): Can't get slice bname\n");

		/*
		 * Free list of attributes, we already acquired,
		 * because it is useless w/o slice name
		 */
		dm_free_name(name);
		nvlist_free(nv_dst);
		return (NULL);
	}

	nvlist_add_string(nv_dst, TD_SLICE_ATTR_NAME, bname);

	/*
	 * Add "last mounted" by directly looking into UFS superblock.
	 */

	last_mount = ddm_ufs_get_lastmount(name);

	if (last_mount == NULL) {
		DDM_DEBUG(DDM_DBGLVL_NOTICE,
		    "ddm_get_slice_attributes(): Can't get last mntpt for %s\n",
		    name);

		nvlist_add_string(nv_dst, TD_SLICE_ATTR_LASTMNT, "");
	} else {
		nvlist_add_string(nv_dst, TD_SLICE_ATTR_LASTMNT, last_mount);
	}

	/* slice name is not necessary anymore - free it */
	dm_free_name(name);
	return (nv_dst);
}

/*
 * ddm_free_handle_list()
 * Frees list of handles returned by
 * ddm_get_<object>() functions.
 */
void
ddm_free_handle_list(ddm_handle_t *h)
{
	assert(h != NULL);

	DDM_DEBUG(DDM_DBGLVL_NOTICE, "%s",
	    "-> ddm_free_handle_list()\n");

	/*
	 * If it is disk handle, it need special treatment.
	 * The reason for this is that during the filter operation
	 * carried out in _ddm_filter_disks(), we create new array
	 * of descriptors,  which contains only drives eligible for
	 * installation and this array is provided to the consumer.
	 * But we still need to keep original array of descriptors
	 * provided by libdiskmgt, so that we can use appropriate
	 * libdiskmgt interfaces for obtaining more particular
	 * information about drives. Since this filter operation
	 * is only carried out for drives, the requirement to free
	 * both original as well as filtered arrays applies only to
	 * drive descriptors.
	 */

	if (dm_get_type(h[0]) == DM_DRIVE) {
		free(h);

		if (ddm_drive_desc != NULL)
			dm_free_descriptors(ddm_drive_desc);

		ddm_drive_desc = NULL;
	} else {
		dm_free_descriptors(h);
	}
}

/*
 * ddm_free_attr_list()
 */
void
ddm_free_attr_list(nvlist_t *attrs)
{
	assert(attrs != NULL);

	nvlist_free(attrs);
}

/*
 * ddm_debug_print()
 */
void
ddm_debug_print(ls_dbglvl_t dbg_lvl, const char *fmt, ...)
{
	va_list	ap;
	char	buf[MAXPATHLEN + 1];

	va_start(ap, fmt);
	(void) vsprintf(buf, fmt, ap);
	(void) ls_write_dbg_message("TDDM", dbg_lvl, buf);
	va_end(ap);
}
