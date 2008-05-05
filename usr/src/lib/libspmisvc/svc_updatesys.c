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



#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <libgen.h>
#include <sys/mntent.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/vfstab.h>
#include "spmisvc_lib.h"
#include "spmicommon_api.h"
#include "spmistore_lib.h"
#include "spmiapp_lib.h"
#include "spmizones_lib.h"
#include "svc_strings.h"

#define	RECONFIGURE_FILE	"/reconfigure"

/* Fix for 4358804 */
#define	TARBOOT			"/tmp/.stubboot.tar"
#define	TMPROOTETC		"/tmp/root/etc"

void 		_preserve_slashboot(Vfsent *);
void		_restore_slashboot(Vfsent *);
int		_slash_boot_is_mounted(Vfsent *);

/* public prototypes */

TSUError	SystemUpdate(TSUData *SUData);
char		*SUGetErrorText(TSUError);
int		SetupTransList(void);

/* private prototypes */
static char	*_make_root(char *, char *);
static int	_force_reconfiguration_boot(void);
static TSUError	SUInstall(TSUInstallData *);
static TSUError SUFlashInstall(TSUInstallData *);
static TSUError SUFlashUpdate(TSUInstallData *);
static TSUError	SUUpgrade(OpType, TSUUpgradeData *);
static TSUError	SUUpgradeAdaptive(TSUUpgradeAdaptiveData *);
static TSUError	SUUpgradeRecover(TSUUpgradeRecoveryData *);
static int another_media_needed();

/* external prototypes */

/* static variables */

static TransList	*trans = NULL;

static char	flash_dir[PATH_MAX];
static char	flash_root[PATH_MAX];
static char	flash_type[PATH_MAX];
static char	flash_archive[PATH_MAX];
static char	flash_date[PATH_MAX];
static char	flash_master[PATH_MAX];
static char	flash_name[PATH_MAX];

/* ---------------------- public functions ----------------------- */

/*
 * *********************************************************************
 * FUNCTION NAME: SystemUpdate
 *
 * DESCRIPTION:
 *  This function is responsible for actually manipulating the system
 *  resources achieve the desired configuration.  This function has four
 *  distinct modes, Initial Install, Upgrade, Adaptive Upgrade and
 *  Upgrade recovery.  For each of these modes the calling application
 *  provides callbacks to keep the calling application informed of the
 *  progress of the processing.
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUData *			A pointer to the SystemUpdate data structure.
 *				The Operation field of this structure dictates
 *				how this function will behave.  Based on the
 *				value for the Operation, the appropriate union
 *				must be populated.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

TSUError
SystemUpdate(TSUData *SUData)
{
	TSUError	SUError;
	char		*msg = (char *)NULL;

	switch (SUData->Operation) {
	    case SI_INITIAL_INSTALL:
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_INITIAL_INSTALL);

		/*
		 * Process an initial install
		 */
		if ((SUError = SUInstall(&SUData->Info.Install)) != SUSuccess)
			return (SUError);

		/*
		 * Print message indicating system modification is complete
		 */
		if (another_media_needed() == 0) {
			msg = MSG0_SU_INITIAL_INSTALL_COMPLETE;
		} else {
			msg = MSG0_SU_INIT_CD1OF2_INSTALL_COMPLETE_WEB;
		}
		write_status(SCR, LEVEL0, msg);
		break;

	    case SI_FLASH_INSTALL:
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_FLASH_INSTALL);

		/*
		 * Process a flash install
		 */
		if ((SUError = SUFlashInstall(&SUData->Info.Install)) !=
		    SUSuccess)
			return (SUError);

		/*
		 * Print message indicating system modification is complete
		 */
		write_status(SCR, LEVEL0, MSG0_SU_FLASH_INSTALL_COMPLETE);
		break;

	    case SI_FLASH_UPDATE:
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_FLASH_UPDATE);

		/*
		 * Process a flash update
		 */

		if ((SUError = SUFlashUpdate(&SUData->Info.Install)) !=
		    SUSuccess)
			return (SUError);

		/*
		 * Print message indicating system modification is complete
		 */
		write_status(SCR, LEVEL0, MSG0_SU_FLASH_UPDATE_COMPLETE);
		break;

	    case SI_UPGRADE:	/* normal (non-adaptive) upgrade */
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_UPGRADE);

		/*
		 * Process a standard upgrade
		 */
		if ((SUError = SUUpgrade(SI_UPGRADE,
		    &SUData->Info.Upgrade)) != SUSuccess) {
			return (SUError);
		}

		/*
		 * Print message indicating system modification is complete
		 */

		if (another_media_needed() == 0) {
			msg = MSG0_SU_UPGRADE_COMPLETE;
		} else {
			msg = MSG0_SU_UPGRADE_CD1OF2_COMPLETE_WEB;
		}
		write_status(SCR, LEVEL0, msg);
		break;

	    case SI_ADAPTIVE:	/* adaptive upgrade */
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_UPGRADE);

		/*
		 * Process an adaptive upgrade
		 */
		if ((SUError =
		    SUUpgradeAdaptive(&SUData->Info.AdaptiveUpgrade)) !=
		    SUSuccess) {
			return (SUError);
		}

		/*
		 * Print message indicating system modification is complete
		 */
		write_status(SCR, LEVEL0, MSG0_SU_UPGRADE_COMPLETE);
		break;

	    case SI_RECOVERY:	/* recovering from a previous */
		/*
		 * Print message indicating system preparation beginning
		 */
		write_status(SCR, LEVEL0, MSG0_SU_UPGRADE);

		/*
		 * Process an upgrade recovery
		 */
		if ((SUError =
		    SUUpgradeRecover(&SUData->Info.UpgradeRecovery)) !=
		    SUSuccess) {
			return (SUError);
		}

		/*
		 * Print message indicating system modification is complete
		 */
		write_status(SCR, LEVEL0, MSG0_SU_UPGRADE_COMPLETE);
		break;

	    default:	/* Don't know what it is, punt */
		write_notice(ERRMSG, SUGetErrorText(SUInvalidOperation));
		return (SUInvalidOperation);
	}

	/* sync out the disks (precautionary) */
	sync();

	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUGetErrorText
 *
 * DESCRIPTION:
 *  This function converts the given error code into an
 *  internationalized human readable string.
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  char *			The internationalized error string
 *				corresponding to the provided error
 *				code.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUError			The error code to convert.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

