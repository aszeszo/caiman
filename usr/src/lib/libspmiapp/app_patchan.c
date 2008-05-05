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



/*
 * Module:      app_patchan.c
 * Group:       libspmiapp
 * Description:
 *      Module for interacting with the back end of the
 *      Patch Analyzer.
 */

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/stat.h>

#include "spmiapp_api.h"
#include "spmisoft_api.h"
#include "spmicommon_api.h"
#include "app_strings.h"

#define	ANALYZER_REL_PATH "../Misc/analyze_patches"
#define	OUTBUF_SIZE 80

/* Path to patch analyzer */
static char *path_to_analyzer = NULL;

/* Path to media for analysis */
static char *path_to_media = NULL;

/* Results of analysis */
static PAResults *results = NULL;

/* Private functions */
static PACheckRC PACheckForAnalyzer(void);
static PACheckRC PACheckEligibility(void);
static PAAnalyzeRC analyze_parse_accum(PAResults *results, char *buf);
static PAAnalyzeRC analyze_parse_downgrade(PAResults *results, char *buf);
static PAAnalyzeRC analyze_parse_removal(PAResults *results, char *buf);
static void free_array(void **array, int num);

/*
 * PUBLIC FUNCTIONS
 */

/*
 * Function: PANeedsAnalysis
 * Description:
 * 	Determine whether or not the analyzer is to be used
 *      for this upgrade.  Analysis is to be done if the
 *      analyzer is present on the media and if the upgrade
 *      is within a release.
 * Scope:       PUBLIC
 * Parameters:  none
 * Return:      [PACheckRC]
 *   PACheckOK         : Analysis can be performed
 *   PACheckNoAnalyzer : The analyzer wasn't found on the media
 *   PACheckNotEligible: Upgrade not eligible for analysis
 *   PACheckError      : Error encountered during checks
 * Notes:
 */
PACheckRC
PANeedsAnalysis(void)
{
	PACheckRC rc;

	if ((rc = PACheckForAnalyzer()) == PACheckOK) {
		return (PACheckEligibility());
	}
	return (rc);
}

/*
 * Function: PADoAnalysis
 * Description:
 *      Perform Patch Analysis
 * Scope:       PUBLIC
 * Parameters:  [PAResults **]
 *  No results returned if NULL supplied.
 * Return:      [PAAnalyzeRC]
 *  Exit status of the analysis.
 * Notes:
 */
PAAnalyzeRC
PADoAnalysis(PAResults **resarg)
{
	FILE *fp;
	char *cmd;
	char buf[OUTBUF_SIZE];  /* A line of output from the script */
	PAAnalyzeRC rc = PAAnalyzeOK;
	PAResults *res;

	/*
	 * This would happen if somebody tried to run an analysis
	 * without checking for the analyzer first.
	 */
	if (path_to_analyzer == NULL)
		return (PAAnalyzeErrNoPA);

	cmd = (char *)xmalloc(strlen(path_to_analyzer) +
			      strlen(get_rootdir()) +
			      strlen(path_to_media) +
			      34);
	(void) sprintf(cmd, "%s -t -R %s -N %s 2>&1 |tee /tmp/pa.log",
			path_to_analyzer, get_rootdir(), path_to_media);

	res = (PAResults *)xcalloc(sizeof (PAResults));
	res->num_removals = 0;
	res->num_downgrades = 0;
	res->num_accumulations = 0;

	if ((fp = popen(cmd, "r")) == NULL) {
		free(cmd);
		free(res);
		return (PAAnalyzeErrPAExec);
	}

	buf[OUTBUF_SIZE-1] = '\0';
	while (fgets(buf, OUTBUF_SIZE-1, fp) != NULL && rc == PAAnalyzeOK) {
		/* Check read size */
		if (strlen(buf) == 0 || strlen(buf) == OUTBUF_SIZE-1) {
			rc = PAAnalyzeErrParse;
		} else {
			/* Take out the newline */
			buf[strlen(buf)-1] = '\0';

			/* Process script output */
			switch (buf[0]) {
			case 'A':  /* Accumulation */
				rc = analyze_parse_accum(res, buf);
				break;

			case 'D':  /* Downgrade */
				rc = analyze_parse_downgrade(res, buf);
				break;

			case 'R':  /* Removal */
				rc = analyze_parse_removal(res, buf);
				break;

			case 'U':  /* Upgrade - ignored for now */
				break;

			default:   /* Anything else is an error */
				rc = PAAnalyzeErrParse;
				break;
			}
		}
	}

	(void) pclose(fp);
	free(cmd);

	/*
	 * Replace global results with this one if the analysis completed
	 * successfully.
	 */
	if (rc == PAAnalyzeOK) {
		if (results != NULL)
			PAFreeResults(results);
		results = res;
	}

	/* Return pointer if requested */
	if (resarg != NULL)
		*resarg = res;

	return (rc);
}

