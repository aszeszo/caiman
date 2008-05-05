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


#ifndef _SPMIAPP_API_H
#define	_SPMIAPP_API_H


/*
 * Module:	spmiapp_api.h
 * Group:	libspmiapp
 * Description:
 */

#include <sys/types.h>
#include <spmicommon_api.h>
#include <spmistore_api.h>
#include <spmisoft_api.h>
#include <spmisvc_api.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * LIBAPPSTR is intended to wrap strings that we want other libraries
 * or apps to be able to use.  These strings are placed in message
 * files in *this* library.
 */
#define	LIBAPPSTR(x)	dgettext("SUNW_INSTALL_LIBAPP", x)

/* other LIBSPMIAPP API files */
#include <spmiapp_strings.h>
#include <spmiapp_ui_msg.h>

/* constants */
#define	DFLT_STATUS_LOG_FILE	"/tmp/install_log.debug"
#define	DFLT_INSTALL_LOG_FILE	"/tmp/install_log"

#define	FD_SIZE_DELETE		 0
#define	FD_SIZE_ALL		-1
#define	FD_SIZE_MAXFREE		-2
#define	FD_SIZE_CYLRANGE	-3
#define	FD_SIZE_UNKNOWN		-4
#define	PROFILE_VER_0		0

/* Delta type (Sw_unit) */
#define	EXPLICIT		0
#define	IMPLICIT		1

/* Miscellaneous macros and constants */

#define		DEFAULT_NUMBER_OF_CLIENTS	5
#define		DEFAULT_ROOT_PER_CLIENT		25
#define		DEFAULT_SWAP_PER_CLIENT		32

/*
 * Standard TRUE/FALSE definitions
 */
#if !defined(TRUE) || ((TRUE) != 1)
#define	TRUE    (1)
#endif
#if !defined(FALSE) || ((FALSE) != 0)
#define	FALSE   (0)
#endif

/*
 * standard length of time (in seconds) for an interactive app
 * to pause a display before removing it so that the user has
 * some time to see it - used mainly for progress displays
 */
#define	APP_PROGRESS_PAUSE_TIME	5

#define	DEFAULT_FS_FREE		15	/* default UFS free space */

#define	DISKPARTITIONING(x)	(x)->disk.partitioning
#define	DISKFILESYS(x)		(x)->disk.filesys
#define	DISKMETADB(x)		(x)->disk.svm_metadb
#define	DISKFDISK(x)		(x)->disk.fdisk
#define	DISKUSE(x)		(x)->disk.use
#define	DISKDONTUSE(x)		(x)->disk.dontuse
#define	SYSTYPE(x)		(x)->param.sys_type
#define	PROFILE(x)		(x)->param.pro_file
#define	DISKFILE(x)		(x)->param.disk_file
#define	ROOTDEVICE(x)		(x)->param.root_device
#define	BACKUPMEDIA(x)		(x)->dsr.backup_media
#define	MEDIAPATH(x)		(x)->dsr.media_path
#define	LAYOUTCONSTRAINT(x)	(x)->dsr.layout_constraint
#define	LCDEVNAME(x)		(x)->devname
#define	LCSTATE(x)		(x)->state
#define	LCSIZE(x)		(x)->size
#define	LCNEXT(x)		(x)->next
#define	MEDIANAME(x)		(x)->param.media
#define	NOREBOOT(x)		(x)->param.noreboot
#define	NOSPACECHK(x)		(x)->param.nospacechk
#define	NOBOOTBLK(x)		(x)->param.nobootblk
#define	NORECONFIGURE(x)	(x)->param.noreconfigure
#define	NOTRANSFER(x)		(x)->param.notransfer
#define	NODISKOPS(x)		(x)->param.nodiskops
#define	LUFLAG(x)		(x)->param.lu_flag
#define	OPTYPE(x)		((x)->param.operation)
#define	ISOPTYPE(x, y)		((x)->param.operation == (y))
#define	REMOTEFS(x)		(x)->remote
#define	SERVICES(x)		(x)->services
#define	CLIENTROOT(x)		SERVICES((x)).client_root
#define	CLIENTSWAP(x)		SERVICES((x)).client_swap
#define	CLIENTCNT(x)		SERVICES((x)).num_clients
#define	CLIENTPLATFORM(x)	SERVICES((x)).karchs
#define	BOOTDEVICE(x)		(x)->bootobj.boot_device
#define	BOOTPROM(x)		(x)->bootobj.preserve
#define	SOFTWARE(x)		(x)->software
#define	TOTALSWAP(x)		(x)->swap.total
#define	LOCALES(x)		SOFTWARE((x)).lang
#define	GEOS(x)			SOFTWARE((x)).geo
#define	UNITS(x)		SOFTWARE((x)).units
#define	SWPRODUCT(x)		SOFTWARE((x)).prod
#define	METACLUSTER(x)		SOFTWARE((x)).meta
#define	PROVERSION(x)		(x)->version
#define	FLARNUM(x)		(x)->flash.num_archives
#define	FLARLOCARR(x)		(x)->flash.archives
#define	FLARLOC(x, y)		(&(FLARLOCARR(x)[(y)]))
#define	BOOTENVNUM(x)		(x)->bootenvobj.numcommands
#define	BOOTENVLOCARR(x)	(x)->bootenvobj.commands
#define	BOOTENVLOC(x, y)	(&(BOOTENVLOCARR(x)[(y)]))
#define	EXTRA_SOFT_PACKAGE(x)	(x)->ext_soft.package
#define	PATCH(x)		(x)->ext_soft.patch
#define	is_fdisk_system 	(IsIsa("i386") || IsIsa("ppc"))


