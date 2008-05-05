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
 * Module:	svc_updatesoft.c
 * Group:	libspmisvc
 * Description: Routines to install software objects onto the live
 *		system.
 */

#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <signal.h>
#include <ulimit.h>
#include <unistd.h>
#include <wait.h>
#include <sys/param.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <poll.h>
#include <thread.h>
#include "spmisvc_lib.h"
#include "spmisoft_lib.h"
#include "spmicommon_api.h"
#include "svc_strings.h"
#include "../libgendb/genericdb.h"

#define	IO_SIZE		4096	/* size of i/o when reading command output */

/* internal prototypes */

int		_setup_software(Module *, TransList **, TCallback *, void *);

/* private prototypes */

static int	_refresh_package_db(char *);
static int	_create_locales_installed(Product *);
static int 	_create_inst_release(Product *);
static int	_install_prod(Module *, PkgFlags *, Admin_file *, TransList **,
    TCallback *, void *);
static int _install_pkg(Node *np, caddr_t dummy, int,
    TCallback *ApplicationCallback, void *ApplicationData);
static int	_open_product_file(Product *);
static int 	_pkg_status(Node *, caddr_t);
static void	_print_results(Module *);
static int	_process_transferlist(TransList **, Node *);
static int	_add_local_pkg(char *pkg_dir, int, PkgFlags *pkg_params,
    char *prod_dir, TCallback *ApplicationCallback, void *ApplicationData);
static int	_add_virtual_pkg(char *pkg, char *arch, char *pkg_dir,
    PkgFlags *pkg_params, char *prod_dir);
static int	_setup_software_results(Module *);
static int	max_pkgdir_len(Product *);

/* globals */

static PkgFlags		*pkg_params;
static Admin_file	*admin_f;
static char		*prod_dir;
static int		inst_status;

/* locale statics */

static ModStatus	cur_stat;
static short		have_one;
static char		product[32];

/*
 * ---------------------- internal functions -----------------------
 */

/*
 * Function:	_setup_software
 * Description:
 * Scope:	internal
 * Parameters:	prod	- pointer to product structure
 *		trans	- A pointer to the list of files being transfered from
 *			  /tmp/root to the indirect install location.
 * Return:	NOERR	- success
 *		ERROR	- error occurred
 */
int
_setup_software(Module *prod,
    TransList **trans,
    TCallback *ApplicationCallback,
    void *ApplicationData)
{
	Admin_file	admin;
	PkgFlags	pkg_parms;

	if (get_machinetype() == MT_CCLIENT)
		return (NOERR);

	_setup_admin_file(&admin);
	_setup_pkg_params(&pkg_parms);

	/* print the solaris installation introduction  message */
	write_status(LOGSCR, LEVEL0, MSG0_SOLARIS_INSTALL_BEGIN);

	/* install software packages */
	if (_install_prod(prod,
	    &pkg_parms,
	    &admin,
	    trans,
	    ApplicationCallback,
	    ApplicationData) == ERROR)
		return (ERROR);

	/* print out the results of the installation */
	_print_results(prod);

	/*
	 * install the software related files on installed system
	 * for future upgrade
	 */
	if (_setup_software_results(prod) != NOERR) {
		write_notice(ERRMSG, MSG0_ADMIN_INSTALL_FAILED);
		return (ERROR);
	}

	/*
	 * Update the legacy contents file iff we are using
	 * a new (Solaris 10) package database
	 */
	if (pkgdb_supported() && genericdb_exists(get_rootdir()) &&
	    _refresh_package_db(get_rootdir()) != NOERR) {
		write_notice(ERRMSG, MSG0_REFRESH_FAILED);
		return (ERROR);
	}

	return (NOERR);
}

/*
 * ---------------------- private functions -----------------------
 */

/*
 * Function:	_atconfig_restore
 * Description:	Restore the atconfig file.
 * Scope:	private
 * Parameters:	none
 * Return:	NOERR	- restore successful
 *		ERROR	- restore failed
 */
int
_atconfig_restore(void)
{
	static char	path[MAXPATHLEN] = "";
	static char	save[MAXPATHLEN] = "";
	static int	complete = 0;

	/* if execution is simulated, return immediately */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/* we only call this routine the first time the file is found */
	if (complete > 0)
		return (NOERR);

	if (path[0] == '\0') {
		(void) snprintf(save, sizeof (save),
					"%s%s", get_rootdir(), IDSAVE);
		(void) snprintf(path, sizeof (path),
					"%s%s", get_rootdir(), IDKEY);
	}

	/*
	 * if the id key file just appeared with this package add,
	 * restore the saved copy if there is one
	 */
	if (access(path, F_OK) == 0) {
		if (access(save, F_OK) == 0) {
			if (_copy_file(path, save) != NOERR)
				return (ERROR);

			(void) unlink(save);
		}

		complete++;
	}

	return (NOERR);
}

