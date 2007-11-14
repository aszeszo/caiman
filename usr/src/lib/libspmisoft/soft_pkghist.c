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
#pragma ident	"@(#)soft_pkghist.c	1.14	07/11/09 SMI"
#endif

#include "spmisoft_lib.h"
#include <sys/wait.h>
#include <signal.h>
#include <dirent.h>
#include <fcntl.h>
#include <libgen.h>
#include <stdlib.h>
#include <ctype.h>
#include <string.h>
#include <libintl.h>
#include <locale.h>


struct s_histid {
	char *verlo;
	char *verhi;
	char *arch;
};

/* Local Statics and Constants */

#define	VER_LOW		1
#define	VER_HIGH	2

#define	ENTRY_BUF_SIZE	8192
#define	TOK_BUF_SIZE	256

static struct pkg_hist *pkg_history = NULL;
static struct pkg_hist *cls_history = NULL;
static char *		gtoksbuf;
static unsigned int	gtoksbuf_size;
static char *		glinebuf;
static int		BadHistoryRecord;	/* This record is bad */
static int		BadHistoryRecordS;	/* Count of bad records */

/* Public Function Prototypes */

void		read_pkg_history_file(char *);
void		read_cls_history_file(char *);

/* Library Function Prototynes */

/* Local Function Prototypes */

static int 	map_hist_to_pkg(char *, char *, char *, char *);
static void 	attach_pkg_hist(char *, char *, char *, char *, struct
    pkg_hist *);
static int 	map_hist_to_cls(char *, char *, char *);
static void 	attach_cls_hist(char *, char *, char *, struct pkg_hist *);
static int 	is_pkg_installed(Modinfo *, struct s_histid *);
static int 	is_cls_installed(Modinfo *, struct s_histid *);
static void	parse_pkg_entry(char *);
static void	parse_cls_entry(char *);
static char * 	set_token_value(char *, char *, int);
static char * 	tok_value(char *);
static char *	split_ver(char *, int);
static void	free_hist_ent(struct pkg_hist *);
static void	select_replacing_locales(char *, char *);


/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */


/*
 * read_pkg_history_file()
 *
 * Parameters:
 *	path	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
read_pkg_history_file(char * path)
{
	FILE	*fp;
	char	*line, *entry;
	unsigned int	entry_used, entry_size, n;

	if ((fp = fopen(path, "r")) == (FILE *)NULL) {
		return;  /* assume no history, which is OK */
	}

	BadHistoryRecordS = 0;

	gtoksbuf = (char *) xcalloc(ENTRY_BUF_SIZE);
	gtoksbuf_size = ENTRY_BUF_SIZE;

	glinebuf = (char *) xcalloc(BUFSIZ);

	line = (char *) xcalloc(BUFSIZ);

	entry = (char *) xcalloc(ENTRY_BUF_SIZE);
	entry_size = ENTRY_BUF_SIZE;
	entry_used = 0;

	while (fgets(line, BUFSIZ, fp)) {

		if (line[0] == '#' || line[0] == '\n' || line[0] == '\0')
			continue;

		if (strstr(line, "PKG=")) {
			parse_pkg_entry(entry);
			(void) memset(entry, '\0', entry_size);
			(void) strcpy(entry, line);
			entry_used = strlen(line);
		} else {
			n = strlen(line);
			if (entry_used + n >= entry_size) {
				entry_size += ENTRY_BUF_SIZE;
				entry = xrealloc(entry, entry_size);
			}
			(void) strcat(entry, line);
			entry_used += n;
		}
	}

	/*
	 * Last one
	 */
	parse_pkg_entry(entry);

	(void) free(line);
	(void) free(entry);
	(void) free(gtoksbuf);
	(void) free(glinebuf);

	(void) fclose(fp);

	if (BadHistoryRecordS) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB", "%d bad records in %s"),
		    BadHistoryRecordS, path);
	}
}

/*
 * read_cls_history_file()
 * Parameters:
 *	path
 * Return:
 *	none
 * Status:
 *	public
 */
