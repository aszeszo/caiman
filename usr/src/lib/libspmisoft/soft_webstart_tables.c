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
#pragma ident	"@(#)soft_webstart_tables.c	1.8	07/11/09 SMI"
#endif

/*
 *	File:		soft_webstart_tables.c
 *
 *	Description:	This file contains webstart table related functions
 */

#include <dirent.h>
#include <locale.h>
#include <unistd.h>

#include "spmisoft_lib.h"
#include "soft_webstart_tables.h"


/*
 * Public functions
 */

/*
 * Functions relating to the reading and manipulating of cobundled
 * product data
 */


/* local functions */
static char *get_loc_text(char *, char *);
static char *get_loc_path(char *, char *);
static char *get_loc_prodname(char *);
static char *get_media_kit_dir();
static void readAllProductTocs();
static void readAllCDInfo();
static void freeProductTables();
static PD_Size *_read_pdfile_size_components(FILE *, const char *);
static parseOSfiles(char *, Module *);
static readMediaDotToc(Module *, char *);
static readInDotFile(char *, Module *);


/* local global data */

static char		*media_kit_dir = MEDIA_KIT_DIR;
static char		*media_kit_dot_toc = MEDIA_KIT_TOC;
static char		*media_kits_dot_toc = MEDIA_KITS_TOC;
static char		*cds_dir = CDS_DIR;
static char		*cdname_dir = CD_NAME_DIR;
static char		*cdhelp_dir = CD_HELP_DIR;
static char		*pds_dir = PD_DIR;
static char		*pdname_dir = PD_NAME_DIR;
static char		*pdhelp_dir = PD_HELP_DIR;

static char		*metaclusters = METACLUSTERS;
static char		*metalocale = METALOCALE;
static char		*oscore1 = OSCORE1;
static char		*slashoscore1 = SLASHOSCORE1;
static char		*product_toc = PRODUCT_DOT_TOC;
static char		*cd_info = CD_DOT_INFO;


/*
 * Name:	(swi_)readProductTables
 * Description:	load the product tables
 * Scope:	public
 * Arguments:	none
 * Returns:	1		- Read media_kit.toc file successfully
 *		0		- Unable to open media_kit.toc file
 */
int
swi_readProductTables(void)
{
	Module	*curprod;
	char media_toc_file[MAXPATHLEN + 1];
	int mediaTocProb = 0;
	int rc = 0;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("readProductTables");
#endif

	/*
	 * Delete dispatch_table if one exists
	 */
	unlink(DISPATCH_TABLE);

	curprod = get_current_product();

	/*
	 * free product tables if they exist
	 */
	if (curprod->info.prod->p_cd_info) {
		freeProductTables(curprod);
	}

	curprod->info.prod->p_cd_info = NULL;

	/*
	 * Parse the os dot files, give error if can't open metacluster dir
	 *
	 * mkit->osDir is set by _init_mkit
	 */
	if ((rc = parseOSfiles(mkit->osDir, curprod)) == 1) {
		write_message(LOGSCR, ERRMSG, LEVEL0,
				"Error opening meta_clusters dir in: %s\n",
				mkit->osDir);
	}

	/*
	 * get media kit dir
	 */
	mkit->osMediaDir =  get_media_kit_dir(mkit->osDir);
	if (!mkit->osMediaDir) {
		return (0);
	}
	(void) snprintf(media_toc_file, sizeof (media_toc_file),
				"%s/%s%s", media_kit_dir,
				mkit->osMediaDir, media_kit_dot_toc);

	/*
	 * read the media_kit.toc file and get cd names/subdir
	 */
	mediaTocProb = readMediaDotToc(curprod, media_toc_file);

	if (mediaTocProb) {
		return (0);
	}

	/*
	 * If p_cd_info is null, the file is empty
	 */
	if (! curprod->info.prod->p_cd_info) {
		return (1);
	}

	/*
	 * Read the cd.info files for all cds in the media kit
	 */
	(void) readAllCDInfo();

	/*
	 * Read the product.toc files for all cds in the media kit
	 * and parse the pd files
	 */
	(void) readAllProductTocs();

	return (1);
}

