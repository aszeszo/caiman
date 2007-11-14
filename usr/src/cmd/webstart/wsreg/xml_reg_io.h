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

#ifndef _XML_REG_IO_H
#define	_XML_REG_IO_H

#pragma ident	"@(#)xml_reg_io.h	1.4	06/02/27 SMI"

#ifdef __cplusplus
extern "C" {
#endif

#include <sys/types.h>
#include <sys/stat.h>
#include "wsreg.h"
#include "xml_file_io.h"

/*
 * The location of the registry file.
 */
#define	REGISTRY_LOCATION	"/var/sadm/install"

/*
 * The filenames used in the simple registry.
 */
#define	REGISTRY_FILE		"productregistry"
#define	REGISTRY_ORIGINAL	"productregistry.bak"
#define	REGISTRY_UPDATE		"productregistry.new"

#define	Xml_reg_io struct _Xml_reg_io

	struct _Xml_reg_io_private;
	struct _Xml_reg_io
	{
		void (*free)(Xml_reg_io *xr);
		void (*open)(Xml_reg_io *xr, Xml_file_mode mode);
		void (*close)(Xml_reg_io *xr);
		void (*set_alternate_root)(Xml_reg_io *xr,
		    const char *alternate_root);
		void (*set_permissions)(Xml_reg_io *xr, mode_t permissions);
		mode_t (*get_permissions)(Xml_reg_io *xr);
		void (*read)(Xml_reg_io *xr);
		void (*write)(Xml_reg_io *xr);
		void (*set_components)(Xml_reg_io *xr, Wsreg_component **comps);
		Wsreg_component **(*get_components)(Xml_reg_io *xr);
		Boolean (*can_read_registry)(Xml_reg_io *xr);
		Boolean (*can_modify_registry)(Xml_reg_io *xr);

		struct _Xml_reg_io_private *pdata;
	};

	Xml_reg_io *_wsreg_xregio_create();


#ifdef	__cplusplus
}
#endif

#endif /* _XML_REG_IO_H */
