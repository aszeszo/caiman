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
 * Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
 * Use is subject to license terms.
 */
/*
 * Copyright 2011 Nexenta Systems, Inc.  All rights reserved.
 */

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <stropts.h>
#include <sys/kbio.h>
#include <stdio.h>
#include <libintl.h>
#include <locale.h>
#include <malloc.h>
#include <string.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <unistd.h>
#include <stdlib.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <errno.h>
#include <dirent.h>
#include <ctype.h>

#include "orchestrator_private.h"
#include "orchestrator_lang_codes.h"

#define	COUNTRY_SEP	'_'
#define	CODESET_SEP	'.'
#define	UTF		"UTF-8"

#define	SIMPLIFIED_CHINESE	"Chinese-Simplified"
#define	TRADITIONAL_CHINESE	"Chinese-Traditional"

#define	INSTALL_NLS_PATH	"/usr/lib/install/data/lib/locale"
#define	NLS_PATH		"/usr/lib/locale"


/* Static variables used to store language/locale system information */

static	lang_info_t 	*install_ll_list = NULL;	/* lang, locale list */
static	lang_info_t	*supported_ll_list = NULL;
static	char		*install_lang_list[MAX_NUM_LANG];
static	char		*supported_lang_list[MAX_NUM_LANG];
static	char		**install_languages = NULL;	/* sorted list */
static	char		**supported_languages = NULL;
static	char		*app_locale = NULL;
static	int		lang_initialized = 0;
static	int		install_initialized = 0;
static	int		install_lang_total = 0;
static	int		supported_lang_total = 0;

struct	chinese_values {
	char 	*lang;
	char	*lang_name;
	char	*lang_code;
} chinese_values[] = {
	{"zh", SIMPLIFIED_CHINESE, "sc"},
	{"zh_CN", SIMPLIFIED_CHINESE, "sc"},
	{"zh_HK", TRADITIONAL_CHINESE, "tc"},
	{"zh_MO", TRADITIONAL_CHINESE, "tc"},
	{"zh_SG", TRADITIONAL_CHINESE, "tc"},
	{"zh_TW", TRADITIONAL_CHINESE, "tc"},
	{ NULL }
};


static int 	add_lang_to_list(char ***list, char *locale, int *k, int j);
static void 	add_locale_entry_to_lang(lang_info_t *lp, char *locale,
    char *region, boolean_t is_default);
static int	build_language_list(char *path, char **, int *);
static void	build_install_ll_list(char *nlspath, char **list,
    int lang_total, lang_info_t **return_list, int *ll_total);
static void	build_ll_list(char **list, int lang_total,
		    lang_info_t **, int *total);
static	char	*copy_up_to(char *start, char *t);
static int	create_lang_entry(char *lang, char *locale, char *region,
    lang_info_t **, boolean_t locale_app_locale, boolean_t locale_in_installer_lang);
static void	end_of_comp(char **t, char **start);
static char 	**get_actual_languages(char **list, int *);
static lang_info_t *get_lang_entry(char *, lang_info_t *search_list);
static char 	*get_locale_component(char **t, char **start);
static char 	*get_locale_description(char *lang, char *region);
static int 	handle_chinese_language(char *region, char **lang);
static boolean_t is_locale_in_installer_lang(char *locale_name);
static boolean_t is_locale_app_locale(char *locale_name);
static boolean_t is_valid_locale(char *locale);
static int 	list_cmp(const void *p1, const void *p2);
static int 	lang_init(char *path, char **list, int *total, int *init_var);
static int 	save_system_default_locale(char *locale);
static void 	set_lang(char *locale);
static void 	set_lc(char *, char *, char *, char *, char *, char *);
static char 	*strip_comment(char *buf);
static char 	*translate_description(char *locale, char *desc);
static void 	translate_lang_names(lang_info_t **list);
static void 	sort_lang_list(char **unsorted_list, int total);
static char 	*substitute_chinese_language(char *locale, char **code);
static char 	*substitute_C_POSIX_language(char **code);
static char 	*substitute_language(char *locale, char **code);
static void 	update_init(FILE *fp, char *locale);
static void 	update_env(char *locale);

#define	STR_LANG	"LANG="
#define	LEN_LANG	(sizeof (STR_LANG) - 1)
#define	STR_LC_COLLATE	"LC_COLLATE="
#define	LEN_LC_COLLATE	(sizeof (STR_LC_COLLATE) - 1)
#define	STR_LC_CTYPE	"LC_CTYPE="
#define	LEN_LC_CTYPE	(sizeof (STR_LC_CTYPE) - 1)
#define	STR_LC_MESSAGES	"LC_MESSAGES="
#define	LEN_LC_MESSAGES	(sizeof (STR_LC_MESSAGES) - 1)
#define	STR_LC_MONETARY	"LC_MONETARY="
#define	LEN_LC_MONETARY	(sizeof (STR_LC_MONETARY) - 1)
#define	STR_LC_NUMERIC	"LC_NUMERIC="
#define	LEN_LC_NUMERIC	(sizeof (STR_LC_NUMERIC) - 1)
#define	STR_LC_TIME	"LC_TIME="
#define	LEN_LC_TIME	(sizeof (STR_LC_TIME) - 1)


/*
 * om_get_install_lang_info
 * This function returns the locales available for use in setting
 * installer locale.
 * Input:	None
 * Output:	int *total, returns the total number of locales found
 * Return:	Pointer to lang_info_t which is a linked list of
 *		locales available for selection.
 *		NULL if no locales found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILIRE if no locales found.
 */
lang_info_t *
om_get_install_lang_info(int *total)
{
	int		ll_total;
	int		ret;

	/*
	 * Path to look for locale data.
	 */
	*total = 0;
	/*
	 * Build the lang list for the install application support.
	 */
	if (!install_initialized) {
		ret = lang_init(INSTALL_NLS_PATH, (char **)&install_lang_list,
		    &install_lang_total, &install_initialized);
		if (ret)
			return (NULL);
	}

	/*
	 * For the install languages we build the locale list associated
	 * with them by reading the lcctab file in the /usr/lib/locale/
	 * directory.
	 */
	build_install_ll_list(NLS_PATH, (char **)&install_lang_list,
	    install_lang_total, &install_ll_list, &ll_total);
	*total = ll_total;
	return (install_ll_list);
}

/*
 * om_get_install_lang_names
 * This function returns the lang names available for use in setting
 * installer locale system
 * Input:	None
 * Output:	int *total, returns the total number of locales found
 * Return:	char ** list of lang names available for selection.
 *		NULL if no locales found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILIRE if no locales found.
 */