/*
 * Function: PAGetResults
 * Description:
 *	Get results (if any) from a previous analysis.
 * Scope:	PUBLIC
 * Parameters:	None
 * Return:	[PAResults *]
 *	PAResults * - results struct from previous analysis
 *	NULL        - if no analysis has been done, or if the
 *		      results of the previous analysis have
 *		      been freed.
 */
PAResults *
PAGetResults(void)
{
	return (results);
}


/*
 * Function: PAFreeResults
 * Description:
 *      Free a PAResults structure
 * Scope:       PUBLIC
 * Parameters:  PAResults *results - the structure to be freed
 * Return:      none
 * Notes:
 */
void
PAFreeResults(PAResults *results)
{
	if (results == NULL)
		return;

	free_array((void **)results->removals, results->num_removals);

	free_array((void **)results->downgrade_ids, results->num_downgrades);
	free_array((void **)results->downgrade_from, results->num_downgrades);
	free_array((void **)results->downgrade_to, results->num_downgrades);

	free_array((void **)results->accumulateds, results->num_accumulations);
	free_array((void **)results->accumulators, results->num_accumulations);
}

/*
 * PRIVATE FUNCTIONS
 */

/*
 * Function: PALookForAnalyzer
 * Description:
 *      Determine whether or not the media contains the Patch
 *      Analyzer back end.
 * Scope:       PRIVATE
 * Parameters:  none
 * Return:      [PACheckRC]
 *   PACheckOK        : Patch Analyzer was located on the media
 *   PACheckNoAnalyzer: Patch Analyzer not found
 *   PACheckError     : An error was encountered looking for the analyzer
 * Notes:
 */
static PACheckRC
PACheckForAnalyzer(void)
{
	Module *mod;
	char *papath;
	int pathlen;
	struct stat pastat;

	/* Search each media for the Analyzer */
	for (mod = get_media_head(); mod != NULL; mod = mod->next) {

		/*
		 * Make sure it's a non-INSTALLED, non-INSTALLED_SVC
		 * Solaris Product
		 */
		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC ||
		    mod->sub->type != PRODUCT ||
		    strcmp(mod->sub->info.prod->p_name, "Solaris") != 0) {
			continue;
		}

		/* Build path to analyzer */
		pathlen = strlen(mod->sub->info.prod->p_pkgdir) +
		    strlen(ANALYZER_REL_PATH) + 2;
		papath = (char *)xmalloc(sizeof (char) * pathlen);

		(void) sprintf(papath, "%s/%s", mod->sub->info.prod->p_pkgdir,
					    ANALYZER_REL_PATH);

		if (stat(papath, &pastat) < 0) {
			if (errno != ENOENT) {
				free(papath);
				return (PACheckError);
			}
		} else {
			/* Found the analyzer.  Save the location */
			if (path_to_analyzer != NULL)
				free(path_to_analyzer);
			path_to_analyzer = papath;
			path_to_media = mod->info.media->med_dir;
			return (PACheckOK);
		}

		/* Not found on this media */
		free(papath);
	}

	return (PACheckNoAnalyzer);
}

/*
 * Function: PACheckEligibility
 * Description:
 *      Determine whether or not the upgrade warrants patch
 *      analysis.  Only intra-release upgrades (upgrades from,
 *      for example, 2.7 to 2.7 3/99) are eligible for patch
 *      analysis.
 * Scope:       PRIVATE
 * Parameters:  None
 * Return:      [int]
 *  PACheckOK         : Upgrade eligible for analysis
 *  PACheckNotEligible: Upgrade not eligible for analysis
 *  PACheckError      : Error determining eligibility
 * Notes:  We don't yet check the services - just the installed products.
 */
static PACheckRC
PACheckEligibility(void)
{
	Module *mod;
	char *prodvers = NULL;
	char *instvers = NULL;

	/* Find the version to which we are upgrading */
	for (mod = get_media_head(); mod != NULL && mod->info.media != NULL;
	    mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED) {
			instvers = mod->sub->info.prod->p_version;
		} else if (mod->info.media->med_type != INSTALLED_SVC &&
		    mod->sub != NULL && mod->sub->type == PRODUCT &&
		    mod->sub->info.prod != NULL &&
		    mod->sub->info.prod->p_name != NULL &&
		    strcmp(mod->sub->info.prod->p_name, "Solaris") == NULL) {
			prodvers = mod->sub->info.prod->p_version;
		}
	}

	/* Compare with the version on the slice to be upgraded */
	if (!prodvers || !instvers) {
		return (PACheckNotEligible);
	} else if (strcmp(prodvers, instvers) == NULL) {
		return (PACheckOK);
	} else {
		return (PACheckNotEligible);
	}
}

/*
 * Function: analyze_parse_accum
 * Description:
 *	Parse a patch accumulation output line generated by the
 *	analyzer script
 *
 *	The line looks like this:
 *
 *	  A X Y
 *
 *	Where X is the accumulated and Y is the accumulator
 *
 * Scope:       PRIVATE
 * Parameters:
 *     PAResults *results - the results structure
 *              char *buf - buffer containing the input line
 * Return:
 *     PAAnalyzeRC - PAAnalyzeOK       if parsing succeeded
 *                 - PAAnalyzeErrParse if parsing failed
 */
