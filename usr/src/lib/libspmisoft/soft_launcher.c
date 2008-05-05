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
#endif

/*
 *	File:		soft_launcher.c
 *
 *	Description:	This file contains launcher related functions
 */

#include <dirent.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include "spmisoft_lib.h"
#include "soft_launcher.h"
#include "soft_locale.h"


/* local functions */
static char *get_installed_locales();
static StringList *sortVirtuals(char **, int);
static StringList *getPostEntries(int);
static StringList *getLangEntries(char *, int);
static StringList *getNofNEntries(char *, int);
static StringList *extract2of2Products(char *);
static void getVirtualNums(StringList **, StringList **);
static void renumberEntries(int, StringList **);
static SolCD_Info *readSolCDInfo(char *);
static void preserve_etc_default_init(void);

/*
 * Public functions
 */


char *locids[] = {
	"fr",
	"de",
	"es",
	"it",
	"sv",
	"zh_HK",
	"zh_TW",
	"zh",
	"ja",
	"ko",
	NULL
};

char *langprods[] = {
	"French",
	"German",
	"Spanish",
	"Italian",
	"Swedish",
	"TraditionalChineseHongKong",
	"Taiwanese",
	"Chinese",
	"Japanese",
	"Korean",
	NULL
};

/*
 * Name:	(swi_)parsePackagesToBeAdded
 * Description:	Runs parsePackagesToBeAdded. This parses the
 *		/a/var/sadm/system/data/packages_to_be_added file
 *		and puts virtual cd 2 and virtual cd 3 packages in
 *		/a/var/sadm/launcher/virtualpkgs2 and virtualpkgs3 files,
 *		respectively.
 * Scope:	public
 * Arguments:	none
 * Returns:	none
 */
void
swi_parsePackagesToBeAdded()
{
	system("/usr/lib/install/data/wizards/bin/parsePackagesToBeAdded " \
		"2>/dev/null 2>&1");
}


/*
 * Name:	(swi_)create_dispatch_table
 * Description:	Create the dispatch_table for the launcher
 * Scope:	public
 * Arguments:	none
 * Returns:	none
 */
void
swi_create_dispatch_table()
{
	int startFrom;
	char dotvirtual[MAXPATHLEN];
	char *vfile = (char *)NULL;
	StringList *savelist = (StringList *)NULL;
	StringList *vnums = (StringList *)NULL;
	StringList *vlangnums = (StringList *)NULL;
	StringList *tmplist = (StringList *)NULL;
	StringList *strlist = (StringList *)NULL;


	/*
	 * Don't do anything if running simulation
	 */
	if (GetSimulation(SIM_ANY)) {
		return;
	}

	/*
	 * Create /a/var/sadm/launcher
	 */
	mkdirs(LAUNCH_DIR);

	/*
	 * Delete dispatch_table if one exists
	 */
	unlink(DISPATCH_TABLE);

	/*
	 * Run parsePackagesToBeAdded to find out if there is
	 * anything left to install on other Solaris and/or
	 * Lang CDs
	 */
	parsePackagesToBeAdded();

	/*
	 * For each .virtualpkgsN file (represented by the N's in
	 * virtualNums), create a set of entries for the dispatch_table.
	 */

	getVirtualNums(&vnums, &vlangnums);

	startFrom = 1;
	for (; vnums; vnums = vnums->next) {
		vfile = vnums->string_ptr;
		(void) snprintf(dotvirtual, sizeof (dotvirtual), "%s/%s%s",
				VAR_SADM_DATA, DOTVIRTUALPKGS, vfile);
		if (access(dotvirtual, R_OK) != 0) {
			continue;
		}

		tmplist = getNofNEntries(vnums->string_ptr, startFrom);
		savelist = tmplist;

		if (StringListCount(tmplist) > 0) {
			startFrom++;
		}
		/* copy these entries (tmplist) to strlist */
		for (; tmplist; tmplist = tmplist->next) {
			StringListAdd(&strlist, tmplist->string_ptr);
		}
		StringListFree(savelist);
	}

	for (; vlangnums; vlangnums = vlangnums->next) {
		vfile = vlangnums->string_ptr;
		(void) snprintf(dotvirtual, sizeof (dotvirtual), "%s/%s%s",
				VAR_SADM_DATA, DOTVIRTUALPKGSLANG, vfile);
		if (access(dotvirtual, R_OK) != 0) {
			continue;
		}

		tmplist = getLangEntries(vlangnums->string_ptr, startFrom);
		savelist = tmplist;

		if (StringListCount(tmplist) > 0) {
			startFrom++;
		}
		/* copy these entries (tmplist) to strlist */
		for (; tmplist; tmplist = tmplist->next) {
			StringListAdd(&strlist, tmplist->string_ptr);
		}
		StringListFree(savelist);
	}

	/*
	 * Determine if we need to run postinstall wizard.
	 * If so, write out the itags file and the osdirectory
	 * where the postinstall wizard will find the patches, etc.
	 */
	tmplist = getPostEntries(startFrom);
	savelist = tmplist;

	/* copy entries (tmplist) to strlist and free tmplist */
	for (; tmplist; tmplist = tmplist->next) {
		StringListAdd(&strlist, tmplist->string_ptr);
	}
	StringListFree(savelist);
	startFrom++;


	/*
	 * Determine if there are other products to install
	 */
	tmplist = (StringList *) readStringListFromFile(PRODUCT_TABLE);
	if (tmplist) {
		renumberEntries(startFrom, &tmplist);
	}

	/* copy entries (tmplist) to strlist and free tmplist */
	for (; tmplist; tmplist = tmplist->next) {
		StringListAdd(&strlist, tmplist->string_ptr);
	}
	StringListFree(tmplist);

	/*
	 * Write out dispatch_table
	 */
	if (StringListCount(strlist) > 0) {
		if (! writeStringListToFile(DISPATCH_TABLE, strlist)) {
			return;
		}
		StringListFree(strlist);
	}
}


