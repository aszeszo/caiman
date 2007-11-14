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

#pragma ident	"@(#)svc_updateconfig.c	1.61	07/10/09 SMI"


/*
 * Module:	svc_updateconfig.c
 * Group:	libspmisvc
 * Description: Routines to update the configuration of file on
 *		an installed system.
 */

#include <ctype.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <arpa/inet.h>
#include <device_info.h>
#include <sys/mman.h>
#include <sys/mntent.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include "spmisvc_lib.h"
#include "svc_strings.h"
#include "spmicommon_api.h"
#include "spmisoft_lib.h"
#include "spmisoft_api.h"
#include "soft_locale.h"

/* constants */

#define	TMPVFSTAB			"/tmp/vfstab"
#define	TMPVFSTABUNSELECT		"/tmp/vfstab.unselected"
#define	SUPPRESS_SOLSTART_FINISH_FILE	"/tmp/.suppress_solstart_finish"
#define	SYS_UNCONFIG			"/usr/sbin/sys-unconfig"

static char transferlist[MAXPATHLEN] = TRANS_LIST;

static char *dev_entries_to_delete[] = {
	"dsk",
	"rdsk",
	"fbs",
	"rmt",
	"cfg",
	"dump",
	"cua",
	"fd",
	"swap",
	"term",
	"pts",
	"ecpp0",
	NULL	/* last entry must be NULL */
};

/* internal prototypes */

int	_setup_bootblock(void);
int	_clean_devices(void);
int	_setup_devices(void);
int	_setup_etc_hosts(Dfs *);
int	_setup_i386_bootenv(Disk_t *, int);
int	_setup_i386_stubboot(void);
int	_setup_i386_grubmenu(Disk_t *, int);
int	_setup_tmp_root(TransList **);
int	_setup_transferlist(TransList **);
int	_setup_vfstab(OpType, Vfsent **);
int	_setup_vfstab_unselect(void);
int	_update_etc_default_init(void);
int	SystemConfigProm(void);

/* private prototypes */

static char	*get_bootpath(char *, int);
static int	parse_transtype(TransType **, char *);
static int	link_file(char *, char *);
static int	write_bootblocks(char *);

/* globals */

static char	cmd[MAXNAMELEN];

/* public functions */

/*
 * get_transferlist()
 *	Returns the transferlist previously set by a call to
 *	set_transferlist(). If set_transferlist() hasn't been called
 *	this returns the default location of /etc/transfer_list.
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to current transferlist string
 * Status:
 *	public
 */
char *
get_transferlist(void)
{
	return (transferlist);
}

/*
 * set_transferlist()
 *	Sets the private 'transferlist' variable. Used to transfer identity
 *	files (like /etc/hosts) to the newly-installed system.
 * Parameters:
 *	newtransferlist	- pathname used to set transferlist
 * Return:
 *	none
 * Status:
 *	public
 */
void
set_transferlist(char *newtransferlist)
{
	(void) strcpy(transferlist, newtransferlist);
	canoninplace(transferlist);
}

/* ---------------------- internal functions ----------------------- */

/*
 * Function:	_is_dboot
 * Description:	Figure out if the target uses direct boot
 * Scope:	internal
 * Parameters:	none
 * Return:	1	target is dboot
 *		0	target is dboot
 */
int
_is_dboot(void)
{
	char mbfile[MAXPATHLEN];
	struct stat sbuf;

	/*
	 * Check for existence /boot/solaris/bin/symdef
	 */
	(void) snprintf(mbfile, MAXPATHLEN, "%s/boot/solaris/bin/symdef",
	    get_rootdir());
	if (stat(mbfile, &sbuf) == -1) {
		return (0);
	}
	return (1);
}

/*
 * Function:	_is_multiboot
 * Description:	Figure out if the target uses multiboot or realmode
 * Scope:	internal
 * Parameters:	none
 * Return:	1	target is multiboot
 *		0	target is not multiboot
 */
int
_is_multiboot(void)
{
	char mbfile[MAXPATHLEN];
	struct stat sbuf;

	/*
	 * Check for existence /platform/i86pc/multiboot
	 */
	(void) snprintf(mbfile, MAXPATHLEN, "%s/platform/i86pc/multiboot",
	    get_rootdir());
	if (stat(mbfile, &sbuf) == -1) {
		return (0);
	}
	return (1);
}

/*
 * Function:	_setup_realmode_bootblock
 * Description:	Install boot blocks on boot disk for realmode-based
 *		flash archive. This can disappear in SunOS 5.11
 * Scope:	internal
 * Parameters:	none
 * Return:	ERROR	- boot block installation failed
 *		NOERR	- boot blocks installed successfully
 */
static int
_setup_realmode_bootblock(Mntpnt_t *info)
{
	Disk_t	*bdp;
	int	stubused;
	char	*rootdir = get_rootdir();
	char	*bootblk_path;
	char	*pboot_path;

	bdp = info->dp;

	stubused = (DiskobjFindStubBoot(CFG_CURRENT, NULL, NULL) == D_OK) ?
								TRUE : FALSE;
	/*
	 * configure the /boot/solaris/bootenv.rc (i386 platforms only)
	 */
	if (_setup_i386_bootenv(bdp, info->slice) != NOERR)
		return (ERROR);

	if (stubused) {
		/*
		 * configure the stub boot partition (i386 only, if present)
		 */
		if (_setup_i386_stubboot() != NOERR)
			return (ERROR);

		/*
		 * Nothing else to do (we don't need boot blocks)
		 */
		return (NOERR);
	}

	write_status(LOGSCR, LEVEL1|LISTITEM,
		    MSG1_BOOT_BLOCKS_INSTALL, disk_name(bdp));

	/*
	 * if you are not running in execution simulation, find the new
	 * bootblocks which were just installed on the system and install
	 * them on the boot disk
	 */
	if (!GetSimulation(SIM_EXECUTE) && !GetSimulation(SIM_SYSDISK)) {
		if ((bootblk_path = gen_bootblk_path(rootdir)) == NULL &&
				(DIRECT_INSTALL || (bootblk_path =
					gen_bootblk_path("/")) == NULL)) {
			write_notice(ERRMSG, MSG0_BOOT_BLOCK_NOTEXIST);
			return (ERROR);
		}

		/*
		 * the pboot file path name is a required argument for
		 * i386 installboot calls; if you can't find it, you're
		 * in trouble at this point
		 */
		if ((pboot_path = gen_pboot_path(rootdir)) == NULL &&
				(DIRECT_INSTALL || (pboot_path =
					gen_pboot_path("/")) == NULL)) {
			write_notice(ERRMSG, MSG0_PBOOT_NOTEXIST);
			return (ERROR);
		}

		(void) sprintf(cmd,
			"/usr/sbin/installboot --force_realmode %s %s %s",
			pboot_path,
			bootblk_path,
			make_char_device(disk_name(bdp), ALL_SLICE));

		if (system(cmd) != 0) {
			write_notice(ERRMSG, MSG0_INSTALLBOOT_FAILED);
			return (ERROR);
		}
	}

	return (NOERR);
}