char *
SUGetErrorText(TSUError SUError)
{
	switch (SUError) {
	case SUSuccess:
		return (MSG0_SU_SUCCESS);
	case SUInvalidOperation:
		return (MSG0_SU_INVALID_OPERATION);
	case SUResetStateError:
		return (MSG0_SU_STATE_RESET_FAILED);
	case SUCreateMountListError:
		return (MSG0_SU_MNTPNT_LIST_FAILED);
	case SUSetupDisksError:
		return (MSG0_SU_SETUP_DISKS_FAILED);
	case SUMountFilesysError:
		return (MSG0_SU_MOUNT_FILESYS_FAILED);
	case SUMountZonesError:
		return (MSG0_SU_MOUNT_ZONES_FAILED);
	case SUSetupSoftwareError:
		return (MSG0_SU_PKG_INSTALL_TOTALFAIL);
	case SUExtractArchiveError:
		return (MSG0_SU_ARCHIVE_EXTRACT_FAILED);
	case SUSetupVFSTabError:
		return (MSG0_SU_VFSTAB_CREATE_FAILED);
	case SUSetupVFSTabUnselectedError:
		return (MSG0_SU_VFSTAB_UNSELECTED_FAILED);
	case SUSetupHostsError:
		return (MSG0_SU_HOST_CREATE_FAILED);
	case SUSetupHostIDError:
		return (MSG0_SU_SERIAL_VALIDATE_FAILED);
	case SUSetupDevicesError:
		return (MSG0_SU_SYS_DEVICES_FAILED);
	case SUUpdateDefaultInitError:
		return (MSG0_SU_DEFAULT_INIT_UPDATE_FAILED);
	case SUReconfigurationBootError:
		return (MSG0_SU_SYS_RECONFIG_BOOT_FAILED);
	case SUSetupBootBlockError:
		return (MSG0_SU_BOOT_BLOCK_FAILED);
	case SUSetupBootPromError:
		return (MSG0_SU_PROM_UPDATE_FAILED);
	case SUUpgradeScriptError:
		return (MSG0_SU_UPGRADE_SCRIPT_FAILED);
	case SUDiskListError:
		return (MSG0_SU_DISKLIST_READ_FAILED);
	case SUDSRALCreateError:
		return (MSG0_SU_DSRAL_CREATE_FAILED);
	case SUDSRALArchiveBackupError:
		return (MSG0_SU_DSRAL_ARCHIVE_BACKUP_FAILED);
	case SUDSRALArchiveRestoreError:
		return (MSG0_SU_DSRAL_ARCHIVE_RESTORE_FAILED);
	case SUDSRALDestroyError:
		return (MSG0_SU_DSRAL_DESTROY_FAILED);
	case SUUnmountError:
		return (MSG0_SU_UNMOUNT_FAILED);
	case SUFileCopyError:
		return (MSG0_SU_FILE_COPY_FAILED);
	case SUCleanDevicesError:
		return (MSG0_SU_CLEAN_DEVICES_FAILED);
	case SUUnconfigureSystemError:
		return (MSG0_SU_UNCONFIGURE_FAILED);
	case SUPredeploymentError:
		return (MSG0_SU_PREDEPLOYMENT_FAILED);
	case SUCloneValidationError:
		return (MSG0_SU_CLONE_VALIDATION_FAILED);
	case SUMasterValidationError:
		return (MSG0_SU_MASTER_VALIDATION_FAILED);
	case SUFatalError:
		return (MSG0_SU_FATAL_ERROR);
	case SUPostdeploymentError:
		return (MSG0_SU_POSTDEPLOYMENT_FAILED);
	default:
		return (MSG0_SU_UNKNOWN_ERROR_CODE);
	}
}

/* ---------------------- private functions ----------------------- */

static int another_media_needed() {

	FILE *fp;

	char *path = xmalloc(strlen(get_rootdir()) + 2 +
		strlen("%s/var/sadm/system/data/packages_to_be_added"));
	(void) sprintf(path, "%s/var/sadm/system/data/packages_to_be_added",
		get_rootdir());
	if ((fp = fopen(path, "r")) == NULL) {
		return (0);
	}
	(void) fclose(fp);
	return (1);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUInstall
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUInstallData *		A pointer to the Initial Install data
 *				structure.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

static TSUError
SUInstall(TSUInstallData *Data)
{
	char		cmd[MAXPATHLEN];
	Vfsent		*vlist = NULL;
	MachineType	mt = get_machinetype();
	Disk_t		*dlist = first_disk();
	char		*logFileName;

	/*
	 * cleanup from possible previous install attempts for
	 * all install processes which could be restarted
	 */

	if (INDIRECT_INSTALL) {
		/*
		 * nodiskops means we don't deal with swap either,
		 * so don't reset_system_state in this case, or else
		 * we would lose any currently-running swap.
		 */
		if (!Data->flags.nodiskops) {
			if (reset_system_state() < 0) {
				write_notice(ERRMSG,
				    SUGetErrorText(SUResetStateError));
				return (SUResetStateError);
			}
		} else {
			if (UmountAllZones(get_rootdir()) != 0 ||
			    DirUmountAll(get_rootdir()) < 0) {
				return (-1);
			}
		}
	}

	/*
	 * create a list of local and remote mount points
	 */

	/* delete stubboot from CFG_CURRENT so it doesn't show */
	(void) BootobjSetAttributePriv(CFG_CURRENT,
	    BOOTOBJ_STUBBOOT_DISK, NULL,
	    NULL);

	if (_create_mount_list(dlist,
		Data->cfs,
		&vlist) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUCreateMountListError));
		return (SUCreateMountListError);
	}

	/*
	 * update the F-disk and VTOC on all selected disks
	 * according to the disk list configuration; start
	 * swapping to defined disk swap slices.  If this is
	 * a flash install, newfs and mount ALL filesystems synchronously,
	 * regardless of their importance to the system.
	 *
	 * if we are in nodiskops mode, this will avoid writing out
	 * VTOCs and/or labelling disks.
	 */

	if (_setup_disks(dlist, vlist, Data->flags.nodiskops,
	    Data->type == SI_FLASH_INSTALL) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupDisksError));
		return (SUSetupDisksError);
	}

	/*
	 * Execute the script to create SVM mirror volumes before installing
	 * packages
	 */
	if (access(MIRROR_CREATION_SCRIPT, R_OK|X_OK) == 0) {
		write_status(LOGSCR, LEVEL0, MSG0_CREATE_SVM_METADEVICES);
		if (execute_mirror_script(MIRROR_CREATION_SCRIPT,
				MIRROR_CREATION_LOG) == ERROR) {
			write_notice(ERRMSG,
				SUGetErrorText(SUMirrorSetupError));
			return (SUMirrorSetupError);
		}
	}

	/*
	 * create mount points on the target system according
	 * to the mount list; note that the target file systems
	 * may be offset of a base directory if the installation
	 * is indirect.
	 */

	if (_mount_filesys_all(SI_INITIAL_INSTALL, vlist,
	    Data->type == SI_FLASH_INSTALL) != NOERR) {
		write_notice(ERRMSG, SUGetErrorText(SUMountFilesysError));
		return (SUMountFilesysError);
	}

	/*
	 * lock critical applications in memory for performance
	 */

	(void) _lock_prog("/usr/sbin/pkgadd");
	(void) _lock_prog("/usr/sadm/install/bin/pkginstall");
	(void) _lock_prog("/usr/bin/cpio");

	/*
	 * Read the transfer list
	 * if it hasn't been read already.
	 */
	if ((trans == NULL) && !(Data->flags.notransfer) &&
	    (get_machinetype() != MT_CCLIENT)) {
		/* Read in the transferlist of files */
		if (_setup_transferlist(&trans) == ERROR) {
			write_notice(ERRMSG, MSG0_TRANS_SETUP_FAILED);
			return (ERROR);
		}
	}

	/* Install the requested packages */
	if (_setup_software(Data->data.Initial.prod,
	    &trans,
	    Data->Callback,
	    Data->ApplicationData) == ERROR) {
		write_notice(ERRMSG,
		    SUGetErrorText(SUSetupSoftwareError));
		return (SUSetupSoftwareError);
	}

	write_status(LOGSCR, LEVEL0, MSG0_SU_FILES_CUSTOMIZE);

	if (!Data->flags.nodiskops) {
		/*
		 * write out the 'etc/vfstab' file to the appropriate
		 * location.  This is a writeable system file (affects
		 * location wrt indirect installs)
		 */
		if (_setup_vfstab(Data->type, &vlist) == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupVFSTabError));
			return (SUSetupVFSTabError);
		}

		/*
		 * write out the vfstab.unselected file to the appropriate
		 * location (if unselected disks with file systems exist)
		 */

		if (_setup_vfstab_unselect() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupVFSTabUnselectedError));
			return (SUSetupVFSTabUnselectedError);
		}
	}

	/*
	 * set up the etc/hosts file. This is a writeable system
	 * file (affects location wrt indirect installs)
	 */

	if (_setup_etc_hosts(Data->cfs) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupHostsError));
		return (SUSetupHostsError);
	}

	/*
	 * initialize serial number if there isn't one supported on the
	 * target architecture
	 */

	if (_setup_hostid() == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupHostIDError));
		return (SUSetupHostIDError);
	}

	/*
	 * Copy information from tmp/root to real root, using the
	 * transfer file list. From this point on, all modifications
	 * to the system will have to write directly to the /a/<*>
	 * directories. (if applicable)
	 */

	if (!Data->flags.notransfer) {
		if (_setup_tmp_root(&trans) == ERROR) {
			write_notice(ERRMSG, SUGetErrorText(SUFileCopyError));
			return (SUFileCopyError);
		}

		/*
		 * update the etc/default/init file with the selected default
		 * system locale.  We do this after items on the transfer list
		 * have been copied over so that our modifications don't get
		 * blown away by the transfer list copyover.
		 */
		if (_update_etc_default_init() == ERROR) {
			write_notice(ERRMSG,
				SUGetErrorText(SUUpdateDefaultInitError));
			return (SUUpdateDefaultInitError);
		}
	} else {
		/* skip the actual transferring of files */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		    DEBUG_LOC, LEVEL1,
		    "SUInstall: skipping transfer list processing");
	}

	/*
	 * setup /dev, /devices, and /reconfigure
	 */
	if (!Data->flags.noreconfigure) {

		/*
		 * We need to clean the device tree before we
		 * can rebuild it.  The master may have had a
		 * wildly different device configuration than
		 * we do.
		 */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		    DEBUG_LOC, LEVEL1,
		    "SUInstall: doing device reconfiguration");
		if (_clean_devices() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUCleanDevicesError));
			return (SUCleanDevicesError);
		}

		/*
		 * during nodiskops mode, we don't want to reconfigure
		 * devices since we don't "own" the disks or have the
		 * right tools (think Live Upgrade)
		 */
		if ((!Data->flags.nodiskops) && (_setup_devices() == ERROR)) {
		    write_notice(ERRMSG, SUGetErrorText(SUSetupDevicesError));
		    return (SUSetupDevicesError);
		}
	} else {
		/*
		 * skip the device reconfiguration, but still force
		 * a reconfiguration boot.
		 */
	    write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		DEBUG_LOC, LEVEL1,
		"SUInstall: skipping device reconfiguration");
	    if (!_force_reconfiguration_boot()) {
		write_notice(ERRMSG,
		    SUGetErrorText(SUReconfigurationBootError));
		return (SUReconfigurationBootError);
	    }
	}

	/*
	 * set up boot block
	 */
	if (!Data->flags.nodiskops) {
		if (_setup_bootblock() != NOERR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupBootBlockError));
			return (SUSetupBootBlockError);
		}

		/*
		 * update the booting PROM if necessary; if the update
		 * fails, print a warning and update the boot object
		 * updateability fields for all states
		 */
		if (SystemConfigProm() != NOERR) {
			write_notice(WARNMSG,
			    SUGetErrorText(SUSetupBootPromError));
			(void) BootobjSetAttributePriv(CFG_CURRENT,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
			(void) BootobjSetAttributePriv(CFG_COMMIT,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
			(void) BootobjSetAttributePriv(CFG_EXIST,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
		}
	}

	/*
	 * Copy the log file from /tmp to the target filesystem
	 */

	logFileName = _setup_install_log();

	/*
	 * Complete installation, including applying 3rd party driver
	 * installation to target OS.
	 */

	if (!GetSimulation(SIM_EXECUTE) && !Data->flags.nodiskops) {
		if (IsIsa("i386")) {
			(void) snprintf(cmd, sizeof (cmd),
			    "/sbin/install-finish %s initial_install "
			    ">> %s 2>&1", get_rootdir(),
			    logFileName ? logFileName : "/dev/null");
			(void) system(cmd);
		}
	}

	/*
	 * Write log file locations before and after install.
	 */

	if (logFileName) {
		write_status(SCR, LEVEL0, MSG0_INSTALL_LOG_LOCATION);
		if (INDIRECT_INSTALL) {
			write_status(SCR, LEVEL1|LISTITEM,
			    MSG1_INSTALL_LOG_BEFORE, logFileName);
		}
		write_status(SCR, LEVEL1|LISTITEM, MSG1_INSTALL_LOG_AFTER,
		    logFileName+strlen(get_rootdir()));
	}

	/*
	 * wait for newfs's and fsck's to complete.  If this is
	 * a flash install, there were no backgrounded newfs's and fsck's,
	 * so we don't have to do this.
	 */
	if (!GetSimulation(SIM_EXECUTE)) {
		while (ProcWalk(ProcIsRunning, "newfs") == 1 ||
			ProcWalk(ProcIsRunning, "fsck") == 1)
			(void) sleep(5);
	}

	/*
	 * on non-AutoClient systems, finish mounting all file systems
	 * which were not previously mounted during install; this
	 * leaves the system correctly configured for a finish script
	 */

	if (mt != MT_CCLIENT) {
		if (GetSimulation(SIM_EXECUTE) || get_trace_level() > 1)
			write_status(SCR, LEVEL0, MSG0_SU_MOUNTING_TARGET);

		    if (_mount_remaining(vlist) != NOERR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUMountFilesysError));
			return (SUMountFilesysError);
		    }
	}

	/*
	 * cleanup
	 */

	_free_mount_list(&vlist);
	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUFlashInstall
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUInstallData *		A pointer to the Flash Install data
 *				structure.
 * *********************************************************************
 */

