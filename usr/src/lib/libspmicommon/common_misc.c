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
 * Copyright (c) 2007, 2012, Oracle and/or its affiliates. All rights reserved.
 */




#include <sys/stat.h>
#include <string.h>
#include <unistd.h>
#include <locale.h>
#include <stdlib.h>
#include <limits.h>
#include <regex.h>
#include <ctype.h>
#include "spmicommon_lib.h"

/* internal prototypes */
void		link_to(Item **, Item *);

/* private prototypes */
void		error_and_exit(int);
static char	*_sh_to_regex(char *s);
static char	*date_time(char *, time_t);
static int	_get_random_info(void *, int);

/* Local Statics and Constants */
static char		rootdir[BUFSIZ] = "";
static char		protodir[BUFSIZ] = "/tmp/root";
static char		osdir[BUFSIZ] = "/";
static MachineType	machinetype = MT_STANDALONE;
static void 		(*fatal_err_func)() = &error_and_exit;
static int		cur_backoff = 0;

/* ----------------------- public functions --------------------------- */

/*
 * get_rootdir()
 *	Returns the rootdir previously set by a call to set_rootdir(). If
 *	set_rootdir() hasn't been called this returns a pointer to an empty
 *	string.
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to current rootdir string
 * Status:
 *	public
 */
char *
get_rootdir(void)
{
	return (rootdir);
}

/*
 * set_rootdir()
 *	Sets the global 'rootdir' variable. Used to install packages
 *	to 'newrootdir'.
 * Parameters:
 *	newrootdir	- non-NULL pathname used to set rootdir
 * Return:
 *	none
 * Status:
 *	public
 */
void
set_rootdir(char *newrootdir)
{
	(void) strcpy(rootdir, newrootdir);
	canoninplace(rootdir);

	if (streq(rootdir, "/"))
		rootdir[0] = '\0';
}

/*
 * get_protodir()
 *	Returns the protodir previously set by a call to set_protodir(). If
 *	set_protodir() hasn't been called this returns "/".
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to current protodir string
 * Status:
 *	public
 */
char *
get_protodir(void)
{
	return (protodir);
}

/*
 * set_protodir()
 *	Sets the global 'protodir' variable. Used to install packages
 *	to 'newprotodir'.
 * Parameters:
 *	newprotodir	- pathname used to set protodir
 * Return:
 *	none
 * Status:
 *	public
 */
void
set_protodir(char *newprotodir)
{
	(void) strcpy(protodir, newprotodir);
	canoninplace(protodir);

	/*
	 * we want protodir to be / if it should be,
	 * so let's not set it to NULL like set_rootdir() does
	 * at this point
	 */
}

/*
 * get_osdir()
 *	Returns the osdir previously set by a call to set_osdir(). If
 *	set_osdir() hasn't been called this returns "/".
 * Parameters:
 *	none
 * Return:
 *	char *	- pointer to current osdir string
 * Status:
 *	public
 */
char *
get_osdir(void)
{
	return (osdir);
}

/*
 * set_osdir()
 *	Sets the global 'osdir' variable. Used to install packages
 *	to 'newosdir'.
 * Parameters:
 *	newosdir	- pathname used to set osdir
 * Return:
 *	none
 * Status:
 *	public
 */
void
set_osdir(char *newosdir)
{
	(void) strcpy(osdir, newosdir);
	canoninplace(osdir);

	/*
	 * we want osdir to be / if it should be,
	 * so let's not set it to NULL like set_rootdir() does
	 * at this point
	 */
}

/*
 * common_dirname()
 * 	Same as libc dirname. A bug was found in the libc dirname. This
 *	is a workaround.
 * Parameters:
 *      char *s
 * Return:
 *      char * pointer to directory name extracted from s.
 * StatuS:
 *      public
 */
char *
common_dirname(char *s)
{
	register char   *p;

	if (!s || !*s)	/* zero or empty argument */
		return (".");

	p = s + strlen(s) - 1;

	while (p != s && *p == '/') {
		p--;
	}

	if (p == s && *p == '/') {
		return ("/");
	}

	while (p != s) {
		p--;
		if (*p == '/') {
			while (*p == '/' && p != s) {
				p--;
			}
			p++;
			*p = '\0';
			return (s);
		}
	}
	return (".");
}

