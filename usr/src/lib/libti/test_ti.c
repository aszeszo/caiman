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

#include <assert.h>
#include <libnvpair.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <stropts.h>

#include <sys/types.h>

#include <sys/dkio.h>
#include <sys/vtoc.h>

#include <sys/stat.h>
#include <fcntl.h>

#include <ti_api.h>
#include <ls_api.h>

/* local constants */

#define	TI_TST_SLICE_NUM	2

/* local typedefs */

/*
 * ti_cb()
 */

static ti_errno_t
ti_cb(nvlist_t *progress)
{
	uint16_t	ms_curr;
	uint16_t	ms_num;
	uint16_t	ms_perc_done;
	uint16_t	ms_perc;

	printf("Callback invoked:\n");

	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_NUM, &ms_num);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_CURR, &ms_curr);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_PERC_DONE, &ms_perc_done);
	nvlist_lookup_uint16(progress, TI_PROGRESS_MS_PERC, &ms_perc);

	printf(" MS=%d/%d(%d%%) , %d%% of total TI is finished\n",
	    ms_curr, ms_num, ms_perc_done, ms_perc);
}

/*
 * display_help()
 */
static void
display_help(void)
{
	(void) printf("usage: test_ti "
	    "[-h] [-x 0-3] [-c] [-t target_type] ... [-R]\n"
	    "  -h                print this help\n"
	    "  -x [0-3]          set debug level (0=emerg, 3=info)\n"
	    "  -c                commit changes - switch off dry run\n"
	    "  -t target_type    specify target type: "
	    "f=fdisk, v=vtoc, b=BE, p=ZFS pool, m=ZFS filesystem, l=ZFS volume,"
	    " r=ramdisk, d=directory\n"
	    " fdisk options (select fdisk type: option \"-t f\")\n"
	    "  -w                Solaris2 partition created on whole disk\n"
	    "  -f file           create fdisk partition table from file\n"
	    "  -d disk_name      disk name - e.g c1t0d0\n"
	    " VTOC options (select VTOC type: option \"-t v\")\n"
	    "  -d disk_name      disk name - e.g c1t0d0\n"
	    "  -f file           create VTOC from file - if not provided, "
	    "create default layout (s0 will occupy all space)\n"
	    " ZFS root pool options (select ZFS root pool type: "
	    "option \"-t p\")\n"
	    "  -p pool_name      name of root pool\n"
	    "  -d device_name    disk or slice name - e.g. c1t0d0s0\n"
	    " BE options (select BE type: option \"-t b\")\n"
	    "  -p pool_name      name of ZFS pool\n"
	    "  -n be_name        name of BE\n"
	    " ZFS filesystem options (select ZFS filesystem type: "
	    "option \"-t m\")\n"
	    "  -p pool_name      name of ZFS pool\n"
	    "  -n fs_name        name of ZFS filesystem\n"
	    " ZFS volume options (select ZFS volume type: option \"-t l\")\n"
	    "  -p pool_name      name of ZFS pool\n"
	    "  -z size_mb        size of ZFS volume to be created\n"
	    "  -n vol_name       name of ZFS volume\n"
	    "  -u vol_type       ZFS volume type (0-generic, 1-swap, 2-dump)\n"
	    " ramdisk options (select ramdisk type: option \"-t r\")\n"
	    "  -r ramdisk_size   size of ramdisk in Kbytes\n"
	    "  -m ramdisk_mp     mount point of ramdisk\n"
	    "  -b boot_archive   file name of boot archive\n"
	    "  -R                release indicated target (see -m, -b)\n"
	    " create directory for DC (select type \"-t d\")\n"
	    "  -m path\n");
}


/*
 * create_fdisk_target()
 */

