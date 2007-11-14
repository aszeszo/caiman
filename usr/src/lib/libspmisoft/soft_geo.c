/*
 * CDDL HEADER START
 *
 * The contents of this file are subject to the terms of the
 * Common Development and Distribution License (the "License").
 * You may not use this file except in compliance with the License.
 *
 * You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 * or http://www.opensolaris.org/os/licensing.
 * See the License for the specific language governing permissions
 * and limitations under the License.
 *
 * When distributing Covered Code, include this CDDL HEADER in each
 * file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 * If applicable, add the following below this CDDL HEADER, with the
 * fields enclosed by brackets "[]" replaced with your own identifying
 * information: Portions Copyright [yyyy] [name of copyright owner]
 *
 * CDDL HEADER END
 */

/*
 * Copyright 2007 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */


#ifndef lint
#pragma ident	"@(#)soft_geo.c	1.6	07/11/09 SMI"
#endif

/*
 *	File:		soft_geo.c
 *
 *	Description:	This file contains the routines needed to handle
 *			geographical regions for locales.
 */

#include <stdio.h>
#include <ctype.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <libintl.h>

#include "spmisoft_lib.h"

static List *geo_code_name_map;

extern struct locmap *global_locmap;

/* Local functions */
static StringList *get_geos_from_locale(char *);
static Module *new_geo_module(char *, char *, char *);
static Module *add_geo_module(Module *, char *, char *);
static int add_to_geo_module(Module *, char *);
static void sort_geo(Geo *);

/*
 * Public functions
 */

/*
 * Name:	(swi_)get_all_geos
 * Description:	Return the list of geo modules associated with the current
 *		product.
 * Scope:	public
 * Arguments:	none
 * Returns:	NULL		- no geos associated with the current product
 *		Module *	- pointer to geo list
 */
Module *
swi_get_all_geos(void)
{
	Module *prod = get_current_product();

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_all_geos");
#endif

	return (prod->info.prod->p_geo);
}

/*
 * Name:	(swi_)valid_geo
 * Description:	Boolean function which checks the string 'geo' against all
 *		geographic regions known to this product and returns TRUE (1)
 *		if it is a valid (known) geographic region, and FALSE (0) if
 *		it is not.
 * Scope:	public
 * Arguments:	prodmod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		geo	- [RO] (char *)
 *			  non-NULL pointer to case specific geographic region
 *			  string
 * Returns:	1	- geographic region matched
 *		0	- geographic region match failed
 */
int
swi_valid_geo(Module *prodmod, char *geo)
{
	Module *mod;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("valid_geo");
#endif

	for (mod = prodmod->info.prod->p_geo; mod; mod = mod->next) {
		if (streq(mod->info.geo->g_geo, geo)) {
			return (1);
		}
	}

	return (0);
}

/*
 * Name:	(swi_)select_geo
 * Description:	Given a geographic region code, select that region and all of
 *		its component locales in the provided product.
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		geo	- [RO] (char *)
 *			  name of the geographic region to be SELECTED
 *
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_BADLOCALE	- 'geo' is not part of the geographic region
 *				  chain for 'mod'
 *		SUCCESS		- geographic region successfully selected
 */
int
swi_select_geo(Module *prod, char *geo)
{
	StringList	*str;
	Module		*mod;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_geo");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* Find the geographic region */
	for (mod = prod->info.prod->p_geo; mod; mod = mod->next) {
		if (streq(mod->info.geo->g_geo, geo)) {
			mod->info.geo->g_selected = SELECTED;

			/* Select constituent locales */
			for (str = mod->info.geo->g_locales; str;
			    str = str->next) {
				select_locale(prod, str->string_ptr, TRUE);
			}

			return (SUCCESS);
		}
	}

	return (ERR_BADLOCALE);
}

/*
 * Name:	(swi_)deselect_geo
 * Description:	Given a geographic region code, deselect the region and all of
 *		its component locales in the provided product.
 * Scope:	public
 * Arguments:	prod	- [RO] (Module *)
 *			  non-NULL pointer to a product module
 *		geo	- [RO] (char *)
 *			  name of the geographic region to be DESELECTED
 * Returns:	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or a NULLPRODUCT
 *		ERR_BADLOCALE	- 'geo' is not part of the geographic region
 *				  chain for 'mod'
 *		SUCCESS		- geographic region successfully deselected
 */
