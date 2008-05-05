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



#include "spmicommon_api.h"
#include "spmisvc_api.h"

/*
 * Module:	svc_oslist.c
 * Group:	libspmisvc
 * Description:	This module contains functions which are used to
 *		manipulate lists of root filesystems (and the
 *		stub boot partitions that point to them, if any),
 *		also referred to here collectively as OS images.
 */

/* private functions */
TLLError FreeOSListItem(TLLData node);

/*
 * Function:	OSListCreate
 * Description:	Create the list head for a list of OS images.
 * Scope:	public
 * Parameters:	list	- [RO, *RW] (OSList)
 *			  Address of the location to be used for storing
 *			  the head of the list.
 * Return:	none
 */
void
OSListCreate(OSList *list)
{
	LLCreateList((TList *)list, NULL);
}

/*
 * Function:	OSListAdd
 * Description:	Add a node (containing the description of an OS image) to an
 *		OSList.
 * Scope:	public
 * Parameters:	list		- [RO] (OSlist - list modified, not head)
 *				  Head of the list containing image descriptions
 *		rootslice	- [RO, *RO]
 *				  The slice containing / for this image
 *		stubdevice	- [RO, *RO]
 *				  The slice containing the name of the disk that
 *				  contains the stub boot partition (if any) for
 *				  this image
 *		stubpartno	- [RO]
 *				  The partition number for the stub boot
 *				  partition (if any) for this image
 *		release		- [RO, *RO]
 *				  The name of the Solaris release installed on
 *				  this image
 * Return:	none
 */
void
OSListAdd(OSList list, char *rootslice, char *stubdevice, int stubpartno,
	char *release, svm_info_t *svminfo)
{
	OSListItem *oli;
	TLink node;
	char *tmp;
	oli = (OSListItem *)xmalloc(sizeof (OSListItem));
	if (svminfo != NULL && svminfo->count > 0) {
		tmp = (char *) xmalloc(MAXPATHLEN);
		snprintf(tmp, MAXPATHLEN, "%s (%s)", svminfo->root_md,
			getSvmSliceList(svminfo));
		oli->svmstring = xstrdup(tmp);
		oli->svminfo = svminfo;
		free(tmp);
	} else {
		oli->svmstring = NULL;
		oli->svminfo = NULL;
	}
	oli->rootslice = rootslice ? xstrdup(rootslice) : NULL;
	oli->stubdevice = stubdevice ? xstrdup(stubdevice) : NULL;
	oli->stubpartno = stubpartno;
	oli->release = release ? xstrdup(release) : NULL;
	LLCreateLink(&node, (TLLData)oli);
	LLAddLink((TList)list, node, LLTail);
}

/*
 * Function:	OSListCount
 * Description:	Return the number of items in the list
 * Scope:	public
 * Parameters:	list		- [RO, *RO] (OSList)
 *				  The list to be counted
 * Return:	-1	- An error occurred
 *		>=0	- The number of images in the list
 */
int
OSListCount(OSList list)
{
	int	num;

	if (list == NULL)
		return (-1);

	if (LLGetSuppliedListData(list, &num, NULL))
		return (-1);

	return (num);
}

/*
 * Function:	OSListGetNode
 * Description:	Get a specific OSList image node
 * Scope:	public
 * Parameters:	list		- [RO, *RO] (OSlist)
 *				  The list
 *		num		- [RO] (int)
 *				  The number of the image to be retrieved.
 *				  Images are numbered from 1.
 * Return:	NULL	- An error occurred
 *		OSListItem * - The requested image
 */
OSListItem *
OSListGetNode(OSList list, int num)
{
	/*
	 * Due to the beauties of abstraction, callers don't have to see
	 * how hideously expensive this function is.
	 */
	OSListItem *data;
	int i;

	if (LLUpdateCurrent(list, LLHead))
		return (NULL);

	/* Move to indicated image node */
	for (i = 0; i < num - 1; i++)
		if (LLUpdateCurrent(list, LLNext))
			return (NULL);

	if (LLGetCurrentLinkData(list, NULL, (TLLData *)&data))
		return (NULL);

	return (data);
}

/*
 * Function:	OSListFree
 * Description:	Free a list of OS images
 * Scope:	public
 * Parameters:	list		- [RO, *RW] (OSlist *)
 *				  The list to be freed
 * Return:	none
 */
void
OSListFree(OSList *list)
{
	LLClearList(*list, FreeOSListItem);
	LLDestroyList(list, NULL);
}

/* ---------------------- private functions ----------------------- */

/*
 * Function:	FreeOSListItem
 * Description:	A callback to be used by LLClearList to free a single OSListItem
 * Scope:	private
 * Parameters:	node		- [RO, *RW] (TLLData/OSListItem *)
 *				  The OSListItem to be freed
 * Return:	LLSuccess (type TLLError)
 */
static TLLError
FreeOSListItem(TLLData node)
{
	OSListItem *oli = (OSListItem *)node;

	if (oli->rootslice) free(oli->rootslice);
	if (oli->stubdevice) free(oli->stubdevice);
	/* stubpartno */
	if (oli->release) free(oli->release);

	free(oli);

	return (LLSuccess);
}