static int
prepare_fdisk_target(nvlist_t *target_attrs, char *disk_name,
    char *pt_file_name, boolean_t whole_disk)
{
	FILE		*pt_file;
	char		fdisk_line[1000];
	uint16_t	part_num;
	int		ret;
	uint_t		id, active;
	uint64_t	bh, bs, bc, eh, es, ec, offset, size;

	uint8_t		*pid, *pactive;
	uint64_t	*pbh, *pbs, *pbc, *peh, *pes, *pec, *poffset, *psize;

	assert(target_attrs != NULL);

	/* add atributes requiring creating Solaris2 partition on whole disk */

	/* disk name */

	if (nvlist_add_string(target_attrs, TI_ATTR_FDISK_DISK_NAME,
	    disk_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_FDISK_DISK_NAME to"
		    "nvlist\n");

		return (-1);
	}

	/*
	 * use whole disk for Solaris partition ?
	 * If not, fdisk partition table needs to be provided in file
	 */

	if (whole_disk) {
		if (nvlist_add_boolean_value(target_attrs,
		    TI_ATTR_FDISK_WDISK_FL, B_TRUE) != 0) {
			(void) fprintf(stderr, "ERR: Couldn't add "
			    "TI_ATTR_FDISK_WDISK_FL to nvlist\n");

			return (-1);
		}
	} else {
		if (pt_file_name == NULL) {
			(void) fprintf(stderr,
			    "ERR: whole disk mode not set and no partition "
			    "information available\n");

			return (-1);
		}

		/*
		 * open partition info file and populate attribute nv list
		 * accordingly
		 */

		pt_file = fopen(pt_file_name, "r");

		if (pt_file == NULL) {
			(void) fprintf(stderr,
			    "ERR: Couldn't open %s file for reading\n");

			return (-1);
		}

		/*
		 * File is in format which is produced by "fdisk(1M) -W"
		 * command. Please see fdisk(1M) man page for details
		 */

		part_num = 0;

		pid = pactive = NULL;
		pbh = pbs = pbc = peh = pes = pec = poffset = psize = NULL;

		while (fgets(fdisk_line, sizeof (fdisk_line), pt_file) !=
		    NULL) {

			/*
			 * lines starting with '*' are comments - ignore them
			 * as well as empty lines
			 */

			if ((fdisk_line[0] == '*') || (fdisk_line[0] == '\n'))
				continue;

			/*
			 * read line describing partition/logical volume.
			 * Line is in following format (decimal numbers):
			 *
			 * id act bhead bsect bcyl ehead esect ecyl rsect nsect
			 *
			 * id - partition
			 * act - active flag - 0|128
			 * bhead, bsect, bcyl - start of partition in CHS format
			 * ehead, esect, ecyl - end of partition in CHS format
			 * rsect - partition offset in sectors from beginning
			 *	   of the disk
			 * numsect - size of partition in sectors
			 */

			id = active = bh = bs = bc = eh = es = ec = offset =
			    size = 0;

			ret = sscanf(fdisk_line,
			    "%d%d%llu%llu%llu%llu%llu%llu%llu%llu",
			    &id, &active, &bh, &bs, &bc, &eh, &es, &ec,
			    &offset, &size);

			if (ret != 10) {
				(void) fprintf(stderr,
				    "following fdisk line has invalid format:\n"
				    "%s\n", fdisk_line);

				(void) fprintf(stderr, "sscanf returned %d: "
				    "%d,%d,%llu,%llu,%llu,%llu,%llu,%llu,%llu,"
				    "%llu\n", ret, id, active, bh, bs, bc, eh,
				    es, ec, offset, size);

				(void) fclose(pt_file);

				return (-1);
			}

			part_num++;

			/* reallocate memory for another line */

			pid = realloc(pid, part_num * sizeof (uint8_t));
			pactive = realloc(pactive, part_num * sizeof (uint8_t));
			pbh = realloc(pbh, part_num * sizeof (uint64_t));
			pbs = realloc(pbs, part_num * sizeof (uint64_t));
			pbc = realloc(pbc, part_num * sizeof (uint64_t));
			peh = realloc(peh, part_num * sizeof (uint64_t));
			pes = realloc(pes, part_num * sizeof (uint64_t));
			pec = realloc(pec, part_num * sizeof (uint64_t));
			poffset = realloc(poffset, part_num *
			    sizeof (uint64_t));
			psize = realloc(psize, part_num * sizeof (uint64_t));

			if (pid == NULL || pactive == NULL ||
			    pbh == NULL || pbs == NULL || pbc == NULL ||
			    peh == NULL || pes == NULL || pec == NULL ||
			    poffset == NULL || psize == NULL) {
				(void) fprintf(stderr,
				    "Memory allocation failed\n");

				(void) fclose(pt_file);

				return (-1);
			}

			/* fill in data */

			pid[part_num - 1] = id;
			pactive[part_num - 1] = active;
			pbh[part_num - 1] = bh;
			pbs[part_num - 1] = bs;
			pbc[part_num - 1] = bc;
			peh[part_num - 1] = eh;
			pes[part_num - 1] = es;
			pec[part_num - 1] = ec;
			poffset[part_num - 1] = offset;
			psize[part_num - 1] = size;
		}

		(void) fclose(pt_file);

		/* add number of partitions to be created */

		if (nvlist_add_uint16(target_attrs, TI_ATTR_FDISK_PART_NUM,
		    part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_NUM to nvlist\n");

			return (-1);
		}

		/* add partition geometry configuration */

		/* ID */

		if (nvlist_add_uint8_array(target_attrs, TI_ATTR_FDISK_PART_IDS,
		    pid, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_NUM to nvlist\n");

			return (-1);
		}

		/* ACTIVE */

		if (nvlist_add_uint8_array(target_attrs,
		    TI_ATTR_FDISK_PART_ACTIVE, pactive, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_ACTIVE to nvlist\n");

			return (-1);
		}

		/* bhead */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_BHEADS, pbh, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_BHEADS to nvlist\n");

			return (-1);
		}

		/* bsec */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_BSECTS, pbs, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_BSECTS to nvlist\n");

			return (-1);
		}

		/* bcyl */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_BCYLS, pbc, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_BCYLS to nvlist\n");

			return (-1);
		}

		/* ehead */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_EHEADS, peh, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_EHEADS to nvlist\n");

			return (-1);
		}

		/* esec */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_ESECTS, pes, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_ESECTS to nvlist\n");

			return (-1);
		}

		/* ecyl */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_ECYLS, pec, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_ECYLS to nvlist\n");

			return (-1);
		}

		/* offset */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_RSECTS, poffset, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_RSECTS to nvlist\n");

			return (-1);
		}

		/* size */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_FDISK_PART_NUMSECTS, psize, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_FDISK_PART_NUMSECTS to nvlist\n");

			return (-1);
		}
	}

	return (0);
}


