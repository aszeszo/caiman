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

#pragma ident	"@(#)app_mirror_methods.c	1.10	07/10/09 SMI"


/*
 * Module:	app_mirror_methods.c
 * Group:	libspmiapp
 * Description:
 */
#include <stdlib.h>
#include <string.h>
#include <sys/fs/ufs_fs.h>
#include "spmiapp_lib.h"
#include "spmistore_api.h"
#include "spmicommon_api.h"
#include "spmisvc_api.h"
#include "spmisvc_lib.h"
#include "app_strings.h"

/*
 * private prototypes
 */

static int	_assign_volume_names(char *, int, char *, char *, char *);
static	int	_can_use_volume_name(char *, char *);


static	Storage	*file_system_list = NULL;

/*
 * Function:	svm_create_mirror_script
 * Description: Create a shell script that uses svm meta commands to create
 *		disk mirrors based on user specification from the jumpstart
 *		profile
 * Scope:	public
 * Parameters:	prop	 - pointer to profile structure
 * Return:	D_OK	 - configuration successful
 *		D_BADARG - invalid argument
 *		D_FAILED - internal failure
 *
 * The sequence of commands to create mirror devices are as follows.
 * After setting up the disks,
 * Call devfsadm to created SVM pseudo device 'md'
 * Call metadb to create metadb as specified by the profile
 * Call metainit to create submirrors(2)
 * Call metainit to create the mirror 
 * Call devfsadm to created SVM pseudo device 'md' in alternate root (/a)
 * If root(/) is a mirror device, call metaroot to set the mirror volume as the
 * 		bootable device (/etc/vfstab)
 */