static TSUError
SUFlashInstall(TSUInstallData *Data)
{
	char		cmd[MAXPATHLEN];
	Vfsent		*vlist = NULL;
	Disk_t		*dlist = first_disk();
	char		*logFileName;
	char		altDstPath[MAXPATHLEN];
	int		i;
	int		fd;
	FLARProgress	prog;

	/*
	 * cleanup from possible previous install attempts for
	 * all install processes which could be restarted
	 */

	if (INDIRECT_INSTALL) {
		/*
		 * nodiskops means we don't deal with swap either,
		 * so don't reset_system_state in this case, or else
		 * we would lose any currently-running swap.
		 */
		if (!Data->flags.nodiskops) {
			if (reset_system_state() < 0) {
				write_notice(ERRMSG,
				    SUGetErrorText(SUResetStateError));
				return (SUResetStateError);
			}
		} else {
			if (UmountAllZones(get_rootdir()) != 0 ||
			    DirUmountAll(get_rootdir()) < 0) {
				return (-1);
			}
		}
	}

	/*
	 * create a list of local and remote mount points
	 */

	/* delete stubboot from CFG_CURRENT so it doesn't show */
	(void) BootobjSetAttributePriv(CFG_CURRENT,
		BOOTOBJ_STUBBOOT_DISK, NULL, NULL);

	if (_create_mount_list(dlist,
	    Data->cfs,
	    &vlist) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUCreateMountListError));
		return (SUCreateMountListError);
	}

	/*
	 * update the F-disk and VTOC on all selected disks
	 * according to the disk list configuration; start
	 * swapping to defined disk swap slices.  If this is
	 * a flash install, newfs and mount ALL filesystems synchronously,
	 * regardless of their importance to the system.
	 *
	 * if we are in nodiskops mode, this will avoid writing out
	 * VTOCs and/or labelling disks.
	 */
	if (_setup_disks(dlist, vlist, Data->flags.nodiskops,
	    Data->type == SI_FLASH_INSTALL) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupDisksError));
		return (SUSetupDisksError);
	}

	/*
	 * Execute the script to create SVM mirror volumes before installing
	 * software
	 */
	if (access(MIRROR_CREATION_SCRIPT, R_OK|X_OK) == 0) {
		write_status(LOGSCR, LEVEL0, MSG0_CREATE_SVM_METADEVICES);
		if (execute_mirror_script(MIRROR_CREATION_SCRIPT,
				MIRROR_CREATION_LOG) == ERROR) {
			write_notice(ERRMSG,
				SUGetErrorText(SUMirrorSetupError));
			return (SUMirrorSetupError);
		}
	}

	/*
	 * create mount points on the target system according
	 * to the mount list; note that the target file systems
	 * may be offset of a base directory if the installation
	 * is indirect.
	 */

	if (_mount_filesys_all(SI_INITIAL_INSTALL, vlist,
	    Data->type == SI_FLASH_INSTALL) != NOERR) {
		write_notice(ERRMSG, SUGetErrorText(SUMountFilesysError));
		return (SUMountFilesysError);
	}

	/*
	 * lock critical applications in memory for performance
	 */

	(void) _lock_prog("/usr/bin/cpio");

	/*
	 * Read the transfer list
	 * if it hasn't been read already.
	 */
	if ((trans == NULL) && !(Data->flags.notransfer) &&
	    (get_machinetype() != MT_CCLIENT)) {
		/* Read in the transferlist of files */
		if (_setup_transferlist(&trans) == ERROR) {
			write_notice(ERRMSG, MSG0_TRANS_SETUP_FAILED);
			return (ERROR);
		}
	}

	write_status(LOGSCR, LEVEL0, MSG0_FLASH_INSTALL_BEGIN);

	/*
	 * store atconfig for safe keeping
	 */
	if (_atconfig_store() != NOERR) {
	    write_notice(ERRMSG,
		SUGetErrorText(SUExtractArchiveError));
	    return (ERROR);
	}

	/* Extract the Flash archives */
	prog.type = FLARPROGRESS_STATUS_BEGIN;
	Data->Callback(Data->ApplicationData, (void *)&prog);

	/* set environment for deployment scripts */

	(void) snprintf(flash_root, sizeof (flash_root), "FLASH_ROOT=%s",
	    get_rootdir());
	(void) putenv(flash_root);
	(void) snprintf(flash_dir,  sizeof (flash_dir),
	    "FLASH_DIR=%s/tmp/flash_tmp", get_rootdir());
	(void) putenv(flash_dir);
	(void) snprintf(flash_type,  sizeof (flash_type), "FLASH_TYPE=FULL");
	(void) putenv(flash_type);

	for (i = 0; i < Data->data.Flash.num_archives; i++) {
		prog.type = FLARPROGRESS_STATUS_BEGIN_ARCHIVE;
		prog.data.current_archive.flar =
		    &Data->data.Flash.archives[i];
		Data->Callback(Data->ApplicationData, (void *)&prog);

		/* set environment for deployment scripts */

		(void) snprintf(flash_archive, sizeof (flash_archive),
		    "FLASH_ARCHIVE=%s",
		    FLARArchiveWhere(&(Data->data.Flash.archives[i])));
		(void) putenv(flash_archive);
		(void) snprintf(flash_date, sizeof (flash_date),
		    "FLASH_DATE=%s",
		    Data->data.Flash.archives[i].ident.cr_date_str);
		(void) putenv(flash_date);
		(void) snprintf(flash_master, sizeof (flash_master),
		    "FLASH_MASTER=%s",
		    Data->data.Flash.archives[i].ident.cr_master);
		(void) putenv(flash_master);
		(void) snprintf(flash_name, sizeof (flash_name),
		    "FLASH_NAME=%s",
		    Data->data.Flash.archives[i].ident.cont_name);
		(void) putenv(flash_name);

		/*
		 * Preinstall processing
		 */

		if (FLARInitialPreDeployment(&(Data->data.Flash.archives[i]),
			Data->flags.local_customization) != FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUPredeploymentError));
			return (SUPredeploymentError);
		}

		/*
		 * extract the bits
		 */

		if (FLARExtractArchive(&(Data->data.Flash.archives[i]),
		    Data->Callback,
		    Data->ApplicationData) != FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUExtractArchiveError));

			return (SUExtractArchiveError);
		}

		if (FLARPostDeployment(&(Data->data.Flash.archives[i]),
			Data->flags.local_customization) != FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUPostdeploymentError));
			return (SUPostdeploymentError);
		}

		/*
		 * restore atconfig file if necessary
		 */
		if (_atconfig_restore() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUExtractArchiveError));
			return (ERROR);
		}

		prog.type = FLARPROGRESS_STATUS_END_ARCHIVE;
		Data->Callback(Data->ApplicationData, (void *)&prog);
	}
	prog.type = FLARPROGRESS_STATUS_END;
	Data->Callback(Data->ApplicationData, (void *)&prog);

	if (!Data->flags.notransfer) {

		/* Unconfigure the system */
		if (get_trace_level() > 2) {
			write_status(LOGSCR, LEVEL0,
			    MSG0_UNCONFIGURING_SYSTEM);
		}

		if (_unconfigure_system() != SUCCESS) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUUnconfigureSystemError));
			return (SUUnconfigureSystemError);
		}
	}

	write_status(LOGSCR, LEVEL0, MSG0_SU_FILES_CUSTOMIZE);

	if (!Data->flags.nodiskops || Data->flags.lu_flag) {

		/*
		 * The code below tries to create /tmp/root/etc/vfstab
		 * file. This is required because of the way that pfinstall
		 * handles flash installation from liveupgrade. Incase
		 * if the directory structures are not created, they are
		 * created prior to creating the file itself. Code will
		 * be executed only if call is from liveupgrade.
		 */

		if (Data->flags.nodiskops && Data->flags.lu_flag) {

			(void) snprintf(altDstPath, sizeof (altDstPath),
				"%s/%s", TMPROOTETC, "vfstab");


			if ((fd = open(altDstPath, O_WRONLY | O_TRUNC | O_CREAT,
				S_IRUSR|S_IWUSR| S_IRGRP | S_IROTH)) < 0 &&
				(errno == ENOENT)) {

				/*
				 * Target directory not present, so create it.
				 * create the directory structure like
				 * /tmp/root/etc.
				 */


				if (access(TMPROOTETC, F_OK) != 0) {

				/*
				 * Create the directory structures
				 * using mkdirp(3GEN)
				 */

					if (mkdirp(TMPROOTETC, 0755) != 0) {

						write_notice(ERRMSG,
						SUGetErrorText(
						SUCreateDirectoryError));
						return (SUCreateDirectoryError);
					} else {

						/*
						 * Directory structures created.
						 * Time to create the file.
						 */

						fd = open(altDstPath,
							O_WRONLY |
							O_TRUNC | O_CREAT,
							S_IRUSR | S_IWUSR |
							S_IRGRP | S_IROTH);
						if (fd < 0) {
							write_notice(ERRMSG,
							SUGetErrorText(
						SUCreateTemporaryFileError));
						return (
						SUCreateTemporaryFileError);
						}
					}

				}
			}

			if (fd == -1) {
				write_notice(ERRMSG,
					SUGetErrorText(
						SUCreateTemporaryFileError));
				return (SUCreateTemporaryFileError);

			} else {
				(void) close(fd);
			}


			/*
			 * Set the SYS_VFSTAB environment variable to
			 * "/tmp/root/etc/vfstab"
			 */

			(void) putenv("SYS_VFSTAB=/tmp/root/etc/vfstab");
		}


		/*
		 * write out the 'etc/vfstab' file to the appropriate
		 * location.  This is a writeable system file (affects
		 * location wrt indirect installs)
		 */
		if (_setup_vfstab(Data->type, &vlist) == ERROR) {
			write_notice(ERRMSG,
				SUGetErrorText(SUSetupVFSTabError));
			return (SUSetupVFSTabError);
		}

		/*
		 * write out the vfstab.unselected file to the appropriate
		 * location (if unselected disks with file systems exist)
		 */

		if (_setup_vfstab_unselect() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupVFSTabUnselectedError));
			return (SUSetupVFSTabUnselectedError);
		}

	}

	/*
	 * set up the etc/hosts file. This is a writeable system
	 * file (affects location wrt indirect installs)
	 */

	if (_setup_etc_hosts(Data->cfs) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupHostsError));
		return (SUSetupHostsError);
	}

	/*
	 * initialize serial number if there isn't one supported on the
	 * target architecture
	 */

	if (_setup_hostid() == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupHostIDError));
		return (SUSetupHostIDError);
	}

	/*
	 * Copy information from tmp/root to real root, using the
	 * transfer file list. From this point on, all modifications
	 * to the system will have to write directly to the /a/<*>
	 * directories. (if applicable)
	 */

	if (!Data->flags.notransfer) {

		if (Data->flags.nodiskops && Data->flags.lu_flag) {
			set_protodir(TMPROOTETC);
		}

		if (_setup_tmp_root(&trans) == ERROR) {
			write_notice(ERRMSG, SUGetErrorText(SUFileCopyError));
			return (SUFileCopyError);
		}

		/*
		 * update the etc/default/init file with the selected default
		 * system locale.  We do this after items on the transfer list
		 * have been copied over so that our modifications don't get
		 * blown away by the transfer list copyover.
		 */
		if (_update_etc_default_init() == ERROR) {
			write_notice(ERRMSG,
				SUGetErrorText(SUUpdateDefaultInitError));
			return (SUUpdateDefaultInitError);
		}
	} else {
		/* skip the actual transferring of files */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		    DEBUG_LOC, LEVEL1,
		    "SUInstall: skipping transfer list processing");
	}

	/*
	 * setup /dev, /devices, and /reconfigure
	 */
	if (!Data->flags.noreconfigure) {

		/*
		 * We need to clean the device tree before we
		 * can rebuild it.  The master may have had a
		 * wildly different device configuration than
		 * we do.
		 */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		    DEBUG_LOC, LEVEL1,
		    "SUInstall: doing device reconfiguration");
		if (_clean_devices() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUCleanDevicesError));
			return (SUCleanDevicesError);
		}

		/*
		 * during nodiskops mode, we don't want to reconfigure
		 * devices since we don't "own" the disks or have the
		 * right tools (think Live Upgrade)
		 */
		if ((!Data->flags.nodiskops) && (_setup_devices() == ERROR)) {
		    write_notice(ERRMSG, SUGetErrorText(SUSetupDevicesError));
		    return (SUSetupDevicesError);
		}

	} else {
		/*
		 * skip the device reconfiguration, but still force
		 * a reconfiguration boot.
		 */
	    write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		DEBUG_LOC, LEVEL1,
		"SUInstall: skipping device reconfiguration");
	    if (!_force_reconfiguration_boot()) {
		write_notice(ERRMSG,
		    SUGetErrorText(SUReconfigurationBootError));
		return (SUReconfigurationBootError);
	    }
	}

	/*
	 * set up boot block
	 */
	if (!Data->flags.nodiskops) {
		if (_setup_bootblock() != NOERR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupBootBlockError));
			return (SUSetupBootBlockError);
		}

		/*
		 * update the booting PROM if necessary; if the update
		 * fails, print a warning and update the boot object
		 * updateability fields for all states
		 */
		if (SystemConfigProm() != NOERR) {
			write_notice(WARNMSG,
			    SUGetErrorText(SUSetupBootPromError));
			(void) BootobjSetAttributePriv(CFG_CURRENT,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
			(void) BootobjSetAttributePriv(CFG_COMMIT,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
			(void) BootobjSetAttributePriv(CFG_EXIST,
			    BOOTOBJ_PROM_UPDATEABLE,  FALSE,
			    NULL);
		}
	}

	/*
	 * Copy the log file from /tmp to the target filesystem
	 */

	logFileName = _setup_install_log();

	/*
	 * Complete installation, including applying 3rd party driver
	 * installation to target OS.
	 */

	if (!GetSimulation(SIM_EXECUTE) && !Data->flags.nodiskops) {
		if (IsIsa("i386")) {
			(void) snprintf(cmd, sizeof (cmd),
			    "/sbin/install-finish %s flash_install >> %s 2>&1",
			    get_rootdir(),
			    logFileName ? logFileName : "/dev/null");
			(void) system(cmd);
		}
	}

	/*
	 * Write log file locations before and after install.
	 */

	if (logFileName) {
		write_status(SCR, LEVEL0, MSG0_INSTALL_LOG_LOCATION);
		if (INDIRECT_INSTALL) {
			write_status(SCR, LEVEL1|LISTITEM,
			    MSG1_INSTALL_LOG_BEFORE, logFileName);
		}

		write_status(SCR, LEVEL1|LISTITEM, MSG1_INSTALL_LOG_AFTER,
		    logFileName+strlen(get_rootdir()));
	}

	/*
	 * If this is a Flash install, touch a magic file in /tmp
	 * that tells Solstart not to run
	 */
	if (!Data->flags.nodiskops) {
		_suppress_solstart();
	}

	/*
	 * cleanup
	 */

	_free_mount_list(&vlist);
	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUFlashUpdate
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUInstallData *		A pointer to the Initial Install data
 *				structure.
 * *********************************************************************
 */

static TSUError
SUFlashUpdate(TSUInstallData *Data)
{
	Vfsent		*vlist = NULL;
	char		*logFileName;
	int		i;
	FLARProgress	prog;

	/*
	 * lock critical applications in memory for performance
	 */

	(void) _lock_prog("/usr/bin/cpio");

	write_status(LOGSCR, LEVEL0, MSG0_FLASH_INSTALL_BEGIN);

	/* Extract the Flash archives */

	prog.type = FLARPROGRESS_STATUS_BEGIN;
	Data->Callback(Data->ApplicationData, (void *)&prog);

	/* set environment for deployment scripts */

	(void) snprintf(flash_root, sizeof (flash_root), "FLASH_ROOT=%s",
	    get_rootdir());
	(void) putenv(flash_root);
	(void) snprintf(flash_dir,  sizeof (flash_dir),
	    "FLASH_DIR=%s/tmp/flash_tmp", get_rootdir());
	(void) putenv(flash_dir);
	(void) snprintf(flash_type, sizeof (flash_type),
	    "FLASH_TYPE=DIFFERENTIAL");
	(void) putenv(flash_type);

	for (i = 0; i < Data->data.Flash.num_archives; i++) {
		prog.type = FLARPROGRESS_STATUS_BEGIN_ARCHIVE;
		prog.data.current_archive.flar =
		    &Data->data.Flash.archives[i];
		Data->Callback(Data->ApplicationData, (void *)&prog);

		/* set environment for deployment scripts */
		(void) snprintf(flash_archive, sizeof (flash_archive),
		    "FLASH_ARCHIVE=%s",
		    FLARArchiveWhere(&(Data->data.Flash.archives[i])));
		(void) putenv(flash_archive);
		(void) snprintf(flash_date, sizeof (flash_date),
		    "FLASH_DATE=%s",
		    Data->data.Flash.archives[i].ident.cr_date_str);
		(void) putenv(flash_date);
		(void) snprintf(flash_master, sizeof (flash_master),
		    "FLASH_MASTER=%s",
		    Data->data.Flash.archives[i].ident.cr_master);
		(void) putenv(flash_master);
		(void) snprintf(flash_name, sizeof (flash_name),
		    "FLASH_NAME=%s",
		    Data->data.Flash.archives[i].ident.cont_name);
		(void) putenv(flash_name);

		/*
		 * Predeployment processing
		 */

		if (FLARUpdatePreDeployment(&(Data->data.Flash.archives[i]),
				Data->flags.local_customization,
				Data->flags.check_master,
				Data->flags.check_contents,
				Data->flags.forced_deployment) !=
			FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUPredeploymentError));
			return (SUPredeploymentError);
		}

		/*
		 * extract the bits
		 */

		if (FLARExtractArchive(&(Data->data.Flash.archives[i]),
		    Data->Callback,
		    Data->ApplicationData) != FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUExtractArchiveError));
			return (SUExtractArchiveError);
		}

		if (FLARPostDeployment(&(Data->data.Flash.archives[i]),
			Data->flags.local_customization) !=
			FlErrSuccess) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUPostdeploymentError));
			return (SUPostdeploymentError);
		}

		/*
		 * restore atconfig file if necessary
		 */
		if (_atconfig_restore() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUExtractArchiveError));
			return (ERROR);
		}

		prog.type = FLARPROGRESS_STATUS_END_ARCHIVE;
		Data->Callback(Data->ApplicationData, (void *)&prog);
	}
	prog.type = FLARPROGRESS_STATUS_END;
	Data->Callback(Data->ApplicationData, (void *)&prog);

	write_status(LOGSCR, LEVEL0, MSG0_SU_FILES_CUSTOMIZE);

	/*
	 * setup /dev, /devices, and /reconfigure
	 */
	if (!Data->flags.noreconfigure) {

		/*
		 * We need to clean the device tree before we
		 * can rebuild it.  The master may have had a
		 * wildly different device configuration than
		 * we do.
		 */
		write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		    DEBUG_LOC, LEVEL1,
		    "SUInstall: doing device reconfiguration");
		if (_clean_devices() == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUCleanDevicesError));
			return (SUCleanDevicesError);
		}

		/*
		 * during nodiskops mode, we don't want to reconfigure
		 * devices since we don't "own" the disks or have the
		 * right tools (think Live Upgrade)
		 */
		if ((!Data->flags.nodiskops) && (_setup_devices() == ERROR)) {
		    write_notice(ERRMSG, SUGetErrorText(SUSetupDevicesError));
		    return (SUSetupDevicesError);
		}
	} else {
		/*
		 * skip the device reconfiguration, but still force
		 * a reconfiguration boot.
		 */
	    write_debug(SCR, get_trace_level() > 3, "LIBSPMISVC",
		DEBUG_LOC, LEVEL1,
		"SUInstall: skipping device reconfiguration");
	    if (!_force_reconfiguration_boot()) {
		write_notice(ERRMSG,
		    SUGetErrorText(SUReconfigurationBootError));
		return (SUReconfigurationBootError);
	    }
	}

	/*
	 * 3rd party driver installation
	 *
	 * NOTE:	this needs to take 'bdir' as an argument
	 *		if it intends to write directly into the
	 *		installed image.
	 */

	if (!GetSimulation(SIM_EXECUTE) && !Data->flags.nodiskops) {
		if (access("/tmp/diskette_rc.d/icdinst9.sh", X_OK) == 0) {
			write_status(LOGSCR, LEVEL0, MSG0_SU_DRIVER_INSTALL);
			(void) system("/sbin/sh "
					"/tmp/diskette_rc.d/icdinst9.sh");
		} else if (access("/tmp/diskette_rc.d/inst9.sh", X_OK) == 0) {
			write_status(LOGSCR, LEVEL0, MSG0_SU_DRIVER_INSTALL);
			(void) system("/sbin/sh /tmp/diskette_rc.d/inst9.sh");
		}
	}

	/*
	 * Copy the log file from /tmp to the target filesystem
	 */

	if ((logFileName = _setup_install_log()) != NULL) {
		write_status(SCR, LEVEL0, MSG0_INSTALL_LOG_LOCATION);
		if (INDIRECT_INSTALL) {
			write_status(SCR, LEVEL1|LISTITEM,
			    MSG1_INSTALL_LOG_BEFORE, logFileName);
		}
		write_status(SCR, LEVEL1|LISTITEM, MSG1_INSTALL_LOG_AFTER,
		    logFileName+strlen(get_rootdir()));
	}

	/*
	 * If this is a Flash update, touch a magic file in /tmp
	 * that tells Solstart not to run
	 */
	if ((!Data->flags.nodiskops) && (Data->type == SI_FLASH_INSTALL)) {
		_suppress_solstart();
	}

	_free_mount_list(&vlist);
	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUUpgrade
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUUpgradeData *		A pointer to the Upgrade data structure.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

