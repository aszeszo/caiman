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


#include <stdio.h>
#include <fcntl.h>
#include <strings.h>
#include <unistd.h>
#include "cluster_file_io.h"
#include "hashtable.h"
#include "pkg_db_io.h"
#include "wsreg_private.h"
#include "wsreg.h"
#include "string_util.h"
#include "localized_strings.h"

#define	Private struct _Cluster_file_io_private

/*
 * Object-private data associated with a Cluster_file_io object.
 */
struct _Cluster_file_io_private
{
	char *cluster_file_name;
	char *clustertoc_file_name;
	char *inst_release_file_name;
	int readfd;
	int n_read;
	char *metacluster;
	char *os;
	char *version;
	char *line;
} _Cluster_file_io_private;

/*
 * The folder name for all packages not in the registry and
 * not part of any system metacluster.
 */
static char *other_folder_name = "unclassified_software";

/*
 * The folder name for all packages not in the registry and
 * part of the system metacluster.
 */
static char *os_folder_name = "solaris_os";

typedef enum {CLUSTER = 0, CLUSTERTOC, INST_RELEASE} _Cluster_file;

/*
 * The path to the CLUSTER file.
 */
static const char *_cluster = "/var/sadm/system/admin/CLUSTER";

/*
 * The path to the .clustertoc file.
 */
static const char *_clustertoc = "/var/sadm/system/admin/.clustertoc";

/*
 * The path to the INST_RELEASE file.
 */
static const char *_inst_release = "/var/sadm/system/admin/INST_RELEASE";


/* Private Function Prototypes */
static Wsreg_component *
convert_to_component(Hashtable *, Boolean);
static int
cfio_get_metacluster_name(Cluster_file_io *);
static int
cfio_get_os_version(Cluster_file_io *);
static int
cfio_open(Cluster_file_io *, _Cluster_file);
static int
cfio_read_buffer(Cluster_file_io *, char *);
static int
cfio_close(Cluster_file_io *);
static void
cfio_set_file_names(Cluster_file_io *, const char *, const char *,
    const char *);
static void
add_child(Wsreg_component *, Wsreg_component *);
static int
cfio_get_my_metacluster(Cluster_file_io *, Hashtable *,
    Hashtable *, Hashtable *, Hashtable *);
static List *
get_members(Wsreg_component *);
static void
hookup_pkg_dependencies(Cluster_file_io *, Hashtable *);
static List *
get_pkg_list(Wsreg_component *);
static Hashtable *
get_xall_db();

/*
 * Fills the specified Hashtable with components representing
 * all clusters found in the .clustertoc file.  Returns a
 * string representing the current installed metacluster.
 */
static int
cfio_fill_cluster_map(Cluster_file_io *cfio, Hashtable *cluster_map)
{
	/*
	 * Read through the file's KEY = VALUE pairs. Since we start at the
	 * beginning of the first KEY, the first '=' will seperate the beg-
	 * nning of it's VALUE. Since a VALUE can have numerous ' = ' in it
	 * we look for the next '\n' where the following char will be the
	 * beginning of the next KEY, etc. Unless pkginfo is larger then
	 * BUFSIZ (1024 on Solaris), only one efficient read is required.
	 */

	char buf[BUFSIZ+1];
	char key[BUFSIZ+1];
	char value[BUFSIZ+1];
	int key_count = 0, value_count = 0;
	String_util *sutil = _wsreg_strutil_initialize();
	register int i;
	typedef enum { KEY = 0, VALUE } _Ws_keyvalue_type;
	typedef enum {
		CLUSTER = 0,
		METACLUSTER,
		MY_METACLUSTER } _Ws_cluster_type;
	_Ws_keyvalue_type kv_flag = KEY;
	_Ws_cluster_type cluster_flag = CLUSTER;
	Hashtable *cluster_member = NULL;
	List *member_list = NULL;

	/*
	 * Open CLUSTERTOC file to get the metacluster and all clusters
	 */
	if (cfio_open(cfio, CLUSTERTOC) == 1) {
		return (1);
	}

	cluster_member = _wsreg_hashtable_create();
	member_list = _wsreg_list_create();
	/*
	 * Read all clusters and the installed metacluster into components
	 */
	while (cfio_read_buffer(cfio, buf) != 1) {
		for (i = 0; i < cfio->pdata->n_read; ++i) {

			/*
			 * Parse the key
			 */
			if (kv_flag == KEY) {

				/*
				 * The " = " designates the key is
				 * complete and to start
				 * parsing the value (or the char
				 * following the equals.)
				 */
				if (buf[i] == '=') {
					key[key_count] = '\0';
					kv_flag = VALUE;
					value_count = 0;

					/*
					 * See if we encountered an "END"
					 * tag which has no value
					 * and designates the end of a
					 * cluster or metacluster.
					 */
				} else if (buf[i] == '\n') {
					Wsreg_component *comp = NULL;
					void *v;
					key_count = 0;

					/*
					 * Add the member list to the
					 * hashtable.
					 */
					v = cluster_member->put(cluster_member,
					    "SUNW_CSRMEMBER", member_list);
					if (v != NULL)
						free(v);

					/*
					 * Create the component with the data
					 * read in so far.
					 * Add the new component to the
					 * component database.
					 * The convert_to_component function
					 * also clears the specified
					 * hashtable during its conversion.
					 * This allows us to continue reading
					 * data into the same hashtable
					 * without mixing data.
					 */
					comp = convert_to_component(
						cluster_member,
					    cluster_flag == MY_METACLUSTER);
					cluster_map->put(cluster_map,
					    wsreg_get_id(comp), comp);

					/*
					 * Create a new member list.  The old
					 * one was freed by the conversion
					 * function.
					 */
					member_list = _wsreg_list_create();

					/*
					 * More key left continue parsing it
					 */
				} else {
					key[key_count++] = buf[i];
				}

				/*
				 * Parse the value
				 */
			} else {
				/*
				 * kv_flag == VALUE
				 */
				if (buf[i] == '\n') {
					value[value_count] = '\0';
					kv_flag = KEY;
					key_count = 0;

					/*
					 * If the key is METACLUSTER check
					 * if it's the installed metacluster.
					 * We only create a component for
					 * that one.
					 */
					if (strcmp(key, "METACLUSTER") == 0) {
						cluster_flag = METACLUSTER;
						if (strcmp(value,
						    cfio->pdata->metacluster) ==
						    0) {
							cluster_flag =
							    MY_METACLUSTER;
						}
					}

					/*
					 * Add the value to the member list.
					 * This list will be processed into a
					 * delimited string in the conversion
					 * function.
					 */
					if (strcmp(key,
					    "SUNW_CSRMEMBER") == 0) {

						/*
						 * Duplicate the value
						 * because "value" is declared
						 * as a static buffer that is
						 * reused.
						 */
						member_list->add_element(
							member_list,
							    sutil->clone(
								    value));

					} else {
						/*
						 * Duplicate the value
						 * because "value" is declared
						 * as a static buffer that is
						 * reused.
						 */
						void *v;
						v = cluster_member->put(
							cluster_member,
							    key, sutil->clone(
								    value));
						if (v != NULL)
							free(v);
					}

				} else {
					/*
					 * More value left continue parsing
					 * it
					 */
					value[value_count++] = buf[i];
				}
			}
		}
	}

	/*
	 * Cleanup
	 */
	member_list->free(member_list, free);
	cluster_member->free(cluster_member, free);

	(void) cfio_close(cfio);
	return (0);
}