int
svm_create_mirror_script(Profile *prop)
{
	MDBStorage	*mdb;
	Storage		*fsf;
	int		status = D_OK;
	int		current = 0;
	char		mirror[MAX_SVM_MIRROR_NAMELEN];
	char		root_mirror[MAX_SVM_MIRROR_NAMELEN];
	char		submirror1[MAX_SVM_MIRROR_NAMELEN];
	char		submirror2[MAX_SVM_MIRROR_NAMELEN];
	FILE		*fp;
	char		*new = "/tmp/root/etc/lvm/md.cf.new";
	char		*original = "/tmp/root/etc/lvm/md.cf";
	char		file1[MAXPATHLEN];
	char		file2[MAXPATHLEN];
	char		buf[MAXPATHLEN];
	char		volume_names[MAXPATHLEN];
	int		mirror_setup = FALSE;


	/* validate arguments */
	if (prop == NULL) {
		write_notice(ERRMSG,
			"(svm_create_mirror_script) %s",
			library_error_msg(D_BADARG));
		return (D_BADARG);
	}

	/*
	 * If metadb keyword is not specified in the profile, we cannot setup
	 * mirror. Return OK.
	 */

	if (DISKMETADB(prop) == NULL) {
		return (D_OK);
	}

	fp = fopen(MIRROR_CREATION_SCRIPT, "w+");

	if (fp == NULL) {
		write_notice(ERRMSG,
			"(svm_create_mirror_script) %s",
			strerror(errno));
		return (D_BADARG);
	}

	bzero(buf, sizeof (buf));
	/*
	 * devfsadm is needed to create SVM pseudo device 'md'
	 */
	if (!GetSimulation(SIM_EXECUTE)) {
		(void) fprintf(fp, "/usr/sbin/devfsadm -i %s -p %s/%s > "\
			"/dev/null 2>&1 \n",
			SVM_PSEUDO_DRIVER, get_protodir(), WPATH_TO_INST);
	}

	/*
	 * Go through the profile and add commands to the script to
	 * create metadb
	 */
	WALK_LIST(mdb, DISKMETADB(prop)) {

		(void) fprintf(fp, "/usr/bin/echo \"%s %s\"\n", 
			MSG0_METADB_SLICE_CONFIGURE, mdb->dev); 
		if (!GetSimulation(SIM_EXECUTE)) {
			(void) fprintf(fp,
				"/usr/sbin/metadb -a -f -c %d -l %d %s\n",
					mdb->count, mdb->size, mdb->dev);
		}
	}

	/*
	 * Collect all the requested mirror names so that we don't 
	 * use them for submirrors
	 */
	
	volume_names[0] = 0;
	WALK_LIST(fsf, DISKFILESYS(prop)) {

		char	str[MAX_SVM_MIRROR_NAMELEN];

		if (!fsf->is_mirror)
			continue;
		/*
		 * Copy all the specified volume names in a buffer
		 * to compare against assigned volume names
		 */
		if (fsf->mirror_name) {
			(void) snprintf(str, sizeof (str), ":%s:",
				fsf->mirror_name);
			strncat(volume_names, str, strlen(str));
		}
	}

	/*
	 * process filesys entries
	 */
	WALK_LIST(fsf, DISKFILESYS(prop)) {

		if (!fsf->is_mirror)
			continue;

		mirror_setup = TRUE;

		/*
		 * Assign names to mirror components so that there is
		 * no clash
		 */
		if (fsf->mirror_name)
			(void) strncpy(mirror, fsf->mirror_name, sizeof (mirror));
		else
			mirror[0] = '\0';

		current = _assign_volume_names(volume_names, current, mirror,
				submirror1, submirror2);

		/*
		 * If the user has provided a mirror name, copy over
		 * but retain submirror names. If the mirror name is
		 * not provided, save the mirror name got from the
		 * above function in the Profile for future use.
		 */
		if (!fsf->mirror_name)
			fsf->mirror_name = xstrdup(mirror);

		/*
		 * Find the size of the partitions. 
		 * SVM needs sizeof(submirror1) <= sizeof(submirror2)
		 */

		if (fsf->dev && fsf->dev_mirror) {
			Disk_t	*dp;
			char 	*ptr1, *ptr2;
			int 	slice1, slice2;
			int	size1, size2;
			char	tmp[MAXPATHLEN];

			size1 = size2 = 0;
			/* Find the size of first submirror device */
			dp = find_disk(fsf->dev);
			ptr1 = strrchr(fsf->dev, 's');
			if (ptr1) {
				slice1 = atoi(++ptr1);
				size1 = slice_size(dp, slice1);
			}

			/* Find the size of second submirror device */
			dp = find_disk(fsf->dev_mirror);
			ptr2 = strrchr(fsf->dev, 's');
			if (ptr2) {
				slice2 = atoi(++ptr2);
				size2 = slice_size(dp, slice2);
			}

			/*
			 * If size1 is <= size2, we can mirror the devices 
			 * Otherwise give an error and exit.
			 */
			if (size1 > size2) {
				write_notice(ERRMSG,MSG2_SVM_SLICE2_IS_SMALL,
					fsf->dev_mirror, fsf->dev);	
				return (D_BADARG);
			}
		}

		/*
		 * Create the submirrors
		 */
		if (!GetSimulation(SIM_EXECUTE)) {
			(void) fprintf(fp, "/usr/sbin/metainit -f %s 1 1 %s\n",
				submirror1, fsf->dev);

			if (fsf->dev_mirror) {
				(void) fprintf(fp,
					"/usr/sbin/metainit -f %s 1 1 %s\n",
						submirror2, fsf->dev_mirror);
			}
			/*
		 	 * Due to a problem in metacommands with Read only
			 * file system, we have to copy the temporary file
			 * created by metacommands to the original file
		 	 */
			(void) fprintf(fp, "/usr/bin/cp %s %s\n",
				new, original);
		}

		/*
		 * Create the mirror using metainit
		 */
		(void) fprintf(fp, "/usr/bin/echo \"%s %s (%s)\"\n", 
				MSG0_MIRROR_SLICE_CONFIGURE, mirror, fsf->name);
		if (!GetSimulation(SIM_EXECUTE)) {
			/*
			 * If second submirror is given use it to create
			 * mirror using metainit
			 */
			if (fsf->dev_mirror) {
				(void) fprintf(fp,
					"/usr/sbin/metainit %s -m %s %s\n",
					mirror, submirror1, submirror2);
				/*
			 	 * do a newfs on the mirror device just make 
			 	 * sure that mirror device is clean
			 	 */
				(void) fprintf(fp,
					"/usr/sbin/newfs /dev/md/rdsk/%s \
					</dev/null > /dev/null 2>&1 \n",
					mirror);

			} else {
				(void) fprintf(fp,
					"/usr/sbin/metainit %s -m %s\n",
					mirror, submirror1);
			}

			(void) fprintf(fp, "/usr/bin/cp %s %s\n",
				new, original);

			/*
		 	 * If / is mirrored, call metaroot to make the
			 * mirrored volume as the default bootable device
		 	 */
			if (streq(fsf->name, ROOT)) {
				(void) strncpy(root_mirror, mirror,
					sizeof (root_mirror));	
				(void) snprintf(buf, sizeof (buf),
			    		"/usr/sbin/metaroot -R %s %s\n",
						get_rootdir(), mirror);
			}
		}
	}
				
	fclose(fp);

	if (GetSimulation(SIM_EXECUTE)) {
		return(D_OK);
	}
	/*
	 * The second script will be executed after installing the packages
	 * because metaroot needs to update the files /a/etc/vfstab
	 * and /a/etc/system
	 */
	if (mirror_setup) {
		fp = fopen(MIRROR_TRANSFER_SCRIPT, "w+");

		if (fp == NULL) {
			write_notice(ERRMSG,
				"(svm_mirror_script) %s",
				strerror(errno));
			return (D_BADARG);
		}

		(void) fprintf(fp, "/usr/sbin/devfsadm -i %s -p %s/%s -r %s > "\
			"/dev/null 2>&1 \n",
			SVM_PSEUDO_DRIVER, get_rootdir(),
				WPATH_TO_INST, get_rootdir());

		if (buf[0] != 0) {
			(void) fprintf(fp,
				"/usr/bin/echo \"%s (/dev/md/dsk/%s)\"\n", 
					MSG0_MIRROR_ROOT_DEVICE, root_mirror);
			(void) fprintf(fp, "%s\n", buf);
		}
		fclose(fp);


		/*
		 * Save the file system property list so that it can referred
		 * during the mounting of mirror file systems
		 */
		file_system_list = DISKFILESYS(prop);

	}
	return (D_OK);
}