/*
 * Name:	(swi_)setup_launcher
 * Description:	Setup files/dispatch_table for launcher
 * Scope:	public
 * Arguments:	none
 * Returns:	none
 */
void
swi_setup_launcher(int autoreboot)
{
	if (is_flash_install()) {
		mkdirs(LAUNCH_DIR);
		if (isBootFromDisc()) {
			mkdirs(DOT_BOOTDISC_DIR);
		}
		return;
	}

	(void) create_dispatch_table();

	if (! isAutoEject()) {
		mkdirs(DOT_NOEJECT_DIR);
	}

	if (autoreboot) {
		mkdirs(DOT_REBOOT_DIR);
	}

	if (isBootFromDisc()) {
		mkdirs(DOT_BOOTDISC_DIR);
	}

	preserve_etc_default_init();
}


/*
 * Private functions
 */

/*
 * Name:	getPostEntries
 * Description:	Get the postinstall dispatch_table entries, starting at W<wnum>.
 * Scope:	private
 * Arguments:	wnum	- int of "W" number for postinstall entries
 *			  in dispatch_table
 * Returns:	strlist*	- StringList of dispatch_table entries
 */
static StringList *
getPostEntries(int wnum)
{
	Product *prod = (Product *)NULL;
	Module *os = (Module *)NULL;
	Module *curmod = (Module *)NULL;
	StringList *postlist = (StringList *)NULL;
	StringList *itagslist = (StringList *)NULL;
	StringList *tmplist = (StringList *)NULL;
	OS_Info *osinfo = (OS_Info *)NULL;
	char *clusterID = (char *)NULL;
	char *thisID = (char *)NULL;
	char buf[BUFSIZ];

	/*
	 * Determine if we need to run postinstall wizard.
	 * If so, write out the itags file and the osdirectory
	 * where the postinstall wizard will find the patches, etc.
	 */
	prod = get_current_product()->info.prod;
	curmod = get_current_metacluster();
	clusterID = (char *)curmod->info.mod->m_pkgid;

	/*
	 * find table info for selected metacluster
	 */
	osinfo = prod->p_os_info->info.osinf;
	for (os = prod->p_os_info; os; os = os->next) {
		osinfo = os->info.osinf;
		thisID = osinfo->prodToc->info.pdinf->pdfile->cluster;
		if (strcmp(thisID, clusterID) == 0) {
			break;
		}
	}

	/*
	 * see if there are any itags in selected metacluster
	 */
	itagslist = (StringList *) osinfo->prodToc->info.pdinf->pdfile->itags;

	/*
	 * if there are itags, write them out to the .itags file
	 */
	if (StringListCount(itagslist) > 0) {
		writeStringListToFile(ITAGS_FILE, itagslist);
		StringListAdd(&tmplist, osinfo->ospath);
		writeStringListToFile(OSDIR_FILE, tmplist);
		StringListFree(tmplist);

		/*
		 * Delete post_table if it exists
		 */
		unlink(POST_FILE);

		itagslist = NULL;
		/*
		 * construct lines with the CDname, VOLID, LaunchCommand,
		 * MiniRootOpts, and Products
		 */
		(void) snprintf(buf, sizeof (buf),
				"W%i.LaunchCommand=%s/bin/postinstaller" \
				" -warp Summary... -autonext Summary...",
				wnum,
				VAR_SADM_WEBSTART);
		StringListAdd(&postlist, buf);

		(void) snprintf(buf, sizeof (buf),
				"W%i.MiniRootOpts=-R /a", wnum);
		StringListAdd(&postlist, buf);

		/*
		 * Check if we must install everything else after the reboot
		 */
		if (installAfterReboot()) {
			(void) snprintf(buf, sizeof (buf),
				"W%i.Product1.MiniRoot=NO", wnum);
		} else {
			(void) snprintf(buf, sizeof (buf),
				"W%i.Product1.MiniRoot=YES", wnum);
		}
		StringListAdd(&postlist, buf);
	}
	return (postlist);
}