char **
om_get_install_lang_names(int *total)
{
	int		ret;
	*total = 0;

	/*
	 * Reads directory that contains installation application
	 * languages. Fills install_lang_list with this data,
	 * if this has not been initialized yet.
	 */
	if (!install_initialized) {
		ret = lang_init(INSTALL_NLS_PATH, (char **)&install_lang_list,
		    &install_lang_total, &install_initialized);
		if (ret)
			return (NULL);
	}
	install_languages = get_actual_languages((char **)install_lang_list,
	    total);
	sort_lang_list(install_languages, *total);
	return (install_languages);
}

/*
 * om_get_lang_info
 * This function returns the available locales for installation on to
 * system
 * Input:	None
 * Output:	int *total, returns the total number of locales found
 * Return:	Pointer to lang_info_t which is a linked list of
 *		locales available for selection to install.
 *		NULL if no locales found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILIRE if no locales found.
 */
lang_info_t *
om_get_lang_info(int *total)
{
	int	ret;
	int	locale_total;

	*total = 0;

	if (!lang_initialized) {
		ret = lang_init(NLS_PATH, (char **)&supported_lang_list,
		    &supported_lang_total, &lang_initialized);
		if (ret)
			return (NULL);
	}
	/*
	 * This function looks in usr/lib/locale on the installation
	 * media to determine languages that we provide support for.
	 */
	sort_lang_list((char **)&supported_lang_list, supported_lang_total);
	build_ll_list((char **)&supported_lang_list, supported_lang_total,
	    &supported_ll_list, &locale_total);
	*total = locale_total;
	return (supported_ll_list);
}

/*
 * om_get_lang_names
 * This function returns the language strings that can are supported for
 * installation on to system.
 * Input:	None
 * Output:	int *total, returns the total number of lang names found
 * Return:	char ** list of lang names
 *		NULL if no lang names found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */

char **
om_get_lang_names(int *total)
{
	int	ret = 0;
	*total = 0;

	/*
	 * We only gather 'supported lang names'. Supported means
	 * full locale, UTF-8 only. For display to the user for
	 * default locale selection.
	 */
	if (!lang_initialized) {
		ret = lang_init(NLS_PATH, (char **)&supported_lang_list,
		    &supported_lang_total, &lang_initialized);
		if (ret) {
			return (NULL);
		}
	}
	supported_languages = get_actual_languages(supported_lang_list, total);
	sort_lang_list(supported_languages, *total);
	return (supported_languages);
}

/*
 * om_get_locale_info
 * This function returns a linked list of locale_info_t's that correspond
 * to the language specified.
 * Input:	char *lang - language for which to return locale data.
 * Output:	int *total, returns the total number of lang names found
 * Return:	locale_info_t * list of locale_names.
 *		NULL if no locale names found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
locale_info_t *
om_get_locale_info(char *lang, int *total)
{
	lang_info_t *langp;
	locale_info_t *localep = NULL;
	lang_info_t	*tmp = supported_ll_list;

	if (tmp == NULL)
		tmp = install_ll_list;
	if (tmp == NULL)
		return (NULL);

	/*
	 * The lang is passed in as the lang code. Not the translated
	 * name.
	 */
	for (langp = tmp; langp != NULL; langp = langp->next) {
		if (strcmp(langp->lang, lang) == 0) {
			localep = langp->locale_info;
			break;
		}
	}
	*total = langp->n_locales;
	return (localep);
}

/*
 * om_get_locale_names
 * This function returns a list of locale names that correspond
 * to the language specified.
 * Input:	char *lang - language for which to return locale data.
 * Output:	int *total, returns the total number of lang names found
 * Return:	char ** list of locale_names.
 *		NULL if no locale names found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
char **
om_get_locale_names(char *lang, int *total)
{
	lang_info_t 	*langp;
	locale_info_t 	*localep = NULL;
	char		**locale_names;
	int		i = 0;

	/*
	 * locale_names is a an array of char *. Allocate each array
	 * member before strduping the locale_info in to this array.
	 */

	/*
	 * The lang is passed in as the lang code. Not the translated
	 * name.
	 */
	for (langp = supported_ll_list; langp != NULL; langp = langp->next) {
		if (strcmp(langp->lang, lang) == 0) {
			localep = langp->locale_info;
			break;
		}
	}
	/*
	 * allocate number of char * pointers to correspond to number
	 * of locale names.
	 */
	locale_names = (char **)malloc(langp->n_locales * sizeof (char *));
	if (locale_names == NULL) {
		om_set_error(OM_NO_SPACE);
		return (NULL);
	}

	for (; localep; localep = localep->next) {
		locale_names[i] = strdup(localep->locale_name);
		if (locale_names[i] == NULL) {
			om_free_lang_names(locale_names);
			om_set_error(OM_NO_SPACE);
			return (NULL);
		}
		i++;
	}
	*total = i;
	return (locale_names);
}

/*
 * om_set_install_lang_by_value
 * This function sets the installer application language, using the
 * lang_info_t * data passed in.
 * Input:	lang_info_t	* lang/locale info to set
 * Output:	none
 * Return:	Success or Failure
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
int
om_set_install_lang_by_value(lang_info_t *localep)
{
	/*
	 * For install applications, there will only be 1 locale
	 * associated with that language.
	 */
	locale_info_t *locp = localep->locale_info;
	if (locp == NULL) {
		om_set_error(OM_INVALID_LOCALE);
		return (OM_FAILURE);
	}

	om_save_locale(locp->locale_name, B_TRUE);
	return (OM_SUCCESS);
}

/*
 * om_set_install_lang_by_name
 * This function sets the installer application language, using the
 * lang name passed in.
 * Input:	char *lang name to set.
 * Output:	none
 * Return:	int, Success or Failure
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
int
om_set_install_lang_by_name(char *lang)
{
	locale_info_t	*locp;
	int		total;
	/*
	 * Find the locale entry based on the name passed in. If no
	 * locales for this language use the default locale of C/POSIX.
	 */
	locp = om_get_locale_info(lang, &total);

	if (locp == NULL) {
		om_set_error(OM_INVALID_LOCALE);
		return (OM_FAILURE);
	}

	/*
	 * Now, set the environment for the installation application.
	 */
	om_save_locale(locp->locale_name, B_TRUE);
	om_free_locale_info(locp);
	return (OM_SUCCESS);
}

/*
 * om_set_default_locale_by_name
 * This function sets the system default locale by name
 * Input:	char *lang name to set.
 * Output:	none
 * Return:	int, Success or Failure
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
int
om_set_default_locale_by_name(char *localep)
{
	int ret = 0;

	/*
	 * C/Posix is the default, there is no need to specify it
	 * in the /etc/default/init file.
	 */
	if (strcasecmp(localep, "C/Posix") == 0 ||
	    strcasecmp(localep, "Posix") == 0) {
		return (ret);
	}
	ret = save_system_default_locale(localep);
	if (!ret)
		om_save_locale(localep, B_FALSE);
	return (ret);
}

