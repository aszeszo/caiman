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


/*
 * Module:	spmixm_api.h
 * Group:	libspmixm
 * Description:
 *	Header file for common Motif routines.
 */

#ifndef	_LIBSPMIXM_API_H
#define	_LIBSPMIXM_API_H

#pragma ident	"@(#)spmixm_api.h	1.5	07/11/12 SMI"

/* gui toolkit header files */
#include <Xm/Xm.h>
#include <Xm/DragDrop.h>
#include <Xm/Label.h>
#include <Xm/LabelG.h>
#include <Xm/PushB.h>
#include <Xm/PushBG.h>
#include <Xm/Form.h>
#include <Xm/Text.h>
#include <Xm/Separator.h>
#include <Xm/SeparatoG.h>
#include <Xm/FileSB.h>
#include <Xm/MessageB.h>
#include <Xm/DialogS.h>
#include <Xm/PanedW.h>
#include <Xm/CascadeBG.h>
#include <Xm/DrawingA.h>
#include <Xm/RowColumn.h>
#include <Xm/ScrolledW.h>
#include <Xm/SelectioB.h>
#include <Xm/TextF.h>
#include <Xm/ToggleB.h>
#include <Xm/ToggleBG.h>
#include <Xm/Frame.h>
#include <Xm/List.h>
#include <Xm/Protocols.h>
#include <Xm/AtomMgr.h>

#include "spmiapp_api.h" /* required */

/*
 * Message Dialog defines/typedefs...
 */

/*
 * structure to hold xm specific info needed by xm message functions.
 */
typedef struct {
	Widget	toplevel;
	Widget	parent;
	XtAppContext    app_context;
	Atom	delete_atom;
	void (*delete_func)(void);
} xm_MsgAdditionalInfo;

/*
 * Motif help
 */

/* the following defines are used for second argument to xm_adminhelp() */
#define TOPIC   'C'
#define HOWTO   'P'
#define REFER   'R'


/*
 * Function prototypes
 */
#ifdef __cplusplus
extern "C" {
#endif

/* xm_msg.c */
/*
 * function with motif implementation if UI message dialogs
 */
extern void xm_MsgFunction(UI_MsgStruct *msg_info);

/* xm_adminhelp.c */
extern int xm_adminhelp(Widget parent, char help_category, char *textfile);
extern void xm_adminhelp_reinit(int destroy);

/* xm_utils.c */
extern Widget xm_ChildWidgetFindByClass(Widget widget, WidgetClass class);
extern Widget xm_GetShell(Widget w);
extern void xm_SetNoResize(Widget toplevel, Widget w);
extern void xm_ForceDisplayUpdate(Widget toplevel, Widget dialog);
extern void xm_ForceEventUpdate(XtAppContext app_context, Widget toplevel);
extern int xm_SetWidgetString(Widget widget, char *message_text);
extern Boolean xm_IsDescendent(Widget base, Widget w);
extern void xm_AlignWidgetCols(Widget base, Widget *col);
extern int xm_SizeScrolledWindowToWorkArea(Widget w, Boolean doWidth, Boolean doHeight);
#ifdef __cplusplus
}
#endif

#endif	/* _LIBSPMIXM_API_H */
