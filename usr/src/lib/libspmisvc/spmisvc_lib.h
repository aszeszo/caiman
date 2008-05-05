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



#ifndef _SPMISVC_LIB_H
#define	_SPMISVC_LIB_H


/*
 * Module:	spmisvc_lib.h
 * Group:	libspmisvc
 * Description:
 */

#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>
#include <string.h>
#include <sys/param.h>
#include <sys/types.h>
#include <sys/vfstab.h>
#include <spmicommon_api.h>
#include <spmisoft_api.h>
#include <spmisvc_api.h>
#include "spmiapp_api.h"
#include <spmizones_api.h>

/*
 * macros usefule for debugging
 */
#define	SPMI_SVCLIB_NAME	"LIBSPMISVC"
#define	SVC_DEBUG(_debug_trace_level)	\
	LOGSCR, (get_trace_level() >= _debug_trace_level),\
	SPMI_SVCLIB_NAME, DEBUG_LOC
#define	SVC_DEBUG_NOHD(_debug_trace_level)	\
	LOGSCR, (get_trace_level() >= _debug_trace_level),\
	NULL, DEBUG_LOC
#define	SVC_DEBUG_L1(_debug_trace_level)	\
	SVC_DEBUG(_debug_trace_level), LEVEL1
#define	SVC_DEBUG_L1_NOHD(_debug_trace_level)	\
	SVC_DEBUG_NOHD(_debug_trace_level), LEVEL1

/* constants */

#define	NUMDEFMNT	11	/* number of default resource entries */

#define	DIRECT_INSTALL	 \
	(*get_rootdir() == '\0' || strcmp(get_rootdir(), "/") == 0 ? 1 : 0)
#define	INDIRECT_INSTALL \
	(*get_rootdir() != '\0' && strcmp(get_rootdir(), "/") != 0 ? 1 : 0)

/* common path names */
#define	TMPLOGFILE		"/tmp/install_log"
#define	IDKEY			"/kernel/misc/sysinit"
#define	IDKEY64			"/kernel/misc/amd64/sysinit"
#define	IDSAVE			"/.atconfig"
#define	TRANS_LIST		"/etc/transfer_list"
#define	SYS_ADMIN_DIRECTORY	"/var/sadm/system/admin"
#define	SYS_SERVICES_DIRECTORY	"/var/sadm/system/admin/services"
#define	SYS_DATA_DIRECTORY	"/var/sadm/system/data"
#define	SYS_LOGS_DIRECTORY	"/var/sadm/system/logs"
#define	HW_CAP_TESTS_DIRECTORY	"/usr/sbin/install.d/hardware_checks"
#define	DEVMAP_SCRIPTS_DIRECTORY	"/usr/sadm/install/devmap_scripts"

/* pkgadd valid returns */
#define	PKGREBOOT	10
#define	PKGIREBOOT	20

/* data structures */

typedef struct vfs_entry {
	struct vfstab		*entry;
	struct vfs_entry 	*next;
} Vfsent;

/* tranfser file type */
typedef struct trans_type {
	TType	type;		/* type of transfer file		*/
	char	*mergescript;	/* name of mergescript to use		*/
} TransType;

/* transfer file elements */
typedef struct trans_file_element {
	char	*file;		/* name of a transition file		*/
	char	*package;	/* name of package containing file	*/
	int	found;		/* a status flag			*/
	TransType *transtype;	/* type of transfer file		*/
	mode_t	mode;		/* File mode 				*/
	uid_t	uid;		/* User ID of the file's owner		*/
	gid_t	gid;		/* Group ID of the file's group		*/
} TransList;

/* -------------------------------------------------------------- */
/*		system resource data elements			  */
/* -------------------------------------------------------------- */

/* comparison constraint bits for checkpoint */

#define	CHECKPOINT_DISKS	0x01
#define	CHECKPOINT_RESOURCES	0x02
#define	CHECKPOINT_ALL		(CHECKPOINT_DISKS | CHECKPOINT_RESOURCES)

/*
 * Checkpoint handle structure to hold resource and disk configuration status
 * information for autolayout checkpointing
 */
typedef struct {
	ResStatEntry *	resources;
	Disk_t		*disks;
} Checkpoint;

typedef void *		CheckHandle;

/*
 * Flags identifying the degree of privilege in a call - used to support
 * common call interfaces for internal and external use
 */
#define	NOPRIVILEGE	0
#define	PRIVILEGE	1