void
read_cls_history_file(char *path)
{
	FILE	*fp;
	char	*line, *entry;
	unsigned int	entry_used, entry_size, n;

	if ((fp = fopen(path, "r")) == (FILE *)NULL) {
		return;  /* assume no history, which is OK */
	}

	BadHistoryRecordS = 0;

	gtoksbuf = (char *) xcalloc(ENTRY_BUF_SIZE);
	gtoksbuf_size = ENTRY_BUF_SIZE;

	glinebuf = (char *) xcalloc(BUFSIZ);

	line = (char *) xcalloc(BUFSIZ);

	entry = (char *) xcalloc(ENTRY_BUF_SIZE);
	entry_size = ENTRY_BUF_SIZE;
	entry_used = 0;

	while (fgets(line, BUFSIZ, fp)) {

		if (line[0] == '#' || line[0] == '\n' || line[0] == '\0')
			continue;

		if (strstr(line, "CLUSTER=")) {
			parse_cls_entry(entry);
			(void) memset(entry, '\0', entry_size);
			(void) strcpy(entry, line);
			entry_used = strlen(line);
		} else {
			n = strlen(line);
			if (entry_used + n >= entry_size) {
				entry_size += ENTRY_BUF_SIZE;
				entry = xrealloc(entry, entry_size);
			}
			(void) strcat(entry, line);
		}
	}
	/*
	 * Last one
	 */
	parse_cls_entry(entry);

	(void) free(line);
	(void) free(entry);
	(void) free(gtoksbuf);
	(void) free(glinebuf);

	(void) fclose(fp);

	if (BadHistoryRecordS) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB", "%d bad records in %s"),
		    BadHistoryRecordS, path);
	}
}

/*
 * free_history()
 * Parameters:
 *	histp
 * Return:
 *	none
 * Status:
 *	public
 */
void
free_history(struct pkg_hist *histp)
{
	struct pkg_hist **last, *cur;

	if (histp == NULL || --(histp->ref_count) > 0)
		return;

	last = &pkg_history;
	cur = pkg_history;
	while (cur) {
		if (cur == histp) {
			*last = cur->hist_next;
			free_hist_ent(cur);
			return;
		}
		last = &(cur->hist_next);
		cur = cur->hist_next;
	}
	last = &cls_history;
	cur = cls_history;
	while (cur) {
		if (cur == histp) {
			*last = cur->hist_next;
			free_hist_ent(cur);
			return;
		}
		last = &(cur->hist_next);
		cur = cur->hist_next;
	}
}


/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * parse_cls_entry()
 * Parameters:
 *	entry	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
parse_cls_entry(char *entry)
{
	struct pkg_hist	*ph;
	char	cls_abbr[TOK_BUF_SIZE], ver_high[TOK_BUF_SIZE];
	char	ver_low[TOK_BUF_SIZE];
	char	*tok_value;
	char	*p, *nl;

	if (*entry == '\0')
		return;

	BadHistoryRecord = 0;

	(void) memset(cls_abbr, '\0', sizeof (cls_abbr));
	(void) memset(ver_high, '\0', sizeof (ver_high));
	(void) memset(ver_low, '\0', sizeof (ver_low));

	tok_value = set_token_value("CLUSTER=", entry, TOK_BUF_SIZE);
	if (tok_value != NULL)
		(void) strcpy(cls_abbr, tok_value);
	if (strchr(tok_value, ' ') != NULL) {
		BadHistoryRecord++;
	}

	tok_value = set_token_value("VERSION=", entry, 0);
	if (tok_value != NULL) {
		(void) strcpy(ver_low, split_ver(tok_value, VER_LOW));
		(void) strcpy(ver_high, split_ver(tok_value, VER_HIGH));
	}

	if (map_hist_to_cls(cls_abbr, ver_low, ver_high) &&
	    !BadHistoryRecord) {
		ph = (struct pkg_hist *) xcalloc(sizeof (struct pkg_hist));

		tok_value = set_token_value("REPLACED_BY=", entry, 0);
		if (tok_value != NULL)
			ph->replaced_by = xstrdup(tok_value);

		if (ph->replaced_by != NULL) {
			if (!strstr(ph->replaced_by, cls_abbr))
				ph->to_be_removed = 1;
		}
		attach_cls_hist(cls_abbr, ver_low, ver_high, ph);
	} else if (BadHistoryRecord) {
		BadHistoryRecordS++;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB", "Bad record ignored:"));
		/*
		 * write_message() can't handle very long strings,
		 * so we feed it one line at a time
		 */
		p = entry;
		while ((nl = strchr(p, '\n')) != NULL) {
			*nl = '\0';
			write_message(LOGSCR, STATMSG, LEVEL0|CONTINUE, p);
			p = nl+1;
		}
	}

}


