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
 * Copyright 2002 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)xml_reg.c	1.12	06/02/27 SMI"

/*LINTLIBRARY*/

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "xml_reg.h"
#include "reg_comp.h"
#include "list.h"
#include "wsreg_private.h"
#include "wsreg.h"

static Reg_comp *comp_obj = NULL;

static int
_instances_equal(const _Wsreg_instance *, const _Wsreg_instance *);
static List *
_get_list_differences(List *, List *, int (*equal)(const void *,
    const void *));
static void
_remove_parent_relationships(Xml_reg *, List*);
void
_remove_dependent_relationships(Xml_reg *xreg, Wsreg_component *, List *);
static List *
_component_array_to_list(Wsreg_component **);
static int
_component_cmp(Wsreg_component *, Wsreg_component *);
static Wsreg_component **
_component_list_to_array(List *);
static void
_release_children(Xml_reg *, Wsreg_component *);
static int
_fields_equal(const char *, const char *);
static void
_free_instance(void *);




/*
 * Stores private data associated with the xml_reg object.
 */
struct _Xml_reg_private
{
	Xml_reg_io *regio;
} _Xml_reg_private;

/*
 * Frees the specified xml reg object.
 */
static void
xreg_free(Xml_reg *xreg)
{
	if (xreg->pdata->regio != NULL) {
		xreg->pdata->regio->free(xreg->pdata->regio);
	}

	free(xreg->pdata);
	free(xreg);
}

/*
 * Opens the specified xml file with the specified mode.
 */
static void
xreg_open(Xml_reg *xreg, Xml_file_mode mode)
{
	xreg->pdata->regio->open(xreg->pdata->regio, mode);
}

/*
 * Closes the specified xml file.
 */
static void
xreg_close(Xml_reg *xreg)
{
	xreg->pdata->regio->close(xreg->pdata->regio);
}

/*
 * Returns a NULL-terminated array containing all registered
 * components that match the specified query.
 */
static Wsreg_component **
xreg_query(Xml_reg *xreg, const Wsreg_query *query)
{
	Wsreg_component **components = NULL;
	Wsreg_component **array = NULL;
	int i;
	List *complist = NULL;

	/*
	 * Create a list of components.  The elements will not
	 * be cloned.
	 */
	components = xreg->pdata->regio->get_components(xreg->pdata->regio);
	complist = _wsreg_list_create();
	i = 0;
	while (components[i] != NULL) {
		complist->add_element(complist, components[i]);
		i++;
	}

	/*
	 * Filter the components with the query structure.
	 */
	if (query->id != NULL) {
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    complist->next_element(complist);

			/*
			 * We do not have to check if c->id exists, since
			 * this must be supplied to register a component.
			 */
			if (strcmp(c->id, query->id) != 0) {
				complist->remove(complist, c, NULL);
			}
		}
	}
	if (query->unique_name != NULL) {
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    complist->next_element(complist);

			/*
			 * We must check if unique_name is specified, since
			 * it is possible to register a component without
			 * one.
			 */
			if (c->unique_name &&
			    strcmp(c->unique_name, query->unique_name) != 0) {
				complist->remove(complist, c, NULL);
			}
		}
	}
	if (query->version != NULL) {
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    complist->next_element(complist);

			/*
			 * We must check if version is specified, since it
			 * is possible to register a component without a
			 * version string specified.
			 */
			if (c->version &&
			    strcmp(c->version, query->version) != 0) {
				complist->remove(complist, c, NULL);
			}
		}
	}
	if (query->instance > 0) {
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    complist->next_element(complist);

			if (c->instance != query->instance) {
				complist->remove(complist, c, NULL);
			}
		}
	}
	if (query->location != NULL) {
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    complist->next_element(complist);

			/*
			 * We must check if location is specified, since it
			 * is possible to register a component without a
			 * version string specified.
			 */
			if (c->location &&
			    strcmp(c->location, query->location) != 0) {
				complist->remove(complist, c, NULL);
			}
		}
	}

	/*
	 * Create an array of cloned components representing the result of
	 * the query.
	 */
	if (complist->size(complist) > 0) {
		array =
		    (Wsreg_component **)wsreg_malloc(sizeof (Wsreg_component*) *
			(complist->size(complist) + 1));
		i = 0;
		complist->reset_iterator(complist);
		while (complist->has_more_elements(complist)) {
			Wsreg_component *c =
			    (Wsreg_component *)complist->next_element(complist);
			array[i++] = c;
		}
		array[complist->size(complist)] = NULL;
	}

	complist->free(complist, NULL);
	complist = NULL;
	return (array);
}