/*
 * Creates a hashtable from the specifed cluster map.  The
 * cluster map is a hashtable that maps package and cluster
 * names to the components that those names represent.
 *
 * The resulting hashtable serves as a quick reference to find
 * if a particular package or cluster is a system package or
 * cluster.  A simple call to hashtable->contains(name) will
 * return true if the specified name is a system package or
 * cluster; false otherwise.
 *
 * When freeing the resulting hashtable, be sure not to specify
 * a free function.  The values in the resulting hashtable should
 * not be freed.
 */
/*ARGSUSED*/
static Hashtable *
cfio_create_system_lookup(Cluster_file_io *cfio, Hashtable *cluster_map)
{
	Hashtable *system_lookup = NULL;
	List *pkg_names = cluster_map->keys(cluster_map);
	system_lookup = _wsreg_hashtable_create();

	pkg_names->reset_iterator(pkg_names);
	while (pkg_names->has_more_elements(pkg_names)) {
		List *cluster_list = NULL;
		Wsreg_component *cluster;

		/*
		 * The system lookup will store the value
		 * 1 for all system clusters and packages.
		 * The value is not important; only the fact that
		 * the key resides in the hashtable indicates that
		 * this is/is not a system entity.
		 *
		 * Why a hashtable?  Because a list is so darn slow.
		 */
		char *pkg_name =
		    (char *)pkg_names->next_element(pkg_names);
		cluster = cluster_map->get(cluster_map, pkg_name);
		system_lookup->put(system_lookup, pkg_name, (void *)1);

		/*
		 * The members of the metacluster represent child
		 * clusters.  Add all children to the system
		 * lookup table as well.
		 */
		cluster_list = get_members(cluster);
		cluster_list->reset_iterator(cluster_list);
		while (cluster_list->has_more_elements(cluster_list)) {
			pkg_name = (char *)
			    cluster_list->next_element(cluster_list);
			system_lookup->put(system_lookup, pkg_name,
			    (void *)1);
		}
		cluster_list->free(cluster_list, free);
	}
	pkg_names->free(pkg_names, NULL);
	return (system_lookup);
}

/*
 * Recursively adds the metacluster/cluster/package specified by
 * "name" to the specified core lookup.
 */
static void
add_to_core_lookup(Cluster_file_io *cfio, Hashtable *cluster_map,
    Hashtable *core_lookup, char *name)
{
	List *pkg_names = NULL;
	Wsreg_component *comp = NULL;

	/*
	 * Add the name to the core lookup hashtable.
	 */
	core_lookup->put(core_lookup, name, (void *)1);

	/*
	 * Get the component from the cluster map.
	 */
	comp = (Wsreg_component *)cluster_map->get(cluster_map, name);

	if (comp != NULL) {
		/*
		 * Add each child package (or cluster) to the core
		 * lookup.
		 */
		pkg_names = get_members(comp);
		if (pkg_names != NULL) {
			pkg_names->reset_iterator(pkg_names);
			while (pkg_names->has_more_elements(pkg_names)) {
				char *pkg_name =
				    (char *)pkg_names->next_element(pkg_names);
				add_to_core_lookup(cfio, cluster_map,
				    core_lookup, pkg_name);
			}
			pkg_names->free(pkg_names, free);
		}
	}
}

/*
 * Creates a hashtable from the specifed cluster map.  The
 * cluster map is a hashtable that maps package and cluster
 * names to the components that those names represent.
 *
 * The resulting hashtable serves as a quick reference to find
 * if a particular package or cluster is a core package or
 * cluster.  A simple call to hashtable->contains(name) will
 * return true if the specified name is a core package or
 * cluster; false otherwise.
 *
 * When freeing the resulting hashtable, be sure not to specify
 * a free function.  The values in the resulting hashtable should
 * not be freed.
 */
/*ARGSUSED*/
static Hashtable *
cfio_create_core_lookup(Cluster_file_io *cfio, Hashtable *cluster_map)
{
	char core_metacluster_name[] = "SUNWCreq";
	Hashtable *core_lookup = NULL;
	core_lookup = _wsreg_hashtable_create();

	add_to_core_lookup(cfio, cluster_map, core_lookup,
	    core_metacluster_name);
	return (core_lookup);
}

/*
 * Returns the name of the folder that contains all non-system software
 * that does not appear in the registry.
 */
static char *
cfio_get_other_folder_name()
{
	return (other_folder_name);
}

/*
 * Adds the specified component to the "Unclassified software" folder.
 * If the "Unclassified software" folder does not yet exist, it will
 * be created as a result of this function call.
 */
static void
cfio_add_other_folder(Hashtable *system, Wsreg_component *pkg)
{
	char display_name[] = "Unclassified Software";
	char *folder_name = cfio_get_other_folder_name();
	char uuid[] = "8f64eabf-1dd2-11b2-a3f1-0800209a5b6b";
	Wsreg_component *other = system->get(system, folder_name);

	if (other == NULL) {
		/*
		 * The os folder has not yet been created.
		 * Create it now and add it to the system table.
		 */
		other = wsreg_create_component(uuid);
		wsreg_set_unique_name(other, folder_name);
		wsreg_set_version(other, "1.0");
		wsreg_add_display_name(other, "en", display_name);
		wsreg_set_location(other, "/");
		wsreg_set_instance(other, 1);

		system->put(system, folder_name, other);
	}

	/*
	 * Hook up parent/child relationship.
	 */
	add_child(other, pkg);
	system->put(system, wsreg_get_unique_name(pkg), pkg);
}