/*
 * om_get_default_locale
 * This function returns the default locale as set by a call to
 * set_default_locale.
 * Input:	locale_info_t *loclistp - list to search
 * Output:	none
 * Return:	locale_info_t * pointer to structure for default locale.
 * 		or NULL if none found.
 * Error Handling:
 *		OM_SUCCESS if locales found.
 *		OM_FAILURE if no locales found.
 */
locale_info_t *
om_get_def_locale(locale_info_t *loclistp)
{
	locale_info_t *lp;

	for (lp = loclistp; lp != NULL; lp = lp->next)
		if (lp->def_locale == B_TRUE)
			return (lp);
	return (NULL);
}
/*
 * om_free_lang_names
 * This function frees the memory associated with the char **list of lang
 * names passed in.
 * Input:	char **lang name list.
 * Output:	none
 * Return:	none
 * Error Handling:
 *		none
 */
void
om_free_lang_names(char **listp)
{
	int	i = 0;

	for (i = 0; listp[i] != NULL; i++) {
		free(listp[i]);
	}
	free(listp);
}

/*
 * om_free_lang_info
 * This function frees the memory associated with the lang_info_t *list
 * Input:	lang_info_t * langp - list to free
 * Output:	none
 * Return:	none
 * Error Handling:
 *		none
 */
void
om_free_lang_info(lang_info_t *langp)
{
	lang_info_t *nextp;

	while (langp != NULL) {
		nextp = langp->next;
		om_free_locale_info((locale_info_t *)langp->locale_info);
		free(langp->lang);
		free(langp->lang_name);
		free(langp);
		langp = nextp;
	}
}

/*
 * om_free_locale_info
 * This function frees the memory associated with the locale_info_t *list
 * Input:	locale_info_t * localep - list to free
 * Output:	none
 * Return:	none
 * Error Handling:
 *		none
 */
void
om_free_locale_info(locale_info_t *localep)
{
	locale_info_t	*nextp;

	while (localep != NULL) {
		nextp = localep->next;
		free(localep->locale_name);
		free(localep->locale_desc);
		free(localep);
		localep = nextp;
	}
}
/*
 * Static functions.
 */
static int
save_system_default_locale(char *locale)
{

	FILE 	*fp = (FILE *)NULL;

	if (locale == NULL)
		return (OM_FAILURE);

	if ((fp = fopen(TMP_INITDEFSYSLOC, "w")) == (FILE *)NULL)
		return (OM_FAILURE);
	if (fprintf(fp, "%s\n", locale) < 0) {
		(void) fclose(fp);
		return (OM_FAILURE);
	}
	(void) fclose(fp);

	if ((fp = fopen(TMP_DEFSYSLOC, "w")) == (FILE *)NULL)
		return (OM_FAILURE);
	if (fprintf(fp, "%s\n", locale) < 0) {
		(void) fclose(fp);
		return (OM_FAILURE);
	}
	(void) fclose(fp);
	return (OM_SUCCESS);
}


static int
lang_init(char *path, char **list, int *total, int *init_var)
{
	int	ret;

	ret = build_language_list(path, list, total);
	if (!ret) {
		*init_var = 1;
	}
	return (ret);
}

/*
 * Function
 *		create_lang_entry
 *
 * Description
 *		Create a language/locale list node and link
 *		it into the lang/locale linked list.
 *
 * Scope
 *		Private
 *
 * Parameters
 *		lang - language to add
 *		locale - locale which uses lang
 *
 * Return
 *		none
 *
 */
static int
create_lang_entry(char *lang, char *locale, char *region,
    lang_info_t **return_list, boolean_t locale_app_locale, boolean_t locale_in_installer_lang)
{
	lang_info_t	*tmp, *last, *new;
	locale_info_t	*lp = NULL;
	char		**trans_lang = NULL;
	char		*sub = NULL;
	char		*tmp_lang = NULL;
	char		*code = NULL;
	char		*desc = NULL;
	int		total;
	lang_info_t	*list = *return_list;

	/*
	 * For Chinese we have to handle it specially. There is Traditional
	 * Chinese or Simplified Chinese. Everything else is a locale.
	 */
	sub = substitute_language(lang, &code);

	if (sub != NULL) {
		tmp_lang = strdup(sub);
		if (tmp_lang == NULL)
			goto error;
	}

	if (locale == NULL)
		locale = dgettext(TEXT_DOMAIN, lang);

	new = (lang_info_t *)malloc(sizeof (lang_info_t));
	if (new == NULL)
		goto error;

	(void) memset(new, 0, sizeof (lang_info_t));

	new->lang = (code != NULL) ? strdup(code): strdup(lang);
	if (new->lang == NULL)
		goto error;

	if (tmp_lang != NULL) {
		trans_lang = &tmp_lang;
	} else
		trans_lang = get_actual_languages(&new->lang, &total);

	/*
	 * We look for the lang name in our list of iso approved language
	 * translations. If not found, then it isn't a language so
	 * we don't create an entry for it.
	 */

	if (trans_lang != NULL && *trans_lang != NULL) {
		new->lang_name  = *trans_lang;
	} else {
		om_set_error(OM_NOT_LANG);
		goto error;
	}

	new->def_lang = locale_in_installer_lang;

	if (locale != NULL) {
		lp = (locale_info_t *)malloc(sizeof (locale_info_t));
		if (lp == NULL) {
			om_set_error(OM_NO_SPACE);
			goto error;
		}
		(void) memset(lp, 0, sizeof (locale_info_t));

		lp->locale_name = strdup(locale);
		if (lp->locale_name == NULL) {
			om_set_error(OM_NO_SPACE);
			goto error;
		}

		desc = get_locale_description(new->lang_name, region);
		lp->locale_desc = desc;
		new->locale_info = lp;
		new->locale_info->def_locale = locale_app_locale;
		new->n_locales++;
	}
	if (list != NULL) {
		for (tmp = list, last = NULL; tmp != NULL;
		    last = tmp, tmp = tmp->next) {
			/* Everything is after English */
			if (strcmp(tmp->lang, dgettext(TEXT_DOMAIN,
			    "English")) == 0) {
				break;
			}
			if (strcmp(tmp->lang, lang) > 0) {
				break;
			}
		}
		if (tmp == list) {
			new->next = list;
			list = new;
		} else {
			last->next = new;
			new->next = tmp;
		}
	} else {
		list = new;
	}

	*(return_list) = list;
	return (OM_SUCCESS);

error:
	om_free_lang_info(new);
	om_free_locale_info(lp);
	return (OM_FAILURE);

}
/*
 * Function
 *		get_lang_entry
 *
 * Description
 *		Get the language/locale list node which uses
 *		the specified language
 *
 * Scope
 *		Private
 *
 * Parameters
 *		lang - language to search for
 *
 * Return
 *		a pointer to the correct lang/locale node or NULL
 *
 */
