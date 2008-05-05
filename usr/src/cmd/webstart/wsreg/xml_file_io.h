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

#ifndef _XML_FILE_IO_H
#define	_XML_FILE_IO_H


#ifdef __cplusplus
extern "C" {
#endif

#include "xml_file_context.h"
#include "xml_tag.h"

#define	Xml_file_io struct _Xml_file_io

	struct _Xml_file_io_private;
	struct _Xml_file_io
	{
		void (*free)(Xml_file_io *xf);
		void (*set_file_names)(Xml_file_io *xf,
		    const char *file_name,
		    const char *backup_file_name,
		    const char *new_file_name);
		char *(*get_file_name)(Xml_file_io *xf);
		char *(*get_backup_file_name)(Xml_file_io *xf);
		char *(*get_new_file_name)(Xml_file_io *xf);
		void (*open)(Xml_file_io *xf, Xml_file_mode mode,
		    mode_t permissions);
		void (*close)(Xml_file_io *xf);
		void (*write_tag)(Xml_file_io *xf, const Xml_tag *xt);
		void (*write_close_tag)(Xml_file_io *xf, const Xml_tag *xt);
		Xml_tag *(*read_tag)(Xml_file_io *xf);

		struct _Xml_file_io_private *pdata;
	};

	Xml_file_io *_wsreg_xfio_create(String_map *tag_map);

#define	MAX_BUFFER_LENGTH	1024
#define	MAX_LINE_LENGTH		1024
#define	MAX_TAG_LENGTH		128
#define	MAX_VALUE_LENGTH	512


#ifdef	__cplusplus
}
#endif

#endif /* _XML_FILE_IO_H */