/*
 * masks for application state
 *
 * AppState_UPGRADE:
 *	Upgrade required,
 *	This is set whenever upgrade is required, so both it AND
 *	the other AppState_UPGRADE states may be set at the same time.
 *
 * AppState_UPGRADE_DSR:
 *	DSR upgrade required for currently
 *	selected upgradeable slice.
 *
 * AppState_UPGRADE_RECOVER:
 *	We're are resuming an upgrade.
 *
 * AppState_UPGRADE_RECOVER_RESTORE:
 *	We're are resuming an upgrade in the DSR archive restore phase.
 *
 * AppState_UPGRADE_RECOVER_UPGSCRIPT:
 *	We're are resuming an upgrade in the upgrade script phase.
 *
 * AppState_UPGRADE_CHILD:
 *	We are in an upgrade and we are in the child process.
 *
 * AppState_UPGRADE_PARENT:
 *	We are in an upgrade and we are in the parent process.
 *
 * AppState_UPGRADESW:
 * 	Used internally to track some sw lib state/resetting behavior.
 */
#define	AppState_UPGRADE		01
#define	AppState_UPGRADE_DSR		02
#define	AppState_UPGRADE_RECOVER	04
#define	AppState_UPGRADE_RECOVER_RESTORE	010
#define	AppState_UPGRADE_RECOVER_UPGSCRIPT	020
#define	AppState_UPGRADE_CHILD		040
#define	AppState_UPGRADE_PARENT		0100
#define	AppState_UPGRADESW		0200

/*
 * For the interactive apps.
 *
 * These are the return codes that the child will return back to the
 * parent.
 *
 * The upgrade path forks off a child process so that the child can
 * mount and add swap, whereas the parent can't mount and add swap since
 * it has to be able to reformat the disks, which can't be done when swap
 * is mounted and being used.
 *
 * The boundary points in the upgrade parade between the parent/child are:
 *	- between the select version to upgrade processing and the
 *	software customization screen.
 *	(i.e. the parent process picks the upgradeable slice and then
 *	the child process takes over and actually does the mount and add swap
 *	on that slice).
 *	- the child process displays the Profile screen and the parent
 *	process picks up to actually do the SystemUpdate backend processing.
 */
typedef enum {
	/* the user chose not to resume an upgrade */
	ChildUpgRecoverNo,

	/* resume an upgrade in the DSR archive list restore phase */
	ChildUpgRecoverRestore,

	/* resume an upgrade in the upgrade script phase */
	ChildUpgRecoverUpgScript,

	/* proceed with a normal upgrade */
	ChildUpgNormal,

	/* proceed with a DSR upgrade */
	ChildUpgDsr,

	/*
	 * The child is requesting a goback across the parent/child
	 * boundary. i.e. a goback into the parOs realm of the parent.
	 */
	ChildUpgGoback,

	/*
	 * The child is requesting a change from the Upgrade Profile
	 * screen. i.e. go back to the parent at the beginning of the
	 * upgrade parade.
	 */
	ChildUpgChange,

	/*
	 * there are no more ugpradeable slices and the user has just
	 * chosen to opt for the initial path as their only option.
	 */
	ChildUpgInitial,

	/* the slice we tried to upgrade has failed for some reason */
	ChildUpgSliceFailure,

	/* the child is continuing on the normal parade */
	ChildUpgContinue,

	/* if child exits with a signal */
	ChildUpgExitSignal,

	/*
	 * install exit codes from the upgrade child process.
	 * The parent maps these to the standard exit codes
	 * (EXIT_INSTALL_FAILURE, EXIT_INSTALL_SUCCESS_*)
	 */
	ChildUpgExitOkReboot,
	ChildUpgExitOkNoReboot,
	ChildUpgExitFailure,

	/*
	 * Indicates that the child exitted via a user reuest.
	 * This is actually only used in the CUI right now.
	 */
	ChildUpgUserExit

} TChildAction;

