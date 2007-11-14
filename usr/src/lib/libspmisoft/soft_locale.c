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

#pragma ident	"@(#)soft_locale.c	1.19	07/11/09 SMI"

#include <string.h>
#include <locale.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>
#include <unistd.h>

#include "spmisoft_lib.h"
#include "soft_locale.h"

/* Local Globals */

struct locmap	*global_locmap = NULL;	/* List of localization maps */

/* Local Statics and Constants */

static struct loclang {
	char	   *locale;
	char	   *language;
};

typedef struct locale_list {
	char	*locale_id;
	int	n_locales;
	char	**list;
	char	**descriptions;
	struct	locale_list	*next;
} LocaleList;

/* Static Globals */
static LocaleList *llist = NULL;

/* Public Function Prototype */

Module		*swi_get_all_locales(void);
int		swi_select_locale(Module *, char *, int);
int		swi_deselect_locale(Module *, char *);
int		swi_valid_locale(Module *, char *);
int		swi_locale_list_selected(StringList **);
char		*swi_get_default_system_locale();
int		swi_set_default_system_locale(char *);
char		*swi_get_system_locale();
char		*swi_get_locale_geo();
int		swi_save_locale(char *, char *);
int		swi_get_sys_locale_list(char *, char ***);
void		swi_build_locale_list(void);
char		*swi_get_init_default_system_locale(void);
char		*swi_get_composite_locale(char *);

/* Library Function Prototype */

void		sync_l10n(Module *);
void		localize_packages(Module *);
void		sort_locales(Module *);
char		*get_lang_from_loc_array(char *);
char		*get_lang_from_locale(char *);
char		*get_C_lang_from_locale(char *);
int		add_locale_list(Module *, StringList *);
int		add_subset_locale_list(Module *, StringList *);

/* Local Function Prototype */

static int	resolve_package_l10n(Node *, caddr_t);
static int	select_single_locale(Module *, char *);
static int	select_decomp_locale(Module *, char *);
static int	select_base_locale(Module *, char *);
static int	add_locale(Module *, char *);
static int	empty_locale_list(Module *);
static void	subset_locale_list(Module *, StringList *);
static int	valid_product_locale(Module *, char *);
static char	*translate_locale(const char *);
static int	create_locale_list_entry(char *);
static void	add_to_list(char ***, char ***, int, char *);
static void	free_locale_list(void);
static int	add_installed_locales(Module *, char *);

/*
 * Order these so the known used ones are first.
 */
static struct loclang loc_array[] = {
	{"C", "Default Locale"},
	{"ca", "Catalan"},
	{"de", "German"},
	{"en", "English"},
	{"es", "Spanish"},
	{"fr", "French"},
	{"it", "Italian"},
	{"ja", "Japanese"},
	{"ko", "Korean"},
	{"sv", "Swedish"},
	{"zh", "Chinese"},
	{"zh_TW", "Chinese/Taiwan"},
	{"ar", "Arabic"},
	{"bg", "Bulgarian"},
	{"co", "Corsican"},
	{"cs", "Czech"},
	{"cy", "Welsh"},
	{"da", "Danish"},
	{"de_CH", "Swiss German"},
	{"el", "Greek"},
	{"en_UK", "English/UK"},
	{"en_US", "English/USA"},
	{"eo", "Esperanto"},
	{"eu", "Basque"},
	{"fa", "Persian"},
	{"fi", "Finnish"},
	{"fr_BE", "French/Belgium"},
	{"fr_CA", "Canadian French"},
	{"fr_CH", "Swiss French"},
	{"fy", "Frisian"},
	{"ga", "Irish"},
	{"gd", "Scots Gaelic"},
	{"hu", "Hungarian"},
	{"is", "Icelandic"},
	{"iw", "Hebrew"},
	{"ji", "Yiddish"},
	{"kl", "Greenlandic"},
	{"lv", "Latvian"},
	{"nl", "Dutch"},
	{"no", "Norwegian"},
	{"pl", "Polish"},
	{"pt", "Portuguese"},
	{"ro", "Romanian"},
	{"ru", "Russian"},
	{"sh", "Serbo-Croatian"},
	{"sk", "Slovak"},
	{"sr", "Serbian"},
	{"tr", "Turkish"}
};

/*
 * this just gets the strings into the .po file for
 * translation.  I do a get text later when actually displaying
 * the string...
 */
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Default Locale")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Arabic")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Bulgarian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Catalan")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Corsican")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Czech")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Welsh")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Danish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "German")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Swiss German")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Greek")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "English")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "English/UK")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "English/USA")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Esperanto")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Spanish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Basque")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Persian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Finnish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "French")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "French/Belgium")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Canadian French")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Swiss French")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Frisian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Irish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Scots Gaelic")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Hungarian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Icelandic")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Italian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Hebrew")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Japanese")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Yiddish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Greenlandic")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Korean")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Latvian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Dutch")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Norwegian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Polish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Portuguese")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Romanian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Russian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Serbo-Croatian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Slovak")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Serbian")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Swedish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Turkish")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Chinese")
#undef DUMMY
#define	DUMMY dgettext("SUNW_INSTALL_SWLIB", "Chinese/Taiwan")
#undef DUMMY

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * get_all_locales()
 *	Return the list of locale modules assocated with the current
 *	product.
 * Parameters:
 *	none
 * Return:
 *	NULL	 - no locales associated with the current product
 *	Module * - pointer to locale list
 * Status:
 *	public
 */
Module *
swi_get_all_locales(void)
{
	Module	*prod = get_current_product();
#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_all_locales");
#endif

	return (prod->info.prod->p_locale);
}

/*
 * deselect_locale()
 *	If the product has a locale structure of the specified type,
 *	set the status of the locale structure to UNSELECTED.
 * Parameters:
 *	mod	- pointer to product module
 *	locale	- specifies name of locale to be deselected
 * Return:
 *	ERR_INVALIDTYPE	- 'mod' is neither PRODUCT or NULLPRODUCT
 *	ERR_BADLOCALE	- invalid locale parameter specified for this
 *			  product
 *	SUCCESS		- locale structure of type 'locale' cleared
 *			  successfully
 * Status:
 *	public
 */
