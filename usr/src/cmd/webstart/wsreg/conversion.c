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


#include <stdlib.h>
#include <stdio.h>
#include <strings.h>
#include <ctype.h>
#include <sys/param.h>
#include "conversion.h"
#include "boolean.h"
#include "list.h"
#include "hashtable.h"
#include "string_util.h"
#include "file_util.h"
#include "reg_comp.h"
#include "pkg_db_io.h"

/*
 * This structure is used to bind object-private data
 * to a conversion object.
 */
struct _Conversion_private
{
	List *article_list;
	Progress *progress;
} _Conversion_private;

/*
 * Tree primitive.  The node is used to build a tree of
 * articles.  Registration of articles requires the conversion
 * of the articles into components, and the association of
 * components in a parent/child tree.
 */
struct _Node
{
	Article *article;
	Wsreg_component *component;
	int child_count;
	struct _Node **children;
} _Node;
#define	Node struct _Node

static List *
get_pkg_list(Wsreg_component *);
static int
prune_pkg_list(Wsreg_component *);

/*
 * Creates a node that contains a pointer to the specified
 * article.  The article is not cloned.
 */
static Node *
node_create(Article *a)
{
	Node *n = (Node*)wsreg_malloc(sizeof (Node));
	memset(n, 0, sizeof (Node));
	n->article = a;
	return (n);
}

/*
 * Frees the specified node.  The article and component
 * associated with the specified node are also freed.
 */
static void
node_free(Node *n)
{
	if (n != NULL) {
		if (n->article != NULL) {
			n->article->free(n->article);
			n->article = NULL;
		}
		if (n->component != NULL) {
			wsreg_free_component(n->component);
			n->component = NULL;
		}
		if (n->children != NULL) {
			int i = 0;
			while (n->children[i] != NULL) {
				node_free(n->children[i]);
				n->children[i] = NULL;
				i++;
			}
			free(n->children);
			n->children = NULL;
		}
		free(n);
	}
}

#if 0
/*
 * Diagnostic function that prints the tree of nodes.  This
 * is a recursive function.  All clients should use the entry
 * point function "print_tree"
 */
static void
recurse_print_tree(Node *root, int tab)
{
	if (root != NULL && root->article) {
		int i;
		for (i = 0; i < tab; i++) {
			(void) printf("\t");
		}
		(void) printf("%s\n",
		    root->article->get_mnemonic(root->article));
		if (root->children != NULL) {
			i = 0;
			while (root->children[i] != NULL) {
				recurse_print_tree(root->children[i], tab+1);
				i++;
			}
		}
	}
}

/*
 * The entry point function that prints the tree of article
 * objects.
 */
static void
print_tree(Node *root)
{
	(void) printf("tree:---------------------------------\n");
	recurse_print_tree(root, 0);
	(void) printf("--------------------------------------\n");
}
#endif

/*
 * Returns true if the specified key is valid; false otherwise.
 */
static int
valid_key(const char *key)
{
	char is_valid = 0;
	if (key != NULL &&
	    strlen(key) != NULL) {
		int index;
		int length = strlen(key);
		for (index = 0; !is_valid && index < length; index++) {
			is_valid = !isspace((int)key[index]);
		}
	}
	return (is_valid);
}

/*
 * Returns true if the specified value is valid; false otherwise.
 */
static int
valid_value(const char *value)
{
	/*
	 * Apply the same rules as for a key.
	 */
	return (valid_key(value));
}

/*
 * Returns a string that represents the command used
 * to uninstall the component.  The specified uninstaller
 * comes directly out of the article's "uninstallprogram"
 * property.
 */
