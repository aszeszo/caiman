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
 * Copyright 2003 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */

#pragma ident	"@(#)reg_comp.c	1.13	06/02/27 SMI"

#include <stdio.h>
#include <stdlib.h>
#include <strings.h>
#include "wsreg.h"
#include "list.h"
#include "reg_comp.h"
#include "wsreg_private.h"
#include "xml_reg.h"
#include "string_util.h"
#include "file_util.h"

/*
 * The Reg_comp object only has static methods, so there is never
 * a need to create more than one.  Once the object is created,
 * we will save a reference to that object and pass it to all
 * clients requiring a Reg_comp object.  This object is never to
 * be freed (hence no free method).
 */
static Reg_comp *comp_obj = NULL;

static void
free_localized_string(void *);
static void
free_instance(void *);
static void
free_data(void *);
static int
fields_equal(const char *, const char *);
static int
lists_equal(List *, List *,
    int (*)(const void*, const void*));
static int
localized_strings_equal(const _Wsreg_localized_string *,
    const _Wsreg_localized_string *);
static int
instances_equal(const _Wsreg_instance *, const _Wsreg_instance *);
static int
data_equal(const _Wsreg_data *, const _Wsreg_data *);
static void *
clone_localized_string(void *);
static _Wsreg_instance *
clone_instance(const _Wsreg_instance *);
static char *
clone_string(const char *);
static _Wsreg_data *
clone_data(const _Wsreg_data *);
static _Wsreg_instance *
create_instance(Xml_reg *xreg, char *, int,
    char *, char *);
static Wsreg_component **
create_ref_array(List *);
static Wsreg_component **
create_comp_array(Xml_reg *xreg, List *);


/*
 * Creates a component structure.
 */
static Wsreg_component *
rc_create()
{
	Wsreg_component *comp = wsreg_malloc(sizeof (Wsreg_component));
	(void) memset(comp, 0, sizeof (Wsreg_component));

	/*
	 * The default component type is COMPONENT.
	 */
	comp->component_type = WSREG_COMPONENT;
	return (comp);
}

/*
 * Frees the specified component structure.
 */
static void
rc_free(Wsreg_component *comp)
{
	if (comp == NULL) {
		return;
	}
	if (comp->id != NULL) {
		free(comp->id);
		comp->id = NULL;
	}
	if (comp->unique_name != NULL) {
		free(comp->unique_name);
		comp->unique_name = NULL;
	}
	if (comp->display_name != NULL) {
		List *list = (List*)comp->display_name;
		list->free(list,
		    free_localized_string);
		comp->display_name = NULL;
	}
	if (comp->vendor != NULL) {
		free(comp->vendor);
		comp->vendor = NULL;
	}
	if (comp->version != NULL) {
		free(comp->version);
		comp->version = NULL;
	}
	if (comp->parent != NULL) {
		free_instance(comp->parent);
		comp->parent = NULL;
	}
	if (comp->location != NULL) {
		free(comp->location);
		comp->location = NULL;
	}
	if (comp->uninstaller != NULL) {
		free(comp->uninstaller);
		comp->uninstaller = NULL;
	}
	if (comp->required != NULL) {
		List *required = (List*)comp->required;
		required->free(required, free_instance);
		comp->required = NULL;
	}
	if (comp->dependent != NULL) {
		List *dependent = (List*)comp->dependent;
		dependent->free(dependent, free_instance);
		comp->dependent = NULL;
	}
	if (comp->children != NULL) {
		List *children = (List*)comp->children;
		children->free(children, free_instance);
		comp->children = NULL;
	}
	if (comp->backward_compatible != NULL) {
		List *back_compat = (List *)comp->backward_compatible;
		back_compat->free(back_compat,
		    free);
		comp->backward_compatible = NULL;
	}
	if (comp->app_data != NULL) {
		List *app_data = (List *)comp->app_data;
		app_data->free(app_data, free_data);
		comp->app_data = NULL;
	}
	free(comp);
	comp = NULL;
}

/*
 * Frees the specified component array.  The specified array
 * must be NULL-terminated.  All components in the array are
 * also freed as a result of this call.
 */
static int
rc_free_array(Wsreg_component **array)
{
	int index = 0;
	while (array[index] != NULL)
		rc_free(array[index++]);
	free(array);
	return (TRUE);
}

/*
 * Sets the specified id into the specified component.  If
 * NULL is specified as the id, the id of the specified component
 * is unset.
 */