/*
 * Function:	_atconfig_store
 * Description:	Store the atconfig file for safe keeping.
 * Scope:	private
 * Parameters:	none
 * Return:	NOERR	- storage successful
 *		ERROR	- storage failed
 */
int
_atconfig_store(void)
{
	char	path[MAXPATHLEN];
	char	save[MAXPATHLEN];

	/* if execution is simulated, return immediately */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/*
	 * if the id key file exists, save it on the target file
	 * system in case for disaster recovery
	 */
	(void) snprintf(path, sizeof (path), "%s%s", get_protodir(), IDKEY);
	canoninplace(path);
	if (access(path, F_OK) == 0) {
		(void) snprintf(save, sizeof (save),
				"%s%s", get_rootdir(), IDSAVE);
		if (_copy_file(save, path) != NOERR)
			return (ERROR);
	}

	return (NOERR);
}

/*
 * Function:	_create_locales_installed
 * Description:	Create the locales_installed file on the image being created
 *		and log the selected locales and geos (if any).  This file is
 *		created regardless of whether or not there are any selected
 *		locales or geos.
 * Scope:	private
 * Parameters:	prod	- non-NULL product structure pointer for the Solaris
 *			  product
 * Return:	NOERR	- action completed (or skipped if debugging is
 *			  turned on)
 *		ERROR	- unable to create the locales_installed file.
 */
static int
_create_locales_installed(Product *prod)
{
	FILE	*fp;
	char	entry[MAXPATHLEN + 1];
	Module	*mod;
	int	first;

	/* If execution is simulated, return immediately */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	(void) snprintf(entry, sizeof (entry), "%s%s/locales_installed",
			get_rootdir(), SYS_DATA_DIRECTORY);

	if ((fp = fopen(entry, "w")) == NULL)
		return (ERROR);

	/* Print the selected geos */
	(void) fprintf(fp, "GEOS=");
	for (first = 1, mod = prod->p_geo; mod; mod = mod->next) {
		if (mod->info.geo->g_selected == SELECTED) {
			(void) fprintf(fp, "%s%s", first ? "" : ",",
			    mod->info.geo->g_geo);
			first = 0;
		}
	}
	(void) fprintf(fp, "\n");

	/* Print the selected locales */
	(void) fprintf(fp, "LOCALES=");
	for (first = 1, mod = prod->p_locale; mod; mod = mod->next) {
		if (mod->info.locale->l_selected) {
			(void) fprintf(fp, "%s%s", first ? "" : ",",
			    mod->info.locale->l_locale);
			first = 0;
		}
	}
	(void) fprintf(fp, "\n");

	(void) fclose(fp);

	return (NOERR);
}

/*
 * Function:	_create_inst_release
 * Description:	Create the softinfo INST_RELEASE file on the image being
 *		created and log the current Solaris release, version, and
 *		revision representing the product installed on the system.
 * Scope:	private
 * Parameters:	prod	- non-NULL product structure pointer for the Solaris
 *			  product
 * Return:	NOERR	- action completed (or skipped if debugging is on)
 *		ERROR	- unable to create INST_RELEASE file
 */
static int
_create_inst_release(Product *prod)
{
	FILE 	*fp;
	char	entry[MAXPATHLEN*2];

	/* if execution is simulated, return immediately */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	(void) snprintf(entry, sizeof (entry), "%s%s/INST_RELEASE",
			get_rootdir(), SYS_ADMIN_DIRECTORY);

	if ((fp = fopen(entry, "w")) == NULL)
		return (ERROR);

	(void) fprintf(fp, "OS=%s\nVERSION=%s\nREV=%s\n",
			prod->p_name, prod->p_version, prod->p_rev);
	(void) fclose(fp);

	return (NOERR);
}

/*
 * Function:	_install_prod
 * Description:
 * Scope:	private
 * Parameters:	prods	  -
 *		pkg_parms -
 *		admin	  -
 *		trans	  - This is a pointer to the transfer file list. To be
 *			    processed in _process_transferlist();
 * Return:
 */