/*
 * Name:	extract2of2Products
 * Description:	Extract the 2of2 entries from the product_table
 * Scope:	private
 * Arguments:	none
 * Returns:	strlist	- StringList of 2of2 dispatch_table entries
 */
static StringList *
extract2of2Products(char *volid)
{
	FILE *fp = (FILE *)NULL;
	StringList *prodlist = (StringList *)NULL;
	StringList *prodlistsave = (StringList *)NULL;
	StringList *tablelist = (StringList *)NULL;
	StringList *tablelistsave = (StringList *)NULL;
	StringList *newlist = (StringList *)NULL;
	StringList *strlist = (StringList *)NULL;
	char buf[BUFSIZ];
	char *line = (char *)NULL;
	char *dotPtr;
	char *thisVolId;
	char *lastentry;
	int cdnum;
	int have2of2 = 0;
	int found2of2 = 0;
	int currentnum = -1;


	if ((fp = fopen(PRODUCT_TABLE, "r")) == (FILE *)NULL) {
		return (NULL);
	}

	/*
	 * read contents of /tmp/product_table into a StringList
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else {
			StringListAdd(&tablelist, buf);
		}
	}
	(void) fclose(fp);

	/*
	 * Gather all entries for a particular cd into prodlist.
	 * When we start the next set of cd entries, write all
	 * of the current prodlist entries into either newlist
	 * (which will become the new product_table) or strlist
	 * if the volID matches the 2of2 volID.
	 */
	tablelistsave = tablelist;
	for (; tablelist; tablelist = tablelist->next) {
		line = tablelist->string_ptr;
		dotPtr = (char *)strchr(line, '.');
		if (!dotPtr) {
			continue;
		}
		if (! (char *)strchr(line, '=')) {
			continue;
		}

		*dotPtr = '\0';
		cdnum = atoi(line+1);
		*dotPtr = '.';
		if (currentnum == -1) {
			currentnum = cdnum;
		}

		lastentry = (char *)NULL;
		if (cdnum != currentnum) {
			/*
			 * We have the first entry for the next cd.
			 * Don't add it to prodlist, but save it for the
			 * next set of entries.
			 */
			lastentry = line;
		} else {
			StringListAdd(&prodlist, line);
		}

		if (cdnum != currentnum || ! tablelist->next) {
			/*
			 * We are finished with this cd's set of entries.
			 * See if they contain 2of2 products. Look for
			 * the volume ID and see if it matches.
			 */
			prodlistsave = prodlist;
			for (; prodlist; prodlist = prodlist->next) {
				line = prodlist->string_ptr;
				dotPtr = (char *)strchr(line, '.');
				if (strncmp(dotPtr, ".VOLID=", 7) != 0) {
					continue;
				}

				/*
				 * We have a volID entry. See if the
				 * volID matches the 2of2 id (passed in).
				 * If so, set a flag to process separately.
				 */
				thisVolId = dotPtr + strlen(".VOLID=");
				if (strcasecmp(thisVolId, volid) == 0) {
					have2of2 = 1;
					found2of2 = 1;
				}
				break;
			}
			prodlist = prodlistsave;

			/*
			 * Save the current cd's set of entries. They
			 * either go into strlist if they are vcd2 (2of2)
			 * entries (now extracted) or into newlist
			 * (newlist will become the new product_Table).
			 */
			for (; prodlist; prodlist = prodlist->next) {
				line = prodlist->string_ptr;
				if (have2of2) {
					StringListAdd(&strlist, line);
				} else {
					StringListAdd(&newlist, line);
				}
			}
			have2of2 = 0;

			/*
			 *  get ready for next set of entries
			 */
			StringListFree(prodlistsave);

			/*
			 * if we have a lastentry, means it should be the
			 * first entry of the next set
			 */
			if (lastentry) {
				StringListAdd(&prodlist, lastentry);
			}
			currentnum = cdnum;
		}
	}
	StringListFree(tablelistsave);


	/*
	 * if no 2of2 entries found, leave product table as is
	 */
	if (! found2of2) {
		return (strlist);
	}

	/*
	 * Delete the product_table. If newlist size > 0, we will
	 * write out a new one below. Otherwise, that means that
	 * the only product_table entry was the 2of2 entry and
	 * we don't want the table anymore.
	 */
	unlink(PRODUCT_TABLE);
	if (! newlist || StringListCount(newlist) == 0) {
		return (strlist);
	}

	/*
	 * write out the new product_table
	 */
	tablelistsave = newlist;
	writeStringListToFile(PRODUCT_TABLE, newlist);
	StringListFree(newlist);

	return (strlist);
}