/*
 * xcalloc()
 * 	Allocate 'size' bytes from the heap using calloc()
 * Parameters:
 *	size	- number of bytes to allocate
 * Return:
 *	NULL	- calloc() failure
 *	void *	- pointer to allocated structure
 * Status:
 *	public
 */
void *
xcalloc(size_t size)
{
	void *	tmp;

	if ((tmp = (void *) malloc(size)) == NULL) {
		fatal_err_func(ERR_MALLOC_FAIL);
		return (NULL);
	}

	(void) memset(tmp, 0, size);
	return (tmp);
}

/*
 * xmalloc()
 * 	Alloc 'size' bytes from heap using malloc()
 * Parameters:
 *	size	- number of bytes to malloc
 * Return:
 *	NULL	- malloc() failure
 *	void *	- pointer to allocated structure
 * Status:
 *	public
 */
void *
xmalloc(size_t size)
{
	void *tmp;

	if ((tmp = (void *) malloc(size)) == NULL) {
		fatal_err_func(ERR_MALLOC_FAIL);
		return (NULL);
	} else
		return (tmp);
}

/*
 * xrealloc()
 *	Calls realloc() with the specfied parameters. xrealloc()
 *	checks for realloc failures and adjusts the return value
 *	automatically.
 * Parameters:
 *	ptr	- pointer to existing data block
 * 	size	- number of bytes additional
 * Return:
 *	NULL	- realloc() failed
 *	void *	- pointer to realloc'd structured
 * Status:
 *	public
 */
void *
xrealloc(void *ptr, size_t size)
{
	void *tmp;

	if ((tmp = (void *)realloc(ptr, size)) == (void *)NULL) {
		fatal_err_func(ERR_MALLOC_FAIL);
		return ((void *)NULL);
	} else
		return (tmp);
}

/*
 * xstrdup()
 *	Allocate space for the string from the heap, copy 'str' into it,
 *	and return a pointer to it.
 * Parameters:
 *	str	- string to duplicate
 * Return:
 *	NULL	- duplication failed or 'str' was NULL
 * 	char *	- pointer to newly allocated/initialized structure
 * Status:
 *	public
 */
char *
xstrdup(char *str)
{
	char *tmp;

	if (str == NULL)
		return ((char *)NULL);

	if ((tmp = strdup(str)) == NULL) {
		fatal_err_func(ERR_MALLOC_FAIL);
		return ((char *)NULL);
	} else
		return (tmp);
}

/*
 * Function: strip_whitespace
 * Description:
 *	Strip the leading and trailing whitespace off of the
 *	str passed in.
 *
 * Scope:	PUBLIC
 * Parameters:
 *	str - [RW]
 *		char ** ptr to a str to be stripped.
 *		value of *str may change.
 * Return:	none
 * Globals:	none
 * Notes:
 */
void
strip_whitespace(char *str)
{
	char *ptr;
	char *tmp_str;

	if (!str || !strlen(str))
		return;


	/*
	 * Strip spaces off front:
	 * 	- find 1st non-blank char
	 *	- copy remaining str back to beginning of str.
	 */
	for (ptr = str; *ptr == ' '; ptr++);

	/* if there were leading spaces */
	if (ptr != str) {
		tmp_str = (char *)xmalloc(strlen(ptr) + 1);
		(void) strcpy(tmp_str, ptr);
		(void) strcpy(str, tmp_str);
	}

	/* strip spaces off end */
	for (ptr = str; *ptr && *ptr != ' '; ptr++);
	*ptr = '\0';
}

/*
 * Function: _sh_to_regex
 * Description:
 *	Convert a shell regular expression to an
 *	extended RE (regular expression)
 *	(thanks to Sam Falkner)
 * Scope:	PRIVATE
 * Parameters:
 *	char *pattern - shell regular expression to convert
 * Return:
 *	char * - converted shell expression; has been dynamically
 *	allocated - caller should free.
 * Globals:	none
 * Notes:
 */