/*
 * Resource state object indicating the status and status modifiability
 * for a given system type
 */
typedef struct {
	ResStat_t	status;		/* resource storage allocation status */
	ResMod_t	modify;		/* status modification permissions */
} ResState;

/*
 * Resource state object holding all storage allocation and modification
 * statuses for all supported installation system types
 */
typedef struct {
	ResState	standalone;	/* standalone (MT_STANDALONE) */
	ResState	server;		/* server (MT_SERVER) system type */
	ResState	autoclient;	/* autoclient (cacheos/MT_CCLIENT) */
} Sysstat;

/*
 * Resource object device layout contraints used to pass storage configuration
 * requirements and preferences to auto-layout
 */
typedef struct {
	int	default_device;		/* default slice for layout	*/
	int	explicit_size;		/* explicit size specified by	*/
					/* user				*/
	int	explicit_start;		/* explicit start cylinder	*/
					/* specified by	user		*/
	int	explicit_minimum;	/* explicit minimum size	*/
					/* allowed			*/
	char	explicit_disk[MAXPATHLEN]; /* disk required "" if	*/
					/* unspecified			*/
	int	explicit_device;	/* slice required; WILD_SLICE	*/
					/* if unspecified		*/
	char	preferred_disk[MAXPATHLEN]; /* disk preferred for layout */
					/* "" if unspecified		*/
	int	preferred_device;	/* slice preferred; WILD_SLICE	*/
					/* if unspecified		*/
} Devconst;

/*
 * Resource object content requirements containing all content
 * obligations associated with the resource
 */
typedef struct {
	ResClass_t	class;	   /* content classification */
	int		software;  /* # of sectors required for software */
	int		extra;	   /* # of sectors required for extra */
	int		services;  /* # of sectors required for service */
} Content;

/*
 * Resource object file system parameters and directives used to
 * direct auto-layout and back-end installation processes for
 * directory resources which have independent storage
 */
typedef struct {
	FsAction_t	action;		/* file system creation status */
	char		*mount_options;
	int		minfree;
	int		percentfree;
} Filesys;

/*
 * Resourc object
 */
typedef struct resobj {
	char		name[MAXPATHLEN]; /* name */
	int		instance;	  /* instance */
	ResType_t	type;		  /* type */
	ResOrigin_t	origin;		  /* origin */
	Sysstat		state;		  /* storage allocation data */
	Content		content;	  /* content requirements data */
	Devconst	layout;		  /* device layout constraints */
	Filesys		filesys;	  /* file system specific info */
	struct resobj	*next;
} Resobj;

/*
 * Resource object access macros
 */
#define	Resobj_Name(r)			(((Resobj *)(r))->name)
#define	Resobj_Instance(r)		(((Resobj *)(r))->instance)
#define	Resobj_Type(r)			(((Resobj *)(r))->type)
#define	Resobj_Origin(r)		(((Resobj *)(r))->origin)
#define	Resobj_Next(r)			(((Resobj *)(r))->next)
#define	Resobj_Content_Class(r)		(((Resobj *)(r))->content.class)
#define	Resobj_Content_Software(r)	(((Resobj *)(r))->content.software)
#define	Resobj_Content_Extra(r)   	(((Resobj *)(r))->content.extra)
#define	Resobj_Content_Services(r)   	(((Resobj *)(r))->content.services)
#define	Resobj_Layout(r)		(((Resobj *)(r))->layout)
#define	Resobj_Dev_Explmin(r)		(Resobj_Layout((r)).explicit_minimum)
#define	Resobj_Dev_Explstart(r)		(Resobj_Layout((r)).explicit_start)
#define	Resobj_Dev_Explsize(r)		(Resobj_Layout((r)).explicit_size)
#define	Resobj_Dev_Expldevice(r)	(Resobj_Layout((r)).explicit_device)
#define	Resobj_Dev_Expldisk(r)		(Resobj_Layout((r)).explicit_disk)
#define	Resobj_Dev_Dfltdevice(r)	(Resobj_Layout((r)).default_device)
#define	Resobj_Dev_Prefdevice(r)	(Resobj_Layout((r)).preferred_device)
#define	Resobj_Dev_Prefdisk(r)		(Resobj_Layout((r)).preferred_disk)
#define	Resobj_Fs(r)			(((Resobj *)(r))->filesys)
#define	Resobj_Fs_Mountopts(r)		(Resobj_Fs((r)).mount_options)
#define	Resobj_Fs_Minfree(r)		(Resobj_Fs((r)).minfree)
#define	Resobj_Fs_Percentfree(r)	(Resobj_Fs((r)).percentfree)
#define	Resobj_Fs_Action(r)		(Resobj_Fs((r)).action)

