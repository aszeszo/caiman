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

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libnvpair.h>
#include <sys/param.h>
#include <sys/types.h>

#include "orchestrator_private.h"
#include "test.h"
#include "transfermod.h"

static	boolean_t	discovery_done = B_FALSE;

om_handle_t	handle;
void update_progress(om_callback_info_t *cb_data,
		    uintptr_t app_data);
void idm_dryrun_mode(void);

void
update_progress(om_callback_info_t *cb_data, uintptr_t app_data)
{
	(void) printf("update_progress is called\n");
	(void) printf("Milestone = %d, ", cb_data->curr_milestone);
	(void) printf("percent_done = %d\n", cb_data->percentage_done);
	if (cb_data->curr_milestone == OM_UPGRADE_TARGET_DISCOVERY &&
	    cb_data->percentage_done == 100) {
		discovery_done = B_TRUE;
	}
}

void
print_disk_info(disk_info_t *dt)
{
	char	vendor[8];

	(void) printf("Name\tSize\tType\tVendor\tBoot?\t");
	(void) printf("Label\tRemovable\tSerial\n");
	while (dt != NULL) {
		if (dt->vendor == NULL) {
			(void) strlcpy(vendor, OM_UNKNOWN_STRING, 7);
		} else {
			(void) strlcpy(vendor, dt->vendor, 7);
		}

		(void) printf("%s\t%d\t%d\t%s\t%s\t%d\t%s\t\t%s\n",
		    dt->disk_name,
		    dt->disk_size,
		    dt->disk_type,
		    vendor,
		    (dt->boot_disk)?"True":"False",
		    dt->label,
		    (dt->removable)?"True":"False",
		    (dt->serial_number == NULL)? OM_UNKNOWN_STRING
			:dt->serial_number);
		dt = dt->next;
	}
}

void
print_disk_info_array(disk_info_t **da, int total)
{
	int i;
	disk_info_t	*dt;
	char	vendor[8];

	(void) printf("Name\tSize\tType\tVendor\tBoot?\t");
	(void) printf("Label\tRemovable\tSerial\n");
	for (i = 0; i < total; i++, da++) {
		dt = (disk_info_t *)*da;
		if (dt == NULL) {
			continue;
		}
		if (dt->vendor == NULL) {
			(void) strlcpy(vendor, OM_UNKNOWN_STRING, 7);
		} else {
			(void) strlcpy(vendor, dt->vendor, 7);
		}

		(void) printf("%s\t%d\t%d\t%s\t%s\t%d\t%s\t\t%s\n",
		    dt->disk_name,
		    dt->disk_size,
		    dt->disk_type,
		    vendor,
		    (dt->boot_disk)?"True":"False",
		    dt->label,
		    (dt->removable)?"True":"False",
		    (dt->serial_number == NULL)? OM_UNKNOWN_STRING
			: dt->serial_number);
	}
}

void
print_partition_info(disk_parts_t *dp)
{
	int	j;

	if (dp == NULL) {
		printf("No partition info (NULL)\n");
		return;
	}
	if (dp->disk_name) {
		(void) printf("Disk = %s\n", dp->disk_name);
	}
	(void) printf("Id\tOrder\tType\tContent\tSize\toffset\tActive\n");
	for (j = 0; j < FD_NUMPART; j++) {
		if (dp->pinfo[j].partition_id == 0) {
			continue;
		}
		(void) printf("%d\t%d\t%d\t%d\t%u\t%u\t%s\t%lld\t%lld\n",
		    dp->pinfo[j].partition_id,
		    dp->pinfo[j].partition_order,
		    dp->pinfo[j].partition_type,
		    dp->pinfo[j].content_type,
		    dp->pinfo[j].partition_size,
		    dp->pinfo[j].partition_offset,
		    (dp->pinfo[j].active)?"True":"False",
		    dp->pinfo[j].partition_size_sec,
		    dp->pinfo[j].partition_offset_sec);
	}
}