/*
 * Name:	(swi_)readCDInfo
 * Description:	read the cd.info file for each cd
 * Scope:	public
 * Arguments:	cdinfo	- ptr to CD_Info for cd of interest
 * Returns:	none
 */
void
swi_readCDInfo(CD_Info *cdinfo)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];
	char cdInfoPath[MAXPATHLEN + 1];
	char *str = (char *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("readCDInfo");
#endif

	(void) snprintf(cdInfoPath, sizeof (cdInfoPath),
				"%s/%s%s", cds_dir,
				cdinfo->cddir, cd_info);
	if ((fp = fopen(cdInfoPath, "r")) == (FILE *)NULL) {
			return;
	}

	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strncmp(buf, "CD_INSTALLER=", 13) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdinfo->installer = xstrdup(str);
			}
		} else if (strncmp(buf, "INSTALLER_WSR=", 14) == 0) {
			str = get_value(buf, '=');
			if (str != NULL && (strncmp(str, "NO", 2) == 0)) {
				cdinfo->installer_wsr = B_FALSE;
			}
		} else if (strncmp(buf, "CD_VOLID=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdinfo->volid = xstrdup(str);
			}
		} else if (strncmp(buf, "MINIROOT_OPTS=", 14) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				cdinfo->minirootopts = xstrdup(str);
			}
		}
	}
	(void) fclose(fp);
}

/*
 * Name:	(swi_)readProductToc
 * Description:	read the product.toc file for the cd in cdinfo
 *		and populate prodToc structure
 * Scope:	public
 * Arguments:	cdinfo	- ptr to CD_Info structure
 * Returns:	none
 */
void
swi_readProductToc(CD_Info *cdinfo)
{
	FILE *fp = (FILE *)NULL;
	char buf[BUFSIZ + 1];
	char prodPath[MAXPATHLEN + 1];
	char *entry = (char *)NULL;
	char *pdname = (char *)NULL;
	char *locprodname = (char *)NULL;
	char *defYorN = (char *)NULL;
	int defInstall;
	int count;
	int i;
	StringList *slist = (StringList *)NULL;
	StringList *strlist = (StringList *)NULL;


#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("readProductToc");
#endif

	(void) snprintf(prodPath, sizeof (prodPath),
				"%s/%s%s", cds_dir,
				cdinfo->cddir, product_toc);
	if ((fp = fopen(prodPath, "r")) == (FILE *)NULL) {
		return;
	}

	/*
	 * read the contents of the product.toc file
	 * into a stringlist
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';
		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else {
			StringListAdd(&strlist, buf);
		}
	}
	(void) fclose(fp);

	/*
	 * add products in reverse so prodsel panel matches
	 * the order in the product.toc file
	 */
	count = StringListCount(strlist);
	while (count) {
		slist = strlist;
		for (i = 1; i < count; i++) {
			slist = slist->next;
		}
		entry = xstrdup(slist->string_ptr);

		/*
		 * Each line in product.toc file is:
		 * 	pdfilesuffix <YES,NO>
		 */
		defYorN = (get_value(entry, ' '));
		if (strcasecmp(defYorN, "YES") == 0) {
			defInstall = DEFAULT_ON;
		} else {
			defInstall = DEFAULT_OFF;
		}
		pdname = strtok(entry, " ");

		(void) snprintf(prodPath, sizeof (prodPath),
				"%s/pd.%s", pds_dir, pdname);
		/*
		 * Make sure pd file exists
		 */
		if (access(prodPath, R_OK) != 0) {
			(void) free(entry);
			count--;
			continue;
		}

		locprodname = get_loc_prodname(pdname);
		cdinfo->prodToc = (Module *) add_comp_module(cdinfo->prodToc,
					pdname, locprodname, defInstall);
		cdinfo->prodToc->info.pdinf->p_selected =
				defInstall? SELECTED:UNSELECTED;

		/*
		 * Read and parse this product's pd file
		 */
		readInDotFile(prodPath, cdinfo->prodToc);

		/*
		 * Replace cdname from pd file with cdname from cd.info
		 */
		free(cdinfo->prodToc->info.pdinf->pdfile->cd_name);
		cdinfo->prodToc->info.pdinf->pdfile->cd_name =
						xstrdup(cdinfo->cdname);

		/*
		 * if there is no locprodname, use the PRODNAME from
		 * the pd file (couldn't do this above, since need prodtoc
		 * to read in pd file) rather than the pd suffix
		 */
		if (locprodname == NULL || strlen(locprodname) == 0) {
			cdinfo->prodToc->info.pdinf->locprodname=
				cdinfo->prodToc->info.pdinf->pdfile->prodname;
		}
		(void) free(entry);
		count--;
	}
	StringListFree(strlist);
}