static lang_info_t *
get_lang_entry(char *lang_name, lang_info_t *search_list)
{
	lang_info_t 	*list = NULL;
	char		*sub = NULL;
	char		*code = NULL;
	boolean_t	found = B_FALSE;

	if (lang_name == NULL)
		return (NULL);
	/*
	 * Chinese language names are stored differently.
	 */

	sub = substitute_language(lang_name, &code);

	for (list = search_list; list != NULL; list = list->next) {
		if (code) {
			if (strcmp(list->lang, code) == 0) {
				found = B_TRUE;
				break;
			}
		} else {
			if (strcmp(list->lang, lang_name) == 0) {
				found = B_TRUE;
				break;
			}
		}
	}

	if (!found)
		return (NULL);
	return (list);
}

/*
 * Function
 *		add_locale_entry_to_lang
 *
 * Description
 *		Add an additional locale to the list of
 *		locales that use lang.
 *
 * Scope
 *		Private
 *
 * Parameters
 *		langp - pointer to the lang/locale node to add locale to
 *		locale - locale which uses lang
 *
 * Return
 *		none
 *
 */
static void
add_locale_entry_to_lang(lang_info_t *langp, char *locale_name, char *region,
    boolean_t is_default)
{
	char		*desc = NULL;
	locale_info_t 	*locp = NULL;
	locale_info_t	*tmp = NULL;

	tmp = langp->locale_info;

	/*
	 * Check for previous inclusion of this locale entry.
	 */

	while (tmp != NULL) {
		if (strcmp(tmp->locale_name, locale_name) == 0)
			return;
		tmp = tmp->next;
	}
	/*
	 * Allocate space for new entry.
	 */
	locp = (locale_info_t *)malloc(sizeof (locale_info_t));
	if (locp == NULL) {
		om_set_error(OM_NO_SPACE);
		return;
	}
	(void) memset(locp, 0, sizeof (locale_info_t));

	locp->locale_name = strdup(locale_name);
	if (locp->locale_name == NULL) {
		om_set_error(OM_NO_SPACE);
		om_free_locale_info(locp);
		return;
	}

	desc = get_locale_description(langp->lang_name, region);
	locp->locale_desc = desc;
	locp->def_locale = is_default;

	tmp = langp->locale_info;
	while (tmp->next != NULL) {
		tmp = tmp->next;
	}
	tmp->next = locp;
	langp->n_locales++;
}

static void
build_install_ll_list(char *nlspath, char **install_list, int lang_total,
    lang_info_t **return_list, int *ll_total)
{
	char 		path[MAXPATHLEN];
	char		trans[MAX_LOCALE + 1];
	char 		linebuf[128];
	FILE		*fp;
	char		*c, *c2;
	int		i, ret = 0;
	lang_info_t	*lp;
	locale_info_t	*locp = NULL;
	int		num_entries = 0;
	boolean_t	is_default = B_FALSE;
	char		*start = NULL, *t = NULL, *lang = NULL;
	char		*region = NULL, *encoding = NULL;

	*return_list = NULL;

	if (install_list == NULL || *install_list == NULL) {
		om_set_error(OM_INVALID_LANG_LIST);
		return;
	}

	(void) memset(trans, 0, sizeof (trans));
	/*
	 * For the installer application supported languages we only
	 * want the non-UTF-8 codeset. Why? Because there is not full
	 * locale support for UTF-8 in the miniroot.
	 */
	for (i = 0; i < lang_total && install_list[i] != NULL; i++) {
		start = install_list[i];
		lang = get_locale_component(&t, &start);

		if (start && *t == COUNTRY_SEP)
			region = get_locale_component(&t, &start);

		if (start && *t == CODESET_SEP)
			encoding = get_locale_component(&t, &start);

		if (encoding != NULL) {
			if (strcmp(encoding, UTF) == 0) {
				free(encoding);
				free(region);
				free(lang);
				encoding = NULL;
				region = NULL;
				lang = NULL;
				continue;
			}
		}

		if (strncmp(lang, "zh", 2) == 0) {
			if (region != NULL && strcmp(region, "TW") == 0) {
				om_errno = handle_chinese_language(region,
				    &lang);
				if (om_errno != OM_SUCCESS) {
					goto error;
				}
			}
		} else if (strcmp(lang, "C") == 0 ||
		    strcmp(lang, "POSIX") == 0 ||
		    strcmp(lang, "C/POSIX") == 0) {
			free(lang);
			lang = strdup("en");
			is_default = B_TRUE;
			if (lang == NULL) {
				om_set_error(OM_NO_SPACE);
				goto error;
			}
		}

		if ((lp = get_lang_entry(lang, *return_list)) != NULL) {
			continue;
		} else {
			ret = create_lang_entry(install_list[i],
			    install_list[i], region, return_list, is_default, is_default);
			if (!ret)
				num_entries++;
		}
		free(lang);
		free(region);
		free(encoding);
		lang = NULL;
		region = NULL;
		encoding = NULL;
		is_default = B_FALSE;
	}

	/*
	 * For the install application language specifications, which
	 * are located at /usr/lib/install/data/lib/locale, we need
	 * to ensure we have an up to date locale/lang name for
	 * translation. The lcttab file in /usr/lib/locale provides
	 * the correct mapping.
	 */
	lp = *return_list;
	(void) snprintf(path, sizeof (path), "%s/lcttab", nlspath);
	if ((fp = fopen(path, "r"))) {
		for (i = 0; lp != NULL; lp = lp->next) {
			locp = lp->locale_info;
			rewind(fp);
			while (fgets(linebuf, 128, fp)) {
				if (strlen(linebuf) == 0 ||
				    linebuf[0] == '#') {
					continue;
				}
				/* Search for whitespace */
				for (c = linebuf; *c && !isspace(*c); c++)
					;

				if (*c != '\0') {
					/* End of line - invalid input */
					continue;
				}
				*c = '\0';
				if (strcmp(linebuf, locp->locale_name) != 0) {
					continue;
				}

				/* Found the old name - get the new version */
				for (c++; *c && isspace(*c); c++)
					;

				if (!*c) {
					continue;
				}
				for (c2 = c; *c2 && !isspace(*c2); c2++)
					;

				*c2 = '\0';
				/*
				 * We are not interested in UTF-8
				 * codesets for now.
				 */
				if (strstr(c, UTF) != NULL)
					continue;
				(void) strcpy(trans, c);
				break;
			} /* end while */

			/*
			 * We may have not found a match in the lcttab file.
			 * If not, copy the original locale data in and
			 * search for locale_map.
			 */
			if (trans[0] == '\0')
				(void) strcpy(trans, locp->locale_name);

			locp = (locale_info_t *)malloc(sizeof (locale_info_t));
			if (locp == NULL) {
				om_set_error(OM_NO_SPACE);
				goto error;
			}
			(void) memset(locp, 0, sizeof (locale_info_t));
			locp->locale_name = strdup(trans);
			if (locp->locale_name == NULL) {
				om_free_locale_info(locp);
				om_set_error(OM_NO_SPACE);
				goto error;
			}
			(void) memset(trans, 0, sizeof (trans));
			/*
			 * free the original lang_info_t->locale_info
			 * data.
			 */
			om_free_locale_info(lp->locale_info);
			lp->locale_info = locp;
			lp->n_locales++;
		} /* end for */
	} /* end if */

	/*
	 * Now, translate language names, in this order, in to native
	 * locale based on current locale data associated with this language.
	 */
	translate_lang_names(return_list);
	*ll_total = num_entries;
	(void) fclose(fp);
	return;

error:
	(void) fclose(fp);
	om_free_lang_info(*return_list);
	*return_list = NULL;
	*ll_total = 0;
	free(lang);
	free(region);
	free(encoding);
	free(start);
}