/*
 * set_token_value()
 * Parameters:
 *	tok	- Token to match
 *	entry	- String to search
 *	max_len	- Maximum length we're allowed to return
 * Return:
 *		String containing a blank separated list of token values
 * Status:
 *	private
 */
static char *
set_token_value(char *tok, char *entry, int max_len)
{
	char	*cp, *tmp;
	int	tok_len;
	unsigned int	gtoksbuf_used;

	*gtoksbuf = '\0';
	gtoksbuf_used = 0;
	tok_len = strlen(tok);

	for (cp = strstr(entry, tok); cp != NULL;
	    cp = strstr((cp + tok_len), tok)) {
		tmp = tok_value(cp + tok_len);
		if (gtoksbuf_used + strlen(tmp) + 1 >= gtoksbuf_size) {
			gtoksbuf_size += ENTRY_BUF_SIZE;
			gtoksbuf = xrealloc(gtoksbuf, gtoksbuf_size);
		}
		if (*gtoksbuf != '\0') {
			(void) strcat(gtoksbuf, " ");
			gtoksbuf_used++;
		}
		(void) strcat(gtoksbuf, tmp);
		gtoksbuf_used += strlen(tmp);
	}
	if (*gtoksbuf == '\0')
		return (NULL);

	/* Is it too long? */

	if (max_len && *gtoksbuf != '\0' && strlen(gtoksbuf) >= max_len) {
		BadHistoryRecord++;
		return (NULL);
	}
	return (gtoksbuf);

}

/*
 * tok_value()
 * Parameters:
 *	cp	- Pointer to a string
 * Return:
 *		Pointer to a string startring at cp through, but not
 *		including the first '\n'
 *		Leading and trailing spaces are eliminated
 * Status:
 *	private
 */
static char *
tok_value(char *cp)
{
	char	*lp;
	int	bufsiz = BUFSIZ;

	lp = glinebuf;

	/* Copy cp to lp; stop if we exceed size of glinebuf */

	while (*cp != '\n' && --bufsiz)
		*lp++ = *cp++;
	*lp = '\0';

	/* Trim trailing blanks */

	while (*--lp == ' ' && lp > glinebuf)
		*lp = '\0';

	/* Trim leading blanks */

	lp = glinebuf;
	while (*lp == ' ')
		lp++;

	return (lp);
}

/*
 * split_ver()
 * Parameters:
 *	ver	-
 *	flag	-
 * Return:
 *	none
 * Status:
 *	private
 */
static char *
split_ver(char *ver, int flag)
{
	static	char version[TOK_BUF_SIZE];
	char *zero = "0";
	char *cp;

	(void) strcpy(version, ver);
	cp = strchr(version, ':');

	if (flag == VER_LOW) {
		/*
		 * "0" or the string before ":"
		 */
		if (cp == NULL)
			(void) strcpy(version, zero);
		else {
			cp--;
			while (isspace((u_char)*cp))
				cp--;
			*++cp = '\0';
		}
		cp = version;
	} else if (flag == VER_HIGH) {
		/*
		 * The string after the ":", or the whole string if no ":"
		 */
		if (cp != NULL) {
			cp++;
			while (isspace((u_char)*cp))
				cp++;
		} else {
			cp = version;
		}
	} else {
		cp = version;
	}

	/*
	 * Sanity check
	 * Can't be too long, and can't have imbedded blanks
	 */

	if (*cp != '\0' && strlen(cp) >= TOK_BUF_SIZE) {
		BadHistoryRecord++;
		cp = zero;
	}
	if (strchr(cp, ' ') != NULL) {
		BadHistoryRecord++;
		cp = zero;
	}

	return (cp);
}