/*
 * Returns the name of the folder that contains all system software that
 * does not appear in the registry.
 */
static char *
cfio_get_os_folder_name()
{
	return (os_folder_name);
}

/*
 * Adds the specified component to the "System Software" folder.
 * If the "System Software" folder does not yet exist, it will
 * be created as a result of this function call.
 */
static void
cfio_add_os_folder(Cluster_file_io *cfio, Hashtable *system,
    Wsreg_component *pkg)
{
	Wsreg_component *os;
	char *display_name;
	char *folder_name;
	char uuid[] = "a01ee8dd-1dd1-11b2-a3f2-0800209a5b6b";
	char *system_software_string = WSREG_SYSTEM_SOFTWARE;

	folder_name = cfio_get_os_folder_name();
	os = system->get(system, folder_name);

	if (os == NULL) {
		/*
		 * The os folder has not yet been created.
		 * Create it now and add it to the system table.
		 */
		  display_name = (char *)wsreg_malloc(sizeof (char) *
		      (strlen(cfio->pdata->os) +
			  strlen(cfio->pdata->version) +
			  strlen(system_software_string) + 1));
		  
		  sprintf(display_name, system_software_string, cfio->pdata->os,
		      cfio->pdata->version);
		
		os = wsreg_create_component(uuid);
		wsreg_set_unique_name(os, folder_name);
		wsreg_set_version(os, cfio->pdata->version);
		wsreg_add_display_name(os, "en", display_name);
		wsreg_set_location(os, "/");
		wsreg_set_instance(os, 1);

		/*
		 * Don't allow the system folder to be uninstalled from the
		 * registry viewer.
		 */
		wsreg_set_data(os, "noUninstall", "true");

		free(display_name);
		system->put(system, folder_name, os);
	}

	/*
	 * Hook up parent/child relationship.
	 */
	add_child(os, pkg);
}

/*
 * Adds the specified component to the proper folder for language
 * packages.  If the specified component localizes any package
 * that appears in the specified system hashtable, it is considered
 * a language package for the OS, and will be placed under the
 * "System Software" folder.  Otherwise, it will be placed under
 * the "Unclassified Software" folder.
 */
/*ARGSUSED*/
static void
cfio_add_other_localized_pkg(Hashtable *system, Wsreg_component *comp,
    Hashtable *pkg_table)
{
	char display_name[] = "Software Localizations";
	char folder_name[] = "software_localizations";
	char uuid[] = "a8dcab4f-1dd1-11b2-a3f2-0800209a5b6b";
	Wsreg_component *languages = system->get(system, folder_name);

	if (languages == NULL) {
		/*
		 * The language folder has not yet been created.
		 * Create it now and add it to the system table.
		 */
		languages = wsreg_create_component(uuid);
		wsreg_set_unique_name(languages, folder_name);
		wsreg_set_version(languages, "1.0");
		wsreg_add_display_name(languages, "en", display_name);
		wsreg_set_location(languages, "/");
		wsreg_set_instance(languages, 1);

		system->put(system, folder_name, languages);
		cfio_add_other_folder(system, languages);
	}

	system->put(system, wsreg_get_unique_name(comp), comp);

	/*
	 * Hook up parent/child relationship.
	 */
	add_child(languages, comp);
}

/*
 * Adds the specified package to the "Additional System Software"
 * folder.
 */
static void
cfio_add_additional_sys_pkg(Cluster_file_io *cfio, Hashtable *system,
    char *pkg_name, Hashtable *pkg_table)
{
	char display_name[] = "Additional System Software";
	char folder_name[] = "additional_system_software";
	char uuid[] = "b1c43601-1dd1-11b2-a3f2-0800209a5b6b";
	Wsreg_component *additional = system->get(system, folder_name);
	Wsreg_component *pkg = NULL;

	if (additional == NULL) {
		/*
		 * The additional folder has not yet been created.
		 * Create it now and add it to the system table.
		 */
		additional = wsreg_create_component(uuid);
		wsreg_set_unique_name(additional, folder_name);
		wsreg_set_version(additional, "1.0");
		wsreg_add_display_name(additional, "en", display_name);
		wsreg_set_location(additional, "/");
		wsreg_set_instance(additional, 1);

		system->put(system, folder_name, additional);
		cfio_add_os_folder(cfio, system, additional);
	}

	/*
	 * Remove the package from the pkg_table.
	 */
	pkg = (Wsreg_component *)pkg_table->remove(pkg_table, pkg_name);

	/*
	 * Hook up parent/child relationship.
	 */
	add_child(additional, pkg);
	system->put(system, pkg_name, pkg);
}

/*
 * Adds the specified component to the system software localizations
 * folder.
 */
/*ARGSUSED*/
static void
cfio_add_sys_localized_pkg(Cluster_file_io *cfio, Hashtable *system,
    Wsreg_component *comp, Hashtable *pkg_table)
{
	char display_name[] = "System Software Localizations";
	char folder_name[] = "system_software_localizations";
	char uuid[] = "b96ae9a9-1dd1-11b2-a3f2-0800209a5b6b";
	Wsreg_component *languages = system->get(system, folder_name);

	if (languages == NULL) {
		/*
		 * The language folder has not yet been created.
		 * Create it now and add it to the system table.
		 */
		languages = wsreg_create_component(uuid);
		wsreg_set_unique_name(languages, folder_name);
		wsreg_set_version(languages, "1.0");
		wsreg_add_display_name(languages, "en", display_name);
		wsreg_set_location(languages, "/");
		wsreg_set_instance(languages, 1);

		system->put(system, folder_name, languages);
		cfio_add_os_folder(cfio, system, languages);
	}

	system->put(system, wsreg_get_unique_name(comp), comp);

	/*
	 * Hook up parent/child relationship.
	 */
	add_child(languages, comp);
}

/*
 * Adds all remaining packages from the specified "pkg_table"
 * hashtable to the "my_metacluster" (system) hashtable.
 * The "system_lookup" table is used to find out if a
 * package is a system package (part of the OS).
 */