/*
 * Registers the specified component.
 */
static int
xreg_register_component(Xml_reg *xreg, Wsreg_component *comp)
{
	Wsreg_component **components = NULL;
	Wsreg_query query;
	Wsreg_component *previousComponent = NULL;
	Wsreg_component **componentMatches = NULL;

	/*
	 * If this component is being overinstalled, we will simply update
	 * the registry to reflect this.
	 */
	query.id = comp->id;
	query.unique_name = NULL;
	query.version = NULL;
	query.instance = 0;
	query.location = comp->location;
	componentMatches = xreg_query(xreg, &query);
	if (componentMatches != NULL) {
		previousComponent = componentMatches[0];
		free(componentMatches);
	}
	if (previousComponent != NULL) {
		Wsreg_component** componentArray =
		    xreg->pdata->regio->get_components(xreg->pdata->regio);
		int index = 0;
		int componentIndex = -1;

		while (componentArray[index] != NULL) {
			if (componentArray[index] == previousComponent) {
				componentIndex = index;
			}
			index++;
		}
		if (componentIndex != -1) {
			List *old_relationship_list = NULL;

			/*
			 * Found the offset.  Replace the previous component
			 * with the new component.
			 */
			comp->instance = previousComponent->instance;
			componentArray[componentIndex] =
			    comp_obj->clone(comp);

			/*
			 * Undo the relationships that are not being
			 * preserved.
			 */
			old_relationship_list =
			    _get_list_differences(comp->children,
				previousComponent->children,
				(int (*)(const void*, const void*))
				_instances_equal);

			_remove_parent_relationships(xreg,
			    old_relationship_list);
			old_relationship_list->free(old_relationship_list,
			    NULL);

			old_relationship_list =
			    _get_list_differences(comp->required,
				previousComponent->required,
				(int (*)(const void*, const void*))
				_instances_equal);
			_remove_dependent_relationships(xreg, previousComponent,
			    old_relationship_list);
			old_relationship_list->free(old_relationship_list,
			    NULL);

			/*
			 * Don't forget to free the previous component.
			 */
			comp_obj->free(previousComponent);
		}
	} else {
		List *componentlist = NULL;
		Wsreg_component *cloned_comp = NULL;

		/*
		 * Assign an instance number.
		 */
		Wsreg_component **compInstances = NULL;
		query.id = comp->id;
		query.unique_name = NULL;
		query.version = NULL;
		query.instance = 0;
		query.location = NULL;
		compInstances = xreg->query(xreg, &query);
		if (compInstances == NULL) {
			/*
			 * Currently, no instances of this component are
			 * installed.
			 */
			comp->instance = 1;
		} else {
			/*
			 * Assign an instance number based on the currently
			 * installed instances.
			 */
			int index;
			int latestinstance = 0;

			index = 0;
			while (compInstances[index] != NULL) {
				if (compInstances[index]->instance >
				    latestinstance)
					latestinstance =
					    compInstances[index]->instance;
				index++;
			}

			comp->instance = latestinstance + 1;
		}


		/*
		 * Insert the new component into the array.  If multiple
		 * instances of this component are installed, the new
		 * component must be added with the other instances.
		 */
		componentlist =
		    _component_array_to_list(
			    xreg->pdata->regio->get_components(
				    xreg->pdata->regio));
		cloned_comp = comp_obj->clone(comp);
		if (compInstances != NULL) {
			/*
			 * Identify the component that should precede the new
			 * component.
			 */
			Wsreg_component *prevComp = NULL;
			int compindex = 0;
			do {
				prevComp = compInstances[compindex++];
			}
			while (compInstances[compindex] != NULL &&
			    _component_cmp(prevComp, comp) <= 0);

			/*
			 * Insert the new component into the list.
			 */
			componentlist->insert_element_at(componentlist,
			    cloned_comp,
			    compindex);
			free(compInstances);
			compInstances = NULL;
		} else {
			/*
			 * Other instances of this component are not
			 * installed.  Simply add to the end of the array.
			 */
			componentlist->add_element(componentlist, cloned_comp);
		}

		components = _component_list_to_array(componentlist);
		xreg->pdata->regio->set_components(xreg->pdata->regio,
		    components);

		componentlist->free(componentlist, NULL);
		componentlist = NULL;
	}

	/*
	 * Cross reference all required components.
	 */
	if (comp->required != NULL) {
		List *requiredlist = comp->required;
		requiredlist->reset_iterator(requiredlist);
		while (requiredlist->has_more_elements(requiredlist)) {
			_Wsreg_instance *required =
			    (_Wsreg_instance*)
			    requiredlist->next_element(requiredlist);
			if (required != NULL) {
				Wsreg_query query = {
					NULL,
					NULL,
					NULL,
					NULL,
					NULL};
				Wsreg_component **compMatches = NULL;
				Wsreg_component *c = NULL;

				query.id = required->id;
				query.instance = required->instance;
				compMatches = xreg_query(xreg, &query);
				if (compMatches != NULL) {
					c = compMatches[0];
					free(compMatches);
				}
				if (c != NULL) {
					(void) comp_obj->add_dependent(xreg,
					    c, comp);
				}
			}
		}
	}

	/*
	 * Cross reference all child components.
	 */
	if (comp->children != NULL) {
		List *childList = comp->children;
		childList->reset_iterator(childList);
		while (childList->has_more_elements(childList)) {
			_Wsreg_instance *childReference =
			    (_Wsreg_instance*)
			    childList->next_element(childList);
			if (childReference != NULL) {
				Wsreg_query query = {
					NULL,
					NULL,
					NULL,
					NULL,
					NULL};
				Wsreg_component **compMatches = NULL;
				Wsreg_component *child = NULL;

				query.id = childReference->id;
				query.instance = childReference->instance;
				compMatches = xreg_query(xreg, &query);
				if (compMatches != NULL) {
					child = compMatches[0];
					free(compMatches);
				}
				if (child != NULL && child->parent == NULL) {
					comp_obj->set_parent(xreg, child, comp);
				}
			}
		}
	}
	return (1);
}