int
swi_deselect_locale(Module *mod, char *locale)
{
	Module *m;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("deselect_locale");
#endif

	if (mod->type != PRODUCT && mod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	for (m = mod->info.prod->p_locale; m != NULL; m = m->next) {
		if (strcmp(locale, m->info.locale->l_locale) == 0) {
			m->info.locale->l_selected = UNSELECTED;
			sync_l10n(mod);
			return (SUCCESS);
		}
	}

	return (ERR_BADLOCALE);
}

/*
 * valid_locale()
 *	Boolean function which checks the string 'locale'
 *	against all known locales and returns TRUE (1) if
 *	it is a valid (known) locale, and FALSE (0) if it
 *	is not.
 * Parameters:
 *	locale	- non-NULL pointer to case specific locale
 *		  string
 * Return:
 *	1	- locale matched
 *	0	- locale match failed
 */
int
swi_valid_locale(Module *prodmod, char *locale)
{
	if (get_C_lang_from_locale(locale) == NULL)
		return (0);
	else
		return (1);
}

/*
 * locale_list_selected()
 *      Boolean function which checks if any locale from list
 *      is currently selected to be installed.
 * Parameters:
 *      list   - non-NULL pointer to a StringList pointer.
 * Return:
 *      1      - a locale from list is selected.
 *      0      - no locales in list are selected.
 */
int
swi_locale_list_selected(StringList **list)
{
	Module *m;
	StringList **s;

	for (s = list; *s; s = &((*s)->next)) {
		if (streq((*s)->string_ptr, "C"))
			return (TRUE);
		else {
			for (m = get_all_locales(); m; m = m->next) {
				if (m->info.locale->l_selected &&
					streq(m->info.locale->l_locale,
						(*s)->string_ptr)) {
					return (TRUE);
				}
			}
		}
	}

	return (FALSE);
}

/*
 * select_locale()
 *	Break up a (possibly composite) locale string into individual
 *	locales and select each of them.
 *
 *	A composite locale looks like:
 *		/fr/fr/fr/fr/fr/C
 * Parameters:
 *	mod	- product module pointer (must be type PRODUCT or NULLPRODUCT)
 *	locale	- name of locale to be SELECTED
 *	decomp	- whether or not decompositions of the locale name are to be
 *		  tried if the passed name doesn't exist.  Must be TRUE or
 *		  FALSE.
 * Return:
 *	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or NULLPRODUCT
 *	ERR_BADLOCALE	- 'locale' is not part of the locale chain for 'mod'
 *	SUCCESS		- locale structure of type 'locale' set successfully
 * Status:
 *	public
 */
int
swi_select_locale(Module *mod, char *locale, int decomp)
{
	int	ret, final_code;
	char	*cp;
	char	locstring[80];

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_locale");
#endif

	if (mod->type != PRODUCT && mod->type != NULLPRODUCT)
		return (ERR_INVALIDTYPE);

	final_code = SUCCESS;

	if (locale[0] == '/') {		/* it's a composite locale */
		while (locale && *locale) {
			locale++;	/* skip over '/' */
			if ((cp = strchr(locale, '/')) != NULL) {
				(void) strncpy(locstring, locale, cp - locale);
				locstring[cp - locale] = '\0';
			} else
				(void) strcpy(locstring, locale);
			if (strlen(locstring) != 0) {
				if (decomp) {
					ret = select_decomp_locale(mod,
								locstring);
				} else {
					ret = select_single_locale(mod,
								locstring);
				}
				if (ret != SUCCESS)
					final_code = ret;
			}
			locale = cp;
		}
	} else {
		if (decomp) {
			final_code = select_decomp_locale(mod, locale);
		} else {
			final_code = select_single_locale(mod, locale);
		}
	}

	return (final_code);
}

/*
 * swi_get_init_default_system_locale()
 *      Function that returns the initial value to be used as the
 *      default system locale.  This initial value is set by
 *      sysidtool which is run before the installer is run.  Since
 *      we now only support the 10 Big Rule languages during install
 *      time, we need to store the original value specified in a
 *      sysidcfg file so that the installer can get at it.
 *
 *      For example, lets say in a sysidcfg file, the system_locale is
 *      specified as "it_IT.UTF=8".  Since we only support languages
 *      during install, we translate this locale to "it" and set this
 *      value in the environment during install (it also gets set in
 *      the /etc/default/init file during install).
 *      Now when we get to the Geo panel and the Default System Locale
 *      panel in the installer, "it_IT.UTF-8" should be selected by
 *      default, but the environment has "it".  The installer needs
 *      to get at the original value specified in the sysidcfg file
 *      somehow, and this is the method we use to get at the value.
 *
 *      NOTE: This is ugly, and we should really have a mechanism to
 *      pass any general information from sysidtool to the installer,
 *      but since this is the only thing we need to pass right now,
 *      we'll chug along with it.
 *
 * Parameters:
 *      none
 * Return:
 *      char * - (static storage) pointer to locale name.
 */
char *
swi_get_init_default_system_locale()
{
	static boolean_t	answered = B_FALSE;
	static char		*idsl = NULL;

	if (!answered) {
		idsl = (char *)readInText(TMP_INITDEFSYSLOC);

		answered = B_TRUE;
	}

	if (idsl != NULL)
		return (idsl);

	return (get_system_locale());
}

/*
 * get_default_system_locale()
 *      Function that returns the default system locale that will
 *	be used when the system reboots after install is complete.
 * Parameters:
 *      none
 * Return:
 *      char * - (static storage) pointer to locale name.
 */
char *
swi_get_default_system_locale()
{
	char *dsl = NULL;

	dsl = (char *)readInText(TMP_DEFSYSLOC);

	if (dsl != NULL)
		return (dsl);

	return (get_system_locale());
}

/*
 * set_default_system_locale()
 *      Function to set the default system locale that will
 *      be used when the system reboots.
 * Parameters:
 *      locale   - non-NULL pointer to a valid locale.
 * Return:
 *      1      - selected system locale set successfully.
 *      0      - could not set the selected system locale.
 */
int
swi_set_default_system_locale(char *locale)
{
	if (locale == NULL)
		return (FAILURE);

	return (writeOutText(TMP_DEFSYSLOC, "w", locale));
}

/*
 * get_system_locale()
 *      Function that returns the system locale that is
 *	currently set on the system in /etc/default/init (i.e. locale
 *	that is currently set in the miniroot.)
 * Parameters:
 *      none
 * Return:
 *      char * - pointer to locale name.
 */
char *
swi_get_system_locale(void)
{
	char *locale = NULL;

	if ((locale = (char *)get_system_locale_from_file()) != NULL)
		return (locale);

	return (get_default_locale());
}

/*
 * get_locale_geo
 *	Function to get the geo region that this locale belongs to.
 *	The string returned will be in the language of the current locale.
 * Paraemters:
 *	locale		- non-NULL pointer to the locale name.
 * Returns:
 *	char *		- (static storage) pointer to geo region string.
 */
char *
swi_get_locale_geo(char *locale)
{
	LocMap *lmap;
	char *geo;

	if ((lmap = global_locmap) != NULL) {
		while (lmap) {
			if (strcmp(lmap->locmap_partial, locale) == 0) {
				if (lmap->locmap_geo) {
					/*
					 * return the first geo in the list.
					 * a real locale will only have one
					 * geo anyway
					 */
					geo = geo_name_from_code(
						lmap->locmap_geo->string_ptr);
					if (geo)
						return (geo);
					else
						break;
				} else {
					break;
				}
			}
			lmap = lmap->next;
		}
	}

	return (NULL);
}

/*
 * get_sys_locale_list
 *	Function that returns the list of all locales (including
 *	derivative locales), given that base locale_id.  For example,
 *	the base locale_id "en_US" would yield the list with
 *	"en_US.ISO8859-1" and "en_US.ISO8859-15".
 * Paremeters:
 *	lcoale_id	- non-NULL pointer to base locale name.
 *	localep		- non-NULL pointer to string array.
 * Returns:
 *	int		- number of locales returned in localep.
 */
int
swi_get_sys_locale_list(char *locale_id, char ***localep)
{
	LocaleList *ll;

	for (ll = llist; ll; ll = ll->next) {
		if (streq(locale_id, ll->locale_id)) {
			*localep = ll->list;
			return (ll->n_locales);
		}
	}

	return (0);
}

/*
 * build_locale_list
 *	Function to build the internal locale list of all locales
 *	installable on the system.  Each locale list entry consists
 *	of the base locale id name and the list of all derivative locales
 *	which that locale id includes (which may include itself).
 * Parameters:
 *	none
 * Returns:
 *	none
 */
void
swi_build_locale_list()
{
	Module *m;

	if (llist != NULL)
		free_locale_list();

	for (m = get_all_locales(); m; m = m->next) {
		create_locale_list_entry(m->info.locale->l_locale);
	}
}

/*
 * save_locale()
 *      Function to set the default system locale in the
 *      etc/default/init file.
 * Parameters:
 *      locale   - non-NULL pointer to a valid locale.
 *      target   - pointer to target file to update.  If NULL,
 *                 function will update /etc/default/init.
 * Return:
 *      SUCCESS  - selected system locale set successfully.
 *      FAILURE  - could not set the selected system locale.
 */
int
swi_save_locale(char *locale, char *target)
{
	FILE *fp, *tfp;
	char line[BUFSIZ], orig_line[BUFSIZ], tfile[MAXPATHLEN];
	char *translated_locale = NULL;
	int fd;
	struct stat buf;

	/* Make sure the locale has been translated */
	translated_locale = translate_locale(locale);

	if (translated_locale == NULL)
		return (FAILURE);

	/* Generate a temporary file */
	(void) snprintf(tfile, sizeof (tfile), "/tmp/initXXXXXX");

	if ((fd = mkstemp(tfile)) == -1)
		return (FAILURE);

	if (fstat(fd, &buf) == -1)
		return (FAILURE);

	if (!S_ISREG(buf.st_mode))
		return (FAILURE);

	if ((tfp = fdopen(fd, "w")) == NULL)
		return (FAILURE);

	if (!target) {
		target = INIT_FILE;
	}

	/* Strip the current LANG and LC_* entries */
	if ((fp = fopen(target, "r")) != NULL) {
		while (fgets(line, BUFSIZ, fp) != NULL) {

			(void) strcpy(orig_line, line);
			trim(line);

			if (strlen(line) <= 0)
				continue;

			if (strneq("LANG=", line, 5))
				continue;
			if (strneq("LC_", line, 3))
				continue;

			if (fputs(orig_line, tfp) == EOF) {
				(void) fclose(fp);
				(void) fclose(tfp);
				return (FAILURE);
			}
		}
	}

	(void) fclose(fp);

	update_init(tfp, translated_locale);

	(void) fclose(tfp);

	if ((fp = fopen(target, "w")) == NULL)
		return (FAILURE);

	if ((tfp = fopen(tfile, "r")) == NULL) {
		(void) fclose(fp);
		return (FAILURE);
	}

	while (fgets(line, BUFSIZ, tfp) != NULL)
		if (fputs(line, fp) == EOF)
			break;

	(void) fclose(fp);
	(void) fclose(tfp);

	(void) unlink(tfile);

	return (SUCCESS);
}

/*
 * Name:	swi_get_composite_locale
 * Description: Forms the composite locale listing (seperated by '/'s)
 *		of all locales used by locale.
 *		e.g.  the locale es_ES.ISO8859-15 will have the following
 *		string returned: "/es_ES.ISO8859-15/es_ES.ISO8859-1/es/ \
 *			es_ES.ISO8859-15/es_ES.ISO8859-15/es_ES.ISO8859-15"
 * Scope:	public
 * Arguments:	locale - locale to lookup
 * Returns:	composite locale - char pointer to the composite locale.
 */
char *
swi_get_composite_locale(char *locale)
{
	char		locstr[7][MAX_LOCALE];
	char		path[MAXPATHLEN];
	char		composite_locale[(MAX_LOCALE * 7) + 7];
	FILE		*fp;
	int		i;

	if (locale == NULL)
		return (NULL);

	/* now try to read a locale_map file */
	(void) snprintf(path, sizeof (path), "%s/%s/%s", NLSPATH,
		locale, LOCALE_MAP_FILE);

	if ((fp = fopen(path, "r")) == NULL) {
		return (NULL);
	}

	/* initialize arrays */
	composite_locale[0] = '\0';
	for (i = 0; i < 7; i++)
		locstr[i][0] = '\0';

	(void) read_locale_file(fp, locstr[0], locstr[1], locstr[2],
		    locstr[3], locstr[4], locstr[5], locstr[6]);

	(void) fclose(fp);

	for (i = 0; i < 7; i++) {
		if (locstr[i][0] != '\0') {
			(void) strlcat(composite_locale, "/",
			    sizeof (composite_locale));
			(void) strlcat(composite_locale, locstr[i],
			    sizeof (composite_locale));
		}
	}

	return (composite_locale);
}

/* ******************************************************************** */
/*			LIBRARY SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * load_installed_locales()
 *	Read the list of installed locales and geographic regions from the
 *	installed system.
 * Parameters:
 *	prod	- pointer to product module
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
load_installed_locales(Module *prod)
{
	struct stat	statbuf;
	char		path[MAXPATHLEN + 1];
	char		buf[BUFSIZ + 1];
	FILE		*fp;

	/* Validate parameters */
	if (prod == NULL ||
	    (prod->type != PRODUCT && prod->type != NULLPRODUCT)) {
		return;
	}

	if (prod->info.prod->p_rootdir == NULL) {
		return;
	}

	(void) snprintf(path, sizeof (path), "%s%s", get_rootdir(),
	    LOCALES_INSTALLED);

	if (stat(path, &statbuf) || !S_ISREG(statbuf.st_mode) ||
	    (fp = fopen(path, "r")) == NULL) {
		/*
		 * Stat failed, if this a non-global zone, try opening
		 * the file descriptor for the locales_installed file
		 * from the global zone before quitting.
		 */
		if ((fp = get_fp_from_zone_fd(ZONE_FD_LOCALES_INSTALLED)) ==
		    NULL) {
			return;
		}
	}

	/*
	 * Read and process the LOCALES and GEOS lines from the
	 * locales_installed file.  Ignore all other lines.
	 */
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';

		if (strneq(buf, "LOCALES=", 8)) {
			add_installed_locales(prod, buf + 8);
		} else if (strneq(buf, "GEOS=", 5)) {
			add_installed_geos(prod, buf + 5);
		}
	}

	(void) fclose(fp);
}

