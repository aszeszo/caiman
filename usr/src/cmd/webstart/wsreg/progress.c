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
 * Copyright 2000 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "progress.h"
#include "wsreg.h"

/*
 * This structure contains data that is private to a progress object.
 */
struct _Progress_private
{
	Progress_callback callback;
	int current_progress;
	int begin_progress;
	int end_progress;
	int item_count;
	int current_item;
} _Progress_private;

/*
 * Frees the specified progress object.
 */
static void
prg_free(Progress *progress)
{
	free(progress->pdata);
	free(progress);
}

/*
 * Reports the current progress to the registered callback
 * function.
 */
static void
prg_report(Progress *progress)
{
	Progress_callback callback = progress->pdata->callback;
	if (callback != NULL) {
		callback(progress->pdata->current_progress);
	}
}

/*
 * This method sets the boundaries for the next section.
 */
static void
prg_set_section_bounds(Progress *progress, int end_percent, int item_count)
{
	progress->pdata->begin_progress = progress->pdata->current_progress;
	progress->pdata->end_progress = end_percent;
	progress->pdata->item_count = item_count;
	progress->pdata->current_item = 0;
}

/*
 * This method sets the number of items representing the current
 * progress section.
 */
static void
prg_set_item_count(Progress *progress, int item_count)
{
	progress->pdata->item_count = item_count;
}

/*
 * Finishes the current progress section.  A call to this function
 * results in the progress being updated to the end progress value
 * specified in the progress->set_section_bounds method.
 */
static void
prg_finish_section(Progress *progress)
{
	progress->pdata->current_progress = progress->pdata->end_progress;
	progress->pdata->current_item = progress->pdata->item_count;
	progress->report(progress);
}

/*
 * Increments the progress by one item.  The percent of progress
 * is recalculated and if the progress changes as a result,
 * the new progress will be reported to the progress callback.
 */
static void
prg_increment(Progress *progress)
{
	int begin = progress->pdata->begin_progress;
	int end = progress->pdata->end_progress;
	int item_count = progress->pdata->item_count;
	int current_item = progress->pdata->current_item;
	int current_progress;
	float percent_per_item = (float)(end - begin) / (float)item_count;

	if (current_item < item_count) {
		current_item++;
		current_progress = (int)(percent_per_item *
		    (float)current_item + 0.5) + begin;
		progress->pdata->current_item = current_item;
		if (current_progress != progress->pdata->current_progress) {
			/*
			 * The progress has changed.  Report the change
			 * to the callback.
			 */
			progress->pdata->current_progress =
			    current_progress;
			progress->report(progress);
		}
	}
}

/*
 * Creates a new progress object with the specified progress
 * callback.  Each time new progress is reported to this object,
 * the specified callback will be called with the new progress.
 * The resulting progress object must be released with a
 * call to progress->free().
 */
Progress *
_wsreg_progress_create(Progress_callback progress_callback)
{
	Progress *progress = (Progress *)wsreg_malloc(sizeof (Progress));
	struct _Progress_private *p = NULL;

	/*
	 * Initialize the method set.
	 */
	progress->free = prg_free;
	progress->report = prg_report;
	progress->set_section_bounds = prg_set_section_bounds;
	progress->set_item_count = prg_set_item_count;
	progress->finish_section = prg_finish_section;
	progress->increment = prg_increment;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Progress_private *)
	    wsreg_malloc(sizeof (struct _Progress_private));
	memset(p, 0, sizeof (struct _Progress_private));
	p->callback = progress_callback;
	progress->pdata = p;
	return (progress);
}
