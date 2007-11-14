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

#pragma ident	"@(#)svc_sp_free_results.c	1.2	07/10/09 SMI"


#include "spmicommon_lib.h"
#include "spmisoft_lib.h"
#include "spmisvc_lib.h"
#include "sw_space.h"
#include <libintl.h>
#include <stdlib.h>

/*	Public Function Prototypes	*/

void	free_final_space_report(SW_space_results *);

void
free_final_space_report(SW_space_results *fsr)
{
	SW_space_results *fsr_next;

	while (fsr != NULL) {
		fsr_next = fsr->next;
		free(fsr->sw_mountpnt);
		free(fsr->sw_devname);
		free(fsr);
		fsr = fsr_next;
	}
}