void
print_slices_info(disk_slices_t *ds)
{
	int	j;

	if (ds->disk_name) {
		(void) printf("Disk = %s\n", ds->disk_name);
	}
	(void) printf("Partition = %d\n", ds->partition_id);

	(void) printf("Id\tSize\toffset\ttags\tflags\n");
	for (j = 0; j < NDKMAP; j++) {
		if (ds->sinfo[j].slice_size == 0) {
			continue;
		}
		(void) printf("%d\t%d\t%d\t%d\t%d\n",
		    ds->sinfo[j].slice_id,
		    ds->sinfo[j].slice_size,
		    ds->sinfo[j].slice_offset,
		    ds->sinfo[j].tag,
		    ds->sinfo[j].flags);
	}
}

void
print_upgrade_targets(upgrade_info_t *instances)
{
	upgrade_info_t *ui;

	ui = instances;
	(void) printf("Disk Name\tslice\tVersion\tsvm?\tNGZ?\tUpgradable?\n");
	for (ui = instances; ui != NULL; ui = ui->next) {
		(void) printf("%s\t%d\t%s\t%s\t%s\t%s\n",
		    ui->instance.uinfo.disk_name,
		    ui->instance.uinfo.slice,
		    ui->solaris_release,
		    (ui->instance.uinfo.svm_configured)?"True":"False",
		    (ui->zones_installed)?"True":"False",
		    (ui->upgradable)?"True":"False");
		if (ui->instance.uinfo.svm_configured &&
		    ui->instance.uinfo.svm_info) {
			(void) printf("SVM Info = %s\n",
			    ui->instance.uinfo.svm_info);
		}
		if (ui->zones_installed && ui->incorrect_zone_list) {
			(void) printf("Bad non-global zones = %s\n",
			    ui->incorrect_zone_list);
		}
		if (!ui->upgradable) {
			(void) printf("Upgrade is not allowed because of %d\n",
			    ui->upgrade_message_id);
		}
	}
}

disk_info_t *
test_disk_info(om_handle_t handle)
{
	disk_info_t	*disks, *dt;
	disk_info_t	**di_array;
	int		total;

	(void) printf("--------------Testing om_get_disk_info--------------\n\n");
	disks = om_get_disk_info(handle, &total);

	if (disks == NULL) {
		(void) printf("No Disks found...\n");
		exit(2);
	}

	if (total == 0) {
		(void) printf("No Disks found...\n");
		exit(3);
	}
	(void) printf("Number of disks = %d\n", total);
	print_disk_info(disks);
	(void) printf("--------------Testing om_duplicate_disk_info------------\n\n");

	dt = om_duplicate_disk_info(handle, disks);

	if (dt == NULL) {
		(void) printf("om_duplicate_disk_info failed...\n");
		return (disks);
	}
	print_disk_info(dt);

	/*
	 * Free the duplicated disk_info_t
	 */
	(void) om_free_disk_info(handle, dt);

	(void) printf("------Testing om_convert_linked_disk_info_to_array------\n\n");
	di_array = om_convert_linked_disk_info_to_array(handle, disks, total);
	if (di_array == NULL) {
		(void) printf(" om_convert_linked_disk_info_to_array failed...\n");
		return (disks);
	}
	print_disk_info_array(di_array, total);

	/*
	 * Free the allocated array
	 */
	(void) om_free_disk_info_array(handle, di_array);
	return (disks);
}