static int
_install_prod(Module *prods,
    PkgFlags *pkg_parms,
    Admin_file *admin,
    TransList **trans,
    TCallback *ApplicationCallback,
    void *ApplicationData)
{
	Module	*cur_prod;
	Node	*np;
	int	maxlen;
	char	name[MAXNAMELEN];
	TSoftUpdateStateData StateData;

	/*
	 * store atconfig for safe keeping
	 */
	if (_atconfig_store() != NOERR) {
		write_notice(ERRMSG, MSG0_PKG_PREP_FAILED);
		return (ERROR);
	}

	pkg_params = pkg_parms;
	admin_f = admin;

	for (cur_prod = prods; cur_prod != NULL; cur_prod = cur_prod->next) {

		/* if there are no packages in this product, skip it */
		if (cur_prod->info.prod->p_packages == NULL)
			continue;

		/* save prod dir for use when installing pkgs */
		prod_dir = cur_prod->info.prod->p_pkgdir;

		inst_status = NOERR;

		/*
		 * If a callback has been provided by the calling application
		 * then call it with the state set to Begin.
		 */
		if (ApplicationCallback) {
			StateData.State = SoftUpdateBegin;
			if (ApplicationCallback(ApplicationData, &StateData)) {
				return (ERROR);
			}
		}

		/* figure out max length of this product's set of pkg_dirs */
		maxlen = max_pkgdir_len(cur_prod->info.prod);

		/* install the pkgs associated with this product */
		/* can't use walklist -- need to exit immediately on error */

		for (np = cur_prod->info.prod->p_packages->list->next;
				np != cur_prod->info.prod->p_packages->list;
				np = np->next) {
			/* ignore null packages */
			if (((Modinfo*)np->data)->m_shared == NULLPKG) {
				if (((Modinfo*)np->data)->m_instances == NULL) {
					write_notice(WARNMSG,
						MSG1_PKG_NONEXISTENT,
						((Modinfo*)np->data)->m_pkgid);
				}

				continue;
			}

			/* call pkgadd to install the package */
			if (_install_pkg(np, NULL, maxlen,
			    ApplicationCallback, ApplicationData) == ERROR) {
				write_notice(ERRMSG,
					MSG0_PKG_INSTALL_INCOMPLETE);
				if (ApplicationCallback) {
					StateData.State = SoftUpdateEnd;
					if (ApplicationCallback(ApplicationData,
								&StateData)) {
						return (ERROR);
					}
				}
				return (ERROR);
			}

			/* restore atconfig file if necessary */
			if (_atconfig_restore() == ERROR) {
				if (ApplicationCallback) {
					StateData.State = SoftUpdateEnd;
					if (ApplicationCallback(ApplicationData,
								&StateData)) {
						return (ERROR);
					}
				}
				return (ERROR);
			}

			/*
			 * Setup symlinks for any files found in the
			 * transfer_list which depend on this package.
			 */
			if (_process_transferlist(trans, np) == ERROR) {
				write_notice(ERRMSG,
					MSG0_PKG_INSTALL_INCOMPLETE);
				if (ApplicationCallback) {
					StateData.State = SoftUpdateEnd;
					if (ApplicationCallback(ApplicationData,
								&StateData)) {
						return (ERROR);
					}
				}
				return (ERROR);
			}
		}

		/*
		 * the progress display is terminated here, just after all
		 * pkgadds are done.  If the callback is provided call it to
		 * signify that the processing is complete.
		 */
		if (ApplicationCallback) {
			StateData.State = SoftUpdateEnd;
			if (ApplicationCallback(ApplicationData, &StateData)) {
				return (ERROR);
			}
		}

		/* open the product file */
		if (_open_product_file(cur_prod->info.prod) != NOERR) {
			write_notice(ERRMSG, MSG0_SOFTINFO_CREATE_FAILED);
			return (ERROR);
		}

		/* log the installed locales */
		if (_create_locales_installed(cur_prod->info.prod) != NOERR) {
			write_notice(ERRMSG, MSG0_LOCINST_CREATE_FAILED);
			return (ERROR);
		}

		/* create release file for product */
		if (_create_inst_release(cur_prod->info.prod) != NOERR) {
			write_notice(ERRMSG, MSG0_RELEASE_CREATE_FAILED);
			return (ERROR);
		}

		(void) snprintf(name, sizeof (name),
				"%s %s", cur_prod->info.prod->p_name,
				cur_prod->info.prod->p_version);

		if (inst_status == NOERR) {
			write_status(LOGSCR, LEVEL0,
				MSG1_PKG_INSTALL_SUCCEEDED,
				name);
		} else {
			write_status(LOGSCR, LEVEL0,
				MSG1_PKG_INSTALL_PARTFAIL,
				name);
		}
	}

	return (NOERR);
}

/*
 * Function:	_install_pkg
 * Description:	Install the specified package onto the system.
 * Scope:	private
 * Parameters:	np	- Node pointer for package list
 *		dummy	- required for walklist, but not used in this routine
 *		maxlen	- max length of package dir being installed
 * Return:	NOERR	- success
 *		ERROR	- error occurred
 */
/*ARGSUSED1*/
static int
_install_pkg(Node *np,
    caddr_t dummy,
    int maxlen,
    TCallback *ApplicationCallback,
    void *ApplicationData)
{
	Modinfo *mp;
	int	results;

	mp = (Modinfo *)np->data;

	/* if pkg is not selected, or pkg_arch is not sys_arch, cont */
	if (mp->m_status == UNSELECTED ||
			_arch_cmp(mp->m_arch, get_default_impl(),
				get_default_inst()) != TRUE)
		return (NOERR);

	/* create admin file if package should be installed */
	admin_f->basedir = mp->m_basedir;
	if (_build_admin(admin_f) != NOERR)
		return (ERROR);

	if (mp->m_flags & IS_VIRTUAL_PKG) {
		results = _add_virtual_pkg(mp->m_pkgid,
					    mp->m_arch,
					    mp->m_pkg_dir,
					    pkg_params,
					    prod_dir);
	} else {
		/* add current package */
		results = _add_local_pkg(mp->m_pkg_dir,
					maxlen,
					pkg_params,
					prod_dir,
					ApplicationCallback,
					ApplicationData);
	}

	if (results == NOERR || results == PKGREBOOT ||
			results == PKGIREBOOT)
		mp->m_status = INSTALL_SUCCESS;
	else {
		mp->m_status = INSTALL_FAILED;
		inst_status = ERROR;
	}

	return (NOERR);
}