/*
 * prepare_vtoc_target()
 */

static int
prepare_vtoc_target(nvlist_t *target_attrs, char *disk_name,
    char *layout_file_name, boolean_t default_layout)
{
	FILE		*pt_file;
	char		vtoc_line[1000];
	uint16_t	part_num;
	int		ret;
	int		num, tag, flag;
	uint64_t	start, size;

	uint16_t	*pnum, *ptag, *pflag;
	uint64_t	*pstart, *psize;

	assert(target_attrs != NULL);

	/* add atributes requiring creating VTOC */

	/* disk name */

	if (nvlist_add_string(target_attrs, TI_ATTR_SLICE_DISK_NAME,
	    disk_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_SLICE_DISK_NAME to"
		    "nvlist\n");

		return (-1);
	}

	/*
	 * create default or customized layout ?
	 * If customized layout is to be created, file containing layout
	 * configuration needs to be provided
	 */

	if (default_layout) {
		if (nvlist_add_boolean_value(target_attrs,
		    TI_ATTR_SLICE_DEFAULT_LAYOUT, B_TRUE) != 0) {
			(void) fprintf(stderr, "ERR: Couldn't add "
			    "TI_ATTR_SLICE_DEFAULT_LAYOUT to nvlist\n");

			return (-1);
		}
	} else {
		/*
		 * open file containing information about VTOC layout
		 * to be created and populate attribute nv list accordingly
		 */

		pt_file = fopen(layout_file_name, "r");

		if (pt_file == NULL) {
			(void) fprintf(stderr,
			    "ERR: Couldn't open %s file for reading\n");

			return (-1);
		}

		/*
		 * File is in format which is produced by prtvtoc(1M) command
		 * and which can be passed to "fmthard(1M) -s" command.
		 */

		part_num = 0;

		pnum = ptag = pflag = NULL;
		pstart = psize = NULL;

		while (fgets(vtoc_line, sizeof (vtoc_line), pt_file) != NULL) {

			/*
			 * lines starting with '*' are comments - ignore them
			 * as well as empty lines
			 */

			if ((vtoc_line[0] == '*') || (vtoc_line[0] == '\n'))
				continue;

			/*
			 * read line describing VTOC slice.
			 * Line is in following format (decimal numbers):
			 *
			 * num tag flag 1st_sector size_in_sectors
			 *
			 * num - slice number - 0-7 for Sparc, 0-15 for x86
			 * tag - slice tag
			 *	 0 - V_UNASSIGNED
			 *	 1 - V_BOOT
			 *	 2 - V_ROOT
			 *	 3 - V_SWAP
			 *	 4 - V_USR
			 *	 5 - V_BACKUP
			 *	 6 - V_STAND
			 *	 7 - V_VAR
			 *	 8 - V_HOME
			 * flag - slice flag
			 *	 01 - V_UNMNT
			 *	 10 - V_RONLY
			 * 1st_sector - 1st sector of slice
			 * size_in_sectors - slice size in sectors
			 */

			num = tag = flag = 0;
			start = size = 0;

			ret = sscanf(vtoc_line, "%d%d%X%llu%llu",
			    &num, &tag, &flag, &start, &size);

			if (ret != 5) {
				(void) fprintf(stderr,
				    "following slice line has invalid format:\n"
				    "%s\n", vtoc_line);

				(void) fprintf(stderr, "sscanf returned %d: "
				    "%d,%02X,%llu,%llu\n", ret,
				    num, tag, flag, start, size);

				(void) fclose(pt_file);

				return (-1);
			}

			part_num++;

			/* reallocate memory for another line */

			pnum = realloc(pnum, part_num * sizeof (uint16_t));
			ptag = realloc(ptag, part_num * sizeof (uint16_t));
			pflag = realloc(pflag, part_num * sizeof (uint16_t));
			pstart = realloc(pstart, part_num * sizeof (uint64_t));
			psize = realloc(psize, part_num * sizeof (uint64_t));

			if (pnum == NULL || ptag == NULL ||
			    pflag == NULL || pstart == NULL || psize == NULL) {
				(void) fprintf(stderr,
				    "Memory allocation failed\n");

				(void) fclose(pt_file);

				return (-1);
			}

			/* fill in data */

			pnum[part_num - 1] = num;
			ptag[part_num - 1] = tag;
			pflag[part_num - 1] = flag;
			pstart[part_num - 1] = start;
			psize[part_num - 1] = size;
		}

		(void) fclose(pt_file);

		/* add number of slices to be created */

		if (nvlist_add_uint16(target_attrs, TI_ATTR_SLICE_NUM,
		    part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_NUM to nvlist\n");

			return (-1);
		}

		/* add slice geometry configuration */

		/* slice numbers */

		if (nvlist_add_uint16_array(target_attrs, TI_ATTR_SLICE_PARTS,
		    pnum, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_PARTS to nvlist\n");

			return (-1);
		}

		/* slice tags */

		if (nvlist_add_uint16_array(target_attrs,
		    TI_ATTR_SLICE_TAGS, ptag, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_TAGS to nvlist\n");

			return (-1);
		}

		/* slice flags */

		if (nvlist_add_uint16_array(target_attrs,
		    TI_ATTR_SLICE_FLAGS, pflag, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_FLAGS to nvlist\n");

			return (-1);
		}

		/* slice start */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_SLICE_1STSECS, pstart, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_1STSECS to nvlist\n");

			return (-1);
		}

		/* slice size */

		if (nvlist_add_uint64_array(target_attrs,
		    TI_ATTR_SLICE_SIZES, psize, part_num) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_SLICE_SIZES to nvlist\n");

			return (-1);
		}
	}

	return (0);
}


/*
 * prepare_be_target()
 */

static int
prepare_be_target(nvlist_t *target_attrs, char *rpool_name, char *be_name)
{
	char	fs_num = 4;
	char	*fs_names[4] =
	    {"/", "/usr", "/var", "/opt"};

	char	fs_shared_num = 3;
	char	*fs_shared_names[3] =
	    {"/export", "/export/home", "/export/home/dambi"};

	/* target type */

	if (nvlist_add_uint32(target_attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_BE) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (-1);
	}

	/* root pool name */

	if (nvlist_add_string(target_attrs, TI_ATTR_BE_RPOOL_NAME,
	    rpool_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_BE_RPOOL_NAME to"
		    "nvlist\n");

		return (-1);
	}

	/* BE name */

	if (nvlist_add_string(target_attrs, TI_ATTR_BE_NAME,
	    be_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_BE_NAME to"
		    "nvlist\n");

		return (-1);
	}

	/* file systems to be created */

	if (nvlist_add_string_array(target_attrs, TI_ATTR_BE_FS_NAMES,
	    fs_names, fs_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_BE_FS_NAMES to"
		    "nvlist\n");

		return (-1);
	}

	/* file systems to be created */

	if (nvlist_add_string_array(target_attrs, TI_ATTR_BE_SHARED_FS_NAMES,
	    fs_shared_names, fs_shared_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_BE_SHARED_FS_NAMES"
		    "to nvlist\n");

		return (-1);
	}

	return (0);
}

/*
 * prepare_zfs_rpool_target()
 */

static int
prepare_zfs_rpool_target(nvlist_t *target_attrs, char *rpool_name,
    char *disk_name)
{
	/* target type */

	if (nvlist_add_uint32(target_attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_RPOOL) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (-1);
	}

	/* root pool name */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    rpool_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_RPOOL_NAME to"
		    "nvlist\n");

		return (-1);
	}

	/* device name */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_DEVICE,
	    disk_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_RPOOL_DEVICE "
		    "to nvlist\n");

		return (-1);
	}

	return (0);
}