/*
 * Function:	_setup_bootblock
 * Description:	Install boot blocks on boot disk.
 * Scope:	internal
 * Parameters:	none
 * Return:	ERROR	- boot block installation failed
 *		NOERR	- boot blocks installed successfully
 */
int
_setup_bootblock(void)
{
	Mntpnt_t info;
	Disk_t	*bdp;
	StringList	*list;
	int		error = 0;

	write_status(LOGSCR, LEVEL0, MSG0_BOOT_INFO_INSTALL);

	/* there should only be one "/" in the disk object list */
	if (find_mnt_pnt(NULL, NULL, ROOT, &info, CFG_CURRENT) == 0) {
		write_notice(ERRMSG, MSG0_ROOT_UNSELECTED);
		return (ERROR);
	}

	bdp = info.dp;

	/* handling realmode based boot archives, remove in SunOS 5.11 */
	if (streq(get_default_inst(), "i386") && !_is_multiboot() &&
	    !_is_dboot())
		return (_setup_realmode_bootblock(&info));

	/*
	 * configure the /boot/solaris/bootenv.rc file and the
	 * grub menu /boot/grub/menu.lst (i386 platforms only).
	 */
	if (_setup_i386_bootenv(bdp, info.slice) != NOERR)
		return (ERROR);

	if (disk_is_vbd(bdp)) {
		/* we are finished if installing onto a virtual disk */
		return (NOERR);
	}
	(void) _setup_i386_grubmenu(bdp, info.slice);

	write_status(LOGSCR, LEVEL1|LISTITEM,
		    MSG1_BOOT_BLOCKS_INSTALL,
		    IsIsa("sparc") ?
			make_slice_name(disk_name(bdp), info.slice) :
			disk_name(bdp));

	/*
	 * if you are not running in execution simulation, find the new
	 * bootblocks which were just installed on the system and install
	 * them on the boot disk
	 */
	if (GetSimulation(SIM_EXECUTE) || GetSimulation(SIM_SYSDISK))
		return (NOERR);

	/*
	 * Check whether the root is a SVM mirror.
	 * If so, write bootblocks in all submirror slices
	 */

	list = get_all_mirror_parts(disk_name(bdp), info.slice);
	if (list == NULL) {
		char    *root_slice;
		/*
		 * The root is not mirrored.
		 * Write bootblocks to the root partition we got
		 */
		root_slice = make_char_device(disk_name(bdp), info.slice);
		write_status(LOGSCR, LEVEL1|LISTITEM,
		    MSG1_BOOT_BLOCKS_INSTALL, root_slice);
		if (write_bootblocks(root_slice)) {
			error++;
		}
	} else {
		StringList	*ptr;
		/*
		 * The root is mirrored.
		 * Walk through all the sub mirror slices and write
		 * bootblocks.
		 */
		for (ptr = list; ptr != NULL; ptr = ptr->next) {
			write_status(LOGSCR, LEVEL1|LISTITEM,
			    MSG1_BOOT_BLOCKS_INSTALL, ptr->string_ptr);
			if (write_bootblocks(ptr->string_ptr))
				error++;
		}
		StringListFree(list);
	}

	if (error) {
		return (ERROR);
	}

	return (NOERR);
}

/*
 * Function:	_clean_devices
 * Description:	When extracting a Flash archive, we end up extracting a copy
 *		of the device tree from the master.  This is only a good thing
 *		if the clone is exactly the same as the master.  In the majority
 *		of cases, however, it is not.  We therefore have to clean out
 *		as much of the device tree that is specific to the master as
 *		possible so we can start anew for the clone.  If we don't do
 *		this, controller numbers on the clone can end up starting from
 *		1 instead of zero, among other things.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	- setup successful
 *		ERROR	- setup failed
 */
int
_clean_devices(void)
{
	char path[PATH_MAX + 2];
	char cmd[PATH_MAX + 10];
	int i;
	struct stat st;
	struct dirent *dp;
	int changed;
	DIR *dirp;

	write_status(LOGSCR, LEVEL0, MSG0_DEVICES_CLEAN);

	/*
	 * There is no way to simulate this, so don't even try
	 */
	if (GetSimulation(SIM_EXECUTE)) {
		return (NOERR);
	}

	/*
	 * There are two ways to do this - the Q&D hack, or the right way.
	 * The right way involves special flags to devfsadm that will tell
	 * it to recreate things from scratch.  The hack is to blow away
	 * all of /devices except for pseudo, and to clear some devices
	 * under /dev.
	 */

	/* Remove all of /devices except for pseudo */
	(void) snprintf(path, PATH_MAX + 2, "%s/devices", get_rootdir());
	canoninplace(path);

	do {
		changed = 0;
		if (!(dirp = opendir(path))) {
			write_notice(ERRMSG, MSG0_CANT_FIND_DEVICES, path);
			return (ERROR);
		}

		while ((dp = readdir(dirp))) {
			if (streq(dp->d_name, ".") ||
			    streq(dp->d_name, "..") ||
			    streq(dp->d_name, "pseudo")) {
				continue;
			}

			if (get_trace_level() > 2) {
				write_status(LOG, LEVEL1|LISTITEM,
				    MSG0_REMOVING, dp->d_name);
			}

			(void) sprintf(cmd, "rm -fr %s/%s",
			    path, dp->d_name);
			if (system(cmd)) {
				write_notice(ERRMSG, MSG0_CANT_CLEAN_DEVICES,
				    path);
				return (ERROR);
			}
			changed = 1;
			break;
		}

		(void) closedir(dirp);

	} while (changed);

	/* Kill off some /dev entries for good measure. */

	for (i = 0; dev_entries_to_delete[i] != NULL; i++) {
		(void) sprintf(path, "%s/dev/%s", get_rootdir(),
		    dev_entries_to_delete[i]);
		if (stat(path, &st) && (errno == ENOENT)) {
			/* don't delete it if it's not there */
			continue;
		}
		(void) sprintf(cmd, "rm -fr %s", path);
		if (stat(path, &st) || system(cmd)) {
			write_notice(ERRMSG, MSG0_CANT_CLEAN_DEVICES, path);
			return (ERROR);
		}

		if (get_trace_level() > 2) {
			write_status(LOG, LEVEL1|LISTITEM, MSG0_REMOVING, path);
		}
	}

	return (NOERR);
}

/*
 * Function:	_setup_devices
 * Description:	Configure the /dev and /devices directory by copying over from
 *		the running system /dev and /devices directory. Install the
 *		/reconfigure file so that an automatic "boot -r" will occur.
 *		Note that a minimum set of devices must be present in the
 *		/dev and /devices tree in order for the system to even boot
 *		to the level of reconfiguration.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	- setup successful
 *		ERROR	- setup failed
 */