/*
 * Function:	execute_mirror_script
 * Description: This function executes the scripts to setup mirrors
 *
 * Scope:	public
 * Parameters:	script	 - Full path name of the script
 *		log	 - Full path name of the output log file
 * Return:	0	 - The execution of the shell script is successful
 *		< 0	 - The shell script failed to execute completely.
 */
int
execute_mirror_script(char *script, char *log)
{
	int		status;
	char		buf[MAXPATHLEN];
	FILE		*fp;

	(void) snprintf(buf, sizeof (buf), "/bin/sh %s > %s 2>&1",
		script, log);

	status = system(buf);

	fp = fopen(log, "r+");

	if (fp == NULL) {
		write_notice(ERRMSG,
			MSG1_MIRROR_LOG_FAILED, strerror(errno));
		return (status);
	}

	while (fgets(buf, sizeof (buf), fp) != NULL) {
		/*
		 * Ignore trivial status messages and read-only file system
		 * errors. We need to check both translated and C only 
		 * messages because some of the error messages are not 
		 * translated.
		 */
		if (strstr(buf, MSG0_READ_ONLY) != NULL ||
			strstr(buf, "Read-only") != NULL) {
			continue;
		}
		if (strstr(buf, MSG0_SETUP) != NULL  ||
			strstr(buf, "setup") != NULL) {
			continue;
		}
		if (strstr(buf, MSG0_SUBMIRRORS) != NULL ||
			strstr(buf, "submirrors") != NULL) {
			continue;
		}
		if (strstr(buf, MSG0_METAINIT) != NULL ||
			strstr(buf, "metainit") != NULL) {
			continue;
		}
		if (strcmp(buf, "\n") == 0) {
			continue;
		}
		write_status(LOGSCR, LEVEL1|LISTITEM|FMTPARTIAL, buf);
	}
	return (D_OK);
}

/*
 * Function:	get_mirror_block_device
 * Description:	Given the device, this return the mirror block device
 *		if available.
 * Scope:	public
 * Parameters:	disk		pointer to disk name (e.g. c0t0d0)
 *              slice		slice number
 * Return:	char *		Successfully returned the mirror block device
 *				The mirror_bdev look like /dev/md/dsk/volume
 *		NULL		There is no mirror device
 */