/*
 * Unregisters the specified component.
 */
static int
xreg_unregister_component(Xml_reg *xreg, const Wsreg_component *comp)
{
	int result = 0;
	Wsreg_query query;
	Wsreg_component **compMatches = NULL;
	Wsreg_component *c = NULL;

	query.id = comp->id;
	query.unique_name = comp->unique_name;
	query.version = comp->version;
	query.instance = comp->instance;
	query.location = comp->location;

	compMatches = xreg->query(xreg, &query);
	if (compMatches != NULL) {
		c = compMatches[0];
		free(compMatches);
	}

	if (c != NULL) {
		Wsreg_component **components = NULL;
		List *componentlist = NULL;

		/*
		 * There is a component to remove.
		 *
		 * NOTE:  There is no longer a check here to determine
		 * if it is legal to remove the component, that is whether
		 * other components require it.  THIS IS UNSAFE, BUT IT
		 * IS BETTER TO GIVE THE ADMINISTRATOR THE CHOICE TO
		 * REMOVE GARBAGE IN THE REGISTRY THAN TO FORBID ANY
		 * LOGICALLY WRONG CHANGES.
		 *
		 * A better change would be one which modifies the
		 * registry API to allow explicit 'force' operation
		 * and default to strict checking.  The current change
		 * does not alter the binary interface, only the behavior.
		 */
		_release_children(xreg, c);

		if (c->required != NULL) {
			/*
			 * This component requires other components.  Remove the
			 * dependency references before removing the component.
			 */
			List *list = c->required;

			list->reset_iterator(list);
			while (list->has_more_elements(list)) {
				_Wsreg_instance *rc =
				    (_Wsreg_instance*)list->next_element(list);
				if (rc != NULL) {
					Wsreg_query q = {
						NULL,
						NULL,
						NULL,
						NULL,
						NULL};
					Wsreg_component *requiredComponent =
					    NULL;
					Wsreg_component **compMatches = NULL;

					q.id = rc->id;
					q.instance = rc->instance;
					compMatches = xreg_query(xreg, &q);
					if (compMatches != NULL) {
						requiredComponent =
						    compMatches[0];
						free(compMatches);
					}
					if (requiredComponent != NULL) {
						Wsreg_component *r;
						r = requiredComponent;
						(void)
						    comp_obj->remove_dependent(
							    xreg, r, c);
					}
				}
			}
		}

		/*
		 * Find the component in the array to remove.  This is done
		 * by first creating a list of the components (which is more
		 * flexible than an array).
		 */
		componentlist =
		    _component_array_to_list(
			    xreg->pdata->regio->get_components(
				    xreg->pdata->regio));

		/*
		 * Remove the component from the list.
		 */
		componentlist->remove(componentlist, c, NULL);

		/*
		 * Don't forget to free the component.
		 */
		comp_obj->free(c);

		/*
		 * Recreate the array from the list.
		 */
		components = _component_list_to_array(componentlist);

		/*
		 * Cleanup and reset the components array into the xd.
		 */
		componentlist->free(componentlist, NULL);
		xreg->pdata->regio->set_components(xreg->pdata->regio,
		    components);
		result = 1;
	}
	return (result);
}