/*
 * parse_pkg_entry()
 * Parameters:
 *	entry	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
parse_pkg_entry(char *entry)
{
	struct pkg_hist	*ph;
	char	pkg_abbr[TOK_BUF_SIZE], ver_high[TOK_BUF_SIZE];
	char	ver_low[TOK_BUF_SIZE], arch[TOK_BUF_SIZE];
	char	*tok_value;
	char	*p, *nl;
	StringList	*replaced_by_sl;

	if (*entry == '\0')
		return;

	BadHistoryRecord = 0;

	(void) memset(pkg_abbr, '\0', sizeof (pkg_abbr));
	(void) memset(ver_high, '\0', sizeof (ver_high));
	(void) memset(ver_low, '\0', sizeof (ver_low));
	(void) memset(arch, '\0', sizeof (arch));

	tok_value = set_token_value("PKG=", entry, TOK_BUF_SIZE);
	if (tok_value != NULL)
		(void) strcpy(pkg_abbr, tok_value);
	if (strchr(tok_value, ' ') != NULL) {
		BadHistoryRecord++;
	}

	tok_value = set_token_value("ARCH=", entry, TOK_BUF_SIZE);
	if (tok_value != NULL)
		(void) strcpy(arch, tok_value);
	if (strchr(tok_value, ' ') != NULL) {
		BadHistoryRecord++;
	}

	tok_value = set_token_value("VERSION=", entry, 0);
	if (tok_value != NULL) {
		(void) strcpy(ver_low, split_ver(tok_value, VER_LOW));
		(void) strcpy(ver_high, split_ver(tok_value, VER_HIGH));
	}

	if (map_hist_to_pkg(pkg_abbr, ver_low, ver_high, arch) &&
	    !BadHistoryRecord) {
		ph = (struct pkg_hist *) xcalloc(sizeof (struct pkg_hist));

		tok_value = set_token_value("REPLACED_BY=", entry, 0);
		if (tok_value != NULL)
			ph->replaced_by = xstrdup(tok_value);

		tok_value = set_token_value("PRODRM=", entry, 0);
		if (tok_value != NULL)
			ph->prod_rm_list = xstrdup(tok_value);

		tok_value = set_token_value("REMOVED_FILES=", entry, 0);
		if (tok_value != NULL)
			ph->deleted_files = xstrdup(tok_value);

		tok_value = set_token_value("REMOVE_FROM_CLUSTER=", entry, 0);
		if (tok_value != NULL)
			ph->cluster_rm_list = xstrdup(tok_value);

		tok_value =
		    set_token_value("IGNORE_VALIDATION_ERROR=", entry, 0);
		if (tok_value != NULL)
			ph->ignore_list = xstrdup(tok_value);

		tok_value = set_token_value("PKGRM=", entry, 0);
		if (tok_value != NULL) {
			if ((*tok_value == 'y') || (*tok_value == 'Y'))
				ph->needs_pkgrm = 1;
		}

		tok_value = set_token_value("BASEDIR_CHANGE=", entry, 0);
		if (tok_value != NULL) {
			if ((*tok_value == 'y') || (*tok_value == 'Y')) {
				ph->basedir_change = 1;

				/* BASEDIR_CHANGE implies PKGRM */
				ph->needs_pkgrm = 1;
			}
		}
		/*
		 * Search replaced by string to make sure that the package being
		 * replaced doesn't have the same name as the one doing the
		 * replacing.
		 */
		if (ph->replaced_by != NULL) {
			replaced_by_sl = StringListBuild(ph->replaced_by, ' ');
			if (StringListFind(replaced_by_sl, pkg_abbr) == NULL) {
				ph->to_be_removed = 1;
			}
			StringListFree(replaced_by_sl);
		}
		attach_pkg_hist(pkg_abbr, ver_low, ver_high, arch, ph);
	} else if (BadHistoryRecord) {
		BadHistoryRecordS++;
		write_message(LOGSCR, ERRMSG, LEVEL0,
		    dgettext("SUNW_INSTALL_SWLIB", "Bad record ignored:"));
		/*
		 * write_message() can't handle very long strings,
		 * so we feed it one line at a time
		 */
		p = entry;
		while ((nl = strchr(p, '\n')) != NULL) {
			*nl = '\0';
			write_message(LOGSCR, STATMSG, LEVEL0|CONTINUE, p);
			p = nl+1;
		}
	}
}

