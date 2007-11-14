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

#pragma ident	"@(#)app_bootobj.c	1.8	07/10/09 SMI"


/*
 * Module:	app_lfs.c
 * Group:	libspmiapp
 * Description:
 *	Application library level local file system handling routines.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "spmicommon_api.h"
#include "spmistore_api.h"
#include "spmiapp_api.h"
#include "spmisvc_api.h"
#include "app_utils.h"

#include "app_strings.h"

/*
 * Function:	BootobjDiffersQuery
 * Description:
 *	A function used by both installtool and ttinstall to determine
 *	if the current boot device differs from that ladi out by
 *	auto-layout.
 * Scope:       PUBLIC
 * Parameters:  char	*root_device
 *		The slice location of the root file system.
 *
 * Return:      [int]
 *              TRUE - The user selected Repeat Auto Layout
 *              FALSE -  The user selected Cancel
 */

int
BootobjDiffersQuery(char *root_device)
{
	UI_MsgStruct *msg_info;
	int answer;
	char    *msg_buf;

	msg_buf = (char *)xmalloc(strlen(MSG_AUTOLAYOUT_BOOT_WARNING) +
						strlen(MSG_BOOT_PREVIOUS) +
						strlen(root_device) + 1);

	write_debug(APP_DEBUG_L1, "Entering BootobjDiffersQuery");

	if (streq(root_device, "")) {
		(void) sprintf(msg_buf, MSG_AUTOLAYOUT_BOOT_WARNING,
						MSG_BOOT_PREVIOUS);
	} else {
		(void) sprintf(msg_buf, MSG_AUTOLAYOUT_BOOT_WARNING,
						root_device);
	}

	/* set up the message */
	msg_info = UI_MsgStructInit();
	msg_info->title = TITLE_AUTOLAYOUT_BOOT_WARNING;
	msg_info->msg = msg_buf;
	msg_info->help_topic = NULL;
	msg_info->btns[UI_MSGBUTTON_OK].button_text = UI_BUTTON_OK_STR;
	msg_info->btns[UI_MSGBUTTON_CANCEL].button_text = NULL;
	msg_info->btns[UI_MSGBUTTON_HELP].button_text = NULL;

	/* invoke the message */
	(void) UI_MsgFunction(msg_info);

	switch (UI_MsgResponseGet()) {
	case UI_MSGRESPONSE_OK:
		answer = TRUE;
		break;
	}

	return (answer);
}