static TSUError
SUUpgrade(OpType Operation, TSUUpgradeData *Data)
{
	char	*logFileName;
	char	*cleanupFileName = "/var/sadm/system/data/upgrade_cleanup";

	/*
	 * If we are not running in simulation mode
	 */

	if (GetSimulation(SIM_EXECUTE)) {
		return (SUSuccess);
	}

	/*
	 * lock critical applications in memory for performance
	 */

	(void) _lock_prog("/usr/sbin/pkgadd");
	(void) _lock_prog("/usr/sadm/install/bin/pkginstall");
	(void) _lock_prog("/usr/bin/cpio");

	/*
	 * Move the log file from /tmp to the target filesystem
	 * Feed log file location to execute_upgrade so it knows where
	 * to send the upgrade_script output
	 */

	if ((logFileName = _setup_install_log()) == NULL) {
		/*
		 * Couldn't create the logfile - bummer
		 */
		write_notice(ERRMSG, SUGetErrorText(SUFileCopyError));
		return (SUFileCopyError);
	}

	if (execute_upgrade(Operation, logFileName,
	    Data->ScriptCallback,
	    Data->ScriptData)) {
		write_notice(ERRMSG, SUGetErrorText(SUUpgradeScriptError));
		return (SUUpgradeScriptError);
	}

	/*
	 * update the etc/default/init file with the selected default
	 * system locale.
	 */
	if (_update_etc_default_init() == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUUpdateDefaultInitError));
		return (SUUpdateDefaultInitError);
	}

	/*
	 * Tell user where the log file will be
	 */

	write_status(SCR, LEVEL0, MSG0_INSTALL_LOG_LOCATION);
	if (INDIRECT_INSTALL) {
		write_status(SCR, LEVEL1|LISTITEM,
		    MSG1_INSTALL_LOG_BEFORE, logFileName);
	}
	write_status(SCR, LEVEL1|LISTITEM, MSG1_INSTALL_LOG_AFTER,
	    logFileName+strlen(get_rootdir()));

	/*
	 * Tell the user where the upgrade_cleanup script is.
	 */

	write_status(SCR, LEVEL0, MSG0_CLEANUP_LOG_LOCATION);
	write_status(SCR, LEVEL1|LISTITEM, "%s%s",
	    (strcmp(get_rootdir(), "/") ? get_rootdir() : ""),
	    cleanupFileName);

	write_status(SCR, LEVEL0, MSG0_CLEANUP_LOG_MESSAGE);

	if (INDIRECT_INSTALL) {
		write_status(SCR, LEVEL1|LISTITEM, cleanupFileName);
	}

	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUUpgradeAdaptive
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUUpgradeAdaptiveData *	A pointer to the Adaptive Upgrade data
 *				structure.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