/*
 * Function:    (swi_)get_loc_cdname
 * Description: Determine the localized cd name given the subdir
 * Scope:       public
 * Parameters:  subdir  - the name of the subdir in the products/cds directory
 * Return:      char *  - pointer to buffer containing localized name
 */
char *
swi_get_loc_cdname(char *subdir)
{
	char *locName = (char *)NULL;

	locName = get_loc_text(cdname_dir, subdir);

	return (locName);
}


/*
 * Function:    (swi_)get_loc_cdhelp
 * Description: Return the localized cd help given the cd subdir
 * Scope:       public
 * Parameters:  subdir - the name of the subdir in the products/cds directory
 * Return:      char *  - pointer to buffer containing localized info,
 *			caller should free
 */
char *
swi_get_loc_cdhelp(char *subdir)
{
	char *locName = (char *)NULL;

	locName = get_loc_text(cdhelp_dir, subdir);

	return (locName);
}

/*
 * Function:    (swi_)get_loc_prodhelp
 * Description: Return the localized product help given the pd file suffix
 * Scope:       public
 * Parameters:  pdsuffix - the pd file suffix ("SDK301" for pd.SDK301)
 * Return:      char *  - pointer to allocated buffer containing localized
 *			info, caller should free
 */
char *
swi_get_loc_prodhelp(char *pdsuffix)
{
	char *locName = (char *)NULL;

	locName = get_loc_text(pdhelp_dir, pdsuffix);

	return (locName);
}

/*
 * Function:    (swi_)get_loc_license_path
 * Description: Return the path to the localized license file
 * Scope:       public
 * Parameters:  none
 * Return:      char *  - pointer to allocated buffer containing path
 *			  of localized license file, caller should free
 */
char *
swi_get_loc_license_path()
{
	char licensesDir[MAXPATHLEN + 1];
	char *licensePath = (char *)NULL;

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("get_loc_license_path");
#endif

	if (mkit->osDir == NULL) {
		return (NULL);
	}
	(void) snprintf(licensesDir, sizeof (licensesDir),
			"%s/%s", mkit->osDir, "licenses");

	licensePath = get_loc_path(licensesDir, "license");

	return (licensePath);
}

/*
 * Function:    (swi_)parsePDfile
 * Description: Parse pd files
 * Scope:       public
 * Parameters:  none
 * Return:      none
 */
void
swi_parsePDfile(CD_Info *cdinfo)
{
	Module *productToc = (Module *)NULL;
	char *pname = (char *)NULL;
	char pdPath[MAXPATHLEN + 1];

#ifdef SW_LIB_LOGGING
	sw_lib_log_hook("parsePDfile");
#endif

	/*
	 * parse pd files corresponding to cd constituents
	 */
	for (productToc = cdinfo->prodToc; productToc;
				productToc = productToc->next) {
		pname = productToc->info.pdinf->pdname;
		(void) snprintf(pdPath, sizeof (pdPath),
				"%s/pd.%s", pds_dir, pname);
		readInDotFile(pdPath, productToc);
	}
}

/*
 * Function:    (swi_)setMkit
 * Description: Sets value of mkit
 * Scope:       public
 * Parameters:  none
 * Return:      none
 */
void
swi_setMkit(Media_Kit_Info *newmkit)
{
	mkit = newmkit;
}


/*
 * Function:    (swi_)getMkit
 * Description: Gets value of mkit
 * Scope:       public
 * Parameters:  none
 * Return:      none
 */
Media_Kit_Info *
swi_getMkit()
{
	return (mkit);
}



/*
 * Private functions
 */