#define	Resobj_State(r)			(((Resobj *)(r))->state)
#define	Resobj_Standalone_Status(r)	(Resobj_State((r)).standalone.status)
#define	Resobj_Server_Status(r)		(Resobj_State((r)).server.status)
#define	Resobj_Autoclient_Status(r)	(Resobj_State((r)).autoclient.status)
#define	Resobj_Standalone_Modify(r)	(Resobj_State((r)).standalone.modify)
#define	Resobj_Server_Modify(r)		(Resobj_State((r)).server.modify)
#define	Resobj_Autoclient_Modify(r)	(Resobj_State((r)).autoclient.modify)
#define	Resobj_Modify(r)		(get_machinetype() == MT_STANDALONE ? \
					    Resobj_Standalone_Modify((r)) : \
					    get_machinetype() == MT_SERVER ? \
					    Resobj_Server_Modify((r)) : \
					    get_machinetype() == MT_CCLIENT ? \
					    Resobj_Autoclient_Modify((r)) : \
					    RESMOD_UNDEFINED)
#define	Resobj_Status(r)		(get_machinetype() == MT_STANDALONE ? \
					    Resobj_Standalone_Status((r)) : \
					    get_machinetype() == MT_SERVER ? \
					    Resobj_Server_Status((r)) : \
					    get_machinetype() == MT_CCLIENT ? \
					    Resobj_Autoclient_Status((r)) : \
					    RESSTAT_UNDEFINED)

/*
 * Resource object test macros
 */
#define	ResobjIsValidName(n)	    ((n) != NULL && (streq((n), SWAP) || \
						NameIsPath((n)) || \
						streq((n), "")))
#define	ResobjIsValidInstance(n)    ((n) == VAL_UNSPECIFIED || (n) >= 0)
#define	ResobjIsDirectory(r)	    (Resobj_Type((Resobj *)(r)) == \
						RESTYPE_DIRECTORY)
#define	ResobjIsUnnamed(r)	    (Resobj_Type((Resobj *)(r)) == \
						RESTYPE_UNNAMED)
#define	ResobjIsSwap(r)		    (Resobj_Type((Resobj *)(r)) == \
						RESTYPE_SWAP)
#define	ResobjIsIgnored(r)	    (Resobj_Status((Resobj *)(r)) == \
						RESSTAT_IGNORED)
#define	ResobjIsDependent(r)	    (Resobj_Status((Resobj *)(r)) == \
						RESSTAT_DEPENDENT)
#define	ResobjIsIndependent(r)	    (Resobj_Status((Resobj *)(r)) == \
						RESSTAT_INDEPENDENT)
#define	ResobjIsOptional(r)	    (Resobj_Status((Resobj *)(r)) == \
						RESSTAT_OPTIONAL)
#define	NameIsSwap(n)		    (streq((n), SWAP))
#define	NameIsOverlap(n)	    (streq((n), OVERLAP))
#define	NameIsNull(n)		    (streq((n), ""))
#define	NameIsPath(n)		    (is_pathname((n)))

#define	WALK_RESOURCE_LIST_PRIV(r, t)    for ((r) = ResobjFirstPriv((t)); \
						(r) != NULL; \
						(r) = ResobjNextPriv((r), (t)))

/*
 * Flash macros
 */

#define	FLASH_COOKIE_STATIC	"FlAsH-aRcHiVe-"
#define	FLASH_SECTION_BEGIN	"section_begin"
#define	FLASH_SECTION_END	"section_end"
#define	FLASH_SECTION_IDENT	"identification"
#define	FLASH_SECTION_FILES	"archive"

#define	FLASH_SECTION_PREDEPLOYMENT	"predeployment"
#define	FLASH_SECTION_POSTDEPLOYMENT	"postdeployment"
#define	FLASH_SECTION_REBOOT		"reboot"
#define	FLASH_SECTION_MANIFEST		"manifest"

#define	FLASH_MINIMUM_MAJOR		1
#define	FLASH_TYPE_INTRODUCED_MAJOR	2
#define	FLASH_MAXIMUM_MAJOR		2

