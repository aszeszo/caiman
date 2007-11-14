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

#pragma ident	"@(#)simple_registry.c	1.26	06/02/27 SMI"

#include <stdlib.h>
#include <fcntl.h>
#include "wsreg.h"
#include "wsreg_private.h"
#include "reg_comp.h"
#include "reg_query.h"
#include "xml_reg.h"
#include "cluster_file_io.h"

static Reg_comp *_comp_obj = NULL;
static Reg_query *_query_obj = NULL;

/*
 * Returns true if the user can read and modify the
 * registry; false otherwise.
 */
static int
sreg_is_available(void)
{
	int result = 0;
	Xml_reg_io *regio = _wsreg_xregio_create();
	result = regio->can_modify_registry(regio);
	regio->free(regio);
	return (result);
}

/*
 * Returns true if the current user has the specified access
 * to the registry.  Legal values for access_flag are:
 * O_RDONLY and O_RDWR.
 */
static int
sreg_can_access_registry(int access_flag)
{
	int result = 0;
	if (access_flag == O_RDONLY) {
		Xml_reg_io *regio = _wsreg_xregio_create();
		result = regio->can_read_registry(regio);
		regio->free(regio);
	} else if (access_flag == O_RDWR) {
		Xml_reg_io *regio = _wsreg_xregio_create();
		result = regio->can_modify_registry(regio);
		regio->free(regio);
	}
	return (result);
}

/*
 * Sets the specified alternate root.  The alternate
 * root is a string that is prepended to the paths
 * of files.  This is often used during OS install.
 */
static void
sreg_set_alternate_root(const char *alternate_root)
{
	Xml_reg_io *regio = _wsreg_xregio_create();
	regio->set_alternate_root(regio, alternate_root);
	regio->free(regio);
}

/*
 * Creates a new component and sets the specified id.
 */
static Wsreg_component *
sreg_create_component(const char *compID)
{
	Wsreg_component *comp = _comp_obj->create();
	_comp_obj->set_id(comp, compID);
	return (comp);
}

/*
 * Adds the specified required component to the specified
 * component.
 */
