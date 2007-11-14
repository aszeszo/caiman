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

#pragma ident	"@(#)td_version.c	1.1	07/08/03 SMI"

#include <td_version.h>

#include <stdio.h>
#include <ctype.h>
#include <sys/param.h>
#include <sys/types.h>
#include <string.h>
#include <stdlib.h>
#include <td_lib.h>

/* Local Function Prototypes */

static  int	prod_tokenize(char **, char *);
static  int	chk_prod_toks(char **);
static  int	vstrcoll(char *, char *);
static  int	is_empty(char *);
static	void	strip_trailing_blanks(char **);
#ifdef DEBUG_V
static	void	print_tokens(char **);
#endif

#define	MAX_VERSION_LEN		256
#define	MAX_TOKENS		10

#define	PROD_SUN_NAME_TOK	0
#define	PROD_SUN_VER_TOK	1
#define	PROD_SUN_IVER_TOK	2
#define	PROD_VENDOR_NAME_TOK	3
#define	PROD_VENDOR_VER_TOK	4
#define	PROD_VENDOR_IVER_TOK	5

#define	PKG_SUN_VER_TOK		0
#define	PKG_SUN_IVER_TOK	1
#define	PKG_VENDOR_NAME_TOK	2
#define	PKG_VENDOR_VER_TOK	3
#define	PKG_VENDOR_IVER_TOK	4
#define	PKG_PATCH_TOK		5


#ifdef MAIN
main(int argc, char *argv[])
{
	int 	ret;
	int	c;
	char	*str1, *str2;

	if (argv[1] == NULL || argv[2] == NULL || argv[3] == NULL) {
		(void) printf("USAGE: %s -[P(roduct)p(ackage)] ver1 ver2\n",
		    argv[0]);
		exit(1);
	}
	if (*argv[1] != '-') {
		(void) printf("USAGE: %s -[P(roduct)p(ackage)] ver1 ver2\n",
		    argv[0]);
		exit(1);
	}

	c = (*(argv[1] + 1));

	str1 = argv[2];
	str2 = argv[3];

	switch (c) {
	case 'P':
		ret = td_prod_vcmp(str1, str2);
		(void) printf("td_prod_vcmp return = %d\n", ret);
		break;
	default:
		(void) printf("USAGE: %s -[P(roduct)] ver1 ver2\n",
		    argv[0]);
		exit(1);
	}
	exit(0);
}
#endif

static char *INST_RELEASE_tmp_path = NULL;
/*
 * INST_RELEASE_read_path()
 *	this function will return the correct path for the INST_RELEASE
 *	file.
 *
 * Called By: load_installed()
 *
 * Parameters:
 *	rootdir - This is the root directory passed in by caller.
 * Return:
 *	the path to the file or NULL if not found.
 * Status:
 *	software library internal
 */
static char *
INST_RELEASE_read_path(const char *rootdir)
{
	/*
	 * Check to see if the temp variable used to hold the path is
	 * free. If no free it, then allocate a new one.
	 */
	if (INST_RELEASE_tmp_path != NULL)
		free(INST_RELEASE_tmp_path);
	INST_RELEASE_tmp_path = malloc(MAXPATHLEN);

	(void) snprintf(INST_RELEASE_tmp_path, MAXPATHLEN,
	    (td_is_new_var_sadm(rootdir) ?
	    "%s/var/sadm/system/admin/INST_RELEASE" :
	    "%s/var/sadm/softinfo/INST_RELEASE"),
	    rootdir);

	return (INST_RELEASE_tmp_path);
}

