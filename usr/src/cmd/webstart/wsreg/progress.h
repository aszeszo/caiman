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

#ifndef _PROGRESS_H
#define	_PROGRESS_H

#pragma ident	"@(#)progress.h	1.4	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * The prototype for progress callbacks.
 */
typedef void (*Progress_callback)(int progress);

#define	Progress struct _Progress

struct _Progress_private;
struct _Progress
{
	void (*free)(Progress *progress);
	void (*report)(Progress *progress);
	void (*set_section_bounds)(Progress *progress, int end_percent,
	    int item_count);
	void (*set_item_count)(Progress *progress, int item_count);
	void (*finish_section)(Progress *progress);
	void (*increment)(Progress *progress);

	struct _Progress_private *pdata;
};

Progress *_wsreg_progress_create(Progress_callback progress_callback);

#ifdef	__cplusplus
}
#endif

#endif /* _PROGRESS_H */