/*
 * Name:	getVirtualNums
 * Description:	Get a list of the numbers of the .virtualpkgs* files in
 *              /a/var/sadm/system/data
 * Scope:	private
 * Arguments:	none
 * Returns:	strlist	- StringList of numbers of .virtualpkgs* files
 */
static void
getVirtualNums(StringList **vnums, StringList **vlangs)
{
	StringList *slist1 = (StringList *)NULL;
	StringList *slist2 = (StringList *)NULL;
	int numCDS = 5;
	int i, k;
	int last1, last2;
	char **nums1;
	char **nums2;
	char *idPtr;
	DIR *dirp;
	struct stat sb;
	struct dirent *dp;

	/* see if os base dir exists  */
	if (stat(VAR_SADM_DATA, &sb) || !S_ISDIR(sb.st_mode)) {
		return;
	}

	if (!(dirp = opendir(VAR_SADM_DATA))) {
		return;
	}

	nums1 = (char **)xcalloc(numCDS * sizeof (char *));
	nums2 = (char **)xcalloc(numCDS * sizeof (char *));
	i = 0;
	k = 0;
	last1 = numCDS;
	last2 = numCDS;

	while ((dp = readdir(dirp)) != NULL) {
		if (streq(dp->d_name, ".") || streq(dp->d_name, "..")) {
			continue;
		}

		/*
		 * add .virtualpkgsX to nums
		 */
		idPtr = (char *)strstr(dp->d_name, DOTVIRTUALPKGS);
		if (! idPtr) {
			continue;
		}

		if (strstr(dp->d_name, DOTVIRTUALPKGSLANG)) {
			*(nums2 + k) =
				xstrdup(idPtr + strlen(DOTVIRTUALPKGSLANG));
			k++;
			if (k == last2) {
				nums2 = (char **)xrealloc(nums2,
					(last2 + numCDS) * sizeof (char *));
				last2 += numCDS;
			}
			*(nums2 + k) = (char *)NULL;
		} else {
			*(nums1 + i) = xstrdup(idPtr + strlen(DOTVIRTUALPKGS));
			i++;
			if (i == last1) {
				nums1 = (char **)xrealloc(nums1,
					(last1 + numCDS) * sizeof (char *));
				last1 += numCDS;
			}
			*(nums1 + i) = (char *)NULL;
		}
	}

	/*
	 * convert nums into a sorted stringlist
	 */
	slist1 = sortVirtuals(nums1, i);
	slist2 = sortVirtuals(nums2, k);
	*vnums = slist1;
	*vlangs = slist2;
	free(nums1);
	free(nums2);
}


/*
 * Name:	sortVirtuals
 * Description:	Sort numbers represented by strings into ascending order
 * Scope:	private
 * Arguments:   nums - pointer to char array of nums
 *              size - number of strings to sort
 * Returns:	strlist	- StringList of sorted numbers (strings)
 */