boolean_t
td_get_release(const char *rootdir, char *release, int maxrellen,
    char *pminor, int maxminor)
{
	FILE	*fp;
	char	line[BUFSIZ];

	if (release == NULL)
		return (B_FALSE);
	release[0] = '\0';

	if ((fp = fopen(INST_RELEASE_read_path(rootdir), "r")) == NULL) {
		return (B_FALSE);
	}

	/* First line must be OS=Solaris */
	if (fgets(line, sizeof (line), fp) == NULL ||
	    strncmp(line, "OS=Solaris", 10) != 0) {
		(void) fclose(fp);
		return (B_FALSE);
	}

	/* Second line must be VERSION= (actual number checked below) */
	if (fgets(line, sizeof (line), fp) == NULL ||
	    strncmp(line, "VERSION=", 8) != 0) {
		(void) fclose(fp);
		return (B_FALSE);
	}

	/* clear out the newline */
	line[strlen(line) - 1] = '\0';
	/* Version can be either x or x.y */
	if (isdigit(line[8]) && line[9] == '.' && isdigit(line[10])) {
		if (pminor != NULL)
			(void) strncpy(pminor, &line[10], maxminor);
	} else if (!isdigit(line[8])) {
		(void) fclose(fp);
		return (B_FALSE);
	}
	if (release != NULL)
		(void) snprintf(release, maxrellen, "Solaris_%s", &line[8]);
	else {
		(void) fclose(fp);
		return (B_FALSE);
	}
	(void) fclose(fp);
	return (B_TRUE);
}

/*
 * td_get_build_id()
 *
 * get build id from /etc/release of rooted directory
 *
 * Parameters:
 *	rootdir - This is the root directory passed in by caller.
 *	build_id - address of buffer
 *	maxlen - size of build_id
 * Return:
 *	true if found and at least partially copied
 *	otherwise false
 * Status:
 *	software library internal
 * Note: The build information in /etc/release is in one of the
 * following formats
 * "Solaris Express Community Edition snv_69 X86"
 * "Solaris Nevada snv_64a X86"
 * "Solaris 9 4/03 s9s_u3wos_08 SPARC"
 * "Solaris 10 3/05 s10_74L2a X86"
 */
boolean_t
td_get_build_id(const char *rootdir, char *build_id, size_t maxlen)
{
	FILE	*fp;
	char	line[BUFSIZ];
	char	etcrelease[MAXPATHLEN];
	char	*token = NULL;
	char	release[BUFSIZ];

	if (rootdir == NULL || build_id == NULL || maxlen < 1)
		return (B_FALSE);
	(void) strcpy(etcrelease, rootdir);
	(void) strlcat(etcrelease, "/etc/release", sizeof (etcrelease));
	if ((fp = fopen(etcrelease, "r")) == NULL)
		return (B_FALSE);
	release[0] = '\0';
	/* Ignore the first two tokens */
	if (fgets(line, sizeof (line), fp) != NULL &&
	    strtok(line, " \n") != NULL &&
	    strtok(NULL, " \n") != NULL) {
		/*
		 * Ignore the tokens Community, Edition, X86 and SPARC
		 * since we want the release string to be compact
		 */
		while ((token = strtok(NULL, " \n")) != NULL) {
			if (strcmp(token, "Community") &&
			    strcmp(token, "Edition") &&
			    strcmp(token, "X86") &&
			    strcmp(token, "SPARC")) {
				(void) strcat(release, token);
				(void) strcat(release, " ");
			}
		}
	}
	(void) fclose(fp);
	if (release[0] == '\0') {
		return (B_FALSE);
	}
	(void) strncpy(build_id, release, maxlen);
	return (B_TRUE);
}

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * td_prod_vcmp() - compare two product version strings
 *
 * Parameters:
 *	v1	- first version string
 *	v2	- second version string
 * Returns:
 *   V_EQUAL_TO - v1 and v2 are equal
 *   V_GREATER_THAN - v1 is greater than v2.
 *   V_LESS_THAN - v1 is less than v2.
 *   V_NOT_UPGRADEABLE - v1 and v2 don't have a clear order relationship.
 *	This would be the case if we were comparing, say, Cray's
 *	version of Solaris to Toshiba's version of Solaris.  Since
 *	neither of them is a descendent of the other, we can't upgrade
 *	one to the other.
 *
 * Status:
 *	public
 */
