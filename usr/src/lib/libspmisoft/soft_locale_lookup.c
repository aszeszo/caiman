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

#pragma ident	"@(#)soft_locale_lookup.c	1.13	07/11/12 SMI"

/*
 *	File:		locale_lookup.c
 *
 *	Description:	This file contains the routines needed to prompt
 *			the user for the desired locale.
 */

#include <stdio.h>
#include <locale.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <dirent.h>
#include <ctype.h>
#include "spmisoft_lib.h"
#include "soft_locale.h"

extern char 	*boot_root;
extern struct locmap *global_locmap;

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

/* library function prototypes */
void	read_locale_table(Module *);
char	*get_locale_description(char *, char *);
void	update_init(FILE *, char *);
int	locale_is_multibyte(char *);
char	*get_system_locale_from_file(void);
int	read_locale_file(FILE *fp, char *, char *, char *,
					char *, char *, char *, char *);
void	trim(char *);

/* local function prototypes */
static void read_liblocale_directory(char *);
static char *read_locale_description_file(char *, char *);

/* static variables */
static char	s_locale_description[256];

/*
 * Finding one of these locales on an image means that the image has
 * multi-byte locales, which we can't support in the CUI.
 * We also have to play games with the UI to insure it gets the right
 * font set in the GUI.
 */
char *mb_locales[] = {"ja", "ja_JP.PCK", "ja_JP.UTF-8",
		"ko", "ko.UTF-8",
		"zh", "zh.GBK", "zh.UTF-8",
		"zh_TW", "zh_TW.BIG5", "zh_TW.UTF-8",
		"zh_HK.BIG5HK", "zh_HK.UTF-8", "zh_CN.GB18030",
		NULL};

/*
 * read_locale_table:
 *	returns 1 if locale should be determined, 0 if no need
 *
 *	The idea is to scan the directories under /usr/lib/locale
 *	for locales and categories that are in the proper arrangement,
 *	and create a menu of available locales for user selection.
 *	Only create the menu if non-default locale is found.
 *	The menu is used in case the user must be prompted.
 *	This should be called before prompt_locale().
 */

void
read_locale_table(Module *media)
{
	char		path[MAXPATHLEN];
	struct stat	statbuf;

	if (media->sub == NULL || media->sub->info.prod == NULL ||
	    media->sub->info.prod->p_pkgdir == NULL)
		return;
	/*
	 *  This next line is a temporary workaround for build 11.
	 *  By creating a symlink that allows this pathname to
	 *  be resolved, RE can make the build 11 CD build work (and
	 *  find the /usr/lib/locale directory.  Eventually, the
	 *  alternate location for the /usr/lib/locale directory needs
	 *  to be provided as an argument to buildtoc, which will then
	 *  provide it (somehow) to this function.  This function should
	 *  try the alternate location if provided, or should use
	 *  /usr/lib/locale.
	 */
	if (snprintf(path, sizeof (path), "%s/../Tools/Boot%s",
		media->sub->info.prod->p_pkgdir, NLSPATH) >= sizeof (path))
		return;
	if (lstat(path, &statbuf) || !S_ISDIR(statbuf.st_mode)) {
		(void) strncpy(path, NLSPATH, MAXPATHLEN);
		if (lstat(path, &statbuf) || !S_ISDIR(statbuf.st_mode))
			return;
	}

	read_liblocale_directory(path);

	read_geo_code_name_map(path);
}

/*
 * get_locale_description
 *
 * Get the English-language description of the locale specified
 * by the "locale" argument.  It is returned in English, since the
 * the English description is the message key used to translate the
 * string.
 *
 * The pointer returned is a pointer to static storage.  It is
 * expected that the caller will make a copy of the string, if
 * the string needs to be saved for later use.
 */
char	*
get_locale_description(char *root, char *locale)
{
	char	*cp;
	char	path[MAXPATHLEN];

	if (snprintf(path, sizeof (path), "%s%s", root, NLSPATH) <
							sizeof (path)) {
		if ((cp = read_locale_description_file(path, locale)) != NULL)
			return (cp);
	}
	return (get_lang_from_loc_array(locale));
}