static StringList *
sortVirtuals(char **nums, int size)
{
	StringList *strlist = (StringList *)NULL;
	int i, k;
	int num1, num2;
	char *tmpnum;

	/*
	 * convert nums into a sorted stringlist
	 */
	for (i = 0; i < size - 1; i++) {
		for (k = i + 1; k < size; k++) {
			num1 = atoi(nums[i]);
			num2 = atoi(nums[k]);
			if (num1 > num2) {
				tmpnum = nums[i];
				nums[i] = nums[k];
				nums[k] = tmpnum;
			}
		}
	}

	for (i = 0; i < size; i++) {
		StringListAdd(&strlist, xstrdup(nums[i]));
	}

	return (strlist);
}

/*
 * Name:	get_installed_locales
 * Description:	Get string of installed locales
 * Scope:	private
 * Arguments:	none
 * Return:	char *  - pointer to allocated string containing comma
 *			  separated listof locales from locales_installed
 *			  file (or empty string)
 */
static char *
get_installed_locales()
{
	char *loctext = (char *)NULL;
	struct stat	statbuf;
	char		path[MAXPATHLEN + 1];
	char		buf[BUFSIZ + 1];
	FILE		*fp;

	snprintf(path, MAXPATHLEN, "%s%s", get_rootdir(), LOCALES_INSTALLED);
	path[MAXPATHLEN] = '\0';

	if (stat(path, &statbuf) || !S_ISREG(statbuf.st_mode) ||
	    (fp = fopen(path, "r")) == NULL) {
		return (xstrdup(""));
	}

	/*
	 * Read and process the LOCALES line from the
	 * locales_installed file.  Return the comma separated list
	 * of locales.
	 */
	while (fgets(buf, BUFSIZ, fp) != NULL) {
		buf[strlen(buf) - 1] = '\0';

		if (strneq(buf, "LOCALES=", 8)) {
			loctext = xstrdup(buf+8);
			break;
		}
	}

	fclose(fp);

	if (loctext == NULL) {
		loctext = xstrdup("");
	}
	return (loctext);

}

/*
 * Name:	getNofNEntries
 * Description:	Get the NofN cd entries, starting at W<wnum>.
 * Scope:	private
 * Arguments:	none
 * Returns:	strlist	- StringList of NofN dispatch_table entries
 */
