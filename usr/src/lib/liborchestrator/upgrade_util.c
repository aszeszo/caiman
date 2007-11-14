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

#pragma ident	"@(#)upgrade_util.c	1.1	07/08/03 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "spmizones_api.h"
#include "spmiapp_api.h"
#include "orchestrator_private.h"

/*
 * Name:	init_spmi_for_upgrade_check
 * Description:	Initializes the spmi library global variables, structures
 *		so that upgrade target can be checked.
 *		This duplicates all the initialization done by pfinstall
 *		before upgrade.
 * Scope:	private
 * Arguments:	None
 * Returns:	None
 */
void
init_spmi_for_upgrade_check()
{
	char	*root_dir = "/a";

	DiskobjInitList(NULL);
	ResobjInitList();
	set_rootdir(root_dir);
	z_set_zone_root(root_dir);
	(void) set_install_type(CMNUpgrade);
	(void) set_profile_upgrade();
	(void) sw_lib_init(PTYPE_UNKNOWN);
	set_percent_free_space(1);
}
/*
 * Name:	configure_software
 * Description:	Configure the software, selecting the requested metacluster,
 *		and marking the required metacluster as required.
 * Scope:	private
 * Arguments:	meta	- [RO, *RO] (char *)
 *			  The name of the metacluster to select
 * Returns:	0 - Requested metacluster found and selected
 *		-1 - Requested metacluster not found
 */
int
configure_software(char *meta)
{
	Module *m;
	static int first = 1;
	static boolean_t found = B_FALSE;

	/* Deselect all but the requested metacluster */
	for (m = get_head(get_current_metacluster()); m; m = get_next(m)) {
		mark_module(m, UNSELECTED);
	}

	/* Select the requested metacluster */
	for (m = get_head(get_current_metacluster()); m; m = get_next(m)) {
		if (streq(m->info.mod->m_pkgid, meta)) {
			mark_module(m, SELECTED);
			found = B_TRUE;
		} else if (streq(m->info.mod->m_pkgid, REQD_METACLUSTER) &&
		    first == 1) {
			first = 0;
			mark_required(m);
		}
	}

	if (found) {
		return (0);
	} else {
		return (-1);
	}
}

/*
 * Copied from the libspmisvc/svc_sp_print_results.c:_final_results()
 * This is called by the upgrade validation function to print the space
 * data structure in the case of insufficient space
 */
void
print_space_results(FSspace **sp, char *outfile)
{
	int		i, inode_err;
	FILE		*fp = NULL;
	char		inode_flag;

	if (outfile) {
		fp = fopen(outfile, "w");
		if (fp == (FILE *)NULL) {
			return;
		}
		(void) chmod(outfile, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH);
	}

	if (fp) {
		/*
		 * Print Current slice size and suggested slice size.
		 */
		(void) fprintf(fp, "%-20s%-20s%-20s%-20s\n",
		    "", "",
		    dgettext("SUNW_INSTALL_LIBSVC", "Current Size"),
		    dgettext("SUNW_INSTALL_LIBSVC", "Minimum Suggested"));

		(void) fprintf(fp, "%-20s%-20s%-20s%-20s\n",
		    dgettext("SUNW_INSTALL_LIBSVC", "Mount Point"),
		    dgettext("SUNW_INSTALL_LIBSVC", "Slice"),
		    dgettext("SUNW_INSTALL_LIBSVC", "1 Kilobyte Blocks"),
		    dgettext("SUNW_INSTALL_LIBSVC", "1 Kilobyte Blocks"));

		(void) fprintf(fp, "----------------------------------------");
		(void) fprintf(fp, "---------------------------------------\n");
	}

	inode_err = 0;

	/*
	 * Run through the list and print out all of the file systems
	 * that have failed due to space limitations.
	 */

	if (fp) {
		(void) fprintf(fp, "%s\n",
		    dgettext("SUNW_INSTALL_LIBSVC",
		    "File systems with insufficient space."));
	}
	for (i = 0; sp[i]; i++) {
		if (sp[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;

		if (sp[i]->fsp_fsi == NULL) {
			continue;
		}

		if (!(sp[i]->fsp_flags & FS_INSUFFICIENT_SPACE))
			continue;

		inode_flag = ' ';

		if (sp[i]->fsp_cts.contents_inodes_used >
		    sp[i]->fsp_fsi->f_files) {
			inode_flag = '*';
			inode_err++;
		}
		if (fp) {
			if ((int)strlen(sp[i]->fsp_mntpnt) > (int)19) {
				(void) fprintf(fp, "%s\n", sp[i]->fsp_mntpnt);
				(void) fprintf(fp,
				    "%-20s%-20s%-20ld%-18ld%c\n", "",
				    sp[i]->fsp_fsi->fsi_device,
				    sp[i]->fsp_cur_slice_size,
				    sp[i]->fsp_reqd_slice_size, inode_flag);
			} else {
				(void) fprintf(fp, "%-20s%-20s%-20ld%-18ld%c\n",
				    sp[i]->fsp_mntpnt,
				    sp[i]->fsp_fsi->fsi_device,
				    sp[i]->fsp_cur_slice_size,
				    sp[i]->fsp_reqd_slice_size, inode_flag);
			}
		}
	}

	/*
	 * Now run through the list and print out all of the remaining
	 * file systems
	 */

	if (fp) {
		(void) fprintf(fp, "\n");
		(void) fprintf(fp, "%s\n",
		    dgettext("SUNW_INSTALL_LIBSVC",
		    "Remaining file systems."));
	}
	for (i = 0; sp[i]; i++) {
		if (sp[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;

		if (sp[i]->fsp_fsi == NULL) {
			continue;
		}

		if (sp[i]->fsp_flags & FS_INSUFFICIENT_SPACE)
			continue;

		inode_flag = ' ';

		if (sp[i]->fsp_cts.contents_inodes_used >
		    sp[i]->fsp_fsi->f_files) {
			inode_flag = '*';
			inode_err++;
		}
		if (fp) {
			if ((int)strlen(sp[i]->fsp_mntpnt) > (int)19) {
				(void) fprintf(fp, "%s\n", sp[i]->fsp_mntpnt);
				(void) fprintf(fp,
				    "%-20s%-20s%-20ld%-18ld%c\n", "",
				    sp[i]->fsp_fsi->fsi_device,
				    sp[i]->fsp_cur_slice_size,
				    sp[i]->fsp_reqd_slice_size, inode_flag);
			} else {
				(void) fprintf(fp, "%-20s%-20s%-20ld%-18ld%c\n",
				    sp[i]->fsp_mntpnt,
				    sp[i]->fsp_fsi->fsi_device,
				    sp[i]->fsp_cur_slice_size,
				    sp[i]->fsp_reqd_slice_size, inode_flag);
			}
		}
	}

	if (fp && inode_err) {
		(void) fprintf(fp, "\n%s\n", dgettext("SUNW_INSTALL_LIBSVC",
"Slices marked with a '*' have an insufficient number of inodes available."));
		(void) fprintf(fp, "%s\n",
		    dgettext("SUNW_INSTALL_LIBSVC",
		    "See newfs(1M) for details on how to increase"\
		    " the number of inodes per slice."));
	}
	if (fp) {
		(void) fclose(fp);
	}
}