/* data structures */

struct swap_res {
	int		*explicit;	/* explicit swap requested */
	struct swap_obj	*next;		/* list of swap objects */
};

struct swap_obj {
	u_char		type;		/* type of swap object */
	char		*name;		/* name of swap object */
	struct swap_obj	*next;		/* next swap object in list */
};

typedef struct namelist {
	char		*name;
	struct namelist	*next;
} Namelist;

/*
 * Define default values for metadb  (SVM mirror information)
 */
#define	MINIMUM_METADB_SIZE 100
#define	MAXIMUM_METADB_SIZE 8192
#define	DEFAULT_METADB_SIZE 8192

#define	MINIMUM_METADB_COUNT 1
#define	MAXIMUM_METADB_COUNT 50
#define	DEFAULT_METADB_COUNT 3

/*
 * Define the script names amd log files
 */
#define	MIRROR_CREATION_SCRIPT	"/tmp/create_mirror"
#define	MIRROR_CREATION_LOG	"/tmp/create_mirror.log"
#define	MIRROR_TRANSFER_SCRIPT	"/tmp/transfer_mirror"
#define	MIRROR_TRANSFER_LOG	"/tmp/transfer_mirror.log"
#define	SVM_PSEUDO_DRIVER	"md"
#define	WPATH_TO_INST		"/etc/path_to_inst"
#define	MD_CF			"/etc/lvm/md.cf"
#define	MDDB_CF			"/etc/lvm/mddb.cf"
#define	MD_CONF			"/kernel/drv/md.conf"
#define	SVM_ROOT_PKG		"SUNWmdr"
#define	MAX_SVM_MIRROR_NAMELEN	32
#define	MAX_SVM_VOLUME_ID	128

/*
 * filesys store
 */
typedef struct storage {
	char		*dev;		/* Disk Slice */
	char		*name;		/* File System/mount point */
	char		*size;		/* Size/any/free etc */
	char		*mntopts;	/* Mount options */
	char		*mirror_name;	/* The volume name of the mirror dev */
	char		*dev_mirror;	/* Mirror Device */
	int		is_mirror;	/* Is this entry for mirroring? */
	int		preserve;
	struct storage	*next;
} Storage;

/*
 * State replica (metadb) store
 */
typedef struct mdb_storage {
	char			*dev;	/* SVM replica (metadb) disk slice */
	int			size;	/* Size in blocks */
	int			count;	/* Number of SVM replica */
	struct mdb_storage	*next;
} MDBStorage;

/* Deltas to selected metacluster */
typedef struct software_unit {
	char			*name;		/* Name of package or cluster */
	int			delta;		/* SELECTED or UNSELECTED */
	int			unit_type;	/* PACKAGE or CLUSTER */
	int			source;		/* IMPLICIT or EXPLICIT */
	struct software_unit	*next;
} Sw_unit;

/*
 * Fdisk keyword data structure.
 *	flags	- 32 bit flag field
 *	part	- 0 (any) or 1-4 (explicit)
 * 	id	- partition type
 *	size	-  0 - unused
 *		  -1 - all
 *		  -2 - maxfree
 *		  -3 - explicit cylinder range
 *		  -4 - unknown
 */
typedef struct fdisk {
	char		*disk;		/* cX[tX]dX */
	u_long		flags;		/* see #defines above */
	int		part;		/* partition # (1-4) */
	int		id;		/* partition ID */
	int		size;		/* explicit partition size */
	int		startcyl;	/* explicit partition size */
	int		cylcount;	/* explicit partition size */
	struct fdisk	*next;
} Fdisk;

/*
 * Linked list structure for client services
 */
