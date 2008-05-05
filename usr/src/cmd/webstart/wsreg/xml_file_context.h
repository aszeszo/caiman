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

#ifndef _XML_FILE_CONTEXT_H
#define	_XML_FILE_CONTEXT_H


#ifdef __cplusplus
extern "C" {
#endif

#define	Xml_file_context struct _Xml_file_context

	typedef enum {
		READONLY = 0,
		READWRITE
	} Xml_file_mode;

	struct _Xml_file_context_private;
	struct _Xml_file_context
	{
		void (*free)(Xml_file_context *xc);
		void (*set_readfd)(Xml_file_context *xc, int read_fd);
		int (*get_readfd)(Xml_file_context *xc);
		void (*set_writefd)(Xml_file_context *xc, int write_fd);
		int (*get_writefd)(Xml_file_context *xc);
		void (*set_mode)(Xml_file_context *xc, Xml_file_mode mode);
		Xml_file_mode (*get_mode)(Xml_file_context *xc);
		void (*tab_increment)(Xml_file_context *xc);
		void (*tab_decrement)(Xml_file_context *xc);
		int  (*get_tab_count)(Xml_file_context *xc);
		void (*line_increment)(Xml_file_context *xc);
		int  (*get_line_number)(Xml_file_context *xc);

		struct _Xml_file_context_private *pdata;
	};

/*
 * Creates a context.
 */
	Xml_file_context* _wsreg_xfc_create();


#ifdef	__cplusplus
}
#endif

#endif /* _XML_FILE_CONTEXT_H */