/*
 * Returns all currently registered components in the form of a NULL-
 * terminated component array.
 */
static Wsreg_component **
xreg_get_all_components(Xml_reg *xreg)
{
	Wsreg_component **components = NULL;

	components = xreg->pdata->regio->get_components(xreg->pdata->regio);
	return (components);
}

/*
 * Creates a new xml reg object.
 */
Xml_reg *
_wsreg_xreg_create()
{
	Xml_reg *xreg = (Xml_reg*)wsreg_malloc(sizeof (Xml_reg));
	struct _Xml_reg_private *p = NULL;

	/*
	 * Load the method set.
	 */
	xreg->free = xreg_free;
	xreg->open = xreg_open;
	xreg->close = xreg_close;
	xreg->query = xreg_query;
	xreg->register_component = xreg_register_component;
	xreg->unregister_component = xreg_unregister_component;
	xreg->get_all_components = xreg_get_all_components;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Xml_reg_private *)
	    wsreg_malloc(sizeof (struct _Xml_reg_private));
	if (p != NULL) {
		(void *) memset(p, 0, sizeof (struct _Xml_reg_private));
		p->regio = _wsreg_xregio_create();
	}
	xreg->pdata = p;
	if (comp_obj == NULL) {
		comp_obj = _wsreg_comp_initialize();
	}
	return (xreg);
}

/*
 * Returns 1 if the specified instance structures are equal;
 * 0 otherwise.
 */
static int
_instances_equal(const _Wsreg_instance *inst1, const _Wsreg_instance *inst2)
{
	if (inst1 != NULL &&
	    inst2 != NULL) {
		if (!_fields_equal(inst1->id, inst2->id)) {
			return (0);
		}
		if (inst1->instance != inst2->instance) {
			return (0);
		}
		if (!_fields_equal(inst1->version, inst2->version)) {
			return (0);
		}
		return (1);
	}
	return (inst1 == inst2);
}

/*
 * Returns a list consisting of elements in the old list that do
 * not appear in the new list.
 */
static List *
_get_list_differences(List *newList,
    List *oldList,
    int (*equal)(const void *d1,
	const void *d2))
{
	if (oldList != NULL) {
		if (newList != NULL) {
			List *intersection =
			    newList->intersection(newList,
				oldList,
				equal);
			List *difference =
			    oldList->difference(oldList,
				intersection,
				equal);
			intersection->free(intersection, NULL);
			intersection = NULL;
			return (difference);
		} else {
			/*
			 * Since the new list doesn't exist, the
			 * old list represents the difference.
			 */
			return (oldList->clone(oldList, NULL));
		}
	}
	return (_wsreg_list_create());
}

/*
 * Removes the parent from the components identified by
 * the component instances in the specified list.
 */
static void
_remove_parent_relationships(Xml_reg *xreg,
    List* list)
{
	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		_Wsreg_instance *instance =
		    (_Wsreg_instance*)list->next_element(list);
		Wsreg_query *query = wsreg_query_create();
		Wsreg_component **compMatches = NULL;
		Wsreg_component *comp = NULL;

		wsreg_query_set_id(query, instance->id);
		wsreg_query_set_instance(query, instance->instance);
		compMatches = xreg_query(xreg, query);
		if (compMatches != NULL) {
			comp = compMatches[0];
			free(compMatches);
		}
		if (comp != NULL) {
			comp_obj->set_parent(xreg, comp, NULL);
		}
		wsreg_query_free(query);
		query = NULL;
	}
}

/*
 * Removes dependent components from the specified component.
 */
