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

#ifndef _XML_REG_H
#define	_XML_REG_H


#ifdef __cplusplus
extern "C" {
#endif

#include "wsreg.h"
#include "reg_query.h"
#include "xml_reg_io.h"

#define	Xml_reg struct _Xml_reg

	struct _Xml_reg_private;
	struct _Xml_reg
	{
		void (*free)(Xml_reg *xreg);
		void (*open)(Xml_reg *xreg, Xml_file_mode mode);
		void (*close)(Xml_reg *xreg);
		Wsreg_component **(*query)(Xml_reg *xreg,
		    const Wsreg_query *query);
		int (*register_component)(Xml_reg *xreg, Wsreg_component *comp);
		int (*unregister_component)(Xml_reg *xreg,
		    const Wsreg_component *comp);
		Wsreg_component **(*get_all_components)(Xml_reg *xreg);

		struct _Xml_reg_private *pdata;
	};

	Xml_reg *_wsreg_xreg_create();


#ifdef	__cplusplus
}
#endif

#endif /* _XML_REG_H */