static void
build_ll_list(char **list, int lang_total, lang_info_t **return_list,
    int *total)
{
	int		i;
	int		ret = 0;
	int		num_langs = 0;
	char		*lang = NULL, *encoding = NULL, *region = NULL;
	char		*locale = NULL;
	lang_info_t	*lp = NULL;
	char		*orig, *start = NULL;
	char		*t = NULL;
	boolean_t	locale_app_locale = B_FALSE;
	boolean_t	locale_in_installer_lang = B_FALSE;

	*total = 0;

	/*
	 * lang_list passed in is a sorted list of the data found in
	 * the locale directory. Take this sorted list,
	 * parse appropriately, and insert locale data for each language
	 * in to the return_list.
	 */

	for (i = 0; i < lang_total; i++)  {
		orig = start = list[i];
		if (!is_valid_locale(list[i]))
			continue;

		t = NULL;
		lang = get_locale_component(&t, &start);

		/*
		 * Valid locale must contain country information.
		 * The lang value is the language part of
		 * the lang/locale pair. What was in the original list
		 * is the locale.
		 */
		if (start && *t == COUNTRY_SEP) {
			region = get_locale_component(&t, &start);
		} else {
			free(lang);
			lang = NULL;
			continue;
		}

		if (start && *t == CODESET_SEP) {
			encoding = get_locale_component(&t, &start);
		}

		if (strncmp(lang, "zh", 2) == 0) {
			/*
			 * If there is a region with the Chinese lang,
			 * we need to ensure that it is not its own language.
			 * Chinese specifications for language include
			 * the region, such as zh_HK and zh_TW.
			 * If no region is found, then lang is simply lang
			 * from above.
			 */
			if (region) {
				om_errno = handle_chinese_language(region,
				    &lang);
				if (om_errno != OM_SUCCESS) {
					goto error;
				}
			} else {
				/*
				 * We need to account for Simplified Chinese,
				 * EUC in the locale list. Its locale name
				 * does not include a region.
				 */
				locale = strdup(lang);
				if (locale == NULL) {
					om_set_error(OM_NO_SPACE);
					goto error;
				}
			}
		} else if (strcmp(lang, "C") == 0 ||
		    strcmp(lang, "POSIX") == 0 ||
		    strcmp(lang, "C/POSIX") == 0) {
			free(lang);
			lang = strdup("en");
			if (lang == NULL) {
				om_set_error(OM_NO_SPACE);
				goto error;
			}
			locale = strdup(lang);
			if (locale == NULL) {
				om_set_error(OM_NO_SPACE);
				goto error;
			}
		}
		/*
		 * Locale is a combination of  lang, country and codeset.
		 */
		if (encoding != NULL) {
			locale = strdup(orig);
			if (locale == NULL) {
				om_set_error(OM_NO_SPACE);
				goto error;
			}
		}

		/*
		 * If we don't have the locale value, we haven't found
		 * anything we are interested in, so skip.
		 */
		if (locale != NULL)  {
			locale_in_installer_lang = is_locale_in_installer_lang(locale);
			locale_app_locale = is_locale_app_locale(locale);
			
			om_debug_print(OM_DBGLVL_INFO, "Adding locale: "
			    "locale=%s,lang=%s,region=%s\n", locale,
			    lang == NULL ? "#" : lang,
			    region == NULL ? "#" : region);

			if ((lp = get_lang_entry(lang, *return_list)) != NULL) {
				add_locale_entry_to_lang(lp, locale, region,
				    locale_app_locale);
			} else {
				ret = create_lang_entry(lang, locale, region,
				    return_list, locale_app_locale, locale_in_installer_lang);
				if (!ret) {
					num_langs++;
					om_debug_print(OM_DBGLVL_INFO,
					    "num_langs = %d\n", num_langs);
				}
			}
		}
		free(region);
		free(encoding);
		free(lang);
		free(locale);
		region = NULL;
		encoding = NULL;
		lang = NULL;
		locale = NULL;
	}
	*total = num_langs;
	return;
error:
	om_free_lang_info(*return_list);
	*return_list = NULL;
	free(region);
	free(encoding);
	free(lang);
	free(locale);
}

/*
 * build_language_list:
 *
 *	The idea is to scan the directories under "path" and
 *	build the language list, char ** list, associated with
 *	the "path".
 */
static int
build_language_list(char *path, char **list, int *total)
{
	DIR		*locale_dir;
	struct dirent	*locale;		/* entries in locale_dir */
	int		i = 0;

	/*
	 * Read in language data from the locale directory.
	 */
	(void) memset(list, 0, sizeof (*list));
	locale_dir = opendir(path);
	if (locale_dir == NULL) {
		if (errno == EACCES) {
			om_set_error(OM_PERMS);
		} else if (errno != EMFILE && errno != ENFILE) {
			om_set_error(OM_NO_LOCALE_DIR);
		} else {
			om_set_error(OM_TOO_MANY_FD);
		}
		goto error;
	}

	while (locale = readdir(locale_dir)) {
		/*
		 * Exclude current and parent directory. Make sure
		 * we are not over our buffer limit.
		 */
		if (strcmp(locale->d_name, ".") == 0 ||
		    strcmp(locale->d_name, "..") == 0)
			continue;

		list[i] = strdup(locale->d_name);
		if (list[i] == NULL) {
			om_set_error(OM_NO_SPACE);
			goto error;
		}
		i++;
	}
	*total = i;
	(void) closedir(locale_dir);
	return (OM_SUCCESS);

error:
	om_free_lang_names(list);
	*list = NULL;
	(void) closedir(locale_dir);
	return (OM_FAILURE);
}
/*
 * This function reads a locales locale_map file to get the settings
 * that should be used for localization.
 *
 * Input: File *fp  File pointer to locale_map file
 * Output: Each type of locale category value is returned.
 */