static char *
_sh_to_regex(char *pattern)
{
	char *vi;
	char *c;
	char *tmp_pattern;
	char *tmp_pattern_ptr;

	if (!pattern)
		return (NULL);

	/* copy the pattern passed in so we don't modify it permanently */
	tmp_pattern = tmp_pattern_ptr = xstrdup(pattern);

	/*
	 * we'll never expand it to more than twice the original length
	 * plus the ^, $ anchors.
	 */
	vi = (char *)xmalloc((strlen(tmp_pattern) * 2) + 3);

	vi[0] = '^';
	for (c = vi+1; *tmp_pattern_ptr; ++c, ++tmp_pattern_ptr) {
		if (*tmp_pattern_ptr == '\\') {
			*(c++) = *(tmp_pattern_ptr++);
		} else if (*tmp_pattern_ptr == '*') {
			*(c++) = '.';
		} else if ((*tmp_pattern_ptr == '.') ||
			(*tmp_pattern_ptr == '$') ||
			(*tmp_pattern_ptr == '^')) {
			*(c++) = '\\';
		} else if (*tmp_pattern_ptr == '?') {
			*tmp_pattern_ptr = '.';
		}
		*c = *tmp_pattern_ptr;
		if (*tmp_pattern_ptr == '\0') {
			++c;
			break;
		}
	}
	*(c++) = '$';
	*c = '\0';

	free(tmp_pattern);
	return (vi);
}
/*
 * Function: re_match
 * Description:
 *	Perform regular expression matching on the search_str passed in
 *	using the RE pattern.
 * Scope:	PUBLIC
 * Parameters:
 * 	search_str - [R0] - string to look for RE pattern in
 * 	pattern - [R0] - RE pattern string
 *	shell_re_flag - [RO] -
 *		!0: treat pattern as a shell regular expression
 *		0: treat pattern as an regex() extended regular expression
 * Return:	REError (see typedef)
 * Globals:	none
 * Notes:
 */
REError
re_match(char *search_str, char *orig_pattern, int shell_re_flag)
{
	regex_t re;
	int ret;
	char errbuf[PATH_MAX];
	char *pattern;

	if (!orig_pattern || !search_str)
		return (REBadArg);

	/* convert the shell re pattern to a ERE pattern if requested */
	if (shell_re_flag) {
		pattern = _sh_to_regex(orig_pattern);
	} else {
		pattern = xstrdup(orig_pattern);
	}

	ret = regcomp(&re, pattern, REG_EXTENDED | REG_NOSUB);
	if (ret != REG_OK) {
		(void) regerror(ret, &re, errbuf, PATH_MAX);
		regfree(&re);
		free(pattern);
		return (RECompFailure);
	}

	ret = regexec(&re, search_str, 0, NULL, 0);
	regfree(&re);
	free(pattern);
	if (ret == REG_NOMATCH) {
		return (RENoMatch);
	} else {
		return (REMatch);
	}

	/* NOTREACHED */
}

/*
 * Function:	rm_link_mv_file
 * Description:	If there is a symbolic link in the old_location, remove
 *		it.  If there is a file in the old_location, not a symbolic
 *		link, move it to new_location in a dated form.
 * Scope:	PUBLIC
 * Parameters:	old_location -	RO
 *				type char *, full filepath
 *		new_locaiton -	RO
 *				type char *, full filepath
 * Returns:	Pointer to new name if the file was renamed or NULL
 */
char *
rm_link_mv_file(char *old_location, char *new_location)
{
	char date_str[MAXNAMELEN];
	char name_buf[MAXPATHLEN];
	static char newfile[MAXPATHLEN];
	struct stat buf;

	(void) snprintf(name_buf, MAXPATHLEN, "%s%s", get_rootdir(),
	    old_location);
	if (lstat(name_buf, &buf) == 0) {
		if ((buf.st_mode & S_IFLNK) == S_IFLNK)
			(void) unlink(name_buf);
		else if ((buf.st_mode & S_IFREG) == S_IFREG) {
			(void) snprintf(newfile, MAXPATHLEN, "%s%s",
				get_rootdir(), new_location);
			(void) strcpy(date_str,
				date_time(newfile, buf.st_mtime));
			(void) strcat(newfile, "_");
			(void) strcat(newfile, date_str);
			(void) rename(name_buf, newfile);
			return (newfile);
		}
	}
	return (NULL);
}