static void
cfio_add_remaining_pkgs(Cluster_file_io *cfio, Hashtable *system,
    Hashtable *pkg_table, Hashtable *system_lookup)
{
	/*
	 * Create a list from the remaining packages.  Look at each
	 * package and determine where to hang it in the system
	 * tree.
	 */
	Hashtable *registered_comps = get_xall_db();
	List *remaining_pkgs = pkg_table->keys(pkg_table);
	String_util *sutil = _wsreg_strutil_initialize();
	remaining_pkgs->reset_iterator(remaining_pkgs);
	while (remaining_pkgs->has_more_elements(remaining_pkgs)) {
		char *pkg_name = sutil->clone((char *)
		    remaining_pkgs->next_element(remaining_pkgs));
		Wsreg_component *comp = NULL;
		char *sunw_pkglist = NULL;

		/*
		 * If this is a system package, add it to
		 * additional system software.
		 */
		if (system_lookup->contains_key(system_lookup, pkg_name)) {
			cfio_add_additional_sys_pkg(cfio, system, pkg_name,
			    pkg_table);
			free(pkg_name);
			continue;
		}

		/*
		 * Check to see if this package is in the registry or
		 * is referenced by a component that is in the
		 * registry.
		 */
		if (registered_comps->contains_key(registered_comps,
		    pkg_name)) {
			/*
			 * The component is in the registry.  Do not
			 * add it to the system hashtable and remove
			 * it from the pkg_table.
			 */
			comp = pkg_table->remove(pkg_table, pkg_name);
			if (comp != NULL) {
				wsreg_free_component(comp);
			}
			free(pkg_name);
			continue;
		}

		/*
		 * Check to see if this is a localized package.
		 */
		comp = (Wsreg_component *)pkg_table->get(pkg_table, pkg_name);
		sunw_pkglist = wsreg_get_data(comp, "SUNW_PKGLIST");
		if (sunw_pkglist != NULL) {
			/*
			 * This is a localization package.  Does it
			 * belong in the "system" software or "other"
			 * software folder?
			 */
			char *locl_name = strtok(sunw_pkglist, ",");
			Boolean was_added = FALSE;
			if (locl_name == NULL) {
				/*
				 * Blank list.  Assume this is a
				 * Solaris System package.
				 */
				cfio_add_sys_localized_pkg(cfio, system, comp,
				    pkg_table);
				was_added = TRUE;
			}
			while (!was_added && locl_name != NULL) {
				if (system_lookup->contains_key(system_lookup,
				    locl_name)) {
					/*
					 * This package localizes a system
					 * package.
					 */
					cfio_add_sys_localized_pkg(cfio, system,
					    comp, pkg_table);
					was_added = TRUE;
				}
				locl_name = strtok(NULL, ",");
			}

			if (!was_added) {
				/*
				 * This package does not localize a system
				 * package.  Add it to "Unclassified/Languages"
				 */
				cfio_add_other_localized_pkg(system, comp,
				    pkg_table);
			}
			pkg_table->remove(pkg_table, pkg_name);
			free(pkg_name);
			continue;
		}

		/*
		 * This component is unclassified.
		 */
		cfio_add_other_folder(system, comp);

		pkg_table->remove(pkg_table, pkg_name);
		free(pkg_name);
	}
	remaining_pkgs->free(remaining_pkgs, NULL);
	registered_comps->free(registered_comps, (Free)wsreg_free_component);
}

/*
 * Returns an array of Wsreg_component structures representing the
 * entire package database.  This function is called by the viewer
 * to present a tree view of system and unclassified software.
 */
static Wsreg_component **
cfio_get_sys_pkgs(Progress *progress)
{
	Hashtable *xall = _wsreg_hashtable_create();
	Hashtable *system_lookup = NULL;
	Hashtable *core_lookup = NULL;
	Hashtable *pkg_table = NULL;
	Hashtable *my_metacluster = NULL;
	List *list = NULL;
	Wsreg_component **comp_array;
	int index = 0;
	Pkg_db_io *pkg_db_io = _wsreg_pkgdbio_initialize();

	/*
	 * Initialize cfio object
	 */
	Cluster_file_io *cfio = _wsreg_cfio_create();

	/*
	 * Set file names and paths
	 */
	cfio_set_file_names(cfio, _cluster, _clustertoc, _inst_release);

	/*
	 * Get the name of the installed metacluster
	 */
	cfio_get_metacluster_name(cfio);

	/*
	 * Get the name of the installed OS and Version
	 */
	cfio_get_os_version(cfio);

	/*
	 * Step 1:
	 * Fill in a hashtable that represents the clustertoc file.
	 */
	cfio_fill_cluster_map(cfio, xall);

	/*
	 * Step 2:
	 * Create a hashtable that serves as a quick lookup for system
	 * clusters and packages.
	 */
	system_lookup = cfio_create_system_lookup(cfio, xall);

	/*
	 * Step 3:
	 * Create a hashtable that serves as a quick lookup for core
	 * clusters and packages.
	 */
	core_lookup = cfio_create_core_lookup(cfio, xall);

	/*
	 * Step 4:
	 * Get all packages currently installed on the system.
	 */
	pkg_table = _wsreg_hashtable_create();
	progress->set_section_bounds(progress, 100, 1);
	pkg_db_io->get_all_pkg_data(pkg_table, progress);

	/*
	 * Step 5:
	 * Create a representation of the currently installed metacluster.
	 */
	my_metacluster = _wsreg_hashtable_create();
	cfio_get_my_metacluster(cfio, my_metacluster, xall, core_lookup,
	    pkg_table);

	/*
	 * Step 6:
	 * Add 'other' software to the hashtable.  This function
	 * goes through the packages remaining in the pkg_table
	 * and assigns them a place in the my_metacluster hashtable.
	 * This will later be converted into a component array
	 * and passed back to the client.
	 */
	cfio_add_remaining_pkgs(cfio, my_metacluster, pkg_table, system_lookup);

	/*
	 * Step 7: Finally, establish relationships between dependent
	 * and required components
	 */
	hookup_pkg_dependencies(cfio, my_metacluster);


	/*
	 * Done creating the component relationships. Create an array to
	 * return back to the caller.
	 */

	list = my_metacluster->elements(my_metacluster);
	comp_array = (Wsreg_component **)
	    wsreg_malloc(sizeof (Wsreg_component *) * (list->size(list) + 1));
	list->reset_iterator(list);
	index = 0;
	while (list->has_more_elements(list)) {
		comp_array[index] = (Wsreg_component *)list->next_element(list);
		index++;
	}
	comp_array[list->size(list)] = NULL;

	/*
	 * Don't free the contents of the list.  The components that
	 * are in the list are also in the newly created component
	 * array which will be returned to the caller.
	 */
	list->free(list, NULL);


	/*
	 * Don't free the contents of the hashtable.  The components
	 * that are in the hashtable are also in the newly created
	 * component array which will be returned to the caller.
	 */
	my_metacluster->free(my_metacluster, NULL);
	system_lookup->free(system_lookup, NULL);
	core_lookup->free(core_lookup, NULL);
	pkg_table->free(pkg_table, (Free)wsreg_free_component);

	/*
	 * The components remaining in the "xall" hashtable
	 * represent components that were not transferred into
	 * the component array being passed back to the client.
	 * Its contents should be freed.
	 */
	xall->free(xall, (Free)wsreg_free_component);
	cfio->free(cfio);

	return (comp_array);
}

