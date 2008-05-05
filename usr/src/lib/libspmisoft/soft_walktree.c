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


#include "spmisoft_lib.h"

#include <signal.h>
#include <fcntl.h>

/* Public Function Prototypes */

extern void     walktree(Module *, int (*)(Modinfo *, caddr_t), caddr_t);

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * walktree()
 *	Do a depth-first search of the module tree, calling the provided
 *	function for each module encountered. Recursively traverse the tree, 
 *	processing local instances, then the children.
 * Parameters:
 *	mod	- pointer to head of module tree
 *	proc	- pointer to function to be invoked by 'walktree'.
 *		  Function must take the following parameters:
 *			Modinfo *	- pointer to module
 *			caddr_t		- pointer to data structure
 *					  passed in with walktree
 *	data	- data argument for parameter function
 * Return:
 *	none
 * Status:
 *	public
 * Note:
 *	recursive
 */
void
walktree(Module * mod, int (*proc)(Modinfo *, caddr_t), caddr_t data)
{
	Modinfo *mi;
	Module	*child;
	int	errs = 0;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("walktree");
#endif

	/* parameter check */
	if (mod == (Module *)NULL)
		return;

	mi = mod->info.mod;
	if (proc(mi, data) != 0)
		errs++;

	while ((mi = next_inst(mi)) != NULL) {
		if (proc(mi, data) != 0)
			errs++;
	}

	child = mod->sub;
	while (child) {
		walktree(child, proc, data);
		child = child->next;
	}
	return;
}
