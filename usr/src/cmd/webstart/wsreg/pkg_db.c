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


#include "boolean.h"
#include <wsreg.h>
#include "cluster_file_io.h"
#include "pkg_db.h"
#include "list.h"
/*
 * Module: prodreg_spmi.c
 *
 * Description: Routines used to query spmisoft library and build a
 * java.util.Vector of all system packages/clusters/metaclusters
 */

/*
 * The Pkg_db class only has static methods.  This object
 * is created only once and that single reference is
 * passed to all clients.
 */
static Pkg_db *pkg_obj = NULL;

static int
elapsed_time(struct timeval before, struct timeval after)
{
/*   double elapsed_time = (after.tv_usec - before.tv_usec) * 1000; */
	int elapsed_time = (after.tv_sec - before.tv_sec);
	return (elapsed_time);
}

/*
 * local functions
 */
static int _sysreg_get_all(List* list);

static Wsreg_component **
pkgdb_get_pkg_db()
{

	/*
	 * Returns all component in a vector
	 */
	List *components;
	Wsreg_component **componentArray;
	Wsreg_component *component;
	int count;
	int i;

	/*
	 * Initialize linked list to hold components
	 */
	components = _wsreg_list_create();

	/*
	 * Now we call the system to get all the components
	 */

	/*
	 * Create an array of components.
	 */
	count = components->size(components);
	componentArray = (Wsreg_component**)malloc((count + 1) *
	    sizeof (Wsreg_component *));
	if (componentArray == NULL) {
		/* could not allocate array */
		return (NULL);
	}

	/*
	 * reset list to front
	 */
	components->reset_iterator(components);

	/*
	 * iterate through links, retrieving data and putting
	 * in list of structures
	 */
	i = 0;
	while (components->has_more_elements(components)) {
		component = (Wsreg_component *)
		    components->next_element(components);
		componentArray[i++] = component;
	}

	/*
	 * Terminate array
	 */
	componentArray[count] = NULL;

	/*
	 * Free the list, but not the elements of the list because
	 * they are now in the array.
	 */
	components->free(components, NULL);

	/*
	 * Now return the filled-in java.util.Vector
	 */
	return (componentArray);
}

/*
 *
 * Module: _sysreg_get_all
 *
 * Description:
 * Fills in linked list with all system components
 *
 * Scope: local
 *
 * Returns: 0 on success, non-zero otherwise
 */
static int
_sysreg_get_all(List* list) {
	Module * m;

	/*
	 * Throttle spmi library to load in all software
	 */
	if (load_installed("/", FALSE) == NULL) {
		return (-1);
	}

	m = get_media_head();

	/*
	 * Recursively visit list of modules, adding each
	 * to the list as we go along
	 */
	_walk_module(m, list, NULL);
	return (0);
}

/*
 *
 * Module: _convert_module
 *
 * Description:
 * Converts a Module data structure into a Wsreg_component
 * data structure, copying over information as necessary.
 *
 * Scope: local
 *
 * Returns: 0 on success, non-zero otherwise
 */
static int _convert_module(Module* m, Wsreg_component** comp,
    Wsreg_component* parent) {

	switch (m->type) {
	case PACKAGE:
	case CLUSTER:
	case METACLUSTER:
		if (m->info.mod != NULL) {
			*comp = wsreg_create_component(m->info.mod->m_name);
			wsreg_add_display_name(*comp,
			    "en",
			    m->info.mod->m_name);
			if (parent != NULL) {
				wsreg_set_parent(*comp, parent);
				wsreg_add_child_component(parent, *comp);
			}
			return (0);
		}
		break;
	default:
		break;

	}
	return (1);
}

/*
 * Module: _walk_module
 *
 * Description:
 * Recursively walks modinfo tree
 * Scope: local
 *
 * Returns: none.
 */
static void
_walk_module(Module * m, List* list, Wsreg_component* parent)
{
	Module * newmod;
	Wsreg_component* comp;
	Module* n;
	do {
		if (_convert_module(m, &comp, parent) == 0) {
			list->add_element(list, comp);
		} else {
			comp = NULL;
		}

		n = m->sub;
		for (; n != NULL; n = get_sub(n)) {
			_walk_module(n, list, comp);
		}
	}
	while (m = get_next(m));
}

Pkg_db *
_wsreg_pkgdb_initialize()
{
	Pkg_db *pkg = pkg_obj;
	if (pkg == NULL) {
		/*
		 * Initialize the object.
		 */
		pkg = (Pkg_db *)malloc(sizeof (Pkg_db));
		if (pkg != NULL) {
			/*
			 * Initialize the method set.
			 */
			pkg->get_pkg_db = pkgdb_get_pkg_db;

			pkg_obj = pkg;
		}
	}
	return (pkg);
}


/*
 * Stuff we replaced.  Do NOT look below here!
 */







