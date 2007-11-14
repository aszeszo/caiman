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


#ifndef	_APP_STRINGS_H
#define	_APP_STRINGS_H

#pragma ident	"@(#)app_strings.h	1.19	07/10/09 SMI"

#ifdef	__cplusplus
extern "C" {
#endif

/*
 * This file contains strings that can appear in applications using these
 * libraries.
 */

#include <libintl.h>

/* constants */

#ifndef	TEXT_DOMAIN
#define	TEXT_DOMAIN	"SUNW_INSTALL_LIBAPP"
#endif

#ifndef ILIBSTR
#define	ILIBSTR(x)	dgettext(TEXT_DOMAIN, x)
#endif

/* BE common install parameter strings */

#define	APP_PARAMS_USAGE_HDR	ILIBSTR("%s options:\n")
#define	APP_PARAMS_PUBLIC_HDR	ILIBSTR("PUBLIC OPTIONS:\n")
#define	APP_PARAMS_PRIVATE_HDR	ILIBSTR(\
	"PRIVATE OPTIONS (use these at your own risk!):\n")
#define	APP_PARAMS_PREV_PUBLIC_USAGE ILIBSTR(\
	"\t[-c cdrom_base_directory]\n"\
	"\t[-d disk_configuration_file]\n"\
	"\t[-D] (for simulation using local disks)\n")
#define	APP_PARAMS_COMMON_PUBLIC_USAGE ILIBSTR(\
	"\t[-d disk_configuration_file]\n"\
	"\t[-D] (for simulation using local disks)\n")
#define	APP_PARAMS_COMMON_PRIVATE_USAGE ILIBSTR(\
	"\t[-h] (for usage summary)\n"\
	"\t[-x libstore_trace_level]\n")
#define	APP_PARAMS_TRAILING_OPTS_ERR	ILIBSTR("unknown trailing options.\n")

/* disk strings */
/* i18n: 9 chars max */
#define	APP_BOOTDRIVE   ILIBSTR("(boot disk)")

/* message strings */

#define	MSG0_INTERNAL_GET_DFLTMNT	ILIBSTR(\
	"Could not get default mount list")
#define	MSG0_INTERNAL_SET_DFLTMNT	ILIBSTR(\
	"Could not set default mount list")
#define	MSG1_DFLTMNT_FORCE_IGNORE	ILIBSTR(\
	"Force DFLT_IGNORE (%s)")
#define	MSG1_DFLTMNT_FORCE_SELECT	ILIBSTR(\
	"Force DFLT_SELECT (%s)")
#define	MSG0_DFLTMNT_CLEAR		ILIBSTR(\
	"Force DFLT_IGNORE on all mount points")
#define	MSG0_INTERNAL_FREE_DFLTMNT	ILIBSTR(\
	"Could not free default mount list")
#define	MSG1_INTERNAL_DISK_RESET	ILIBSTR(\
	"Could not initialize state (%s)")
#define	MSG2_SLICE_REALIGNED		ILIBSTR(\
	"Slice %s has been realigned to cylinder boundaries (%s)")
#define	MSG2_SLICE_ALIGN_REQUIRED	ILIBSTR(\
	"%s must be cylinder aligned (%s)")
#define	MSG2_SLICE_PRESERVE		ILIBSTR(\
	"Preserving slice %s (%s)")
#define	MSG1_SLICE_PRESERVE_FAILED	ILIBSTR(\
	"Could not preserve slice (%s)")
#define	MSG2_SLICE_EXISTING		ILIBSTR(\
	"Preserving existing geometry for %s (%s)")
#define	MSG0_STD_UNNAMED		ILIBSTR(\
	"unnamed")
#define	MSG0_DEFAULT_CONFIGURE_ALL	ILIBSTR(\
	"Automatically configuring disks for Solaris operating system")
#define	MSG0_DEFAULT_CONFIGURE_FAILED	ILIBSTR(\
	"Could not automatically configure disks")