void
test_disk_partition_info(om_handle_t handle, disk_info_t *disks)
{
	disk_info_t	*dt;
	int		j;

	if (disks == NULL) {
		(void) printf("Partition Info: No Disks");
		return;
	}

	(void) printf("\nFdisk Partition Information\n");
	(void) printf("---------------------------\n\n");
	for (dt = disks; dt != NULL; dt = dt->next) {
		disk_parts_t	*dp, *dp1;

		(void) printf("------Testing om_get_disk_partition_info------\n\n");
		dp = om_get_disk_partition_info(handle, dt->disk_name);
		if (dp == NULL) {
			printf("No partitions found.  Initializing new partition table.\n");
			dp = om_init_disk_partition_info(dt->disk_name);
			(void) printf("Error = %d\n", om_get_error());
			continue;
		}
		print_partition_info(dp);

		(void) printf("----Testing om_duplicate_disk_partition_info----\n\n");
		dp1 = om_duplicate_disk_partition_info(handle, dp);
		print_partition_info(dp1);

		/*
		 * Free the disk partitions
		 */
		om_free_disk_partition_info(handle, dp1);
		/*
		 * Assign the whold disk to one solaris part
		 */
		for (j = 0; j < FD_NUMPART; j++) {
			dp->pinfo[j].partition_size = 0;
		}

		dp->pinfo[0].partition_offset = 0;
		dp->pinfo[0].partition_size = dt->disk_size;
		dp->pinfo[0].partition_type = SUNIXOS2;
		dp->pinfo[1].partition_offset = 0;
		dp->pinfo[1].partition_size = 0;

		/*
		 * Test om_is_disk_partition_valid
		 */
		dp1 = om_validate_and_resize_disk_partitions(handle, dp);
		if (dp1 == NULL) {
			(void) printf("Disk Parts not valid for disk = %s \
			    with size = %d\n",
			    dt->disk_name, dt->disk_size);
		} else {
			(void) printf("Disk Parts valid for disk = %s \
			    with size = %d\n",
			    dt->disk_name, dt->disk_size);
			(void) printf("part_size = %u\n",
			    dp1->pinfo[0].partition_size);
		}

		(void) om_set_disk_partition_info(handle, dp1);
		(void) om_free_disk_partition_info(handle, dp1);
		(void) om_free_disk_partition_info(handle, dp);
	}
}

/*
 * read commands from configuration file
 * Commands:
 * device <disk name> - basename only - cxtxdx or cxdx
 * create partition <offset in sectors> <size in sectors> (if size is 0, use whole disk)
 * create slice <offset in sectors> <size in sectors> <slice number>
 * delete partition <slice number>
 * delete slice <slice number>
 * preserve slice <slice number>
 * write partition - write partition table using fdisk(1m)
 * write slice - write vtoc using write_vtoc(3ext)
 *
 * If "write slice" is issued without creating slices, entire partition will go to slice 0
 *
 * Procedure:
 * first issue "disk"
 * then issue series of "create"/"delete" "partition"/"slice"
 * finally issue "write partition"/"slice"
 */