typedef struct {
	int	num_clients;	/* # diskless clients */
	int	client_root;	/* explicit size of per-client root (MB) */
	int	client_swap;	/* explicit size of per-client swap (MB) */
	Namelist	*karchs;	/* list of supported client archs */
} Services;

/*
 * swap resource data structure
 */
typedef struct {
	int	total;		/* user specified required swap */
} Swap;

/*
 * Master disk work profile structure
 */
typedef struct {
	int		partitioning;
	Storage		*filesys;
	MDBStorage	*svm_metadb;
	Fdisk		*fdisk;
	Namelist	*use;
	Namelist	*dontuse;
} Disk;

/*
 * Software configuration data structure
 */
typedef struct software {
	char 		*meta;
	Sw_unit		*units;
	Namelist	*lang;
	Namelist	*geo;
	Module 		*prod;
} Software;


/*
 * DSR layout_constraint Parameters
 */
typedef struct layout_constraint {
	char				*devname;
	TSLState			state;
	unsigned long			size;
	struct layout_constraint 	*next;
} LayoutConstraint;

/*
 * Command line pfinstall parameters
 */
typedef struct param {
	OpType		operation;	/* upgrade or install flag */
	MachineType	sys_type;	/* system type */
	char		*pro_file;	/* profile file name */
	char		*media;		/* media specified */
	char		*disk_file;	/* disk file */
	char		*root_device;	/* explicit root disk specifier */
	int		noreboot;	/* noreboot state flag */
	int		nospacechk;	/* no space check flag */
	int		nobootblk;	/* no boot block flag */
	int		noreconfigure;	/* don't un/reconfigure */
	int		notransfer;	/* don't transfer files */
	int		nodiskops;	/* don't modify low-level disk stuff */
	int		lu_flag;	/* flag to specify that caller is LU */
} Param;

/*
 * Data structure for boot object configuration
 */
typedef struct bootobject {
	char		*boot_device;	/* explicit root disk specifier */
	int		preserve;
} BootObject;

/*
 * Data structure for boot environment object configuration
 */
typedef enum {
	BootEnvCreate
	/* other bootenv ops go here */
} BootEnvCommandType;

typedef struct {
	char		*mntpt;
	char		*device;
	char		*fstyp;
} BootEnvCreateFilesys;

typedef struct {
	char			*bename;
	char			*source_bename;
	int			num_filesys;
	BootEnvCreateFilesys	*filesys;
} BootEnvCreateCommand;

typedef struct {
	BootEnvCommandType		cmdtype;
	union {
		BootEnvCreateCommand	createbe;
		/* other types here */
	} cmd;
} BootEnvCommand;

typedef struct {

	/* how many commands */
	int		numcommands;
	/* array of commands to carry out */
	BootEnvCommand	*commands;

} BootEnvObject;

/*
 * DSR layout_constraint Parameters
 */
typedef struct dsrobject {
	/* The media type for the backup */
	TDSRALMedia		backup_media;

	/* The path to the media */
	char			*media_path;

	/* The list of slices to be modified */
	LayoutConstraint	*layout_constraint;
} DSRObject;

typedef struct flashobject {
	/* The number of archives */
	int		num_archives;
	/* Flag to check clone parent ws archive master */
	int	check_master;
	/* Flag to check clone contents ws archive manifest */
	int	check_contents;
	/* Flag for forced deployment */
	int	forced_deployment;
	/* path to local customization scripts */
	char	*local_customization;

	/* The array of archive locations */
	FlashArchive	*archives;
} FlashObject;

/*
 * Structure to save additional package and patch specification
 */
typedef struct extra_software {
	int		soft_type;
	PackageStorage	*package;
	PatchStorage	*patch;
} ExtraSoftware;

/*
 * Data structure representing profile specification
 */
typedef struct profile {
	Param		param;		/* execution parameters */
	Software	software;	/* software structure */
	Swap		swap;		/* swap resources */
	Disk		disk;		/* disk specification structure */
	Remote_FS	*remote;	/* remote file systems */
	Services	services;	/* required services */
	BootObject	bootobj;	/* boot object parameters */
	BootEnvObject	bootenvobj;	/* boot environment parameters */
	DSRObject	dsr;		/* dsr parameters */
	FlashObject	flash;		/* flash parameters */
	ExtraSoftware	ext_soft;	/* Additonal packages and patch */
	int		version;	/* profile version ID */
} Profile;

/*
 * Data structure for passing different app (ttinstall, installtool
 * pfinstall) command line parameter information.
 */