static int
sreg_add_required_component(Wsreg_component *comp,
    const Wsreg_component *requiredComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	result = _comp_obj->add_required(xreg, comp, requiredComp);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Removes the specified required component from the
 * specified component.
 */
static int
sreg_remove_required_component(Wsreg_component *comp,
    const Wsreg_component *requiredComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	result = _comp_obj->remove_required(xreg, comp, requiredComp);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Returns a NULL-terminated array of components representing
 * all of the required components of the specified component.
 */
static Wsreg_component **
sreg_get_required_components(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	result = _comp_obj->get_required(xreg, comp);
	if (result != NULL) {
		int index = 0;
		while (result[index] != NULL) {
			result[index] = _comp_obj->clone(result[index]);
			index++;
		}
	}

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Adds the specified dependent component to the specified
 * component.
 */
static int
sreg_add_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	result = _comp_obj->add_dependent(xreg, comp, dependentComp);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Removes the specified dependent component from the
 * specified component.
 */
static int
sreg_remove_dependent_component(Wsreg_component *comp,
    const Wsreg_component *dependentComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = _comp_obj->remove_dependent(xreg, comp, dependentComp);
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Returns a NULL-terminated component array representing
 * all components that depend on the specified component.
 */
static Wsreg_component **
sreg_get_dependent_components(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = _comp_obj->get_dependent(xreg, comp);
	if (result != NULL) {
		int index = 0;
		while (result[index] != NULL) {
			result[index] = _comp_obj->clone(result[index]);
			index++;
		}
	}
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Adds the specified child component to the specified
 * component.
 */
static int
sreg_add_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = _comp_obj->add_child(xreg, comp, childComp);
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Removes the specified child component from the
 * specified component.
 */
static int
sreg_remove_child_component(Wsreg_component *comp,
    const Wsreg_component *childComp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = _comp_obj->remove_child(xreg, comp, childComp);
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Returns a NULL-terminated component array representing all
 * child components of the specified component.
 */
static Wsreg_component **
sreg_get_child_components(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = _comp_obj->get_children(xreg, comp);
	if (result != NULL) {
		int index = 0;
		while (result[index] != NULL) {
			result[index] = _comp_obj->clone(result[index]);
			index++;
		}
	}
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Returns the parent of the specified component.
 */
static Wsreg_component *
sreg_get_parent(const Wsreg_component *comp)
{
	Wsreg_component *result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	result = _comp_obj->get_parent(xreg, comp);
	if (result != NULL)
		result = _comp_obj->clone(result);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Sets the parent of the specified component.
 */
static void
sreg_set_parent(Wsreg_component *comp, const Wsreg_component *parent)
{
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READONLY);

	_comp_obj->set_parent(xreg, comp, parent);
	xreg->close(xreg);
	xreg->free(xreg);
}

/*
 * Returns the component from the registry that matches the
 * specified query constraints.
 */
static Wsreg_component *
sreg_get(const Wsreg_query *query)
{
	Wsreg_component **compMatches = NULL;
	Wsreg_component *result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	compMatches = xreg->query(xreg, query);
	if (compMatches != NULL) {
		result = _comp_obj->clone(compMatches[0]);
		free(compMatches);
	}
	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Registers the specified component.  If the specified component
 * has child or required components, the opposite associations
 * are established automatically.
 */
static int
sreg_register(Wsreg_component *comp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READWRITE);

	result = xreg->register_component(xreg, comp);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Unregisters the specified component.  Returns true
 * if the unregistration succeeded; false otherwise.
 */
static int
sreg_unregister(const Wsreg_component *comp)
{
	int result = 0;
	Xml_reg *xreg = _wsreg_xreg_create();

	xreg->open(xreg, READWRITE);

	result = xreg->unregister_component(xreg, comp);

	xreg->close(xreg);
	xreg->free(xreg);

	return (result);
}

/*
 * Returns a component array representing all components currently
 * registered.  The array and all components in the array must
 * be freed by the caller.
 */
static Wsreg_component **
sreg_get_all(void)
{
	Wsreg_component **result = NULL;
	Xml_reg *xreg = _wsreg_xreg_create();
	xreg->open(xreg, READONLY);
	result = xreg->get_all_components(xreg);
	result = _comp_obj->clone_array(result);
	xreg->close(xreg);
	xreg->free(xreg);
	return (result);
}

/*
 * Returns a component array representing all clusters and packages
 * installed on the sysetm that are not registered.  The resulting
 * array must be freed by the caller.
 */
static Wsreg_component **
sreg_get_sys_pkgs(Progress_function progress_callback)
{
	Cluster_file_io *cluster = _wsreg_cfio_create();
	Progress *progress = _wsreg_progress_create(progress_callback);
	Wsreg_component **result = cluster->get_sys_pkgs(progress);
	cluster->free(cluster);
	progress->free(progress);
	return (result);
}

/*
 * Returns a component array representing all components currently
 * registered and all packages referenced by those components.  The
 * resulting array and all components in the array must be freed
 * by the caller.
 */
static Wsreg_component **
sreg_get_xall(void)
{
	Cluster_file_io *cluster = _wsreg_cfio_create();
	Wsreg_component **result = cluster->get_xall();
	cluster->free(cluster);
	return (result);
}

/*
 * This function sets the application data
 * "isDamaged" to "TRUE" for all components that
 * represent Solaris packages that are not currently
 * installed on the system.
 */
static void
sreg_flag_broken_components(Wsreg_component **comps)
{
	Cluster_file_io *cluster = _wsreg_cfio_create();
	cluster->flag_broken_components(comps);
	cluster->free(cluster);
}

/*
 * This is the initialization function.  It sets up the registry
 * function table such that the "_wsreg_simple" registry backend
 * will be used.
 */
_Wsreg_function_table *
_wsreg_simple_init(_Wsreg_function_table *ftable)
{
	if (_comp_obj == NULL)
		_comp_obj = _wsreg_comp_initialize();
	if (_query_obj == NULL)
		_query_obj = _wsreg_query_initialize();

	if (ftable == NULL) {
		ftable = wsreg_malloc(sizeof (_Wsreg_function_table));
	}
	ftable->is_available =		sreg_is_available;
	ftable->can_access_registry = sreg_can_access_registry;
	ftable->set_alternate_root =	sreg_set_alternate_root;
	ftable->create_component =	sreg_create_component;
	ftable->free_component =	_comp_obj->free;
	ftable->set_id =		_comp_obj->set_id;
	ftable->get_id =		_comp_obj->get_id;
	ftable->set_instance =		_comp_obj->set_instance;
	ftable->get_instance =		_comp_obj->get_instance;
	ftable->set_version =		_comp_obj->set_version;
	ftable->get_version =		_comp_obj->get_version;
	ftable->set_unique_name =	_comp_obj->set_unique_name;
	ftable->get_unique_name =	_comp_obj->get_unique_name;
	ftable->add_display_name =	_comp_obj->add_display_name;
	ftable->remove_display_name =	_comp_obj->remove_display_name;
	ftable->get_display_name =	_comp_obj->get_display_name;
	ftable->get_display_languages =	_comp_obj->get_display_languages;
	ftable->set_type =		_comp_obj->set_type;
	ftable->get_type =		_comp_obj->get_type;
	ftable->set_location =		_comp_obj->set_location;
	ftable->get_location =		_comp_obj->get_location;
	ftable->set_uninstaller =	_comp_obj->set_uninstaller;
	ftable->get_uninstaller =	_comp_obj->get_uninstaller;
	ftable->set_vendor =		_comp_obj->set_vendor;
	ftable->get_vendor =		_comp_obj->get_vendor;
	ftable->components_equal =	_comp_obj->equal;
	ftable->clone_component =	_comp_obj->clone;
	ftable->add_required_component = sreg_add_required_component;
	ftable->remove_required_component = sreg_remove_required_component;
	ftable->get_required_components = sreg_get_required_components;
	ftable->add_dependent_component = sreg_add_dependent_component;
	ftable->remove_dependent_component = sreg_remove_dependent_component;
	ftable->get_dependent_components = sreg_get_dependent_components;
	ftable->add_child_component = sreg_add_child_component;
	ftable->remove_child_component = sreg_remove_child_component;
	ftable->get_child_components = sreg_get_child_components;
	ftable->add_compatible_version = _comp_obj->add_compatible_version;
	ftable->remove_compatible_version =
	    _comp_obj->remove_compatible_version;
	ftable->get_compatible_versions = _comp_obj->get_compatible_versions;
	ftable->get_parent = sreg_get_parent;
	ftable->set_parent = sreg_set_parent;
	ftable->get_data =	_comp_obj->get_data;
	ftable->set_data =	_comp_obj->set_data;
	ftable->get_data_pairs = _comp_obj->get_data_pairs;
	ftable->get = sreg_get;
	ftable->register_ = sreg_register;
	ftable->unregister = sreg_unregister;
	ftable->get_parent_reference = _comp_obj->get_parent_reference;
	ftable->get_child_references = _comp_obj->get_child_references;
	ftable->get_required_references = _comp_obj->get_required_references;
	ftable->get_dependent_references = _comp_obj->get_dependent_references;
	ftable->get_all = sreg_get_all;
	ftable->get_sys_pkgs = sreg_get_sys_pkgs;
	ftable->get_xall = sreg_get_xall;
	ftable->flag_broken_components = sreg_flag_broken_components;
	ftable->free_component_array = _comp_obj->free_array;
	ftable->query_create =	_query_obj->create;
	ftable->query_free =	_query_obj->free;
	ftable->query_set_id =	_query_obj->set_id;
	ftable->query_get_id =	_query_obj->get_id;
	ftable->query_set_unique_name =	_query_obj->set_unique_name;
	ftable->query_get_unique_name =	_query_obj->get_unique_name;
	ftable->query_set_version = _query_obj->set_version;
	ftable->query_get_version = _query_obj->get_version;
	ftable->query_set_instance = _query_obj->set_instance;
	ftable->query_get_instance = _query_obj->get_instance;
	ftable->query_set_location = _query_obj->set_location;
	ftable->query_get_location = _query_obj->get_location;

	return (ftable);
}