/*
 * Name:	freeProductTables
 * Description:	free all product table structures
 * Scope:	private
 * Arguments:	curprod	- ptr to current product
 * Returns:	none
 */
static void
freeProductTables(Module *curprod)
{
	Module *cd = (Module *)NULL;
	Module *cdSave = (Module *)NULL;
	Module *productToc = (Module *)NULL;
	Module *prodTocSave = (Module *)NULL;
	Product *prod = (Product *)NULL;
	PDFile *pdFile = (PDFile *)NULL;
	Size_comp *scomp = (Size_comp *)NULL;
	PD_Size *hsizes = (PD_Size *)NULL;

	prod = curprod->info.prod;

	/*
	 * for each cd, free the product/pdfile tables and
	 * then the cd tables
	 */
	for (cd = prod->p_cd_info; cd; cd = cd->next) {
		if (cdSave) {
			free(cdSave->info.cdinf);
			free(cdSave);
		}

		/*
		 * free the constituent components and associated info
		 */
		for (productToc = cd->info.cdinf->prodToc; productToc;
				productToc = productToc->next) {
			if (prodTocSave) {
				free(prodTocSave->info.pdinf);
				free(prodTocSave);
			}
			if (! productToc->info.pdinf) {
				continue;
			}

			free(productToc->info.pdinf->pdname);
			free(productToc->info.pdinf->locprodname);

			pdFile = productToc->info.pdinf->pdfile;
			if (pdFile) {
				free(pdFile->cd_name);
				free(pdFile->prodname);
				free(pdFile->prodid);
				free(pdFile->reqMeta);
				free(pdFile->compid);

				hsizes = pdFile->head_sizes;
				for (; hsizes; hsizes = hsizes->next) {
					scomp = hsizes->info;
					free(scomp->arch);
					StringListFree(scomp->locales);
				}
				if (pdFile->gen_size) {
				    StringListFree(pdFile->gen_size->locales);
				    free(pdFile->gen_size->arch);
				}
				free(pdFile);
			}
			prodTocSave = productToc;
		}

		if (prodTocSave) {
			free(prodTocSave->info.pdinf);
			free(prodTocSave);
		}

		/*
		 * now free the cd info
		 */
		free(cd->info.cdinf->cddir);
		free(cd->info.cdinf->cdname);
		free(cd->info.cdinf->loccdname);
		free(cd->info.cdinf->volid);
		free(cd->info.cdinf->installer);
		free(cd->info.cdinf->minirootopts);
		free(cd->info.cdinf->addpath);
		cdSave = cd;
	}

	if (cdSave) {
		free(cdSave->info.cdinf);
		free(cdSave);
	}
}

/*
 * Name:	readMediaDotToc
 * Description:	read the media_kit.toc file
 * Scope:	private
 * Arguments:	prod	- ptr to current product
 * 		mediatocfile	- ptr to fullpath of media_kit.toc file
 * Returns:	0		- Read media_kit.toc file successfully
 *		1	- Unable to open media_kit.toc file
 */
static int
readMediaDotToc(Module *prod, char *mediatocfile)
{
	char buf[BUFSIZ + 1];
	FILE *fp = (FILE *)NULL;
	char *cdname = (char *)NULL;
	char *locname = (char *)NULL;
	char *subdir = (char *)NULL;
	char *entry = (char *)NULL;
	StringList *slist = (StringList *)NULL;
	StringList *strlist = (StringList *)NULL;
	int i;
	int count;

	if ((fp = fopen(mediatocfile, "r")) == (FILE *)NULL) {
		fprintf(stdout, "Error opening file: %s\n", mediatocfile);
		return (1);
	}

	/*
	 * read the contents of the media_kit.toc file
	 * into a stringlist
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else {
			StringListAdd(&strlist, buf);
		}
	}
	(void) fclose(fp);

	/*
	 * add products in reverse so prodsel panel matches
	 * the order in the media_kit.toc file
	 */
	count = StringListCount(strlist);
	while (count) {
		slist = strlist;
		for (i = 1; i < count; i++) {
			slist = slist->next;
		}
		entry = xstrdup(slist->string_ptr);
		cdname = get_value(entry, ' ');
		subdir = strtok(entry, " ");
		locname = (char *)get_loc_cdname(subdir);
		prod->info.prod->p_cd_info =
			add_cd_module(prod->info.prod->p_cd_info,
			cdname, locname, subdir);
		prod->info.prod->p_cd_info->info.cdinf->c_selected =
			UNSELECTED;
		(void) free(entry);
		count--;
	}
	StringListFree(strlist);
	return (0);
}