static StringList *
getNofNEntries(char *dotvirtual, int wnum)
{
	Product *prod = (Product *)NULL;
	char path[MAXPATHLEN];
	char modline[BUFSIZ];
	char buf[BUFSIZ];
	int prodnum;
	char *dotPtr;
	char *ospath = (char *)NULL;
	char *locstr = (char *)NULL;
	char *line = (char *)NULL;
	SolCD_Info *solcdinfo = (SolCD_Info *)NULL;
	StringList *strlist = (StringList *)NULL;
	StringList *prod2of2list = (StringList *)NULL;
	StringList *prodlist = (StringList *)NULL;
	StringList *savelist = (StringList *)NULL;

	if (dotvirtual == NULL) {
		return ((StringList *)NULL);
	}

	prod = get_current_product()->info.prod;

	/*
	 * we have dotvirtual packages to install
	 */
	ospath = prod->p_os_info->info.osinf->ospath;
	(void) snprintf(path, sizeof (path), "%s%s%s",
				ospath, VCDN_INFO, dotvirtual);
	solcdinfo = (SolCD_Info *)readSolCDInfo(path);
	if (solcdinfo == NULL) {
		return ((StringList *)NULL);
	}
	if (! solcdinfo->cdname || ! solcdinfo->installer ||
			! solcdinfo->volid || ! solcdinfo->prodid) {
		/* missing key-value pair */
		return ((StringList *)NULL);
	}

	prod2of2list = extract2of2Products(solcdinfo->volid);
	if (prod2of2list && StringListCount(prod2of2list) > 0) {
		/*
		 * We have products. We want to add the products
		 * following the solarisn wizard.
		 */
		savelist = prod2of2list;
		for (; prod2of2list; prod2of2list = prod2of2list->next) {
			line = prod2of2list->string_ptr;

			/*
			 * Find the product lines. Increment the Product
			 * number by one, since they will now all follow the
			 * solarisn wizard. Save the entries for use below.
			 */
			dotPtr = (char *)strstr(line, ".Product");
			if (!dotPtr) {
				continue;
			}
			line = dotPtr + strlen(".Product");
			dotPtr = (char *)strchr(line, '.');
			*dotPtr = '\0';
			prodnum = atoi(line);
			*dotPtr = '.';
			(void) snprintf(modline, sizeof (modline),
					"W%i.Product%i%s", wnum, ++prodnum,
					dotPtr);
			StringListAdd(&prodlist, modline);
		}
		StringListFree(savelist);

	}

	/*
	 * construct lines with the CDname, VOLID, LaunchCommand,
	 * MiniRootOpts, and Products
	 */
	(void) snprintf(buf, sizeof (buf),
			"W%i.CDName=%s", wnum, solcdinfo->cdname);
	StringListAdd(&strlist, buf);

	(void) snprintf(buf, sizeof (buf),
			"W%i.VOLID=%s", wnum, solcdinfo->volid);
	StringListAdd(&strlist, buf);

	/*
	 * add the install command with -warp and -locales option
	 * All but -locales comes from the sol.info file.
	 */
	locstr = (char *)get_installed_locales();
	if (strlen(locstr) > 0) {
		(void) snprintf(buf, sizeof (buf),
			"W%i.LaunchCommand=%s -locales %s",
				wnum, solcdinfo->installer, locstr);
	} else {
		(void) snprintf(buf, sizeof (buf),
			"W%i.LaunchCommand=%s ",
				wnum, solcdinfo->installer);
	}
	free(locstr);
	StringListAdd(&strlist, buf);

	(void) snprintf(buf, sizeof (buf), "W%i.MiniRootOpts=-R /a", wnum);
	StringListAdd(&strlist, buf);

	(void) snprintf(buf, sizeof (buf),
			"W%i.Product1.PRODID=%s", wnum, solcdinfo->prodid);
	StringListAdd(&strlist, buf);

	/*
	 * Check if we must install everything else after the reboot
	 */
	if (installAfterReboot()) {
		(void) snprintf(buf, sizeof (buf),
					"W%i.Product1.MiniRoot=NO", wnum);
	} else {
		(void) snprintf(buf, sizeof (buf),
					"W%i.Product1.MiniRoot=YES", wnum);
	}
	StringListAdd(&strlist, buf);

	/*
	 * Now add the vcdn products, if any, that we saved above
	 */
	savelist = prodlist;
	for (; prodlist; prodlist = prodlist->next) {
		StringListAdd(&strlist, prodlist->string_ptr);
	}
	StringListFree(savelist);

	return (strlist);
}

/*
 * Name:	getLangEntries
 * Description:	Get the Lang cd entries, starting at W<wnum>.
 * Scope:	private
 * Arguments:	none
 * Returns:	strlist	- StringList of Lang dispatch_table entries
 */