/*
 * Adds components representing packages referenced by components
 * in the specified hashtable to the specified hashtable.  The hashtable
 * key must be the component's unique name.  The value in the hashtable
 * must be the component structure.
 */
static void
add_referenced_packages(Hashtable *comp_db)
{
	List *xall = comp_db->elements(comp_db);
	Pkg_db_io *pkg_db_io = _wsreg_pkgdbio_initialize();

	/*
	 * Go through the list of components and see if packages are
	 * being referenced.
	 */
	xall->reset_iterator(xall);
	while (xall->has_more_elements(xall)) {
		Wsreg_component *comp =
		    (Wsreg_component *)xall->next_element(xall);
		List *pkgs = get_pkg_list(comp);
		if (pkgs != NULL) {
			/*
			 * This component references packages.  Go through
			 * the list to be sure each package is already
			 * in the component database.
			 */
			pkgs->reset_iterator(pkgs);
			while (pkgs->has_more_elements(pkgs)) {
				char *pkg_name =
				    (char *)pkgs->next_element(pkgs);
				if (!comp_db->contains_key(comp_db, pkg_name)) {
					/*
					 * This package is not in the registry.
					 * Create a component that represents
					 * this package and then establish
					 * parent/child relationships.
					 */
					Wsreg_component *child =
					    pkg_db_io->get_pkg_data(pkg_name);
					if (child != NULL) {
						add_child(comp, child);
						comp_db->put(comp_db, pkg_name,
						    child);
					}
				} else {
					/*
					 * The package has been registered
					 * already.  Fill in the data from
					 * the pkginfo file.
					 */
					Wsreg_component *child =
					    (Wsreg_component *)
					    comp_db->get(comp_db, pkg_name);
					pkg_db_io->load_pkg_info(pkg_name,
					    child);
				}
			}
		}
	}
	xall->free(xall, NULL);
}

/*
 * Returns a hashtable of component structures representing every
 * registered component and all packages referenced by registered
 * components.
 */
static Hashtable *
get_xall_db()
{
	Wsreg_component **registered_components = wsreg_get_all();
	Hashtable *xall_db = NULL;
	int index;

	/*
	 * Create a simple database of registered components that serves as
	 * a quick lookup.
	 */
	xall_db = _wsreg_hashtable_create();
	if (registered_components != NULL) {
		index = 0;
		while (registered_components[index] != NULL) {
			char *unique_name =
			    wsreg_get_unique_name(registered_components[index]);
			if (unique_name != NULL) {
				xall_db->put(xall_db, unique_name,
				    registered_components[index]);
			}
			index++;
		}
		free(registered_components);
		registered_components = NULL;
	}

	/*
	 * Add referenced packages to the database.
	 */
	add_referenced_packages(xall_db);
	return (xall_db);
}

/*
 * Returns an array of component structures representing every registered
 * component and all packages referenced by registered components.
 */
static Wsreg_component **
cfio_get_xall()
{
	Hashtable *xall_db = NULL;
	Wsreg_component **registered_components = NULL;
	List *xall = NULL;
	int index;

	xall_db = get_xall_db();

	/*
	 * Create the component array from the database.
	 */
	xall = xall_db->elements(xall_db);
	registered_components = (Wsreg_component **)
	    wsreg_malloc(sizeof (Wsreg_component *) * (xall->size(xall) + 1));
	memset(registered_components, 0, sizeof (Wsreg_component *) *
	    (xall->size(xall) + 1));
	xall->reset_iterator(xall);
	index = 0;
	while (xall->has_more_elements(xall)) {
		registered_components[index] =
		    (Wsreg_component *)xall->next_element(xall);
		index++;
	}
	xall->free(xall, NULL);
	xall_db->free(xall_db, NULL);

	return (registered_components);
}

/*
 * Adds all child packages from the specified package into the
 * my_metacluster hashtable.  All child packages added to the
 * my_metacluster hashtable will be removed from the xall
 * and pkg_table hashtables.
 */
static void
cfio_add_child_packages(Wsreg_component *cluster, char *pkg_name,
    Hashtable *my_metacluster, Hashtable *xall, Hashtable *core_lookup,
    Hashtable *pkg_table)
{
	if (cluster != NULL && pkg_name != NULL) {
		/*
		 * Remove the package from the xall hashtable.  The
		 * package will appear in xall and in pkg_table.  Be
		 * sure that when we are done, the pkg is removed
		 * from both hashtables.
		 * Hashtable's remove method returns a pointer to the value
		 * associated with the specified key.
		 */
		Wsreg_component *pkg =
		    (Wsreg_component *)xall->remove(xall, pkg_name);
		if (pkg != NULL) {
			wsreg_free_component(pkg);
		}

		/*
		 * Request a Wsreg_component structure that represents the
		 * named package.
		 */
		pkg = (Wsreg_component *)pkg_table->remove(pkg_table, pkg_name);
		if (pkg != NULL) {
			if (core_lookup->contains_key(core_lookup, pkg_name)) {
				/*
				 * This package is part of the core metacluster.
				 * Make sure the user cannot uninstall it from
				 * the registry viewer.
				 */
				wsreg_set_data(pkg, "noUninstall", "true");
			}

			/*
			 * Set the cluster as the parent of this package.
			 */
			add_child(cluster, pkg);

			/*
			 * Add the package's Wsreg_component structure to
			 * the database.
			 */
			my_metacluster->put(my_metacluster, pkg_name, pkg);
		} else {
			/*
			 * The pkg is not installed.
			 */
			/*EMPTY*/
		}
	}
}

/*
 * Adds child clusters to the specified metacluster.
 */