/*
 * Function:	_open_product_file
 * Description: Open/create the product release file on the targetted install
 *		image for appended writing. Log the current product information.
 *		The softinfo directory is also created if one does not already
 *		exist. The file is in the softinfo directory, and has a name of
 *		the form:
 *
 *			<PRODUCT>_<VERSION>
 *
 *		The file is set to no buffering to avoid the need to
 *		close the file upon completion. The file format is:
 *			OS=<product name>
 *			VERSION=<product version>
 *			REV=<product revision>
 * Scope:	private
 * Parameters:	prod	- non-NULL Product structure pointer
 * Return:	NOERR	- product file open
 *		ERROR	- product file open failed
 */
static int
_open_product_file(Product *prod)
{
	char	path[MAXPATHLEN];
	FILE	*fp;

	/* if execution is simulated, return immediately */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	(void) snprintf(path, sizeof (path), "%s%s/%s_%s", get_rootdir(),
		SYS_SERVICES_DIRECTORY, prod->p_name, prod->p_version);

	if ((fp = fopen(path, "a")) != NULL) {
		(void) fprintf(fp, "OS=%s\nVERSION=%s\nREV=%s\n",
			prod->p_name, prod->p_version, prod->p_rev);
		(void) fclose(fp);
		return (NOERR);
	}

	return (ERROR);
}

/*
 * Function:	_pkg_status
 * Description: Function used in walklist() to print the status of the node.
 * Scope:	private
 * Parameters:	np	- node pointer to current node being processed
 *		dummy	- required parameter for walklist, but not used here
 * Return:	0	- always returns this value
 */
/*ARGSUSED1*/
static int
_pkg_status(Node *np, caddr_t dummy)
{
	Modinfo * 	mp;
	uchar_t		log;

	mp = (Modinfo *) np->data;

	/* log successful packages only for execution simulation */
	log = (GetSimulation(SIM_EXECUTE) ? LOGSCR : LOG);

	if (mp->m_status == cur_stat) {
		if (cur_stat == INSTALL_SUCCESS) {
			if (have_one == 0) {
				write_status(log, LEVEL0,
					PKGS_FULLY_INSTALLED, product);
			}
			write_status(log, LEVEL2, mp->m_pkgid);
		} else if (cur_stat == INSTALL_FAILED) {
			if (have_one == 0) {
				write_status(LOGSCR, LEVEL0,
					PKGS_PART_INSTALLED, product);
			}
			write_status(LOGSCR, LEVEL2, mp->m_pkgid);
		}
		have_one++;
	}
	return (0);
}

/*
 * Function:	_print_results
 * Description: Walk through the linked list of products. Walk the package
 *		chain for each product and print out the names of those
 *		packages which have an INSTALL_SUCCESS status. Thne walk
 *		through the chain and print out then names of those packages
 *		which have an INSTALL_FAILED status (partials).
 * Scope:	private
 * Parameters:	prod	  - pointer to the head of product list to be printed
 * Return:	none
 */
static void
_print_results(Module *prod)
{
	Module	*t;

	for (t = prod; t != NULL; t = t->next) {
		(void) snprintf(product, sizeof (product), "%s %s",
			t->info.prod->p_name, t->info.prod->p_version);

		/* look for all packages with a successful install status */

		have_one = 0;
		cur_stat = INSTALL_SUCCESS;
		(void) walklist(t->info.prod->p_packages, _pkg_status,
				(caddr_t)NULL);
		if (have_one == 0)
			write_status(LOG, LEVEL2, NONE_STRING);

		/* look for all packages with an unsuccessful install status */
		have_one = 0;
		cur_stat = INSTALL_FAILED;
		(void) walklist(t->info.prod->p_packages, _pkg_status,
				(caddr_t)NULL);
	}
}

/*
 * Function:	_process_transferlist
 * Description: This function is called after every pkgadd to determine if any
 *		of the files in the transfer list are part of the installed
 *		package.
 *		If a file is to be processed the newly installed file is
 *		replaced by a symlink to the proto dir file and the access
 *		permissions are stored for latter use.
 * Scope:	private
 * Parameters:	transL	- a pointer to the TransList structure list to be
 *			  processed.
 *		np	- a node pointer for a package list (used to get the
 *			  package name).
 * Return:	ERROR - processing of transfer list for this package
 *			failed. REASONS: couldn't determine package name, or
 *			transferlist is corrupted.
 *		NOERROR - processing of transfer list for this package succeeded
 *			or this is not an indirect installation.
 * Note:	This assumes that the max length of a package name is 9
 *		characters. This is in compliance with the packaging API.
 */