#if 0
/*
 * Module: _walk_module
 *
 * Description:
 * Recursively walks modinfo tree
 * Scope: local
 *
 * Returns: none.
 */
static void
_walk_module(Module * m, TList* list, Wsreg_component* parent)
{
	Module * newmod;
	Wsreg_component* comp;
	TLink* link;
	Module* n;
	do {
		if (_convert_module(m, &comp, parent) == 0) {
			link = _make_link(comp);
			LLAddLink(*list, link, LLTail);
		} else {
			comp = NULL;
		}

		n = m->sub;
		for (; n != NULL; n = get_sub(n)) {
			_walk_module(n, list, comp);
		}
	}
	while (m = get_next(m));
}

/*
 *
 * Module: _make_link
 *
 * Description:
 * Makes a TLink out of a Wsreg_component suitable for
 * insertion into a linked list.
 *
 * Scope: local
 *
 * Returns: Pointer to new link if successful, NULL otherwise.
 */
static TLink*
_make_link(Wsreg_component* comp) {
	TLink l;
	if (LLCreateLink(&l, comp) == LLSuccess) {
		return (l);
	}
	return (NULL);

}

/*
 *
 * Module: _cleanList
 *
 * Description:
 * Wipes out a LList (linked list) and frees memory
 *
 * Scope: local
 *
 * Returns: none.
 */
static void _cleanList(TList* list) {
	LLClearList(list, _clean);
	/*
	 * Doesn't matter if cleanup failed, what are we gonna do?
	 */

	LLDestroyList(list, NULL);

}

static TLLError _clean(TLLData data) {
	wsreg_free_component((Wsreg_component*)(data));
	return (LLSuccess);
}

/*
 *
 * Module: _sysreg_get_all
 *
 * Description:
 * Fills in linked list with all system components
 *
 * Scope: local
 *
 * Returns: 0 on success, non-zero otherwise
 */
static int
_sysreg_get_all(TList* list) {
	Module * m;

	/*
	 * Throttle spmi library to load in all software
	 */
	if (load_installed("/", FALSE) == NULL) {
		return (-1);
	}

	m = get_media_head();

	/*
	 * Recursively visit list of modules, adding each
	 * to the list as we go along
	 */
	_walk_module(m, list, NULL);
	return (0);
}

static Wsreg_component **
pkgdb_get_pkg_db()
{

	/*
	 * Returns all component in a vector
	 */
	TList components;
	Wsreg_component **componentArray;
	Wsreg_component *component;
	int count;
	TLLData current_data;
	TLink current_link;
	struct timeval before;
	struct timeval spmi_complete;
	struct timeval conversion_complete;
	int i;
	List *wsreg_comps;

	gettimeofday(&before, NULL);

	/*
	 * Initialize linked list to hold components
	 */
	LLCreateList(&components, NULL);

	/*
	 * Now we call the system to get all the components
	 */
	if (_sysreg_get_all(&components) != 0) {
		return (NULL);
	}

	gettimeofday(&spmi_complete, NULL);

	/*
	 * now we convert all Wsreg_component structs to java
	 * ComponentDescriptions, and place them in the newly-allocated
	 * java.util.Vector object (if there are any)
	 */
	if (LLGetSuppliedListData(components, &count, NULL) != LLSuccess) {
		_cleanList(components);
		return (NULL);
	}

	componentArray = (Wsreg_component**)
	    malloc((count + 1) * sizeof (Wsreg_component *));
	if (componentArray == NULL) {
		/* could not allocate array */
		return (NULL);
	}

	/*
	 * reset list to front
	 */
	if (LLUpdateCurrent(components, LLHead) != LLSuccess) {
		_cleanList(components);
		return (NULL);
	}

	/*
	 * iterate through links, retrieving data and putting
	 * in list of structures
	 */
	for (i = 0; i < count; i++) {
		if (LLGetCurrentLinkData(components,
		    &current_link, &current_data) != LLSuccess) {
			_cleanList(components);
			return (NULL);
		}
		component = (Wsreg_component*)current_data;

		/* Add component to end of array */
		componentArray[i] = component;
		LLUpdateCurrent(components, LLNext);
	}

	/*
	 * Terminate array
	 */
	componentArray[count] = NULL;

	gettimeofday(&conversion_complete, NULL);

	/*
	 * Print time table.
	 */
	fprintf(stderr, "PKG_DB Time to call spmilib: %d sec.\n",
	    elapsed_time(before, spmi_complete));
	fprintf(stderr, "PKG_DB Time to convert from spmi structs to "
	    "Wsreg structs: %d sec\n",
	    elapsed_time(spmi_complete, conversion_complete));
	fprintf(stderr, "PKG_DB Total time: %d\n",
	    elapsed_time(before, conversion_complete));
	fprintf(stderr, "PKG_DB total components read = %d\n", count);

	/*
	 * Now return the filled-in java.util.Vector
	 */
	return (componentArray);
}
#endif