void
_remove_dependent_relationships(Xml_reg *xreg,
    Wsreg_component *dependent_component,
    List *list)
{
	list->reset_iterator(list);
	while (list->has_more_elements(list)) {
		_Wsreg_instance *instance =
		    (_Wsreg_instance*)list->next_element(list);
		Wsreg_query *query = wsreg_query_create();
		Wsreg_component **compMatches = NULL;
		Wsreg_component *comp = NULL;
		wsreg_query_set_id(query, instance->id);
		wsreg_query_set_instance(query, instance->instance);
		compMatches = xreg_query(xreg, query);
		if (compMatches != NULL) {
			comp = compMatches[0];
			free(compMatches);
		}
		if (comp != NULL) {
			comp_obj->remove_dependent(xreg, comp,
			    dependent_component);
		}
		wsreg_query_free(query);
		query = NULL;
	}
}

/*
 * Creates a list of arrays from the specified NULL-terminated
 * component array.
 */
static List *
_component_array_to_list(Wsreg_component **comps)
{
	List *list = _wsreg_list_create();

	if (comps != NULL) {
		int index = 0;
		while (comps[index] != NULL) {
			list->add_element(list, comps[index]);
			index++;
		}
	}
	return (list);
}

/*
 * Compares two components for the purpose of sorting.  Only the
 * component id and the instance number are considered.
 */
static int
_component_cmp(Wsreg_component *comp1, Wsreg_component *comp2)
{
	int result = 1;
	if (comp1 != NULL && comp2 != NULL) {
		int cmp = strcmp(comp1->version, comp2->version);
		int instance = 0;

		if (cmp != 0) {
			return (cmp);
		}

		instance = comp1->instance - comp2->instance;
		return (instance);
	}
	return (result);
}

/*
 * Creates a NULL-terminated component array from the specified
 * component list.
 */
static Wsreg_component **
_component_list_to_array(List *list)
{
	Wsreg_component **components = NULL;

	if (list != NULL) {
		int index;
		components =
		    (Wsreg_component **)wsreg_malloc(sizeof (Wsreg_component*) *
			(list->size(list) + 1));

		list->reset_iterator(list);
		index = 0;
		while (list->has_more_elements(list)) {
			Wsreg_component *comp =
			    (Wsreg_component*)list->next_element(list);
			if (comp != NULL) {
				components[index++] = comp;
			}
		}
		while (index <= list->size(list)) {
			components[index++] = NULL;
		}
	}
	return (components);
}

/*
 * Removes children from the specified registered component.
 */
static void
_release_children(Xml_reg *xreg, Wsreg_component *c)
{
	if (c->children != NULL) {
		/*
		 * This component has child components.  Unset the
		 * "parent" field for each child before removing
		 * the component.
		 */
		List *list = c->children;

		list->reset_iterator(list);
		while (list->has_more_elements(list)) {
			_Wsreg_instance *childReference =
			    (_Wsreg_instance*) list->next_element(list);
			if (childReference != NULL) {
				Wsreg_query q = {
					NULL,
					NULL,
					NULL,
					NULL,
					NULL};
				Wsreg_component **compMatches = NULL;
				Wsreg_component *childComponent =
				    NULL;

				q.id = childReference->id;
				q.instance = childReference->instance;
				compMatches = xreg_query(xreg, &q);
				if (compMatches != NULL) {
					childComponent = compMatches[0];
					free(compMatches);
				}
				if (childComponent != NULL) {
					_Wsreg_instance
					    *parentReference =
					    childComponent->parent;
					if (parentReference != NULL) {
						_free_instance(
							parentReference);
						childComponent->parent =
						    NULL;
					}
				}
			}
		}
	}
}

/*
 * Returns 1 if the specified strings are equal; 0 otherwise.
 */
static int
_fields_equal(const char *field1, const char *field2)
{
	if (field1 != NULL || field2 != NULL) {
		if (field1 == NULL || field2 == NULL) {
			return (0);
		}
		if (strcmp(field1, field2)) {
			return (0);
		}
	}
	return (1);
}

/*
 * Frees the specified instance structure.
 */
static void
_free_instance(void *data)
{
	_Wsreg_instance *comp = data;
	if (comp != NULL) {
		if (comp->id != NULL) {
			free(comp->id);
			comp->id = NULL;
		}
		if (comp->version != NULL) {
			free(comp->version);
			comp->version = NULL;
		}
		free(comp);
		comp = NULL;
	}
}
