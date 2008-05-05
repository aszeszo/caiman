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

#ifndef _REG_COMP_H
#define	_REG_COMP_H


#ifdef __cplusplus
extern "C" {
#endif

#include "boolean.h"
#include "xml_reg.h"

#define	Reg_comp struct _Reg_comp

	struct _Reg_comp
	{
		Wsreg_component *(*create)();
		void (*free)(Wsreg_component *comp);
		int (*free_array)(Wsreg_component **array);
		int (*set_id)(Wsreg_component *comp, const char *id);
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
		char *(*get_display_name)(const Wsreg_component *comp,
		    const char *language);
		char **(*get_display_languages)(const Wsreg_component *comp);
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

		int (*equal)(const Wsreg_component *comp1,
		    const Wsreg_component *comp2);
		Wsreg_component *(*clone)(const Wsreg_component *comp);
		Boolean (*add_required)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *required);
		int (*remove_required)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *required);
		Wsreg_component **(*get_required)(Xml_reg *xreg,
		    const Wsreg_component *comp);
		Boolean (*add_dependent)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *dependent);
		int (*remove_dependent)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *dependent);
		Wsreg_component **(*get_dependent)(Xml_reg *xreg,
		    const Wsreg_component *comp);
		Wsreg_component **(*get_children)(Xml_reg *xreg,
		    const Wsreg_component *comp);
		Boolean (*add_child)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *child);
		int (*remove_child)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *child);
		int (*add_compatible_version)(Wsreg_component *comp,
		    const char *version);
		int (*remove_compatible_version)(Wsreg_component *comp,
		    const char *version);
		char **(*get_compatible_versions)(const Wsreg_component *comp);
		Wsreg_component* (*get_parent)(Xml_reg *xreg,
		    const Wsreg_component *comp);
		void (*set_parent)(Xml_reg *xreg, Wsreg_component *comp,
		    const Wsreg_component *parent);
		char *(*get_data)(const Wsreg_component *comp, const char *key);
		int (*set_data)(Wsreg_component *comp,
		    const char *key, const char *value);
		char **(*get_data_pairs)(const Wsreg_component *comp);
		Wsreg_component *(*get_parent_reference)(
			const Wsreg_component *comp);
		Wsreg_component **(*get_child_references)(
			const Wsreg_component *comp);
		Wsreg_component **(*get_required_references)(
			const Wsreg_component *comp);
		Wsreg_component **(*get_dependent_references)(
			const Wsreg_component *comp);
		Wsreg_component **(*clone_array)(Wsreg_component **comp_array);
		int (*array_size)(Wsreg_component **comp_array);
	};

	Reg_comp *_wsreg_comp_initialize();


#ifdef	__cplusplus
}
#endif

#endif /* _REG_COMP_H */