static TSUError
SUUpgradeAdaptive(TSUUpgradeAdaptiveData *Data)
{
	TSUUpgradeData	UpgradeData;

	Vfsent		*vlist = NULL;
	Disk_t		*dlist = first_disk();
	Disk_t		*dp;
	char		buf[MAXPATHLEN];

	TDSRArchiveList ArchiveList;
	TSUError	SUError;

	TDSRALError	DSRALError;

	/*
	 * If we are not running in simulation mode then we need to
	 * create an instance of the DSR archive list.
	 */

	if (!GetSimulation(SIM_EXECUTE)) {

		if ((DSRALError = DSRALCreate(&ArchiveList))) {
			write_notice(ERRMSG,
			    DSRALGetErrorText(DSRALError));
			write_notice(ERRMSG,
			    SUGetErrorText(SUDSRALCreateError));
			return (SUDSRALCreateError);
		}

		/*
		 * Backup the archive to the specified media
		 */

		if ((DSRALError = DSRALArchive(ArchiveList,
		    DSRALBackup,
		    Data->ArchiveCallback,
		    Data->ArchiveData))) {
			write_notice(ERRMSG,
			    DSRALGetErrorText(DSRALError));
			write_notice(ERRMSG,
			    SUGetErrorText(SUDSRALArchiveBackupError));
			return (SUDSRALArchiveBackupError);
		}
	}

	/*
	 * Read the Disk list from the backup file generated by the
	 * child process.
	 */

	if (ReadDiskList(&dlist)) {
		write_notice(ERRMSG, SUGetErrorText(SUDiskListError));
		return (SUDiskListError);
	}

	/*
	 * If tracing is enabled
	 */

	if (get_trace_level() > 2) {
		write_status(SCR, LEVEL0,
		    "Disk list read from child process");
		WALK_LIST(dp, dlist) {
			print_disk(dp, NULL);
		}
	}

	/*
	 * create a list of local and remote mount points
	 */

	if (_create_mount_list(dlist, NULL, &vlist) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUCreateMountListError));
		return (SUCreateMountListError);
	}

	/*
	 * If tracing is enabled then dump the mount list
	 */

	if (get_trace_level() > 2) {
		write_status(SCR, LEVEL0, "New entries for the vfstab");
		_mount_list_print(&vlist);
	}

	write_status(LOGSCR, LEVEL0, MSG0_SU_FILES_CUSTOMIZE);

	/*
	 * write out the 'etc/vfstab' file to the appropriate location
	 * This is a writeable system file (affects location wrt
	 * indirect installs)
	 */

	if (_setup_vfstab(SI_ADAPTIVE, &vlist) == ERROR) {
		write_notice(ERRMSG, SUGetErrorText(SUSetupVFSTabError));
		return (SUSetupVFSTabError);
	}

	/*
	 * If tracing is enabled then dump the mount list
	 */

	if (get_trace_level() > 2) {
		write_status(LOGSCR, LEVEL0, "The merged vfstab:");
		CatFile("/tmp/vfstab",
		    LOGSCR, STATMSG, LEVEL1);
	}

	/*
	 * If we are not running in simulation mode
	 */

	if (!GetSimulation(SIM_EXECUTE)) {

		/*
		 * Workaround for bugid 4358804
		 * x86 wouldn't boot after
		 * upgrade w/dsr and x86 boot exists.
		 * this will need to go away once
		 * DSR is fixed to handle partitions
		 * as well as slices
		 */
		_preserve_slashboot(vlist);
		/*
		 * Ok, the required files have been archived to
		 * the media so unmount the file systems in
		 * preperation for laying down the new file
		 * system layout.
		 */

		if (umount_and_delete_swap()) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUUnmountError));
			return (SUUnmountError);
		}

		/*
		 * update the F-disk and VTOC on all selected disks
		 * according to the disk list configuration; start
		 * swapping to defined disk swap slices
		 */

		if (_setup_disks(dlist, vlist, FALSE, FALSE) == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUSetupDisksError));
			return (SUSetupDisksError);
		}

		/*
		 * wait for newfs's and fsck's to complete
		 */

		if (!GetSimulation(SIM_EXECUTE)) {
			while (ProcWalk(ProcIsRunning, "newfs") == 1 ||
			    ProcWalk(ProcIsRunning, "fsck") == 1)
				(void) sleep(5);
		}

		/*
		 * Sort the vfstab list prior to mounting it to
		 * insure that parent gets mounted prior to a
		 * dependent child
		 */

		_mount_list_sort(&vlist);

		/*
		 * Mount all of the slices in the new file system.
		 */

		if (_mount_filesys_all(SI_ADAPTIVE, vlist, FALSE) !=
		    NOERR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUMountFilesysError));
			return (SUMountFilesysError);
		}
		/*
		 * Workaround for bugid 4358804
		 * x86 wouldn't boot after
		 * upgrade w/dsr and x86 boot exists.
		 * this will need to go away once
		 * DSR is fixed to handle partitions
		 * as well as slices
		 */
		_restore_slashboot(vlist);

		/*
		 * If we are in simulation mode or tracing is enabled
		 */

		if (GetSimulation(SIM_EXECUTE) || get_trace_level() > 1)
			write_status(SCR, LEVEL0, MSG0_SU_MOUNTING_TARGET);

		/*
		 * Mount all of the file systems that may have been
		 * newfs'd in the back ground.
		 */

		if (_mount_remaining(vlist) != NOERR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUMountFilesysError));
			return (SUMountFilesysError);
		}

		/*
		 * Check to see if the destination directory exists
		 * and if not create it.
		 */

		(void) snprintf(buf, sizeof (buf), "%s/etc", get_rootdir());

		if (access(buf, X_OK) != 0) {
			if (_create_dir(buf) != NOERR) {
				write_notice(ERRMSG,
				    SUGetErrorText(SUCreateDirectoryError));
				return (SUCreateDirectoryError);
			}
		}

		/*
		 * Copy the merged vfstab from the temporary location
		 * into the real location
		 */

		(void) snprintf(buf, sizeof (buf), "%s%s", get_rootdir(),
		    VFSTAB);

		if (_copy_file(buf, "/tmp/root/etc/vfstab") == ERROR) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUFileCopyError));
			return (SUFileCopyError);
		}

		/*
		 * Restore the archive from the media.
		 */

		if ((DSRALError = DSRALArchive(ArchiveList,
		    DSRALRestore,
		    Data->ArchiveCallback,
		    Data->ArchiveData))) {
			write_notice(ERRMSG,
			    DSRALGetErrorText(DSRALError));
			write_notice(ERRMSG,
			    SUGetErrorText(SUDSRALArchiveRestoreError));
			return (SUDSRALArchiveRestoreError);
		}

		/*
		 * Destroy the ArchiveList Object.
		 */

		if ((DSRALError = DSRALDestroy(&ArchiveList)))	{
			write_notice(ERRMSG,
			    DSRALGetErrorText(DSRALError));
			write_notice(ERRMSG,
			    SUGetErrorText(SUDSRALDestroyError));
			return (SUDSRALDestroyError);
		}

		/*
		 * cleanup
		 */

		_free_mount_list(&vlist);

		/*
		 * Mount up all non-global zones
		 */
		if (mount_zones()) {
			write_notice(ERRMSG,
			    SUGetErrorText(SUMountZonesError));
			return (SUMountZonesError);
		}

		/*
		 * Ok, now this is interesting.  The normal upgrade code
		 * expects that the directory structure for the upgrade
		 * will be in place prior to beginning the upgrade.
		 * However, since the backup logic is optimized to only
		 * archive off those files that have been modified since
		 * their original installation or other user modified
		 * files, we get caught with the Post KBI directories
		 * that upgrade depends on may not exist after the
		 * restore.  So, we go ahead and make them here just in case.
		 * Note: I do not care about return codes since if the
		 *	directories already exist thats fine.
		 */

		MakePostKBIDirectories();

	}

	/*
	 * Upgrade the system
	 */

	UpgradeData.ScriptCallback = Data->ScriptCallback;
	UpgradeData.ScriptData = Data->ScriptData;
	if ((SUError = SUUpgrade(SI_ADAPTIVE, &UpgradeData)) != SUSuccess) {
		return (SUError);
	}

	return (SUSuccess);
}