/*
 * Name:	readAllCDInfo
 * Description:	read the cd.info file for each cd
 * Scope:	private
 * Arguments:	none
 * Returns:	none
 */
static void
readAllCDInfo()
{
	Module	*prod;
	Module *mod = (Module *)NULL;
	CD_Info *cdinfo = (CD_Info *)NULL;


	prod = get_current_product();
	mod = prod->info.prod->p_cd_info;
	while (mod) {
		cdinfo = mod->info.cdinf;
		readCDInfo(cdinfo);
		mod = mod->next;
	}
}


/*
 * Name:	readAllProductTocs
 * Description:	read the product.toc file for each cd
 * Scope:	private
 * Arguments:	none
 * Returns:	none
 */
static void
readAllProductTocs()
{
	Module	*prod;
	Module *mod = (Module *)NULL;

	prod = get_current_product();
	mod = prod->info.prod->p_cd_info;
	while (mod) {
		mod->info.cdinf->prodToc = NULL;
		readProductToc(mod->info.cdinf);
		mod = mod->next;
	}
}


/*
 * Function:    get_media_kit_dir
 * Description: Determine the media kit subdirectory
 * Scope:       private
 * Parameters:  osbase  - ptr to os base directory
 * Return:      char *  - ptr to allocated string containing media kit
 *				subdirectory or NULL
 */
char *
get_media_kit_dir(char *osbase)
{
	DIR *dirp;
	char media_kits_path[MAXPATHLEN + 1];
	FILE *fp;
	char buf[BUFSIZ];
	char *subdir;

	if (!(dirp = opendir(osbase))) {
		return (NULL);
	}

	/*
	 * open media_kits.toc file in os directory
	 */
	(void) snprintf(media_kits_path, sizeof (media_kits_path),
			"%s%s", osbase, media_kits_dot_toc);
	if ((fp = fopen(media_kits_path, "r")) == (FILE *)NULL) {
		return (NULL);
	}

	/*
	 * read in the contents of the media_kits.toc file
	 */
	while (fgets(buf, BUFSIZ, fp)) {
		buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else {
			subdir = strtok(buf, " ");
		}
	}
	(void) fclose(fp);
	closedir(dirp);

	return (xstrdup(subdir));
}


/*
 * Function:    get_loc_prodname
 * Description: Determine the localized product name given the
 *              pd file suffix
 * Scope:       private
 * Parameters:  pdsuffix - the pd file suffix ("SDK301" for pd.SDK301)
 * Return:      char *  - pointer to buffer containing localized name
 */
static char *
get_loc_prodname(char *pdsuffix)
{
	char *locName = (char *)NULL;

	locName = get_loc_text(pdname_dir, pdsuffix);

	return (locName);
}

/*
 * Function:    get_loc_path
 * Description: Get path of localized file for given parent dir and filename
 * Scope:       private
 * Parameters:  leadingPath - the parent directory (not including locale)
 *              filename - the name of the file
 * Return:      char *  - pointer to buffer containing full pathname,
 *			  caller should free
 */