void
fdisk_vtoc_config(om_handle_t handle, disk_info_t *disks)
{
	FILE *fp = NULL;
	char lin[1024];
	int ac;
	char cmd[132];
	char obj[132];
	char disk_name[132];
	uint64_t offset, size, p3;
	boolean_t success;

	assert(fdisk_vtoc_conf != NULL);

	if ((fp = fopen(fdisk_vtoc_conf, "r")) == NULL) {
		printf("can't open %s\n", fdisk_vtoc_conf);
		exit(1);
	}
	ls_init(NULL);
#if 0
	idm_dryrun_mode();
#endif
	while (fgets(lin, sizeof (lin), fp) != NULL) {
		if (lin[0] == '#')
			continue;
		ac = sscanf(lin, "%s %s %lld %lld %lld \n", &cmd, &obj, &offset, &size, &p3);
		if (ac <= 0)
			continue;
		printf("configuration: %s", lin);
		if (strcmp(cmd, "device") == 0) {
			disk_info_t *di;
			disk_parts_t *dp;
			disk_slices_t *ds;

			for (di = disks; di != NULL; di = di->next) {
				if (strcmp(di->disk_name, disk_name) != 0)
					break;
			}
			if (di == NULL) {
				printf("disk not found\n");
				exit(1);
			}
			strcpy(disk_name, obj);
			dp = om_get_disk_partition_info(handle, disk_name);
			if (dp == NULL) {
				printf("get part infor returned NULL\n");
				dp = om_init_disk_partition_info(disk_name);
				if (dp == NULL) {
					printf("init part infor returned NULL\n");
					exit(1);
				}
			}
			om_set_disk_partition_info(handle, dp);
			ds = om_get_slice_info(handle, disk_name);
			if (ds == NULL) {
				printf("couldn't get disk slice info\n");
				ds = om_init_slice_info(disk_name);
				if (ds == NULL) {
					printf("couldn't init disk slice info\n");
					exit(1);
				}
			}
			om_set_slice_info(handle, ds);
			continue;
		}
		if (strcmp(cmd, "create") == 0) {
			if (strcmp(obj, "partition") == 0) {
				if (size == 0) {
					success = om_create_partition(0, 0, B_TRUE);
					printf("create partition for entire disk returned %d\n", success);
				} else {
					success = om_create_partition(offset, size, B_FALSE);
					printf("create partition at sector %lld returned %d\n", offset, success);
				}
				continue;
			}
			if (strcmp(obj, "slice") == 0) {
				success = om_create_slice((uint8_t) p3,
					size, B_TRUE);
				printf("create slice returned %d\n", success);
				continue;
			}
			printf("unrecognized object\n");
		}
		if (strcmp(cmd, "delete") == 0) {
			if (strcmp(obj, "partition") == 0) {
				success = om_delete_partition(offset, size);
				printf("delete partition table returned %d\n", success);
				continue;
			}
			if (strcmp(obj, "slice") == 0) {
				success = om_delete_slice((uint8_t) p3);
				printf("delete slice %d returned %d\n", (int) p3, success);
				continue;
			}
			printf("unrecognized object\n");
		}
		if (strcmp(cmd, "preserve") == 0) {
			if (strcmp(obj, "slice") == 0) {
				success = om_preserve_slice((uint8_t) p3);
				printf("preserve slice returned %d\n", success);
				continue;
			}
			printf("unrecognized object\n");
		}
		if (strcmp(cmd, "write") == 0) {
			if (strcmp(obj, "partition") == 0) {
				success = om_write_partition_table();
				printf("write partition table returned %d\n", success);
				continue;
			}
			if (strcmp(obj, "slice") == 0) {
				success = om_write_vtoc();
				printf("write vtoc returned %d\n", success);
				continue;
			}
			printf("unrecognized object\n");
			continue;
		}
		printf("unrecognized command\n");
	}
}

void
test_disk_slices_info(om_handle_t handle, disk_info_t *disks)
{
	disk_info_t	*dt;

	if (disks == NULL) {
		(void) printf("Slices Info: No Disks");
		return;
	}

	(void) printf("\nVTOC Partition Information\n");
	(void) printf("---------------------------\n\n");
	for (dt = disks; dt != NULL; dt = dt->next) {
		disk_slices_t	*ds, *ds1;

		(void) printf("------Testing om_get_slice_info------\n\n");
		ds = om_get_slice_info(handle, dt->disk_name);
		if (ds == NULL) {
			(void) printf("Disk = %s\n", dt->disk_name);
			(void) printf("Error = %d\n", om_get_error());
			continue;
		}
		print_slices_info(ds);

		(void) printf("------Testing om_duplicate_slice_info------\n\n");
		ds1 = om_duplicate_slice_info(handle, ds);
		print_slices_info(ds1);

		/*
		 * Free the disk slices
		 */
		(void) om_free_disk_slice_info(handle, ds1);
		(void) om_free_disk_slice_info(handle, ds);
	}
}

upgrade_info_t *
test_upgrade_targets(om_handle_t handle)
{
	upgrade_info_t	*instances, *ut;
	uint16_t		found;

	found = 0;
	(void) printf("------------Testing om_get_upgrade_targets------------\n\n");
	instances = om_get_upgrade_targets(handle, &found);

	if (found <= 0 || instances == NULL) {
		(void) printf("No Solaris Instances found\n");
		return (NULL);
	}

	(void) printf("Number of Instances = %d\n", found);
	print_upgrade_targets(instances);

	for (ut = instances; ut != NULL; ut = ut->next) {
		(void) om_is_upgrade_target_valid(handle, ut, update_progress);
		(void) printf("Sleep for 5 minutes to complete callbacks\n");
		(void) sleep(300);
	}
	return (instances);
}

