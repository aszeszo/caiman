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

#pragma ident	"@(#)soft_sp_space.c	1.26	07/10/14 SMI"

#include "spmisoft_lib.h"
#include "sw_space.h"

#include <sys/stat.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <libintl.h>
#include <stropts.h>
#include <soft_hash_table.h>
#include <libcontract.h>
#include <libzonecfg.h>
#include <sys/contract/process.h>
#include <sys/ctfs.h>
#include <sys/wait.h>
#include "pkglib.h"
#include "dbsql.h"
#include "genericdb.h"
#include "spmizones_api.h"

/* Local Globals */
boolean_t is_child_zone_context = B_FALSE; /* set if zone entered in child */

/* Local Statics and Constants */
static	FSspace **cur_sp = NULL; /* current global space table */
static	FSspace **upg_xstab = NULL; /* extra space table */
static	FILE	*dfp = (FILE *)NULL;
static	boolean_t first_pass = B_TRUE; /* do counting and metering only once */
static	FILE	*locdbgfp = NULL;

/* Public Function Prototypes */
FSspace **swi_calc_cluster_space(Module *, ModStatus);
ulong	swi_calc_tot_space(Product *);
void	swi_free_space_tab(FSspace **);
void	swi_free_fsspace(FSspace *);
ulong	swi_tot_pkg_space(Modinfo *);
int	swi_calc_sw_fs_usage(FSspace **, int (*)(void *, void *), void *);
FSspace **gen_dflt_fs_spaceinfo(void);
void	find_modified(Module *mod);
int	is_flash_install(void);
int	archive_total_reqd_space(void);
void	set_global_space(FSspace **);

/* Library function prototypes */
int	calc_pkg_space(char *, Modinfo *, Product *);
FILE	*open_debug_print_file(void);
void	print_space_usage(FILE *, char *, FSspace **);

/* Local Function Prototypes */

static int	walk_add_mi_space(Node *, caddr_t);
static int	walk_add_unselect_cspace(Modinfo *, caddr_t);
static int	walk_add_unselect_cspace_list(Node *, caddr_t);
static int	walk_add_select_cspace(Modinfo *, caddr_t);
static int	walk_add_select_cspace_list(Node *, caddr_t);
static int	walk_upg_final_chk(Node *, Product *);
static int	walk_upg_preserved_pkgs(Node *np, caddr_t rootdir_p);
static int	walk_upg_final_chk_isspooled(Node *, caddr_t);
static int	add_space_upg_final_chk(Modinfo *, Product *);
static int	service_going_away(Module *);
static int	is_servermod(Module *);
static void	add_dflt_fs(Modinfo *, char *);
static void	sp_to_dspace(Modinfo *, FSspace **);
static void	add_contents_space(Product *, float);
static void	compute_pkg_ovhd(Modinfo *, char *);
static void	add_pkg_ovhd(Modinfo *, char *);
static int	walk_upg_final_chk_pkgdir(Node *, caddr_t);
static void	compute_patchdir_space(Product *);
static void	close_debug_print_file(FILE *);
static int	sp_add_patch_space(Product *, int);
static int	sp_add_products_space(Product *, char *);
static int	pkg_match(struct patdir_entry *, Product *);
static int	count_file_space(Node *, caddr_t);
static void	_count_file_space(Modinfo *, Product *);
static void	do_add_savedfile_space(Module *);
static FSspace	**calc_extra_contents(Module *, FSspace **);
static int	upg_calc_sw_fs_usage(FSspace **, int (*)(void *, void *),
		    void *);
static int	inin_calc_sw_fs_usage(FSspace **, int (*)(void *, void *),
		    void *);
static ulong	total_contents_lines(void);
static long	contents_lines(Module *);
static ulong	get_spooled_size(char *);
static int	upg_calc_zone(Module *, FSspace **, FSspace **);
static int	upg_calc_mod(Module *, char *, FSspace **, FSspace **);

/* Globals and Externals */

extern struct patch_space_reqd *patch_space_head;
extern	int	doing_add_service;

char	*slasha = NULL;
int	upg_state;
FILE	*ef = stderr;

char 	*Pkgs_dir;
static	FSspace **Tmp_fstab;

#define	ROOT_COMPONENT		0x0001
#define	NATIVE_USR_COMPONENT	0x0002
#define	NONNATIVE_USR_COMPONENT	0x0004
#define	OPT_COMPONENT		0x0008
#define	SPOOLED_COMPONENT	0x0010

/* ******************************************************************** */
/*			PUBLIC SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * tot_pkg_space()
 *	Add up all space fields the package uses.
 * Parameters:
 *	mp	-
 * Return:
 * Status:
 *	public
 */
ulong
swi_tot_pkg_space(Modinfo * mp)
{
	int 	i;
	ulong 	tot = 0;

	if (mp == NULL) {
		return (0);
	}

	for (i = 0; i < N_LOCAL_FS; i++)
		tot += mp->m_deflt_fs[i];

	return (tot);
}

/*
 * calc_cluster_space()
 *	Create a space table using the default mount points.
 *	Module must either correspond to a cluster or package.
 *	Populate the table based on space usage for the cluster
 *	package. This routine assumes only 1 product (read initial
 *	install)!
 * Parameters:
 *	mod	- pointer to cluster module
 *	status	- SELECTED or UNSELECTED (not currently implemented)
 *	flags	- calculation constraint flag:
 *			CSPACE_ARCH, CSPACE_LOCALE,
 *			CSPACE_NONE, or CSPACE_ALL
 * Return:
 *	NULL	- error
 *	!NULL	- space table pointer with space calculations per FS
 * Status:
 *	public
 */
FSspace **
swi_calc_cluster_space(Module *mod, ModStatus status)
{
	Module	*hmod, *prodmod;
	Product	*prod;
	static	FSspace	**sp = NULL;

	hmod = get_media_head();
	prodmod = hmod->sub;
	prod = prodmod->info.prod;
	Pkgs_dir = prod->p_pkgdir;

	if (mod == NULL)
		return ((FSspace **)NULL);

	if (sp == NULL) {
		sp = load_def_spacetab(NULL);
		if (sp == NULL)
			return ((FSspace **)NULL);
	} else {
		reset_stab(sp);
	}

	begin_global_qspace_sum(sp);
	if (status == UNSELECTED)
		walktree(mod, walk_add_unselect_cspace, (caddr_t)NULL);
	else if (status == SELECTED)
		walktree(mod, walk_add_select_cspace, (caddr_t)NULL);

	(void) end_global_space_sum();
	return (sp);
}

/*
 * Name:	calc_package_space
 * Description:	Create a space table using the default mount points.  This space
 *		table is populated using the sizes of the selected packages in
 *		the passed product.
 * Arguments:	mod	- [RO, *RO] (Module *)
 *			  The product to be sized
 *		status	- [RO] (ModStatus)
 *			  Whether we are to calculate the selected (SELECTED)
 *			  size or the unselected (UNSELECTED) size.
 * Returns:	FSspace **	- The populated space table
 *		NULL		- Invalid arguments or an error in the space
 *				  calculations.
 */
FSspace **
swi_calc_package_space(Module *mod, ModStatus status)
{
	Module *hmod, *prodmod;
	Product *prod;
	static  FSspace **sp = NULL;

	hmod = get_media_head();
	prodmod = hmod->sub;
	prod = prodmod->info.prod;
	Pkgs_dir = prod->p_pkgdir;

	/* Validate arguments */
	if (mod == NULL || mod->type != PRODUCT) {
		return ((FSspace **)NULL);
	}

	if (status != SELECTED && status != UNSELECTED) {
		return ((FSspace **)NULL);
	}

	/* Initialize the space table */
	if (sp == NULL) {
		sp = load_def_spacetab(NULL);
		if (sp == NULL) {
			return ((FSspace **)NULL);
		}
	} else {
		reset_stab(sp);
	}

	/* Populate the space table */
	begin_global_qspace_sum(sp);

	if (status == UNSELECTED) {
		walklist(mod->info.prod->p_packages,
		    walk_add_unselect_cspace_list, (caddr_t)NULL);
	} else if (status == SELECTED) {
		walklist(mod->info.prod->p_packages,
		    walk_add_select_cspace_list, (caddr_t)NULL);
	}

	(void) end_global_space_sum();

	return (sp);
}

/*
 * calc_tot_space()
 *	Walk packages list adding up space for selected packages.
 * Parameters:
 *	prod	-
 * Return:
 *
 * Status:
 *	public
 */