/*
 * get_value()
 *	Parse out value from string passed in. str should be of the form:
 *	"TOKENxVALUE\n" where x=delim.  The trailing \n is optional, and
 *	will be removed.
 *	Also, leading and trailing white space will be removed from VALUE.
 * Parameters:
 *	str	- string pointer to text line to be parsed
 *	delim	- a character delimeter
 * Return:
 * Status:
 *	public
 */
char	*
get_value(char *str, char delim)
{
	char	   *cp, *cp1;

	if ((cp = strchr(str, delim)) == NULL)
		return (NULL);

	cp += 1;		/* value\n	*/
	cp1 = strchr(cp, '\n');
	if (cp1 && *cp1)
		*cp1 = '\0';	/* value	*/

	/* chop leading white space */
	for (; cp && *cp && ((*cp == ' ') || (*cp == '\t')); ++cp)
		;

	if (*cp == '\0')
		return ("");

	/* chop trailing white space */
	for (cp1 = cp + strlen(cp) - 1;
	    cp1 >= cp && ((*cp1 == ' ') || (*cp1 == '\t')); --cp1)
		*cp1 = '\0';

	if (cp && *cp)
		return (cp);

	return ("");
}

/*
 * count_digits()
 *	Count the number of digits in a passed number.  This can
 *	be used to determine the number of spaces to reserve for printing.
 *	Zero takes up one digit.  Negative numbers have an extra digit for
 *	the negative sign.
 * Parameters:
 *	num	- the number whose digits are to be counted
 * Return: (int) the number of digits
 * Status:
 *	public
 */
int
count_digits(long num)
{
	int digits = 0;

	if (!num) {
		return (1);
	}

	/* Reserve a space for the sign */
	if (num < 0) {
		digits++;
		num = labs(num);
	}

	while (num) {
		digits++;
		num /= 10;
	}

	return (digits);
}

/* ---------------------- internal functions -------------------------- */

#ifdef notdef
/*
 * keyvalue_parse()
 *	Convert a key-value pair line into canonical form.  The
 *	operation is performed in-place.
 *	The following conversions are performed:
 *	- remove leading white space.
 *	- remove any white space before or after the "=".
 *	- remove any comments (anything after a '#')
 *	- null-terminate the keyword.
 *	- remove trailing blanks.
 *	- if the line is empty after these conversions, convert the
 *	  string to the null string and return a value pointer of NULL.
 *
 * Parameters:	buf - a pointer to the string to be converted to canonical
 *		form.
 * Return:
 *	a pointer to the value field.  Return NULL if none.
 *	at return, the original buffer now points to the null-terminated
 *	keyword only.
 * Status:
 *	semi-private (internal library use only)
 */
char *
keyvalue_parse(char *buf)
{
	char	*rp, *wp;
	char	*cp;
	int	len;

	if (buf == NULL)
		return (NULL);
	rp = buf;
	wp = buf;

	/* eat leading blanks */
	while (isspace(*rp))
		rp++;

	/* trim comments */

	if ((cp = strchr(rp, '#')) != NULL)
		*cp = '\0';

	/* trim trailing white space */

	len = strlen(rp);
	if (len > 0) {
		cp = rp + len - 1;  /* *cp points to last char */
		while (isspace(*cp) && cp >= rp - 1)
			cp--;
		/* cp points to last non-white char, or to rp - 1 */
		++cp;
		*cp = '\0';
	}

	if (strlen(rp) == 0) {
		*buf = '\0';
		return (NULL);
	}

	/*
	 *  We now know that there is at least one non-null char in the
	 *  line pointed to by rp (though not necessarily in the line
	 *  pointed to by buf, since we haven't collapsed buf yet.)
	 *  Leading and trailing blanks are gone, and comments are gone.
	 */

	/*  Move the keyword to the beginning of buf */
	while (!isspace(*rp) && *rp != '=' && *rp != '\0')
		*wp++ = *rp++;

	*wp++ = '\0';	/* keyword is now null-terminated */

	/* find the '=' (if there is one) */

	while (*rp != '\0' && isspace(*rp))
		rp++;

	if (*rp != '=')		/* there is no keyword-value */
		return (NULL);

	/* now skip over white space between the '=' and the value */
	while (*rp != '\0' && isspace(*rp))
		rp++;

	/*
	 *  rp now either points to the end of the string, or to the
	 *  beginning of the keyword's value.  If end-of-string, there is no
	 *  keyword value.
	 */

	if (*rp == '\0')
		return (NULL);
	else
		return (rp);
}
#endif /* notdef */