/*
 * map_hist_to_pkg()
 * Parameters:
 *	pkg	-
 *	verlo	-
 *	verhi	-
 *	arch	-
 * Return:
 * Status:
 *	private
 */
static int
map_hist_to_pkg(char *pkg, char *verlo, char *verhi, char *arch)
{
	Module *mod;
	struct s_histid histid;
	int is_installed = 0;
	Node *node;
	Modinfo *mi;

	histid.verlo = verlo;
	histid.verhi = verhi;
	histid.arch = arch;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC) {
			node = findnode(mod->sub->info.prod->p_packages,
			    pkg);
			if (node) {
				mi = (Modinfo *)(node->data);
				if (is_pkg_installed(mi, &histid))
					is_installed = 1;
				else
					while ((mi = next_inst(mi)) != NULL)
						if (is_pkg_installed(mi,
						    &histid)) {
							is_installed = 1;
							break;
						}
			}
		}
		if (is_installed)
			break;
	}
	return (is_installed);
}

/*
 * is_pkg_installed()
 * Parameters:
 *	mi	-
 *	histid	-
 * Return:
 * Status:
 *	private
 */
static int
is_pkg_installed(Modinfo * mi, struct s_histid * histid)
{
	if ((mi->m_shared == NOTDUPLICATE ||
	    mi->m_shared == SPOOLED_NOTDUP) &&
	    strcmp(mi->m_arch, histid->arch) == 0 &&
	    pkg_vcmp(mi->m_version, histid->verlo) >= 0 &&
	    pkg_vcmp(mi->m_version, histid->verhi) < 0)
		return (1);
	else
		return (0);
}

/*
 * map_hist_to_cls()
 * Parameters:
 *	cls	-
 *	verlo	-
 *	verhi	-
 * Return:
 * Status:
 *	private
 */
static int
map_hist_to_cls(char *cls, char *verlo, char *verhi)
{
	Module *mod;
	struct s_histid histid;
	int is_installed = 0;
	Node *node;
	Modinfo *mi;

	histid.verlo = verlo;
	histid.verhi = verhi;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC) {
			node = findnode(mod->sub->info.prod->p_clusters,
			    cls);
			if (node) {
				mi = (Modinfo *)(node->data);
				if (is_cls_installed(mi, &histid))
					is_installed = 1;
				else
					while ((mi = next_inst(mi)) != NULL)
						if (is_cls_installed(mi,
						    &histid)) {
							is_installed = 1;
							break;
						}
			}
		}
		if (is_installed)
			break;
	}
	return (is_installed);
}

/*
 * is_cls_installed()
 * Parameters:
 *	mi	-
 *	histid	-
 * Return:
 * Status:
 *	private
 */
static int
is_cls_installed(Modinfo * mi, struct s_histid * histid)
{
	if (prod_vcmp(mi->m_version, histid->verlo) >= 0 &&
	    prod_vcmp(mi->m_version, histid->verhi) < 0)
		return (1);
	else
		return (0);
}

