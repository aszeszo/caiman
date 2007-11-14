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

#pragma ident	"@(#)om_kbd_locale_test.c	1.2	07/08/24 SMI"

#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "orchestrator_private.h"

static void dump_install_lang_info();
static void dump_install_languages();
static void dump_keyboard_types();
static void dump_lang_info();
static void dump_lang_names();
static void print_keyboards(keyboard_type_t *kp, int total);
static void set_install_lang_by_value(lang_info_t *lp);
static void set_keyboard_by_num(int type);
static void set_keyboard_by_value(keyboard_type_t *kbd);
static void set_keyboard_by_name(char *name);
static char *get_default_language(lang_info_t *lp);

int
main(int argc, char **argv)
{
	int 		opt;
	int		type;
	int		total;
	boolean_t	is_self;
	lang_info_t	*lp;
	int		i;
	char		*lang;

	while ((opt = getopt(argc, argv, "iIlLg:kc:n:S:t:xu:")) != EOF) {
		switch (opt) {
		case 'c':
			/*
			 * Scan in the number of the locale the
			 * caller wants to set.
			 */
			(void) sscanf(optarg, "%d", &type);
			/*
			 * First get lang info
			 */
			lp = om_get_install_lang_info(&total);
			for (i = 0; i < type && lp; i++)
				lp = lp->next;
			(void) fprintf(stderr,
			    "setting install app locale to %s\n",
			    lp->locale_info->locale_name);
			(void) set_install_lang_by_value(lp);
			dump_lang_info();
			break;
		case 'g':
			(void) sscanf(optarg, "%d", &type);
			lp = om_get_install_lang_info(&total);
			for (i = 0; i < type && lp; i++)
				lp = lp->next;
			(void) fprintf(stderr,
			    "setting install app locale to %s\n",
			    lp->locale_info->locale_name);
			(void) set_install_lang_by_value(lp);
			lp = om_get_lang_info(&total);
			lang = get_default_language(lp);
			(void) fprintf(stderr,
			    "Default language for user is %s\n", lang);
			break;
		case 'i':
			(void) dump_install_lang_info();
			break;
		case 'I':
			dump_install_languages();
			break;
		case 'l':
			dump_lang_info();
			break;
		case 'L':
			dump_lang_names();
			break;
		case 'k':
			dump_keyboard_types();
			break;
		case 'n':
			(void) sscanf(optarg, "%d", &type);
			set_keyboard_by_num(type);
			break;
		case 'S':
			set_keyboard_by_name(optarg);
			break;
		case 't':
			set_keyboard_by_value((keyboard_type_t *)optarg);
			break;
		case  'x':
			is_self = om_is_self_id_keyboard();
			(void) fprintf(stderr,
			    "Keyboard is %d self identifying\n", is_self);
			break;
		case	'u':
			set_user_name_password(optarg, optarg, NULL);
			break;
		default:
			(void) fprintf(stderr, "Need to provide option \n");
			break;
		}
	}
	exit(0);
}

static void
dump_install_lang_info()
{
	lang_info_t 	*lp = NULL;
	int		total;
	locale_info_t	*locp;
	int		i, j;

	lp = om_get_install_lang_info(&total);

	for (i = 0; lp != NULL && i < total; i ++) {
		(void) fprintf(stderr, "language: %s\n", lp->lang);
		if (lp->lang_name)
			(void) fprintf(stderr, "translated language name: %s\n",
			    lp->lang_name);
		(void) fprintf(stderr, "default language = %d\n", lp->def_lang);
		(void) fprintf(stderr, "locales for this language are: \n");
		locp = (locale_info_t *)lp->locale_info;
		for (j = 0; j < lp->n_locales && locp != NULL;
		    j ++) {
			(void) fprintf(stderr,
			    "locale_name: %s\n", locp->locale_name);
			if (locp->locale_desc) {
				(void) fprintf(stderr,
				    "locale_description: %s\n",
				    locp->locale_desc);
			} else {
				(void) fprintf(stderr,
					"locale_description is NULL\n");
			}
			(void) fprintf(stderr, "is default locale %d\n",
			    locp->def_locale);
			locp = locp->next;
		}
		lp = lp->next;
	}
}

static void
dump_keyboard_types()
{
	int total;
	keyboard_type_t *kp;

	kp = om_get_keyboard_types(&total);
	if (kp)
		print_keyboards(kp, total);
}