static int
rc_set_id(Wsreg_component *comp, const char *id)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp->id != NULL) {
		free(comp->id);
		comp->id = NULL;
	}
	if (id != NULL) {
		comp->id = sutil->clone(id);

		/*
		 * Trim the whitespace from the end of the
		 * id.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(comp->id);
	}
	return (1);
}

/*
 * Returns the id from the specified component.  The returned
 * id is not a clone of the component's id, so the caller must
 * not free it.
 */
static char *
rc_get_id(const Wsreg_component *comp)
{
	return (comp->id);
}

/*
 * Sets the specified instance number into the specified component.
 */
static int
rc_set_instance(Wsreg_component *comp, int instance)
{
	comp->instance = instance;
	return (1);
}

/*
 * Returns the instance of the specified component.
 */
static int
rc_get_instance(const Wsreg_component *comp)
{
	return (comp->instance);
}

/*
 * Sets the specified version into the specified component.  The
 * component will get a clone of the specified version.
 */
static int
rc_set_version(Wsreg_component *comp, const char *version)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp->version != NULL) {
		free(comp->version);
		comp->version = NULL;
	}
	if (version != NULL) {
		comp->version = sutil->clone(version);

		/*
		 * Trim the whitespace from the end of the
		 * version.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(comp->version);
	}
	return (1);
}

/*
 * Returns the version of the specified component.  The returned
 * version is not a clone, so the caller should not try to free it.
 */
static char *
rc_get_version(const Wsreg_component *comp)
{
	return (comp->version);
}

/*
 * Sets the specified unique_name into the specified component.
 */
static int
rc_set_unique_name(Wsreg_component *comp, const char *unique_name)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp->unique_name != NULL) {
		free(comp->unique_name);
		comp->unique_name = NULL;
	}
	if (unique_name != NULL) {
		comp->unique_name = sutil->clone(unique_name);

		/*
		 * Trim the whitespace from the end of the
		 * unique name.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(comp->unique_name);
	}
	return (1);
}

/*
 * Returns the unique name of the specified component.  The resulting
 * name is not a clone of that in the component structure, so the
 * caller should not free it.
 */
static char *
rc_get_unique_name(const Wsreg_component *comp)
{
	return (comp->unique_name);
}

/*
 * Removes the display name associated with the specified language
 * from the specified component.
 */
static int
rc_remove_display_name(Wsreg_component *comp, const char *language)
{
	if (comp->display_name != NULL &&
	    language != NULL) {
		/*
		 * Go through the list of display names and remove
		 * the element that contains the specified language.
		 * There can only be one element per language, so
		 * the search can stop at that point.
		 */
		List *list = (List*)comp->display_name;
		list->reset_iterator(list);
		while (list->has_more_elements(list)) {
			_Wsreg_localized_string *localized_string =
			    (_Wsreg_localized_string*)list->next_element(list);
			if (localized_string != NULL &&
			    localized_string->language != NULL &&
			    localized_string->string != NULL) {
				/*
				 * Compare the language to see if there is
				 * a match.
				 */
				if (strcmp(localized_string->language,
				    language) == 0) {
					list->remove(list,
					    localized_string, NULL);
					free(localized_string->language);
					localized_string->language = NULL;
					free(localized_string->string);
					localized_string->string = NULL;
					free(localized_string);
					localized_string = NULL;

					if (list->size(list) == 0) {
						/*
						 * The last element has been
						 * removed from the list.
						 * Remove the list.
						 */
						list->free(list, NULL);
						comp->display_name = NULL;
					}

					/*
					 * The removal was successful.
					 */
					return (1);
				}
			}
		}
	}
	return (0);
}

/*
 * Adds the specified display name to the specified component.  If
 * a display name is already associated with the specified language
 * in the specified component, that display name will be removed
 * and freed as a result of this function call.
 */
static int
rc_add_display_name(Wsreg_component *comp, const char *language,
    const char *display_name)
{
	List *name_list = (List *)comp->display_name;
	_Wsreg_localized_string *localized_string = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	if (language == NULL || display_name == NULL)
		return (0);

	if (name_list != NULL) {
		/*
		 * Be sure we are not adding duplicate entries for
		 * any specific language.
		 */
		(void) rc_remove_display_name(comp, language);
		name_list = (List *)comp->display_name;
	}

	if (name_list == NULL) {
		/*
		 * The list has not yet been created or was deleted
		 * when the name was removed in the previous code
		 * block.  Create it now.
		 */
		name_list = _wsreg_list_create();
		comp->display_name = (void *)name_list;
	}

	/*
	 * Add an entry for the specified language.
	 */
	localized_string = (_Wsreg_localized_string*)
	    wsreg_malloc(sizeof (_Wsreg_localized_string));
	localized_string->language = sutil->clone(language);
	localized_string->string = sutil->clone(display_name);

	/*
	 * Trim the whitespace from the end of the
	 * language and display name.  This whitespace
	 * is not preserved in the xml file.
	 */
	sutil->trim_whitespace(localized_string->language);
	sutil->trim_whitespace(localized_string->string);
	name_list->add_element(name_list, localized_string);
	return (1);
}

/*
 * Returns the display name associated with the specified language
 * in the specified component.  The resulting display name is not
 * a clone, so the caller should not free it.
 */
static char *
rc_get_display_name(const Wsreg_component *comp,
    const char *language)
{
	if (comp->display_name != NULL &&
	    language != NULL) {
		/*
		 * Go through the list of display names and return
		 * the localized string that corresponds to the
		 * specified language.
		 */
		List *list = (List*)comp->display_name;
		list->reset_iterator(list);
		while (list->has_more_elements(list)) {
			_Wsreg_localized_string *localized_string =
			    (_Wsreg_localized_string*)list->next_element(list);
			if (localized_string != NULL &&
			    localized_string->language != NULL &&
			    localized_string->string != NULL) {
				/*
				 * Compare the language to see if there is
				 * a match.
				 */
				if (strcmp(localized_string->language,
				    language) == 0) {
					return (localized_string->string);
				}
			}
		}
	}
	return (NULL);
}

/*
 * Returns an array representing all languages for which display
 * names have been set into the specified component.
 *
 * The resulting array is NULL-terminated.  The elements of the
 * array represent the languages.  The languages are not cloned,
 * so the caller should free the array, but not the contents of
 * the array.
 */
static char **
rc_get_display_languages(const Wsreg_component *comp)
{
	char **language_array = NULL;
	int array_index = 0;

	if (comp->display_name) {
		/*
		 * Go through the list of display names and add
		 * each language to the language array.
		 */
		List *list = (List*)comp->display_name;

		language_array = (char **)wsreg_malloc(sizeof (char *) *
		    (list->size(list) + 1));
		(void) memset(language_array, 0, sizeof (char *) *
		    (list->size(list) + 1));
		list->reset_iterator(list);
		while (list->has_more_elements(list)) {
			_Wsreg_localized_string *localized_string =
			    (_Wsreg_localized_string*)list->next_element(list);

			if (localized_string != NULL &&
			    localized_string->language != NULL &&
			    localized_string->string != NULL) {
				language_array[array_index++] =
				    localized_string->language;
			}
		}
	}
	return (language_array);
}

/*
 * Sets the specified component type into the specified component.
 */
static int
rc_set_type(Wsreg_component *comp, Wsreg_component_type type)
{
	comp->component_type = type;
	return (1);
}

/*
 * Returns the component type currently set in the specified component.
 */
static Wsreg_component_type
rc_get_type(const Wsreg_component *comp)
{
	return (comp->component_type);
}

/*
 * Sets the specified location into the specified component.
 */
static int
rc_set_location(Wsreg_component *comp, const char *location)
{
	if (comp->location != NULL) {
		free(comp->location);
		comp->location = NULL;
	}
	if (location != NULL) {
		File_util *futil = _wsreg_fileutil_initialize();

		/*
		 * Be sure to use the canonical path.  Don't trust
		 * the application to do this.
		 */
		comp->location = futil->get_canonical_path(location);
	}
	return (1);
}

/*
 * Returns the location currently set into the specified component.
 * The resulting string is not a clone of the location, so the caller
 * should not free it.
 */
static char *
rc_get_location(const Wsreg_component *comp)
{
	return (comp->location);
}

/*
 * Sets the specified uninstaller command into the specified component.
 */
static int
rc_set_uninstaller(Wsreg_component *comp, const char *uninstaller)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp->uninstaller != NULL) {
		free(comp->uninstaller);
		comp->uninstaller = NULL;
	}
	if (uninstaller != NULL) {
		comp->uninstaller = sutil->clone(uninstaller);
		/*
		 * Trim the whitespace from the end of the
		 * uninstaller.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(comp->uninstaller);
	}
	return (1);
}

/*
 * Returns the uninstaller command currently set in the specified
 * component.
 */
static char *
rc_get_uninstaller(const Wsreg_component *comp)
{
	return (comp->uninstaller);
}

/*
 * Sets the specified vendor into the specified component.
 */
static int
rc_set_vendor(Wsreg_component *comp, const char *vendor)
{
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp->vendor != NULL) {
		free(comp->vendor);
		comp->vendor = NULL;
	}
	if (vendor != NULL) {
		comp->vendor = sutil->clone(vendor);
		/*
		 * Trim the whitespace from the end of the
		 * uninstaller.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(comp->vendor);
	}
	return (1);
}

/*
 * Returns the vendor currently set in the specified component.
 * The resulting string is not cloned, so the caller should not
 * free it.
 */
static char *
rc_get_vendor(const Wsreg_component *comp)
{
	return (comp->vendor);
}

/*
 * Returns true if the specified components are equal.  Components
 * are considered equal if all of their attributes are the same.
 * It does not matter what order the data was set in either
 * component (i.e. the child components do not have to be added in
 * the same order on both components for the equality to be true).
 */
static int
rc_equal(const Wsreg_component *comp1, const Wsreg_component *comp2)
{
	if (comp1 == comp2)
		return (1);
	if (comp1 != NULL && comp2 != NULL) {
		/*
		 * Check the component id.
		 */
		if (!fields_equal(comp1->id, comp2->id)) {
			return (0);
		}

		/*
		 * Check the version
		 */
		if (!fields_equal(comp1->version, comp2->version)) {
			return (0);
		}

		/*
		 * Check the unique name.
		 */
		if (!fields_equal(comp1->unique_name,
		    comp2->unique_name)) {
			return (0);
		}

		/*
		 * Check the display name.
		 */
		if (!lists_equal(comp1->display_name,
		    comp2->display_name,
		    (int (*)(const void*, const void*))
		    localized_strings_equal)) {
			return (0);
		}

		/*
		 * Check the vendor.
		 */
		if (!fields_equal(comp1->vendor, comp2->vendor)) {
			return (0);
		}

		/*
		 * Check the parent.
		 */
		if (!instances_equal(comp1->parent, comp2->parent)) {
			return (0);
		}

		/*
		 * Check the install location.
		 */
		if (!fields_equal(comp1->location, comp2->location)) {
			return (0);
		}

		/*
		 * Check the uninstaller.
		 */
		if (!fields_equal(comp1->uninstaller,
		    comp2->uninstaller)) {
			return (0);
		}

		/*
		 * Check the required components.
		 */
		if (!lists_equal(comp1->required, comp2->required,
		    (int (*)(const void*, const void*))
		    instances_equal)) {
			return (0);
		}

		/*
		 * Check the dependent components.
		 */
		if (!lists_equal(comp1->dependent, comp2->dependent,
		    (int (*)(const void*, const void*))
		    instances_equal)) {
			return (0);
		}

		/*
		 * Check the child components.
		 */
		if (!lists_equal(comp1->children, comp2->children,
		    (int (*)(const void*, const void*))
		    instances_equal)) {
			return (0);
		}

		/*
		 * Check the compatible versions.
		 */
		if (!lists_equal(comp1->backward_compatible,
		    comp2->backward_compatible,
		    (int (*)(const void*, const void*))fields_equal)) {
			return (0);
		}

		/*
		 * Check the app data.
		 */
		if (!lists_equal(comp1->app_data, comp2->app_data,
		    (int (*)(const void*, const void*))data_equal)) {
			return (0);
		}
		return (1);
	}
	return (0);
}

/*
 * Returns a clone of the specified component.
 */
static Wsreg_component *
rc_clone(const Wsreg_component *comp)
{
	Wsreg_component *newcomp = rc_create();
	(void) rc_set_id(newcomp, comp->id);
	newcomp->instance = comp->instance;
	(void) rc_set_version(newcomp, rc_get_version(comp));
	(void) rc_set_unique_name(newcomp, rc_get_unique_name(comp));

	if (comp->display_name != NULL) {
		List *list = (List *)comp->display_name;
		newcomp->display_name = list->clone(list,
		    clone_localized_string);
	}
	newcomp->parent = clone_instance(comp->parent);
	if (comp->children != NULL) {
		List *list = (List *)comp->children;
		newcomp->children = list->clone(list,
		    (Clone)clone_instance);
	}
	(void) rc_set_vendor(newcomp, rc_get_vendor(comp));

	(void) rc_set_type(newcomp, rc_get_type(comp));
	(void) rc_set_location(newcomp, rc_get_location(comp));
	(void) rc_set_uninstaller(newcomp, rc_get_uninstaller(comp));

	if (comp->required != NULL) {
		List *list = (List *)comp->required;
		newcomp->required = list->clone(list,
		    (Clone)clone_instance);
	}
	if (comp->dependent != NULL) {
		List *list = (List *)comp->dependent;
		newcomp->dependent = list->clone(list,
		    (Clone)clone_instance);
	}
	if (comp->backward_compatible != NULL) {
		List *list = (List *)comp->backward_compatible;
		newcomp->backward_compatible =
		    list->clone(list,
			(Clone)clone_string);
	}
	if (comp->app_data != NULL) {
		List *list = (List *)comp->app_data;
		newcomp->app_data = list->clone(list,
		    (Clone)clone_data);
	}
	return (newcomp);
}

/*
 * Returns the size of the specified array.  The specified
 * array must be NULL-terminated.
 */
static int
rc_array_size(Wsreg_component **comp_array)
{
	int size = 0;
	if (comp_array != NULL) {
		while (comp_array[size] != NULL) {
			size++;
		}
	}
	return (size);
}

/*
 * Returns a clone of the specified component array.  All components
 * in the array are cloned.  It is the callers responsibility to
 * free the resulting array and its elements.
 */
static Wsreg_component **
rc_clone_array(Wsreg_component **comp_array)
{
	Wsreg_component **result = NULL;
	if (comp_array != NULL) {
		int count = rc_array_size(comp_array);
		int index = 0;

		/*
		 * Create the clone.
		 */
		result = (Wsreg_component **)
		    wsreg_malloc(sizeof (Wsreg_component *) *
		    (count + 2));
		(void) memset(result, 0,
		    sizeof (Wsreg_component *) * (count + 2));
		for (index = 0; index < count; index++) {
			result[index] = comp_obj->clone(comp_array[index]);
		}
	}
	return (result);
}

/*
 * Removes the specified required component from the specified component.
 */
static int
rc_remove_required(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *required)
{
	int removeCount = 0;

	List *requiredComponents = comp->required;
	_Wsreg_instance *reqComp =
	    create_instance(xreg, required->id,
		required->instance,
		required->location,
		required->version);
	if (reqComp == NULL) {
		return (0);
	}

	if (requiredComponents == NULL) {
		/*
		 * Nothing to remove.
		 */
		/*EMPTY*/
	} else {
		/*
		 * Search through the list of required components.  If
		 * the specified required component is in the list,
		 * remove it.
		 */
		requiredComponents->reset_iterator(requiredComponents);
		while (requiredComponents->has_more_elements(
			requiredComponents)) {
			_Wsreg_instance *compI =
			    requiredComponents->next_element(
				    requiredComponents);

			if (compI != NULL) {
				if ((strcmp(reqComp->id,
				    compI->id) == 0) &&
				    reqComp->instance ==
				    compI->instance) {
					/*
					 * Found the element in the
					 * list.
					 */
					requiredComponents->remove(
						requiredComponents,
						    compI, NULL);
					free_instance(compI);

					removeCount++;
				}
			}
		}
	}
	free_instance(reqComp);
	if (removeCount > 0)
		return (1);
	return (0);
}

/*
 * Adds the specified required component to the specified component.
 */
static Boolean
rc_add_required(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *required)
{
	if (comp != NULL && required != NULL) {
		List *requiredComponents = (List *)comp->required;
		_Wsreg_instance *reqComp = NULL;

		reqComp = create_instance(xreg,
		    required->id,
		    required->instance,
		    required->location,
		    required->version);
		if (reqComp == NULL) {
			return (FALSE);
		}
		if (requiredComponents == NULL) {
			/*
			 * Make a new list.
			 */
			requiredComponents = _wsreg_list_create();
			comp->required = requiredComponents;
		} else {
			/*
			 * If the specified required component is already in
			 * the list, remove the old one and add the new one.
			 */
			(void) rc_remove_required(xreg, comp, required);
			requiredComponents = (List *)comp->required;

			requiredComponents->reset_iterator(requiredComponents);
			while (requiredComponents->has_more_elements(
				requiredComponents)) {
				_Wsreg_instance *compI =
				    requiredComponents->next_element(
					    requiredComponents);

				if (compI != NULL) {
					if ((strcmp(reqComp->id,
					    compI->id) == 0) &&
					    reqComp->instance ==
					    compI->instance) {
						/*
						 * Found the element in the
						 * list.
						 */
						requiredComponents->remove(
							requiredComponents,
							    compI, NULL);
						free_instance(compI);
					}
				}
			}
		}

		/*
		 * Add the new required component to the list.
		 */
		requiredComponents->add_element(requiredComponents, reqComp);
		return (TRUE);
	}
	return (FALSE);
}

/*
 * Returns a component array containing all components
 * that the specified component requires.
 */
static Wsreg_component **
rc_get_required(Xml_reg *xreg, const Wsreg_component *comp)
{
	return (create_comp_array(xreg,
	    comp->required));
}

/*
 * Removes the specified dependent component from the specified
 * component.
 */
static int
rc_remove_dependent(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *dependent)
{
	int removeCount = 0;

	List *dependentComponents = comp->dependent;
	_Wsreg_instance *depComp =
	    create_instance(xreg, dependent->id,
		dependent->instance,
		dependent->location,
		dependent->version);
	if (depComp == NULL) {
		return (0);
	}
	if (dependentComponents == NULL) {
		/*
		 * Nothing to remove.
		 */
		/*EMPTY*/
	} else {
		/*
		 * Search through the list of dependent components.  If
		 * the specified dependent component is in the list,
		 * remove it.
		 */
		dependentComponents->reset_iterator(
			dependentComponents);
		while (dependentComponents->has_more_elements(
			dependentComponents)) {
			_Wsreg_instance *compI =
			    dependentComponents->next_element(
				    dependentComponents);

			if (compI != NULL) {
				if ((strcmp(depComp->id,
				    compI->id) == 0) &&
				    depComp->instance ==
				    compI->instance) {
					/*
					 * Found the element in the
					 * list.
					 */
					dependentComponents->remove(
						dependentComponents,
						    compI, NULL);
					free_instance(compI);
					removeCount++;
				}
			}
		}
	}
	free_instance(depComp);
	if (removeCount > 0)
		return (1);
	return (0);
}

/*
 * Adds the specified dependent component to the specified component.
 */
static Boolean
rc_add_dependent(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *dependent)
{
	List *dependentComponents = comp->dependent;
	_Wsreg_instance *depComp =
	    create_instance(xreg, dependent->id,
		dependent->instance,
		dependent->location,
		dependent->version);
	if (depComp == NULL) {
		return (FALSE);
	}

	/*
	 * If the specified dependent component is already in
	 * the list, remove the old one and add the new one.
	 */
	(void) rc_remove_dependent(xreg, comp, dependent);
	dependentComponents = (List *)comp->dependent;

	if (dependentComponents == NULL) {
		/*
		 * Make a new list.
		 */
		dependentComponents = _wsreg_list_create();
		comp->dependent = dependentComponents;
	}

	/*
	 * Add the new dependent component to the list.
	 */
	dependentComponents->add_element(dependentComponents, depComp);
	return (TRUE);
}

/*
 * Returns a component array containing all components dependent
 * on the specified component.
 */
static Wsreg_component **
rc_get_dependent(Xml_reg *xreg, const Wsreg_component *comp)
{
	return (create_comp_array(xreg,
	    comp->dependent));
}

/*
 * Returns a component array containing all child components
 * of the specified component.
 */
static Wsreg_component **
rc_get_children(Xml_reg *xreg, const Wsreg_component *comp)
{
	return (create_comp_array(xreg,
	    comp->children));
}

/*
 * Adds the specified child component to the specified
 * component.
 */
static Boolean
rc_add_child(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *child)
{
	if (comp != NULL && child != NULL) {
		List *childComponents = comp->children;
		_Wsreg_instance *childComp =
		    create_instance(xreg, child->id,
			child->instance,
			child->location,
			child->version);
		if (childComp == NULL) {
			return (FALSE);
		}

		if (childComponents == NULL) {
			/*
			 * Make a new list.
			 */
			childComponents = _wsreg_list_create();
			comp->children = childComponents;
		} else {
			/*
			 * Search through the list of child components.
			 * If the specified child component is already
			 * in the list, remove the old one and add
			 * the new one.
			 */
			childComponents->reset_iterator(childComponents);
			while (childComponents->has_more_elements(
				childComponents)) {
				_Wsreg_instance *compI =
				    childComponents->next_element(
					    childComponents);

				if (compI != NULL) {
					if ((strcmp(childComp->id,
					    compI->id) == 0) &&
					    childComp->instance ==
					    compI->instance) {
						/*
						 * Found the element in the
						 * list.
						 */
						childComponents->remove(
							childComponents,
							    compI, NULL);
						free_instance(compI);
					}
				}
			}
		}

		/*
		 * Add the new child component to the list.
		 */
		childComponents->add_element(childComponents, childComp);
		return (TRUE);
	}
	return (FALSE);
}

/*
 * Removes the specified child component from the specified
 * component.
 */
static int
rc_remove_child(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *child)
{
	int removeCount = 0;

	if (comp != NULL && child != NULL) {
		List *childComponents = comp->children;
		_Wsreg_instance *childComp =
		    create_instance(xreg, child->id,
			child->instance,
			child->location,
			child->version);
		if (childComp == NULL) {
			return (0);
		}
		if (childComponents == NULL) {
			/*
			 * Nothing to remove.
			 */
			/*EMPTY*/
		} else {
			/*
			 * Search through the list of child components.  If
			 * the specified child component is in the list,
			 * remove it.
			 */
			childComponents->reset_iterator(childComponents);
			while (childComponents->has_more_elements(
				childComponents)) {
				_Wsreg_instance *compI =
				    childComponents->next_element(
					    childComponents);
				if (compI != NULL) {
					if ((strcmp(childComp->id,
					    compI->id) == 0) &&
					    childComp->instance ==
					    compI->instance) {
						/*
						 * Found the element in the
						 * list.
						 */
						childComponents->remove(
							childComponents,
							    compI, NULL);
						free_instance(compI);
						removeCount++;
					}
				}
			}
		}
		free_instance(childComp);
		if (removeCount > 0)
			return (1);
	}
	return (0);
}

/*
 * Adds the specified version to the list of versions the specified
 * component is backward compatible with.
 */
static int
rc_add_compatible_version(Wsreg_component *comp, const char *version)
{
	List *bc = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	if (comp != NULL && version != NULL) {
		char *versionCopy;

		/*
		 * Be sure that the version is not already included.
		 */
		(void) wsreg_remove_compatible_version(comp, version);
		versionCopy = sutil->clone(version);

		/*
		 * Trim the whitespace from the end of the
		 * version.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(versionCopy);

		bc = comp->backward_compatible;
		if (bc == NULL) {
			bc = _wsreg_list_create();
			comp->backward_compatible = bc;
		}

		/*
		 * Now add the new version to the list.
		 */
		bc->add_element(bc, versionCopy);
		return (1);
	}
	return (0);
}

/*
 * Removes the specified version from the list of version the
 * specified component is backward compatible with.
 */
static int
rc_remove_compatible_version(Wsreg_component *comp,
    const char *version)
{
	List *bc = NULL;
	int removeCount = 0;

	if (comp != NULL && version != NULL) {
		bc = comp->backward_compatible;
		if (bc != NULL) {
			bc->reset_iterator(bc);
			while (bc->has_more_elements(bc)) {
				char *v = (char *)bc->next_element(bc);
				if (v != NULL &&
				    strcmp(v, version) == 0) {
					char *oldVersion = NULL;

					/*
					 * Found a match.  Remove it.
					 */
					oldVersion = bc->remove(bc,
					    version,  NULL);
					bc->reset_iterator(bc);
					removeCount++;

					/*
					 * Be sure to free the memory from
					 * the element.
					 */
					free(oldVersion);
				}
			}
			if (bc->size(bc) == 0) {
				/*
				 * There are no more items in this list.
				 * Remove the list.
				 */
				bc->free(bc, NULL);
				bc = NULL;
				comp->backward_compatible = NULL;
			}
		}
	}
	return (removeCount);
}

/*
 * Returns a NULL-terminated array of versions the specified component
 * is backward compatible with.  The caller must free the resulting
 * array and its contents.
 */
static char **
rc_get_compatible_versions(const Wsreg_component *comp)
{
	char **compatibleVersions = NULL;
	int position = 0;
	String_util *sutil = _wsreg_strutil_initialize();

	if (comp != NULL) {
		List *bc = comp->backward_compatible;
		if (bc != NULL) {
			/*
			 * Allocate enough memory for the array.  Don't forget
			 * the NULL termination.
			 */
			int arraySize = bc->size(bc) + 1;
			compatibleVersions = (char **)
			    wsreg_malloc(sizeof (char *) * arraySize);
			(void) memset(compatibleVersions, 0, sizeof (char *) *
			    arraySize);

			/*
			 * Copy the versions into the array.
			 */
			bc->reset_iterator(bc);
			while (bc->has_more_elements(bc)) {
				char *version =
				    bc->next_element(bc);
				if (version != NULL) {
					compatibleVersions[position] =
					    sutil->clone(version);
					position++;
				}
			}
		}
	}
	return (compatibleVersions);
}

/*
 * Returns a component representing the parent of the specified
 * component.
 */
static Wsreg_component*
rc_get_parent(Xml_reg *xreg, const Wsreg_component *comp)
{
	_Wsreg_instance *parent = NULL;
	if (comp == NULL) {
		return (NULL);
	}

	parent = comp->parent;
	if (parent != NULL) {
		/*
		 * The parent has been specified.  Simply look it up based on
		 * its component instance.
		 */
		Wsreg_component *p = NULL;
		Wsreg_component **compMatches = NULL;
		Wsreg_query query;

		query.id = parent->id;
		query.instance = parent->instance;
		query.version = parent->version;
		query.unique_name = NULL;
		query.location = NULL;

		compMatches = xreg->query(xreg, &query);
		if (compMatches != NULL) {
			p = compMatches[0];
			free(compMatches);
		}
		return (p);
	}
	return (NULL);
}

/*
 * Sets the parent component of the specified component.
 */
static void
rc_set_parent(Xml_reg *xreg, Wsreg_component *comp,
    const Wsreg_component *parent)
{
	_Wsreg_instance *old_parent = NULL;
	_Wsreg_instance *new_parent = NULL;

	if (comp == NULL)
		return;

	old_parent = comp->parent;
	if (old_parent != NULL) {
		free_instance(old_parent);
		comp->parent = NULL;
	}
	if (parent != NULL) {
		new_parent =
		    create_instance(xreg, parent->id,
			parent->instance,
			parent->location, parent->version);
		comp->parent = new_parent;
	}
}

/*
 * Returns the value associated with the specified key in
 * the specified component.
 */
static char *
rc_get_data(const Wsreg_component *comp, const char *key)
{
	if (comp->app_data != NULL) {
		List *data = comp->app_data;
		data->reset_iterator(data);
		while (data->has_more_elements(data)) {
			_Wsreg_data *d =
			    data->next_element(data);
			if (d->key != NULL &&
			    strcmp(d->key, key) == 0) {
				return (d->value);
			}
		}
	}
	return (NULL);
}

/*
 * Associates the specified value with the specified key in the
 * specified component.
 */
static int
rc_set_data(Wsreg_component *comp,
    const char *key, const char *value)
{
	List *data = comp->app_data;

	/*
	 * Are we removing a value or adding/replacing a value?
	 */
	if (value == NULL) {
		/*
		 * Removing a value.
		 */
		if (data != NULL) {
			data->reset_iterator(data);
			while (data->has_more_elements(data)) {
				_Wsreg_data *d =
				    data->next_element(data);
				if (d->key != NULL &&
				    strcmp(d->key, key) == 0) {
					data->remove(data, d, NULL);
					free_data(d);

					/*
					 * Should we remove the list?
					 */
					if (data->size(data) == 0) {
						data->free(data,
						    free_data);
						data = NULL;
						comp->app_data = NULL;
					}
					return (1);
				}
			}
		}
		return (1);
	} else {
		/*
		 * Adding/replacing a value.
		 */
		_Wsreg_data *d = NULL;
		String_util *sutil = _wsreg_strutil_initialize();

		if (data != NULL) {
			data->reset_iterator(data);
			while (data->has_more_elements(data)) {
				d = data->next_element(data);

				if (d->key != NULL &&
				    strcmp(d->key, key) == 0) {
					/*
					 * Replace the value.
					 */
					free(d->value);
					d->value = clone_string(value);

					/*
					 * Trim the whitespace from the
					 * end of the value.  This
					 * whitespace is not preserved
					 * in the xml file.
					 */
					sutil->trim_whitespace(
						d->value);
					return (1);
				}
			}
		} else {
			data = _wsreg_list_create();
			comp->app_data = data;
		}

		/*
		 * Add the value.
		 */
		d = (_Wsreg_data*)wsreg_malloc(sizeof (_Wsreg_data));
		d->key = clone_string(key);
		d->value = clone_string(value);

		/*
		 * Trim the whitespace from the end of the
		 * key and value.  This whitespace is not
		 * preserved in the xml file.
		 */
		sutil->trim_whitespace(d->key);
		sutil->trim_whitespace(d->value);
		data->add_element(data, d);
		return (1);
	}
}

/*
 * Returns a NULL-terminated array of key/value pairs stored in
 * the specified component.
 *
 * The even indexes of the resulting array represent the keys;
 * the odd indexes represent the values.
 *
 * It is the responsibility of the client to free the resulting
 * array, but not the contents of that array.
 */
static char **
rc_get_data_pairs(const Wsreg_component *comp)
{
	char **dataArray = NULL;
	int pos = 0;

	if (comp != NULL && comp->app_data != NULL) {
		List *data = comp->app_data;
		int arraySize = (data->size(data) + 1)  *2;

		dataArray = (char **)wsreg_malloc(sizeof (char *) * arraySize);
		(void) memset(dataArray, 0, sizeof (char *) * arraySize);

		data->reset_iterator(data);
		while (data->has_more_elements(data)) {
			_Wsreg_data *d = data->next_element(data);

			dataArray[pos++] = d->key;
			dataArray[pos++] = d->value;
		}
	}
	return (dataArray);
}

/*
 * Returns a sparse component representing the parent of the
 * specified component.  This call does not completely fill out
 * the component structure because it does no registry access
 */
static Wsreg_component *
rc_get_parent_reference(const Wsreg_component *comp)
{
	Wsreg_component *result = NULL;

	if (comp != NULL) {
		_Wsreg_instance *parent = comp->parent;
		if (parent != NULL) {
			result = wsreg_create_component(parent->id);
			wsreg_set_instance(result, parent->instance);
			wsreg_set_version(result, parent->version);
		}
	}
	return (result);
}

/*
 * Returns an array of sparse components representing the children
 * of the specified component.  This call does not completely fill
 * out the component structure because it does no registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
static Wsreg_component **
rc_get_child_references(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;

	if (comp != NULL) {
		result = create_ref_array((List*)comp->children);
	}
	return (result);
}

/*
 * Returns an array of sparse components representing the components
 * that the specified component requires.  This call does not
 * completely fill out the component structure because it does no
 * registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
static Wsreg_component **
rc_get_required_references(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;

	if (comp != NULL) {
		result = create_ref_array((List*)comp->required);
	}
	return (result);
}


/*
 * Returns an array of sparse components representing the components
 * that require the specified component.  This call does not
 * completely fill out the component structure because it does no
 * registry access.
 *
 * It is the responsibility of the caller to free the resulting
 * array and its contents.
 */
static Wsreg_component **
rc_get_dependent_references(const Wsreg_component *comp)
{
	Wsreg_component **result = NULL;

	if (comp != NULL) {
		result = create_ref_array((List*)comp->dependent);
	}
	return (result);
}

/*
 * Initializes the Reg_comp object.  Since there are no non-static
 * methods and no object-private data, there is no need to ever
 * create more than one Reg_comp object.  There is no free method
 * for this object.
 */
Reg_comp *
_wsreg_comp_initialize()
{
	Reg_comp *rc = comp_obj;
	if (rc == NULL) {
		rc = (Reg_comp *)wsreg_malloc(sizeof (Reg_comp));
		/*
		 * Initialize the method set.
		 */
		rc->create = rc_create;
		rc->free = rc_free;
		rc->free_array = rc_free_array;
		rc->set_id = rc_set_id;
		rc->get_id = rc_get_id;
		rc->set_instance = rc_set_instance;
		rc->get_instance = rc_get_instance;
		rc->set_version = rc_set_version;
		rc->get_version = rc_get_version;
		rc->set_unique_name = rc_set_unique_name;
		rc->get_unique_name = rc_get_unique_name;
		rc->add_display_name = rc_add_display_name;
		rc->remove_display_name = rc_remove_display_name;
		rc->get_display_name = rc_get_display_name;
		rc->get_display_languages = rc_get_display_languages;
		rc->set_type = rc_set_type;
		rc->get_type = rc_get_type;
		rc->set_location = rc_set_location;
		rc->get_location = rc_get_location;
		rc->set_uninstaller = rc_set_uninstaller;
		rc->get_uninstaller = rc_get_uninstaller;
		rc->set_vendor = rc_set_vendor;
		rc->get_vendor = rc_get_vendor;
		rc->equal = rc_equal;
		rc->clone = rc_clone;
		rc->add_required = rc_add_required;
		rc->remove_required = rc_remove_required;
		rc->get_required = rc_get_required;
		rc->add_dependent = rc_add_dependent;
		rc->remove_dependent = rc_remove_dependent;
		rc->get_dependent = rc_get_dependent;
		rc->get_children = rc_get_children;
		rc->add_child = rc_add_child;
		rc->remove_child = rc_remove_child;
		rc->add_compatible_version = rc_add_compatible_version;
		rc->remove_compatible_version = rc_remove_compatible_version;
		rc->get_compatible_versions = rc_get_compatible_versions;
		rc->get_parent = rc_get_parent;
		rc->set_parent = rc_set_parent;
		rc->get_data = rc_get_data;
		rc->set_data = rc_set_data;
		rc->get_data_pairs = rc_get_data_pairs;
		rc->get_parent_reference = rc_get_parent_reference;
		rc->get_child_references = rc_get_child_references;
		rc->get_required_references = rc_get_required_references;
		rc->get_dependent_references = rc_get_dependent_references;
		rc->clone_array = rc_clone_array;
		rc->array_size = rc_array_size;

		comp_obj = rc;
	}
	return (rc);
}

/*
 * Frees the specified localized string structure.  The data type
 * is "void *" so it conforms to the free function used by the
 * list object.
 */
static void
free_localized_string(void *data)
{
	_Wsreg_localized_string *d = data;
	if (d != NULL) {
		if (d->language != NULL) {
			free(d->language);
			d->language = NULL;
		}
		if (d->string != NULL) {
			free(d->string);
			d->string = NULL;
		}
		free(d);
		d = NULL;
	}
}

/*
 * Frees the specified component instance.  The data type is
 * "void *" so it conforms to the free function used by the
 * list object.
 */
static void
free_instance(void *data)
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

/*
 * Frees the specified key/value pair.  The data type is
 * "void *" so it conforms to the free function used by the
 * list object.
 */
static void
free_data(void *data)
{
	_Wsreg_data *d = data;
	if (d != NULL) {
		if (d->key != NULL) {
			free(d->key);
			d->key = NULL;
		}
		if (d->value != NULL) {
			free(d->value);
			d->value = NULL;
		}
		free(d);
		d = NULL;
	}
}

/*
 * Returns true if the specified strings are equal; false otherwise.
 */
static int
fields_equal(const char *field1, const char *field2)
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
 * Returns true if the specified lists are equal; false otherwise.
 * The equality of the data stored in the list is evaluated with
 * the specified check function.
 */
static int
lists_equal(List *list1, List *list2,
    int (*check)(const void*, const void*))
{
	if (list1 != NULL && list2 != NULL) {
		if (list1->size(list1) != list2->size(list2))
			return (0);
		list1->reset_iterator(list1);
		while (list1->has_more_elements(list1)) {
			void *list1Data = list1->next_element(list1);

			if (!list2->contains(list2, list1Data, (Equal)check))
				return (0);
		}
		return (1);
	}
	if (list1 == NULL) {
		if (list2 == NULL || list2->size(list2) == 0)
			return (1);
	}
	if (list2 == NULL) {
		if (list1 == NULL || list1->size(list1) == 0)
			return (1);
	}
	return (0);
}

/*
 * Returns true if the specified localized strings are equal; false
 * otherwise.
 */
static int
localized_strings_equal(const _Wsreg_localized_string *s1,
    const _Wsreg_localized_string *s2)
{
	if (s1 != NULL &&
	    s2 != NULL) {
		if (!fields_equal(s1->language, s2->language)) {
			return (0);
		}
		if (!fields_equal(s1->string, s2->string)) {
			return (0);
		}
		return (1);
	}
	return (s1 == s2);
}

/*
 * Returns true if the specified instance structures are equal;
 * false otherwise.
 */
static int
instances_equal(const _Wsreg_instance *inst1, const _Wsreg_instance *inst2)
{
	if (inst1 != NULL &&
	    inst2 != NULL) {
		if (!fields_equal(inst1->id, inst2->id)) {
			return (0);
		}
		if (inst1->instance != inst2->instance) {
			return (0);
		}
		if (!fields_equal(inst1->version, inst2->version)) {
			return (0);
		}
		return (1);
	}
	return (inst1 == inst2);
}

/*
 * Returns true if the specified data structures are equal;
 * false otherwise.
 */
static int
data_equal(const _Wsreg_data *data1, const _Wsreg_data *data2)
{
	if (data1 != NULL &&
	    data2 != NULL) {
		if (!fields_equal(data1->key, data2->key)) {
			return (0);
		}
		if (!fields_equal(data1->value, data2->value)) {
			return (0);
		}
		return (1);
	}
	return (data1 == data2);
}

/*
 * Returns a clone of the specified localized string.  The
 * data type for the specified string is "void *" so it conforms
 * to the clone function used by the list object.
 */
static void *
clone_localized_string(void *p)
{
	_Wsreg_localized_string *s = (_Wsreg_localized_string *)p;
	_Wsreg_localized_string *returnString = NULL;

	if (s != NULL) {
		returnString =
		    (_Wsreg_localized_string*)
		    wsreg_malloc(sizeof (_Wsreg_localized_string));
		returnString->language = clone_string(s->language);
		returnString->string = clone_string(s->string);
	}
	return (returnString);
}

/*
 * Returns a clone of the specified instance structure.
 */
static _Wsreg_instance *
clone_instance(const _Wsreg_instance *i)
{
	_Wsreg_instance *newinstance = NULL;
	if (i != NULL) {
		newinstance = wsreg_malloc(sizeof (_Wsreg_instance));
		newinstance->instance = i->instance;

		newinstance->id = clone_string(i->id);
		newinstance->version = clone_string(i->version);
	}
	return (newinstance);
}

/*
 * Returns a clone of the specified string.
 */
static char *
clone_string(const char *s)
{
	char *returnString = NULL;
	if (s != NULL) {
		returnString = (char *)wsreg_malloc(sizeof (char) *
		    (strlen(s) + 1));
		(void) strcpy(returnString, s);
	}
	return (returnString);
}

/*
 * Returns a clone of the specified data structure.
 */
static _Wsreg_data *
clone_data(const _Wsreg_data *data)
{
	_Wsreg_data *returnData = NULL;

	if (data != NULL) {
		returnData = (_Wsreg_data*)wsreg_malloc(sizeof (_Wsreg_data));
		returnData->key = clone_string(data->key);
		returnData->value = clone_string(data->value);
	}
	return (returnData);
}

/*
 * Creates a component reference that contains the specified id,
 * instance, and version.  If instance is not provided, the
 * install location can be specified.
 */
static _Wsreg_instance *
create_instance(Xml_reg *xreg, char *compID, int instance,
    char *installLocation, char *version)
{
	_Wsreg_instance *comp = wsreg_malloc(sizeof (_Wsreg_instance));
	comp->id = NULL;
	comp->version = NULL;
	comp->instance = 0;

	if (compID != NULL) {
		if (instance > 0) {
			comp->instance = instance;
		} else if (installLocation != NULL) {
			/*
			 * Query for the component and get the instance number.
			 */
			Wsreg_query query;
			Wsreg_component **componentMatches = NULL;
			Wsreg_component *component = NULL;

			query.id = compID;
			query.instance = instance;
			query.location = installLocation;
			query.version = version;
			componentMatches = xreg->query(xreg, &query);
			if (componentMatches != NULL)
				component = componentMatches[0];
			if (component != NULL) {
				comp->instance = component->instance;
			} else {
				free(comp);
				return (NULL);
			}
		} else {
			/*
			 * Cannot create an instance without the instance
			 * number or the install location.
			 */
			free(comp);
			return (NULL);
		}

		comp->id = wsreg_malloc(sizeof (char)*strlen(compID) + 1);
		(void) strcpy(comp->id, compID);
		if (version != NULL) {
			comp->version =
			    wsreg_malloc(sizeof (char)*strlen(version) + 1);
			(void) strcpy(comp->version, version);
		}
	}
	return (comp);
}

/*
 * Creates an array of sparse components, each representing a component
 * instance in the specified component list.
 */
static Wsreg_component **
create_ref_array(List *componentList)
{
	Wsreg_component **compArray = NULL;
	int listPos = 0;

	if (componentList != NULL) {
		componentList->reset_iterator(componentList);
		compArray = (Wsreg_component**)
		    wsreg_malloc(sizeof (Wsreg_component*) *
			    (componentList->size(componentList) + 1));
		(void) memset(compArray, 0, sizeof (Wsreg_component*) *
		    (componentList->size(componentList) + 1));

		while (componentList->has_more_elements(componentList)) {
			_Wsreg_instance *compI =
			    componentList->next_element(componentList);

			if (compI != NULL) {
				/*
				 * Create a component with only the
				 * lightweight reference information.
				 */
				Wsreg_component *comp =
				    wsreg_create_component(compI->id);
				wsreg_set_instance(comp, compI->instance);
				wsreg_set_version(comp, compI->version);
				compArray[listPos++] = comp;
			}
		}
		if (listPos != 0) {
			/*
			 * Successful call resulting in a valid list.
			 */
			return (compArray);
		}

		/*
		 * Free the array; it has a length of 0.
		 */
		if (compArray != NULL) {
			free(compArray);
			compArray = NULL;
		}
	}
	return (NULL);
}

/*
 * Creates a component array, each element representing one
 * of the components in the specified component list.
 */
static Wsreg_component **
create_comp_array(Xml_reg *xreg, List *componentList)
{
	Wsreg_component **compArray = NULL;
	int listPos = 0;

	if (componentList != NULL) {
		componentList->reset_iterator(componentList);
		compArray = (Wsreg_component**)
		    wsreg_malloc(sizeof (Wsreg_component*) *
			    (componentList->size(componentList) + 1));
		(void) memset(compArray, 0, sizeof (Wsreg_component*) *
		    (componentList->size(componentList) + 1));

		while (componentList->has_more_elements(componentList)) {
			_Wsreg_instance *compI =
			    componentList->next_element(componentList);

			if (compI != NULL) {
				/*
				 * Fill out the query structure and get the
				 * component.
				 */
				Wsreg_component **compMatches = NULL;
				Wsreg_component *comp = NULL;
				Wsreg_query query;

				query.id = compI->id;
				query.instance = compI->instance;
				query.version = compI->version;
				query.unique_name = NULL;
				query.location = NULL;

				compMatches = xreg->query(xreg, &query);
				if (compMatches != NULL) {
					comp = compMatches[0];
					free(compMatches);
				}
				if (comp != NULL) {
					compArray[listPos++] = comp;
				}
			}
		}
		if (listPos != 0) {
			/*
			 * Successful call resulting in a valid list.
			 */
			return (compArray);
		}

		/*
		 * Free the array; it has a length of 0.
		 */
		if (compArray != NULL) {
			free(compArray);
			compArray = NULL;
		}
	}
	return (NULL);
}