static StringList *
getLangEntries(char *dotvirtual, int wnum)
{
	FILE *fp = (FILE *)NULL;
	Product *prod = (Product *)NULL;
	char path[MAXPATHLEN];
	char buf[BUFSIZ];
	int k;
	int prodnum;
	char *ospath = (char *)NULL;
	char *locstr = (char *)NULL;
	char *tok = (char *)NULL;
	char *str = (char *)NULL;
	SolCD_Info *langcdinfo = (SolCD_Info *)NULL;
	StringList *strlist = (StringList *)NULL;
	StringList *langs = (StringList *)NULL;
	StringList *loclist = (StringList *) NULL;

	if (dotvirtual == NULL) {
		return (strlist);
	}

	prod = get_current_product()->info.prod;

	/*
	 * we have dotvirtual packages to install
	 */
	ospath = prod->p_os_info->info.osinf->ospath;
	(void) snprintf(path, sizeof (path), "%s%s%s",
				ospath, LANG_INFO, dotvirtual);
	langcdinfo = (SolCD_Info *)readSolCDInfo(path);
	if (langcdinfo == NULL) {
		return ((StringList *)NULL);
	}
	if (! langcdinfo->cdname || ! langcdinfo->installer ||
			! langcdinfo->volid) {
		/* missing key-value pair */
		return ((StringList *)NULL);
	}

	/*
	 * construct lines with the CDname, VOLID, LaunchCommand,
	 * MiniRootOpts, and Products
	 */
	(void) snprintf(buf, sizeof (buf),
			"W%i.CDName=%s", wnum, langcdinfo->cdname);
	StringListAdd(&strlist, buf);

	(void) snprintf(buf, sizeof (buf),
			"W%i.VOLID=%s", wnum, langcdinfo->volid);
	StringListAdd(&strlist, buf);

	/*
	 * add the install command with -warp and -locales option
	 * All but -locales comes from the lang.info file.
	 */
	locstr = (char *)get_installed_locales();
	(void) snprintf(buf, sizeof (buf),
			"W%i.LaunchCommand=%s -locales %s",
				wnum, langcdinfo->installer, locstr);
	StringListAdd(&strlist, buf);

	(void) snprintf(buf, sizeof (buf), "W%i.MiniRootOpts=-R /a", wnum);
	StringListAdd(&strlist, buf);

	/*
	 * From the selected locales, obtain the languages to
	 * install. For example, if selected locales are
	 * fr, ko.UTF-8 and zh.GBK, then the languages to
	 * install would be French, Korean, and Chinese.
	 *
	 * The specific locale derivatives get installed by
	 * using the -locales option.
	 */

	prodnum = 1;

	/*
	 * Read from .virtual_packagetoc_langN
	 */
	(void) snprintf(path, sizeof (path), "%s/%s%s",
			VAR_SADM_DATA, DOTVIRTUALPKGTOCLANG, dotvirtual);


	if ((fp = fopen(path, "r")) == (FILE *)NULL) {
		return ((StringList *)NULL);
	}

	/*
	 * Make StringList consisting of locales on lang cd
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strncmp(buf, "SUNW_LOC=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				for (tok = strtok(str, ","); tok;
						tok = strtok(NULL, ",")) {
					StringListAddNoDup(&loclist, tok);
				}
			}
		}
	}
	(void) fclose(fp);

	for (tok = strtok(locstr, ","); tok; tok = strtok(NULL, ",")) {
		/*
		 * make sure locale is a SUNW_LOC on lang cd
		 */
		if (StringListFind(loclist, tok) == NULL) {
			continue;
		}
		for (k = 0; locids[k]; k++) {
			/* this works because zh_HK and zh_TW are ahead of zh */
			if (strstr(tok, locids[k]) == tok) {
				if (StringListFind(langs, langprods[k])) {
					break;
				}
				(void) snprintf(buf, sizeof (buf),
						"W%i.Product%i.Name=%s",
						wnum, prodnum, langprods[k]);
				StringListAdd(&strlist, buf);
				/*
				 * Check if we must install everything else
				 * after the reboot
				 */
				if (installAfterReboot()) {
					(void) snprintf(buf, sizeof (buf),
						"W%i.Product%i.MiniRoot=NO",
						wnum, prodnum);
				} else {
					(void) snprintf(buf, sizeof (buf),
						"W%i.Product%i.MiniRoot=YES",
						wnum, prodnum);
				}
				StringListAdd(&strlist, buf);
				(void) snprintf(buf, sizeof (buf),
						"W%i.Product%i.PRODID=%s",
						wnum, prodnum, langprods[k]);
				StringListAdd(&strlist, buf);
				StringListAdd(&langs, langprods[k]);
				prodnum++;
				break;
			}
		}
	}
	free(locstr);


	return (strlist);
}

/*
 * Name:	renumberEntries
 * Description:	Renumber entries in stringlist starting with startFrom.
 * Scope:	private
 * Arguments:	startFrom	- int of starting Wnum
 *		strlist	- StringList of entries to renumber
 * Returns:	ptr to StringList of renumbered entries
 */
static void
renumberEntries(int startFrom, StringList **strlist)
{
	char *line = (char *)NULL;
	char *restofline = (char *)NULL;
	int currentNum = -1;
	int newnum = startFrom - 1;
	int cdnum;
	char modline[BUFSIZ];
	char *dotPtr;
	StringList *tmplist = (StringList *)NULL;
	StringList *newlist = (StringList *)NULL;


	if (!strlist || StringListCount(*strlist) == 0) {
		return;
	}

	/*
	 * Go through table and bump up "W" number of each entry.
	 */
	tmplist = *strlist;
	for (; tmplist; tmplist = tmplist->next) {
		line = tmplist->string_ptr;
		dotPtr = (char *)strchr(line, '.');
		if (!dotPtr) {
			continue;
		}
		restofline = dotPtr + 1;
		*dotPtr = '\0';
		cdnum = atoi(line+1);

		/*
		 * See if we have next set of entries and need
		 * bump "W" number.
		 */
		if (cdnum != currentNum) {
			newnum++;
			currentNum = cdnum;
		}
		*dotPtr = '.';
		(void) snprintf(modline, sizeof (modline),
				"W%i%s", newnum, dotPtr);
		StringListAdd(&newlist, modline);
	}

	*strlist = newlist;
}