/*
 * *********************************************************************
 * FUNCTION NAME: SUUpgradeRecover
 *
 * DESCRIPTION:
 *
 * RETURN:
 *  TYPE			DESCRIPTION
 *  TSUError			The value of SUSuccess is returned upon
 *				successful completion.  Upon failure the
 *				appropriate error code will be returned that
 *				describes the encountered failure.
 *
 * PARAMETERS:
 *  TYPE			DESCRIPTION
 *  TSUUpgradeRecoveryData *	A pointer to the upgrade recovery data
 *				structure.
 *
 * DESIGNER/PROGRAMMER: Craig Vosburgh/RMTC (719)528-3647
 * *********************************************************************
 */

static TSUError
SUUpgradeRecover(TSUUpgradeRecoveryData *Data)
{
	TSUUpgradeData	UpgradeData;
	OpType		Operation = SI_RECOVERY;

	TDSRArchiveList ArchiveList;
	TDSRALError	ArchiveError;
	TDSRALMedia	Media;
	char		MediaString[PATH_MAX];
	TSUError	SUError;

	/*
	 * Check to see if we can recover from an interrupted
	 * adaptive upgrade
	 */

	if ((ArchiveError = DSRALCanRecover(&Media, MediaString))) {
		switch (ArchiveError) {

		/*
		 * If we can recover from a interrupted restore
		 */

		case DSRALRecovery:
			break;

		/*
		 * If we hit this path we have a problem
		 */

		default:
			write_notice(ERRMSG,
			    DSRALGetErrorText(ArchiveError));
			write_notice(ERRMSG,
			    SUGetErrorText(SUFatalError));
			return (SUFatalError);
		}
	}

	/*
	 * If we are not running in simulation mode
	 */

	if (!GetSimulation(SIM_EXECUTE)) {

		/*
		 * If we are recovering from a failed restore
		 */

		if (ArchiveError == DSRALRecovery) {

			/*
			 * Create an instance of the DSR Archive
			 * List object for use
			 */

			if ((ArchiveError = DSRALCreate(&ArchiveList))) {
				write_notice(ERRMSG,
				    DSRALGetErrorText(ArchiveError));
				write_notice(ERRMSG,
				    SUGetErrorText(SUDSRALCreateError));
				return (SUDSRALCreateError);
			}

			/*
			 * Restore the archive from the media.
			 */

			if ((ArchiveError = DSRALArchive(ArchiveList,
			    DSRALRestore,
			    Data->ArchiveCallback,
			    Data->ArchiveData))) {
				write_notice(ERRMSG,
				    DSRALGetErrorText(ArchiveError));
				write_notice(ERRMSG,
				    SUGetErrorText(SUDSRALArchiveRestoreError));
				return (SUDSRALArchiveRestoreError);
			}

			/*
			 * Destroy the ArchiveList Object.
			 */

			if ((ArchiveError = DSRALDestroy(&ArchiveList))) {
				write_notice(ERRMSG,
				    DSRALGetErrorText(ArchiveError));
				write_notice(ERRMSG,
				    SUGetErrorText(SUDSRALDestroyError));
				return (SUDSRALDestroyError);
			}
			Operation = SI_UPGRADE;
		}
	}

	/*
	 * Upgrade the system
	 */

	UpgradeData.ScriptCallback = Data->ScriptCallback;
	UpgradeData.ScriptData = Data->ScriptData;
	if ((SUError = SUUpgrade(Operation, &UpgradeData)) != SUSuccess) {
		return (SUError);
	}

	return (SUSuccess);
}

