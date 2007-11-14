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


#ifndef lint
#pragma ident	"@(#)soft_swi_choosemedia.c	1.2	07/11/09 SMI"
#endif

#include "spmisoft_api.h"
#include "sw_swi.h"

void
setAutoEject(int autoeject)
{

	enter_swlib("setAutoEject");
	(void) swi_setAutoEject(autoeject);
	exit_swlib();
}

int
isAutoEject()
{
	int i;

	enter_swlib("isAutoEject");
	i = (int)swi_isAutoEject();
	exit_swlib();
	return (i);
}

char *
getCDdevice()
{
	char	*c;

	enter_swlib("getCDdevice");
	c = (char *)swi_getCDdevice();
	exit_swlib();
	return (c);
}

int
have_disc_in_drive(char *device)
{
	int	i;

	enter_swlib("have_disc_in_drive");
	i = (int)swi_have_disc_in_drive(device);
	exit_swlib();
	return (i);
}

void
eject_disc(char *rawdevice)
{
	enter_swlib("eject_disc");
	(void) swi_eject_disc(rawdevice);
	exit_swlib();
}

int
umount_dir(char *mountpt)
{
	int	i;

	enter_swlib("umount_dir");
	i = swi_umount_dir(mountpt);
	exit_swlib();
	return (i);
}

int
mount_disc(char *mountpt, char *device)
{
	int	i;

	enter_swlib("mount_disc");
	i = swi_mount_disc(mountpt, device);
	exit_swlib();
	return (i);
}

int
mount_path(char *hostpath, char *mountpt)
{
	int	i;

	enter_swlib("mount_path");
	i = swi_mount_path(hostpath, mountpt);
	exit_swlib();
	return (i);
}

int
verify_solaris_image(char *mountpt, StringList **nlist, StringList **dlist)
{
	int	i;

	enter_swlib("verify_solaris_image");
	i = swi_verify_solaris_image(mountpt, nlist, dlist);
	exit_swlib();
	return (i);
}