static char *
get_uninstall_command(char *uninstaller)
{
	char *uninstall_command = NULL;
	String_util *sutil = _wsreg_strutil_initialize();
	/*
	 * Only modify the original uninstaller string if
	 * it references a Java class file.
	 */
	int len = strlen(uninstaller);
	if (len > strlen(".class") &&
	    strcmp(uninstaller + (len - strlen(".class")),
		".class") == 0) {
		/*
		 * Separate the class path from the classname.
		 */
		String_util *sutil = _wsreg_strutil_initialize();
		File_util *futil = _wsreg_fileutil_initialize();
		char tmp_classpath[MAXPATHLEN];
		char *classpath;
		char classname[MAXPATHLEN];
		char *name_start;
		int name_len;
		int prefix_len = 0;
		char *alternate_root = wsreg_get_alternate_root();
		int alternate_root_length = 0;

		/*
		 * This string will be the prefix of the
		 * Java command.
		 */
		char java_command[] = "/usr/bin/java -mx64m";

		/*
		 * The classpath ends where the last directory
		 * separator is.
		 */
		int index = sutil->last_index_of(uninstaller, '/');

		if (strlen(alternate_root) > 0) {
			/*
			 * Be sure to call get_cannonical_path to
			 * resolve possible links in the alternate
			 * root path.
			 */
			alternate_root =
			    futil->get_canonical_path(alternate_root);
			alternate_root_length = strlen(alternate_root);
			/*
			 * Prepend the alternate root to the uninstaller
			 * string so get_canonical_path can properly
			 * reduce.
			 */
			sprintf(tmp_classpath, "%s/", alternate_root);
			prefix_len = strlen(tmp_classpath);
		} else {
			alternate_root = NULL;
		}

		strncpy(tmp_classpath + prefix_len, uninstaller, index);
		tmp_classpath[index + prefix_len] = '\0';
		classpath = futil->get_canonical_path(tmp_classpath);

		/*
		 * The "+1" part omits the preceding '/'.
		 */
		name_start = uninstaller + index + 1;
		name_len = strlen(uninstaller + index + 1) - strlen(".class");
		strncpy(classname, name_start, name_len);
		classname[name_len] = '\0';

		/*
		 * Now construct the uninstall command.
		 */
		uninstall_command = (char *)wsreg_malloc(sizeof (java_command) +
		    sizeof (char) * (strlen(classpath) +
			strlen(classname) + strlen(" -classpath  \0")));
		(void) sprintf(uninstall_command, "%s -classpath %s %s",
		    java_command, (classpath + alternate_root_length),
		    classname);
		free(classpath);
		if (alternate_root != NULL) {
			free(alternate_root);
		}
	} else {
		/*
		 * The resulting uninstall command will
		 * simply be a copy of the original
		 * string.
		 */
		uninstall_command = sutil->clone(uninstaller);
	}
	return (uninstall_command);
}

/*
 * Converts the article associated with the specified node into a
 * component.  If the prunePkgList flag is true, package names in the
 * component's package list that are not currently installed on the
 * system will be removed from the package list.
 */