typedef struct paramUsage {
	char *app_name;			/* argv[0] app name */
	char *app_name_base;		/* basename of app */
	char *app_args;			/* getopt arg string for FE */
	char *app_public_usage;		/* FE public args usage string */
	char *app_private_usage;	/* FE private args usage string */
	char *app_trailing_usage;	/* FE trailing (public) operands */
					/* usage string */
} ParamUsage;

/*
 * Multiple OS upgrade data structure.
 * Used by the interactives for tracking selections for which
 * slice to upgrade.
 */
typedef struct {
	char *slice;	/* upgradeable slice - e.g. cot0d0s0 */
	char *stub;	/* stub boot device (if any) */
	char *release;	/* release string - e.g. 2.5.1 */
	svm_info_t *svminfo;	/* solaris logical vol. man. info */
	/*
	 * svmstring - string to display to user
	 * if svminfo exists
	 */
	char *svmstring;
	int failed;	/* has this slice been tried and failed? */
	int selected;	/* marks the currently selected slice */
} UpgOs_t;

/*
 * Patch Analyzer results structure
 */
typedef struct {
	int num_removals;	/* Number of patches being removed */
	char **removals;	/* Patches being removed */

	int num_downgrades;	/* Number of patches being downgraded */
	char **downgrade_ids;	/* IDs of downgraded patches */
	char **downgrade_from;	/* current revs of patches */
	char **downgrade_to;	/* resulting revs of patches */

	int num_accumulations;	/* Number of patches being accumulated */
	char **accumulateds;	/* Patches being accumulated */
	char **accumulators;	/* Accumulator patch names */
} PAResults;

/*
 * Patch Analyzer analysis applicability check return codes
 */
typedef enum {
	PACheckOK = 1,
	PACheckNoAnalyzer,
	PACheckNotEligible,
	PACheckError
} PACheckRC;

/*
 * Patch Analyzer analysis return codes
 */
typedef enum {
	PAAnalyzeOK = 1,
	PAAnalyzeErrNoPA = 2,
	PAAnalyzeErrPAExec = 3,
	PAAnalyzeErrParse = 4

} PAAnalyzeRC;

/*
 * DSR:
 * Slice list attributes that are relevant to a given slice list entry.
 */
typedef enum {
	/* CANNOT start at 0 - used as varargs */
	DsrSLAttrReqdSize = 1,
	DsrSLAttrReqdSizeStr,
	DsrSLAttrExistingSize,
	DsrSLAttrExistingSizeStr,
	DsrSLAttrCurrentSize,
	DsrSLAttrCurrentSizeStr,
	DsrSLAttrFreeSpace,
	DsrSLAttrFreeSpaceStr,
	DsrSLAttrSpaceReqd,
	DsrSLAttrSpaceReqdStr,
	DsrSLAttrMountPointStr,
	DsrSLAttrTaggedMountPointStr,
	DsrSLAttrExistingSlice,
	DsrSLAttrCurrentSlice
} DsrSLEntryAttr;

/*
 * DSR:
 * Slice list attributes that are relevant at the slice list level.
 */
typedef enum {
	/* CANNOT start at 0 - used as varargs */
	DsrSLAttrMediaType = 1,
	DsrSLAttrMediaTypeStr,
	DsrSLAttrMediaTypeDeviceStr,
	DsrSLAttrMediaTypeEgStr,
	DsrSLAttrMediaDeviceStr,
	DsrSLAttrMediaToggleStr
} DsrSLListAttr;

/* how much of a file system name will be displayed? */
#define	UI_FS_DISPLAY_LENGTH 14

/* standard field length for displaying file system size in */
#define	UI_FS_SIZE_DISPLAY_LENGTH	5

/* total max length of "main_label: detail label" string */
#define	APP_UI_UPG_PROGRESS_STR_LEN	60

/*
 * DSR: ways a file system could have changed
 * Used in the interactive apps for the File System Modification Summary screen
 */
#define	SliceChange_Nothing_mask	0x0001
#define	SliceChange_Size_mask		0x0002
#define	SliceChange_Slice_mask		0x0004
#define	SliceChange_Unused_mask		0x0008
#define	SliceChange_Collapsed_mask	0x0010
#define	SliceChange_Deleted_mask	0x0020
#define	SliceChange_Created_mask	0x0040

/*
 * DSR: ways a slice list can be filtered
 */