/*
 * Function:	_preserve_slashboot
 * Description:	Preserve the contents of the slash boot
 *		partition prior to deleting it.
 *
 * Scope:	internal
 * Parameters:	vlist   - a linked list of vfstab struct
 * Return: None
 */
void
_preserve_slashboot(Vfsent *vlist)
{
	char cmd[MAXPATHLEN+1];

	/* Only run if on i386 */
	if (! IsIsa("i386"))
		return;

	if (_slash_boot_is_mounted(vlist) == SUCCESS) {
		/* /boot was found, tar it up to /tmp */
		(void) snprintf(cmd, sizeof (cmd),
		    "/usr/sbin/tar -cf %s %s%s > /dev/null 2>&1",
		    TARBOOT, get_rootdir(), BOOT);
		/*
		 * just run it, not much
		 * we can do if it fails
		 */
		(void) system(cmd);
	}
}

/*
 * Function:	_restore_slashboot
 * Description:	Restore the contents of the slash boot
 * 		partition after it was deleted.
 *
 * Scope:	internal
 * Parameters:	vlist   - a linked list of vfstab struct
 * Return: None
 */
void
_restore_slashboot(Vfsent *vlist)
{
	char cmd[MAXPATHLEN+1];

	/* Only run if on i386 */
	if (! IsIsa("i386"))
		return;
	if ((access(TARBOOT, R_OK) == 0) &&
	    (_slash_boot_is_mounted(vlist) == SUCCESS)) {

		/*
		 * boot tarfile was found,
		 * untar it up to /tmp
		 */
		(void) snprintf(cmd, sizeof (cmd), "/usr/sbin/tar -xf %s",
		    TARBOOT);
		(void) system(cmd);
	}

}

