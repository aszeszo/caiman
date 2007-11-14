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

#pragma ident	"@(#)app_utils.c	1.7	07/10/09 SMI"


/*
 * Module:	app_utils.c
 * Group:	libspmiapp
 * Description:
 */

#include <assert.h>
#include <stdio.h>
#include <stdarg.h>
#include <strings.h>
#include <stdlib.h>

#include "spmiapp_api.h"
#include "app_utils.h"
#include "spmizones_lib.h"

int
UI_ScalePercent(int real_percent, int scale_start, float scale_factor)
{
	int factored_percent;
	int final_percent;

	factored_percent = (int)(real_percent * scale_factor);
	final_percent = scale_start + factored_percent;
	if (final_percent > 100)
		final_percent = 100;
	return (final_percent);
}

/*
 * Function: UI_ProgressBarTrimDetailLabel
 * Description:
 *	Routine to trim the secondary label in the progress bars if
 *	necessary to ensure that the detail label is not too long.
 * Scope:	PUBLIC
 * Parameters:
 *	char *main_label: main label
 *	char *detail_label: secondary label we want to trim, if necessary
 *		- trimmed version in here if it's changed
 *	int total_len: total length of "main label: detail label" string
 * Return: none
 * Globals: none
 * Notes:
 */
#define	APP_UI_UPG_PROGRESS_CUT_STR	"..."
void
UI_ProgressBarTrimDetailLabel(
	char *main_label,
	char *detail_label,
	int total_len)
{
	int main_len;
	int detail_len;

	if (!detail_label)
		return;

	write_debug(APP_DEBUG_L1, "Original detail label: %s\n", detail_label);

	if (main_label)
		main_len = strlen(main_label) + 2;
	else
		main_len = 0;

	if (detail_label)
		detail_len = strlen(detail_label);
	else
		detail_len = 0;

	if ((main_len + detail_len) > total_len) {
		detail_len = total_len - main_len -
			strlen(APP_UI_UPG_PROGRESS_CUT_STR);
		if (detail_len < 0) {
			/*
			 * If there is no room at all for the detail
			 * label, just null it out.
			 * Note that if the main label is too long,
			 * we're not handling that here.  This is just to
			 * trim the detail label, since that is usually a
			 * file name or package name that has gotten out
			 * of control, whereas the main label should be
			 * some constant string defined or provided by
			 * L10N that should be a reasonable length to
			 * begin with.
			 */
			detail_label[0] = '\0';
		} else {
			/*
			 * Cut off the detail label and append "..."
			 * so they know there's more to it.
			 */
			(void) strcpy(&detail_label[detail_len],
				APP_UI_UPG_PROGRESS_CUT_STR);
			detail_label[detail_len +
				strlen(APP_UI_UPG_PROGRESS_CUT_STR)] = '\0';
		}
	}

	write_debug(APP_DEBUG_L1, "Trimmed detail label: %s\n", detail_label);

}

/*
 * Function: UI_GetCheckDisksMessageStr
 * Description:
 *	Return the message text string (not the error string itself)
 *	used in the CUI/GUI error/warning dialog that is popped up
 *	with all the check_disks() errors.
 * Scope:	PUBLIC
 * Parameters:
 *	int errors: are there any errors to report.
 *	int warnings: are there any warnings to report.
 * Return: char *: the message text string (dynamically allocated - the
 *	caller should deallocate).
 * Globals: none
 * Notes:
 */
/*ARGSUSED*/
char *
UI_GetCheckDisksMessageStr(int errors, int warnings)
{
	return (xstrdup(APP_ER_CHECK_DISKS));
}

/*
 * Function: UI_GetNewErrorMsgFromStoreLib
 * Description:
 *	Redo some of the lame error messages that come out of the
 *	store library into something presentable for the UI's.
 *
 * Scope:	PUBLIC
 * Parameters:
 *	Errmsg_t *error_item: the error item from the library
 *	void *extra: any extra data that may be needed for each type of
 *	error so we can make data specific messages if we want.
 * Return: char *: the message text string (dynamically allocated - the
 *	caller should deallocate).
 * Globals: none
 * Notes:
 */
/*ARGSUSED*/
char *
UI_GetNewErrorMsgFromStoreLib(Errmsg_t *error_item, void *extra)
{
	switch (error_item->code) {
	case D_PROMMISCONFIG:
		/*
		 * the prom needs to be changed and install is not doing
		 * it - you should.
		 */
		if (IsIsa("i386")) {
			return (xstrdup(APP_WARN_BOOT_PROM_CHANGE_REQ_x86));
		} else {
			return (xstrdup(APP_WARN_BOOT_PROM_CHANGE_REQ_SPARC));
		}
		/*NOTREACHED*/
		break;
	case D_PROMRECONFIG:
		/*
		 * the prom will be changed by install
		 */
		if (IsIsa("i386")) {
			return (xstrdup(APP_WARN_BOOT_PROM_CHANGING_x86));
		} else {
			return (xstrdup(APP_WARN_BOOT_PROM_CHANGING_SPARC));
		}
		/*NOTREACHED*/
		break;
	default:
		if (error_item->msg)
			return (xstrdup(error_item->msg));
		else
			return (xstrdup(""));
	}
}

/*
 * Function:    reset_system_state
 * Description: Routine used to reset the state of the system. Resetting
 *      includes:
 *
 *      (1) halt all running newfs and fsck processes which
 *          may still be active
 *      (2) unregister all currently active swap devices
 *      (3) unmount all filesystems registered in /etc/mnttab
 *          to be mounted under /a (NOTE: this must be done after
 *          killing fscks or a "busy" may be recorded)
 * Scope:   public
 * Parameters:  none
 * Return:   0  - reset successful
 *      -1  - reset failed
 */
int
reset_system_state(void)
{

	/* if running an any simulation, return immediately */
	if (GetSimulation(SIM_ANY)) {
		return (0);
	}
	/* BEGIN CSTYLED */
	if (system("ps -e | egrep newfs >/dev/null 2>&1") == 0) {
		(void) system("kill -9 `ps -e | egrep newfs | \
		awk '{print $1}'` \
		    `ps -e | egrep mkfs | awk '{print $1}'` \
		    `ps -e | egrep fsirand | awk '{print $1}'` \
		    > /dev/null 2>&1");
	}
	if (system("ps -e | egrep fsck >/dev/null 2>&1") == 0) {
		(void) system("kill -9 `ps -e | egrep fsck | awk '{print $1}'` \
		    > /dev/null 2>&1");
	}
	/* END CSTYLED */
	if (delete_all_swap() != 0) {
		return (-1);
	}

	/* unmount all zones that may be mounted in mntpnt */
	if (UmountAllZones("/a") != 0) {
		return (-1);
	}

	if (DirUmountAll("/a") < 0) {
		return (-1);
	}

	return (0);
}