int
read_locale_file(FILE *fp, char *lang, char *lc_collate, char *lc_ctype,
	char *lc_messages, char *lc_monetary, char *lc_numeric, char *lc_time)
{
	int status = 0;
	char line[BUFSIZ];

	(void) strcpy(lc_collate, "C");
	(void) strcpy(lc_ctype, "C");
	(void) strcpy(lc_messages, "C");
	(void) strcpy(lc_monetary, "C");
	(void) strcpy(lc_numeric, "C");
	(void) strcpy(lc_time, "C");

	while (fgets(line, BUFSIZ, fp) != NULL) {
		/*
		 * Remove the trailing newline, and strip any comments that
		 * may appear on the read line.
		 */
		line[strlen(line) - 1] = '\0';
		(void) strip_comment(line);

		if (strncmp(STR_LANG, line, LEN_LANG) == 0) {
			(void) strcpy(lang, line + LEN_LANG);
			status = 1;
		} else if (strncmp(STR_LC_COLLATE, line, LEN_LC_COLLATE) == 0) {
			(void) strcpy(lc_collate, line + LEN_LC_COLLATE);
			status = 2;
		} else if (strncmp(STR_LC_CTYPE, line, LEN_LC_CTYPE) == 0) {
			(void) strcpy(lc_ctype, line + LEN_LC_CTYPE);
			status = 2;
		} else if (strncmp(STR_LC_MESSAGES, line, LEN_LC_MESSAGES)
		    == 0) {
			(void) strcpy(lc_messages, line + LEN_LC_MESSAGES);
			status = 2;
		} else if (strncmp(STR_LC_MONETARY, line, LEN_LC_MONETARY)
		    == 0) {
			(void) strcpy(lc_monetary, line + LEN_LC_MONETARY);
			status = 2;
		} else if (strncmp(STR_LC_NUMERIC, line, LEN_LC_NUMERIC) == 0) {
			(void) strcpy(lc_numeric, line + LEN_LC_NUMERIC);
			status = 2;
		} else if (strncmp(STR_LC_TIME, line, LEN_LC_TIME) == 0) {
			(void) strcpy(lc_time, line + LEN_LC_TIME);
			status = 2;
		}
	}

	if (status == 1) {
		/*
		 * There's a LANG, but nothing else, so populate all of the
		 * fields with the value put in LANG
		 */
		(void) strcpy(lc_collate, lang);
		(void) strcpy(lc_ctype, lang);
		(void) strcpy(lc_messages, lang);
		(void) strcpy(lc_monetary, lang);
		(void) strcpy(lc_numeric, lang);
		(void) strcpy(lc_time, lang);
	}
	return (status);
}

/*
 * Function:	strip_comment
 * Description:	Given a string of the form 'foo # comment', strip the comment
 *		text, the comment marker, and the whitespace (if any) preceding
 *		it.  This modification is done in-place on the passed in string.
 * Scope:	private
 * Arguments:	buf	- [RO, *RW] (char *)
 *			  The buffer from which the comment is to be stripped.
 * Returns:	char *	- buf, the pointer passed in
 */
static char *
strip_comment(char *buf)
{
	char *comchr;

	if (buf == NULL || (comchr = strchr(buf, '#')) == NULL)
		return (buf);

	for (; comchr != buf && isspace(*(comchr - 1)); comchr--)
		;
	*comchr = '\0';
	return (buf);
}
static void
set_lang(char *locale)
{
	static char	tmpstr[MAX_LOCALE + 6];

	(void) setlocale(LC_ALL, locale);
	(void) snprintf(tmpstr, sizeof (tmpstr), "LANG=%s", locale);
	(void) putenv(tmpstr);
}

static void
set_lc(char *lc_collate, char *lc_ctype, char *lc_messages, char *lc_monetary,
	char *lc_numeric, char *lc_time)
{

	/*
	 * The longest addition to a locale value is LC_MESSAGES=. This
	 * plus the NULL value is 14 chars. Added 15 for padding as
	 * a result.
	 */
	static char	tmpstr1[MAX_LOCALE + 15];
	static char	tmpstr2[MAX_LOCALE + 15];
	static char	tmpstr3[MAX_LOCALE + 15];
	static char	tmpstr4[MAX_LOCALE + 15];
	static char	tmpstr5[MAX_LOCALE + 15];
	static char	tmpstr6[MAX_LOCALE + 15];
	char		*loc = NULL;

	loc = setlocale(LC_COLLATE, lc_collate);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO, "lc_collate set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_collate value\n");

	(void) snprintf(tmpstr1, sizeof (tmpstr1), "LC_COLLATE=%s", lc_collate);
	(void) putenv(tmpstr1);

	loc = setlocale(LC_CTYPE, lc_ctype);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO,
		    "lc_ctype set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_ctype value\n");
	(void) snprintf(tmpstr2, sizeof (tmpstr2), "LC_CTYPE=%s", lc_ctype);
	(void) putenv(tmpstr2);

	loc = setlocale(LC_MESSAGES, lc_messages);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO,
		    "lc_messages set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_messages value\n");
	(void) snprintf(tmpstr3, sizeof (tmpstr3),
	    "LC_MESSAGES=%s", lc_messages);
	(void) putenv(tmpstr3);

	loc =  setlocale(LC_MONETARY, lc_monetary);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO,
		    "lc_monetary set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_monetary value\n");
	(void) snprintf(tmpstr4, sizeof (tmpstr4),
	    "LC_MONETARY=%s", lc_monetary);
	(void) putenv(tmpstr4);

	loc = setlocale(LC_NUMERIC, lc_numeric);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO,
		    "lc_numeric set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_numeric value\n");
	(void) snprintf(tmpstr5, sizeof (tmpstr5), "LC_NUMERIC=%s", lc_numeric);
	(void) putenv(tmpstr5);

	loc = setlocale(LC_TIME, lc_time);
	if (loc)
		om_debug_print(OM_DBGLVL_INFO,
		    "lc_time set to %s\n", loc);
	else
		om_debug_print(OM_DBGLVL_WARN,
		    "Could not set lc_time value\n");
	(void) snprintf(tmpstr6, sizeof (tmpstr6), "LC_TIME=%s", lc_time);
	(void) putenv(tmpstr6);
}

/*
 * Name:	get_locale_description
 * Description:	Read the locale_description file for a given locale, returning
 *		a pointer to a buffer containing the contents of that
 *		file.
 * Scope:	private
 * Arguments:	locale	- [RO, *RO] (char *)
 *			  The locale whose locale_description is to be read
 * Returns:	char *	- The first line of the locale_description
 */
static char *
get_locale_description(char *lang, char *region)
{
	char	*user_desc;

	/*
	 * Chinese and Korean are handled differently. This is due to
	 * the locale description for each of these being different than
	 * the standard.
	 */

	if (region == NULL) {
		if (strcmp(lang, dgettext(TEXT_DOMAIN, TRADITIONAL_CHINESE))
		    == 0 ||
		    strcmp(lang, dgettext(TEXT_DOMAIN, SIMPLIFIED_CHINESE))
		    == 0) {
			region = strdup("zh");
		} else if (strcmp(lang, dgettext(TEXT_DOMAIN, "Korean")) == 0) {
			region = strdup("ko");
		}
	}
	user_desc = translate_description(lang, region);
	return (user_desc);
}