typedef enum {
	SLFilterAll,
	SLFilterFailed,
	SLFilterVfstabSlices,
	SLFilterNonVfstabSlices,
	SLFilterSliceNameSearch,
	SLFilterMountPntNameSearch
} TSLFilter;

/*
 * DSR: Slice list application data that is stored per slice list entry
 */
typedef struct {
	/*
	 * User entered data that we want to save in order to maintain
	 * screen history.
	 *
	 * Final size: since they could leave a screen with a bad value
	 * in the the size field, we store it as a char *, rather than
	 * a ulong.
	 */
	struct {
		char *final_size;
	} history;

	/*
	 * should this slice be displayed this time?
	 * i.e. this is set during filtering
	 */
	int in_filter;

	/*
	 * room for even more additional untyped data here -
	 * i.e. the gui and cui can keep very UI specific data
	 * in here...
	 */
	void *extra;

} DsrSLEntryExtraData;

/*
 * DSR: Slice list application data that is stored at the slice list level
 */
typedef struct {
	/* the filter info for the last filter that worked */
	TSLFilter filter_type;
	char *filter_pattern;

	/* the info for the last filter request */
	struct {
		TSLFilter filter_type;
		char *filter_pattern;
		TDSRALMedia media_type;
		char *media_device;
	} history;

	struct {
		int num_in_vfstab;
		ulong reqd;	/* in KB */
	} swap;

	/* archive size needed */
	unsigned long long archive_size;

	void *extra;

} DsrSLListExtraData;

/*
 * DSR progress display defines/data structures for the UI apps
 * These are the indexes into the arrays of progress information
 * passed to the progress display module.
 */
#define	PROGBAR_ALGEN_INDEX			0
#define	PROGBAR_SW_ANALYZE_INDEX		0

/* has to be 0!  */
#define	PROGBAR_UPGRADE_INDEX	PROGBAR_SW_ANALYZE_INDEX

/* has to be 1!  */
#define	PROGBAR_ALRESTORE_INDEX	1
#define	PROGBAR_NEWFS_INDEX	2
#define	PROGBAR_ALBACKUP_INDEX	3
#define	PROGBAR_PROGRESS_CNT	4

/*
 * Information used to store how much of a progress bar should be
 * used for a particular phase and where in the progress bar it should
 * start.
 */
typedef struct {
	int start;
	float	factor;
} UIProgressBarScaleInfo;

/*
 * Holds data used to initialize a progress bar.
 */
typedef struct {
	char *title;
	char *main_msg;
	char *main_label;
	char *detail_label;
	int percent;
} UIProgressBarInitData;

/*
 * Interactive apps parade definitions
 */
#define	PARADE_INTRO_FILE	"/tmp/.run_install_intro"

/* main parade window names */
typedef enum {
	/*
	 * indicates no window - useful for eaxmple, for indicating that the
	 * go back stack is empty.
	 */
	parNoWin,

	parAllocateSvcQuery,
	parAutoQuery,

	/* only used in CUI */
	parClientParams,

	/* only used in GUI */
	parClientSetup,

	parClients,
	parFilesys,
	parIntro,
	parIntroInitial,
	parFlashArchives,
	parGeo,
	parSysLocale,
	parOs,

	/* Patch Analyzer windows */
	parPAQuery,
	parPASummary,
	parPARemovals,
	parPADowngrades,
	parPAAccumulations,
	parPAFinale,

	parPrequery,
	parProgress,
	parReboot,
	parRemquery,

	/* DSR - sw lib analyze space progress bar */
	parDsrAnalyze,

	/*
	 * DSR - File System Redistribution screen
	 * (now the Auto-layout Constraints screen)
	 */
	parDsrFSRedist,

	/* DSR - File System Modifications Summary screen */
	parDsrFSSummary,

	/* DSR - Archive list backup media screen */
	parDsrMedia,

	/* DSR - Archive list generation progress bar */
	parDsrALGenerateProgress,

	/* DSR - More Space Required screen */
	parDsrSpaceReq,

	/* currently unused, but prototyped for in the gui? */
	parServiceSelect,

	parSummary,
	parChooseMedia,
	parSw,
	parLicense,
	parProdSel,
	parAddProds,
	parInstallSummary,
	parSwQuery,
	parUpgrade,
	parUpgradeProgress,
	parUsedisks,
	parWin_t_count
} parWin_t;