static Wsreg_component *
convert_to_component(Node *n, Boolean prunePkgList)
{
	Wsreg_component *component = NULL;
	int i;
	Article *a = n->article;
	Node **children = NULL;
	char **keys = NULL;
	char *unique_name = NULL;
	char *install_location = NULL;
	Wsreg_query *query;
	Revision **revisions = NULL;
	String_util *sutil = _wsreg_strutil_initialize();

	/*
	 * Look to see if the component already exists.
	 */
	unique_name = a->get_property(a, "mnemonic");
	install_location = a->get_property(a, "installlocation");

	query = wsreg_query_create();
	wsreg_query_set_unique_name(query, unique_name);
	wsreg_query_set_location(query, install_location);
	component = wsreg_get(query);
	wsreg_query_free(query);

	if (component == NULL) {
		/*
		 * The component has not yet been registered.  Fill
		 * in the unique id and the unique name with the
		 * article's mnemonic.
		 */
		component = wsreg_create_component(a->get_mnemonic(a));
		wsreg_set_unique_name(component, a->get_mnemonic(a));
	}

	/*
	 * Set the component's version.
	 */
	revisions = a->get_revisions(a);
	if (revisions != NULL) {
		char *version = NULL;
		int index = 0;
		while (revisions[index] != NULL) {
			if (revisions[index]->get_version(
				revisions[index]) != NULL) {
				if (version != NULL) {
					free(version);
				}
				version =
				    sutil->clone(revisions[index]->get_version(
						revisions[index]));
			}
			revisions[index]->free(revisions[index]);
			index++;
		}
		if (version != NULL) {
			wsreg_set_version(component, version);
			free(version);
		}
		free(revisions);
	}

	children = n->children;

	i = 0;
	while (children != NULL && children[i] != NULL) {
		Node *child = children[i];
		wsreg_add_child_component(component, child->component);
		wsreg_add_required_component(component,
		    child->component);
		i++;
	}

	keys = a->get_property_names(a);
	i = 0;
	while (keys != NULL && keys[i] != NULL) {
		char *key = keys[i];
		char *value = a->get_property(a, key);

		if (strcmp(key, "mnemonic") == 0 ||
		    strcmp(key, "articles") == 0 ||
		    strcmp(key, "articleids") == 0 ||
		    strcmp(key, "parent") == 0 ||
		    strcmp(key, "parentid") == 0) {
			/* EMPTY */
		} else if (strcmp(key, "version") == 0) {
			wsreg_set_version(component, value);
		} else if (strcmp(key, "vendor") == 0) {
			wsreg_set_vendor(component, value);
		} else if (strcmp(key, "installlocation") == 0) {
			wsreg_set_location(component, value);
		} else if (strcmp(key, "title") == 0) {
			wsreg_add_display_name(component, "en", value);
		} else if (strcmp(key, "uninstallprogram") == 0) {
			char *uninstaller = value;
			if (uninstaller != NULL) {
				/*
				 * If the uninstaller ends with
				 * ".class", prepend
				 * "/usr/bin/java -mx... to it.
				 */
				char *uninstall_command;
				uninstall_command =
				    get_uninstall_command(uninstaller);
				wsreg_set_uninstaller(component,
				    uninstall_command);
				free(uninstall_command);
			}
		} else {
			if (valid_key(key) && valid_value(value))
				wsreg_set_data(component, key, value);
		}
		i++;
	}

	if (keys != NULL) {
		free(keys);
	}
	wsreg_set_type(component, WSREG_COMPONENT);

	if (prunePkgList) {
		/*
		 * Be sure all packages referenced by this
		 * component are currently installed on the
		 * system.  Packages that are not currently
		 * installed on the system will be removed
		 * from the "pkgs" list.
		 */
		prune_pkg_list(component);
	}

	/*
	 * In prodreg 2.0, a version was optional.  Not a good
	 * idea!  If we do run into articles with no version,
	 * we will set the version to "1.0".  This case has
	 * not come up in practice yet.
	 */
	if (wsreg_get_version(component) == NULL) {
		wsreg_set_version(component, "1.0");
	}
	return (component);
}

/*
 * Removes all package names from the specified component's package
 * list that do not represent packages currently installed on the
 * system.  Returns the number of packages removed from the package
 * list.
 */
