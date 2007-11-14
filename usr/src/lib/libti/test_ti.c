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

#pragma ident	"@(#)test_ti.c	1.3	07/10/23 SMI"

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
	(void) printf("usage: test_ti [-h] [-w] [-s] [-f] [-x level] "
	    "[-d disk_name] [-p pool_name] [-z zvol_size_mb]\n");
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
	char		*disk_name = NULL;

	char		zfs_device[100];
	char		*zfs_root_pool_name = "root_pool";
	char		zfs_fs_num = 6;
	char		*zfs_fs_names[6] =
	    {"root", "usr", "var", "opt", "export", "export/home"};

	char		zfs_vol_num = 0;
	char		*zfs_vol_names[1] = {"swap"};
	uint32_t	zfs_vol_sizes[1] = {2048};

	/* init logging/debugging service */

	ls_init_log();
	ls_init_dbg();

	/*
	 * d - target disk
	 * f - run in real mode. Target is modified
	 * x - set debug mode
	 * w - create Solaris2 partition on whole disk
	 * s - occupy all available space with slice 0
	 * z - size in MB of zvol to be created
	 */

	/* -p is not supported for Sparc */


	while ((opt = getopt(argc, argv, "x:d:p:z:hfws")) != EOF) {
		switch (opt) {

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

			case 'h':
				display_help();

				return (0);
			break;

			case 'd':
				disk_name = optarg;
			break;

			case 'f':
				fl_dryrun = B_FALSE;
			break;

			case 'w':
				fl_wholedisk = B_TRUE;
			break;

			case 's':
				fl_vtoc_default = B_TRUE;
			break;

			case 'p':
				zfs_root_pool_name = optarg;
			break;

			case 'z':
				zfs_vol_sizes[0] = atoi(optarg);

				zfs_vol_num = 1;
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
		printf("Couldn't create nvlist describing the target\n");

		return (0);
	}

	/* add atributes requiring creating Solaris2 partition on whole disk */
	if (fl_wholedisk && disk_name != NULL) {
		if (nvlist_add_boolean_value(target_attrs,
		    TI_ATTR_FDISK_WDISK_FL, B_TRUE) != 0) {
			printf("Couldn't add TI_ATTR_FDISK_WDISK_FL "
			    "to nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}
	}

	if (disk_name != NULL) {
		if (nvlist_add_string(target_attrs, TI_ATTR_FDISK_DISK_NAME,
		    disk_name) != 0) {
			printf("Couldn't add TI_ATTR_FDISK_DISK_NAME to "
			    "nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}

		/* VTOC */

		if (fl_vtoc_default) {
			if (nvlist_add_boolean_value(target_attrs,
			    TI_ATTR_SLICE_DEFAULT_LAYOUT, B_TRUE) != 0) {
				printf("Couldn't add "
				    "TI_ATTR_SLICE_DEFAULT_LAYOUT"
				    " to nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}
		} else {
			if (nvlist_add_uint16(target_attrs, TI_ATTR_SLICE_NUM,
			    TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_NUM to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_PARTS,
			    slice_parts, TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_PARTS to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_TAGS,
			    slice_tags, TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_TAGS to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint16_array(target_attrs,
			    TI_ATTR_SLICE_FLAGS,
			    slice_flags, TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_FLAGS to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint64_array(target_attrs,
			    TI_ATTR_SLICE_1STSECS,
			    slice_1stsecs, TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_1STSECS to "
				    "nvlist\n");

				nvlist_free(target_attrs);
				return (0);
			}

			if (nvlist_add_uint64_array(target_attrs,
			    TI_ATTR_SLICE_SIZES,
			    slice_sizes, TI_TST_SLICE_NUM) != 0) {
				printf("Couldn't add TI_ATTR_SLICE_SIZES to "
				    "nvlist\n");

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
			printf("Couldn't add TI_ATTR_ZFS_RPOOL_DEVICE to "
			    "nvlist\n");

			nvlist_free(target_attrs);
			return (0);
		}
	}

	/* ZFS root pool */

	if (nvlist_add_string(target_attrs, TI_ATTR_ZFS_RPOOL_NAME,
	    zfs_root_pool_name) != 0) {
		printf("Couldn't add TI_ATTR_ZFS_RPOOL_NAME to nvlist\n");

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
		printf("Couldn't add TI_ATTR_ZFS_FS_NUM to nvlist\n");

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