/* main parade actions */
typedef enum {
	parAAllocateSvc,
	parAAnalyze,
	parAChange,
	parAComeback,
	parAContinue,
	parACustomize,
	parADsrSpaceReq,
	parADsrFSSumm,
	parADsrFSRedist,
	parAExit,
	parAGoback,
	parAInitial,
	parAFlash,
	parAStandard,
	parANone,
	parAReboot,
	parAUpgrade,
	parAUpgradeFail,
	parANoDsr,
	parAStayOnPanel
} parAction_t;

/*
 * if non-zero, copious ui printf - this will change when standardized
 * tracing/debugging is done
 */
extern unsigned int debug;

/* if not 1 then disable upgrade,server */
extern unsigned int upgradeEnabled;

/* functional prototypes */

/* app_dsr.c */
extern int DsrFSAnalyzeSystem(FSspace **fs_space,
	int *num_failed, TCallback callback_func, void *user_data);
extern int DsrFSGetNumFailed(FSspace **fs_space);

extern int DsrSLAutoLayout(
	TList slhandle, FSspace **fs_space, int default_layout);
extern void DsrSLPrint(TList slice_list, char *file, int line_num);
extern int DsrSLCreate(TList *slice_list, TLLData list_data,
	FSspace **fs_space);
extern int DsrSLSetDefaults(TList slhandle);
extern int DsrSLEntrySetDefaults(TSLEntry *slentry);

extern int DsrSLUICreate(TDSRArchiveList *archive_list,
	TList *slice_list, FSspace **fs_space);
extern TLLError DsrSLUIEntryDestroy(TLLData data);
extern int DsrSLUIInitExtras(TList slhandle);
extern int DsrSLUIResetDefaults(TList slhandle, FSspace **fs_space,
	int lose_collapse);
extern int DsrSLUISetDefaults(TList slhandle);
extern void DsrSLUIEntrySetDefaults(TSLEntry *slentry);
extern void DsrSLUIRenameUnnamedSlices(char **str);

extern int DsrIsDeviceCoResident(FSspace **fs_space, char *device);
extern int DsrGetSliceNumFromDeviceName(char *device);
extern void DsrSLEntryGetAttr(TSLEntry *slentry, ...);
extern void DsrSLListGetAttr(TList slhandle, ...);
extern int DsrSLFilter(TList slhandle, int *match_cnt);
extern int DsrSLResetSpaceIgnoreEntries(TList slhandle);

extern int DsrSLGetSwapInfo(TList slhandle, ulong *total_swap);
extern int DsrSLSetInstanceNumbers(TList slhandle);
extern int DsrSLGetNumCollapseable(TList slhandle);
extern char *DsrSLGetParentFS(FSspace **fs_space, char *mount_point);
extern TSLEntry *DsrSLGetEntry(TList slhandle,
	char *mntpnt, int instance_number);
extern TSLEntry *DsrSLGetSlice(TList slhandle, char *path);
extern int DsrSLGetSpaceSummary(TList slhandle,
	ulong *add_space_req,
	ulong *add_space_alloced);
extern int DsrSLValidFinalSize(char *final_size_str, ulong *final_size);
extern ulong DsrHowSliceChanged(Disk_t *dp, int new_slice,
	Disk_t **orig_dp, int *orig_slice);
extern char *DsrHowSliceChangedStr(ulong mask);
extern char *DsrALMediaTypeStr(TDSRALMedia media_type);
extern char *DsrALMediaTypeEgStr(TDSRALMedia media_type);
extern char *DsrALMediaErrorStr(TDSRALMedia Media,
	char *MediaPath, TDSRALError err);
extern int DsrALMediaErrorIsFatal(TDSRALError err);

extern char *DsrSLStateStr(TSLState state);
extern char *DsrSLFilterTypeStr(TSLFilter filter_type);

/* app_disks.c */
extern void DiskRestoreAll(Label_t state);
extern void DiskCommitAll(void);
extern void DiskSelectAll(int select);
extern void DiskDeselectNonSolaris(Label_t state);
extern void DiskNullAll(void);
extern void DiskPrintAll(void);
int	DiskGetContentMinimum(void);
int	DiskGetContentDefault(void);

/* app_usedisks.c */
extern void DiskAutoSelect(Disk_t *);
extern int DiskIsCurrentBootDisk(Disk_t *);
extern int DiskGetSize(Disk_t *, int);
extern char *DiskMakeListName(Disk_t *, int);
extern int DiskGetListTotal(int);

/* app_bootobj.c */
extern int BootobjDiffersQuery(char *);

