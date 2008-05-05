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
 * Copyright 1999 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

/*
 * Private header file that provides a structure for using a function
 * table.  The function table is used by the wsreg.c front end (the
 * public API), which provides an interface to multiple private
 * backend implementations that can be chosen at runtime.
 */

#ifndef	_WSREG_PRIVATE_H
#define	_WSREG_PRIVATE_H


#ifdef	__cplusplus
extern "C" {
#endif

#include "wsreg.h"

typedef struct _Wsreg_function_table
{
	int (*is_available)();
	int (*can_access_registry)(int access_flag);
	void (*set_alternate_root)(const char *alternate_root);
	Wsreg_component *(*create_component)(const char *compID);
	void (*free_component)(Wsreg_component*);
	int (*set_id)(Wsreg_component *comp, const char *compID);
	char *(*get_id)(const Wsreg_component *comp);
	int (*set_instance)(Wsreg_component *comp, int instance);
	int (*get_instance)(const Wsreg_component *comp);
	int (*set_version)(Wsreg_component *comp, const char *version);
	char *(*get_version)(const Wsreg_component *comp);
	int (*set_unique_name)(Wsreg_component *comp,
	    const char *unique_name);
	char *(*get_unique_name)(const Wsreg_component *comp);
	int (*add_display_name)(Wsreg_component *comp,
	    const char *language,
	    const char *display_name);
	int (*remove_display_name)(Wsreg_component *comp,
	    const char *language);
	char **(*get_display_languages)(const Wsreg_component *comp);
	char *(*get_display_name)(const Wsreg_component *comp,
	    const char *language);
	int (*set_type)(Wsreg_component *comp,
	    Wsreg_component_type type);
	Wsreg_component_type (*get_type)(const Wsreg_component *comp);
	int (*set_location)(Wsreg_component *comp,
	    const char *location);
	char *(*get_location)(const Wsreg_component *comp);
	int (*set_uninstaller)(Wsreg_component *comp,
	    const char *uninstaller);
	char *(*get_uninstaller)(const Wsreg_component *comp);
	int (*set_vendor)(Wsreg_component *comp, const char *vendor);
	char *(*get_vendor)(const Wsreg_component *comp);
	int  (*components_equal) (const Wsreg_component *comp1,
	    const Wsreg_component *comp2);
	Wsreg_component *(*clone_component)(
		const Wsreg_component *comp);
	int (*add_required_component)(Wsreg_component *comp,
	    const Wsreg_component *requiredComp);
	int (*remove_required_component)(Wsreg_component *comp,
	    const Wsreg_component *requiredComp);
	Wsreg_component **(*get_required_components)
		(const Wsreg_component *comp);
	int (*add_dependent_component)(Wsreg_component *comp,
	    const Wsreg_component *dependentComp);
	int (*remove_dependent_component)(Wsreg_component *comp,
	    const Wsreg_component *dependentComp);
	Wsreg_component **(*get_dependent_components)
		(const Wsreg_component *comp);
	int (*add_child_component)(Wsreg_component *comp,
	    const Wsreg_component *childComp);
	int (*remove_child_component)(Wsreg_component *comp,
	    const Wsreg_component *childComp);
	Wsreg_component **(*get_child_components)(
		const Wsreg_component *comp);
	int (*add_compatible_version)
		(Wsreg_component *comp, const char *version);
	int (*remove_compatible_version)
		(Wsreg_component *comp, const char *version);
	char **(*get_compatible_versions)(const Wsreg_component *comp);
	Wsreg_component *(*get_parent)(const Wsreg_component *comp);
	void (*set_parent)(Wsreg_component *comp,
	    const Wsreg_component *parent);
	char *(*get_data)(const Wsreg_component *comp, const char *key);
	int (*set_data)
		(Wsreg_component *comp, const char *key,
		    const char *value);
	char **(*get_data_pairs)(const Wsreg_component *comp);
	Wsreg_component *(*get)(const Wsreg_query *query);
	int (*register_)(Wsreg_component *comp);
	int (*unregister)(const Wsreg_component *comp);
	Wsreg_component *(*get_parent_reference)(
		const Wsreg_component *comp);
	Wsreg_component **(*get_child_references)(
		const Wsreg_component *comp);
	Wsreg_component **(*get_required_references)(
		const Wsreg_component *comp);
	Wsreg_component **(*get_dependent_references)(
		const Wsreg_component *comp);
	Wsreg_component **(*get_all)(void);
	Wsreg_component **(*get_sys_pkgs)(Progress_function progress_callback);
	Wsreg_component **(*get_xall)(void);
	void (*flag_broken_components)(Wsreg_component **comps);
	int (*free_component_array)(Wsreg_component **complist);
	Wsreg_query *(*query_create)();
	void (*query_free)(Wsreg_query *query);
	int (*query_set_id)(Wsreg_query *query, const char *compID);
	char *(*query_get_id)(const Wsreg_query *query);
	int (*query_set_unique_name)(Wsreg_query *query,
	    const char *unique_name);
	char *(*query_get_unique_name)(const Wsreg_query *query);
	int (*query_set_version)(Wsreg_query *query,
	    const char *version);
	char *(*query_get_version)(const Wsreg_query *query);
	int (*query_set_instance)(Wsreg_query *query, int instance);
	int (*query_get_instance)(const Wsreg_query *query);
	int (*query_set_location)(Wsreg_query *query,
	    const char *location);
	char *(*query_get_location)(const Wsreg_query *query);

} _Wsreg_function_table;

/*
 * This structure serves as a lightweight component reference.  This
 * reference provides enough information to uniquely identify the target
 * component.  Parent, child, dependent, and required components are all
 * identified with a _Wsreg_instance structure.
 */
	typedef struct {
		char *id;
		int instance;
		char *version;
	} _Wsreg_instance;

/*
 * This structure is used to store application data associated with each
 * component instance.
 */
	typedef struct {
		char *key;
		char *value;
	} _Wsreg_data;

/*
 * This structure is used to store a single localized string.  The
 * display_name field of the Wsreg_component structure is a list of
 * _Wsreg_localized_string structures.
 */
	typedef struct
	{
		char *language;
		char *string;
	} _Wsreg_localized_string;

#ifdef	__cplusplus
}
#endif

#endif	/* _WSREG_PRIVATE_H */