int
_setup_devices(void)
{
	char    root[MAXNAMELEN] = "";
	char    reconfig_path[MAXNAMELEN] = "";
	int 	fd;

	/* only set up devices for indirect installs */
	if (DIRECT_INSTALL)
		return (NOERR);

	write_status(LOGSCR, LEVEL0, MSG0_DEVICES_CUSTOMIZE);
	write_status(LOGSCR, LEVEL1|LISTITEM, MSG0_DEVICES_PHYSICAL);
	write_status(LOGSCR, LEVEL1|LISTITEM,
		MSG0_DEVICES_LOGICAL);

	(void) strcpy(root, get_rootdir());
	if (!GetSimulation(SIM_EXECUTE)) {

		(void) sprintf(cmd,
		    "/usr/sbin/devfsadm -R %s > /dev/null 2>&1", root);

		if (system(cmd) != 0) {
			write_notice(ERRMSG,
				MSG1_DEV_INSTALL_FAILED,
				"/devices");
			return (ERROR);
		}

		(void) sprintf(reconfig_path, "%s/reconfigure", root);

		if ((fd = creat(reconfig_path, 0444)) < 0)
			write_notice(WARNMSG, MSG0_REBOOT_MESSAGE);
		else
			(void) close(fd);
	}

	return (NOERR);
}

/*
 * Function:	_setup_etc_hosts
 * Description:	Create the system 'etc/hosts' file using the remote file systems
 *		specified by the user during installation configuration.
 * Scope:	internal
 * Parameters:	cfs	- pointer to remote file system list
 * Return:	NOERR	- /etc/hosts file created successfully
 *		ERROR	- attempt to create /etc/hosts file failed
 */
int
_setup_etc_hosts(Dfs *cfs)
{
	FILE 		*fp;
	Dfs 		*p1, *p2;
	int		match;
	struct hostent	*ent;
	char		*cp = NULL;

	write_status(LOGSCR, LEVEL1|LISTITEM, MSG0_HOST_ADDRESS);

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	if ((fp = fopen("/etc/hosts", "a")) == NULL) {
		write_notice(ERRMSG,
			MSG_OPEN_FAILED,
			"/etc/hosts");
		return (ERROR);
	}

	for (p1 = cfs; p1; p1 = p1->c_next) {
		for (match = 0, p2 = cfs; p2 != p1; p2 = p2->c_next) {
			if (strcmp(p1->c_hostname, p2->c_hostname) == 0) {
				match = 1;
				break;
			}
		}
		if (match)
			continue;

		if (strstr(p1->c_mnt_pt, USR) || p1->c_ip_addr[0]) {
			if (p1->c_ip_addr[0] == '\0' &&
					(ent = gethostbyname(
						p1->c_hostname)) != NULL)
			    /* LINTED */
			    cp = inet_ntoa(*((struct in_addr *)ent->h_addr));
			if (p1->c_ip_addr[0] != '\0') {
				(void) fprintf(fp,
					"%s\t%s\n", p1->c_ip_addr,
					p1->c_hostname);
			} else if (cp) {
				(void) fprintf(fp,
					"%s\t%s\n", cp, p1->c_hostname);
			}
		}
	}

	(void) fclose(fp);
	return (NOERR);
}

/*
 * Function:	_setup_i386_bootenv
 * Description:	/platform/i86pc/boot/solaris/bootenv.rc file is used by
 *		the initial boot loader to determine the location of
 *		solaris, and to hold other configuration variables.
 * Scope:	internal
 * Parameters:	bdp	valid pointer to boot disk object
 *		slice	slice index for "/" slice
 * Return:	NOERR	all work relating to bootenv completed successfully
 *		ERROR	required work in configuring bootrc failed
 */
int
_setup_i386_bootenv(Disk_t *bdp, int slice)
{
	char	efile[MAXPATHLEN];
	char	tfile[MAXPATHLEN];
	char	edit[MAXNAMELEN];
	char	*lp;
	FILE 	*fp;

	/* if this is not an i386 system there is no work to do */
	if (!IsIsa("i386"))
		return (NOERR);

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/*
	 * THE PATH SHOULD BE WRITTEN WITH A STANDARD SOFTWARE
	 * LIBRARY FUNCTION gen_bootenv_path(), not hardcoded
	 * here
	 */
	(void) sprintf(efile, "%s/boot/solaris/bootenv.rc", get_rootdir());

	/*
	 * if we can't find bootenv.rc, then we are dead
	 */
	if (access(efile, R_OK) != 0)
		return (ERROR);

	/*
	 * we know there's a bootenv.rc file at this point; strip
	 * any "setprop bootpath" lines from the existing file
	 */
	(void) sprintf(tfile, "%s-", efile);
	(void) unlink(tfile);
	(void) sprintf(edit,
		"/usr/bin/sed -e '/^setprop bootpath/d' < %s > %s",
		efile, tfile);
	(void) system(edit);

	/*
	 * find the string that needs to be substituted, and if one
	 * is defined, add the "setprop bootpath" line to the file.
	 */
	if ((lp = get_bootpath(disk_name(bdp), slice)) != NULL) {
		/*
		 * Print the status message only if we're actually going to
		 * edit the file.
		 */
		write_status(LOGSCR, LEVEL1|LISTITEM, MSG0_BOOTENV_INSTALL);

		/*
		 * append on the new (correct) entry, and replace the
		 * current bootenv.rc file with the temporary edited
		 * copy
		 */
		if (access(tfile, R_OK) != 0 ||
				(fp = fopen(tfile, "a")) == NULL) {
			(void) unlink(tfile);
			return (ERROR);
		}
		(void) fprintf(fp, "setprop bootpath %s\n", lp);
		(void) fclose(fp);
		if (_copy_file(efile, tfile) != NOERR) {
			(void) unlink(tfile);
			return (ERROR);
		}
	}

	(void) unlink(tfile);
	return (NOERR);
}

/*
 * Function:	_setup_i386_stubboot
 * Description:	Configure the stub boot partition.  Currently this
 *		means creating the solaris.map file.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	successful completion
 *		ERROR	configuration failed
 */
int
_setup_i386_stubboot(void)
{
	char	mapfile[MAXPATHLEN];
	FILE	*fp;

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/*
	 * When the system boots from the stub boot partition,
	 * that partition will effectively be mounted as /.
	 * All of the files in the partition, however, expect
	 * to be in /boot.  The solaris.map file tells the boot
	 * code that / is the same as /boot.  This is the same
	 * mechanism used by the floppy.
	 */
	(void) sprintf(mapfile, "%s/boot/solaris.map", get_rootdir());

	if ((fp = fopen(mapfile, "w")) == NULL) {
		(void) unlink(mapfile);
		return (ERROR);
	}

	(void) fprintf(fp, "/boot/\t/\tp\n");
	(void) fclose(fp);

	return (NOERR);
}