/*
 * Name:	readSolCDInfo
 * Description:	read the 2of2.info file
 * Scope:	private
 * Arguments:	infoFilePath - fullpath to file to read
 * Returns:	ptr to SolCD_Info generated
 */
static SolCD_Info *
readSolCDInfo(char *infoFilePath)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];
	char *str = (char *)NULL;
	SolCD_Info *solcdinfo = (SolCD_Info *)NULL;

	if ((fp = fopen(infoFilePath, "r")) == (FILE *)NULL) {
			return (NULL);
	}

	solcdinfo = (SolCD_Info *)xcalloc(sizeof (SolCD_Info));
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strncmp(buf, "CD_INSTALLER=", 13) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				solcdinfo->installer = xstrdup(str);
			}
		} else if (strncmp(buf, "CD_NAME=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				solcdinfo->cdname = xstrdup(str);
			}
		} else if (strncmp(buf, "PRODID=", 7) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				solcdinfo->prodid = xstrdup(str);
			}
		} else if (strncmp(buf, "CD_VOLID=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				solcdinfo->volid = xstrdup(str);
			}
		}
	}
	(void) fclose(fp);
	return (solcdinfo);
}

/*
 * Name:	preserve_etc_default_init
 * Description:	This function is called by the setup_launcher routine.
 *		If the system locale (in /a/etc/default/init) is difffernt
 *		from the installation locale (in /etc/default/init), it will
 *		try to setup to run the launcher in the installation locale.
 *		It will save the system locale in /a/etc/default/init.save,
 *		which will be copied back by the launcher's rc script.
 * Scope:	private
 * Arguments:	none
 * Returns:	none
 */
static void
preserve_etc_default_init(void)
{
	char buf[MAXPATHLEN];
	char path[MAXPATHLEN];
	char path_save[MAXPATHLEN];
	char *display = (char *)NULL;
	char *install_time_locale = get_system_locale();
	char *locale = get_default_system_locale();

	(void) snprintf(path, sizeof (path),
				"%s%s", get_rootdir(), INIT_FILE);
	(void) snprintf(path_save, sizeof (path_save),
				"%s.save", path);

	/*
	 * If installtime locale and system locale are the same
	 * then there is no need to do processing to preserve the
	 * locale in /etc/default/init.
	 */
	if (strcmp(install_time_locale, locale) != 0) {
		/*
		 * If the installtime locale wasn't installed on the system
		 * don't do anything.  We check to see if the installtime
		 * locale was installed on the system by checking for the
		 * existence of the locale_map file.
		 * One thing we must check for differently is the C locale.
		 * The C locale is always installed on the system,
		 * but it does not have a locale map file.  So if the
		 * installtime locale is C ( get_default_locale() ),
		 * we save the init file.
		 */
		(void) snprintf(buf, sizeof (buf),
			"%s%s/%s/%s", get_rootdir(), NLSPATH,
			install_time_locale, LOCALE_MAP_FILE);
		if (access(buf, F_OK) == 0 ||
			strcmp(install_time_locale, get_default_locale())
									== 0) {
			/* Save off a copy of  /a/etc/default/init */
			copyFile(path, path_save, B_TRUE);

			/*
			 * Modify /a/etc/default/init to contain the
			 * install time locale
			 */
			save_locale(install_time_locale, path);
		}
	}

	/*
	 * If we are running in tty mode,
	 * we want the locale to be set to C if the user
	 * has selected an asian system locale. Look for
	 * LC_MESSAGES, then LANG in /a/etc/default/init
	 * to decide if we have an asian locale. Then,
	 * make a temporary /etc/default/init by getting
	 * rid of all LC_ and LANG lines and add LANG=C
	 */
	display = (char *)getenv("DISPLAY");
	if ((display == NULL) && locale_is_multibyte(install_time_locale)) {
		/* Save file if it hasn't already been saved above. */
		if (access(path_save, F_OK) != 0) {
			copyFile(path, path_save, B_TRUE);
		}
		/* Modify /a/etc/default/init to contain C locale */
		save_locale(get_default_locale(), path);
	}
}