/*
 * add_installed_locales()
 *	Given a comma-delimited list of installed locales, select those locales
 *	in the product.
 * Parameters:
 *	prod	- pointer to product module
 *	locales	- comma-delimited list of installed locales
 * Return:
 *	SUCCESS		- All locales were successfully selected
 *	ERR_INVALIDTYPE	- 'prod' is neither a PRODUCT or a NULLPRODUCT
 *	ERR_BADLOCALE	- the 'locales' string was invalid
 */
static int
add_installed_locales(Module *prod, char *locales)
{
	char *locs, *loc;

	/* Validate parameters */
	if (prod == NULL ||
	    (prod->type != PRODUCT && prod->type != NULLPRODUCT)) {
		return (ERR_INVALIDTYPE);
	}

	if (locales == NULL) {
		return (ERR_BADLOCALE);
	}

	/* Make a local copy of locales so we can use strtok */
	locs = xstrdup(locales);

	for (loc = strtok(locs, ","); loc; loc = strtok(NULL, ",")) {
		(void) add_locale(prod, loc);
	}

	free(locs);

	return (SUCCESS);
}

/*
 * sync_l10n()
 *	Mark the localization packages as selected or unselected base of the
 *	locale status of the associated product 'prod', and the status of each
 *	package in the product (i.e.  SELECTED or REQUIRED). If 'prod' is NULL,
 *	the current product is used.  This function must be called each time
 *	the status of one (or more) locales changes.
 * Parameters:
 *	prod	- pointer to product module
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
sync_l10n(Module * prod)
{
	Arch		*ap;
	Media		*med;
	Module		*mod, *ml, *mp;
	PkgsLocalized 	*pkgloc;
	Product		*instprod;
	Modinfo		*mi;
	Arch_match_type	match;
	int		selectable;
	int		ret;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("sync_l10n");
#endif

	if (prod == NULL)
		return;

	if (prod->parent == NULL)
		return;

	med = prod->parent->info.media;

	/* Look for a product (if any) being upgraded */
	instprod = NULL;
	for (mod = get_media_head(); mod != NULL; mod = mod->next)  {
		if (mod->info.media->med_type == INSTALLED &&
		    mod->info.media->med_flags & BASIS_OF_UPGRADE &&
		    mod->sub) {
			instprod = mod->sub->info.prod;
			break;
		}
	}

	/* Deselect all L10n packages for unselected locales */
	for (ml = prod->info.prod->p_locale; ml; ml = ml->next) {
		if (ml->info.locale->l_selected)
			continue;

		for (mp = ml->sub; mp; mp = mp->next) {
			/*
			 * Deselect them unless we're upgrading and the package
			 * in question wasn't an L10N package in the rev from
			 * which we're upgrading.
			 *
			 * This algorithm could be enhanced to check for
			 * packages that have changed locales, but that would
			 * be really expensive, and it's not clear that it's
			 * worth the effort.
			 */
			if (instprod) {
				if ((mi = find_new_package(instprod,
				    mp->info.mod->m_pkgid, mp->info.mod->m_arch,
				    &match))) {
					if (mi->m_locale == NULL) {
						/*
						 * The existing package was not
						 * an L10N package.
						 */
						continue;
					}
				}
			}

			mp->info.mod->m_status = UNSELECTED;
		}
	}

	/* Select all L10n packages for selected locales */
	for (ml = prod->info.prod->p_locale; ml; ml = ml->next) {
		if (!ml->info.locale->l_selected)
			continue;

		for (mp = ml->sub; mp; mp = mp->next) {

			/*
			 *    We only want to select localization packages
			 *    that make sense to be installed on this products
			 *    architecture.
			 */

			selectable = False;

			if (med->med_type == INSTALLED ||
				!(med->med_flags & SPLIT_FROM_SERVER)) {
				for (ap = prod->info.prod->p_arches; ap;
				    ap = ap->a_next) {

					ret = compatible_arch(
						mp->info.mod->m_arch,
						ap->a_arch);

					if ((ret == ARCH_MATCH ||
					    ret == ARCH_MORE_SPECIFIC) &&
					    ap->a_selected) {
						selectable = True;
						break;
					}
				}
			} else {  /* client package */
				for (ap = prod->info.prod->p_arches; ap;
				    ap = ap->a_next) {

					ret = compatible_arch(
						mp->info.mod->m_arch,
						ap->a_arch);

					if ((ret == ARCH_MATCH ||
					    ret == ARCH_MORE_SPECIFIC) &&
					    ap->a_selected) {

						ret = compatible_arch(
						    mp->info.mod->m_arch,
						    get_default_arch());

						if (ret == ARCH_MATCH ||
						    ret == ARCH_MORE_SPECIFIC) {
							selectable = True;
							break;
						}
					}
				}
			}


			if (!selectable) {
				mp->info.mod->m_status = UNSELECTED;
				continue;
			}
			if (mp->info.mod->m_pkgs_lclzd == NULL) {
				mp->info.mod->m_status = SELECTED;
				continue;
			}
			for (pkgloc = mp->info.mod->m_pkgs_lclzd; pkgloc;
			    pkgloc = pkgloc->next)
				if (pkgloc->pkg_lclzd->m_status == SELECTED ||
				    pkgloc->pkg_lclzd->m_status == REQUIRED)
					break;
			if (pkgloc)
				mp->info.mod->m_status = SELECTED;
			else
				mp->info.mod->m_status = UNSELECTED;
		}
	}
}