int
td_prod_vcmp(const char *v1, const char *v2)
{
	int	ret, i, state;
	char	v1_buf[MAX_VERSION_LEN + 1];
	char	v2_buf[MAX_VERSION_LEN + 1];
	char	*v1_tokens[MAX_TOKENS + 2], *v2_tokens[MAX_TOKENS + 2];

	(void) memset(v1_buf, '\0', sizeof (v1_buf));
	(void) memset(v2_buf, '\0', sizeof (v2_buf));
	(void) memset(v1_tokens, '\0', sizeof (v1_tokens));
	(void) memset(v2_tokens, '\0', sizeof (v2_tokens));

	(void) strcpy(v1_buf, v1);
	if ((ret = prod_tokenize(v1_tokens, v1_buf)) < 0)
		return (ret);

	(void) strcpy(v2_buf, v2);
	if ((ret = prod_tokenize(v2_tokens, v2_buf)) < 0)
		return (ret);


#ifdef DEBUG_V
	print_tokens(v1_tokens);
	(void) printf("\n");
	print_tokens(v2_tokens);
#endif

	for (i = 0; v1_tokens[i]; i++) {
		if (is_empty(v1_tokens[i]))
			continue;

		switch (i) {
		case PROD_SUN_NAME_TOK:
			state = vstrcoll(v1_tokens[i], v2_tokens[i]);
			if (state != V_EQUAL_TO)
				return (V_NOT_UPGRADEABLE);
			break;

		case PROD_SUN_VER_TOK:
			if (is_empty(v2_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			state = vstrcoll(v1_tokens[i], v2_tokens[i]);
			break;

		case PROD_SUN_IVER_TOK:
			/* Solaris_2.0.1_5.0  Solaris_2.0.1 */
			if (is_empty(v2_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			if (state == V_EQUAL_TO) {
				state = vstrcoll(v1_tokens[i], v2_tokens[i]);
			}
			break;
		case PROD_VENDOR_NAME_TOK:
			/* Solaris_2.0.1_5.0  Solaris_2.0.1_Dell_A */
			if (!is_empty(v2_tokens[PROD_SUN_IVER_TOK]))
				return (V_NOT_UPGRADEABLE);

			if (is_empty(v2_tokens[i])) {
				/* Solaris_2.0.1_Dell_A  Solaris_2.0.1 */
				if (state == V_EQUAL_TO)
					return (V_GREATER_THAN);
				i = MAX_TOKENS;
				continue;
			}
			ret = strcoll(v1_tokens[i], v2_tokens[i]);
			if (ret != 0) {
				/*
				 * Solaris_2.0.1_Soulbourne_A
				 * Solaris_2.0.1_Dell_A
				 */
				if (state == V_EQUAL_TO)
					return (V_NOT_UPGRADEABLE);
				/*
				 * Solaris_2.0.1_Soulbourne_A
				 * Solaris_2.0.2_Dell_A
				 */
				else
					return (state);
			}
			break;

		case PROD_VENDOR_VER_TOK:
			/* Solaris_2.0.1_Dell_A  Solaris_2.0.1_Dell */
			if (is_empty(v2_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			if (state == V_EQUAL_TO) {
				state = vstrcoll(v1_tokens[i], v2_tokens[i]);
			}
			break;

		case PROD_VENDOR_IVER_TOK:
			/* Solaris_2.0.1_Dell_A_1.0  Solaris_2.0.1_Dell_A */
			if (is_empty(v2_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			if (state == V_EQUAL_TO) {
				state = vstrcoll(v1_tokens[i], v2_tokens[i]);
			}
			break;
		default:
			return (V_NOT_UPGRADEABLE);
		}
	}

	for (i = 0; v2_tokens[i]; i++) {
		if (is_empty(v2_tokens[i]))
			continue;
		switch (i) {
		case PROD_SUN_NAME_TOK:
		case PROD_SUN_VER_TOK:
		case PROD_SUN_IVER_TOK:
			if (is_empty(v1_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			break;
		case PROD_VENDOR_NAME_TOK:
			/* Solaris_2.0.1_Dell_A  Solaris_2.0.1_5.1 */
			if (!is_empty(v1_tokens[PROD_SUN_IVER_TOK]))
				return (V_NOT_UPGRADEABLE);
			if (is_empty(v1_tokens[i])) {
				/* Solaris_2.0.1  Solaris_2.0.1_Dell_A */
				if (state == V_EQUAL_TO)
					return (V_LESS_THAN);
				else
					i = MAX_TOKENS;
			}
			break;
		case PROD_VENDOR_VER_TOK:
			/* Solaris_2.0.1_Dell  Solaris_2.0.1_Dell_A */
			if (is_empty(v1_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			break;
		case PROD_VENDOR_IVER_TOK:
			/* Solaris_2.0.1_Dell_A  Solaris_2.0.1_Dell_A_1.0 */
			if (is_empty(v1_tokens[i]))
				return (V_NOT_UPGRADEABLE);
			break;
		}
	}
	return (state);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * prod_tokenize()
 * Parameters:
 *	toks	-
 *	buf	-
 * Return:
 * Status:
 *	private
 */
static int
prod_tokenize(char *toks[], char buf[])
{
	static	char	*empty_str = "";
	char		*bp, *cp;
	int		len, i;

	len = (int)strlen(buf);
	if (len > MAX_VERSION_LEN)
		return (ERR_STR_TOO_LONG);

	toks[PROD_SUN_NAME_TOK] = empty_str;
	toks[PROD_SUN_VER_TOK] = empty_str;
	toks[PROD_SUN_IVER_TOK] = empty_str;
	toks[PROD_VENDOR_NAME_TOK] = empty_str;
	toks[PROD_VENDOR_VER_TOK] = empty_str;
	toks[PROD_VENDOR_IVER_TOK] = empty_str;

	bp = buf;
	if (!isalpha((unsigned)*bp))
		return (V_NOT_UPGRADEABLE);
	toks[PROD_SUN_NAME_TOK] = bp;

	for (i = 1; (cp = strchr(bp, '_')); i++) {
		*cp = '\0';
		bp = cp + 1;
		if (bp > (buf + len)) {
			return (V_NOT_UPGRADEABLE);
		}
		switch (i) {
		case PROD_SUN_VER_TOK:
			if (!isdigit((unsigned)(*bp))) {
				return (V_NOT_UPGRADEABLE);
			}
			toks[i] = bp;
			break;
		case PROD_SUN_IVER_TOK:
			if (isdigit((unsigned)(*bp))) {
				toks[i] = bp;
			} else {
				i++;
				toks[i] = bp;	/* Vendor name */
			}
			break;
		case PROD_VENDOR_NAME_TOK:
			if (isdigit((unsigned)(*bp))) {
				return (V_NOT_UPGRADEABLE);
			}
			toks[i] = bp;
			break;
		case PROD_VENDOR_VER_TOK:
			if (!isalpha((unsigned)(*bp))) {
				return (V_NOT_UPGRADEABLE);
			}
			toks[i] = bp;
			break;

		case PROD_VENDOR_IVER_TOK:
			if (!isdigit((unsigned)(*bp))) {
				return (V_NOT_UPGRADEABLE);
			}
			toks[i] = bp;
			break;
		}
	}

	if (i < 2)
		return (V_NOT_UPGRADEABLE);

	for (i = 0; toks[i]; i++) {
		cp = toks[i];
		while (*cp) {
			if (isalpha((unsigned)*cp)) {
				*cp = toupper((unsigned)*cp);
			}
			cp++;
		}
	}
	strip_trailing_blanks(toks);

	return (chk_prod_toks(toks));
}

/*
 * chk_prod_toks()
 *
 * Parameters:
 *	toks	-
 * Return:
 *
 * Status:
 *	private
 */
static int
chk_prod_toks(char *toks[])
{
	int	i;
	char	*cp;

	for (i = 0; toks[i]; i++) {
		if (*toks[i] == '\0')
			continue;

		switch (i) {
		case PROD_SUN_NAME_TOK:
			if ((strcoll(toks[i], "SOLARIS") == 0))
				break;
			else
				return (V_NOT_UPGRADEABLE);

		case PROD_SUN_VER_TOK:
		case PROD_SUN_IVER_TOK:
		case PROD_VENDOR_IVER_TOK:
			for (cp = toks[i]; *cp; cp++) {
				if (*cp == '.')
					continue;
				if (!isdigit((unsigned)(*cp)))
					return (V_NOT_UPGRADEABLE);
			}
			break;
		case PROD_VENDOR_NAME_TOK:
		case PROD_VENDOR_VER_TOK:
			for (cp = toks[i]; *cp; cp++) {
				if (!isalpha((unsigned)(*cp)))
					return (V_NOT_UPGRADEABLE);
			}
			break;
		}
	}
	return (0);
}


/*
 * vstrcoll()
 *
 * Parameters:
 *	s1	-
 *	s2	-
 * Return:
 *
 * Status:
 *	private
 */
static int
vstrcoll(char *s1, char *s2)
{
	int 	ret, i;
	int 	s1num[20], s2num[20];
	char	*cp_beg, *cp_end;

	if (isalpha((uchar_t)*s1)) {
		ret = strcoll(s1, s2);
		if (ret < 0)
			return (V_LESS_THAN);
		else if (ret > 0)
			return (V_GREATER_THAN);

		return (V_EQUAL_TO);
	}

	for (i = 0; i < 20; i++) {
		s1num[i] = -1;
		s2num[i] = -1;
	}

	i = 0; cp_beg = s1; cp_end = s1;
	while (cp_beg != NULL) {
		cp_end = strchr(cp_beg, '.');
		if (cp_end != NULL) {
			*cp_end = '\0';
			cp_end++;
		}
		s1num[i++] = atoi(cp_beg);
		cp_beg = cp_end;
	}

	i = 0; cp_beg = s2; cp_end = s2;
	while (cp_beg != NULL) {
		cp_end = strchr(cp_beg, '.');
		if (cp_end != NULL) {
			*cp_end = '\0';
			cp_end++;
		}
		s2num[i++] = atoi(cp_beg);
		cp_beg = cp_end;
	}

	for (i = 0; s1num[i] != -1; i++) {
		if (s2num[i] == -1) break;
		if (s1num[i] > s2num[i])
			return (V_GREATER_THAN);
		if (s1num[i] < s2num[i])
			return (V_LESS_THAN);
	}

	if ((s1num[i] != -1) || (s2num[i] != -1)) {
		if (s1num[i] == -1) {
			while (s2num[i] == 0) i++;
			if (s2num[i] != -1)
				return (V_LESS_THAN);
		} else {
			while (s1num[i] == 0) i++;
			if (s1num[i] != -1)
				return (V_GREATER_THAN);
		}
	}
	return (V_EQUAL_TO);
}

/*
 * strip_trailing_blanks()
 *
 * Parameters:
 *	toks	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
strip_trailing_blanks(char *toks[])
{
	int	i;
	char	*cp;

	for (i = 0; toks[i]; i++) {
		if (is_empty(toks[i]))
			continue;
		cp = toks[i] + (strlen(toks[i]) - 1);
		if (isspace((unsigned)*cp)) {
			while (isspace((unsigned)*cp)) cp--;
			cp++;
			*cp = '\0';
		}
	}
}

/*
 * is_empty()
 *
 * Parameters:
 *	cp	-
 * Return:
 *	0	-
 *	1	-
 * Status:
 *	private
 */
static int
is_empty(char *cp)
{
	if (*cp == '\0')
		return (1);
	return (0);
}

#ifdef DEBUG_V
static void
print_tokens(char *toks[])
{
	int i;

	for (i = 0; toks[i]; i++) {
		(void) printf("%s\n", toks[i]);
	}
}
#endif