static int
prune_pkg_list(Wsreg_component *comp)
{
	int pkgs_removed = 0;
	Reg_comp *comp_util = _wsreg_comp_initialize();
	List *pkg_list = get_pkg_list(comp);
	if (pkg_list != NULL) {
		List *final_list = _wsreg_list_create();
		Pkg_db_io *pkg_db_io = _wsreg_pkgdbio_initialize();
		char *pkg_string = NULL;

		/*
		 * Look at each package name in the list to see if
		 * it represents an installed package.
		 */
		pkg_list->reset_iterator(pkg_list);
		while (pkg_list->has_more_elements(pkg_list)) {
			char *pkg_name =
			    (char *)pkg_list->next_element(pkg_list);
			Wsreg_component *pkg =
			    pkg_db_io->get_pkg_data(pkg_name);
			if (pkg != NULL) {
				/*
				 * The package is installed on the
				 * system.  Add it to the final
				 * package list.
				 */
				final_list->add_element(final_list,
				    pkg_name);
				comp_util->free(pkg);
			} else {
				/*
				 * The package is not installed on
				 * the system.  Do not add it to the
				 * list.
				 */
				pkgs_removed++;
			}
		}

		/*
		 * Create the new pkg list string.
		 */
		if (final_list->size(final_list) > 0) {
			String_util *sutil = _wsreg_strutil_initialize();
			final_list->reset_iterator(final_list);
			while (final_list->has_more_elements(final_list)) {
				char *pkg_name = (char *)
				    final_list->next_element(final_list);
				if (pkg_string == NULL) {
					/*
					 * The string has not yet been created.
					 */
					pkg_string = sutil->clone(pkg_name);
				} else {
					pkg_string = sutil->append(pkg_string,
					    " ");
					pkg_string = sutil->append(pkg_string,
					    pkg_name);
				}
			}
		}

		/*
		 * Set the new package string into the component's
		 * data.
		 */
		comp_util->set_data(comp, "pkgs", pkg_string);
		if (pkg_string != NULL) {
			free(pkg_string);
		}
	}
	return (pkgs_removed);
}

/*
 * Returns the number of elements in the specified NULL-
 * terminated array.
 */
static int
get_array_length(Revision **array)
{
	int length = 0;
	if (array != NULL) {
		while (array[length] != NULL)
			length++;
	}
	return (length);
}

/*
 * Child articles generally do not have a version.  All
 * components must have a version.  This function fixes
 * the child article version problem by assigning the
 * parent's version when the child has none.
 */
static void
fix_versions(Node *root, Revision **parent_revisions)
{
	if (root != NULL) {
		Article *a = NULL;
		Revision **revisions = NULL;
		Revision *revision_obj = _wsreg_revision_create();
		int index = 0;

		a = root->article;
		revisions = a->get_revisions(a);
		if (revisions == NULL || get_array_length(revisions) == 0) {
			if (parent_revisions != NULL &&
			    get_array_length(revisions) > 0) {
				/*
				 * Assign the parent's revisions to the child.
				 */
				index = 0;
				while (parent_revisions[index] != NULL) {
					a->add_revision(a,
					    parent_revisions[index]->clone(
						    parent_revisions[index]));
					index++;
				}
			} else {
				/*
				 * Parent revisions were not passed in.  This
				 * must be a parent with no revisions.
				 * prodreg version 2.0 allowed articles to be
				 * registered with no version.  This is not
				 * a good idea.  Each component must have a
				 * version assigned to it.  We will call
				 * this "1.0".
				 */
				Revision *r = _wsreg_revision_create();
				r->set_version(r, "1.0");
				a->add_revision(a, r);
			}
		}
		if (revisions != NULL) {
			revision_obj->free_array(revisions);
		}

		/*
		 * Recurse through the children to fix the versions.
		 */
		revisions = a->get_revisions(a);
		index = 0;
		while (root->children != NULL &&
		    root->children[index] != NULL) {
			fix_versions(root->children[index], revisions);
			index++;
		}

		revision_obj->free_array(revisions);
		revision_obj->free(revision_obj);
	}
}

/*
 * Child articles generally do not have an install
 * location.  All components must have an install
 * location.  This function fixes the child article
 * location problem by assigning the parent's
 * location when the child has none.
 */