static void
read_liblocale_directory(char *localedir)
{
	DIR		*locale_dirp;
	struct dirent	*locale;
	char		path[MAXPATHLEN];
	struct stat	statbuf;
	LocMap		*lmap;
	FILE		*fp;
	char		locstr[7][MAX_LOCALE];
	StringList	*str;
	int		i;
	char		*cp;
	Module		*prod;

	/*
	 * Loop thru all entries in the locale directory,
	 * checking for directories which contain locale
	 * subdirectories.  If there is at least one, then
	 * do the locale menu.
	 */
	locale_dirp = opendir(localedir);
	while (locale_dirp && (locale = readdir(locale_dirp))) {

		/* Obviously, exclude the current/parent directories */
		if (strcmp(locale->d_name, ".") == 0 ||
		    strcmp(locale->d_name, "..") == 0)
			continue;

		/* exclude the default locale */
		if (strcmp(locale->d_name, "C") == 0)
			continue;

		/* Is this entry a directory? */
		/*
		 * 11 is the length of "/locale_map"
		 * going to be appended later
		 */
		if (snprintf(path, sizeof (path), "%s/%s", localedir,
					locale->d_name) >= (sizeof (path) - 11))
			continue;
		if (lstat(path, &statbuf) || !S_ISDIR(statbuf.st_mode))
			continue;

		/* check for a locale_description */
		if ((cp = read_locale_description_file(localedir,
		    locale->d_name)) == NULL)
			continue;

		/*
		 * Fall thru if there's no geo info for 2.6
		 * or 2.7 locales which have no geo info
		 */
		prod = get_current_product();

		/* check for a geo_map */
		if (!(str = read_geo_map_file(localedir, locale->d_name)) &&
			prod->info.prod->p_version != NULL &&
			!(strneq(prod->info.prod->p_version, "2.7", 3) ||
			strneq(prod->info.prod->p_version, "2.6", 3))) {
			continue;
		}

		/* we have a valid locale description, add it to table */
		lmap = (LocMap *)xcalloc((size_t)sizeof (LocMap));
		lmap->locmap_partial = xstrdup(locale->d_name);
		lmap->locmap_description = xstrdup(cp);
		lmap->locmap_geo = str;

		/* now try to read a locale_map file */
		(void) snprintf(path, MAXPATHLEN, "%s/%s/%s", localedir,
			locale->d_name, LOCALE_MAP_FILE);

		if ((fp = fopen(path, "r")) == NULL) {
			errno = 0;
			link_to((Item **)&global_locmap, (Item *)lmap);
			continue;
		}

		for (i = 0; i < 7; i++)
			locstr[i][0] = '\0';

		(void) read_locale_file(fp, locstr[0], locstr[1], locstr[2],
		    locstr[3], locstr[4], locstr[5], locstr[6]);

		for (i = 0; i < 7; i++)
			if (locstr[i] != NULL && locstr[i][0] != '\0' &&
			    strcmp(locale->d_name, locstr[i]) != 0) {
				/* if locale is already on list, continue */
				for (str = lmap->locmap_base; str != NULL;
				    str = str->next)
					if (strcmp(str->string_ptr, locstr[i])
					    == 0)
						break;
				if (str)
					continue;

				/* locale isn't already on list.  Add it */
				str = (StringList *)xcalloc((size_t)
					sizeof (StringList));
				str->string_ptr = xstrdup(locstr[i]);
				link_to((Item **)&lmap->locmap_base,
				    (Item *)str);
				str = NULL;
			}

		fclose(fp);

		link_to((Item **)&global_locmap, (Item *)lmap);
	}

	/* Close locale directory */
	if (locale_dirp)
		(void) closedir(locale_dirp);
}

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

		trim(line);

		if (strlen(line) <= 0)
			continue;

		if (strneq(STR_LANG, line, LEN_LANG)) {
			(void) strcpy(lang, line + LEN_LANG);
			status = 1;
		} else if (strneq(STR_LC_COLLATE, line, LEN_LC_COLLATE)) {
			(void) strcpy(lc_collate, line + LEN_LC_COLLATE);
			status = 2;
		} else if (strneq(STR_LC_CTYPE, line, LEN_LC_CTYPE)) {
			(void) strcpy(lc_ctype, line + LEN_LC_CTYPE);
			status = 2;
		} else if (strneq(STR_LC_MESSAGES, line, LEN_LC_MESSAGES)) {
			(void) strcpy(lc_messages, line + LEN_LC_MESSAGES);
			status = 2;
		} else if (strneq(STR_LC_MONETARY, line, LEN_LC_MONETARY)) {
			(void) strcpy(lc_monetary, line + LEN_LC_MONETARY);
			status = 2;
		} else if (strneq(STR_LC_NUMERIC, line, LEN_LC_NUMERIC)) {
			(void) strcpy(lc_numeric, line + LEN_LC_NUMERIC);
			status = 2;
		} else if (strneq(STR_LC_TIME, line, LEN_LC_TIME)) {
			(void) strcpy(lc_time, line + LEN_LC_TIME);
			status = 2;
		}
	}

	return (status);
}

/*
 * read_locale_description_file
 *
 * read a locale_description file, if possible.  Return a pointer
 * to the locale description (untranslated) in a static buffer.
 */