/*
 * Function:	_setup_i386_grubmenu
 * Description:	call bootadm to setup /boot/grub/menu.lst
 * Scope:	internal
 * Parameters:	bdp	valid pointer to boot disk object
 *		slice	slice index for "/" slice
 * Return:	NOERR	all work relating to bootenv completed successfully
 *		ERROR	required work in configuring bootrc failed
 */
int
_setup_i386_grubmenu(Disk_t *bdp, int slice)
{
	char	edit[MAXNAMELEN];

	/* if this is not an i386 system there is no work to do */
	if (!IsIsa("i386"))
		return (NOERR);

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/*
	 * Clear out grub menu
	 */
	(void) snprintf(edit, sizeof (edit),
	    "/sbin/bootadm -m delete_all_entries -R %s", get_rootdir());
	(void) system(edit);

	/*
	 * Call bootadm update-menu -R <menu_root> -o <rawrootdev>
	 */
	(void) snprintf(edit, sizeof (edit),
	    "/sbin/bootadm update-menu -R %s -o %s",
	    get_rootdir(), make_char_device(disk_name(bdp), slice));
	(void) system(edit);

	return (NOERR);
}

#define	NO_OF_ENTRIES	50

/*
 * Function:	_setup_transferlist
 * Description:	Initialize the transfer list with the files to be transfered to
 *		the indirect installation directory after the initial
 *		installation. The data structures are initialized with data from
 *		the transfer_list file.
 * Scope:	internal
 * Parameters:	transL	- a pointer to the TransList structure list to be
 *			  initialized.
 * Return:	NOERROR - setup of transfer list succeeded
 *		ERROR - setup of transfer list failed. Reasons: could not open
 *			file, couldn't read file, couldn't malloc space, or
 *			transfer-file list corrupted.
 */
int
_setup_transferlist(TransList **transL)
{
	FILE		*TransFile;	/* transferlist file pointer	*/
	int		i, allocCount;	/* Simple counter		*/
	TransList 	*FileRecord;	/* tmp trans file item		*/
	char		*file, *package;
	char		*transtype_p;
	char		transtype[32 + MAXPATHLEN]; /* String to describe */
						    /* the transfer type and */
						    /* merge script if any */
	char		line[(MAXPATHLEN * 2) + (64)];	/* String used to */
							/* read in a line */
							/* from transfer */
							/* list file */

	write_debug(SVC_DEBUG_L1(1), "_setup_transferlist");

	/*
	 * do not process the transferlist for direct installations
	 */
	if (DIRECT_INSTALL) {
		return (NOERR);
	}

	/*
	 * during a simulation, only simulate the transferlist
	 * if user has specified something other than the default.
	 */
	if (GetSimulation(SIM_EXECUTE)) {
		if (strcmp(get_transferlist(), TRANS_LIST) == 0) {
			return (NOERR);
		}
	}

	write_debug(SVC_DEBUG_L1(1), "Using %s for transferlist",
	    get_transferlist());

	if ((TransFile = fopen(get_transferlist(), "r")) == NULL) {
		write_notice(ERRMSG,
			MSG_OPEN_FAILED,
			get_transferlist());
		return (ERROR);
	}

	/*
	 * Allocate the array for files and packages
	 * I get 50 entries a time (malloc 50 then realloc 50 more)
	 */

	FileRecord = (TransList *) xcalloc(sizeof (TransList) * NO_OF_ENTRIES);

	/* initialize the array counter and allocation count */
	i = 1;
	allocCount = 1;

	while (fgets(line, sizeof (line), TransFile) != NULL) {
		/*
		 * Make sure we get rid of the newline
		 * that fgets may have left there.
		 */
		if (line[strlen(line) - 1] == '\n')
			line[strlen(line) - 1] = '\0';

		if ((file = (char *)strtok(line, " \t")) != NULL)
			if ((package = (char *)strtok(NULL, " \t")) != NULL)
				transtype_p = (char *)strtok(NULL, " \t");

		/* If transtype is NULL, default it to OVERWRITE */
		if (transtype_p == NULL) {
			(void) strncpy(transtype, OVERWRITE_STR,
			    sizeof (transtype));
		} else {
			(void) strncpy(transtype, transtype_p,
			    sizeof (transtype));
		}

		/* Verify that the read was good and the file, package, */
		/* and transtype are of the correct length. */
		if ((file == NULL) || (package == NULL) ||
		    (transtype == NULL) ||
		    (strlen(file) > (size_t)MAXPATHLEN) ||
		    (strlen(package) > (size_t)32) ||
		    (strlen(transtype) > (size_t)(32 + MAXPATHLEN))) {
			write_notice(WARNMSG,
			    MSG_READ_FAILED,
			    get_transferlist());
			(void) fclose(TransFile);
			return (ERROR);
		}

		/* See if we have to reallocate space */
		if ((i / NO_OF_ENTRIES) == allocCount) {
			FileRecord = (TransList *) xrealloc(FileRecord,
			    sizeof (TransList) *
			    (NO_OF_ENTRIES * ++allocCount));
		}

		/* Initialize the record for this file */
		FileRecord[i].file = (char *)xstrdup(file);
		FileRecord[i].package = (char *)xstrdup(package);
		FileRecord[i].found = 0;
		if (parse_transtype(&FileRecord[i].transtype, transtype) != 0)
			return (ERROR);

		write_debug(SVC_DEBUG_L1(1), "transferlist: %s %s %d:%s",
		    FileRecord[i].file, FileRecord[i].package,
		    FileRecord[i].transtype->type,
		    FileRecord[i].transtype->mergescript ?
			    FileRecord[i].transtype->mergescript : "NULL");

		/* increment counter */
		i++;
	}
	/* Store the size of the array in the found filed of the 1st entry */
	FileRecord[0].found = --i;

	/* Just for safety NULL out the package, file, and transtype */
	FileRecord[0].file = NULL;
	FileRecord[0].package = NULL;
	FileRecord[0].transtype = NULL;

	*transL = FileRecord;

	(void) fclose(TransFile);
	return (NOERR);
}

/*
 * Function:	_setup_tmp_root
 * Description:	Copy files from the transfer list (parameter transL), which are
 *		located in (get_protodir()), to the indirect install base (only
 *		applies	to indirect installs).
 * Scope:	internal
 * Parameters:	transL	a pointer to the list of files being transfered.
 * Return:	NOERR	Either this is an indirect installation and nothing
 *			was done. Or all of the applicable files were copied
 *			from (get_protodir()) to /a.
 *		ERROR	Some error occured, the transfer list was corrupted, a
 *			file could not be copied, or the attributes could not
 *			be set.
 */