static char *
get_loc_path(char *leadingPath, char *filename)
{
	char	*locid;
	char	help_path[MAXPATHLEN + 1];
	char	fullPath[MAXPATHLEN + 1];
	char	*dotPtr;

	/*
	 * get locale system is running in
	 */
	locid = xstrdup(setlocale(LC_MESSAGES, ""));

	/*
	* First check locid directory. If not there, strip locid
	* to dot(fr_CA.ISO8859-1 becomes fr_CA) and check again. If
	* not there, truncate locid to 2 chars(fr). If still not
	* there, use C directory.
	*/
	if (locid != NULL) {
		(void) snprintf(help_path, sizeof (help_path),
				"%s/%s", locid, filename);
		(void) snprintf(fullPath, sizeof (fullPath),
				"%s/%s", leadingPath, help_path);

		if (access(fullPath, R_OK) != 0) {
			dotPtr = (char *)strchr(locid, '.');

			if (dotPtr != NULL) {
				/*
				*  Strip the locid of dot extension
				*/
				*dotPtr = '\0';
			}
			(void) snprintf(help_path, sizeof (help_path),
					"%s/%s", locid, filename);
			(void) snprintf(fullPath, sizeof (fullPath),
					"%s/%s", leadingPath,
					help_path);

			if (access(fullPath, R_OK) != 0) {
				if (strlen(locid) > 1) {
					/*
					 *  Truncate the locid to 2 chars
					 */

					*(locid+2) = '\0';
				}
				(void) snprintf(help_path,
						sizeof (help_path),
						"%s/%s", locid,
						filename);
				(void) snprintf(fullPath,
						sizeof (fullPath),
						"%s/%s", leadingPath,
						help_path);

				if (access(fullPath, R_OK) != 0) {
					(void) snprintf(help_path,
							sizeof (help_path),
							"%s/%s",
							"C", filename);
				}
			}
		}
		free(locid);
	} else {
		(void) snprintf(help_path, sizeof (help_path),
					"%s/%s", "C", filename);
	}

	(void) snprintf(fullPath, sizeof (fullPath),
					"%s/%s", leadingPath, help_path);
	return (xstrdup(fullPath));
}

/*
 * Function:    get_loc_text
 * Description: Get localized text for given parent dir and filename
 * Scope:       private
 * Parameters:  leadingPath - the parent directory (not including locale)
 *              filename - the name of the file
 * Return:      char *  - pointer to buffer containing localized text,
 *			  caller should free
 */
static char *
get_loc_text(char *leadingPath, char *filename)
{
	char	*fullPath = (char *)NULL;
	char	*locText = (char *)NULL;

	fullPath = get_loc_path(leadingPath, filename);
	locText = (char *)readInText(fullPath);
	free(fullPath);
	return (locText);
}


/*
 * Function:    parseOSfiles
 * Description: parse os. (os.core.1, etc) files
 * Scope:       private
 * Parameters:  osdir - path to os directory
 *		(e.g. /usr/lib/install/data/os/5.10)
 * Return:      int  - 0 - files parsed successfully
 *                     1 - can't open metaclusters directory
 */
static int
parseOSfiles(char *osdir, Module *prod)
{
	Module *productToc = (Module *)NULL;
	char metaPath[MAXPATHLEN + 1];
	char metaLocalePath[MAXPATHLEN + 1];
	char osPath[MAXPATHLEN + 1];
	char *locName = (char *)NULL;
	char *parentPtr = (char *)NULL;
	int rc;
	DIR *dirp = (DIR *)NULL;
	struct dirent *dp;
	OS_Info *osinfo = (OS_Info *)NULL;

	(void) snprintf(metaPath, sizeof (metaPath),
			"%s%s", osdir, metaclusters);
	if (!(dirp = opendir(metaPath))) {
		return (1);
	}

	(void) snprintf(metaLocalePath, sizeof (metaLocalePath),
			"%s%s", osdir, metalocale);
	if (!(dirp = opendir(metaLocalePath))) {
		return (1);
	}

	/*
	 * We want to select the osfiles based on miniroot locale to
	 * account for differences in StarOffice/StarSuite
	 *
	 * Call get_loc_path to see if os.core.1 exists in locale 
	 * directory, otherwise returns version in default C directory.
	 */
	locName = get_loc_path(metaLocalePath, oscore1);
        parentPtr = strstr(locName, slashoscore1);
	*parentPtr = '\0';

	if (!(dirp = opendir(locName))) {
		(void) free(locName);
		return (1);
	}
	while ((dp = readdir(dirp)) != (struct dirent *)0) {
		if (strcmp(dp->d_name, ".") == 0 ||
					strcmp(dp->d_name, "..") == 0) {
			continue;
		}

		if (strncmp("os.", dp->d_name, strlen("os.")) != 0) {
			continue;
		}
		(void) snprintf(osPath, sizeof (osPath),
				"%s/%s", locName, dp->d_name);

		/*
		 * create os file
		 */
		prod->info.prod->p_os_info =
			add_os_module(prod->info.prod->p_os_info,
					dp->d_name, osdir);
		osinfo = prod->info.prod->p_os_info->info.osinf;
		osinfo->prodToc = (Module *)add_comp_module(osinfo->prodToc,
					dp->d_name, NULL, DEFAULT_OFF);
		productToc = osinfo->prodToc;
		/*
		 * parse os file
		 */
		if ((rc = readInDotFile(osPath, productToc)) == 1) {
			/*
			 * if can't open os file, give error ?
			 */
			continue;
		}
	}
	(void) free(locName);
	closedir(dirp);
	return (0);
}


