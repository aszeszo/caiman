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

#ifndef _REG_QUERY_H
#define	_REG_QUERY_H


#ifdef __cplusplus
extern "C" {
#endif

#define	Reg_query struct _Reg_query

	struct _Reg_query
	{
		Wsreg_query *(*create)();
		void (*free)(Wsreg_query *query);
		int (*set_id)(Wsreg_query *query, const char *id);
		char *(*get_id)(const Wsreg_query *query);
		int (*set_unique_name)(Wsreg_query *query, const char *name);
		char *(*get_unique_name)(const Wsreg_query *query);
		int (*set_version)(Wsreg_query *query, const char *version);
		char *(*get_version)(const Wsreg_query *query);
		int (*set_instance)(Wsreg_query *query, int instance);
		int (*get_instance)(const Wsreg_query *query);
		int (*set_location)(Wsreg_query *query, const char *location);
		char *(*get_location)(const Wsreg_query *query);
	};

	Reg_query *_wsreg_query_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _REG_QUERY_H */
