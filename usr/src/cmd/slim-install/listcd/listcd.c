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
 * Copyright 2009 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * Live CD's boot_archive contains a minimal set of utilities under /usr and
 * devfsadm isn't there. The smf service live-fs-root bootstaps the process
 * by locating the CDROM device and mounting the compressed /usr and /opt
 * to provide a fully functioning system. To mount these file systems the
 * CDROM device must be identified. This utility traverses the device tree
 * and prints out all devices that could support a CDROM device.
 *
 * This utility will print out block and raw devices. A sample output is
 * listed below.
 *
 * /devices/pci@0,0/pci-ide@6/ide@0/sd@0,0:e /devices/pci@0,0/pci-ide@6/ide@0
 * /sd@0,0:e,raw
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <libdevinfo.h>
#include <limits.h>
#include <sys/sunddi.h>
#include <sys/types.h>
#include <sys/dkio.h>

static int
dump_minor(di_node_t node, di_minor_t  minor,  void *arg)
{
	int fd;
	struct dk_cinfo dkinfo;
	char *nt, *mnp, *cp;
	char mpath[PATH_MAX];

	nt = di_minor_nodetype(minor);
	if (nt == NULL)
		return (DI_WALK_CONTINUE);
	/*
	 * Since open is an expensive operation, the code attempts to optimize
	 * the search by looking only for block devices. If the device node is
	 * marked as a possible CD type device, print and return. If not, then
	 * the device is opened and checked to see if it's a CDROM type.
	 */

	if (strstr(nt, DDI_NT_BLOCK) == NULL)
		return (DI_WALK_CONTINUE);
	/* We are here because its a block device */
	mnp = di_devfs_minor_path(minor);
	if (mnp != NULL) {
		/*
		 * We are only interested in block devices, so skip
		 * character i.e. raw devices
		 */
		if (strstr(mnp, ",raw") == NULL) {
			di_devfs_path_free(mnp);
			return (DI_WALK_CONTINUE);
		}

		strcpy(mpath, "/devices");
		strlcat(mpath, mnp, PATH_MAX);

		if ((strstr(nt, DDI_NT_CD) != NULL) ||
		    strstr(nt, DDI_NT_CD_CHAN) != NULL) {
			/*
			 * We have a match. Strip out ",raw"
			 * and print character and block devices.
			 */
			if ((cp = strrchr(mpath, ',')) != NULL)
				*cp = '\0';
			printf("%s /devices%s \n", mpath, mnp);
			di_devfs_path_free(mnp);
			return (DI_WALK_CONTINUE);
		}
		/*
		 * If node type is not marked, Xvm devices for instance
		 * need to verify device type via ioctls
		 */
		if ((fd = open(mpath, O_NDELAY | O_RDONLY)) == -1) {
			perror("open failed ");
			di_devfs_path_free(mnp);
			return (DI_WALK_CONTINUE);
		}
		if (ioctl(fd, DKIOCINFO, &dkinfo) < 0) {
			perror("DKIOCINFO failed");
			close(fd);
			di_devfs_path_free(mnp);
			return (DI_WALK_CONTINUE);
		}
		close(fd);
		/*
		 * strip out ",raw" and print character
		 * and block devices.
		 */
		if (dkinfo.dki_ctype == DKC_CDROM) {
			if ((cp = strrchr(mpath, ',')) != NULL)
				*cp = '\0';
			printf("%s /devices%s \n", mpath, mnp);
		}
		di_devfs_path_free(mnp);
	}
	return (DI_WALK_CONTINUE);
}

int main(void) {
	di_node_t root_node;

	if ((root_node = di_init("/", DINFOCPYALL)) == DI_NODE_NIL) {
		return (1);
	}
	di_walk_minor(root_node, NULL, 0, NULL, dump_minor);
	di_fini(root_node);
	return (0);
}