void
test_perform_initial_install(disk_info_t *disks)
{
	disk_info_t	*dt;
	nvlist_t	*install_attr;
	char		*timezone = "America/Los_Angeles";
	char		*default_locale = "en_US";
	char		*locales = "en zh zh_TW";
	char		*root_pw = "MWrmkOemPiH56";
	char		*user_pw = "UW45fb?324";
	char		*user_name = "test_user";
	char		*login_name = "test";

	if (disks == NULL) {
		(void) printf("test_perform_initial_install: No Disks");
		return;
	}

	if (nvlist_alloc(&install_attr, NV_UNIQUE_NAME, 0) != 0) {
		(void) printf("Can't allocate nvlist for install\n");
		return;
	}

	/*
	 * If we are testing and notinstalling, set OM_ATTR_INSTALL_TEST
	 * to B_TRUE. This can be used for GUI testing
	 */
	if (nvlist_add_boolean_value(install_attr,
	    OM_ATTR_INSTALL_TEST, B_TRUE) != 0) {
		(void) printf("Can't add INSTALL_TEST to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	/*
	 * Setup nvlist for install
	 */
	if (nvlist_add_uint8(install_attr, OM_ATTR_INSTALL_TYPE,
	    OM_INITIAL_INSTALL) != 0) {
		(void) printf("Can't add install_type to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_TIMEZONE_INFO,
	    timezone) != 0) {
		(void) printf("Can't add timezone to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DEFAULT_LOCALE,
	    default_locale) != 0) {
		(void) printf("Can't add default_locale to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_LOCALES_LIST,
	    locales) != 0) {
		(void) printf("Can't add locales to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_ROOT_PASSWORD,
	    root_pw) != 0) {
		(void) printf("Can't add root password to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_NAME,
	    user_name) != 0) {
		(void) printf("Can't add user_name to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_LOGIN_NAME,
	    login_name) != 0) {
		(void) printf("Can't add user_name to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_USER_PASSWORD,
	    user_pw) != 0) {
		(void) printf("Can't add user_name to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	if (nvlist_add_string(install_attr, OM_ATTR_DEFAULT_LOCALE,
	    default_locale) != 0) {
		(void) printf("Can't add user password to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	for (dt = disks; dt != NULL; dt = dt->next) {
		if (nvlist_add_string(install_attr, OM_ATTR_DISK_NAME,
		    dt->disk_name) != 0) {
			(void) printf("Can't add diskname to nvlist for install\n");
			nvlist_free(install_attr);
			return;
		}
/*
		if (om_perform_install(install_attr, update_progress) < 0) {
			(void) printf("om_perform_install failed. Error = %d\n",
			    om_get_error());
		}
*/
	}
}

void
test_perform_upgrade(upgrade_info_t *instances)
{
	upgrade_info_t	*ut;
	nvlist_t	*install_attr;
	char		buf[MAXNAMELEN];

	if (instances == NULL) {
		(void) printf("test_perform_upgrade: No instances");
		return;
	}

	if (nvlist_alloc(&install_attr, NV_UNIQUE_NAME, 0) != 0) {
		(void) printf("Can't allocate nvlist for install\n");
		return;
	}

	/*
	 * If we are testing and notinstalling, set OM_ATTR_INSTALL_TEST
	 * to B_TRUE. This can be used for GUI testing
	 */
	if (nvlist_add_boolean_value(install_attr,
	    OM_ATTR_INSTALL_TEST, B_TRUE) != 0) {
		(void) printf("Can't add INSTALL_TEST to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	/*
	 * Setup nvlist for install
	 */
	if (nvlist_add_uint8(install_attr, OM_ATTR_INSTALL_TYPE,
	    OM_UPGRADE) != 0) {
		(void) printf("Can't add install_type to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}

	/*
	 * Try upgrading only the first instance
	 */
	ut = instances;
	(void) snprintf(buf, sizeof (buf), "%ss%d",
	    ut->instance.uinfo.disk_name, ut->instance.uinfo.slice);

	if (nvlist_add_string(install_attr, OM_ATTR_UPGRADE_TARGET,
	    buf) != 0) {
		(void) printf("Can't add diskname to nvlist for install\n");
		nvlist_free(install_attr);
		return;
	}
/*
	if (om_perform_install(install_attr, update_progress) < 0) {
		(void) printf("om_perform_install failed. Error = %d\n",
		    om_get_error());
	}
*/
}

upgrade_info_t *
cookup_one_instance()
{
	upgrade_info_t  *si;

	si = (upgrade_info_t *)calloc(1, sizeof (upgrade_info_t));
	if (si == NULL) {
		(void) om_set_error(OM_NO_SPACE);
		return (NULL);
	}
	/*
	 * setup the new upgrade target by copied values from the
	 * instance passed as an input parameter
	 */
	si->solaris_release = strdup("Solaris 11");
	si->zones_installed = B_FALSE;
	si->upgradable = B_FALSE;
	si->upgrade_message_id = 3001;
	/*
	 * Currently assuming that it is UFS
	 */
	si->instance_type = OM_INSTANCE_UFS;
	if (si->instance_type == OM_INSTANCE_UFS) {
		si->instance.uinfo.disk_name = strdup("c1t0d0");
		si->instance.uinfo.slice = 0;
		si->instance.uinfo.svm_configured = B_FALSE;
	}
	si->next = NULL;
	return (si);
}

void
test_perform_slim_install(disk_info_t *disks)
{
	nvlist_t	*slim_attrs;
	disk_info_t	*dt = disks;

	fprintf(stderr, "Performing slim install\n");
	
	if (disks == NULL) {
		printf("No disks to perform slim install\n");
		return;
	}
	if (nvlist_alloc(&slim_attrs, NV_UNIQUE_NAME, 0) != 0) {
		fprintf(stderr, "Can't allocate nvlist for slim install\n");
		return;
	}

	/*
	 * Use first disk found(for now).
	 */
	dt = dt->next;

	if (nvlist_add_string(slim_attrs, OM_ATTR_DISK_NAME, 
	    dt->disk_name) != 0) {
		fprintf(stderr, "Can't add disk name to slim install nvlist.\n");
		nvlist_free(slim_attrs);
		return;
	}

	if (om_perform_install(slim_attrs, update_progress) < 0) {
		fprintf(stderr, "om_perform_install_failed. Error = %d\n", 
		    om_get_error);
	}
	return;
}

int
om_test_target_discovery(int arg)
{
	disk_info_t	*disks;
	upgrade_info_t	*instances = NULL;

	/*
	 * Initiate Target Discovery
	 */
	handle = om_initiate_target_discovery(update_progress);
	if (handle < 0) {
		(void) printf("Cannot start target discovery...\n");
		return (1);
	}

	while (discovery_done == B_FALSE) {
		sleep(10);
	}

	if (arg & DISK_INFO) {
		disks = test_disk_info(handle);
	}

	if (arg & PART_INFO) {
		test_disk_partition_info(handle, disks);
	}

	if (arg & SLICE_INFO) {
		test_disk_slices_info(handle, disks);
	}

	if (arg & FDISK_VTOC_TEST) {
		fdisk_vtoc_config(handle, disks);
	}

	if (arg & UPGRADE_TARGET_INFO) {
		instances = test_upgrade_targets(handle);
	}

	if (arg & DO_INSTALL) {
		test_perform_initial_install(disks);
		(void) printf("Sleeping for 20 minutes to complete callbacks\n");
		(void) sleep(1200);
	}
	if (arg & DO_SLIM_INSTALL) {
		test_perform_slim_install(disks);
		return (0);
	}
		
	if (arg & DO_UPGRADE) {
		if (instances == NULL) {
			instances = cookup_one_instance();
		}
		test_perform_upgrade(instances);
		(void) printf("Sleeping for 20 minutes to complete callbacks\n");
		(void) sleep(1200);
	}
}