static void
cfio_add_child_cluster(Wsreg_component *metacluster, char *cluster_name,
    Hashtable *my_metacluster, Hashtable *xall, Hashtable *core_lookup,
    Hashtable *pkg_table)
{
	/*
	 * Get the Wsreg_component structure that represents the
	 * child cluster.
	 */
	List *pkg_list = NULL;
	Wsreg_component *cluster =
	    (Wsreg_component *)xall->remove(xall, cluster_name);
	if (cluster != NULL) {
		if (core_lookup->contains_key(core_lookup, cluster_name)) {
			/*
			 * The cluster is part of the core metacluster.
			 * Make sure the user cannot uninstall it from
			 * the registry viewer.
			 */
			wsreg_set_data(cluster, "noUninstall", "true");
		}

		/*
		 * Add the cluster to the resulting hashtable.
		 */
		my_metacluster->put(my_metacluster, cluster_name, cluster);
		/*
		 * Set the cluster as a child of the
		 * metacluster.
		 */
		add_child(metacluster, cluster);

		/*
		 * The members of the cluster represent child
		 * packages.
		 */
		pkg_list = get_members(cluster);

		/*
		 * Look at each package that is a child of this
		 * cluster.
		 */
		pkg_list->reset_iterator(pkg_list);
		while (pkg_list->has_more_elements(pkg_list)) {
			char *pkg_name = (char *)
			    pkg_list->next_element(pkg_list);

			/*
			 * Add the packages associated with the
			 * current cluster member to the my_metacluster
			 * table.
			 */
			cfio_add_child_packages(cluster, pkg_name,
			    my_metacluster, xall, core_lookup,
			    pkg_table);
		}

		/*
		 * Free the list of package names.
		 */
		pkg_list->free(pkg_list, free);

		/*
		 * Remove the members from the cluster.
		 */
		wsreg_set_data(metacluster, "MEMBERS", NULL);
	} else {
		/*
		 * The specified cluster is not in the
		 * hashtable. It is probably a package.
		 * Upon doing some research, we found
		 * packages that were direct children of the
		 * metacluster.  Try reading the packgage in.
		 */
		char *pkg_name = cluster_name;

		/*
		 * Add the packages associated with the current cluster member
		 * to the my_metacluster table.
		 */
		cfio_add_child_packages(metacluster, pkg_name,
		    my_metacluster, xall, core_lookup, pkg_table);
	}
}

/*
 * Fills in the specified my_metacluster hashtable with all clusters associated
 * with my_metacluster and all packages associated with each of those clusters.
 */
static int
cfio_get_my_metacluster(Cluster_file_io *cfio, Hashtable *my_metacluster,
    Hashtable *xall, Hashtable *core_lookup, Hashtable *pkg_table)
{
	List *cluster_list = NULL;

	/*
	 * Get the metacluster.
	 */
	Wsreg_component *metacluster = xall->remove(xall,
	    cfio->pdata->metacluster);

	if (metacluster != NULL) {
		/*
		 * Make sure the metacluster cannot be uninstalled from
		 * the viewer.
		 */
		wsreg_set_data(metacluster, "noUninstall", "true");

		/*
		 * Add the current metacluster to the resulting hashtable.
		 */
		my_metacluster->put(my_metacluster, cfio->pdata->metacluster,
		    metacluster);
		cfio_add_os_folder(cfio, my_metacluster, metacluster);

		/*
		 * The members of the metacluster represent child
		 * clusters.
		 */
		cluster_list = get_members(metacluster);

		/*
		 * Look at each cluster that is a child of my metacluster.
		 */
		cluster_list->reset_iterator(cluster_list);
		while (cluster_list->has_more_elements(cluster_list)) {
			char *cluster_name = (char *)
			    cluster_list->next_element(cluster_list);

			/*
			 * Add the cluster referenced by cluster_name
			 * to the metacluster.
			 */
			cfio_add_child_cluster(metacluster, cluster_name,
			    my_metacluster, xall, core_lookup, pkg_table);
		}

		/*
		 * Free the list of cluster names.
		 */
		cluster_list->free(cluster_list, free);

		/*
		 * Remove the members from the app_data.
		 */
		wsreg_set_data(metacluster, "MEMBERS", NULL);
	}

	return (0);
}

/*
 * Converts the specified cluster_member into a component.
 */
static Wsreg_component *
convert_to_component(Hashtable *cluster_member, Boolean is_metacluster)
{
	Wsreg_component *component = NULL;
	if (cluster_member != NULL &&
	    cluster_member->size(cluster_member) > 0) {

		List *keys = cluster_member->keys(cluster_member);
		component = wsreg_create_component(NULL);
		keys->reset_iterator(keys);
		while (keys->has_more_elements(keys)) {
			char *key = (char *)keys->next_element(keys);
			if (strcmp(key, "SUNW_CSRMEMBER") == 0) {
				char *value;
				int value_length = 0;
				int index;
				List *cluster_names = (List *)
				    cluster_member->get(cluster_member, key);

				/*
				 * Get the length required to store the
				 * specified cluster names in a
				 * token-separated string.
				 */
				cluster_names->reset_iterator(cluster_names);
				while (cluster_names->has_more_elements(
					cluster_names)) {
					char *name = (char *)
					    cluster_names->next_element(
						    cluster_names);
					value_length += strlen(name);
				}
				/*
				 * Now figure out the size of the separators.
				 * The last name does not require a separator.
				 */
				value_length +=
				    cluster_names->size(cluster_names) - 1;

				/*
				 * Create the string.
				 */
				value = (char *)wsreg_malloc(sizeof (char) *
				    (value_length + 1));
				value[0] = '\0';
				cluster_names->reset_iterator(cluster_names);
				index = 0;
				while (cluster_names->has_more_elements(
					cluster_names)) {
					char *name = (char *)
					    cluster_names->next_element(
						    cluster_names);
					strcat(value, name);

					/*
					 * Append a separator to all but the
					 * last name.
					 */
					if (cluster_names->size(cluster_names) >
					    index + 1) {
						strcat(value, ":");
					}
					index++;
				}

				wsreg_set_data(component, "MEMBERS", value);
				free(value);
				cluster_member->remove(cluster_member, key);
				cluster_names->free(cluster_names, free);
			} else {
				char *value = (char *)cluster_member->get(
					cluster_member, key);
				if (strcmp(key, "CLUSTER") == 0 ||
				    strcmp(key, "METACLUSTER") == 0) {
					wsreg_set_unique_name(component, value);
					wsreg_set_id(component,
					    value);
				} else if (strcmp(key, "NAME") == 0) {
					wsreg_add_display_name(component,
					    "en", value);
				} else if (strcmp(key, "VENDOR") == 0) {
					wsreg_set_vendor(component, value);
				} else if (strcmp(key, "VERSION") == 0) {
					wsreg_set_version(component,
					    value);
				} else {
					wsreg_set_data(component, key, value);
				}
				if (is_metacluster) {
					wsreg_set_data(component, "METACLUSTER",
					    "TRUE");
				}
				free(cluster_member->remove(cluster_member,
				    key));
			}
		}
		keys->free(keys, NULL);
		wsreg_set_instance(component, 1);
	}

	return (component);
}