/*
 * prepare_zfs_vol_target()
 */

static int
prepare_zfs_vol_target(nvlist_t *target_attrs, char *pool_name, char *vol_name,
    uint32_t vol_size, uint16_t vol_type)
{
	char		vol_num = 1;
	char		*vol_names[1];
	uint16_t	vol_types[1];
	uint32_t	vol_sizes[1];

	vol_names[0] = vol_name;
	vol_sizes[0] = vol_size;
	vol_types[0] = vol_type;

	/* target type */

	if (nvlist_add_uint32(target_attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_VOLUME) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (-1);
	}

	/* only one volume will be created */

	if (nvlist_add_uint16(target_attrs, TI_ATTR_ZFS_VOL_NUM, vol_num) !=
	    0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_VOL_NUM to"
		    "nvlist\n");

		return (-1);
	}

	/* pool name */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_VOL_POOL_NAME,
	    pool_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_VOL_POOL_NAME "
		    "to nvlist\n");

		return (-1);
	}

	/* ZFS volume names */

	if (nvlist_add_string_array(target_attrs, TI_ATTR_ZFS_VOL_NAMES,
	    vol_names, vol_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_VOL_NAMES to"
		    "nvlist\n");

		return (-1);
	}

	/* ZFS volume sizes */

	if (nvlist_add_uint32_array(target_attrs, TI_ATTR_ZFS_VOL_MB_SIZES,
	    vol_sizes, vol_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_VOL_MB_SIZES "
		    "to nvlist\n");

		return (-1);
	}

	/* ZFS volume types */

	if (nvlist_add_uint16_array(target_attrs, TI_ATTR_ZFS_VOL_TYPES,
	    vol_types, vol_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_VOL_TYPES "
		    "to nvlist\n");

		return (-1);
	}

	return (0);
}