int
_setup_tmp_root(TransList **transL)
{
	TransList	*trans = *transL;
	char		tmpFile[MAXPATHLEN];	/* proto file name	*/
	char		aFile[MAXPATHLEN];	/* name of /a file	*/
	struct stat	Stat_buf, Stat_buf2;
	int		error = 0, i;
	int		*flags;
	int		k, checkResult;
	FILE		*input;
	char		*command;

	/* add add'l bytes for '/usr/bin/rm -rf ' and '\0' */
	char		cmdbuf[MAXPATHLEN + 17];

	/* add add'l bytes for rootdir arugument  and '\0' */
	char		mergescriptbuf[(MAXPATHLEN * 2) + 2];

	/* only set up proto dir for indirect installs */
	if (DIRECT_INSTALL) {
		return (NOERR);
	}

	if (GetSimulation(SIM_EXECUTE)) {

		/* Don't do debug if no transfer information exists */
		if (!trans || (trans[0].found <= 0) ||
		    (trans[0].file != NULL)) {
			return (NOERR);
		}

		/*
		 * Step through the transfer array and print out
		 *   debugging info
		 */
		for (i = 1; i <= trans[0].found; i++) {
			write_debug(SVC_DEBUG_L1(1),
			    "transfer: %s\t%s\n",
			    trans[i].package,
			    trans[i].file);
		}
		return (NOERR);
	}

	/* Make sure the 1st element of array is not corrupted */
	if (!trans || (trans[0].found <= 0) || (trans[0].file != NULL)) {
		write_notice(ERRMSG, MSG0_TRANS_CORRUPT);
		return (ERROR);
	}

	/* package filter initialization */
	flags = xcalloc((trans[ 0 ].found + 1) * sizeof (int));
	for (i = 1;
		i <= trans[ 0 ].found;
		i++) {
		flags[ i ] = 0;
	}

	/* Step through the transfer array looking for items to process */

	for (i = 1; i <= trans[0].found; i++) {

		/*
		 * Package filter - checks new transfer list uncheckd
		 * entry (flags = 0) does entry's package installed on /a then
		 * marks following transfer list entries with same package
		 * to copy (flags = 1) or not to copy (flags = 2).
		 */
		if (flags[i] == 0) {
			command = (char *)xmalloc(strlen(trans[i].package) +
									60);
			(void) sprintf(command,
				"/usr/bin/pkginfo -q -R /a %s 2>/dev/null",
				trans[i].package);
			input = popen(command, "r");
			if (pclose(input) == 0) {
				checkResult = 1;
			} else {
				checkResult = 2;
			}
			free(command);
			flags[i] = checkResult;
			for (k = i + 1; k <= trans[0].found; k++) {
				if (streq(trans[k].package,
						trans[i].package)) {
					flags[k] = checkResult;
				}
			}
		}
		if (flags[i] == 2) {
			continue;
		}

		(void) sprintf(aFile, "%s%s",
			get_rootdir(), trans[i].file);
		(void) sprintf(tmpFile, "%s%s", get_protodir(), trans[i].file);
		canoninplace(tmpFile);
		/*
		 * If the file in question is not present in the proto dir
		 * then skip it. (this happens when the file is not in
		 * the proto dir before the installation.
		 */
		if (stat(tmpFile, &Stat_buf) >= 0 ||
			trans[i].transtype->type == TTYPE_MERGE) {

			write_debug(SVC_DEBUG_L1(1),
			    "transfer: %s -> %s\n",
			    tmpFile, aFile);

			/*
			 * What type of transition is this?
			 * 	OVERWRITE - copy over
			 *	REPLACE - copy over only if it exists in /a
			 *	MERGE - use merge script to copy file over.
			 */

			/* If transition type TTYPE_MERGE */
			if (trans[i].transtype->type == TTYPE_MERGE) {
				/* execute merge script */
				if (trans[i].transtype->mergescript != NULL) {
					(void) snprintf(mergescriptbuf,
					sizeof (mergescriptbuf), "%s %s",
					trans[i].transtype->mergescript,
					get_rootdir());
					if (system(mergescriptbuf) != 0) {
						write_notice(ERRMSG,
						MSG2_TRANS_MERGESCRIPT_FAILED,
						aFile,
					trans[i].transtype->mergescript);
						error = 1;
					}
				} else {
					write_notice(WARNMSG,
						MSG1_TRANS_NO_MERGESCRIPT,
						aFile);
					error = 1;
				}
			/*
			 * Else if transition type TTYPE_OVERWRITE
			 * or type TTYPE_REPLACE and file exists in /a
			 */
			} else if (
				(trans[i].transtype->type == TTYPE_OVERWRITE) ||
				((trans[i].transtype->type == TTYPE_REPLACE) &&
					(stat(aFile, &Stat_buf2) >= 0))) {

				/* Is this file really a directory? */
				if ((Stat_buf.st_mode & S_IFDIR) == S_IFDIR) {

					/*
					 * nuke the /a directory and
					 * its contents
					 */
					(void) snprintf(cmdbuf, sizeof (cmdbuf),
							"/usr/bin/rm -rf %s",
							aFile);
					(void) system(cmdbuf);

					/*
					 * Since this is a directory, we know
					 * that is have been created outside of
					 * a normal pkgadd. Thus it just needs
					 * to be created in /a and given the
					 * correct attributes.
					 */
					/* Make a direcotry in /a */
					if (mkdir(aFile, Stat_buf.st_mode) < 0)
						error = 1;
				} else { /* not a directory, but a file */

					/*
					 * Remove aFile, if it is symlink.
					 * And make proper symlink.
					 */
					if ((lstat(aFile, &Stat_buf2) == 0) &&
						(S_ISLNK(Stat_buf2.st_mode))) {
						error = link_file(tmpFile,
								aFile);
					} else {
						/*
						 * copy overwrites aFile,
						 * But mode, uid and gid
						 * associated  with aFile are
						 * not changed.
						 */
						if (_copy_file(aFile,
							tmpFile) == ERROR) {
							error = 1;
						}
					}
				}
			}

			/*
			 * Change ownership/attributes back
			 * to the way it was created.
			 */
			if ((Stat_buf.st_mode & S_IFDIR) == S_IFDIR) {
				/* Change its ownership to be the way it */
				/* was created */
				if (chown(aFile, Stat_buf.st_uid,
					Stat_buf.st_gid) < 0) {
					write_notice(WARNMSG,
						MSG1_TRANS_ATTRIB_FAILED,
						aFile);
					error = 1;
				}
			} else if (trans[i].found != 0 && error != 1) {
				/* Set the various attributes of the /a file */
				if ((chmod(aFile, trans[i].mode) < 0) ||
					(chown(aFile, trans[i].uid,
							trans[i].gid) < 0)) {
					write_notice(WARNMSG,
						MSG1_TRANS_ATTRIB_FAILED,
						aFile);
					error = 1;
				}
			}
		}
		/* free up the space taken by file, package name, and type */
		if (trans[i].file != NULL)
			free(trans[i].file);
		if (trans[i].package != NULL)
			free(trans[i].package);
		if (trans[i].transtype != NULL) {
			if (trans[i].transtype->mergescript != NULL)
				free(trans[i].transtype->mergescript);
			free(trans[i].transtype);
		}
	}

	/* Give back the borrowed memory */
	free(trans);
	free(flags);

	if (error)
		return (ERROR);
	else
		return (NOERR);
}