static PAAnalyzeRC
analyze_parse_accum(PAResults *results, char *buf)
{
	char *accumulated;
	char *accumulator;
	char *c;

	/* Read X - the accumulated */
	buf += 2; /* Start of accumulated */
	if ((c = strchr(buf, ' ')) == NULL)
		return (PAAnalyzeErrParse);
	*c = '\0';
	accumulated = xstrdup(buf);
	*c = ' ';

	/* Read Y - the accumulator */
	buf = c + 1;
	if (strchr(buf, ' ') != NULL)
		/* Should only be 3 words */
		return (PAAnalyzeErrParse);
	accumulator = xstrdup(buf);

	results->num_accumulations++;

	results->accumulateds = (char **)xrealloc(results->accumulateds,
						    sizeof (char *) *
						    results->num_accumulations);
	results->accumulateds[results->num_accumulations-1] = accumulated;

	results->accumulators = (char **)xrealloc(results->accumulators,
						    sizeof (char *) *
						    results->num_accumulations);
	results->accumulators[results->num_accumulations-1] = accumulator;

	return (PAAnalyzeOK);
}

/*
 * Function: analyze_parse_downgrade
 * Description:
 *	Parse a patch downgrade output line generated by the
 *	analyzer script
 *
 *	The line looks like this:
 *
 *	  D X Y Z
 *
 *	Where X is the patch ID, Y is the from rev, and
 *	Z is the to rev
 *
 * Scope:       PRIVATE
 * Parameters:
 *     PAResults *results - the results structure
 *              char *buf - buffer containing the input line
 * Return:
 *     PAAnalyzeRC - PAAnalyzeOK       if parsing succeeded
 *                 - PAAnalyzeErrParse if parsing failed
 */
static PAAnalyzeRC
analyze_parse_downgrade(PAResults *results, char *buf)
{
	char *patchid;
	char *from;
	char *to;
	char *c;

	/* Read X - the patch ID */
	buf += 2; /* Start of patch ID */
	if ((c = strchr(buf, ' ')) == NULL)
		return (PAAnalyzeErrParse);
	*c = '\0';
	patchid = xstrdup(buf);
	*c = ' ';

	/* Read Y - the from rev */
	buf = c + 1;
	if ((c = strchr(buf, ' ')) == NULL)
		return (PAAnalyzeErrParse);
	*c = '\0';
	from = xstrdup(buf);
	*c = ' ';

	/* Read Z - the to rev */
	buf = c + 1;
	if (strchr(buf, ' ') != NULL)
		/* Should only be 4 words */
		return (PAAnalyzeErrParse);
	to = xstrdup(buf);

	results->num_downgrades++;

	results->downgrade_ids = (char **)xrealloc(results->downgrade_ids,
						    sizeof (char *) *
						    results->num_downgrades);
	results->downgrade_ids[results->num_downgrades-1] = patchid;

	results->downgrade_from = (char **)xrealloc(results->downgrade_from,
						    sizeof (char *) *
						    results->num_downgrades);
	results->downgrade_from[results->num_downgrades-1] = from;

	results->downgrade_to = (char **)xrealloc(results->downgrade_to,
						    sizeof (char *) *
						    results->num_downgrades);
	results->downgrade_to[results->num_downgrades-1] = to;

	return (PAAnalyzeOK);
}

/*
 * Function: analyze_parse_removal
 * Description:
 *	Parse a patch removal output line generated by the
 *	analyzer script
 *
 *	The line looks like this:
 *
 *	  R X
 *
 *	Where X is the patch
 *
 * Scope:       PRIVATE
 * Parameters:
 *     PAResults *results - the results structure
 *              char *buf - buffer containing the input line
 * Return:
 *     PAAnalyzeRC - PAAnalyzeOK       if parsing succeeded
 *                 - PAAnalyzeErrParse if parsing failed
 */
static PAAnalyzeRC
analyze_parse_removal(PAResults *results, char *buf)
{
	char *patch;

	/* Read X - the patch */
	buf += 2; /* Start of patch */
	if (strchr(buf, ' ') != NULL)
		/* Should only be 2 words */
		return (PAAnalyzeErrParse);
	patch = xstrdup(buf);

	results->num_removals++;

	results->removals = (char **)xrealloc(results->removals,
					    sizeof (char *) *
					    results->num_removals);
	results->removals[results->num_removals-1] = patch;

	return (PAAnalyzeOK);
}


/*
 * Function: free_array
 * Description:
 *      Free the elements of an array
 * Scope:       PRIVATE
 * Parameters:
 *     void *array[] - the array to be freed
 *     int num       - the number of elements in the array
 * Return: none
 */
static void
free_array(void **array, int num)
{
	int i;

	for (i = 0; i < num; i++)
		if (array[i] != NULL)
			free(array[i]);
}