static char *
read_locale_description_file(char *localedir, char *locale)
{
	char		path[MAXPATHLEN];
	char		buf[BUFSIZ+1];
	struct stat	statbuf;
	FILE		*fp;

	if (snprintf(path, sizeof (path), "%s/%s/%s", localedir,
			locale, LOCALE_DESC_FILE) >= sizeof (path))
		return (NULL);
	if (stat(path, &statbuf) || !S_ISREG(statbuf.st_mode) ||
	    (fp = fopen(path, "r")) == NULL) {
		errno = 0;
		return (NULL);
	}

	buf[0] = '\0';
	if (fgets(buf, BUFSIZ, fp) != NULL) {
		int l;

		l = strlen(buf) - 1;
		if (buf[l] == '\n')
			buf[l] = 0;
	}
	fclose(fp);

	if (strlen(buf) == 0 || (u_int) strlen(buf) > 256)
		return (NULL);

	(void) strcpy(s_locale_description, buf);

	return (s_locale_description);
}

/*
 * update_init
 *
 * Append to the etc/default/init file pointed to by "fp" with "locale".
 * The function will first check if this locale has a locale map,
 * and if so, it will use it to set the LC_* variables.  Otherwise
 * it will just set the LANG variable with the locale name.
 */
void
update_init(FILE *fp, char *locale)
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

	(void) snprintf(path, MAXPATHLEN, "%s/%s/locale_map",
		NLSPATH, locale);
	if ((mfp = fopen(path, "r")) == NULL) {
		if (!streq(locale, "C"))
			fprintf(fp, "%s%s\n", STR_LANG, locale);

	} else {
		rc = read_locale_file(mfp, lang, lc_collate, lc_ctype,
		    lc_messages, lc_monetary, lc_numeric, lc_time);
		fclose(mfp);

		if (rc == 1) {
			fprintf(fp, "%s%s\n", STR_LANG, lang);
		} else {
			fprintf(fp, "%s%s\n", STR_LC_COLLATE, lc_collate);
			fprintf(fp, "%s%s\n", STR_LC_CTYPE, lc_ctype);
			fprintf(fp, "%s%s\n", STR_LC_MESSAGES, lc_messages);
			fprintf(fp, "%s%s\n", STR_LC_MONETARY, lc_monetary);
			fprintf(fp, "%s%s\n", STR_LC_NUMERIC, lc_numeric);
			fprintf(fp, "%s%s\n", STR_LC_TIME, lc_time);
		}
	}
}

/*
 * Function:	locale_is_multibyte
 * Description:	Determine whether or not a given locale is a multibyte locale.
 *		This is primarily of interest because multibyte locales cannot
 *		be displayed in tty/curses mode.
 * Scope:	public
 * Arguments:	locale	- [RO, *RO] (char *)
 *			  The locale to be checked
 * Returns:	1	Multibyte locale
 *		0	Non-multibyte locale
 */
int
locale_is_multibyte(char *locale)
{
	int i;

	for (i = 0; mb_locales[i]; i++) {
		if (streq(locale, mb_locales[i])) {
			return (1);
		}
	}

	return (0);
}

/*
 * Function:	get_system_locale_from_file
 * Description:	Get the system locale from the /etc/default/init file.
 * Scope:	public
 * Arguments:	none
 * Returns:	locale - char pointer to system locale.
 *		NULL - if could not get system locale.
 */
char *
get_system_locale_from_file(void)
{
	FILE *fp;
	char lc_collate[MAX_LOCALE];
	char lc_ctype[MAX_LOCALE];
	char lc_messages[MAX_LOCALE];
	char lc_monetary[MAX_LOCALE];
	char lc_numeric[MAX_LOCALE];
	char lc_time[MAX_LOCALE];
	char lang[MAX_LOCALE];
	int rc;

	if ((fp = fopen(INIT_FILE, "r")) == NULL) {
		return (NULL);
	}

	rc = read_locale_file(fp, lang, lc_collate, lc_ctype,
		    lc_messages, lc_monetary, lc_numeric, lc_time);

	fclose(fp);

	if (rc == 1) {
		return (xstrdup(lang));
	} else {
		return (xstrdup(lc_ctype));
	}
}

/*
 * Name:	trim
 * Description: Trims whitespace from a string
 *		has been registered)
 * Scope:	private
 * Arguments:	string	- string to trim.  It is assumed
 *		this string is writable up to it's entire
 *		length.
 * Returns:	none
 */
void
trim(char *str)
{
	int len, i;
	if (str == NULL) {
		return;
	}

	len = strlen(str);
	/* strip from front */
	while (isspace(*str)) {
		for (i = 0; i < len; i++) {
			str[i] = str[i+1];
		}
	}

	/* strip from back */
	len = strlen(str);
	while (isspace(str[len-1])) {
		len--;
	}
	str[len] = '\0';
}
