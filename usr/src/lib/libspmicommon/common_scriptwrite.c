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

#pragma ident	"@(#)common_scriptwrite.c	1.5	07/11/12 SMI"

#include <assert.h>
#include <string.h>
#include "spmicommon_lib.h"
#include "common_strings.h"

#define	SCRIPTBUFSIZE 1024
#define	SCRIPTTOKSIZE 40		/* Maximum size of a script token */
#define	SCRIPTTOKNUM  10		/* Maximum number of unique tokens */

static int	g_seq = 1;

/* Public Function Prototypes */

void		scriptwrite(FILE *, uint, char **, ...);

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * scriptwrite()
 *	Write out specified script fragment to output file, replacing
 *	specified tokens by values.
 *
 *	expected arguments:
 *		FILE	*fp;			file pointer
 *		u_int	format			format flag for write_message()
 *		char	**cmds;			array of shell commands
 *		{char	*token, *value}*	up to SCRIPTTOKNUM token-value
 *						pairs
 *		char	*(0)			to mark end of list
 *
 *	The array of shell commands will contain 2 sets of strings delimeted
 *	by a null string.
 *	The first will be used to generate the actual upgrade shell script,
 *	and will contain token placeholders identified by @TOKEN@.  These will
 *	be replaced by their actual values before writing.
 *	The second set of strings will begin with:
 *		"DryRun @TOKEN0@ @TOKEN1@ ..."
 *	Followed by any text that will be printed on the screen.
 *	    If the text needs translation, it will be of the form:
 *		"gettext SUNW_INSTALL_LIBSVC The actual text...`"
 *	    Any tokens will be represented by $0n to avoid confusion during
 *	    localization, and will be replaced by ther actual values before
 *	    writing.
 *	    Also, the string "gettext SUNW_INSTALL_LIBSVC" will be
 *	    stripped along with the trailing "`"
 *
 *	If DryRun AND trace_level is set > 0, we'll still write the script.
 *
 * WARNINGS:
 *	The output string must NOT be longer than SCRIPTBUFSIZE
 *	Tokens must NOT be longer than SCRIPTTOKSIZE.  There cannot be more
 *	than SCRIPTTOKNUM tokens passed to this function.
 * Return:
 *	none
 * Status:
 *	public
 */
void
scriptwrite(FILE *fp, u_int format, char **cmdarray, ...)
{
	va_list ap;
	char	*token[SCRIPTTOKNUM], *value[SCRIPTTOKNUM];
	int	TokenIndex[SCRIPTTOKNUM];
	char	thistoken[SCRIPTTOKSIZE];
	char	buf[SCRIPTBUFSIZE], ibuf[SCRIPTBUFSIZE];
	int	count;
	int	DryRun = 0;
	int	DryRunHdr = 0;
	int	PrintDryRun = 0;
	int	PassCount = 1;
	int	i, j, len, slen, TokI;
	char	c, *cp, *dst;
	char	*bp;

	/*
	 * Copy in the tokens and values.  Make sure the caller didn't overflow
	 * whatever arbitrary limits we happen to be using now.
	 */
	va_start(ap, cmdarray);
	count = 0;
	for (cp = va_arg(ap, char *); cp; cp = va_arg(ap, char *)) {
		assert(count < SCRIPTTOKNUM);
		assert(strlen(cp) < SCRIPTTOKSIZE);
		token[count] = cp;
		value[count] = va_arg(ap, char *);

		count++;
	}
	va_end(ap);

	i = TokI = 0;
	if (GetSimulation(SIM_EXECUTE)) {
		PassCount = 2;
		if (get_trace_level() == 0) {
			/*
			 * If we're in DryRun, but not tracing, skip down to
			 * the "DryRun" eyecatcher.
			 */
			for (i = 0; *(cp = cmdarray[i]) != '\0'; i++)
				;
		}
	}
	while (PassCount) {
	    for (; *(cp = cmdarray[i]) != '\0'; i++, DryRunHdr++) {
		if (DryRun && (strncmp(cp, "gettext", 7) == 0)) {
			/*
			 * Translate it before doing token replacements:
			 * Strip all chars up to "'",
			 * Strip trailing char (assumed to be "'"
			 */
			dst = strchr(cp, '\'');
			if (*dst != '\0') {
				dst++;
				strcpy(ibuf, dst);
				ibuf[strlen(ibuf)-1] = NULL;
				cp = dgettext("SUNW_INSTALL_LIBSVC", ibuf);
			}
		}
		/*
		 * cp is now pointing to the source string
		 * bp is pointing to the destination buffer
		 */
		bp = buf;
		while ((c = *cp++) != '\0') {
			switch (c) {

			case '@':
				dst = thistoken;
				while ((*dst++ = *cp++) != '@')
					;
				*--dst = '\0';
				if (strcmp(thistoken, "SEQ") == 0) {
					len = sprintf(bp, "%d", g_seq);
					if (len > 0)
						bp += len;
					break;
				}
				for (j = 0; j < count; j++) {
					/*
					 * If the token matches
					 *   If this is a dryrun && we're
					 *   processing the header
					 *	Note the index of this token
					 *	for later substitution
					 *   else
					 *	replace the token by its value
					 */
					if (strcmp(thistoken, token[j]) == 0) {
						if (!DryRun || DryRunHdr) {
							slen = strlen(value[j]);
							strncpy(bp, value[j],
							    slen);
							bp += slen;
						} else if (
						    DryRun && !DryRunHdr) {
							TokenIndex[TokI++] = j;
						}
						break;
					}
				}
				if (j == count) {
					write_message(SCR, WARNMSG, LEVEL0,
					    MSG1_BAD_TOKEN, thistoken);
				}
				break;

			case '$':
				if (!DryRun) {
					*bp++ = c;
					break;
				}
				/*
				 * Make sure it's '$0n'
				 */
				if (*cp != '0') {
					*bp++ = c;
					break;
				}
				if (!isdigit(*(cp+1))) {
					*bp++ = c;
					break;
				}
				/*
				 * Got it, copy value if it's valid
				 */
				j = TokenIndex[atoi(cp+1)];
				if (j >= 0) {
					slen = strlen(value[j]);
					strncpy(bp, value[j], slen);
					bp += slen;
					cp += 2;
				} else {
					*bp++ = c;
				}
				break;

			default:
				*bp++ = c;
				break;
			}
		}
		*bp = NULL;
		if (PrintDryRun) {
			/*
			 * If we're printing DryRun info, and we're past
			 * the eyecatcher, write_message() the buffer
			 */
			if (DryRunHdr)
				write_message_nofmt(LOGSCR, STATMSG, format,
						    buf);
		} else {
			(void) fprintf(fp, "%s\n", buf);
		}
	    }
	    PassCount--;
	    /*
	     * If we're not in DryRun, PassCount should be 0 now
	     */
	    if (GetSimulation(SIM_EXECUTE) && (PassCount == 1)) {
		i++;
		if (strncmp(cmdarray[i], "DryRun", 6)) {
			write_message(SCR, WARNMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_LIBSVC",
			    "Internal error: Dry Run message missing"));
			/*
			 * Just use the shell script string
			 */
			i = 0;
			DryRunHdr = 1;
		} else {
			DryRunHdr = 0;
			DryRun = 1;
			TokI = 0;
			for (j = 0; j < SCRIPTTOKNUM; j++) {
				TokenIndex[j] = -1;
			}
		}
		PrintDryRun = 1;
	    }
	}
	g_seq++;
}