char *
get_mirror_block_device(char *disk, int slice)
{

	Storage *fsf;
	char	mirror_bdev[MAXPATHLEN];
	char	device[MAXPATHLEN];

	(void) snprintf(device, sizeof (device), "%ss%d", disk, slice);
	WALK_LIST(fsf, file_system_list) {
		if ((streq(device, fsf->dev)) &&
		    (fsf->mirror_name)) {
			    (void) snprintf(mirror_bdev, sizeof (mirror_bdev),
					"/dev/md/dsk/%s", fsf->mirror_name);
			     return (mirror_bdev);
		}
	}
	return (NULL);
}

/*
 * Function:	get_mirror_char_device
 * Description:	Given the device, this return the mirror char device
 *		if available.
 * Scope:	public
 * Parameters:	disk		pointer to disk name (e.g. c0t0d0)
 *              slice		slice number
 * Return:	char *		Successfully returned the mirror char device
 *				The mirror_bdev look like /dev/md/rdsk/volume
 *		NULL		There is no mirror device
 */
char *
get_mirror_char_device(char *disk, int slice)
{

	Storage *fsf;
	char	mirror_cdev[MAXPATHLEN];
	char    device[MAXPATHLEN];

	(void) snprintf(device, sizeof (device), "%ss%d", disk, slice);
	WALK_LIST(fsf, file_system_list) {
		if ((streq(device, fsf->dev)) &&
		    (fsf->mirror_name)) {
			    (void) snprintf(mirror_cdev, sizeof (mirror_cdev),
					"/dev/md/rdsk/%s", fsf->mirror_name);
			    return (mirror_cdev);
		}
	}
	return (NULL);
}

/*
 * Function:  get_all_mirror_parts
 * Description:       Given the device, this returns all the disk slices
 *            that form this mirror.
 * Scope:     public
 * Parameters:        disk            pointer to disk slice (e.g. c0t0d0)
 *              slice         slice number
 * Return:    StringList *    StringList of full pathname of all the
 *                            slices that form the mirror
 *            NULL            There is no mirror device
 */
StringList *
get_all_mirror_parts(char *disk, int slice)
{

	Storage		*fsf;
	StringList	*slices = NULL;
	char		device[MAXPATHLEN];
	char		buf[MAXPATHLEN];

	(void) snprintf(device, sizeof (device), "%ss%d", disk, slice);
	WALK_LIST(fsf, file_system_list) {
		if ((streq(device, fsf->dev)) &&
		    (fsf->mirror_name)) {
			(void) snprintf(buf, sizeof (buf),
			    "/dev/rdsk/%s", fsf->dev);
			slices = StringListBuild(buf, ',');
			if (fsf->dev_mirror) {
				(void) snprintf(buf, sizeof (buf),
				    "/dev/rdsk/%s", fsf->dev_mirror);
				StringListAdd(&slices, buf);
			}
			break;
		}
	}
	return (slices);
}

/*
 * Function:	is_slice_tobe_mirrored
 * Description:	Given the device, this returns whether the slice will be
 *		part of a mirror device
 * Scope:	public
 * Parameters:	disk		pointer to disk name (e.g. c0t0d0)
 *              slice		slice number
 * Return:	1		TRUE (part of mirror)
 *		0		FALSE (Not part of mirror)
 */
int
is_slice_tobe_mirrored(char *disk, int slice)
{

	Storage *fsf;
	char    device[MAXPATHLEN];

	if (disk == NULL) {
		return (0);
	}

	(void) snprintf(device, sizeof (device), "%ss%d", disk, slice);
	WALK_LIST(fsf, file_system_list) {
		if (fsf->dev_mirror &&
		    (streq(device, fsf->dev_mirror))) {
			    return (1);
		}
	}
	return (0);
}

/*
 * Function:	setup_metadb_disk
 * Description: Configure metadb slice according to the profile specification.
 * Scope:	public
 * Parameters:	prop	 - pointer to profile structure
 * Return:	D_OK	 - configuration successful
 *		D_BADARG - invalid argument
 *		D_FAILED - internal failure
 */