int
swi_deselect_geo(Module *prod, char *geo)
{
	StringList	*str;
	Module		*mod;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("deselect_geo");
#endif

	if (prod->type != PRODUCT && prod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	/* Find the geographic region */
	for (mod = prod->info.prod->p_geo; mod; mod = mod->next) {
		if (streq(mod->info.geo->g_geo, geo)) {
			mod->info.geo->g_selected = UNSELECTED;

			/* Deselect the constituent locales */
			for (str = mod->info.geo->g_locales; str;
			    str = str->next) {
				deselect_locale(prod, str->string_ptr);
			}

			return (SUCCESS);
		}
	}

	return (ERR_BADLOCALE);
}

/*
 * Name:	(swi_)generate_locgeo_lists
 * Description:	Generate lists of locales and geos.  The geo list is composed
 *		of all of the selected geos.  The locale list is composed of
 *		all selected locales that are not constituents of selected
 *		geos.
 * Scope:	public
 * Arguments:	locs	- [RO, *RW] (char ***)
 *			  A pointer to the location where the array of
 *			  selected locales that aren't constituents of
 *			  selected geos will be stored.  The last
 *			  element of the array will be followed by a
 *			  NULL element.  The array must be freed by
 *			  the caller.  If locs is NULL, the locale list
 *			  will not be returned.
 *		geos	- [RO, *RW] (char ***)
 *			  A pointer to the location where the array of
 *			  selected geos will be stored.  The last
 *			  element of the array will be followed by a
 *			  NULL element.  The array must be freed by the
 *			  caller.  If geos is NULL, the geo list will
 *			  not be returned.
 * Returns:	none
 */
void
swi_generate_locgeo_lists(char ***locs, char ***geos)
{
	StringList *cl;
	Module *prod, *mod;
	char **l = NULL;	/* locale codes */
	char **ln = NULL;	/* locale names */
	char **g = NULL;	/* geo codes */
	char **gn = NULL;	/* geo names */
	int nsl = 0;		/* Number of selected locales */
	int nsg = 0;		/* Number of selected geos */
	int nil = 0;		/* Number of sel'd locs not in sel'd geos */
	int i, j;

	prod = get_current_product();

	/* find all of the selected locales */
	for (nsl = 0, mod = prod->info.prod->p_locale; mod; mod = mod->next) {
		if (mod->info.locale->l_selected) {
			nsl++;
			l = (char **)xrealloc(l, sizeof (char *) * nsl);
			ln = (char **)xrealloc(ln, sizeof (char *) * nsl);
			l[nsl - 1] = mod->info.locale->l_locale;
			ln[nsl - 1] = mod->info.locale->l_language;
		}
	}
	nil = nsl;

	/* find all of the selected geos */
	for (nsg = 0, mod = prod->info.prod->p_geo; mod; mod = mod->next) {
		if (mod->info.geo->g_selected) {
			nsg++;
			g = (char **)xrealloc(g, sizeof (char *) * nsg);
			gn = (char **)xrealloc(gn, sizeof (char *) * nsg);
			g[nsg - 1] = mod->info.geo->g_geo;
			gn[nsg - 1] = mod->info.geo->g_name;

			/*
			 * Remove from l the names of all of the locales in this
			 * selected geo.  We only return (in locs) the names of
			 * selected locales that are not accounted for by
			 * selected geos.
			 */
			for (cl = mod->info.geo->g_locales; cl; cl = cl->next) {
				for (i = 0; i < nsl; i++) {
					if (l[i] &&
					    streq(cl->string_ptr, l[i])) {
						nil--;
						l[i] = NULL;
						break;
					}
				}
			}
		}
	}

	/*
	 * collapse the locale list in l into locs, removing any empty
	 * entries, and turning locale codes into locale names
	 */
	if (locs) {
		*locs = (char **)xmalloc(sizeof (char *) * (nil + 1));
		for (i = 0, j = 0; i < nsl; i++) {
			if (l[i]) {
				(*locs)[j++] = ln[i];
			}
		}
		(*locs)[nil] = NULL;
	}

	/*
	 * create the geos map, composed of the full names for the geo codes
	 * stored in g.
	 */
	if (geos) {
		*geos = (char **)xmalloc(sizeof (char *) * (nsg + 1));
		for (i = 0; i < nsg; i++) {
			(*geos)[i] = gn[i];
		}
		(*geos)[nsg] = NULL;
	}

	free(l);
	free(ln);
	free(g);
	free(gn);
}

/*
 * Name:	(swi)_geo_name_from_code
 * Description:	Given a geo code, return the name for the region in the current
 *		locale.
 * Scope:	private
 * Arguments:	geo	- [RO] (char *)
 *			  The geo code to look up
 * Return:	char *	- A pointer to a static buffer containing the name of
 *			  the region.
 */
char *
swi_geo_name_from_code(char *geo)
{
	static char	namebuf[BUFSIZ + 1];
	Node		*n;

	if (!geo_code_name_map) {
		/*
		 * The map hasn't been initialized.  This could mean that
		 * it doesn't exist on the image
		 */
		snprintf(namebuf, BUFSIZ, "No code/name map: %s", geo);
		return (namebuf);
	}

	if (!(n = findnode(geo_code_name_map, geo))) {
		snprintf(namebuf, BUFSIZ, "No name for code %s", geo);
		return (namebuf);
	}

	if (n->data == NULL) {
		snprintf(namebuf, BUFSIZ, "Blank name for code %s", geo);
		return (namebuf);
	}

	strcpy(namebuf, dgettext("SUNW_INSTALL_GEO", (char *)n->data));
	return (namebuf);
}

/*
 * Library-private functions
 */

/*
 * Name:	read_geo_map_file
 * Description:	Read a geo_map file, if possible.  Return a pointer to a
 *		StringList containing the list of geos listed in the file.
 *		This routine is considered to have failed either if there
 *		is no geo_map file, or if there are no geos in said file.
 * Scope:	semi-private (internal library use only)
 * Arguments:	localedir	- [RO] (char *)
 *				  The location of the locale directory from
 *				  which the map file is to be read.
 *		locale		- [RO] (char *)
 *				  The locale whose geo_map is to be read.
 * Returns:	StringList 	- A list of the geos in the geo_map
 *		NULL		- No geo_map found, or no geos in geo_map
 */
StringList *
read_geo_map_file(char *localedir, char *locale)
{
	char		path[MAXPATHLEN + 1];
	char		buf[BUFSIZ + 1];
	struct stat	statbuf;
	FILE		*fp;

	if (snprintf(path, sizeof (path), "%s/%s/geo_map",
				localedir, locale) >= sizeof (path)) {
		return (NULL);
	}
	if (stat(path, &statbuf) || !S_ISREG(statbuf.st_mode) ||
	    (fp = fopen(path, "r")) == NULL) {
		return (NULL);
	}

	while (fgets(buf, BUFSIZ, fp) != NULL) {
		if (strncmp(buf, "LC_GEO=", 7) != 0) {
			continue;
		}

		/* Remove the trailing newline */
		if (buf[strlen(buf) - 1] == '\n')
			buf[strlen(buf) - 1] = '\0';

		fclose(fp);
		return (StringListBuild(buf + 7, ','));
	}

	/* No LC_GEO line found */
	fclose(fp);
	return (NULL);
}

/*
 * Name:	read_geo_code_name_map
 * Description:	Read a geo code-to-name translation file, and store the mapping
 *		in geo_code_name_map for later use.
 * Scope:	semi-private (internal library use only)
 * Arguments:	localedir	- [RO] (char *)
 *				  The locale directory containing the
 *				  translation file
 * Returns:	none
 */
void
read_geo_code_name_map(char *localedir)
{
	struct stat	statbuf;
	char		path[MAXPATHLEN + 1];
	char		buf[BUFSIZ + 1];
	char		*c;
	FILE		*fp;
	Node		*n;

	geo_code_name_map = getlist();

	if (snprintf(path, sizeof (path), "%s/geo", localedir) >= sizeof (path))
		return;

	if (stat(path, &statbuf) || !S_ISREG(statbuf.st_mode) ||
	    (fp = fopen(path, "r")) == NULL) {
		return;
	}

	buf[0] = '\0';
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		if (buf[strlen(buf) - 1] == '\n')
			buf[strlen(buf) - 1] = '\0';

		/* Find the end of the code */
		for (c = buf; *c && !isspace(*c); c++);

		if (!*c)
			/* Code but no name - invalid line */
			continue;

		*c = '\0';

		/* Find the start of the translation */
		for (c += 1; isspace(*c); c++);

		if (!*c)
			/* Code then ws then eol - invalid line */
			continue;

		n = getnode();
		n->key = xstrdup(buf);
		n->data = xstrdup(c);
		n->delproc = NULL;

		addnode(geo_code_name_map, n);
	}

	fclose(fp);
}