/*
 * sort_locales()
 *	Walk the locale chain for a given product and sort the
 *	language order alphabetically based on the language name.
 * Parameters:
 *	prod	- product to be sorted
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
sort_locales(Module * prod)
{

	Module  *p, *q;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("sort_locales");
#endif

	if (prod->info.prod->p_locale == NULL)
		return;

	for (p = prod->info.prod->p_locale->next; p != NULL; p = p->next) {
		for (q = prod->info.prod->p_locale; q != p; q = q->next) {
			if (strcoll(p->info.locale->l_language,
					q->info.locale->l_language) < 0) {
				if (p->next != NULL)
					p->next->prev = p->prev;
				p->prev->next = p->next;
				p->prev = q->prev;
				p->next = q;

				if (q->prev != NULL)
					q->prev->next = p;
				else
					prod->info.prod->p_locale = p;

				q->prev = p;
				break;
			}
		}
	}
}

/*
 * localize_packages()
 *	Walk the product package list to (1) build the list of "packages
 *	that localize this packages" for each package, and (2) for
 *	each locale in the product's p_locale list, build the list
 *	of l10n packages for that locale.  This function is called
 *	when building a product structure that describes either
 *	an installable media, or an installed product.
 * Parameters:
 *	prod	- pointer to product structure for product being walked
 * Return:
 *	none
 * Status:
 *	semi-private (internal library use only)
 */
void
localize_packages(Module * prod)
{

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("localize_packages");
#endif
	if ((prod->type == PRODUCT) || (prod->type == NULLPRODUCT))
		walklist(prod->info.prod->p_packages,
				resolve_package_l10n, (caddr_t)prod);
}

/*
 * add_locale_list()
 *	Add the locales from the list into the locale list for the
 *	specified product.
 * Parameters:
 *	prod	- non-NULL Product structure pointer
 *	loc_str_list	- a StringList of locales.
 * Return:
 *	ERR_INVALIDTYPE	- invalid product type
 *	ERR_INVALID	- invalid locale
 *	SUCCESS		- a valid locale structure was created
 *			  and added to the locale chain
 * Status:
 *	semi-private (internal library use only)
 */
int
add_locale_list(Module * prod, StringList * loc_str_list)
{
	int	stat;

	while (loc_str_list) {
		stat = add_locale(prod, loc_str_list->string_ptr);
		if (stat != SUCCESS)
			return (stat);
		loc_str_list = loc_str_list->next;
	}
	return (SUCCESS);
}