int
setup_metadb_disk(Profile *prop)
{
	MDBStorage	*mdb;
	Storage		*new;
	static	char	temp[MAXPATHLEN];
	int		status = D_OK;
	int		size_in_mb;

	/* validate arguments */
	if (prop == NULL) {
		write_notice(ERRMSG,
			"(configure_metadb) %s",
			library_error_msg(D_BADARG));
		return (D_BADARG);
	}

	/*
	 * process metadb entries
	 */
	WALK_LIST(mdb, DISKMETADB(prop)) {

		/*
		 * Setup the metadb slice
		 */
		new = (Storage *)xcalloc(sizeof (Storage));
		new->dev = mdb->dev;
		/*
		 * size is in blocks.
		 * Convert it in to MBytes for disk size
		 */
		size_in_mb = (mdb->size * UBSIZE)/(1024 * 1024) ;
		(void) snprintf(temp, sizeof (temp), "%d",
			mdb->count * size_in_mb) ;
		new->size = temp;
		new->is_mirror = 0;
		new->preserve = 0;
		new->name = xstrdup("");
		new->mirror_name = xstrdup("State Database Replica");

		/*
		 * Configure the metadb slice
		 */
		status = app_config_slice(prop, new);
		free (new->name);
		free (new->mirror_name);
		free(new);
		if (status != D_OK) {
			return (status);
		}

	}

	return (D_OK);
}

/*
 * Function:	setup_mirror_disk
 * Description: Configure svm mirror slice according to the profile
 * 		specification.
 * Scope:	public
 * Parameters:	prop	 - pointer to profile structure
 * Return:	D_OK	 - configuration successful
 *		D_BADARG - invalid argument
 *		D_FAILED - internal failure
 */
int
setup_mirror_disk(Profile *prop, Storage *fsf)
{
	Storage		*new;
	int		status;
	char		str[MAXPATHLEN];
	char		temp[MAXPATHLEN];

	/* validate arguments */
	if (fsf == NULL) {
		write_notice(ERRMSG,
			"(configure_svm_mirror) %s",
			library_error_msg(D_BADARG));
		return (D_BADARG);
	}

	/*
	 * process filesys entry
	 */
	if (!fsf->is_mirror)
		return (D_OK);
	/*
	 * Setup the first slice
	 */
	new = (Storage *)xcalloc(sizeof (Storage));
	new->dev = fsf->dev;
	new->size = fsf->size;
	new->name = fsf->name;
	if (fsf->mirror_name) {
		(void) snprintf(str, sizeof (str), "%s %s",
			MSG0_MIRROR_VOLUME, fsf->mirror_name);
	} else {
		(void) snprintf(str, sizeof (str), "%s", MSG0_MIRROR_VOLUME);
	}

	new->mirror_name = str;
	new->is_mirror = 0;
	new->preserve = 0;
	new->mntopts = fsf->mntopts;

	/*
	 * Configure the first submirror slice
	 */
	if ((status = app_config_slice(prop, new)) != D_OK) {
		free(new);
		return (status);
	}

	/*
	 * Setup the second slice
	 */
	if (fsf->dev_mirror) {
		new->dev = fsf->dev_mirror;
		new->size = fsf->size;
		/*
		 * If SWAP is mirrored, let the second slice also start
		 * at the beginning of the disk.
		 */
		if (streq(fsf->name, SWAP))
			new->name = strdup("SWAP_MIRROR");
		else 
			new->name = strdup("");

		new->is_mirror = 0;
		new->preserve = 0;
		new->mntopts = fsf->mntopts;

		/*
		 * Configure the first submirror slice
		 */
		if ((status = app_config_slice(prop, new)) != D_OK) {
			free(new->name);
			free(new);
			return (status);
		}
		free(new->name);
	}
	/*
	 * free the allocated filesys property
	 */
	free(new);

	return (D_OK);
}

/* ---------------------- private functions ---------------------- */

