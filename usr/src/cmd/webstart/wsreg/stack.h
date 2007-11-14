/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 1999 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#ifndef _STACK_H
#define	_STACK_H

#pragma ident	"@(#)stack.h	1.2	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"
#include "list.h"

#define	Stack struct _Stack

	struct _Stack_private;
	struct _Stack
	{
		Stack *(*create)();
		void (*free)(Stack *stack, Free free_function);
		void (*push)(Stack *stack, void *data);
		void *(*pop)(Stack *stack);
		int (*size)(Stack *stack);
		void (*print)(Stack *stack, Print print_function);

		struct _Stack_private *pdata;
	};

	Stack *_wsreg_stack_create();


#ifdef	__cplusplus
}
#endif

#endif /* _STACK_H */