static char *
translate_description(char *lang, char *region)
{
	char 		*trans_desc = NULL;
	int		len = 0, i;
	int		szcountry = sizeof (orchestrator_country_list) /
	    sizeof (orchestrator_country_list[0]);

	char		*tmp_ctrystring = NULL;

	if (lang == NULL || region == NULL) {
		return (NULL);
	}

	for (i = 0; i < szcountry; i++) {
		/*
		 * Translate the country code for this locale.
		 */
		if (strncasecmp(region,
		    orchestrator_country_list[i].country_code, 2) == 0) {
			tmp_ctrystring =
			    dgettext(TEXT_DOMAIN,
			    orchestrator_country_list[i].country_name);
			break;
		}
	}
	if (tmp_ctrystring) {
		len = strlen(lang) + strlen(tmp_ctrystring) + 4;
		trans_desc = (char *)malloc(len);
		if (trans_desc == NULL)
			return (NULL);
		(void) snprintf(trans_desc, len, "%s (%s)",
		    lang, tmp_ctrystring);
	}
	return (trans_desc);
}

static char **
get_actual_languages(char **list, int *total)
{
	char	**lp;
	char	**lang_listp = NULL;
	size_t	sz;
	int	ret = 0;
	int	i, j, k = 0;


	*total = 0;

	if (list == NULL || *list == NULL)
		return (NULL);

	sz = sizeof (orchestrator_lang_list)/sizeof (orchestrator_lang_list[0]);

	lp = list;
	for (i = 0; lp[i] != '\0'; i++) {
		for (j = 0; j < sz; j++) {
			if (strncmp(lp[i],
			    (char *)orchestrator_lang_list[j].lang_code,
			    2) == 0) {
				ret = add_lang_to_list(&lang_listp,
				    lp[i], &k, j);
				if (ret) {
					om_free_lang_names(lang_listp);
					return (NULL);
				}
				break;
			}
		}
	}
	/*
	 * No lang translation found. Return existing list.
	 */
	if (j == sz) {
		return (lang_listp);
	}
	*total = k;
	om_set_error(OM_SUCCESS);
	return (lang_listp);
}

