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
 * 
 * CDDL HEADER END
 */

/*
 * Portions Copyright 2006  Anil Gulecha
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <libdevinfo.h>
#include <sys/sunddi.h>
#include <sys/types.h>
#include <limits.h>

/*
 * Tinny utility to traverse the device tree and dump
 * all the minor cdrom nodes.
 */

static int
dump_minor(di_node_t node, di_minor_t  minor,  void *arg)
{
    char *mnp;
    int **prop;

    if ((di_minor_spectype(minor) == 0060000) &&
        (di_prop_lookup_ints(DDI_DEV_T_ANY, node, "usb", prop) >= 0)) 
    {
        if ((mnp = di_devfs_minor_path(minor)) != NULL) 
        {
            printf("/devices%s /devices%s,raw\n", mnp,mnp);
            di_devfs_path_free(mnp);
        }
    }

    return (DI_WALK_CONTINUE);
}

int main(void)
{

    di_node_t root_node;

    if ((root_node = di_init("/", DINFOCPYALL)) == DI_NODE_NIL)
    {
        return (1);
    }
    di_walk_minor(root_node, NULL, 0, NULL, dump_minor);
    di_fini(root_node);
    sync();
    
    return (0);
}