/*
 * Function:	_setup_vfstab
 * Description:	Create the  <bdir>/etc/vfstab file.
 *		This function sets up the /etc/vfstab. In order to have it
 *		copied to the correct file system at the end, it is made and
 *		then put in /tmp/root/etc, to be copied over when the real
 *		filesystem would be.
 * Scope:	internal
 * Parameters:	vent	- pointer to mount list to be used to create vfstab
 * Return:	NOERR	- successful
 * 		ERROR	- error occurred
 */
int
_setup_vfstab(OpType Operation, Vfsent **vent)
{
	char    	buf[128] = "";
	Vfsent  	*vp;
	FILE    	*infp;
	FILE    	*outfp;
	struct vfstab   *entp; /* pointer to mount list entry */
	struct vfstab   fent;  /* vfstab entry */
	uchar_t  	status = (GetSimulation(SIM_EXECUTE) ? SCR : LOG);
	char		vfile[64] = "";
	char		*v;
	char		devlink[MAXNAMELEN];

	write_status(LOGSCR, LEVEL1|LISTITEM, MSG0_MOUNT_POINTS);

	/*
	 * merge mount list entries from the existing /etc/vfstab file
	 * with the new new mount list
	 */
	if (_merge_mount_list(Operation, vent) == ERROR)
		return (ERROR);

	/*
	 * open the appropriate vfstab file for reading
	 */
	if (((v = getenv("SYS_VFSTAB")) != NULL) && *v)
		(void) strcpy(vfile, v);
	else
		(void) sprintf(vfile, "%s/etc/vfstab", get_rootdir());

	/*
	 * make sure there isn't a residual vfstab file sitting
	 * around, and open the temporary vfstab file for writing
	 */
	(void) unlink(TMPVFSTAB);
	if ((outfp = fopen(TMPVFSTAB, "a")) == NULL) {
		write_notice(ERRMSG,
			MSG1_FILE_ACCESS_FAILED,
			TMPVFSTAB);
		return (ERROR);
	}

	/*
	 * transfer all comment lines directly from the source vfstab
	 * file, and write out the vfstab entries from the merged
	 * mount list
	 */
	if ((infp = fopen(vfile, "r")) != NULL) {
		while (fgets(buf, 128, infp) != NULL && buf[0] == '#')
			(void) fprintf(outfp, buf);

		(void) fclose(infp);
	}

	/*
	 * load the entries from the mount list into the vfstab file
	 */
	WALK_LIST(vp, *vent) {
		entp = vp->entry;

		if (Operation != SI_FLASH_INSTALL) {
			if ((streq(entp->vfs_fstype, "swap") ||
				streq(entp->vfs_fstype, "ufs") ||
				streq(entp->vfs_fstype, "s5")) &&
			    (_map_from_effective_dev(entp->vfs_special, devlink)
				== 0)) {
				fent.vfs_special = xstrdup(devlink);
			} else {
				fent.vfs_special = xstrdup(entp->vfs_special);
			}
			if ((streq(entp->vfs_fstype, "swap") ||
				streq(entp->vfs_fstype, "ufs") ||
				streq(entp->vfs_fstype, "s5")) &&
			    (_map_from_effective_dev(entp->vfs_fsckdev, devlink)
				== 0)) {
				fent.vfs_fsckdev = xstrdup(devlink);
			} else {
				fent.vfs_fsckdev = xstrdup(entp->vfs_fsckdev);
			}
		} else {
			fent.vfs_special = xstrdup(entp->vfs_special);
			fent.vfs_fsckdev = xstrdup(entp->vfs_fsckdev);
		}

		fent.vfs_mountp = xstrdup(entp->vfs_mountp);
		fent.vfs_fstype = xstrdup(entp->vfs_fstype);
		fent.vfs_fsckpass = xstrdup(entp->vfs_fsckpass);
		fent.vfs_automnt = xstrdup(entp->vfs_automnt);
		fent.vfs_mntopts = xstrdup(entp->vfs_mntopts);

		write_status(status, LEVEL1|LISTITEM|CONTINUE,
			"%s\t%s\t%s\t%s\t%s\t%s\t%s",
			fent.vfs_special ? fent.vfs_special : "-", \
			fent.vfs_fsckdev ? fent.vfs_fsckdev : "-", \
			fent.vfs_mountp ? fent.vfs_mountp : "-", \
			fent.vfs_fstype ? fent.vfs_fstype : "-", \
			fent.vfs_fsckpass ? fent.vfs_fsckpass : "-", \
			fent.vfs_automnt ? fent.vfs_automnt : "-", \
			fent.vfs_mntopts ? fent.vfs_mntopts : "-");

		(void) putvfsent(outfp, &fent);

		free(fent.vfs_special);
		free(fent.vfs_fsckdev);
		free(fent.vfs_mountp);
		free(fent.vfs_fstype);
		free(fent.vfs_fsckpass);
		free(fent.vfs_automnt);
		free(fent.vfs_mntopts);
	}

	(void) fclose(outfp);
	(void) sprintf(buf, "%s/%s",
		INDIRECT_INSTALL ? "/tmp/root" : "", VFSTAB);

	/*
	 * only do the actual installation of the temporary file if this
	 * is a live run
	 */
	if (!GetSimulation(SIM_EXECUTE)) {
		if (_copy_file(buf, TMPVFSTAB) == ERROR) {
			write_notice(ERRMSG, MSG0_VFSTAB_INSTALL_FAILED);
			return (ERROR);
		}
	}

	return (NOERR);
}

/*
 * Function:	_setup_vfstab_unselect
 * Description: Scan all unselected disk for any slices with mountpoints
 *		beginning with '/' and assemble a vfstab entry in
 *		<bdir>/var/sadm/system/data/vfstab.unselected for the
 *		convenience of the system administrator.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	the vfstab.unselected file was either unnecessary
 *			or was created successfully
 *		ERROR	vfstab.unselected file should have been created,
 *			but was not
 */