/*
 * attach_pkg_hist()
 * Parameters:
 *	pkg	-
 *	verlo	-
 *	verhi	-
 *	arch	-
 *	histp	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
attach_pkg_hist(char *pkg, char *verlo, char *verhi, char *arch,
					struct pkg_hist *histp)
{
	Module *mod;
	struct s_histid histid;
	Node *node;
	Modinfo *mi, *installed;

	histid.verlo = verlo;
	histid.verhi = verhi;
	histid.arch = arch;

	histp->hist_next = pkg_history;
	pkg_history = histp;


	/*
	 * Add the package history entry to the appropriate package entry in
	 * the installed Product.
	 */
	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC) {
			node = findnode(mod->sub->info.prod->p_packages, pkg);
			if (node) {
				installed = NULL;
				mi = (Modinfo *)(node->data);
				if (is_pkg_installed(mi, &histid)) {
					mi->m_pkg_hist = histp;
					histp->ref_count++;
					installed = mi;
				}

				while ((mi = next_inst(mi)) != NULL) {
					if (is_pkg_installed(mi, &histid)) {
						mi->m_pkg_hist = histp;
						histp->ref_count++;
						installed = mi;
					}
				}

				/*
				 * If a non-locale package has been replaced
				 * by a locale package, then we need to
				 * select the locales in the replacing
				 * package(s).
				 *
				 * This all seems like a scary hack, and it
				 * is.  It is, however, necessary to deal with
				 * the partial locale split that happened in
				 * S8.  Specifically, SUNWploc and a few other
				 * packages split into per-partial-locale
				 * packages (SUNWnamos and friends).
				 */
				if (installed && !installed->m_locale &&
				    histp->replaced_by) {
					select_replacing_locales(
							histp->replaced_by,
							pkg);
				}
			}
		}
	}
}

/*
 * attach_cls_hist()
 * Parameters:
 *	pkg	-
 *	verlo	-
 *	verhi	-
 *	arch	-
 *	histp	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
attach_cls_hist(char *cls, char *verlo, char *verhi, struct pkg_hist *histp)
{
	Module *mod;
	struct s_histid histid;
	Node *node;
	Modinfo *mi;

	histid.verlo = verlo;
	histid.verhi = verhi;

	histp->hist_next = cls_history;
	cls_history = histp;

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC) {
			node = findnode(mod->sub->info.prod->p_clusters,
			    cls);
			if (node) {
				mi = (Modinfo *)(node->data);
				if (is_cls_installed(mi, &histid)) {
					mi->m_pkg_hist = histp;
					histp->ref_count++;
				}
				while ((mi = next_inst(mi)) != NULL)
					if (is_cls_installed(mi, &histid)) {
						mi->m_pkg_hist = histp;
						histp->ref_count++;
					}
			}
		}
	}
}

/*
 * free_hist_ent()
 * Parameters:
 *	histp
 * Return:
 *	none
 * Status:
 *	private
 */
static void
free_hist_ent(struct pkg_hist *histp)
{
	if (histp->replaced_by)
		free(histp->replaced_by);
	if (histp->prod_rm_list)
		free(histp->prod_rm_list);
	if (histp->deleted_files)
		free(histp->deleted_files);
	if (histp->cluster_rm_list)
		free(histp->cluster_rm_list);
	if (histp->ignore_list)
		free(histp->ignore_list);
	free(histp);
}

/*
 * Name:	select_replacing_locales
 * Description:	Sometimes (i.e. Solaris 7 => Solaris 8) the LCs will split a
 *		common non-L10N package (SUNWploc) into several L10N packages.
 *		Upgrade will only install the pieces that are in selected
 *		locales.  To preserve what they've already got, we want to
 *		select the locales in the replacement packages.  Given a list
 *		a list of replacing packages, this routine selects their
 *		locales.
 *
 *		I'd prefer to do this in sync_l10n(), but to do so would be
 *		phenomenally expensive as, at this time, there is no way to go
 *		backwards in the replacement tree.  That is, you can find out
 *		that foo is replaced by foo and bar, but you can't look at bar
 *		and determine that it replaces foo.
 * Scope:	private
 * Arguments:	replist	- [RO, *RO] (char *)
 *			  A space-delimited list of packages whose locales are
 *			  to be selected.
 * Returns:	none
 */
static void
select_replacing_locales(char *replist, char *package)
{
	Module *curprod;
	Modinfo *mi;
	Node *node;
	StringList *str;
	char *p, *cp;

	curprod = get_current_product();
	cp = replist;
	while ((p = split_name(&cp))) {
		if (!streq(p, package)) {
			node = findnode(curprod->info.prod->p_packages, p);
			if (node) {
				mi = (Modinfo *)(node->data);
				for (str = mi->m_loc_strlist; str;
				    str = str->next) {
					(void) select_locale(curprod,
					    str->string_ptr, FALSE);
				}
			}
		}
	}
}