/*
 * Function:    readInDotFile
 * Description: Read in pd/os file and parse contents
 * Scope:       private
 * Parameters:  pdPath - path to file to read
 *              prodtoc - ptr to prod_toc module
 * Return:      int  - 0 - file opened successfully
 *                     1 - file not opened successfully
 */
static int
readInDotFile(char *pdPath, Module *prodtoc)
{
	char buf[BUFSIZ + 1];
	FILE *fp;
	char *tok = (char *)NULL;
	char *str = (char *)NULL;
	PDFile *pdFile;
	StringList *itags = (StringList *)NULL;

	prodtoc->info.pdinf->pdfile = (PDFile *)NULL;

	/*
	 * return error if can't open file
	 */
	if ((fp = fopen(pdPath, "r")) == (FILE *)NULL) {
		return (1);
	}

	pdFile = (PDFile *)xcalloc(sizeof (PDFile));
	pdFile->gen_size = (Size_comp *)xcalloc(sizeof (Size_comp));
	reset_size_comp(pdFile->gen_size);
	prodtoc->info.pdinf->pdfile = pdFile;

	while (fgets(buf, BUFSIZ, fp)) {
		/* get rid of newline if line has one */
		if (buf[strlen(buf) - 1] == '\n')
			buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		}

		if (buf[0] == '[') {
			pdFile->head_sizes =
				_read_pdfile_size_components(fp, buf);
		} else if (strncmp(buf, "CD_NAME=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->cd_name = xstrdup(str);
			}
		} else if (strncmp(buf, "PRODNAME=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->prodname = xstrdup(str);
			}
		} else if (strncmp(buf, "PRODID=", 7) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->prodid = xstrdup(str);
			}
		} else if (strncmp(buf, "REQUIRED=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->reqMeta = xstrdup(str);
			}
		} else if (strncmp(buf, "MINIROOT=", 9) == 0) {
			pdFile->miniRoot = 0;
			str = get_value(buf, '=');
			if (str != NULL && ci_streq(str, "yes")) {
				pdFile->miniRoot = 1;
			}
		} else if (strncmp(buf, "COMPID=", 7) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->compid = xstrdup(str);
			}
		} else if (strncmp(buf, "CLUSTER=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->cluster = xstrdup(str);
			}
		} else if (strncmp(buf, "PACKAGES=", 9) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				/* Make itag entry for each package */
				tok = strtok(str, " ");
				(void) snprintf(buf, sizeof (buf),
						"package %s", tok);
				StringListAddNoDup(&itags, buf);
				while (tok = strtok(NULL, " ")) {
					(void) snprintf(buf, sizeof (buf),
							"package %s", tok);
					StringListAddNoDup(&itags, buf);
				}
			}
		} else if (strncmp(buf, "SCRIPTS=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				/* Make itag entry for each script */
				tok = strtok(str, " ");
				(void) snprintf(buf, sizeof (buf),
						"script %s", tok);
				StringListAddNoDup(&itags, buf);
				while (tok = strtok(NULL, " ")) {
					(void) snprintf(buf, sizeof (buf),
							"script %s", tok);
					StringListAddNoDup(&itags, buf);
				}
			}
		} else if (strncmp(buf, "PATCHES=", 8) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				/* Make itag entry for each patch */
				tok = strtok(str, " ");
				(void) snprintf(buf, sizeof (buf),
						"patch %s", tok);
				StringListAddNoDup(&itags, buf);
				while (tok = strtok(NULL, " ")) {
					(void) snprintf(buf, sizeof (buf),
						"patch %s", tok);
					StringListAddNoDup(&itags, buf);
				}
			}
		} else if (strncmp(buf, "ROOT=", 5) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[ROOT_FS] = atoi(str);
			}
		} else if (strncmp(buf, "VAR=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[VAR_FS] = atoi(str);
			}
		} else if (strncmp(buf, "OPT=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[OPT_FS] = atoi(str);
			}
		} else if (strncmp(buf, "USR=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[USR_FS] = atoi(str);
			}
		} else if (strncmp(buf, "EXPORT=", 7) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[EXPORT_FS] =
					atoi(str);
			}
		} else if (strncmp(buf, "USROW=", 6) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				pdFile->gen_size->fs_size[USR_OWN_FS] =
					atoi(str);
			}
		}

	}
	/* save ptr to itag entries */
	pdFile->itags = itags;
	(void) fclose(fp);
	return (0);
}