static void
set_keyboard_by_num(int type)
{
	int	error;
	FILE	*out;
	char	buf[BUFSIZE];
	keyboard_type_t *kp = NULL;
	int	total;

	/*
	 * get keyboard list first
	 */

	kp = om_get_keyboard_types(&total);
	if (kp == NULL) {
		(void) fprintf(stderr, "couldn't get keyboard list\n");
		return;
	}

	error = om_set_keyboard_by_num(type);
	if (!error) {
		out = popen("kbd -l", "r");
			if (out != NULL) {
				while (fgets(buf, BUFSIZE, out) != NULL) {
					(void) fprintf(stderr, "%s", buf);
			}
			(void) pclose(out);
		}
	} else {
		(void) fprintf(stderr, "Error setting kbd by num %d\n", error);
	}

}
static void
set_keyboard_by_name(char *name)
{
	int	error;
	FILE	*out;
	char	buf[BUFSIZE];

	error = om_set_keyboard_by_name(name);
	if (!error) {
		out = popen("kbd -l", "r");
			if (out != NULL) {
				while (fgets(buf, BUFSIZE, out) != NULL) {
					(void) fprintf(stderr, "%s", buf);
			}
			(void) pclose(out);
		}
	}
}
static void
set_keyboard_by_value(keyboard_type_t *kbd)
{
}

static void
print_keyboards(keyboard_type_t *kp, int total)
{
	keyboard_type_t *kpp;

	kpp = kp;
	while (kpp != NULL) {
		(void) fprintf(stderr, "keyboard name: %s, keyboard number %d,"
		    "default_keyboard %d\n",
		    kpp->kbd_name,
		    kpp->kbd_num,
		    kpp->is_default);
		kpp = kpp->next;
	}

}
static void
dump_lang_info()
{
	lang_info_t *lp;
	locale_info_t *locp;
	int	total = 0;
	int	i, j;
	lang_info_t  *ilp;

	ilp = om_get_install_lang_info(&total);
	lp = om_get_lang_info(&total);

	(void) fprintf(stderr, "total lang info found = %d\n", total);

	for (i = 0; lp != NULL && i < total; i ++) {
		(void) fprintf(stderr, "language: %s\n", lp->lang);
		if (lp->lang_name)
			(void) fprintf(stderr, "translated language name: %s\n",
			    lp->lang_name);
		(void) fprintf(stderr, "default language = %d\n", lp->def_lang);
		(void) fprintf(stderr, "locales for this language are: \n");
		locp = (locale_info_t *)lp->locale_info;
		(void) fprintf(stderr, "num locales = %d\n", lp->n_locales);
		for (j = 0; j < lp->n_locales && locp != NULL;
		    j ++) {
			(void) fprintf(stderr,
			    "locale_name: %s\n", locp->locale_name);
			if (locp->locale_desc)
				(void) fprintf(stderr,
				    "locale_description: %s\n",
				    locp->locale_desc);
			(void) fprintf(stderr, "is default locale %d\n",
			    locp->def_locale);
			locp = locp->next;
		}
		lp = lp->next;
	}
}

static void
dump_install_languages()
{
	char **langp;
	int	total;
	int	i;

	langp = om_get_install_lang_names(&total);
	(void) fprintf(stderr, "got install languages\n");

	for (i = 0; i < total; i ++) {
		if (langp[i] != NULL) {
			(void) fprintf(stderr,
			    "languages supported = %s\n", langp[i]);
		}
	}
}

static void
dump_lang_names()
{
	char **langp;
	int	total;
	int	i;

	langp = om_get_lang_names(&total);
	(void) fprintf(stderr,
	    "total from get supported languages: %d\n", total);

	for (i = 0; i < total; i ++) {
		if (langp[i] != NULL) {
			(void) fprintf(stderr,
			    "languages supported = %s\n", langp[i]);
		}
	}
}

static void
set_install_lang_by_value(lang_info_t *lp)
{
	int	error;
	error = om_set_install_lang_by_value(lp);
	(void) fprintf(stderr, "error for setting install lang = %d\n", error);
}

static char *
get_default_language(lang_info_t *lp)
{
	lang_info_t *langp;

	for (langp = lp; langp != NULL; langp = langp->next) {
		if (langp->def_lang == B_TRUE)
			return (langp->lang_name);
	}
	return (NULL);
}