static void
fix_locations(Node *root, char *parent_location)
{
	if (root != NULL) {
		Article *a = NULL;
		char *location = NULL;
		int index = 0;

		a = root->article;
		location = a->get_property(a, "installlocation");
		if (location == NULL) {
			if (parent_location != NULL) {
				/*
				 * Assign the parent's location to the child.
				 */
				a->set_property(a, "installlocation",
				    parent_location);
			} else {
				/*
				 * Parent location was not passed in.  This must
				 * be a parent with no location.  We will call
				 * it "/".  DON'T EVER LET THIS HAPPEN!
				 */
				a->set_property(a, "installlocation", "/");
			}
		}

		/*
		 * Recurse through the children to fix the locations.
		 */
		index = 0;
		while (root->children != NULL &&
		    root->children[index] != NULL) {
			fix_locations(root->children[index],
			    a->get_property(a, "installlocation"));
			index++;
		}
	}
}

/*
 * Registers the tree having the specified root node.  If
 * parent is specified, it will be registered as the parent
 * component of the components in the tree.
 *
 * If the prunePkgList is set to true, packages in the package
 * list but not installed on the system at registration time
 * will be removed from the package list.
 */
/*ARGSUSED*/
static int
register_tree(Conversion *c, Node *root, Article *parent, Boolean prunePkgList)
{
	int total = 0;
	if (root != NULL) {
		Node **children = NULL;
		Wsreg_component *component = NULL;
		Progress *progress = c->pdata->progress;

		/*
		 * Register the children first.
		 */
		children = root->children;
		component = NULL;

		if (children != NULL) {
			int i = 0;
			while (children[i] != NULL) {
				total += register_tree(c, children[i],
				    root->article, prunePkgList);
				i++;
			}
		}

		/*
		 * Convert and register this node.
		 */
		component = convert_to_component(root, prunePkgList);
		if (component != NULL) {
			root->component = component;
			wsreg_register(component);
			total++;
		}
		if (progress) {
			progress->increment(progress);
		}
	}
	return (total);
}

/*
 * Adds the specified child to the specified node.
 */
static void
node_add_child_node(Node *n, Node *child)
{
	if (n->children == NULL) {
		n->children = (Node**)wsreg_malloc(sizeof (Node *) * 2);
		memset(n->children, 0, sizeof (Node *) * 2);
		n->children[n->child_count++] = child;
	} else {
		/*
		 * Children have already been allocated.
		 */
		n->children = realloc(n->children,
		    sizeof (Node*) *
		    (n->child_count + 2));
		n->children[n->child_count++] = child;
		n->children[n->child_count] = NULL;
	}
}

/*
 * Adds the specified child article to the specified tree
 * node.
 */
static void
node_add_child(Node *n, Article *child)
{
	node_add_child_node(n, node_create(child));
}

/*
 * Frees the specified conversion object.  All articles added
 * to this conversion object are freed as a result of this call.
 */
static void
cvs_free(Conversion *c)
{
	Article *article = _wsreg_article_create();
	if (c->pdata->article_list != NULL) {
		c->pdata->article_list->free(
			c->pdata->article_list,
			    (Free)article->free);
		c->pdata->article_list = NULL;
	}
	free(c->pdata);
	free(c);
	article->free(article);
}

/*
 * Adds the specified article to the specified conversion
 * object.  The article will be freed with the conversion
 * object via the conversion->free method.
 */
static void
cvs_add_article(Conversion *c, Article *a)
{
	if (c->pdata->article_list == NULL) {
		c->pdata->article_list = _wsreg_list_create();
	}
	c->pdata->article_list->add_element(c->pdata->article_list, a);
}

/*
 * Returns true if the child article is a child of the specified
 * article; false otherwise.  This function is used during the
 * creation of the article tree that occurs before conversion
 * and registration.
 */
static Boolean
is_child_article(Article *a, Article *child)
{
	Boolean is_child = FALSE;
	char **child_names = a->get_child_mnemonics(a);
	char **child_ids = a->get_child_ids(a);
	String_util *sutil = _wsreg_strutil_initialize();

	if (child_names != NULL && child_ids != NULL) {
		char *child_mnemonic = child->get_mnemonic(child);
		char *child_id = child->get_id(child);
		int i = 0;
		while (child_names[i] != NULL) {
			if (sutil->equals_ignore_case(child_names[i],
			    child_mnemonic) &&
			    strcmp(child_ids[i], child_id) == 0) {
				is_child = TRUE;
			}
			free(child_names[i]);
			free(child_ids[i]);
			i++;
		}
		free(child_names);
		free(child_ids);
	}
	return (is_child);
}