/*
 * Function:	_assign_volume_names
 * Description:	Assign names to mirror components so that there is no clash
 *		The logic used here is as follows. The mirror names are from
 *		d0 to d128.
 * 		1. If the user provided a volume name for the mirror, try to get next
 *		two numbers as submirror names. 
 *		For example if d7 is the mirror name, try to get d8 and d9 for
 *		submirrors. If the user is already used d8 and/or d9, the next
 *		available names will be used.
 *
 *		2. If the user lets the install to provide the voulme name, start with
 *		d0 if it is available, use it otherwise jump to d10 and so on.
 *		Apply the rule 1 after the mirror name is selected.
 *
 *		3. If you reach the max (128), then you may have exhausted all the
 *		numbers ending in 0, so use a different jumping index (say 5).
 *
 *		4. Return the the number used in the volume + 10 as the new value
 *		to be used for the next mirror name assignment request
 *
 * Scope:	private
 * Parameters:	volume_names	Currently requested list of mirror names
 * 		current		The integer portion of current mirror name
 *		mirror		The mirror name is returned
 * 		submirror1	The submirror1 name is returned
 * 		submirror2	The submirror2 name is returned
 * Return:	int		The integer portion of new mirror name
 *				for subsequent use
 */

#define MIRROR_JUMP_INDEX	10
#define SECONDARY_MIRROR_START_INDEX	5

static int
_assign_volume_names(char *volume_names, int current, char *mirror,
		char *submirror1, char *submirror2)
{
	char		*base_string = "d";
	char		str[MAX_SVM_MIRROR_NAMELEN];

	/* Assign a volume name for mirror */
	if (mirror[0] == '\0') {
	    while (1) {
		if (current >= MAX_SVM_VOLUME_ID)
			current = SECONDARY_MIRROR_START_INDEX;
		(void) snprintf(mirror, sizeof (mirror), "%s%d",
			base_string, current);
		if (_can_use_volume_name(mirror, volume_names)) {
			/* mirror_name is not already used. So break */
			break;
		}
		current = current + MIRROR_JUMP_INDEX;
	    }
	    /*
	     * update the volume_names buffer to add the recently allocated
	     * volume name so that they won't be used again
	     */
		
	    (void) snprintf(str, sizeof (str), ":%s:", mirror);
	    strncat(volume_names, str, strlen(str));
	}

	/*
	 * Make submirror names with some relation to mirror names
	 * If the mirror is d10, we want to make submirrors d11 and d12
	 */
	
	current = atoi(mirror+1) + 1 ;

	/* Assign a volume name for submirror1 */
	while (1) {
		if (current >= MAX_SVM_VOLUME_ID)
			current = SECONDARY_MIRROR_START_INDEX;
		(void) snprintf(submirror1, sizeof (submirror1), "%s%d",
			base_string, current);
		if (_can_use_volume_name(submirror1, volume_names)) {
			/* mirror_name is not already used. So break */
			break;
		}
		current++;
	}

	/*
	 * update the volume_names buffer to add the recently allocated
	 * volume name so that they won't be used again
	 */
	(void) snprintf(str, sizeof (str), ":%s:", submirror1);
	strncat(volume_names, str, strlen(str));

	/* Assign a volume name for submirror2 */
	while (1) {
		if (current >= MAX_SVM_VOLUME_ID)
			current = SECONDARY_MIRROR_START_INDEX;
		(void) snprintf(submirror2, sizeof (submirror2), "%s%d",
			base_string, current);
		if (_can_use_volume_name(submirror2, volume_names)) {
			/* mirror_name is not already used. So break */
			break;
		}
		current++;
	}

	/*
	 * update the volume_names buffer to add the recently allocated
	 * volume names so that they won't be used again
	 */
	(void) snprintf(str, sizeof (str), ":%s:", submirror2);
	strncat(volume_names, str, strlen(str));

	current = atoi(mirror+1) + MIRROR_JUMP_INDEX;
	return (current);
}

/*
 * Function: _can_use_volume_name
 * Description:	Given a volume name, this function checks whether it is already
		assigned.
 * Scope:	private
 * Parameters:	volume_name	Volume name 
 * 		repositary	list of volume names assigned already
 * Return:	1, if this voulme name can be used
 *		0, if assigned already		
 */
static	int 
_can_use_volume_name(char *volume_name, char *repository)
{
	char tmp_str[MAX_SVM_MIRROR_NAMELEN];

	snprintf(tmp_str, sizeof (tmp_str), ":%s:", volume_name);
	if (strstr(repository, tmp_str) == NULL) 
		return (1);
	return (0);
}
