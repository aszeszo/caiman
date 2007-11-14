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

#pragma ident	"@(#)svc_setaction.c	1.3	07/10/09 SMI"


/*
 * Module:	svc_setaction.c
 * Group:	libspmisvc
 * Description: Routines to set the action codes for initial install.
 */

#include "spmisvc_lib.h"
#include "spmicommon_api.h"
#include "spmisoft_api.h"

/* public function prototypes */
void	set_action_for_machine_type(Module *);

/*-------------------------------------------------------------------*/
/*								     */
/*		Public Functions 				     */
/*								     */
/*-------------------------------------------------------------------*/

/*
 * set_action_for_machine_type()
 *	Called whenever the machine type changes.  Sets up the necessary
 *	fields so that the space code correctly calculates the needed space.
 *	Only used by initial install - glue for space calculations.
 * Parameters:
 *	prod	- product module pointer
 * Return:
 *	none
 * Status:
 *	public
 */
void
set_action_for_machine_type(Module * prod)
{
	static int	machtype = 0;
	Module  	*med = NULL;

	if ((machtype != MT_SERVER) &&
	    (get_machinetype() != MT_SERVER)) {
		machtype = get_machinetype();
		return;
	}

	if (machtype == MT_SERVER && get_machinetype() == MT_SERVER)
		return;

	if (machtype == MT_SERVER || get_machinetype() == MT_SERVER) {
		if (prod->info.prod->p_next_view)
			med = prod->info.prod->p_next_view->p_view_from;
		if (med == NULL)
			med = prod->info.prod->p_view_from;
		if (get_machinetype() == MT_SERVER)
			med->info.media->med_flags = 0;
		else {
			med->info.media->med_flags = SVC_TO_BE_REMOVED;
			/* reset the client expansion space to '0' */
	
			/*
			 * NOTE:  not clear whether we should be doing
			 * something with the error code from this
			 * function.
			 */
			(void) set_client_space(0, 0, 0);
		}
	}
	machtype = get_machinetype();
}