/*
 * prepare_zfs_fs_target()
 */

static int
prepare_zfs_fs_target(nvlist_t *target_attrs, char *pool_name, char *fs_name)
{
	char		fs_num = 1;
	char		*fs_names[1];

	fs_names[0] = fs_name;

	/* target type */

	if (nvlist_add_uint32(target_attrs, TI_ATTR_TARGET_TYPE,
	    TI_TARGET_TYPE_ZFS_FS) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_TARGET_TYPE to"
		    "nvlist\n");

		return (-1);
	}

	/* only one filesystem will be created */

	if (nvlist_add_uint16(target_attrs, TI_ATTR_ZFS_FS_NUM, fs_num) !=
	    0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_FS_NUM to"
		    "nvlist\n");

		return (-1);
	}

	/* pool name */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_FS_POOL_NAME,
	    pool_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_FS_POOL_NAME "
		    "to nvlist\n");

		return (-1);
	}

	/* ZFS filesystem names */

	if (nvlist_add_string_array(target_attrs, TI_ATTR_ZFS_FS_NAMES,
	    fs_names, fs_num) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_FS_NAMES to"
		    "nvlist\n");

		return (-1);
	}

	return (0);
}


/*
 * main()
 */
int
main(int argc, char *argv[])
{
	int		opt;

	/* dryrun mode is the default */
	boolean_t	fl_dryrun = B_TRUE;

	/* create Solaris2 partition on whole disk */
	boolean_t	fl_wholedisk = B_FALSE;

	/* all available space is dedicated to one slice 0 */
	boolean_t	fl_vtoc_default = B_FALSE;

	nvlist_t	*target_attrs = NULL;
	uint16_t	slice_parts[TI_TST_SLICE_NUM] = {0, 1};
	uint16_t	slice_tags[TI_TST_SLICE_NUM] = {2, 3};
	uint16_t	slice_flags[TI_TST_SLICE_NUM] = {0, 1};
	uint64_t	slice_1stsecs[TI_TST_SLICE_NUM] = {0, 40000000};
	uint64_t	slice_sizes[TI_TST_SLICE_NUM] = {40000000, 4000000};
	char		*target_type = NULL;
	char		*disk_name = NULL;
	char		*config_file = NULL;

	char		zfs_device[100];
	char		*zfs_root_pool_name = NULL;
	char		*zfs_be_name = "myBE";
	char		zfs_fs_num = 3;
	char		zfs_shared_fs_num = 2;
	char		*zfs_fs_names[3] =
	    {"usr", "var", "opt"};
	char		*zfs_shared_fs_names[2] =
	    {"export", "export/home"};
	char		zfs_vol_num = 0;
	char		*zfs_vol_names[1] = {"swap"};
	uint32_t	zfs_vol_sizes[1] = {2048};
	uint32_t	zfs_vol_size = 2048;
	uint16_t	zfs_vol_type = 0;
	uint32_t	dc_ramdisk_size = 0;
	char		*dc_bootarch_name = NULL;
	char		*dc_dest_path = NULL;
	boolean_t	dc_ramdisk_release = B_FALSE;
	char		*dc_dir = NULL;

	char		*name_arg = NULL;

	/* init logging service */

	if (ls_init(NULL) != LS_E_SUCCESS) {
		(void) fprintf(stderr, "Couldn't initialize "
		    "logging service\n");

		exit(1);
	}

	/*
	 * x - set debug mode
	 * c - run in real mode. Target is modified
	 * t - target type
	 * d - target disk
	 * w - create Solaris2 partition on whole disk
	 * f - create fdisk partition table
	 * s - create default VTOC - swap on s1
	 *	and rest of available space on slice 0
	 * z - size in MB of zvol to be created
	 * u - zvol type
	 * m - ramdisk mountpoint
	 * b - boot archive file name
	 * n - BE name
	 */

	while ((opt = getopt(argc, argv, "x:b:d:f:m:n:p:Rr:t:z:u:hcws")) !=
	    EOF) {
		switch (opt) {

			case 'h':
				display_help();

				return (0);
			break;

			/* debug level */

			case 'x': {
				/*
				 * convert from  command line option
				 * to logsvc debug level
				 */

				ls_dbglvl_t dbg_lvl = atoi(optarg) + 1;

				ls_set_dbg_level(dbg_lvl);
			}
			break;

			case 'b':
				dc_bootarch_name = optarg;
			break;

			case 'c':
				fl_dryrun = B_FALSE;
			break;

			case 'd':
				disk_name = optarg;
			break;

			case 'f':
				config_file = optarg;
			break;

			case 'm':
				dc_dest_path = optarg;
			break;

			case 'p':
				zfs_root_pool_name = optarg;
			break;

			case 'R':
				dc_ramdisk_release = B_TRUE;
			break;

			case 'r':
				dc_ramdisk_size = atoi(optarg);
			break;

			case 's':
				fl_vtoc_default = B_TRUE;
			break;

			case 't':
				target_type = optarg;
			break;

			case 'w':
				fl_wholedisk = B_TRUE;
			break;

			case 'n':
				name_arg = optarg;
			break;

			case 'z':
				zfs_vol_size = atoi(optarg);
			break;

			case 'u':
				zfs_vol_type = atoi(optarg);
			break;
		}
	}

	/* Makes TI work in dry run mode. No changes done to the target */
	if (fl_dryrun) {
		printf("Test TI started in simulation mode...\n");

		ti_dryrun_mode();
	} else
		printf("Test TI started in real mode...\n");

	/* Create nvlist containing attributes describing the target */

	if (nvlist_alloc(&target_attrs, TI_TARGET_NVLIST_TYPE, 0) != 0) {
		(void) fprintf(stderr, "ERR: Couldn't create nvlist describing "
		    "the target\n");
		return (-1);
	}

	/* if target type specified, create particular target */

	if (target_type != NULL) {
		printf("Target type specified: ");

		switch (target_type[0]) {
		/* fdisk */
		case 'f': {
			printf("fdisk\n");

			if (disk_name == NULL) {
				(void) fprintf(stderr, "ERR: device name "
				    "has to be specifed - use '-d' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			/* set target type attribute */

			if (nvlist_add_uint32(target_attrs,
			    TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_FDISK) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_TARGET_TYPE to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_fdisk_target(target_attrs, disk_name,
			    config_file, fl_wholedisk) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of fdisk target failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "fdisk target prepared successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of fdisk target failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "fdisk target created successfully\n");
			}

			break;
		}
		case 'r': {
			printf("ramdisk\n");
			if (fl_dryrun)
				ti_dryrun_mode();
			if (dc_ramdisk_release)
				printf("  ramdisk release requested\n");

			/* set target type attribute */

			if (nvlist_add_uint32(target_attrs,
			    TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_DC_RAMDISK) !=
			    0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_TARGET_TYPE to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (dc_bootarch_name == NULL) {
				(void) fprintf(stderr, "ERR: missing boot "
				    "archive name (-b <boot archive name>)\n");
				nvlist_free(target_attrs);
				exit(1);
			}
			if (nvlist_add_string(target_attrs,
			    TI_ATTR_DC_RAMDISK_BOOTARCH_NAME,
			    dc_bootarch_name) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_DC_RAMDISK_BOOTARCH_NAME to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			if (dc_dest_path == NULL) {
				(void) fprintf(stderr, "ERR: missing ramdisk "
				    "mountpoint (-m <ramdisk mountpoint>)\n");
				nvlist_free(target_attrs);
				return (-1);
			}
			if (nvlist_add_string(target_attrs,
			    TI_ATTR_DC_RAMDISK_DEST, dc_dest_path) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_DC_RAMDISK_DEST to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			if (!dc_ramdisk_release && dc_ramdisk_size == 0) {
				(void) fprintf(stderr, "ERR: missing ramdisk "
				    "size (-r <size in Kbytes>)\n");
				nvlist_free(target_attrs);
				exit(1);
			}
			if (!dc_ramdisk_release &&
			    nvlist_add_uint16(target_attrs,
			    TI_ATTR_DC_RAMDISK_FS_TYPE,
			    TI_DC_RAMDISK_FS_TYPE_UFS) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_DC_RAMDISK_FS_TYPE to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			if (!dc_ramdisk_release &&
			    nvlist_add_uint32(target_attrs,
			    TI_ATTR_DC_RAMDISK_SIZE, dc_ramdisk_size) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_DC_RAMDISK_FS_TYPE to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			/* create target */

			if (dc_ramdisk_release) {
				if (ti_release_target(target_attrs) !=
				    TI_E_SUCCESS) {
					(void) fprintf(stderr,
					    "ERR: release of ramdisk target "
					    "failed\n");

					exit(1);
				} else {
					(void) fprintf(stdout,
					    "ramdisk target released - "
					    "success\n");
				}
			} else {
				if (ti_create_target(target_attrs, NULL) !=
				    TI_E_SUCCESS) {
					(void) fprintf(stderr,
					    "ERR: creating of ramdisk target "
					    "failed\n");

					exit(1);
				} else {
					(void) fprintf(stdout,
					    "ramdisk target created - "
					    "success\n");
				}
			}

			break;
		}
		case 'd': {
			printf("DC UFS (simple directory)\n");

			/* set target type attribute */

			if (nvlist_add_uint32(target_attrs,
			    TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_DC_UFS) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_TARGET_TYPE_DC_UFS to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			if (dc_dest_path == NULL) {
				(void) fprintf(stderr, "ERR: missing directory "
				    "pathname (-m <pathname>)\n");
				nvlist_free(target_attrs);
				exit(1);
			}
			if (nvlist_add_string(target_attrs,
			    TI_ATTR_DC_UFS_DEST, dc_dest_path) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_DC_RAMDISK_DEST to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}
			/* create target */
			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of directory failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "directory created - success\n");
			}
			break;
		}

		/* VTOC */
		case 'v': {
			printf("VTOC\n");

			if (disk_name == NULL) {
				(void) fprintf(stderr, "ERR: device name "
				    "has to be specifed - use '-d' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			/*
			 * if config_file was not specified, create
			 * VTOC with default layout
			 */

			if (config_file == NULL) {
				fl_vtoc_default = B_TRUE;

				printf("Config file not specified, default "
				    "VTOC will be created\n");
			}

			/* set target type attribute */

			if (nvlist_add_uint32(target_attrs,
			    TI_ATTR_TARGET_TYPE, TI_TARGET_TYPE_VTOC) != 0) {
				(void) fprintf(stderr, "ERR: Couldn't add "
				    "TI_ATTR_TARGET_TYPE to nvlist\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_vtoc_target(target_attrs, disk_name,
			    config_file, fl_vtoc_default) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of VTOC target failed\n");

				nvlist_free(target_attrs);
				exit(1);
			} else {
				(void) fprintf(stdout,
				    "VTOC target prepared successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of VTOC target failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "VTOC target created successfully\n");
			}
			break;
		}

		/* Snap Upgrade BE */
		case 'b': {
			printf("BE\n");

			/* root pool and be_name have to be specified */

			if (zfs_root_pool_name == NULL) {
				(void) fprintf(stderr, "ERR: root pool "
				    "has to be specifed - use '-p' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (name_arg == NULL) {
				(void) fprintf(stderr, "ERR: be name "
				    "has to be specifed - use '-n' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_be_target(target_attrs, zfs_root_pool_name,
			    name_arg) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of BE target failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "BE target prepared successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of BE target failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "BE target created successfully\n");
			}

			break;
		}

		/* ZFS root pool */
		case 'p': {
			printf("ZFS root pool\n");

			/* root pool name and device have to be specified */

			if (zfs_root_pool_name == NULL) {
				(void) fprintf(stderr, "ERR: root pool "
				    "has to be specifed - use '-p' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (disk_name == NULL) {
				(void) fprintf(stderr, "ERR: device name "
				    "has to be specifed - use '-d' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_zfs_rpool_target(target_attrs,
			    zfs_root_pool_name, disk_name) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of ZFS root pool target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS root pool target prepared "
				    "successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of ZFS root pool target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS root pool target created "
				    "successfully\n");
			}

			break;
		}

		/* ZFS filesystem */
		case 'm': {
			printf("ZFS filesystem\n");

			/*
			 * pool name, volume name and size have to be specified
			 */

			if (zfs_root_pool_name == NULL) {
				(void) fprintf(stderr, "ERR: root pool "
				    "has to be specifed - use '-p' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (name_arg == NULL) {
				(void) fprintf(stderr, "ZFS filesystem name "
				    "has to be specifed - use '-n' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_zfs_fs_target(target_attrs,
			    zfs_root_pool_name, name_arg) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of ZFS filesystem target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS filesystem target prepared "
				    "successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of ZFS filesystem target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS filesystem target created "
				    "successfully\n");
			}
			break;
		}

		/* ZFS volume */
		case 'l': {
			printf("ZFS volume\n");

			/*
			 * pool name, volume name and size have to be specified
			 */

			if (zfs_root_pool_name == NULL) {
				(void) fprintf(stderr, "ERR: root pool "
				    "has to be specifed - use '-p' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (name_arg == NULL) {
				(void) fprintf(stderr, "ZFS volume name "
				    "has to be specifed - use '-n' option\n");

				nvlist_free(target_attrs);
				exit(1);
			}

			if (prepare_zfs_vol_target(target_attrs,
			    zfs_root_pool_name, name_arg, zfs_vol_size,
			    zfs_vol_type) != 0) {
				(void) fprintf(stderr,
				    "ERR: preparing of ZFS volume target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS volume target prepared "
				    "successfully\n");
			}

			/* create target */

			if (ti_create_target(target_attrs, NULL) !=
			    TI_E_SUCCESS) {
				(void) fprintf(stderr,
				    "ERR: creating of ZFS volume target "
				    "failed\n");

				exit(1);
			} else {
				(void) fprintf(stdout,
				    "ZFS volume target created "
				    "successfully\n");
			}
			break;
		}

		/* UNKNOWN */
		default:
			printf("UNKNOWN\n");
		break;
		}

		nvlist_free(target_attrs);

		exit(0);
	}

	if (disk_name != NULL) {
		/* FDISK */
		if (prepare_fdisk_target(target_attrs, disk_name,
		    config_file, fl_wholedisk) != 0)
			(void) fprintf(stderr,
			    "ERR: preparing of fdisk target failed\n");
		else
			(void) fprintf(stdout,
			    "fdisk target prepared - success\n");

		/* VTOC */

		if (fl_vtoc_default) {
			if (nvlist_add_boolean_value(target_attrs,
			    TI_ATTR_SLICE_DEFAULT_LAYOUT, B_TRUE) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_DEFAULT_LAYOUT"
				    " to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}
		} else {
			if (nvlist_add_uint16(target_attrs, TI_ATTR_SLICE_NUM,
			    TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_NUM to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_PARTS,
			    slice_parts, TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_PARTS to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_TAGS,
			    slice_tags, TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_TAGS to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_FLAGS,
			    slice_flags, TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_FLAGS to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint64_array(target_attrs,
			    TI_ATTR_SLICE_1STSECS,
			    slice_1stsecs, TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_1STSECS to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint64_array(target_attrs,
			    TI_ATTR_SLICE_SIZES,
			    slice_sizes, TI_TST_SLICE_NUM) != 0) {
				(void) fprintf(stderr, "Couldn't add "
				    "TI_ATTR_SLICE_SIZES to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}
		}

		/*
		 * slice for holding root pool - slice name is created from disk
		 * name. Slice 0 is considered to be the one for ZFS root pool.
		 */

		(void) snprintf(zfs_device, sizeof (zfs_device), "%ss0",
		    disk_name);

		if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_DEVICE,
		    zfs_device) != 0) {
			(void) fprintf(stderr, "Couldn't add "
			    "TI_ATTR_ZFS_RPOOL_DEVICE to nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}
	}

	/* ZFS root pool */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    zfs_root_pool_name) != 0) {
		(void) fprintf(stderr, "Couldn't add TI_ATTR_ZFS_RPOOL_NAME "
		    "to nvlist\n");

		nvlist_free(target_attrs);
		return (0);
	}

	/* ZFS file systems */

	if (nvlist_add_uint16(target_attrs, TI_ATTR_ZFS_FS_NUM, zfs_fs_num)
	    != 0) {
		printf("Couldn't add TI_ATTR_ZFS_FS_NUM to nvlist\n");

		nvlist_free(target_attrs);
		return (0);
	}

	if (nvlist_add_string_array(target_attrs, TI_ATTR_ZFS_FS_NAMES,
	    zfs_fs_names, zfs_fs_num) != 0) {
		printf("Couldn't add TI_ATTR_ZFS_FS_NAMES to nvlist\n");

		nvlist_free(target_attrs);
		return (0);
	}

	/* ZFS volumes */

	if (zfs_vol_num != 0) {
		if (nvlist_add_uint16(target_attrs, TI_ATTR_ZFS_VOL_NUM,
		    zfs_vol_num) != 0) {
			printf("Couldn't add TI_ATTR_ZFS_VOL_NUM to nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}

		if (nvlist_add_string_array(target_attrs, TI_ATTR_ZFS_VOL_NAMES,
		    zfs_vol_names, zfs_vol_num) != 0) {
			printf("Couldn't add TI_ATTR_ZFS_VOL_NAMES to "
			    "nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}

		if (nvlist_add_uint32_array(target_attrs,
		    TI_ATTR_ZFS_VOL_MB_SIZES, zfs_vol_sizes, zfs_vol_num)
		    != 0) {
			printf("Couldn't add TI_ATTR_ZFS_VOL_MB_SIZES to "
			    "nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}
	}

	/* call TI for creating the target */

	ti_create_target(target_attrs, ti_cb);

	nvlist_free(target_attrs);

	return (0);
}