#define	MSG2_SLICE_CONFIGURE		ILIBSTR(\
	"Configuring %s (%s)")
#define	MSG0_EXISTING_FS_SIZE_INVALID	ILIBSTR(\
	"Existing partitioning requires a size of \"existing\"")
#define	MSG1_NO_ALL_FREE_DISK		ILIBSTR(\
	"No completely free disk available (%s)")
#define	MSG1_DISK_INVALID		ILIBSTR(\
	"Disk is not valid on this machine (%s)")
#define	MSG2_START_CYL_INVALID		ILIBSTR(\
	"Starting cylinder (%d) precedes first available cylinder (%d)")
#define	MSG2_CYL_INVALID_FOR_PLAT	ILIBSTR(\
	"cylinder range (%d-%d) for filesystem / exceeds allowable " \
	"cylinder for this system (%d)")
#define	MSG1_START_CYL_EXCEEDS_DISK	ILIBSTR(\
	"Starting cylinder exceeds disk capacity (%d)")
#define	MSG2_TRACE_AUTO_SIZE		ILIBSTR(\
	"Auto size is %d sectors (~%d MB)")
#define	MSG1_DEFAULT_SIZE_INVALID	ILIBSTR(\
	"No default size (%s)")
#define	MSG2_SLICE_SIZE_NOT_AVAIL	ILIBSTR(\
	"No %d MB slice available (%s)")
#define	MSG1_SLICE_NOT_AVAIL		ILIBSTR(\
	"No unused slice available (%s)")
#define	MSG0_STD_UNNAMED		ILIBSTR(\
	"unnamed")
#define	MSG2_SLICE_ANY_BECOMES		ILIBSTR(\
	"\"any\" for %s becomes \"%s\"")
#define	MSG1_SLICE_GEOM_SET_FAILED	ILIBSTR(\
	"Could not fit slice on disk (%s)")
#define	MSG1_DISK_NOT_FREE		ILIBSTR(\
	"All slices are in use (%s)")
#define	MSG0_DISKS_NOT_FREE		ILIBSTR(\
	"No disk is completely free")
#define	MSG1_SLICE_NOT_AVAIL		ILIBSTR(\
	"No unused slice available (%s)")
#define	MSG1_SLICE_PRESERVE_OFF_FAILED	ILIBSTR(\
	"Could not disable preserve on slice (%s)")
#define	MSG1_SLICE_IGNORE		ILIBSTR(\
	"Ignoring slice (%s)")
#define	MSG1_SLICE_IGNORE_FAILED	ILIBSTR(\
	"Could not ignore slice (%s)")

/*
 * Mirror related messages
 */
#define	MSG0_READ_ONLY			ILIBSTR(\
	"Read-only")
#define	MSG0_SETUP			ILIBSTR(\
	"setup")
#define	MSG0_SUBMIRRORS			ILIBSTR(\
	"submirrors")
#define	MSG0_METAINIT			ILIBSTR(\
	"metainit")
#define	MSG0_MIRROR_VOLUME		ILIBSTR(\
	"Mirror Volume")
#define	MSG0_METADB_SLICE_CONFIGURE	ILIBSTR(\
	"Creating SVM State Replica on disk")
#define	MSG0_MIRROR_SLICE_CONFIGURE	ILIBSTR(\
	"Creating SVM Mirror Volume")
#define	MSG0_MIRROR_ROOT_DEVICE		ILIBSTR(\
	"Making SVM Mirror Volume as boot device")
#define	MSG1_MIRROR_LOG_FAILED	ILIBSTR(\
	"Failed to obtain log information for mirror creation: %s")
#define	MSG2_SVM_SLICE2_IS_SMALL	ILIBSTR(\
	"SVM mirroring is not possible. submirror2 (%s) is smaller " \
	"than the submirror1 (%s)")
#define	MSG3_METADEVICE_CONFIGURE	ILIBSTR(\
	"Configuring SVM %s on %s (%s)")
#ifdef	__cplusplus
}
#endif

#endif	/* _APP_STRINGS_H */
