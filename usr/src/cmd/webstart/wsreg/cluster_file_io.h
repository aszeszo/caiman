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

#ifndef _CLUSTER_FILE_IO_H
#define	_CLUSTER_FILE_IO_H


#ifdef __cplusplus
extern "C" {
#endif

#include "wsreg.h"
#include "progress.h"

/* Function Prototypes */

#define	Cluster_file_io struct _Cluster_file_io

	struct _Cluster_file_io_private;

	struct _Cluster_file_io
	{
		Wsreg_component **(*get_sys_pkgs)(Progress *progress);
		Wsreg_component **(*get_xall)();
		void (*free)(Cluster_file_io *cfio);
		void (*flag_broken_components)(Wsreg_component **comps);
		struct _Cluster_file_io_private *pdata;
	};

	Cluster_file_io *_wsreg_cfio_create();

#ifdef	__cplusplus
}
#endif

#endif /* _CLUSTER_FILE_IO_H */