static int
_process_transferlist(TransList **transL, Node *np)
{
	char		*pkg_id;	/* the name pf the package	*/
	int		i = 0;		/* loop counter			*/
	static int	done = 0;	/*  found and processed counter	*/
	struct stat	Stat_buf,
			tmpBuf;		/* Junk buffer for test read 	*/
	char		tmpFile[MAXPATHLEN];	/* proto dir file name	*/
	char		aFile[MAXPATHLEN];	/* name of /a file	*/
	TransList	*trans = *transL;
	Modinfo 	*mp;

	mp = (Modinfo *)np->data;

	/*
	 * do not process the transferlist for direct installations or
	 * execution simulations
	 */
	if (DIRECT_INSTALL || GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/* Determine the name (id) of the package */
	if (mp->m_pkgid != NULL)
		pkg_id = mp->m_pkgid;
	else if (mp->m_pkginst != NULL)
		pkg_id = mp->m_pkginst;
	else				/* no valid name found		*/
		return (ERROR);

	/* Make sure the 1st element of array has a good size */
	if (trans[0].found <= 0) {
		write_notice(ERRMSG, MSG0_TRANS_CORRUPT);
		return (ERROR);
	}

	/* Step through the transfer array looking for items to process */
	for (i = 1; i <= trans[0].found; i++) {
		/* Check to see if all the items have been processed */
		if (done == trans[0].found)
			break;

		/* has this item been found? */
		if (trans[i].found != 0)
			continue;

		/* does the package match this element? */
		if (strcmp(trans[i].package, pkg_id) == 0) {
			/* Check to see if the file name is not null */
			if (trans[i].file == NULL)
				continue;
			/*
			 * Make up the file names.
			 * file being checked is in /a
			 * file being created is in proto dir
			 */
			(void) snprintf(tmpFile, sizeof (tmpFile),
				"%s%s", get_protodir(), trans[i].file);
			canoninplace(tmpFile);
			(void) snprintf(aFile, sizeof (aFile), "%s%s",
				get_rootdir(), trans[i].file);
			/*
			 * Get the information about the newly installed
			 * file. It is maybe OK if this fails. It could
			 * just mean that the file is not in this package.
			 */
			if (stat(aFile, &Stat_buf) >= 0) {
				/* If the file is not in /tmp/root don't */
				/* do anything */
				if (stat(tmpFile, &tmpBuf) > 0) {
					/* First: Remove the pkgadded file */
					(void) unlink(aFile);

					/* Then: Link the files together */
					if (symlink(tmpFile, aFile) < 0) {
						write_notice(WARNMSG,
							MSG2_LINK_FAILED,
							tmpFile,
							aFile);
						return (ERROR);
					}
				}
			} else {
				/* If the aFile does not exist get the */
				/* info for the proto dir file */
				if (stat(tmpFile, &Stat_buf) < 0)
					continue;
			}

			/* Store the file information for later use. */
			trans[i].mode = Stat_buf.st_mode;
			trans[i].uid = Stat_buf.st_uid;
			trans[i].gid = Stat_buf.st_gid;
			trans[i].found = 1;
			done++;
		}
	}
	*transL = trans;
	return (NOERR);
}

/*
 * Function:	_setup_software_results
 * Description:	Copy the .clustertoc to the installed system and create
 *		the CLUSTER software administration files.
 * Scope:	private
 * Parameters:	prod	- pointer to product structure
 * Return:	NOERR	- results file set up successfully
 *		ERROR	- results file failed to set up
 */
static int
_setup_software_results(Module *prod)
{
	char	path[MAXPATHLEN] = "";
	FILE	*fp;
	Module  *mp;

	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	/* copy the .clustertoc file.  */
	(void) snprintf(path, sizeof (path), "%s%s/.clustertoc",
		get_rootdir(), SYS_ADMIN_DIRECTORY);
	if (_copy_file(path, get_clustertoc_path(NULL)) != NOERR)
		return (ERROR);

	/* create the .platform file */
	if (write_platform_file(get_rootdir(), prod) != SUCCESS)
		return (ERROR);

	WALK_LIST(mp, get_current_metacluster()) {
		if (mp->info.mod->m_status == SELECTED ||
				mp->info.mod->m_status == REQUIRED)
			break;
	}

	if (mp == NULL)
		return (ERROR);

	/*
	 * Create the CLUSTER file based on the current metacluster
	 */
	(void) snprintf(path, sizeof (path), "%s%s/CLUSTER",
		get_rootdir(), SYS_ADMIN_DIRECTORY);
	if ((fp = fopen(path, "a")) != NULL) {
		(void) fprintf(fp, "CLUSTER=%s\n", mp->info.mod->m_pkgid);
		(void) fclose(fp);
		return (NOERR);
	}

	return (ERROR);
}

/*
 * Function:	_refresh_package_db
 * Description:	Refresh the legacy contents file with entries
 *		that need to be consistent between the legacy contents
 *		file and the package database.
 * Scope:	private
 * Parameters:	rootdir - The root of the system to refresh
 * Return:	NOERR	- contents file refreshed up successfully,
 *		ERROR	- contents file not refreshed successfully.
 */
static int
_refresh_package_db(char *rootdir)
{
	char	cmd[MAXPATHLEN];

	/* don't attempt to refresh anything during simulation */
	if (GetSimulation(SIM_EXECUTE))
		return (NOERR);

	if (snprintf(cmd, MAXPATHLEN, "/usr/bin/pkgadm refresh -R %s",
	    rootdir) > MAXPATHLEN) {
		return (ERROR);
	}

	if (system(cmd) != 0) {
		return (ERROR);
	}

	return (NOERR);
}

/* Local Function Prototypes */

/*ARGSUSED*/
void
sigchild_interrupt_handler(int a_arg)
{
}

/*
 * Function:	_add_local_pkg
 * Description:	Adds the package specified by "pkgdir", using the command line
 *		arguments specified by "pkg_params".  "prod_dir" specifies the
 *		location of the package to be installed. Has both an interactive
 *		and non-interactive mode.
 * Scope:	private
 * Parameters:	pkg_dir		- directory containing package
 *		pkg_params	- packaging command line arguments
 *		prod_dir	- pathname for package to be installed
 * Returns	NOERR		- successful
 *		ERROR		- Exit Status of pkgadd
 */
static int
_add_local_pkg(char *pkg_dir,
    int maxlen,
    PkgFlags *pkg_params,
    char *prod_dir,
    TCallback *ApplicationCallback,
    void *ApplicationData)
{
	TSoftUpdateStateData StateData;
	char	*cmdline[64];
	char	buf[MAXPATHLEN];
	char	buffer[IO_SIZE];
	int	fdin[2];
	int	fdout[2];
	int	n;
	int	pid;
	int	processExited = 0;
	int	size;
	int	spool = FALSE;
	pid_t	waitstat;
	uint_t	status_loc = 0;
	void	(*func)();

	/*
	 * If the calling application provided a callback then call it
	 * with the state set to SoftUpdatePkgAddBegin.
	 */

	if (ApplicationCallback) {
		StateData.State = SoftUpdatePkgAddBegin;
		(void) strcpy(StateData.Data.PkgAddBegin.PkgDir, pkg_dir);
		StateData.Data.PkgAddBegin.maxlen = maxlen;
		if (ApplicationCallback(ApplicationData, &StateData)) {
			return (ERROR);
		}
	}

	if (GetSimulation(SIM_ANY)) {
		if (ApplicationCallback) {
			StateData.State = SoftUpdatePkgAddEnd;
			(void) strcpy(StateData.Data.PkgAddBegin.PkgDir,
								pkg_dir);
			if (ApplicationCallback(ApplicationData, &StateData)) {
				return (ERROR);
			}
		}
		return (SUCCESS);
	}

	/* set up pipe to collect output from pkgadd */

	if (pipe(fdout) == -1) {
		return (ERROR);
	}

	/* set up pipe to provide input to pkgadd if interactive */

	if ((pkg_params->notinteractive == 0) && (pipe(fdin) == -1)) {
		return (ERROR);
	}

	/*
	 * construct command to execute: if spooling, call
	 * pkgtrans; otherwise, call pkginstall.
	 */

	/* use pkg_params to set command line */

	if (pkg_params != NULL && pkg_params->spool != NULL) {
		n = 0;
		cmdline[n++] = "/usr/bin/pkgtrans";
		cmdline[n++] = "-o";
		if (prod_dir != NULL)
			cmdline[n++] = prod_dir;
		else
			cmdline[n++] = "/var/spool/pkg";

		if (pkg_params->basedir != NULL) {
			(void) snprintf(buf, sizeof (buf),
				"%s/%s",
				pkg_params->basedir,
				pkg_params->spool);
			cmdline[n++] = buf;
		} else {
			cmdline[n++] = pkg_params->spool;
		}

		cmdline[n++] = pkg_dir;
		cmdline[n++] = (char *)0;
	} else {
		/*
		 * build args for pkginstall command line;
		 * call pkginstall directly because it is faster than
		 * calling pkgadd - pkgadd does checking that is not
		 * necessary here, eventually calling pkginstall anyway.
		 */

		n = 0;
		cmdline[n++] = "/usr/sadm/install/bin/pkginstall";

		/* use pkg_params to set command line */

		if (pkg_params != NULL) {
			if (pkg_params->accelerated == 1)
				cmdline[n++] = "-I";
			if (pkg_params->silent == 1)
				cmdline[n++] = "-S";
			if (pkg_params->checksum == 1)
				cmdline[n++] = "-C";
			if (pkg_params->basedir != NULL) {
				cmdline[n++] = "-R";
				cmdline[n++] = pkg_params->basedir;
			}
			if (getset_admin_file(NULL) != NULL) {
				cmdline[n++] = "-a";
				cmdline[n++] =
				    (char *)getset_admin_file(NULL);
			}
			if (pkg_params->notinteractive == 1)
				cmdline[n++] = "-n";
		} else {
			if (getset_admin_file(NULL) != NULL) {
				cmdline[n++] = "-a";
				cmdline[n++] = (char *)getset_admin_file(NULL);
			}
		}

		/* -N pkgadd: set name for pkginstall to report */

		cmdline[n++] = "-N";
		cmdline[n++] = "pkgadd";

		if (prod_dir != NULL) {
			cmdline[n++] = prod_dir;
		} else {
			cmdline[n++] = "/var/spool/pkg";
		}

		cmdline[n++] = pkg_dir;
		cmdline[n++] = (char *)0;
	}

	/* flush standard i/o before creating new process */

	(void) fflush(stderr);
	(void) fflush(stdout);

	/*
	 * create new process to execute command in;
	 * vfork() is being used to avoid duplicating the parents
	 * memory space - this means that the child process may
	 * not modify any of the parents memory including the
	 * standard i/o descriptors - all the child can do is
	 * adjust interrupts and open files as a prelude to a
	 * call to exec().
	 */

	if ((pid = vfork()) == 0) {
		/*
		 * this is the child process
		 */

		int	i;

		/* reset any signals to default */

		for (i = 0; i < NSIG; i++) {
			(void) sigset(i, SIG_DFL);
		}

		/* ignore signals that might interrupt if default */

		(void) sigignore(SIGALRM);
		(void) sigignore(SIGCHLD);

		/* set stdin if interactive */

		if (pkg_params->notinteractive == 0) {
			if (fdin[0] != STDIN_FILENO) {
				(void) dup2(fdin[0], STDIN_FILENO);
				if (fdin[0] != STDIN_FILENO) {
					(void) close(fdin[0]);
				}
			}
			/* close pipe writer [stdin] */
			(void) close(fdin[1]);
		}

		/* place stdout and stderr on single pipe writer */

		(void) dup2(fdout[1], STDOUT_FILENO);
		(void) dup2(fdout[1], STDERR_FILENO);

		/* close all other file descriptors in child */

		closefrom(3);

		(void) execv(cmdline[0], cmdline);
		write_notice(ERROR, MSG0_PKGADD_EXEC_FAILED);
		_exit(99);

	} else if (pid == -1) {
		if (pkg_params->notinteractive == 0) {
			(void) close(fdin[0]);
			(void) close(fdin[1]);
		}

		(void) close(fdout[1]);
		(void) close(fdout[0]);
		return (ERROR);
	}

	/*
	 * this is the parent process
	 */

	/* close pipe writer [stdout/stderr] */

	(void) close(fdout[1]);

	if (pkg_params->notinteractive == 0) {
		/* close pipe reader [stdin] */

		(void) close(fdin[0]);

		if (ApplicationCallback) {
			StateData.State = SoftUpdateInteractivePkgAdd;
			if (ApplicationCallback(ApplicationData, &StateData)) {
				return (ERROR);
			}
		}

		/* close pipe writer [stdin] */

		(void) close(fdin[1]);
	} else {

		/* turn off sigchild interrupts */

		func = signal(SIGCHLD, sigchild_interrupt_handler);

		/* read data from pkgadd until EOF or error */

		for (;;) {
			size = read(fdout[0], buffer, sizeof (buffer)-1);

			/* if error either ignore or treat as EOF */

			if (size == -1) {
				if (errno == EAGAIN) {
					continue;
				}
				if (errno == EINTR) {
					continue;
				}
				break;
			}

			/* break out on EOF */

			if (size == 0) {
				break;
			}

			/* hold alarm/child interrupts for write_status_nofmt */

			(void) sighold(SIGALRM);
			(void) sighold(SIGCHLD);

			buffer[size] = '\0';
			write_status_nofmt(LOG,
					LEVEL0|CONTINUE|FMTPARTIAL, buffer);

			/* enable interrupts disabled for write_status_nofmt */

			(void) sigrelse(SIGALRM);
			(void) sigrelse(SIGCHLD);
		}

		/* all data written to log - reap child process status */

		while (processExited == 0) {
			waitstat = waitpid(pid, (int *)&status_loc, 0);
			if (waitstat < 0) {
				/* waitpid returned error */
				if (errno == EAGAIN) {
					/* try again */
					continue;
				}
				if (errno == EINTR) {
					continue;
				}
				/* error from waitpid: bail */
				processExited++;
				continue;
			} else if (waitstat > 0) {
				/* child exit status available */
				processExited++;
				continue;
			}
		}

		/* enable sigchild interrupts */

		(void) signal(SIGCHLD, func);

	}

	/* close pipe reader [stdout/stderr] */

	(void) close(fdout[0]);

	if (ApplicationCallback) {
		StateData.State = SoftUpdatePkgAddEnd;
		(void) strcpy(StateData.Data.PkgAddBegin.PkgDir, pkg_dir);
		if (ApplicationCallback(ApplicationData, &StateData)) {
			return (ERROR);
		}
	}
	return (WEXITSTATUS(status_loc) == 0 ? NOERR : ERROR);
}

/*
 * Function:	_add_virtual_pkg
 * Description:	Records the flags necessary to do a pkgadd of this package
 *		when it becomes available.
 * Scope:	private
 * Parameters:	pkg_dir		- directory containing package
 *		pkg_params	- packaging command line arguments
 *		prod_dir	- pathname for package to be installed
 * Returns:	NOERR		- successful
 *		ERROR		- recording failed
 */
static int
_add_virtual_pkg(char *pkg,
    char *arch,
    char *pkg_dir,
    PkgFlags *pkg_params,
    char *prod_dir)
{
	char buf[1024];
	char path[MAXPATHLEN];
	char *adminfile;
	FILE *fp, *afp;

	if (GetSimulation(SIM_ANY)) {
		return (NOERR);
	}

	(void) snprintf(path, sizeof (path),
			"%s/var/sadm/system/data", get_rootdir());
	if (access(path, X_OK) != 0) {
		if (_create_dir(path) != NOERR) {
			return (ERROR);
		}
	}

	(void) snprintf(path, sizeof (path),
		"%s/var/sadm/system/data/packages_to_be_added",
		get_rootdir());
	if ((fp = fopen(path, "a")) == NULL) {
		return (ERROR);
	}

	(void) fprintf(fp, "PKG=%s\n", pkg);
	(void) fprintf(fp, "ARCH=%s\n", arch);
	(void) fprintf(fp, "PKGDIR=%s\n", pkg_dir);

	if (pkg_params != NULL && pkg_params->spool != NULL) {
		(void) fprintf(fp, "TYPE=PKGTRANS\n");
		(void) fprintf(fp, "FLAGS=OVERWRITE\n");

		if (pkg_params->basedir != NULL) {
			(void) fprintf(fp, "SPOOLDIR=%s/%s\n",
				pkg_params->basedir, pkg_params->spool);
		} else {
			(void) fprintf(fp, "SPOOLDIR=%s\n", pkg_params->spool);
		}
	} else if (pkg_params == NULL || pkg_params->spool == NULL) {
		(void) fprintf(fp, "TYPE=PKGADD\n");

		if (pkg_params != NULL) {
			if (pkg_params->accelerated == 1)
				(void) fprintf(fp, "FLAGS=ACCELERATED\n");
			if (pkg_params->silent == 1)
				(void) fprintf(fp, "FLAGS=SILENT\n");
			if (pkg_params->checksum == 1)
				(void) fprintf(fp, "FLAGS=CHECKSUM\n");
			if (pkg_params->notinteractive == 1)
				(void) fprintf(fp, "FLAGS=NOTINTERACTIVE\n");
			if (pkg_params->basedir != NULL)
				(void) fprintf(fp, "BASEDIR=%s\n",
					pkg_params->basedir);
		}
	}

	if (prod_dir != NULL) {
		(void) fprintf(fp, "PRODDIR=%s\n", prod_dir);
	} else {
		(void) fprintf(fp, "PRODDIR=/var/spool/pkg\n");
	}

	/* Print the admin file for all but spooled packages */
	if (pkg_params == NULL || pkg_params->spool == NULL) {
		if ((adminfile = getset_admin_file(NULL)) != NULL) {
			(void) fprintf(fp, "START ADMIN_FILE\n");

			if ((afp = fopen(adminfile, "r")) != NULL) {
				while (fgets(buf, 1023, afp) != NULL) {
					(void) fputs(buf, fp);
				}
				(void) fclose(afp);
			}

			(void) fprintf(fp, "END ADMIN_FILE\n");
		}
	}

	(void) fclose(fp);

	return (NOERR);
}

/*
 * Function:	max_pkgdir_len
 * Description:	Determines the length of the longest package name
 *		from a given product.  The package name is stored
 *		in the 'm_pkg_dir' member of each Module.
 *
 * Scope:		private
 *
 * Parameters:	cur_prod	- The Product to examine
 *
 * Returns:	A non-negative number representing the length of the
 *		longest Package name in the Product.  This value can
 *		be used, for example, to size a column containing the
 *		package names.
 */
static int
max_pkgdir_len(Product *cur_prod)
{
	Node	*np;
	int	len, maxlen = 0;

	for (np = cur_prod->p_packages->list->next;
		np != cur_prod->p_packages->list;
		np = np->next) {
		/* ignore null packages */
		if (((Modinfo*)np->data)->m_shared == NULLPKG) {
			continue;
		}

		len = strlen(((Modinfo *)np->data)->m_pkg_dir);
		if (len > maxlen) {
			maxlen = len;
		}
	}
	return (maxlen);
}