/*
 * append a linked list to the end of another linked list.  Assume
 * that both linked lists are properly terminated.
 */
void
link_to(Item **head, Item *item)
{
	if (item == NULL)
		return;
	while (*head != (Item *)NULL)
		head = &((*head)->next);
	*head = item;
}


/*
 * get_machintype()
 * Parameters:
 *	none
 * Return:
 * Status:
 *	public
 */
MachineType
get_machinetype(void)
{
	return (machinetype);
}

/*
 * set_machinetype()
 *	Set the global machine "type" specifier
 * Parameters:
 *	type	- machine type specifier (valid types: MT_SERVER,
 *		  MT_DATALESS, MT_DISKLESS, MT_CCLIENT, MT_SERVICE)
 * Return:
 *	none
 * Status:
 *	Public
 */
void
set_machinetype(MachineType type)
{
	machinetype = type;
}

/*
 * path_is_readable()
 *	Determine if a pathname is accessable and readable.
 * Parameters:
 *	fn	- pathname
 * Return:
 *	SUCCESS	- path is accessable and readable
 *	FAILURE	- path access/read failed
 * Status:
 *	public
 */
int
path_is_readable(char *fn)
{
	return ((access(fn, R_OK) == 0) ? SUCCESS : FAILURE);
}

/*
 * set_memalloc_failure_func()
 *	Allows an appliation to specify the function to be called when
 *	a memory allocation function fails.
 * Parameters:
 *	(*alloc_proc)(int)	- specifies the function to call if fatal error
 *			  (such as being unable to allocate memory) occurs.
 * Return:
 *	none
 * Status:
 *	Public
 */
void
set_memalloc_failure_func(void (*alloc_proc)(int))
{
	if (alloc_proc != (void (*)())NULL)
		fatal_err_func = alloc_proc;
}

/*
 * get_err_str()
 *	Retrieve the error message associated with 'errno'. Provided
 *	to allow applications which specify their own fatal error
 *	function to turn the error code passed to this function into
 *	a meaningful string.
 * Parameters:
 *	errno	- install-library specific error codes
 * Return:
 *	char *  - pointer to internationalized error string associated
 *		  with 'errno'
 * Status:
 *	Public
 */
char *
get_err_str(int errno)
{
	char *ret;

	switch (errno) {

	case ERR_MALLOC_FAIL:
		ret = dgettext("solaris_install_swlib",
					"Allocation of memory failed");
		break;
	case ERR_IBE:
		ret = dgettext("solaris_install_swlib",
		    "Install failed.  See /tmp/install_log for more details");
		break;
	default:
		ret = dgettext("solaris_install_swlib", "Fatal Error");
		break;
	}

	return (ret);
}

/* ----------------------- private functions -------------------------- */

/*
 * error_and_exit()
 *	Abort routine. An exit code of '2' is used by all applications
 *	to indicate a non-recoverable fatal error.
 * Parameters:
 *	errno	- error index number:
 *			ERR_IBE
 *			ERR_MALLOC_FAIL
 * Return:
 *	none
 * Status:
 *	public
 */
void
error_and_exit(int errno)
{
	(void) printf("%s\n", get_err_str(errno));
	exit(EXIT_INSTALL_FAILURE);
}

/*
 * Function:	date_time
 * Description:	Given a filename and a time, in seconds, create a
 *		unique dated filename in the following format:
 *
 *			filename_YEAR_MON_DAY[_INDEX]
 *
 *		where
 *			YEAR  ::= 4 character year string
 *			MON   ::= 2 character month of the year - 1 to 12
 *			DAY   ::= 2 character day of the month - 1 to 31
 *			INDEX ::= A character string comprised of a '_'
 *				  and a integer.  The INDEX is optional
 *				  and is used only to create a unique filename
 *				  in the event of a name collision.
 *
 * Scope:	PRIVATE
 * Parameters:	logname - RO
 *			  type char *, filename
 * 		seconds - RO
 *			  type time_t, representing the time in seconds
 *			  since 00:00:00 UTC, January 1, 1970.
 */