int
_setup_vfstab_unselect(void)
{
	FILE		*fp = stderr;
	Disk_t		*dp;
	int		i;
	int		count;
	struct vfstab	*vfsp;
	Vfsent		*vp = NULL;
	Vfsent		*tmp;
	struct vfstab	*ent;
	char		buf[64] = "";

	/*
	 * scan through all unselected drives; merge all mount
	 * points found on those drives into the unselected drive
	 * mount linked list; only slices with file systems are
	 * considered for this list
	 */
	count = 0;
	WALK_DISK_LIST(dp) {
		if (disk_selected(dp) || disk_not_okay(dp))
			continue;

		WALK_SLICES(i) {
			if ((vfsp = (struct vfstab *)xcalloc(
					sizeof (struct vfstab))) == NULL)
				return (ERROR);

			vfsnull(vfsp);
			if (orig_slice_mntpnt(dp, i)[0] != '/' ||
					orig_slice_locked(dp, i) ||
					orig_slice_size(dp, i) == 0)
				continue;

			count++;
			vfsp->vfs_special = xstrdup(
					make_block_device(disk_name(dp), i));
			vfsp->vfs_fsckdev = xstrdup(
					make_char_device(disk_name(dp), i));
			vfsp->vfs_mountp = xstrdup(orig_slice_mntpnt(dp, i));
			vfsp->vfs_fstype = xstrdup(MNTTYPE_UFS);
			(void) _merge_mount_entry(vfsp, &vp);
		}
	}

	/*
	 * if there was at least one mount point entry on an unselected
	 * drive, create the vfstab.unselected file and install it on
	 * the target system
	 */
	if (count > 0) {
		write_status(LOGSCR, LEVEL1|LISTITEM,
			MSG0_VFSTAB_UNSELECTED);

		if (!GetSimulation(SIM_EXECUTE)) {
			(void) unlink(TMPVFSTABUNSELECT);
			if ((fp = fopen(TMPVFSTABUNSELECT, "a")) == NULL)
				return (ERROR);

			(void) fprintf(fp, VFSTAB_COMMENT_LINE1);
			(void) fprintf(fp, VFSTAB_COMMENT_LINE2);
			(void) fprintf(fp, VFSTAB_COMMENT_LINE3);
			(void) fprintf(fp, VFSTAB_COMMENT_LINE4);
		}

		WALK_LIST(tmp, vp) {
			ent = tmp->entry;
			write_status(GetSimulation(SIM_EXECUTE) ? SCR : LOG,
				LEVEL1|LISTITEM|CONTINUE,
				"%s\t%s\t%s\t%s\t%s\t%s\t%s",
				ent->vfs_special ? ent->vfs_special : "-", \
				ent->vfs_fsckdev ? ent->vfs_fsckdev : "-", \
				ent->vfs_mountp ? ent->vfs_mountp : "-", \
				ent->vfs_fstype ? ent->vfs_fstype : "-", \
				ent->vfs_fsckpass ? ent->vfs_fsckpass : "-", \
				ent->vfs_automnt ? ent->vfs_automnt : "-", \
				ent->vfs_mntopts ? ent->vfs_mntopts : "-");
			if (!GetSimulation(SIM_EXECUTE))
				(void) putvfsent(fp, tmp->entry);
		}

		if (!GetSimulation(SIM_EXECUTE)) {
			(void) fclose(fp);
			(void) sprintf(buf, "%s%s/vfstab.unselected",
				get_rootdir(), SYS_DATA_DIRECTORY);
			if (_copy_file(buf, TMPVFSTABUNSELECT) == ERROR)
				return (ERROR);
		}
	}

	return (NOERR);
}

/*
 * Function:	_update_etc_default_init
 * Description: Update the /etc/default/init file with the selected
 *		default system locale.  This locale is the default locale
 *		that is used when the user
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	the /etc/default/init file was updated successfully
 *		ERROR	there was a problem updating the
 *			/etc/default/init file
 */
int
_update_etc_default_init(void)
{
	char *locale;
	char path[MAXPATHLEN];

	write_status(LOGSCR, LEVEL1|LISTITEM, MSG0_ETC_DEFAULT_INIT);

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	locale = get_default_system_locale();

	if (locale) {
		(void) sprintf(path, "%s%s", get_rootdir(), INIT_FILE);
		if (save_locale(locale, path) == SUCCESS)
			return (NOERR);
		else
			return (ERROR);
	}

	return (NOERR);
}

/*
 * Function:	SystemConfigProm
 * Description:	If the existing boot device differs from the current boot
 *		device, and the system supports prom modification, and the user
 *		has authorized prom modification, then update the prom
 *		configuration by prepending the current boot device to the boot
 *		device list, using the new DDI supplied interfaces.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	Prom updated successfully, or no prom modification
 *			required.
 *		ERROR	Prom update required, authorized, and possible, but
 *			attempt to update failed.
 */
/*
 * To get around a problem with dbx and libthread, define NODEVINFO
 * to 'comment out' code references to functions in libdevinfo,
 * which is threaded.
 */
int
SystemConfigProm(void)
{
	int 	vip;
	int 	auth;
	char	disk[MAXPATHLEN];
	int	dev_specifier;
	char	dev_type;
	char	buf[MAXNAMELEN];
	int	retcode;

	/* see if the system is capable of being updated */
	if (BootobjGetAttribute(CFG_CURRENT,
			BOOTOBJ_PROM_UPDATEABLE,	&vip,
			BOOTOBJ_PROM_UPDATE,		&auth,
	    NULL) != D_OK || vip == 0 || auth == 0)
		return (NOERR);

	/* compare old and new boot disk and device values */
	if (BootobjCompare(CFG_CURRENT, CFG_EXIST, 1) != D_OK) {
		if (vip == 1 && auth == 1) {
			write_status(LOGSCR, LEVEL1|LISTITEM,
				MSG0_BOOT_FIRMWARE_UPDATE);
			if (!GetSimulation(SIM_EXECUTE) &&
					!GetSimulation(SIM_SYSDISK)) {

				if (BootobjGetAttribute(CFG_CURRENT,
						BOOTOBJ_DISK, disk,
						BOOTOBJ_DEVICE, &dev_specifier,
						BOOTOBJ_DEVICE_TYPE, &dev_type,
						NULL) != D_OK ||
						dev_specifier < 0 ||
						streq(disk, ""))
					return (ERROR);

				/*
				 * create the boot device specification for
				 * the DDI interface routine
				 */
				(void) sprintf(buf, "/dev/dsk/%s%c%d",
				    disk, dev_type, dev_specifier);
#ifndef NODEVINFO
				if ((retcode = devfs_bootdev_set_list(buf,
						0)) != 0) {
					/*
					 * if by prepending we will exceed the
					 * prom limits then attempt to
					 * overwrite boot dev
					 */

					if (retcode != DEVFS_LIMIT ||
						    (retcode == DEVFS_LIMIT &&
						    devfs_bootdev_set_list(buf,
						    BOOTDEV_OVERWRITE) != 0))
						return (ERROR);
				}
#endif
			}
		}
	}

	return (NOERR);
}