/*
 * Name:	add_geo
 * Description:	Add all of the geographical regions represented by a locale to
 *		the product.
 * Scope:	semi-private (internal library use only)
 * Arguments:	prod	- [RO] (Module *)
 *			  The product to which the geos will be added
 *		locale	- [RO] (char *)
 *			  The locale whose geos will be added
 * Returns:	SUCCESS		- the geos for this locale are in the product
 *		ERR_INVALID	- the locale specified doesn't have any geos
 */
int
add_geo(Module *prod, char *locale)
{
	Module		*prodgeo;
	StringList	*locgeos, *locgeo;

	if (!(locgeos = get_geos_from_locale(locale))) {
		return (ERR_INVALID);
	}

	for (locgeo = locgeos; locgeo; locgeo = locgeo->next) {
		for (prodgeo = prod->info.prod->p_geo; prodgeo;
		    prodgeo = prodgeo->next) {
			if (streq(locgeo->string_ptr,
			    prodgeo->info.geo->g_geo)) {
				/*
				 * The Geo already exists in the product, so add
				 * our locale to it
				 */
				add_to_geo_module(prodgeo, locale);
				break;
			}
		}

		if (!prodgeo) {
			/* locgeo isn't in the product geo list */
			prod->info.prod->p_geo = add_geo_module(
			    prod->info.prod->p_geo, locgeo->string_ptr, locale);
		}
	}

	return (SUCCESS);
}