ulong
swi_calc_tot_space(Product * prod)
{
	static	FSspace	**sp = NULL;
	ulong	sum;
	int	i;

	if (prod == NULL) {
#ifdef DEBUG
		(void) fprintf(ef, "DEBUG: calc_tot_space():\n");
		(void) fprintf(ef, "Passed a NULL pointer.\n");
#endif
		return (NULL);
	}


	Pkgs_dir = prod->p_pkgdir;

	if (sp == NULL) {
		sp = load_def_spacetab(NULL);
		if (sp == NULL)
			return (NULL);
	} else {
		reset_stab(sp);
	}

	cur_sp = sp;

	begin_global_qspace_sum(sp);

	(void) walklist(prod->p_packages, walk_add_mi_space, NULL);

	(void) end_global_space_sum();

	for (sum = 0, i = 0; sp[i]; i++) {
		if (sp[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;
		sum += sp[i]->fsp_reqd_contents_space;
	}
	return (sum);
}

/*
 * free_space_tab()
 *	Free space used by a space table.
 * Parameters:
 *	sp	-
 * Return:
 *	none
 * Status:
 *	public
 */
void
swi_free_space_tab(FSspace **sp)
{
	int	i;

	if (sp == NULL)
		return;
	for (i = 0; sp[i]; i++) {
		free_fsspace(sp[i]);
	}
	(void) free(sp);
}

/*
 * calc_pkg_space()
 *	Calculate the default space for each pkg on a cd. Reads the
 *	packages pkgmap and space file and creates a space table which
 *	is attached to the modinfo structure.
 * Parameters:
 *	pkgmap_path - full path to package map file
 *	mp	    -
 * Return:
 *	SP_ERR_PARAM_INVAL	- invalid package map file or
 *				  invalid modinfo pointer
 *	SUCCESS			- space calculated correctly
 *	other			- return values from subroutines
 * Status:
 *	public
 */
int
calc_pkg_space(char *pkgmap_path, Modinfo *mp, Product *prod)
{
	int	ret;
	static	FSspace	**sp = NULL;
	char	*cp;
	char	space_path[MAXPATHLEN];

	if (mp == NULL || pkgmap_path == NULL)
		return (SP_ERR_PARAM_INVAL);

	/*
	 * Set path to space file.
	 */
	if (strlcpy(space_path, pkgmap_path, sizeof (space_path))
				>= sizeof (space_path))
		return (SP_ERR_PATH_INVAL);
	cp = strrchr(space_path, '/');
	*cp = '\0';
	if (strlcat(space_path, "/install/space", sizeof (space_path))
				>= sizeof (space_path))
		return (SP_ERR_PATH_INVAL);

	if (sp == NULL)
		sp = load_def_spacetab(NULL);
	else
		reset_stab(sp);

	begin_specific_space_sum(sp);

	load_inherited_FSs(prod);

	ret = sp_read_pkg_map(pkgmap_path, mp->m_pkg_dir, prod,
	    mp->m_basedir, SP_CNT_DEVS, sp);

	if (ret != SUCCESS) {
		return (ret);
	}

	if (path_is_readable(space_path) == SUCCESS) {
		ret = sp_read_space_file(space_path, prod, NULL, sp);

		if (ret != SUCCESS) {
			return (ret);
		}
	}

	end_specific_space_sum(sp);
	sp_to_dspace(mp, sp);

	return (SUCCESS);
}

int
swi_calc_sw_fs_usage(FSspace **fs_list, int (*callback_proc)(void *, void*),
	void *callback_arg)
{
	if (is_upgrade() || doing_add_service)
		return (upg_calc_sw_fs_usage(fs_list, callback_proc,
		    callback_arg));
	else
		return (inin_calc_sw_fs_usage(fs_list, callback_proc,
		    callback_arg));
}

/*
 * gen_dflt_fs_spaceinfo()
 *	Allocate a space table based on the default mount points.
 *	Run the software tree and populate the table.
 * Parameters:
 *
 * Return:
 * 	NULL	 - invalid mount point list
 *	Space ** - pointer to allocated and initialized array of space
 *		   structures
 * Status:
 *	public
 */
FSspace **
gen_dflt_fs_spaceinfo(void)
{
	Module	*mod, *prodmod;
	Product	*prod;
	static	FSspace **new_sp = NULL;
	static	int prev_null = 0;

	if ((mod = get_media_head()) == (Module *)NULL) {
		return (NULL);
	}

	prodmod = mod->sub;
	prod = prodmod->info.prod;
	Pkgs_dir = prod->p_pkgdir;

	/* set up the space table */
	if (prev_null == 1) {
		/* Reuse table. */
		sort_spacetab(new_sp);
		reset_stab(new_sp);
	} else {
		free_space_tab(new_sp);
		new_sp = load_def_spacetab(NULL);
	}
	prev_null = 1;

	if (new_sp == NULL)
		return (NULL);

	if (calc_sw_fs_usage(new_sp, NULL, NULL) != SUCCESS)
		return (NULL);

	return (new_sp);
}


/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

/*
 * walk_add_mi_space()
 *	walklist() processing routine used to add modinfo space.
 * Parameters:
 *	np	   - current node being processed
 * 	rootdir_p  - package root directory
 * Return:
 *	0
 * Status:
 *	private
 */
static int
walk_add_mi_space(Node *np, caddr_t rootdir_p)
{
	Modinfo	*i, *j;

	for (i = (Modinfo *)np->data; i != (Modinfo *)NULL; i = next_inst(i)) {
		for (j = i; j != (Modinfo *) NULL; j = next_patch(j)) {
			if (meets_reqs(j))
				add_dflt_fs(j, rootdir_p);
		}
	}
	i = (Modinfo *)np->data;

	if (get_trace_level() > 0) {
		char buf[BUFSIZ];
		(void) snprintf(buf, sizeof (buf),
			"walk_add_mi_space:after adding %s", i->m_pkgid);
		print_space_usage(dfp, buf, cur_sp);
	}
	return (0);
}

/*
 * walk_add_unselect_cspace()
 *	Add space for all patches associated with a given module. The flags
 *	field is used to specify the conditions under which an instance or
 *	localization module should be included.  This function is designed to
 *	be invoked by walktree.
 * Parameters:
 *	mod	- pointer to current module being processed
 *	flags	- CSPACE_ALL, CSPACE_ARCH, CSPACE_NONE, or CSPACE_LOCALE
 * Return:
 *	0	- always returns this
 * Status:
 *	private
 */
/*ARGSUSED1*/
static int
walk_add_unselect_cspace(Modinfo *mod, caddr_t flags)
{
	Modinfo	*i;

	for (i = mod; i != (Modinfo *) NULL; i = next_patch(i)) {
			add_dflt_fs(i, "/");
	}

	return (0);
}

/*
 * Name:	walk_add_unselect_cspace_list
 * Description:	An interface for walk_add_unselect_cspace that allows
 *		invocation via walklist.
 * Arguments:	n	- [RO, *RO] (Node *)
 *			  The module to be passed down
 *		flags	- [RO] (caddr_t)
 *			  Unused
 * Returns:	0	- always
 */
static int
walk_add_unselect_cspace_list(Node *n, caddr_t flags)
{
	Modinfo *mi;

	mi = (Modinfo *)n->data;

	return (walk_add_unselect_cspace(mi, flags));
}

/*
 * walk_add_select_cspace()
 *	Add space for a clusters components which are SELECTED, REQUIRED,
 *	or PARTIALLY_SELECTED.  This function in designed to be invoked by
 *	walktree.
 * Parameters:
 *	mod	- current module pointer
 *	flags	- ignored
 * Return:
 *	0	- always returns this
 * Status:
 *	private
 */
/*ARGSUSED1*/
static int
walk_add_select_cspace(Modinfo *mod, caddr_t flags)
{
	Modinfo	*i;

	for (i = mod; i != (Modinfo *) NULL; i = next_patch(i)) {

		if ((i->m_status == SELECTED) ||
			(i->m_status == REQUIRED) ||
			(i->m_status == PARTIALLY_SELECTED)) {
			add_dflt_fs(i, "/");
		}
	}
	return (0);
}

/*
 * Name:	walk_add_select_cspace_list
 * Description:	An interface for walk_add_select_cspace that allows
 *		invocation via walklist.
 * Arguments:	n	- [RO, *RO] (Node *)
 *			  The module to be passed down
 *		flags	- [RO] (caddr_t)
 *			  Unused
 * Returns:	0	- always
 */
static int
walk_add_select_cspace_list(Node *n, caddr_t flags)
{
	Modinfo *mi;

	mi = (Modinfo *)n->data;

	return (walk_add_select_cspace(mi, flags));
}

/*
 * walk_upg_preserved_pkgs()
 * Parameters:
 *	np	  -
 *	rootdir_p -
 * Return:
 * Status:
 *	private
 * Globals modified:
 *	package overhead added to master FS usage
 *	mi->m_fs_usage contents record loaded
 */
static int
walk_upg_preserved_pkgs(Node *np, caddr_t rootdir_p)
{
	Modinfo	*orig_mod, *i, *j;
	char	path[MAXPATHLEN];

	orig_mod = (void *) np->data;
	for (i = orig_mod; i != (Modinfo *) NULL; i = next_inst(i)) {
		for (j = i; j != (Modinfo *) NULL; j = next_patch(j)) {
			if (meets_reqs(j)) {
				/* ModState */
				if (j->m_shared == SPOOLED_NOTDUP) {
					set_path(path, j->m_instdir, NULL, "/");
					add_file_blks(path, j->m_spooled_size,
					    0, SP_DIRECTORY, (FSspace **)NULL);
				} else {
					add_pkg_ovhd(j, rootdir_p);
					add_contents_record(j->m_fs_usage,
					    (FSspace **)NULL);
				}
			}
		}
	}
	return (0);
}

/*
 * walk_upg_final_chk_isspooled() - count the currently-spooled
 *	packages.
 *
 *	note:  If ProgressInCountMode() returns true, just count
 *		the spooled packages.
 * Parameters:
 *	np	  -
 *	rootdir_p -
 * Return:
 * 	0
 * Status:
 *	private
 */
/*ARGSUSED1*/
static int
walk_upg_final_chk_isspooled(Node *np, caddr_t data)
{
	Modinfo	*orig_mod, *i, *j;
	ulong	sp_sz;
	char	path[MAXPATHLEN];

	orig_mod = (void *) np->data;
	for (i = orig_mod; i != (Modinfo *) NULL; i = next_inst(i)) {
		for (j = i; j != (Modinfo *) NULL; j = next_patch(j)) {
			if (j->m_shared == SPOOLED_NOTDUP) {
				if (ProgressInCountMode())
					ProgressCountActions(PROG_DIR_DU, 1);
				else {
					if (j->m_spooled_size == 0) {
						set_path(path, slasha,
						    j->m_instdir, "/");
						if ((sp_sz =
						    get_spooled_size(path)) > 0)
							j->m_spooled_size =
							    sp_sz;
						ProgressAdvance(PROG_DIR_DU, 1,
						    VAL_SPOOLPKG_SPACE,
						    j->m_pkgid);
					}
					set_path(path, j->m_instdir, NULL, "/");
					add_file_blks(path, j->m_spooled_size,
					    0, SP_DIRECTORY, (FSspace **)NULL);
				}
			}
		}
	}
	return (0);
}

/*
 * walk_upg_final_chk()
 *	New pkgs and svcs.
 * Parameters:
 *	np	  -
 *	rootdir_p -
 * Return:
 *	return value from add_space_upg_final_chk()
 *	SUCCESS
 * Status:
 *	private
 * Side effects:
 *	see add_space_upg_final_chk()
 */
static int
walk_upg_final_chk(Node *np, Product *prod)
{
	int ret;
	Modinfo *orig_mod, *i, *j;

	orig_mod = (void *) np->data;
	for (i = orig_mod; i != (Modinfo *) NULL; i = next_inst(i)) {
		for (j = i; j != (Modinfo *) NULL; j = next_patch(j)) {
			if (meets_reqs(j)) {
				ret = add_space_upg_final_chk(j, prod);
				if (ret != SUCCESS)
					return (ret);
			}
		}
	}
	return (SUCCESS);
}

/*
 * add_space_upg_final_chk()
 *	New pkgs and svcs.
 * Parameters:
 *	mp	  -
 *	rootdir_p -
 * Return:
 * Status:
 *	private
 * Globals modified:
 *	sets mp->m_fs_usage, mp->m_pkgovhd_size, mp->m_spooled_size
 *	adds blocks to master fs space
 *	adds contents record to master fs space
 *	adds mi->m_pkgovhd_size to master fs space
 */
static int
add_space_upg_final_chk(Modinfo *mp, Product *prod)
{
	char	*rootdir, *bdir;
	char	path[MAXPATHLEN];
	char	pkgmap_path[MAXPATHLEN];
	char	space_path[MAXPATHLEN];
	long	sp_sz;
	int	ret;
	struct	stat	sbuf;

	if (mp->m_instdir)	bdir = mp->m_instdir;
	else			bdir = mp->m_basedir;

	rootdir = (prod->p_rootdir == NULL ? "/" : prod->p_rootdir);

	if (mp->m_action == TO_BE_SPOOLED) {
		if (ProgressInCountMode())
			return (SUCCESS);
		set_path(path, Pkgs_dir, NULL, mp->m_pkg_dir);
		if (mp->m_spooled_size == 0) {
			if ((sp_sz = get_spooled_size(path)) > 0)
			mp->m_spooled_size = (ulong) sp_sz;
		}
		if (slasha) {
			if (!do_chroot(slasha))
				return (SP_ERR_CHROOT);
		}
		add_file_blks(bdir, mp->m_spooled_size, 0, SP_DIRECTORY,
		    (FSspace **)NULL);
		if (slasha) {
			if (!do_chroot("/"))
				return (SP_ERR_CHROOT);
		}
		return (SUCCESS);
	}

	if (mp->m_fs_usage == NULL) {
		gen_pkgmap_path(pkgmap_path, Pkgs_dir, mp);
		if (snprintf(space_path, sizeof (space_path),
			"%s/%s/install/space", Pkgs_dir, mp->m_pkg_dir)
			>= sizeof (space_path)) {
			return (SP_ERR_PATH_INVAL);
		}

		if (ProgressInCountMode()) {
			if (stat(pkgmap_path, &sbuf) == 0)
				ProgressCountActions(PROG_PKGMAP_SIZE,
				    sbuf.st_size);
			return (SUCCESS);
		}

		reset_stab(Tmp_fstab);
		begin_specific_space_sum(Tmp_fstab);

		ret = sp_read_pkg_map(pkgmap_path, mp->m_pkg_dir, prod,
		    bdir, 0, Tmp_fstab);
		if (ret != SUCCESS) {
			end_specific_space_sum(Tmp_fstab);
			return (ret);
		}

		if (path_is_readable(space_path) == SUCCESS) {
			ret = sp_read_space_file(space_path, prod, bdir,
			    Tmp_fstab);
			if (ret != SUCCESS) {
				end_specific_space_sum(Tmp_fstab);
				return (ret);
			}
		}

		end_specific_space_sum(Tmp_fstab);
		mp->m_fs_usage = contents_record_from_stab(Tmp_fstab,
		    (ContentsRecord *)NULL);
		mp->m_pkgovhd_size = 10;  /* estimate 10 blks per package */
	}
	add_pkg_ovhd(mp, rootdir);
	add_contents_record(mp->m_fs_usage, (FSspace **)NULL);
	return (SUCCESS);
}

/*
 * add_dflt_fs()
 * Parameters:
 *	mp	  -
 *	rootdir_p -
 * Return:
 *	none
 * Status:
 *	private
 */
static void
add_dflt_fs(Modinfo *mp, char *rootdir_p)
{
	ulong 	num;
	long	sp_sz;
	char	*bdir;
	char 	path[MAXPATHLEN];

	if (mp->m_instdir)	bdir = mp->m_instdir;
	else			bdir = mp->m_basedir;

	/*
	 * We need to fix up the base dir if it is /usr. This is done to
	 * correctly get the /usr/openwin space added to the correct
	 * bucket. The problem is that some of the openwin package have a
	 * base dir of / and others have /usr, therefore to get the
	 * set_path to work correctly bdir must be set to /
	 */
	if (bdir != NULL && strcmp(bdir, "/usr") == 0)
	    bdir = "/";

	if (mp->m_action == TO_BE_SPOOLED) {
		set_path(path, Pkgs_dir, NULL, mp->m_pkg_dir);
		if (mp->m_spooled_size == 0) {
			if ((sp_sz = get_spooled_size(path)) > 0)
				mp->m_spooled_size = (ulong) sp_sz;
		}
		set_path(path, mp->m_instdir, NULL, "/");
		add_file_blks(path, mp->m_spooled_size, 0, SP_DIRECTORY,
		    (FSspace **)NULL);
		return;

	}

	num = mp->m_deflt_fs[ROOT_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[USR_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/usr");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[USR_OWN_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/usr/openwin");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[OPT_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/opt");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[VAR_FS];
	if (num != 0) {
		set_path(path, rootdir_p, NULL, "/var");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[EXP_EXEC_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/export/exec");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[EXP_ROOT_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/export/root");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[EXP_HOME_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/export/home");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
	num = mp->m_deflt_fs[EXPORT_FS];
	if (num != 0) {
		set_path(path, rootdir_p, bdir, "/export");
		add_file_blks(path, num, 0, SP_MOUNTP, (FSspace **)NULL);
	}
}

/*
 * sp_to_dspace()
 * Parameters:
 *	mp	-
 *	sp	-
 * Return:
 *	none
 * Status:
 *	private
 */
static void
sp_to_dspace(Modinfo *mp, FSspace **sp)
{
	int i;

	for (i = 0; i < N_LOCAL_FS; i++)
		mp->m_deflt_fs[i] = 0;

	for (i = 0; sp[i]; i++) {
		if (sp[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;
		if (strcmp(sp[i]->fsp_mntpnt, "/") == 0)
			mp->m_deflt_fs[ROOT_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/usr") == 0)
			mp->m_deflt_fs[USR_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/usr/openwin") == 0)
			mp->m_deflt_fs[USR_OWN_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/opt") == 0)
			mp->m_deflt_fs[OPT_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/var") == 0)
			mp->m_deflt_fs[VAR_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/export/exec") == 0)
			mp->m_deflt_fs[EXP_EXEC_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/export/root") == 0)
			mp->m_deflt_fs[EXP_ROOT_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/export/home") == 0)
			mp->m_deflt_fs[EXP_HOME_FS] =
			    sp[i]->fsp_reqd_contents_space;
		else if (strcmp(sp[i]->fsp_mntpnt, "/export") == 0)
			mp->m_deflt_fs[EXPORT_FS] =
			    sp[i]->fsp_reqd_contents_space;
	}
}

/*
 * service_going_away()
 *	A sevice which is going away.
 * Parameters:
 *	mod	-
 * Return:
 * Status:
 *	private
 */
static int
service_going_away(Module *mod)
{
	int flags;

	if (mod->info.media->med_type == INSTALLED_SVC) {
		flags = mod->info.media->med_flags;
		if ((flags & SVC_TO_BE_REMOVED) &&
			(!(flags & BASIS_OF_UPGRADE)))
			return (1);
	}
	return (0);
}

/*
 * is_servermod()
 * Parameters:
 *	mod	-
 * Return:
 *	0	-
 *	1	-
 * Status:
 *	private
 */
static int
is_servermod(Module *mod)
{
	if ((mod->info.media->med_type == INSTALLED) &&
		(mod->info.media->med_dir != NULL) &&
		(strcoll(mod->info.media->med_dir, "/") == 0))
		return (1);
	return (0);
}

/*
 * add_contents_space()
 *	For upgrade when we are deriving extra files on the system we must
 *	adjust for the space used by the contents file. By multiplying by
 *	two we grossly approximate for other install related files
 *	in /var/sadm/ not listed in the contents file.
 * Parameters:
 *	prod	-
 *	mult	- this is the multiplier
 * Return:
 *	none
 * Status:
 *	private
 */
static void
add_contents_space(Product * prod, float mult)
{
	char		contname[MAXPATHLEN];
	long		sz;
	struct stat	st;

	if (slasha) {
		if (!do_chroot(slasha))
			return;
	}

	if (pkgdb_supported()) {
		sz = genericdb_db_size(prod->p_rootdir);
		if (sz > 0) {
			add_file(contname, (int)((float)sz * mult), 1, 0,
			    (FSspace **)NULL);
		}
	} else {
		set_path(contname, prod->p_rootdir, NULL,
		    "var/sadm/install/contents");

		if (stat(contname, &st) < 0) {
			int dummy = 0; dummy += 1; /* Make lint shut up */
#ifdef DEBUG
			(void) fprintf(ef, "DEBUG: add_contents_space():\n");
			(void) fprintf(ef, "stat failed for file %s\n",
			    contname);
			perror("stat");
#endif
		} else {
			add_file(contname, (int)((float)st.st_size * mult),
			    1, 0, (FSspace **)NULL);
		}
	}

	if (slasha)
		(void) do_chroot("/");
}

/*
 * walk_upg_final_chk_pkgdir() - compute the space for the
 *	/var/sadm/pkg/<pkginst> directories (existing).
 *
 *	Note: this function has two modes.  If ProgressInCountMode()
 *		returns TRUE, just count the package directories.
 * Parameters:
 *	np	  -
 *	rootdir_p -
 * Return:
 *	0
 * Status:
 *	private
 *
 */
static int
walk_upg_final_chk_pkgdir(Node *np, caddr_t rootdir_p)
{
	Modinfo	*orig_mod, *i, *j;

	orig_mod = (void *) np->data;
	for (i = orig_mod; i != (Modinfo *) NULL; i = next_inst(i)) {
		if (i->m_shared == NOTDUPLICATE) {
			if (!(i->m_flags & IS_UNBUNDLED_PKG)) {
				for (j = i; j != (Modinfo *) NULL;
				    j = next_patch(j)) {
					if (ProgressInCountMode())
						ProgressCountActions(
						    PROG_DIR_DU, 1);
					else {
						compute_pkg_ovhd(j, rootdir_p);
						add_pkg_ovhd(j, rootdir_p);
						ProgressAdvance(PROG_DIR_DU, 1,
						    VAL_CURPKG_SPACE,
						    j->m_pkginst ?
						    j->m_pkginst : j->m_pkgid);
					}
				}
			}
		}
	}
	return (0);
}

/*
 * compute_pkg_ovhd()
 * Parameters:
 *	mi	-
 *	rootdir -
 * Return:
 *	none
 * Status:
 *	private
 * Globals modified:
 *	sets mi->m_pkgovhd_size
 */
static void
compute_pkg_ovhd(Modinfo *mi, char *rootdir)
{
	int	blks = 0;
	char	buf[BUFSIZ], command[MAXPATHLEN + 20];
	char	path[MAXPATHLEN];
	FILE	*pp;
	char    target_rootdir[MAXPATHLEN];

	/*
	 * If the target root file system is mounted on a
	 * temporary mount point (slasha), check to make
	 * sure it's accessible, and that the mount point
	 * is a well-formed directory path (i.e. starts
	 * with a '/' and does not end in a '/'.)
	 * The set_path() procedure called below requires
	 * every path in the three paths that it concatenates
	 * to be well-formed.
	 *
	 * After checking slasha, chroot back to the miniroot
	 * so that the popen() call and the du command executed
	 * below run in the miniroot environment.  That prevents
	 * errors caused by differences between the target root
	 * environment and the miniroot environment, e.g. absence
	 * of locales in the target root environment that can
	 * cause shells to complain when they start up (see bugid
	 * 4012486.)
	 *
	 * Finally, prepend slasha to rootdir, so the du command
	 * will run on a directory in the target root file system
	 * rather than the miniroot file system.
	 *
	 */
	if (slasha) {
		if (!do_chroot(slasha)) {
			return;
		} else {
			(void) do_chroot("/");
		}
		if (snprintf(target_rootdir, sizeof (target_rootdir),
			"%s%s", slasha, rootdir) >= sizeof (target_rootdir))
			return;
	} else {
		if (strlcpy(target_rootdir, rootdir, sizeof (target_rootdir))
				>= sizeof (target_rootdir))
			return;
	}

	set_path(path, target_rootdir, "/var/sadm/pkg", mi->m_pkginst ?
	    mi->m_pkginst : mi->m_pkgid);

	(void) snprintf(command, sizeof (command), "/usr/bin/du -sk %s", path);
	if ((pp = popen(command, "r")) == NULL) {
		return;
	}
	while (!feof(pp)) {
		if (fgets(buf, BUFSIZ, pp) != NULL) {
			buf[strlen(buf) - 1] = '\0';
			(void) sscanf(buf, "%d %*s", &blks);
		}
	}
	(void) pclose(pp);

	mi->m_pkgovhd_size = blks;
}

/*
 * add_pkg_ovhd()
 * Parameters:
 *	mi	-
 *	rootdir -
 * Return:
 *	none
 * Status:
 *	private
 */
static void
add_pkg_ovhd(Modinfo *mi, char *rootdir)
{
	char	path[MAXPATHLEN];

	if (slasha) {
		if (!do_chroot(slasha))
			return;
	}

	set_path(path, rootdir, "/var/sadm/pkg", mi->m_pkginst ?
	    mi->m_pkginst : mi->m_pkgid);

	/*
	 * Estimate 7 inodes.
	 */
	if (mi->m_pkgovhd_size != 0)
		add_file_blks(path, mi->m_pkgovhd_size, (ulong) 7,
		    SP_DIRECTORY, (FSspace **)NULL);

	if (slasha)
		(void) do_chroot("/");
}

/*
 * compute_patchdir_space() - compute the space used by
 *	/var/sadm/patch/<pkginst> directories.  If ProgressInCountMode()
 *	returns TRUE, just count the directories to be du'd.
 * Parameters:
 *	prod
 * Return:
 *	none
 * Status:
 *	private
 */
static void
compute_patchdir_space(Product *prod)
{
	struct patch *p;
	int	blks = 0;
	char	buf[BUFSIZ], command[MAXPATHLEN + 20];
	char	path[MAXPATHLEN];
	FILE	*pp;
	char    target_rootdir[MAXPATHLEN];

	/*
	 * If the target root file system is mounted on a
	 * temporary mount point (slasha), check to make
	 * sure it's accessible, and that the mount point
	 * is a well-formed directory path (i.e. starts
	 * with a '/' and does not end in a '/'.)
	 * The set_path() procedure called below requires
	 * every path in the three paths that it concatenates
	 * to be well-formed.
	 *
	 * After checking slasha, chroot back to the miniroot
	 * so that the popen() calls and du commands executed
	 * below run in the miniroot environment.  That prevents
	 * errors caused by differences between the target root
	 * environment and the miniroot environment, e.g. absence
	 * of locales in the target root environment that can
	 * cause shells to complain when they start up (see bugid
	 * 4012486.)
	 *
	 * Finally, prepend slasha to prod->p_rootdir before
	 * executing each popen call, so the du command
	 * will run on the prod->p_rootdir directory in the
	 * target root file system instead of on the
	 * prod->p_rootdir directory in the miniroot file system.
	 *
	 */
	if (slasha) {
		if (!do_chroot(slasha)) {
			return;
		} else {
			(void) do_chroot("/");
		}
	}

	for (p = prod->p_patches; p != NULL; p = p->next) {
		/* only count space for patches being removed */
		if (!p->removed)
			continue;
		if (ProgressInCountMode()) {
			ProgressCountActions(PROG_DIR_DU, 1);
			continue;
		}

		if (slasha) {
			if (snprintf(target_rootdir, sizeof (target_rootdir),
				"%s%s", slasha, prod->p_rootdir)
				>= sizeof (target_rootdir)) {
				return;
			}
		} else {
			if (strlcpy(target_rootdir, prod->p_rootdir,
				sizeof (target_rootdir))
				>= sizeof (target_rootdir)) {
				return;
			}
		}

		set_path(path, target_rootdir, "/var/sadm/patch",
		    p->patchid);

		(void) snprintf(command, sizeof (command),
		    "/usr/bin/du -sk %s", path);
		if ((pp = popen(command, "r")) == NULL) {
			return;
		}
		while (!feof(pp)) {
			if (fgets(buf, BUFSIZ, pp) != NULL) {
				buf[strlen(buf) - 1] = '\0';
				(void) sscanf(buf, "%d %*s", &blks);
			}
		}
		(void) pclose(pp);

		/*
		 * Estimate 7 inodes.
		 */
		if (blks != 0)
			add_file_blks(path, (ulong) blks, (ulong) 7,
			    SP_DIRECTORY, (FSspace **)NULL);

		ProgressAdvance(PROG_DIR_DU, 1, VAL_CURPATCH_SPACE,
			p->patchid);
	}
}

FILE *
open_debug_print_file()
{
	char		*log_file = "/tmp/space.log";

	if (locdbgfp != NULL)
		return (locdbgfp);
	if (get_trace_level() > 0 && log_file != NULL) {
		locdbgfp = fopen(log_file, "w");
		if (locdbgfp != NULL)
			(void) chmod(log_file, S_IRUSR | S_IWUSR |
			    S_IRGRP | S_IROTH);
	}
	return (locdbgfp);
}

static void
close_debug_print_file(FILE *fp)
{
	if (fp != NULL) {
		(void) fclose(fp);
		fp = NULL;
		locdbgfp = NULL;
	}
}

void
print_space_usage(FILE *fp, char *message, FSspace **sp)
{
	int	i;
	ulong totblks = 0;   /* Total blocks used */
	ulong totinodes = 0; /* Total inodes used */

	if (sp == (FSspace **)NULL || fp == NULL)
		return;

	(void) fprintf(fp, "\nSpace consumed at: %s\n", message);

	(void) fprintf(fp, "%20s:  Blks Used \tInodes Used\n",
	    "Mount Point");

	/*
	 * For every file system print out the necessary information
	 */
	for (i = 0; sp[i]; i++) {
		if (sp[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;
		(void) fprintf(fp, "%20s:  %10ld\t%10ld\n", sp[i]->fsp_mntpnt,
		    sp[i]->fsp_reqd_contents_space,
		    sp[i]->fsp_cts.contents_inodes_used);
		totblks += sp[i]->fsp_reqd_contents_space;
		totinodes += sp[i]->fsp_cts.contents_inodes_used;
	}

	(void) fprintf(fp, "\n%20s:  %10ld\t%10ld\n", "TOTAL",
	    totblks, totinodes);
}

/*
 * sp_add_patch_space()
 *
 * Parameters:
 *	prod - product where patches will be applied.
 * Return:
 *	SUCCESS
 */
static int
sp_add_patch_space(Product *prod, int component_types)
{
	char		fullpath[MAXPATHLEN + 1];
	struct patch_space_reqd	*psr;
	struct patdir_entry	*pde;

	if (upg_state & SP_UPG) {
		if (slasha) {
			if (!do_chroot(slasha))
				return (SP_ERR_CHROOT);
		}
	}
	for (psr = patch_space_head; psr != NULL; psr = psr->next) {

		if (!arch_is_selected(prod, psr->patsp_arch))
			continue;

		for (pde = psr->patsp_direntry; pde != NULL; pde = pde->next) {

			if (pde->patdir_spooled) {
				if ((component_types & SPOOLED_COMPONENT) &&
				    pkg_match(pde, prod) &&
				    prod->p_name != NULL &&
				    prod->p_version != NULL) {
					(void) snprintf(fullpath,
					    MAXPATHLEN + 1,
					    "/export/root/templates/%s_%s",
					    prod->p_name, prod->p_version);
					add_file(fullpath,
					    pde->patdir_kbytes * 1024,
					    pde->patdir_inodes, SP_DIRECTORY,
					    (FSspace **)NULL);
				}
				continue;
			}

			set_path(fullpath, prod->p_rootdir, NULL,
			    pde->patdir_dir);

			if (strncmp(pde->patdir_dir, "/usr/", 5) == 0 ||
			    strcmp(pde->patdir_dir, "/usr") == 0) {
				if (supports_arch(get_default_arch(),
				    psr->patsp_arch))
					if ((component_types &
					    NATIVE_USR_COMPONENT) &&
					    pkg_match(pde, prod))
						add_file(fullpath,
						    pde->patdir_kbytes * 1024,
						    pde->patdir_inodes,
						    SP_DIRECTORY,
						    (FSspace **)NULL);
				else
					if ((component_types &
					    NONNATIVE_USR_COMPONENT) &&
					    pkg_match(pde, prod))
						add_file(fullpath,
						    pde->patdir_kbytes * 1024,
						    pde->patdir_inodes,
						    SP_DIRECTORY,
						    (FSspace **)NULL);
				continue;
			}

			if (strncmp(pde->patdir_dir, "/opt/", 5) == 0 ||
			    strcmp(pde->patdir_dir, "/opt") == 0) {
				if ((component_types & OPT_COMPONENT) &&
				    pkg_match(pde, prod))
					add_file(fullpath,
					    pde->patdir_kbytes * 1024,
					    pde->patdir_inodes, SP_DIRECTORY,
					    (FSspace **)NULL);
				continue;
			}

			if ((component_types & ROOT_COMPONENT) &&
			    pkg_match(pde, prod))
				add_file(fullpath, pde->patdir_kbytes * 1024,
				    pde->patdir_inodes, SP_DIRECTORY,
				    (FSspace **)NULL);
		}
	}

	if (upg_state & SP_UPG) {
		if (slasha) {
			if (!do_chroot("/"))
				return (SP_ERR_CHROOT);
		}
	}

	return (SUCCESS);
}

/*
 * sp_add_products_space()
 *
 * Parameters:
 *	prod - product where CD products will be added to.
 * Return:
 *	SUCCESS
 */
static int
sp_add_products_space(Product *prod, char *p_rootdir)
{
	Module *mod = NULL;

	if (prod == NULL)
		return (FAILURE);

	/* if p_cd_info is NULL, then there are no product CDs */
	if ((mod = prod->p_cd_info) == NULL)
		return (SUCCESS);

	/* for each product CD, add the product into space total */
	for (; mod; mod = mod->next)
		add_product(mod->info.cdinf, NULL, p_rootdir);

	return (SUCCESS);
}



static int
pkg_match(struct patdir_entry *pde, Product *prod)
{
	Node	*node;

	if (pde->patdir_pkgid) {
		node = findnode(prod->p_packages, pde->patdir_pkgid);
		if (node && node->data &&
		    (((Modinfo *)(node->data))->m_status == SELECTED ||
		    ((Modinfo *)(node->data))->m_status == REQUIRED))
			return (1);
		else
			return (0);
	}
	return (1);
}

void
swi_free_fsspace(FSspace *fsp)
{
	(void) free(fsp->fsp_mntpnt);
	StringListFree(fsp->fsp_pkg_databases);
	(void) free(fsp);
}

/* ******************************************************************** */
/*			INTERNAL SUPPORT FUNCTIONS			*/
/* ******************************************************************** */

static int
upg_calc_sw_fs_usage(FSspace **fs_list, int (*callback_proc)(void *, void *),
	void *callback_arg)
{
	Module  *mod, *newmedia;
	Product *prod1;
	int 	ret = SUCCESS;
	static	FSspace  **upg_istab = NULL;
	List	*l;
	Node	*n;
	int	i;

	/*
	 * Grab newmedia pointer and service shared with server info.
	 */
	if ((newmedia = get_newmedia()) == NULL)
		return (ERR_NOMEDIA);
	upg_state |= SP_UPG;

	/*
	 *  If this is the first pass through the code, use the
	 *  callback functions to record progress.  Subsequent
	 *  calls should make use of the data calculated in the
	 *  first pass and so should be fast enough to not require
	 *  progress metering.
	 *
	 *  Count total space checking actions to be performed.
	 */
	if (first_pass && callback_proc != NULL) {
		ProgressBeginActionCount();

		/* count the number of lines to be processed by find_modified */
		if (!doing_add_service)
			ProgressCountActions(PROG_FIND_MODIFIED,
			    total_contents_lines());

		for (mod = get_media_head(); mod != NULL; mod = mod->next) {
			if ((mod->info.media->med_type != INSTALLED) &&
				(mod->info.media->med_type != INSTALLED_SVC))
				continue;
			if (service_going_away(mod))
				continue;

			if (!(mod->info.media->med_flags & BASIS_OF_UPGRADE) &&
			    svc_unchanged(mod->info.media))
				continue;

			if (has_view(newmedia->sub, mod) != SUCCESS)
				continue;

			/* call calc_extra_contents in action-counting mode */
			(void) calc_extra_contents(mod, NULL);

			prod1 = mod->sub->info.prod;

			(void) load_view(newmedia->sub, mod);
			Pkgs_dir = newmedia->sub->info.prod->p_pkgdir;

			load_inherited_FSs(prod1);

			l = newmedia->sub->info.prod->p_packages;
			for (n = l->list->next; n != NULL && n != l->list;
			    n = n->next) {
				(void) walk_upg_final_chk(n, prod1);
			}
		}
		/* Set the view back to global root if it isn't already */
		if (get_current_view(newmedia->sub) != get_localmedia())
			load_local_view(newmedia->sub);

		/* stop counting actions and start progress bar */
		ProgressBeginMetering(callback_proc, callback_arg);
	}

	/*
	 * Perform analysis on Solaris space requirements
	 */
	dfp = open_debug_print_file(); /* re-open space.log in zone */

	/* initialize for extra space calculation */
	if (upg_istab == NULL)
		upg_istab = get_current_fs_layout();
	if (upg_istab == NULL)
		return (NULL);
	if (first_pass)
		begin_global_space_sum(upg_istab);

	/* initialize the final space table */
	reset_stab(fs_list);
	begin_global_space_sum(fs_list);

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if ((mod->info.media->med_type != INSTALLED) &&
		    (mod->info.media->med_type != INSTALLED_SVC))
			continue;
		if (service_going_away(mod))
			continue;
		if (!(mod->info.media->med_flags & BASIS_OF_UPGRADE) &&
		    svc_unchanged(mod->info.media))
			continue;
		load_view(newmedia->sub, mod);
		if (mod->info.media->med_type != INSTALLED ||
		    mod->info.media->med_zonename == NULL &&
		    streq(mod->info.media->med_dir, "/")) {
			ret = upg_calc_mod(mod, "/", fs_list, upg_istab);
		} else {
			/* non-global zone -handle in zone-safe manner */
			ret = upg_calc_zone(mod, fs_list, upg_istab);
		}
		if (ret != SUCCESS) {
			upg_state &= ~SP_UPG;
			return (ret);
		}
	}
	/* Set the view back to global root if it isn't already */
	if (get_current_view(newmedia->sub) != get_localmedia())
		load_local_view(newmedia->sub);

	/* extra contents */
	if (upg_xstab == NULL)
		upg_xstab = get_current_fs_layout();
	else
		reset_stab(upg_xstab);
	if (upg_xstab == NULL)
		return (FAILURE);

	for (i = 0; upg_istab[i]; i++) {
		ulong	bused, bdiff, fused, fdiff;

		if (upg_istab[i]->fsp_flags & FS_IGNORE_ENTRY)
			continue;
		bused = upg_istab[i]->fsp_fsi->f_blocks -
					upg_istab[i]->fsp_fsi->f_bfree;
		fused = upg_istab[i]->fsp_fsi->f_files -
					upg_istab[i]->fsp_fsi->f_ffree;

		if (bused > upg_istab[i]->fsp_reqd_contents_space)
			bdiff = bused - upg_istab[i]->fsp_reqd_contents_space;
		else
			bdiff = 0;
		if (fused > upg_istab[i]->fsp_cts.contents_inodes_used)
			fdiff = fused -
			    upg_istab[i]->fsp_cts.contents_inodes_used;
		else
			fdiff = 0;

		fsp_set_field(upg_xstab[i], FSP_CONTENTS_NONPKG, bdiff);
		upg_xstab[i]->fsp_cts.contents_inodes_used = fdiff;
	}

	set_global_space(fs_list);
	add_spacetab(upg_xstab, NULL, NULL);

	do_add_savedfile_space(newmedia->sub);
	if (get_trace_level() > 0)
		print_space_usage(dfp, "After adding in save files",
		    fs_list);

	(void) end_global_space_sum();

	if (get_trace_level() > 0) {
		(void) fprintf(dfp, "\nSpace available:\n");
		(void) fprintf(dfp, "%20s:    Blocks  \t  Inodes\n",
		    "Mount Point");
	}

	if (first_pass)
		ProgressEndMetering();

	first_pass = B_FALSE;
	upg_state &= ~SP_UPG;

	close_debug_print_file(dfp);
	return (SUCCESS);
}

/*
 * upg_calc_mod()
 *	Zone-safe routine to calculate file space requirements for Solaris
 *	for non-global zone, that zone should be entered before calling
 *
 * Parameters:
 *	mod - module for zone or service
 *	fs_list - to contain file system space required
 *	istab - to contain file system space for extra contents
 * Return:
 *	SUCCESS/FAILURE
 */
static int
upg_calc_mod(Module *mod, char *p_rootdir, FSspace **fs_list,
    FSspace **istab)
{
	Product *prod1;
	List 	*l;
	Node	*n;
	Module	*prodmod, *newmedia, *tmod;
	int	ret = SUCCESS;
	Module	*split_from_servermod = NULL;

	/*
	 * if non-global zone, we build the space table from scratch,
	 * then pipe it back to be added to the global space table
	 */

	/*
	 * Grab newmedia pointer and service shared with server info.
	 */
	for (tmod = get_media_head(); tmod != NULL; tmod = tmod->next) {
		if ((tmod->info.media->med_type != INSTALLED) &&
		    (tmod->info.media->med_type != INSTALLED_SVC)) {
			newmedia = tmod;
		}
		if ((tmod->info.media->med_type == INSTALLED_SVC) &&
		    (tmod->info.media->med_flags & SPLIT_FROM_SERVER)) {
			split_from_servermod = tmod;
		}
	}

	prodmod = newmedia->sub;

	/*
	 * in zone, we count fs usage from zero
	 * and pipe back fs table to be added to global fs table
	 */
	if (is_child_zone_context)
		reset_stab(fs_list);

	if (mod->info.media->med_flags & BASIS_OF_UPGRADE &&
	    !(mod->info.media->med_flags & MODIFIED_FILES_FOUND) &&
		/*
		 * don't scan for modified files if this
		 * service is actually the server's own
		 * service.  It's already been scanned.
		 */
	    !(mod->info.media->med_type == INSTALLED_SVC &&
	    mod->info.media->med_flags & SPLIT_FROM_SERVER) &&
	    (mod->info.media->med_type == INSTALLED ||
	    mod->info.media->med_type == INSTALLED_SVC)) {
		(void) load_view(prodmod, mod);
		find_modified(mod);
		mod->info.media->med_flags |= MODIFIED_FILES_FOUND;
	}

	if (get_current_view(prodmod) != get_localmedia())
		load_local_view(prodmod);

	/* do once only for each zone */
	if (first_pass &&
	    (mod->info.media->med_type != INSTALLED ||
	    mod->info.media->med_type != INSTALLED_SVC) &&
	    !(mod->info.media->med_flags & NEW_SERVICE) &&
	    !service_going_away(mod) &&
		/*
		 *  If the media isn't the basis of an upgrade and
		 *  isn't being modified, or is an unchanged service,
		 *  skip it.
		 */
	    ((mod->info.media->med_flags & BASIS_OF_UPGRADE) ||
	    !svc_unchanged(mod->info.media))) {

		if (is_child_zone_context) { /* start sum for zone */
			reset_stab(istab);
			begin_global_space_sum(istab);
		} else
			set_global_space(istab); /* change global fs table */

		istab = calc_extra_contents(mod, istab);

		if (istab == NULL) {
			if (first_pass)
				ProgressEndMetering();
			return (FAILURE);
		}
		if (is_child_zone_context) /* end sum of zone xtra contents */
			end_global_space_sum();
	}

	/* set global table back to caller's global table */
	if (is_child_zone_context)
		begin_global_space_sum(fs_list); /* start non-global zone sum */
	else
		set_global_space(fs_list); /* resume global zone sum */


	prod1 = mod->sub->info.prod;

	if (mod != split_from_servermod)
		add_contents_space(prod1, 2.5);

	(void) walklist(prod1->p_packages, walk_upg_preserved_pkgs,
	    prod1->p_rootdir);

	if (get_trace_level() > 0)
		print_space_usage(dfp, "After loading preserved packages",
		    fs_list);

	if (has_view(newmedia->sub, mod) != SUCCESS)
		return (SUCCESS);

	/*
	 * Count new pkgs (both pkgadded and spooled) and services.
	 */
	Tmp_fstab = get_current_fs_layout();
	(void) load_view(newmedia->sub, mod);
	Pkgs_dir = newmedia->sub->info.prod->p_pkgdir;
	/*
	 *  The following values are passed globally to
	 *  walk_upg_final_chk:
	 *
	 *  Pkgs_dir : the directory containing the new packages.
	 *  Tmp_fstab : the fstab used for temporary per-package
	 * 	space calculations (as necessary).
	 */

	load_inherited_FSs(prod1);

	l = newmedia->sub->info.prod->p_packages;
	for (n = l->list->next; n != NULL && n != l->list;
	    n = n->next) {
		(void) walk_upg_final_chk(n, prod1);
	}
	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "After walking new packages (both spooled and "
		    "pkgadded)", fs_list);

	if (ret != SUCCESS) {
		if (first_pass)
			ProgressEndMetering();
		close_debug_print_file(dfp);
		return (ret);
	}

	/*
	 * Count space for patches to be installed after upgrade
	 * is complete (this might be driver-update patches or
	 * general-purpose patches).
	 */

	if (mod->info.media->med_type == INSTALLED_SVC) {
		if (mod->info.media->med_flags & SPLIT_FROM_SERVER)
			ret = sp_add_patch_space(
			    newmedia->sub->info.prod,
			    SPOOLED_COMPONENT |
			    NONNATIVE_USR_COMPONENT);
		else
			ret = sp_add_patch_space(
			    newmedia->sub->info.prod,
			    SPOOLED_COMPONENT |
			    NONNATIVE_USR_COMPONENT |
			    NATIVE_USR_COMPONENT);
	} else {
		/* it's the global root, or a nonglobal zone */
		if (mod == get_localmedia() ||
		    mod->info.media->med_zonename != NULL)
			ret = sp_add_patch_space(
			    newmedia->sub->info.prod,
			    ROOT_COMPONENT |
			    NATIVE_USR_COMPONENT |
			    OPT_COMPONENT);
		else	/* it's a diskless client */
			ret = sp_add_patch_space(
			    newmedia->sub->info.prod,
			    ROOT_COMPONENT);
	}
	if (ret != SUCCESS) {
		if (first_pass)
			ProgressEndMetering();
		close_debug_print_file(dfp);
		return (ret);
	}

	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "After adding space for patches", fs_list);

	/* Set the view back to global root if it isn't already */
	if (get_current_view(newmedia->sub) != get_localmedia())
		load_local_view(newmedia->sub);

	/*
	 * Count space for additional products to be
	 * installed/upgraded.
	 *
	 * Even though the core OS software is being upgraded,
	 * the additional products that have been selected will
	 * be either:
	 *	a) initially installed if they are currently not
	 *	   installed the existing system.
	 *	b) upgraded if they are currently installed on
	 *	   the existing system.
	 *
	 * Unfortunately, we currently do not have any mechanism
	 * to determine whether additional products are already
	 * installed on the existing system, let alone a mechanism to
	 * determine the size of the installed products on the
	 * existing system.
	 *
	 * Therefore, we will aproximate size based on the worst
	 * case scenario.  That is, we will assume that the
	 * additional products selected will be initially installed
	 * during this upgrade.
	 */

	(void) sp_add_products_space(newmedia->sub->info.prod, p_rootdir);

	if (get_trace_level() > 0) {
		print_space_usage(dfp,
		    "After adding space for products", fs_list);
	}
	/*
	 * for child zone process, run tracked dirs and accumulate
	 * totals in global fs space for piping back upon returning
	 */
	if (is_child_zone_context) {
		end_global_space_sum();
	}
	return (SUCCESS);
}

/*
 * upg_calc_zone()
 *	Zone-safe routine to calculate file space requirements for Solaris
 *	for non-global zone only
 * Parameters:
 *	mod - module for zone or service
 *	fs_list - to contain file system space required
 *	istab - to contain file system space for extra contents
 * Return:
 *	SUCCESS/FAILURE
 * Side effects:
 *	zone is entered after forking
 *	child pipes non-global zone information to parent
 *	parent files non-global zone information
 * Globals modified:
 *	is_child_zone_context - identifies child zone processing
 *	misc. data filed in parent sent from child (see read_from_pipe routines)
 */
static int
upg_calc_zone(Module *mod, FSspace **fs_list, FSspace **istab)
{
	zoneList_t		zlst;
	int			k;
	char			*zoneName;

	int			child_pid;
	int			child_status;
	pid_t			retval;
	zoneid_t		zoneid;

	int			tmpl_fd;
	int			err = 0;
	FILE			*zfd;
	int			zpipe[2] = {0, 0};
	char			*p_rootdir;

	if (!z_zones_are_implemented())
		return (SUCCESS);

	zlst = z_get_nonglobal_zone_list();
	if (zlst == (zoneList_t)NULL) {
		return (SUCCESS);
	}

	/* Set up contract template for child */
	tmpl_fd = open64(CTFS_ROOT "/process/template", O_RDWR);
	if (tmpl_fd == -1) {
		return (FAILURE);
	}

	/*
	 * Child process doesn't do anything with the contract.
	 * Deliver no events, don't inherit, and allow it to
	 * be orphaned.
	 */
	err |= ct_tmpl_set_critical(tmpl_fd, 0);
	err |= ct_tmpl_set_informative(tmpl_fd, 0);
	err |= ct_pr_tmpl_set_fatal(tmpl_fd, CT_PR_EV_HWERR);
	err |= ct_pr_tmpl_set_param(tmpl_fd, CT_PR_PGRPONLY | CT_PR_REGENT);
	if (err || ct_tmpl_activate(tmpl_fd)) {
		(void) close(tmpl_fd);
		return (FAILURE);
	}

	for (k = 0; (zoneName = z_zlist_get_zonename(zlst, k)) != (char *)NULL;
	    k++) {

		if (!streq(zoneName, mod->info.media->med_zonename))
			continue;

		/*
		 * Open a pipe so that the child process can send its
		 * output back to us.
		 */
		if (pipe(zpipe) != 0) {
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Could not create pipe to process zone: %s"),
			    zoneName);
			return (FAILURE);
		}

		/*
		 * fork off a child to do space calculation
		 * for a non-global zone.
		 */
		if ((child_pid = fork()) == -1) {
			(void) ct_tmpl_clear(tmpl_fd);
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Could not fork to process zone: %s"), zoneName);
			return (FAILURE);
		} else if (child_pid == 0) { /* child process */
			(void) ct_tmpl_clear(tmpl_fd);
			(void) close(tmpl_fd);

			/* get zone's zoneid */
			zoneid = getzoneidbyname(z_zlist_get_scratch(zlst, k));

			/*
			 * Close read side of pipe, and turn
			 * write side into a stream.
			 */
			(void) close(zpipe[0]);
			zfd = fdopen(zpipe[1], "w");
			if (zfd == NULL) {
				write_message(LOGSCR, WARNMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Could not open pipe to process zone: "
				    "%s"), zoneName);
				_exit(1);
			}
			setbuf(zfd, NULL);

			/*
			 * In case any of stdin, stdout or stderr
			 * are streams, anchor them to prevent
			 * malicious I_POPs.
			 */
			(void) ioctl(STDIN_FILENO, I_ANCHOR);
			(void) ioctl(STDOUT_FILENO, I_ANCHOR);
			(void) ioctl(STDERR_FILENO, I_ANCHOR);

			if (dfp != NULL) {
				close_debug_print_file(dfp);
				dfp = NULL;
			}
			if (zone_enter(zoneid) == -1) {
				(void) ct_tmpl_clear(tmpl_fd);

				write_message(LOGSCR, WARNMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Failed to zone_enter zone: %s"), zoneName);
				_exit(1);
			}

			/*
			 * We're running in the non-global zone
			 */
			is_child_zone_context = B_TRUE;

			p_rootdir = mod->info.media->med_dir;

			/* make zone root-relative */
			mod->info.media->med_dir = "/";
			mod->sub->info.prod->p_rootdir = "/";
			mod->sub->info.prod->p_pkgdir = "/var/sadm/pkg";
			/* re-open space.log in zone */
			dfp = open_debug_print_file();

			/*
			 * calculate free space usage and perform file
			 * system analysis for a zone - here from the
			 * context of a non-global zone
			 */
			retval = upg_calc_mod(mod, p_rootdir, fs_list,
			    istab);

			close_debug_print_file(dfp);
			dfp = NULL;

			if (retval == SUCCESS) {
				/*
				 * Send the data back to the global zone
				 * data includes:
				 * - modified file list
				 * - FSspace
				 * - contents records
				 * - extra contents
				 */
				if (write_zone_fs_analysis_to_pipe(zfd, mod,
				    istab, fs_list, first_pass) != 0) {
					write_message(LOGSCR, WARNMSG, LEVEL0,
					    dgettext("SUNW_INSTALL_SWLIB",
					    "Failure writing nonglobal zone "
					    "fs analysis: %s"), zoneName);
					(void) fclose(zfd);
					_exit(1);
				}
				/* end of data to transmit */
				(void) fclose(zfd);
				write_debug(LOGSCR, (get_trace_level() > 0),
				    "LIBSPMISOFT", DEBUG_LOC, LEVEL1,
				    "Finished file system analysis in zone %s",
				    zoneName);
				_exit(0); /* successful end of child zone */
			} else {
				write_message(LOGSCR, WARNMSG, LEVEL0,
				    dgettext("SUNW_INSTALL_SWLIB",
				    "Failure calculating nonglobal zone "
				    "free space: %s"), zoneName);
				(void) fclose(zfd);
				_exit(1);
			}
		}
		/* parent process */

		/* Close write side of pipe, and turn read side into stream. */
		(void) close(zpipe[1]);
		zfd = fdopen(zpipe[0], "r");
		setbuf(zfd, NULL);

		if (get_trace_level() > 0)
			print_space_usage(dfp,
			    "Before adding in non-global zone files", fs_list);

		/*  process output piped from child process */
		if (read_zone_fs_analysis_from_pipe(zfd, mod, istab, fs_list,
		    dfp) != 0) {
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Failure reading non-global zone fs analysis: %s"),
			    zoneName);
			return (FAILURE);
		}

		if (get_trace_level() > 0)
			print_space_usage(dfp,
			    "After adding in non-global zone files", fs_list);

		(void) fclose(zfd); /* close pipe */

		/* wait for child to exit */
		do {
			retval = waitpid(child_pid, &child_status, 0);
			if (retval == -1) {
				child_status = 0;
			}
		} while (retval != child_pid);

		if (WEXITSTATUS(child_status) != 0) {
			write_message(LOGSCR, ERRMSG, LEVEL0,
			    dgettext("SUNW_INSTALL_SWLIB",
			    "Failure calculating nonglobal zone "
			    "free space: %s"), zoneName);
			return (FAILURE);
		}
	}

	return (SUCCESS);
}

/*ARGSUSED1*/
static int
inin_calc_sw_fs_usage(FSspace **fs_list, int (*callback_proc)(void *, void *),
    void *callback_arg)
{
	Module	*mod, *prodmod;
	Product	*prod;
	Module  *cur_view;

	if (!is_flash_install()) {
	    if ((mod = get_media_head()) == (Module *)NULL)
		return (NULL);
	}

	dfp = open_debug_print_file();

	if (!is_flash_install()) {
		prodmod = mod->sub;
		prod = prodmod->info.prod;
		Pkgs_dir = prod->p_pkgdir;
	}

	/* set up the space table */
	sort_spacetab(fs_list);
	reset_stab(fs_list);

	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "inin_calc_sw_fs_usage: Before doing anything", fs_list);

	/* calculate space requirements of the tree */
	begin_global_qspace_sum(fs_list);

	if (is_flash_install()) {
		add_file_blks("/",
		    (daddr_t)(archive_total_reqd_space()*MBYTE/KBYTE),
		    0, SP_MOUNTP, NULL);
		(void) end_global_space_sum();
		if (get_trace_level() > 0)
			print_space_usage(dfp,
			"inin_calc_sw_fs_usage: After flash space computing",
			    fs_list);

		close_debug_print_file(dfp);
		return (SUCCESS);
	}

	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "inin_calc_sw_fs_usage: After qspace_chk", fs_list);

	(void) walklist(prod->p_packages, walk_add_mi_space, prod->p_rootdir);
	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "inin_calc_sw_fs_usage: After walking packages", fs_list);
	(void) sp_add_patch_space(prod,
	    NATIVE_USR_COMPONENT | OPT_COMPONENT | ROOT_COMPONENT);

	if (get_trace_level() > 0)
		print_space_usage(dfp,
	    "inin_calc_sw_fs_usage: After adding patch space requirements",
		    fs_list);

	(void) sp_add_products_space(prod, NULL);
	if (get_trace_level() > 0)
		print_space_usage(dfp,
	    "inin_calc_sw_fs_usage: After adding products space requirements",
			fs_list);

	cur_view = get_current_view(prodmod);
	(void) load_default_view(prodmod);
	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (mod->info.media->med_type == INSTALLED_SVC) {
			if (service_going_away(mod))
				continue;
			if (has_view(prodmod, mod) != SUCCESS)
				continue;

			(void) load_view(prodmod, mod);
			(void) walklist(prod->p_packages, walk_add_mi_space,
				mod->sub->info.prod->p_rootdir);
			if (get_trace_level() > 0)
				print_space_usage(dfp,
		    "inin_calc_sw_fs_usage: After walking packages (2nd)",
				    fs_list);
			/*
			 *  Currently, initial-install only allocates space
			 *  for the shared service of the same ISA as the
			 *  server itself.  That's why we only add up
			 *  non-native /usr components here.  Native /usr
			 *  components would have already been accounted for.
			 */
			(void) sp_add_patch_space(mod->sub->info.prod,
			    NONNATIVE_USR_COMPONENT | SPOOLED_COMPONENT);
			if (get_trace_level() > 0)
				print_space_usage(dfp,
				    "inin_calc_sw_fs_usage: After adding patch "
				    "space requirements (2nd)",
				    fs_list);
		}
	}

	if (cur_view != get_current_view(prodmod)) {
		if (cur_view == NULL)
			(void) load_default_view(prodmod);
		else
			(void) load_view(prodmod, cur_view);
	}

	(void) end_global_space_sum();

	if (get_trace_level() > 0)
		print_space_usage(dfp,
		    "inin_calc_sw_fs_usage: After space computing", fs_list);

	close_debug_print_file(dfp);

	return (SUCCESS);
}

static void
do_add_savedfile_space(Module *prodmod)
{
	Module	*mod;

	if (slasha)
		do_chroot(slasha);

	for (mod = get_media_head(); mod != NULL; mod = mod->next) {
		if (!(mod->info.media->med_flags & BASIS_OF_UPGRADE))
			continue;
		/*
		 * don't scan for modified files if this
		 * service is actually the server's own
		 * service.  It's already been scanned.
		 */
		if (mod->info.media->med_type == INSTALLED_SVC &&
		    mod->info.media->med_flags & SPLIT_FROM_SERVER)
			continue;

		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC) {
			(void) load_view(prodmod, mod);
			(void) walklist(mod->sub->info.prod->p_packages,
			    count_file_space, (caddr_t)(mod->sub->info.prod));
		}
	}

	/* Set the view back to global root if it isn't already */
	if (get_current_view(prodmod) != get_localmedia())
		load_local_view(prodmod);

	if (slasha)
		do_chroot("/");
}

static int
count_file_space(Node *node, caddr_t arg)
{
	Modinfo	*mi;
	Product	*prod;

	mi = (Modinfo *)(node->data);
	/*LINTED [alignment ok]*/
	prod = (Product *)arg;
	_count_file_space(mi, prod);
	while ((mi = next_inst(mi)) != NULL)
		_count_file_space(mi, prod);
	return (0);
}

static void
_count_file_space(Modinfo *mi, Product *prod)
{
	struct filediff *fdp;
	char	file[MAXPATHLEN];

	fdp = mi->m_filediff;
	while (fdp != NULL) {
		/*
		 * A file needs to be saved if its contents has changed
		 * and at least one of these two conditions is satisfied:
		 *  1)	the replacing package is selected or required and
		 *	TO_BE_PKGADDED
		 *  2)	if the action is not TO_BE_PRESERVED and
		 *	if the contents of the package are not going away
		 */
		if ((fdp->diff_flags & DIFF_CONTENTS) &&

		/* 1st condition */
		    ((fdp->replacing_pkg != NULL &&
		    (fdp->replacing_pkg->m_status == SELECTED ||
		    fdp->replacing_pkg->m_status == REQUIRED) &&
		    fdp->replacing_pkg->m_action == TO_BE_PKGADDED) ||

		/* 2nd condition */
		    (mi->m_action != TO_BE_PRESERVED &&
			!(mi->m_flags & CONTENTS_GOING_AWAY)))) {

			if (strlcpy(file, prod->p_rootdir, sizeof (file))
						>= sizeof (file))
				goto skip;
			if (strlcat(file, fdp->component_path, sizeof (file))
						>= sizeof (file))
				goto skip;
			(void) record_save_file(file, (FSspace **)NULL);
		}
skip:		fdp = fdp->diff_next;
	}
}

/*
 * calc_extra_contents()
 *	Calculate the amount of space in each file system that
 *	is not accounted for any by any package or patch.
 *
 *	This function has two modes, controlled by the value
 *	returned by ProgressInCountMode().  When in progress-counting
 *	mode, this function does nothing but count the number of actions
 *	to be performed by the validation phase.  This is to provide a
 *	total number of actions so that a percent-complete number can
 *	be computed for the validation (for the progress-display callbacks).
 *
 * Parameters:
 *	mod:	global, non-global zone, ...
 *	upg_istab:	space table for accumulating extra contents
 * Return:
 *	upg_istab if successful
 *	NULL if failure
 * Status:
 *	public
 */
static FSspace **
calc_extra_contents(Module *mod, FSspace **upg_istab)
{
	Module  *tmod;
	Module	*split_from_servermod = NULL;
	Product *prod1, *prod2;

	/*
	 * only compute extra contents once
	 */
	if (!first_pass || !is_child_zone_context && upg_xstab != NULL)
		return (upg_xstab);
	/*
	 * for non-global zones, clear the table and add in
	 * later
	 */
	if (is_child_zone_context && upg_xstab != NULL)
		reset_stab(upg_xstab);

	/* Grab service shared with server info. */
	for (tmod = get_media_head(); tmod != NULL; tmod = tmod->next) {
		if ((tmod->info.media->med_type == INSTALLED_SVC) &&
		    (tmod->info.media->med_flags & SPLIT_FROM_SERVER)) {
			split_from_servermod = tmod;
		}
	}
	/*
	 *  If the media isn't the basis of an upgrade and
	 *  isn't being modified, or is an unchanged service,
	 *  skip it.
	 */
	if ((mod->info.media->med_type == INSTALLED ||
	    mod->info.media->med_type == INSTALLED_SVC) &&
	    !(mod->info.media->med_flags & NEW_SERVICE) &&
	    !service_going_away(mod) &&
	    ((mod->info.media->med_flags & BASIS_OF_UPGRADE) ||
	    !svc_unchanged(mod->info.media))) {

		prod1 = mod->sub->info.prod;

		if (!ProgressInCountMode() && get_trace_level() > 0)
			print_space_usage(dfp,
			    "Before calculating extra contents",
			    upg_istab);
		/*
		 * Add space for /var/sadm/pkg/<pkg>'s we know about.
		 * walk_upg_final_chk_pkgdir will only count the packages
		 * if ProgressInCountMode().
		 */
		(void) walklist(prod1->p_packages,
		    walk_upg_final_chk_pkgdir,
		    prod1->p_rootdir);

		if (!ProgressInCountMode() && get_trace_level() > 0)
			print_space_usage(dfp,
			    "After adding in initial packages", upg_istab);
		/*
		 * Add space for /var/sadm/patch/<patchid> directories.
		 * compute_patchdir_space() will only count the patches
		 * if ProgressInCountMode();
		 */
		compute_patchdir_space(prod1);

		if (!ProgressInCountMode() && get_trace_level() > 0)
			print_space_usage(dfp, "After Adding in patches",
			    upg_istab);
		/*
		 * Pick up space for spooled packages.
		 * walk_upg_final_chk_isspooled() will only count the patches
		 * if ProgressInCountMode();
		 */
		if (mod == split_from_servermod) {
			(void) walklist(prod1->p_packages,
			    walk_upg_final_chk_isspooled, (caddr_t)0);
			return (SUCCESS);
		}
		if (!ProgressInCountMode() && get_trace_level() > 0)
		    print_space_usage(dfp,
			"After adding spooled packages", upg_istab);

		if (!ProgressInCountMode()) {
			/* If we share the server as a service.  */
			if ((is_servermod(mod)) && (split_from_servermod))
				prod2 = split_from_servermod->sub->info.prod;
			/*
			 * Otherwise, set it to NULL so that we don't
			 * have trouble in the sp_load_contents()
			 */
			else
				prod2 = NULL;

			(void) sp_load_contents(prod1, prod2);

			add_contents_space(prod1, 1);
		} else
			ProgressCountActions(PROG_CONTENTS_LINES,
			    contents_lines(mod));

		if (!ProgressInCountMode() && get_trace_level() > 0)
			print_space_usage(dfp,
			    "After loading/adding contents", upg_istab);
	}
	if (ProgressInCountMode())
		return (NULL);
	return (upg_istab);
}

static ulong
total_contents_lines(void)
{
	Module	*mod;
	ulong total_lines = 0;

	for (mod = get_media_head(); mod != NULL;
	    mod = mod->next) {
		if (!(mod->info.media->med_flags & BASIS_OF_UPGRADE))
			continue;
		/*
		 * don't scan for modified files if this
		 * service is actually the server's own
		 * service.
		 */
		if (mod->info.media->med_type == INSTALLED_SVC &&
		    mod->info.media->med_flags & SPLIT_FROM_SERVER)
			continue;

		if (mod->info.media->med_type == INSTALLED ||
		    mod->info.media->med_type == INSTALLED_SVC)
			total_lines += contents_lines(mod);
	}
	return (total_lines);
}

/* return the number of lines in a particular contents file */
static long
contents_lines(Module *mod)
{
	char	dbname[MAXPATHLEN];
	long	lines = 0;
	FILE	*pp;
	char	buf[BUFSIZ];
	genericdb *gdb;
	genericdb_Error gdbe;


	if (pkgdb_supported() && genericdb_exists(get_rootdir())) {
		if ((gdb = genericdb_open(get_rootdir(), 0400, 0,
		    NULL, &gdbe)) != NULL) {
			if ((lines = get_pkg_db_rowcount(NULL, NULL, gdb)) ==
			    -1) {
				genericdb_close(gdb);
				return (0);
			}
			genericdb_close(gdb);
		}
	} else {
		if (snprintf(dbname, sizeof (dbname),
		    "%s/%s/var/sadm/install/contents",
		    get_rootdir(), mod->sub->info.prod->p_rootdir) >=
		    MAXPATHLEN) {
			return (0);
		}
		if ((pp = fopen(dbname, "r")) == NULL)
			return (0);
		while (!feof(pp)) {
			if (fgets(buf, BUFSIZ, pp) != NULL)
				lines++;
		}
		(void) fclose(pp);
	}

	return (lines);
}
/*
 * get_spooled_size()
 * Get the number of blocks used by the filesystem tree specified by 'pkgdir'.
 * Parameter:	pkgdir	- directory to summarize
 * Return:	# >= 0	- block count
 */
static ulong
get_spooled_size(char *pkgdir)
{

	daddr_t	blks = 0;
	char	buf[BUFSIZ], command[MAXPATHLEN + 20];
	FILE	*pp;

	if (pkgdir == NULL) {
#ifdef DEBUG
		(void) fprintf(ef,
		    "DEBUG: get_spooled_size(): pkgdir = NULL.\n");
#endif
		return (0);

	}

	if (path_is_readable(pkgdir) != SUCCESS) {
		set_sp_err(SP_ERR_STAT, errno, pkgdir);
#ifdef DEBUG
		(void) fprintf(ef,
		    "DEBUG: get_spooled_size(): path unreadable: %s.\n",
		    pkgdir);
#endif
		return (0);
	}

	(void) snprintf(command, sizeof (command), "/usr/bin/du -sk %s",
	    pkgdir);
	if ((pp = popen(command, "r")) == NULL) {
		set_sp_err(SP_ERR_POPEN, -1, command);
#ifdef DEBUG
		(void) fprintf(ef,
		    "DEBUG: get_spooled_size(): popen failed for du.\n");
#endif
		return (0);
	}
	while (!feof(pp)) {
		if (fgets(buf, BUFSIZ, pp) != NULL) {
			buf[strlen(buf)-1] = '\0';
			(void) sscanf(buf, "%ld %*s", &blks);
		}
	}
	(void) pclose(pp);

	return (blks);
}