/* app_lfs.c */
extern int any_preservable_filesystems(void);


/* app_upgrade.c */
extern void SliceGetUpgradeable(UpgOs_t **slices);
extern void SliceFreeUpgradeable(UpgOs_t *slices);
extern int SliceGetTotalNumUpgradeable(UpgOs_t *slices);
extern int SliceGetNumUpgradeable(UpgOs_t *slices);
extern int SliceIsSystemUpgradeable(UpgOs_t *slices);
extern void SliceSelectOne(UpgOs_t *slices);
extern UpgOs_t *SliceGetSelected(UpgOs_t *slices, int *slice_index);
extern void SliceSetFailed(UpgOs_t *slices);
extern void SliceSetUnselected(UpgOs_t *slices);
extern void SlicePrintDebugInfo(UpgOs_t *slices);
extern boolean_t CheckZonesUpgradeableFromSlice(char *, StringList **);
extern int AppUpgradeInitSw(unsigned int *state);
extern int AppUnmountAll(void);
extern int AppUpgradeResetToInitial(unsigned int *state);
extern int AppUpgradeInitialize(
	FSspace ***fs_space,
	UpgOs_t *slices,
	unsigned int *state);
extern int AppDoMountsAndSwap(UpgOs_t *slices);
extern void AppGetUpgSystemSlices(char ***slice_array);
extern void AppFreeUpgSystemSlices(char **slice_array);
extern void AppGetUpgradeProgressStr(ValProgress *val_progress,
	char **main_label, char **detail_label);
extern char *AppGetUpgradeErrorStr(
	int error_code, char *release, char *slice);
extern TChildAction AppParentStartUpgrade(
	FSspace ***fs_space,
	UpgOs_t *slices,
	unsigned int *state,
	void (*confirm_exit_func)(void),
	void (*parent_reinit_func)(void *),
	void *parent_reinit_data);
extern parAction_t AppParentContinueUpgrade(
	TChildAction parent_resume, unsigned int *state,
	void (*exit_func)(int exit_code, void *exit_data));
extern void AppUpgradeGetProgressBarInfo(
	int index, int state, int *start, float *factor);

/* app_params.c */
extern char *ParamsGetCommonArgs(void);
extern void ParamsGetProgramName(char *prog, ParamUsage *param_usage);
extern void ParamsPrintUsage(ParamUsage *param_usage);
extern int ParamsParseCommonArgs(int argc, char **argv,
	ParamUsage *param_usage, Profile *profile);
extern void ParamsParseUIArgs(int argc, char **argv, ParamUsage *param_usage);
extern void ParamsValidateUILastArgs(int argc, int optindex,
	ParamUsage *param_usage);
extern void ParamsValidateCommonArgs(Profile *profile);

/* app_patchan.c */
extern PACheckRC PANeedsAnalysis(void);
extern PAAnalyzeRC PADoAnalysis(PAResults **results);
extern PAResults *PAGetResults(void);
extern void PAFreeResults(PAResults *results);

/* app_profile.c */
extern void	ProfileInitialize(Profile *profile);
extern int	configure_dfltmnts(Profile *);
extern int	configure_sdisk(Profile *);
extern char	*find_swap(int);
extern int	app_config_slice(Profile *, Storage *);

/* app_sw.c */
extern void initNativeArch(void);

/* app_utils.c */
extern int UI_ScalePercent(int real_percent, int scale_start,
	float scale_factor);
extern void UI_ProgressBarTrimDetailLabel(
	char *main_label,
	char *detail_label,
	int total_len);
extern char *
	UI_GetCheckDisksMessageStr(int errors, int warnings);
extern char *
	UI_GetNewErrorMsgFromStoreLib(Errmsg_t *error_item, void *extra);
extern	int	reset_system_state(void);

/* app_64bit.c */
extern int installedImageIsPre64Bit(void);

/* app_mirror_methods.c */
extern	int		setup_mirror_disk(Profile *, Storage *);
extern	int		setup_metadb_disk(Profile *);
extern	int		svm_create_mirror_script(Profile *);
extern	int		execute_mirror_script(char *, char *);
extern	char		*get_mirror_block_device(char *, int);
extern	char		*get_mirror_char_device(char *, int);
extern	int		is_slice_tobe_mirrored(char *, int);
extern	StringList	*get_all_mirror_parts(char *, int);

#ifdef __cplusplus
}
#endif

#endif	/* _SPMIAPP_API_H */