/*
 * Name:	add_installed_geos
 * Description:	Given a comma-separated list of installed geos, add those geos
 *		to the product.
 * Scope:	semi-private (internal library use only)
 * Arguments:	prod	- [RO] (Module *)
 *			  The product to which the geos will be added
 *		geolist	- [RO] (char *)
 *			  comma-delimited list of installed locales
 * Returns:	SUCCESS		- All geos were successfully added
 *		ERR_BADLOCALE	- The geos string was invalid
 */
int
add_installed_geos(Module *prod, char *geolist)
{
	char *geos, *geo;
	struct locmap *lm;
	StringList *lmgeo, *loclist;

	/* Validate parameters */
	if (prod == NULL ||
	    (prod->type != PRODUCT && prod->type != NULLPRODUCT)) {
		return (ERR_INVALIDTYPE);
	}

	if (geolist == NULL) {
		return (ERR_BADLOCALE);
	}

	/* Make a local copy of the geo list so we can use strtok */
	geos = xstrdup(geolist);

	for (geo = strtok(geos, ","); geo; geo = strtok(NULL, ",")) {
		prod->info.prod->p_geo = add_geo_module(prod->info.prod->p_geo,
							geo, NULL);
		prod->info.prod->p_geo->info.geo->g_selected = SELECTED;

		/* add the locales comprising the geo */
		for (lm = global_locmap; lm; lm = lm->next) {
			for (lmgeo = lm->locmap_geo; lmgeo;
			    lmgeo = lmgeo->next) {
				if (streq(lmgeo->string_ptr, geo)) {
					loclist = NULL;
					StringListAdd(&loclist,
					    lmgeo->string_ptr);
					add_locale_list(prod, loclist);
					StringListFree(loclist);
				}
			}
		}
	}

	return (SUCCESS);
}

/*
 * Name:	sort_geos
 * Description:	Given a list of geos, sort the locales in each of those geos.
 * Scope:	semi-private (internal library use only)
 * Arguments:	prod	- [RO, *RO] (Module *)
 *			  The list of geos whose locales are to be sorted.
 * Returns:	none
 */
void
sort_geos(Module *prod)
{
	Module *g;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("sort_geos");
#endif

	if (prod->info.prod->p_geo == NULL)
		return;

	for (g = prod->info.prod->p_geo; g; g = g->next) {
		sort_geo(g->info.geo);
	}
}

