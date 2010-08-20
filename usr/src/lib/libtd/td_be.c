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
 * Copyright (c) 2008, 2010, Oracle and/or its affiliates. All rights reserved.
 */

/*
 * Snap BE discovery for Target Discovery module
 */
#include <unistd.h>
#include <libnvpair.h>
#include <strings.h>
#include <td_lib.h>
#include <td_api.h>
#include <ls_api.h>
#include <libbe.h>

#define	TDMOD "TDMG"	/* module to display in log messages */

/*
 * td_be_list()
 * calls add_td_discovered_obj(TD_OT_OS, onvl) to add to list of discovered OSs
 *
 * Parses the output of 'zpool import', finding slices and marking them
 * as pool members for install disk display
 */
void
td_be_list()
{
	char cmd[MAXPATHLEN] = "/usr/sbin/zpool import";
	FILE *pipfp;
	char rpobuf[MAXPATHLEN];	/* popen() output buffer */
	char slicenm[MAXPATHLEN];

	ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO, "executing %s\n", cmd);
	if ((pipfp = popen(cmd, "r")) == NULL)
		return;
	/*
	 * parse zpool status command
	 * scan for slices in column 1
	 */
	while (fgets(rpobuf, sizeof (rpobuf), pipfp) != NULL) {
		char label[132];
		char status[132];
		int nsc;
		nvlist_t *onvl;

		nsc = sscanf(rpobuf, "%s %s", label, status);
		if (nsc < 2)
			continue;
		(void) snprintf(slicenm, sizeof (slicenm),
		    "/dev/dsk/%s", label);
		if (!td_is_slice(label))
			continue;
		ls_write_dbg_message(TDMOD,
		    LS_DBGLVL_INFO,
		    "found device %s\n", slicenm);
		/* pool member found */
		if (nvlist_alloc(&onvl, NV_UNIQUE_NAME, 0) != 0) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
			    "nvlist allocation failure\n");
			continue;
		}	/* allocate list */
		/* release string */
		if (nvlist_add_string(onvl, TD_OS_ATTR_BUILD_ID,
		    "Pool member") != 0) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
			    "nvlist add_string failure\n");
			nvlist_free(onvl);
			continue;
		}
		/* add slice name to attribute list */
		if (nvlist_add_string(onvl, TD_OS_ATTR_SLICE_NAME, label)
		    != 0) {
			ls_write_dbg_message(TDMOD, LS_DBGLVL_ERR,
			    "nvlist add_string failure\n");
			nvlist_free(onvl);
			continue;
		}

		/* add BE to list of known Solaris instances */
		add_td_discovered_obj(TD_OT_OS, onvl);
	}
	(void) pclose(pipfp);
	ls_write_dbg_message(TDMOD, LS_DBGLVL_INFO,
	    "finishing td_be_list\n");
}