/*
 * Sets the currently installed metacluster name into the specified
 * Cluster_file_io object.
 */
static int
cfio_get_metacluster_name(Cluster_file_io *cfio)
{
	char buf[BUFSIZ+1];
	String_util *sutil = _wsreg_strutil_initialize();

	/* Open, read and close the CLUSTER file to get the metacluster name */
	if (cfio_open(cfio, CLUSTER) == 1) {
		return (1);
	}
	if (cfio_read_buffer(cfio, buf) == 1) {
		return (1);
	}
	(void) cfio_close(cfio);

	(void) strtok(buf, "=");
	cfio->pdata->metacluster = sutil->clone(strtok(NULL, "'\n'"));

	return (0);
}

/*
 * Sets the version of the currently installed OS into the specified
 * Cluster_file_io object.
 */
static int
cfio_get_os_version(Cluster_file_io *cfio)
{
	char buf[BUFSIZ+1];
	char *key;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Open, read and close the INST_RELEASE file to get the OS name
	 * and version.
	 */
	if (cfio_open(cfio, INST_RELEASE) == 1) {
		return (1);
	}
	if (cfio_read_buffer(cfio, buf) == 1) {
		return (1);
	}
	(void) cfio_close(cfio);

	/*
	 * Load OS and Version. Rev isn't used
	 */
	key = strtok(buf, "=");
	while (key != NULL) {
		if (strcmp(key, "OS") == 0) {
			cfio->pdata->os = sutil->clone(strtok(NULL, "'\n'"));
		} else if (strcmp(key, "VERSION") == 0) {
			cfio->pdata->version =
			    sutil->clone(strtok(NULL, "'\n'"));
		}
		key = strtok(NULL, "=");
	}

	return (0);
}

/*
 * Frees the specified Cluster_file_io object.
 */
static void
cfio_free(Cluster_file_io *cfio)
{
	if (cfio->pdata->cluster_file_name != NULL)
		free(cfio->pdata->cluster_file_name);
	if (cfio->pdata->clustertoc_file_name != NULL)
		free(cfio->pdata->clustertoc_file_name);
	if (cfio->pdata->inst_release_file_name != NULL)
		free(cfio->pdata->inst_release_file_name);
	if (cfio->pdata->metacluster != NULL)
		free(cfio->pdata->metacluster);
	if (cfio->pdata->version != NULL)
		free(cfio->pdata->version);
	if (cfio->pdata->os != NULL)
		free(cfio->pdata->os);
	if (cfio->pdata->line != NULL)
		free(cfio->pdata->line);
	free(cfio->pdata);
	free(cfio);
}

/*
 * Opens the cluster file associated with the specified file id.
 */
static int
cfio_open(Cluster_file_io *cfio, _Cluster_file fileid)
{
	switch (fileid) {
	case CLUSTER:
		if ((cfio->pdata->readfd =
		    open(cfio->pdata->cluster_file_name, O_RDONLY, 0)) == -1) {
			/*
			 * The open failed
			 */
			return (1);
		}
		break;

	case CLUSTERTOC:
		if ((cfio->pdata->readfd =
		    open(cfio->pdata->clustertoc_file_name, O_RDONLY, 0)) ==
		    -1) {
			/*
			 * The open failed
			 */
			return (1);
		}
		break;

	case INST_RELEASE:
		if ((cfio->pdata->readfd =
		    open(cfio->pdata->inst_release_file_name, O_RDONLY, 0)) ==
		    -1) {
			/*
			 * The open failed
			 */
			return (1);
		}
		break;
	}

	return (0);
}

/*
 * Reads all data from the open cluster file into the specified
 * buffer.
 */
static int
cfio_read_buffer(Cluster_file_io *cfio, char *buf)
{
	if ((cfio->pdata->n_read = read(cfio->pdata->readfd, buf, BUFSIZ)) <=
	    0) {
		return (1);
	} else {
		buf[cfio->pdata->n_read] = '\0';
		return (0);
	}
}

/*
 * Closes the specified cluster file io object.
 */
static int
cfio_close(Cluster_file_io *cfio)
{
	(void) close(cfio->pdata->readfd);

	return (0);
}

/*
 * Sets the filenames for each of the cluster files this object
 * knows how to read.
 */
static void
cfio_set_file_names(Cluster_file_io *cfio, const char *cluster_file_name,
    const char *clustertoc_file_name, const char *inst_release_file_name)
{
	struct _Cluster_file_io_private *pdata = cfio->pdata;
	String_util *sutil = _wsreg_strutil_initialize();
	char *alternate_root = wsreg_get_alternate_root();
	if (pdata->cluster_file_name != NULL)
		free(pdata->cluster_file_name);
	if (pdata->clustertoc_file_name != NULL)
		free(pdata->clustertoc_file_name);
	if (pdata->inst_release_file_name != NULL)
		free(pdata->inst_release_file_name);
	pdata->cluster_file_name = sutil->prepend(sutil->clone(
	    cluster_file_name), alternate_root);
	pdata->clustertoc_file_name = sutil->prepend(sutil->clone(
	    clustertoc_file_name), alternate_root);
	pdata->inst_release_file_name = sutil->prepend(sutil->clone(
	    inst_release_file_name), alternate_root);
}

/*
 * Returns a list of strings representing the
 * members of the specified component.
 */
static List *
get_members(Wsreg_component *comp)
{
	List *result = _wsreg_list_create();
	String_util *sutil = _wsreg_strutil_initialize();
	if (comp != NULL) {
		char *members = wsreg_get_data(comp, "MEMBERS");
		if (members != NULL) {
			char *members_clone = sutil->clone(members);
			char *member = strtok(members_clone, ":");
			while (member != NULL) {
				result->add_element(result,
				    sutil->clone(member));
				member = strtok(NULL, ":");
			}
			free(members_clone);
		}
	}
	return (result);
}

/*
 * Creates a lightweight component reference that references the
 * specified component.
 */
static _Wsreg_instance *
get_component_reference(Wsreg_component *comp)
{
	_Wsreg_instance *inst = (_Wsreg_instance *)
	    wsreg_malloc(sizeof (_Wsreg_instance));
	String_util *sutil = _wsreg_strutil_initialize();
	inst->id = sutil->clone(wsreg_get_id(comp));
	inst->version = sutil->clone(wsreg_get_version(comp));
	inst->instance = wsreg_get_instance(comp);
	return (inst);
}