/*
 * Function:    _read_pdfile_size_components
 * Description: Read in pdfile size components
 * Scope:       private
 * Parameters:  fp - FILE pointer to pdfile
 *              file_line - pointer to first size component
 *                        line already read in.
 * Return:      PD_Size * - pointer to the head of the PD_Size
 *                        list for this pdfile.
 */
static PD_Size *
_read_pdfile_size_components(FILE *fp, const char *first_line)
{

	char buf[BUFSIZ + 1];
	PD_Size *head_sizes = (PD_Size *)NULL;
	PD_Size *tail_sizes = (PD_Size *)NULL;
	char *tok = (char *)NULL;
	char *str = (char *)NULL;
	char *arch, *loc_list;
	char *delim_char = NULL;

	strcpy(buf, first_line);

	do {
		/* get rid of newline if line has one */
		if (buf[strlen(buf) - 1] == '\n')
			buf[strlen(buf) - 1] = '\0';

		if (buf[0] == '[') {
			if (head_sizes == NULL) {
				head_sizes =
				    (PD_Size *)xcalloc(sizeof (PD_Size));
				head_sizes->next = NULL;
				tail_sizes = head_sizes;
			} else {
				tail_sizes->next =
					(PD_Size *)xcalloc(sizeof (PD_Size));
				tail_sizes = tail_sizes->next;
				tail_sizes->next = NULL;
			}
			tail_sizes->info =
				(Size_comp *)xcalloc(sizeof (Size_comp));

			reset_size_comp(tail_sizes->info);

			/* get the locale list string */
			str = strchr(buf, ' ');
			str = str+1;
			loc_list = xstrdup(str);

			/* get rid of the ending "]" */
			loc_list[strlen(loc_list) - 1] = '\0';

			/* set the arch for this size component */
			arch = strtok(buf, " ");
			tail_sizes->info->arch = xstrdup(arch+1);

			/* list could be seperated by a comma or space */
			if (tok = strchr(loc_list, ','))
				delim_char = ",";
			else
				delim_char = " ";
			tok = strtok(loc_list, delim_char);
			StringListAddNoDup(&tail_sizes->info->locales, tok);
			while (tok = strtok(NULL, delim_char)) {
				StringListAddNoDup(&tail_sizes->info->locales,
					tok);
			}
		}

		else if (buf[0] == '#' || buf[0] == '\n' || strlen(buf) == 0) {
			continue;
		} else if (strncmp(buf, "ROOT=", 5) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[ROOT_FS] = atoi(str);
			}
		} else if (strncmp(buf, "VAR=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[VAR_FS] = atoi(str);
			}
		} else if (strncmp(buf, "OPT=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[OPT_FS] = atoi(str);
			}
		} else if (strncmp(buf, "USR=", 4) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[USR_FS] = atoi(str);
			}
		} else if (strncmp(buf, "EXPORT=", 7) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[EXPORT_FS] =
					atoi(str);
			}
		} else if (strncmp(buf, "USROW=", 6) == 0) {
			str = get_value(buf, '=');
			if (str != NULL) {
				tail_sizes->info->fs_size[USR_OWN_FS] =
					atoi(str);
			}
		}
	} while (fgets(buf, BUFSIZ, fp));

	return (head_sizes);
}