/*
 * Function:	_slash_boot_is_mounted
 * Description: Check to see if /boot is in the vfstab
 *
 * Scope:	internal
 * Parameters:	vlist   - a linked list of vfstab struct
 * Return: int
 *	SUCCESS - /boot was found in the vlist
 *	FAILURE - /boot was not found in the vlist
 */
int
_slash_boot_is_mounted(Vfsent *vlist)
{
	Vfsent	*vp;
	struct vfstab *vfsp;

	WALK_LIST(vp, vlist) {
		vfsp = vp->entry;
		/*
		 * only look at entries with directory
		 * mount_p names
		 */
		if (vfsp->vfs_mountp == NULL ||
				vfsp->vfs_mountp[0] != '/')
			continue;
		if (strcasecmp(vfsp->vfs_mountp, BOOT) == 0) {
			return (SUCCESS);
		}
	}
	return (FAILURE);
}


/*
 * Function:	_make_root
 * Description: Generate a path given a path and root
 *
 * Scope:	internal
 * Parameters:	path	The path from the altroot
 *		rootdir	The alternate root
 * Return:	A pointer to the new root, not to be
 *		free'd.
 */
static char *
_make_root(char *path, char *rootdir)
{
	static char pathbuf[MAXPATHLEN + 1];

	if (rootdir == NULL || strcmp(rootdir, "/") == 0) {
		return (path);
	} else {
		(void) snprintf(pathbuf, MAXPATHLEN + 1, "%s%s%s",
		    rootdir,
		    path[0] == '/' ? "" : "/",
		    path);
		return (pathbuf);
	}
}

/*
 * Function:	_force_reconfiguration_boot
 * Description: force a reconfiguration by touching a magic file
 *
 * Scope:	internal
 * Return:	0 if we could not create the file, non-zer otherwise
 */
static int
_force_reconfiguration_boot(void)
{
	int fd;

	/* don't do it when simulating */
	if (GetSimulation(SIM_EXECUTE)) {
		return (1);
	}

	if ((fd = open(_make_root(RECONFIGURE_FILE, get_rootdir()),
	    O_CREAT)) == -1) {
		return (0);
	}
	(void) close(fd);
	return (1);
}

/*
 * Function:	mark_required_software
 * Description:	Marks all modules and submodules as being
 *		required if the top-level module is marked as such.
 *		Also marks any packages appearing in the
 *		transfer list as being required.
 * Scope:		global
 * Parameters:	none
 * Return:	NOERROR if sucessful, ERROR otherwise
 */
int
mark_required_software(void)
{
	int		i;
	Module		*meta = get_current_metacluster();
	int		found_reqd = FALSE, found_deflt = FALSE;

	/*
	 * First mark any required packages from the transferlist
	 */
	if ((trans == NULL) && (_setup_transferlist(&trans) != NOERR)) {
	    return (ERROR);
	}

	while (meta) {
		if (meta->info.mod->m_status == REQUIRED) {
			mark_required(meta);
			found_reqd = TRUE;
			write_debug(SVC_DEBUG_L1(1),
			    "mark_required_software: marking %s as REQUIRED\n",
			    meta->info.mod->m_pkgid);
		} else if ((meta->info.mod->m_flags & UI_DEFAULT) != 0) {
			set_default(meta);
			found_deflt = TRUE;
			write_debug(SVC_DEBUG_L1(1),
			    "mark_required_software: marking %s as DEFAULT\n",
			    meta->info.mod->m_pkgid);
		}
		meta = get_next(meta);
	}

	/*
	 * mark the legacy default and required metaclusters if they weren't
	 * specified in the clustertoc.
	 */
	meta = get_current_metacluster();
	while (meta) {
	    if (!found_reqd &&
		streq(meta->info.mod->m_pkgid, REQD_METACLUSTER)) {
		mark_required(meta);
		found_reqd = TRUE;
		write_debug(SVC_DEBUG_L1(1),
		    "mark_required_software: marking %s as legacy REQUIRED\n",
		    meta->info.mod->m_pkgid);
	    }
	    if (!found_deflt &&
		streq(meta->info.mod->m_pkgid, ENDUSER_METACLUSTER)) {
		set_default(meta);
		found_deflt = TRUE;
		write_debug(SVC_DEBUG_L1(1),
		    "mark_required_software: marking %s as legacy DEFAULT\n",
		    meta->info.mod->m_pkgid);
	    }
	    meta = get_next(meta);
	}

	/* only set up /tmp/root for indirect installs */
	if (DIRECT_INSTALL) {
	    return (NOERR);
	}

	if (GetSimulation(SIM_EXECUTE)) {

		/* Don't do debug if no transfer information exists */
		if (!trans || (trans[0].found <= 0) ||
		    (trans[0].file != NULL)) {
			return (NOERR);
		}
	}

	/*
	 * Now mark any packages whose members appear in the
	 * transfer_list file as being required (cause we're
	 * going to copy them over
	 */

	/* Make sure the 1st element of array is not corrupted */
	if (!trans || (trans[0].found <= 0) || (trans[0].file != NULL)) {
		write_notice(ERRMSG, MSG0_TRANS_CORRUPT);
		return (ERROR);
	}

	/* Step through the transfer array looking for items to process */
	for (i = 1; i <= trans[0].found; i++) {
	    write_debug(SVC_DEBUG_L1(1),
		"mark_required_software: marking %s required "
		"from transferlist (%s)\n",
		trans[i].package, trans[i].file);
	    mark_pkg_required(trans[i].package);
	}

	return (NOERR);
}