static int
add_lang_to_list(char ***list, char *locale, int *k, int j)
{
	int	i;
	char	**lpp = *list;
	char	**tmp_list;
	char	*tmp = NULL;
	char	*sub = NULL;
	char	*code;

	tmp_list = *list;

	sub = substitute_language(locale, &code);

	if (sub != NULL) {
		tmp = strdup(sub);
	} else {
		tmp = strdup(dgettext(TEXT_DOMAIN,
		    orchestrator_lang_list[j].lang_name));
	}

	if (tmp == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}

	if (tmp_list != NULL) {
		/*
		 * Search for existence of this language in the list already
		 */
		for (i = 0; tmp_list[i] != NULL && tmp_list[i] != '\0' &&
		    i < *k; i++) {
			if (strcmp(tmp, tmp_list[i]) == 0) {
				free(tmp);
				return (OM_SUCCESS);
			}
		}
	}
	tmp_list = (char **)realloc(*list, ((*k) + 1) * sizeof (char *));
	if (tmp_list == NULL) {
		free(tmp);
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	lpp = *list = tmp_list;
	lpp[*k] = tmp;
	(*k)++;
	return (OM_SUCCESS);
}

static boolean_t
is_valid_locale(char *locale)
{

	char	path[MAXPATHLEN];
	struct	stat stat_buf;

	if (locale == NULL)
		return (B_FALSE);

	if (strstr(locale, UTF) == NULL)
		return (B_FALSE);

	(void) snprintf(path, sizeof (path), "%s/%s/LC_COLLATE/LCL_DATA",
	    NLS_PATH, locale);
	if ((stat(path, &stat_buf) == 0) &&
	    ((stat_buf.st_mode & S_IFMT) == S_IFREG)) {
		return (B_TRUE);
	}
	return (B_FALSE);
}

static char *
substitute_C_POSIX_language(char **code)
{
	char	*lang = NULL;

	/*
	 * locale is C and or POSIX. Set to English, set code
	 * to 'en'.
	 */
	lang = dgettext(TEXT_DOMAIN, "English");
	*code = "en";
	return (lang);
}

static char *
substitute_chinese_language(char *locale, char **code)
{
	int 		i;
	int		len;
	char		*sub = NULL;

	for (i = 0; chinese_values[i].lang != NULL; i++) {
		len = strlen(chinese_values[i].lang);
		if ((strncmp(locale,  chinese_values[i].lang, len) == 0) &&
		    (locale[len] == '\0' || locale[len] == '.')) {
			sub =
			    dgettext(TEXT_DOMAIN, chinese_values[i].lang_name);
			*code = chinese_values[i].lang_code;
			return (sub);
		}
	}

	om_set_error(OM_INVALID_LOCALE);
	return (sub);
}

static char *
substitute_language(char *locale, char **code)
{
	char *lang = NULL;

	if (strncmp(locale, "zh", 2) == 0) {
		lang = substitute_chinese_language(locale, code);
		if (lang == NULL)
			goto error;
	} else if (strcmp(locale, "C") == 0 || strcmp(locale, "POSIX") == 0) {
		lang = substitute_C_POSIX_language(code);
	}

error:
	return (lang);
}

static void
sort_lang_list(char **unsorted_list, int total)
{
	qsort((char **)unsorted_list, total, sizeof (char *), list_cmp);
}

static int
handle_chinese_language(char *region, char **lang)
{
	int	len;
	char	*chinese_lang;


	len = strlen(*lang) + strlen(region) + 3;
	chinese_lang = (char *)malloc(len);
	/*
	 * If we cannot allocate new language data, return error, but
	 * don't modify language value. Allow caller to determine what
	 * to do.
	 */
	if (chinese_lang == NULL) {
		om_set_error(OM_NO_SPACE);
		return (OM_FAILURE);
	}
	(void) snprintf(chinese_lang, len, "%s%s%s", *lang, "_", region);
	free(*lang);
	*lang = chinese_lang;
	return (OM_SUCCESS);
}
static int
list_cmp(const void *p1, const void *p2)
{
	return (strcmp(*(char **)p1, *(char **)p2));

}
/*
 * This function gets each of the locale components. It does so
 * by looking for each component of a locale, as noted above as defines.
 * It returns each segment in t, or NULL if no additional component is found.
 */
static char *
get_locale_component(char **t, char **start)
{
	char	*result = NULL;

	end_of_comp(t, start);
	result = copy_up_to(*start, *t);
	*start = (**t != '\0') ? *t + 1: NULL;
	return (result);
}

/*
 * This function looks for each component of the locale string passed in
 * in the 'start' parameter. If it finds one it returns a pointer to that
 * component. Or NULL if not found.
 */
static void
end_of_comp(char **t, char **start)
{
	(((*t) = strchr((*start), COUNTRY_SEP)) != NULL) ||
	    (((*t) = strchr((*start), CODESET_SEP)) != NULL) ||
	/*LINTED*/
	    (((*t) = strchr((*start), '\0')) != NULL);
}

static char *
copy_up_to(char *start, char *end)
{
	/*
	 * XXX look at this.
	 */

	ptrdiff_t	diff;
	char		*sub = NULL;

	if (end == NULL) {
		diff = strlen(start);
	} else {
		/*LINTED*/
		diff = end - start;
	}
	sub = (char *)malloc(diff + 1);
	(void) memset(sub, 0, diff + 1);
	(void) strlcpy(sub, start, (diff + 1));
	return (sub);
}

/* This method checks to see if the locale passed in as an argument
 * is in the same language as the application.
 */
static boolean_t
is_locale_in_installer_lang(char *locale_name)
{
	if (app_locale == NULL) {
		app_locale = strdup(setlocale(LC_MESSAGES, NULL));
	}

	if (app_locale != NULL) {
		if (strcmp(locale_name, app_locale) == 0) {
			/* locale name is same */
			return (B_TRUE);
		} else if (strncmp(locale_name, app_locale, 2) == 0) {
			/* language part is same */
			if ((strncmp(locale_name, "zh_TW", 5) == 0) ||
			    (strncmp(locale_name, "zh_HK", 5) == 0)) {
				/* traditional Chinese */
				if ((strncmp(app_locale, "zh_TW", 5) == 0) ||
				    (strncmp(app_locale, "zh_HK", 5) == 0)) {
					return (B_TRUE);
				}
			} else if (strncmp(locale_name, "zh", 2) == 0) {
				/* simplified Chinese */
				if ((strncmp(app_locale, "zh_TW", 5) != 0) &&
				    (strncmp(app_locale, "zh_HK", 5) != 0)) {
					return (B_TRUE);
				}
			} else {
				/* others */
				return (B_TRUE);
			}
		} else if (strncmp(locale_name, "en", 2) == 0) {
			/* English */
			if (strcmp(app_locale, "C") == 0) {
				return (B_TRUE);
			}
		}
	}

	return (B_FALSE);
}

/*
 * This method checks to see if the currently used locale is the same
 * as the locale passed as an argument. We do this by comparing
 * app_locale to locale_name.
 */
static boolean_t
is_locale_app_locale(char *locale_name)
{
	if (app_locale == NULL) {
		app_locale = strdup(setlocale(LC_MESSAGES, NULL));
	}

	if (app_locale != NULL) {
		if (strcmp(locale_name, app_locale) == 0) {
			/* locale name is same */
			return (B_TRUE);
		} 
	}

	return (B_FALSE);
}

void
om_save_locale(char *locale, boolean_t install_only)
{
	FILE 	*fp, *tfp;
	char	line[BUFSIZ];
	char	tfile[80];
	char	target[MAXPATHLEN];

	/*
	 * If this is only setting the installation app locale we don't
	 * want to modify the users /etc/default/init file just yet. That
	 * will happen later.
	 */

	if (install_only) {
		update_env(locale);
	}

	(void) sprintf(tfile, "/tmp/orchlocale%ld", getpid());
	(void) snprintf(target, sizeof (target), "%s%s", INSTALLED_ROOT_DIR,
	    INIT_FILE);

	if ((tfp = fopen(tfile, "w")) == NULL)
		return;

	if ((fp = fopen(target, "r")) != NULL) {
		while (fgets(line, BUFSIZ, fp) != NULL) {
			if (strncmp("LANG=", line, 5) == 0)
				continue;
			if (strncmp("LC_", line, 3) == 0)
				continue;
			if (fputs(line, tfp) == EOF) {
				(void) fclose(fp);
				(void) fclose(tfp);
				return;
			}
		}
	}
	(void) fclose(fp);
	update_init(tfp, locale);
	(void) fclose(tfp);

	if ((fp = fopen(target, "w")) == NULL)
		return;

	if ((tfp = fopen(tfile, "r")) == NULL) {
		(void) fclose(fp);
		return;
	}

	while (fgets(line, BUFSIZ, tfp) != NULL)
		if (fputs(line, fp) == EOF)
			break;
	(void) fclose(fp);
	(void) fclose(tfp);
}

static void
update_env(char *locale)
{
	char path[MAXPATHLEN];
	char lc_collate[MAX_LOCALE];
	char lc_ctype[MAX_LOCALE];
	char lc_messages[MAX_LOCALE];
	char lc_monetary[MAX_LOCALE];
	char lc_numeric[MAX_LOCALE];
	char lc_time[MAX_LOCALE];
	char lang[MAX_LOCALE];
	FILE *mfp;
	int rc;

	(void) snprintf(path, sizeof (path), "%s/%s/LC_COLLATE/LCL_DATA",
	    NLS_PATH, locale);
	if ((mfp = fopen(path, "r")) == NULL) {
		set_lang(locale);
	} else {
		rc = read_locale_file(mfp, lang, lc_collate, lc_ctype,
		    lc_messages, lc_monetary, lc_numeric, lc_time);
		(void) fclose(mfp);

		if (rc == 1) {
			set_lang(lc_messages);
		} else {
			set_lc(lc_collate, lc_ctype, lc_messages, lc_monetary,
			    lc_numeric, lc_time);
		}
	}
}

static void
update_init(FILE *fp, char *locale)
{
	if (strcmp(locale, "C") != 0) {
		(void) fprintf(fp, "LANG=%s\n", locale);
	}
	set_lang(locale);
}

static void
translate_lang_names(lang_info_t **list)
{

	char		trans[512];
	lang_info_t	*langp;

	/*
	 * Set locale to en_US.UTF-8. It doesn't really matter
	 * what it is set to expect it cannot be C. dgettext does
	 * not pick up the translated strings if the current locale
	 * is C.
	 */
	set_lang("en_US.UTF-8");
	for (langp = *list; langp != NULL; langp = langp->next) {
		if (langp->lang_name != NULL) {
			(void) strcpy(trans,
			    dgettext("SUNW_INSTALL_LANG",
			    langp->lang_name));
			/*
			 * Free original lang name.
			 */
			free(langp->lang_name);
			langp->lang_name = strdup(trans);
			if (langp->lang_name == NULL) {
				/*
				 * Log a message. leave the other
				 * lang names untranslated.
				 * Otherwise, would have to free
				 * full list and provide
				 * the user with nothing.
				 */
				om_debug_print(OM_DBGLVL_ERR,
				    "Couldn't allocate memory"
				    " for translated lang name\n");
				return;
			}
		}
	}
}