/*
 * Routines and data structure for maintaining a list of flags.  These
 * are used only by add_subset_locale_list().
 *
 * These routines should be moved out of soft_locale.c if somebody
 * else uses them.
 */

/* A list of flags used in add_subset_locale_list */
static struct flag_list {
	void *key;
	struct flag_list *next;
};

/* Prototypes */
static int find_flag(struct flag_list *, void *);
static struct flag_list *set_flag(struct flag_list *, void *);
static struct flag_list *unset_flag(struct flag_list *, void *);

/* Return 1 if the flag was found, 0 if it wasn't */
static int
find_flag(struct flag_list *fl, void *key)
{
	for (; fl; fl = fl->next)
		if (fl->key == key)
			return (1);
	return (0);
}

/*
 * Set a flag.  This list is built on two assumptions - that size
 * (or lack thereof) is very important, and that older flags (and flag
 * other than the newest one) are rarely, if ever accessed.
 */
static struct flag_list *
set_flag(struct flag_list *fl, void *key)
{
	struct flag_list *new;

	new = (struct flag_list *)xmalloc(sizeof (struct flag_list));

	new->key = key;
	new->next = fl;

	return (new);
}

/*
 * Unset a flag.  Delete the corresponding flag (if any) out of the list
 */
static struct flag_list *
unset_flag(struct flag_list *fl, void *key)
{
	struct flag_list *ofl = NULL;

	for (; fl && fl->key != key; ofl = fl, fl = fl->next);

	if (!ofl) {
		ofl = fl;
		fl = fl->next;
		free(ofl);
	} else if (fl) {
		ofl->next = fl->next;
		free(fl);
	}

	return (fl);
}

/*
 * add_subset_locale_list()
 *      Add locales from a package to a locale list, abiding by the
 *      following rules (for the entire list):
 *
 * 0. If no locale packages are found, the list of installed locales
 *    will be empty.
 *
 * 1. If there are any single-locale packages, the locales found in
 *    them are used as the list of installed locales.
 *
 * 2. If there are NO single-locale packages, and there is a set of
 *    locales that can be found in ALL multi-locale packages, that
 *    set, known as the minimum locale subset, will be used as the
 *    list of installed locales.
 *
 * 3. If there are NO single-locale package, and there is NO minimum
 *    locale subset (as defined in 3), the list of installed locales
 *    will be empty.
 *
 * See Bug #4032489 for more information
 *
 * Parameters:
 *	prod	- non-NULL Product structure pointer
 *	loc_str_list	- a StringList of locales.
 * Return:
 *	ERR_INVALIDTYPE	- invalid product type
 *	ERR_INVALID	- invalid locale
 *	SUCCESS		- a valid locale structure was created
 *			  and added to the locale chain
 * Status:
 *	semi-private (internal library use only)
 */
int
add_subset_locale_list(Module *prod, StringList* loc_str_list)
{
	static struct flag_list *subset_flag_list = NULL;
	int flag = 0;

	/*
	 * find_flag returns NULL if the value isn't found.  We're only making
	 * a list entry if the flag is set.
	 */
	flag = find_flag(subset_flag_list, prod);

	if (!loc_str_list->next) {
		/* Single locale package */
		if (flag) {
			free_locale(prod->info.prod->p_locale);
			prod->info.prod->p_locale = NULL;
			subset_flag_list = unset_flag(subset_flag_list, prod);
		}
		return (add_locale(prod, loc_str_list->string_ptr));
	} else {
		/* Multi locale package */
		if (flag) {
			/* Multi-locale package with a subset in the product */
			subset_locale_list(prod, loc_str_list);
			return (SUCCESS);
		} else {
			/* Multi-locale package without a subset in product */
			if (empty_locale_list(prod)) {
				/*
				 * Multi-locale package with nothing in
				 * the product
				 */
				subset_flag_list = set_flag(subset_flag_list,
							    prod);
				return (add_locale_list(prod, loc_str_list));
			} else {
				/*
				 * Multi-locale package with non-subset,
				 * non-empty product
				 */
			}
		}
	}

	return (SUCCESS);
}

/*
 * get_lang_from_locale()
 *	Returns a descriptive string describing the language represented
 *	by `locale'.  The string will have been translated into the
 *	appropriate local language.
 * Parameters:
 *	locale	-
 * Return:
 *
 * Status:
 *	semi-private
 */
char *
get_lang_from_locale(char *locale)
{
	LocMap	*lmap;
	LocaleList *ll;
	int i;
	char *desc;

	if ((lmap = global_locmap) != NULL) {
		while (lmap) {
			if (strcmp(lmap->locmap_partial, locale) == 0) {
				if (lmap->locmap_description)
					return (dgettext("SUNW_LOCALE_DESCR",
					    lmap->locmap_description));
				else
					break;
			}
			lmap = lmap->next;
		}
	}

	/*
	 * If locale is not found in the global_locmap,
	 * then check the llist.
	 */
	ll = llist;
	while (ll) {
		if (strneq(ll->locale_id, locale, strlen(ll->locale_id))) {
			if (ll->list) {
				for (i = 0; i < ll->n_locales; i++) {
					if (streq(ll->list[i], locale)) {
						if (ll->descriptions[i]) {
							return (dgettext(
							"SUNW_LOCALE_DESCR",
							ll->descriptions[i]));
						} else {
							break;
						}
					}
				}
			}
		}
		ll = ll->next;
	}

	if ((desc = get_lang_from_loc_array(locale)) != NULL) {
		return (desc);
	} else {
		return (locale);
	}
}

/*
 * get_lang_from_loc_array
 *
 * Attempt to map a locale id ("fr", "de") to its English
 * description, using the array loc_array.  THis is only used
 * for media that don't have locale_description files.
 */