/*
 * Adds the specified required component to the specified component.
 * The dependent component association is established as well.
 */
static void
add_required_comp(Wsreg_component *comp, Wsreg_component *req_comp)
{
	if (comp != NULL && req_comp != NULL) {
		List *required_comps = (List *)comp->required;
		List *dependent_comps = (List *)req_comp->dependent;

		if (required_comps  == NULL) {
			required_comps = _wsreg_list_create();
			comp->required = required_comps;
		}
		if (dependent_comps  == NULL) {
			dependent_comps = _wsreg_list_create();
			req_comp->dependent = dependent_comps;
		}

		required_comps->add_element(required_comps,
		    get_component_reference(req_comp));
		dependent_comps->add_element(dependent_comps,
		    get_component_reference(comp));
	}
}

/*
 * Adds the specified child component as a child of the specified
 * component.
 */
static void
add_child(Wsreg_component *parent, Wsreg_component *child)
{
	if (parent != NULL && child != NULL) {
		List *children = (List *)parent->children;

		if (children == NULL) {
			children = _wsreg_list_create();
			parent->children = children;
		}

		children->add_element(children, get_component_reference(child));
		/*
		 * Only set the parent if it hasn't already been set.
		 */
		if (child->parent == NULL) {
			child->parent = get_component_reference(parent);
		}

		add_required_comp(parent, child);
	}
}

/*
 * This function hooks up dependencies which are stored in
 * Wsreg_component app_data under "DEPEND".
 */
/*ARGSUSED*/
static void
hookup_pkg_dependencies(Cluster_file_io *cfio, Hashtable *comp_db)
{
	List *component_list = NULL;

	/*
	 * Cycle through all components in the hashtable
	 * looking for components that have a "DEPEND" in
	 * their app_data.
	 */
	component_list = comp_db->elements(comp_db);
	component_list->reset_iterator(component_list);
	while (component_list->has_more_elements(component_list)) {
		Wsreg_component *pkg = (Wsreg_component *)
		    component_list->next_element(component_list);
		char *dependencies = wsreg_get_data(pkg, "PREREQUISITE");
		if (dependencies != NULL) {
			/*
			 * We found a package with dependencies.
			 */
			char *dependency = strtok(dependencies, ",");
			while (dependency != NULL) {
				Wsreg_component *required_pkg =
				    (Wsreg_component *)
				    comp_db->get(comp_db, dependency);
				if (required_pkg != NULL) {
					/*
					 * The pkg depends on (requires) the
					 * required_pkg.
					 */
					add_required_comp(pkg, required_pkg);
				}

				dependency = strtok(NULL, ",");
			}

			/*
			 * Remove the prerequisites from the app_data.
			 *
			 * wsreg_set_data(pkg, "PREREQUISITE", NULL);
			 */
		}
	}

	/*
	 * Don't free the contents of the list because they are
	 * the same references that are in the hashtable.
	 */
	component_list->free(component_list, NULL);
}

/*
 * Returns a list of package names associated with
 * the specified component.  If the component is not
 * associated with any packages, NULL is returned.
 */
static List *
get_pkg_list(Wsreg_component *comp)
{
	List *pkg_list = NULL;
	char *packages = wsreg_get_data(comp, "pkgs");
	String_util *sutil = _wsreg_strutil_initialize();
	if (packages != NULL) {
		/*
		 * Packages is a space-separated list
		 * of Solaris packages.
		 */
		char *pkg_name = NULL;
		packages = sutil->clone(packages);
		pkg_list = _wsreg_list_create();
		pkg_name = strtok(packages, " ");
		while (pkg_name != NULL) {
			pkg_list->add_element(pkg_list,
			    sutil->clone(pkg_name));
			pkg_name = strtok(NULL, " ");
		}
		free(packages);
	}
	return (pkg_list);
}

/*
 * This function sets the application data
 * "isDamaged" to "TRUE" for all components that
 * represent Solaris packages that are not currently
 * installed on the system.
 */
static void
cfio_flag_broken_components(Wsreg_component **comps)
{
	int index = 0;
	Pkg_db_io *pkg_io = _wsreg_pkgdbio_initialize();

	while (comps[index] != NULL) {
		Wsreg_component *comp = comps[index];
		List *pkg_list = get_pkg_list(comp);
		if (pkg_list != NULL) {
			pkg_list->reset_iterator(pkg_list);
			while (pkg_list->has_more_elements(pkg_list)) {
				char *pkg_name =
				    pkg_list->next_element(pkg_list);
				Wsreg_component *tmp_comp =
				    pkg_io->get_pkg_data(pkg_name);
				if (tmp_comp == NULL) {
					/*
					 * The package is not installed.
					 * The component's "isDamaged"
					 * flag should be set to
					 * "TRUE".
					 */
					wsreg_set_data(comp,
					    "isDamaged", "TRUE");
				} else {
					/*
					 * The package is installed.
					 */
					wsreg_free_component(tmp_comp);
				}
			}
			/*
			 * Free the package list.  The contents of
			 * the list are simple strings which can
			 * be released with the standard 'free'
			 * function.
			 */
			pkg_list->free(pkg_list, free);
		}
		index++;
	}
}

/*
 * Creates a new Cluster_file_io object.
 */
Cluster_file_io *
_wsreg_cfio_create()
{
	Cluster_file_io *cfio = (Cluster_file_io *)
	    wsreg_malloc(sizeof (Cluster_file_io));
	struct _Cluster_file_io_private *p = NULL;

	/*
	 * Initialize methods
	 */
	cfio->get_sys_pkgs = cfio_get_sys_pkgs;
	cfio->get_xall = cfio_get_xall;
	cfio->free = cfio_free;
	cfio->flag_broken_components = cfio_flag_broken_components;

	/*
	 * Initialize the object's private data.
	 */
	p = (struct _Cluster_file_io_private *)
	    wsreg_malloc(sizeof (struct _Cluster_file_io_private));
	p->cluster_file_name = NULL;
	p->clustertoc_file_name = NULL;
	p->inst_release_file_name = NULL;
	p->readfd = -1;
	p->n_read = -1;
	p->metacluster = NULL;
	p->os = NULL;
	p->version = NULL;
	p->line = NULL;
	cfio->pdata = p;
	return (cfio);
}