/*
 * Function:	_unconfigure_system
 * Description:	The master was archived as-is.  As such, the archive
 *		contains a good deal of information specific to the
 *		master - /etc/hosts files and such being a prime example.
 *		We don't want to do a sys-unconfig prior to or during the
 *		archive process, because we want to at some future point
 *		allow for restoration of the master through Flash.  As
 *		such, we need those files in the archive.
 *
 *		When we're cloning the master onto a different system, we
 *		want the master-specific files to go away.  We do that here.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	System unconfigured correctly
 *		ERROR	An error occurred during unconfiguration
 */
int
_unconfigure_system(void)
{
	char *cmd;
	char path[MAXPATHLEN + 23];
	int pathlen;

	if (GetSimulation(SIM_EXECUTE)) {
		return (NOERR);
	}

	/*
	 * cmd = [OSPATH]/usr/sbin/sys-unconfig -R [TARGETPATH]\0
	 */
	pathlen = strlen(get_osdir()) + strlen(SYS_UNCONFIG) + 4 +
	    strlen(get_rootdir()) + 1;

	cmd = (char *)xcalloc(pathlen * sizeof (char));
	(void) snprintf(cmd, pathlen, "%s%s -R %s", get_osdir(),
	    SYS_UNCONFIG, get_rootdir());
	/* get rid of extra /'s */
	canoninplace(cmd);

	write_debug(SVC_DEBUG_L1(1),
	    "unconfiguring system using \"%s\"", cmd);

	if (system(cmd)) {
		free(cmd);
		return (ERROR);
	}

	/*
	 * Do some cleanup after sys-unconfig.  sys-unconfig saves some
	 * files (like /etc/hosts in /etc/hosts.saved) to allow the user
	 * to recover some info after the unconfig.  We don't want those
	 * files in this case, because we're installing the machine from
	 * scratch.
	 */
	(void) sprintf(path, "%s/etc/inet/hosts.saved", get_rootdir());
	(void) unlink(path);

	free(cmd);
	return (NOERR);
}

/*
 * Name:	_suppress_solstart
 * Description:	Touch the magic file that tells Solstart not to run its
 *		finish script(s).  Among other things, this suppresses
 *		patch addition - something that's not appropriate for a
 *		Flash install.
 * Scope:	internal
 * Parameters:	none
 * Return:	NOERR	File created successfully
 *		ERROR	Unable to create suppression file
 */
int
_suppress_solstart(void)
{
	FILE *fp;

	if (!(fp = fopen(SUPPRESS_SOLSTART_FINISH_FILE, "w"))) {
		return (ERROR);
	}

	(void) fclose(fp);

	return (NOERR);
}

/* ---------------------- private functions ----------------------- */

#define	MAXLINE	2048	/* maximum expected line length */
/*
 * Function:	get_bootpath
 * Description: returns NULL if the bootpath cannot be determined,
 *		otherwise returns the right-hand-side of the line
 *		for the file /boot/solaris/bootenv.rc
 *		that reads:
 *
 *			setprop bootpath RHS
 *
 *		NOTE: "bootpath" does not have a dash in it!
 */
static char *
get_bootpath(char *disk, int slice)
{
	static char outline[MAXLINE];
	static char linktok[] = "../../devices";
	char in_line[MAXLINE];
	char linkline[MAXLINE];
	int len;

	(void) sprintf(in_line, "/dev/dsk/%ss%d", disk, slice);
	if ((len = readlink(in_line, linkline, MAXLINE)) < 0 ||
	    strncmp(linkline, linktok, strlen(linktok)) != 0)
		/* Can't see the other side of the link - fail */
		return (NULL);

	linkline[len] = '\0'; /* readlink doesn't null-terminate */
	(void) strcpy(outline, linkline + strlen(linktok));
	return (outline);
}

/*
 * Function:	parse_transtype
 * Description: parse the transtype information from "transtype" string
 *		and place it into a newly allocated TransType object.
 * Scope:	Private
 * Return:	0 -	Success
 *		1 -	Failure
 */
static int
parse_transtype(TransType **tt, char *transtype)
{
	int ret_val = 0;
	char *type = NULL;
	char *mergescript = NULL;

	(*tt) = (TransType *) xmalloc(sizeof (TransType));
	(*tt)->mergescript = NULL;

	if ((type = strtok(transtype, ":")) == NULL) {
		return (1);
	}

	if (streq(type, OVERWRITE_STR)) {
		(*tt)->type = TTYPE_OVERWRITE;
		(*tt)->mergescript = NULL;
		ret_val = 0;
	} else if (streq(type, REPLACE_STR)) {
		(*tt)->type = TTYPE_REPLACE;
		(*tt)->mergescript = NULL;
		ret_val = 0;
	} else if (streq(type, MERGE_STR)) {
		(*tt)->type = TTYPE_MERGE;
		mergescript = strtok(NULL, ":");
		if (mergescript) {
			(*tt)->mergescript = (char *)xstrdup(mergescript);
			ret_val = 0;
		} else {
			ret_val = 1;
		}
	} else {
		ret_val = 1;
	}

	if (ret_val != 0)
		if ((*tt))
			free((*tt));

	return (ret_val);
}

/*
 * Function:	link_file
 * Description: Remove existing aFile and read link file of tmpFile.
 *		Make same link file to aFile. So that both tmpFile and aFile
 *		points to same file in different directories.
 *
 * Scope:	Private
 * Return:	0 -	Success
 *		1 -	Failure
 */
static int
link_file(char *tmpfile, char *afile)
{
	char file_buf[MAXPATHLEN];

	/* Remove existing afile */
	(void) remove(afile);

	/* Read link of tmpfile */
	if (readlink(tmpfile, file_buf, MAXPATHLEN) == -1)
		return (1);

	/* Make same link file(file_buf) to afile */
	if (symlink(file_buf, afile) == -1)
		return (1);

	return (0);
}

/*
 * Function:  write_bootblocks
 * Description: Execute installgrub in the case of X86 or installboot
 *            if it is sparc
 *
 * Scope:     Private
 * Return:    0 -     Success
 *            1 -     Failure
 */
static int
write_bootblocks(char *rootpath)
{
	char    *rootdir = get_rootdir();
	char    *bootblk_path;

	if (streq(get_default_inst(), "i386")) {
		(void) sprintf(cmd,
		    "/sbin/installgrub /boot/grub/stage1 /boot/grub/stage2 %s"
		    " > /dev/null",
		    rootpath);
	} else {
		if ((bootblk_path = gen_bootblk_path(rootdir)) == NULL &&
		    (DIRECT_INSTALL || (bootblk_path =
		    gen_bootblk_path("/")) == NULL)) {
			write_notice(ERRMSG, MSG0_BOOT_BLOCK_NOTEXIST);
			return (ERROR);
		}

		(void) sprintf(cmd,
		    "/usr/sbin/installboot %s %s",
		    bootblk_path,
		    rootpath);
	}

	if (system(cmd) != 0) {
		write_notice(ERRMSG, MSG0_INSTALLBOOT_FAILED);
		return (ERROR);
	}
	return (NOERR);
}