char *
get_lang_from_loc_array(char *locale)
{
	int	i;
	int	high = (int)(sizeof (loc_array) / sizeof (struct loclang));

	for (i = 0; i < high; i++) {
		if (strcmp(locale, loc_array[i].locale) == 0)
			return (loc_array[i].locale);
	}
	return (NULL);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * resolve_package_l10n()
 *	Walklist() function used to (1) build the list of "packages
 *	that localize this packages" for each package, and (2) for
 *	each locale in the product's p_locale list, build the list
 *	of l10n packages for that locale.  This function is called
 *	when building a product structure that describes either
 *	an installable media, or an installed product.
 * Parameters:
 *	np	- node pointer for package being processed
 *	data	- product structure pointer parenting the package list
 * Return:
 *	ERR_NOPROD - product structure invalid
 * Status:
 *	private
 */
static int
resolve_package_l10n(Node * np, caddr_t data)
{
	char	*buf;
	char	*pkgid;
	char	*version;
	char	*delim;
	Node	*tn;
	char	*tmp;
	Module	*prod;
	Module	*mp, *mp1, *mp2;
	L10N	*lp;
	Modinfo	*mi, *milp;
	PkgsLocalized	*loclzd_pkg;

	/* use current product if data == NULL */
	if (data == NULL)
		prod = get_current_product();
	else
		/*LINTED [alignment ok]*/
		prod = (Module *)data;
	if (prod == NULL)
		return (ERR_NOPROD);

	mi = (Modinfo *)np->data;

	/*
	 * if this package is a localization package (has locale and list of
	 * affected packages that is non-NULL)
	 */
	if (mi->m_loc_strlist && mi->m_l10n_pkglist &&
	    (*(mi->m_l10n_pkglist))) {
		buf = (char *)xstrdup(mi->m_l10n_pkglist);
		pkgid = buf;

		do
		{
			/*
			 * break pkglist into components:
			 *
			 *	pkg1:version, pkg2:version..., pkgn:version
			 *	  ^    ^    ^
			 * pkgid__|    |    |
			 * version_____|    |
			 * delim____________|
			 */
			if (delim = strchr(pkgid, ','))
				*delim = '\0';

			if (version = strchr(pkgid, ':')) {
				*version = '\0';
				++version;
				if (delim) {
					tmp = delim;
					++delim;
					if (strncmp(delim, "REV=", 4) == 0) {
						*tmp = ',';
						if (delim = strchr(++tmp, ','))
							*delim = '\0';
					} else
						delim = tmp;
				}

			}

			/*
			 * figure out if package specification matchings a
			 * package we know about
			 */
			if ((tn = findnode(prod->info.prod->p_packages, pkgid))
							!= (Node *) NULL) {

				milp = (Modinfo *)tn->data;
				/*
				 * point package milp at package mi if no
				 * version is specified or if the version
				 * specified exactly matches milp's version
				 */
				if (version == (char *)NULL ||
				    streq(version, milp->m_version)) {
					lp = (L10N *) xcalloc(sizeof (L10N));
					lp->l10n_package = mi;
					lp->l10n_next = milp->m_l10n;
					milp->m_l10n = lp;

					loclzd_pkg = (PkgsLocalized *)
					    xcalloc(
						(size_t)sizeof (PkgsLocalized));
					loclzd_pkg->pkg_lclzd = milp;
					link_to((Item **)&mi->m_pkgs_lclzd,
					    (Item *)loclzd_pkg);
				}
			}

			if (delim) {			/* another token? */
				/* skip any leading white space */
				for (++delim; delim && *delim &&
				    ((*delim == ' ') || (*delim == '\t'));
				    ++delim);
					pkgid = delim;
			}
		} while (delim);

		free(buf);
	}
	/* Add to locale tree */
	if (mi->m_loc_strlist) {
		for (mp = prod->info.prod->p_locale; mp; mp = mp->next) {
			if (StringListFind(mi->m_loc_strlist,
					mp->info.locale->l_locale) == NULL)
				continue;
			mp2 = NULL;
			for (mp1 = mp->sub; mp1; mp1 = mp1->next) {
				if (strcmp(mp1->info.mod->m_pkgid,
						mi->m_pkgid) == NULL)
					break;
				mp2 = mp1;
			}
			if (mp1)
				continue;
			if (!mp2) {
				mp1 = mp->sub =
					(Module *)xcalloc(sizeof (Module));
				mp1->prev = NULL;
			} else {
				mp1 = mp2->next =
					(Module *)xcalloc(sizeof (Module));
				mp1->prev = mp2;
			}
			mp1->info.mod = mi;
			mp1->parent = mp;
			mp1->head = mp->sub;
		}
	}
	return (SUCCESS);
}

/*
 * get_C_lang_from_locale()
 *	Returns a descriptive string describing the language represented
 *	by `locale'.  The string is not translated.
 * Parameters:
 *	locale	-
 * Return:
 *
 * Status:
 *	private
 */
char *
get_C_lang_from_locale(char *locale)
{
	LocMap	*lmap;

	if ((lmap = global_locmap) != NULL) {
		while (lmap) {
			if (strcmp(lmap->locmap_partial, locale) == 0) {
				if (lmap->locmap_description)
					return (lmap->locmap_description);
				else
					break;
			}
			lmap = lmap->next;
		}
	}

	return (get_lang_from_loc_array(locale));
}

/*
 * valid_product_locale()
 *	Determine whether or not the passed locale is one of the locales
 *	attached to the product.
 * Parameters:
 *	mod	- product module pointer (must be type PRODUCT or NULLPRODUCT)
 *	locale	- name of locale to be checked
 * Return:
 *	TRUE	- locale found
 *	FALSE	- locale not found
 * Status:
 *	private
 */
static int
valid_product_locale(Module *mod, char *locale)
{
	Module *m;

	for (m = mod->info.prod->p_locale; m != NULL; m = m->next) {
		if (streq(locale, m->info.locale->l_locale)) {
			return (TRUE);
		}
	}

	return (FALSE);
}

/*
 * select_decomp_locale()
 *	Try to select a given locale (and its required base locales, if any).
 *	If the locale cannot be selected, try the decompositions of it (if any).
 *	The first decomposition is the removal of everything after the first
 *	at sign.  The second decomposition is the removal of everything after
 *	the first dot.  The third decomposition is the removal of everything
 *	after the underscore.  The routine stops with the first successful
 *	selection.
 * Parameters:
 *	mod	- product module pointer (must be type PRODUCT or NULLPRODUCT)
 *	locale	- name of locale to be SELECTED
 * Return:
 *	ERR_BADLOCALE	- 'locale' can't be selected.
 *	SUCCESS		- locale structure of type 'locale' set successfully
 * Status:
 *	private
 */
static int
select_decomp_locale(Module *mod, char *locale)
{
	char locbuf[MAX_LOCALE + 1];
	char *c;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_decomp_locale");
#endif

	(void) strncpy(locbuf, locale, sizeof (locbuf));
	if (!valid_product_locale(mod, locbuf)) {
		/* Try truncating at the '@' (if any) */
		if ((c = strchr(locbuf, '@'))) {
			*c = '\0';
		}

		if (!valid_product_locale(mod, locbuf)) {
			/* Try truncating at the dot (if any) */
			if ((c = strchr(locbuf, '.'))) {
				*c = '\0';
			}

			if (!valid_product_locale(mod, locbuf)) {
				/* Try truncating at the underscore */
				if ((c = strchr(locbuf, '_'))) {
					*c = '\0';
				}
			}
		}
	}

	return (select_single_locale(mod, locbuf));
}

/*
 * select_single_locale()
 *	Select the partial locale, and all base locales required by the
 *	partial locale.  If the selection of any of the base locales
 *	succeed, or if one of the base locales is "C", return SUCCESS (even
 *	if the selection of the partial locale failed, or if the selection
 *	of any of the base locales failed.)  If there are no base locales
 *	associated with the partial locale, return the result of selecting
 *	the partial locale.
 * Parameters:
 *	mod	- product module pointer (must be type PRODUCT or NULLPRODUCT)
 *	locale	- name of locale to be SELECTED
 * Return:
 *	ERR_BADLOCALE	- 'locale' can't be selected.
 *	SUCCESS		- locale structure of type 'locale' set successfully
 * Status:
 *	public
 */
static int
select_single_locale(Module *mod, char *locale)
{
	int	part_status, base_status, base_locale_selected;
	StringList *str;
	LocMap	*lmap;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_single_locale");
#endif

	part_status = select_base_locale(mod, locale);

	/* defensive programming */
	if (!mod->parent || !mod->parent->info.media)
		return (part_status);

	for (lmap = global_locmap; lmap != NULL; lmap = lmap->next) {
		if (strcmp(lmap->locmap_partial, locale) != 0)
			continue;
		if (lmap->locmap_base == NULL)
			break;
		base_locale_selected = 0;
		for (str = lmap->locmap_base; str; str = str->next) {
			if (strcmp(str->string_ptr, "C") == 0) {
				base_locale_selected = 1;
				continue;
			}
			base_status = select_base_locale(mod, str->string_ptr);
			if (base_status == SUCCESS)
				base_locale_selected = 1;
		}
		if (base_locale_selected)
			return (SUCCESS);
		else
			return (ERR_BADLOCALE);
	}

	return (part_status);
}

/*
 * select_base_locale()
 *	Scan the 'mod' product locale list for a member which matches 'locale'.
 *	If found, set the status of that locale structure to "SELECTED" and
 *	return.
 * Parameters:
 *	mod	- product module pointer (must be type PRODUCT or NULLPRODUCT)
 *	locale	- name of locale to be SELECTED
 * Return:
 *	ERR_INVALIDTYPE	- 'mod' is neither a PRODUCT or NULLPRODUCT
 *	ERR_BADLOCALE	- 'locale' is not part of the locale chain for 'mod'
 *	SUCCESS		- locale structure of type 'locale' set successfully
 * Status:
 *	public
 */
static int
select_base_locale(Module *mod, char *locale)
{
	Module	*m;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("select_base_locale");
#endif

	for (m = mod->info.prod->p_locale; m != NULL; m = m->next) {
		if (strcmp(locale, m->info.locale->l_locale) == 0) {
			m->info.locale->l_selected = SELECTED;
			sync_l10n(mod);
			return (SUCCESS);
		}
	}

	return (ERR_BADLOCALE);
}

/*
 * add_locale()
 *	Search for a specified locale in the current list of known
 *	product locales, and if it doesn't already exist, add it
 *	to the list. The locale must be legal (see loc_array[]) and
 *	the product structure must by type PRODUCT or NULLPRODUCT.
 *	If the geographic region corresponding to this locale hasn't
 *	already been seen, add it too.
 * Parameters:
 *	prod	- non-NULL Product structure pointer
 *	locale	- non-NULL locale
 * Return:
 *	ERR_INVALIDTYPE	- invalid product type
 *	ERR_INVALID	- invalid locale
 *	SUCCESS		- a valid locale structure was created
 *			  and added to the locale chain
 * Status:
 *	static
 */
static int
add_locale(Module *prod, char *locale)
{
	Module	*lp, *lastlocale;
	char	*cp;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("add_locale");
#endif
	lp = lastlocale = (Module *) NULL;

	if ((prod->type != PRODUCT) && (prod->type != NULLPRODUCT))
		return (ERR_INVALIDTYPE);

	if ((cp = get_lang_from_locale(locale)) == (char *)NULL ||
						strcmp(locale, "C") == 0)
		return (ERR_INVALID);

	for (lp = prod->info.prod->p_locale; lp; lp = lp->next) {
		if (strcmp(locale, lp->info.locale->l_locale) == 0)
			break;
		else
			lastlocale = lp;
	}

	/*
	 * Don't fail on this since there is no geo information
	 * for 2.6 and 2.7 and this code is used for adding
	 * services for these versions.
	 */
	if (add_geo(prod, locale) != SUCCESS &&
		prod->info.prod->p_version != NULL &&
		!(strneq(prod->info.prod->p_version, "2.7", 3) ||
		strneq(prod->info.prod->p_version, "2.6", 3))) {

		return (ERR_INVALID);
	}

	if (lp == (Module *) NULL) {
		lp = (Module *) xcalloc(sizeof (Module));
		lp->info.locale = (Locale *) xcalloc(sizeof (Locale));
		lp->info.locale->l_locale = (char *)xstrdup(locale);
		lp->info.locale->l_language = cp;
		lp->type = LOCALE;
		lp->next = NULL;
		lp->sub = NULL;
		lp->head = prod->info.prod->p_locale;
		lp->parent = prod;

		if (lastlocale) {
			lastlocale->next = lp;
			lp->prev = lastlocale;
		} else {
			prod->info.prod->p_locale = lp;
			lp->prev = NULL;
		}
	}
	return (SUCCESS);
}

/*
 * empty_locale_list()
 *      Determine whether or not a given package has any locales
 * Parameters:
 *      prod - product in which the locales are defined.
 * Return:
 *      0        - the product has no locales
 *      non-zero - the product has one or more locales
 * Status:
 *      static
 */
static int
empty_locale_list(Module* prod)
{
	return (prod->info.prod->p_locale == NULL);
}

/*
 * subset_locale_list()
 *      Given a locale list and a product, modify the locale list in
 *      the product such that the resulting list is the intersection
 *      of the passed locale list and the original locale list from the
 *      product.
 * Parameters:
 *      prod - product in which the locales are selected.
 *      loc_str_list - list of locales
 * Return:
 *      none
 * Status:
 *      static
 */
static void
subset_locale_list(Module* prod, StringList* loc_str_list) {
	Module *prodloc = prod->info.prod->p_locale;
	Module *tmp;
	StringList *strptr;
	int found;

	while (prodloc) {
		/*
		 * Look for the current product locale in the package
		 * locale list
		 */
		for (found = 0, strptr = loc_str_list; strptr;
		    strptr = strptr->next)
			if (streq(strptr->string_ptr,
			    prodloc->info.locale->l_locale)) {
				found = 1;
				break;
			}

		if (!found) {
			/*
			 * Not found in package locale list, so delete it from
			 * product locale list.
			 */
			if (prodloc == prod->info.prod->p_locale) {
				/* Delete it from the head of the list */
				tmp = prodloc;

				prod->info.prod->p_locale = prodloc =
								prodloc->next;

				if (prodloc)
					prodloc->prev = NULL;
				tmp->next = NULL;
				free_locale(tmp);
			} else {
				/*
				 * Delete it from the middle or end of the
				 * list
				 */
				if (prodloc->next) {
					prodloc->next->prev = prodloc->prev;
				}
				if (prodloc->prev) {
					prodloc->prev->next = prodloc->next;
				}
				tmp = prodloc;
				prodloc = prodloc->next;
				free(tmp);
			}
		} else {
			prodloc = prodloc->next;
		}
	}
}

/*
 * Function:	translate_locale
 * Description:	Validate the specified locale.  There are two stages to this.
 *		First, we check to see if the specified locale exists on the
 *		currently running system in /usr/lib/locale as either a full
 *		or partial locale.  If it doesn't then the user may have
 *		specified an old locale name.  If they've specified an old
 *		name, then we need to turn it into the new version.
 * Scope:	Private
 * Parameters:	locale [RO] (char *)
 *		A pointer to the character string containing the
 *		locale.
 * Return:	char *	- The locale to use
 *		NULL	- Invalid locale specified
 */
static char *
translate_locale(const char *locale)
{
	static char trans[MAX_LOCALE + 1];
	char path[MAXPATHLEN];
	char linebuf[128];
	struct stat stat_buf;
	FILE *fp;
	char *c;

	(void) strncpy(trans, locale, sizeof (trans));

	/*
	 * Let's try to translate the locale name to a newer version.
	 */
	if ((fp = fopen(LCTTAB, "r"))) {
		while (fgets(linebuf, 128, fp)) {

			trim(linebuf);
			if (strlen(linebuf) <= 0 || linebuf[0] == '#') {
				continue;
			}

			/* Search for whitespace */
			for (c = linebuf; *c && !isspace(*c); c++);
			if (!*c) {
				/* End of line - invalid input */
				continue;
			}

			*c = '\0';
			if (strcmp(linebuf, locale) != 0) {
				continue;
			}

			/* Found the old name - get the new version */
			for (c++; *c && isspace(*c); c++);
			if (!*c) {
				/* End of line - invalid input */
				continue;
			}

			(void) strncpy(trans, c, sizeof (trans));
			trans[MAX_LOCALE] = '\0';

			break;
		}
		(void) fclose(fp);
	}

	/*
	 * Check to see if locale is a full locale by checking
	 * to see if the LIBSOFT message file exists
	 */
	(void) snprintf(path, sizeof (path), "%s/%s/LC_MESSAGES/%s.mo",
		NLSPATH, trans, "SUNW_INSTALL_LIBSOFT");
	if ((stat(path, &stat_buf) == 0) &&
			((stat_buf.st_mode & S_IFMT) == S_IFREG)) {
		/* Valid full locale */
		return (trans);
	}

	/*
	 * Check to see if locale is a partial locale by checking
	 * for the existence of the locale description file
	 */
	(void) snprintf(path, sizeof (path), "%s/%s/locale_description",
	    NLSPATH, trans);
	if ((stat(path, &stat_buf) == 0) &&
			((stat_buf.st_mode & S_IFMT) == S_IFREG)) {
		/* Valid partial locale */
		return (trans);
	}

	/* Didn't find anything */
	return (NULL);
}

/*
 * create_locale_list_entry
 *	Function to add an entry into the internal locale list.  Each
 *	locale list entry consists of the base locale id, and a list
 *	of
 * Paremters:
 *	locale_id	- non-NULL pointer to the base locale id.
 * Returns:
 *	SUCCESS
 *	FAILURE
 * Status:
 *	static
 */
static int
create_locale_list_entry(char *locale_id)
{
	char		d_locale[MAXPATHLEN];
	char		locale_map[MAXPATHLEN];
	char		geo_map[MAXPATHLEN];

	DIR		*locale_dir;
	struct dirent	*locale;
	struct stat	buf;
	int		num_locales = 0;

	LocaleList	*last, *new;

	if (locale_id == NULL)
		return (FAILURE);

	new = (LocaleList *)xcalloc(sizeof (LocaleList));

	new->locale_id = locale_id;

	locale_dir = opendir(NLSPATH);

	while (locale_dir && (locale = readdir(locale_dir))) {

		(void) snprintf(d_locale, sizeof (d_locale), "%s.", locale_id);

		/*
		 * If this directory equals the locale_id being checked,
		 * check if has a locale_map in its directory.
		 */
		if (strcmp(locale_id, locale->d_name) == 0) {

			(void) snprintf(locale_map, sizeof (locale_map),
			    "%s/%s/%s", NLSPATH, locale->d_name,
			    LOCALE_MAP_FILE);
			(void) snprintf(geo_map, sizeof (geo_map),
			    "%s/%s/%s", NLSPATH, locale->d_name,
			    GEO_MAP_FILE);

			if (stat(locale_map, &buf) || !S_ISREG(buf.st_mode)) {
				/* No locale_map - not a locale */
				continue;
			} else {
				/*
				 * Has locale_map - save its namd and
				 * description, and add it to list.
				 */
				add_to_list(&new->list, &new->descriptions,
					num_locales, locale->d_name);
				num_locales++;
			}

		/*
		 * IF this directory equals one of the locale_id's
		 * derivatives, check if it has a locale_map and that
		 * it does not have a geo_map.
		 */
		} else if (strncmp(d_locale, locale->d_name,
						strlen(d_locale)) == 0) {

			(void) snprintf(locale_map, sizeof (locale_map),
			    "%s/%s/%s", NLSPATH, locale->d_name,
			    LOCALE_MAP_FILE);
			(void) snprintf(geo_map, sizeof (geo_map),
			    "%s/%s/%s", NLSPATH, locale->d_name, GEO_MAP_FILE);

			if (stat(locale_map, &buf) || !S_ISREG(buf.st_mode)) {
				/* No locale_map - not a derivative locale */
				continue;
			} else if (!stat(geo_map, &buf) &&
					S_ISREG(buf.st_mode)) {
				/* Has a geo_map - not a derivative locale */
				continue;
			} else {
				/*
				 * Has locale_map - save its name and
				 * description, and add it to list.
				 */
				add_to_list(&new->list, &new->descriptions,
					num_locales, locale->d_name);
				num_locales++;
			}
		}
	}

	if (locale_dir)
		(void) closedir(locale_dir);

	new->n_locales = num_locales;
	new->next = NULL;

	if (llist == NULL) {
		llist = new;
	} else {
		last = llist;
		while (last->next) {
			last = last->next;
		}
		last->next = new;
	}

	return (SUCCESS);
}

/*
 * add_to_list
 *	Function to add an sub-entry into the locale list.
 * Parameters:
 *	none
 * Returns:
 *	none
 * Status:
 *	static
 */
static void
add_to_list(char ***list, char ***desc, int num_locales, char *locale)
{
	if (*list == NULL) {
		*list = (char **)xcalloc(sizeof (char *));
		(*list)[0] = xstrdup(locale);
		*desc = (char **)xcalloc(sizeof (char *));
		(*desc)[0] = xstrdup(get_locale_description("/", locale));
	} else {
		*list = (char **)xrealloc((*list),
					(num_locales + 1) * sizeof (char *));
		(*list)[num_locales] = xstrdup(locale);
		(*desc) = (char **)xrealloc((*desc),
					(num_locales + 1) * sizeof (char *));
		(*desc)[num_locales] =
			xstrdup(get_locale_description("/", locale));
	}
}

/*
 * free_locale_list
 *	Function to free the locale list.
 * Parameters:
 *	none
 * Returns:
 *	none
 * Status:
 *	static
 */

static void
free_locale_list(void)
{
	LocaleList *ll, *ll_prev;
	int i;

	ll = llist;
	while (ll) {
		if (ll->locale_id)
			free(ll->locale_id);

		if (ll->list) {
			for (i = 0; i < ll->n_locales; i++) {
				if (ll->list[i])
					free(ll->list[i]);
			}
			free(ll->list);
		}

		if (ll->descriptions) {
			for (i = 0; i < ll->n_locales; i++) {
				if (ll->descriptions[i])
					free(ll->descriptions[i]);
			}
			free(ll->descriptions);
		}

		ll_prev = ll;
		ll = ll->next;
		free(ll_prev);
	}

	llist = NULL;
}