/*
 * Private functions
 */

/*
 * Name:	get_geos_from_locale
 * Description:	Retrieve the list of geos associated with the language
 *		represented by a given locale.
 * Scope:	private
 * Arguments:	locale	- [RO] (char *)
 *			  The language to search for
 * Returns:	StringList	- The list of geos
 *		NULL		- No geos found for this locale
 */
static StringList *
get_geos_from_locale(char *locale)
{
	LocMap *lmap;

	for (lmap = global_locmap; lmap; lmap = lmap->next) {
		if (streq(lmap->locmap_partial, locale)) {
			return (lmap->locmap_geo);
		}
	}

	return (NULL);
}

/*
 * Name:	new_geo_module
 * Description:	Creates a new geo module with a given locale name for that
 *		region.
 * Scope:	private
 * Arguments:	geo	- The geographic region code
 *		name	- The English name for the geographic region
 *		locale	- A locale for the geographic region (optional)
 * Returns:	Module *	- The new geo module
 */
static Module *
new_geo_module(char *geo, char *name, char *locale)
{
	Module *m;

	m = (Module *)xcalloc(sizeof (Module));
	m->type = GEO;

	m->info.geo = (Geo *)xcalloc(sizeof (Geo));
	m->info.geo->g_geo = xstrdup(geo);
	m->info.geo->g_name = xstrdup(name);
	if (locale) {
		StringListAdd(&m->info.geo->g_locales, locale);
	}

	return (m);
}

/*
 * Name:	add_geo_module
 * Description:	Create a new geo module, populate it, and add it to the front of
 *		the current list.
 * Scope:	private
 * Arguments:	list	- The current geo list
 *		geo	- The geo code
 *		locale	- The inital locale to add to the geo
 * Returns:	Module *	- The new head of the geo list
 */
static Module *
add_geo_module(Module *list, char *geo, char *locale)
{
	Module *m;

	m = new_geo_module(geo, geo_name_from_code(geo), locale);

	m->next = list;
	if (list)
		list->prev = m;

	return (m);
}

/*
 * Name:	add_to_geo_module
 * Description:	Add a locale to a geographic region (geo) module if it hasn't
 *		already been added.
 * Scope:	private
 * Arguments:	geo	- [RO] (Module *)
 *			  The geo module to which the locale is to be added
 *		locale	- [RO] (char *)
 *			  The locale to add
 * Returns:	SUCCESS		- Operation succeeded
 *		ERR_INVALID	- Invalid arguments
 */
static int
add_to_geo_module(Module *geo, char *locale)
{
	/* verify parameters */
	if (geo == NULL || locale == NULL || geo->type != GEO)
		return (ERR_INVALID);

	if (StringListAddNoDup(&geo->info.geo->g_locales, locale) == SUCCESS)
		return (SUCCESS);

	return (ERR_INVALID);
}

/*
 * Name:	sort_geo
 * Description:	Sort the list of locales that make up a geo.  The list is
 *		sorted according alphabetically according to the locale
 *		description.
 * Scope:	private
 * Arguments:	g	- [RO, *RW] (Geo *)
 *			  The Geo whose constituent locales are to be sorted.
 * Returns:	none
 */
static void
sort_geo(Geo *g)
{
	StringList *new, *l, *ol, *cur, *ocur;
	char *curdesc, *desc;

	if (g->g_locales == NULL)
		return;

	new = NULL;
	while (g->g_locales) {
		/* Look for locale description highest in the sorting order */
		cur = NULL;
		for (l = g->g_locales, ol = NULL; l; ol = l, l = l->next) {
			if (!cur) {
				cur = l;
				ocur = ol;
				curdesc = get_lang_from_locale(cur->string_ptr);
			} else {
				desc = get_lang_from_locale(l->string_ptr);

				if (strcoll(desc, curdesc) > 0) {
					cur = l;
					ocur = ol;
					curdesc = desc;
				}
			}
		}

		/* Remove cur from g_locales */
		if (ocur) {
			ocur->next = cur->next;
		} else {
			g->g_locales = cur->next;
		}

		/* Add cur to beginning of new */
		cur->next = new;
		new = cur;
	}

	/* new now contains the sorted list */
	g->g_locales = new;
}