/*
 * Adds the specified article to the specified article tree.  This
 * function returns true if the specified article was added to the
 * tree; false otherwise.  This function is used to create the
 * article tree.
 */
static Boolean
add_child_article_to_tree(Node *root, Article *a)
{
	if (root != NULL && a != NULL) {
		if (is_child_article(root->article, a)) {
			/*
			 * The new article is a child of the current root.
			 */
			node_add_child(root, a);
			return (TRUE);
		} else if (root->children != NULL) {
			int i = 0;
			while (root->children[i] != NULL) {
				if (add_child_article_to_tree(
					root->children[i], a)) {
					return (TRUE);
				}
				i++;
			}
		}
	}
	return (FALSE);
}

/*
 * Builds an article tree from the articles added to the specified
 * conversion object.
 */
static Node *
build_article_tree(Conversion *c)
{
	Node *root = NULL;
	if (c->pdata->article_list != NULL &&
	    c->pdata->article_list->size(c->pdata->article_list) > 0) {
		c->pdata->article_list->reset_iterator(c->pdata->article_list);
		while (c->pdata->article_list->has_more_elements(
			c->pdata->article_list)) {
			Boolean remove_from_list = FALSE;
			Article *a =
			    (Article *)c->pdata->article_list->next_element(
				    c->pdata->article_list);
			if (root == NULL) {
				remove_from_list = TRUE;
				root = node_create(a);
			} else {

				/*
				 * Find out if the article fits into
				 * the tree somewhere.
				 */
				if (is_child_article(a, root->article)) {
					/*
					 * The new article is the
					 * parent of the current root.
					 */
					Node *new_root = node_create(a);
					node_add_child_node(new_root, root);
					root = new_root;
					remove_from_list = TRUE;
				} else if (add_child_article_to_tree(root, a)) {
					remove_from_list = TRUE;
				}
			}
			if (remove_from_list) {
				c->pdata->article_list->remove(
					c->pdata->article_list,
				    a, NULL);
				c->pdata->article_list->reset_iterator(
					c->pdata->article_list);
			}
		}
	}
	return (root);
}

/*
 * Performs the registration and returns the number of articles
 * converted to Components and registered.  Articles must first
 * be added to the conversion object via the conversion->add_article
 * method.
 */
static int
cvs_register_components(Conversion *c, Wsreg_component *parent_component,
    Boolean prunePkgList)
{
	int count = 0;
	Article *parent_article = NULL;
	if (parent_component != NULL) {
		/*
		 * Create an Article that represents the parent.
		 */
		Article *article_obj = _wsreg_article_create();
		parent_article =
		    article_obj->from_component(parent_component);
		article_obj->free(article_obj);
	}
	while (c->pdata->article_list != NULL &&
	    c->pdata->article_list->size(c->pdata->article_list) > 0) {
		Node *root = build_article_tree(c);
		if (parent_article != NULL) {
			/*
			 * Reparent the root article with the
			 * specified component.
			 */
			Node *new_root = node_create(parent_article);
			node_add_child_node(new_root, root);
			root = new_root;
		}
		fix_versions(root, NULL);
		fix_locations(root, NULL);
		count += register_tree(c, root, parent_article, prunePkgList);
		node_free(root);
	}
	return (count);
}

/*
 * This function creates a mapping of Article mnemonics
 * to their respective Article objects.  This makes for
 * a very simple lookup mechanism used by the
 * create_associations method.
 *
 * This function always returns a valid Hashtable.
 */