static char *
date_time(char *logname, time_t seconds)
{
	static char	ndx_str[MAXPATHLEN];
	static char	mdy[MAXPATHLEN];
	char		stat_name[MAXPATHLEN];
	struct stat	buf;
	int		ndx;

	(void) strftime(mdy, MAXPATHLEN, "%Y_%m_%d", localtime(&seconds));
	(void) snprintf(stat_name, MAXPATHLEN, "%s_%s", logname, mdy);
	ndx_str[0] = '\0';

	for (ndx = 1; stat(stat_name, &buf) == 0; ndx++) {
		(void) snprintf(ndx_str, MAXPATHLEN, "%s_%d", mdy, ndx);
		(void) snprintf(stat_name, MAXPATHLEN, "%s_%s", logname,
		    ndx_str);
	}
	if (ndx_str[0] != '\0')
		return (ndx_str);
	else
		return (mdy);
}

/*
 * Name:		backoff
 * Description:	sleeps for a certain # of seconds after a network
 *		failure.
 * Scope:	public
 * Arguments:	none
 * Returns:	none
 */
void
backoff()
{
	static int initted = FALSE;
	int backoff;
	long seed;

	if (!initted) {
		/* seed the rng */
		(void) _get_random_info(&seed, sizeof (seed));
		srand48(seed);
		initted = TRUE;
	}

	backoff = drand48() * (double)cur_backoff;
	(void) sleep(backoff);
	if (cur_backoff < MAX_BACKOFF) {
		/*
		 * increase maximum time we might wait
		 * next time so as to fall off over
		 * time.
		 */
		cur_backoff *= BACKOFF_FACTOR;
	}
}

/*
 * Name:		reset_backoff
 * Description:	notifies the backoff service that whatever was
 *		being backoff succeeded.
 * Scope:	public
 * Arguments:	none
 * Returns:	none
 */
void
reset_backoff()
{
	cur_backoff = MIN_BACKOFF;
}

/*
 * Name:	_get_random_info
 * Description:	generate an amount of random bits.  Currently
 *		only a small amount (a long long) can be
 *		generated at one time.
 * Scope:	private
 * Arguments:	buf	- [RO, *RW] (char *)
 *			  Buffer to copy bits into
 *		size	- amount to copy
 * Returns:	0 on success, non-zero otherwise.  The buffer is filled
 *		with the amount of bytes of random data specified.
 */
static int
_get_random_info(void *buf, int size)
{
	struct timeval tv;
	typedef struct {
		long low_time;
		long hostid;
	} randomness;
	randomness r;
	(void) gettimeofday(&tv, (struct timezone *)0);

	/* Wouldn't it be nice if we could hash these */
	r.low_time = tv.tv_usec;
	r.hostid = gethostid();

	if (sizeof (r) < size) {
		/*
		 * Can't copy correctly
		 */
		return (-1);
	}
	(void) memcpy(buf, &r, size);
	return (0);
}

/*
 * Name:	trim_whitespace
 * Description:	Trims whitespace from a string
 *
 * Scope:	private
 * Arguments:	string	- string to trim.  It is assumed
 *		this string is writable up to it's entire
 *		length.
 * Returns:	none
 */
void
trim_whitespace(char *str)
{
	int len, newlen, bindex, findex;

	if (str == NULL) {
		return;
	}

	if ((len = strlen(str)) == 0) {
	    /* empty string */
	    return;
	}


	/* find index of beginning of non-whitespace */
	findex = 0;
	while ((findex < len) && isspace(str[findex])) {
	    findex++;
	}

	if (findex == len) {
	    /* all-whitespace string */
	    str[0] = '\0';
	    return;
	}

	/* find index of start of trailing whitespace */
	bindex = len;
	while (isspace(str[bindex - 1])) {
	    bindex--;
	}

	newlen = bindex - findex;
	if ((findex > 0) && (newlen > 0)) {
		(void) memcpy(str, str + findex, newlen);
	}
	str[newlen] = '\0';
}