#define	FLASH_KNOWN_MINOR	0

/* function prototypes */

#ifdef __cplusplus
extern "C" {
#endif

/* svc_checkpoint.c */
int		CheckpointCompare(Label_t, Disk_t *, CheckHandle, u_char);
CheckHandle	CheckpointCreate(void);
int		CheckpointDestroy(CheckHandle);
int		CheckpointRestore(CheckHandle, u_char);

/* svc_dfltrsrc.c */
ResobjHandle	ResobjCreatePriv(ResType_t, char *, int, ...);
int		ResobjDestroyPriv(ResobjHandle);
int		ResobjGetAttributePriv(ResobjHandle, ...);
int		ResobjSetAttributePriv(ResobjHandle, ...);
ResobjHandle	ResobjFindPriv(char *, int);
ResobjHandle	ResobjFirstPriv(ResType_t);
ResobjHandle	ResobjNextPriv(ResobjHandle, ResType_t);

/* svc_flash.c */
char		*FLARArchiveWhere(FlashArchive *);
char		*FLARArchiveType(FlashArchive *);
FlashError	FLARInitialPreDeployment(FlashArchive *, char *);
FlashError	FLARPostDeployment(FlashArchive *, char *);
FlashError	FLARUpdatePreDeployment(FlashArchive *, char *,	int, int, int);

/* svc_global.c */
int		GlobalSetAttributePriv(GlobalAttr_t, void *);
int		GlobalGetAttributePriv(GlobalAttr_t, void *);

/* svc_sdiskfreespace.c */
int		SegmentFindEnd(Disk_t *, int);
int		SegmentFindFreeSectors(Disk_t *, int, int);

/* svc_fs_space.c */
ulong		new_slice_size(ulong, ulong, int, ulong *, ulong *,
			ulong *);

/* svc_updateconfig.c */
int		_setup_bootblock(void);
int		_clean_devices(void);
int		_setup_devices(void);
int		_setup_etc_hosts(Dfs *);
int		_setup_i386_bootrc(Disk_t *, int);
int		_setup_tmp_root(TransList **);
int		_setup_vfstab(OpType, Vfsent **);
int		_setup_vfstab_unselect(void);
int		SystemConfigProm(void);
int		_setup_transferlist(TransList **);
int		_unconfigure_system(void);
int		_suppress_solstart(void);
int		_update_etc_default_init(void);

/* svc_updatedisk.c */
int		_setup_disks(Disk_t *, Vfsent *, int, int);
void 		_swap_add(Disk_t *);

/* svc_updateserial.c */
int		_setup_hostid(void);

/* svc_updatesoft.c */
int		_setup_software(Module *, TransList **, TCallback *, void *);
int		_atconfig_restore(void);
int		_atconfig_store(void);

/* svc_vfstab.c */
int		_create_mount_list(Disk_t *, Dfs *, Vfsent **);
void		_free_mount_list(Vfsent **);
int		_merge_mount_entry(struct vfstab *, Vfsent **);
int		_mount_add_local_entry(Vfsent **, Disk_t *, int);
int		_mount_add_remote_entry(Dfs *, Vfsent **);
int 		_mount_filesys_all(OpType, Vfsent *, int);
int		_mount_remaining(Vfsent *vlist);
int		_mount_filesys_specific(char *, struct vfstab *);
void		_mount_list_print(Vfsent **);
void		_mount_list_sort(Vfsent **);
int		_merge_mount_list(OpType, Vfsent **);
int		_mount_synchronous_fs(struct vfstab *, Vfsent *);
void		_vfstab_free_entry(struct vfstab *);

/* svc_mountall.c */
int		gen_mount_script(FILE *, int);
void		gen_umount_script(FILE *);
int		umount_root(void);
void		gen_installboot(FILE *);
int		mount_zones(void);

/* svc_resource.c */
int		ResobjIsGuardian(ResobjHandle, ResobjHandle);
int		_filesys_boot_critical(char *);

/* write_script.c */
int		write_script(Module *, int);
void		scriptwrite(FILE *, uint, char **, ...);
void		set_umount_script_fcn(int (*)(FILE *, int), void (*)(FILE *));
char		*upgrade_script_path(Product *);
char		*upgrade_log_path(Product *);
void		generate_swm_script(char *);

#ifdef __cplusplus
}
#endif

#endif	/* _SPMISVC_LIB_H */