static Hashtable *
cvs_create_article_lookup(List *article_list)
{
	Hashtable *articles = _wsreg_hashtable_create();
	String_util *sutil = _wsreg_strutil_initialize();
	if (article_list != NULL) {
		article_list->reset_iterator(article_list);
		while (article_list->has_more_elements(article_list)) {
			Article *a = (Article *)article_list->next_element(
				article_list);
			char *mnemonic = a->get_mnemonic(a);

			/*
			 * Convert the mnemonic to lower case so
			 * subsequent queries can be done on a
			 * normalized string.
			 */
			mnemonic = sutil->to_lower(mnemonic);
			articles->put(articles, mnemonic, a);
			free(mnemonic);
		}
	}
	return (articles);
}

/*
 * This method establishes parent/child relationships between the
 * articles in the specified list.  This method is used by the
 * prodreg legacy command line interface to connect associated
 * articles that are being registered together with the 'register'
 * prodreg subcommand.
 */
static void
cvs_create_associations(List *article_list)
{
	Hashtable *article_table =
	    cvs_create_article_lookup(article_list);
	article_list->reset_iterator(article_list);
	while (article_list->has_more_elements(article_list)) {
		Article *a = (Article *)
		    article_list->next_element(article_list);
		char *parent_mnemonic = NULL;
		char **child_mnemonics = NULL;
		char *articleids = NULL;
		String_util *sutil = _wsreg_strutil_initialize();

		/*
		 * Set the parent id.
		 */
		parent_mnemonic = a->get_property(a, "parent");
		if (parent_mnemonic != NULL) {
			char *normalized_mnemonic =
			    sutil->to_lower(parent_mnemonic);
			Article *parent =
			    (Article *)article_table->get(article_table,
				normalized_mnemonic);
			if (parent != NULL) {
				a->set_property(a, "parentid",
				    parent->get_id(parent));
			}
			free(normalized_mnemonic);
		}

		/*
		 * Set the child ids.
		 */
		child_mnemonics = a->get_child_mnemonics(a);
		if (child_mnemonics != NULL) {
			int index = 0;
			int count = 0;

			while (child_mnemonics[count] != NULL) {
				count++;
			}

			/*
			 * The size of the articleids string is
			 * count * 10 + 1.  That is, 9 characters for
			 * each child id and one character for a
			 * separator, and one more for the '\0'.
			 */
			articleids = (char *)
			    wsreg_malloc((sizeof (char) * count * 10) + 1);
			memset(articleids, 0,
			    (sizeof (char) * count * 10) + 1);
			while (child_mnemonics[index] != NULL) {
				char *normalized_mnemonic =
				    sutil->to_lower(
					    child_mnemonics[index]);
				Article *child =
				    (Article *)article_table->get(article_table,
					normalized_mnemonic);
				char *child_id = child->get_id(child);
				strcat(articleids, child_id);
				strcat(articleids, " ");
				free(normalized_mnemonic);
				index++;
			}
			a->set_property(a, "articleids", articleids);
		}
	}
	article_table->free(article_table, NULL);
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
 * Creates a conversion object that is capable of registering
 * one or more articles.  The articles must be added to the
 * conversion object through a subsequent call to
 * conversion->add_article().
 */
Conversion *
_wsreg_conversion_create(Progress *progress)
{
	Conversion *c = (Conversion*)wsreg_malloc(sizeof (Conversion));
	struct _Conversion_private *p = NULL;

	/*
	 * Load the method set.
	 */
	c->create = _wsreg_conversion_create;
	c->free = cvs_free;
	c->add_article = cvs_add_article;
	c->register_components = cvs_register_components;
	c->create_associations = cvs_create_associations;

	/*
	 * Initialize the private data.
	 */
	p = (struct _Conversion_private *)wsreg_malloc(
		sizeof (struct _Conversion_private));
	memset(p, 0, sizeof (struct _Conversion_private));
	p->progress = progress;
	c->pdata = p;
	return (c);
}
